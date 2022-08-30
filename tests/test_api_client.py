import json
import logging

import httpx
import pytest
from fastapi import HTTPException

from hatch import api_client, config, models, schema


def test_create_release(httpx_mock, workspace):
    httpx_mock.add_response(
        url=config.JOB_SERVER_ENDPOINT + "/releases/workspace/workspace",
        method="POST",
        status_code=201,
        headers={
            "Location": "https://url",
            "Release-Id": "id",
            "Connection": "close",
            "Server": "server",
            "Content-Length": "100",
            "Content-Type": "application/json",
        },
    )

    workspace.write("output/file1.txt", "test1")
    filelist = models.get_index(workspace.path)
    filelist.files[0].metadata = {"test": "test"}
    filelist.metadata = {"foo": "bar"}

    response = api_client.create_release("workspace", filelist, "user")

    assert response.headers["Location"] == "https://url"
    assert response.headers["Release-Id"] == "id"
    assert "Connection" not in response.headers
    assert "Server" not in response.headers

    request = httpx_mock.get_request()
    assert request.headers["OS-User"] == "user"
    assert request.headers["Authorization"] == config.JOB_SERVER_TOKEN
    assert json.loads(request.read()) == {
        "files": [
            {
                "name": "output/file1.txt",
                "url": None,
                "size": 5,
                "sha256": workspace.get_sha("output/file1.txt"),
                "date": workspace.get_date("output/file1.txt"),
                "metadata": {"test": "test"},
                "review": None,
            },
        ],
        "metadata": {"foo": "bar"},
        "review": None,
    }


def test_create_release_error(httpx_mock):
    httpx_mock.add_response(
        url=config.JOB_SERVER_ENDPOINT + "/releases/workspace/workspace",
        method="POST",
        status_code=400,
        json={"detail": "error"},
        headers={
            "Some-Header": "value",
            "Connection": "close",
            "Server": "server",
            "Content-Length": "100",
            "Content-Type": "application/json",
        },
    )

    filelist = schema.FileList(files=[])

    with pytest.raises(HTTPException) as exc_info:
        api_client.create_release("workspace", filelist, "user")

    response = exc_info.value
    assert response.headers["Some-header"] == "value"
    assert response.detail == {"detail": "error"}
    assert "Connection" not in response.headers
    assert "Server" not in response.headers


def test_upload_file(httpx_mock, tmp_path):
    httpx_mock.add_response(
        url=config.JOB_SERVER_ENDPOINT + "/releases/release/release_id",
        method="POST",
        status_code=201,
        headers={
            "Location": "https://url",
            "File-Id": "file-id",
            "Content-Length": "100",
            "Content-Type": "application/json",
        },
    )

    path = tmp_path / "output/file.txt"
    path.parent.mkdir()
    path.write_text("test")
    response = api_client.upload_file("release_id", "output/file.txt", path, "user")

    assert response.headers["Location"] == "https://url"
    assert response.headers["File-Id"] == "file-id"

    request = httpx_mock.get_request()
    assert request.headers["OS-User"] == "user"
    assert request.headers["Authorization"] == config.JOB_SERVER_TOKEN
    assert (
        request.headers["Content-Disposition"]
        == 'attachment; filename="output/file.txt"'
    )
    assert request.read() == b"test"


def test_upload_file_error(httpx_mock, tmp_path):
    httpx_mock.add_response(
        url=config.JOB_SERVER_ENDPOINT + "/releases/release/release_id",
        method="POST",
        status_code=400,
        json={"detail": "error"},
    )

    path = tmp_path / "output/file.txt"
    path.parent.mkdir()
    path.write_text("test")

    with pytest.raises(HTTPException) as exc_info:
        api_client.upload_file("release_id", "output/file.txt", path, "user")

    response = exc_info.value
    assert response.detail == {"detail": "error"}


def test_upload_review_error(httpx_mock, release):
    httpx_mock.add_response(
        url=config.JOB_SERVER_ENDPOINT + "/releases/release/release_id/reviews",
        method="POST",
        status_code=400,
        json={"detail": "error"},
    )

    release.write("output/file1.txt", "test1")
    filelist = models.get_index(release.path)

    with pytest.raises(HTTPException) as exc_info:
        api_client.upload_review("release_id", filelist, "user")

    response = exc_info.value
    assert response.detail == {"detail": "error"}


def test_proxy_httpx_error_bad_json():
    response = httpx.Response(
        status_code=400,
        content="]{",
    )
    exc = api_client.proxy_httpx_error(response)
    assert exc.status_code == 400
    assert exc.detail == "]{"


def test_client_logs_message(httpx_mock, caplog):
    caplog.set_level(logging.DEBUG)
    # no headers
    url = "http://test.com/path"
    httpx_mock.add_response(url=url, method="POST", status_code=200)

    api_client.client.post(url)

    assert caplog.records[-1].msg == f"POST {url}: status=200 "

    httpx_mock.add_response(
        url=url,
        method="POST",
        status_code=200,
        headers={
            "Content-Length": "10",
            "Content-Type": "application/json",
        },
    )

    api_client.client.post(url)

    assert (
        caplog.records[-1].msg
        == f"POST {url}: status=200 size=10 type=application/json"
    )
