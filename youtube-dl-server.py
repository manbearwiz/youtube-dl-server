import json
import os
import subprocess
from queue import Queue
from bottle import route, run, Bottle, request, static_file
from threading import Thread

app = Bottle()

@app.route('/youtube-dl')
def dl_queue_list():
    return static_file('index.html', root='./')

@app.route('/youtube-dl/static/:filename#.*#')
def server_static(filename):
    return static_file(filename, root='./static')

@app.route('/youtube-dl/q', method='GET')
def q_size():
    return { "success" : True, "size" : json.dumps(list(dl_q.queue)) }

@app.route('/youtube-dl/q', method='POST')
def q_put():
    url = request.forms.get( "url" )
    if "" != url:
        dl_q.put( url )
        print("Added url " + url + " to the download queue")
        return { "success" : True, "url" : url }
    else:
        return { "success" : False, "error" : "dl called without a url" }

def dl_worker():
    while not done:
        item = dl_q.get()
        download(item)
        dl_q.task_done()

def download(url):
    print("Starting download of " + url)
    command = """youtube-dl -o "/youtube-dl/.incomplete/%(title)s.%(ext)s" -f bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4] --exec 'touch {} && mv {} /youtube-dl/' --merge-output-format mp4 """ + url
    subprocess.call(command, shell=True)
    print("Finished downloading " + url)

dl_q = Queue();
done = False;
dl_thread = Thread(target=dl_worker)
dl_thread.start()

print("Started download thread")

app.run(host='0.0.0.0', port=8080, debug=True)
done = True
dl_thread.join()
