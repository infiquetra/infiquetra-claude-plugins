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


def test_scanner_opus_mismatch_fails(tmp_path: pathlib.Path) -> None:
    """A sonnet-max-class agent pinned to opus trips the audit (proves the ceiling isn't vacuous).

    Uses `mechanical-scan` (the scanner class's dispatch alias) rather than the issue AC's
    original `role-tier: survey` spelling: a class key is no longer a valid `role-tier:` value
    (FIX-2 round 2 -- the lint vocabulary is pinned to dispatch's ROLE_TIER_ALIASES, and
    `survey` has no dispatch alias yet). Scanner shares survey's max_model=sonnet ceiling, so
    this exercises the same "pinned to opus must fail" scenario through a dispatch-valid tier.
    """
    red = _write_agent_file(
        tmp_path,
        "scan-agent",
        {"name": "scan-agent", "role-tier": "mechanical-scan", "model": "opus"},
    )
    assert "model-role-class" in _blocking_rule_ids(red)


def test_scanner_sonnet_passes(tmp_path: pathlib.Path) -> None:
    """The same fixture corrected to sonnet passes (asserts both directions)."""
    green = _write_agent_file(
        tmp_path,
        "scan-agent",
        {"name": "scan-agent", "role-tier": "mechanical-scan", "model": "sonnet"},
    )
    assert "model-role-class" not in _blocking_rule_ids(green)


def test_survey_class_reachable_only_through_an_alias(tmp_path: pathlib.Path) -> None:
    """The reserved `survey` class still audits correctly once an alias maps onto it.

    The real tables carry no survey alias today (dispatch has none), so this drives the audit
    through an injected policy -- proving the class config is live, not dead weight.
    """
    survey_policy = {
        "survey": {
            "role_tier_aliases": ["read-only-survey"],
            "min_model": "haiku",
            "max_model": "sonnet",
            "is_review_class": False,
        }
    }
    rules = [
        agent_spec.Rule(
            "model-role-class", True, agent_spec.make_model_role_class_check(survey_policy)
        )
    ]
    red = _write_agent_file(
        tmp_path,
        "survey-agent",
        {"name": "survey-agent", "role-tier": "read-only-survey", "model": "opus"},
    )
    record = agent_spec.load_agent(red)
    assert any(v.rule_id == "model-role-class" for v in agent_spec.lint_agent(record, rules))


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
# FIX-2 (round 2): tools: values are resolved with REAL YAML semantics (yaml.safe_load --
# what the runtime grants) and then strictly validated fail-closed. A mutating tool cannot
# hide behind ANY valid-YAML authoring, because unrecognized forms are errors, not passes.
# Red fixtures: every one of these MUST produce a blocking violation.
# ---------------------------------------------------------------------------


def test_tool_floor_flow_list_edit_fails(tmp_path: pathlib.Path) -> None:
    """YAML flow-list form `tools: [Read, Edit]` must trip the floor (resolves to a real list)."""
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
    """Single-quoted scalar `tools: 'Read, Edit'` must trip the floor (YAML strips the quotes)."""
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


def test_tool_floor_trailing_comment_edit_fails(tmp_path: pathlib.Path) -> None:
    """`tools: Read, Edit # innocuous note` -- YAML strips the comment; the floor must see Edit.

    The round-1 tokenizer produced the token `Edit # innocuous note` != `Edit` and passed;
    the runtime's yaml.safe_load resolves the value to 'Read, Edit' and grants Edit.
    """
    red = _write_agent_file(
        tmp_path,
        "comment-reviewer",
        {
            "name": "comment-reviewer",
            "role-tier": "adversarial-review",
            "model": "opus",
            "tools": "Read, Edit # innocuous note",
        },
    )
    assert "tool-scope-floor" in _blocking_rule_ids(red)


def test_tool_floor_folded_scalar_edit_fails(tmp_path: pathlib.Path) -> None:
    """Folded block scalar `tools: >-\\n  Read, Edit` resolves to 'Read, Edit' -- must fail."""
    red = _write_agent_file(
        tmp_path,
        "folded-reviewer",
        {
            "name": "folded-reviewer",
            "role-tier": "adversarial-review",
            "model": "opus",
            "tools": ">-\n  Read, Edit",
        },
    )
    assert "tool-scope-floor" in _blocking_rule_ids(red)


def test_tool_floor_literal_block_edit_fails(tmp_path: pathlib.Path) -> None:
    """Literal block scalar `tools: |\\n  Read, Edit` resolves to 'Read, Edit\\n' -- must fail."""
    red = _write_agent_file(
        tmp_path,
        "literal-reviewer",
        {
            "name": "literal-reviewer",
            "role-tier": "adversarial-review",
            "model": "opus",
            "tools": "|\n  Read, Edit",
        },
    )
    assert "tool-scope-floor" in _blocking_rule_ids(red)


