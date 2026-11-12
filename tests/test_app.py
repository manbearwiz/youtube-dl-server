"""Behavior tests.

Each test pins one observable behavior.
"""

import asyncio
import importlib
import logging
from urllib.parse import quote

from starlette.testclient import TestClient
from yt_dlp import version

app = importlib.import_module("youtube-dl-server")


def test_root_redirects(client):
    # Starlette 1.0 RedirectResponse defaults to 307.
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == "/youtube-dl"


def test_queue_list_renders(client):
    r = client.get("/youtube-dl")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    # TemplateResponse uses Starlette's (request, name, context) signature.
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
    # The multipart branch of request.form(), so a python-multipart or starlette
    # regression is visible in CI.
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
    # Queue adds are logged through the named logger at INFO.
    caplog.set_level(logging.INFO, logger="youtube-dl-server")
    client.post("/youtube-dl/q", data={"url": "https://example.com/watch?v=x"})
    assert (
        "Added url https://example.com/watch?v=x to the download queue" in caplog.text
    )


def test_q_ui_redirect(client, calls):
    r = client.post(
        "/youtube-dl/q",
        data={"url": "https://example.com/watch?v=x", "ui": "true"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    # percent-encoding makes the added= query param parse for urls containing
    # ? or &.
    assert r.headers["location"] == "/youtube-dl?added=" + quote(
        "https://example.com/watch?v=x"
    )
    assert calls["download"] == [("https://example.com/watch?v=x", {"format": None})]


def test_q_missing_url_returns_json_error(client):
    # Status stays 200: the API contract for a missing url is a JSON error body.
    r = client.post("/youtube-dl/q", data={})
    assert r.status_code == 200
    assert r.json() == {
        "success": False,
        "error": "/q called without a 'url' in form data",
    }


def test_no_startup_self_update(client, calls):
    # Nothing runs at startup; the pip upgrade happens only through PUT /update.
    assert calls["update"] == []


def test_update_route(client, calls):
    r = client.put("/youtube-dl/update")
    assert r.status_code == 200
    assert r.json() == {"output": "Initiated package update"}
    assert calls["update"] == [True]


def test_version_tuple_compare():
    # Dotted numeric segments, so int tuples order correctly, including the
    # occasional fourth segment. A non-numeric segment is not comparable.
    assert app.version_tuple("2026.10.26") == (2026, 10, 26)
    assert app.version_tuple("2026.10.26.1") > app.version_tuple("2026.10.26")
    assert app.version_tuple("2026.10.26rc1") is None


def test_update_check_is_off_by_default(client, calls, status):
    assert app.app_defaults["YDL_UPDATE_CHECK"] is False
    assert calls["check"] == []
    assert client.get("/youtube-dl/update").json() == {
        "current": status["current"],
        "latest": None,
        "checked_at": None,
        "update_available": False,
    }
    assert "available)" not in client.get("/youtube-dl").text


def test_healthz_makes_no_network_call(status, fetch, calls, monkeypatch):
    # The readiness probe stays local and cheap: it reads the record, it does not
    # fetch.
    monkeypatch.setitem(app.app_defaults, "YDL_UPDATE_CHECK", True)
    calls["latest"] = "2099.1.1"

    with TestClient(app.app) as client:
        calls["check"].clear()
        client.get("/healthz")
        assert calls["check"] == []


def test_update_check_runs_at_startup_when_enabled(status, fetch, calls, monkeypatch):
    monkeypatch.setitem(app.app_defaults, "YDL_UPDATE_CHECK", True)
    calls["latest"] = "2099.1.1"

    with TestClient(app.app):
        # The first check is awaited during startup, so the record is populated
        # before the first request.
        assert calls["check"] == [True]
        assert status["update_available"] is True


def test_update_check_reports_an_available_upgrade(client, fetch, calls, status):
    calls["latest"] = "2099.1.1"
    asyncio.run(app.check_update())

    assert status["update_available"] is True
    assert client.get("/youtube-dl/update").json() == {
        "current": status["current"],
        "latest": "2099.1.1",
        "checked_at": status["checked_at"],
        "update_available": True,
    }
    assert "(2099.1.1 available)" in client.get("/youtube-dl").text


def test_ui_shows_nothing_when_up_to_date(client, fetch, calls, status):
    calls["latest"] = status["current"]
    asyncio.run(app.check_update())

    assert status["update_available"] is False
    assert "available)" not in client.get("/youtube-dl").text


def test_update_check_failure_is_logged_and_not_reported(
    client, status, monkeypatch, caplog
):
    caplog.set_level(logging.WARNING, logger="youtube-dl-server")

    def boom():
        raise RuntimeError("no network")

    monkeypatch.setattr(app, "fetch_latest", boom)
    asyncio.run(app.check_update())

    assert "update check failed" in caplog.text
    assert status["latest"] is None
    assert status["update_available"] is False
    assert client.get("/youtube-dl/update").json()["update_available"] is False
    assert "available)" not in client.get("/youtube-dl").text


def test_update_check_interval_is_clamped(monkeypatch):
    # The floor keeps a mis-set interval from turning the check into a loop against
    # the index.
    monkeypatch.setitem(app.app_defaults, "YDL_UPDATE_CHECK_INTERVAL", 0)
    assert app.check_interval() == app.MIN_CHECK_INTERVAL
    monkeypatch.setitem(app.app_defaults, "YDL_UPDATE_CHECK_INTERVAL", 7200)
    assert app.check_interval() == 7200


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
    # What starlette's cast=bool accepts: true/1/false/0, case-insensitive.
    # Deferring to Config means no bespoke vocabulary.
    for value, expected in (
        ("true", True),
        ("False", False),
        ("1", True),
        ("0", False),
    ):
        monkeypatch.setenv("YDL_TEST_BOOL", value)
        assert app.resolve("YDL_TEST_BOOL", bool, True) is expected


def test_resolve_warns_and_uses_default_for_unparseable_value(monkeypatch, caplog):
    # An unparseable value warns and keeps the documented default instead of
    # raising at import time, which would take the whole app down.
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
    # A boolean setting reaches the yt-dlp options as a bool.
    monkeypatch.setenv("YDL_UPDATE_TIME", "false")
    monkeypatch.setitem(
        app.app_defaults, "YDL_UPDATE_TIME", app.resolve("YDL_UPDATE_TIME", bool, True)
    )
    assert app.get_ydl_options({})["updatetime"] is False


def test_env_var_wins_over_dotenv_file(monkeypatch, tmp_path):
    # Precedence: process environment > .env file > default.
    (tmp_path / ".env").write_text("YDL_FORMAT=from_file\n")
    config = app.config.__class__(tmp_path / ".env")
    monkeypatch.setenv("YDL_FORMAT", "from_env")
    assert config("YDL_FORMAT") == "from_env"


def test_proxy_option_is_none_when_unset(monkeypatch):
    # An unset YDL_PROXY passes None, which yt-dlp treats as "use the
    # environment's proxy discovery".
    monkeypatch.delenv("YDL_PROXY", raising=False)
    assert app.get_ydl_options({})["proxy"] is None


def test_proxy_value_passed_through(monkeypatch):
    monkeypatch.setitem(app.app_defaults, "YDL_PROXY", "http://127.0.0.1:8118")
    assert app.get_ydl_options({})["proxy"] == "http://127.0.0.1:8118"


def test_empty_proxy_env_value_means_unset(monkeypatch):
    # An empty YDL_PROXY (common in compose and .env files) means not set, so
    # yt-dlp's own proxy discovery still applies.
    monkeypatch.setenv("YDL_PROXY", "")
    assert app.resolve("YDL_PROXY", str, None) is None


def test_cookie_file_option_is_none_when_unset(monkeypatch):
    # Cookies are only read when configured.
    monkeypatch.delenv("YDL_COOKIE_FILE", raising=False)
    assert app.get_ydl_options({})["cookiefile"] is None


def test_cookie_file_path_passed_as_given(monkeypatch):
    # The cookie file is the path as the operator wrote it, so it can live
    # outside the output volume.
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
    # "bestvideo", None and unknown formats produce no postprocessors.
    assert app.get_ydl_options({"format": "bestvideo"})["postprocessors"] == []
    assert app.get_ydl_options({"format": None})["postprocessors"] == []
    assert app.get_ydl_options({"format": ""})["postprocessors"] == []


def test_env_audio_format_applies_when_request_names_no_format(monkeypatch):
    # The env value is a default, so it must survive a request that names no
    # format, which is what the REST API sends.
    monkeypatch.setitem(app.app_defaults, "YDL_EXTRACT_AUDIO_FORMAT", "mp3")
    assert app.get_ydl_options({})["postprocessors"] == [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }
    ]
    monkeypatch.setitem(app.app_defaults, "YDL_RECODE_VIDEO_FORMAT", "mkv")
    monkeypatch.setitem(app.app_defaults, "YDL_EXTRACT_AUDIO_FORMAT", None)
    assert app.get_ydl_options({})["postprocessors"] == [
        {"key": "FFmpegVideoConvertor", "preferedformat": "mkv"}
    ]


def test_request_format_choice_still_wins_over_env_default(monkeypatch):
    # An explicit request format overrides the env default for the same choice.
    monkeypatch.setitem(app.app_defaults, "YDL_EXTRACT_AUDIO_FORMAT", "mp3")
    opts = app.get_ydl_options({"format": "flac"})
    assert opts["postprocessors"] == [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": "flac",
            "preferredquality": "192",
        }
    ]
    assert (
        app.get_ydl_options({"format": "bestaudio"})["postprocessors"][0][
            "preferredcodec"
        ]
        == "best"
    )


