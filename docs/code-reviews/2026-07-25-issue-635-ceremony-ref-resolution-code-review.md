# Code review — #635 ship_ceremony ceremony-ref resolution

- **Mode:** programmatic / report-only, called from `/work` Phase 5.
- **Target:** branch `work/635-ceremony-ref-resolution`, **REVIEWED_SHA `6b0a8180`**.
- **Diff base:** `474fd3cc` (= `origin/main`, verified merge-base; `main` unmoved; zero open PRs).
- **Scope:** 2 commits, 18 files (+3746/−69). Production: `ship_ceremony.py`, `ceremony_hazards.py`,
  `ship_undo.py`.
- **Plan:** `docs/plans/2026-07-25-issue-635-ship-ceremony-base-branch-resolution-plan.md` (R1–R13,
  R-live, KTD1–KTD10c).
- **Verdict at `6b0a8180`: BLOCKED** — 1 P0, 1 P1, 3 P2, 3 P3.
- **Verdict after repair (`REPAIRED_SHA` below): CLEAN** — zero unresolved P0/P1.

## Lens team

Judgment-selected, `inline` backend, 3 concurrent (the above-Haiku cap), each spawned
`saga:readonly-verifier` + worktree isolation at `opus`:

| Lens | Selected because |
|---|---|
| correctness | always-on — resolver ladder, single-source property, refusal semantics |
| security / destructive-ops | always-on — `git branch -d`, `push --delete`, refs becoming argv |
| testing | always-on — 48 new tests, red-first honesty, R9 seam preservation |

Not spawned (no work on this diff): data-migration, deploy-verification, API/contract, infra,
privacy. The maintainability lens's work was folded into correctness and testing, both of which
audit docstring accuracy directly — R13 makes that a first-class requirement here.

## Findings

### P0-1 — the operator-confirmed target is discarded; a second resolution drives the deletion

`ship_ceremony.py:1211` (resolve + validate) → `:1273` (dispatch, carrying nothing) → `:940`
(re-resolve, destructive).

`run()` resolved the ceremony refs, validated `--operator-confirmed branch_delete:<target>` against
them, and handed the resolved head to the hazard probe — then dispatched
`_RUNNERS[upcoming](saga, repo_root=..., runner=...)`, a signature carrying neither the confirmed
target nor the refs. `_do_branch_delete` re-resolved from scratch.

`resolve_ceremony_refs` degrades from rung 1 to rung 2 on **any** non-zero `gh` exit, so one
transient failure between the two calls answers from a different rung and can name a different
branch. **Found independently by both the correctness and security lenses, each reproducing it
end-to-end**; graded P1 and P0 respectively, resolved to P0 per the conservative-route rule.

The security lens's scenario C is the sharp one: `outcome/norns-next-horizon` deleted local **and**
origin *through the new code*, with the non-acknowledgeable `branch_delete_targets_base` hazard
reporting clean — because the hazard had been evaluated against the rung-1 head, not the rung-2 head
that was deleted. The change set closed the derive-independently split *inside* `_do_branch_delete`
and reopened the identical class of split *across the gate*.

Two shipped docstrings asserted the guarantee unconditionally (`:1148-1149`, `:925-926`).

**Repair:** `run()` keeps the validated `CeremonyRefs` and passes it to the runner; `_do_branch_delete`
takes `confirmed_refs` and only self-resolves when called directly. The authorization and the
deletion are now the same object by construction, and a redundant `gh pr view` disappears.
**Regression test:** `test_branch_delete_deletes_the_branch_the_operator_confirmed_not_a_re_resolution`
— red against `6b0a8180`.

### P1-1 — `refs.base` is bound and never used; the only floor is the literal `"main"`

`ship_ceremony.py:940-946`. A hardcoded `"main"` is exactly the class of guess
`resolve_default_branch` was added to remove, and it does not protect a ceremony based on
`outcome/demo`.

Reachable with **no fault injection at all**: `_probe_branch_delete_targets_base` returns `None` when
the saga has no PR number, so on a ceremony with empty `pr_refs` the hazard never runs and rung 1 is
skipped in both resolutions. If rung 2's head equals its base, the base is deleted with zero
automated refusal.