def test_tool_floor_multiline_flow_list_edit_fails(tmp_path: pathlib.Path) -> None:
    """Multi-line flow list `tools: [Read,\\n  Edit]` resolves to a real list -- must fail."""
    red = _write_agent_file(
        tmp_path,
        "multiline-reviewer",
        {
            "name": "multiline-reviewer",
            "role-tier": "adversarial-review",
            "model": "opus",
            "tools": "[Read,\n  Edit]",
        },
    )
    assert "tool-scope-floor" in _blocking_rule_ids(red)


def test_tool_floor_block_list_edit_fails(tmp_path: pathlib.Path) -> None:
    """Block-list form resolves to a real list; Edit in it must fail the floor (was previously
    mis-reported as 'has no tools: frontmatter field')."""
    text = (
        "---\n"
        "name: blocklist-reviewer\n"
        "role-tier: adversarial-review\n"
        "model: opus\n"
        "tools:\n"
        "  - Read\n"
        "  - Edit\n"
        "---\n\nbody\n"
    )
    path = tmp_path / "blocklist-reviewer.md"
    path.write_text(text)
    blocking = _blocking_rule_ids(path)
    assert "tool-scope-floor" in blocking
    # ...and the message names the mutating tool, not a bogus "no tools: field" claim.
    record = agent_spec.load_agent(path)
    floor_msgs = [
        v.message for v in agent_spec.lint_agent(record) if v.rule_id == "tool-scope-floor"
    ]
    assert floor_msgs and "Edit" in floor_msgs[0]
    assert "no `tools:` frontmatter field" not in floor_msgs[0]


def test_tool_floor_trailing_comma_fails_closed(tmp_path: pathlib.Path) -> None:
    """A trailing comma (`Bash, Read,`) is not a recognized form -- fails closed even though
    no mutating tool is present (the guarantee is fail-closed, not enumerate-and-allow)."""
    red = _write_agent_file(
        tmp_path,
        "trailing-comma-reviewer",
        {
            "name": "trailing-comma-reviewer",
            "role-tier": "adversarial-review",
            "model": "opus",
            "tools": "Bash, Read,",
        },
    )
    blocking = _blocking_rule_ids(red)
    assert "tool-scope-floor" in blocking
    assert "tools-shape" in blocking


def test_tool_floor_explicit_empty_list_fails(tmp_path: pathlib.Path) -> None:
    """`tools: []` on a review-class agent is a blocking authoring mistake, not a floor pass."""
    red = _write_agent_file(
        tmp_path,
        "empty-roster-reviewer",
        {
            "name": "empty-roster-reviewer",
            "role-tier": "adversarial-review",
            "model": "opus",
            "tools": "[]",
        },
    )
    blocking = _blocking_rule_ids(red)
    assert "tool-scope-floor" in blocking
    assert "tools-shape" in blocking


def test_tool_floor_valueless_tools_key_fails(tmp_path: pathlib.Path) -> None:
    """A bare `tools:` key with no value resolves to None -- blocking, never treated as a list."""
    red = _write_agent_file(
        tmp_path,
        "valueless-reviewer",
        {
            "name": "valueless-reviewer",
            "role-tier": "adversarial-review",
            "model": "opus",
            "tools": "",
        },
    )
    blocking = _blocking_rule_ids(red)
    assert "tool-scope-floor" in blocking
    assert "tools-shape" in blocking


def test_duplicate_tools_key_is_blocking(tmp_path: pathlib.Path) -> None:
    """Two `tools:` keys in one block: last-wins vs first-wins ambiguity means a consumer could
    execute an unaudited roster -- strict parsing rejects the duplicate outright."""
    text = (
        "---\n"
        "name: duplicate-reviewer\n"
        "role-tier: adversarial-review\n"
        "model: opus\n"
        "tools: Bash, Read, Grep, Glob\n"
        "tools: Read, Edit\n"
        "---\n\nbody\n"
    )
    path = tmp_path / "duplicate-reviewer.md"
    path.write_text(text)
    assert "frontmatter-schema" in _blocking_rule_ids(path)


def test_tools_shape_applies_fleet_wide(tmp_path: pathlib.Path) -> None:
    """A malformed tools: value blocks even on a non-review-class agent (unaudited roster)."""
    red = _write_agent_file(
        tmp_path,
        "malformed-scanner",
        {
            "name": "malformed-scanner",
            "role-tier": "mechanical-scan",
            "model": "haiku",
            "tools": "Bash,, Read",
        },
    )
    blocking = _blocking_rule_ids(red)
    assert "tools-shape" in blocking
    assert "tool-scope-floor" not in blocking  # scanner is not review-class


# --- Green fixtures: the recognized authored forms must still pass -----------------


def test_tool_floor_bracketed_benign_list_passes(tmp_path: pathlib.Path) -> None:
    """A bracketed benign flow-list must still PASS (strictness isn't over-broad)."""
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


