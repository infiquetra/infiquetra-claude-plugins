---
title: "capability: backlog admission governor — pace issue materialization against measured execution throughput"
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
objective: Make the backlog and lifecycle self-improving
wave: wave-3
---

# capability: backlog admission governor — pace issue materialization against measured execution throughput

### Objective

Make the backlog and lifecycle self-improving — stop wave/tier tagging and prepared-issue
materialization from being an act of hope, and start pacing new-draft admission against the
board's own measured execution throughput, so the backlog cannot grow unboundedly faster than
the fleet can actually clear it.

### Problem / Motivation

Nothing in the fleet today paces how many new issues get materialized against how fast issues
actually move. Every board-facing control that exists is a static, hand-set ceiling with no
feedback loop into it, and no control exists at all on the front end (issue creation/handoff):

- **WIP limits are static per-column ceilings on issues already on the board, not admission
  control on new drafts entering it.** `plugins/mission-control/skills/board/SKILL.md:128-139`
  defines a fixed table (Operations Shaping/Ready = 10, Active/Verify = 5; Asgard
  Shaping/Ready = 8, Active/Verify = 5) and instructs the operator to manually "stop pulling
  new work on that board and focus on finishing" when it's exceeded
  (`plugins/mission-control/skills/board/SKILL.md:140-141`). This is prose guidance for a human
  to notice and act on — there is no code path that consults it before a new prepared issue is
  compiled and offered for creation.
- **Flow metrics are measured but never fed back into anything upstream.**
  `plugins/mission-control/scripts/sdlc_manager.py:1611` (`metrics_cycle_time`) and
  `plugins/mission-control/scripts/sdlc_manager.py:1738` (`metrics_wip_age`) compute exactly the
  signal an admission budget would need — per-status cycle time and current WIP age — but these
  are read-only reporting commands (`mission-control:metrics`) with no consumer that acts on the
  numbers. `plugins/mission-control/scripts/sdlc_manager.py:1214` (`board_wip`) similarly reports
  current WIP counts against the static table with no admission decision attached.
