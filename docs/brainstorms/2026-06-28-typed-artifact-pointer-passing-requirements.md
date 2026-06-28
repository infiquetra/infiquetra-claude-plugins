---
date: 2026-06-28
topic: typed-artifact-pointer-passing
maturity: requirements-ready
source: docs/ideation/2026-06-26-vecu-port-seeds-ideation.md (survivor R15b — typed artifact-pointer passing, the live half of the R15 SPLIT)
---

# Typed Artifact-Pointer Passing (team-execution)

## Summary

When the team-execution orchestrator hands a large artifact (a diff, a changed file, a generated
output) to a spawned agent, pass a **typed pointer** — a git object reference, a path + content hash,
or a path + symbol reference — instead of inlining the raw text. The orchestrator stops constructing N
redundant inlined copies and keeps its long-running context window lean; the already-capable agent
dereferences the artifact itself.

Delivered as a dependency-ordered stack, lowest-risk-first: **Layer 1** git-object diff pointers (no
new storage) → **Layer 2** a content-addressed store for non-git artifacts → **Layer 3** AST/symbol
pointers (feasibility-gated). In v1 a receiving agent dereferences the **full** artifact; per-lens
scoping (reading only part of it) is a deferred, guarded refinement, because reading less than the
inlined version would have shown can change a review verdict.

## Problem Frame

Today the orchestrator inlines artifacts as raw text into spawn prompts. After workers finish, it
captures a `git diff` and passes it into each reviewer's context
(`plugins/team-execution/skills/team-execution/SKILL.md:297`;
`plugins/team-execution/skills/team-execution/references/consensus-protocol.md:26-31, 149-157`).
Validators get a lighter "relevant changed files or diff summary," not necessarily the full diff
reviewers receive
(`plugins/team-execution/skills/team-execution/references/validator-spawn-quirks.md:9-17`).

The consensus loop spawns three or more reviewers in parallel and re-spawns sub-threshold reviewers
*fresh* each cycle (`consensus-protocol.md:51`), and a freshly spawned subagent "starts with no cache
hits" (`docs/analysis/2026-06-25-claude-cache-and-orchestration-chatgpt-source.md:191`). So the same
large diff is rebuilt and re-sent across N parallel reviewers and again on each re-review cycle. The
spawned agents already inherit all tools (no team-execution agent declares a `tools:` restriction), and
`architecture-reviewer` already self-dereferences (it searches for and reads ADRs) — so inlining a diff
the agent could read itself is redundant work on the orchestrator's most expensive, longest-lived
context.

## Key Decisions

- **KD1 — A pointer is typed: locator plus integrity plus freshness.** Every pointer carries an
  artifact kind, a dereference locator, a content-integrity hash, and a **freshness marker** (an epoch
  or a binding to the current review state). The hash detects byte-drift; the freshness marker detects
  a valid-but-*stale* earlier artifact whose hash still verifies. The receiver checks both before use;
  a failure is a typed error, never a silent review of the wrong or outdated bytes.

- **KD2 — The defensible win is a leaner orchestrator and no redundant inlining; the headline
  payload win is deferred.** Two savings are possible. (a) **Orchestrator-side**: not rebuilding and
  re-sending the diff across N spawns and re-review cycles, and keeping the orchestrator's finite
  context window lean (which matters most in long consensus loops, where window pressure forces
  compaction). (b) **Child-side scoping**: each reviewer reading only its lens's slice. The child-side
  win is *deferred* because it conflicts with review invariance (KD6, R14). The exact magnitude of the
  orchestrator-side win is runtime-dependent — prompt caching offsets the per-turn token cost, and
  whether the host durably retains a spawn's tool-input versus treating it as transient is not verified
  here. v1 is justified by the qualitative redundancy (inlining a readable artifact N times is
  wasteful), and the real magnitude is observed by using it, not asserted as a headline number.

- **KD3 — Small fixed context stays inline (the false-economy boundary).** Plan summary, intended
  outcome, and already-referenced docs (`review-criteria.md`) stay inlined — pointerizing a
  hundred-token blurb costs a dereference round-trip for no saving. Only artifacts above a size/reuse
  threshold are pointerized.

