---
title: capability: team-execution external-engine workers — chaperone dispatch (U12 from #283)
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: plan-ready
---

# capability: team-execution external-engine workers — chaperone dispatch (U12 from #283)

### Objective

Close the one deliberately-deferred leg of #283 (ship-with-deferred, KTD7): let an external engine
(agy, codex) run as a team-execution **worker** or **advisory validator** — via a resident Claude
**chaperone worker** that resolves (`engine_resolver`), dispatches through the existing containment
wrappers, verifies the returned evidence, applies the patch as sole-committer, and writes the
worker-exit provenance manifest. This activates the dispositions #285 reserved in
`plugins/team-execution/skills/team-execution/references/worker-manifest.md:47-49`
(`fell-back-to-claude` / `substituted-engine`) and completes R10/R12 of the #283 requirements doc.

The authoritative spec is the plan:
`docs/plans/2026-07-02-team-execution-external-engine-workers-plan.md` (KTD1–KTD7, U1–U6).

### Intent

Two operator-distinguished delegation intents, each an explicit per-worker choice (plan KTD2):

- **offload** — reduce Claude token spend; the chaperone must be cheap (`sonnet/medium` default)
  or the delegation is net-negative.
- **second-opinion** — an independent pair of eyes; extra tokens assumed; chaperone `opus/high`
  default, `fable/xhigh` per-unit override only.

The intent→tier mapping is a recommendation surfaced in the existing Phase-A tier table; the
operator confirms or overrides per worker — never silently locked.

### Out-of-scope / non-goals

- File-mutating external workers (R23 second half — blocked on the ideation-R14 sandbox profile).
- External engines in any gated/blocking position: reviewer consensus, blocking validators,
  automation-eligibility signals (R13/R15).
- Changes to `engine_resolver.py`, `engine_dispatch.py`, `provenance_manifest.py`,
  `manifest_store.py` — the saga side is complete; this work consumes it.
- Auto-selection of the external validator (explicit `.team-execution.json` opt-in only).
- A measurement/ROI loop over delegation outcomes (maintenance stays `/retro`).

### Files expected to change

- `plugins/team-execution/skills/team-execution/references/external-engine-workers.md` (new, U1)
- `plugins/team-execution/skills/team-execution/SKILL.md` (Workers table columns, wave protocol, U2)
- `plugins/saga/skills/plan/SKILL.md` (KTD2 intent→tier recommendation row + plan-time resolution
  preview in the tier table, U2)
- `plugins/saga/scripts/execution_spec.py` (`Unit.engine_intent`, U3)
- `plugins/saga/scripts/team_emitter.py` (engine-worker rows, U3)
- `plugins/team-execution/skills/team-execution/references/worker-manifest.md` (live engine leg, U4)
- `plugins/team-execution/skills/team-execution/references/validator-registry.md`,
  `validator-criteria.md`, `validator-evidence-state.md` (advisory external validator, U5)
- `plugins/team-execution/CHANGELOG.md`, `plugins/saga/CHANGELOG.md`, both `plugin.json`s,
  `.claude-plugin/marketplace.json`, `docs/engineering-journal/DECISIONS.md` (U6)

### Tests to add or update

- `tests/test_saga_execution_spec.py` — `engine_intent` validation (requires engine/capability;
  closed vocabulary; defaults to `offload`).
- `tests/test_team_emitter.py` — explicit-engine segment renders `worker-<engine>` with Engine
  cell `<key>`; capability segment renders `worker-<capability>` with Engine cell `cap:<key>`;
  Claude rows render `—`/`—`; new column-shape oracles added (none exist today).
- `tests/test_team_execution_plugin.py` — new reference doc packaged + linked; metadata drift
  guards pass with bumped versions.

### Context library links

- Plan (authoritative): `docs/plans/2026-07-02-team-execution-external-engine-workers-plan.md`
- Deferral origin: `docs/plans/2026-07-01-external-engine-capability-routing-plan.md` (KTD7, U12)
- Requirements: `docs/brainstorms/2026-06-27-external-engine-capability-routing-requirements.md`
  (R10, R12–R15, R23–R26)
- Manifest contract: `docs/plans/2026-07-01-evidence-provenance-manifests-plan.md` (#285 R14 leg)

### Acceptance criteria

- [ ] A team plan can declare an engine-owned unit; the emitted Team Structure shows a
  `worker-<engine>` row with Engine and Intent populated (capability-routed units render
  `worker-<capability>` with Engine `cap:<key>`); Claude worker rows are unchanged
  except the two new `—` cells.
- [ ] The chaperone protocol doc fully specifies resolve → dispatch → verify → apply → test →
  manifest, including R26 halt and R8/R24 fallback with visible downgrade notes.
- [ ] An engine worker's exit manifest carries `kind=external-engine`, engine
  identity/effort/protocol, and the honest disposition (`ran-as-requested` /
  `fell-back-to-claude` / `substituted-engine`).
- [ ] The `external-second-opinion` validator exists, is advisory-only (Blocking = never), opt-in
  via `.team-execution.json`, and its absence/failure never blocks a run.
- [ ] No external engine can satisfy a gate anywhere in team-execution (R13/R15 restated in every
  touched contract doc).

### Verification

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run mypy plugins/ scripts/ tests/
# manual: emit a sample spec with one engine unit and inspect the Workers table
python3 plugins/saga/scripts/execution_spec.py emit <sample-spec.json> -o /tmp/sample.workflow.js
python3 plugins/saga/scripts/team_emitter.py <sample-spec.json>
```

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/318
- Number: 318
- Created at: 2026-07-02T04:59:38.063373+00:00

