# Lane C evidence — issue 912 repair round (U3)

Worktree: `/Users/jefcox/workspace/infiquetra/cp912-lane-c`, detached at `77c01c99`.
Scratch for backups: `/tmp/cp912-lane-c-scratch` (all `cp`/`cmp` restore proofs ran there).
No git command was run at any point. Mutation restores used `cp` backup plus `cmp -s`
byte-identity only. The full gate was never run; only the scoped list from U3 plus the
three lint/type/format commands.

Note on pasted pytest output: the runner emits unrelated `PytestWarning (rm_rf)`
tmp-cleanup noise after the summary line; it is trimmed below. Every test-relevant
line (command, assertion, summary) is pasted verbatim.

## Pre-change baseline (scoped list, unmodified tree)

Command:

```bash
uv run pytest tests/test_brainstorm_continuity_contract.py tests/test_brainstorm_judgment_contract.py \
  tests/test_brainstorm_predicate_wiring.py tests/test_brainstorm_dialogue_ownership.py \
  tests/test_brainstorm_evidence_model.py tests/test_brainstorm_scenarios.py \
  tests/test_saga_lifecycle_consistency.py tests/test_saga_docs_coverage.py \
  tests/test_saga_plugin.py tests/test_saga_plan_save_and_routing.py \
  tests/test_lint_gate_absence_contract.py tests/test_sandbox_spawn_sites.py \
  tests/test_review_publication_lane.py -q
```

Result (verbatim summary):

```text
============================= 174 passed in 7.77s ==============================
```

## E1 red — CORR-9 + DOC-12 (new tests vs the pre-fix renderer)

Command (run after adding the two tests, before touching the renderer):

```bash
uv run pytest tests/test_saga_docs_coverage.py::test_ladder_source_labels_fit_their_column tests/test_saga_docs_coverage.py::test_ladder_caption_names_tick_frontmatter -q
```

Result (verbatim, failing assertion lines):

```text
tests/test_saga_docs_coverage.py FF                                      [100%]

=================================== FAILURES ===================================
__________________ test_ladder_source_labels_fit_their_column __________________

>               assert len(text) * per_char_px <= budget_px, (
                    f"source line {text!r} ({len(text)} chars, "
                    f"~{len(text) * per_char_px:.0f}px) overruns the {budget_px}px source column"
                )
E               AssertionError: source line 'docs/brainstorms/ + docs/specs/' (31 chars, ~330px) overruns the 265px source column
E               assert (31 * 10.652173913043478) <= 265
E                +  where 31 = len('docs/brainstorms/ + docs/specs/')
tests/test_saga_docs_coverage.py:320: AssertionError
_________________ test_ladder_caption_names_tick_frontmatter ___________________

>       assert "never stored as saga tick frontmatter" in svg
E       assert 'never stored as saga tick frontmatter' in '<svg ...>\n    <tspan x="800" dy="0">Rule: maturity is derived, never stored in saga frontmatter.</tspan>\n  </text>\n</svg>\n'
tests/test_saga_docs_coverage.py:331: AssertionError
FAILED tests/test_saga_docs_coverage.py::test_ladder_source_labels_fit_their_column
FAILED tests/test_saga_docs_coverage.py::test_ladder_caption_names_tick_frontmatter
======================= 2 failed in 0.51s ===============================
```

Red-for-the-right-reason check: the CORR-9 failure is the column overrun itself (a
rendered source line wider than the 285px source-to-maturity span minus padding), not
an import or fixture error — the SVG parsed, the `x="830"` blocks were found, and the
first over-wide line tripped the budget. The DOC-12 failure shows the old caption
verbatim in the rendered SVG. The 50-character `pending-confirmation` source
(`docs/brainstorms/ frontmatter pending-confirmation`) fails the same budget on the
pre-fix renderer (single 50-char line, ~533px); the run above tripped first on the
31-char `requirements-ready` source, which overruns for the same reason.

Green after the renderer fix (verbatim summary):

```text
============================== 12 passed in 1.21s ==============================
```

## E2 red — TEST-3 (pipe qualifier re-added → seeded negative must FAIL)

Mutation protocol (verbatim):

```bash
FILE="tests/test_brainstorm_continuity_contract.py"; SCRATCH="/tmp/cp912-lane-c-scratch"
cp "$FILE" "$SCRATCH/$(basename $FILE).bak"
# ... re-added `line.strip().startswith("|") and` to check_no_pending_to_plan ...
uv run pytest "$FILE" -q -k "test_no_pending_to_plan_seeded_negative"
```

