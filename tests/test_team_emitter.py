"""Oracle tests for the team-execution markdown emitter (U11, R9 second emitter).

Spec says: ``tests/test_team_emitter.py`` (new) — the same spec [as U10] yields valid
Team Structure markdown, matching the parsed structure of workers / reviewers /
validators / gates from ``team-execution/SKILL.md:234``.

The load-bearing oracles here are:
* The ``## Team Structure`` heading and all four sub-section headings must be present.
* Each spec unit generates a worker row (parsed-structure match for the template).
* The base reviewer set (devils-advocate-reviewer, security-reviewer,
  architecture-reviewer) is always present.
* The base validator set (security-scanner) is always present.
* The standard execution gates are always present.
* The ``orchestration_ref`` semantic: the emitter returns a string the caller writes +
  passes to ``saga.py save --orchestration-ref``; the emitter never writes the file
  itself (pure function) — asserted by calling it without touching the filesystem.
* ``never vendor team-execution machinery`` (R9): the emitter imports nothing from the
  team-execution plugin directory.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parent.parent
EXECUTION_SPEC_SCRIPT = ROOT / "plugins" / "saga" / "scripts" / "execution_spec.py"
TEAM_EMITTER_SCRIPT = ROOT / "plugins" / "saga" / "scripts" / "team_emitter.py"


def _load_execution_spec() -> ModuleType:
    """Load execution_spec.py as a module (same pattern as test_workflow_emitter.py)."""
    spec = importlib.util.spec_from_file_location("execution_spec", EXECUTION_SPEC_SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["execution_spec"] = module
    spec.loader.exec_module(module)
    return module


def _load_team_emitter() -> ModuleType:
    """Load team_emitter.py as a module."""
    spec = importlib.util.spec_from_file_location("team_emitter", TEAM_EMITTER_SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["team_emitter"] = module
    spec.loader.exec_module(module)
    return module


def _valid_spec_dict() -> dict[str, object]:
    """A minimal valid spec with varied tiers — the same shape as test_workflow_emitter.py."""
    return {
        "name": "demo-campaign",
        "description": "a demo execution spec",
        "repo": "/tmp/repo",
        "units": [
            {
                "unit_id": "U1",
                "label": "preflight",
                "tier": {"model": "haiku", "effort": "low"},
                "prompt": "verify grounding facts on origin/main",
                "returns": ["ready", "drift"],
                "escalation": "HALT on drift",
            },
            {
                "unit_id": "U2",
                "label": "build",
                "tier": {"model": "sonnet", "effort": "high"},
                "prompt": "implement the unit",
                "depends_on": ["U1"],
                "returns": ["done", "files"],
            },
            {
                "unit_id": "U3",
                "label": "judge",
                "tier": {"model": "opus", "effort": "high"},
                "prompt": "review the diff",
                "depends_on": ["U2"],
            },
        ],
    }


# ---------------------------------------------------------------------------
# Happy path: a valid spec yields valid Team Structure markdown.
# ---------------------------------------------------------------------------


def test_emit_team_structure_returns_string() -> None:
    """emit_team_structure returns a non-empty string (pure function, no I/O)."""
    es_mod = _load_execution_spec()
    te_mod = _load_team_emitter()
    spec = es_mod.ExecutionSpec.from_dict(_valid_spec_dict())
    result = te_mod.emit_team_structure(spec)
    assert isinstance(result, str)
    assert len(result) > 0


def test_top_level_heading_present() -> None:
    """The output must start with '## Team Structure' (matches SKILL.md:234)."""
    es_mod = _load_execution_spec()
    te_mod = _load_team_emitter()
    spec = es_mod.ExecutionSpec.from_dict(_valid_spec_dict())
    result = te_mod.emit_team_structure(spec)
    assert "## Team Structure" in result


def test_all_four_subsection_headings_present() -> None:
    """All four parsed-structure subsections must be present (SKILL.md template)."""
    es_mod = _load_execution_spec()
    te_mod = _load_team_emitter()
    spec = es_mod.ExecutionSpec.from_dict(_valid_spec_dict())
    result = te_mod.emit_team_structure(spec)
    assert "### Workers" in result
    assert "### Reviewers" in result
    assert "### Validators" in result
    assert "### Execution Gates" in result


def test_reference_files_section_present() -> None:
    """The Reference Files section must list the team-execution protocol references."""
    es_mod = _load_execution_spec()
    te_mod = _load_team_emitter()
    spec = es_mod.ExecutionSpec.from_dict(_valid_spec_dict())
    result = te_mod.emit_team_structure(spec)
    assert "### Reference Files" in result
    assert "reviewer-registry.md" in result
    assert "consensus-protocol.md" in result


def test_one_resident_row_per_segment() -> None:
    """The units collapse into one segment with resident_id 'worker'."""
    es_mod = _load_execution_spec()
    te_mod = _load_team_emitter()
    spec = es_mod.ExecutionSpec.from_dict(_valid_spec_dict())
    result = te_mod.emit_team_structure(spec)
    assert "`worker`" in result
    assert "U1, U2, U3" in result
    assert "`worker-1`" not in result
    assert "`worker-2`" not in result
    assert "`worker-3`" not in result


def test_two_plugin_spec_emits_two_resident_rows() -> None:
    """A spec with units under different plugin directories emits separate resident rows."""
    es_mod = _load_execution_spec()
    te_mod = _load_team_emitter()
    data = {
        "name": "two-plugins",
        "description": "spec targeting two plugins",
        "units": [
            {
                "unit_id": "U1",
                "label": "saga-unit",
                "tier": {"model": "haiku", "effort": "low"},
                "prompt": "do saga stuff",
                "files": ["plugins/saga/scripts/team_emitter.py"],
            },
            {
                "unit_id": "U2",
                "label": "te-unit",
                "tier": {"model": "sonnet", "effort": "high"},
                "prompt": "do team-execution stuff",
                "depends_on": ["U1"],
                "files": ["plugins/team-execution/skills/team-execution/SKILL.md"],
            },
        ],
    }
    spec = es_mod.ExecutionSpec.from_dict(data)
    result = te_mod.emit_team_structure(spec)
    assert "`worker-saga`" in result
    assert "`worker-team-execution`" in result


def test_worker_rows_carry_unit_ids() -> None:
    """Worker rows carry the covered unit IDs."""
    es_mod = _load_execution_spec()
    te_mod = _load_team_emitter()
    spec = es_mod.ExecutionSpec.from_dict(_valid_spec_dict())
    result = te_mod.emit_team_structure(spec)
    assert "U1" in result
    assert "U2" in result
    assert "U3" in result


def test_base_reviewers_always_present() -> None:
    """The three mandatory base reviewers are always present (SKILL.md template)."""
    es_mod = _load_execution_spec()
    te_mod = _load_team_emitter()
    spec = es_mod.ExecutionSpec.from_dict(_valid_spec_dict())
    result = te_mod.emit_team_structure(spec)
    assert "`devils-advocate-reviewer`" in result
    assert "`security-reviewer`" in result
    assert "`architecture-reviewer`" in result


def test_base_validator_present() -> None:
    """The base security-scanner validator is always present."""
    es_mod = _load_execution_spec()
    te_mod = _load_team_emitter()
    spec = es_mod.ExecutionSpec.from_dict(_valid_spec_dict())
    result = te_mod.emit_team_structure(spec)
    assert "`security-scanner`" in result


def test_execution_gates_present() -> None:
    """The standard consensus gate text is present in the Execution Gates section."""
    es_mod = _load_execution_spec()
    te_mod = _load_team_emitter()
    spec = es_mod.ExecutionSpec.from_dict(_valid_spec_dict())
    result = te_mod.emit_team_structure(spec)
    assert "9.0/10" in result
    assert "Reviewer non-consensus blocks validators" in result
    assert "Maximum 3 remediation loops" in result


# ---------------------------------------------------------------------------
# Governance comment: the emitter labels the choice (never vendors machinery).
# ---------------------------------------------------------------------------


def test_governance_comment_present() -> None:
    """The emitted markdown annotates the governance choice (team-execution / gated)."""
    es_mod = _load_execution_spec()
    te_mod = _load_team_emitter()
    spec = es_mod.ExecutionSpec.from_dict(_valid_spec_dict())
    result = te_mod.emit_team_structure(spec)
    # Must name team-execution as the governance choice and contrast with advisory.
    assert "team-execution" in result
    assert "gated consensus" in result


def test_spec_name_in_emitter_comment() -> None:
    """The spec name appears in the header comment for traceability."""
    es_mod = _load_execution_spec()
    te_mod = _load_team_emitter()
    spec = es_mod.ExecutionSpec.from_dict(_valid_spec_dict())
    result = te_mod.emit_team_structure(spec)
    assert "demo-campaign" in result


# ---------------------------------------------------------------------------
# orchestration_ref semantic: emitter is pure (no filesystem write).
# ---------------------------------------------------------------------------


def test_emitter_is_pure_no_filesystem_write(tmp_path: Path) -> None:
    """emit_team_structure does NOT write any files — it is a pure function.

    Saga records orchestration_ref via saga.py save --orchestration-ref; the emitter
    returns the string for the caller to write.  This test confirms no side effects.
    """
    es_mod = _load_execution_spec()
    te_mod = _load_team_emitter()
    spec = es_mod.ExecutionSpec.from_dict(_valid_spec_dict())

    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        before_files = set(tmp_path.iterdir())
        result = te_mod.emit_team_structure(spec)
        after_files = set(tmp_path.iterdir())
    finally:
        os.chdir(original_cwd)

    # No new files written by the emitter.
    assert after_files == before_files
    # But the result string is still valid.
    assert "## Team Structure" in result


# ---------------------------------------------------------------------------
# Single-unit spec: boundary condition.
# ---------------------------------------------------------------------------


def test_single_unit_spec_emits_one_worker_row() -> None:
    """A single-unit spec produces exactly one worker row."""
    es_mod = _load_execution_spec()
    te_mod = _load_team_emitter()
    data: dict[str, object] = {
        "name": "tiny",
        "description": "one-unit spec",
        "units": [
            {
                "unit_id": "U1",
                "label": "do it all",
                "tier": {"model": "sonnet", "effort": "high"},
                "prompt": "implement everything",
            }
        ],
    }
    spec = es_mod.ExecutionSpec.from_dict(data)
    result = te_mod.emit_team_structure(spec)
    assert "`worker`" in result
    assert "`worker-2`" not in result
    assert "U1" in result
    assert "sonnet/high" in result


def test_resident_rows_carry_tier_and_deps() -> None:
    """Resident worker rows carry their derived tiers and segment-level dependencies."""
    es_mod = _load_execution_spec()
    te_mod = _load_team_emitter()
    data = {
        "name": "two-plugins-deps",
        "description": "spec targeting two plugins with deps",
        "units": [
            {
                "unit_id": "U1",
                "label": "saga-unit",
                "tier": {"model": "haiku", "effort": "low"},
                "prompt": "do saga stuff",
                "files": ["plugins/saga/scripts/team_emitter.py"],
            },
            {
                "unit_id": "U2",
                "label": "te-unit",
                "tier": {"model": "opus", "effort": "high"},
                "prompt": "do team-execution stuff",
                "depends_on": ["U1"],
                "files": ["plugins/team-execution/skills/team-execution/SKILL.md"],
            },
        ],
    }
    spec = es_mod.ExecutionSpec.from_dict(data)
    result = te_mod.emit_team_structure(spec)
    assert "haiku/low" in result
    assert "opus/high" in result
    assert "worker-saga" in result


# ---------------------------------------------------------------------------
# CLI surface: emit to stdout and to a file.
# ---------------------------------------------------------------------------


def test_cli_emit_to_stdout(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """CLI with no -o flag prints the markdown to stdout."""
    te_mod = _load_team_emitter()
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(_valid_spec_dict()))
    rc = te_mod.main([str(spec_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "## Team Structure" in out


def test_cli_emit_writes_file(tmp_path: Path) -> None:
    """CLI with -o writes the markdown to the given path."""
    te_mod = _load_team_emitter()
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(_valid_spec_dict()))
    out_path = tmp_path / "team.md"
    rc = te_mod.main([str(spec_path), "-o", str(out_path)])
    assert rc == 0
    assert out_path.exists()
    content = out_path.read_text()
    assert "## Team Structure" in content
    assert "`worker`" in content


def test_cli_bad_spec_returns_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """CLI returns exit code 2 on a bad spec (e.g. missing units)."""
    te_mod = _load_team_emitter()
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps({"name": "bad", "description": "x", "units": []}))
    rc = te_mod.main([str(spec_path)])
    assert rc == 2
    assert "EMIT ERROR" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Never vendors team-execution machinery (R9).
# ---------------------------------------------------------------------------


def test_emitter_does_not_import_team_execution_plugin() -> None:
    """The emitter source must not import from the team-execution plugin directory.

    R9: saga records a pointer, never vendors backend machinery.  A static check
    on the source file is sufficient and offline-deterministic.
    """
    source = TEAM_EMITTER_SCRIPT.read_text()
    # No direct import of team-execution plugin modules (which live under
    # plugins/team-execution/). A reference to the SKILL.md template in a string
    # constant is fine; an `import` statement importing that plugin's code is not.
    forbidden = "from plugins.team_execution"
    assert forbidden not in source, (
        "team_emitter.py must not import team-execution plugin code (R9 -- never vendor machinery)"
    )
    forbidden2 = "import plugins.team_execution"
    assert forbidden2 not in source, (
        "team_emitter.py must not import team-execution plugin code (R9 -- never vendor machinery)"
    )
