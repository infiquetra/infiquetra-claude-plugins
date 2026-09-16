# Code review — Mission Control alignment campaign (#999, #1000, #942)

- **Assignment:** `MC-ALIGN-14-CODE-REVIEW`. Authority: the implementation plan
  (`docs/plans/2026-09-13-mission-control-alignment-implementation-plan.md`) and the finite test
  plan (`docs/plans/2026-09-13-mission-control-alignment-finite-test-plan.md`), plus GitHub issues
  #999, #1000, #942 under grouping issue #1004.
- **Mode:** report-only review with a durable artifact at the assigned path. Strictly read-only
  over the reviewed codebase: no production or test edits, no commit, no push. No saga write was
  attempted (out of scope for this assignment).
- **Target:** local branch `main`, four child-scoped commits `f608bea6`, `f2ce1aca`, `920f7db9`,
  `e829445a`.
- **Merge base:** `ea7963a4bbf735b7179bd2d2605af740a1f8c2e7`.
- **Reviewed revision:** `e829445ab51cec0e5cdd8ba017ea57c879ae8b1a`.
- **Diff:** `git diff ea7963a4bbf735b7179bd2d2605af740a1f8c2e7 e829445ab51cec0e5cdd8ba017ea57c879ae8b1a`
  — 41 files, +3728/−596. Untracked files under `docs/plans/` and `docs/reviews/` are
  pre-existing evidence and were excluded from review, per the assignment.
- **Lenses:** the four always-on lenses (Correctness, Security, Testing,
  Maintainability/Conventions) plus the assigned conditionals (API Contract, Reliability).
- **Terminal outcome: `revisions-requested`.** Two P1 findings must be repaired before merge (a
  red gate and a containment bypass); six P2 findings should be repaired in the same pass. No P0
  findings. Counts: **P0: 0, P1: 2, P2: 6, P3: 4.**

## Verdict rationale

The campaign's core is strong: schema and generated-contract provenance is byte-exact against the
pinned SDLC commit, the Risk body field and UNKNOWN semantics match the reconciled oracle, the
repair-window verb is citation-first and idempotent with no project-field write, Technical Risk is
fully retired, and the Saga readiness delegation deletes every local parser with fail-closed
behavior across the six maturities. Both test suites are green (495 + 290 passed) and ruff is
clean.

Two defects block acceptance. First, the repository gate is red: the diff introduces exactly the 6
mypy errors the U6 gate report noted, and nothing else, across the full 354-file gate scope —
they are gate-blocking, not acceptable residuals (§ Adjudication). Second, the source reader opens
every local file *before* the owner refuses it, and for a re-anchored source it publishes the
in-root twin's identity with the outside original's bytes — a live violation of R9 and Jeff's
decision 3, proven by execution, and directly contradicted by the new journal entry. The six P2
findings are plan deviations the tests neither implement nor cover (two silent reconciliation
rules, the text-only default, hint-search poisoning, a weakened drift oracle, and an unproven
refusal case). None of the P1/P2 repairs is large; most are one-to-twenty-line changes.

## Findings

| # | Sev | Lens | File | Issue |
|---|-----|------|------|-------|
| 1 | P1 | Testing | 4 test files (§1) | Gate mypy red: 6 new errors, adjudicated must-fix |
| 2 | P1 | Correctness/Security | `plugins/mission-control/scripts/sdlc_manager.py:4807` | Read-before-refuse; re-anchored twin publishes outside bytes |
| 3 | P2 | Correctness | `plugins/mission-control/scripts/sdlc_manager.py:5886` | `--risk`/body conflict never blocks (R4) |
| 4 | P2 | Correctness | `plugins/mission-control/scripts/sdlc_manager.py:5836` | `--maturity`/source conflict never blocks (Ruling 942-5) |
| 5 | P2 | Correctness/Reliability | `plugins/mission-control/scripts/sdlc_manager.py:5868` | Text-only stamps `requirements-ready`, stays Saga-dependent |
| 6 | P2 | Reliability | `plugins/mission-control/scripts/sdlc_manager.py:4966` | Hint search crashes on first undeclared/malformed file |
| 7 | P2 | Testing | `tests/test_mission_control.py` relocated check | Weakened drift oracle never restored after the lag closed |
| 8 | P2 | Testing | `plugins/mission-control/tests/test_repair_window_label.py:235` | Schema-too-old case passes via the wrong branch; self-heal untested |
| 9 | P3 | Correctness | `plugins/mission-control/scripts/sdlc_manager.py:5438` | `handoff_maturity` frontmatter/sidecar mirror unchecked (KTD8) |
| 10 | P3 | Maintainability | `plugins/saga/scripts/handoff_envelope.py:478` + saga CHANGELOG | 6 of 9 non-routable diagnostics still embed paths; changelog overclaims |
| 11 | P3 | Reliability | `plugins/saga/scripts/handoff_envelope.py:769` | `assert` on `path_to_read None` instead of a fail-closed sentinel |
| 12 | P3 | Testing | T942-08/09/10 | Three thin coverage spots in the alignment suite |

### #1 (P1) — Gate mypy is red: 6 new errors in 4 test files; residuals rejected

