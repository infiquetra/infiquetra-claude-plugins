# Doc review - TTL lease broker and write-fencing plan (#356)

Verdict: **READY AT OPERATOR GATE** - all issue-rubric, lifecycle, safety, and executable-readiness
findings were fixed in place; zero P0-P3 findings remain. Implementation is intentionally blocked
until the outcome and exact Verified Workflow candidate are approved.

## Review-Result Contract

- **Target:** `docs/plans/2026-07-15-issue-356-ttl-lease-broker-plan.md`
- **Reviewed revision:** working tree on `outcome/lease-safe-runtime-continuity`, base
  `a20cc3ce6d74`
- **Blocked status:** document is not blocked; execution is blocked at the explicit operator gates
- **Linked issue:** infiquetra/infiquetra-claude-plugins#356, outcome node `sub-356`
- **Linked outcome:** `docs/outcomes/lease-safe-runtime-continuity/proposal.md` (local review draft)
- **Review artifact:**
  `docs/reviews/2026-07-15-issue-356-ttl-lease-broker-plan-doc-review.md`
- **Override rationale:** none
- **External panel:** not invoked; the panel is opt-in and the operator did not request external egress

## Applied Fixes

The review reconciled the issue's stale fixed-cap assumption with #350, selected fleet-core as the
single cross-plugin authority, separated agent/worktree pools, defined exact registry and fencing
contracts, closed pre-spawn and workflow-batch races, added two-signal foreground release, replaced
wall-clock expiry with boot-aware monotonic TTL, required dead-owner proof before destructive reap,
hardened store paths, made the current V2 mutation boundary truthful, and repaired the stale
event-flow role-lens binding.

## Issue-Rubric Results

All three core issue rubrics and all applicable extras ran inline. Scores reflect the remediated plan.

| Rubric | Score | Finding | Status |
|---|---:|---|---|
| acceptance criteria clarity | 9 | The issue's cap-three wording conflicted with #350's base/read-only/aggregate policy and did not distinguish agent from worktree capacity | FIXED - shared normalized limits, exact resolved snapshots, separate pools, and AC mapping added |
| devil's advocate | 8 | A broker plus every adapter is a broad PR, but landing a partial broker would leave bypasses while claiming fleet safety | ACCEPTED - six dependency-ordered units, one core, thin adapters, and hard stop conditions bound the slice |
| spec fidelity | 9 | The original issue assumes TTL plus fencing but leaves clock, process-liveness, and in-flight tool boundaries unstated | FIXED - boot-aware monotonic expiry, authorization-vs-physical concurrency, tool-boundary fencing, and dead-owner reap proof are explicit |
| context completeness | 10 | The live hook order, filesystem-less workflow lane, existing reaper, and fleet-commons shim materially change the implementation | FIXED - each live seam and owner is named with files and tests |
| issue sizing | 8 | Core state, hooks, three adapters, worktrees, conformance, and three release surfaces are large | ACCEPTED - all are required to satisfy the issue's every-spawn-site contract; #358's generic teardown remains excluded |
| prerequisite mapping | 10 | The issue named only #350 but delivery also collides with #351's Saga release surfaces | FIXED - behavioral dependency and post-Wave-1 serialization/baseline versions are explicit |
| security and destructive operations | 9 | A symlinked registry or TTL-only reaper could redirect/trigger destructive removal | FIXED - no-follow ownership/mode checks and Saga registry plus dead-owner validation precede reaping |

## Readiness Findings

Every P0-P3 readiness finding was fixed in the plan.

