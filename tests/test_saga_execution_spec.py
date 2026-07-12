"""Oracle tests for Saga execution-spec external-engine routing (U5)."""

from __future__ import annotations

import importlib.util
import json
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


@pytest.mark.parametrize(
    "selector",
    [
        {"engine": "codex/gpt-5.5-xhigh"},
        {"capability": "code-generation"},
    ],
    ids=("engine", "capability"),
)
def test_divergence_intent_selector_forms_validate_and_round_trip(
    selector: dict[str, str],
) -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict(**selector, engine_intent="divergence"))
    spec.validate()

    unit_dict = spec.units[0].to_dict()
    assert unit_dict["engine_intent"] == "divergence"
    assert ES.ExecutionSpec.from_dict(spec.to_dict()).units[0].engine_intent == "divergence"


def test_engine_intent_omitted_from_to_dict_for_plain_claude_unit() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict())
    assert "engine_intent" not in spec.units[0].to_dict()


def test_advisory_panel_request_is_separate_from_verify_and_round_trips() -> None:
    request = ES.AdvisoryPanelRequest.from_dict(
        {"role": "cross-family-review-panel"},
        "advisory panel",
    )

    assert request == ES.AdvisoryPanelRequest("cross-family-review-panel")
    assert request.to_dict() == {"role": "cross-family-review-panel"}
    assert not hasattr(request, "n")
    assert ES.PANEL_N_CAP == ES._engine_registry_module().PANEL_N_CAP


def test_advisory_panel_rejects_malformed_role_name() -> None:
    with pytest.raises(ES.SpecError, match="normalized kebab-case"):
        ES.AdvisoryPanelRequest.from_dict({"role": "Bad Role"}, "advisory panel")


def test_advisory_panel_rejects_over_cap_role_at_spec_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_module = ES._engine_registry_module()
    registry = registry_module.Registry.load(ES._engine_registry_path())
    role = registry.by_role("cross-family-review-panel")
    role.members[:] = [role.members[0]] * (ES.PANEL_N_CAP + 1)
    monkeypatch.setattr(
        registry_module.Registry,
        "load",
        classmethod(lambda _cls, _path: registry),
    )

    with pytest.raises(ES.SpecError, match="PANEL_N_CAP"):
        ES.AdvisoryPanelRequest("cross-family-review-panel").validate("unit U1")


def test_engine_verifiability_round_trips_and_emits_external_engine_option() -> None:
    spec = ES.ExecutionSpec.from_dict(
        _spec_dict(engine="codex/gpt-5.5-xhigh", verifiability="test-gated")
    )
    spec.validate()

    unit_dict = spec.units[0].to_dict()
    script = ES.emit_workflow_script(spec)

    assert unit_dict["verifiability"] == "test-gated"
    assert "verifiability=test-gated" in script
    assert 'verifiability: "test-gated"' in script


def test_absent_verifiability_emits_no_key_for_external_engine_unit() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict(engine="codex/gpt-5.5-xhigh"))
    spec.validate()

    assert "verifiability" not in spec.units[0].to_dict()


def test_engine_verifiability_bad_vocabulary_fails() -> None:
    spec = ES.ExecutionSpec.from_dict(
        _spec_dict(engine="codex/gpt-5.5-xhigh", verifiability="maybe")
    )
    with pytest.raises(ES.SpecError, match="verifiability .* not in"):
        spec.validate()


def test_verifiability_without_external_selector_fails() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict(verifiability="test-gated"))
    with pytest.raises(ES.SpecError, match="verifiability requires engine or capability"):
        spec.validate()


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


def _return_schema_fragment(keys: tuple[str, ...] = ("result",), *, cheap: bool = False) -> str:
    return_schema: dict[str, object] = {
        "type": "object",
        "properties": {key: {} for key in keys},
        "required": list(keys),
        "additionalProperties": True,
    }
    if cheap:
        # #364 pull-cord shape: a FLAT typed object -- returns keys plus an optional pull_cord
        # string, no required alternation. The API rejects any top-level combinator (oneOf/allOf/
        # anyOf), so the either/or is enforced by __gate + the RETURN CONTRACT, not the schema.
        properties: dict[str, object] = {key: {} for key in keys}
        properties["pull_cord"] = {"type": "string"}
        return_schema = {
            "type": "object",
            "properties": properties,
            "additionalProperties": True,
        }
    return "schema: " + json.dumps(return_schema, sort_keys=True)


