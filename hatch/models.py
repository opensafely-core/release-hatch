import hashlib
from typing import List

from pydantic import BaseModel

from hatch import config


def get_sha(path):
    """Calculate and cache the sha256 hash of a file.

    We cache because a big workspace can have lots of large files, and serving
    the index would involve calculating the hashes of all files, which could get
    slow.

    We cache it in a separate directory, but the same relative path. So the
    cache for config.WORKSPACES/workspace1/output/file.txt is located at
    config.CACHE/workspace1/output/file.txt.
    """
    sha_path = config.CACHE / path.relative_to(config.WORKSPACES)
    sha = None
    # does cache file exist and is current?
    if sha_path.exists():
        sha_modified = sha_path.stat().st_mtime
        src_modified = path.stat().st_mtime
        if src_modified < sha_modified:
            sha = sha_path.read_text()

    if sha is None:
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        sha_path.parent.mkdir(parents=True, exist_ok=True)
        sha_path.write_text(sha)

    return sha


class FileMetadata(BaseModel):
    """Metadata for a workspace file."""

    name: str
    url: str
    size: int
    sha256: str

    @classmethod
    def from_path(cls, directory, name, urlbase):
        assert urlbase.endswith("/")
        abspath = directory / name
        return cls(
            name=str(name),
            url=urlbase + f"{name}",
            size=abspath.stat().st_size,
            sha256=get_sha(abspath),
        )


class FilesIndex(BaseModel):
    """An index of files in a workspace.

    This must match the json format that the SPA's client API expects.
    """

    files: List[FileMetadata]

    @classmethod
    def from_dir(cls, path, url):
        paths = sorted([p.relative_to(path) for p in path.glob("**/*") if p.is_file()])
        return cls(files=[FileMetadata.from_path(path, p, url) for p in paths])
