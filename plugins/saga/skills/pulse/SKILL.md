---
name: pulse
description: Live fleet telemetry — board state, agent/run state, run-fact ledger facts, and outcome economics rendered from real signals in one read-only surface. Strictly derive-on-read (no committed status field, no writes anywhere); every panel is tri-state ok / no-data / unavailable so an empty or unreadable source is labeled explicitly, never presented as a silent zero. Cites numbers and lets the operator judge — no hardcoded thresholds, not a gate, no experiment loop (that is /optimize). Triggers on "what is the fleet doing", "live telemetry", "pulse", "show run state and spend", "/pulse".
argument-hint: "[--project NAME] [--saga SAGA_ID] [--json] [--watch]"
---

# Pulse

`/pulse` answers "what is the fleet actually doing right now?" from **real signals only** —
never a stub, never a fixture, never a fabricated number (#400). It is a continuous read-only
view, refreshed on invoke.

## Run it

```bash
# One snapshot: runs + ledger + outcome economics (board skipped without a --project)
python3 plugins/saga/scripts/pulse.py

# Include live board columns (repeat --project for more boards)
python3 plugins/saga/scripts/pulse.py --project operations

# Focus one saga's whole tick trajectory
python3 plugins/saga/scripts/pulse.py --saga issue-400

# Machine shape (pulse_snapshot.v1)
python3 plugins/saga/scripts/pulse.py --json

# Bounded refresh loop (NOT a daemon — iterations required)
python3 plugins/saga/scripts/pulse.py --project operations --watch --interval 15 --iterations 20
```

## The four panels and their real sources

| Panel | Source | Read path |
|---|---|---|
| Board | live GitHub projectV2 columns | mission-control's own `sdlc_manager.py --format json board view` (subprocess; Pulse never re-implements the GraphQL read). Override the script location with `--sdlc-manager PATH` if the repo-relative default does not resolve (installed-plugin layouts). |
| Runs | saga tick history (derive-on-read) | `saga.py scan()` for the fleet, `read_ticks()` for `--saga` focus. Pulse renders exactly the fields the scanner derives — no pulse-owned status field exists anywhere. |
| Ledger | the hash-chained run-fact ledger (#401) | `run_ledger.py read_snapshot` + its own reducers (`rollup`, `reuse_ratio`). The chain verdict is always shown; a broken chain **suppresses every aggregate** (the numbers are no longer trustworthy). |
| Outcome economics | leaf-produced cost records | `outcome_costs.rollup` over the newest `docs/outcomes/*/outcome-spec.json`. |

## Honesty contract (tri-state per panel)

- `ok` — the source was read; the cited numbers come from it directly.
- `no-data` — the source is readable but empty ("no data yet"). Never rendered as zeros.
- `unavailable` — the source could not be read; the reason is shown. Never rendered as an
  empty board or an empty ledger.
- `chain-broken` (ledger only) — tamper/corruption detected; the banner names the first broken
  record and all aggregates are suppressed.

Pulse cites numbers and lets the operator judge — it introduces **no thresholds, no
color-as-judgment, no verdicts**. `--max-sagas` is a display cap only ("showing N of M"), not
a data threshold.

## Boundary vs `/optimize` (settled)

`/pulse` is the continuous "what is happening live?" read; `/optimize` is the bounded
experiment loop (target / baseline / budget / stop) that runs and stops. Pulse stands
**beside** `/optimize` — there is no programmatic feed between them and Pulse is **not a
gate**. An operator may read a Pulse snapshot when choosing an `/optimize` target; that
data-flow is human, by design.

## Verifying it against a real run

See [references/manual-verification.md](references/manual-verification.md) for the
drive-a-run recipe (start a disposable saga, watch the surface change tick by tick). The
automated equivalent is `uv run pytest tests/test_pulse_telemetry.py -k drives_real_run`.
