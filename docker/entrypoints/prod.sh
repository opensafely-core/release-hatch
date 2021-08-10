#!/usr/bin/env bash
set -euo pipefail
exec "$VIRTUAL_ENV/bin/uvicorn" hatch.app:app --host 0.0.0.0 --port 8001
