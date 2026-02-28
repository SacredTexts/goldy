#!/usr/bin/env python3
"""Startup recovery helpers for interrupted GOLDY loop sessions."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from goldy_session import read_json, write_json


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _checkpoint_dir(runtime: dict[str, Path], session_id: str) -> Path:
    return runtime["checkpoints"] / session_id


def _checkpoint_file_for_phase(runtime: dict[str, Path], session_id: str, phase: int) -> Path:
    return _checkpoint_dir(runtime, session_id) / f"phase-{phase}.json"


def list_phase_checkpoints(runtime: dict[str, Path], session_id: str) -> list[dict[str, Any]]:
    phase_dir = _checkpoint_dir(runtime, session_id)
    if not phase_dir.exists():
        return []

    checkpoints: list[dict[str, Any]] = []
    for path in sorted(phase_dir.glob("phase-*.json")):
        payload = read_json(path, {})
        if isinstance(payload, dict):
            payload["_path"] = str(path)
            checkpoints.append(payload)
    return checkpoints


def compute_resume_phase(
    selected_phases: list[dict[str, object]],
    completed_phases: list[int] | set[int],
) -> int | None:
    selected_numbers = sorted(int(phase["phase"]) for phase in selected_phases)
    completed = {int(number) for number in completed_phases}
    for phase_number in selected_numbers:
        if phase_number not in completed:
            return phase_number
    return None


def recover_stale_running_state(
    runtime: dict[str, Path],
    session_id: str,
    session_state: dict[str, Any],
    selected_phases: list[dict[str, object]],
    *,
    mutate_files: bool = True,
) -> dict[str, Any]:
    now = _utc_now_iso()
    updated_state = deepcopy(session_state)
    changed = False
    stale_checkpoints: list[int] = []

    completed_phases = updated_state.get("completed_phases", [])
    completed_set = {int(value) for value in completed_phases if str(value).isdigit() or isinstance(value, int)}

    checkpoints = list_phase_checkpoints(runtime, session_id)
    for checkpoint in checkpoints:
        status = str(checkpoint.get("status", "")).lower()
        phase_number = int(checkpoint.get("phase", 0) or 0)
        if status == "started":
            stale_checkpoints.append(phase_number)
            checkpoint["status"] = "interrupted"
            checkpoint["reason"] = "startup_recovery:stale_running_checkpoint"
            checkpoint["recovered_at"] = now
            changed = True
            if mutate_files and phase_number > 0:
                destination = _checkpoint_file_for_phase(runtime, session_id, phase_number)
                write_json(destination, checkpoint)

    session_status = str(updated_state.get("status", "")).lower()
    if session_status == "running":
        changed = True
        updated_state["status"] = "interrupted"
        updated_state["stop_reason"] = "recovery_needed"
        updated_state["next_action"] = "resume from recovered checkpoint"
        updated_state["last_checkpoint_at"] = now

    resume_phase = compute_resume_phase(selected_phases, completed_set)
    if changed:
        recovery_payload = {
            "detected_at": now,
            "stale_checkpoints": sorted(set(stale_checkpoints)),
            "resume_phase": resume_phase,
        }
        updated_state["recovery"] = recovery_payload

    return {
        "recovered": changed,
        "resume_phase": resume_phase,
        "stale_checkpoints": sorted(set(stale_checkpoints)),
        "session_state": updated_state,
    }
