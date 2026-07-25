---
title: "fix(saga): ship ceremony resolves head and base from ceremony-scoped evidence, not the rolling branch field"
type: fix
status: active
date: 2026-07-25
origin: https://github.com/infiquetra/infiquetra-claude-plugins/issues/635
---

# fix(saga): ship ceremony resolves head and base from ceremony-scoped evidence, not the rolling branch field

## Summary

`ship_ceremony.py` assumes every pull request is main-based, at five sites. The severe one deletes
the PR **base** branch (local and origin) on a leaf-into-outcome ceremony, because the deletion
target comes from `saga["branch"]` — a field re-stamped from `git branch --show-current` on every
tick save.

This plan replaces five independent guesses with one resolver that answers "what are this
ceremony's head and base refs?" from ceremony-scoped durable evidence, and refuses rather than
guessing when that evidence is absent.

## Problem frame

`plugins/saga/scripts/saga.py:566` stamps `"branch": run(["git", "branch", "--show-current"])` on
**every** `save`. The field therefore means "whatever branch the last save happened on", not "the
branch this ceremony opened". Five ceremony sites consume that field, or the literal string `main`,
as if it were ceremony state:

| ID | Site | Current behavior | Failure on a leaf-into-outcome PR |
|---|---|---|---|
| A | `ship_ceremony.py:549` `_do_branch_delete` | deletes `saga.get("branch")` | **deletes the base branch, local + origin** |
| B | `ship_ceremony.py:535` `_do_checkout_main` | `git checkout main` | lands on the wrong branch for `pull` / `branch_delete` |
| C | `ship_ceremony.py:466` `_do_open_pr` | `gh pr create --head <b>` | PR opens against the repo default branch |
| D | `ship_ceremony.py:868` `start()` | `gh pr create --draft --head <b>` | draft PR opens against the repo default branch |
| E | `ship_ceremony.py:508` `_do_merge` | reads `refs/heads/main` for both SHAs | records `main`'s tip as the squash SHA; `ship --undo` **reverts an unrelated healthy commit on the default branch, and pushes it** |
| F | `ship_undo.py:362-367` `_undo_merge` | checks out `main`, reverts there, pushes `origin main` | applies the revert to the **wrong branch**. Found by U2's refute panel, 2026-07-25 |

The issue reports A–D and describes them as "three places". E was found while grounding this plan
and folded in on the operator's call: it is the same root cause, and leaving it unfixed means the
undo path stays silently broken for exactly the leaf-into-outcome case the issue is about.

F was found by U2's refute-3 panel after U2 shipped (2026-07-25) and folded in on the operator's
call under the same reasoning. **Fixing E without F moves the bug rather than removing it.** E is
about *recording* the right squash SHA; F is about *applying* it. `_undo_merge` hardcodes `main`
three times — `git checkout main`, `git revert --no-edit <merge_sha>`, `git push origin main` — so
a correctly recorded `outcome/demo` SHA is still reverted on `main`. When the outcome branch has
already landed there, that revert applies cleanly and strips the leaf's work from `main`.

`ship_undo._sha_reachable` (`:162-182`) does not catch this either: it is
`git cat-file -e <sha>^{commit}`, a pure **existence** probe, not an ancestry check. A correctly
recorded SHA exists, so it passes. That is honest to its own docstring ("best-effort") and is left
alone; F fixes the branch target, not the probe.

**A is data-loss class.** The only guard is `if not branch or branch == "main"`; an outcome branch
passes it. The real incident (2026-07-20/21, `infiquetra/team-norns`, saga `issue-236`) deleted
`outcome/norns-next-horizon` local and origin while the actual feature branch survived. Recovery
depended on the rollback manifest's recorded head SHA plus local object-store retention.

### The mis-target is a three-part failure

Grounded at `474fd3cc`; the issue documents only the first part.

1. **The base branch is deleted.** `git branch -d` then `git push origin --delete` — the latter with
   `check=False`, so a failed remote deletion is silently swallowed.
2. **The wrong manifest entry is closed.** `_do_branch_delete:562` calls
   `_close_if_registered(saga, _branch_resource_id(branch), …)` using the same rolling field, so it
   addresses `ceremony-branch:<base>` — an id that was never registered. `_close_if_registered`
   no-ops on unknown ids **by design** (`:346-357`), so this fails silently.
3. **The ceremony can never complete.** The real feature branch's `ceremony-branch:<head>` entry
   stays `open`. `_teardown_attempt_closes:604` auto-closes only `scratch` and `worktree` kinds —
   never `branch`. So `_do_teardown` raises `ship_receipt.TeardownBlockedError` on every subsequent
   attempt, permanently.

Part 3 is a consequence, not a separate defect: once A resolves correctly, the entry closes
correctly. It is called out because it changes the recovery story for any ceremony already in this
state, and because it is the evidence that A's manifest key and A's deletion target must come from
one resolver (KTD1).

