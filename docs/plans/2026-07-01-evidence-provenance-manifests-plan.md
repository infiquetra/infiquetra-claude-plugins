---
title: Evidence / Provenance Manifests — a verified-vs-adjudicated record per delegated output
type: feat
status: active
date: 2026-07-01
origin: docs/brainstorms/2026-06-28-evidence-provenance-manifests-requirements.md
issue: infiquetra/infiquetra-claude-plugins#285
---

# Evidence / Provenance Manifests — a verified-vs-adjudicated record per delegated output

Give saga a typed, persisted provenance manifest on every delegated agent output — one envelope per
execution carrying an `output_completeness` subrecord (declared vs produced) and a `claim_provenance`
subrecord (source-attributed claims with a producer-*claimed* vs Claude-*adjudicated* two-layer tag) —
stored on a cross-worktree carrier, wired into the two gates that shipped while the issue was being
written, and consumed as an advisory signal by `/code-review`, `/qa`, and `/retro`.

## Issue verification & drift report (trust-but-verify)

The operator asked for the issue to be verified, not trusted, with improvements recorded here. Every
load-bearing citation was checked against the current tree on 2026-07-01. Verdicts:

| # | Issue claim | Verdict | Evidence |
|---|---|---|---|
| V1 | `orchestration_downgrade` is a complete produce→persist→consume loop | **VERIFIED** (mechanism) | Note *produced* by the recompile fn in `plugins/saga/scripts/lifecycle_state.py` (~230-310); field + guard in `plugins/saga/scripts/saga.py:178-180,640-669`; consumed in `plugins/saga/scripts/override_rate_reader.py:74,137,215`. The field name never appears in `lifecycle_state.py` — it produces the note dict; `saga.py` persists it. Citation correct in substance. |
| V2 | S-7 (#277) and S-4 (#283) are "proposals, not built code"; gate consumers are "scheduled" | **STALE — the plan's biggest correction** | #277 CLOSED 2026-06-29 (PR #303, `b09ad50`); #283 CLOSED 2026-07-01 (PR #316, `c702668`, QA verdict ship-with-deferred). Both gates are LIVE. D7's two-speed framing (advisory now, gates later) is inverted: the gate wiring is now the *cheap* half because the gates already compute the data R11 persists. |
| V3 | Parroting finding at `DECISIONS.md:290` | **DRIFTED** | Now at `docs/engineering-journal/DECISIONS.md:410` (the journal grew). Substance verified: Antigravity parroted two code claims; degrade wiring shipped wrong. |
| V4 | D6: "`/plan` writes any new DECISIONS.md entry" for the never-gatekeeper rule | **OVERTAKEN** | #283 already recorded it: `DECISIONS.md:1452` `{#external-engines-never-gatekeepers}`, explicitly a NEW binding decision citing the parroting note as evidence. R11 references it; no new entry for the rule itself. |
| V5 | S-7's gate "needs a post-execution record to diff declared against produced… and cannot perform today" | **PARTLY STALE — new fact** | `plugins/saga/scripts/completeness_gate.py` (shipped by #277) computes exactly this: `Contract.derive()` (declared, from `Unit.returns`/fanout targets), `classify()` → presence/truncation/fanout-count/required-keys checks. It computes at gate time and **discards** — no persisted record. R11's `output_completeness` = persisting what `classify()` already computes. |
| V6 | — | **NEW FACT (naming collision)** | `completeness_gate.py:172` has a function literally named `check_manifest` meaning "required-keys check" — a different sense of "manifest" than R11's envelope. No external callers exist (grep of `tests/`, `plugins/`, `status_card.py`: zero refs outside the module). Renamed in U4 (KTD6). |
| V7 | — | **NEW FACT (proto-manifest exists)** | `plugins/saga/scripts/engine_dispatch.py:26-33` `AdvisoryEvidence` already carries `provenance: dict[str, Any]` (untyped: engine/variant/status/note) and `verified_by_claude: bool`; `satisfy_gate()` (:122-128) already refuses unverified evidence. R11 types this dict into the envelope rather than adding a parallel record. |
| V8 | `Unit.returns` at `execution_spec.py:180,536-537` | **DRIFTED** (lines) | Field now at `execution_spec.py:374`; the :184 region is the *emitted JS* returns-check; contract-derivation at :648-652. Substance verified. |
| V9 | Carrier candidates: git-common-dir cache `outcome_store.py:93-148`; `CompletionEvent.payload` open dict `:252-296` | **VERIFIED** | `resolve_common_dir()` at :93; `CompletionEvent.payload: dict[str, Any]` untyped at ~:250-296. |
| V10 | R14 depends on the S-4 team-execution external-wrapper contract | **STILL TRUE** | #283 deferred team-execution dispatch (its U12/KTD7; plan `docs/plans/2026-07-01-external-engine-capability-routing-plan.md:115,613`). External engines cannot run as team-execution workers yet. R14's *external-engine-via-team-execution* leg stays scheduled; Claude team-execution workers are real today. |
| V11 | Prose-habit skill citations (`code-review:39-43`, `qa:49-58`, `doc-review:83-94`, `investigate:57-61`) | **VERIFIED** | All four present with the quoted semantics. |
| V12 | `validator-evidence-state` as closest existing manifest | **VERIFIED** | `plugins/team-execution/skills/team-execution/references/validator-evidence-state.md` — per-run JSON with inputs/evidence/findings; stored repo-local under `.claude/team-execution/validators/` (worktree-local, which is exactly the R19 breadth the manifest store fixes). |
| V13 | — | **NEW CONSTRAINT** | Workflow scripts have **no filesystem access** — a cc-workflows leaf cannot write its own manifest file. The driving session must persist it post-run from the spec contract + returned results (KTD7). The issue's "the producing agent emits the manifest" needs this qualification for the cc-workflows producer. |

**Corrections to post on #285** (one comment, at `/work` start): V2 (both gate consumers shipped —
sequencing question is moot, v1 wires them), V3/V8 (line drift), V4 (never-gatekeeper DECISIONS entry
exists), V5-V7 (completeness/provenance machinery partially exists; R11 types and persists it), V13
(cc-workflows producer is driver-mediated).

