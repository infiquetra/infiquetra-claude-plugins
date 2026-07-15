# Outcome proposal: lease-safe runtime continuity

Date: 2026-07-15

Status: approved for execution. Outcome specification revision 2 carries the operator-approved
run-start intent. Every leaf uses the `manual` backend and fail-closed review gates; deployment and
real-profile mutation remain excluded.

## Goal

Ship one coherent control plane in which Claude and Codex can discover and coordinate the same
Outcome without duplicate dispatch, while the surrounding fleet enforces a shared concurrency cap,
accounts for every dispatched unit, fences stale writers, detects stalled work, and reclaims every
resource it opens.

## Why this is the next outcome

The Operations board has 163 cards under `Objective=improve-claude-plugins`: 12 parent Objectives,
their direct sub-issues, and one open unparented card. The two previously prioritized campaigns
(`fleet-integrity-gates` and `intent-envelope-autonomy`) are complete. The next previously identified
dependency chain was #335 concurrency and reclamation. The only open card outside the 12 parent
hierarchies is #579, now in Shaping, and it directly addresses the Claude-to-Codex handoff that
required transcript reconstruction before this proposal.

This proposal combines the #335 safety substrate with #579 as its first high-value consumer. It does
not build a second lease or idempotency house inside #579.

## Proposed DAG

```text
  #350 Concurrency policy ------+
                                +--> #356 Fleet TTL lease broker --> #355 Orphan containment --+
  #351 Dispatch settlement -----+             |                           |                    |
                                              |                           +--> Claude contract -+
                                              |                           |                    |
                                              |                           +--> Codex substrate -+
                                              |                                                |
                                              +--> #357 Liveness --> #358 Teardown --> #353     |
                                                                                         |      |
                                                        Claude contract + Codex substrate +------+
                                                                       |                        |
                                                                       v                        |
                                                               Codex protocol parity -----------+
                                                                                                |
                                                                                                v
                                                                                 Cross-runtime acceptance

  The picture is the transitive reduction. The machine spec retains direct audit edges from #351
  and #356 to their safety consumers so a dependency regression is visible during validation.

  #579 Cross-runtime coordination umbrella
       +---- tracks Claude coordination
       +---- tracks Codex shared substrate
       +---- tracks Codex parity
       +---- tracks cross-runtime acceptance
```

## Dependency decisions

- #350 precedes #356 so the lease broker enforces one declared concurrency policy instead of
  introducing another cap vocabulary.
- #351 can start beside #350 semantically, but is delivered second because both touch Saga release
  surfaces. #356 consumes both merged contracts: concurrency limits from #350 and settlement identity
  from #351.
- #355 follows #356. Their plans must reconcile overlapping write-fencing language: #356 owns the
  broker and token contract; #355 consumes it for quarantine, bridge adoption, and late-writer
  containment.
- #357 consumes dispatch accounting and lease ownership; #358 follows #357 because idle eviction may
  act only on its confirmed liveness results. Both also consume #351/#356 directly.
- The Claude coordination child of #579 follows #351 and #355 so cross-runtime handoff reuses the
  settled dispatch and fencing contracts instead of defining runtime-local substitutes.
- #353 is deliberately late. Its value is independent observation of the finished mechanisms, so
  running it as a capstone turns the outcome's safety claims into a repeatable diagnostic.
- #579 is the tracking umbrella, not an executable release unit. Its four prepared children are the
  Claude compatibility contract, the Codex shared-runtime substrate, the Codex protocol-parity
  release, and the final cross-runtime acceptance proof.
- The Codex substrate follows #355 and ports the merged #351/#355/#356 lease, fencing, and settlement
  contracts while preserving Codex's native `outcome.dispatch.v2` acknowledgement semantics. The
  Codex protocol-parity child follows both that substrate and the Claude compatibility child so it
  can pin both exact merged contracts. Cross-runtime acceptance follows Codex parity and #353.
- Functional dependencies permit some parallel work, but implementation and merge stay serial for
  leaves that change the same plugin release surfaces. This is a delivery serialization overlay, not
  a false semantic dependency in the DAG.

## Value delivered by layer

