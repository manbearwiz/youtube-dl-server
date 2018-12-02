import json
import os
import subprocess
from queue import Queue
from bottle import route, run, Bottle, request, static_file
from threading import Thread

sub_lang = os.environ.get("SUB_LANGS","all")
archive_file = os.environ.get("ARCHIVE_FILE","/youtube-dl/yt-dl_archive.txt")

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
    archive = request.forms.get("archive")
    subfolder = request.forms.get("playlistfolder")
    subs = request.forms.get( "subs" )
    audio_only =  request.forms.get( "audio_only" )

    settings = {"url" : url ,"subs":subs,"archive":archive,"subfolder":subfolder,"audio_only":audio_only}
    if "" != url:
        dl_q.put( settings )
        print("Added url " + url + " to the download queue")
        settings.update({"success" : True})
        return settings
    else:
        return { "success" : False, "error" : "dl called without a url" }

def dl_worker():
    while not done:
        item = dl_q.get()
        download(item)
        dl_q.task_done()

def download(item):
    url = item["url"]
    print(item)
    path = "/youtube-dl/%(playlist_title)s/%(title)s.%(ext)s" if item["subfolder"] == "True" else "/youtube-dl/%(title)s.%(ext)s"
    runcall = ["youtube-dl","-q", "-o", path, "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]", "--merge-output-format", "mp4", url]

    if item["archive"] == "True":
        runcall.extend(["--download-archive", archive_file])

    if item["audio_only"] == "True":
        runcall.append("--extract-audio")

    if not item["subs"] == "none":
        runcall.append("--write-sub")
        if sub_lang == "all" or item["subs"] == "all":
            runcall.append("--all-subs")
        else:
            runcall.extend(["--sub-lang",sub_lang])
    if item["subs"] == "embed":
        runcall.append("--embed-subs")


    print("Starting download of " + url)
    subprocess.run(runcall)
    print("Finished downloading " + url)


print("Sub langs:",sub_lang)

dl_q = Queue();
done = False;
dl_thread = Thread(target=dl_worker)
dl_thread.start()

print("Started download thread")

app.run(host='0.0.0.0', port=8080, debug=True)
done = True
dl_thread.join()
