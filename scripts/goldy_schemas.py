"""
GOLDY Loop Hardening — JSON Schema Definitions

Phase 0 deliverable: canonical schema contracts for all new state artifacts.
Every schema here is the source of truth for its corresponding file format.

Attribution: Schema patterns adapted from ralph-orchestrator (MIT) with
Python-native adaptations for GOLDY's filesystem-based state model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Circuit Breaker (FR-03, FR-04, FR-05, FR-28, FR-29, FR-30)
# Adapted from: ralph-claude-code/lib/circuit_breaker.sh
# ---------------------------------------------------------------------------

class BreakerState(str, Enum):
    """Three-state circuit breaker model."""
    CLOSED = "CLOSED"          # Normal operation
    HALF_OPEN = "HALF_OPEN"    # Warning threshold reached, probation
    OPEN = "OPEN"              # Halted — requires reset or cooldown


class BreakerResetPolicy(str, Enum):
    """How the breaker transitions from OPEN back to HALF_OPEN."""
    MANUAL = "manual"          # Operator must explicitly reset
    AUTO = "auto"              # Resets after cooldown_minutes elapses


BREAKER_STATE_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "GoldyBreakerState",
    "description": "Circuit breaker persisted state for GOLDY loop.",
    "type": "object",
    "required": ["state", "session_id", "updated_at"],
    "properties": {
        "state": {
            "type": "string",
            "enum": ["CLOSED", "HALF_OPEN", "OPEN"],
        },
        "session_id": {"type": "string"},
        "updated_at": {"type": "string", "format": "date-time"},
        "opened_at": {
            "type": ["string", "null"],
            "format": "date-time",
            "description": "Timestamp when breaker entered OPEN state. Used for cooldown.",
        },
        "no_progress_streak": {
            "type": "integer",
            "minimum": 0,
            "default": 0,
        },
        "repeated_error_streak": {
            "type": "integer",
            "minimum": 0,
            "default": 0,
        },
        "permission_denial_streak": {
            "type": "integer",
            "minimum": 0,
            "default": 0,
        },
        "completion_signal_streak": {
            "type": "integer",
            "minimum": 0,
            "default": 0,
            "description": "Consecutive explicit completion signals (FR-31 safety breaker).",
        },
        "open_reason": {
            "type": ["string", "null"],
            "description": "Human-readable reason the breaker opened.",
        },
        "reset_policy": {
            "type": "string",
            "enum": ["manual", "auto"],
            "default": "auto",
        },
        "cooldown_minutes": {
            "type": "number",
            "minimum": 0,
            "default": 5,
        },
        "transition_history": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "from_state": {"type": "string"},
                    "to_state": {"type": "string"},
                    "reason": {"type": "string"},
                    "timestamp": {"type": "string", "format": "date-time"},
                },
            },
            "maxItems": 50,
            "description": "Rolling window of recent transitions.",
        },
    },
}

# Default thresholds — overridable via env/CLI (FR-29)
BREAKER_DEFAULTS: dict[str, Any] = {
    "no_progress_threshold": 3,        # Iterations with zero task progress
    "repeated_error_threshold": 3,     # Consecutive identical errors
    "permission_denial_threshold": 2,  # Permission denials (highest priority)
    "completion_signal_threshold": 3,  # Repeated explicit completion signals
    "cooldown_minutes": 5,             # Minutes before auto-reset from OPEN
    "signal_window_size": 5,           # Rolling window for trend detection
}


# ---------------------------------------------------------------------------
# Task Lifecycle (FR-08)
# ---------------------------------------------------------------------------

class TaskState(str, Enum):
    """Per-phase task lifecycle states."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# Valid transitions matrix
TASK_TRANSITIONS: dict[str, list[str]] = {
    "PENDING": ["RUNNING", "CANCELLED"],
    "RUNNING": ["COMPLETED", "FAILED", "CANCELLED"],
    "COMPLETED": [],       # Terminal
    "FAILED": ["PENDING"],  # Retry path
    "CANCELLED": [],       # Terminal
}

