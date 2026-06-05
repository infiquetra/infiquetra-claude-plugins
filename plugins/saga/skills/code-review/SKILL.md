---
name: code-review
description: Run a structured Infiquetra code-quality review at the work-to-PR boundary. Reads the merge-base diff, runs a built-vs-planned audit plus judgment-selected review lenses, validates findings, writes a durable review artifact, appends to the work-thread saga, and routes — without mutating code. Triggers on "review this PR", "code review", "check my diff", "pre-PR review", or a /work hand-in before shipping.
---

# Code Review

`/code-review` answers **"Is this code safe to merge?"** It is a code-quality review **lens** that
fires at the **work -> PR boundary**: after `/work` produces code, before a PR is opened or a merge
happens. It reads a diff (working tree, branch, or PR), audits built-vs-planned, runs the lenses the
diff actually warrants, validates the surviving findings, classifies and routes them, and writes a
durable review artifact. It reports and routes — it does **not** fix, commit, push, open PRs, or file
issues.

## Position in the lifecycle

`/code-review` is NOT the saga `LIFECYCLE_PHASES` `review` slot. That slot is `/doc-review`'s plan ->
work gate ("Is this plan ready to execute?"). `/code-review` is a **within-work** pre-PR gate on the
code itself, downstream of execution:

- `/plan` answers: "How should it be built?"
- the `review` phase (`/doc-review`) answers: "Is this plan ready to execute?"
- `/work` answers: "Build it." (and calls `/code-review` before opening a PR)
- **`/code-review` answers: "Is the built code safe to merge?"** (this engine — a code-quality lens)
- `/qa` answers: "Does the shipped thing actually work?"

`/work`'s brief already names this engine ("Run `/code-review` before PR or shipping gates"). Because
code-review is a within-work gate and not the LIFECYCLE_PHASES `review` slot, it **never advances**
`lifecycle_phase` — it appends `review_paths` to the existing work-thread saga and leaves the phase
where `/work` set it.

## Core principles

1. **Gate, not fixer.** `/code-review` reports, classifies, and routes findings. It does **NOT** mutate
   code, does **NOT** commit, does **NOT** push, does **NOT** open or update a PR, and does **NOT** file
   SDLC issues (`/work`, ship gates, and `mission-control` own those). The programmatic mode is **ZERO file
   writes to reviewed code** — it is strictly read-only over the diff. Fixer dispatch is *offered*, never
   auto-run.
2. **Verify, don't guess.** Every finding cites `file:line` evidence. Claims of "safe", "handled
   elsewhere", or "tested" must cite the proving line, the handling code, or the test name — or be flagged
   as unverified. Never say "likely handled" or "probably tested". "This looks fine" is not a finding:
   either cite evidence it IS fine or flag it as unverified. This is Jeff's no-lies rule and it is the
   engine's spine.
3. **Confidence-gated and deduped.** Findings carry an anchored confidence (0/25/50/75/100). Suppress
   anything below anchor 75 — except a P0 at anchor 50+, which must surface (a critical-but-uncertain issue
   must not be silently dropped). Dedup by fingerprint (`path:line:category`). Honor `pre_existing`: do not
   blame this diff for old code it merely touched.
4. **Judgment-based lenses.** Read the full diff and spawn only the lenses with real work to do — not a
   fixed specialist roster that re-opens "reviewers that find nothing on this diff". Announce the team
   before spawning, with a one-line justification per conditional lens.
5. **Built-vs-planned audit always runs.** Scope-drift detection (informational) plus the 5-state
   plan-completion audit run on every review, grounded in the `docs/plans/` artifact and the engineering
   journal. The audit produces findings; the normal P0/P1 findings gate is what blocks.
6. **Saga append-only.** Touch the work-thread saga **only if one already exists** (scan first). Append
   the artifact path to `review_paths` and record the backend in `orchestration_mode`. **Never mint a
   saga, never invent `--kind`/`--id`, never advance `lifecycle_phase`.** If no saga is found, skip the
   saga write and say so.

## Interaction method

