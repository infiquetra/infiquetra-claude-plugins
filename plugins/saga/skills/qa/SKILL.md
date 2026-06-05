---
name: qa
description: Run a risk-driven Infiquetra acceptance-evidence QA gate on shipped work. Restores the work-thread saga, classifies the change into risk classes, runs acceptance checks (including browser behavior via the installed MCP), gathers evidence, assigns severity, derives a ship verdict, writes a durable QA artifact, advances the saga qa-track on pass, and routes by merge state — without fixing, committing, or deploying. Triggers on "qa", "run QA", "does this actually work", "acceptance check", "ship-readiness", or a /work or /code-review hand-in after merge.
---

# QA

`/qa` answers **"Does the shipped thing actually work?"** It is the **acceptance-evidence GATE**
downstream of `/work` and `/code-review`: after code is built, reviewed, and (usually) merged, `/qa`
runs the acceptance checks the change actually warrants, gathers evidence, assigns severity, derives a
ship verdict, and routes. It reports and routes — it does **not** fix, commit, push, open or merge a
PR, deploy, file SDLC issues, or set readiness labels.

## Position in the lifecycle

`/qa` is the saga `LIFECYCLE_PHASES` `qa` slot — the gate after execution:

- `/plan` answers: "How should it be built?"
- the `review` phase (`/doc-review`) answers: "Is this plan ready to execute?"
- `/work` answers: "Build it." (and calls `/code-review` before opening a PR)
- `/code-review` answers: "Is the built code safe to merge?" (a within-work code-quality lens)
- **`/qa` answers: "Does the shipped thing actually work?"** (this engine — the acceptance gate)

`/code-review` reads the *diff*; `/qa` reads the *running behavior and acceptance evidence*. `/qa` is an
**advisory router node**: it produces a verdict and routes, but it **never blocks the router** (`/loop`
treats a `/qa` route as advisory) and it normally runs **post-merge**. `/work` (`work/SKILL.md`) routes
here advisorily after merge and explicitly **deferred the `qa` phase advance to this rebuild** — `/qa`
lands that advance (Phase 6).

## Core principles

1. **Gate, not fixer.** `/qa` reports, assigns severity, derives a verdict, and routes. It does **NOT**
   fix bugs, does **NOT** edit reviewed code, does **NOT** commit, does **NOT** push, does **NOT** open,
   update, or merge a PR, does **NOT** deploy, does **NOT** file SDLC issues, and does **NOT** set
   readiness labels. All fixing and deep root-cause work belongs to `/work` (round-N), the existing
   fixers, and `/investigate` (the systematic-debugging engine). Fixer dispatch is *routed*, never run
   here.
2. **Risk-driven.** Classify the change into the **9-way risk router** — behavior, security, infra, API,
   deployment, data, docs, config, trivial — and run only the classes the change actually touches,
   narrow before broad. Browser behavior folds into the **behavior** class as one MCP-driven check
   (`references/risk-taxonomy.md`), a graceful no-op for non-UI repos.
3. **Evidence + falsifiable prediction.** Every finding cites concrete evidence — a `file:line`, a check
   command's output, a log line, a network response, or an MCP screenshot/console capture. "It looks
   broken" is not a finding. For each failure whose **cause is uncertain**, state a `ce-debug`-style
   **falsifiable prediction**: "if this is the real cause, then X in a different path/scenario must also
   fail." A wrong prediction means you found a symptom, not the cause — and the prediction gives the
   routed fixer a head start. When the cause is obvious (clear stack trace, explicit null), the evidence
   itself is sufficient; the prediction is for uncertain links only.
4. **Score AND severity-banded verdict.** Each finding carries a severity
   (critical / high / medium / low) with a documented cross-walk to `/code-review`'s P0-P3. `/qa`
   reports **both** a deterministic 0-100 health **score** *and* a **ship verdict**, and they play
   different roles. The score is a **real PORT of gstack's Health Score Rubric formula** — not an
   invented number: `qa_health_score.py` applies gstack's verbatim per-finding deductions
   (critical -25 / high -15 / medium -8 / low -3, floored at 0 per class) over documented infiquetra
   ship-risk class weights, re-normalized across the in-scope classes (`references/qa-report.md`). The
   honest caveat: the score's *inputs* are LLM-assigned severity counts, so the number is **one
   signal**, not the gate. The **gate decision** is the severity-banded ship verdict — `ship` /
   `ship-with-deferred` / `no-ship` — **derived** from the tier's blocking threshold; pass/fail is
   stated **per risk class**. Report the score alongside the verdict; the verdict decides.
