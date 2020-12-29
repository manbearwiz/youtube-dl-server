FROM ghcr.io/linuxserver/baseimage-alpine:3.12

ENV XDG_CACHE_HOME /tmp

RUN \
	echo "**** install python ****" && \
	apk add --no-cache python3 && \
	python3 -m ensurepip && \
	rm -r /usr/lib/python*/ensurepip && \
	pip3 install --upgrade pip setuptools && \
	if [ ! -e /usr/bin/pip ]; then ln -s pip3 /usr/bin/pip ; fi && \
	if [[ ! -e /usr/bin/python ]]; then ln -sf /usr/bin/python3 /usr/bin/python; fi && \
	echo "**** install apk ****" && \
	apk add --no-cache \
		curl \
		ffmpeg \
		tzdata && \
	echo "**** install python packages ****" && \
    pip install --upgrade \
        flask \
        flask-restful \
		flask-httpauth \
        youtube-dl && \
	rm -rf \
		/root/.cache \
		/var/cache/apk/* \
		/tmp/*

COPY root/ /

RUN chmod a+x /healthcheck.sh

# ports and volumes
EXPOSE 8080
VOLUME /youtube-dl
WORKDIR /youtube-dl

HEALTHCHECK --interval=30s --timeout=30s --start-period=10s --retries=3 CMD [ "/healthcheck.sh" ]
