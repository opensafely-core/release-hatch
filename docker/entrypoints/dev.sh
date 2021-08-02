#!/usr/bin/env bash
set -euo pipefail
exec "$VIRTUAL_ENV/bin/uvicorn" hatch.app:app --reload --port 8001
