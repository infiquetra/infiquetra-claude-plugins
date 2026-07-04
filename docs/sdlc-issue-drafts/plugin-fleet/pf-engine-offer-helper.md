---
title: "capability: shared engine_offer helper — one per-stage offer primitive with remembered per-repo prefs and mechanical opt-out defaults"
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
objective: "Stand up the external-engine offload lane"
wave: wave-1
---

# capability: shared engine_offer helper — one per-stage offer primitive with remembered per-repo prefs and mechanical opt-out defaults

### Objective
Stand up the external-engine offload lane

### Summary
One pure, tested `engine_offer` helper that every lifecycle stage (`ideate`, `brainstorm`, `work`,
`doc-review`, `code-review`) calls to decide whether — and at what tier — to offer an external-engine
option for the current unit of work. The helper folds together three previously-separate concerns that
today would otherwise ship as six-plus near-duplicate call sites: (1) per-stage-class intent/tier
resolution (judgment work → `second-opinion`/`opus-high`; mechanical work → `offload`/`sonnet-medium`),
(2) a remembered per-repo preference so the operator is asked once ever, not once per run, and (3) a
mechanical-fingerprint classifier that flips the default to offload-opt-out for scaffold-shaped units
while leaving judgment-shaped units opt-in only.

### Problem Frame
The plan-time tier heuristic and the external-engine chaperone-dispatch model already exist and are
binding (`plugins/saga/skills/plan/SKILL.md:296-308` — the work-shape tier table, including the
`intent=offload`→`sonnet/medium` and `intent=second-opinion`→`opus/high` rows; and DECISIONS
`{#external-engine-chaperone-dispatch}` #318 — external engines in teams are chaperone dispatch only,
never a second executor kind). What is missing is a single reusable *offer* primitive that the
individual lifecycle-stage skills call to surface this choice to the operator. Today each stage that
wants to offer an external engine would have to hand-roll its own intent/tier resolution, its own
remembered-preference storage, and its own mechanical/judgment classification — the ideation survivor
set for this theme independently found six near-duplicate "offer at this surface" variants
(`consolidation_rationale` for `pf-engine-offer-helper` in
`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/` intake, theme T1/frame F2) plus a separate
remembered-default variant and a separate opt-out-default variant, all needing the same underlying
per-stage intent/tier answer. No shared helper exists yet: `grep -rn "engine_offer\|engine-prefs\|mechanical-fingerprint"
plugins/saga/skills/*/SKILL.md` (run 2026-07-03) returns nothing — every stage would otherwise
reinvent this independently, producing five (or more) subtly different intent/tier answers for the
same three lifecycle stages this issue targets, an explicit binding-decision constraint this consolidation
must not violate: Claude remains verifier-of-record everywhere (DECISIONS `{#external-engines-never-gatekeepers}`
#283) — the helper only ever proposes an intent/tier pair for a human or gate to accept, it never
dispatches or gates on its own authority.

### Key Decisions
- **One helper, three call-sites' worth of behavior, not three helpers.** `engine_offer.py` is the single
  entry point for per-stage intent/tier resolution, remembered-preference lookup, and mechanical-fingerprint
  opt-out — the three absorbed facets are implemented as one coherent function, not stitched-together
  separate modules, so `ideate`/`brainstorm`/`work`/`doc-review`/`code-review` each get exactly one call site.
- **Never gatekeeping.** The helper's return value is advisory input to the stage's own operator-choice flow
  (`{#operator-choice-framework}`) — it never itself invokes an external engine or blocks progress. This keeps
  it compliant with `{#external-engines-never-gatekeepers}` (#283) and `{#external-engine-chaperone-dispatch}`
  (#318): offload maps only to `sonnet/medium` chaperone dispatch, second-opinion only to `opus/high`
  advisory-reviewer dispatch — never a residency or gated-decision role.
- **Remembered prefs are silent when unattended, confirmed when attended.** `.saga/engine-prefs.json` is read
  and reused without prompting in unattended/background runs; in an attended run the operator is prompted once
  and the answer is persisted for future runs of that stage in that repo. This must ship with a
  `DECISIONS.md` entry recording the choice and its revisit-when condition (matching the existing pattern at
  `docs/engineering-journal/DECISIONS.md:1997` for adjacent decisions in this file).
- **Mechanical-fingerprint opt-out is a default, not a lock.** A unit classified as scaffold-shaped (matching
  the mechanical-fingerprint classifier) defaults `engine_intent=offload`/`sonnet-medium` with an explicit
  operator opt-out; a judgment-shaped unit never defaults to offload. This mirrors, and must stay consistent
  with, the existing `/plan`-time work-shape tier table (`plugins/saga/skills/plan/SKILL.md:296-303`).

### Actors
- A1. `engine_offer` helper — new pure function/module; computes `{intent, tier}` for a given stage-class
  and unit-fingerprint, and encapsulates the remembered-preference read/write.
- A2. Lifecycle-stage skill (`ideate`, `brainstorm`, `work`, `doc-review`, `code-review`) — the caller; each
  gets exactly one documented call site.
- A3. Operator — attended sessions see a one-time confirm prompt per repo/stage; unattended sessions get
  silent reuse of the remembered preference.
- A4. `.saga/engine-prefs.json` — the per-repo preference store the helper reads and writes.

### Requirements
**Per-stage intent/tier resolution**
R1. The helper returns the correct `{intent, tier}` pair for a given stage class: judgment-shaped stages
(e.g., adversarial review, architectural decision points) resolve to `second-opinion`/`opus-high`; mechanical
stages (scaffolding, deterministic transforms) resolve to `offload`/`sonnet-medium` — consistent with the
`/plan`-time tier table at `plugins/saga/skills/plan/SKILL.md:296-303`.
R2. A drift guard exists that asserts each of the five named surfaces (`ideate`, `brainstorm`, `work`,
`doc-review`, `code-review` SKILL.md files) calls the shared helper rather than a hand-rolled equivalent.

**Remembered per-repo preferences**
R3. `.saga/engine-prefs.json` is read before any prompt is shown; if a preference exists for the current
stage in the current repo, it is reused silently when the session is unattended.
R4. In an attended session, the operator is prompted once per stage/repo combination the first time it is
encountered, and the answer is written back to `.saga/engine-prefs.json` for future runs (ask-once-ever, not
ask-once-per-run).
R5. A preference of `none` (opt out of any engine offer for this stage) round-trips correctly — it is
persisted and subsequently suppresses the prompt without silently defaulting to some other intent.

**Mechanical opt-out defaults**
R6. A unit matching the mechanical-fingerprint classifier (scaffold-shaped: deterministic transform, no
judgment call) defaults to `engine_intent=offload`/`sonnet-medium`, with an explicit operator opt-out
available.
R7. A unit that does not match the mechanical-fingerprint classifier (judgment-shaped) never defaults to
offload — no default engine offer is made unless the operator opts in.

### Key Flows
F1. **Attended first-encounter.** Trigger: a stage calls `engine_offer` for a stage/repo pair with no
existing entry in `.saga/engine-prefs.json`, session is attended. Helper resolves the stage-class
intent/tier (R1), classifies the unit (R6/R7), prompts the operator once, and writes the answer back
(R4). Covers R1, R4, R6, R7.
F2. **Unattended reuse.** Trigger: a stage calls `engine_offer` for a stage/repo pair with an existing
entry, session is unattended. Helper reads `.saga/engine-prefs.json` and reuses the stored preference
silently, no prompt shown. Covers R3.
F3. **Opt-out round-trip.** Trigger: operator previously chose `none` for a stage/repo pair. Helper reads
the stored `none` preference and suppresses any engine offer for that stage/repo going forward, in both
attended and unattended sessions, until the operator explicitly changes it. Covers R5.

### Acceptance Examples
AE1. **Covers R1, R2.** Calling `engine_offer` for the `code-review` stage on a judgment-shaped unit
returns `{intent: "second-opinion", tier: "opus-high"}`; the drift guard confirms `code-review/SKILL.md`
calls the shared helper rather than a local equivalent.
AE2. **Covers R1.** Calling `engine_offer` for the `work` stage on a mechanical/scaffolding unit returns
`{intent: "offload", tier: "sonnet-medium"}`.
AE3. **Covers R3, R4.** First attended call for `(ideate, repo-X)` prompts the operator and writes the
answer to `.saga/engine-prefs.json`; a second call for the same pair in an unattended session reuses the
stored answer without prompting.
AE4. **Covers R5.** An operator preference of `none` for `(doc-review, repo-X)` persists and suppresses
future offers for that pair without falling back to some other default intent.
AE5. **Covers R6.** A unit whose shape matches the mechanical-fingerprint classifier (e.g., a templated
scaffold generation task) defaults to `offload`/`sonnet-medium` even with no stored preference, and the
operator can opt out.
AE6. **Covers R7.** A unit whose shape is judgment-shaped (e.g., an architectural trade-off write-up) never
defaults to `offload` — no engine is offered unless the operator explicitly opts in.

### Out-of-scope / non-goals
- This issue ships the shared decision primitive (`engine_offer.py`) and its five call sites plus the
  preference store and mechanical classifier. It does not implement a new dispatch mechanism — offload and
  second-opinion dispatch already exist per `{#external-engine-chaperone-dispatch}` (#318); this helper only
  decides which intent/tier to *offer*.
- It does not change `{#external-engines-never-gatekeepers}` (#283) — the helper's output remains advisory
  input to each stage's existing operator-choice flow, never a gate.
- It does not add a sixth external-engine surface beyond the five named stages (`ideate`, `brainstorm`,
  `work`, `doc-review`, `code-review`); extending to additional surfaces is a follow-up.
- It does not redesign the `/plan`-time per-unit tier table (`plugins/saga/skills/plan/SKILL.md:296-303`) —
  it reuses that table's tier vocabulary and must stay consistent with it, not fork it.

### Dependencies / Assumptions
- Binding: DECISIONS `{#external-engines-never-gatekeepers}` (#283) — Claude is verifier-of-record; the
  helper never gates.
- Binding: DECISIONS `{#external-engine-chaperone-dispatch}` (#318) — offload→`sonnet/medium`,
  second-opinion→`opus/high`, chaperone dispatch only.
- Reuses the existing work-shape tier heuristic: `plugins/saga/skills/plan/SKILL.md:296-303`.
- Verified absent today: `grep -rn "engine_offer\|engine-prefs\|mechanical-fingerprint" plugins/saga/skills/*/SKILL.md`
  (run against this repo, 2026-07-03) returns no hits — this is greenfield, not a refactor of an existing helper.

## Grounding References
Absorbed ideas, from `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T1.json`:
- `T1-F2-1` (primary, tier `structural`) — "Auto-injected per-stage engine offer — kill the /plan-only
  authoring bottleneck." Basis: `dod_sketch` calls for a pure, tested `engine_offer.py` helper plus one
  documented call site in each of `ideate`/`brainstorm`/`work`/`doc-review`/`code-review` SKILL.md, a
  marketplace/CHANGELOG bump, a unit test that the helper returns `second-opinion`/`opus-high` for
  judgment stages and `offload`/`sonnet-medium` for mechanical stages, and a drift guard that each surface
  uses the shared helper.
- `T1-F2-2` (facet, tier `quick-win`) — "Remembered per-stage engine choice — invert 'ask once per run'
  into 'ask once, ever'." Basis: `dod_sketch` calls for `.saga/engine-prefs.json` read/write, an
  attended-prompt/unattended-silent branch, a schema, tests covering silent-reuse-when-unattended,
  prompt-when-attended, a `none` round-trip, and a `DECISIONS.md` entry with revisit-when.
- `T1-F2-8` (facet, tier `structural`) — "Opt-out offload for mechanical units — invert the default so the
  machinery tags offload." Basis: `dod_sketch` calls for a mechanical-fingerprint classifier at `/plan`
  unit authoring that defaults `engine_intent=offload`/`sonnet-medium` on matching units with operator
  opt-out; tests that a scaffold-shaped unit defaults to offload and a judgment-shaped unit does not; a
  `DECISIONS.md` entry with revisit-when.
- Consolidation rationale (`docs/plans/plugin-fleet-ideation-2026-07-03/` issue-map): `T1-F2-1` is the dedup
  keeper across six offer-at-every-surface variants; `.saga/engine-prefs.json` remembered-default absorbs
  four more variants; the mechanical-fingerprint opt-out default is a second policy the same helper
  consults. One tested helper, one PR, per-SKILL call sites — not three separate helpers.
- source_context: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T1.json` (ids `T1-F2-1`, `T1-F2-2`,
  `T1-F2-8`)
- source_context: `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §2 (binding-decision register)

### Files expected to change
Indicative only — the exact set is `/plan`'s to determine.
- `plugins/saga/scripts/engine_offer.py` — new pure helper module (intent/tier resolution, mechanical
  fingerprint classifier, remembered-preference read/write).
- `plugins/saga/skills/ideate/SKILL.md` — one documented call site.
- `plugins/saga/skills/brainstorm/SKILL.md` — one documented call site.
- `plugins/saga/skills/work/SKILL.md` — one documented call site.
- `plugins/saga/skills/doc-review/SKILL.md` — one documented call site.
- `plugins/saga/skills/code-review/SKILL.md` — one documented call site.
- `.saga/engine-prefs.schema.json` (or embedded schema in `engine_offer.py`) — the preference-store schema.
- `plugins/saga/.claude-plugin/plugin.json` — version bump.
- `.claude-plugin/marketplace.json` — plugin metadata sync.
- `plugins/saga/CHANGELOG.md` — entry for the new helper.
- `docs/engineering-journal/DECISIONS.md` — new entry for the remembered-preference and opt-out-default
  choices, each with a revisit-when condition.
- `tests/test_engine_offer.py` — new tests (intent/tier resolution, remembered-preference round-trip,
  mechanical-fingerprint opt-out, drift guard).

### Tests to add or update
- Intent/tier resolution: judgment-class stage → `second-opinion`/`opus-high`; mechanical-class stage →
  `offload`/`sonnet-medium`.
- Remembered preference: silent-reuse-when-unattended, prompt-when-attended, `none` round-trip.
- Mechanical-fingerprint opt-out: scaffold-shaped unit defaults to offload; judgment-shaped unit does not.
- Drift guard: each of the five named SKILL.md surfaces calls the shared `engine_offer` helper.

### Context library links
- source_context: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T1.json` (ids `T1-F2-1`, `T1-F2-2`,
  `T1-F2-8`)
- source_context: `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §2 (binding-decision register)

## Definition of Done
`engine_offer.py` ships as one pure, tested helper with a documented call site in each of the five
named SKILL.md files, backed by a drift guard proving each surface calls it rather than a hand-rolled
equivalent. `.saga/engine-prefs.json` remembered-preference read/write (silent-unattended,
prompt-once-attended, `none` round-trip) and the mechanical-fingerprint opt-out default are both in
place and covered by tests, with corresponding `DECISIONS.md` entries and revisit-when conditions.
Release-surface metadata (plugin version, marketplace entry, CHANGELOG) lands in the same PR, and the
full test/format/lint/type gate is green.

### Acceptance criteria
- [ ] Helper returns `{intent: "second-opinion", tier: "opus-high"}` for a judgment-class stage and
  `{intent: "offload", tier: "sonnet-medium"}` for a mechanical-class stage. Check:
  `uv run pytest tests/test_engine_offer.py -k intent_tier_resolution` → passes.
- [ ] Drift guard confirms each of `ideate`, `brainstorm`, `work`, `doc-review`, `code-review` SKILL.md calls
  the shared helper (not a local equivalent). Check: `uv run pytest tests/test_engine_offer.py -k drift_guard`
  → passes.
- [ ] Unattended session silently reuses a stored `.saga/engine-prefs.json` preference with no prompt. Check:
  `uv run pytest tests/test_engine_offer.py -k unattended_silent_reuse` → passes.
- [ ] Attended session on first encounter prompts once and persists the answer for future runs. Check:
  `uv run pytest tests/test_engine_offer.py -k attended_prompt_once` → passes.
- [ ] A stored `none` preference round-trips and suppresses future offers without defaulting elsewhere.
  Check: `uv run pytest tests/test_engine_offer.py -k none_roundtrip` → passes.
- [ ] A scaffold-shaped (mechanical-fingerprint match) unit defaults to `offload`/`sonnet-medium` with an
  available operator opt-out. Check: `uv run pytest tests/test_engine_offer.py -k mechanical_opt_out_default`
  → passes.
- [ ] A judgment-shaped unit never defaults to offload. Check:
  `uv run pytest tests/test_engine_offer.py -k judgment_no_offload_default` → passes.
- [ ] `DECISIONS.md` carries an entry for the remembered-preference behavior and the opt-out-default
  behavior, each with a revisit-when condition. Check: `grep -n "revisit-when" docs/engineering-journal/DECISIONS.md`
  → includes new entries for this change.
- [ ] Release-surface metadata (plugin version, marketplace entry, CHANGELOG) is updated in the same PR.
  Check: `git diff --name-only` includes `plugins/saga/.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`, and `plugins/saga/CHANGELOG.md`.
- [ ] Full suite, format, lint, and types stay green. Check:
  `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`
  → all pass.

### Verification
```bash
# Unit tests for the new helper
uv run pytest tests/test_engine_offer.py -v
# Confirm drift guard covers all five surfaces
uv run pytest tests/test_engine_offer.py -k drift_guard -v
# Confirm DECISIONS.md carries the required entries
grep -n "revisit-when" docs/engineering-journal/DECISIONS.md | tail -5
# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```
Expected: all green; drift guard test enumerates and passes for all five named SKILL.md surfaces;
`DECISIONS.md` contains new entries with revisit-when conditions for both the remembered-preference and
mechanical opt-out-default behaviors.

### Recommended executor profile
- **Model:** sonnet
- **Effort:** medium
- **Backend:** inline
- **External-LLM posture:** none
- **Justification:** This is a self-contained, mechanically-scoped helper-plus-call-sites change (one
  pure module, a documented call site per existing SKILL.md, a preference-store schema, and a drift-guard
  test) with no architectural ambiguity to resolve — the intent/tier vocabulary and chaperone-dispatch
  constraints are already settled by binding decisions #283 and #318 and the existing `/plan`-time tier
  table. Sonnet/medium is sufficient; no case for opus or an external engine here since the work itself is
  building the offer primitive, not consuming one.

### Release-surface checklist
This issue changes plugin behavior (new helper + new call sites in five skill files), so the following
must land in the same PR:
- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump.
- [ ] `.claude-plugin/marketplace.json` — plugin metadata sync.
- [ ] `plugins/saga/CHANGELOG.md` — entry describing the new `engine_offer` helper and its five call sites.
- [ ] Drift-guard test (`tests/test_engine_offer.py -k drift_guard`) enumerating all five surfaces, so a
  future stage-skill edit that bypasses the shared helper fails CI instead of silently drifting.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T1.json` (ids `T1-F2-1`, `T1-F2-2`, `T1-F2-8`)
- Source type: ideation-survivor
- Source title: Shared engine_offer helper — one per-stage offer primitive with remembered per-repo prefs and mechanical opt-out defaults

### Intent

One pure, tested `engine_offer` helper that every lifecycle stage (`ideate`, `brainstorm`, `work`, `doc-review`, `code-review`) calls to decide whether — and at what tier — to offer an external-engine option for the current unit of work. The helper folds together three previously-separate concerns that today would otherwise ship as six-plus near-duplicate call sites: (1) per-stage-class intent/tier resolution (judgment work → `second-opinion`/`opus-high`; mechanical work → `offload`/`sonnet-medium`), (2) a remembered per-repo preference so the operator is asked once ever, not once per run, and (3) a mechanical-fingerprint classifier that flips the default to offload-opt-out for scaffold-shaped units while leaving judgment-shaped units opt-in only.

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/451
- Number: 451
- Created at: 2026-07-04T08:22:03.738942+00:00

