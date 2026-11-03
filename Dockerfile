#
# youtube-dl-server Dockerfile
#
# https://github.com/manbearwiz/youtube-dl-server-dockerfile
#

# Pinned for reproducible builds; kept current by Dependabot (.github/dependabot.yml).
# 3.15.2 rather than 3.15.0: 3.15.0-alpine3.24 has no arm/v6 or arm/v7 builds, which
# this image publishes (see .github/workflows/docker-image.yml).
FROM python:3.15.2-alpine3.24

# Install JS runtime for yt-dlp based on architecture
# deno is available on: x86_64 (amd64), aarch64 (arm64)
# nodejs fallback for: armv7, armhf, armv6, armel and other architectures
RUN apk add --no-cache ffmpeg tzdata && \
  ARCH=$(apk --print-arch) && \
  case "$ARCH" in \
    x86_64|aarch64) \
      apk add --no-cache deno \
      ;; \
    *) \
      apk add --no-cache nodejs && \
      mkdir -p /etc/yt-dlp && \
      echo "--js-runtimes node" > /etc/yt-dlp/config \
      ;; \
  esac

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

COPY requirements.txt /usr/src/app/
RUN apk --update-cache add --virtual build-dependencies gcc libc-dev make \
  && pip install --no-cache-dir -r requirements.txt \
  && apk del build-dependencies

COPY . /usr/src/app

EXPOSE 8080

VOLUME ["/youtube-dl", "/root/.config/yt-dlp"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD wget -q --spider http://127.0.0.1:8080/healthz || exit 1

CMD ["uvicorn", "youtube-dl-server:app", "--host", "0.0.0.0", "--port", "8080"]
