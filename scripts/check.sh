#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
PLUGIN_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
PYTHON="$PLUGIN_ROOT/.venv/bin/python"
SERVER="$PLUGIN_ROOT/scripts/mcp_server.py"

if [ ! -x "$PYTHON" ]; then
  echo "missing plugin virtualenv. Run '$PLUGIN_ROOT/scripts/setup.sh' first." >&2
  exit 1
fi

"$PYTHON" - <<'PY'
import json
import subprocess
from pathlib import Path

plugin_root = Path.cwd()
python = plugin_root / ".venv/bin/python"
server = plugin_root / "scripts/mcp_server.py"

proc = subprocess.Popen(
    [str(python), str(server)],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=False,
)

def send(msg):
    raw = json.dumps(msg).encode("utf-8")
    proc.stdin.write(f"Content-Length: {len(raw)}\r\n\r\n".encode("utf-8"))
    proc.stdin.write(raw)
    proc.stdin.flush()

def recv():
    headers = {}
    while True:
        line = proc.stdout.readline()
        if line in (b"\r\n", b"\n", b""):
            break
        key, value = line.decode("utf-8").split(":", 1)
        headers[key.lower().strip()] = value.strip()
    length = int(headers.get("content-length", "0"))
    payload = proc.stdout.read(length)
    return json.loads(payload.decode("utf-8"))

send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
init = recv()
send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
tools = recv()

tool_names = [item["name"] for item in tools["result"]["tools"]]
assert init["result"]["serverInfo"]["name"] == "duster"
assert set(["snapshot", "report", "diff"]).issubset(set(tool_names))

proc.terminate()
proc.wait(timeout=5)

print(json.dumps({"server": init["result"]["serverInfo"], "tools": tool_names}, indent=2))
PY
