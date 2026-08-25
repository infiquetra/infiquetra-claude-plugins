---
title: [ENHANCEMENT] gate.sh needs a supported long-run pattern for the ten-minute foreground timeout
repo: infiquetra-claude-plugins
type: enhancement
team: asgard
project: operations
status: Shaping
labels: enhancement, needs-plan
risk: low
handoff_maturity: requirements-ready
---

# [ENHANCEMENT] gate.sh needs a supported long-run pattern for the ten-minute foreground timeout

### Objective

Give sessions a supported way to run the full quality gate that survives the ten-minute foreground
tool timeout, avoids duplicate concurrent runs, and reliably captures completion status.

## Observed behavior

A saga:work session in the unifi/fleet-core repair train ran `bash scripts/gate.sh` in the
foreground exactly as CLAUDE.md instructs ("Before pushing, run the whole gate — not a subset").
The Bash tool's default 600000ms foreground timeout killed it (exit 143) with only a `base=<sha>`
line printed — the gate's first visible step had not finished printing. The session then re-ran the
identical command backgrounded with redirected output and polled the file. Every fresh session
following the instruction literally loses a full ten-minute cycle before discovering this, and a
naive retry risks overlapping duplicate gate runs.

## Operator impact

One wasted timeout cycle per fresh session; risk of duplicate concurrent gate runs after the kill;
completion status captured ad hoc instead of reliably.

## Evidence and provenance

- `~/.claude/projects/-Users-jefcox-workspace-infiquetra-orch-o3-fleetcore-retry-after/0981fa8e-357f-49a8-9fc2-5634d2f1de33.jsonl`
  lines 341-347 (2026-08-22T18:54:13Z): killed at exactly the 600000ms default, exit 143, followed
  by the agent's own "The gate exceeds the ten-minute foreground limit" and a backgrounded re-run.
- Transcript-audit report: `/private/tmp/plugin-transcript-audit-20260823/FINAL-REPORT.md`, finding E4 (lane3-02).

### Intent

Document (and lightly tool) the supported long-run invocation: a backgrounded run with a named
log/result location and a completion marker, duplicate-run protection or a stated safe re-entry
rule, and a doc note that the full 24-step gate is expected to exceed common foreground timeouts.

### Out-of-scope / non-goals

- Changing what the gate checks, its 24-step coverage contract, its `GATE INCOMPLETE` self-audit
  property, or its exit-code contract (0 green / 1 blocking failure / 2 coverage short).
- Making individual steps faster.

### Files expected to change

- `CLAUDE.md` (Running Quality Checks section)
- `scripts/gate.sh` (result/marker capture and duplicate-run guard, if implemented rather than
  documented)

### Tests to add or update

- If gate.sh gains a lock or result-file mechanism: a minimal `tests/test_gate_invocation.py` (new)
  or shell self-test asserting the marker/lock behavior; otherwise documentation-only with the
  verification commands below.

### Context library links

- source_context: `/private/tmp/plugin-transcript-audit-20260823/issue-sources/4-gate-timeout-guidance.md`
  (audit task dir — ephemeral; durable anchor is the transcript path above)

### Acceptance criteria

- [ ] `grep -n "background" CLAUDE.md` shows the Running Quality Checks section documenting the
      supported long-run invocation and stating the expected >10-minute runtime.
- [ ] Following the documented invocation, a completed run's outcome (pass/fail plus failing step)
      is capturable from a named file or marker — for example `tail -1 <documented-result-file>`
      shows the final status line — without scraping a live terminal.
- [ ] The documented pattern includes duplicate-run protection or an explicit safe re-entry rule —
      verifiable via `grep -n -iE "lock|already running|re-entry" CLAUDE.md scripts/gate.sh`.
- [ ] `bash -n scripts/gate.sh` exits 0 and the 0/1/2 exit-code contract is restated where the new
      pattern is documented.

### Verification

```bash
bash -n scripts/gate.sh
grep -n "background" CLAUDE.md
grep -n -iE "lock|already running|re-entry" CLAUDE.md scripts/gate.sh
# implementation validates once to completion and once with an early kill,
# confirming captured status both times
```

Validation belongs in implementation — no fresh reproduction was required to file (operator
instruction, 2026-08-24).

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

### Recommended Tier Band

sonnet/medium

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/782
- Number: 782
- Created at: 2026-08-24T03:58:37.014335+00:00

