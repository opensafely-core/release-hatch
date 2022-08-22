import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

from fastapi.testclient import TestClient

from hatch import app, config, models, schema, signing
from tests.factories import WorkspaceFactory
from tests.test_signing import create_raw_token


client = TestClient(app.app)


def auth_token(path, user="user", expiry=None, base_url=None):
    if expiry is None:  # pragma: no cover
        expiry = datetime.now(timezone.utc) + timedelta(hours=1)
    if base_url is None:
        base_url = client.base_url

    return signing.AuthToken(
        url=urljoin(base_url, path),
        user=user,
        expiry=expiry,
    )


def auth_headers(workspace="workspace", user="user", expiry=None, base_url=None):
    """Helper to create valid authentication headers for a specific workspace"""
    token = auth_token(f"/workspace/{workspace}", user, expiry, base_url)
    return {"Authorization": token.sign(config.JOB_SERVER_TOKEN, "hatch")}


def test_cors():
    response = client.options(
        "/workspace/workspace/current",
        headers={
            "Origin": config.SPA_ORIGIN,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers["Access-Control-Allow-Methods"] == "GET, HEAD, POST"
    assert response.headers["Access-Control-Allow-Origin"] == config.SPA_ORIGIN
    assert response.headers["Access-Control-Max-Age"] == "3200"
    assert "Authorization" in response.headers["access-control-allow-headers"]


def test_validate_invalid_token_secret():
    url = "/workspace/workspace/current"
    token = create_raw_token(
        dict(
            url=urljoin(client.base_url, "/workspace/workspace"),
            user="user",
            expiry=datetime.now(timezone.utc) + timedelta(hours=1),
        ),
        "bad secret" * 10,
    )

    # we can not easily call validate() directly, as fastapi's Request object
    # is very much not sans-io, and thus difficult just instantiate.
    response = client.get(url, headers={"Authorization": token})

    assert response.status_code == 403


def test_validate_invalid_token_values():
    url = "/workspace/workspace/current"
    token = create_raw_token(
        dict(
            url="bad url",
            user="user",
            expiry=datetime.now(timezone.utc) + timedelta(hours=1),
        ),
        config.JOB_SERVER_TOKEN,
        salt="hatch",
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
        ),
        key=config.JOB_SERVER_TOKEN,
        salt="hatch",
    )
    response = client.get(url, headers={"Authorization": token})
    assert response.status_code == 401


def test_validate_url(caplog):
    caplog.set_level(logging.DEBUG)
    headers = auth_headers()
    r1 = client.get("/workspace/workspace/current", headers=headers)
    # this means it was valid, but workspace did not exist
    assert r1.status_code == 404

    # test file url prefix
    r2 = client.get("/workspace/workspace/current/file.txt", headers=headers)
    # this means it was valid, but file did not exist
    assert r2.status_code == 404

    invalid_host = auth_headers(base_url="https://invalid.com/")
    r3 = client.get("/workspace/workspace/current/file.txt", headers=invalid_host)
    # the token hostname did not match
    assert r3.status_code == 403
    assert (
        caplog.records[-1].msg
        == "Host invalid.com from 'https://invalid.com/workspace/workspace' did not match any of ('testserver', 'localhost')"
    )

    localhost = auth_headers(base_url="https://localhost/")
    r4 = client.get("/workspace/workspace/current/file.txt", headers=localhost)
    # this means it was valid, but file did not exist
    assert r4.status_code == 404

    r5 = client.get("/workspace/invalid/current/file.txt", headers=headers)
    # the url and token url did not match
    assert r5.status_code == 403
    assert (
        caplog.records[-1].msg
        == "Request path /workspace/invalid/current/file.txt does not match token path /workspace/workspace"
    )


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
                "url": "http://testserver/workspace/workspace/current/output/file1.txt",
                "size": 5,
                "sha256": workspace.get_sha("output/file1.txt"),
                "date": workspace.get_date("output/file1.txt"),
                "metadata": None,
                "review": None,
            },
            {
                "name": "output/file2.txt",
                "url": "http://testserver/workspace/workspace/current/output/file2.txt",
                "size": 5,
                "sha256": workspace.get_sha("output/file2.txt"),
                "date": workspace.get_date("output/file2.txt"),
                "metadata": None,
                "review": None,
            },
        ],
        "metadata": None,
        "review": None,
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
        == f"frame-src: {config.SPA_ORIGIN};"
    )


def test_workspace_release_no_data():
    url = "/workspace/workspace/release"
    response = client.post(url, headers=auth_headers())
    assert response.status_code == 422


def test_workspace_release_workspace_not_exists():
    url = "/workspace/notexists/release"
    response = client.post(
        url,
        json=schema.Release(files={}).dict(),
        headers=auth_headers(),
    )
    assert response.status_code == 403


def test_workspace_release_workspace_bad_sha_osrelease(workspace):
    workspace.write("output/file1.txt", "test1")

    release = schema.Release(files={"output/file1.txt": "badhash"})

    url = "/workspace/workspace/release"
    response = client.post(
        url,
        data=release.json(),
        headers=auth_headers(),
    )
    assert response.status_code == 400
    error = response.json()["detail"][0]
    assert "output/file1.txt" in error
    assert "badhash" in error


def test_workspace_release_workspace_bad_sha_spa(workspace):
    workspace.write("output/file1.txt", "test1")

    filelist = models.get_index(workspace.path)
    filelist.files[0].sha256 = "badhash"

    url = "/workspace/workspace/release"
    response = client.post(
        url,
        data=filelist.json(),
        headers=auth_headers(),
    )
    assert response.status_code == 400
    error = response.json()["detail"][0]
    assert "output/file1.txt" in error
    assert "badhash" in error


