from datetime import datetime
from typing import Dict, List

from pydantic import BaseModel


class FileSchema(BaseModel):
    """Metadata for a workspace file."""

    name: str
    url: str
    size: int
    sha256: str
    user: str = None
    date: datetime = None


class IndexSchema(BaseModel):
    """An index of files in a workspace.

    This must match the json format that the SPA's client API expects.
    """

    files: List[FileSchema]


class Release(BaseModel):
    """Request a release.

    Files is a dict with {name: sha256} mapping.
    """

    files: Dict[str, str]
