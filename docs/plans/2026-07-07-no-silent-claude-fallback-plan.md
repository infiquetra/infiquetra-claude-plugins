---
title: No silent Claude-fallback — fail-loud provenance wiring across the delegation lane
type: fix
status: active
date: 2026-07-07
origin: infiquetra/infiquetra-claude-plugins#390
---

# No silent Claude-fallback — fail-loud provenance wiring across the delegation lane

## Summary

Close five dead-wiring gaps where a delegation check has a producer but no consumer: wire
`provenance_required` into agy's status/exit decision, auto-derive `SUBSTITUTED_ENGINE` inside
`build_dispatch_manifest` (deleting the documented hand-build path), refuse substituted evidence at
`satisfy_gate`, surface fallback reasons in the manifest roll-up, add an empty-delivery HALT at the
delegated-unit boundary, and attribute verify-spawn fallback depth in the gate summary.

## Problem Frame

Issue #390 (sub-390 of outcome #336) names a five-times-recurring journal failure class: a run
claimed as "delegated" that Claude actually did itself, with nothing failing loud. The issue body
was drafted 2026-07-03; PRs #516/#518/#521/#522 have since landed on the same files, so this plan
re-grounds every citation. Two scope-note comments on the issue (2026-07-06) are canonical
amendments: facet 3 narrows to auto-derivation only (`SUBSTITUTED_ENGINE` already exists), and #390
now owns closed #392's surviving facet — the invocation-proof / fail-loud discriminator for the
team-execution external-engine worker slot.

**Re-grounding deltas vs the issue body (verified 2026-07-07 on `main@5d45bed`):**

| Issue claim (2026-07-03) | Today's reality | Plan response |
|---|---|---|
| `build_dispatch_manifest` "only inspects `evidence.halt`" | Now derives 4 dispositions incl. `DELEGATION_INTEGRITY` + `UNPROVEN` (`engine_dispatch.py:443-506`) | Add only the missing `SUBSTITUTED` branch (U2) |
| Fallback reason reaches nothing | Reason already lands in `disposition_note` (`engine_dispatch.py:476-478`) | Remaining gap is the operator surface (U4) |
| "session-end `DELEGATION_NOOP` roll-up" | Does not exist — zero grep hits repo-wide | Wire the real surface: `manifest_reader` R18 report (KTD2) |
| "auto-commit-on-gate-pass flow" to wire into | No such machinery; `/optimize` explicitly shed it | Gate the chaperone's existing documented commit step (KTD6) |
| Tests in `test_agy_delegate.py` / `test_engine_dispatch.py` | Real homes: `tests/test_agy_delegate_contract.py`, `tests/test_saga_engine_dispatch.py` | Corrected test paths throughout |
| No unit-boundary delivery check | `record-completeness` `missing-output` trip exists (`manifest_store.py:249-363`) — returned-value axis only | U5 covers the distinct file-delivery axis |

**Facet 1 confirmed live:** `provenance_required` is defined, parsed, and threaded
(`agy_delegate.py:106,143-145,160,267`) but consulted nowhere — not in `decide_non_apply_status`
(`:891-905`), not in `_real_agy_verdict` (`:1627-1635`, the wrapper's own "real"/"unproven"
supervision verdict, consumed only by the supervision report at `:1622`), not in the exit mapping
(`:1167`). A caller can demand provenance and get exit 0 on an unproven run. Note:
`classify_transcript` (`:995-1021`) has NO run-path call site in the wrapper — #384 moved
transcript auditing to the fleet-core Stop-hook and pinned agy's copy as fixture-parity only —
so the in-wrapper consumer must key off `_real_agy_verdict`, never re-introduce in-run
transcript auditing.

**#392 facet confirmed live:** `satisfy_gate` (`engine_dispatch.py:585-625`) refuses unverified,
uncorroborated, and unadjudicated evidence — but never checks `disposition`. A substituted run
carrying valid corroboration *for the wrong engine* would pass the gate as if it ran as approved.

## Requirements

