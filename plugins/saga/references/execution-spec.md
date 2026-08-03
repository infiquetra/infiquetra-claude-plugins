# Execution-spec — one spec, two emitters (R9)

`/plan` authors **one** structured execution-spec and emits from it **either** a runnable
Claude Code workflow script **or** the team-execution markdown protocol. Saga stores only an
`orchestration_ref` pointer to the emitted artifact; it never vendors backend machinery
(R9, KTD6). The governance choice (does the verdict need to stick? — see
[`operator-choice.md`](./operator-choice.md) §3.1) selects *which emitter runs*, not the
authoring.

The spec schema and the workflow-script emitter live in
[`../scripts/execution_spec.py`](../scripts/execution_spec.py). The second emitter (the
`## Team Structure` markdown) is U11's `team_emitter.py`, fed by the same spec.

The worked reference — a hand-authored harness of exactly this shape — is the campaign's own
sibling `docs/plans/2026-06-21-saga-tiering-and-execution-campaign.workflow.js`. Authoring it
by hand validated the spec by walking it (KTD1) before this emitter automated it.

## Spec shape

```jsonc
{
  "name": "my-campaign",
  "description": "one-line workflow purpose",
  "repo": "/abs/path/to/repo",        // optional; emitted as the REPO constant
  "concurrency": {                    // optional; absent preserves legacy serialization
    "max_concurrent": 3,
    "readonly_max_concurrent": 4,
    "aggregate_max_concurrent": 7
  },
  "units": [
    {
      "unit_id": "U1",
      "label": "preflight",
      "tier": { "model": "haiku", "effort": "low" },   // per-unit {model, effort} (R2b)
      "prompt": "verify grounding facts ...",
      "returns": ["ready", "drift"],   // the structured-return contract (required keys)
      "depends_on": [],                // barrier: unit_ids that must finish first
      "escalation": "HALT on drift",   // operator note surfaced on a resumable HALT
      "fanout": false,                 // same op over many enumerated targets?
      "targets": [],                   // REQUIRED & non-empty when fanout=true (R10)
      "pilot": "",                     // a unit_id that gates the fan-out (same tier, R3)
      "verify": { "n": 3, "pass_rule": "majority" }
                                       // optional refute-N panel (KTD5); absent = no panel
    }
  ]
}
```

### Concurrency policy (optional)

`concurrency` is a closed block of positive integers satisfying
`max_concurrent <= readonly_max_concurrent <= aggregate_max_concurrent`. When omitted, emission
uses the defaults shown above but round-trip serialization leaves the block absent. Every executable
fan-out routes through the same stable chunking governor.

Resolution is deterministic: spec default, `SAGA_MAX_CONCURRENT`, an all-explicit-read-only cohort
lift, cost-weighted tier admission, a selected external-engine lane's optional `max_concurrent`, then
the explicit emit-time `--max-concurrent` override. Before aggregate preflight, the emitter copies
the environment once and builds one immutable routing context used by worker waves, ordinary and
iterate-to-consensus verifier panels, thunk panels, and unattended retry panels. Exact-engine
selectors use their registry row directly. Capability selectors resolve once to an exact registry
row; the authored capability remains inert provenance in that frozen context, while runtime dispatch
emits only the selected exact `engine` and never re-resolves or emits a capability selector. Tier
admission can narrow but never widen the selected non-tier ceiling. A lane cap applies only to units
resolved to that lane; ordinary units in a mixed layer keep their own resolved limit. The run
override is the final operator instruction. Invalid values and values above the aggregate ceiling
fail emission instead of being clamped.

Dependency layers and verifier panels preserve declaration order while emitting bounded sequential
chunks. Before rendering, the emitter checks each layer's conservative aggregate product: largest
worker chunk width times largest co-running verifier chunk width. A product above
`aggregate_max_concurrent` halts with the layer, both factors, product, and ceiling named.

