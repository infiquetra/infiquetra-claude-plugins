---
name: code-review
description: Run a structured Infiquetra code-quality review at the work-to-PR boundary. Reads the merge-base diff, runs a built-vs-planned audit plus the four always-on lenses and operator-approved conditionals, validates findings, writes a durable review artifact, appends to the work-thread saga, and routes — never mutating reviewed code, and publishing only its own review artifact (interactive mode, §5.7). Triggers on "review this PR", "code review", "check my diff", "pre-PR review", or a /work hand-in before shipping.
---

# Code Review

`/code-review` answers **"Is this code safe to merge?"** It is a code-quality review **lens** that
fires at the **work -> PR boundary**: after `/work` produces code, before a PR is opened or a merge
happens. It reads a diff (working tree, branch, or PR), audits built-vs-planned, runs the lenses the
diff actually warrants, validates the surviving findings, classifies and routes them, and writes a
durable review artifact. It reports and routes. It never implements the fixes it requests — the author
or the Work process owns repair changes and implementation commits — never opens or updates a PR, and
never files issues. The one write lane it holds is its own review artifact: in **interactive /
standalone** mode it may write, commit, and push that artifact and submit the GitHub pull-request
review on an existing PR (§5.7). In **programmatic / report-only** mode it makes **ZERO durable
writes** — the caller owns persistence.

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
   reviewed source, does **NOT** implement the fixes it requests (fixer dispatch is *offered*, never
   auto-run), does **NOT** open or update a PR, and does **NOT** file SDLC issues (`/work`, ship gates,
   and `mission-control` own those). Its one write lane is its own review artifact (§5.7): in
   **interactive / standalone** mode it may write, commit, and push that artifact and submit the
   GitHub pull-request review on an existing PR; in **programmatic / report-only** mode it makes
   **ZERO file writes to reviewed code** and is strictly read-only over the diff.
2. **Verify, don't guess.** Every finding cites `file:line` evidence. Claims of "safe", "handled
   elsewhere", or "tested" must cite the proving line, the handling code, or the test name — or be flagged
   as unverified. Never say "likely handled" or "probably tested". "This looks fine" is not a finding:
   either cite evidence it IS fine or flag it as unverified. This is Jeff's no-lies rule and it is the
   engine's spine.
3. **Confidence-classified and deduped.** Findings carry anchored confidence metadata
   (0/25/50/75/100), are admitted to the report by the findings-schema rules, and are deduplicated by
   fingerprint (`path:line:category`). Confidence and Priority never decide review acceptance. Honor
   `pre_existing`: do not blame this diff for old code it merely touched.
4. **Always-on four, then one batched approval.** Load `plugins/saga/references/lens-roster.json`.
   Auto-run exactly the four always-on lenses — `architecture-maintainability`, `correctness`,
   `security`, `testing`. Recommend conditionals with one plain-language reason each. Do not launch
   any conditional lens until an approval record exists for this reviewed commit and cycle. Present
   one batched operator choice: accept-recommended (the default) / always-on-only / customize. A
   caller- or Orchestrate-supplied selection **is** that approval — do not ask again. Persist the
   record on the existing review-cycle state in `review_consensus.py`. Reuse it on repair cycles
   unless applicability changes, then ask once about only the delta. Dismissal or no answer pauses
   with no conditional launches. No hidden or supplemental lenses outside the approved set.
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

Use `AskUserQuestion` for choices from a known set (review mode, conditional-lens approval,
execution backend, fixer-dispatch routing). Call `ToolSearch` with `select:AskUserQuestion` first if
its schema is not loaded. Ask one question per turn, except the lens-selection gate may share its
widget with backend selection when the client supports a multi-question payload — that is still one
interaction. For open-ended discussion, ask inline in chat. Never silently skip a question.

In a channel session (`redis-channel` active), `AskUserQuestion` cannot be called — inline the choices
in your reply text instead. Follow the canonical channel-inline convention in
`saga/skills/brainstorm/SKILL.md` (do not duplicate its wording here).

