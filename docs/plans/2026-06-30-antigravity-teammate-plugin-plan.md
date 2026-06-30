---
title: Antigravity Teammate Plugin Implementation Plan
type: feat
status: active
date: 2026-06-30
origin: docs/brainstorms/2026-06-30-antigravity-teammate-plugin-requirements.md
deepened: 2026-06-30
destination: pr
recommended_backend: team-execution
---

# Antigravity Teammate Plugin Implementation Plan

## Summary

Build a new first-party `agy` Claude Code plugin that exposes Antigravity-backed teammates:
`agy-coder`, `agy-reviewer`, and the secondary `/agy:delegate` quick command. All surfaces route
through one Python wrapper that validates a delegation envelope, runs `agy`, records evidence, and
applies or preserves patches only through a managed import gate.

The implementation should be delivered as a PR-bound feature, not as an immediate marketplace
flip. The plugin may be scaffolded dormant first, but the marketplace entry, release version, and
advertised readiness land only after static tests, direct wrapper tests, and live Claude Code
harness proof pass.

## Planning Inputs

- Requirements source: `docs/brainstorms/2026-06-30-antigravity-teammate-plugin-requirements.md`.
- Readiness review: `docs/reviews/2026-06-30-antigravity-teammate-plugin-requirements-readiness.md`.
- Prior failure evidence: `docs/engineering-journal/LEARNINGS.md` and
  `docs/external-agent-delegation/blueprint.md`.
- Repo conventions: `AGENTS.md`, `tests/test_release_triad.py`, `tests/test_deploy_plugin.py`,
  `tests/test_team_execution_plugin.py`, and existing plugin command/agent patterns.

## Requirements

R1. Ship the plugin namespace as `agy` under `plugins/agy`, with a slash command named
`/agy:delegate` and agent files named `agy-coder.md` and `agy-reviewer.md`.

R2. Implement the plugin as a CLI-style plugin: Markdown command/agent/skill surfaces plus a
shared Python wrapper. Do not fork or wrap the existing upstream plugin as the user-facing product.

R3. Both teammates are bridge agents. Their frontmatter must constrain them to Bash only, and their
prompts must require exactly one wrapper invocation per delegated turn. They must not use Claude
file-editing tools to solve the requested coding or review work.

R4. `/agy:delegate` is the quick-use surface for direct operator calls. It fills the same envelope
and invokes the same wrapper as the teammates. No weaker raw runner is exposed as a normal command.

R5. Every delegated turn is a fresh `agy` invocation by default. Stateful Antigravity conversations
are out of scope for v1.

R6. The wrapper owns a versioned delegation envelope with fields for role, mode, lens, task, model
selection, write-set, evidence level, verification policy, timeout, provenance expectations, and
apply policy. Verification commands are supplied by the orchestrator/operator envelope, never by
the delegate's self-report.

R7. V1 supports exactly these user-facing envelope mode strings: `no-write`, `patch-only`, and
`auto-if-clean`. Reviewer delegation defaults to `no-write`. Coder delegation defaults to
`patch-only` unless the caller explicitly provides a write-set and asks for `auto-if-clean`.
Internal Python symbols may use snake_case, but the CLI and envelope contract use the hyphenated
mode names from the requirements.

R8. `auto-if-clean` may apply to the live tree only when all of these are true: explicit write-set,
clean compatible pre-run git state, explicit verification policy, real `agy` proof, changed paths
inside write-set, verification passed, no timeout/no-output/fallback/orphan signal, and post-apply
git proof shows only the expected write-set changes with no rogue statuses.

R9. No explicit write-set means no automatic live-tree mutation. Inferred or proposed write-sets
may be surfaced only as `patch_ready` evidence.

R10. All runs write a full local evidence bundle under `.claude/agy/runs/<run-id>/`. Inline output
is only a projection of that bundle and must include the bundle path.

R11. The wrapper must record run lease and provenance evidence before trusting output: resolved
`agy` executable, sanitized argv, process id, start/end timestamps, stdout/stderr logs, working
boundary, timeout class, shutdown outcome, and real-`agy` verdict.

