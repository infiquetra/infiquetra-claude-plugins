---
title: Verify-Panel Robustness — Non-Applicable vs Failed Panel Members
type: fix
status: active
date: 2026-07-03
origin: docs/brainstorms/2026-06-28-verify-panel-robustness-requirements.md
---

# Verify-Panel Robustness — Non-Applicable vs Failed Panel Members

Issue: infiquetra/infiquetra-claude-plugins#293 (requirements-ready; doc-review verdict READY).

## Summary

Make the two panel surfaces honest about members that produce no verdict. Layer A: the cc-workflows
verify reconciliation records a runtime-missing verifier and recomputes the pass-rule threshold over
the members that reported, replacing today's silent uphold-bias. Layer B: a reviewer dimension whose
repo-state precondition is absent is excluded from the consensus average, replacing the fabricated
N/A→8.0 default. Static exclusion and runtime recompute stay on separate paths (the two-kinds
contract), and a panel where every member reports behaves exactly as today.

---

## Problem Frame

Grounded against the current tree (saga 0.49.2); the issue was grounded at 0.38.0 and four premises
have drifted. The plan honors the issue's requirements under the current code:

- **Three reconciliation sites, not one.** The `v && v.refuted` silent-null drop plus the fixed
  `⌈n/2⌉`-of-declared-n threshold is now emitted from three places:
  `_emit_thunk` (`plugins/saga/scripts/execution_spec.py:909-958`, iterate-to-consensus thunk in a
  parallel wave), `_emit_verify_loop_singleton` (`:979-1028`), and `_emit_verify_panel`
  (`:1031-1075`). All three must carry the fix.
- **The consumer is a throw, not a `log()`.** Since #277 (saga 0.40.0, commit b09ad50), a refuted
  one-shot panel throws `verifier-disagreement: …` (`execution_spec.py:1069-1074`); the iterate
  loops retry, then throw at `max_iterations`. The `_emit_verify_panel` docstring (`:1041-1042`)
  still claims a `log()` consumer — stale. The throw-message prefix is pinned by existing tests
  (`tests/test_workflow_emitter.py:1522,1550,1624` assert the substring's presence/absence) and by
  the `FailureClass.VERIFIER_DISAGREEMENT` vocabulary (`completeness_gate.py:22` — an extensible
  failure-class set whose string must stay aligned; note `classify()` at `:201-219` does not parse
  throw messages today).
- **`team_emitter.py` has no verify reconciliation** — Layer A is `execution_spec.py` only.
- **`tests/test_team_execution_consensus.py` does not exist** — it is a new file.

The two defects themselves are unchanged from the issue: a null verifier is counted as "did not
refute" while the threshold stays at `⌈n/2⌉` of the declared n (masking genuine majority
refutations — the unsafe direction), and `architecture-reviewer.md:82` scores a fabricated N/A→8.0
into a five-dimension average (`:112`) that feeds the unanimous-ACCEPT gate
(`consensus-protocol.md:69`).

---

## Requirements

Issue R1–R11 are adopted verbatim (stable IDs preserved); R12–R15 are plan additions from the
premise drift above.

- R1. A panel member that produces no verdict is recorded with its cause —
  `static-non-applicable` or `runtime-failure` — never dropped without a record.
- R2. Static non-applicability is resolved at composition time: excluded from the denominator
  before dispatch; never enters the floor or escalation.
- R3. Runtime failure is resolved at reconciliation time: the pass-rule threshold recomputes over
  the `(n−k)` reporters — `majority` ⇒ `⌈(n−k)/2⌉`, `unanimous` ⇒ all `(n−k)` — subject to a
  minimum-quorum floor.
- R4. Below the floor, the result is marked UNDER-STRENGTH in the existing consumer surfaces; no
  re-spawn / operator-escalation / `inconclusive` state in v1.
- R5. The reconciliation records each runtime-missing verifier and states which reported, which
  were missing and why, and the `(n−k)` the verdict was computed over.
- R6. Budget exhaustion is already handled (`BUDGET_RIDER`, `execution_spec.py:122-129`); the
  residue covered is a verifier that dies without emitting (terminal error → `null`). Hang
  liveness: resolved as KTD2 — no verifier-level timeout in v1.
