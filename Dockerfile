# syntax=docker/dockerfile:1.2
#################################################
#
# Create base image with python installed.
#
# DL3007 ignored because base-docker we specifically always want to build on
# the latest base image, by design.
#
# hadolint ignore=DL3007
FROM ghcr.io/opensafely-core/base-docker:latest as base-python

# we are going to use an apt cache on the host, so disable the default debian
# docker clean up that deletes that cache on every apt install
RUN rm -f /etc/apt/apt.conf.d/docker-clean

# ensure fully working base python3 installation
# see: https://gist.github.com/tiran/2dec9e03c6f901814f6d1e8dad09528e
# use space efficient utility from base image
RUN --mount=type=cache,target=/var/cache/apt \
  /root/docker-apt-install.sh python3 python3-venv python3-pip python3-distutils tzdata ca-certificates

# install any additional system dependencies
# Uncomment if you add dependencies.txt
#RUN --mount=type=bind,source=dependencies.txt,target=/dependencies.txt \
#    --mount=type=cache,target=/var/cache/apt \
#    /root/docker-apt-install.sh /dependencies.txt


##################################################
#
# Build image
#
# Ok, now we have local base image with python and our system dependencies on.
# We'll use this as the base for our builder image, where we'll build and
# install any python packages needed.
#
# We use a separate, disposable build image to avoid carrying the build
# dependencies into the production image.
FROM base-python as builder

# Install any system build dependencies
# Uncomment if you add build-dependencies.txt
#RUN --mount=type=bind,source=build-dependencies.txt,target=/build-dependencies.txt \
#    --mount=type=cache,target=/var/cache/apt \
#    /root/docker-apt-install.sh /build-dependencies.txt

# Install everything in venv for isolation from system python libraries
RUN python3 -m venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv/ PATH="/opt/venv/bin:$PATH"

# The cache mount means a) /root/.cache is not in the image, and b) it's preserved
# between docker builds locally, for faster dev rebuild.
COPY requirements.prod.txt /tmp/requirements.prod.txt

# DL3042: using cache mount instead
# DL3013: we always want latest pip/setuptools/wheel, at least for now
# hadolint ignore=DL3042,DL3013
RUN --mount=type=cache,target=/root/.cache \
    python -m pip install -U pip setuptools wheel && \
    python -m pip install --require-hashes --requirement /tmp/requirements.prod.txt


##################################################
#
# Base project image
#
# Ok, we've built everything we need, build an image with all dependencies but
# no code.
#
# Not including the code at this stage has two benefits:
#
# 1) this image only rebuilds when the handlful of files needed to build release-hatch-base
#    changes. If we do `COPY . /app` now, this will rebuild when *any* file changes.
#
# 2) Ensures we *have* to mount the volume for dev image, as there's no embedded
#    version of the code. Otherwise, we could end up accidentally using the
#    version of the code included when the prod image was built.
FROM base-python as release-hatch-base

# Create a non-root user to run the app as
RUN useradd --create-home appuser

# copy venv over from builder image. These will have root:root ownership, but
# are readable by all.
COPY --from=builder /opt/venv /opt/venv

# Ensure we're using the venv by default
ENV VIRTUAL_ENV=/opt/venv/ PATH="/opt/venv/bin:$PATH"

RUN mkdir /app
WORKDIR /app
VOLUME /app
VOLUME /workspaces

# This may not be nessecary, but it probably doesn't hurt
ENV PYTHONPATH=/app

# switch to running as the user
USER appuser


##################################################
#
# Production image
#
# Copy code in, add proper metadata
FROM release-hatch-base as release-hatch-prod

# Adjust this metadata to fit project. Note that the base-docker image does set
# some basic metadata.
LABEL org.opencontainers.image.title="release-hatch" \
      org.opencontainers.image.description="project description" \
      org.opencontainers.image.source="https://github.com/opensafely-core/project"

# copy application code
COPY . /app

# We set command rather than entrypoint, to make it easier to run different
# things from the cli
CMD ["/app/entrypoints/prod.sh"]

# finally, tag with build information. These will change regularly, therefore
# we do them as the last action.
ARG BUILD_DATE=unknown
LABEL org.opencontainers.image.created=$BUILD_DATE
ARG GITREF=unknown
LABEL org.opencontainers.image.revision=$GITREF



##################################################
#
# Dev image
#
# Now we build a dev image from our release-hatch-base image. This is basically
# installing dev dependencies and changing the entrypoint
#
FROM release-hatch-base as release-hatch-dev

# switch back to root to run the install of dev requirements.txt
USER root

# TODO: its possible python dev dependencies might need some additional build packages installed?

# install development requirements
COPY requirements.dev.txt /tmp/requirements.dev.txt
# using cache mount instead
# hadolint ignore=DL3042
RUN --mount=type=cache,target=/root/.cache \
    python -m pip install --require-hashes --requirement /tmp/requirements.dev.txt

CMD ["/app/entrypoints/dev.sh"]

# in dev, ensure appuser uid matches host user id
ARG USERID=1000
RUN usermod -u $USERID appuser

# switch back to appuser
USER appuser
