#
# youtube-dl-server Dockerfile
#
# https://github.com/manbearwiz/youtube-dl-server-dockerfile
#

# Build stage
FROM python:3.12-slim AS builder

WORKDIR /usr/src/app

COPY requirements.txt .

# Install build dependencies and Python packages in one layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && pip install --no-cache-dir --root-user-action=ignore --prefix=/install -r requirements.txt \
    && apt-get purge -y --auto-remove build-essential \
    && rm -rf /var/lib/apt/lists/*

# Runtime stage
FROM python:alpine

RUN apk add --no-cache \
  ffmpeg \
  tzdata \
  nodejs

# Copy Python packages from builder
COPY --from=builder /install /usr/local

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

COPY . /usr/src/app

# Create yt-dlp config directory and set Node.js as the JavaScript runtime
RUN mkdir -p /etc/yt-dlp && \
  echo "--js-runtimes node" > /etc/yt-dlp/config

EXPOSE 8080

VOLUME ["/youtube-dl", "/root/.config/yt-dlp"]

CMD ["uvicorn", "youtube-dl-server:app", "--host", "0.0.0.0", "--port", "8080"]
