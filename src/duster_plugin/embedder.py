from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from pathlib import Path

import numpy as np
from openai import OpenAI

BATCH_SIZE = 100
MAX_CHARS = 28000
MODEL = "text-embedding-3-small"


def _duster_dir(root: str) -> Path:
    path = Path(root) / ".duster"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _db_path(root: str) -> Path:
    return _duster_dir(root) / "embeddings.db"


def _ensure_gitignore(root: str) -> None:
    gitignore = Path(root) / ".gitignore"
    entry = ".duster/embeddings.db"
    if gitignore.exists():
        existing = gitignore.read_text(encoding="utf-8", errors="ignore").splitlines()
        if entry in existing:
            return
        with gitignore.open("a", encoding="utf-8") as handle:
            if existing and existing[-1] != "":
                handle.write("\n")
            handle.write(f"{entry}\n")
        return
    gitignore.write_text(f"{entry}\n", encoding="utf-8")


def _open_db(root: str) -> sqlite3.Connection:
    db = sqlite3.connect(_db_path(root))
    db.execute("CREATE TABLE IF NOT EXISTS embeddings(hash TEXT PRIMARY KEY, vector BLOB)")
    db.commit()
    return db


def _normalize_source(source: str) -> str:
    cleaned = source.strip()
    if len(cleaned) <= MAX_CHARS:
        return cleaned
    return f"{cleaned[:MAX_CHARS]}\n[truncated]"


def _hash_source(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _fetch_cached(conn: sqlite3.Connection, hash_value: str) -> list[float] | None:
    row = conn.execute("SELECT vector FROM embeddings WHERE hash = ?", (hash_value,)).fetchone()
    if row is None:
        return None
    vector = row[0]
    if isinstance(vector, str):
        return json.loads(vector)
    if isinstance(vector, bytes):
        return np.frombuffer(vector, dtype=np.float32).astype(float).tolist()
    return None


def _store_cached(conn: sqlite3.Connection, hash_value: str, vector: list[float]) -> None:
    payload = np.asarray(vector, dtype=np.float32).tobytes()
    conn.execute(
        "INSERT OR REPLACE INTO embeddings(hash, vector) VALUES (?, ?)",
        (hash_value, payload),
    )


def _embed_batch(client: OpenAI, inputs: list[str]) -> list[list[float]]:
    try:
        response = client.embeddings.create(model=MODEL, input=inputs)
    except Exception:
        time.sleep(5)
        response = client.embeddings.create(model=MODEL, input=inputs)
    return [item.embedding for item in response.data]


def embed_units(units: list[dict], root: str) -> list[dict]:
    """Add 'vector' key to each unit and return the same list."""
    if not units:
        return units

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("missing OPENAI_API_KEY environment variable")

    _duster_dir(root)
    _ensure_gitignore(root)

    conn = _open_db(root)
    try:
        pending: list[tuple[int, str, str]] = []
        for index, unit in enumerate(units):
            normalized = _normalize_source(unit.get("source", ""))
            hash_value = _hash_source(normalized)
            cached = _fetch_cached(conn, hash_value)
            if cached is not None:
                unit["vector"] = cached
                continue
            pending.append((index, hash_value, normalized))

        if pending:
            client = OpenAI(api_key=api_key)
            for start in range(0, len(pending), BATCH_SIZE):
                batch = pending[start : start + BATCH_SIZE]
                vectors = _embed_batch(client, [item[2] for item in batch])
                for (index, hash_value, _), vector in zip(batch, vectors):
                    unit = units[index]
                    unit["vector"] = vector
                    _store_cached(conn, hash_value, vector)
            conn.commit()
    finally:
        conn.close()

    return units
