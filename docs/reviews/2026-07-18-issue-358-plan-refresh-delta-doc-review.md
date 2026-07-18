# Doc review (focused delta) — issue-358 plan 2026-07-18 post-merge refresh

- **Target:** `docs/plans/2026-07-15-issue-358-non-skippable-teardown-reclamation-plan.md`
- **Reviewed revision:** working tree on `outcome/lease-safe-runtime-continuity` at base `824428f5`
  (committed together with this artifact; see the commit that carries both)
- **Scope:** the 2026-07-18 refresh delta only. The plan body was reviewed READY at
  `docs/reviews/2026-07-15-issue-358-non-skippable-teardown-reclamation-plan-doc-review.md`
  (all P0–P3 fixed) and an API-drift survey against merged main (post-`77f56894`) verified every
  #351/#356/#357 API reference in the unchanged body holds exactly (liveness engine, events
  projection, liveness protocol, lease broker `sweep`/`inspect_resource_head`/owner-state,
  `run_fact.v1`, `dispatch-settlement`); the unchanged body is out of scope here.
- **Blocked status:** not blocked
- **One-line verdict:** **READY** — the refresh delta is evidence-backed; zero P0–P3 findings
  remain; ceremony candidate anchor recorded below awaits operator approval before dispatch.

## Delta reviewed and evidence

| # | Change | Evidence |
|---|--------|----------|
| 1 | R13/U6 version rungs: team-execution target corrected from "2.19.0 → 2.20.0" to "2.20.0 → 2.21.0"; fleet-core 0.15.0 and Saga 0.102.0 targets confirmed unchanged | Merged main `plugins/*/.claude-plugin/plugin.json`: fleet-core 0.14.0, saga 0.101.0, team-execution 2.20.0; #357 itself bumped team-execution 2.19.0→2.20.0 in PR #619 (`77f56894`) |
| 2 | Problem Frame current-state rewrite: Phase B now ends at #356's minimal `Step B8: Stop and release resident leases`; #358 extends it, does not introduce it; call chain corrected to `lease_protocol.py teardown` → `release_session_if_terminal` + broker `sweep` | `plugins/team-execution/skills/team-execution/SKILL.md:572` heading verified byte-exact on merged main |
| 3 | Sibling-safety wording: #355 recorded as merged | `a1dc0c2a` = PR #614, committed 2026-07-17, verified via `git log` |
| 4 | Workflow Structure + Operating Contract vehicle revision: Codex auto form (gpt-5.6 tiers, six unreproducible `role_lens_sha256` digests, MultiAgent V2 caveats) replaced with the cc-workflow inline form mirroring the operator-approved issue-357 ceremony — six `agent()` lenses (devils-advocate/security/architecture/testing at opus+high; concurrency/event-flow validators at sonnet+medium) as `saga:readonly-verifier` in disposable worktrees, bounded pool of 3, halt-if-Workflow-unavailable, section-bytes approval anchor | Template: issue-357 plan `## Workflow Structure`/`## Workflow Operating Contract` (approved anchor `453fa2d1…`); `saga:readonly-verifier` present in the session agent roster; `plugins/saga/references/sandbox-spawn-sites.md` exists; table parses 9 rows × uniform 14 columns |
| 5 | Validator-tier prose (~line 552) aligned to the new table (sonnet-medium validators, opus-high reviewers) | Internal consistency with the revised table |
| 6 | Safe fix applied during this review: summary line 28 "operator-approved Verified Workflow" (Codex-era term) reworded to name the cc-workflow ceremony sections | Supported by change #4; no semantic change |

## Resolution of the prior digest gap

The prior structure pinned six `role_lens_sha256`/`profile_sha256` values that reproduce under no
hashing method present in this repo (no merged code computes or validates that field; sibling plans
reuse identical values). The vehicle revision removes that false precision entirely: the approval
identity is now **the SHA-256 of the exact `## Workflow Structure` and `## Workflow Operating
Contract` section bytes**, the same mechanism the operator approved for issue-357.

## Ceremony candidate anchor (awaiting operator approval)

```
04cf1694e1d1cc94c8e414fcfdfaec129a2b080d275485fc4283f51057e77c51
```

Recomputed byte-exact after every edit in this delta. Dispatch of the sub-358 leaf under the
outcome's quiesce posture requires operator approval of this candidate; any model, effort, lens,
validator, or execution-class change afterward requires a newly approved candidate.

## Findings

None. P0: 0, P1: 0, P2: 0, P3: 0.

## Links

- Plan: `docs/plans/2026-07-15-issue-358-non-skippable-teardown-reclamation-plan.md`
- Prior full review: `docs/reviews/2026-07-15-issue-358-non-skippable-teardown-reclamation-plan-doc-review.md`
- Issue: infiquetra/infiquetra-claude-plugins#358 (leaf `sub-358` of `lease-safe-runtime-continuity`)
- Ceremony template: issue-357 plan sections approved under anchor `453fa2d1…`
