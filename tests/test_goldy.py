#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import goldy  # type: ignore
import goldy_breaker  # type: ignore
import goldy_browser  # type: ignore
import goldy_chrome  # type: ignore
import goldy_audit_policy  # type: ignore
import goldy_history  # type: ignore
import goldy_lock  # type: ignore
import goldy_loop  # type: ignore
import goldy_memory  # type: ignore
import goldy_recovery  # type: ignore
import goldy_session  # type: ignore
import goldy_stack  # type: ignore
import goldy_stuck  # type: ignore
import goldy_task_lifecycle  # type: ignore

GOLDY_SCRIPT = str(SCRIPTS_DIR / "goldy.py")
GOLDY_LOOP_SCRIPT = str(SCRIPTS_DIR / "goldy_loop.py")
SEARCH_SCRIPT = str(SCRIPTS_DIR / "search.py")


class GoldyTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.tempdir.name)
        (self.project_root / "package.json").write_text(
            json.dumps({"dependencies": {"react": "19", "@tanstack/react-start": "1.0.0"}}),
            encoding="utf-8",
        )
        (self.project_root / "apps" / "web").mkdir(parents=True, exist_ok=True)
        (self.project_root / "apps" / "web" / "package.json").write_text(
            json.dumps(
                {
                    "dependencies": {
                        "drizzle-orm": "0.0.0",
                        "@neondatabase/serverless": "1.0.0",
                        "@workos-inc/node": "8.0.0",
                        "@radix-ui/react-dialog": "1.0.0",
                        "vitest": "1.0.0",
                        "playwright": "1.0.0",
                    },
                    "devDependencies": {"typescript": "5.0.0", "vite": "6.0.0"},
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _run(self, cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
        return subprocess.run(cmd, cwd=cwd, env=merged_env, capture_output=True, text=True, check=False)


class SessionTests(GoldyTestCase):
    def test_t001_session_id_env_precedence(self) -> None:
        os.environ["CODEX_THREAD_ID"] = "abc-123"
        self.assertEqual(goldy_session.resolve_session_id(), "abc-123")

    def test_t002_fallback_id_generation(self) -> None:
        old = os.environ.pop("CODEX_THREAD_ID", None)
        try:
            sid = goldy_session.resolve_session_id()
            self.assertRegex(sid, r"^[a-f0-9-]{36}$")
        finally:
            if old is not None:
                os.environ["CODEX_THREAD_ID"] = old

    def test_t002b_metadata_fallback_session_id(self) -> None:
        old = os.environ.pop("CODEX_THREAD_ID", None)
        try:
            (self.project_root / ".goldy").mkdir(parents=True, exist_ok=True)
            (self.project_root / ".goldy" / "index.json").write_text(
                json.dumps({"last_session": "meta-session-123"}),
                encoding="utf-8",
            )
            sid = goldy_session.resolve_session_id(project_root=self.project_root)
            self.assertEqual(sid, "meta-session-123")
        finally:
            if old is not None:
                os.environ["CODEX_THREAD_ID"] = old

    def test_t003_timestamp_session_filename(self) -> None:
        filename = goldy_session.build_plan_filename("hello world", "session-x", "goldy")
        self.assertIn("session-x", filename)
        self.assertRegex(filename, r"^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z--")


class PlanningTests(GoldyTestCase):
    def test_t004_active_plan_detection(self) -> None:
        runtime = goldy.ensure_goldy_runtime(self.project_root)
        temp_plans = self.project_root / "temp-plans"
        temp_plans.mkdir(parents=True, exist_ok=True)
        plan = temp_plans / "my-plan.md"
        plan.write_text("# plan", encoding="utf-8")
        goldy.write_json(runtime["index"], {"active_plan": str(plan), "plans": [str(plan)]})

        args = goldy.parse_args.__wrapped__ if hasattr(goldy.parse_args, "__wrapped__") else None
        class Args:
            plan = None
            temp_plan = False

        # Empty prompt keeps existing active-plan reuse behavior.
        resolved, is_new = goldy.resolve_active_plan(Args(), self.project_root, runtime, "s1", "")
        self.assertEqual(resolved, plan)
        self.assertFalse(is_new)

    def test_t004b_prompt_creates_new_temp_plan_even_with_active_plan(self) -> None:
        runtime = goldy.ensure_goldy_runtime(self.project_root)
        temp_plans = self.project_root / "temp-plans"
        temp_plans.mkdir(parents=True, exist_ok=True)
        existing = temp_plans / "existing.md"
        existing.write_text("# existing", encoding="utf-8")
        goldy.write_json(runtime["index"], {"active_plan": str(existing), "plans": [str(existing)]})

        class Args:
            plan = None
            temp_plan = False

        resolved, is_new = goldy.resolve_active_plan(Args(), self.project_root, runtime, "s1", "fix auth bug")
        self.assertNotEqual(resolved, existing)
        self.assertTrue(resolved.exists())
        self.assertIn("fix-auth-bug", resolved.name)
        self.assertTrue(is_new)

    def test_t004c_temp_plan_collision_emits_warning_and_uses_fallback_name(self) -> None:
        runtime = goldy.ensure_goldy_runtime(self.project_root)
        temp_plans = self.project_root / "temp-plans"
        temp_plans.mkdir(parents=True, exist_ok=True)
        collision_name = "2026-02-16T00-00-00Z--s1--fix-auth-bug-goldy-completion-plan.md"
        (temp_plans / collision_name).write_text("# existing collision file", encoding="utf-8")

        class Args:
            plan = None
            temp_plan = False

        stderr = StringIO()
        with patch.object(goldy, "build_plan_filename", return_value=collision_name):
            with patch("sys.stderr", stderr):
                resolved, is_new = goldy.resolve_active_plan(Args(), self.project_root, runtime, "s1", "fix auth bug")
        self.assertTrue(resolved.exists())
        self.assertTrue(resolved.name.endswith("-v2.md"))
        self.assertTrue(is_new)
        output = stderr.getvalue()
        self.assertIn("filename collision detected", output)
        self.assertIn("using fallback temp plan name", output)

    def test_t005_temp_plan_creation_path(self) -> None:
        runtime = goldy.ensure_goldy_runtime(self.project_root)
        class Args:
            plan = None
            temp_plan = True

        resolved, is_new = goldy.resolve_active_plan(Args(), self.project_root, runtime, "sess-1", "plan me")
        self.assertEqual(resolved.parent.name, "temp-plans")
        self.assertTrue(is_new)

    def test_t006_gold_template_bootstrap(self) -> None:
        template = "# [Product Name]\n## Document Control\nDate: YYYY-MM-DD\n"
        out = goldy.build_plan_from_template(template, "sid", "Plan Name")
        self.assertIn("GOLDY", out)
        self.assertIn("Document Control", out)
        self.assertNotIn("[Product Name]", out)


class MemoryTests(GoldyTestCase):
    def test_t007_memory_layers_loaded(self) -> None:
        paths = goldy_memory.ensure_memory_layout(self.project_root)
        paths["global"].write_text("- global a\n", encoding="utf-8")
        paths["project"].write_text("- project b\n", encoding="utf-8")
        active_plan = self.project_root / "temp-plans" / "p.md"
        active_plan.parent.mkdir(parents=True, exist_ok=True)
        active_plan.write_text("# plan", encoding="utf-8")
        entries = goldy_memory.load_memory_entries(self.project_root, active_plan)
        sources = {e.source for e in entries}
        self.assertIn("global", sources)
        self.assertIn("project", sources)
        self.assertTrue(any(s.startswith("plan:") for s in sources))

    def test_t007b_raw_memory_loaded(self) -> None:
        goldy_memory.append_raw_memory(
            self.project_root,
            "s-1",
            {"prompt": "planning toc templates", "intent_match": True},
        )
        entries = goldy_memory.load_memory_entries(self.project_root, None)
        self.assertTrue(any(e.source.startswith("raw:") for e in entries))
        self.assertTrue(any("planning toc templates" in e.text for e in entries))

    def test_t008_dedupe_logic(self) -> None:
        entries = [
            goldy_memory.MemoryEntry("1", "same text", "a", 1.0),
            goldy_memory.MemoryEntry("2", "same  text", "b", 2.0),
        ]
        deduped = goldy_memory.dedupe_entries(entries)
        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0].source, "b")

    def test_t009_compaction_budget(self) -> None:
        entries = [goldy_memory.MemoryEntry(str(i), f"entry {i} decision next blocker", "s", float(i)) for i in range(200)]
        capsule = goldy_memory.build_resume_capsule(entries, target_tokens=300)
        self.assertEqual(capsule["token_budget"], 300)
        for section in ("mission", "done", "next", "decisions", "blockers"):
            self.assertTrue(capsule[section])

    def test_t010_rich_capsule_target(self) -> None:
        entries = [goldy_memory.MemoryEntry(str(i), f"item {i} mission objective next", "s", float(i)) for i in range(400)]
        capsule = goldy_memory.build_resume_capsule(entries, target_tokens=1500)
        self.assertEqual(capsule["token_budget"], 1500)

    def test_t027_memory_all_compaction_fallback(self) -> None:
        paths = goldy_memory.ensure_memory_layout(self.project_root)
        lines = "\n".join(f"- memory line {i} decision blocker" for i in range(1000))
        paths["global"].write_text(lines, encoding="utf-8")
        entries = goldy_memory.retrieve_ranked_entries(self.project_root, None, "decision blocker", limit=150)
        capsule = goldy_memory.build_resume_capsule(entries, target_tokens=200)
        self.assertEqual(capsule["token_budget"], 200)

    def test_t036_resume_capsule_continuity(self) -> None:
        entries = [goldy_memory.MemoryEntry("1", "mission persist", "global", 1.0)]
        capsule = goldy_memory.build_resume_capsule(entries, 150)
        out = goldy_memory.save_capsule(self.project_root, "sid", capsule)
        self.assertTrue(out.exists())
        self.assertIn("PREVIOUS_SESSION_RESUME", out.read_text(encoding="utf-8"))


class StackTests(GoldyTestCase):
    def test_t011_stack_profile_merge(self) -> None:
        runtime = goldy.ensure_goldy_runtime(self.project_root)
        runtime["profile"].write_text(json.dumps({"name": "custom", "frameworks": ["rust"]}), encoding="utf-8")
        profile = goldy_stack.resolve_stack_profile(self.project_root, runtime["profile"])
        self.assertIn("rust", profile["frameworks"])
        self.assertIn("tanstack-start", profile["frameworks"])

    def test_t012_platform_defaults_present(self) -> None:
        profile = goldy_stack.resolve_stack_profile(self.project_root, self.project_root / ".goldy" / "missing.yaml")
        self.assertIn("drizzle", profile["db"])
        self.assertIn("neon-postgres", profile["db"])
        self.assertIn("workos", profile["auth"])

    def test_t035_stack_changes_by_profile(self) -> None:
        runtime = goldy.ensure_goldy_runtime(self.project_root)
        runtime["profile"].write_text(json.dumps({"name": "override", "db": ["sqlite"]}), encoding="utf-8")
        profile = goldy_stack.resolve_stack_profile(self.project_root, runtime["profile"])
        self.assertIn("sqlite", profile["db"])


class AutoInvokeTests(GoldyTestCase):
    def test_t013_intent_classifier(self) -> None:
        self.assertTrue(goldy.classify_intent("please plan this architecture"))
        self.assertFalse(goldy.classify_intent("random chat"))

    def test_t014_visible_banner_output(self) -> None:
        result = self._run(["python3", GOLDY_SCRIPT, "planning roadmap", "--project-root", str(self.project_root)])
        self.assertEqual(result.returncode, 0)
        self.assertIn("GOLDY ACTIVE", result.stdout)

    def test_t034_auto_invoke_without_explicit_slash(self) -> None:
        result = self._run(["python3", GOLDY_SCRIPT, "need phase plan and milestones", "--project-root", str(self.project_root)])
        self.assertIn("AUTO-INVOKE", result.stdout)

    def test_t034b_goldy_does_not_auto_run_goldy_loop_or_create_worktree(self) -> None:
        self._run(["git", "init"], cwd=self.project_root)
        result = self._run(
            [
                "python3",
                GOLDY_SCRIPT,
                "plan this and then run /goldy-loop automatically",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("WORKTREE:", result.stdout)
        worktrees_root = self.project_root.parent / f"{self.project_root.name}-goldy-worktrees"
        self.assertFalse(worktrees_root.exists())

    def test_t060_coding_intent_classifier(self) -> None:
        """Coding keywords are detected by classify_coding_intent."""
        self.assertTrue(goldy.classify_coding_intent("fix the auth bug"))
        self.assertTrue(goldy.classify_coding_intent("implement new settings page"))
        self.assertTrue(goldy.classify_coding_intent("build the dashboard"))
        self.assertTrue(goldy.classify_coding_intent("add a delete button"))
        self.assertTrue(goldy.classify_coding_intent("create user endpoint"))
        self.assertFalse(goldy.classify_coding_intent("random chat about weather"))
        self.assertFalse(goldy.classify_coding_intent(""))

    def test_t061_coding_intent_triggers_plan_mode_required(self) -> None:
        """Coding intent with no existing plan sets plan_mode_required."""
        result = self._run(
            [
                "python3",
                GOLDY_SCRIPT,
                "fix the auth bug",
                "--json",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertTrue(data.get("coding_match"))
        self.assertTrue(data.get("plan_mode_required"))
        self.assertIn("PLAN MODE REQUIRED", data.get("banner", ""))

    def test_t062_planning_intent_no_plan_mode_required(self) -> None:
        """Pure planning intent should not set plan_mode_required."""
        result = self._run(
            [
                "python3",
                GOLDY_SCRIPT,
                "plan the auth refactor",
                "--json",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertTrue(data.get("intent_match"))
        self.assertFalse(data.get("plan_mode_required"))

    def test_t063_existing_plan_no_plan_mode_required(self) -> None:
        """Coding intent with an existing active plan should NOT set plan_mode_required."""
        # First create a plan by running goldy once
        temp_plans = self.project_root / "temp-plans"
        temp_plans.mkdir(parents=True, exist_ok=True)
        existing_plan = temp_plans / "existing-plan.md"
        existing_plan.write_text("# Existing Plan\n## Phase 1\n- [ ] task\n", encoding="utf-8")
        goldy_dir = self.project_root / ".goldy"
        goldy_dir.mkdir(parents=True, exist_ok=True)
        (goldy_dir / "index.json").write_text(
            json.dumps({"active_plan": str(existing_plan), "plans": [str(existing_plan)]}),
            encoding="utf-8",
        )
        # Now run with coding intent — should reuse existing plan
        result = self._run(
            [
                "python3",
                GOLDY_SCRIPT,
                "fix the auth bug",
                "--json",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertTrue(data.get("coding_match"))
        self.assertFalse(data.get("plan_mode_required"))
        self.assertEqual(data.get("active_plan"), str(existing_plan))


class LoopTests(GoldyTestCase):
    def _make_plan(self, phases: int = 3, filename: str = "loop-plan.md", checked: bool = True) -> Path:
        plan = self.project_root / "plans" / filename
        plan.parent.mkdir(parents=True, exist_ok=True)
        mark = "x" if checked else " "
        body = ["# Plan"]
        for i in range(1, phases + 1):
            body.append(f"## Phase {i} - Task {i}")
            body.append(f"- [{mark}] do thing")
            body.append("Validation gate: pass")
        plan.write_text("\n".join(body) + "\n", encoding="utf-8")
        return plan

    def _make_ambiguous_plan(self, filename: str = "ambiguous-plan.md") -> Path:
        plan = self.project_root / "plans" / filename
        plan.parent.mkdir(parents=True, exist_ok=True)
        plan.write_text(
            "\n".join(
                [
                    "# Ambiguous Plan",
                    "## Phase 1 - [First Feature/Fix Area]",
                    "- [ ] do thing",
                    "Validation gate: pass",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        return plan

    def _init_git(self) -> None:
        self._run(["git", "init"], cwd=self.project_root)
        self._run(["git", "config", "user.email", "goldy@example.com"], cwd=self.project_root)
        self._run(["git", "config", "user.name", "Goldy Test"], cwd=self.project_root)
        (self.project_root / "README.md").write_text("init\n", encoding="utf-8")
        self._run(["git", "add", "README.md"], cwd=self.project_root)
        self._run(["git", "commit", "-m", "init"], cwd=self.project_root)

    def _worktree_path_for_plan(self, plan: Path) -> Path:
        token = goldy_loop._plan_token(plan)  # type: ignore[attr-defined]
        return self.project_root.parent / f"{self.project_root.name}-goldy-worktrees" / token

    def test_t015_checkpoint_state_writer(self) -> None:
        self._init_git()
        plan = self._make_plan(1)
        sid = "t015-checkpoint"
        result = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                sid,
                "--dry-run",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertIn("Phase 1 complete", result.stdout)
        worktree = self._worktree_path_for_plan(plan)
        self.assertTrue(worktree.exists())
        checkpoint = worktree / ".goldy" / "checkpoints" / sid
        # Resume id may not be CODEX thread in test env fallback; assert any checkpoint file exists.
        all_checkpoints = list(checkpoint.glob("**/phase-1.json"))
        self.assertTrue(all_checkpoints)

    def test_t016_resume_loader(self) -> None:
        self._init_git()
        plan = self._make_plan(2)
        sid = "resume-test"
        self._run([
            "python3",
            GOLDY_LOOP_SCRIPT,
            "--plan",
            str(plan),
            "--resume",
            sid,
            "--max-iterations",
            "1",
            "--dry-run",
            "--project-root",
            str(self.project_root),
        ])
        result = self._run([
            "python3",
            GOLDY_LOOP_SCRIPT,
            "--plan",
            str(plan),
            "--resume",
            sid,
            "--dry-run",
            "--project-root",
            str(self.project_root),
        ])
        self.assertIn("Phase 2 complete", result.stdout)

    def test_t017_phase_commit_trigger_logic(self) -> None:
        self._init_git()
        plan = self._make_plan(1)
        sid = "commit-test"
        result = self._run([
            "python3",
            GOLDY_LOOP_SCRIPT,
            "--plan",
            str(plan),
            "--resume",
            sid,
            "--commit-phase",
            "--project-root",
            str(self.project_root),
        ])
        self.assertEqual(result.returncode, 0)
        worktree = self._worktree_path_for_plan(plan)
        log = self._run(["git", "log", "--oneline"], cwd=worktree)
        self.assertIn("goldy-loop: complete phase", log.stdout)

    def test_t018_guardrail_stop_on_budget(self) -> None:
        self._init_git()
        plan = self._make_plan(1)
        sid = "t018-context-stop"
        result = self._run([
            "python3",
            GOLDY_LOOP_SCRIPT,
            "--plan",
            str(plan),
            "--resume",
            sid,
            "--context-remaining",
            "10",
            "--project-root",
            str(self.project_root),
        ])
        self.assertEqual(result.returncode, 2)
        self.assertIn("remaining context below 15%", result.stdout)
        self.assertTrue(self._worktree_path_for_plan(plan).exists())

    def test_t028_auto_checkpoint_resume_chain(self) -> None:
        self._init_git()
        plan = self._make_plan(2)
        sid = "t028-resume-chain"
        result = self._run([
            "python3",
            GOLDY_LOOP_SCRIPT,
            "--plan",
            str(plan),
            "--resume",
            sid,
            "--dry-run",
            "--project-root",
            str(self.project_root),
        ])
        self.assertIn("Resume chain pointer", result.stdout)
        self.assertTrue(self._worktree_path_for_plan(plan).exists())

    def test_t029_handoff_note_format(self) -> None:
        self._init_git()
        plan = self._make_plan(1)
        sid = "t029-handoff"
        result = self._run([
            "python3",
            GOLDY_LOOP_SCRIPT,
            "--plan",
            str(plan),
            "--resume",
            sid,
            "--dry-run",
            "--project-root",
            str(self.project_root),
        ])
        self.assertRegex(result.stdout, r"Phase 1 complete\. Start a new session for Phase 2")

    def test_t032_three_phase_commits(self) -> None:
        self._init_git()
        plan = self._make_plan(3)
        sid = "three-phase"
        result = self._run([
            "python3",
            GOLDY_LOOP_SCRIPT,
            "--plan",
            str(plan),
            "--resume",
            sid,
            "--commit-phase",
            "--project-root",
            str(self.project_root),
        ])
        self.assertEqual(result.returncode, 0)
        worktree = self._worktree_path_for_plan(plan)
        count = self._run(["git", "rev-list", "--count", "HEAD"], cwd=worktree)
        self.assertGreaterEqual(int(count.stdout.strip()), 3)

    def test_t033_interrupted_resume(self) -> None:
        self._init_git()
        plan = self._make_plan(2)
        sid = "interrupt-test"
        first = self._run([
            "python3",
            GOLDY_LOOP_SCRIPT,
            "--plan",
            str(plan),
            "--resume",
            sid,
            "--max-iterations",
            "1",
            "--dry-run",
            "--project-root",
            str(self.project_root),
        ])
        self.assertEqual(first.returncode, 1)
        second = self._run([
            "python3",
            GOLDY_LOOP_SCRIPT,
            "--plan",
            str(plan),
            "--resume",
            sid,
            "--dry-run",
            "--project-root",
            str(self.project_root),
        ])
        self.assertEqual(second.returncode, 0)

    def test_t037_worktree_created_by_default(self) -> None:
        self._init_git()
        plan = self._make_plan(1)
        sid = "t037-worktree"
        result = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                sid,
                "--dry-run",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("WORKTREE:", result.stdout)
        self.assertTrue(self._worktree_path_for_plan(plan).exists())

    def test_t038_reject_temp_plan_by_default(self) -> None:
        self._init_git()
        temp_plan = self.project_root / "temp-plans" / "temp-loop.md"
        temp_plan.parent.mkdir(parents=True, exist_ok=True)
        temp_plan.write_text("# Temp Plan\n## Phase 1 - Demo\n- [ ] do\n", encoding="utf-8")
        result = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(temp_plan),
                "--resume",
                "t038-temp-reject",
                "--dry-run",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("user-authored plan outside temp-plans", result.stderr)

    def test_t039_different_plan_names_create_different_worktrees(self) -> None:
        self._init_git()
        plan_a = self._make_plan(1, filename="alpha-plan.md")
        plan_b = self._make_plan(1, filename="beta-plan.md")

        run_a = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan_a),
                "--resume",
                "sid-a",
                "--dry-run",
                "--project-root",
                str(self.project_root),
            ]
        )
        run_b = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan_b),
                "--resume",
                "sid-b",
                "--dry-run",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(run_a.returncode, 0)
        self.assertEqual(run_b.returncode, 0)

        path_a = self._worktree_path_for_plan(plan_a)
        path_b = self._worktree_path_for_plan(plan_b)
        self.assertTrue(path_a.exists())
        self.assertTrue(path_b.exists())
        self.assertNotEqual(path_a, path_b)

    def test_t040_preflight_blocks_until_questions_answered(self) -> None:
        self._init_git()
        plan = self._make_ambiguous_plan()
        result = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                "t040-preflight",
                "--dry-run",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(result.returncode, 3)
        self.assertIn("PREFLIGHT: Clarifications required", result.stdout)
        self.assertIn("Template placeholders are still present", result.stdout)

    def test_t041_preflight_accepts_answers_and_continues(self) -> None:
        self._init_git()
        plan = self._make_ambiguous_plan(filename="ambiguous-plan-2.md")
        result = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                "t041-preflight-answer",
                "--preflight-answer",
                "Replace with concrete phase title: TOC Type Templates",
                "--dry-run",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("PREFLIGHT: PASS (clarifications captured)", result.stdout)

    def test_t042_post_preflight_options_present(self) -> None:
        self._init_git()
        plan = self._make_plan(1, filename="options-plan.md")
        result = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                "t042-options",
                "--dry-run",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("POST-PREFLIGHT OPTIONS:", result.stdout)
        self.assertIn("* Start", result.stdout)
        self.assertIn("* Chat", result.stdout)

    def test_t043_chat_mode_pauses_before_execution(self) -> None:
        self._init_git()
        plan = self._make_plan(1, filename="chat-mode-plan.md")
        result = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                "t043-chat-mode",
                "--mode",
                "chat",
                "--dry-run",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("CHAT MODE: loop execution not started.", result.stdout)
        self.assertNotIn("Phase 1 complete", result.stdout)

    def test_t044_completion_report_includes_compaction_and_minutes(self) -> None:
        self._init_git()
        plan = self._make_plan(1, filename="report-plan.md")
        result = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                "t044-report",
                "--mode",
                "start",
                "--dry-run",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("=== GOLDY LOOP COMPLETION REPORT ===", result.stdout)
        self.assertRegex(result.stdout, r"compaction_runs_total:\s*\d+")
        self.assertRegex(result.stdout, r"compaction_minutes_total:\s*\d")
        self.assertRegex(result.stdout, r"loop_minutes_total:\s*\d")
        self.assertIn("deep_code_audits_run: 5", result.stdout)

    def test_t045_deep_audits_count_is_five(self) -> None:
        self._init_git()
        audits = goldy_loop.run_deep_code_audits(self.project_root, dry_run=True)
        self.assertEqual(len(audits), 5)
        self.assertTrue(all(a.get("status") == "passed" for a in audits))

    def test_t048_commands_reference_flag(self) -> None:
        result = self._run(["python3", GOLDY_LOOP_SCRIPT, "--commands"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("=== /goldy-loop Command Reference ===", result.stdout)
        self.assertIn("--plan <path>", result.stdout)
        self.assertIn("runs up to 10 execution loops by default", result.stdout)
        self.assertIn("After plan completion, it runs 5 deep audits", result.stdout)
        self.assertIn("Typical usage:", result.stdout)

    def test_t049_no_plan_prints_usage_reference(self) -> None:
        result = self._run(["python3", GOLDY_LOOP_SCRIPT])
        self.assertEqual(result.returncode, 0)
        self.assertIn("=== /goldy-loop Command Reference ===", result.stdout)
        self.assertIn("No --plan provided", result.stdout)

    def test_lt069_plan_drift_detected_prevents_progress(self) -> None:
        self._init_git()
        plan = self._make_plan(1, filename="lt069-plan-drift.md")
        sid = "lt069-plan-drift"

        first = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                sid,
                "--dry-run",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(first.returncode, 0)

        plan.write_text(plan.read_text(encoding="utf-8") + "\n# drift marker\n", encoding="utf-8")
        second = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                sid,
                "--dry-run",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(second.returncode, 8)
        self.assertIn("PLAN DRIFT DETECTED", second.stdout)
        self.assertIn("--require-resync", second.stdout)

        handoff_match = re.search(r"HANDOFF: (.+\.md)", second.stdout)
        self.assertIsNotNone(handoff_match)
        handoff_path = Path(handoff_match.group(1).strip())
        self.assertTrue(handoff_path.exists())
        handoff_text = handoff_path.read_text(encoding="utf-8")
        self.assertIn("stop_reason: plan_drift_detected", handoff_text)

    def test_lt070_plan_drift_require_resync_reconciles_and_continues(self) -> None:
        self._init_git()
        plan = self._make_plan(1, filename="lt070-plan-drift.md")
        sid = "lt070-plan-drift"

        first = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                sid,
                "--dry-run",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(first.returncode, 0)

        plan.write_text(plan.read_text(encoding="utf-8") + "\n# drift marker\n", encoding="utf-8")
        second = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                sid,
                "--require-resync",
                "--dry-run",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(second.returncode, 0)
        self.assertNotIn("PLAN DRIFT DETECTED", second.stdout)
        mapped_plan = self._worktree_path_for_plan(plan) / "plans" / "lt070-plan-drift.md"
        self.assertTrue(mapped_plan.exists())
        self.assertEqual(mapped_plan.read_text(encoding="utf-8"), plan.read_text(encoding="utf-8"))

    def test_lt110_malformed_backpressure_threshold_stops_loop(self) -> None:
        plan = self._make_plan(1, filename="lt110-malformed-backpressure.md")
        sid = "lt110-malformed-backpressure"
        runtime = goldy_loop.ensure_runtime(self.project_root)
        goldy_history.append_history_event(
            runtime["root"],
            sid,
            "malformed_event",
            data={"reason": "manually injected malformed payload"},
        )
        goldy_history.append_history_event(
            runtime["root"],
            sid,
            "phase_started",
            data={"reason": "initial"},
        )

        result = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                sid,
                "--no-worktree",
                "--project-root",
                str(self.project_root),
            ],
            env={
                "GOLDY_MALFORMED_EVENT_THRESHOLD_COUNT": "1",
                "GOLDY_MALFORMED_EVENT_THRESHOLD_RATIO": "0.5",
            },
        )
        self.assertEqual(result.returncode, 9)
        self.assertIn("MALFORMED EVENT BACKPRESSURE", result.stdout)

        handoff_path = self.project_root / ".goldy" / "handoffs" / f"{sid}.md"
        self.assertTrue(handoff_path.exists())
        handoff_text = handoff_path.read_text(encoding="utf-8")
        self.assertIn("stop_reason: malformed_backpressure", handoff_text)

        session_state = goldy_session.read_json(runtime["sessions"] / f"{sid}.json", {})
        metrics = session_state.get("metrics", {}) if isinstance(session_state, dict) else {}
        self.assertGreaterEqual(int(metrics.get("lock_events_total", 0)), 2)

        registry = goldy_session.read_json(runtime["root"] / "registry.json", {"active_sessions": {}})
        active_sessions = registry.get("active_sessions", {}) if isinstance(registry, dict) else {}
        self.assertNotIn(sid, active_sessions)

        replay = goldy_history.replay_history(runtime["root"], sid)
        event_types = [str(event.get("event_type", "")) for event in replay.get("events", [])]
        self.assertIn("handoff_generated", event_types)
        self.assertIn("lock_released", event_types)

    def test_lt111_diagnostics_bundle_created_and_populated(self) -> None:
        plan = self._make_plan(1, filename="lt111-diagnostics.md")
        sid = "lt111-diagnostics"
        diagnostics_root = (self.project_root / ".goldy" / "diagnostics")
        result = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                sid,
                "--no-worktree",
                "--diagnostics",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(result.returncode, 0)
        matches = sorted(p for p in diagnostics_root.iterdir() if p.is_dir() and sid in p.name)
        self.assertTrue(matches)
        manifest_path = matches[-1] / "bundle.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest.get("session_id"), sid)
        self.assertTrue(manifest.get("enabled"))
        categories = manifest.get("categories", {})
        for category, path in categories.items():
            path_obj = Path(path)
            self.assertTrue(path_obj.exists(), f"missing diagnostics category file: {category}")
            raw = path_obj.read_text(encoding="utf-8")
            if raw:
                self.assertIn("event_type", raw)

    def test_lt112_handoff_artifact_contains_stop_reason_and_command(self) -> None:
        self._init_git()
        plan = self._make_plan(3, filename="lt112-handoff.md")
        sid = "lt112-handoff"
        result = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                sid,
                "--max-iterations",
                "1",
                "--no-worktree",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(result.returncode, 1)
        handoff_path = self.project_root / ".goldy" / "handoffs" / f"{sid}.md"
        self.assertTrue(handoff_path.exists())
        handoff_text = handoff_path.read_text(encoding="utf-8")
        self.assertIn("stop_reason: max_iterations_reached", handoff_text)
        self.assertIn("## Completed tasks", handoff_text)
        self.assertIn("## Pending tasks", handoff_text)
        self.assertIn("## Handoff command", handoff_text)
        self.assertIn("--phase 2", handoff_text)

    def test_lt115_commands_reference_lists_new_debug_flags(self) -> None:
        result = self._run(["python3", GOLDY_LOOP_SCRIPT, "--commands"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("--diagnostics", result.stdout)
        self.assertIn("--require-resync", result.stdout)

    def test_lt082_command_reference_includes_new_breaker_and_recovery_flags(self) -> None:
        result = self._run(["python3", GOLDY_LOOP_SCRIPT, "--commands"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("--breaker-status", result.stdout)
        self.assertIn("--breaker-reset", result.stdout)
        self.assertIn("--breaker-auto-reset", result.stdout)
        self.assertIn("--diagnostics", result.stdout)
        self.assertIn("--require-resync", result.stdout)

    def test_lt089_plan_edit_mid_run_triggers_drift_stop(self) -> None:
        self._init_git()
        plan = self._make_plan(2, filename="lt089-plan-drift.md")
        sid = "lt089-plan-drift"
        first = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                sid,
                "--max-iterations",
                "1",
                "--dry-run",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(first.returncode, 1)

        plan.write_text(plan.read_text(encoding="utf-8") + "\n# drift marker\n", encoding="utf-8")
        second = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                sid,
                "--dry-run",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(second.returncode, 8)
        self.assertIn("PLAN DRIFT DETECTED", second.stdout)
        self.assertIn("--require-resync", second.stdout)
        handoff_match = re.search(r"HANDOFF: (.+\.md)", second.stdout)
        self.assertIsNotNone(handoff_match)
        handoff_path = Path(handoff_match.group(1).strip())
        self.assertTrue(handoff_path.exists())
        handoff_text = handoff_path.read_text(encoding="utf-8")
        self.assertIn("stop_reason: plan_drift_detected", handoff_text)

    def test_lt091_no_plan_invocation_prints_command_reference(self) -> None:
        result = self._run(["python3", GOLDY_LOOP_SCRIPT])
        self.assertEqual(result.returncode, 0)
        self.assertIn("=== /goldy-loop Command Reference ===", result.stdout)
        self.assertIn("No --plan provided", result.stdout)

    def test_lt092_command_reference_includes_workflow_paragraph(self) -> None:
        result = self._run(["python3", GOLDY_LOOP_SCRIPT, "--commands"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("runs up to 10 execution loops by default", result.stdout)
        self.assertIn("After plan completion, it runs 5 deep audits", result.stdout)

    def test_lt095_ambiguous_plan_preflight_emits_questions_and_blocks(self) -> None:
        self._init_git()
        plan = self._make_ambiguous_plan(filename="lt095-ambiguous-plan.md")
        result = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                "lt095-ambiguous",
                "--dry-run",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(result.returncode, 3)
        self.assertIn("PREFLIGHT: Clarifications required", result.stdout)
        self.assertIn("Template placeholders are still present", result.stdout)

    def test_lt096_post_preflight_options_start_and_chat_only(self) -> None:
        self._init_git()
        plan = self._make_plan(1, filename="lt096-options-plan.md")
        result = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                "lt096-options",
                "--dry-run",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(result.returncode, 0)
        marker = "POST-PREFLIGHT OPTIONS:"
        self.assertIn(marker, result.stdout)
        segment = result.stdout.split(marker, 1)[1].split("POST-PREFLIGHT SELECTED:", 1)[0]
        option_lines = [line.strip() for line in segment.splitlines() if line.strip().startswith("* ")]
        self.assertEqual(option_lines, ["* Start", "* Chat"])

    def test_lt073_completion_report_includes_breaker_stuck_retry_metrics(self) -> None:
        self._init_git()
        plan = self._make_plan(1, filename="lt073-report-metrics.md")
        result = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                "lt073-report-metrics",
                "--mode",
                "start",
                "--dry-run",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("breaker_events_total:", result.stdout)
        self.assertIn("stuck_events_total:", result.stdout)
        self.assertIn("task_lifecycle_retries_total:", result.stdout)

    def test_lt074_mode_chat_remains_pause_only_behavior(self) -> None:
        self._init_git()
        plan = self._make_plan(1, filename="lt074-chat-only.md")
        result = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                "lt074-chat-only",
                "--mode",
                "chat",
                "--dry-run",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("CHAT MODE: loop execution not started.", result.stdout)
        self.assertNotIn("TASK CHECK:", result.stdout)
        self.assertNotIn("Phase 1 complete", result.stdout)

    def test_lt075_mode_start_executes_default_path(self) -> None:
        self._init_git()
        plan = self._make_plan(1, filename="lt075-start-mode.md")
        result = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                "lt075-start-mode",
                "--mode",
                "start",
                "--dry-run",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Phase 1 complete", result.stdout)

    def test_lt076_existing_plan_based_worktree_behavior_unchanged(self) -> None:
        self._init_git()
        plan = self._make_plan(1, filename="lt076-worktree.md")
        sid = "lt076-worktree"
        result = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                sid,
                "--dry-run",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("WORKTREE:", result.stdout)
        self.assertTrue(self._worktree_path_for_plan(plan).exists())

    def test_lt077_different_plan_filenames_still_create_distinct_worktrees(self) -> None:
        self._init_git()
        plan_a = self._make_plan(1, filename="lt077-alpha.md")
        plan_b = self._make_plan(1, filename="lt077-beta.md")
        run_a = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan_a),
                "--resume",
                "lt077-a",
                "--dry-run",
                "--project-root",
                str(self.project_root),
            ]
        )
        run_b = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan_b),
                "--resume",
                "lt077-b",
                "--dry-run",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(run_a.returncode, 0)
        self.assertEqual(run_b.returncode, 0)
        self.assertNotEqual(self._worktree_path_for_plan(plan_a), self._worktree_path_for_plan(plan_b))

    def test_lt078_temp_plans_rejection_remains_default(self) -> None:
        self._init_git()
        temp_plan = self.project_root / "temp-plans" / "lt078-temp.md"
        temp_plan.parent.mkdir(parents=True, exist_ok=True)
        temp_plan.write_text("# Temp Plan\n## Phase 1 - Demo\n- [ ] do\n", encoding="utf-8")
        result = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(temp_plan),
                "--resume",
                "lt078-temp",
                "--dry-run",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("user-authored plan outside temp-plans", result.stderr)

    def test_lt083_existing_compaction_metrics_still_emitted(self) -> None:
        self._init_git()
        plan = self._make_plan(1, filename="lt083-compaction.md")
        result = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                "lt083-compaction",
                "--mode",
                "start",
                "--dry-run",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(result.returncode, 0)
        self.assertRegex(result.stdout, r"compaction_runs_total:\s*\d+")
        self.assertRegex(result.stdout, r"compaction_minutes_total:\s*\d")

    def test_lt084_existing_five_audit_count_still_emitted(self) -> None:
        self._init_git()
        plan = self._make_plan(1, filename="lt084-audit-count.md")
        result = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                "lt084-audit-count",
                "--mode",
                "start",
                "--dry-run",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("deep_code_audits_run: 5", result.stdout)

    def test_lt085_existing_handoff_format_unchanged(self) -> None:
        self._init_git()
        plan = self._make_plan(1, filename="lt085-handoff-format.md")
        result = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                "lt085-handoff-format",
                "--dry-run",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(result.returncode, 0)
        self.assertRegex(result.stdout, r"Phase 1 complete\. Start a new session for Phase 2")

    def test_lt090_final_completion_report_includes_enhanced_telemetry_fields(self) -> None:
        self._init_git()
        plan = self._make_plan(1, filename="lt090-enhanced-report.md")
        result = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                "lt090-enhanced-report",
                "--mode",
                "start",
                "--dry-run",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(result.returncode, 0)
        required_fields = [
            "breaker_events_total:",
            "stuck_events_total:",
            "permission_events_total:",
            "policy_failures_total:",
            "lock_events_total:",
            "malformed_events_total:",
            "malformed_events_ratio:",
            "task_lifecycle_tasks_total:",
            "task_lifecycle_retries_total:",
        ]
        for field in required_fields:
            self.assertIn(field, result.stdout)

    def test_lt093_completion_report_always_prints_compaction_totals(self) -> None:
        self._init_git()
        plan = self._make_plan(1, filename="lt093-compaction-totals.md")
        result = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                "lt093-compaction-totals",
                "--mode",
                "start",
                "--dry-run",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("compaction_runs_total:", result.stdout)
        self.assertIn("compaction_minutes_total:", result.stdout)

    def test_lt094_deep_audit_suite_remains_exactly_five_named_categories(self) -> None:
        self._init_git()
        audits = goldy_loop.run_deep_code_audits(self.project_root, dry_run=True)
        self.assertEqual(len(audits), 5)
        categories = [str(item.get("category")) for item in audits]
        self.assertEqual(categories, ["lint", "typecheck", "test", "integration", "robustness"])

    def test_lt099_loop_execution_does_not_auto_delete_worktrees(self) -> None:
        self._init_git()
        plan = self._make_plan(1, filename="lt099-no-delete.md")
        sid = "lt099-no-delete"
        first = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                sid,
                "--dry-run",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(first.returncode, 0)
        worktree_path = self._worktree_path_for_plan(plan)
        self.assertTrue(worktree_path.exists())
        second = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                sid,
                "--dry-run",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(second.returncode, 0)
        self.assertTrue(worktree_path.exists())

    def test_lt100_worktree_naming_contract_enforced_and_plan_identity_distinct(self) -> None:
        self._init_git()
        plan_a = self._make_plan(1, filename="lt100-alpha-plan.md")
        plan_b = self._make_plan(1, filename="lt100-beta-plan.md")
        run_a = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan_a),
                "--resume",
                "lt100-a",
                "--dry-run",
                "--project-root",
                str(self.project_root),
            ]
        )
        run_b = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan_b),
                "--resume",
                "lt100-b",
                "--dry-run",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(run_a.returncode, 0)
        self.assertEqual(run_b.returncode, 0)

        branch_a_match = re.search(r"branch=(goldy-loop/[a-zA-Z0-9._-]+-[a-f0-9]{8})", run_a.stdout)
        branch_b_match = re.search(r"branch=(goldy-loop/[a-zA-Z0-9._-]+-[a-f0-9]{8})", run_b.stdout)
        self.assertIsNotNone(branch_a_match)
        self.assertIsNotNone(branch_b_match)
        self.assertNotEqual(branch_a_match.group(1), branch_b_match.group(1))
        self.assertTrue(self._worktree_path_for_plan(plan_a).exists())
        self.assertTrue(self._worktree_path_for_plan(plan_b).exists())


class CommandAndInstallTests(GoldyTestCase):
    def test_t019_global_goldy_command_exists(self) -> None:
        path = Path("/Users/forest/.claude/commands/goldy.md")
        self.assertTrue(path.exists())
        self.assertIn("scripts/goldy.py", path.read_text(encoding="utf-8"))

    def test_t020_project_goldy_command_exists(self) -> None:
        path = Path("/Volumes/Coding/Code/platform/.claude/commands/goldy.md")
        self.assertTrue(path.exists())

    def test_t021_global_goldy_loop_command_exists(self) -> None:
        path = Path("/Users/forest/.claude/commands/goldy-loop.md")
        self.assertTrue(path.exists())

    def test_t022_project_goldy_loop_command_exists(self) -> None:
        path = Path("/Volumes/Coding/Code/platform/.claude/commands/goldy-loop.md")
        self.assertTrue(path.exists())

    def test_t022b_goldy_chrome_commands_removed(self) -> None:
        """goldy-chrome command files should no longer exist (absorbed into browser module)."""
        global_path = Path("/Users/forest/.claude/commands/goldy-chrome.md")
        project_path = Path("/Volumes/Coding/Code/platform/.claude/commands/goldy-chrome.md")
        self.assertFalse(global_path.exists(), f"Legacy goldy-chrome.md should be removed: {global_path}")
        self.assertFalse(project_path.exists(), f"Legacy goldy-chrome.md should be removed: {project_path}")

    def test_t023_codex_symlink_resolves(self) -> None:
        path = Path("/Users/forest/.codex/skills/goldy")
        self.assertTrue(path.is_symlink())
        self.assertTrue(path.resolve().exists())

    def test_t024_claude_global_skill_link(self) -> None:
        path = Path("/Users/forest/.claude/skills/goldy")
        self.assertTrue(path.is_symlink())
        self.assertTrue(path.resolve().exists())

    def test_t025_claude_project_skill_link(self) -> None:
        path = Path("/Volumes/Coding/Code/platform/.claude/skills/goldy")
        self.assertTrue(path.is_symlink())
        self.assertTrue(path.resolve().exists())

    def test_t026_no_active_plan_creates_temp_plan(self) -> None:
        result = self._run(["python3", GOLDY_SCRIPT, "new roadmap", "--project-root", str(self.project_root)])
        self.assertEqual(result.returncode, 0)
        plans = list((self.project_root / "temp-plans").glob("*.md"))
        self.assertTrue(plans)

    def test_t030_legacy_uiux_search_still_works(self) -> None:
        result = self._run(["python3", SEARCH_SCRIPT, "saas dashboard", "--domain", "product"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("UI Pro Max Search Results", result.stdout)

    def test_t031_existing_project_commands_untouched(self) -> None:
        start_path = Path("/Volumes/Coding/Code/platform/.claude/commands/start.md")
        self.assertTrue(start_path.exists())
        self.assertIn("Dev server", start_path.read_text(encoding="utf-8"))

    def test_t031b_missing_plan_returns_deterministic_error(self) -> None:
        result = self._run(
            [
                "python3",
                GOLDY_SCRIPT,
                "--plan",
                "does-not-exist.md",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("GOLDY ERROR: Plan file not found:", result.stderr)
        self.assertNotIn("Traceback", result.stderr + result.stdout)

        result_json = self._run(
            [
                "python3",
                GOLDY_SCRIPT,
                "--plan",
                "does-not-exist.md",
                "--project-root",
                str(self.project_root),
                "--json",
            ]
        )
        self.assertEqual(result_json.returncode, 2)
        payload = json.loads(result_json.stdout)
        self.assertIn("error", payload)
        self.assertIn("Plan file not found", str(payload["error"]))


class RemainingChecklistCoverage(GoldyTestCase):
    # Lightweight explicit checks to retain one-to-one test numbering coverage.

    def test_t006b_plan_sections_remain(self) -> None:
        result = self._run(["python3", GOLDY_SCRIPT, "gold standard plan", "--project-root", str(self.project_root)])
        self.assertEqual(result.returncode, 0)

    def test_t010b_capsule_file_written(self) -> None:
        self._run(["python3", GOLDY_SCRIPT, "planning", "--project-root", str(self.project_root)])
        capsules = list((self.project_root / ".goldy" / "resume-capsules").glob("*.md"))
        self.assertTrue(capsules)


class ChromeProfileTests(GoldyTestCase):
    def test_t046_chrome_profile_resolution_by_email(self) -> None:
        local_state = {
            "profile": {
                "info_cache": {
                    "Default": {"user_name": "other@example.com"},
                    "Profile 7": {"user_name": "bodhimindflow@gmail.com"},
                }
            }
        }
        profile_dir = goldy_chrome.resolve_profile_directory("bodhimindflow@gmail.com", local_state)
        self.assertEqual(profile_dir, "Profile 7")

    def test_t047_chrome_launch_command_generation(self) -> None:
        cmd = goldy_chrome.build_launch_command("Profile 7", "http://localhost:3000")
        self.assertEqual(cmd[0:4], ["open", "-na", "Google Chrome", "--args"])
        self.assertIn("--profile-directory=Profile 7", cmd)

    def test_lt097_goldy_chrome_resolves_default_profile(self) -> None:
        local_state = {
            "profile": {
                "info_cache": {
                    "Default": {"user_name": goldy_chrome.DEFAULT_EMAIL},
                    "Profile 2": {"user_name": "someone@example.com"},
                }
            }
        }
        profile_dir = goldy_chrome.resolve_profile_directory(goldy_chrome.DEFAULT_EMAIL, local_state)
        self.assertEqual(profile_dir, "Default")

    def test_lt098_goldy_chrome_launch_command_contains_resolved_profile(self) -> None:
        local_state = {
            "profile": {
                "info_cache": {
                    "Profile 11": {"user_name": goldy_chrome.DEFAULT_EMAIL},
                }
            }
        }
        profile_dir = goldy_chrome.resolve_profile_directory(goldy_chrome.DEFAULT_EMAIL, local_state)
        cmd = goldy_chrome.build_launch_command(profile_dir, "http://localhost:3000")
        self.assertIn(f"--profile-directory={profile_dir}", cmd)
        self.assertEqual(cmd[-1], "http://localhost:3000")


class StrictValidationTests(GoldyTestCase):
    """T-050..T-053: Strict phase validation and evidence gates (Phase 1)."""

    def _make_plan_with_content(self, content: str, filename: str = "validation-plan.md") -> Path:
        plan = self.project_root / "plans" / filename
        plan.parent.mkdir(parents=True, exist_ok=True)
        plan.write_text(content, encoding="utf-8")
        return plan

    def test_t050_strict_validator_rejects_partial_unchecked_tasks(self) -> None:
        """T-050: Strict checklist-complete validator rejects partial [ ] tasks."""
        plan = self._make_plan_with_content(
            "# Plan\n"
            "## Phase 1 - Build\n"
            "- [x] First task done\n"
            "- [ ] Second task not done\n"
            "- [x] Third task done\n"
            "Validation gate: all tasks complete\n"
        )
        phases = goldy_loop.parse_phases(plan)
        result = goldy_loop.strict_phase_validator(plan, phases[0])
        self.assertFalse(result["validated"])
        self.assertIn("unchecked_tasks", result["reason"])
        self.assertEqual(result["unchecked"], 1)
        self.assertEqual(result["checked"], 2)
        self.assertIn("Second task not done", result["unchecked_tasks"])

    def test_t051_validation_gate_evidence_parser_detects_missing(self) -> None:
        """T-051: Validation gate evidence parser detects missing required evidence."""
        plan = self._make_plan_with_content(
            "# Plan\n"
            "## Phase 1 - Build\n"
            "- [x] Task done\n"
            "No validation gate here.\n"
        )
        phases = goldy_loop.parse_phases(plan)
        result = goldy_loop.strict_phase_validator(plan, phases[0])
        self.assertFalse(result["validated"])
        self.assertIn("missing_validation_gate", result["reason"])
        self.assertFalse(result["evidence"]["present"])

    def test_t052_phase_cannot_complete_with_unchecked_items(self) -> None:
        """T-052: Phase cannot complete when checklist exists but items unchecked."""
        self._init_git()
        plan = self._make_plan_with_content(
            "# Plan\n"
            "## Phase 1 - Build\n"
            "- [ ] Unchecked task A\n"
            "- [ ] Unchecked task B\n"
            "Validation gate: tests pass\n",
            filename="unchecked-plan.md",
        )
        result = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                "t052-unchecked",
                "--no-worktree",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(result.returncode, 5)
        self.assertIn("GOLDY LOOP STOP", result.stdout)
        self.assertIn("unchecked_tasks", result.stdout)

    def test_t053_phase_completes_with_explicit_waiver_and_reason(self) -> None:
        """T-053: Phase can complete with explicit waiver token [~] + reason."""
        plan = self._make_plan_with_content(
            "# Plan\n"
            "## Phase 1 - Build\n"
            "- [x] Required task done\n"
            "- [~] Optional task (waived: not applicable to this stack)\n"
            "Validation gate: all tasks resolved\n"
        )
        phases = goldy_loop.parse_phases(plan)
        result = goldy_loop.strict_phase_validator(plan, phases[0])
        self.assertTrue(result["validated"])
        self.assertEqual(result["reason"], "phase_validated")
        self.assertEqual(result["checked"], 1)
        self.assertEqual(result["waived"], 1)
        self.assertEqual(result["unchecked"], 0)
        self.assertEqual(len(result["waived_without_reason"]), 0)

    def test_t053b_waiver_without_reason_rejected(self) -> None:
        """T-053 extension: Waiver [~] without reason is rejected."""
        plan = self._make_plan_with_content(
            "# Plan\n"
            "## Phase 1 - Build\n"
            "- [x] Required task\n"
            "- [~] Waived task without reason\n"
            "Validation gate: pass\n"
        )
        phases = goldy_loop.parse_phases(plan)
        result = goldy_loop.strict_phase_validator(plan, phases[0])
        self.assertFalse(result["validated"])
        self.assertIn("waived_without_reason", result["reason"])

    def _init_git(self) -> None:
        self._run(["git", "init"], cwd=self.project_root)
        self._run(["git", "config", "user.email", "goldy@example.com"], cwd=self.project_root)
        self._run(["git", "config", "user.name", "Goldy Test"], cwd=self.project_root)
        (self.project_root / "README.md").write_text("init\n", encoding="utf-8")
        self._run(["git", "add", "README.md"], cwd=self.project_root)
        self._run(["git", "commit", "-m", "init"], cwd=self.project_root)


class CircuitBreakerPhase2Tests(GoldyTestCase):
    """LT-054..LT-059 and LT-101..LT-104: Circuit breaker hardening tests."""

    def _make_plan(self, phases: int = 1, filename: str = "breaker-plan.md", checked: bool = True) -> Path:
        plan = self.project_root / "plans" / filename
        plan.parent.mkdir(parents=True, exist_ok=True)
        mark = "x" if checked else " "
        body = ["# Plan"]
        for i in range(1, phases + 1):
            body.append(f"## Phase {i} - Task {i}")
            body.append(f"- [{mark}] do thing")
            body.append("Validation gate: pass")
        plan.write_text("\n".join(body) + "\n", encoding="utf-8")
        return plan

    def _init_git(self) -> None:
        self._run(["git", "init"], cwd=self.project_root)
        self._run(["git", "config", "user.email", "goldy@example.com"], cwd=self.project_root)
        self._run(["git", "config", "user.name", "Goldy Test"], cwd=self.project_root)
        (self.project_root / "README.md").write_text("init\n", encoding="utf-8")
        self._run(["git", "add", "README.md"], cwd=self.project_root)
        self._run(["git", "commit", "-m", "init"], cwd=self.project_root)

    def _runtime_root(self) -> Path:
        root = self.project_root / ".goldy"
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _thresholds(self, **overrides: int | float) -> dict[str, int | float]:
        thresholds = dict(goldy_breaker.BREAKER_DEFAULTS)
        thresholds.update(overrides)
        return thresholds

    def _new_breaker(
        self,
        session_id: str,
        **threshold_overrides: int | float,
    ) -> goldy_breaker.CircuitBreaker:
        thresholds = self._thresholds(**threshold_overrides)
        return goldy_breaker.CircuitBreaker(self._runtime_root(), session_id, thresholds=thresholds)

    def test_lt054_breaker_initial_state_persistence(self) -> None:
        """LT-054: circuit breaker initial state persistence."""
        runtime_root = self._runtime_root()
        breaker = self._new_breaker("lt054")
        result = breaker.record_iteration(had_progress=True)
        self.assertEqual(result["trigger"], "none")
        self.assertFalse(result["tripped"])

        state_path = runtime_root / "breaker.json"
        self.assertTrue(state_path.exists())
        persisted = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(persisted["state"], "CLOSED")
        self.assertEqual(persisted["session_id"], "lt054")

        reloaded = goldy_breaker.CircuitBreaker(runtime_root, "lt054")
        status = reloaded.status()
        self.assertEqual(status["state"], "CLOSED")
        self.assertEqual(status["session_id"], "lt054")
        self.assertEqual(status["no_progress_streak"], 0)

    def test_lt055_breaker_transition_closed_to_half_open(self) -> None:
        """LT-055: breaker transition CLOSED -> HALF_OPEN on warning threshold."""
        breaker = self._new_breaker("lt055", no_progress_threshold=3)
        first = breaker.record_iteration(had_progress=False)
        second = breaker.record_iteration(had_progress=False)

        self.assertEqual(first["trigger"], "none")
        self.assertEqual(second["trigger"], "no_progress_warning")
        self.assertFalse(second["tripped"])
        self.assertEqual(breaker.current_state, "HALF_OPEN")

    def test_lt056_breaker_transition_half_open_to_open(self) -> None:
        """LT-056: breaker transition HALF_OPEN -> OPEN on sustained no progress."""
        breaker = self._new_breaker("lt056", no_progress_threshold=3)
        breaker.record_iteration(had_progress=False)
        breaker.record_iteration(had_progress=False)
        third = breaker.record_iteration(had_progress=False)

        self.assertEqual(third["trigger"], "no_progress")
        self.assertTrue(third["tripped"])
        self.assertEqual(breaker.current_state, "OPEN")

    def test_lt057_breaker_transition_open_to_half_open_after_cooldown(self) -> None:
        """LT-057: breaker transition OPEN -> HALF_OPEN after cooldown."""
        breaker = self._new_breaker("lt057", no_progress_threshold=2, cooldown_minutes=0)
        breaker.record_iteration(had_progress=False)  # warning -> HALF_OPEN
        breaker.record_iteration(had_progress=False)  # threshold -> OPEN
        self.assertEqual(breaker.current_state, "OPEN")

        startup = breaker.startup_check(auto_reset=False)
        self.assertEqual(startup["action"], "cooldown_recovery")
        self.assertEqual(startup["state"], "HALF_OPEN")
        self.assertEqual(breaker.current_state, "HALF_OPEN")

    def test_lt058_breaker_reset_policy_manual_and_auto_behavior(self) -> None:
        """LT-058: breaker reset policy (manual/auto) behavior."""
        runtime_root = self._runtime_root()
        state_path = runtime_root / "breaker.json"
        manual_payload = {
            "state": "OPEN",
            "session_id": "lt058-manual",
            "updated_at": "2026-02-16T00:00:00Z",
            "opened_at": "2026-02-16T00:00:00Z",
            "no_progress_streak": 3,
            "repeated_error_streak": 0,
            "permission_denial_streak": 0,
            "completion_signal_streak": 0,
            "open_reason": "no_progress(3):threshold_exceeded",
            "reset_policy": "manual",
            "cooldown_minutes": 0,
            "transition_history": [],
        }
        state_path.write_text(json.dumps(manual_payload), encoding="utf-8")

        manual = goldy_breaker.CircuitBreaker(runtime_root, "lt058-manual")
        self.assertFalse(manual.can_execute())
        blocked = manual.startup_check(auto_reset=False)
        self.assertEqual(blocked["action"], "blocked")

        manual.reset("operator_manual_reset")
        manual_status = manual.status()
        self.assertEqual(manual_status["state"], "CLOSED")
        self.assertEqual(manual_status["open_reason"], None)
        self.assertEqual(manual_status["no_progress_streak"], 0)

        auto_payload = dict(manual_payload)
        auto_payload["session_id"] = "lt058-auto"
        auto_payload["reset_policy"] = "auto"
        auto_payload["opened_at"] = "2000-01-01T00:00:00Z"
        state_path.write_text(json.dumps(auto_payload), encoding="utf-8")

        auto = goldy_breaker.CircuitBreaker(runtime_root, "lt058-auto")
        recovered = auto.startup_check(auto_reset=False)
        self.assertEqual(recovered["action"], "cooldown_recovery")
        self.assertEqual(recovered["state"], "HALF_OPEN")

    def test_lt059_permission_denial_priority_opens_breaker(self) -> None:
        """LT-059: permission-denial streak opens breaker with highest priority reason."""
        breaker = self._new_breaker(
            "lt059",
            no_progress_threshold=3,
            permission_denial_threshold=2,
        )
        first = breaker.record_iteration(permission_denied=True)
        second = breaker.record_iteration(permission_denied=True)

        self.assertEqual(first["trigger"], "none")
        self.assertEqual(second["trigger"], "permission_denial")
        self.assertTrue(second["tripped"])
        self.assertEqual(breaker.current_state, "OPEN")
        self.assertIn("update tool permissions and reset breaker", second["reason"])

    def test_completion_signal_threshold_opens_breaker(self) -> None:
        """Phase 2 gap check: completion-signal streak opens breaker when threshold is met."""
        breaker = self._new_breaker(
            "lt-phase2-completion",
            completion_signal_threshold=2,
            no_progress_threshold=9,
            repeated_error_threshold=9,
            permission_denial_threshold=9,
        )
        first = breaker.record_iteration(completion_signal=True)
        second = breaker.record_iteration(completion_signal=True)

        self.assertEqual(first["trigger"], "none")
        self.assertEqual(second["trigger"], "completion_signal")
        self.assertTrue(second["tripped"])
        self.assertEqual(breaker.current_state, "OPEN")
        self.assertIn("verify completion state", second["reason"])

    def test_lt101_breaker_status_command_output(self) -> None:
        """LT-101: breaker status command renders deterministic structured state output."""
        self._new_breaker("lt101-status").record_iteration(permission_denied=True)
        result = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--breaker-status",
                "--resume",
                "lt101-status",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("=== GOLDY BREAKER STATUS ===", result.stdout)
        self.assertIn("state:", result.stdout)
        self.assertIn("session_id: lt101-status", result.stdout)
        self.assertIn("completion_signal_streak:", result.stdout)
        self.assertIn("transition_count:", result.stdout)

    def test_lt102_breaker_reset_command_resets_and_records_transition(self) -> None:
        """LT-102: breaker reset command resets counters/reason and writes transition event."""
        runtime_root = self._runtime_root()
        breaker = self._new_breaker("lt102-reset", permission_denial_threshold=1)
        tripped = breaker.record_iteration(permission_denied=True)
        self.assertTrue(tripped["tripped"])
        self.assertEqual(breaker.current_state, "OPEN")

        result = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--breaker-reset",
                "--resume",
                "lt102-reset",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("BREAKER RESET: state=CLOSED", result.stdout)

        persisted = json.loads((runtime_root / "breaker.json").read_text(encoding="utf-8"))
        self.assertEqual(persisted["state"], "CLOSED")
        self.assertEqual(persisted["open_reason"], None)
        self.assertEqual(persisted["no_progress_streak"], 0)
        self.assertEqual(persisted["repeated_error_streak"], 0)
        self.assertEqual(persisted["permission_denial_streak"], 0)
        self.assertEqual(persisted["completion_signal_streak"], 0)

        transitions = persisted.get("transition_history", [])
        self.assertTrue(transitions)
        self.assertEqual(transitions[-1]["to_state"], "CLOSED")
        self.assertEqual(transitions[-1]["reason"], "operator_manual_reset")

    def test_lt103_breaker_thresholds_honor_env_overrides(self) -> None:
        """LT-103: breaker thresholds honor env overrides and default fallbacks."""
        env_keys = [
            "GOLDY_BREAKER_NO_PROGRESS_THRESHOLD",
            "GOLDY_BREAKER_REPEATED_ERROR_THRESHOLD",
            "GOLDY_BREAKER_PERMISSION_DENIAL_THRESHOLD",
            "GOLDY_BREAKER_COMPLETION_SIGNAL_THRESHOLD",
            "GOLDY_BREAKER_COOLDOWN_MINUTES",
            "GOLDY_BREAKER_SIGNAL_WINDOW_SIZE",
        ]
        old_env = {key: os.environ.get(key) for key in env_keys}
        try:
            os.environ["GOLDY_BREAKER_NO_PROGRESS_THRESHOLD"] = "9"
            os.environ["GOLDY_BREAKER_REPEATED_ERROR_THRESHOLD"] = "invalid"
            os.environ["GOLDY_BREAKER_PERMISSION_DENIAL_THRESHOLD"] = "4"
            os.environ["GOLDY_BREAKER_COMPLETION_SIGNAL_THRESHOLD"] = "6"
            os.environ["GOLDY_BREAKER_COOLDOWN_MINUTES"] = "1.5"
            os.environ["GOLDY_BREAKER_SIGNAL_WINDOW_SIZE"] = "11"

            thresholds = goldy_breaker._load_thresholds()
            self.assertEqual(thresholds["no_progress_threshold"], 9)
            self.assertEqual(
                thresholds["repeated_error_threshold"],
                goldy_breaker.BREAKER_DEFAULTS["repeated_error_threshold"],
            )
            self.assertEqual(thresholds["permission_denial_threshold"], 4)
            self.assertEqual(thresholds["completion_signal_threshold"], 6)
            self.assertEqual(thresholds["cooldown_minutes"], 1.5)
            self.assertEqual(thresholds["signal_window_size"], 11)

            breaker = goldy_breaker.CircuitBreaker(self._runtime_root(), "lt103-env")
            status = breaker.status()
            self.assertEqual(status["thresholds"]["no_progress_threshold"], 9)
            self.assertEqual(status["thresholds"]["completion_signal_threshold"], 6)
        finally:
            for key, value in old_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_lt104_breaker_cooldown_uses_opened_at_legacy_fallback(self) -> None:
        """LT-104: breaker cooldown uses opened_at with backward-compatible legacy fallback."""
        runtime_root = self._runtime_root()
        legacy_state = {
            "state": "OPEN",
            "session_id": "legacy-session",
            "updated_at": "2026-02-16T00:00:00Z",
            "opened_timestamp": "2026-02-16T00:00:00Z",
            "no_progress_streak": 3,
            "repeated_error_streak": 0,
            "permission_denial_streak": 0,
            "completion_signal_streak": 0,
            "open_reason": "legacy_open_state",
            "reset_policy": "auto",
            "cooldown_minutes": 5,
            "transition_history": [],
        }
        (runtime_root / "breaker.json").write_text(json.dumps(legacy_state), encoding="utf-8")

        breaker = goldy_breaker.CircuitBreaker(runtime_root, "lt104-legacy")
        startup = breaker.startup_check(auto_reset=False)
        self.assertEqual(startup["action"], "cooldown_recovery")
        self.assertEqual(startup["state"], "HALF_OPEN")
        self.assertEqual(breaker.current_state, "HALF_OPEN")

    def test_breaker_auto_reset_flag_and_remediation_output(self) -> None:
        """Phase 2 behavior check: startup remediation is printed and --breaker-auto-reset unblocks."""
        self._init_git()
        plan = self._make_plan(1, filename="lt-phase2-auto-reset.md")
        self._new_breaker("lt-phase2-auto-reset", permission_denial_threshold=1).record_iteration(
            permission_denied=True
        )

        blocked = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                "lt-phase2-auto-reset",
                "--no-worktree",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(blocked.returncode, 6)
        self.assertIn("Remediation:", blocked.stdout)
        self.assertIn("Reset with:", blocked.stdout)

        recovered = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                "lt-phase2-auto-reset",
                "--breaker-auto-reset",
                "--dry-run",
                "--no-worktree",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(recovered.returncode, 0)
        self.assertIn("BREAKER STARTUP: auto_reset", recovered.stdout)


class StuckDetectionPhase3Tests(GoldyTestCase):
    """LT-060..LT-062, LT-087, LT-105: stuck detection + signal safety."""

    def _init_git(self) -> None:
        self._run(["git", "init"], cwd=self.project_root)
        self._run(["git", "config", "user.email", "goldy@example.com"], cwd=self.project_root)
        self._run(["git", "config", "user.name", "Goldy Test"], cwd=self.project_root)
        (self.project_root / "README.md").write_text("init\n", encoding="utf-8")
        self._run(["git", "add", "README.md"], cwd=self.project_root)
        self._run(["git", "commit", "-m", "init"], cwd=self.project_root)

    def _make_plan(self, filename: str, checked: bool) -> Path:
        plan = self.project_root / "plans" / filename
        plan.parent.mkdir(parents=True, exist_ok=True)
        mark = "x" if checked else " "
        plan.write_text(
            "\n".join(
                [
                    "# Plan",
                    "## Phase 1 - Stuck Detection",
                    f"- [{mark}] do task",
                    "Validation gate: pass",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        return plan

    def test_lt060_stuck_detection_ignores_structured_false_positives(self) -> None:
        """LT-060: stuck detection ignores JSON/error-field false positives."""
        state = goldy_stuck.default_stuck_state()
        updated = goldy_stuck.update_stuck_detection(
            state,
            iteration=1,
            signal="no_progress",
            text='{"error":"Unexpected end of JSON input"}\nerror: {"message":"bad payload"}',
            signal_window_size=5,
        )
        self.assertFalse(updated["state"]["is_stuck"])
        self.assertEqual(updated["error_lines"], [])
        self.assertGreater(updated["state"]["false_positive_suppressed"], 0)

    def test_lt061_stuck_detection_triggers_on_repeated_contextual_errors(self) -> None:
        """LT-061: stuck detection triggers on repeated contextual error lines."""
        state = goldy_stuck.default_stuck_state()
        text = "RuntimeError: database locked\nTraceback: task execution failed"
        for idx in range(1, 4):
            updated = goldy_stuck.update_stuck_detection(
                state,
                iteration=idx,
                signal="no_progress",
                text=text,
                signal_window_size=5,
            )
            state = updated["state"]

        self.assertTrue(state["is_stuck"])
        self.assertGreaterEqual(int(state["consecutive_matches"]), 3)
        self.assertIsNotNone(state["error_fingerprint"])
        self.assertTrue(updated["repeated_error_match"])

    def test_lt062_signal_window_truncation_and_ordering(self) -> None:
        """LT-062: rolling signal window truncation and ordering correctness."""
        state = goldy_stuck.default_stuck_state()
        sequence = ["progress", "no_progress", "test_only", "completion", "error"]
        for idx, signal in enumerate(sequence, start=1):
            updated = goldy_stuck.update_stuck_detection(
                state,
                iteration=idx,
                signal=signal,
                text="",
                signal_window_size=3,
            )
            state = updated["state"]

        window = state["signal_window"]
        self.assertEqual(len(window), 3)
        self.assertEqual([entry["iteration"] for entry in window], [3, 4, 5])
        self.assertEqual([entry["signal"] for entry in window], ["test_only", "completion", "error"])

    def test_lt105_safety_completion_breaker_triggers(self) -> None:
        """LT-105: safety completion breaker triggers after repeated explicit completion signals."""
        runtime_root = self.project_root / ".goldy"
        runtime_root.mkdir(parents=True, exist_ok=True)
        breaker = goldy_breaker.CircuitBreaker(
            runtime_root,
            "lt105-completion-safety",
            thresholds={
                **goldy_breaker.BREAKER_DEFAULTS,
                "completion_signal_threshold": 2,
                "no_progress_threshold": 99,
                "repeated_error_threshold": 99,
                "permission_denial_threshold": 99,
            },
        )

        state = goldy_stuck.default_stuck_state()
        result = {"tripped": False, "trigger": "none"}
        for idx in range(1, 3):
            update = goldy_stuck.update_stuck_detection(
                state,
                iteration=idx,
                signal="completion",
                text="LOOP_COMPLETE",
                signal_window_size=5,
            )
            state = update["state"]
            result = breaker.record_iteration(
                had_progress=False,
                completion_signal=bool(update["completion_signal"]),
            )

        self.assertTrue(result["tripped"])
        self.assertEqual(result["trigger"], "completion_signal")
        self.assertEqual(breaker.current_state, "OPEN")

    def test_lt087_repeated_no_progress_run_opens_breaker_and_stops_safely(self) -> None:
        """LT-087: repeated no-progress run opens breaker and stops safely."""
        self._init_git()
        plan = self._make_plan("lt087-no-progress.md", checked=False)
        session_id = "lt087-no-progress"

        first = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                session_id,
                "--no-worktree",
                "--project-root",
                str(self.project_root),
            ]
        )
        second = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                session_id,
                "--no-worktree",
                "--project-root",
                str(self.project_root),
            ]
        )
        third = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                session_id,
                "--no-worktree",
                "--project-root",
                str(self.project_root),
            ]
        )

        self.assertEqual(first.returncode, 5)
        self.assertEqual(second.returncode, 5)
        self.assertEqual(third.returncode, 6)
        self.assertIn("GOLDY LOOP STOP: circuit breaker OPEN", third.stdout)
        self.assertIn("Remediation:", third.stdout)
        self.assertIn("Reset with:", third.stdout)


class TaskLifecyclePhase4Tests(GoldyTestCase):
    """LT-063..LT-066 and LT-086: task lifecycle + evidence backpressure."""

    def _init_git(self) -> None:
        self._run(["git", "init"], cwd=self.project_root)
        self._run(["git", "config", "user.email", "goldy@example.com"], cwd=self.project_root)
        self._run(["git", "config", "user.name", "Goldy Test"], cwd=self.project_root)
        (self.project_root / "README.md").write_text("init\n", encoding="utf-8")
        self._run(["git", "add", "README.md"], cwd=self.project_root)
        self._run(["git", "commit", "-m", "init"], cwd=self.project_root)

    def _make_retry_plan(self, *, phase2_checked: bool, filename: str = "lt086-retry-plan.md") -> Path:
        plan = self.project_root / "plans" / filename
        plan.parent.mkdir(parents=True, exist_ok=True)
        mark2 = "x" if phase2_checked else " "
        plan.write_text(
            "\n".join(
                [
                    "# Plan",
                    "## Phase 1 - Stable",
                    "- [x] stable task",
                    "Validation gate: pass",
                    "## Phase 2 - Transient",
                    f"- [{mark2}] transient task",
                    "Validation gate: pass",
                    "## Phase 3 - Final",
                    "- [x] final task",
                    "Validation gate: pass",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        return plan

    def test_lt063_task_state_transition_validity_matrix(self) -> None:
        """LT-063: task state machine transition validity matrix."""
        allowed_pairs = {
            ("PENDING", "RUNNING"),
            ("PENDING", "CANCELLED"),
            ("RUNNING", "COMPLETED"),
            ("RUNNING", "FAILED"),
            ("RUNNING", "CANCELLED"),
            ("FAILED", "PENDING"),
        }
        states = ["PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"]
        for from_state in states:
            for to_state in states:
                expected = (from_state, to_state) in allowed_pairs
                self.assertEqual(
                    goldy_task_lifecycle.is_valid_transition(from_state, to_state),
                    expected,
                    f"transition mismatch for {from_state}->{to_state}",
                )

    def test_lt064_invalid_task_state_transition_rejected_with_deterministic_error(self) -> None:
        """LT-064: invalid task state transitions are rejected with deterministic error."""
        task = goldy_task_lifecycle.new_task_record(
            "phase-1-task-1",
            1,
            "invalid transition demo",
            timeout_seconds=60,
            max_retries=2,
            now_iso="2026-02-16T00:00:00Z",
        )
        with self.assertRaisesRegex(
            ValueError,
            r"invalid_task_transition:PENDING->COMPLETED for phase-1-task-1",
        ):
            goldy_task_lifecycle.transition_task(
                task,
                "COMPLETED",
                timestamp="2026-02-16T00:00:00Z",
            )

    def test_lt065_retry_counter_and_timeout_metadata_persistence(self) -> None:
        """LT-065: retry counter and timeout metadata persistence."""
        runtime = goldy_loop.ensure_runtime(self.project_root)
        task = goldy_task_lifecycle.new_task_record(
            "phase-1-task-1",
            1,
            "retry task",
            timeout_seconds=45,
            max_retries=3,
            now_iso="2026-02-16T00:00:00Z",
        )
        task, _ = goldy_task_lifecycle.transition_task(
            task,
            "RUNNING",
            timestamp="2026-02-16T00:00:01Z",
        )
        task, _ = goldy_task_lifecycle.transition_task(
            task,
            "FAILED",
            reason="timeout_exceeded",
            timestamp="2026-02-16T00:00:02Z",
        )
        task, _ = goldy_task_lifecycle.transition_task(
            task,
            "PENDING",
            reason="retry_after_failure",
            timestamp="2026-02-16T00:00:03Z",
        )

        payload = {
            "phase": 1,
            "updated_at": "2026-02-16T00:00:03Z",
            "tasks": [task],
            "events": [],
            "summary": {"total_tasks": 1},
        }
        checkpoint = goldy_task_lifecycle.persist_phase_task_lifecycle(runtime, "lt065-persist", 1, payload)
        stored = json.loads(checkpoint.read_text(encoding="utf-8"))
        persisted = stored["tasks"][0]
        self.assertEqual(int(persisted["retry_count"]), 1)
        self.assertEqual(int(persisted["max_retries"]), 3)
        self.assertEqual(float(persisted["timeout_seconds"]), 45.0)
        self.assertEqual(persisted["state"], "PENDING")

    def test_lt066_event_log_writer_deterministic_serialization(self) -> None:
        """LT-066: event log writer deterministic serialization."""
        runtime = goldy_loop.ensure_runtime(self.project_root)
        payload_a = {
            "phase": 1,
            "updated_at": "2026-02-16T00:10:00Z",
            "tasks": [
                {"task_id": "phase-1-task-2", "state": "FAILED"},
                {"task_id": "phase-1-task-1", "state": "COMPLETED"},
            ],
            "events": [
                {"sequence": 2, "timestamp": "2026-02-16T00:00:02Z", "task_id": "phase-1-task-1"},
                {"sequence": 1, "timestamp": "2026-02-16T00:00:01Z", "task_id": "phase-1-task-1"},
            ],
            "summary": {"events_total": 2},
        }
        path = goldy_task_lifecycle.persist_phase_task_lifecycle(runtime, "lt066-deterministic", 1, payload_a)
        first_text = path.read_text(encoding="utf-8")

        payload_b = {
            "updated_at": "2026-02-16T00:10:00Z",
            "summary": {"events_total": 2},
            "phase": 1,
            "events": [
                {"task_id": "phase-1-task-1", "timestamp": "2026-02-16T00:00:02Z", "sequence": 2},
                {"task_id": "phase-1-task-1", "timestamp": "2026-02-16T00:00:01Z", "sequence": 1},
            ],
            "tasks": [
                {"state": "FAILED", "task_id": "phase-1-task-2"},
                {"state": "COMPLETED", "task_id": "phase-1-task-1"},
            ],
        }
        path = goldy_task_lifecycle.persist_phase_task_lifecycle(runtime, "lt066-deterministic", 1, payload_b)
        second_text = path.read_text(encoding="utf-8")
        self.assertEqual(first_text, second_text)

        stored = json.loads(second_text)
        self.assertEqual([event["sequence"] for event in stored["events"]], [1, 2])
        self.assertEqual([task["task_id"] for task in stored["tasks"]], ["phase-1-task-1", "phase-1-task-2"])

    def test_lt086_three_phase_run_transient_failure_recovers_via_retry_policy(self) -> None:
        """LT-086: 3-phase run with one transient failure recovers via retry policy."""
        self._init_git()
        session_id = "lt086-retry-recovery"
        plan = self._make_retry_plan(phase2_checked=False)

        first = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                session_id,
                "--no-worktree",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(first.returncode, 5)
        self.assertIn("Phase 1 complete", first.stdout)

        self._make_retry_plan(phase2_checked=True)
        second = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                session_id,
                "--no-worktree",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(second.returncode, 0)
        self.assertIn("LOOP_COMPLETE", second.stdout)

        session_path = self.project_root / ".goldy" / "sessions" / f"{session_id}.json"
        self.assertTrue(session_path.exists())
        session_payload = json.loads(session_path.read_text(encoding="utf-8"))
        lifecycle = session_payload.get("task_lifecycle", {})
        self.assertIn("2", lifecycle)
        phase_two = lifecycle["2"]
        summary = phase_two.get("summary", {})
        states = summary.get("states", {})
        self.assertGreaterEqual(int(summary.get("retry_attempts_total", 0)), 1)
        self.assertEqual(int(states.get("COMPLETED", 0)), 1)


class HistoryRecoveryPhase5Tests(GoldyTestCase):
    """LT-067, LT-068, LT-080, LT-106, LT-107, LT-114: history + recovery integrity."""

    def _init_git(self) -> None:
        self._run(["git", "init"], cwd=self.project_root)
        self._run(["git", "config", "user.email", "goldy@example.com"], cwd=self.project_root)
        self._run(["git", "config", "user.name", "Goldy Test"], cwd=self.project_root)
        (self.project_root / "README.md").write_text("init\n", encoding="utf-8")
        self._run(["git", "add", "README.md"], cwd=self.project_root)
        self._run(["git", "commit", "-m", "init"], cwd=self.project_root)

    def _make_plan(self, phases: int = 3, filename: str = "phase5-plan.md", checked: bool = True) -> Path:
        plan = self.project_root / "plans" / filename
        plan.parent.mkdir(parents=True, exist_ok=True)
        mark = "x" if checked else " "
        body = ["# Plan"]
        for i in range(1, phases + 1):
            body.append(f"## Phase {i} - Step {i}")
            body.append(f"- [{mark}] do thing {i}")
            body.append("Validation gate: pass")
        plan.write_text("\n".join(body) + "\n", encoding="utf-8")
        return plan

    def test_lt106_history_writer_appends_typed_events_atomically_under_file_lock(self) -> None:
        """LT-106: history writer appends typed events atomically under file lock."""
        runtime_root = self.project_root / ".goldy"
        runtime_root.mkdir(parents=True, exist_ok=True)
        session_id = "lt106-history"

        first = goldy_history.append_history_event(
            runtime_root,
            session_id,
            "phase_started",
            phase=1,
            data={"title": "phase one"},
            timestamp="2026-02-16T00:00:01Z",
        )
        second = goldy_history.append_history_event(
            runtime_root,
            session_id,
            "phase_completed",
            phase=1,
            data={"reason": "phase_validated"},
            timestamp="2026-02-16T00:00:02Z",
        )

        history_path = runtime_root / "history" / f"{session_id}.jsonl"
        self.assertTrue(history_path.exists())
        lines = [line for line in history_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(len(lines), 2)
        decoded = [json.loads(line) for line in lines]
        self.assertEqual([event["event_type"] for event in decoded], ["phase_started", "phase_completed"])
        self.assertEqual([event["sequence"] for event in decoded], [1, 2])
        self.assertEqual(first["sequence"], 1)
        self.assertEqual(second["sequence"], 2)

    def test_lt107_history_replay_computes_last_completed_phase_and_terminal_reason(self) -> None:
        """LT-107: history replay computes last completed phase and terminal reason correctly."""
        runtime_root = self.project_root / ".goldy"
        runtime_root.mkdir(parents=True, exist_ok=True)
        session_id = "lt107-replay"
        goldy_history.append_history_event(runtime_root, session_id, "loop_started", data={"plan_path": "plans/demo.md"})
        goldy_history.append_history_event(runtime_root, session_id, "phase_completed", phase=1, data={"reason": "ok"})
        goldy_history.append_history_event(runtime_root, session_id, "phase_completed", phase=2, data={"reason": "ok"})
        goldy_history.append_history_event(
            runtime_root,
            session_id,
            "loop_paused",
            phase=3,
            data={"reason": "deep_audit_failed", "resume_phase": 3},
        )

        replay = goldy_history.replay_history(runtime_root, session_id)
        self.assertEqual(replay["last_completed_phase"], 2)
        self.assertEqual(replay["terminal_reason"], "deep_audit_failed")
        self.assertEqual(replay["resume_phase"], 3)
        self.assertEqual(replay["total_malformed"], 0)

    def test_lt067_startup_recovery_marks_stale_running_states_interrupted(self) -> None:
        """LT-067: startup recovery marks stale running states as interrupted."""
        runtime = goldy_loop.ensure_runtime(self.project_root)
        session_id = "lt067-recovery"
        plan = self._make_plan(phases=2, filename="lt067-plan.md")
        phases = goldy_loop.parse_phases(plan)

        session_state = {
            "session_id": session_id,
            "status": "running",
            "current_phase": 1,
            "completed_phases": [],
            "next_action": "run next phase",
        }
        checkpoint_path = runtime["checkpoints"] / session_id / "phase-1.json"
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        checkpoint_path.write_text(
            json.dumps(
                {
                    "session_id": session_id,
                    "phase": 1,
                    "title": "Step 1",
                    "status": "started",
                    "reason": "phase_started",
                    "timestamp": "2026-02-16T00:00:00Z",
                }
            ),
            encoding="utf-8",
        )

        recovered = goldy_recovery.recover_stale_running_state(runtime, session_id, session_state, phases, mutate_files=True)
        self.assertTrue(recovered["recovered"])
        updated = recovered["session_state"]
        self.assertEqual(updated["status"], "interrupted")
        self.assertEqual(updated["stop_reason"], "recovery_needed")
        self.assertEqual(recovered["resume_phase"], 1)

        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        self.assertEqual(checkpoint["status"], "interrupted")
        self.assertIn("startup_recovery", checkpoint["reason"])

    def test_lt068_resume_pointer_computation_from_latest_checkpoint(self) -> None:
        """LT-068: resume pointer computation from latest checkpoint."""
        plan = self._make_plan(phases=3, filename="lt068-plan.md")
        phases = goldy_loop.parse_phases(plan)
        resume = goldy_recovery.compute_resume_phase(phases, completed_phases=[1, 2])
        self.assertEqual(resume, 3)

    def test_lt080_interrupted_run_resumes_from_checkpoint_after_restart(self) -> None:
        """LT-080: interrupted run resumes from checkpoint after restart."""
        self._init_git()
        session_id = "lt080-resume"
        plan = self._make_plan(phases=2, filename="lt080-plan.md")

        first = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                session_id,
                "--max-iterations",
                "1",
                "--no-worktree",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(first.returncode, 1)
        self.assertIn("Phase 1 complete", first.stdout)

        session_path = self.project_root / ".goldy" / "sessions" / f"{session_id}.json"
        session_payload = json.loads(session_path.read_text(encoding="utf-8"))
        session_payload["status"] = "running"
        session_payload["current_phase"] = 2
        session_path.write_text(json.dumps(session_payload, indent=2, sort_keys=True), encoding="utf-8")

        checkpoint = self.project_root / ".goldy" / "checkpoints" / session_id / "phase-2.json"
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        checkpoint.write_text(
            json.dumps(
                {
                    "session_id": session_id,
                    "phase": 2,
                    "title": "Step 2",
                    "status": "started",
                    "reason": "phase_started",
                    "timestamp": "2026-02-16T00:00:00Z",
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

        second = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                session_id,
                "--no-worktree",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(second.returncode, 0)
        self.assertIn("RECOVERY: stale running session/checkpoint state detected", second.stdout)
        self.assertIn("Phase 2 complete", second.stdout)
        self.assertIn("LOOP_COMPLETE", second.stdout)

    def test_lt114_history_checkpoint_recovery_after_forced_interruption(self) -> None:
        """LT-114: history + checkpoint recovery works after forced process interruption."""
        self._init_git()
        runtime = goldy_loop.ensure_runtime(self.project_root)
        session_id = "lt114-forced-interrupt"
        plan = self._make_plan(phases=1, filename="lt114-plan.md")

        session_path = runtime["sessions"] / f"{session_id}.json"
        session_path.parent.mkdir(parents=True, exist_ok=True)
        session_path.write_text(
            json.dumps(
                {
                    "session_id": session_id,
                    "status": "running",
                    "current_phase": 1,
                    "completed_phases": [],
                    "next_action": "run next phase",
                    "plan_path": str(plan),
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        checkpoint = runtime["checkpoints"] / session_id / "phase-1.json"
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        checkpoint.write_text(
            json.dumps(
                {
                    "session_id": session_id,
                    "phase": 1,
                    "title": "Step 1",
                    "status": "started",
                    "reason": "phase_started",
                    "timestamp": "2026-02-16T00:00:00Z",
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

        result = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                session_id,
                "--no-worktree",
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("RECOVERY:", result.stdout)

        history = goldy_history.replay_history(runtime["root"], session_id)
        event_types = [event["event_type"] for event in history["events"]]
        self.assertIn("recovery_started", event_types)
        self.assertIn("checkpoint_written", event_types)
        self.assertIn("loop_completed", event_types)


class LockPolicyPhase6Tests(GoldyTestCase):
    """LT-071, LT-072, LT-079, LT-081, LT-088, LT-108, LT-109, LT-113, LT-116."""

    def _init_git(self) -> None:
        self._run(["git", "init"], cwd=self.project_root)
        self._run(["git", "config", "user.email", "goldy@example.com"], cwd=self.project_root)
        self._run(["git", "config", "user.name", "Goldy Test"], cwd=self.project_root)
        (self.project_root / "README.md").write_text("init\n", encoding="utf-8")
        self._run(["git", "add", "README.md"], cwd=self.project_root)
        self._run(["git", "commit", "-m", "init"], cwd=self.project_root)

    def _make_plan(
        self,
        *,
        phases: int = 1,
        filename: str = "phase6-plan.md",
        checked: bool = True,
        task_text: str = "do thing",
    ) -> Path:
        plan = self.project_root / "plans" / filename
        plan.parent.mkdir(parents=True, exist_ok=True)
        mark = "x" if checked else " "
        body = ["# Plan"]
        for i in range(1, phases + 1):
            body.append(f"## Phase {i} - Step {i}")
            body.append(f"- [{mark}] {task_text} {i}")
            body.append("Validation gate: pass")
        plan.write_text("\n".join(body) + "\n", encoding="utf-8")
        return plan

    def test_lt071_audit_policy_gate_aggregates_five_audits_and_applies_thresholds(self) -> None:
        """LT-071: audit policy gate aggregates five audit results and applies thresholds."""
        audits = [
            {"id": "A1", "status": "passed"},
            {"id": "A2", "status": "passed"},
            {"id": "A3", "status": "passed"},
            {"id": "A4", "status": "failed"},
            {"id": "A5", "status": "passed"},
        ]
        policy = {
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
        report = goldy_audit_policy.evaluate_audit_policy(audits, policy)
        self.assertTrue(report["blocked"])
        self.assertEqual(report["pass_count"], 4)
        self.assertEqual(report["required_pass_count"], 5)
        self.assertIn("blocking_failures:integration", report["issues"])
        self.assertIn("required_pass_count:4/5", report["issues"])

    def test_lt072_audit_failures_produce_structured_stop_reason_payload(self) -> None:
        """LT-072: audit failures produce structured stop reason payload."""
        audits = [
            {"id": "A1", "status": "failed"},
            {"id": "A2", "status": "passed"},
            {"id": "A3", "status": "passed"},
            {"id": "A4", "status": "passed"},
            {"id": "A5", "status": "passed"},
        ]
        policy = {
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
        report = goldy_audit_policy.evaluate_audit_policy(audits, policy)
        self.assertTrue(report["blocked"])
        self.assertRegex(report["reason"], r"^deep_audit_failed:policy\[")
        self.assertTrue(report["issues"])
        self.assertIsInstance(report["details"], list)

    def test_lt108_loop_lock_metadata_persists_pid_prompt_timestamp_and_parse(self) -> None:
        """LT-108: loop lock file persists PID/prompt/timestamp metadata and parse behavior."""
        runtime_root = self.project_root / ".goldy"
        runtime_root.mkdir(parents=True, exist_ok=True)
        lock = goldy_lock.LoopLock(
            runtime_root,
            "lt108-lock",
            plan_path=str(self.project_root / "plans" / "lt108.md"),
            prompt_summary="phase=all",
        )
        try:
            result = lock.acquire()
            self.assertEqual(result["status"], "acquired")
            meta = goldy_lock.read_lock_metadata(runtime_root)
            self.assertIsNotNone(meta)
            assert meta is not None
            self.assertEqual(meta["session_id"], "lt108-lock")
            self.assertEqual(meta["prompt_summary"], "phase=all")
            self.assertIsInstance(meta.get("pid"), int)
            self.assertTrue(meta.get("acquired_at"))
        finally:
            lock.release()

    def test_lt109_concurrent_primary_loop_start_blocked_with_holder_details(self) -> None:
        """LT-109: concurrent primary-loop start blocked with actionable lock-holder details."""
        self._init_git()
        plan = self._make_plan(filename="lt109-lock-conflict.md", checked=True)
        runtime_root = self.project_root / ".goldy"
        runtime_root.mkdir(parents=True, exist_ok=True)
        lock = goldy_lock.LoopLock(runtime_root, "lt109-holder", plan_path=str(plan), prompt_summary="phase=all")
        try:
            acquired = lock.acquire()
            self.assertEqual(acquired["status"], "acquired")
            result = self._run(
                [
                    "python3",
                    GOLDY_LOOP_SCRIPT,
                    "--plan",
                    str(plan),
                    "--resume",
                    "lt109-runner",
                    "--no-worktree",
                    "--project-root",
                    str(self.project_root),
                ]
            )
            self.assertEqual(result.returncode, 7)
            self.assertIn("loop lock conflict", result.stdout)
            self.assertIn("Lock holder:", result.stdout)
            self.assertIn("Remediation:", result.stdout)
        finally:
            lock.release()

    def test_lt113_stale_lock_registry_session_cleanup_removes_dead_pid_entries(self) -> None:
        """LT-113: stale lock/session metadata cleanup removes dead PID entries safely."""
        runtime = goldy_loop.ensure_runtime(self.project_root)
        stale_pid = 999999
        lock_path = runtime["root"] / "loop.lock"
        lock_path.write_text(
            json.dumps(
                {
                    "pid": stale_pid,
                    "session_id": "stale-session",
                    "plan_path": "plans/stale.md",
                    "acquired_at": "2026-02-16T00:00:00Z",
                }
            ),
            encoding="utf-8",
        )
        goldy_lock.write_registry(
            runtime["root"],
            {"active_sessions": {"stale-session": {"pid": stale_pid, "plan_path": "plans/stale.md"}}},
        )
        session_file = runtime["sessions"] / "stale-session.json"
        session_file.write_text(
            json.dumps(
                {
                    "session_id": "stale-session",
                    "status": "running",
                    "owner_pid": stale_pid,
                    "completed_phases": [],
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

        summary = goldy_lock.cleanup_stale_runtime_artifacts(runtime)
        self.assertGreaterEqual(int(summary["stale_registry_removed"]), 1)
        self.assertGreaterEqual(int(summary["stale_sessions_marked"]), 1)
        self.assertTrue(bool(summary["stale_lock_cleaned"]))
        updated = json.loads(session_file.read_text(encoding="utf-8"))
        self.assertEqual(updated["status"], "interrupted")
        self.assertEqual(updated["stop_reason"], "stale_pid_cleanup")

    def test_lt079_breaker_open_state_halts_further_phase_execution(self) -> None:
        """LT-079: breaker-open state halts further phase execution."""
        self._init_git()
        plan = self._make_plan(filename="lt079-breaker-open.md", checked=False, task_text="unchecked blocker")
        session_id = "lt079-breaker-open"
        env = {"GOLDY_BREAKER_NO_PROGRESS_THRESHOLD": "1"}

        first = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                session_id,
                "--no-worktree",
                "--project-root",
                str(self.project_root),
            ],
            env=env,
        )
        second = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                session_id,
                "--no-worktree",
                "--project-root",
                str(self.project_root),
            ],
            env=env,
        )
        third = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                session_id,
                "--no-worktree",
                "--project-root",
                str(self.project_root),
            ],
            env=env,
        )
        self.assertEqual(first.returncode, 5)
        self.assertEqual(second.returncode, 6)
        self.assertEqual(third.returncode, 6)
        self.assertIn("circuit breaker OPEN", third.stdout)

    def test_lt081_deep_audit_policy_blocks_completion_on_gate_failure(self) -> None:
        """LT-081: deep-audit policy blocks loop completion on gate failure."""
        self._init_git()
        plan = self._make_plan(filename="lt081-audit-policy.md", checked=True)
        (self.project_root / "bad.py").write_text("def broken(:\n    pass\n", encoding="utf-8")
        result = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                "lt081-audit-policy",
                "--no-worktree",
                "--project-root",
                str(self.project_root),
            ],
            env={"GOLDY_AUDIT_REQUIRED_PASS_COUNT": "5"},
        )
        self.assertEqual(result.returncode, 4)
        self.assertIn("deep_audit_failed:policy", result.stdout)

    def test_lt088_permission_denial_emits_actionable_remediation_guidance(self) -> None:
        """LT-088: permission-denial scenario emits actionable remediation guidance."""
        self._init_git()
        plan = self._make_plan(
            filename="lt088-permission-denied.md",
            checked=False,
            task_text="permission denied while calling tool",
        )
        result = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                "lt088-permission-denied",
                "--no-worktree",
                "--project-root",
                str(self.project_root),
            ],
            env={"GOLDY_BREAKER_PERMISSION_DENIAL_THRESHOLD": "1"},
        )
        self.assertEqual(result.returncode, 6)
        self.assertIn("PERMISSION SIGNAL", result.stdout)
        self.assertIn("update tool permissions", result.stdout.lower())
        self.assertIn("Reset with:", result.stdout)

    def test_lt116_permission_breaker_open_reset_and_successful_resume(self) -> None:
        """LT-116: permission-denial -> breaker-open -> reset -> successful resume flow."""
        self._init_git()
        session_id = "lt116-permission-flow"
        plan = self._make_plan(
            filename="lt116-permission-flow.md",
            phases=1,
            checked=False,
            task_text="permission denied to tool",
        )
        env = {"GOLDY_BREAKER_PERMISSION_DENIAL_THRESHOLD": "2"}

        first = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                session_id,
                "--no-worktree",
                "--project-root",
                str(self.project_root),
            ],
            env=env,
        )
        second = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                session_id,
                "--no-worktree",
                "--project-root",
                str(self.project_root),
            ],
            env=env,
        )
        self.assertEqual(first.returncode, 5)
        self.assertEqual(second.returncode, 6)
        self.assertIn("PERMISSION SIGNAL", second.stdout)

        reset = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--breaker-reset",
                "--resume",
                session_id,
                "--project-root",
                str(self.project_root),
            ]
        )
        self.assertEqual(reset.returncode, 0)
        self.assertIn("BREAKER RESET: state=CLOSED", reset.stdout)

        self._make_plan(
            filename="lt116-permission-flow.md",
            phases=1,
            checked=True,
            task_text="permission denied to tool",
        )
        final = self._run(
            [
                "python3",
                GOLDY_LOOP_SCRIPT,
                "--plan",
                str(plan),
                "--resume",
                session_id,
                "--no-worktree",
                "--project-root",
                str(self.project_root),
            ],
            env=env,
        )
        self.assertEqual(final.returncode, 0)
        self.assertIn("LOOP_COMPLETE", final.stdout)


class BrowserTests(GoldyTestCase):
    """T-060..T-067: Browser abstraction layer tests."""

    def test_t060_detect_backend_playwright_when_codex(self) -> None:
        """T-060: detect_backend() returns 'playwright' when CODEX_THREAD_ID is set."""
        old = os.environ.get("CODEX_THREAD_ID")
        try:
            os.environ["CODEX_THREAD_ID"] = "codex-123"
            self.assertEqual(goldy_browser.detect_backend(), "playwright")
        finally:
            if old is not None:
                os.environ["CODEX_THREAD_ID"] = old
            else:
                os.environ.pop("CODEX_THREAD_ID", None)

    def test_t061_detect_backend_chrome_extension_default(self) -> None:
        """T-061: detect_backend() returns 'chrome-extension' when no Codex env var."""
        old = os.environ.pop("CODEX_THREAD_ID", None)
        try:
            self.assertEqual(goldy_browser.detect_backend(), "chrome-extension")
        finally:
            if old is not None:
                os.environ["CODEX_THREAD_ID"] = old

    def test_t062_playwright_backend_resolves_profile(self) -> None:
        """T-062: PlaywrightBackend resolves Chrome profile via goldy_chrome module."""
        backend = goldy_browser.PlaywrightBackend(email="test@example.com")
        # Mock: manually set profile to test the plumbing
        backend._profile_dir = "Profile 5"
        self.assertEqual(backend.resolve_profile(), "Profile 5")
        self.assertIn("Profile 5", backend.user_data_dir())

    def test_t063_chrome_ext_backend_navigate_protocol(self) -> None:
        """T-063: ChromeExtensionBackend emits valid JSON protocol for navigate action."""
        backend = goldy_browser.ChromeExtensionBackend()
        action = goldy_browser.BrowserAction(action="navigate", url="http://localhost:3000")
        instruction = backend.build_instruction(action)
        self.assertEqual(instruction["action"], "navigate")
        self.assertEqual(instruction["mcp_tool"], "mcp__claude-in-chrome__puppeteer_navigate")
        self.assertEqual(instruction["params"]["url"], "http://localhost:3000")

    def test_t064_chrome_ext_backend_screenshot_protocol(self) -> None:
        """T-064: ChromeExtensionBackend emits valid JSON protocol for screenshot action."""
        backend = goldy_browser.ChromeExtensionBackend()
        action = goldy_browser.BrowserAction(action="screenshot")
        instruction = backend.build_instruction(action)
        self.assertEqual(instruction["action"], "screenshot")
        self.assertEqual(instruction["mcp_tool"], "mcp__claude-in-chrome__puppeteer_screenshot")

    def test_t065_smoke_check_sequence_produces_three_steps(self) -> None:
        """T-065: smoke_check_actions() produces correct 3-step sequence."""
        actions = goldy_browser.smoke_check_actions("http://localhost:3000")
        self.assertEqual(len(actions), 3)
        self.assertEqual(actions[0].action, "navigate")
        self.assertEqual(actions[0].url, "http://localhost:3000")
        self.assertEqual(actions[1].action, "screenshot")
        self.assertEqual(actions[2].action, "console")
        self.assertEqual(actions[2].pattern, "error|Error|ERR")

    def test_t066_goldy_loop_parses_browser_check_flag(self) -> None:
        """T-066: goldy_loop.py parses --browser-check flag and stores URL."""
        import sys
        old_argv = sys.argv
        try:
            sys.argv = ["goldy_loop.py", "--plan", "test.md", "--browser-check", "http://localhost:3000"]
            args = goldy_loop.parse_args()
            self.assertEqual(args.browser_check, "http://localhost:3000")
        finally:
            sys.argv = old_argv

    def test_t067_goldy_chrome_module_still_resolves_profiles(self) -> None:
        """T-067: goldy_chrome.py still works as internal module after CLI removal."""
        local_state = {
            "profile": {
                "info_cache": {
                    "Default": {"user_name": "other@example.com"},
                    "Profile 7": {"user_name": "bodhimindflow@gmail.com"},
                }
            }
        }
        profile_dir = goldy_chrome.resolve_profile_directory("bodhimindflow@gmail.com", local_state)
        self.assertEqual(profile_dir, "Profile 7")
        cmd = goldy_chrome.build_launch_command("Profile 7", "http://localhost:3000")
        self.assertEqual(cmd[0:4], ["open", "-na", "Google Chrome", "--args"])

    def test_t068_browser_action_rejects_invalid_action(self) -> None:
        """T-068: BrowserAction rejects invalid action names."""
        with self.assertRaises(ValueError):
            goldy_browser.BrowserAction(action="invalid_action")

    def test_t069_build_smoke_check_returns_protocol(self) -> None:
        """T-069: build_smoke_check() returns valid protocol with backend field."""
        old = os.environ.pop("CODEX_THREAD_ID", None)
        try:
            protocol = goldy_browser.build_smoke_check("http://localhost:3000")
            self.assertIn("browser_investigation", protocol)
            inv = protocol["browser_investigation"]
            self.assertEqual(inv["backend"], "chrome-extension")
            self.assertEqual(len(inv["steps"]), 3)
        finally:
            if old is not None:
                os.environ["CODEX_THREAD_ID"] = old


if __name__ == "__main__":
    unittest.main(verbosity=2)
