---
date: 2026-06-27
kind: doc-review
target: docs/brainstorms/2026-06-27-precompact-spore-rehydration-requirements.md
reviewed_revision: working tree (fixes applied on top of commit bcef923)
blocked: false
---

# Readiness Review — PreCompact Spore Rehydration

## Readiness summary

**READY to drive planning.** No `P0` or `P1` findings remain open. The core design — a PreCompact
spore that persists structured saga facts at the compaction boundary and re-injects them via
`SessionStart(source=compact)`, carrying the OutcomeOrchestrator DAG frontier + the single active saga
— survived intact. The review was substantive: it corrected a real self-contradiction in where the
spore lives, grounded two invented abstractions in actual source, made the 10k truncation and the
"structured facts win" claim decision-complete, and added a deadline to the failure story. The
residual deferred items are genuine `/plan` mechanism (the `session_id→saga_id` map, the truncation
byte formula, the timeout value), not unverified assumptions.

The hook mechanics were confirmed *before* the brainstorm (via the Claude Code hooks reference): the
mandatory two-hook split (PreCompact is write-only; `SessionStart(source=compact)` injects
`additionalContext` ≤10k) is load-bearing and verified. This review then ran codex (`gpt-5.5`, xhigh,
read-only with repo access) and agy (`Gemini 3.1 Pro (High)`, hermetic, doc + grounded facts inlined)
as **gated generators under Claude-side verification** — every finding was checked against source or a
live fact before adoption. Claude independently pre-empted the suspected weakest point (active-saga
resolution) by finding `state.json:active_saga_id` already exists; both engines converged on it from
opposite directions (codex from the repo, agy from first principles), and the synthesis —
`session_id`-keyed spores with an `active_saga_id` fallback — is stronger than any single source's fix.
codex's repo access produced the decisive net-new findings; agy contributed the truncation-deadlock and
the LLM-trust-framing; Claude verified the worktree contradiction and declined agy's ROI cut.

## Applied fixes (8)

All edits are evidence-backed (verified source or a confirmed hook fact).

- **Spore home corrected to the git-common-dir (resolves a self-contradiction).** The draft said both
  ".claude/saga cache" (KD3) and "worktree-safe path" (KD6); verified `.claude/saga` is worktree-
  relative (`saga.py:44`) and `outcome_store` uses `git rev-parse --git-common-dir` for a
  worktree-stable home (`outcome_store.py:80-149`). The spore now lives under
  `<git-common-dir>/saga-spores/`. *(codex P1, Claude-verified)*
- **Spore keyed by `session_id`.** Stable across in-session compaction, so concurrent sessions don't
  collide and SessionStart reads its own spore. *(agy P1 + codex P1)*
- **Active-saga resolution made concrete.** `session_id→saga_id` map with `state.json:active_saga_id`
  (`saga.py:818`) fallback; spore carries `saga_id`+repo-root for mismatch-skip; same-cwd concurrency
  named as a known limitation. *(codex P1 + agy P0→P1; Claude downgraded severity — the mechanism
  exists)*
- **"Gate verdicts" grounded in real fields.** Replaced the invented object with
  `{leaf_id, state, gated, halted, degraded, last_completion_event_ref}` (`outcome.py:571/580/603`).
  *(codex P2)*
- **Outcome-spec discovery specified.** The saga→spore contract carries a typed `outcome_id`/spec path;
  codex CHECK-3 VERIFIED the frontier is loadable once `outcome_id` is known. *(codex P2)*
- **10k truncation made deterministic.** Fixed byte budget; inline `{ids, state, ready frontier, saga
  box}` first as the never-dropped resumable core; drop evidence/waiting-leaf detail before the
  frontier; log the drop. *(agy P1 + codex P1)*
- **Self-describing authority block.** The injected block leads with an explicit conflict instruction
  and carries provenance (`generated_at`, `saga_id`, spec revision, tick path, refs), making
  "structured facts win" enforceable while reconciling newer in-flight work (not regressing).
  *(codex P2 + agy P1/P2)*
- **Bounded-time degrade + crash-safe unlink.** R12 now covers slowness (a hard timeout skips the spore
  rather than stalling compaction); R8 unlinks before emit. *(agy P2 + P3)*

## Findings by priority

| Pri | Finding | Source | Status |
|-----|---------|--------|--------|
| P1 | Spore home contradicts worktree safety (`.claude/saga` is worktree-relative) | codex | Fixed (git-common-dir) |
| P1 | Active-saga matching is repo-global, not session-safe | codex + agy + claude | Fixed (session_id key + map) |
| P1 | `SessionStart(compact)` path not wired; hook reads `cwd` not `source` | codex | Fixed (R7 wiring) |
| P1 | 10k truncation could drop the ready frontier → campaign deadlock | agy + codex | Fixed (frontier never dropped) |
| P1 | "structured facts win" unenforceable without framing | agy + codex | Fixed (self-describing block) |
| P2 | "gate verdicts" is not a defined source object | codex | Fixed (grounded fields) |
| P2 | Outcome-spec discovery implicit | codex | Fixed (typed `outcome_id`) |
| P2 | Spore lags unpersisted in-flight work | agy | Fixed (reconcile-don't-regress) |
| P2 | Derivation could stall (hang) the compaction | agy | Fixed (R12 timeout) |
| P3 | Consume-and-reset double-inject window | agy | Fixed (unlink-before-emit) |
| P3 | Restrict to campaigns on ROI grounds | agy | Declined (operator chose single-saga; ~0 cost) |
| — | CHECK-1/3/6 (no PreCompact, frontier loadable, no dead-wiring) | codex | Verified |

## Residual risk from limited evidence

Low-to-moderate. The mechanism rests on confirmed hook behavior and verified storage facts (git-common-
dir, `active_saga_id`, loadable frontier). The genuine sizing risk is concentrated in two `/plan`
mechanisms: the `session_id→saga_id` map (how `session_id` reaches saga's save path — the hooks have it
on stdin, the save commands do not today) and the deterministic 10k truncation formula for very wide
campaigns. Both are located and scoped, not hidden. The same-working-directory concurrent-session case
is an acknowledged limitation rather than a silent failure (the spore self-identifies its `saga_id` for
mismatch-skip).

## Scope observation (operator's call, not a blocker)

The build surface is two hooks plus a small serializer/loader — modest. The one place a reviewer could
still push is whether v1 should also write a final saga tick at PreCompact (Outstanding Q4): it keeps
durable state maximally current but re-introduces the very worktree-path hazard KD3 just fixed, so it is
correctly deferred. The single-saga inclusion (vs campaign-only) is a confirmed operator decision with
~zero marginal cost; no reduction is required for readiness.
