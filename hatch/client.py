#!/usr/bin/env python3
import argparse
import getpass
import json
import secrets
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests

from hatch import app, config, signing


def generate_token(workspace, user, duration):
    """Generate and sign and auth token."""
    url = urljoin(config.RELEASE_HOST, f"/workspace/{workspace}")
    expiry = datetime.now(timezone.utc) + timedelta(minutes=duration)
    token = signing.AuthToken(url=url, user=user, expiry=expiry)
    return token.sign(config.JOB_SERVER_TOKEN, salt="hatch")


def get_token(args):
    return generate_token(args.workspace, args.user, args.duration)


def fetch_index(token, workspace, release_id=None):
    """Fetch the index."""
    headers = {"Authorization": token}
    kwargs = {"workspace": workspace}
    if release_id:
        view_name = "release_index"
        kwargs["release_id"] = release_id
    else:
        view_name = "workspace_index"

    # generate url
    path = app.app.url_path_for(view_name, **kwargs)
    url = path.make_absolute_url(base_url=config.RELEASE_HOST)

    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()


def run_test(workspace, token):
    """Run an integration tests against a running local server."""
    files = {
        "output/file1.csv": "csv",
        "output/file2.png": "png",
        "output/file3.html": "html",
    }

    path = Path(config.WORKSPACES) / workspace
    path.mkdir()

    try:
        yield from test_index_api(path, files, workspace, token)
    finally:
        shutil.rmtree(path)


def test_index_api(path, files, workspace, token):
    """Create a test workspace and release, and make sure the index APIs work."""
    for name, content in files.items():
        print(f"Creating file {name} in workspace {workspace}")
        filepath = path / name
        filepath.parent.mkdir(exist_ok=True, parents=True)
        filepath.write_text(content)

    index = fetch_index(token, workspace)
    print("Index:")
    print(json.dumps(index, indent=2))

    yield from check_files(index, files, token)

    release_id = secrets.token_hex(8)
    release_dir = path / "releases" / release_id
    # copy across release files
    for name in files:
        release_path = release_dir / name
        release_path.parent.mkdir(exist_ok=True, parents=True)
        release_path.write_bytes((path / name).read_bytes())
        (release_dir / name).write_bytes((path / name).read_bytes())

    release_index = fetch_index(token, workspace, release_id)
    print("Release Index:")
    print(json.dumps(release_index, indent=2))

    yield from check_files(release_index, files, token)


def check_files(index, files, token):
    index_files = {f["name"]: f for f in index["files"]}
    if index_files.keys() != files.keys():  # pragma: no cover
        err = f"File list {list(index_files)} did not match expected {list(files)}"
        yield err

    for name, content in files.items():
        try:
            metadata = index_files[name]
            resp = requests.get(metadata["url"], headers={"Authorization": token})
            resp.raise_for_status()
            assert (
                resp.text == content
            ), f"{resp.text} does not match expected {content}: {resp.text}"
            print(f"File {name}: OK")
        except KeyError:  # pragma: no cover
            yield f"File {name}: not found in index"
        except Exception as exc:  # pragma: no cover
            yield f"File {name}: {exc}"


def token_cmd(args):
    """Just print a token."""
    print(get_token(args))


def index_cmd(args):
    """Show the API index for a workspace or release."""
    token = get_token(args)
    index = fetch_index(token, args.workspace, args.release_id)
    print(json.dumps(index, indent=2))


def file_cmd(args):
    """Download file from server."""
    if not args.file:
        sys.exit("File command need --file argument")
    token = get_token(args)
    index = fetch_index(token, args.workspace, args.release_id)
    files_dict = {f["name"]: f for f in index["files"]}

    metadata = files_dict.get(args.file)
    if metadata is None:  # pragma: no cover
        sys.exit(f"File {args.file} not found.\n{json.dumps(index, indent=2)}")
    else:
        print("Metadata:")
        print(json.dumps(metadata, indent=2))
        print()

    resp = requests.get(metadata["url"], headers={"Authorization": token})
    resp.raise_for_status()
    print("Content:")
    print(resp.text)


def test_cmd(args):  # pragma: no cover
    """Run simple integration test aginst running server"""
    if not args.workspace:
        args.workspace = secrets.token_hex(8)
    token = get_token(args)

    exit_code = 0
    for error in run_test(args.workspace, token):
        print(error)
        exit_code += 1

    sys.exit(exit_code)


cmds = {
    "token": token_cmd,
    "index": index_cmd,
    "file": file_cmd,
    "test": test_cmd,
}


def main(argv):
    parser = argparse.ArgumentParser()

    parser.add_argument("command", help="command to run", choices=cmds)
    parser.add_argument(
        "--workspace",
        "-w",
        help="workspace name",
    )
    parser.add_argument(
        "--user",
        "-u",
        default=getpass.getuser(),
        help="user (default: $USER)",
    )
    parser.add_argument(
        "--duration",
        "-d",
        default=60,
        help="how many minutes is the token valid for",
    )
    parser.add_argument(
        "--release",
        "-r",
        dest="release_id",
        help="release id to index or download file fome",
    )
    parser.add_argument(
        "--file",
        "-f",
        help="file to download (only for 'file' command)",
    )
    args = parser.parse_args(argv)

    return cmds[args.command](args)


if __name__ == "__main__":  # pragma: no cover
    main(sys.argv[1:])
