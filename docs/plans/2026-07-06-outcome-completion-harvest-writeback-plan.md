---
title: /outcome code-leaf completion harvest — PR-ref writeback and gh-consumable ref normalization
type: fix
status: active
date: 2026-07-06
origin: https://github.com/infiquetra/infiquetra-claude-plugins/issues/495
---

# /outcome code-leaf completion harvest — PR-ref writeback and gh-consumable ref normalization

## Summary

Fix the two coupled gaps in `#495` that make code-leaf completion harvest silently never fire: give a
leaf's merged PR a way to reach its coordinator node **without a manual JSON hand-edit** — an explicit
`link-pr` verb that supplies the single `node.github["pr"]` producer both downstream consumers (the
harvester barrier and the auto-merge queue) wait on — and normalize stored GitHub refs so `gh` reads
resolve regardless of whether the ref is `owner/repo#N`, a full URL, or a bare number. Saga-only change
to the `/outcome` machinery; backend `inline`.

## Problem Frame

The code-leaf completion contract is `code:pr-merged` (`outcome_orchestrator.py:100-112`): a node is
`done` only when `node.github["pr"]` reads `merged` on GitHub (R10/R11 — the parent must be able to
re-verify on GitHub; a closed tracking issue alone must **not** satisfy a code leaf). Two gaps break the
producer side of that contract:

**Gap 1 — no merged-PR ref reaches the coordinator node (the blocker).** The record-only dispatch →
native `/work` → squash-merge flow never writes the leaf's merged PR back onto the coordinator node.
`barrier_satisfied` returns `(False, "no PR ref yet")` (`outcome_orchestrator.py:102-103`) and leaves
every code leaf pending forever. The only recovery today is an operator hand-edit of `github.pr` in the
committed spec followed by `commit --push` + re-`advance` — the workaround proven on `sub-362` (commit
`c5549d5`) and repeated across all 9 nodes of the `tier-effort-first-class` dogfood.

**Gap 2 — the stored ref format is not gh-consumable (latent here, breaks non-code + autonomous).**
Decompose/ingestion stores refs as `owner/repo#N` (the 9 tier-effort nodes carry
`github.issue = "infiquetra/infiquetra-claude-plugins#362"`). `outcome_github.pr_state` /`issue_state`
pass that string **raw** to `gh` (`outcome_github.py:59,82`), and `gh issue view "owner/repo#N"` errors
(`invalid issue format`) while `gh pr view "owner/repo#N"` misreads it as a branch. A ref-parse regex
already exists at `outcome_github.py:148` inside `_closed_by`, but `pr_state`/`issue_state` do not share
it. Code leaves dodged this only because the workaround stored full-URL PRs (which `gh` does accept).

This is the first `/outcome` dogfood defect. **The `tier-effort-first-class` outcome is already durably
reconstructable** (its 9 committed PR URLs all resolve `merged`; `report.md` renders 9/9; a cache-less
`advance` rebuilds 9/9 from GitHub) — so this fix does **not** change that outcome's durability. It makes
the machinery **correct and automatic** so future outcomes and non-code/autonomous leaves work without
the hand-edit, and it pins the `code:pr-merged` contract against regression. Operator decision on
2026-07-06: fix `#495` before closing objective `#343`.

## Requirements

R1. A code leaf's merged PR must reach its coordinator node **without a manual JSON hand-edit** — via an
    explicit `link-pr` verb. This is the single missing *producer* of `node.github["pr"]`; both the
    harvester barrier (`outcome_orchestrator.py:100-112`) and the auto-merge queue
    (`outcome_merge.py:170` `_is_mergeable_kind` requires the ref) are *consumers* of it, so one producer
    unblocks both.

R2. Every `outcome_github` `gh` read (`pr_state`, `issue_state`, and the issue-ref readers
    `board_status` / `issue_close_info`) must resolve a ref stored as `owner/repo#N`, a full GitHub URL,
    or a bare number — none may reach `gh` in a form it rejects.

R3. The `code:pr-merged` barrier contract is preserved exactly: a code leaf requires a **merged**
    `github.pr`; a closed tracking issue with no merged PR must never satisfy it (no false-positive
    harvest).

