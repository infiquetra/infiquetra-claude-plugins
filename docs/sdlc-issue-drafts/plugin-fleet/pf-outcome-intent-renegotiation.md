---
title: capability: mid-run posture renegotiation for /outcome (repost/set_intent, overlap-safe amendment, monotonic gating, HALT-as-renegotiation-point)
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
wave: wave-2
objective: Ship run-start intent envelope for lifecycle autonomy
---

# capability: mid-run posture renegotiation for /outcome (repost/set_intent, overlap-safe amendment, monotonic gating, HALT-as-renegotiation-point)

### Objective

Ship run-start intent envelope for lifecycle autonomy

## Summary

`/outcome` campaigns capture posture (autonomy level, sandbox, degrade policy) once at
`start` time and have no supported way to change it mid-run. This capability ships a
`repost` / `set_intent` verb that lets an operator renegotiate posture on a live campaign
under the same atomic snapshot-validate-bump-revision-decision_trail discipline the
DAG-edit path already uses, with dispatch-time-posture overlap semantics so in-flight
leaves are not retroactively reinterpreted, a monotonic-toward-more-gating rule for
merge/deploy transitions, and a reframe of gate-caused HALTs as scoped renegotiation
points rather than dead stops.

## Problem Frame

- **DAG edits already have the atomic mutation shape this needs; posture does not.**
  `OutcomeSpec.bump_revision()` (`plugins/saga/scripts/outcome_spec.py:382-395`) increments
  `spec_revision` and appends a `decision_trail` entry on every structural mutation
  (`redirect_dependency` and friends), and `DECISIONS.md:788` records the generalized
  contract: "snapshot → validate → bump revision + trail; rejected edit leaves
  `nodes`/`depends_on`/`spec_revision`/`decision_trail` untouched (R26)." Posture
  (autonomy, sandbox, degrade policy) has no equivalent mutation verb today — it is set
  once at `start` and is otherwise read-only for the life of the campaign.
- **Degrade policy already distinguishes guarantee-bearing halts from soft degrades, but
  nothing lets an operator move it mid-run.** `DEGRADE_POLICIES = ("halt",
  "operator_away_one_rung", "none")` (`plugins/saga/scripts/outcome_spec.py:90-96`), with
  `"halt"` documented as "guarantee-bearing leaf halts (no degrade)." The `/outcome`
  campaign's binding decision is HALT-not-degrade — "Derived-on-read status, never
  committed status fields; HALT-not-degrade; backend menu off-by-default host-conditional
  degrade; cost ledger = leaf-produced fact"
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:48`;
  `docs/engineering-journal/DECISIONS.md:739-744`, `{#outcome-backend-degrade-stance}`).
  A new posture-renegotiation verb must compose this existing halt precedence, not invent
  a second, conflicting one.
- **`advance --autonomous` already reads a live board without a supported way to reduce its
  own authority mid-flight.** "Autonomous board-sync (`advance --autonomous`, #279) *writes*
  the board but never re-reads it" (`plugins/saga/references/outcome-spec.md:150`), with a
  `detect` step that "runs at the top of every `advance --autonomous` tick *before* any
  board write" (`plugins/saga/references/outcome-spec.md:156`). There is no verb today that
  lets an operator tighten (or loosen) the autonomy envelope this tick is allowed to act
  under, and no rule preventing a loosening repost from silently reopening a merge/deploy
  gate an operator already closed off.
- **Recurring-pain evidence: operators already ask for mid-run posture changes with no
  primitive to answer it.** "Ad hoc tier reasoning every time — 'xhigh-Opus on everything
  wasteful'; manual per-unit tier tables; operator asking mid-run model-change pauses (3
  repos)" (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:126-128`, theme 12) is the
  same underlying gap this issue's sibling `pf-midrun-adjustment-envelope` answers for
  reversible worker-facing directives (quiesce/pause/andon-cord); this issue is the
  posture-authority counterpart — renegotiating the campaign's own gating envelope, not a
  single worker's pause state.