def _verifier_schema_fragment() -> str:
    schema: dict[str, object] = {
        "type": "object",
        "properties": {
            "refuted": {"type": "array"},
            "upheld": {"type": "array"},
            "verifier_identity": {"type": "string"},
            "fallback_depth": {},
            "examined_sha": {"type": "string"},
        },
        "required": [
            "refuted",
            "upheld",
            "verifier_identity",
            "fallback_depth",
            "examined_sha",
        ],
        "additionalProperties": True,
    }
    return "schema: " + json.dumps(schema, sort_keys=True)


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
    assert script.count(_verifier_schema_fragment()) == 2
    assert "__verifierPrompt(" in script
    assert "UNIT RESULT INPUT (authoritative structured evidence)" in script
    assert "status --short" in script
    assert "named untracked output files" in script


def test_verifier_panel_stamps_identity_and_fallback_schema_fields() -> None:
    # U6/R8/KTD7: the emitted verifier prompt carries the emitter-stamped identity and instructs
    # the verifier to echo verifier_identity + fallback_depth (default 0). A workflow agent() call
    # can only ever be the first-choice rung, so the stamped depth is 0.
    script = _emit_units([_verify_unit("a", verify={"n": 2, "pass_rule": "majority"})])
    assert "verifier_identity" in script
    assert "fallback_depth" in script
    assert "examined_sha" in script
    # Stamped identity == the readonly-verifier agent type the emitter knows.
    assert "verifier_identity: saga:readonly-verifier" in script
    assert "fallback_depth: 0" in script
    assert "Include examined_sha as the git SHA you" in script


def test_verifier_panel_emits_fallback_tier_marker_in_throw() -> None:
    # The runtime gate summary computes a "fallback tier" marker over the reporting verdicts and
    # rides it on the operator-facing verifier-disagreement throw.
    script = _emit_units([_verify_unit("a", verify={"n": 2, "pass_rule": "majority"})])
    assert "fallback tier" in script
    assert "fallback_marker" in script
    assert "verifier-disagreement" in script


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


def test_unit_agent_call_emits_return_schema() -> None:
    script = _emit_units([_verify_unit("a")])
    assert _return_schema_fragment() in script
    assert "schema:" in script.split("const a = await agent(", 1)[1].split("__gate(a", 1)[0]


def test_external_engine_unit_emits_return_schema() -> None:
    script = _emit_units([_verify_unit("ext", capability="code-generation")])
    assert 'dispatch: "external-engine"' in script
    assert 'capability: "code-generation"' in script
    assert _return_schema_fragment() in script


def test_parallel_thunks_emit_return_schema_for_each_unit() -> None:
    script = _emit_units([_verify_unit("a"), _verify_unit("b")])
    assert "parallel([" in script
    assert script.count(_return_schema_fragment()) == 2


def test_iterate_to_consensus_unit_emits_return_schema() -> None:
    script = _emit_units(
        [_verify_unit("i", verify={"n": 2, "pass_rule": "majority", "iterate_to_consensus": True})]
    )
    assert "for (let iter" in script
    assert _return_schema_fragment() in script


def test_cheap_tier_schema_preserves_pull_cord_alternative() -> None:
    script = _emit_units([_verify_unit("cheap", tier={"model": "haiku", "effort": "low"})])
    assert _return_schema_fragment(cheap=True) in script
    assert "pull_cord" in script


def _extract_agent_schemas(script: str) -> list[dict[str, object]]:
    """Parse every ``schema: {...}`` JSON blob out of an emitted workflow script."""
    decoder = json.JSONDecoder()
    marker = "schema: "
    schemas: list[dict[str, object]] = []
    start = script.find(marker)
    while start != -1:
        obj, _ = decoder.raw_decode(script, start + len(marker))
        assert isinstance(obj, dict)
        schemas.append(obj)
        start = script.find(marker, start + len(marker))
    return schemas