TASK_STATE_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "GoldyTaskState",
    "description": "Per-task lifecycle state with retry metadata.",
    "type": "object",
    "required": ["task_id", "phase", "state", "updated_at"],
    "properties": {
        "task_id": {"type": "string"},
        "phase": {"type": "integer"},
        "description": {"type": "string"},
        "state": {
            "type": "string",
            "enum": ["PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"],
        },
        "updated_at": {"type": "string", "format": "date-time"},
        "retry_count": {
            "type": "integer",
            "minimum": 0,
            "default": 0,
        },
        "max_retries": {
            "type": "integer",
            "minimum": 0,
            "default": 2,
        },
        "timeout_seconds": {
            "type": ["number", "null"],
            "description": "Per-task timeout. null means no timeout.",
        },
        "failure_reason": {
            "type": ["string", "null"],
        },
        "cancellation_reason": {
            "type": ["string", "null"],
        },
        "started_at": {
            "type": ["string", "null"],
            "format": "date-time",
        },
        "completed_at": {
            "type": ["string", "null"],
            "format": "date-time",
        },
    },
}


# ---------------------------------------------------------------------------
# History Events (FR-32)
# Adapted from: ralph-orchestrator/crates/ralph-core/src/loop_history.rs
# ---------------------------------------------------------------------------

class HistoryEventType(str, Enum):
    """Typed events for append-only JSONL history."""
    LOOP_STARTED = "loop_started"
    LOOP_PAUSED = "loop_paused"
    LOOP_COMPLETED = "loop_completed"
    LOOP_FAILED = "loop_failed"
    PHASE_STARTED = "phase_started"
    PHASE_COMPLETED = "phase_completed"
    PHASE_FAILED = "phase_failed"
    TASK_STATE_CHANGE = "task_state_change"
    BREAKER_TRANSITION = "breaker_transition"
    COMPACTION_RUN = "compaction_run"
    AUDIT_RESULT = "audit_result"
    STUCK_DETECTED = "stuck_detected"
    PERMISSION_DENIED = "permission_denied"
    DRIFT_DETECTED = "drift_detected"
    LOCK_ACQUIRED = "lock_acquired"
    LOCK_RELEASED = "lock_released"
    CHECKPOINT_WRITTEN = "checkpoint_written"
    RECOVERY_STARTED = "recovery_started"
    HANDOFF_GENERATED = "handoff_generated"
    MALFORMED_EVENT = "malformed_event"


HISTORY_EVENT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "GoldyHistoryEvent",
    "description": "Single event in .goldy/history/<session-id>.jsonl",
    "type": "object",
    "required": ["event_type", "timestamp", "session_id"],
    "properties": {
        "event_type": {
            "type": "string",
            "enum": [e.value for e in HistoryEventType],
        },
        "timestamp": {"type": "string", "format": "date-time"},
        "session_id": {"type": "string"},
        "phase": {"type": ["integer", "null"]},
        "data": {
            "type": "object",
            "description": "Event-specific payload. Structure varies by event_type.",
            "additionalProperties": True,
        },
        "sequence": {
            "type": "integer",
            "minimum": 0,
            "description": "Monotonically increasing sequence number within session.",
        },
    },
}


# ---------------------------------------------------------------------------
# Loop Lock (FR-33, FR-34)
# Adapted from: ralph-orchestrator/crates/ralph-core/src/loop_lock.rs
# ---------------------------------------------------------------------------

LOOP_LOCK_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "GoldyLoopLock",
    "description": "Lock metadata at .goldy/loop.lock for primary-loop exclusivity.",
    "type": "object",
    "required": ["pid", "session_id", "acquired_at"],
    "properties": {
        "pid": {
            "type": "integer",
            "description": "Process ID of the lock holder.",
        },
        "session_id": {"type": "string"},
        "plan_path": {"type": "string"},
        "acquired_at": {"type": "string", "format": "date-time"},
        "prompt_summary": {
            "type": ["string", "null"],
            "description": "Short description of what the lock holder is doing.",
        },
        "hostname": {
            "type": ["string", "null"],
            "description": "Machine hostname for multi-machine disambiguation.",
        },
    },
}


