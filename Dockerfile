#
# youtube-dl-server Dockerfile
#
# https://github.com/manbearwiz/youtube-dl-server-dockerfile
#

FROM python:alpine

# Install common dependencies shared across all architectures
# ffmpeg, tzdata, and common JS runtime dependencies
RUN apk add --no-cache \
  ffmpeg \
  tzdata \
  ca-certificates \
  libgcc \
  libstdc++ \
  icu-libs \
  simdutf \
  sqlite-libs \
  zstd-libs

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

COPY requirements.txt /usr/src/app/
RUN apk --update-cache add --virtual build-dependencies gcc libc-dev make \
  && pip install --no-cache-dir -r requirements.txt \
  && apk del build-dependencies

COPY . /usr/src/app

# Install JS runtime for yt-dlp based on architecture (at end to maximize cache reuse)
ARG TARGETARCH
RUN if [ "$TARGETARCH" = "amd64" ] || [ "$TARGETARCH" = "arm64" ]; then \
      apk add --no-cache deno; \
    else \
      apk add --no-cache nodejs && \
      mkdir -p /etc/yt-dlp && \
      echo "--js-runtimes node" > /etc/yt-dlp/config; \
    fi

EXPOSE 8080

VOLUME ["/youtube-dl", "/root/.config/yt-dlp"]

CMD ["uvicorn", "youtube-dl-server:app", "--host", "0.0.0.0", "--port", "8080"]
