---
title: Fix the execution-backend recommendation + offer flow in /plan Phase 5.2
type: fix
status: active
date: 2026-07-12
origin: docs/engineering-journal/QUEUED.md
---

# Fix the execution-backend recommendation + offer flow in /plan Phase 5.2

## Summary

Fix the four `/plan` Phase 5.2 backend-offer defects that misfired live while planning #526
(crude `file_count >= 8` size signal, breadth-only ultracode vocabulary, caller-asserted
`workflow_available`, silently-omitted third backend), plus the adjacent gap that a verify panel
cannot carry its own tier. Issue: infiquetra/infiquetra-claude-plugins#565; canonical defect
record: `docs/engineering-journal/QUEUED.md` `{#plan-backend-recommendation-broken}`.

## Problem Frame

All four defects distort every `/plan` backend offer, and the operator directed the fix
(2026-07-11: "both need fixed"). The signal chain is: `recommend_execution_backend`
(`plugins/saga/scripts/lifecycle_state.py:100`) reuses `should_offer_team_execution`
(`lifecycle_state.py:45`, raw-count trigger at `:77`), gates ultracode on three triggers only
(`:184-186`), trusts `workflow_available` verbatim (`:113`), and drops an unavailable backend
from the offer entirely (`:201-204`, `omit_ultracode` at `:210`). Four prose sites mirror the
omit-and-underscope behavior: `plugins/saga/skills/plan/SKILL.md:286`,
`plugins/saga/references/operator-choice.md:153` (§4, "prefer to omit"),
`plugins/saga/skills/loop/SKILL.md:268`, and
`plugins/saga/skills/work/references/execution-strategy.md:166,181-182` (documents the
`omit_ultracode` JSON shape). The adjacent gap: `Verify` (`plugins/saga/scripts/
execution_spec.py:531`) has no tier field, and the single verifier-opts emit site
(`execution_spec.py` ~1495-1517) rides the unit tier unconditionally (R4), so an opus/high
refute-3 request on a sonnet/medium unit forces the whole unit up.

## Requirements

- **R1.** Release-surface bookkeeping (plugin.json, marketplace.json, CHANGELOGs, drift pins)
  must not count toward the team-execution size trigger; the #526 shape (3 functional + 6
  bookkeeping files) must recommend `inline`, while 8+ genuinely functional files still trips.
- **R2.** The ultracode trigger vocabulary must reach the workflow shapes the Workflow tool doc
  names — understand / design / research / review / migrate — not only breadth and
  adversarial-confidence; an unknown shape fails loud, never silently ignored.
- **R3.** Availability must be declared with provenance: the recommender records whether
  `workflow_available` was probed (ToolSearch) or asserted, and surfaces it in the output; the
  skill prose mandates a live probe at offer time.
- **R4.** The offer must always enumerate all three backends (`inline` / `team-execution` /
  `cc-workflows-ultracode`) with per-backend status and an availability note — never a silent
  drop. The `omit_ultracode` key and every prose site instructing omission are removed/rewritten
  in lockstep.
- **R5.** A `verify` panel may carry its own `{model, effort}` tier; absent, it defaults to the
  unit tier and the spec emits byte-identically to today (R4 default preserved).
- **R6.** A premium panel tier (above `sonnet/high`) is subject to the same worth-it receipts
  rule as a premium unit tier under `validate --require-receipts`, and `spend` prices verifier
  calls at the effective panel tier.
- **R7.** Release surfaces ship in the same PR: saga `plugin.json` minor bump,
  `marketplace.json`, `CHANGELOG.md`, and the version drift pin in `tests/test_saga_plugin.py`.

## Key Technical Decisions

