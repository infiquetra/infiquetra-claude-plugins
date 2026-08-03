---
title: Work session — give the refute-N verify panel a severity axis (#686)
date: 2026-08-03
issue: https://github.com/infiquetra/infiquetra-claude-plugins/issues/686
plan: docs/plans/2026-08-02-issue-686-verify-panel-severity-axis-plan.md
doc_review: docs/reviews/doc-review-issue-686-2026-08-03.md
branch: feat/686-verify-panel-severity-axis
commit: 793c7c9b
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
- **`.gitignore` gap.** `.saga/` and `coverage.xml` are untracked but not ignored, so any blanket
  `git add -A` would sweep machine-local workflow artifacts into a commit.

## Refs

- Commit `793c7c9b` on `feat/686-verify-panel-severity-axis`
- LEARNINGS `{#workflow-lease-ttl-outlives-no-poll-contract}`,
  `{#verdict-contract-has-three-prompt-surfaces}`, `{#worktree-copies-poison-recursive-grep}`,
  `{#regenerate-diff-fails-on-hand-patched-artifacts}`
- DECISIONS `{#verify-panel-severity-axis-686}` (KTD1–KTD8)
- saga `0.122.0` → `0.123.0`
