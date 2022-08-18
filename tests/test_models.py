import hashlib
import time
from datetime import datetime
from pathlib import Path

import pytest
from fastapi import HTTPException

from hatch import config, models, schema


def test_get_sha_caches_sha(workspace):
    f = workspace.write("file.txt", "test")

    sha = models.get_sha(f)

    expected_sha = hashlib.sha256(b"test").hexdigest()
    assert sha == expected_sha
    assert (config.CACHE / "workspace/file.txt").read_text() == expected_sha


def test_get_sha_uses_cached_sha(workspace):
    f = workspace.write("file.txt", "test")

    time.sleep(0.01)

    c = config.CACHE / "workspace/file.txt"
    c.parent.mkdir()
    c.write_text("cached")

    sha = models.get_sha(f)

    assert sha == "cached"


def test_get_sha_stale_cache(workspace):
    c = config.CACHE / "workspace/file.txt"
    c.parent.mkdir()
    c.write_text("cached")

    time.sleep(0.01)

    f = workspace.write("file.txt", "test")

    sha = models.get_sha(f)

    # it should use actual hash an update file
    expected_sha = hashlib.sha256(b"test").hexdigest()
    assert sha == expected_sha
    assert (config.CACHE / "workspace/file.txt").read_text() == expected_sha


def test_get_files(workspace):
    workspace.write("output/file.txt", "test")
    # all these should be ignored
    workspace.write("metadata/manifest.json", "test")
    workspace.write("releases/id/file.txt", "test")
    workspace.write(".git/config", "test")
    workspace.write("output/.hidden", "test")

    assert models.get_files(workspace.path) == [Path("output/file.txt")]


def test_get_index(workspace):
    workspace.write("output/file1.txt", "test1")
    workspace.write("output/file2.txt", "test2")

    def url_builder(filename):
        return f"https://release/test/{filename}"

    index = models.get_index(workspace.path, url_builder).dict()

    assert index == {
        "files": [
            {
                "name": "output/file1.txt",
                "url": "https://release/test/output/file1.txt",
                "size": 5,
                "sha256": workspace.get_sha("output/file1.txt"),
                "date": workspace.get_date("output/file1.txt", iso=False),
                "metadata": None,
            },
            {
                "name": "output/file2.txt",
                "url": "https://release/test/output/file2.txt",
                "size": 5,
                "sha256": workspace.get_sha("output/file2.txt"),
                "date": workspace.get_date("output/file2.txt", iso=False),
                "metadata": None,
            },
        ],
        "metadata": None,
    }


def test_validate_release_files_errors_osrelease(workspace):
    workspace.write("output/file.txt", "test")

    release = schema.Release(
        files={
            "badfile": workspace.get_sha("output/file.txt"),
            "output/file.txt": "badsha",
        }
    )
    assert models.validate_release_files("workspace", workspace.path, release) == [
        "File badfile not found in workspace workspace",
        "File output/file.txt does not match sha of 'badsha'",
    ]


def test_validate_release_files_errors_spa(workspace):
    workspace.write("output/file.txt", "test")

    filelist = models.get_index(workspace.path)
    filelist.files[0].sha256 = "badsha"
    # add missing file
    filelist.files.append(
        schema.FileMetadata(
            name="badfile",
            sha256="foo",
            size=0,
            date=datetime.utcnow(),
        )
    )

    assert models.validate_release_files("workspace", workspace.path, filelist) == [
        "File output/file.txt does not match sha of 'badsha'",
        "File badfile not found in workspace workspace",
    ]


def test_validate_release_files_valid_osrelease(workspace):
    workspace.write("output/file.txt", "test")

    release = schema.Release(
        files={"output/file.txt": workspace.get_sha("output/file.txt")}
    )
    assert models.validate_release_files("workspace", workspace.path, release) == []


def test_validate_release_files_valid_spa(workspace):
    workspace.write("output/file.txt", "test")

    filelist = models.get_index(workspace.path)
    assert models.validate_release_files("workspace", workspace.path, filelist) == []


def test_create_release(workspace, httpx_mock):
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

    response = models.create_release("workspace", workspace.path, release, "user")
    assert response.headers["Location"] == "https://url"
    release_id = response.headers["Release-Id"]
    assert release_id == "id"

    release_dir = workspace.path / "releases" / release_id
    assert release_dir.exists()

    for f in models.get_files(release_dir):
        copy = release_dir / f
        orig = workspace.path / f
        assert models.get_sha(copy) == models.get_sha(orig)


def test_create_release_error(workspace, httpx_mock):
    httpx_mock.add_response(
        url=config.JOB_SERVER_ENDPOINT + "/releases/workspace/workspace",
        method="POST",
        status_code=400,
        json={"detail": "error"},
    )

    workspace.write("output/file.txt", "test")

    release = schema.Release(
        files={"output/file.txt": hashlib.sha256(b"test").hexdigest()}
    )

    with pytest.raises(HTTPException) as exc_info:
        models.create_release("workspace", workspace.path, release, "user")

    response = exc_info.value
    assert response.detail == "error"
