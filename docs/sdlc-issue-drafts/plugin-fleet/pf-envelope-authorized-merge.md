---
title: capability: envelope-authorized merge — AUTONOMOUS_UNDER_ENVELOPE write class with token check, revocation, and ledger attribution
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: high
handoff_maturity: requirements-ready
tier: moonshot
wave: wave-3
objective: Ship run-start intent envelope for lifecycle autonomy
---

# capability: envelope-authorized merge — AUTONOMOUS_UNDER_ENVELOPE write class with token check, revocation, and ledger attribution

### Objective
Ship run-start intent envelope for lifecycle autonomy

### Tier
moonshot

### Wave
wave-3

### Intent
`reversibility_certificate.py` is the single authority `/outcome` consults before any
autonomous mission-control write (`authorize_write`, `plugins/saga/scripts/reversibility_certificate.py:239`).
Its allowlist is closed by design: merge, deploy, and repo-level mutations are
**intentionally absent** from the registry and therefore always GATE
(`plugins/saga/scripts/reversibility_certificate.py:16,19,51`, requirement tag R20). This is
restated operationally in the outcome skill — "Merging PR" and "deploying" are listed
under "Never autonomous — always the operator's keystroke (never allowlisted)"
(`plugins/saga/skills/outcome/SKILL.md:104-107`).

That posture is a deliberate, previously-settled binding decision, not an oversight — the
grounding brief's binding-decision register records it verbatim: *"`/outcome` campaign
(U1–U11) | Derived-on-read status, never committed status fields; HALT-not-degrade;
backend menu off-by-default host-conditional degrade; cost ledger = leaf-produced fact"*
and separately notes *"PR merge/deploy documented 'never autonomous.'"*
(`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:30,48`).

The same binding decision carries its own revisit condition, and that condition has now
fired. The plugin-fleet intake brief's Autonomy Posture section requires the run-start
envelope dialog to ask, once, per outcome: *"Gate or auto merge / deploy-to-nonprod? ...
Merge/deploy is NOT unconditionally gated; operator decides per outcome, once, at start"*
(`docs/plans/2026-07-03-plugin-fleet-ideation-intake-brief.md:53-55`, Tension 3 /
Autonomy posture). This issue is the mechanism that answers that intake requirement
without silently loosening the never-autonomous default: it adds a new,
narrowly-scoped, revocable write class instead of removing merge/deploy's GATE-by-default
behavior for every case.

This is the sole "kept-alone" issue from the plugin-fleet consolidation pass precisely
because of that crossing: *"Kept alone: it crosses the never-autonomous-merge posture via
the intake §3 revisit condition and must be schedulable (and rejectable) independently of
everything else; default stays GATE"* (issue-map consolidation rationale for
`pf-envelope-authorized-merge`, absorbing `T7-F6-2`).

## Problem Frame

Today, `authorize_write` has exactly two verdicts — `AUTHORIZED` and `GATE` — and the
merge/deploy op kinds simply do not exist in `OpKind` or `_REGISTRY`
(`plugins/saga/scripts/reversibility_certificate.py:34-42` enumerates the closed
allowlist: `SET_FIELD_STATUS`, `ISSUE_LABEL_ADD`, `ISSUE_LABEL_REMOVE`,
`SUB_ISSUE_CLOSE`, `SUB_ISSUE_REOPEN`, `ISSUE_PROGRESS_COMMENT`, `PARENT_ISSUE_CLOSE`;
merge/deploy absent). There is no way, even in principle, for an operator to grant a
scoped, time-boxed, revocable exception for merge under a specific outcome's envelope —
the only two options are "GATE forever" (current default, correct for every
un-configured case) or "add merge to the permanent allowlist" (which nothing in this
repository proposes and which would violate R20 outright).

The board-sync side of the pipeline (`plugins/saga/scripts/outcome_board_sync.py`)
already has the pattern this capability needs to extend: it calls
`reversibility_certificate.authorize_write` per candidate op
(`outcome_board_sync.py:316`), GATEs with a visible `{status:"gated"}` record and no
silent skip (`outcome_board_sync.py:196`), and on `AUTHORIZED` checks a namespaced
board-sync ledger keyed by an idempotency key before writing
(`outcome_board_sync.py:197-211,337-340`). That ledger already stores *that* a write
happened and its idempotency key; it does not yet store *which envelope authorized it*.
This capability's job is to (a) introduce a new op kind and tier that only exists when an
active envelope token grants it, (b) plumb an `envelope_token` through
`authorize_write`, and (c) extend the ledger schema to attribute every authorized merge
write to the envelope id that authorized it — so a revoked or expired envelope can be
proven to have stopped authorizing merges, and every historical merge can be traced back
to the intent that permitted it.

## Requirements