# ---------------------------------------------------------------------------
# Diagnostics Bundle (FR-35)
# ---------------------------------------------------------------------------

DIAGNOSTICS_BUNDLE_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "GoldyDiagnosticsBundle",
    "description": "Diagnostics bundle at .goldy/diagnostics/<timestamp>/",
    "type": "object",
    "required": ["session_id", "created_at", "categories"],
    "properties": {
        "session_id": {"type": "string"},
        "created_at": {"type": "string", "format": "date-time"},
        "enabled": {
            "type": "boolean",
            "default": False,
            "description": "Diagnostics are opt-in via --diagnostics or env flag.",
        },
        "categories": {
            "type": "object",
            "properties": {
                "agent_output": {
                    "type": "string",
                    "description": "Path to agent-output.jsonl",
                },
                "orchestration": {
                    "type": "string",
                    "description": "Path to orchestration.jsonl",
                },
                "errors": {
                    "type": "string",
                    "description": "Path to errors.jsonl",
                },
                "performance": {
                    "type": "string",
                    "description": "Path to performance.jsonl",
                },
            },
        },
    },
}


# ---------------------------------------------------------------------------
# Handoff Artifact (FR-36)
# Adapted from: ralph-orchestrator/crates/ralph-core/src/handoff.rs
# ---------------------------------------------------------------------------

HANDOFF_ARTIFACT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "GoldyHandoffArtifact",
    "description": "Deterministic handoff at .goldy/handoffs/<session-id>.md",
    "type": "object",
    "required": ["session_id", "plan_path", "created_at", "completed_tasks", "pending_tasks", "resume_command"],
    "properties": {
        "session_id": {"type": "string"},
        "plan_path": {"type": "string"},
        "created_at": {"type": "string", "format": "date-time"},
        "current_phase": {"type": ["integer", "null"]},
        "completed_phases": {
            "type": "array",
            "items": {"type": "integer"},
        },
        "completed_tasks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "phase": {"type": "integer"},
                    "description": {"type": "string"},
                    "evidence": {"type": ["string", "null"]},
                },
            },
        },
        "pending_tasks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "phase": {"type": "integer"},
                    "description": {"type": "string"},
                    "blocked_by": {"type": ["string", "null"]},
                },
            },
        },
        "stop_reason": {
            "type": ["string", "null"],
            "description": "Why execution stopped (context_budget, breaker_open, drift, etc.)",
        },
        "breaker_state": {
            "type": ["string", "null"],
            "enum": ["CLOSED", "HALF_OPEN", "OPEN", None],
        },
        "resume_command": {
            "type": "string",
            "description": "Exact CLI command to resume from this handoff.",
        },
        "worktree_path": {
            "type": ["string", "null"],
        },
    },
}


# ---------------------------------------------------------------------------
# Plan Drift Detection (FR-12)
# ---------------------------------------------------------------------------

PLAN_DRIFT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "GoldyPlanDrift",
    "description": "Plan drift detection state.",
    "type": "object",
    "required": ["source_hash", "worktree_hash", "checked_at"],
    "properties": {
        "source_hash": {
            "type": "string",
            "description": "SHA-256 of the source plan file.",
        },
        "worktree_hash": {
            "type": "string",
            "description": "SHA-256 of the worktree plan copy.",
        },
        "checked_at": {"type": "string", "format": "date-time"},
        "drifted": {"type": "boolean"},
        "action": {
            "type": "string",
            "enum": ["none", "require_resync", "auto_synced"],
        },
    },
}


# ---------------------------------------------------------------------------
# Stuck Detection (FR-06, FR-07)
# Adapted from: ralph-claude-code/lib/response_analyzer.sh
# ---------------------------------------------------------------------------

