"""
GOLDY stuck-loop detection utilities.

Two-stage approach:
1) Suppress structured JSON/key-value error fields (false-positive control).
2) Extract contextual runtime error lines and require repeated-all-line matches.

Pattern note: two-stage error filtering concept adapted from
ralph-claude-code response-analyzer patterns (MIT).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from hashlib import sha1
from typing import Any

MAX_SIGNAL_WINDOW_ITEMS = 10
DEFAULT_REPEAT_THRESHOLD = 3

CONTEXTUAL_ERROR_RE = re.compile(
    r"\b(error|exception|traceback|failed|failure|denied|timeout|refused|cannot|unable|crash)\b",
    re.IGNORECASE,
)
JSON_ERROR_OBJECT_RE = re.compile(
    r'^\s*\{.*"(error|errors|message|status|code)".*\}\s*$',
    re.IGNORECASE,
)
STRUCTURED_ERROR_FIELD_RE = re.compile(
    r'^\s*["\']?(error|errors|message|status|code)["\']?\s*[:=].+$',
    re.IGNORECASE,
)
COMPLETION_SIGNAL_RE = re.compile(
    r"\b(loop_complete|completion_signal|explicit completion signal|execution complete)\b",
    re.IGNORECASE,
)
PERMISSION_DENIED_RE = re.compile(
    r"\b(permission denied|access denied|not permitted|tool permission)\b",
    re.IGNORECASE,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_line(line: str) -> str:
    compact = re.sub(r"\s+", " ", line.strip().lower())
    # Drop noisy leading log metadata (`[error]`, timestamps, etc.) for stable matching.
    compact = re.sub(r"^\[[^\]]+\]\s*", "", compact)
    compact = re.sub(r"^\d{4}-\d{2}-\d{2}[^\s]*\s*", "", compact)
    return compact


def _is_structured_error_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if JSON_ERROR_OBJECT_RE.match(stripped):
        return True
    if STRUCTURED_ERROR_FIELD_RE.match(stripped):
        return True
    return False


def extract_contextual_error_lines(text: str) -> tuple[list[str], int]:
    """Extract contextual runtime error lines and count suppressed structured false positives."""
    lines: list[str] = []
    seen: set[str] = set()
    suppressed = 0

    for raw in (text or "").splitlines():
        candidate = raw.strip()
        if not candidate:
            continue
        if _is_structured_error_line(candidate):
            suppressed += 1
            continue
        if not CONTEXTUAL_ERROR_RE.search(candidate):
            continue

        normalized = _normalize_line(candidate)
        if normalized and normalized not in seen:
            seen.add(normalized)
            lines.append(normalized)

    return lines, suppressed


def contains_completion_signal(text: str) -> bool:
    return bool(COMPLETION_SIGNAL_RE.search(text or ""))


def contains_permission_denied(text: str) -> bool:
    return bool(PERMISSION_DENIED_RE.search(text or ""))


def default_stuck_state() -> dict[str, Any]:
    return {
        "is_stuck": False,
        "detected_at": None,
        "error_fingerprint": None,
        "consecutive_matches": 0,
        "false_positive_suppressed": 0,
        "signal_window": [],
        # Internal rolling windows for repeated-all-line detection.
        "_recent_error_windows": [],
    }


def update_stuck_detection(
    state: dict[str, Any] | None,
    *,
    iteration: int,
    signal: str,
    text: str,
    signal_window_size: int = 5,
    repeat_threshold: int = DEFAULT_REPEAT_THRESHOLD,
) -> dict[str, Any]:
    """Update persisted stuck-detection state for one iteration."""
    current = dict(state or {})
    defaults = default_stuck_state()
    for key, value in defaults.items():
        current.setdefault(key, value if not isinstance(value, list) else list(value))

    bounded_window = max(1, min(MAX_SIGNAL_WINDOW_ITEMS, int(signal_window_size)))
    repeat_threshold = max(2, int(repeat_threshold))

    current_window = list(current.get("signal_window", []))
    current_window.append(
        {
            "iteration": int(iteration),
            "signal": signal,
            "timestamp": _utc_now_iso(),
        }
    )
    if len(current_window) > bounded_window:
        del current_window[:-bounded_window]
    current["signal_window"] = current_window

    error_lines, suppressed = extract_contextual_error_lines(text)
    current["false_positive_suppressed"] = int(current.get("false_positive_suppressed", 0)) + int(suppressed)

    repeated_error_match = False
    if error_lines:
        fingerprint = sha1("\n".join(error_lines).encode("utf-8")).hexdigest()[:12]
        recent_windows = list(current.get("_recent_error_windows", []))
        recent_windows.append(error_lines)
        if len(recent_windows) > repeat_threshold:
            del recent_windows[:-repeat_threshold]
        current["_recent_error_windows"] = recent_windows

        # Two-stage repeated-all-line requirement:
        # stuck only when the entire extracted error line-set repeats N times.
        if len(recent_windows) == repeat_threshold and all(window == recent_windows[0] for window in recent_windows):
            current["is_stuck"] = True
            current["detected_at"] = _utc_now_iso()
        else:
            current["is_stuck"] = False
            current["detected_at"] = None

        if len(recent_windows) >= 2 and recent_windows[-1] == recent_windows[-2]:
            repeated_error_match = True

        consecutive_matches = 1
        for idx in range(len(recent_windows) - 2, -1, -1):
            if recent_windows[idx] == recent_windows[-1]:
                consecutive_matches += 1
            else:
                break
        current["consecutive_matches"] = consecutive_matches
        current["error_fingerprint"] = fingerprint
    else:
        current["is_stuck"] = False
        current["detected_at"] = None
        current["error_fingerprint"] = None
        current["consecutive_matches"] = 0
        current["_recent_error_windows"] = []

    completion_signal = contains_completion_signal(text)
    permission_denied = contains_permission_denied(text)

    return {
        "state": current,
        "error_lines": error_lines,
        "repeated_error_match": repeated_error_match,
        "completion_signal": completion_signal,
        "permission_denied": permission_denied,
    }