The exact gate command fails at the reviewed revision and only because of this diff:

```
$ uv run python -m mypy plugins/ scripts/ tests/ --ignore-missing-imports
tests/test_handoff_envelope_maturity.py:1190: error: "object" has no attribute "maturity"  [attr-defined]
plugins/mission-control/tests/test_saga_readiness_alignment.py:79: error: Returning Any ... [no-any-return]
plugins/mission-control/tests/test_repair_window_label.py:68: error: Returning Any ... [no-any-return]
plugins/mission-control/tests/test_issue_risk_field.py:90: error: Returning Any ... [no-any-return]
plugins/mission-control/tests/test_issue_risk_field.py:124: error: Returning Any ... [no-any-return]
plugins/mission-control/tests/test_issue_risk_field.py:128: error: Returning Any ... [no-any-return]
Found 6 errors in 4 files (checked 354 source files)   # exit 1
```

Five are `warn_return_any` hits on `json.loads(...)` / untyped-helper returns in Test Author
fixtures (`isolate_schema`, `_prepare`, `_sidecar`); the sixth is `str(assessment.maturity)` on an
`object`-typed parameter in the new `_maturity` helper
(`tests/test_handoff_envelope_maturity.py:1187-1190`). All six lines are Test Author-added,
including the maturity-file helper, which sits in the new parity region (`@@ -1194,3 +1165,181`).
This directly violates #942's acceptance criterion (`bash scripts/gate.sh` exits 0) and R12.
**Adjudication: rejected as residuals** — full reasoning in § Mypy adjudication below.
**Repair:** test-author amendment; each fix is a one-line `cast(...)` / `isinstance` assert with
zero behavioral risk. Route to seat `w86:p8` (the three new MC files) and to the
`test_handoff_envelope_maturity.py` parity region under the existing shared-file protocol.

### #2 (P1) — `_source_from_local_path` reads before refusal; re-anchor publishes outside bytes as the twin

`_source_from_local_path` (`plugins/mission-control/scripts/sdlc_manager.py:4800`) reads the file
at line 4807 and only afterwards asks the owner to assess it (line 4816) and refuse it (line
4817). Two consequences, both verified by execution:

1. **Every refused source is opened first.** An out-of-root path, an escaping symlink, and an
   undeclared draft are all `read_text()` into memory before the refusal raises. The bytes are
   discarded, so this half is read-then-discard with no leak — but the plan requires local
   sources to be resolved against the named root *before reading* (R9), the grounding requires a
   refused source to be "never opened" (§4.5), and the new `DECISIONS.md` entry asserts "an
   out-of-root source is refused before it is read". The journal states a security property the
   code does not hold.
2. **Re-anchored sources publish the twin's identity with the original's bytes (live mismatch).**
   When the owner re-anchors an outside path to a declared in-root twin, MC keeps the pre-read
   *outside* content while adopting the twin's `published_source` and declaration:

