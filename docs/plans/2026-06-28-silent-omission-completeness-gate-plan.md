---
title: Silent-Omission Completeness Gate — Implementation Plan
type: feat
status: active
date: 2026-06-28
origin: docs/brainstorms/2026-06-27-silent-omission-completeness-gate-requirements.md
---

# Silent-Omission Completeness Gate — Implementation Plan

## Summary

Add a required completeness gate to the saga execution engine that turns its #1 recorded failure — a
leaf agent that silently produces nothing — into a loud, typed, named failure. The gate is *one
comparison at two granularities* (mechanical presence/count detector + opportunistic manifest diff),
and it ships with an on-demand `--self-test`. This plan is built to be implemented by **agy** (Gemini)
as a delegated coder under Claude verification, so every unit carries an exact write-set that doubles
as the delegate's allow-set.

## Problem Frame

The engine's dominant failure is omission, not incorrectness: in run `wf_4a5f04b6`, 16/19 fan-out agents
finished without emitting their structured output (budget exhaustion), and nothing detected it
(`docs/engineering-journal/LEARNINGS.md:603`/`:607`). The two paths `/plan` emits both swallow it — the
emitted `.workflow.js` passes the resulting `null` to dependents with no null-check
(`plugins/saga/scripts/execution_spec.py:591-628`), and the team-execution path leaves a silently-absent
evidence record. A correctness gate cannot catch this: refute-N asks "is what's here right?" but there is
nothing on the page to refute. The wrong thing is the absence.

## Requirements

Carried forward verbatim from the requirements doc (the reviewer's and `/work`'s checklist). IDs are stable.

**Mechanical detection (always-on, every leaf)**

R1. After every leaf returns, the gate inspects the result before any dependent consumes it; for an agent
expected to emit structured output, a `null`/absent/missing-emit result is a trip (`missing-output`),
never an empty-but-valid output.

R2. A structurally truncated output is a trip (`malformed-output`), not parsed as complete.

