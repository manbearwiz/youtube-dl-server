from bottle import route, request, Bottle
import subprocess
import threading

app = Bottle()

@app.route('/download')
def download():
    return '''
        <form action="/download" method="post">
            URL: <input name="url" type="text" />
            <input value="Submit" type="submit" />
        </form>
    '''

@app.route('/download', method='POST')
def do_download():
    url = request.forms.get('url')
    threading.Thread(target=exec_download, args=[url]).start()
    return '''
        <form action="/download" method="post">
            URL: <input name="url" type="text" />
            <input value="Submit" type="submit" />
            <p>Downloading ''' + url + '''</p>
        </form>
    '''
    
def exec_download(url):
    print(url)
    subprocess.call("youtube-dl -o %(title)s.%(ext)s -f bestvideo+bestaudio " + url)

app.run()