def test_every_emitted_agent_schema_has_toplevel_type() -> None:
    # Regression for the pull-cord schema dispatch failure (#364, reproduced 2026-07-10 in
    # team-norns run wf_758c9923-c2c). The Anthropic API rejects a tool input_schema on TWO
    # counts, checked in sequence: first if it lacks a top-level "type"
    # (400 tools.N.custom.input_schema.type: Field required), then if it carries ANY top-level
    # combinator (400 tools.N.custom.input_schema: input_schema does not support oneOf, allOf,
    # or anyOf at the top level). The first fix added "type" but kept a top-level oneOf, so it
    # still 400ed -- this test now asserts BOTH invariants so the second gate can't slip through.
    # Sweep EVERY schema across all emission sites: plain unit, cheap pull-cord shape,
    # external-engine dispatch, refute-N verifier panel, and the iterate-to-consensus loop.
    script = _emit_units(
        [
            _verify_unit("plain"),
            _verify_unit("cheap", tier={"model": "haiku", "effort": "low"}),
            _verify_unit("ext", capability="code-generation"),
            _verify_unit("panel", verify={"n": 2, "pass_rule": "majority"}),
            _verify_unit(
                "iter",
                verify={"n": 2, "pass_rule": "majority", "iterate_to_consensus": True},
            ),
        ]
    )
    schemas = _extract_agent_schemas(script)
    # 5 unit schemas + 2 panel verifiers + the iterate loop's verifier call at minimum.
    assert len(schemas) >= 7
    for schema in schemas:
        assert schema.get("type") == "object", f"schema missing top-level type: {schema}"
        forbidden = {"oneOf", "allOf", "anyOf"} & schema.keys()
        assert not forbidden, f"schema has unsupported top-level combinator {forbidden}: {schema}"
    # The cheap-tier pull-cord shape is a FLAT typed object: pull_cord rides as a top-level
    # optional property (NOT under a combinator), and there is no `required` alternation. The
    # returns-XOR-pull_cord contract lives in __gate + the RETURN CONTRACT, not the schema.
    cheap: list[dict[str, object]] = []
    for schema in schemas:
        properties = schema.get("properties")
        if isinstance(properties, dict) and "pull_cord" in properties:
            cheap.append(schema)
    assert cheap, "expected at least one cheap-tier pull-cord schema"
    for schema in cheap:
        properties = schema["properties"]
        assert isinstance(properties, dict)
        assert properties.get("pull_cord") == {"type": "string"}
        assert "oneOf" not in schema and "required" not in schema


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


# --- Runtime ladder climbing (#364): escalate_tier + escalate_on_signal + pull_cord ---


def test_escalate_tier_one_rung_effort_first() -> None:  # R1
    t = ES.escalate_tier(ES.Tier(model="sonnet", effort="medium"))
    assert t == ES.Tier(model="sonnet", effort="high")  # exactly one effort rung, same model


def test_escalate_tier_model_climb_at_effort_ceiling() -> None:  # R1
    # haiku's ceiling is high (models.json) -> the next rung is the MODEL axis, keeping effort.
    t = ES.escalate_tier(ES.Tier(model="haiku", effort="high"))
    assert t == ES.Tier(model="sonnet", effort="high")


def test_escalate_tier_top_of_ladder_returns_none() -> None:  # R3 signal
    assert ES.escalate_tier(ES.Tier(model="fable", effort="xhigh")) is None


def test_escalate_tier_ceiling_blocks_climb() -> None:  # KTD5
    blocked = ES.escalate_tier(
        ES.Tier(model="sonnet", effort="high"), ceiling=ES.Tier(model="sonnet", effort="high")
    )
    assert blocked is None  # never exceeds the ceiling, never same-tier re-run


def test_escalate_tier_never_unrunnable() -> None:  # KTD1 invariant
    seen = ES.Tier(model="haiku", effort="low")
    for _ in range(16):  # walk the whole ladder from the bottom
        nxt = ES.escalate_tier(seen)
        if nxt is None:
            break
        assert nxt != seen
        nxt.validate("walk")  # would raise SpecError on an unrunnable pair
        seen = nxt
    assert seen == ES.Tier(model="fable", effort="xhigh")  # the walk terminates at the top


def _escalate_unit(**kw: object) -> dict[str, object]:
    unit = _verify_unit("U1", verify={"n": 3, "pass_rule": "majority"}, escalate_on_signal=True)
    unit["tier"] = {"model": "sonnet", "effort": "medium"}
    unit.update(kw)
    return unit


def _emit_units_unattended(units: list[dict[str, object]]) -> str:
    spec = ES.ExecutionSpec.from_dict(
        {"name": "verify-demo", "description": "d", "repo": "/tmp/r", "units": units}
    )
    spec.validate()
    return str(ES.emit_workflow_script(spec, unattended=True))


def test_escalate_on_signal_one_rung_reemit() -> None:  # R2
    script = _emit_units_unattended([_escalate_unit()])
    # The retry re-runs at EXACTLY one rung up (sonnet/medium -> sonnet/high), never more.
    assert 'effort: "high"' in script
    assert "climbing ONE rung to sonnet/high" in script
    assert "sonnet/xhigh" not in script.split("cordProposal")[0]  # no rung-skipping in the retry
    # let-declared so the refuted branch can reassign the unit var.
    assert "let U1 = await agent(" in script


def test_escalate_on_signal_unattended_retry_emits_return_schema() -> None:
    script = _emit_units_unattended([_escalate_unit()])
    assert "climbing ONE rung to sonnet/high" in script
    assert script.count(_return_schema_fragment()) == 2


def test_escalate_on_signal_top_of_ladder_halts() -> None:  # R3
    script = _emit_units_unattended([_escalate_unit(tier={"model": "fable", "effort": "xhigh"})])
    assert "at top of ladder" in script
    assert "HALT, not loop" in script
    assert "climbing ONE rung" not in script  # no retry branch exists at the top
    assert "const U1 = await agent(" in script  # nothing to reassign -> const stays