- **KD4 — Deliver as a dependency-ordered stack, not a big bang.** Layer 1 (diff pointers) is the
  foundation; Layer 2 (general artifact store) builds on the same pointer contract; Layer 3 (AST/symbol
  pointers) is the heaviest and is feasibility-gated. Layer 3 can be *light* — a path + symbol name the
  agent resolves with its existing grep/read tools — rather than a formal symbol-resolution backend.
  Each layer ships and stands alone.

- **KD5 — Extend saga's existing pointer storage; do not invent a parallel one.** Saga already stores
  artifact *paths* (`plugins/saga/scripts/saga.py:191-195` — `plan_path`, `work_session_paths`,
  `review_paths`, `qa_paths`); the gap is only that spawned agents never dereference them. Build on
  that envelope, honoring "push the value into the shared canonical artifact the earlier layer already
  reads, never add a back-edge import" (`docs/engineering-journal/DECISIONS.md:80`).

- **KD6 — The receiver contract is explicit, and full-dereference is the v1 default.** An agent that
  receives a pointer must (a) have read capability — verified: agents inherit all tools — (b)
  dereference and verify both the integrity hash and the freshness marker, and (c) in v1 read the
  **full** artifact, so it sees everything the inlined version would have shown. The orchestrator stops
  inlining the pointerized artifact. A tool-restricted agent that cannot dereference falls back to
  inlined content (the degradation path).

## Requirements

### Pointer contract (layer-agnostic)

- R1. A typed artifact pointer carries four things: an artifact **kind** (`diff` | `file` | `symbol`),
  a dereference **locator** (a git object reference | a repo-relative path | a path plus symbol
  reference), an **integrity hash**, and a **freshness marker** (an epoch or current-review-state
  binding).
- R2. A receiving agent dereferences a pointer by reading the located artifact and verifying both the
  integrity hash *and* the freshness marker before using it. A mismatch on either surfaces a typed
  error to the orchestrator rather than proceeding on the wrong or stale artifact.
- R3. Pointerization is conditional on a size/reuse threshold. Artifacts below the threshold (plan
  summary, intended outcome, single-sentence context) stay inlined; artifacts above it are passed by
  pointer. Reviewers (full diff) and validators (diff summary) are distinct producers of the
  pointerized artifact and are configured separately.

### Layer 1 — diff pointers (foundation, no new storage)

- R4. The orchestrator passes the review/validation diff as a **git object reference** instead of
  inlining the diff text into reviewer and validator spawns.
- R5. Each spawned reviewer/validator dereferences and reads the **full** diff itself (v1), so review
  invariance is preserved. Per-lens scoping (reading only the slice a lens cares about) is a deferred
  refinement (see Scope Boundaries) and, when added, must not silently drop context a lens's rubric
  would have flagged.
- R6. Layer 1 introduces **no new artifact storage**: git is the content-addressed store and a git
  object hash is the integrity hash. The exact locator for the *uncommitted* review tree is the
  resolve-before-planning gate Q1.
- R7. On a consensus re-spawn, the orchestrator passes the updated git object reference; reviewers
  re-dereference rather than re-receiving an inlined diff.

### Layer 2 — general artifact store (non-git payloads)

- R8. Artifacts not reconstructible from git (large tool outputs, generated logs, intermediate
  non-committed files) are written once to a content-addressed store and passed by **path + content
  hash + freshness** pointer.
- R9. The store is bounded — stale artifacts are reclaimable so it does not grow without limit. The
  reclamation policy is deferred to `/plan`.
- R10. A receiving agent dereferences a stored artifact by path and verifies it under the R2 contract.
- R11. Layer 2 is accepted only when proven end-to-end through the **real** path: a real producer
  entrypoint writes a stored artifact and a **spawned** consumer reads and verifies it through the
  actual spawn flow — not merely a serialization round-trip. (This clears the dead-wiring bar at
  `docs/engineering-journal/LEARNINGS.md:126-136`.)

### Layer 3 — AST/symbol pointers (feasibility-gated)