R1. A new `OpKind` member (e.g. `MERGE_UNDER_ENVELOPE` or equivalent) and a new
`Tier.AUTONOMOUS_UNDER_ENVELOPE` (or a `always_operator=False` entry gated by an
additional envelope check layered in front of the existing tier system) are added to
`reversibility_certificate.py`. This class is **not** part of the base closed allowlist a
caller gets for free — it is inert (denies) unless an active, unexpired, unrevoked
envelope token authorizing merge is presented alongside the request.

R2. `authorize_write` (or a new sibling function that wraps it, to avoid changing the
signature every existing caller depends on) accepts an optional envelope-token
parameter. Absent a token, merge continues to GATE exactly as today (no regression to
R20's existing behavior for every caller that doesn't pass one).

R3. A token carries at minimum: envelope id, issuing outcome id, scope (must be
merge-only in this capability's v1 — deploy stays out of scope, see Non-Goals), an
expiry, and a revocation-checkable status. Token validity is re-checked at
authorization time, not cached from envelope creation.

R4. Revocation is effective immediately: once an envelope is revoked, the very next
`authorize_write` call presenting that envelope's token returns GATE, with no grace
window and no cached-authorized state surviving the revocation.

R5. The board-sync ledger schema (`outcome_board_sync.py`'s ledger record, currently
`{status, ...}` keyed by idempotency key per `_safe_ledger_name` /
`_board_sync_dir`, `outcome_board_sync.py:93-120`) gains an `authorizing_envelope_id`
field. Every ledger record written for a merge authorized under this write class
carries the id of the envelope that authorized it — non-merge ledger records are
unaffected (field is merge-authorization-specific, not a schema-wide change forced onto
unrelated op kinds).

R6. The issue text (this document) explicitly engages the never-autonomous binding's
revisit condition rather than silently reopening it: it cites the binding decision
(`reversibility_certificate.py:16,51`, R20; `outcome/SKILL.md:104-107`) and the revisit
condition that licenses this change (intake brief §3,
`2026-07-03-plugin-fleet-ideation-intake-brief.md:53-55`), and the default for every
outcome that does not explicitly configure an envelope stays GATE — this capability adds
an opt-in exception mechanism, it does not flip the default.

R7. No existing `authorize_write` caller's behavior changes for any op kind it already
authorizes (`SET_FIELD_STATUS`, `ISSUE_LABEL_ADD/REMOVE`, `SUB_ISSUE_CLOSE/REOPEN`,
`ISSUE_PROGRESS_COMMENT`, `PARENT_ISSUE_CLOSE`) — this is additive only.

### Acceptance criteria
- [ ] AC1 (covers R1, R2). Calling the merge-authorization path with no envelope token
  returns `GATE`. Check: a unit test in `tests/test_reversibility_certificate.py` (new
  or extended) asserts `authorize_write("merge-under-envelope")` (or the chosen op-kind
  string) with no token returns `Verdict.GATE`.
- [ ] AC2 (covers R2, R3). Calling the merge-authorization path with a valid,
  unexpired, unrevoked envelope token whose scope includes merge, and with all other
  outcome gates (PR reviews required, tests green, etc.) satisfied, returns
  `AUTHORIZED`. Check: unit test asserts `Verdict.AUTHORIZED` under this combined
  condition, and asserts `GATE` if any other required gate is not green (envelope
  authorization is necessary but not sufficient).
- [ ] AC3 (covers R4). After the same envelope is revoked, a subsequent call presenting
  the same token returns `GATE` again — re-DENIED, not cached-authorized. Check: unit
  test revokes the envelope between two `authorize_write` calls and asserts the second
  call's verdict flips to `GATE`.
- [ ] AC4 (covers R5). Every ledger record written for a merge authorized under this
  write class includes `authorizing_envelope_id` matching the envelope that authorized
  it. Check: unit test on `outcome_board_sync.py`'s ledger-write path (or the merge
  equivalent introduced by this capability) asserts the written ledger JSON contains the
  correct `authorizing_envelope_id` key and value.
- [ ] AC5 (covers R7). The full existing `reversibility_certificate` test suite and
  `outcome_board_sync` test suite continue to pass unmodified in behavior for every
  pre-existing op kind. Check: `uv run pytest tests/test_reversibility_certificate.py
  tests/test_outcome_board_sync.py -v` — all pre-existing cases pass unchanged.
- [ ] AC6 (covers R6). This issue's grounding section cites the never-autonomous binding
  (R20) and the intake §3 revisit condition it satisfies. Check: this document's
  "Intent" and "Problem Frame" sections contain both citations (present above).

### Out-of-scope / non-goals
**In scope**: merge authorization only, under an explicit, revocable, per-outcome
envelope token; extension of the board-sync ledger schema to attribute authorized
merges to their authorizing envelope; the token validity/revocation check itself.

