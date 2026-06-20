---
title: Global Transcendent-Learnings Layer — Implementation Plan
type: feat
status: active
date: 2026-06-20
origin: docs/brainstorms/2026-06-20-global-transcendent-learnings-requirements.md
---

# Global Transcendent-Learnings Layer — Implementation Plan

## Summary

Build a workspace-level layer that promotes the select few cross-repo learnings into `infiquetra-context-library`'s engineering journal as distilled org standards. Two feeders — a `/retro` marking step (declare) and a new gated workspace pass (recurrence net) — funnel transcendent learnings through a propose-diff-and-wait gate into one upsert-by-lesson destination. The ~785 per-repo learnings stay where they are; recall is pull-only.

## Problem Frame

The per-repo engineering journal works, but each is a silo: a lesson learned in one repo is invisible when the same mistake recurs in another. The naive fix — harvesting all `Generalizable rule` lines into one aggregate file — was rejected during brainstorming as context-bloating duplication, because the marker means "generalized *from* the incident," not "transcends repos."

The grounded gap is narrower and already half-modeled in the codebase. `infiquetra-sdlc/docs/process/engineering-journal.md:195-217` already prescribes "promote when the same rule appears 2+ times" and frames the journal as a feeder to durable surfaces — but that promotion path is per-repo and stops at the repo boundary. There is no cross-repo tier and no mechanism to lift a genuinely transcendent learning into the org-wide library. This plan builds that tier as a gated, derived, pull-only layer.

## Requirements

What the built layer must satisfy. R-IDs trace to the origin brainstorm's requirements (shown in parentheses) and are the reviewer's and `/work`'s checklist.

**Selection & marking**

- R1. A greppable transcendence marker, visually distinct from `**Generalizable rule.**`, is applied inline in a source repo's `LEARNINGS.md` entry. (brainstorm R1)
- R2. `/retro` proposes the marker as a gated edit when a learning passes the transcendence test, operating only within the repo it runs in. (R2, R4)
- R3. A human can apply the marker to any learning at any time, using the same test. (R3)

**Recurrence detection**

- R4. A workspace-level pass reads the marked learnings plus all not-yet-promoted `Generalizable rule` lines across repo journals as its candidate pool, excluding context-library's own journal. (R5, R14)
- R5. Clustering of "same lesson across repos" is by agent judgment with no vector store; a cluster is nominated at a default threshold of two distinct repos, configurable. (R6, R7)

**Promotion**

- R6. Promotion writes a self-contained Rule + Mechanism entry into `infiquetra-context-library`'s `LEARNINGS.md`, readable without opening the source repo. (R8)
- R7. Each promoted entry carries source backlinks (a navigational pointer plus a drift-stable key) to every origin; the source entry stays in place — copy, never move. (R9, R10)
- R8. Every write into the context-library journal is gated: propose a diff, wait for explicit approval. (R11)
- R9. The pass is idempotent via a drift-stable source-key ledger; a recurrence cluster upserts one entry carrying one backlink per source repo. (R12, R13)
- R10. The pass writes only to context-library — never back to source repos — and is READ-ONLY on the SDLC (no issue/board/saga mutation). (brainstorm scope boundary)

**Recall, cost, and integration**

- R11. Promoted learnings are consumed pull-only (grep/read on demand); nothing auto-loads into sessions. (R15)
- R12. The ~785 existing learnings remain in their repos, untouched and searchable. (R16)
- R13. The pass runs manually on demand as an invocable saga skill; scheduling is deferred. (R17)
- R14. The workspace tier reconciles with the existing journal-to-surface promotion model in `infiquetra-sdlc/docs/process/engineering-journal.md`, positioned as a cross-repo journal *feeder*, not a sixth durable surface. (grounding-driven)

## Key Technical Decisions

The load-bearing choices that constrain implementation.

