---
title: Doc review — issue #677 lease broker retirement plan
type: doc-review
date: 2026-07-30
target: docs/plans/2026-07-30-issue-677-lease-broker-retirement-plan.md
reviewed_revision: working tree at ddba53a0
linked_issue: https://github.com/infiquetra/infiquetra-claude-plugins/issues/677
blocked: false
---

# Doc review — issue #677 lease broker retirement plan

**Verdict: all 12 findings are resolved. The operator settled every open decision on 2026-07-30 — no
questions remain open.** `D1` (no documentation-only unit) and `D2` (`team-execution` → 3.0.0) were
confirmed as decided. `D7` was closed on re-checking the source: its premise was wrong, and U2 and U3
run in parallel. `D12` was found after decomposition and folded into the existing units. Everything the plan measured, it measured correctly — all 15 line counts,
all three plugin versions, and all six issue states are exact against the working tree at commit
`ddba53a0`. What it missed is a whole category of work (agent-facing documentation) and the true blast
radius of one rename.

The operator's instruction for this review was to fix everything found. Nine findings were safe fixes
backed by tree evidence. The remaining two (`D1` unit resizing, `D2` target versions) are judgment calls
about plan text rather than shipped code, so they were decided and their reasoning written into the plan
where it can be argued with, instead of being left as open questions. Both are flagged below as
operator-overridable.

- **Target:** `docs/plans/2026-07-30-issue-677-lease-broker-retirement-plan.md`
- **Reviewed revision:** working tree at `ddba53a0` (plan file is untracked; not yet committed)
- **Rubric review:** not applicable — the rubric engine supports `idea`, `spec`, and `issue` phases only,
  and this is a plan under `docs/plans/`. Readiness-skeptic pass run in full.
- **Engine offer:** `engine_offer.py offer --stage doc-review` returned `prompt_required: false`
  (stored preference, `intent: none`). No external-engine panel dispatched.
- **Blocked:** no. `D1` and `D2` were `P1` open findings; both are now decided in the plan with stated
  reasoning. `/work` is unblocked, subject to the operator overruling either decision.

## What verified clean

Stated so the fixes below are read in proportion. None of these needed changing:

| Claim | Result |
|---|---|
| Deletion payload of 10,203 lines across four files | **exact** (4,731 + 1,578 + 2,709 + 1,185) |
| All 11 consumer-file line counts, plus the saga wrapper and `concurrency_policy.py` | **all exact** |
| Plugin versions `fleet-core` 0.23.0, `saga` 0.122.0, `team-execution` 2.23.0 | **all exact** |
| Four open defects #645, #646, #647, #661; #648 open as an *enhancement*; #642 already closed | **all confirmed via `gh`** |
| `orphan_evidence.py` has zero production consumers under `plugins/` | **confirmed** — its only three referencing files are all tests, and all three are accounted for |
| KTD12's three bare `production_adapters(broker)` sites | **confirmed** at `team_teardown_hook.py:80`, `team_teardown.py:1710`, `:1724` |
| `outcome_worktrees.py:674` is the only production reaper | **confirmed** |
| KTD9's hard-raise loader, KTD4's `renew_batch` at `workflow_emitter.py:187` | **confirmed** |
| `INFIQUETRA_FLEET_LEASE_ENFORCEMENT` has exactly one reader | **confirmed** — `lease_lifecycle_hook.py`, which U5 deletes whole, so no coverage gap |
| No `fleet_commons_shim.py` names `lease_broker` statically | **confirmed** across all 9 shim copies — resolution is caller-side, so U7 needs no shim-registry edit |

## Findings

