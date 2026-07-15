# Doc Review - Claude cross-runtime Outcome contract plan

One-line verdict: **READY** - all P0-P3 findings were fixed in the plan and prepared issue source;
implementation remains upstream-, operator-, and exact-workflow-gated.

## Review-result contract

- **Target:** `docs/plans/2026-07-15-claude-cross-runtime-outcome-contract-plan.md`
- **Reviewed revision:** uncommitted outcome worktree based on
  `a20cc3ce6d740a4891bddba71f7e8f2856620655`
- **Blocked:** no document-readiness blocker; no issue, board item, workflow, agent, or validator was
  launched
- **Classification:** parent-derived, cross-runtime authority and compatibility plan
- **Rubrics:** all issue cores plus applicable context, sizing, prerequisite, security-boundary, and
  cross-repository-release extras
- **Linked:** `infiquetra/infiquetra-claude-plugins#579`, `infiquetra/infiquetra-claude-plugins#604`, and
  `claude-cross-runtime` in the lease-safe runtime continuity DAG
- **Review artifact:** this file

## Applied fixes

The review found thirteen actionable gaps or unsafe assumptions and fixed all thirteen.

| ID | Priority | Status | Applied fix |
|---|---|---|---|
| D579C-1 | P1 | fixed | Split same-clone coordination from cross-clone reconstruction. A second clone receives canonical completion/candidate-frontier status but explicitly no transient state or mutation authority. |
| D579C-2 | P1 | fixed | Identified current `outcome-bundle/1` import as an authority violation: it writes a bundled spec and replays cache dispatch/completion facts into another repo. `export` is now exactly a deprecated alias of `discover`; `import` always rejects portable authority. |
| D579C-3 | P1 | fixed | Rejected a serialized handoff as a bearer token. Public JSON is only an opaque reference; acceptance must reopen protected same-clone evidence and verify its seal plus live broker/settlement facts. |
| D579C-4 | P1 | fixed | Put repository, committed-blob, spec, protocol, and capability validation before all store creation, quarantine-capable readers, broker/fact writes, dispatch, board/GitHub writes, or spec saves. |
| D579C-5 | P1 | fixed | Added canonical GitHub repository identity and committed-ref/blob discovery, with fork, wrong-host, credential URL, dirty-spec, ID mismatch, and divergent-ref ambiguity failures. |
| D579C-6 | P1 | fixed | Scoped every mutating handoff to one exact operation and one subplot. `advance-one` uses an allowlist; Outcome-wide, multi-frontier, and `--loop` handoffs are forbidden. |
| D579C-7 | P1 | fixed | Replaced caller-asserted issuer/freshness with broker-derived ownership, a 300-second maximum lifetime, a 30-second future-skew limit, exact operation/subplot binding, and current fence checks. |
| D579C-8 | P1 | fixed | Removed an invented generic coordinator-pool assumption. Attached mutation consumes #356's final Outcome-dispatch resource and capacity class, keyed to the exact leaf/attempt. |
| D579C-9 | P1 | fixed | Closed transfer crash gaps with protected offer, accept-intent, successor fence, and accept-commit records under #355's resource guard. Same-receiver retry is idempotent; another receiver cannot steal an intent; dead receivers require TTL plus dead-owner recovery. |
| D579C-10 | P2 | fixed | Defined portable “equivalent status” precisely. It is a byte-stable canonical projection from committed Git plus GitHub, not a false reconstruction of cache-local dispatched/running state. |
| D579C-11 | P2 | fixed | Avoided stale parallel-release version reservations. The PR refreshes the merged #351/#355/#356 schemas, rebases before release edits, and takes the next available Saga minor once. |
| D579C-12 | P2 | fixed | Named closed schemas, byte/node/output/time caps, duplicate-key rejection, symlink/file-kind checks, privacy denylist, real-Git topologies, deterministic interleavings, and no-mutation snapshots. |
| D579C-13 | P2 | fixed | Updated both the issue source and prepared issue body to carry the same cross-clone read-only, scoped protected handoff, and legacy-bundle retirement constraints; named neutral fixtures at `tests/fixtures/outcome-cross-runtime/v1/` for the separate Codex PR. |

## Readiness summary

The plan is one cohesive Claude release unit: identity/discovery, canonical read projection,
protected same-clone transfer, one-leaf attached dispatch, and retirement of the conflicting legacy
import path. Those pieces share one authority boundary and cannot ship safely as independent partial
PRs. The Codex consumer remains separately releasable and separately reviewable.

| rubric | score | result |
|---|---:|---|
| acceptance criteria clarity | 10/10 | every parent/child acceptance row maps to production-shaped positive, skew, race, replay, wrong-repo, or cross-clone proof |
| devil's advocate | 10/10 | bearer-token, cross-clone dispatch, broad-frontier handoff, copied-cache, and newest-ref shortcuts are explicitly rejected |
| spec fidelity | 10/10 | committed spec plus GitHub remain canonical; git-common-dir/broker/settlement stay transient coordination only |
| security and authority boundary | 10/10 | committed identity preflight, protected local evidence, current fence, one-use scope, caps, and mutation snapshots are decision complete |
| issue sizing | 9/10 | five implementation units in one Claude PR; downstream Codex and acceptance are correctly excluded |
| prerequisite/release mapping | 10/10 | #351/#355/#356 ownership is explicit, parallel siblings are non-blocking, and release collision handling is named |

## Evidence verified

- `outcome_store.resolve_common_dir()` makes linked worktrees share one cache but serializes no
  repository identity.
- `outcome_store.acquire_lease()` documents a stale-reclaim TOCTOU and explicitly scopes itself away
  from cross-host authority; it cannot be promoted into the cross-runtime guarantee.
- `resume()` currently loads working-tree spec plus cache and its docstring still admits cache-loss
  completion gaps.
- `export_bundle()` includes cache completion events and dispatch-ledger records.
- `import_bundle()` accepts a bundle in a different repo, saves its spec, and replays both transient
  fact classes; the current regression test asserts that behavior.
- `advance()` dispatches the ready frontier, so a handoff that authorizes generic `advance` would be
  broader than one leaf and could not prove the requested single-dispatch boundary.
- `outcome_orchestrator.barrier_satisfied()` already owns GitHub completion predicates and can support
  a non-materializing canonical projection without inventing a second completion implementation.
- The #356 plan gives Outcome dispatch a broker adapter and persistent resource heads; #355 adds a
  resource-scoped guard and protected late/superseded evidence semantics. The reviewed plan consumes
  their final merged shapes and adds no sibling lease or dispatch settlement.
- The Workflow Structure parses against installed roles/profiles, passes full-review selection, and
  has digest `4d670236995dc6a600a8214c4bd4238197af6783f976ca1749e066d6873a6fcd`.
- Focused current-state regression suite: 149 passed across Outcome command, store, dispatcher,
  completion, and orchestrator tests. `git diff --check`: clean after fixes.

## Remaining findings by priority

None. P0: 0, P1: 0, P2: 0, P3: 0.

## Residual risk

All safety-substrate dependencies are planned rather than merged. Implementation must refresh their
actual resource identity, protected-evidence write protocol, and settlement schema; incompatible
merged behavior requires a revised plan and exact workflow approval rather than an adapter guessed
from these drafts.

Cross-host mutating continuation remains deliberately unsupported. The current authority model has
no networked atomic active-dispatch source; GitHub completion evidence can reconstruct what finished,
but cannot prove another host has no in-flight dispatch. That is an honest limitation, not an
implementation omission in this child.