- R1. A passing status (`success`/`patch_ready`/`applied`) whose supervision verdict
  (`_real_agy_verdict`) is `unproven`, combined with `provenance_required=True`, coerces the run
  status to `fallback_suspected` and the process exits non-zero via the existing
  `agy_delegate.py:1167` mapping; with `provenance_required=False` behavior is unchanged, and a
  status already `fallback_suspected` (via the stdout marker, `:1374`) is not double-coerced.
- R2. `build_dispatch_manifest` auto-derives `Disposition.SUBSTITUTED_ENGINE` when the evidence
  carries an expected engine identity that differs from the resolved `engine_id/variant`; the
  `disposition_note` names both identities.
- R3. Every manifest whose disposition is not `RAN_AS_REQUESTED` carries a non-empty,
  human-readable `disposition_note` (builder-enforced invariant).
- R4. `satisfy_gate` refuses a manifest whose disposition is `SUBSTITUTED_ENGINE` — substituted
  evidence can never satisfy a gate as-approved (the #392 fail-loud discriminator).
- R5. The chaperone contract has exactly one manifest-construction path: the documented hand-build
  of `provenance_manifest.Manifest` (`external-engine-workers.md:174` region) is deleted;
  `grep -rn "pm.Disposition.SUBSTITUTED_ENGINE" plugins/` finds only shared-builder and test
  references — no contract-doc hand-build instruction remains.
- R6. The manifest roll-up surface (`manifest_reader` report) renders the reason note for every
  non-`RAN_AS_REQUESTED` manifest, so a forced fallback is traceable to prose, not just an enum.
- R7. A delegated unit that claims delivery but changed zero paths HALTs with a typed verdict at
  the unit boundary; a delivering unit receives a proceed verdict that authorizes the existing
  documented chaperone commit step. The check is distinct from `record-completeness`'s
  returned-value `missing-output` trip.
- R8. Verify-panel verdicts carry `verifier_identity` and `fallback_depth`; the panel gate summary
  renders an explicit "fallback tier N" marker when any reporter's depth exceeds 0 and no marker
  for a first-choice `saga:readonly-verifier` pass. The fallback ladder itself is unchanged.
- R9. Release surfaces move together: agy, saga, and team-execution `plugin.json` +
  `.claude-plugin/marketplace.json` + three CHANGELOGs + version drift-guard test pins.
- R10. Full gate green (`uv run pytest`, `ruff check` + `ruff format --check`, mypy CI scope); the
  R1 and R2 regression tests are demonstrated red against pre-fix `main` before the fix lands.

## Key Technical Decisions

KTD1 — Wire `provenance_required` as a post-classification status coercion in `agy_delegate.py`,
reusing the existing status vocabulary and the `:1167` exit mapping: the smallest consumer that
closes the dead wire — no new exit codes, no envelope schema change, no new result fields beyond a
provenance note recording the coercion. Rejected: a dedicated exit code (callers already branch on
the status set).

KTD2 — Re-ground facet 2 onto consumers that exist: the reason already reaches
`disposition_note` (#384); the missing consumer is `manifest_reader`'s R18 report. Do NOT invent a
`DELEGATION_NOOP` roll-up (zero grep hits — the issue named machinery that was never built), and do
NOT write run-fact-ledger records — `run_ledger.py`'s docstring assigns those writers to #386/#393.

KTD3 — The substitution baseline is an optional `expected_identity` ("engine/variant") threaded
into `dispatch()` and stamped into evidence provenance, mirroring the additive-defaulted
`runner_receipt` precedent (`engine_dispatch.py:41-55`): the builder stays a pure function of
evidence, the resolver/registry stay untouched (clean seam for #388), and callers without a
plan-time preview (`expected_identity=None`) keep today's behavior exactly.

KTD4 — Disposition branch precedence: `DELEGATION_INTEGRITY` > halt (`FELL_BACK_TO_CLAUDE`) >
`SUBSTITUTED_ENGINE` > receipt check (`UNPROVEN`/`RAN_AS_REQUESTED`). Observer contradiction
outranks everything; nothing-ran outranks wrong-thing-ran; substitution is an affirmative
contradiction so it outranks mere proof-absence — a valid receipt for the wrong engine must never
yield `RAN_AS_REQUESTED`.

KTD5 — The #392 fail-loud leg lives in `satisfy_gate`, not as a dispatch-time exception: #390 is
post-hoc status/disposition/reporting correctness by its own scope line, so dispatch still records
honest evidence and the gate is where loudness is owed. Rejected: raising inside
`build_dispatch_manifest` (would lose the manifest record itself).

KTD6 — Empty-delivery is a new small `plugins/saga/scripts/check_empty_delivery.py` helper (pure
verdict function + CLI) that GATES the chaperone's existing documented commit step
(`external-engine-workers.md` §5.2 "the chaperone … owns the commit"); no new auto-commit machinery
is minted — none exists, and `/optimize` deliberately shed its own. The file-delivery axis is kept
distinct from `record-completeness`'s returned-value axis (`manifest_store.py:249-363`).

KTD7 — Verifier attribution is emitter-stamped where the spawner is code and self-recorded where
the spawner is Claude prose: `execution_spec.py` stamps `verifier_identity` into the verdict schema
it already forces (`:1326-1332`) with `fallback_depth` defaulting to 0 (a workflow `agent()` call
cannot silently descend the ladder — an unresolvable agentType fails the call); the inline
prose-ladder rule in `sandbox-spawn-sites.md` gains the recording requirement for rungs 2/3. The
render rule is a pure function so the gate-summary marker is unit-testable.

## Implementation Units

### U1. agy — `provenance_required` becomes a status/exit consumer

**Goal:** close the facet-1 dead wire in `plugins/agy/scripts/agy_delegate.py`.

**Changes:** where the result payload is assembled (`_result_payload`, `:1416-1454`, called at
`:415/:474/:612`), coerce a passing status to `fallback_suspected` when
`envelope.provenance_required` is true and `_real_agy_verdict(run_result)` is `unproven`; record
the coercion reason in the payload (e.g. `coerced_by: provenance_required`). Exit behavior
arrives free via `:1167`. Do not call `classify_transcript` in the run path — transcript
auditing is the Stop-hook's (#384); the wrapper's signal is `_real_agy_verdict` alone.

**Boundary (#523):** the upstream bug where the wrapper maps an executor-construction failure to
`success` with `bytes_produced: 0` stays #523's — this unit wires classification *output* to
status/exit; once #523 fixes the classifier input, this coercion makes it fail loud automatically.

**Test scenarios** (`tests/test_agy_delegate_contract.py`, selector
`provenance_required_coerces_fallback`): unproven + required → `fallback_suspected` + exit 1;
unproven + not-required → status unchanged + exit 0; proven (`real` verdict) + required →
unchanged; status already `fallback_suspected` (marker path) + required → stays
`fallback_suspected`, no double-coercion, still exit 1.
Oracle discipline: run the new tests against pre-fix `main` first and record them red (R10).

### U2. saga — `SUBSTITUTED_ENGINE` auto-derivation + gate refusal + note invariant

**Goal:** the shared builder expresses substitution itself and the gate refuses it (R2, R3, R4).

**Changes** in `plugins/saga/scripts/engine_dispatch.py`: `dispatch()` gains optional
`expected_identity`; stamped into evidence provenance. `build_dispatch_manifest` gains the
`SUBSTITUTED_ENGINE` branch at KTD4 precedence with a note naming expected vs resolved. Enforce
the R3 non-empty-note invariant with a fixed fallback string for degenerate empty reasons.
`satisfy_gate` refuses `disposition == SUBSTITUTED_ENGINE` (KTD5).

**Test scenarios** (`tests/test_saga_engine_dispatch.py`, selectors `substituted_disposition`,
`fallback_reason`): expected ≠ resolved → `SUBSTITUTED_ENGINE` + both identities in note; expected
= resolved → unchanged path; `expected_identity=None` → today's behavior byte-for-byte; halt +
mismatch → halt branch wins; mismatch + schema-valid receipt → still `SUBSTITUTED_ENGINE` (never
`RAN_AS_REQUESTED`); `satisfy_gate` on a substituted manifest → `DispatchError`; empty
halt/note → fixed non-empty reason string. Red-on-main demonstration for the derivation test (R10).

### U3. team-execution — delete the hand-build manifest path (depends on U2)

**Goal:** exactly one manifest-construction path (R5) and the #392 fold recorded in the contract.

**Changes:** rewrite `external-engine-workers.md` §5 step 4 to a single-path
`record_dispatch_manifest(..., expected_identity=<§4 preview>)` instruction; delete the documented
direct `provenance_manifest.Manifest` construction (`:163-176` region); update §4's "only reachable
substitution path" wording; refresh the stale `engine_dispatch.py:124-161`/`:153` line citations;
state the fail-loud discriminator (substituted ⇒ gate refusal) as the worker-slot contract.

**Test expectation:** doc-guard assertion that the contract file no longer instructs direct
`Manifest` construction and does reference `expected_identity` (default home:
`tests/test_manifest_consumer_matrix.py` beside the existing manifest-contract guards; `/work` may
place it with the other doc-drift guards if a better home exists). R5's grep check runs in U7.

### U4. saga — fallback reasons reach the operator roll-up (depends on U2)

**Goal:** the reason prose is readable where dispositions are already tallied (R6, KTD2).

**Changes:** `plugins/saga/scripts/manifest_reader.py` report gains a reasons section — for each
manifest with disposition ≠ `RAN_AS_REQUESTED`: execution id, disposition, `disposition_note`.

**Test scenarios** (`tests/test_manifest_reader.py`, selector `fallback_reason_propagation`):
forced-unavailable-engine manifest (halted dispatch) renders its resolver reason; substituted and
integrity rows render notes; all-`RAN_AS_REQUESTED` store renders no reasons section; empty store
unchanged.

### U5. saga — `check_empty_delivery()` at the delegated-unit boundary

**Goal:** empty delivery HALTs; real delivery proceeds to the existing commit step (R7, KTD6).

**Changes:** new `plugins/saga/scripts/check_empty_delivery.py` — pure verdict function (inputs:
changed paths, claims-delivery flag; output: typed HALT / proceed verdict) plus a thin CLI reading
`git status --porcelain -z`, exit non-zero on HALT. Wire into `external-engine-workers.md` §5
(check runs between verify and the chaperone-owned commit) and the `/work` unit-boundary prose for
delegated inline units.

**Test scenarios** (new `tests/test_check_empty_delivery.py`, selectors `halts_on_empty_delivery`,
`autocommits_on_delivery`): claims-delivery + zero paths → HALT; claims-delivery + paths → proceed
verdict authorizing the documented commit step (the "autocommit" selector asserts the proceed
verdict — the helper itself never commits); no-delivery-claimed + zero paths → ok (a legitimately
read-only unit); CLI outside a git repo → clean error, not a stack trace.

### U6. saga — attributed verify-spawn fallback (independent)

**Goal:** a degraded verify spawn is visible to the gate consumer (R8, KTD7).

**Changes:** `plugins/saga/scripts/execution_spec.py` — verifier verdict schema + prompt gain
`verifier_identity` (emitter-stamped) and `fallback_depth` (default 0); panel aggregation renders
"fallback tier N" in the panel summary/throw message via a pure render helper.
`plugins/saga/references/sandbox-spawn-sites.md` — the ladder section adds the rung-recording rule
for inline spawns. Ladder order/contract untouched (binding decision).

**Test scenarios** (new `tests/test_verify_spawn_gate_summary.py` for the render helper, plus
emitted-JS assertions in `tests/test_saga_execution_spec.py`): depth 2 → "fallback tier 2" marker;
depth 0 across panel → no marker; mixed panel (one rung-2 reporter among rung-0) → marker names the
degraded reporter only; emitted workflow JS carries the schema fields and stamped identity.

### U7. Release surfaces, journal, and full gate

**Goal:** installed-plugin metadata tells the same story as the diff (R9, R10).

**Changes:** minor version bumps + description updates for `plugins/agy`, `plugins/saga`,
`plugins/team-execution` `plugin.json`; root `.claude-plugin/marketplace.json` sync
(`scripts/sync_marketplace.py --check`); three CHANGELOG entries (agy's flags the behavior change:
previously-passing unproven runs with `provenance_required=True` now fail loud); drift-guard pins
(`tests/test_saga_plugin.py`, `tests/test_agy_plugin.py`, team-execution equivalent); DECISIONS
entry for the KTDs; R5 grep check; full gate run.

**Test expectation:** existing drift-guard suites updated; no new scenarios beyond pins.

## Scope Boundaries

**Out of scope (true non-goals):** new receipt/attestation shapes (#383 shipped the contract; #388
owns server-authoritative attestation inside the receipt-validation leg); runtime
PreToolUse/Stop-hook interception (#384 shipped it; #520 hardens it); observer/corroboration
hardening (#523 wrapper classification, #524 HTTP-lane `ENGINE_CONFIGS` row); fallback-ladder
redesign (attribution only, per binding decision); run-fact-ledger writers (#386/#393 per
`run_ledger.py` docstring); granting any engine gate authority (#283 — Claude stays
verifier-of-record; every change here makes existing checks fail loud, none adds engine authority).

**Deferred to Follow-Up Work:** rendering verifier attribution and fallback reasons in
`status_card.py` (the card's cell vocabulary gap is already a known cosmetic issue from the #468
drill); propagating dispatch reasons into the run-fact ledger once #386/#393 land their writers.

**Coordination seam (#388):** both issues touch `build_dispatch_manifest`'s derivation chain. #390
lands first (this plan); #388 extends the receipt-validation leg *below* KTD4's substitution branch
and rebases over it. Named here so neither plan silently rewrites the other's branch.

## Risks & Dependencies

- **agy behavior change is breaking for callers relying on exit 0 of unproven runs** — mitigated:
  `provenance_required` defaults to `True` in envelope parsing (`agy_delegate.py:143`), so the
  default posture flips to fail-loud; CHANGELOG flags it, and `engine_dispatch.py:146` (the saga
  dispatch envelope author) already sets it explicitly.
- **Branch-precedence regression in the builder** — the four existing dispositions have live
  consumers (drill manifests, tripwire tests); mitigated by the U2 "unchanged when
  `expected_identity=None`" scenarios and the existing `test_saga_engine_dispatch.py` suite (30K).
- **Doc-contract drift** (U3/U5 edit prose contracts agents execute) — mitigated by the doc-guard
  assertions and by keeping every behavioral statement pointing at the shared builder, not
  duplicated prose.

## Sources

Grounded 2026-07-07 against `main@5d45bed`: `plugins/agy/scripts/agy_delegate.py:106,143-145,160,
267,891-905,995-1021,1167,1374,1416-1454,1627-1635`; `plugins/saga/scripts/engine_dispatch.py:
41-55,146,197-207,443-506,585-625`; `plugins/saga/scripts/provenance_manifest.py:54-71`;
`plugins/saga/scripts/manifest_store.py:249-363`; `plugins/saga/scripts/manifest_reader.py:14,109`;
`plugins/saga/scripts/run_ledger.py:1-25`; `plugins/saga/scripts/execution_spec.py:105-115,
504-537,1326-1439`; `plugins/team-execution/skills/team-execution/references/
external-engine-workers.md:140-180`; `plugins/saga/references/sandbox-spawn-sites.md:50-80`;
issue #390 body + two scope-note comments (2026-07-06); LEARNINGS
`{#agy-delegate-silent-claude-fallback}`, `{#dead-wiring-needs-producer-and-consumer}`,
`{#zero-token-drill-marginal-fabrication}`.
