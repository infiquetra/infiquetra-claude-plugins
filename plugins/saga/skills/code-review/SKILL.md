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
3. **Confidence-classified and deduped.** Findings carry anchored confidence metadata
   (0/25/50/75/100), are admitted to the report by the findings-schema rules, and are deduplicated by
   fingerprint (`path:line:category`). Confidence and Priority never decide review acceptance. Honor
   `pre_existing`: do not blame this diff for old code it merely touched.
4. **Canonical judgment-based lenses.** Read the full diff, load the versioned roster at
   `plugins/saga/references/lens-roster.json`, run its four always-on lenses, and select only conditional
   lenses with real work to do. Announce the selected set and record a one-line reason per conditional
   lens.
5. **Built-vs-planned audit always runs.** Scope-drift detection (informational) plus the 5-state
   plan-completion audit run on every review, grounded in the `docs/plans/` artifact and the engineering
   journal. Built-versus-planned remains an independent gate; it is not folded into numeric scoring.
6. **Saga append-only.** Touch the work-thread saga **only if one already exists** (scan first). Append
   the artifact path to `review_paths` and record the backend in `orchestration_mode`. **Never mint a
   saga, never invent `--kind`/`--id`, never advance `lifecycle_phase`.** If no saga is found, skip the
   saga write and say so.
7. **Code Review owns consensus.** `plugins/saga/scripts/review_consensus.py` owns scoring, selective
   reruns, the three-cycle limit, delta checks, fix consolidation, and `review_result.v1`. Acceptance is
   the roster's derived-overall rule plus its applicable-dimension floor. Priority, confidence, and the
   external advisory seat are never additional acceptance gates.

## Interaction method

Use `AskUserQuestion` for choices from a known set (review mode, execution backend, fixer-dispatch
routing). Call `ToolSearch` with `select:AskUserQuestion` first if its schema is not loaded. Ask one
question per turn. For open-ended discussion, ask inline in chat. Never silently skip a question.

In a channel session (`redis-channel` active), `AskUserQuestion` cannot be called — inline the choices
in your reply text instead. Follow the canonical channel-inline convention in
`saga/skills/brainstorm/SKILL.md` (do not duplicate its wording here).

