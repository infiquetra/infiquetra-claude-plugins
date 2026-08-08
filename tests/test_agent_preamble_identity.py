"""Tests for #704 U6: every agent definition carries a byte-identical copy of the canonical
subagent presentation preamble.

Two properties this file exists specifically to catch:

(a) The file count is asserted against an ENUMERATED expectation, not a glob-at-test-time
    count. A test that discovers its own population (``len(glob(...)) == len(glob(...))``)
    cannot detect a 37th `plugins/*/agents/*.md` file that was added without the preamble --
    the new file would just join the denominator and vanish from the count. The 36-file list
    below is the fixed ground truth; a mismatch (missing OR extra) fails loudly.

(b) The preamble is inserted into the body without disturbing frontmatter -- each file must
    still open with a bare ``---`` frontmatter block, and ``tests/test_agent_registration_drift.py``
    (a separate suite covering saga's frontmatter-driven agent registration) must still pass
    unmodified by this change.
"""

from __future__ import annotations

import pathlib

REPO_ROOT = pathlib.Path(__file__).parent.parent
PREAMBLE_PATH = (
    REPO_ROOT / "plugins" / "house-style" / "references" / "subagent-presentation-preamble.md"
)

# The enumerated ground truth: exactly these 36 paths, spread across 9 plugins (25 of them
# under team-execution). Do NOT replace this with a glob -- see module docstring (a).
EXPECTED_AGENT_FILES: tuple[str, ...] = (
    "plugins/agy/agents/agy-coder.md",
    "plugins/agy/agents/agy-reviewer.md",
    "plugins/codex/agents/codex-coder.md",
    "plugins/codex/agents/codex-reviewer.md",
    "plugins/deploy/agents/release-orchestrator.md",
    "plugins/home-lab-ops/agents/homelab-sre.md",
    "plugins/mission-control/agents/sdlc-operator.md",
    "plugins/redis-channel/agents/redis-channel-coach.md",
    "plugins/saga/agents/mechanical-executor.md",
    "plugins/saga/agents/readonly-verifier.md",
    "plugins/team-execution/agents/ai-usefulness-reviewer.md",
    "plugins/team-execution/agents/api-compat-scanner.md",
    "plugins/team-execution/agents/api-contract-tester.md",
    "plugins/team-execution/agents/api-reviewer.md",
    "plugins/team-execution/agents/architecture-reviewer.md",
    "plugins/team-execution/agents/clarity-reviewer.md",
    "plugins/team-execution/agents/code-quality-reviewer.md",
    "plugins/team-execution/agents/concurrency-tester.md",
    "plugins/team-execution/agents/dependency-scanner.md",
    "plugins/team-execution/agents/deploy-watcher.md",
    "plugins/team-execution/agents/devils-advocate-reviewer.md",
    "plugins/team-execution/agents/event-flow-tester.md",
    "plugins/team-execution/agents/github-actions-monitor.md",
    "plugins/team-execution/agents/iac-cost-scanner.md",
    "plugins/team-execution/agents/infra-reviewer.md",
    "plugins/team-execution/agents/performance-tester.md",
    "plugins/team-execution/agents/privacy-reviewer.md",
    "plugins/team-execution/agents/runtime-monitor.md",
    "plugins/team-execution/agents/scenario-tester.md",
    "plugins/team-execution/agents/sdk-regression-tester.md",
    "plugins/team-execution/agents/security-reviewer.md",
    "plugins/team-execution/agents/security-scanner.md",
    "plugins/team-execution/agents/smoke-tester.md",
    "plugins/team-execution/agents/testing-reviewer.md",
    "plugins/team-execution/agents/ui-regression-tester.md",
    "plugins/unifi/agents/unifi-network-ops.md",
)


def _discovered_agent_files() -> list[pathlib.Path]:
    """The actual on-disk population, sorted -- compared AGAINST the enumeration, never
    used as the pass/fail criterion by itself."""
    return sorted(REPO_ROOT.glob("plugins/*/agents/*.md"))


def test_expected_agent_file_count_is_exactly_36() -> None:
    assert len(EXPECTED_AGENT_FILES) == 36