**Out of scope / non-goals**:
- Deploy authorization. The intake brief's revisit condition names both merge and
  deploy-to-nonprod, but the absorbed idea and its `dod_sketch` scope this capability to
  merge only (`reversibility_certificate` + "board-sync ledger schema recording the
  authorizing envelope id" — no deploy-path changes are named). A follow-on issue should
  extend the same envelope-token mechanism to deploy once this merge-only slice is
  proven; do not bundle deploy into this PR.
- Changing the default behavior of `authorize_write` for any caller that does not pass
  an envelope token. GATE-by-default for merge/deploy in the absence of an envelope
  remains untouched.
- Building the envelope-issuance UX (the run-start dialog that asks "Gate or auto merge
  / deploy-to-nonprod?" per the intake brief). That dialog and its persistence format
  are the concern of the broader run-start intent envelope objective this issue ships
  under, not of this write-class-and-ledger capability. This issue only needs a token
  shape it can validate — the issuance side may be built as a companion issue under the
  same Objective.
- Any change to `PARENT_ISSUE_CLOSE`'s `ALWAYS_OPERATOR` tier or to the existing R20
  closed allowlist for the ops already enumerated in `_REGISTRY`.
- CLI/skill-level exposure beyond what's needed to exercise the acceptance criteria via
  tests; wiring this into `/outcome`'s live dispatch path end-to-end is expected to be a
  fast-follow once the certificate-level mechanism is proven, unless `/plan` determines
  it must ship atomically.

## Grounding References

- Absorbed idea: `T7-F6-2` — "Envelope-authorized merge in the `/outcome` autonomous
  allowlist" (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T7.json`, id
  `T7-F6-2`). Full `dod_sketch`: "Merged AUTONOMOUS_UNDER_ENVELOPE write class +
  envelope-token check in reversibility_certificate + board-sync ledger schema; certificate
  test asserts merge DENIED with no token, AUTHORIZED with a valid token + all gates
  green, and re-DENIED after revocation, each authorized merge carrying the authorizing
  envelope id. Crosses the never-autonomous binding via the intake §3 revisit; default
  stays GATE."
- Binding decision this crosses: R20 / never-autonomous merge-deploy posture —
  `plugins/saga/scripts/reversibility_certificate.py:16,19,51` (closed allowlist,
  merge/deploy intentionally absent); `plugins/saga/skills/outcome/SKILL.md:104-107`
  (operational restatement: "Never autonomous — always the operator's keystroke").
  Also recorded in the grounding brief's binding-decision register:
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:30,48`.
- Revisit condition licensing this change: intake brief Autonomy Posture §3 —
  `docs/plans/2026-07-03-plugin-fleet-ideation-intake-brief.md:47-58`, specifically
  lines 53-55: "Gate or auto merge / deploy-to-nonprod? Merge/deploy NOT unconditionally
  gated; operator decides per outcome, once, at start."
- Consolidation rationale (why this is its own issue, not merged into anything else):
  issue-map `pf-envelope-authorized-merge` entry, `consolidation_rationale`: "Kept alone:
  it crosses the never-autonomous-merge posture via the intake §3 revisit condition and
  must be schedulable (and rejectable) independently of everything else; default stays
  GATE."
- Existing certificate/ledger machinery this capability extends:
  `plugins/saga/scripts/reversibility_certificate.py:239` (`authorize_write` public
  API); `plugins/saga/scripts/outcome_board_sync.py:93-120` (ledger dir/naming),
  `outcome_board_sync.py:177-211` (`reconcile_board` GATE/AUTHORIZED/ledger flow),
  `outcome_board_sync.py:316` (existing `authorize_write` call site), `:337-340`
  (ledger idempotency-key check before write).

## Recommended Executor Profile

- Model: opus
- Effort: high — *target posture: not a live team-execution dispatch knob until `pf-effort-first-class` lands; teammates inherit session tier until then*
- Backend: team-execution
- External-LLM posture: second-opinion (advisory only)
- Justification: This capability crosses a binding, previously-settled autonomy
  decision (R20, never-autonomous merge). Designing the token shape, the revocation
  semantics, and the boundary between "envelope grants merge" and "all other gates still
  must be green" requires adversarial design judgment, not mechanical implementation —
  a wrong default here (e.g., a token that outlives its revocation check, or a ledger
  schema that can't distinguish envelope-authorized merges from anything else) directly
  reopens a decision the fleet has deliberately kept closed. Per the repository's
  model/effort tiering guidance, judgment/design/adversarial-review work of this shape
  warrants opus, and the never-autonomous crossing specifically warrants a second-opinion
  external-LLM pass before the design is locked, not just at code-review time.

## Release-Surface Checklist

This capability changes plugin behavior (a new write class and a schema field consumed
by `/outcome` autonomy), so the following must ship in the same PR:

- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump reflecting the new
  write-class capability.
- [ ] `.claude-plugin/marketplace.json` — saga entry version/description kept in sync
  with the plugin.json bump.
- [ ] `plugins/saga/CHANGELOG.md` — entry describing the new
  `AUTONOMOUS_UNDER_ENVELOPE` write class, the envelope-token check, and the ledger
  schema addition (`authorizing_envelope_id`).
- [ ] Any version/metadata drift-guard tests in `tests/` that assert plugin.json ↔
  marketplace.json ↔ CHANGELOG consistency — verified green after the bump, not just
  after the code change.
- [ ] `docs/engineering-journal/DECISIONS.md` — entry recording that merge gained a
  scoped, revocable exception mechanism, why (intake §3 revisit), and the "revisit when"
  condition for this decision itself (e.g., "revisit when deploy-to-nonprod gains the
  same mechanism, or when envelope-issuance UX ships and this token shape needs
  extending").

## Definition of Done

- [ ] `AUTONOMOUS_UNDER_ENVELOPE` write class exists in
  `reversibility_certificate.py`, inert without a token.
  Check: `uv run pytest tests/test_reversibility_certificate.py -k envelope` → passes.
- [ ] Envelope-token check wired into `authorize_write` (or a documented sibling
  function), verified DENIED-with-no-token, AUTHORIZED-with-valid-token-and-green-gates,
  re-DENIED-after-revocation.
  Check: `uv run pytest tests/test_reversibility_certificate.py -k envelope_token` →
  passes, covering all three verdicts.
- [ ] Board-sync ledger schema records `authorizing_envelope_id` on every envelope-
  authorized merge write.
  Check: `uv run pytest tests/test_outcome_board_sync.py -k authorizing_envelope` →
  passes.
- [ ] Full suite, format, lint, and types stay green.
  Check: `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` → all pass.
- [ ] Release-surface checklist above is complete (plugin.json, marketplace.json,
  CHANGELOG, drift-guard tests, journal entry).

### Verification

```bash
# Certificate-level envelope-authorized-merge behavior
uv run pytest tests/test_reversibility_certificate.py -k envelope -v

# Ledger attribution of authorized merges to their authorizing envelope
uv run pytest tests/test_outcome_board_sync.py -k authorizing_envelope -v

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all green; the envelope test explicitly exercises DENIED (no token) →
AUTHORIZED (valid token, all gates green) → GATE (post-revocation) in one assertion
chain, and the ledger test confirms `authorizing_envelope_id` is present and correct on
the written record.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan — the design of the token shape
and its relationship to the existing `Tier`/`OpFacts` model should be settled there
before code, given the opus-level judgment this issue's executor profile calls for.

### Source context
- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T7.json` (id
  `T7-F6-2`) via `issue-map-final.json` slug `pf-envelope-authorized-merge`.
- Source type: ideation-survivor (moonshot tier, wave-3)
- Source title: Envelope-authorized merge in the `/outcome` autonomous allowlist

### Context library links

_none_

### Files expected to change

- `plugins/saga/scripts/outcome_board_sync.py`
- `tests/test_reversibility_certificate.py`
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T7.json`
- `plugins/saga/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `plugins/saga/CHANGELOG.md`
- `docs/engineering-journal/DECISIONS.md`

### Tests to add or update

- `tests/test_outcome_board_sync.py`
- `tests/test_reversibility_certificate.py`

### Inputs inventory

- `plugins/saga/scripts/outcome_board_sync.py`
- `tests/test_reversibility_certificate.py`
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T7.json`
- `plugins/saga/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `plugins/saga/CHANGELOG.md`
- Gate E issue plan: `docs/plans/2026-07-04-plugin-fleet-issue-plan.md`
- Grounding References section of this issue (absorbed-idea bases)

### Failure modes / pre-mortem

- The mechanism ships partially against the Definition of Done — caught by the Acceptance criteria checks below going red.
- Scope creeps past Out-of-scope / non-goals during implementation — caught at PR review against this issue body.
- Release surfaces (plugin.json / marketplace.json / CHANGELOG) drift from the change — caught by the release-surface drift-guard tests.
- `/plan` should deepen this pre-mortem with issue-specific failure modes before implementation.

### Stop conditions

- Any acceptance check cannot go green without widening scope beyond the stated non-goals → HALT, return to operator.
- A load-bearing grounding reference turns out stale against live sources → HALT, re-verify before proceeding.
- Release-surface drift guards fail after version bumps → HALT, reconcile before PR.

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/449
- Number: 449
- Created at: 2026-07-04T08:17:21.686780+00:00