R12. The wrapper must avoid the known background detach/hang trap. V1 uses a blocking foreground
subprocess supervised by the Python wrapper, with explicit timeout/no-output handling, and never
passes a plugin-level `--background` style path.

R13. Real-`agy` proof is transcript/process backed. If the wrapper cannot prove the external `agy`
process ran, or if a harness transcript shows Claude directly using repo file tools instead, the
status is `fallback_suspected` and no apply may occur.

R14. The wrapper status enum is snake_case and starts with:
`success`, `patch_ready`, `applied`, `plan_gap`, `test_conflict`, `path_missing`, `timeout`,
`no_output`, `fallback_suspected`, `out_of_scope_mutation`, `checks_failed`,
`shutdown_incomplete`, `bundle_failed`, and `error`.

R15. Static tests cover packaging, frontmatter, prompt contract, release surfaces, envelope schema,
status transitions, write-set enforcement, patch-only behavior, auto-apply refusal cases, and
harness transcript classification.

R16. Live harness proof is a release gate. It must include one packaged `agy-reviewer` run and one
packaged `agy-coder` write run in a scratch repo, then audit transcripts to prove the packaged
agents invoked the wrapper/`agy` path instead of solving directly.

## Key Technical Decisions

KTD1. The plugin id and namespace are `agy`.

`agy` is short, matches the intended `/agy:delegate` command surface, and lets this become the
first-party replacement for the unreliable current Antigravity plugin. Do not co-install or rely on
the upstream `antigravity-plugin-cc` implementation during v1 proof, because the proof must
attribute behavior to this plugin.

KTD2. The implementation is CLI-style, not skill-only.

Existing repo conventions support CLI plugins with command Markdown, skills, agents, README,
CHANGELOG, tests, and Python scripts. The shared wrapper belongs in `plugins/agy/scripts/` so both
agents and commands call one executable path.

KTD3. The bridge agents are Bash-only.

Use `tools: Bash` in `plugins/agy/agents/agy-coder.md` and
`plugins/agy/agents/agy-reviewer.md`. Their prompts should make local solving a contract breach and
should construct a task file plus wrapper invocation through Bash. This gives Claude Code fewer
wrong actions than an agent with broad Read/Edit/Write tools.

KTD4. The delegation envelope is the product primitive.

The command and agents fill one JSON envelope format, `agy.delegation.v1`. Markdown prompt text may
explain the contract, but validation and defaults live in `plugins/agy/scripts/agy_delegate.py` so
there is no prompt-only bypass.

KTD5. Evidence is the return value.

The full local bundle is always written under `.claude/agy/runs/<run-id>/`. The wrapper emits a
projection selected by `--evidence full|summary|minimal`, but all projections name the bundle path
and derive from `result.json`. If the bundle cannot be written, the run fails.

KTD6. All modes run in a disposable local clone, then import patches.

For v1, the wrapper creates a local disposable clone under the run bundle, removes remotes, records
the base SHA, runs `agy` there, and re-derives the diff from the base. The clone bounds repository
patch import, not the whole filesystem. The README and evidence must say that without claiming
OS-level sandboxing.

KTD7. `auto-if-clean` is intentionally stricter than `patch-only`.

`auto-if-clean` requires a clean live tree before launch. `patch-only` may run when the live tree is
dirty, but the evidence records that the patch was derived from the clean committed base and cannot
be auto-applied. This avoids applying a delegate patch across untracked operator work.

KTD8. Release registration is the final unit.

The plugin can exist on disk before marketplace registration, but the marketplace entry, versioned
CHANGELOG release heading, README readiness claim, and release-triad test coverage must land
together only after wrapper behavior and harness proof exist.

KTD9. Direct tests fake `agy`; live proof uses real `agy`.

Unit tests use a fake executable and fixture git repos to cover wrapper behavior deterministically.
The live harness run is separate evidence because static tests cannot prove Claude Code will choose
the bridge path instead of doing the work itself.

KTD10. Implementation backend recommendation is `team-execution`.

