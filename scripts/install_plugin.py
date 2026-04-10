#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path


PLUGIN_NAME = "duster"


def _copy_plugin(src: Path, dst: Path) -> None:
    ignore = shutil.ignore_patterns(
        ".git",
        ".venv",
        "__pycache__",
        "*.pyc",
        ".DS_Store",
    )
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=ignore)


def _marketplace_path(path: str | None) -> Path:
    if path:
        return Path(path).expanduser()
    return Path.home() / ".agents" / "plugins" / "marketplace.json"


def _target_root(path: str | None) -> Path:
    if path:
        return Path(path).expanduser()
    return Path.home() / "plugins" / PLUGIN_NAME


def _load_marketplace(path: Path) -> dict:
    if not path.exists():
        return {
            "name": "local-plugins",
            "interface": {"displayName": "Local Plugins"},
            "plugins": [],
        }
    return json.loads(path.read_text(encoding="utf-8"))


def _ensure_marketplace_entry(path: Path) -> None:
    payload = _load_marketplace(path)
    plugins = payload.setdefault("plugins", [])

    entry = {
        "name": PLUGIN_NAME,
        "source": {"source": "local", "path": f"./plugins/{PLUGIN_NAME}"},
        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
        "category": "Productivity",
    }

    for index, item in enumerate(plugins):
        if item.get("name") == PLUGIN_NAME:
            plugins[index] = entry
            break
    else:
        plugins.append(entry)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _run_setup(target: Path) -> None:
    subprocess.run([str(target / "scripts" / "setup.sh")], check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Install the Duster Codex plugin locally.")
    parser.add_argument("--plugin-root", help="Target plugin directory, defaults to ~/plugins/duster")
    parser.add_argument(
        "--marketplace-path",
        help="Marketplace JSON path, defaults to ~/.agents/plugins/marketplace.json",
    )
    parser.add_argument(
        "--source-root",
        help="Source plugin directory. Defaults to the current script's plugin root.",
    )
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    source_root = Path(args.source_root).expanduser() if args.source_root else script_dir.parent
    target = _target_root(args.plugin_root)
    marketplace = _marketplace_path(args.marketplace_path)

    target.parent.mkdir(parents=True, exist_ok=True)
    _copy_plugin(source_root, target)
    _ensure_marketplace_entry(marketplace)
    _run_setup(target)

    print(f"installed duster to {target}")
    print(f"updated marketplace at {marketplace}")
    print("restart Codex to load the plugin")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