def test_tool_floor_quoted_benign_scalar_passes(tmp_path: pathlib.Path) -> None:
    """A double-quoted benign comma list must still PASS (YAML resolves the quotes away)."""
    green = _write_agent_file(
        tmp_path,
        "quoted-clean-reviewer",
        {
            "name": "quoted-clean-reviewer",
            "role-tier": "adversarial-review",
            "model": "opus",
            "tools": '"Bash, Read, Grep, Glob"',
        },
    )
    blocking = _blocking_rule_ids(green)
    assert "tool-scope-floor" not in blocking
    assert "tools-shape" not in blocking


def test_tool_floor_block_list_benign_passes(tmp_path: pathlib.Path) -> None:
    """A benign block list is a recognized form (list of plain strings) and passes."""
    text = (
        "---\n"
        "name: blocklist-clean-reviewer\n"
        "role-tier: adversarial-review\n"
        "model: opus\n"
        "tools:\n"
        "  - Bash\n"
        "  - Read\n"
        "  - Grep\n"
        "  - Glob\n"
        "---\n\nbody\n"
    )
    path = tmp_path / "blocklist-clean-reviewer.md"
    path.write_text(text)
    blocking = _blocking_rule_ids(path)
    assert "tool-scope-floor" not in blocking
    assert "tools-shape" not in blocking


def test_parse_tools_value_recognized_and_fail_closed_forms() -> None:
    """Direct coverage of the strict normalizer: two recognized forms, everything else raises."""
    assert agent_spec.parse_tools_value("Bash, Read, Grep, Glob") == [
        "Bash",
        "Read",
        "Grep",
        "Glob",
    ]
    assert agent_spec.parse_tools_value(["Read", "Grep"]) == ["Read", "Grep"]
    assert agent_spec.parse_tools_value("NotebookEdit") == ["NotebookEdit"]

    for bad in (
        None,  # key present, no value
        "",  # explicit-empty scalar
        [],  # explicit-empty list
        "Read, Edit,",  # trailing comma -> empty token
        "Read,, Edit",  # empty token
        "'Read', 'Edit'",  # embedded quotes survive YAML -> not bare names
        {"Read": True},  # mapping
        ["Read", ["Edit"]],  # nested list
        ["Read", 3],  # non-string item
        3,  # non-collection scalar
    ):
        with pytest.raises(agent_spec.ToolsValueError):
            agent_spec.parse_tools_value(bad)


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
# FIX-3 (round 2): the lint's role-tier vocabulary is the DISPATCH vocabulary.
# A class key (review/tester/scanner/survey) is not dispatch-resolvable
# (fleet_commons.tier_resolver resolves role-tier: only via ROLE_TIER_ALIASES),
# so it must fail the vocab rule instead of linting green and failing at dispatch.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("class_key", ["review", "tester", "scanner", "survey"])
def test_class_key_as_role_tier_fails_vocab_rule(class_key: str, tmp_path: pathlib.Path) -> None:
    red = _write_agent_file(
        tmp_path,
        "classkey-agent",
        {
            "name": "classkey-agent",
            "role-tier": class_key,
            "model": "opus",
            "tools": "Bash, Read, Grep, Glob",
        },
    )
    assert "role-tier-vocab" in _blocking_rule_ids(red)


def test_role_tier_vocab_matches_dispatch_aliases() -> None:
    """Drift guard: the classified aliases in tools/agent-role-classes.json must be identical
    to the dispatch path's ROLE_TIER_ALIASES (fleet_commons/tier_resolver.py) -- both ways."""
    assert agent_spec.role_tier_vocabulary_drift() == []
    policy = agent_spec.load_role_class_policy()
    classified = {alias for cfg in policy.values() for alias in cfg.get("role_tier_aliases", [])}
    assert classified == set(agent_spec.ROLE_TIER_ALIASES)


def test_synthetic_role_tier_vocab_drift_is_detected() -> None:
    """Both drift directions produce messages (proves the guard isn't vacuous)."""
    # A lint-only alias dispatch cannot resolve:
    lint_only = {
        "review": {"role_tier_aliases": ["adversarial-review", "lint-only-alias"]},
    }
    msgs = agent_spec.role_tier_vocabulary_drift(lint_only)
    assert any("lint-only-alias" in m and "not dispatch-resolvable" in m for m in msgs)
    # A dispatch alias the lint leaves unclassified (empty policy -> every alias unclassified):
    msgs = agent_spec.role_tier_vocabulary_drift({})
    assert msgs and all("unclassified" in m for m in msgs)


def test_cli_blocks_on_vocab_drift(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The CLI fails the whole lint when the alias tables drift (blocking, not advisory)."""
    drifted = tmp_path / "agent-role-classes.json"
    drifted.write_text(
        '{"review": {"role_tier_aliases": ["adversarial-review", "lint-only-alias"], '
        '"min_model": "opus", "max_model": "opus", "is_review_class": true}}'
    )
    monkeypatch.setattr(agent_spec, "ROLE_CLASSES_PATH", drifted)
    good = _write_agent_file(tmp_path, "plain-agent", {"name": "plain-agent", "model": "sonnet"})
    assert agent_spec.main([str(good)]) == 1


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
