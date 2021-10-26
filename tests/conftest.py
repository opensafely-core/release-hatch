import os
import secrets

import pytest


# force testing config
os.environ["JOB_SERVER_TOKEN"] = secrets.token_hex(32)
os.environ["RELEASE_HOST"] = "http://testserver"

# now we can import hatch stuff
from hatch import config  # noqa: E402
from tests import factories  # noqa: E402


@pytest.fixture(autouse=True)
def set_up_storage(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setattr(config, "WORKSPACES", tmp_path)
    monkeypatch.setattr(config, "CACHE", cache)


@pytest.fixture
def workspace():
    return factories.WorkspaceFactory("workspace")


@pytest.fixture
def release(workspace):
    return factories.ReleaseFactory(name="release_id", workspace=workspace)
