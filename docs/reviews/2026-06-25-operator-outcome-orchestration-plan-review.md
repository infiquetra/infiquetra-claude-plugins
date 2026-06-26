---
date: 2026-06-25
kind: doc-review
target: docs/plans/2026-06-25-operator-outcome-orchestration-plan.md
reviewed_revision: working tree (uncommitted)
reviewers: Claude (this session) + Codex gpt-5.5 xhigh + Antigravity Gemini 3.1 Pro High
blocked: false
---

# Doc-Review — Operator Outcome-Orchestration Implementation Plan

**Verdict:** Strong, well-grounded HOW plan. Three independent reviewers (Claude, Codex, Antigravity)
each ran a trust-but-verify adversarial pass over the plan; **all spot-checked the plan's code citations
and confirmed them accurate** (`recompile_for_tier` is a dispatcher at `execution_spec.py:708`, the
downgrade policy is upstream at `lifecycle_state.py:223`, `STATE_DIR` is CWD-relative at `saga.py:44`,
`orchestration_ref` is a string pointer at `saga.py:168`, the release-triad/team-execution asset tests
exist). No P0 was found. The review surfaced **seven P1 and five lower findings** — none architectural,
all "the builder would otherwise have to invent core behavior" — and **all twelve were resolved in the
same session** (see Resolution). The plan is ready to drive `/work`.

## Reviewer provenance

The plan was itself synthesized from three independent plans; the same three engines then reviewed the
synthesis. Convergence was high: the store-durability gap, the release-surface-discipline conflict, and
the R34 offline-conflict gap were each flagged by two or three reviewers independently. Two findings are
notable for the discipline working as intended: Codex **sharpened** the ledger finding into a real
contradiction with R27/F5, and Codex **refuted one of Claude's own review notes** (the auto-merge race is
*not* fully closed by serialization — a manual merge can still land during reverify).

## Findings

| ID | Pri | Finding | Source | Status |
|----|-----|---------|--------|--------|
| F1 | P1 | Store durability mechanics under-defined — no atomic-write / lock / torn-file / quarantine spec | Codex, Agy, Claude | resolved — KTD15 + U2 |
| F2 | P1 | KTD5 "fresh-machine coarser" appeared to weaken R27/F5 "non-lossy"; non-code completion not durable | Codex, Agy | resolved — KTD5 reframe + KTD4 marker |
| F3 | P1 | R34 offline reconcile conflict resolution still open (winner policy, retry exhaustion, queue loss) | Codex, Claude | resolved — KTD15 offline policy + U2/U6 |
| F4 | P1 | Auto-merge third-sibling / manual-merge-during-reverify race not closed by serialization alone | Codex (refuted Claude MF5) | resolved — KTD7 base-SHA guard + U6 |
| F5 | P1 | Release-surface sync deferred to U11 violates `AGENTS.md:104` (same-PR rule) → integration bomb | Codex, Agy | resolved — KTD14 per-unit + U4/U11 |
| F6 | P1 | Build-sequencing inversions: U5 needs PR-read (in U6); U8 cost vs U10 (circular); U6 worktree vs U7 | Agy, Codex | resolved — U5/U6/U7/U8 boundaries |
| F7 | P1 | Child-recursion branch isolation — child spec not in parent's worktree | Agy | resolved — KTD10 GitHub terminal read |
| F8 | P2 | R3 "coordinator never collapses" invariant has no test | Claude | resolved — U3 test |
| F9 | P2 | R15 under-proved — U7 tests cap/reap but not durable session / owner / shared installs | Codex | resolved — U7 facets + matrix split |
| F10 | P2 | Idempotency key collides on a retry after clean failure → retry skipped as duplicate | Agy | resolved — KTD5 `attempt:<n>` |
| F11 | P2 | U7 falsely claims R31 coverage (its scope is graph/worktree, not liveness) | Agy | resolved — matrix fix |
| F12 | P3 | Weak citation: `SKILL.md:276` is only the Phase B heading, not spawn proof | Codex | resolved — `consensus-protocol.md:10` |

## Finding detail (the load-bearing ones)

### F2 — the ledger boundary appeared to weaken a settled requirement (P1)

KTD5's first draft said a fresh machine "recovers to GitHub+spec granularity — coarser but correct,"
which reads as conceding F5/R27's "non-lossy cold re-entry including the why." Codex flagged the
contradiction (requirements:69, :288). The resolution is a reframe, not a patch: **cold re-entry (F5) and
crash recovery (R30) are different scenarios.** Cold re-entry is a rest-state event (nothing
mid-transition) → fully reconstructed from the committed spec (structure + decision-trail "why" + cost) +
GitHub (completion); the cache absence loses nothing. Crash recovery is a same-machine event (the cache +
ledger are right there) → fine-grained replay. The only lossy case — mid-transition crash *plus* a
machine switch before reconnect — is a non-scenario for a solo operator and still degrades safely to
idempotent GitHub-truth reconcile. Antigravity's adjacent catch (a non-code leaf's completion lived only
in the cache → fresh-machine re-run) is closed by KTD4 now writing a durable GitHub/spec marker for
non-code leaves (already mandated by R11, now explicit in the KTD).