R4. `link-pr` is idempotent, validates its target (the subplot exists, is a `code` node, the URL is a
    PR URL), and never mutates a non-target node.

R5. The fix is **read-time robust**: it repairs already-committed specs (e.g. tier-effort's
    `owner/repo#N` issue refs) with no re-ingestion or migration.

R6. Saga-only release-surface parity: `plugins/saga/.claude-plugin/plugin.json` + `CHANGELOG.md` +
    `.claude-plugin/marketplace.json` synced; `tools/release_surface_diff_guard.py --base-ref <sha>`
    green against committed state before push.

R7. **No change to R17** — `node.state` on the committed spec stays authoring-time-only. The fix
    operates on GitHub refs and completion events, never on persisting derived state into the spec JSON.

## Key Technical Decisions

KTD1 — **Supply the one missing producer; do not touch the consumers.** The fix adds the `link-pr` verb
(U2) that writes `node.github["pr"]`. Both downstream stages are *consumers* of that field — the
harvester barrier (`outcome_orchestrator.py:100-112`) and the auto-merge queue's `_is_mergeable_kind`
(`outcome_merge.py:170`, which requires `bool(node.github.get("pr"))` before it will even queue a
merge) — so a single producer unblocks both. **Rejected: a merge-time writeback** (the originally-drafted
U3) — it is *vacuous*, because the auto-merge queue already requires `github.pr` to be present to act, so
there is nothing to write back at merge time. **Rejected: a closing-PR timeline resolver** —
`issue_close_info`/`_closed_by` (`outcome_github.py:139-196`) surface only the closing *actor*, a robust
closing-PR query is edge-case-heavy (manual closes, non-merge closes, multiple linked PRs), and it would
not have fired for the tier-effort leaves anyway (their sub-issues were closed manually, not by a
keyword-closing PR — the `#369` pattern). A zero-touch autonomous producer is deferred (see Scope).

