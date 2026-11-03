"""Baseline tests pinning CURRENT behavior, including known bugs.

Bug pins are intentionally asserting today's broken behavior. When a fix PR
changes the behavior, the corresponding test must be updated in that same PR —
that diff is the reviewable signal that a behavior change is intentional.

Note: the missing `HTTP_303_SEE_OTHER` import was already fixed on main
(812bed5), so the UI redirect path is asserted as fixed behavior, not pinned.
"""

import importlib

import pytest
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
    # BUG PIN: TemplateResponse is called as (context, name), but Starlette 1.0's
    # signature is (request, name, context), so the footer version renders EMPTY
    # today. Flip to `version.__version__ in r.text` in the fix PR.
    assert version.__version__ not in r.text


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


def test_q_missing_url_documents_current_bug(client):
    # BUG PIN: `form.get("url").strip()` raises AttributeError when url is
    # missing, so the JSON error branch below it is unreachable today.
    with pytest.raises(AttributeError):
        client.post("/youtube-dl/q", data={})


def test_update_route_documents_current_bug(client):
    # BUG PIN: update_route is defined with a raw-ASGI signature (scope, receive,
    # send) but registered as a Route endpoint, which Starlette 1.0 calls with a
    # single `request` argument, so PUT /update raises TypeError (500) today.
    # Update in the fix PR to assert the JSON response and that update() ran.
    with pytest.raises(TypeError):
        client.put("/youtube-dl/update")


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