## Requirements traceability

R-IDs are carried verbatim from the requirements doc embedded in #285.

| Requirement | Unit(s) |
|---|---|
| R1 envelope + two subrecords | U1 |
| R2 producer attribution | U1, U3 |
| R3 output_completeness (declared vs produced) | U1, U4 |
| R4 claims with source refs + revision; `not-checkable` state | U1, U3 |
| R5 producer-claimed status + gate-effects | U1 (KTD4) |
| R6 Claude-adjudicated status + attested adjudication record | U1, U3 |
| R7 mismatch_reason taxonomy; parroting = refuted/unsupported only | U1, U6 |
| R8 advisory default, never blocks | U1, U6 |
| R9 payload sized to tier (full vs lightweight) | U1 (KTD9) |
| R10 missing manifest trips only contract-bearing leaves | U4 |
| R11 gated verdict requires Claude-adjudicated claims | U3 |
| R12 no gate of R11's own | U1, U6 (tests) |
| R13 completeness gate consumes output_completeness | U4 |
| R14 verifier-of-record consumes attribution + claim_provenance | U3 (engine leg live; team-execution leg scheduled, see Scope Boundaries) |
| R15 /code-review skips re-verifying adjudicated-verified | U6 |
| R16 /qa ratio signal; /retro parroting + disposition counts | U6 |
| R17 producer/consumer matrix; no orphan fields | U7 |
| R18 disposition (`ran-as-requested \| fell-back-to-claude \| substituted-engine`) | U1, U3, U6 |
| R19 durable cross-session/cross-worktree carrier | U2 |
| R20 evidence, never authority | U1 (schema holds no verdict field), tests in U1/U3 |
| R21 no new privilege; mutating external workers out of scope | U3, U5 (evidence-only assertions) |

## Key Technical Decisions