| Key | Priority | Finding | Status |
|---|---|---|---|
| `D1` | **P1** | Agent-facing documentation was in no unit's file list — 13 documents describe the broker as current behavior | fixed (new **R11**/**R11a**); **resizing decided — overridable** |
| `D2` | **P1** | Target plugin versions are unstated, and `team-execution` is post-1.0 losing a documented capability | fixed (**R8** target table); **`team-execution` → 3.0.0 decided — overridable** |
| `D3` | P1 | The R4 rename crosses a serialized event schema in a file no unit owned | fixed in place (new **R4a**, U6 file list, risk row) |
| `D4` | P1 | R5 undercounted the disposition surface it requires be preserved | fixed in place (new **R5c**) |
| `D5` | P2 | `R6` collides with issue #358's R6 quoted in `team_teardown.py`'s docstring | fixed in place (disambiguated at all three sites) |
| `D6` | P2 | No verification section — the plan named no repository quality gates | fixed in place (new **Verification** section) |
| `D7` | P2 | U2 must add a dependency on a file U3 concurrently rewrites | **closed 2026-07-30 — premise was wrong**; the interface exists and is broker-free, units stay parallel |
| `D12` | P1 | Two broker consumers (`team_teardown_hook.py`, `outcome_decompose.py`) belonged to no unit | found after decomposition; folded into U2 and U3; U7's guard widened |
| `D8` | P2 | `outcome_worktrees.py` defaults three parameters to a deleted broker constant | fixed in place (U3 approach) |
| `D9` | P2 | Line references had no pinned revision | fixed in place (note under Summary) |
| `D10` | P2 | Issue dispositions buried in the codex section; #648 must not be closed | fixed in place (moved to Scope Boundaries as a table) |
| `D11` | P3 | Six wrong or truncated internal references | all fixed in place |

### `D1` — P1, OPEN. Documentation was missing from the plan entirely.

**The plan listed no Markdown file in any unit.** Meanwhile 13 documents in the three affected plugins
describe the lease broker as current behavior. These are not commentary — a `SKILL.md` is executable
instruction, so a stale one makes an agent attempt a mechanism that no longer exists.

The two worst cases: `plugins/saga/references/concurrency-spawn-sites.md` (13 references) is an inventory
table whose columns literally are *"Lease pool / Acquire or reserve seam / Bind seam / Renewal seam /
Release seam"* — every row goes false. And `plugins/team-execution/skills/team-execution/references/lease-protocol.md`
documents `lease_protocol.py`, which U6 lists as a whole-file deletion candidate, so the reference would
point at a deleted script. `plugins/saga/skills/work/SKILL.md` (8 references) is the repo's most-used
surface.

Measured with a word-boundary pattern that excludes `release`/`released`; UniFi's matches are DHCP leases
and are correctly excluded.

**Fixed by** adding **R11** with the full inventory and an assignment rule (each document moves with the
unit that removes the behavior it describes), plus **R11a** for the `fleet-core` `plugin.json` description
that advertises *"lease and liveness decisions"* and its `marketplace.json` mirror.

**Decision taken — no U8 documentation unit.** A documentation-only unit at the end would recreate exactly
the window the assignment rule exists to prevent: shipped skills instructing agents to use a deleted
mechanism. So U2, U6, and U7 each absorb their share and are **larger than their original estimates**, U6
most of all. Two documents span multiple units and were given named owners so they cannot be orphaned:
`concurrency-spawn-sites.md` is rewritten once in U7 (when its last row empties), and
`saga/skills/work/SKILL.md` belongs to U3.

**Overrule this if** you would rather see the documentation as its own reviewable pull request — the
tradeoff is a real but time-boxed window of lying skills against easier review.

### `D2` — P1, DECIDED. No target versions, and `team-execution` is the hard case.

**R8** requires versions, CHANGELOGs, and `marketplace.json` move together, and correctly names the three
current versions — but never says what they become. Two of the three are easy; one is a real decision:

- `fleet-core` **0.23.0** — pre-1.0, deletes its largest module. Minor bump is the repo convention.
- `saga` **0.122.0** — pre-1.0, deletes a hook and a wrapper. Same.
- `team-execution` **2.23.0** — **post-1.0, and it loses a documented capability.** Its README at `:20-29`
  advertises lease admission, preflight, renewal, release, and dead-owner sweep; `lease_protocol.py` may
  be deleted outright. Under semver that reads as a major bump to **3.0.0**, not `2.24.0`.

**Decision taken:** `fleet-core` → **0.24.0**, `saga` → **0.123.0**, `team-execution` → **3.0.0**, written
into R8 with the reasoning beside each. The `team-execution` major bump is the one worth arguing about.

**Overrule this if** you read the removal as non-breaking for that plugin's actual consumers. Note the only
alternative that avoids the major bump is keeping `lease_protocol.py` as a deprecated no-op shim for one
more minor release — and that contradicts R1 and R2, so it is a scope reversal rather than a version tweak.

### `D3` — P1, FIXED. The R4 rename crosses a wire schema.

R4 required renaming `lease_ttl_seconds` → `ttl_seconds` and located it at `liveness_engine.py:94` and
`:367`. The measured surface is **five files**:

- `liveness_engine.py` — `:94`, `:288`, `:289` (including a `_finite_nonnegative(…, "lease_ttl_seconds")`
  **string literal** that reaches operator-visible error text), `:367`
- **`plugins/saga/scripts/liveness_events.py`** — `:65` (membership in the `IDENTITY_KEYS` required-key
  contract), `:207`, **`:236` wire parse**, **`:258` wire serialize**, `:644`. **This file was in no unit.**
- `team-execution/.../liveness_protocol.py:291` — the producer
- three test files asserting the old name

The failure mode is why this is P1 rather than P2: a partial rename raises `KeyError` at
`liveness_events.py:236` when the first event is *parsed*, not at import time and not under mypy. Neither
the type checker nor a smoke import catches it. Fixed by adding **R4a** with the full table, adding
`liveness_events.py` to U6, requiring one commit for all five, and adding a round-trip test scenario.

`liveness_events.py` does not import the broker (it loads `liveness_engine` through the shim), which is
why it was legitimately absent from the consumer table — but that is exactly what let it slip R4's net.

**One question I left for you:** whether previously written liveness events must still parse under the old
key. If yes, U6 needs a compatibility shim, not a rename. Flagged in R4a, not decided.

### `D4` — P1, FIXED. R5 required preserving less than it thought.

R5 named three dispositions to preserve. Read from `_worktree_sweep` directly, the surface is **five
outcomes across four reason codes and three evidence-ref strings** — R5 would have silently dropped the
`released-by-sweep` and `not-a-sweep-candidate` branches. Two deeper problems, now in **R5c**:

1. **All three evidence-ref strings are lease-id-namespaced** (`broker:lease-absent:{lease_id}`,
   `sweep:reaped:{lease_id}`, `sweep:lease-gone:{lease_id}`). With no broker there is no `broker:`
   namespace and no lease id, so they are **redefined**, not re-keyed — a CHANGELOG-worthy behavior change
   the plan called a mechanical re-key.
2. **`already-absent` changes meaning.** Today it fires when the *lease* head is gone, saying nothing
   about the worktree. Re-keyed on path it comes to mean "git no longer lists this worktree" — a different
   predicate wearing the same word.

### `D7` — P2, **CLOSED 2026-07-30. The finding rested on a wrong premise.**

*As originally written:* U2's replacement reads `outcome_worktrees.py`'s per-leaf routing, but
`team_teardown.py` does not import `outcome_worktrees` today (verified: zero references either
direction). So U2 must **add** a dependency on the module U3 is concurrently rewriting, and
`assert_no_wave_file_conflicts()` will not catch it — the units are file-disjoint but not
interface-disjoint. I flagged it but did not re-sequence, because changing unit order is a scope decision.

