set dotenv-load := true

# just has no idiom for setting a default value for an environment variable
# so we shell out, as we need VIRTUAL_ENV in the justfile environment
export VIRTUAL_ENV := `echo ${VIRTUAL_ENV:-.venv}`

# TODO: make it /scripts on windows?
export BIN := VIRTUAL_ENV + "/bin"
export PIP := BIN + "/python -m pip"
# enforce our chosen pip compile flags
export COMPILE := BIN + "/pip-compile --allow-unsafe --generate-hashes"


# list available commands
list:
    @{{ just_executable() }} --list


# clean up temporary files
clean:
    rm -rf .venv


# ensure valid virtualenv
_virtualenv:
    #!/usr/bin/env bash
    set -euo pipefail

    # allow users to specify python version in .env
    PYTHON_VERSION=${PYTHON_VERSION:-python3.9}

    # create venv and upgrade pip
    test -d $VIRTUAL_ENV || { $PYTHON_VERSION -m venv $VIRTUAL_ENV && $PIP install --upgrade pip; }

    # ensure we have pip-tools so we can run pip-compile
    test -e $BIN/pip-compile || $PIP install pip-tools


_compile src dst *args: _virtualenv
    #!/usr/bin/env bash
    set -euo pipefail

    # exit if src file is older than dst file (-nt = 'newer than', but we negate with || to avoid error exit code)
    test "${FORCE:-}" = "true" -o {{ src }} -nt {{ dst }} || exit 0
    $BIN/pip-compile --allow-unsafe --generate-hashes --output-file={{ dst }} {{ src }} {{ args }}


# update requirements.prod.txt if requirements.prod.in has changed
requirements-prod *args:
    {{ just_executable() }} _compile requirements.prod.in requirements.prod.txt {{ args }}


# update requirements.dev.txt if requirements.dev.in has changed
requirements-dev *args: requirements-prod
    {{ just_executable() }} _compile requirements.dev.in requirements.dev.txt {{ args }}


# ensure prod requirements installed and up to date
prodenv: requirements-prod
    #!/usr/bin/env bash
    set -euo pipefail

    # exit if .txt file has not changed since we installed them (-nt == "newer than', but we negate with || to avoid error exit code)
    test requirements.prod.txt -nt $VIRTUAL_ENV/.prod || exit 0

    $PIP install -r requirements.prod.txt
    touch $VIRTUAL_ENV/.prod


_env:
    test -f .env || cp dotenv-sample.env .env


# && dependencies are run after the recipe has run. Needs just>=0.9.9. This is
# a killer feature over Makefiles.
#
# ensure dev requirements installed and up to date
devenv: _env prodenv requirements-dev && _install-precommit
    #!/usr/bin/env bash
    set -euo pipefail

    # exit if .txt file has not changed since we installed them (-nt == "newer than', but we negate with || to avoid error exit code)
    test requirements.dev.txt -nt $VIRTUAL_ENV/.dev || exit 0

    $PIP install -r requirements.dev.txt
    touch $VIRTUAL_ENV/.dev


# ensure precommit is installed
_install-precommit:
    #!/usr/bin/env bash
    set -euo pipefail

    BASE_DIR=$(git rev-parse --show-toplevel)
    test -f $BASE_DIR/.git/hooks/pre-commit || $BIN/pre-commit install


# upgrade dev or prod dependencies (specify package to upgrade single package, all by default)
upgrade env package="": _virtualenv
    #!/usr/bin/env bash
    set -euo pipefail

    opts="--upgrade"
    test -z "{{ package }}" || opts="--upgrade-package {{ package }}"
    FORCE=true {{ just_executable() }} requirements-{{ env }} $opts


# *args is variadic, 0 or more. This allows us to do `just test -k match`, for example.
# Run the tests
test *args: devenv
    $BIN/coverage run --module pytest {{ args }}
    $BIN/coverage report || $BIN/coverage html


black *args=".": devenv
    $BIN/black --check {{ args }}

ruff *args=".": devenv
    $BIN/ruff check {{ args }}

# run the various dev checks but does not change any files
check: black ruff


# fix formatting and import sort ordering
fix: devenv
    $BIN/black .
    $BIN/ruff --fix .


# Run the dev project
run:
    #!/usr/bin/env bash
    set -euxo pipefail

    port=$(echo $RELEASE_HOST | awk -F: '{print $3}' | tr -d / )
    $BIN/uvicorn hatch.app:app --reload --port ${port:-8000}


# Run the test client
client *ARGS:
    @PYTHONPATH=. $BIN/python ./hatch/client.py {{ ARGS }}


# build docker image env=dev|prod
docker-build env="dev": _env
    {{ just_executable() }} docker/build {{ env }}


# run tests in docker container
docker-test: _env
    {{ just_executable() }} docker/test


# run dev server in docker container
docker-serve: _env
    {{ just_executable() }} docker/serve


# run cmd in dev docker continer
docker-run *args="bash": _env
    {{ just_executable() }} docker/run {{ args }}


# exec command in an existing dev docker container
docker-exec *args="bash": _env
    {{ just_executable() }} docker/exec {{ args }}
