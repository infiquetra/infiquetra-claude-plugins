"""Tests for U14: cheap-tier mechanical executor agent (R16).

Asserts:
- The agent file exists at the expected path.
- Frontmatter pins model: haiku (cheap tier, R1).
- Frontmatter pins tools: Bash (Bash-only scope, R16).
- The approved op list is declared and complete (census, file-exist, json-validate,
  grep-count, link-check).
- The op-discrimination rejection contract is documented (unknown op → rejected, not guessed).
- The agent body carries the inert-until-called guarantee (no auto-trigger).
"""

from __future__ import annotations

import pathlib
import re

import pytest

PLUGINS_ROOT = pathlib.Path(__file__).parent.parent / "plugins"
AGENT_PATH = PLUGINS_ROOT / "saga" / "agents" / "mechanical-executor.md"

APPROVED_OPS = {"census", "file-exist", "json-validate", "grep-count", "link-check"}

# Judgment / authoring tools that the agent must NOT list in its tools: field.
NON_BASH_TOOLS = {"Read", "Edit", "Write", "Glob", "Grep", "WebFetch", "WebSearch"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_frontmatter(path: pathlib.Path) -> dict[str, str]:
    """Extract YAML frontmatter key/value pairs from the agent .md file.

    Returns top-level scalar fields only.  Returns an empty dict when no
    frontmatter block is found.
    """
    text = path.read_text()
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    block = text[3:end]
    result: dict[str, str] = {}
    for line in block.splitlines():
        m = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*):\s*(.*)", line)
        if m:
            result[m.group(1)] = m.group(2).strip().strip('"')
    return result


def _agent_body(path: pathlib.Path) -> str:
    """Return the body of the agent file (everything after the frontmatter block)."""
    text = path.read_text()
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    if end == -1:
        return text
    return text[end + 4 :]  # skip past the closing '---\n'


# ---------------------------------------------------------------------------
# Existence
# ---------------------------------------------------------------------------


def test_agent_file_exists() -> None:
    """The mechanical-executor agent file must exist at the canonical path."""
    assert AGENT_PATH.exists(), (
        f"mechanical-executor agent missing at {AGENT_PATH}. "
        "Create plugins/saga/agents/mechanical-executor.md."
    )


# ---------------------------------------------------------------------------
# Frontmatter: model tier
# ---------------------------------------------------------------------------


def test_frontmatter_model_is_haiku() -> None:
    """model: must be haiku — the cheap tier (R1, R16)."""
    fm = _parse_frontmatter(AGENT_PATH)
    assert "model" in fm, (
        "mechanical-executor.md has no `model:` field in frontmatter. Add `model: haiku`."
    )
    assert fm["model"] == "haiku", (
        f"mechanical-executor model is `{fm['model']}`, expected `haiku`. "
        "This agent must run on the cheap tier (R1, R16)."
    )


# ---------------------------------------------------------------------------
# Frontmatter: tool scope (Bash-only)
# ---------------------------------------------------------------------------


def test_frontmatter_tools_is_bash_only() -> None:
    """tools: must be `Bash` (Bash-only scope, R16).

    The field may be a single value `Bash` or a comma/space-separated list
    that reduces to just `Bash`.  No non-Bash tools (Read, Edit, Write, Glob,
    Grep, WebFetch, WebSearch, …) are permitted.
    """
    fm = _parse_frontmatter(AGENT_PATH)
    assert "tools" in fm, (
        "mechanical-executor.md has no `tools:` field in frontmatter. "
        "Add `tools: Bash` to enforce the Bash-only scope."
    )
    raw_tools = fm["tools"]
    # Normalise: split on commas/spaces, lowercase, strip
    tool_names = {t.strip() for t in re.split(r"[,\s]+", raw_tools) if t.strip()}
    assert tool_names == {"Bash"}, (
        f"mechanical-executor tools field lists {tool_names!r}; expected exactly {{'Bash'}}. "
        "This agent is Bash-only (R16) — remove all non-Bash tool entries."
    )


@pytest.mark.parametrize("forbidden_tool", sorted(NON_BASH_TOOLS))
def test_tools_field_excludes_non_bash_tools(forbidden_tool: str) -> None:
    """Each non-Bash tool must NOT appear in the tools: field."""
    fm = _parse_frontmatter(AGENT_PATH)
    raw_tools = fm.get("tools", "")
    tool_names = {t.strip() for t in re.split(r"[,\s]+", raw_tools) if t.strip()}
    assert forbidden_tool not in tool_names, (
        f"mechanical-executor lists `{forbidden_tool}` in its tools: field. "
        "Only `Bash` is permitted (R16)."
    )


# ---------------------------------------------------------------------------
# Op-discrimination: approved op list
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("op", sorted(APPROVED_OPS))
def test_approved_op_documented_in_body(op: str) -> None:
    """Every approved op must be documented in the agent body."""
    body = _agent_body(AGENT_PATH)
    assert op in body, (
        f"Approved op `{op}` is not documented in mechanical-executor.md body. "
        "Add a section describing its input fields and output format."
    )


