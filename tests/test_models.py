import hashlib
import time

from hatch import models


def test_get_sha_caches_sha(workspace):
    f = workspace.write("file.txt", "test")

    sha = models.get_sha(f)

    expected_sha = hashlib.sha256(b"test").hexdigest()
    assert sha == expected_sha
    assert (workspace.cache / "workspace/file.txt").read_text() == expected_sha


def test_get_sha_uses_cached_sha(workspace):
    f = workspace.write("file.txt", "test")

    time.sleep(0.01)

    c = workspace.cache / "workspace/file.txt"
    c.parent.mkdir()
    c.write_text("cached")

    sha = models.get_sha(f)

    assert sha == "cached"


def test_get_sha_stale_cache(workspace):
    c = workspace.cache / "workspace/file.txt"
    c.parent.mkdir()
    c.write_text("cached")

    time.sleep(0.01)

    f = workspace.write("file.txt", "test")

    sha = models.get_sha(f)

    # it should use actual hash an update file
    expected_sha = hashlib.sha256(b"test").hexdigest()
    assert sha == expected_sha
    assert (workspace.cache / "workspace/file.txt").read_text() == expected_sha


def test_filemetadata_from_path(workspace):
    workspace.write("output/file.txt", "test")
    meta = models.FileMetadata.from_path(workspace.path, "output/file.txt", "/url/")

    assert meta.name == "output/file.txt"
    assert meta.url == "/url/output/file.txt"
    assert meta.size == 4
    assert meta.sha256 == hashlib.sha256(b"test").hexdigest()


def test_fileindex_from_dir(workspace):
    workspace.write("output/file1.txt", "test1")
    workspace.write("output/file2.txt", "test2")

    index = models.FilesIndex.from_dir(workspace.path, "/url/")

    assert index.files[0].name == "output/file1.txt"
    assert index.files[0].url == "/url/output/file1.txt"
    assert index.files[0].size == 5
    assert index.files[0].sha256 == hashlib.sha256(b"test1").hexdigest()
    assert index.files[1].name == "output/file2.txt"
    assert index.files[1].url == "/url/output/file2.txt"
    assert index.files[1].size == 5
    assert index.files[1].sha256 == hashlib.sha256(b"test2").hexdigest()
