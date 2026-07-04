---
title: "capability: journal_query.py — cross-repo learning consumption via query-time join at /plan and /investigate"
repo: infiquetra-claude-plugins
type: capability
tier: structural
objective: "Make the backlog and lifecycle self-improving"
wave: wave-3
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
executor_profile: {model: sonnet, effort: medium, backend: inline, external_llm: none}
---

# capability: journal_query.py — cross-repo learning consumption via query-time join at /plan and /investigate

### Intent
Replace the push-and-curate cross-repo learning architecture — which has never fired a single
promotion — with a cheap, mandatory, query-time join. Add `journal_query.py`, a tool that
greps/indexes every workspace repo's `LEARNINGS.md`/`DECISIONS.md`, wire it as a mandatory low-cost
step in `/plan` and `/investigate` ("has any repo already learned about X?"), and mark `/promote`
deprecated-pending-signal — its curation-ceremony architecture stays in the codebase but is no
longer the org's only cross-repo consumption path, and its future is gated on an observable
resurrection trigger (repeated query-hit clusters) rather than requiring a ceremony nobody performs.

## Problem / Motivation

- **The push-and-curate promotion loop exists and has never fired.** The grounding brief's
  consumer-side signal survey states directly: "Promote ledger: 0 learnings ever promoted; no
  genuine ≥3-repo transcendent cluster... The cross-repo learning loop exists but has never fired"
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:72-73`). `/promote`
  (`plugins/saga/skills/promote/SKILL.md:1-30`) is explicitly a "manual, gated, agent-judged
  workspace pass" that requires someone to run it, cluster candidates by judgment, and pass a
  propose-diff-and-wait gate before anything crosses into `infiquetra-context-library`. Zero
  promotions in the ledger after this much repo history means the push side of the architecture is
  dead weight, not under-disciplined — the fix is not "run `/promote` more often," it's inverting
  the direction of the join.
- **Stale claims are caught only by operator recall, not systematically, at exactly the moment a
  query-time join would catch them.** The grounding brief's session-mining synthesis names this as
  recurring pattern 7: "Stale memory/doc claims asserted as fact, caught only by operator recall or
  lucky re-verification (2 repos)" (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:135-136`),
  explicitly linked forward to "theme 10" — the same cross-repo learning theme this issue addresses.
  `/plan` and `/investigate` are precisely the two moments in the lifecycle where "has this already
  been learned somewhere in this workspace?" is the question an agent should be asking before
  proposing new design or diagnosing a bug from scratch — today neither skill consults any other
  repo's journal at all.
- **No binding decision protects the promote architecture from this change.** The grounding brief's
  binding-decision register (§2, `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:41-52`) lists
  the constraints that bound ideation in this wave — external-engine gating, cache-economics
  residency, `/outcome`'s derived-on-read status model, operator-choice framework, readonly-verifier
  fallback ladder, tier-vocabulary ordering, and the 17-to-7 plugin-portfolio groom. None of these
  registers `/promote`'s push-and-curate architecture as a protected invariant, so retiring its
  exclusivity as the only cross-repo consumption path is in bounds.
- **`/promote` already has the machinery this issue needs to reuse, not duplicate.**
  `plugins/saga/scripts/promote_scan.py` already enumerates every repo journal, parses
  `**Transcendent.**`/`**Generalizable rule.**` markers, and reads a drift-stable source-key ledger
  (`plugins/saga/scripts/promote_scan.py:20-21`, `:202-206`). `journal_query.py` is a different
  consumption shape over largely the same corpus — an on-demand search/index at `/plan` and
  `/investigate` time, not a judgment-clustering promotion pass — and should reuse `promote_scan.py`'s
  repo-enumeration logic rather than re-implementing a second journal walker.

## Definition of Done

Merged PR delivering:

1. `plugins/saga/scripts/journal_query.py` (exact path is `/plan`'s to determine; co-located with
   `promote_scan.py` is the natural default) that indexes every workspace repo's
   `docs/engineering-journal/LEARNINGS.md` and `docs/engineering-journal/DECISIONS.md`, exposing a
   query interface (keyword/topic search, minimum: substring or simple token match over entry
   headings and bodies) returning matching entries with their source repo, file, and anchor/line.
