---
date: 2026-06-20
topic: global-transcendent-learnings
maturity: requirements-ready
source: docs/ideation/2026-06-19-global-engineering-journal-ideation.md (survivors #1 derived-rollup + #2 retro-promote, reshaped)
---

# Global Transcendent-Learnings Layer

## Summary

A global layer that promotes the *select few* learnings which genuinely cross repositories into the `infiquetra-context-library` engineering journal as distilled org standards. The per-repo journals stay the system of record; the global layer is a small, derived, pull-only set — not an aggregate of every journal.

## Problem Frame

The per-repo engineering journal works. Roughly 785 `**Generalizable rule.**` lines now exist across 30 repos — but each is a silo with zero rollup, so a lesson learned in one repo is invisible when the same mistake reappears in another. The instinct was to harvest all 785 into one generated `GLOBAL_LEARNINGS.md`.

That instinct is wrong, and naming why is the whole frame. The `Generalizable rule` marker means "generalized *from* the incident" — within-repo, usually domain-bound (an Ansible `selectattr`/`loop_control.label` lesson is useless outside the home-lab). It does **not** mean "transcends repositories." Bulk-harvesting conflates the two senses of "general" and produces a duplicated, context-bloating file nobody wants.

The real gap is a handful of learnings that *do* transcend any single repo, with no home and no path to get there. The cost today is silent re-learning: the same cross-cutting lesson rediscovered repo by repo because the transcendent few are buried in an undifferentiated long tail.

## Key Decisions

The framing choices that constrain everything below.

- **Global means the transcendent subset, never the aggregate.** The deliverable is the select learnings that cross repos, not a roll-up of all 785. This kills the harvest-everything model outright; the 785 stay where they are.
- **Two feeders: declare + recurrence net.** Transcendence is caught at write time (a marker applied when the lesson is known to cross repos) *and* by a periodic safety-net sweep that catches what declaration missed. Neither alone is trusted to be complete.
- **Home is the context-library journal, pull-only.** Promoted learnings land in `infiquetra-context-library/docs/engineering-journal/LEARNINGS.md` and are read on demand. No new aggregate file, no always-loaded hot tier in this build — so the layer costs zero context budget at rest.
- **Promotion is copy + backlink, not move.** The distilled lesson is copied up with a backlink to its origin; the source entry stays put as the incident record. Idempotency keys on the lesson's drift-stable identity (a content hash or assigned ID), not on line position — so the backlinks stay a pure provenance trail while re-runs reliably skip what is already promoted.
- **What lands is Rule + Mechanism, readable cold.** A promoted entry is self-contained — the generalizable rule plus the why — stripped of incident-specific cruft, understandable without opening the source repo.
- **`/retro`'s single-repo boundary stays intact.** Per-repo `/retro` only *marks* transcendence locally; it never writes across repos. The cross-repo write lives in a new workspace-level pass, `/retro`'s sibling.
- **Agent judgment, not vectors.** The recurrence sweep reads the `Generalizable rule` lines (which fit one context window today) and clusters by judgment. No embeddings, no RAG, no re-index tax.
- **Every context-library write is gated.** Promotions are proposed as a diff and wait for human approval before anything is written — these become org standards, so a human signs off.

## Requirements

What must be true of the layer. IDs are stable and referenced by the flows and acceptance examples below.

**Selection & marking (the declare feeder)**

- R1. A transcendence marker exists that is greppable and visually distinct from `**Generalizable rule.**`, applied inline alongside the source learning in its own repo's `LEARNINGS.md`.
- R2. `/retro` gains a step that applies the marker when a learning passes the transcendence test — *would this rule hold and help in a repo of a different stack or domain?* — operating only within the repo it is run in.
- R3. A human can apply the marker to any learning at any time, independent of `/retro`, using the same transcendence test.
- R4. Marking introduces no cross-repo write; `/retro`'s single-repo safety boundary is preserved exactly as it is today.

**Recurrence detection (the recurrence-net feeder)**

- R5. A workspace-level pass reads `Generalizable rule` lines from the `docs/engineering-journal/` directories of all repos under the Infiquetra workspace root (the directory that parents the repos) as its candidate pool; whether a line counts as not-yet-promoted is determined by the dedup ledger (R12), not by mutating the source — source markers persist in place.
- R6. The pass clusters "same lesson appearing in multiple repos" by agent judgment over that text — no vector store, no embeddings.
- R7. The pass nominates a cluster for promotion when the lesson recurs across at least two distinct repos by default — the literal meaning of recurrence — with the threshold configurable and raisable if nominations prove noisy.

**Promotion (the global pass → context-library)**

- R8. Promotion writes a self-contained entry — the generalizable rule plus its mechanism — into the context-library journal, readable without opening the source repo.
- R9. Each promoted entry carries one or more backlinks to its origin(s) as `repo/path:line` references for human navigation; these are provenance pointers that may drift as source files grow, not the idempotency key (R12).
- R10. The source entry is left in place as the incident record; promotion copies, never moves or deletes.
- R11. Every write into the context-library journal is gated: the pass proposes a diff and waits for explicit human approval before writing.
- R12. The pass is idempotent — dedup keys on each lesson's drift-stable identity (a content hash of its rule and mechanism, or an assigned lesson ID), so a lesson already promoted is never promoted again even as source line numbers shift.
- R13. A recurrence cluster upserts a single context-library entry — matched by the lesson's stable identity (R12) — carrying one backlink per source repo rather than one entry per repo; backlink count is the transcendence signal.
- R14. The pass excludes the context-library's own journal from its candidate pool, so promoted entries never feed themselves.

**Recall & cost**

- R15. Promoted learnings are consumed pull-only — grepped or read from the context-library journal on demand — with no automatic injection into sessions.
- R16. The ~785 existing learnings remain in their repos, untouched and individually searchable; they are the long tail, not migrated.

**Invocation**

- R17. The global pass runs manually on demand as an invocable skill; scheduled or automatic invocation is deferred.

## Key Flows

The two paths a learning can travel from a repo to the global layer.

**F1. Declaration-driven promotion**

- **Trigger:** `/retro` (R2) or a human (R3) marks a learning transcendent in its repo's `LEARNINGS.md`.
- The marker sits locally until the next global-pass run — no cross-repo write happens at mark time (R4).
- On the next run, the pass collects marked learnings, distills each to Rule + Mechanism, and proposes a copy-up with a backlink to the source (R8, R9, R10).
- The human approves or rejects each proposed entry; only approved entries are written to the context-library journal (R11).

**F2. Recurrence-net promotion**

- **Trigger:** the global pass runs and reads all not-yet-promoted `Generalizable rule` lines as its pool (R5), excluding the context-library's own journal (R14).
- It clusters same-lesson-across-repos by judgment (R6) and keeps clusters that clear the recurrence threshold (R7).
- For each surviving cluster it proposes a single upserted entry carrying one backlink per source repo (R13); already-backlinked sources are skipped as duplicates (R12).
- The human approves or rejects each proposal before any write (R11).

## Acceptance Examples

The conditional requirements, pinned so planning cannot reinvent the edge behavior.

- AE1. **Covers R12.** When the pass runs and a lesson's stable identity already exists in the context-library journal, that lesson produces no new or duplicate entry — even if its source line number has since shifted.
- AE2. **Covers R7.** When a lesson is judged to recur across at least the threshold number of distinct repos, it is nominated; when it appears in fewer, it is not.
- AE3. **Covers R13.** When a recurrence cluster spans three repos, the pass proposes one context-library entry with three backlinks — not three separate entries.
- AE4. **Covers R14.** When the pass builds its candidate pool, `Generalizable rule` lines already living in the context-library's own journal are excluded from clustering and nomination.
- AE5. **Covers R2, R11, R15.** When a learning is marked transcendent, it does not appear in the context-library journal at mark time; it appears only after a subsequent pass run and only after the human approves the proposed entry.

## Scope Boundaries

What this build deliberately does not do.

- **No aggregate `GLOBAL_LEARNINGS.md` and no bulk-copy of the 785.** This is the rejected harvest model; the long tail stays distributed.
- **No vectors, RAG, or embeddings.** Agent judgment over greppable text is the chosen mechanism (revivable cut R2 stays rejected).
- **No always-loaded hot tier and no auto-memory-dir population.** That is survivor #4 — deferred, and addable later with no rework here, since it would simply read the most-backlinked context-library entries.
- **No `/recall` skill, no Todoist integration, no dedicated journal git repo.** Survivors #3, #6, and #5 are out of this build's scope.
- **No cross-machine sync engineering.** The context-library is already a git repo, so durability and sync ride along for free; building a sync mechanism is not in scope.
- **No scheduling or automation of the pass.** Manual invocation only for now (R17).
- **No write-back to source repos from the global pass.** The pass writes only to the context-library journal; source-repo markers are written locally by `/retro` or a human, never by the global pass.

## Success Criteria

Signals that the layer is doing its job, beyond the requirements being met.

- Zero context-budget cost at rest — nothing about the layer auto-loads into a session.
- A reader can grep the context-library journal for an org standard and trace it back to the originating incident through its backlink.
- Re-running the pass is safe and boring — no duplicate proliferation, ever (the drift-stable dedup ledger holds).
- A promoted entry reads correctly cold, with no need to open the source repo to understand it.
- The 785 per-repo learnings are demonstrably untouched, and `/retro` still performs no cross-repo writes.

## Dependencies / Assumptions

Upstream facts the design leans on, including the ones worth revisiting as scale grows.

- Depends on `infiquetra-context-library` existing with an active `docs/engineering-journal/` (verified present this session: `LEARNINGS.md` ~17KB, 50+ dated entries).
- Depends on the `**Generalizable rule.**` marker being a stable, greppable anchor (verified: 785 marker lines across 30 repos; 602 in canonical form; 778 carry the lesson text inline on the same line).
- **Scaling assumption:** the candidate pool fits one context window, which is what makes "judgment, not vectors" viable. True at ~785 lines today; revisit when the corpus outgrows a single window.
- **Format-tolerance assumption:** the recurrence pass must normalize across the 13+ observed marker variants (canonical, leading-space, colon-terminated, heading-form, bare), not just the canonical 571 — a planning-level detail, but a real one.
- Assumes `/retro` can host a marking step inside its existing per-repo, gated, propose-diff structure (verified: `/retro` is prompt-driven and single-repo; the marking step fits its local-curation phase).

## Outstanding Questions

All deferred to planning — none is an open product decision that blocks `/plan`.

- The exact marker string and syntax for declaration (distinct from `Generalizable rule`, cleanly greppable).
- Whether the default recurrence threshold of two repos should be raised, once real nomination noise is observed.
- Whether the global pass is a brand-new skill or an extension of an existing one, and its name.
- The context-library entry template — how rule, mechanism, and multiple backlinks render in one entry.
- The exact drift-stable dedup key — a content hash of the rule and mechanism versus an assigned lesson ID — and how the `repo/path:line` backlink pointer is refreshed when source lines move.
- Whether declared-but-not-yet-promoted learnings should also flow through recurrence clustering (likely yes, so a declared lesson can still merge with undeclared siblings).

## Sources / Research

Breadcrumbs a planner reading cold would want.

- `docs/ideation/2026-06-19-global-engineering-journal-ideation.md` — the ideation this deep-dives; survivors #1 and #2, reshaped after the aggregate-harvest model was rejected.
- `plugins/saga/skills/retro/SKILL.md` and `plugins/saga/skills/retro/references/self-edit-safety.md` — `/retro`'s gated, single-repo safety model; the boundary R4 preserves and the propose-diff pattern R11 reuses.
- `infiquetra-context-library/docs/engineering-journal/LEARNINGS.md` — the promotion destination.
- Marker scan (this session): 785 lines / 30 repos / 33 journal dirs; 602 canonical, 778 inline — the basis for the single-window recurrence pass and the format-tolerance assumption.
