[![GitHub license](https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square)](https://raw.githubusercontent.com/manbearwiz/youtube-dl-server/master/LICENSE)

# youtube-dl-server

![Docker Stars Shield](https://img.shields.io/docker/stars/kmb32123/youtube-dl-server.svg?style=flat-square)
![Docker Pulls Shield](https://img.shields.io/docker/pulls/kmb32123/youtube-dl-server.svg?style=flat-square)
[![GitHub license](https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square)](https://raw.githubusercontent.com/manbearwiz/youtube-dl-server/master/LICENSE)

# youtube-dl-server

Very spartan and opinionated Web / REST interface for downloading youtube videos onto a server. [`bottle`](https://github.com/bottlepy/bottle) + [`youtube-dl`](https://github.com/rg3/youtube-dl).

![screenshot][1]

## How to use this image

### Configuration
Use environment variable _"SUB_LANGS"_ = enUS or deDE or valid lists to specify subtitles to pass to the `--sub-lang` parameter.

Specify an archive file with _"ARCHIVE_FILE"_. Default is _"/youtube-dl/yt-dl_archive.txt"_.

### Run on host networking

This example uses host networking for simplicity. Also note the `-v` argument. This directory will be used to output the resulting videos

```shell
docker run -d --net="host" --name youtube-dl -v /home/core/youtube-dl:/youtube-dl kmb32123/youtube-dl-server
```

### Alpine

There is now a working image based on Alpine linux that is much smaller. This will likely become the main image in the future

```shell
docker run kmb32123/youtube-dl-server:alpine
```

### Start a download remotely

Downloads can be triggered by supplying the `{{url}}` of the requested video through the Web UI or through the REST interface via curl, etc.

#### HTML

Just navigate to `http://{{address}}:8080/youtube-dl` and enter the requested `{{url}}`.

#### Curl

```shell
curl -X POST --data-urlencode "url={{url}}" http://{{address}}:8080/youtube-dl/q
```

## Implementation

The server uses [`bottle`](https://github.com/bottlepy/bottle) for the web framework and [`youtube-dl`](https://github.com/rg3/youtube-dl) to handle the downloading. For better or worse, the calls to youtube-dl are made through the shell rather then through the python API.

This docker image is based on [`python:3-onbuild`](https://registry.hub.docker.com/_/python/) and consequently [`debian:jessie`](https://registry.hub.docker.com/u/library/debian/).

[1]: https://raw.githubusercontent.com/manbearwiz/youtube-dl-server/master/youtube-dl-server.png
