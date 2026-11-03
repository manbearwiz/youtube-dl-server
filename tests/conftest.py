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
    return {"download": [], "update": []}


@pytest.fixture
def client(monkeypatch, calls):
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
