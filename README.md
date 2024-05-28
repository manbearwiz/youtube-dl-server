[![Docker Stars Shield](https://img.shields.io/docker/stars/qx6ghqkz/youtube-dl-server.svg?style=flat-square)](https://hub.docker.com/r/qx6ghqkz/youtube-dl-server/)
[![Docker Pulls Shield](https://img.shields.io/docker/pulls/qx6ghqkz/youtube-dl-server.svg?style=flat-square)](https://hub.docker.com/r/qx6ghqkz/youtube-dl-server/)
[![GitHub license](https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square)](https://raw.githubusercontent.com/qx6ghqkz/youtube-dl-server/master/LICENSE)

# youtube-dl-server

Very spartan Web and REST interface for downloading youtube videos onto a server. [`starlette`](https://github.com/encode/starlette) + [`yt-dlp`](https://github.com/yt-dlp/yt-dlp).

![screenshot][1]

## Running

### Docker CLI

This example uses the docker run command to create the container to run the app. Here we also use host networking for simplicity. Also note the `-v` argument. This directory will be used to output the resulting videos.

```shell
docker run -d --net="host" --name youtube-dl -v /home/core/youtube-dl:/youtube-dl qx6ghqkz/youtube-dl-server
```

### Docker Compose

This is an example service definition that could be put in `docker-compose.yml`. This service uses a VPN client container for its networking.

```yml
  youtube-dl:
    image: "qx6ghqkz/youtube-dl-server"
    network_mode: "service:vpn"
    volumes:
      - /home/core/youtube-dl:/youtube-dl
    restart: always
```

### Python

If you have python ^3.6.0 installed in your PATH you can simply run like this, providing optional environment variable overrides inline.

```shell
YDL_UPDATE_TIME=False python3 -m uvicorn youtube-dl-server:app --port 8123
```

In this example, `YDL_UPDATE_TIME=False` is the same as the command line option `--no-mtime`.

### Environment variables

Environment variables can be set to change different settings, for example using docker run.

```shell
docker run -d \
  --name youtube-dl \
  --user 1000:1000 \
  -p 7080:8080 \
  --mount type=bind,source='/path/to/videos',target='/youtube-dl' \
  -v '/path/to/data':'/data' \
  -e YDL_FORMAT='bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best' \
  -e YDL_OUTPUT_TEMPLATE='/youtube-dl/%(title).200s.%(ext)s' \
  -e YDL_ARCHIVE_FILE='/data/archive.txt' \
  -e YDL_IGNORE_ERRORS=True \
  -e YDL_WRITE_THUMBNAIL=True \
  -e YDL_WRITE_SUBTITLES=True \
  -e YDL_SUBTITLES_FORMAT='srt' \
  -e YDL_SUBTITLES_LANGS='all' \
  -e YDL_EMBED_METADATA=True \
  --restart unless-stopped \
  qx6ghqkz/youtube-dl-server
```
Environment variables can also be placed in a `.env ` file when using `docker compose up`.

| Environment variable | Default value | Notes |
| --- | --- | --- |
| YDL_FORMAT | bestvideo+bestaudio/best |
| YDL_EXTRACT_AUDIO_FORMAT | None | Can be set using the web interface
| YDL_EXTRACT_AUDIO_QUALITY |192 |
| YDL_RECODE_VIDEO_FORMAT | None | Can be set using the web interface
| YDL_OUTPUT_TEMPLATE | /youtube-dl/%(title).200s [%(id)s].%(ext)s |
| YDL_ARCHIVE_FILE | None |
| YDL_UPDATE_TIME | True |
| YDL_IGNORE_ERRORS | True |
| YDL_RESTRICT_FILENAMES | False |
| YDL_GEO_BYPASS | False |
| YDL_WRITE_THUMBNAIL | True
| YDL_WRITE_SUBTITLES | False |
| YDL_SUBTITLES_FORMAT | None |
| YDL_SUBTITLES_LANGS | all |
| YDL_EMBED_METADATA | False |

For more information on these options, see the [yt-dlp docs](https://github.com/yt-dlp/yt-dlp?tab=readme-ov-file#usage-and-options) and [YouTubeDL object parameters](https://github.com/yt-dlp/yt-dlp/blob/12b248ce60be1aa1362edd839d915bba70dbee4b/yt_dlp/YoutubeDL.py#L176-L565).

## Usage

### Start a download remotely

Downloads can be triggered by supplying the `{{url}}` of the requested video through the Web UI or through the REST interface via curl, etc.

#### HTML

Just navigate to `http://{{host}}:8080/youtube-dl` and enter the requested `{{url}}`.

#### Curl

```shell
curl -X POST --data-urlencode "url={{url}}" http://{{host}}:8080/youtube-dl/q
```

#### Fetch

```javascript
fetch(`http://${host}:8080/youtube-dl/q`, {
  method: "POST",
  body: new URLSearchParams({
    url: url,
    format: "bestvideo"
  }),
});
```

#### Bookmarklet

Add the following bookmarklet to your bookmark bar so you can conviently send the current page url to your youtube-dl-server instance.

```javascript
javascript:!function(){fetch("http://${host}:8080/youtube-dl/q",{body:new URLSearchParams({url:window.location.href,format:"bestvideo"}),method:"POST"})}();
```

## Implementation

The server uses [`starlette`](https://github.com/encode/starlette) for the web framework and [`youtube-dl`](https://github.com/rg3/youtube-dl) to handle the downloading. The integration with youtube-dl makes use of their [python api](https://github.com/rg3/youtube-dl#embedding-youtube-dl).

This docker image is based on [`python:alpine`](https://registry.hub.docker.com/_/python/) and consequently [`alpine:3.8`](https://hub.docker.com/_/alpine/).

[1]:youtube-dl-server.png
