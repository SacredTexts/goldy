#!/usr/bin/env python3
"""Stack profile resolution for GOLDY."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

GLOBAL_PROFILE: dict[str, Any] = {
    "name": "default-global",
    "frameworks": ["react"],
    "db": ["postgres"],
    "auth": ["workos"],
    "ui": ["radix", "shadcn"],
    "testing": ["vitest", "playwright"],
    "build": ["pnpm", "vite"],
    "routing": ["tanstack-router"],
    "rules": [
        "Use GOLD STANDARD planning template for new plans",
        "Preserve guardrails and evidence-first execution",
    ],
}

PLATFORM_DEFAULT_PROFILE: dict[str, Any] = {
    "name": "platform-default",
    "frameworks": ["tanstack-start", "react-19", "typescript"],
    "db": ["drizzle", "neon-postgres"],
    "auth": ["workos", "rbac"],
    "ui": ["radix-ui", "shadcn", "tailwind"],
    "testing": ["vitest", "playwright"],
    "build": ["pnpm", "vite"],
    "routing": ["tanstack-router", "file-based-routes"],
    "rules": [
        "Use createServerFn for server operations",
        "Validate all server input with zod",
        "Respect SSR/hydration safety in initial renders",
    ],
}


_DETECTION_MAP = {
    "@tanstack/react-start": ("frameworks", "tanstack-start"),
    "@tanstack/react-router": ("routing", "tanstack-router"),
    "react": ("frameworks", "react-19"),
    "typescript": ("frameworks", "typescript"),
    "drizzle-orm": ("db", "drizzle"),
    "@neondatabase/serverless": ("db", "neon-postgres"),
    "@workos-inc/node": ("auth", "workos"),
    "@radix-ui/react-dialog": ("ui", "radix-ui"),
    "shadcn": ("ui", "shadcn"),
    "vitest": ("testing", "vitest"),
    "playwright": ("testing", "playwright"),
    "pnpm": ("build", "pnpm"),
    "vite": ("build", "vite"),
}


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            return {}
        return json.loads(content)
    except (OSError, json.JSONDecodeError):
        return {}


def load_project_override(path: Path) -> dict[str, Any]:
    """
    Load project override profile.
    We keep .yaml extension but allow JSON content for zero-dependency parsing.
    """
    return _load_json(path)


def detect_profile(project_root: Path) -> dict[str, Any]:
    detected: dict[str, Any] = {
        "name": "auto-detected",
        "frameworks": [],
        "db": [],
        "auth": [],
        "ui": [],
        "testing": [],
        "build": [],
        "routing": [],
        "rules": [],
    }

    package_paths = [
        project_root / "package.json",
        project_root / "apps" / "web" / "package.json",
    ]

    dependencies: dict[str, Any] = {}
    for pkg_path in package_paths:
        data = _load_json(pkg_path)
        for section in ("dependencies", "devDependencies"):
            dependencies.update(data.get(section, {}))

    for dep_name in dependencies:
        mapping = _DETECTION_MAP.get(dep_name)
        if not mapping:
            continue
        category, value = mapping
        detected.setdefault(category, [])
        if value not in detected[category]:
            detected[category].append(value)

    return detected


def merge_profiles(*profiles: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge list-based stack profile fields with uniqueness."""
    merged: dict[str, Any] = {
        "name": "merged-profile",
        "frameworks": [],
        "db": [],
        "auth": [],
        "ui": [],
        "testing": [],
        "build": [],
        "routing": [],
        "rules": [],
    }

    for profile in profiles:
        if not profile:
            continue
        if profile.get("name"):
            merged["name"] = profile["name"]
        for key in (
            "frameworks",
            "db",
            "auth",
            "ui",
            "testing",
            "build",
            "routing",
            "rules",
        ):
            for value in profile.get(key, []):
                if value not in merged[key]:
                    merged[key].append(value)

    return merged


def resolve_stack_profile(project_root: Path, profile_path: Path) -> dict[str, Any]:
    project_override = load_project_override(profile_path)
    detected = detect_profile(project_root)
    return merge_profiles(GLOBAL_PROFILE, PLATFORM_DEFAULT_PROFILE, detected, project_override)