R3. When a leaf declares a count (v1: a fan-out unit's enumerated `Unit.targets`) and produces fewer, the
shortfall is a trip (`missing-output`).

R4. On any trip the gate fails loud with a typed, named failure and never releases the partial *return
envelope* downstream (halt-not-degrade). On-disk side-effects are out of v1 scope (deferred R14).

**Manifest completeness (opportunistic)**

R5. The contract already exists as `Unit.returns` (`plugins/saga/scripts/execution_spec.py:180`) — required
structured-output keys, rendered into the prompt but never diffed against emission. v1 enforces it.

R6. Where `returns` is non-empty, the gate diffs declared required keys against emitted keys and trips
(`missing-output`) on any absent declared key, naming the omission.

R7. The manifest check is opportunistic — a leaf with no contract gets the mechanical detector only.

**Typed failures and bounded iteration**

R8. Every trip carries a typed class. v1 wires `missing-output`, `malformed-output`, `verifier-disagreement`;
the enum is extensible (future `tool-denial` / `stale-context` / `merge-conflict` slot in without rework).

R9. The emitted-workflow path gains the iteration cap it lacks; reaching it emits `verifier-disagreement`
instead of silently exiting the loop.

R10. The cap is overridable for iterate-to-consensus, but an override still terminates (raises the bound or
hands off) — never removes it. An uncapped loop is prohibited.

**Coverage**

R11. Primary v1 seam: the emitted `.workflow.js` path — every emitted agent result is gate-checked before a
dependent reads it (synchronous model). The R9 cap applies here.

R12. The team-execution path gains an evidence-absence check at validator/leaf process exit: a *required,
non-skipped* validator/leaf whose evidence record was never written is a trip; `skipped-by-config` is not.

**Self-test**

R13. `--self-test` plants one known omission, asserts the gate trips, reports, and exits — out-of-band, on
demand, never on a schedule.

## Key Technical Decisions

KTD1 — **Enforcement lives in emitted JS; semantics live in a Python oracle.** The emitted `.workflow.js`
runs in the Workflow JS runtime and cannot call Python at execution time, so the runtime guards must be
*emitted JS* injected after each `agent()` call. `completeness_gate.py` is the Python oracle (enum + pure
check predicates + `--self-test`) that unit-tests pin; the emitter ports the same semantics into one
`__gate` JS helper — which `completeness_gate.py` **owns as a string constant the emitter imports**, so the JS
guard is authored in exactly one place (shrinking the oracle↔guard drift surface to a single faithful port).
*Residual (accepted):* executable parity between the Python `classify()` and the emitted JS `__gate` cannot be
asserted without a Node runtime — deferred (see U2 test scenarios); the single-sourced helper is the v1
mitigation. *Rejected:* calling Python at runtime (impossible — JS runtime); duplicating inline checks at every
call site (drift-prone, unreadable).

KTD2 — **One vocabulary across three enforcement sites.** The mechanical + manifest checks (R1–R7) are
emitted-JS guards; R12 is a pure-prose team-execution protocol (that plugin has zero Python). All three
reference the same `FailureClass` names. The team-exec side cannot import the Python enum, so it *mirrors*
the class names as documented constants — an accepted, unavoidable duplication (prose cannot import).

KTD3 — **Self-test = oracle fires on planted fixtures, in-process.** `--self-test` constructs canonical
omission fixtures (null result; truncated string; short fan-out count; missing required key) and asserts
`classify()` trips each with the right class; exit 0 + "caught" on success. It spawns no agent and touches
no workspace (R13). The emitted-JS guard's firing is proven *separately* by an emitter injection test —
the JS guard cannot run outside the Workflow runtime.

KTD4 — **missing/malformed-output → halt typed; retry budget defaults to 0.** v1 trips and **halts loud with
the typed class**; the retry-budget field is designed in (per-unit, always terminating) but defaults to 0.
*Rationale:* no acceptance example requires a working retry, the loud typed halt *is* the requirement, and
the dominant cause (over-read budget exhaustion) is structural — an unchanged re-run would not fix it, only
burn budget. Bounded retry is a clean fast-follow.

KTD5 — **Iterate-to-consensus override = two fields on `Verify`.** Extend the `Verify` dataclass with
`iterate_to_consensus: bool = False` and `max_iterations: int = 3` (the default mirrors team-execution's
existing prose cap at `consensus-protocol.md:17`). Default: a refuted panel → `verifier-disagreement` halt
(today it `log()`s and proceeds — the R4 fix). Override: re-run→re-verify up to `max_iterations`, then halt.
`validate()` rejects `max_iterations < 1` (uncapped prohibited, R10). An absent `verify` round-trips
unchanged (existing specs untouched).

KTD6 — **Delegated build: plain `/agy:delegate` + post-hoc verify + review-and-fix loop.** (Operator decision
2026-06-29, superseding the clone-jail design — too many moving parts for this harness; deferred as a possible
later optimization, and properly the job of independent agents with their own workspace.) Treat agy as a
*junior engineer*: it drafts, Claude reviews and FIXES, Claude is sole committer. Per unit: hand the unit's
write-set as a tight in-prompt allow-set to plain `/agy:delegate --model flash <task>` (NO `--background` — it
detaches agy to a 0-output context; NO hand-rolled `agy` shell call); then Claude verifies post-hoc against the
REAL tree — `git status` changed-paths ⊆ allow-set (quarantine strays), the FULL gate (`pytest` + `ruff
format --check` + `ruff check` + `mypy`), and for any unit where agy wrote its own tests **mutation-proof**
them (break the behavior, the test must go red — guards F4 test-gaming). Claude then fixes whatever is wrong
and commits. **Scrap threshold:** if a draft needs more fixing than writing, stop fixing — re-delegate once at
Pro (KTD7) or write it directly; never polish a fundamentally wrong draft. A broken *uncommitted* tree is safe
(Claude is sole committer); nothing reaches `origin` until the gate is green.

KTD7 — **Model ladder: Flash High → (Claude fix | Pro retry) on fail.** Start each unit on Gemini 3.5 Flash
(High). On a failed/insufficient draft, default recovery is **Claude fixes it** (the review-and-fix loop, KTD6);
re-delegating the unit once at 3.1 Pro (High) is the alternative when the draft is wrong enough to scrap but
still worth a second agy attempt (keeps n=2 comparable to n=1). Either way Claude owns the final diff.

## High-Level Technical Design

One vocabulary, three enforcement sites:

```
                      completeness_gate.py  (Python ORACLE — the single source of semantics)
                      ┌──────────────────────────────────────────────────────────┐
                      │ FailureClass enum: missing-output | malformed-output |    │
                      │                    verifier-disagreement  (extensible)    │
                      │ check_presence / check_truncation / check_fanout_count /  │
                      │ check_manifest  → classify(result, contract) -> Failure?  │
                      │ --self-test  (plants fixtures, asserts each trips)        │
                      └───────────────┬──────────────────────────┬───────────────┘
            unit-tested + self-tested │   ports same semantics   │  mirrors class NAMES (prose; cannot import)
                                      ▼                          ▼
        SITE 1: emitted .workflow.js              SITE 2: team-execution (prose protocol)
        execution_spec.py emits one __gate(...)   validator-execution-order.md / SKILL.md B7:
        helper + a guard call AFTER every         a required, non-skipped validator/leaf whose
        agent() → HALT (throw typed) instead of   evidence record is absent at process exit
        passing null/partial downstream.          → missing-output trip (skipped-by-config: no trip).
        (R1–R4, R6, R11) + verify-cap (R9/R10)    (R12)
```

Site 1 is where the runtime null/truncation/count/key enforcement lives (emitted JS, because the workflow
runs JS). Site 2 is the team-execution model (no return value to inspect; the artifact's *absence* is the
signal). The oracle (Python) is what makes Site 1's semantics testable offline and is the body of the
self-test.

## Implementation Units

Dependency-ordered, each independently landable. The **write-set is the agy allow-set** — agy may read the
whole repo but write only these paths; anything else is a `PLAN_GAP` escalation, never a silent edit.

### U1. Completeness-gate oracle module + `--self-test`

**Goal:** The semantic single-source — `FailureClass` enum, a `Failure` record (class + message + unit_id +
detail), the pure check predicates (`check_presence`, `check_truncation`, `check_fanout_count`,
`check_manifest`), a top-level `classify(result, *, contract)`, and a `--self-test` CLI. No I/O at import
(house pattern: mirrors `saga.py` / `execution_spec.py`).

**Write-set:** `plugins/saga/scripts/completeness_gate.py` (new) · `tests/test_completeness_gate.py` (new).

**Approach:** `expects_output` is derived from the contract (a schema-bearing / non-empty-`returns` /
enumerated-`targets` leaf expects output; a prose/side-effect leaf does not — R7/AE9). Each predicate returns
`Failure | None`. `--self-test` builds the four canonical omission fixtures, asserts `classify` trips each
with the expected class, prints `caught`/`UNCAUGHT`, exits 0/1.

**Test scenarios** (`tests/test_completeness_gate.py`): null-when-expected → `missing-output`; legitimate
empty (no contract) → no trip (R7/AE9); truncated → `malformed-output` (R2); fan-out 12-declared/9-produced
→ `missing-output` (R3/AE3); `returns` missing `rollback_sql` → `missing-output` naming the key (R6/AE4);
all keys present → pass; enum extensibility (a new class added without breaking dispatch, R8); `--self-test`
via subprocess exits 0 and prints `caught` (R13/AE7).

**Depends on:** none.

### U2. Emitted-workflow guards (the null/truncation/count/manifest enforcement)

**Goal:** Make the emitted `.workflow.js` halt on an omission instead of passing `null` downstream. Emit one
`__gate(result, opts)` helper (imported from `completeness_gate.py` per KTD1) into the workflow preamble and a
guard call after **every emitted UNIT-result `agent()` site** — the singleton, each var of a `parallel([...])`
layer, and fan-out — that throws a typed error rather than letting a dependent consume a partial/empty envelope.
The verify-panel's verifier `agent()` calls (`_emit_verify_panel`) are **out of U2's scope**: their null is
already tolerated by the `v && v.refuted` reconciliation, and panel-level disagreement is U3's domain.

**Write-set:** `plugins/saga/scripts/execution_spec.py` · `tests/test_workflow_emitter.py`.

**Approach:** Extend `emit_workflow_script` (and `_emit_thunk`) to inject `__gate` once in the preamble and a
`__gate(<var>, {returns, targets, expectsOutput})` call after each unit-result var is bound — for the singleton
layer right after `const <var> = await agent(...)`, and for a `parallel([...])` layer after the
`const [<v1>, <v2>, …] = await parallel([...])` destructure, one guard per var — before any dependent reads it.
The fan-out reconcile guard (R3) and the manifest-key guard (R6) emit only where `targets`/`returns` are present. The acceptance criterion names `tests/test_execution_spec.py -k emitted_null_check`; this plan
places it in the existing `tests/test_workflow_emitter.py` (convention) — the `-k emitted_null_check`
selector still resolves.

**Test scenarios** (`tests/test_workflow_emitter.py`): emitted JS contains the `__gate` helper; a guard call
is emitted after every **unit-result** `agent()` site (`emitted_null_check`), and **not** after the verify-panel's
verifier agents; the guard *halts* (the emitted code throws, not pass-through) on null; fan-out units emit the
count-reconcile guard; only `returns`-bearing units emit the manifest guard; a no-contract unit emits the
presence guard only. *(Parity residual: a Node-executed test that runs the emitted `__gate` against U1's
canonical fixtures and asserts class-match with `classify()` would close the oracle↔JS gap — deferred from v1
as it reintroduces a Node dependency; KTD1's single-sourced helper is the v1 mitigation.)*

**Depends on:** U1.

### U3. Verify-panel iteration cap + typed `verifier-disagreement`

**Goal:** A refuted verify panel must **halt** (`verifier-disagreement`), not `log()`-and-proceed as it does
today (`execution_spec.py:514-518`) — the R4 fix on the verify path. Add the bounded iterate-to-consensus
override (KTD5).

**Write-set:** `plugins/saga/scripts/execution_spec.py` · `tests/test_workflow_emitter.py`.

**Approach:** Extend the `Verify` dataclass with `iterate_to_consensus` + `max_iterations` (+ `from_dict` /
`to_dict` / `validate`, rejecting `max_iterations < 1`). Rework `_emit_verify_panel` so a refuted result
emits a typed halt by default, or — when `iterate_to_consensus` — a bounded re-run loop that halts with
`verifier-disagreement` at `max_iterations`.

**Test scenarios** (`tests/test_workflow_emitter.py`): refuted panel emits a `verifier-disagreement` halt (not
a `log`-and-continue, R9/AE6); `iterate_to_consensus` emits a loop bounded by `max_iterations` (R10/AE6);
`max_iterations < 1` → `SpecError` at `validate()` (uncapped prohibited); an absent `verify` round-trips
unchanged (existing specs untouched).

**Depends on:** U1, U2 (same file, sequential).

### U4. Team-execution evidence-absence protocol (prose)

**Goal:** Specify, in the team-execution protocol docs, the required-evidence-absence check at process exit:
a required, non-skipped validator/leaf whose evidence record was never written is a `missing-output` trip;
a `skipped-by-config` one is not (R12/AE8). team-execution has no Python — this is a prose-protocol change.

**Write-set:** `plugins/team-execution/skills/team-execution/references/validator-execution-order.md` (+
`validator-evidence-state.md` and SKILL.md Step B7 as needed) · `tests/test_team_execution_plugin.py`.

**Approach:** Add the exit-time check to the validator-execution-order protocol and the B7 completion step,
mirroring the `FailureClass` names from U1 as documented constants (KTD2). The test is a doc-contract
assertion (like the existing `test_skill_documents_validator_state_and_automation_gates`).

**Test scenarios** (`tests/test_team_execution_plugin.py`): the SKILL/reference docs contain the
required-evidence-absence gate language and the explicit `skipped-by-config` exception.

**Depends on:** U1 (vocabulary).

### U5. Release surfaces + version-pin tests

**Goal:** Ship the capability across the release triad with the version-pin metadata tests **in the write-set
this time** — the explicit fix for the #275 U6 under-scope that broke CI on `test_saga_plugin.py:48` /
`test_team_execution_plugin.py:60`.

**Write-set:** `plugins/saga/.claude-plugin/plugin.json` (0.39.0→0.40.0) · `plugins/team-execution/.claude-plugin/plugin.json`
(2.3.0→2.4.0) · `plugins/saga/CHANGELOG.md` · `plugins/team-execution/CHANGELOG.md` ·
`.claude-plugin/marketplace.json` (the saga + team-execution *entries*, not the top-level 3.0.0) ·
`tests/test_saga_plugin.py` · `tests/test_team_execution_plugin.py`.

**Approach:** New capability → saga **minor** bump; R12 protocol change → team-execution **minor** bump.
Update both CHANGELOGs, the two marketplace entries (mind the array-edit footgun — validate with
`python3 -m json.tool` after), and the two version-pin assertions.

**Test scenarios:** `test_saga_plugin.py` pins `0.40.0`; `test_team_execution_plugin.py` pins `2.4.0`; the
existing `test_release_triad.py` (plugin.json ↔ marketplace ↔ CHANGELOG lockstep) stays green.

**Depends on:** U1, U2, U3, U4.

## Delegated Build Protocol (the agy harness for `/work`)

The operational layer `/work` runs. This is **n=2** of the delegation experiment — record the result in
`docs/external-agent-delegation/`'s README matrix. **Method (2026-06-29): plain `/agy:delegate` + Claude
review-and-fix, NOT the blueprint's clone-jail** (pulled — see KTD6); the blueprint's clone-jail topology is
retained there as a deferred optimization for the independent-agent / own-workspace case. After each unit, fold
what agy got wrong into the NEXT unit's prompt + the blueprint — refining the instructions IS this experiment's
output.

- **Containment (KTD6):** none beyond the harness. Run plain `/agy:delegate --model flash <task>` against the
  REAL working tree; the boundary is the in-prompt allow-set + Claude's post-hoc verification + sole-committer
  (an uncommitted tree is safe). NO clone-jail, NO `git` shim, NO `agy --sandbox`, NO hand-rolled `agy` shell
  call (operator-banned), NO `--background` (it detaches agy to a 0-output context and the runner spins).
- **Per-unit packet:** the unit's write-set as a CLOSED allow-set + pre-resolved read-context (the target paths
  are handed over so agy need not *search to find them*; it MAY still read/search the repo broadly for correctness
  — read broad, write narrow — but writes only the allow-set and escalates `PLAN_GAP` for any path it believes
  must change outside it) + the exact VERIFY commands + the `PLAN_GAP` / `TEST-CONFLICT` / `PATH-MISSING`
  escalation channels. Launch FOREGROUND via `/agy:delegate` (it runs `agy:runner` as a session teammate that
  blocks to completion and idle-notifies; do NOT `--background`).
- **Validation floor (non-negotiable, every unit):** `git status --short` — changed/untracked paths ⊆ the
  allow-set; **quarantine** strays (surface, do not auto-revert); run the **FULL** suite + `ruff format --check`
  + `ruff check` + `mypy` (never a file-local subset); **mutation-proof** any tests agy wrote (break the
  behavior, the test must go red — F4 guard); READ the diff (green ≠ correct). Claude fixes what's wrong and is
  **sole committer** — nothing reaches `origin` until the gate is green.
- **Model ladder (KTD7):** Flash High per unit; escalate that unit to Pro High on failure.

## Scope Boundaries

In scope: the two fan-out seams (emitted `.workflow.js`, team-execution); the three v1 failure classes; the
on-demand self-test.

Out of scope (deferred, with reason): generated-patch / command-input hostile validation (fast-follow with the
live R14 verify/review profile); a standing spike-calibration harness (S-6 ceremony, killed); backfilling
`returns` contracts; the unimplemented failure classes (`tool-denial` / `stale-context` / `merge-conflict` —
enum-extensible, not wired); changing team-execution's proceed-best-available cap; the **inline backend** (no
fan-out seam); on-disk side-effect containment (deferred R14 workspace isolation); a working bounded-retry
(KTD4 — field designed-in, defaults to halt).

