"""Behavior tests.

Each test pins one observable behavior.
"""

import asyncio
import importlib
import logging
from urllib.parse import quote

from starlette.testclient import TestClient
from yt_dlp import parse_options, version

app = importlib.import_module("youtube-dl-server")


def processing(opts):
    # The postprocessors that run on each downloaded file, in order. yt-dlp's
    # command line also adds its playlist-stage FFmpegConcat (multi-part videos).
    return [
        pp
        for pp in opts["postprocessors"]
        if pp.get("when", "post_process") == "post_process"
    ]


def processing_keys(opts):
    return [pp["key"] for pp in processing(opts)]


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
    assert processing(app.get_ydl_options({"format": "bestvideo"})) == []
    assert processing(app.get_ydl_options({"format": None})) == []
    assert processing(app.get_ydl_options({"format": ""})) == []


def test_env_audio_format_applies_when_request_names_no_format(monkeypatch):
    # The env value is a default, so it must survive a request that names no
    # format, which is what the REST API sends.
    monkeypatch.setitem(app.app_defaults, "YDL_EXTRACT_AUDIO_FORMAT", "mp3")
    [extract] = processing(app.get_ydl_options({}))
    assert extract["key"] == "FFmpegExtractAudio"
    assert extract["preferredcodec"] == "mp3"
    assert extract["preferredquality"] == "192"
    monkeypatch.setitem(app.app_defaults, "YDL_RECODE_VIDEO_FORMAT", "mkv")
    monkeypatch.setitem(app.app_defaults, "YDL_EXTRACT_AUDIO_FORMAT", None)
    assert processing(app.get_ydl_options({})) == [
        {"key": "FFmpegVideoConvertor", "preferedformat": "mkv"}
    ]


def test_request_format_choice_still_wins_over_env_default(monkeypatch):
    # An explicit request format overrides the env default for the same choice.
    monkeypatch.setitem(app.app_defaults, "YDL_EXTRACT_AUDIO_FORMAT", "mp3")
    opts = app.get_ydl_options({"format": "flac"})
    [extract] = processing(opts)
    assert extract["preferredcodec"] == "flac"
    assert extract["preferredquality"] == "192"
    assert opts["final_ext"] == "flac"
    opts = app.get_ydl_options({"format": "bestaudio"})
    assert processing(opts)[0]["preferredcodec"] == "best"
    # "best" keeps the downloaded codec, so there is no final extension to expect.
    assert opts["final_ext"] is None


def test_request_choice_excludes_the_env_choice_of_the_other_kind(monkeypatch):
    # A request naming a codec or a container selects one pipeline, so the env
    # value of the other kind must not add a second postprocessor: ffmpeg would
    # recode an extracted audio file into a video container.
    monkeypatch.setitem(app.app_defaults, "YDL_EXTRACT_AUDIO_FORMAT", "mp3")
    assert processing_keys(app.get_ydl_options({"format": "mp4"})) == [
        "FFmpegVideoConvertor"
    ]
    monkeypatch.setitem(app.app_defaults, "YDL_RECODE_VIDEO_FORMAT", "mkv")
    opts = app.get_ydl_options({"format": "mp3"})
    assert processing_keys(opts) == ["FFmpegExtractAudio"]
    # yt-dlp would name the recode's container, which no longer runs.
    assert opts["final_ext"] == "mp3"


def test_debug_mode_off(client):
    # Error responses do not include tracebacks.
    assert app.app.debug is False


def test_media_options_are_off_by_default(monkeypatch):
    # Every option here is opt-in, and the values match yt-dlp's own defaults
    # when unset, including its default subtitle language selection.
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
    assert opts["subtitleslangs"] == parse_options([]).ydl_opts["subtitleslangs"]
    assert processing(opts) == []


