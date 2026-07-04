---
title: capability: Deploy canary + verify + auto-revert flow for the deploy plugin
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
wave: wave-3
objective: Expand saga+deploy capability breadth (misc/quick-wins)
---

# capability: Deploy canary + verify + auto-revert flow for the deploy plugin

### Objective
Expand saga+deploy capability breadth (misc/quick-wins)

### Tier
structural

### Wave
wave-3

### Intent

Add a canary-promote → verify-health → auto-revert flow to the `infiquetra-deploy` (`plugins/deploy`)
plugin: promote a tag-promotion deployment as a canary, evaluate a post-deploy health signal, and
automatically revert to the prior known-good tag when that signal fails — instead of today's
tag-promotion flow, which mints and pushes a tag with no post-deploy verification or rollback
mechanism at all.

### Problem / Motivation

`plugins/deploy` today implements tag-promotion (`plugins/deploy/scripts/mint_tag.py`), deployment
status/drift query (`plugins/deploy/scripts/query_deployments.py`), and release-notes preview
(`plugins/deploy/scripts/preview_release_notes.py`), driven by the `/deploy` command
(`plugins/deploy/commands/deploy.md`). None of that surface reads a post-deploy health signal or
reverts a bad promotion — `mint_tag.py` mints and (optionally) pushes a tag
(`plugins/deploy/scripts/mint_tag.py:1-50`) and stops; `query_deployments.py` only reports current
status/drift after the fact (`plugins/deploy/scripts/query_deployments.py:124`), it does not gate a
promotion or trigger a rollback.

This is a long-queued, deliberately relocated capability, not a new idea invented for this
ideation pass. It was originally built as part of the `/work` execution-engine rebuild
(DECISIONS `{#work-engine-rebuild}`), which merged gstack's `ship`/`land-and-deploy` canary-verify +
offer-revert mechanics into `/work`'s design — then explicitly *read-to-relocate* rather than kept,
because canary/revert is deploy-mutation and sits on the wrong side of `/work`'s hard lifecycle
boundary against `infiquetra-deploy` (saga-spec §1.1/§10): *"gstack's canary-verify + offer-revert
are relocated to infiquetra-deploy (a deliberate brief deviation — read to relocate knowingly, not
dropped silently; the capability is queued there)"* (DECISIONS `{#work-engine-rebuild}`, referencing
`plugins/saga/skills/work/SKILL.md:354` for the deferred advance). The relocation was recorded as a
QUEUED anchor at the time: `docs/engineering-journal/QUEUED.md:41-48`
(`{#infiquetra-deploy-canary-verify-revert}`), which names the engine source explicitly — gstack's
`canary` primitive (plus the canary/revert fragment inside `ship`/`land-and-deploy`) — a post-deploy
health probe → verify → offer-revert-on-failure sequence, to be ported *campaign-style* (extract,
adapt, shed; no vendoring or runtime dependency) and grounded on `infiquetra-deploy`'s own
tag-promotion model and real prod health signals, not gstack's browse daemon.

