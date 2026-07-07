# Zero-token fire drill — irreducibility map (#468)

One real lifecycle loop — spec-framing → plan → implement → review → PR-prep — on a real unit of
work (the `/code-review` programmatic-mode append contradiction, QUEUED
`{#code-review-saga-scan-touchups}` Defect 2), with every step dispatched through BOTH $0 lanes.
Claude verified every output (never-gatekeeper, R6); no engine output satisfied any gate.

- **Plan:** `docs/plans/2026-07-07-zero-token-fire-drill-plan.md` · **Saga:** `issue-468`
- **Lanes:** `agy/gemini-3.5-flash-high` (cost_speed_rank 1) · `ollama-cloud/gpt-oss-120b`
  (rank 5, first-ever live dispatch on the newly wired `OLLAMA_API_KEY`)
- **Machinery frozen (R5):** `engine-registry.yaml`, `engine_resolver.py`, `engine_dispatch.py`,
  `external-engine-workers.md` — zero changes; defects found are dispositions + follow-ups.

## Method

Each dispatch followed the plan's recipe (`external-engine-workers.md` §2–§5): resolve with
`{"role_kind": "worker", "engine": <lane>}` in `mode="dispatch"` → `engine_dispatch.dispatch()`
with `session_id` (arms the #384 delegation tripwire) → Claude verification → manifest row under
saga `issue-468` (`manifest_store.py --saga-id issue-468 list`). Receipts are the manifest rows;
tripwire audit records corroborate where the machinery supports it (see OBS-1).

**Verdict rubric (KTD3), per step × lane:**

| Verdict | Meaning |
|---|---|
| `offloaded-clean` | accepted after Claude verification with only trivial edits (rework < ~10%) |
| `degraded` | usable only after substantive Claude rework or a retry (rework ≥ ~10%, or 2nd dispatch) |
| `claude-irreducible` | output unusable, or the lane structurally cannot perform the step |

Step-level verdict = the best lane's verdict. Rework fraction = edited-lines / total-lines of the
accepted artifact.

## Pre-dispatch machinery observations

**OBS-1 — two-signal corroboration is receipt- and bundle-gated; only the agy lane can carry it.**
`delegation_audit.ENGINE_CONFIGS` has rows for `agy` and `codex` only — `corroborate("ollama-cloud", …)`
raises `UnknownEngineError`, which `_observer_corroborates` conservatively maps to observer-NO.
Because `dispatch()` treats `workspace_root is not None` as opting into two-signal reconciliation,
passing `workspace_root` on the ollama-cloud lane converts every honest `ok` into an advisory
`DELEGATION_INTEGRITY` divergence **that discards the engine's output** (`evidence=""`,
`engine_dispatch.py:292-305`). Driver posture therefore differs by lane — a deviation from the
plan recipe's blanket "session_id + workspace_root REQUIRED", recorded here per KTD8:

| Lane | `session_id` (arm) | `workspace_root` (observer) | Corroboration ceiling |
|---|---|---|---|
| agy | yes | yes | full two-signal (bundle `agy_launched` + embedded receipt) |
| ollama-cloud | yes | **omitted** | single-signal; receipt still schema-valid (`http-bridge` emits `bridge_receipt.v1`) |

Follow-up candidate (out of scope, R5): an `ollama-cloud` row in `ENGINE_CONFIGS` — or receipt-only
corroboration for bundle-less HTTP engines — so the HTTP lane can opt into two-signal without
losing output.

## Dispositions

<!-- One per step × lane, filled as the drill runs. -->

### S1 — spec-framing

| Lane | Status | Disposition (manifest) | Verdict | Rework | Evidence |
|---|---|---|---|---|---|
| agy | _pending_ | | | | |
| ollama-cloud | _pending_ | | | | |

### S2 — plan authoring

| Lane | Status | Disposition (manifest) | Verdict | Rework | Evidence |
|---|---|---|---|---|---|
| agy | _pending_ | | | | |
| ollama-cloud | _pending_ | | | | |

### S3 — implementation

| Lane | Status | Disposition (manifest) | Verdict | Rework | Evidence |
|---|---|---|---|---|---|
| agy | _pending_ | | | | |
| ollama-cloud | _pending_ | | | | |

### S4 — review

| Lane | Status | Disposition (manifest) | Verdict | Rework | Evidence |
|---|---|---|---|---|---|
| agy | _pending_ | | | | |
| ollama-cloud | _pending_ | | | | |

### S5 — PR-preparation

| Lane | Status | Disposition (manifest) | Verdict | Rework | Evidence |
|---|---|---|---|---|---|
| agy | _pending_ | | | | |
| ollama-cloud | _pending_ | | | | |

## Step verdicts + recommendations

_Filled at U6: per-step verdict, and for every `claude-irreducible` step a recommendation and a
revisit-when condition (AC3)._

## Tripwire machinery observations (#384, first real exercise)

_Filled as observed: arming behavior, stop-audit records, corroboration outcomes._
