# Runbook — starting the next delegated-coder run

> **You (a future session) are about to run an issue through the external-agent delegation practice.**
> Nothing here is in-flight — this is prepared material to work *from*, not a task to start now. The
> **operator initiates** a run and picks the issue + engine. Do **not** auto-start.

## 30-second orientation

We are experimenting on **how to safely + valuably delegate code implementation to an external agentic
CLI** (agy / codex). **Two runs done (n=2):**

- **n=1: #275 / agy 3.5 Flash** — shipped (PR #297), but the delegate wandered, committed, and pushed
  despite prompt guards; all caught reactively. Used the **manual-discipline** posture (branch + sole
  committer + post-hoc git/remote checks).
- **n=2: #277 / agy 3.5 Flash** — shipped (PR #303), **no clone-jail**: plain `/agy:delegate` against the
  real tree + post-hoc verification + a review-and-fix loop. Containment held across all 3 delegated units;
  fixes were cosmetic; one unit (prose) was a **silent no-op** and got hand-written.

Thesis of the practice: **contain the agent's authority, don't try to out-prompt it.** Before doing
anything, read, in order:

1. [`blueprint.md`](blueprint.md) — full design + reference harness + per-engine flags + failure taxonomy. **Start here.**
2. [`../engineering-journal/narratives/2026-06-29-agy-as-coder-dogfood-277.md`](../engineering-journal/narratives/2026-06-29-agy-as-coder-dogfood-277.md) — n=2 blow-by-blow (the no-jail posture).
3. [`../engineering-journal/narratives/2026-06-28-agy-as-coder-dogfood-275.md`](../engineering-journal/narratives/2026-06-28-agy-as-coder-dogfood-275.md) — n=1 blow-by-blow (the wandering run).
4. LEARNINGS `#agy-delegate-plain-is-the-path` + `#agy-delegated-coder-contain-agency` + DECISIONS `#agy-delegated-build-no-jail` — durable rules.
5. [`README.md`](README.md) — experiment framing, the three tracking dimensions, results matrix + review-fix log you append to.

## What exists vs what does not (so you don't re-derive or re-assume)

- **Exists:** blueprint, this runbook, README + results matrix + review-fix log, LEARNINGS/DECISIONS rules,
  n=1 + n=2 evidence (n=1 evidence posted on issue **#287**, capability-scoped sandbox).
- **Does NOT exist yet:** a built containment harness. The blueprint carries a **reference**
  `delegate-run.sh` (first-cut, assumptions unproven). n=2 showed you may not need it for the co-located
  in-session case — post-hoc verification sufficed.

## The three tracking dimensions (record findings against these)

1. **Harness-coupled (→ #287/#289):** how to get the delegate running inside the CC harness.
2. **Harness-independent:** the methodology (containment, validation floor).
3. **Review-fix cycle:** per unit, what you had to fix in the delegate's draft → README review-fix log.
   **For n=3, archive each raw draft before you fix it** (`git stash` or a copy) so the delta is measured,
   not reconstructed.

## Protocol for a run (when one starts)

1. **Pick a matrix cell:** issue × engine. Remaining unbuilt VECU survivors: **#278, #279, #281, #283,
   #285, #287, #289, #291, #293, #295** (#275 + #277 are done). Engines: agy 3.5 Flash (compare to n=1/n=2),
   agy Pro, or codex gpt-5.5. Dependency order matters for some: **#279 (board authority+writer) →
   #295 (reconcile companion, hard-dep on #279)**; **#275 → #289 (residency guard, after S-1/U4)**;
   **#277 → #285**. The operator picks; goal across runs is to fill the README matrix.
2. **Plan if needed.** A requirements-ready issue needs `/plan #<n>` first — the plan must list each
   unit's **exact write-set files** (n=1 proved plans under-list real blast radius; an accurate write-set
   feeds the in-prompt allow-set and starves wander).
3. **Choose containment posture** (operator's call; default has shifted since n=2):
   - **(default) Post-hoc / no-jail (n=2):** plain `/agy:delegate --model <alias> <task>` against the real
     tree, the unit's write-set as a tight in-prompt allow-set, then Claude verifies: `git status` ⊆
     allow-set + the FULL gate (`pytest` + `ruff format --check` + `ruff check` + `mypy`) + mutation-proof
     any tests the delegate wrote + read the diff. **Claude is sole committer.** Lightest; validated at n=2.
   - **(escalate) Clone-jail (blueprint §3):** build the disposable-clone harness only if the delegate
     actually wanders outside its allow-set on a write job. Strongest; most setup; the natural moment to
     fold work into #287.
   - **(legacy) Manual-discipline (n=1):** isolated branch + sole committer + snapshot `BASE=$(git rev-parse
     HEAD)` + `git log $BASE..HEAD` remote-drift check + `--force-with-lease` to undo a rogue push. Use
     only if the engine has a git-commit/push reflex (n=1 agy did; n=2's plain-delegate path never gave it
     a jailed git to abuse).
4. **Per unit:**
   - Assemble the **task-packet** prompt (blueprint §4): read-broad/write-narrow, the resolved write-set as
     the allow-set, and explicit `PLAN_GAP` / `TEST-CONFLICT` / `PATH-MISSING` escalation channels.
   - **Launch via `/agy:delegate` (the front door) — never hand-spawn `agy:runner`, never hand-roll an
     `agy` shell call (operator-banned).** Spawn the runner **with a `name`** so it survives the
     multi-minute run as a session teammate. **Do NOT pass `--background` — it is the trap** (nests
     backgrounding, detaches agy into a 0-output context, the runner spins). A transient "Teammates cannot
     spawn other teammates" hiccup is recoverable; the *nameless* spawn is what actually fails.
   - **(n=3+) Archive the raw draft** before touching it (Track 3 measurement).
   - **Verify:** re-derive, run the **full** suite (never the delegate's file-local subset — n=1/n=2 both
     proved blast radius hides outside the touched file, including version-pin tests on release bumps),
     **mutation-proof** the delegate's tests, and check the changed-path set ⊆ the allow-set lines.
   - **Scrap threshold:** if the draft needs more fixing than writing — or is a silent no-op (F6) — write
     the unit yourself. Record it in the review-fix log.
5. **Commit / PR / merge:**
   - **Orchestrator (Claude) is sole committer/pusher.** Never let the delegate commit "for convenience."
   - **No attribution lines** of any kind in commits or PR bodies (no "Co-authored-by", no "Generated
     with…"). This overrides any default.
   - Commit each unit **as it lands** (a thrashing runner can spawn a late-writing orphan agent — n=2 saw
     one write ~72 min later, after the PR; immediate commits left it nothing to clobber).
   - On this repo (infiquetra-claude-plugins), squash-merge clean PRs without asking; pause on risky /
     non-green CI. Branch first off `main`.
   - **Release surfaces are their own unit:** plugin.json + marketplace.json + CHANGELOG + the version-pin
     tests, all in-scope (the n=1/#275-U6 CI break was a missed version-pin test).

## Pointers

blueprint `docs/external-agent-delegation/blueprint.md` · README + matrix + review-fix log
`docs/external-agent-delegation/README.md` · n=2 narrative
`docs/engineering-journal/narratives/2026-06-29-agy-as-coder-dogfood-277.md` · n=1 narrative
`docs/engineering-journal/narratives/2026-06-28-agy-as-coder-dogfood-275.md` · rules LEARNINGS
`#agy-delegate-plain-is-the-path` / `#agy-delegated-coder-contain-agency`, DECISIONS
`#agy-delegated-build-no-jail` · enforcement home issue **#287**.