2. A mandatory, low-cost consult step wired into `plugins/saga/skills/plan/SKILL.md` and
   `plugins/saga/skills/investigate/SKILL.md`: before producing a plan or diagnosing a root cause,
   the skill runs `journal_query.py` against the current topic/symptom and surfaces any cross-repo
   hits to the operator/agent before proceeding. The step must be cheap enough to run on every
   invocation (no fan-out, no LLM clustering — a local index/grep pass only).
3. `plugins/saga/skills/promote/SKILL.md` updated to mark the push-and-curate pass
   deprecated-pending-signal: state plainly that `/promote` is no longer the primary cross-repo
   consumption path, and document the resurrection trigger — a query-hit cluster (the same topic
   surfacing repeated `journal_query.py` hits across ≥3 repos) is the observable condition under
   which `/promote`'s judgment-clustering pass becomes worth running again, replacing the prior
   "run it periodically" framing.
4. `tests/test_journal_query.py` exercising the query tool against fixture journals (multi-repo hit,
   single-repo hit, no hit) and asserting the `/plan`/`/investigate` consult step surfaces the
   returned hits.

Verify: run `journal_query.py` against a query with a known cross-repo prior-art fixture and observe
a hit report naming the source repo/file/line; run `/plan` or `/investigate` (or their test harness)
against a scenario matching a fixture and observe the consult step surface the same hit before the
skill proceeds; confirm `/promote`'s `SKILL.md` states its deprecated-pending-signal status and names
the query-hit-cluster resurrection trigger.