This plan touches more than eight files, has more than four implementation units, includes
adversarial reviewer/provenance concerns, and has a live harness gate. Per Saga operator-choice
rules, `team-execution` is the recommended backend for the implementation phase. If the operator
chooses inline execution after doc-review, the units are still sequenced to support it.

## High-Level Technical Design

Data flow:

```text
Claude Code orchestrator
  -> agy-coder / agy-reviewer / /agy:delegate
  -> plugins/agy/scripts/agy_delegate.py
  -> validate agy.delegation.v1 envelope
  -> create .claude/agy/runs/<run-id>/ evidence bundle
  -> create disposable local clone with remotes removed
  -> render prompt packet
  -> run resolved agy executable under supervised foreground subprocess
  -> classify lease/provenance/liveness/status
  -> derive diff and changed paths from base SHA
  -> run explicit verification policy when requested
  -> patch-only: preserve patch
     auto-if-clean: import allowed patch into live tree only if gates pass
  -> write result.json and projection
```

Wrapper modules can remain in one script for v1 if readable, but should be internally separated
into these units:

- `Envelope` and `VerificationPolicy` validation.
- Run directory and evidence writers.
- Git boundary setup, diff derivation, and patch import.
- `agy` subprocess runner.
- Provenance and liveness classifier.
- Projection renderer.
- CLI argument parser.

Initial envelope shape:

```json
{
  "schema": "agy.delegation.v1",
  "role": "coder",
  "mode": "patch-only",
  "task": "Implement the requested change...",
  "model": "flash",
  "review_lens": null,
  "write_set": ["plugins/agy/scripts/agy_delegate.py", "tests/test_agy_delegate.py"],
  "apply_policy": "preserve-patch",
  "evidence": "full",
  "verification": {
    "commands": ["PYTHONPATH=. python3 -m pytest -q tests/test_agy_delegate.py"],
    "required": true,
    "run_scope": "clone"
  },
  "timeout_seconds": 900,
  "no_output_seconds": 180,
  "provenance_required": true
}
```

Initial evidence bundle:

```text
.claude/agy/runs/<run-id>/
  envelope.json
  prompt.txt
  command.json
  run-lease.json
  stdout.log
  stderr.log
  changed-paths.json
  diff.patch
  git-proof.json
  checks.json
  result.json
  projection.md
  harness-transcript-audit.json    # only for live harness proof runs
```

Prompt packets:

- Coder prompt: expert software engineer framing, read-broad/write-narrow instruction, exact
  write-set, no commit/push/history/rewrite operations, escalation markers `PLAN_GAP:`,
  `TEST_CONFLICT:`, and `PATH_MISSING:`, explicit verification commands, and required final run
  report.
- Reviewer prompt: adversarial second-opinion default with lens-specific criteria for
  `adversarial`, `quality`, `scope-gap`, and `security-ops`; defaults to `no-write`; reports
  findings with severity, evidence, and "no finding" confidence.
- Quick command prompt: no persona expansion beyond role/mode/lens; its job is to submit the
  envelope and return the wrapper projection.

## Implementation Units

### U1. Dormant `agy` Plugin Scaffold

Create the plugin shell and packaging tests without marketplace registration.

Requirements: R1, R2, R3, R4, R15.

Files:

- `plugins/agy/.claude-plugin/plugin.json`
- `plugins/agy/README.md`
- `plugins/agy/CHANGELOG.md`
- `plugins/agy/commands/delegate.md`
- `plugins/agy/skills/agy-delegate/SKILL.md`
- `plugins/agy/skills/agy-delegate/references/delegation-contract.md`
- `plugins/agy/agents/agy-coder.md`
- `plugins/agy/agents/agy-reviewer.md`
- `tests/test_agy_plugin.py`

Build notes:

- `plugin.json` starts at `0.1.0`; `CHANGELOG.md` starts with `[Unreleased]` and a planned 0.1.0
  note. U7 converts that into a released `0.1.0` heading when marketplace registration lands.
- `commands/delegate.md` has `name: delegate`, a role/mode/evidence argument hint, and a single
  instruction to load `plugins/agy/skills/agy-delegate/SKILL.md` and run the wrapper.