- R7. A reviewer dimension whose repo-state precondition is absent is excluded from the overall
  computation (overall = mean of applicable dimensions), replacing the N/A→8.0 default.
- R8. Exclusion is dimension-granular; a reviewer whose entire lens is non-applicable is excluded
  whole from the consensus denominator, with a logged cause.
- R9. Static exclusion and runtime failure carry distinct causes and run on distinct paths; never
  conflated.
- R10. A panel where every member applies and reports behaves exactly as today: same verdicts,
  same `n` / `pass_rule` / `VERIFY_N_CAP` / same-tier rule / cost levers.
- R11. Every new behavior attaches to an existing surface with a real producer and consumer (the
  reconciliation + its throw/log; the dimension average) — no free-floating concept
  (`docs/engineering-journal/LEARNINGS.md` dead-wiring rule).
- R12. All three emission sites (`_emit_thunk`, `_emit_verify_loop_singleton`,
  `_emit_verify_panel`) carry the identical recompute, emitted from one shared helper.
- R13. The emitted throw keeps the exact `verifier-disagreement:` prefix — pinned by existing
  test assertions (`tests/test_workflow_emitter.py:1522,1550,1624`) and kept string-aligned with
  `FailureClass.VERIFIER_DISAGREEMENT` (`completeness_gate.py:22`); detail is appended after the
  prefix, never restructured. The emitted script must also never contain the banned phrase
  `review before relying on it` (asserted absent at `tests/test_workflow_emitter.py:1526`).
- R14. The stale `_emit_verify_panel` docstring and the verify block in
  `plugins/saga/references/execution-spec.md:44-61` are updated to the actual throw/accept
  contract, including the missing-verdict rules and the Q1 residue.
- R15. Release surfaces ship in the same PR: both `plugin.json` versions, `marketplace.json`,
  both CHANGELOGs, and the version drift-guard tests (`tests/test_saga_plugin.py:48`,
  `tests/test_team_execution_plugin.py:64`).

---

## Key Technical Decisions

- KTD1 — "Reported" means the harness returned a non-null verdict: the workflow harness resolves a
  skipped or terminally-errored agent to `null` (harness contract; the shipped `v &&` guard in all
  three reconciliation sites is the in-repo acknowledgment that a verdict slot can be null), and
  that is the only machine-detectable absence in the emitted script. A non-null but malformed
  verdict (no `.refuted` array) keeps today's did-not-refute handling — malformed-output is
  already a separate `completeness_gate.py` failure class, and folding it into "missing" would
  conflate two diagnoses.

- KTD2 — Q1 resolved: no verifier-level timeout in v1: workflow scripts cannot express timers —
  `Date.now()` / `new Date()` throw by design (resume-safety) and `agent()` exposes no timeout
  option — so a hung verifier is unreachable from the emitted script. v1 relies on
  terminal-error → `null`; a hang blocks the panel's `parallel([...])` and remains a
  harness/operator liveness concern (documented as a known residue in `execution-spec.md`).
  Rejected alternative: a `Promise.race` sleep — no timer primitive exists in the script sandbox.

- KTD3 — Quorum floor = `⌈n/2⌉` of the declared n, baked as a literal per panel: scales with n
  (n=3→2, n=7→4, n=1→1), and "a majority of the declared panel reported" is the natural meaning of
  full-strength. The recomputed threshold is `max(1, ⌈reported/2⌉)` (majority) /
  `max(1, reported)` (unanimous) — the `max(1, …)` guard makes the all-missing case
  (`reported = 0`) deterministically not-refuted instead of vacuously refuted
  (`0 >= ⌈0/2⌉ = 0` would be true).

- KTD4 — Skeptical asymmetry: a refutation over reporters always acts (throws / retries), even
  under-strength — the throw message then carries the UNDER-STRENGTH note; the floor annotates
  only the accept path. Rationale: the defect being fixed is masked refutation; suppressing a
  refutation because the quorum is small would reintroduce the uphold bias in a new form.

- KTD5 — One shared reconciliation-emission helper for all three sites: three hand-maintained
  copies is the same drift risk `_verifier_agent_opts` (`execution_spec.py:887-906`) was created
  to kill for verifier opts; the helper takes the target indentation and the panel, and emits
  identical logic everywhere.

