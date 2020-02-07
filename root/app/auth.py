import os
from flask_httpauth import HTTPBasicAuth

basic_auth = HTTPBasicAuth()

AUTH_DATA = {}

authuser = os.getenv('YTBDL_SERVER_USER', '')
authpass = os.getenv('YTBDL_SERVER_PASS', '')
if authuser and authpass:
    AUTH_DATA.update({authuser: authpass})


@basic_auth.verify_password
def verify(username, password):
    if not bool(AUTH_DATA):
        return True
    if not (username and password):
        return False
    return AUTH_DATA.get(username) == password
