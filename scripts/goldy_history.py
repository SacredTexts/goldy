#!/usr/bin/env python3
"""
Append-only loop history helpers for GOLDY.

Pattern note: append-only event replay model adapted from
ralph-orchestrator loop history concepts (MIT).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _history_path(runtime_root: Path, session_id: str) -> Path:
    history_dir = runtime_root / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    return history_dir / f"{session_id}.jsonl"


def _locked_append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    with path.open("a+", encoding="utf-8") as handle:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            handle.write(line)
            handle.write("\n")
            handle.flush()
        finally:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _read_events(path: Path) -> tuple[list[dict[str, Any]], int]:
    if not path.exists():
        return [], 0
    events: list[dict[str, Any]] = []
    malformed = 0
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        if isinstance(payload, dict):
            events.append(payload)
    events.sort(key=lambda event: int(event.get("sequence", 0)))
    return events, malformed


def append_history_event(
    runtime_root: Path,
    session_id: str,
    event_type: str,
    *,
    phase: int | None = None,
    data: dict[str, Any] | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    path = _history_path(runtime_root, session_id)
    existing, _ = _read_events(path)
    sequence = int(existing[-1].get("sequence", 0)) + 1 if existing else 1
    event = {
        "event_type": str(event_type),
        "timestamp": timestamp or _utc_now_iso(),
        "session_id": session_id,
        "phase": phase,
        "data": data or {},
        "sequence": sequence,
    }
    _locked_append_jsonl(path, event)
    return event


def replay_history(runtime_root: Path, session_id: str) -> dict[str, Any]:
    path = _history_path(runtime_root, session_id)
    events, malformed = _read_events(path)

    last_completed_phase: int | None = None
    terminal_reason: str | None = None
    resume_phase: int | None = None
    terminal_events = {"loop_failed", "loop_paused", "loop_completed"}

    for event in events:
        event_type = str(event.get("event_type", ""))
        phase = event.get("phase")
        data = event.get("data", {})
        if event_type == "phase_completed" and isinstance(phase, int):
            last_completed_phase = phase
        if event_type in terminal_events:
            if isinstance(data, dict):
                reason = data.get("reason")
                resume_candidate = data.get("resume_phase")
                if reason:
                    terminal_reason = str(reason)
                if isinstance(resume_candidate, int):
                    resume_phase = resume_candidate

    if resume_phase is None and last_completed_phase is not None:
        resume_phase = last_completed_phase + 1

    return {
        "path": str(path),
        "events": events,
        "total_valid": len(events),
        "total_malformed": malformed,
        "last_completed_phase": last_completed_phase,
        "terminal_reason": terminal_reason,
        "resume_phase": resume_phase,
    }