5. **Saga qa-track consumer.** `restore` the work-thread saga, write `qa_paths`, and **on PASS advance**
   `lifecycle_phase` from `work` to `qa` (the deferred advance). On FAIL, keep `lifecycle_phase=work`
   and record the evidence. `/qa` never edits `saga.py` — every flag it uses already exists.
6. **Route, don't execute.** PASS routes to `/handoff` or `/retro`. FAIL routes by **merge state**:
   pre-merge to `/work` (re-enter the round-N loop), post-merge to `/handoff` to open a new defect
   thread. Routing **reads** `loop/references/dispatch-table.md` — it never restates the table.

## Interaction method

Use `AskUserQuestion` for choices from a known set (tier, execution backend for large/parallel
verification, FAIL routing target). Call `ToolSearch` with `select:AskUserQuestion` first if its schema
is not loaded. Ask one question per turn; never silently skip a question.

In a channel session (`redis-channel` active), `AskUserQuestion` cannot be called — inline the choices
in your reply text instead, following the canonical channel-inline convention in
`saga/skills/brainstorm/SKILL.md` (do not duplicate its wording here).

Use repo-relative paths in every generated document. Absolute paths break portability across machines
and worktrees. (The one exception is the saga `--saga-id` value — a derived id, not a path.)

---

## Phase 0 — Enter, parse, restore, scope the diff

Parse arguments and establish the change scope before running any check.

### 0.1 Parse the target and tier

- **Target:** the issue/PR (`#N`), a branch name, a diff, or a free-text scope. Strip recognized tier
  tokens before treating the rest as a target.
- **Tier (default Standard):** `Quick` / `Standard` / `Exhaustive` — these set which severities **block**
  the ship verdict and the verification depth (`references/risk-taxonomy.md` and `references/qa-report.md`).

### 0.2 Restore the work-thread saga

Find and restore the saga for this change so the gate advances the same thread `/work` built. Use the
exact `kind` and `id` (or run `saga.py scan` first to locate the active thread, then restore by id):

```bash
python3 plugins/saga/scripts/saga.py restore --saga-id <issue-N|task-slug>
```

Capture the restored `lifecycle_phase`, the integer `phase`, `issue_ref`, `plan_path`, `branch`, and
`pr_refs` — you reuse them verbatim in Phase 6. If no saga is found, `/qa` still runs and writes the
artifact, but the saga tick is skipped (say so) — never mint a saga from `/qa`.

### 0.3 Determine the diff (diff-aware mode)

**Pre-merge / branch case** — reuse `/code-review`'s stale-base merge-base mechanic (fetch first so
stale local state does not produce false positives), then map changed files to risk classes:

```bash
git fetch origin <base> --quiet
DIFF_BASE=$(git merge-base origin/<base> HEAD)
git diff --name-only "$DIFF_BASE"
```

`<base>` is the PR base branch (`gh pr view <N> --json baseRefName -q .baseRefName` when a PR exists) or
the repository default branch.

**Post-merge case** — the work is already on `main`, so `<base>...HEAD` (three-dot) is **empty**. Read
the merge commit's changeset from the PR instead:

```bash
gh pr view <N> --json files
```

Map the changed file paths to risk classes with the file-pattern map in `references/risk-taxonomy.md`.

### 0.4 Read the prior overall score (baseline-from-prior-report)

If the restored saga carries a most-recent `qa_paths` entry, **read that prior QA report** and extract
its `## Health Score` overall (0-100). Pass it to the Phase 4 scorer as `--baseline-score <prior>` so
the run emits a `delta`. There is **no `baseline.json`** and **no saga baseline field** — the baseline
is read straight from the prior report the saga points at (the gstack regression-daemon is dropped).
First run for a thread has no prior `qa_paths`: omit `--baseline-score` (the scorer emits
`delta: null`).

---

## Phase 1 — Risk classification

Decide which of the 9 risk classes are in scope. Combine three signals:

1. The diff-aware file→class map from Phase 0.3.
2. The plan's verification section (`saga.plan_path` → `docs/plans/...`) — the acceptance criteria the
   build was supposed to satisfy.
3. `references/risk-taxonomy.md` — the per-class acceptance/evidence checklist.

A change usually lands in 1-3 classes. **trivial** short-circuits to a quick read-and-confirm.
**behavior** with a UI surface pulls in the browser MCP check (one class, not seven web categories).

