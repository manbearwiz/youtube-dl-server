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
        app_module, "download", lambda url, options: calls["download"].append((url, options))
    )
    monkeypatch.setattr(app_module, "update", lambda: calls["update"].append(True))
    # Deliberately NOT using `with TestClient(...)`: entering the context runs
    # the app's lifespan, which today executes a real `pip install --upgrade`.
    # Fix this when the lifespan self-update is removed.
    return TestClient(app_module.app)