| ID | Priority | Finding | Status |
|---|---|---|---|
| D356-1 | P1 | The event-flow lens digest was stale, so the installed closed Workflow Structure parser rejected the candidate | FIXED - bound current digest `2e20ab69...f356`; parser and selection policy pass |
| D356-2 | P1 | `SubagentStart` lacks parent `tool_use_id`; FIFO claim plus parent-only release could free the wrong live same-type child | FIXED - provisional slots are fungible and claimed leases require both trusted child-terminal and exact parent-completed timestamps before removal |
| D356-3 | P1 | A hook cannot infer an `ExecutionSpec`, so “consume #350 policy” was not implementable and risked a second numeric authority | FIXED - fleet-core owns normalized defaults/record; Saga retains #350 resolution and passes the digest-bound result; broker never re-resolves |
| D356-4 | P1 | Wall-clock TTL and expiry-only worktree sweep could expire on a clock jump or delete beneath a live in-flight process | FIXED - same-boot monotonic TTL plus boot identity; destructive sweep additionally requires dead-owner or explicit terminal proof |
| D356-5 | P2 | The workflow claimed named profiles guaranteed read-only workspace access although current V2 may reapply the parent permission profile | FIXED - `mutation=none` is the authorization boundary; root baseline/diff audit fails any child mutation |
| D356-6 | P2 | Directory/file modes alone did not close store-root, lock, or registry symlink substitution | FIXED - effective-user ownership, no-follow/exclusive creation, same-directory atomic replace, and symlink tests added |
| D356-7 | P2 | #356's minimum team-execution Step B8 adoption could silently consume the broader #358 teardown issue | FIXED - #356 owns only lease stop-confirm-release-sweep; #358 retains the generic non-skippable teardown contract |
| D356-8 | P1 | Removing a released lease erased the resource's last token, so downstream evidence handling could reject a late writer but could not distinguish closed from superseded as #355 requires | FIXED - persistent per-resource fencing heads retain the last grant; four-way disposition is derived from head plus live lease without a status field |
| D356-9 | P2 | Frontmatter used `status: proposed`, which is outside the plan artifact's active/completed lifecycle contract | FIXED - plan status is `active`; operator approval remains a separate execution gate |
| D356-10 | P1 | The initial broker default lived under `~/.claude/fleet-leases`, so the planned Codex parity runtime either had to depend on a forbidden Claude host path or open a second registry | FIXED - fleet authority now resolves through `INFIQUETRA_FLEET_STATE_DIR`, safe absolute XDG state, then `~/.local/state/infiquetra`; Claude/Codex/PLUGIN_DATA fallbacks are forbidden and consumers compare a redacted root-identity digest before admission |

## Evidence Verified

- `plugins/fleet-core/scripts/fleet_commons/` is the shared cross-plugin module home; Saga and
  team-execution already load it through vendored fleet-commons shims.
- `outcome_store.py` documents an unfenced stale-reclaim TOCTOU; `outcome_worktrees.py` owns the
  cap-four registry and validated `reap_worktree` path.
- The Codex adapter runbook rejects active Claude host paths and assigns shared policy to fleet-core;
  a `~/.claude` broker default would therefore make the cross-runtime same-host contract impossible
  without a second authority.
- `plugins/saga/hooks/hooks.json` wires `Agent|Task` before-use, delegated mutation before-use, and
  `SubagentStop`; `delegation_stop_audit_hook.py` can block a first stop attempt.
- Claude's current hook contract supplies `tool_use_id` to pre/post tool events, `agent_id` and
  `agent_type` to subagent events, does not supply parent `tool_use_id` to `SubagentStart`, cannot
  block `SubagentStart`, and runs matching hooks in parallel. Source:
  https://code.claude.com/docs/en/hooks
- Generated workflow JavaScript has no filesystem access; `/work` already uses a trusted root driver
  for persistence, so batch pre-reservation belongs before its `Workflow(...)` call.
- The Workflow Structure has eight steps and digest
  `62d5bff8e79f0330744f250358cbbc6910dcb82a7e31bf1a44f216747932430d`.
  Installed role/profile binding passes, full-review selection passes, and both
  `validate-concurrency` and `validate-event-flow` are required.
- Verified-workflow readiness resolves
  `docs/plans/2026-07-15-issue-356-ttl-lease-broker-plan.md#workflow-structure` as ready.

## Remaining Findings by Priority

None. P0: 0, P1: 0, P2: 0, P3: 0.

## Residual Risk

Hook fencing cannot preempt a provider inference or Bash command already executing when TTL expires;
it denies the next supported tool boundary. The plan makes that limitation explicit and requires
dead-owner evidence before destructive worktree removal. File locking is host-local by design; this
issue does not claim distributed coordination across machines. Independent implementation review,
concurrency validation, event-flow validation, and later `/code-review` remain mandatory.