<!-- gate-record: id=code-review-interaction absence=HALT transport=ask-user-question -->
**Operator-absence contract (#371).** Every known-set gate above declares what happens on
silence, and the declaration above this line is the contract. `HALT` here: stop and wait. A timeout,
a widget error, or a dropped session is never consent — do not proceed on a default and do not
invent an answer. On the conditional-lens gate, dismissal or no answer **pauses**: run the always-on
four only, launch no conditional lens, and persist no approval record. Ask one question at a time
and read the decision from the operator's actual answer, never from a widget's raw return value.

Use repo-relative paths in every generated document. Absolute paths break portability across machines
and worktrees. (The one exception is the saga `--review-paths` value — see Phase 5.)

## Reviewer-session transport

Orchestrate owns every reviewer session. Do not launch or collect an external reviewer
through `engine_session_runner.py`, `engine_offer.py`, or any other saga transport.
Do not consult `engine-registry.yaml` as a launch authority — it is capability metadata
only and cannot override the live Orchestrate/Herdr roster.

When this review runs as an Orchestrate unit, the run record already names the
review-controller and any `external-reviewer` seats (vendor, model, effort, worktree).
Consume revision-bound evidence those seats return. If a requested reviewer is not in
the Orchestrate run record, HALT — do not invent a custom review, do not fall back to
the retired runner, and do not dispatch a subagent, hidden subprocess, or unowned
terminal session as a substitute.

In a standalone `/code-review` (no Orchestrate run), the operator is the transport:
ask them to add reviewer seats through Orchestrate `expand`/`go`, or proceed without
an external seat. Never prompt via `.saga/engine-prefs.json`.

The in-session lens fan-out (Explore/Task) is the consensus-panel roster, which is
separate from reviewer-session transport. Code Review still owns scoring, consensus,
and `review_result.v1`.

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

## Phase 2 — Select lenses (always-on auto-run, then one batched approval)

<!-- gate-record: id=code-review-conditional-lens-approval absence=HALT transport=ask-user-question -->
Read the FULL diff before recommending. Load `plugins/saga/references/lens-roster.json` as the
executable contract and `references/lens-catalog.md` as its prose guide. Drive the launch set through
`review_consensus.resolve_lens_selection` / `launch_approved_lenses` so the approval record lives on
the existing review-cycle state (reviewed commit + cycle) — not a new store. Issue #418's selection
adapter may produce candidates and reasons; it **cannot** approve a launch.

1. **Auto-run the always-on four.** Spawn `architecture-maintainability`, `correctness`, `security`,
   and `testing` with no operator question. Omitting any one is a defect. These are the only lenses
   that may receive an Agent/Task call before an approval record exists.
2. **Recommend conditionals.** Judgment-select zero or more conditional lenses whose domain this diff
   actually touches. Record the roster identifier and one plain-language reason each (e.g.,
   "api-contract — diff changes the public command schema"). Filename or keyword matching is not
   sufficient. Do not recommend a lens with no applicable dimension. Do not omit one because another
   overlaps it.
3. **One batched question, before any conditional launch.** If any conditional is recommended and no
   approval already exists for this reviewed commit and cycle, ask **one** operator question whose
   choices are exactly `accept-recommended` (the default), `always-on-only`, and `customize`.
   Combine this question with execution-backend selection in the same AskUserQuestion payload when
   the client supports multiple questions in one widget. Otherwise ask lens selection first.
4. **Caller- or Orchestrate-supplied selection is approval.** If the caller, `/work`, or an
   Orchestrate run record already named the conditional set, pass it as `caller_selection` (source
   `caller` or `orchestrate`). Do not re-ask. Persist that record and launch exactly those
   conditionals plus the always-on four.
5. **Persist against reviewed commit + cycle.** Call `ReviewCycleState.record_lens_approval` (or let
   `resolve_lens_selection` do it) so the record is keyed by reviewed commit and review cycle. Round-
   trip it with the existing `review_cycle_state.v1` payload; do not invent a parallel store.
6. **Reuse on repair cycles; ask only the delta.** On a later cycle, if judged applicability is
   unchanged, reuse the approved set and do not re-ask. If the diff newly makes a conditional
   applicable, ask once about **only that delta**. Drop conditionals that are no longer applicable
   without asking (they have no work). Still-applicable previously approved lenses stay.
7. **Pause on dismissal or no answer.** Do not default to `accept-recommended`. Launch no conditional
   lens. Persist no approval. The always-on four may already be running; they are not rolled back.
8. **No hidden lenses.** Spawn only `launch_approved_lenses`'s return value. Do not add supplemental
   or unofficial lens reviews outside the approved set. External advisory seats are a separate
   transport concern and are not a native lens approval.

The high-signal checklist categories ground the always-on checks: enum-and-value completeness (which
**requires reading code OUTSIDE the diff**), LLM-output trust boundary, SQL and shell injection, and
race conditions.

In **programmatic / report-only** mode the caller supplies `caller_selection` (empty means
always-on-only). If it supplies none, treat that as pause: always-on four only, no conditional Agent
calls, no invented approval.

---

## Phase 3 — Review (fan-out)

Spawn **only the approved launch set** as **generic agents** (`Explore`/`Task` — this plugin has no
`agents/` dir for lens-specific personas, so do **not** reference named `ce-*` agents). Call
`launch_approved_lenses` (or refuse any conditional spawn while `state.lens_approval_for(commit,
cycle)` is missing) **before** the Agent/Task call. Each review/verify-class lens spawn names
`subagent_type: saga:readonly-verifier` (read-only toolset) and `isolation: "worktree"` (disposable
worktree) — see `plugins/saga/references/sandbox-spawn-sites.md`. Each lens returns findings in the
schema defined by `references/findings-schema.md`.

**Operator-choice backend.** Offer the default Saga execution backends per
`../../references/operator-choice.md` (the plugin-root decision contract, as narrowed by issue #808).
The default offer presents `inline` ("inline") and `team-execution` ("team execution").
`cc-workflows-ultracode` ("dynamic workflows") remains a recorded enum value and is available only by
**explicit invocation** inside a managed Claude Code session, or when an already-approved plan records
that choice. Read the work shape, recommend the cheapest-correct Saga backend (`inline` or
`team-execution`) and pre-select it. `inline` suits small diffs; `team-execution` suits multi-reviewer
gated consensus. When the Phase 2 lens-selection question is still open, attach this backend choice to
that same operator interaction. When a caller-supplied or reused approval already closed lens selection,
ask backend alone.

**Claude Code Workflows still serve both purposes** (per `operator-choice.md` §3.2) — **breadth / scale**
(broad independent fan-out across many targets) and **adversarial confidence** (judge panels,
prove-by-refutation / refute-N). These describe **when an operator might explicitly invoke** a Workflow;
they are **never** default or automatic offer triggers and must never pre-select `cc-workflows-ultracode`.

**The backend changes transport, never policy ownership.** `inline`, Team Execution, and explicitly
invoked Claude Code Workflows may execute selected lenses, but every backend returns evidence to the
same Code Review controller. Code Review invokes `review_consensus.py`, retains cycle state, and emits the
outcome. Team Execution supplies transport and worker coordination; it never recomputes the score or
owns a second acceptance rule. Code Review retains its own lenses, consensus, and acceptance policy
regardless of where a workflow step runs. Omit `cc-workflows-ultracode` when the Workflow tool is
observably absent.
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
raised. Code Review owns the reviewer identity, request digest, typed evidence, adjudication, and lifecycle.
Orchestrate launches and collects that seat as a named Herdr session (`role: external-reviewer` through
`expand`/`go`). Halt rather than falling back to the retired saga runner or inventing a custom review.

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

For every recorded finding owned by a scoring lens, construct a `FindingEvidence` value with the same
finding and dimension identifiers, its critical and resolved evidence state, and its Priority and
confidence metadata. Pass those values through the `findings` argument together with each selected
lens's applicable dimensions, recorded non-applicable causes, and reported overall to
`review_consensus.score_lens_review`. The full `ReviewFinding` values passed to `record_cycle` must name
the same finding and dimension records; the cycle controller reconciles the two forms and refuses a
typed result whose routed findings were not scored.

After collecting the selected `LensScore` values, construct `IndependentGateResult` values for the
built-versus-planned audit and every applicable scanner, test, deployment, casualty, and
operational-safety gate. Call `review_consensus.evaluate_review_readiness` with the scores and those
independent gate results. Enforce `ReviewReadiness.can_proceed`: a failed independent gate blocks
readiness even when numeric review acceptance passes. A gate result never changes a dimension score,
derived overall, accepted flag, or failing-dimension list; do not rescore a lens from gate state.

Then create `ReviewCycleState` with the selected roster identifiers and call `record_cycle` only after
the candidate revision was successfully integrated. The first cycle attempts every selected lens.
Later cycles attempt exactly `state.next_lenses`; accepted lenses retain the revision they actually
reviewed. `ReviewResult.outcome` remains the sole decision field inside the serialized result; carry
the independent `ReviewReadiness` state alongside it rather than rewriting that outcome.

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

In **interactive / standalone** mode only, the reviewer may also publish the artifact itself: it may
commit and push the review artifact (at its own path — `docs/code-reviews/` or the ledger artifact
path above, never anything else) to the branch under review, and submit the GitHub pull-request
review on the existing PR. That commit is **evidence only**, never an implementation commit: the
artifact's frontmatter records `reviewed_revision` as the full 40-character commit SHA of the exact
implementation revision reviewed, and the commit subject names that revision. An abbreviated SHA or a
symbolic ref like `HEAD` is not a valid reviewed revision — it stops meaning anything once the branch
moves.

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
fix requests to Work (`dispatch_repairs` in `review_consensus.py` is the existing hand-back path).
`/code-review` never applies the fix itself and never authors a fix for a finding it raised: **the
author or the Work process owns repair changes and implementation commits**, and the reviewer hands
findings back. `advisory` findings are report-only, and Priority or confidence never changes this
outcome.

### 5.6 Route

- **`accepted`** — continue to the caller's next independent gate.
- **`repairs_requested`** — hand the structured fix requests to Work, then resubmit only after landing.
- **`cycle_cap_best_available`** — continue with the cycle-three revision and surface all residuals.
- **`review_incomplete`** — report that delivery did not establish a review; do not invent a score or
  relaunch a terminal request.
- **`/handoff`** — when the work should become or update an SDLC issue.

### 5.7 Hard boundary

`/code-review` reviews, classifies, and routes. It does **NOT** implement the fixes it requests — the
author or the Work process owns repair changes and implementation commits — does **NOT** mutate
reviewed source, does **NOT** open or update a PR, and does **NOT** file SDLC issues. The one granted
write lane is **review-artifact publication**, and only in **interactive / standalone** mode: write,
commit, and push the review artifact at its own path (`docs/code-reviews/` or the evidence-ledger
artifact path), and submit the GitHub pull-request review on the existing PR. That commit is evidence
only and names the exact implementation revision reviewed (full 40-character `reviewed_revision` in
the artifact frontmatter) — it is never an implementation commit. When `/work` is the caller the
review runs in **programmatic / report-only** mode, where nothing changes: ZERO durable writes, no
commit, no push, no review submission — `/work` persists through the evidence ledger, which does not
advance `HEAD`, so its `REVIEWED_SHA` staleness check stays valid.

In interactive mode: review, write the artifact, (optionally publish it per the publication lane above),
append the saga tick (if one exists), route — then stop. In
programmatic mode: review and return `review_result.v1` — the caller owns persistence and routing.

---

## Reference files

- `../../references/lens-roster.json` — the versioned executable lens, dimension, anchor, and acceptance
  contract used by both Code Review and Team Execution.
- `../../scripts/review_consensus.py` — the scorer, selective-rerun state machine, delivery mapping,
  delta-check enforcement, fix consolidation, `review_result.v1` serializer, and the conditional-lens
  approval record bound to reviewed commit + cycle (`resolve_lens_selection`,
  `launch_approved_lenses`).
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
