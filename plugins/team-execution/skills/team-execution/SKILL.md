---
name: team-execution
description: |
  Two-phase structured plan execution with reviewer consensus, validator gates,
  and guarded nonprod automation for Infiquetra repositories.

  Phase A runs during planning: inspect the requested work, derive workers,
  reviewers, and selected validators, then embed the team plan into the user-approved
  plan artifact.

  Phase B runs after approval: workers complete changes, reviewers reach consensus,
  scanners run, PR/CI/nonprod coordination happens only after gates pass, and
  testers plus monitors validate the deployed nonprod result.
when_to_use: |
  Use this skill proactively when in plan mode and any of these are true:
  - The plan has 3+ steps, touches 3+ files, or involves docs/specs.
  - The plan involves multiple work streams, repositories, contracts, workflows, or deployments.
  - The user asks for agent teams, team-execution, validator gates, nonprod automation,
    review consensus, or automated checks.
  - The user asks for code review as part of a plan.

  Do not use when:
  - The plan already has a ## Team Structure section.
  - The change is trivially simple and the user declines team planning.
  - The user has already declined team planning for this plan in this session.
---

# Team Execution Skill

This skill has two phases:

- **Phase A** runs during planning. You inspect the plan and repository signals, derive
  workers, reviewers, selected validators, and automation eligibility, then embed the
  `## Team Structure` section into the plan before plan approval.
- **Phase B** is the orchestration protocol. It is followed directly by the main agent after
  the user approves the plan.

Validators are selected by task context. Do not spawn the full validator roster by default.

---

# Phase A: Team Planning

## Step A0: Environment Pre-flight

Run pre-flight checks silently. Show only actionable gaps.

### A0a. Handoff Rule

Check for the handoff rule:

```bash
grep -q "Team Execution Auto-Handoff" ~/.claude/CLAUDE.md 2>/dev/null && echo "FOUND" || echo "MISSING"
```

If missing, tell the user to add the rule manually. Do not block plan creation.

---

## Step A1: Plan and Repository Intake

Derive the plan from all available signals:

- User plan text and acceptance criteria.
- Repo type and language/tooling.
- Changed files, staged files, and branch state.
- GitHub workflows under `.github/workflows/`.
- API contracts such as OpenAPI, AsyncAPI, protobuf, GraphQL schemas, or SDK fixtures.
- Documentation, runbooks, architecture docs, and issue specs.
- Test suites and existing quality commands.
- Optional `.team-execution.json`.

The `.team-execution.json` file is optional. Absence means infer from the repo. Supported keys:

```json
{
  "required_validators": ["security-scanner", "smoke-tester"],
  "disabled_validators": ["performance-tester"],
  "nonprod_workflows": ["publish-nonprod.yml"],
  "scenario_hints": ["checkout flow", "webhook replay"],
  "smoke_targets": ["https://example-nonprod.internal/health"]
}
```

If present:

- `required_validators` must be selected unless explicitly impossible.
- `disabled_validators` must not run unless the user overrides.
- `nonprod_workflows` limits deployment/publish workflow candidates.
- `scenario_hints` inform scenario and event-flow testers.
- `smoke_targets` inform smoke tests.

---

## Step A2: Classify Work

Classify the plan:

| Type | Definition |
|------|------------|
| code | Primarily code changes, refactors, bug fixes, or infrastructure |
| docs/specs | Primarily documentation, issue specs, skill docs, or runbooks |
| mixed | Both code and documentation/spec content |

Also classify repository signals:

| Repo Signal | Examples |
|-------------|----------|
| Python service | `pyproject.toml`, `requirements.txt`, `pytest`, FastAPI, Lambda handlers |
| AWS/CDK service | `cdk.json`, `template.yaml`, CloudFormation, SAM, Lambda, IAM |
| API contract repo | OpenAPI, AsyncAPI, protobuf, GraphQL schema |
| SDK repo | `sdk`, generated clients, package publishing workflows |
| Frontend repo | React, Next.js, Vite, Playwright, browser smoke targets |
| Home-lab/observability | Ansible, Prometheus, Grafana, Docker Compose, local infra |

---

## Step A3: Reviewer Selection

Read:

