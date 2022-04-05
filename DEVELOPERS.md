# Notes for developers

## Deployment

### TPP
release-hatch is deployed on L4 under `/d/release-hatch-2/`.
It is running in a terminal under @ghickman's account via `./run.sh`.

Should it break any other user _should_ be able to run the same command from the same directory.

If `./run.sh` prints nothing back and exits with `1` then it's likely something is up with the virtualenv and recreating is likely the easiest first step:

1. `cd /d/release-hatch-2/`
1. `rm -rf venv`
1. `python -m venv venv`
1. `venv/Scripts/pip install -r requirements.prod.txt --no-index -f /d/windows-wheels/`

This will remove the current virtualenv, create a new one, and install the requirements from the directory of wheels.


## System requirements

### just

```sh
# macOS
brew install just

# Linux
# Install from https://github.com/casey/just/releases

# Add completion for your shell. E.g. for bash:
source <(just --completions bash)

# Show all available commands
just #  shortcut for just --list
```


## Local development environment


Set up a local development environment with:
```
just devenv
```

## Tests
Run the tests via pytest with:
```
just test <args>
```


## Setup config

Config is loaded via env vars from .env:

`cp dotenv-sample .env`

The default dev config will run this service on `http://127.0.0.1:8001`, and
assume a local job-runner is running on `http://127.0.0.8:8000`


## Run server

This will run the server on the port configured

`just run`

You can now go to `http://127.0.0:8001/docs` do examine and try the API.


## Test client

The test client is a developer tool to test a locally running release-hatch
server, and uses the same configuration as the running service. It can be used
to exercise the APIs release-hatch provides. It automatically generates the
appropriate auth tokens using the service config.

### Generate auth token

This can be useful if you are manually testing urls with curl, for example.

    just client token -w WORKSPACE

### View index API response

Get the index API response for a workspace or release.

    just client index -w WORKSPACE [-r RELEASE_ID]

### Download file

Download a specific file from a workspace or release.

    just client file -w WORKSPACE [-r RELEASE_ID] -f file/name.txt

### Run basic integration test

This creates some files in a temporary workspace which is deleted after the
test run. It creates a release for that workspace, and checks the the index and
files APIs work correctly for both the workspace and the release.  It is run by
default as a part of the test suite, as well as used as part of our deployment
tooling testing.

    just client test

Note: it does not test the release creation or file upload APIs, currently, but
may do in future.


## Communicate with local job-runner

You will need to set your `JOB_SERVER_TOKEN` value in .env to match the token value in
job-server and restart.
