---
title: "capability: mined-session ledger, pattern lineage, and closed-loop retirement of resolved findings"
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

# capability: mined-session ledger, pattern lineage, and closed-loop retirement of resolved findings

### Objective

Make the backlog and lifecycle self-improving

### Problem / motivation

Session-mining runs today (`/retro`'s transcript-review pass) with no memory of what was
already mined, no durable record of where a distilled pattern came from, and no channel
by which a merged fix ever silences the finding that prompted it. Three related gaps in
one bookkeeping layer:

- **Mining has no idempotency ledger, so it can only re-mine blind.** `/retro`'s Pass 3
  (`plugins/saga/skills/retro/references/retro-passes.md:81-88`) discovers sessions with
  `discover_sessions.py --repo <repo> --days <N> --exclude <current-session-id>` and
  extracts skeletons per session, but there is no record anywhere of which session IDs a
  prior mining pass already consumed. Every invocation re-discovers the same windowed set
  from scratch; there is no way to ask "what changed since last time" or "how many
  sessions remain unmined." The plugin already has a working idempotency-ledger idiom for
  exactly this shape of problem — `/promote`'s scanner reads a `<!-- promote-keys: ... -->`
  ledger comment and drops already-promoted candidates before computing new ones
  (`plugins/saga/scripts/promote_scan.py:19-21`, `:74` `PROMOTE_KEYS_RE`, `:203`
  "Build already-promoted key set from context-library's journal (§5)"). Mining has no
  equivalent; it is the one mining/promotion stage in the pipeline without a delta-skip
  primitive.
- **A mined-session synthesis run already proved the "runs once, evaporates" failure mode
  at this repo's own tier.** The grounding pass's session-mining synthesis distilled
  70/70 skeletons from 27 sessions into 175 findings and 10 recurring patterns
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:113`), and separately recorded
  **219 codex sessions in-window with no mining substrate at all**
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:115`) — a grounded, countable
  dark zone that no report currently surfaces as an ongoing metric. Without a ledger,
  nothing distinguishes "we mined everything available" from "219 sessions are silently
  invisible to mining," and every subsequent pass restates the same unmined backlog
  instead of shrinking it.
- **Distilled patterns have no durable lineage back to source.** `provenance_manifest.py`
  already defines the plugin's typed provenance contract for delegated-output evidence —
  `ClaimProvenance` records source-attributed claims with a two-layer producer-claimed vs
  Claude-adjudicated tag (`plugins/saga/scripts/provenance_manifest.py:1-18`, `:300`
  `class ClaimProvenance`) — but nothing in that manifest, or anywhere else, records which
  session IDs and skeleton hashes a *mined pattern* traces back to. Once a pattern is
  synthesized into a `LEARNINGS.md`-shaped entry or a recurring-pattern bullet, its
  connection to the raw session evidence is gone; re-verifying "did this pattern really
  come from these sessions" requires re-reading raw transcripts by hand.
- **A merged fix never tells mining to stop re-surfacing the pattern it fixed.** The
  grounding brief's promotion-ledger finding — "0 learnings ever promoted; no genuine
  ≥3-repo transcendent cluster... cross-repo learning loop exists but never fired"
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:76`) — is one face of a broader
  problem: even where a pattern *does* get acted on (a PR merges that fixes the
  originating defect), nothing back-annotates the finding as resolved. The next mining
  pass over the same or an overlapping window re-surfaces the identical pattern as if
  nothing happened, because there is no resolution signal feeding back into the mining
  substrate — this is the "closed loop" theme 10 names but never wires
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:99-116`).

## Definition of Done

One merged PR delivering three tightly coupled bookkeeping primitives that share a single
mining-ledger data shape (no new plugin, no new command surface beyond what wires into
existing `/retro` and provenance machinery):

