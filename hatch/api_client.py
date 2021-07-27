import httpx
from fastapi import HTTPException, Response

from hatch import config


# using a module level client should keep the connection open to job-server
client = httpx.Client(
    base_url=config.API_SERVER, headers={"Authorization": config.BACKEND_TOKEN}
)


def create_release(workspace, release, user):
    """API call to job server to create a release.

    We return job server's response, but mapped from httpx to a fastapi
    response object, so we can send it straight to the client.
    """
    response = client.post(
        url=f"/api/v2/releases/workspace/{workspace}",
        content=release.json(),
        headers={
            "OS-User": user,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    if response.status_code != 201:
        raise proxy_httpx_error(response)

    return proxy_httpx_response(response)


def upload_file(release_id, name, path, user):
    """Upload file to job server.

    We return job server's response, but mapped from httpx to a fastapi
    response object, so we can send it straight to the client.
    """
    response = client.post(
        url=f"/api/v2/releases/release/{release_id}",
        content=path.read_bytes(),
        headers={
            "OS-User": user,
            "Content-Disposition": f'attachment; filename="{name}"',
            "Content-Type": "application/octet-stream",
            "Accept": "application/json",
        },
    )
    if response.status_code != 201:
        raise proxy_httpx_error(response)

    return proxy_httpx_response(response)


def _proxy_headers(orig_headers):
    """Remove hop-based headers.

    When proxying http responses, certain headers are not valid to proxy, as
    they are per-hop rather than per-connection.

    Normally, something like nginx would do this for us, but this app is
    designed to not need nginx.
    """
    headers = orig_headers.copy()
    for header in ["Connection", "Server"]:
        headers.pop(header, None)
    # add in proxy info
    headers["Via"] = config.SERVER_HOST
    return headers


def proxy_httpx_response(response):
    """Take an upstream httpx response and convert to a proxied FastAPI Response."""
    return Response(
        status_code=response.status_code,
        content=response.content,
        headers=_proxy_headers(response.headers),
    )


def proxy_httpx_error(response):
    """Take an upstream httpx response and convert to a proxied FastAPI HTTPException."""
    try:
        detail = response.json()["detail"]
    except Exception:
        detail = response.content

    return HTTPException(
        status_code=response.status_code,
        detail=detail,
        headers=_proxy_headers(response.headers),
    )
