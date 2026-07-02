"""
tests/test_team_spawn_residency_hook.py

Unit + subprocess tests for U1 (issue #289):
  plugins/saga/hooks/team_spawn_residency_hook.py

Contract under test:
  1. load_trigger_set parses reviewer-registry.md + validator-registry.md into the
     18-agent team-execution reviewer/tester trigger set (R3, R4, KTD4) and degrades
     to an empty set when a registry file is missing/unreadable (R10).
  2. _find_references_dir resolves the registries' directory across the four KTD3
     layouts (dev-repo sibling, versioned-cache via installed_plugins.json with
     max-semver-glob fallback, CLAUDE_PROJECT_DIR, bounded cwd-ancestor scan).
  3. decide() is a pure predicate: warns iff a normalized subagent_type is in the
     (env-adjusted) trigger set AND name is missing/empty/non-string (KTD1, KTD2,
     KTD5, R2, R5, R7).
  4. main() is silent on malformed envelopes, non-team tool_name, and named/
     out-of-set spawns; emits one PreToolUse additionalContext line and always
     exits 0 (R6, R8, R9).
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).parent.parent
HOOK_PATH = REPO_ROOT / "plugins" / "saga" / "hooks" / "team_spawn_residency_hook.py"
REAL_REFERENCES_DIR = (
    REPO_ROOT / "plugins" / "team-execution" / "skills" / "team-execution" / "references"
)

EXCLUDED_AGENTS = {
    "security-scanner",
    "iac-cost-scanner",
    "api-compat-scanner",
    "dependency-scanner",
    "github-actions-monitor",
    "runtime-monitor",
    "deploy-watcher",
}


def _load_hook_module() -> Any:
    spec = importlib.util.spec_from_file_location("team_spawn_residency_hook", HOOK_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


@pytest.fixture
def hook() -> Any:
    return _load_hook_module()


# ---------------------------------------------------------------------------
# load_trigger_set — registry parsing (R3, R4, R10, KTD4)
# ---------------------------------------------------------------------------


class TestLoadTriggerSet:
    def test_real_registries_yield_exactly_18_reviewers_and_testers(self, hook: Any) -> None:
        trigger_set = hook.load_trigger_set(REAL_REFERENCES_DIR)
        assert len(trigger_set) == 18
        assert not (trigger_set & EXCLUDED_AGENTS), (
            f"trigger set leaked excluded agents: {trigger_set & EXCLUDED_AGENTS}"
        )

    def test_no_template_artifact_from_adding_a_new_reviewer_section(self, hook: Any) -> None:
        trigger_set = hook.load_trigger_set(REAL_REFERENCES_DIR)
        assert "name-reviewer" not in trigger_set
        assert not any("<" in name or ">" in name for name in trigger_set)

    def test_missing_directory_yields_empty_set(self, hook: Any, tmp_path: Path) -> None:
        trigger_set = hook.load_trigger_set(tmp_path / "does-not-exist")
        assert trigger_set == frozenset()

    def test_unreadable_registry_contributes_nothing(self, hook: Any, tmp_path: Path) -> None:
        (tmp_path / "reviewer-registry.md").write_text("| `only-reviewer` | x | y |\n")
        # validator-registry.md deliberately absent.
        trigger_set = hook.load_trigger_set(tmp_path)
        assert trigger_set == frozenset({"only-reviewer"})

    def test_agent_file_column_does_not_leak_into_reviewer_set(
        self, hook: Any, tmp_path: Path
    ) -> None:
        (tmp_path / "reviewer-registry.md").write_text(
            "| Keywords | Suggested Reviewer | Agent File |\n"
            "|---|---|---|\n"
            "| foo | `infra-reviewer` | `agents/infra-reviewer.md` |\n"
        )
        (tmp_path / "validator-registry.md").write_text("")
        trigger_set = hook.load_trigger_set(tmp_path)
        assert trigger_set == frozenset({"infra-reviewer"})

    def test_tester_names_scoped_to_testers_section_only(self, hook: Any, tmp_path: Path) -> None:
        (tmp_path / "reviewer-registry.md").write_text("")
        (tmp_path / "validator-registry.md").write_text(
            "## Scanners\n\n"
            "| Agent | Select When |\n|---|---|\n"
            "| `security-scanner` | always |\n\n"
            "## Testers\n\n"
            "| Agent | Select When |\n|---|---|\n"
            "| `smoke-tester` | always |\n\n"
            "## Monitors\n\n"
            "| Agent | Select When |\n|---|---|\n"
            "| `runtime-monitor` | always |\n"
        )
        trigger_set = hook.load_trigger_set(tmp_path)
        assert trigger_set == frozenset({"smoke-tester"})


# ---------------------------------------------------------------------------
# _find_references_dir — KTD3 four-step resolution chain
# ---------------------------------------------------------------------------


def _make_references(root: Path) -> Path:
    refs = root / "skills" / "team-execution" / "references"
    refs.mkdir(parents=True)
    return refs


class TestFindReferencesDir:
    def test_dev_repo_sibling_layout_resolves(
        self, hook: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plugins_dir = tmp_path / "plugins"
        saga_root = plugins_dir / "saga"
        saga_root.mkdir(parents=True)
        expected = _make_references(plugins_dir / "team-execution")

        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(saga_root))
        monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)

        assert hook._find_references_dir(None) == expected

    def test_versioned_cache_layout_prefers_installed_plugins_json_over_max_semver(
        self, hook: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cache_root = tmp_path / "plugins" / "cache" / "infiquetra-plugins"
        saga_root = cache_root / "saga" / "0.46.0"
        saga_root.mkdir(parents=True)

        old_refs = _make_references(cache_root / "team-execution" / "2.4.0")
        _make_references(cache_root / "team-execution" / "2.6.0")

        (tmp_path / "plugins" / "installed_plugins.json").write_text(
            json.dumps(
                {
                    "plugins": {
                        "team-execution@infiquetra-plugins": [
                            {"installPath": str(cache_root / "team-execution" / "2.4.0")}
                        ]
                    }
                }
            )
        )

        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(saga_root))
        monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)

        assert hook._find_references_dir(None) == old_refs

    def test_versioned_cache_layout_falls_back_to_max_semver_when_registry_absent(
        self, hook: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cache_root = tmp_path / "plugins" / "cache" / "infiquetra-plugins"
        saga_root = cache_root / "saga" / "0.46.0"
        saga_root.mkdir(parents=True)

        _make_references(cache_root / "team-execution" / "2.4.0")
        newest_refs = _make_references(cache_root / "team-execution" / "2.6.0")
        # installed_plugins.json deliberately not written — absent registry.

        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(saga_root))
        monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)

        assert hook._find_references_dir(None) == newest_refs

    def test_versioned_cache_layout_falls_back_on_malformed_registry(
        self, hook: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cache_root = tmp_path / "plugins" / "cache" / "infiquetra-plugins"
        saga_root = cache_root / "saga" / "0.46.0"
        saga_root.mkdir(parents=True)
        newest_refs = _make_references(cache_root / "team-execution" / "2.6.0")
        (tmp_path / "plugins" / "installed_plugins.json").write_text("not json")

        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(saga_root))
        monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)

        assert hook._find_references_dir(None) == newest_refs

    def test_versioned_cache_layout_falls_back_on_missing_key(
        self, hook: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cache_root = tmp_path / "plugins" / "cache" / "infiquetra-plugins"
        saga_root = cache_root / "saga" / "0.46.0"
        saga_root.mkdir(parents=True)
        newest_refs = _make_references(cache_root / "team-execution" / "2.6.0")
        (tmp_path / "plugins" / "installed_plugins.json").write_text(
            json.dumps({"plugins": {"saga@infiquetra-plugins": [{"installPath": str(saga_root)}]}})
        )

        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(saga_root))
        monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)

        assert hook._find_references_dir(None) == newest_refs

    def test_claude_project_dir_layout_resolves(
        self, hook: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        expected = _make_references(tmp_path / "project" / "plugins" / "team-execution")

        monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path / "project"))

        assert hook._find_references_dir(None) == expected

    def test_bare_cwd_ancestor_scan_resolves(
        self, hook: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        expected = _make_references(tmp_path / "repo" / "plugins" / "team-execution")
        nested_cwd = tmp_path / "repo" / "some" / "nested" / "dir"
        nested_cwd.mkdir(parents=True)

        monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
        monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)

        assert hook._find_references_dir(str(nested_cwd)) == expected

    def test_nothing_present_returns_none(
        self, hook: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
        monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
        empty_cwd = tmp_path / "nowhere"
        empty_cwd.mkdir()

        assert hook._find_references_dir(str(empty_cwd)) is None


# ---------------------------------------------------------------------------
# decide() — pure predicate (KTD1, KTD2, KTD5, R2, R5, R7, R8)
# ---------------------------------------------------------------------------


class TestDecide:
    TRIGGER_SET = frozenset({"security-reviewer", "smoke-tester"})

    def test_nameless_trigger_agent_warns_naming_agent_and_fix(self, hook: Any) -> None:
        advisory = hook.decide({"subagent_type": "security-reviewer"}, self.TRIGGER_SET)
        assert advisory is not None
        assert "security-reviewer" in advisory
        assert "name" in advisory
        assert "SendMessage" in advisory

    def test_prefixed_nameless_trigger_agent_warns(self, hook: Any) -> None:
        advisory = hook.decide(
            {"subagent_type": "team-execution:security-reviewer"}, self.TRIGGER_SET
        )
        assert advisory is not None
        assert "team-execution:security-reviewer" in advisory

    def test_named_trigger_agent_is_silent(self, hook: Any) -> None:
        assert (
            hook.decide(
                {"subagent_type": "team-execution:security-reviewer", "name": "sec-1"},
                self.TRIGGER_SET,
            )
            is None
        )

    @pytest.mark.parametrize("bad_name", ["", None, 123, []])
    def test_empty_or_non_string_name_still_warns(self, hook: Any, bad_name: Any) -> None:
        advisory = hook.decide(
            {"subagent_type": "security-reviewer", "name": bad_name}, self.TRIGGER_SET
        )
        assert advisory is not None

    @pytest.mark.parametrize("run_in_background", [True, False])
    def test_run_in_background_never_consulted(self, hook: Any, run_in_background: bool) -> None:
        advisory = hook.decide(
            {"subagent_type": "security-reviewer", "run_in_background": run_in_background},
            self.TRIGGER_SET,
        )
        assert advisory is not None  # still warns — no `name`, regardless of this field

    @pytest.mark.parametrize(
        "subagent_type",
        [
            "general-purpose",
            "saga:mechanical-executor",
            "security-scanner",
            "github-actions-monitor",
            "deploy-watcher",
        ],
    )
    def test_out_of_set_agents_are_silent(self, hook: Any, subagent_type: str) -> None:
        assert hook.decide({"subagent_type": subagent_type}, self.TRIGGER_SET) is None

    def test_empty_trigger_set_is_always_silent(self, hook: Any) -> None:
        assert hook.decide({"subagent_type": "security-reviewer"}, frozenset()) is None

    def test_missing_subagent_type_is_silent(self, hook: Any) -> None:
        assert hook.decide({}, self.TRIGGER_SET) is None

    def test_include_env_extends_trigger_set(
        self, hook: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TEAM_SPAWN_GUARD_INCLUDE", "worker-x")
        monkeypatch.delenv("TEAM_SPAWN_GUARD_EXCLUDE", raising=False)
        assert hook.decide({"subagent_type": "worker-x"}, self.TRIGGER_SET) is not None

    def test_exclude_env_shrinks_trigger_set(
        self, hook: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TEAM_SPAWN_GUARD_EXCLUDE", "security-reviewer")
        monkeypatch.delenv("TEAM_SPAWN_GUARD_INCLUDE", raising=False)
        assert hook.decide({"subagent_type": "security-reviewer"}, self.TRIGGER_SET) is None


# ---------------------------------------------------------------------------
# main() — envelope shim (R6, R8, R9)
# ---------------------------------------------------------------------------


class TestMainEnvelopeShim:
    def test_malformed_envelope_exits_0_silently(
        self, hook: Any, capsys: pytest.CaptureFixture
    ) -> None:
        with patch.object(sys, "stdin") as mock_stdin:
            mock_stdin.read.return_value = "not json"
            with pytest.raises(SystemExit) as exc_info:
                hook.main()
        assert exc_info.value.code == 0
        assert capsys.readouterr().out == ""

    def test_non_team_tool_name_exits_0_silently(
        self, hook: Any, capsys: pytest.CaptureFixture
    ) -> None:
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls"}})
        with patch.object(sys, "stdin") as mock_stdin:
            mock_stdin.read.return_value = payload
            with pytest.raises(SystemExit) as exc_info:
                hook.main()
        assert exc_info.value.code == 0
        assert capsys.readouterr().out == ""


# ---------------------------------------------------------------------------
# Subprocess-level — the plan's manual acceptance checks, run as real tests
# ---------------------------------------------------------------------------


class TestSubprocessInvocation:
    def _run(self, stdin_text: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input=stdin_text,
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            timeout=10,
        )

    def test_malformed_stdin_no_output_exit_0(self) -> None:
        result = self._run("not json")
        assert result.returncode == 0
        assert result.stdout == ""

    def test_nameless_team_family_envelope_emits_advisory_json(self) -> None:
        payload = json.dumps(
            {
                "tool_name": "Agent",
                "tool_input": {"subagent_type": "team-execution:security-reviewer"},
                "cwd": str(REPO_ROOT),
            }
        )
        result = self._run(payload)
        assert result.returncode == 0
        out = json.loads(result.stdout)
        assert out["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
        assert "team-execution:security-reviewer" in out["hookSpecificOutput"]["additionalContext"]

    def test_named_spawn_via_stock_task_tool_is_silent(self) -> None:
        payload = json.dumps(
            {
                "tool_name": "Task",
                "tool_input": {"subagent_type": "security-reviewer", "name": "sec-1"},
                "cwd": str(REPO_ROOT),
            }
        )
        result = self._run(payload)
        assert result.returncode == 0
        assert result.stdout == ""

    def test_bash_tool_name_silent_exit_0(self) -> None:
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls"}})
        result = self._run(payload)
        assert result.returncode == 0
        assert result.stdout == ""