- **Consolidation rationale (issue map).** "Mid-flight posture renegotiation needs one
  merged verb, not three competing repost semantics: T8-F1-7 supplies the audited
  snapshot→validate→bump_revision→decision_trail mutation shape; T8-F5-6 supplies
  Raft-joint-consensus-style overlap-safe amendment semantics (in-flight leaves finish
  under dispatch-time posture, pending leaves pick up the amendment, an amendment that
  would strand an authorized irreversible op HALTs instead); T8-F6-7 supplies the
  monotonic-toward-more-gating invariant for merge/deploy transitions specifically; T8-F3-8
  reframes a posture-caused HALT as a first-class renegotiation point rather than a dead
  end. One verb, one revision counter, one trail." (issue-map-final.json, slug
  `pf-outcome-intent-renegotiation`)

## Requirements

**Repost/set_intent verb (T8-F1-7, primary)**

R1. `/outcome` gains a `repost` (aka `set_intent`) verb that mutates a live campaign's
posture fields through the same atomic sequence as existing spec edits: snapshot the
current spec, validate the proposed posture change, bump `spec_revision`, append a
`decision_trail` entry recording the change and its reason — mirroring
`OutcomeSpec.bump_revision()` (`plugins/saga/scripts/outcome_spec.py:382-395`).

R2. A rejected repost (failed validation) leaves `spec_revision`, `decision_trail`, and all
posture fields byte-identical to their pre-repost state — no partial mutation, matching the
existing R26 invariant ("rejected edit leaves `nodes`/`depends_on`/`spec_revision`/
`decision_trail` untouched," `DECISIONS.md:788`).

R3. A repost that *loosens* any gate (widens sandbox, drops autonomy from `halt` toward
`operator_away_one_rung`/`none`, or otherwise reduces required approval) re-closes the
frontier approval that gate previously satisfied — the loosened gate must be re-approved
before any leaf gated by it dispatches again. A repost that only tightens gating requires
no re-approval.

**Overlap-safe amendment (T8-F5-6, facet)**

R4. Every posture change is tagged with the `spec_revision` it introduces
(`intent_revision`), and each leaf's dispatch record captures which `intent_revision` was
active at the moment of its dispatch (dispatch-time posture).

R5. A leaf already in flight when a repost lands continues to completion under the posture
that was active at its dispatch time; it is not retroactively re-evaluated against the new
posture. Leaves not yet dispatched pick up the new posture at their next dispatch.

R6. If an amendment would strand a leaf that was authorized to perform an irreversible
operation under the old posture but would not be authorized under the new one (the leaf is
mid-flight and cannot be un-authorized), the campaign HALTs instead of silently letting the
stranded op proceed or silently revoking it — no silent resolution either direction.

**Monotonic merge/deploy gating (T8-F6-7, facet)**

R7. `merge_gate` and `deploy_gate` postures may only move toward *more* gating via
`set_intent` — any repost that would relax `merge_gate` or `deploy_gate` from a gated state
toward an autonomous (ungated) state is rejected outright by `set_intent` validation, never
silently accepted. This asymmetry is intentional: a campaign can tighten its own merge/
deploy posture at any time, but can never loosen it back to autonomous once gated, without a
new campaign.

**HALT as renegotiation point (T8-F3-8, facet)**

R8. When a leaf HALTs purely because of the current posture's gating (a "posture-caused gate
HALT" — e.g. it needs operator sign-off the current posture requires), the HALT surfaces a
scoped-repose option: the operator may resolve the specific gated leaf's posture (not the
whole campaign's) via `set_intent` scoped to that leaf/subtree.

R9. A globally-gated leaf that surfaces a scoped-repose option does not proceed under any
default or timeout — it remains halted until the operator explicitly selects a resolution
(repose the scope, or leave halted). Silence is never treated as consent, consistent with
the fleet's existing gate-primitive-unreliability finding ("AskUserQuestion silently
auto-proceeds on timeout treating silence as consent,"
`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:122-125`, theme 6).

## Key Flows

F1. **Tightening repost, no re-approval needed.** Trigger: operator runs `repost`/
`set_intent` narrowing sandbox or raising a leaf's degrade policy toward `halt`. Gate: none
required — tightening never reopens closed approvals. Covers R1, R2, R7.

F2. **Loosening repost, frontier re-closes.** Trigger: operator reposts widening sandbox or
dropping degrade policy away from `halt`. Any frontier approval the loosened gate had
previously satisfied is re-closed; affected leaves do not dispatch until re-approved.
Covers R1–R3.

