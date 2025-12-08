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

FROM python:alpine AS venv
ENV PYTHON_ENV="/usr/local/python-env"

RUN apk add --no-cache g++
COPY ./requirements.txt .
RUN pip install uv --break-system-packages && \
    uv venv $PYTHON_ENV && \
    source $PYTHON_ENV/bin/activate && \
    uv pip install -r <(cat ./requirements.txt| grep -v youtube-dl | grep -v yt-dlp) && \
    uv pip install pip

FROM venv AS venv-yt-dlp

RUN source $PYTHON_ENV/bin/activate && \
  uv pip install -r <(cat ./requirements.txt| grep yt-dlp)

FROM venv AS venv-youtube-dl

RUN source $PYTHON_ENV/bin/activate && \
  uv pip install -r <(cat ./requirements.txt| grep youtube-dl)


FROM python:alpine AS base
ENV PYTHON_ENV="/usr/local/python-env"
ARG ATOMICPARSLEY=0
ARG YDLS_VERSION
ARG YDLS_RELEASE_DATE

ENV YDLS_VERSION=$YDLS_VERSION
ENV YDLS_RELEASE_DATE=$YDLS_RELEASE_DATE

WORKDIR /usr/src/app
RUN apk add --no-cache ffmpeg tzdata mailcap && \
  if [ $ATOMICPARSLEY == 1 ]; then apk add --no-cache -X http://dl-cdn.alpinelinux.org/alpine/edge/testing atomicparsley; ln /usr/bin/atomicparsley /usr/bin/AtomicParsley || true; fi

VOLUME "/youtube-dl"
VOLUME "/app_config"

FROM base AS yt-dlp
COPY --from=venv-yt-dlp $PYTHON_ENV $PYTHON_ENV
RUN apk add --no-cache deno

FROM base AS youtube-dl
COPY --from=venv-youtube-dl $PYTHON_ENV $PYTHON_ENV

FROM ${YOUTUBE_DL}

COPY ./config.yml /usr/src/app/default_config.yml
COPY ./ydl_server /usr/src/app/ydl_server
COPY ./youtube-dl-server.py /usr/src/app/

COPY --from=nodebuild /app/dist /usr/src/app/ydl_server/static

EXPOSE 8080

ENV YOUTUBE_DL=$YOUTUBE_DL
ENV YDL_CONFIG_PATH='/app_config'
ENV PATH="${PYTHON_ENV}/bin:$PATH"

CMD [ "python", "-u", "./youtube-dl-server.py" ]

HEALTHCHECK CMD wget 127.0.0.1:8080/api/info --spider -q -Y off
