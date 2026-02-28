#!/usr/bin/env python3
"""
Loop lock + stale runtime cleanup helpers for GOLDY.

Pattern note: metadata lock-file approach adapted from ralph-orchestrator
loop lock behavior (MIT), with process-local Python safeguards.
"""

from __future__ import annotations

import json
import os
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from goldy_session import read_json, write_json

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _lock_path(runtime_root: Path) -> Path:
    runtime_root.mkdir(parents=True, exist_ok=True)
    return runtime_root / "loop.lock"


def _registry_path(runtime_root: Path) -> Path:
    runtime_root.mkdir(parents=True, exist_ok=True)
    return runtime_root / "registry.json"


def read_lock_metadata(runtime_root: Path) -> dict[str, Any] | None:
    path = _lock_path(runtime_root)
    if not path.exists():
        return None
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


class LoopLock:
    """Process-held non-blocking loop lock with metadata file payload."""

    def __init__(
        self,
        runtime_root: Path,
        session_id: str,
        *,
        plan_path: str | None = None,
        prompt_summary: str | None = None,
    ) -> None:
        self.runtime_root = runtime_root
        self.session_id = session_id
        self.plan_path = plan_path
        self.prompt_summary = prompt_summary
        self.path = _lock_path(runtime_root)
        self._handle: Any = None
        self.metadata: dict[str, Any] | None = None

    @property
    def is_held(self) -> bool:
        return self._handle is not None

    def acquire(self) -> dict[str, Any]:
        if fcntl is None:  # pragma: no cover
            raise RuntimeError("loop lock requires fcntl on this platform")

        handle = self.path.open("a+", encoding="utf-8")
        try:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                holder = read_lock_metadata(self.runtime_root) or {}
                handle.close()
                return {"status": "conflict", "holder": holder}

            payload = {
                "pid": os.getpid(),
                "session_id": self.session_id,
                "plan_path": self.plan_path,
                "acquired_at": _utc_now_iso(),
                "prompt_summary": self.prompt_summary,
                "hostname": socket.gethostname(),
            }
            handle.seek(0)
            handle.truncate(0)
            handle.write(json.dumps(payload, sort_keys=True))
            handle.flush()
            self._handle = handle
            self.metadata = payload
            return {"status": "acquired", "holder": payload}
        except Exception:
            try:
                handle.close()
            except Exception:  # pragma: no cover
                pass
            raise

    def release(self) -> None:
        if self._handle is None:
            return
        if fcntl is not None:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        self._handle.close()
        self._handle = None


def load_registry(runtime_root: Path) -> dict[str, Any]:
    path = _registry_path(runtime_root)
    payload = read_json(path, {"active_sessions": {}, "updated_at": _utc_now_iso()})
    if not isinstance(payload, dict):
        payload = {"active_sessions": {}, "updated_at": _utc_now_iso()}
    payload.setdefault("active_sessions", {})
    return payload


def write_registry(runtime_root: Path, payload: dict[str, Any]) -> None:
    data = dict(payload)
    data["updated_at"] = _utc_now_iso()
    write_json(_registry_path(runtime_root), data)


def register_active_session(
    runtime_root: Path,
    session_id: str,
    *,
    plan_path: str | None,
) -> None:
    payload = load_registry(runtime_root)
    active = payload.setdefault("active_sessions", {})
    if not isinstance(active, dict):
        active = {}
        payload["active_sessions"] = active
    active[session_id] = {
        "pid": os.getpid(),
        "plan_path": plan_path,
        "updated_at": _utc_now_iso(),
    }
    write_registry(runtime_root, payload)


def unregister_active_session(runtime_root: Path, session_id: str) -> None:
    payload = load_registry(runtime_root)
    active = payload.get("active_sessions", {})
    if isinstance(active, dict) and session_id in active:
        del active[session_id]
        write_registry(runtime_root, payload)


def cleanup_stale_runtime_artifacts(runtime: dict[str, Path]) -> dict[str, Any]:
    runtime_root = runtime["root"]
    sessions_dir = runtime["sessions"]
    summary = {
        "stale_registry_removed": 0,
        "stale_sessions_marked": 0,
        "stale_lock_cleaned": False,
    }

    registry = load_registry(runtime_root)
    active = registry.get("active_sessions", {})
    if isinstance(active, dict):
        stale_ids: list[str] = []
        for sid, info in active.items():
            pid = int(info.get("pid", 0)) if isinstance(info, dict) else 0
            if not _pid_alive(pid):
                stale_ids.append(str(sid))
        for sid in stale_ids:
            del active[sid]
            summary["stale_registry_removed"] += 1
        if stale_ids:
            write_registry(runtime_root, registry)

    if sessions_dir.exists():
        for session_file in sessions_dir.glob("*.json"):
            payload = read_json(session_file, {})
            if not isinstance(payload, dict):
                continue
            status = str(payload.get("status", "")).lower()
            owner_pid = int(payload.get("owner_pid", 0) or 0)
            if status == "running" and owner_pid and not _pid_alive(owner_pid):
                payload["status"] = "interrupted"
                payload["stop_reason"] = "stale_pid_cleanup"
                payload["next_action"] = "resume from interrupted session"
                payload["last_checkpoint_at"] = _utc_now_iso()
                payload["cleanup"] = {"stale_owner_pid": owner_pid, "cleaned_at": _utc_now_iso()}
                write_json(session_file, payload)
                summary["stale_sessions_marked"] += 1

    lock_meta = read_lock_metadata(runtime_root)
    if lock_meta and isinstance(lock_meta, dict):
        pid = int(lock_meta.get("pid", 0) or 0)
        if pid and not _pid_alive(pid):
            path = _lock_path(runtime_root)
            try:
                path.unlink(missing_ok=True)
                summary["stale_lock_cleaned"] = True
            except OSError:
                summary["stale_lock_cleaned"] = False

    return summary