F3. **In-flight leaf under old posture, pending leaf under new posture.** Trigger: repost
lands while leaf A is dispatched and leaf B is pending. Leaf A completes under its
dispatch-time posture; leaf B is dispatched (if at all) under the new posture. Covers R4,
R5.

F4. **Amendment strands an authorized irreversible op.** Trigger: repost would revoke
authorization for an irreversible action a mid-flight leaf was already cleared to perform.
Campaign HALTs rather than letting the op proceed unauthorized or silently killing it mid-
op. Covers R6.

F5. **Rejected merge/deploy loosening.** Trigger: operator attempts `set_intent` moving
`merge_gate` or `deploy_gate` from gated toward autonomous. `set_intent` rejects the change
outright; campaign posture is unchanged. Covers R7.

F6. **Posture-caused HALT offers scoped repose.** Trigger: a leaf HALTs because the current
posture gates it. The HALT record carries a scoped-repose option targeting only that leaf/
subtree. Operator must explicitly select repose-or-remain-halted; no timeout auto-proceed.
Covers R8, R9.

## Scope Boundaries

- **One verb (`repost`/`set_intent`), not a family of ad hoc posture setters.** All posture
  renegotiation — sandbox, degrade policy, merge/deploy gating — goes through this single
  atomic verb reusing the existing snapshot→validate→bump_revision→decision_trail shape;
  it does not introduce a parallel posture-mutation path.
- **Does not touch DAG structure.** This issue is posture-only. Node add/prune/redirect
  mutations already exist via `redirect_dependency` and friends
  (`plugins/saga/scripts/outcome_spec.py`); `set_intent` must not duplicate or bypass that
  path.
- **Does not weaken existing HALT-not-degrade precedence.** The scoped-repose option added
  by R8/R9 is a resolution *path out of* an existing HALT, not a new degrade mode; it must
  compose with, not override, `{#outcome-backend-degrade-stance}`
  (`docs/engineering-journal/DECISIONS.md:739-744`).
- **Merge/deploy monotonicity is one-directional by design, not a general rollback
  feature.** Reverting a mistaken tightening requires a new campaign, not a `set_intent`
  loosening path — this is intentional scope, not a gap to close later in this issue.
  Sibling `pf-midrun-adjustment-envelope` covers reversible, worker-facing mid-run
  directives (quiesce/pause/andon-cord/act-log-notify); this issue is scoped strictly to
  campaign-level posture authority.
- **No new operator-facing UI.** `repost`/`set_intent` is a CLI/command-surface verb on
  `/outcome`; a dashboard or chat-based control surface is out of scope.

## Dependencies / Assumptions

- Builds on the existing atomic-edit contract: `OutcomeSpec.bump_revision()`
  (`plugins/saga/scripts/outcome_spec.py:382-395`) and the generalized "snapshot → validate
  → bump revision + trail" invariant (`docs/engineering-journal/DECISIONS.md:788`).
  Verified present in code at grounding time.
- Builds on the existing `DEGRADE_POLICIES` vocabulary (`"halt"`,
  `"operator_away_one_rung"`, `"none"`) at `plugins/saga/scripts/outcome_spec.py:90-96` and
  the HALT-not-degrade binding decision (`{#outcome-backend-degrade-stance}`,
  `docs/engineering-journal/DECISIONS.md:739-744`). `set_intent` must compose with this
  precedence, not add a second halt vocabulary.
- Builds on the `advance --autonomous` re-read gap noted at
  `plugins/saga/references/outcome-spec.md:150,156` — this issue is the mechanism by which
  an operator can deliberately narrow (or, subject to R7, widen non-merge/deploy) the
  authority that tick is allowed to act under.
- Assumes `merge_gate`/`deploy_gate` posture fields either already exist on `OutcomeSpec` or
  are introduced by this issue as part of `set_intent`'s validation surface; `/plan` should
  confirm current field presence before design and add them if absent — verified absent as
  named fields in `outcome_spec.py` at grounding time (only `DEGRADE_POLICIES` and sandbox
  axes exist today).
- Consolidates four ideation survivors per the issue map's consolidation rationale (see
  Problem Frame) — do not re-split this into separate posture-mutation verbs.

## Grounding References

