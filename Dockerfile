#
# youtube-dl Server Dockerfile
#


# Pull base image.
FROM python:3-onbuild

# Install ffmpeg.
RUN \
  apt-get update && \
  apt-get install -y libav-tools libavcodec-extra && \
  rm -rf /var/lib/apt/lists/* \
  pip install --upgrade youtube-dl

EXPOSE 8080

VOLUME ["/youtube-dl"]

CMD [ "python", "-u", "./youtube-dl-server.py" ]
