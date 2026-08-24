"""Tests for the write-ownership lane lint (issue #431, hardened in #583).

Covers:
- Clean-pass case against the real saga / mission-control / deploy directories (AC2 / AC5)
- Seeded cross-lane-violation gates (AC3 / R1)
- Wrapper-shaped invocations (_run_gh, _gh, list concatenation) (R1)
- GraphQL ProjectV2 mutation policing for non-owners (R2)
- Read-verb allowance for sensitive subcommands (e.g. gh issue view) (R3)
- Endpoint-position-only evaluation for reserved API paths (R4)
- Missing declared lane directory loud failure (R4)
- CI drift guard asserting the actual step invocation in ci.yml (AC4 / R4)
- Manifest error handling and validation
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

TESTS_ROOT = Path(__file__).parent
REPO_ROOT = TESTS_ROOT.parent
SCRIPTS_ROOT = REPO_ROOT / "scripts"

if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import check_ownership_lanes as col  # noqa: E402

REAL_MANIFEST = REPO_ROOT / "marketplace" / "ownership_lanes.json"
REAL_PLUGINS_ROOT = REPO_ROOT / "plugins"


def _write_plugin_script(root: Path, plugin: str, relpath: str, body: str) -> Path:
    """Helper to write a plugin script and ensure all declared lane dirs exist."""
    for lane in ("saga", "mission-control", "deploy"):
        (root / lane).mkdir(parents=True, exist_ok=True)
    path = root / plugin / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    return path


@pytest.fixture
def manifest() -> dict[str, object]:
    return col.load_manifest(REAL_MANIFEST)


# --------------------------------------------------------------------------- AC1


def test_real_manifest_is_valid_json() -> None:
    """AC1: the shipped manifest parses and declares the three named lanes."""
    data = json.loads(REAL_MANIFEST.read_text())
    for plugin in ("saga", "mission-control", "deploy"):
        assert plugin in data["lanes"]
        assert isinstance(data["lanes"][plugin]["allowed_gh_subcommands"], list)


# ------------------------------------------------------------------ AC2 / AC5


def test_real_tree_is_clean(manifest: dict[str, object]) -> None:
    """AC2 / AC5: the real saga / mission-control / deploy scripts have zero violations."""
    violations = col.run_check(manifest, REAL_PLUGINS_ROOT)
    assert violations == [], "\n".join(v.render(REAL_PLUGINS_ROOT) for v in violations)


def test_main_exit_zero_on_real_tree() -> None:
    """AC2: the CLI entrypoint exits 0 against the real tree."""
    rc = col.main(["--manifest", str(REAL_MANIFEST), "--plugins-root", str(REAL_PLUGINS_ROOT)])
    assert rc == 0


# --------------------------------------------------------------------------- AC3


def test_seeded_violation_deploy_calls_gh_issue(
    tmp_path: Path, manifest: dict[str, object], capsys: pytest.CaptureFixture[str]
) -> None:
    """AC3: a throwaway deploy-lane script calling `gh issue` trips the lint by name."""
    offender = _write_plugin_script(
        tmp_path,
        "deploy",
        "scripts/rogue_promote.py",
        "import subprocess\n"
        'subprocess.run(["gh", "issue", "create", "--title", "oops"], check=True)\n',
    )

    violations = col.run_check(manifest, tmp_path)
    assert len(violations) == 1
    v = violations[0]
    assert v.plugin == "deploy"
    assert v.call == "gh issue"
    assert v.file == offender
    assert "mission-control" in v.crossed_into

    rc = col.main(["--manifest", str(REAL_MANIFEST), "--plugins-root", str(tmp_path)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "rogue_promote.py" in err
    assert "gh issue" in err


def test_seeded_violation_reserved_api_path(tmp_path: Path, manifest: dict[str, object]) -> None:
    """A saga-lane script writing board fields via `gh api projects/` crosses into mc."""
    _write_plugin_script(
        tmp_path,
        "saga",
        "scripts/rogue_board.py",
        "import subprocess\n"
        "pid = 42\n"
        'subprocess.run(["gh", "api", "--method", "PATCH", f"projects/{pid}/items"])\n',
    )
    violations = col.run_check(manifest, tmp_path)
    assert len(violations) == 1
    assert violations[0].crossed_into == "mission-control"
    assert "projects/" in violations[0].call


# --------------------------------------------------------------------------- R1


def test_r1_wrapper_run_gh_flagged_from_non_owner(
    tmp_path: Path, manifest: dict[str, object]
) -> None:
    """R1: a deploy script calling _run_gh(["issue", "create", ...]) is flagged."""
    _write_plugin_script(
        tmp_path,
        "deploy",
        "scripts/deploy_issue_wrapper.py",
        'def _run_gh(args):\n    pass\n_run_gh(["issue", "create", "--title", "bypass"])\n',
    )
    violations = col.run_check(manifest, tmp_path)
    assert len(violations) == 1
    assert violations[0].plugin == "deploy"
    assert violations[0].call == "gh issue"
    assert violations[0].crossed_into == "mission-control"


def test_r1_wrapper_binop_concatenation_flagged(
    tmp_path: Path, manifest: dict[str, object]
) -> None:
    """R1: a deploy script building cmd = ["gh"] + ["issue", "create"] is flagged."""
    _write_plugin_script(
        tmp_path,
        "deploy",
        "scripts/deploy_concat.py",
        "import subprocess\n"
        'cmd = ["gh"] + ["issue", "create", "--title", "bypass"]\n'
        "subprocess.run(cmd)\n",
    )
    violations = col.run_check(manifest, tmp_path)
    assert len(violations) == 1
    assert violations[0].plugin == "deploy"
    assert violations[0].call == "gh issue"


def test_r1_find_gh_invocations_wrapper_shapes() -> None:
    """R1: find_gh_invocations recognizes _run_gh, _run_gh_json, _gh, and list additions."""
    source = (
        'def _run_gh(args): subprocess.run(["gh", *args])\n'
        'def _gh(args): cmd = ["gh"] + args\n'
        '_run_gh(["issue", "create", "--title", "test"])\n'
        '_run_gh_json(["pr", "view", "1", "--json", "state"])\n'
        '_gh(["api", "graphql", "-f", "query=..."])\n'
        'concat_cmd = ["gh"] + ["issue", "delete", "123"]\n'
    )
    invs = col.find_gh_invocations(source)
    # The definitions have subcommand=None, call sites have literal subcommands
    named_invs = [inv for inv in invs if inv.subcommand is not None]
    subcommands = [inv.subcommand for inv in named_invs]
    assert "issue" in subcommands
    assert "pr" in subcommands
    assert "api" in subcommands


# --------------------------------------------------------------------------- R2


def test_r2_graphql_project_v2_mutation_flagged_for_non_owner(
    tmp_path: Path, manifest: dict[str, object]
) -> None:
    """R2: a gh api graphql literal containing updateProjectV2ItemFieldValue is flagged."""
    _write_plugin_script(
        tmp_path,
        "saga",
        "scripts/rogue_graphql_mutation.py",
        "import subprocess\n"
        "query = 'mutation { updateProjectV2ItemFieldValue(input: {}) { clientMutationId } }'\n"
        'subprocess.run(["gh", "api", "graphql", "-f", f"query={query}"])\n',
    )
    violations = col.run_check(manifest, tmp_path)
    assert len(violations) == 1
    v = violations[0]
    assert v.plugin == "saga"
    assert "graphql" in v.call
    assert "updateProjectV2ItemFieldValue" in v.call
    assert v.crossed_into == "mission-control"


def test_r2_graphql_project_v2_mutation_allowed_for_owner(
    tmp_path: Path, manifest: dict[str, object]
) -> None:
    """R2: mission-control can execute ProjectV2 mutations via gh api graphql."""
    _write_plugin_script(
        tmp_path,
        "mission-control",
        "scripts/board_mutation.py",
        "import subprocess\n"
        "query = 'mutation { updateProjectV2ItemFieldValue(input: {}) { clientMutationId } }'\n"
        'subprocess.run(["gh", "api", "graphql", "-f", f"query={query}"])\n',
    )
    violations = col.run_check(manifest, tmp_path)
    assert violations == []


def test_r2_graphql_read_query_allowed_for_all_lanes(
    tmp_path: Path, manifest: dict[str, object]
) -> None:
    """R2: GraphQL read queries (no ProjectV2 mutations) are allowed in saga/deploy."""
    _write_plugin_script(
        tmp_path,
        "saga",
        "scripts/read_subissues.py",
        "import subprocess\n"
        'query = \'query { repository(owner: "o", name: "r") { issue(number: 1) { id } } }\'\n'
        'subprocess.run(["gh", "api", "graphql", "-f", f"query={query}"])\n',
    )
    violations = col.run_check(manifest, tmp_path)
    assert violations == []


# --------------------------------------------------------------------------- R3


def test_r3_direct_literal_issue_view_allowed_for_saga(
    tmp_path: Path, manifest: dict[str, object]
) -> None:
    """R3: direct-literal `gh issue view` (read verb) from saga does not fail the lint."""
    _write_plugin_script(
        tmp_path,
        "saga",
        "scripts/view_issue.py",
        'import subprocess\nsubprocess.run(["gh", "issue", "view", "42", "--json", "state"])\n',
    )
    violations = col.run_check(manifest, tmp_path)
    assert violations == []


def test_r3_read_verbs_allowance_for_sensitive_subcommands(
    tmp_path: Path, manifest: dict[str, object]
) -> None:
    """R3: read verbs (view, list, status, diff, checks) pass; mutation verbs fail."""
    _write_plugin_script(
        tmp_path,
        "saga",
        "scripts/read_verbs.py",
        "import subprocess\n"
        'subprocess.run(["gh", "issue", "list", "--state", "open"])\n'
        'subprocess.run(["gh", "issue", "status"])\n'
        'subprocess.run(["gh", "label", "list"])\n',
    )
    assert col.run_check(manifest, tmp_path) == []

    # But a mutation verb fails:
    _write_plugin_script(
        tmp_path,
        "saga",
        "scripts/mutation_verb.py",
        'import subprocess\nsubprocess.run(["gh", "issue", "close", "42"])\n',
    )
    violations = col.run_check(manifest, tmp_path)
    assert len(violations) == 1
    assert violations[0].call == "gh issue"


# --------------------------------------------------------------------------- R4


def test_r4_lint_wired_into_ci_actual_step() -> None:
    """R4: the CI drift guard asserts the actual step invocation (not just a substring)."""
    ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text()
    pattern = r"run:\s+uv run python scripts/check_ownership_lanes\.py\s+--verbose"
    assert re.search(pattern, ci) is not None, "CI must invoke check_ownership_lanes.py --verbose"


def test_r4_missing_lane_directory_fails_loud(tmp_path: Path, manifest: dict[str, object]) -> None:
    """R4: a declared lane whose directory is missing raises ManifestError."""
    # Create empty tmp_path with no lane subdirectories
    with pytest.raises(col.ManifestError, match="declared lane '.*' directory not found"):
        col.run_check(manifest, tmp_path)


def test_r4_reserved_path_endpoint_position_only(
    tmp_path: Path, manifest: dict[str, object]
) -> None:
    """R4: _reserved_path_crossed checks endpoint position only, avoiding flag false-positives."""
    # Flag containing projects/ string should NOT trigger reserved path violation
    _write_plugin_script(
        tmp_path,
        "saga",
        "scripts/issue_with_flag.py",
        "import subprocess\n"
        'subprocess.run(["gh", "api", "-f", "title=projects/123", "repos/infiquetra/repo/issues"])\n',
    )
    violations = col.run_check(manifest, tmp_path)
    assert violations == []

    # Actual endpoint starting with projects/ DOES trigger violation
    _write_plugin_script(
        tmp_path,
        "saga",
        "scripts/actual_reserved.py",
        "import subprocess\n"
        'subprocess.run(["gh", "api", "--method", "PATCH", "projects/42/items"])\n',
    )
    violations = col.run_check(manifest, tmp_path)
    assert len(violations) == 1
    assert "projects/" in violations[0].call


# --------------------------------------------------------------- detection unit


def test_find_gh_invocations_ignores_docstrings_and_messages() -> None:
    """Docstrings/comments/error strings that merely mention gh are not real calls."""
    source = (
        "def f():\n"
        '    """Reads `gh issue view` off the node."""\n'
        "    # gh pr merge is saga's job\n"
        '    msg = "gh pr view failed; degrading safe"\n'
        "    return msg\n"
    )
    assert col.find_gh_invocations(source) == []


def test_find_gh_invocations_skips_dynamic_command() -> None:
    """`["gh"] + args` has no literal subcommand and must be skipped (not flagged)."""
    invs = col.find_gh_invocations('cmd = ["gh"] + args\n')
    assert len(invs) == 1
    assert invs[0].subcommand is None


def test_find_gh_invocations_reads_list_subcommand() -> None:
    invs = col.find_gh_invocations('run(["gh", "pr", "create", "--fill"])\n')
    assert len(invs) == 1
    assert invs[0].subcommand == "pr"


def test_find_gh_invocations_reads_combined_token() -> None:
    invs = col.find_gh_invocations('run(["gh api", "user"])\n')
    assert len(invs) == 1
    assert invs[0].subcommand == "api"


def test_allowed_subcommand_not_flagged(tmp_path: Path, manifest: dict[str, object]) -> None:
    """saga using `gh pr` (its own lane) and read-only `gh api repos/` is clean."""
    _write_plugin_script(
        tmp_path,
        "saga",
        "scripts/ship.py",
        "import subprocess\n"
        'subprocess.run(["gh", "pr", "merge", "1", "--squash"])\n'
        'subprocess.run(["gh", "api", "repos/o/r/deployments"])\n',
    )
    assert col.run_check(manifest, tmp_path) == []


# --------------------------------------------------------------- manifest guard


def test_missing_manifest_fails_loud(tmp_path: Path) -> None:
    with pytest.raises(col.ManifestError, match="not found"):
        col.load_manifest(tmp_path / "nope.json")


def test_malformed_manifest_fails_loud(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{ not json")
    with pytest.raises(col.ManifestError, match="not valid JSON"):
        col.load_manifest(bad)


def test_manifest_missing_key_fails_loud(tmp_path: Path) -> None:
    bad = tmp_path / "partial.json"
    bad.write_text('{"sensitive_subcommands": [], "reserved_api_paths": {}}')
    with pytest.raises(col.ManifestError, match="lanes"):
        col.load_manifest(bad)


def test_main_returns_2_on_bad_manifest(tmp_path: Path) -> None:
    rc = col.main(["--manifest", str(tmp_path / "missing.json")])
    assert rc == 2


# ------------------------------------------------- review repairs (#583 cycle 1)


def test_unresolvable_flag_value_does_not_swallow_reserved_endpoint(
    tmp_path: Path, manifest: dict[str, object]
) -> None:
    """A non-literal flag value must not shift the endpoint into the flag's value slot.

    `_api_endpoint` skips a value-taking flag and its argument. When that argument is a bare
    name it has no static string, so dropping it made the skip consume the endpoint itself and
    `gh api --jq <expr> projects/42/items` passed the gate clean. Positions are placeheld now.
    """
    _write_plugin_script(
        tmp_path,
        "saga",
        "scripts/rogue_board_via_flag.py",
        "import subprocess\n"
        "def go(jq_expr, header):\n"
        '    subprocess.run(["gh", "api", "--jq", jq_expr, "projects/42/items"])\n'
        '    subprocess.run(["gh", "api", "-H", header, "projects/42/items"])\n',
    )
    violations = col.run_check(manifest, tmp_path)
    assert len(violations) == 2
    assert all(v.crossed_into == "mission-control" for v in violations)
    assert all("projects/" in v.call for v in violations)


def test_unresolved_token_is_placeheld_not_dropped() -> None:
    """Element positions survive an unresolvable argument."""
    invs = col.find_gh_invocations('run(["gh", "api", "--jq", jq, "projects/42/items"])\n')
    assert len(invs) == 1
    assert invs[0].tokens == (
        "gh",
        "api",
        "--jq",
        col.UNRESOLVED_TOKEN,
        "projects/42/items",
    )
    assert col._api_endpoint(invs[0].tokens) == "projects/42/items"


def test_rebound_variable_cannot_mask_a_project_v2_mutation(
    tmp_path: Path, manifest: dict[str, object]
) -> None:
    """A later same-named binding must not hide an earlier ProjectV2 mutation query.

    `_collect_string_variables` is scope-blind, so two functions each assigning `query` used to
    collapse to one binding — a read query bound after a mutation query hid the mutation and the
    board write passed clean. Every binding is kept, and the gate fails closed.
    """
    _write_plugin_script(
        tmp_path,
        "saga",
        "scripts/rogue_rebound_query.py",
        "import subprocess\n"
        "def write_board():\n"
        "    query = 'mutation { updateProjectV2ItemFieldValue(input: $i) { id } }'\n"
        '    subprocess.run(["gh", "api", "graphql", "-f", f"query={query}"])\n'
        "def read_board():\n"
        '    query = \'query { repository(owner: \\"o\\", name: \\"r\\") { id } }\'\n'
        '    subprocess.run(["gh", "api", "graphql", "-f", f"query={query}"])\n',
    )
    violations = col.run_check(manifest, tmp_path)
    assert violations, "the ProjectV2 mutation must be attributed to the saga lane"
    assert all("updateProjectV2ItemFieldValue" in v.call for v in violations)
    assert all(v.crossed_into == "mission-control" for v in violations)


def test_collect_string_variables_keeps_every_binding() -> None:
    """A name bound twice carries both values, in source order."""
    var_map = col._collect_string_variables(
        __import__("ast").parse("q = 'first'\ndef f():\n    q = 'second'\n")
    )
    assert var_map["q"] == ("first", "second")


def test_combined_token_read_verb_is_allowed(tmp_path: Path, manifest: dict[str, object]) -> None:
    """`["gh issue view", ...]` must get the read-verb allowance like the split form does."""
    _write_plugin_script(
        tmp_path,
        "saga",
        "scripts/combined_read.py",
        'import subprocess\nsubprocess.run(["gh issue view", "42", "--json", "state"])\n',
    )
    assert col.run_check(manifest, tmp_path) == []


def test_combined_token_mutation_verb_still_flagged(
    tmp_path: Path, manifest: dict[str, object]
) -> None:
    """The combined form must not become an escape hatch for mutations."""
    _write_plugin_script(
        tmp_path,
        "deploy",
        "scripts/combined_write.py",
        'import subprocess\nsubprocess.run(["gh issue create", "--title", "bypass"])\n',
    )
    violations = col.run_check(manifest, tmp_path)
    assert len(violations) == 1
    assert violations[0].call == "gh issue"


def test_extract_verb_reads_combined_subcommand_and_verb() -> None:
    assert col._extract_verb(("gh issue view", "42"), "issue") == "view"
    assert col._extract_verb(("gh issue create", "--title"), "issue") == "create"
    assert col._extract_verb(("gh", "issue", "view", "42"), "issue") == "view"


def test_manifest_doc_matches_shipped_verb_awareness() -> None:
    """The manifest is the lint's human-facing contract; it must not describe retired behavior."""
    doc = " ".join(json.loads(REAL_MANIFEST.read_text())["_doc"])
    assert "VERB-AWARE" in doc
    assert "not yet policed" not in doc
    assert "the lint does not attribute" not in doc
