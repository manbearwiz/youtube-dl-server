![Docker Stars Shield](https://img.shields.io/docker/stars/nbr23/youtube-dl-server.svg?style=flat-square)
![Docker Pulls Shield](https://img.shields.io/docker/pulls/nbr23/youtube-dl-server.svg?style=flat-square)
[![GitHub license](https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square)](https://raw.githubusercontent.com/nbr23/youtube-dl-server/master/LICENSE)

# youtube-dl-server

Simple Web and REST interface for downloading youtube videos onto a server.
[`bottle`](https://github.com/bottlepy/bottle) +
[`youtube-dl`](https://github.com/rg3/youtube-dl) /
[`youtube-dlc`](https://github.com/blackjack4494/yt-dlc)

Forked from [manbearwiz/youtube-dl-server](https://github.com/manbearwiz/youtube-dl-server).

![screenshot][1]


![screenshot][2]

## Running

For easier deployment, a docker image is available on
[dockerhub](https://hub.docker.com/r/nbr23/youtube-dl-server).

The `latest` tag uses `youtube-dl`.

Force using `youtube-dl` or `youtube-dlc` by using the tags of the same name,
eg: `nbr23/youtube-dl-server:youtube-dl` and
`nbr23/youtube-dl-server:youtube-dlc`.

*Note: the legacy version using `config.py` is available on the
[legacy](https://github.com/nbr23/youtube-dl-server/tree/legacy) branch,
and through the `legacy` tag on docker.*

### Docker CLI

This example uses the docker run command to create the container to run the
app. Note the `-v` argument to specify the volume and its binding on the host.
This directory will be used to output the resulting videos.

```shell
docker run -d --name youtube-dl -v $HOME/youtube-dl:/youtube-dl nbr23/youtube-dl-server:latest
```

### Docker Compose

This is an example service definition that could be put in `docker-compose.yml`.

```yml
  youtube-dl:
    image: "nbr23/youtube-dl-server:latest"
    volumes:
      - $HOME/youtube-dl:/youtube-dl
      - ./config.yml:/usr/src/app/config.yml:ro # Overwrite the container's config file with your own configuration
    restart: always
```

#### Configuration

Configuration is done through the config.yml file at the root of the project.

An alternate configuration file path can be forced by setting the environment
variable `YDL_CONFIG_PATH`:

```shell
export YDL_CONFIG_PATH=/var/local/youtube-dl-server/config.yml
```

The configuration file must contain at least the following variables:

```yaml
ydl_server:
  port: 8080
  host: 0.0.0.0
  metadata_db_path: '/youtube-dl/.ydl-metadata.db'

ydl_options:
  output: '/youtube-dl/%(title)s [%(id)s].%(ext)s'
  cache-dir: '/youtube-dl/.cache'
```

Additional youtube-dl parameters can be set in the `ydl_options` sections. To
do this, simply add regular youtube-dl parameters, removing the leading `--`.

For example, to write subtitles in spanish, the youtube-dl command would be:

`youtube-dl --write-sub --sub-lang es URL`

Which would translate to the following `ydl_options` in `config.yml`:

```yaml
ydl_options:
  output: '/tmp/youtube-dl/%(title)s [%(id)s].%(ext)s'
  cache-dir: '/tmp/youtube-dl/.cache'
  write-sub: True
  sub-lang: es
```

### Python

If you have python ^3.3.0 installed in your PATH you can simply run like this,
providing optional environment variable overrides inline.

You will need `bottle`, `pyyaml` and either `youtube-dl` or `youtube-dlc`
installed locally.

You can run the
[bootstrap.sh](https://github.com/nbr23/youtube-dl-server/blob/master/bootstrap.sh)
to download the required front-end libraries (jquery, bootstrap).

You can run the [bootstrap.sh](https://github.com/nbr23/youtube-dl-server/blob/master/bootstrap.sh) to download the required front-end libraries (jquery, bootstrap).

```shell
python3 -u ./youtube-dl-server.py
```

To force using `youtube-dl` or `youtube-dlc`, use the variable `YOUTUBE_DL`:

```shell
YOUTUBE_DL=youtube-dlc python3 -u ./youtube-dl-server.py
```

## Usage

### Start a download remotely

Downloads can be triggered by supplying the `{{url}}` of the requested video
through the Web UI or through the REST interface via curl, etc.

#### HTML

Just navigate to `http://{{host}}:8080/` and enter the requested `{{url}}`.

#### Curl

```shell
curl -X POST --data-urlencode "url={{url}}" http://{{host}}:8080/api/downloads
```

#### Fetch

```javascript
fetch(`http://${host}:8080/api/downloads`, {
  method: "POST",
  body: new URLSearchParams({
    url: url,
    format: "bestvideo"
  }),
});
```

#### Bookmarklet

Add the following bookmarklet to your bookmark bar so you can conviently send
the current page url to your youtube-dl-server instance.

##### HTTPS

If your youtube-dl-server is served through https (behind a reverse proxy
handling https for example), you can use the following bookmarklet:

```javascript
javascript:fetch("https://${host}/api/downloads",{body:new URLSearchParams({url:window.location.href,format:"bestvideo"}),method:"POST"});
```

##### Plain text

If you are hosting it without HTTPS, the previous bookmarklet will likely be
blocked by your browser (as it will generate mixed content when used on HTTPS
sites).

Instead, you can use the following bookmarklet:

```javascript
javascript:(function(){document.body.innerHTML += '<form name="ydl_form" method="POST" action="http://${host}/api/downloads"><input name="url" type="url" value="'+window.location.href+'"/></form>';document.ydl_form.submit()})();
```

## Implementation

The server uses [`bottle`](https://github.com/bottlepy/bottle) for the web
framework and [`youtube-dl`](https://github.com/rg3/youtube-dl) /
[`youtube-dlc`](https://github.com/blackjack4494/yt-dlc) to handle the
downloading. The integration with youtube-dl makes use of their [python
api](https://github.com/rg3/youtube-dl#embedding-youtube-dl).

This docker image is based on
[`python:alpine`](https://registry.hub.docker.com/_/python/) and consequently
[`alpine:3.8`](https://hub.docker.com/_/alpine/).

[1]:youtube-dl-server.png
[2]:youtube-dl-server-logs.png