- `team-execution/skills/team-execution/references/reviewer-registry.md`
- `team-execution/skills/team-execution/references/review-criteria.md`
- `team-execution/skills/team-execution/references/consensus-protocol.md`

Base reviewers always included:

- `devils-advocate-reviewer`
- `security-reviewer`
- `architecture-reviewer`

Optional reviewers are suggested from plan and repo signals.

Reviewer non-consensus blocks validators unless the user explicitly overrides.

---

## Step A4: Validator Selection

Read:

- `team-execution/skills/team-execution/references/validator-registry.md`
- `team-execution/skills/team-execution/references/validator-criteria.md`
- `team-execution/skills/team-execution/references/validator-execution-order.md`
- `team-execution/skills/team-execution/references/validator-evidence-state.md`
- `team-execution/skills/team-execution/references/validator-spawn-quirks.md`

Select validators by context:

| Group | Agents |
|-------|--------|
| Scanners | `security-scanner`, `iac-cost-scanner`, `api-compat-scanner`, `dependency-scanner` |
| Testers | `smoke-tester`, `scenario-tester`, `api-contract-tester`, `sdk-regression-tester`, `event-flow-tester`, `ui-regression-tester`, `performance-tester`, `concurrency-tester` |
| Monitors | `github-actions-monitor`, `runtime-monitor` |
| Operational | `deploy-watcher` |

Tool candidates are OSS/free where available:

- Semgrep
- Bandit
- pip-audit
- Trivy
- Gitleaks
- detect-secrets
- Checkov
- oasdiff
- Schemathesis
- Playwright
- k6

If a selected validator requires a missing tool, fail loud with setup guidance. Do not silently
skip required validators.

---

## Step A5: State and Evidence Plan

Validator run state is JSON under:

```text
.claude/team-execution/validators/
```

Before planning validator state, check whether `.claude/` is ignored in the target repo. If it is
not ignored, instruct the user to add an ignore rule or use the user-local fallback:

```text
~/.claude/team-execution/state/<repo>/
```

Each validator state record includes:

- Validator name and group.
- Selection reason.
- Required tool commands and availability.
- Inputs inspected.
- Evidence paths.
- Findings and severity.
- Gate result: pass, warn, hard-fail, skipped-by-config, or blocked.
- Remediation loop count.

---

## Step A6: Automation Eligibility

Automation is allowed only when all conditions are true:

- Remote matches `github.com/infiquetra/*`.
- The plan follows the repo default branch model.
- Reviewers, selected scanners, CI, and required testers pass.
- Workflow is explicitly nonprod or publish-nonprod.
- The action does not touch production, staging, force-push, branch deletion, or credentials.

Any ambiguous or missing signal blocks automation.

---

## Step A7: Embed Team Structure

Append a plan section like this:

```markdown
## Team Structure

### Workers
| Agent | Units | Tier | Mode | Depends-on | Engine | Intent |
|-------|-------|------|------|------------|--------|--------|
| `worker-<plugin>` | U1, U2 | opus/high | bypassPermissions | — | — | — |
| `worker-<engine>` | U3 | sonnet/medium | bypassPermissions | `worker-<plugin>` | `<engine-key>` | offload |

`Engine` and `Intent` are `—` for Claude workers. An engine-owned worker (KTD3, U12) renders
`Engine` as `<engine-key>` for an explicit selector or `cap:<capability-key>` for a capability
route, and `Intent` as `offload` or `second-opinion` — see
`team-execution/skills/team-execution/references/external-engine-workers.md`.

<!-- EFFORT-EMISSION MARKER (#362 U5, R7, KTD6): the `Tier` column is a `<model>/<effort>` pair
sourced verbatim from `fleet_commons.tier_resolver.resolve(...).model` and `.effort` (via the
worker's `role-tier:` alias or work-shape), never a bare model literal with effort omitted. This
is emission only — #362 adds no dispatch-time honoring of the `effort` half; the Agent tool has
no effort knob yet (#363's `EFFORT_RIDER`/cascade). #363's A7 parser splits this cell on `/` into
`(model, effort)`, matching `/plan`'s per-unit tier table cell shape (same marker, `plugins/saga/
skills/plan/SKILL.md`). -->



### Reviewers
| Agent | Role | Required | Selection Reason |
|-------|------|----------|------------------|
| `devils-advocate-reviewer` | Devil's Advocate Reviewer | yes | Base reviewer |
| `security-reviewer` | Security Reviewer | yes | Base reviewer |
| `architecture-reviewer` | Architecture Reviewer | yes | Base reviewer |

### Validators
| Agent | Group | Required | Selection Reason | Blocking |
|-------|-------|----------|------------------|----------|
| `security-scanner` | Scanner | yes/no | [Why selected] | hard-fail blocks automation |

### Execution Gates
- Reviewer consensus threshold: >= 9.0/10 from every reviewer.
- Reviewer non-consensus blocks validators unless the user explicitly overrides.
- Scanners run before PR/CI/merge/nonprod coordination.
- Tester hard-fail blocks completion.
- Maximum 3 remediation loops before escalation.

### Reference Files
- `team-execution/skills/team-execution/references/reviewer-registry.md`
- `team-execution/skills/team-execution/references/review-criteria.md`
- `team-execution/skills/team-execution/references/consensus-protocol.md`
- `team-execution/skills/team-execution/references/validator-registry.md`
- `team-execution/skills/team-execution/references/validator-criteria.md`
- `team-execution/skills/team-execution/references/validator-execution-order.md`
- `team-execution/skills/team-execution/references/validator-evidence-state.md`
- `team-execution/skills/team-execution/references/validator-spawn-quirks.md`
- `team-execution/skills/team-execution/references/worker-manifest.md`
- `team-execution/skills/team-execution/references/external-engine-workers.md`
- `team-execution/skills/team-execution/references/artifact-pointers.md`
- `team-execution/skills/team-execution/references/andon-cord.md`
```

Then submit the plan for approval. Do not start implementation during Phase A.

---

# Phase B: Orchestration Protocol

Phase B starts only after plan approval.

## Step B0: Parse the Approved Team Plan

Read the approved `## Team Structure`, selected validators, reference files, automation
eligibility, and state location.

If the plan has no `## Team Structure`, stop and tell the user to run `/team-execute`.

---

## Step B0a: Validator-State Preflight

Before any worker runs (pre-execution, so the safety check survives without `/team-setup`), re-verify
the validator-state location is safe — the same `.claude/`-ignored check from Step A5, now enforced at
execution time:

```text
.claude/team-execution/validators/   (valid only when .claude/ is git-ignored in the target repo)
```

If `.claude/` is NOT ignored in the target repo, do not write run-state there — fail loud and either
have the user add an ignore rule or fall back to `~/.claude/team-execution/state/<repo>/`. This guards
against committing validator run-state into the repo and runs in BOTH Phase A planning (Step A5) and
here in Phase B preflight.

---

## Step B1: Workers Complete Changes

Workers execute approved tasks. Coordinate dependencies, keep work scoped to the plan, and run execution waves using the resident-worker residency protocol:

- **Run-posture check (#380):** when the run carries a committed intent envelope (the plan's
  `ExecutionSpec.intent`, or an envelope file handed down by `/outcome`), resolve every spend
  decision — wave spawn at an escalated tier, a worker/reviewer-proposed tier or verify-depth
  increase — through the fleet posture registry, never an ad hoc question:
  `python3 plugins/team-execution/skills/team-execution/scripts/posture_check.py
  --envelope-file <envelope.json> [--spend-increase] [--approval-token <tok>]`. An attended
  spend increase without an explicit approval token exits `2` (a structural `PostureError` —
  surface it to the operator; never escalate silently); an unattended run proceeds at the
  cache-tight default silently and a requested increase is held at the default and recorded.
  No envelope means no new gate — today's behavior, unchanged. The single posture interview
  lives in the envelope registry (`plugins/saga/references/intent-envelope.md`); Step B1 only
  READS posture — it never re-asks a question the envelope already answers (the fleet
  drift-guard test fails on one).