### Prior art the fix must honor

- `{#ceremony-sidecars-forward-only-undo-346}` — ceremony safety state is per-saga JSON sidecars
  (`merge_expectation.json`, `rollback_manifest.json`), **never** saga tick fields. The defect is
  precisely what happens when ceremony state is read off a tick field.
- `{#ship-teardown-terminal-gate-347}` — the opened-resource manifest is `opened_resources.json`,
  reconciled with per-kind reality probes; a closed-claiming entry whose resource still exists counts
  as open. Rejected extending the outcome store for it: wrong ownership axis.
- `{#ship-ceremony-operator-gate-526}` — `always_operator` transitions refuse unless
  `--operator-confirmed <transition>` names the exact upcoming transition. Its **"Revisit when"**
  clause reads: *"A transition is added whose confirmation needs an argument of its own … then the
  flag grows into a typed confirmation payload rather than a name match."* The issue's request that
  the operator confirm a **named target** meets that condition exactly (KTD6).
- `_scratch_ref_contained` (`ship_ceremony.py:592`) — added after a security review found `rmtree`
  would honor a verbatim stored ref. Same defect class as A (a destructive op trusting a stored
  ref), already solved once for scratch directories, never applied to branch deletion.

## Requirements

- **R1.** `branch_delete` deletes the PR **head** branch. The target is resolved from ceremony-scoped
  evidence; `saga["branch"]` is never a source for a destructive target.
- **R2.** `branch_delete` refuses when the resolved target equals the PR base branch. The refusal
  lands **before** the runner dispatches and before `saga.py save`, so the ledger is provably
  unadvanced.

  **Reachability is rung-scoped, and saying so is part of the requirement** (added 2026-07-25 after
  U4's panel). The hazard is a backstop on the resolver's *fallible* rung, not a universal check.
  When `resolve_ceremony_refs` answers on **rung 1**, the head and base both come from one
  `gh pr view --json headRefName,baseRefName` record, and GitHub forbids a same-repo PR whose head
  IS its base — so the two operands cannot be equal and the probe is inert **by construction**.
  That is correct, not a gap: rung 1 is authoritative and cannot yield a wrong target.

  The hazard exists for **rung 2**, where the head comes from the opened-resource manifest and the
  base from the PR — two independent records that can agree wrongly. That is precisely the
  `outcome/norns-next-horizon` incident shape. Any claim that this probe compares "two derivation
  paths" in general is false and must not be restated; it does so only on rung 2.

  Evidence: `test_branch_delete_targets_base_fires_on_the_rung_2_incident_topology` drives the
  reachable case end to end (rung 1 forced unavailable, manifest naming the base as the head) and is
  red-first — with the probe removed from the `branch_delete` pipeline the ceremony proceeds to
  `git rev-parse outcome/norns-next-horizon`, i.e. it reaches the deletion path for the base branch.
  The two sibling tests that force `head == base` on the PR record prove the refusal **ordering**, on
  a topology GitHub cannot produce; they are worth keeping and must not be counted as proof of
  production reachability.
- **R3.** The manifest resource id closed by `branch_delete` derives from the **same** resolved value
  as the deletion, so the two can never diverge.
- **R4.** `checkout_main` checks out the PR's resolved base branch rather than the literal `main`.
- **R5.** Both `gh pr create` call sites pass an explicit `--base` from ceremony context. The default
  is the dynamically resolved repo default branch, never the literal `main`.
- **R6.** `_do_merge` probes the PR's **base** ref for both `pre_merge_main_sha` and `merge_sha`, so
  the rollback manifest carries the real squash commit and `ship --undo` reverts the right thing.
  The key name `pre_merge_main_sha` is **kept as-is** — it is a keyword argument of
  `ship_undo.append_entry` (`ship_undo.py:250`) pinned by four test assertions, and `ship_undo.py:14`
  records it as audit-only forensic context that `undo()` never consumes programmatically, so
  renaming it changes a cross-module signature on the undo path for zero behavioral gain.
- **R7.** Resolution never silently degrades to a source that can be wrong. Exhausting the ladder
  raises; it does not fall through to `saga["branch"]`.
- **R8.** The `branch_delete` operator confirmation names the resolved target branch, so the operator
  confirms a target rather than only a transition.
- **R9.** No existing test seam weakens. All 47 existing `branch_delete` / `checkout_main` references
  in `tests/test_ship_ceremony.py` still pass unmodified, except where a test asserts the defective
  behavior itself (each such change is called out in the PR body with its justification).
- **R10.** Every new *behavioral* test fails against `474fd3cc` and passes after the fix (red-first),
  and the red is demonstrated **surgically** — reverting only the defective function body, not the
  whole baseline file, so the failure is the behavior and not a signature or fixture error.

  **Discharged for defect F, 2026-07-25, and the honest answer is 2 of 4, not 4 of 4.** Restoring the
  literal `474fd3cc` file reds all four tests, but three of those reds are `TypeError` / `KeyError` /
  `AttributeError` — the tests never reach the behavior. Reverting *only* `_undo_merge`'s body gives
  `2 failed, 2 passed`:
  - `test_undo_merge_targets_recorded_base_not_main` — genuine red-first regression test for F.
  - `test_undo_merge_does_not_touch_main_when_outcome_already_landed` — genuine, and the only one
    whose red is a **data-loss demonstration**: local `main`'s sha moves, proving the leaf's revert
    landed on the default branch.
  - `test_undo_merge_without_recorded_base_floors_at_legacy_main` — **not** an F regression test. It
    pins pre-#635 behavior argv-for-argv, so pre-F code satisfies it by construction. It is a
    backward-compatibility characterization test, and a genuine regression test for the *R12* defect.
  - `test_base_less_entry_ignores_a_non_main_default_branch` — **not** an F regression test either.
    It only unit-calls `_merge_entry_base` and never invokes `undo()`, so it cannot produce a
    behavioral red at all. It is a standing floor on the resolver, not red-first proof.

  All three of U2c's verifiers reproduced the `2 failed, 2 passed` split independently. Keep the two
  characterization tests — a test that cannot fail against the old code is still worth having; it
  just must not be *counted* as red-first evidence.
- **R11.** Release surfaces and the engineering journal ship in the same PR as the code.
- **R12.** `ship_undo._undo_merge` applies the revert to the **ceremony's recorded base**, not the
  literal `main`: the checkout and the push both name the resolved ref, and the revert runs on
  whatever branch that checkout left `HEAD` on. (`git revert --no-edit <sha>` names no branch of its
  own — an earlier wording here claimed all three "target the same resolved ref", which is why the
  same false claim propagated into three shipped docstrings before U2c caught it.) A
  rollback-manifest entry that predates this change (no recorded base) floors at the **literal
  `main`** — *not* the repo's resolved default branch. Such an entry's `merge_sha` was read by a
  pre-#635 `_do_merge` that probed `refs/heads/main` verbatim, so `main` is provably where that sha
  came from; resolving the current default would send the revert to a branch the sha was never read
  from whenever the default is not `main`. Provenance beats currency.

  *(Corrected 2026-07-25 after U2b's refute panel. The original wording of this requirement said
  "falls back to the repo default branch", which is what led U2b to route the fallback through a
  `refs/remotes/origin/HEAD` lookup — two verifiers independently reproduced the resulting
  wrong-branch revert on a `trunk`-default repo. The requirement, not the unit, was wrong.)*
- **R13.** No shipped docstring or comment asserts a safety property the code does not have. The two
  claims U2 shipped are corrected: the `_do_merge` docstring's "recording the right sha is [what
  stands between a mis-recorded sha and a bad revert]" (false until R12 lands) and its
  "pinned by four test assertions" (four *references*, two assertions).
