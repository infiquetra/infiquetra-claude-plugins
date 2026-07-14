"""Tests for #422: one agent-file CI lint (frontmatter schema, role-class tier audit,
tool-scope floor).

Exercises ``tools/agent_spec.py``'s pluggable rule registry: a full-fleet sweep (every real
``plugins/*/agents/*.md`` file must carry zero *blocking* violations -- `effort:` absence stays
a warning, per the warn-then-block grace period) plus red/green fixture pairs proving each
blocking rule actually fires and isn't vacuously true.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).parent.parent
PLUGINS_ROOT = REPO_ROOT / "plugins"
_AGENT_SPEC_PATH = REPO_ROOT / "tools" / "agent_spec.py"

_spec = importlib.util.spec_from_file_location("agent_spec", _AGENT_SPEC_PATH)
assert _spec is not None and _spec.loader is not None, f"Cannot load {_AGENT_SPEC_PATH}"
agent_spec = importlib.util.module_from_spec(_spec)
# dataclasses.dataclass() looks its defining module up in sys.modules by name; register
# before exec so tools/agent_spec.py's frozen dataclasses build cleanly.
sys.modules[_spec.name] = agent_spec
_spec.loader.exec_module(agent_spec)

ALL_AGENT_FILES: list[pathlib.Path] = agent_spec.iter_agent_paths(PLUGINS_ROOT)


def _write_agent_file(
    tmp_path: pathlib.Path, name: str, frontmatter: dict[str, str]
) -> pathlib.Path:
    lines = [f"{key}: {value}" for key, value in frontmatter.items()]
    text = "---\n" + "\n".join(lines) + "\n---\n\n# Fixture\n\nbody\n"
    path = tmp_path / f"{name}.md"
    path.write_text(text)
    return path


def _blocking_rule_ids(path: pathlib.Path) -> set[str]:
    record = agent_spec.load_agent(path)
    return {v.rule_id for v in agent_spec.lint_agent(record) if v.blocking}


def _warning_rule_ids(path: pathlib.Path) -> set[str]:
    record = agent_spec.load_agent(path)
    return {v.rule_id for v in agent_spec.lint_agent(record) if not v.blocking}


# ---------------------------------------------------------------------------
# Sanity: the glob must find files, or the full-fleet sweep is inert.
# ---------------------------------------------------------------------------


def test_agent_glob_finds_files() -> None:
    assert ALL_AGENT_FILES, f"no agent files found under {PLUGINS_ROOT}/*/agents/*.md"


# ---------------------------------------------------------------------------
# Clean pass on the fixed fleet (AC: full_fleet)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    ALL_AGENT_FILES,
    ids=[str(p.relative_to(PLUGINS_ROOT)) for p in ALL_AGENT_FILES],
)
def test_full_fleet_agent_file_passes(path: pathlib.Path) -> None:
    """Every current agent file passes the full BLOCKING rule set.

    `effort:` absence is deliberately excluded here -- it is a warning, not a blocker, during
    the grace period (see the dedicated warn-only test below).
    """
    blocking = _blocking_rule_ids(path)
    assert not blocking, f"{path.relative_to(PLUGINS_ROOT)}: blocking rule(s) {blocking} fired"


def test_effort_absence_is_warn_only_on_current_fleet() -> None:
    """0-of-24 team-execution agents carry `effort:` today; none of that may be blocking."""
    warning_only_paths = [
        p
        for p in ALL_AGENT_FILES
        if any(
            v.rule_id == "effort-presence" and not v.blocking
            for v in agent_spec.lint_agent(agent_spec.load_agent(p))
        )
    ]
    assert warning_only_paths, "expected at least one current agent file missing `effort:`"
    for path in warning_only_paths:
        blocking = _blocking_rule_ids(path)
        assert "effort-presence" not in blocking


# ---------------------------------------------------------------------------
# Rule 1: frontmatter schema
# ---------------------------------------------------------------------------


def test_name_stem_mismatch_fails_frontmatter_schema(tmp_path: pathlib.Path) -> None:
    bad = _write_agent_file(tmp_path, "my-agent", {"name": "something-else", "model": "sonnet"})
    assert "frontmatter-schema" in _blocking_rule_ids(bad)


def test_name_stem_match_passes_frontmatter_schema(tmp_path: pathlib.Path) -> None:
    good = _write_agent_file(tmp_path, "my-agent", {"name": "my-agent", "model": "sonnet"})
    assert "frontmatter-schema" not in _blocking_rule_ids(good)


# ---------------------------------------------------------------------------
# Rule 3: model-vs-role-class (AC: role_class_mismatch, survey_opus_mismatch)
# ---------------------------------------------------------------------------


def test_role_class_mismatch_fails(tmp_path: pathlib.Path) -> None:
    """A review-class agent pinned to a weaker-than-permitted model trips the audit."""
    red = _write_agent_file(
        tmp_path,
        "mistiered-reviewer",
        {"name": "mistiered-reviewer", "role-tier": "adversarial-review", "model": "haiku"},
    )
    assert "model-role-class" in _blocking_rule_ids(red)


def test_role_class_match_passes(tmp_path: pathlib.Path) -> None:
    """The same fixture corrected to the permitted tier (opus) passes (asserts both directions)."""
    green = _write_agent_file(
        tmp_path,
        "mistiered-reviewer",
        {"name": "mistiered-reviewer", "role-tier": "adversarial-review", "model": "opus"},
    )
    assert "model-role-class" not in _blocking_rule_ids(green)


def test_survey_opus_mismatch_fails(tmp_path: pathlib.Path) -> None:
    """A survey-class agent pinned to opus trips the audit (proves the rule isn't vacuous)."""
    red = _write_agent_file(
        tmp_path,
        "survey-agent",
        {"name": "survey-agent", "role-tier": "survey", "model": "opus"},
    )
    assert "model-role-class" in _blocking_rule_ids(red)


def test_survey_sonnet_passes(tmp_path: pathlib.Path) -> None:
    """The same fixture corrected to sonnet passes (asserts both directions)."""
    green = _write_agent_file(
        tmp_path,
        "survey-agent",
        {"name": "survey-agent", "role-tier": "survey", "model": "sonnet"},
    )
    assert "model-role-class" not in _blocking_rule_ids(green)


def test_unknown_role_tier_is_not_this_rules_job(tmp_path: pathlib.Path) -> None:
    """An agent with no role-tier (or an unrecognized one) is out of scope for this rule."""
    path = _write_agent_file(
        tmp_path, "ecosystem-agent", {"name": "ecosystem-agent", "model": "opus"}
    )
    assert "model-role-class" not in _blocking_rule_ids(path)


# ---------------------------------------------------------------------------
# Rule 4: tool-scope floor (AC: tool_floor_violation)
# ---------------------------------------------------------------------------


def test_tool_floor_violation_edit_fails(tmp_path: pathlib.Path) -> None:
    red = _write_agent_file(
        tmp_path,
        "leaky-reviewer",
        {
            "name": "leaky-reviewer",
            "role-tier": "adversarial-review",
            "model": "opus",
            "tools": "Read, Edit",
        },
    )
    assert "tool-scope-floor" in _blocking_rule_ids(red)


def test_tool_floor_violation_absent_tools_fails(tmp_path: pathlib.Path) -> None:
    red = _write_agent_file(
        tmp_path,
        "toolless-reviewer",
        {"name": "toolless-reviewer", "role-tier": "adversarial-review", "model": "opus"},
    )
    assert "tool-scope-floor" in _blocking_rule_ids(red)


def test_tool_floor_least_privilege_passes(tmp_path: pathlib.Path) -> None:
    """The same fixture corrected to a non-mutating tool list passes (asserts both directions)."""
    green = _write_agent_file(
        tmp_path,
        "leaky-reviewer",
        {
            "name": "leaky-reviewer",
            "role-tier": "adversarial-review",
            "model": "opus",
            "tools": "Read, Grep, Glob",
        },
    )
    assert "tool-scope-floor" not in _blocking_rule_ids(green)


def test_tool_floor_does_not_apply_to_non_review_class(tmp_path: pathlib.Path) -> None:
    """A scanner-class agent with no tools: field is NOT a tool-scope-floor violation (v1 scope)."""
    path = _write_agent_file(
        tmp_path,
        "cheap-scanner",
        {"name": "cheap-scanner", "role-tier": "mechanical-scan", "model": "haiku"},
    )
    assert "tool-scope-floor" not in _blocking_rule_ids(path)


# ---------------------------------------------------------------------------
# tiering_exempt escape hatch (mirrors tests/test_agent_tier_lint.py's KTD6)
# ---------------------------------------------------------------------------


def test_tiering_exempt_skips_effort_and_role_class_rules(tmp_path: pathlib.Path) -> None:
    path = _write_agent_file(
        tmp_path,
        "exempt-agent",
        {
            "name": "exempt-agent",
            "role-tier": "adversarial-review",
            "model": "haiku",
            "tiering_exempt": "true",
        },
    )
    blocking = _blocking_rule_ids(path)
    assert "model-role-class" not in blocking
    # frontmatter schema and tool-scope-floor are NOT exempted -- exemption covers only the
    # tier-appropriateness/warn-only rules, not schema or least-privilege.


# ---------------------------------------------------------------------------
# FIX-2: the tool-scope floor must not be evadable by valid-YAML punctuation.
# The issue AC's LITERAL red fixture "tools: [Read, Edit]" (and the quoted-scalar
# variant) must FAIL the floor, not sail through on a comma-split artifact.
# ---------------------------------------------------------------------------


def test_tool_floor_flow_list_edit_fails(tmp_path: pathlib.Path) -> None:
    """YAML flow-list form `tools: [Read, Edit]` must trip the floor (bracket-split evasion)."""
    red = _write_agent_file(
        tmp_path,
        "flowlist-reviewer",
        {
            "name": "flowlist-reviewer",
            "role-tier": "adversarial-review",
            "model": "opus",
            "tools": "[Read, Edit]",
        },
    )
    assert "tool-scope-floor" in _blocking_rule_ids(red)


def test_tool_floor_single_quoted_edit_fails(tmp_path: pathlib.Path) -> None:
    """Single-quoted scalar `tools: 'Read, Edit'` must trip the floor (quote-strip evasion)."""
    red = _write_agent_file(
        tmp_path,
        "quoted-reviewer",
        {
            "name": "quoted-reviewer",
            "role-tier": "adversarial-review",
            "model": "opus",
            "tools": "'Read, Edit'",
        },
    )
    assert "tool-scope-floor" in _blocking_rule_ids(red)


def test_tool_floor_bracketed_benign_list_passes(tmp_path: pathlib.Path) -> None:
    """A bracketed benign flow-list must still PASS (normalization isn't over-broad)."""
    green = _write_agent_file(
        tmp_path,
        "flowlist-clean-reviewer",
        {
            "name": "flowlist-clean-reviewer",
            "role-tier": "adversarial-review",
            "model": "opus",
            "tools": "[Bash, Read, Grep, Glob]",
        },
    )
    assert "tool-scope-floor" not in _blocking_rule_ids(green)


def test_parse_tool_list_normalizes_forms() -> None:
    """Direct coverage of the normalizer across bare / bracketed / quoted forms."""
    assert agent_spec._parse_tool_list("Read, Edit") == {"Read", "Edit"}
    assert agent_spec._parse_tool_list("[Read, Edit]") == {"Read", "Edit"}
    assert agent_spec._parse_tool_list("'Read, Edit'") == {"Read", "Edit"}
    assert agent_spec._parse_tool_list('"Read, Edit"') == {"Read", "Edit"}
    assert agent_spec._parse_tool_list("[Bash, Read, Grep, Glob]") == {
        "Bash",
        "Read",
        "Grep",
        "Glob",
    }


# ---------------------------------------------------------------------------
# FIX-3: a role-tier value present but not in agent-role-classes.json must be a
# BLOCKING error -- a typo must not silently exempt an agent from the audit + floor.
# ---------------------------------------------------------------------------


def test_misspelled_role_tier_with_edit_fails_vocab_rule(tmp_path: pathlib.Path) -> None:
    """A typo'd tier carrying Edit must fail role-tier-vocab (not sail through green)."""
    red = _write_agent_file(
        tmp_path,
        "typo-reviewer",
        {
            "name": "typo-reviewer",
            "role-tier": "adversarial-reveiw",  # deliberate typo
            "model": "opus",
            "tools": "Read, Edit",
        },
    )
    blocking = _blocking_rule_ids(red)
    assert "role-tier-vocab" in blocking


def test_recognized_role_tier_passes_vocab_rule(tmp_path: pathlib.Path) -> None:
    """The corrected spelling passes the vocab rule (asserts both directions)."""
    green = _write_agent_file(
        tmp_path,
        "typo-reviewer",
        {
            "name": "typo-reviewer",
            "role-tier": "adversarial-review",
            "model": "opus",
            "tools": "Bash, Read, Grep, Glob",
        },
    )
    assert "role-tier-vocab" not in _blocking_rule_ids(green)


# ---------------------------------------------------------------------------
# FIX-4: --strict promotes the warn-only effort-presence rule to blocking.
# ---------------------------------------------------------------------------


def test_strict_flag_makes_effort_absence_blocking(tmp_path: pathlib.Path) -> None:
    path = _write_agent_file(
        tmp_path,
        "no-effort-agent",
        {"name": "no-effort-agent", "model": "sonnet"},
    )
    record = agent_spec.load_agent(path)

    default_blocking = {v.rule_id for v in agent_spec.lint_agent(record) if v.blocking}
    assert "effort-presence" not in default_blocking

    strict_rules = agent_spec.build_default_rules(strict=True)
    strict_blocking = {v.rule_id for v in agent_spec.lint_agent(record, strict_rules) if v.blocking}
    assert "effort-presence" in strict_blocking


def test_strict_cli_exits_nonzero_on_effort_absence(tmp_path: pathlib.Path) -> None:
    path = _write_agent_file(
        tmp_path,
        "no-effort-agent",
        {"name": "no-effort-agent", "model": "sonnet"},
    )
    assert agent_spec.main([str(path)]) == 0
    assert agent_spec.main(["--strict", str(path)]) == 1


# ---------------------------------------------------------------------------
# FIX-5: a role-tiered agent with no model: emits a warn-only warning, not silence.
# ---------------------------------------------------------------------------


def test_role_tiered_agent_without_model_warns(tmp_path: pathlib.Path) -> None:
    path = _write_agent_file(
        tmp_path,
        "modelless-reviewer",
        {
            "name": "modelless-reviewer",
            "role-tier": "adversarial-review",
            "tools": "Bash, Read, Grep, Glob",
        },
    )
    assert "model-presence" in _warning_rule_ids(path)
    # ...and it is NOT blocking (the tier audit is skipped, but with a signal, not silence).
    assert "model-presence" not in _blocking_rule_ids(path)