def test_escalate_attended_asks() -> None:  # R5
    script = _emit_units([_escalate_unit()])  # attended is the default emission
    assert "escalation-proposal" in script
    assert "confirm via /tier patch and re-emit" in script
    assert "climbing ONE rung" not in script  # never a silent in-script climb when attended


def test_escalate_unattended_silent() -> None:  # R6
    script = _emit_units_unattended([_escalate_unit()])
    assert "escalation-proposal" not in script  # no ask gate -- the climb is silent
    assert "climbing ONE rung" in script
    assert "still refuted after the one-rung climb" in script  # then HALT, never a second climb


def test_escalate_on_signal_absent_roundtrips() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict())
    unit_out = spec.to_dict()["units"][0]
    assert "escalate_on_signal" not in unit_out  # absent field emits no key (byte-identical)
    spec_on = ES.ExecutionSpec.from_dict(
        _spec_dict(escalate_on_signal=True, verify={"n": 3, "pass_rule": "majority"})
    )
    assert spec_on.to_dict()["units"][0]["escalate_on_signal"] is True


def test_escalate_on_signal_rejects_iterate_to_consensus() -> None:  # doc-review P1 (a)
    spec = ES.ExecutionSpec.from_dict(
        _spec_dict(
            escalate_on_signal=True,
            verify={"n": 3, "pass_rule": "majority", "iterate_to_consensus": True},
        )
    )
    with pytest.raises(ES.SpecError, match="iterate_to_consensus"):
        spec.validate()


def test_escalate_on_signal_rejects_fanout() -> None:  # doc-review P1 (b)
    spec = ES.ExecutionSpec.from_dict(
        _spec_dict(
            escalate_on_signal=True,
            verify={"n": 3, "pass_rule": "majority"},
            fanout=True,
            targets=["a.py", "b.py"],
        )
    )
    with pytest.raises(ES.SpecError, match="fan-out"):
        spec.validate()


def test_escalate_on_signal_requires_verify_panel() -> None:  # dead-wiring guard
    spec = ES.ExecutionSpec.from_dict(_spec_dict(escalate_on_signal=True))
    with pytest.raises(ES.SpecError, match="no.*refute signal|refute signal"):
        spec.validate()


def test_pull_cord_disposition() -> None:  # R7
    script = _emit_units([_verify_unit("U1", tier={"model": "haiku", "effort": "low"})])
    # The gate accepts the cord shape as a valid alternative, distinct from the
    # missing/malformed-output throws (which remain in the helper for non-cord results).
    assert "pull_cord" in script
    assert "__pulledCords.push" in script
    assert "missing-output" in script  # crash-path throws still present and distinct
    # The cheap-tier prompt carries the cord rider so the disposition has a producer.
    assert "PULL-CORD (#364" in script
    # A non-cheap unit does NOT get the rider (the signal rides the cheap-tier contract).
    opus_script = _emit_units([_verify_unit("U1")])
    assert "PULL-CORD (#364" not in opus_script


def test_pull_cord_not_complete_batched() -> None:  # R8
    script = _emit_units(
        [
            _verify_unit("U1", tier={"model": "haiku", "effort": "low"}),
            _verify_unit("U2", tier={"model": "haiku", "effort": "low"}, depends_on=["U1"]),
        ]
    )
    # Exactly ONE batched escalation check for the whole run -- not one per unit.
    assert script.count("if (__pulledCords.length > 0)") == 1
    assert "ONE batched escalation ask" in script
    # The batch fails the run (throw) so a cord unit is never marked complete.
    assert "throw new Error(`pull-cord (#364)" in script
    # Each cord entry carries its one-rung proposal computed at emit time.
    assert 'cordProposal: "haiku/low -> haiku/medium (+1 effort rung)"' in script


def test_pull_cord_reserved_returns_key() -> None:  # verifier P2
    spec = ES.ExecutionSpec.from_dict(_spec_dict(returns=["diff", "pull_cord"]))
    with pytest.raises(ES.SpecError, match="reserved return-disposition key"):
        spec.validate()


def test_cord_proposal_respects_session_ceiling() -> None:  # verifier P1
    # A unit AT the session ceiling has zero climb room: the cord entry must carry NO
    # proposal (the ceiling is the final word), rendering the no-legal-climb HALT branch.
    spec = ES.ExecutionSpec.from_dict(
        {
            "name": "d",
            "description": "d",
            "repo": "/tmp/r",
            "units": [
                {
                    "unit_id": "U1",
                    "label": "l",
                    "prompt": "p",
                    "tier": {"model": "haiku", "effort": "high"},
                    "returns": ["result"],
                }
            ],
        }
    )
    spec.validate()
    ceiling = ES.Tier(model="haiku", effort="high")
    script = str(ES.emit_workflow_script(spec, session_ceiling=ceiling))
    assert 'cordProposal: "' not in script  # no proposal above the operator's own cap
    assert "no legal climb: top of ladder or session ceiling" in script
    # Without the ceiling the same unit proposes its one-rung climb.
    unlimited = str(ES.emit_workflow_script(spec))
    assert 'cordProposal: "haiku/high -> sonnet/high (+1 model rung)"' in unlimited


