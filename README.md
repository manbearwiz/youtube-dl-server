# youtube-dl-server

This docker image is with

- lsiobase/alpine:latest
    - permission handling with ```PUID``` and ```PGID```
    - running an app with non-root user
- Flask web framework
- Simple REST API for youtube-dl to download requested url
- Auto-update youtube-dl (restart your container to update)

## Usage

```yaml
version: '3'

services:
  ytb-dl:
    container_name: ytb-dl
    image: wiserain/youtube-dl-server:latest
    restart: always
    network_mode: bridge
    ports:
      - ${PORT_TO_EXPOSE}:8080
    volumes:
      - ${DIR_TO_DOWNLOAD}:/youtube-dl
    environment:
      - PUID=${PUID}
      - PGID=${PGID}
      - TZ=Asia/Seoul
      - YTBDL_O=%(title)s - [%(id)s].%(ext)s
      - YTBDL_F=bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]
```

Create and run your container as above, and then access to ```http://${DOCKER_HOST_IP}:${PORT_TO_EXPOSE}/youtube-dl```

## REST API

- target url: ```/youtube-dl/q```
- method: ```POST```
- available parameters: ```url```, ```audio```, and ```acodec```

## Environment variables

| ENV  | Description  | Default  |
|---|---|---|
| ```PUID``` / ```PGID```  | uid and gid for running an app  | ```911``` / ```911```  |
| ```YTBDL_VER```  | either of ```latest``` or youtube-dl version, e.g. ```2019.09.28```  | ```latest```  |
| ```YTBDL_O```  | [OUTPUT TEMPLATE](https://github.com/rg3/youtube-dl#output-template)  | ```%(uploader)s/%(title)s.%(ext)s```  |
| ```YTBDL_F```  | [FORMAT SELECTION](https://github.com/rg3/youtube-dl#format-selection)  | ```bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best```  |
| ```YTBDL_I```  | set ```true``` to ignore youtube-dl errors, the same as passing ```--ignore-errors``` in commandline  |
| ```YTBDL_SERVER_HOST```  |   | ```0.0.0.0```
| ```YTBDL_SERVER_PORT```  |   | ```8080```
| ```YTBDL_SERVER_ROOT```  | set ```/``` if you want to access without a location path   | ```/youtube-dl```
| ```YTBDL_SERVER_USER``` / ```YTBDL_SERVER_PASS```  | requires both to activate basicauth   |

## TODO

- ~~Support http basic auth~~
