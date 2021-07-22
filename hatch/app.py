import aiofiles
from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security.api_key import APIKeyHeader
from pydantic import ValidationError
from starlette.requests import Request

from hatch import config, models, schema
from hatch.signing import AuthToken, set_default_key


app = FastAPI()


# Allow SPA to access these files
app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.API_SERVER],
    # credentials here is cookies, we don't use them
    allow_credentials=False,
    # allow caching for 1 hour
    max_age=3200,
    allow_methods=["GET", "HEAD", "POST"],
    # allow browser JS to set Authorization header
    allow_headers=["Authorization"],
    # ensure JS can read our custom headers
    expose_headers=["Response-Id", "File-Id"],
)


# set key to use in signing
set_default_key(config.BACKEND_TOKEN, config.BACKEND)
api_key_header = APIKeyHeader(name="Authorization")


def validate(request: Request, auth_token: str = Security(api_key_header)):
    try:
        token = AuthToken.verify(auth_token)
    except ValidationError:
        raise HTTPException(403, "Unauthorised")

    # We validate the full url prefix for 2 reasons:
    # 1) Validating the FQDN prevents possibly use of this token in a different context
    # 2) All urls start with /workspace/{workspace}/, so it effectively
    #    constrains a token to a workspace
    if not str(request.url).startswith(token.url):
        raise HTTPException(403, "Unauthorised")

    return token


def validate_workspace(workspace):
    """Validate a workspace exists on disk."""
    path = config.WORKSPACES / workspace
    if not path.exists():
        raise HTTPException(404, f"Workspace {workspace} not found")
    return path


def validate_release(workspace_dir, release_id):
    """Validate a Release exists on disk."""
    path = workspace_dir / "releases" / release_id
    if not path.exists():
        raise HTTPException(404, f"Release {release_id} not found")
    return path


async def aioexists(path):
    """async version for use in async file serving APIs."""
    try:
        await aiofiles.os.stat(str(path))
    except FileNotFoundError:
        return False
    else:
        return True


@app.get("/workspace/{workspace}/current/", response_model=schema.IndexSchema)
def workspace_index(
    workspace: str, request: Request, token: AuthToken = Depends(validate)
):
    """Return an index of the files on disk in this workspace."""
    path = validate_workspace(workspace)
    return models.get_index(path, request.url.path + "/")


@app.get("/workspace/{workspace}/current/{name:path}")
async def workspace_file(
    workspace: str, name: str, token: AuthToken = Depends(validate)
):
    """Return the contents of a file in this workspace.

    Note: this API is async, to serve files efficiently."""
    path = config.WORKSPACES / workspace / name
    if not await aioexists(path):
        raise HTTPException(404, f"File {name} not found in workspace {workspace}")

    # FastAPI supports async file responses
    return FileResponse(
        path, headers={"Content-Security-Policy": f"frame-src: {config.API_SERVER};"}
    )


@app.post("/workspace/{workspace}/release")
def workspace_release(
    workspace: str,
    release: schema.Release,
    token: AuthToken = Depends(validate),
):
    """Create a Release locally and in job-server."""

    if token.scope not in ["release", "upload"]:
        raise HTTPException(403, "Unauthorised")

    workspace_dir = validate_workspace(workspace)
    errors = models.validate_release(workspace, workspace_dir, release)
    if errors:
        raise HTTPException(400, errors)

    response = models.create_release(workspace, workspace_dir, release, token.user)
    # forward job-servers response back to client
    return response


@app.get("/workspace/{workspace}/release/{release_id}")
def release_index(
    workspace: str,
    release_id: str,
    request: Request,
    token: AuthToken = Depends(validate),
):
    """Index of files in a Release."""
    workspace_dir = validate_workspace(workspace)
    release_dir = validate_release(workspace_dir, release_id)
    return models.get_index(release_dir, request.url.path + "/")


@app.get("/workspace/{workspace}/release/{release_id}/{name:path}")
async def release_file(
    workspace: str, release_id: str, name: str, token: AuthToken = Depends(validate)
):
    """Return the contents of a file in this workspace.

    Note: this API is async, to serve files efficiently."""
    path = config.WORKSPACES / workspace / "releases" / release_id / name
    if not await aioexists(path):
        raise HTTPException(404, f"File {name} not found in release {release_id}")

    return FileResponse(path)
