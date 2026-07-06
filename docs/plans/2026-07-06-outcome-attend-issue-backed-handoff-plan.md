---
title: /outcome attend — emit the leaf's issue-backed saga id, not the raw dispatcher handoff
type: fix
status: active
date: 2026-07-06
origin: https://github.com/infiquetra/infiquetra-claude-plugins/issues/491
---

# /outcome attend — emit the leaf's issue-backed saga id, not the raw dispatcher handoff

## Summary

`/outcome attend <id> <subplot>` hands the operator a dead `/resume` pointer: it prints the dispatcher's
raw `leaf_saga_id` (`leaf-<outcome>-<subplot>`), but an issue-backed leaf's real native saga is
`issue-<N>`. Resolve the correct id from the node's GitHub issue ref and emit `/resume issue-<N>`, falling
back to the raw id only for a non-issue-backed leaf. Saga-only; backend `inline`; Lightweight.

## Problem Frame

`attend` (`plugins/saga/scripts/outcome.py:940-955`) returns `f"/resume {leaf}"` where
`leaf = _dispatch_records(store).get(subplot_id)` — the raw `leaf_saga_id` the default dispatcher minted
as `leaf-<outcome_id>-<subplot_id>` (`outcome.py:95`). But `/plan` and `/work` mint an issue-backed
leaf's saga as `issue-<N>` (`saga.derive_saga_id("issue", N)`, `saga.py:333`). So
`/outcome attend tier-effort-first-class sub-362` prints `/resume leaf-tier-effort-first-class-sub-362`
when the actual resumable saga is `issue-362` — the pointer resolves to nothing.

**Scope is `attend` only.** The report (`outcome_report.py`) was investigated and does **not** emit a
leaf `/resume` handoff or the raw `leaf_saga_id`: `AttentionItem` carries only `subplot_id`,
`consolidated_prompt` (`outcome_report.py:174`) renders `subplot_id`, and the `report.md` generator emits
`subplot_id` + PR/issue evidence — never the saga id. The issue title's "attend/report" is corrected to
attend-only here.

This is the last open execution-discovered sub-issue of objective #343; fixing it clears #343's child
set (operator sequenced: fix #491 → close #343).

## Requirements

R1. `/outcome attend <id> <subplot>` for an **issue-backed** leaf must emit `/resume issue-<N>`, where `N`
    is the leaf node's GitHub issue number.

R2. A **non-issue-backed** leaf (no resolvable issue on the node) falls back to the raw `leaf_saga_id` —
    unchanged behavior.

R3. Degrade gracefully, never raise: a missing node, an absent/unparseable issue ref, or a still-present
    raw handoff all resolve to the raw `leaf_saga_id` rather than an error. A subplot that is not
    dispatched keeps its existing "not dispatched yet" error.

R4. The report's attention prompt is unaffected (it never emitted the id) — no behavior change there.

R5. Saga-only release-surface parity: saga `plugin.json` 0.71.0→0.72.0 + CHANGELOG + marketplace sync;
    `release_surface_diff_guard.py` green against committed state before push.

## Key Technical Decisions

KTD1 — **Resolve `issue-<N>` from the node's GitHub issue, prefer the bare `sub_issue`.** A node's
`github` dict carries both `sub_issue` (a bare integer, e.g. `362`) and `issue` (an `owner/repo#N`
string). Prefer `sub_issue` when it is a digit; else parse `issue` via `outcome_github._parse_ref`
(landed in #495) and take its `number`. Then emit `issue-<N>`.

KTD2 — **Inline the `f"issue-{n}"` construction (mirror `saga.derive_saga_id`), do not import `saga`.**
`outcome.py` deliberately imports only its `outcome_*` siblings + `fleet_commons_shim`; pulling in the
heavy `saga` module for a one-line format string is not worth the dependency. Mirror the exact contract
(`saga.py:333` → `f"issue-{str(id_).strip()}"`) and cite it in a comment so drift is catchable.
*Alternative considered:* `import saga; derive_saga_id(...)` — more DRY but adds a cross-module
dependency; revisit if `outcome.py` needs more saga-id logic later.

KTD3 — **`attend` must `load_spec` + `node_by_id` to reach `node.github`.** It currently reads only the
dispatch ledger. Add the spec read; a `node_by_id` miss falls back to the raw `leaf_saga_id` (R3).

KTD4 — **Backend `inline`.** One tiny, deterministic resolver + its call site; no fan-out. The adversarial
`/code-review` gate still runs at the work→PR boundary.

## Implementation Units

### U1. Issue-backed handoff resolver + `attend` fix

Emit the real native saga id for an issue-backed leaf.

**Approach:** add a helper `_leaf_handoff_id(node, leaf_saga_id) -> str` in
`plugins/saga/scripts/outcome.py`: if `node` is not None and carries a resolvable issue (prefer a digit
`github["sub_issue"]`, else `_parse_ref(github["issue"])`'s number), return `f"issue-{n}"`; otherwise
return `leaf_saga_id` unchanged. In `attend`, after resolving `leaf` from the dispatch records,
`load_spec(repo_root, outcome_id)` + `spec.node_by_id(subplot_id)` and pass the node through the resolver
before formatting `/resume {handoff}`. Keep the existing "not dispatched yet" guard.

**Files:** `plugins/saga/scripts/outcome.py`.

**depends_on:** none.

**Test scenarios** (`tests/test_outcome_command.py`): `attend` on an issue-backed dispatched leaf returns
`/resume issue-<N>` (both when the node has a bare `sub_issue` and when it has only an `owner/repo#N`
`issue` string); a leaf with no issue on its node falls back to `/resume <raw-leaf-saga-id>`; a
not-dispatched subplot still raises the existing error; a dispatched subplot whose node is missing from
the spec falls back to the raw id without raising.

### U2. Release surface + journal

Keep installed metadata honest and record the decision.

**Approach:** bump saga `plugin.json` 0.71.0→0.72.0; CHANGELOG entry; marketplace sync via
`python3 scripts/sync_marketplace.py` + `python3 -m json.tool` check; pin `tests/test_saga_plugin.py` to
0.72.0; run `python3 tools/release_surface_diff_guard.py --base-ref <merge-base>` against committed state;
DECISIONS `{#outcome-attend-issue-backed-handoff-491}` mirroring the KTDs.

**Files:** `plugins/saga/.claude-plugin/plugin.json`, `plugins/saga/CHANGELOG.md`,
`.claude-plugin/marketplace.json`, `tests/test_saga_plugin.py`, `docs/engineering-journal/DECISIONS.md`.

**depends_on:** U1.

**Test expectation:** `tests/test_saga_plugin.py` pins 0.72.0; release-surface parity green.

## Scope Boundaries

**In scope:** the issue-backed handoff resolver + `attend` fix (U1); saga release surface + journal (U2).

**Explicit non-goals:**
- `outcome_report.py` — investigated; it never emits the leaf `/resume` handoff or the raw `leaf_saga_id`,
  so it needs no change (scope corrected from the issue title).
- Changing how the dispatcher mints `leaf_saga_id` (`outcome.py:95`) — the raw id stays the record-keeping
  key; only the *operator-facing handoff* is resolved to the native saga id.
- Task-backed / ad-hoc leaves — they legitimately have no issue; the raw-id fallback is correct for them.

**Deferred Follow-Up Work:** none.
