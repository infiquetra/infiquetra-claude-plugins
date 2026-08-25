---
title: [DEFECT] Orchestrate settles units from pane state: committed work marked failed, stalled work marked done
repo: infiquetra-claude-plugins
type: defect
team: asgard
project: operations
status: Shaping
labels: defect, needs-plan
risk: medium
handoff_maturity: requirements-ready
---

# [DEFECT] Orchestrate settles units from pane state: committed work marked failed, stalled work marked done

### Objective

Settlement must be grounded in completion evidence — commits on the unit branch, a typed result, or
a declared artifact — not in Herdr pane idleness or session presence, which produced wrong outcomes
in both directions.

## Observed behavior

Three incidents across two Team Mimir sessions where orchestration treated Herdr idle/done/session
presence as proof of task outcome:

1. (session 6990cc3c-4d53-46ee-a714-6bfa04b91418, 2026-08-21T03:22–03:23Z) A unit's status read
   `done` and `settle` accepted it — but the status predated a supplemental prompt; `land` then
   reported "COMMITTED NOTHING" because it checked the branch rather than the status.
2. (session b31ec85e-82d5-4a00-aa18-e82cc22b2284, 2026-08-23T17:18:59Z) Herdr reported "done" six
   consecutive times for a unit actually stuck — its background child was `SIGTTIN`-suspended for
   eight minutes; an idle process tree was classified as finished.
3. (same session, 2026-08-23T17:21:29Z) The reverse: a unit whose work had already landed was marked
   `failed` when its Herdr session was closed during operator cleanup — session-gone treated as
   failure.

The skill doc is honest that a single idle is not a settlement
(`plugins/orchestrate/skills/orchestrate/SKILL.md:176-181`) and currently disclaims verifying that a
session "really" finished (SKILL.md:189-193) — but `settle`/`land` still derive success/failure from
pane/session state, and those conclusions were wrong with real cost.

## Operator impact

Incident 1 nearly launched reviewers against an unamended plan; incident 2 wasted eight minutes on a
unit that could never finish; incident 3 would have burned the run's final review cycle redoing
already-landed work. All three were caught only by manually cross-checking git state.

## Evidence and provenance

- `~/.claude/projects/-Users-jefcox-workspace-infiquetra-team-mimir/6990cc3c….jsonl` line 1894
  (2026-08-21T03:23:14Z) — "The session's herdr status was `done` and `settle` accepted that. But
  `land` checks the branch rather than the status, found no commit, and said so."
- `~/.claude/projects/…-team-mimir/b31ec85e….jsonl` line 6569 (2026-08-23T17:18:59Z) — "Herdr saw an
  idle process tree and called it done."; line 6678 (17:21:29Z) — "`settle` marks a unit `failed`
  when its Herdr session is gone — but the operator's cleanup closed `repair2-docs` *after* it had
  successfully committed."
- Transcript-audit report: `/private/tmp/plugin-transcript-audit-20260823/FINAL-REPORT.md`, finding E1 (lane1-05).

### Intent

Require expected-result evidence before settling a worker: `done` needs completion evidence,
`failed` needs failure evidence, and session absence alone yields a distinct orphaned state. Apply
`land`'s branch-truth model at settle time and reconcile the SKILL.md "deliberately does not do"
paragraph with the new contract.

### Out-of-scope / non-goals

- Token counting, spend ceilings, voting panels, durable lock registers (the archived
  full-implementation scope stays retired).
- Herdr's own idle/done classification (dependency context).
- Prompt-delivery confirmation (separate defect filed from the same audit).

### Files expected to change

- `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py`
- `plugins/orchestrate/skills/orchestrate/SKILL.md`
- `tests/test_orchestrate_settlement.py` (new)
- `plugins/orchestrate/.claude-plugin/plugin.json`, `plugins/orchestrate/CHANGELOG.md`,
  `.claude-plugin/marketplace.json` (release-surface parity)

### Tests to add or update

- `tests/test_orchestrate_settlement.py` (new) covering the three observed shapes: stale `done`
  captured before a supplemental prompt; idle-but-stuck (suspended child) never becoming `done`
  without evidence; session-closed-after-commit settling as `done` (not `failed`), with
  session-gone-no-evidence yielding the distinct orphaned state.

### Context library links

- source_context: `/private/tmp/plugin-transcript-audit-20260823/issue-sources/2-orchestrate-settlement.md`
  (audit task dir — ephemeral; durable anchors are the transcript paths above)

### Acceptance criteria

- [ ] `uv run pytest tests/test_orchestrate_settlement.py -q` passes — all three observed incident
      shapes are covered and enforce evidence-based settlement.
- [ ] `python3 plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py settle` (exercised via
      stubbed state in tests) records `done` only with documented completion evidence
      (commit-on-branch, typed result file, or declared artifact); a merely idle pane stays
      unsettled.
- [ ] A closed Herdr session whose branch carries the expected output settles `done`, never
      `failed`; session-gone without evidence produces a distinct named state — asserted in the
      tests above.
- [ ] `grep -n "settlement" plugins/orchestrate/skills/orchestrate/SKILL.md` shows the updated
      contract, including the revised "What this deliberately does not do" paragraph.

### Verification

```bash
uv run pytest tests/test_orchestrate_settlement.py -q
grep -n "settlement" plugins/orchestrate/skills/orchestrate/SKILL.md
scripts/gate.sh
```

Validation belongs in implementation — no fresh reproduction was required to file (operator
instruction, 2026-08-24). Related context, not duplicates: closed #351, closed #495.

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

### Recommended Tier Band

opus/high

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/780
- Number: 780
- Created at: 2026-08-24T03:58:00.125857+00:00

