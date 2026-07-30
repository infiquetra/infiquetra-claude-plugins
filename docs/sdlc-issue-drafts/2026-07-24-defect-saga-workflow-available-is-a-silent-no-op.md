---
title: defect(saga): --workflow-available is a silent no-op without --host-capable
repo: infiquetra-claude-plugins
type: defect
team: asgard
project: operations
status: Shaping
labels: defect, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
---

# defect(saga): --workflow-available is a silent no-op without --host-capable

## Summary

`outcome.py advance --workflow-available` is a **silent no-op** unless `--host-capable` is also
passed. The operator gets an unexplained availability HALT while having passed the exact flag the
CLI help says enables the backend.

## Evidence

`plugins/saga/scripts/outcome_dispatcher.py:451` (in `resolve_available`, defined at `:438`):

```python
avail = set(ALWAYS_AVAILABLE)
if host_capable:
    avail |= {"fork", "subagent", "goal"}
if host_capable and workflow_available:      # <-- :451, requires BOTH
    avail.add("cc-workflows-ultracode")
```

The operator-facing help at `plugins/saga/scripts/outcome.py:2438-2440` reads as standalone, with
no mention of the coupling:

```python
"--workflow-available",
action="store_true",
help="this host can run cc-workflows-ultracode (the Workflow tool is present)",
```

The function **docstring** does state the coupling ("`workflow_available` *additionally* enables
`cc-workflows-ultracode`"). The defect is that the coupling is documented only where the operator
never looks — the CLI surface contradicts it by omission.

## Reproduction

Observed during the #626 R-live acceptance run (2026-07-24) on a host where both the Agent and
Workflow tools were genuinely present:

```
$ outcome.py advance <id> --workflow-available
  -> HALT: "cc-workflows-ultracode unavailable"

$ outcome.py advance <id> --host-capable --workflow-available
  -> dispatched, backend='cc-workflows-ultracode'
```

The halt reason names the backend, not the missing flag, so nothing connects the failure to the
operator's input. It reads as a host-capability fault.

## Impact

Bounded but misleading. No data corruption and no silent wrong-backend dispatch — the halt is loud.
The cost is diagnostic: an operator who passes the documented flag and gets an availability halt
has no signal pointing at the second flag, and the natural next step is to investigate the host or
the Workflow tool rather than the command line.

`degrade_policy` sharpens this. Under the default (`"none"`) an unavailable `cc-workflows-ultracode`
node degrades one rung down `DEGRADE_LADDER` to `team-execution` and then `inline` — so the tick
*appears to succeed* while the external path was never exercised. The R-live run surfaced the flag
coupling only because every probe node deliberately carried `degrade_policy: "halt"`.

## Fix shapes (not prescriptive)

1. **Imply it** — `--workflow-available` sets `host_capable` too.
2. **State it** — amend the CLI help to name the dependency, and/or make the flags argparse-dependent
   so a lone `--workflow-available` errors at parse time.
3. **Explain it** — when `workflow_available and not host_capable`, warn, or make the halt reason
   say `"cc-workflows-ultracode unavailable: --workflow-available requires --host-capable"`.

Shape 2 or 3 is preferable to 1: implying a flag weakens the conservative-default contract that
`resolve_available`'s docstring is explicit about ("the coordinator never claims a host-dependent
backend it cannot verify").

### Files expected to change

- `plugins/saga/scripts/outcome_dispatcher.py` — `resolve_available` (`:438-453`) and/or the halt
  reason string that reports an unavailable backend.
- `plugins/saga/scripts/outcome.py` — the `--workflow-available` / `--host-capable` argparse
  definitions at `:2438-2441`.
- Release surfaces if a code path changes: `plugins/saga/.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`, `plugins/saga/CHANGELOG.md`, drift pins.

### Tests to add or update

- `tests/test_outcome_dispatcher.py` — `resolve_available(host_capable=False,
  workflow_available=True)` pins the chosen behavior for the currently-untested combination.
- A CLI-surface test asserting the `--workflow-available` help text and `resolve_available` agree,
  so the two cannot drift apart again.

### Context library links

_none_

### Acceptance criteria

- [ ] `resolve_available(host_capable=False, workflow_available=True)` either includes
      `cc-workflows-ultracode` or the CLI refuses/warns naming `--host-capable` — it must not
      silently return the always-available floor.
- [ ] `outcome.py advance --help` describes the `--workflow-available` / `--host-capable`
      relationship consistently with `resolve_available`.
- [ ] A test in `tests/test_outcome_dispatcher.py` pins the `workflow_available and not
      host_capable` combination and fails against current code.

### Verification

```
uv run pytest -q tests/test_outcome_dispatcher.py tests/test_outcome.py
uv run python plugins/saga/scripts/outcome.py advance --help
```

### Objective

`improve-claude-plugins` (Operations board). A follow-up finding from #626, not a leaf of the
governed-execution-integrity DAG.

### Intent

An operator who passes `--workflow-available` gets either the external backend or an explanation —
never a silent downgrade to the always-available floor with a halt reason that blames the host.

### Target repo / surface

`infiquetra-claude-plugins` — `plugins/saga/scripts/outcome_dispatcher.py` (`resolve_available`) and
the `outcome.py advance` argument parser.

### Mode

build

### Constraints

Do not weaken the conservative default: with neither flag, the coordinator must still resolve only
`ALWAYS_AVAILABLE`. No change to `DEGRADE_LADDER` order or to `ALWAYS_AVAILABLE` membership. Saga
patch bump only — no `fleet_commons/` change is expected, so no fleet-core bump.

### Risk

medium — the seam is small and well covered, but `resolve_available` gates every outcome dispatch,
so a wrong change could enable a backend the host cannot actually run.

### Transfer notes

Reproduced live during #626 R-live; both flags were honest on that host (Agent and Workflow tools
present). The `degrade_policy: "halt"` detail is the important one for whoever picks this up — with
the default policy the symptom is invisible, so any regression test must pin `halt`, not `none`.

### Out-of-scope / non-goals

The `DEGRADE_LADDER` semantics themselves (correct as designed); the settlement/halt model
(#626, closed); `degrade_policy` defaults; any change to which backends `ALWAYS_AVAILABLE` covers.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context

- Source: `docs/validation/issue-626-rlive/acceptance.md` (merged PR #656 -> `474fd3cc`)
- Source type: acceptance-evidence
- Found during the #626 R-live acceptance leg; not fixed there because #626 shipped zero production
  code by design.

### Recommended Tier Band
sonnet/medium

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/657
- Number: 657
- Created at: 2026-07-24T23:39:08.583089+00:00

