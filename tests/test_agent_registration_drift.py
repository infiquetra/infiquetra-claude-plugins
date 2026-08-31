"""Tests for #325 R4: static discoverability drift guard for saga agent registration.

Cannot assert the running session's agent roster from CI (unobservable), so this guards
every repo-side precondition of discoverability instead: frontmatter parses and its
`name:` matches the file stem, `execution_spec.py`'s READONLY_VERIFIER_AGENT_TYPE constant
matches the on-disk agent, every spawn-context `saga:<name>` reference resolves to an
existing agent file, and the #325 fallback ladder is documented (Key Technical Decision 2).
"""

from __future__ import annotations

import importlib.util
import pathlib
import re
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).parent.parent
PLUGINS_ROOT = REPO_ROOT / "plugins"
SAGA_AGENTS_DIR = PLUGINS_ROOT / "saga" / "agents"
EXECUTION_SPEC_PATH = PLUGINS_ROOT / "saga" / "scripts" / "execution_spec.py"
# The emission internals (incl. this constant) moved to the cc-workflows plugin (#925/U4).
WORKFLOW_EMITTER_PATH = (
    PLUGINS_ROOT / "cc-workflows" / "skills" / "cc-workflows" / "scripts" / "emitter.py"
)
SANDBOX_SPAWN_SITES_PATH = PLUGINS_ROOT / "saga" / "references" / "sandbox-spawn-sites.md"
CLAUDE_MD_PATH = REPO_ROOT / "CLAUDE.md"

# A spawn-context line names an agent by subagent_type or agentType — the only references
# that can hard-fail a session. A bare `saga:<name>` mention elsewhere (e.g. a skill name
# like `/saga:work` or `saga:plan` in prose) is deliberately NOT in scope: skills share the
# `saga:` namespace with agents, so an unscoped grep false-positives on every skill mention.
SPAWN_CONTEXT_PATTERN = re.compile(
    r"(?:subagent_type|agentType)\s*[:=]\s*['\"]?saga:([a-zA-Z0-9_-]+)['\"]?"
)

# #422: the frontmatter parser is shared (tools/ is not an importable package, so we load it
# the same way tests/test_release_rituals.py loads other tools/*.py modules).
_AGENT_SPEC_PATH = REPO_ROOT / "tools" / "agent_spec.py"
_spec = importlib.util.spec_from_file_location("agent_spec", _AGENT_SPEC_PATH)
assert _spec is not None and _spec.loader is not None, f"Cannot load {_AGENT_SPEC_PATH}"
_agent_spec = importlib.util.module_from_spec(_spec)
# dataclasses.dataclass() looks its defining module up in sys.modules by name; register
# before exec so tools/agent_spec.py's frozen dataclasses build cleanly.
sys.modules[_spec.name] = _agent_spec
_spec.loader.exec_module(_agent_spec)

_parse_frontmatter = _agent_spec.parse_frontmatter


def _saga_agent_files() -> list[pathlib.Path]:
    return sorted(SAGA_AGENTS_DIR.glob("*.md"))


def _spawn_context_agent_names(corpus: str) -> set[str]:
    return set(SPAWN_CONTEXT_PATTERN.findall(corpus))


def _name_matches_stem(fm: dict[str, str], stem: str) -> bool:
    """The (a) decision: does frontmatter `name:` match the file stem it lives in?"""
    return fm.get("name") == stem


def _constant_matches_frontmatter(constant_value: str, fm: dict[str, str]) -> bool:
    """The (b) decision: does the emitter's agent-type constant match the on-disk agent?"""
    return constant_value == f"saga:{fm.get('name')}"


def _dangling_references(referenced: set[str], known_names: set[str]) -> set[str]:
    """The (c) decision: which spawn-context references have no matching agent file?"""
    return referenced - known_names


# ---------------------------------------------------------------------------
# (a) Frontmatter name matches file stem
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "agent_path", _saga_agent_files(), ids=[p.stem for p in _saga_agent_files()]
)
def test_agent_frontmatter_name_matches_stem(agent_path: pathlib.Path) -> None:
    fm = _parse_frontmatter(agent_path.read_text())
    assert "name" in fm, f"{agent_path} has no `name:` field in frontmatter"
    assert _name_matches_stem(fm, agent_path.stem), (
        f"{agent_path}: frontmatter `name: {fm['name']}` does not match file stem "
        f"`{agent_path.stem}` — a mismatch here means `saga:{agent_path.stem}` won't "
        f"resolve to this file."
    )


def test_synthetic_name_mismatch_is_flagged() -> None:
    """Negative case: exercises the SAME _name_matches_stem decision the positive test uses,
    so a regression that makes the decision always-true would fail this test too (proves the
    assertion isn't vacuous — see #325 code-review finding: the prior version of this test
    reimplemented the comparison inline and stayed green under mutation)."""
    fm = _parse_frontmatter("---\nname: something-else\nmodel: sonnet\n---\n\nbody")
    assert not _name_matches_stem(fm, "readonly-verifier")


