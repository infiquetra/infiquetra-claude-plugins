# Doc Review — Effort becomes a first-class field (#363 plan)

**Target:** `docs/plans/2026-07-05-effort-first-class-plan.md`
**Reviewed revision:** working tree (post-`/plan`, pre-`/work`)
**Blocked:** **NO** — no unresolved P0/P1 (all findings fixed in place per operator instruction "fix all").
**Linked:** plan `docs/plans/2026-07-05-effort-first-class-plan.md` · spec `…-spec.json` · saga `issue-363` · issue #363 · outcome leaf `sub-363`

## Readiness summary

The plan can drive implementation. It is a plan-phase artifact (no formal rubric engine — that is for
idea/issue/spec phases), so it took the readiness-skeptic pass. Grounding is strong: every claim carries
a `file:line` cite, and the central design fork (KTD1) was operator-decided. Eight findings surfaced; two
were verified against the repo (not assumed), and all eight were fixed in place. The one P1 was a
scope-unbounded risk that could have let `/work` refactor a working code path — now locked out.

## Findings (all fixed)

| # | Pri | Finding | Status |
|---|-----|---------|--------|
| 1 | P1 | Seam scope unbounded — `/work` could refactor `execution_spec.py`'s working emit (`:982`) to route through `inject_effort()`, re-introducing risk + dead-wiring | **Fixed** — Scope Boundaries now lock the seam to the Agent-tool site; non-agent branches are guarded no-ops (proven by AC6), emit path explicitly out of scope |
| 2 | P2 | R5 three-layer cascade's "team default" middle layer had no source (verified: no team-level effort config exists) | **Fixed** — R5 defines it as an optional team-wide effort that falls through to the agent default when unset |
| 3 | P2 | AC3 said "parse the A7 table" but R4/KTD say the emitter *generates* the cell | **Fixed** — AC3 reframed to compose-time validation, not table re-parsing |
| 4 | P2 | R9/U5 "actual effort" source unspecified | **Fixed** — pinned to the worker manifest (`worker-manifest.md:48,54`) in R9 + U5 + the spec prompt |
| 5 | P2 | U1 lint "script and/or pytest" — an open choice | **Fixed** — resolved to a pytest test in the existing CI step + optional script wrapper (R3 needs no new CI step) |
| 6 | P3 | Lint blast-radius unstated / could red-CI | **Fixed** — verified all 33 existing `model:` values in-palette; recorded the safe-audit note in U1 |
| 7 | P3 | U3 logical dependency on U2 overstated | **Fixed** — U3 dep clarified to U1+`resolve()`; U2 is serialization-order only |
| 8 | P3 | U6 "flip QUEUED to shipped" would overclaim real Agent-tool honoring | **Fixed** — U6 now marks it *resolved via the seam* with the native-knob swap as tracked residual |

## Facts verified during review (not assumed)

- All existing agent `model:` values are in-palette (8 haiku / 11 opus / 14 sonnet across 34 agent files;
  one model-less `tiering_exempt` agent) → the fleet-wide lint is safe to enable (finding 6).
- No team-level effort/tier default config exists in `plugins/team-execution/` or `team_emitter.py` →
  the R5 middle layer needed an explicit definition (finding 2).
- `execution_spec.py:982` already emits `agent({effort})` and `external-engine-workers.md:155` passes real
  effort → the two "real-knob" paths are live, which is what makes finding 1's scope-lock correct.

## Applied fixes

Eight in-place edits to the plan (findings 1–8 above) plus two aligned prompts in the ExecutionSpec
(U1 pytest-primary, U5 worker-manifest source). Spec re-validated (`OK: 6 units`) and re-emitted; per-unit
tiers preserved (U2/U3 opus/high, rest sonnet/medium).

## Residual risk

Low. The plan is decision-complete and scope-locked. The one irreducible honesty caveat — already stated
in KTD1/KTD7 — is that the `EFFORT_RIDER` proxy on the Agent-tool path is a prose directive, not a real
reasoning-budget knob; the plan does not claim otherwise, and the seam is structured to swap in the real
knob when the harness ships it.