---

## Phase 2 — Run checks per class

For each in-scope class, run the acceptance checks from `references/risk-taxonomy.md`, narrow before
broad, and gather **evidence** for every result:

- **behavior** — repo test commands; for a UI surface, drive the running app with the installed
  **chrome-devtools / playwright MCP** (navigate, interact, read console + network) and capture
  screenshots/console as evidence. Graceful no-op for serverless / SDK / Ansible / plugin repos.
- **security** — the per-class checklist; **offer** an `appsec-audit` (operator-choice) for a real trust
  boundary; never run a destructive probe.
- **deployment / infra** — **READ** deploy state / inventory and confirm acceptance evidence; **never
  mutate** infrastructure or deploy.
- **API / data / config / docs** — contract/shape/migration/render checks per the reference.

**Operator-choice for large/parallel verification.** When several risk classes warrant independent,
parallel verification, **OFFER** a backend per `../../references/operator-choice.md` (`inline` /
`team-execution` / `cc-workflows-ultracode`) — never auto-spawn. Parallel verification uses **generic
`Explore` / `Task` agents** (this plugin has no `agents/` dir — do not reference named `ce-*` agents).

---

## Phase 3 — Findings

Turn evidence into findings. Each finding records:

- **severity** — critical / high / medium / low (defs + the P0-P3 cross-walk in `references/risk-taxonomy.md`).
- **risk class** — which of the 9 it belongs to.
- **evidence** — the proving `file:line`, check output, log, network response, or MCP capture.
- **repro** — the minimal steps to reproduce.
- **falsifiable prediction** — *only for failures whose cause is uncertain*: a concrete claim about
  another path/scenario that must also fail if this is the real cause (principle 3). Obvious-cause
  findings skip it.

`/qa` does **not** fix anything here — it documents.

---

## Phase 4 — Score + verdict

Report **two** things — the deterministic health **score** (a signal) and the **ship verdict** (the
gate decision). They are separate: the score is a continuous 0-100 number; the verdict is the
pass/fail gate.

### 4.1 Compute the deterministic health score

Roll the per-class severity counts from Phase 3 into the deterministic scorer — a faithful **PORT of
gstack's Health Score Rubric** (the deduction values are gstack's verbatim; the class weights are a
documented infiquetra ship-risk adaptation — see `references/qa-report.md`):

```bash
python3 plugins/saga/scripts/qa_health_score.py \
  --findings-json '{"<class>": {"<severity>": <count>, ...}, "<checked-clean-class>": {}}' \
  --baseline-score <prior-overall-from-Phase-0.4>
```

`--findings-json` accepts a file path or an inline JSON string keyed by the in-scope risk classes (a
checked-but-clean class is an empty `{}` map and scores 100; an absent class is N/A and excluded).
`--baseline-score` is the prior run's `overall` (Phase 0.4); when present the scorer also emits
`delta`. The scorer prints `{"per_class": {...}, "overall": N, "in_scope": [...], "baseline": N,
"delta": D}` — report the overall, the per-class table, and the baseline delta.

The score is **one signal**, not the gate: its inputs are LLM-assigned severities (principle 4).

### 4.2 Derive the ship verdict

State **pass/fail per risk class**, then derive the overall **ship verdict** from the tier's blocking
threshold (`references/qa-report.md`):

- **Quick:** critical + high block.
- **Standard:** critical + high + medium block.
- **Exhaustive:** all severities block + a broad sweep.

A class with no blocking finding **passes**; any blocking finding makes its class **fail**. The ship
verdict is `ship` (no blocking findings), `ship-with-deferred` (only non-blocking findings, recorded
with repro), or `no-ship` (any blocking finding). The **verdict is the gate decision**; the score
above rides alongside it as the continuous health signal.

---

## Phase 5 — Report + emit evidence

### 5.1 Write the durable artifact