### Acceptance criteria
- [ ] **AC1 (H-F2-8, primary).** A plan-time query against a topic with prior art in another repo's
  journal returns that hit, naming the source repo, file, and anchor/line. Check: `uv run pytest
  tests/test_journal_query.py -k cross_repo_hit` → passes (asserts the query tool returns the
  fixture's known-match entry with correct repo/file attribution).
- [ ] **AC2 (H-F2-8, primary).** The query-hit-cluster condition (the same topic surfacing hits across
  ≥3 repos) is documented in `/promote`'s `SKILL.md` as the explicit resurrection trigger for the
  deprecated-pending-signal pass. Check: `grep -n "query-hit-cluster\|resurrection"
  plugins/saga/skills/promote/SKILL.md` → returns at least one match naming the trigger condition.
- [ ] **AC3.** `/plan`'s consult step runs the query tool and surfaces a matching cross-repo hit before
  the plan artifact is produced. Check: `uv run pytest tests/test_journal_query.py -k
  plan_consult_step` → passes.
- [ ] **AC4.** `/investigate`'s consult step runs the query tool and surfaces a matching cross-repo hit
  before root-cause diagnosis proceeds. Check: `uv run pytest tests/test_journal_query.py -k
  investigate_consult_step` → passes.
- [ ] **AC5.** A query against a topic with no cross-repo prior art returns no false-positive hits (the
  consult step does not block or clutter output when nothing relevant exists). Check: `uv run pytest
  tests/test_journal_query.py -k no_hit_clean` → passes.
- [ ] **AC6.** The consult step is cheap: it performs no LLM-judgment clustering and no fan-out (local
  index/grep only), matching the "mandatory cheap step" requirement. Check: `uv run pytest
  tests/test_journal_query.py -k consult_step_is_local_only` → passes (asserts the step invokes no
  `Task`/subagent dispatch, only the local query function).
- [ ] **AC7.** `/promote`'s `SKILL.md` states explicitly that it is deprecated-pending-signal and no
  longer the primary cross-repo consumption path, without deleting its existing
  judgment-clustering/propose-diff-and-wait machinery. Check: manual PR review confirms
  `plugins/saga/skills/promote/SKILL.md` carries the deprecated-pending-signal framing while
  `plugins/saga/scripts/promote_scan.py` remains intact and callable.
- [ ] **AC8.** Full suite, format, lint, and types stay green. Check: `uv run pytest && uv run ruff
  format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/
  --ignore-missing-imports` → all pass.

### Out-of-scope / non-goals
**In scope:** `journal_query.py`, its wiring into `/plan` and `/investigate` as a mandatory cheap
consult step, the `/promote` `SKILL.md` deprecated-pending-signal note and its resurrection-trigger
documentation, and the new test suite.

**Non-goals (deferred, explicitly out of scope for this issue):**
- Deleting `/promote`, `promote_scan.py`, or `references/promotion-contract.md` outright — this issue
  demotes the pass to an optional, signal-gated fallback; it does not remove the machinery. Full
  removal, if ever warranted, is a separate future issue gated on the resurrection trigger never
  firing.
- Any change to `/promote`'s propose-diff-and-wait gate, its drift-stable source-key ledger format,
  or its `**Transcendent.**`/`**Generalizable rule.**` marker parsing — those stay as documented in
  `references/promotion-contract.md`; this issue only changes when/whether the pass is invoked.
- Semantic or embedding-based search over journal content — the query tool is a local
  keyword/token-match index per the "cheap, mandatory step" requirement; no vector index, no RAG, no
  drift-prone embedding pipeline (mirrors `/promote`'s existing "judgment, not vectors" principle,
  `plugins/saga/skills/promote/SKILL.md`).
- Pulling `infiquetra-context-library`'s org-wide `LEARNINGS.md`/`llms.txt` into this query — this
  issue scopes to this workspace's per-repo journals only; library-pull integration into
  `/plan`/`/investigate`/`mission-control:issue` is separately named as absent in the grounding
  brief §4 and is other wave-3 work, not this issue.
- Any new standing/scheduled cluster-detection dashboard — the query-hit-cluster resurrection trigger
  is surfaced at query time (an agent/operator notices repeated hits across sessions), not tracked by
  a scheduled metrics job.

## Grounding References

| Absorbed idea | Basis | Role |
|---|---|---|
| `H-F2-8` | `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T10.json` (theme T10, frame F2, axis removal — "Retire promotion ceremony: cross-repo learning query-time join at /plan and /investigate." Basis: "Grounding brief section 3 item 5: 'Promote ledger: 0 learnings ever promoted; no genuine ≥3-repo transcendent cluster. cross-repo learning loop exists but never fired.' Plus section 7 pattern 7 (stale claims caught only by operator recall) — query-time join at plan time is exactly the moment a stale claim would be cross-checked. No binding decision in grounding brief section 2 register protects the promote architecture, so retirement is in bounds.") | primary |

**Binding decisions this issue builds on / must not contradict:**
- Grounding brief §2 binding-decision register (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:41-52`):
  none of the seven listed decisions (external-engine gating, chaperone dispatch, cache-economics
  residency, `/outcome`'s derived-on-read model, operator-choice framework, readonly-verifier
  fallback ladder, tier-vocabulary ordering) protects `/promote`'s architecture as a fixed invariant
  — confirmed by the absorbed idea's own basis statement, re-verified here against the current
  register.
- `/promote`'s existing core principles (`plugins/saga/skills/promote/SKILL.md`, "Core principles"
  section): "sparing, not a harvest," "gated, always," "judgment, not vectors" — this issue's
  deprecated-pending-signal framing preserves these principles for whenever the pass resurfaces; it
  does not relax the propose-diff-and-wait gate or introduce vector search as a substitute for
  `/promote`'s judgment-based clustering.

## Recommended Executor Profile

- **Model:** sonnet
- **Effort:** medium
- **Backend:** inline
- **External LLM:** none
- **Justification:** a bounded engineering task — a new local index/query tool over two
  well-known markdown file shapes already walked by `promote_scan.py`, plus two documented-SKILL.md
  edits wiring a cheap consult step and a status note. No adversarial judgment, no novel architecture,
  no cross-repo write surface (this issue is entirely read-only over journals plus two skill-doc
  edits). Sonnet/medium matches the fleet's own work-shape heuristic for a structural-tier issue of
  this bounded scope; no external-LLM chaperone dispatch is warranted per
  `{#external-engines-never-gatekeepers}` (#283) and `{#external-engine-chaperone-dispatch}` (#318) —
  there is no generator/second-opinion role this task needs.

## Release-Surface Checklist

This issue changes `/plan` and `/investigate` skill behavior (adds a mandatory consult step) and
`/promote` skill-facing guidance (deprecated-pending-signal status) — plugin behavior changes, so the
following must land in the same PR:
- [ ] `plugins/saga/.claude-plugin/plugin.json` version bump reflecting the new script and the two
      `SKILL.md` behavior changes (`/plan`, `/investigate`) plus the `/promote` status change.
- [ ] `.claude-plugin/marketplace.json` saga entry kept in sync with the bumped version/description.
- [ ] `plugins/saga/CHANGELOG.md` entry describing: the new `journal_query.py` tool, the mandatory
      consult step added to `/plan` and `/investigate`, and `/promote`'s deprecated-pending-signal
      status with its resurrection trigger.
- [ ] Any existing version/metadata drift-guard tests (this repo's marketplace/plugin-metadata parity
      tests) stay green against the bumped version.

## Files Expected to Change

- `plugins/saga/scripts/journal_query.py` — new cross-repo journal index/query tool.
- `plugins/saga/skills/plan/SKILL.md` — mandatory consult-step wiring.
- `plugins/saga/skills/investigate/SKILL.md` — mandatory consult-step wiring.
- `plugins/saga/skills/promote/SKILL.md` — deprecated-pending-signal status note + resurrection
  trigger documentation.
- `plugins/saga/.claude-plugin/plugin.json` — version bump.
- `.claude-plugin/marketplace.json` — saga entry sync.
- `plugins/saga/CHANGELOG.md` — new entry.
- `tests/test_journal_query.py` — new fixture-driven tests.

## Tests to Add or Update

- `tests/test_journal_query.py::test_cross_repo_hit` — a query with fixture prior art in another
  repo's journal returns the correct hit with repo/file/anchor attribution.
- `tests/test_journal_query.py::test_no_hit_clean` — a query with no prior art returns no
  false-positive hits.
- `tests/test_journal_query.py::test_plan_consult_step` — `/plan`'s consult step surfaces a matching
  hit before the plan artifact is produced.
- `tests/test_journal_query.py::test_investigate_consult_step` — `/investigate`'s consult step
  surfaces a matching hit before root-cause diagnosis proceeds.
- `tests/test_journal_query.py::test_consult_step_is_local_only` — the consult step performs no
  subagent/Task dispatch, only the local query function.

### Verification
```bash
# New journal-query suite
uv run pytest tests/test_journal_query.py -v

# Direct query against a known cross-repo prior-art fixture
python3 plugins/saga/scripts/journal_query.py --query "<fixture topic>"

# /promote SKILL.md carries the deprecated-pending-signal + resurrection-trigger language
grep -n "deprecated-pending-signal\|query-hit-cluster" plugins/saga/skills/promote/SKILL.md

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```
Expected: all green; the direct query against the known fixture returns a hit naming its source
repo/file/line; the grep against `/promote`'s `SKILL.md` returns at least one match for both phrases.

## Handoff Maturity

requirements-ready

## Suggested Next Action

Use `/plan <issue>` to create an implementation plan.

## Source Context

- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T10.json` (id `H-F2-8`)
- Source type: ideation survivor + issue-map consolidation + grounding-brief cross-check
- Source title: Cross-repo learning consumption query-time join at /plan and /investigate

### Context library links

_none_

### Files expected to change

- `plugins/saga/scripts/promote_scan.py`
- `plugins/saga/scripts/journal_query.py`
- `docs/engineering-journal/LEARNINGS.md`
- `docs/engineering-journal/DECISIONS.md`
- `plugins/saga/skills/plan/SKILL.md`
- `plugins/saga/skills/investigate/SKILL.md`
- `plugins/saga/skills/promote/SKILL.md`
- `tests/test_journal_query.py`

### Tests to add or update

- `tests/test_journal_query.py`

### Objective

"Make the backlog and lifecycle self-improving"

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/441
- Number: 441
- Created at: 2026-07-04T08:15:08.193588+00:00

