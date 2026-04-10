from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from .embedder import embed_units
from .parser import parse_repo
from .reporter import inject_agents_md, report_json, report_markdown
from .scorer import score
from .snapshot import diff_snapshots, load_latest, load_previous, save_snapshot

DEFAULT_MAX_UNITS = 3000


def resolve_root(raw: str | None) -> str:
    return str(Path(raw or ".").resolve())


def _sample_units(units: list[dict], max_units: int | None) -> list[dict]:
    if max_units is None or len(units) <= max_units:
        return units

    buckets: dict[str, list[dict]] = defaultdict(list)
    for unit in units:
        buckets[unit["folder"]].append(unit)

    ordered_folders = sorted(buckets)
    selected: list[dict] = []
    index = 0
    while len(selected) < max_units:
        progressed = False
        for folder in ordered_folders:
            bucket = buckets[folder]
            if index < len(bucket):
                selected.append(bucket[index])
                progressed = True
                if len(selected) >= max_units:
                    break
        if not progressed:
            break
        index += 1
    return selected


def run_snapshot(root: str, max_units: int | None = DEFAULT_MAX_UNITS, full_scan: bool = False) -> dict:
    units = parse_repo(root)
    units = _sample_units(units, None if full_scan else max_units)
    units = embed_units(units, root)
    scores = score(units)
    save_snapshot(scores, root)
    latest = load_latest(root)
    return latest or scores


def run_report(
    root: str,
    out_format: str = "markdown",
    inject: bool = False,
    max_units: int | None = DEFAULT_MAX_UNITS,
    full_scan: bool = False,
) -> str:
    latest = load_latest(root)
    if latest is None:
        latest = run_snapshot(root, max_units=max_units, full_scan=full_scan)
    previous = load_previous(root)
    diff = diff_snapshots(latest, previous) if previous else None

    if out_format == "json":
        body = report_json(latest, diff)
    else:
        body = report_markdown(latest, diff)

    if inject:
        inject_agents_md(report_markdown(latest, diff), root)
        body += f"\n\n[injected into {Path(root) / 'AGENTS.md'}]"

    return body


def run_diff(root: str) -> tuple[str, bool]:
    latest = load_latest(root)
    previous = load_previous(root)
    if latest is None or previous is None:
        return "need at least 2 snapshots", True
    diff = diff_snapshots(latest, previous)
    return report_json(latest, diff), False