**KTD1 — Functional surface via a subtractive `release_surface_file_count` kwarg:** add
`release_surface_file_count: int = 0` to `should_offer_team_execution` and
`recommend_execution_backend` (CLI `--release-surface-file-count`); the size trigger compares
`file_count - release_surface_file_count >= 8`. Keeps `file_count`'s meaning stable (raw touched
files), defaults to byte-identical behavior for every existing caller, and matches the repo's
"release surfaces" vocabulary. Rejected: redefining `file_count` as functional-only (silently
changes every caller's semantics); a ratio heuristic (unexplainable magic threshold).

**KTD2 — One validated `workflow_shapes` vocabulary parameter, not five booleans:** add
`workflow_shapes: Sequence[str] = ()` validated against a frozen
`WORKFLOW_SHAPES = ("understand", "design", "research", "review", "migrate")` (the shapes the
Workflow tool doc itself names); any entry trips the ultracode branch beside
`broad_independent_fanout` / `adversarial_confidence`; an unknown shape raises `ValueError`
(fail loud). CLI: repeatable `--workflow-shape`. The rationale string names the shape(s) so the
offer explains itself. Shapes ride under the same elevated-risk suppressor as the existing
triggers; read-only shapes on keyword-risky-but-untouched code are already handled by
`has_code_surface=False` (the existing neutralizer). The `review` shape covers a multi-lens
review *sweep* requested as a workflow; the explicit refute-N / judge-panel form remains
`adversarial_confidence` — the two may co-fire and share the branch, no precedence between
them. Rejected: one boolean per shape (kwarg clutter, unversioned vocabulary); free-text shape
(unvalidatable, silent typo = silent inline).

**KTD3 — Availability provenance recorded, probe mandated in prose:** the recommender is pure
Python and cannot call ToolSearch, so the honest contract is: new kwarg
`workflow_availability_source: "probed" | "asserted"` (default `"asserted"`, CLI
`--workflow-availability-source`), echoed in the output as
`workflow_availability: {available, source}`; the offer renders an asserted absence as
"unverified — probe before trusting". The `/plan` prose (U2) mandates the ToolSearch probe and
passing `probed`. Rejected: probing from inside the recommender (no such API from Python);
requiring `probed` always (breaks non-Claude hosts where assertion is the only source).

**KTD4 — Full-enumeration `backends` key; `omit_ultracode` removed:** the output gains
`backends`: an ordered list of exactly three `{backend, status, note}` entries with
`status ∈ {recommended, alternative, unavailable}` and the availability note carrying the KTD3
source. `alternatives` (reachable, non-recommended) is retained for the one-keystroke escalation
list. `omit_ultracode` is deleted — its only consumers (`plan/SKILL.md:286`,
`execution-strategy.md:181`, `operator-choice.md:153`, `loop/SKILL.md:268`) implement exactly
the offer-hiding behavior this issue removes, and all are rewritten in the same PR (lockstep,
no deprecation shim — dead wiring invites the old behavior back). Rejected: keeping
`omit_ultracode` deprecated (a live key that says "omit" will get consumed again).

*Compat contract the KTD depends on:* `outcome_dispatcher.py:411` is a direct Python consumer —
it calls `recommend_execution_backend(**leaf_signals)` and post-processes the result
(`:421-425`: frontier-budget downgrade rewrites `recommended` and mutates `alternatives`). The
new kwargs must therefore stay default-valued (additive) and `recommended` / `rationale` /
`alternatives` keep their keys and semantics. The downgrade path must ALSO re-stamp the new
`backends` statuses (ultracode → `alternative`, team-execution → `recommended`, with the
`budget_note` reason) — otherwise the authoritative enumeration would contradict the downgraded
recommendation. That dispatcher edit + its regression test are U1 scope.

**KTD5 — `Verify` gains an optional panel tier plus its own receipts, mirroring unit machinery:**
`Verify.tier: Tier | None = None` (None → unit tier, R4 default), plus `worth_it_because: str`
and `cheaper_fallback: Tier | None` mirroring the unit fields so a premium panel justifies its
own spend rather than borrowing the unit's receipt. Panel tier is palette-validated like a unit
tier (haiku/xhigh HALTs); `to_dict` omits absent keys (byte-identical round-trip);
`_verifier_opts` emits the effective tier `verify.tier or unit.tier`; `unit_spend`
(`execution_spec.py:1037`) prices the `n × iterations` verifier calls at the effective panel
tier. Receipts enforced only under `--require-receipts` (authoring boundary), so existing specs
never break retroactively. Rejected: reusing the unit's receipt fields for panel escalation
(conflates two independent spend decisions); forcing the unit up to the panel tier (the live
failure this fixes).

## Implementation Units

### U1. Recommender rework in `lifecycle_state.py`

**Goal:** land R1-R4's code half — functional-surface signal, widened shapes, availability
provenance, full-enumeration offer payload — with the existing recommender tests updated in
lockstep.

**Files:** `plugins/saga/scripts/lifecycle_state.py`; `tests/test_saga_plugin.py` (the
recommender block starting at `tests/test_saga_plugin.py:2600` asserts the exact behaviors that
change: the `file_count=8` boundary, `omit_ultracode`, alternatives-dropping — update these,
never leave them asserting the defect); `plugins/saga/scripts/outcome_dispatcher.py`
(`:411-425` — the frontier-budget downgrade re-stamps `backends` statuses per KTD4's compat
contract); `tests/test_outcome_dispatcher.py` (downgrade-consistency regression).

**Test scenarios** (`tests/test_saga_plugin.py`):
- #526-shape regression: `file_count=9, release_surface_file_count=6` → `inline`; without the
  subtraction (`release_surface_file_count=0`) the same call still → `team-execution`
  (boundary preserved at 8 functional).
- `workflow_shapes=["research"]` → `cc-workflows-ultracode`; `workflow_shapes=["bogus"]` →
  `ValueError`; CLI `--workflow-shape understand --workflow-shape migrate` round-trips.
- Elevated-risk suppressor still wins: `workflow_shapes=["migrate"], has_infra=True` →
  `team-execution`.
- `backends` always has exactly 3 entries; with `workflow_available=False` the ultracode entry
  is `status="unavailable"` with the source in its note (asserted vs probed) — and
  `"omit_ultracode" not in result`.
- `workflow_availability` echoes `{available, source}` for both sources; default is
  `asserted`.
- CLI JSON surface end-to-end for the new flags.
- Dispatcher downgrade consistency (`tests/test_outcome_dispatcher.py`): a wide-frontier
  ultracode recommendation downgraded to team-execution re-stamps `backends` so the
  team-execution entry reads `recommended` and ultracode reads `alternative` — the enumeration
  never contradicts the downgraded `recommended` key.

**Depends on:** nothing.

### U2. Prose lockstep — the offer contract across four skill/reference sites

**Goal:** land R2-R4's prose half: every site that instructs omission or documents the old JSON
shape teaches the new contract — always name all three backends, mark unavailable ones with
provenance, probe availability via ToolSearch at offer time, and the widened shape vocabulary.

**Files:** `plugins/saga/skills/plan/SKILL.md` (Phase 5.2 — rewrite the omit sentence at `:286`,
widen the "serve BOTH purposes" framing at `:269-277` to the five shapes);
`plugins/saga/references/operator-choice.md` (§3.2 vocabulary, §4 omit rule at `:153` →
always-name-and-mark, §5 offer form if it echoes the omission);
`plugins/saga/skills/loop/SKILL.md:268`;
`plugins/saga/skills/work/references/execution-strategy.md:166,181-182` (new JSON shape:
`backends` + `workflow_availability`, no `omit_ultracode`; `--workflow-availability-source`);
`plugins/saga/skills/work/SKILL.md:50,229-232` and
`plugins/saga/skills/loop/references/drive-and-resume.md:52-56` (both render the offer from
"surface the alternatives" — reword to render from the full `backends` enumeration so every
offer site names all three).

**Test expectation:** none — prose-only unit; U1's CLI tests pin the JSON shape the prose
describes, and the drift-guard style test for skill/registry sync does not cover these files.
AC4's `grep -n "ToolSearch" plugins/saga/skills/plan/SKILL.md` check must pass (the probe
mandate is greppable).