**Repair:** refuse when `branch == refs.base`. Both refs are already in hand; the check costs nothing
and needs no network. **Regression test:**
`test_branch_delete_refuses_when_the_resolved_head_is_the_resolved_base` — red against `6b0a8180`.

### P2-1 — resolved refs reach git argv without the option guard the sibling module applies

`ship_ceremony.py:471`, `:488-492`, `:908`, `:947-949` vs `ship_undo._require_option_safe`.

`ship_undo` treats manifest-sourced strings as hostile argv at five sites; `ship_ceremony` applied
none of it to any resolved ref. The security lens **measured** the consequence: a sidecar containing
`{"base": "-f"}` yields `git checkout -f`, which exits 0 and silently reverts a dirty tree to HEAD.
`checkout_main` is REVERSIBLE tier, so nothing asks the operator first, and `argparse` accepts
`start --base=-f`.

It also bounded the claim honestly: `_do_branch_delete` is *incidentally* protected, because any
option-only token leaves `git branch -d` zero operands and it exits 128 under `check=True` before the
remote delete. That is an accident of argument arity, not a guard.

**Repair:** validate in `CeremonyRefs.__post_init__` (so no unsafe ref can exist in the type at all)
and at `write_ceremony_base` (so `start --base=-f` refuses before persisting). **Tests:**
`test_ceremony_refs_refuses_an_option_like_ref`, `test_write_ceremony_base_refuses_an_option_like_base`.

### P2-2 — `_do_open_pr` resolves a base and discards it, so rung 2 can never answer

`ship_ceremony.py:780` vs the single `write_ceremony_base` call site in `start()`. On any ceremony
opened through the plain-run flow, `ceremony_base.json` never exists, so rung 2 cannot satisfy its
both-or-nothing condition and `checkout_main` / `merge` / `branch_delete` become hard-dependent on a
reachable `gh` — directly contradicting the ladder's stated rationale ("a local answer that needs no
network at exactly the moment an operator is finishing a ship").

**Repair:** persist it, as `start()` does. **Test:**
`test_open_pr_records_the_resolved_base_to_the_ceremony_sidecar`.

### P2-3 — `_probe_stacked_pr` asks about the rolling field, which on this topology is the base

`ceremony_hazards.py:166`. The probe's own summary line says "an open PR based on the branch about to
be deleted"; its operand was `saga["branch"]`. The diff plumbed `resolved_head` into every probe
signature and declined to use it here, with a docstring contradicting the summary four lines above.

