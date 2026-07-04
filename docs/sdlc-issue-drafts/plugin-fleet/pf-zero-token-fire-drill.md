---
title: "exploration: zero-token fire drill — canonical lifecycle loop on the $0 registry entry"
repo: infiquetra-claude-plugins
type: exploration
team: campps
project: operations
status: Idea
labels: exploration, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
objective: "Stand up the external-engine offload lane"
wave: wave-2
---

# exploration: zero-token fire drill — run one canonical lifecycle loop entirely on the $0 registry entry

### Objective

Stand up the external-engine offload lane.

### Intent

Run one canonical Infiquetra lifecycle loop (idea → plan → work → PR) end-to-end with every
offloadable unit dispatched to the cheapest registry entry — `agy/gemini-3.5-flash-high`,
`cost_speed_rank: 1` in `plugins/saga/references/engine-registry.yaml` (the "$0 registry entry":
lowest-cost-tier, default-for-engine `agy` variant) — instead of a resident Claude worker, and
publish an irreducibility map recording which lifecycle steps offloaded cleanly, which degraded,
and which proved structurally irreducible to Claude. This is a fire drill, not a feature build: the
deliverable is evidence plus a decision document, not new dispatch machinery.

## Problem / Motivation

The fleet already has one working external-engine dispatch contract — the chaperone pattern in
`plugins/team-execution/skills/team-execution/references/external-engine-workers.md` (KTD1: one
resident Claude worker per engine, resolve → dispatch → verify → apply → test → manifest, engine
never write-capable, `worker-manifest.md`'s `fell-back-to-claude` / `substituted-engine`
dispositions) — and one populated cost-ranked registry (`plugins/saga/references/
engine-registry.yaml`, `cost_speed_rank` as the KTD9 tie-break key, `agy/gemini-3.5-flash-high` at
rank 1, "cheapest + fastest (STRONG)"). But per the grounding brief's theme roster (`docs/plans/
2026-07-03-plugin-fleet-grounding-brief.md` section 8, theme 1: "External-LLM integration across
lifecycle") and binding-decision register (section 2: `{#external-engines-never-gatekeepers}` #283,
`{#external-engine-chaperone-dispatch}` #318), nobody has actually run a full lifecycle loop against
that lane end-to-end and recorded what happened. The contract exists on paper; its irreducibility
boundary (which steps genuinely need Claude versus which tolerate the cheapest offload tier) is
unmeasured.

This absence is direct-to-candidate seed `H-F6-3` (theme T2, frame F6, axis `budget-zero`,
`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T2.json`), grounded by the operator's stated
external-LLM posture ("evaluated and incorporated based on analysis, main LLM stays
verifier/gatekeeper — never-gatekeeper, advisory-only" — grounding brief section 2's alignment
note) and by the plugin-portfolio-groom binding decision (`{#plugin-portfolio-groom-17-to-7}`:
new capability claims must prove out against real evidence, not another thought experiment).

Without this drill:
- The chaperone contract's untested assumption — that `agy/gemini-3.5-flash-high` (rank 1, "STRONG"
  cheapest+fastest per registry `capability_profile`) is viable for real lifecycle steps, not just
  synthetic units — stays unverified.
