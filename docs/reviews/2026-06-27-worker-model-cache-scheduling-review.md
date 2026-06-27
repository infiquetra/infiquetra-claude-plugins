# Doc Review — Worker×Model Cache Scheduling Plan

**Verdict:** was **BLOCKED** (1 P0 + 4 P1) at the reviewed revision; all confirmed findings fixed in
place — the plan is now ready to drive implementation.

- **Target:** `docs/plans/2026-06-27-worker-model-cache-scheduling-plan.md`
- **Reviewed revision:** `be20b3b` (baseline) → working tree (fixes applied)
- **Method:** readiness-skeptic pass (Claude) + two adversarial second-opinion generators —
  codex (`gpt-5.5`, xhigh) and agy (Gemini 3.1 Pro High) — each run read-only against plan + source.
  External engines generated; every finding was verified against source before adoption (none taken as
  verifier-of-record).
- **Linked:** plan above · saga `task-worker-cache-scheduling` · requirements
  `docs/brainstorms/2026-06-27-worker-model-cache-scheduling-requirements.md` · decisions
  `docs/engineering-journal/DECISIONS.md#worker-cache-scheduling`

## Findings & resolution

| # | Pri | Finding | Source | Status |
|---|-----|---------|--------|--------|
| 1 | P0 | `Unit` carries no file-path data → plugin-dir segmentation (KTD2/U2) unbuildable | Claude + agy + codex | **Fixed** — U1 adds `Unit.files` (R2, KTD2) |
| 2 | P1 | Row cardinality undefined: U2 collapses units into one resident worker but emitter emits one row per unit | codex (agy: agent-name variant) | **Fixed** — KTD3 + U2 emit one row per segment |
| 3 | P1 | Wave scheduling underspecified: `depends_on` is unit-level, needs segment-level derivation | codex | **Fixed** — KTD4 + U1 derives segment deps + U5 schedules on them |
| 4 | P1 | U3 doesn't update the SKILL.md A7 template to match the new emitted columns | agy | **Fixed** — U3 updates the template |
| 5 | P1 | U2 mutates the shared `ExecutionSpec` → leak across per-tier emits | agy | **Fixed** — KTD5 + R9 (side mapping / copy) |
| 6 | P2 | Risk section calls U2 "additive"; it is schema-breaking (changes contract + breaks tests) | codex | **Fixed** — Risk corrected; U2 marked schema-breaking |
| 7 | P2 | U3 omits R4 cross-segment summary-handoff | agy | **Fixed** — U3 includes summary-handoff |
| 8 | P2 | U4 re-engages reviewers but doesn't switch context to the delta | agy | **Fixed** — U4 + R5 delta context |
| 9 | P2 | U2 test pointed at workflow emitter, not the team emitter that owns the markdown | codex | **Fixed** — U2 tests via `recompile_for_tier(..., "team-execution")` |
| 10 | P2/P3 | U1 (now U2) breaks existing `worker-{i}` oracle assertions | Claude + agy + codex | **Fixed** — U2 updates `test_team_emitter.py` assertions |
| 11 | P3 | Citation completeness (`consensus-protocol.md:26` + `:51`) | codex | **Fixed** — both cited |

## Applied fixes

Restructured the plan around **derive-then-emit** and threaded segment granularity through:
- U1 became `Unit.files` + saga-side segmentation / segment-dep derivation / tiering (on a side map,
  no mutation).
- U2 became the segment-row emit (one row per resident worker), explicitly schema-breaking.
- U3 gained the template-column update + the R4 summary-handoff.
- U4 gained the delta-context switch.
- U5 now schedules on the derived segment graph.
- Added KTD3 (row cardinality), KTD4 (segment-dep derivation), KTD5 (copy-not-mutate); corrected the
  Risk section's "additive" claim.

## Residual risk

The revision is substantial and was not re-run through a second adversarial pass — each fix maps
directly to a verified finding, but the integrated result carries the usual large-edit risk. The
behavioral units (U3/U4/U5) remain prose-validated by design (KTD6), so their correctness is confirmed
at `/work` review + first real run, not by pytest.
