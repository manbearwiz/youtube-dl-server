import json
import tempfile
import subprocess
from queue import Queue
from bottle import Bottle, request, static_file
from threading import Thread
from os import listdir, stat
from os.path import isfile, join

app = Bottle()
dl_path = '/youtube-dl'


@app.route('/youtube-dl')
def dl_queue_list():
    return static_file('index.html', root='./')


@app.route('/youtube-dl/static/:filename#.*#')
def server_static(filename):
    return static_file(filename, root='./static')


@app.route('/youtube-dl/completed', method='GET')
def q_completed():
    completed = [f for f in listdir(dl_path) if isfile(join(dl_path, f))]
    mtime = lambda f: stat(join(dl_path, f)).st_mtime
    completed = sorted(completed, key=mtime, reverse=True)
    return {"success": True, "files": completed}


@app.route('/youtube-dl/q', method='GET')
def q_get():
    return {"success": True, "size": json.dumps(list(dl_q.queue))}


@app.route('/youtube-dl/q', method='POST')
def q_put():
    url = request.forms.get("url")
    audio = request.forms.get("audio")
    if not url:
        return {"success": False, "error": "dl called without a url"}
    else:
        dl_q.put({"url": url, "audio": bool(audio)})
        print("Added url " + url + " to the download queue")
        return {"success": True, "url": url}


def dl_worker():
    while not done:
        item = dl_q.get()
        download(item)
        dl_q.task_done()


def download(item):
    with tempfile.TemporaryDirectory() as tmpdir:
        l_command = ["youtube-dl",
                     "-o", join(tmpdir, os.getenv("YTBDL_O", "%(title)s.%(ext)s")),
                     "-f", os.getenv("YTBDL_F", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]")]
        if item.get("audio"):
            l_command += ["-x"]
        url = item.get("url")
        print("Starting download of " + url)
        subprocess.run(l_command + ["--exec", "touch {} && " + "mv {}/* {}/".format(tmpdir, dl_path), "--merge-output-format", "mp4", url])
        print("Finished downloading " + url)


dl_q = Queue()
done = False
dl_thread = Thread(target=dl_worker)
dl_thread.start()

ydl_ver = subprocess.check_output("youtube-dl --version", shell=True).decode('utf-8').strip()
print('Youtube-dl version:', ydl_ver)
print("Started download thread")

app.run(host='0.0.0.0', port=8080, debug=True)
done = True
dl_thread.join()
