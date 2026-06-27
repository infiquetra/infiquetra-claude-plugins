---
title: capability: infiquetra-claude-plugins campps work
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
---

# capability: infiquetra-claude-plugins campps work

---
date: 2026-06-27
kind: brainstorm
maturity: requirements-ready
type: capability
source: docs/ideation/2026-06-26-vecu-port-seeds-ideation.md — survivor S-3 (PreCompact spore rehydration)
title: "PreCompact Spore — Re-ground the Continuing Session on Structured Saga Facts, Not Prose"
---

# PreCompact Spore — Re-ground the Continuing Session on Structured Facts, Not Prose

### Objective

Board objective: **improve-claude-plugins**. S-3 of the VECU port-seeds campaign (tier ③, last). Guards
the **mid-run auto-compaction boundary** so long `/work`, `/loop`, and especially `/outcome` campaigns
re-ground on **structured saga facts** instead of the harness prose summary. Corrects the survivor's
premise: saga already rehydrates durably on the explicit `/resume` path; the unguarded gap is the
*implicit* compaction where the same session keeps running on a lossy summary.

### Intent

Add a `PreCompact` hook that writes a thin **structured spore** (OutcomeOrchestrator DAG frontier +
single active saga, frozen at the boundary) to the **git-common-dir** cache keyed by `session_id`, and
a `SessionStart(source=compact)` hook that re-injects it (≤10k, self-describing, authority-framed) so
the continuing session re-grounds on facts, not prose. Mandatory two-hook split (PreCompact is
write-only; SessionStart injects).

### Out-of-scope / non-goals

- The existing `/resume` path — already durable; untouched.
- Replacing the harness summary — impossible (already in-context); the spore **augments** only.
- Persisting the frontier into canonical `outcome-spec.json` — the spore is a boundary cache.
- A general event-sourcing rewrite — the append-only-log substrate already exists.
- Restricting the spore to `/outcome` campaigns on ROI grounds — operator chose to include single-saga;
  marginal cost ~zero.

### Files expected to change

- `plugins/saga/hooks/hooks.json` — register `PreCompact` (matchers `auto`+`manual`); wire the
  `SessionStart` `compact` path.
- `plugins/saga/hooks/precompact_spore_hook.py` — **new**: resolves the active saga, discovers the
  outcome spec, freezes the frontier under a timeout, serializes the spore to
  `<git-common-dir>/saga-spores/<session_id>.json`.
- SessionStart spore reader — extend `stale_main_session_hook.py` (parse `source`/`session_id`/`cwd`)
  or a new compact-only entry: read + unlink + emit the self-describing `additionalContext`.
