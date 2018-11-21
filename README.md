# youtube-dl-server

## Usage

```yaml
version: '3'

services:
  ytb-dl:
    container_name: ytb-dl
    image: wiserain/youtube-dl-server:alpine
    restart: always
    network_mode: bridge
    ports:
      - ${PORT_TO_EXPOSE}:8080
    volumes:
      - ${DOWNLOAD_TO}/youtube-dl:/youtube-dl
    environment:
      - TZ=Asia/Seoul
      - YTBDL_O=%(title)s - [%(id)s].%(ext)s
      - YTBDL_F=bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]
```

## Internal youtube-dl command

bash + python mixed syntax

```bash
youtube-dl -o "/incomplete/" + os.getenv("YTBDL_O", "%(title)s.%(ext)s") \
    -f os.getenv("YTBDL_F", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]") \
    -x # only audio checked
    --exec "touch {} && mv {} /youtube-dl/" \
    --merge-output-format mp4 \
    url
```

## Environment variables

- ```YTBDL_O```: [OUTPUT TEMPLATE](https://github.com/rg3/youtube-dl#output-template)
- ```YTBDL_F```: [FORMAT SELECTION](https://github.com/rg3/youtube-dl#format-selection)
