# Notes for developers

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
just dev_setup
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


## Generate token

If you need a test token to access the APIs, you can run:

just token WORKSPACE

This will output a token that can be used to access urls for workspace
WORKSPACE.


## Communicate with local job-runner

You will need to set your `BACKEND_TOKEN` value in .env to match the token value in
job-server and restart.
