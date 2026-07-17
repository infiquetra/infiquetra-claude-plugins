# Code Review — Issue #356 Lease-Aware Teardown Repair

## Verdict

> **PASS.** The post-merge lease-authority bypass and both validated repair findings are closed. No
> P0-P2 finding remains in the reviewed revision.

| Field | Value |
|---|---|
| Target | `issue/356-lease-aware-teardown` against `origin/main` |
| Merge base | `811b04705a1a25b647ef97c4826ed84ab0e133ba` |
| Reviewed revision | `2dcffcd7b0da6269745762c0a0412e1c1f3639ea` |
| Plan | `docs/plans/2026-07-15-issue-356-ttl-lease-broker-plan.md` |
| Work session | `docs/work-sessions/2026-07-16-issue-356-ttl-lease-broker.md` |
| Scope check | CLEAN |
| Blocked | false |

## Scope Check

The repair is limited to lease-aware outcome worktree teardown, its release surfaces, and regression
tests. It does not change the broker protocol, admission policy, or unrelated outcome behavior.

## Plan Completion

| Unit | Status | Evidence |
|---|---|---|
| U5 — worktree ownership and reclamation | DONE, repaired | Exact authority preflight now precedes graph, issue, Git, registry, and broker mutation. |
| U6 — conformance and release closure | DONE | Saga 0.99.1 metadata, changelog, marketplace, journal, and release guards agree. |

COMPLETION: 2/2 repair units accepted.

## Findings

| # | Sev | Finding | Status |
|---|---|---|---|
| 1 | P1 | Generic teardown could remove a lease-bound worktree without broker authority. | closed |
| 2 | P1 | Prune could mutate the graph before validating a mismatched broker or omitted adapter. | closed |
| 3 | P2 | Missing or corrupt managed-path registry state could fall through to raw Git removal. | closed |
| 4 | P1 | Release-contract tests still pinned Saga 0.99.0 and the historical #433 entry as newest. | closed |

The proposed reacquisition race was independently rejected: acquisition refuses an existing expired
lease until exact release, and broker sweep callbacks execute under the broker lock. The proposed raw
team terminal-ID bypass was also rejected because Step B8 intentionally trusts the root coordinator
under the documented threat model.

## Coverage And Validator Evidence

- Independent validators confirmed findings 1-3 and rejected both false-positive candidates above.
- Final authority/prune and managed-path rereviews: PASS with no P0-P2 findings.
- Focused outcome/worktree/ship suite: 117 passed.
- Exact release-contract and release-triad suite: 41 passed.
- Broader release group: 116 passed; release-surface diff guard passed.
- Ruff check, Ruff format check, affected-file mypy, marketplace sync/parity, and `git diff --check`:
  passed.

## Residual Risk

The broker remains host-local and file-backed. A malicious local operator who can rewrite the authority
store or disable hooks remains outside the documented threat model.

## Route

Proceed to repair PR publication, required-check monitoring, merge, exact-head QA/evidence capture, and
outcome harvest.