- **Wave Scheduling & Reactive Unblocking (R8, R10):** A resident worker with unmet segment-level `Depends-on` must not be spawned (avoiding premature creation costs) until its upstream segments complete. Segments with no dependencies can start in parallel. This within-run segment frontier is strictly subordinate to saga's coordinator-level `ready_frontier`.
- **Persistent Resident Workers (R3):** Spawn exactly one named, persistent teammate per resident worker (segment) using an Agent with a specific `name` (the resident id) and `run_in_background` enabled, rather than spawning anonymous workers per unit. Before that Agent-tool spawn, run the segment's cascade-resolved `effort` (R5 cascade result; falls back to the worker's agent-frontmatter `effort:` default when no plan-unit or team-level override applies) through `fleet_commons.effort_rider.inject_effort(prompt, resolved_effort, "agent")` (load via `fleet_commons_shim.load("effort_rider")`) and spawn with the returned prompt — this is the only dispatch path with no real per-call effort knob (KTD1/KTD2), so `EFFORT_RIDER[resolved_effort]` is prepended as a labeled proxy directive. The `workflow` and `external-engine` spawn kinds already pass `effort` as a real knob (`agent({effort})` / `effort=resolution.effort`) and should route through the same seam with their own `spawn_kind` so it passes through unchanged instead of double-injecting.
- **Worker Reuse (R3):** Reuse the resident worker across all units in its segment via `SendMessage`. Never re-spawn the worker per unit; reusing the persistent teammate preserves its warm context/cache across all units it owns.
- **Cross-Segment Summary-Handoff (R4):** When a dependent segment requires the result of a prior segment, seed the dependent segment's fresh worker with a short summary of the upstream segment's output via `SendMessage` instead of forwarding the upstream worker's entire context.
- **Context Shedding (R11):** Shed a resident worker at its segment boundary, or when a block of time is expected to exceed the prompt cache TTL horizon (~5 minutes). Teammate reuse is for temporally-tight loops, not indefinite warmth.
- **Session tier override at the segment boundary (#365):** the emitted Team Structure honors a run-scoped tier ceiling / mid-run patch written via `/tier` (`.claude/saga/tier-session-override.json`) — the `team_emitter` clamps each segment's worker tier down to the ceiling at emit. Because a mid-run patch only touches **not-yet-run** units, a tier change written between segments affects only the **next** (not-yet-shed) segment's worker spec; an already-shed segment keeps its recorded tier. The ceiling only ever clamps down and is the final word (it can clamp a segment below a `min_tier` floor — the live operator override wins, and the downgrade is logged).
- **Chaperone Dispatch (KTD1, U12):** A resident worker whose `### Workers` row carries a non-`—`
  `Engine` cell is a chaperone: it resolves, dispatches through the existing containment wrappers,
  verifies the returned evidence, applies the patch as sole-committer, runs its unit's tests, and
  writes the worker-exit manifest — the engine itself never joins wave scheduling or touches the
  working tree. Full protocol in
  `team-execution/skills/team-execution/references/external-engine-workers.md`.
- **Andon-cord — worker-raised stop-the-line (#372):** any worker or reviewer that finds a
  blocking problem (fabricated evidence, a wrong-direction build, an unsafe mutation) may raise an
  `andon_halt` into the shared mid-run adjustment envelope (`.saga/adjustment-envelope.json`) via
  `adjustment_envelope.raise_andon(...)`. At the next wave/tick boundary the coordinator polls the
  envelope and, on a raised andon, **does not dispatch the next wave** and writes an operator-surface
  HALT record. This is an additional, orthogonal halt path — it does **not** replace or weaken the
  3-cycle consensus cap or the 3-loop remediation cap (an andon and an iteration-cap
  "proceed-with-best-available" are distinct, coexisting outcomes). Full protocol in
  `team-execution/skills/team-execution/references/andon-cord.md`.

Each worker writes a provenance manifest at segment/unit exit — see
`team-execution/skills/team-execution/references/worker-manifest.md` (attribution + disposition +,
for contract-bearing units, output_completeness; evidence-only, grants no privilege). A chaperone
worker's manifest additionally carries `kind=external-engine` attribution and the honest
disposition (`ran-as-requested` / `fell-back-to-claude` / `substituted-engine`) per
`external-engine-workers.md`.

- **Post-Run Reconciliation (R9, KTD7):** After manifests are written, compare each teammate's
  cascade-resolved `effort` against the effort the worker manifest recorded
  (`worker-manifest.md:48,54`) via `fleet_commons.effort_rider.reconcile_effort(resolved_effort,
  spawn_kind, manifest_effort=..., spawn_prompt=...)`. On the `workflow`/`external-engine`
  (real-knob) paths, pass `manifest_effort` — the value the manifest recorded as actually passed
  to `agent()`/the engine — and a mismatch emits a named `tiering-drift[<spawn_kind>]` line naming
  both efforts. On the `agent` path, pass `spawn_prompt` — the constructed spawn prompt — because
  there is no real knob to observe; a mismatch there names `rider-text` (not "reasoning spend") as
  the compared quantity, since the seam can only confirm the `EFFORT_RIDER` directive reached the
  prompt, never actual harness reasoning spend. A match emits nothing.

When all worker tasks are complete, run `artifact_pointer.py snapshot --run <run-id> --epoch
<epoch>` once per review epoch (`team-execution/skills/team-execution/scripts/artifact_pointer.py`,
epoch = the consensus iteration counter) to capture the changed files as a Layer-1 tree snapshot.
Pass the resulting pointer to reviewers and validators **in place of an inlined diff** whenever the
artifact is above threshold: **pointerize at > 4 KB, or > 1 KB with >= 2 recipients; an artifact
<= 1 KB always stays inline, regardless of recipient count.** This threshold is the single
source of truth — `consensus-protocol.md`, `validator-spawn-quirks.md`, and
`references/artifact-pointers.md` reference it rather than restating the numbers. Reviewers (full
diff) and validators (diff summary) are evaluated against the threshold independently. See
`references/artifact-pointers.md` for the receiver contract (dereference procedure, full-read
invariance, and the KTD7 capability-keyed fallback to inlined content).

---

## Step B2: Reviewers Reach Consensus

Run reviewers according to `consensus-protocol.md`.

Before the first reviewer Agent call, create one `site=team-execution` dispatch manifest with every
configured reviewer and its expected scored-review deliverable, then append that reviewer's `spawn`
fact immediately before its Agent call. Use the packaged coordinator adapter, not a repository-relative
Saga path: it resolves Saga from `SAGA_PLUGIN_ROOT`, an Infiquetra source checkout,
`~/.claude/plugins/installed_plugins.json`, or the `CLAUDE_PLUGIN_ROOT` cache sibling. Its required
preflight fails before any Agent call when no valid Saga plugin is installed.

```bash
TEAM_SETTLEMENT="${CLAUDE_PLUGIN_ROOT:-plugins/team-execution}/skills/team-execution/scripts/dispatch_settlement_adapter.py"
python3 "$TEAM_SETTLEMENT" preflight
python3 "$TEAM_SETTLEMENT" manifest --kind reviewer --repo-root "$REPO_ROOT" --subplot-id "$SAGA_ID" \
  --dispatch-id "$DISPATCH_ID" --roster-json "$REVIEWER_ROSTER_JSON" --at "$NOW"
python3 "$TEAM_SETTLEMENT" saga -- --repo-root "$REPO_ROOT" --subplot-id "$SAGA_ID" spawn \
  --dispatch-id "$DISPATCH_ID" --unit-id "$REVIEWER" --attempt 1 \
  --idempotency-key "team-execution:reviewer:$REVIEWER" --at "$NOW"
```

At collection, the coordinator stores the returned structured reviewer result in a JSON file and runs
`settle --kind reviewer --source-json ... --receipt-path ...`. The adapter validates the real result,
materializes a `dispatch.artifact.v1` file, and passes only its `{receipt_type, unit_id,
evidence_path}` descriptor to Saga. Missing, incomplete, prose-only, or artifact-pointer-only output
is settled as `silent-no-op`; trust flags, caller digests, and caller-selected outputs are never
accepted. Source and receipt paths are relative to `--repo-root` by default. When team state lives
under `~/.claude`, pass that state directory as `--evidence-root`; the adapter confines both paths to
that root while validator-referenced evidence remains confined to `--repo-root`.

```bash
python3 "$TEAM_SETTLEMENT" settle --kind reviewer --repo-root "$REPO_ROOT" --subplot-id "$SAGA_ID" \
  --dispatch-id "$DISPATCH_ID" --unit-id "$REVIEWER" --attempt 1 --at "$NOW" \
  --source-json ".claude/team-execution/reviews/$REVIEWER.json" \
  --receipt-path ".claude/team-execution/settlement/$DISPATCH_ID-$REVIEWER.json"
python3 "$TEAM_SETTLEMENT" saga -- --repo-root "$REPO_ROOT" --subplot-id "$SAGA_ID" report \
  --dispatch-id "$DISPATCH_ID"
```

HALT when `halt_required=true`. At the next review boundary, use `saga -- ... claim-retry` before new
reviewer work; the idempotency key remains stable.

- All confirmed reviewers score the implementation.
- Consensus requires overall score >= 9.0/10 and no dimension < 7.0.
- Security/auth/secrets dimension < 5.0 is a blocking stop.
- Reviewer non-consensus blocks validators unless the user explicitly overrides.
- Maximum 3 review cycles.

---

## Step B3: Scanners Run

Run selected scanner validators only after reviewer consensus or explicit user override.

Apply the same settlement sequence to the complete selected-validator roster: manifest before any
Agent call, spawn immediately before each call, and settle from the validator's required state file.
The state file's `evidence[]` entries must resolve to existing files inside `--repo-root`; the adapter
then materializes the `dispatch.artifact.v1` receipt. A required validator with no state file,
incomplete state, missing referenced evidence, success prose, or an artifact pointer is
`silent-no-op`, enters the derived DLQ while attempts remain, and can never be counted as an implicit
pass. The exact command is in `validator-evidence-state.md`.

Scanners inspect local artifacts, code, dependency manifests, contracts, and infrastructure.
Hard-fail scanner findings block auto-merge, nonprod deploy, and completion.

Missing required scanner tools fail loud with setup guidance. Optional scanner tools may be
reported as skipped only if the validator is not required.

---

## Step B4: PR, CI, Merge, and Nonprod Coordination

Coordinate automation only if gates pass and automation is eligible:

1. Confirm remote matches `github.com/infiquetra/*`.
2. Confirm default branch model.
3. Confirm no production, staging, force-push, branch deletion, or credential-changing action.
4. Run or monitor allowed `nonprod` or `publish-nonprod` workflows only.

If any signal is ambiguous, stop automation and report what is missing.

---

## Step B5: Testers Validate Deployed Nonprod Result

Run selected tester validators after a deploy or publish target is available.

Testers validate smoke targets, scenarios, contracts, SDK compatibility, event flows, UI
regressions, performance thresholds, and concurrency behavior as applicable.

Hard-fail tester findings block completion. Run a maximum 3 remediation loops before escalating
to the user.

---

## Step B6: Monitors Verify Runtime Signals

Run monitor validators:

- `github-actions-monitor` checks workflow status and relevant logs.
- `runtime-monitor` checks repository-appropriate observability: CloudWatch for AWS repos,
  Prometheus/Grafana-style checks for home-lab/local-infra repos, and app health endpoints
  where configured.

If monitors cannot reach an expected signal, mark the gate blocked or warn based on whether
the signal was required.

---

## Step B7: Completion

Report:

- Worker changes.
- Reviewer scores.
- Scanner, tester, and monitor gate results.
- Validator state location.
- Evidence paths.
- Automation actions taken or blocked.
- Residual risks.

Do not claim completion while required validators are hard-failing or blocked unless the user
explicitly accepts the residual risk.

A required, non-skipped validator whose evidence record was **never written** is a `missing-output`
omission, not a silent pass — treat its absent evidence at process exit as a completion block,
exactly like a hard-fail. A `skipped-by-config` validator (recorded with a `selection_reason`) is
not a trip. See `references/validator-execution-order.md` (Required-Evidence Absence).

---

# Quick Reference: File Paths

```text
team-execution/
├── .claude-plugin/plugin.json
├── skills/
│   ├── appsec-audit/SKILL.md
│   └── team-execution/
│       ├── SKILL.md
│       └── references/
│           ├── consensus-protocol.md
│           ├── review-criteria.md
│           ├── reviewer-registry.md
│           ├── validator-criteria.md
│           ├── validator-evidence-state.md
│           ├── validator-execution-order.md
│           ├── validator-registry.md
│           ├── validator-spawn-quirks.md
│           ├── worker-manifest.md
│           ├── external-engine-workers.md
│           └── artifact-pointers.md
├── agents/
│   ├── devils-advocate-reviewer.md
│   ├── security-reviewer.md
│   ├── architecture-reviewer.md
│   └── [reviewer and validator agents]
└── commands/
    ├── team-execute.md
```
