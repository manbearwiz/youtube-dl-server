import json
import os
import subprocess
from queue import Queue
from bottle import route, run, Bottle, request, static_file, template
from threading import Thread
from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlunparse

BASE_URL = os.getenv('BASE_URL', '/youtube-dl')
DEST_DIR = os.getenv('DEST_DIR', '/youtube-dl')

processed = set()
app = Bottle()

@app.route('/youtube-dl')
def dl_queue_list():
    return template('index', BASE_URL=BASE_URL,
                    ROBOTS_NOINDEX=os.getenv('ROBOTS_NOINDEX', 'False').lower() in ('1', 'true'))

@app.route('/youtube-dl/static/:filename#.*#')
def server_static(filename):
    return static_file(filename, root='./static')

@app.route('/youtube-dl/q', method='GET')
def q_get():
    return { 'pending_qsize': dl_q.qsize(), 'processed': list(processed) }

@app.route('/youtube-dl/q_pop_processed', method='GET')
def q_pop_processed():
    url = request.query.get("url")
    if url in processed:
        processed.remove(url)
        return { 'complete': True }
    return { 'complete': False }

@app.route('/youtube-dl/q', method='POST')
def q_put():
    url = request.forms.get("url")
    audio_only = request.forms.get("audio-only") == 'on'
    if not url:
        return { "success" : False, "error" : "/q called without a 'url' query param" }
    parsed_url = urlparse(url)
    qparams = dict(parse_qsl(parsed_url.query))
    if 'list' in qparams:
        # This means that the video is part of a playlist:
        # we need to remove the 'list' query param,
        # otherwise youtube-dl will download the entire playlist.
        del qparams['list']
        url = urlunparse(parsed_url._replace(query=urlencode(qparams)))
    dl_q.put((url, audio_only))
    print("Added url " + url + " to the download queue")
    if audio_only and DEST_DIR.endswith('/static') and 'v' in qparams:
        return template('processing', url=quote(url, safe=''), generated_file='{}.mp3'.format(qparams['v']))
    return { "success" : True, "url" : url }

def dl_worker():
    while not done:
        url, audio_only = dl_q.get()
        download(url, audio_only)
        dl_q.task_done()

def download(url, audio_only):
    print("Starting download of " + url)
    if audio_only:
        subprocess.run(["youtube-dl", "-o", DEST_DIR + "/%(id)s.%(ext)s", "--extract-audio", "--audio-format", "mp3", "--no-mtime", url])
    else:
        subprocess.run(["youtube-dl", "-o", "/youtube-dl/.incomplete/%(title)s.%(ext)s", "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]", "--exec", "touch {} && mv {} /youtube-dl/", "--merge-output-format", "mp4", url])
    processed.add(url)
    print("Finished downloading " + url)

dl_q = Queue()
done = False
dl_thread = Thread(target=dl_worker)
dl_thread.start()

print("Started download thread")

app.run(host=os.getenv('HOST', '0.0.0.0'),
        port=int(os.getenv('PORT', '8080')),
        debug=os.getenv('DEBUG', 'True').lower() in ('true', '1'))
done = True
dl_thread.join()
