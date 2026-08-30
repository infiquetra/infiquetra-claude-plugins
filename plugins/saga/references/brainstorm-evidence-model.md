# Brainstorm Evidence Model — Three Layers for Issue 915 (B3)

How the suite proves the behaviour B1 and B2 shipped without turning a
conversational judgment into a unit-test fact. Prior art reviewed, shape
reused, and what this suite explicitly does **not** prove.

## Prior art — reviewed and recorded

Four candidates already in the repository were reviewed before designing
this model. Each verdict is a fit decision, not a reimplementation.

| Candidate | Location | Verdict | Reason |
|---|---|---|---|
| Data-file case suite + injectable runner + deterministic graders | `plugins/saga/scripts/engine_benchmark.py` + `plugins/saga/references/benchmark-suite.yaml` — header states graders are never model-graded | **Reuse the shape** | Cases as data, runner injectable, grading deterministic and never LLM-judged; live grading opt-in behind env var, never in CI (R23, KTD5) |
| Markdown rubrics with narrative scoring bands | `plugins/saga/references/rubrics/` + `plugins/saga/scripts/lifecycle_review.py` | **Reuse the dimension vocabulary, decline the Markdown carrier** | R19 needs per-dimension reporting with rubric as data, not inlined prose assertions; Markdown would require parsing and would hide the rubric from the grader's structured input |
| Standalone AST visitor + fixtures + whole-suite invariant | `scripts/lint_test_shape.py` + `tests/test_lint_test_shape.py` | **Reuse the mechanism** | `ast.NodeVisitor` plus dataclass report plus whole-suite invariant for R17's mechanical dialogue-assertion check |
| In-memory string surgery feeding a pure analyzer | `tests/test_concurrency_conformance.py::_mutate_source` | **Reuse the mechanism** | Mutation proof via `text.replace(needle, "", 1)` feeding the same `check_*(text)` predicate (KTD3) |

## Layer 1 — Deterministic contract boundary, mechanically enforced

`tests/test_brainstorm_evidence_model.py` walks the AST of every
`tests/test_brainstorm_*.py` module. It collects string literals that
appear inside `assert` statements and fails on:

- any literal that ends with `?` or opens with an interrogative
  (`what`, `how`, `why`, `who`, `when`, `which`, `can you`, `could you`);
- any `assert` that compares an ordered sequence (list/tuple literal) of
  two or more such question-shaped literals.

The walk is `ast.NodeVisitor` only; no substring search over the file.
This proves R17 over the test sources rather than by reviewer promise:
no deterministic test asserts which question is asked, its wording, or
the order of the creative dialogue.

Deterministic coverage is also asserted: artifact metadata, resume
lookup, the declared `brainstorm-scope-confirmation` gate,
scope-confirmation state, terminal routing, and helper ceilings each have
at least one passing `check_*` assertion, discovered by scanning the
modules for those keywords rather than hardcoding a second list.

## Layer 2 — Scenario evaluations scored per dimension

`tests/data/brainstorm/scenarios.json` holds the case set. Each case
carries `id`, `idea_seed`, `product_size` and `consequence` as
**independent** fields, `material_dimensions`, `expected` per dimension,
and `transcript` (`captured` or `none`). The set varies both variables
independently (not collinear) and includes at minimum the four required
failure-mode kinds: `premature-convergence`, `missed-material-gap`,
`consequence-calibration`, `checklist-overengineering`.

`tests/data/brainstorm/rubric.json` holds dimensions and their band
descriptions as data, never inlined in assertions.

`grade(transcript, rubric) -> dict[dimension, Result]` is a pure
function returning one result per material dimension named by the case.
The runner is injectable exactly as `engine_benchmark.run_suite` takes
one, so live grading is opt-in behind an environment variable and never
runs in CI (R23).

**Authored case data is expected and permitted.** `scenarios.json`,
`rubric.json`, and `calibration.json` are authored by this unit: they
define the idea seed, the two independent variables, the material
dimensions, and the expected outcome per dimension. That is design input,
not evidence.

**Captured transcripts are optional and additive.** Where a checkpoint
transcript exists, `grade()` runs against it and the case records
`transcript: captured`. Where none exists, the case records
`transcript: none` and the offline suite still proves everything it
claims — shape, coverage, per-dimension reporting, no-aggregate, gating,
and calibration agreement. A missing failure-mode transcript never
blocks U3.

**The one thing that stays forbidden is mislabelling.** No case may
carry a synthesized transcript labelled `captured`. That is the
harness-substitution failure this constraint prevents.

No aggregate number is computed, stored, or reported. The result object
exposes no `score`, `total`, `aggregate`, `overall`, or `quality` key at
any level, and no consumer computes one (R19). Reporting is per
dimension only.

## Layer 3 — Evaluator trust and mutation proof

**Evaluator-trust rule (R20).** `is_blocking(finding, *, reproducible,
second_grader_agrees, operator_adjudicated) -> bool` returns `True`
unconditionally for a deterministic contract failure, and for a
model-judged finding returns `True` only when the scenario is
reproducible **and** either a second independent grader agrees or an
operator adjudication is recorded. Every combination is asserted
directly.

**Calibration (R21).** `tests/data/brainstorm/calibration.json` holds a
small fixed set of cases with expected grades. The test runs the grader
over them, reports agreement per case, and fails when agreement drops
below the recorded floor. A seeded disagreeing grade drops the reported
agreement, proving drift is surfaced. The calibration set produces no
aggregate target of its own.

**Mutation proof (R22).** `tests/test_brainstorm_mutation_proofs.py`
carries one case per safeguard U1 and U2 declared critical — eight in
total: the ambiguity stop, the fresh-confirmation rule, the route-gating
on declared readiness, the no-deferred-save rule, the helper ceiling,
the map-privacy rule, the no-named-assurance-level rule, and the helper
read-only capability rule. Each case reads the real file, removes the
rule's text in memory, calls the same `check_*` predicate the contract
test calls, asserts violation, then asserts the unmutated text reports
none. A meta-assertion requires every safeguard named in the
declared-critical list to have a case, so adding a safeguard without a
mutation case fails.

## What this suite does not prove

The suite proves the grading and gating machinery, the deterministic
boundary, and the per-dimension reporting. It does **not** prove that any
given brainstorm was good. Formal completeness and contradiction review
stay after the confirmed artifact, in Document Review or a narrow
post-write validator, never in the live dialogue. A green scenario run
without a captured transcript proves the case set's shape and the
grader's determinism, not the quality of a conversation that was never
captured.

## Offline and side-effect-free (R23)

The harness runs offline, writes nothing under `docs/brainstorms/`,
mutates no path under `.claude/saga/`, and opens no socket. Live grading
is opt-in (`BRAINSTORM_LIVE_GRADE=1`) and never runs in CI.
