"""Oracle tests for Saga execution-spec external-engine routing (U5)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parent.parent
SCRIPT_DIR = ROOT / "plugins" / "saga" / "scripts"
EXECUTION_SPEC_SCRIPT = SCRIPT_DIR / "execution_spec.py"
LIFECYCLE_STATE_SCRIPT = SCRIPT_DIR / "lifecycle_state.py"


def _load(name: str, path: Path) -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ES = _load("execution_spec", EXECUTION_SPEC_SCRIPT)
_load("lifecycle_state", LIFECYCLE_STATE_SCRIPT)


def _spec_dict(**unit_overrides: object) -> dict[str, object]:
    unit: dict[str, object] = {
        "unit_id": "U1",
        "label": "external draft",
        "tier": {"model": "sonnet", "effort": "high"},
        "prompt": "draft a bounded implementation diff",
        "returns": ["diff", "assumptions"],
    }
    unit.update(unit_overrides)
    return {
        "name": "external-engine-demo",
        "description": "exercise external-engine unit selectors",
        "repo": "/tmp/repo",
        "units": [unit],
    }


def test_engine_unit_validates_and_emits_external_engine_marker() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict(engine="codex/gpt-5.5-xhigh"))
    spec.validate()

    script = ES.emit_workflow_script(spec)

    assert "// external-engine dispatch: engine=codex/gpt-5.5-xhigh" in script
    assert 'dispatch: "external-engine"' in script
    assert 'engine: "codex/gpt-5.5-xhigh"' in script


def test_unknown_engine_variant_fails() -> None:
    with pytest.raises(ES.SpecError, match="unknown engine variant"):
        ES.ExecutionSpec.from_dict(_spec_dict(engine="codex/nonexistent"))


def test_unknown_capability_fails() -> None:
    with pytest.raises(ES.SpecError, match="unknown capability"):
        ES.ExecutionSpec.from_dict(_spec_dict(capability="telepathy"))


def test_engine_and_capability_are_mutually_exclusive() -> None:
    with pytest.raises(ES.SpecError, match="mutually exclusive"):
        ES.ExecutionSpec.from_dict(
            _spec_dict(engine="codex/gpt-5.5-xhigh", capability="code-generation")
        )


def test_existing_style_unit_has_no_external_engine_marker() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict())
    spec.validate()

    script = ES.emit_workflow_script(spec)

    assert "external-engine dispatch" not in script
    assert 'model: "sonnet"' in script
    assert 'effort: "high"' in script


def test_engine_intent_without_selector_fails() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict(engine_intent="offload"))
    with pytest.raises(ES.SpecError, match="engine_intent requires engine or capability"):
        spec.validate()


def test_engine_intent_bad_vocabulary_fails() -> None:
    spec = ES.ExecutionSpec.from_dict(
        _spec_dict(engine="codex/gpt-5.5-xhigh", engine_intent="urgent")
    )
    # "not in" pins the vocabulary-check branch specifically -- the bare substring
    # "engine_intent" also appears in the sibling "requires engine or capability"
    # error, so that weaker match wouldn't prove this branch actually fired.
    with pytest.raises(ES.SpecError, match="not in"):
        spec.validate()


def test_engine_intent_bad_vocabulary_fails_for_capability_selector() -> None:
    spec = ES.ExecutionSpec.from_dict(
        _spec_dict(capability="code-generation", engine_intent="urgent")
    )
    with pytest.raises(ES.SpecError, match="not in"):
        spec.validate()


def test_engine_and_capability_mutual_exclusion_fires_before_intent_vocabulary() -> None:
    """A unit with both a conflicting selector pair AND an invalid intent must surface
    the selector mutual-exclusion error, proving that check runs first (from_dict calls
    _validate_external_engine_selector before resolving/validating engine_intent)."""
    with pytest.raises(ES.SpecError, match="mutually exclusive"):
        ES.ExecutionSpec.from_dict(
            _spec_dict(
                engine="codex/gpt-5.5-xhigh",
                capability="code-generation",
                engine_intent="urgent",
            )
        )


def test_engine_intent_defaults_to_offload_when_omitted() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict(capability="code-generation"))
    spec.validate()

    assert spec.units[0].engine_intent == "offload"


def test_engine_intent_defaults_to_offload_when_omitted_for_engine_selector() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict(engine="codex/gpt-5.5-xhigh"))
    spec.validate()

    assert spec.units[0].engine_intent == "offload"


def test_engine_intent_explicit_value_round_trips() -> None:
    spec = ES.ExecutionSpec.from_dict(
        _spec_dict(engine="codex/gpt-5.5-xhigh", engine_intent="second-opinion")
    )
    spec.validate()

    round_tripped = ES.ExecutionSpec.from_dict(spec.to_dict())
    assert round_tripped.units[0].engine_intent == "second-opinion"


def test_engine_intent_omitted_from_to_dict_for_plain_claude_unit() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict())
    assert "engine_intent" not in spec.units[0].to_dict()


def test_advisory_consensus_routes_to_ultracode_backend() -> None:
    from lifecycle_state import recommend_execution_backend

    result = recommend_execution_backend(needs_consensus=True, consensus_is_gated=False)

    assert result["recommended"] == "cc-workflows-ultracode"


def test_recommend_backend_no_ledger_has_no_prior_key() -> None:
    # #401 U5: byte-identical to today when no ledger is passed (the common path).
    from lifecycle_state import recommend_execution_backend

    result = recommend_execution_backend(needs_consensus=True, consensus_is_gated=False)
    assert "prior" not in result


def test_recommend_backend_empty_ledger_is_the_no_data_fallback(tmp_path: Path) -> None:
    import run_ledger
    from lifecycle_state import recommend_execution_backend

    ledger = run_ledger.RunLedger(path=tmp_path / "run-facts.jsonl")
    result = recommend_execution_backend(ledger=ledger)
    assert "prior" not in result  # no data -> no prior key (recommendation unchanged)


def test_recommend_backend_surfaces_ledger_prior(tmp_path: Path) -> None:
    import run_ledger
    from lifecycle_state import recommend_execution_backend

    ledger = run_ledger.RunLedger(path=tmp_path / "run-facts.jsonl")
    for tok in (100, 300):
        run_ledger.append_fact(
            ledger,
            run_ledger.build_fact(
                "spend", subplot_id="s", at="t", tokens=tok, tokens_cached=0, tokens_fresh=tok
            ),
        )
    result = recommend_execution_backend(ledger=ledger, prior_n=5)
    assert result["prior"] == {"metric": "spend.tokens", "n": 5, "avg_tokens": 200.0}


# --------------------------------------------------------------------------- sandbox (U1)
# The two-axis capability envelope (#287 R1-R3): mutation_policy x workspace_isolation, with
# named profile shorthand. Absent => ambient x read-write (today's behavior, no new key).


def test_sandbox_profile_string_expands_to_axis_pair() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict(sandbox="read-only-verify"))
    spec.validate()
    sb = spec.units[0].sandbox
    assert sb is not None
    assert sb.mutation_policy == "read-only"
    assert sb.workspace_isolation == "disposable-worktree"
    assert sb.is_restrictive


def test_sandbox_sandboxed_mutate_profile_expands() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict(sandbox="sandboxed-mutate"))
    spec.validate()
    sb = spec.units[0].sandbox
    assert (sb.mutation_policy, sb.workspace_isolation) == ("read-write", "owned-worktree")


def test_sandbox_explicit_axes_accepted() -> None:
    spec = ES.ExecutionSpec.from_dict(
        _spec_dict(sandbox={"mutation_policy": "read-only", "workspace_isolation": "ambient"})
    )
    spec.validate()
    sb = spec.units[0].sandbox
    assert sb.mutation_policy == "read-only" and sb.workspace_isolation == "ambient"
    # read-only alone (isolation ambient) still narrows a policy => restrictive.
    assert sb.is_restrictive


def test_sandbox_default_ambient_readwrite_is_not_restrictive() -> None:
    sb = ES.Sandbox(mutation_policy="read-write", workspace_isolation="ambient")
    assert not sb.is_restrictive


def test_sandbox_absent_defaults_to_none_with_no_key() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict())
    unit = spec.units[0]
    assert unit.sandbox is None
    assert "sandbox" not in unit.to_dict()


def test_sandbox_to_dict_emits_expanded_axes_not_shorthand() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict(sandbox="read-only-verify"))
    emitted = spec.units[0].to_dict()["sandbox"]
    assert emitted == {
        "mutation_policy": "read-only",
        "workspace_isolation": "disposable-worktree",
    }
    # Round-trip is idempotent: the expanded form reparses to the same axes.
    again = ES.ExecutionSpec.from_dict(spec.to_dict())
    assert again.units[0].sandbox == spec.units[0].sandbox


def test_sandbox_unknown_profile_raises() -> None:
    with pytest.raises(ES.SpecError, match="unknown sandbox profile"):
        ES.ExecutionSpec.from_dict(_spec_dict(sandbox="airtight"))


def test_sandbox_unknown_axis_value_raises() -> None:
    spec = ES.ExecutionSpec.from_dict(
        _spec_dict(sandbox={"mutation_policy": "write-anywhere", "workspace_isolation": "ambient"})
    )
    with pytest.raises(ES.SpecError, match="mutation_policy 'write-anywhere' not in"):
        spec.validate()


def test_sandbox_profile_key_conflicts_with_explicit_axes() -> None:
    with pytest.raises(ES.SpecError, match="conflicts with the explicit-axes form"):
        ES.ExecutionSpec.from_dict(
            _spec_dict(
                sandbox={
                    "profile": "read-only-verify",
                    "mutation_policy": "read-only",
                    "workspace_isolation": "disposable-worktree",
                }
            )
        )


def test_sandbox_coexists_with_engine_selector_without_interference() -> None:
    spec = ES.ExecutionSpec.from_dict(
        _spec_dict(capability="code-generation", sandbox="sandboxed-mutate")
    )
    spec.validate()
    unit = spec.units[0]
    assert unit.capability == "code-generation"
    assert unit.engine_intent == "offload"  # selector default still applies
    assert unit.sandbox.workspace_isolation == "owned-worktree"
    # Both round-trip together, neither field perturbs the other.
    again = ES.Unit.from_dict(unit.to_dict())
    assert again.capability == "code-generation"
    assert again.sandbox == unit.sandbox


# ------------------------------------------------------ read-only verifier wiring (U2)
# Every verifier agent() call the emitter renders MUST carry agentType + isolation across all
# three emission shapes (plain panel, iterate-to-consensus singleton, parallel-layer thunk).
# Missing any one site is exactly the R9 dead-wiring failure.

AGENTS_DIR = ROOT / "plugins" / "saga" / "agents"
READONLY_VERIFIER_AGENT = AGENTS_DIR / "readonly-verifier.md"


def _frontmatter_scalar(text: str, key: str) -> str:
    """Read one top-level single-line frontmatter scalar (name/model/tools) without a YAML dep.

    Stops at the multi-line ``description: |`` block, which is fine -- the keys this test cares
    about (name, tools) precede it.
    """
    in_fm = False
    for line in text.splitlines():
        if line.strip() == "---":
            if in_fm:
                break
            in_fm = True
            continue
        if in_fm and line.startswith(f"{key}:"):
            return line[len(key) + 1 :].strip()
    raise AssertionError(f"{key!r} not found in frontmatter")


def _emit_units(units: list[dict[str, object]]) -> str:
    spec = ES.ExecutionSpec.from_dict(
        {"name": "verify-demo", "description": "d", "repo": "/tmp/r", "units": units}
    )
    spec.validate()
    return str(ES.emit_workflow_script(spec))


def _verify_unit(uid: str, **kw: object) -> dict[str, object]:
    unit: dict[str, object] = {
        "unit_id": uid,
        "label": uid,
        "tier": {"model": "opus", "effort": "high"},
        "prompt": "do the work",
        "returns": ["result"],
    }
    unit.update(kw)
    return unit


def test_readonly_verifier_agent_definition_exists_with_readonly_toolset() -> None:
    assert READONLY_VERIFIER_AGENT.exists()
    text = READONLY_VERIFIER_AGENT.read_text(encoding="utf-8")
    assert _frontmatter_scalar(text, "name") == "readonly-verifier"
    tools = [t.strip() for t in _frontmatter_scalar(text, "tools").split(",")]
    assert tools == ["Bash", "Read", "Grep", "Glob"]
    # The read-only contract IS tool omission at spawn: Edit/Write must be absent.
    assert "Edit" not in tools and "Write" not in tools


def test_verifier_agenttype_literal_matches_agent_definition_name() -> None:
    # Literal-consistency guard (#287 U2, saga-side half of the registry-drift risk): the
    # agentType string the emitter bakes into every verifier call MUST equal the agent
    # definition's `name:` plus the `saga:` plugin prefix. A rename on either side fails HERE
    # rather than silently spawning verifiers with an unknown (=> unrestricted) agent type.
    text = READONLY_VERIFIER_AGENT.read_text(encoding="utf-8")
    name = _frontmatter_scalar(text, "name")
    assert f"saga:{name}" == ES.READONLY_VERIFIER_AGENT_TYPE
    assert ES.READONLY_VERIFIER_ISOLATION == "worktree"


def test_verifier_panel_emits_readonly_agenttype_and_isolation() -> None:
    script = _emit_units([_verify_unit("a", verify={"n": 2, "pass_rule": "majority"})])
    assert 'agentType: "saga:readonly-verifier"' in script
    assert 'isolation: "worktree"' in script


def test_verifier_iterate_singleton_emits_readonly_agenttype_and_isolation() -> None:
    script = _emit_units(
        [_verify_unit("b", verify={"n": 2, "pass_rule": "majority", "iterate_to_consensus": True})]
    )
    assert 'agentType: "saga:readonly-verifier"' in script
    assert 'isolation: "worktree"' in script
    assert "for (let iter" in script  # proves the singleton loop path, not the plain panel


def test_verifier_parallel_thunk_emits_readonly_agenttype_and_isolation() -> None:
    # Two independent units land in one dependency layer => parallel([...]) of thunks; each
    # thunk with iterate_to_consensus runs its own inline verifier loop (the third site).
    script = _emit_units(
        [
            _verify_unit(
                "c1", verify={"n": 2, "pass_rule": "majority", "iterate_to_consensus": True}
            ),
            _verify_unit(
                "c2", verify={"n": 2, "pass_rule": "majority", "iterate_to_consensus": True}
            ),
        ]
    )
    assert "parallel(" in script
    # Both units' verifier loops carry the opts: 2 units x n=2 verifiers = 4 tagged calls.
    assert script.count('agentType: "saga:readonly-verifier"') == 4
    assert script.count('isolation: "worktree"') == 4


def test_unit_own_agent_call_is_not_verifier_restricted() -> None:
    # A single unit with a 2-verifier panel: agentType appears on the TWO verifier calls only,
    # never on the unit's own agent() call (which keeps the ambient x read-write R1 default).
    script = _emit_units([_verify_unit("a", verify={"n": 2, "pass_rule": "majority"})])
    assert script.count('agentType: "saga:readonly-verifier"') == 2


def test_plain_unit_without_verify_emits_no_verifier_wiring() -> None:
    script = _emit_units([_verify_unit("a")])
    assert "agentType" not in script
    assert "isolation:" not in script


# ---------------------------------------------------------- enforceability matrix (U3)
# unenforceable_sandbox_axis(backend, sandbox) -> the (axis, value) a backend cannot enforce, or
# None. Only NON-default axis values need enforcing; unlisted backends enforce nothing (R4).


@pytest.mark.parametrize(
    "backend,profile,expected",
    [
        ("inline", "read-only-verify", None),
        ("cc-workflows-ultracode", "read-only-verify", None),
        ("inline", "sandboxed-mutate", ("workspace_isolation", "owned-worktree")),
        ("team-execution", "read-only-verify", ("mutation_policy", "read-only")),
        ("fork", "read-only-verify", ("mutation_policy", "read-only")),
        ("subagent", "sandboxed-mutate", ("workspace_isolation", "owned-worktree")),
        ("goal", "read-only-verify", ("mutation_policy", "read-only")),
        ("manual", "read-only-verify", ("mutation_policy", "read-only")),
    ],
)
def test_unenforceable_sandbox_axis_matrix(backend: str, profile: str, expected: object) -> None:
    sb = ES.Sandbox.from_dict(profile, "w")
    assert ES.unenforceable_sandbox_axis(backend, sb) == expected


def test_unenforceable_sandbox_axis_none_and_default_are_enforceable_everywhere() -> None:
    # No sandbox and the ambient x read-write default never trip on any backend (R1).
    default = ES.Sandbox(mutation_policy="read-write", workspace_isolation="ambient")
    for backend in ("inline", "team-execution", "fork", "manual", "goal", "subagent"):
        assert ES.unenforceable_sandbox_axis(backend, None) is None
        assert ES.unenforceable_sandbox_axis(backend, default) is None


def test_unlisted_backend_is_never_permissive() -> None:
    # A future/unknown backend enforces nothing => any restrictive sandbox halts (R4).
    sb = ES.Sandbox.from_dict("read-only-verify", "w")
    assert ES.unenforceable_sandbox_axis("some-future-backend", sb) is not None


# ---------------------------------------------------------- tier enforceability (#369 U1)
# unenforceable_tier(backend, tier) -> the (axis, value) a backend cannot spawn, or None. v1 checks
# the MODEL axis: team-execution spawns by agentType (models {opus,sonnet,haiku}, no fable); unlisted
# backends enforce nothing (R3).


def test_unenforceable_tier_halts_fable_on_team_execution() -> None:
    # fable is unreachable outside saga plan vocabulary; team-execution cannot spawn it -> HALT.
    assert ES.unenforceable_tier("team-execution", ES.Tier("fable", "xhigh")) == ("model", "fable")
    # A reachable model on team-execution is fine (existing specs stay green).
    assert ES.unenforceable_tier("team-execution", ES.Tier("opus", "high")) is None


def test_unenforceable_tier_passes_reachable_model() -> None:
    # The enforcing-backend branch of the issue AC: inline / cc-workflows set the per-call tier and
    # reach the whole palette, so the same fable/xhigh unit passes there.
    for backend in ("inline", "cc-workflows-ultracode"):
        assert ES.unenforceable_tier(backend, ES.Tier("fable", "xhigh")) is None


def test_unenforceable_tier_unknown_backend_never_permissive() -> None:
    # A backend absent from TIER_ENFORCEABLE_BY_BACKEND enforces nothing => any model halts (R3).
    assert ES.unenforceable_tier("some-future-backend", ES.Tier("opus", "high")) == (
        "model",
        "opus",
    )


# ---------------------------------------------------------- Unit.min_tier floor (#369 U2)


def test_min_tier_pulls_cheap_segment_up() -> None:
    # Two units share the plugins/saga segment; the floored one drags the whole resident up to its
    # floor via the same upgrade-only ladder op as the base merge.
    spec = ES.ExecutionSpec.from_dict(
        {
            "name": "floor-demo",
            "description": "d",
            "repo": "/tmp/r",
            "units": [
                {
                    "unit_id": "A",
                    "label": "floored",
                    "tier": {"model": "haiku", "effort": "low"},
                    "prompt": "p",
                    "files": ["plugins/saga/scripts/execution_spec.py"],
                    "min_tier": {"model": "opus", "effort": "high"},
                },
                {
                    "unit_id": "B",
                    "label": "cheap",
                    "tier": {"model": "haiku", "effort": "low"},
                    "prompt": "p",
                    "files": ["plugins/saga/scripts/team_emitter.py"],
                },
            ],
        }
    )
    spec.validate()
    segments = ES.segment_units(spec)
    assert len(segments) == 1
    assert segments[0].tier == ES.Tier(model="opus", effort="high")


def test_off_palette_min_tier_fails_emit() -> None:
    # A floor drawn off the MODELS/EFFORTS palette fails validation with a named error (R5).
    unit = ES.Unit.from_dict(
        {
            "unit_id": "A",
            "label": "a",
            "tier": {"model": "sonnet", "effort": "high"},
            "prompt": "p",
            "min_tier": {"model": "gpt-5", "effort": "high"},
        }
    )
    with pytest.raises(ES.SpecError, match="not in"):
        unit.validate("unit A")


def test_absent_min_tier_round_trips_byte_identical() -> None:
    # A spec with no floor emits no min_tier key and round-trips through to_dict/from_dict unchanged.
    spec = ES.ExecutionSpec.from_dict(_spec_dict())
    first = spec.to_dict()
    assert all("min_tier" not in u for u in first["units"])
    again = ES.ExecutionSpec.from_dict(first).to_dict()
    assert first == again


# ---------------------------------------------------------- session tier ceiling (#365 U2/U3)


def test_tier_ceiling_clamp() -> None:
    # A sonnet/medium ceiling clamps an opus/high tier DOWN on both axes.
    clamped = ES.clamp_tier_to_ceiling(ES.Tier("opus", "high"), ES.Tier("sonnet", "medium"))
    assert clamped == ES.Tier("sonnet", "medium")


def test_tier_ceiling_never_escalates() -> None:
    # A ceiling at or above the tier is a no-op -- a ceiling never RAISES a tier.
    weak = ES.Tier("haiku", "low")
    assert ES.clamp_tier_to_ceiling(weak, ES.Tier("opus", "high")) == weak
    # Mixed: ceiling above on model, below on effort -> only effort clamps down.
    assert ES.clamp_tier_to_ceiling(
        ES.Tier("sonnet", "xhigh"), ES.Tier("opus", "medium")
    ) == ES.Tier("sonnet", "medium")


def test_clamp_tier_to_ceiling_is_always_runnable() -> None:
    # #365 gate P0: even a direct caller passing an unrunnable ceiling Tier (bypassing tier_session)
    # must never yield an unrunnable result -- the clamped effort is pulled to the model's ceiling.
    out = ES.clamp_tier_to_ceiling(ES.Tier("opus", "xhigh"), ES.Tier("haiku", "xhigh"))
    assert out == ES.Tier("haiku", "high")  # not haiku/xhigh (haiku's ceiling is high)
    # And an emit with such a ceiling never renders the unrunnable combo.
    spec = ES.ExecutionSpec.from_dict(_spec_dict(tier={"model": "opus", "effort": "xhigh"}))
    script = ES.emit_workflow_script(spec, session_ceiling=ES.Tier("haiku", "xhigh"))
    assert 'effort: "xhigh"' not in script
    assert 'model: "haiku"' in script and 'effort: "high"' in script


def test_workflow_emit_honors_session_ceiling() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict(tier={"model": "opus", "effort": "high"}))
    # No ceiling -> the authored tier is rendered verbatim.
    plain = ES.emit_workflow_script(spec)
    assert 'model: "opus"' in plain and 'effort: "high"' in plain
    # A sonnet/medium ceiling clamps the emitted tier and logs the downgrade.
    clamped = ES.emit_workflow_script(spec, session_ceiling=ES.Tier("sonnet", "medium"))
    assert 'model: "sonnet"' in clamped and 'effort: "medium"' in clamped
    assert 'model: "opus"' not in clamped
    assert "SESSION TIER CEILING" in clamped and "U1" in clamped


# ---------------------------------------------------------- mid-run patch (#365 U4)


def _two_unit_spec() -> dict[str, object]:
    return {
        "name": "patch-demo",
        "description": "d",
        "repo": "/tmp/r",
        "units": [
            {
                "unit_id": "A",
                "label": "a",
                "tier": {"model": "haiku", "effort": "low"},
                "prompt": "p",
            },
            {
                "unit_id": "B",
                "label": "b",
                "tier": {"model": "haiku", "effort": "low"},
                "prompt": "p",
            },
        ],
    }


def test_tier_patch_unrun_only() -> None:
    spec = ES.ExecutionSpec.from_dict(_two_unit_spec())
    overrides = {"A": ES.Tier("opus", "high"), "B": ES.Tier("opus", "high")}
    patched = ES.patch_spec_tiers(spec, overrides, already_run_ids=["A"])
    by_id = {u.unit_id: u.tier for u in patched.units}
    assert by_id["A"] == ES.Tier("haiku", "low")  # already-run -> untouched
    assert by_id["B"] == ES.Tier("opus", "high")  # not-yet-run -> patched


def test_tier_patch_validate_gate() -> None:
    # A patch producing an unrunnable tier (haiku/xhigh) fails validation before any emit (R5).
    spec = ES.ExecutionSpec.from_dict(_spec_dict())
    patched = ES.patch_spec_tiers(spec, {"U1": ES.Tier("haiku", "xhigh")}, already_run_ids=[])
    with pytest.raises(ES.SpecError):
        patched.validate()


def test_tier_patch_reemit() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict(tier={"model": "haiku", "effort": "low"}))
    patched = ES.patch_spec_tiers(spec, {"U1": ES.Tier("opus", "high")}, already_run_ids=[])
    patched.validate()
    script = ES.emit_workflow_script(patched)
    assert 'model: "opus"' in script and 'effort: "high"' in script


def test_tier_patch_spend_delta_gate() -> None:
    # Up-ladder on either axis is an escalation (confirm required); cheapen/lateral is not.
    assert (
        ES.is_escalation(ES.Tier("sonnet", "medium"), ES.Tier("opus", "medium")) is True
    )  # model up
    assert (
        ES.is_escalation(ES.Tier("sonnet", "medium"), ES.Tier("sonnet", "high")) is True
    )  # effort up
    assert (
        ES.is_escalation(ES.Tier("opus", "high"), ES.Tier("sonnet", "medium")) is False
    )  # cheapen
    assert (
        ES.is_escalation(ES.Tier("sonnet", "medium"), ES.Tier("sonnet", "medium")) is False
    )  # lateral
