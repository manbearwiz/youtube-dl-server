#
# youtube-dl Server Dockerfile
#
# https://github.com/nbr23/youtube-dl-server
#

FROM --platform=$BUILDPLATFORM node:18-alpine as nodebuild

WORKDIR /app
COPY ./front/package*.json /app
RUN npm ci
COPY ./front /app
RUN npm run build


FROM python:alpine3.17 as wheels

RUN apk add --no-cache g++
RUN pip install --upgrade --no-cache-dir pip && pip wheel --no-cache-dir --no-deps --wheel-dir /out/wheels brotli pycryptodomex websockets pyyaml

FROM python:alpine3.17
ARG YOUTUBE_DL=youtube_dl
ARG ATOMICPARSLEY=0
ARG YDLS_VERSION
ARG YDLS_RELEASE_DATE

ENV YDLS_VERSION=$YDLS_VERSION
ENV YDLS_RELEASE_DATE=$YDLS_RELEASE_DATE

VOLUME "/youtube-dl"
VOLUME "/app_config"

COPY --from=wheels /out/wheels /wheels
RUN pip install --no-cache /wheels/*

RUN mkdir -p /usr/src/app
RUN apk add --no-cache ffmpeg tzdata mailcap
RUN if [ $ATOMICPARSLEY == 1 ]; then apk add --no-cache -X http://dl-cdn.alpinelinux.org/alpine/edge/testing atomicparsley; ln /usr/bin/atomicparsley /usr/bin/AtomicParsley || true; fi
COPY ./requirements.txt /usr/src/app/
RUN pip install --upgrade pip && pip install --no-cache-dir -r <(cat /usr/src/app/requirements.txt| grep -v yt-dlp)

COPY ./config.yml /usr/src/app/default_config.yml
COPY ./ydl_server /usr/src/app/ydl_server
COPY ./youtube-dl-server.py /usr/src/app/

COPY --from=nodebuild /app/dist /usr/src/app/ydl_server/static

WORKDIR /usr/src/app

EXPOSE 8080

ENV YOUTUBE_DL=$YOUTUBE_DL
ENV YDL_CONFIG_PATH='/app_config'
CMD [ "python", "-u", "./youtube-dl-server.py" ]

HEALTHCHECK CMD wget 127.0.0.1:8080/api/info --spider -q
