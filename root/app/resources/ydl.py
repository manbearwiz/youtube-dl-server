# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from flask_restful import Resource, fields, marshal, reqparse, inputs
from auth import basic_auth

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
fields_on_success = {
    'success': fields.Boolean,
    'queue': fields.List(fields.String),
    'completed': fields.List(fields.String),
    'incomplete': fields.List(fields.String),
}
fields_on_failed = {
    'success': fields.Boolean,
    'message': fields.String,
}


class YoutubeDLAPI(Resource):
    decorators = [basic_auth.login_required]

    def get(self):
        try:
            all_files = [str(f) for f in Path(dl_path).glob('**/*') if isfile(f)]
            completed = [f for f in all_files if 'incomplete_' not in f]
            incomplete = [f for f in all_files if 'incomplete_' in f]
            mtime = lambda f: stat(f).st_mtime
            return marshal({
                'success': True,
                'queue': [q['url'] for q in list(dl_q.queue)],
                'completed': [relpath(f, dl_path) for f in sorted(completed, key=mtime, reverse=True)],
                'incomplete': [relpath(f, dl_path) for f in sorted(incomplete, key=mtime, reverse=True)],
            }, fields_on_success), 200
        except Exception as e:
            return marshal({
                'success': False,
                'message': str(e),
            }, fields_on_failed), 200

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
        'ignoreerrors': os.getenv('YTBDL_I','false').lower() == 'true',
    }


def download(args):
    tmpdir = tempfile.mkdtemp(prefix='incomplete_', dir=dl_path)
    url, ydl_options = parse_request_args(args)
    ydl_options.update({'outtmpl': join(tmpdir, ydl_options['outtmpl'])})
    with youtube_dl.YoutubeDL(ydl_options) as ytb_dl:
        try:
            ytb_dl.download([url])
            for f in Path(tmpdir).glob('**/*'):
                subdir = join(dl_path, dirname(relpath(f, tmpdir)))
                os.makedirs(subdir, exist_ok=True)
                shutil.move(f, join(dl_path, relpath(f, tmpdir)))
        except Exception as e:
            print(e)
            print('Consider setting "YTBDL_I=true" to ignore youtube-dl errors')

    print('Cleaning incomplete directory {}'.format(tmpdir))
    try:
        os.rmdir(tmpdir)
    except Exception as e:
        print('Failed to delete incomplete directory: {}'.format(e))


dl_path = '/youtube-dl'
dl_q = Queue()
done = False

dl_thread = Thread(target=dl_worker)
dl_thread.start()