| Absorbed id | Role | Title | Basis |
|---|---|---|---|
| `T8-F1-7` | primary | `outcome repost`: change campaign posture mid-run as audited, re-approving spec bump | `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T8.json` — direct; dod_sketch: merged PR adding `repost` verb doing atomic snapshot→validate→bump_revision→decision_trail; tests asserting rejected repost leaves revision/trail untouched and gate-loosening repost re-closes frontier approval |
| `T8-F5-6` | facet | Raft joint consensus: overlap-safe mid-run posture amendment | `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T8.json` — external basis (Raft joint-consensus overlap pattern); dod_sketch: merged PR adding `intent_revision` + intent-amend verb where in-flight leaves finish under dispatch-time posture, pending leaves pick up amendment; tests over the overlap window and the HALT case where amendment would strand an authorized irreversible op |
| `T8-F6-7` | facet | `outcome intent set`: renegotiate posture mid-run, atomic revision bump + re-gate | `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T8.json` — direct; dod_sketch: merged PR adding `set_intent` revision-bumping re-gating; `merge_gate`/`deploy_gate` may move only toward more gating, never merge/deploy→autonomous |
| `T8-F3-8` | facet | A HALT is a latent renegotiation point, not just a dead stop | `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T8.json` — reasoned; dod_sketch: merged PR attaching a scoped-repose resolution option to posture-caused gate HALTs; test asserting a globally-gated leaf surfaces the scoped-repose option and does not proceed until selected |

Binding decisions this issue must engage:
`{#outcome-backend-degrade-stance}` / HALT-not-degrade
(`docs/engineering-journal/DECISIONS.md:739-744`); the `/outcome` campaign's
derived-on-read-status stance and atomic-edit invariant (R26)
(`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:48`;
`docs/engineering-journal/DECISIONS.md:788`).

## Recommended Executor Profile

- **Model:** Sonnet
- **Effort:** high — *target posture: not a live team-execution dispatch knob until `pf-effort-first-class` lands; teammates inherit session tier until then*
- **Backend:** team-execution
- **External-LLM posture:** none
- **Justification:** Concurrency-semantics design (overlap windows between dispatch-time
  posture and amended posture, the monotonic merge/deploy invariant, and the HALT-as-
  renegotiation-point resolution path) is subtle enough to benefit from reviewer consensus
  before landing, but is schema-and-invariant shaped against an existing mutation pattern
  (`bump_revision`/`decision_trail`) rather than open-ended architectural judgment, so
  Sonnet at high effort is sufficient without Opus.

### Out-of-scope / non-goals
See Scope Boundaries above. In short: one `repost`/`set_intent` verb reusing the existing
atomic-edit shape, dispatch-time-posture overlap semantics for in-flight leaves,
monotonic-only merge/deploy gating, and a scoped-repose resolution path attached to
posture-caused HALTs — no DAG-structure mutation, no new degrade vocabulary, no reversible
rollback of merge/deploy tightening, no new operator-facing UI.

## Definition of Done

Merged PR adding a `repost`/`set_intent` verb to `/outcome` that performs an atomic
snapshot → validate → bump_revision → decision_trail posture mutation
(`plugins/saga/scripts/outcome_spec.py`), tags each posture change with an `intent_revision`
consumed by dispatch-time-posture overlap logic so in-flight leaves finish under their
dispatch-time posture while pending leaves pick up the amendment, rejects any
`merge_gate`/`deploy_gate` transition that would move from gated toward autonomous, and
attaches a scoped-repose resolution option to posture-caused gate HALTs — with passing
tests for each of the four requirement clusters below and full quality gates green.

### Acceptance criteria
- [ ] A rejected repost leaves `spec_revision`, `decision_trail`, and all posture fields
  untouched (no partial mutation). Check: `uv run pytest tests/test_outcome_intent.py -k
  rejected_repost_untouched` → passes.
- [ ] A gate-loosening repost (sandbox widen or degrade-policy drop away from `halt`)
  re-closes the frontier approval that gate previously satisfied; affected leaves do not
  dispatch until re-approved. Check: `uv run pytest tests/test_outcome_intent.py -k
  loosening_repost_recloses_approval` → passes.
- [ ] A leaf dispatched before a repost lands completes under its dispatch-time posture; a
  leaf not yet dispatched at repost time picks up the new posture. Check: `uv run pytest
  tests/test_outcome_intent.py -k dispatch_time_posture_overlap` → passes.
