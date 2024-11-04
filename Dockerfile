#
# youtube-dl Server Dockerfile
#
# https://github.com/nbr23/youtube-dl-server
#

ARG YOUTUBE_DL=yt-dlp
FROM --platform=$BUILDPLATFORM node:22-alpine AS nodebuild

WORKDIR /app
COPY ./front/package*.json /app
RUN npm ci
COPY ./front /app
RUN npm run build

FROM python:alpine AS wheels

RUN apk add --no-cache g++
COPY ./requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /out/wheels -r <(cat ./requirements.txt| grep -v youtube-dl | grep -v yt-dlp) \
  && pip wheel --no-cache-dir --wheel-dir /out/wheels-youtube-dl  -r <(cat ./requirements.txt| grep youtube-dl) \
  && pip wheel --no-cache-dir --wheel-dir /out/wheels-yt-dlp  -r <(cat ./requirements.txt| grep yt-dlp)

FROM python:alpine AS base
ARG ATOMICPARSLEY=0
ARG YDLS_VERSION
ARG YDLS_RELEASE_DATE

ENV YDLS_VERSION=$YDLS_VERSION
ENV YDLS_RELEASE_DATE=$YDLS_RELEASE_DATE

WORKDIR /usr/src/app
RUN apk add --no-cache ffmpeg tzdata mailcap
RUN if [ $ATOMICPARSLEY == 1 ]; then apk add --no-cache -X http://dl-cdn.alpinelinux.org/alpine/edge/testing atomicparsley; ln /usr/bin/atomicparsley /usr/bin/AtomicParsley || true; fi

VOLUME "/youtube-dl"
VOLUME "/app_config"

COPY --from=wheels /out/wheels /wheels
RUN pip install --no-cache /wheels/*

COPY ./requirements.txt /usr/src/app/

FROM base AS yt-dlp

COPY --from=wheels /out/wheels-yt-dlp /wheels
RUN pip install --no-cache /wheels/*
RUN pip install --no-cache-dir -r <(cat /usr/src/app/requirements.txt| grep -v youtube-dl)

FROM base AS youtube-dl

COPY --from=wheels /out/wheels-youtube-dl /wheels/
RUN pip install --no-cache /wheels/*
RUN pip install --no-cache-dir -r <(cat /usr/src/app/requirements.txt| grep -v yt-dlp)

FROM ${YOUTUBE_DL}

COPY ./config.yml /usr/src/app/default_config.yml
COPY ./ydl_server /usr/src/app/ydl_server
COPY ./youtube-dl-server.py /usr/src/app/

COPY --from=nodebuild /app/dist /usr/src/app/ydl_server/static

EXPOSE 8080

ENV YOUTUBE_DL=$YOUTUBE_DL
ENV YDL_CONFIG_PATH='/app_config'
CMD [ "python", "-u", "./youtube-dl-server.py" ]

HEALTHCHECK CMD wget 127.0.0.1:8080/api/info --spider -q -Y off