- R12. Where an agent needs only a specific symbol (a function, a class) rather than a whole file, the
  pointer carries a **path plus symbol reference**. The light form passes path + symbol name as text
  and relies on the agent's existing grep/read tools; a formal symbol-resolution backend (LSP, serena)
  is an optional heavier form.
- R13. If a formal resolver is chosen, Layer 3 is gated on a feasibility probe **run under the spawned
  agent's final tool profile** (a parent-session resolver check can falsely pass — the agent, not the
  orchestrator, must be able to resolve the symbol). If the probe fails, Layer 3 stays deferred and
  Layers 1–2 stand alone.

### Composition and safety

- R14. Pointerization never changes *what* an agent reviews — only *how* the bytes arrive. Under the
  v1 full-dereference default (R5, KD6), the same artifact content is **available** to the agent, so
  review verdicts and consensus thresholds are unaffected. Any future scoping refinement must preserve
  this invariant.
- R15. The pointer mechanism composes with the capability-scoped worktree isolation filed as the
  read-only verify profile (#287). Whether an isolated child can resolve the pointer depends on how
  isolation is implemented (linked worktrees share `.git/objects`; separate clones do not) — folded
  into gate Q1.

## Key Flows

### F1 — Diff-pointer review (Layer 1)

- **Trigger:** workers complete (`SKILL.md` Step B1); the orchestrator produces a git object reference
  for the uncommitted review tree instead of capturing an inlined diff.
- The orchestrator spawns each reviewer with the git object reference, the intended outcome, and the
  `review-criteria.md` path — **no inlined diff**.
- Each reviewer dereferences and reads the full diff, verifies the integrity hash and freshness marker,
  scores, and returns its verdict.
- **Re-review:** the orchestrator passes the new git object reference to re-spawned sub-threshold
  reviewers (`consensus-protocol.md:51`); no re-inlining.

### F2 — Stored-artifact dereference (Layer 2)

- **Trigger:** a producing agent emits a large non-git artifact (a tool dump, a generated log).
- The artifact is written once to the content-addressed store; the producer gets back a path + hash +
  freshness marker.
- The pointer travels through the saga envelope (KD5).
- A spawned consuming agent reads the path and verifies it under R2 — exercised end-to-end per R11.

## Acceptance Examples

- AE1. **Covers R3.** When the artifact is a one-sentence intended-outcome statement → it stays
  inlined (below threshold). When it is a two-thousand-line diff → it is passed as a pointer.
- AE2. **Covers R2.** When a reviewer dereferences a diff pointer and either the integrity hash or the
  freshness marker fails to match (the tree moved underneath it) → a typed error is surfaced to the
  orchestrator, not a review of the wrong or stale diff.
- AE3. **Covers R13.** The Layer-3 feasibility probe runs as the spawned reviewer/validator under its
  final tool profile and resolves a known symbol. If that spawned-agent probe fails → Layer 3 stays
  deferred; Layers 1–2 ship and stand alone. A parent-session-only resolver check does not satisfy this.

## Scope Boundaries

**In scope (v1, full survivor — layered):**

- Layer 1 git-object diff pointers (foundation).
- Layer 2 content-addressed store for non-git artifacts, proven end-to-end (R11).
- Layer 3 AST/symbol-level pointers (feasibility-gated, light form preferred).
- The typed-pointer contract (integrity + freshness), the false-economy threshold, and the
  full-dereference receiver contract.

**Deferred for later (not v1):**

- **Per-lens scoping** — the child-side payload saving. Deferred because it conflicts with review
  invariance (R14); revisit only with a guarantee that no rubric-relevant context is silently dropped.
- A **formal LSP/serena symbol-resolution backend** — the light path+symbol-name form is preferred
  first.

**Deferred to `/plan` (HOW, not WHAT):**

- The exact integrity-hash algorithm and freshness-marker representation; the store location, layout,
  and reclamation policy; the numeric size/reuse threshold; and the dirty-tree locator mechanism (Q1).

**Out of scope:**

- R15a context-GC (evicting dead-end paths) — folded into S-1, not here.
- Semantic log compaction (the third R15 fragment) — not pulled forward.
- Worker residency / cache scheduling (S-1, #275) — the residency-side cost attack; this is the
  payload side and is independent.
- Any change to review semantics, scoring rubrics, or consensus thresholds (R14).

## Dependencies / Assumptions

- **Verified:** team-execution agents inherit all tools (no `tools:` key in any agent file under
  `plugins/team-execution/agents/`), so they can read files and run git; `architecture-reviewer`
  already self-dereferences ADRs. A future tool-restricted agent cannot receive pointers and falls back
  to inlined content (KD6).
- **Verified:** reviewers see a **dirty working tree**, not committed changes — `SKILL.md` goes from
  Step B1 (workers finish, capture diff) straight to Step B2 (reviewers score) with no commit between.
  This is why R6 cannot assume a `base..head` SHA range and why Q1 is a real gate.
- **Verified:** saga already stores artifact paths (`saga.py:191-195`) but no spawned agent
  dereferences them — the envelope to extend (KD5) exists; the consumer does not.
- **Unverified (runtime, observed by use):** whether removing inlined diffs durably reduces the
  orchestrator's retained context versus being transient, and the net token magnitude after prompt
  caching. v1 does not rest a headline number on this (KD2).
- **Relationship:** composes with the capability-scoped verify profile (#287, worktree isolation) via
  R15/Q1. Independent of S-1 worker-cache scheduling (#275).

## Outstanding Questions

**Resolve before planning:**

- Q1. **Dirty-tree locator for Layer 1.** Review happens against an uncommitted tree, so the Layer-1
  pointer cannot be a `base..head` SHA range. The chosen locator must cover **staged, unstaged, and
  untracked** changes, **retention** (a bare `git stash create` makes an unreferenced dangling commit
  that git can garbage-collect, and it does not capture untracked files — `--include-untracked` is
  push/save only), and **worktree sharing** (an isolated child resolves the object only if isolation
  uses linked worktrees sharing `.git/objects`, not separate clones). Candidate mechanisms: a pinned
  checkpoint commit, a `git stash create` object plus a holding ref and untracked handling, or a
  one-time entry in the Layer-2 store. This is the first `/plan` task; it determines whether Layer 1
  is truly storage-free and how it composes with #287.

**Deferred to planning (answered during planning or codebase exploration):**

- The numeric size/reuse threshold that triggers pointerization (KD3, R3).
- The integrity-hash algorithm, the freshness-marker representation, and the pointer serialization
  shape (R1).
- The Layer-2 store location, layout, and reclamation policy (R8, R9).
- The Layer-3 symbol form (light text vs formal resolver) and, if formal, the spawned-agent
  feasibility-probe outcome (R12, R13).

## Sources

- `docs/ideation/2026-06-26-vecu-port-seeds-ideation.md:45,396` — survivor R15b framing and the R15
  SPLIT (context-GC → S-1; pointer-passing → live).
- `plugins/team-execution/skills/team-execution/SKILL.md:297`, Step B1 → B2 boundary (dirty-tree
  review).
- `plugins/team-execution/skills/team-execution/references/consensus-protocol.md:26-31, 51, 149-157` —
  reviewer spawn template (inlined diff) and fresh re-spawn of sub-threshold reviewers.
- `plugins/team-execution/skills/team-execution/references/validator-spawn-quirks.md:9-17` — validator
  context package (diff *summary*, distinct from the reviewer full diff).
- `plugins/team-execution/agents/*.md` — agent definitions, none declaring a `tools:` restriction;
  `architecture-reviewer.md` already self-dereferences ADRs; `devils-advocate-reviewer.md:47-50`
  already instructs "Read the git diff or changed files".
- `plugins/saga/scripts/saga.py:191-195` — existing artifact-path storage (the envelope to extend).
- `docs/analysis/2026-06-25-claude-cache-and-orchestration-chatgpt-source.md:191` — a freshly spawned
  subagent starts with no cache hits (grounds KD2's redundant-inlining argument).
- `docs/engineering-journal/DECISIONS.md:80` — "push the value into the shared canonical artifact the
  earlier layer already reads, never add a back-edge import".
- `docs/engineering-journal/LEARNINGS.md:126-136` — dead-wiring rule (a new consumed field needs both
  a real producer and a real spawned consumer) — the bar R11 must clear.