```
$ resolve_source_artifact('/tmp/reanchor/out/docs/plans/x.md', root)   # outside, undeclared
ref:      docs/plans/x.md              # the twin's identity
maturity: plan-ready                   # the twin's declaration
content:  'OUTSIDE-ORIGINAL-BYTES\n'   # the outside original's bytes
```

   R9 requires "Read, draft, sidecar, and published handoff must agree on the chosen source";
   here the read (outside original) disagrees with the published source (twin). This is the exact
   shape Jeff's decision 3 forbids ("Do not mistake selecting a contained counterpart for
   authorization to read the outside original") — except no selection even occurred. The
   outside-with-declared-twin case is untested: T942-05's twin declares nothing (refused) and
   T942-06 selects the twin directly (consistent). Blast radius is local-only (same-user file
   bytes into the operator's own draft; no exfiltration vector), but the containment contract is
   broken. **Repair:** assess first, then read `assessment.path_read` (the twin when re-anchored)
   instead of pre-reading `resolved`; raise on `refused` before any open. Add a
   declared-twin re-anchor test asserting content bytes equal the twin's.

### #3 (P2) — A `--risk` value conflicting with the source body never blocks (R4)

R4 and Ruling 1000-2 require: when `--risk` and a supplied body's `### Risk` first line differ,
prepare records a blocking gap naming both values. `issue_prepare`
(`plugins/mission-control/scripts/sdlc_manager.py:5886`) derives `risk` from the body and drops
`--risk` on the floor for supplied bodies — no comparison exists anywhere in the module
(`grep conflict` finds only the draft-metadata check). The silent direction is safe (the
authoritative body wins), but the loud rule the plan requires is absent, and no test covers a
present-but-differing pair: T1000-01 covers seed-with-missing-section, and every T1000-05 seed
case pairs the seed with a malformed section (blocked for malformation either way).
**Repair:** compare the `--risk` seed against a well-formed body token in `issue_prepare` and
record a blocking gap naming both on mismatch; add the differing-pair test.

### #4 (P2) — An explicit `--maturity` silently overrides a differing source declaration (Ruling 942-5)

Ruling 942-5 requires: source carries a declaration and `--maturity` differs → blocking gap
naming both ("an override must not promote an artifact whose own declaration says otherwise").
`issue_prepare` (`plugins/mission-control/scripts/sdlc_manager.py:5836-5854`) classifies
`--maturity` through the owner and always wins; the artifact's assessment is never compared. A
`pending-confirmation` source plus `--maturity plan-ready` (typo or stale flag) is silently
stamped `plan-ready` with a live `/work` route. No test covers the differing pair, and
`plugins/mission-control/skills/issues/SKILL.md:142` documents the deviation ("`--maturity`
overrides the source's Saga-assessed handoff maturity"), so doc and code agree with each other
against the plan. **Repair:** reconcile before winning — block naming both values when the
source carries a declaration (vocabulary, blank, or sentinel) that differs; keep
override-wins only over the path-only fallback. Update the skill sentence and add both tests.

### #5 (P2) — Text-only prepare still stamps `requirements-ready` and stays Saga-dependent in readiness

The R8 creation table requires for "no source and no `--maturity` on text-only prepare": draft
allowed **with missing-maturity warning**, no readiness route. `issue_prepare`
(`plugins/mission-control/scripts/sdlc_manager.py:5868-5869`) instead stamps
`maturity = "requirements-ready"` (the retired default, kept for the no-source branch), renders
`### Handoff maturity / requirements-ready` into the draft, records it as Lifecycle Origin, and
emits no warning. Worse, the laziness is illusory: `_readiness_for_prepared_issue`
(`:5666-5668`) verifies every truthy maturity through `_saga_maturity_block`, so a text-only
draft's readiness *depends on Saga after all* — with Saga absent, text-only prepares land
`blocked` on "could not be verified", contradicting the "no source, no assessment, no Saga
requirement" comment at `:5830-5834` and the U5 "still work with Saga absent" check (which no
test pins for text-only prepare; T942-07 smokes only `board view`). The R8-table shape (maturity
absent + warning) would have avoided the dependency entirely. Note the default is entrenched in
an existing oracle (`test_issue_prepare_compile_approve.py` pins Lifecycle Origin
`requirements-ready` for text-only), so repair touches that oracle too. **Repair:** leave
maturity absent on the text-only branch with the missing-maturity warning (no owner load, no
verification); update the entrenched oracle and add a text-only-with-absent-Saga test.

### #6 (P2) — `find_source_artifacts` aborts the whole hint search on the first undeclared/malformed file

`find_source_artifacts` (`plugins/mission-control/scripts/sdlc_manager.py:4966-4981`) calls
`_source_from_local_path` per candidate, which now *raises* for undeclared, blank, unknown, and
refused sources. One bad file therefore aborts the entire search instead of being skipped — a
robustness regression, since the old inference never raised. The search dirs include
`docs/sdlc-issue-drafts/` and `.claude/saga/`, and this repository holds 215 historical drafts
whose sidecars predate `handoff_maturity`. Live repro against the real tree:

```
$ find_source_artifacts('draft', repo_root)
RAISED: RuntimeError Source artifact readiness problem for
docs/sdlc-issue-drafts/2026-07-20-codex-627-...md: unknown:undeclared:...
```

Any `--from` hint (or natural-language hint) over a root containing an undeclared draft now
crashes instead of matching. **Repair:** skip-and-continue on readiness refusal inside the
search loop (a non-routable candidate is simply not a match); add a hint-search test with an
undeclared draft present.

### #7 (P2) — Template-drift oracle weakened for the lag, never restored after it closed

`test_relocated_copy_check_behaves_identically` (`tests/test_mission_control.py`) previously
asserted the drift-check exit code is exactly 2 (missing canonical dir). Commit `f608bea6` (U1)
loosened it to `(1, 2)`, citing "the expected state during the dated #999 schema-to-generated
lag". But U2 re-rendered `templates-reference.md`, the lag never existed in the final history
(f608 shipped schema + generated together), and `sync_template_docs.py --check` exits 0 at the
reviewed revision (verified). No later commit restored strictness. The finite test plan forbids
exactly this ("Do not weaken a pin to silence it"), and the loosened oracle now permanently
tolerates exit 1 (drift) in any environment where it occurs. Dormant at HEAD, but the blinding
is permanent. **Repair:** revert to `== 2` (exit 1 is drift and must fail); drop the stale lag
comment.

### #8 (P2) — T1000-08's schema-too-old case passes via the wrong branch; the self-heal path is untested

`test_t1000_08_refuses_schema_without_marker`
(`plugins/mission-control/tests/test_repair_window_label.py:235`) feeds the *real* vendored
schema — which at 2026-09-07.5 *declares* the marker (with `marker_source`) — through a harness
whose `load_config` carries no `labels` key. It therefore refuses via the
*unresolvable-definition* branch ("that labels config does not define 'repair-window'"), not the
schema-too-old branch the test name claims. The true old-schema path (marker block absent → "too
old" diagnostic) is implemented (inspected-correct at
`plugins/mission-control/scripts/sdlc_manager.py:257-268`) but never executed by any test, and
the `marker_source`-present self-heal path (`flow_verify_label` with resolved color/description)
is likewise never exercised — T1000-06/07 use a synthetic marker *without* `marker_source`.
(Production is not broken: real `load_config` does carry `labels` from the SDLC checkout or its
remote fallback — verified at `sdlc_manager.py:223-275`.) **Repair (test-author amendment):**
retarget the test at a marker-less schema fixture for the too-old branch, and add a
`marker_source`-present open asserting the `flow_verify_label` self-heal call.

### #9 (P3) — `handoff_maturity` frontmatter/sidecar mirror agreement unchecked (KTD8)

KTD8 and the grounding (§4.4) require extending the existing frontmatter-versus-sidecar conflict
check to `handoff_maturity` "so the mirror cannot disagree silently".
`_read_prepared_issue` (`plugins/mission-control/scripts/sdlc_manager.py:5438-5449`) still
checks only repo/type/team/project; `field("handoff_maturity")` (`:5427`) lets draft metadata
win silently over a disagreeing sidecar. A hand-edit that changes one carrier but not the other
is honored without a word. **Repair:** add `handoff_maturity` to the mirror check; add a
disagreement test.

### #10 (P3) — Six non-routable diagnostics still embed paths; the saga changelog overclaims

`_assessment_diagnostic` (`plugins/saga/scripts/handoff_envelope.py`) made only
deferred-context, pending-confirmation, and undeclared path-free. The generic arm delegates
blank, carrier, unterminated, out-of-root, unreadable, and unrecognized to the frozen
`_maturity_diagnostic`, which interpolates `{source}` — so a blank file under `docs/plans/`
carries a `/plan` substring in a non-routable `next_action` (verified by execution:
`maturity: ''`, `routable: False`, `next_action: 'Blank maturity for docs/plans/blank.md — …'`,
`'/plan' in next_action is True`). The `routable` flag is correct, so production routing is
safe; only substring-shaped consumers are at risk. But the saga CHANGELOG asserts universally
that "a non-routable result can never carry a literal `/plan` or `/work` substring from a
display path" — false as written. **Repair:** either extend path-free diagnostics to the six
remaining shapes (per the LEARNINGS rule the campaign itself recorded) or narrow the changelog
claim to the three hardened shapes.

### #11 (P3) — `assess_source` asserts instead of failing closed on a missing declaration-class file

`assess_source` (`plugins/saga/scripts/handoff_envelope.py:769`) runs
`assert resolved.path_to_read is not None` for draft/state-class sources. An in-root but
nonexistent declaration-class path (resolves within root, `path_to_read None`) therefore dies
with `AssertionError` — invisible under `python -O` (flagged B101 by bandit) — instead of a
bounded `unknown:` sentinel. MC's caller checks existence first, so only direct API consumers
can reach it. **Repair:** replace the assert with an explicit `unknown:` return.

### #12 (P3) — Three thin coverage spots in the alignment suite

- **T942-09 binary case is owner-only** (`test_saga_readiness_alignment.py:520-524`): the
  unreadable-bytes fixture never runs through MC, so the finite plan's "both entry points agree"
  is unproven there. (MC would raise a raw `UnicodeDecodeError` from `read_text` — a
  pre-existing wart, not introduced here — rather than a bounded diagnostic.)
- **T942-10 reuses one fixture** (`:527-542`) where the finite plan requires the T942-01–06/09
  set; agreement is proven for a single pending-confirmation brainstorm.
- **T942-08's `incomplete-vocab` id is mislabeled** (`:438-450`): the fixture lacks
  `assess_declared` entirely (missing-API shape), so the "compatible API with incomplete
  vocabulary" shape from reconciliation 5 is never exercised, though the implementation's
  vocabulary probe handles it.
**Repair (test-author amendment):** add the MC-half binary assertion (or normalize the error
type first), widen T942-10's fixture set, and add a true misclassifying-owner case to T942-08.

## Built-vs-Planned audit

Scope check: **CLEAN with notes.** Every production change maps to #999, #1000, or #942; the U6
gate repairs (stage_flow oracle retarget, version-drift guards, two mypy touch-ups inside
`sdlc_manager.py`) are in-scope fallout of the resync, not creep. No merge, deployment, board
write, card closure, or upstream edit was performed. Notes: (a) `planning_to_active_risk_ready`
is new public surface the plan never asked MC to own (the authoritative gate stays upstream in
`planning_readiness.py`) — tested, harmless, but extra; (b) the U1/U2 commit boundary collapsed
(schema + generated shipped together in `f608bea6`; no dated lag guard ever existed) — the final
state matches U2's end state, so this is process-only.

### Units

| Unit | Disposition | Evidence |
|------|-------------|----------|
| U1 #999 resync + WIP | **DONE** (process deviation noted) | Vendored JSON hash `5a8c0c93…65b7` == SDLC `67845cdd` bytes; version `2026-09-07.5`; `67845cdd` still SDLC HEAD. `_wip_limits` + legacy branch deleted; `board wip`/`board view` count-only; docs rewritten. Generated modules shipped in the same commit, so the dated lag guard was never built — final parity is exact (see U2), intermediate states unreviewed. |
| U2 #1000 Risk field | **PARTIAL** | Single body reader, scaffold seed, UNKNOWN warn-and-create, Asgard grammar binding, trio preservation, generated bytes identical to `67845cdd` (`de8c98c8…`, `0e853d5c…`), no lag allowance, `--check` exits 0 — all verified. Missing: the `--risk`/body conflict block (finding #3). |
| U3 #1000 label + retirement | **DONE** | `flow repair-window` with citation-before-network (refusal precedes `load_config`), idempotent open/close, one comment per transition, REST-only writes (GraphQL use is a label *read*), schema-sourced marker, old-schema + unresolvable-definition refusals. `Technical Risk` mapping + prompt fully removed (zero hits in `sdlc_manager.py`); E1 pointers in comments + CHANGELOG; historical sidecars untouched. Test-oracle weakness on the too-old branch (finding #8). |
| U4 #942 Saga owner | **DONE** | `READINESS_CONTRACT_MAJOR = 1`, `UNKNOWN_PREFIX`, `assess_source`/`assess_declared`, frozen `ReadinessAssessment`, sidecar/state carriers, `unknown:undeclared`, path-free deferred/pending/undeclared diagnostics, envelope bytes preserved (root envelope tests green). Nits: findings #10, #11. |
| U5 #942 MC consumer | **PARTIAL** | Lazy registry resolution with rung provenance (install-time subprocess tests green), contract/API/vocabulary gates, local tuple/parser/default-on-routed-paths deleted, pending/deferred creatable-but-never-routed, blank/unknown block before draft, dependency diagnostic with no fallback, unrelated commands usable. Deviations: findings #2, #4, #5, #6, #9. Lifecycle Origin vocabulary-only holds by construction (non-vocabulary raises before `PreparedIssue` exists) — no explicit check, unreachable otherwise. |
| U6 integration | **PARTIAL** | 2.16.0/0.158.0 across plugin.json + marketplace (sync + parity checks exit 0), changelogs name owning children, three DECISIONS + two LEARNINGS entries newest-first (order lint 0 violations), existing pins preserved and strengthened. **Gate is not green** (mypy, finding #1). All 23 automated T-rows pass; several required outcomes are weakly proven (findings #3, #4, #8, #12). |

### Requirements R1–R12

DONE: R1 (hash-verified resync, no removed-key readers, count-only), R2 (same-commit
provenance for all three artifacts, oracles updated, no lag allowance in final state), R3
(body-sourced Risk, tier+UNKNOWN grammar, trio preserved, projections write-only), R5 (dedicated
label verb, cited open/close, idempotent, never a fourth field), R6 (Technical Risk retired,
history intact, upstream untouched), R7 (Saga-owned assessment, six-state probe, local inference
deleted), R10 (lazy ladder, repairable diagnostic, no fallback, `board view` proven usable).
PARTIAL: R4 (missing/malformed block ✓, UNKNOWN warn+create + active-gate helper ✓, **conflict
block ✗** #3), R8 (all six creation dispositions ✓ except **text-only row ✗** #5), R9 (root
resolution, twin/URL/branch identity ✓; **read-before-refuse + re-anchor mismatch ✗** #2),
R12 (release surfaces ✓, **gate red ✗** #1). R11 (single-seat serialization,
Test-Author-before-Dev) is **UNVERIFIABLE** from history — all four commits share one
author/date with tests and production in the same commits; no custody violation is visible, but
the sequencing cannot be confirmed from the diff.

### Finite T-rows (all 23 automated rows pass; oracle-strength notes)

T999-01/02/04 pass and prove their outcomes; T999-03 (plugin suite) re-verified green at
`495 passed, 1 xfailed`. T1000-01–05 pass; the differing `--risk` pair is absent from every row
(#3). T1000-06/07 pass including idempotent no-ops and no-`QUERY_SET_FIELD_VALUE`; T1000-08's
blank-citation half is rigorous (real-dispatch test asserts four no-calls) while its
schema-without-marker half proves the wrong branch (#8); T1000-09 passes with schema + matrix
pins. T942-01–04 pass on real files through real prepare paths with owner agreement; T942-05
passes all four escape shapes but not the declared-twin re-anchor (#2); T942-06 passes
twin/URL/branch identity; T942-07/08 pass the resolver- and loader-injected failures (board
smoke included; text-only-with-absent-Saga unpinned, #5); T942-09 passes five malformed shapes
plus owner-only binary (#12); T942-10 passes the no-local-parser scan plus single-fixture
agreement (#12).

## Lens results

- **Correctness — revisions requested.** The Risk reader, UNKNOWN lifecycle, repair-window
  state machine, retirement, resync, and owner contract are correct as built. Findings #2–#6
  and #9 are the correctness gaps: one containment bypass, two silent reconciliations, one
  retired default that survived, one search-path crash, one unchecked mirror.
- **Security — revisions requested (via #2 only).** No injection, secret, auth, or network-order
  issue found: citation refusal precedes all network access, label/comment writes are REST with
  typed errors, out-of-root *publishing* is refused, and diagnostics are bounded/escaped.
  Bandit on both changed production files reports 0 High / 0 Medium; the two new Lows are a
  B105 false positive on the `UNKNOWN` token constant and the B101 `assert` from finding #11.
  Finding #2 is local-only (no exfiltration vector) but breaks the documented containment
  property, so it gates this lens.
- **Testing — revisions requested.** Suites green as run here: `plugins/mission-control/tests`
  `495 passed, 1 xfailed`; root saga/mission-control selection `290 passed`. Schema isolation
  (`isolate_schema` + `_gh` block) is present in every new MC file; install-time coverage uses
  real scrubbed subprocesses outside the repo. Existing oracles were strengthened, not weakened
  (fixtures gain valid Risk; Asgard prose converted; agreement test carries a dated divergence
  note) — with one exception: finding #7. Findings #1, #7, #8, #12 are the testing gaps.
- **Maintainability/Conventions — accepted with nits.** `ruff check` and `ruff format --check`
  pass on every touched file; naming, module layout, and comment discipline follow repo
  conventions; journal entries are complete and ordered. Nits: the stale lag comment (#7), the
  `assert`-for-control-flow (#11), and the uncalled-in-prod `planning_to_active_risk_ready`
  helper (kept as the T1000-04 oracle; harmless).
- **API Contract (conditional) — accepted.** Owner contract (major + API + functional probe) is
  additive and correctly gated; generated bytes are byte-identical to the pinned SDLC commit
  with matching manifests and updated literal oracles; shim headers, CLI surface
  (`repair-window` with required `--citation`, free-string `--maturity`), and envelope
  byte-stability all verified. The `_SAGA_READINESS_VOCABULARY` probe tuple is a
  less-than-or-equal floor, not a second vocabulary copy — additive Saga changes flow through.
  One docs-accuracy wart: finding #10's changelog overclaim.
- **Reliability (conditional) — revisions requested.** Fail-closed verified by test or probe for
  pending/deferred non-routing, blank/unknown blocking before draft, out-of-root refusal,
  missing/incompatible Saga (no fallback), blank-citation refusal, and idempotent
  open/close/no-op transitions. Gaps: findings #5 (text-only Saga dependence), #6 (hint-search
  crash), #11 (assert crash), plus the pre-existing raw `UnicodeDecodeError` on binary
  `--from` input (noted, not introduced here).

## Mypy adjudication (the 6 U6 residuals)

**Ruling: rejected as residuals — all six must be repaired.** Each error sits on a
Test Author-added line, each fix is a mechanical one-line typing correction (`cast` /
`isinstance` / `getattr`) with zero behavioral effect, and the gate step they fail is a
blocking `step`, not an `advisory`. A residual is for risk accepted with reason (unfixable,
upstream-owned, or fix-riskier-than-tolerance); none of those applies — the cheapest correct
action is six one-line amendments. The full gate scope (`mypy plugins/ scripts/ tests/`,
354 files) shows exactly these six and nothing else, so repair restores a fully green type
gate; production modules are unaffected (`plugins/*/scripts/` is mypy-excluded by repo config).
Custody: test-author amendment — the three new MC files are Test Author-owned, and the
`test_handoff_envelope_maturity.py:1190` helper sits in the new parity region the Test Author
added before handoff, so it returns through the shared-file protocol, not a unilateral Dev
rewrite.

## Verification evidence

All commands ran from the repository root at the reviewed revision (`e829445a`), with
`UV_CACHE_DIR=/tmp/uv-cache` (the default uv cache is permission-blocked in this environment;
test behavior is unaffected):

| Check | Command (abridged) | Observed result |
|-------|--------------------|-----------------|
| MC plugin suite (T999-03) | `uv run pytest plugins/mission-control/tests -q` | `495 passed, 1 xfailed`, exit 0 |
| Root saga/MC selection | `pytest tests/test_handoff_envelope_maturity.py tests/test_handoff_envelope.py tests/test_fleet_commons_install_time.py tests/test_mission_control.py tests/test_saga_plugin.py -q` | `290 passed`, exit 0 |
| Gate mypy scope | `mypy plugins/ scripts/ tests/ --ignore-missing-imports` | exit 1: exactly the 6 errors, 354 files checked |
| Ruff lint + format | `ruff check` / `ruff format --check` on all 9 touched Python files | `All checks passed!`, `6 files already formatted` |
| Schema provenance | SDLC `git show 67845cdd:config/sdlc-schema.json \| shasum` vs vendored | `5a8c0c93…65b7` both; version `2026-09-07.5`; `67845cdd` is SDLC HEAD |
| Generated provenance | `git show 67845cdd:tools/docs/generated/<f> \| shasum` vs vendored + manifests | `de8c98c8…` / `0e853d5c…` match on bytes, manifests, and parity-test oracles |
| Template sync | `sync_template_docs.py --check` | exit 0, "in sync" |
| Release surfaces | `sync_marketplace.py --check`, `check_release_surface_parity.py`, `lint_journal_order.py` | all exit 0 |
| Bandit (advisory) | `bandit sdlc_manager.py handoff_envelope.py` | 0 High / 0 Medium / 14 Low (2 new: B105 FP + B101, see #11) |
| Re-anchor probe | outside-undeclared + declared-twin `resolve_source_artifact` | ref=twin, maturity=twin's, content=outside bytes (#2 proven) |
| Hint-search probe | `find_source_artifacts('draft', repo_root)` | raises on first historical undeclared draft (#6 proven) |
| Substring probe | blank file under `docs/plans/` via `assess_source` | non-routable `next_action` contains `/plan` (#10 proven) |
| Retirement greps | `wip_limits\|component_slices` plugin-wide; `Technical Risk` in `sdlc_manager.py` | schema hits are migration/source-note prose only; zero in prod code |

The full `scripts/gate.sh` was not run end-to-end: the mypy step already fails deterministically,
and every other gate element material to this diff was run individually above. The `rm_rf`
pytest warnings in the logs are sandbox tmp-cleanup noise from an unrelated test, not failures.

## Coverage, residual risks, and routing

- **Suppressed/dropped:** none. No finding was suppressed for low confidence — every finding
  above cites `file:line` plus executed or inspected evidence. No conditional lens beyond the
  assigned API Contract + Reliability set was run; no external advisory seat was requested.
- **Residual risks after repair:** (a) the upstream Planning-to-Active gate (not this repo)
  remains the enforcer that keeps UNKNOWN cards out of Active — verified to exist at the pinned
  SDLC commit by the plan review, not re-verified here; (b) the home-lab card validator is
  still pre-Risk (dated divergence note in the agreement test) — cross-repo skew to track, not
  this diff's defect; (c) historical `docs/sdlc-issue-drafts/` sidecars (215 files) carry no
  `handoff_maturity` and are now unresolvable as prepare sources by design.
- **Routing:** findings #1 (mypy), #8, #12 route as test-author amendments (`w86:p8`); finding
  #7 (drift-oracle revert) is a Dev one-liner in an existing file; findings #2–#6, #9–#11
  route to the Dev (`w86:p9`) as production repairs with the named test additions. Re-review
  the repaired revision before merge; the gate must be re-run green (mypy + full suite) on the
  exact repaired SHA.
- **Next action:** `repairs_requested` — hand findings #1–#12 to the owners above, then resubmit
  the repaired revision for a cycle-2 review.

---

# Cycle 2 recheck — assignment MC-ALIGN-17-RECHECK

- **Repaired revision:** `829f67a3ab29faed854aa95d9ad86d9e56239791` (HEAD verified). **Merge base:**
  `ea7963a4bbf735b7179bd2d2605af740a1f8c2e7` (unchanged). Repair range `e829445a..829f67a3`:
  six commits (`66627f85`, `ac081914`, `136b6fa5`, `500f3efc`, `5744341d`, `829f67a3`), 15
  files, +772/−60. Everything above this line is the preserved cycle-1 record.
- **Method:** full re-read of the 15-file repair range (production, tests, skills, journal);
  re-execution of every cycle-1 probe at the repaired revision; MC suite, root selection, gate
  mypy scope, ruff, release/journal lints re-run; plus an independent full 25-step
  `scripts/gate.sh` run. Strictly read-only over the codebase (no edits, commits, or pushes);
  this section is the only write.
- **Terminal outcome: `accepted`.** All 12 findings verified repaired; no new defect introduced
  by the repairs. Remaining counts: **P0: 0, P1: 0, P2: 0, P3: 0** — with one documented residual
  (ready-state frontmatter vs `--maturity`, see #4) and one observation (commit-message issue
  ref) carried below, neither gating.

## Per-finding dispositions

| # | Sev | Disposition | How verified |
|---|-----|-------------|--------------|
| 1 | P1 | **FIXED** | Gate mypy scope exits 0: `Success: no issues found in 355 source files` (was 6 errors). Fixes are `cast` + `assert isinstance` / `getattr` one-liners on the exact flagged lines. |
| 2 | P1 | **FIXED** | Assess-before-read + bytes from `assessment.path_read`. Re-anchor probe now serves twin bytes with twin identity and maturity; a chmod-000 outside file draws a `RuntimeError` refusal, never a read (`PermissionError` would prove a read was attempted). Regression test pins twin bytes. |
| 3 | P2 | **FIXED** | `--risk`/body mismatch recorded as a blocking gap naming both tokens (self-consistent: scaffold seeds equal the flag, so no self-conflict). Regression test: body `high` + flag `medium` → blocked, both quoted. |
| 4 | P2 | **FIXED with documented residue** | `_maturity_declaration_conflicts` blocks positively-confirmed differing declarations (draft sidecar, Saga state, pending/deferred values — the sound predicate, since only a real declaration can produce those). Regression tests for block + path-fallback-wins (both `chdir`, correctly — the re-assessment resolves against CWD). **Residue, as the code comment flags:** frontmatter-declared *ready* states on plain-class files are indistinguishable from path fallback through the major-1 contract, so the override still wins there — verified behaving exactly as documented (no crash, no gap, override recorded). Closing: the hazardous direction (promoting past pending/deferred/undeclared) is blocked; the residue needs a contract change and is honestly recorded. Skill doc updated (it names only draft/state; the code also blocks pending/deferred on plain files — doc understates in the safe direction). |
| 5 | P2 | **FIXED** | Text-only branch records `None`: sidecar `handoff_maturity is None`, no rendered section, exactly the missing-maturity warning, no owner load — including a Saga-absent test proving `ready_to_create`. Entrenched oracle updated (`Lifecycle Origin` absent). The accompanying strip-and-rerender cascade (`_strip_trailing_handoff_context`: trailing-only, fence-aware, tier band re-stamped) keeps revision chains R9-agreed; `draft_revision` oracle pins the new behavior. |
| 6 | P2 | **FIXED** | Hint search skips non-routable candidates (`continue` on `RuntimeError`). Live probe over the real tree: 214 matches returned where it previously raised on the first historical draft. Regression test pins skip-and-match. |
| 7 | P2 | **FIXED** | Drift oracle restored to `== 2` with the stale lag comment replaced by "exit 1 is drift and must fail". |
| 8 | P2 | **FIXED** | Too-old case now strips the marker block from a copied fixture and matches the `too old` diagnostic; new self-heal test asserts the `flow_verify_label(repo, marker, color, description)` call. LEARNINGS entry captures the fixture trap. |
| 9 | P3 | **FIXED** | Mirror check extended to `handoff_maturity` (both-present disagreement raises); regression test hand-edits one carrier and asserts the loud conflict. |
| 10 | P3 | **FIXED** | All six remaining shapes got path-free twins (raw author values dropped too — stronger than asked). Blank-under-`docs/plans` probe: `routable False`, no `/plan` or `/work` in either string. CHANGELOG now enumerates all nine shapes. New 8-test diagnostics file pins each shape. |
| 11 | P3 | **FIXED** | `assert` replaced by the bounded `unknown:undeclared:<published>` sentinel; missing draft and state paths both return it non-routable (probed + tested). Bandit B101 gone. |
| 12 | P3 | **FIXED** | Binary case gains the MC half (tolerating the pre-existing raw codec error honestly); T942-10 widened to 7 resolvable + 4 refused fixtures; T942-08's incomplete-vocab case is now a true misclassifying owner that the probe rejects. |

## Cycle-2 verification evidence (all at `829f67a3`)

| Check | Observed result |
|-------|-----------------|
| MC plugin suite | `503 passed, 1 xfailed` (+8 new tests), exit 0 |
| Root selection incl. new diagnostics file | `298 passed` (+8), exit 0 |
| Gate mypy scope (355 files) | exit 0, `Success: no issues found` |
| Ruff check + format on all touched files | `All checks passed!`, formatted |
| Marketplace sync, release parity, journal order | all exit 0, 0 violations |
| Bandit on both prod files | B101 gone; remainder is the pre-existing set + the B105 `UNKNOWN` false positive |
| No version churn across the repair range | plugin.json/marketplace/CHANGELOG versions untouched (repairs under the same release) |
| Live probes (#2 ×2, #6, #10, #11, #4-residue) | all behave as the dispositions state |

## Gate status — honest accounting

The assignment reported an external full-gate GREEN (25 steps, 0 blocking). I ran the full gate
independently and observed **24/25 green, 1 blocking failure in step 02 (Run tests with
coverage): 5 failed, 7821 passed.** The five failures are all in files the campaign never
touched (`tests/test_audit_store.py`, `tests/test_codex_delegate_lifecycle.py`,
`tests/test_saga_engine_dispatch.py`, `tests/test_team_execution_pointers.py`, plus their prod
plugins — `git diff` across the full campaign range for all of them is empty), and every one
fails with an environment-denial signature, not an assertion on behavior:

- 2× `multiprocessing` semaphore `PermissionError` (this sandbox forbids unnamed semaphores);
- 1× live `codex exec` smoke exiting 1 (availability-gated live tool, broken in sandbox);
- 2× writes/stats under `/Users/jefcox/.claude/...` denied by the sandbox (one `PermissionError`,
  one consequent `FileNotFoundError`).

Steps 01 and 03–25 — including mypy, both ruff gates, all release-surface guards, journal
order, and mermaid — passed in my run. I could not independently reproduce 25/25 green inside
this sandbox (it lacks exactly the three capabilities those five tests need), so the external
GREEN stands as externally-reported and consistent with my analysis — not as independently
confirmed. It does not gate this verdict: every campaign-relevant signal is green in my own
runs, and the red step's failures are provably unrelated to the reviewed code.

## Residuals and observations carried forward (non-gating)

- Finding #4's ready-state-frontmatter residue (above): accepted as documented; closing it
  needs an owner-contract declaration-provenance flag — a future Saga change, not this campaign.
- Observation: repair commit `500f3efc` cites `(re #822)` though the change belongs to this
  campaign (#999/#1000) — a commit-message issue-ref typo. Traceability nit only; the diff
  itself is correct and no action is required.
- Cycle-1 residual risks (b), (c) stand: home-lab validator still pre-Risk (dated divergence
  note in-tree); the 215 historical sidecars remain unresolvable-as-sources by design.
- **Next action:** `accepted` — the repaired candidate `829f67a3` is approved from code review;
  merge remains the Lead's separate decision under its own authority.
