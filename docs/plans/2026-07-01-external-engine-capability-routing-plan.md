---
title: External-Engine Capability Routing
type: feat
status: active
date: 2026-07-01
origin: docs/brainstorms/2026-06-27-external-engine-capability-routing-requirements.md
---

# External-Engine Capability Routing

## Summary

Build a saga-owned **registry + resolver + thin dispatch-adapter** that maps a logical capability
(or an explicitly-named engine) to a concrete `{engine, effort, protocol}`, assembles the engine's
required prompting discipline into a literal payload, and dispatches it to the wrapper each engine
already owns (`codex:codex-rescue`, `agy:delegate`) — with Claude as verifier-of-record on every
gated decision. The build itself is dogfooded: bounded code units are drafted by Codex under a
read-only, evidence-only, Claude-commits contract, so building the router exercises the very
delegation path the router formalizes.

## Problem Frame

Saga already reaches external engines by hand — the #283 readiness review ran a three-engine panel
(Codex `xhigh` + agy Gemini Pro + agy Gemini Flash) as gated generators under Claude verification,
and the S-1 sibling plan records "a codex + agy adversarial pass" as house practice
(`DECISIONS.md#worker-cache-scheduling`). The value is proven; what is missing is reusable
machinery. Today the choice of "which engine, what effort, prompted how" lives in the operator's
head and the hard-won prompting discipline (Gemini anti-sycophancy framing, Codex read-only posture)
is re-applied from memory each time or forgotten. This capability turns that manual practice into
data an operator and the engine can both consult, and a resolver that applies it consistently across
inline and cc-workflows dispatch.

This is VECU port seed **S-4** (`docs/ideation/2026-06-26-vecu-port-seeds-ideation.md`). The WHAT is
settled and readiness-reviewed (`docs/reviews/2026-06-27-external-engine-capability-routing-readiness.md`,
verdict READY). This plan answers only the HOW and records the binding decision the capability
establishes.

## Requirements Traceability

Every requirement from the requirements doc maps to a unit. R12 is deferred (see Scope Boundaries).

| Requirement | Unit(s) |
|---|---|
| R1 registry per-variant, default variant, composing roles | U1 |
| R2 three content kinds per entry (profile / protocol / recipe) | U1 |
| R3 model identity + last-validated stamp | U1 (field), U7 (populated) |
| R4 editable-as-data, not code | U1 |
| R5 capability → `{engine, effort, protocol}` | U2 |
| R6 explicit engine → `{effort, protocol}`; default variant | U2 |
| R7 advisory vs dispatch modes | U2, U5 |
| R8 no-fit → Claude fallback (worker/generator) + note | U2, U3, U4 |
| R9 wrap in subagent; forward literal payload verbatim | U2 (payload), U4 (dispatch) |
| R10 dispatch across backends (inline + cc-workflows; team-exec deferred) | U4, U5 |
| R11 protocol applied to the engine's own payload, verbatim | U2, U4 |
| R12 team-execution worker context-package contract | **Deferred** (U12 follow-up) |
| R13 Claude verifier-of-record | U4, U6, U8 |
| R14 external engines: generator / advisory-reviewer / non-gated-worker only | U4, U6 |
| R15 gated consensus stays team-execution; external only advisory | U5, U6 |
| R16 doc-review external-reviewer panel is first-class | U6 |
| R17 composing role unavailable → halt, do not sub Claude for the panel | U3, U6 |
| R18 operator requests by capability | U2 |
| R19 operator names an engine | U2 |
| R20 override pre-dispatch/advisory; autonomous acts on standing config + post-hoc | U2, U4 |
| R21 maintenance via `/retro`, no auto-measurement | U7 |
| R22 staleness surfaced when last-validated predates a model revision | U1 (check), U7 (dates) |
| R23 evidence-only / non-mutating by default | U4 |
| R24 fallback/substitution emits a visible provenance/downgrade note | U2, U4 |
| R25 context-window fitness; no silent truncation | U1 (field), U2 (check) |
| R26 explicitly-named unavailable engine halts | U2, U3 |

## Key Technical Decisions

**KTD1 — Registry + resolver live in the saga plugin.** Every seam the resolver must hook already
lives in saga: the per-unit `engine` field (`execution_spec.py`), `recommend_execution_backend()`
(`lifecycle_state.py:99`), the `saga.orchestration_downgrade` provenance field
(`saga-spec.md:121-125`), and the reviewer-role wiring (`doc-review`/`code-review` SKILLs). *Rejected:*
a new `external-engines` plugin (fragments the resolver from its seams, adds an 8th marketplace plugin
to version); folding into `agy` (conflates one engine's containment wrapper with the cross-engine
router — asymmetric, since agy is in-repo and codex is external).

**KTD2 — Registry is a YAML data file, not code and not JSON.** R4 requires editable-as-data. YAML is
already a saga convention (`plugins/saga/docs/model/saga-docs-model.yaml`; `render_docs_visuals.py`
imports yaml; `pyyaml` is a declared dependency), supports inline comments and structured per-row
source-attribution fields, and is hand-editable by the operator over time (R21). *Rejected:* JSON
(no comments, trailing-comma footguns for a hand-edited file); a Python dict (violates R4).

