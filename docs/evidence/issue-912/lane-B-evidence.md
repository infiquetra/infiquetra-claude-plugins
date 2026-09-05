# Lane B evidence — issue 912 repair round

Worktree: `/Users/jefcox/workspace/infiquetra/cp912-lane-b`, detached at `77c01c99`.
Scope: U2 (Lane B) of `docs/plans/2026-09-04-issue-912-repair-lanes.md`, lines 518-693.
Rule compliance: no `git checkout`/`restore`/`stash`/`add`/`commit` or any other git
mutation ran in this worktree (one read-only `git show <rev>:<path>` per KTD2, plus the
`git merge-base` read used to diagnose the lint contradiction in §12). Mutation proof
restored by `cp` backup plus `cmp -s` byte identity. Every run below is pasted, not
described. (The recurring `PytestWarning: (rm_rf) ... Directory not empty` lines are
environmental tmp-cleanup noise on this machine, present on the pre-edit baseline too.)

## 0. Baseline (pre-edit)

```
$ uv run python scripts/lint_journal_order.py --base-ref origin/main
journal-order lint: 5 file(s) checked, VIOLATIONS: 0
EXIT=0
```

```
$ uv run pytest tests/test_brainstorm_evidence_model.py -q
============================== 3 passed in 0.19s ===============================
```

## 1. Item 1 — SEC-1 prose + DOC-1 residue (CHANGELOG bullets 2+4, SKILL Maturity, spec §4, DECISIONS)

```
$ grep -c "can route live" plugins/saga/CHANGELOG.md
0
$ grep -c "original absolute file is read" plugins/saga/CHANGELOG.md docs/engineering-journal/DECISIONS.md
plugins/saga/CHANGELOG.md:0
docs/engineering-journal/DECISIONS.md:0
$ grep -c "is read only when its path carries a marker directory" plugins/saga/skills/handoff/SKILL.md
0
$ grep -c "that declaration is honoured" plugins/saga/skills/handoff/SKILL.md
0
$ grep -c "reanchored_missing_fallback_to_original" plugins/saga/CHANGELOG.md
0
$ grep -c "test_reanchored_missing_twin_is_refused" plugins/saga/CHANGELOG.md docs/engineering-journal/DECISIONS.md
plugins/saga/CHANGELOG.md:1
docs/engineering-journal/DECISIONS.md:1
```

Pinned-phrase guard (must stay verbatim per `tests/test_saga_plugin.py:4023-4061`):

```
$ for p in "ONLY when \`handoff_maturity\` is one of the routable vocabulary values" "NEVER a runnable command" "two fail-closed states"; do grep -c "$p" plugins/saga/skills/handoff/SKILL.md; done
1
1
1
```

## 2. Item 2 — API-9 (scope the fail-closed claim, issue 950)

```
$ sed -n '3,12p' plugins/saga/CHANGELOG.md | grep -c "950"
1
```

Appended verbatim to the 0.156.0 entry: "This contract is saga's reader's.
Mission Control's `issue --prepare` path infers maturity from the artifact path alone
and does not apply it; that gap is tracked as issue 950."

## 3. Item 3 — SEC-9 prose half (already satisfied, no edit)

```
$ grep -c "unknown:out-of-root" docs/engineering-journal/DECISIONS.md
2
```

## 4. Item 4 — AU-3 prose half (flow mapping)

```
$ grep -rn "flow-style" plugins/saga/docs/state-readiness.md plugins/saga/skills/handoff/SKILL.md plugins/saga/references/saga-spec.md plugins/saga/CHANGELOG.md | grep -c "nested\|top-level"; grep -rn "flow-style" plugins/saga/docs/state-readiness.md plugins/saga/skills/handoff/SKILL.md plugins/saga/references/saga-spec.md plugins/saga/CHANGELOG.md | wc -l
5
5
```

All 5 `flow-style` hits are qualified by "nested" or "top-level". Behavioural anchor
is Lane A's `test_top_level_flow_mapping_declares` (not this lane's file).

## 5. Item 5 — API-6 (§9 lists four causes; add the fifth)

```
$ awk '/^## 9/,/^## 10/' plugins/saga/references/saga-spec.md | grep -c "out-of-root"
1
```

## 6. Item 6 — API-12 (grammar + KTD7 window sentence)

```
$ grep -c "must be an$" plugins/saga/references/saga-spec.md
0
$ grep -n "beyond the 8192-byte window" plugins/saga/references/saga-spec.md
316:file (within the first 8192 bytes) fails closed with no durable route and a diagnostic, rather than falling through to the path rule, provided the declaration lies within the bounded read windows; beyond the 8192-byte window the source fails closed as `unknown:unterminated:`.
```

