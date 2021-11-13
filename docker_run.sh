#! /usr/bin/env sh

pip install --no-cache-dir -t $YDL_PYTHONPATH --upgrade $YOUTUBE_DL
PYTHONPATH="${PYTHONPATH}:${YDL_PYTHONPATH}" python -u ./youtube-dl-server.py