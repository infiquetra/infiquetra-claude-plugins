---
title: "enhancement: fix promote_scan recall — diagnose mode, lexical clustering, subject scoping, capture-time slugs"
repo: infiquetra-claude-plugins
type: enhancement
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
objective: Make the backlog and lifecycle self-improving
wave: wave-3
---

# enhancement: fix promote_scan recall — diagnose mode, lexical clustering, subject scoping, capture-time slugs

## Objective

Fix the cross-repo learning-promotion loop's recall problem from four angles that all attack the
same fact: it has never fired. `promote_scan.py` gains a `diagnose` mode that reports real fleet
counts instead of leaving the zero-promotions state unmeasured, a `cluster-candidates` mode that
breaks the exact-wording recurrence floor with lexical (keyword-Jaccard) clustering, a
subject-scope classifier that stops fleet-shared learnings from being held to the same
recurrence bar as repo-local ones, and a controlled-vocabulary slug convention that moves
clustering cost from scan-time text matching to capture-time authoring — plus a backfill pass
proving the new slug convention against this repo's own journal.

## Problem / motivation

The promote ledger has zero entries. That is not a claim of "the mechanism is imperfect" — it is
a directly grounded, dated fact with a specific, currently-unmeasured cause on each of four
independent axes.

- **Zero promotions is a grounded, cited fact, not a guess.**
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:72-73`: "Promote ledger: 0 learnings
  ever promoted; no genuine ≥3-repo transcendent cluster. The cross-repo learning loop exists but
  has never fired." This is listed as the top consumer-side signal across 19 scanned repos and
  explicitly "strengthens theme 10" (cross-repo learning-mining & provenance discipline;
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:172`).
- **The friction causing the zero is invisible today — nothing measures it.** `promote_scan.py`
  (`plugins/saga/scripts/promote_scan.py:1-32`) implements the read backbone (enumerate
  journals, parse markers, compute source keys, group exact-recurrence clusters) and emits
  `scan` output as "data only; the orchestrator does the judgment," but there is no mode that
  reports the raw fleet counts (how many `**Transcendent.**`-marked candidates exist, how many
  near-miss clusters fall just short of the recurrence floor) before or independent of a live
  scan's clustering decision. An operator cannot currently tell *why* zero promotions happened —
  too few candidates, too little lexical overlap, or a bar too high — without instrumenting the
  script by hand.
- **The exact-wording recurrence floor is the deterministic gate, and it is measurably too
  strict.** `_recurrence_clusters()` (`plugins/saga/scripts/promote_scan.py:302-329`) groups
  "exact-recurrence clusters: same normalized rule in >= threshold distinct repos" via
  `normalize_rule()` / `rule_hash()` (`plugins/saga/scripts/promote_scan.py:82-111`) — identical
  wording, after normalization, produces an identical hash; anything short of that wording match
  is invisible to the deterministic floor entirely. Independently-worded learnings about the same
  underlying pattern (e.g. the four Claude Code runtime-quirk learnings below) never cluster
  because no two authors phrase a rule identically, even when the substance recurs.
  `DEFAULT_THRESHOLD = 2` (`plugins/saga/scripts/promote_scan.py:58`) is the deterministic floor
  under `SKILL.md`'s judgment clustering (`plugins/saga/skills/promote/SKILL.md:65`,
  `:82-84`), but exact-hash matching means even a threshold of 2 rarely fires across
  independently-authored repos.
