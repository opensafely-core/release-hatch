import aiofiles
from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.responses import FileResponse
from fastapi.security.api_key import APIKeyHeader
from pydantic import ValidationError
from starlette.requests import Request

from hatch import config, models, schema
from hatch.signing import AuthToken, set_default_key


app = FastAPI()
# set key to use in signing
set_default_key(config.BACKEND_TOKEN, config.BACKEND)
api_key_header = APIKeyHeader(name="Authorization")


def validate(request: Request, auth_token: str = Security(api_key_header)):
    try:
        token = AuthToken.verify(auth_token)
    except ValidationError:
        raise HTTPException(403, "Unauthorised")

    if not str(request.url).startswith(token.url):
        raise HTTPException(403, "Unauthorised")

    return token


@app.get("/workspace/{workspace}", response_model=schema.IndexSchema)
def workspace_index(
    workspace: str, request: Request, token: AuthToken = Depends(validate)
):
    """Return an index of the files on disk in this workspace."""
    path = config.WORKSPACES / workspace

    if not path.exists():
        raise HTTPException(404, f"Workspace {workspace} not found")

    return models.get_index(path, request.url.path + "/")


@app.get("/workspace/{workspace}/{name:path}")
async def workspace_file(
    workspace: str, name: str, token: AuthToken = Depends(validate)
):
    """Return the contents of a file in this workspace.

    Note: this API is async, to serve files efficiently."""
    path = config.WORKSPACES / workspace / name
    try:
        await aiofiles.os.stat(path)
    except FileNotFoundError:
        raise HTTPException(404, f"File {name} not found in workspace {workspace}")

    # FastAPI supports async file responses
    return FileResponse(path)


@app.post("/workspace/{workspace}")
def workspace_release(
    workspace: str,
    release: schema.Release,
    token: AuthToken = Depends(validate),
):
    """Create a Release locally and in job-server."""

    workspace_dir = config.WORKSPACES / workspace
    if not workspace_dir.exists():
        raise HTTPException(404, f"Workspace {workspace} not found")

    errors = models.validate_release(workspace, workspace_dir, release)
    if errors:
        raise HTTPException(400, errors)

    response = models.create_release(workspace, workspace_dir, release, token.user)
    # forward job-servers response back to client
    return response
