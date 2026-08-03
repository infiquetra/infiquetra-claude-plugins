---
title: Work session — give the refute-N verify panel a severity axis (#686)
date: 2026-08-03
issue: https://github.com/infiquetra/infiquetra-claude-plugins/issues/686
plan: docs/plans/2026-08-02-issue-686-verify-panel-severity-axis-plan.md
doc_review: docs/reviews/doc-review-issue-686-2026-08-03.md
branch: feat/686-verify-panel-severity-axis
commit: 793c7c9b
final_commit: a40eac2c
pull_request: https://github.com/infiquetra/infiquetra-claude-plugins/pull/689
merge_commit: f0ca9a47
saga: issue-686
orchestration: cc-workflows-ultracode
---

# Work session — #686 verify-panel severity axis

## What this changed, in one paragraph

The saga plugin can compile a plan into a JavaScript "harness" that a Claude Code workflow runs.
When a harness includes a **verify panel**, several read-only agents independently try to refute the
work a unit just did, and a majority refutation kills that unit and halts the run. Until this change
the verdict those agents returned had exactly **one** rejection bucket, so "the code is broken" and
"the code is fine but the author described it wrong" were the same signal. This change splits that
bucket in two: `refuted_deliverable` still stops the run, `advisory_corrections` does not.

## Why it mattered

This is not a theoretical sharp edge. It fired in a real seven-unit workflow run in the sibling
repository `infiquetra/infiquetra-codex-plugins` (pull request #71): a verifier objected to a unit's
prose, the single-bucket gate read that as a refutation, and the run discarded a **correct** unit and
dead-lettered five units downstream of it. The gate was doing exactly what it was written to do —
the wiring, not the verifiers, was wrong.

## Execution

Three units, dispatched through the Claude Code workflow backend (`cc-workflows-ultracode`) as
workflow `wf_7dbd5245-def`. U1 ran alone; U2 and U3 ran as a parallel wave behind it, so the widest
concurrency was 2.

| Unit | Tier | What it owned | Result |
|---|---|---|---|
| U1 | opus / high | Split the verdict contract across 8 emitter sites plus two test modules | `done` |
| U2 | sonnet / medium | Reference doc, plugin release surfaces, DECISIONS entry | `complete` |
| U3 | sonnet / low | Cross-repo check against the hand-patched harness (read-only) | `pass` |

Run cost: 294,697 subagent tokens, 138 tool calls, 32.2 minutes wall clock.

Settlement was clean — 3/3 delivered, 0 casualties, `halt_required: false`, empty dead-letter queue,
ledger hash chain intact from the pre-submit manifest through all three settle events.

## The load-bearing edit

`_emit_panel_reconciliation()` is the single site where the gate arithmetic lives, and it is shared
by all three panel shapes: the one-shot panel, the `iterate_to_consensus` retry loop, and the `#364`
`escalate_on_signal` tier climb. Changing one predicate there changed all three at once — the plan
predicted this (KTD5) and it held.

The subtle part was **where** the advisory harvest call goes. `__logAdvisory` sits immediately after
the refuted const and *before* the missing-verifier block, because the function returns early on the
climb path further down. A call appended after that early return would have worked for two of the
three panel shapes and silently emitted nothing for climb units — advisories absent on exactly one
path and nowhere else, which is close to undebuggable. The doc-review caught this as a P1 before
execution started; the plan as originally written named the accumulator's declaration and its return
but never its fill site.

## What execution surfaced that planning did not

**A third prompt surface.** The plan's KTD6 correctly insisted every prompt surface change together,
and enumerated two — the Python-assembled `_verifier_prompt()` and the emitted JavaScript
`__verifierPrompt` helper. There were three. `plugins/saga/agents/readonly-verifier.md` is the
verifier's own **system prompt**, and it still instructed the legacy `{refuted, upheld}` shape — the
exact shape the new schema now rejects. A verifier following its own definition over the per-call
prompt would have emitted a verdict that failed validation, classified as *runtime-missing*, and
pushed the panel toward its quorum floor. That is the same silent gate-disarming failure class #686
exists to remove, reintroduced through the back door.

U1 found it, correctly declined to fix it (outside its declared file list), and flagged it for
assignment rather than assuming it. It was fixed here in the driving session and pinned with a drift
guard — nothing pinned that sentence before, which is why it drifted.

**A judgment call worth checking.** U1 changed two node-based tests to model the workflow runtime as
"hoist `export const meta`, run the remainder as an async function body," because the new top-level
`return` is a SyntaxError under plain ES-module parsing while top-level `await` — which harnesses
have always used — is legal. Both cannot hold in one loader. It flagged this explicitly as an
assumption to challenge. It is correct: the Workflow tool's own documented example scripts end with
a top-level `return`. KTD4 stands and needs no revisit.

## Verification

Everything below was run in the driving session against the **combined** tree — U1's suite run
predates U2's changes, and both predate the two edits made here.

| Check | Result |
|---|---|
| `uv run python -m pytest -q` | 5521 passed, 1 skipped, 442s, exit 0 (coverage 83%, min 80%) |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 433 files already formatted |
| `uv run mypy plugins/ scripts/ tests/` | no issues in 267 source files |
| `uv run bandit -r plugins/` | exit 0; 6 HIGH all pre-existing and outside changed files (5 in a vendored `.venv`, 1 a SHA1 call in `board_progression.py:95`) |

Cross-repo acceptance (U3, read-only, reading `origin/main` via `git show` after an explicit fetch):
re-emitting `infiquetra-codex-plugins`' committed spec with the fixed emitter reproduces its
hand-patched harness's gate mechanics exactly — legacy gate count `0`, and predicate / filter /
`__logAdvisory` counts of 4 / 4 / 5 on **both** files. The only residual difference is unit-prompt
text hand-authored mid-run, which appears in none of the committed spec's prompts and therefore no
re-emit can reproduce. The plan predicted this and named it a non-defect.

## Review and merge

Two review rounds ran after `793c7c9b`, the second reading the fixes the first produced. Round 1 was
a full programmatic `/code-review` over the merge-base diff. Round 2 was a targeted re-review of the
round-1 fix commit only — three lenses (testing / security / correctness), each spawned as
`saga:readonly-verifier` in a disposable worktree, capped at 3 concurrent.

| Round | Reviewed | Findings | Gating (P0/P1) | Fixed in |
|---|---|---|---|---|
| 1 | `1295270c` (merge-base diff) | 13 | 0 | `db3893e8` |
| 2 | `db3893e8` (the round-1 fix commit) | 8 | 0 | `cda95fb6` |

All 21 findings were fixed. Each round-2 fix was **mutation-proven**: the fix was reverted
in a scratch copy of the file and the suite re-run to confirm a test actually failed. That step is
what distinguishes "the tests pass" from "the tests would notice if this broke", and it caught two
cases where they would not have.

**A pre-existing fail-open surfaced while building the panel-size test matrix**, unrelated to the
severity axis. The emit-time quorum floor was baked as `ceil(n/2)` while the runtime disagreement
threshold is `ceil(k/2)` over *surviving* reporters. Those agree at odd `n` and differ by one at even
`n`, so a panel that lost exactly half its verifiers still cleared its floor — and because the lost
verdicts were the refuting ones, a HALT silently became a PASS. The floor is now `n // 2 + 1`.
Validated by executing 238 scenarios against both the old and new emitters: 18 cells differ, all at
even `n`, all in the fail-closed direction, zero deltas at odd `n`. All 36 committed panels in this
repo are `n=3`, so no committed panel changed behavior. See LEARNINGS
`{#quorum-floor-must-be-a-strict-majority}`.

**The three findings worth remembering** are the ones that could not have been found by re-reading
one's own work:

- A LEARNINGS entry that **stated its own measurement backwards**, crediting the unpatched emitter
  with the halt and the patched one with the clean pass — in the entry whose only job is preserving
  that direction. Acting on it would have restored the bug.
- A test that **could not fail**. It grepped the emitted harness source for `${gatingBar}` — the
  generator's own un-interpolated template literal, present whatever the ternary computes. Deleting
  the branching logic left the suite green. The root cause was structural: the test harness stub
  signature discarded prompts entirely, so no test built on it could ever have observed prompt text.
  See LEARNINGS `{#generator-output-greps-assert-on-templates}`.
- The advisory `round` ordinal counted *stored entries* rather than *panel rounds*, so a clean first
  round renumbered the second to "round 1". The original test put advisories in both rounds and so
  shared the code's blind spot exactly.

**Two fix commits merged unreviewed by any lens** — `cda95fb6` and `a40eac2c`. Reviewing the
fix-of-the-fix recurses without end, so the merge rested on per-fix mutation evidence plus a green
suite rather than on another review round. This is stated here and in the PR body rather than left
implied by the presence of review artifacts.

Final gate before merge: **5574 passed, 1 skipped**; ruff check and format, mypy, bandit, and all
five steps of the Release Surface Parity job clean locally; all 8 CI checks SUCCESS with
`mergeStateStatus: CLEAN`. Merged with `--merge` rather than `--squash` to preserve the two distinct
version bumps (`0.123.0` and `0.124.0`) as separate commits, matching the precedent set by PR #688.

One CI round was spent on a **ride-along commit**: `99cbd47b` (an unrelated CAMPPS board journal
entry that was already on the branch) failed the pull-request-only journal newest-first guard on its
own account. Worth noting the check that went red was named "Release Surface Parity" while the parity
script itself passed — it is a five-step job and the failure was in a later step. Fixed by relocating
four entries verbatim into the newest date section (`a40eac2c`).

## Deliberately not done

- **`orchestration_ref` overloading in the `/work` skill.** Phase 1.5 *reads* that field to locate
  the spec for re-emit, then the post-launch step *overwrites* it with the workflow run id. Measured
  across `.claude/saga/state.json`: 12 sagas hold a run id there, 4 hold a spec path. A resume finds
  the field present (so it clears the "ref missing" halt) but pointing at nothing. This session left
  the spec path in place and recorded the workflow handle in `--notes` instead — a stated divergence
  from the skill's literal instruction. Needs a defect card.
- **Workflow lease TTL.** The lease minted for this run declares `execution_ttl_seconds: 300` against
  a 32-minute run, and the skill tells the driver never to poll — so there is no boundary at which
  it could be renewed. The slots were swept ~5 minutes in; teardown's `release` returned an empty
  list, which reads like success. Nothing leaked, but the mid-run oversubscription guarantee did not
  hold. See LEARNINGS `{#workflow-lease-ttl-outlives-no-poll-contract}`. Needs a defect card.
- **`.gitignore` gap.** Two partial coverages, not two absences. `.coverage` (the binary data file) is
  ignored at line 30 but `coverage.xml` (the report `pytest --cov-report=xml` writes) is not — same
  tool, two artifacts, one covered. And `.saga/` is ignored *selectively*, six named paths rather than
  the directory, so the workflow lease files, `workflow-evidence-*/` directories, lease-keeper logs
  and invocation-id pointers the runtime writes all fall through. A blanket `git add -A` would sweep
  machine-local workflow artifacts into a commit.
- **The advisory accumulator never resets across a run.** `__advisories` is a module-level array in
  the emitted harness that only ever grows. Bounded in practice — 50 items × 180 chars per panel
  round — and unreachable by any committed panel, so it is a P3. Pre-existing.
- **A strict-majority floor is still satisfiable by a panel that lost its refuters.** At odd `n ≥ 5`,
  enough verifiers can go missing to flip the outcome while the surviving count still clears
  `n // 2 + 1`. Closing this means demanding full strength from every panel, which is a policy
  decision that would change behavior for all 36 committed `n=3` panels — not a fix to slip into a
  merge. Pre-existing, P3.

## Refs

- Commits `793c7c9b` → `db3893e8` → `cda95fb6` → `a40eac2c` on `feat/686-verify-panel-severity-axis`
- Pull request #689, merged as `f0ca9a47`; issue #686 closed 2026-08-03T11:59:26Z
- LEARNINGS `{#workflow-lease-ttl-outlives-no-poll-contract}`,
  `{#verdict-contract-has-three-prompt-surfaces}`, `{#worktree-copies-poison-recursive-grep}`,
  `{#regenerate-diff-fails-on-hand-patched-artifacts}`,
  `{#quorum-floor-must-be-a-strict-majority}`, `{#generator-output-greps-assert-on-templates}`
- DECISIONS `{#verify-panel-severity-axis-686}` (KTD1–KTD8)
- saga `0.122.0` → `0.123.0` → `0.124.0`