- **The prepared-issue materialization path has no admission check at all.** `saga:handoff`
  hands an envelope to `mission-control:issue` (`plugins/saga/skills/handoff/SKILL.md:11-19`
  documents the boundary: saga builds the envelope, mission-control owns "prepared draft
  markdown and JSON sidecar; readiness checks; labels, project fields, board placement, and
  GitHub mutation"). `PreparedIssue` construction and readiness validation happen in
  `plugins/mission-control/scripts/sdlc_manager.py:2970` (`class PreparedIssue`), with
  `issue_prepare` (`:3676`) and `issue_create_prepared` (`:4028`) doing the compile/create work.
  None of these check current board WIP or cycle time before producing or admitting a draft —
  readiness today is purely a content/schema check (see the `card_validator`-shaped
  `blocking_gaps` in the exemplar sidecar
  `docs/sdlc-issue-drafts/2026-06-27-capability-infiquetra-claude-plugins-campps-work-2.json`),
  never a throughput check.
- **This is a recorded, not speculative, gap.** The grounding brief names it directly: "Promote
  ledger: 0 learnings ever promoted; no genuine ≥3-repo transcendent cluster. ... The cross-repo
  learning loop exists but has never fired." (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:72-73`).
  A backlog that keeps materializing drafts irrespective of what the lifecycle can actually
  absorb is the same disease at the intake end: machinery exists, nothing closes the loop back
  onto itself.

## Definition of Done

- A materialization-budget check runs in the Gate-F/handoff path — the point where
  `saga:handoff` hands off to `mission-control:issue`'s prepare/create step
  (`plugins/mission-control/scripts/sdlc_manager.py:3676` `issue_prepare`, `:4028`
  `issue_create_prepared`) — before a new prepared draft is offered for creation.
- The budget is derived from measured flow metrics, not another hand-set constant: it reads
  current WIP age/count (`board_wip`, `:1214`) and recent cycle time
  (`metrics_cycle_time`, `:1611`) for the target board/status and computes an open-WIP
  admission ceiling, replacing (or feeding) the static table at
  `plugins/mission-control/skills/board/SKILL.md:128-139` with a derived one.
- When admission would exceed the computed budget, the draft is held (not silently dropped,
  not created and left to rot) — it is written to the prepared-drafts store with an explicit
  `state: held` / blocked-by-budget marker and a note, rather than being pushed straight to
  `state: ready`.
- An operator override exists, is exercised explicitly (not a hidden default), and is recorded
  in the same sidecar/policy note that the held-state check writes — so an override is always
  auditable after the fact.
- A dry run over this backlog's own wave plan (`docs/plans/plugin-fleet-ideation-2026-07-03/`
  and this issue's own sibling wave-3 drafts) emits the computed admission schedule, showing
  which drafts would be held vs. admitted under measured throughput, without mutating any real
  GitHub state.
- Merged PR includes the check, its unit tests, an updated `board/SKILL.md` reference section
  documenting the derived-ceiling behavior alongside the existing static table, and a
  `docs/engineering-journal/DECISIONS.md` entry recording the design and a revisit-when
  condition.

### Acceptance criteria
- [ ] **Dry-run admission schedule over this backlog's wave plan.** A dry run against the
      wave-3 prepared drafts in `docs/sdlc-issue-drafts/plugin-fleet/` computes and prints the
      admission schedule (admit-now / hold-for-budget per draft) derived from current board WIP
      and cycle time, without creating or mutating any GitHub issue. Check:
      `uv run python3 plugins/mission-control/scripts/sdlc_manager.py issue admission-dry-run --project operations --input docs/sdlc-issue-drafts/plugin-fleet/ --format json | jq '.schedule | length > 0'`
      → `true`.
- [ ] **Admission is derived from measured flow metrics, not a hardcoded constant.** A unit
      test asserts the computed budget changes when the underlying `metrics_cycle_time` /
      `board_wip` inputs change (e.g., synthetic fixture with slow cycle time yields a lower
      admission ceiling than a fixture with fast cycle time). Check:
      `uv run pytest tests/test_admission_governor.py -k budget_derived_from_metrics` → passes.
- [ ] **Over-budget drafts are held, not dropped or silently created.** A unit test asserts
      that when the computed ceiling is exceeded, `issue_prepare`/`issue_create_prepared`
      writes the draft with an explicit held/blocked-by-budget state and a policy note, rather
      than either raising an unhandled error or proceeding to `state: ready`. Check:
      `uv run pytest tests/test_admission_governor.py -k held_not_dropped` → passes.
- [ ] **Operator override is explicit and auditable.** A unit test asserts that passing an
      explicit override flag admits an over-budget draft, and that doing so writes an
      auditable record (who/when/why) into the sidecar rather than silently bypassing the
      check. Check: `uv run pytest tests/test_admission_governor.py -k override_is_auditable`
      → passes.
- [ ] **Under-budget drafts are unaffected.** A unit test asserts that when computed WIP is
      below the derived ceiling, draft admission behaves exactly as it does today (no new
      held state, no behavior change to the existing readiness/`card_validator` checks).
      Check: `uv run pytest tests/test_admission_governor.py -k under_budget_unaffected` →
      passes.
- [ ] **Static WIP table and derived ceiling do not silently diverge.** A test or lint asserts
      the derived-ceiling computation is documented alongside (not as a silent replacement for)
      the existing static table at `plugins/mission-control/skills/board/SKILL.md:128-139`, and
      that the derived ceiling never exceeds the static per-column limit for that board/status.
      Check: `uv run pytest tests/test_admission_governor.py -k derived_never_exceeds_static` →
      passes.
- [ ] **Full suite, lint, types, security stay green.** Check:
      `uv run pytest && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports && uv run bandit -r plugins/`
      → all pass.

- [ ] Full repo gate passes: `uv run pytest && uv run ruff check .`
### Out-of-scope / non-goals
In scope: one admission-budget check fronting the existing `saga:handoff` →
`mission-control:issue` materialization boundary (`issue_prepare` / `issue_create_prepared` in
`plugins/mission-control/scripts/sdlc_manager.py`); deriving the budget from existing
`metrics_cycle_time` / `board_wip` outputs; held-state marking with operator override; a
dry-run mode; documentation of the derived ceiling alongside the existing static WIP table.

Out of scope (do not do in this issue):

- Replacing or removing the static WIP-limits table at
  `plugins/mission-control/skills/board/SKILL.md:128-139` — the derived ceiling is bounded by
  it (never exceeds it), it does not supersede it.
- Any change to the runtime concurrency/wave-width admission control covered by the separate
  `pf-adaptive-admission-governor` issue — that issue governs in-flight execution concurrency
  (`VERIFY_N_CAP`, `/outcome` leaf dispatch); this issue governs backlog intake (new draft
  materialization) and the two do not share a control loop or module.
- Changing `card_validator`/readiness content checks (schema, required sections, placeholder
  detection) — this issue adds a throughput gate alongside those checks, not a replacement for
  them.
- Auto-creating, auto-labeling, or auto-triaging held drafts — held state is a marker for an
  operator to review and override, not an automated promotion path.
- Building a new metrics pipeline — this issue consumes the existing
  `metrics_cycle_time`/`board_wip` outputs as-is; it does not add new metrics collection.
- CAMPPS-board admission — `plugins/mission-control/skills/board/SKILL.md` states CAMPPS is an
  initiative rollup board with no per-column WIP limits; this issue targets Operations and
  Asgard only, where a static ceiling already exists to derive against.

## Grounding References

- `G-negative-space-8` (primary, `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T10.json`)
  — "Backlog admission governor: pace issue materialization against measured execution
  throughput, so wave tagging is machinery instead of hope"; basis: direct; dod_sketch: "Merged
  PR: materialization-budget check in the Gate-F/handoff path holding drafts beyond a
  flow-metrics-derived open-WIP budget (operator override) + policy note; verified by a dry
  run over this backlog's wave plan showing the computed admission schedule." This issue's
  Definition of done and dry-run acceptance criterion are drawn directly from that dod_sketch.
- Binding decisions and prior findings this issue must not violate or duplicate:
  - `{#plugin-portfolio-groom-17-to-7}` (grounding brief §2) — plugin sprawl is an active
    concern; this issue adds a check inside the existing `mission-control` plugin's issue
    materialization path, it does not introduce a new plugin.
  - Recurring-pain finding 3, "mission-control board/field drift — nonexistent fields assumed,
    hardcoded aliases, item-list pagination silently truncating" (grounding brief §7, item 3) —
    this issue's admission check must read live `board_wip`/`metrics_cycle_time` output, not a
    cached or hardcoded WIP assumption, to avoid repeating that drift class.
  - Grounding brief §3 finding 5, "Promote ledger: 0 learnings ever promoted; no genuine ≥3-repo
    transcendent cluster... the cross-repo learning loop exists but has never fired"
    (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:72-73`) — the named evidence that
    machinery-without-feedback-loop is a recurring fleet disease, which this issue's
    "objective: make the backlog and lifecycle self-improving" directly answers at the intake
    end.
  - `saga:handoff` boundary contract (`plugins/saga/skills/handoff/SKILL.md:11-27`) — saga owns
    the envelope and phase inference; mission-control owns prepared-draft body, readiness
    checks, and board placement. The admission-budget check belongs on the mission-control side
    of that boundary (inside `issue_prepare`/`issue_create_prepared`), not inside
    `saga:handoff` itself.

### Recommended executor profile

- **Model:** sonnet. **Effort:** medium. **Backend:** inline. **External LLM posture:** none.
- **Justification:** this is a bounded, mechanical addition to an existing, well-understood
  module (`sdlc_manager.py`'s prepare/create path) consuming metrics functions that already
  exist and are already tested. It is not an architectural judgment call on the order of the
  runtime concurrency governor (`pf-adaptive-admission-governor`, which justifies opus/high +
  second-opinion because a wrong control-loop decision fails silently as starvation or
  oscillation under adversarial load). A held-vs-admit threshold check with an audit record is
  deterministic and unit-testable without an external second opinion.

### Release-surface checklist

This issue changes runtime behavior of the `mission-control` plugin (issue materialization
path) and documentation behavior (`board/SKILL.md`). Update in the same PR:

- [ ] `plugins/mission-control/.claude-plugin/plugin.json` — version bump (new admission-budget
      behavior affecting `issue_prepare`/`issue_create_prepared`).
- [ ] `.claude-plugin/marketplace.json` — reflect the mission-control version bump.
- [ ] `plugins/mission-control/CHANGELOG.md` — entry describing the admission-budget check,
      held-state marker, dry-run mode, and operator override.
- [ ] Any existing plugin-metadata/version drift-guard tests (marketplace/plugin.json parity
      test) re-run green after the bump.
- [ ] `plugins/mission-control/skills/board/SKILL.md` — new section documenting the derived
      ceiling alongside the existing static WIP Limits Reference table (do not delete the
      static table).
- [ ] `docs/engineering-journal/DECISIONS.md` — new entry recording the admission-governor
      design (derived-but-bounded-by-static-ceiling, held-not-dropped, explicit auditable
      override) as settled pattern, with a revisit-when condition (e.g., if per-board static
      limits are retired outright, or if a future fleet-wide admission broker subsumes this
      check).

### Files expected to change

Indicative only — exact set is `/plan`'s to determine.

- `plugins/mission-control/scripts/sdlc_manager.py` — admission-budget check wired into
  `issue_prepare` (`:3676`) and `issue_create_prepared` (`:4028`); new CLI subcommand
  (`issue admission-dry-run`) for the dry-run path; consumes `board_wip` (`:1214`) and
  `metrics_cycle_time` (`:1611`).
- `plugins/mission-control/scripts/sdlc_manager.py` — `class PreparedIssue` (`:2970`) gains a
  held/blocked-by-budget state field and override-audit fields.
- `plugins/mission-control/tests/test_admission_governor.py` (new) — budget-derivation,
  held-not-dropped, override-auditable, under-budget-unaffected, derived-never-exceeds-static
  cases.
- `plugins/mission-control/skills/board/SKILL.md` — new section documenting the derived
  ceiling next to the existing WIP Limits Reference table (`:128-139`).
- `plugins/mission-control/CHANGELOG.md` — Release-surface entry.
- `plugins/mission-control/.claude-plugin/plugin.json` — Release-surface version bump.
- `.claude-plugin/marketplace.json` — Release-surface version bump.
- `docs/engineering-journal/DECISIONS.md` — Release-surface decision entry.

### Verification

```bash
uv run pytest plugins/mission-control/tests/test_admission_governor.py -v
uv run python3 plugins/mission-control/scripts/sdlc_manager.py issue admission-dry-run \
  --project operations --input docs/sdlc-issue-drafts/plugin-fleet/ --format json
uv run pytest && uv run ruff check . \
  && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports \
  && uv run bandit -r plugins/
```

Expected: all green; the dry run emits a non-empty admission schedule with no GitHub
mutation performed.

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

### Source context

- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/issue-map/issue-map-final.json`
- Source type: issue-map
- Source title: Backlog admission governor: pace materialization against measured execution
  throughput

**Absorbed ideas:** G-negative-space-8

### Context library links

_none_

### Tests to add or update

- `tests/test_admission_governor.py`

### Intent

Nothing in the fleet today paces how many new issues get materialized against how fast issues actually move. Every board-facing control that exists is a static, hand-set ceiling with no feedback loop into it, and no control exists at all on the front end (issue creation/handoff):

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/439
- Number: 439
- Created at: 2026-07-04T08:14:34.555742+00:00

