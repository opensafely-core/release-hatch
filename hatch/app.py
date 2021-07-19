import aiofiles
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from hatch import config
from hatch.models import FilesIndex


app = FastAPI()


@app.get("/workspace/{workspace}", response_model=FilesIndex)
def workspace_index(workspace: str):
    """Return an index of the files on disk in this workspace."""
    path = config.WORKSPACES / workspace

    if not path.exists():
        raise HTTPException(404, f"Workspace {workspace} not found")

    return FilesIndex.from_dir(path, f"/workspace/{workspace}/")


@app.get("/workspace/{workspace}/{name:path}")
async def workspace_file(workspace: str, name: str):
    """Return the contents of a file in this workspace.

    Note: this one API is async, to serve files efficiently."""
    path = config.WORKSPACES / workspace / name
    try:
        # we need to async this stat for this api
        await aiofiles.os.stat(path)
    except FileNotFoundError:
        raise HTTPException(404, f"File {name} not found in workspace {workspace}")

    # FastAPI supports async file responses
    return FileResponse(path)
