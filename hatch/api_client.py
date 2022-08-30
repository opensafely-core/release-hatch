import logging

import httpx
from fastapi import HTTPException, Response

from hatch import config


logger = logging.getLogger(__name__)


def log_response(resp):
    req = resp._request
    h = resp.headers
    extra = []
    if "Content-Length" in h:
        extra.append(f"size={h['Content-Length']}")
    if "Content-Type" in h:
        extra.append(f"type={h['Content-Type']}")
    logger.info(f"{req.method} {req.url}: status={resp.status_code} {' '.join(extra)}")


# using a module level client should keep the connection open to job-server
client = httpx.Client(
    base_url=config.JOB_SERVER_ENDPOINT,
    headers={"Authorization": config.JOB_SERVER_TOKEN},
    event_hooks={"response": [log_response]},
)


def create_release(workspace, release, user):
    """API call to job server to create a release.

    We return job server's response, but mapped from httpx to a fastapi
    response object, so we can send it straight to the client.
    """
    response = client.post(
        url=f"/releases/workspace/{workspace}",
        content=release.json(),
        headers={
            "OS-User": user,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    if response.status_code != 201:
        logger.debug(f"request body: {release.json()}")
        raise proxy_httpx_error(response)

    return proxy_httpx_response(response)


def upload_file(release_id, name, path, user):
    """Upload file to job server.

    We return job server's response, but mapped from httpx to a fastapi
    response object, so we can send it straight to the client.
    """

    def upload_bytes():
        with path.open("rb") as f:
            while True:
                data = f.read(8192)
                if not data:
                    break
                yield data

    response = client.post(
        url=f"/releases/release/{release_id}",
        content=upload_bytes(),
        headers={
            "OS-User": user,
            "Content-Disposition": f'attachment; filename="{name}"',
            "Content-Type": "application/octet-stream",
            "Accept": "application/json",
        },
    )
    if response.status_code != 201:
        logger.debug(f"request body: {path}")
        raise proxy_httpx_error(response)

    return proxy_httpx_response(response)


def upload_review(release_id, filelist, user):
    """Upload review data to job server.

    We return job server's response, but mapped from httpx to a fastapi
    response object, so we can send it straight to the client.
    """

    response = client.post(
        url=f"/releases/release/{release_id}/reviews",
        content=filelist.json(),
        headers={
            "OS-User": user,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    if response.status_code != 200:
        logger.debug(f"request body: {filelist.json()}")
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
    for header in ["Connection", "Server", "Content-Length"]:
        headers.pop(header, None)
    # add in proxy info
    headers["Via"] = config.RELEASE_HOST
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
    # either it is json from job-server, or its html from nginx
    try:
        detail = response.json()
    except Exception:
        detail = response.content.decode("utf8")

    headers = " ".join(f"{k}={v}" for k, v in response.headers.items())
    logger.error(f"headers: {headers}")
    if len(detail) <= 2048:
        logger.error(f"body:\n{detail}")
    else:  # pragma: no cover
        logger.error(f"body (truncated):\n{detail[:2048]}")

    return HTTPException(
        status_code=response.status_code,
        detail=detail,
        headers=_proxy_headers(response.headers),
    )
