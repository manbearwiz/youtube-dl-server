from flask import Flask
from flask_restful import Api
from flask_basicauth import BasicAuth

import os
import logging

from blueprints.ydl import ydl
from resources.ydl import YoutubeDLAPI

http_root = os.getenv('YTBDL_SERVER_ROOT', '/youtube-dl')
if not http_root.startswith('/'):
    http_root = '/' + http_root

app = Flask(__name__)

username = os.getenv('YTBDL_SERVER_USER', '')
password = os.getenv('YTBDL_SERVER_PASS', '')
if username and password:
    app.config['BASIC_AUTH_USERNAME'] = username
    app.config['BASIC_AUTH_PASSWORD'] = password
    app.config['BASIC_AUTH_FORCE'] = True
    basic_auth = BasicAuth(app)

app.register_blueprint(ydl, url_prefix=http_root)

api = Api(app)
api.add_resource(YoutubeDLAPI, http_root  + ('q' if http_root.endswith('/') else '/q'))


if __name__ == '__main__':
    # disable verbose log from werkzeug
    log = logging.getLogger('werkzeug')
    log.disabled = True

    app.run(
        host=os.getenv('YTBDL_SERVER_HOST', '0.0.0.0'),
        port=os.getenv('YTBDL_SERVER_PORT', 8080),
        debug=False,
    )
