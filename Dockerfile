#
# youtube-dl Server Dockerfile
#
# https://github.com/manbearwiz/youtube-dl-server-dockerfile
#

FROM python:alpine

# install dependencies
RUN apk add --no-cache \
		ffmpeg \
		tzdata && \
	pip install --upgrade --force-reinstall --ignore-installed \
		bottle youtube-dl && \
	rm -r /root/.cache && \
	rm -rf /var/cache/apk/* && \
	rm -rf /tmp/*

# copy scripts
COPY root/ /

# ports and volumes
EXPOSE 8080
VOLUME ["/youtube-dl"]
WORKDIR /usr/src/app

CMD [ "python", "-u", "./youtube-dl-server.py" ]