def test_request_choice_excludes_the_env_choice_of_the_other_kind(monkeypatch):
    # A request naming a codec or a container selects one pipeline, so the env
    # value of the other kind must not add a second postprocessor: ffmpeg would
    # recode an extracted audio file into a video container.
    monkeypatch.setitem(app.app_defaults, "YDL_EXTRACT_AUDIO_FORMAT", "mp3")
    assert [
        p["key"] for p in app.get_ydl_options({"format": "mp4"})["postprocessors"]
    ] == ["FFmpegVideoConvertor"]
    monkeypatch.setitem(app.app_defaults, "YDL_RECODE_VIDEO_FORMAT", "mkv")
    assert [
        p["key"] for p in app.get_ydl_options({"format": "mp3"})["postprocessors"]
    ] == ["FFmpegExtractAudio"]


def test_debug_mode_off(client):
    # Error responses do not include tracebacks.
    assert app.app.debug is False


def test_media_options_are_off_by_default(monkeypatch):
    # Every option here is opt-in, and the values match yt-dlp's own defaults
    # when unset. subtitleslangs is absent so yt-dlp keeps its default language
    # selection.
    for key in (
        "YDL_WRITE_SUBTITLES",
        "YDL_SUBTITLES_LANGS",
        "YDL_WRITE_THUMBNAIL",
        "YDL_EMBED_METADATA",
    ):
        monkeypatch.delenv(key, raising=False)
    opts = app.get_ydl_options({})
    assert opts["writesubtitles"] is False
    assert opts["writethumbnail"] is False
    assert "subtitleslangs" not in opts
    assert opts["postprocessors"] == []


