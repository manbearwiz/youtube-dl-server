import json
import os
import subprocess
from queue import Queue
from bottle import route, run, Bottle, request
from threading import Thread

app = Bottle()

@app.route('/youtube-dl')
def dl_queue_list():
    print("bar")
    return '''
        <form action="/youtube-dl/q" method="POST">
            URL: <input name="url" type="text" />
            <input value="Submit" type="submit" />
        </form>
    '''

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
    command = """youtube-dl -o "/youtube-dl/.incomplete/%(title)s.%(ext)s" --restrict-filenames -f best[acodec=none][ext=mp4]+best[vcodec=none][ext=m4a] --exec 'mv {} /youtube-dl/' --merge-output-format mp4 """ + url
    print("Finished downloading " + url)
    subprocess.call(command, shell=True)
    
dl_q = Queue();
done = False;
dl_thread = Thread(target=dl_worker)
dl_thread.start()

print("Started download thread")

app.run(host='0.0.0.0', port=8080, debug=True)
done = True
dl_thread.join()
