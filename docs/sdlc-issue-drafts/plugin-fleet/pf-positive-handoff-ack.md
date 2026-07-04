---
title: "capability: positive handoff protocol at the saga <-> mission-control <-> deploy boundary"
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
objective: "Automate the ship ceremony end-to-end"
wave: wave-2
---

# capability: positive handoff protocol at the saga <-> mission-control <-> deploy boundary — no dropped batons

## Summary

Ownership of a work item passes across three plugins as it ships — saga (`/work` builds to
merge), mission-control (board and issue state), deploy (tag promotion to nonprod/staging/
production) — but today those transfers are implicit: no plugin explicitly declares "I have
released this" or "I have accepted this." Borrow the aviation positive-handoff / naval bridge
"you have the con" pattern: the releasing plugin does not drop ownership of a work item until
the receiving plugin explicitly acknowledges the transfer, recorded as an ack token in the saga.
The saga -> deploy edge is the sharp one — `/work` owns the PR loop through merge but explicitly
does **not** own deploy — so a merge can land with no plugin visibly holding the item until deploy
picks it up, or never picking it up at all with nothing surfacing the gap. This capability adds a
handoff-ack envelope (ack token + gate-or-auto payload) at that boundary and a saga field that
records the acknowledged transfer, so the gate-or-auto answer captured once at intent time
travels with the baton instead of being silently re-decided (or silently dropped) at each
boundary crossing.

## Problem Frame

`/work` states its own boundary explicitly: it "builds, tests, gates, records, and coordinates
the PR loop" and merge is "a git op `/work` owns under confirmation," after which it "routes to
`/qa` **advisorily**" (`plugins/saga/skills/work/SKILL.md:459-462`, "Hard boundary" section).
Nothing in that boundary statement, or anywhere else in the fleet, requires deploy (or
mission-control) to *acknowledge* that it has picked the item up. The transfer is asserted by the
releasing side (`/work` routes advisorily) and never confirmed by the receiving side. There is no
ack token, no saga field recording "deploy has this now," and no test that would catch a merged
item that never gets an acknowledged deploy owner.

This is a live consolidation seam, not a hypothetical one: the same "no dropped baton" idea
surfaced independently across five ideation frames in this repo's 2026-07-03 plugin-fleet
ideation pass before being deduplicated onto this one (`T7-F1-7`, `T7-F2-8`, `T7-F3-7` — see
Grounding references below) — a signal that the ownership gap is felt repeatedly, not a one-off
observation.