def test_write_subtitles_when_enabled(monkeypatch):
    monkeypatch.setitem(app.app_defaults, "YDL_WRITE_SUBTITLES", True)
    opts = app.get_ydl_options({})
    assert opts["writesubtitles"] is True
    # This is the mapping of --write-sub (sidecar files), not --embed-sub, so
    # postprocessors are unchanged.
    assert processing(opts) == []


def test_subtitles_langs_only_when_set(monkeypatch):
    # yt-dlp's default language selection must survive when the option is unset.
    monkeypatch.setenv("YDL_SUBTITLES_LANGS", "en, es")
    assert app.resolve("YDL_SUBTITLES_LANGS", app.split_langs, None) == ["en", "es"]
    monkeypatch.setitem(app.app_defaults, "YDL_SUBTITLES_LANGS", ["en", "es"])
    assert app.get_ydl_options({})["subtitleslangs"] == ["en", "es"]
    monkeypatch.setitem(app.app_defaults, "YDL_SUBTITLES_LANGS", None)
    assert (
        app.get_ydl_options({})["subtitleslangs"]
        == parse_options([]).ydl_opts["subtitleslangs"]
    )


def test_write_thumbnail_when_enabled(monkeypatch):
    monkeypatch.setitem(app.app_defaults, "YDL_WRITE_THUMBNAIL", True)
    opts = app.get_ydl_options({})
    assert opts["writethumbnail"] is True
    assert processing(opts) == []


def test_metadata_postprocessor_when_enabled(monkeypatch):
    monkeypatch.setitem(app.app_defaults, "YDL_EMBED_METADATA", True)
    assert processing_keys(app.get_ydl_options({})) == ["FFmpegMetadata"]
    # The metadata postprocessor runs after the converters: containers before
    # conversion may not carry metadata.
    monkeypatch.setitem(app.app_defaults, "YDL_WRITE_SUBTITLES", True)
    opts = app.get_ydl_options({"format": "mp3"})
    assert processing_keys(opts) == ["FFmpegExtractAudio", "FFmpegMetadata"]


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


def test_get_ydl_options_defaults(client):
    # With nothing set and no config file, the server's own defaults. Everything
    # else is yt-dlp's command-line default.
    opts = app.get_ydl_options({})
    assert opts["format"] == "bestvideo+bestaudio/best"
    assert opts["outtmpl"] == {"default": app.OPTIONS["YDL_OUTPUT_TEMPLATE"][1]}
    assert opts["updatetime"] is True
    assert opts["ignoreerrors"] is False
    for param in ("download_archive", "cookiefile", "proxy"):
        assert opts[param] is None
    assert opts["writesubtitles"] is False
    assert opts["writethumbnail"] is False
    assert processing(opts) == []


def write_config(path, text):
    path.mkdir(parents=True, exist_ok=True)
    (path / "config").write_text(text)


def test_config_files_are_read_system_then_user(config_dirs, caplog):
    # The image's /etc/yt-dlp/config and the mounted /root/.config/yt-dlp/config.
    # The user's file comes later, so it wins.
    caplog.set_level(logging.INFO, logger="youtube-dl-server")
    system, user = config_dirs
    write_config(system, "--js-runtimes node\n")
    write_config(user, "# every download\n-o '/cfg/%(title)s.%(ext)s'\n")
    assert app.read_config_files() == [
        "--js-runtimes",
        "node",
        "-o",
        "/cfg/%(title)s.%(ext)s",
    ]
    assert str(system / "config") in caplog.text
    assert str(user / "config") in caplog.text


def test_no_config_file_reads_nothing(config_dirs):
    assert app.read_config_files() == []


def test_unparseable_config_file_warns_and_is_ignored(config_dirs, caplog):
    # Like a bad option value, a bad config file must not fail every download.
    caplog.set_level(logging.WARNING, logger="youtube-dl-server")
    write_config(config_dirs[1], "--no-such-option\n")
    assert app.read_config_files() == []
    assert "Ignoring yt-dlp config files: no such option: --no-such-option" in (
        caplog.text
    )


