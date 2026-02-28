#!/usr/bin/env python3
"""Memory storage, indexing, retrieval, and compaction for GOLDY."""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

TOKEN_ESTIMATE_RATIO = 1.3
DEFAULT_TARGET_TOKENS = 1500


@dataclass(frozen=True)
class MemoryEntry:
    id: str
    text: str
    source: str
    mtime: float
    tags: tuple[str, ...] = ()


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _estimate_tokens(text: str) -> int:
    words = len(text.split())
    return max(1, int(math.ceil(words * TOKEN_ESTIMATE_RATIO)))


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_memory_layout(project_root: Path) -> dict[str, Path]:
    base = project_root / ".goldy"
    memory_dir = base / "memory"
    plans_dir = memory_dir / "plans"
    raw_dir = memory_dir / "raw"
    capsules_dir = base / "resume-capsules"
    for folder in (memory_dir, plans_dir, raw_dir, capsules_dir):
        folder.mkdir(parents=True, exist_ok=True)

    files = {
        "global": memory_dir / "global.md",
        "project": memory_dir / "project.md",
        "plans_dir": plans_dir,
        "raw_dir": raw_dir,
        "capsules_dir": capsules_dir,
        "index_db": base / "index.db",
    }

    if not files["global"].exists():
        files["global"].write_text(
            "# GOLDY Global Memory\n\n- Preserve guardrails and evidence-first execution.\n",
            encoding="utf-8",
        )
    if not files["project"].exists():
        files["project"].write_text(
            "# GOLDY Project Memory\n\n- TOC ordering is managed in Topic Manager detail view.\n",
            encoding="utf-8",
        )

    return files


