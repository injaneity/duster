from __future__ import annotations

from collections import defaultdict
from itertools import combinations

import numpy as np
from sklearn.metrics import silhouette_samples, silhouette_score
from sklearn.metrics.pairwise import cosine_similarity


EXEMPT_FINAL_COMPONENTS = {
    "utils",
    "util",
    "shared",
    "common",
    "helpers",
    "helper",
    "types",
    "mocks",
    "mock",
    "vendor",
    "gen",
    "generated",
}

FILE_FRAGMENT_THRESHOLD = 0.88
FOLDER_FRAGMENT_THRESHOLD = 0.85
TOP_FRAGMENTED_FILE_PAIRS = 5
TOP_FRAGMENTED_FOLDER_PAIRS = 10


def cosine(a, b):
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def _mean(vectors: list[list[float]]) -> list[float]:
    return np.mean(np.asarray(vectors, dtype=float), axis=0).tolist()


def _normalize_silhouette(value: float) -> float:
    out = (value + 1.0) / 2.0
    return float(min(1.0, max(0.0, out)))


def _final_component(folder: str) -> str:
    if not folder:
        return ""
    return folder.rstrip("/").split("/")[-1]


def _is_exempt(folder: str) -> bool:
    return _final_component(folder) in EXEMPT_FINAL_COMPONENTS


def _parent_label(folder: str) -> str:
    if not folder or "/" not in folder:
        return "root"
    return folder.rsplit("/", 1)[0]


def _build_file_entries(units: list[dict]) -> list[dict]:
    file_to_vectors: dict[tuple[str, str], list[list[float]]] = defaultdict(list)
    for unit in units:
        file_to_vectors[(unit["file"], unit["folder"])].append(unit["vector"])

    file_entries = []
    for (file_path, folder), vectors in file_to_vectors.items():
        if _is_exempt(folder):
            continue
        file_entries.append({"file": file_path, "folder": folder, "vector": _mean(vectors)})
    return file_entries


def _build_folder_entries(file_entries: list[dict]) -> list[dict]:
    folder_to_vectors: dict[str, list[list[float]]] = defaultdict(list)
    for entry in file_entries:
        folder_to_vectors[entry["folder"]].append(entry["vector"])

    folder_entries = []
    for folder, vectors in folder_to_vectors.items():
        folder_entries.append(
            {"folder": folder, "vector": _mean(vectors), "parent": _parent_label(folder)}
        )
    return folder_entries


def _compute_file_level(file_entries: list[dict]):
    if len(file_entries) < 2:
        print("warning: not enough file samples after exemptions for file-level silhouette")
        return None, [], {}

    labels = [entry["folder"] for entry in file_entries]
    distinct_labels = set(labels)
    if len(distinct_labels) < 2:
        print("warning: fewer than 2 folders after exemptions; file-level score unavailable")
        return None, [], {}
    if len(file_entries) <= len(distinct_labels):
        print("warning: insufficient file samples per folder for file-level silhouette")
        return None, [], {}

    X = np.asarray([entry["vector"] for entry in file_entries], dtype=float)
    raw = silhouette_score(X, labels, metric="cosine")
    point_scores = silhouette_samples(X, labels, metric="cosine")

    worst = []
    breakdown = {}
    for entry, item_score in zip(file_entries, point_scores):
        norm = round(_normalize_silhouette(float(item_score)), 2)
        worst.append({"file": entry["file"], "folder": entry["folder"], "score": norm})
        breakdown[entry["file"]] = {"folder": entry["folder"], "score": norm}
    worst.sort(key=lambda item: item["score"])
    return round(_normalize_silhouette(float(raw)), 2), worst[:3], breakdown


def _compute_folder_level(folder_entries: list[dict]):
    if len(folder_entries) < 2:
        print("warning: not enough folder samples after exemptions for folder-level silhouette")
        return None, [], {}

    labels = [entry["parent"] for entry in folder_entries]
    distinct_labels = set(labels)
    if len(distinct_labels) < 2:
        print("warning: fewer than 2 distinct parent folders; folder-level score unavailable")
        return None, [], {}
    if len(folder_entries) <= len(distinct_labels):
        print("warning: insufficient folder samples per parent for folder-level silhouette")
        return None, [], {}

    X = np.asarray([entry["vector"] for entry in folder_entries], dtype=float)
    raw = silhouette_score(X, labels, metric="cosine")
    point_scores = silhouette_samples(X, labels, metric="cosine")

    worst = []
    breakdown = {}
    for entry, item_score in zip(folder_entries, point_scores):
        norm = round(_normalize_silhouette(float(item_score)), 2)
        worst.append({"folder": entry["folder"], "score": norm})
        breakdown[entry["folder"]] = norm
    worst.sort(key=lambda item: item["score"])
    return round(_normalize_silhouette(float(raw)), 2), worst[:3], breakdown


def _coherence_score(file_score: float | None, folder_score: float | None) -> float | None:
    if file_score is not None and folder_score is not None:
        return round(0.6 * file_score + 0.4 * folder_score, 2)
    if file_score is not None:
        return file_score
    if folder_score is not None:
        return folder_score
    return None


