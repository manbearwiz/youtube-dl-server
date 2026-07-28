![Docker Stars Shield](https://img.shields.io/docker/stars/nbr23/youtube-dl-server.svg?style=flat-square)
![Docker Pulls Shield](https://img.shields.io/docker/pulls/nbr23/youtube-dl-server.svg?style=flat-square)
[![GitHub license](https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square)](https://raw.githubusercontent.com/nbr23/youtube-dl-server/master/LICENSE)

# youtube-dl-server

Simple Web and REST interface for downloading youtube videos onto a server.
[`starlette`](https://www.starlette.io/) +
[yt-dlp](https://github.com/yt-dlp/yt-dlp) / [`youtube-dl`](https://github.com/rg3/youtube-dl)

Forked from [manbearwiz/youtube-dl-server](https://github.com/manbearwiz/youtube-dl-server).

![screenshot][1]


![screenshot][2]

## Running

For easier deployment, a docker image is available on
[dockerhub](https://hub.docker.com/r/nbr23/youtube-dl-server):

- `nbr23/youtube-dl-server:yt-dlp` or simply `nbr23/youtube-dl-server` to use `yt-dlp`
- `nbr23/youtube-dl-server:youtube-dl` to use `youtube-dl`. Note that the latest release of `youtube-dl` is pretty [outdated](https://github.com/ytdl-org/youtube-dl/releases/tag/2021.12.17).

### Docker CLI

This example uses the docker run command to create the container to run the
app. Note the `-v` argument to specify the volume and its binding on the host.
This directory will be used to output the resulting videos.

```shell
docker run -d --name youtube-dl -p 8080:8080 -v $HOME/youtube-dl:/youtube-dl nbr23/youtube-dl-server:latest
```

OR for yt-dlp:

```shell
docker run -d --name youtube-dl -p 8080:8080 -v $HOME/youtube-dl:/youtube-dl nbr23/youtube-dl-server:yt-dlp
```

### Docker Compose

This is an example service definition that could be put in `docker-compose.yml`.

```yml
  youtube-dl:
    image: "nbr23/youtube-dl-server:latest"
    volumes:
      - $HOME/youtube-dl:/youtube-dl
      - ./config.yml:/app_config/config.yml:ro # Overwrite the container's config file with your own configuration
    ports:
      - 8080:8080
    restart: always
```

## Configuration

Configuration is done through the config.yml file at the root of the project.

An alternate configuration path or file path can be forced by setting the environment
variable `YDL_CONFIG_PATH`:

```shell
export YDL_CONFIG_PATH=/var/local/youtube-dl-server/config.yml
```

In the above case, if `/var/local/youtube-dl-server/config.yml` does not exist, it will be created with the default options.

```shell
export YDL_CONFIG_PATH=/var/local/youtube-dl-server/
```

In the above case, if `/var/local/youtube-dl-server/config.yml` does not exist, it will be created with the default options as well.

### ydl_server options

| Key | Default | Description |
|-----|---------|-------------|
| `port` | `8080` | Port to listen on |
| `host` | `0.0.0.0` | IP to bind to |
| `metadata_db_path` | `/youtube-dl/.ydl-metadata.db` | Path to the SQLite job database |
| `output_playlist` | `/youtube-dl/%(playlist_title)s [%(playlist_id)s]/%(title)s.%(ext)s` | Output template for playlists and multi-URL jobs |
| `max_log_entries` | `100` | Maximum number of job history entries to keep |
| `default_format` | `video/best` | Default format pre-selected in the UI |
| `download_workers_count` | `2` | Number of parallel download worker threads |
| `forwarded_allow_ips` | `None` | Comma-separated list of IPs to trust proxy headers from (passed to uvicorn) |
| `proxy_headers` | `True` | Trust `X-Forwarded-Proto`, `X-Forwarded-For`, `X-Forwarded-Port` headers (passed to uvicorn) |
| `debug` | `False` | Enable debug mode |

Minimum required configuration:

```yaml
ydl_server:
  port: 8080
  host: 0.0.0.0
  metadata_db_path: '/youtube-dl/.ydl-metadata.db'

ydl_options:
  output: '/youtube-dl/%(title)s [%(id)s].%(ext)s'
  cache-dir: '/youtube-dl/.cache'
```

### ydl_options

Additional yt-dlp/youtube-dl parameters can be set in the `ydl_options` section. Add
parameters by removing the leading `--` from the flag name.

For example, to write subtitles in spanish, the yt-dlp command would be:

`yt-dlp --write-sub --sub-lang es URL`

Which translates to:

```yaml
ydl_options:
  output: '/youtube-dl/%(title)s [%(id)s].%(ext)s'
  cache-dir: '/youtube-dl/.cache'
  write-sub: True
  sub-lang: es
```

The download directory listed in the Finished tab is derived from the static part of
`output`, before the first template variable. If `output` is relative, it is resolved
against `paths` (yt-dlp's `--paths`, `home:` prefix supported):

```yaml
ydl_options:
  paths: '/youtube-dl'
  output: '%(title)s [%(id)s].%(ext)s'
```

`output` must resolve to a directory other than the filesystem root, otherwise the server
refuses to start.

### Profiles

Profiles are named configuration sets selectable in the UI. Each profile can
override any `ydl_options`.

```yaml
profiles:
  podcast:
      name: 'Audio Podcasts'
      ydl_options:
        output: '/youtube-dl/Podcast/%(title)s [%(id)s].%(ext)s'
        format: bestaudio/best
        write-thumbnail: True
        embed-thumbnail: True
        add-metadata: True
        audio-quality: 0
        extract-audio: True
        audio-format: mp3
  philosophy_lectures:
      name: 'Philosophy Lectures'
      ydl_options:
        output: '/youtube-dl/Lectures/Philosophy/%(title)s [%(id)s].%(ext)s'
        write-thumbnail: True
        embed-thumbnail: True
        add-metadata: True
        verbose: True
```

![screenshot][3]

### Option groups (aliases)

Aliases are named `ydl_options` sets that can be shared between profiles, avoiding
duplication. A profile pulls them in with `use:`, and they can also be ticked
individually in the Advanced Options section of the download form.

```yaml
aliases:
  mp3:
      name: 'MP3 audio'      # optional label shown in the UI, defaults to the key
      ydl_options:
        format: bestaudio/best
        extract-audio: True
        audio-format: mp3
  thumbnails:
      name: 'Thumbnails'
      ydl_options:
        write-thumbnail: True
        embed-thumbnail: True
  podcast_base:
      ui: False              # building block: usable with `use:`, hidden from the UI
      use: [mp3, thumbnails]
      ydl_options:
        add-metadata: True

profiles:
  podcast:
      name: 'Audio Podcasts'
      use: [podcast_base]
      ydl_options:
        output: '/youtube-dl/Podcast/%(title)s [%(id)s].%(ext)s'
```

Aliases may reference other aliases through their own `use:` list. Options are merged
in this order, the last one winning: `ydl_options`, then the profile (its aliases in
listed order, then its own `ydl_options`), then the aliases selected in the form.
Unknown aliases and recursive `use:` chains are rejected when the configuration is
loaded, at server startup.

## Python

Requires Python ^3.8.

Install dependencies:

```shell
pip install -r requirements.txt
```

Build the frontend:

```shell
cd front && npm install && npm run build
```

Run the server:

```shell
python3 -u ./youtube-dl-server.py
```

To force a specific yt-dlp/youtube-dl fork, set the `YOUTUBE_DL` environment variable:

```shell
YOUTUBE_DL=yt-dlp python3 -u ./youtube-dl-server.py
```

The following environment variables are used for version display in the UI:

| Variable | Description |
|----------|-------------|
| `YOUTUBE_DL` | The yt-dlp/youtube-dl module to use (`yt-dlp`, `youtube-dl`) |
| `YDLS_VERSION` | Version string shown in the server info endpoint |
| `YDLS_RELEASE_DATE` | Release date string shown in the server info endpoint |

## Usage

### Web UI

Navigate to `http://{{host}}:8080/` and enter the URL to download.

### REST API

#### Queue a download

```shell
curl -X POST \
  -H 'Content-Type: application/json' \
  --data-raw '{"url": "{{URL}}", "format": "video/best"}' \
  http://{{host}}:8080/api/downloads
```

Accepted body fields:

| Field | Type | Description |
|-------|------|-------------|
| `url` | string | Single URL to download |
| `urls` | array | Multiple URLs to download as one job |
| `format` | string | Format string (see formats below) |
| `profile` | string | Profile name from config |
| `aliases` | array | Alias names from config to apply on top of the profile |
| `audio_format` | string | Audio format (e.g. `mp3`, `aac`) |
| `force_generic_extractor` | bool | Force use of the generic extractor |
| `extra_params` | object | Extra parameters; `title` key overrides the output filename |

Available format values:

| Value | Description |
|-------|-------------|
| `video/best` | Best video+audio (default) |
| `video/bestvideo` | Best video quality |
| `video/mp4` | MP4 |
| `video/webm` | WebM |
| `video/mkv` | Matroska |
| `video/avi` | AVI |
| `video/flv` | Flash Video |
| `video/ogg` | Ogg |
| `bestaudio/best` | Best audio |
| `audio/mp3` | MP3 |
| `audio/aac` | AAC |
| `audio/flac` | FLAC |
| `audio/m4a` | M4A |
| `audio/opus` | Opus |
| `audio/vorbis` | Vorbis |
| `audio/wav` | WAV |

#### List jobs

```shell
curl http://{{host}}:8080/api/downloads
```

Query parameters:

| Parameter | Description |
|-----------|-------------|
| `status` | Filter by status: `Running`, `Completed`, `Failed`, `Pending`, `Aborted` |
| `show_logs` | Include log output in response, `1` (default) or `0` |

#### Queue statistics

```shell
curl http://{{host}}:8080/api/downloads/stats
```

#### Clean old job entries

Removes completed and failed entries beyond `max_log_entries`:

```shell
curl -X POST http://{{host}}:8080/api/downloads/clean
```

#### Purge all job history

```shell
curl -X DELETE http://{{host}}:8080/api/downloads
```

#### Fetch metadata without downloading

```shell
curl -X POST \
  -H 'Content-Type: application/json' \
  --data-raw '{"url": "{{URL}}"}' \
  http://{{host}}:8080/api/metadata
```

#### Stop a job

```shell
curl -X POST http://{{host}}:8080/api/jobs/{{job_id}}/stop
```

#### Retry a job

```shell
curl -X POST http://{{host}}:8080/api/jobs/{{job_id}}/retry
```

#### Delete a job entry

```shell
curl -X DELETE http://{{host}}:8080/api/jobs/{{job_id}}
```

#### List downloaded files

```shell
curl http://{{host}}:8080/api/finished
```

#### Delete a downloaded file

```shell
curl -X DELETE http://{{host}}:8080/api/finished/{{filename}}
```

#### Server info

```shell
curl http://{{host}}:8080/api/info
```

#### Available formats

```shell
curl http://{{host}}:8080/api/formats
```

#### Supported extractors

```shell
curl http://{{host}}:8080/api/extractors
```

### Bookmarklet

Add the following bookmarklet to your bookmark bar to send the current page URL
to your youtube-dl-server instance.

#### HTTPS

If your youtube-dl-server is served through HTTPS (behind a reverse proxy
handling HTTPS for example), you can use the following bookmarklet:

```javascript
javascript:fetch("https://${host}/api/downloads",{body:JSON.stringify({url:window.location.href,format:"video/best"}),method:"POST",headers:{'Content-Type':'application/json'}});
```

#### Plain HTTP

If you are hosting it without HTTPS, the previous bookmarklet will likely be
blocked by your browser (mixed content when used on HTTPS sites).

Instead, you can use the following bookmarklet:

```javascript
javascript:(function(){document.body.innerHTML += '<form name="ydl_form" method="POST" action="http://${host}/api/downloads"><input name="url" type="url" value="'+window.location.href+'"/></form>';document.ydl_form.submit()})();
```

## Notes

### Extra format support

`ffmpeg` is required for format conversion and audio extraction in some
scenarios.

## Additional references

* [ansible-role-youtubedl-server](https://github.com/nbr23/ansible-role-youtubedl-server)
* [ytdl-k8s](https://github.com/droopy4096/ytdl-k8s) - `youtube-dl-server` Helm chart (uses `youtube-dl-server` image for kubernetes deployment)
* [starlette](https://www.starlette.io/)
* [youtube-dl](https://github.com/rg3/youtube-dl)
* [yt-dlp](https://github.com/yt-dlp/yt-dlp)

[1]:youtube-dl-server.png
[2]:youtube-dl-server-logs.png
[3]:youtube-dl-server-profiles.png