**Depends on:** U1 (the prose documents U1's output shape).

### U3. `Verify` panel tier in `execution_spec.py`

**Goal:** land R5-R6 — optional per-panel tier with its own receipts, effective-tier emission at
the single verifier-opts site, panel-tier-aware spend.

**Files:** `plugins/saga/scripts/execution_spec.py` (`Verify` dataclass `:531` — new fields +
`validate(where, require_receipts=...)` + `from_dict`/`to_dict`; `_verifier_opts` ~`:1495-1517`
— effective tier; `unit_spend` `:1037` — panel-tier pricing; `Unit.validate` threads
`require_receipts` into `verify.validate`); `tests/test_saga_execution_spec.py`.

**Test scenarios** (`tests/test_saga_execution_spec.py`):
- Spec with `verify: {n: 3, pass_rule: majority, tier: {model: opus, effort: high}}` on a
  sonnet/medium unit: emitted `.workflow.js` verifier opts carry `model: 'opus'`,
  `effort: 'high'` while the unit's own agent call stays sonnet/medium.
- Same spec without the `tier` key: emitted output byte-identical to today's emission (R4
  default preserved) and `to_dict` round-trip omits the new keys.
- Premium panel tier without `worth_it_because`/`cheaper_fallback`: plain `validate` passes,
  `validate --require-receipts` fails naming the unit and the panel.
