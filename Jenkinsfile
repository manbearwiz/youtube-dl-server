pipeline {
    agent any

    options {
        disableConcurrentBuilds()
    }

    stages {
        stage('Checkout'){
            steps {
                checkout scm
            }
        }
        stage('Linting') {
            steps {
                script {
                    sh "ruff check .";
                }
            }
        }
        stage('Prep buildx') {
            steps {
                script {
                    env.BUILDX_BUILDER = getBuildxBuilder();
                }
            }
        }
        stage('Build yt_dlp Image') {
            steps {
                withCredentials([usernamePassword(credentialsId: 'dockerhub', usernameVariable: 'DOCKERHUB_CREDENTIALS_USR', passwordVariable: 'DOCKERHUB_CREDENTIALS_PSW')]) {
                    sh 'docker login -u $DOCKERHUB_CREDENTIALS_USR -p "$DOCKERHUB_CREDENTIALS_PSW"'
                }
                sh """
                    docker buildx build \
                        --pull \
                        --builder \$BUILDX_BUILDER  \
                        --platform linux/amd64,linux/arm64,linux/arm/v7 \
                        --build-arg YDLS_VERSION=`git rev-parse --short HEAD` \
                        --build-arg YDLS_RELEASE_DATE="`git log -1 --pretty='format:%cd' --date=format:'%Y-%m-%d %H:%M:%S'`" \
                        --build-arg YOUTUBE_DL=yt-dlp \
                        --build-arg ATOMICPARSLEY=1 \
                        -t nbr23/youtube-dl-server:yt-dlp \
                        -t nbr23/youtube-dl-server:`git rev-parse --short HEAD`-yt-dlp \
                        -t nbr23/youtube-dl-server:${GIT_COMMIT}-`date +%s`-yt-dlp \
                        -t nbr23/youtube-dl-server:yt-dlp_atomicparsley \
                        ${ "$GIT_BRANCH" == "master" ? "--push" : ""} .
                    """
            }
        }
        stage('Build Youtube-dl Image') {
            steps {
                withCredentials([usernamePassword(credentialsId: 'dockerhub', usernameVariable: 'DOCKERHUB_CREDENTIALS_USR', passwordVariable: 'DOCKERHUB_CREDENTIALS_PSW')]) {
                    sh 'docker login -u $DOCKERHUB_CREDENTIALS_USR -p "$DOCKERHUB_CREDENTIALS_PSW"'
                }
                sh """
                    docker buildx build \
                        --pull \
                        --builder \$BUILDX_BUILDER \
                        --platform linux/amd64,linux/arm64,linux/arm/v7 \
                        --build-arg YDLS_VERSION=`git rev-parse --short HEAD` \
                        --build-arg YDLS_RELEASE_DATE="`git log -1 --pretty='format:%cd' --date=format:'%Y-%m-%d %H:%M:%S'`" \
                        --build-arg ATOMICPARSLEY=1 \
                        --build-arg YOUTUBE_DL=youtube-dl \
                        -t nbr23/youtube-dl-server:latest \
                        -t nbr23/youtube-dl-server:youtube-dl \
                        -t nbr23/youtube-dl-server:`git rev-parse --short HEAD`-youtube-dl \
                        -t nbr23/youtube-dl-server:${GIT_COMMIT}-`date +%s`-youtube-dl \
                        -t nbr23/youtube-dl-server:youtube-dl_atomicparsley \
                        ${ "$GIT_BRANCH" == "master" ? "--push" : ""} .
                    """
            }
        }
        stage('Sync github repo') {
            when { branch 'master' }
            steps {
                syncRemoteBranch('git@github.com:nbr23/youtube-dl-server.git', 'master')
            }
        }
    }
    post {
        always {
            sh 'docker buildx stop $BUILDX_BUILDER || true'
            sh 'docker buildx rm $BUILDX_BUILDER || true'
        }
    }
}
