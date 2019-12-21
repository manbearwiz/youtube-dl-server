FROM lsiobase/alpine:3.11

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
		ffmpeg \
		tzdata && \
	echo "**** install python packages ****" && \
    pip install --upgrade \
        flask \
        flask-restful \
        youtube-dl && \
	rm -rf \
	    /root/.cache \
	    /var/cache/apk/* \
	    /tmp/*

COPY root/ /

# ports and volumes
EXPOSE 8080
VOLUME /youtube-dl
WORKDIR /youtube-dl
