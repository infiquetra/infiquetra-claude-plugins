---
date: 2026-06-27
kind: brainstorm
maturity: requirements-ready
type: capability
source: docs/ideation/2026-06-26-vecu-port-seeds-ideation.md — survivor S-3 (PreCompact spore rehydration)
title: "PreCompact Spore — Re-ground the Continuing Session on Structured Saga Facts, Not Prose"
---

# PreCompact Spore — Re-ground the Continuing Session on Structured Facts, Not Prose

## Summary

When a long continuous session (a `/work`, `/loop`, or especially an `/outcome` campaign) fills the
context window, the harness **auto-compacts**: it replaces the conversation with a prose summary and
the **same session keeps running**. Structured saga facts the run depends on — open leaf ids, the
ready frontier, per-leaf gate verdicts, `saga_id`, `next_step` — get blurred into that prose or
dropped. The session continues, but fuzzy about *where it is*.

The fix is a **"spore"**: at the compaction boundary, saga writes a thin **structured** snapshot of
those facts, and immediately after compaction re-injects them into the continuing session so it
re-grounds on facts, not prose. This is the survivor's load-bearing critique made literal —
*rehydrate from structured durable facts, never a prose CoT summary*.

**Grounding correction (verified this session).** The survivor's framing — "saga has no durable
rehydration; `load_state` should prefer the spore over the harness summary" — is **wrong about the
baseline**. Saga *already* rehydrates durably on the **explicit `/resume` path**: append-only
immutable ticks (each a full snapshot), a derived/rebuildable `state.json`, and `/resume`
reconstructs from the whole tick chain + committed `docs/*` + GitHub, with an explicit authority model
("committed docs + GitHub are authoritative; the `.claude/saga/` cache is the *anchor, not the
authority*"). There is no `load_state` function. The real, unguarded gap is narrower: the **mid-run
auto-compaction boundary**, where the *same* session continues on the harness prose summary without
ever calling `/resume`. The spore guards exactly that boundary — it **augments** the post-compaction
window with authoritative structured facts; it does not (and cannot) replace the harness summary.

**Operator scope (this brainstorm):** the spore carries the **OutcomeOrchestrator DAG frontier + the
single active saga** (Q1=A), and uses **persist + re-inject** (Q2=A).

## Problem frame

- **Where it bites hardest:** long `/outcome` campaigns that eat *multiple* compactions. The
  OutcomeOrchestrator's frontier (open leaf ids, ready set, per-leaf gate verdicts) is **computed
  derived-on-read every reconcile tick and never persisted** (`outcome_projection.py:72`,
  `outcome_spec.py:531`, `outcome.py:333`). After a compaction, the continuing agent must re-derive
  it from the spec + store — and if those aren't in the compacted context, it cannot.
- **Why `/resume` doesn't cover it:** `/resume` is an *explicit, fresh-session* cold restart and is
  already fully durable. Auto-compaction is *implicit and mid-run* — the agent never re-runs `/resume`;
  it just keeps going on the summary. Nothing today writes saga facts at that boundary.
- **The hook reality (confirmed via the Claude Code hooks reference):**
  - `PreCompact` hook **exists** (matchers `auto` + `manual`), can write files, but **cannot inject
    context** into the post-compaction window — its only output is `decision: block`. So PreCompact is
    **write-to-disk only**.
  - `SessionStart` fires after compaction with `source: "compact"`, and its `additionalContext` **is**
    injected into the continuing window — **capped at 10,000 characters**.
  - Therefore the mechanism is a **mandatory two-hook split**: PreCompact writes the spore →
    SessionStart(`source=compact`) reads it and re-injects (≤10k). saga already emits SessionStart
    `additionalContext` today (`stale_main_session_hook.py:235-244`), so the injection substrate is
    proven.

## Key decisions

- **KD1 — The spore is a thin STRUCTURED index, never prose or a log re-dump.** This is the survivor's
  central critique and is now a *hard constraint*: the 10k `additionalContext` cap enforces thinness
  by construction. The spore carries enumerated facts + pointers to canonical artifacts, not narrative.
- **KD2 — Two-hook split is mandatory (not a design choice).** PreCompact cannot inject (confirmed);
  it only persists. The re-injection MUST come from `SessionStart(source=compact)`. A spore write with
  no reader would be dead-wiring — both ends are in scope.
- **KD3 — The spore AUGMENTS; it is the anchor, not the authority.** It adds authoritative structured
  facts beside the harness summary (it cannot replace the summary — that's already in-context). On
  conflict, structured facts + committed docs + GitHub win, consistent with the existing `/resume`
  precedence. The spore lives in the git-ignored `.claude/saga/` cache like ticks.
- **KD4 — The frontier must be computed-and-frozen at the boundary.** Because it is derived-on-read
  and never persisted, the PreCompact hook computes the live frontier (`ready_frontier(spec,
  completed)`) at the instant of compaction and serializes the result. Post-compaction it is read, not
  re-derived.
- **KD5 — Consume-and-reset; match before inject.** The SessionStart hook injects only a spore that
  matches the active saga / cwd, and resets it after consuming, so a stale spore from a prior
  compaction never re-injects into an unrelated session.
- **KD6 — The spore path must be worktree-safe.** Lifecycle writes in background/worktree sessions
  land in the worktree, which can be removed; a spore written to a vanishing worktree path would be
  unreadable by the post-compaction SessionStart. The spore must be written to a stable, session-
  resolvable location (not a worktree-relative one). *(repo lesson: bg-worktree ↔ saga interaction.)*
- **KD7 — Never block compaction; degrade silently.** A spore failure (can't compute frontier, can't
  write) must let compaction proceed and the session continue — exit 0, no `decision: block`, no
  raise. Same discipline as the existing SessionStart hook.

## Actors

- **A1 — PreCompact hook (net-new).** Fires at the boundary (auto + manual). Resolves the active
  saga, computes-and-freezes the DAG frontier + single-saga box, serializes a ≤10k structured spore to
  a stable path. Write-only; silent on failure.
- **A2 — SessionStart(source=compact) hook (extends existing pattern).** On `source=compact`, reads
  the matching spore, emits it as `additionalContext`, resets it. Reuses the
  `hookSpecificOutput`/`additionalContext` shape already in `stale_main_session_hook.py`.
- **A3 — The continuing session (consumer).** Receives the structured facts at the top of the
  post-compaction window and re-grounds: which leaves are open, what's ready, which gates passed, the
  current saga's phase/next_step.

## Requirements

**Spore content — the structured spine (Q1=A):**
- **R1** — The spore is structured facts (keyed fields), not prose and not a re-dump of the tick log.
- **R2** — It carries the **single active saga** box: `saga_id`, `lifecycle_phase`, `phase_status`,
  `status`, `next_step`, `blockers`, `open_questions`, last `checks_run`. *(fields exist —
  `saga.py:138-225`)*
- **R3** — It carries the **OutcomeOrchestrator DAG**: open leaf ids, the ready frontier, and per-leaf
  last gate verdicts — **computed-and-frozen at PreCompact** (KD4). *(derive via
  `ready_frontier`/`derive_states`)*
- **R4** — It carries **pointers** to canonical artifacts (outcome-spec path, issue refs, plan/work
  doc paths), not their contents. *(authority stays in committed docs + GitHub — KD3)*
- **R5** — The serialized spore fits the **10,000-char** `additionalContext` budget, with an explicit
  **prioritization + truncation** rule (frontier + open leaves + last-N verdicts inline; the remainder
  replaced by a counted pointer, e.g. "+K more leaves — see `<spec>`"). Truncation is **logged/visible**,
  never silent. *(no-silent-caps lesson)*

**The two-hook mechanism (Q2=A):**
- **R6** — A `PreCompact` hook (matchers `auto` **and** `manual`) writes the spore to a stable,
  worktree-safe path in the git-ignored saga cache. *(KD6; saga registers no PreCompact hook today —
  `hooks.json:3-45`)*
- **R7** — A `SessionStart` hook branch on `source == "compact"` reads the matching spore and emits it
  as `additionalContext`. *(extends `stale_main_session_hook.py`)*
- **R8** — The spore is **consumed and reset** after injection, so it cannot re-inject on a later
  unrelated compaction. *(KD5)*
- **R9** — Injection is **match-guarded**: only the spore for the active saga / cwd is injected (no
  cross-session leakage). *(KD5)*

**Correctness & authority:**
- **R10** — The spore **augments**; structured facts + committed docs + GitHub remain authoritative on
  conflict, per the existing `/resume` precedence. The spore never becomes the source of truth. *(KD3)*
- **R11** — Nothing on the existing `/resume` path or the tick/`state.json` model changes; the spore is
  additive cache. *(don't touch what already works durably)*

**Robustness:**
- **R12** — Both hooks **degrade silently**: any failure → compaction proceeds / session continues,
  exit 0, no block, no raise. *(KD7; mirrors the existing SessionStart hook)*
- **R13** — The PreCompact write and the SessionStart read agree on the spore path/format and are
  covered by a round-trip test (write a spore from a synthetic saga+outcome, assert SessionStart emits
  the expected structured `additionalContext` within budget). *(components-present ≠ end-to-end —
  test the seam)*

## Key flows

- **F1 — Auto-compaction during an `/outcome` campaign.** Window fills → `PreCompact(auto)` computes
  the frontier (U9,U10 ready; U8 verdicts; U11 waiting) + the coordinator saga box, writes the spore →
  harness compacts → `SessionStart(source=compact)` injects the structured facts → the continuing
  session re-grounds and advances the right leaf.
- **F2 — Manual `/compact`.** Same path via matcher `manual`; the operator compacting by hand gets the
  same re-grounding.
- **F3 — Spore failure.** PreCompact can't resolve the active saga → writes nothing, compaction
  proceeds, SessionStart finds no matching spore and injects nothing. Session continues on the prose
  summary (status quo) — no regression.
- **F4 — Stale spore.** A spore from compaction N is consumed+reset at compaction N's SessionStart; at
  compaction N+1 a fresh spore is written. No double-inject. *(R8)*

## Acceptance examples

- **AE1** — Given a long `/outcome` session that auto-compacts, the post-compaction context contains an
  injected `additionalContext` block listing the ready frontier, open leaves, and last gate verdicts
  (structured), not only the harness prose. *(R3/R7)*
- **AE2** — Given a campaign whose full per-leaf detail exceeds 10k chars, the spore truncates to
  frontier + open leaves + last-N verdicts and appends a counted pointer; total ≤10k; the drop is
  logged. *(R5)*
- **AE3** — Given a PreCompact hook error, compaction still completes and the session continues; no
  block, no traceback. *(R12)*
- **AE4** — Given two consecutive compactions, the second does not re-inject the first's spore. *(R8)*
- **AE5** — Given a spore fact that conflicts with a merged PR's state, the canonical source wins on
  `/resume`/reconcile; the spore is treated as anchor, not authority. *(R10)*
- **AE6** — Given a background/worktree session, the spore is written to a stable path that the
  post-compaction SessionStart can still read after the worktree is gone. *(R6/KD6)*

## Scope boundaries

- **IN**: the two-hook spore (PreCompact write + SessionStart(`compact`) re-inject); DAG frontier +
  single-saga content; 10k-budget thinness with explicit truncation; worktree-safe path; silent
  degrade; the seam round-trip test.
- **OUT — the existing `/resume` path.** Already durable; not touched. *(R11)*
- **OUT — replacing the harness summary.** Impossible (it's already injected by the harness); the spore
  augments only. *(KD3)*
- **OUT — persisting the frontier into the canonical `outcome-spec.json`.** The spore is a boundary
  cache, not a schema change; the frontier stays derived-on-read everywhere else. *(KD4)*
- **OUT — a general event-sourcing rewrite.** The append-only-log + rebuildable-index substrate already
  exists; this is one hook pair on top, not a re-architecture.

## Dependencies / assumptions (confirmed, not assumed)

- `PreCompact` hook exists (matchers `auto`/`manual`), is **write-only** (no context injection) —
  **confirmed** via the Claude Code hooks reference.
- `SessionStart` fires with `source: "compact"`; its `additionalContext` injects post-compaction and is
  **capped at 10,000 chars** — **confirmed**.
- saga already emits SessionStart `additionalContext` (`stale_main_session_hook.py:235-244`) — verified.
- The DAG frontier is derived-on-read and must be frozen at the boundary
  (`outcome_projection.py:72`, `outcome_spec.py:531`, `outcome.py:333`) — verified.
- The saga cache is git-ignored; the spore lives there as a cache/anchor — verified
  (`saga.py:9-20`, resume `SKILL.md:36-51`).

## Outstanding questions (deferred to /plan)

1. **10k prioritization/truncation policy** — exact ordering (frontier → open leaves → last-N verdicts
   → pointer) and how `N` adapts to campaign size. The seed's "too thin can't rebuild / too fat
   expensive" tradeoff, now hard-bounded by 10k.
2. **Spore path + naming + the match guard** — per active saga vs per project; how SessionStart
   resolves "the active saga" for the current cwd; the worktree-safe stable location (KD6).
3. **Also write a final saga tick at PreCompact?** — keeps durable state current vs spore-only; weigh
   against the worktree-write caveat (a tick into a vanishing worktree is the failure mode KD6 guards).
4. **Multi-saga disambiguation** — which saga is "active" when several exist in one repo/session.
5. **Manual vs auto** — confirm the operator wants `manual` `/compact` to spore too (assumed yes via
   matcher `manual`), or auto-only.

## Sources

- Survivor framing: `docs/ideation/2026-06-26-vecu-port-seeds-ideation.md:163-184` (frame 3) +
  the REWORK critique at `:376` ("structured durable facts … never a prose CoT summary").
- Baseline (already-durable) facts: `saga.py:870-925` (`restore`/`read_ticks`/`_scan_legacy` legacy
  fallback), `saga.py:9-20` (storage + derived index), resume `SKILL.md:36-51`/`:84-238`,
  `drive-and-resume.md:103-126` (anchor-not-authority).
- The gap: `hooks.json:3-45` (no PreCompact registered), `outcome_projection.py:37-83` (frontier
  derived-on-read, never persisted), `outcome_spec.py:531-544`, `outcome.py:333-359`.
- Injection substrate: `stale_main_session_hook.py:181-245` (SessionStart `additionalContext` shape).
- Hook mechanics (confirmed via Claude Code hooks reference, code.claude.com/docs/en/hooks.md):
  PreCompact exists (auto/manual), write-only / `decision`-block-only; SessionStart `source=compact`
  injects `additionalContext`; 10,000-char cap.
- Schema fields available to the spore: `saga.py:138-225`; saga-spec `references/saga-spec.md:104-159`.