The 2026-07-03 plugin-fleet grounding brief carried this anchor forward as a pre-existing seed for
this ideation pass (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:96`,
`{#infiquetra-deploy-canary-verify-revert}`) and it survived ideation unmerged with any other
survivor as an orphan seed (`consolidation_rationale`: "Orphan seed placed by reconciler:
deploy-plugin capability breadth, self-contained against deploy-state fixtures" —
issue-map `pf-deploy-canary-verify-revert` entry, absorbed id `S-7`).

The QUEUED anchor itself gates this on one condition worth restating honestly: it was written
"P1 (when prod deploy path exists)" because at authoring time Infiquetra was "pre-revenue greenfield,
no live prod canary; capability [had] nothing to verify against"
(`docs/engineering-journal/QUEUED.md:44`). This issue builds the mechanism against
`infiquetra-deploy`'s own tag-promotion model and deterministic test fixtures
(`plugins/deploy/skills/deploy-state/SKILL.md`), so it does not require a live production health
endpoint to land and be verified — it requires one when this flow is actually invoked against a real
production environment.

### Requirements

R1. A new `plugins/deploy/scripts/canary_verify.py` (or equivalent module under
    `plugins/deploy/scripts/`) implements: promote-as-canary → wait/read a post-deploy health signal
    → decide pass/fail → on pass, complete the promotion; on fail, automatically revert to the prior
    tag for that environment.

R2. The health-signal read is a pluggable/injectable check (a callable or CLI-configurable probe),
    not hardcoded to any one external monitoring vendor — so it can be driven by test fixtures today
    and wired to a real prod signal later without a rewrite.

R3. On revert, the flow uses `infiquetra-deploy`'s own tag-promotion model and existing rollback tag
    convention (`rollback-<environment>-v<version>`, `plugins/deploy/skills/deploy-state/SKILL.md:31`)
    — it does not invent a parallel rollback mechanism.

R4. A failing canary reverts to the immediately-prior promoted tag for that environment; a passing
    canary completes/promotes without reverting. Both outcomes are observable in the flow's output
    (exit code, printed status, or equivalent).

R5. Production, rollback, and hotfix mutation continues to require explicit operator confirmation
    before any tag push, consistent with the existing deploy-state discipline
    (`plugins/deploy/skills/deploy-state/SKILL.md:43`, `:44`) — the canary/verify/revert flow
    automates the sequencing and decision, not the authorization to mutate production.
    Auto-revert-on-failing-canary is the one exception named explicitly in scope (R4); no other
    mutation becomes silent.

R6. `/deploy` (`plugins/deploy/commands/deploy.md`) and the `deploy-state` skill
    (`plugins/deploy/skills/deploy-state/SKILL.md`) document the new canary-verify-revert flow as an
    available mode, alongside the existing plain tag-promotion path.

## Definition of Done

A merged deploy-plugin flow that promotes a tag as a canary, verifies a post-deploy health signal
against a pluggable/injectable probe, and automatically reverts to the prior known-good tag
(using the existing `rollback-<environment>-v<version>` convention) when that signal fails —
verified by test fixtures simulating both a failing canary (triggers revert) and a passing canary
(promotes without reverting), with the new mode documented in `/deploy` and the `deploy-state` skill.

### Acceptance criteria
- [ ] AC1 (S-7). A simulated failing canary (a test fixture health-check returning a failure signal)
      triggers a revert to the prior tag for that environment.
      Check: `uv run pytest tests/test_canary_verify.py -k failing_canary_reverts` → passes.
- [ ] AC2 (S-7). A simulated passing canary (a test fixture health-check returning a success signal)
      completes/promotes without reverting.
      Check: `uv run pytest tests/test_canary_verify.py -k passing_canary_promotes` → passes.
- [ ] AC3. The health-signal probe is injectable/pluggable — the same flow driven against two
      different fixture probes (pass-returning and fail-returning) produces the two outcomes in
      AC1/AC2 without touching the flow's own code.
      Check: `uv run pytest tests/test_canary_verify.py -k pluggable_health_probe` → passes.
- [ ] AC4. Revert uses the existing rollback tag convention
      (`rollback-<environment>-v<version>`) rather than a new tag scheme.
      Check: `uv run pytest tests/test_canary_verify.py -k rollback_tag_convention` → passes.
- [ ] AC5. Production-targeted canary/revert runs still require explicit operator confirmation before
      any tag push; a `--dry-run` invocation performs no mutation.
      Check: `uv run pytest tests/test_canary_verify.py -k production_requires_confirmation` → passes.
- [ ] AC6. `plugins/deploy/commands/deploy.md` and
      `plugins/deploy/skills/deploy-state/SKILL.md` document the canary-verify-revert mode.
      Check: `grep -n "canary" plugins/deploy/commands/deploy.md plugins/deploy/skills/deploy-state/SKILL.md` → at least one match in each file.
- [ ] AC7. Full suite, format, lint, and types stay green.
      Check: `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` → all pass.

### Out-of-scope / non-goals
**In scope**: a new `plugins/deploy/scripts/canary_verify.py` (or equivalent) implementing
canary-promote → verify → auto-revert against `infiquetra-deploy`'s existing tag-promotion model and
rollback-tag convention; test fixtures simulating passing/failing health signals; documentation
updates to `/deploy` and the `deploy-state` skill.

**Out of scope / non-goals**:
- Building or operating a real production health-monitoring endpoint — this issue builds the
  mechanism against deploy-state test fixtures; wiring a live prod signal is a follow-on once a real
  prod deploy path with live health signals exists (the condition the original QUEUED anchor named,
  `docs/engineering-journal/QUEUED.md:44`).
- Any canary/revert logic inside `/work` or `/qa` — `/work` already relocated this capability out of
  its own boundary to `infiquetra-deploy` (DECISIONS `{#work-engine-rebuild}`); `/work` and `/qa`
  route to this flow, they never own it (saga-spec §1.1/§10 deploy-mutation boundary).
- Vendoring or taking a runtime dependency on gstack's `canary` implementation — this is a
  campaign-style port (extract, adapt, shed), not a vendored copy.
- Changing hotfix promotion (`deploy-hotfix`) or release-notes preview (`deploy-notes`) flows —
  untouched by this issue.
- A general-purpose alerting/monitoring plugin — the health-signal probe is a pluggable interface
  for this flow only, not a new monitoring product.

## Grounding References

- `S-7` — primary (sole absorbed id) — `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json:75-85`
  (title "Infiquetra deploy canary + verify + revert"; `basis_type: direct`; `basis`: "QUEUED anchor
  {#infiquetra-deploy-canary-verify-revert} (brief §5)"; `dod_sketch`: "Merged deploy-plugin flow:
  canary promote, verify signal, auto-revert on failure. Verify: simulated failing canary triggers
  revert to prior tag; passing canary promotes (test against deploy-state fixtures)").
- Original relocation record and engine source: `docs/engineering-journal/QUEUED.md:41-48`
  (`{#infiquetra-deploy-canary-verify-revert}`) — names gstack's `canary` primitive (+ the
  canary/revert fragment inside `ship`/`land-and-deploy`) as the engine source, to be ported
  campaign-style (extract, adapt, shed; no vendoring), grounded on `infiquetra-deploy`'s own
  tag-promotion model and real prod health signals rather than gstack's browse daemon. States the
  boundary explicitly: "Lives in `infiquetra-deploy` (owns deploy mutation); `/work` + `/qa` route TO
  it, never own it."
- Binding decision this relocates out of: DECISIONS `{#work-engine-rebuild}` (PR #181, squash
  d398055) — "gstack's canary-verify + offer-revert are relocated to `infiquetra-deploy` (a deliberate
  brief deviation — read to relocate knowingly, not dropped silently; the capability is queued
  there)"; deferred advance recorded at `plugins/saga/skills/work/SKILL.md:354`.
- Brief carry-forward: `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:90-97` (§5,
  "Pre-existing seeds — carry into Phase D as seed candidates"), listing
  `{#infiquetra-deploy-canary-verify-revert}` among the direct pre-existing-seed matches.
- Issue-map consolidation record: issue-map `pf-deploy-canary-verify-revert` entry —
  `consolidation_rationale`: "Orphan seed placed by reconciler: deploy-plugin capability breadth,
  self-contained against deploy-state fixtures" — no other survivor absorbed alongside `S-7`.
- Current deploy-plugin surface this extends: `plugins/deploy/scripts/mint_tag.py` (tag minting/push,
  no post-deploy verification today), `plugins/deploy/scripts/query_deployments.py:124`
  (status/drift reporting only, not a promotion gate), `plugins/deploy/commands/deploy.md` (current
  `/deploy` instructions, no canary mode), `plugins/deploy/skills/deploy-state/SKILL.md:31`
  (existing rollback tag convention `rollback-<environment>-v<version>`) and `:43`-`:44` (existing
  explicit-confirmation discipline for production/rollback/hotfix mutation).

### Recommended Executor Profile

- **Model**: sonnet
- **Effort**: high
- **Backend**: inline
- **External-LLM posture**: none
- **Justification**: A single, well-bounded new module plus fixture-driven tests inside one existing
  plugin's script directory, extending an already-documented tag-promotion model rather than
  inventing new architecture — mechanical build-to-spec work matching the issue-map's own
  `executor_profile` (`model: sonnet`, `effort: high`, `backend: inline`, `external_llm: none`); no
  opus-tier judgment call or cross-plugin consensus surface is present, so no escalation above the
  sonnet default is warranted.

### Release-Surface Checklist

This issue changes plugin behavior (new script, new `/deploy` mode, updated skill guidance) and
therefore requires, in the same PR:

- [ ] `plugins/deploy/.claude-plugin/plugin.json` — version bump reflecting the new
      canary-verify-revert capability (current: `0.1.2`).
- [ ] `.claude-plugin/marketplace.json` — matching version bump for the `deploy` entry
      (current: `0.1.2`, `.claude-plugin/marketplace.json:65`).
- [ ] `plugins/deploy/CHANGELOG.md` — new dated entry describing the canary/verify/auto-revert flow,
      following the existing entry format (`plugins/deploy/CHANGELOG.md:1-13`).
- [ ] Version/metadata drift-guard tests — confirm any existing plugin-metadata consistency test
      (e.g. a marketplace/plugin.json version-match test under `tests/`) is updated or still passes
      against the bumped version.
- [ ] `plugins/deploy/commands/deploy.md` and `plugins/deploy/skills/deploy-state/SKILL.md` — updated
      to document the canary-verify-revert mode as part of the release surface, not just as code.

### Tests to Add or Update

- `tests/test_canary_verify.py` (new) — failing-canary-reverts, passing-canary-promotes,
  pluggable-health-probe, rollback-tag-convention, production-requires-confirmation, dry-run-no-op.
- `plugins/deploy` metadata drift-guard test (existing, if present) — updated for the version bump.

### Verification

```bash
# New flow's own test suite
uv run pytest tests/test_canary_verify.py -v

# Full-repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports

# Confirm documentation mentions the new mode
grep -n "canary" plugins/deploy/commands/deploy.md plugins/deploy/skills/deploy-state/SKILL.md
```

Expected: all green; the final grep prints at least one matching line from each file.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json (id S-7)
- Source type: ideation survivor set (issue-map-final.json entry `pf-deploy-canary-verify-revert`)
- Source title: Deploy canary + verify + auto-revert flow for the deploy plugin

### Context library links

_none_

### Files expected to change

- `plugins/deploy/scripts/mint_tag.py`
- `plugins/deploy/scripts/query_deployments.py`
- `plugins/deploy/scripts/preview_release_notes.py`
- `plugins/deploy/commands/deploy.md`
- `plugins/deploy/skills/deploy-state/SKILL.md`
- `plugins/deploy/scripts/canary_verify.py`
- `plugins/deploy/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`

### Tests to add or update

- `tests/test_canary_verify.py`

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/435
- Number: 435
- Created at: 2026-07-04T08:12:51.435722+00:00

