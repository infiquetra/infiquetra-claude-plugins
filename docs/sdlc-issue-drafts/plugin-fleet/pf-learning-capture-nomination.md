---
title: "enhancement: capture-time transcendence marking, nightly nominate-only accumulation, promote-ledger backlink guard"
repo: infiquetra-claude-plugins
type: enhancement
tier: structural
objective: "Make the backlog and lifecycle self-improving"
wave: wave-3
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
executor_profile: {model: sonnet, effort: medium, backend: inline, external_llm: none}
---

# enhancement: capture-time transcendence marking, nightly nominate-only accumulation, promote-ledger backlink guard

### Intent
Turn the cross-repo learning-promotion loop from a mechanism that exists but has never fired
into one that actually runs: mark transcendent learnings at journal-entry capture time instead
of waiting for a rare `/retro` Pass 5 sweep, accumulate nightly nominations into a standing,
watermarked candidate list that never writes to `infiquetra-context-library` on its own, and add
a CI backlink guard so promoted entries can't silently orphan their source key.

## Problem / Motivation

- **The promotion loop has fired zero times.** The grounding brief states it plainly: "ledger:
  0 learnings ever promoted; no genuine ≥3-repo transcendent cluster... the cross-repo learning
  loop exists but never fired" (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:72-73`,
  echoed in §8 theme 10: "promote loop never fired; 219 codex sessions dark; stale-claim
  pattern; evidence integrity",
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:172-173`).
- **Transcendence-marking is a rare, manual sweep, not a lifecycle byproduct.** The only place a
  `**Transcendent.**` marker gets written today is inside `/retro`'s Pass 5 curation sweep
  (`plugins/saga/skills/retro/references/retro-passes.md:114-145`), which is idempotent and
  single-repo scoped by design ("writes marker into **this** repo's journal only... marker waits
  in place [for the] next `promote` run" — `retro-passes.md:144-146`). Nothing prompts the
  marker at the moment a stack-agnostic `LEARNINGS.md` entry is actually captured
  (`journal_triggers.py` today only exposes `detect_targets()` for routing which journal file an
  entry belongs to — `plugins/saga/scripts/journal_triggers.py:13` — with no
  transcendence-detection or capture-time prompt at all).
- **`promote_scan.py` already computes the signal but only on manual, all-or-nothing invoke.**
  The scan already derives `_recurrence_clusters` (`plugins/saga/scripts/promote_scan.py:302`)
  and a stable `source_key`/backlink pair (`promote_scan.py:105`, `:132`), but the CLI has no
  nominate-only, no-write mode — its `scan` subcommand's only tunable is the distinct-repo
  threshold for what counts as a recurring cluster (`promote_scan.py:557`, "Distinct-repo count
  to nominate [a] recurrence cluster (default 2)"). Every invocation is a full, gated,
  agent-judged workspace pass (`plugins/saga/skills/promote/SKILL.md:48` frames it "a manual,
  gated, agent-judged workspace pass") — there is no lightweight, unattended, watermarked
  accumulation mode a nightly routine could run safely without risking an unreviewed
  context-library write.
- **The promoted-standard side has enforcement in the library but no backlink guard from this
  repo's side.** `infiquetra-context-library`'s own CI already runs `check_docs.py`
  (schema/frontmatter/link lint + promotion-ledger checks) and `context_census.py --check`
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:77-80`), but nothing in that pipeline
  resolves a promote-key backlink from a library entry back to *this* repo's originating
  journal source, so a rename or deletion on this side can silently orphan a promoted entry
  without either repo's CI going red.