### F4 — the auto-merge race serialization does not close (P1)

Claude's own review note claimed the single-writer merge queue prevents the third-sibling race. Codex
refuted it: serialization stops two *coordinator* merges colliding, but during the (minutes-long)
reverify window a *manual or external* merge can land on the base, so the subsequent squash would merge a
stale tree. Resolved by guarding the final squash with an expected base-SHA / lease
(`gh pr merge --match-head-commit`) checked immediately before merge — a moved base fails the squash and
reloops — plus a 3-cycle base-churn starvation cap (KTD7, U6).

### F5 — release-surface discipline vs the all-or-nothing gate (P1)

Codex (citing `AGENTS.md:104`) and Antigravity both flagged that deferring every plugin's
metadata/changelog/marketplace sync to a final U11 either reds the drift guard at each interim merge or
ships a gutted plugin early. Resolved by making release-surface sync **per-unit-per-plugin in the same
PR** (KTD14) — e.g. U4 carries team-execution's own triad bump when it deletes `team-setup` — and
recasting U11 as the **final feature-flip gate** (advertise `/outcome`, prove the full suite), not the
only place surfaces touch.

### F6 — three unit-boundary sequencing inversions (P1)

Resolved by moving the read/write split to the right units: **U5** owns the read-only GitHub PR/issue
state primitive the completion barrier needs (the *merge action* stays U6); **U8** renders the cost
rollup "when present / no data yet when absent" so it depends only on U5/U6 (breaking a latent U8↔U10
cycle — U10 populates the fields U8 already renders); the **worktree-removed** negative state moves to U7
(which owns worktree lifecycle), leaving U6 the PR/branch negative states.

## Resolution (same session)

All twelve findings were resolved in the target plan immediately after review, at planning altitude:

- **F1 + F3** → new **KTD15** (atomic temp+`os.replace`, malformed-file quarantine, torn-ledger-line
  tolerance, lease-based coordinator + per-subplot locks with stale reclamation, and a concrete offline
  policy: GitHub wins for completion, server-superseded queued writes dropped, retry exhaustion pages,
  lost-queue intent re-derived from spec+ledger). U2's goal + test scenarios updated to match.
- **F2** → **KTD5** reframed (cold-re-entry vs crash-replay) + **KTD4** now writes a durable
  GitHub/spec marker for non-code leaves.
- **F4** → **KTD7** adds the expected-base-SHA squash guard + starvation cap; U6 gains the
  manual-merge-during-reverify test.
- **F5** → **KTD14** rewritten to per-unit-per-plugin sync; U4 gains the team-execution triad-bump test;
  U11 recast as the feature-flip gate.
- **F6** → U5 (PR-state read), U6 (merge action + base-SHA), U7 (worktree-removed), U8 (graceful cost,
  no U10 dep) boundaries corrected.
- **F7** → **KTD10** — the parent reads the child outcome's terminal state from GitHub, never a
  cross-branch spec read; child recursion is depth-bounded + ancestor-cycle-checked.
- **F8** → U3 test: the coordinator dispatches but never runs a leaf in-process (R3 invariant).
- **F9** → U7 test scenarios add durable-named-owned-session, one-worktree-per-sub-outcome, shared
  installs; the coverage matrix splits R15 across U6 (session/token) + U7 (worktree).
- **F10** → **KTD5** idempotency key gains an `attempt:<n>` ordinal so a post-clean-failure retry runs.
- **F11** → coverage matrix: R31 → U1 (validation) + U9 (liveness); dropped from U7.
- **F12** → citation corrected to `team-execution/.../consensus-protocol.md:10`.

## Review-result contract

- **Target:** `docs/plans/2026-06-25-operator-outcome-orchestration-plan.md`
- **Reviewed revision:** working tree (uncommitted)
- **Blocked:** no — all findings resolved in the same session; ready for `/work`.
- **Findings:** P1 ×7 (resolved), P2 ×4 (resolved), P3 ×1 (resolved); no P0.
- **Reviewers:** Claude (this session), Codex gpt-5.5 xhigh, Antigravity Gemini 3.1 Pro High — each
  independent, each trust-but-verify; citation accuracy confirmed by all three.
- **Residual risk:** the net-new orchestration layer (zero existing machinery) remains the highest build
  risk — mitigated by the build spine proving a vertical slice (U1–U5 on a 2-node DAG) before the full
  backend menu. The store-durability and merge-race mechanics are now specified but only a built draft
  with crash-injection tests will fully settle them.

## Linked artifacts

- Plan: `docs/plans/2026-06-25-operator-outcome-orchestration-plan.md`
- Requirements (origin): `docs/brainstorms/2026-06-25-operator-outcome-orchestration-requirements.md`
- Requirements review: `docs/reviews/2026-06-25-operator-outcome-orchestration-requirements-review.md`