- Agent frontmatter uses `tools: Bash`.
- Contract tests assert files exist, frontmatter names match, agent frontmatter is Bash-only, and
  command/agent text points at the shared wrapper.
- Do not add `.claude-plugin/marketplace.json` yet.

Checks:

```bash
PYTHONPATH=. python3 -m pytest -q tests/test_agy_plugin.py
```

### U2. Delegation Envelope and Evidence Contract

Implement the wrapper's schema validation, defaulting, status enum, and bundle writer.

Requirements: R6, R7, R10, R14, R15.

Files:

- `plugins/agy/scripts/agy_delegate.py`
- `plugins/agy/skills/agy-delegate/references/delegation-contract.md`
- `tests/test_agy_delegate_contract.py`

Build notes:

- Accept either CLI flags or `--envelope <path>`; internally normalize to one `Envelope`.
- Reject unknown role, mode, lens, evidence level, and status names.
- Reject `auto-if-clean` with an empty write-set before any subprocess launch.
- Create the run directory and write `envelope.json`, `prompt.txt`, `command.json`, and
  `run-lease.json` before executing `agy`.
- Treat bundle write failure as `bundle_failed`.
- Output `projection.md` to stdout for normal command/agent consumption.

Checks:

```bash
PYTHONPATH=. python3 -m pytest -q tests/test_agy_delegate_contract.py
```

### U3. Supervised `agy` Invocation and Provenance Classifier

Run `agy` through one foreground subprocess path, capture logs, and classify liveness/provenance.

Requirements: R11, R12, R13, R14, R15.

Files:

- `plugins/agy/scripts/agy_delegate.py`
- `tests/test_agy_run_lease.py`
- `tests/fixtures/agy/fake_agy.py`
- `tests/fixtures/agy/transcripts/real-agy.jsonl`
- `tests/fixtures/agy/transcripts/claude-clone.jsonl`

Build notes:

- Resolve `agy` with `shutil.which` unless `--agy-bin` is supplied for tests.
- Store sanitized argv in `command.json`; do not store secrets or raw environment dumps.
- Use `subprocess.Popen` with no shell and stream stdout/stderr to logs while checking both total
  timeout and `no_output_seconds`. Do not use `subprocess.run` for the supervised live `agy` path,
  because it cannot enforce no-output liveness before process exit.
- Detect timeout, no-output, non-zero exit, and incomplete shutdown as explicit statuses.
- Add a transcript classifier used by harness proof fixtures. Real agy means an `agy` command
  path is present and Claude file-editing tools did not perform the substantive repo write.

Checks:

```bash
PYTHONPATH=. python3 -m pytest -q tests/test_agy_run_lease.py
```

### U4. Disposable Clone, Patch Inbox, and Apply Policy

Add the repository boundary, diff derivation, patch preservation, and live-tree import gates.

Requirements: R7, R8, R9, R10, R14, R15.

Files:

- `plugins/agy/scripts/agy_delegate.py`
- `tests/test_agy_apply_policy.py`

Build notes:

- For each run, create a disposable local clone under the evidence bundle and remove remotes before
  invoking `agy`.
- Record base SHA, live pre-run status, clone post-run status, changed paths, rogue commits, and
  remote state in `git-proof.json`.
- Re-derive the patch with `git diff --binary <base>` plus untracked-file handling. Do not trust a
  delegate-supplied patch.
- `no-write`: never apply; if the clone changed, preserve the diff and surface a non-clean status.
- `patch-only`: preserve `diff.patch` and return `patch_ready` when the run is otherwise clean.
- `auto-if-clean`: require clean live pre-run status, explicit write-set, in-scope changed paths,
  passed orchestrator-supplied verification, and real `agy` proof before importing with
  `git apply`; after import, record post-apply proof showing only expected write-set changes before
  returning `applied`.
- Out-of-scope changes are preserved in the bundle, not reverted or hidden.

Checks:

```bash
PYTHONPATH=. python3 -m pytest -q tests/test_agy_apply_policy.py
```

