---
title: "defect(fleet,saga): lease refusal names the condition but never the remedy — operators patch installed hooks instead"
repo: infiquetra-claude-plugins
type: defect
team: asgard
project: operations
status: Shaping
labels: defect, hermes-task, needs-plan
risk: medium
mode: implement
handoff_maturity: requirements-ready
---

# defect(fleet,saga): lease refusal names the condition but never the remedy — operators patch installed hooks instead

### Objective

Make the fleet-lease refusal self-remedying at the point of failure. The message today tells an
operator what is missing and gives them no supported way forward, and the observed consequence is
that operators reach for an unsupported workaround that silently evaporates at the next release.

### Intent

When a subagent claims a lease with no matching provisional reservation,
`plugins/fleet-core/scripts/fleet_commons/lease_broker.py:2880` raises
`no live provisional reservation for session=<id>, agent_type=<kind>, batch_id=<batch>`. Both
operator-facing surfaces in `plugins/saga/hooks/lease_lifecycle_hook.py` pass that string through
and add nothing actionable: `_halt()` (line 31, `PreToolUse`) prefixes
`HALT — agent reservation refused before spawn:` and exits 2; `_warn_child()` (line 35,
`SubagentStart`) wraps it with `All delegated mutation tools will fail closed`.

Neither surface states the three things the operator needs: **the trigger** (this is the expected
refusal when a `Workflow` is launched without the `reserve()` → `attest()` → `claim()`
choreography — a `Workflow` started outside a saga skill produces it by construction, not by
malfunction); **the supported bypass** (`INFIQUETRA_FLEET_LEASE_ENFORCEMENT=off`, already read by
`_enforcement_disabled()` at line 18 of the same file); and **the correct fix** (launch through a
saga skill so the choreography runs). The kill switch is named to a human in exactly one place —
line 22, the branch that only fires once someone already knows to set it. At the moment of
refusal, the only moment the operator is looking, it is invisible.

This is a defect rather than a wording preference because the gap has a demonstrated failure
chain, observed 2026-07-24 → 2026-07-25. Enforcement refused Workflow subagents with this message;
lacking any stated remedy an operator neutralized `lease_lifecycle_hook.py` and
`lease_mutation_hook.py` **inside the installed plugin cache** (`saga/0.114.0/hooks/`) with
unconditional early returns, leaving `.orig-2026-07-24` backups beside them; the saga 0.115.0
release then shipped clean copies from git, silently re-arming enforcement with no signal that a
deliberate operator decision had been reverted. Patching installed files cannot survive a release
and the env var can, so the diagnosability gap directly produced an unsafe, non-durable
configuration change.

Planning must adjudicate where the remedy text belongs: at the broker raise site (one message,
inherited by every consumer, but `fleet_commons` is vendored into consumer plugins under a
byte-frozen drift guard) or in the hook adapters (free to change, but two call paths to keep in
sync). State the choice with rationale; do not assume it.

### Out-of-scope / non-goals

- Changing *when* the lease refuses. The refusal is correct fail-closed behavior and stays armed by
  default. This issue changes only what the operator is told.
