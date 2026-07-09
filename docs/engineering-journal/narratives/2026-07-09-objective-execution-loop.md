# Objective Execution Loop

This is the reusable operating loop for multi-issue objectives and outcome-backed campaigns in
`infiquetra-claude-plugins`. Use it when an objective has a live child issue set and the operator asks
to "run the loop", "drive the outcome", or "work through the objective".

The loop came from two successful patterns:

- `team-freya` `freya-uplift`: seed or resume the outcome from live issue evidence, respect real
  dependency order, then carry execution through deploy/readback/closeout when the coordinator cannot
  finish locally.
- `infiquetra-claude-plugins` `defects-claude-plugins`: enumerate the full objective-linked set first,
  then run each leaf through plan, review, work, review, PR, CI, closeout, and board verification.

## Canonical Loop

1. Enumerate the full live objective set before choosing work.
2. Read outcome status and attend the next leaf.
3. Route the leaf with `/loop`; for requirements-ready leaves this should normally become `/plan`.
4. Run `/plan` and write a durable `docs/plans/...` implementation plan.
5. Run `/doc-review` before implementation.
6. Fix all actionable review findings before asking for approval; unresolved P0/P1 findings block
   `/work` unless the operator explicitly overrides with rationale.
7. Run `/work` from the reviewed plan.
8. Run `/code-review` at the PR boundary and fix findings until clean.
9. Open or update the PR, merge only after required checks are green, and re-query GitHub for fresh
   check status before calling it merged.
10. Verify issue closeout from GitHub truth, then move the board card through Verify and Done.
11. Re-run `outcome.py advance <outcome-id>` to harvest completions and choose the next leaf.
12. Repeat until the parent objective has no open actionable children.

## Command Shape

For an outcome-backed objective:

```bash
python3 plugins/saga/scripts/outcome.py status <outcome-id>
python3 plugins/saga/scripts/outcome.py attend <outcome-id> <subplot-id>
python3 plugins/saga/scripts/saga.py scan
```

The `attend` command gives the native leaf handoff, usually `/resume issue-<N>` or a direct
`/plan issue-<N>` route after a local saga tick exists. `/loop` is the cross-phase router; the
destination command owns its own phase.

For board objective sweeps:

```bash
gh project item-list 3 --owner infiquetra --limit 200 --format json
```

Filter by the board `Objective` field before touching a card. Do not work only from the visible board
column; that caused drift toward the currently visible work instead of the full objective.

## Gates And Truth Sources

- Outcome state is derived on read from the spec, store, and GitHub evidence. Do not treat authored
  `node.state` in `outcome-spec.json` as completion truth by itself.
- `/doc-review` is the hard readiness gate before `/work`; P0/P1 findings block work unless explicitly
  overridden.
- `/code-review` is the merge-readiness gate after implementation.
- GitHub PR state, check rollups, issue state, and the Operations board are the final closeout truth.
- `outcome advance --autonomous` can write board state only inside its reversibility-gated envelope.
  Without that flag, outcome ticks are read/derive/dispatch only.

## Current Application

For objective `infiquetra-claude-plugins#336` (`external-engine-offload`), the active outcome id is
`external-engine-offload`. The first resumed leaf is `issue-389`, routed to:

```text
/plan issue-389
```

Run that leaf through this loop, then harvest the outcome and continue with the next open leaf.