# --- #366 U2: cost_budget emit-time HALT ---------------------------------------------------


def _budget_spec(units: list[dict[str, object]], cost_budget: object = None) -> dict[str, object]:
    """Build a multi-unit spec dict with an optional cost_budget."""
    spec: dict[str, object] = {
        "name": "budget-demo",
        "description": "exercise the #366 cost budget",
        "repo": "/tmp/repo",
        "units": units,
    }
    if cost_budget is not None:
        spec["cost_budget"] = cost_budget
    return spec


def _unit(unit_id: str, model: str, effort: str, **overrides: object) -> dict[str, object]:
    unit: dict[str, object] = {
        "unit_id": unit_id,
        "label": unit_id,
        "tier": {"model": model, "effort": effort},
        "prompt": "do the thing",
    }
    unit.update(overrides)
    return unit


def test_over_budget_spec_fails_emit_naming_total_vs_ceiling() -> None:
    # One sonnet/high unit costs 12; a budget of 10 must HALT naming both numbers.
    spec = ES.ExecutionSpec.from_dict(_budget_spec([_unit("U1", "sonnet", "high")], cost_budget=10))
    with pytest.raises(ES.SpecError, match=r"total spend 12 exceeds cost_budget 10"):
        spec.validate()


def test_under_budget_spec_passes() -> None:
    # Summed spend 12 <= budget 100 validates and emits clean.
    spec = ES.ExecutionSpec.from_dict(
        _budget_spec([_unit("U1", "sonnet", "high")], cost_budget=100)
    )
    spec.validate()  # no raise
    assert spec.spec_spend() == 12
    ES.emit_workflow_script(spec)  # emit path also runs validate -> no raise


def test_over_budget_counts_fanout_and_verify_multiplicity() -> None:
    # Naive one-weight-per-unit sum = 12 + 6 = 18 (<= budget 40, would pass).
    # Multiplicity-aware: fan-out sonnet/high x3 targets = 36; sonnet/medium (6) + verify n=3 (3x6)
    # = 24; total 60 > 40 -> HALT. Guards the false-negative KTD8 exists to prevent.
    fanout_unit = _unit("U1", "sonnet", "high", fanout=True, targets=["a", "b", "c"])
    verify_unit = _unit("U2", "sonnet", "medium", verify={"n": 3, "pass_rule": "majority"})
    spec = ES.ExecutionSpec.from_dict(_budget_spec([fanout_unit, verify_unit], cost_budget=40))
    assert spec.spec_spend() == 60
    with pytest.raises(ES.SpecError, match=r"total spend 60 exceeds cost_budget 40"):
        spec.validate()


def test_cost_budget_absent_roundtrips() -> None:
    # No cost_budget key -> to_dict emits none, and from_dict(to_dict) is byte-identical.
    payload = _budget_spec([_unit("U1", "sonnet", "high")])
    spec = ES.ExecutionSpec.from_dict(payload)
    assert spec.cost_budget is None
    assert "cost_budget" not in spec.to_dict()
    assert ES.ExecutionSpec.from_dict(spec.to_dict()).to_dict() == spec.to_dict()
    spec.validate()  # absent budget performs no spend check


def test_cost_budget_soft_warn_band(capsys: pytest.CaptureFixture[str]) -> None:
    # sonnet/high costs 12; budget 13 -> 12 is within 10% of the ceiling (0.9*13 = 11.7).
    spec = ES.ExecutionSpec.from_dict(_budget_spec([_unit("U1", "sonnet", "high")], cost_budget=13))
    spec.validate()  # no raise -- legal but near the ceiling
    captured = capsys.readouterr()
    assert "close to the ceiling" in captured.err


def test_cost_budget_below_one_rejected() -> None:
    spec = ES.ExecutionSpec.from_dict(_budget_spec([_unit("U1", "sonnet", "high")], cost_budget=0))
    with pytest.raises(ES.SpecError, match=r"cost_budget 0 must be >= 1"):
        spec.validate()


