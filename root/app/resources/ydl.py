# coding: utf-8
from __future__ import unicode_literals
from flask_restful import Resource, fields, marshal_with, reqparse, inputs

import os
import shutil
import tempfile
import youtube_dl

from pathlib import Path
from os import listdir, stat
from os.path import isfile, join, relpath, dirname
from queue import Queue
from threading import Thread


# input
parser = reqparse.RequestParser()
parser.add_argument('url', type=str, required=True, help='url to be downloaded')
parser.add_argument('audio', type=inputs.boolean, default=False, help='audio only')
parser.add_argument(
    'acodec', choices=('aac', 'flac', 'mp3', 'm4a', 'opus', 'vorbis', 'wav'),
    default='mp3', help='preferred audio codec when extracting'
)

# output
output_fields = {
    'success': fields.Boolean,
    'queue': fields.List(fields.String),
    'completed': fields.List(fields.String),
}


class YoutubeDLAPI(Resource):
    @marshal_with(output_fields)
    def get(self):
        completed = [f for f in listdir(dl_path) if isfile(join(dl_path, f))]
        mtime = lambda f: stat(join(dl_path, f)).st_mtime
        completed = sorted(completed, key=mtime, reverse=True)
        queue = [q['url'] for q in list(dl_q.queue)]
        return {
            'success': True,
            'queue': queue,
            'completed': completed,
        }

    def post(self):
        args = parser.parse_args()
        dl_q.put(args)
        return self.get()


def dl_worker():
    while not done:
        args = dl_q.get()
        download(args)
        dl_q.task_done()


def parse_request_args(args):
    # format
    if args.get('audio', False):
        ydl_format = 'bestaudio/best'
    else:
        ydl_format = os.getenv('YTBDL_F', 'bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best')

    # postprocessor
    postprocessor = []
    if args.get('audio', False):
        postprocessor.append({
            'key': 'FFmpegExtractAudio',
            'preferredcodec': args['acodec'],
        })

    # output template
    outtmpl = os.getenv('YTBDL_O', '%(uploader)s/%(title)s.%(ext)s')

    return args['url'], {
        'format': ydl_format,
        'postprocessors': postprocessor,
        'outtmpl': outtmpl,
    }


def download(args):
    url, ydl_options = parse_request_args(args)
    with tempfile.TemporaryDirectory() as tmpdir:
        ydl_options.update({'outtmpl': join(tmpdir, ydl_options['outtmpl'])})
        with youtube_dl.YoutubeDL(ydl_options) as ytb_dl:
            ytb_dl.download([url])
            for file in Path(tmpdir).glob('**/*.*'):
                subdir = join(dl_path, dirname(relpath(file, tmpdir)))
                os.makedirs(subdir, exist_ok=True)
                shutil.move(file, join(dl_path, relpath(file, tmpdir)))


dl_path = '/youtube-dl'
dl_q = Queue()
done = False

dl_thread = Thread(target=dl_worker)
dl_thread.start()
