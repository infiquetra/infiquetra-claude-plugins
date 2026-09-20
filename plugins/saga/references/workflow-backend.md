# The Claude Code Workflow backend, and the team-execution emission

This file holds the instructions for the two Saga execution backends that are not `inline`:
`team-execution` and `cc-workflows-ultracode`. It was extracted from `skills/plan/SKILL.md` and
`skills/work/SKILL.md` by issue 1026, which left the entry path of every run carrying only the
contract a reader needs to decide whether to come here.

**Reaching this file is a decision, not a step.** A Claude Code Workflow is reachable only by
explicit operator invocation (DECISIONS `{#cc-workflows-backend-narrow-808}`, issue #808's NARROW
ruling). It is never a default, never pre-selected, never a silent substitute for `inline` or
`team-execution`, and never wrapped in a mechanism-neutral backend-switching abstraction. If you
arrived here from a recommendation rather than from an operator naming the backend, go back.

The Workflow protocol itself — the lease contract, the invocation identity, the release and renew
semantics — lives with its capability in
`plugins/cc-workflows/skills/cc-workflows/references/protocol.md`. What follows is the driver-side
seam: how `/plan` records the choice and authors the specification, and how `/work` re-emits, runs,
and settles it.

## Related references

- `operator-choice.md` — the decision contract the offer renders from, as narrowed by issue #808.
- `execution-spec.md` — the specification schema this section authors.
- `../skills/work/references/execution-strategy.md` — the runnable recommender call.

---

# Part one — from `/plan`

What follows was `/plan` Phase 5.2 and 5.2a. Its cross-references to "Phase 5.3", "Phase 0.7" and
"§5.3" still mean those sections of `skills/plan/SKILL.md`.

### 5.2 Offer the execution backend

