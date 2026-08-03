---
title: Emitted harness advisory accumulator never resets between units
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

# Emitted harness advisory accumulator never resets between units

### Objective
Reset the emitted harness's advisory accumulator at each panel boundary so advisories reported by
one unit's verify panel cannot be attributed to a later unit's panel.

### Intent
`plugins/saga/scripts/execution_spec.py` emits a JavaScript harness that a Claude Code workflow
runs. Inside that harness, `__advisories` is declared once at module scope and only ever appended
to. `__logAdvisory()` pushes every rendered advisory item onto it, and `__halt()` attaches the whole
array to the thrown error as `error.advisory_corrections`.

Nothing clears it between units. In a multi-unit run the array a consumer reads at unit 5 still
contains everything units 1 through 4 reported. A driver that reads `advisory_corrections` off a
halt in order to decide what to correct will act on advice about units that already settled
successfully.

Severity is P3 and this is pre-existing, not introduced by #686. It is bounded in practice — the
render path caps each panel round at 50 items of 180 characters — so this is misattribution and
slow growth, never a flipped gate verdict. No panel committed in this repository reaches it today
because all 36 are single-round `n=3` panels, but `iterate_to_consensus` and `escalate_on_signal`
panels do run multiple rounds per unit.

### Out-of-scope / non-goals
- Do not change the gating semantics. `refuted_deliverable` still halts; `advisory_corrections`
  stays non-gating.
- Do not change the render, scrub, or truncation behavior added in #686.
- Do not change the per-round item caps.
- Do not touch `__advisoryRounds`, whose per-unit ordinal counting is correct as shipped.

### Files expected to change
- `plugins/saga/scripts/execution_spec.py` (the `_JS_ADVISORY_HELPER` template and whichever emit
  site owns the per-unit boundary)
- `tests/test_saga_execution_spec.py`
- `plugins/saga/references/execution-spec.md`
- `plugins/saga/CHANGELOG.md`, `plugins/saga/.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`

### Tests to add or update
- A node-executed test that runs a harness with two units, each with a verify panel that reports
  advisories, and asserts the second unit's returned `advisory_corrections` contains only its own
  items.
- A test that a halt raised in the second unit does not carry the first unit's advisories.
- Confirm the existing `advisory_corrections` tests still pass unchanged.

### Context library links
- `plugins/saga/references/execution-spec.md`
- `docs/engineering-journal/DECISIONS.md` anchor `{#verify-panel-severity-axis-686}`
- `docs/work-sessions/2026-08-03-verify-panel-severity-axis.md`

### Acceptance criteria
- [ ] `uv run python -m pytest tests/test_saga_execution_spec.py -q` exits 0.
- [ ] A new test proves cross-unit isolation: with two units each reporting one advisory, the second
   unit's returned array has length 1, not 2.
- [ ] Reverting the reset in a scratch copy of `execution_spec.py` makes that new test fail (mutation
   proof), and this is recorded in the pull request body.
- [ ] `uv run python -m pytest -q` exits 0 with no reduction in the existing pass count.
- [ ] Plugin release surfaces tell the same story as the diff: version bumped in
   `plugin.json`, `marketplace.json` and `CHANGELOG.md`.

### Verification
```bash
uv run python -m pytest tests/test_saga_execution_spec.py -q
uv run python -m pytest -q
uv run ruff check . && uv run ruff format --check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
uv run python scripts/check_release_surface_parity.py
```

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: /private/tmp/claude-501/-Users-jefcox-workspace-infiquetra-infiquetra-claude-plugins/69f09efc-465e-4e84-9258-fcca4901722b/scratchpad/cards/01-advisory-accumulator-reset.md
- Source type: local-file
- Source title: 01-advisory-accumulator-reset

### Recommended Tier Band
opus/high

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/691
- Number: 691
- Created at: 2026-08-03T19:54:05.341475+00:00

