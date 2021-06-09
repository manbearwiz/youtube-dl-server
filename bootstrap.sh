#! /usr/bin/env sh

# Download required web frontend libraries
wget -q https://code.jquery.com/jquery-3.4.1.min.js -O ydl_server/static/js/jquery.min.js
wget -q https://github.com/twbs/bootstrap/releases/download/v5.0.1/bootstrap-5.0.1-dist.zip -O bootstrap.zip
unzip -jo bootstrap.zip *.css *.css.map -d ydl_server/static/css/
unzip -jo bootstrap.zip *.js *.js.map -d ydl_server/static/js/
rm -f bootstrap.zip