**KTD1 — Carrier: a git-common-dir `saga-manifests/` tree, plus a typed `manifest_ref` pointer in
`CompletionEvent.payload` for outcome leaves.** *(Operator-confirmed.)* One JSON file per delegated
invocation at `<git-common-dir>/saga-manifests/<saga-id>/<execution-id>.json`, resolved through the
same `resolve_common_dir()` used by `outcome_store.py:93` — the only candidate satisfying R19 for
delegations that never emit a `CompletionEvent` (agy runs during plain `/work`, team-execution outside
an outcome). Rejected: `CompletionEvent.payload`-only (outcome leaves only — R19 breadth fails); saga
tick pointer (ticks are per-checkout, git-ignored, worktree-local — a bg-worktree manifest would be
invisible to `/code-review` in main).

**KTD2 — Full-loop v1: producers + both shipped gates + advisory consumers, one PR.**
*(Operator-confirmed; drift-driven — see V2.)* The requirements doc's contract-first sequencing (D7)
assumed the gates didn't exist. They do, and they compute-and-discard the exact data R11 persists, so
gate wiring is persistence of computed data, not new verification.

**KTD3 — Saga-local schema with a version key; external vocabularies are prior art only.** The
envelope carries `schema: "saga.manifest.v1"`. in-toto/SLSA/PROV solve cross-organization supply-chain
attestation with signing and verifier ecosystems saga doesn't have; adopting one wholesale is ceremony
for a one-operator plugin system. Field *naming* may borrow (e.g. `predicate`-style separation of
envelope vs subrecords); the version key keeps later alignment open. Revisit when a manifest must be
consumed outside this marketplace.

