import os
import secrets
from dataclasses import dataclass
from pathlib import Path

import pytest


# force testing config
os.environ["BACKEND_TOKEN"] = secrets.token_hex(32)
os.environ["SERVER_HOST"] = "http://testserver"
from hatch import config, signing  # noqa: E402


signing.set_default_key(config.BACKEND_TOKEN, config.BACKEND)


@dataclass
class Workspace:
    path: Path
    cache: Path
    root: Path

    def write(self, name, contents):
        path = self.path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)
        return path


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    cache = tmp_path / "cache"
    releases = tmp_path / "releases"
    workspace.mkdir()
    cache.mkdir()
    releases.mkdir()
    monkeypatch.setattr(config, "WORKSPACES", tmp_path)
    monkeypatch.setattr(config, "CACHE", cache)
    monkeypatch.setattr(config, "RELEASES", releases)
    return Workspace(workspace, cache, tmp_path)