- `plugins/saga/scripts/` — a spore serializer/loader (frontier freeze via the `outcome_*` modules).
- `tests/test_precompact_spore.py` — **new** (repo-root, CI-collected).
- Release surfaces: `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
  `plugins/saga/CHANGELOG.md`.

### Tests to add or update

The R13 seam round-trip + negatives: write a spore from a synthetic saga+outcome (incl. an over-budget
campaign), assert `SessionStart(compact)` emits a **≤10k** self-describing block with the **ready
frontier never dropped**; assert a mismatched-`session_id` spore is **not** injected and is unlinked
before emit; assert a PreCompact failure or timeout **skips** the spore without blocking compaction;
assert the git-common-dir path is readable **after a worktree is removed**.

### Context library links

- `docs/brainstorms/2026-06-27-precompact-spore-rehydration-requirements.md` — this requirements doc.
- `docs/reviews/2026-06-27-precompact-spore-rehydration-readiness.md` — gated codex+agy review.
- `docs/ideation/2026-06-26-vecu-port-seeds-ideation.md:163-184` + critique `:376` — survivor S-3.

### Acceptance criteria

- [ ] `uv run pytest tests/test_precompact_spore.py` is green (round-trip + all negatives).
- [ ] The PreCompact hook writes `<git-common-dir>/saga-spores/<session_id>.json` carrying the DAG
  frontier + saga box, frozen at the boundary, ≤10,000 chars.
- [ ] `SessionStart(source=compact)` injects the self-describing spore block; the ready frontier is
  present and the block leads with the authority/conflict instruction.
- [ ] A stale or mismatched-`session_id` spore is **not** injected; the spore is unlinked before emit.
- [ ] A PreCompact failure or timeout skips the spore; compaction is never blocked or stalled.
- [ ] The spore survives a worktree removal (git-common-dir, not `.claude/saga`).

### Verification

```bash
uv run pytest tests/test_precompact_spore.py -v   # round-trip + negatives
uv run pytest                                      # full suite
uv run ruff check . && uv run ruff format --check .
uv run mypy plugins/ && uv run bandit -r plugins/
```

Manual: run a long `/outcome` session to an auto-compaction and confirm the post-compaction context
contains the structured frontier block (provenance + ready leaves), not only the harness prose.

## Summary

When a long continuous session (a `/work`, `/loop`, or especially an `/outcome` campaign) fills the
context window, the harness **auto-compacts**: it replaces the conversation with a prose summary and
the **same session keeps running**. Structured saga facts the run depends on — open leaf ids, the
ready frontier, per-leaf gate state, `saga_id`, `next_step` — get blurred into that prose or dropped.
The session continues, but fuzzy about *where it is*.

The fix is a **"spore"**: at the compaction boundary, saga writes a thin **structured** snapshot of
those facts to a worktree-stable, session-keyed cache, and immediately after compaction re-injects
them into the continuing session so it re-grounds on facts, not prose. This is the survivor's
load-bearing critique made literal — *rehydrate from structured durable facts, never a prose CoT
summary*.

**Grounding correction (verified this session).** The survivor's framing — "saga has no durable
rehydration; `load_state` should prefer the spore over the harness summary" — is **wrong about the
baseline**. Saga *already* rehydrates durably on the **explicit `/resume` path**: append-only
immutable ticks (each a full snapshot), a derived/rebuildable `state.json`, and `/resume` reconstructs
from the whole tick chain + committed `docs/*` + GitHub, with an explicit authority model ("committed
docs + GitHub are authoritative; the `.claude/saga/` cache is the *anchor, not the authority*"). There
is no `load_state` function. The real, unguarded gap is narrower: the **mid-run auto-compaction
boundary**, where the *same* session continues on the harness prose summary without ever calling
`/resume`. The spore guards exactly that boundary — it **augments** the post-compaction window with
authoritative structured facts; it does not (and cannot) replace the harness summary.

**Operator scope (this brainstorm):** the spore carries the **OutcomeOrchestrator DAG frontier + the
single active saga** (Q1=A), and uses **persist + re-inject** (Q2=A).

> **Doc-review note (codex + agy, gated under Claude-side verification).** The core design survived;
> the review hardened five things, each verified against source: (1) the spore home was self-
> contradictory — `.claude/saga` is **worktree-relative** (`saga.py:44`) and would vanish, so it moves
> to the **git-common-dir** cache like `outcome_store` (`outcome_store.py:80-149`, "same path from
> every worktree"); (2) the spore is **keyed by `session_id`** (stable across in-session compaction),
> resolving isolation + matching; (3) "gate verdicts" was an invented object — it is now grounded in
> the real per-leaf fields (`state`/`gated`/`halted`/`degraded` + completion-event ref); (4) the 10k
> truncation policy is now deterministic with the ready frontier as the never-dropped core; (5) the
> injected block is **self-describing** (provenance + explicit conflict instruction) so "structured
> facts win" is enforceable, while still reconciling newer in-flight work. agy's "restrict to
> campaigns only on ROI grounds" was **declined** (operator chose to include single-saga; marginal
> cost is ~zero; ROI-gating a solo tool isn't the bar).

## Problem frame

- **Where it bites hardest:** long `/outcome` campaigns that eat *multiple* compactions. The
  OutcomeOrchestrator's frontier (open leaf ids, ready set, per-leaf gate state) is **computed
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
    `additionalContext` today (`stale_main_session_hook.py:235-244`), though that hook reads only
    `cwd`, not `source` — the compact branch + full-payload parse are net-new wiring.

## Key decisions

- **KD1 — The spore is a thin STRUCTURED index, never prose or a log re-dump.** This is the survivor's
  central critique and is now a *hard constraint*: the 10k `additionalContext` cap enforces thinness
  by construction. The spore carries enumerated facts + pointers to canonical artifacts, not narrative.
- **KD2 — Two-hook split is mandatory (not a design choice).** PreCompact cannot inject (confirmed);
  it only persists. The re-injection MUST come from `SessionStart(source=compact)`. A spore write with
  no reader would be dead-wiring — both ends are in scope (codex CHECK-6 VERIFIED both present).
- **KD3 — The spore lives in the git-common-dir cache; it AUGMENTS, anchor-not-authority.** It is
  written under `<git-common-dir>/saga-spores/` (the worktree-stable location `outcome_store` already
  uses for `saga-outcomes/`, resolved via `git rev-parse --git-common-dir` — `outcome_store.py:93-149`),
  **not** `.claude/saga` (which is worktree-relative — `saga.py:44` — and would vanish under a removed
  worktree). It adds authoritative structured facts beside the harness summary (it cannot replace the
  summary — that's already in-context). On conflict about a *durable* fact, structured facts +
  committed docs + GitHub win, per the existing `/resume` precedence.
- **KD4 — The frontier must be computed-and-frozen at the boundary, from a discoverable spec.** Because
  it is derived-on-read and never persisted, the PreCompact hook computes the live frontier
  (`ready_frontier(spec, completed)`) at compaction and serializes the result. This requires the
  saga→spore contract to carry a typed `outcome_id` / spec path so the hook can *find* the spec; codex
  CHECK-3 VERIFIED the frontier is loadable from disk once `outcome_id` is known
  (`outcome.py:128/137`, `outcome_spec.py:424`, `outcome_store.py:148`).
- **KD5 — Session-keyed; consume-and-reset; resolve the active saga.** The spore is keyed by
  `session_id` (stable across in-session compaction), so concurrent sessions never collide and
  SessionStart reads *its own* session's spore. *Which* saga's facts go in the spore is resolved by a
  `session_id → saga_id` map (written by saga commands) with `state.json:active_saga_id` (`saga.py:818`,
  per-repo last-written) as fallback. The SessionStart hook unlinks the spore **immediately before**
  emitting `additionalContext`, so a crash can't double-inject.
- **KD6 — The injected block is self-describing and enforces its own authority.** It leads with an
  explicit instruction ("the preceding prose summary is lossy; the following structured facts are
  authoritative on conflict about durable state — but reconcile any newer in-flight progress from the
  summary; do not regress") and carries provenance: `generated_at`, `saga_id`, spec revision, the
  source tick path, and the canonical doc/issue refs. This makes KD3's "structured facts win"
  *enforceable* rather than hopeful, while preventing the agent from discarding newer unpersisted work.
- **KD7 — Never block or stall compaction; degrade silently AND on a deadline.** A spore failure
  (can't compute frontier, can't write) lets compaction proceed — exit 0, no `decision: block`, no
  raise. The PreCompact computation also runs under a hard wall-clock timeout; if exceeded it skips the
  spore rather than stalling the compaction the user is waiting on.

## Actors

- **A1 — PreCompact hook (net-new).** Fires at the boundary (auto + manual). Resolves the active saga
  (KD5), discovers the outcome spec (KD4), computes-and-freezes the DAG frontier + single-saga box
  under a timeout (KD7), serializes a ≤10k structured spore to `<git-common-dir>/saga-spores/
  <session_id>.json` (KD3). Write-only; silent/bounded on failure.
- **A2 — SessionStart(source=compact) hook (extends existing pattern).** Parses the full payload
  (`source`, `session_id`, `cwd`), reads the matching `<session_id>` spore, unlinks it, then emits it
  as a self-describing `additionalContext` block (KD6). Reuses the `hookSpecificOutput`/
  `additionalContext` shape already in `stale_main_session_hook.py:235-244`; needs the `compact`
  matcher wired in `hooks.json`.
- **A3 — The continuing session (consumer).** Receives the structured facts at the top of the
  post-compaction window and re-grounds: which leaves are open, what's ready, each leaf's gate state,
  the current saga's phase/next_step — trusting them over conflicting prose, reconciling newer work.

## Requirements

**Spore content — the structured spine (Q1=A):**
- **R1** — The spore is structured facts (keyed fields), not prose and not a re-dump of the tick log.
- **R2** — It carries the **single active saga** box: `saga_id`, `lifecycle_phase`, `phase_status`,
  `status`, `next_step`, `blockers`, `open_questions`, last `checks_run`. *(fields exist —
  `saga.py:138-225`)*
- **R3** — It carries the **OutcomeOrchestrator DAG**, computed-and-frozen at PreCompact (KD4): open
  leaf ids, the ready frontier, and a per-leaf **state object grounded in real fields** —
  `{leaf_id, state, gated, halted, degraded, last_completion_event_ref}` (`outcome.py:571/580/603`),
  **not** an invented "verdict." Spec discovery is via a typed `outcome_id`/spec-path in the contract.
- **R4** — It carries **pointers** to canonical artifacts (outcome-spec path, issue refs, plan/work
  doc paths, the source tick path), not their contents. *(authority stays in committed docs + GitHub)*
- **R5** — The serialized spore fits **10,000 chars** via a **deterministic** policy: a fixed byte
  budget with ordering — inline `{leaf ids, state, ready frontier, saga box}` **first** (the minimal
  resumable core, **never** dropped); then bounded per-leaf state refs; drop free-form/evidence blobs
  and waiting-leaf detail **before** ever truncating the ready frontier. Any truncation is **logged**
  (counted pointer, e.g. "+K more leaves — see `<spec>`"), never silent. *(no-silent-caps lesson)*

**The two-hook mechanism (Q2=A):**
- **R6** — A `PreCompact` hook (matchers `auto` **and** `manual`) writes the spore to
  `<git-common-dir>/saga-spores/<session_id>.json` — worktree-stable, session-isolated (KD3/KD5).
  *(saga registers no PreCompact hook today — `hooks.json:3-45`)*
- **R7** — A `SessionStart` path on `source == "compact"` (matcher wired in `hooks.json`; the hook
  parses `source`/`session_id`/`cwd`, which the current hook does not — `stale_main_session_hook.py:76,93`)
  reads the matching spore and emits it as `additionalContext`.
- **R8** — The spore is **unlinked immediately before** emitting `additionalContext` (consume-and-
  reset, crash-safe ordering), so it cannot re-inject on a later compaction. *(KD5; agy P3)*
- **R9** — Injection is **session-keyed** by `<session_id>` (no cross-session leakage). The active-saga
  selection uses the `session_id→saga_id` map with `active_saga_id` fallback; the spore carries
  `saga_id` + repo root so SessionStart can detect and skip a mismatch. **Known limitation:**
  concurrent sessions in the *same* working directory with no session→saga map fall back to per-repo
  last-writer-wins. *(codex P1 + agy P1)*

**Correctness & authority:**
- **R10** — The injected block is **self-describing** (provenance: `generated_at`, `saga_id`, spec
  revision, tick path, canonical refs) and leads with an explicit conflict instruction: structured
  facts are authoritative for **durable** state on conflict, but newer in-flight progress in the
  summary is real — reconcile, do not regress. *(KD6; codex P2 + agy P1/P2)*
- **R11** — Nothing on the existing `/resume` path or the tick/`state.json` model changes; the spore is
  additive cache. The spore is the anchor, never the authority. *(don't touch what already works)*

**Robustness:**
- **R12** — Both hooks **degrade silently AND on a deadline**: any failure → compaction proceeds /
  session continues (exit 0, no block, no raise); the PreCompact frontier computation runs under a hard
  wall-clock timeout and skips the spore if exceeded, so it never stalls the compaction. *(KD7; agy P2)*
- **R13** — The PreCompact write and the SessionStart read agree on path/format and are covered by a
  round-trip test: write a spore from a synthetic saga+outcome (incl. an over-budget campaign), assert
  SessionStart emits the expected self-describing `additionalContext` within 10k, and assert a
  mismatched-session spore is **not** injected. *(components-present ≠ end-to-end — test the seam)*

## Key flows

- **F1 — Auto-compaction during an `/outcome` campaign.** Window fills → `PreCompact(auto)` resolves
  the active saga, discovers the spec, computes the frontier (U9,U10 ready; U8 gated→state; U11
  waiting) + the coordinator saga box under timeout, writes `saga-spores/<session_id>.json` → harness
  compacts → `SessionStart(source=compact)` reads + unlinks + injects the self-describing block → the
  continuing session re-grounds and advances the right leaf.
- **F2 — Manual `/compact`.** Same path via matcher `manual`.
- **F3 — Spore failure or timeout.** PreCompact can't resolve the saga / spec, or exceeds the deadline
  → writes nothing; compaction proceeds; SessionStart finds no matching spore and injects nothing.
  Session continues on the prose summary (status quo) — no regression.
- **F4 — Stale / concurrent.** Compaction N's spore is unlinked at N's SessionStart before emit; N+1
  writes a fresh one. Two sessions write `<session_id>`-distinct spores — no collision. *(R8/R9)*

## Acceptance examples

- **AE1** — Given a long `/outcome` session that auto-compacts, the post-compaction context contains an
  injected, self-describing block listing the ready frontier, open leaves, and per-leaf state
  (structured + provenance), not only the harness prose. *(R3/R7/R10)*
- **AE2** — Given a campaign whose full per-leaf detail exceeds 10k, the spore inlines the resumable
  core (ids/state/frontier/saga box), truncates waiting-leaf/evidence detail with a counted pointer,
  stays ≤10k, and logs the drop; the **ready frontier is never dropped**. *(R5)*
- **AE3** — Given a PreCompact error or a frontier computation exceeding the deadline, compaction still
  completes and the session continues; no block, no stall, no traceback. *(R12)*
- **AE4** — Given two consecutive compactions, the second does not re-inject the first's spore; given
  two concurrent sessions, neither reads the other's spore. *(R8/R9)*
- **AE5** — Given a spore fact that conflicts with a merged PR's state, the canonical source wins on
  reconcile; given newer unpersisted progress in the summary, the agent integrates it rather than
  regressing to the spore's persisted floor. *(R10)*
- **AE6** — Given a background/worktree session, the spore is written under the git-common-dir and is
  still readable by the post-compaction SessionStart after the worktree is removed. *(R6/KD3)*

## Scope boundaries

- **IN**: the two-hook spore (PreCompact write + SessionStart(`compact`) re-inject); DAG frontier +
  single-saga content; git-common-dir session-keyed storage; 10k deterministic truncation; self-
  describing authority block; silent+bounded-time degrade; the seam round-trip test.
- **OUT — the existing `/resume` path.** Already durable; not touched. *(R11)*
- **OUT — replacing the harness summary.** Impossible (it's already injected); the spore augments only.
- **OUT — persisting the frontier into the canonical `outcome-spec.json`.** The spore is a boundary
  cache, not a schema change; the frontier stays derived-on-read everywhere else.
- **OUT — a general event-sourcing rewrite.** The append-only-log + rebuildable-index substrate already
  exists; this is one hook pair on top.

### Considered and declined

- **Restricting the spore to `/outcome` campaigns only (agy P3, ROI grounds).** The operator chose to
  include the single-saga case (Q1=A). The marginal cost is ~zero — the hook runs at the boundary
  regardless, and the single-saga box is already computed — so there is no measurement-gate to clear
  here. Declined as scope-narrowing on an ROI basis that doesn't fit a solo tool.

## Dependencies / assumptions (confirmed, not assumed)

- `PreCompact` hook exists (matchers `auto`/`manual`), is **write-only** (no context injection);
  `SessionStart(source=compact)` injects `additionalContext` capped at **10,000 chars** — **confirmed**
  via the Claude Code hooks reference.
- The DAG frontier is loadable from disk once `outcome_id` is known (`outcome.py:128/137`,
  `outcome_spec.py:424`, `outcome_store.py:148`) — codex CHECK-3 VERIFIED.
- The git-common-dir is the worktree-stable cache home (`outcome_store.py:80-149`,
  `git rev-parse --git-common-dir`); `.claude/saga` is worktree-relative (`saga.py:44`) — verified.
- saga already emits SessionStart `additionalContext` (`stale_main_session_hook.py:235-244`), but reads
  only `cwd` today (`:76,93`) — verified.
- `state.json` carries `active_saga_id` + `current_work.saga_id` for mismatch detection
  (`saga.py:794,818`) — verified.

## Outstanding questions (deferred to /plan)

1. **`session_id → saga_id` map** — where saga commands write it, and the exact precedence with the
   `active_saga_id` fallback (and how `session_id` reaches saga's save path).
2. **10k truncation formula** — the fixed byte budget per section and the deterministic `N` for inlined
   per-leaf state vs pointer-only, as campaign width grows.
3. **PreCompact deadline value** — the wall-clock timeout for frontier computation (start near ~1s).
4. **Also write a final saga tick at PreCompact?** — keeps durable state current vs spore-only; the
   tick must go to the git-common-dir-safe path too, not a vanishing worktree (the KD3 hazard).
5. **Manual vs auto** — confirm `manual` `/compact` should also spore (assumed yes), or auto-only.

## Sources

- Survivor framing: `docs/ideation/2026-06-26-vecu-port-seeds-ideation.md:163-184` + the REWORK critique
  at `:376` ("structured durable facts … never a prose CoT summary").
- Baseline (already-durable): `saga.py:870-925` (`restore`/`read_ticks`/`_scan_legacy`), `saga.py:9-20`,
  resume `SKILL.md:36-51`/`:84-238`, `drive-and-resume.md:103-126` (anchor-not-authority).
- The gap: `hooks.json:3-45` (no PreCompact), `outcome_projection.py:37-83` (frontier derived-on-read),
  `outcome_spec.py:531-544`, `outcome.py:333-359`.
- Storage/worktree: `saga.py:44` (`.claude/saga` worktree-relative), `outcome_store.py:80-149`
  (git-common-dir, "same path from every worktree"); `saga.py:794,818` (`active_saga_id`).
- Frontier loadability + verdict fields: `outcome.py:128/137/571/580/603`, `outcome_spec.py:424`,
  `outcome_store.py:148`. *(codex CHECK-3 + P2 VERIFIED)*
- Injection substrate: `stale_main_session_hook.py:76,93,235-245` (reads `cwd`, emits
  SessionStart `additionalContext`).
- Hook mechanics (Claude Code hooks reference, code.claude.com/docs/en/hooks.md): PreCompact
  write-only / `decision`-block-only; SessionStart `source=compact` injects `additionalContext`;
  10,000-char cap.
- Schema fields: `saga.py:138-225`; saga-spec `references/saga-spec.md:104-159`.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: docs/brainstorms/2026-06-27-precompact-spore-rehydration-requirements.md
- Source type: brainstorm
- Source title: PreCompact Spore — Re-ground the Continuing Session on Structured Facts, Not Prose
