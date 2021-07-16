import os
from pathlib import Path


# directory where Leve4 files are located
WORKSPACES = Path(os.environ.get("WORKSPACES", "./workspaces/"))
assert WORKSPACES.exists()

# directory to cache sha256 files
CACHE = os.environ.get("CACHE", None)
if CACHE is None:
    CACHE = WORKSPACES / ".cache"
    CACHE.mkdir(exist_ok=True)
else:  # pragma: no cover
    CACHE = Path(CACHE)
    assert CACHE.exists()
