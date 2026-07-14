"""Tests for U2: callable ecosystem agent model pinning (R1, R2a).

Asserts that the 4 callable ecosystem agents carry the expected `model:` value in
their YAML frontmatter and that the redis-channel-coach is recorded as exempt (KTD7).
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
from typing import NamedTuple

import pytest

PLUGINS_ROOT = pathlib.Path(__file__).parent.parent / "plugins"

# #422: the frontmatter parser is shared (tools/ is not an importable package, so we load it
# the same way tests/test_release_rituals.py loads other tools/*.py modules).
_AGENT_SPEC_PATH = pathlib.Path(__file__).parent.parent / "tools" / "agent_spec.py"
_spec = importlib.util.spec_from_file_location("agent_spec", _AGENT_SPEC_PATH)
assert _spec is not None and _spec.loader is not None, f"Cannot load {_AGENT_SPEC_PATH}"
_agent_spec = importlib.util.module_from_spec(_spec)
# dataclasses.dataclass() looks its defining module up in sys.modules by name; register
# before exec so tools/agent_spec.py's frozen dataclasses build cleanly.
sys.modules[_spec.name] = _agent_spec
_spec.loader.exec_module(_agent_spec)

_parse_frontmatter = _agent_spec.parse_frontmatter_file


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
