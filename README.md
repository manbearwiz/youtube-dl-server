[![Docker Stars Shield](https://img.shields.io/docker/stars/kmb32123/youtube-dl-server.svg?style=flat-square)](https://hub.docker.com/r/kmb32123/youtube-dl-server/)
[![Docker Pulls Shield](https://img.shields.io/docker/pulls/kmb32123/youtube-dl-server.svg?style=flat-square)](https://hub.docker.com/r/kmb32123/youtube-dl-server/)
[![GitHub license](https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square)](https://raw.githubusercontent.com/manbearwiz/youtube-dl-server/master/LICENSE)
![Workflow](https://github.com/manbearwiz/youtube-dl-server/actions/workflows/docker-image.yml/badge.svg)

# youtube-dl-server

Very spartan Web and REST interface for downloading youtube videos onto a server. [`starlette`](https://github.com/encode/starlette) + [`yt-dlp`](https://github.com/yt-dlp/yt-dlp).

![screenshot][1]

## Running

### Docker CLI

This example uses the docker run command to create the container to run the app. Here we also use host networking for simplicity. Also note the `-v` argument. This directory will be used to output the resulting videos

```shell
docker run -d --net="host" --name youtube-dl -v /home/core/youtube-dl:/youtube-dl kmb32123/youtube-dl-server
```

To provide custom yt-dlp configuration (e.g., authentication, custom options), mount a config directory:

```shell
docker run -d --net="host" --name youtube-dl \
  -v /home/core/youtube-dl:/youtube-dl \
  -v /home/core/yt-dlp-config:/root/.config/yt-dlp \
  kmb32123/youtube-dl-server
```

Place your `config` file in `/home/core/yt-dlp-config/` with yt-dlp options (one per line). See [yt-dlp configuration documentation](https://github.com/yt-dlp/yt-dlp#configuration) for details.

### Docker Compose

A minimal example lives in [`docker-compose.example.yml`](docker-compose.example.yml). This is an example service definition that could be put in `docker-compose.yml`. This service uses a VPN client container for its networking.

```yml
  youtube-dl:
    image: "kmb32123/youtube-dl-server"
    network_mode: "service:vpn"
    volumes:
      - /home/core/youtube-dl:/youtube-dl
      - /home/core/yt-dlp-config:/root/.config/yt-dlp  # optional: custom yt-dlp config
    restart: always
```

### Python

If you have Python 3.12+ installed in your PATH you can simply run like this, providing optional environment variable overrides inline.

```shell
YDL_UPDATE_TIME=False python3 -m uvicorn youtube-dl-server:app --port 8123
```

In this example, `YDL_UPDATE_TIME=False` is the same as the command line option `--no-mtime`.

## Configuration

All behavior is controlled by environment variables (or a `.env` file read from the working directory). The process environment wins over the `.env` file, and an empty value means "not set". Booleans accept `true/1/false/0` (case-insensitive); an unparseable value is logged as a warning and the documented default is used, so a typo cannot stop the app from starting. See [`.env.example`](.env.example) for the full list with defaults: `YDL_FORMAT`, `YDL_EXTRACT_AUDIO_FORMAT`, `YDL_EXTRACT_AUDIO_QUALITY`, `YDL_RECODE_VIDEO_FORMAT`, `YDL_OUTPUT_TEMPLATE`, `YDL_ARCHIVE_FILE`, `YDL_PROXY`, `YDL_COOKIE_FILE`, `YDL_UPDATE_TIME`, `YDL_LOG_LEVEL`, and the opt-in media options `YDL_WRITE_SUBTITLES`, `YDL_SUBTITLES_LANGS`, `YDL_WRITE_THUMBNAIL`, `YDL_EMBED_METADATA`.

`YDL_FORMAT` is yt-dlp's format selector. The `format` field of a download request is a separate thing: it names a postprocessor (`mp3` extracts audio, `mp4` recodes), and an explicit request format wins for that download. `YDL_EXTRACT_AUDIO_FORMAT` and `YDL_RECODE_VIDEO_FORMAT` apply when the request names no codec or container.

Downloads run through a bounded worker pool instead of a task per request. `POST /youtube-dl/q` records a job and its response gains a `job_id` field; `success`, `url` and `options` are unchanged. A failed download is logged and recorded on the job instead of vanishing after the response was already sent as success. The job record is in-memory and bounded by `YDL_JOB_HISTORY`, so it is cleared by a restart — `YDL_ARCHIVE_FILE` remains the durable record.

The default is four concurrent downloads. Release note: before the queue, a burst of requests ran up to anyio's 40-token thread pool, so `YDL_MAX_CONCURRENT_DOWNLOADS=40` restores the previous behavior for installs that relied on parallel downloads. A single download at a time is unaffected.

The container includes a health check that probes `http://127.0.0.1:8080/healthz` — it verifies the app responds and that the output volume is writable (the most common operational failure). It makes no external network calls.

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

Add the following bookmarklet to your bookmark bar so you can conveniently send the current page url to your youtube-dl-server instance.

```javascript
javascript:!function(){fetch("http://${host}:8080/youtube-dl/q",{body:new URLSearchParams({url:window.location.href,format:"bestvideo"}),method:"POST"})}();
```

## Implementation

The server uses [`starlette`](https://github.com/encode/starlette) for the web framework and [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) to handle the downloading. The integration with yt-dlp makes use of their [python api](https://github.com/yt-dlp/yt-dlp#embedding-yt-dlp).

This docker image is based on the official [`python`](https://hub.docker.com/_/python/) alpine image, pinned in the `Dockerfile` and kept current by Dependabot.

[1]:youtube-dl-server.png