def test_config_file_replaces_the_defaults(monkeypatch):
    monkeypatch.setattr(
        app, "config_args", ["-f", "worst", "-o", "/cfg/%(id)s.%(ext)s", "--no-mtime"]
    )
    opts = app.get_ydl_options({})
    assert opts["format"] == "worst"
    assert opts["outtmpl"]["default"] == "/cfg/%(id)s.%(ext)s"
    assert opts["updatetime"] is False


def test_set_option_wins_over_config_file(monkeypatch):
    # The environment and the .env file win over a config file.
    monkeypatch.setattr(app, "config_args", ["-f", "worst", "--no-mtime"])
    monkeypatch.setitem(app.settings, "YDL_FORMAT", "best")
    monkeypatch.setitem(app.settings, "YDL_UPDATE_TIME", True)
    opts = app.get_ydl_options({})
    assert opts["format"] == "best"
    assert opts["updatetime"] is True


def test_healthz_checks_the_config_file_output_dir(client, monkeypatch, tmp_path):
    monkeypatch.setattr(app, "config_args", ["-o", "/not-writable-cfg/%(id)s.%(ext)s"])
    r = client.get("/healthz")
    assert r.status_code == 503
    assert "/not-writable-cfg" in r.json()["error"]
    monkeypatch.setattr(app, "config_args", ["-o", str(tmp_path / "%(id)s.%(ext)s")])
    assert client.get("/healthz").status_code == 200


def test_config_file_options_reach_downloads(monkeypatch):
    # Options the server has no YDL_* variable for pass straight through, and
    # yt-dlp places its own postprocessors and output templates for them.
    monkeypatch.setattr(
        app,
        "config_args",
        [
            "--embed-thumbnail",
            "--sponsorblock-remove",
            "sponsor",
            "--js-runtimes",
            "node",
        ],
    )
    opts = app.get_ydl_options({})
    assert "node" in opts["js_runtimes"]
    assert opts["writethumbnail"] is True
    assert opts["outtmpl"]["default"] == app.OPTIONS["YDL_OUTPUT_TEMPLATE"][1]
    assert "pl_thumbnail" in opts["outtmpl"]
    assert "SponsorBlock" in [pp["key"] for pp in opts["postprocessors"]]
    assert processing_keys(opts) == ["ModifyChapters", "EmbedThumbnail"]


def test_request_format_replaces_the_config_file_conversion(monkeypatch):
    monkeypatch.setattr(
        app, "config_args", ["-x", "--audio-format", "mp3", "--embed-thumbnail"]
    )
    monkeypatch.setitem(app.app_defaults, "YDL_EMBED_METADATA", True)
    # A request that names no codec or container keeps the config file's.
    opts = app.get_ydl_options({})
    assert processing_keys(opts) == [
        "FFmpegExtractAudio",
        "FFmpegMetadata",
        "EmbedThumbnail",
    ]
    assert opts["final_ext"] == "mp3"
    # yt-dlp's order: the request's converter runs before the config file's
    # EmbedThumbnail, so the cover art ends up in the converted file.
    opts = app.get_ydl_options({"format": "mp4"})
    assert processing_keys(opts) == [
        "FFmpegVideoConvertor",
        "FFmpegMetadata",
        "EmbedThumbnail",
    ]
    # Otherwise yt-dlp would take an existing .mp3 for this download and skip it.
    assert opts["final_ext"] == "mp4"


def test_unparseable_option_value_warns_and_uses_default(monkeypatch, caplog):
    # yt-dlp checks the values it takes, so a bad one cannot fail every download.
    caplog.set_level(logging.WARNING, logger="youtube-dl-server")
    monkeypatch.setenv("YDL_EXTRACT_AUDIO_FORMAT", "zzz")
    assert app.resolve("YDL_EXTRACT_AUDIO_FORMAT", str, None) is None
    assert "Ignoring YDL_EXTRACT_AUDIO_FORMAT" in caplog.text