- KTD6 — Layer A implements only the runtime path; Layer B only the static path: cc-workflows
  verifiers are homogeneous skeptics with no per-member precondition (static exclusion there is
  just authoring a smaller `n`); team-execution dimensions are precondition-bearing but reconciled
  by prompt, not generated code. The two-kinds contract is shared in the docs; the arithmetic is
  per-surface.

- KTD7 — Layer B ships as a prompt-contract change pinned by drift-guard tests: the reviewer
  markdown *is* the executable spec for the agent; `tests/test_team_execution_consensus.py`
  asserts the contract text (exclusion present, fabricated default absent) following the
  `tests/test_team_execution_plugin.py` idiom, so a future edit cannot silently reintroduce the
  8.0 default.

- KTD8 — Version bumps are minor, not patch: saga 0.49.2 → 0.50.0 (emitted-script behavior
  changes), team-execution 2.8.0 → 2.9.0 (reviewer scoring contract changes).

---

## High-Level Technical Design

The generated reconciliation changes from (majority n=3 shown; names use the unit var prefix):

```js
// today
const U_refute_count = U_verdicts.filter((v) => v && v.refuted && v.refuted.length > 0).length
const U_refuted = U_refute_count >= 2  // majority
```

to:

```js
// after — recompute over reporters (R3), record the missing (R1/R5), floor as marker (R4)
const U_reported = U_verdicts.filter((v) => v != null)
const U_missing_idx = U_verdicts.map((v, i) => (v == null ? i + 1 : null)).filter((i) => i != null)
const U_refute_count = U_reported.filter((v) => v.refuted && v.refuted.length > 0).length
const U_threshold = Math.max(1, Math.ceil(U_reported.length / 2))  // majority over reporters
const U_refuted = U_refute_count >= U_threshold
if (U_missing_idx.length > 0) {
  log(`verify panel over U2: ${U_missing_idx.length}/3 verifier(s) missing (runtime-failure: #${U_missing_idx.join(", #")}); verdict computed over ${U_reported.length}/3` +
      (U_reported.length < 2 ? " — UNDER-STRENGTH (quorum floor 2)" : ""))
}
```

`unanimous` emits `Math.max(1, U_reported.length)` as the threshold. The floor literal (`2` above)
is `⌈n/2⌉` baked at emit time. The throw becomes:

```js
throw new Error(`verifier-disagreement: Unit U2 refuted by ${U_refute_count}/${U_reported.length} reporting verifiers (${U_missing_idx.length} missing)`)
```

— prefix intact (R13), detail appended. With all n reporting: `reported = n`, threshold
`= ⌈n/2⌉` (majority) / `n` (unanimous), no log line — byte-equivalent behavior to today (R10).

Layer B replaces `architecture-reviewer.md:82`'s "score … as N/A (8.0 default)" with exclusion:
the dimension row renders `N/A — excluded (precondition absent: no architecture docs)`, the
overall is the mean of the scored dimensions, and `consensus-protocol.md` defines the
applicable-dimensions denominator for the ≥9.0 / no-dimension-<7.0 gate plus the whole-lens
exclusion rule (R8) and the static-skip-is-not-a-failure boundary (AE3).

---

## Implementation Units

### U1. Consolidate the three reconciliation emissions into one helper

Behavior-preserving refactor so the semantic change in U2 lands in exactly one place.

**Goal:** a `_emit_panel_reconciliation(lines, unit, verdicts_var, result_var, indent)` helper
emits the verdict-count/threshold/consumer block for all three sites; emitted script text is
unchanged.

**Requirements:** R12 (structure half); enables R10.

**Dependencies:** none.

**Files:** `plugins/saga/scripts/execution_spec.py` (extract from `_emit_thunk:935-955`,
`_emit_verify_loop_singleton:1006-1027`, `_emit_verify_panel:1051-1075`);
`tests/test_workflow_emitter.py` (no assertion changes expected).

**Approach:** mirror the `_verifier_agent_opts` single-source precedent (`:887-906`). The three
sites differ in indentation (6 / 2 / 0 spaces), consumer (break-or-throw inside the iterate loops
vs direct throw in the one-shot panel), and variable prefix — parameterize those; keep the emitted
strings identical this unit.

**Patterns to follow:** `_verifier_agent_opts` docstring's drift rationale; existing
emission-helper style (append to `lines`, f-string literals).

**Test scenarios:** the existing suite is the oracle — `uv run pytest tests/test_workflow_emitter.py`
green with zero assertion edits, covering all three shapes: one-shot panel
(`:763-784` and `:841-844`), iterate-to-consensus singleton loop
(`test_iterate_to_consensus_emits_loop`, `:1528-1554`), iterate-to-consensus thunk loop
(`test_parallel_iterate_to_consensus_emits_loop_in_thunk`, `:1557+`); mutation-guard count tests
(`:903-934`) unchanged.

**Verification:** full emitter test file passes untouched; `git diff` shows only
`execution_spec.py` structure, no emitted-string changes.

### U2. Runtime-missing recompute, quorum floor, honest messages (Layer A)

The core fix: record missing verifiers, recompute the threshold over reporters, mark
under-strength, keep the throw prefix.

**Goal:** the emitted reconciliation matches the High-Level Technical Design block above at all
three sites; the stale `_emit_verify_panel` docstring is corrected to the throw contract.

**Requirements:** R1 (runtime cause), R3, R4, R5, R6, R10, R12 (semantic half), R13.

**Dependencies:** U1.

**Files:** `plugins/saga/scripts/execution_spec.py`; `tests/test_workflow_emitter.py`.

**Approach:** implement inside the U1 helper. Majority threshold expression
`Math.max(1, Math.ceil(<reported>.length / 2))`; unanimous `Math.max(1, <reported>.length)`.
Floor literal `⌈n/2⌉` baked at emit time (KTD3). Missing-log emitted on the accept path of all
three sites; iterate-loop throw at `max_iterations` and the one-shot throw both gain
`${refute_count}/${reported} reporting verifiers (${missing} missing)` after the intact
`verifier-disagreement:` prefix (KTD4/R13). Update existing fixed-threshold assertions
(`tests/test_workflow_emitter.py:780,797,844`) to the recomputed expressions. Contract guards to
honor: `test_refuted_panel_emits_verifier_disagreement_halt` (`:1508-1526`) enforces
throw-not-log-and-continue and bans the phrase `review before relying on it` — the new
missing-log is an *annotation on the accept path*, never a replacement for the throw, and its
message must avoid the banned phrase (the planned wording "verdict computed over …" complies).

**Patterns to follow:** string-assertion test idiom at `tests/test_workflow_emitter.py:758-784`;
budget-rider verify test naming.

**Test scenarios (assertions over emitted script text; there is no JS runner in this repo):**

- Happy path / no-regression (`-k verify_panel`): n=3 majority spec emits the reported-filter,
  `Math.max(1, Math.ceil(U2_reported.length / 2))` threshold, and the intact
  `verifier-disagreement:` prefix; mutation-guard agent counts unchanged.
- Missing-verifier recording (`-k missing_verifier`): emitted script contains the
  `runtime-failure` missing-log with the `reported/declared-n` statement and the baked
  UNDER-STRENGTH floor literal (`quorum floor 2` for n=3; `quorum floor 4` for n=7;
  `quorum floor 1` for n=1).
- Unanimous recompute: `pass_rule=unanimous` spec emits `Math.max(1, U1_reported.length)`.
- All three sites: one spec with an iterate-to-consensus unit inside a parallel wave, an
  iterate-to-consensus singleton, and a one-shot panel — each emission carries the recompute
  block (guards R12 against a site regressing to the old pattern).
- Edge: n=1 panel emits `Math.max(1, …)` guard (the all-missing → not-refuted path is encoded in
  the expression, assert the guard text).

**Verification:** `uv run pytest tests/test_workflow_emitter.py -v -k "verify or missing"` green;
manually emit a sample spec (`execution_spec.py emit`) and read the generated reconciliation for
a 3-panel unit — it names reported/missing/floor exactly as the design block.

### U3. Verify-block contract documentation

Bring the reference doc in line with the shipped behavior and the new missing-verdict contract.

**Goal:** `plugins/saga/references/execution-spec.md:44-61` documents: the throw consumer (not
`log()`-only), the runtime-missing recompute rule with the `⌈(n−k)/2⌉` / all-`(n−k)` table, the
`⌈n/2⌉` quorum floor and UNDER-STRENGTH marker, the static-vs-runtime two-kinds boundary (static
exclusion = author a smaller n at composition; runtime failure = recompute), and the KTD2 hang
residue.

**Requirements:** R2 (documented boundary), R4, R9, R14.

**Dependencies:** U2 (documents what U2 shipped).

**Files:** `plugins/saga/references/execution-spec.md`.

**Approach:** extend the existing `Unit.verify` section table and prose in place; keep the KTD3
authoring defaults paragraph; one short "Missing verdicts" subsection, no new top-level section.

**Test expectation:** none — reference documentation; the behavior it describes is pinned by U2's
emitter tests.

**Verification:** the verify section's every claim is traceable to emitted code from U2 (spot-read
against a fresh `emit` output).

### U4. Layer B — dimension exclusion in team-execution consensus

Replace the fabricated N/A→8.0 with exclusion from the denominator, and pin the contract with
drift-guard tests.

**Goal:** a non-applicable dimension is excluded from the overall; the consensus gate evaluates
over applicable dimensions; a whole-lens-non-applicable reviewer is excluded from the consensus
denominator with a logged cause; a static skip never reads as a failure.

**Requirements:** R1 (static cause), R2, R7, R8, R9, R11.

**Dependencies:** none (independent of U1–U3).

**Files:** `plugins/team-execution/agents/architecture-reviewer.md` (`:81-82` exclusion
instruction; `:112` overall = mean of applicable dimensions; Output Format table gains the
`N/A — excluded (precondition absent: …)` row form and the overall row names its denominator,
e.g. "avg of 4 applicable");
`plugins/team-execution/skills/team-execution/references/consensus-protocol.md` (`:33-35`
applicable-dimensions scoring; `:69` pass threshold over applicable dimensions; new short
subsection: whole-lens exclusion + static-skip-is-not-a-failure — an excluded dimension/reviewer
does not trigger the re-review path at `:51-54` and is not a NEEDS-REVISION signal);
`tests/test_team_execution_consensus.py` (new).

**Approach:** prompt-contract edits only — no scoring engine exists to change; the markdown is the
spec the reviewer agent executes (KTD7). Keep the exclusion cause phrasing aligned with R1's
`static-non-applicable` vocabulary so Layer A docs and Layer B docs name the same contract.

**Patterns to follow:** drift-guard test idiom in `tests/test_team_execution_plugin.py:106-159`
(assert contract phrases present / anti-patterns absent, with pointed failure messages).

**Test scenarios (content drift-guards):**

- `test_dimension_exclusion_replaces_fabricated_default`: `architecture-reviewer.md` no longer
  contains `8.0 default` (or any fabricated-default scoring for N/A); contains the exclusion
  instruction and the mean-of-applicable overall rule.
- `test_consensus_gate_evaluates_applicable_dimensions`: `consensus-protocol.md` defines the
  applicable-dimensions denominator for the ≥9.0 / <7.0 gate and the whole-lens exclusion rule.
- `test_static_skip_no_floor` (AE3 boundary): both docs state a precondition exclusion is
  recorded with cause `static-non-applicable` and is not a failure — never enters re-review /
  escalation; assert the exclusion vocabulary is shared with the Layer A contract name.
- Edge: exclusion is dimension-granular — reviewer doc still requires scoring the four
  precondition-independent dimensions when only ADR-coverage is excluded.

**Verification:** `uv run pytest tests/test_team_execution_consensus.py -v` green; a dry read of
the reviewer doc yields an unambiguous instruction path for the no-architecture-docs repo (score
4, exclude 1, average 4).

### U5. Release surfaces and engineering journal

Ship the installed-plugin metadata and journal in the same PR, per repo policy.

**Goal:** versions, marketplace, changelogs, drift guards, and journal entries all tell the same
story as the diff.

**Requirements:** R15.

**Dependencies:** U2, U3, U4 (records what shipped).

**Files:** `plugins/saga/.claude-plugin/plugin.json` (0.49.2 → 0.50.0);
`plugins/team-execution/.claude-plugin/plugin.json` (2.8.0 → 2.9.0);
`.claude-plugin/marketplace.json` (both entries); `plugins/saga/CHANGELOG.md`;
`plugins/team-execution/CHANGELOG.md`; `tests/test_saga_plugin.py:48` and
`tests/test_team_execution_plugin.py:64` version pins;
`docs/engineering-journal/DECISIONS.md` (two-kinds contract; KTD2 no-timeout; KTD3 floor);
`docs/engineering-journal/LEARNINGS.md` (the uphold-bias mechanism: a null-tolerant filter plus a
fixed threshold silently converts member failure into member assent — generalizable to any
quorum-over-nullable-array pattern).

**Approach:** follow the changelog voice of `plugins/saga/CHANGELOG.md` 0.49.x entries; minor
bumps per KTD8.

**Test expectation:** none beyond updating the two version drift-guard pins — metadata unit.

**Verification:** `uv run pytest tests/test_saga_plugin.py tests/test_team_execution_plugin.py`
green; `grep -r "0.49.2\|2.8.0"` finds no stale pin for these plugins.

---

## Scope Boundaries

**In scope:** the two-kinds contract across the two existing surfaces exactly as U1–U5 describe.

**Deferred to follow-up work:**

- A verifier-level timeout / hang-to-missing conversion (Q1 residue, KTD2) — requires a harness
  timer primitive that does not exist in the script sandbox today.
- A re-spawn / operator-escalation / `inconclusive` control-flow state — v1 only makes the
  throw/accept surfaces honest.
- The floor value as an operator-tunable knob — v1 bakes `⌈n/2⌉`; revisit if real panels show the
  fixed rule mis-sized.

**Out of scope (non-goals, affirmed by the readiness review):**

- Single-saga cost rubric; new concurrency caps (`VERIFY_N_CAP=7` + harness cap stand); model
  homogeneity (same-tier rule stands); `pass_rule` semantics for members that do report;
  the gated-vs-advisory governance split; malformed-but-non-null verdict handling (KTD1 —
  existing `malformed-output` failure-class territory).

---

## Risks & Dependencies

- **Existing tests assert fixed-threshold strings** (`test_workflow_emitter.py:780,797,844`) —
  they will fail loudly on U2, which is intended; the risk is quietly weakening them during the
  update. Mitigation: replace each with the full recomputed expression plus the prefix assertion,
  never a looser substring.
- **The `verifier-disagreement:` prefix is a pinned contract** — existing tests assert its
  presence/absence (`tests/test_workflow_emitter.py:1522,1550,1624`) and the string must stay
  aligned with `FailureClass.VERIFIER_DISAGREEMENT` (`completeness_gate.py:22`; no production
  message-parser exists today, so the tests are the enforcement). Mitigation: R13 pins the
  prefix; U2 adds an explicit prefix-intact assertion.
- **Layer B is prompt-level** — no runtime enforces the exclusion arithmetic; a model could still
  misread. Mitigation: KTD7 drift-guards pin the contract text; the instruction is made mechanical
  (an explicit worked "4 applicable → average 4" example in the reviewer doc).

## Open Questions

None — Q1 is resolved as KTD2; the floor value and representation questions the issue deferred to
planning are resolved as KTD3 and the High-Level Technical Design message formats.

## Sources

- `plugins/saga/scripts/execution_spec.py:337-403` (Verify dataclass, iterate_to_consensus),
  `:869-906` (verifier prompt/opts single-source precedent), `:909-958` / `:979-1028` /
  `:1031-1075` (the three reconciliation sites), `:122-129` (BUDGET_RIDER).
- `plugins/saga/scripts/completeness_gate.py:18-32` (failure classes; throw-prefix contract).
- `plugins/saga/references/execution-spec.md:44-93` (verify block + emitter invariants).
- `plugins/team-execution/agents/architecture-reviewer.md:34,81-82,112-115` (five-dimension
  average; N/A→8.0; verdict rule).
- `plugins/team-execution/skills/team-execution/references/consensus-protocol.md:13,33-35,44-54,69`
  (consensus loop, scoring, re-review path, pass threshold).
- `tests/test_workflow_emitter.py:758-844,903-934,1504-1624` (verify-panel assertion idiom;
  mutation guard; typed verifier-disagreement halt tests + banned-phrase assert).
- `tests/test_team_execution_plugin.py:59-159` (drift-guard idiom; 2.8.0 version pin).
- Upstream: `docs/brainstorms/2026-06-28-verify-panel-robustness-requirements.md`;
  `docs/reviews/2026-06-28-verify-panel-robustness-readiness.md` (READY; the reframe history).
