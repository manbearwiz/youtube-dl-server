#
# youtube-dl Server Dockerfile
#
# https://github.com/kmb32123/youtube-dl-server-dockerfile
#

# Pull base image.
FROM python:3-onbuild

# Install ffmpeg.
RUN \
  apt-get update && \
  apt-get install -y libav-tools && \
  rm -rf /var/lib/apt/lists/*

VOLUME ["/youtube-dl"]

WORKDIR /youtube-dl

CMD python youtube-dl-server.py
