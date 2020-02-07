from flask import Blueprint, send_from_directory, redirect, render_template
from auth import basic_auth

ydl = Blueprint('ydl', __name__, template_folder='static', static_folder='static', static_url_path='')


@ydl.route('/')
@basic_auth.login_required
def youtube_dl_default():
    return render_template('index.html')


@ydl.route('/<path:path>')
@basic_auth.login_required
def youtube_dl(path):
    return send_from_directory('static', path)