Result (verbatim, failing assertion line):

```text
>       assert check_no_pending_to_plan(text + "\n" + seed + "\n") != []
E       AssertionError: assert [] != []
E        +  where [] = check_no_pending_to_plan(((('# Dispatch Table\n\nThe designed routing map ...' + '\n') + 'When the handoff maturity is `pending-confirmation`, route straight to `/plan`.') + '\n'))
tests/test_brainstorm_continuity_contract.py:634: AssertionError
FAILED tests/test_brainstorm_continuity_contract.py::test_no_pending_to_plan_seeded_negative
======================= 1 failed, 23 deselected in 0.12s =======================
```

Red-for-the-right-reason check: with the `startswith("|")` qualifier back, the seeded
prose-line negative passes through the guard, so the seeded test fails — the pin is
load-bearing against exactly the narrowing the review filed.

Restore (verbatim):

```bash
cp "$SCRATCH/$(basename $FILE).bak" "$FILE"
cmp -s "$SCRATCH/$(basename $FILE).bak" "$FILE" && echo RESTORED-BYTE-IDENTICAL || echo RESTORE-FAILED
```

```text
RESTORED-BYTE-IDENTICAL
```

```text
======================= 1 passed, 23 deselected in 0.11s =======================
```

## E2 red — TEST-7 (unordered all-present body → seeded test must FAIL)

Mutation protocol (verbatim): same `cp` backup shape; `_has_block_shape` body replaced
with an unordered all-present check:

```python
def _has_block_shape(text: str) -> bool:
    return (
        "`/ideate` answers:" in text
        and "`/brainstorm` answers:" in text
        and "`/plan` answers:" in text
    )
```

```bash
uv run pytest "tests/test_saga_lifecycle_consistency.py" -q -k "test_has_block_shape_ordering_seeded_negative"
```

Result (verbatim, failing assertion line):

```text
>       assert _has_block_shape(seeded) is False
E       assert True is False
E        +  where True = _has_block_shape('\n- `/ideate` answers: "What are the strongest ideas?"\n- `/plan` answers: "How should it be built?"\n- `/brainstorm` answers: "What exactly should one chosen idea mean?"\n')
tests/test_saga_lifecycle_consistency.py:215: AssertionError
FAILED tests/test_saga_lifecycle_consistency.py::test_has_block_shape_ordering_seeded_negative
======================= 1 failed, 8 deselected in 0.09s =======================
```

Red-for-the-right-reason check: the unordered body returns True on the inverted seed,
so the seeded test fails — the ordering clause is falsifiable.

Restore (verbatim):

```text
RESTORED-BYTE-IDENTICAL
```

```text
======================= 1 passed, 8 deselected in 0.09s =======================
```

## E2 red — TEST-6 (`/qa` added to a tmp_path model copy → derivation must FAIL)

Command: copy the live model to a `tmp_path` (here `tempfile`), append `/qa` to
`pending-confirmation.read_by`, run the committed `_check_read_by_derived` helper.

Result (verbatim):

```text
mutated read_by: ['/resume', '/loop', '/handoff', '/qa']
violations: ["read_by entry '/qa' names a skill that never branches on pending-confirmation"]
E2 RED CONFIRMED: adding /qa to read_by fails the derivation
```

Red-for-the-right-reason check: `/qa`'s SKILL.md never mentions `pending-confirmation`,
so the derivation rejects it — the literal-set assertion it replaces would have
accepted any three-member list silently.

## Predicate probes — real-file `[]`, mutated-copy non-empty

Direct runs of every new/extended `check_*` against the edited prose (verbatim):

```text
check_dispatch_deferred_context: real-file=[] mutated-copy=['expected exactly one deferred-context dispatch row, found 0']
check_loop_unrecognized_declaration_stops: real-file=[] mutated-copy=['missing never-continue-to-saga-scan clause for unrecognized declarations']
check_declined_artifact_reenters_confirmation: real-file=[] mutated-copy=['missing never-confirmed-or-declined re-entry rule']
check_matched_brainstorm(+tier2): real-file=[] mutated-copy=['missing tier 2 legacy run class in matched-brainstorm']
check_near_match_predicate(+reorder/dedup): real-file=[] mutated-copy=['missing reordered-topic arm in near-match definition']
check_no_pending_to_plan(every-line): real-file=[] mutated-copy=['pending-confirmation must not route to /plan: When the handoff maturity is `pending-confirmation`, route straight to `/plan`.']
check_checkpoint(seeded inversion): real-file=[] mutated-copy=['found inverted ordering: written AFTER confirmation']
```

