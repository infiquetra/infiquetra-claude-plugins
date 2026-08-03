---
title: Verify panel quorum floor is still satisfiable after refuting verifiers go missing at odd n
repo: infiquetra-claude-plugins
type: defect
team: asgard
project: operations
status: Shaping
labels: defect, hermes-task, needs-plan
risk: medium
mode: actionable
handoff_maturity: requirements-ready
---

# Verify panel quorum floor is still satisfiable after refuting verifiers go missing at odd n

### Objective
Decide and implement what a verify panel should do when enough verifiers go missing that the
surviving reporters could not have produced the refutation the panel would otherwise have reached,
even though the survivor count still clears the strict-majority quorum floor.

### Intent
Issue #686 fixed the even-`n` case: the emit-time quorum floor was `ceil(n/2)` while the runtime
disagreement threshold is `ceil(k/2)` over surviving reporters `k`. Those agree at odd `n` and
differ by one at even `n`, so a panel that lost exactly half its verifiers still cleared its floor,
and because the lost verdicts were the refuting ones a HALT silently became a PASS. The floor is now
`n // 2 + 1`, validated over 238 executed scenarios.

That fix does not close the odd case. At odd `n >= 5` a panel can lose verifiers, still clear
`n // 2 + 1`, and reach the opposite verdict from the one full strength would have produced. With
`n = 5` and floor 3, two verifiers going missing leaves 3 reporters. If both missing verdicts were
refutations, full strength would be 2 refutations plus a possible third, while the surviving 3
report clean and the panel passes.

This is a **policy question before it is a code change**, which is why it was deferred out of #686
rather than fixed there. The strict reading — require full strength from every panel, halting on any
missing verifier — would change behavior for all 36 committed `n=3` panels in this repository, every
one of which currently tolerates one missing verifier. That is a real behavior change to the whole
fleet's gate, not a bug fix, and it belongs to the operator.

Pre-existing and P3. It has not been observed to fire.

### Out-of-scope / non-goals
- Do not silently tighten the floor for existing `n=3` panels as a side effect. If the chosen policy
  changes their behavior, say so explicitly and get operator sign-off first.
- Do not revisit the even-`n` fix from #686; it is settled and validated.
- Do not change `refuted_deliverable` versus `advisory_corrections` semantics.

### Files expected to change
- `plugins/saga/scripts/execution_spec.py` (`_emit_panel_reconciliation`, `_emit_verify_panel`)
- `tests/test_saga_execution_spec.py`
- `plugins/saga/references/execution-spec.md`
- `docs/engineering-journal/DECISIONS.md`
- `plugins/saga/CHANGELOG.md`, `plugins/saga/.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`

### Tests to add or update
- Extend the existing panel-size scenario sweep to assert the chosen policy at odd `n` in the range
  5 to 9, covering every count of missing verifiers that still clears the floor.
- Pin the behavior of `n = 3` panels explicitly so any future change to them is a deliberate,
  visible test edit.

### Context library links
- `docs/engineering-journal/LEARNINGS.md` anchor `{#quorum-floor-must-be-a-strict-majority}`
- `docs/engineering-journal/DECISIONS.md` anchor `{#verify-panel-severity-axis-686}`
- `plugins/saga/references/execution-spec.md`
- `docs/work-sessions/2026-08-03-verify-panel-severity-axis.md`

### Acceptance criteria
- [ ] A DECISIONS entry records the chosen policy, the alternatives rejected, and a "revisit when"
   condition — written before the code change, since the code follows the decision.
- [ ] The scenario sweep covers odd `n` in 5, 7, 9 for every survivor count at or above the floor, and
   asserts the chosen policy in each cell.
- [ ] A test pins `n = 3` behavior explicitly and states in a comment whether the policy changed it.
- [ ] `uv run python -m pytest -q` exits 0.
- [ ] If the policy changes any of the 36 committed `n=3` panels, the pull request body states which
   ones and why, and the change is not merged without explicit operator confirmation.

### Verification
```bash
uv run python -m pytest tests/test_saga_execution_spec.py -q
uv run python -m pytest -q
grep -rc 'quorum floor' plugins/saga/scripts/execution_spec.py
uv run python scripts/check_release_surface_parity.py
```

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: /private/tmp/claude-501/-Users-jefcox-workspace-infiquetra-infiquetra-claude-plugins/69f09efc-465e-4e84-9258-fcca4901722b/scratchpad/cards/02-quorum-floor-odd-n.md
- Source type: local-file
- Source title: 02-quorum-floor-odd-n

### Recommended Tier Band
opus/high

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/692
- Number: 692
- Created at: 2026-08-03T19:54:26.926110+00:00

