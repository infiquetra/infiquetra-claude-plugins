# Doc review (focused delta) — codex-parity plan 2026-07-19 post-merge refresh

- **Target:** `docs/plans/2026-07-15-codex-cross-runtime-outcome-parity-plan.md`
- **Reviewed revision:** working tree on `outcome/lease-safe-runtime-continuity` at base `6f462cfe`
  (committed together with this artifact; see the commit that carries both)
- **Scope:** the 2026-07-19 refresh delta only. The plan body was authored 2026-07-15 as
  `ready-to-freeze` pending its two prerequisite merges; both merged 2026-07-19 and this refresh
  binds them. The unchanged body is out of scope here.
- **Blocked status:** not blocked
- **One-line verdict:** **READY** — the refresh delta is evidence-backed; zero P0–P3 findings
  remain; ceremony candidate anchor recorded below **awaits operator approval** before the
  `codex-parity` leaf may dispatch.

## Delta reviewed and evidence

| # | Change | Evidence |
|---|--------|----------|
| 1 | Frontmatter `deepened: 2026-07-19` added | Mirrors the `deepened:` convention of the issue-604 plan refresh (2026-07-18) |
| 2 | Summary execution-vehicle paragraph: operator chose Claude-direct cc-workflow (Codex auto vehicle not selected); inputs bound; ready to freeze at U1 | Operator decision recorded in-session 2026-07-19 ("1. this session"); both merges verified below |
| 3 | Claude input bound: PR #622 closing issue #604, merge SHA `97d2fb15dbed7ea210391e3fc293fb0de31dc95e`, Saga 0.103.0, four v1 golden fixtures + `invalid/` on `main` | `gh pr view 622` → MERGED 2026-07-19T00:57:57Z; `gh issue view 604` → CLOSED 2026-07-19T00:57:58Z; `git show 97d2fb15:plugins/saga/.claude-plugin/plugin.json` → 0.103.0; `ls tests/fixtures/outcome-cross-runtime/v1/` → discovery-envelope, canonical-status, handoff-reference, compatibility-halt, `invalid/` |
| 4 | Codex input bound: PR #41 closing issue #33, merge SHA `3723a8183e3ea9c372ad9f34fd18f4170c36d26f`, saga `0.76.0+codex.20260719174556`, fleet-core `0.9.0+codex.20260719174556`, substrate manifest digest `13fe52e3…`, conformance digest pins at `tests/test_lease_settlement_conformance.py:32-34` | `gh pr view 41` → merge SHA + 2026-07-19T20:48:35Z; codex `main` head `3723a81`; `shasum -a 256` of the manifest → `13fe52e36f322357a11fd99104451832e01646f2881ae263b0df990f5bdb140e`; both plugin.json versions read from codex `main`; `grep` confirms broker `f60fd482…` / ledger `34804e26…` at the cited lines |
| 5 | KTD6 seam-deferral decision added, with matching R6 sentence, stop-condition bullet, and completion-gate clause: `outcome.py` `make_dispatcher` NOT rewired to `default_lease_authority()`; `audit_store` ancestor hardening deferred with it to `cross-runtime-acceptance` | Operator decision recorded in-session 2026-07-19 ("2. Lets wait for the final acceptance issue"); `grep -n make_dispatcher plugins/saga/scripts/outcome.py` on codex `main` → line 2048, no lease-authority argument (seam dormant as described) |
| 6 | Verification section: `port_contract.py validate` CLI stages replaced with the per-port pytest gate (`tests/test_outcome_cross_runtime_parity_port_contract.py`); commands aligned to repo norm `PYTHONPATH=. uv run pytest` | The CLI is permanently pinned to the 2026-07-11 external-advisory port (proven during #33 QA, 13 pin errors); codex `docs/engineering-journal/DECISIONS.md:314` "2026-07-19: Lease-Safe Substrate Ports Byte-Faithful, Gates Per-Port"; the substrate port shipped with the same per-port gate pattern (`tests/test_lease_safe_substrate_port_contract.py`, 15 tests) |
| 7 | Expected target paths: per-port gate test file added | Internal consistency with change #6 |
| 8 | Workflow Structure + operating contract converted from the Codex auto form (gpt-5.6 tiers, unreproducible `role_lens_sha256` digests) to the cc-workflow inline form mirroring the approved issue-604 vehicle: six `agent()` lenses (devils-advocate/security/architecture/testing at opus+high; concurrency/event-flow validators at sonnet+medium) as `saga:readonly-verifier` in disposable worktrees, bounded pool of 3, halt-if-Workflow-unavailable, section-bytes approval anchor, #34-specific lens charters | Template: issue-604 plan `## Workflow Structure`/`## Workflow Operating Contract` (executed clean under its approved anchor); `saga:readonly-verifier` present in the session agent roster; `plugins/saga/references/sandbox-spawn-sites.md` exists; table parses 8 rows × uniform 13 columns; root isolation cell reads `isolated-codex-worktree` (this port executes in a fresh worktree of infiquetra-codex-plugins, unlike #604's primary-worktree root) |

## Resolution of the prior digest gap

The prior structure pinned `role_lens_sha256`/`profile_sha256` values that reproduce under no
hashing method present in either repo. The vehicle revision removes that false precision: the
approval identity is now **the SHA-256 of the exact `## Workflow Structure` and
`## Workflow operating contract` section bytes**, the same mechanism the operator approved for
issues 357, 358, 604, and the #33 substrate ceremony.

## Ceremony candidate anchor (awaiting operator approval)

```
c76ef1eea7c23d0242b063d3df9b5365729a95a33a78617cb28460ecd515ca9c
```

Computed over 6306 bytes: from the first byte of the `## Workflow Structure` heading to the byte
before the `## Completion gate` heading. Recompute byte-exact against the committed plan before
launch every round. Dispatch of the `codex-parity` leaf under the outcome's quiesce posture
requires operator approval of this candidate; any model, effort, lens, validator, or vehicle
change afterward requires a newly approved candidate.

**Operator approval:** Jeff, 2026-07-19, in-session ("approved"). The anchor was recomputed
byte-exact against the committed plan at approval time (`c0913b22`, section bytes 6306) and
matched. The approval authorizes dispatch of the `codex-parity` leaf only; the standing quiesce
remains in force for `cross-runtime-acceptance`.

## Findings

None. P0: 0, P1: 0, P2: 0, P3: 0.

## Links

- Plan: `docs/plans/2026-07-15-codex-cross-runtime-outcome-parity-plan.md`
- Issue: infiquetra/infiquetra-codex-plugins#34 (leaf `codex-parity` of `lease-safe-runtime-continuity`)
- Prerequisite merges: infiquetra-claude-plugins PR #622 (`97d2fb15`), infiquetra-codex-plugins
  PR #41 (`3723a818`)
- Substrate handoff data: comment on infiquetra-codex-plugins#34 (merge SHA, versions, digests,
  seam pointer)
- Ceremony template: issue-604 plan workflow sections (executed clean); pattern lineage 357 → 358
  → 604 → #33 substrate ceremony