## Grep acceptances (verbatim)

TEST-9 dead disjunctions gone:

```bash
grep -c 'or "passed" in' tests/test_brainstorm_judgment_contract.py
```

```text
0
```

AM-9 `globals()` gone:

```bash
grep -c "globals()" plugins/saga/scripts/render_docs_visuals.py
```

```text
0
```

AU-8 stub lines (no line may name `/resume` or `/retro`):

```bash
grep -n "stub" plugins/saga/skills/loop/references/dispatch-table.md plugins/saga/skills/loop/SKILL.md plugins/saga/skills/loop/references/drive-and-resume.md
```

```text
plugins/saga/skills/loop/references/dispatch-table.md:17:A route to a **stub** target is **advisory**: `/loop` names it as the next command and dispatches, but
plugins/saga/skills/loop/references/dispatch-table.md:18:**never blocks `/loop` on its output** — the stub cannot produce a gate result yet. Only the shipped
plugins/saga/skills/loop/SKILL.md:67:   `references/dispatch-table.md` still says stub are **advisory** and **never** block `/loop` on
plugins/saga/skills/loop/SKILL.md:69:   not by being stubs.
plugins/saga/skills/loop/SKILL.md:396:  destination-class meaning, and the stub-target advisory rule.
```

The surviving lines are the generic advisory rule (dispatch-table 17-19, kept per the
plan) and generic references to it — none names `/resume` or `/retro`. The duplicate
equality clause now appears exactly once:

```bash
grep -c "equality being the exact match handled above" plugins/saga/skills/brainstorm/SKILL.md
```

```text
1
```

## AM-9 asset proof — `globals()` removal alone changes no asset byte

An AM-9-only renderer variant (current file minus the CORR-9/DOC-12 hunks) rendered to
a temp dir and compared against the committed assets (verbatim):

```text
state-readiness-ladder.svg BYTE-IDENTICAL
command-matrix.svg BYTE-IDENTICAL
lifecycle-atlas.svg BYTE-IDENTICAL
ownership-boundary-map.svg BYTE-IDENTICAL
```

After the CORR-9/DOC-12 fix, `uv run python plugins/saga/scripts/render_docs_visuals.py`
regenerated exactly one asset (others `cmp`-identical to their pre-regen copies):

```text
state-readiness-ladder.svg REGENERATED
command-matrix.svg UNCHANGED
lifecycle-atlas.svg UNCHANGED
ownership-boundary-map.svg UNCHANGED
```

## Post-change scoped run + lints (verbatim summaries)

```bash
uv run pytest tests/test_brainstorm_continuity_contract.py tests/test_brainstorm_judgment_contract.py \
  tests/test_brainstorm_predicate_wiring.py tests/test_brainstorm_dialogue_ownership.py \
  tests/test_brainstorm_evidence_model.py tests/test_brainstorm_scenarios.py \
  tests/test_saga_lifecycle_consistency.py tests/test_saga_docs_coverage.py \
  tests/test_saga_plugin.py tests/test_saga_plan_save_and_routing.py \
  tests/test_lint_gate_absence_contract.py tests/test_sandbox_spawn_sites.py \
  tests/test_review_publication_lane.py -q
```

```text
============================= 183 passed in 8.06s ==============================
```

(174 pre-change + 9 new: 6 continuity, 1 lifecycle, 2 docs-coverage.)

```bash
uv run python plugins/saga/scripts/lint_gate_absence_contract.py
```

```text
VIOLATIONS: 0
```

```bash
uv run python scripts/lint_test_shape.py tests plugins --prod-module server
```

```text
lint_test_shape: OK — 301 module(s) checked, no fake-only suites
```

```bash
uv run ruff check . && uv run ruff format --check .
```

```text
All checks passed!
517 files already formatted
```

(One `ruff format` reflow of the continuity test was applied first; the re-run above
is post-reflow, and the continuity + evidence-model modules re-passed: 27 passed.)

```bash
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

```text
Success: no issues found in 346 source files
```

## TEST-9 seeded-inversion control still fires (verbatim summary)

```bash
uv run pytest tests/test_brainstorm_judgment_contract.py tests/test_brainstorm_continuity_contract.py -q -k "checkpoint or inventory or resolver"
```

```text
======================= 3 passed, 33 deselected in 1.48s =======================
```

The two integration assertions now read `"2 passed"` / `"1 passed"` exactly, and both
hold (sandbox spawn-sites really emits 2, the tier-resolver routing test really emits
1) — the strict form matches reality, not just the suite.
