from flask import Flask
from flask_restful import Api

import os
import logging

from blueprints.ydl import ydl
from resources.ydl import YoutubeDLAPI

app = Flask(__name__)
app.register_blueprint(ydl, url_prefix='/youtube-dl')

api = Api(app)
api.add_resource(YoutubeDLAPI, '/youtube-dl/q')


if __name__ == '__main__':
    # disable verbose log from werkzeug
    log = logging.getLogger('werkzeug')
    log.disabled = True

    app.run(
        host=os.getenv('YTBDL_SERVER_HOST', '0.0.0.0'),
        port=os.getenv('YTBDL_SERVER_PORT', 8080),
        debug=False,
    )