### U5. Coder, Reviewer, and Slash Command Prompt Contracts

Finish the packaged prompt surfaces so Claude Code has the fewest likely wrong actions.

Requirements: R1, R2, R3, R4, R5, R6, R15.

Files:

- `plugins/agy/agents/agy-coder.md`
- `plugins/agy/agents/agy-reviewer.md`
- `plugins/agy/commands/delegate.md`
- `plugins/agy/skills/agy-delegate/SKILL.md`
- `plugins/agy/skills/agy-delegate/references/delegation-contract.md`
- `tests/test_agy_prompt_contracts.py`

Build notes:

- `agy-coder` always constructs a coder envelope and calls the wrapper. It may strengthen the task
  into a coder packet, but it may not read/edit/write repo files directly.
- `agy-reviewer` always constructs a reviewer envelope and calls the wrapper. It defaults to
  `review_lens=adversarial` and `mode=no-write`.
- Both agents state that each follow-up turn is a fresh wrapper invocation.
- The slash command shows role/mode/evidence/write-set syntax and routes to the wrapper, not to raw
  `agy`.
- Tests scan prompts for required guardrails and for banned local-solving affordances.

Checks:

```bash
PYTHONPATH=. python3 -m pytest -q tests/test_agy_prompt_contracts.py
```

### U6. Live Harness Proof and Transcript Audit

Prove that packaged Claude Code agents actually invoke the wrapper/`agy` path.

Requirements: R13, R16.

Files:

- `plugins/agy/docs/harness-proof.md`
- `plugins/agy/scripts/audit_harness_transcript.py`
- `tests/test_agy_harness_audit.py`
- `tests/fixtures/agy/harness/real-reviewer.jsonl`
- `tests/fixtures/agy/harness/real-coder.jsonl`
- `tests/fixtures/agy/harness/claude-clone.jsonl`

Build notes:

- Write a small harness runbook with exact scratch-repo setup, plugin install/source path, reviewer
  task, coder task, expected write-set, and transcript extraction path.
- The runbook must execute one `agy-reviewer` no-write review and one `agy-coder` write flow using
  either `patch-only` plus manual patch import proof or `auto-if-clean` with an explicit write-set.
- The transcript audit script classifies fixtures and live transcripts using the same real/fallback
  rules as the wrapper.
- Store live proof results in `plugins/agy/docs/harness-proof.md`, including dates, commands,
  transcript paths or redacted excerpts, evidence bundle paths, and pass/fail verdict.
- The plugin is not v1-ready until this unit has real proof, not just fixture tests.

Checks:

```bash
PYTHONPATH=. python3 -m pytest -q tests/test_agy_harness_audit.py
```

Manual proof gate:

```bash
python3 plugins/agy/scripts/audit_harness_transcript.py <reviewer-transcript.jsonl>
python3 plugins/agy/scripts/audit_harness_transcript.py <coder-transcript.jsonl>
```

### U7. Release Surfaces, Journal, and Full Validation

Register and advertise the plugin only after behavior and live proof are in place.

Requirements: R10, R15, R16.

Files:

- `.claude-plugin/marketplace.json`
- `plugins/agy/.claude-plugin/plugin.json`
- `plugins/agy/CHANGELOG.md`
- `plugins/agy/README.md`
- `tests/test_agy_plugin.py`
- `tests/test_release_triad.py`
- `docs/engineering-journal/DECISIONS.md`
- `docs/engineering-journal/LEARNINGS.md` if implementation uncovers new durable behavior

Build notes:

- Add the marketplace entry with `source: ./plugins/agy`, `version: 0.1.0`, and keywords for
  `antigravity`, `agy`, `delegation`, `teammate`, and `evidence`.
- Extend `tests/test_agy_plugin.py` to assert marketplace metadata, README surface claims, and
  CHANGELOG version alignment for `agy`.
- Let `tests/test_release_triad.py` cover the registered plugin after marketplace entry lands.
- Update `CHANGELOG.md` with the released v0.1.0 surface and proof status.
- Add or update journal entries only for durable discoveries made during implementation; do not
  duplicate this plan if no new evidence lands.

