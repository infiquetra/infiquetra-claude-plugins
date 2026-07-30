---
title: enhancement(saga): pre-push gate step timeout is hard-coded at 300s with no headroom or override
repo: infiquetra-claude-plugins
type: enhancement
team: asgard
project: operations
status: Shaping
labels: enhancement, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
---

# enhancement(saga): pre-push gate step timeout is hard-coded at 300s with no headroom or override

## Summary

The pre-push gate runs every manifest step under a hard-coded 300-second timeout with no
configuration and no environment override. The repo's own test step measured **264 s** on
2026-07-24 — roughly 12 % headroom — and has already produced one false FAIL under CPU contention.

## Evidence

`plugins/saga/hooks/pre_push_gate_hook.py:93-103` — the timeout is a literal in the generic step
runner, so it applies uniformly to every step in `tools/gate-manifest.json`:

```python
result = subprocess.run(
    cmd,
    capture_output=True,
    text=True,
    cwd=str(cwd),
    timeout=300,            # <-- :98, hard-coded, no override
)
except subprocess.TimeoutExpired:
    return False, "timed out after 300 s"
```

Measured on 2026-07-24 in this repo, running the gate's exact pytest command
(`uv run python -m pytest -q --no-cov`):

```
5439 passed, 1 skipped in 264.22s
```

264 s against a 300 s cap. The other manifest steps (`ruff format --check`, `ruff check`, `mypy`,
and the remainder) are far below the cap and are not at risk.

## Observed failure

During the #626 evidence push the gate reported `FAIL: pytest / timed out after 300 s`. The suite
was not broken and nothing was wrong with the tree — a background test run in the same session was
competing for CPU. Stopping it and re-running measured the 264 s above, and the retried push
passed. The cap converts ordinary machine load into a push refusal that presents as a test-gate
failure.

## Why this gets worse

The margin is a function of suite size, and the suite grows with every leaf: 5286 tests on
2026-07-20, 5436 on 2026-07-24, 5439 now. At that rate the pytest step crosses 300 s on an
unloaded machine within a few campaign leaves, at which point the gate fails *deterministically*
for everyone and the only remedy is editing hook source.

There is also no way for an operator who knows they are on a loaded machine to raise the ceiling
for one push — the value is read from neither the manifest, an env var, nor a settings file.

## Fix shapes (not prescriptive)

1. **Per-step timeout in the manifest.** `tools/gate-manifest.json` already single-sources *what*
   the gate runs; letting a step declare `timeout_seconds` (default 300) puts the slow step's
   budget next to the slow step. This matches the manifest's stated purpose — "add or remove steps
   here to change what the gate checks — the hook never diverges."
2. **Env override.** Honor e.g. `INFIQUETRA_PRE_PUSH_TIMEOUT` as a ceiling override, in the spirit
   of the existing `INFIQUETRA_FLEET_LEASE_ENFORCEMENT=off` escape hatch.
3. **Distinguish the failure.** A timeout is not a test failure. Report it as a distinct outcome
   with a hint rather than as an indistinguishable FAIL.

1 and 3 are complementary and probably both worth doing; 3 alone would have saved the diagnostic
detour that surfaced this.

### Files expected to change

- `plugins/saga/hooks/pre_push_gate_hook.py` — the step runner at `:93-103` (timeout resolution and
  the `TimeoutExpired` branch's reported outcome).
- `tools/gate-manifest.json` — optional per-step `timeout_seconds` key.
- Release surfaces: `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
  `plugins/saga/CHANGELOG.md`, drift pins.

### Tests to add or update

- `tests/test_pre_push_gate_hook.py` — resolution order (manifest value -> env override -> 300 s
  default); a step declaring nothing still gets 300 s.
- A test asserting a timed-out step is reported distinguishably from a step that exited non-zero.

### Context library links

_none_

### Acceptance criteria

- [ ] A step's timeout budget is declarable in `tools/gate-manifest.json` without editing hook
      source, and a step that declares nothing still gets `300`.
- [ ] A timed-out step is distinguishable in gate output from a genuinely failing step (distinct
      status or message, not a bare `FAIL`).
- [ ] `uv run pytest -q tests/test_pre_push_gate_hook.py` pins the resolution order and the
      timeout-vs-failure distinction.

### Verification

```
uv run pytest -q tests/test_pre_push_gate_hook.py
uv run python -m pytest -q --no-cov --durations=5
```

### Objective

`improve-claude-plugins` (Operations board). A follow-up finding from #626, not a leaf of the
governed-execution-integrity DAG.

### Intent

The gate refuses a push because a check genuinely failed, never because the machine was busy — and
when a budget does need raising, that is a manifest edit rather than a source edit.

### Target repo / surface

`infiquetra-claude-plugins` — `plugins/saga/hooks/pre_push_gate_hook.py` and the
`tools/gate-manifest.json` schema.

### Mode

build

### Constraints

Default behavior must not change for steps that declare nothing (300 s stays the floor). The gate
must not become bypassable: an override may raise a budget, never skip a step. The manifest remains
the single source of what the gate runs — the hook must not diverge from it.

### Risk

medium — the hook gates every push in the repo, so a regression either blocks all pushes or
silently stops enforcing. Blast radius is local (no runtime/production path), and the change is
additive with a preserved default.

### Transfer notes

The 264 s figure is a single measurement on one machine (2026-07-24, this repo, `--no-cov`); treat
it as an order-of-magnitude signal, not a benchmark. Whoever picks this up should re-measure with
`--durations` before choosing a new budget. Note the gate's pytest step passes `--no-cov` while CI
does not, so CI timings are not comparable.

### Out-of-scope / non-goals

Making the suite faster (a separate concern); changing which steps the gate runs; CI workflow
timeouts (GitHub Actions, governed separately); any bypass or skip mechanism for the gate itself.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context

- Source: `docs/validation/issue-626-rlive/acceptance.md` (merged PR #656 -> `474fd3cc`)
- Source type: acceptance-evidence
- Measured during the #626 R-live acceptance leg; flagged rather than changed there, because #626
  shipped zero production code by design.

### Recommended Tier Band
sonnet/medium

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/658
- Number: 658
- Created at: 2026-07-24T23:40:33.538448+00:00

