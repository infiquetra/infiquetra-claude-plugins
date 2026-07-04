# Gate G Verification Report — plugin-fleet materialization

- **Date:** 2026-07-04 · **Result: PASS — 0 problems across all S7 checks**
- **Ledger:** `gate-g-ledger.jsonl` (every mutation journaled; slug→issue-number map authoritative)

## What exists on GitHub now

- **12 objective parents** #332–#343 (labels `objective` + `hermes-not-actionable`, fallback
  create path — prepared pipeline structurally rejects objective type via `_TEAM_CHOICES`).
- **126 leaves** #344–#469: 117 via `issue create-prepared` (pilot #344), 9 non-actionable
  (exploration/context-update) via the sanctioned fallback with canonical label sets.
- **Zero duplicates** — 138 distinct issue numbers, ledger↔GitHub parity exact.

## S7 checks (all read-only, all green)

| Check | Result |
|---|---|
| Parent links (native sub-issues, exactly one parent, correct objective) | 126/126 |
| Sub-issue rollup counts on the 12 parents | 14/9/20/11/5/6/10/7/14/15/10/5 — all match |
| Status field | `Idea` on all 138 |
| Objective field | `improve-claude-plugins` on all 138 |
| Risk field (leaves) | Medium 104 · High 12 · Low 10 |
| Milestones (leaves) | wave-1: 56 · wave-2: 50 · wave-3: 20 |
| Tier labels | applied in S6, 0 failures |
| Pre-existing this-repo cards | 17 Done/closed — statuses intact post-upgrade |

## Board upgrade (S0) end state

Operations (#3) Status vocabulary = Asgard's exactly (`Idea/Shaping/Ready/Active/Verify/Done`);
Risk field (Low/Medium/High/Critical) added; 3 wave milestones; 27 pre-existing cards migrated
(10 open→Idea — other repos' cards included; 17 closed→Done in this repo). One incident during
U1: the option update cleared all existing Status selections despite byte-identical resubmission
— HALT fired, per-item snapshot enabled full restore; see LEARNINGS
`{#projectv2-option-update-clears-selections}`.

## Deviations from the letter of the plan (all ledgered, end state as approved)

1. U2/U3 reordered after the U1 selection-clearing discovery (schema converges first, statuses
   written once).
2. 12 objectives + 9 non-actionable leaves via `gh issue create` fallback (pipeline's team/type
   matrix rejects them structurally) — the plan's named fallback path.
3. All 126 draft bodies transformed pre-create to satisfy the real card validator (8 required
   H3 sections; +3 at high risk) — validated locally at 126/126 before any create; see LEARNINGS
   `{#three-schema-drift-issue-creation}`.
4. S4 field-sets used the same GraphQL mutation `flow set-field` wraps, resolving the item list
   once (~10× fewer API calls); S5 links used `flow link-sub-issue` as written.
5. 7 sidecars had invented team values (saga/platform→campps); 3 labels created on demand
   (quick-win/ci/saga); non-actionable label sets corrected to `_ISSUE_TYPE_LABELS` canon.