STUCK_DETECTION_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "GoldyStuckDetection",
    "description": "Stuck-loop detection state.",
    "type": "object",
    "properties": {
        "is_stuck": {"type": "boolean", "default": False},
        "detected_at": {"type": ["string", "null"], "format": "date-time"},
        "error_fingerprint": {
            "type": ["string", "null"],
            "description": "Hash of the repeated error pattern.",
        },
        "consecutive_matches": {
            "type": "integer",
            "minimum": 0,
            "default": 0,
        },
        "false_positive_suppressed": {
            "type": "integer",
            "minimum": 0,
            "default": 0,
            "description": "Count of JSON/structured-field false positives suppressed.",
        },
        "signal_window": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "iteration": {"type": "integer"},
                    "signal": {
                        "type": "string",
                        "enum": ["progress", "no_progress", "completion", "test_only", "error"],
                    },
                    "timestamp": {"type": "string", "format": "date-time"},
                },
            },
            "maxItems": 10,
            "description": "Rolling window of recent iteration signals.",
        },
    },
}


# ---------------------------------------------------------------------------
# Malformed Event Backpressure (from ralph-orchestrator/event_reader.rs)
# ---------------------------------------------------------------------------

MALFORMED_EVENT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "GoldyMalformedEvent",
    "description": "Accounting record for malformed events as backpressure signal.",
    "type": "object",
    "required": ["total_malformed", "session_id"],
    "properties": {
        "session_id": {"type": "string"},
        "total_malformed": {
            "type": "integer",
            "minimum": 0,
        },
        "total_valid": {
            "type": "integer",
            "minimum": 0,
        },
        "malformed_ratio": {
            "type": "number",
            "description": "total_malformed / (total_malformed + total_valid)",
        },
        "last_malformed_at": {
            "type": ["string", "null"],
            "format": "date-time",
        },
        "samples": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 5,
            "description": "Recent malformed event samples for debugging.",
        },
    },
}


# ---------------------------------------------------------------------------
# Audit Policy (FR-11)
# ---------------------------------------------------------------------------

AUDIT_POLICY_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "GoldyAuditPolicy",
    "description": "Configurable thresholds for the 5 deep audit categories.",
    "type": "object",
    "properties": {
        "fail_fast": {
            "type": "boolean",
            "default": False,
            "description": "Stop on first audit failure instead of running all 5.",
        },
        "required_pass_count": {
            "type": "integer",
            "minimum": 0,
            "maximum": 5,
            "default": 5,
            "description": "Minimum audits that must pass for loop completion.",
        },
        "category_overrides": {
            "type": "object",
            "description": "Per-category severity overrides (warn vs fail).",
            "properties": {
                "lint": {"type": "string", "enum": ["fail", "warn", "skip"]},
                "typecheck": {"type": "string", "enum": ["fail", "warn", "skip"]},
                "test": {"type": "string", "enum": ["fail", "warn", "skip"]},
                "integration": {"type": "string", "enum": ["fail", "warn", "skip"]},
                "robustness": {"type": "string", "enum": ["fail", "warn", "skip"]},
            },
        },
    },
}

AUDIT_POLICY_DEFAULTS: dict[str, Any] = {
    "fail_fast": False,
    "required_pass_count": 5,
    "category_overrides": {
        "lint": "fail",
        "typecheck": "fail",
        "test": "fail",
        "integration": "fail",
        "robustness": "fail",
    },
}


# ---------------------------------------------------------------------------
# Structured Stop Reasons
# ---------------------------------------------------------------------------

class StopReason(str, Enum):
    """Deterministic stop reasons for loop/phase halts."""
    CONTEXT_BUDGET = "context_below_15_percent"
    BREAKER_OPEN = "breaker_open"
    PHASE_VALIDATION_FAILED = "phase_validation_failed"
    STUCK_DETECTED = "stuck_detected"
    PERMISSION_DENIED = "permission_denied"
    PLAN_DRIFT = "plan_drift_detected"
    AUDIT_FAILED = "deep_audit_failed"
    MAX_ITERATIONS = "max_iterations_reached"
    LOCK_CONFLICT = "loop_lock_conflict"
    COMPLETION_SIGNAL_SAFETY = "completion_signal_safety_halt"
    USER_REQUESTED = "user_requested_stop"
    TASK_FAILED = "task_failed"
    RECOVERY_NEEDED = "recovery_needed"