KTD2 — **Normalize refs at READ time, inside `outcome_github`**, not only at ingestion. Read-time
normalization repairs already-committed specs (tier-effort's `owner/repo#N` issue refs) with no
migration; storing full URLs at ingestion is optional additional hygiene, deferred to follow-up.

KTD3 — **`owner/repo#N` → full URL** (not `N --repo owner/repo`). A URL is a single positional token,
cwd-independent, and uniform; the caller's kind picks `/pull/N` (PR) vs `/issues/N` (issue). Full URLs
and bare numbers pass through unchanged.

KTD4 — **`link-pr` writes locally with an optional `--push`; it does not auto-commit by default.**
Consistent with `prune`/`promote` (`save_spec` local, `outcome.py:1312,1319`) and the R26/R27
explicit-bank cadence; the operator's existing `advance --persist` / `commit --push` banks it.

KTD5 — **U4 is a pure regression test (no production code).** The barrier already enforces
`code:pr-merged` correctly (`outcome_orchestrator.py:100-112`); the bug was the absent producer, not a
wrong predicate. Pin the false-positive guard (closed issue ≠ merged PR) so a future "a close is enough"
shortcut cannot regress it.

KTD6 — **Scope excludes persisting derived completion into the committed spec (R17 unchanged).** That was
the operator-rejected "make the JSON self-describing" option; durability already holds via committed
gh-consumable refs + reconstruct-on-advance (proven for tier-effort), so this fix does not touch the
derived-on-read contract.

KTD7 — **Backend `inline`.** Mechanical, well-bounded, test-heavy; no broad fan-out or adversarial-panel
need. (An adversarial `/code-review` gate still runs at the work→PR boundary per the standing pattern.)

## Implementation Units

### U1. Gap-2 — gh-consumable ref normalization in `outcome_github`

Add a shared normalizer so every `gh` read resolves the three stored ref formats uniformly.

**Approach:** add a **components** parser `_parse_ref(ref) -> tuple[str, str, str] | None` in
`plugins/saga/scripts/outcome_github.py` that yields `(owner, repo, number)` from an `owner/repo#N` ref
or a full GitHub `pull`/`issues` URL (reusing the `owner/repo#N` regex shape from `_closed_by:148` and
adding a URL shape), and `None` for a bare `N` or an unparseable ref. Build a small `_gh_ref(ref, kind)`
that returns a gh-consumable token: from parsed components it emits a full URL
(`https://github.com/{owner}/{repo}/{pull|issues}/{number}`, `kind` picking the segment); a bare `N` and
an already-full URL pass through unchanged. Call `_gh_ref` at the head of `pr_state` (kind=pr) and
`issue_state` (kind=issue), and route `issue_close_info`'s `gh issue view` (`outcome_github.py:180-182`)
through it too. **Do NOT pre-normalize the ref handed to `_closed_by`** — its `gh api
repos/{owner}/{repo}/issues/{N}/events` path builder needs the raw components; instead have `_closed_by`
consume `_parse_ref` so a URL, `owner/repo#N`, or bare ref all resolve there consistently (a URL must not
starve `_closed_by`, which today returns "" on anything but `owner/repo#N`).

**Files:** `plugins/saga/scripts/outcome_github.py`.

**depends_on:** none.

**Test scenarios** (`tests/test_outcome_completion.py`): `pr_state` and `issue_state` each resolve all
three formats (`owner/repo#N`, full URL, bare `N`) against a stubbed `subprocess.run`, and the stub
asserts the argv `gh` actually receives is gh-consumable — no raw `owner/repo#N` token ever reaches `gh`.
A full URL is passed through byte-for-byte. `_parse_ref` returns the right components for `owner/repo#N`
and both `/pull/N` and `/issues/N` URLs, and `None` for a bare/garbage ref. `_closed_by` still resolves
its events path when handed a full URL (the coupling guard). Malformed refs still degrade to `unknown`
(never raise), preserving the never-raise contract.

### U2. Gap-1 attended — `/outcome link-pr <id> <subplot> <pr-url>` verb

Formalize the manual PR-attach into a validated, idempotent verb (the attended/inline seam).

**Approach:** add a `link_pr(repo_root, outcome_id, subplot_id, pr_url, *, push=False)` function in
`plugins/saga/scripts/outcome.py` that loads the spec, finds the node, validates (subplot exists;
`node.kind == "code"`; `pr_url` matches a PR-URL shape), sets `node.github["pr"] = pr_url`, `save_spec`,
and — when `--push` — `commit_spec(..., push=True)`. Re-linking the same URL is a no-op (idempotent).
Register the `link-pr` subparser beside the structural verbs (`outcome.py:1114+`) with positionals
`outcome_id`, `subplot_id`, `pr_url` and an optional `--push`; wire the dispatch branch beside `prune`
/`promote` (`outcome.py:1296-1320`). `link-pr` attaches a *pointer* only — the harvester barrier still
re-verifies `merged` on GitHub (`outcome_orchestrator.py:104-112`), so a wrong or not-yet-merged link
simply never harvests rather than falsely completing the node (attended operator responsibility, safely
gated).

**Files:** `plugins/saga/scripts/outcome.py`.

**depends_on:** none (parallel to U1; harvest reliability of the linked ref depends on U1 at read time).

**Test scenarios** (`tests/test_outcome_command.py`): `link-pr` writes `github.pr` on the named code
node and leaves every other node untouched; re-running with the same URL is a no-op; an unknown subplot
id raises a clear error; a non-`code` node is rejected; a non-PR URL is rejected; `--push` invokes
`commit_spec` with `push=True` (stubbed git runner) while the default path only `save_spec`s. After a
`link-pr` + `advance`, the previously-stuck code leaf harvests to `done`.

### U3. End-to-end harvest integration — the closed producer→consumer loop

Prove the whole edge the defect broke: no PR ref → no harvest; `link-pr` a merged PR → harvest to `done`;
and a node whose stored issue ref is `owner/repo#N` resolves after U1. (Replaces the originally-drafted
merge-time writeback, which doc-review found vacuous — the merge queue already requires `github.pr`;
KTD1.)

**Approach:** an integration test over a small real spec + store (the harness `test_outcome_integration.py`
already establishes) driving `production_harvester` with a stubbed `github_runner`. No production code —
U3 is the end-to-end proof that U1 + U2 close the loop the unit tests only cover in pieces.

**Files:** `tests/test_outcome_integration.py`.

**depends_on:** U1, U2.

**Test scenarios:** a spec with a `code` node and no `github.pr` → `advance` harvests nothing and the
node stays off the done set; after `link-pr` attaches a PR URL the stub reports `merged`, the next
`advance` harvests it → `derive_states` reports `done` and (as the last node) `complete: true`; a node
whose `github.issue` is stored as `owner/repo#N`, with the stub reporting that issue `closed`, resolves
through the U1-normalized reader (asserting the pre-U1 `invalid issue format` failure is gone).

### U4. Barrier contract regression test — `code:pr-merged` requires a merged PR

Pin the false-positive guard the whole defect turns on (KTD5 — pure test, no production code).

**Approach:** add regression tests asserting `barrier_satisfied` / `harvest` behavior on code leaves:
a code node with a merged `github.pr` harvests to a success completion event; a code node whose tracking
`github.issue` reads **closed** but which has **no** merged `github.pr` does **not** harvest (barrier
stays unsatisfied, `contract == code:pr-merged`, `reason` names the missing/again-checked PR). Uses the
stubbed `github_runner` already established in the completion tests.

**Files:** `tests/test_outcome_completion.py`.

**depends_on:** none.

**Test expectation:** the two assertions above; no source change (guards `outcome_orchestrator.py:100-112`
against a future "close is enough" regression).

### U5. Release surface + engineering journal

Keep installed-plugin metadata telling the same story as the diff, and record the decisions.

**Approach:** bump `plugins/saga/.claude-plugin/plugin.json` (minor — a new `link-pr` verb;
`0.70.0 → 0.71.0`), add the `CHANGELOG.md` entry, sync `.claude-plugin/marketplace.json` via
`python3 tools/sync_marketplace.py` then `python3 -m json.tool .claude-plugin/marketplace.json`, and run
`python3 tools/release_surface_diff_guard.py --base-ref <merge-base-sha>` against committed state before
push (per LEARNINGS `{#fleet-core-release-surface-own-bump}`). Add DECISIONS
`{#outcome-completion-harvest-writeback-495}` mirroring the KTDs; add a LEARNINGS entry only if the
producer/consumer-writeback mechanism proves non-obvious in implementation.

**Files:** `plugins/saga/.claude-plugin/plugin.json`, `plugins/saga/CHANGELOG.md`,
`.claude-plugin/marketplace.json`, `docs/engineering-journal/DECISIONS.md`,
`docs/engineering-journal/LEARNINGS.md`, and the version pin in `tests/test_saga_plugin.py`.

**depends_on:** U1, U2, U3, U4.

**Test expectation:** the saga version drift-guard (`tests/test_saga_plugin.py`) pins `0.71.0`; the
release-surface parity check is green.

## Scope Boundaries

**In scope:** read-time ref normalization (U1); the attended `link-pr` verb — the missing `github.pr`
producer that unblocks both consumers (U2); the end-to-end harvest integration proof (U3); the
`code:pr-merged` regression guard (U4); saga release surface + journal (U5).

**Explicit non-goals:**
- A **zero-touch autonomous PR producer** (the coordinator learning a dispatched leaf's PR with no
  operator action). It is deferred, not built, on evidence: no code leaf has ever reached the auto-merge
  queue (all outcomes to date ran attended/inline), and the only auto-mechanisms are fragile
  (closing-PR-timeline resolution) or couple the leaf executor to the coordinator. `link-pr` already
  removes the JSON hand-edit, which is the defect. Flagged for operator review — see the readiness note.
- A merge-time writeback in `process_merge_queue` — vacuous (the merge queue requires `github.pr` to act;
  KTD1).
- Persisting derived completion (`node.state`/`complete`) into the committed spec JSON — R17 stays; the
  operator rejected the "self-describing artifact" broadening (KTD6).
- Changing decompose/ingestion to store full-URL refs — read-time normalization covers existing and new
  specs; ingestion-side URL storage is optional hygiene.
- Sibling `#491` (attend/report emit the raw leaf handoff id, not the issue URL) — a separate re-entry
  pointer seam, out of scope unless trivially coupled.

**Deferred to Follow-Up Work:** the zero-touch autonomous PR producer (a coordinator-side read of the
dispatched leaf saga's PR ref, feeding both consumers); ingestion-time full-URL ref storage; a
fully-cache-less committed completion-log marker (the "future path" noted at
`outcome_orchestrator.py:126-130`).
