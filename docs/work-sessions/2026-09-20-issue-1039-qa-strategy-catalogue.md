# Issue 1039 — `/qa` as a prescribed strategy catalogue

**Branch:** `issue/1039`, from `origin/parent/1018` at `61da4b1c`. A child of parent 1018: no pull
request of its own; the coordinator merges this branch onto the integration branch.

**Plan:** `docs/plans/2026-09-20-issue-1039-qa-strategy-catalogue-plan.md`
**Doc review:** `docs/reviews/doc-review-issue-1039-2026-09-20.md` — nine findings, all fixed, none
open. The gate passed with no override.

**Versions shipped:** saga `0.171.0` → `0.172.0`, fleet-core `0.29.0` → `0.30.0`. Both re-read from
`origin/parent/1018` immediately before the bump.

**`change_kinds`:** `["behavior", "docs", "test"]`. Behaviour is in the list, so the hard test gate
applies and every feature-bearing unit ships with tests. It does: eighty-nine in the new file, plus
the retargeted contract, status-card and release-step tests.

## What was built, by unit

**U1 — the catalogue and the two schemas.** `plugins/saga/references/qa-catalogue.yaml` holds ten
rows; `qa-profile.schema.json` and `qa-envelope.schema.json` hold the two shapes. The loader
refuses a row missing a column by naming both, refuses an unknown proof boundary, and refuses a row
that ships no driver and names no reason.

**U2 — selection.** The required set is computed from the profile's file patterns first, then
filtered by the boundary ladder (`hermetic ⊂ branch-preview ⊂ non-production`), and only then is
the advisory judgment asked. Its answer is unioned through fleet-core's existing widen-only union,
so the declaration is a floor the model may raise and never lower. The new `qa-strategies` verb in
`jev_verbs.py` carries one question per catalogue row.

**U3 — preflight.** Sums the catalogue's estimates against the profile's ceiling and checks the
declared secret handles. Over the ceiling, or missing a credential, the **whole** selection refuses
and zero drivers run.

**U4 — the envelope and the drivers.** Five drivers ship; five strategies are declared without one
and return `blocked` carrying a stated reason and a revisit condition. Redaction runs inside the
driver before the envelope exists, on fleet-core's pattern set plus the bearer-token and
authorization-header shapes.

**U5 — the verdict, the route, the record.** Pure arithmetic over three values. A `fail` routes to
the build loop; a **required** `blocked` routes to the operator. The block is written under the run
record's top-level `qa` key, the documented extension point.

**U6 — the command line and this repository's profile.** `select` / `run` / `verdict`, a
`--boundary` flag defaulting to `non-production`, and six distinct exit codes. This repository's
`qa` block declares `cli-smoke` and `installed-surface`, both required.

**U7 — the prose, the removals, the release surfaces.** The skill and command rewritten; the two
references renamed with `git mv` and rewritten; `qa_health_score.py` and its test deleted; the
corpus guard, the status-card projection and its tests retargeted.

**Outside the plan's units, and named as such:** the repair to
`release_step.record_functional_test` (below) and the retarget of `status_card.project_qa` (below).

## The end-to-end run — acceptance criterion 15

Run against this repository's own profile at the `non-production` boundary:

```
verdict: pass          route: close          exit code 0
cli-smoke          passed   2 declared invocation(s) exited zero
installed-surface  passed   2 installed plugin root(s) resolve 0.161.0, 0.27.0
                            and carry every expected surface
```

Published as a comment on issue 1039
(`https://github.com/infiquetra/infiquetra-claude-plugins/issues/1039#issuecomment-5748930959`),
and the verdict written to the run record. Two strategies reported `passed`, which is what the
criterion asks for; a specification satisfied only by `blocked` runs would have proved nothing.

**That first live run found two bugs the eighty-six passing tests did not.** The
`installed-surface` driver pooled every plugin's version into one set, so saga beside fleet-core
read as "the roots do not agree" on a healthy machine; and it demanded every declared plugin carry
every declared surface, so it wanted saga's `commands/qa.md` from fleet-core. Both need a profile
naming two plugins to appear, and every unit fixture named one. Both are fixed, both have
regression tests written from what the live run reported, and the lesson is in `LEARNINGS.md` under
`{#1039-live-run-found-two-driver-bugs}`.

## The release-step repair

The card's own criterion is "a missing required environment yields `blocked`, never `passed`", and
`release_step.record_functional_test` could still report `passed` for a scenario list holding
nothing but `blocked` entries: it validated all three states and then computed its status from the
failed list alone.

Five tests were written **first** and watched fail on the unrepaired code. Every one reported
`assert 'passed' == 'blocked'` — the hazard reproducing exactly. The repair returns `blocked` for a
required blocked scenario (no repair cycle counted, because no build loop repairs a credential),
`passed-with-proof-debt` for an optional one, and treats a scenario that does not say which it is
as required.

## The status-card retarget, which the plan had deferred

The plan deferred teaching `status_card.project_qa` the new verdict, on the grounds that its
existing guard degraded safely. `test_ae10_status_card_single_emitter_routing` forced the question:
it requires the `/qa` skill to name the single emitter and its projection, and the projection
parsed a health score that no longer exists.

