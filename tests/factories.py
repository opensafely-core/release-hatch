from datetime import datetime, timezone

from hatch import config
from hatch.models import get_sha


class BaseFactory:
    root_dir = None

    def __init__(self, name):
        self.name = name
        self.path = self.root_dir / name
        self.path.mkdir(parents=True)

    def write(self, name, contents):
        path = self.path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)
        return path

    def get_date(self, name, iso=True):
        path = self.path / name
        stat = path.stat()
        dt = datetime.fromtimestamp(stat.st_mtime, timezone.utc)
        if iso:
            return dt.isoformat()
        else:
            return dt

    def get_sha(self, name):
        return get_sha(self.path / name)


class WorkspaceFactory(BaseFactory):
    # use property for dynamic look up
    @property
    def root_dir(self):
        return config.WORKSPACES


class ReleaseFactory(BaseFactory):
    def __init__(self, name, workspace):
        self.workspace = workspace
        super().__init__(name)

    # use property for dynamic look up
    @property
    def root_dir(self):
        return self.workspace.path / "releases"

    @property
    def id(self):  # noqa: A003
        return self.name
