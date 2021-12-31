pipeline {
    agent any
    stages {


        stage('Checkout'){
            steps {
                checkout scm
            }
        }

        stage('Dockerhub login') {
            steps {
                withCredentials([usernamePassword(credentialsId: 'dockerhub', usernameVariable: 'DOCKERHUB_CREDENTIALS_USR', passwordVariable: 'DOCKERHUB_CREDENTIALS_PSW')]) {
                    sh 'docker login -u $DOCKERHUB_CREDENTIALS_USR -p "$DOCKERHUB_CREDENTIALS_PSW"'
                }
            }
        }
        stage('Build Youtube-dl Image') {
            steps {
                sh '''
                    BUILDER=`docker buildx create --use`
                    docker buildx build --platform linux/amd64,linux/arm64,linux/arm/v7 --build-arg ATOMICPARSLEY=1 -t nbr23/youtube-dl-server:latest -t nbr23/youtube-dl-server:youtube-dl -t nbr23/youtube-dl-server:youtube-dl_atomicparsley --push .
                    docker buildx rm $BUILDER
                    '''
            }
        }

        stage('Build Youtube-dl yt_dlp Image') {
            steps {
                sh '''
                    BUILDER=`docker buildx create --use`
                    docker buildx build --platform linux/amd64,linux/arm64,linux/arm/v7 --build-arg YOUTUBE_DL=yt_dlp --build-arg ATOMICPARSLEY=1 -t nbr23/youtube-dl-server:yt-dlp -t nbr23/youtube-dl-server:yt-dlp_atomicparsley --push .
                    docker buildx rm $BUILDER
                    '''
            }
        }
    }

    post {
        always {
            sh 'docker logout'
        }
    }
}