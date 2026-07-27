"""
tests/test_pre_push_gate.py

Unit tests for U9 (R15, KTD10):
  - tools/gate-manifest.json  — single-source declarative gate definition
  - plugins/saga/hooks/pre_push_gate_hook.py — the hook runner

Contract under test:
  1. The manifest exists, is valid JSON, and lists the 6 expected gate steps.
  2. The manifest is the single source of truth: the hook reads it at runtime.
  3. The hook is silent on an all-green tree (report by exception).
  4. The hook reports failures and exits 2 (blocking) when any step fails.
  5. The hook ignores non-push Bash commands.
  6. The hook degrades silently when the manifest is absent.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent
MANIFEST_PATH = REPO_ROOT / "tools" / "gate-manifest.json"
HOOK_PATH = REPO_ROOT / "plugins" / "saga" / "hooks" / "pre_push_gate_hook.py"

# ---------------------------------------------------------------------------
# Helpers — load the hook module without installing it
# ---------------------------------------------------------------------------


def _load_hook_module() -> Any:
    """Dynamically import the hook script as a module."""
    spec = importlib.util.spec_from_file_location("pre_push_gate_hook", HOOK_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ---------------------------------------------------------------------------
# Manifest tests
# ---------------------------------------------------------------------------


class TestGateManifest:
    """Verify the declarative gate manifest is well-formed and complete."""

    def test_manifest_exists(self) -> None:
        assert MANIFEST_PATH.exists(), f"gate manifest not found: {MANIFEST_PATH}"

    def test_manifest_is_valid_json(self) -> None:
        text = MANIFEST_PATH.read_text(encoding="utf-8")
        data = json.loads(text)  # raises on invalid JSON
        assert isinstance(data, dict)

    def test_manifest_has_steps(self) -> None:
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        steps = data.get("steps")
        assert isinstance(steps, list) and len(steps) > 0, "manifest must have at least one step"

    def test_manifest_step_ids_are_unique(self) -> None:
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        ids = [s.get("id") for s in data["steps"]]
        assert len(ids) == len(set(ids)), f"duplicate step IDs: {ids}"

    def test_manifest_contains_required_gate_steps(self) -> None:
        """
        The manifest must list all 6 CI gate steps (per R15 + spec §U9; mypy added #314):
          ruff format --check, ruff check, mypy, validate_plugins, validate marketplace, pytest
        """
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        step_ids = {s.get("id") for s in data["steps"]}
        required = {
            "ruff-format",
            "ruff-lint",
            "mypy",
            "validate-plugins",
            "validate-marketplace",
            "pytest",
        }
        missing = required - step_ids
        assert not missing, f"gate manifest is missing required steps: {missing}"

    def test_every_step_has_command(self) -> None:
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        for step in data["steps"]:
            assert step.get("command"), f"step {step.get('id')!r} has no command"

    def test_every_step_has_label(self) -> None:
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        for step in data["steps"]:
            assert step.get("label"), f"step {step.get('id')!r} has no label"

    def test_every_step_has_failure_hint(self) -> None:
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        for step in data["steps"]:
            assert step.get("failure_hint"), f"step {step.get('id')!r} has no failure_hint"


# ---------------------------------------------------------------------------
# Hook module unit tests
# ---------------------------------------------------------------------------


def _make_payload(command: str, tool_name: str = "Bash") -> str:
    """Return a JSON hook envelope string for the given tool invocation."""
    return json.dumps({"tool_name": tool_name, "tool_input": {"command": command}})


class TestPrePushGateHookDetection:
    """Verify command detection helpers."""

    @pytest.fixture
    def hook(self) -> Any:
        return _load_hook_module()

    def test_git_push_is_detected(self, hook: Any) -> None:
        assert hook._push_target("git push origin main")[0]
        assert hook._push_target("git -C /some/path push --force-with-lease")[0]
        assert hook._push_target("git push")[0]
        # Compound: a real push anywhere in the command still gates.
        assert hook._push_target("git add -A ; git push")[0]
        # Global flags before the subcommand must not hide it.
        assert hook._push_target("git --no-pager -c user.name=x push")[0]

    def test_non_push_is_not_detected(self, hook: Any) -> None:
        assert not hook._push_target("git commit -m 'fix: something'")[0]
        assert not hook._push_target("git pull origin main")[0]
        assert not hook._push_target("echo 'git push'")[0]

    def test_argument_text_containing_push_does_not_gate(self, hook: Any) -> None:
        """#663 fault (b): the old regex matched the WORD push anywhere in the argument span.

        Each of these ran the full ~5500-test suite on a read-only git command, and under CPU
        contention could hit the gate's own step timeout -- turning a `git log` into a hard
        failure. A token list distinguishes a subcommand from an argument.
        """
        for command in (
            "git add docs/push-notes.md",
            "git log --oneline --grep=push",
            "git show HEAD:docs/how-to-push.md",
            "git commit -m 'document the git push gate'",
            "git checkout -b feature/push-gate-fix",
        ):
            assert not hook._push_target(command)[0], f"must not gate: {command}"

    def test_repo_is_resolved_from_the_invocation(self, hook: Any) -> None:
        """#663 fault (a): resolve the target repo from the invocation, not the session cwd."""
        assert hook._push_target("git -C /tmp/repo push")[1] == "/tmp/repo"
        assert hook._push_target("git --git-dir=/tmp/r/.git push")[1] == "/tmp/r/.git"
        assert hook._push_target("git --work-tree /tmp/wt push")[1] == "/tmp/wt"
        assert hook._push_target("git push origin main")[1] is None

    def test_cd_prefix_targets_the_other_repo(self, hook: Any) -> None:
        """The live failure: `cd <other-repo>` then push ran THIS repo's suite and blocked it."""
        assert hook._cd_target("cd /tmp/other-repo ; git push") == "/tmp/other-repo"
        assert hook._cd_target("git push origin main") is None

    def test_unparseable_command_does_not_gate(self, hook: Any) -> None:
        """Unbalanced quotes yield no segments -- degrade to not gating, never guess."""
        assert not hook._push_target("git push 'unterminated")[0]


class TestPrePushGateHookExitBehavior:
    """Verify that the hook exits correctly based on push detection and step results."""

    @pytest.fixture
    def hook(self) -> Any:
        return _load_hook_module()

    def test_non_bash_tool_exits_0(self, hook: Any) -> None:
        """Non-Bash tools must pass through silently."""
        payload = json.dumps({"tool_name": "Edit", "tool_input": {"file_path": "foo.py"}})
        with patch.object(sys, "stdin") as mock_stdin:
            mock_stdin.read.return_value = payload
            with pytest.raises(SystemExit) as exc_info:
                hook.main()
        assert exc_info.value.code == 0

    def test_non_push_bash_command_exits_0(self, hook: Any) -> None:
        """A Bash git commit must not trigger the gate."""
        payload = _make_payload("git commit -m 'fix: oops'")
        with patch.object(sys, "stdin") as mock_stdin:
            mock_stdin.read.return_value = payload
            with pytest.raises(SystemExit) as exc_info:
                hook.main()
        assert exc_info.value.code == 0

    def test_malformed_payload_exits_0(self, hook: Any) -> None:
        """Malformed JSON envelope must degrade silently."""
        with patch.object(sys, "stdin") as mock_stdin:
            mock_stdin.read.return_value = "not-json"
            with pytest.raises(SystemExit) as exc_info:
                hook.main()
        assert exc_info.value.code == 0

    def test_missing_manifest_exits_0(self, hook: Any, tmp_path: Path) -> None:
        """When the manifest is absent the hook must degrade silently."""
        payload = _make_payload("git push origin main")

        # Point the hook at a tmp repo root that has no manifest.
        with (
            patch.object(sys, "stdin") as mock_stdin,
            patch.object(hook, "_find_repo_root", return_value=tmp_path),
        ):
            mock_stdin.read.return_value = payload
            with pytest.raises(SystemExit) as exc_info:
                hook.main()
        assert exc_info.value.code == 0

    def test_all_steps_pass_exits_0_silently(self, hook: Any, tmp_path: Path) -> None:
        """A clean tree must exit 0 with no output (report by exception)."""
        # Build a minimal manifest with one always-passing step.
        manifest = {
            "steps": [
                {
                    "id": "always-pass",
                    "label": "always pass",
                    "command": [sys.executable, "-c", ""],
                    "failure_hint": "n/a",
                }
            ]
        }
        (tmp_path / "tools").mkdir()
        (tmp_path / "tools" / "gate-manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        payload = _make_payload("git push origin main")

        with (
            patch.object(sys, "stdin") as mock_stdin,
            patch.object(hook, "_find_repo_root", return_value=tmp_path),
        ):
            mock_stdin.read.return_value = payload
            with pytest.raises(SystemExit) as exc_info:
                hook.main()
        assert exc_info.value.code == 0

    def test_failing_step_exits_2_and_reports(
        self, hook: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A seeded failure must exit 2 and print the failure to stderr."""
        manifest = {
            "steps": [
                {
                    "id": "always-fail",
                    "label": "always fail",
                    "command": [sys.executable, "-c", "import sys; sys.exit(1)"],
                    "failure_hint": "Fix the thing.",
                }
            ]
        }
        (tmp_path / "tools").mkdir()
        (tmp_path / "tools" / "gate-manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        payload = _make_payload("git push origin main")

        with (
            patch.object(sys, "stdin") as mock_stdin,
            patch.object(hook, "_find_repo_root", return_value=tmp_path),
        ):
            mock_stdin.read.return_value = payload
            with pytest.raises(SystemExit) as exc_info:
                hook.main()

        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "always fail" in captured.err
        assert "Fix the thing." in captured.err
        assert "blocked" in captured.err

    def test_multiple_failures_all_reported(
        self, hook: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """All failing steps must be reported, not just the first."""
        manifest = {
            "steps": [
                {
                    "id": "fail-a",
                    "label": "step A",
                    "command": [sys.executable, "-c", "import sys; sys.exit(1)"],
                    "failure_hint": "Hint A",
                },
                {
                    "id": "pass-b",
                    "label": "step B",
                    "command": [sys.executable, "-c", ""],
                    "failure_hint": "Hint B",
                },
                {
                    "id": "fail-c",
                    "label": "step C",
                    "command": [sys.executable, "-c", "import sys; sys.exit(1)"],
                    "failure_hint": "Hint C",
                },
            ]
        }
        (tmp_path / "tools").mkdir()
        (tmp_path / "tools" / "gate-manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        payload = _make_payload("git push origin main")

        with (
            patch.object(sys, "stdin") as mock_stdin,
            patch.object(hook, "_find_repo_root", return_value=tmp_path),
        ):
            mock_stdin.read.return_value = payload
            with pytest.raises(SystemExit) as exc_info:
                hook.main()

        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        # Both failures must be named; the passing step must not appear.
        assert "step A" in captured.err
        assert "step C" in captured.err
        assert "Hint A" in captured.err
        assert "Hint C" in captured.err

    def test_failing_step_output_is_included(
        self, hook: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The step's stdout/stderr must be echoed in the failure report."""
        manifest = {
            "steps": [
                {
                    "id": "loud-fail",
                    "label": "loud fail",
                    "command": [
                        sys.executable,
                        "-c",
                        "import sys; print('UNIQUE_OUTPUT_TOKEN'); sys.exit(1)",
                    ],
                    "failure_hint": "Fix loudly.",
                }
            ]
        }
        (tmp_path / "tools").mkdir()
        (tmp_path / "tools" / "gate-manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        payload = _make_payload("git push origin main")

        with (
            patch.object(sys, "stdin") as mock_stdin,
            patch.object(hook, "_find_repo_root", return_value=tmp_path),
        ):
            mock_stdin.read.return_value = payload
            with pytest.raises(SystemExit) as exc_info:
                hook.main()

        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "UNIQUE_OUTPUT_TOKEN" in captured.err


# ---------------------------------------------------------------------------
# Integration smoke: manifest drives the actual gate commands
# ---------------------------------------------------------------------------


class TestManifestDrivesHook:
    """
    Verify that the manifest's command list, not a hard-coded list inside the
    hook, is what the hook executes.  This is the single-source property (R15).
    """

    def test_hook_reads_manifest_not_hardcoded_commands(self, tmp_path: Path) -> None:
        """
        Place a manifest with a canary step command.  Verify the hook invokes
        that command (not a hard-coded list).  We monkey-patch _run_step to
        capture which steps were executed.
        """
        hook = _load_hook_module()

        canary_id = "canary-step-12345"
        manifest = {
            "steps": [
                {
                    "id": canary_id,
                    "label": "canary",
                    "command": [sys.executable, "-c", ""],
                    "failure_hint": "n/a",
                }
            ]
        }
        (tmp_path / "tools").mkdir()
        (tmp_path / "tools" / "gate-manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        payload = _make_payload("git push origin main")

        executed_step_ids: list[str] = []
        original_run_step = hook._run_step

        def capturing_run_step(step: dict, cwd: Path) -> tuple[bool, str]:
            executed_step_ids.append(step.get("id", ""))
            result: tuple[bool, str] = original_run_step(step, cwd)
            return result

        with (
            patch.object(sys, "stdin") as mock_stdin,
            patch.object(hook, "_find_repo_root", return_value=tmp_path),
            patch.object(hook, "_run_step", side_effect=capturing_run_step),
        ):
            mock_stdin.read.return_value = payload
            with pytest.raises(SystemExit):
                hook.main()

        assert canary_id in executed_step_ids, (
            f"hook did not execute the manifest-defined step {canary_id!r}; "
            f"executed: {executed_step_ids}"
        )


# ---------------------------------------------------------------------------
# Per-step timeout (issue #658)
# ---------------------------------------------------------------------------


class TestPerStepTimeout:
    """The step budget lives in the manifest, not in the hook.

    It was hardcoded at 300 s, which broke the hook's own SINGLE SOURCE property and
    failed in the worst direction: the suite grew past the budget while still passing,
    so the gate blocked every push in the repo reporting a timeout that reads exactly
    like a real red at the call site.
    """

    @pytest.fixture
    def hook(self) -> Any:
        return _load_hook_module()

    def test_step_without_a_declared_timeout_keeps_the_historical_default(
        self, hook: Any, tmp_path: Path
    ) -> None:
        captured: dict[str, Any] = {}

        def fake_run(cmd: list[str], **kwargs: Any) -> Any:
            captured.update(kwargs)
            return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        with patch.object(hook.subprocess, "run", side_effect=fake_run):
            passed, _ = hook._run_step({"id": "x", "command": ["true"]}, tmp_path)

        assert passed
        assert captured["timeout"] == hook._DEFAULT_STEP_TIMEOUT == 300

    def test_step_may_declare_its_own_timeout(self, hook: Any, tmp_path: Path) -> None:
        captured: dict[str, Any] = {}

        def fake_run(cmd: list[str], **kwargs: Any) -> Any:
            captured.update(kwargs)
            return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        with patch.object(hook.subprocess, "run", side_effect=fake_run):
            hook._run_step({"id": "x", "command": ["true"], "timeout_seconds": 600}, tmp_path)

        assert captured["timeout"] == 600

    def test_timeout_message_reports_the_budget_that_was_actually_applied(
        self, hook: Any, tmp_path: Path
    ) -> None:
        """A message hardcoding "300 s" while a step ran on a different budget sends the
        operator to check the wrong number."""

        def boom(cmd: list[str], **kwargs: Any) -> Any:
            raise hook.subprocess.TimeoutExpired(cmd, kwargs.get("timeout"))

        with patch.object(hook.subprocess, "run", side_effect=boom):
            passed, message = hook._run_step(
                {"id": "x", "command": ["true"], "timeout_seconds": 600}, tmp_path
            )

        assert not passed
        assert "600" in message

    def test_the_real_pytest_step_declares_a_budget_above_the_default(self) -> None:
        """The suite measured 325 s green on an idle machine against the 300 s default,
        so the real manifest must carry its own budget or the gate blocks every push."""
        steps = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["steps"]
        pytest_step = next(s for s in steps if s["id"] == "pytest")
        assert pytest_step["timeout_seconds"] > 300