- **This is a named seed, not a speculative ask.** `QUEUED.md` already anchors the
  under-served "Build the `plugins/engineering-journal/` plugin" seed
  (`docs/engineering-journal/QUEUED.md:317`, `{#engineering-journal-plugin}`), which the
  grounding brief lists among the direct pre-existing-seed matches carried into ideation
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:94`). This issue does not build that
  full plugin; it closes the specific "loop never fires" gap that seed and theme 10 both name.

## Definition of Done

Merged PR delivering, across this repo and (for the backlink guard) a companion PR to
`infiquetra-context-library`:

1. `plugins/saga/scripts/journal_triggers.py` gains a stack-agnostic-without-marker check: when
   a newly captured `LEARNINGS.md` entry's generalizable-rule line reads as stack-agnostic (no
   repo-specific stack/domain token) and carries no `**Transcendent.**` marker, the capture path
   surfaces a prompt asking whether to mark it — exact detection heuristic is `/plan`'s to
   determine, but it must not silently skip a stack-agnostic entry the way today's Pass-5-only
   path does.
2. `plugins/saga/skills/retro/references/retro-passes.md` and repo `CLAUDE.md` gain an explicit
   capture-time rule documenting that transcendence marking is no longer Pass-5-exclusive: an
   entry may be marked at capture time, and Pass 5 remains idempotent over already-marked
   entries (no double-marking, no regression to the existing single-repo-boundary contract in
   `retro-passes.md:144-146`).
3. `plugins/saga/scripts/promote_scan.py` gains a `--nominate-only` watermarked mode: it reads a
   persisted watermark (last-scanned position/timestamp per journal), scans only newly-added
   content since that watermark, appends any newly-qualifying recurrence clusters or marked
   entries to a standing `PROMOTION-CANDIDATES.md`, advances the watermark, and performs **zero**
   writes to `infiquetra-context-library` under any circumstance — nomination and promotion stay
   separate operations.
4. A scheduled routine (cron-equivalent; mechanism is `/plan`'s to determine — e.g. `schedule` or
   `cron`) invokes `promote_scan.py --nominate-only` nightly.
5. `infiquetra-context-library`'s `check_docs.py` gains a promote-key backlink resolver: for
   every promoted entry carrying a `source_key`/backlink (per the shape `promote_scan.py:105`
   and `:132` already produce), the resolver confirms the backlink resolves to a real, current
   entry in the originating repo's journal, and fails CI on an orphaned key.
6. Tests and verification below pass; `docs/engineering-journal/DECISIONS.md` gains a dated
   entry recording this decision per the repo's own auto-maintain journal convention.

### Acceptance criteria
- [ ] **AC1 (T10-F6-2, primary).** A fresh, stack-agnostic `LEARNINGS.md` entry captured without a
  `**Transcendent.**` marker surfaces the marker prompt at capture time (not only at the next
  `/retro` Pass 5 run). Check: `uv run pytest tests/test_journal_triggers.py -k
  stack_agnostic_prompts_marker` → passes (asserts the capture path returns/emits the
  marker-nomination prompt for a fixture entry with no repo-specific stack token and no existing
  marker).
- [ ] **AC2 (T10-F6-2, primary).** An entry that is already marked, or that names a genuinely
  repo-specific stack/domain detail, does NOT surface the prompt (no false-positive nag). Check:
  `uv run pytest tests/test_journal_triggers.py -k already_marked_or_repo_specific_skips_prompt`
  → passes.
- [ ] **AC3 (T10-F6-7, primary).** Two separate nightly `--nominate-only` runs, seeded with distinct
  new journal content between them, accrue distinct nominations into `PROMOTION-CANDIDATES.md`
  and make **zero** writes anywhere under a checked-out `infiquetra-context-library` fixture
  tree. Check: `uv run pytest tests/test_promote_scan.py -k
  nominate_only_two_runs_zero_context_library_writes` → passes (asserts the fixture
  context-library tree's mtimes/contents are byte-identical before and after both runs, and that
  `PROMOTION-CANDIDATES.md` gained two distinct entries).
- [ ] **AC4 (T10-F6-7).** A third `--nominate-only` run against unchanged journal content (no new
  content since the last watermark) adds no duplicate nomination for content already nominated.
  Check: `uv run pytest tests/test_promote_scan.py -k
  nominate_only_watermark_prevents_duplicate` → passes.
- [ ] **AC5 (T10-F4-6, primary).** An orphaned promote-key — a promoted `infiquetra-context-library`
  entry whose backlink points at a journal source entry that has been deleted or renamed without
  updating the backlink — reds `check_docs.py` in CI. Check (run from a checked-out
  `infiquetra-context-library` working copy with the fixture applied):
  `python3 check_docs.py --check` → exits non-zero on the fixture orphaned-key case.
- [ ] **AC6 (T10-F4-6).** Reconciling the backlink (updating it to point at the entry's current
  location, or removing the promoted entry) turns the same check green. Check:
  `python3 check_docs.py --check` → exits `0` once the fixture backlink is reconciled.
- [ ] **AC7 (S-3).** The capture-time marker rule and the `--nominate-only` accumulation flow are
  each documented in a `docs/engineering-journal/` entry (per this repo's own auto-maintain
  convention — a `DECISIONS.md` entry with rationale, rejected alternatives, and a
  "revisit when" condition) so the mechanism this issue ships is itself journaled, not just
  coded. Check: `grep -c '{#learning-capture-nomination' docs/engineering-journal/DECISIONS.md`
  → `>= 1`.
- [ ] **AC8.** Full repo gate stays green. Check: `uv run pytest && uv run ruff format --check . &&
  uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` → all
  pass.

### Out-of-scope / non-goals
**In scope:** capture-time transcendence-marking prompt in `journal_triggers.py`; a
`--nominate-only` watermarked mode in `promote_scan.py` plus a scheduled nightly routine
invoking it; a promote-key backlink resolver in `infiquetra-context-library`'s `check_docs.py`.

**Non-goals (deferred, explicitly out of scope for this issue):**

- Building the full `plugins/engineering-journal/` distribution plugin named in
  `docs/engineering-journal/QUEUED.md:317` (`{#engineering-journal-plugin}`) — that is
  multi-day, cross-repo distribution work (template files, `/journal-init`, `--upgrade`); this
  issue closes only the specific capture/nominate/backlink gap theme 10 names, not the whole
  seed.
- Any automatic, unattended write to `infiquetra-context-library` — nomination stays
  propose-only; the existing `/promote` skill's gated, agent-judged upsert step is unchanged and
  remains the only path that writes promoted entries.
- Near-duplicate/paraphrase clustering improvements to `promote_scan.py`'s recurrence-cluster
  logic (a separately tracked idea in the ideation pool) — this issue's nominate-only mode reuses
  the existing exact-recurrence and marker detection as-is.
- Cross-repo codex-session mining (the "219 codex sessions dark" gap named in the grounding
  brief) — a separate, already-distinct theme-10 facet, not absorbed into this issue's scope.
- Any change to `/retro`'s existing single-repo-boundary contract
  (`retro-passes.md:144-146`) — Pass 5 continues to write markers into only the current repo's
  own journal; this issue adds a second, capture-time place a marker can originate, it does not
  change the marker's semantics or scope.

## Grounding References

| Absorbed idea | Basis | Role |
|---|---|---|
| `T10-F6-2` | `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T10.json` (dod_sketch: "Merged PR: journal_triggers.py stack-agnostic-without-marker check + retro-passes.md + CLAUDE.md capture rule; verified by a fresh stack-agnostic LEARNINGS entry surfacing the Transcendent-marker prompt and the trigger flagging an unmarked one.") | primary |
| `T10-F6-7` | `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T10.json` (dod_sketch: "Merged PR: promote_scan.py --nominate-only watermarked mode + scheduled routine + standing PROMOTION-CANDIDATES.md; verified by two nightly runs accruing distinct nominations under a token budget with zero context-library writes.") | facet |
| `T10-F4-6` | `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T10.json` (dod_sketch: "Cross-repo PR: extend context-library check_docs.py with a promote-key backlink resolver + orphaned-key fixture; verified by CI going red on an orphaned promote-key and green once reconciled.") | facet |
| `S-3` | `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json` — thin seed (null body); basis: "QUEUED anchor {#engineering-journal-plugin} (brief §5); brief §3 'ledger: 0 learnings ever promoted; loop never fired'" — reconstructed via `docs/engineering-journal/QUEUED.md:317` and `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §3/§5 | facet |

**Binding decisions this issue builds on / must not contradict:**

- Cross-repo learning-loop architecture (`docs/plans/2026-06-20-global-transcendent-learnings-plan.md:71`):
  `promote_scan.py` does the mechanical work (enumerate journals, parse markers, compute the
  drift-stable source key); the promote SKILL does the judgment layer (cluster nomination,
  distillation, propose-diff-and-wait gate). This issue's nominate-only mode extends the
  mechanical half only — it must not fold judgment or auto-write behavior into the scan script.
- `/retro`'s existing single-repo-boundary and idempotency contract for transcendence marking
  (`plugins/saga/skills/retro/references/retro-passes.md:144-146`): marking is idempotent
  (never double-marks an already-`**Transcendent.**` entry) and single-repo scoped. Capture-time
  marking must honor the same idempotency and scope, not introduce a second, divergent marker
  semantics.
- Standards/ADR-enforcement org convention
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §4): schema-validate-in-CI +
  self-describing index, not runtime-injected blobs — the backlink guard extends
  `check_docs.py` as a CI-run static checker, matching the shape already established for the
  library's other schema/frontmatter/link lint.

## Recommended Executor Profile

- **Model:** sonnet
- **Effort:** medium
- **Backend:** inline
- **External LLM:** none
- **Justification:** three bounded, mostly-mechanical extensions to existing, well-understood
  scripts (`journal_triggers.py`'s detection surface, `promote_scan.py`'s CLI/watermark
  plumbing, `check_docs.py`'s existing lint pattern) plus a scheduled-routine wiring step — no
  novel architecture or adversarial judgment call is required beyond what the referenced binding
  decisions already settled. This matches the fleet's own quick-win/structural work-shape
  heuristic; no external-LLM chaperone dispatch is warranted.

## Release-Surface Checklist

This issue changes `saga` plugin-owned script behavior (new CLI mode on `promote_scan.py`, new
capture-time behavior in `journal_triggers.py`) and adds a scheduled routine — these are
user-facing lifecycle behavior changes, not repo-internal tooling only. Confirm at merge:

- [ ] `plugins/saga/.claude-plugin/plugin.json` version bumped to reflect the new
  `--nominate-only` CLI mode and capture-time marker-prompt behavior.
- [ ] `.claude-plugin/marketplace.json`'s `saga` entry kept in sync with the bumped version.
- [ ] `plugins/saga/CHANGELOG.md` gains an entry describing the `--nominate-only` mode, the
  capture-time transcendence-marking prompt, and the scheduled nightly routine.
- [ ] Any drift-guard / version-metadata test asserting plugin.json/marketplace.json/CHANGELOG
  parity re-run and green after the bump.
- [ ] If the promote-key backlink resolver lands in a companion `infiquetra-context-library` PR,
  that repo's own CI/version metadata (out of this repo's blast radius) is confirmed passing
  before this repo's PR is considered done.

## Tests to Add or Update

- `tests/test_journal_triggers.py::test_stack_agnostic_prompts_marker` — fresh stack-agnostic,
  unmarked entry surfaces the marker prompt.
- `tests/test_journal_triggers.py::test_already_marked_or_repo_specific_skips_prompt` — no
  false-positive nag on already-marked or genuinely repo-specific entries.
- `tests/test_promote_scan.py::test_nominate_only_two_runs_zero_context_library_writes` — two
  nightly-style runs accrue distinct nominations with zero writes to the context-library
  fixture tree.
- `tests/test_promote_scan.py::test_nominate_only_watermark_prevents_duplicate` — a third run
  over unchanged content adds no duplicate nomination.
- (companion `infiquetra-context-library` PR) `test_check_docs.py::test_orphaned_promote_key_reds_ci`
  and `test_check_docs.py::test_reconciled_promote_key_passes` — orphaned backlink reds CI,
  reconciled backlink passes.

### Verification
```bash
# New/updated capture-time and nominate-only suites
uv run pytest tests/test_journal_triggers.py tests/test_promote_scan.py -v

# Nominate-only mode makes zero writes to a fixture context-library checkout
python3 plugins/saga/scripts/promote_scan.py --nominate-only --workspace-root <fixture-root>

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all green; the two nominate-only runs produce two distinct `PROMOTION-CANDIDATES.md`
entries with an unmodified context-library fixture tree; the companion `check_docs.py` change
(verified separately in the `infiquetra-context-library` repo) goes red on a fixture orphaned
promote-key and green once reconciled.

## Handoff Maturity

requirements-ready

## Suggested Next Action

Use `/plan <issue>` to create an implementation plan.

## Source Context

- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T10.json` (ids `T10-F6-2`,
  `T10-F6-7`, `T10-F4-6`) and `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json`
  (id `S-3`)
- Source type: ideation survivors (three direct, one thin seed with null body) + issue-map
  consolidation + grounding-brief reconstruction
- Source title: Capture-time transcendence marking, nightly nominate-only accumulation,
  promote-ledger backlink guard

### Context library links

_none_

### Files expected to change

- `plugins/saga/scripts/journal_triggers.py`
- `plugins/saga/skills/retro/references/retro-passes.md`
- `plugins/saga/scripts/promote_scan.py`
- `docs/engineering-journal/DECISIONS.md`
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T10.json`
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json`
- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
- `plugins/saga/.claude-plugin/plugin.json`

### Tests to add or update

- `tests/test_journal_triggers.py`
- `tests/test_promote_scan.py`

### Objective

"Make the backlog and lifecycle self-improving"

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/442
- Number: 442
- Created at: 2026-07-04T08:15:25.613436+00:00

