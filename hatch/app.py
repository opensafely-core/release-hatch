import aiofiles
from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.responses import FileResponse
from fastapi.security.api_key import APIKeyHeader

from hatch import config
from hatch.models import FilesIndex


api_key_header = APIKeyHeader(name="Authorization")


def validate(auth_token: str = Security(api_key_header)):
    if auth_token != config.BACKEND_TOKEN:
        raise HTTPException(403, "Unauthorised")


app = FastAPI(dependencies=[Depends(validate)])


@app.get(
    "/workspace/{workspace}",
    response_model=FilesIndex,
    dependencies=[Depends(validate)],
)
def workspace_index(workspace: str):
    """Return an index of the files on disk in this workspace."""
    path = config.WORKSPACES / workspace

    if not path.exists():
        raise HTTPException(404, f"Workspace {workspace} not found")

    return FilesIndex.from_dir(path, f"/workspace/{workspace}/")


@app.get("/workspace/{workspace}/{name:path}")
async def workspace_file(workspace: str, name: str):
    """Return the contents of a file in this workspace.

    Note: this API is async, to serve files efficiently."""
    path = config.WORKSPACES / workspace / name
    try:
        await aiofiles.os.stat(path)
    except FileNotFoundError:
        raise HTTPException(404, f"File {name} not found in workspace {workspace}")

    # FastAPI supports async file responses
    return FileResponse(path)