## 7. Item 7 — DOC-11 (0.151.0 → 0.156.0)

```
$ grep -c "retitled this branch's CHANGELOG entry to \`## \[0.156.0\]\`" docs/engineering-journal/LEARNINGS.md
1
```

## 8. Item 8 — DOC-8 (six-field body under the bare heading)

Literal plan command and what it selects (see §12 plan-defect note — the range
collapses to the heading line because the anchor line itself matches `/^### /`):

```
$ awk '/916-dispatch-line-count-no-target/,/^### /' docs/engineering-journal/LEARNINGS.md | grep -c '^\*\*'
0
$ awk '/916-dispatch-line-count-no-target/,/^### /' docs/engineering-journal/LEARNINGS.md | head -8
### A hand-maintained count in a Markdown table drifts silently; delete it, do not refresh it  {#916-dispatch-line-count-no-target}
```

Body actually present (range that skips the start-line end-match):

```
$ awk '/916-dispatch-line-count-no-target/{f=1; next} f && /^### /{exit} f' docs/engineering-journal/LEARNINGS.md | grep '^\*\*' | cut -c1-30
**Context.** The design record
**Evidence.** Preflight F1 at
**Mechanism.** A volatile coun
**Fix.** Recorded F1 and F2 in
**Generalizable rule.** When a
**Refs.** Issue #916 (B4); F1/
```

Six `**` fields restored from merge-base `f30d8678` lines 149-154 (read-only
`git show`, heading line 147 not copied, Fix adapted: counts deleted not refreshed).

## 9. Item 9 — DOC-6 (renamed key)

```
$ grep -c "authored_verdicts" plugins/saga/references/brainstorm-evidence-model.md
3
$ grep -c "grading_status" plugins/saga/references/brainstorm-evidence-model.md
1
$ grep -c "authored_verdicts" docs/engineering-journal/DECISIONS.md docs/engineering-journal/LEARNINGS.md
docs/engineering-journal/DECISIONS.md:1
docs/engineering-journal/LEARNINGS.md:1
```

Both journal lines carry "(the key was renamed `authored_verdicts` on this branch)".

## 10. Item 10 — AM-7 (residual's next step)

```
$ grep -c "fleet_commons" docs/evidence/issue-912/residuals-cycle-7.md
2
$ grep -c "marketplace-install-layout-no-import-path" docs/evidence/issue-912/residuals-cycle-7.md
1
```

## 11. Item 11 — TEST-4/TEST-8 dialogue guard (E2 mutation proof, KTD2 protocol)

Green run after the refactor (`find_dialogue_assertions`, per-file parse,
path-scoped exemption, `<path>:<line>` reports, three seeded tests):

```
$ uv run pytest tests/test_brainstorm_evidence_model.py -q
============================== 6 passed in 0.19s ===============================
```

Backup, then the E2 mutation (restore the unscoped name-based exemption —
`self._own_module = True` unconditionally):

```
$ cp tests/test_brainstorm_evidence_model.py /var/folders/ky/n5fq5mgd5rl4321kxfy3jtvw0000gn/T/opencode/lane-b-scratch/test_brainstorm_evidence_model.py.bak && echo BACKUP-OK
BACKUP-OK
```

Red run — the escape test fails for the right reason (the exemption swallows the
renamed tuple, so no violations are reported), control and self-exemption stay green:

```
$ uv run pytest tests/test_brainstorm_evidence_model.py -q -k "find_dialogue_assertions"
______ test_find_dialogue_assertions_flags_renamed_interrogatives_escape _______
tmp_path = PosixPath('/private/var/folders/ky/n5fq5mgd5rl4321kxfy3jtvw0000gn/T/pytest-of-jefcox/pytest-17145/test_find_dialogue_assertions_1')
    def test_find_dialogue_assertions_flags_renamed_interrogatives_escape(
        violations = find_dialogue_assertions([mod])
>       assert violations != [], (
E       assert [] != []
FAILED tests/test_brainstorm_evidence_model.py::test_find_dialogue_assertions_flags_renamed_interrogatives_escape
================== 1 failed, 2 passed, 3 deselected in 0.09s ===================
```

Restore by copy plus byte-identity check:

