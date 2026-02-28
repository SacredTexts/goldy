#!/usr/bin/env python3
"""Task lifecycle state machine + evidence backpressure helpers for GOLDY loop."""

from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from goldy_schemas import TASK_TRANSITIONS, TaskState
from goldy_session import write_json

CHECKLIST_RE = re.compile(r"^\s*-\s*\[([ xX~])\]\s*(.+)$", re.MULTILINE)
WEAK_EVIDENCE_RE = re.compile(r"(___/___|\b(?:todo|tbd|placeholder|pending)\b)", re.IGNORECASE)
CLAIM_LINE_RE = re.compile(
    r"^\s*(?:-\s*\[[ xX~]\]\s*)?(?:Validation gate|Evidence)\s*:\s*(.+)$",
    re.IGNORECASE | re.MULTILINE,
)
RATIO_RE = re.compile(r"\b(\d+)\s*/\s*(\d+)\b")
WAIVER_REASON_RE = re.compile(r"\(waive[dr]\s*:\s*([^)]+)\)", re.IGNORECASE)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _phase_block(plan_path: Path, phase: dict[str, object]) -> str:
    lines = plan_path.read_text(encoding="utf-8").splitlines()
    start = max(0, int(phase["start_line"]) - 1)
    end = min(len(lines), int(phase["end_line"]))
    return "\n".join(lines[start:end])


