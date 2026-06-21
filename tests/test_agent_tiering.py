"""Tests for U2: callable ecosystem agent model pinning (R1, R2a).

Asserts that the 4 callable ecosystem agents carry the expected `model:` value in
their YAML frontmatter and that the redis-channel-coach is recorded as exempt (KTD7).
"""

from __future__ import annotations

import pathlib
import re
from typing import NamedTuple

import pytest

PLUGINS_ROOT = pathlib.Path(__file__).parent.parent / "plugins"


def _parse_frontmatter(path: pathlib.Path) -> dict[str, str]:
    """Extract YAML frontmatter key/value pairs from an agent .md file.

    Returns a dict of top-level scalar fields only (no multi-line / block values).
    Returns an empty dict if no frontmatter block is found.
    """
    text = path.read_text()
    if not text.startswith("---"):
        return {}
    # Extract the block between the first --- and second ---
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    block = text[3:end]
    result: dict[str, str] = {}
    for line in block.splitlines():
        # Match top-level key: value lines (not indented block content)
        m = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*):\s*(.*)", line)
        if m:
            result[m.group(1)] = m.group(2).strip().strip('"')
    return result


class AgentSpec(NamedTuple):
    plugin: str
    agent_file: str
    expected_model: str


# The 4 callable ecosystem agents and their required model tier (R1, R2a).
PINNED_AGENTS: list[AgentSpec] = [
    AgentSpec("home-lab-ops", "homelab-sre.md", "opus"),
    AgentSpec("mission-control", "sdlc-operator.md", "sonnet"),
    AgentSpec("unifi", "unifi-network-ops.md", "sonnet"),
    AgentSpec("deploy", "release-orchestrator.md", "sonnet"),
]


@pytest.mark.parametrize("spec", PINNED_AGENTS, ids=[s.agent_file for s in PINNED_AGENTS])
def test_agent_model_pin(spec: AgentSpec) -> None:
    """Each callable ecosystem agent must carry model: <expected> in its frontmatter."""
    path = PLUGINS_ROOT / spec.plugin / "agents" / spec.agent_file
    assert path.exists(), f"Agent file missing: {path}"
    fm = _parse_frontmatter(path)
    assert "model" in fm, (
        f"{spec.plugin}/{spec.agent_file} has no `model:` field in frontmatter — "
        f"add `model: {spec.expected_model}` to the YAML block."
    )
    assert fm["model"] == spec.expected_model, (
        f"{spec.plugin}/{spec.agent_file}: expected `model: {spec.expected_model}`, "
        f"got `model: {fm['model']}`."
    )


def test_redis_channel_coach_exempt() -> None:
    """redis-channel/redis-channel-coach is documented exempt from model pinning (KTD7).

    The coach is a reference pointer, not a dispatched subagent — pinning model: on it
    is inert. The exemption is recorded via tiering_exempt in frontmatter so it is
    machine-verifiable rather than a comment in a doc.
    """
    path = PLUGINS_ROOT / "redis-channel" / "agents" / "redis-channel-coach.md"
    assert path.exists(), f"Coach file missing: {path}"
    fm = _parse_frontmatter(path)

    # The coach must NOT have an active model: pin (it is exempt).
    assert "model" not in fm, (
        "redis-channel-coach unexpectedly carries a `model:` pin. "
        "If this agent has become callable, remove the tiering_exempt field and add it "
        "to PINNED_AGENTS in this test instead."
    )

    # The exemption must be explicitly documented.
    assert "tiering_exempt" in fm, (
        "redis-channel-coach is missing the `tiering_exempt` field. "
        'Add `tiering_exempt: "KTD7 — reference pointer, not a dispatched subagent; '
        'model: pin is inert here"` to the frontmatter to record the exemption.'
    )
    assert "KTD7" in fm["tiering_exempt"], (
        "tiering_exempt field must reference KTD7 to link the exemption to its rationale."
    )
