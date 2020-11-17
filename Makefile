CONTAINER=docker.pkg.github.com/xtreamr/youtube-dl-server/youtube-dl-server
VERSION=1.0.0

docker_dev:
	docker build -t ${CONTAINER}:${VERSION} -t ${CONTAINER}:dev .

publish_dev: docker_dev
	docker push ${CONTAINER}:${VERSION}
	docker push ${CONTAINER}:dev

docker_pre:
	docker build -t ${CONTAINER}:${VERSION} -t ${CONTAINER}:pre .

publish_pre: docker_pre
	docker push ${CONTAINER}:${VERSION}
	docker push ${CONTAINER}:pre

docker_pro:
	docker build -t ${CONTAINER}:${VERSION} -t ${CONTAINER}:latest .

publish_pro: docker_pro
	docker push ${CONTAINER}:${VERSION}
	docker push ${CONTAINER}:latest
