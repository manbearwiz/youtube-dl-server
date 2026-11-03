"""Behavior tests.

Tests marked with a bug-pin comment asserted broken behavior in the baseline
suite (PR #378). This PR flips each pin; the flipped assertion is the
reviewable signal that the behavior change is intentional.
"""

import importlib
import logging
from urllib.parse import quote

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


def test_q_accepts_multipart_form_data(client, calls):
    # python-multipart is a declared dependency, but the suite only exercised the
    # urlencoded path. This pins the multipart branch of request.form() so a
    # python-multipart or starlette regression is visible in CI.
    r = client.post(
        "/youtube-dl/q",
        files={"url": ("", "https://example.com/watch?v=x", "text/plain")},
    )
    assert r.status_code == 200
    assert r.json() == {
        "success": True,
        "url": "https://example.com/watch?v=x",
        "options": {"format": None},
    }
    assert calls["download"] == [("https://example.com/watch?v=x", {"format": None})]


def test_q_logs_queue_add(client, caplog):
    # print() replaced by logging; caplog confirms the message is logged via
    # the named logger at INFO.
    caplog.set_level(logging.INFO, logger="youtube-dl-server")
    client.post("/youtube-dl/q", data={"url": "https://example.com/watch?v=x"})
    assert "Added url https://example.com/watch?v=x to the download queue" in caplog.text


def test_q_ui_redirect(client, calls):
    # Already fixed on main (812bed5: missing HTTP_303_SEE_OTHER import). Pins
    # the now-correct behavior so it cannot regress.
    r = client.post(
        "/youtube-dl/q",
        data={"url": "https://example.com/watch?v=x", "ui": "true"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    # Behavior change in this commit: the added= value is percent-encoded
    # instead of raw string concatenation, so the UI page's query param parses
    # correctly for urls containing ? or &.
    assert r.headers["location"] == "/youtube-dl?added=" + quote(
        "https://example.com/watch?v=x"
    )
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


def test_healthz_ok(client, monkeypatch, tmp_path):
    # Point the output template at a writable directory for the probe.
    monkeypatch.setitem(
        app.app_defaults, "YDL_OUTPUT_TEMPLATE", str(tmp_path / "%(title)s.%(ext)s")
    )
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_healthz_reports_unwritable_output_dir(client, monkeypatch):
    monkeypatch.setitem(
        app.app_defaults,
        "YDL_OUTPUT_TEMPLATE",
        "/definitely-not-writable-for-tests/%(title)s.%(ext)s",
    )
    r = client.get("/healthz")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "unhealthy"
    assert "not writable" in body["error"]


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


def test_debug_mode_off(client):
    # Release-note candidate: error responses no longer include tracebacks;
    # API consumers scraping error pages will see plain 500s.
    assert app.app.debug is False


def test_get_ydl_options_base_keys(client):
    opts = app.get_ydl_options({})
    assert sorted(opts) == [
        "download_archive",
        "format",
        "outtmpl",
        "postprocessors",
        "updatetime",
    ]