Checks:

```bash
PYTHONPATH=. python3 -m pytest -q \
  tests/test_agy_plugin.py \
  tests/test_agy_delegate_contract.py \
  tests/test_agy_run_lease.py \
  tests/test_agy_apply_policy.py \
  tests/test_agy_prompt_contracts.py \
  tests/test_agy_harness_audit.py \
  tests/test_release_triad.py
uv run ruff check plugins/agy tests/test_agy_*.py
PYTHONPATH=. python3 -m pytest -q
```

## Scope Boundaries

In scope:

- `agy-coder`, `agy-reviewer`, and `/agy:delegate`.
- Python wrapper, envelope, evidence, patch import, and direct tests.
- Fixture transcript audit plus live Claude Code harness proof.
- README, CHANGELOG, marketplace entry, and release-triad coverage.

Out of scope:

- `agy-investigator`, `agy-general`, or a reviewer-agent zoo.
- Stateful Antigravity sessions across turns.
- OS-level filesystem sandboxing. V1 claims repository patch import safety only.
- Automatic commits or pushes by the delegate. Claude Code remains the sole committer.
- Replacing the full team-execution plugin. This plugin supplies teammates that other workflows may
  select.

## Risks & Dependencies

| Risk | Impact | Mitigation |
|---|---|---|
| Claude Code still solves directly instead of invoking the bridge agent wrapper. | Teammate proof is false. | Bash-only agents, prompt-contract tests, transcript audit fixtures, and live harness proof before release. |
| `agy` CLI behavior or model flags differ by host/version. | Wrapper may fail despite correct plugin packaging. | Resolve executable and argv into evidence, support `--agy-bin` for tests, and record live harness environment. |
| Disposable clone does not capture uncommitted operator context. | Delegate may miss local work. | Require clean live tree for `auto-if-clean`; treat dirty-tree runs as `patch-only` review evidence. |
| Clone boundary is mistaken for full sandboxing. | False security claim. | README, evidence, and plan state repo patch import guarantee only; no OS containment claim. |
| Long runs hang or produce no output. | Orchestrator waits forever or trusts stale output. | Foreground supervised subprocess, timeout/no-output statuses, shutdown evidence, and no background detach path. |
| Fake unit tests pass while packaged Claude agents fail live. | Plugin looks ready but is unusable. | U6 live harness proof is required before marketplace readiness claim. |
| Release metadata drifts from behavior. | Installed plugin advertises stale or false behavior. | Marketplace registration is final unit; release-triad and plugin contract tests run after registration. |

## Alternatives Considered

Use the current upstream plugin as-is.

Rejected because the failures are at the command/agent affordance and proof boundary: Claude can
think it delegated while no `agy` process ran, and background paths can hang. A thin wrapper would
preserve too much of the wrong action shape.

Expose a raw `/agy:run` command for flexibility.

Rejected for v1. The requirements are explicitly trying to prevent Claude from picking the wrong
action. A raw runner can exist later as unsafe diagnostics, but not as a normal user-facing surface.

Run `agy` in the live tree and verify after.

Rejected for v1 teammate plugin safety. Prior dogfood showed post-hoc verification can work for
human-supervised one-offs, but this plugin is meant to be the reusable teammate substrate. A
disposable clone plus patch import makes the apply boundary structural.

Use git worktrees instead of a local clone.

Deferred unless clone mechanics fail in implementation. Worktrees are cheaper, but a clone with
remotes removed is easier to reason about for v1 patch import and rogue git evidence.

Make reviewers separate agents by lens.

Rejected for v1. `agy-reviewer` with explicit lenses is enough and keeps the surface smaller.

Register marketplace metadata first.

Rejected. Existing release discipline treats metadata as a shipping surface. Registering early would
advertise a teammate capability before harness proof exists.

## Success Metrics

- Static tests prove plugin packaging, frontmatter, command/agent prompt contracts, schema/status
  validation, and release-triad sync.