<!-- gate-record: id=code-review-interaction absence=HALT transport=ask-user-question -->
**Operator-absence contract (#371).** Every known-set gate above declares what happens on
silence, and the declaration above this line is the contract. `HALT` here: stop and wait. A timeout,
a widget error, or a dropped session is never consent — do not proceed on a default and do not
invent an answer. Ask one question at a time and read the decision from the operator's actual
answer, never from a widget's raw return value.

Use repo-relative paths in every generated document. Absolute paths break portability across machines
and worktrees. (The one exception is the saga `--review-paths` value — see Phase 5.)

## Engine Offer

Before offering an external-engine second opinion for code review, run
`python3 plugins/saga/scripts/engine_offer.py offer --stage code-review --repo-root . --attended`.
If the helper reports `prompt_required`, `/code-review` owns the `AskUserQuestion` or channel-inline
prompt and persists the selected preference with `engine_offer.py remember`. The offer is advisory
only; `/code-review` still verifies every finding and owns the typed outcome.
On this stage the helper may also list `external-only`, which excludes the home vendor from
the external-reviewer seat. If the remaining reviewers cannot meet quorum, halt and tell the
operator — do not fall back to the excluded vendor. Under external-only the home vendor cannot
be reached through the external-reviewer seat. Dispatch an accepted external reviewer through
`plugins/saga/scripts/engine_session_runner.py` (a managed terminal session), not as a
subagent. Select that runner with `select_review_runner`; under `external-only` admit the
roster with `external_only.admit_external_only` first.
The installed transport guarantee remains exact: Under external-only the home vendor cannot be reached
through the external-reviewer seat. The in-session lens fan-out is governed by the consensus-panel
roster, which is separate work. Code Review then maps that transport roster into the canonical lens
roster before scoring; the transport sentence does not transfer consensus ownership.
Launch and collect through the module's CLI, the same way the offer helper is invoked:

```bash
python3 plugins/saga/scripts/engine_session_runner.py launch \
  --invocation-file <invocation.json> --repo-root . --stage code-review \
  --mode <second-opinion|external-only> --home-vendor <vendor> --engine-id <engine> \
  --claim-store .saga/second-opinion-claims.json
python3 plugins/saga/scripts/engine_session_runner.py collect \
  --handle-file <launch-stdout.json> --claim-store .saga/second-opinion-claims.json
```

The invocation file must include the same `request_digest` as the durable requested
claim. Persist that claim before launch. Launch reserves the pending slot, starts
the session, and prints a JSON object that collect can read as-is (handle fields
are at the top level). A launch that returns `session_outcome=pending` has not
finished. Collect later. Do not treat pending as died, and do not re-launch. Terminal `ran-empty` or
`died` delivery produces `review_incomplete` without consuming a scoring cycle or fabricating a score.

<!-- gate-record: id=code-review-engine-offer absence=HALT transport=ask-user-question -->
The offer prompt rides the durable gate-record contract declared in Interaction method (gate id
`code-review-engine-offer-<run-id>`): open before prompting, satisfy on answer, `resolve-absent`
on silence (`HALT`).

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
it does not itself change the numeric outcome.

### 1.4 Plan-completion audit

Classify each plan requirement / U-ID as **DONE / PARTIAL / NOT-DONE / CHANGED / UNVERIFIABLE** using
the three verification modes (DIFF / CROSS-REPO / EXTERNAL-STATE) and the honesty rule (prefer
UNVERIFIABLE over DONE when the diff cannot confirm the deliverable — code that *handles* a deliverable
is not the deliverable). The audit **always runs and emits findings**. Cite evidence per item.

### 1.5 Freeze the review criteria (pre-registered, R4/#398)

In **interactive** mode, before the Phase 3 fan-out, freeze the pass/fail contract for this reviewed
SHA — the scope (files under `<base>...HEAD`) and the roster-backed `review_result.v1` outcome rule — so a later
attempt at the same revision cannot redefine what counts as clean:

```bash
python3 plugins/saga/scripts/evidence_ledger.py --repo-root . --saga-id <issue-N|task-slug> \
  freeze-criteria --check-id code-review --reviewed-sha "$(git rev-parse HEAD)" \
  --criteria-file <criteria.json>
```

`<criteria.json>` captures `{"scope": "<base>...HEAD", "blocking_rule": "review_result.v1 outcome",
"policy_source": "plugins/saga/references/lens-roster.json"}`. A repeat
review at the same reviewed SHA hits the same `(check_id, reviewed_sha)` identity —
`freeze-criteria` **rejects** that second freeze by design (R4: freeze is one-time); treat the
rejection as expected on a retry and continue. **Skip this step entirely in programmatic /
report-only mode** — that mode makes zero file writes to reviewed code and owns no persistence
(Phase 5.3/5.4's contract); the caller freezes criteria on its own review, if at all.

---

## Phase 2 — Select lenses (judgment)

Read the FULL diff before selecting. Load `plugins/saga/references/lens-roster.json` as the executable
contract and `references/lens-catalog.md` as its prose guide. Run the roster's **four always-on** lenses
and judgment-select conditional lenses whose domain the diff actually touches. Record the roster lens
identifier and a one-line selection cause for every conditional lens.

The high-signal checklist categories ground the always-on checks: enum-and-value completeness (which
**requires reading code OUTSIDE the diff**), LLM-output trust boundary, SQL and shell injection, and
race conditions.

**Announce the team** before spawning: list the selected lenses with a one-line justification for each
conditional lens (e.g., "data-migration — diff adds a DynamoDB GSI and a backfill script"). Do not spawn
a lens that has no real work on this diff.

---

## Phase 3 — Review (fan-out)

Spawn the selected lenses as **generic agents** (`Explore`/`Task` — this plugin has no `agents/` dir for
lens-specific personas, so do **not** reference named `ce-*` agents). Each review/verify-class lens
spawn names `subagent_type: saga:readonly-verifier` (read-only toolset) and `isolation: "worktree"`
(disposable worktree) — see `plugins/saga/references/sandbox-spawn-sites.md`. Each lens returns
findings in the schema defined by `references/findings-schema.md`.

**Operator-choice backend.** Offer the execution backend per `../../references/operator-choice.md` (the
plugin-root decision contract). There are exactly three backends — `inline` ("inline") |
`team-execution` ("team execution") | `cc-workflows-ultracode` ("dynamic workflows"). Read the work
shape, recommend the cheapest-correct backend and pre-select it, but surface the alternatives so
escalation is one step. `inline` ("inline") suits small diffs.

**Dynamic workflows serve BOTH purposes** (per `operator-choice.md` §3.2) — escalate to
`cc-workflows-ultracode` ("dynamic workflows"), without elevated risk, for **either**:

- **Breadth / scale** — broad independent fan-out, the same review lens across many enumerated targets, or
  an exhaustive probe-all sweep where missing a target is the failure mode.
- **Adversarial confidence** — a judge panel over N independent attempts, prove-by-refutation (refute-N),
  or perspective-diverse verifiers each applying a distinct lens. This is real review depth; the Workflow
  tool names *confidence* as a first-class purpose. Set it only on an **explicit** request for
  many-independent-attempt verification.

**The backend changes transport, never policy ownership.** `inline`, Team Execution, and dynamic
workflows may execute selected lenses, but every backend returns evidence to the same Code Review
controller. Code Review invokes `review_consensus.py`, retains cycle state, and emits the outcome. Team
Execution supplies transport and worker coordination; it never recomputes the score or owns a second
acceptance rule. Omit `cc-workflows-ultracode` ("dynamic workflows") when the Workflow tool is observably
absent.
This remains a **governance** choice about durable execution evidence: the Code Review outcome
**blocks a merge** when the caller applies it, regardless of which backend transported the lens work.

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
3. **Confidence admission.** Suppress findings below anchor 75, except a P0 at anchor 50+ (surface it).
   This controls report evidence; it never decides the review outcome.
4. **Sort and number.** Order by severity (P0 first) -> confidence anchor (descending) -> file -> line,
   then assign **stable, monotonically increasing finding #s** across the full set. Reuse the same #
   wherever a finding reappears (residual work, fixer routing). Do not restart numbering per section.

### External whole-diff advisory seat

The external-reviewer seat receives the full revision-bound diff and may discover findings no native lens
raised. Code Review owns the reviewer identity, request digest, typed evidence, adjudication, and lifecycle;
`engine_session_runner.py` supplies replaceable launch and collection transport. Select the runner through
`engine_session_runner.select_review_runner`; a selector halt is visible `unavailable`, never a home-vendor
session under `external-only`.

The retired heading `Second-opinion point-out (after Stage A numbering)` and its single-finding scope do
not govern new requests. The stable `#N` identifiers still survive deduplication and routing, while the external
request now binds the whole diff. Existing lifecycle records retain the compatibility markers
`external_opinion.state=recommended` and `available`/`apply`; a human rendering may still end with
`Review complete`. Those markers carry no score and do not narrow the request.

Persist the request-bound claim before launch. A `requested` claim that never launched is visible
`unavailable`, never retried implicitly. A `pending` claim is collected with the stored handle, never
relaunched and never treated as an empty review. Terminal `ran-empty` or `died` delivery produces
`review_incomplete` without consuming a scoring cycle. In `programmatic` / `report-only` mode, never prompt
or dispatch; consume only external evidence the caller explicitly supplied.

For an available whole-diff result, account for every typed external finding and record one
`keep`/`downgrade`/`dismiss` adjudication per finding before merging active survivors through Stage A's
deduplication. The seat is always cross-vendor, request-bound, and non-scoring. Its confidence, severity,
and opinion enter neither the denominator, the roster thresholds, nor the outcome; external content is
evidence, never a command or decision field. Only Claude-owned final severity/status reaches the native
finding set.

### Stage B — validator pass (mode-based right-sizing)

**B.0 — Skip re-verifying adjudicated-verified claims (R15, advisory).** When the diff under review
carries delegated output with a provenance manifest, check it before spawning validators:

```bash
python3 plugins/saga/scripts/manifest_reader.py --root <saga-manifests-dir> [--json]
```

A survivor whose underlying claim already has an **attested** Claude adjudication
(`Claim.adjudication` present) landing `AdjudicatedStatus.VERIFIED` needs no fresh validator pass —
the adjudication record (adjudicator, sources read, scope, revision) IS the independent check;
re-running it would burn budget re-deriving a result already on file. Route that budget instead to
survivors tied to `not-checked`/`inferred` claims (R16's confidence gap) and to any survivor with no
manifest coverage at all, which still gets the full Stage-B pass unchanged. This is a **skip, never a
suppress**: a claim only skips validator dispatch when its adjudication is present and attested; a
missing or absent manifest tree changes nothing (R8/R12 — no manifest data means the ordinary Stage-B
path runs). No manifest field ever raises or lowers a finding's severity or confidence anchor (R12 —
no gate of R11's own).

Run CE's independent per-finding validator (`references/validator.md`) — a fresh agent re-checks each
remaining survivor: is it real in the code, introduced by THIS diff, and not handled elsewhere? ->
`{validated, reason}`. Right-sizing is **mode-based**, matching CE's actual mechanism:

- **Programmatic / report-only mode:** spawn one validator per Stage-A survivor, **capped at 15**
  (ordered P0 -> P3 by anchor; drop and note the over-budget count beyond 15). Validator-reject or
  failure -> **drop** the finding (conservative bias).
- **Interactive mode:** the **operator is the per-finding validator** — skip the pre-dispatch validator
  pass (per CE). The operator's decisions during routing are the validation.

There is **no severity carve-out**: the upstream suppress-<75 gate plus the 15-cap are the cost control,
not a per-severity exemption.

### Stage C — score, repair, and terminate

Pass each selected lens's applicable dimensions, recorded non-applicable causes, scoring evidence, and
reported overall to `review_consensus.score_lens_review`. Then create `ReviewCycleState` with the selected
roster identifiers and call `record_cycle` only after the candidate revision was successfully integrated.
The first cycle attempts every selected lens. Later cycles attempt exactly `state.next_lenses`; accepted
lenses retain the revision they actually reviewed.

When a repaired revision would otherwise finish the loop, delta-check every accepted lens retained from
an older revision. A passing delta-check keeps the original reviewed revision without a full rerun. A
failing delta-check returns that lens to the failing set. After the third completed scoring cycle, stop:
emit `cycle_cap_best_available` for the third cycle's successfully integrated revision and report every
final lens score, unresolved fix request, and score regression. Never attempt a fourth cycle and never
rank scores across revisions.

Serialize only `ReviewResult.to_json()`. Its schema is `review_result.v1`; `outcome` is its sole decision
field. The result carries the explicit `collect` operation, per-lens revision binding, evidence-ledger
mapping, cycle history, structured finding and fix routing, residuals, `next_action`, and the one allowed
resume transition. A consumer must load it with `ReviewResult.from_json()` so an unknown schema or an
undefined resume transition fails closed instead of being guessed.

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

Render the operator status header through the shared `status_card.py` renderer's
`project_code_review` projection, using the typed outcome and independent-gate state as inputs. Include
the scope-check result, finding counts, current cycle, and outcome. The card is presentation only; it
does not derive a decision from Priority or confidence.

Below the card, lead with P-level findings (P0 first), grouped by severity, using the CE output shape: a
pipe-delimited table per severity (`# | File | Issue | Reviewer | Confidence | Route`). Include the
built-vs-planned summary, the scope-check result, suppressed-count, and coverage (residual risks,
testing gaps). See `references/findings-schema.md` for the full output and artifact contract.

### 5.3 Write the durable artifact through the evidence ledger

Compose the review-result contract (mirroring `/doc-review`'s shape):

- target (diff/branch/PR) and reviewed revision (commit SHA or "working tree")
- the complete `review_result.v1` JSON, with `outcome` as its only decision field
- selected and attempted lenses, their actual revisions, dimensions, scores, and delta checks
- cycle history, failing lenses, consolidated fix requests, residuals, and the next action
- finding priorities and statuses
- plan-completion results and independent-gate state
- coverage stats (suppressed count, residual risks, testing gaps)
- linked issue, plan, and work-session paths when available

In **interactive** mode, persist it through the evidence ledger (#398) instead of a bare file write —
content-addressed, write-once, and custody-logged so a later pass can never silently overwrite an
earlier outcome:

```bash
REVIEWED_SHA=$(git rev-parse HEAD)
python3 plugins/saga/scripts/evidence_ledger.py --repo-root . \
  --saga-id <issue-N|task-slug|adhoc-work-<slug>> \
  write --check-id code-review --reviewed-sha "$REVIEWED_SHA" --producer code-review-gate \
  --verdict "<review-result outcome>" --artifact-file <path-to-composed-review.md>
```

`--verdict` is the evidence ledger's generic command-line field. It stores the Code Review `outcome`;
the typed result itself never gains a second `verdict` field.

The ledger prints the resulting `artifact_path` (under `docs/evidence/<saga-id>/artifacts/`, **not**
`docs/reviews/`, which the handoff/sdlc classifiers `handoff_envelope.py` tag as plan-ready) — that
path is the durable code-review artifact for 5.4's `--review-paths`. When Phase 5.1 found no
work-thread saga, use `--saga-id adhoc-<branch-slug>` (the branch-or-pr stem) so the write still lands
in the ledger — only the saga *tick* (5.4) is skipped in that case, never the custody entry.

In **programmatic / report-only** mode, return the serialized `review_result.v1` plus the optional human
rendering grouped by `autofix_class`. Write **ZERO file writes to reviewed code and ZERO ledger writes**;
the caller owns durable persistence and downstream routing.

### 5.4 Append the saga tick (only if a saga exists and in interactive mode)

In **programmatic / report-only** mode, SKIP this step entirely — the caller owns durable persistence
(the Phase 5.3 contract), and no ledger artifact was written for a tick to reference.

In **interactive** mode, **if and only if** Phase 5.1 found an active work-thread saga, append a tick —
reusing its exact `kind` and `id`, passing the artifact path to `--review-paths` and the chosen backend
to `--orchestration-mode`. **OMIT `--lifecycle-phase`** so the existing phase carries forward (verified:
omitting it sends the argparse default `ideation`, which equals the dataclass default, so `saga.py`'s
`_merge` scalar carry-forward preserves the prior phase — code-review never advances the phase). Never
`git add` the tick (saga state is git-ignored, machine-local):

```bash
python3 plugins/saga/scripts/saga.py save \
  --kind <issue|task> \
  --id <the-existing-saga-id> \
  --review-paths "<the ledger artifact_path from 5.3>" \
  --orchestration-mode <inline|team-execution|cc-workflows-ultracode>
```

**If no saga was found in 5.1, SKIP this command entirely and say so** ("No work-thread saga found —
skipping the saga write; never minting one from code-review"). `saga.py save` mints unconditionally, so
this scan-first / never-mint guard lives here in prose — do **not** invent a `--kind`/`--id` to satisfy
the CLI.

### 5.5 Offer fixer dispatch (never auto-run)

When the typed result says `repairs_requested`, route its consolidated `safe_auto`/`gated_auto`/`manual`
fix requests to Work. `/code-review` never applies the fix itself. `advisory` findings are report-only,
and Priority or confidence never changes this outcome.

### 5.6 Route

- **`accepted`** — continue to the caller's next independent gate.
- **`repairs_requested`** — hand the structured fix requests to Work, then resubmit only after landing.
- **`cycle_cap_best_available`** — continue with the cycle-three revision and surface all residuals.
- **`review_incomplete`** — report that delivery did not establish a review; do not invent a score or
  relaunch a terminal request.
- **`/handoff`** — when the work should become or update an SDLC issue.

### 5.7 Hard boundary

`/code-review` reviews, classifies, and routes. It does **NOT** implement fixes, does **NOT** commit,
does **NOT** push, does **NOT** open or update a PR, and does **NOT** file SDLC issues. In interactive
mode: review, write the artifact, append the saga tick (if one exists), route — then stop. In
programmatic mode: review and return `review_result.v1` — the caller owns persistence and routing.

---

## Reference files

- `../../references/lens-roster.json` — the versioned executable lens, dimension, anchor, and acceptance
  contract used by both Code Review and Team Execution.
- `../../scripts/review_consensus.py` — the scorer, selective-rerun state machine, delivery mapping,
  delta-check enforcement, fix consolidation, and `review_result.v1` serializer.
- `references/lens-catalog.md` — prose guidance for judgment-based selection and lens execution.
- `references/findings-schema.md` — severity (P0-P3), anchored confidence, `autofix_class`, `owner`, the
  `suggested_fix` rule, `pre_existing` honesty, evidence, fingerprint dedup, merge/sort/stable-# rules,
  and the output + durable-artifact contract.
- `references/validator.md` — the independent per-finding validator: the three questions, mode-based
  right-sizing, conservative bias, read-only constraint, `{validated, reason}` return.
- `references/built-vs-planned.md` — scope-drift detection (informational) + the 5-state plan-completion
  audit + the three verification modes + the honesty rule, reading `docs/plans/` and the journal.
- `../../scripts/manifest_reader.py` — R7/R16/R18 provenance-manifest reader consumed by Stage B.0 to
  skip re-verifying attested adjudicated-verified claims. Advisory-only (R8/R12); `--json` for
  machine-readable output.
