#!/usr/bin/env python3
"""Structured execution-spec + Claude Code workflow-script emitter (R9 keystone).

`/plan` authors ONE structured execution-spec and emits from it **either** a runnable
Claude Code workflow script (this module) **or** the team-execution markdown protocol
(``team_emitter.py``, U11). Saga stores only an ``orchestration_ref`` pointer; it never
vendors backend machinery (R9, KTD6). The governance difference is *which emitter runs*,
not the authoring.

The spec is the single source of truth: units carry a per-unit ``{model, effort}`` tier
(R2(b)), a return contract, dependency barriers, escalations, and -- for fan-out units --
an **enumerated** target list with post-run reconciliation (R10, never a silent filter).

Two authoring-time invariants are enforced at EMIT time -- a mis-built spec is an invalid
oracle, so it must fail loudly rather than silently emit a broken script:

* **R10** -- a fan-out unit with an empty / missing enumerated target list FAILS emit.
* **R3** -- a pilot at a different ``{model, effort}`` tier than its fan-out FAILS emit
  (a mis-tiered pilot validates a different cost surface than the fan-out it gates).

The sibling worked reference is
``docs/plans/2026-06-21-saga-tiering-and-execution-campaign.workflow.js`` -- a hand-authored
ultracode harness whose shape this emitter reproduces: control-flow only, agents do the
work, per-unit tiers, dependency barriers, rebase-before-merge, full hands-off auto-merge.

Cheap-tier (haiku / sonnet-low) generated agents carry the
``workflow_structuredoutput_budget`` lesson baked in (cap output, mandatory final emit,
skim don't read, batch concurrency) -- a budget-exhausted cheap agent that never emits its
StructuredOutput is the failure this prevents.

House testability pattern (mirrors ``saga.py`` / ``handoff_envelope.py``): pure functions,
no I/O at import, dataclasses with explicit ``from_dict`` so a JSON/plan-authored spec
round-trips deterministically and offline.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Tier vocabulary (Epic 0 tier rule R1). The emitter does not invent tiers; it only
# validates that authored tiers are drawn from these closed sets so a typo
# ("opus-high", "med") fails emit rather than silently producing an un-runnable script.
MODELS = ("opus", "sonnet", "haiku")
EFFORTS = ("low", "medium", "high")

# Models cheap enough that the structuredoutput-budget lesson MUST be baked into the
# generated agent prompt. An opus/high agent has budget headroom; a haiku or a
# sonnet/low agent over a large surface is exactly the case the lesson guards
# (workflow_structuredoutput_budget: brevity + mandatory emit + skim + batch).
_CHEAP_MODELS = ("haiku",)

# refute-N pass rules (KTD3 / KTD5). A finding survives unless refuted per this rule:
# majority => >= ceil(N/2) verifiers refute; unanimous => all N refute.
PASS_RULES = ("majority", "unanimous")

# Hard upper bound on a verify panel's verifier count. N above this FAILS validate/emit --
# the bound directly guards the rate-limit overcorrection (R3: the 22/23-judges panel that
# tripped the concurrency cap). N <= CAP is allowed; a soft warn band starts at WARN below.
VERIFY_N_CAP = 7

# Soft threshold: a panel size in (WARN, CAP] validates but emits a stderr warning -- big
# panels are legal but smell like the overcorrection, so they are surfaced, not silently run.
VERIFY_N_WARN = 5

# The verbatim budget-discipline rider baked into cheap-tier generated agents. This is
# the workflow_structuredoutput_budget lesson as an instruction the emitted agent reads.
BUDGET_RIDER = (
    "BUDGET DISCIPLINE (cheap-tier): you run on a small output budget. "
    "(1) CAP OUTPUT -- be terse; no human-facing prose, no recaps of files you read. "
    "(2) MANDATORY EMIT -- your FINAL action MUST be the StructuredOutput call; never end "
    "the turn without it, even if the work is partial (return what you have + a note). "
    "(3) SKIM, don't read -- open only the exact lines you need, never whole large files. "
    "(4) BATCH -- issue independent tool calls in one parallel block, not serially."
)


class SpecError(ValueError):
    """A spec that violates an authoring-time invariant (R3 / R10) or is malformed.

    Raised at validate/emit time so a mis-built spec fails loudly. Carrying the
    offending unit id in the message keeps the failure actionable for ``/plan``.
    """


@dataclass(frozen=True)
class Tier:
    """A per-unit ``{model, effort}`` tier (R2(b))."""

    model: str
    effort: str

    def validate(self, where: str) -> None:
        if self.model not in MODELS:
            raise SpecError(f"{where}: model {self.model!r} not in {MODELS}")
        if self.effort not in EFFORTS:
            raise SpecError(f"{where}: effort {self.effort!r} not in {EFFORTS}")

    @property
    def is_cheap(self) -> bool:
        """True iff this tier needs the structuredoutput-budget rider baked in."""
        return self.model in _CHEAP_MODELS

    @classmethod
    def from_dict(cls, data: dict[str, Any], where: str) -> Tier:
        if "model" not in data or "effort" not in data:
            raise SpecError(f"{where}: tier needs both 'model' and 'effort'")
        return cls(model=str(data["model"]), effort=str(data["effort"]))

    def to_dict(self) -> dict[str, str]:
        return {"model": self.model, "effort": self.effort}


@dataclass(frozen=True)
class Verify:
    """An optional refute-N judge-panel over a unit's output (KTD5).

    ``n`` verifier agents (same tier as the unit) review the unit's result; a finding
    survives unless refuted per ``pass_rule`` (majority / unanimous). The panel is
    bounded (KTD3): ``1 <= n <= VERIFY_N_CAP``, with a soft warn band above
    ``VERIFY_N_WARN`` -- the bound guards the rate-limit overcorrection.
    """

    n: int
    pass_rule: str

    def validate(self, where: str) -> None:
        if self.n < 1:
            raise SpecError(f"{where}: verify n={self.n} must be >= 1")
        if self.n > VERIFY_N_CAP:
            raise SpecError(
                f"{where}: verify n={self.n} exceeds the cap {VERIFY_N_CAP} "
                f"(KTD3 -- a bounded panel guards the rate-limit overcorrection)"
            )
        if self.n > VERIFY_N_WARN:
            print(
                f"WARN {where}: verify n={self.n} is in the warn band "
                f"({VERIFY_N_WARN} < n <= {VERIFY_N_CAP}) -- large panels risk the "
                f"rate-limit overcorrection.",
                file=sys.stderr,
            )
        if self.pass_rule not in PASS_RULES:
            raise SpecError(f"{where}: verify pass_rule {self.pass_rule!r} not in {PASS_RULES}")

    @classmethod
    def from_dict(cls, data: dict[str, Any], where: str) -> Verify:
        if "n" not in data or "pass_rule" not in data:
            raise SpecError(f"{where}: verify needs both 'n' and 'pass_rule'")
        try:
            n = int(data["n"])
        except (TypeError, ValueError) as exc:
            raise SpecError(f"{where}: verify n {data['n']!r} is not an integer") from exc
        return cls(n=n, pass_rule=str(data["pass_rule"]))

    def to_dict(self) -> dict[str, Any]:
        return {"n": self.n, "pass_rule": self.pass_rule}


@dataclass
class Unit:
    """One execution unit -- one ``agent()`` call in the emitted script.

    A *fan-out* unit (``fanout=True``) runs the same operation across many targets;
    it MUST carry an enumerated ``targets`` list (R10) so the run can reconcile what
    actually ran against what was declared -- never a silent filter. A fan-out unit
    MAY name a ``pilot`` unit that gates it (run one target first to de-risk the
    fan-out); the pilot MUST be at the SAME tier as the fan-out (R3).
    """

    unit_id: str
    label: str
    tier: Tier
    prompt: str
    # The structured-return contract: the required keys the agent must emit. Mirrors the
    # reference's UNIT_SCHEMA `required`. Empty list = no enforced contract (a barrier).
    returns: list[str] = field(default_factory=list)
    # Dependency barriers: unit_ids that must complete before this unit runs.
    depends_on: list[str] = field(default_factory=list)
    # Escalation: a human/operator note surfaced if the unit HALTs (resumable).
    escalation: str = ""
    # Fan-out: same op over many enumerated targets (R10).
    fanout: bool = False
    targets: list[str] = field(default_factory=list)
    # A pilot unit_id that gates this fan-out (run one first). Same-tier required (R3).
    pilot: str = ""
    # An optional refute-N judge-panel over this unit's output (KTD5). Absent => no panel;
    # an absent field round-trips unchanged so team_emitter / existing specs are untouched.
    verify: Verify | None = None

    def validate(self, where: str) -> None:
        if not self.unit_id:
            raise SpecError(f"{where}: a unit needs a non-empty unit_id")
        self.tier.validate(f"unit {self.unit_id}")
        if self.verify is not None:
            self.verify.validate(f"unit {self.unit_id}")
        if self.fanout and not self.targets:
            # R10: a fan-out unit MUST enumerate its targets -- never a silent filter.
            raise SpecError(
                f"unit {self.unit_id}: fan-out unit declares no enumerated targets "
                f"(R10 -- a fan-out without an explicit target list is a silent filter)"
            )
        if self.targets and not self.fanout:
            raise SpecError(
                f"unit {self.unit_id}: targets given but fanout=False -- "
                f"mark the unit fanout=True or drop the targets"
            )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Unit:
        unit_id = str(data.get("unit_id", ""))
        where = f"unit {unit_id or '<missing id>'}"
        if "tier" not in data:
            raise SpecError(f"{where}: missing 'tier'")
        return cls(
            unit_id=unit_id,
            label=str(data.get("label", unit_id)),
            tier=Tier.from_dict(data["tier"], where),
            prompt=str(data.get("prompt", "")),
            returns=[str(r) for r in data.get("returns", [])],
            depends_on=[str(d) for d in data.get("depends_on", [])],
            escalation=str(data.get("escalation", "")),
            fanout=bool(data.get("fanout", False)),
            targets=[str(t) for t in data.get("targets", [])],
            pilot=str(data.get("pilot", "")),
            verify=(Verify.from_dict(data["verify"], where) if data.get("verify") else None),
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "unit_id": self.unit_id,
            "label": self.label,
            "tier": self.tier.to_dict(),
            "prompt": self.prompt,
            "returns": list(self.returns),
            "depends_on": list(self.depends_on),
            "escalation": self.escalation,
            "fanout": self.fanout,
            "targets": list(self.targets),
            "pilot": self.pilot,
        }
        # Only emit verify when present so an absent panel round-trips unchanged --
        # team_emitter and existing specs never gain a new key (R5).
        if self.verify is not None:
            out["verify"] = self.verify.to_dict()
        return out


@dataclass
class ExecutionSpec:
    """The structured execution-spec `/plan` authors and the emitters consume.

    One spec, two emitters (R9 / KTD6): ``emit_workflow_script`` (this module) and the
    team-execution markdown emitter (U11). Saga stores only an ``orchestration_ref``
    pointer to the emitted artifact.
    """

    name: str
    description: str
    units: list[Unit]
    # The repo the emitted workflow operates on (the harness `REPO` constant).
    repo: str = ""

    def unit_by_id(self, unit_id: str) -> Unit | None:
        for unit in self.units:
            if unit.unit_id == unit_id:
                return unit
        return None

    def validate(self) -> None:
        """Validate the whole spec, enforcing the R3 + R10 authoring invariants.

        Raises ``SpecError`` on the first violation found (fail emit). Checks, in order:
        non-empty name + units; unique unit ids; per-unit validity (incl. R10 fan-out
        targets); every ``depends_on`` / ``pilot`` resolves to a real unit; and R3 --
        a pilot is at the SAME tier as the fan-out it gates.
        """
        if not self.name:
            raise SpecError("spec needs a non-empty name")
        if not self.units:
            raise SpecError("spec needs at least one unit")

        seen: set[str] = set()
        var_owner: dict[str, str] = {}
        for unit in self.units:
            unit.validate(f"spec {self.name}")
            if unit.unit_id in seen:
                raise SpecError(f"duplicate unit_id {unit.unit_id!r}")
            seen.add(unit.unit_id)
            # The emitted result var is the sanitized unit_id; two ids that sanitize to the
            # same JS identifier would emit a duplicate `const` (a SyntaxError in the ESM the
            # emitter produces). Reject the collision here rather than emit unloadable JS.
            js_var = _js_var(unit.unit_id)
            if js_var in var_owner:
                raise SpecError(
                    f"unit_id {unit.unit_id!r} and {var_owner[js_var]!r} both map to the JS "
                    f"identifier {js_var!r} (- and . both become _); rename one so the emitted "
                    f"script has unique result vars"
                )
            var_owner[js_var] = unit.unit_id

        for unit in self.units:
            for dep in unit.depends_on:
                if dep not in seen:
                    raise SpecError(
                        f"unit {unit.unit_id}: depends_on {dep!r} is not a declared unit"
                    )
            if unit.pilot:
                pilot = self.unit_by_id(unit.pilot)
                if pilot is None:
                    raise SpecError(
                        f"unit {unit.unit_id}: pilot {unit.pilot!r} is not a declared unit"
                    )
                if not unit.fanout:
                    raise SpecError(
                        f"unit {unit.unit_id}: declares a pilot but is not a fan-out unit"
                    )
                # R3: the pilot must be at the SAME tier as the fan-out it gates --
                # a mis-tiered pilot is an invalid oracle (it validates a different
                # cost surface than the fan-out runs on).
                if pilot.tier != unit.tier:
                    raise SpecError(
                        f"unit {unit.unit_id}: pilot {unit.pilot!r} tier "
                        f"{pilot.tier.to_dict()} != fan-out tier {unit.tier.to_dict()} "
                        f"(R3 -- a mis-tiered pilot is an invalid oracle)"
                    )

        # The dependency graph (depends_on + implicit pilot barriers) must be acyclic --
        # a cycle has no valid layering, so it fails validate (KTD4). This also re-checks
        # that every depends_on / pilot id resolves to a declared unit.
        dependency_layers(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExecutionSpec:
        if "units" not in data or not isinstance(data["units"], list):
            raise SpecError("spec needs a 'units' list")
        return cls(
            name=str(data.get("name", "")),
            description=str(data.get("description", "")),
            units=[Unit.from_dict(u) for u in data["units"]],
            repo=str(data.get("repo", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "repo": self.repo,
            "units": [u.to_dict() for u in self.units],
        }


# ---------------------------------------------------------------------------
# Topological dependency layering (KTD4) -- the input to layer-parallel emission
# ---------------------------------------------------------------------------


def dependency_layers(spec: ExecutionSpec) -> list[list[str]]:
    """Compute topological layers (Kahn) of unit ids ready to run together (KTD4).

    Each returned layer is a list of unit ids whose dependencies are all satisfied by
    earlier layers, so a layer of >1 id renders as one ``parallel([...])`` wave and
    layers are sequenced by ``await``. Edges come from each unit's ``depends_on`` AND --
    so R3 is preserved -- from a fan-out unit's ``pilot``: the pilot is an implicit
    barrier edge (pilot -> fan-out), guaranteeing the pilot lands in an EARLIER layer
    than the fan-out it gates (otherwise both would share a parallel wave and the gate
    would be lost).

    Raises ``SpecError`` on a cycle (the remaining un-layered units are named) or on a
    ``depends_on`` / ``pilot`` id that resolves to no declared unit. Within a layer, ids
    keep declaration order for deterministic emission.
    """
    ids = [u.unit_id for u in spec.units]
    id_set = set(ids)

    # Build edges (predecessor -> successor) and an in-degree per unit. A pilot edge is
    # an IMPLICIT barrier (pilot before fan-out) on top of any explicit depends_on.
    preds: dict[str, set[str]] = {uid: set() for uid in ids}
    for unit in spec.units:
        for dep in unit.depends_on:
            if dep not in id_set:
                raise SpecError(f"unit {unit.unit_id}: depends_on {dep!r} is not a declared unit")
            preds[unit.unit_id].add(dep)
        if unit.pilot:
            if unit.pilot not in id_set:
                raise SpecError(f"unit {unit.unit_id}: pilot {unit.pilot!r} is not a declared unit")
            preds[unit.unit_id].add(unit.pilot)

    layers: list[list[str]] = []
    placed: set[str] = set()
    remaining = list(ids)  # declaration order preserved
    while remaining:
        ready = [uid for uid in remaining if preds[uid] <= placed]
        if not ready:
            # No unit is unblocked -> a cycle among the remaining units.
            raise SpecError(f"dependency cycle among units: {', '.join(sorted(remaining))}")
        layers.append(ready)
        placed.update(ready)
        remaining = [uid for uid in remaining if uid not in placed]

    return layers


# ---------------------------------------------------------------------------
# Emitter -- spec -> runnable Claude Code workflow script
# ---------------------------------------------------------------------------


def _js_string(value: str) -> str:
    """Encode a Python string as a single-quoted JS string literal.

    ``json.dumps`` gives a valid JS string (double-quoted, escaped); we keep that --
    it is the safest encoder for arbitrary prompt text.
    """
    return json.dumps(value)


def _js_var(unit_id: str) -> str:
    """Sanitize a unit_id into a JS identifier used as the emitted result var.

    ``-`` and ``.`` are not legal in JS identifiers, so both map to ``_``. Two distinct
    unit_ids can therefore collide to the same var (``a-b`` and ``a.b`` both -> ``a_b``),
    which would emit a duplicate ``const`` -- a SyntaxError in the ESM the emitter produces.
    ``ExecutionSpec.validate`` rejects that collision up front (fail emit, never emit
    unloadable JS).
    """
    return unit_id.replace("-", "_").replace(".", "_")


def _verifier_prompt(unit: Unit) -> str:
    """Assemble the prompt text a verifier agent in ``unit``'s refute-N panel reads.

    A verifier is an adversarial skeptic over the unit's result: it tries to REFUTE the
    unit's findings, not to re-do the work. Cheap-tier panels (same tier as the unit per
    R4) carry the budget rider so a budget-exhausted verifier still emits its verdict.
    """
    parts: list[str] = [
        f"REFUTE-N VERIFIER over unit {unit.unit_id} ({unit.label}). You are an adversarial "
        f"skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's "
        f"output and the evidence it cites; for each claimed finding decide REFUTED (with a "
        f"concrete reason) or UPHELD. Emit a structured verdict {{refuted: [...], upheld: [...]}}."
    ]
    if unit.tier.is_cheap:
        parts.append(BUDGET_RIDER)
    return "\n\n".join(parts)


def _emit_thunk(lines: list[str], spec: ExecutionSpec, unit: Unit) -> None:
    """Append one ``() => agent(...),`` thunk entry for ``unit`` inside a ``parallel([...])``.

    Every thunk carries the unit's per-unit ``{model, effort}`` tier (R2(b)) and the same
    budget-rider / R10 reconciliation prompt as a singleton agent() call.
    """
    prompt = _agent_prompt(spec, unit)
    opts = [
        f"label: {_js_string(unit.label)}",
        f"model: {_js_string(unit.tier.model)}",
        f"effort: {_js_string(unit.tier.effort)}",
    ]
    lines.append("  () =>")
    lines.append("    agent(")
    lines.append(f"      {_js_string(prompt)},")
    lines.append("      { " + ", ".join(opts) + " },")
    lines.append("    ),")


def _emit_verify_panel(lines: list[str], unit: Unit, var: str) -> None:
    """Append a refute-N judge-panel + pass-rule reconciliation for ``unit`` to ``lines``.

    Renders a ``parallel([...])`` of ``unit.verify.n`` verifier ``agent()`` calls over the
    unit's result (each at the SAME ``{model, effort}`` tier as the unit per R4), then a
    PANEL-LEVEL pass-rule verdict: count the verifiers that returned at least one refutation
    and compare to the threshold -- ``majority`` => ``>= ceil(N/2)`` verifiers refuted;
    ``unanimous`` => all N refuted. (This is a panel-level signal, not per-finding survival:
    a generic emitter cannot match findings across verifiers, so it surfaces "did enough
    skeptics refute anything" for the operator/runtime to act on.) The resulting
    ``<var>_refuted`` boolean is CONSUMED: when set, the script ``log()``s a review warning so
    a refuted unit result is surfaced rather than silently relied upon.
    """
    panel = unit.verify
    assert panel is not None  # caller guards this
    n = panel.n
    threshold = (n + 1) // 2 if panel.pass_rule == "majority" else n
    verifier_prompt = _verifier_prompt(unit)
    opts = [
        f"label: {_js_string(unit.label + ' verifier')}",
        f"model: {_js_string(unit.tier.model)}",
        f"effort: {_js_string(unit.tier.effort)}",
    ]

    lines.append(f"// verify: refute-{n} panel over {unit.unit_id} (pass_rule: {panel.pass_rule};")
    lines.append(
        f"// panel-level: the unit result is refuted when >= {threshold} of {n} verifiers refute)"
    )
    lines.append(f"const {var}_verdicts = await parallel([")
    for _ in range(n):
        lines.append("  () => agent(")
        lines.append(f"    {_js_string(verifier_prompt)},")
        lines.append("    { " + ", ".join(opts) + f", input: {var} }},")
        lines.append("  ),")
    lines.append("])")
    # Pass-rule reconciliation: count verifiers that refuted at least one finding.
    lines.append(
        f"const {var}_refute_count = {var}_verdicts.filter((v) => v && v.refuted "
        f"&& v.refuted.length > 0).length"
    )
    lines.append(f"const {var}_refuted = {var}_refute_count >= {threshold}  // {panel.pass_rule}")
    # Consume the verdict: surface a refuted unit result instead of relying on it silently.
    lines.append(
        f"if ({var}_refuted) log(`refute-{n} ({panel.pass_rule}): {unit.unit_id} result refuted by "
        f"${{{var}_refute_count}}/{n} verifiers -- review before relying on it`)"
    )
    lines.append("")


def _agent_prompt(spec: ExecutionSpec, unit: Unit) -> str:
    """Assemble the prompt text for a unit's emitted ``agent()`` call.

    Bakes the budget rider into cheap-tier (haiku) agents (R9 mitigation) and appends
    the enumerated-target reconciliation instruction for fan-out units (R10).
    """
    parts: list[str] = [unit.prompt]
    if unit.tier.is_cheap:
        parts.append(BUDGET_RIDER)
    if unit.fanout:
        targets = ", ".join(unit.targets)
        parts.append(
            f"FAN-OUT TARGETS ({len(unit.targets)}, enumerated -- run the operation across "
            f"EXACTLY these, no silent filter): {targets}. "
            f"RECONCILE after the run: report any declared target you did NOT complete "
            f"(R10 -- a missing target is a reported gap, never silently dropped)."
        )
    if unit.returns:
        parts.append("Return a structured result with keys: " + ", ".join(unit.returns) + ".")
    return "\n\n".join(p for p in parts if p)


def emit_workflow_script(spec: ExecutionSpec) -> str:
    """Emit a runnable Claude Code workflow script (.workflow.js) from the spec.

    Validates first (fail emit on R3 / R10), then renders a control-flow-only harness:
    one ``agent()`` call per unit at its ``{model, effort}`` tier, dependency barriers
    rendered as ``await`` ordering, fan-out reconciliation + cheap-tier budget riders
    baked into prompts. The agents do the real work; this script is control flow only.

    Returns the script source as a string (the caller writes it beside the plan and
    records the path as the saga ``orchestration_ref``).
    """
    spec.validate()

    lines: list[str] = []
    lines.append("// ===========================================================================")
    lines.append(f"// {spec.name} -- emitted Claude Code workflow harness.")
    lines.append("// AUTO-EMITTED from a structured execution-spec by execution_spec.py.")
    lines.append("// CONTROL FLOW ONLY -- every agent reads the plan as its authoritative spec.")
    lines.append("// Per-unit {model, effort} tiers (R2(b)); R3 pilot/fan-out same-tier +")
    lines.append("// R10 enumerated-target reconciliation enforced at emit time.")
    lines.append("// ===========================================================================")
    lines.append("")
    lines.append("export const meta = {")
    lines.append(f"  name: {_js_string(spec.name)},")
    lines.append(f"  description: {_js_string(spec.description)},")
    lines.append("}")
    lines.append("")
    if spec.repo:
        lines.append(f"const REPO = {_js_string(spec.repo)}")
        lines.append("")

    # Topological waves (KTD4): each layer's units are mutually independent and run in a
    # single parallel() wave; layers are sequenced by await (the dependency barrier). A
    # singleton layer renders as a plain `const x = await agent(...)`. _js_var (module-level)
    # sanitizes the unit_id into the result var; validate() has already rejected any two ids
    # that would collide to the same identifier.
    _var = _js_var

    def _emit_unit_header(unit: Unit) -> None:
        lines.append(f"// ---- {unit.unit_id}: {unit.label} ----")
        if unit.depends_on:
            lines.append(f"// depends_on: {', '.join(unit.depends_on)} (barrier)")
        if unit.pilot:
            lines.append(f"// pilot: {unit.pilot} (R3 same-tier gate)")
        if unit.escalation:
            lines.append(f"// escalation: {unit.escalation}")

    for layer in dependency_layers(spec):
        layer_units = [spec.unit_by_id(uid) for uid in layer]
        if len(layer_units) == 1:
            unit = layer_units[0]
            assert unit is not None
            _emit_unit_header(unit)
            var = _var(unit.unit_id)
            lines.append(f"const {var} = await agent(")
            prompt = _agent_prompt(spec, unit)
            opts = [
                f"label: {_js_string(unit.label)}",
                f"model: {_js_string(unit.tier.model)}",
                f"effort: {_js_string(unit.tier.effort)}",
            ]
            lines.append(f"  {_js_string(prompt)},")
            lines.append("  { " + ", ".join(opts) + " },")
            lines.append(")")
            lines.append("")
            if unit.verify is not None:
                _emit_verify_panel(lines, unit, var)
            continue

        # A layer of >1 ready unit -> one parallel() wave of thunks. The wave's results
        # are destructured back into the per-unit vars so dependents/verify panels read them.
        for unit in layer_units:
            assert unit is not None
            _emit_unit_header(unit)
        layer_vars = [_var(uid) for uid in layer]
        lines.append(f"const [{', '.join(layer_vars)}] = await parallel([")
        for unit in layer_units:
            assert unit is not None
            _emit_thunk(lines, spec, unit)
        lines.append("])")
        lines.append("")
        for unit in layer_units:
            assert unit is not None
            if unit.verify is not None:
                _emit_verify_panel(lines, unit, _var(unit.unit_id))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Capability-portable inline/serial baseline (R11 / U12)
# ---------------------------------------------------------------------------
#
# Every authored plan carries a runnable inline/serial baseline so it executes on ANY
# host, with or without the Workflow tool. The dynamic-workflow layer (emit_workflow_script)
# applies only on a capable host; on an off-host resume the orchestration tier recompiles
# DOWN (lifecycle_state.recheck_orchestration_capability) and this baseline is what the
# inline floor runs. The recompile preserves every unit spec and its per-unit {model,
# effort} tier -- the baseline below annotates each unit with the SAME tier it carried in
# the dynamic script, so a downgrade changes only HOW units are dispatched (serial, inline)
# and never WHICH units run or AT WHAT tier.


def emit_inline_baseline(spec: ExecutionSpec) -> str:
    """Emit the runnable inline/serial baseline plan from the spec (R11 floor).

    Validates first (the same R3/R10 invariants -- a mis-built spec has no valid baseline
    either), then renders a deterministic, host-independent serial checklist: each unit in
    declared order, dependency barriers honored by ordering, the per-unit ``{model, effort}``
    tier PRESERVED on every unit (the recompile preserves tiers -- R11), fan-out targets
    enumerated inline (R10, never a silent filter). This is the always-runnable floor an
    off-host resume degrades to; it requires no Workflow tool.

    Returned as a Markdown checklist string (the inline executor reads it as its serial
    run order). It is NOT a .workflow.js -- by construction it dispatches nothing in
    parallel and calls no agent() harness.
    """
    spec.validate()

    lines: list[str] = []
    lines.append(f"# Inline/serial baseline -- {spec.name}")
    lines.append("")
    lines.append(
        "Runnable on ANY host (no Workflow tool required). The orchestration tier "
        "recompiled DOWN to inline; unit specs and per-unit {model, effort} tiers preserved."
    )
    if spec.description:
        lines.append("")
        lines.append(spec.description)
    if spec.repo:
        lines.append("")
        lines.append(f"Repo: {spec.repo}")
    lines.append("")
    lines.append("Run each unit IN ORDER (serial); honor the declared dependency barriers.")
    lines.append("")

    for idx, unit in enumerate(spec.units, start=1):
        tier = f"{unit.tier.model}/{unit.tier.effort}"
        lines.append(f"## {idx}. {unit.unit_id}: {unit.label}  [tier: {tier}]")
        if unit.depends_on:
            lines.append(f"- depends_on (run after): {', '.join(unit.depends_on)}")
        if unit.pilot:
            lines.append(f"- pilot (run first, same tier): {unit.pilot}")
        if unit.escalation:
            lines.append(f"- escalation: {unit.escalation}")
        if unit.fanout:
            lines.append(
                f"- fan-out over {len(unit.targets)} enumerated targets "
                f"(serial, reconcile after -- report any not completed): "
                f"{', '.join(unit.targets)}"
            )
        prompt = _agent_prompt(spec, unit)
        lines.append("")
        for prompt_line in prompt.splitlines():
            lines.append(f"  {prompt_line}" if prompt_line else "")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


# The orchestration tiers, mirrored from lifecycle_state.ORCHESTRATION_TIERS, so the
# emitter can render the correct floor for a given (possibly downgraded) tier without a
# cross-module import at module scope (the scripts load standalone in tests).
_WORKFLOW_TIER = "cc-workflows-ultracode"
_TEAM_TIER = "team-execution"
_INLINE_TIER = "inline"


def _emit_team_structure(spec: ExecutionSpec) -> str:
    """Lazily load ``team_emitter`` and emit the team-execution ``## Team Structure`` markdown.

    Imported by path (not at module scope) so ``execution_spec`` stays importable standalone in
    tests and there is no import cycle with ``team_emitter`` (which lazily loads this module).
    """
    import importlib.util

    path = Path(__file__).parent / "team_emitter.py"
    loaded = importlib.util.spec_from_file_location("team_emitter", path)
    assert loaded is not None and loaded.loader is not None
    module = importlib.util.module_from_spec(loaded)
    loaded.loader.exec_module(module)
    return module.emit_team_structure(spec)  # type: ignore[no-any-return]


def recompile_for_tier(spec: ExecutionSpec, orchestration_mode: str) -> str:
    """Re-emit the spec for a (possibly downgraded) orchestration tier (R11 recompile).

    ONLY the orchestration tier changes -- every unit survives in every emitter. The inline and
    workflow emitters additionally render each unit's ``{model, effort}`` tier verbatim;
    ``team-execution`` re-emits the ``team_emitter`` ``## Team Structure`` markdown protocol (the R5
    third leg of the by-mode dispatcher seam), which renders the team roles/units but not the
    per-unit ``{model, effort}`` (the team-execution protocol selects models per its own roster).
    ``cc-workflows-ultracode`` re-emits the dynamic ``.workflow.js`` harness; ``inline`` or any
    unknown floor re-emits the inline/serial baseline, the always-runnable floor. This is the
    function an off-host resume calls after ``recheck_orchestration_capability`` decides the new
    tier: it never errors and always returns a runnable artifact (AE3).
    """
    spec.validate()
    if orchestration_mode == _WORKFLOW_TIER:
        return emit_workflow_script(spec)
    if orchestration_mode == _TEAM_TIER:
        return _emit_team_structure(spec)
    # The inline floor and any other/unknown tier emit the host-independent serial baseline --
    # never an empty or un-runnable artifact.
    return emit_inline_baseline(spec)


# ---------------------------------------------------------------------------
# CLI -- validate or emit from a JSON spec file (offline-deterministic)
# ---------------------------------------------------------------------------


def _load_spec(path: Path) -> ExecutionSpec:
    return ExecutionSpec.from_dict(json.loads(path.read_text()))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Execution-spec validator + workflow emitter.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_val = sub.add_parser("validate", help="validate a spec JSON (R3/R10 invariants)")
    p_val.add_argument("spec", type=Path)

    p_emit = sub.add_parser("emit", help="emit a workflow script from a spec JSON")
    p_emit.add_argument("spec", type=Path)
    p_emit.add_argument("-o", "--out", type=Path, help="write the script here (default: stdout)")

    p_base = sub.add_parser(
        "baseline", help="emit the runnable inline/serial baseline (R11 floor) from a spec JSON"
    )
    p_base.add_argument("spec", type=Path)
    p_base.add_argument("-o", "--out", type=Path, help="write the baseline here (default: stdout)")

    args = parser.parse_args(argv)
    try:
        spec = _load_spec(args.spec)
        if args.cmd == "validate":
            spec.validate()
            print(f"OK: {spec.name} ({len(spec.units)} units) is a valid execution-spec.")
            return 0
        if args.cmd == "baseline":
            script = emit_inline_baseline(spec)
        else:
            script = emit_workflow_script(spec)
    except SpecError as exc:
        print(f"SPEC ERROR: {exc}", file=sys.stderr)
        return 2

    if args.out:
        args.out.write_text(script)
        print(f"wrote {args.out}")
    else:
        print(script)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