def test_write_subtitles_when_enabled(monkeypatch):
    monkeypatch.setitem(app.app_defaults, "YDL_WRITE_SUBTITLES", True)
    opts = app.get_ydl_options({})
    assert opts["writesubtitles"] is True
    # This is the mapping of --write-sub (sidecar files), not --embed-sub, so
    # postprocessors are unchanged.
    assert opts["postprocessors"] == []


def test_subtitles_langs_only_when_set(monkeypatch):
    # yt-dlp's default language selection must survive when the option is unset,
    # so the key is only added when the operator set it.
    monkeypatch.setenv("YDL_SUBTITLES_LANGS", "en, es")
    assert app.resolve("YDL_SUBTITLES_LANGS", app.split_langs, None) == ["en", "es"]
    monkeypatch.setitem(app.app_defaults, "YDL_SUBTITLES_LANGS", ["en", "es"])
    assert app.get_ydl_options({})["subtitleslangs"] == ["en", "es"]
    monkeypatch.setitem(app.app_defaults, "YDL_SUBTITLES_LANGS", None)
    assert "subtitleslangs" not in app.get_ydl_options({})


def test_write_thumbnail_when_enabled(monkeypatch):
    monkeypatch.setitem(app.app_defaults, "YDL_WRITE_THUMBNAIL", True)
    opts = app.get_ydl_options({})
    assert opts["writethumbnail"] is True
    assert opts["postprocessors"] == []


def test_metadata_postprocessor_when_enabled(monkeypatch):
    monkeypatch.setitem(app.app_defaults, "YDL_EMBED_METADATA", True)
    assert [p["key"] for p in app.get_ydl_options({})["postprocessors"]] == [
        "FFmpegMetadata"
    ]
    # The metadata postprocessor runs after the converters: containers before
    # conversion may not carry metadata.
    monkeypatch.setitem(app.app_defaults, "YDL_WRITE_SUBTITLES", True)
    opts = app.get_ydl_options({"format": "mp3"})
    assert [p["key"] for p in opts["postprocessors"]] == [
        "FFmpegExtractAudio",
        "FFmpegMetadata",
    ]


def test_ignore_errors_is_off_by_default(monkeypatch):
    # Same as yt-dlp's own default: a failing item aborts the download.
    monkeypatch.delenv("YDL_IGNORE_ERRORS", raising=False)
    assert app.resolve("YDL_IGNORE_ERRORS", bool, False) is False
    assert app.get_ydl_options({})["ignoreerrors"] is False


def test_ignore_errors_when_enabled(monkeypatch):
    # The equivalent of yt-dlp --ignore-errors: an unavailable video (deleted,
    # region blocked) in a playlist is skipped instead of ending the whole job.
    monkeypatch.setenv("YDL_IGNORE_ERRORS", "true")
    assert app.resolve("YDL_IGNORE_ERRORS", bool, False) is True
    monkeypatch.setitem(app.app_defaults, "YDL_IGNORE_ERRORS", True)
    assert app.get_ydl_options({})["ignoreerrors"] is True


def test_get_ydl_options_base_keys(client):
    opts = app.get_ydl_options({})
    # The media params appear with their defaults (False, which is yt-dlp's
    # default too). subtitleslangs is conditional: passing None would break
    # yt-dlp.
    assert sorted(opts) == [
        "cookiefile",
        "download_archive",
        "format",
        "ignoreerrors",
        "outtmpl",
        "postprocessors",
        "proxy",
        "updatetime",
        "writesubtitles",
        "writethumbnail",
    ]
