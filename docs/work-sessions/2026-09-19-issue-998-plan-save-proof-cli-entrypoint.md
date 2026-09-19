# Work session — issue 998, a command-line entrypoint for plan_save_proof.py

Executed the plan `docs/plans/2026-09-19-issue-998-plan-save-proof-cli-entrypoint-plan.md` on
branch `issue/998` in a worktree off base commit `30c36bb5`. All four units landed.

## What was built, by unit

**U1 — PyYAML at its point of use.** The module-scope `import yaml` moved into
`SaveProbe.__call__`, the one place that uses it, with a comment at the import block saying why.
Without this the entrypoint U2 adds would have been born with the defect issue #997 had just
fixed in the sibling file.

**U2 — the self-describing entrypoint.** `main()` plus an `if __name__ == "__main__":` guard at
the foot of `plan_save_proof.py`. `--help` prints what the file is and the command that actually
runs it, at exit 0. Every other direct invocation exits 2 with usage on standard error and
nothing at all on standard output. The module docstring gained a matching line, and the guard
block carries a comment naming `runpy.run_path` and why the loader cannot reach it.

**U3 — the guard and its behavioral mutation.**
`test_proof_cli_describes_itself_and_stays_inert_under_the_loader` in
`tests/test_saga_plan_contract_boundaries.py` covers all four requirements, and
`plan-save-contract-proof-cli` in `tools/canary_registry.json` proves it has teeth.

**U4 — release surfaces and journal.** Saga `0.159.3` across the plugin manifest, the marketplace
entry, the changelog and the pinned version assertion, plus two LEARNINGS entries and one
DECISIONS entry.

## Key decisions

The entrypoint describes and refuses rather than running the proof standalone. A standalone
runner would duplicate `plan_save_contract.py validate` and bypass its tool-revision check, which
exists so the renderer that writes is the one that was verified.

The canary mutation is not the obvious one. Replacing the `__main__` guard with an unconditional
one fires the entrypoint while pytest imports the module, so the run dies with an INTERNALERROR
and the canary reports `error` rather than `caught` — an unproven guard, not a passing one. The
registered mutation returns the success code from a direct invocation instead, which is the
reported defect itself and fails the guard cleanly. Both the rejected mutation and the reason are
recorded in the registry entry.

## Watched failing before it passed

The guard was written first and run against the unmodified file: it failed at the `--help`
assertion with `''.startswith('usage: plan_save_proof.py')`, which is the reported defect exactly
— exit 0, empty output.

Each half of the fix was then reverted on its own to confirm the guard covers both. Restoring the
module-scope `import yaml` killed it at the PyYAML-free interpreter probe with
`ModuleNotFoundError: No module named 'yaml'` at exit 1. The entrypoint's absence was already
covered by the first run above.

## Files modified

- `plugins/saga/scripts/plan_save_proof.py`
- `tests/test_saga_plan_contract_boundaries.py`
- `tools/canary_registry.json`
- `plugins/saga/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `plugins/saga/CHANGELOG.md`
- `tests/test_saga_plugin.py`
- `docs/engineering-journal/LEARNINGS.md`
- `docs/engineering-journal/DECISIONS.md`

## change_kinds

`behavior`

The file gains a command-line surface it did not have and changes what it does with its
arguments, so the hard test gate applies. It is satisfied: one named guard covers all four
requirements, its behavioral mutation reports `caught`, and both halves of the fix were watched
failing on their own.

## Questions answered from the coordinator's message

`AskUserQuestion` was unavailable. Each choice below came from the coordinator's stage-two
message, which is its source unless another is named.

| Question | Answer |
|---|---|
| Resume or mint a saga | Resume `issue-998`; the scan matched it on plan path and branch |
| Branch | Stay on `issue/998` |
| Execution backend | `inline`, which is also what the plan's `backend:` frontmatter says, so the skill honours it without offering |
| Doc-review gate | Passed, nothing open; no override needed or permitted |
| Complexity triage | Small-medium, the skill's documented default for a four-unit plan |
| Round-N detection | Fresh build: the restored saga carried no `pr_refs` |
| Front-loaded ship ceremony (a draft pull request at mint time) | Declined — the coordinator directs a single pull request at the end of this stage |
| Board moves | The three documented ones only: Designing, Ready for Active, Implementing |
| Code review lens selection | `accept-recommended` |
| Fixer dispatch | Never auto-run; repairs applied by hand |
| Gate | `scripts/gate.sh` not run; the fast inner loop plus the release-surface checks, with the pull request's CI as the full gate |
| Merge confirmation | No — the coordinator merges after the required checks pass |

## Next step

Run the code review against base commit `30c36bb5`, then open the pull request to `main`.