- `{#external-engine-chaperone-dispatch}` (#318, "offload→sonnet/medium, second-opinion→opus/high")
  has no receipt showing offload actually held up across a full loop, only unit-level design intent.
- Future work sizing the external-engine offload lane (Objective: "Stand up the external-engine
  offload lane") has no baseline for which lifecycle steps are worth offloading at all.

## Definition of Done

One canonical lifecycle loop (a single small, real unit of work — e.g. one `/plan` → `/work` →
PR cycle on a scoped, low-risk change) is executed end-to-end with every offloadable step routed
through the `agy/gemini-3.5-flash-high` chaperone lane (`engine_resolver.resolve(..., mode=
"dispatch")` per `external-engine-workers.md` §2), producing:

1. **Receipts** — dispatch manifests (`worker-manifest.md` disposition records:
   `ran-as-requested` / `fell-back-to-claude` / `substituted-engine`) and evidence records for
   every step attempted, stored under the drill's own saga/ledger rows (not a narrative summary).
2. **A published irreducibility map** (a durable markdown artifact, e.g. under
   `docs/engineering-journal/narratives/` or a dedicated `docs/plans/` doc) enumerating every
   lifecycle step attempted, with a verdict per step (`offloaded-clean` / `degraded` /
   `claude-irreducible`) and an evidence pointer (manifest ID, ledger row, or transcript excerpt)
   backing that verdict.
3. **Recommendations + revisit-when conditions** per irreducible step, so a future maintainer knows
   what would have to change (model capability, contract shape, registry entry) before revisiting.

No new dispatch code, registry entries, or chaperone contract changes are in scope — this drill
exercises the existing lane and reports what it finds.

### Acceptance criteria
- [ ] **AC1 (drill is real, not a thought experiment).** The lifecycle loop actually runs against
      the `$0` registry entry (`agy/gemini-3.5-flash-high`, `cost_speed_rank: 1`), producing
      dispatch-manifest receipts and ledger rows for each offloaded step — no step's outcome is
      asserted from memory or extrapolation. Check: manifest store (`manifest_store.py`) contains
      at least one `execution_id` per offloaded step from this drill, each resolvable to a
      `saga.manifest.v1` record.
- [ ] **AC2 (full step coverage with verdict + evidence).** The published irreducibility map lists
      every lifecycle step the drill attempted (minimum: idea/spec framing, plan authoring, one
      implementation unit, one verify/review pass, PR preparation) with an explicit verdict
      (`offloaded-clean` / `degraded` / `claude-irreducible`) and a concrete evidence pointer
      (manifest ID, ledger row reference, or quoted transcript excerpt) for each — no step is
      left unverdicted or backed only by prose.
- [ ] **AC3 (recommendations + revisit-when per irreducible step).** For every step verdicted
      `claude-irreducible` or `degraded`, the doc records a recommendation (what to try next: a
      different registry entry, a contract change, or "stays Claude-only") and an explicit
      revisit-when condition (the trigger that would justify re-attempting offload).
- [ ] **AC4 (never-gatekeeper contract held).** Every offloaded step's evidence was reviewed and
      `verified_by_claude` before counting toward any gate, per `engine_dispatch.satisfy_gate()`
      (`plugins/saga/scripts/engine_dispatch.py:238-258`) — the drill does not bypass or weaken
      `{#external-engines-never-gatekeepers}` (#283) to get a cleaner-looking result.
- [ ] **AC5 (no dispatch-machinery changes).** The drill produces zero changes to
      `engine-registry.yaml`, `engine_resolver.py`, `engine_dispatch.py`, or the chaperone contract
      in `external-engine-workers.md` — findings are captured only in the irreducibility map and
      (if warranted) queued as follow-up ideas, not implemented inline.

- [ ] Full repo gate passes: `uv run pytest && uv run ruff check .`
### Out-of-scope / non-goals
**In scope:** running one real, small, low-risk lifecycle loop through the existing chaperone lane
against the rank-1 registry entry; capturing receipts; writing and publishing the irreducibility
map with recommendations and revisit-when conditions.

**Non-goals (explicitly out of scope for this issue):**
- Building new dispatch machinery, a new registry entry, or a new chaperone shape — this is a
  drill against what already exists (`external-engine-workers.md`, `engine-registry.yaml`).
- Changing the never-gatekeeper or chaperone-dispatch binding decisions (#283, #318) — the drill
  operates strictly within them.
- Standing up a repeating/scheduled measurement loop — this is a one-shot fire drill, matching the
  grounding brief's rejection of standing-ceremony measurement shapes elsewhere in the fleet
  (section 4's "spike-calibration harness... killed" precedent for on-demand over standing checks).
- Any plugin behavior, CLI, or schema change — this issue is pure exploration/evidence-gathering.
  If findings later motivate a registry or contract change, that is a separate follow-up issue.

## Grounding References

- **Absorbed idea:** `H-F6-3` — "Zero-token fire drill: run one canonical lifecycle loop entirely
  on the $0 registry entry and publish the irreducibility map" (theme T2, frame F6, axis
  `budget-zero`, basis_type `direct`, tier_guess `structural`, verdict `survive`) —
  `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T2.json`.
- **Existing chaperone contract:** `plugins/team-execution/skills/team-execution/references/
  external-engine-workers.md` — KTD1 shape, never-gatekeeper enforcement, resolve/dispatch/verify/
  apply/test/manifest steps this drill exercises unmodified.
- **Existing cost-ranked registry:** `plugins/saga/references/engine-registry.yaml` —
  `cost_speed_rank` as KTD9 tie-break key; `agy/gemini-3.5-flash-high` at rank 1 ("cheapest +
  fastest (STRONG)"), the drill's target lane.
- **Binding decisions this issue builds on and must not violate** (grounding brief section 2,
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:41-52`):
  - `{#external-engines-never-gatekeepers}` (#283) — Claude stays verifier-of-record; external
    engines are generator/advisory-reviewer/non-gated-worker only.
  - `{#external-engine-chaperone-dispatch}` (#318) — external engines in teams are chaperone
    dispatch only, never a second executor kind, residency, or git participant.
  - `{#operator-choice-framework}` — operator-choice stays doc-only, `/work`-driven; this drill
    does not introduce a new operator-facing lever.
- **Objective + wave placement:** theme roster item 1 ("External-LLM integration across lifecycle,"
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:157-158`), consolidated under Objective
  "Stand up the external-engine offload lane," wave-2.
- **Operator posture grounding:** grounding brief section 2's alignment note — external-LLM output
  is "evaluated [and] incorporated based on analysis" by the main LLM; never a gatekeeper,
  advisory-only.

## Recommended Executor Profile

- **Model:** sonnet
- **Effort:** medium
- **Backend:** inline
- **External-LLM posture:** offload (this issue's entire purpose is exercising the offload lane —
  the executor itself dispatches lifecycle steps to `agy/gemini-3.5-flash-high` per the chaperone
  contract, then reviews and verifies every result before treating it as evidence)
- **Justification:** this is an evidence-gathering fire drill against an existing, already-designed
  contract, not novel architecture — sonnet/medium is sufficient to run the loop, invoke the
  chaperone dispatch, review returned evidence, and write up the irreducibility map. No case for
  opus/xhigh: there is no ambiguous design decision to reason through, only execution-and-observe.

## Release-Surface Checklist

Not applicable — this issue makes no plugin behavior, schema, command, or prompt change. No updates
required to any `plugins/<plugin>/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
plugin `CHANGELOG.md`, or drift-guard tests. If the irreducibility map's findings later motivate a
registry or contract change, that follow-up issue will carry its own release-surface checklist.

## Files Expected to Change

Indicative only; exact set for `/plan` to determine.

- `docs/plans/plugin-fleet-ideation-2026-07-03/` or `docs/engineering-journal/narratives/` — new
  published irreducibility-map artifact (exact path TBD by `/plan`).
- `docs/engineering-journal/LEARNINGS.md` — dated entry capturing the drill's mechanism and
  generalizable rule, per this repo's auto-maintain convention.
- No changes to `plugins/saga/references/engine-registry.yaml`,
  `plugins/saga/scripts/engine_resolver.py`, `plugins/saga/scripts/engine_dispatch.py`, or
  `plugins/team-execution/skills/team-execution/references/external-engine-workers.md`.

### Verification
```bash
# Confirm no dispatch-machinery files were touched by the drill
git diff --name-only origin/main... -- \
  plugins/saga/references/engine-registry.yaml \
  plugins/saga/scripts/engine_resolver.py \
  plugins/saga/scripts/engine_dispatch.py \
  plugins/team-execution/skills/team-execution/references/external-engine-workers.md
# Expected: empty output

# Confirm the published irreducibility map exists and covers every attempted step
test -f <published-map-path> && grep -c "verdict:" <published-map-path>
# Expected: file exists; count >= number of lifecycle steps attempted (minimum 5 per AC2)

# Confirm dispatch receipts exist for offloaded steps
python3 plugins/saga/scripts/manifest_store.py --list --since <drill-start-date>
# Expected: at least one saga.manifest.v1 record per offloaded step
```

Expected: all checks pass; irreducibility map is committed and readable without access to this
issue's originating conversation.

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan for scoping the specific lifecycle loop to
drill (which small real unit of work, which steps count as "offloadable") before execution.

### Source context

- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T2.json` (idea `H-F6-3`)
- Source type: ideation survivor (issue-map)
- Source title: Zero-token fire drill: run one canonical lifecycle loop entirely on the $0 registry
  entry and publish the irreducibility map

### Context library links

_none_

### Files expected to change

- `plugins/saga/references/engine-registry.yaml`
- `plugins/team-execution/skills/team-execution/references/external-engine-workers.md`
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T2.json`
- `.claude-plugin/marketplace.json`
- `docs/engineering-journal/LEARNINGS.md`
- `plugins/saga/scripts/engine_resolver.py`
- `plugins/saga/scripts/engine_dispatch.py`

### Tests to add or update

- Full repo gate: `uv run pytest` (no new test files named; see Acceptance criteria)