Use `AskUserQuestion` for choices from a known set (review mode, execution backend, fixer-dispatch
routing). Call `ToolSearch` with `select:AskUserQuestion` first if its schema is not loaded. Ask one
question per turn. For open-ended discussion, ask inline in chat. Never silently skip a question.

In a channel session (`redis-channel` active), `AskUserQuestion` cannot be called — inline the choices
in your reply text instead. Follow the canonical channel-inline convention in
`saga/skills/brainstorm/SKILL.md` (do not duplicate its wording here).

Use repo-relative paths in every generated document. Absolute paths break portability across machines
and worktrees. (The one exception is the saga `--review-paths` value — see Phase 5.)

---

## Phase 0 — Enter and scope

Parse arguments and determine the diff scope before doing any review work.

### 0.1 Parse the target and mode

- **Target:** working tree (default), a branch name, a PR number/URL, or `base:<ref>`. Strip recognized
  mode tokens before treating the rest as a target.
- **Mode:** `interactive` (default — the operator is in the loop) or `programmatic`/`report-only` (for
  `/work`'s future call and any skill-to-skill invocation). Programmatic mode is strictly read-only over
  the reviewed code (see Phase 4 and Phase 5 for the mode-based behavior).

### 0.2 Determine the diff scope (stale-base guard)

Fetch the base before diffing so stale local state does not produce false positives, then diff the
working tree against the merge base:

```bash
git fetch origin <base> --quiet
DIFF_BASE=$(git merge-base origin/<base> HEAD)
git diff "$DIFF_BASE"
```

`<base>` is the PR base branch (`gh pr view --json baseRefName -q .baseRefName` when a PR exists) or the
repository default branch. This includes committed and uncommitted changes while excluding commits that
landed on the base after this branch was created.

- **Untracked files:** they are not in `git diff` output. Note any untracked files in the working tree
  as excluded from review; do not review unstaged or untracked content as if it were part of the change.
- **No diff:** if `git diff "$DIFF_BASE" --stat` is empty, stop with "Nothing to review — no changes
  against `<base>`."
- **Tiny diffs (interactive only):** a trivial change may short-circuit to a quick read-and-report.
  Programmatic callers always run the full pass.

---

## Phase 1 — Intent and built-vs-planned audit

Establish what this change was *supposed* to do, then audit what it actually did. Load
`references/built-vs-planned.md` for the full rubric.

### 1.1 Discover intent

Gather stated intent from: the PR body (`gh pr view --json body -q .body` when a PR exists), the branch
name, the calling context (a `/work` hand-in names the plan), and commit messages
(`git log origin/<base>..HEAD --oneline`). When no PR exists — the common case, since `/code-review`
runs before a PR is opened — rely on commit messages and the plan.

### 1.2 Plan discovery

Locate the active plan artifact under `docs/plans/` and the journal entries for this work-thread (read
`docs/engineering-journal/` — DECISIONS/QUEUED for the relevant initiative). The saga's `plan_path`
(from `saga.py scan`/`restore`, Phase 5.1) is the most reliable pointer when a saga exists.

### 1.3 Scope-drift detection (informational)

Compare what was built against what was requested: SCOPE CREEP (files/features unrelated to the stated
intent, "while I was in there" changes that expand blast radius) and REQUIREMENTS MISSING (stated
requirements not addressed). Emit a `Scope Check: [CLEAN / DRIFT DETECTED / REQUIREMENTS MISSING]`
result with one-line Intent and Delivered summaries. This is **informational** — it produces findings,
it does not itself block. The normal P0/P1 findings gate is what blocks the PR.

### 1.4 Plan-completion audit

Classify each plan requirement / U-ID as **DONE / PARTIAL / NOT-DONE / CHANGED / UNVERIFIABLE** using
the three verification modes (DIFF / CROSS-REPO / EXTERNAL-STATE) and the honesty rule (prefer
UNVERIFIABLE over DONE when the diff cannot confirm the deliverable — code that *handles* a deliverable
is not the deliverable). The audit **always runs and emits findings**. Cite evidence per item.

---

## Phase 2 — Select lenses (judgment)

Read the FULL diff before selecting. Load `references/lens-catalog.md` and pick the lean infiquetra lens
set: the **4 always-on** lenses (correctness, security, testing, maintainability/conventions) plus the
conditional lenses whose domain the diff actually touches — including the **distinct
deploy/migration-verification** lens (not folded into anything) and the **reliability** lens.

The high-signal checklist categories ground the always-on checks: enum-and-value completeness (which
**requires reading code OUTSIDE the diff**), LLM-output trust boundary, SQL and shell injection, and
race conditions.

**Announce the team** before spawning: list the selected lenses with a one-line justification for each
conditional lens (e.g., "data-migration — diff adds a DynamoDB GSI and a backfill script"). Do not spawn
a lens that has no real work on this diff.

---

## Phase 3 — Review (fan-out)

Spawn the selected lenses as **generic agents** (`Explore`/`Task` — this plugin has no `agents/` dir, so
do **not** reference named `ce-*` agents). Each lens returns findings in the schema defined by
`references/findings-schema.md`.

**Operator-choice backend.** Offer the execution backend per `../../references/operator-choice.md` (the
plugin-root decision contract). There are exactly three backends — `inline | team-execution |
cc-workflows-ultracode`. Read the work shape, recommend the cheapest-correct backend and pre-select it,
but surface the alternatives so escalation is one step. Escalate to `team-execution` for risky/consensus
review (large diff, security, infra, cross-repo, deployment-sensitive); to `cc-workflows-ultracode` for
broad independent fan-out without elevated risk. Omit `cc-workflows-ultracode` when the Workflow tool is
observably absent. `inline` suits small diffs.

**Search-before-recommending.** Before citing a fix pattern (concurrency, caching, auth, framework
behavior), verify it is current best practice for the version in use — check for a built-in solution in
newer versions and verify API signatures against current docs. If WebSearch is unavailable, note it and
proceed with in-distribution knowledge.

---

## Phase 4 — Merge and validate

### Stage A — merge

1. **Dedup by fingerprint** (`path:line:category`). When multiple lenses flag the same issue, merge into
   one finding and record the cross-reviewer agreement.
2. **Cross-reviewer promotion / disagreement.** On a routing disagreement, keep the most conservative
   route (a finding may move `safe_auto -> gated_auto -> manual`, never the other way without stronger
   evidence).
3. **Confidence-gate.** Suppress findings below anchor 75, except a P0 at anchor 50+ (surface it).
4. **Sort and number.** Order by severity (P0 first) -> confidence anchor (descending) -> file -> line,
   then assign **stable, monotonically increasing finding #s** across the full set. Reuse the same #
   wherever a finding reappears (residual work, fixer routing). Do not restart numbering per section.

### Stage B — validator pass (mode-based right-sizing)

Run CE's independent per-finding validator (`references/validator.md`) — a fresh agent re-checks each
survivor: is it real in the code, introduced by THIS diff, and not handled elsewhere? -> `{validated,
reason}`. Right-sizing is **mode-based**, matching CE's actual mechanism:

- **Programmatic / report-only mode:** spawn one validator per Stage-A survivor, **capped at 15**
  (ordered P0 -> P3 by anchor; drop and note the over-budget count beyond 15). Validator-reject or
  failure -> **drop** the finding (conservative bias).
- **Interactive mode:** the **operator is the per-finding validator** — skip the pre-dispatch validator
  pass (per CE). The operator's decisions during routing are the validation.

There is **no severity carve-out**: the upstream suppress-<75 gate plus the 15-cap are the cost control,
not a per-severity exemption.

---

## Phase 5 — Report, route, and saga

### 5.1 Scan the saga (first)

```bash
python3 plugins/saga/scripts/saga.py scan
```

Find the active work-thread saga for this change (match on `issue_ref`, `plan_path`, or branch; confirm
with the operator if ambiguous). Capture its **exact** `kind` and `id` — you will reuse them verbatim.
**If no saga is found, there is no saga write** (see 5.4).

### 5.2 Present findings

Lead with P-level findings (P0 first), grouped by severity, using the CE output shape: a
pipe-delimited table per severity (`# | File | Issue | Reviewer | Confidence | Route`), then a
blockquote verdict. Include the built-vs-planned summary, the scope-check result, suppressed-count, and
coverage (residual risks, testing gaps). See `references/findings-schema.md` for the full output and
artifact contract.

### 5.3 Write the durable artifact

Write `docs/code-reviews/YYYY-MM-DD-<branch-or-pr>-code-review.md`. Use its **own** directory
`docs/code-reviews/` — **not** `docs/reviews/`, which the handoff/sdlc classifiers
(`handoff_envelope.py`) tag as plan-ready. The artifact carries the **reviewed SHA**
(`git rev-parse HEAD`) and the review-result contract (mirroring `/doc-review`'s shape):

- target (diff/branch/PR) and reviewed revision (commit SHA or "working tree")
- blocked status (blocked when any P0/P1 finding remains)
- finding priorities and statuses
- plan-completion results and the scope-check verdict
- coverage stats (suppressed count, residual risks, testing gaps)
- linked issue, plan, and work-session paths when available

In **interactive** mode, write the artifact. In **programmatic / report-only** mode, return the
structured findings envelope (CE headless shape — findings grouped by `autofix_class`, verdict in the
header, `Review complete` as the terminal line) and write **ZERO file writes to reviewed code**; the
caller owns durable persistence and any downstream routing.

### 5.4 Append the saga tick (only if a saga exists)

**If and only if** Phase 5.1 found an active work-thread saga, append a tick — reusing its exact `kind`
and `id`, passing the artifact path to `--review-paths` and the chosen backend to
`--orchestration-mode`. **OMIT `--lifecycle-phase`** so the existing phase carries forward (verified:
omitting it sends the argparse default `ideation`, which equals the dataclass default, so `saga.py`'s
`_merge` scalar carry-forward preserves the prior phase — code-review never advances the phase). Never
`git add` the tick (saga state is git-ignored, machine-local):

```bash
python3 plugins/saga/scripts/saga.py save \
  --kind <issue|task> \
  --id <the-existing-saga-id> \
  --review-paths docs/code-reviews/YYYY-MM-DD-<branch-or-pr>-code-review.md \
  --orchestration-mode <inline|team-execution|cc-workflows-ultracode>
```

**If no saga was found in 5.1, SKIP this command entirely and say so** ("No work-thread saga found —
skipping the saga write; never minting one from code-review"). `saga.py save` mints unconditionally, so
this scan-first / never-mint guard lives here in prose — do **not** invent a `--kind`/`--id` to satisfy
the CLI.

### 5.5 Offer fixer dispatch (never auto-run)

For actionable findings (`safe_auto`/`gated_auto`/`manual`), **OFFER** a fixer route — a review-fixer
agent, `/work`, or `team-execution` (operator-choice). `/code-review` never applies the fix itself.
`advisory` findings are report-only.

### 5.6 Route

- **`/qa`** — recommended when the review is clean (no P0/P1): the next gate is ship-readiness.
- **`/work`** — recommended when P0/P1 findings remain: hand the findings back for fixing.
- **`/handoff`** — when the work should become or update an SDLC issue.

### 5.7 Hard boundary

`/code-review` reviews, classifies, and routes. It does **NOT** implement fixes, does **NOT** commit,
does **NOT** push, does **NOT** open or update a PR, and does **NOT** file SDLC issues. Review, write the
artifact, append the saga tick (if one exists), route — then stop.

---

## Reference files

- `references/lens-catalog.md` — the lean infiquetra lens set (4 always-on + conditional, incl. the
  distinct deploy/migration-verification and reliability lenses), judgment-based selection rules, per-lens
  checklist grounding, the announce-the-team rule.
- `references/findings-schema.md` — severity (P0-P3), anchored confidence, `autofix_class`, `owner`, the
  `suggested_fix` rule, `pre_existing` honesty, evidence, fingerprint dedup, merge/sort/stable-# rules,
  and the output + durable-artifact contract.
- `references/validator.md` — the independent per-finding validator: the three questions, mode-based
  right-sizing, conservative bias, read-only constraint, `{validated, reason}` return.
- `references/built-vs-planned.md` — scope-drift detection (informational) + the 5-state plan-completion
  audit + the three verification modes + the honesty rule, reading `docs/plans/` and the journal.
