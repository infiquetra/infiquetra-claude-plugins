---
title: Operator Gate-Status Card — Implementation Plan
type: feat
status: active
date: 2026-06-29
origin: docs/brainstorms/2026-06-27-operator-gate-status-card-requirements.md
---

# Operator Gate-Status Card — Implementation Plan

Build one shared, fixed-position **glyph card** that projects every saga status-bearing
surface (`/work`, `/code-review`, `/qa`, `/outcome`, `/resume`) through a single render site —
derived-on-read from durable engine state, constant in size, every determinable cell traceable
to its evidence. Replaces today's ad-hoc, per-surface status prose. Implements issue
[#278](https://github.com/infiquetra/infiquetra-claude-plugins/issues/278) (VECU survivor S-5),
whose requirements doc passed `/doc-review` (verdict READY,
`docs/reviews/2026-06-27-operator-gate-status-card-readiness.md`).

This plan is the HOW. The WHAT is settled in the requirements doc; this plan does not reopen it.
The four forks the requirements explicitly deferred to `/plan` are resolved as KTD1–KTD4 below,
each confirmed against the actual code.

## High-Level Technical Design

```
                  ┌─────────────────────────────────────────────┐
   durable state  │  status_card.py   (the ONLY status emitter)  │
   (derived-on-   │                                              │
    read)         │  state enum (R1) ─ glyph+label map (R8/R9)   │
                  │  card-spec model ─ render(spec) -> str        │
  saga envelope ──┤    archetype: gate-sequence | summary-proj   │──> fixed positional card
  + gate_verdicts │    indexed-footer drill-down refs (R12/R13)  │    (constant size, R3)
  code-review art ┤                                              │
  qa artifact ────┤  per-surface projection builders:            │
  outcome_proj ───┤    project_work / project_code_review /       │
  saga restore ───┤    project_qa  (gate-sequence)               │
                  │    project_outcome / project_resume (summary) │
                  └─────────────────────────────────────────────┘
```

Two archetypes under one glyph grammar (KD6). **Gate-sequence** (`/work`, `/code-review`, `/qa`):
one row per declared gate, in order, a static superset so an unreached gate still occupies its row
as *not-reached*. **Summary-projection** (`/outcome`, `/resume`): a fixed set of summary rows over
dynamic state, so a 3-node and a 30-node DAG render the same height. Both are constant-size; they
differ only in what a row *is*.

The renderer never reads operator input — every cell is computed from durable state, mirroring the
`outcome_projection.py` invariant (`assert p["states"] == derive_states(...)`, `"status" not in p`;
`outcome_projection.py:37-83`). The display-label map (`saga.py:73-87`,
`#display-label-map-decouples-enum-from-prose`) is the precedent for R9: frozen wire values, an
additive operator-label map, raw-string fallback on miss.

## Grounding (verified facts, with citations)

- **R7 capture gap is real.** `saga.py:215` `checks_run` is a `ListOrAbsent` of check *names*
  (`["pytest","ruff"]`); `phase_status` (`saga.py:162`) is a coarse enum
  (`pending|in_progress|complete`). Neither carries a per-gate pass/fail verdict, so the `/work`
  "Tests" cell cannot distinguish *ran* from *passed* from *failed* today. → KTD4 / U2.
- **Drill-down targets are already per-row parseable** (so R12 needs *zero* new artifact capture):
  code-review artifact has a `| Unit | Status | Evidence |` table + `Scope Check: CLEAN|BLOCKED` +
  a verdict line; qa artifact has YAML `verdict:` / `health_score:` + a `| risk class | score |
  result |` table; doc-review readiness has `blocked:` + a `| Pri | … | Status |` table.
- **No card renderer exists today** (grep for glyph/card/StatusCard under `plugins/saga/` →
  zero). The only renderer is `render_docs_visuals.py` (Mermaid/SVG docs, unrelated).
- **The five surfaces' current status emitters** (R14 migration targets): `/work` SKILL §5.4
  (continuation routing prose, ~lines 402-415); `/code-review` SKILL §5.2 (findings table,
  ~243-249); `/qa` SKILL §5.1 (health-score block, ~235-243); `/outcome` `project` verb already
  calls `outcome_projection.project()` (`outcome.py:1102-1110`); `/resume` Phase 3a reconciliation
  prose (~171-184). The `/work` §4.3 and `/qa` §5.2 `issue_progress.py` emissions are the
  mission-control GitHub write — **out of scope** (a separate operator-initiated consumer).
- **Saga state model:** append-only ticks `.claude/saga/sagas/<id>/<ts>.md` (markdown frontmatter)
  + derived `state.json`; full-snapshot list semantics + scalar carry-forward; `restore()` reads
  the latest tick by filename order and never calls git (`saga.py:870-880`).
- **Test conventions:** dynamic module load (`importlib.util.spec_from_file_location`,
  `test_completeness_gate.py:14-21`), factory-injected state, derived-state assertions,
  doc-contract token-presence tests (`test_saga_plugin.py:168-201`). Saga-state round-trip tests
  live in `tests/test_saga_saga.py`; doc-contract tests in `tests/test_saga_plugin.py`.
- **Quality gate (CI parity):** `uv run pytest && uv run ruff format --check . && uv run ruff
  check . && uv run mypy plugins/` (+ `bandit -r plugins/`). Ruff line length 100.

## Requirements (carried forward from the issue)

Authoritative text: the requirements doc (`origin`). Stable R-IDs preserved for traceability.

R1. Fixed-position glyph card; state set **done · in-progress · blocked · failed · halted ·
not-reached/unknown**; status read by location, not prose. (Glyph/label set ratified — KTD1.)
R2. Every cell derived-on-read; **no operator-writable status field**; fresh process regenerates an
identical card.
R3. Constant-size and position-stable (gate-sequence: static superset; summary-projection: fixed
rows).
R4. A single shared renderer is the **only** emitter of operator-facing status (made true by R14).
R5. Renders at the status boundaries of all five surfaces.
R6. `/outcome` reuses `outcome_projection.py` — no second outcome projection, no row-per-node.
R7. For `/work`, `/code-review`, `/qa`, `/resume`, define a derived-on-read projection per surface;
add capture where state isn't yet derivable (notably the `/work` test verdict — KTD4).
R8. Shared concepts → one operator label + one glyph wherever they appear; surface-specific rows
named once.
R9. Operator labels decoupled from wire identifiers via a render-edge display-label map.
R10. Vocabulary enforced by construction (single render site); depends on R14. No separate lint v1.
R11. Agent-facing markers stay distinct from the operator-facing vocabulary.
R12. Every determinable cell carries a resolvable reference (saga tick/field · durable artifact ·
external read). The card is the top layer of a projection, never the only layer.
R13. A glyph never asserts a status the operator cannot trace; unknown/not-reached renders as such
and is exempt from R12. Failure/halt is determinable and must carry its reference.
R14. Retire or route every existing per-surface prose **status** emission through the renderer
(`/work` §5.4, `/code-review` §5.2, `/qa` §5). Likely the bulk of v1.

(Acceptance examples AE1–AE10 from the issue map to the per-unit test scenarios below.)

## Key Technical Decisions

**KTD1 — Glyph + label set: restrained Unicode.** The single render site uses
`✓ done · ◐ in-progress · ⊘ blocked · ✗ failed · ‖ halted · · not-reached/unknown`. Operator's
call (terminal is iTerm2/tmux, Unicode-capable); failure and halt are visually unmistakable, which
R1 requires. ASCII-safe (`[x] [~] [!] [F] [H] [ ]`) is the documented fallback if a strict-ASCII
pipe ever needs it — the glyph set lives behind the display-label map (R9) so swapping it is a map
edit, not a render-logic change.

**KTD2 — Renderer home: a Python script `plugins/saga/scripts/status_card.py`**, mirroring
`outcome_projection.py`. The card must regenerate deterministically and be unit-tested (R2/AE2,
`tests/test_status_card.py`); an agent-rendered skill-reference doc cannot satisfy a determinism
test (nothing for AE2 to call). One importable `render()` = the single emitter (R4/KD2). Each
SKILL.md invokes it. *Rejected:* shared skill-reference doc (not deterministically testable).

**KTD3 — Drill-down: indexed footer.** Each determinable cell carries a short `[n]` index; the
references collect in a block below the card. Keeps the card body narrow and column-aligned
(protects R3 constant-width), scales to many rows, and puts all evidence in one scan. Reference
types are the R12 enumeration: saga tick/field, durable artifact path, or external read
(GitHub PR/CI/HITL target). Not-reached/unknown cells carry no index (R13). *Rejected:* inline ref
(rows go ragged/wrap, threatening constant-width); resolvable-id (evidence a keystroke away, not
visible).

**KTD4 — `/work` Tests verdict: add a structured `gate_verdicts` capture** to the saga envelope —
a full-snapshot field carrying `{gate, state, ref}` entries, **written by the producing gate**
(the `/work` test gate) and **read by the card** (the `/work` projection). Derived from gate
machinery, never operator-set, so it honors R2/KD5. `checks_run` (names) stays frozen — additive,
no wire-contract break. *Rejected:* derive-from-existing-evidence-only — today's `checks_run`
(names) + coarse `phase_status` can't distinguish *ran* from *passed*, so the card would risk
asserting *done* from mere "checks ran" (violates AE4). **Anti-dead-wiring:** the field (U2), its
consumer (U3), and its producer SKILL instruction (U5) all land in this plan.

**KTD5 — The card replaces the status *summary*, not the evidence detail.** R14 "single emitter of
operator-facing status" means the gate/verdict **summary** routes through the card; the detailed
findings prose (code-review's per-finding table, qa's per-finding list) **remains** as the
drill-down *body* the card's cells reference. Findings detail is evidence, not status — deleting it
would destroy R12's drill-down target. This resolves the apparent R14-vs-keep-the-findings tension.

**KTD6 — Two archetypes, one renderer via a per-surface card-spec descriptor.** `render(card_spec)`
is surface-agnostic; per-surface projection builders construct the spec (archetype + ordered rows +
each row's derived state + drill-down ref). Mirrors the renderer/projection split that
`outcome_report.py` / `outcome_projection.py` already use.

**KTD7 — Execution method: delegate each feature unit to agy Gemini Pro 3.1 High** (`/agy:delegate
--model pro` → canonical `Gemini 3.1 Pro (High)`), Claude as sole committer/reviewer. This is the
n=3 external-agent-delegation run and the **first Pro run** (n=1/n=2 were Flash) — a model-strength
data point for `docs/external-agent-delegation/`. The documented contract is pinned in the
**Execution Method** section below.

## Implementation Units

Dependency-ordered. Each unit is independently landable, committed the moment it passes its gate
(orphan-agent hazard). Test files are repo-relative. "Delegate" = agy Pro per the Execution Method.

### U1. Shared glyph-card renderer + card-spec model

**Goal:** the single render site — state enum, glyph/label map, card-spec model, both archetypes,
indexed-footer drill-down, `--self-test`. No surface logic yet.

**Files:** `plugins/saga/scripts/status_card.py` (new).

**Build:**
- State enum (R1) + glyph map (KTD1) + operator-label map, decoupled from wire values via the
  display-label-map pattern (R9; mirror `saga.py:73-87`). Agent-facing markers stay distinct (R11).
- Card-spec dataclass: `archetype` (`gate-sequence` | `summary-projection`), `header`
  (surface, id, round), ordered `rows` (`key`, `label`, `state`, `ref | None`).
- `render(card_spec) -> str`: gate-sequence renders the declared row superset (unreached → its row
  as *not-reached*); summary-projection renders the fixed summary rows. Indexed-footer drill-down
  (KTD3): determinable cells get `[n]`, refs block below; not-reached/unknown carry none (R13).
  Constant-width, position-stable (R3).
- `--self-test` (CI-runnable, mirror `completeness_gate.py`).

**Depends on:** none.

**Test scenarios** (`tests/test_status_card.py`, new):
- Both archetypes render a well-formed card.
- Constant size: gate-sequence height identical at phase 1 vs phase 5; summary-projection height
  identical for 3 vs 30 dynamic items (AE1).
- Determinism + no writable status: same spec → byte-identical output; there is no spec input that
  sets a cell's *displayed* status independent of its `state` (AE2/R2).
- Failure + halt representable: a `failed`/`halted` row renders the `✗`/`‖` glyph and carries a
  footer ref (AE9).
- Unknown/not-reached carries no footer ref (AE7/R13).
- Renaming an operator label changes only the display-label map, not the wire state value (AE8/R9).
- `--self-test` runs clean: subprocess-invoke `status_card.py --self-test` with `check=True` and
  assert on expected stdout tokens (mirror `tests/test_completeness_gate.py::test_self_test_cli`).

### U2. `gate_verdicts` capture in the saga envelope

**Goal:** a durable, derived (never operator-set) per-gate verdict the `/work` Tests cell can
project. Producer = the `/work` test gate (wired in U5); consumer = U3's `/work` projection.

**Files:** `plugins/saga/scripts/saga.py`.

**Build:**
- Add `gate_verdicts` field to the `Saga` dataclass (full-snapshot list of `{gate, state, ref}`),
  wired into `FRONTMATTER_FIELDS`, `_LIST_FIELDS`, `render_envelope`, `parse_envelope`, and `_merge`
  (same full-snapshot replace / `ABSENT` carry-forward semantics as `checks_run`). `checks_run`
  stays frozen (additive change).
- Add the `save` CLI write path (e.g. `--gate-verdict gate:state:ref`, repeatable) so a producer
  can record verdicts; the value is supplied by the gate machinery, not hand-typed by the operator.
  **Parse the ref by splitting on the first two colons only** — refs are GitHub URLs (`https://…`)
  and `path:line` artifacts that contain colons, so a naive `split(':')` mangles them.

**Depends on:** none (independent schema change; logically feeds U3).

**Test scenarios** (`tests/test_saga_saga.py`):
- `gate_verdicts` round-trips through `save`/`restore` and renders in frontmatter.
- Full-snapshot semantics: an incoming list replaces the prior tick's; `ABSENT` carries forward;
  `[]` clears.
- A persisted verdict reads back as `{gate, state, ref}` with `state` ∈ the R1 state set.
- The `--gate-verdict` CLI parses a **colon-bearing ref** (a PR URL like
  `https://github.com/o/r/pull/9`) without mangling it — `{gate, state, ref}` round-trips with the
  ref intact (split on the first two colons, not a naive `split(':')`).

### U3. Per-surface projections — `/work`, `/code-review`, `/qa` (gate-sequence)

**Goal:** derived-on-read card-spec builders for the three gate-sequence surfaces, per the issue's
per-surface status-row contract.

**Files:** `plugins/saga/scripts/status_card.py` (add `project_work`, `project_code_review`,
`project_qa`).

**Build:**
- `project_work(saga)`: rows Implementation · Doc-review · Tests · Reviewer panel · Scanners · CI ·
  Merge (HITL) · Deploy (HITL). Tests cell derives from `gate_verdicts` (U2). Refs: saga tick
  (impl), `review_paths` → code-review artifact (reviewer panel/scanners), `qa_paths`/gate_verdicts
  (tests), `pr_refs`+`head_sha`+`destination` → GitHub (CI/merge/deploy).
- `project_code_review(artifact)`: rows Scope · Intent/built-vs-planned · Lenses · Review fan-out ·
  Merge · Validators · Verdict, parsed from the code-review artifact (`Scope Check: CLEAN|BLOCKED`,
  the `| Unit | Status | Evidence |` table, the verdict line).
- `project_qa(artifact)`: rows Risk class · Checks · Findings · Health score · Ship verdict, parsed
  from the qa artifact (`verdict:`/`health_score:` frontmatter + the per-class table).
- Each determinable cell attaches its drill-down ref (R12); shared concepts use the shared label +
  glyph (R8).

**Depends on:** U1, U2.

**Test scenarios** (`tests/test_status_card.py`):
- Each surface's rows derive correctly from fixture state.
- AE4: `/work` Tests cell reads *in-progress* while running, *done* only when `gate_verdicts` shows
  pass, *failed* on fail — never hand-advanced from `checks_run` names.
- AE5: the test-gate concept renders the same label + glyph on `/work` and `/qa`.
- AE6: `/work` Reviewer-panel cell carries a resolvable ref to the code-review artifact.
- AE7: a panel mid-run renders *in-progress* with a traceable pending count; an undeterminable cell
  renders *unknown* with no ref.
- AE9 (`/qa`): `project_qa` with a **FAIL** verdict in the qa artifact renders the Ship-verdict row
  with the failure glyph and a footer ref to the failing artifact — never *blocked*/*not-reached*
  (the most operator-safety-critical derivation; R1 "failure unmistakable").
- R12 external-read: a determinable `/work` CI/merge cell carries a resolvable **external** (GitHub
  PR/CI/HITL) reference, from a fixture with `pr_refs`/`head_sha`/`destination` set.

### U4. Summary-projection surfaces — `/outcome` (reuse) + `/resume` (spine)

**Goal:** render the two dynamic surfaces as fixed-size summary cards.

**Files:** `plugins/saga/scripts/status_card.py` (add `project_outcome`, `project_resume`).

**Build:**
- `project_outcome(...)`: adapt the **existing** `outcome_projection.project()` output (progress,
  ready frontier, blocked, attention, negative terminals) into a summary card-spec — no second
  projection (R6), no row-per-node. Negative-terminal nodes render the failure glyph (AE9);
  non-terminal summary rows (ready frontier, blocked) use the shared R1/R8 glyphs at the summary
  level — there is no per-node state collapse (a per-node state→glyph table would contradict
  R6/AE3, which pin the card values to equal `project()` exactly).
- `project_resume(...)`: define the spine summary-projection over what `/resume` Phase 3a actually
  reconstructs for a **single work thread** — **Phase/destination · Blockers (open vs cleared) ·
  Open questions · Last gate verdicts · Route (next-step)** — each row sourced from a real Phase-3a
  output (`resume/SKILL.md:171-184`): `phase`/`phase_status`+`destination`, reconciled `blockers`,
  `open_questions`, `checks_run`+`gate_verdicts` (U2), and `next_step`. **NOT "Open leaves / Ready
  frontier"** — those are outcome-DAG concepts with no producer in `/resume`'s single-thread
  reconstruction; the requirements' per-surface-contract "(confirm at /plan)" flag is resolved here
  (P1 fix — they'd have rendered perpetually-unknown, violating R12/R13).

**Depends on:** U1, U2.

**Test scenarios** (`tests/test_status_card.py`):
- AE3: `/outcome` card values equal `outcome_projection.project()` exactly; a 3-node and a 30-node
  DAG render the same height.
- `/resume` spine projects Phase/destination · Blockers · Open questions · Last gate verdicts ·
  Route from a reconstructed single-thread fixture; every rendered row maps to a real Phase-3a
  output (no perpetually-unknown row).
- AE9: an `/outcome` `failed`/`rejected`/`stalled`/`halted` node renders the failure/halt glyph,
  not *blocked*/*not-reached*.

### U5. Migration (R14) — route the prose status emissions through the card

**Goal:** make the renderer the only emitter of operator-facing *status*; wire the producer
(`/work` → `gate_verdicts`) and the summary surfaces.

**Files:** `plugins/saga/skills/work/SKILL.md` (§5.4), `plugins/saga/skills/code-review/SKILL.md`
(§5.2), `plugins/saga/skills/qa/SKILL.md` (§5), `plugins/saga/skills/outcome/SKILL.md`,
`plugins/saga/skills/resume/SKILL.md`.

**Build:**
- Convert each surface's status-summary emission to render the card (status header); detailed
  findings/evidence remain as the drill-down body (KTD5).
- Wire `/work` to write `gate_verdicts` when its test gate runs (U2 producer).
- Wire `/outcome` and `/resume` to render their summary cards (U4).

**Depends on:** U3, U4.

**Test scenarios** (`tests/test_saga_plugin.py`, doc-contract — mirror
`test_office_hours_two_mode_and_hard_gate_contract`):
- AE10: each converted section references the `status_card` renderer; the retired status-summary
  emitters are absent — assert the **specific** status tokens gone (the `/code-review` §5.2 verdict
  blockquote, the `/qa` §5.1 ship-verdict block) while the **per-finding evidence tokens REMAIN**
  (the code-review findings table, the qa per-finding list) per KTD5. A generic guard token would
  not prove single-emitter; name the literal tokens.

**Risk:** prose-heavy unit; this is exactly where agy's n=2 **F6 silent no-op** appeared. Archive
the agy draft before fixing, and budget a Claude hand-finish if the delegate no-ops.

### U6. Release surfaces (mechanical — Claude-written, not delegated)

**Goal:** keep installed-plugin metadata telling the same story as the diff (repo CLAUDE.md §6).

**Files:** `plugins/saga/.claude-plugin/plugin.json` (version bump),
`.claude-plugin/marketplace.json` (saga entry version), `plugins/saga/CHANGELOG.md` (entry),
`tests/test_saga_plugin.py` (update the literal version pin — it currently hard-asserts
`plugin_json["version"] == "0.40.0"`, which fails the moment U6 bumps the minor).

**Build:** bump saga version (minor — additive capability), add the CHANGELOG entry, sync the
marketplace registry. Mechanical and metadata-exact → Claude writes it (per the delegation
practice, mechanical units are not delegated).

**Depends on:** U5.

**Test scenarios:** update the literal version pin in `tests/test_saga_plugin.py` to the new minor
version **in this same unit**, then the metadata/version-pin drift tests pass (`uv run pytest
tests/test_saga_plugin.py`); full gate green.

## Dependency graph

```
U1 ─┬─> U3 ─┐
U2 ─┴─> U4 ─┴─> U5 ─> U6
   (U3,U4 both need U1+U2)
```

## Execution Method (agy Pro delegation contract — KTD7)

Per `docs/external-agent-delegation/` and memory `[[reference-agy-delegated-coder]]`. This is n=3
and the first Pro run.

- **Front door:** `/agy:delegate --model pro <task>` (canonical `Gemini 3.1 Pro (High)`). Never a
  hand-rolled `agy` shell call (operator-banned).
- **NAMED spawn is the only working invocation** (operator-confirmed). Spawn `agy:runner` with
  `name: agy-u<N>` so it is a persistent teammate that survives the main loop's ~2-min Bash cap.
  Its **first action fails** (`Teammates cannot spawn other teammates`) then **recovers** — that is
  expected; do not strip the name over it. The nameless variant dies; a long Bash `timeout` is
  **not** a substitute.
- **Never `--background`** — it detaches agy into a 0-output context (the n=2/U1 21-min hang).
  Foreground only.
- **Claude is the sole committer/pusher.** agy is told "Do NOT run any git command." Commit each
  unit the moment it passes its gate (the n=2 orphan-late-write hazard).
- **Tight in-prompt allow-set** per unit (the files listed above) + a hard scope guard ("if you
  need another file, STOP and report — never silently edit elsewhere"). Read broad, write narrow.
- **Post-hoc verification before integrating** any unit: `git status` ⊆ the unit's allow-set; the
  **full** gate (`uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run
  mypy plugins/`); read the diff for test-gaming **AND mutation-proof any tests agy wrote** (break
  the intended behavior, confirm the new test goes red — reading the diff alone does not catch F4
  test-gaming; the canonical floor pairs both, `blueprint.md:152-154`); confirm no rogue commit/push
  (`git log` + `git log origin/<branch>`).
- **Track-3 provenance fix (close the n=2 gap):** archive each agy draft (`git stash` or a copy)
  **before** fixing it, so the review-fix delta is measured, not reconstructed. Log per-unit churn
  to `docs/external-agent-delegation/README.md` (Review-fix cycle log). Compare Pro-vs-Flash.
- **U6 is mechanical → Claude writes it** (not delegated).

Saga orchestration backend = **inline** (Claude drives, delegates each unit to agy, verifies) —
matches n=1 (#275) and n=2 (#277).

## Scope Boundaries

**In scope (v1):** the shared renderer (both archetypes); per-surface derived-on-read projections
for all five surfaces; reuse of `outcome_projection.py` for `/outcome`; the `gate_verdicts` capture;
the shared-core + per-surface-subset vocabulary and display-label-map extension; indexed-footer
per-cell drill-down refs; retiring/routing the existing per-surface prose **status** emissions
(R14).

**Out of scope / deferred (true non-goals, carried from the issue):**
- The CLAUDE.md house-style cleanup and a standalone vocabulary lint (excluded by the
  single-render-site enforcement, KD2; revivable if vocabulary leaks beyond the card).
- A second emitter (the mission-control issue-progress comment from the same projection) — the
  card is designed to allow it later; v1 does not build it.
- Transcript-mining for additional surfaces.
- Any operator-writable status (KD5); redesigning the gates themselves (the card projects existing
  gates/states); the mission-control GitHub write (a separate operator-initiated consumer).

## Risk Analysis & Mitigation

| Risk | Likelihood | Mitigation |
|---|---|---|
| U5 prose migration triggers agy **F6 silent no-op** (the n=2 failure mode) | Med | Archive the draft; Claude hand-finish budget; U5 is the smallest-blast-radius prose change |
| Dead-wiring `gate_verdicts` (field with no producer/consumer) | Low | U2 (field+write path) + U3 (consumer) + U5 (producer SKILL) all in-plan; gate is failing the no-dead-wiring check at review |
| Constant-size (R3) violated by a surface adding dynamic rows | Low | Gate-sequence = static superset; summary-projection = fixed rows; explicit same-height tests (AE1) |
| Drill-down ref to external state (CI/HITL) when offline → false ref | Low | R13: undeterminable → *unknown*, no ref; tested (AE7) |
| agy agency leak (unrelated edits / rogue commit), per n=1 | Med | Documented containment: named spawn, no `--background`, sole-committer, `git status` ⊆ allow-set, immediate per-unit commit. **First Pro run — agency unobserved (n=1/n=2 were Flash); if Pro writes outside its allow-set on any unit, escalate that unit class to a throwaway git worktree / clone-jail (`blueprint.md` §3) per the DECISIONS `#agy-delegated-build-no-jail` revisit trigger — don't keep delegating it un-jailed.** |

## Alternatives Considered

- **Renderer as a skill-reference doc** (no Python) — rejected: agent-rendered output is not
  deterministically testable, so AE2 has nothing to call (KTD2).
- **Derive `/work` Tests from existing evidence only** — rejected: `checks_run` (names) + coarse
  `phase_status` can't distinguish ran/passed/failed (KTD4).
- **One unit per surface** — rejected: the three gate-sequence surfaces share the archetype and
  projection pattern (cohesive as U3); the two summary surfaces as U4 keeps blast radius aligned to
  the archetype boundary.

## Verification (CI parity)

```bash
uv run pytest tests/test_status_card.py -v          # renderer + per-surface projections
uv run pytest tests/test_saga_saga.py -v            # gate_verdicts round-trip
uv run pytest tests/test_saga_plugin.py -v          # doc-contract migration (AE10)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/
```

Expected: all green; the card renders for each of the five surfaces through one renderer,
deterministically, with failure representable and every determinable cell traceable.

## Routing

`/doc-review` next (the work-to-PR gate blocks on unresolved P0/P1), then `/work` (inline backend,
agy-Pro delegation per the Execution Method).