**KTD4 — Producer-claimed vocabulary stays three-valued: `verified | inferred | not-checked`.**
Gate-effect (closing R5's open question): at a gate, *every* gate-relevant claim requires Claude
adjudication before a verdict persists, regardless of producer tag — the producer tag never changes
what the gate accepts, only where the verifier spends budget first (`not-checked`/`inferred` before
claimed-`verified`, per R15's budget-concentration logic). Collapsing to `verified | unverified` was
rejected: it erases the `inferred`-vs-`not-checked` distinction the verifier uses to rank attention,
and buys nothing — the layer is non-authoritative either way (D2).

**KTD5 — Adjudicated statuses `verified | inferred | not-checked | refuted`; `mismatch_reason` enum
`not-adjudicated | scope-excluded | source-stale | unsupported | refuted`.** Parroting is counted iff
claimed-`verified` ∧ adjudicated ∈ {`refuted`, `unsupported`} (R7). Implemented as a pure predicate
`is_parroting(claim)` in the schema module so the taxonomy is unit-testable without I/O — same
house pattern as `completeness_gate.py` ("pure Python, no I/O at import").

**KTD6 — Rename `completeness_gate.check_manifest` → `check_required_keys`.** It checks declared
`returns` keys against emitted keys — "manifest" there collides fatally with R11's envelope in a PR
that introduces the real manifest. Zero external callers (V6); the module is two days old. Cheap now,
confusing forever later. `classify()`'s behavior is unchanged; `tests/test_completeness_gate.py`
updated in the same unit.

**KTD7 — cc-workflows manifests are driver-materialized.** Workflow scripts cannot touch the
filesystem (V13), so the leaf cannot emit its own manifest file. The driving session persists one
manifest per unit post-run via `manifest_store.py record-completeness --spec <spec.json> --results
<results.json>`, deriving each declared contract with `completeness_gate.Contract.from_unit` and the
produced side from the returned results. Attribution (R2) uses the spec's per-unit label/model/effort.
This is a qualification of the issue's "the producing agent emits the manifest": for cc-workflows the
producer *declares* (in the spec + return value) and the driver *materializes*.

**KTD8 — `/retro` surfacing via a new `manifest_reader.py`, a sibling of `override_rate_reader.py`.**
Same reporting pattern (scan → counts → human/`--json` output: parroting count, disposition rate,
adjudicated-verified ratio), different substrate (common-dir manifest tree vs saga ticks). Extending
`override_rate_reader` in place was rejected — it would couple two unrelated scan roots behind one
CLI.

**KTD9 — One schema, tier-sized payload (R9).** A *lightweight* manifest is the envelope with both
subrecords absent (attribution + disposition + existence bit); a *full* manifest adds the subrecords.
No second schema, no second store path — `validate()` enforces that gate-feeding or contract-bearing
outputs carry the relevant subrecord.

**KTD10 — Model tiers use the Claude 5 family where capability is load-bearing.** U1 (the schema
contract everything downstream consumes) and U3 (gate semantics) run on **Claude Fable 5 at xhigh
effort** — Anthropic's most capable generally available model, a tier above Opus 4.8, with `xhigh`
the recommended effort for the hardest agentic/coding work (claude-api skill, cached 2026-06-24).
Cost is the tradeoff: $10/$50 per MTok vs Opus 4.8's $5/$25 — bounded here to 8 calls (2 units + 2×3
same-tier verifiers). Mechanical units stay on the `sonnet` alias, which this harness now resolves to
**Claude Sonnet 5** ($3/$15; intro $2/$10 through 2026-08-31) — no spec change needed for that
upgrade. Gated on U0 because `execution_spec.py:49-50` accepts only `opus|sonnet|haiku` ×
`low|medium|high` today; the session's Agent tool already lists `fable` as a valid subagent model.
Fallback if the Workflow runtime rejects fable at dispatch: opus/high (see Execution backend
section).

## High-level design

```
producers                          carrier (KTD1)                     consumers
─────────                          ──────────────                     ─────────
engine_dispatch.dispatch()   ──▶  <git-common-dir>/saga-manifests/  ──▶  satisfy_gate() reads
  provenance dict → typed          └─ <saga-id>/                          adjudicated status (R11)
  claim_provenance (U3)               └─ <execution-id>.json         ──▶  /code-review skips
/work post-run driver        ──▶     (schema saga.manifest.v1, U1;        adjudicated-verified (R15)
  spec+results →                      store read/write/CLI, U2)      ──▶  /qa verified:inferred
  output_completeness (U4)                    ▲                           ratio (R16)
team-execution worker exit   ──▶             │ typed pointer         ──▶  /retro parroting +
  (contract in refs, U5)           CompletionEvent.payload                disposition via
                                     ["manifest_ref"] (outcome           manifest_reader.py (U6)
                                      leaves only)
```

## Execution backend (operator-confirmed — do not confuse with U5)

**Backend: `cc-workflows-ultracode` (dynamic workflows), destination: merge.** The build runs as a
Claude Code Workflow script — NOT as a team-execution agent team. Artifacts: the canonical spec
`docs/plans/2026-07-01-evidence-provenance-manifests-spec.json` (saga `orchestration_ref`) and the
emitted `docs/plans/2026-07-01-evidence-provenance-manifests.workflow.js` (regenerable; control-flow
only, every agent reads this plan as the authoritative spec). Adversarial verify panels (n=3,
majority, advisory in-session votes) run on U1 and U3; `/code-review` remains the blocking gate
before PR.

The word "team-execution" elsewhere in this plan refers to a **product surface being wired** — U5
defines the manifest contract that team-execution *workers* will emit when team-execution runs are
used in the future — never to the backend executing this build.

**`/work` entry procedure — steps 1-3 DONE 2026-07-01 (pre-`/work`, working tree):** U0 landed
(`MODELS` prepended with `"fable"`, `EFFORTS` appended with `"xhigh"` — ordering is load-bearing
because `segment_units()` merges tiers via `min(MODELS.index)` / `max(EFFORTS.index)`; round-trip +
merge-order tests added; `execution-spec.md` vocabulary mirrored), the spec JSON retiered U1/U3 to
`{"model": "fable", "effort": "xhigh"}`, and `validate` + `emit` re-ran clean (the `.workflow.js`
now carries 8 `model: "fable"` calls). Remaining at `/work`:

1. Launch the workflow for U1-U8. If the Workflow runtime rejects `model: "fable"` for subagents at
   runtime, revert U1/U3 to `{"model": "opus", "effort": "high"}` in the spec, re-validate, re-emit —
   a one-line fallback, and record the downgrade in the saga tick.

## Implementation Units

Dependency order: U0 (inline, pre-workflow) → U1 → U2 → {U3, U4, U5 in parallel} → U6 → U7 → U8.

### U0. Enable fable/xhigh tiers in the spec validator — `plugins/saga/scripts/execution_spec.py` — **DONE 2026-07-01**

**Goal:** Extend `MODELS` (`execution_spec.py:49`) with `"fable"` and `EFFORTS` (`:50`) with
`"xhigh"` so execution specs can tier judgment-heavy units on Claude Fable 5. Mirror in the
tier-guidance table in this skill's operator-choice reference if it enumerates models.

**Requirements:** none from #285 — enabling infrastructure for KTD10; smallest possible diff (two
tuple entries + tests). `"max"` effort and team-emitter tier text are deferred until something needs
them.

