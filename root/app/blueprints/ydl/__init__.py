from flask import Blueprint, send_from_directory, redirect


ydl = Blueprint('ydl', __name__, static_folder='static', static_url_path='')


@ydl.route('/')
def youtube_dl_default():
    return redirect('/youtube-dl/index.html')


@ydl.route('/<path:path>')
def youtube_dl(path):
    return send_from_directory('static', path)
