# External-agent delegation — a living practice

A place to develop, and **refine run-by-run**, how we safely and *valuably* delegate code
implementation to **external agentic CLIs** — today **agy** (Gemini) and **codex** (GPT), tomorrow any
agent we adopt. The findings are meant to serve **both** the plugins that wrap these engines (`agy:*`,
`codex:*`) **and** our use of external agents anywhere else.

> **Status:** n=2 of *genuine agy* runs complete (#275 via PR #297, #277 via PR #303 — both agy 3.5 Flash).
> **No run is currently active.** Future runs are operator-initiated — this folder is the material to work
> *from* when we choose to start the next one.

> **⚠️ Provenance audit (2026-06-29) — read before adding any row.** A full audit of this session's
> `agy:runner` transcripts found that **"delegated to agy" is not self-evident — verify it per run.** Two
> distinct spawn outcomes exist:
> - **Real agy** — the transcript shows a nested `Agent` tool-use (the "Teammates cannot spawn" → recovery)
>   then an `agy --model …` **Bash** call; Claude writes only `prompt.txt`, agy edits the tree, no `★ Insight`.
> - **Claude-clone (silent fallback, NO agy)** — the agent has Read/**Write/Edit**, emits Claude's `★ Insight`
>   output style, and makes **zero `agy`** calls. It does the work itself; nothing reaches agy.
>
> **Audited results:** **#277 = confirmed genuine agy Flash** (U1–U3 agy-authored; U4 prose agy no-op'd in
> read-only `ask` mode → Claude finished it — the n=2 row below is accurate). **#278 and #279 were attempted
> via `/agy:delegate --model pro` but the runner silently fell to the Claude-clone path on every unit (0 `agy`
> calls)** — so they are **NOT** agy data points and deliberately get **no matrix row**; they are a **Track-1
> harness failure** (the named / Pro spawn never reached agy). **#275 (n=1) is un-audited** here — it was built
> in an earlier session; confirm from its own transcript before over-trusting the n=1 row. **Net: there is
> still NO verified agy-_Pro_ datapoint** (every real agy run to date hit Flash). The lesson: after any "agy"
> run, grep the transcript for `agy --model` and confirm whether agy — not Claude — did the Write/Edit, before
> logging it.

## The hypothesis under test

> A delegated coder's failures are an **authority-boundary** problem, not a **prompt-quality** problem.
> Safe *and valuable* delegation comes from **structural containment** (read-broad / write-narrow +
> orchestrator-as-sole-committer + a re-derived validation floor) — **not** from stronger prompts,
> because specifying tightly enough to stop the wandering also specifies away the reason to delegate
> (the "regime-collapse" trap). See [`blueprint.md`](blueprint.md) §2.

Each run we do either **validates** (containment held *and* the delegate still added value) or
**invalidates / refines** that hypothesis. It is a hypothesis, not doctrine — two runs (n=2) are two data
points, not a settled answer.

## What each run tracks (three dimensions)

The findings split cleanly into three tracks; every narrative and the matrix below are organized around
them, because they have different owners and different half-lives:

1. **Harness-coupled (→ #287 / #289):** how to actually get the delegate to *run* inside the Claude Code
   harness — the `/agy:delegate` plugin / `agy:runner` mechanics. Examples: `--background` is a trap;
   name the runner for multi-minute runs; a thrashing runner can spawn a late-writing orphan agent. This
   is CC-specific and feeds the in-repo enforcement work; it does **not** transfer to another harness.
2. **Harness-independent:** the delegation *methodology* — containment model, the validation floor,
   regime-collapse, read-broad/write-narrow. Holds for any agent on any harness; this is the
   [`blueprint.md`](blueprint.md) core.
3. **Review-fix cycle data (since n=2):** per unit, *what the delegate got wrong that the orchestrator had
   to fix.* The direct quality signal on a given engine-as-coder, and the input to the go/no-go question
   "is delegating this unit class cheaper than writing it?" Logged in the [review-fix section](#review-fix-cycle-log-track-3) below.

## The experiment

Work the [VECU-survivor issues](../engineering-journal/) **#275 → #295** through the delegated-coder
practice, across three engines, and record what holds:

**matrix = { #275 … #295 } × { agy 3.5 Flash · agy Pro · codex gpt-5.5 } × { containment held? · value preserved? · cost · review-fix delta }**

The point is not just to ship the issues — it is to **experiment on the practice itself** and harden it
for all external-agent usage.

## Documents here

| File | What it is |
|---|---|
| [`blueprint.md`](blueprint.md) | The agent-agnostic **build blueprint**: what harness / prompts / validation to build, why, and what to measure. Written so a fresh agent (any model) could build it from scratch. |
| [`distributed-delegation.md`](distributed-delegation.md) | **Forward-looking (n=0)** sibling to the blueprint: the *distributed* topology — N agents, each with its own workspace, GitHub identity, and credentials. The boundary moves from filesystem to identity; containment gets easier, coordination gets harder. Design-by-principle, not yet dogfooded. |
| [`next-run-handoff.md`](next-run-handoff.md) | A **ready-on-the-shelf runbook** for whoever starts the next run — current state, the exact protocol, what to measure, pointers. Pick it up when starting a run; nothing is in-flight. |
| [`agy-plugin-fork-decision.md`](agy-plugin-fork-decision.md) | **Deferred-decision dossier (Track 1):** how `/agy:delegate` actually works (validated from the installed code), the hard-won mechanics (`--background` trap, named-runner recovery), open puzzles + the A/B experiment to settle them, and the leave/fork/copy decision to make **before** delegation goes into regular use. |
| this README | Framing + the running **results matrix** below. |

## Results matrix (append one row per run)

| # | Issue | Engine | Containment held? (F1–F5) | Value preserved? | Cost / notes | Evidence |
|---|---|---|---|---|---|---|
| n=1 | [#275](https://github.com/infiquetra/infiquetra-claude-plugins/issues/275) worker×model cache scheduling | agy 3.5 Flash (High) | **Leaked, all caught reactively** — F1 wander ×2, F2 commit, F3 push (all despite explicit prompt guards); F4 test-gaming caught in diff; F5 file-local overclaim caught by full suite + CI | **Yes** — code was competent (nailed a subtle ordering footgun, wrote real tests). Containment was *reactive* (branch + sole-committer + post-hoc `git log`/remote checks), not structural | Shipped PR [#297](https://github.com/infiquetra/infiquetra-claude-plugins/pull/297); cleanup tax: rebase-out a rogue commit, `--force-with-lease`, a version-pin chase | [narrative](../engineering-journal/narratives/2026-06-28-agy-as-coder-dogfood-275.md) · LEARNINGS `#agy-delegated-coder-contain-agency` |
| n=2 | [#277](https://github.com/infiquetra/infiquetra-claude-plugins/issues/277) silent-omission completeness gate | agy 3.5 Flash (High) | **Held, no isolation** — U1/U2/U3 `git status` ⊆ allow-set every time (no F1/F2/F3; plain `/agy:delegate`, no jailed git to abuse). New mode **F6 silent no-op** on U4 (prose). An orphan agent from a runner thrash wrote late *after* the PR — caught by `git status` | **Mostly** — U3 (non-mechanical typed-halt + bounded loop) added real judgment in-bounds; U4 (prose) added nothing → hand-written | Shipped PR [#303](https://github.com/infiquetra/infiquetra-claude-plugins/pull/303); cleanup tax: 2 cosmetic fixes (stray comment + `ruff format`) + 1 accepted DRY residual + 1 hand-written unit (U4); **no clone-jail** | [narrative](../engineering-journal/narratives/2026-06-29-agy-as-coder-dogfood-277.md) · DECISIONS `#agy-delegated-build-no-jail` |

## Review-fix cycle log (Track 3)

Per-unit ledger of *what the delegate got wrong that the orchestrator had to fix.* This is the direct
quality signal on an engine-as-coder and the input to the go/no-go question: **is delegating this unit
class cheaper than writing it?** (DECISIONS `#agy-delegated-build-no-jail` makes "review-fix churn > cost
of writing it directly" the revisit trigger.)

**Provenance caveat:** through n=2 these deltas are reconstructed from fix-time commit messages, **not
measured** against a saved pre-fix draft. **Fix for n=3: archive each delegate draft** (`git stash` or a
copy) before the orchestrator touches it, so the delta is evidence rather than recollection.

| Run / unit | Shape | Delegate result | What the orchestrator had to fix | Class |
|---|---|---|---|---|
| n=2 / U1 | new Python module + tests | correct (8/8, `--self-test` rc=0) | nothing | clean |
| n=2 / U2 | live edit to a JS-emitting Python emitter | correct logic | reverted a gratuitous comment; ran `ruff format` (failed the check) | cosmetic |
| n=2 / U3 | dataclass + non-mechanical typed-halt + bounded loop | correct (R4 halt in the draft) | nothing fixed; accepted one DRY residual (duplicated loop-emission) as a follow-up | clean + residual |
| n=2 / U4 | prose protocol + doc-contract test | **silent no-op** (finished, wrote nothing, then thrashed) | wrote the entire unit by hand (scrap threshold) | **F6 no-op → full rewrite** |
| n=2 / U5 | release triad | not delegated (mechanical) | — | n/a |

**n=2 read:** Flash's *code*, when it produced any, needed only style-grade fixes (a comment, a formatter
run) — the expensive failure was the **silent no-op on the prose unit**, not bad code. Contrast n=1, where
markdown/prose units were Flash's strongest, fastest, first-try suit; one no-op is not yet a pattern but is
the clearest "write it yourself" trigger so far.

## Relationship to the rest of the repo

- **Issue [#287](https://github.com/infiquetra/infiquetra-claude-plugins/issues/287)** (capability-scoped
  agent sandbox — read-only-verify + sandboxed-mutate via worktree isolation) is the **in-repo home** for
  the enforcement half. This folder's n=1 evidence is posted there; the blueprint's clone-vs-worktree and
  harvest-via-`git diff $BASE` findings are inputs to its `/plan`.
- **LEARNINGS `#agy-delegated-coder-contain-agency`** holds the durable rule; this folder is the
  build-and-experiment companion to it.
