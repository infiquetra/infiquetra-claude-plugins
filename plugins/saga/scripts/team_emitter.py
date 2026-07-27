#!/usr/bin/env python3
"""Team-execution markdown emitter — the R9 second emitter (U11).

`/plan` authors ONE structured execution-spec (``execution_spec.py``, U10) and emits
from it **either** a runnable Claude Code workflow script (U10) **or** this team-
execution markdown protocol.  The governance difference is *which emitter runs*, not
the authoring — the spec is the single source of truth (R9, KTD6).

This emitter produces the ``## Team Structure`` section (mirroring
``team-execution/skills/team-execution/SKILL.md:234``) from the spec's units:

* **Workers** — one row per spec unit (each unit is a discrete phase of work).
* **Reviewers** — always the base reviewer set required by team-execution protocol.
* **Validators** — the base scanner set; extended per-unit via ``validators`` metadata.
* **Execution Gates** — the standard consensus + remediation protocol.
* **Reference Files** — the team-execution protocol reference set.

Saga records the path to the emitted plan file as ``orchestration_ref`` (a pointer,
never a copy of team-execution machinery — R9, KTD6).  The emitter returns the markdown
string; the caller writes it beside the plan and passes the path to
``saga.py save --orchestration-ref <path>``.

House testability pattern (mirrors ``execution_spec.py`` / ``saga.py``): pure functions,
no I/O at import.  The ``emit_team_structure`` function is the single testable surface.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fleet_commons_shim  # noqa: E402  (after the sys.path shim, by design)

# Canonical effort vocabulary + the #362 dispatch-time tier resolver, loaded through the
# fleet-commons shim (never re-declared here -- KTD3). ``EFFORTS`` is the single source of
# truth the A7 ``Tier`` cell's effort half is validated against (R4); ``resolve()`` supplies
# the base agent-frontmatter layer the three-layer cascade wraps (R5, KTD4).
_tier_palette = fleet_commons_shim.load("tier_palette")
EFFORTS: tuple[str, ...] = _tier_palette.EFFORTS
_tier_resolver = fleet_commons_shim.load("tier_resolver")

# Reverse map from a segment's resolved model to a canonical work-shape registry key, used
# only to give ``resolve()`` a valid base layer (the agent-frontmatter default). Because the
# plan-authored per-unit tier is the most-specific layer and always present when the emitter
# runs, this base is never the cascade winner in practice -- it is recorded in provenance as
# the layer that *would* have supplied the value had no more-specific layer existed.
_MODEL_TO_WORK_SHAPE: dict[str, str] = {
    "fable": "judgment",
    "opus": "judgment",
    "sonnet": "mechanical",
    "haiku": "purely-mechanical",
}

# The base reviewer set the team-execution protocol always requires.
# These are the three mandatory base reviewers from the SKILL.md template.
_BASE_REVIEWERS: list[tuple[str, str]] = [
    ("devils-advocate-reviewer", "Devil's Advocate Reviewer"),
    ("security-reviewer", "Security Reviewer"),
    ("architecture-reviewer", "Architecture Reviewer"),
]

# The base validator set (security-scanner is the baseline).
_BASE_VALIDATORS: list[tuple[str, str]] = [
    ("security-scanner", "Scanner"),
]

# The reference files the team-execution protocol requires (verbatim from SKILL.md).
_REFERENCE_FILES: list[str] = [
    "team-execution/skills/team-execution/references/reviewer-registry.md",
    "team-execution/skills/team-execution/references/review-criteria.md",
    "team-execution/skills/team-execution/references/consensus-protocol.md",
    "team-execution/skills/team-execution/references/validator-registry.md",
    "team-execution/skills/team-execution/references/validator-criteria.md",
    "team-execution/skills/team-execution/references/validator-execution-order.md",
    "team-execution/skills/team-execution/references/validator-evidence-state.md",
    "team-execution/skills/team-execution/references/validator-spawn-quirks.md",
]

# The standard execution-gate protocol (verbatim from SKILL.md).
_EXECUTION_GATES: list[str] = [
    "Reviewer consensus threshold: >= 9.0/10 from every reviewer.",
    "Reviewer non-consensus blocks validators unless the user explicitly overrides.",
    "Scanners run before PR/CI/merge/nonprod coordination.",
    "Tester hard-fail blocks completion.",
    "Maximum 3 remediation loops before escalation.",
]


def _validate_effort(effort: str, where: str) -> None:
    """Raise on an off-palette effort (R4) -- the same failure as an R1/R2 frontmatter typo.

    ``spec.validate()`` already checks each unit's tier, but the emitter re-asserts at compose
    time so an off-palette effort reaching the A7 ``Tier`` cell fails loudly here rather than
    being silently rendered into an un-runnable team-structure table.
    """
    if effort not in EFFORTS:
        raise ValueError(f"{where}: effort {effort!r} not in {EFFORTS} (R4 off-palette effort)")


def resolve_teammate_effort(
    seg: Any,
    team_default_effort: str | None,
    *,
    resolve: Any = None,
) -> tuple[str, str]:
    """Resolve one teammate's effort through the three-layer cascade (R5, KTD4).

    Precedence, most-specific wins:

    1. **plan-unit** -- the plan-authored per-unit tier (``seg.tier.effort``). Always present
       when the emitter runs, so it is the winner in the ordinary case.
    2. **team-default** -- an optional team-wide effort default (usually ``None`` today).
    3. **agent-frontmatter** -- the base layer ``resolve()`` supplies from the segment's
       work-shape registry row (``default_effort``).

    The cascade *wraps* ``tier_resolver.resolve()``: ``resolve()`` computes the base layer, and
    the winning layer's value is threaded back through ``operator_override={"effort": ...}`` so
    the resolver validates it. Returns ``(effort, resolving_layer)``.

    Chaperone workers are excluded upstream (see ``emit_team_structure``); this function is
    never called for them (R6, KTD5).
    """
    resolve_fn = resolve if resolve is not None else _tier_resolver.resolve
    work_shape = _MODEL_TO_WORK_SHAPE.get(seg.tier.model, "mechanical")

    plan_effort = getattr(seg.tier, "effort", None)
    if plan_effort is not None:
        override = {"effort": plan_effort}
        layer = "plan-unit"
    elif team_default_effort is not None:
        override = {"effort": team_default_effort}
        layer = "team-default"
    else:
        override = None
        layer = "agent-frontmatter"

    resolution = resolve_fn(role_kind=None, work_shape=work_shape, operator_override=override)
    return resolution.effort, layer


def _is_chaperone(seg: Any) -> bool:
    """A chaperone segment routes to an external engine/capability (KTD5).

    Its effort is intent-driven (offload -> sonnet/medium, second-opinion -> opus/high) and
    must NOT be overridden by the cascade -- the two intents pull in opposite directions by
    design, so the cascade skips these workers entirely (R6, KTD5).
    """
    return seg.engine is not None or seg.capability is not None


def emit_team_structure(
    spec: Any, team_default_effort: str | None = None, session_ceiling: Any | None = None
) -> str:
    """Emit the ``## Team Structure`` markdown section from an ``ExecutionSpec``.

    The spec is the same object ``execution_spec.py`` builds — validated by the caller
    before passing here.  This emitter never vendors team-execution machinery (R9): it
    produces a conforming markdown section the team-execution skill reads, nothing more.

    Returns the markdown string.  The caller writes it to the plan file and passes the
    path to ``saga.py save --orchestration-ref <path>`` so saga records only a pointer.

    Parameters
    ----------
    spec:
        A validated ``ExecutionSpec`` (from ``execution_spec.ExecutionSpec.from_dict``).
        The units become worker rows; the base reviewer / validator sets are fixed.
    team_default_effort:
        The optional team-wide effort default (R5 middle cascade layer). Usually ``None``
        (no such config today), in which case the cascade falls through to the plan-unit
        tier / agent-frontmatter base. Validated against ``EFFORTS`` when provided.
    """
    spec.validate()
    if team_default_effort is not None:
        _validate_effort(team_default_effort, "team-default effort")

    lines: list[str] = []
    ceiling_notes: list[str] = []

    # ---- Header ----
    lines.append("## Team Structure")
    lines.append("")
    lines.append(
        f"<!-- emitted from execution-spec '{spec.name}' by team_emitter.py (R9, KTD6) -->"
    )
    lines.append(
        "<!-- governance: team-execution (gated consensus); "
        "for advisory consensus use emit_workflow_script instead -->"
    )
    lines.append("")

    # ---- Workers ---- one row per resident-worker segment (U2/KTD3)
    lines.append("### Workers")
    lines.append("| Agent | Units | Tier | Mode | Depends-on | Engine | Intent |")
    lines.append("|-------|-------|------|------|------------|--------|--------|")
    import importlib.util

    # Reuse the canonical execution_spec module if it is already imported so the classes this
    # emitter references -- notably ``SpecError`` raised on an unenforceable sandbox (U3) -- are
    # IDENTITY-equal to the ones the caller catches. A fresh per-call load would define distinct
    # class objects, and an ``except execution_spec.SpecError`` upstream would silently miss them.
    mod = sys.modules.get("execution_spec")
    if mod is None:
        spec_module_path = Path(__file__).parent / "execution_spec.py"
        _spec = importlib.util.spec_from_file_location("execution_spec", spec_module_path)
        assert _spec is not None and _spec.loader is not None
        mod = importlib.util.module_from_spec(_spec)
        sys.modules["execution_spec"] = mod
        _spec.loader.exec_module(mod)
    # KTD3 halt-not-downgrade at the cheapest failure point (authoring time): a team-execution
    # resident runs bypassPermissions with no per-leaf tool restriction, so it cannot enforce a
    # restrictive sandbox. A unit that asks for one is rejected HERE rather than silently emitted
    # unrestricted -- reroute it to inline/cc-workflows or drop the sandbox (R4).
    for unit in spec.units:
        offending = mod.unenforceable_sandbox_axis("team-execution", unit.sandbox)
        if offending is not None:
            axis_name, axis_value = offending
            raise mod.SpecError(
                f"unit {unit.unit_id}: sandbox {axis_name}={axis_value!r} cannot be enforced by "
                f"backend 'team-execution' (KTD3 -- residents run bypassPermissions with no "
                f"per-leaf tool restriction). Route this unit to inline or cc-workflows, or drop "
                f"the restrictive sandbox. Halt-not-downgrade (R4)."
            )
    # #671: same halt the workflow emitter applies, and it matters MORE here — team-execution
    # residents are same-cwd by construction, run bypassPermissions with no per-leaf tool
    # restriction (KTD3), and are the one spawn kind the fleet lease never write-fenced (the
    # deliberate #616 carve-out: a PreToolUse-stamped, non-worktree reservation claims with no
    # worktree_root, so assert_write_target returns without a containment check).
    mod.assert_no_wave_file_conflicts(spec)
    segments = mod.segment_units(spec)

    # #365 U3: a session tier ceiling clamps each POST-MERGE segment tier DOWN, BEFORE the #369
    # enforceability halt and before rendering. Order is deliberate: a ceiling that caps e.g.
    # fable -> sonnet makes the segment spawnable by team-execution, so the halt should judge the
    # CLAMPED tier. The ceiling is the operator's live cap and never raises a tier; it is the final
    # word (it can clamp a segment below a #369 min_tier floor -- the live override wins, and the
    # downgrade is logged below).
    if session_ceiling is not None:
        clamped_segments = []
        for seg in segments:
            eff = mod.clamp_tier_to_ceiling(seg.tier, session_ceiling)
            if eff != seg.tier:
                ceiling_notes.append(
                    f"<!-- session tier ceiling {session_ceiling.model}/{session_ceiling.effort}"
                    f" (#365): {seg.resident_id} {seg.tier.model}/{seg.tier.effort}"
                    f" -> {eff.model}/{eff.effort} -->"
                )
            clamped_segments.append(dataclasses.replace(seg, tier=eff))
        segments = clamped_segments

    # #369 U3: the tier-axis sibling of the sandbox halt above -- but run on the POST-MERGE segment
    # tier, NOT the pre-merge unit tier. A member unit's min_tier floor can push the merged segment
    # above what team-execution can spawn even when every individual unit.tier was reachable (the
    # floor clamp in segment_units() happens AFTER any per-unit check would run). Checking seg.tier
    # subsumes the per-unit case -- seg.tier is the strongest of all member tiers + floors -- and so
    # closes that bypass. team-execution spawns by agentType and inherits its agent-frontmatter model,
    # so a segment whose merged model it cannot spawn (e.g. fable) HALTs rather than rendering a
    # cosmetic Tier cell it will not obey (halt-not-downgrade, R3).
    for seg in segments:
        tier_offending = mod.unenforceable_tier("team-execution", seg.tier)
        if tier_offending is not None:
            axis_name, axis_value = tier_offending
            raise mod.SpecError(
                f"segment {seg.resident_id} (units {', '.join(seg.unit_ids)}): tier "
                f"{axis_name}={axis_value!r} cannot be spawned by backend 'team-execution' (#369 -- "
                f"residents spawn by agentType and inherit their agent-frontmatter model; "
                f"{axis_value!r} is not in its reachable set -- a unit's min_tier floor may have "
                f"pushed the merged segment here). Route these units to inline or cc-workflows, or "
                f"lower the tier/floor. Halt-not-downgrade (R3)."
            )

    # Per-teammate effort provenance lines (R5): one HTML comment naming the layer that
    # supplied each teammate's resolved effort. Collected here and emitted as a commented
    # block after the table so they never disturb the parsed worker rows.
    provenance: list[str] = []

    for seg in segments:
        agent = f"`{seg.resident_id}`"
        units = ", ".join(seg.unit_ids)
        # R4: the A7 Tier cell's effort half must be drawn from the canonical EFFORTS palette;
        # an off-palette value raises here (same failure class as an R1/R2 frontmatter typo).
        _validate_effort(seg.tier.effort, f"worker {seg.resident_id} tier")

        if _is_chaperone(seg):
            # KTD5: chaperone effort is intent-driven and left untouched by the cascade.
            resolved_effort = seg.tier.effort
            resolving_layer = f"chaperone-intent:{seg.engine_intent or 'offload'}"
        else:
            resolved_effort, resolving_layer = resolve_teammate_effort(seg, team_default_effort)

        tier = f"{seg.tier.model}/{resolved_effort}"
        deps = ", ".join(seg.depends_on) if seg.depends_on else "—"
        if seg.engine is not None:
            engine = seg.engine
        elif seg.capability is not None:
            engine = f"cap:{seg.capability}"
        else:
            engine = "—"
        intent = seg.engine_intent if seg.engine_intent is not None else "—"
        lines.append(
            f"| {agent} | {units} | {tier} | bypassPermissions | {deps} | {engine} | {intent} |"
        )
        provenance.append(
            f"<!-- effort-provenance worker={agent} effort={resolved_effort} "
            f"resolved-by={resolving_layer} "
            f"(layers: plan-unit={seg.tier.effort} "
            f"team-default={team_default_effort or '—'}) -->"
        )
    lines.append("")
    lines.extend(provenance)
    lines.append("")

    # ---- Reviewers ---- always the base set
    lines.append("### Reviewers")
    lines.append("| Agent | Role | Required | Selection Reason |")
    lines.append("|-------|------|----------|------------------|")
    for agent, role in _BASE_REVIEWERS:
        lines.append(f"| `{agent}` | {role} | yes | Base reviewer |")
    lines.append("")

    # ---- Validators ---- base set; the team-execution skill selects further per plan
    lines.append("### Validators")
    lines.append("| Agent | Group | Required | Selection Reason | Blocking |")
    lines.append("|-------|-------|----------|------------------|----------|")
    for agent, group in _BASE_VALIDATORS:
        lines.append(
            f"| `{agent}` | {group} | yes | Base validator | hard-fail blocks automation |"
        )
    lines.append("")

    # ---- Execution Gates ----
    lines.append("### Execution Gates")
    for gate in _EXECUTION_GATES:
        lines.append(f"- {gate}")
    lines.append("")

    # ---- Reference Files ----
    lines.append("### Reference Files")
    for ref in _REFERENCE_FILES:
        lines.append(f"- `{ref}`")
    lines.append("")

    if ceiling_notes:
        lines.append("")
        lines.extend(ceiling_notes)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI -- emit the team-structure markdown from a JSON spec file
# ---------------------------------------------------------------------------


def _load_spec(path: Path) -> Any:
    """Load and return an ``ExecutionSpec`` from a JSON file.

    Imports ``execution_spec`` lazily so this module is importable without it on the
    path (tests import it directly from the file path).
    """
    # Resolve execution_spec relative to this file so the CLI works from any cwd.
    spec_module_path = Path(__file__).parent / "execution_spec.py"
    import importlib.util

    _spec = importlib.util.spec_from_file_location("execution_spec", spec_module_path)
    assert _spec is not None and _spec.loader is not None
    mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod.ExecutionSpec.from_dict(json.loads(path.read_text()))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Emit a team-execution ## Team Structure section from a spec JSON (R9, U11)."
    )
    parser.add_argument("spec", type=Path, help="Path to the execution-spec JSON file.")
    parser.add_argument(
        "-o",
        "--out",
        type=Path,
        help="Write the markdown here (default: stdout).",
    )
    args = parser.parse_args(argv)

    try:
        spec = _load_spec(args.spec)
        markdown = emit_team_structure(spec)
    except Exception as exc:  # SpecError or IO
        print(f"EMIT ERROR: {exc}", file=sys.stderr)
        return 2

    if args.out:
        args.out.write_text(markdown)
        print(f"wrote {args.out}")
    else:
        print(markdown, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
