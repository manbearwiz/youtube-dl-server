"""Behavior tests.

Tests marked with a bug-pin comment asserted broken behavior in the baseline
suite (PR #378). This PR flips each pin; the flipped assertion is the
reviewable signal that the behavior change is intentional.
"""

import importlib

from yt_dlp import version

app = importlib.import_module("youtube-dl-server")


def test_root_redirects(client):
    # Pins current behavior: Starlette 1.0 RedirectResponse defaults to 307.
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == "/youtube-dl"


def test_queue_list_renders(client):
    r = client.get("/youtube-dl")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    # Bug pin flipped (was EMPTY in the baseline): TemplateResponse now uses
    # Starlette's (request, name, context) signature.
    assert version.__version__ in r.text


def test_q_json_success_pins_current_shape(client, calls):
    r = client.post("/youtube-dl/q", data={"url": "https://example.com/watch?v=x"})
    assert r.status_code == 200
    body = r.json()
    assert body == {
        "success": True,
        "url": "https://example.com/watch?v=x",
        "options": {"format": None},
    }
    assert calls["download"] == [("https://example.com/watch?v=x", {"format": None})]


def test_q_ui_redirect(client, calls):
    # Already fixed on main (812bed5: missing HTTP_303_SEE_OTHER import). Pins
    # the now-correct behavior so it cannot regress.
    r = client.post(
        "/youtube-dl/q",
        data={"url": "https://example.com/watch?v=x", "ui": "true"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/youtube-dl?added=https://example.com/watch?v=x"
    assert calls["download"] == [("https://example.com/watch?v=x", {"format": None})]


def test_q_missing_url_returns_json_error(client):
    # Bug pin flipped (was AttributeError -> 500 in the baseline): now the JSON
    # error branch is reachable, with status intentionally unchanged (200).
    r = client.post("/youtube-dl/q", data={})
    assert r.status_code == 200
    assert r.json() == {
        "success": False,
        "error": "/q called without a 'url' in form data",
    }


def test_no_startup_self_update(client, calls):
    # PR #380 removed the lifespan pip self-update. The client fixture enters
    # the app lifespan; nothing must run at startup. The runtime pip upgrade
    # remains available only via the explicit PUT /update endpoint.
    assert calls["update"] == []


def test_update_route(client, calls):
    # Bug pin flipped (was TypeError -> 500 in the baseline): update_route now
    # uses the request-style endpoint signature.
    r = client.put("/youtube-dl/update")
    assert r.status_code == 200
    assert r.json() == {"output": "Initiated package update"}
    assert calls["update"] == [True]


def test_get_ydl_options_audio_postprocessor():
    opts = app.get_ydl_options({"format": "mp3"})
    assert opts["postprocessors"][0]["key"] == "FFmpegExtractAudio"
    assert opts["postprocessors"][0]["preferredcodec"] == "mp3"
    assert opts["postprocessors"][0]["preferredquality"] == "192"


def test_get_ydl_options_video_postprocessor():
    opts = app.get_ydl_options({"format": "mp4"})
    assert opts["postprocessors"][0]["key"] == "FFmpegVideoConvertor"
    # `preferedformat` is the spelling the yt-dlp API itself uses.
    assert opts["postprocessors"][0]["preferedformat"] == "mp4"


def test_get_ydl_options_no_postprocessor_for_non_codec_formats():
    # Pins that "bestvideo", None and unknown formats produce no postprocessors.
    assert app.get_ydl_options({"format": "bestvideo"})["postprocessors"] == []
    assert app.get_ydl_options({"format": None})["postprocessors"] == []
    assert app.get_ydl_options({"format": ""})["postprocessors"] == []


def test_get_ydl_options_base_keys(client):
    opts = app.get_ydl_options({})
    assert sorted(opts) == [
        "download_archive",
        "format",
        "outtmpl",
        "postprocessors",
        "updatetime",
    ]