The intake-side binding decision this capability must honor is that merge/deploy autonomy is
never coordinator-autonomous and is instead an operator-authored posture answered once at intent
capture — "Whether PR reviews are required and whether merge/deploy-to-nonprod is gate-or-auto ...
[is] envelope properties captured exactly once at intent capture ... so the ship reconciler merely
reads them rather than interrogating the operator mid-ceremony" (`docs/plans/
plugin-fleet-ideation-2026-07-03/pool-final.json:6920`, idea `T7-F5-8`'s sibling). Today that
gate-or-auto answer has nowhere durable to live once it crosses from saga into deploy — this
capability is the carrier.

Existing envelope infrastructure this builds on, verified present today:

- `plugins/saga/commands/handoff.md` + `plugins/saga/skills/handoff/SKILL.md` (69 lines) already
  define saga's handoff *boundary* (source-artifact selection, maturity inference, routing to
  mission-control) but stop at "route to mission-control" — there is no ack step, and no envelope
  crosses into deploy at all today.
- `plugins/saga/scripts/handoff_envelope.py` already builds a "thin Infiquetra loop handoff
  envelope for mission-control" (module docstring) with `infer_maturity` / `infer_lifecycle_phase`
  helpers, but the envelope it emits carries no ack token and no gate-or-auto payload, and there is
  no equivalent envelope emitted toward deploy.
- `plugins/deploy/skills/deploy-state/SKILL.md` and the deploy commands (`deploy.md`,
  `deploy-hotfix.md`, `deploy-status.md`, `deploy-notes.md`) document tag-promotion mechanics but
  have no notion of "an upstream saga handed this item to me" — deploy has no acceptance side to
  acknowledge into.

## Requirements

R1. A handoff-ack envelope schema (ack token + gate-or-auto payload) is added to
`plugins/saga/scripts/handoff_envelope.py` (or a sibling module it calls), distinct from the
existing mission-control-facing envelope, addressed at the saga -> deploy edge.

R2. The envelope's gate-or-auto payload is read from the same intent-capture source the outcome
DAG already treats as authoritative for merge/deploy autonomy (the operator-authored posture
captured once at intent time), not re-derived or re-asked at handoff time.

R3. A durable saga field records the acknowledged transfer (for example
`handoff.deploy_ack: {token, acknowledged_at, acknowledged_by}`), written only when the receiving
side (deploy) explicitly acknowledges — not when the releasing side (saga/`work`) merely offers
or routes.

R4. Ownership is not considered released until that ack is recorded. Until an ack exists, the
work item's derived status must reflect "handed off, not yet accepted," not "deployed" or "done" —
consistent with the fleet-wide derive-on-read status discipline (`/outcome` campaign binding
decision, `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:48`: "Derived-on-read status,
never committed status fields").

R5. The gate-or-auto answer carried in the envelope propagates into the deploy-side authorization
decision: deploy must consult it before auto-promoting, and an envelope carrying `gate` must never
be silently overridden to auto-fire by the deploy side.

R6. Deploy-side skill docs (`plugins/deploy/skills/deploy-state/SKILL.md` and/or the relevant
command doc) document the acceptance step — what deploy does to record its ack — so the boundary
contract is discoverable from the deploy side, not only from saga's `handoff` skill.

R7. This capability does not change `/work`'s existing hard boundary (merge stays a confirmed git
op `/work` owns; `/work` still routes to `/qa` advisorily) — it adds an explicit acceptance step
on the deploy side of the boundary `/work` already declares it does not own.

## Definition of Done

- A handoff-ack envelope (ack token + gate-or-auto payload) exists at the saga -> deploy edge in
  `plugins/saga/scripts/handoff_envelope.py` (or a sibling module), plus a durable saga field
  recording the acknowledged transfer.
- Ownership of the work item is not released until that ack is recorded; deploy-side skill docs
  document the acceptance step so the boundary contract is discoverable from the deploy side.
- The gate-or-auto answer captured at intent time propagates into the deploy-side authorization
  decision without being re-derived or re-asked.

## Key Flows

F1. **Normal handoff, deploy accepts.** `/work` merges a PR and routes the item toward deploy
carrying a gate-or-auto payload. Deploy reads the envelope, records an ack token in the saga
handoff field, and only then does the item's derived status stop reading "awaiting deploy
acceptance." If the payload said `gate`, deploy proceeds only under explicit confirmation; if it
said `auto`, deploy is authorized to promote without an additional prompt.
**Covers R1, R2, R3, R4, R5.**

F2. **Dropped baton caught.** `/work` merges and routes, but deploy never acknowledges (crashed
run, missed handoff, wrong target). No ack token is written. A later status read (board sync,
`/outcome` reconciliation, or an explicit check) surfaces the item as "handed off, unacknowledged"
rather than silently reading as done or silently vanishing from view.
**Covers R3, R4.**

F3. **Gate-or-auto honored across the boundary.** The intent-capture envelope says merge/deploy is
`gate`. The saga -> deploy handoff envelope carries that `gate` value. Deploy's authorization
decision reads the payload and requires confirmation before promoting, even though the merge on
the saga side already completed.
**Covers R2, R5.**

### Out-of-scope / non-goals
- This capability instruments the **saga -> deploy** edge, since that is the sharp boundary
  `/work` explicitly disclaims ownership of (`work/SKILL.md:459-462`). It does not add a
  symmetric ack requirement to the existing saga -> mission-control edge (`saga/handoff` already
  routes there and mission-control owns issue-body mutation on its side); widening the ack pattern
  to that edge is a candidate follow-up, not this issue.
- Does not change deploy's tag-promotion mechanics, canary/verify/revert behavior, or environment
  model — only adds an acceptance/ack step ahead of the existing promotion flow.
- Does not change `/work`'s hard boundary or its advisory routing to `/qa`.
- Does not introduce a new autonomy allowlist or reversibility classifier — it consumes the
  existing intent-capture gate-or-auto posture as given, it does not compute it.
- Does not build a standing reconciliation loop for unacknowledged handoffs beyond what is needed
  to make the gap observable (F2); a scheduled sweep of stale unacknowledged handoffs is a
  candidate fast-follow, not in scope here.

## Dependencies / Assumptions

- Assumes the intent-capture gate-or-auto posture already exists as an authoritative, readable
  value by the time a saga -> deploy handoff needs to consult it. If the fleet's intent-envelope
  work (the `ENGINE_INTENTS` / intent-capture line of ideas) has not landed a durable field for
  this by the time this capability is planned, the plan step must either take a narrow dependency
  on that field or define a minimal interim source — this is a planning-time decision, not
  resolved here.
- Builds on, does not replace, `plugins/saga/scripts/handoff_envelope.py`'s existing envelope
  shape and `plugins/saga/skills/handoff/SKILL.md`'s existing saga/mission-control boundary
  language.
- Assumes deploy has a place to write/read saga state from (or an equivalent durable channel) to
  record its ack; verify this at plan time against `plugins/deploy`'s current state model before
  committing to a specific storage location.

## Grounding References

- Absorbed idea `T7-F5-8` (primary, `basis_type: direct`) — full text:
  `docs/plans/plugin-fleet-ideation-2026-07-03/pool-final.json:7160` (idea) and `:7163`
  (outcome_shape); survivor record: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/
  T7.json` (`id: T7-F5-8`).
