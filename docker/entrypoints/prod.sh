#!/usr/bin/env bash
set -euo pipefail

port=$(echo "$SERVER_HOST" | awk -F: '{print $3}' | tr -d / )
exec "$VIRTUAL_ENV/bin/uvicorn" hatch.app:app --port "$port"
