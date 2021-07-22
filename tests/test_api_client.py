import json

import httpx
import pytest
from fastapi import HTTPException

from hatch import api_client, config, schema


def test_create_release(httpx_mock):
    httpx_mock.add_response(
        url=config.API_SERVER + "/api/v2/releases/workspace/workspace",
        method="POST",
        status_code=201,
        headers={
            "Location": "https://url",
            "Release-Id": "id",
            "Connection": "close",
            "Server": "server",
        },
    )

    release = schema.Release(files={"file.txt": "sha"})

    response = api_client.create_release("workspace", release, "user")

    assert response.headers["Location"] == "https://url"
    assert response.headers["Release-Id"] == "id"
    assert "Connection" not in response.headers
    assert "Server" not in response.headers

    request = httpx_mock.get_request()
    assert request.headers["OS-User"] == "user"
    assert request.headers["Authorization"] == config.BACKEND_TOKEN
    assert json.loads(request.read()) == {"files": {"file.txt": "sha"}}


def test_create_release_error(httpx_mock):
    httpx_mock.add_response(
        url=config.API_SERVER + "/api/v2/releases/workspace/workspace",
        method="POST",
        status_code=400,
        json={"detail": "error"},
        headers={
            "Some-Header": "value",
            "Connection": "close",
            "Server": "server",
        },
    )

    release = schema.Release(files={"file.txt": "sha"})

    with pytest.raises(HTTPException) as exc_info:
        api_client.create_release("workspace", release, "user")

    response = exc_info.value
    assert response.headers["Some-header"] == "value"
    assert response.detail == "error"
    assert "Connection" not in response.headers
    assert "Server" not in response.headers


def test_upload_file(httpx_mock, tmp_path):
    httpx_mock.add_response(
        url=config.API_SERVER + "/api/v2/releases/release/release_id",
        method="POST",
        status_code=201,
        headers={
            "Location": "https://url",
            "File-Id": "file-id",
        },
    )

    path = tmp_path / "file.txt"
    path.write_text("test")
    response = api_client.upload_file("release_id", "file.txt", path, "user")

    assert response.headers["Location"] == "https://url"
    assert response.headers["File-Id"] == "file-id"

    request = httpx_mock.get_request()
    assert request.headers["OS-User"] == "user"
    assert request.headers["Authorization"] == config.BACKEND_TOKEN
    assert request.headers["Content-Disposition"] == "attachment; filename=file.txt"
    assert request.read() == b"test"


def test_upload_file_error(httpx_mock, tmp_path):
    httpx_mock.add_response(
        url=config.API_SERVER + "/api/v2/releases/release/release_id",
        method="POST",
        status_code=400,
        json={"detail": "error"},
    )

    path = tmp_path / "file.txt"
    path.write_text("test")

    with pytest.raises(HTTPException) as exc_info:
        api_client.upload_file("release_id", "file.txt", path, "user")

    response = exc_info.value
    assert response.detail == "error"


def test_proxy_httpx_error_bad_json(httpx_mock):
    response = httpx.Response(
        status_code=400,
        json={},
    )
    exc = api_client.proxy_httpx_error(response)
    assert exc.status_code == 400
    assert exc.detail == b"{}"
