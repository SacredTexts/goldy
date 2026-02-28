#!/usr/bin/env python3
"""Session and naming helpers for GOLDY."""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SESSION_ENV_KEYS = (
    "CODEX_THREAD_ID",
    "CLAUDE_SESSION_ID",
    "CLAUDE_THREAD_ID",
    "SESSION_ID",
)


def _resolve_from_metadata(metadata: dict[str, Any] | None) -> str | None:
    if not metadata:
        return None
    for key in ("session_id", "thread_id", "last_session", "last_thread"):
        value = str(metadata.get(key, "")).strip()
        if value:
            return sanitize_id(value)
    return None


def _resolve_metadata_from_project_root(project_root: Path | None) -> str | None:
    if project_root is None:
        return None
    index_path = project_root / ".goldy" / "index.json"
    index_payload = read_json(index_path, {})
    if not isinstance(index_payload, dict):
        return None
    return _resolve_from_metadata(index_payload)


def resolve_session_id(project_root: Path | None = None, metadata: dict[str, Any] | None = None) -> str:
    """Resolve session/thread id with env-first strategy, then metadata, then uuid."""
    for key in SESSION_ENV_KEYS:
        value = os.environ.get(key, "").strip()
        if value:
            return sanitize_id(value)
    metadata_resolved = _resolve_from_metadata(metadata) or _resolve_metadata_from_project_root(project_root)
    if metadata_resolved:
        return metadata_resolved
    return str(uuid.uuid4())


def sanitize_id(value: str) -> str:
    """Keep ids filesystem-safe and deterministic."""
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-") or str(uuid.uuid4())


def utc_timestamp_compact(now: datetime | None = None) -> str:
    dt = now or datetime.now(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H-%M-%SZ")


def slugify(text: str, default: str = "session", max_len: int = 80) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    if not normalized:
        normalized = default
    return normalized[:max_len].strip("-") or default


def build_plan_filename(prompt: str, session_id: str, suffix: str = "plan") -> str:
    stamp = utc_timestamp_compact()
    prompt_slug = slugify(prompt, default="prompt")
    suffix_slug = slugify(suffix, default="plan")
    return f"{stamp}--{sanitize_id(session_id)}--{prompt_slug}-{suffix_slug}.md"


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
