---
title: team-execution external-engine workers (U12 follow-up from #283)
type: feat
status: active
date: 2026-07-02
origin: docs/plans/2026-07-01-external-engine-capability-routing-plan.md
---

# team-execution external-engine workers (U12 follow-up from #283)

Close the one deliberately-deferred leg of #283 (ship-with-deferred, KTD7): let an external engine
(agy, codex) run **as a team-execution worker or advisory validator** — via a resident Claude
**chaperone worker** that resolves, dispatches through the existing containment wrappers, verifies
the returned evidence, applies the patch as sole-committer, and writes the worker-exit provenance
manifest. This activates the dispositions #285 reserved in
`plugins/team-execution/skills/team-execution/references/worker-manifest.md:47-49`
(`fell-back-to-claude` / `substituted-engine`) and completes R10/R12 of the #283 requirements doc.

**Operator decisions already made (2026-07-02):** chaperone-worker dispatch shape (over
coordinator-dispatches); scope = workers **and** advisory validators; chaperone tier is
**intent-driven and operator-confirmed** (see KTD2).

## Problem frame (carried WHAT — do not re-litigate)

- Requirements: `docs/brainstorms/2026-06-27-external-engine-capability-routing-requirements.md`
  R10 (dispatch across all three backends), R12 (worker/validator context-package contract),
  R13/R14/R15 (external engines never gatekeepers; non-gated roles only), R23 (evidence-only,
  no file-mutating external workers until the sandbox profile ships), R24 (visible downgrade
  note on fallback/substitution), R26 (explicitly-named unavailable engine halts).
- #285's worker-manifest contract (R14 leg): engine workers must record real
  `substituted-engine` / `fell-back-to-claude` dispositions with `kind=external-engine`
  attribution.
- New operator requirement (this session): a delegation carries one of two **intents** —
  **offload** (reduce Claude token spend; the chaperone must be cheap or the delegation is
  net-negative) or **second-opinion** (an independent pair of eyes; extra tokens are assumed).
  The intents pull the chaperone tier in opposite directions, so the operator picks per worker.

## What exists / what's missing (grounded)

| Seam | State | Evidence |
|---|---|---|
| Resolver worker role + Claude fallback | **Done** | `plugins/saga/scripts/engine_resolver.py:18-20` (`"worker"` ∈ `ROLE_KINDS`, ∈ `FALLBACK_ROLE_KINDS`) |
| Engine dispatch adapters + failure → fallback note | **Done** | `plugins/saga/scripts/engine_dispatch.py:39-121` (codex/agy invocations, `downgrade_note`) |
| Dispatch manifest builder (external-engine attribution) | **Done** | `plugins/saga/scripts/engine_dispatch.py:124-186` |
| Manifest dispositions + store CLI | **Done** | `plugins/saga/scripts/provenance_manifest.py:57-59`; `manifest_store.py` CLI |
| Unit-level engine/capability selector + registry validation | **Done** | `plugins/saga/scripts/execution_spec.py:236-259` (`_validate_external_engine_selector`) |
| Team Structure worker table — engine discriminator | **Missing** | `plugins/team-execution/skills/team-execution/SKILL.md:228` (columns: Agent, Units, Tier, Mode, Depends-on — no engine slot) |
| team_emitter engine-worker rendering | **Missing** | `plugins/saga/scripts/team_emitter.py:102-120` renders `seg.tier` only; zero engine references |
| Chaperone protocol + context-package contract | **Missing** | no reference doc; `worker-manifest.md:21` names this gap explicitly |
| External advisory validator slot | **Missing** | `references/validator-registry.md` has no engine entry |

The precedent to mirror: cc-workflows dispatch (#283 U5) wraps each engine unit in a Claude
subagent (`execution_spec.py:733,769` emits `// external-engine dispatch:` markers). The chaperone
worker is the team-execution analog of that same R9 "wrap in subagent" rule.

## Key Technical Decisions

**KTD1 — Chaperone worker, not coordinator dispatch (operator-decided 2026-07-02):** one resident
Claude worker (`worker-<engine>`, e.g. `worker-agy`) owns an engine's units end-to-end: resolve
(`engine_resolver.resolve({"role_kind": "worker", "engine"|"capability": …}, mode="dispatch",
registry=…)` — the role_kind rides in the request dict, `engine_resolver.py:79`; `"dispatch"` ∈
`MODES`, `:17`) → wrapper dispatch (agy
`no-write`/patch-only or codex `-s read-only`) → verify evidence → apply patch as sole-committer →
run unit tests → write the exit manifest. Fits the residency protocol (R3 reuse, wave scheduling)
and keeps worker-manifest.md's "the worker itself writes it" contract with a single writer mode.
*Rejected:* coordinator dispatches inline (context bloat per dispatch; needs a second
driver-materialized manifest writer mode; two executor kinds in wave scheduling).

**KTD2 — Delegation intent drives the chaperone tier; operator confirms (operator-required
2026-07-02):** each engine worker carries `intent ∈ {offload, second-opinion}`.
Default tier mapping — `offload` → chaperone `sonnet/medium` (mechanical verify-apply-test; a
heavier chaperone erases the token savings that motivated the delegation); `second-opinion` →
chaperone `opus/high` (adversarial verification IS the product; extra spend assumed; `fable/xhigh`
available as a per-unit override, never a default). The mapping produces a **recommendation** in
the existing Phase-A tier table; the operator confirms or overrides per worker — never silently
locked. *Rejected:* one fixed chaperone tier (the two intents have opposite cost goals — a fixed
tier is wrong for one of them by construction).

**KTD3 — Discriminator = two nullable columns on the existing Workers table, not a new
subsection:** `### Workers` gains `Engine` and `Intent` columns (`—` for Claude workers). Resident
naming follows the selector, previewing only what is knowable at plan time: an explicit-engine unit
renders `worker-<engine-key>` with Engine cell `<key>`; a capability-routed unit renders
`worker-<capability-key>` with Engine cell `cap:<key>` (the concrete engine is resolved at run time
and recorded in the manifest — KTD4's substitution baseline). One
parse path for Step B0, one emitter template, one oracle set. *Rejected:* a separate
`### External Workers` subsection (two parsers, two templates, drift risk between them).

**KTD4 — One worker-exit manifest per unit, external-engine attribution:** the chaperone writes a
single manifest via the `manifest_store.py` CLI shaped per worker-manifest.md, with
`kind=external-engine`, `identity=<engine>/<variant>` (same format the dispatch builder emits —
`engine_dispatch.py:153`), `effort=<engine effort>`, `protocol` populated from the resolution, and
the honest disposition (`ran-as-requested`; `fell-back-to-claude` when the wrapper fails and the
chaperone does the unit itself; `substituted-engine` when run-time capability routing resolves a
different engine/variant than the plan-time resolution preview the operator approved (recorded in
the tier-table recommendation row, U2) — the only reachable substitution path, since an
operator-**named** engine halts instead of substituting, R26). The chaperone
constructs `provenance_manifest.Manifest` directly (worker-manifest.md's documented path);
`engine_dispatch.build_dispatch_manifest` maps only ran-as-requested/fell-back
(`engine_dispatch.py:143-148`) and is out of scope to change. *Rejected:*
dual manifests (dispatch manifest + worker manifest) — two records for one output invites
divergence; the dispatch detail lands in the one manifest's fields.

**KTD5 — Validators are advisory-only, opt-in, never blocking (operator-scoped 2026-07-02):** a
new `external-second-opinion` validator entry dispatches through the same chaperone protocol, its
verdict enters validator evidence as **advisory** (Blocking = never — R13/R15 forbid external
gatekeepers), and it is selected only via explicit `.team-execution.json` opt-in, never
auto-selected by Phase A. A failed external validator dispatch records its downgrade note and the
run proceeds — Required-Evidence Absence rules do NOT apply to an advisory external validator.

**KTD6 — Evidence-only + Claude-sole-committer carried forward (R23):** the engine never edits the
working tree; the chaperone applies the returned patch and owns the commit. File-mutating external
workers stay out of scope (blocked on the ideation-R14 sandbox profile — issue #287, unchanged).

**KTD7 — Fallback/halt semantics reuse the resolver's, verbatim:** capability-routed no-fit →
Claude fallback with visible note (R8/R24, disposition `fell-back-to-claude`); operator-**named**
engine unavailable → halt the worker's units, surface to coordinator, do not silently substitute
(R26). No new policy — the chaperone consumes `Resolution.halt` / `Resolution.fallback` as-is.

## Implementation Units

### U1 — Chaperone protocol + context-package reference doc

**Goal:** new `plugins/team-execution/skills/team-execution/references/external-engine-workers.md`
defining the full contract: what the coordinator sends the chaperone (unit IDs, plan pointer,
engine selector, intent, plan-time resolution preview, write-set scope); what the chaperone
assembles for the engine (the resolver's protocol-wrapped payload, forwarded **verbatim** — R11);
the verify→apply→test→manifest exit sequence; how substitution is detected (compare the run-time
resolution's engine/variant against the plan-time preview from the context package — KTD4); KTD7
fallback/halt semantics; the never-gatekeeper boundary restated.

**Depends on:** —

**Test expectation:** `tests/test_team_execution_plugin.py::test_validator_references_are_packaged_and_linked`
extended to include the new reference file (packaged + linked from SKILL.md's Reference Files list).

### U2 — SKILL.md integration (discriminator + wave protocol)

**Goal:** extend `### Workers` table (SKILL.md Step A7 template) with `Engine` / `Intent` columns
(KTD3); extend Step B1's residency protocol with the chaperone dispatch flow and a pointer to U1's
reference doc; add the reference doc to the Reference Files list; state the KTD2 intent→tier
recommendation rule where the tier table actually lives — the saga `/plan` tier-derivation step
(`plugins/saga/skills/plan/SKILL.md:295-305`, "present the full tier table … confirm or override
before locking"). An engine unit's recommendation row carries intent, the KTD2 chaperone-tier
default, and the plan-time capability-resolution preview ("resolves today to `<engine>/<variant>`")
— the baseline KTD4's substitution detection compares against. Team-execution Phase A (Steps
A0–A7) has no tier step of its own, so this unit touches `plugins/saga/skills/plan/SKILL.md` too.

**Depends on:** U1

**Test expectation:** none — markdown template surfaces are covered by U3's emitter oracles
(the emitter's output IS the A7 template; a drift between them fails `tests/test_team_emitter.py`).

### U3 — execution_spec `engine_intent` + team_emitter engine-worker rows

**Goal:** add optional `Unit.engine_intent ∈ {offload, second-opinion}` to
`plugins/saga/scripts/execution_spec.py` (valid only alongside `engine`/`capability`; defaults to
`offload`). `tier` stays a **required** Unit field (`from_dict` requires `data["tier"]`,
`execution_spec.py:428`) — the KTD2 intent→tier default is a plan-time recommendation row in the
tier heuristic (lands with U2's `/plan` SKILL.md touch), not a schema default. Render engine-owned
segments in `plugins/saga/scripts/team_emitter.py` per the KTD3 naming rule — `worker-<engine-key>`
/ Engine cell `<key>` for explicit selectors, `worker-<capability-key>` / Engine cell `cap:<key>`
for capability routes — with populated Engine/Intent columns (`—`/`—` for Claude workers).

**Depends on:** U2 (column shape is the contract)

**Test scenarios** (`tests/test_saga_execution_spec.py`, `tests/test_team_emitter.py`):
- `engine_intent` without `engine`/`capability` → SpecError; bad vocabulary value → SpecError.
- `engine_intent` omitted on an engine unit → defaults to `offload`; explicit values round-trip
  `to_dict`/`from_dict`.
- emitted Workers table: explicit-engine segment renders `worker-agy` + Engine cell `agy`;
  capability segment renders `worker-<capability-key>` + Engine cell `cap:<key>` (no plan-time
  engine guess); Claude segments render `—`/`—`. No existing oracle asserts the 5-column header
  (current asserts are
  id/tier/heading presence — `tests/test_team_emitter.py:123,146-150,307,338`), so U3 must **add**
  the column-shape oracles: header row with Engine/Intent, a populated engine row, a Claude row
  with `—`/`—` cells.

### U4 — worker-manifest.md engine-worker leg

**Goal:** update `plugins/team-execution/skills/team-execution/references/worker-manifest.md`:
replace the "reserved for the future leg" language with the live contract — engine-worker
attribution per KTD4, all three dispositions with their trigger conditions (KTD4; halt/fallback
semantics per KTD7), chaperone as
the writer, `claim_provenance` guidance for engine output claims (chaperone adjudicates before any
claimed-`verified` counts — D5 unchanged).

**Depends on:** U1

**Test expectation:** none — contract prose; the store/schema it points at is already tested
(`tests/test_manifest_store.py`, `tests/test_provenance_manifest.py`, unchanged).

### U5 — Advisory external validator slot

**Goal:** add the `external-second-opinion` validator entry to
`references/validator-registry.md` (advisory, Blocking = never, `.team-execution.json` opt-in key,
chaperone-dispatch pointer to U1) with matching touches in `validator-criteria.md` and
`validator-evidence-state.md` (advisory external evidence is exempt from Required-Evidence
Absence — KTD5).

**Depends on:** U1

**Test expectation:** none — registry prose; selection is judgment-driven at Phase A, not
code-enforced (consistent with every other validator entry).

### U6 — Release surfaces + journal

**Goal:** CHANGELOG entries (team-execution minor, saga minor), `plugin.json` version bumps,
`.claude-plugin/marketplace.json` mirror, `docs/engineering-journal/DECISIONS.md` entry for
KTD1/KTD2/KTD5 (chaperone shape, intent-driven tier, advisory-only validators) with revisit-when
conditions.

**Depends on:** U1–U5

**Test expectation:** existing metadata drift guards
(`tests/test_team_execution_plugin.py::test_team_execution_metadata_is_v2_and_marketplace_matches`
and `tests/test_saga_plugin.py::test_infiquetra_lifecycle_metadata_and_marketplace_entry_match`)
must pass with the new versions.

## Scope Boundaries

**Out of scope (true non-goals):**
- File-mutating external workers (R23 second half — still blocked on the sandbox profile, issue #287).
- External engines in any gated/blocking position: reviewer consensus, blocking validators,
  automation-eligibility signals (R13/R15; KTD5 restates it).
- Changes to `engine_resolver.py`, `engine_dispatch.py`, `provenance_manifest.py`,
  `manifest_store.py` — the saga side is complete; this plan consumes it.
- Auto-selection of the external validator (opt-in only).
- A measurement/ROI loop over delegation outcomes (maintenance stays `/retro`).

**Deferred follow-up:**
- Intent-aware token accounting (did an `offload` delegation actually net-save?) — a `/retro`
  question first; only automate if the manual loop proves painful.

## Risks

- **Chaperone overhead can eat the offload win.** Named honestly in KTD2; the sonnet/medium
  default plus thin-pointer context package is the mitigation, and the manifest's effort field
  makes the actual spend auditable per unit.
- **The new columns land untested by default (U3).** No current emitter test asserts the column
  shape (verified: header/row oracles absent from `tests/test_team_emitter.py`), so adding
  Engine/Intent breaks nothing — and guards nothing. U3 must add the header/row oracles or KTD3's
  discriminator has no drift guard.
- **Wrapper availability in worker context.** The chaperone runs the same preflight the resolver
  already encodes (R26 halt / R8 fallback); no new availability machinery.

## Sources

- `docs/plans/2026-07-01-external-engine-capability-routing-plan.md` (KTD7, U12 deferral, HTD).
- `docs/brainstorms/2026-06-27-external-engine-capability-routing-requirements.md` (R10, R12–R15, R23–R26).
- `docs/plans/2026-07-01-evidence-provenance-manifests-plan.md` (#285 R14 leg, worker-manifest contract).
- Operator decisions this session: chaperone shape; workers+validators scope; intent-driven tier.