- Broadening the kill switch's semantics. `_enforcement_disabled()` accepting only the exact string
  `off` is a deliberate fail-safe direction (#615) and is preserved verbatim.
- The other `LeaseNotFoundError` raise sites in `lease_broker.py` (13 beyond this one), unless the
  planning survey shows the same remedy-free shape reaching an operator surface — in which case
  name each explicitly rather than silently widening scope.
- Cleaning up the stale `.orig-2026-07-24` backups in the now-inert 0.114.0 plugin trees. Cosmetic,
  and separable from this change.
- \#642 (`installed_plugins.json` staleness). It bites the same rollout but is a distinct mechanism.
- \#647 / \#646 / \#645 lease-family defects. Independent; do not bundle.

### Files expected to change

- `plugins/saga/hooks/lease_lifecycle_hook.py` — `_halt()` and `_warn_child()`, the two surfaces an
  operator actually reads.
- `plugins/fleet-core/scripts/fleet_commons/lease_broker.py` — the raise site at line 2880, only if
  planning chooses the broker-side option; respects the freeze/port contract if so.
- `tests/test_lease_lifecycle_hook.py` — new red-first assertions on both operator surfaces.
- `plugins/saga/CHANGELOG.md` and `plugins/saga/.claude-plugin/plugin.json` — release surface.
- `plugins/fleet-core/CHANGELOG.md` and `plugins/fleet-core/.claude-plugin/plugin.json` — only if
  `fleet_commons/` is touched.
- `.claude-plugin/marketplace.json` — version sync for whichever plugins bump.
- `docs/engineering-journal/DECISIONS.md` — the raise-site-vs-adapter placement decision.

### Tests to add or update

- Red-first: a test that the `PreToolUse` `_halt()` stderr contains the literal
  `INFIQUETRA_FLEET_LEASE_ENFORCEMENT`, failing against the current tree.
- Red-first: a test that the `SubagentStart` `_warn_child()` JSON `additionalContext` names both the
  kill switch and the reserve/attest choreography, failing against the current tree.
- Regression pin: `_halt()` still raises `SystemExit(2)` and `_warn_child()` still emits valid JSON
  with `hookEventName == "SubagentStart"` — the message change must not alter posture.
- Characterization (must pass before and after): `_enforcement_disabled()` returns `True` only for
  the exact string `off`, `False` for `"Off"`, `"1"`, `"true"`, and absence.
- If the broker is touched: the `fleet_commons` byte-freeze drift-guard test updated in the same PR.

### Context library links

_none_

### Acceptance criteria

- [ ] Both operator surfaces name the remedy. `uv run pytest tests/test_lease_lifecycle_hook.py -q`
      passes, including the two new assertions that the emitted text contains
      `INFIQUETRA_FLEET_LEASE_ENFORCEMENT` and a reference to the reserve/attest choreography.
- [ ] Red-first is proven, not claimed. Running the two new tests against the pre-fix tree via
      `git stash && uv run pytest tests/test_lease_lifecycle_hook.py -q; git stash pop` reports
      exactly those 2 tests failing, and the output is pasted into the work-session record.
- [ ] Fail-closed posture is unchanged. A test asserts `_halt()` exits `2`; confirm with
      `uv run pytest tests/test_lease_lifecycle_hook.py -q -k "halt and exit"` → passing.
- [ ] Kill-switch semantics unchanged. `uv run pytest tests/ -q -k "enforcement_disabled"` passes
      with no test body edited (verify via `git diff --stat` showing no deletions in those tests).
- [ ] Release surfaces are in parity. `uv run python scripts/check_release_surface_parity.py` exits
      `0` and reports all plugins in parity.
- [ ] Version drift pins updated for every bumped plugin. `uv run pytest tests/test_saga_plugin.py -q`
      passes (and `tests/test_liveness_events.py` if `fleet-core` bumped).
- [ ] Full gate green. `uv run pytest -q` reports `0 failed`; `uv run ruff check .` and
      `uv run ruff format --check .` both clean; `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`
      exits `0`.

### Verification

Reproduce the current remedy-free output, then confirm the fix. The refusal is reachable by
invoking the hook adapter directly with a `SubagentStart` envelope carrying a session that has no
live provisional reservation:

```bash
# Current (defective) behavior — additionalContext names no remedy.
echo '{"hook_event_name":"SubagentStart","session_id":"no-such-session",
       "agent_type":"general-purpose","batch_id":"no-such-batch"}' \
  | python3 plugins/saga/hooks/lease_lifecycle_hook.py

# Expected BEFORE the fix: JSON whose additionalContext ends at
#   "...All delegated mutation tools will fail closed; return control to the parent."
# with no mention of INFIQUETRA_FLEET_LEASE_ENFORCEMENT or reserve/attest.

# Expected AFTER the fix: the same JSON, additionalContext additionally naming
#   the reserve/attest trigger, INFIQUETRA_FLEET_LEASE_ENFORCEMENT=off, and
#   "launch through a saga skill" as the correct fix.

# Grep assertion form used by the new tests:
echo '{...same envelope...}' | python3 plugins/saga/hooks/lease_lifecycle_hook.py \
  | grep -q 'INFIQUETRA_FLEET_LEASE_ENFORCEMENT' && echo REMEDY-PRESENT || echo REMEDY-ABSENT
```

Evidence anchors, all verified live at `origin/main` `b464d090` (saga 0.115.0, fleet-core 0.23.0):

```
plugins/fleet-core/scripts/fleet_commons/lease_broker.py:2880   the raise
plugins/saga/hooks/lease_lifecycle_hook.py:15                   _KILL_SWITCH defined
plugins/saga/hooks/lease_lifecycle_hook.py:18-27                _enforcement_disabled() — only human mention
plugins/saga/hooks/lease_lifecycle_hook.py:31-33                _halt() — no remedy text
plugins/saga/hooks/lease_lifecycle_hook.py:35-48                _warn_child() — no remedy text
plugins/saga/hooks/lease_lifecycle_hook.py:71-77                except Exception → routes message verbatim
```

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

### Recommended Tier Band

opus/high

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/661
- Number: 661
- Created at: 2026-07-25T23:22:14.283616+00:00

