# Cross-runtime acceptance — post-codex-re-freeze run (objective #639, DoD clause 3)

**Run:** 2026-07-26T17:33:18Z · **overall_verdict: `fail`** · 12 pass / 2 fail / 0 halt
**Bundle:** `cross-runtime-acceptance.json` · sha256 `c91eaa385f6f95919082912a93e3ec55bd9b764b9096c28d4303383c397f2b77`

Harness: `tools/run_cross_runtime_outcome_acceptance.py` at claude `b464d090`. Both runtimes were
supplied as clean detached worktrees at the exact pins — `require_clean_pinned` verifies
`HEAD == pin.sha` and refuses a dirty tree, so neither primary checkout was touched.

| Runtime | SHA | saga | fleet-core |
|---|---|---|---|
| claude | `b464d090fccb59d0ff862f273902f1653f1d8835` | 0.115.0 | 0.23.0 |
| codex | `d0982fec60465b35e3ae5a15cf5e69197e4bf7f5` (PR #53, the #45 re-freeze) | 0.80.0+codex.20260726031557 | 0.12.0+codex.20260726031557 |

The run was executed with `INFIQUETRA_FLEET_LEASE_ENFORCEMENT` explicitly unset. That variable
survives as a stale export in some interactive sessions; an acceptance run about governed leases
executed with lease enforcement disabled would prove nothing.

## The result is two-sided — read both halves

### codex#45 did what it was chartered to do

`race-codex-first` and `race-simultaneous` both **PASS**. Those are the two legs that defect #628
(cross-runtime double dispatch) documented as failing, and turning them green was the stated purpose
of the codex re-freeze. This run is the first measured evidence that it worked.

### Two different legs are now red, and they are not #45's doing

| Scenario | Req | Verdict | Error |
|---|---|---|---|
| `handoff-negatives-claude-issued` | R4 | **fail** | `RegistryCorruptError: leases.0f0045a7…: unknown field(s): isolation` |
| `handoff-negatives-codex-issued` | R4 | **fail** | `RegistryCorruptError: leases.2e58f0ff…: unknown field(s): isolation` |

Both failures occur on the **codex read side** — in the first leg codex is the receiver; in the
second, codex's own attempt 2 reads a registry that by then carries a claude-written lease.

## Root cause — verified, not inferred

Measured directly against the two pinned trees:

| | claude `b464d090` | codex `d0982fe` |
|---|---|---|
| `lease_broker.py` | 4731 lines | 4249 lines |
| `isolation` references | **21** | **0** |
| forward-compat / tolerance references | **4** | **0** |

- Claude **#616** added `isolation` to the lease record: it is a member of `_LEASE_KEYS`
  (`lease_broker.py:159`), normalized by `_agent_isolation()` (`:289`, whose docstring cites
  "#616 KTD2"), and carried on the lease dataclass (`:904`).
- Claude **#617** added bounded forward-compatibility — unknown fields are *preserved* within a
  tolerance capacity rather than rejected (`:1465`, `:1997`), with an explicit operator
  down-migration path (`:4435`, citing "#617 R8/KTD4").
- Codex has **neither**. Its `lease_broker.py` still rejects any unknown field outright (`:353`).

The asymmetry is the whole story. Claude carries a back-compat shim for a record *missing*
`isolation` (`:930-931`: `if set(raw) == _LEASE_KEYS - {"isolation"}: raw["isolation"] = None`), so
the codex→claude direction survives. Codex has no matching tolerance for a record *carrying*
`isolation`, so the claude→codex direction hard-fails.

**This is not a regression in codex#45.** #45 re-froze the #627 seam contract and ported the COR3
worktree lease-authority subsystem; it did not touch the lease registry schema. The red is new
because *claude* moved: the previous 14/14 green run (2026-07-20, recorded under
`docs/validation/lease-safe-runtime-continuity/`) pinned claude saga **0.106.1**, which predates
#616 and #617 entirely. The `isolation` field did not exist in that tree.

This is the KTD5 upstream-first pattern behaving exactly as designed: the root cause landed in
`infiquetra-claude-plugins` first (#616, #617 — both CLOSED), and codex has not yet re-frozen that
surface.

## Remedy — and the one thing not to do

The fix is for codex to port **#617's registry forward-compatibility**, so its reader tolerates
unknown fields generically.

**Do not patch codex to recognize `isolation`.** That is a standing scope rule: teaching codex one
specific claude field trades a general forward-compatibility gap for a point fix, and the next field
claude adds reproduces this failure verbatim. Forward-compat is the contract; `isolation` is just the
first field to exercise it.

## Bearing on objective #639

DoD clause 3 — *"cross-runtime acceptance harness re-run green after the codex re-freeze"* — is
**not satisfied**. It is recorded here as documented truth rather than worked around, per the
acceptance plan's failure rule: failures retain artifacts and file or reopen the owning defect
without production edits. The failing run's workdir was retained by the harness.

Clause 1 (all nine sub-issues closed) is satisfied. Clause 2 (a governed, armed-hook Workflow run
end-to-end) has no committed artifact anywhere under `docs/` on `main` and remains unevidenced.