- **R-live.** An operator-gated live-acceptance leg proves the destructive path against a **real git
  remote** in a disposable sandbox — real `git branch -d` and `git push origin --delete`, real
  refs — showing the base branch survives a `branch_delete` on a leaf-into-outcome topology. Never
  against an Infiquetra origin (KTD8).

## Key technical decisions

**KTD1 — One resolver, every consumer.** All five sites, plus the manifest resource id, consume a
single `resolve_ceremony_refs()`. The three-part failure above exists precisely because the deletion
target and the manifest key were derived independently from the same wrong field; a shared resolver
makes that class of divergence unrepresentable.

**KTD2 — Resolution ladder: PR-authoritative, then manifest, then refuse.** In order: (1)
`gh pr view <n> --json headRefName,baseRefName` when the saga carries a PR ref — the ceremony's own
externally durable record, immune to local drift; (2) the `ceremony-branch:` entry on
`opened_resources.json`, written once at push time by `_register_branch` (`:418`, `:863`) and never
re-stamped, for head, plus the recorded base sidecar; (3) raise. `saga["branch"]` is not a rung.

*Rejected:* manifest-first. The manifest is local disk written by this machine; the PR is the shared
truth and is what the operator sees. Preferring local state is how the ceremony got here.

*Rejected:* PR-only, no manifest rung. That makes a destructive path hard-depend on network
reachability at exactly the moment the operator is finishing a ship.

