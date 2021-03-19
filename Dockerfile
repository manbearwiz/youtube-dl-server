#
# youtube-dl Server Dockerfile
#
# https://github.com/nbr23/youtube-dl-server
#

FROM python:alpine
ARG YOUTUBE_DL=youtube_dl
ARG ATOMICPARSLEY=0

RUN mkdir -p /usr/src/app
RUN apk add --no-cache ffmpeg tzdata mailcap
RUN if [ $ATOMICPARSLEY == 1 ]; then apk add --no-cache -X http://dl-cdn.alpinelinux.org/alpine/edge/testing atomicparsley; ln /usr/bin/atomicparsley /usr/bin/AtomicParsley; fi
COPY ./requirements.txt /usr/src/app/
RUN sed -i s/youtube-dl/${YOUTUBE_DL}/ /usr/src/app/requirements.txt && pip install --no-cache-dir -r /usr/src/app/requirements.txt

COPY ./bootstrap.sh /usr/src/app/
COPY ./config.yml /usr/src/app/default_config.yml
COPY ./ydl_server /usr/src/app/ydl_server
COPY ./youtube-dl-server.py /usr/src/app/

WORKDIR /usr/src/app

RUN apk add --no-cache wget && ./bootstrap.sh && apk del wget


EXPOSE 8080

VOLUME "/youtube-dl"
VOLUME "/app_config"

ENV YOUTUBE_DL=$YOUTUBE_DL
ENV YDL_CONFIG_PATH='/app_config'
CMD [ "python", "-u", "./youtube-dl-server.py" ]
