#
# youtube-dl Server Dockerfile
#
# https://github.com/manbearwiz/youtube-dl-server-dockerfile
#

FROM python:alpine

RUN apk add --no-cache ffmpeg tzdata curl wget

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

COPY requirements.txt /usr/src/app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /usr/src/app

# Download static files (JS/CSS Libraries)
WORKDIR /usr/src/app/static
RUN curl -s https://code.jquery.com/jquery-3.4.1.min.js > js/jquery.min.js
RUN curl -s https://unpkg.com/@popperjs/core@2.1.1/dist/umd/popper.min.js > js/popper.min.js
RUN wget https://github.com/twbs/bootstrap/releases/download/v4.4.1/bootstrap-4.4.1-dist.zip
RUN mkdir tmp_bs
RUN unzip bootstrap-4.4.1-dist.zip -d tmp_bs
RUN mv tmp_bs/*/css/* css/
RUN mv tmp_bs/*/js/* js/
RUN rm -rf bootstrap-4.4.1-dist.zip tmp_bs

EXPOSE 8080

WORKDIR /usr/src/app
VOLUME ["/youtube-dl"]

CMD [ "python", "-u", "./youtube-dl-server.py" ]