def test_cost_budget_non_integer_rejected() -> None:
    with pytest.raises(ES.SpecError, match=r"cost_budget"):
        ES.ExecutionSpec.from_dict(
            _budget_spec([_unit("U1", "sonnet", "high")], cost_budget="lots")
        )
    with pytest.raises(ES.SpecError, match=r"must be an integer, not a bool"):
        ES.ExecutionSpec.from_dict(_budget_spec([_unit("U1", "sonnet", "high")], cost_budget=True))


def test_unit_spend_pilot_not_double_counted() -> None:
    # A pilot is a separate declared unit counted on its own row; the fan-out must not re-add it.
    pilot = _unit("P1", "sonnet", "high")
    fanout = _unit("U1", "sonnet", "high", fanout=True, targets=["a", "b"], pilot="P1")
    spec = ES.ExecutionSpec.from_dict(_budget_spec([pilot, fanout]))
    # pilot 12 + fan-out (12 x 2 targets = 24) = 36; the pilot is NOT added again onto U1.
    assert ES.unit_spend(spec.unit_by_id("U1")) == 24
    assert spec.spec_spend() == 36


def test_spend_cli_reports_total_and_headroom(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # The `spend` verb is the real read-consumer /plan invokes -- it reports even an over-budget
    # spec rather than HALTing, so the operator sees the numbers.
    import json

    payload = _budget_spec([_unit("U1", "sonnet", "high")], cost_budget=20)
    payload["spend_envelope"] = 15
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(payload), encoding="utf-8")

    rc = ES.main(["spend", str(spec_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "total spend: 12" in out
    assert "cost_budget: 20  (headroom 8)" in out
    assert "spend_envelope: 15" in out


def test_spend_cli_reports_overage(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    import json

    payload = _budget_spec([_unit("U1", "opus", "high")], cost_budget=10)  # opus/high = 32
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(payload), encoding="utf-8")

    rc = ES.main(["spend", str(spec_path)])
    out = capsys.readouterr().out
    assert rc == 0  # a report never HALTs
    assert "total spend: 32" in out
    assert "OVER by 22" in out


# --- #367 U3: worth_it_because + cheaper_fallback validate hard-block ----------------------


def test_worth_it_fallback_required_above_baseline() -> None:
    # opus/high is a premium tier -> under require_receipts it needs worth_it_because AND
    # cheaper_fallback. The hard-block is authoring-gated (require_receipts), not on plain validate().
    bare = ES.ExecutionSpec.from_dict(_budget_spec([_unit("U1", "opus", "high")]))
    bare.validate()  # plain validate() does NOT enforce receipts (no retroactive break)
    with pytest.raises(ES.SpecError, match="worth_it_because"):
        bare.validate(require_receipts=True)
    # justification present but no fallback:
    no_fb = ES.ExecutionSpec.from_dict(
        _budget_spec([_unit("U1", "opus", "high", worth_it_because="deep judgment")])
    )
    with pytest.raises(ES.SpecError, match="cheaper_fallback"):
        no_fb.validate(require_receipts=True)
    # both present with a genuinely cheaper named fallback -> passes.
    ok = ES.ExecutionSpec.from_dict(
        _budget_spec(
            [
                _unit(
                    "U1",
                    "opus",
                    "high",
                    worth_it_because="deep judgment",
                    cheaper_fallback={"model": "sonnet", "effort": "high"},
                )
            ]
        )
    )
    ok.validate(require_receipts=True)  # no raise


def test_worth_it_fallback_not_required_at_baseline() -> None:
    # Non-premium tiers (sonnet/high and below, any cheap-model tier) need no justification even
    # under require_receipts.
    for model, effort in (
        ("sonnet", "medium"),
        ("sonnet", "high"),
        ("haiku", "high"),
        ("haiku", "low"),
    ):
        ES.ExecutionSpec.from_dict(_budget_spec([_unit("U1", model, effort)])).validate(
            require_receipts=True
        )


def test_worth_it_fields_absent_roundtrip() -> None:
    spec = ES.ExecutionSpec.from_dict(_budget_spec([_unit("U1", "sonnet", "medium")]))
    unit_dict = spec.units[0].to_dict()
    assert "worth_it_because" not in unit_dict
    assert "cheaper_fallback" not in unit_dict
    assert ES.ExecutionSpec.from_dict(spec.to_dict()).to_dict() == spec.to_dict()


def test_cheaper_fallback_not_actually_cheaper_fails() -> None:
    # opus/xhigh is DEARER than opus/high -> spend_delta != "cheapen" -> validate fails.
    spec = ES.ExecutionSpec.from_dict(
        _budget_spec(
            [
                _unit(
                    "U1",
                    "opus",
                    "high",
                    worth_it_because="x",
                    cheaper_fallback={"model": "opus", "effort": "xhigh"},
                )
            ]
        )
    )
    with pytest.raises(ES.SpecError, match="not strictly cheaper"):
        spec.validate(require_receipts=True)


def test_engine_owned_unit_exempt_from_worth_it() -> None:
    # A capability-routed second-opinion unit pins to opus/high by intent, not operator choice -> exempt.
    spec = ES.ExecutionSpec.from_dict(
        _budget_spec(
            [
                _unit(
                    "U1",
                    "opus",
                    "high",
                    capability="code-generation",
                    engine_intent="second-opinion",
                )
            ]
        )
    )
    spec.validate(require_receipts=True)  # no raise even under the authoring gate


def test_worth_it_cheaper_fallback_roundtrips_when_present() -> None:
    spec = ES.ExecutionSpec.from_dict(
        _budget_spec(
            [
                _unit(
                    "U1",
                    "fable",
                    "xhigh",
                    worth_it_because="frontier reasoning",
                    cheaper_fallback={"model": "opus", "effort": "xhigh"},
                )
            ]
        )
    )
    unit_dict = spec.units[0].to_dict()
    assert unit_dict["worth_it_because"] == "frontier reasoning"
    assert unit_dict["cheaper_fallback"] == {"model": "opus", "effort": "xhigh"}
    assert ES.ExecutionSpec.from_dict(spec.to_dict()).to_dict() == spec.to_dict()
    spec.validate(require_receipts=True)  # fable/xhigh with a strictly-cheaper opus/xhigh fallback


# --- #565 U3: Verify panel tier + panel receipts (KTD5) -------------------------------------


def _panel_unit(
    unit_id: str = "U1",
    model: str = "sonnet",
    effort: str = "medium",
    **verify_overrides: object,
) -> dict[str, object]:
    """A unit at ``model``/``effort`` carrying an n=3 majority verify panel with overrides."""
    verify: dict[str, object] = {"n": 3, "pass_rule": "majority"}
    verify.update(verify_overrides)
    return {
        "unit_id": unit_id,
        "label": unit_id,
        "tier": {"model": model, "effort": effort},
        "prompt": "do the work",
        "returns": ["result"],
        "verify": verify,
    }


def test_panel_tier_emits_effective_tier_while_unit_stays_lower() -> None:
    # A verify panel authored at opus/high over a sonnet/medium unit runs the VERIFIERS at
    # opus/high while the unit's own agent call stays sonnet/medium (#565 KTD5).
    unit_dict = _panel_unit(tier={"model": "opus", "effort": "high"})
    spec = ES.ExecutionSpec.from_dict(
        {"name": "panel-tier", "description": "d", "repo": "/tmp/r", "units": [unit_dict]}
    )
    spec.validate()
    unit = spec.unit_by_id("U1")
    assert unit is not None

    verifier_opts = ES._verifier_agent_opts(unit)
    assert 'model: "opus"' in verifier_opts
    assert 'effort: "high"' in verifier_opts
    # The unit's own tier is untouched.
    assert unit.tier.model == "sonnet"
    assert unit.tier.effort == "medium"

    script = str(ES.emit_workflow_script(spec))
    # Both tiers appear in the emitted script: the unit at sonnet/medium, the verifiers at opus/high.
    assert 'model: "opus"' in script
    assert 'model: "sonnet"' in script


def test_panel_tier_absent_uses_unit_tier_and_omits_keys() -> None:
    # Without a panel tier, verifiers ride the unit tier (R4 default preserved) and to_dict omits
    # the new keys byte-identically.
    unit_dict = _panel_unit(model="sonnet", effort="medium")
    spec = ES.ExecutionSpec.from_dict(
        {"name": "panel-default", "description": "d", "repo": "/tmp/r", "units": [unit_dict]}
    )
    spec.validate()
    unit = spec.unit_by_id("U1")
    assert unit is not None

    verifier_opts = ES._verifier_agent_opts(unit)
    assert 'model: "sonnet"' in verifier_opts
    assert 'effort: "medium"' in verifier_opts

    verify_dict = unit.verify.to_dict()
    assert set(verify_dict) == {"n", "pass_rule", "iterate_to_consensus", "max_iterations"}
    assert "tier" not in verify_dict
    assert "worth_it_because" not in verify_dict
    assert "cheaper_fallback" not in verify_dict
    # Full spec round-trip is byte-identical.
    assert ES.ExecutionSpec.from_dict(spec.to_dict()).to_dict() == spec.to_dict()


def test_panel_tier_and_receipts_roundtrip_when_present() -> None:
    unit_dict = _panel_unit(
        tier={"model": "opus", "effort": "high"},
        worth_it_because="adversarial depth",
        cheaper_fallback={"model": "sonnet", "effort": "high"},
    )
    spec = ES.ExecutionSpec.from_dict(
        {"name": "panel-receipts", "description": "d", "repo": "/tmp/r", "units": [unit_dict]}
    )
    verify_dict = spec.units[0].to_dict()["verify"]
    assert verify_dict["tier"] == {"model": "opus", "effort": "high"}
    assert verify_dict["worth_it_because"] == "adversarial depth"
    assert verify_dict["cheaper_fallback"] == {"model": "sonnet", "effort": "high"}
    assert ES.ExecutionSpec.from_dict(spec.to_dict()).to_dict() == spec.to_dict()


def test_premium_panel_tier_receipts_gate_both_ways() -> None:
    # A premium panel tier (opus/high) on a NON-premium unit (sonnet/medium): plain validate passes,
    # but validate(require_receipts=True) fails naming both the unit and the panel.
    unit_dict = _panel_unit(tier={"model": "opus", "effort": "high"})
    bare = ES.ExecutionSpec.from_dict(
        {"name": "panel-gate", "description": "d", "repo": "/tmp/r", "units": [unit_dict]}
    )
    bare.validate()  # no receipts -> no raise (no retroactive break)
    with pytest.raises(ES.SpecError, match=r"unit U1: verify tier .*worth_it_because"):
        bare.validate(require_receipts=True)

    # justification present but no cheaper_fallback:
    no_fb = ES.ExecutionSpec.from_dict(
        {
            "name": "panel-gate",
            "description": "d",
            "repo": "/tmp/r",
            "units": [
                _panel_unit(
                    tier={"model": "opus", "effort": "high"},
                    worth_it_because="adversarial depth",
                )
            ],
        }
    )
    with pytest.raises(ES.SpecError, match=r"cheaper_fallback"):
        no_fb.validate(require_receipts=True)

    # both present with a strictly-cheaper fallback -> passes the authoring gate.
    ok = ES.ExecutionSpec.from_dict(
        {
            "name": "panel-gate",
            "description": "d",
            "repo": "/tmp/r",
            "units": [
                _panel_unit(
                    tier={"model": "opus", "effort": "high"},
                    worth_it_because="adversarial depth",
                    cheaper_fallback={"model": "sonnet", "effort": "high"},
                )
            ],
        }
    )
    ok.validate(require_receipts=True)  # no raise


def test_panel_cheaper_fallback_not_strictly_cheaper_fails() -> None:
    # A panel cheaper_fallback that is NOT strictly cheaper than the panel tier fails under
    # require_receipts, mirroring the unit rule.
    unit_dict = _panel_unit(
        tier={"model": "opus", "effort": "high"},
        worth_it_because="adversarial depth",
        cheaper_fallback={"model": "opus", "effort": "xhigh"},  # dearer, not cheaper
    )
    spec = ES.ExecutionSpec.from_dict(
        {"name": "panel-fb", "description": "d", "repo": "/tmp/r", "units": [unit_dict]}
    )
    with pytest.raises(ES.SpecError, match=r"not strictly\s+cheaper"):
        spec.validate(require_receipts=True)


def test_panel_tier_haiku_xhigh_halts_on_ceiling() -> None:
    # An on-palette-but-unrunnable panel tier (haiku/xhigh) HALTs on the palette ceiling check --
    # a HALT, not a clamp -- even on plain validate().
    unit_dict = _panel_unit(tier={"model": "haiku", "effort": "xhigh"})
    spec = ES.ExecutionSpec.from_dict(
        {"name": "panel-ceiling", "description": "d", "repo": "/tmp/r", "units": [unit_dict]}
    )
    with pytest.raises(ES.SpecError, match=r"exceeds model 'haiku' ceiling"):
        spec.validate()


def test_panel_tier_spend_prices_verifiers_at_effective_tier() -> None:
    # A 3-verifier opus/high panel on a sonnet/medium unit costs base(sonnet/medium) +
    # 3 x base(opus/high) = 6 + 3*32 = 102.
    unit_dict = _panel_unit(tier={"model": "opus", "effort": "high"})
    spec = ES.ExecutionSpec.from_dict(
        {"name": "panel-spend", "description": "d", "repo": "/tmp/r", "units": [unit_dict]}
    )
    unit = spec.unit_by_id("U1")
    assert unit is not None
    base_unit = ES.to_spend("sonnet", "medium")
    base_panel = ES.to_spend("opus", "high")
    assert ES.unit_spend(unit) == base_unit + 3 * base_panel

    # Without the panel tier the same panel prices at the unit tier: 6 + 3*6 = 24.
    default_dict = _panel_unit(model="sonnet", effort="medium")
    default_spec = ES.ExecutionSpec.from_dict(
        {"name": "panel-spend2", "description": "d", "repo": "/tmp/r", "units": [default_dict]}
    )
    default_unit = default_spec.unit_by_id("U1")
    assert default_unit is not None
    assert ES.unit_spend(default_unit) == base_unit + 3 * base_unit