**KTD3 — Logical capabilities are a fixed, closed vocabulary.** The resolver validates capability
keys against a seeded enum exactly as `execution_spec.py:48` validates `MODELS`/`EFFORTS`. This keeps
every capability routable and typo-proof. *Rejected:* free-form keys (unvalidatable; R8's no-fit path
fires unpredictably on a typo).

**KTD4 — `engine` is a new parallel field on the execution_spec `Unit`, not an extension of
`tier.model`.** `MODELS = ("opus","sonnet","haiku")` (`execution_spec.py:48`) is load-bearing for
Claude-agent dispatch (`:674`); widening it to `"gpt-5.5"` would corrupt tier semantics. The emitter
reads `Unit.engine` *before* `tier.model` and routes engine-bearing units through the dispatch
adapter. *Rejected:* extend the `MODELS` enum.

**KTD5 — The resolver dispatches to existing engine wrappers; it does not own containment.** agy
already owns disposable-clone + remotes-stripped containment and a provenance bundle under
`.claude/agy/runs/`; codex owns its `-s read-only|workspace-write` sandbox. The resolver assembles the
literal protocol payload (R9/R11) and a thin adapter injects it into each engine's native invocation
slot verbatim (codex → the `task "<text>"` argument; agy → the envelope `task` field), never
paraphrasing or shell-interpolating. *Rejected:* a new unified containment harness in saga (duplicates
proven wrappers, re-opens solved clobber risk).