**KTD3 — Refusal is a hazard, not an in-runner raise.** R2's refusal registers as a new
`ceremony_hazards` entry rather than raising inside `_do_branch_delete`. `detect()` runs at
`ship_ceremony.py:773`, ahead of the `_RUNNERS[upcoming]` dispatch at `:794` and the `saga.py save`
at `:809` (and ahead of the `ship_undo.append_entry` at `:796`), which is the
"ledger provably unadvanced" proof shape #526/#346/#347 all rely on. `acknowledgeable=False`,
matching `MERGE_NOT_LANDED`: there is no legitimate case for deleting the PR base, so there is
nothing to acknowledge. The existing empty/`main` guard **stays** in the runner as defense in depth.

**KTD4 — Ceremony base lives in a per-saga sidecar, not a tick field.** Following
`{#ceremony-sidecars-forward-only-undo-346}`. A tick field rolls with the checkout; a sidecar is
ceremony-scoped. That distinction is the entire defect, so the fix must not reintroduce it.

**KTD5 — The default branch is resolved, never hardcoded.** `git symbolic-ref
refs/remotes/origin/HEAD` with a `gh repo view --json defaultBranchRef` fallback. Replacing one
hardcoded `main` with another hardcoded `main` moves the bug rather than fixing it, and this repo
family already contains repos whose default branch is not the ceremony's base.

**KTD6 — `--operator-confirmed branch_delete:<target>` is required for `branch_delete`.** The bare
form refuses with a message naming the resolved target, so the operator's confirming invocation
carries a value they have actually seen. This is the typed-payload growth #526's own "Revisit when"
clause anticipated. The mismatch rule stays uniform: a qualified confirmation whose target does not
match the resolved target refuses. Every other transition keeps the bare grammar.

*Migration:* two documentation surfaces name the old invocation and must change in the same PR —
`plugins/saga/skills/work/SKILL.md:750-752` and
`plugins/saga/skills/work/references/pr-continuation-loop.md:100-102`.

**KTD7 — In-flight ceremonies need no data migration.** A ceremony that pushed before this ships
already has its `ceremony-branch:` manifest entry and, once `open_pr` has run, a PR — so rung 1 or
rung 2 resolves it. A ceremony with neither has not reached `open_pr`, and `branch_delete` is
structurally unreachable before `open_pr` in `TRANSITIONS`. The refusal path is therefore not
reachable by any legitimate in-flight ceremony.

**KTD8 — R-live runs against a disposable local remote, not GitHub.** A temp bare repo serves as
`origin` with a real clone; git transitions run with a real runner while `gh` calls are stubbed.
This exercises the actual destructive commands against real refs with zero exposure to an
Infiquetra origin. A throwaway GitHub repo was rejected: it adds org-level repo creation and
deletion to a leg whose entire purpose is proving a deletion does *not* happen.

**KTD9 — Tier: opus/high for the resolver and the destructive paths.** Judgment work on
data-loss-class code with a cross-cutting resolution contract. Mechanical units (release surfaces,
base-aware transitions) drop to `sonnet`. Refute-3 verify panels ride only on U2 and U4 — the two
units that change destructive behavior and the safety gate. The locked per-unit tiers live in
`docs/plans/2026-07-25-issue-635-ship-ceremony-base-branch-resolution-spec.json`; the workflow is
emitted from that spec and is regenerable at any time.

**KTD10 — U2's refute-3 panel is adjudicated, not re-run.** The panel fired on 2026-07-25 (run
`wf_048a3245-637`) and halted the workflow: 3/3 verifiers returned a non-empty `refuted` array, which
is all the gate at `workflow.js:307` measures — it counts refuting verifiers, not severity. All
twelve refutations were read. Eleven are bookkeeping about *claims*, not code: a spliced statistic
(`48 → 57`, which is really 47→57 by line or 48→59 by occurrence), an unreproducible test-selection figure
(`163 passed`; the whole-repo run the verifiers substituted is a strictly stronger green signal), an
incomplete file enumeration (an undisclosed but benign `sys.modules[spec.name] = module` loader hunk
in `tests/test_ship_undo.py`, the known `{#sys-modules-stale-patch-620}` pattern), and the
"four assertions" miscount. Two of those reached shipped docstrings and are fixed under R13. The
twelfth was substantive and became defect F. U2's code itself was **upheld** by every verifier with
line evidence, and 130 ceremony/undo/hazard tests pass at the current tree.

Re-running the panel would re-derive verdicts already adjudicated at a cost of 128. The verify block
is therefore removed from U2 in the spec and the adjudication recorded here and in the work-session
artifact. U2b carries its own refute-3 panel, so the destructive change F introduces is not
un-panelled.

**KTD10a — U2b's panel, adjudicated the same way (2026-07-25).** U2b was likewise refuted 3/3, on
eight items. Two were real and were repaired directly, with `tests/test_ship_undo.py` +
`tests/test_ship_ceremony.py` + `tests/test_ceremony_hazards.py` green at 136 passed:

1. **The R13 correction installed a fresh false claim.** U2b replaced "pinned by four test
   assertions" with "carried by four references across the test suite (two of them assertions)",
   verifying the count against `474fd3cc` rather than the working tree the docstring ships in —
   where there are twelve. All three verifiers caught it. Repaired by removing the number outright:
   any reference count is stale the moment a test is added, which is the whole reason R13 exists.
2. **The backward-compatibility fallback did not do what its own comment argued.**
   `LEGACY_MERGE_BASE`'s rationale said a base-less entry's sha provably came from `refs/heads/main`,
   but `_merge_entry_base` routed through `_default_branch()` first, so a `trunk`-default repo would
   revert a legacy entry on `trunk`. Two verifiers reproduced it independently. Repaired by flooring
   at the literal `LEGACY_MERGE_BASE` and deleting `_default_branch`, whose only production caller
   this was. R12's own wording caused this and has been corrected above.

The remaining six were report-accuracy defects with the end state verified good by the verifiers
themselves (a mis-attributed neighbouring assertion, an "existing test" that was new relative to
`474fd3cc`, and an unreproducible red-first narrative — the verifier's variant B reproduced the
underlying R10 property, so the property holds and only the story about it was wrong).

*(Corrected 2026-07-25 after U2c's panel. This paragraph originally said variant B showed "four
behavioral tests failing". It shows **two**: `2 failed, 2 passed`. U2c re-derived it and all three
of its verifiers reproduced the same 2/2 independently — see R10 below for the per-test verdict.
The error was the driver's, written while adjudicating panel 2 from a single verifier's prose
rather than from a run.)*

**KTD10b — U2c's panel, adjudicated PASS (2026-07-25).** Refuted 3/3, on **8 refutations against 51
upheld claims**, and this time *not one* of the eight touches the production code. All three
verifiers say so in terms: "the substance of the claims is independently confirmed and is upheld
separately; what is refuted is that these `file:line` coordinates resolve." The eight fall into
three classes, none of which is a defect in the change set:

1. **Stale `file:line` coordinates (all 3 verifiers).** Real, and confirmed by the driver
   independently: `_merge_entry_base` is at `ship_undo.py:176` not `:175`, its call site `:421` not
   `:415`, the trunk test `tests/test_ship_undo.py:1233` not `:1231`. The offsets are exactly the
   line growth from U2c's own prose edits — it grepped, then edited above the greps, and never
   re-ran them. The coordinates are wrong in a **workflow return value**, which is not a repo
   artifact; nothing on disk carries them. Structural, not careless: *any* unit that edits a file
   after measuring it inherits this, which is the same root cause as the three prior panels.
2. **Cross-unit attribution (2 verifiers).** "U2b claimed 5 failed" is unverifiable *to a verifier*
   because U2b's report lives in the workflow journal, not the repo — the panel cannot see sibling
   units' output. A blind spot in the harness, not a defect in the unit.
3. **Unprovable negatives (2 verifiers).** "U2c's input tree is not materializable, so its delta
   cannot be isolated." True and unfixable: the whole change set is uncommitted, so no snapshot of
   the input state exists to diff against. Verifier 3 got as far as byte-proving `ship_undo.py`
   prose-only from U2c's own scratchpad snapshot, and could not for the other two files.

**The pattern across four panels is now the finding worth keeping.** Of twenty-eight refutations
the verifiers have upheld the *code* every single time; what they refute is almost always a **claim
about** the code — statistics, deltas, citations, attributions. The gate cannot tell those apart:
`workflow.js:307` counts verifiers with a non-empty `refuted` array, unweighted. That conflation is
what makes a 3/3 refutation unreadable without a human pass, and it is worth its own emitter issue
(a `refuted_code` / `refuted_claims` split, so the gate halts on the former and reports the latter).

The panels have nonetheless paid for themselves: they found defect F, the R12 trunk-default bug, and
three false claims that had already reached shipped docstrings. The instrument is coarse, not
useless — the correct fix is to sharpen the verdict schema, not to lower the bar.

**KTD10c — U4's panel, and the one that changed the code (2026-07-25).** Refuted 3/3 on **4
refutations against 42 upheld**. Two were the familiar unverifiable class (a line number in an
intermediate uncommitted tree that no longer exists; a red-first claim whose "before" state git never
retained — note the contrast the verifier itself drew, that U4's *hazard-file* red-first claim WAS
reproducible and matched exactly). The other two were real:

