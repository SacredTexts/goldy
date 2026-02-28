#!/usr/bin/env python3
"""Permission/tool-denial classifier for breaker and operator remediation."""

from __future__ import annotations

import re
from typing import Any

PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("permission_denied", re.compile(r"\bpermission denied\b", re.IGNORECASE)),
    ("access_denied", re.compile(r"\baccess denied\b", re.IGNORECASE)),
    ("not_permitted", re.compile(r"\bnot permitted\b", re.IGNORECASE)),
    ("tool_permission", re.compile(r"\btool permission\b", re.IGNORECASE)),
    ("approval_policy", re.compile(r"\bapproval policy\b", re.IGNORECASE)),
    ("insufficient_permissions", re.compile(r"\binsufficient permissions\b", re.IGNORECASE)),
]


def classify_permission_denial(text: str) -> dict[str, Any]:
    source = text or ""
    matched: list[str] = []
    for label, pattern in PATTERNS:
        if pattern.search(source):
            matched.append(label)

    denied = bool(matched)
    if denied:
        summary = "permission/tool denial detected"
        remediation = [
            "Verify required tool permissions for this loop.",
            "Resolve the permission denial cause in environment/policy.",
            "Reset breaker and resume: /goldy-loop --breaker-reset --project-root <path>",
        ]
    else:
        summary = "no permission/tool denial signals"
        remediation = []

    return {
        "permission_denied": denied,
        "signals": sorted(set(matched)),
        "summary": summary,
        "remediation": remediation,
    }