Workflow source generation is fail closed. `unit_id` must match
`[A-Za-z_][A-Za-z0-9_.-]*`, must not map to a JavaScript keyword, harness binding, or supported
JavaScript/Workflow runtime global, and must not collide with another unit's generated result,
verifier, or chunk symbols. Runtime globals are reserved independently of whether the current
harness happens to reference them, so a later bare, shorthand, or member call cannot create a new
shadowing path. Iterate-to-consensus units additionally cannot claim loop-local or reconciliation
names. Free-form values emitted in JavaScript line comments have line terminators and
template-expression syntax escaped; values in executable expressions use JSON string encoding.

### Unit.verify — refute-N judge-panel (optional, KTD5)

A unit may carry an optional `verify` block that attaches a **refute-N judge-panel** over that unit's
output. When present, the emitter appends one or more bounded, sequential `parallel([...])` chunks
containing the `n` verifier `agent()` calls (each at the **same `{model, effort}` tier** as the parent
unit when `verify.tier` is absent, or at the explicitly authored `verify.tier`), concatenates chunk
results in verifier order, and then emits pass-rule reconciliation. Concurrency admission uses that
effective verifier tier while preserving the subject unit's sandbox and resolved engine-lane
context:

| Field | Type | Meaning |
|---|---|---|
| `n` | integer ≥ 1 | Number of independent adversarial verifiers dispatched. Hard cap: `VERIFY_N_CAP = 7` (above the cap, `validate` hard-blocks — guards the rate-limit overcorrection). Soft warn band: `n > 5` validates but emits a stderr warning. |
| `pass_rule` | `"majority"` \| `"unanimous"` | A finding **survives** unless refuted per this rule, recomputed over the verifiers that actually reported — see "Missing verdicts" below. Only a verifier's **gating** bucket (`refuted_deliverable`) counts toward this arithmetic; its non-gating bucket (`advisory_corrections`) never does (#686). |
| `iterate_to_consensus` | boolean, default `false` | When `true`, a refuted result retries (re-runs the unit, re-panels) up to `max_iterations` instead of failing on the first refutation. |
| `max_iterations` | integer | Retry ceiling for `iterate_to_consensus`; the final iteration throws instead of retrying. |

**Defaults for `/plan` authoring (KTD3):** `n=3`, `pass_rule="majority"` — a finding survives unless ≥2 of
3 verifiers put it in the gating bucket. Override per unit when the operator requests a different panel size. N=3/majority is
the conservative default: enough independent skeptics to surface noise without hitting the rate-limit
overcorrection that prompted the cap.

