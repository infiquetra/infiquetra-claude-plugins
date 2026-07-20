# Cross-runtime Outcome acceptance evidence (#605)

`cross-runtime-acceptance.json` is the evidence bundle produced by
`tools/run_cross_runtime_outcome_acceptance.py` — the revision-pinned harness that drives the
two installed Saga runtimes (Claude `infiquetra-claude-plugins`, Codex
`infiquetra-codex-plugins`) as subprocesses against temporary fixture clones and proves the
cross-runtime coordination contract of the `lease-safe-runtime-continuity` outcome
(plan: `docs/plans/2026-07-15-cross-runtime-outcome-acceptance-plan.md`, R1–R10).
The bundle validates against `cross-runtime-acceptance.schema.json` (closed schema,
`additionalProperties: false` throughout).

## How to read the bundle

- `runtimes.*` — the exact pinned checkout SHA, the expected plugin versions, and the
  **installed-package readback identity** (KTD1: verdicts bind to what was staged and
  imported, not to working-tree claims).
- `contract_digests` — byte-identity of the two `outcome_compat.py` copies after normalizing
  the single allowed divergence (`RUNTIME_LABEL`), plus the codex target-inventory digest.
- `environment_names_set` — which allowlisted environment-variable NAMES were set for child
  processes. Never values, never names outside the closed list (R10).
- `scenarios[]` — one entry per acceptance scenario, keyed to a plan requirement (`R3`–`R9`).
  `facts` are bounded and path-redacted; refusal receipts appear as code strings only.
- `overall_verdict` — `pass` only when every scenario passes; `halt` when the run stopped
  before completing (the `halt` object carries the code).

## Scenario map

| Scenario | Requirement | Proves |
| --- | --- | --- |
| `discovery-*-created` | R3 | Canonical discovery + byte-identical projections across runtimes AND clones; independent clone B state-free and mutation-denied |
| `handoff-*-issued` | R4 | Protected bounded handoff accepted cross-runtime; successor lease + offer/intent/commit records; advance moves the leaf |
| `handoff-negatives-*` | R4 | 14 adversarial acceptances each direction, all refused with the exact receipt code and zero mutable effect |
| `race-claude-first` | R5 | Claude settles the legacy chain; Codex observes shared settlement and invents no native ack |
| `race-codex-first` | R6 | Full codex-native chain (v2 intent + protected `ack_kind=launched`), then Claude must observe it |
| `race-simultaneous` | R5 | Barrier-released two-OS-process race with overlap receipts; exactly one settled chain, no dangling unit |
| `race-crash-*-effect` | R5 | Write-once fake backend across crash windows: at most one effect, recovery settles exactly once |
| `teardown-reclaim` | R9 | Reclamation passes are idempotent no-ops once settled |
| `fleet-doctor-positions` | R9 | #353 fleet doctor reads zero open positions on a settled rig AND flags a planted dispatched-unsettled leaf |
| `legacy-import-refused` | R8 | Both installed runtimes refuse `outcome-bundle/1` import with zero writes |

## Current verdict: `fail` — two scenarios document a real production defect

At the pinned runtimes (Claude `794b4da6` / saga 0.105.0, Codex `f3e1af75` / saga
0.78.0+codex.20260720120109), `race-codex-first` and `race-simultaneous` FAIL because the
Claude runtime carries no `outcome.dispatch.v2` vocabulary in its local advance dedup or its
handoff already-settled guard: a codex-native intent (and even a fully receipt-validated
launched acknowledgement) does not block Claude from re-dispatching the same leaf — a
cross-runtime double dispatch (R5 violation). The codex-native chain itself is proven working
by the same scenarios.

This is recorded as production truth per the plan's failure rule ("Failures retain artifacts
and file/reopen the owning defect without production edits"): the owning defect is
**infiquetra/infiquetra-claude-plugins#628**. The bundle stays red until that fix ships, the
Claude pin advances, and the harness is re-run with the new pin.

## Consciously bounded coverage

- **Lease expiry/successor ordering (R5 sketch)** is not driven as a live scenario: broker
  TTL expiry is not deterministically inducible through the installed CLI without clock
  injection into the lease authority. The expiry contract is covered by both repos' dispatcher
  unit suites; the crash-window scenarios here cover the recovery semantics.
- **R7 compatibility-refusal breadth**: wrong repository/revision/operation/subplot, foreign
  authority, tamper, freshness, and clone-B denial are driven live (U2/U3); malformed-envelope
  and protocol-skew shapes are pinned by the hermetic suites
  (`tests/test_cross_runtime_acceptance.py` and both repos' contract suites).
- `fleet_doctor` runs from the installed Claude package only — the doctor is a Claude-side
  #353 deliverable with no codex port.

## Re-running

```bash
uv run python tools/run_cross_runtime_outcome_acceptance.py \
  --claude-repo <clean-claude-checkout> --claude-sha <pin> \
  --claude-saga-version <ver> --claude-fleet-core-version <ver> \
  --codex-repo <clean-codex-checkout> --codex-sha <pin> \
  --codex-saga-version <ver> --codex-fleet-core-version <ver> \
  --units all \
  --output docs/validation/lease-safe-runtime-continuity/cross-runtime-acceptance.json
```

Repo paths must be absolute, clean, and at exactly the pinned SHAs (R1 refuses otherwise).
Exit codes: 0 all-pass, 1 scenario failure(s), 2 halt. Failed or halted runs retain the
temporary work directory for inspection.
