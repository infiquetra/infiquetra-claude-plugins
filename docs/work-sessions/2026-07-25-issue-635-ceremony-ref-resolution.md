# Work session — #635 ship_ceremony resolves ceremony refs instead of guessing them

- **Issue:** infiquetra/infiquetra-claude-plugins#635 (leaf `sub-635` of outcome
  `governed-execution-integrity`, Objective #639). A campaign **isolate** — blocks nothing, blocked
  by nothing.
- **Plan:** `docs/plans/2026-07-25-issue-635-ship-ceremony-base-branch-resolution-plan.md`
- **Doc-review:** `docs/reviews/doc-review-issue-635-2026-07-25.md` (5 findings — 1 P0, 3 P1, 1 P3 —
  all fixed in place, zero unresolved P0/P1)
- **Branch:** `work/635-ceremony-ref-resolution` (base `main` `474fd3cc`)
- **Saga:** `issue-635`, `lifecycle_phase=work`
- **Backend:** `cc-workflows-ultracode`, 7 units, spend 370
- **Release surface:** saga `0.114.0 → 0.115.0`. No fleet-core bump (`fleet_commons/` untouched),
  no mission-control bump (no verb added).

## The defect in one sentence

`saga.py:566` stamps `"branch": git branch --show-current` on **every** tick save, so the field means
"whatever branch the last save happened on" — not "the branch this ceremony opened." Five call sites
in `ship_ceremony.py` read that field, or the literal string `main`, as if it recorded ceremony
identity. On a leaf-into-outcome PR whose last save happened on the base branch, `branch_delete`
therefore deleted **the base branch**, local and origin.

The real incident (2026-07-20/21, `infiquetra/team-norns`, saga `issue-236`) destroyed
`outcome/norns-next-horizon` on both sides while the actual feature branch survived. Recovery
depended on the rollback manifest's recorded head SHA plus local object-store retention.

## Six sub-defects, not four

The plan opened with four (A–D). Two more surfaced during the build, both from verify panels:

| | Site | Was | Now |
|---|---|---|---|
| **A** | `_do_branch_delete` | deletes the resolved-from-rolling-field target | one resolved head drives the delete, the `rev-parse` check **and** the manifest close |
| **B** | `_do_checkout_main` | hardcoded `main` | checks out the resolved base; **return value deliberately unchanged** |
| **C** | `_do_open_pr` | no `--base` | explicit `--base` from ceremony context |
| **D** | `start()` | no `--base` | explicit `--base` + `--base` CLI flag + sidecar record |
| **E** | `_do_merge` | reads `refs/heads/main` for both SHAs | probes the ceremony's resolved base ref |
| **F** | `ship_undo._undo_merge` | checks out / reverts on / pushes `main` | all target the recorded base |

**F is why E alone was not enough.** E records the right squash SHA; F is what *applies* it. Fixing E
without F moves the bug rather than removing it — and the `SHA_UNREACHABLE` guard could never have
caught it, because `_sha_reachable` is `git cat-file -e <sha>^{commit}`, a pure existence probe. A
mis-recorded but perfectly valid SHA passes it. Reachability is not provenance.

## The three-part failure behind defect A

Worth recording because only one third of it is visible at the point of failure:

1. The deletion ran against the base branch, with the origin-side `git push --delete` swallowing
   failure under `check=False`.
2. The manifest close addressed `ceremony-branch:<base>` — an id never registered — so
   `_close_if_registered`'s by-design no-op on unknown ids hid the divergence with no error.
3. The real branch's `ceremony-branch:<head>` entry stayed `open` **forever**, because
   `_teardown_attempt_closes` auto-closes only `scratch` and `worktree` kinds, never `branch`. Every
   later teardown attempt raised `TeardownBlockedError` permanently.

That is why target resolution had to be centralized into one helper consumed by both the delete and
the manifest key: they could not be allowed to diverge again.

## Design: a ladder that refuses rather than guesses

`resolve_ceremony_refs()` — rung 1 the PR itself (`gh pr view --json headRefName,baseRefName`),
rung 2 the `ceremony-branch:` opened-resource manifest entry plus a per-saga base sidecar, rung 3
**raise**. `saga["branch"]` is not a rung at any level, including last resort. On a destructive path
a refusal is strictly better than a guess.

Two safety additions:

- **`BRANCH_DELETE_TARGETS_BASE` hazard**, `acknowledgeable=False` (there is no legitimate case for
  deleting the branch you just merged into, so there is nothing to acknowledge). It refuses *before*
  `_RUNNERS[upcoming]` dispatch and *before* `saga.py save`, so the ledger is provably unadvanced.
- **Typed confirmation** `--operator-confirmed branch_delete:<target>` — the operator names the
  branch they are destroying, and the refusal message tells them the resolved value so their next
  invocation carries something they have actually seen. This is what #526's own "revisit when"
  clause anticipated.