def test_workspace_release_success_osrelease(workspace, httpx_mock):
    httpx_mock.add_response(
        url=config.JOB_SERVER_ENDPOINT + "/releases/workspace/workspace",
        method="POST",
        status_code=201,
        headers={
            "Location": "https://url",
            "Release-Id": "id",
            "Content-Length": "100",
            "Content-Type": "application/json",
        },
    )
    workspace.write("output/file.txt", "test")

    release = schema.Release(
        files={"output/file.txt": workspace.get_sha("output/file.txt")}
    )

    url = "/workspace/workspace/release"
    response = client.post(
        url,
        json=release.dict(),
        headers=auth_headers(),
    )

    assert response.status_code == 201
    assert response.headers["Location"].endswith("/workspace/workspace/release/id")


def test_workspace_release_success_spa(workspace, httpx_mock):
    httpx_mock.add_response(
        url=config.JOB_SERVER_ENDPOINT + "/releases/workspace/workspace",
        method="POST",
        status_code=201,
        headers={
            "Location": "https://url",
            "Release-Id": "id",
            "Content-Length": "100",
            "Content-Type": "application/json",
        },
    )
    workspace.write("output/file.txt", "test")

    filelist = models.get_index(workspace.path)
    filelist.metadata = {"foo": "bar"}

    url = "/workspace/workspace/release"
    response = client.post(
        url,
        data=filelist.json(),
        headers=auth_headers(),
    )

    assert response.status_code == 201
    assert response.headers["Location"].endswith("/workspace/workspace/release/id")


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
                "url": f"http://testserver/workspace/workspace/release/{release.id}/output/file1.txt",
                "size": 5,
                "sha256": release.get_sha("output/file1.txt"),
                "date": release.get_date("output/file1.txt"),
                "metadata": None,
                "review": None,
            },
            {
                "name": "output/file2.txt",
                "url": f"http://testserver/workspace/workspace/release/{release.id}/output/file2.txt",
                "size": 5,
                "sha256": release.get_sha("output/file2.txt"),
                "date": release.get_date("output/file2.txt"),
                "metadata": None,
                "review": None,
            },
        ],
        "metadata": None,
        "review": None,
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
        == f"frame-src: {config.JOB_SERVER_ENDPOINT};"
    )


def test_release_file_upload_bad_workspace(release):
    release.write("output/file.txt", "test")
    url = f"/workspace/other/release/{release.id}"
    name = schema.ReleaseFile(name="output/file.txt")
    response = client.post(url, data=name.json(), headers=auth_headers("other"))
    assert response.status_code == 404


def test_release_file_upload_bad_release(release):
    release.write("output/file.txt", "test")
    url = "/workspace/workspace/release/badid"
    name = schema.ReleaseFile(name="output/file.txt")
    response = client.post(url, data=name.json(), headers=auth_headers())
    assert response.status_code == 404


def test_release_file_upload_bad_file(release):
    release.write("output/file.txt", "test")
    url = f"/workspace/workspace/release/{release.id}"
    name = schema.ReleaseFile(name="output/bad.txt")
    response = client.post(url, data=name.json(), headers=auth_headers())
    assert response.status_code == 404


def test_release_file_upload(release, httpx_mock):
    httpx_mock.add_response(
        url=config.JOB_SERVER_ENDPOINT + f"/releases/release/{release.id}",
        method="POST",
        status_code=201,
        headers={
            "Location": "https://url",
            "File-Id": "id",
            "Content-Length": "100",
            "Content-Type": "application/json",
        },
    )
    release.write("output/file.txt", "test")

    url = f"/workspace/workspace/release/{release.id}"
    name = schema.ReleaseFile(name="output/file.txt")
    response = client.post(
        url,
        data=name.json(),
        headers=auth_headers(),
    )

    assert response.status_code == 201


def test_release_review_invalid_json(release):
    release.write("output/file1.txt", "test1")
    release.write("output/file2.txt", "test2")

    filelist = models.get_index(release.path)

    filelist.files[0].review = schema.FileReview(
        status=schema.ReviewStatus.REJECTED,
        comments={},
    )

    response = client.post(
        url=f"/workspace/workspace/{release.id}/reviews",
        data=filelist.json(),
        headers=auth_headers(),
    )

    assert response.status_code == 400
    errors = response.json()["detail"]
    assert "output/file1.txt" in errors[0]
    assert "output/file2.txt" in errors[1]


def test_release_review_invalid_sha(release):
    release.write("output/file1.txt", "test1")
    filelist = models.get_index(release.path)

    filelist.files[0].sha256 = "badsha"
    response = client.post(
        url=f"/workspace/workspace/{release.id}/reviews",
        data=filelist.json(),
        headers=auth_headers(),
    )

    assert response.status_code == 400
    errors = response.json()["detail"]
    assert "badsha" in errors[0]


def test_release_review_valid(release, httpx_mock):
    httpx_mock.add_response(
        url=config.JOB_SERVER_ENDPOINT + f"/releases/release/{release.id}/reviews",
        method="POST",
        status_code=200,
        headers={
            "Content-Length": "100",
            "Content-Type": "application/json",
        },
    )
    release.write("output/file1.txt", "test1")

    filelist = models.get_index(release.path)

    filelist.files[0].review = schema.FileReview(
        status=schema.ReviewStatus.APPROVED,
        comments={"foo": "bar"},
    )

    response = client.post(
        url=f"/workspace/workspace/{release.id}/reviews",
        data=filelist.json(),
        headers=auth_headers(),
    )

    assert response.status_code == 200
