from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _snapshot_dir(root: str) -> Path:
    path = Path(root) / ".duster" / "snapshots"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _snapshot_files(root: str) -> list[Path]:
    directory = Path(root) / ".duster" / "snapshots"
    if not directory.exists():
        return []
    return sorted([path for path in directory.glob("*.json") if path.is_file()])


def _dup_key(item: dict) -> tuple[str, str, str, str]:
    left = (item["a"]["file"], item["a"]["name"])
    right = (item["b"]["file"], item["b"]["name"])
    if left <= right:
        return (left[0], left[1], right[0], right[1])
    return (right[0], right[1], left[0], left[1])


def _pair_key(item: dict, kind: str) -> tuple[str, str, str]:
    left = item["a"]
    right = item["b"]
    if left <= right:
        return (kind, left, right)
    return (kind, right, left)


def _delta(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None:
        return None
    return round(current - previous, 2)


def save_snapshot(scores: dict, root: str) -> str:
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    path = _snapshot_dir(root) / f"{timestamp}.json"

    payload = dict(scores)
    payload["timestamp"] = timestamp
    payload["root"] = str(Path(root).resolve())
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return str(path)


def load_latest(root: str) -> dict | None:
    files = _snapshot_files(root)
    if not files:
        return None
    return json.loads(files[-1].read_text(encoding="utf-8"))


def load_previous(root: str) -> dict | None:
    files = _snapshot_files(root)
    if len(files) < 2:
        return None
    return json.loads(files[-2].read_text(encoding="utf-8"))


def diff_snapshots(current: dict, previous: dict) -> dict:
    current_dups = {_dup_key(item): item for item in current.get("duplicates", [])}
    previous_dups = {_dup_key(item): item for item in previous.get("duplicates", [])}

    current_pairs = {}
    for item in current.get("fragmented_folder_pairs", []):
        current_pairs[_pair_key(item, "folder")] = {"kind": "folder", **item}
    for item in current.get("fragmented_file_pairs", []):
        current_pairs[_pair_key(item, "file")] = {"kind": "file", **item}

    previous_pairs = {}
    for item in previous.get("fragmented_folder_pairs", []):
        previous_pairs[_pair_key(item, "folder")] = {"kind": "folder", **item}
    for item in previous.get("fragmented_file_pairs", []):
        previous_pairs[_pair_key(item, "file")] = {"kind": "file", **item}

    current_folders = current.get("folder_breakdown", {}) or {}
    previous_folders = previous.get("folder_breakdown", {}) or {}
    degraded = []
    for folder in sorted(set(current_folders) & set(previous_folders)):
        delta = round(float(current_folders[folder]) - float(previous_folders[folder]), 2)
        if delta < -0.05:
            degraded.append({"folder": folder, "delta": delta})

    degraded.sort(key=lambda item: item["delta"])
    return {
        "overall_delta": _delta(current.get("overall"), previous.get("overall")) or 0.0,
        "coherence_delta": _delta(current.get("coherence_score"), previous.get("coherence_score")),
        "file_delta": _delta(current.get("file_score"), previous.get("file_score")),
        "folder_delta": _delta(current.get("folder_score"), previous.get("folder_score")),
        "fragmentation_delta": _delta(
            current.get("fragmentation_penalty", 0.0),
            previous.get("fragmentation_penalty", 0.0),
        )
        or 0.0,
        "new_duplicates": [current_dups[key] for key in sorted(set(current_dups) - set(previous_dups))],
        "resolved_duplicates": [
            previous_dups[key] for key in sorted(set(previous_dups) - set(current_dups))
        ],
        "degraded_folders": degraded,
        "new_fragmented_pairs": [
            current_pairs[key] for key in sorted(set(current_pairs) - set(previous_pairs))
        ],
        "resolved_fragmented_pairs": [
            previous_pairs[key] for key in sorted(set(previous_pairs) - set(current_pairs))
        ],
    }
