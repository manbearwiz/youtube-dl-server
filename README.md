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
