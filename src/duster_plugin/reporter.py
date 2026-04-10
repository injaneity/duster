from __future__ import annotations

import json
import re
from pathlib import Path


def _fmt_score(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}"


def _fmt_delta(value: float | None) -> str:
    if value is None:
        return "-"
    arrow = "▲" if value > 0 else "▼" if value < 0 else "•"
    return f"{arrow} {abs(value):.2f}"


def report_json(scores: dict, diff: dict | None) -> str:
    return json.dumps({"scores": scores, "diff": diff}, indent=2, sort_keys=True)


def report_markdown(scores: dict, diff: dict | None) -> str:
    timestamp = scores.get("timestamp", "unknown")
    if timestamp.endswith("Z"):
        timestamp = timestamp[:-1]

    overall = scores.get("overall", 0.0)
    overall_delta = diff.get("overall_delta") if diff else None
    if overall_delta is None:
        top = f"> last run: {timestamp}Z · overall **{overall:.2f}**"
    else:
        previous = overall - overall_delta
        top = (
            f"> last run: {timestamp}Z · overall **{overall:.2f}** "
            f"(was {previous:.2f}, {_fmt_delta(overall_delta)})"
        )

    lines = [
        "## codebase hygiene",
        "",
        top,
        "",
        "| level | score | delta |",
        "|---|---|---|",
        f"| coherence | {_fmt_score(scores.get('coherence_score'))} | {_fmt_delta(diff.get('coherence_delta') if diff else None)} |",
        f"| fragmentation penalty | {_fmt_score(scores.get('fragmentation_penalty'))} | {_fmt_delta(diff.get('fragmentation_delta') if diff else None)} |",
        f"| overall | {_fmt_score(scores.get('overall'))} | {_fmt_delta(diff.get('overall_delta') if diff else None)} |",
        "",
        "**fix before adding new code:**",
    ]

    fragmented = scores.get("fragmented_folder_pairs", [])
    if fragmented:
        top_pair = fragmented[0]
        lines.append(
            f"- `{top_pair['a']}/` + `{top_pair['b']}/` similarity {top_pair['similarity']:.2f} - likely over-split, consider merging"
        )

    duplicates = scores.get("duplicates", [])
    if duplicates:
        item = duplicates[0]
        pct = int(round(item["similarity"] * 100))
        lines.append(f"- `{item['a']['file']}` duplicates ~{pct}% of `{item['b']['file']}`")

    return "\n".join(lines[:15])


def inject_agents_md(markdown: str, root: str) -> None:
    agents = Path(root) / "AGENTS.md"
    if agents.exists():
        content = agents.read_text(encoding="utf-8")
    else:
        content = ""

    pattern = re.compile(r"^## codebase hygiene\n[\s\S]*?(?=^##\s|\Z)", re.MULTILINE)
    block = markdown.rstrip() + "\n"

    if pattern.search(content):
        updated = pattern.sub(block, content, count=1)
    else:
        if content and not content.endswith("\n"):
            content += "\n"
        if content.strip():
            content += "\n"
        updated = content + block

    agents.write_text(updated, encoding="utf-8")