- Duplicate ideas consolidated onto `T7-F5-8` (confirms recurrence of the same gap across
  independent ideation frames — not separately absorbed, cited for problem-frame weight only):
  `T7-F1-7` ("Ship-ceremony ownership contract... documented handoff protocol"), `T7-F2-8` ("A
  single ceremony envelope that batons merge->nonprod->close across saga, deploy,
  mission-control"), `T7-F3-7` ("The ceremony is owned by no one — name the seam contract") — all
  three in `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T7.json`, each carrying
  `kept_duplicate_of: T7-F5-8`.
- Binding decision this capability must honor: gate-or-auto merge/deploy is an operator-captured
  intent-time posture, not a mid-ceremony re-ask — `docs/plans/plugin-fleet-ideation-2026-07-03/
  pool-final.json:6920`; fleet-wide derive-on-read status discipline —
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:48` ("`/outcome` campaign (U1-U11)...
  Derived-on-read status, never committed status fields; HALT-not-degrade").
- `/work`'s explicit disclaimed deploy ownership: `plugins/saga/skills/work/SKILL.md:459-462`
  ("Hard boundary" section — merge is a confirmed git op `/work` owns; routes to `/qa`
  advisorily; deploy is not mentioned as an owned step).
- Existing saga-side handoff scaffolding to extend, not replace:
  `plugins/saga/commands/handoff.md`, `plugins/saga/skills/handoff/SKILL.md`,
  `plugins/saga/scripts/handoff_envelope.py`.
- Deploy-side surface with no current acceptance step:
  `plugins/deploy/skills/deploy-state/SKILL.md`, `plugins/deploy/commands/deploy.md`.
- Plugin sprawl / consolidation-burden constraint on ideation:
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:52`
  (`{#plugin-portfolio-groom-17-to-7}` — new-surface ideas carry a consolidation-burden proof;
  this issue extends two existing modules rather than adding a new plugin).

## Recommended executor profile

- **Model:** sonnet
- **Effort:** medium
- **Backend:** inline
- **External-LLM posture:** none (no codex/agy delegation; this is a structural cross-plugin
  contract change owned end-to-end by the primary executor)
- **Justification:** mechanical, well-scoped extension of two existing modules
  (`handoff_envelope.py` schema addition + a deploy-side doc/ack step) with a clear test surface;
  does not require judgment calls above what a Sonnet-tier executor at medium effort routinely
  handles, and the binding decisions it must honor (gate-or-auto posture, derive-on-read status)
  are already settled elsewhere, not decisions this issue makes itself. No basis to justify a
  higher tier.

## Release-surface checklist

This capability changes cross-plugin behavior (saga's handoff envelope schema, deploy's
acceptance step) and documented guidance (deploy-state skill docs), so the following must land in
the same PR:

- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump reflecting the handoff-ack envelope
  schema addition.
- [ ] `plugins/deploy/.claude-plugin/plugin.json` — version bump reflecting the new acceptance/ack
  step and any deploy-state skill doc changes.
- [ ] `.claude-plugin/marketplace.json` — version/metadata sync for both `saga` and `deploy`
  entries.
- [ ] `plugins/saga/CHANGELOG.md` — entry describing the handoff-ack envelope and the new saga
  field recording acknowledged transfer.
- [ ] `plugins/deploy/CHANGELOG.md` — entry describing the deploy-side acceptance step and
  gate-or-auto consumption.
- [ ] Any existing version/metadata drift-guard tests (for example under `tests/`) updated or
  extended to cover the new schema fields so plugin.json/marketplace.json/CHANGELOG cannot drift
  from the code change unnoticed.

### Acceptance criteria
- [ ] AC1. **Covers R1, R3.** A handoff-ack envelope with an ack token and a gate-or-auto payload is merged into `plugins/saga/scripts/handoff_envelope.py` (or a named sibling module). Check: `uv run pytest tests/test_handoff_envelope.py -k ack_envelope_schema` → passes.
- [ ] AC2. **Covers R3, R4.** Ownership is not released until an ack is recorded: a simulated handoff with no ack present must not cause the item's derived status to report "deployed" or "done." Check: `uv run pytest tests/test_handoff_envelope.py -k ownership_not_released_without_ack` → passes.
- [ ] AC3. **Covers R2, R5.** The gate-or-auto answer captured at intent time propagates into the deploy-side authorization decision: a `gate` payload blocks deploy auto-promotion pending confirmation; an `auto` payload authorizes it. Check: `uv run pytest tests/test_handoff_envelope.py -k gate_or_auto_propagation` → passes.
- [ ] AC4. **Covers R3.** A recorded ack includes a token, timestamp, and acknowledging identity, and round-trips through save/load of saga state. Check: `uv run pytest tests/test_handoff_envelope.py -k ack_round_trip` → passes.
- [ ] AC5. **Covers R4, F2.** A dropped-baton scenario (merge completes, deploy never acks) is detectable: a status/reconciliation read surfaces the item as handed-off-unacknowledged rather than silently omitting it or marking it done. Check: `uv run pytest tests/test_handoff_envelope.py -k dropped_baton_detected` → passes.
- [ ] AC6. **Covers R6.** `plugins/deploy/skills/deploy-state/SKILL.md` (or the relevant deploy command doc) documents the acceptance/ack step from the deploy side. Check: `grep -n "ack" plugins/deploy/skills/deploy-state/SKILL.md` → at least one match describing the handoff acceptance step.
- [ ] AC7. **Covers R7.** `/work`'s existing hard boundary (merge as a confirmed git op it owns, advisory routing to `/qa`) is unchanged by this capability. Check: `git diff --stat -- plugins/saga/skills/work/SKILL.md` shows no changes to the "Hard boundary" section (or, if `/work`'s SKILL.md is touched to reference the new envelope, the "Hard boundary" section's substantive language is preserved), confirmed by reviewer at PR time.
### Files expected to change

- `plugins/saga/scripts/handoff_envelope.py` — add ack-token + gate-or-auto envelope schema and
  emission logic for the saga -> deploy edge.
- `plugins/saga/skills/handoff/SKILL.md` — document the deploy-facing envelope and ack contract
  alongside the existing mission-control boundary language.
- `plugins/deploy/skills/deploy-state/SKILL.md` (and/or `plugins/deploy/commands/deploy.md`) —
  document the deploy-side acceptance step and gate-or-auto consumption.
- `.claude/saga/state.json` (schema, not a specific file) — new field recording the acknowledged
  transfer.
- `tests/test_handoff_envelope.py` — new/extended tests for the ack envelope, ownership-release
  gating, gate-or-auto propagation, and dropped-baton detection.
- `plugins/saga/.claude-plugin/plugin.json`, `plugins/deploy/.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`, `plugins/saga/CHANGELOG.md`, `plugins/deploy/CHANGELOG.md` —
  release-surface updates (see checklist above).

### Tests to add or update

- Ack envelope schema round-trips (token, gate-or-auto payload, timestamp, acknowledging
  identity).
- Ownership-not-released-without-ack: no ack present → status must not read deployed/done.
- Gate-or-auto propagation: `gate` blocks auto-promotion pending confirmation; `auto` authorizes
  without an additional prompt.
- Dropped-baton detection: merged-but-unacknowledged item surfaces as handed-off-unacknowledged on
  a status/reconciliation read.
- Existing `/work` hard-boundary tests (merge confirmation gate, advisory `/qa` routing) remain
  green and unmodified in behavior.

### Verification

```bash
# New/extended handoff-ack tests
uv run pytest tests/test_handoff_envelope.py -v

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports && uv run bandit -r plugins/
```

Expected: all green; the ack-envelope tests specifically demonstrate that (a) ownership is not
released without a recorded ack, and (b) the gate-or-auto answer captured at intent time is the
value deploy's authorization decision consults.

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

### Source context

- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/pool-final.json` (idea `T7-F5-8`,
  lines 7160-7163) and `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T7.json`
- Source type: ideation (plugin-fleet ideation pass, 2026-07-03)
- Source title: "Positive handoff protocol at the saga <-> mission-control <-> deploy boundary —
  no dropped batons"

### Intent

Ownership of a work item passes across three plugins as it ships — saga (`/work` builds to merge), mission-control (board and issue state), deploy (tag promotion to nonprod/staging/ production) — but today those transfers are implicit: no plugin explicitly declares "I have released this" or "I have accepted this." Borrow the aviation positive-handoff / naval bridge "you have the con" pattern: the releasing plugin does not drop ownership of a work item until the receiving plugin explicitly acknowledges the transfer, recorded as an ack token in the saga. The saga -> deploy edge is the sharp one — `/work` owns the PR loop through merge but explicitly does **not** own deploy — so a merge can land with no plugin visibly holding the item until deploy picks it up, or never picking it up at all with nothing surfacing the gap. This capability adds a handoff-ack envelope (ack token + gate-or-auto payload) at that boundary and a saga field that records the acknowledged transfer, so the gate-or-auto answer captured once at intent time travels with the baton instead of being silently re-decided (or silently dropped) at each boundary crossing.

### Context library links

_none_

### Objective

"Automate the ship ceremony end-to-end"

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/395
- Number: 395
- Created at: 2026-07-04T08:00:01.917929+00:00

