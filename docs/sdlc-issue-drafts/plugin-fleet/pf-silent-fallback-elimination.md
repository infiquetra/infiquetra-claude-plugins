---
title: "defect: no silent Claude-fallback — fail-loud provenance_required, SUBSTITUTED disposition, fallback-reason propagation, empty-delivery HALT, attributed verify-fallback"
repo: infiquetra-claude-plugins
type: defect
tier: structural
objective: "Stand up the external-engine offload lane"
wave: wave-1
team: campps
project: operations
status: Idea
labels: defect, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
---

# defect: no silent Claude-fallback — fail-loud provenance_required, SUBSTITUTED disposition, fallback-reason propagation, empty-delivery HALT, attributed verify-fallback

### Objective
Stand up the external-engine offload lane

### Tier
structural

### Wave
wave-1

### Problem / motivation (grounded)

The fleet has a recorded, repeated failure mode: a run claimed as "delegated to an external
engine" turns out to be Claude doing the work itself, with nothing in the system that fails
loud about it. This is not hypothetical — it is a five-times-recurring class of finding in this
repo's own journal, and the current code has at least one live, provably decorative guard-rail
meant to catch it:

- `docs/engineering-journal/LEARNINGS.md:293` — `{#agy-delegate-silent-claude-fallback}`: audit
  of `#279` and `#278` found their "delegated to agy" runs made **zero** `agy` CLI invocations —
  the spawned teammate behaved as a Claude clone (Read/Write/Edit + `★ Insight` output style)
  while `#277` (PR #303) showed the genuine-delegation shape (nested `Agent` → `agy --model ...`
  Bash calls, Claude touching only `prompt.txt`). The generalizable rule recorded there: verify
  per-run transcript, never assume invocation happened because a delegate step was requested.
- `docs/engineering-journal/LEARNINGS.md:471` — `{#dead-wiring-needs-producer-and-consumer}`:
  the repo's standing lesson that a field or check with a producer but no consumer (or vice
  versa) is dead wiring that looks safe and is not.
- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:99-104` (§6) names this cluster
  explicitly as recurring-pain theme candidate 15, "delegation integrity" — 5+ journal learnings
  spanning agy silent Claude-fallback, dead-wiring producer+consumer mismatches,
  test-shape-masks-dead-wiring, and fake-adapter mismatch — concluding any bridge/delegation
  idea needs an explicit "did it actually run/persist" check, not a documentation promise.

Concretely, today's code has the following gaps, each independently verified against the
current tree on 2026-07-03:

1. **`provenance_required` is parsed and stored but never consulted.** `plugins/agy/scripts/
   agy_delegate.py:100,137-139,154,261` define, validate, and thread the `provenance_required`
   boolean through the envelope end to end. `plugins/saga/scripts/engine_dispatch.py:97` sets
   `"provenance_required": True` in the dispatch envelope it authors. Nowhere in
   `agy_delegate.py` does an `unproven + provenance_required` combination change `status` or the
   process exit code — `classify_transcript` (`agy_delegate.py:989-1022`) computes
   `"real"` vs `"fallback_suspected"` independently, and `decide_non_apply_status`
   (`agy_delegate.py:885`) and the exit-code path (`agy_delegate.py:1595-1614`) never read
   `provenance_required` at all. The field is decorative: a caller can request "provenance
   required" and get a clean exit on an unproven run.
2. **The resolver's Claude-fallback reason is not carried anywhere the operator or a downstream
   consumer can see it.** `engine_dispatch.py`'s `build_dispatch_manifest` (`:163-187`) sets
   `disposition = Disposition.FELL_BACK_TO_CLAUDE` purely from `evidence.halt is not None`
   (per `plugins/team-execution/skills/team-execution/references/external-engine-workers.md:158`)
   but does not surface *why* the fallback happened into the unit run-report schema or the
   session-end delegation roll-up — a forced unavailable-engine offload today produces a
   disposition value with no accompanying reason string reaching the report or roll-up.
3. **There is no first-class `SUBSTITUTED` disposition in the shared manifest builder.**
   `plugins/team-execution/skills/team-execution/references/external-engine-workers.md:163-168`
   documents, in prose, that `build_dispatch_manifest` "has no way to express this disposition
   (it only inspects `evidence.halt`)", so the chaperone worker is forced to hand-construct a
   `provenance_manifest.Manifest` directly with `disposition=pm.Disposition.SUBSTITUTED_ENGINE`,
   bypassing the shared builder entirely whenever a previewed engine gets silently substituted
   for another at dispatch time. That hand-built path is exactly the kind of one-off,
   easy-to-drift manifest construction the shared builder exists to prevent elsewhere.
4. **A delegated unit that writes nothing is not distinguished from a delegated unit that
   delivers.** `docs/engineering-journal/LEARNINGS.md:337-347`
   (`{#delegate-orphan-late-write}`) records a thrashing delegate runner spawning an orphan that
   wrote ~72 minutes after a PR was already open — caught only by an operator's routine
   `git status`, not by any structural boundary check. There is no `check_empty_delivery()` or
   equivalent at the unit boundary today; "commit each unit as it lands" is a remembered manual
   habit, not automated machinery.
5. **A degraded (tier-2+) verify spawn is invisible to the gate consumer.**
   `plugins/saga/references/sandbox-spawn-sites.md:57-76`
   (`{#readonly-verifier-fallback-ladder-325}`) documents a two-step fallback ladder
   (`saga:readonly-verifier` → `Explore` + worktree → `general-purpose` + worktree with explicit
   read-only instruction) so a verify-class spawn degrades gracefully instead of failing
   outright or silently reverting to unsandboxed. The ladder's descent depth is not attributed
   anywhere the gate-side summary renders — a caller reading a passing gate cannot tell whether
   the verifier that ran was the real `saga:readonly-verifier` or a tier-2/tier-3 fallback.

Each of these gaps shares the same shape: a check or field that looks like it enforces
provenance but has no wired consumer (or, in case 3, has a consumer with no shared producer) —
the dead-wiring pattern this repo's own journal names as its own recurring failure class.

## Definition of Done

Merged PR that:

1. Wires `provenance_required` into the supervised-status decision in
   `agy_delegate.py` so `unproven + provenance_required` coerces the run's status to
   `fallback_suspected` and the process exits non-zero, closing the dead-wiring gap between the
   field's producer (envelope authoring) and its (currently absent) consumer.
2. Threads the resolver's Claude-fallback reason string from `engine_dispatch.py`'s dispatch
   decision into both the unit run-report schema and the session-end `DELEGATION_NOOP` roll-up,
   so a forced unavailable-engine offload is traceable to a non-empty, human-readable reason in
   both places.
3. Extends `build_dispatch_manifest` (`engine_dispatch.py:163-187`) with a `SUBSTITUTED`
   disposition keyed off the bridge's receipt/preview-vs-resolved engine identity, and deletes
   the chaperone's hand-built `provenance_manifest.Manifest` construction path documented at
   `external-engine-workers.md:163-168`, so there is exactly one manifest-construction path for
   every disposition including substitution.
4. Adds a `check_empty_delivery()` unit-boundary check plus auto-commit-on-gate-pass wiring, so
   a delegated unit that writes nothing HALTs visibly instead of silently handing off, and a
   delivering unit auto-commits and advances without a manual "did anything land" habit.
5. Adds `verifier_identity` / `fallback_depth` fields to the verify-spawn contract and a
   gate-side render rule consuming them, so a tier-2 (or deeper) verify per
   `{#readonly-verifier-fallback-ladder-325}` surfaces explicitly (e.g. "fallback tier 2") in the
   gate summary rather than reading identically to a first-choice `saga:readonly-verifier` pass.
6. Is verified by the acceptance criteria below plus full-suite, lint, and type-check green.

### Acceptance criteria
- [ ] `unproven + provenance_required=True` coerces status to `fallback_suspected` and produces
  a non-zero exit code; `unproven + provenance_required=False` does not. Check:
  `uv run pytest tests/test_agy_delegate.py -k provenance_required_coerces_fallback` → passes,
  asserting both branches. *(covers T15-F3-1)*
- [ ] A forced unavailable-engine offload (engine unresolvable at dispatch time) produces a
  non-empty fallback reason string present in both the unit run report and the session-end
  `DELEGATION_NOOP` roll-up — not merely a disposition enum with no accompanying text. Check:
  `uv run pytest tests/test_engine_dispatch.py -k fallback_reason_propagation` → passes,
  asserting the reason string is present and non-empty in both artifacts. *(covers T15-F1-4)*
- [ ] A zero-invocation dispatch run auto-produces a manifest with
  `disposition=Disposition.SUBSTITUTED` and `kind=CLAUDE` attribution through
  `build_dispatch_manifest` itself, and the chaperone's prior hand-built
  `provenance_manifest.Manifest` construction call is deleted (not merely superseded). Check:
  `uv run pytest tests/test_engine_dispatch.py -k substituted_disposition` → passes; `grep -n
  "pm.Disposition.SUBSTITUTED_ENGINE" plugins/team-execution/skills/team-execution/references/
  external-engine-workers.md plugins/team-execution/**/*.py` finds no remaining hand-build call
  site outside the shared builder. *(covers T15-F2-5)*
- [ ] A delegated unit that writes nothing HALTs at the unit boundary (visible, typed stop —
  not a silent hand-off to the next step); a delegated unit that does deliver auto-commits and
  advances without a manual commit step. Check: `uv run pytest tests/test_check_empty_delivery.py
  -k halts_on_empty_delivery` and `-k autocommits_on_delivery` → both pass. *(covers T15-F2-4)*
- [ ] A verify-class spawn that falls back to tier 2 of the
  `{#readonly-verifier-fallback-ladder-325}` ladder (`Explore` + worktree) renders "fallback tier
  2" (or an equivalently explicit depth marker) in the gate summary; a first-choice
  `saga:readonly-verifier` spawn renders no fallback marker. Check: `uv run pytest
  tests/test_verify_spawn_gate_summary.py -k fallback_tier_2_rendered` and `-k
  no_fallback_marker_on_first_choice` → both pass. *(covers T15-F1-3)*
- [ ] Full suite, format, lint, and types stay green. Check: `uv run pytest && uv run ruff
  format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/
  --ignore-missing-imports` → all pass.

### Out-of-scope / non-goals
**In scope:**
- Wiring `provenance_required` into the existing supervised-status decision path in
  `agy_delegate.py` — no new envelope field, no new schema version.
- Adding a fallback-reason string to the existing run-report and roll-up schemas in
  `engine_dispatch.py` / the session-end roll-up consumer.
- Extending `build_dispatch_manifest` with a `SUBSTITUTED` disposition branch and removing the
  one hand-built manifest-construction call site it replaces.
- A new `check_empty_delivery()` unit-boundary helper plus its wiring into the existing
  auto-commit-on-gate-pass flow.
- Adding `verifier_identity` / `fallback_depth` to the existing verify-spawn contract and one
  gate-side render rule consuming them.

**Non-goals / explicitly out of scope:**
- Building a new receipt/proof-of-execution contract (`bridge_receipt.v1`) — that is
  `pf-delegation-receipt-contract`'s scope (T15-F2-1/F1-1/F2-2); this issue consumes whatever
  evidence already exists at each site, it does not invent a new evidence shape.
- Real-time `PreToolUse`/`Stop`-hook tripwires that intercept a delegation while it is in
  flight — that is `pf-delegation-tripwires-audit`'s scope (T15-F2-3/F3-2/F5-4); this issue is
  about post-hoc status/disposition/reporting correctness, not runtime interception.
- Changing the fallback ladder's degrade-order or preserved sandbox axes documented at
  `{#readonly-verifier-fallback-ladder-325}` — this issue only adds attribution of which rung
  was used, it does not alter the ladder itself.
- Cross-bridge receipt ledgers, hash-chained custody, or orphan-liveness fencing tokens — those
  are separate T15 facets (F1-6/F1-7/F1-8/F2-7/F2-8/F4-4/F4-5) not absorbed into this issue.
- Redesigning the verifier-of-record model — Claude remains sole gate per
  `{#external-engines-never-gatekeepers}` (#283); this issue only makes existing checks fail
  loud, it does not grant any engine new gating authority.

## Grounding References

Absorbed ideas (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T15.json`):

- `T15-F3-1` (primary) — "Make the inert `provenance_required` field fail-loud instead of
  decorative." `dod_sketch`: merged PR gates on `provenance_required` in the supervised status
  decision so `unproven+required` coerces status to `fallback_suspected` and `exit!=0`; verified
  by oracle test red on today's code, green after wiring, plus CHANGELOG/plugin.json bump.
  Closes a real dead-wiring finding (field with zero consumer). Basis: `agy_delegate.py:100,
  137-139,154,261` (field threaded end to end, never consulted for status/exit).
- `T15-F1-4` (facet) — "Propagate resolver Claude-fallback reason to the merged artifact and
  operator." `dod_sketch`: merged PR carries resolver fallback reason into the unit run-report
  schema + session-end `DELEGATION_NOOP` roll-up; verified by test that a forced
  unavailable-engine offload produces a non-empty fallback reason in both the run report and the
  roll-up. Basis: `engine_dispatch.py:163-187` (`build_dispatch_manifest` sets disposition from
  `evidence.halt` with no reason-string propagation).
- `T15-F2-5` (facet) — "First-class `SUBSTITUTED` disposition — remove the hand-built fallback
  manifest." `dod_sketch`: merged PR extends `build_dispatch_manifest` with a `SUBSTITUTED`
  disposition keyed off the bridge receipt and deletes the chaperone hand-build path; verified
  by test that a zero-invocation run yields a `SUBSTITUTED` manifest with `kind=CLAUDE`
  attribution automatically. Basis: `external-engine-workers.md:163-168` (documents the
  hand-build workaround in prose as today's only path).
- `T15-F2-4` (facet) — "Empty-delivery HALT at every unit boundary — automate 'commit each unit
  as it lands.'" `dod_sketch`: merged PR adds unit-boundary `check_empty_delivery()` +
  auto-commit-on-gate-pass; verified by test that a delegated unit writing nothing HALTs (not
  silent hand-off) and a delivering unit auto-commits and advances. Basis:
  `docs/engineering-journal/LEARNINGS.md:337-347` (`{#delegate-orphan-late-write}` — orphan
  wrote 72 minutes late, caught only by manual `git status`).
- `T15-F1-3` (facet) — "Attributed verify-spawn fallback ladder — descent must be visible to the
  consumer." `dod_sketch`: merged PR adds `verifier_identity`/`fallback_depth` to the
  verify-spawn contract + gate-side render rule; verified by fixture test that a tier-2 verify
  surfaces as "fallback tier 2" in the gate summary. Engages
  `{#readonly-verifier-fallback-ladder-325}` revisit-when (ladder + worktree preserved,
  attribution-only). Basis: `plugins/saga/references/sandbox-spawn-sites.md:57-76`.

Recurring-pain theme this issue closes: grounding brief §6 ("Silent no-ops in delegation & dead
wiring", 5+ journal learnings) — theme candidate 15, "delegation integrity"
(`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:99-104`).

Binding decisions this capability builds on and must not violate:
- `{#external-engines-never-gatekeepers}` (#283) — Claude stays verifier-of-record; this issue
  only makes existing checks fail loud, it grants no engine new gating authority.
- `{#external-engine-chaperone-dispatch}` (#318) — external engines remain
  offload/second-opinion workers only; no change to executor kind or team residency.
- `{#readonly-verifier-fallback-ladder-325}` — the two-step degrade ladder (`Explore` + worktree,
  then `general-purpose` + worktree with explicit read-only instruction) is preserved as-is;
  this issue adds attribution of which rung fired, not a change to the ladder's order or
  contract.
- `{#dead-wiring-needs-producer-and-consumer}` — the generalizable rule this entire issue applies
  five times over: a field or check is only real once both its producer and its consumer exist
  and are wired together.

Current-state citations (2026-07-03, verified against the tree at issue-drafting time):
`plugins/agy/scripts/agy_delegate.py:100,137-139,154,261,885,989-1022,1595-1614`;
`plugins/saga/scripts/engine_dispatch.py:97,163-187`;
`plugins/saga/references/sandbox-spawn-sites.md:57-76`;
`plugins/team-execution/skills/team-execution/references/external-engine-workers.md:158-168`;
`docs/engineering-journal/LEARNINGS.md:293-347,471-483`.

### Recommended executor profile

- **Model:** sonnet
- **Effort:** medium
- **Backend:** inline
- **External-LLM posture:** none
- **Justification:** every facet is a mechanical wiring fix — connect an already-defined field
  or already-documented disposition/reason to a status/exit-code/render decision that currently
  ignores it. None of the five facets requires novel architecture or ambiguous design judgment;
  each has a concrete, cited current-state gap and a named target behavior. Sonnet at medium
  effort, run inline, matches this shape; no external-engine offload or opus-tier judgment call
  is warranted here.

### Release-surface checklist (plugin behavior changes — required)

- [ ] `plugins/agy/.claude-plugin/plugin.json` — version bump + description update reflecting
  `provenance_required` now gating status/exit code.
- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump + description update reflecting
  the `SUBSTITUTED` disposition addition to `build_dispatch_manifest`, the fallback-reason
  propagation into the run-report/roll-up schemas, and the verify-spawn
  `verifier_identity`/`fallback_depth` attribution.
- [ ] `plugins/team-execution/.claude-plugin/plugin.json` — version bump if the chaperone's
  hand-built manifest call site (in team-execution's references/scripts) is edited or removed as
  part of deleting the hand-build path.
- [ ] `.claude-plugin/marketplace.json` — all touched plugin entries' version/description kept
  in sync with the bumps above.
- [ ] `plugins/agy/CHANGELOG.md` — entry documenting `provenance_required` becoming a
  status/exit-code gate (behavior change: previously-passing unproven runs with
  `provenance_required=True` now fail loud).
- [ ] `plugins/saga/CHANGELOG.md` — entry documenting the `SUBSTITUTED` disposition addition,
  fallback-reason propagation, and verify-spawn fallback attribution.
- [ ] `plugins/team-execution/CHANGELOG.md` — entry documenting removal of the chaperone's
  hand-built manifest-construction path in favor of the shared builder's new `SUBSTITUTED`
  branch.
- [ ] Version/metadata drift-guard tests (if present in `tests/`, e.g.
  `test_saga_plugin.py`, `test_agy_plugin.py`) updated or extended so
  `plugin.json`/`marketplace.json`/`CHANGELOG.md` tell the same story as the diff.

### Files expected to change

Indicative only — exact set is `/plan`'s to determine.

- `plugins/agy/scripts/agy_delegate.py` — wire `provenance_required` into the status decision
  (`decide_non_apply_status`) and the exit-code path.
- `plugins/saga/scripts/engine_dispatch.py` — `build_dispatch_manifest` gains a `SUBSTITUTED`
  disposition branch; fallback-reason threaded into the dispatch manifest / run report.
- `plugins/saga/scripts/provenance_manifest.py` — disposition handling for the new
  `SUBSTITUTED` branch consumed by `build_dispatch_manifest` rather than hand-constructed.
- `plugins/team-execution/skills/team-execution/references/external-engine-workers.md` — remove
  the documented hand-build workaround, point at the shared builder's new branch instead.
- `plugins/saga/references/sandbox-spawn-sites.md` — document the new
  `verifier_identity`/`fallback_depth` attribution fields on the verify-spawn contract.
- New: `plugins/saga/scripts/check_empty_delivery.py` (or equivalent module) — unit-boundary
  empty-delivery HALT + auto-commit-on-gate-pass helper (proposed path).
- `tests/test_agy_delegate.py` — provenance_required-coerces-fallback tests.
- `tests/test_engine_dispatch.py` — fallback-reason-propagation and substituted-disposition
  tests.
- `tests/test_check_empty_delivery.py` — new test module for the empty-delivery HALT.
- `tests/test_verify_spawn_gate_summary.py` — new or extended test module for fallback-tier
  attribution rendering.

### Tests to add or update

- `test_agy_delegate.py -k provenance_required_coerces_fallback` — unproven + required →
  `fallback_suspected` status, non-zero exit; unproven + not-required → unchanged behavior.
- `test_engine_dispatch.py -k fallback_reason_propagation` — forced unavailable-engine offload
  produces a non-empty reason string in both the run report and the roll-up.
- `test_engine_dispatch.py -k substituted_disposition` — zero-invocation run yields
  `SUBSTITUTED` + `kind=CLAUDE` via the shared builder; no remaining hand-build call site.
- `test_check_empty_delivery.py -k halts_on_empty_delivery` / `-k autocommits_on_delivery` —
  empty unit HALTs, delivering unit auto-commits and advances.
- `test_verify_spawn_gate_summary.py -k fallback_tier_2_rendered` / `-k
  no_fallback_marker_on_first_choice` — gate summary renders fallback depth only when a
  fallback rung was actually used.

### Verification

```bash
# Facet-specific tests
uv run pytest tests/test_agy_delegate.py -k provenance_required_coerces_fallback -v
uv run pytest tests/test_engine_dispatch.py -k "fallback_reason_propagation or substituted_disposition" -v
uv run pytest tests/test_check_empty_delivery.py -v
uv run pytest tests/test_verify_spawn_gate_summary.py -v
# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all green; the `provenance_required` and `substituted_disposition` tests must be
demonstrably red against today's code before the fix lands (run them on a clean checkout of
`main` first to confirm the regression they close is real, not vacuous).

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T15.json (ids: T15-F3-1
  (primary), T15-F1-4, T15-F2-5, T15-F2-4, T15-F1-3 (facets))
- Source type: ideation issue-map
- Source title: No silent Claude-fallback: fail-loud provenance_required, SUBSTITUTED
  disposition, fallback-reason propagation, empty-delivery HALT, attributed verify-fallback

### Context library links

_none_

### Intent

The fleet has a recorded, repeated failure mode: a run claimed as "delegated to an external engine" turns out to be Claude doing the work itself, with nothing in the system that fails loud about it. This is not hypothetical — it is a five-times-recurring class of finding in this repo's own journal, and the current code has at least one live, provably decorative guard-rail meant to catch it:

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/390
- Number: 390
- Created at: 2026-07-04T07:58:26.740013+00:00

