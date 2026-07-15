# Lease-safe runtime continuity approval packet

Prepared: 2026-07-15

Status: approved. The operator approved the recommended defaults in the Codex outcome thread on
2026-07-15. This authorizes exactly the scope, mutations, workflow digests, merge posture, cleanup
boundary, and exclusions recorded below; changed workflow candidates or expanded operational scope
require fresh approval.

## Scope approval

Approve the 11 executable nodes in `outcome-spec.json` and #579 as a tracking-only umbrella with four
new children:

1. Claude-side cross-runtime compatibility contract.
2. Codex shared lease, fencing, and dispatch-settlement substrate.
3. Codex cross-runtime protocol parity and release.
4. Cross-runtime acceptance proof.

Parent #335 stays open because excluded children #349, #352, and #354 remain open. Parent #579 stays
open until all four children, #353, acceptance evidence, and QA complete.

## Board and issue approval

Live Operations read at 2026-07-15T07:46:02Z:

```text
Shaping  28/10  over limit
Ready     0/10
Active    8/5   over limit
Verify    2/5
```

Three closed cards remain in nonterminal workflow columns:

| Card | Current status | Project item ID | Proposed action |
|---|---|---|---|
| `infiquetra/team-freya#66` | Shaping | `PVTI_lADODdfJoc4BZLMKzgx9Hf4` | targeted archive |
| `infiquetra/team-mimir#116` | Shaping | `PVTI_lADODdfJoc4BZLMKzgymJH8` | targeted archive |
| `infiquetra/team-mimir#71` | Active | `PVTI_lADODdfJoc4BZLMKzgyE3QM` | targeted archive |

The generic Mission Control `board archive` command is not the correct operation: its dry-run would
archive 145 cards already in Done and would not target these three stale nonterminal cards. After
approval, root uses three explicit `gh project item-archive 3 --owner infiquetra --id <item-id>`
calls and verifies each card is absent. That leaves Shaping 26/10 and Active 7/5.

Creating the four prepared children then places Shaping at 30/10. Approve one of:

- **Recommended:** targeted four-card WIP exception, recorded on #579; pull no unrelated work.
- Wait until at least sixteen other Shaping cards leave the column.

Prepared drafts, all readiness-passed with zero blocking gaps:

```text
docs/sdlc-issue-drafts/2026-07-15-claude-side-cross-runtime-outcome-authority-disc-2.md
docs/sdlc-issue-drafts/2026-07-15-codex-shared-lease-fencing-and-dispatch-settleme.md
docs/sdlc-issue-drafts/2026-07-15-codex-side-cross-runtime-outcome-parity-and-rele.md
docs/sdlc-issue-drafts/2026-07-15-cross-runtime-outcome-acceptance-proof-for-lease.md
```

After creation, root links every issue natively beneath #579, explicitly adds both Codex issues to
Operations, sets Objective `improve-claude-plugins`, Status `Shaping`, and Risk `High`, validates all
four cards, and updates the DAG/plans from prepared-task IDs to live issue references.

## Proposed run-start intent

```intent-envelope
{
  "schema_version": 1,
  "run_mode": "unattended",
  "ceremony_gates": {
    "reviews_required": "gate",
    "merge": "auto",
    "deploy_nonprod": "gate"
  },
  "source": "issue-capture",
  "authored_by": "codex",
  "backends_permitted": [
    "manual"
  ],
  "degrade_policy": "halt"
}
```

`reviews_required:gate` makes recorded review evidence mandatory for every code leaf's done
transition. (`auto` would let the leaf pipeline vouch for itself and is incompatible with the
operator's explicit plan/doc-review/code-review requirement.) `merge:auto` authorizes root to
squash-merge only after all gates pass. `deploy_nonprod:gate` keeps deployment and real-profile
mutation outside this approval. `backends_permitted:[manual]` matches all 11 gated nodes;
`degrade_policy:halt` prohibits backend substitution. Root renders a fresh schema-valid envelope with
`authored_at` only after operator approval, then commits it to the outcome spec before dispatch.

## Exact Verified Workflow candidates

Every candidate uses root-only implementation/integration; four read-only logical review lenses
(`devils-advocate`, `security`, `architecture`, `testing`) on `review_high` with `gpt-5.6-sol/high`;
and only the named validators on `test_medium` with `gpt-5.6-terra/medium`.

| Leaves | Required validators | Workflow digest |
|---|---|---|
| #350 | concurrency | `7b84779088a63ef8e6c893a1246bd7744922b1b3a7c938a6bf3833e883e04146` |
| #351 | concurrency, event flow | `4c7114ab6317aad550977f37a0c3992dd9667ee4e57e23d58e750b9b39057848` |
| #356, #355 | concurrency, event flow | `62d5bff8e79f0330744f250358cbbc6910dcb82a7e31bf1a44f216747932430d` |
| #357, #353 | event flow, scenario | `4e993a3e3e4a9ce6b953995fdc5d58e74d7be26da2304e95d342d373a7d230b3` |
| #358, Claude compatibility | concurrency, event flow | `4d670236995dc6a600a8214c4bd4238197af6783f976ca1749e066d6873a6fcd` |
| Codex substrate, Codex parity | concurrency, event flow | `1ca06d3b15280fa357d69d8d9e588d90b660a36473ac04af87e4d03b39378aba` |
| Acceptance | concurrency, event flow, scenario | `4e50f995b5398188054462b0c36ffb8350e8c9a787ec42764771bc4457829e7a` |

Approve one posture:

- **Recommended:** approve every exact digest now. Execution pauses only if a table, role, lens,
  class, runtime agent, model, effort, validator, permission posture, or digest changes.
- Per-wave approval: root previews and waits before every dependency wave.

No silent fallback is allowed. Requested role/model/effort must match host-issued runtime evidence.
Agent-lens rows have `mutation=none`; root takes before/after workspace snapshots and rejects any
child-created change. At most three children run concurrently. A new attempt gets a fresh context.
Root fixes every P0-P3 finding and reruns affected roles; three unsuccessful remediation cycles stop
and page the operator. Named agents are retained through their issue gate and released before the
next issue.

## Delivery and cleanup approval

Recommended standing authorization:

- One atomic issue branch/PR per executable leaf; an additional outcome-bootstrap documentation PR
  records live child refs and the approved intent before #350 starts.
- Squash merge after required checks, review gates, release-surface parity, and live merge readback.
- Close the completed issue and reconcile its Operations card to Done after merge proof.
- Delete only clean merged issue worktrees and local/remote issue branches after verifying the merge
  SHA; retain the outcome coordinator worktree/branch until final acceptance and report merge.
- Do not deploy, mutate a real/default profile, copy credentials, use production data, force-push,
  or delete unrelated/pre-existing worktrees or branches.
- No hard spend ceiling. Sol/high is confined to judgment reviews; Terra/medium to validators. Three
  remediation cycles are the per-issue escalation bound.

## Operator response contract

`approve recommended defaults` approves the scope, targeted stale-card archives, four-card WIP
exception, four issue creations/linkage/board reconciliation, proposed intent, every exact workflow
digest, squash/close/Done behavior, clean issue branch/worktree cleanup, no hard spend ceiling, and
the no-deploy boundary above.

Any override should name the section and replacement. Approval never extends to a changed workflow
digest, production deployment, credential mutation, force push, or unrelated cleanup.

## Approval receipt

- Response: `approved`
- Interpreted as: `approve recommended defaults`
- Recorded: 2026-07-15
- Intent captured: `outcome-spec.json` revision 2; live issue references materialized in revision 3