1. **The R2 hazard was inert on the resolver's preferred rung, and the code said otherwise.** U4 had
   deviated deliberately — injecting `resolved_head` into the probe — precisely to stop the hazard
   being a dead check, and reported that it now compared "two derivation paths". A verifier traced
   the operands and showed the deviation does not achieve that on rung 1: `run()` injects the head
   that rung 1 read from `gh pr view`, and the probe re-issues the *same* query for the base, so both
   still originate in one PR record. It also spotted that both integration tests force the fake PR's
   base to equal its own head — a topology GitHub forbids.

   The verifier's diagnosis was right and its framing was slightly off: this is not a defect in the
   design but an overclaim about it. A backstop on the fallible rung is the correct shape. The repair
   was therefore to say so exactly (probe docstring, `run()` comment, R2 above) **and** to add the
   missing test for the only path where the hazard can fire — which was entirely uncovered. That test
   is red-first: remove the probe and the ceremony walks into `git rev-parse` on the base branch.

2. **"Byte-unchanged" was false for the uniform mismatch rule.** The guard's operand changed from the
   raw confirmation string to the parsed transition name, which silently moved one input —
   `merge:x` with `merge` upcoming — from the mismatch refusal to the "does not take a confirmation
   target" refusal. Both refuse; the new wording is the more accurate diagnosis. CLI-unreachable
   before the change, Python-API-reachable. Now documented at the guard and pinned by
   `test_qualified_target_on_a_transition_that_takes_none_refuses`.

**This is what the panel is for.** Five panels in, the first four refuted only claims; this one found
a safety control that was narrower than advertised and a test suite that proved the wrong thing. The
cost of the four false alarms bought this. That is the trade, and on a change set whose failure mode
is deleting a branch off `origin`, it is worth paying.

## Implementation units

### U1. Ceremony ref resolution core

Add the resolver and its sidecar; change no call site yet.

**Files:** `plugins/saga/scripts/ship_ceremony.py` (new `CeremonyRefs` dataclass,
`resolve_ceremony_refs()`, `resolve_default_branch()`, base-sidecar read/write helpers).

**Behavior:** `resolve_ceremony_refs(saga, *, repo_root, runner) -> CeremonyRefs` returning
`head`, `base`, and `source` (the rung that answered). Walks KTD2's ladder and raises
`CeremonyRefsError` when exhausted. `resolve_default_branch()` implements KTD5.

**Test scenarios** (`tests/test_ship_ceremony.py`):

- rung 1 wins when a PR ref exists — `gh pr view` stub returns head/base; `saga["branch"]` set to a
  *different* value and is not consulted.
- rung 2 answers when the `gh` call fails — manifest entry supplies head, sidecar supplies base.
- ladder exhausted (no PR ref, no manifest entry) raises `CeremonyRefsError`; asserts the message
  names both missing sources.
- `saga["branch"]` is never returned, even when it is the only value present.
- `resolve_default_branch()` returns the symbolic-ref answer; falls back to `gh repo view`; raises
  rather than defaulting to `"main"` when both fail.

### U2. Destructive paths consume the resolver (defects A and E)

Fix both destructive sites. E is not merely bad evidence: a `merge_sha` pointing at the default
branch's tip is fully reachable, so the undo engine's `SHA_UNREACHABLE` guard never fires and the
bad revert lands.

**Files:** `plugins/saga/scripts/ship_ceremony.py` (`_do_branch_delete`, `_do_merge`).

**Behavior:** `_do_branch_delete` resolves once and uses that single value for the `git rev-parse`,
the `git branch -d`, the `git push origin --delete`, **and** `_branch_resource_id()` for the
manifest close (R3). The empty/`main` guard stays. `_do_merge` reads `refs/heads/<resolved base>`
for both SHA probes instead of `refs/heads/main` (R6); the returned key stays `pre_merge_main_sha`.

**Test scenarios** (`tests/test_ship_ceremony.py`):

- **headline regression (red-first):** leaf-into-outcome fixture where the last tick save happened on
  the base branch, so `saga["branch"] == "outcome/demo"`. Asserts the `git branch -d` and
  `git push origin --delete` argv name the **head** branch and that no command anywhere in the
  transition names the base.
- the manifest entry closed is `ceremony-branch:<head>`, and the head entry's status becomes closed —
  the part-2/part-3 divergence cannot recur.
- `_do_merge` on an outcome-based PR probes `refs/heads/outcome/demo` for both SHAs; the recorded
  `merge_sha` equals the base ref's post-merge tip, and differs from `pre_merge_main_sha` in the
  fixture where the base advanced.
- **revert-safety (red-first, the reason E is destructive and not merely wrong evidence):** against
  current code on an outcome-based PR, the recorded `merge_sha` is `main`'s *unchanged, reachable*
  tip. So `ship_undo._undo_merge`'s `SHA_UNREACHABLE` guard (`ship_undo.py:360`) does **not** fire —
  `git revert --no-edit <sha>` succeeds against an unrelated healthy commit on the default branch
  and is pushed. Assert the recorded `merge_sha` is a commit introduced by *this* merge, so the
  guard is not the thing standing between a mis-recorded SHA and a bad revert.
- `_do_merge` on a main-based PR is byte-identical in behavior to today (no regression for the
  common case).