The choice was to drop `/qa` from the single-emitter rule — creating the first status surface
outside the one renderer — or to retarget the projection. The projection was retargeted, with its
five `project_qa` tests and their fixtures, and the decision is recorded under
`{#1039-status-card-follows-the-verdict}`.

## The two declared narrowings, kept visible

`app-ui` at a simulator target and `hosted-surface` ship **no driver**. Both are declared in the
catalogue, both return `blocked` carrying a stated reason, and both name the condition that
reopens them: the first repository whose profile declares them. The reason is that no application
surface, hosted page or browser target exists here to exercise a driver against, and an unexercised
driver is the silent skip this redesign exists to remove wearing a new name. This is in the
changelog entry as well as here, per the coordinator's instruction.

## One more consequence the full suite found

`plugins/saga/scripts/gate_absence_baseline.json` pinned three uncovered gate sites for
`plugins/saga/skills/qa/SKILL.md`. The rewrite removed all three, so the baseline entry went stale
and `test_gate_absence_lint_reports_zero_violations` red with "file has no uncovered gate site
(baseline pins 3) — remove it from the baseline". The entry was removed, which **tightens** the
guard rather than weakening it: the qa skill now has no allowance to spend.

## What the first full suite found — five cross-skill contracts

The rewrite dropped prose that four other test files require of this document, and only the whole
suite saw it. Each is restored, and each was a real requirement rather than an artefact:

- **The board's `Verify` stage relationship** (`test_verify_entry_contract`, two tests). `/qa` is
  the activity that stage holds, and the schema block in the lifecycle repository is the single
  authority for the entry condition. The no-deployable route relaxes the deployment requirement and
  never the merge requirement, which the prose has to say in those words because a paraphrase of a
  board rule is a second, unversioned copy of it.
- **The sandboxed verify-class spawn** (`test_sandbox_spawn_sites`, and
  `test_inventory_guard_covers_brainstorm`, which fails as a cascade of it). A spawn from this step
  passes the read-only verifier in a disposable worktree, which is what keeps "reads behaviour,
  never writes code" a property rather than a promise.
- **The step it continues into** (`test_skill_continuation_endings`, two tests). `/qa` continues
  into `/retro` on a pass, and the continuation has to appear in the document's ending, where a
  reader stops reading.

## Checks run

| Check | Result |
|---|---|
| `uv run ruff check .` | pass |
| `uv run ruff format --check .` | pass |
| `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` | pass, 388 files |
| `uv run pytest tests/test_qa_strategies.py` | 89 passed |
| `uv run pytest tests/test_release_step.py` | 38 passed |
| `uv run pytest tests/test_saga_plugin.py` | 58 passed |
| `uv run pytest tests/test_status_card.py` | 71 passed |
| `uv run python scripts/check_release_surface_parity.py` | all plugins in parity |
| `uv run python scripts/sync_marketplace.py --check` | matches the plugin fleet |
| `uv run python marketplace/validator/validate.py` | 15 plugins, 0 errors |
| `uv run python scripts/lint_journal_order.py --base-ref <merge-base with main>` | 0 violations |
| `uv run python tools/release_surface_diff_guard.py --base-ref origin/parent/1018` | run after the version-bump commit |
| the whole suite at the merged head | see below |

`scripts/gate.sh` was **not** run: the coordinator runs it after the merge.

## Guards watched failing before they were trusted

- The catalogue-to-verb drift guard: renaming one verb key reds it; restoring the key greens it.
- The retargeted contract guard: changing one runnable line in the skill reds it with
  "the 'select' subcommand must be shown"; restoring it greens it.
- The five release-step tests: all five red on the unrepaired code with `'passed' == 'blocked'`.

## Questions answered from the coordinator's message

Every one below came from the coordinator's stage-two message, recorded here as its source.

| Question the skill would ask | Answer taken |
|---|---|
| Resume or mint a saga | Resume `issue-1039`; never mint a second |
| Branch | Stay on `issue/1039` |
| Execution backend | `inline`, as the plan's frontmatter says; no other backend offered or entered |
| Doc-review gate | Passed with nothing open; no override needed or permitted |
| Complexity triage | The documented default for a fresh build: large, so the task list is built from the plan's U-IDs |
| Round-N detection | The documented default: no `pr_refs`, so this is a fresh build, not a round-N re-entry |
| Board move | The documented `Active` / `Implementing` move, submitted through the reconcile controller; it reported `written` with `field: Stage+Status` |
| Code review | None in this stage; deferred to the parent pull request by the coordinator |
| The two declared narrowings | Accepted as the plan states them, and kept visible here and in the changelog |
| The release-step hazard | Mine to repair in this stage, test-first, watched failing |
| Versions | Next minor above `origin/parent/1018` at the moment of the bump, re-read then |
| Gate | Not run here; the coordinator runs it after the merge |

## Next step

The coordinator merges `issue/1039` onto `parent/1018` and runs the full gate. The single code
review happens at the parent pull request.
