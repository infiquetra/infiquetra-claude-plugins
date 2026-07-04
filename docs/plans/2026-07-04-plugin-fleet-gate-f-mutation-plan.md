# Plugin-Fleet Gate F Mutation Plan (dry-run) — revision 2

- **Date:** 2026-07-04 (rev 2 — reshaped per operator direction: Operations board brought
  inline with Asgard first; reuse `improve-claude-plugins`; **no new Objective options**)
- **Status:** APPROVED and EXECUTED 2026-07-04 — see
  [verification report](plugin-fleet-ideation-2026-07-03/gate-g-verification-report.md)
  (PASS, 0 problems; deviations ledgered)
- **Inputs:** [Gate E Issue Plan](2026-07-04-plugin-fleet-issue-plan.md) (approved) ·
  [execution manifest v2](plugin-fleet-ideation-2026-07-03/gate-f-manifest.json)
- **Scale:** board upgrade + 12 objective parents + 126 leaves, ~989 serial mutations,
  est. 35–50 min runtime

## Target shape (the Norns pattern, verified live on Asgard/team-norns)

Three grouping layers, exactly as The Norns runs on Asgard:

1. **Objective field** = program identity: the existing Operations option
   **`improve-claude-plugins`** on all 138 cards. No Objective option is created, renamed, or
   removed; the other 3 existing options are untouched.
2. **12 objective parent issues** (the "Norns Inc-N" layer) — labels `objective` +
   `hermes-not-actionable`, never dispatched.
3. **126 leaves** as native sub-issues of their parents (largest parent = 20 children;
   GitHub cap 100). Progress rolls up via GitHub's sub-issue bars on the 12 parents.

All 138 cards go on **Operations (#3)** (repo's mapped board). Waves = milestones
(`wave-1/2/3`); tiers = labels (`tier-structural`/`tier-quick-win`/`tier-moonshot`).

## S-pre: Operations board upgrade (Asgard as the example)

Live census (verified 2026-07-04): Operations holds **27 cards** — 10 Todo/open,
13 Todo/closed, 3 Done/closed, 1 no-status/closed. **Zero cards in In Progress or Blocked**,
so the status migration is trivial.

| Step | Mutation | Detail |
|---|---|---|
| U1 | Status options **add** | Append `Idea`, `Shaping`, `Ready`, `Active`, `Verify` — existing options (`Todo`, `In Progress`, `Blocked`, `Done`) passed back byte-identical **with their IDs** so no card loses status. Post-check: 4 originals survive with unchanged IDs, else HALT. |
| U2 | Migrate 24 cards | 10 Todo/open → `Idea`; 13 Todo/closed + 1 no-status/closed → `Done` (closed cards parked in Todo are stale). Per-card `flow set-field`. |
| U3 | Status options **remove** | Re-submit list without `Todo`, `In Progress`, `Blocked` (all now empty — verified by re-census immediately before). Final vocabulary = Asgard's exactly: `Idea / Shaping / Ready / Active / Verify / Done`. |
| U4 | **Risk field create** | New single-select `Risk` = `Low / Medium / High / Critical` (Asgard-identical, `createProjectV2Field` — purely additive). Sidecar risk maps directly (program uses Low/Medium/High). |
| U5 | Milestones + labels | Create `wave-1/2/3` milestones (repo has none); `flow verify-label` for 3 tier labels + `objective` + `hermes-not-actionable`. |

Deliberately **not** copied from Asgard: `Mode`, `Jeff Needed`, `Target Repository`,
`Transfer Target` — those encode Asgard's team mechanics, not board vocabulary. Say the word if
you want any of them too. `Priority` and `Work Type` stay as-is on Operations.

U1/U3 are the only mutations touching shared board schema. Both use the query-with-IDs →
resubmit → re-verify procedure (field option IDs rotate; never cached — flow SKILL hard rule).

## Execution sequence (Phase G, serial, checkpointed — no fan-out)

Ledger: `docs/plans/plugin-fleet-ideation-2026-07-03/gate-g-ledger.jsonl` (one line per
completed op). Resume = replay ledger, skip done. Halt on first unexpected error. Never
recreate a slug already in the ledger (belt: exact-title search before every create).

- **S0:** read-only preflight snapshot, then U1→U5 above.
- **S1 Objective parents (12):** author 12 prepared draft pairs from the template below
  (mechanical, from `issue-map-final.json`), `issue create-prepared --yes` — **pilot one,
  verify on GitHub, then the rest**. Fallback if readiness blocks `objective`-type drafts:
  `gh issue create` from the same body (ledger-flagged as fallback-path).
- **S2 Parent placement (12):** `board add --project operations` → set-field
  `Objective=improve-claude-plugins`, `Status=Idea` → `gh issue edit --milestone <wave>`.
- **S3 Leaf creation (126):** `issue create-prepared docs/sdlc-issue-drafts/plugin-fleet/
  <slug>.md --yes`, wave order (56/50/20) — pilot one first. Sidecar `approval_state: null`
  proceeds without the approval gate (verified `sdlc_manager.py:4049-4053`).
- **S4 Leaf placement (126):** `board add` → set-field `Objective=improve-claude-plugins`,
  `Status=Idea`, `Risk=<sidecar risk>`.
- **S5 Hierarchy (126):** `flow link-sub-issue` child→parent (numbers from ledger;
  idempotent, 422 = already linked = success).
- **S6 Metadata (126):** one `gh issue edit --milestone <wave> --add-label tier-<tier>` each.
- **S7 Verification sweep (read-only):** counts (12/126), ledger↔GitHub parity, every leaf has
  exactly one parent, Objective/Status/Risk parity vs manifest, milestone totals 56/50/20,
  sub-issue bars render on all 12 parents, the 27 pre-existing cards still hold correct
  statuses. Emits `gate-g-verification-report.md`. Mismatch = HALT + report, no auto-repair.

## Objective parent body template (S1)

```markdown
# objective: <title>

**Mission:** <mission from issue map>
**Wave:** <wave> · **Program:** plugin-fleet ideation 2026-07-03 (Gate E approved 2026-07-04)

## Sub-issues
Native sub-issue links (rendered by GitHub's sub-issue panel).

## Definition of Done
All sub-issues closed or explicitly re-triaged; mission outcome verified against the
Gate E plan (docs/plans/2026-07-04-plugin-fleet-issue-plan.md).
```

## Failure posture & rate limits

Serial ≈989 ops vs 5,000/hr REST budget — comfortable. On 403/429: sleep 60s, retry once,
else HALT with ledger intact. `create-prepared` readiness block: HALT that slug, continue
others, report in S7. Rollback: issues closable, links/fields reversible, ledger is the exact
undo list; U1–U4 board-schema steps are additive or verified-safe and would be left in place
(they are the "bring Operations inline" goal in their own right).

## What Gate F approval authorizes

Executing S0–S7 exactly as written, serially, from this session or a Sonnet session — ledger +
manifest + drafts are the full contract; no conversation context required. Anything outside
this document comes back to you first.