### U2b. The undo path applies the revert to the recorded base (defect F, R12, R13)

Make the recovery path honor the same base the forward ceremony did.

**Files:** `plugins/saga/scripts/ship_undo.py` (`_undo_merge`, `append_entry`),
`plugins/saga/scripts/ship_ceremony.py` (the two R13 docstring corrections),
`tests/test_ship_undo.py`.

**Behavior:** `_undo_merge` resolves the ceremony's base from the rollback-manifest entry and uses
that single value for the checkout, the revert, and the push — replacing all three hardcoded `main`
literals at `:363-367`. `append_entry` records the base on the `merge` entry so the value is
available at undo time without a network call (it is written by `_do_merge`, which already resolves
it under U2). An entry with no recorded base — every manifest written before this ships — falls back
to the repo default branch, preserving today's behavior exactly.

`_sha_reachable` is **not** changed: it is an existence probe, honestly documented as best-effort,
and F is a wrong-target defect rather than a wrong-probe one.

Also apply R13: correct the `_do_merge` docstring's false safety claim (it may assert the property
only once R12 lands, so state the dependency) and its "four test assertions" miscount.

**Test scenarios** (`tests/test_ship_undo.py`):

- **headline (red-first):** a merge entry recording base `outcome/demo`; assert the checkout, the
  `git revert`, and the `git push` argv all name `outcome/demo` and that **no** command in the
  transition names `main`.
- the leaf-landed-on-main hazard the panel found: outcome branch already merged to `main`, undo of
  the leaf's merge must not touch `main`.
- backward compatibility: a manifest entry with **no** recorded base still undoes against the repo
  default branch, byte-identical to today.
- a main-based ceremony is behaviorally unchanged (no regression for the common case).

### U3. Base-aware transitions (defects B, C, D)

Stop hardcoding `main` in the checkout and both PR-create calls.

