---
title: Typed artifact-pointer passing for team-execution — build to PR-ready
type: work-session
status: pr-ready
date: 2026-07-02
issue: infiquetra/infiquetra-claude-plugins#291
plan: docs/plans/2026-07-02-typed-artifact-pointer-passing-plan.md
branch: feat/291-typed-artifact-pointers
reviewed_sha: 4538002e6f6388e43fed03db4a421bd4e2ffb50e
---

# Typed artifact-pointer passing (#291)

Instead of inlining large artifacts (diffs, changed files, generated outputs) into spawned-agent
prompts, the orchestrator passes a **typed pointer** (a git object ref, or path + sha256 + freshness
epoch) that a capable receiver dereferences itself. 3-layer stack: L1 git-object diff pointers
(temp-index tree snapshot), L2 content-addressed store, L3 light path+symbol pointers. Receivers
verify integrity AND freshness; v1 receivers always dereference the FULL artifact (review invariance).

## What was built (by unit)

| Unit | Commit | Tier | Summary |
|------|--------|------|---------|
| U1 | `b4084cf` | opus | Pointer contract (`ArtifactPointer` dataclass, typed errors) + L1 temp-index tree snapshot |
| — | `232ac9a` | — | Plan + readiness review + KTD journal entry |
| U2 | `83a3d64` | sonnet | Spawn templates pass pointers; receiver contract (`artifact-pointers.md`) |
| U3 | `834a84b` | sonnet | L2 content-addressed store + TTL gc |
| sec | `887f769` | opus | Confine L2 deref to hash-derived CAS path (path-traversal + hash-oracle fix) |
| U4 | `bc9a5b2` | opus | Saga `artifact_pointers` envelope field + R11 e2e proof |
| U5 | `c99a643` | haiku | L3 light path+symbol pointer form (formal resolver deferred) |
| U6 | `1d967e4` | sonnet | Release surfaces: team-execution 2.8.0, saga 0.49.0, marketplace, changelogs, drift guards |

## Consensus-gate remediation (3 cycles, 5 reviewers, all opus)

The team-execution 5-reviewer consensus (devils-advocate, security, architecture, testing,
ai-usefulness) ran three cycles. It caught three defects the green 1792-test build had shipped:

- **Security P1 (arbitrary-file-write)** — L1 `_deref_argv` parsed a free-form `deref` string into git
  argv; a tampered `git diff --output=<path> ...` was an arbitrary write. Fixed (`1c1cafc`): promoted
  the base tree to a validated first-class `base` field; argv is rebuilt deterministically from
  hex-validated OIDs; the `deref` string is display-only.
- **R9 gc leak (found at two depths)** — `git gc` packs custom-namespace refs (loose-file-mtime gc went
  blind), so the fix switched to the reflog. But `git gc`'s internal `reflog expire` resets the reflog
  FILE mtime, so cycle 2 corrected it again to the reflog ENTRY timestamp (`4538002`), which survives
  both packing and expire. Verified against a real `git gc`.
- **Dead-wiring (KTD5)** — the saga `artifact_pointers` field was producer-only; the e2e test masked the
  gap by reusing the in-memory producer output. Fixed (`79a49ea`): `/resume` now derefs a restored
  tick's pointers, and the e2e test crosses the persistence boundary (`saga.py restore` → deref).

Remediation commits: `1c1cafc` (code hardening + 9 tests), `79a49ea` (consumer + e2e), `b5bf68f`
(docs/journal), `4538002` (cycle-2: gc entry-timestamp + `base` propagation to consensus-protocol
templates + security P3 hardening + architecture P3 doc fixes).

Final scores (all ≥9.0): security 9.3 · architecture 9.4 · testing 9.2 · ai-usefulness 9.4 ·
devils-advocate 9.3.

## Gate results

- **Consensus:** MET — all 5 reviewers ≥9.0, no dimension <7.0, security dimension 9.5.
- **Security-scanner validator:** PASS — bandit -ll clean on changed code, no secrets, nosec honest.
- **/code-review (merge-safety):** SAFE_TO_MERGE — REVIEWED_SHA `4538002` — P0:0 P1:0 P2:0 P3:0. All 8
  merge-safety claims upheld, independently reproduced in an isolated worktree.
- **CI parity (primary tree):** ruff clean · ruff format clean (185 files) · mypy clean (116 sources) ·
  bandit clean · **`uv run pytest` → 1795 passed**.

## Key decisions & learnings (journaled)

- DECISIONS `{#artifact-pointer-ktds-291}` — KTD1/4/5/6/7, rejected alternatives, cycle-1/2 remediation,
  team-execution now a hybrid plugin, revisit-when conditions.
- LEARNINGS `{#git-gc-packs-custom-refs-291}` — git metadata durability layers: loose ref (packed
  away) → reflog file mtime (reset by expire) → reflog entry timestamp (durable). Test against a real
  `git gc`.
- LEARNINGS `{#test-shape-masks-dead-wiring-291}` — a round-trip test only proves the round-trip if the
  consumer reads from the boundary it claims to validate, not the producer's in-memory return value.

## Notes / follow-ups

- **Sandbox agent gap:** CLAUDE.md + `sandbox-spawn-sites.md` mandate `saga:readonly-verifier` for
  verify-class spawns, but that agent is not registered in the current roster (definition exists at
  `plugins/saga/agents/readonly-verifier.md`). The code-review gate fell back to `general-purpose` in a
  worktree with read-only instructions. Worth a follow-up to register the agent or reconcile the docs.
- **Residual gc P3 (non-blocking):** an aggressive `git reflog expire --expire=now` or
  `gc.reflogExpireUnreachable < 7d` empties the reflog body → ref skipped → bounded leak. Defaults
  (90d/30d) exceed the 7d TTL, so the automatic gc path is safe. Documented in DECISIONS revisit-when.
- **base unauthenticated (non-blocking):** the `base` OID is format-validated but not cryptographically
  bound to the snapshot — a tampered persisted pointer could substitute another valid tree (misleading
  but git-object-store-confined diff). Documented in DECISIONS revisit-when.

## Next step

PR-ready. Awaiting operator confirmation to push `feat/291-typed-artifact-pointers` and open the PR
(destination: merge). No PR-open or merge without explicit confirmation.
