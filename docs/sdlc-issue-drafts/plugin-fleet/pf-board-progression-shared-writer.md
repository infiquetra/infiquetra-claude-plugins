---
title: capability — board_progression.py, the certificate-gated autonomous status writer shared by /outcome, /work, and /loop
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
wave: wave-1
objective: Ship run-start intent envelope for lifecycle autonomy
---

# capability — board_progression.py, the certificate-gated autonomous status writer shared by /outcome, /work, and /loop

### Objective

Ship run-start intent envelope for lifecycle autonomy (wave-1).

---
date: 2026-07-03
topic: board-progression-shared-writer
maturity: requirements-ready
source: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T7.json — T7-F4-2 (primary), T7-F1-3, T7-F2-4; docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json — S-19
depends_on: "#279 (S-2 reversibility/idempotency certificate) and #295 (board↔saga reconciliation on resume) — both merged; this issue extracts and widens their write path, it does not redo them"
repo: infiquetra-claude-plugins
---

# board_progression.py: certificate-gated autonomous status writer shared by /outcome, /work, and /loop

## Summary

`/outcome`'s autonomous board-sync writer (`outcome_board_sync.py`, merged in #279/#295) already
proves the pattern: a reversibility-classified allowlist gates every board write through
`reversibility_certificate.authorize_write`, records each write as a saga tick, and returns `GATE`
(never a silent skip) for anything not on the allowlist. Today that writer is wired to exactly one
caller — `/outcome`'s `advance` reconcile tick (`outcome.py:684`). `/work`'s post-merge Status/close
moves and `/loop`'s lifecycle-arc rendering still do not go through it: `/work` prompts the operator
for Status/close moves by hand at merge time, and `/loop` has no idea→deploy visual progress
projection at all. This issue extracts the writer into a shared, plugin-agnostic module
(`board_progression.py`), keeps its allowlist/certificate/GATE contract intact, and wires two new
consumers — `/work` (post-merge) and `/loop` (on-route) — onto it. It also ships a derived,
read-only `project_arc` renderer in `status_card.py` so `/loop` can show the idea→deploy arc as a
pure function of durable saga fields, with no board field ever treated as a writable source of
truth.

## Problem frame

**What already exists and is verified (do not rebuild).** `outcome_board_sync.py` implements the
allowlist-gated writer end to end: `_candidate_ops` derives the bounded set of reversibility-eligible
ops per leaf state (`outcome_board_sync.py:149`), `reconcile_board` calls
`reversibility_certificate.authorize_write` per candidate op and appends a `{status:"gated"}`
record — never a silent write, never a silent skip — on any op the certificate does not authorize
(`outcome_board_sync.py:177-196`, `:316-328`). It is called from exactly one site:
`outcome.py:652-684`, inside `/outcome`'s `advance` reconcile tick. This is the whole of today's
autonomous-write surface.

**What is missing (the grounded gap this issue closes).**
- `/work`'s post-merge phase still prompts the operator for the Status move and issue close by hand
  (`plugins/saga/skills/work/SKILL.md:374`, "`/work` renders and hands the comment to
  `mission-control`; it does not file or mutate the issue itself" — no autonomous-write path exists
  here at all). Every merge that lands through `/work` re-asks a question `/outcome` already answers
  autonomously for its own leaves.
- `/loop` has no derived progress projection. `status_card.py` today ships `project_work`
  (`status_card.py:246`) and other gate-sequence archetypes, but no `project_arc` — so there is no
  single-glyph idea→deploy rendering, and any such rendering that did exist would be tempted to read
  a writable status field rather than derive from saga fields, repeating the exact anti-pattern the
  binding decision below forbids.
- Root cause named in the grounding brief: "the fleet's ONE operator-facing model/effort lever…"
  aside, the recurring-pain synthesis independently names **"Manual ship ceremony… done by raw git/gh
  in session after session, even where saga/mission-control is installed (8 repos)"**
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:119-121`, theme 7) and **"saga
  append-only… derive-on-read over committed state"** as a recurring rejected alternative
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:109`). The manual Status/close prompt in
  `/work` is theme 7's remaining instance inside this very repo; a `/loop` arc that consulted a
  writable field would be theme-109's rejected alternative recurring again.

**Binding decision this issue must honor.** The `/outcome` campaign's settled architecture (U1–U11,
`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:48`) is explicit: *"Derived-on-read status,
never committed status fields; HALT-not-degrade; backend menu off-by-default with host-conditional
degrade; cost ledger = leaf-produced fact."* This issue extends that architecture to two new
consumers — it does not relax it. Every board write anywhere in the fleet must still go through the
one certificate-gated writer; every board *read* used for progress display must still be a pure
derivation over durable saga fields, never a cached or committed status column.