- KTD1. **Marker form — a `**Transcendent.**` subheader line** on the source `LEARNINGS.md` entry, greppable as `^\*\*Transcendent`, distinct from `**Generalizable rule.**`. Rationale: format-consistent with the existing `**Subheader.**` entry grammar (`docs/engineering-journal/LEARNINGS.md:8-22`); trivially greppable; both `/retro` and a human apply it the same way.
- KTD2. **Dedup identity — a per-source stable key `<repo>:<short-hash of the normalized Generalizable-rule text>`**, never a line number. Context-library entries carry the covered key-set, which *is* the dedup ledger. Rationale: resolves the brainstorm's drift P2 — line numbers shift as `LEARNINGS.md` grows; hashing the rule text is drift-proof and needs no ID registry. Trade-off: editing a rule's text re-keys it; the human gate (KTD6) catches the rare re-nomination.
- KTD3. **Backlink convention — a new `**Sources.**` field** in the promoted entry, one line per origin: `<repo> · <YYYY-MM-DD> · <short-hash> — <repo>/docs/engineering-journal/LEARNINGS.md`. Rationale: context-library's journal has no existing backlink/source convention (Agent 3); this introduces the minimal one, doubling as provenance (navigation) and dedup ledger (the keys).
- KTD4. **Recurrence mechanism — agent-judgment clustering over the in-window candidate pool, threshold ≥2 repos, no vectors.** Rationale: matches the brainstorm and Anthropic's agentic-grep stance, and aligns with the practice doc's existing "same rule appears 2+ times → promote" heuristic (`infiquetra-sdlc/docs/process/engineering-journal.md:195-217`).
- KTD5. **Home & mirror — a new saga skill in `infiquetra-claude-plugins`, mirroring `/ideate`'s cross-repo grounding** (workspace + `gh` repo discovery, per-repo reader agents, context-library short-circuit). Rationale: `/ideate` (`.../skills/ideate/SKILL.md:40-100, 247-300`) is the only proven workspace-spanning pattern in saga; reuse it rather than invent. Working command name **`promote`** (disambiguated below; open to override at routing).
- KTD6. **Gating — every context-library write and the `/retro` marking edit are Tier-2 propose-diff-and-wait.** Rationale: marking modifies an existing entry, which `/retro`'s self-edit-safety contract already classifies as gated (`.../skills/retro/SKILL.md:81-99`); cross-repo writes into the canonical library warrant the same gate, consistent with sdlc's high-blast-radius cadence decision (`infiquetra-sdlc/docs/engineering-journal/DECISIONS.md:81-90`).
- KTD7. **Boundary split — `/retro` keeps its single-repo boundary; the cross-repo write lives ONLY in the new skill,** which is saga READ-ONLY on the SDLC and writes only to context-library. Rationale: preserves brainstorm R4 and confines all cross-repo mutation to one auditable place.

The `promote` name reuses the practice doc's existing "promotion" vocabulary (journal → standard) and is distinct from mission-control's *issue* promotion; alternatives `globalize` / `transcend` are noted for the routing confirmation.

## High-Level Technical Design

The shape of the layer, end to end.