Write `docs/qa/qa-<saga-id-or-issue>-<date>.md` using the shape in `references/qa-report.md` (adapted
from gstack's template, browser-decoupled): header (target / tier / scope / reviewed revision), the
**health-score block** (overall 0-100 + per-class table + baseline delta from Phase 4), top findings,
summary-by-severity, per-finding (severity / class / evidence / repro / falsifiable-prediction),
**recommended** regression tests (recommend — do **not** generate them), the ship verdict with its
derivation, and deferred-with-repro. Use `docs/qa/` — its own directory, with no handoff/sdlc
classifier collision.

### 5.2 Emit issue progress with evidence

Post a progress update linking the artifact and listing the checks run:

```bash
python3 plugins/saga/scripts/issue_progress.py \
  --event qa \
  --issue-ref <owner/repo#N> \
  --destination <plan-only|pr|merge|nonprod-deploy> \
  --checks-run "<class:check | class:check | ...>" \
  --evidence-link "docs/qa/<file>.md"
```

`--checks-run` is pipe-separated. Skip this command when there is no issue ref (a `task-` thread).

---

## Phase 6 — Tick the saga + route

### 6.1 PASS — advance the qa-track

On a `ship` (or `ship-with-deferred`) verdict, append a tick that writes `qa_paths` and **advances**
`lifecycle_phase` from `work` to `qa` (the deferred advance). **Pin `--phase` to the restored integer
`phase`** so `--phase-status complete` does not advertise a phantom counter advance, and reuse the
restored `kind`/`id` verbatim:

```bash
python3 plugins/saga/scripts/saga.py save \
  --kind <issue|task> \
  --id <the-restored-saga-id-suffix> \
  --lifecycle-phase qa \
  --phase-status complete \
  --phase <restored-phase> \
  --qa-paths docs/qa/<file>.md \
  --checks-run "<class:check | ...>" \
  --next-step "<route to /handoff or /retro>" \
  --summary "<one-line ship verdict>"
```

`saga.py save` **mints unconditionally**, so run this tick **only if Phase 0.2 restored a saga** — never
invent a `--kind`/`--id` to satisfy the CLI (the scan-first / never-mint guard `/qa` shares with
`/code-review`). Never `git add` the tick — saga state is git-ignored and machine-local. Then route to
**`/handoff`** (turn the work into / update an SDLC issue) or **`/retro`** (capture learnings).

### 6.2 FAIL — keep work phase, route by merge state

On a `no-ship` verdict, **keep `lifecycle_phase=work`** (omit `--lifecycle-phase`, which carries the
prior phase forward), tick with `--qa-paths docs/qa/<file>.md` and the evidence, then route by **merge
state**:

- **Pre-merge (PR still open)** → **`/work`** — hand the findings back and re-enter the round-N PR loop.
  `/work`'s Phase 0.4 re-entry keys on the saga's `pr_refs`, so the thread resumes cleanly.
- **Post-merge (merged to `main`)** → a **two-target branch**. Do **not** route a merged thread back to
  `/work` round-N: its `pr_refs` PR is merged, so Phase 0.4 would cycle the merged PR straight back to
  `/qa`. Instead route by what the failure needs:
  - **Deep / uncertain root cause** (the cause is unknown or the falsifiable prediction failed) →
    **`/investigate`** — the systematic-debugging engine owns the causal-chain work `/qa` does not do.
  - **Clear / trackable defect** (the cause is understood, just not fixing it now) → **`/handoff`** —
    open a **new defect thread**.

`/investigate` is a real routable target — it ships and is on the dispatch-table's routable list, so
emit it for deep post-merge root-cause failures. `/qa` still does **not** debug: it routes the
root-cause work TO `/investigate`, never runs it, and there is **no `/investigate` → `/qa` verify
loop`. Routing **reads** `loop/references/dispatch-table.md`.

---

## Hard boundary

`/qa` gathers acceptance evidence, assigns severity, derives a verdict, writes the artifact, ticks the
saga, and routes — then stops. It does **NOT** fix bugs, does **NOT** edit reviewed code, does **NOT**
commit, does **NOT** push, does **NOT** open, update, or merge a PR, does **NOT** deploy, does **NOT**
file SDLC issues, does **NOT** set readiness labels, and does **NOT** run a fix loop or deep root-cause
debugging (`/work` and `/investigate` own those). It never blocks the router.

---

## Reference files

- `references/risk-taxonomy.md` — the 9-way risk router with per-class acceptance/evidence checklists,
  the browser-as-one-MCP-class fold, the file-pattern → risk-class map for diff-aware mode, the severity
  definitions (critical / high / medium / low), and the critical/high/medium/low ↔ P0-P3 cross-walk.
- `references/qa-report.md` — the QA artifact shape (browser-decoupled, including the health-score
  block), the health-score model (the gstack-ported deductions + infiquetra class weights +
  re-normalization + baseline-from-prior-report) with its runnable `qa_health_score.py` line, the
  ship-verdict derivation (severity bands → ship / ship-with-deferred / no-ship), the
  tier → blocking-threshold table, and the falsifiable-prediction finding shape.