## Key decisions

**KD1 — Extraction, not reinvention.** `board_progression.py` is `outcome_board_sync.py`'s writer
logic (allowlist, `_candidate_ops`, `authorize_write` call, GATE/record path) lifted into a
plugin-agnostic module with the caller-specific glue (leaf-state derivation) left behind in
`outcome.py`. The certificate contract (#279) and the reconcile-on-resume contract (#295) are
untouched; this issue is a consumer-widening, not a rewrite of either.

**KD2 — Reversibility allowlist is config, not caller-specific code.** The allowlist that decides
which ops are eligible for autonomous write (Status move, label add/remove, sub-issue close,
coalesced comment) is expressed once, as data, and consumed identically by `/outcome`, `/work`, and
`/loop`. A caller does not get to special-case its own bypass of the allowlist.

**KD3 — Merge and deploy are permanently gated, in every consumer.** `/outcome`'s existing rule
("PR-merge / deploy autonomy — permanently HITL," `docs/sdlc-issue-drafts/2026-06-28-capability-board-saga-reconciliation-on-resume.md`,
Scope Boundaries) carries over unchanged to `/work` and `/loop`: a merge or deploy candidate op
always returns `GATE`, regardless of caller. Widening the consumer set must not widen what is
autonomously actionable.

**KD4 — `/loop`'s arc is read-only and derived.** `project_arc` in `status_card.py` computes the
idea→deploy glyph from the same durable saga fields every other `status_card.py` archetype reads
(saga-spec §6 full-snapshot fields) — it consults no writable status column, board cache, or
`board_progression.py` write-record as ground truth for *rendering*. It may read `board_progression`'s
write-record stream only to know what was already asserted, never to decide what to render next.

**KD5 — `/work`'s post-merge move stops prompting when the op is on the allowlist.** Today `/work`
asks the operator by hand for every post-merge Status/close move. After this issue, an op inside the
reversibility allowlist (e.g., Status → Done, sub-issue close after merge) fires through
`board_progression.py` with no prompt; an op outside the allowlist (or a merge/deploy) still prompts,
unchanged.

## Requirements

**Shared writer module**
- R1. `board_progression.py` exists at `plugins/saga/scripts/board_progression.py`, contains the
  allowlist config, `_candidate_ops`-equivalent derivation entry point, and the
  `authorize_write`/GATE/record path extracted from `outcome_board_sync.py`, with no behavior change
  to `/outcome`'s existing call site. **(T7-F4-2)**
- R2. `outcome_board_sync.py`'s `reconcile_board` is refactored to call into `board_progression.py`
  for the write path rather than duplicating it; `/outcome`'s existing tests
  (`tests/test_outcome_board_sync.py` or equivalent) stay green with zero behavior diff. **(T7-F4-2)**
- R3. The allowlist config classifies every candidate op as reversible or irreversible; only
  enumerated reversible ops fire autonomously through any consumer, and merge/deploy candidate ops
  return `GATE` from every consumer (`/outcome`, `/work`, `/loop`) — never a silent write, never a
  silent skip. **(T7-F4-2, T7-F1-3)**
- R4. Reversible transitions reflect autonomously (write lands, tick recorded); irreversible
  transitions HALT with a surfaced reason; the diff introduced by this issue commits zero new
  status/board fields into saga or issue state — only the existing write-record ledger grows.
  **(T7-F1-3)**

**New consumers**
- R5. `/work`'s post-merge phase (`plugins/saga/skills/work/SKILL.md` around the existing
  `:374` issue-progress section) calls `board_progression.py` for the post-merge Status move and
  sub-issue close; an allowlisted op fires with no operator prompt, a non-allowlisted op (including
  merge/deploy) still prompts exactly as today. **(T7-F4-2)**
- R6. `/loop` calls `board_progression.py` on-route wherever it currently defers a board mutation to
  `mission-control` by hand, subject to the same allowlist/GATE contract as `/outcome` and `/work`.
  **(T7-F4-2)**

**Derived arc projection**
- R7. `status_card.py` gains a `project_arc` function that renders the idea→deploy progress arc as a
  pure function of durable saga fields (the same fields `project_work` already reads), with no
  writable status field consulted. **(T7-F2-4)**
- R8. `/loop` renders the arc via `project_arc` at least at Route/Drive/Resume entry, replacing any
  manual status narration `/loop` currently produces by hand. **(T7-F2-4)**

