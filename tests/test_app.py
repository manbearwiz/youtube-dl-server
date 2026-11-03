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


def test_resolve_uses_config_bool_mapping(monkeypatch):
    # Documents what starlette's cast=bool actually accepts: true/1/false/0,
    # case-insensitive. Deferring to Config means no bespoke vocabulary.
    for value, expected in (("true", True), ("False", False), ("1", True), ("0", False)):
        monkeypatch.setenv("YDL_TEST_BOOL", value)
        assert app.resolve("YDL_TEST_BOOL", bool, True) is expected


def test_resolve_warns_and_uses_default_for_unparseable_value(monkeypatch, caplog):
    # Bug pin flipped: an unparseable value (including an empty one) raised
    # ValueError at import time and took the whole app down -- a container restart
    # loop with no clear message. It now warns and keeps the documented default.
    caplog.set_level(logging.WARNING, logger="youtube-dl-server")
    monkeypatch.setenv("YDL_TEST_BOOL", "yes")
    assert app.resolve("YDL_TEST_BOOL", bool, True) is True
    assert "Ignoring YDL_TEST_BOOL" in caplog.text


def test_empty_value_means_not_set(monkeypatch):
    # An env file cannot distinguish absent from empty, and yt-dlp checks these
    # options with `is not None`, so an empty value must resolve to the default.
    monkeypatch.setenv("YDL_ARCHIVE_FILE", "")
    assert app.resolve("YDL_ARCHIVE_FILE", str, None) is None


def test_setting_reaches_ydl_options(monkeypatch):
    # Pins the wiring: a boolean setting must reach the yt-dlp options as a bool.
    monkeypatch.setenv("YDL_UPDATE_TIME", "false")
    monkeypatch.setitem(
        app.app_defaults, "YDL_UPDATE_TIME", app.resolve("YDL_UPDATE_TIME", bool, True)
    )
    assert app.get_ydl_options({})["updatetime"] is False


def test_env_var_wins_over_dotenv_file(monkeypatch, tmp_path):
    # Both sources are supported. Documented precedence: process environment >
    # .env file > default. Pinned so the two sources cannot drift in behavior.
    (tmp_path / ".env").write_text("YDL_FORMAT=from_file\n")
    config = app.config.__class__(tmp_path / ".env")
    monkeypatch.setenv("YDL_FORMAT", "from_env")
    assert config("YDL_FORMAT") == "from_env"


def test_proxy_option_is_none_when_unset(monkeypatch):
    # Pins the no-change guarantee for existing installs: an unset YDL_PROXY
    # passes None, which is what yt-dlp treats as "use the environment's proxy
    # discovery".
    monkeypatch.delenv("YDL_PROXY", raising=False)
    assert app.get_ydl_options({})["proxy"] is None


def test_proxy_value_passed_through(monkeypatch):
    monkeypatch.setitem(app.app_defaults, "YDL_PROXY", "http://127.0.0.1:8118")
    assert app.get_ydl_options({})["proxy"] == "http://127.0.0.1:8118"


def test_empty_proxy_env_value_means_unset(monkeypatch):
    # An empty YDL_PROXY= (common in compose files and .env files) must not
    # disable yt-dlp's own proxy discovery. Worth knowing: yt-dlp's CLI treats an
    # explicit --proxy '' as "no proxy", so this is our documented rule -- an
    # env file cannot distinguish absent from empty, so empty means not set.
    monkeypatch.setenv("YDL_PROXY", "")
    assert app.resolve("YDL_PROXY", str, None) is None


def test_cookie_file_option_is_none_when_unset(monkeypatch):
    # Pins the no-change guarantee: cookies are only read when configured, so
    # existing installs behave exactly as before.
    monkeypatch.delenv("YDL_COOKIE_FILE", raising=False)
    assert app.get_ydl_options({})["cookiefile"] is None


def test_cookie_file_path_passed_as_given(monkeypatch):
    # Bug pin flipped against #96: that PR hard-prefixed "/youtube-dl/", which
    # assumed the cookie file lives in the output volume. The value is a path as
    # the operator wrote it, so a separate mount works.
    monkeypatch.setitem(app.app_defaults, "YDL_COOKIE_FILE", "cookies.txt")
    assert app.get_ydl_options({})["cookiefile"] == "cookies.txt"
    monkeypatch.setitem(app.app_defaults, "YDL_COOKIE_FILE", "/config/cookies.txt")
    assert app.get_ydl_options({})["cookiefile"] == "/config/cookies.txt"


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
        "cookiefile",
        "download_archive",
        "format",
        "outtmpl",
        "postprocessors",
        "proxy",
        "updatetime",
    ]
