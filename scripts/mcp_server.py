#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure the bundled plugin package is importable from the plugin root.
PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PLUGIN_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

try:
    from duster_plugin.service import resolve_root, run_diff, run_report, run_snapshot
except ModuleNotFoundError as exc:
    sys.stderr.write(
        "duster plugin dependencies are not installed. "
        "Run `python3 -m pip install -r plugins/duster/requirements.txt`.\n"
    )
    raise SystemExit(1) from exc


TOOLS = [
    {
        "name": "snapshot",
        "description": "Parse, embed, score, and save a duster snapshot.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root": {"type": "string", "description": "Repo root path", "default": "."},
                "max_units": {"type": "integer", "default": 3000},
                "full": {"type": "boolean", "default": False},
            },
        },
    },
    {
        "name": "report",
        "description": "Generate a duster report from latest snapshots.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root": {"type": "string", "description": "Repo root path", "default": "."},
                "format": {
                    "type": "string",
                    "enum": ["json", "markdown"],
                    "default": "markdown",
                },
                "inject": {"type": "boolean", "default": False},
                "max_units": {"type": "integer", "default": 3000},
                "full": {"type": "boolean", "default": False},
            },
        },
    },
    {
        "name": "diff",
        "description": "Diff the latest two duster snapshots.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root": {"type": "string", "description": "Repo root path", "default": "."}
            },
        },
    },
]


def _read_message() -> dict | None:
    headers = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        if line in (b"\r\n", b"\n"):
            break
        try:
            key, value = line.decode("utf-8").split(":", 1)
        except ValueError:
            continue
        headers[key.strip().lower()] = value.strip()

    length = int(headers.get("content-length", "0"))
    if length <= 0:
        return None
    body = sys.stdin.buffer.read(length)
    return json.loads(body.decode("utf-8"))


def _write(payload: dict) -> None:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(raw)}\r\n\r\n".encode("utf-8"))
    sys.stdout.buffer.write(raw)
    sys.stdout.buffer.flush()


def _ok(req_id, result: dict) -> None:
    _write({"jsonrpc": "2.0", "id": req_id, "result": result})


def _err(req_id, code: int, message: str) -> None:
    _write({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})


def _text_result(text: str, is_error: bool = False) -> dict:
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def _handle_tool_call(name: str, arguments: dict) -> dict:
    root = resolve_root(arguments.get("root"))

    if name == "snapshot":
        scores = run_snapshot(
            root,
            max_units=arguments.get("max_units", 3000),
            full_scan=bool(arguments.get("full", False)),
        )
        return _text_result(json.dumps({"scores": scores}, indent=2, sort_keys=True))

    if name == "report":
        body = run_report(
            root,
            out_format=arguments.get("format", "markdown"),
            inject=bool(arguments.get("inject", False)),
            max_units=arguments.get("max_units", 3000),
            full_scan=bool(arguments.get("full", False)),
        )
        return _text_result(body)

    if name == "diff":
        body, is_error = run_diff(root)
        return _text_result(body, is_error=is_error)

    return _text_result(f"unknown tool: {name}", is_error=True)


def main() -> int:
    while True:
        msg = _read_message()
        if msg is None:
            return 0

        method = msg.get("method")
        req_id = msg.get("id")
        params = msg.get("params", {})

        try:
            if method == "initialize":
                _ok(
                    req_id,
                    {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "duster", "version": "0.3.0"},
                    },
                )
            elif method == "notifications/initialized":
                continue
            elif method == "tools/list":
                _ok(req_id, {"tools": TOOLS})
            elif method == "tools/call":
                name = params.get("name", "")
                arguments = params.get("arguments", {})
                _ok(req_id, _handle_tool_call(name, arguments))
            elif method == "shutdown":
                _ok(req_id, {})
            elif method == "exit":
                return 0
            else:
                if req_id is not None:
                    _err(req_id, -32601, f"Method not found: {method}")
        except Exception as exc:
            if req_id is not None:
                _err(req_id, -32000, str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