**Lifecycle-wide closure**
- R9. Driving a saga through its stages (plan → work → merge → deploy) moves the mission-control
  board card and closes the issue at terminal state, end to end, without an operator having to
  manually move the card at any allowlisted transition. **(S-19)**

## Key flows

F1. **Autonomous reversible move via `/work`.** Trigger: `/work` reaches post-merge with an
allowlisted op (e.g., Status → Done). `board_progression.py` authorizes, writes, records a tick; no
prompt shown. **Covers R3, R4, R5.**

F2. **Gate on merge/deploy from any consumer.** Trigger: any consumer (`/outcome`, `/work`, `/loop`)
proposes a merge or deploy candidate op. `board_progression.py` returns `GATE`; operator is prompted
exactly as today. **Covers R3, KD3.**

F3. **`/loop` renders the arc.** Trigger: `/loop` enters Route, Drive, or Resume for a saga with
board-relevant history. `project_arc` derives the glyph from saga fields only, renders it, consults no
write record to decide the glyph. **Covers R7, R8, KD4.**

F4. **End-to-end lifecycle closure.** Trigger: a saga is driven from plan through deploy across
`/work` and `/loop` without operator board intervention at any allowlisted transition. The board card
and issue reach terminal state solely from the two consumers' allowlisted writes. **Covers R9.**

## Acceptance examples

- **AE1 (allowlist boundary).** A candidate op is on the reversibility allowlist (Status move) →
  fires autonomously through `board_progression.py`, tick recorded, no prompt. **Covers R3.**
- **AE2 (merge always gated).** A candidate op is a PR-merge → `board_progression.py` returns `GATE`
  from every one of `/outcome`, `/work`, `/loop` — never a silent write. **Covers R3, KD3.**
- **AE3 (zero committed status fields).** After a reversible autonomous write, `git diff` over the
  changed saga/issue artifacts shows only ledger/tick growth, no new committed status field.
  **Covers R4.**
- **AE4 (`/work` stops prompting on allowlisted ops).** `/work` reaches post-merge with an allowlisted
  Status move → no operator prompt appears; a non-allowlisted move still prompts. **Covers R5.**
- **AE5 (derived arc, no writable read).** `project_arc` is called twice with identical saga field
  input and differing board-cache state → renders an identical glyph both times, proving it is a pure
  function of saga fields, not board state. **Covers R7, KD4.**
- **AE6 (lifecycle closure).** Driving a saga from plan to deploy through `/work` and `/loop` results
  in the mission-control card at terminal status and the issue closed, with no manual board move by
  the operator at any allowlisted step. **Covers R9.**

### Out-of-scope / non-goals
**In:** extracting `outcome_board_sync.py`'s writer into `board_progression.py`; wiring `/work`
(post-merge) and `/loop` (on-route) as new consumers of the existing allowlist/certificate contract;
adding `project_arc` to `status_card.py`; wiring `/loop` to render it.

