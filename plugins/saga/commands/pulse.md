---
name: pulse
description: Live fleet telemetry — board/run/ledger/outcome state from real signals, read-only
argument-hint: "[--project NAME] [--saga SAGA_ID] [--json] [--watch]"
---

Load `saga/skills/pulse/SKILL.md` and render one live fleet-telemetry snapshot.

Run `python3 plugins/saga/scripts/pulse.py` with the operator's arguments. The four panels —
board (mission-control's own JSON read path), runs (saga tick history, derive-on-read), the
hash-chained run-fact ledger (its own reducers), and outcome economics (`outcome_costs.rollup`)
— render from real signals only. Every panel is tri-state `ok` / `no-data` / `unavailable`
(ledger adds `chain-broken`): an empty or unreadable source is labeled explicitly, never shown
as a silent zero, and a broken chain suppresses all aggregates.

`/pulse` is a continuous read-only view: it writes nothing (no tick, no fact, no cache), sets
no thresholds, gates nothing, and contains no experiment loop — the bounded
target/baseline/budget loop is `/optimize`'s job, and there is no programmatic feed between
them.

Treat `$ARGUMENTS` as pulse.py CLI arguments (e.g. `--project operations --saga issue-400`).

`$ARGUMENTS`
