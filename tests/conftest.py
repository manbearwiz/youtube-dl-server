import importlib
import os
import sys
from pathlib import Path

import pytest
from starlette.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent

# The app resolves its template directory and .env relative to the CWD, so pin
# the CWD to the repo root for hermetic runs from any caller.
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

# Module name contains a hyphen, so it cannot be a plain `import`.
app_module = importlib.import_module("youtube-dl-server")


@pytest.fixture
def calls():
    """Records side effects that would otherwise hit the network or pip."""
    return {"download": [], "update": [], "check": [], "latest": None}


@pytest.fixture
def status():
    """The update-check record, reset so tests cannot see each other's state."""
    record = app_module.update_status
    record["current"] = app_module.version.__version__
    record["latest"] = None
    record["checked_at"] = None
    record["update_available"] = False
    return record


@pytest.fixture
def fetch(monkeypatch, calls):
    """Stub for the PyPI request, so no test reaches the network."""

    def fake_latest():
        calls["check"].append(True)
        return calls["latest"]

    monkeypatch.setattr(app_module, "fetch_latest", fake_latest)
    return calls


@pytest.fixture
def client(monkeypatch, fetch):
    calls = fetch
    monkeypatch.setattr(
        app_module,
        "download",
        lambda url, options: calls["download"].append((url, options)),
    )
    monkeypatch.setattr(app_module, "update", lambda: calls["update"].append(True))
    # Safe as a context manager now that the lifespan pip self-update is gone
    # (PR #380); test_no_startup_self_update protects that property.
    with TestClient(app_module.app) as client:
        yield client
