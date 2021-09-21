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
import requests
import os
from dotenv import load_dotenv

load_dotenv()

app = Bottle()


app_defaults = {
    'YDL_FORMAT': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]',
    'YDL_EXTRACT_AUDIO_FORMAT': None,
    'YDL_EXTRACT_AUDIO_QUALITY': '192',
    'YDL_RECODE_VIDEO_FORMAT': None,
    'YDL_OUTPUT_TEMPLATE': '%(title)s [%(id)s]',
    'YDL_ARCHIVE_FILE': None,
    'YDL_SERVER_HOST': '0.0.0.0',
    'YDL_SERVER_PORT': 8080,
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
    options = {
        'format': request.forms.get("format"),
        'filename': request.forms.get("filename"),
        'collectionId': request.forms.get("collectionId"),
        'base_url': request.forms.get("base_url")
    }

    if not url:
        return {"success": False, "error": "/q called without a 'url' query param"}

    dl_q.put((url, options))
    print("Added url " + url + " to the download queue")
    return {"success": True, "url": url, "options": options}

@app.route("/youtube-dl/update", method="GET")
def update():
    command = ["pip", "install", "--upgrade", "youtube-dl"]
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    output, error = proc.communicate()
    return {
        "output": output.decode('ascii'),
        "error":  error.decode('ascii')
    }

def login(request_options):
    user_login = requests.post(request_options['base_url'] + '/auth/local', {
        'identifier': os.getenv('IDENTIFIER'),
        'password': os.getenv('PASSWORD'),
    })

    loging_content = json.loads(user_login.content.decode('utf-8'))
    return loging_content['jwt']

def upload_video(jwt, request_options):
    upload_url = request_options['base_url'] + '/upload'
    path = os.getenv('DOWNLOAD_PATH') + request_options['filename'] + '.mp4'
    with open(path, 'rb') as f:
        response = requests.post(
            upload_url,
            files={'files': (request_options['filename'] + '.mp4', f, 'video')},
            headers={'Authorization': 'Bearer ' + jwt}
        )

    return response

def get_video(request_options):
    video_url = request_options['base_url'] +'/videos/' + request_options['collectionId']
    return requests.get(video_url)

def sanitize_video(upload_video_response, video):
    video_sanitized = json.loads(video.content.decode('utf-8'))
    upload_video_response_content = json.loads(upload_video_response.content.decode('utf-8'))

    video_sanitized['partner'] = video_sanitized['partner']['id']
    video_sanitized['language'] = video_sanitized['language']['id']
    video_sanitized['category'] = video_sanitized['category']['id']
    video_sanitized['source'] = upload_video_response_content[0]['id']

    return video_sanitized

def update_video_in_strapi(jwt, upload_video_response, video, request_options):
    video_sanitized = sanitize_video(upload_video_response, video)
    update_video_url = request_options['base_url'] +'/videos/' + request_options['collectionId']
    headers={'Authorization': 'Bearer ' + jwt}
    requests.put(update_video_url, data=video_sanitized, headers=headers)

def dl_worker():
    while not done:
        url, options = dl_q.get()
        download(url, options)
        jwt = login(options)
        upload_video_response = upload_video(jwt, options)
        if (upload_video_response.status_code == 200):
            video = get_video(options)
            update_video_in_strapi(jwt, upload_video_response, video, options)
        dl_q.task_done()


def get_ydl_options(request_options):
    request_vars = {
        'YDL_EXTRACT_AUDIO_FORMAT': None,
        'YDL_RECODE_VIDEO_FORMAT': None,
    }

    requested_format = request_options.get('format', 'bestvideo')

    if requested_format in ['aac', 'flac', 'mp3', 'm4a', 'opus', 'vorbis', 'wav']:
        request_vars['YDL_EXTRACT_AUDIO_FORMAT'] = requested_format
    elif requested_format == 'bestaudio':
        request_vars['YDL_EXTRACT_AUDIO_FORMAT'] = 'best'
    elif requested_format in ['mp4', 'flv', 'webm', 'ogg', 'mkv', 'avi']:
        request_vars['YDL_RECODE_VIDEO_FORMAT'] = requested_format

    ydl_vars = ChainMap(request_vars, os.environ, app_defaults)
    requested_outputname = request_options.get('filename', ydl_vars['YDL_OUTPUT_TEMPLATE'])

    postprocessors = []

    if(ydl_vars['YDL_EXTRACT_AUDIO_FORMAT']):
        postprocessors.append({
            'key': 'FFmpegExtractAudio',
            'preferredcodec': ydl_vars['YDL_EXTRACT_AUDIO_FORMAT'],
            'preferredquality': ydl_vars['YDL_EXTRACT_AUDIO_QUALITY'],
        })

    if(ydl_vars['YDL_RECODE_VIDEO_FORMAT']):
        postprocessors.append({
            'key': 'FFmpegVideoConvertor',
            'preferedformat': ydl_vars['YDL_RECODE_VIDEO_FORMAT'],
        })

    return {
        'format': ydl_vars['YDL_FORMAT'],
        'postprocessors': postprocessors,
        'outtmpl': '/youtube-dl/' + requested_outputname + '.%(ext)s',
        'download_archive': ydl_vars['YDL_ARCHIVE_FILE']
    }

def download(url, request_options):
    with youtube_dl.YoutubeDL(get_ydl_options(request_options)) as ydl:
        try:
            ydl.download([url])
        except:
            print("Error for URL: ",url)

dl_q = Queue()
done = False
dl_thread = Thread(target=dl_worker)
dl_thread.start()

print("Updating youtube-dl to the newest version")
updateResult = update()
print(updateResult["output"])
print(updateResult["error"])

print("Started download thread")

app_vars = ChainMap(os.environ, app_defaults)

app.run(host=app_vars['YDL_SERVER_HOST'], port=app_vars['YDL_SERVER_PORT'], debug=True)
done = True
dl_thread.join()
