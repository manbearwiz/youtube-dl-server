from flask import Blueprint, send_from_directory, redirect, render_template


ydl = Blueprint('ydl', __name__, template_folder='static', static_folder='static', static_url_path='')


@ydl.route('/')
def youtube_dl_default():
    return render_template('index.html')


@ydl.route('/<path:path>')
def youtube_dl(path):
    return send_from_directory('static', path)