def test_enumerated_agent_files_match_disk_exactly() -> None:
    """Catches both directions of drift: a file removed from disk, and a file added to disk
    that the enumeration above doesn't know about (the #37 case)."""
    expected = {REPO_ROOT / rel for rel in EXPECTED_AGENT_FILES}
    actual = set(_discovered_agent_files())

    missing_from_disk = expected - actual
    unexpected_on_disk = actual - expected

    assert not missing_from_disk, (
        f"Enumerated agent file(s) no longer exist on disk: "
        f"{sorted(str(p.relative_to(REPO_ROOT)) for p in missing_from_disk)}"
    )
    assert not unexpected_on_disk, (
        f"Agent file(s) exist on disk but are not in the enumerated 36-file expectation "
        f"(a new agent file was added without being given the preamble and added here): "
        f"{sorted(str(p.relative_to(REPO_ROOT)) for p in unexpected_on_disk)}"
    )
    assert len(actual) == 36, f"Expected exactly 36 agent files, found {len(actual)}"


def test_synthetic_37th_agent_file_is_flagged(tmp_path: pathlib.Path) -> None:
    """Negative case proving the assertion in the prior test isn't vacuous: simulates a 37th
    `plugins/*/agents/*.md` file that was never given the preamble, using the SAME
    set-difference decision the positive test relies on."""
    expected = {REPO_ROOT / rel for rel in EXPECTED_AGENT_FILES}
    synthetic_extra = REPO_ROOT / "plugins" / "synthetic-plugin" / "agents" / "ghost-agent.md"
    actual = set(_discovered_agent_files()) | {synthetic_extra}

    unexpected_on_disk = actual - expected
    assert unexpected_on_disk == {synthetic_extra}


def test_preamble_source_file_exists() -> None:
    assert PREAMBLE_PATH.exists(), f"Canonical preamble source missing: {PREAMBLE_PATH}"


def test_preamble_source_has_no_frontmatter_delimiter_collision() -> None:
    """The preamble is inserted into agent-file bodies, never into the frontmatter block, but
    a stray line reading exactly `---` inside the preamble would still be a latent hazard if
    a future edit ever moved the insertion point. Fail closed now rather than discover it
    later via a broken frontmatter parse."""
    lines = PREAMBLE_PATH.read_text().split("\n")
    assert not any(line.startswith("---") for line in lines), (
        "the canonical preamble must not contain a line starting with `---` -- such a line "
        "would be mistaken for a frontmatter delimiter if the preamble is ever inserted "
        "immediately after the opening `---` block"
    )


def test_every_expected_agent_file_contains_byte_identical_preamble() -> None:
    preamble = PREAMBLE_PATH.read_text()
    failures = []
    for rel in EXPECTED_AGENT_FILES:
        path = REPO_ROOT / rel
        if not path.exists():
            failures.append(f"{rel}: file does not exist")
            continue
        text = path.read_text()
        if preamble not in text:
            failures.append(f"{rel}: does not contain a byte-identical copy of the preamble")
    assert not failures, "\n".join(failures)


def test_every_expected_agent_file_still_opens_with_frontmatter() -> None:
    """The preamble insertion must not disturb the existing frontmatter block (name,
    description, tools, etc.) that agent registration depends on."""
    failures = []
    for rel in EXPECTED_AGENT_FILES:
        path = REPO_ROOT / rel
        text = path.read_text()
        lines = text.split("\n")
        if not lines or lines[0] != "---":
            failures.append(f"{rel}: does not open with a bare `---` frontmatter line")
            continue
        close_idx = next((i for i in range(1, len(lines)) if lines[i] == "---"), None)
        if close_idx is None:
            failures.append(f"{rel}: frontmatter block is unterminated")
    assert not failures, "\n".join(failures)


def test_synthetic_non_identical_copy_is_flagged(tmp_path: pathlib.Path) -> None:
    """Negative case proving the byte-identity check isn't vacuous: a copy that differs by a
    single trailing character must fail the same containment check the positive test uses."""
    preamble = PREAMBLE_PATH.read_text()
    mutated = preamble.rstrip("\n") + " EXTRA\n"
    fixture = tmp_path / "mutated-agent.md"
    fixture.write_text(f"---\nname: mutated-agent\n---\n\n{mutated}\nbody\n")

    text = fixture.read_text()
    assert preamble not in text
