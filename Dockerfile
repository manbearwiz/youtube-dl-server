#
# youtube-dl-server Dockerfile
#
# https://github.com/manbearwiz/youtube-dl-server-dockerfile
#

FROM python:alpine

ENV YDL_PORT 8080
ENV YDL_BASE_URL /youtube-dl

RUN apk add --no-cache \
  ffmpeg \
  tzdata

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

COPY requirements.txt /usr/src/app/
RUN apk --update-cache add --virtual build-dependencies gcc libc-dev make \
  && pip install --no-cache-dir -r requirements.txt \
  && apk del build-dependencies

COPY . /usr/src/app

EXPOSE ${YDL_PORT}

VOLUME ["/youtube-dl"]

CMD ["uvicorn", "youtube-dl-server:app", "--host", "0.0.0.0", "--port", ${YDL_PORT}]
