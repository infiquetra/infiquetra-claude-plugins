# Document review — issue 1030 removals and saga 1.0.0 release plan

## Review-result contract

| Field | Value |
|---|---|
| Target path | `docs/plans/2026-09-20-issue-1030-removals-and-saga-1-0-0-release-plan.md` |
| Reviewed revision | working tree — the plan was not yet committed when this review ran; it is committed in the same commit as this artifact, so the verdict binds to that commit's version of both files |
| Blocked status | **not blocked** — no `P0` and no `P1` remains |
| Rubrics run | issue phase: the three core rubrics (acceptance criteria clarity, devil's advocate, spec fidelity) and all three conditional extras (context completeness, issue sizing, prerequisite mapping), each fired after reading its applicability condition |
| Cross-family reviewer seat | none — the run record for issue 1030 carries no named `external-reviewer` unit, so no external seat was dispatched and none was invented |
| Linked issue | infiquetra/infiquetra-claude-plugins#1030, under parent #1018 |
| Work-session path | `docs/work-sessions/2026-09-20-issue-1030-removals-and-release.md` (written at the build stage) |
| Override rationale | none; no override was used |

## Readiness summary

The plan can drive implementation. It survived three review rounds, and each round found real
defects — two of which would have caused an implementer following the document literally to delete a
guard or leave a surviving skill pointing at a deleted script.

## Applied fixes, by round

**Round 1 — five fixes.**

The new removal guard now copies the two patterns this repository already proved instead of
inventing a third: scanning shim-resolved paths, from `tests/test_no_lease_broker_readd.py` and
defect 642, and matching each module name in every syntax a caller could use, from
`tests/test_team_emitter_and_spec_table_removed.py`.

The fleet-core version claim was a convention assertion with no evidence; it is now backed by the
plugin's own precedent — version 0.24.0 deleted two modules totalling 10,203 lines with their suites
and took a minor bump (`plugins/fleet-core/CHANGELOG.md:311`).

The `/qa` documentation-model test was named speculatively as "`tests/test_saga_docs_model.py` or its
current name"; the real guard is `tests/test_saga_docs_coverage.py`.

The line-count checkpoint pointed at "the work-session note" with no path; it now names one.

The cc-workflows version row is marked conditional on the operator's answer rather than stated flat.

**Round 2 — four fixes, two of them load bearing.**

`tests/test_team_emitter_and_spec_table_removed.py` matches the `tests/test_team_*.py` pattern the
plan told the implementer to delete, but its subject is that `team_emitter.py` and `spec_table.py`
stay gone — deleting it would remove the guard against re-adding modules this very release removes.
The plan now names it as the one file matching the pattern that must not be deleted.

`scripts/gate.sh` invokes three saga scripts, not two; `lint_gate_absence_contract.py` at line 217
survives and would have been taken by an implementer removing gate steps by pattern.

Five of the 105 script modules were classified by wildcard (`plan_*`, `review_*`) rather than by
name, and `tier_defaults.py` was named nowhere. Every one of the 105 is now named exactly once in
either the removal table or the kept list, checked mechanically.

The plan did not say what happens if the operator never answers either open question; it now says
both stop and report, and names which units can land first.

**Round 3 — one fix, the largest.**

The plan claimed only `/plan` and `/work` carried stale prose. A grep of all thirteen surviving
skills found three offenders: `/plan`'s tier and spend sections, `/retro`'s five references to
removed readers (at `SKILL.md:189`, `:215`, `:239` and `references/retro-passes.md:87-88`), and
`/work`'s instruction at `SKILL.md:521-524` to run
`plugins/team-execution/skills/team-execution/scripts/artifact_pointer.py` — a script the archive
step deletes. `/code-review` was verified clean. The third decision now names all three with line
numbers, and records that two of `/plan`'s sections are generated regions that must be re-rendered
from their contract file rather than hand-edited.

## Remaining findings

| Priority | Finding | Status |
|---|---|---|
| `P2` | The fleet-core shrink lists seven modules as *candidates* for removal rather than deciding each one, leaving the choice to the implementer | Open by design — fleet-commons is consumed by six plugins and both installed trees, so the plan requires each deletion be proved by grep first. Deciding it here without that evidence would be a guess |
| `P2` | The thirteen implementation units are far more than the four-to-eight a Deep plan normally carries | Open by design — the card forbids a phased rollout and the parent's acceptance criteria are judged at one release. The units are separate commits on one branch and one pull request |
| `P3` | The plan names no explicit rollback for the release itself, only for the two plugin trees | Open — the pull request is a single merge commit on `main` and a revert is the rollback, which the repository's own history shows is understood; no reader is likely to need it spelled out |

## Residual risk from limited evidence

The plan's line-count arithmetic — that keeping only the named modules with no severance still leaves
about 15,800 lines — rests on summing recorded per-file line counts, not on running the deletion. The
plan handles this correctly by making the count a measured checkpoint with a stop rather than an
assumption, so the risk is that the build stops and reports, not that it ships something wrong.

The fleet-core shrink and the `/qa` merge-turn check both depend on state that does not exist yet:
issue 1039's rewrite of the `/qa` skill has not merged. The plan records both as checks to run after
that merge rather than as decisions taken now, which is the correct treatment.
