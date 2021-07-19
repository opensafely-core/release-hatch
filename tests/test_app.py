import hashlib

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from hatch import app


client = TestClient(app.app)


def test_validate_raises_with_bad_secret():
    with pytest.raises(HTTPException):
        app.validate("bad")


def test_validate_succeeds():
    assert app.validate("secret") is None


def test_index_api_bad_workspace():
    response = client.get("/workspace/bad", headers={"Authorization": "secret"})
    assert response.status_code == 404


def test_index_api(workspace):
    workspace.write("output/file1.txt", "test1")
    workspace.write("output/file2.txt", "test2")

    response = client.get("/workspace/workspace", headers={"Authorization": "secret"})
    assert response.status_code == 200

    assert response.json() == {
        "files": [
            {
                "name": "output/file1.txt",
                "url": "/workspace/workspace/output/file1.txt",
                "size": 5,
                "sha256": hashlib.sha256(b"test1").hexdigest(),
            },
            {
                "name": "output/file2.txt",
                "url": "/workspace/workspace/output/file2.txt",
                "size": 5,
                "sha256": hashlib.sha256(b"test2").hexdigest(),
            },
        ]
    }


def test_file_api_not_found(workspace):
    workspace.write("file.txt", "test")
    r1 = client.get("/workspace/bad/file.txt", headers={"Authorization": "secret"})
    assert r1.status_code == 404
    r2 = client.get("/workspace/workspace/bad.txt", headers={"Authorization": "secret"})
    assert r2.status_code == 404


def test_file_api(workspace):
    workspace.write("output/file.txt", "test")
    response = client.get(
        "/workspace/workspace/output/file.txt", headers={"Authorization": "secret"}
    )
    assert response.status_code == 200
    assert response.content == b"test"
