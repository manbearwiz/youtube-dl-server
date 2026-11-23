pipeline {
    agent any

    options {
        disableConcurrentBuilds()
    }

    stages {
        stage('Checkout') {
            steps {
                script {
                    def revision = checkout scm
                    env.PREVIOUS_SUCCESSFUL_COMMIT = revision.GIT_PREVIOUS_SUCCESSFUL_COMMIT ?: ''
                }
            }
        }
        stage('Version') {
            steps {
                script {
                    env.RELEASE_VERSION = sh(
                        returnStdout: true,
                        script: '''#!/bin/bash
                            set -euo pipefail
                            version="$(cat ydl_server/VERSION)"
                            version_pattern='^(0|[1-9][0-9]*)[.](0|[1-9][0-9]*)[.](0|[1-9][0-9]*)$'
                            if [[ ! "$version" =~ $version_pattern ]]; then
                                echo "Expected MAJOR.MINOR.PATCH in ydl_server/VERSION" >&2
                                exit 1
                            fi

                            if [[ "${BRANCH_NAME:-}" != master ]]; then
                                exit 0
                            fi

                            base="${PREVIOUS_SUCCESSFUL_COMMIT:-}"
                            if [[ -z "$base" ]]; then
                                base="$(git rev-parse --verify HEAD^1)"
                            fi
                            if ! git merge-base --is-ancestor "$base" HEAD; then
                                echo "Cannot compare versions without checkout history back to $base" >&2
                                exit 1
                            fi

                            version_entry="$(git ls-tree "$base" -- ydl_server/VERSION)"
                            if [[ -n "$version_entry" ]]; then
                                previous_version="$(git show "${base}:ydl_server/VERSION")"
                                if [[ ! "$previous_version" =~ $version_pattern ]]; then
                                    echo "Invalid release version at $base" >&2
                                    exit 1
                                fi
                                if [[ "$version" == "$previous_version" ]]; then
                                    exit 0
                                fi
                                highest_version="$(printf '%s\\n' "$previous_version" "$version" | LC_ALL=C sort -V | tail -n 1)"
                                if [[ "$highest_version" != "$version" ]]; then
                                    echo "Release version $version is lower than $previous_version" >&2
                                    exit 1
                                fi
                            fi

                            echo "$version"
                        '''
                    ).trim()
                }
            }
        }
        stage('Linting') {
            steps {
                sh 'ruff check .'
            }
        }
        stage('Prep buildx') {
            steps {
                script {
                    env.BUILDX_BUILDER = getBuildxBuilder();
                }
            }
        }
        stage('Tests') {
            steps {
                sh '''#!/bin/bash
                    set -euo pipefail
                    test_image="youtube-dl-server-tests:${BUILD_TAG}"
                    trap 'docker image rm "$test_image" >/dev/null' EXIT
                    docker buildx build \
                        --pull \
                        --builder "$BUILDX_BUILDER" \
                        --target test \
                        --load \
                        --tag "$test_image" .
                    docker run --rm "$test_image"
                '''
            }
        }
        stage('Build production images') {
            when { expression { !env.RELEASE_VERSION } }
            steps {
                buildProductionImages()
            }
        }
        stage('Sync GitHub repo') {
            when { branch 'master' }
            steps {
                ghSync()
            }
        }
        stage('Publish release images') {
            when { expression { env.RELEASE_VERSION } }
            steps {
                withCredentials([usernamePassword(credentialsId: 'dockerhub', usernameVariable: 'DOCKERHUB_CREDENTIALS_USR', passwordVariable: 'DOCKERHUB_CREDENTIALS_PSW')]) {
                    buildProductionImages()
                }
            }
        }
    }
}

def buildProductionImages() {
    sh '''#!/bin/bash
        set -euo pipefail
        repository="nbr23/youtube-dl-server"
        release_date="$(git log -1 --format=%cd --date=format:'%Y-%m-%d %H:%M:%S')"
        version="${RELEASE_VERSION:-}"

        if [[ -n "$version" ]]; then
            docker login --username "$DOCKERHUB_CREDENTIALS_USR" --password-stdin <<< "$DOCKERHUB_CREDENTIALS_PSW"
        fi

        for downloader in yt-dlp youtube-dl; do
            publish_args=()
            if [[ -n "$version" ]]; then
                publish_args=(--push --tag "$repository:$version-$downloader")
                if [[ "$downloader" == yt-dlp ]]; then
                    publish_args+=(--tag "$repository:$version")
                fi
            fi

            docker buildx build \\
                --pull \\
                --builder "$BUILDX_BUILDER" \\
                --platform linux/amd64,linux/arm64,linux/arm/v7 \\
                --build-arg "YDLS_RELEASE_DATE=$release_date" \\
                --build-arg "YOUTUBE_DL=$downloader" \\
                --build-arg ATOMICPARSLEY=1 \\
                "${publish_args[@]}" .
        done

        if [[ -n "$version" ]]; then
            docker buildx imagetools create \\
                --builder "$BUILDX_BUILDER" \\
                --tag "$repository:youtube-dl" \\
                --tag "$repository:youtube-dl_atomicparsley" \\
                "$repository:$version-youtube-dl"
            docker buildx imagetools create \\
                --builder "$BUILDX_BUILDER" \\
                --tag "$repository:yt-dlp" \\
                --tag "$repository:yt-dlp_atomicparsley" \\
                --tag "$repository:latest" \\
                "$repository:$version-yt-dlp"
        fi
    '''
}