def _extract_lines(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("- "):
            lines.append(line[2:].strip())
        else:
            lines.append(line)
    return [line for line in lines if line]


def _extract_jsonl_lines(path: Path, max_line_len: int = 400) -> list[str]:
    if not path.exists():
        return []
    output: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
            if isinstance(payload, dict):
                parts: list[str] = []
                for key in ("prompt", "active_plan", "intent_match", "recorded_at", "capsule_path"):
                    if key in payload and payload[key] is not None:
                        value = str(payload[key]).strip()
                        if value:
                            parts.append(f"{key}: {value[:max_line_len]}")
                line = " | ".join(parts) if parts else str(payload)[:max_line_len]
            else:
                line = str(payload)[:max_line_len]
        except json.JSONDecodeError:
            line = raw[:max_line_len]
        if line:
            output.append(line)
    return output


def _entry_id(source: str, text: str) -> str:
    digest = hashlib.sha1(f"{source}|{text}".encode("utf-8")).hexdigest()[:16]
    return f"mem-{digest}"


def load_memory_entries(project_root: Path, active_plan: Path | None) -> list[MemoryEntry]:
    paths = ensure_memory_layout(project_root)

    candidates: list[tuple[Path, str]] = [
        (paths["global"], "global"),
        (paths["project"], "project"),
    ]

    if active_plan:
        plan_memory = paths["plans_dir"] / f"{active_plan.stem}.md"
        if not plan_memory.exists():
            plan_memory.write_text(
                f"# Plan Memory: {active_plan.name}\n\n- Plan initialized at {_utc_now_iso()}\n",
                encoding="utf-8",
            )
    for plan_file in sorted(paths["plans_dir"].glob("*.md")):
        candidates.append((plan_file, f"plan:{plan_file.name}"))

    for capsule_file in sorted(paths["capsules_dir"].glob("*.md")):
        candidates.append((capsule_file, f"capsule:{capsule_file.name}"))

    entries: list[MemoryEntry] = []
    for file_path, source in candidates:
        mtime = file_path.stat().st_mtime if file_path.exists() else 0.0
        for line in _extract_lines(file_path):
            entry = MemoryEntry(
                id=_entry_id(source, line),
                text=line,
                source=source,
                mtime=mtime,
                tags=tuple(_extract_tags(line)),
            )
            entries.append(entry)

    for raw_file in sorted(paths["raw_dir"].glob("*.jsonl")):
        source = f"raw:{raw_file.name}"
        mtime = raw_file.stat().st_mtime
        for line in _extract_jsonl_lines(raw_file):
            entries.append(
                MemoryEntry(
                    id=_entry_id(source, line),
                    text=line,
                    source=source,
                    mtime=mtime,
                    tags=tuple(_extract_tags(line)),
                )
            )

    return dedupe_entries(entries)


def _extract_tags(text: str) -> list[str]:
    tags = []
    lowered = text.lower()
    for token in (
        "constraint",
        "decision",
        "assumption",
        "risk",
        "blocker",
        "todo",
        "next",
        "done",
        "evidence",
    ):
        if token in lowered:
            tags.append(token)
    return tags


def dedupe_entries(entries: Iterable[MemoryEntry]) -> list[MemoryEntry]:
    seen: dict[str, MemoryEntry] = {}
    for entry in entries:
        key = _normalize_text(entry.text)
        previous = seen.get(key)
        if not previous or entry.mtime >= previous.mtime:
            seen[key] = entry
    return list(seen.values())


def _hash_embedding(text: str, dim: int = 64) -> list[float]:
    vec = [0.0] * dim
    tokens = re.findall(r"[a-zA-Z0-9]+", text.lower())
    if not tokens:
        return vec
    for token in tokens:
        digest = hashlib.md5(token.encode("utf-8")).digest()
        for i in range(dim):
            byte = digest[i % len(digest)]
            vec[i] += 1.0 if (byte & 1) else -1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _init_index(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS memory_entries (
            id TEXT PRIMARY KEY,
            text TEXT NOT NULL,
            source TEXT NOT NULL,
            mtime REAL NOT NULL,
            tags TEXT NOT NULL,
            embedding TEXT NOT NULL
        )
        """
    )
    try:
        conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts
            USING fts5(id UNINDEXED, text, source, tags, tokenize='porter')
            """
        )
    except sqlite3.OperationalError:
        # FTS5 may be unavailable on rare python/sqlite builds.
        pass


def _upsert_index(conn: sqlite3.Connection, entries: list[MemoryEntry]) -> None:
    for entry in entries:
        embedding = json.dumps(_hash_embedding(entry.text))
        conn.execute(
            """
            INSERT INTO memory_entries (id, text, source, mtime, tags, embedding)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                text=excluded.text,
                source=excluded.source,
                mtime=excluded.mtime,
                tags=excluded.tags,
                embedding=excluded.embedding
            """,
            (entry.id, entry.text, entry.source, entry.mtime, ",".join(entry.tags), embedding),
        )
        try:
            conn.execute("DELETE FROM memory_fts WHERE id = ?", (entry.id,))
            conn.execute(
                "INSERT INTO memory_fts (id, text, source, tags) VALUES (?, ?, ?, ?)",
                (entry.id, entry.text, entry.source, ",".join(entry.tags)),
            )
        except sqlite3.OperationalError:
            pass


def _retrieve(conn: sqlite3.Connection, query: str, limit: int) -> list[MemoryEntry]:
    query_vec = _hash_embedding(query)
    fts_scores: dict[str, float] = {}

    try:
        rows = conn.execute(
            "SELECT id, bm25(memory_fts) AS rank FROM memory_fts WHERE memory_fts MATCH ? LIMIT ?",
            (query or "memory", limit * 4),
        ).fetchall()
        for row in rows:
            # bm25 lower is better; invert for higher-better score.
            rank = float(row[1]) if row[1] is not None else 100.0
            fts_scores[str(row[0])] = 1.0 / (1.0 + max(rank, 0.0))
    except sqlite3.OperationalError:
        pass

    rows = conn.execute(
        "SELECT id, text, source, mtime, tags, embedding FROM memory_entries"
    ).fetchall()

    ranked: list[tuple[float, MemoryEntry]] = []
    now = datetime.now(timezone.utc).timestamp()
    for row in rows:
        entry = MemoryEntry(
            id=str(row[0]),
            text=str(row[1]),
            source=str(row[2]),
            mtime=float(row[3]),
            tags=tuple(t for t in str(row[4]).split(",") if t),
        )
        embedding = json.loads(str(row[5]))
        semantic = _cosine(query_vec, embedding)
        lexical = fts_scores.get(entry.id, 0.0)
        recency_days = max(0.0, (now - entry.mtime) / 86400.0)
        recency = 1.0 / (1.0 + recency_days)
        score = (semantic * 0.55) + (lexical * 0.3) + (recency * 0.15)
        ranked.append((score, entry))

    ranked.sort(key=lambda item: item[0], reverse=True)
    return [entry for _, entry in ranked[:limit]]


def retrieve_ranked_entries(project_root: Path, active_plan: Path | None, query: str, limit: int = 120) -> list[MemoryEntry]:
    paths = ensure_memory_layout(project_root)
    entries = load_memory_entries(project_root, active_plan)

    conn = sqlite3.connect(paths["index_db"])
    try:
        _init_index(conn)
        _upsert_index(conn, entries)
        conn.commit()
        return _retrieve(conn, query=query, limit=limit)
    finally:
        conn.close()


def _take_budgeted(items: list[str], token_budget: int) -> list[str]:
    selected: list[str] = []
    used = 0
    for item in items:
        cost = _estimate_tokens(item)
        if used + cost > token_budget:
            continue
        selected.append(item)
        used += cost
    return selected


def build_resume_capsule(entries: list[MemoryEntry], target_tokens: int = DEFAULT_TARGET_TOKENS) -> dict[str, object]:
    mission: list[str] = []
    done: list[str] = []
    next_items: list[str] = []
    decisions: list[str] = []
    blockers: list[str] = []
    evidence_refs: list[str] = []

    for entry in entries:
        text = entry.text
        lowered = text.lower()

        refs = re.findall(r"[A-Za-z0-9_./-]+\.[A-Za-z0-9_#:-]+", text)
        evidence_refs.extend(refs)

        if any(word in lowered for word in ("mission", "goal", "objective")):
            mission.append(text)
        elif any(word in lowered for word in ("done", "completed", "[x]")):
            done.append(text)
        elif any(word in lowered for word in ("next", "todo", "[ ]", "pending")):
            next_items.append(text)
        elif any(word in lowered for word in ("decision", "assumption", "constraint", "rule")):
            decisions.append(text)
        elif any(word in lowered for word in ("blocker", "risk", "unclear", "stuck", "fail")):
            blockers.append(text)
        else:
            if len(mission) < 3:
                mission.append(text)
            else:
                next_items.append(text)

    budgets = {
        "mission": int(target_tokens * 0.12),
        "done": int(target_tokens * 0.22),
        "next": int(target_tokens * 0.24),
        "decisions": int(target_tokens * 0.18),
        "blockers": int(target_tokens * 0.16),
        "evidence": int(target_tokens * 0.08),
    }

    capsule = {
        "generated_at": _utc_now_iso(),
        "token_budget": target_tokens,
        "mission": _take_budgeted(mission, budgets["mission"]),
        "done": _take_budgeted(done, budgets["done"]),
        "next": _take_budgeted(next_items, budgets["next"]),
        "decisions": _take_budgeted(decisions, budgets["decisions"]),
        "blockers": _take_budgeted(blockers, budgets["blockers"]),
        "evidence_refs": _take_budgeted(sorted(set(evidence_refs)), budgets["evidence"]),
    }

    # Ensure required sections are never empty.
    for key in ("mission", "done", "next", "decisions", "blockers"):
        if not capsule[key]:
            capsule[key] = ["No captured items in this section yet."]

    return capsule


def capsule_to_markdown(capsule: dict[str, object]) -> str:
    lines = [
        "# PREVIOUS_SESSION_RESUME",
        "",
        f"- generated_at: {capsule['generated_at']}",
        f"- token_budget: {capsule['token_budget']}",
        "",
    ]

    for section in ("mission", "done", "next", "decisions", "blockers", "evidence_refs"):
        title = section.replace("_", " ").title()
        lines.append(f"## {title}")
        for item in capsule.get(section, []):
            lines.append(f"- {item}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def save_capsule(project_root: Path, session_id: str, capsule: dict[str, object]) -> Path:
    paths = ensure_memory_layout(project_root)
    out_file = paths["capsules_dir"] / f"{session_id}.md"
    out_file.write_text(capsule_to_markdown(capsule), encoding="utf-8")

    out_json = paths["capsules_dir"] / f"{session_id}.json"
    out_json.write_text(json.dumps(capsule, indent=2, sort_keys=True), encoding="utf-8")
    return out_file


def append_raw_memory(project_root: Path, session_id: str, payload: dict[str, object]) -> Path:
    paths = ensure_memory_layout(project_root)
    raw_file = paths["raw_dir"] / f"{session_id}.jsonl"
    record = dict(payload)
    record["recorded_at"] = _utc_now_iso()
    with raw_file.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
    return raw_file
