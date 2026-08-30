---
name: cc-workflows
description: |
  Claude Code Workflow execution capability, extracted from Saga (#925): the
  workflow-script emitter, the driver-owned lease/settlement contracts, and the
  Workflow protocol. Enter only by explicit invocation (issue #808 NARROW) — never
  a default backend. The boundary is the typed execution spec: this plugin reads
  Saga's spec shape, and Saga's /plan and /work keep the integration contract.
---

# cc-workflows

Reusable **Claude Code Workflow** capability — extracted from Saga (#925, U4). Owns the
workflow-script emitter, the driver-owned lease/settlement contract CLI, and the Workflow
protocol prose. The boundary is the **typed execution spec**: this plugin still reads Saga's
spec shape (`plugins/saga/scripts/execution_spec.py`), and Saga's `/plan` / `/work` keep the
small integration contract that recognises the backend, records the operator's explicit
selection, validates availability, invokes this emitter, and consumes its structured result.

## Explicit invocation only (issue #808 NARROW, #840 C5)

`cc-workflows-ultracode` is never a default or automatic backend and never a generic
interchangeable execution backend. **Do not pre-select** it — the recommender never returns
it; the default offer is `inline` or `team-execution` only. A Workflow is entered only by
**explicit invocation**: the plan already recorded `backend: cc-workflows-ultracode`, or the
operator names it in the session. No silent substitute — if the Workflow tool is unavailable
at launch, HALT with a recovery line pointing at `team-execution` or `inline`.

## What lives here

- `skills/cc-workflows/scripts/emitter.py` — the workflow-script emission path:
  `emit_workflow_script` (spec → runnable `.workflow.js`), the driver-owned
  `workflow_settlement_metadata` / `workflow_lease_metadata` builders, and the #708
  agent-opts guards. Loads Saga's `execution_spec` for the schema (never a copy).
- `skills/cc-workflows/scripts/workflow_emitter.py` — the frozen
  `workflow_lease_reservation.v1` contract CLI (`reserve` / `attest` / `release` / `renew`).
- `skills/cc-workflows/references/protocol.md` — the Workflow run protocol: invocation
  identity, lease-contract retirement semantics, release/renew.

## Authoring protocol (spec → script)

The plan's tier/spend authoring stays in `/plan` (Saga). Once the spec exists, author it into
a runnable workflow in four steps.

**Step 2 — Author thin per-unit prompts (KTD2).** Each unit's prompt is a **thin pointer**, not a prose
transcription of the plan:

```
<unit-id>: <one-line goal>. Read the plan at <repo-relative plan path> as your authoritative spec.
```

The emitter appends fan-out reconciliation, budget riders, and return contracts automatically — do not
duplicate them in the prompt. Depth comes from the agent reading the plan; the prompt is control flow.

**Step 3 — Wire depends_on barriers and optional verify panels.** Set `depends_on` from the plan's
dependency order. For units with an **explicit** adversarial-confidence request, add a `verify` panel:
default `n=3`, `pass_rule=majority` (KTD3 — a finding survives unless ≥⌈3/2⌉=2 of 3 verifiers refute
it). Override N per-unit when the operator requests a different panel size; N is capped at 7
(VERIFY_N_CAP) — above the cap, `validate` will hard-block.

**Step 4 — Validate the spec (HARD BLOCK on failure).** Run the validator:

```bash
python3 plugins/saga/scripts/execution_spec.py validate docs/workflows/<name>-spec.json
```

A non-zero exit means the spec is malformed. **Do NOT proceed to emit or persist an invalid spec** — fix
the `SpecError` and re-validate. Common failures: `depends_on` cycle, fan-out unit with no `targets`,
pilot tier mismatch (R3), N above VERIFY_N_CAP.

**Step 5 — Emit the workflow script and surface for operator confirmation.** Once `validate` exits 0:

```bash
python3 plugins/saga/scripts/execution_spec.py emit docs/workflows/<name>-spec.json \
  -o docs/workflows/<name>.workflow.js
```

(`execution_spec.py emit` is Saga's typed integration contract: it delegates emission to this
plugin's `emitter.py`.)

**Then render the approval table — this is the artifact the operator approves, not the JSON:**

```bash
python3 plugins/saga/scripts/spec_table.py docs/workflows/<name>-spec.json --backend <backend>
```

Paste that table into your reply verbatim. It reports every unit's tier, the dependency waves
(what actually runs in parallel), spend against budget, and — the decision-relevant part — **what
the chosen backend can and cannot enforce**. A spec declaring a restrictive sandbox axis the
backend cannot enforce will HALT at emit rather than silently downgrade, and the table says so
*before* the operator approves rather than after the run fails.

Do **not** hand-build this table, and do **not** dump the spec JSON instead. Never ask an operator
to approve a backend without showing its enforceability rows: `cc-workflows-ultracode` enforces
read-only and disposable-worktree and reaches every model; `team-execution` enforces neither axis
and cannot reach `fable`. That asymmetry is invisible in the spec itself.

**Split the work so concurrent units never share a file (#671).** The table's
*Concurrent-writer safety* section reports any two units that would run in the same wave while
declaring the same path, and `emit` HALTs on one — no backend can enforce its way out of a
collision, because concurrent agents share one working tree and Claude Code has no cross-agent file
lock. Get this right while authoring the units, not at emit:

- Different repositories, or disjoint files → safe to run in parallel.
- Same file → **one unit**, not two. Merging beats sequencing: a single agent making both edits
  keeps the file's context warm and reuses the prompt cache, where splitting pays to load the same
  file into two agents and then risks losing one of their writes.
- Only reach for `depends_on` when the two really are separate pieces of work that happen to touch
  a shared path.

Bias toward fewer, longer-lived units generally. Parallel width is not free — it costs cache
reuse, and the fleet's own history is 88 of 92 waves running a single unit.

The operator must explicitly confirm the tier assignments and the control-flow structure before
`/work` runs it (R8 "approved"). A rejection means revising the spec and re-running validate +
emit + table.

## Run protocol

`/work` Phase 1.5 stays the driver-side seam (spec-check gate, re-emit, launch, settlement,
HALT conditions). The lease-contract shape, invocation identity, and release/renew semantics
live in [`references/protocol.md`](references/protocol.md).
