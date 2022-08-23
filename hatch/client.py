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

from hatch import app, config, schema, signing


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
    args.workspace = secrets.token_hex(8)
    token = get_token(args)

    exit_code = 0
    for error in run_test(args.workspace, token):
        print(error)
        exit_code += 1

    sys.exit(exit_code)


def request_cmd(args):  # pragma: no cover
    token = get_token(args)
    index = fetch_index(token, args.workspace)
    files = {f["name"]: f for f in index["files"]}

    filelist = schema.FileList(files=[])
    if args.metadata:
        filelist.metadata = {"comment": args.metadata}

    for arg in args.files:
        p, _, metadata = arg.partition(":")
        filedata = files.get(p)
        if filedata is None:
            sys.exit(f"{p} does not exist")

        obj = schema.FileMetadata(**filedata)
        if metadata:
            obj.metadata = {"comment": metadata}

        filelist.files.append(obj)

    path = app.app.url_path_for("workspace_release", workspace=args.workspace)
    url = path.make_absolute_url(base_url=config.RELEASE_HOST)
    response = requests.post(
        url,
        data=filelist.json(),
        headers={"Authorization": token},
    )

    print(response)
    print(response.headers)
    print(response.text)


def main(argv):
    parser = argparse.ArgumentParser()

    def show_help(*args, **kwargs):  # pragma: no cover
        parser.print_help()
        parser.exit()

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

    # a holder for shared arguments for each subcommand
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--workspace", "-w", help="workspace name")
    shared.add_argument(
        "--release",
        "-r",
        dest="release_id",
        help="release to use",
    )

    subparsers = parser.add_subparsers(
        title="available commands", dest="command", description="", metavar="COMMAND"
    )

    token_parser = subparsers.add_parser(
        "token",
        help="generate a token to use manually",
        parents=[shared],
    )
    token_parser.set_defaults(function=token_cmd)

    index_parser = subparsers.add_parser(
        "list",
        help="list the files for a workspace or release",
        parents=[shared],
    )
    index_parser.set_defaults(function=index_cmd)

    file_parser = subparsers.add_parser(
        "file",
        help="download a file from workspace or release",
        parents=[shared],
    )
    file_parser.set_defaults(function=file_cmd)
    file_parser.add_argument(
        "--file",
        "-f",
        required=True,
        help="file name to download",
    )

    test_parser = subparsers.add_parser(
        "test",
        help="run a functional test against a local release-hatch",
    )
    test_parser.set_defaults(function=test_cmd)

    request_parser = subparsers.add_parser(
        "request",
        help="request some files be release",
        parents=[shared],
    )
    request_parser.add_argument(
        "files",
        nargs="+",
        help="files to release path[:metadata]",
    )
    request_parser.add_argument(
        "--metadata",
        "-m",
        help="request metadata",
    )
    request_parser.set_defaults(function=request_cmd)

    args = parser.parse_args(argv)
    return args.function(args)


if __name__ == "__main__":  # pragma: no cover
    main(sys.argv[1:])
