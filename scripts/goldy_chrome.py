#!/usr/bin/env python3
"""Chrome profile resolver — internal module used by goldy_browser.py.

Resolves a Chrome profile directory from Local State by matching an email address.
Used by PlaywrightBackend to launch Chrome with the correct logged-in profile.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_EMAIL = "bodhimindflow@gmail.com"
DEFAULT_CHROME_ROOT = Path.home() / "Library" / "Application Support" / "Google" / "Chrome"
DEFAULT_LOCAL_STATE = DEFAULT_CHROME_ROOT / "Local State"


def load_local_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Local State file not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Invalid Local State payload")
    return payload


def resolve_profile_directory(email: str, local_state: dict[str, Any]) -> str:
    profile = local_state.get("profile", {}) if isinstance(local_state, dict) else {}
    info_cache = profile.get("info_cache", {}) if isinstance(profile, dict) else {}
    if not isinstance(info_cache, dict):
        raise ValueError("Local State missing profile.info_cache")

    wanted = email.strip().lower()
    for profile_dir, meta in info_cache.items():
        if not isinstance(meta, dict):
            continue
        user_name = str(meta.get("user_name", "")).strip().lower()
        if user_name == wanted:
            return str(profile_dir)

    available = [
        f"{name}:{str(meta.get('user_name', '')).strip()}"
        for name, meta in info_cache.items()
        if isinstance(meta, dict)
    ]
    raise ValueError(
        f"No Chrome profile matched email '{email}'. Available profile/user pairs: {', '.join(available) or 'none'}"
    )


def build_launch_command(profile_dir: str, url: str) -> list[str]:
    return [
        "open",
        "-na",
        "Google Chrome",
        "--args",
        f"--profile-directory={profile_dir}",
        "--new-window",
        url,
    ]


