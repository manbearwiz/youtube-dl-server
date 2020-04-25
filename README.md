# youtube-dl-server

Youtube-dl + Web UI [`youtube-dl`](https://github.com/rg3/youtube-dl).

![screenshot][1]


![screenshot][2]

## Running

This example uses the docker run command to create the container to run the app. Here we also use host networking for simplicity. Also note the `-v` argument. This directory will be used to output the resulting videos

```shell
docker run -d -p 8080:8080 --name youtube-dl -v /home/$USER/youtube-dl:/youtube-dl gallofeliz/youtube-dl-server
```

Go to http://localhost:8080 and ENJOY !

More information ? Please see original repository https://github.com/nbr23/youtube-dl-server

[1]:youtube-dl-server.png
[2]:youtube-dl-server-logs.png