1. **Mined-session ledger with delta-skip.** A ledger, following the `promote-keys`
   idiom (`plugins/saga/scripts/promote_scan.py:74`, `:203`), records which session IDs a
   mining pass already consumed (proposed: `<!-- mined-keys: ... -->` comment in the
   mining-report artifact, or an equivalent ledger file read by `discover_sessions.py` /
   a new `mining_ledger.py`). A second mining pass over an unchanged session corpus mines
   zero new sessions and reports the standing unmined count (e.g. "0 new, 219 still
   unmined") instead of blindly re-discovering the same set.
2. **Durable pattern-lineage records.** A mined-pattern lineage record — source session
   IDs plus skeleton hashes — is added to the provenance manifest surface
   (`plugins/saga/scripts/provenance_manifest.py`), so a distilled pattern can be
   round-tripped back to its exact source skeleton set from the durable record alone,
   with no raw-transcript re-read required.
3. **Resolution back-annotation and mining de-rank.** When a merged PR/issue closes with
   evidence that it fixed the defect an existing mined finding named, that finding is
   back-annotated as resolved (with PR evidence), and a de-rank filter causes the next
   mining pass to skip or flag the resolved pattern rather than re-surfacing it verbatim.

Merged PR must demonstrate all three DOD facets against fixture data (no live GitHub
writes required for the demonstration) — see Acceptance criteria below.

### Acceptance criteria
- [ ] **Second pass over an unchanged corpus mines zero new sessions.** Given a fixture
  session corpus and a ledger already recording those session IDs as mined, running the
  mining pass again yields 0 newly-mined sessions and reports the standing unmined count
  (sessions present in the discovery window but absent from both "mined" and "excluded"
  sets). Check: `uv run pytest tests/test_mining_ledger.py -k second_pass_zero_new` →
  passes.
- [ ] **Unmined count is reported and matches the discovery-window gap.** Given a fixture
  discovery window of N sessions where the ledger has recorded M as mined (M < N), the
  mining-pass report states an unmined count of exactly N − M. Check:
  `uv run pytest tests/test_mining_ledger.py -k unmined_count_matches_gap` → passes.
- [ ] **A distilled pattern round-trips to its source skeleton set.** Given a fixture
  lineage record (source session IDs + skeleton hashes) attached to one distilled
  pattern, a lookup by pattern ID returns exactly that session/skeleton set with no
  access to raw transcript files. Check: `uv run pytest tests/test_provenance_manifest.py
  -k pattern_lineage_roundtrip` → passes.
- [ ] **Lineage record round-trips through `from_dict`/`to_dict` without unknown-key
  drift.** The new lineage record type follows `provenance_manifest.py`'s existing
  "unknown keys REJECTED" discipline (`plugins/saga/scripts/provenance_manifest.py:1-18`)
  — a lineage payload with an unexpected key raises `ManifestError` rather than being
  silently dropped. Check: `uv run pytest tests/test_provenance_manifest.py -k
  lineage_rejects_unknown_keys` → passes.
- [ ] **A resolved-pattern finding is skipped or flagged on the next mining pass.** Given
  a fixture finding that has been back-annotated as resolved (merged-PR evidence
  attached), running a mining pass over a session window that would otherwise re-surface
  that exact pattern either omits it or emits it tagged `resolved` rather than as a fresh
  finding. Check: `uv run pytest tests/test_resolution_backannotation.py -k
  resolved_pattern_skipped_or_flagged` → passes.
- [ ] **Back-annotation requires PR evidence, never asserts resolution from prose alone.**
  Attempting to back-annotate a finding as resolved without a linked merged-PR/commit
  reference is rejected (mirrors the manifest's evidence-attribution discipline). Check:
  `uv run pytest tests/test_resolution_backannotation.py -k
  backannotation_requires_pr_evidence` → passes.
- [ ] **Full suite, format, lint, types, security stay green.** Check: `uv run pytest &&
  uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/
  tests/ --ignore-missing-imports && uv run bandit -r plugins/` → all pass.

### Out-of-scope / non-goals
In scope: one mined-session ledger with delta-skip and unmined-count reporting; one
pattern-lineage record type added to the provenance-manifest surface; one resolution
back-annotation + mining de-rank filter. All three consume/emit fixture data structures
already implied by existing `/retro` and `/promote` machinery — no new external service,
no new plugin.

Out of scope (do not do in this issue):

- **Building or scheduling the session-mining workflow itself.** This issue adds
  bookkeeping (ledger, lineage, resolution) around the existing `/retro` Pass 3
  discovery/extraction flow (`plugins/saga/skills/retro/references/retro-passes.md:84-88`)
  — it does not change how sessions are discovered, skeletons extracted, or fan-out
  synthesized.
- **Closing the 219-codex-sessions mining-substrate gap.** The grounding brief's grounded
  gap — "219 codex sessions in-window with no mining substrate"
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:115`) — is a substrate-coverage
  problem (codex sessions aren't skeleton-extractable today), not a ledger problem. This
  issue makes the unmined count *visible and countable*; it does not build codex-session
  skeleton extraction.
- **Automating resolution detection.** This issue provides the back-annotation primitive
  and the PR-evidence-required contract; it does not build a scanner that automatically
  infers "this merged PR fixed pattern X" from diff content — that judgment call (or a
  future automation of it) is out of scope here. The back-annotation call site is
  expected to be invoked with an explicit PR reference, mirroring how `/promote`'s ledger
  write is explicit and gated, not inferred.
- **Auto-opening GitHub issues or writing to the board.** No facet of this issue mutates
  GitHub state; ledger, lineage, and resolution records are local/repo-committed
  artifacts consumed by `/retro` and `/promote`-adjacent tooling.
- **Rewriting `/promote`'s promotion-contract or ledger format.** The mined-session ledger
  reuses the *idiom* (drift-stable key, ledger comment, delta-skip) established by
  `promote_scan.py`, not its literal ledger — `/promote`'s `<!-- promote-keys: ... -->`
  contract (`plugins/saga/skills/promote/references/promotion-contract.md`) is untouched.

## Grounding References

- **Absorbed idea `T10-F2-8`** (primary) — "Mined-session ledger — remove blind
  re-mining and make the dark zone countable" (theme T10, frame F2, axis
  mining-substrates). `dod_sketch`: "Merged PR: mined-session ledger (promote-keys
  idiom) + delta-skip + unmined-count report in retro mining; verified by a second pass
  over unchanged corpus mining 0 sessions while reporting standing unmined count."
- **Absorbed idea `T10-F3-8`** (facet) — "Closed-loop retirement — a merged fix must
  silence its originating pattern" (theme T10, frame F3, axis feedback-pipeline).
  `dod_sketch`: "Merged PR: resolution back-annotation (merged issue -> mark originating
  finding resolved with PR evidence) + mining de-rank filter; verified by a
  resolved-pattern issue causing its finding to be skipped/flagged on the next mining
  pass."
- **Absorbed idea `T10-F6-6`** (facet) — "Durable lineage records so every mined pattern
  is re-verifiable to source" (theme T10, frame F6, axis provenance-discipline).
  `dod_sketch`: "Merged PR: provenance_manifest.py mined-pattern lineage record (source
  session IDs + skeleton hashes); verified by round-tripping one distilled pattern back
  to its exact source skeleton set from the durable manifest alone."
- **Consolidation rationale (issue-map):** "Idempotency ledger, durable lineage, and
  resolution back-annotation are three faces of one mining bookkeeping layer: what was
  mined, where a pattern came from, and when a fix silences it." The three facets share
  one mining-report data shape and one gating discipline, so they ship as one PR rather
  than splitting into three near-duplicate issues.
- **Session-mining synthesis grounding** —
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:113,115`: workflow
  `wf_7e5d77a2-5c0`, 70/70 skeletons distilled, 27 sessions, 175 findings; 219 codex
  sessions in-window with no mining substrate (grounded dark-zone gap).
- **Promote-loop-never-fired grounding** —
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:76`: "Promote ledger: 0 learnings
  ever promoted; no genuine ≥3-repo transcendent cluster... cross-repo learning loop
  exists but never fired."
- **Theme 10 grounding** — `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:99-116`:
  recurring-pain synthesis names "Stale memory/doc claims asserted as fact, caught only
  by operator recall or lucky re-verification" and provenance/status re-verification as
  live, unaddressed themes feeding theme 10.
- **Existing idempotency-ledger idiom (basis for the mined-session ledger)** —
  `plugins/saga/scripts/promote_scan.py:19-21` (drop already-promoted candidates via
  `<!-- promote-keys: ... -->` ledger comment), `:74` (`PROMOTE_KEYS_RE`), `:203` (build
  already-promoted key set from context-library's journal).
- **Existing provenance-manifest contract (basis for the lineage record)** —
  `plugins/saga/scripts/provenance_manifest.py:1-18` (schema `saga.manifest.v1`; unknown
  keys rejected, versioned schema prefers loud drift over silent key-dropping), `:300`
  (`class ClaimProvenance` — source-attributed claims, producer-claimed vs
  Claude-adjudicated).
- **Existing mining discovery/extraction seam (call site for the ledger)** —
  `plugins/saga/skills/retro/references/retro-passes.md:81-88` (`/retro` Pass 3:
  `discover_sessions.py --repo <repo-folder> --days <N> --exclude
  <current-session-id>`, `extract_session_skeleton.py --output
  "$SCRATCH/<id>.skeleton.txt" <session-file>`).
- **Plugin-portfolio consolidation-burden decision** —
  `{#plugin-portfolio-groom-17-to-7}`: new-capability additions to an existing plugin's
  scripts/commands surface carry a consolidation-burden proof; this issue adds bookkeeping
  to existing `saga` scripts (`provenance_manifest.py`, mining-adjacent scripts) rather
  than introducing a new plugin.

### Recommended executor profile

- **Model:** sonnet
- **Effort:** medium
- **Backend:** inline
- **External LLM:** none
- **Justification:** All three facets are mechanical bookkeeping extensions over
  already-specified idioms — the ledger reuses `/promote`'s proven `promote-keys` pattern
  verbatim in shape, the lineage record extends an existing typed manifest class family
  with a documented rejection discipline, and the back-annotation filter is a
  gated-write-with-evidence pattern the plugin already uses elsewhere. No architectural
  judgment call or novel design space is required; sonnet at medium effort is sufficient,
  and no external-engine involvement is warranted since the work is a straight
  extend-existing-contract task against fixtures, not open-ended synthesis or an
  adversarial review.

## Release-Surface Checklist

This issue adds new bookkeeping surface (ledger + lineage record type + back-annotation
filter) to the `saga` plugin's mining/provenance scripts without changing any existing
command's external behavior. Update in the same PR:

- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump reflecting the new
  mined-session ledger, lineage-record type, and resolution back-annotation surface.
- [ ] `.claude-plugin/marketplace.json` — reflect the version bump.
- [ ] `plugins/saga/CHANGELOG.md` — entry describing the mined-session ledger
  (delta-skip + unmined-count reporting), the pattern-lineage record added to
  `provenance_manifest.py`, and the resolution back-annotation + mining de-rank filter.
- [ ] Any existing plugin-metadata/version drift-guard tests (e.g. marketplace/plugin.json
  parity test) re-run green after the bump.
- [ ] `docs/engineering-journal/DECISIONS.md` — entry recording that mining bookkeeping
  reuses the `promote-keys` idiom rather than inventing a second ledger format, and that
  resolution back-annotation requires explicit PR evidence (never inferred), matching the
  repo's existing propose-diff-and-wait pattern used by `/promote`.

### Files expected to change

Indicative only — exact set is `/plan`'s to determine.

- `plugins/saga/scripts/mining_ledger.py` (proposed, new) — mined-session ledger:
  delta-skip against a `promote-keys`-style ledger comment/file, unmined-count reporting.
- `plugins/saga/scripts/provenance_manifest.py` — new mined-pattern lineage record class
  (source session IDs + skeleton hashes), following the existing `ClaimProvenance`
  (`:300`) rejection-of-unknown-keys pattern.
- `plugins/saga/scripts/resolution_backannotation.py` (proposed, new) — resolved-finding
  back-annotation (requires PR evidence) and mining de-rank filter consumed by the mining
  pass.
- `plugins/saga/skills/retro/references/retro-passes.md` — Pass 3 documentation updated
  to reference the ledger's delta-skip and unmined-count report.
- `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
  `plugins/saga/CHANGELOG.md` — release-surface bump (see checklist above).
- `tests/test_mining_ledger.py` — second-pass-zero-new, unmined-count-matches-gap.
- `tests/test_provenance_manifest.py` — pattern-lineage-roundtrip,
  lineage-rejects-unknown-keys.
- `tests/test_resolution_backannotation.py` — resolved-pattern-skipped-or-flagged,
  backannotation-requires-pr-evidence.
- `tests/fixtures/mining_ledger_corpus/` — fixture session corpus + ledger state for the
  second-pass test.
- `tests/fixtures/pattern_lineage/` — fixture lineage record + expected skeleton set.
- `tests/fixtures/resolved_pattern/` — fixture finding + PR-evidence back-annotation.

### Verification

```bash
# Mined-session ledger unit tests
uv run pytest tests/test_mining_ledger.py -v

# Pattern-lineage round-trip unit tests
uv run pytest tests/test_provenance_manifest.py -k lineage -v

# Resolution back-annotation unit tests
uv run pytest tests/test_resolution_backannotation.py -v

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . \
  && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports \
  && uv run bandit -r plugins/
```

Expected: all green; second mining pass over an unchanged fixture corpus reports 0 newly
mined sessions and a nonzero standing unmined count; the lineage lookup returns the exact
fixture skeleton set with no raw-transcript file access; the resolved-pattern fixture is
omitted or flagged (not re-surfaced as fresh) on the next mining-pass run.

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

### Source context

- Source: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T10.json (ids
  `T10-F2-8`, `T10-F3-8`, `T10-F6-6`)
- Source type: issue-map
- Source title: Mined-session ledger, pattern lineage, and closed-loop retirement of
  resolved findings

### Context library links

_none_

### Tests to add or update

- `tests/test_mining_ledger.py`
- `tests/test_provenance_manifest.py`
- `tests/test_resolution_backannotation.py`

### Intent

Session-mining runs today (`/retro`'s transcript-review pass) with no memory of what was already mined, no durable record of where a distilled pattern came from, and no channel by which a merged fix ever silences the finding that prompted it. Three related gaps in one bookkeeping layer:

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/445
- Number: 445
- Created at: 2026-07-04T08:16:15.317311+00:00