def _fragmentation_metrics(file_entries: list[dict], folder_entries: list[dict]) -> dict:
    file_pairs_total = 0
    file_pairs_flagged = 0
    fragmented_file_pairs = []

    by_folder: dict[str, list[dict]] = defaultdict(list)
    for entry in file_entries:
        by_folder[entry["folder"]].append(entry)

    for entries in by_folder.values():
        if len(entries) < 2:
            continue
        matrix = np.asarray([entry["vector"] for entry in entries], dtype=float)
        sim = cosine_similarity(matrix)
        for i in range(len(entries)):
            for j in range(i + 1, len(entries)):
                file_pairs_total += 1
                pair_score = float(sim[i, j])
                if pair_score > FILE_FRAGMENT_THRESHOLD:
                    file_pairs_flagged += 1
                    fragmented_file_pairs.append(
                        {
                            "a": entries[i]["file"],
                            "b": entries[j]["file"],
                            "similarity": round(pair_score, 2),
                        }
                    )

    folder_pairs_total = 0
    folder_pairs_flagged = 0
    fragmented_folder_pairs = []
    if len(folder_entries) >= 2:
        matrix = np.asarray([entry["vector"] for entry in folder_entries], dtype=float)
        sim = cosine_similarity(matrix)
        for i in range(len(folder_entries)):
            for j in range(i + 1, len(folder_entries)):
                folder_pairs_total += 1
                pair_score = float(sim[i, j])
                if pair_score > FOLDER_FRAGMENT_THRESHOLD:
                    folder_pairs_flagged += 1
                    fragmented_folder_pairs.append(
                        {
                            "a": folder_entries[i]["folder"],
                            "b": folder_entries[j]["folder"],
                            "similarity": round(pair_score, 2),
                        }
                    )

    file_fragmentation = file_pairs_flagged / max(file_pairs_total, 1)
    folder_fragmentation = folder_pairs_flagged / max(folder_pairs_total, 1)
    penalty = 0.5 * file_fragmentation + 0.5 * folder_fragmentation

    fragmented_file_pairs.sort(key=lambda item: item["similarity"], reverse=True)
    fragmented_folder_pairs.sort(key=lambda item: item["similarity"], reverse=True)
    return {
        "fragmentation_penalty": round(float(min(1.0, max(0.0, penalty))), 2),
        "file_fragmentation": round(file_fragmentation, 2),
        "folder_fragmentation": round(folder_fragmentation, 2),
        "fragmented_file_pairs": fragmented_file_pairs[:TOP_FRAGMENTED_FILE_PAIRS],
        "fragmented_folder_pairs": fragmented_folder_pairs[:TOP_FRAGMENTED_FOLDER_PAIRS],
    }


def _duplicate_pairs(units: list[dict]) -> list[dict]:
    fn_units = [u for u in units if u.get("kind") in {"function", "method"} and "vector" in u]
    if len(fn_units) < 2:
        return []

    duplicates = []
    if len(fn_units) > 500:
        matrix = np.asarray([u["vector"] for u in fn_units], dtype=float)
        sim = cosine_similarity(matrix)
        for i in range(len(fn_units)):
            for j in range(i + 1, len(fn_units)):
                if fn_units[i]["file"] == fn_units[j]["file"]:
                    continue
                pair_score = float(sim[i, j])
                if pair_score > 0.92:
                    duplicates.append(
                        {
                            "a": {"name": fn_units[i]["name"], "file": fn_units[i]["file"]},
                            "b": {"name": fn_units[j]["name"], "file": fn_units[j]["file"]},
                            "similarity": round(pair_score, 2),
                        }
                    )
    else:
        for left, right in combinations(fn_units, 2):
            if left["file"] == right["file"]:
                continue
            pair_score = cosine(left["vector"], right["vector"])
            if pair_score > 0.92:
                duplicates.append(
                    {
                        "a": {"name": left["name"], "file": left["file"]},
                        "b": {"name": right["name"], "file": right["file"]},
                        "similarity": round(float(pair_score), 2),
                    }
                )

    duplicates.sort(key=lambda item: item["similarity"], reverse=True)
    return duplicates


def _overall(coherence_score: float | None, fragmentation_penalty: float) -> float:
    if coherence_score is None:
        return 0.0
    value = coherence_score * (1 - fragmentation_penalty)
    return round(float(min(1.0, max(0.0, value))), 2)


def score(units: list[dict]) -> dict:
    file_entries = _build_file_entries(units)
    folder_entries = _build_folder_entries(file_entries)

    file_score, worst_files, file_breakdown = _compute_file_level(file_entries)
    folder_score, worst_folders, folder_breakdown = _compute_folder_level(folder_entries)
    coherence_score = _coherence_score(file_score, folder_score)
    fragmentation = _fragmentation_metrics(file_entries, folder_entries)

    return {
        "overall": _overall(coherence_score, fragmentation["fragmentation_penalty"]),
        "coherence_score": coherence_score,
        "file_score": file_score,
        "folder_score": folder_score,
        "fragmentation_penalty": fragmentation["fragmentation_penalty"],
        "file_fragmentation": fragmentation["file_fragmentation"],
        "folder_fragmentation": fragmentation["folder_fragmentation"],
        "duplicates": _duplicate_pairs(units),
        "worst_files": worst_files,
        "worst_folders": worst_folders,
        "fragmented_folder_pairs": fragmentation["fragmented_folder_pairs"],
        "fragmented_file_pairs": fragmentation["fragmented_file_pairs"],
        "file_breakdown": file_breakdown,
        "folder_breakdown": folder_breakdown,
    }