```
$ cp /var/folders/ky/n5fq5mgd5rl4321kxfy3jtvw0000gn/T/opencode/lane-b-scratch/test_brainstorm_evidence_model.py.bak tests/test_brainstorm_evidence_model.py && cmp -s /var/folders/ky/n5fq5mgd5rl4321kxfy3jtvw0000gn/T/opencode/lane-b-scratch/test_brainstorm_evidence_model.py.bak tests/test_brainstorm_evidence_model.py && echo RESTORED-BYTE-IDENTICAL || echo RESTORE-FAILED
RESTORED-BYTE-IDENTICAL
```

Post-restore `ruff format` join of three over-split f-strings, then green again:

```
$ uv run ruff format tests/test_brainstorm_evidence_model.py && uv run ruff format --check tests/test_brainstorm_evidence_model.py && uv run pytest tests/test_brainstorm_evidence_model.py -q
1 file reformatted
1 file already formatted
============================== 6 passed in 0.19s ===============================
```

(The backup predates the format-only join; the join is formatting-only, tests green
before and after. `brainstorm-evidence-model.md` Layer 1 + "What this suite does not
prove" updated to the path-scoped exemption.)

## Scoped suite, lints, typecheck (final state)

```
$ uv run pytest tests/test_brainstorm_evidence_model.py tests/test_saga_plugin.py tests/test_handoff_envelope_maturity.py tests/test_saga_docs_coverage.py tests/test_saga_lifecycle_consistency.py tests/test_lint_journal_order.py tests/test_release_triad.py tests/test_release_surface_parity.py tests/test_changelog_heading_lint.py tests/test_release_rituals.py tests/test_manifest_consumer_matrix.py tests/test_workflow_extraction.py tests/test_saga_plan_save_and_routing.py tests/test_brainstorm_scenarios.py -q
============================= 309 passed in 8.32s ==============================
```

```
$ uv run python scripts/lint_test_shape.py tests plugins --prod-module server
lint_test_shape: OK — 301 module(s) checked, no fake-only suites
EXIT=0
```

(The plan's bare `uv run python scripts/lint_test_shape.py` exits 2 — it requires
`paths` plus `--prod-module`; the gate's form above is what runs. See §12.)

```
$ uv run ruff check . && uv run ruff format --check .
All checks passed!
517 files already formatted
```

```
$ uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
Success: no issues found in 346 source files
```

Journal lint, structural (this is the gate's "Engineering-journal ordering lint" step):

```
$ uv run python scripts/lint_journal_order.py
journal-order lint: 5 file(s) checked, VIOLATIONS: 0
```

Journal lint, diff-scoped (plan acceptance form — see §12 plan-defect note):

```
$ uv run python scripts/lint_journal_order.py --base-ref origin/main
docs/engineering-journal/LEARNINGS.md: new entry filed outside the newest section (`## 2026-09-05`) — A guard placed inside the exception handler for a decode tha
docs/engineering-journal/LEARNINGS.md: new entry filed outside the newest section (`## 2026-09-05`) — A regression probe must be sized to the regime that showed t
docs/engineering-journal/LEARNINGS.md: new entry filed outside the newest section (`## 2026-09-05`) — A reserved version number can be taken by a concurrent run b
docs/engineering-journal/LEARNINGS.md: new entry filed outside the newest section (`## 2026-09-05`) — A test that agrees with the defect makes a green suite evide
docs/engineering-journal/LEARNINGS.md: new entry filed outside the newest section (`## 2026-09-05`) — Repairing a finding without reading its second implementatio
docs/engineering-journal/LEARNINGS.md: add a `## <today>` heading at the top and put new entries under it; do not append at the end of the file
docs/engineering-journal/DECISIONS.md: new entry filed outside the newest section (`## 2026-09-05`) — Handoff maturity fail-closed sentinel: `unknown:` prefix ove
docs/engineering-journal/DECISIONS.md: new entry filed outside the newest section (`## 2026-09-05`) — Repository-wide handoff-maturity vocabulary invariant  {#913
docs/engineering-journal/DECISIONS.md: add a `## <today>` heading at the top and put new entries under it; do not append at the end of the file
journal-order lint: 5 file(s) checked, VIOLATIONS: 9
EXIT=1
```

Same 9 violations with the gate's own base (`--base-ref f30d8678`, the merge base
`git merge-base HEAD origin/main` returned). Pre-edit baseline with the same command
was `VIOLATIONS: 0`.

## 12. Plan-defect notes (work complete; acceptance commands at fault, or plan internally contradictory)

1. **DOC-8 acceptance awk cannot return 6 as written.** The range
   `awk '/916-dispatch-line-count-no-target/,/^### /'` starts on the `###` heading
   line that carries the anchor — and that line also matches the end pattern
   `/^### /`, so the range collapses to the single heading line (`head -8` shows
   exactly one line). It returns 0 with the body present and 0 with the bare
   heading. The six-field body is proven by the corrected range in §8 (six `**`
   fields: Context, Evidence, Mechanism, Fix, Generalizable rule, Refs).
2. **KTD6's `## 2026-09-05` headings contradict the lint's newest-section rule on
   this branch.** The 7 orphaned entries are branch-added (absent from
   `origin/main`: `git show origin/main:...LEARNINGS.md | grep -c
   "probe-sized-to-the-defect\|tests-that-pin-fail-opens"` → `0`;
   `.../DECISIONS.md | grep -c "913-maturity-unknown-sentinel"` → `0`), filed by
   cycle 8 under `## 2026-09-01` / `## 2026-08-31` when those were newest. Adding
   any newer date heading — which item 1 explicitly requires for
   `{#912-out-of-root-refused-outright}` — moves them outside the newest section,
   which the lint (under both `--base-ref origin/main` and the gate's merge-base
   form) reports as 9 violations. No action inside this lane reconciles both:
   filing under the existing newest sections would violate KTD6's letter (and only
   defer the conflict to the journal-fold commit, which presupposes the
   `## 2026-09-05` sections exist); moving the 7 entries under the new headings
   would re-date cycle-8 records, and two carry internal `**Date:** 2026-08-30`
   fields contradicting a move. Lane B shipped KTD6's letter (new headings + the
   required entries) and reports the red diff-scoped lint for controller
   adjudication; the structural lint is green. Not a stop-and-surface item in the
   plan's list, reported here with evidence instead of silently substituting an
   approach.
3. **`scripts/lint_test_shape.py` bare form takes no arguments.** The plan's
   `uv run python scripts/lint_test_shape.py` exits 2 (`error: the following
   arguments are required: paths`). Ran the gate's form instead (pasted above).

## 13. Follow-up — controller adjudication of note 2 (relocation, 2026-09-05)

Per `lane-B-adjudication.md`: the guard's own docstring (`check_new_entries`,
lines 112-120) sanctions relocation — identity is the (title, slug) pair, which a
move does not change. Moved the seven branch-added entries under the
`## 2026-09-05` headings by deleting / re-inserting section-heading lines only;
every entry body preserved byte-for-byte, including internal `**Date:**` fields
and `{#slug}` anchors. No entry rewritten.

LEARNINGS.md — five moved below the Lane B entry (most-recent-first); the emptied
`## 2026-09-01` heading removed:

- A regression probe must be sized to the regime that showed the defect
- A test that agrees with the defect makes a green suite evidence of nothing
- Repairing a finding without reading its second implementation …
- A guard placed inside the exception handler for a decode …
- A reserved version number can be taken by a concurrent run …

DECISIONS.md — two moved below the `{#912-out-of-root-refused-outright}` entry;
`## 2026-08-31` retained for the remaining (on-main) entries:

- Handoff maturity fail-closed sentinel: `unknown:` prefix …
- Repository-wide handoff-maturity vocabulary invariant `{#913-…}`

Proof — diff-scoped form with the gate's base (the one permitted `git merge-base`
read; no other git command ran):

```
$ uv run python scripts/lint_journal_order.py --base-ref $(git merge-base HEAD origin/main)
journal-order lint: 5 file(s) checked, VIOLATIONS: 0
EXIT=0
```

Structural form:

```
$ uv run python scripts/lint_journal_order.py
journal-order lint: 5 file(s) checked, VIOLATIONS: 0
EXIT=0
```

Scoped suite and both ruff forms after the move:

```
$ uv run pytest tests/test_brainstorm_evidence_model.py tests/test_saga_plugin.py tests/test_handoff_envelope_maturity.py tests/test_saga_docs_coverage.py tests/test_saga_lifecycle_consistency.py tests/test_lint_journal_order.py tests/test_release_triad.py tests/test_release_surface_parity.py tests/test_changelog_heading_lint.py tests/test_release_rituals.py tests/test_manifest_consumer_matrix.py tests/test_workflow_extraction.py tests/test_saga_plan_save_and_routing.py tests/test_brainstorm_scenarios.py -q
============================= 309 passed in 7.95s ==============================
```

```
$ uv run ruff check .
All checks passed!
CHECK_EXIT=0
$ uv run ruff format --check .
517 files already formatted
FORMAT_EXIT=0
```
