from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from tree_sitter import Language, Parser
import tree_sitter_go


_KIND_BY_NODE_TYPE = {
    "function_declaration": "function",
    "method_declaration": "method",
}

_SKIP_DIR_NAMES = {
    "vendor",
    "testdata",
    "generated",
    "gen",
    "mock",
    "mocks",
    "test",
    "tests",
}

_SKIP_FILE_SUFFIXES = (
    "_test.go",
    ".pb.go",
    ".gen.go",
    "_generated.go",
    "_mock.go",
    ".mock.go",
)


def _build_parser() -> Parser:
    parser = Parser()
    parser.language = Language(tree_sitter_go.language())
    return parser


def _should_skip_file(path: Path, root: Path) -> bool:
    rel_parts = path.relative_to(root).parts
    if any(part in _SKIP_DIR_NAMES for part in rel_parts[:-1]):
        return True

    name = path.name
    if any(name.endswith(suffix) for suffix in _SKIP_FILE_SUFFIXES):
        return True
    if name.startswith("zz_generated."):
        return True

    try:
        header = path.read_text(encoding="utf-8", errors="ignore")[:512]
    except OSError:
        return False

    return "Code generated" in header or "DO NOT EDIT" in header


def _iter_go_files(root: Path):
    for current_root, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIR_NAMES]
        for filename in files:
            if not filename.endswith(".go"):
                continue
            path = Path(current_root) / filename
            if _should_skip_file(path, root):
                continue
            yield path


def _node_name(node: Any, source_bytes: bytes) -> str:
    name_node = node.child_by_field_name("name")
    if name_node is None:
        return ""
    return source_bytes[name_node.start_byte : name_node.end_byte].decode(
        "utf-8", errors="replace"
    )


def _extract_from_file(path: Path, root: Path, parser: Parser) -> list[dict]:
    units: list[dict] = []
    try:
        source_bytes = path.read_bytes()
    except OSError as exc:
        print(f"warning: failed reading {path}: {exc}")
        return units

    try:
        tree = parser.parse(source_bytes)
    except Exception as exc:
        print(f"warning: parse error in {path}: {exc}")
        return units

    if tree is None or tree.root_node is None:
        print(f"warning: parse error in {path}: empty syntax tree")
        return units

    if tree.root_node.has_error:
        print(f"warning: parse error in {path}, skipping file")
        return units

    rel_file = os.path.relpath(path, root).replace("\\", "/")
    folder = os.path.relpath(path.parent, root).replace("\\", "/")
    if folder == ".":
        folder = ""

    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        kind = _KIND_BY_NODE_TYPE.get(node.type)
        if kind is not None:
            units.append(
                {
                    "name": _node_name(node, source_bytes),
                    "kind": kind,
                    "file": rel_file,
                    "folder": folder,
                    "start_line": node.start_point[0] + 1,
                    "end_line": node.end_point[0] + 1,
                    "source": source_bytes[node.start_byte : node.end_byte].decode(
                        "utf-8", errors="replace"
                    ),
                }
            )
        for child in node.children:
            stack.append(child)

    units.sort(key=lambda u: (u["file"], u["start_line"], u["name"]))
    return units


def parse_repo(root: str) -> list[dict]:
    """Return list of extracted units for all Go files under root."""
    root_path = Path(root).resolve()
    parser = _build_parser()

    all_units: list[dict] = []
    for path in _iter_go_files(root_path):
        all_units.extend(_extract_from_file(path, root_path, parser))

    return all_units