def _default_timeout_seconds() -> float | None:
    raw = os.environ.get("GOLDY_TASK_TIMEOUT_SECONDS", "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _default_max_retries() -> int:
    raw = os.environ.get("GOLDY_TASK_MAX_RETRIES", "").strip()
    if not raw:
        return 2
    try:
        parsed = int(raw)
        return parsed if parsed >= 0 else 2
    except ValueError:
        return 2


def extract_phase_checklist(plan_path: Path, phase: dict[str, object]) -> list[dict[str, Any]]:
    phase_number = int(phase["phase"])
    block = _phase_block(plan_path, phase)
    items: list[dict[str, Any]] = []
    for index, (mark, task_text) in enumerate(CHECKLIST_RE.findall(block), start=1):
        normalized_mark = "x" if mark.lower() == "x" else ("~" if mark == "~" else " ")
        items.append(
            {
                "task_id": f"phase-{phase_number}-task-{index}",
                "phase": phase_number,
                "mark": normalized_mark,
                "description": task_text.strip(),
            }
        )
    return items


def new_task_record(
    task_id: str,
    phase: int,
    description: str,
    *,
    timeout_seconds: float | None = None,
    max_retries: int | None = None,
    now_iso: str | None = None,
) -> dict[str, Any]:
    now = now_iso or _utc_now_iso()
    retries = _default_max_retries() if max_retries is None else max(0, int(max_retries))
    return {
        "task_id": task_id,
        "phase": int(phase),
        "description": description,
        "state": TaskState.PENDING.value,
        "updated_at": now,
        "retry_count": 0,
        "max_retries": retries,
        "timeout_seconds": _default_timeout_seconds() if timeout_seconds is None else timeout_seconds,
        "failure_reason": None,
        "cancellation_reason": None,
        "started_at": None,
        "completed_at": None,
    }


def is_valid_transition(from_state: str, to_state: str) -> bool:
    from_key = str(from_state).upper()
    to_key = str(to_state).upper()
    allowed = TASK_TRANSITIONS.get(from_key, [])
    return to_key in allowed


def transition_task(
    task: dict[str, Any],
    to_state: str,
    *,
    reason: str | None = None,
    timeout_seconds: float | None = None,
    max_retries: int | None = None,
    timestamp: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    now = timestamp or _utc_now_iso()
    from_state = str(task.get("state", TaskState.PENDING.value)).upper()
    target_state = str(to_state).upper()
    task_id = str(task.get("task_id", "unknown-task"))
    if not is_valid_transition(from_state, target_state):
        raise ValueError(f"invalid_task_transition:{from_state}->{target_state} for {task_id}")

    updated = deepcopy(task)
    updated["state"] = target_state
    updated["updated_at"] = now
    updated["retry_count"] = int(updated.get("retry_count", 0))
    updated["max_retries"] = (
        max(0, int(max_retries))
        if max_retries is not None
        else int(updated.get("max_retries", _default_max_retries()))
    )
    if timeout_seconds is not None:
        updated["timeout_seconds"] = timeout_seconds
    else:
        updated.setdefault("timeout_seconds", _default_timeout_seconds())
    updated.setdefault("failure_reason", None)
    updated.setdefault("cancellation_reason", None)
    updated.setdefault("started_at", None)
    updated.setdefault("completed_at", None)

    if from_state == TaskState.FAILED.value and target_state == TaskState.PENDING.value:
        updated["retry_count"] = int(updated.get("retry_count", 0)) + 1
        updated["failure_reason"] = None
    if target_state == TaskState.RUNNING.value and updated.get("started_at") is None:
        updated["started_at"] = now
    if target_state == TaskState.COMPLETED.value:
        updated["completed_at"] = now
        updated["failure_reason"] = None
        updated["cancellation_reason"] = None
    elif target_state == TaskState.FAILED.value:
        updated["failure_reason"] = reason or "task_failed"
    elif target_state == TaskState.CANCELLED.value:
        updated["completed_at"] = now
        updated["cancellation_reason"] = reason or "task_cancelled"
        updated["failure_reason"] = None

    event = {
        "event_type": "task_state_change",
        "phase": int(updated.get("phase", 0)),
        "task_id": task_id,
        "from_state": from_state,
        "to_state": target_state,
        "timestamp": now,
        "reason": reason,
        "retry_count": int(updated.get("retry_count", 0)),
        "timeout_seconds": updated.get("timeout_seconds"),
    }
    return updated, event


def _task_waiver_reason(description: str) -> str:
    match = WAIVER_REASON_RE.search(description)
    if match:
        reason = match.group(1).strip()
        if reason:
            return reason
    return "waived_in_plan"


def _normalize_task(existing: dict[str, Any], *, timeout_seconds: float | None, max_retries: int, now: str) -> dict[str, Any]:
    task = deepcopy(existing)
    task.setdefault("state", TaskState.PENDING.value)
    task.setdefault("updated_at", now)
    task["retry_count"] = int(task.get("retry_count", 0))
    task["max_retries"] = int(task.get("max_retries", max_retries))
    if task.get("timeout_seconds") is None and timeout_seconds is not None:
        task["timeout_seconds"] = timeout_seconds
    task.setdefault("failure_reason", None)
    task.setdefault("cancellation_reason", None)
    task.setdefault("started_at", None)
    task.setdefault("completed_at", None)
    return task


def _ensure_running(task: dict[str, Any], now: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    state = str(task.get("state", TaskState.PENDING.value))
    if state == TaskState.RUNNING.value:
        return task
    if state == TaskState.PENDING.value:
        task, event = transition_task(task, TaskState.RUNNING.value, timestamp=now)
        events.append(event)
    return task


def _handle_mark_unchecked(task: dict[str, Any], now: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    state = str(task.get("state", TaskState.PENDING.value))
    retry_count = int(task.get("retry_count", 0))
    max_retries = int(task.get("max_retries", _default_max_retries()))

    if state == TaskState.FAILED.value and retry_count >= max_retries:
        return task

    if state == TaskState.FAILED.value:
        task, event = transition_task(task, TaskState.PENDING.value, reason="retry_after_failure", timestamp=now)
        events.append(event)
        state = TaskState.PENDING.value

    if state == TaskState.PENDING.value:
        task, event = transition_task(task, TaskState.RUNNING.value, timestamp=now)
        events.append(event)
        state = TaskState.RUNNING.value

    if state == TaskState.RUNNING.value:
        task, event = transition_task(task, TaskState.FAILED.value, reason="unchecked_task", timestamp=now)
        events.append(event)

    return task


def _handle_mark_checked(task: dict[str, Any], now: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    state = str(task.get("state", TaskState.PENDING.value))
    if state == TaskState.COMPLETED.value:
        return task
    if state == TaskState.FAILED.value:
        task, event = transition_task(task, TaskState.PENDING.value, reason="retry_after_failure", timestamp=now)
        events.append(event)
        state = TaskState.PENDING.value

    task = _ensure_running(task, now, events)
    state = str(task.get("state", TaskState.PENDING.value))
    if state == TaskState.RUNNING.value:
        task, event = transition_task(task, TaskState.COMPLETED.value, reason="validated_checklist_item", timestamp=now)
        events.append(event)
    return task


def _handle_mark_waived(task: dict[str, Any], description: str, now: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    state = str(task.get("state", TaskState.PENDING.value))
    if state == TaskState.CANCELLED.value:
        return task
    if state == TaskState.FAILED.value:
        task, event = transition_task(task, TaskState.PENDING.value, reason="retry_after_failure", timestamp=now)
        events.append(event)

    task = _ensure_running(task, now, events)
    if str(task.get("state", TaskState.PENDING.value)) == TaskState.RUNNING.value:
        task, event = transition_task(
            task,
            TaskState.CANCELLED.value,
            reason=_task_waiver_reason(description),
            timestamp=now,
        )
        events.append(event)
    return task


def aggregate_phase_lifecycle(tasks: list[dict[str, Any]], events: list[dict[str, Any]]) -> dict[str, Any]:
    states = {
        TaskState.PENDING.value: 0,
        TaskState.RUNNING.value: 0,
        TaskState.COMPLETED.value: 0,
        TaskState.FAILED.value: 0,
        TaskState.CANCELLED.value: 0,
    }
    retry_total = 0
    timeout_count = 0
    blocked_by_retry_limit: list[str] = []
    for task in tasks:
        state = str(task.get("state", TaskState.PENDING.value)).upper()
        if state in states:
            states[state] += 1
        retry_count = int(task.get("retry_count", 0))
        retry_total += retry_count
        if task.get("timeout_seconds") is not None:
            timeout_count += 1
        if state == TaskState.FAILED.value and retry_count >= int(task.get("max_retries", _default_max_retries())):
            blocked_by_retry_limit.append(str(task.get("task_id")))
    return {
        "total_tasks": len(tasks),
        "states": states,
        "retry_attempts_total": retry_total,
        "timeout_configured_count": timeout_count,
        "events_total": len(events),
        "blocked_by_retry_limit": sorted(blocked_by_retry_limit),
    }


def evaluate_phase_task_lifecycle(
    *,
    plan_path: Path,
    phase: dict[str, object],
    previous_payload: dict[str, Any] | None = None,
    timeout_seconds: float | None = None,
    max_retries: int | None = None,
) -> dict[str, Any]:
    now = _utc_now_iso()
    timeout_value = _default_timeout_seconds() if timeout_seconds is None else timeout_seconds
    retries = _default_max_retries() if max_retries is None else max(0, int(max_retries))
    checklist = extract_phase_checklist(plan_path, phase)
    phase_number = int(phase["phase"])

    previous = previous_payload if isinstance(previous_payload, dict) else {}
    previous_tasks = previous.get("tasks", []) if isinstance(previous.get("tasks", []), list) else []
    previous_events = previous.get("events", []) if isinstance(previous.get("events", []), list) else []
    previous_by_id = {
        str(item.get("task_id")): item for item in previous_tasks if isinstance(item, dict) and item.get("task_id")
    }

    tasks: list[dict[str, Any]] = []
    new_events: list[dict[str, Any]] = []
    for item in checklist:
        task_id = str(item["task_id"])
        description = str(item["description"])
        existing = previous_by_id.get(task_id)
        task = (
            _normalize_task(existing, timeout_seconds=timeout_value, max_retries=retries, now=now)
            if existing
            else new_task_record(
                task_id=task_id,
                phase=phase_number,
                description=description,
                timeout_seconds=timeout_value,
                max_retries=retries,
                now_iso=now,
            )
        )
        task["description"] = description

        mark = str(item.get("mark", " "))
        if mark == "x":
            task = _handle_mark_checked(task, now, new_events)
        elif mark == "~":
            task = _handle_mark_waived(task, description, now, new_events)
        else:
            task = _handle_mark_unchecked(task, now, new_events)
        tasks.append(task)

    prior_sequence = 0
    for event in previous_events:
        if isinstance(event, dict):
            prior_sequence = max(prior_sequence, int(event.get("sequence", 0) or 0))
    sequenced_new: list[dict[str, Any]] = []
    for index, event in enumerate(new_events, start=1):
        payload = deepcopy(event)
        payload["sequence"] = prior_sequence + index
        sequenced_new.append(payload)

    events = [event for event in previous_events if isinstance(event, dict)] + sequenced_new
    events = sorted(events, key=lambda item: (int(item.get("sequence", 0)), str(item.get("timestamp", ""))))
    if len(events) > 200:
        events = events[-200:]

    tasks_sorted = sorted(tasks, key=lambda item: str(item.get("task_id", "")))
    summary = aggregate_phase_lifecycle(tasks_sorted, events)
    payload = {
        "phase": phase_number,
        "updated_at": now,
        "tasks": tasks_sorted,
        "events": events,
        "summary": summary,
    }
    return {
        "payload": payload,
        "summary": summary,
        "new_events": sequenced_new,
        "tasks": tasks_sorted,
    }


def persist_phase_task_lifecycle(
    runtime: dict[str, Path],
    session_id: str,
    phase_number: int,
    payload: dict[str, Any],
) -> Path:
    phase_dir = runtime["checkpoints"] / session_id
    phase_dir.mkdir(parents=True, exist_ok=True)
    destination = phase_dir / f"phase-{phase_number}-tasks.json"

    canonical = deepcopy(payload)
    events = canonical.get("events", [])
    if isinstance(events, list):
        canonical["events"] = sorted(
            [item for item in events if isinstance(item, dict)],
            key=lambda item: (int(item.get("sequence", 0)), str(item.get("timestamp", ""))),
        )
    tasks = canonical.get("tasks", [])
    if isinstance(tasks, list):
        canonical["tasks"] = sorted(
            [item for item in tasks if isinstance(item, dict)],
            key=lambda item: str(item.get("task_id", "")),
        )

    write_json(destination, canonical)
    return destination


def parse_evidence_backpressure(phase_block: str) -> dict[str, Any]:
    claims = [match.group(1).strip() for match in CLAIM_LINE_RE.finditer(phase_block)]
    joined = " ".join(claims).strip()
    issues: list[str] = []

    weak_tokens = sorted(set(match.group(0).lower() for match in WEAK_EVIDENCE_RE.finditer(joined)))
    if weak_tokens:
        issues.append("placeholder_claims")

    ratios: list[str] = []
    for left_raw, right_raw in RATIO_RE.findall(joined):
        left = int(left_raw)
        right = int(right_raw)
        ratios.append(f"{left}/{right}")
        if right > 0 and left < right:
            issues.append(f"incomplete_ratio:{left}/{right}")

    if "deep audit" in joined.lower() and "5" not in joined:
        issues.append("audit_count_unspecified")

    status = "blocked" if issues else "ok"
    return {
        "status": status,
        "issues": sorted(set(issues)),
        "claims": claims,
        "ratios": sorted(set(ratios)),
        "checked_at": _utc_now_iso(),
    }


def apply_evidence_backpressure(validation_result: dict[str, Any], phase_block: str) -> dict[str, Any]:
    report = parse_evidence_backpressure(phase_block)
    merged = deepcopy(validation_result)
    merged["evidence_backpressure"] = report
    if bool(merged.get("validated")) and report["status"] == "blocked":
        issue_preview = ",".join(report["issues"][:3]) if report["issues"] else "unverified_claims"
        merged["validated"] = False
        merged["reason"] = f"phase_validation_failed:evidence_backpressure[{issue_preview}]"
    return merged


def serialize_task_event(event: dict[str, Any]) -> str:
    return json.dumps(event, sort_keys=True, separators=(",", ":"))
