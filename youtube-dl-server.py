from __future__ import unicode_literals
import json
import os
import subprocess
from queue import Queue
from bottle import route, run, Bottle, request, static_file
from threading import Thread
import youtube_dl
from pathlib import Path
from collections import ChainMap

app = Bottle()


app_defaults = {
    'YDL_FORMAT': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]',
    'YDL_EXTRACT_AUDIO': False,
    'YDL_OUTPUT_TEMPLATE': '/youtube-dl/%(title)s [%(id)s].%(ext)s',
    'YDL_ARCHIVE_FILE': None
}


@app.route('/youtube-dl')
def dl_queue_list():
    return static_file('index.html', root='./')


@app.route('/youtube-dl/static/:filename#.*#')
def server_static(filename):
    return static_file(filename, root='./static')


@app.route('/youtube-dl/q', method='GET')
def q_size():
    return {"success": True, "size": json.dumps(list(dl_q.queue))}


@app.route('/youtube-dl/q', method='POST')
def q_put():
    url = request.forms.get("url")
    if "" != url:
        dl_q.put(url)
        print("Added url " + url + " to the download queue")
        return {"success": True, "url": url}
    else:
        return {"success": False, "error": "dl called without a url"}


def dl_worker():
    while not done:
        item = dl_q.get()
        download(item)
        dl_q.task_done()


def get_ydl_options():
    ydl_vars = ChainMap(os.environ, app_defaults)

    return {
        'format': ydl_vars['YDL_FORMAT'],
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }] if ydl_vars['YDL_EXTRACT_AUDIO'] else [],
        'outtmpl': ydl_vars['YDL_OUTPUT_TEMPLATE'],
        'download_archive': ydl_vars['YDL_ARCHIVE_FILE']
    }

def download(url):
    with youtube_dl.YoutubeDL(get_ydl_options()) as ydl:
        ydl.download([url])


dl_q = Queue()
done = False
dl_thread = Thread(target=dl_worker)
dl_thread.start()

print("Started download thread")

app.run(host='0.0.0.0', port=8080, debug=True)
done = True
dl_thread.join()
