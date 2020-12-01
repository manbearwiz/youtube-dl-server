#
# youtube-dl Server Dockerfile
#
# https://github.com/nbr23/youtube-dl-server
#

FROM python:alpine
ARG YOUTUBE_DL=youtube_dl

RUN apk add --no-cache ffmpeg tzdata
RUN pip install --no-cache-dir bottle pyyaml ${YOUTUBE_DL}
RUN mkdir -p /usr/src/app


COPY ./bootstrap.sh /usr/src/app/
COPY ./config.yml /usr/src/app/
COPY ./ydl_server /usr/src/app/ydl_server
COPY ./youtube-dl-server.py /usr/src/app/

WORKDIR /usr/src/app

RUN apk add --no-cache wget && ./bootstrap.sh && apk del wget


EXPOSE 8080

VOLUME ["/youtube-dl"]
ENV YOUTUBE_DL=$YOUTUBE_DL
CMD [ "python", "-u", "./youtube-dl-server.py" ]
