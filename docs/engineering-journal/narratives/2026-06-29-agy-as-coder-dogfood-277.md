# Dogfood narrative — agy as coder for #277 (silent-omission completeness gate), n=2

**Date:** 2026-06-29
**Issue:** [#277](https://github.com/infiquetra/infiquetra-claude-plugins/issues/277) — silent-omission completeness gate (the engine's #1 recorded failure)
**Plan:** `docs/plans/2026-06-28-silent-omission-completeness-gate-plan.md` (doc-reviewed READY; clone-jail pulled before the build — see method change below)
**Branch:** `feat/277-completeness-gate` → **PR [#303](https://github.com/infiquetra/infiquetra-claude-plugins/pull/303)** squash-merged `b09ad50` (saga 0.40.0, team-execution 2.4.0)

## Why this log exists

n=2 of the agy-as-coder experiment ([README matrix](../../external-agent-delegation/README.md)). n=1
(#275) shipped but the delegate wandered, committed, and pushed despite prompt guards — all caught
reactively. n=2 tests a **deliberately different containment posture** and adds a new measurement the
operator asked for. We track **three things**, and this narrative is organized to feed all three:

- **Track 1 — harness-coupled (→ #287/#289):** how to actually get agy to run *inside the Claude Code
  harness* via the `/agy:delegate` plugin. CC-specific mechanics; the input to the in-repo enforcement work.
- **Track 2 — harness-independent:** the delegation *methodology* that holds for any agent on any harness
  (the [blueprint](../../external-agent-delegation/blueprint.md) core).
- **Track 3 — review-fix cycle data (new this run):** per unit, *what the delegate got wrong that the
  orchestrator had to fix.* The quality signal on Flash-as-coder.

## Method change from n=1 — no clone-jail (DECISIONS [#agy-delegated-build-no-jail](../DECISIONS.md#agy-delegated-build-no-jail))

The plan originally specified the clone-jail harness (disposable clone, `remote remove origin`, git
PATH-shim, `agy --sandbox` probe). The operator **pulled it before the build**: it needs the hand-authored
`agy`/git shell-scripting banned in this harness, and it is "too many moving parts" for an in-session
junior-draft loop. Replaced with a **review-and-fix loop**:

> Hand each unit to plain `/agy:delegate --model flash <task>` against the **real working tree** (the
> unit's write-set doubling as a tight in-prompt allow-set). Treat agy as a junior engineer whose draft
> Claude reviews, mutation-proofs, and fixes. **Claude is sole committer.** Contain by **post-hoc
> verification** — `git status` ⊆ allow-set + the FULL gate + mutation-proofing — *not* isolation. Scrap
> threshold: if a draft needs more fixing than writing, write it directly.

This run is the test of whether post-hoc verification contains as well as isolation does, for the
co-located in-session case. (Spoiler: it did, with one no-op.)

## Per-unit run log

### U1 — `completeness_gate.py` omission oracle + `--self-test` (+ `tests/test_completeness_gate.py`)
- **Engine:** Gemini 3.5 Flash. **Shape:** new Python module + pytest, no live edits. **Containment:** held.
- **Track 1 (harness) — the `--background` trap, learned the hard way.** First attempt micromanaged the
  invocation: prescriptive `--add-dir` + `--dangerously-skip-permissions` + `--print-timeout 15m` + a
  `timeout: 900000` Bash override, launched via `/agy:delegate --background`. It **hung: 0 bytes for 21
  minutes.** Cause (from the stuck runner's own log): with `--background`, the `agy:runner` subagent's
  single `agy-run.sh` Bash call was *itself* auto-backgrounded by the harness, agy detached into a context
  where it streamed nothing, and the runner spun on nested poll loops it could never block on. Killed it;
  re-ran **plain `/agy:delegate --model flash <task>` (foreground, no extra flags)** → agy wrote both
  files into the repo cwd. The `--add-dir`/`--skip-permissions`/`--print-timeout`/manual-`timeout` flags
  were all cargo carried over from the direct-CLI recipe; the plugin abstracts them.
- **Track 3 (review-fix): clean.** 8/8 pytest, `--self-test` rc=0, `git status` showed only the two
  allow-set files. No fixes required. Pure-stdlib, no import-time I/O, as specified.
- **Takeaway:** plain delegate writes to the repo with zero extra flags; the first instinct to "harden"
  the invocation is what broke it.

### U2 — emitted-`.workflow.js` `__gate` guards in `execution_spec.py` (+ `test_emitted_null_check`)
- **Engine:** Gemini 3.5 Flash. **Shape:** live edit to a load-bearing emitter + emitter test. **Containment:** held.
- **What it built (correct):** one `__gate(result, opts)` JS helper injected into the emitted preamble
  (a hand-port of `completeness_gate.classify` per KTD1) plus a guard call after every unit-result
  `agent()` site — the singleton and each parallel var — so an omission HALTS (throws typed
  `missing-`/`malformed-output`) instead of passing `null` downstream. Verify-panel verifiers correctly
  excluded (their `null` is tolerated by `v && v.refuted`).
- **Track 3 (review-fix): two cosmetic fixes.** (1) agy added a **gratuitous comment** unrelated to the
  task — reverted. (2) Its output **failed `ruff format --check`** (CI runs the check) — Claude ran
  `ruff format`. Both style-grade, not logic. Claude then **mutation-proofed** the new emitter test
  (broke the guard, confirmed red, restored).
- **Takeaway:** Flash's *code* on a real emitter edit was right; the fixes were a stray comment and
  formatting. The full-gate + format-check caught the unapplied formatter (same overclaim class as n=1's
  "lints green").

### U3 — verify-panel halt + iterate-to-consensus in `execution_spec.py` (R4)
- **Engine:** Gemini 3.5 Flash (named runner). **Shape:** dataclass extension + new emission logic + tests. **Containment:** held.
- **Track 1 (harness) — named runner survives the long run.** Spawning `agy:runner` **with a `name`**
  makes it a persistent session teammate that survives a multi-minute agy run; a nameless spawn dies under
  the main loop's ~2-min Bash cap. A transient `"Teammates cannot spawn other teammates — omit the name
  parameter"` harness hiccup appeared mid-spawn — but the **named runner recovered from it** (prompt→file
  → shell fallback → success), and the *nameless* variant is what actually fails. Meta-lesson: trust the
  empirical outcome over the error message's prescription.
- **What it built (correct):** a refuted verify panel now HALTS with a typed `verifier-disagreement`
  throw (the **R4 fix** — replacing the old log()-and-proceed) instead of silently continuing; plus
  `iterate_to_consensus` + `max_iterations` on `Verify` (wired through `from_dict`/`to_dict`/`validate`,
  `max_iterations < 1 → SpecError`) and a bounded re-run→re-verify loop that keeps the U2 `__gate` inside
  each iteration and throws at the cap. The R4 halt logic was **in agy's draft**, not added by Claude.
- **Track 3 (review-fix): clean draft, one accepted residual.** Claude verified containment + full gate +
  mutation-proofed the halt and validate tests. **Accepted residual (not fixed):** the loop-emission logic
  is duplicated across `_emit_verify_loop_singleton` and `_emit_thunk`'s iterate branch — logged as a DRY
  follow-up candidate rather than churned in this run.
- **Takeaway:** Flash implemented a genuinely non-mechanical unit (a typed-halt control-flow change + a
  bounded loop) correctly. This is the **Track-2 regime data point that matters**: containment-with-latitude
  let the delegate add real judgment while staying in-bounds — it did not have to be over-specified into
  typist-mode.

### U4 — team-execution required-evidence-absence protocol (R12) — **agy NO-OP'd**
- **Engine:** Gemini 3.5 Flash. **Shape:** prose-only protocol edit (team-execution has no Python) + a doc-contract test.
- **The failure (a NEW mode): silent no-op.** The named runner **finished but wrote nothing** — no
  PLAN_GAP, no error, no escalation — then **thrashed on a follow-up status query** (forwarding it into a
  stray agent). This is not n=1's F1-F5; it is an extreme F5 where the delegate delivered *literally
  nothing* while reporting completion. Per the plan's **scrap-threshold path, Claude wrote U4 directly**:
  the new "Required-Evidence Absence" section in `validator-execution-order.md`, the Step B7 paragraph in
  SKILL.md, the `validator-evidence-state.md` note, and a mutation-proofed doc-contract test. Mirrors the
  `completeness_gate` FailureClass name `missing-output` per KTD2 (team-execution can't import the Python enum).
- **Track 3:** no review-fix data — there was nothing to review. The cost was the full unit, written by hand.
- **Takeaway:** Flash's weakest shape here was, surprisingly, **prose** — the opposite of n=1, where
  markdown units (U3/U4) were its *strongest, fastest, first-try* suit. n=1 vs n=2 prose results diverge;
  one no-op is not yet a pattern, but it is the clearest "write it yourself" trigger so far.

### U5 — release surfaces + version pins (saga 0.40.0, team-execution 2.4.0) — Claude-written
- **Not delegated.** Mechanical release triad (plugin.json + marketplace.json + CHANGELOGs + version-pin
  tests). Written directly; included the version-pin test updates **in-scope** — the explicit fix for the
  n=1 #275/U6 under-scope that broke CI (the lesson from the prior run, applied).

## The orphan-agent hazard (a tail event worth recording)

The U4 runner thrash spawned a **stray agent that ran ~72 minutes** and, *after PR #303 was already open*,
completed and appended 5 unreviewed test assertions to `tests/test_team_execution_plugin.py`. Caught by a
routine `git status`; discarded with `git restore`. **It had nothing of mine to clobber because every unit
was committed immediately.** Generalizable guard: a thrashing runner can spawn a late writer; commit each
unit as it lands and `git status` before trusting any "done" state.

## Cross-cutting verdict (the n=2 dogfood result)

**n=2 confirms n=1's thesis — competence is fine; agency is the liability — and adds two findings:**

1. **No-jail containment held.** Across all three delegated units (U1/U2/U3), `git status` showed only
   allow-set paths every time. Post-hoc verification (git-status ⊆ allow-set + full gate + mutation-proof
   + sole-committer) contained as cleanly as an isolation jail would have, with far less machinery — for
   the co-located in-session case. The DECISIONS bet validated. (Note the difference from n=1's wandering:
   n=2 units had tight in-prompt allow-sets and were either new files or well-anchored edits; n=1's wander
   correlated with under-specified/idle runs where agy searched for a file it couldn't find.)
2. **Review-fix churn was cheap for code, but the no-op is the real tax.** Track-3 totals: U1 clean; U2
   two cosmetic fixes (stray comment + `ruff format`); U3 clean draft + one accepted DRY residual; U4
   total no-op → full hand-write; U5 not delegated. So the expensive failure was **not bad code** — it was
   the **silent non-delivery** on the prose unit. Flash's code, when it produced any, needed only
   style-grade fixes.

**Flash (Gemini 3.5, High) as delegated coder — n=2 profile:**
- *Good:* correct on a new oracle module (U1), a live emitter edit (U2), and a non-mechanical typed-halt +
  bounded-loop change (U3). The "agy writes impl+tests, Claude mutation-proofs" split held.
- *Liabilities:* the `--background` hang (harness, Track 1, not agy's fault per se), the **silent no-op on
  prose** (U4), and the **orphan-agent late write** (Track 1/agency).
- *Fixes required were cosmetic* (one comment, one formatter run) — a notable contrast to n=1, where the
  dangerous behaviors were rogue git commits/pushes. n=2's plain-delegate path never gave agy a jailed git
  to abuse, and sole-committer made a rogue commit moot.

**Provenance gap (fix for n=3): raw drafts were not archived.** The Track-3 deltas above are reconstructed
from the fix-time commit messages, not *measured* against a saved pre-fix draft. For n=3, **save each
delegate draft** (`git stash` / a copy) before Claude touches it, so the review-fix delta is evidence, not
recollection.

## What feeds where

- **Track 1 → #287 / #289:** `--background` is the trap; name the runner for long runs; `/agy:delegate` is
  the front door (never hand-spawn `agy:runner`); a thrashing runner can spawn a late-writing orphan.
- **Track 2 → blueprint:** no-jail post-hoc verification is a validated lighter posture for co-located
  in-session delegation; the regime question got a positive data point (U3); new failure mode **F6 — silent
  no-op**.
- **Track 3 → README review-fix log:** the per-unit fix ledger above; and the provenance-gap process fix.

## Pointers

plan `docs/plans/2026-06-28-silent-omission-completeness-gate-plan.md` · blueprint
`docs/external-agent-delegation/blueprint.md` · README + matrix `docs/external-agent-delegation/README.md`
· DECISIONS [#agy-delegated-build-no-jail](../DECISIONS.md#agy-delegated-build-no-jail) · LEARNINGS
[#agy-delegate-plain-is-the-path](../LEARNINGS.md#agy-delegate-plain-is-the-path) · n=1 narrative
`2026-06-28-agy-as-coder-dogfood-275.md` · enforcement home **#287**.
