#
# youtube-dl Server Dockerfile
#
# https://github.com/manbearwiz/youtube-dl-server-dockerfile
#

FROM python:alpine

# install dependencies
COPY requirements.txt /tmp/
RUN apk add --no-cache \
		ffmpeg \
		tzdata && \
	pip install --no-cache-dir -r /tmp/requirements.txt

# copy scripts
COPY root/ /

# cleanup
RUN rm -rf /var/cache/apk/* \
		&& rm -rf /tmp/*

CMD [ "python", "-u", "./youtube-dl-server.py" ]

# ports and volumes
EXPOSE 8080
VOLUME ["/youtube-dl"]
WORKDIR /usr/src/app