**Out:**
- Rebuilding or relaxing the reversibility certificate (#279) or the resume-time reconciliation
  path (#295) — both stay exactly as merged; this issue is a consumer-widening only.
- Widening the reversibility allowlist itself (which ops count as reversible) — that is a separate,
  security-review-worthy change; this issue consumes the allowlist as it exists today.
- Making merge or deploy autonomous under any consumer — permanently HITL, unchanged.
- Any change to `/outcome`'s own call site or behavior beyond the internal refactor in R2 (zero
  behavior diff required).
- A standing monitor, webhook, or scheduled board-drift probe — out of scope for both #295 and this
  issue.

## Dependencies / assumptions

- **Hard — #279 (reversibility/idempotency certificate) and #295 (board↔saga reconciliation).** Both
  merged. `board_progression.py` extracts #279's writer; `/loop`'s arc must not regress #295's
  reconcile-on-resume contract when it renders a saga that has pending divergence.
- **Verified today:** `outcome_board_sync.reconcile_board` is called only from `outcome.py:684`
  inside `advance`; no other call site exists (`grep -n "outcome_board_sync\|reconcile_board"
  plugins/saga/scripts/outcome.py`). `status_card.py` has no `project_arc` today
  (`grep -n "project_arc" plugins/saga/scripts/status_card.py` — no match).
- **Assumption to confirm in `/plan`:** the exact seam in `plugins/saga/skills/work/SKILL.md` where
  the post-merge Status/close prompt currently lives (around `:374`, the issue-progress section) is
  the correct integration point for R5; `/plan` confirms rather than this issue asserting it.

## Definition of Done

- `/work`'s post-merge phase no longer prompts for allowlisted Status/close moves; non-allowlisted
  and merge/deploy ops still prompt.
- `/loop` renders a derived idea→deploy arc at Route/Drive/Resume, sourced only from durable saga
  fields.
- `/outcome`'s existing behavior is unchanged (zero test diff beyond the internal refactor) after the
  extraction.
- No new committed status field appears in any saga or issue artifact touched by this issue's diff.

## Grounding References

- **T7-F4-2** (primary) — "Widen the autonomous allowlist consumer from `/outcome` to `/work` and
  `/loop`" (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T7.json`). dod_sketch: merged
  `board_progression.py` (certificate-gated writer extracted from `outcome_board_sync`) consumed by
  `/work` post-merge and `/loop` on-route; test asserts only enumerated reversible ops fire,
  merge/deploy return `GATE`, and `/work`'s post-merge Status/close moves no longer prompt.
- **T7-F1-3** (facet) — "Widen the `/outcome` autonomous status allowlist with a derive-on-read
  reversibility classifier" (same source file). dod_sketch: reversibility-classified status allowlist
  config consumed by the outcome schema-resolve path; reversible transitions reflect autonomously,
  irreversible ones HALT, zero committed status fields in the diff.
- **T7-F2-4** (facet) — "Derived idea→deploy arc projection in `/loop` — replace manual status
  narration" (same source file). dod_sketch: `project_arc` renderer in `status_card.py` plus a
  `/loop` render call; the arc glyph is a deterministic function of durable saga fields with no
  writable status field consulted.
- **S-19** (facet, thin seed reconstructed from `basis`) — "Auto-update status / close issues through
  the lifecycle" (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json`). `basis_type:
  direct`, `basis`: operator statement "auto-update status/close issues through the lifecycle."
  Reconstructed intent (grounding brief §5/§6, theme 7 "Manual ship ceremony… done by raw git/gh in
  session after session, even where saga/mission-control is installed," and the `/outcome` campaign's
  derived-on-read binding decision, §2): the operator wants the board card and issue to progress and
  close automatically as a saga is driven through its lifecycle stages, without hand-narrated status
  moves at each stage — exactly the closure this issue's R9/AE6 verify end to end.
- **Binding decisions engaged:** `/outcome` campaign (U1–U11) — derived-on-read status, never
  committed status fields, HALT-not-degrade (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:48`);
  this issue extends rather than relaxes that architecture to two new consumers.

## Recommended executor profile

- **Model:** sonnet. **Effort:** high *(target posture — inert until `pf-effort-first-class` lands; teammates inherit session tier)*. **Backend:** team-execution. **External LLM:** none.
- **Justification (above-sonnet-tier note: not applicable — this is sonnet/high, the fleet's
  standard structural tier, no escalation needed):** cross-skill extraction touching `/outcome`,
  `/work`, and `/loop` simultaneously, with autonomy-policy implications (which ops may write
  without a human in the loop) — consensus-worthy per `{#tier-vocab-ordering}` and the
  `/outcome` campaign's HALT-not-degrade posture; team-execution's reviewer fan-out is the right
  backend to catch a caller accidentally widening the allowlist rather than just wiring a new
  consumer onto it.

## Release-surface checklist

This issue changes `saga` plugin behavior (new module, new consumer wiring, new skill-doc behavior in
`/work` and `/loop`). In the same PR:
- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump (currently `0.51.0`) and description
      updated to mention the shared board-progression writer.
- [ ] `.claude-plugin/marketplace.json` — saga entry version/description kept in lockstep with the
      plugin.json bump.
- [ ] `plugins/saga/CHANGELOG.md` — entry describing the extraction, the two new consumers, and the
      new `project_arc` renderer.
- [ ] Any version/metadata drift-guard test (e.g., a marketplace-vs-plugin.json parity test) stays
      green with the bumped version.

### Files expected to change
Indicative only; `/plan` determines the exact set.

- `plugins/saga/scripts/board_progression.py` — new module, extracted writer.
- `plugins/saga/scripts/outcome_board_sync.py` — refactored to call `board_progression.py`; zero
  behavior diff at the `/outcome` call site.
- `plugins/saga/scripts/status_card.py` — new `project_arc` function.
- `plugins/saga/skills/work/SKILL.md` — wire post-merge Status/close through `board_progression.py`
  for allowlisted ops (around the existing `:374` issue-progress section).
- `plugins/saga/skills/loop/SKILL.md` — wire on-route board writes through `board_progression.py`;
  wire `project_arc` rendering at Route/Drive/Resume.
- `tests/test_board_progression.py` — new, root-level (where CI collects).
- `tests/test_outcome_board_sync.py` (or existing equivalent) — updated to assert zero behavior diff
  post-refactor.
