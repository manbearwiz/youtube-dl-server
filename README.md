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

This is an example service definition that could be put in `docker-compose.yml`. This service uses a VPN client container for its networking.

```yml
  youtube-dl:
    image: "kmb32123/youtube-dl-server"
    network_mode: "service:vpn"
    volumes:
      - /home/core/youtube-dl:/youtube-dl
      - /home/core/yt-dlp-config:/root/.config/yt-dlp  # optional: custom yt-dlp config
    restart: always
```

### Using an existing HTTP proxy (Docker / Unraid)

Set the optional `YDL_PROXY` environment variable to the URL of an existing
HTTP proxy, for example `http://192.168.1.10:8118`. It is passed directly to
yt-dlp's `proxy` option for outbound requests and downloads. Leaving it unset
or blank preserves existing behavior, including yt-dlp's normal proxy discovery.
This setting does not create or manage a VPN.

For example, a Binhex VPN container with Privoxy enabled can provide the proxy
on port `8118`. Publish that port, allow access from youtube-dl-server in the
proxy's configuration, and replace the example IP with your Unraid server's IP:

```shell
docker run -d --name youtube-dl-server -p 8080:8080 \
  -v /home/core/youtube-dl:/youtube-dl \
  -e YDL_PROXY=http://192.168.1.10:8118 \
  kmb32123/youtube-dl-server
```

On Unraid, keep the normal bridge network and WebUI port mapping, and add a
Variable named `YDL_PROXY` with value `http://UNRAID-IP:8118` (replace
`UNRAID-IP` with the actual IP). Traffic flows from yt-dlp through Privoxy and
the proxy container's VPN. This avoids sharing the VPN container's network
namespace, so the YTDL WebUI remains reachable normally at
`http://UNRAID-IP:8080/youtube-dl`. Only traffic using the configured proxy
follows that route; VPN availability and traffic blocking depend on the proxy
container's configuration.

To verify the public IP seen by yt-dlp, run this on the Docker / Unraid host:

```shell
docker exec -i youtube-dl-server python3 - <<'PY'
import os
from yt_dlp import YoutubeDL

with YoutubeDL({
    "proxy": os.environ.get("YDL_PROXY") or None,
    "quiet": True,
    "no_warnings": True,
}) as ydl:
    response = ydl.urlopen('https://api.ipify.org')
    print("Public IP seen by yt-dlp:", response.read().decode())
PY
```

With `YDL_PROXY` configured, compare the result with the VPN container's public
IP; they should match. This checks the yt-dlp request path rather than a
separate tool's proxy settings.

### Python

If you have python ^3.6.0 installed in your PATH you can simply run like this, providing optional environment variable overrides inline.

```shell
YDL_UPDATE_TIME=False python3 -m uvicorn youtube-dl-server:app --port 8123
```

In this example, `YDL_UPDATE_TIME=False` is the same as the command line option `--no-mtime`.

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

The server uses [`starlette`](https://github.com/encode/starlette) for the web framework and [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) to handle the downloading. The integration with yt-dlp makes use of their [python api](https://github.com/yt-dlp/yt-dlp#embedding-yt-dlp).

This docker image is based on [`python:alpine`](https://registry.hub.docker.com/_/python/) and consequently [`alpine:3.8`](https://hub.docker.com/_/alpine/).

[1]:youtube-dl-server.png
