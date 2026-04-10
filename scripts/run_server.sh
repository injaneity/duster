#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
PLUGIN_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
VENV_PYTHON="$PLUGIN_ROOT/.venv/bin/python"
SERVER="$PLUGIN_ROOT/scripts/mcp_server.py"

if [ ! -x "$VENV_PYTHON" ]; then
  echo "duster plugin is not set up. Run '$PLUGIN_ROOT/scripts/setup.sh' first." >&2
  exit 1
fi

exec "$VENV_PYTHON" "$SERVER"
