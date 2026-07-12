---
title: Positive handoff protocol at the saga -> deploy boundary (issue #395)
type: feat
status: active
date: 2026-07-12
origin: docs/plans/2026-07-03-plugin-fleet-grounding-brief.md
---

# Positive handoff protocol at the saga -> deploy boundary (issue #395)

## Summary

Add a handoff-ack envelope (ack token + gate-or-auto payload) at the saga -> deploy edge: a new
`plugins/saga/scripts/deploy_handoff.py` sidecar module mints the offer when `/work` releases a
merged item toward deploy, deploy explicitly accepts by writing an ack, and until that ack exists
the item's derived status reads "handed off, unacknowledged" — never silently "done". The
gate-or-auto answer is captured once at intent time (a new optional saga field) and travels with
the baton; a `gate` payload can never be silently overridden to auto-fire on the deploy side.

## Problem Frame

`/work` owns the PR loop through merge and explicitly disclaims deploy
(`plugins/saga/skills/work/SKILL.md`, "Hard boundary"). Nothing today requires deploy to
acknowledge picking a merged item up: `handoff_envelope.py` (172 lines) emits only a
mission-control-facing envelope with no ack and no gate-or-auto payload, and
`plugins/deploy/skills/deploy-state/SKILL.md` has no acceptance side at all. A merge can land
with no plugin visibly holding the item — the dropped baton is invisible. Issue #395 (maturity:
requirements-ready) carries the settled WHAT; this plan settles the HOW. This is the last leaf
(sub-395) of the ship-ceremony-hardening outcome (objective #340).

## Requirements

Mirrored from issue #395 (authoritative WHAT), refined with grounded file references.

- **R1.** A handoff-ack envelope schema (ack token + gate-or-auto payload) exists at the
  saga -> deploy edge — a sibling module `plugins/saga/scripts/deploy_handoff.py` that
  `handoff_envelope.py` calls, distinct from the existing mission-control envelope.
- **R2.** The envelope's gate-or-auto payload is read from the operator-authored intent-capture
  posture, never re-derived or re-asked at handoff time. No durable field exists today
  (`lifecycle_state.destination_includes_deploy` at `plugins/saga/scripts/lifecycle_state.py:39-42`
  answers only *whether* deploy is wanted) — KTD3 defines the minimal interim source the issue
  delegates to plan time.
- **R3.** A durable saga-scoped record captures the acknowledged transfer
  (`{token, acknowledged_at, acknowledged_by, evidence}`), written only on the deploy side's
  explicit accept — never by the releasing side's offer.
- **R4.** Ownership is not released until the ack is recorded: a status/reconcile read derives
  "handed-off-unacknowledged" for an offer without an ack (derive-on-read discipline,
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:48`).
- **R5.** Deploy's authorization decision consults the payload: `gate` blocks auto-promotion
  pending explicit confirmation; `auto` authorizes nonprod promotion only. A `gate` payload is
  never silently overridden to auto-fire.
- **R6.** Deploy-side docs (`plugins/deploy/skills/deploy-state/SKILL.md` + `commands/deploy.md`)
  document the acceptance step so the contract is discoverable from the deploy side.
- **R7.** `/work`'s hard boundary is unchanged — merge stays a confirmed git op `/work` owns,
  advisory `/qa` routing intact; this adds an acceptance step on the side `/work` already
  disclaims (AC7 verifies the "Hard boundary" section's substantive language is preserved).

## Key Technical Decisions

**KTD1 — New sibling module `deploy_handoff.py`; `handoff_envelope.py` gains a thin delegating
builder:** keeps the mission-control envelope untouched (R1's "sibling module it calls",
verbatim), gives the deploy edge its own single-writer module, and avoids any cross-plugin Python
import — deploy's docs shell out to the saga script, which `deploy-state/SKILL.md` already
sanctions ("Runtime scratch belongs under ignored local state such as `.claude/saga/`").

**KTD2 — Storage is the per-saga sidecar `.claude/saga/sagas/<saga_id>/deploy_handoff.json`:**
`{envelope: {token, payload, offered_at, offered_by, saga_id, pr_refs}, ack: {token,
acknowledged_at, acknowledged_by, evidence} | null, superseded: [...]}`. Follows the established
sidecar discipline (DECISIONS `{#ceremony-sidecars-forward-only-undo-346}` and
`{#ship-teardown-terminal-gate-347}`): atomic write, saga-id regex hardening
(`[A-Za-z0-9][A-Za-z0-9._-]*`), single-writer, no `state.json` contention. R3's "saga field" is
satisfied as a saga-scoped durable record — the same interpretation `opened_resources.json` and
`ship_receipt.json` already carry.

**KTD3 — Interim intent-capture source is a new optional saga save flag `--deploy-autonomy
{gate,auto}`:** captured once at `/plan` Phase 5.1 as a follow-up only when destination is
`nonprod-deploy`; absent -> `gate` (the safe direction R5 mandates — a missing posture can never
auto-fire). The envelope reads `saga.deploy_autonomy or "gate"` at offer time and never re-asks
(R2). The issue explicitly delegates this source choice to plan time ("Dependencies /
Assumptions"). Revisit when the fleet intent-envelope work lands a richer posture field.

**KTD4 — Ack is write-once; re-offer rotates the token:** double-accept raises a named error
(mirrors `ship_receipt.ReceiptExistsError`); accept-without-offer refuses fail-loud; a repeat
`offer` (crashed deploy run, F2 recovery) mints a fresh token and moves the old envelope to
`superseded` so a stale token can never be acked. `acknowledged_by` and `evidence` must be
non-empty.

**KTD5 — Gate honored mechanically, not by convention:** `authorize_promotion(record, env)`
returns blocked/authorized — `gate` -> blocked pending explicit confirmation; `auto` -> authorized
for `nonprod` only; `staging`/`production` always require confirmation regardless of payload
(deploy's existing promotion mechanics are a non-goal and unchanged).

**KTD6 — Dropped baton is derived on read:** `deploy_handoff.py reconcile` (read-only) lists
offers without acks as `handed-off-unacknowledged`; no committed status field anywhere
(grounding-brief derive-on-read binding decision). A standing scheduled sweep stays out of scope
(issue non-goal).

**KTD7 — Every AC `-k` selector collects in the issue-named file `tests/test_handoff_envelope.py`:**
direct lesson from #347's P2 (AC6 selector collected zero tests). The five selector substrings —
`ack_envelope_schema`, `ownership_not_released_without_ack`, `gate_or_auto_propagation`,
`ack_round_trip`, `dropped_baton_detected` — all land as test names in that file.

## Implementation Units

### U1. `deploy_handoff.py` module + envelope schema + `handoff_envelope.py` hook

**Goal:** the sidecar module owning mint/offer/accept/authorize with hardening, plus the thin
`build_deploy_handoff_envelope()` delegator in `handoff_envelope.py`.

**Files:** `plugins/saga/scripts/deploy_handoff.py` (new),
`plugins/saga/scripts/handoff_envelope.py` (delegating builder only),
`tests/test_handoff_envelope.py` (new).

**Scope:** envelope schema per KTD2; `offer` (mint token via `secrets.token_hex`, payload
defaults `gate` in this unit — the saga-record read that derives it lands in U2, atomic sidecar
write, supersede-on-reoffer per KTD4); `accept` (write-once ack, named
errors for double-accept / no-offer / token mismatch / empty identity or evidence);
`authorize_promotion` per KTD5; saga-id validation; CLI verbs `offer` / `accept` / `read`; all
errors caught at the CLI boundary (exit 1 + message, never a traceback).

**Test scenarios** (in `tests/test_handoff_envelope.py`, KTD7): `test_ack_envelope_schema_*` —
schema fields present, JSON round-trip (AC1); `test_ack_round_trip_*` — token + timestamp +
identity survive save/load (AC4); double-accept refused with prior ack intact;
accept-without-offer refused; stale (superseded) token refused; empty `--by`/`--evidence`
refused; malformed sidecar JSON -> named error; existing `build_handoff_envelope` output
byte-unchanged (regression).

### U2. Intent capture: `--deploy-autonomy` saga field + propagation into the payload

**Goal:** the gate-or-auto posture gets a durable home written once at intent time and read (not
re-asked) at offer time (R2, KTD3).

**Depends on:** U1.

**Files:** `plugins/saga/scripts/saga.py` (`--deploy-autonomy {gate,auto}` on `save`, persisted
field), `plugins/saga/references/saga-spec.md` (field row + `/plan` consumer row),
`plugins/saga/skills/plan/SKILL.md` (Phase 5.1: follow-up question only when destination is
`nonprod-deploy`), `plugins/saga/scripts/deploy_handoff.py` (offer reads the saga record via the
`read_state(root)["sagas"][saga_id]` pattern — precedent `handoff_envelope.py:57` — sourcing
`deploy_autonomy` and `pr_refs` from the same record; either absent -> `gate` / empty list),
`tests/test_handoff_envelope.py`.

**Test scenarios:** `test_gate_or_auto_propagation_*` — saga saved with `auto` -> envelope payload
`auto` authorizes nonprod, blocks staging/production; saved with `gate` -> blocked pending
confirmation; field absent -> payload defaults `gate` (AC3, R5 safe direction); posture is read
from the saga record, not from an offer-time argument (no CLI flag can override it — R2).

### U3. Ownership gating + dropped-baton reconcile read

**Goal:** derived status honors "not released until acked" (R4) and surfaces the dropped baton
(F2) on a read.

**Depends on:** U1.

**Files:** `plugins/saga/scripts/deploy_handoff.py` (`reconcile` verb — read-only, per-saga and
`--all` sweep across `.claude/saga/sagas/*/deploy_handoff.json`), `tests/test_handoff_envelope.py`.

**Test scenarios:** `test_ownership_not_released_without_ack_*` — offer present, ack absent ->
derived status is `handed-off-unacknowledged`, never `deployed`/`done` (AC2);
`test_dropped_baton_detected_*` — merged-then-silence scenario surfaces on `reconcile` naming the
saga and offer age (AC5); exit-code convention follows the `ship_receipt.py read` precedent
(0 = clean or no-handoff, 1 = unacknowledged or error); acked handoff reads
`accepted`; no sidecar at all reads `no-handoff` (not an error).

### U4. Boundary docs on both sides of the edge

**Goal:** the contract is discoverable from saga's handoff skill AND deploy's skill/command docs
(R6), without touching `/work`'s hard boundary (R7).

**Depends on:** U1, U2.

**Files:** `plugins/saga/skills/handoff/SKILL.md` (new "Deploy edge" section: offer/ack contract,
gate-or-auto carriage — beside the existing mission-control boundary language),
`plugins/deploy/skills/deploy-state/SKILL.md` (new "Accepting a saga handoff" section: run
`deploy_handoff.py accept` before promotion on behalf of a saga-tracked item; consult
`authorize_promotion` — `gate` never auto-fires), `plugins/deploy/commands/deploy.md` (acceptance
step in Instructions), `plugins/saga/skills/work/SKILL.md` (one routing-section pointer to the
offer step; "Hard boundary" section substantive language preserved — AC7).

**Test expectation:** none — docs unit; AC6 is a grep check
(`grep -n "ack" plugins/deploy/skills/deploy-state/SKILL.md`) and AC7 is a reviewer diff check on
the "Hard boundary" section.

### U5. Release surfaces: both plugins, marketplace, changelogs, drift guards

**Goal:** installed-plugin metadata tells the same story as the diff (repo rule).

**Depends on:** U1-U4.

**Files:** `plugins/saga/.claude-plugin/plugin.json` (0.78.0 -> 0.79.0),
`plugins/deploy/.claude-plugin/plugin.json` (0.1.4 -> 0.2.0 — new acceptance behavior),
`.claude-plugin/marketplace.json` (both entries), `plugins/saga/CHANGELOG.md`,
`plugins/deploy/CHANGELOG.md`, `tests/test_saga_plugin.py` (pin at line 49 -> 0.79.0),
`tests/test_deploy_plugin.py` (pin at line 42 -> 0.2.0).

**Test scenarios:** existing drift-guard tests updated to the new pins; full-suite green.

## Scope Boundaries

**Out of scope (issue non-goals, carried forward):** no symmetric ack on the saga ->
mission-control edge; no change to deploy's tag-promotion / canary / rollback mechanics or
environment model; no change to `/work`'s hard boundary or advisory `/qa` routing; no new
autonomy allowlist or reversibility classifier (the posture is consumed as given); no standing
scheduled sweep of stale handoffs (the `reconcile` read makes the gap observable — a cron/hook
sweep is a candidate fast-follow).

**Deferred to Follow-Up Work:** wiring `reconcile --all` into the `/outcome` cockpit or
`status_card.py`; migrating KTD3's interim `deploy_autonomy` field onto the fleet intent-envelope
posture when that lands; ship-ceremony auto-offer at the merge transition (this plan documents
the offer step in `/work` routing guidance rather than wiring `ship_ceremony.py` — keeps the
ceremony diff zero for this issue).

## Risk Analysis

- **Sharpest risk — cold `gate` default surprising an `auto`-intent operator:** an operator who
  chose `nonprod-deploy` before this feature exists has no `deploy_autonomy` field, so their
  envelope reads `gate` and deploy asks once more. That is the correct failure direction (an
  extra confirmation, never an unwanted auto-fire) and self-heals for sagas planned on the new
  `/plan` question.
- **Sidecar is machine-local:** a deploy run on a different machine cannot read the offer. Same
  accepted trade as `{#ceremony-sidecars-forward-only-undo-346}` ("revisit when a second consumer
  needs the sidecar cross-machine"); the ack's durable public echo is deploy's existing
  issue-comment evidence convention.
- **Scope creep vector — deploy scripts:** `mint_tag.py` gains no gating logic in this plan;
  `authorize_promotion` lives saga-side and the deploy docs mandate consulting it. Changing
  `mint_tag.py` behavior would widen the blast radius past the issue's non-goals.