- **A concrete, currently-ineligible cluster already exists to validate the fix against.**
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:69-71`: "Claude Code runtime quirks
  recorded as durable build constraints (bg-dispatch loses channel notifications; agents/*.md not
  auto-loaded; protocol byte-identity) — 1 repo, 4 distinct quirks." These four learnings live in
  a single repo today and would fail both the exact-wording floor (independently worded) and any
  naive "recurs across repos" bar (they are single-repo) — they are the concrete case the
  subject-scope classifier and lexical clustering must together make eligible.
- **The `>=3`-repo transcendence bar conflates two different kinds of subject matter.** The
  promotion contract's "select few" framing and the deterministic threshold apply one recurrence
  bar to every learning regardless of whether its subject is fleet-shared infrastructure (e.g. a
  Claude Code runtime quirk that by construction affects every repo using the same runtime, even
  if only observed once) or genuinely repo-local business logic that only becomes "transcendent"
  after independently recurring three or more times. Today there is no classifier distinguishing
  the two, so fleet-shared learnings are held to a repo-local recurrence bar they cannot pass by
  design — one observation of a fleet-shared runtime constraint is evidence for every repo on
  that runtime, not evidence for one-third of a cluster.
- **Clustering cost is paid entirely at scan time today, with no capture-time convention to cheapen
  it.** Journal entries carry free-text rule content (`docs/engineering-journal/LEARNINGS.md`
  entries, parsed via the `**Transcendent.**` / `**Generalizable rule.**` markers,
  `plugins/saga/scripts/promote_scan.py:60-71`) but no structured, controlled-vocabulary slug at
  capture time that a scan could group on directly instead of re-deriving similarity from prose
  every run. Moving even a coarse slug taxonomy into the frontmatter/entry convention at capture
  time turns an expensive, lossy prose-similarity problem at scan time into a cheap, exact
  slug-match at scan time — the same economic move the brainstorm exemplar in this repo's own
  history makes for other detection problems (mechanical check now, cheap re-check later, rather
  than re-deriving judgment every run).

## Definition of Done

Four coordinated changes to `plugins/saga/scripts/promote_scan.py` and the `promote` skill, each
independently mergeable but bundled as one issue because they all target the same recall problem
from complementary angles:

1. **`diagnose` subcommand.** `promote_scan.py diagnose [--workspace-root PATH] [--json]` reports
   real fleet counts — total `**Transcendent.**`-marked candidates, total legacy
   `**Generalizable rule.**` candidates, count of exact-recurrence clusters at the current
   threshold, and count of "near-miss" clusters (lexically similar but below the exact-hash
   floor) — without performing any write. This makes the friction measurable before any other
   fix lands.
2. **`cluster-candidates` mode.** A new scan mode that buckets candidates by lexical
   (keyword-Jaccard) similarity rather than exact-hash equality — no embeddings, no external
   model call — surfacing candidate clusters the exact-recurrence floor misses. This is additive:
   the existing exact-recurrence clusters remain the deterministic floor; lexical clustering is a
   second, looser candidate pool the judgment layer (`SKILL.md`) can act on.
3. **Subject-scope classifier + dual eligibility.** A classifier (fleet-shared vs. repo-local)
   that changes the eligibility rule per subject class: fleet-shared subjects (e.g. runtime/build
   constraints that by nature apply fleet-wide) become eligible under a lower, single- or
   dual-repo bar; repo-local subjects keep the existing `>=3`-repo (or configured threshold) bar.
   Both rules coexist — this is not a global threshold lowering.
4. **Controlled-vocabulary slug convention + backfill.** A documented slug convention added to the
   journal-entry frontmatter convention (the shared engineering-journal practice this repo already
   follows), a new `promote_scan.py` slug-clustering mode that groups on exact slug match instead
   of re-deriving prose similarity, and a backfill pass applying slugs to this repo's own
   `docs/engineering-journal/LEARNINGS.md` entries as the first real-data validation of the
   convention.

### Acceptance criteria
- [ ] **`diagnose` reports real fleet counts.** Running `promote_scan.py diagnose` over the actual
      `~/workspace/infiquetra` fleet prints non-fabricated counts of markers, legacy
      generalizable-rule lines, exact-recurrence clusters, and near-miss clusters — not zeros
      papered over as "nothing found," and not estimates. Check:
      `uv run pytest tests/test_promote_scan.py -k diagnose` → passes, plus a committed baseline
      report from a real run against the workspace root.
- [ ] **Lexical clustering yields a non-empty candidate bucket where the exact floor yields
      zero.** A fixture with independently-worded but topically-recurring learnings across
      `>=2` repos produces at least one non-empty `cluster-candidates` bucket via keyword-Jaccard
      similarity, while the existing exact-recurrence clustering on the same fixture returns zero
      clusters. Check: `uv run pytest tests/test_promote_scan.py -k cluster_candidates_lexical`
      → passes.
- [ ] **The four Claude Code runtime-quirk learnings become eligible.** Given the four
      single-repo runtime-quirk learnings referenced in
      `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:69-71` (bg-dispatch loses channel
      notifications; `agents/*.md` not auto-loaded; protocol byte-identity; and the fourth quirk
      recorded alongside them) as fixture input, the subject-scope classifier marks them
      fleet-shared and the dual eligibility rule marks them promotion-eligible under the
      lower fleet-shared bar — they do not remain permanently ineligible under the repo-local
      `>=3`-repo bar. Check: `uv run pytest tests/test_promote_scan.py -k subject_scope_runtime_quirks`
      → passes.
- [ ] **Repo-local subjects keep the existing recurrence bar.** A fixture with a genuinely
      repo-local, single-repo learning (no fleet-shared markers) is classified repo-local and
      remains ineligible until it independently recurs at the existing threshold — the
      dual-eligibility change must not silently lower the bar for repo-local subjects. Check:
      `uv run pytest tests/test_promote_scan.py -k subject_scope_repo_local_unchanged` → passes.
- [ ] **Slug-grep produces a machine-checkable `>=3`-repo cluster.** After the backfill pass
      applies the controlled-vocabulary slug convention to this repo's
      `docs/engineering-journal/LEARNINGS.md`, a slug-clustering scan (or a plain `grep` over the
      new frontmatter slug field across the fleet) produces at least one cluster meeting the
      configured repo threshold, entirely by exact slug match — no prose-similarity computation
      required at scan time for slugged entries. Check:
      `uv run pytest tests/test_promote_scan.py -k slug_clustering` → passes, plus a manual
      `grep -h '^slug:' */docs/engineering-journal/LEARNINGS.md | sort | uniq -c | sort -rn` run
      showing the cluster.
- [ ] **Backfill pass is applied and committed.** This repo's own `docs/engineering-journal/LEARNINGS.md`
      entries carry the new slug frontmatter field after the backfill script/pass runs, with no
      change to the entries' existing prose content (slug is additive metadata, not a rewrite).
      Check: `git diff docs/engineering-journal/LEARNINGS.md` shows only frontmatter/slug
      additions, no prose deletions.
- [ ] **`promote` skill documents all four new modes.** `plugins/saga/skills/promote/SKILL.md`
      is updated to describe `diagnose`, `cluster-candidates`, the subject-scope classifier and
      dual eligibility rule, and the slug convention, so an operator running `/promote` sees the
      new recall paths without reading the script source.
- [ ] **Full suite, format, lint, types, and security stay green.** Check:
      `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports && uv run bandit -r plugins/`
      → all pass.

### Out-of-scope / non-goals
In scope: four additive changes to `promote_scan.py` and the `promote` skill (diagnose mode,
lexical clustering mode, subject-scope classifier with dual eligibility, slug convention +
slug-clustering mode + backfill), all read-oriented except the backfill's frontmatter addition to
this repo's own journal.

Out of scope (do not do in this issue):

- **No embeddings or external-model calls for clustering.** The lexical clustering mode is
  keyword-Jaccard over normalized text, matching the existing script's dependency-free posture
  (`plugins/saga/scripts/promote_scan.py` has no LLM/embedding dependency today) — this issue
  does not add one.
- **No change to the gated-write path.** `write_promotion()`, `compute_upsert()`, and the
  `context_library_journal()` / `assert_write_target()` write-target guard
  (`plugins/saga/scripts/promote_scan.py:437-526`) are not modified — this issue only changes
  what becomes *visible as a candidate*, never how or where an actual promotion is written.
- **No lowering of the deterministic threshold for repo-local subjects.** `DEFAULT_THRESHOLD`
  (`plugins/saga/scripts/promote_scan.py:58`) stays as the repo-local bar; the dual-eligibility
  rule adds a separate, lower fleet-shared bar rather than changing the existing constant
  globally.
- **No backfill beyond this repo's own journal.** The backfill pass validates the slug convention
  against `docs/engineering-journal/LEARNINGS.md` in this repo only; retrofitting slugs across
  the other 18+ repos in the fleet is a separate follow-on, not this issue.
- **No change to the shared engineering-journal practice document's ownership.** If the slug
  convention requires updating the shared practice doc referenced from this repo's `CLAUDE.md`
  (`https://github.com/infiquetra/infiquetra-sdlc/.../engineering-journal.md`), this issue
  proposes the frontmatter addition and applies it locally; it does not unilaterally rewrite the
  cross-org shared document — that update, if needed, is coordinated separately.

