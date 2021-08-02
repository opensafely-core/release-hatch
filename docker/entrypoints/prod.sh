#!/usr/bin/env bash
set -euo pipefail
exec "$VIRTUAL_ENV/bin/uvicorn" hatch.app:app --port 8001
