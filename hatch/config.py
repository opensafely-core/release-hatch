import os
from pathlib import Path


# directory where Leve4 files are located
WORKSPACES = Path(os.environ.get("WORKSPACES", "./workspaces/"))
assert WORKSPACES.exists()

# directory to cache sha256 files
CACHE = os.environ.get("CACHE", None)
if CACHE is None:
    CACHE = WORKSPACES / "cache"
    CACHE.mkdir(exist_ok=True)
else:  # pragma: no cover
    CACHE = Path(CACHE)
    assert CACHE.exists()

# directory to copy pending release file to
RELEASES = os.environ.get("RELEASES", None)
if RELEASES is None:
    RELEASES = WORKSPACES / "releases"
    RELEASES.mkdir(exist_ok=True)
else:  # pragma: no cover
    RELEASES = Path(RELEASES)
    assert RELEASES.exists()


BACKEND_TOKEN = os.environ.get("BACKEND_TOKEN")
assert BACKEND_TOKEN
BACKEND = os.environ.get("BACKEND", "test-backend")

API_SERVER = os.environ.get("API_SERVER", "https://jobs.opensafely.org")
SERVER_HOST = os.environ.get("SERVER_HOST")
