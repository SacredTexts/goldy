#!/usr/bin/env python3
"""Audit policy loading and evaluation for GOLDY deep audits."""

from __future__ import annotations

import os
from copy import deepcopy
from typing import Any

from goldy_schemas import AUDIT_POLICY_DEFAULTS


AUDIT_CATEGORY_BY_ID = {
    "A1": "lint",
    "A2": "typecheck",
    "A3": "test",
    "A4": "integration",
    "A5": "robustness",
}


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _bounded_int(raw: str | None, *, default: int, low: int, high: int) -> int:
    if raw is None:
        return default
    try:
        parsed = int(raw.strip())
    except ValueError:
        return default
    return max(low, min(high, parsed))


def load_audit_policy() -> dict[str, Any]:
    policy = deepcopy(AUDIT_POLICY_DEFAULTS)
    policy["fail_fast"] = _parse_bool(os.environ.get("GOLDY_AUDIT_FAIL_FAST"), bool(policy["fail_fast"]))
    policy["required_pass_count"] = _bounded_int(
        os.environ.get("GOLDY_AUDIT_REQUIRED_PASS_COUNT"),
        default=int(policy["required_pass_count"]),
        low=0,
        high=5,
    )
    overrides = dict(policy.get("category_overrides", {}))
    for category in ("lint", "typecheck", "test", "integration", "robustness"):
        env_key = f"GOLDY_AUDIT_{category.upper()}".replace("-", "_")
        override = os.environ.get(env_key)
        if not override:
            continue
        normalized = override.strip().lower()
        if normalized in {"fail", "warn", "skip"}:
            overrides[category] = normalized
    policy["category_overrides"] = overrides
    return policy


def should_fail_fast(policy: dict[str, Any], audit_id: str, status: str) -> bool:
    if not bool(policy.get("fail_fast", False)):
        return False
    category = AUDIT_CATEGORY_BY_ID.get(audit_id)
    if category is None:
        return False
    overrides = policy.get("category_overrides", {})
    mode = str(overrides.get(category, "fail")) if isinstance(overrides, dict) else "fail"
    return status == "failed" and mode == "fail"


def evaluate_audit_policy(audits: list[dict[str, Any]], policy: dict[str, Any]) -> dict[str, Any]:
    required_pass_count = int(policy.get("required_pass_count", 5))
    overrides = policy.get("category_overrides", {})
    if not isinstance(overrides, dict):
        overrides = {}

    pass_count = 0
    blocking_failures: list[str] = []
    details: list[dict[str, Any]] = []
    for audit in audits:
        audit_id = str(audit.get("id", ""))
        status = str(audit.get("status", "failed"))
        category = AUDIT_CATEGORY_BY_ID.get(audit_id, "unknown")
        mode = str(overrides.get(category, "fail"))

        effective_pass = False
        if mode == "skip":
            effective_pass = True
        elif status == "passed":
            effective_pass = True
        elif status == "failed" and mode == "warn":
            effective_pass = True

        if effective_pass:
            pass_count += 1
        if status == "failed" and mode == "fail":
            blocking_failures.append(category)

        details.append(
            {
                "id": audit_id,
                "category": category,
                "status": status,
                "mode": mode,
                "effective_pass": effective_pass,
            }
        )

    issues: list[str] = []
    if blocking_failures:
        issues.append("blocking_failures:" + ",".join(sorted(set(blocking_failures))))
    if pass_count < required_pass_count:
        issues.append(f"required_pass_count:{pass_count}/{required_pass_count}")

    blocked = bool(issues)
    reason = "audit_policy_passed"
    if blocked:
        reason = "deep_audit_failed:policy[" + ";".join(issues) + "]"

    return {
        "blocked": blocked,
        "reason": reason,
        "issues": issues,
        "pass_count": pass_count,
        "required_pass_count": required_pass_count,
        "details": details,
        "policy": policy,
    }