## Grounding References

- **Absorbed idea `T10-F4-1`** (primary) — "promote_scan diagnose: make the zero-promotion
  friction visible before fixing it." `dod_sketch`: "Merged PR: promote_scan.py diagnose
  subcommand + test + committed baseline report; verified by running diagnose over
  `~/workspace/infiquetra` and reading actual fleet counts (markers, generalizable-rule lines,
  clusters, near-misses)." Basis: theme T10, frame F4 (promotion-activation axis), tier quick-win.
- **Absorbed idea `T10-F6-1`** (facet) — "Break the exact-wording recurrence floor with lexical
  candidate clustering." `dod_sketch`: "Merged PR: promote_scan.py cluster-candidates mode
  (lexical keyword-Jaccard buckets, no embeddings) + promote SKILL Phase 1-2 rewrite; verified by
  a live-workspace scan producing >=1 non-empty >=2-repo candidate bucket where the exact floor
  returns zero." Basis: theme T10, frame F6, promotion-activation axis, tier structural.
- **Absorbed idea `H-F3-9`** (facet) — "Subject-scoped promotion: the >=3-repo transcendence bar
  is why zero learnings have ever promoted." `dod_sketch`: "Merged PR: promote_scan/promote gains
  a subject-scope classifier (fleet-shared vs repo-local) + dual eligibility rules; verified by
  the 4 runtime-quirk single-repo learnings becoming eligible and promoted as validation." Basis:
  theme T10, frame F3, default-inversion axis, tier quick-win.
