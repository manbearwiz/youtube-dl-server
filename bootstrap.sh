#! /usr/bin/env sh

BOOTSTRAP_VERSION=5.1.3

# Download required web frontend libraries
wget -q https://code.jquery.com/jquery-3.6.0.min.js -O ydl_server/static/js/jquery.min.js
wget -q https://github.com/twbs/bootstrap/releases/download/v$BOOTSTRAP_VERSION/bootstrap-$BOOTSTRAP_VERSION-dist.zip -O bootstrap.zip
unzip -jo bootstrap.zip *.css *.css.map -d ydl_server/static/css/
unzip -jo bootstrap.zip *.js *.js.map -d ydl_server/static/js/
rm -f bootstrap.zip
