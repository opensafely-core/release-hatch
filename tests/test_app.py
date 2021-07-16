import hashlib

from fastapi.testclient import TestClient

from hatch import app


client = TestClient(app.app)


def test_index_api_bad_workspace():
    response = client.get("/workspace/bad")
    assert response.status_code == 404


def test_index_api(workspace):
    workspace.write("output/file1.txt", "test1")
    workspace.write("output/file2.txt", "test2")

    response = client.get("/workspace/workspace")
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
    assert client.get("/workspace/bad/file.txt").status_code == 404
    assert client.get("/workspace/workspace/bad.txt").status_code == 404


def test_file_api(workspace):
    workspace.write("output/file.txt", "test")
    response = client.get("/workspace/workspace/output/file.txt")
    assert response.status_code == 200
    assert response.content == b"test"
