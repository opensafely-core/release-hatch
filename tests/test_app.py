from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

import itsdangerous
from fastapi.testclient import TestClient

from hatch import app, config, schema, signing
from tests.factories import WorkspaceFactory
from tests.test_signing import create_raw_token


client = TestClient(app.app)


def auth_token(path, user="user", expiry=None, scope="view"):
    if expiry is None:  # pragma: no cover
        expiry = datetime.now(timezone.utc) + timedelta(hours=1)

    return signing.AuthToken(
        url=urljoin(client.base_url, path),
        user=user,
        expiry=expiry,
        scope=scope,
    )


def auth_headers(workspace="workspace", user="user", expiry=None, scope="view"):
    """Helper to create valid authentication headers for a specific workspace"""
    token = auth_token(f"/workspace/{workspace}", user, expiry, scope)
    return {"Authorization": token.sign()}


def test_cors():
    response = client.options(
        "/workspace/workspace/current",
        headers={
            "Origin": config.API_SERVER,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers["Access-Control-Allow-Methods"] == "GET, HEAD, POST"
    assert response.headers["Access-Control-Allow-Origin"] == config.API_SERVER
    assert response.headers["Access-Control-Max-Age"] == "3200"
    assert "Authorization" in response.headers["access-control-allow-headers"]


def test_validate_invalid_token():
    url = "/workspace/workspace/current"
    signer = itsdangerous.Signer("badsecret")
    token = create_raw_token(
        dict(
            url=urljoin(client.base_url, "/workspace/workspace"),
            user="user",
            expiry=datetime.now(timezone.utc) + timedelta(hours=1),
            scope="view",
        ),
        signer=signer,
    )

    # we can not easily call validate() directly, as fastapi's Request object
    # is very much not sans-io, and thus difficult just instantiate.
    response = client.get(url, headers={"Authorization": token})

    assert response.status_code == 403


def test_validate_expired_token():
    url = "/workspace/workspace/current"
    # valid except for expiry
    token = create_raw_token(
        dict(
            url=urljoin(client.base_url, "/workspace/workspace"),
            user="user",
            expiry=datetime.now(timezone.utc) - timedelta(hours=1),
            scope="view",
        )
    )
    response = client.get(url, headers={"Authorization": token})
    assert response.status_code == 401


def test_validate_url():
    headers = auth_headers()
    r1 = client.get("/workspace/workspace/current", headers=headers)
    # this means it was valid, but workspace did not exist
    assert r1.status_code == 404

    # test file url prefix
    r2 = client.get("/workspace/workspace/current/output/file.txt", headers=headers)
    # this means it was valid, but file did not exist
    assert r2.status_code == 404

    r3 = client.get("/workspace/other/current/output/file.txt", headers=headers)
    # the url and token url did not match
    assert r3.status_code == 403


def test_index_api_bad_workspace():
    url = "/workspace/bad/current"
    response = client.get(url, headers=auth_headers())
    assert response.status_code == 403


def test_index_api(workspace):
    workspace.write("output/file1.txt", "test1")
    workspace.write("output/file2.txt", "test2")

    url = "/workspace/workspace/current"
    response = client.get(url, headers=auth_headers())
    assert response.status_code == 200

    assert response.json() == {
        "files": [
            {
                "name": "output/file1.txt",
                "url": "/workspace/workspace/current/output/file1.txt",
                "size": 5,
                "sha256": workspace.get_sha("output/file1.txt"),
                "date": workspace.get_date("output/file1.txt"),
                "user": None,
            },
            {
                "name": "output/file2.txt",
                "url": "/workspace/workspace/current/output/file2.txt",
                "size": 5,
                "sha256": workspace.get_sha("output/file2.txt"),
                "date": workspace.get_date("output/file2.txt"),
                "user": None,
            },
        ]
    }


def test_file_api_not_found(workspace):
    workspace.write("file.txt", "test")
    url = "/workspace/workspace/current/bad.txt"
    response = client.get(url, headers=auth_headers())
    assert response.status_code == 404


def test_file_api(workspace):
    workspace.write("output/file.txt", "test")
    url = "/workspace/workspace/current/output/file.txt"
    response = client.get(url, headers=auth_headers())
    assert response.status_code == 200
    assert response.content == b"test"
    assert (
        response.headers["Content-Security-Policy"]
        == f"frame-src: {config.API_SERVER};"
    )


def test_workspace_release_no_data():
    url = "/workspace/workspace/release"
    response = client.post(url, headers=auth_headers(scope="release"))
    assert response.status_code == 422


def test_workspace_release_workspace_not_exists():
    url = "/workspace/notexists/release"
    response = client.post(
        url,
        json=schema.Release(files={}).dict(),
        headers=auth_headers(scope="release"),
    )
    assert response.status_code == 403


def test_workspace_release_workspace_bad_scope():
    url = "/workspace/workspace/release"
    response = client.post(
        url,
        json=schema.Release(files={}).dict(),
        headers=auth_headers(scope="view"),
    )
    assert response.status_code == 403


def test_workspace_release_workspace_bad_sha(workspace):
    workspace.write("output/file1.txt", "test1")

    release = schema.Release(files={"output/file1.txt": "badhash"})

    url = "/workspace/workspace/release"
    response = client.post(
        url,
        json=release.dict(),
        headers=auth_headers(scope="release"),
    )
    assert response.status_code == 400
    assert response.json()["detail"] == [
        "File output/file1.txt does not match sha of 'badhash'"
    ]


def test_workspace_release_success(workspace, httpx_mock):
    httpx_mock.add_response(
        url=config.API_SERVER + "/api/v2/releases/workspace/workspace",
        method="POST",
        status_code=201,
        headers={"Location": "https://url", "Release-Id": "id"},
    )
    workspace.write("output/file.txt", "test")

    release = schema.Release(
        files={"output/file.txt": workspace.get_sha("output/file.txt")}
    )

    url = "/workspace/workspace/release"
    response = client.post(
        url,
        json=release.dict(),
        headers=auth_headers(scope="release"),
    )

    assert response.status_code == 201


def test_release_index_api_bad_workspace():
    url = "/workspace/bad/release/id"
    response = client.get(url, headers=auth_headers("bad"))
    assert response.status_code == 404


def test_release_index_api_bad_release():
    url = "/workspace/workspace/release/id"
    response = client.get(url, headers=auth_headers())
    assert response.status_code == 404


def test_release_cannot_access_different_workspaces_release(release):
    # check we can access the release normally
    response = client.get(
        f"/workspace/workspace/release/{release.id}", headers=auth_headers()
    )
    assert response.status_code == 200

    WorkspaceFactory("other")
    # allow access to other workspace
    headers = auth_headers("other")
    # use above create to try access release from original workspace
    url = f"/workspace/other/release/{release.id}"
    response = client.get(url, headers=headers)
    assert response.status_code == 404


def test_release_index_api(release):
    release.write("output/file1.txt", "test1")
    release.write("output/file2.txt", "test2")

    url = f"/workspace/workspace/release/{release.id}"
    response = client.get(url, headers=auth_headers())
    assert response.status_code == 200
    assert response.json() == {
        "files": [
            {
                "name": "output/file1.txt",
                "url": f"/workspace/workspace/release/{release.id}/output/file1.txt",
                "size": 5,
                "sha256": release.get_sha("output/file1.txt"),
                "date": release.get_date("output/file1.txt"),
                "user": None,
            },
            {
                "name": "output/file2.txt",
                "url": f"/workspace/workspace/release/{release.id}/output/file2.txt",
                "size": 5,
                "sha256": release.get_sha("output/file2.txt"),
                "date": release.get_date("output/file2.txt"),
                "user": None,
            },
        ]
    }


def test_release_file_api_invalid_token_url():
    url = "/workspace/workspace/release/id/bad.txt"
    response = client.get(url, headers=auth_headers("other"))
    assert response.status_code == 403


def test_release_file_api_workspace_notfound(release):
    release.write("output/file.txt", "test")
    url = f"/workspace/bad/release/{release.id}/output/file.txt"
    response = client.get(url, headers=auth_headers("bad"))
    assert response.status_code == 404


def test_release_file_api_not_found(release):
    url = f"/workspace/workspace/release/{release.id}/bad.txt"
    response = client.get(url, headers=auth_headers())
    assert response.status_code == 404


def test_release_file_api(release):
    release.write("output/file.txt", "test")
    url = f"/workspace/workspace/release/{release.id}/output/file.txt"
    response = client.get(url, headers=auth_headers())
    assert response.status_code == 200
    assert response.content == b"test"
    assert (
        response.headers["Content-Security-Policy"]
        == f"frame-src: {config.API_SERVER};"
    )