**Test scenarios** (`tests/test_workflow_emitter.py`, `tests/test_team_emitter.py` where they
enumerate tiers):
- `test_tier_accepts_fable_model` / `test_tier_accepts_xhigh_effort` — validate + emit round-trip a `{"model": "fable", "effort": "xhigh"}` unit.
- Existing invalid-tier rejection tests still pass (unknown models still rejected).

### U1. Manifest schema module — `plugins/saga/scripts/provenance_manifest.py`

**Goal:** The envelope and both subrecords as frozen dataclasses with validation, `to_dict`/
`from_dict` round-trip, tier sizing, and the parroting taxonomy as pure predicates. No I/O at import
(house pattern per `completeness_gate.py:2-5`).

**Requirements:** R1, R2 (shape), R4-R9, R12, R18, R20.

**Approach:** `Manifest` (schema version, execution id, saga ref, producer attribution {kind:
external-engine|team-execution|cc-workflows, identity, effort/protocol per R2}, disposition R18,
created-at, optional subrecords), `OutputCompleteness` (declared keys / target count / produced keys /
count / diff — field-compatible with what `completeness_gate.Contract` + `classify()` know),
`ClaimProvenance` (list of `Claim`: text, source ref, source revision, claimed status, adjudicated
status, `mismatch_reason`, attested `Adjudication` {adjudicator, sources read, scope, revision,
decision} per D5). Pure functions: `is_parroting(claim)`, `mismatch_reason_for(claimed, adjudicated,
…)`, `validate(manifest, tier)`. The schema holds **no verdict field** (R20) and no mutation hooks.

**Test scenarios** (`tests/test_provenance_manifest.py`):
- `test_manifest_envelope_round_trip` — full + lightweight manifests survive to_dict/from_dict; unknown keys rejected or preserved per decision recorded in the module docstring.
- `test_manifest_envelope_requires_attribution_and_disposition` — envelope invalid without R2/R18 fields.
- `test_parroting_taxonomy_refuted_and_unsupported_counted` / `test_parroting_taxonomy_not_adjudicated_excluded` / `test_parroting_taxonomy_source_stale_excluded` — AE1/AE2 as pure-function cases.
- `test_advisory_never_blocks_no_verdict_field` — schema exposes no verdict/authority surface (R20/AE7); lightweight tier valid with zero subrecords (R9/AE4).
- `test_claim_without_source_ref_is_not_checkable` — R4.

### U2. Carrier — `plugins/saga/scripts/manifest_store.py`

**Goal:** Write/read/list manifests under `<git-common-dir>/saga-manifests/<saga-id>/
<execution-id>.json`, reusing `resolve_common_dir` imported from `outcome_store.py`; a typed
`manifest_ref` payload key helper for outcome leaves; CLI entry points (`write`, `read`, `list`,
`record-completeness` — the last lands in U4).

**Requirements:** R19, R1 (carrier metadata).