*What re-checking the source showed.* The interface U2 needs **already exists and is broker-free.**
`outcome_worktrees.live_worktrees(store, ops)` at `:314` reads the worktree registry (`worktrees.json`,
a `{subplot_id -> entry}` map) and asks git whether each registered `path` still exists — exactly the
"cross-reference git with per-leaf routing" U2 was said to need. It reads `entry["path"]` only; the
registry's `lease` field is consumed solely by `_lease_binding` at `:192`, which feeds the
`prevalidate_reap_authority` reap path U3 deletes. So U3 has nothing to build and hand over.

What *is* missing is smaller and lives inside U2: `team_teardown.py` imports only `fleet_commons_shim`
and `run_ledger`, and `reclaim_all(...)` takes `subplot_id` and `team_run_id` but no outcome store, so
it cannot locate `worktrees.json`. The store threads in through
`plugins/saga/hooks/team_teardown_hook.py`, the single production caller — caller-side plumbing inside
U2's own blast radius.

**Resolution: U2 and U3 run in parallel; no ordering constraint.** The residual coupling is one
contract, now an explicit non-goal and acceptance criterion on U3 (#680): `read_registry`,
`live_worktrees`, and the registry's `path` field survive. U2 imports them and edits no file U3 owns,
so the units remain file-disjoint and `assert_no_wave_file_conflicts()` is sufficient after all — the
R7 gap this finding claimed does not materialize here.

### `D12` — P1, **found 2026-07-30, after decomposition. Two broker consumers belonged to no unit.**

Re-deriving the consumer list from scratch turned up 13 files under `plugins/` referencing the broker,
two of which the plan never assigned:

- `plugins/saga/scripts/outcome_decompose.py` (439 lines) takes `lease_authority` at `:259` and threads
  it at `:288`, `:292`, `:306`, `:346`, calling `prevalidate_reap_authority(...)` — the exact function
  U3 deletes. U3 landing breaks this file at runtime.
- `plugins/saga/hooks/team_teardown_hook.py` (110 lines) is the only production caller of
  `production_adapters`: `default_broker()` at `:50`, `read_decision_input` at `:56`,
  `broker.root_sha256` at `:58`, `production_adapters(broker)` at `:80`. The plan cited `:80` once as
  evidence inside the KTD12 argument but assigned the file nowhere.

**Both escaped for the same reason `liveness_events.py` did in `D3`: neither literally imports
`lease_broker`.** One receives the authority as an injected parameter; the other reaches it through
`team_teardown.default_broker()`. That is three instances of one escape mechanism, which makes it a
pattern rather than an oversight — **any consumer survey greping only `lease_broker` is
known-incomplete.**

**Resolution (operator, 2026-07-30):** folded into existing units rather than given an eighth card —
`team_teardown_hook.py` → U2 (#679), `outcome_decompose.py` → U3 (#680). U7's re-add guard was widened
to grep `lease_authority` and `fleet_leases` as well, so the next instance fails a test instead of a
survey.

## Applied fixes

Nine safe fixes, all backed by the document itself or by tree evidence:

1. **New R4a** — the five-file rename surface, with the runtime-`KeyError` failure mode named (`D3`).
2. **New R5c** — the five-outcome disposition table, the evidence-ref namespace problem, and the
   `already-absent` semantic shift (`D4`).
3. **New R11 / R11a** — the 13-document inventory, the assignment rule, and the `plugin.json` description
   (`D1`).
4. **New Verification section** — the repo's own gates from `CLAUDE.md` (`pytest` baseline, `ruff check`
   *and* `ruff format --check`, `mypy plugins/ scripts/ tests/`, `bandit`, `lint_journal_order.py`,
   `check_release_surface_parity.py`) plus three cross-unit sentinels (`D6`).
5. **R6 collision disambiguated** at all three sites — `team_teardown.py`'s docstring "R6" is issue
   **#358's** R6, not this plan's (`D5`).
6. **U6 file list** gained `liveness_events.py`, `liveness_protocol.py:291`, and
   `liveness_engine.py:288-289`; **U3** gained the `DEFAULT_TTL_SECONDS` default problem; **U7** gained the
   `plugin.json` description and the three fleet-doctor documents (`D3`, `D8`, `D1`).
7. **Pinned-revision note** under Summary — every `file:line` was measured at `ddba53a0`; re-grep before
   editing (`D9`).
8. **Issue dispositions moved** out of the codex section into Scope Boundaries as a verified table, with
   #648 called out as needing a rewrite rather than closure (`D10`).
9. **Six reference corrections** (`D11`): `retained_reason` is at `:1267` not `:1268`; the
   `_worktree_sweep` closure runs to `:1277` not `:1272` (two places); U4's site list omitted `:187`, the
   one line KTD4 calls load-bearing; U2's "13 call sites" beside 11 line numbers now explains that the
   other two are `_current_head(broker, …)` helper calls at `:1253` and `:1270`; the elided evidence path
   `ce4ff96….md` is now the full resolvable filename; KTD12 now names `production_adapters` at `:1378`
   threading at `:1419`; Option A's defect list now includes #661; and the 11-vs-12-vs-91 counts are
   reconciled against issue #677's own "12 remaining importers".

## Residual risk from limited evidence

**The 91 call-site total is an upper bound, and the plan says so.** I verified `team_teardown.py`'s row
precisely (11 direct broker-method calls plus 2 helper invocations = 13) but did not re-derive the
alias-based counts for `engine_dispatch.py` (~23), `outcome_worktrees.py` (~16), or
`liveness_protocol.py` (~9). Those aliases may serve non-broker uses in the same file, so real counts
could be lower. This affects sizing, not correctness.

**Documentation counts are match counts, not edit counts.** R11's 13 documents are ranked by how many
lease references each contains. Some references will be a single stale sentence; others (the
`concurrency-spawn-sites.md` inventory) are whole-file rewrites. I did not read all 13 to grade them.

**R11's inventory is scoped to `plugins/`.** Documents under `docs/` — including the outcome specs and
the engineering journal — were not swept for lease references, on the grounds that dated records should
stay as written. If any `docs/` file carries live guidance rather than a dated record, it is outside this
inventory.

## Post-review amendments (2026-07-30)

Recorded after the operator decomposed #677 into seven child issues (#678–#684):

1. **`D7` closed** — see above. The plan's Implementation Units warning was replaced with the
   resolution, and the risk table row was rewritten from "unresolved" to the surviving one-line
   contract on U3.
2. **`D12` opened and resolved** — see above. Both newly found files were added to the plan's
   consumer table with an explicit warning that neither appears in the idiom table, which is why they
   were missed.
3. **Operator confirmed `D1` and `D2`** — no eighth documentation unit, and `team-execution` goes to
   3.0.0. Evidence gathered for `D2` at decision time: nothing pins team-execution's version except
   its own drift guard at `tests/test_team_execution_plugin.py:66`, its `plugin.json`, and the
   generated `marketplace.json`; `plugins/team-execution/README.md:18-29` advertises the lease
   contract as current behavior; and team-execution's only prior major bump (1.5.0 → 2.0.0,
   2026-05-27, "add validator orchestration") marked a structural chapter rather than a breakage,
   while `docs/engineering-journal/DECISIONS.md:4528` records the principle that the number should
   honestly signal breakage. Both readings land on 3.0.0.
4. **Correction to this review's own reasoning on `D1`.** The original write-up said the repo rule
   required documentation to move with the code. That was an overread: `CLAUDE.md` rule 6 makes a
   user-facing guidance change a *trigger* for release-surface updates; it does not mandate same-pull-request
   guidance. The no-U8 decision stands on its own argument — a `SKILL.md` is executable instruction,
   so a trailing documentation pull request leaves a window where shipped skills lie — not on the rule.