**Files:** `plugins/saga/scripts/ship_ceremony.py` (`_do_checkout_main`, `_do_open_pr`, `start()`,
and `start()`'s CLI surface in `_build_parser`).

**Behavior:** `_do_checkout_main` checks out the resolved base. Its **return value stays
`saga.get("branch")` — do not "fix" it.** That field is the `checkout_main` rollback-manifest
entry's `branch`, consumed by `ship_undo._restore_pre_ceremony_checkout` (`ship_undo.py:370-395`),
whose contract is to restore *the pre-ceremony checkout — the saga's own branch*, not the branch
that was checked out. Returning the resolved base instead would make `current == branch` true
immediately after `checkout_main` and turn that undo step into a permanent silent no-op. Both
`gh pr create` invocations gain `--base <resolved>`. `start()` accepts an explicit base, defaults to
`resolve_default_branch()`, and records it to the KTD4 sidecar so later transitions can resolve it
without a PR query.

**Test scenarios** (`tests/test_ship_ceremony.py`):

- `checkout_main` on an outcome-based PR issues `git checkout outcome/demo`; on a main-based PR,
  `git checkout main` (unchanged).
- **undo-contract pin (regression, must pass before and after):** `checkout_main`'s returned
  `branch` is still `saga["branch"]`, so the `checkout_main` rollback-manifest entry keeps
  restoring the operator's pre-ceremony checkout.
- `_do_open_pr`'s fresh-create argv contains `--base <resolved>`; the existing-draft path is
  untouched (it flips ready and must not re-create).
- `start()` with an explicit base records it to the sidecar and passes it to `gh pr create --draft`.
- `start()` with no explicit base uses `resolve_default_branch()`, and does **not** emit the literal
  string `"main"` when the resolved default is something else.

### U4. Hazard and named-target confirmation (R2, R8)

Refuse before mutation, and make the operator confirm a target.

**Files:** `plugins/saga/scripts/ceremony_hazards.py` (new hazard + registry entry),
`plugins/saga/scripts/ship_ceremony.py` (`run()`'s confirmation parsing, `_build_parser`).

**Behavior:** new `BRANCH_DELETE_TARGETS_BASE` hazard, `acknowledgeable=False`, probed only for the
`branch_delete` transition; fires when the resolved head equals the resolved base. `run()` accepts
`--operator-confirmed branch_delete:<target>`; a bare `branch_delete` refuses with a message naming
the resolved target; a qualified target that does not match the resolved target refuses.

**Test scenarios** (`tests/test_ceremony_hazards.py`, `tests/test_ship_ceremony.py`):

- the hazard fires when head == base and is **not** acknowledgeable via `--acknowledge-hazard`.
- the hazard refusal happens before `_RUNNERS` dispatch and before `saga.py save` — assert no git
  command ran and `ceremony_transition` is unchanged.
- bare `--operator-confirmed branch_delete` refuses, and the error text contains the resolved target.
- `--operator-confirmed branch_delete:<wrong>` refuses; `:<resolved>` proceeds.
- every other transition's bare confirmation grammar is unchanged (regression over the existing gate
  tests).

### U5. Release surfaces, documentation, and journal

Ship the metadata and the durable record with the code.

**Files:** `plugins/saga/.claude-plugin/plugin.json` (0.114.0 → 0.115.0),
`.claude-plugin/marketplace.json`, `plugins/saga/CHANGELOG.md`,
`tests/test_saga_plugin.py:48` (**the only saga drift pin**),
`plugins/saga/skills/work/SKILL.md` and
`plugins/saga/skills/work/references/pr-continuation-loop.md` (KTD6 invocation grammar),
`docs/engineering-journal/LEARNINGS.md` and `docs/engineering-journal/DECISIONS.md`.

**Behavior:** no runtime behavior. `fleet_commons/` is untouched, so **no fleet-core bump**; no
mission-control verb is added, so **no mission-control bump**.

**Test expectation:** `uv run python scripts/check_release_surface_parity.py` exits 0, and
`tests/test_saga_plugin.py:48` asserts `saga 0.115.0`.

**Do not touch `tests/test_liveness_events.py` or `tests/test_team_execution_liveness.py`.** Those
pin `fleet_core_version == "0.23.0"`, not the saga version (verified at `474fd3cc`:
`test_liveness_events.py:698`, `test_team_execution_liveness.py:179,409`). This PR ships no
fleet-core bump, so both files stay unmodified — editing them to a saga version would assert a
saga string against a fleet-core field and fail.

## Dependency order

`U1 → U2`, `U1 → U3`, `U1 → U4` (all three consume the resolver). `U2 → U2b`: U2b consumes the base
that U2's `_do_merge` records, and carries U2's R13 docstring corrections. `U2b`, `U3`, `U4` are
mutually independent. `U5` runs last: the CHANGELOG and journal entries describe what U2–U4 actually
did.

**Run state (2026-07-25).** U1 and U2 are **complete** — shipped to the working tree on
`work/635-ceremony-ref-resolution`, upheld by all three verifiers with line evidence, 130
ceremony/undo/hazard tests passing. The continuation run executes `U2b → U3 → U4 → U5`.

## Risk analysis

| Risk | Likelihood | Mitigation |
|---|---|---|
| A resolver bug deletes the wrong branch anyway | low | R2's hazard is an independent second check on a different derivation path; the runner's empty/`main` guard is a third. R-live proves it against real refs. |
| `gh pr view` latency or failure inside the destructive path | medium | Rung 2 (local manifest) answers without network; only an empty ladder refuses, and KTD7 shows no legitimate in-flight ceremony can hit that. |
| KTD6 breaks an operator's muscle memory or an unseen caller | medium | Bare form refuses loudly and prints the exact qualified command to re-run. Caller sweep found exactly two doc surfaces and no code callers outside `ship_ceremony.py` / `ship_undo.py`. |
| A weakened test seam hides a regression | medium | R9 forbids silent test edits; any test whose assertion changes must be named in the PR body with justification. |
| Sibling-PR version collision at merge | medium | Re-check the saga version at merge time — this has bitten repeatedly across this campaign. |

## Scope boundaries

**Deferred to follow-up work:**

- `_teardown_attempt_closes` does not auto-close `branch`-kind entries, so a ceremony **already** in
  the mis-targeted state stays teardown-blocked even after this fix. That is a recovery-path gap, not
  a cause; it warrants its own defect if any such ceremony is found in the wild.
- The `check=False` on `git push origin --delete` swallows remote-deletion failures. Out of scope
  here — it is a reporting weakness, not a mis-target — but worth its own issue.

**Explicit non-goals:**

- #642 (`installed_plugins.json` registry staleness) — different registry, unrelated.
- #628 (cross-runtime double dispatch) — different subsystem.
- #626 — closed; #657 / #658 / #659 — filed 2026-07-24, separate.
- `codex#45` — a downstream leaf in another repo; `sub-635` is a campaign isolate and blocks nothing.
- The `_saga_short_id` split-brain flagged during the #620 review. This plan touches `_do_open_pr`'s
  and `start()`'s `saga save` calls, which consume `_saga_short_id`, but changes neither its
  definition nor its call sites — the requirement is only that the plan **not make it worse**, which
  U3's diff satisfies by leaving those argument lists alone.
- Making the pre-push gate's 300 s timeout configurable (#658), even though this PR's test additions
  push the suite closer to that ceiling.

## Verification

```bash
uv run pytest -q tests/test_ship_ceremony.py tests/test_ceremony_hazards.py
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
uv run python scripts/check_release_surface_parity.py
```

Red-first proof (R10): each new behavioral test must be run against `474fd3cc` and shown failing
before the fix lands. Capture that output in the work-session record.