## Risk Analysis & Mitigation

- **Oracle↔JS-helper drift (KTD1/KTD2).** Two implementations of "what is an omission." *Mitigation:* the JS
  helper is one small fixed function; the Python self-test pins semantics; an emitter test asserts the helper
  is injected + called after every agent. Accept the residual.
- **U4 is prose-only enforcement.** R12's only test is a doc-contract assertion — weaker than the JS path, and
  it relies on the team-execution skill *reading and obeying* the protocol. *Operator decision:* good enough to
  start; revisit if it fails in practice. Tracked as the known soft spot.
- **agy gaming the emitter tests (F4).** U2/U3 are exactly where a delegate could add a marker to make a
  cross-file assertion pass. *Mitigation:* mutation-proof every agy test; read the test diff.
- **agy wandering into the live engine (F1).** U2/U3 edit `execution_spec.py`, the engine this session runs on.
  *Mitigation:* post-hoc `git status` changed-paths ⊆ allow-set + FULL gate before commit; a broken *uncommitted*
  tree is harmless (Claude is sole committer, nothing reaches `origin` un-gated). If agy ever actually wanders
  here, *that's* the trigger to add isolation — not preemptively (clone-jail pulled, KTD6).

## Success Criteria

- A leaf that silently produces nothing surfaces as a loud, typed, named failure; no null/partial result
  reaches a dependent on the emitted path.
- `python3 plugins/saga/scripts/completeness_gate.py --self-test` exits 0 and reports the planted omission
  caught.
- Full gate green: `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/`.
- The delegated build completes with the validation floor intact (containment verified: changed paths ⊆ the
  per-unit allow-set; Claude sole committer; full gate green) and the n=2 result recorded in the delegation
  README matrix.