- Panel `cheaper_fallback` that is not strictly cheaper → `SpecError` (mirrors unit rule).
- Panel tier `haiku/xhigh` → `SpecError` (palette ceiling HALT, not clamp).
- `unit_spend`: a 3-verifier opus/high panel on a sonnet/medium unit yields
  `base(sonnet/medium) + 3 × base(opus/high)`.

**Depends on:** nothing (parallel with U1).

### U4. Release surfaces + issue hygiene

**Goal:** R7 — saga version minor bump (behavior + schema change), marketplace entry, CHANGELOG
entry describing the new offer contract and panel tier, drift pin update. Also correct issue
#565's acceptance-criteria test paths (`tests/test_lifecycle_state.py` /
`tests/test_execution_spec.py` do not exist; the real homes are `tests/test_saga_plugin.py` and
`tests/test_saga_execution_spec.py`).

**Files:** `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
`plugins/saga/CHANGELOG.md`, `tests/test_saga_plugin.py` (version pin), issue #565 body edit.

**Test expectation:** none — release bookkeeping; the existing version drift-guard tests are the
check.

**Depends on:** U1, U2, U3.

## Scope Boundaries

**Out of scope (true non-goals):**
- The separate QUEUED brainstorm/ideate convergence-bias entry that follows this one in
  `docs/engineering-journal/QUEUED.md` — different item, no code overlap.
- `outcome_dispatcher.py resolve_available` — the `/outcome` full-menu enumeration already
  models availability separately (operator-choice §8); not part of the `/plan` offer chain.
  (The dispatcher's *leaf-backend passthrough* at `:411-425` IS in scope — U1 re-stamps
  `backends` on its frontier-budget downgrade per KTD4's compat contract.)
- Backend execution mechanics (team-execution internals, workflow emitter thunk shapes) beyond
  the `Verify` tier field; tier_policy/tier_resolver registry contents.
- The run-fact ledger `prior` key (#401) — untouched.

**Deferred to Follow-Up Work:**
- Auto-deriving `release_surface_file_count` from a path classifier (globbing
  `**/plugin.json`, `CHANGELOG.md`, `marketplace.json`) — worth doing only if hand-counting
  misfires in practice.
- A `deploy_handoff.py authorize` CLI verb and the other #395-envelope residuals (already
  recorded there).

## Verification (plan-level)

```bash
uv run pytest tests/test_saga_plugin.py tests/test_saga_execution_spec.py -q
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```