Two feeders converge on one gated pass that writes one destination. **Declare:** `/retro` (or a human) marks a transcendent learning in its own repo with `**Transcendent.**` (KTD1) — a local, gated edit, no cross-repo write. **Recurrence net:** the new `promote` skill enumerates every repo journal under the workspace (mirroring `/ideate`'s discovery, KTD5), reads the marked entries plus all `Generalizable rule` lines, excludes context-library (recursion guard), and clusters same-lesson-across-repos by judgment (KTD4).

The pass splits into a deterministic backbone and a judgment layer. A new `promote_scan.py` script does the mechanical work — enumerate journals, parse the marker and rule lines across their known format variants, compute the drift-stable source-key (KTD2), and filter out keys already present in context-library's `**Sources.**` ledger. The SKILL.md does the judgment — cluster nomination, distillation to a self-contained Rule + Mechanism entry, and the propose-diff-and-wait gate (KTD6). Promotion is an upsert keyed on the source-key set: a three-repo cluster becomes one entry with three `**Sources.**` backlinks, not three entries.

Architecturally this is a **cross-repo journal feeder**, not a new durable surface. It sits beside the per-repo journals one tier up; from context-library, the existing journal-to-surface promotion rules still apply. U6 reconciles this with `engineering-journal.md` so the workspace tier extends — rather than forks — the documented promotion model.

## Implementation Units

Dependency-ordered. Each is independently landable. Paths are repo-qualified when they leave this plan's repo (`infiquetra-claude-plugins`): context-library and sdlc targets carry their repo prefix; bare paths (e.g. `plugins/saga/...`, `tests/...`) are relative to `infiquetra-claude-plugins`.

**Landing surfaces (multi-repo).** This plan touches three repos: `infiquetra-claude-plugins` (the `promote` skill, scripts, tests, and release surfaces — U1-U5), `infiquetra-context-library` (the promotion destination journal plus a README template note — U1, U4), and `infiquetra-sdlc` (the practice-doc and DECISIONS reconciliation — U6). It does not land as one PR; each repo carries its own branch/PR, sequenced by the unit dependency order.

**Coordination (decided — Option A).** A single workspace-level `/work` session drives all three repos and opens one branch/PR per repo in dependency order. U1's data contract lands first because everything depends on it; then the `infiquetra-claude-plugins` PR carries U1's contract reference plus U2-U5, the `infiquetra-context-library` PR carries U1's README template note, and the `infiquetra-sdlc` PR carries U6. The driving session holds the cross-repo dependency chain so U2-U6 never start against an unfrozen contract.

### U1. Promotion data contract (marker, key, entry template)

**Goal:** Pin the formats everything else depends on — the `**Transcendent.**` marker, the source-key derivation, and the context-library promoted-entry template with `**Sources.**`.

**Dependencies:** none (foundational).

**Files:** `plugins/saga/skills/promote/references/promotion-contract.md` (new); a short entry-template note appended to `infiquetra-context-library/docs/engineering-journal/README.md`.

**Approach:** Specify the marker line and its grep pattern; define the normalized-rule hashing (lowercase, collapse whitespace, strip the `**Generalizable rule.**` label and trailing punctuation, then short hash); define the `**Sources.**` line grammar and the promoted-entry skeleton (reusing context-library's `**Author.**` + subheader grammar, Agent 3). Enumerate the known marker format variants the parser must tolerate.

**Test expectation:** none — convention/reference doc; its rules are enforced executably by the U3 `promote_scan.py` tests and the U5 drift guard.

**Verification:** the contract's marker regex and key recipe are quoted verbatim by `promote_scan.py` (U3) and the `/retro` sweep (U2); no divergent second definition exists.

### U2. `/retro` transcendence-marking sweep (declare feeder)

**Goal:** Teach `/retro` to assess transcendence and propose the `**Transcendent.**` marker, within the current repo only.

**Dependencies:** U1.

**Files:** `plugins/saga/skills/retro/SKILL.md` (Phase-4 CURATE); optionally `.../retro/references/retro-passes.md`.

**Approach:** Add a rule-enforcement-style sweep in Phase 4 CURATE (`.../retro/SKILL.md:215-239`) that applies the transcendence test — *would this rule hold and help in a repo of a different stack or domain?* — and, when met, proposes adding the marker as a Tier-2 propose-diff-and-wait edit (it modifies an existing entry, so it is gated by the existing contract at `:81-99`). No cross-repo write; the marker sits locally until the next `promote` run.

**Test scenarios** (`tests/test_saga_plugin.py`): the retro contract test asserts the marking sweep tokens are present in Phase 4; asserts it is classified Tier-2 (propose-diff), not auto-append; boundary negative — the sweep adds no cross-repo or context-library write to `/retro`.

**Verification:** `grep` for the sweep + a dry contract-test run; `/retro`'s "writes only to current repo" boundary statements remain intact.

### U3. `promote` skill — discovery, scan, and recurrence clustering (recurrence-net feeder)

**Goal:** Build the new workspace skill's read half — discover journals, build the candidate pool, exclude context-library, compute keys, and nominate recurrence clusters.

**Dependencies:** U1.

**Files:** `plugins/saga/skills/promote/SKILL.md` (new); `plugins/saga/scripts/promote_scan.py` (new).

**Approach:** `promote_scan.py` enumerates `*/docs/engineering-journal/LEARNINGS.md` under the workspace root (and local clones, mirroring `/ideate` at `.../skills/ideate/SKILL.md:247-273`), parses `**Transcendent.**` markers and `Generalizable rule` lines across the U1 variants, computes per-source keys (KTD2), and drops keys already in context-library's ledger. SKILL.md mirrors `/ideate`'s grounding gate, then clusters same-lesson-across-repos by judgment (KTD4) at the ≥2 threshold, emitting a nomination list.

**Test scenarios** (`tests/test_promote_scan.py`, new): fixture journals across 3 fake repos → enumeration finds all; **key is stable when a fixture entry's line number is shifted** (drift proof, KTD2); context-library fixture journal is excluded (recursion guard, AE4); all marker format variants parse; a lesson present in 1 repo is below threshold, in 2 is nominated (AE2). Plus a contract test that `promote/SKILL.md` carries the `/ideate`-mirrored discovery tokens.

**Verification:** `pytest tests/test_promote_scan.py`; manual dry-run scan over the real workspace prints a sane nomination list with no context-library entries.

### U4. `promote` skill — gated upsert and idempotency (promotion)

**Goal:** Build the new skill's write half — distill, upsert by lesson, gate, and dedup.

**Dependencies:** U3, U1.

**Files:** `plugins/saga/skills/promote/SKILL.md`; `plugins/saga/scripts/promote_scan.py` (upsert/ledger helpers).

**Approach:** For each approved cluster, distill Rule + Mechanism into the U1 entry template, compute the destination upsert (match an existing entry by overlapping source-key set, else create), append `**Sources.**` backlinks for new origins, and write only to context-library behind a Tier-2 propose-diff-and-wait gate (KTD6). Idempotency comes from the key ledger (KTD2): already-covered keys are skipped.

**Test scenarios** (`tests/test_promote_scan.py`): re-running with an already-present key-set yields no new/duplicate entry (AE1); a 3-repo cluster yields one entry with three `**Sources.**` lines, not three entries (AE3); the writer refuses any path outside context-library's journal (R10 write-surface guard); a marked-but-unapproved cluster produces a proposed diff and no write until approval (AE5). Contract test: `promote/SKILL.md` states the Tier-2 gate and the context-library-only boundary.

**Verification:** `pytest`; a manual end-to-end dry run shows a proposed diff, and approving it writes exactly one upserted entry.

### U5. Skill registration and release surfaces

**Goal:** Make `promote` an installed, packaged saga command without metadata drift.

**Dependencies:** U2, U3, U4.

**Files:** `plugins/saga/commands/promote.md` (new); `plugins/saga/.claude-plugin/plugin.json` (version 0.22.1 → 0.23.0); `.claude-plugin/marketplace.json` (matching version); `plugins/saga/CHANGELOG.md` (new entry); `tests/test_saga_plugin.py` (dispatch tuple).

**Approach:** Add the command file (the `Load saga/skills/promote/SKILL.md …` shape of `.../commands/ideate.md:1-16`); bump both versions in lockstep; add the CHANGELOG entry; add `promote` to the packaged-commands tuple at `tests/test_saga_plugin.py:57-78`. Follow the repo's release-surface rule (`CLAUDE.md:96-107`).

**Test scenarios** (`tests/test_saga_plugin.py`): the dispatch test now expects `promote`; the version-drift guard sees identical `plugin.json`/`marketplace.json` versions; the CHANGELOG has the new top entry.

**Verification:** `uv run pytest tests/test_saga_plugin.py` green; `python3 -m json.tool` validates both JSON files.

### U6. Practice-doc and decision-record integration (sdlc)

**Goal:** Document the workspace tier where the practice lives and reconcile it with the existing promotion model.

**Dependencies:** U1.

**Files:** `infiquetra-sdlc/docs/process/engineering-journal.md`; `infiquetra-sdlc/docs/engineering-journal/DECISIONS.md`.

**Approach:** Extend `infiquetra-sdlc/docs/process/engineering-journal.md:195-217` to describe the cross-repo transcendent-learnings tier as a *feeder* (not a sixth surface, per `infiquetra-sdlc/docs/engineering-journal/DECISIONS.md:254-283`), and reconcile it with the existing "promote when 2+ times" rule so the two paths compose rather than conflict. Record KTD1-KTD7 as a dated entry in `infiquetra-sdlc/docs/engineering-journal/DECISIONS.md` at implementation time (not now — pre-review), with rationale and revisit conditions. These are build-time documentation edits to sdlc markdown, distinct from R10's *runtime* READ-ONLY-on-SDLC boundary (the `promote` pass never mutates SDLC issues, boards, or sagas).

**Test expectation:** none — documentation; verified by cross-reference link-check.

**Verification:** the practice doc names the `promote` skill and the marker; the DECISIONS entry exists with revisit conditions; no contradictory promotion rule remains.

## Scope Boundaries

What this plan does not do.

**Deferred to follow-up work:**

- An always-loaded hot tier / auto-memory population (brainstorm survivor #4) — addable later with no rework; it would read the most-backlinked context-library entries.
- Scheduled/automatic invocation of the `promote` pass — manual only for now (R13).
- A dedicated `/recall` agentic-grep skill (survivor #3) — separate work; recall stays plain grep for now.

**True non-goals:**

- No aggregate `GLOBAL_LEARNINGS.md` and no bulk-copy of the ~785 learnings — the rejected harvest model.
- No vectors, RAG, or embeddings.
- No write-back to source repos from the pass; no cross-machine sync engineering (context-library is already git).
- No bulk migration of existing journals to the new `**Sources.**`/marker conventions — the convention is introduced going forward.

## Risk Analysis & Mitigation

The ways this most plausibly fails, and the guards.

| Risk | Likelihood | Mitigation |
|---|---|---|
| Candidate pool outgrows one context window (breaks the judgment-not-vectors basis) | Low now (~785 lines), rising | `promote_scan.py` chunks the scan and `log`s when the pool exceeds a configurable size; revisit-when condition recorded in DECISIONS (U6). |
| Inconsistent transcendence marking by `/retro` and humans | Medium | Operational test in U2; the recurrence net (U3) backstops missed declarations; the gate filters false positives. |
| Rule text edited after promotion re-keys the lesson → re-nomination | Low | Hash the *normalized* rule (KTD2); the human gate (KTD6) catches the rare duplicate; the source-key is surfaced in `**Sources.**` for manual reconciliation. |
| Cross-repo write blast radius into the canonical library | Medium | Tier-2 gate on every write (KTD6); write-surface confined to context-library (R10); recursion guard (AE4). |
| New tier conflicts with the existing "2+ times → CLAUDE.md" promotion rule | Medium | U6 reconciles explicitly and positions the tier as a feeder, not a surface. |

## Alternatives Considered

Why the rejected forks were rejected.

- **Vector RAG over journals** — dominated by agentic grep at journal scale; re-index tax and retrieval-failure risk. Rejected (brainstorm revivable cut R2).
- **Aggregate harvest into one generated file** — context-bloating duplication; conflates "general" with "transcendent." Rejected — this is the reframe the whole feature rests on.
- **Write-back a "promoted" flag to source repos** — expands the write surface to every repo; unnecessary once the drift-stable key ledger (KTD2) tells the pass what is already promoted. Rejected.
- **Git-hook / automatic promotion** — fragile across 30+ repos and judgment-free; the manual, gated, agent-judged pass is the safer shape (consistent with `infiquetra-sdlc/docs/engineering-journal/DECISIONS.md:81-90`). Rejected.

## Sources / Grounding

Anchors a reviewer or implementer reading cold will want.

- `docs/brainstorms/2026-06-20-global-transcendent-learnings-requirements.md` — the settled WHAT; this plan is its HOW.
- `plugins/saga/skills/ideate/SKILL.md:40-100, 247-300` — the cross-repo grounding pattern KTD5 mirrors.
- `plugins/saga/skills/retro/SKILL.md:81-99, 215-239` — the self-edit-safety tiers and Phase-4 CURATE slot for U2.
- `infiquetra-context-library/docs/engineering-journal/LEARNINGS.md` — the destination format; no existing backlink convention (KTD3 introduces it).
- `infiquetra-sdlc/docs/process/engineering-journal.md:195-217` and `infiquetra-sdlc/docs/engineering-journal/DECISIONS.md:81-90, 254-283` — the existing promotion model and cadence the tier must reconcile with (U6).
- `CLAUDE.md:96-107`, `tests/test_saga_plugin.py:57-78` — the release-surface and dispatch-test touchpoints for U5.
