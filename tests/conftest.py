from dataclasses import dataclass
from pathlib import Path

import pytest

import hatch.config


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
    workspace.mkdir()
    cache.mkdir()
    monkeypatch.setattr(hatch.config, "WORKSPACES", tmp_path)
    monkeypatch.setattr(hatch.config, "CACHE", cache)
    return Workspace(workspace, cache, tmp_path)