- Direct wrapper tests prove fake-`agy` success, timeout, no-output, fallback, patch-only,
  auto-apply refusal, out-of-scope mutation, and bundle write behavior.
- Live Claude Code harness proof records one reviewer and one coder run where transcripts show the
  packaged agents invoked the wrapper/`agy` path.
- `auto-if-clean` applies only with an explicit write-set and passing verification; all refusal
  cases preserve evidence without mutating the live tree.
- The final PR changes release surfaces together and passes `PYTHONPATH=. python3 -m pytest -q`.

## Plan Review Gate

Before implementation, run:

```text
$saga:doc-review docs/plans/2026-06-30-antigravity-teammate-plugin-plan.md
```

The doc-review should specifically challenge:

- Whether disposable clone patch import is implementable with current repo tooling.
- Whether Bash-only agents are sufficient to force the wrapper path in Claude Code.
- Whether U6's live harness proof is concrete enough to be run by another agent/operator.
- Whether marketplace registration really remains last in the implementation order.

## Sources / Research

- `docs/brainstorms/2026-06-30-antigravity-teammate-plugin-requirements.md:13` to
  `docs/brainstorms/2026-06-30-antigravity-teammate-plugin-requirements.md:16` for the teammate
  and shared-wrapper product frame.
- `docs/brainstorms/2026-06-30-antigravity-teammate-plugin-requirements.md:75` to
  `docs/brainstorms/2026-06-30-antigravity-teammate-plugin-requirements.md:85` for the primary
  Claude-facing surfaces.
- `docs/brainstorms/2026-06-30-antigravity-teammate-plugin-requirements.md:123` to
  `docs/brainstorms/2026-06-30-antigravity-teammate-plugin-requirements.md:140` for write modes
  and managed apply semantics.
- `docs/brainstorms/2026-06-30-antigravity-teammate-plugin-requirements.md:144` to
  `docs/brainstorms/2026-06-30-antigravity-teammate-plugin-requirements.md:155` for evidence and
  status requirements.
- `docs/brainstorms/2026-06-30-antigravity-teammate-plugin-requirements.md:159` to
  `docs/brainstorms/2026-06-30-antigravity-teammate-plugin-requirements.md:171` for proof and
  release discipline.
- `docs/reviews/2026-06-30-antigravity-teammate-plugin-requirements-readiness.md:46` to
  `docs/reviews/2026-06-30-antigravity-teammate-plugin-requirements-readiness.md:54` for accepted
  planning residuals.
- `AGENTS.md:39` to `AGENTS.md:59` for CLI-plugin shape.
- `AGENTS.md:97` to `AGENTS.md:108` for release-surface discipline.
- `tests/test_release_triad.py:1` to `tests/test_release_triad.py:19` for release-triad intent.
- `tests/test_deploy_plugin.py:36` to `tests/test_deploy_plugin.py:61` for plugin contract-test
  precedent.
- `tests/test_team_execution_plugin.py:55` to `tests/test_team_execution_plugin.py:87` for
  marketplace and agent packaging tests.
- `plugins/saga/agents/mechanical-executor.md:1` to
  `plugins/saga/agents/mechanical-executor.md:14` for Bash-only agent precedent.
- `.gitignore:54` to `.gitignore:58` for ignored local Claude/Antigravity state.
- `docs/engineering-journal/LEARNINGS.md:30` to
  `docs/engineering-journal/LEARNINGS.md:42` for silent Claude-fallback proof.
- `docs/engineering-journal/LEARNINGS.md:46` to
  `docs/engineering-journal/LEARNINGS.md:58` for the background detach/hang trap.
- `docs/external-agent-delegation/blueprint.md:125` to
  `docs/external-agent-delegation/blueprint.md:129` for clone versus filesystem containment.
- `docs/external-agent-delegation/blueprint.md:135` to
  `docs/external-agent-delegation/blueprint.md:156` for re-derived diff and sole-committer
  validation.
- `docs/external-agent-delegation/blueprint.md:160` to
  `docs/external-agent-delegation/blueprint.md:179` for wrapper-forced path and no-background
  guidance.
