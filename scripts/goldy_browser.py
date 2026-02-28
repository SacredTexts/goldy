#!/usr/bin/env python3
"""Browser abstraction layer for GOLDY — supports Chrome Extension (Claude Code) and Playwright (Codex).

Two execution models:
- ChromeExtensionBackend: Emits JSON protocol instructions for Claude Code to execute via MCP tools.
- PlaywrightBackend: Runs Playwright directly using the user's Chrome profile for auth.

Auto-detection picks the right backend based on runtime environment.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from typing import Any

from goldy_chrome import (
    DEFAULT_CHROME_ROOT,
    DEFAULT_EMAIL,
    DEFAULT_LOCAL_STATE,
    load_local_state,
    resolve_profile_directory,
)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

BACKEND_CHROME_EXTENSION = "chrome-extension"
BACKEND_PLAYWRIGHT = "playwright"

VALID_ACTIONS = frozenset({
    "navigate",
    "screenshot",
    "console",
    "evaluate",
    "click",
    "fill",
    "wait",
})

# MCP tool mapping for Chrome Extension backend
MCP_TOOL_MAP = {
    "navigate": "mcp__claude-in-chrome__puppeteer_navigate",
    "screenshot": "mcp__claude-in-chrome__puppeteer_screenshot",
    "console": "mcp__claude-in-chrome__read_console_messages",
    "evaluate": "mcp__claude-in-chrome__javascript_tool",
    "click": "mcp__claude-in-chrome__puppeteer_click",
    "fill": "mcp__claude-in-chrome__puppeteer_fill",
    "wait": "mcp__claude-in-chrome__puppeteer_evaluate",
}


@dataclass(frozen=True)
class BrowserAction:
    """A single browser action to execute."""

    action: str
    url: str | None = None
    selector: str | None = None
    value: str | None = None
    expression: str | None = None
    pattern: str | None = None
    timeout_ms: int = 5000

    def __post_init__(self) -> None:
        if self.action not in VALID_ACTIONS:
            raise ValueError(f"Invalid action '{self.action}'. Must be one of: {sorted(VALID_ACTIONS)}")

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}


@dataclass
class BrowserResult:
    """Result from executing a browser action."""

    success: bool
    action: str
    data: dict[str, Any] | str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Backend detection
# ---------------------------------------------------------------------------


def detect_backend() -> str:
    """Auto-detect which browser backend to use.

    - CODEX_THREAD_ID present → Playwright (Codex runtime)
    - Otherwise → Chrome Extension (Claude Code runtime)
    """
    if os.environ.get("CODEX_THREAD_ID"):
        return BACKEND_PLAYWRIGHT
    return BACKEND_CHROME_EXTENSION


# ---------------------------------------------------------------------------
# Chrome Extension backend (JSON protocol)
# ---------------------------------------------------------------------------


class ChromeExtensionBackend:
    """Emits structured JSON instructions for Claude Code to execute via MCP tools.

    Does NOT execute anything directly — the AI agent reads the protocol
    and calls the appropriate mcp__claude-in-chrome__* tools.
    """

    def __init__(self) -> None:
        self.backend = BACKEND_CHROME_EXTENSION

    def build_instruction(self, action: BrowserAction) -> dict[str, Any]:
        """Build a single MCP instruction from a BrowserAction."""
        mcp_tool = MCP_TOOL_MAP.get(action.action)
        instruction: dict[str, Any] = {
            "action": action.action,
            "mcp_tool": mcp_tool,
            "params": action.to_dict(),
        }
        return instruction

    def build_investigation(self, steps: list[BrowserAction]) -> dict[str, Any]:
        """Build a complete browser investigation protocol block."""
        return {
            "browser_investigation": {
                "backend": self.backend,
                "steps": [self.build_instruction(step) for step in steps],
            }
        }

    def build_smoke_check(self, url: str) -> dict[str, Any]:
        """Build a smoke check protocol (navigate + screenshot + console)."""
        steps = smoke_check_actions(url)
        return self.build_investigation(steps)


# ---------------------------------------------------------------------------
# Playwright backend (direct execution)
# ---------------------------------------------------------------------------


class PlaywrightBackend:
    """Runs Playwright directly using the user's Chrome profile for auth.

    Requires: pip install playwright && playwright install chromium
    Uses the Chrome profile resolved by goldy_chrome to inherit login sessions.
    """

    def __init__(self, email: str = DEFAULT_EMAIL) -> None:
        self.backend = BACKEND_PLAYWRIGHT
        self.email = email
        self._profile_dir: str | None = None
        self._chrome_root = DEFAULT_CHROME_ROOT

    def resolve_profile(self) -> str:
        """Resolve the Chrome profile directory for the configured email."""
        if self._profile_dir is None:
            local_state = load_local_state(DEFAULT_LOCAL_STATE)
            self._profile_dir = resolve_profile_directory(self.email, local_state)
        return self._profile_dir

    def user_data_dir(self) -> str:
        """Return the full path to the Chrome user data directory for Playwright."""
        profile_dir = self.resolve_profile()
        return str(self._chrome_root / profile_dir)

    def execute(self, steps: list[BrowserAction]) -> list[BrowserResult]:
        """Execute browser actions via Playwright.

        Returns a list of BrowserResult for each step.
        Requires playwright to be installed.
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return [
                BrowserResult(
                    success=False,
                    action="setup",
                    error="Playwright not installed. Run: pip install playwright && playwright install chromium",
                )
            ]

        results: list[BrowserResult] = []
        user_data = self.user_data_dir()

        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=user_data,
                channel="chrome",
                headless=False,
            )
            page = context.pages[0] if context.pages else context.new_page()

            for step in steps:
                result = self._execute_step(page, step)
                results.append(result)
                if not result.success:
                    break

            context.close()

        return results

    def _execute_step(self, page: Any, action: BrowserAction) -> BrowserResult:
        """Execute a single browser action on a Playwright page."""
        try:
            if action.action == "navigate":
                page.goto(action.url, timeout=action.timeout_ms)
                return BrowserResult(success=True, action="navigate", data={"url": action.url})

            elif action.action == "screenshot":
                screenshot_bytes = page.screenshot(full_page=True)
                return BrowserResult(
                    success=True,
                    action="screenshot",
                    data={"bytes_length": len(screenshot_bytes)},
                )

            elif action.action == "console":
                # Read console messages (best-effort: returns page title + URL as proxy)
                return BrowserResult(
                    success=True,
                    action="console",
                    data={"title": page.title(), "url": page.url},
                )

            elif action.action == "evaluate":
                result = page.evaluate(action.expression or "document.title")
                return BrowserResult(success=True, action="evaluate", data={"result": result})

            elif action.action == "click":
                page.click(action.selector or "body", timeout=action.timeout_ms)
                return BrowserResult(success=True, action="click", data={"selector": action.selector})

            elif action.action == "fill":
                page.fill(action.selector or "input", action.value or "", timeout=action.timeout_ms)
                return BrowserResult(success=True, action="fill", data={"selector": action.selector})

            elif action.action == "wait":
                page.wait_for_selector(action.selector or "body", timeout=action.timeout_ms)
                return BrowserResult(success=True, action="wait", data={"selector": action.selector})

            else:
                return BrowserResult(success=False, action=action.action, error=f"Unknown action: {action.action}")

        except Exception as exc:
            return BrowserResult(success=False, action=action.action, error=str(exc))


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------


def smoke_check_actions(url: str) -> list[BrowserAction]:
    """Build the standard 3-step smoke check sequence: navigate, screenshot, console."""
    return [
        BrowserAction(action="navigate", url=url),
        BrowserAction(action="screenshot"),
        BrowserAction(action="console", pattern="error|Error|ERR"),
    ]


def build_smoke_check(url: str) -> dict[str, Any]:
    """Build a smoke check protocol block for the auto-detected backend."""
    backend_type = detect_backend()
    if backend_type == BACKEND_CHROME_EXTENSION:
        backend = ChromeExtensionBackend()
        return backend.build_smoke_check(url)
    else:
        # For Playwright, we return the protocol too (execution happens separately)
        backend_ext = ChromeExtensionBackend()
        protocol = backend_ext.build_smoke_check(url)
        protocol["browser_investigation"]["backend"] = BACKEND_PLAYWRIGHT
        return protocol


def format_protocol(protocol: dict[str, Any]) -> str:
    """Format a browser investigation protocol as pretty JSON for output."""
    return json.dumps(protocol, indent=2, sort_keys=False)