- `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
  `plugins/saga/CHANGELOG.md` — release-surface updates per checklist above.

### Tests to add or update
New `tests/test_board_progression.py` (offline, mocking the certificate and any GitHub/board calls):

- Allowlisted reversible op fires autonomously; tick recorded; no `GATE`.
- Merge and deploy candidate ops always return `GATE`, from a harness that calls the module as
  `/outcome`, `/work`, and `/loop` each would.
- Diff of saga/issue artifacts after an autonomous write shows zero new committed status fields.
- `/outcome`'s existing test suite (`tests/test_outcome_board_sync.py` or equivalent) passes unchanged
  after the refactor, proving zero behavior diff.
- `status_card.py`'s new `project_arc`: identical saga-field input plus differing board-cache/mock
  state produces an identical rendered glyph (purity/derived-on-read proof).
- `/work` post-merge integration test: an allowlisted Status/close move fires with no prompt; a
  non-allowlisted or merge/deploy move still prompts.

### Acceptance criteria
- [ ] Only enumerated reversible ops fire autonomously; merge/deploy candidate ops return `GATE` from
      every consumer. Check: `uv run pytest tests/test_board_progression.py -k gate_on_merge_deploy`
      → passes.
- [ ] Reversible transitions reflect autonomously; irreversible transitions HALT; the diff commits
      zero new status fields. Check: `uv run pytest tests/test_board_progression.py -k
      zero_committed_status_fields` → passes.
- [ ] `/outcome`'s existing board-sync behavior is unchanged after the extraction. Check: `uv run
      pytest tests/test_outcome_board_sync.py` → passes with no test count regression.
- [ ] `/loop` renders the idea→deploy arc as a pure function of durable saga fields. Check: `uv run
      pytest tests/test_board_progression.py -k project_arc_is_pure` → passes.
- [ ] Driving a saga through its stages moves the board card and closes the issue at terminal state.
      Check: `uv run pytest tests/test_board_progression.py -k lifecycle_closure` → passes.
- [ ] `/work`'s post-merge phase no longer prompts on allowlisted Status/close moves. Check: `uv run
      pytest tests/test_board_progression.py -k work_post_merge_no_prompt` → passes.
- [ ] Release-surface checklist items (plugin.json, marketplace.json, CHANGELOG, drift-guard tests)
      are updated in the same PR. Check: `uv run pytest tests/ -k marketplace_version_parity` (or
      equivalent existing drift-guard test) → passes.
- [ ] Full suite, format, lint, types stay green. Check: `uv run pytest && uv run ruff format --check
      . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` →
      all pass.

### Verification
```bash
# Extracted writer + new consumers, unit + integration
uv run pytest tests/test_board_progression.py -v

# Zero behavior diff on /outcome's existing board-sync path
uv run pytest tests/test_outcome_board_sync.py -v

# No autonomous write site bypasses the certificate
rg -n "authorize_write" plugins/saga/scripts/board_progression.py plugins/saga/scripts/outcome_board_sync.py

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . \
  && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all green; the `GATE` path is exercised and asserted for merge/deploy from all three
consumers; no new committed status field appears in any test artifact diff.

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

### Source context

- Source: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T7.json (T7-F4-2, T7-F1-3, T7-F2-4);
  docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json (S-19)
- Source type: ideation survivors (issue-map)
- Source title: board_progression.py: certificate-gated autonomous status writer shared by /outcome,
  /work, and /loop

### Intent

`/outcome`'s autonomous board-sync writer (`outcome_board_sync.py`, merged in #279/#295) already proves the pattern: a reversibility-classified allowlist gates every board write through `reversibility_certificate.authorize_write`, records each write as a saga tick, and returns `GATE` (never a silent skip) for anything not on the allowlist. Today that writer is wired to exactly one caller — `/outcome`'s `advance` reconcile tick (`outcome.py:684`). `/work`'s post-merge Status/close moves and `/loop`'s lifecycle-arc rendering still do not go through it: `/work` prompts the operator for Status/close moves by hand at merge time, and `/loop` has no idea→deploy visual progress projection at all. This issue extracts the writer into a shared, plugin-agnostic module (`board_progression.py`), keeps its allowlist/certificate/GATE contract intact, and wires two new consumers — `/work` (post-merge) and `/loop` (on-route) — onto it. It also ships a derived, read-only `project_arc` renderer in `status_card.py` so `/loop` can show the idea→deploy arc as a pure function of durable saga fields, with no board field ever treated as a writable source of truth.

### Context library links

_none_

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/344
- Number: 344
- Created at: 2026-07-04T07:43:59.136449+00:00