- **Absorbed idea `H-F4-7`** (facet) — "Fix the never-fired promote loop by moving clustering
  cost to capture time (learning slugs)." `dod_sketch`: "Merged PR: controlled-vocab slug
  convention in journal frontmatter + promote_scan slug-clustering mode + a backfill pass over
  this repo's LEARNINGS.md; verified by a slug-grep producing a machine-checkable >=3-repo
  cluster." Basis: theme T10, frame F4, capture-time-economics axis, tier structural.
- **Consolidation rationale (from the issue map):** "Four mechanisms attacking the same
  zero-promotions fact from the recall side: measure the friction, break the exact-wording floor,
  fix the one-operator >=3-repo bar, and move clustering cost to capture time." All four are
  bundled into one issue because they are complementary fixes to one measured failure, not
  four independent features.
- **Grounding fact anchoring the whole issue:**
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:72-73` ("Promote ledger: 0 learnings
  ever promoted; no genuine ≥3-repo transcendent cluster... Strengthens theme 10") and `:172`
  (theme 10: "Cross-repo learning-mining & provenance discipline (promote loop never fired; 219
  codex sessions in-window with no mining substrate)").
- **Grounding fact anchoring the runtime-quirk validation case:**
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:69-71`: "Claude Code runtime quirks
  recorded as durable build constraints (bg-dispatch loses channel notifications; agents/*.md
  not auto-loaded; protocol byte-identity) — 1 repo, 4 distinct quirks."
- **Existing primitives this issue extends without replacing:**
  `plugins/saga/scripts/promote_scan.py` — `normalize_rule()` / `rule_hash()` /
  `source_key()` (`:82-111`), `Candidate` (`:118-133`), `DEFAULT_THRESHOLD = 2` (`:58`),
  `_recurrence_clusters()` (`:302-329`), `Origin` / `Promotion` (`:344-366`),
  `write_promotion()` / `compute_upsert()` / `context_library_journal()` /
  `assert_write_target()` (`:437-526`); `plugins/saga/skills/promote/SKILL.md` (`:50`, `:65`,
  `:82-84`) for the judgment-layer threshold and clustering guidance this issue extends.
- **Binding decision this issue must respect:** the promotion contract's split between
  mechanical read backbone (this script) and judgment (the `SKILL.md` layer) — new clustering
  and classification modes emit candidate data only; the gated apply/skip/modify decision via
  `AskUserQuestion` (`plugins/saga/skills/promote/SKILL.md:50`) remains the judgment layer's job,
  not something the new modes decide automatically.

## Recommended executor profile

- **Model:** sonnet
- **Effort:** high
- **Backend:** inline
- **External LLM:** none
- **Justification:** four coordinated but individually well-specified extensions to a single,
  already-understood script (`promote_scan.py`) and its companion skill doc — no architectural
  ambiguity, but enough combined surface area (four modes, a new classifier, a new frontmatter
  convention, and a real backfill against this repo's own journal) to warrant high effort at
  sonnet rather than medium; no external-engine or embedding dependency is introduced, so no
  above-sonnet escalation is justified.

## Release-surface checklist

This issue adds new subcommands and a new frontmatter convention to the existing `saga` plugin
(no removal or breaking change to existing `promote_scan.py scan`/`key` behavior). Update in the
same PR:

- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump (new `diagnose`,
      `cluster-candidates`, and slug-clustering subcommands; new subject-scope classifier
      behavior).
- [ ] `.claude-plugin/marketplace.json` — reflect the version bump.
- [ ] `plugins/saga/CHANGELOG.md` — entry describing the four new recall mechanisms.
- [ ] Any existing plugin-metadata/version drift-guard tests (e.g. a marketplace/plugin.json
      parity test) re-run green after the bump.
- [ ] `docs/engineering-journal/DECISIONS.md` — entry recording the slug-convention choice
      (controlled vocabulary at capture time vs. re-deriving similarity at scan time) with
      rejected alternatives (embeddings-based clustering, global threshold lowering) and a
      "revisit when" condition.
- [ ] `docs/engineering-journal/LEARNINGS.md` — dated entry noting the zero-promotions root
      cause once diagnose confirms it against real fleet data, plus the backfill's slug additions
      (frontmatter-only, per the acceptance criteria above).

### Files expected to change
Indicative only — exact set is `/plan`'s to determine.

- `plugins/saga/scripts/promote_scan.py` — new `diagnose` subcommand, `cluster-candidates` mode
  (keyword-Jaccard), subject-scope classifier + dual eligibility rules, slug-clustering mode.
- `plugins/saga/skills/promote/SKILL.md` — document all four new modes and how the judgment
  layer consumes their candidate output.
- `plugins/saga/skills/promote/references/promotion-contract.md` — if the frozen contract needs a
  slug-field addendum (frontmatter convention), update alongside the code.
- `plugins/saga/.claude-plugin/plugin.json` — version bump.
- `.claude-plugin/marketplace.json` — version sync.
- `plugins/saga/CHANGELOG.md` — entry for the four new recall mechanisms.
- `tests/test_promote_scan.py` — new: `diagnose`, `cluster_candidates_lexical`,
  `subject_scope_runtime_quirks`, `subject_scope_repo_local_unchanged`, `slug_clustering` cases.
- `docs/engineering-journal/LEARNINGS.md` — backfill slug frontmatter additions + the
  zero-promotions root-cause entry.
- `docs/engineering-journal/DECISIONS.md` — slug-convention decision entry.

### Tests to add or update
- `diagnose` reports non-fabricated fleet counts (markers, legacy-rule lines, exact clusters,
  near-misses) from a fixture and, separately, a committed real-run baseline.
- `cluster-candidates` lexical mode produces a non-empty `>=2`-repo bucket on a fixture where the
  exact-recurrence floor returns zero.
- Subject-scope classifier correctly marks the four runtime-quirk learnings fleet-shared and
  eligible under the lower bar.
- Subject-scope classifier leaves a genuinely repo-local learning ineligible under the unchanged
  existing threshold (no silent global lowering).
- Slug-clustering mode groups entries by exact slug match and produces a `>=3`-repo cluster after
  backfill.
- Backfill diff touches only frontmatter/slug fields in `docs/engineering-journal/LEARNINGS.md`,
  no prose changes.
- Release-surface drift-guard test (plugin.json/marketplace.json version parity) re-run green.

### Verification
```bash
# New promote_scan recall-mode unit tests
uv run pytest tests/test_promote_scan.py -v

# Diagnose against the real fleet (manual read of counts, not just exit code)
python3 plugins/saga/scripts/promote_scan.py diagnose --workspace-root ~/workspace/infiquetra --json

# Slug-cluster validation via plain grep (machine-checkable, no script dependency)
grep -h '^slug:' */docs/engineering-journal/LEARNINGS.md | sort | uniq -c | sort -rn

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . \
  && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports && uv run bandit -r plugins/
```

Expected: all green; `diagnose` prints non-zero real counts for at least the marker/candidate
totals; the slug-grep shows at least one slug value with count `>=3` after the backfill.

## Handoff maturity

requirements-ready

## Suggested next action

Use `/plan <issue>` to create an implementation plan.

## Source context

- Source: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T10.json (`T10-F4-1`, `T10-F6-1`, `H-F3-9`, `H-F4-7`)
- Source type: issue-map
- Source title: Fix promote_scan recall: diagnose mode, lexical clustering, subject scoping, capture-time slugs

### Intent

The promote ledger has zero entries. That is not a claim of "the mechanism is imperfect" — it is a directly grounded, dated fact with a specific, currently-unmeasured cause on each of four independent axes.

### Context library links

_none_

### Objective

Make the backlog and lifecycle self-improving

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/446
- Number: 446
- Created at: 2026-07-04T08:16:31.801038+00:00

