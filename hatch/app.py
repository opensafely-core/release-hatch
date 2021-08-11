import logging
from functools import partial

import aiofiles
from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security.api_key import APIKeyHeader
from pydantic import ValidationError
from starlette.requests import Request

from hatch import config, models, schema
from hatch.signing import AuthToken


logger = logging.Logger(__name__)

app = FastAPI()

# Allow SPA to access these files
app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.JOB_SERVER_ENDPOINT],
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


api_key_header = APIKeyHeader(name="Authorization")


def reverse_url(view_name, **kwargs):
    path = app.url_path_for(view_name, **kwargs)
    return config.RELEASE_HOST.rstrip("/") + path


def validate(request: Request, auth_token: str = Security(api_key_header)):
    try:
        token = AuthToken.verify(auth_token, config.JOB_SERVER_TOKEN, "hatch")
    except AuthToken.Expired as exc:
        logger.info(str(exc))
        raise HTTPException(401, "Unauthorized")
    except AuthToken.BadSignature as exc:
        logger.info(str(exc))
        raise HTTPException(403, "Forbbiden")
    except ValidationError as exc:
        logger.info(str(exc))
        raise HTTPException(403, "Forbidden")

    # We validate the full url prefix for 2 reasons:
    # 1) Validating the FQDN prevents possibly use of this token in a different context
    # 2) All urls start with /workspace/{workspace}/, so it effectively
    #    constrains a token to a workspace
    public_url = config.RELEASE_HOST + request.url.path
    if not public_url.startswith(token.url):
        logger.info(
            f"token url '{token.url}' did not match public request url '{public_url}'"
        )
        raise HTTPException(403, "Forbidden")

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


@app.get("/workspace/{workspace}/current", response_model=schema.IndexSchema)
def workspace_index(
    workspace: str, request: Request, token: AuthToken = Depends(validate)
):
    """Return an index of the files on disk in this workspace."""
    path = validate_workspace(workspace)

    # prepare a function for the index function to construct URLs to the
    # correct file endpoint
    url_builder = partial(reverse_url, "workspace_file", workspace=workspace)

    return models.get_index(path, url_builder)


@app.get("/workspace/{workspace}/current/{filename:path}")
async def workspace_file(
    workspace: str, filename: str, token: AuthToken = Depends(validate)
):
    """Return the contents of a file in this workspace.

    Note: this API is async, to serve files efficiently."""
    path = config.WORKSPACES / workspace / filename
    if not await aioexists(path):
        raise HTTPException(404, f"File {filename} not found in workspace {workspace}")

    # FastAPI supports async file responses
    return FileResponse(
        path,
        headers={
            "Content-Security-Policy": f"frame-src: {config.JOB_SERVER_ENDPOINT};"
        },
    )


@app.post("/workspace/{workspace}/release")
def workspace_release(
    workspace: str,
    release: schema.Release,
    token: AuthToken = Depends(validate),
):
    """Create a Release locally and in job-server."""

    workspace_dir = validate_workspace(workspace)
    errors = models.validate_release(workspace, workspace_dir, release)
    if errors:
        raise HTTPException(400, errors)

    response = models.create_release(workspace, workspace_dir, release, token.user)
    release_id = response.headers["Release-Id"]

    # rewrite location header to point to our upload endpoint, so that clients
    # will know where to post their upload requests to.
    response.headers["Location"] = reverse_url(
        "release_file_upload", workspace=workspace, release_id=release_id
    )
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

    # prepare a function for the index function to construct URLs to the
    # correct file endpoint
    url_builder = partial(
        reverse_url,
        "release_file",
        workspace=workspace,
        release_id=release_id,
    )

    return models.get_index(release_dir, url_builder)


@app.get("/workspace/{workspace}/release/{release_id}/{filename:path}")
async def release_file(
    workspace: str, release_id: str, filename: str, token: AuthToken = Depends(validate)
):
    """Return the contents of a file in this workspace.

    Note: this API is async, to serve files efficiently."""
    path = config.WORKSPACES / workspace / "releases" / release_id / filename
    if not await aioexists(path):
        raise HTTPException(404, f"File {filename} not found in release {release_id}")

    return FileResponse(
        path,
        headers={
            "Content-Security-Policy": f"frame-src: {config.JOB_SERVER_ENDPOINT};"
        },
    )


@app.post("/workspace/{workspace}/release/{release_id}")
def release_file_upload(
    workspace: str,
    release_id: str,
    release_file: schema.ReleaseFile,
    token: AuthToken = Depends(validate),
):
    """Upload a file from a release to job-server."""
    name = release_file.name
    workspace_dir = validate_workspace(workspace)
    release_dir = validate_release(workspace_dir, release_id)
    path = release_dir / name
    if not path.exists():
        raise HTTPException(404, f"File {name} not found in release {release_id}")

    response = models.upload_file(release_id, name, path, token.user)
    # forward job-servers response back to client
    return response