1. Bounded, dependency-preserving fleet concurrency (#350).
2. No silently lost fan-out units; every dispatch settles or reaches a dead-letter path (#351).
3. Fleet-wide lease ownership and stale-write fencing (#356, #355).
4. Shared liveness and non-skippable teardown (#357, #358).
5. One runtime-neutral lease and settlement substrate shared by Claude and Codex, without replacing
   Codex's protected launch acknowledgement contract (#579's Codex substrate child).
6. Safe Claude/Codex discovery, resume, bounded handoff, and duplicate-dispatch prevention (#579's
   Claude and Codex protocol children).
7. Independent proof that no resource, delegation, or wiring position remains open (#353 plus the
   acceptance gate).

## Deliberate exclusions

- #349 adaptive admission governor: high-value moonshot, but it should consume stable policy,
  settlement, lease, and doctor evidence rather than ship in the same first control-plane cut.
- #352 cache-aware dispatch economics: wait for #333/#467 to prove the cache-residency claim.
- #354 `/optimize max_concurrent`: narrow standalone enhancement, not required for the fleet contract.
- #434 stacked-PR cascade guard: valuable, but one native plan/work leaf closes #340 more honestly
  than wrapping it in this unrelated DAG.
- #333 cache economics: evidence-gated on #467; a strong subsequent outcome if the benchmark clears
  its kill criteria.
- #337 residual integrity work, #341 shared-primitives refactor, #342 authoring standards, and #339
  self-improvement machinery remain valid later campaigns but deliver less immediate operational
  leverage than eliminating duplicate dispatch and leaked resources.
- The four parked #332 authoring/ingestion cards remain outside this outcome except where #579
  explicitly consumes existing Outcome authority semantics.

## Prepared execution waves

Each executable leaf runs the full `saga:plan` -> `saga:doc-review` (fix all findings) -> approved
Verified Workflow -> `saga:code-review` (fix all findings) -> tests/acceptance -> atomic commit/PR/merge
loop. Approval is batched per dependency wave; execution remains autonomous inside an approved wave.

1. #350, then #351. The issues are semantically independent, but both change Saga release surfaces.
2. #356.
3. #355, #357, and #358 in dependency-valid order, with same-repository delivery serialized.
4. The Claude compatibility child and Codex shared-runtime substrate after their respective
   prerequisites are merged; they may proceed independently in isolated worktrees. #353 follows
   #358.
5. Codex protocol parity after both Wave 4 contract producers merge.
6. Cross-runtime acceptance and umbrella/outcome closeout.

All eleven executable leaves now have local implementation plans and zero-finding doc-review gates; the
outcome umbrella itself is tracking-only. Their exact Verified Workflow candidates are parser-valid
and operator-approved; no implementation agent has been launched yet. The two Codex plans
are explicitly `ready-to-freeze`: each gets copied/refreshed in the isolated target repo and bound to
the exact upstream/target refs before its mandatory classification gate. #355 consumes #356's live broker,
resource heads, and token dispositions while retaining only bridge-evidence quarantine, terminal
seals, and read-only orphan projection. #357 consumes #351 facts and #356 resident identity/clock,
keeps fleet-core as the one scoring engine, and leaves destructive action to #358. #358 adds a
broker-owned closing fence, composes the existing ownership/fact/liveness authorities, and makes B8
completion and crash recovery executable without a second ledger or reaper.
#353 then uses strict independent raw-source correlation, preserves the existing tolerant
`/delegation-audit`, and never repairs what it reports.

## Board and issue preparation

- #579 remains the parent tracking card.
- Four Mission Control drafts passed readiness validation and were created after approval: Claude
  compatibility `infiquetra-claude-plugins#604`, Codex shared substrate
  `infiquetra-codex-plugins#33`, Codex protocol parity `infiquetra-codex-plugins#34`, and
  cross-runtime acceptance `infiquetra-claude-plugins#605`.
- The prepared profile requires Operations Status `Shaping`. The operator approved the targeted
  four-card WIP exception; the created cards remain the only new work pulled under that exception.
- A read-only state census found two closed issues still in Shaping (`team-freya#66`,
  `team-mimir#116`) and one closed issue still in Active (`team-mimir#71`). Archiving all three would
  leave Shaping at 26/10 and Active at 7/5, so terminal-card cleanup alone does not clear the gate.
- Creating the four prepared #579 children after that cleanup would put Shaping at 30/10. Starting
  now therefore requires a targeted four-card WIP exception; the alternative is to wait until at
  least sixteen additional Shaping cards leave the column.
- `infiquetra-codex-plugins` has no default project mapping. Its issue must be added explicitly to
  Operations with Objective `improve-claude-plugins`.
- Parent #335 remains open because excluded children #349, #352, and #354 are still open.

## Review gates

The exact operator-facing choices, targeted item IDs, intent envelope, workflow digests, and cleanup
boundary are frozen in `approval-packet.md`.

Before approval or dispatch:

1. Approve the scope and #579-as-umbrella topology, including the four prepared child cards.
2. Choose either the recommended WIP-safe path (clear Shaping capacity before creation) or an explicit
   WIP override for the four children.
3. Approve issue creation and parent/project reconciliation after the WIP gate is satisfied.
4. Approve the exact Wave 1 Verified Workflow candidates and batched per-wave approval posture.
5. Before Wave 3, confirm the resolved #355/#356 ownership boundary in the reviewed #355 plan: #356
   owns fleet leases, delegated tool fencing, and validated worktree reclamation; #355 consumes that
   authority at agy/Saga evidence seams and adds quarantine, terminal seals, and read-only projection.
6. Capture the complete run-start intent envelope: backend, model/effort tiers, verification policy,
   concurrency cap, merge posture, pacing, and spend ceiling.
