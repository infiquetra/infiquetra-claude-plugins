# Doc review — closure-gate plan (#397)

Verdict: **READY** — all findings were evidence-backed and fixed in place; nothing remains open.

## Review-result contract

- **Target:** `docs/plans/2026-07-12-closure-gate-plan.md`
- **Reviewed revision:** working tree (plan file untracked at review time; leaf worktree
  `.claude/worktrees/agent-a5f4ff1e1e705e220`, branched from `main` at `e19a9f9`)
- **Blocked status:** NOT blocked — zero unresolved P0/P1
- **Linked issue:** infiquetra/infiquetra-claude-plugins#397 (sub-397 of outcome
  `evidence-integrity`, consumer of #398's evidence ledger)
- **Linked plan saga:** `issue-397` (git-ignored, machine-local)
- **Review artifact:** `docs/reviews/2026-07-12-closure-gate-plan-doc-review.md` (this file)
- **Rubric engine:** not run — the rubric phases are `idea`/`issue`/`spec`; no plan-phase rubric
  exists, so the readiness-skeptic pass is the operative review for a `docs/plans/` artifact
  (matches the sibling #398 plan-review's own precedent).
- **External-engine offer:** not run — this leaf executes single-agent, non-interactively, per
  its own operating boundary; no operator available mid-flight to answer an engine-offer prompt.

## Findings and dispositions

Three findings surfaced during an independent self-review pass; all three were evidence-backed
safe fixes (already-implied semantics made explicit, or an unverified claim replaced with a
verified one) and applied in place — none invents a new decision.

| ID | Pri | Finding | Status |
|---|---|---|---|
| D1 | P1 | The issue's own Verification section runs `pytest -k <substring>` for six exact strings (`fail_overwritten_by_unexplained_pass`, `fail_superseded_with_justification`, `stale_sha_halts`, `missing_evidence_halts`, `matching_sha_pass_closes`, `golden_fixture`) plus `gate_blocks_harvest` in a second file — the plan's test-scenario prose never pinned actual test function names to these substrings, so an implementer following the plan literally could write correctly-behaving tests whose names don't contain the required substrings, making the issue's own DoD checks silently match zero tests ("no tests ran" reads as a false pass) | FIXED — U1 and U2 test-scenario lists now name every required test function explicitly (e.g. `test_closure_gate_golden_fixture_fail_overwritten_by_unexplained_pass`, which satisfies both the `golden_fixture` and `fail_overwritten_by_unexplained_pass` filters in one test), and the Verification lines now spell out that each filter must select at least one test |
| D2 | P2 | KTD2 asserted `head_ref_oid` "remains resolvable" after a merged PR's branch is deleted, without checking it against a real PR — a claim stated as fact rather than verified, against this same session's own Validation Discipline standard | FIXED — verified empirically against this outcome's own sibling PR #567 (merged; `gh pr view --json headRefOid` still returns `22a66d1825...`) whose head branch `work/398-evidence-ledger` is confirmed deleted (`git ls-remote --heads origin work/398-evidence-ledger` returns empty); the verified evidence (not just the conclusion) is now in KTD2 |
| D3 | P2 | The mechanical `recommend-backend` override (team-execution → inline) was recorded only in the saga tick, not in the plan document itself — a future reader of the plan alone would not see that the tool's own signal disagreed | FIXED — added a "Recorded override (recommended-vs-chosen)" paragraph under Execution prerequisites, naming the mechanical result, why it fired (`phase_count>=4`, an explicitly OUTPUT-BLIND volume proxy per the tool's own docstring), and the override rationale |

## Evidence verified during review

- All path:line citations spot-checked against the actual files: `outcome_orchestrator.py:145-172`
  (harvest/barrier_satisfied), `outcome_spec.py:214/308` (`leaf_saga_id` field + `from_dict`),
  `outcome_github.py:272-282` (`head_ref_oid`), `outcome.py:1117,1128` (the two production
  `harvest()` call sites, both already closing over `repo_root`), `outcome-spec.md:54` (the
  `evidence` pass-through-map row this plan gives its first concrete schema),
  `qa/SKILL.md:299`/`code-review/SKILL.md:341` (`REVIEWED_SHA=$(git rev-parse HEAD)`), evidence-
  ledger plan R10 (verbatim: "sub-397 (closure gate)... extend this module without schema
  surgery").
- Confirmed no `tests/test_outcome_orchestrator.py` exists yet (the issue's own AC implies a new
  file, not a modification), and confirmed all ~11 sibling `tests/test_outcome_*.py` files that
  call `harvest()`/`barrier_report()` today, so KTD6's backward-compatibility claim has a concrete,
  enumerable regression surface (listed in U2's Verification).
- Confirmed `/qa` and `/code-review` already write through `evidence_ledger.py` in `main` (grep on
  `plugins/saga/skills/{qa,code-review}/SKILL.md` finds the live `write --check-id
  qa|code-review` invocations) — the plan's premise that the ledger producer side is already
  shipped, not a dependency this issue must also build, is confirmed rather than assumed.
- `head_ref_oid` post-branch-deletion resolution verified live against PR #567 (see D2).

## Residual risk

- The supersession-justification convention (`payload["supersession_reason"]`, KTD3) is enforced
  only by `closure_gate.py`'s own read logic, not by any change to `evidence_ledger.write()` itself
  — a producer could theoretically omit it by mistake. This is the plan's own documented,
  intentional HALT-not-degrade failure direction (Risks & Dependencies), not an oversight; flagged
  here only so `/code-review` re-examines it isn't quietly loosened during implementation.
- The `unresolvable-close-sha` HALT for a non-code node with no override and no PR is a plan-
  authored edge case beyond the issue's literal five acceptance checks — reasonable and
  HALT-not-degrade-consistent, but not itself issue-mandated; confirm at `/code-review` that it
  doesn't block a legitimate non-code leaf that has no need for evidence gating (it doesn't, since
  such a leaf simply declares no `required_checks`, per R8).