**Two-bucket verdict contract (#686).** Every verifier's structured verdict carries two required,
distinct arrays instead of one legacy `refuted` array:

- **`refuted_deliverable` — gating.** A finding belongs here only when the unit's actual work — its
  code, its tests, its `checks_run` results — is wrong, or when the verifier cannot see enough
  evidence to judge (a visibility gap is itself gating). Only this bucket feeds the pass-rule
  arithmetic above.
- **`advisory_corrections` — non-gating.** A finding belongs here when the work is right but the
  unit's self-description (its `notes`, its prose) is wrong. Sound code with wrong prose puts
  nothing in `refuted_deliverable`, no matter how wrong the prose is.

A verdict that omits either bucket is a runtime failure and counts toward the missing-verifier
floor (`quorum floor`, unchanged — see "Missing verdicts" below); there is no tolerant reader that
maps a legacy `refuted` key onto either bucket.

**Consumption.** A gating-refuted panel is never silently logged: the emitted script `throw`s
`verifier-disagreement: …` so a gating-refuted unit result halts the workflow rather than being
relied on — a one-shot panel (`iterate_to_consensus: false`) throws immediately; an
iterate-to-consensus panel retries up to `max_iterations` then throws on the final attempt.
Non-gating corrections never throw; they are `log()`-ged during the run and also collected into the
emitted workflow's final return value (see "Workflow return shape" below), so the driving session
sees them without the unit being killed.

Absent `verify` round-trips unchanged — existing specs and the `team_emitter.py` never gain a spurious key.

### Workflow return shape (#686, KTD4)

Every emitted harness ends with `return { units, advisory_corrections }` instead of returning
`undefined`. `units` is the existing per-unit result map; `advisory_corrections` is the flat list of
every non-gating correction logged across the run (empty when no unit carries a `verify` panel, or
when every panel upheld its unit cleanly). Because emitted harnesses returned `undefined` before this
change, the new return value is additive for any consumer that does not destructure it.

### Runtime ladder climbing (#364): `escalate_on_signal` + `pull_cord`

A unit may set `"escalate_on_signal": true` (requires a verify panel — the refute is the signal).
The signal is a **gating** refutation only (#686, R8): an advisory-only panel — every finding in
`advisory_corrections`, nothing in `refuted_deliverable` — upholds the unit and never burns a tier
escalation. On a gating-refuted panel the emitted script reacts by **exactly one rung** of `escalate_tier()`
(effort-first, then model; never unrunnable; `None` at the top / session ceiling):

- **Attended emission (default):** the refute `throw` carries an
  `escalation-proposal: re-run <unit> at <old> -> <new> (+1 <axis> rung)` tail — the ask gate is
  the `/work` operator loop, which confirms via the #365 `/tier` patch and re-emits. Never a
  silent in-script climb.
- **Unattended emission (`emit --unattended`):** ONE in-script retry of the unit's `agent()` call
  at the climbed tier, a fresh panel at that tier (R4), then a HALT throw if still refuted — never
  a second climb in the same run. At the top of the ladder (or blocked by the session ceiling) the
  throw names the HALT instead of retrying.

Attendance is a **run property, not spec state** — `--unattended` never enters the spec JSON.
Absent/false `escalate_on_signal` emits no key (byte-identical round-trip). v1 composition
exclusions (fail `validate`): `iterate_to_consensus` and fan-out units — both would compound the
one-rung climb into unbounded spend.

`pull_cord` is the worker-initiated depth disposition: a **cheap-tier** unit with a return contract
carries a rider permitting `{"pull_cord": "<one-line reason>"}` instead of the contract when the
worker judges itself out of depth. The gate recognizes the cord (distinct from success and from the
missing/malformed throws), the unit is never marked complete, and every cord batches into **one**
end-of-run coordinator escalation entry carrying its one-rung proposal — never one ask per cord.

### Run-scoped spend budgets (#366): `cost_budget`, `spend_envelope`, effort escrow

The tier lever is *ordered* but not *priced*; `#366` gives it magnitude. `to_spend(model, effort)`
(`fleet_commons/cost_weights.py`, a 16-cell ordinal table validated against the palette ordering at
import) prices one agent call. Two optional `ExecutionSpec` fields turn that into a run budget, both
absent-by-default (byte-identical round-trip):

- **`cost_budget`** — a hard ceiling. `validate()`/`emit` HALT with a `SpecError` naming total vs
  ceiling when the summed spend exceeds it (mirrors `VERIFY_N_CAP`; a soft warn band fires near the
  ceiling). The sum is **multiplicity-aware** (`spec_spend()` / `unit_spend()`): a fan-out unit counts
  `to_spend(tier) × len(targets)` and a verify panel adds `n × to_spend(tier) × iterations`, so the
  HALT cannot false-negative on the expensive fan-out/panel plans (HALT-not-degrade). A `pilot` is a
  separate declared unit, counted on its own row, never re-added.
- **`spend_envelope`** — the "ask once, at the crossing" threshold. The pure `SpendEnvelope` accumulator
  folds a sequence of spend-increasing choices; `consider(delta)` returns `True` only on the choice that
  crosses the envelope. It is a CLI-set field + primitive surfaced to the operator, **not** an
  autonomous runtime gate.

`execution_spec.py spend <spec.json>` reports per-unit spend, total, `cost_budget` headroom, and the
`spend_envelope` — the surface `/plan` §5.2a invokes before locking a plan. The effort-escrow ledger
(`effort_ledger.py` + `effort-policy.yaml`) records per-unit actual-vs-planned spend, refunds unused
allocation to a run pool, and surfaces an escalation-request before a unit executes; `/work` drives it
via the `allocate`/`record`/`escalate`/`report` CLI verbs. The cost-weighted spend-*delta* classifier
is the separate #367.

### Spend-delta machinery (#367): direction classifier, relative lever, worth-it receipts, spend authority

Where #366 priced *magnitude* ("how much?"), #367 classifies *direction* ("which way?"). `spend_delta(old,
new)` returns `cheapen` / `escalate` / `lateral` — built on per-axis ordering (a shared `_axis_deltas`
helper over the palette `stronger` op, never raw `.index()`), so a sideways axis trade (stronger model,
weaker effort) is `lateral`. It is NOT built on `to_spend`: the cost table is injective, so a magnitude
reading could never yield `lateral`. `is_escalation` shares the helper but keeps its exact two-way
semantics (up on either axis) — deliberately distinct from `spend_delta == "escalate"` on mixed moves.

`adjacent_tier(tier, "cheaper"|"dearer")` is the relative one-notch lever: `cheaper` reuses
`tier_resolver.cheaper_fallback` (#362), `dearer` is the symmetric one-rung-up, and a boundary call raises
rather than clamping. Two optional `Unit` fields — `worth_it_because` and `cheaper_fallback` — back the
**premium-tier worth-it hard-block**: `validate(require_receipts=True)` fails a premium tier (opus/fable
model or xhigh effort, above the `sonnet/high` baseline) missing a justification or a strictly-cheaper
named fallback. The check is `require_receipts`-gated (the `/plan` authoring boundary via
`execution_spec.py validate --require-receipts`), never on the unconditional `validate()` emit runs, so
existing specs are never retroactively broken; engine-owned units are exempt. `spend_authority.py` +
`.saga/spend-authority.json` resolve each unit `silent`/`ask` against a `silent_ceiling` (absent →
`sonnet/high`), using the same `is_escalation` predicate as the hard-block so the two levers agree.

### Missing verdicts — runtime failure vs. static non-applicability (R1–R5, KTD7–KTD10)

A verifier that dies before emitting resolves to a `null` verdict slot (harness contract: terminal
error → `null`, KTD7) — the only machine-detectable absence in the emitted script. The reconciliation
treats this as a **runtime failure**, recomputing the pass-rule threshold over the `k` verifiers that
actually reported rather than the declared `n`:

| `pass_rule` | Threshold over `k` reporters |
|---|---|
| `majority` | `max(1, ⌈k/2⌉)` |
| `unanimous` | `max(1, k)` |

The `max(1, …)` guard makes an all-missing panel (`k = 0`) deterministically **not refuted**, rather
than vacuously refuted (`0 >= ⌈0/2⌉ = 0` would otherwise hold). A quorum floor of `⌈n/2⌉` of the
**declared** `n` is baked as a literal at emit time (KTD9) — distinct from the `n=3` authoring
default above; when the reporting count `k` falls under it, the emitted script logs which verifiers
were missing (by index) and the `k/n` the verdict was computed over, with an UNDER-STRENGTH marker.
The floor only *annotates* — a refutation over reporters still throws (or retries, for
`iterate_to_consensus`) regardless of under-strength (KTD10); suppressing a refutation because the
quorum ran small would reintroduce the exact uphold-bias this recompute exists to remove.

**Two-kinds boundary (R2/R9).** Runtime failure (above) is never conflated with **static
non-applicability** — a panel member whose precondition is absent (e.g. a reviewer dimension with no
relevant repo state). Static non-applicability is resolved **at composition**: author a smaller `n`
before dispatch, so it never enters the floor or the missing-verdict bookkeeping at all. Runtime
failure is resolved **at reconciliation**, as above. A unit's `verify.n` is always the count actually
dispatched.

**Known residue (KTD8, Q1).** There is no verifier-level timeout in v1: workflow scripts cannot
express timers (`Date.now()` / `new Date()` throw by design, for resume-safety) and `agent()` exposes
no timeout option, so a *hung* (not terminally-errored) verifier is unreachable from the emitted
script and blocks the panel's `parallel([...])`. This stays a harness/operator liveness concern, not
something the emitted script can detect.

## Topological-layer parallelism (KTD4)

The emitter computes **topological dependency layers** (Kahn) from each unit's `depends_on` list and any
implicit pilot barrier (`pilot` → fan-out). Units whose full dependency set is satisfied by earlier layers
run in one or more bounded, sequential `parallel([...])` chunks; the full layer completes before the next
dependency layer begins:

- **Singleton layer** → plain `const x = await agent(...)`.
- **Multi-unit layer** → each bounded chunk emits
  `const [x, y, z] = await parallel([...])`, destructured back into per-unit vars. Chunks preserve
  declaration order and form one dependency barrier as a group.

Verify panels for units in a parallel wave are emitted **after** the wave closes (so the panel reads the
result from the already-resolved var). Within a layer, units keep their declaration order for deterministic
emission. A dependency cycle among the remaining units raises a `SpecError` at emit time (fail loudly, not
silently).

The pilot implicit barrier is included in the layer computation: a fan-out unit's pilot always lands in a
strictly earlier layer than the fan-out itself, preserving the R3 gate even in a complex topology.

## The two authoring-time invariants (fail emit)

A mis-built spec is an invalid oracle, so the emitter **fails loudly** rather than emitting a
broken script. `ExecutionSpec.validate()` runs at emit time and raises `SpecError`:

- **R10 — enumerated fan-out targets.** A `fanout: true` unit with an empty / missing
  `targets` list fails emit. A fan-out without an explicit target list is a silent filter;
  the emitted agent additionally reconciles after the run (reports any declared target it did
  not complete — never silently dropped).
- **R3 — pilot/fan-out same tier.** A fan-out unit may name a `pilot` (run one target first
  to de-risk the fan-out). The pilot **must** be at the same `{model, effort}` tier as the
  fan-out — a mis-tiered pilot validates a different cost surface than the fan-out runs on, so
  it is an invalid oracle and fails emit.

It also rejects: an empty name / empty units, duplicate `unit_id`s, a `depends_on` / `pilot`
that does not resolve to a declared unit, a `targets` list without `fanout: true`, and any
`model` / `effort` outside the closed tier vocabulary (`fable|opus|sonnet|haiku` ×
`low|medium|high|xhigh`).

## Cheap-tier budget discipline (baked in)

Generated **cheap-tier** agents (haiku) carry the `workflow_structuredoutput_budget` lesson
baked into their emitted prompt as a rider: **cap output** (terse, no recaps), **mandatory
emit** (the final action MUST be the StructuredOutput call, even on partial work), **skim**
(open only the lines needed, never whole large files), and **batch** (parallel independent
tool calls). A budget-exhausted cheap agent that never emits its result is the failure this
prevents.

## Capability-portable degradation (R11 / U12)

Every authored plan is **capability-portable**: it carries a runnable **inline/serial
baseline** alongside the dynamic-workflow script, so it executes on ANY host — with or
without the Workflow tool. The dynamic-workflow layer (`emit_workflow_script`) applies only
on a capable host.

On an **off-host resume** the Workflow tool is re-checked and the orchestration tier
recompiles DOWN — and **only the orchestration tier**. The unit specs and per-unit
`{model, effort}` tiers are PRESERVED across the recompile; a downgrade changes only *how*
units are dispatched (serial, inline), never *which* units run or *at what tier*.

The flow has three moving parts:

1. **`lifecycle_state.recheck_orchestration_capability(...)`** — the capability probe. Given
   the resumed `orchestration_mode` and whether the Workflow tool is available, it returns a
   structured decision: `{downgraded, from, to, note, workflow_available}`. It **never errors
   and never silently runs nothing** (AE3): on a capable host `downgraded=False` and the
   authored tier is kept; off-host it returns a runnable lower tier (`team-execution`, or the
   always-runnable `inline` floor) plus a one-line `note`. An unknown stored mode floors to
   `inline` rather than raising. Tiers ladder, most-capable first:
   `cc-workflows-ultracode → team-execution → inline`.

2. **`execution_spec.recompile_for_tier(spec, mode, repo_root=...)`** — re-emits the *same* spec for the
   (possibly downgraded) tier: `cc-workflows-ultracode` → the dynamic `.workflow.js`; any
   other tier → the inline/serial baseline (`emit_inline_baseline`). Both preserve unit specs
   and per-unit tiers. Capability-routed workflow recompilation requires the authoritative target
   repository root so routing overlays and calibration come from that repository; omitting it fails
   closed with `capability emission requires explicit repo_root`. Exact-engine workflow specs and
   non-workflow tiers remain compatible with the two-argument call.

3. **`saga.orchestration_downgrade`** — the recorded note. The downgrade is durable, not
   silent: the one-line note from step 1 is written to the saga so a later `/retro`/`/optimize`
   pass (and the operator) can see the plan ran degraded and why.

```bash
# Re-check host capability on an off-host resume and recompile the orchestration tier.
uv run python plugins/saga/scripts/lifecycle_state.py recheck-capability \
    --orchestration-mode cc-workflows-ultracode --no-workflow
# -> {"downgraded": true, "from": "cc-workflows-ultracode", "to": "team-execution", "note": "...", ...}

# Emit the runnable inline/serial baseline (the R11 floor) from a spec.
uv run python plugins/saga/scripts/execution_spec.py baseline spec.json -o baseline.md
```

## `/plan` author-validate-emit-approve-persist flow

When the operator chooses `cc-workflows-ultracode`, `/plan` follows this five-step flow before writing the
saga tick (Phase 5.2a in `skills/plan/SKILL.md`). Emit comes BEFORE approve so the operator confirms the
actual generated script, not a description of it:

1. **Author** — derive per-unit `{model, effort}` tiers from the work-shape heuristic; write thin per-unit
   prompts (KTD2 — a thin pointer to the plan, not a prose transcription); wire `depends_on` barriers and
   optional `verify` panels. Surface the tier table for operator review.

2. **Validate (HARD BLOCK)** — run the validator. A non-zero exit means the spec is malformed; do NOT
   proceed until fixed. Common failures: `depends_on` cycle, fan-out with no `targets` (R10), pilot tier
   mismatch (R3), `verify.n` above `VERIFY_N_CAP`, two unit_ids that sanitize to the same JS var.

   ```bash
   python3 plugins/saga/scripts/execution_spec.py validate docs/plans/<name>-spec.json
   ```

3. **Emit** — write the `.workflow.js` beside the spec (`emit` re-validates, so a malformed spec fails here
   too):

   ```bash
   python3 plugins/saga/scripts/execution_spec.py emit docs/plans/<name>-spec.json \
     -o docs/plans/<name>.workflow.js
   ```

4. **Approve** — surface the now-emitted `.workflow.js` and the per-unit tier table for explicit operator
   confirmation. The operator must confirm the tier assignments and the control-flow structure; a rejection
   means revising the spec and re-running validate + emit.

5. **Persist** — write the saga tick with `--orchestration-ref` pointing at the **spec JSON** (the
   canonical artifact — the `.workflow.js` is regenerable, so the ref is the spec, not the script):

   ```bash
   python3 plugins/saga/scripts/saga.py save \
     --orchestration-mode cc-workflows-ultracode \
     --orchestration-ref docs/plans/<name>-spec.json \
     --orchestration-recommended <recommend_execution_backend() output>
   ```

The spec JSON is the durable canonical artifact; the `.workflow.js` can be regenerated at any time via
`emit`. `/work` re-emits fresh from the spec at execution time, so an intermediate re-plan that changed the
spec is automatically reflected.

## CLI

```bash
# Validate a spec (R3/R10 invariants); exit 2 + a SPEC ERROR on a violation.
uv run python plugins/saga/scripts/execution_spec.py validate spec.json

# Emit a runnable workflow script (stdout, or -o to a file).
uv run python plugins/saga/scripts/execution_spec.py emit spec.json -o out.workflow.js

# Unattended emission (#364): escalate_on_signal refutes climb one rung in-script
# instead of throwing the attended ask-gate proposal.
uv run python plugins/saga/scripts/execution_spec.py emit spec.json --unattended -o out.workflow.js

# Emit the runnable inline/serial baseline (R11 floor — runs on any host).
uv run python plugins/saga/scripts/execution_spec.py baseline spec.json -o baseline.md

# Report the priced plan (#366): per-unit spend, multiplicity-aware total, cost_budget
# headroom, and spend_envelope. Reports even an over-budget spec (never HALTs).
uv run python plugins/saga/scripts/execution_spec.py spend spec.json
```
