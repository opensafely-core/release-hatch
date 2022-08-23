import os
import secrets
import select
import subprocess

import pytest

from hatch import config
from hatch.client import generate_token, main, run_test


@pytest.fixture
def test_cli_env(monkeypatch):
    test_host = "http://localhost:18001"
    monkeypatch.setattr(config, "RELEASE_HOST", test_host)

    # setup environment with the modified values for this test
    env = os.environ.copy()
    env["RELEASE_HOST"] = test_host
    env["WORKSPACES"] = config.WORKSPACES
    env["CACHE"] = config.CACHE

    return env


@pytest.fixture
def uvicorn_server(test_cli_env):
    p = subprocess.Popen(
        [
            f"{os.environ['VIRTUAL_ENV']}/bin/uvicorn",
            "hatch.app:app",
            "--port",
            "18001",
        ],
        env=test_cli_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    # trickery to wait minium time until server is complete
    lines = []
    timeout = 2.0
    while True:
        # use select in order to not block forever
        r, _, _ = select.select([p.stdout], [], [], timeout)
        if r:
            line = p.stdout.readline().decode("utf8")
            lines.append(line)
            if "startup complete" in line:
                break
        else:  # pragma: no cover
            exitcode = p.poll()
            stdout = "\n".join(lines)
            if exitcode:
                raise AssertionError(
                    f"release-hatch exited unexpectedly with {exitcode}: {stdout}"
                )
            else:
                # process is still running, but we've had no output for 2s
                raise AssertionError(
                    f"did not find expected output in release-hatch stdout: {stdout}"
                )
    yield p
    p.terminate()


def test_client_test(uvicorn_server):
    workspace = secrets.token_hex(8)
    token = generate_token(workspace, "test_user", 5)
    errors = list(run_test(workspace, token))
    assert errors == []


def test_client_cli_index(test_cli_env, uvicorn_server, workspace):
    workspace.write("output/test.csv", "test")
    main(["list", "-w", workspace.name])


def test_client_cli_file(test_cli_env, uvicorn_server, workspace):
    workspace.write("output/test.csv", "test")
    with pytest.raises(SystemExit):
        main(["file", "-w", workspace.name])
    main(["file", "-w", workspace.name, "-f", "output/test.csv"])


def test_client_cli_token(test_cli_env):
    main(["token", "-w", "workspace"])
