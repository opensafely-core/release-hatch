from pathlib import Path

from hatch.schema import ReleaseFile


def test_release_file_paths():
    assert ReleaseFile(name="a/b/c").name == "a/b/c"
    assert ReleaseFile(name=r"a\b\c").name == "a/b/c"
    assert ReleaseFile(name=Path("a/b/c")).name == "a/b/c"
    assert ReleaseFile(name=Path(r"a\b\c")).name == "a/b/c"