- [ ] An amendment that would strand a leaf already authorized to perform an irreversible
  operation under the old posture HALTs the campaign instead of silently proceeding or
  silently revoking authorization. Check: `uv run pytest tests/test_outcome_intent.py -k
  amendment_strands_irreversible_op_halts` → passes.
- [ ] Any `set_intent` call that would move `merge_gate` or `deploy_gate` from a gated state
  toward autonomous is rejected by validation; the campaign posture is unchanged. Check:
  `uv run pytest tests/test_outcome_intent.py -k merge_deploy_gate_monotonic` → passes.
- [ ] A globally-gated leaf whose HALT is posture-caused surfaces a scoped-repose option and
  does not proceed under any default or timeout until the operator explicitly selects a
  resolution. Check: `uv run pytest tests/test_outcome_intent.py -k
  scoped_repose_no_timeout_default` → passes.
- [ ] Full suite, format, lint, types stay green. Check: `uv run pytest && uv run ruff
  format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/
  --ignore-missing-imports` → all pass.

### Files expected to change
- `plugins/saga/scripts/outcome_spec.py` — add posture fields (`merge_gate`, `deploy_gate`
  if not already present), `intent_revision` tagging, and the `repost`/`set_intent`
  validation path reusing `bump_revision`'s atomic shape.
- `plugins/saga/scripts/outcome.py` — new `repost`/`set_intent` CLI verb.
- `plugins/saga/scripts/outcome_dispatcher.py` — dispatch-time-posture capture per leaf
  dispatch record; overlap-safe posture resolution at dispatch time.
- `plugins/saga/references/outcome-spec.md` — document the `repost`/`set_intent` verb,
  the `intent_revision` overlap contract, the monotonic merge/deploy-gating invariant, and
  the scoped-repose HALT resolution path.
- `tests/test_outcome_intent.py` — new test file: rejected-repost-untouched,
  loosening-repost-recloses-approval, dispatch-time-posture-overlap,
  amendment-strands-irreversible-op-halts, merge-deploy-gate-monotonic,
  scoped-repose-no-timeout-default.
- `plugins/saga/.claude-plugin/plugin.json` — version bump (new verb/schema surface).
- `.claude-plugin/marketplace.json` — metadata sync for `saga`.
- `plugins/saga/CHANGELOG.md` — entry for `repost`/`set_intent`, `intent_revision`
  overlap semantics, monotonic merge/deploy gating, and scoped-repose HALT resolution.

## Release-surface checklist

Because this issue changes plugin behavior and adds a new command/schema surface, update
in the same PR:

- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump.
- [ ] `.claude-plugin/marketplace.json` — metadata sync for `saga`.
- [ ] `plugins/saga/CHANGELOG.md` — entry documenting the new verb and its invariants.
- [ ] Version/metadata drift-guard tests updated to reflect the new command/schema (per
  root `CLAUDE.md` step 6 — installed-plugin metadata must tell the same story as the
  diff).

### Verification
```bash
# New posture-renegotiation tests
uv run pytest tests/test_outcome_intent.py -v

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
uv run bandit -r plugins/
```

Expected: all green; rejected-repost, loosening-repost, dispatch-time-posture-overlap,
amendment-HALT, merge/deploy-monotonic, and scoped-repose-no-timeout tests all pass.

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

### Source context

- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/issue-map/issue-map-final.json`,
  slug `pf-outcome-intent-renegotiation`
- Source type: ideation issue-map (Gate B consolidation)
- Source title: Mid-run posture renegotiation: repost/set_intent with overlap-safe
  amendment, monotonic gating, and HALT-as-renegotiation-point

### Intent

`/outcome` campaigns capture posture (autonomy level, sandbox, degrade policy) once at `start` time and have no supported way to change it mid-run. This capability ships a `repost` / `set_intent` verb that lets an operator renegotiate posture on a live campaign under the same atomic snapshot-validate-bump-revision-decision_trail discipline the DAG-edit path already uses, with dispatch-time-posture overlap semantics so in-flight leaves are not retroactively reinterpreted, a monotonic-toward-more-gating rule for merge/deploy transitions, and a reframe of gate-caused HALTs as scoped renegotiation points rather than dead stops.

### Context library links

_none_

### Tests to add or update

- `tests/test_outcome_intent.py`

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/433
- Number: 433
- Created at: 2026-07-04T08:12:15.719818+00:00

