youtube-dl-server
=================

Web / REST interface for downloading youtube videos onto a server. 

How to use this image
---------------------

###Run on host networking

This example uses host networking for simplicitly. Also note the `-v` argument. This directory will be used to output the resulting videos

```
sudo docker run -d --net="host" --name youtube-dl -v /home/kevin/youtube-dl:/youtube-dl kmb32123/youtube-dl-server
```

Implementation
--------------

This image is based on [`python:3-onbuild`](https://registry.hub.docker.com/_/python/) and consequently [`debian:jessie`](https://registry.hub.docker.com/u/library/debian/).