### The hazard's reachability is rung-scoped, and the code now says so

Found by U4's panel and worth stating plainly: on **rung 1** the head and base both come from a
single `gh pr view` record, and GitHub forbids a same-repo PR whose head is its base — so the probe
is inert there **by construction**. That is correct, not a gap: rung 1 is authoritative and cannot
produce a wrong target.

The hazard exists for **rung 2**, where the head comes from the manifest and the base from the PR:
two independent records that can agree wrongly. That is exactly the incident shape. Any claim that
this probe compares "two derivation paths" in general is false and must not be restated.

`test_branch_delete_targets_base_fires_on_the_rung_2_incident_topology` covers the reachable path and
is red-first: remove the probe from the `branch_delete` pipeline and the ceremony walks into
`git rev-parse outcome/norns-next-horizon` — it reaches the deletion path for the base branch.

## R10 red-first, at the honest count

For defect F: restoring the literal `474fd3cc` file reds all four candidate tests, but three of those
reds are `TypeError` / `KeyError` / `AttributeError` — the tests never reach the behavior. Reverting
*only* `_undo_merge`'s body gives **2 failed, 2 passed**:

- `test_undo_merge_targets_recorded_base_not_main` — genuine.
- `test_undo_merge_does_not_touch_main_when_outcome_already_landed` — genuine, and the only
  **data-loss demonstration**: local `main`'s SHA moves.
- `test_undo_merge_without_recorded_base_floors_at_legacy_main` — pins pre-#635 behavior
  argv-for-argv, so pre-F code satisfies it by construction. A characterization test.
- `test_base_less_entry_ignores_a_non_main_default_branch` — only unit-calls `_merge_entry_base`,
  never invokes `undo()`. Cannot produce a behavioral red at all.

Keep all four; count two. A test that cannot fail against the old code is still worth having — it
just is not red-first evidence. All three of U2c's verifiers reproduced the 2/2 split independently.

**The code review's testing lens then found the concession is one too harsh.** Reverting only
`_undo_merge`'s body reds a *third* test the plan never counted —
`test_option_like_recorded_base_refused_before_shellout`, whose `ExplodingRunner` fires because the
revert removes the pre-`_sha_reachable` option-safety check. So the honest figure is 3 red of 6 new
undo tests, not 2 of a 4-test set. The plan undersold its own evidence. That is the failure direction
to prefer, and it is worth noting that the same audit confirmed **all five** docstrings claiming
"red-first" do go red, with every characterization test correctly labeled "must pass before and
after" — no overclaim in any docstring, CHANGELOG line, or journal entry.

## Provenance beats currency (R12)

A rollback-manifest entry written before this ships carries no recorded base, and floors at the
**literal** `main` (`ship_undo.LEGACY_MERGE_BASE`) — deliberately *not* the repo's resolved default
branch. Such an entry's `merge_sha` was read by a pre-#635 `_do_merge` that probed `refs/heads/main`
verbatim, so `main` is provably where it came from. Resolving the current default would revert on
`trunk` in a trunk-default repo — a wrong branch, chosen by fresher information.

## Verify panels: five rounds, and what they were actually worth

| Panel | Refuted | Upheld | Real code findings |
|---|---|---|---|
| U2 | 12 | — | 1 — **defect F** |
| U2b | 8 | — | 2 — R13 false count, R12 trunk-default bug |
| U2c | 8 | 51 | 0 |
| U4 | 4 | 42 | 2 — hazard rung-scoping, mismatch-guard behavior change |
| **code-review** (3 lenses) | — | — | **8 — 1 P0, 1 P1, 3 P2, 3 P3** |

Four of the five refutations-by-majority were driven by **claims about** the code rather than the
code: stale `file:line` coordinates, cross-unit attributions the panel structurally cannot see,
unprovable negatives about an uncommitted input tree. The gate cannot tell those apart —
`workflow.js:307` counts any verifier with a non-empty `refuted` array, unweighted.

**The root cause of the coordinate class was mechanical and is now fixed at the source.** A unit
greps a file, then edits *above* those lines, and never re-measures; the offsets are exactly its own
insertion counts. Symmetrically, the plan was handing U3/U4/U5 anchors written against `474fd3cc`
after the tree had grown 381 lines. Both directions are the same bug. The spec now carries an
anchor-discipline clause: **the symbol is authoritative, the line is advisory**, and no unit may
quote a figure it measured before its own edits shifted it.

The panels still paid for themselves — defect F, the trunk-default bug, three false claims that had
already reached shipped docstrings, and a safety control narrower than advertised. On a change set
whose failure mode is deleting a branch off `origin`, that trade is worth paying.

