import os
import runpy
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from yt_dlp import YoutubeDL


def load_options(proxy):
    with patch.dict(os.environ):
        if proxy is None:
            os.environ.pop("YDL_PROXY", None)
        else:
            os.environ["YDL_PROXY"] = proxy
        app = runpy.run_path(str(Path(__file__).parents[1] / "youtube-dl-server.py"))
        return app["get_ydl_options"]({})


class ProxyTests(unittest.TestCase):
    def test_unset_preserves_proxy_discovery(self):
        self.assertIsNone(load_options(None)["proxy"])

    def test_blank_matches_unset(self):
        self.assertEqual(load_options(""), load_options(None))

    def test_proxy_url_passed_unchanged(self):
        proxy = "http://192.168.1.10:8118"
        self.assertEqual(load_options(proxy)["proxy"], proxy)

    def test_urlopen_uses_configured_proxy(self):
        requests = []

        class ProxyHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                requests.append(self.path)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"203.0.113.1")

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), ProxyHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            options = load_options(f"http://127.0.0.1:{server.server_port}")
            with YoutubeDL(options) as ydl:
                with ydl.urlopen("http://proxy-test.invalid/ip") as response:
                    self.assertEqual(response.read(), b"203.0.113.1")
            self.assertEqual(requests, ["http://proxy-test.invalid/ip"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
