---
date: 2026-06-28
target: docs/brainstorms/2026-06-28-typed-artifact-pointer-passing-requirements.md
reviewed_revision: working tree
review_type: requirements readiness (saga /doc-review)
verdict: READY
blocked: false
---

# Readiness Review — Typed Artifact-Pointer Passing

## Verdict

**READY for `/plan`** after a heavy reframe. The draft over-claimed the economics: it presented
per-lens scoping (each reviewer reading only its slice) as a headline saving while also guaranteeing
review invariance — and those two cannot both hold. A full three-engine adversarial panel plus a
pre-registered Claude-side critique converged on this as the top defect, and codex's repo access showed
it combines with a second one (the orchestrator-side saving is runtime-unverified) into a single bind:
the draft's economic case rested on **either an unsafe mechanism (scoping) or an unverified one (parent
retention)**. Ten evidence-backed fixes were applied in place. The fix does not shrink the operator's
chosen scope — all three layers remain — it makes v1 default to **full dereference** (preserving
invariance), defers per-lens scoping as a guarded refinement, and restates the economic claim honestly
without adding the ROI ceremony this codebase rejects. No `P0` remains.

## Method

Three external engines ran as gated generators under Claude-side verification; every finding was
checked against the document or repo source before adoption. agy was back in service this pass (the R6
review had run codex-only during an agy outage), so the full cross-family panel ran:

- **Codex / gpt-5.5** at `xhigh`, read-only, repo access — verified `file:line` citations directly,
  surfaced the load-bearing combination (P0 invariance + P1 unverified carry-cost), and checked the
  `git stash create` semantics against the git man page.
- **agy / Gemini 3.1 Pro** and **agy / Gemini 3.5 Flash**, hermetic (doc inlined, no repo access) —
  challenged design logic and scope; both independently raised the R5/R14 contradiction and the
  stale-but-valid-hash gap, and both judged Layer 3 over-built.
- **Claude-side pre-registered critique** — four findings predicted before the engines returned (the
  R5↔R14 tension, the KD2 imprecision, the per-lens behavioral assumption, the worktree-composition
  question). The first three matched engine findings, raising confidence they are real and not
  single-model artifacts.

**Routing footnote (honest record).** This session's codex calls ran **bare** (direct to OpenAI),
bypassing the Headroom proxy, because of a mis-invocation on my part — I called `codex exec` instead of
`headroom wrap codex exec`, and separately mis-probed the proxy at `127.0.0.1` when it runs on the LAN
IP. The proxy was healthy throughout. The operator chose to let the in-flight run stand and wrap future
external-engine calls. Routing does not affect codex's output correctness; its findings were all
repo-fact and independently verified.

## Applied fixes

All evidence-backed; the document was edited in place.

