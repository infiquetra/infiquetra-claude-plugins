# Doc review — delegation-tripwires plan (issue #384)

**Target:** `docs/plans/2026-07-07-delegation-tripwires-plan.md`
**Companion artifacts reviewed for same-story consistency:**
`docs/plans/2026-07-07-delegation-tripwires-spec.json` (canonical execution artifact,
cc-workflows-ultracode), `docs/plans/2026-07-07-delegation-tripwires.workflow.js` (emitted).
**Reviewed revision:** working tree (untracked) at HEAD `b0376e7`, 2026-07-07.
**Review type:** plan readiness-skeptic pass (rubric engine covers idea/issue/spec phases only —
not applicable to a plan). Operator directive: fix ALL severities P0–P3, not just P0/P1.
**Blocked:** NO — all findings fixed in place; zero remaining.
**Linked:** issue #384 (leaf sub-384 of outcome external-engine-offload), saga `issue-384`
(lifecycle-phase plan, destination merge).

## Method

Every load-bearing `path:line` cite in the plan was verified against the live repo (the plan's
author ran this review, so cite verification was made mandatory rather than sampled):
`engine_dispatch.py` (:15/:21/:29/:119-194/:158/:168/:171/:197-205/:282-330/:409-435,
`verified_by_claude` at :424), `provenance_manifest.py:54`, `agy_delegate.py`
(:995/:1021/:1374/:1390/:1594, bundle root `.claude/agy/runs` at :285, `prompt.txt` at :323),
`audit_harness_transcript.py` (:16-20/:32-38), `codex_delegate.py` (:273-297, `codex_launched`,
`.claude/codex/runs`, `prompt.txt` at :908, `MAX_LAST_MESSAGE_BYTES` = 8 MiB at :320),
`fleet_commons_shim.py` (resolution ladder, `load()` path at :153), saga `hooks.json` current
events (PreToolUse exists; Stop/SubagentStop absent), plugin versions (fleet-core 0.7.0, saga
0.73.1, team-execution 2.12.2), `external-engine-workers.md` §5 (:144), journal cites
(`DECISIONS.md:1124/:1145/:656/:1101-1103`, `LEARNINGS.md:528-538`), origin `T15.json`, and the
DoD test-file inventory.

## Findings and dispositions

| # | Priority | Finding | Status |
|---|----------|---------|--------|
| 1 | P1 | Fleet-core module paths wrong in plan U1/U2 **and** spec U1/U2: `plugins/fleet-core/scripts/<mod>.py` is unreachable by `fleet_commons_shim.load()` — the shim loads `<root>/scripts/fleet_commons/<module>.py` (`fleet_commons_shim.py:153`; all existing commons modules live there). As written, U3/U4/U5 hooks would fail open forever and the DoD block-test would fail, forcing mid-run rework. | FIXED — both artifacts now say `plugins/fleet-core/scripts/fleet_commons/…`; spec re-validated (`--require-receipts` clean), workflow re-emitted with corrected paths |
| 2 | P2 | Plan and spec told different execution stories: plan's per-unit Dependencies describe a partial order (U2 ∥ U1; U3/U4/U5 each on U1+U2) while the spec deliberately serializes U1→U7; the plan never referenced the spec, backend, tiers, or the /work-time verifier guardrail. An executor reading only the plan could parallelize into the concurrency cap and shared-file conflicts. | FIXED — new **Execution** section: canonical spec path, backend + operator choice, serialization rationale (cap 3, shared `hooks.json` + `test_delegation_tripwire.py`), tier story incl. U4/U5 operator bump to fable/xhigh (842 spend), Wave-A branch-materialization guardrail |
| 3 | P2 | Test-file ownership inconsistent across units: U1's scenarios create a DoD test in `tests/test_delegation_tripwire.py` but U1's Files omitted it, while U3's Files claimed the file as "(new)" — ambiguous creation ownership under the serialized order. | FIXED — U1 Files now lists it as created there; U3 marked "(extend — created in U1)" |
| 4 | P3 | U3 said "new PreToolUse entry" — `hooks.json` already has a `PreToolUse` array; ambiguous between "new event key" and "new matcher entry". U4's Stop/SubagentStop keys, by contrast, are genuinely new. | FIXED — U3 now says append to the existing array; U4 notes both event keys are new |
| 5 | P3 | Cite drift: `agy_delegate.py:33-47` for `STATUSES` (starts :34); `DECISIONS.md:646-655` for the no-confirmation hooks rule (load-bearing line at :656); `agy_delegate.py:~1390` tilde (exact :1390, twice). | FIXED — all three corrected |

## Applied fixes

All five findings fixed in place (no unsafe edits — no scope, architecture, or acceptance
changes; every fix is backed by repo evidence cited above). Spec re-validated with
`--require-receipts`, spend re-priced (unchanged, 842), `workflow.js` re-emitted; corrected
`fleet_commons/` paths confirmed present in the emitted script.

## Readiness summary

READY. The plan can drive implementation: every mechanism cite checks out against the live
repo, plan/spec/workflow tell one story, and the single execution-breaking defect (shim-invisible
module path) is corrected in all three artifacts.

## Residual risk from limited evidence

- The Claude Code hooks contract (Stop/SubagentStop/PreToolUse I/O) was verified against the
  vendor reference on 2026-07-07 per the plan's Sources; it was not re-fetched during this
  review. If the contract shifts before /work, U3/U4 carry the exposure.
- The Wave-A verifier branch-materialization patch remains a manual /work-time step — the
  emitter does not include it; the plan and spec both now state this explicitly, but nothing
  mechanically enforces it.
- `agy_delegate.py` line cites are exact today; agy is an actively developed plugin and U1
  importlib-loads it for the parity test, so drift before /work would surface as a parity-test
  failure rather than silent divergence (acceptable).
