#
# youtube-dl-server Dockerfile
#
# https://github.com/manbearwiz/youtube-dl-server-dockerfile
#

FROM python:alpine

RUN apk add --no-cache \
  ffmpeg \
  tzdata \
  nodejs

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

COPY requirements.txt /usr/src/app/
RUN apk --update-cache add --virtual build-dependencies gcc libc-dev make \
  && pip install --no-cache-dir -r requirements.txt \
  && apk del build-dependencies

COPY . /usr/src/app

# Create yt-dlp config directory and set Node.js as the JavaScript runtime
RUN mkdir -p /etc/yt-dlp && \
  echo "--js-runtimes node" > /etc/yt-dlp/config

EXPOSE 8080

VOLUME ["/youtube-dl", "/root/.config/yt-dlp"]

CMD ["uvicorn", "youtube-dl-server:app", "--host", "0.0.0.0", "--port", "8080"]