# ---------------------------------------------------------------------------
# (b) execution_spec.py's READONLY_VERIFIER_AGENT_TYPE matches the on-disk agent
# ---------------------------------------------------------------------------


def test_readonly_verifier_agent_type_constant_matches_disk() -> None:
    spec_text = WORKFLOW_EMITTER_PATH.read_text()
    m = re.search(r'READONLY_VERIFIER_AGENT_TYPE\s*=\s*"([^"]+)"', spec_text)
    assert m, (
        "the cc-workflows emitter no longer defines READONLY_VERIFIER_AGENT_TYPE as a string literal"
    )
    constant_value = m.group(1)

    agent_path = SAGA_AGENTS_DIR / "readonly-verifier.md"
    assert agent_path.exists(), f"Agent file missing: {agent_path}"
    fm = _parse_frontmatter(agent_path.read_text())

    assert _constant_matches_frontmatter(constant_value, fm), (
        f"the cc-workflows emitter's READONLY_VERIFIER_AGENT_TYPE={constant_value!r} does not match "
        f"saga:{fm['name']!r} derived from {agent_path}'s frontmatter."
    )


def test_synthetic_constant_mismatch_is_flagged() -> None:
    """Negative case: exercises the SAME _constant_matches_frontmatter decision the positive
    test uses, so a stale-constant regression would fail this test too."""
    constant_value = "saga:readonly-verifier-v2"
    fm = _parse_frontmatter((SAGA_AGENTS_DIR / "readonly-verifier.md").read_text())
    assert not _constant_matches_frontmatter(constant_value, fm)


# ---------------------------------------------------------------------------
# (c) Every spawn-context saga:<name> reference resolves to an existing agent file
# ---------------------------------------------------------------------------


def test_spawn_context_references_resolve_to_agent_files() -> None:
    known_names = {p.stem for p in _saga_agent_files()}
    corpus_paths = list(PLUGINS_ROOT.glob("saga/**/*.md")) + list(PLUGINS_ROOT.glob("saga/**/*.py"))
    corpus_paths.append(CLAUDE_MD_PATH)

    referenced: set[str] = set()
    for path in corpus_paths:
        if not path.is_file():
            continue
        referenced |= _spawn_context_agent_names(path.read_text())

    dangling = _dangling_references(referenced, known_names)
    assert not dangling, (
        f"Spawn-context reference(s) to saga:<name> with no matching "
        f"plugins/saga/agents/<name>.md: {sorted(dangling)}"
    )


def test_synthetic_dangling_spawn_reference_is_flagged() -> None:
    """Negative case: exercises the SAME _dangling_references decision the positive test uses,
    so a regression that always returns an empty dangling set would fail this test too."""
    known_names = {p.stem for p in _saga_agent_files()}
    synthetic = 'subagent_type: "saga:readonly-verifier-typo"'
    referenced = _spawn_context_agent_names(synthetic)
    assert _dangling_references(referenced, known_names) == {"readonly-verifier-typo"}


def test_skill_namespace_mention_is_not_flagged() -> None:
    """Regression case: a skill mention like /saga:work must NOT match the spawn-context
    pattern — skills share the saga: namespace with agents, and this guard must only catch
    actual subagent_type/agentType spawn sites, not prose references to skills."""
    prose = "Use `/saga:work 325` after `/saga:plan` settles the plan, per saga:plan's SKILL.md."
    assert _spawn_context_agent_names(prose) == set()


# ---------------------------------------------------------------------------
# (d) The #325 fallback ladder is documented
# ---------------------------------------------------------------------------


def test_fallback_section_documented_in_sandbox_spawn_sites() -> None:
    assert SANDBOX_SPAWN_SITES_PATH.exists(), f"Reference doc missing: {SANDBOX_SPAWN_SITES_PATH}"
    text = SANDBOX_SPAWN_SITES_PATH.read_text()
    assert "Fallback when `saga:readonly-verifier` is unavailable" in text, (
        f"{SANDBOX_SPAWN_SITES_PATH} is missing the #325 fallback ladder section heading."
    )
    assert "Explore" in text, "the fallback ladder must name the Explore agent as its first rung"
    assert "general-purpose" in text, (
        "the fallback ladder must name general-purpose as its terminal rung"
    )


def test_claude_md_points_to_fallback_section() -> None:
    assert CLAUDE_MD_PATH.exists(), f"CLAUDE.md missing: {CLAUDE_MD_PATH}"
    text = CLAUDE_MD_PATH.read_text()
    assert "saga:readonly-verifier" in text, "CLAUDE.md must still carry the ad-hoc spawn rule"
    assert "fallback" in text.lower(), (
        "CLAUDE.md must carry a pointer to the sandbox-spawn-sites.md fallback ladder "
        "(single-sourced there, per #325 Key Technical Decision 3)"
    )