| # | Fix | Source | Evidence |
|---|---|---|---|
| 1 | R5/R14 contradiction resolved: v1 defaults to **full** dereference (invariance preserved); per-lens scoping deferred as a guarded refinement | Codex P0 + agy-Pro P0 + agy-Flash P1 + Claude (pre-registered) | a content hash proves fetched bytes, not that a scoped reviewer saw the full artifact (doc R5 vs R14) |
| 2 | KD2 reframed: orchestrator-side leanness + no-redundant-inlining is the defensible win; carry-cost magnitude marked runtime-dependent (caching offsets; observed by use, not asserted) | Codex P1 + agy-Pro P3 + Claude (pre-registered) | a spawned subagent "starts with no cache hits" (`docs/analysis/2026-06-25-claude-cache-and-orchestration-chatgpt-source.md:191`) |
| 3 | Q1 expanded: dirty-tree locator must cover staged/unstaged/**untracked**, **retention** (dangling unreffed commit is GC-able), and **worktree sharing** | Codex P1 (verified vs git man page) | `git stash create` makes an unreferenced commit; `--include-untracked` is push/save only |
| 4 | Layer 2 anti-dead-wiring: new R11 requires end-to-end proof through a real producer entrypoint and a real **spawned** consumer | Codex P1 | `saga.py:191-195` has path fields; `LEARNINGS.md:126-136` dead-wiring rule |
| 5 | Pointer contract gains a **freshness marker** (epoch / state binding), not just a content hash | agy-Pro P1 + agy-Flash P0 | a valid-but-stale artifact can pass content-hash verification (doc R1, R2) |
| 6 | Layer 3 feasibility probe must run **under the spawned agent's tool profile**, not the parent session | Codex P2 + agy-Flash P2 | a parent-session LSP/serena check can falsely pass (doc AE3, R13) |
| 7 | Reviewer (full diff) vs validator (diff *summary*) split, not conflated | Codex P2 | `validator-spawn-quirks.md:9-17` says "relevant changed files or diff summary" |
| 8 | Layer 3 lightened: path + symbol name as text (agent greps) preferred over a formal LSP/serena backend; kept in scope per operator choice | agy-Pro P2 + agy-Flash P2 | both engines judged a formal resolver over-built for the saving |
| 9 | KD6 degradation path made explicit (tool-restricted agent falls back to inlined content) | agy-Flash P2 | doc KD6 lacked the capability fallback |
| 10 | Stale agent count "26" removed (registry enumerates 25; the load-bearing fact is "no `tools:` restriction") | Codex P3 | 25 agent files; `reviewer-registry.md` + `validator-registry.md` |

## Findings by priority (post-fix status)

| Priority | Finding | Engine(s) | Status |
|---|---|---|---|
| P0 | Per-lens scoping (R5) contradicts review-invariance (R14) | Codex + agy-Pro + agy-Flash + Claude | Fixed (full-dereference default; scoping deferred) |
| P1 | Orchestrator carry-cost (KD2) is runtime-unverified | Codex + agy-Pro + Claude | Fixed (honest reframe; no ROI gate) |
| P1 | Q1 `git stash create` locator incomplete (untracked / retention / worktree) | Codex (+ agy-Pro, agy-Flash variants) | Fixed (Q1 enumerates what it must cover) |
| P1 | Layer 2 dead-wiring risk | Codex | Fixed (R11 end-to-end acceptance) |
| P1 | Content hash detects drift but not staleness | agy-Pro + agy-Flash | Fixed (freshness marker in R1/R2) |
| P2 | Layer 3 feasibility probe could false-pass at parent level | Codex + agy-Flash | Fixed (spawned-agent probe) |
| P2 | Reviewer/validator inlining conflated | Codex | Fixed (split) |
| P2 | Layer 3 over-built | agy-Pro + agy-Flash | Addressed (lightened, kept per operator scope) |
| P2 | KD6 capability fallback unstated | agy-Flash | Fixed (degradation path) |
| P3 | Agent-count citation stale (26 vs 25) | Codex | Fixed (count removed) |

## Residual risk

- **The economics are more modest than the draft implied, and partly runtime-dependent.** With per-lens
  scoping deferred, v1's win is orchestrator-side (leaner context window, no redundant inlining); its
  token magnitude depends on host retention and caching and is best observed by use, not asserted. This
  is recorded honestly rather than gated behind a measurement ceremony — but the operator should expect
  a real-but-bounded win, not a large headline saving, until scoping can be added safely.
- **Q1 is genuinely unresolved.** The dirty-tree + worktree-sharing locator is the first `/plan` task,
  not a formality; if no locator cleanly covers untracked files, retention, and isolated children, the
  Layer-1 "no new storage" property weakens toward the Layer-2 store.
- **Per-lens scoping may never be safely addable.** If dropping any context risks a missed cross-file
  concern, the deferred child-side win stays deferred permanently.
- **Layer 3 kept against two-engine advice.** Both agy engines judged a formal symbol resolver
  over-built; the operator deliberately chose the full survivor. Layer 3 is retained but lightened and
  feasibility-gated, so the heavy form is never built on assumption.
- **Single-routing note.** codex ran outside Headroom this pass (see Method); output integrity is
  unaffected, but Headroom accounting for this run was not captured.

## Next step

Hand off to `mission-control` as a `capability` issue on the operations board (objective
`improve-claude-plugins`), same pipeline as S-1 (#275) … R6 (#289). Recipient action: `/plan`, whose
first task is the Q1 dirty-tree locator gate, then the size/reuse threshold and the pointer
serialization. Build Layer 1 first; Layer 2 and Layer 3 follow with their own gates.
