# Doc review (focused delta) — issue-604 plan 2026-07-18 post-merge refresh

- **Target:** `docs/plans/2026-07-15-claude-cross-runtime-outcome-contract-plan.md`
- **Reviewed revision:** working tree on `outcome/lease-safe-runtime-continuity` at base `742d1c0c`
  (committed together with this artifact; see the commit that carries both)
- **Scope:** the 2026-07-18 refresh delta only. The plan body was reviewed READY at
  `docs/reviews/2026-07-15-claude-cross-runtime-outcome-contract-plan-doc-review.md` (13/13 P1/P2
  findings fixed, 0 remaining); the unchanged body is out of scope here. Three grounding surveys
  this session (Claude outcome-module map, codex-plugins consumer map, journal/#579 decomposition)
  verified the unchanged body's API references hold on merged main — including byte-identical
  `resolve_common_dir` + `saga-outcomes` store namespace in both repos and Codex
  `outcome.dispatch.v2` / protected-launch-receipt semantics matching R5-R7's assumptions.
- **Blocked status:** not blocked
- **One-line verdict:** **READY** — the refresh delta is evidence-backed; zero P0–P3 findings
  remain; ceremony candidate anchor recorded below awaits operator approval before dispatch.

## Delta reviewed and evidence

| # | Change | Evidence |
|---|--------|----------|
| 1 | Hard-upstream row: descriptive #351/#355/#356 rows replaced with exact merged modules — `dispatch_settlement.py` over `run_ledger.py` (`run_fact.v1`), `fleet_commons/orphan_evidence.py`, `fleet_commons/lease_broker.py` (`fleet_lease_registry.v1`, protocol 2, host-scoped root, `TokenState`, `broker_epoch`+`fencing_sequence`) | Verified on merged main `30bde209`: `lease_broker.py:29-30,42,379`; `dispatch_settlement.py:1257,1340,1500,1514`; `run_ledger.py:1,43`; all four paths present |
| 2 | Parallel-siblings row: #357 (PR #619) and #358 (PR #621) recorded merged; main carries saga 0.102.0 / fleet-core 0.15.0 / team-execution 2.21.0 | `gh pr view`: #619 MERGED 2026-07-18T15:17:19Z, #621 MERGED 2026-07-18T20:48:19Z; `plugin.json` versions read directly |
| 3 | U3/U4 Files rows + Files Expected to Change note: "post-#35x module" placeholders replaced with exact consumed-unmodified paths | Same path/API verification as #1; "(consumed, unmodified)" marking keeps the no-sibling-authority boundary (KTD4) visible in every unit |
| 4 | U4 approach: attach/attend/live-attach term-disambiguation note added | `outcome_intent.validate_live_attach` at `outcome_intent.py:618` (#433); `attend()` at `outcome.py:1607` — both verified byte-exact on merged main |
| 5 | Workflow Structure + Operating Contract vehicle revision: Codex auto form (gpt-5.6 tiers, six unreproducible `role_lens_sha256` digests, MultiAgent V2 caveats) replaced with the cc-workflow inline form mirroring the operator-approved issue-357/358 ceremony — six `agent()` lenses (devils-advocate/security/architecture/testing at opus+high; concurrency/event-flow validators at sonnet+medium) as `saga:readonly-verifier` in disposable worktrees, bounded pool of 3, halt-if-Workflow-unavailable, section-bytes approval anchor; lens charters rewritten for #604's authority/replay/identity surfaces | Template: issue-358 plan sections (approved anchor `04cf1694…`, recomputed byte-exact this session); `saga:readonly-verifier` present in the session agent roster; `plugins/saga/references/sandbox-spawn-sites.md` exists; table parses 8 data rows × uniform 13 columns |
| 6 | Test Strategy tier prose and Summary vehicle sentence aligned to the new table (sonnet-medium validators, opus-high reviewers; "Verified Workflow" wording removed) | Internal consistency with the revised table; repo-wide grep confirms zero residual `gpt-5.6`/`role_lens_sha256`/`Verified Workflow` references in the plan |
| 7 | Frontmatter `deepened: 2026-07-18` added | Plan-sections contract (`references/plan-sections.md`, frontmatter spec) |

## Resolution of the prior digest gap

The prior structure pinned six `role_lens_sha256`/`profile_sha256` values that reproduce under no
hashing method present in this repo (no merged code computes or validates that field; sibling plans
reuse identical values). The vehicle revision removes that false precision entirely: the approval
identity is now **the SHA-256 of the exact `## Workflow Structure` and `## Workflow Operating
Contract` section bytes**, the same mechanism the operator approved for issue-357 and issue-358.

## Ceremony candidate anchor (awaiting operator approval)

```
214431cf7e3c8099ed54f2ee087ff4178b42c362b6d4cb4ca94e2c9cbf5d234f
```

Computed over 5842 section bytes (from the `## Workflow Structure` heading to the horizontal rule
before `## Completion Gate`, exclusive — the same extraction that reproduces issue-358's approved
`04cf1694…` at 5329 bytes). Recomputed byte-exact after every edit in this delta. Dispatch of the
`claude-cross-runtime` leaf under the outcome's quiesce posture requires operator approval of this
candidate; any model, effort, lens, validator, or execution-class change afterward requires a newly
approved candidate.

**Operator approval:** Jeff, 2026-07-18, in-session. The anchor was recomputed byte-exact against
the committed plan at approval time (`e0dc114f`, section bytes 5842) and matched. The approval
authorizes dispatch of `claude-cross-runtime` only, sequenced before `sub-353` (approved under its
own anchor `d10d602e…`); the standing quiesce remains in force for `codex-substrate`.

## External opinion

`engine_offer.py offer --stage doc-review --attended`: advisory second-opinion suggested
(`prompt_required: true`, opus/high, intent second-opinion). Operator accepted the offer in the
review package (Jeff, 2026-07-18, in-session); dispatched through the guarded codex wrapper
(run `20260718T224036Z-8a851690ef1e`, read-only, `mutation_detected: false`, exit 0).

**Result — `external_opinion.state=applied`:** codex verdict **clean** for this plan and this
artifact. Every part-(a) API/path/version claim confirmed with line-exact repository evidence, the
Workflow table shape/pool/remediation/tier coherence confirmed, every evidence-table row judged
supported, and the anchor independently reproduced (`214431cf…`, 5842 bytes) by codex's own
extraction. Zero findings against #604; `claude_adjudication: n/a` (nothing to adjudicate). The
readiness verdict above stands unchanged.

## Findings

None. P0: 0, P1: 0, P2: 0, P3: 0.

## Links

- Plan: `docs/plans/2026-07-15-claude-cross-runtime-outcome-contract-plan.md`
- Prior full review: `docs/reviews/2026-07-15-claude-cross-runtime-outcome-contract-plan-doc-review.md`
- Issue: infiquetra/infiquetra-claude-plugins#604 (leaf `claude-cross-runtime` of
  `lease-safe-runtime-continuity`; parent #579)
- Ceremony template: issue-358 plan sections approved under anchor `04cf1694…` (delta review
  `docs/reviews/2026-07-18-issue-358-plan-refresh-delta-doc-review.md`)