**Write the answer into the plan document's `backend:` frontmatter field**, not only into the saga
tick. The tick is untracked local state: it does not survive a worktree boundary, another machine,
or another vendor, so an executor that did not run in this directory cannot see it. The plan document
travels with the work because the executor commits it alongside the changes, which makes it the
place a decision made here can reliably be read later. `/work` honours that field and does not ask
again. (If a Phase 0.7 pre-answer carrier applied `backend: inline`, skip only the operator-facing offer — still call
`lifecycle_state.recommend_execution_backend`, still record `--orchestration-recommended` with its
output and `--orchestration-mode inline`, and still write the plan document's `backend:` field;
the carrier never applies the other two backends, they remain explicit invocations. Skipping the
offer must never skip the recommend call: Phase 5.3's save examples include its output.)

The recorded enum still has three values — `inline` ("inline") | `team-execution` ("team execution") |
`cc-workflows-ultracode` ("dynamic workflows") — matching `references/operator-choice.md` and
`ORCHESTRATION_MODES`. **The default Saga offer is only `inline` and `team-execution`.** Claude Code
Workflows (`cc-workflows-ultracode`) remain only an **explicitly invoked** task-local mechanism inside
a Herdr-managed Claude Code session: never a default or automatic Saga backend, never a generic
interchangeable execution backend (DECISIONS `{#cc-workflows-backend-narrow-808}`, issue #808 NARROW
ruling). Never pre-select `cc-workflows-ultracode`. Never launch a Workflow because
`recommend_execution_backend()` returned it. Never silently substitute a Workflow for `inline` or
`team-execution`. Do not build a mechanism-neutral backend-switching abstraction around it.

Offer the default Saga backends per `references/operator-choice.md` (the decision contract, as
narrowed by #808). Read the work shape, **recommend the cheapest-correct Saga backend** (`inline` or
`team-execution`) and pre-select it. Call `lifecycle_state.recommend_execution_backend` so the tick
can record `--orchestration-recommended` (R12 telemetry). Confirm with the operator and record what
they picked via `--orchestration-mode`.

**Before an explicit Workflow invocation, probe Workflow-tool availability with `ToolSearch`** (not
an assumption) and pass the result as `--workflow-availability-source probed`; only fall back to the
`asserted` default when a live probe is not possible on this host (e.g. a non-Claude-Code runner). The
recommender echoes the source back in `workflow_availability` so the offer can say whether
availability was verified or merely assumed. An unavailable Workflow is **not** a third interchangeable
choice; name it only to explain that explicit invocation cannot run here.

**Claude Code Workflows still serve the five workflow shapes** (per `references/operator-choice.md`
§3.2) — **understand / design / research / review / migrate** — and the two legacy purposes beside
them. Those purposes describe **when an operator might explicitly invoke** a Workflow. They are **not**
automatic offer triggers and **not** a reason to pre-select `cc-workflows-ultracode`:

- **Breadth / scale** (`broad_independent_fanout`) — broad independent fan-out, the same operation
  across many enumerated targets, or an exhaustive probe-all sweep where missing a target is the
  failure mode.
- **Adversarial confidence** (`adversarial_confidence`) — a judge panel over N independent attempts,
  prove-by-refutation (refute-N), or perspective-diverse verifiers each applying a distinct lens. This
  is real review depth; the Workflow tool names *confidence* as a first-class purpose. Set it only on an
  **explicit** request for many-independent-attempt verification, not on a generic "be more sure." (The
  `review` shape covers a multi-lens review *sweep* requested as a workflow; the explicit refute-N /
  judge-panel form stays `adversarial_confidence` — the two may co-fire, no precedence between them.)

Pass any matching shape(s) via repeatable `--workflow-shape` when authoring a spec after explicit
invocation; an unrecognized shape is rejected loud (`ValueError`), never silently downgraded to inline.

**The team↔workflow fork is GOVERNANCE, not "review depth"** (both have review depth). The question is:
**does the verdict need to stick?** Escalate to `team-execution` ("team execution") when the work needs
**gated** consensus — a verdict that blocks a merge/deploy and persists as standing evidence (a reviewer-
CONSENSUS gate, named scanners, a guarded deploy), or the size/risk signals fire (≥8 functional files,
≥4 phases, security, infra, cross-repo, deployment-sensitive). When the consensus signal is **advisory**
— N throwaway in-session votes you act on yourself, nothing recorded or blocking — stay on `inline`
unless the operator **explicitly invokes** a Claude Code Workflow judge-panel. Confirm with the operator
and record what they picked via `--orchestration-mode`. Enter §5.2a only after that explicit invocation.

**KTD4 — the gated-vs-advisory interrogation (R7).** When a consensus / multi-reviewer / many-attempt
signal is present, do **not** silently force `team-execution`. Ask the operator (`AskUserQuestion`, or
channel-inline) one question, with the work-shape default pre-selected:

> **Does this verdict need to BLOCK a merge/deploy or PERSIST as evidence — or are these throwaway
> in-session votes you act on yourself?**
> **A) Gated** — block/persist (a reviewer-CONSENSUS gate, named scanners, a guarded deploy) → `team-execution`.
> **B) Advisory** — N throwaway votes, nothing recorded/blocking → `inline` (a judge-panel Workflow
> only if the operator then explicitly invokes `cc-workflows-ultracode`).

**Work-shape default:** pre-select **Gated** when any deploy / security / persist signal is present
(`--destination merge|nonprod-deploy`, security/infra work, or a verdict that must be recorded); pre-select
**Advisory** otherwise. Pass the answer into the recommender as `--advisory-consensus` (set for B; omit for
A — gated is the default). Advisory consensus no longer auto-routes onto `cc-workflows-ultracode`; the
default Saga path is `inline`, and a Workflow judge-panel is explicit-invocation only. If the work is
**both** gated **and** broadly parallel, the default offer is still `team-execution` (and `inline` as
the cheaper alternative), not a third interchangeable Workflow choice.

#### 5.2a Author the ExecutionSpec (cc-workflows-ultracode only)

**Enter this section only after explicit invocation** — the operator named `cc-workflows-ultracode` in
this session, or a prior operator decision already recorded it. Never enter it because the recommender
suggested it, never as a silent substitute for `inline` or `team-execution`.

When the operator **explicitly invokes** `cc-workflows-ultracode`, **author a structured `ExecutionSpec`
before writing the saga tick**. This is the canonical artifact `/work` re-emits from; the spec JSON —
not the prose plan — is the single source of truth (KTD1, `references/operator-choice.md` §6).

Step 1, the per-unit tier derivation, is **not** here: it applies to any backend that spawns
per-unit agents, so it stays in `skills/plan/SKILL.md` under §5.2a. Lock the tiers there
first; the steps below price them.