**Approach:** Mirror `outcome_store.Store` conventions (`_safe_name` sanitization, `ensure()`,
injectable `runner` for tests). `manifest_ref` helper writes/reads
`CompletionEvent.payload["manifest_ref"]` as a repo-relative-to-common-dir pointer — the payload
stays an open dict; the key gains a documented reader contract (closes the issue's "not yet a
consumer surface" note on `outcome_store.py:252-296`).

**Test scenarios** (`tests/test_manifest_store.py`):
- `test_manifest_store_write_read_round_trip` — write then read equals input.
- `test_manifest_store_resolves_common_dir_from_worktree` — injected runner returns a worktree-style `--git-common-dir`; path lands in the shared tree (R19).
- `test_manifest_ref_pointer_round_trip` — payload key set + resolved back to a readable manifest.
- `test_manifest_store_rejects_path_traversal_ids` — `_safe_name` parity with outcome store.

### U3. External-engine producer + gate read — `plugins/saga/scripts/engine_dispatch.py`

**Goal:** `dispatch()` emits a typed manifest (claim_provenance + attribution + disposition) through
`manifest_store`, replacing the ad-hoc `provenance` dict fields with envelope-backed data (the dict
may remain as a rendered view for backward compatibility of the AdvisoryEvidence surface);
`satisfy_gate()` enforces R11: a gated verdict cannot persist unless gate-relevant claims are
Claude-adjudicated — extending the existing `verified_by_claude` check to read adjudicated statuses
from the manifest.

**Requirements:** R2, R4-R7 (production side), R11, R14 (engine leg), R18, R20, R21.

**Approach:** Halted/failed dispatches record disposition + note exactly as today's `provenance["note"]`
path does (AE6/F4 — `fell-back-to-claude` / `substituted-engine` mapped from the existing
`downgrade_note` flow). Engine output claims enter as claimed-layer only; adjudication is written by
the driving session (Claude) via a `manifest_store` update helper — never by the engine (D5,
`#external-engines-never-gatekeepers`).

**Test scenarios** (extend `tests/test_saga_engine_dispatch.py`):
- `test_dispatch_emits_manifest_with_attribution` — engine id/variant/protocol recorded (R2).
- `test_halted_dispatch_records_disposition_note` — AE6: fallback disposition visible in the manifest.
- `test_satisfy_gate_refuses_claimed_only_manifest` — AE1 gate half: claimed-`verified` without adjudication raises `DispatchError` (R11).
- `test_adjudicated_refuted_counts_as_parroting` — AE1 taxonomy half, through the real dispatch+adjudicate path.

### U4. Completeness persistence for spec-driven runs — `manifest_store.py` CLI + `completeness_gate.py` + `/work`

**Goal:** `record-completeness --spec <spec.json> --results <results.json>` derives per-unit
`Contract` via `completeness_gate.Contract.from_unit`, diffs against produced results, and persists
one `output_completeness` subrecord per delegated unit (KTD7 — driver-materialized). Rename
`check_manifest` → `check_required_keys` (KTD6). `plugins/saga/skills/work/SKILL.md` gains the
post-run persistence step for cc-workflows and team-execution runs.

**Requirements:** R3, R10, R13.

**Approach:** A missing manifest is a `missing-output` trip **only** for a required, non-skipped,
contract-bearing unit (`Contract.expects_output == True`) — a prose/side-effect-only leaf is never
tripped (R10/AE3), matching `Contract.derive()`'s existing semantics at `completeness_gate.py:50-62`.
The gate consumes the persisted subrecord where present instead of re-deriving (R13); `classify()`
remains the single omission-semantics oracle.

**Test scenarios** (`tests/test_manifest_store.py` + `tests/test_completeness_gate.py`):
- `test_completeness_contract_bearing_leaf_missing_manifest_trips` / `test_completeness_contract_bearing_exempts_contract_less_leaf` — AE3 both halves (both names match the issue AC selector `-k completeness_contract_bearing`).
- `test_record_completeness_persists_declared_vs_produced_diff` — declared keys/counts vs produced, shortfall named.
- `test_check_required_keys_rename_preserves_classify_behavior` — the four canonical omission fixtures (`completeness_gate.py::self_test`) still pass.

### U5. Team-execution worker manifests — references + SKILL wiring (product surface, not this build's backend)

**Goal:** Team-execution workers (Claude agents — the only kind that exist until #283's U12 wrapper
lands) emit a manifest at worker exit via the `manifest_store` CLI. A new reference section (either in
`plugins/team-execution/skills/team-execution/references/validator-evidence-state.md` or a sibling
`worker-manifest.md`) defines the worker-exit contract; `plugins/team-execution/skills/team-execution/SKILL.md`
points at it.

**Requirements:** R2 (worker attribution), R3 (declared-vs-produced for workers), R21.

**Approach:** Complements — never duplicates — validator-evidence-state: validators keep their
repo-local per-run evidence JSON; the manifest is the cross-worktree envelope that outlives the run.
Evidence-only: the contract text repeats that a manifest grants no privilege and holds no verdict.

**Test scenarios:**
- `tests/test_provenance_manifest.py::test_team_execution_attribution_kind` — worker-kind attribution validates (R2).
- Test expectation for the reference/SKILL prose itself: none — documentation contract; behavior is exercised through U2's store tests and the U7 matrix guard.

### U6. Advisory consumers — `plugins/saga/scripts/manifest_reader.py` + three skill wirings

**Goal:** A reader (KTD8) reporting parroting count (R7), disposition rate (R18), and the
adjudicated-`verified` : `inferred`/`not-checked` ratio (R16), human and `--json` output. Skill
wiring: `plugins/saga/skills/code-review/SKILL.md` validator pass skips re-verifying
adjudicated-`verified` claims whose adjudication is attested and spends budget on
`not-checked`/`inferred` (R15/AE5); `plugins/saga/skills/qa/SKILL.md` consumes the ratio as the
confidence input it currently disclaims (:49-58); `plugins/saga/skills/retro/SKILL.md` invokes
`manifest_reader.py` beside `override_rate_reader.py` (:188).

**Requirements:** R7, R8, R12, R15, R16, R18.

**Test scenarios** (`tests/test_manifest_reader.py`):
- `test_reader_counts_parroting_only_on_refuted_unsupported` — issue AC selector `parroting_taxonomy` at the reader level.
- `test_reader_disposition_rate_over_mixed_manifests` — R18 tally mirrors `override_rate_reader` semantics.
- `test_reader_advisory_never_blocks_empty_tree_exits_zero` — no manifests → informative empty report, exit 0 (R8/R12; issue AC selector `advisory_never_blocks`).
- `test_reader_verified_ratio` — R16 ratio arithmetic.

### U7. Contract documentation + producer/consumer matrix + orphan-field guard

**Goal:** `plugins/saga/references/saga-spec.md` gains the manifest contract section: envelope/
subrecord field reference and the R17 matrix — per field: producer, reader, live-or-scheduled. A guard
test enforces "no manifest field without a live-or-scheduled reader."

**Requirements:** R17.

**Approach:** The matrix marks the two still-scheduled readers honestly: S-4's
*team-execution-external-engine* leg (waits on #283 U12) — everything else is live. The guard test
parses the matrix table from `saga-spec.md` and diffs field names against `provenance_manifest.py`'s
dataclass fields, in the same spirit as the existing drift-guard tests.

**Test scenarios** (`tests/test_manifest_consumer_matrix.py`):
- `test_manifest_no_orphan_field` — every schema field appears in the matrix with a named reader (issue AC selector `manifest_no_orphan_field`).
- `test_matrix_has_no_phantom_fields` — the matrix names no field absent from the schema (drift both directions).

### U8. Release surfaces + journal + issue correction

**Goal:** Same-PR release discipline (CLAUDE.md workflow step 6): bump
`plugins/saga/.claude-plugin/plugin.json` and `plugins/team-execution/.claude-plugin/plugin.json`
minor versions, mirror in `.claude-plugin/marketplace.json`, CHANGELOG entries for both plugins,
version-drift guard tests green. `docs/engineering-journal/DECISIONS.md` entries mirroring KTD1-KTD9
(rationale + rejected alternatives + revisit-when). Post the drift-report correction comment on #285.

**Requirements:** repo release discipline; D6 note (references `#external-engines-never-gatekeepers`,
does not restate it).

**Test expectation:** none beyond the existing metadata drift guards — release-surface unit.

## Per-unit tier proposal

| Unit | Label | Tier | Rationale |
|---|---|---|---|
| U0 | fable/xhigh validator enablement | inline (no subagent) — **DONE 2026-07-01** | Two-tuple-entry change (plus ordering guard); landed pre-`/work` |
| U1 | schema module | **fable / xhigh** (was opus/high; KTD10) | Load-bearing contract design; everything downstream consumes it |
| U2 | manifest store | sonnet / medium | Mechanical, patterned on `outcome_store.py` |
| U3 | engine producer + gate | **fable / xhigh** (was opus/high; KTD10) | Gate semantics (R11) are adversarial-confidence territory |
| U4 | completeness persistence | sonnet / medium | Persisting an existing oracle's output; rename is mechanical |
| U5 | team-exec contract docs | sonnet / medium | Documentation contract + one validation hook |
| U6 | reader + skill wiring | sonnet / medium | Reader patterned on `override_rate_reader.py`; prose wiring |
| U7 | matrix + guard test | sonnet / medium | Table + parser test |
| U8 | release surfaces | sonnet / low | Mechanical metadata |

The `sonnet` alias resolves to Claude Sonnet 5 in this harness (KTD10) — the sonnet-tier units get
the Claude 5 upgrade with no spec change. Adversarial verify panels (n=3, majority, same tier as the
unit) run on U1 and U3 — backend is confirmed `cc-workflows-ultracode` (see Execution backend
section).

## Scope Boundaries

**Out of scope (true non-goals):**
- A manifest store UI/browser/query surface — files on the existing common-dir pattern only.
- Inline-Claude self-attestation (D5) — Claude adjudicates and attests adjudications, never its own primary work.
- Any gate of R11's own (R12) — evidence to existing gates only.
- Backfill of historical outputs — manifests begin at adoption.
- Mutating external workers — wait on the read-only sandbox (ideation R14); external engines stay evidence-only (R21).
- Signing/cryptographic attestation (in-toto style) — no verifier ecosystem to consume it (KTD3).

**Deferred follow-up work (distinct from non-goals):**
- R14's team-execution-external-engine consumer leg — blocked on #283's deferred U12 wrapper contract; the matrix (U7) marks it scheduled.
- Schema alignment with an external vocabulary — revisit if a manifest ever needs an out-of-marketplace consumer (KTD3 revisit-when).
- `/investigate` as an advisory consumer (A4 lists it) — v1 wires the three consumers with named read points (R15/R16); `/investigate` reads nothing manifest-specific yet and is deferred until it has a concrete read.

## Risk analysis

- **Schema churn.** First typed contract for a broad surface; mitigated by the `saga.manifest.v1` version key (KTD3) and the orphan-field guard keeping the schema minimal (R17).
- **False completeness trips.** Mitigated by R10's contract-bearing scoping riding on `Contract.derive()`'s shipped semantics, with both AE3 halves as tests (U4).
- **Adjudication cost creep.** Mitigated by KTD9 tier sizing — lightweight manifests carry no subrecords; adjudication only where a gate or contract demands it (R9), which saga already performs as prose today.
- **Consumer-matrix drift.** Mitigated structurally by the two-direction guard test (U7).
- **`AdvisoryEvidence` surface breakage.** U3 keeps the dataclass fields; the provenance dict becomes a rendered view of the typed manifest, so existing tests keep passing until deliberately migrated.

## Verification (mirrors issue #285 acceptance criteria)

```bash
uv run pytest tests/ -k manifest_envelope
uv run pytest tests/ -k parroting_taxonomy
uv run pytest tests/ -k completeness_contract_bearing
uv run pytest tests/ -k advisory_never_blocks
uv run pytest tests/ -k manifest_no_orphan_field
# Full local gate (CI mirror — includes ruff format --check)
uv run pytest -q && uv run ruff format --check . && uv run ruff check . \
  && uv run mypy plugins/ && uv run bandit -r plugins/ -q
```

All five `-k` selectors match test names defined in U1-U7 above.
