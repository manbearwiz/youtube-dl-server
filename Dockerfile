#
# youtube-dl Server Dockerfile
#
# https://github.com/manbearwiz/youtube-dl-server-dockerfile
#

# FROM python:alpine
# for armhf
FROM lsiobase/alpine.python3.armhf

RUN apk add --no-cache \
  ffmpeg \
  tzdata

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

COPY requirements.txt /usr/src/app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /usr/src/app

EXPOSE 8080

VOLUME ["/youtube-dl"]

#ifelse: fatal: unable to exec python: no such file or directory
#CMD [ "python", "-u", "./youtube-dl-server.py" ]
CMD [ "python3", "-u", "./youtube-dl-server.py" ]