def test_all_approved_ops_listed_together() -> None:
    """The agent body must name all approved ops together in the rejection contract.

    This ensures the error message a caller receives on an unknown op is complete —
    listing only some ops would be a misleading contract.
    """
    body = _agent_body(AGENT_PATH)
    # The ops should appear together in an enumeration (the rejection block)
    for op in APPROVED_OPS:
        assert op in body, (
            f"Op `{op}` absent from mechanical-executor.md body. "
            "All approved ops must be listed in the rejection/contract section."
        )


# ---------------------------------------------------------------------------
# Op-discrimination: unknown op rejection
# ---------------------------------------------------------------------------


def test_unknown_op_rejection_documented() -> None:
    """The agent body must document that unknown ops are rejected (not guessed).

    This is the op-discrimination contract (R16): an unknown op produces a
    deterministic ERROR output, never a best-guess action.
    """
    body = _agent_body(AGENT_PATH)
    # The body must mention rejection / error for unknown ops
    assert "unknown op" in body.lower(), (
        "mechanical-executor.md does not document the unknown-op rejection contract. "
        "Add language stating that unknown ops produce an ERROR and are never guessed."
    )


def test_rejection_does_not_guess() -> None:
    """The rejection contract must say the op is rejected, not guessed."""
    body = _agent_body(AGENT_PATH)
    body_lower = body.lower()
    # Must say "reject" OR "not guess" / "never guess"
    assert "reject" in body_lower or "never guess" in body_lower or "not guess" in body_lower, (
        "mechanical-executor.md must state that unknown ops are rejected, not guessed. "
        "Add explicit language: 'rejected, not guessed' or 'never guess'."
    )


# ---------------------------------------------------------------------------
# Inert-until-called guarantee
# ---------------------------------------------------------------------------


def test_inert_until_called_documented() -> None:
    """The agent body must assert it is inert until called (no auto-trigger, R16)."""
    body = _agent_body(AGENT_PATH)
    body_lower = body.lower()
    assert "inert" in body_lower, (
        "mechanical-executor.md does not mention being inert until called. "
        "Add language stating the agent has no auto-trigger and takes no action "
        "without an explicit dispatch from the calling skill."
    )


def test_no_auto_trigger_in_description() -> None:
    """The frontmatter description must not describe auto-trigger conditions.

    Agents with trigger conditions can be auto-activated by the harness; this agent
    must only run when explicitly dispatched.  The description may use words like
    'Dispatched explicitly' but should not define trigger phrases.
    """
    fm = _parse_frontmatter(AGENT_PATH)
    desc = fm.get("description", "")
    # Forbidden: trigger phrases that auto-activate the agent
    forbidden_patterns = [
        r"triggers on",
        r"trigger when",
        r"activate when",
        r"auto.trigger",
    ]
    for pattern in forbidden_patterns:
        assert not re.search(pattern, desc, re.IGNORECASE), (
            f"mechanical-executor frontmatter description contains a trigger pattern "
            f"({pattern!r}) — this agent must be inert until explicitly dispatched."
        )


# ---------------------------------------------------------------------------
# Dispatch wiring present in work/references/execution-strategy.md
# ---------------------------------------------------------------------------


def test_dispatch_wiring_references_mechanical_executor() -> None:
    """execution-strategy.md must mention the mechanical-executor dispatch contract.

    This is the saga-skill-level wiring: the reference doc that /work consults for
    subagent dispatch must instruct callers to route mechanical ops to this agent.
    """
    strategy_path = (
        PLUGINS_ROOT / "saga" / "skills" / "work" / "references" / "execution-strategy.md"
    )
    assert strategy_path.exists(), f"execution-strategy.md not found at {strategy_path}"
    body = strategy_path.read_text()
    assert "mechanical-executor" in body, (
        "execution-strategy.md does not reference the mechanical-executor agent. "
        "Add a dispatch paragraph directing callers to use this agent for mechanical ops."
    )


def test_dispatch_wiring_names_bash_only_scope() -> None:
    """execution-strategy.md dispatch paragraph must name the Bash-only scope."""
    strategy_path = (
        PLUGINS_ROOT / "saga" / "skills" / "work" / "references" / "execution-strategy.md"
    )
    body = strategy_path.read_text()
    # The wiring section must describe the Bash-only constraint so callers know
    # not to pass non-Bash tasks to this agent.
    assert "bash" in body.lower(), (
        "execution-strategy.md dispatch paragraph does not mention Bash-only scope. "
        "Add language clarifying this agent is Bash-only."
    )


def test_dispatch_wiring_names_op_rejection() -> None:
    """execution-strategy.md dispatch paragraph must mention op-discrimination."""
    strategy_path = (
        PLUGINS_ROOT / "saga" / "skills" / "work" / "references" / "execution-strategy.md"
    )
    body = strategy_path.read_text()
    body_lower = body.lower()
    assert "op" in body_lower and ("reject" in body_lower or "discriminat" in body_lower), (
        "execution-strategy.md does not mention op-discrimination. "
        "Add a note that the mechanical-executor rejects unknown ops."
    )
