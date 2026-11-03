"""Behavior tests.

Tests marked with a bug-pin comment asserted broken behavior in the baseline
suite (PR #378). This PR flips each pin; the flipped assertion is the
reviewable signal that the behavior change is intentional.
"""

import asyncio
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


def test_q_json_success_pins_current_shape(client, calls, store):
    r = client.post("/youtube-dl/q", data={"url": "https://example.com/watch?v=x"})
    assert r.status_code == 200
    body = r.json()
    # Behavior change in this commit: the download moved from the request cycle to a
    # worker, so the response completes before the download starts and the body gains
    # job_id. success/url/options are unchanged for existing API consumers.
    assert body == {
        "success": True,
        "url": "https://example.com/watch?v=x",
        "options": {"format": None},
        "job_id": body["job_id"],
    }
    job = store.snapshot()[0]
    assert job["id"] == body["job_id"]
    assert job["status"] == "queued"
    # Workers are disabled in the fixture, so processing is explicit here.
    asyncio.run(app.process(job))
    assert calls["download"] == [("https://example.com/watch?v=x", {"format": None})]
    assert job["status"] == "done"


def test_q_accepts_multipart_form_data(client, calls, store):
    # python-multipart is a declared dependency, but the suite only exercised the
    # urlencoded path. This pins the multipart branch of request.form() so a
    # python-multipart or starlette regression is visible in CI.
    r = client.post(
        "/youtube-dl/q",
        files={"url": ("", "https://example.com/watch?v=x", "text/plain")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["url"] == "https://example.com/watch?v=x"
    assert body["options"] == {"format": None}
    # Pins that the multipart path records the same job as the urlencoded path.
    job = store.snapshot()[0]
    assert job["id"] == body["job_id"]
    asyncio.run(app.process(job))
    assert calls["download"] == [("https://example.com/watch?v=x", {"format": None})]


def test_q_logs_queue_add(client, caplog):
    # print() replaced by logging; caplog confirms the message is logged via
    # the named logger at INFO.
    caplog.set_level(logging.INFO, logger="youtube-dl-server")
    client.post("/youtube-dl/q", data={"url": "https://example.com/watch?v=x"})
    assert (
        "Added url https://example.com/watch?v=x to the download queue" in caplog.text
    )


def test_q_ui_redirect(client, calls, store):
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
    # The UI and API paths now share one entry point, so the same job is recorded.
    asyncio.run(app.process(store.snapshot()[0]))
    assert calls["download"] == [("https://example.com/watch?v=x", {"format": None})]


def test_q_missing_url_returns_json_error(client, store):
    # Bug pin flipped (was AttributeError -> 500 in the baseline): now the JSON
    # error branch is reachable, with status intentionally unchanged (200).
    r = client.post("/youtube-dl/q", data={})
    assert r.status_code == 200
    assert r.json() == {
        "success": False,
        "error": "/q called without a 'url' in form data",
    }
    # Pins that the error path records nothing: a job exists only for work that
    # was actually accepted.
    assert store.snapshot() == []


def test_queue_processes_jobs_in_submission_order(client, calls, store, queue):
    client.post("/youtube-dl/q", data={"url": "https://example.com/first"})
    client.post("/youtube-dl/q", data={"url": "https://example.com/second"})

    async def drain():
        for _ in range(2):
            await app.process(await queue.get())

    asyncio.run(drain())
    assert [url for url, _ in calls["download"]] == [
        "https://example.com/first",
        "https://example.com/second",
    ]


def test_concurrency_limit_bounds_running_jobs(client, store, queue, monkeypatch):
    # The ceiling existed implicitly: every request spawned a BackgroundTask, and the
    # only limit was anyio's default thread pool (40 tokens). Now the limit is
    # explicit and observable, so with one worker a second job stays queued.
    observed = {}

    def stub(url, options):
        observed[url] = {job["url"]: job["status"] for job in store.snapshot()}

    monkeypatch.setattr(app, "download", stub)
    client.post("/youtube-dl/q", data={"url": "https://example.com/running"})
    client.post("/youtube-dl/q", data={"url": "https://example.com/queued"})

    async def drain_one():
        await app.process(await queue.get())

    asyncio.run(drain_one())
    assert observed == {
        "https://example.com/running": {
            "https://example.com/running": "running",
            "https://example.com/queued": "queued",
        }
    }


def test_failed_download_is_logged_and_recorded(
    client, calls, store, queue, caplog, monkeypatch
):
    # Bug pin flipped (audit #6): a failure in a BackgroundTask was invisible to the
    # caller because the response had already been sent as success. The failure is now
    # logged and recorded on the job.

    def stub(url, options):
        if url == "https://example.com/fails":
            raise RuntimeError("ERROR: requested format not available")
        calls["download"].append((url, options))

    monkeypatch.setattr(app, "download", stub)
    client.post("/youtube-dl/q", data={"url": "https://example.com/fails"})

    async def drain():
        await app.process(await queue.get())

    asyncio.run(drain())
    job = store.snapshot()[0]
    assert job["status"] == "failed"
    assert job["error"] == "ERROR: requested format not available"
    assert "Download failed for https://example.com/fails" in caplog.text
    # The worker keeps running after a failure, which a BackgroundTask could not.
    client.post("/youtube-dl/q", data={"url": "https://example.com/next"})

    async def drain_next():
        await app.process(await queue.get())

    asyncio.run(drain_next())
    assert [job["status"] for job in store.snapshot()] == ["failed", "done"]
    assert calls["download"] == [("https://example.com/next", {"format": None})]


def test_history_is_bounded(client, store):
    # Pins the documented bound: the record is a live view, not a durable log. The
    # durable record is the yt-dlp archive file (YDL_ARCHIVE_FILE).
    for url in ("a", "b", "c", "d", "e", "f"):
        client.post("/youtube-dl/q", data={"url": f"https://example.com/{url}"})
    assert [job["url"] for job in store.snapshot()] == [
        "https://example.com/b",
        "https://example.com/c",
        "https://example.com/d",
        "https://example.com/e",
        "https://example.com/f",
    ]
    assert len(store.order) == 5
    assert [job["status"] for job in store.snapshot()] == ["queued"] * 5


def test_default_concurrency_is_bounded():
    # Behavior change, recorded as a release note: previously every request spawned its
    # own task, so a burst ran up to anyio's 40-token thread pool. Four is the bound.
    # A single download is unaffected, and 40 restores the previous ceiling.
    assert app.OPTIONS["YDL_MAX_CONCURRENT_DOWNLOADS"] == (int, 4)
    assert app.OPTIONS["YDL_JOB_HISTORY"] == (int, 200)


def test_int_options_warn_and_use_default(monkeypatch, caplog):
    # int is a new cast in the table; pins that it resolves and warns the same way.
    caplog.set_level(logging.WARNING, logger="youtube-dl-server")
    monkeypatch.setenv("YDL_MAX_CONCURRENT_DOWNLOADS", "8")
    assert app.resolve("YDL_MAX_CONCURRENT_DOWNLOADS", int, 4) == 8
    monkeypatch.setenv("YDL_MAX_CONCURRENT_DOWNLOADS", "lots")
    assert app.resolve("YDL_MAX_CONCURRENT_DOWNLOADS", int, 4) == 4
    assert "Ignoring YDL_MAX_CONCURRENT_DOWNLOADS" in caplog.text


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
    for value, expected in (
        ("true", True),
        ("False", False),
        ("1", True),
        ("0", False),
    ):
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


def test_env_audio_format_applies_when_request_names_no_format(monkeypatch):
    # Bug reproduction. request_vars always contained both keys, one of them None,
    # so `app_defaults | request_vars` cleared the env value on every request:
    # YDL_EXTRACT_AUDIO_FORMAT -- documented in .env.example as forcing audio
    # extraction -- had no effect for a request without a format, which is what the
    # REST API sends. The env value is a default, so it must survive.
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
    # Pins the precedence that must not change: an explicit request format overrides
    # the env default for the same choice.
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
    # A request naming a codec or a container selects one pipeline, so the env value
    # of the other kind must not add a second postprocessor (ffmpeg would recode an
    # extracted audio file into a video container). Pinned both directions.
    monkeypatch.setitem(app.app_defaults, "YDL_EXTRACT_AUDIO_FORMAT", "mp3")
    assert [
        p["key"] for p in app.get_ydl_options({"format": "mp4"})["postprocessors"]
    ] == ["FFmpegVideoConvertor"]
    monkeypatch.setitem(app.app_defaults, "YDL_RECODE_VIDEO_FORMAT", "mkv")
    assert [
        p["key"] for p in app.get_ydl_options({"format": "mp3"})["postprocessors"]
    ] == ["FFmpegExtractAudio"]


def test_debug_mode_off(client):
    # Release-note candidate: error responses no longer include tracebacks;
    # API consumers scraping error pages will see plain 500s.
    assert app.app.debug is False


def test_media_options_are_off_by_default(monkeypatch):
    # Pins the no-change guarantee: every option here is opt-in, and the values
    # match yt-dlp's own defaults when unset (subtitleslangs is deliberately
    # absent so yt-dlp keeps its default language selection).
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
    # Postprocessors are unchanged here: this option is the faithful mapping of
    # --write-sub (sidecar files), not --embed-sub. Embedding stays out of scope.
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
    # Order pins the yt-dlp convention: the metadata postprocessor runs after the
    # converters, since containers before conversion may not carry metadata.
    monkeypatch.setitem(app.app_defaults, "YDL_WRITE_SUBTITLES", True)
    opts = app.get_ydl_options({"format": "mp3"})
    assert [p["key"] for p in opts["postprocessors"]] == [
        "FFmpegExtractAudio",
        "FFmpegMetadata",
    ]


def test_get_ydl_options_base_keys(client):
    opts = app.get_ydl_options({})
    # Behavior change in this commit: the two media params appear with their
    # defaults (False, which is what yt-dlp already does), so the base shape
    # gains them. subtitleslangs stays conditional -- it must not be passed as
    # None, which yt-dlp would choke on.
    assert sorted(opts) == [
        "cookiefile",
        "download_archive",
        "format",
        "outtmpl",
        "postprocessors",
        "proxy",
        "updatetime",
        "writesubtitles",
        "writethumbnail",
    ]
