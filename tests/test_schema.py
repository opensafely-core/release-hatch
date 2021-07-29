from pathlib import Path

from hatch.schema import UrlFileName


def test_filename():
    UrlFileName("a/b/c") == "a/b/c"
    UrlFileName(r"a\b\c") == "a/b/c"
    UrlFileName(Path("a/b/c")) == "a/b/c"
    UrlFileName(Path(r"a\b\c")) == "a/b/c"