Wrong in both directions: a child PR stacked on the real head goes undetected and the branch is
deleted out from under it (the hazard's whole reason to exist), while every sibling leaf still open
against the base fires spuriously — and this hazard **is** acknowledgeable, so spurious firings train
the operator to wave it through.

**Repair:** `branch = str(resolved_head or saga.get("branch") or "")`. `merge` passes no resolved head
and keeps its old operand. **Test:**
`test_stacked_pr_probe_asks_about_the_resolved_head_not_the_rolling_field`.

### P3-1 — `IndexError` escapes the CLI boundary on an absent base ref

`ship_ceremony.py:869-871`. `git ls-remote` exits **0 with empty stdout** for a ref the remote does
not carry, so `.stdout.split()[0]` raises `IndexError` — not in `main()`'s caught tuple, contradicting
the module's own "never an uncaught traceback" contract. Fails safe (it precedes `gh pr merge`).
Surface widened by this diff: the probed ref is now a resolved base that can legitimately be absent,
where before it was the always-present literal `refs/heads/main`.

**Repair:** `_ls_remote_sha` refuses with a diagnosis. **Test:**
`test_ls_remote_sha_refuses_when_origin_carries_no_such_ref`.

### P3-2 — two R13 docstring falsehoods

- `ceremony_hazards.py:340` (`detect()`): described the hazard as comparing "two derivation paths"
  with no rung qualification — the exact claim the plan says must not be restated, surviving in the
  public API's docstring while the probe's own had been corrected. Found by the driver.
- `ship_ceremony.py:575-576` (`_manifest_head_branch`): claimed entries are "never re-stamped";
  `ship_teardown.register` refreshes a still-open entry by design and says so. Found by the
  correctness lens. The ladder's trust argument does not need the false claim.

Both corrected, plus the matching test docstring at `tests/test_ceremony_hazards.py:224`.

### P3-3 — test-count claim and an oracle hole

- "49 new tests" was one high: 49 added `def`s but one replaced a rewritten test, so the net at
  `6b0a8180` was **48**. Corrected here and in the work-session record.
- `_RecordingRunner.mutating_calls` skipped any `git branch` call whose args do not start with `-d`,
  so `git branch -D` and `--delete` would slip through and make `mutating_calls() == []` vacuously
  true for the deletion command if production ever changed the flag. Closed with an explicit
  deny-list. The testing lens proved the oracle is otherwise non-vacuous by running a *successful*
  `branch_delete` through it and observing 3 flagged calls.

## Upheld under challenge (no finding)

- **Single-source inside `_do_branch_delete` (R3)** — one `branch = refs.head` drives `rev-parse`,
  `branch -d`, `push --delete`, and `_branch_resource_id`. Verified by reading and by argv trace.
- **`_do_checkout_main`'s return contract (doc-review P0)** — returning the resolved base would make
  `current == branch` true immediately and permanently no-op `_restore_pre_ceremony_checkout`
  (`ship_undo.py:445-447`). The plan's claim verified in code.
- **R12 provenance-beats-currency** — `_merge_entry_base` consults nothing but the recorded base and
  the literal floor; `ship_undo` contains no `symbolic-ref` or `defaultBranchRef` probe.
- **Refusal ordering** — every refusal precedes the single `_RUNNERS` dispatch and the single
  `saga.py save`. (The P0 is not an ordering defect: the refusals *do* fire first; the value they
  were computed from was not the value dispatch acted on.)
- **Path traversal** — `_validate_saga_id` `fullmatch` guards every path-building entry point;
  the one path built elsewhere is validated callee-side by the identical house regex.
- **Red-first honesty (R10)** — all five docstrings claiming "red-first" empirically go red. The
  plan's 2-of-4 concession for defect F is correct, and **undersells by one**
  (`test_option_like_recorded_base_refused_before_shellout` is a third genuine red). Every
  characterization test is labeled "must pass before and after". No overclaim anywhere.
- **R9 seam preservation** — all 24 removed lines adjudicated; no pre-existing test dropped, no
  assertion weakened. The hazard-ordering oracle was *strengthened* to full-registry equality.
- **Bandit delta** — zero, base and head both `results: 0` at every severity.

## R-live (plan KTD8) — discharged during this review

It had not been run. A temp bare repo serves as `origin` with a real clone; real `git branch -d` and
`git push origin --delete` against real refs; `gh` stubbed to fail, forcing rung 2. Zero network,
zero exposure to any Infiquetra origin.

| Leg | Base `outcome/norns-next-horizon` | Head `work/leaf-635` |
|---|---|---|
| Fixed | survives local **and** origin | deleted from both |
| Pre-fix `474fd3cc` | **destroyed locally** | untouched, stranded |

The counter-proof also surfaced the `check=False` follow-up live: the ceremony raised nothing while
the remote delete silently failed. Both legs re-run green after the repairs.

## Gates (repaired tree)

| Gate | Result |
|---|---|
| `uv run pytest -q` | 5495 passed, 1 skipped, 0 failed |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 439 files already formatted |
| `uv run mypy plugins/ scripts/ tests/` | Success — no issues in 269 source files |
| `uv run bandit -r` (3 production files) | `results: 0`, zero at every severity |
| `check_release_surface_parity.py` | all plugins in parity |
| R-live (KTD8) | both legs PASS |

## Coverage gaps recorded, not fixed

Six error paths remain untested and are noted rather than closed: `resolve_default_branch`'s
invalid-JSON and missing-`name` branches, the resolver's rung-1 invalid-JSON fallthrough and
no-`saga_id` refusal, `_manifest_head_branch`'s unreadable-manifest branch, and the new probe's two
early returns. `write_ceremony_base`'s atomic replace is executed but its `.tmp` sibling is never
asserted gone. `read_ceremony_base`'s two raises **were** closed here, being on a destructive read
path.

## Routing

`/qa` — zero unresolved P0/P1 after repair.