## Change set

18 files across three commits (plan artifacts, the change, the code-review repair). Production:
`ship_ceremony.py`, `ceremony_hazards.py`, `ship_undo.py`. Tests: `test_ship_ceremony.py`,
`test_ship_undo.py`, `test_ceremony_hazards.py` — **56 net new tests** (103 → 159 test functions;
168 collected). The build's own commit message claimed 49; the true figure there was **48** (49
added `def`s, one of them replacing a rewritten test), and the code-review repair adds 8 more.
Release surfaces: `plugin.json`,
`marketplace.json`, `CHANGELOG.md`, drift pin `test_saga_plugin.py:48`. Docs: `work/SKILL.md` and
`references/pr-continuation-loop.md` migrated to the qualified grammar. Journal: `LEARNINGS.md`
`{#ceremony-tick-field-as-state-635}`, `DECISIONS.md` `{#ceremony-ref-resolution-635}`.

## Gates — all run against the delivered tree

| Gate | Result |
|---|---|
| `uv run pytest -q` | **5487 passed, 0 failed, 1 skipped** |
| `uv run ruff check .` | `[]` |
| `uv run ruff format --check .` | 439 files already formatted |
| `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` | exit 0 — no issues in 269 source files |
| `uv run bandit -r` (3 changed production files) | 0 issues at every severity |
| `uv run python scripts/check_release_surface_parity.py` | all plugins in parity |
| Settlement | 7/7 delivered, casualties 0, **`halt_required=false`**, DLQ empty |

## The code review found what five verify panels did not

Artifact: `docs/code-reviews/2026-07-25-issue-635-ceremony-ref-resolution-code-review.md`.
**BLOCKED at `6b0a8180`** — 1 P0, 1 P1, 3 P2, 3 P3 — then CLEAN after repair.

The P0 is the one worth carrying forward. The fix removed the divergence *inside*
`_do_branch_delete` — one resolved value driving the delete, the `rev-parse`, and the manifest key —
and reintroduced the identical class of split one level up. `run()` resolved the refs, validated the
operator's typed confirmation against them, handed the resolved head to the hazard probe, and then
dispatched `_RUNNERS[upcoming](saga, repo_root=..., runner=...)`: a signature carrying none of it.
`_do_branch_delete` resolved again from scratch.

That matters only because the ladder is *designed* to degrade silently — any non-zero `gh` exit drops
rung 1 to rung 2. So a single transient failure inside one `run()` makes the two resolutions answer
from different rungs and name different branches. Two lenses reproduced it independently; the sharper
run deleted `outcome/norns-next-horizon` local and origin **through the new code**, with the
non-acknowledgeable hazard reporting clean, because the hazard had been evaluated against a value the
destructive step never saw.

The general lesson is narrower and more useful than "check your work": **a validated value must
travel to the thing it authorizes.** A uniform dispatch table is a natural place to drop it, and no
amount of correctness *inside* the callee recovers it. The repair passes the validated `CeremonyRefs`
object through, so "the branch the operator authorized" and "the branch git deletes" are the same
object rather than two computations that usually agree.

Five refute panels missed it. They were scoped to units — each verified its own unit's claims — and
this defect lives in the seam between U1's resolver and U4's gate. The code review's diff-wide scope
is what surfaced it, which is an argument about *where* to look, not about effort.

## R-live discharged (plan KTD8)

It had not been run when the build reported complete. A temp bare repo as `origin`, a real clone,
real `git branch -d` and `git push origin --delete` against real refs, `gh` stubbed to force rung 2.
No network, no Infiquetra origin.

| Leg | Base `outcome/norns-next-horizon` | Head `work/leaf-635` |
|---|---|---|
| Fixed | survives local **and** origin | deleted from both |
| Pre-fix `474fd3cc` | **destroyed locally** | untouched, stranded |

The counter-proof reproduces the incident exactly, and incidentally demonstrated the `check=False`
follow-up rather than arguing it: the pre-fix ceremony raised nothing while the remote delete
silently failed.

## Known follow-ups (noted, not filed)

- The emitter renders the GitHub slug as "PRIMARY REPO PATH" in every verifier prompt, so
  `git -C <slug>` cannot resolve. Verifiers worked around it themselves.
- A `refuted_code` / `refuted_claims` split in the verdict schema, so the gate halts on the former
  and reports the latter.
- `_teardown_attempt_closes` does not auto-close `branch`-kind entries — by design, but it turns any
  mistargeted delete into a permanent teardown block.
- `git push origin --delete` runs with `check=False`; the destructive remote op silently swallows
  failure.
- U5 returned the literal string `"placeholder - will be replaced"` as its structured result while
  its files landed correctly. Settlement validates receipt **shape**, not content, so it classified
  as `delivered`.
