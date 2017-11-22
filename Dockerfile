#
# youtube-dl Server Dockerfile
#
# https://github.com/brandong777/youtube-dl-server-dockerfile
#

# Pull base image.
FROM python:3-onbuild

# Install ffmpeg.
RUN \
  apt-get update && \
  apt-get install -y libav-tools && \
  rm -rf /var/lib/apt/lists/*

# Copy default youtube-dl.conf
COPY youtube-dl.conf /config/youtube-dl.conf
  
EXPOSE 8080

VOLUME /config /youtube-dl

CMD [ "python", "-u", "./youtube-dl-server.py" ]
