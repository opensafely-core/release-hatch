import os
import secrets
import subprocess
import time

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
    time.sleep(2)
    assert not p.poll(), p.stdout.read().decode("utf-8")
    yield p
    p.terminate()


def test_client_test(uvicorn_server):
    workspace = secrets.token_hex(8)
    token = generate_token(workspace, "test_user", 5)
    errors = list(run_test(workspace, token))
    assert errors == []


def test_client_cli_index(test_cli_env, uvicorn_server, workspace):
    workspace.write("output/test.csv", "test")
    main(["index", "-w", workspace.name])


def test_client_cli_file(test_cli_env, uvicorn_server, workspace):
    workspace.write("output/test.csv", "test")
    with pytest.raises(SystemExit):
        main(["file", "-w", workspace.name])
    main(["file", "-w", workspace.name, "-f", "output/test.csv"])


def test_client_cli_token(test_cli_env):
    main(["token", "-w", "workspace"])
