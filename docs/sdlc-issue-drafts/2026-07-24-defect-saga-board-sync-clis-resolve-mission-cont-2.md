---
title: defect(saga): board-sync CLIs resolve mission-control before the certificate gate — an unresolvable install turns a GATED op into a hard error (exit 1)
repo: infiquetra-claude-plugins
type: defect
team: asgard
project: operations
status: Shaping
labels: defect, hermes-task, needs-plan
risk: low
handoff_maturity: requirements-ready
approval_state: needs_operator_approval
---

# defect(saga): board-sync CLIs resolve mission-control before the certificate gate — an unresolvable install turns a GATED op into a hard error (exit 1)

## Problem

Since #620, the two certificate-gated board-sync CLIs resolve the mission-control root
**eagerly** — `resolve_mission_control_root()` — and `return 1` on `RuntimeError`, **before** the
certificate gate is ever evaluated. The gate lives *inside* `authorize_and_write` /
`reconcile_and_correct` and returns `{"status": "gated"}` with no write, never touching the
writer, so for a gated op the resolved root is unused work.

Net effect: in an environment where mission-control is unresolvable — a consumer repo with no
install, or the KTD6 stale-fleet-core case #620 itself guards for — an op that would be **GATED**
(the certificate deliberately withholding the write pending operator confirmation) now aborts at
resolution with **exit 1** instead of returning `gated` (exit 0). The CLI exit-code contract flips
for the gated-op-in-unresolvable-environment case.

## Impact

Low, bounded, fail-loud — no data loss, no wrong-target write. The observable regression is
twofold: (a) exit code `0 → 1` for a gated op in an unresolvable environment, which can surprise a
caller/script that treats `gated` (exit 0) as a non-fatal, expected outcome; (b) the surfaced
error is "mission-control unresolvable" rather than the certificate-gate verdict, masking that the
op was actually gated.

Counter-argument for leaving it as-is: in an unresolvable environment every board write fails
anyway, so surfacing the missing install may be the more actionable signal than a gate verdict.
This is a deliberate-behavior call, not a crash — hence **low** priority, filed for tracking and
an explicit decision.

## Fix shape

One of:

- Evaluate the certificate gate **before** resolving the mission-control root: a `gated` verdict
  needs no writer, so resolve lazily only when the gate passes. Preserves exit 0 for gated ops in
  any environment.
- OR keep the eager resolve but map an unresolvable-root error on a *would-be-gated* op to `gated`
  (exit 0) with the resolution reason attached as advisory context.

Either way the CLI exit-code contract should treat `gated` / `halt` as exit 0 independent of
mission-control resolvability, while a *non-gated* op in an unresolvable environment keeps failing
loud (exit 1).

## Evidence

Verified live at main `03c2640c` (saga 0.114.0, fleet-core 0.23.0):

- `plugins/saga/scripts/board_progression.py:532-539` — the `write` CLI calls
  `resolve_mission_control_root()` (raises → prints error, `return 1`), *then* builds the writer,
  *then* calls `authorize_and_write`; the gate at `:191-194` returns `{"status": "gated"}` with no
  write and never uses the writer.
- `plugins/saga/scripts/reconcile_controller.py:423-430` — identical ordering: resolve (raise →
  `return 1`) → build writer → `reconcile_op`; the gate lives inside `reconcile_and_correct`
  (`:204-209`) and short-circuits before any writer use. Note `:448` already treats `gated`/`halt`
  as exit 0 — but only if control reaches it, which the eager resolve prevents.
- Pre-#620 baseline: `default_board_writer` merely *constructed* a path string (no resolution, no
  raise), so a gated op returned `gated` / exit 0 regardless of whether the (unused) path was
  valid.

### Files expected to change

- `plugins/saga/scripts/board_progression.py` — `main` (`write` CLI): gate before resolve, or map
  unresolvable-on-gated to exit 0.
- `plugins/saga/scripts/reconcile_controller.py` — `main` (`reconcile` CLI): same ordering fix.
- Release surfaces if a code path changes: `plugins/saga/.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`, `plugins/saga/CHANGELOG.md`, drift pins.

### Tests to add or update

- `tests/test_board_progression.py` — a gated op with a resolver stubbed to raise returns
  `status=gated` / exit 0; a non-gated op with the same stub still exits 1.
- `tests/test_reconcile_controller.py` — the same two cases for the `reconcile` CLI.

### Context library links

_none_

### Acceptance criteria

- [ ] A gated op (certificate refuses `op_kind`) returns `status=gated` / exit 0 even when
      `resolve_mission_control_root()` would raise (unresolvable install / stale fleet-core).
- [ ] A non-gated op in an unresolvable environment still fails loud (exit 1) with the resolution
      error — no silent skip, no wrong-target write.
- [ ] Regression tests in `tests/test_board_progression.py` and `tests/test_reconcile_controller.py`
      pin both behaviors.

### Verification

```
uv run pytest -q tests/test_board_progression.py tests/test_reconcile_controller.py
```

### Objective

Not yet assigned to an Objective — a follow-up finding from the #620 board-sync plugin-resolution
work (the eager resolve-once-per-tick design's edge on gated ops); grouping is the operator's call.

### Intent

The board-sync CLIs preserve the pre-#620 exit-code contract for gated ops: a certificate gate is
a normal, expected outcome (exit 0) regardless of whether mission-control resolves, while a genuine
write attempt in an unresolvable environment still fails loud.

### Out-of-scope / non-goals

The #620 fix itself (shipped, correct for the write path); #642 installed_plugins.json staleness
(the resolution substrate, a separate defect); changing certificate-gate semantics for healthy
environments.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: /private/tmp/claude-501/-Users-jefcox-workspace-infiquetra-infiquetra-claude-plugins/a2c17e16-6a69-4ff8-a9f6-dc347823861a/scratchpad/eager-resolve-before-gate-body.md
- Source type: local-file
- Source title: eager-resolve-before-gate-body

### Recommended Tier Band
opus/high

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/652
- Number: 652
- Created at: 2026-07-24T12:21:44.672379+00:00