**Step 1b — Price the plan and set the spend guards (#366).** Once tiers are locked the plan has a
*price*: surface it and set the run-scoped guards before authoring prompts.

- Run `python3 plugins/saga/scripts/execution_spec.py spend <spec.json>` to print per-unit spend, the
  multiplicity-aware total (fan-out targets and verify panels counted, not one weight per unit), any
  `cost_budget` headroom, and the `spend_envelope`. Show the operator the priced plan.
- Set an optional `cost_budget` on the spec when the operator wants a hard ceiling — `validate`/`emit`
  HALT (never a silent over-spend, per HALT-not-degrade) if the summed spend exceeds it, mirroring
  `VERIFY_N_CAP`.
- Set an optional `spend_envelope` when the operator wants "ask once, at the crossing" rather than a
  prompt per expensive choice; `/work`'s #364 between-rounds escalation consults it before proposing a
  climb (`SpendEnvelope.consider`).
- Per-unit effort allocations are gone with the effort-escrow ledger (issue 1028). The model and
  effort each role runs at live in the run record's
  `run_configuration.staffing_models_and_efforts`, decided once at admission; a unit that needs a
  different tier is a staffing question for the operator, not an allocation to escalate.

Weights are ordinal/relative, not dollar prices — the cost-weighted spend-*delta* classifier is #367.

**Step 1c — Spend-delta levers: relative override, worth-it receipts, spend authority (#367).**

- **Relative override** — when the operator wants to adjust a proposed tier, offer the three-way
  **relative** choice `cheaper` / `as-proposed` / `dearer` (computed by `execution_spec.adjacent_tier`)
  instead of forcing an absolute re-pick from the full `MODELS × EFFORTS` enum. `cheaper`/`dearer` step
  exactly one rung; at a ladder boundary the lever raises (no silent clamp). `spend_delta(old, new)`
  classifies any change as `cheapen` / `escalate` / `lateral` — a `lateral` (sideways axis trade) or a
  `cheapen` proceeds quietly; an `escalate` is the one that asks.
- **Worth-it receipts** — a **premium** tier (opus/fable model or xhigh effort — above the `sonnet/high`
  baseline) must carry a one-line `worth_it_because` and a named `cheaper_fallback` (an adjacent
  strictly-cheaper tier, default `adjacent_tier(tier, "cheaper")`). Enforce it at authoring by validating
  with receipts required:
  `python3 plugins/saga/scripts/execution_spec.py validate <spec.json> --require-receipts`. Plain
  `validate`/`emit` do NOT require receipts, so existing specs are never retroactively broken.
- **Spend authority** — resolve each unit's silent/ask disposition via
  `spend_authority.resolve_spend_authority(tier)`: a `.saga/spend-authority.json` `silent_ceiling`
  (absent → `sonnet/high`) makes any premium tier `ask` and everything at/below `silent` — the
  configurable home for the cheap-silent/expensive-asks rule.

**Steps 2–5 — Author the spec into a runnable workflow (lives with the capability, #925/U4).**
Follow the cc-workflows authoring protocol — `plugins/cc-workflows/skills/cc-workflows/SKILL.md` —
for the thin per-unit prompts (KTD2), `depends_on` barriers and `verify` panels, `validate` (HARD
BLOCK on failure), `emit`, and concurrent-writer safety
(#671). Saga keeps this entry guard, the tier/spend authoring above, and the tick write below. The
runnable commands are unchanged — `execution_spec.py validate` / `emit` still exist and delegate
emission to the extracted emitter; artifacts land in `docs/workflows/`. The operator must
explicitly confirm the tier assignments and the control-flow structure before `/work` runs it (R8
"approved"); a rejection means revising the spec and re-running validate and emit. The
approval table `spec_table.py` used to render was removed by issue 1026 with the script; present
the tier assignments from the Step 1 table above instead.

**Spec naming convention:** `docs/workflows/<YYYY-MM-DD>-<topic>-spec.json` — the plan doc stays in
`docs/plans/`; generated Workflow artifacts live in `docs/workflows/`. The `.workflow.js`
shares the same stem: `docs/workflows/<YYYY-MM-DD>-<topic>.workflow.js`.

---

# Part two — from `/work`

The first block was the backend-offer half of `/work` §1.4; the second was `/work` §1.5 in full.
Their cross-references to "Phase 1.4", "Phase 2", "Phase 3" and "Phase 4" still mean those sections
of `skills/work/SKILL.md`.

## Offering the backend, when the plan recorded none

Offer only when the field is absent, which is every plan written before this contract existed.

Otherwise, offer the default Saga backends per `references/operator-choice.md` (as narrowed by
issue #808) and the **runnable `recommend_execution_backend()` CLI call** in
`references/execution-strategy.md`: compute the recommendation from the work shape, then pre-select
`inline` or `team-execution` only — **do not pre-select** `cc-workflows-ultracode`; pre-select
`team-execution` when a gated size/risk/consensus trigger fired, otherwise `inline`.
The default offer is those two Saga backends. `cc-workflows-ultracode` is never a default/automatic
backend and never a generic interchangeable execution backend. Enter Phase 1.5 only when the
operator **explicitly invokes** a Claude Code Workflow in this session (or the plan field already
recorded that invocation). Confirm with the operator, and record what they picked via
`--orchestration-mode`. Also pass `--orchestration-recommended <the recommend_execution_backend()
output>` so the tick records recommended-vs-chosen on this decision (R12 override-rate telemetry);
`orchestration_operator_choice` auto-derives from `--orchestration-mode`, so the only added burden is
naming the recommendation. Never silently substitute a Workflow for `inline` or `team-execution`.

### 1.5 cc-workflows-ultracode: re-emit and run, or HALT

**Enter this section only after explicit invocation** — the plan already recorded
`backend: cc-workflows-ultracode`, or the operator named it in this session. Never enter it because
`recommend_execution_backend()` recommended it, never as a silent substitute for `inline` or
`team-execution`.

When `orchestration_mode == cc-workflows-ultracode`, the recorded backend choice **and** the saved spec
are the opt-in — ultracode mode is not required to launch a Workflow. `/work` does **not** hand-roll
sequential subagents as a substitute (that was the campps issue-38 failure: parallel + refute-N silently
dropped). It either runs the real Workflow tool or halts visibly. The Workflow protocol itself — lease
contract, invocation identity, release/renew semantics — lives with its capability in the cc-workflows
plugin (`plugins/cc-workflows/skills/cc-workflows/references/protocol.md`); this section is the
driver-side seam.

**Re-emit for freshness (KD3).** Read the saga's `orchestration_ref` to locate the canonical spec JSON
the plan authored, and gate it mechanically before trusting it (#693):

```bash
python3 plugins/saga/scripts/saga.py spec-check --saga-id <saga-id>
```

Any verdict but `ok` is a HALT condition (see below) — do not proceed on a `missing`, `run-id`, or
`file-missing` ref. On `ok`, mint the logical invocation identity first, then re-emit a fresh
`.workflow.js` and its driver-owned reservation contract (the frozen #356 shape — since #677/U4 it
binds no leases) from the same spec — any intermediate re-plan that changed the spec is reflected.
`CLAUDE_CODE_SESSION_ID` is host-provided to Bash and hook subprocesses and matches the hooks'
trusted `session_id`; HALT if it is absent. Never substitute the saga id.

```bash
test -n "$CLAUDE_CODE_SESSION_ID" || { echo "HALT — CLAUDE_CODE_SESSION_ID is absent" >&2; exit 2; }
export WORKFLOW_INVOCATION_ID="${WORKFLOW_INVOCATION_ID:-$(uuidgen | tr '[:upper:]' '[:lower:]')}"
export WORKFLOW_LEASE_METADATA=".saga/workflow-lease-${WORKFLOW_INVOCATION_ID}.json"
# Resolve the cc-workflows scripts dir the same way the Python seam does: the env var
# wins, the repo-relative default is the fallback (review F12 — never hardcode the path).
CC_WORKFLOWS_SCRIPTS_DIR="${CC_WORKFLOWS_SCRIPTS_DIR:-plugins/cc-workflows/skills/cc-workflows/scripts}"
mkdir -p .saga
python3 plugins/saga/scripts/execution_spec.py emit <orchestration_ref_spec.json> \
  -o docs/workflows/<topic>.workflow.js
python3 plugins/saga/scripts/execution_spec.py lease <orchestration_ref_spec.json> \
  --invocation-id "$WORKFLOW_INVOCATION_ID" > "$WORKFLOW_LEASE_METADATA"
python3 "$CC_WORKFLOWS_SCRIPTS_DIR/workflow_emitter.py" reserve "$WORKFLOW_LEASE_METADATA" \
  --session-id "$CLAUDE_CODE_SESSION_ID" > ".saga/workflow-lease-receipt-${WORKFLOW_INVOCATION_ID}.json"
python3 "$CC_WORKFLOWS_SCRIPTS_DIR/workflow_emitter.py" attest "$WORKFLOW_LEASE_METADATA" \
  --session-id "$CLAUDE_CODE_SESSION_ID"
```

The final `attest` remains the launch gate: any refusal (malformed or not-launch-ready metadata)
means **launch none and HALT** (the lease-contract shape and its broker-free retirement semantics:
cc-workflows plugin `references/protocol.md`).

Then launch it:

Before launch, render the driver-owned expected-unit metadata and persist the manifest plus one spawn
attempt per unit in deterministic order. Generated agents still receive no filesystem or ledger-write
permission; the driving `/work` session is the only writer. Mint `WORKFLOW_INVOCATION_ID` **once** for
this logical Workflow launch, record it with the workflow handle in the saga tick, and reuse that exact
value only after a crash or explicit resume. A later launch of the same unchanged spec must mint a new
value. The following shell sequence is the complete driver-side pre-submit protocol; the `manifest`
command is exact-replay idempotent. On resume, it replays that command and appends only spawn attempts
that the ledger report proves are still absent:

```bash
export SAGA_ID=<saga-id>
export SPEC=<orchestration_ref_spec.json>
mkdir -p .saga
export SETTLEMENT_METADATA=".saga/workflow-settlement-${WORKFLOW_INVOCATION_ID}.json"
python3 plugins/saga/scripts/execution_spec.py settlement "$SPEC" \
  --invocation-id "$WORKFLOW_INVOCATION_ID" > "$SETTLEMENT_METADATA"
python3 - "$SETTLEMENT_METADATA" "$SAGA_ID" <<'PY'
import datetime
import json
import subprocess
import sys

metadata_path, saga_id = sys.argv[1:]
metadata = json.load(open(metadata_path, encoding="utf-8"))
at = datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
base = [
    "python3", "plugins/saga/scripts/dispatch_settlement.py", "--repo-root", ".",
    "--subplot-id", saga_id,
]
subprocess.run(base + [
    "manifest", "--dispatch-id", metadata["dispatch_id"], "--site", metadata["site"],
    "--units-json", json.dumps(metadata["units"]), "--at", at,
], check=True)
report = json.loads(subprocess.check_output(
    base + ["report", "--dispatch-id", metadata["dispatch_id"]], text=True
))
spawned = {
    entry["unit_id"] for entry in report["entries"]
    if entry["attempt"] == 1 and entry["spawned"]
}
for unit in metadata["units"]:
    if unit["unit_id"] in spawned:
        continue
    subprocess.run(base + [
        "spawn", "--dispatch-id", metadata["dispatch_id"], "--unit-id", unit["unit_id"],
        "--attempt", "1", "--idempotency-key", unit["idempotency_key"], "--at", at,
    ], check=True)
PY
```

```
Workflow({ scriptPath: "docs/workflows/<topic>.workflow.js" })
```

After the Workflow returns, or after the host authoritatively confirms cancellation, close the
protocol with the release command (semantics: cc-workflows plugin `references/protocol.md`).
This block runs in a **fresh shell** after the Workflow tool returns, so it re-establishes the
launch identity itself from the newest lease metadata artifact already written under `.saga/`.
Never mint a new id here, or the release targets a lease that was never reserved (review A01/U01).

```bash
WORKFLOW_LEASE_METADATA="$(
  python3 - <<'PY'
from pathlib import Path

leases = [
    path
    for path in Path(".saga").glob("workflow-lease-*.json")
    if not path.name.startswith("workflow-lease-receipt-")
]
if not leases:
    raise SystemExit("HALT — no Workflow lease metadata found under .saga")
print(max(leases, key=lambda path: (path.stat().st_mtime_ns, path.name)))
PY
)" || exit 2
WORKFLOW_INVOCATION_ID="$(
  python3 - "$WORKFLOW_LEASE_METADATA" <<'PY'
import json
import sys
from pathlib import Path

metadata_path = Path(sys.argv[1])
metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
invocation_id = metadata.get("invocation_id")
if not isinstance(invocation_id, str) or not invocation_id:
    raise SystemExit(f"HALT — {metadata_path} has no invocation_id")
print(invocation_id)
PY
)" || exit 2
WORKFLOW_LEASE_METADATA=".saga/workflow-lease-${WORKFLOW_INVOCATION_ID}.json"
CC_WORKFLOWS_SCRIPTS_DIR="${CC_WORKFLOWS_SCRIPTS_DIR:-plugins/cc-workflows/skills/cc-workflows/scripts}"
python3 "$CC_WORKFLOWS_SCRIPTS_DIR/workflow_emitter.py" release "$WORKFLOW_LEASE_METADATA" \
  --session-id "$CLAUDE_CODE_SESSION_ID"
```

For a long driver-side collection step, the boundary renew call stays for protocol continuity
(semantics: cc-workflows plugin `references/protocol.md`). Fresh shell, same rule as the release
block: re-establish the launch identity from the newest on-disk lease metadata first.

```bash
WORKFLOW_LEASE_METADATA="$(
  python3 - <<'PY'
from pathlib import Path

leases = [
    path
    for path in Path(".saga").glob("workflow-lease-*.json")
    if not path.name.startswith("workflow-lease-receipt-")
]
if not leases:
    raise SystemExit("HALT — no Workflow lease metadata found under .saga")
print(max(leases, key=lambda path: (path.stat().st_mtime_ns, path.name)))
PY
)" || exit 2
WORKFLOW_INVOCATION_ID="$(
  python3 - "$WORKFLOW_LEASE_METADATA" <<'PY'
import json
import sys
from pathlib import Path

metadata_path = Path(sys.argv[1])
metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
invocation_id = metadata.get("invocation_id")
if not isinstance(invocation_id, str) or not invocation_id:
    raise SystemExit(f"HALT — {metadata_path} has no invocation_id")
print(invocation_id)
PY
)" || exit 2
WORKFLOW_LEASE_METADATA=".saga/workflow-lease-${WORKFLOW_INVOCATION_ID}.json"
CC_WORKFLOWS_SCRIPTS_DIR="${CC_WORKFLOWS_SCRIPTS_DIR:-plugins/cc-workflows/skills/cc-workflows/scripts}"
python3 "$CC_WORKFLOWS_SCRIPTS_DIR/workflow_emitter.py" renew "$WORKFLOW_LEASE_METADATA"
```

The Workflow tool owns execution from this point. `/work` records the returned workflow id in
`orchestration_run_id` via a saga tick (#693) — never in `orchestration_ref`, which stays the durable
spec-path pointer written at `/plan` time (overloading it destroyed the spec path the next resume
needs to locate the spec):

```bash
python3 plugins/saga/scripts/saga.py save \
  --kind <issue|task> --id <...> \
  --orchestration-run-id <workflow-id>
```

**HALT conditions.** If **either** of the following holds, `/work` MUST halt — never substitute with
hand-rolled serial subagents or any other inline fallback:

1. The **Workflow tool is genuinely absent** from this session (not found in the available tools).
2. `saga.py spec-check --saga-id <saga-id>` reports any verdict but `ok` (#693). The guard
   DISCRIMINATES rather than testing presence — an `orchestration_run_id` held beside the ref never
   satisfies it:
   - `missing`: the plan did not author a spec, or the saga tick never recorded the ref.
   - `run-id`: the ref holds a workflow run handle — the pre-#693 clobber shape.
   - `file-missing`: the ref is a path, but the spec file does not exist.

On a HALT, surface the reason and one recovery line, e.g.:

- Workflow tool absent: "HALT — Workflow tool not available in this session. Recovery: resume in a
  Claude Code session where the Workflow tool is present, or ask the operator to switch the backend to
  `team-execution` or `inline`."
- `missing` / `file-missing`: "HALT — saga `orchestration_ref` is empty or the spec file does not
  exist at `<path>`. Recovery: re-run `/plan` to author the spec and record the ref, then resume
  `/work`."
- `run-id`: "HALT — saga `orchestration_ref` holds a workflow run id, not the spec path (the pre-#693
  clobber). Recovery: re-record the spec path (`saga.py save ... --orchestration-ref
  docs/workflows/<date>-<topic>-spec.json`); the run handle belongs in `--orchestration-run-id`."

This is **explicitly not** the off-host recompile-down path (`recheck_orchestration_capability` in
`lifecycle_state.py`), which is reserved for `/loop` and `/resume`. A guarantee-bearing ultracode
choice halts rather than silently losing the parallel fan-out and refute-N verification (KD2/KTD6).

**Provenance guard.** `/work` NEVER writes `operator_choice` to record its own substitution. The
`saga.py` save guard rejects a tick that newly asserts `orchestration_mode != orchestration_operator_choice`
without an `orchestration_downgrade` note justifying that divergence — exactly the issue-38 shape (an AI
swap masquerading as the operator's pick). The guard is precise, not blunt: it is a no-op when no
`operator_choice` is asserted, and it lets an *unchanged* carry-forward of a prior, already-vetted
divergence through (its note was checked when that earlier tick saved). The only legitimate path is:
the operator picks a backend, `/work` records exactly that pick via `--orchestration-mode` (so
`orchestration_operator_choice` derives equal to it — no divergence), and a genuine capability degrade is
recorded as `orchestration_downgrade` WITH the divergence (operator-choice §6).

**Post-run settlement (U4/KTD7).** A Workflow script has no filesystem access, so it cannot write its
own receipts — the *driving session* is the producer of record. After Workflow returns, collect its
structured results as a JSON object keyed by the original workflow `unit_id`, save it as
`$WORKFLOW_RESULTS`, and run this exact adapter before moving on. `metadata.driver.units` maps the
original result contract to its bounded settlement identity; do not rename result keys to make them
ledger-safe.

```bash
export WORKFLOW_RESULTS=<workflow-returned-results.json>
export EVIDENCE_DIR=".saga/workflow-evidence-${WORKFLOW_INVOCATION_ID}"
export SETTLE_DESCRIPTORS="$EVIDENCE_DIR/descriptors.jsonl"
mkdir -p "$EVIDENCE_DIR"
python3 - "$SETTLEMENT_METADATA" "$WORKFLOW_RESULTS" "$EVIDENCE_DIR" <<'PY' > "$SETTLE_DESCRIPTORS"
import json
import sys
from pathlib import Path

metadata = json.load(open(sys.argv[1], encoding="utf-8"))
results = json.load(open(sys.argv[2], encoding="utf-8"))
evidence_dir = Path(sys.argv[3])
for binding in metadata["driver"]["units"]:
    result = results.get(binding["workflow_unit_id"])
    if not isinstance(result, dict):
        print("null")  # Missing or prose-only result: settle as silent-no-op.
        continue
    evidence_path = evidence_dir / (binding["settlement_unit_id"] + ".json")
    evidence_path.write_text(json.dumps({
        "schema": "dispatch.workflow-result.v1",
        "unit_id": binding["settlement_unit_id"],
        "result": result,
    }, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "receipt_type": "workflow-result",
        "unit_id": binding["settlement_unit_id"],
        "evidence_path": str(evidence_path),
    }))
PY
python3 - "$SETTLEMENT_METADATA" "$SETTLE_DESCRIPTORS" "$SAGA_ID" <<'PY'
import datetime
import json
import subprocess
import sys

metadata = json.load(open(sys.argv[1], encoding="utf-8"))
descriptors = open(sys.argv[2], encoding="utf-8")
base = [
    "python3", "plugins/saga/scripts/dispatch_settlement.py", "--repo-root", ".",
    "--subplot-id", sys.argv[3], "settle", "--dispatch-id", metadata["dispatch_id"],
]
for unit, descriptor in zip(metadata["units"], descriptors, strict=True):
    at = datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
    subprocess.run(base + [
        "--unit-id", unit["unit_id"], "--attempt", "1", "--evidence-json", descriptor.strip(),
        "--at", at,
    ], check=True)
PY
export DISPATCH_ID="$(python3 - "$SETTLEMENT_METADATA" <<'PY'
import json
import sys
print(json.load(open(sys.argv[1], encoding="utf-8"))["dispatch_id"])
PY
)"
python3 plugins/saga/scripts/dispatch_settlement.py --repo-root . report --dispatch-id "$DISPATCH_ID"
python3 plugins/saga/scripts/dispatch_settlement.py --repo-root . dlq --dispatch-id "$DISPATCH_ID"
```

The only accepted delivery receipt is the exact evidence file schema above plus its descriptor. Never
pass agent prose or a self-report as evidence: it settles as `silent-no-op`, not success.
A missing structured result is `silent-no-op`: the driver emits `null` and records the casualty. HALT on a
settlement error or a report with `halt_required=true`. The `dlq` read is the retry derivation; at the next Workflow
boundary claim each operator-approved entry with `claim-retry --dispatch-id <id> --unit-id <id> --at
<iso-time>`, append its returned attempt's spawn before submission, and retain its metadata
`idempotency_key`. This is at-least-once and preserves the stable idempotency key; it is never
exactly-once delivery.
