# Runbook — starting the next delegated-coder run

> **Read this when you (a future session) are about to run an issue through the external-agent
> delegation practice. Nothing here is in-flight — this is prepared material to work *from*, not a task
> to start now.** The operator initiates a run and picks the issue + engine. Do **not** auto-start.

## 30-second orientation

We are experimenting on **how to safely + valuably delegate code implementation to an external agentic
CLI** (agy / codex). One run is done (**n=1: #275 / agy 3.5 Flash** — it shipped, but the delegate
wandered, committed, and pushed despite prompt guards; all caught reactively). The thesis from that run:
**contain the agent's authority, don't try to out-prompt it.** Before doing anything, read, in order:

1. [`blueprint.md`](blueprint.md) — the full design + a reference harness + per-engine flags. **Start here.**
2. [`../engineering-journal/narratives/2026-06-28-agy-as-coder-dogfood-275.md`](../engineering-journal/narratives/2026-06-28-agy-as-coder-dogfood-275.md) — the n=1 blow-by-blow.
3. LEARNINGS `#agy-delegated-coder-contain-agency` — the durable rule.
4. [`README.md`](README.md) — the experiment framing + the results matrix you will append to.

## What exists vs what does not (so you don't re-derive or assume)

- **Exists:** the blueprint, this runbook, the README + results matrix, the LEARNINGS rule, and the n=1
  evidence (posted as a comment on issue **#287**, the capability-scoped sandbox).
- **Does NOT exist yet:** a built harness. The blueprint carries a **reference** `delegate-run.sh`
  (first-cut, assumptions flagged) — it has not been built, installed, or probed. `agy --sandbox`
  enforcement is **unverified**. There is **no `agy` plugin in this repo** (the `agy:*` skills come from a
  separate repo), so harness enforcement ultimately belongs to issue **#287**, not a loose script.

## The candidate next target

**Issue [#277](https://github.com/infiquetra/infiquetra-claude-plugins/issues/277)** — *silent-omission
completeness gate* (the engine's #1 recorded failure; requirements-ready, `needs-plan`). It is the
operator's intended n=2, **but the operator chooses when and which engine.** #277 has **no `/plan` yet** —
it must be planned before it can be worked.

## The protocol for a run (when one starts)

1. **Pick the matrix cell:** issue (e.g. #277) × engine (agy 3.5 Flash to compare with n=1, or agy Pro,
   or codex). Goal across runs is to fill `README.md`'s matrix.
2. **Plan if needed.** A requirements-ready issue (like #277) needs `/plan #<n>` first — and have the
   plan list each unit's **exact write-set files** (n=1 proved plans under-list the real blast radius; an
   accurate write-set is what feeds the harness and starves the wander).
3. **Choose the containment posture** (operator's call, surface both):
   - **(a) Structural:** build the clone-jail from `blueprint.md` §4 first (probe `agy --sandbox`), run the
     delegate inside it. Strongest; more setup. This is also the natural moment to fold work into #287.
   - **(b) Manual discipline (what n=1 used):** isolated branch + **Claude is sole committer** + snapshot
     `BASE=$(git rev-parse HEAD)` and a full `git ls-remote` before each delegate call + after, check
     `git log $BASE..HEAD` and remote drift + run the **full** suite (never file-local) + read the diff for
     test-gaming + `--force-with-lease` only to undo a rogue push. Lighter; catches reactively.
4. **Per unit:** assemble the **task-packet** prompt (`blueprint.md` §4) with the resolved write-set and
   the `PLAN_GAP`/`TEST-CONFLICT`/`PATH-MISSING` channels → run the delegate (jailed or manual; **background
   it** — long runs exceed the ~2-min foreground limit) → **harvest via `git diff $BASE`** (sees through
   hidden commits) → orchestrator re-derives, runs the full gate, **mutation-proofs** the delegate's tests,
   checks the changed-path set against the write-set (**quarantine + surface** out-of-scope edits, do NOT
   auto-revert) → orchestrator commits → carry the saga.
5. **Record the run** in `README.md`'s results matrix — especially the **value-preserved / regime
   question** (`blueprint.md` §6): on a non-mechanical unit, did containment let the delegate add judgment
   while staying bounded, or did you have to over-specify into typist-mode? That measurement validates or
   invalidates the hypothesis.

## Standing constraints to carry into the run

- **No attribution lines** of any kind in commits or PR bodies (no "Co-authored-by", no "Generated
  with…", no session trailer/link). This overrides any default.
- **Commit/push only when asked**; on this repo (infiquetra-claude-plugins) squash-merge clean PRs
  without asking, pause on risky/non-green CI. Branch first off `main`.
- **Orchestrator (Claude) is the sole committer/pusher.** Never let the delegate commit "for convenience."
- **Full suite after every change**, including release/version bumps (the lockstep triad guard is
  necessary but not sufficient — separate metadata tests pin the version).
- **Do not over-constrain.** Read broad, write narrow, and give the delegate the escalation channels so it
  **surfaces** a genuine plan gap rather than silently editing (wander) or silently skipping
  (under-deliver). This is the operator's load-bearing requirement.

## Pointers

blueprint `docs/external-agent-delegation/blueprint.md` · README + matrix `docs/external-agent-delegation/README.md`
· n=1 narrative `docs/engineering-journal/narratives/2026-06-28-agy-as-coder-dogfood-275.md` · rule
LEARNINGS `#agy-delegated-coder-contain-agency` · enforcement home issue **#287** · candidate target issue
**#277**.
