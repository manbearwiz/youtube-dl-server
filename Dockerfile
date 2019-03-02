FROM python:alpine

# install dependencies
RUN apk add --no-cache \
		ffmpeg \
		tzdata && \
	pip install --upgrade --force-reinstall --ignore-installed \
		bottle youtube-dl && \
	rm -rf \
	    /root/.cache \
	    /var/cache/apk/* \
	    /tmp/*

# copy scripts
COPY root/ /

# ports and volumes
EXPOSE 8080
VOLUME /youtube-dl /incomplete
WORKDIR /usr/src/app

CMD [ "python", "-u", "./youtube-dl-server.py" ]
