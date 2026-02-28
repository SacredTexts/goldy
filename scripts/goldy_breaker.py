"""
GOLDY Circuit Breaker — Three-state loop protection.

Adapted from ralph-claude-code/lib/circuit_breaker.sh (MIT).
Python-native implementation with JSON persistence and configurable thresholds.

States: CLOSED (normal) → HALF_OPEN (warning) → OPEN (halted)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from goldy_schemas import BreakerState, BreakerResetPolicy, BREAKER_DEFAULTS
from goldy_session import read_json, write_json


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        # Handle both Z suffix and +00:00
        cleaned = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned)
    except (ValueError, TypeError):
        return None


def _load_thresholds() -> dict[str, Any]:
    """Load breaker thresholds from environment, falling back to defaults."""
    result = dict(BREAKER_DEFAULTS)
    env_map = {
        "GOLDY_BREAKER_NO_PROGRESS_THRESHOLD": ("no_progress_threshold", int),
        "GOLDY_BREAKER_REPEATED_ERROR_THRESHOLD": ("repeated_error_threshold", int),
        "GOLDY_BREAKER_PERMISSION_DENIAL_THRESHOLD": ("permission_denial_threshold", int),
        "GOLDY_BREAKER_COMPLETION_SIGNAL_THRESHOLD": ("completion_signal_threshold", int),
        "GOLDY_BREAKER_COOLDOWN_MINUTES": ("cooldown_minutes", float),
        "GOLDY_BREAKER_SIGNAL_WINDOW_SIZE": ("signal_window_size", int),
    }
    for env_key, (field, cast) in env_map.items():
        val = os.environ.get(env_key, "").strip()
        if val:
            try:
                result[field] = cast(val)
            except (ValueError, TypeError):
                pass
    return result


class CircuitBreaker:
    """Persisted three-state circuit breaker for GOLDY loop protection.

    File: .goldy/breaker.json
    """

    def __init__(self, runtime_root: Path, session_id: str, thresholds: dict[str, Any] | None = None):
        self.runtime_root = runtime_root
        self.session_id = session_id
        self.state_path = runtime_root / "breaker.json"
        self.thresholds = thresholds or _load_thresholds()
        self._state = self._load_or_init()

    def _load_or_init(self) -> dict[str, Any]:
        """Load persisted state or initialize fresh CLOSED state."""
        if self.state_path.exists():
            loaded = read_json(self.state_path, {})
            if isinstance(loaded, dict) and "state" in loaded:
                # Ensure all fields exist (backward compat with older state files)
                loaded.setdefault("no_progress_streak", 0)
                loaded.setdefault("repeated_error_streak", 0)
                loaded.setdefault("permission_denial_streak", 0)
                loaded.setdefault("completion_signal_streak", 0)
                loaded.setdefault("opened_at", None)
                loaded.setdefault("open_reason", None)
                loaded.setdefault("reset_policy", BreakerResetPolicy.AUTO.value)
                loaded.setdefault("cooldown_minutes", self.thresholds["cooldown_minutes"])
                loaded.setdefault("transition_history", [])
                return loaded
        return self._fresh_state()

    def _fresh_state(self) -> dict[str, Any]:
        return {
            "state": BreakerState.CLOSED.value,
            "session_id": self.session_id,
            "updated_at": _utc_now_iso(),
            "opened_at": None,
            "no_progress_streak": 0,
            "repeated_error_streak": 0,
            "permission_denial_streak": 0,
            "completion_signal_streak": 0,
            "open_reason": None,
            "reset_policy": BreakerResetPolicy.AUTO.value,
            "cooldown_minutes": self.thresholds["cooldown_minutes"],
            "transition_history": [],
        }

    def _persist(self) -> None:
        self._state["updated_at"] = _utc_now_iso()
        self._state["session_id"] = self.session_id
        write_json(self.state_path, self._state)

    def _record_transition(self, from_state: str, to_state: str, reason: str) -> None:
        history = self._state.setdefault("transition_history", [])
        history.append({
            "from_state": from_state,
            "to_state": to_state,
            "reason": reason,
            "timestamp": _utc_now_iso(),
        })
        # Keep rolling window of last 50 transitions
        if len(history) > 50:
            del history[:-50]

    # ── Public state queries ──────────────────────────────────────────

    @property
    def current_state(self) -> str:
        return self._state.get("state", BreakerState.CLOSED.value)

    @property
    def is_open(self) -> bool:
        return self.current_state == BreakerState.OPEN.value

    @property
    def is_closed(self) -> bool:
        return self.current_state == BreakerState.CLOSED.value

    def can_execute(self) -> bool:
        """Whether the loop can proceed (not OPEN, or cooldown elapsed)."""
        if self.current_state != BreakerState.OPEN.value:
            return True
        # Check cooldown for auto-reset policy
        if self._state.get("reset_policy") == BreakerResetPolicy.AUTO.value:
            return self._cooldown_elapsed()
        return False

    def _cooldown_elapsed(self) -> bool:
        opened_at = _parse_iso(self._state.get("opened_at"))
        if opened_at is None:
            # Legacy state without opened_at — treat as cooldown elapsed (FR-30 backward compat)
            return True
        cooldown = float(self._state.get("cooldown_minutes", self.thresholds["cooldown_minutes"]))
        elapsed = (_utc_now() - opened_at).total_seconds() / 60.0
        return elapsed >= cooldown

    # ── State transitions ─────────────────────────────────────────────

    def _transition(self, new_state: str, reason: str) -> None:
        old_state = self.current_state
        if old_state == new_state:
            return
        self._record_transition(old_state, new_state, reason)
        self._state["state"] = new_state
        if new_state == BreakerState.OPEN.value:
            self._state["opened_at"] = _utc_now_iso()
            self._state["open_reason"] = reason
        elif new_state == BreakerState.CLOSED.value:
            self._state["opened_at"] = None
            self._state["open_reason"] = None
            self._state["no_progress_streak"] = 0
            self._state["repeated_error_streak"] = 0
            self._state["permission_denial_streak"] = 0
            self._state["completion_signal_streak"] = 0
        self._persist()

    def record_iteration(
        self,
        had_progress: bool = False,
        had_error: bool = False,
        same_error: bool = False,
        permission_denied: bool = False,
        completion_signal: bool = False,
    ) -> dict[str, Any]:
        """Record loop iteration result and evaluate breaker transitions.

        Returns dict with 'tripped' flag and 'reason' if breaker opens.
        """
        # Update streaks
        if had_progress:
            self._state["no_progress_streak"] = 0
            self._state["repeated_error_streak"] = 0
            self._state["completion_signal_streak"] = 0
        else:
            self._state["no_progress_streak"] = int(self._state.get("no_progress_streak", 0)) + 1

        if same_error:
            self._state["repeated_error_streak"] = int(self._state.get("repeated_error_streak", 0)) + 1
        elif not had_error:
            self._state["repeated_error_streak"] = 0

        if permission_denied:
            self._state["permission_denial_streak"] = int(self._state.get("permission_denial_streak", 0)) + 1
        else:
            self._state["permission_denial_streak"] = 0

        if completion_signal:
            self._state["completion_signal_streak"] = int(self._state.get("completion_signal_streak", 0)) + 1
        else:
            self._state["completion_signal_streak"] = 0

        self._persist()

        # Evaluate transitions — permission denial is HIGHEST PRIORITY
        return self._evaluate_thresholds()

    def _evaluate_thresholds(self) -> dict[str, Any]:
        """Check streaks against thresholds and trigger transitions."""
        thresholds = self.thresholds
        state = self.current_state

        # Permission denial — highest priority (checked first)
        perm_streak = int(self._state.get("permission_denial_streak", 0))
        perm_threshold = int(thresholds["permission_denial_threshold"])
        if perm_streak >= perm_threshold:
            reason = f"permission_denied({perm_streak}):update tool permissions and reset breaker"
            if state != BreakerState.OPEN.value:
                self._transition(BreakerState.OPEN.value, reason)
            return {"tripped": True, "reason": reason, "trigger": "permission_denial"}

        # Repeated explicit completion signal (safety breaker)
        completion_streak = int(self._state.get("completion_signal_streak", 0))
        completion_threshold = int(thresholds["completion_signal_threshold"])
        if completion_streak >= completion_threshold:
            reason = (
                f"completion_signal({completion_streak}):verify completion state and reset breaker if safe"
            )
            if state != BreakerState.OPEN.value:
                self._transition(BreakerState.OPEN.value, reason)
            return {"tripped": True, "reason": reason, "trigger": "completion_signal"}

        # Repeated same error
        error_streak = int(self._state.get("repeated_error_streak", 0))
        error_threshold = int(thresholds["repeated_error_threshold"])

        # No progress
        noprog_streak = int(self._state.get("no_progress_streak", 0))
        noprog_threshold = int(thresholds["no_progress_threshold"])

        # Transition logic depends on current state
        if state == BreakerState.CLOSED.value:
            # CLOSED → HALF_OPEN on warning thresholds
            if noprog_streak >= max(1, noprog_threshold - 1):
                reason = f"no_progress({noprog_streak}):approaching threshold"
                self._transition(BreakerState.HALF_OPEN.value, reason)
                return {"tripped": False, "reason": reason, "trigger": "no_progress_warning"}

            if error_streak >= max(1, error_threshold - 1):
                reason = f"repeated_error({error_streak}):approaching threshold"
                self._transition(BreakerState.HALF_OPEN.value, reason)
                return {"tripped": False, "reason": reason, "trigger": "error_warning"}

        elif state == BreakerState.HALF_OPEN.value:
            # HALF_OPEN → CLOSED if progress detected
            if int(self._state.get("no_progress_streak", 0)) == 0:
                self._transition(BreakerState.CLOSED.value, "progress_detected:recovered")
                return {"tripped": False, "reason": "recovered", "trigger": "progress"}

            # HALF_OPEN → OPEN on sustained no progress
            if noprog_streak >= noprog_threshold:
                reason = f"no_progress({noprog_streak}):threshold_exceeded"
                self._transition(BreakerState.OPEN.value, reason)
                return {"tripped": True, "reason": reason, "trigger": "no_progress"}

            if error_streak >= error_threshold:
                reason = f"repeated_error({error_streak}):threshold_exceeded"
                self._transition(BreakerState.OPEN.value, reason)
                return {"tripped": True, "reason": reason, "trigger": "repeated_error"}

        elif state == BreakerState.OPEN.value:
            # OPEN → HALF_OPEN after cooldown (auto policy)
            if self._state.get("reset_policy") == BreakerResetPolicy.AUTO.value and self._cooldown_elapsed():
                self._transition(BreakerState.HALF_OPEN.value, "cooldown_elapsed:auto_recovery")
                return {"tripped": False, "reason": "auto_recovery", "trigger": "cooldown"}

        return {"tripped": False, "reason": "ok", "trigger": "none"}

    # ── Operator controls ─────────────────────────────────────────────

    def reset(self, reason: str = "operator_reset") -> None:
        """Manual operator reset — returns breaker to CLOSED."""
        self._transition(BreakerState.CLOSED.value, reason)

    def startup_check(self, auto_reset: bool = False) -> dict[str, Any]:
        """Run on loop startup to handle stale OPEN states.

        If auto_reset=True, immediately reset to CLOSED.
        Otherwise, check cooldown for auto-recovery.
        """
        if self.current_state != BreakerState.OPEN.value:
            return {"action": "none", "state": self.current_state}

        if auto_reset:
            self._transition(BreakerState.CLOSED.value, "startup_auto_reset")
            return {"action": "auto_reset", "state": BreakerState.CLOSED.value}

        if self._state.get("reset_policy") == BreakerResetPolicy.AUTO.value and self._cooldown_elapsed():
            self._transition(BreakerState.HALF_OPEN.value, "startup_cooldown_recovery")
            return {"action": "cooldown_recovery", "state": BreakerState.HALF_OPEN.value}

        return {
            "action": "blocked",
            "state": BreakerState.OPEN.value,
            "reason": self._state.get("open_reason", "unknown"),
            "opened_at": self._state.get("opened_at"),
        }

    def status(self) -> dict[str, Any]:
        """Return structured status for operator display."""
        return {
            "state": self.current_state,
            "session_id": self._state.get("session_id"),
            "updated_at": self._state.get("updated_at"),
            "opened_at": self._state.get("opened_at"),
            "open_reason": self._state.get("open_reason"),
            "no_progress_streak": int(self._state.get("no_progress_streak", 0)),
            "repeated_error_streak": int(self._state.get("repeated_error_streak", 0)),
            "permission_denial_streak": int(self._state.get("permission_denial_streak", 0)),
            "completion_signal_streak": int(self._state.get("completion_signal_streak", 0)),
            "reset_policy": self._state.get("reset_policy", "auto"),
            "cooldown_minutes": float(self._state.get("cooldown_minutes", 5)),
            "thresholds": self.thresholds,
            "transition_count": len(self._state.get("transition_history", [])),
        }

    def print_status(self) -> None:
        """Print human-readable status to stdout."""
        s = self.status()
        print("=== GOLDY BREAKER STATUS ===")
        print(f"state: {s['state']}")
        print(f"session_id: {s['session_id']}")
        print(f"updated_at: {s['updated_at']}")
        if s["opened_at"]:
            print(f"opened_at: {s['opened_at']}")
        if s["open_reason"]:
            print(f"open_reason: {s['open_reason']}")
        print(f"no_progress_streak: {s['no_progress_streak']}")
        print(f"repeated_error_streak: {s['repeated_error_streak']}")
        print(f"permission_denial_streak: {s['permission_denial_streak']}")
        print(f"completion_signal_streak: {s['completion_signal_streak']}")
        print(f"reset_policy: {s['reset_policy']}")
        print(f"cooldown_minutes: {s['cooldown_minutes']}")
        print(f"transition_count: {s['transition_count']}")