**KTD6 — Codex delegation for this build is evidence-only (read-only), Claude sole-committer.** Codex
drafts bounded code units, returns them as a diff plus assumptions, and Claude verifies against the
plan's R-IDs, runs the full gate, and commits. This dogfoods the capability's own R23 ("external
workers return evidence, not edits, until the sandbox profile exists") and matches the repo's
containment lesson (external-agent *agency* is the liability, not its code). The registry's own
capability profile does the routing: code-generation/refactor/debug → Codex, long-form writing (the
`DECISIONS.md` entry, the seed data) → Claude. *Rejected:* write-capable Codex on the real working
tree (uncontained agency path; contradicts R23).

**KTD7 — team-execution dispatch (R10/R12) is deferred.** No external-engine worker context-package
contract exists — workers are Claude agents fed by `SendMessage` (`team-execution SKILL.md:226-228,
294-304`); adding a worker-type discriminator + context-package slot is ~50-100 LOC of new spec.
Because external engines are never gatekeepers (R13/R15), they are off team-execution's critical
path. Inline + cc-workflows dispatch cover the real use case now. Deferred as U12.

**KTD8 — "External engines are never gatekeepers" is recorded as a new binding decision.** The
parroting note (`DECISIONS.md:276-290`) is *evidence*, not a standing rule; the gated-vs-advisory
split (`operator-choice.md:82-95`) is the *mechanism* this rides on. Per readiness fix #3, this plan
lands the real `DECISIONS.md` entry when the capability ships (U8).

**KTD9 — Deterministic capability tie-break: cost·speed (operator-confirmed 2026-07-01).** The resolver
selects the best-rated variant for a capability (STRONG > MODERATE > WEAK); when ≥2 variants rate it
equally, the tie is broken by **cost·speed — cheapest-fastest wins** (the repo's "recommend
cheapest-correct" convention plus the seed table's cost·speed column), with registry declaration order
as the final deterministic backstop when cost·speed is also equal. A resolver must be deterministic on
ties or two runs pick different engines. *Rejected:* corroboration-strength as the tie-break (operator
chose cost·speed on 2026-07-01); prompt-the-operator-on-every-tie (breaks autonomous dispatch, R20).
This lands as the `DECISIONS.md` rationale in U8, and the seed data (U7) must therefore carry a
comparable cost·speed value per variant for the ordering to be well-defined.

## High-Level Technical Design

**Component topology.** The registry is data; the resolver is the one decision point; dispatch is a
thin adapter over wrappers that already exist.

```
saga (the engine)
 ├─ references/engine-registry.yaml     ← data (R4): variants, capabilities, roles, sources
 ├─ scripts/engine_registry.py          ← loader + schema validator + staleness check
 ├─ scripts/engine_resolver.py          ← resolve() [advisory|dispatch] + preflight + payload assembly
 └─ hooks it already owns:
      execution_spec Unit.engine · recommend_execution_backend · saga.orchestration_downgrade
         │  resolve → {engine, effort, protocol, recipe, payload}
         │  assemble LITERAL payload (R9/R11) · preflight (R26) · fitness check (R25)
         ▼  dispatch adapter injects payload verbatim into the wrapper's native slot
      ┌────────────────────────────┬────────────────────────────┐
      ▼                            ▼                            (deferred U12)
   codex:codex-rescue          agy:delegate                  team-execution
   `task "<payload>"`          envelope.task = <payload>     worker context-package
   -s read-only (R23)          mode: no-write (R23)
      │                            │
      └──────────► Claude verifies result before any gate (R13) ◄──────────┘
```

**Registry entry schema (YAML).** One entry per engine *variant*; capabilities and roles are
top-level maps.

```yaml
capabilities:                 # KTD3 closed vocabulary (resolver validates against this)
  [code-generation, adversarial-review, second-opinion, debug, refactor, scaffold, long-form-writing]

engines:
  - engine_id: codex          # stable
    variant: gpt-5.5-xhigh    # variant = engine + effort when behavior materially changes (R1)
    substrate: external       # external marketplace plugin (vs agy = in-repo)
    default_for_engine: false # R1: which variant an engine-only request resolves to
    invocation:               # R2 field 3 — the concrete recipe
      via: codex:codex-rescue # the wrapper path — NEVER raw codex
      recipe: "codex -s read-only --effort xhigh"
      write_capable: false    # R23 evidence-only default
    context_window: 400000    # R25
    cost_speed_rank: 2        # KTD9 tie-break key — lower = cheaper+faster; integer, orderable
    model_identity: gpt-5.5
    last_validated: 2026-06-27 # R3
    capability_profile:       # R2 field 1 — keyed to the closed vocabulary
      code-generation: {rating: MODERATE, note: "structured-output fidelity, multi-file refactor"}
      debug:           {rating: MODERATE, note: "tool-orchestrated"}
      long-form-writing: {rating: WEAK,   note: "route to Claude"}
    prompting_protocol:       # R2 field 2 — forwarded VERBATIM into the engine payload (R11)
      - "Run read-only when generating against the repo."
      - "Give tools to iterate when debugging (quality drops in pure-chat mode)."
      - "Manage context actively; it does not self-manage."
      - "Reserve xhigh for the hardest tasks (cost multiplier)."
    sources:                  # per-row attribution (seed requirement)
      - {claim: "top composite reasoning", url: "<openai gpt-5.5 model card>", date: 2026-06-27,
         tag: OFFICIAL, corroboration: STRONG}

roles:                        # R1/R16 composing roles reference multiple variants
  cross-family-review-panel:
    members: [codex/gpt-5.5-xhigh, agy/gemini-3.1-pro-high, agy/gemini-3.5-flash-high]
    verdict: advisory         # R15 — never gated
    verifier: claude          # R13 — Claude verifies each finding against source
```

For **agy-substrate entries**, `invocation` additionally carries `model:` holding the **verbatim
canonical `--model` string** agy expects (e.g. `"Gemini 3.1 Pro (High)"`, not a slug); the U4 adapter
forwards it byte-for-byte, because agy's `--model` is passed through verbatim
(`agy_delegate.py:1519-1542`). The `members:` slugs are registry lookup keys, not the strings sent to agy.

**Resolver contract.**

```
resolve(request, *, mode) -> Resolution
  request : {capability?: str, engine?: str, task_context?: dict,
             role_kind: "worker" | "generator" | "advisory-reviewer" | "panel"}  # capability XOR engine
  mode    : "advisory" | "dispatch"                                 # R7
  Resolution:
    engine_id, variant, effort, recipe
    protocol : list[str]          # the discipline lines from the registry
    payload  : str                # literal protocol + context, assembled here (R9/R11)
    write_capable : bool          # R23
    fallback : Optional[str]      # set ONLY for role_kind worker|generator: a no-fit capability
                                  #   falls back to Claude with a downgrade note (R8/R24)
    halt     : Optional[str]      # set when an explicitly-named engine is unavailable (R26), OR for
                                  #   role_kind advisory-reviewer|panel a member is unavailable (R17 —
                                  #   never substitute Claude for a reviewer; halt instead)
```

**Operator surface (R18/R19/R20).** This capability ships **two** operator entry points, not a new
standalone command. (1) *Declarative* — a plan/spec unit carries a discriminated request: either
`engine:` (a variant id, R19) **or** `capability:` (a vocabulary key, R18), never both (U5); the
resolver runs at emit/dispatch time. (2) *Opt-in role* — the
`/doc-review` external-reviewer panel (U6). Both are override points: inline dispatch lets the operator
override pre-dispatch (R20); autonomous cc-workflows dispatch acts on the standing registry config and
surfaces its selection post-hoc. A standalone interactive `/engine resolve <capability>` command is
**explicitly out of scope** for this plan (see Scope Boundaries) so an implementer does not invent one.

## Implementation Units

### U1. Registry schema, loader, and validator

Define the YAML registry schema and a loader that validates it hard, so a malformed or stale entry
is caught as data rather than surfacing at dispatch time.

**Goal:** A `engine_registry.py` module that loads `engine-registry.yaml`, validates every entry, and
exposes lookups by capability, by engine (with default-variant resolution), and by role.

**Requirements:** R1, R2, R3, R4, R16 (role model), R22 (staleness check), R25 (context_window field).

**Dependencies:** none.

**Files:** `plugins/saga/references/engine-registry.yaml` (schema skeleton only; seed data is U7),
`plugins/saga/scripts/engine_registry.py`, `tests/test_saga_engine_registry.py`.

**Approach:** Mirror `execution_spec.py`'s dataclass + `from_dict` validator pattern
(`:214-239`). Closed `CAPABILITIES` tuple validated like `MODELS`/`EFFORTS`. `EngineEntry`,
`Role` dataclasses; `Registry.load(path)` raises a `RegistryError` (analogous to `SpecError`) on
missing required field, unknown capability key, missing `last_validated`, missing per-row `sources`,
a missing or non-integer `cost_speed_rank` (required for the KTD9 tie-break to be well-defined), or a
role referencing a non-existent variant. Add `Registry.stale(entry, known_revision_dates)` for R22.

**Patterns to follow:** `plugins/saga/scripts/execution_spec.py` (dataclass + `from_dict` + closed
enums); `plugins/saga/scripts/render_docs_visuals.py` (yaml load in a saga script).

**Test scenarios:**
- Happy path: a valid two-entry registry loads; lookup by capability returns the highest-rated
  variant; lookup by engine-only returns the `default_for_engine` variant.
- Edge: an engine with no `default_for_engine: true` and >1 variant → `RegistryError` (ambiguous).
- Edge: `stale()` returns true when `last_validated` predates a supplied model-revision date; false
  otherwise.
- Error: unknown capability key in a `capability_profile` → `RegistryError` naming the bad key.
- Error: an entry missing `sources` → `RegistryError` (seed requirement enforced as data).
- Error: a role member referencing a non-existent `engine/variant` → `RegistryError`.

**Verification:** `uv run pytest tests/test_saga_engine_registry.py` is green; a hand-written invalid
fixture is rejected with a line-identifying message.

### U2. Resolver — advisory and dispatch modes

The single decision point that maps a request to a concrete engine and assembles the literal payload.

**Goal:** `engine_resolver.resolve(request, mode)` returning the `Resolution` contract, covering
capability lookup, explicit-engine handling, fallback, halt, payload assembly, and the R25 fitness check.

**Requirements:** R5, R6, R7, R8, R9, R11, R18, R19, R20, R24, R25, R26.

**Dependencies:** U1.

**Files:** `plugins/saga/scripts/engine_resolver.py`, `tests/test_saga_engine_resolver.py`.

**Approach:** `resolve` accepts a capability XOR an engine name, plus a required `role_kind` that
governs the fallback-vs-halt fork. Capability → best-rated variant for that capability (R5); ties are
broken by the deterministic chain in KTD9. Engine name → that engine's default variant + protocol,
refined by `task_context` when present (R6). `mode="advisory"` returns the `Resolution` for a caller to
act on; `mode="dispatch"` additionally marks it ready for the adapter (R7). Payload assembly
concatenates the registry `prompting_protocol` lines + the caller-supplied context into one string,
forwarded verbatim downstream (R9/R11) — the resolver never shell-interpolates. **Fallback vs halt is
role-kind-gated** (R25 note distinguishes them): a no-fit capability for `role_kind`
worker/generator → `fallback` note set to a Claude-substitution message (R8/R24); a no-fit or
unavailable engine for `role_kind` advisory-reviewer/panel → `halt`, never a Claude substitute (R17 —
Claude reviewing Claude defeats the purpose). Explicitly-named unavailable engine → `halt` regardless of
role (R26). `task_context.token_estimate > context_window` → `halt` with a fitness message (R25),
never a silent truncation.

**Patterns to follow:** `lifecycle_state.py:223-309` `recheck_orchestration_capability()` (the
`{downgraded, note}` result-dict shape R24 mirrors).

**Test scenarios:**
- Happy path: `resolve({capability: "code-generation"}, "dispatch")` returns Codex variant + its
  protocol lines + assembled payload.
- Happy path: `resolve({engine: "codex"}, "advisory")` with no task_context returns the
  `default_for_engine` variant (R6).
- Edge: payload assembly preserves protocol-line order and content byte-for-byte (R11 — assert no
  paraphrase/reorder).
- Edge: `resolve({capability: "long-form-writing"}, ...)` → `fallback` note (no engine rates it) not a
  Codex/Gemini pick (R8).
- Error: `resolve({engine: "codex"})` when preflight reports codex unavailable → `halt` set, no
  substitution (R26/AE6).
- Error: task token estimate exceeds the variant `context_window` → `halt` with fitness reason (R25),
  never a truncated payload.

**Verification:** `uv run pytest tests/test_saga_engine_resolver.py` green; a byte-equality assertion
proves the assembled payload contains the registry protocol lines verbatim.

### U3. Preflight / availability contract

Learn whether each engine is actually usable before the resolver commits to it.

**Goal:** `engine_resolver.preflight(engine_id) -> {available, reason}` checking CLI presence and a
cheap auth/health probe for codex and agy.

**Requirements:** R8, R17, R26 (and AE1, AE6).

**Dependencies:** U1.

**Files:** `plugins/saga/scripts/engine_resolver.py` (preflight function),
`tests/test_saga_engine_resolver.py` (preflight cases).

**Approach:** Preflight is **best-effort and cheap**: `command -v codex`/`command -v agy` for presence,
plus a credential-config check (presence of the engine's auth/config file) — it does **not** make a
live API call, so `codex --version` proves presence, not auth. Rate-limit and stale-token failures
therefore cannot be reliably detected at preflight; the dispatch adapter (U4) must treat a dispatch-time
auth/rate-limit failure as the same `halt` signal (R26), so unavailability surfaces whether it is caught
early (preflight) or late (dispatch). Preflight returns `{available, reason}`; the resolver halts a
named-but-unavailable engine (R26) and halts a panel whose member is unavailable rather than
substituting Claude (R17 — Claude reviewing Claude defeats the purpose). Probes are mocked in tests (no
live CLI dependency in CI).

**Patterns to follow:** subprocess-with-timeout usage already present in saga scripts; keep probes
read-only and bounded.

**Test scenarios:**
- Happy path: mocked `command -v` success + credential-config present → `{available: true}`.
- Edge: CLI present but the credential-config file is absent → `{available: false, reason:
  "not configured"}`.
- Error: CLI absent → `{available: false, reason: "not installed"}`; resolver turns this into a halt
  for a named request (AE6) and for a panel member (AE1/R17).
- Note: rate-limit / stale-token failures are **not** preflight-detectable; their coverage lives in U4
  as dispatch-time halt tests, not here.

**Verification:** `uv run pytest tests/test_saga_engine_resolver.py -k preflight` green with all
subprocess calls mocked.

### U4. Dispatch adapters — inline + cc-workflows

Hand a resolved payload to the wrapper each engine already owns, and route the result back to Claude
before it can feed any gate.

**Goal:** A dispatch adapter that, given a `Resolution`, invokes `codex:codex-rescue` or `agy:delegate`
with the payload injected verbatim, returns the engine's evidence, and records a provenance/downgrade
note on any fallback.

**Requirements:** R9, R10 (inline + cc-workflows only), R11, R13, R14, R20, R23, R24 (and AE4, AE5, AE7).

**Dependencies:** U2, U3.

**Files:** `plugins/saga/scripts/engine_dispatch.py`, `plugins/saga/references/engine-dispatch.md`
(the dispatch contract), `tests/test_saga_engine_dispatch.py`.

**Approach:** For codex, build the `codex:codex-rescue` invocation with `-s read-only` (R23) and the
payload as the `task` text (AE5 — verbatim, no wrapper paraphrase). For agy, build an `agy.delegation.v1`
envelope with `mode: no-write` (R23) and `task = payload`, `model` = the registry's verbatim canonical
string. The adapter is evidence-only, and R13 is **enforced structurally, not just asserted**: every
external result is wrapped in an `advisory-evidence` result type that carries no verdict field, and the
emitter/gate path (`execution_spec.py:120-147`, `:671-681`) refuses to let an `advisory-evidence`
result satisfy a gated return until a distinct Claude verification step has stamped it — so a workflow
cannot wire raw external evidence into a gate even by mistake. A no-fit fallback or substitution writes
a one-line note destined for `saga.orchestration_downgrade` (R24), mirroring the existing downgrade
record. Override semantics
(R20): in interactive/inline dispatch the operator can override pre-dispatch; in autonomous
cc-workflows dispatch the adapter acts on the standing registry config and surfaces its selection
post-hoc in the result rather than blocking.

**Patterns to follow:** `plugins/agy/scripts/agy_delegate.py` envelope construction + verbatim
`--model` forward (`:1519-1542`); the codex-rescue `task` contract
(`codex/skills/codex-cli-runtime/SKILL.md`).

**Test scenarios:**
- Happy path (codex, mocked): a `Resolution` produces a `codex:codex-rescue` call whose `task` text
  equals the assembled payload byte-for-byte and whose recipe includes `-s read-only`.
- Happy path (agy, mocked): produces an `agy.delegation.v1` envelope with `mode: no-write`, `task` =
  payload, `model` = the verbatim registry string.
- Edge (AE7): a worker asked to change files with no sandbox profile present returns the proposed
  change as evidence, not an edit.
- Edge (R24): a fallback path emits a downgrade note string with engine + reason.
- Failure modes (one per wrapper status the wrappers actually return — `agy_delegate.py:441-498, :745-788`):
  timeout, no-output, error, malformed-output, and agy disposable-clone failure each → `halt` +
  provenance note, and **no** gated verdict is produced.
- Dispatch-time (relocated from U3): a mocked auth/rate-limit failure at call time → `halt` with the
  reason surfaced (R26), since preflight cannot detect it.
- Integration: dispatch → result → the adapter surfaces an `advisory-evidence` result to Claude and
  asserts no gated verdict field is set by the engine, and that the result cannot satisfy a gated
  return without a Claude verification stamp (R13).

**Verification:** `uv run pytest tests/test_saga_engine_dispatch.py` green; payload byte-equality and
"no gated verdict" assertions both hold.

### U5. `engine` field on execution_spec Units + advisory backend hook

Let a plan unit name an engine, and let advisory external panels reach the ultracode judge-panel
branch instead of team-execution.

**Goal:** A parallel `engine` field on the execution_spec `Unit`, emitter routing for engine-bearing
units, and a wiring so the resolver's advisory mode drives the internal `advisory_consensus` branch (by
passing `needs_consensus=True, consensus_is_gated=False`).

**Requirements:** R7, R10 (cc-workflows), R15.

**Dependencies:** U2.

**Files:** `plugins/saga/scripts/execution_spec.py`, `plugins/saga/scripts/lifecycle_state.py`,
`tests/test_saga_execution_spec.py` (create if absent; else extend existing execution_spec coverage).

**Approach:** Add two optional, mutually-exclusive fields to `Unit` (KTD4) — `engine: Optional[str]`
(a variant id, R19) and `capability: Optional[str]` (a vocabulary key, R18) — both defaulting to
`None` (a pure Claude unit) so every existing spec still parses; `Unit.from_dict` rejects a unit that
sets both. The emitter, when either is set, resolves it and emits a dispatch-adapter call instead of a
native Claude agent option, consuming the resolved engine before `tier.model` (`execution_spec.py:674`).
Advisory external panels call `recommend_execution_backend(needs_consensus=True, consensus_is_gated=False)`
— `advisory_consensus` is computed internally from those two args, it is **not** a parameter — so they
route to the ultracode judge-panel branch and never regress to inline
(`lifecycle_state.py:164-183`; `operator-choice.md:82-95`).

**Patterns to follow:** `execution_spec.py` `Unit.from_dict` (add the field with a default so older
specs parse); the S-1 sibling's "derive saga-side" seam (`DECISIONS.md#worker-cache-scheduling`).

**Test scenarios:**
- Happy path: a spec with `engine: codex/gpt-5.5-xhigh` on one unit validates; the emitter produces a
  dispatch call for that unit and a normal Claude agent for units without `engine`.
- Edge: `engine` referencing an unknown variant → `SpecError` at validate time.
- Edge: a unit that sets **both** `engine` and `capability` → `SpecError` (mutually exclusive, KTD4).
- Edge: an existing spec JSON with neither field parses unchanged (backward compatibility).
- Integration: `recommend_execution_backend(needs_consensus=True, consensus_is_gated=False)` returns
  `ultracode`, not `team-execution` (R15).

**Verification:** `uv run pytest tests/test_saga_execution_spec.py` green; `execution_spec.py validate`
still passes on the existing example specs (no regression).

### U6. First-class external-reviewer role

Turn the ad-hoc three-engine review panel into a reusable, registry-defined role.

**Goal:** A `cross-family-review-panel` role the resolver can dispatch, wired into `/doc-review` (and
optionally `/code-review`) as an opt-in panel whose findings Claude verifies against source before
adoption, with the gated verdict staying Claude's.

**Requirements:** R14, R15, R16, R17 (and AE3, F3).

**Dependencies:** U1, U4.

**Files:** `plugins/saga/references/engine-registry.yaml` (the role entry),
`plugins/saga/skills/doc-review/SKILL.md` (opt-in panel wiring),
`tests/test_saga_engine_registry.py` (role resolution) + `tests/test_saga_engine_dispatch.py`
(panel dispatch is advisory).

**Approach:** The role names its member variants and marks `verdict: advisory`, `verifier: claude`
(R15/R13). The resolver expands the role into per-member dispatches (each with its own protocol, R11).
`/doc-review` gains a short opt-in section: "run the external-reviewer panel" → dispatch the role,
Claude verifies each finding against the doc/repo source, adopts only verified findings (F3). If any
member is unavailable, the panel halts and surfaces it rather than substituting Claude (R17). This unit
adds the *role* and the wiring; it does not add a new SDLC gate.

**Patterns to follow:** the readiness review's own Method section (the panel it ran by hand); existing
`/doc-review` SKILL structure for an opt-in pass.

**Test scenarios:**
- Happy path: role resolution returns three member `Resolution`s, each with its own protocol.
- Edge (R15/AE3): the panel's aggregate result carries `verdict: advisory` and no gated field.
- Error (R17): a mocked-unavailable member halts the panel with a surfaced reason (no Claude
  substitution).

**Verification:** `uv run pytest tests/test_saga_engine_registry.py tests/test_saga_engine_dispatch.py`
green; the SKILL edit is a documented opt-in, not a forced step (grep confirms it is gated on operator
request).

### U7. Seed capability data with per-row source attribution

Populate the registry from the readiness review's captured sources — a dated seed, not a permanent
ranking. Claude-owned (judgment + attribution; the registry's own profile routes writing to Claude).

**Goal:** Three seeded engine entries — Codex/gpt-5.5 (`high`, `xhigh`), Gemini 3.1 Pro (High) via
agy, Gemini 3.5 Flash (High) via agy — each row carrying a `cost_speed_rank` (from the seed table:
Gemini Flash = 1 cheapest·fastest, Codex = 2 mid; the KTD9 tie-break key), OFFICIAL/INDEPENDENT tags + corroboration +
`last_validated`.

**Requirements:** R3, R21, R22 (dates), seed requirement.

**Dependencies:** U1.

**Files:** `plugins/saga/references/engine-registry.yaml`, `tests/test_saga_engine_registry.py`
(seed-validity + staleness cases).

**Approach:** Transcribe the capability profiles + prompting protocols from the requirements doc's Seed
Capability Data table and the readiness review's "Captured capability-research sources" section, each
claim tagged per row. Set `last_validated: 2026-06-27`. Record the known correction (Gemini Pro is
**not** the expert-writing engine → long-form writing routes to Claude). No measurement loop; drift is
handled by `/retro` re-validation (R21).

**Patterns to follow:** the requirements-doc Seed Capability Data table and the readiness-review source
list (both already corroboration-tagged).

**Test scenarios:** `Test expectation: none -- data file, validated by U1's loader.` Coverage is the
U1 validator asserting every seeded row has `sources` + `last_validated`, plus a staleness test that
flags the seed when a later revision date is supplied.

**Verification:** `uv run pytest tests/test_saga_engine_registry.py` green against the real seed file;
`engine_registry.py` loads the seed without error.

### U8. Binding decision + plugin release surfaces

Record the decision the capability establishes and keep the installed-plugin metadata telling the same
story as the diff.

**Goal:** A `DECISIONS.md` entry for "external engines are never gatekeepers," plus the mandatory
release-surface updates.

**Requirements:** R13 (decision of record); repo release-surface discipline (CLAUDE.md step 6).

**Dependencies:** U1–U7.

**Files:** `docs/engineering-journal/DECISIONS.md`, `plugins/saga/.claude-plugin/plugin.json`
(version bump), `.claude-plugin/marketplace.json` (saga version mirror),
`plugins/saga/CHANGELOG.md`, and any version/metadata drift-guard test under `tests/`.

**Approach:** DECISIONS entry mirrors the house format (Date / Plan / KTDs / rejected alternatives /
revisit-when), citing `operator-choice.md:82-95` (mechanism) and `DECISIONS.md:276-290` (the parroting
evidence, reframed). Bump saga's version, mirror it in `marketplace.json`, add a CHANGELOG entry.
Long-form writing is Claude-owned per KTD6.

**Patterns to follow:** `DECISIONS.md#worker-cache-scheduling` (the S-1 sibling entry);
the marketplace.json editing guard in project memory (include the last entry's `}` + array `]` +
`"version"` line; `python3 -m json.tool` after).

**Test scenarios:** `Test expectation: none -- docs + metadata.` Coverage is the existing
version/metadata drift-guard test (saga plugin.json version == marketplace.json == CHANGELOG top) and
`ruff format --check` + the two plugin validators in CI.

**Verification:** `uv run pytest` full suite green; `python3 -m json.tool .claude-plugin/marketplace.json`
parses; drift guard passes.

## Codex Delegation Map

This is the plan for the `/work` phase's use of the codex plugin — the dogfool you asked to see. It is
capability-aware routing applied to the router's own build: units whose work matches a Codex strength
are drafted by Codex; units the registry's own profile flags as Codex-weak (long-form writing,
judgment) stay with Claude.

**Contract for every Codex-delegated unit (KTD6, R23):**
- **Invocation:** `codex:codex-rescue` (never raw `codex`). **Read-only is load-bearing and must be
  forced explicitly** — the `codex:codex-rescue` forwarder defaults to `--write` and only runs
  `-s read-only` when the request "only wants review, diagnosis, or research without edits"
  (`codex/skills/codex-cli-runtime/SKILL.md`). A bare "implement U-N" reads as write-capable, which is
  the uncontained posture KTD6 rejects. So each delegation is framed as an explicit read-only research
  task ("do NOT edit any files; return the implementation as a diff in your response") **and** the
  verification gate runs `git status --porcelain` before and after each Codex call — a non-empty delta
  from Codex is treated as a contract breach, not accepted output. Effort per the registry protocol:
  `xhigh` reserved for the hardest unit (U2), `high` for the rest.
- **Prompt shape (thin pointer, KTD from the plan skill):** *"Read the plan at
  `docs/plans/2026-07-01-external-engine-capability-routing-plan.md` as the authoritative spec.
  Implement `<U-N>`. Return the implementation and its tests as a unified diff. Do NOT edit any files.
  Enumerate your assumptions and any open questions. Manage context actively."*
- **Return contract:** evidence only — a unified diff + assumptions + a test list. No commits, no tree
  edits.
- **Verification gate (Claude, sole-committer, R13):** Claude reviews the diff against the unit's
  R-IDs and test scenarios, applies it, runs `uv run pytest && uv run ruff check . && uv run mypy
  plugins/`, and only then commits. A failed or incomplete Codex run is reported as a finding and
  Claude implements the unit itself — never a silent Claude substitute presented as Codex output.

| Unit | Owner | Codex capability | Effort | Why |
|---|---|---|---|---|
| U1 registry loader/validator | **Codex draft** | code-generation | high | Structured dataclass + validator — Codex structured-output strength. |
| U2 resolver | **Codex draft** | code-generation | **xhigh** | The hardest logic (modes, fallback, halt, payload assembly); reserve xhigh (protocol). |
| U3 preflight | **Codex draft** | debug / devops | high | CLI probes + terminal orchestration — a Codex strength. |
| U5 execution_spec `engine` field + hook | **Codex draft** | refactor | high | Multi-file structured refactor — a Codex strength. |
| U4 dispatch adapter (code) | **Codex draft**; policy prose Claude | code-generation | high | Adapter code to Codex; the trust-boundary contract prose stays Claude. |
| U6 reviewer role (code) | Split | — | — | Role-resolution code → Codex; the `/doc-review` SKILL prose → Claude. |
| U7 seed capability data | **Claude** | — | — | Judgment + per-row source attribution; the registry's own profile routes writing to Claude. |
| U8 DECISIONS entry + release surfaces | **Claude** | — | — | Long-form writing + governance — Codex-weak by the seed data's own finding. |

**Dogfool payoff.** Running this map produces the first real dispatch traces for the registry. These
are **explicit-engine requests** (`resolve({engine: "codex"}, ...)`, R6/R19) — the operator named
Codex — not capability routing (R5), because the registry's seed profile rates several engines for
`code-generation` and a capability request could resolve to Gemini Flash instead. The traces still
exercise the whole dispatch path (payload assembly → `codex -s read-only` → Claude-verifies); frictions
surface as `/retro` input that re-validates the seed capability data (R21) — which is exactly how the
requirements doc says the registry stays honest.

## Risks & Dependencies

- **Codex `codex:codex-rescue` defaults to write-capable.** Mitigation: every delegation is framed
  read-only (review/diagnosis/generate-as-diff, "do NOT edit files") so the forwarder runs
  `-s read-only`; the verification gate re-asserts no tree edits arrived out of band (U4 AE7 test is
  the standing check).
- **Codex 400K context window (R25).** Mitigation: the resolver's fitness check halts rather than
  truncates; per-unit delegation prompts are thin pointers to the plan, not inlined context.
- **Seed capability data drifts.** Accepted, by design: R21 makes re-validation a `/retro` concern, not
  an automated measurement loop (per project memory: no ROI ceremony on solo tools).
- **team-execution wrapper contract unproven.** Mitigation: deferred to U12; inline + cc-workflows are
  the shipped paths.
- **Dependency:** codex is an external-marketplace plugin (not in this repo's `marketplace.json`); agy
  is in-repo (`plugins/agy/`, v0.1.0). The registry treats both as substrate via their wrappers; the
  preflight contract (U3) is how the system learns an engine is actually installed/authenticated.

## Alternatives Considered

- **New `external-engines` plugin** (KTD1 rejected) — cleaner ownership, but fragments the resolver
  from the saga seams it must hook and adds an 8th marketplace plugin to version.
- **Fold routing into the `agy` plugin** (KTD1 rejected) — reuses agy containment, but conflates one
  engine's wrapper with the cross-engine router; asymmetric given codex is external.
- **Extend the `tier.model` enum to carry engines** (KTD4 rejected) — smallest diff, but corrupts the
  closed `MODELS` set that Claude-agent dispatch depends on.
- **Write-capable Codex on the real tree** (KTD6 rejected) — faster, but the uncontained agency path
  the repo already learned to avoid; contradicts the capability's own R23.
- **Define the team-execution wrapper contract now** (KTD7 rejected for this plan) — real ~50-100 LOC
  of new spec for a path external engines don't need to be on (they're never gatekeepers); deferred.

## Scope Boundaries

**Out of scope (true non-goals):**
- External engines holding any gated verdict, blocking merge/deploy, or persisting a gate (R13 forbids
  it; this is the decision U8 records).
- A measurement / ROI / scoring loop over engine quality (R21 — maintenance is `/retro`, not metrics).
- A new containment harness (agy and codex own containment; KTD5).
- Changing the closed `MODELS`/`EFFORTS` tier vocabulary (KTD4).
- A standalone interactive `/engine resolve <capability>` command — the operator surface is the
  declarative `Unit.engine` field (U5) plus the `/doc-review` panel opt-in (U6).

**Deferred to Follow-Up Work:**
- **U12 — team-execution external-engine dispatch (R10/R12).** Define the worker-type discriminator +
  context-package slot in `team-execution` (SKILL.md:226-228), then wire the adapter. A separate
  `/plan`.
- **File-mutating external workers (R23 second half).** Blocked on the ideation-R14 read-only-sandbox /
  worktree-ownership profile; until it ships, external workers stay evidence-only.
- **GPT-5.5 refuter/second-opinion behavior mapping** — unproven until the operator exercises the
  `second-opinion` capability; the seed entry flags it as residual risk.

## Sources / Research

- Requirements: `docs/brainstorms/2026-06-27-external-engine-capability-routing-requirements.md` (R1–R26,
  Seed Capability Data, Key Flows F1–F4, Acceptance Examples AE1–AE7).
- Readiness review: `docs/reviews/2026-06-27-external-engine-capability-routing-readiness.md` (verdict
  READY; captured capability-research sources for registry seeding).
- Ideation origin: `docs/ideation/2026-06-26-vecu-port-seeds-ideation.md` (survivor S-4); prior art
  `docs/ideation/2026-05-30-delegate-agent-plugin-ideation.md`.
- Code seams: `plugins/saga/scripts/execution_spec.py:48` (closed `MODELS`/`EFFORTS`), `:214-239`
  (Tier validator), `:310-410` (Unit schema), `:674` (`tier.model` consumption);
  `plugins/saga/scripts/lifecycle_state.py:99-113` (`recommend_execution_backend`), `:164-183`
  (gated/advisory branch), `:298-302` (downgrade note); `plugins/saga/references/operator-choice.md:82-95`
  (gated-vs-advisory split); `plugins/saga/references/execution-spec.md:136-138` (durable downgrade);
  `plugins/saga/references/saga-spec.md:121-125, :493` (saga fields + `/plan` consumer row);
  `plugins/team-execution/skills/team-execution/SKILL.md:226-228, 294-304` (worker contract gap).
- Sibling engine wrappers: `plugins/agy/scripts/agy_delegate.py:1519-1542` (verbatim `--model`),
  `:808-854` (disposable-clone containment); codex plugin
  `codex/skills/codex-cli-runtime/SKILL.md` (the `task` forwarder contract).
- Sibling decision precedent: `docs/engineering-journal/DECISIONS.md#worker-cache-scheduling` (S-1 /
  #275, same VECU campaign, same codex+agy adversarial-pass discipline).
