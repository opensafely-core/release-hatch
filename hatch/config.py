import logging
import os
import sys
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

JOB_SERVER_TOKEN = os.environ.get("JOB_SERVER_TOKEN")
assert JOB_SERVER_TOKEN
BACKEND = os.environ.get("BACKEND", "test-backend")

JOB_SERVER_ENDPOINT = os.environ.get(
    "JOB_SERVER_ENDPOINT", "https://jobs.opensafely.org"
)
RELEASE_HOST = os.environ.get("RELEASE_HOST")

DEBUG_LEVEL = os.environ.get("DEBUG", "info")


def setup_logging():
    logger = logging.getLogger("hatch")
    logger.setLevel(logging.getLevelName(DEBUG_LEVEL.upper()))
    handler = logging.StreamHandler(sys.stdout)
    # if running under uvicorn, reuse it's formatter
    uvicorn_handlers = logging.getLogger("uvicorn").handlers
    if uvicorn_handlers:  # pragma: no cover
        handler.setFormatter(uvicorn_handlers[0].formatter)
    logger.addHandler(handler)
