---
reviewed_revision: 9224198b391e6eccc7c4e483ff56ad71e5513429
---

# Code review — issue 998, cycle 1

The change is accepted. Five findings, none above P3; two were repaired during the review and three
are recorded residuals, none of which blocks.

## Review-result contract

| Field | Value |
|---|---|
| Target | branch `issue/998` |
| Base | commit `30c36bb5` on `main`, confirmed as the merge base with `origin/main` |
| Reviewed commit | `9224198b391e6eccc7c4e483ff56ad71e5513429` (`fix(saga): name both runpy loaders and hoist the runbook path`) |
| Mode | interactive, the skill's default, run by the card driver |
| Outcome | `accepted` |
| Derived overall | 9.6 of 10 |
| Lowest applicable dimension | 8.0, shared by adversarial `scope-creep-risk` and agent-usability `machine-readable-output-actionable-errors` |
| Acceptance rule | overall at or above 9.0 and every applicable dimension at or above 7.0, per `plugins/saga/references/lens-roster.json` |
| Findings | 5 total: 0 at P0, 0 at P1, 0 at P2, 5 at P3 (2 repaired, 3 recorded) |
| Cycle | 1 of a possible 3; no repair cycle was needed |
| Saga | `issue-998` |
| Linked issue | infiquetra/infiquetra-claude-plugins#998, child of grouping #1005 |
| Plan | `docs/plans/2026-09-19-issue-998-plan-save-proof-cli-entrypoint-plan.md` |
| Work session | `docs/work-sessions/2026-09-19-issue-998-plan-save-proof-cli-entrypoint.md` |
| Artifact | this file |

The reviewed commit is the branch head. The two repairs the review produced landed in it, and every
gate below was re-run at that revision rather than inherited from the revision before it.

## How this review was run

The caller approved the recommended lens set (`accept-recommended`) in its launch message. A
caller-supplied selection is an approval record under the skill's own contract, so the operator
question was not asked again.

**Transport deviation, recorded.** The caller forbade spawning subagents, so the lens fan-out ran in
this thread instead of as parallel read-only verifier agents in disposable worktrees. That changes
who executed each lens, not which lenses ran or what each was asked. Both sibling cards merged today
recorded the same deviation.

- **Always-on:** correctness, security, testing, architecture and maintainability.
- **Conditional, approved:** adversarial (this file's siblings each hid a second seam that only the
  adversarial lens found); application-programming-interface contract (the file gains a command-line
  surface with an exit-code and stream contract); documentation clarity (help text, module docstring,
  changelog, two journal entries and load-bearing code comments all ship together); agent usability
  (the card is itself an agent-usability finding, so that lens should judge the repair).
- **Not selected:** previous-comments (no pull request exists yet), deployment and infrastructure,
  performance, reliability, privacy, accessibility — none has an applicable dimension in this diff.

## Scope check

**Result: clean.** Intent, from the plan and the commit messages: give `plan_save_proof.py` a
command-line entrypoint that says what it is and names the command that runs it. Delivered: exactly
that, plus the PyYAML move the new `--help` needs to work on a bare interpreter, one guard, its
canary, the release bookkeeping and the journal entries this repository requires to ship with a
behavior change. No file in the diff is unrelated to that intent.

## Plan-completion audit

| Requirement | Verdict | Evidence |
|---|---|---|
| R1 — `--help` names the file and its runnable command, exit 0 | done | Run directly: usage names the proof and `plan_save_contract.py --root <checkout> validate`. Asserted in the guard. |
| R2 — every other direct invocation exits 2, stderr carries usage, stdout empty | done | Bare invocation, unknown flag and a guessed subcommand each probed; the guard asserts `stdout == ""` on all three. |
| R2a — the entrypoint parses the real command line | done | A malformed argument reaches argparse and exits 2, which is only reachable if `sys.argv` is read. |
| R3 — R1 holds with no PyYAML installed | done | The guard builds a virtual environment without PyYAML, asserts that absence first, then runs `--help` there. |
| R4 — the runpy loader does not execute the entrypoint | done | `plan_save_contract.py validate` against a clean temporary checkout still returns `outcome: valid` at exit 0. |
| R5 — one named guard plus a behavioral mutation with teeth | done | `plan-save-contract-proof-cli` reports `caught`; `tests/test_wiring_canary.py::test_plan_contract_guards_have_teeth` passes. |
| R6 — release surfaces move together | done | Saga `0.159.3` across four surfaces; parity and the diff guard against `30c36bb5` both green. |
| U1 through U4 | done | All four units landed; files listed in the work session. |
| U3's canary mutation, as the plan specified it | **changed** | The plan names an unconditional entrypoint as the mutation; the shipped entry uses a different one. See finding 5. |

The honesty rule was applied to R4: it is verified by a positive run against a clean checkout, not
by inferring from the absence of a failure.

## Findings

| # | Priority | File | Issue | Lens | Confidence | Route | Status |
|---|---|---|---|---|---|---|---|
| 1 | P3 | `plugins/saga/scripts/plan_save_proof.py:553` | The entrypoint guard's comment named one runpy loader; there are two | architecture | 100 | safe_auto | repaired in `9224198b` |
| 2 | P3 | `plugins/saga/scripts/plan_save_proof.py:538` | The help epilog built a `Path` inline where the sibling path is a module constant | architecture | 75 | safe_auto | repaired in `9224198b` |
| 3 | P3 | `plugins/saga/scripts/plan_save_proof.py:24` | The PyYAML move is a second defect class inside a discoverability card | adversarial | 100 | advisory | recorded, accepted |
| 4 | P3 | `plugins/saga/scripts/plan_save_proof.py:519` | `main(argv)`'s explicit argument list is never exercised by a test | testing | 75 | advisory | recorded, accepted |
| 5 | P3 | `docs/plans/2026-09-19-issue-998-plan-save-proof-cli-entrypoint-plan.md` | The plan names a canary mutation that was not the one shipped | documentation | 100 | advisory | recorded, accepted |

### 1 — the guard comment named one of two runpy loaders (repaired)

The comment said `plan_save_contract.py` loading this file cannot reach `main()`. True, but
`tests/saga_plan_contract.py:6` loads the same file the same way at test-collection time, and that
is the loader the first canary mutation actually tripped over: an unconditional entrypoint exits the
pytest interpreter outright. Naming one loader hid the more immediate risk from the next maintainer.
The comment now names both and says what each would do.

### 2 — an inline `Path` where a module constant belongs (repaired)

The epilog constructed `Path("plugins/saga/references/plan-save-contract.md")` purely to interpolate
it as text, two lines below `SCRIPT`, which is a module constant. Beyond the inconsistency, an inline
`Path` renders with backslashes on Windows where a repo-relative documentation path should not. It is
now the module constant `RUNBOOK`, matching `PLAN_SKILL` and `SCRIPT`.

### 3 — the PyYAML move is a second defect class (recorded)

Moving the module-scope `import yaml` to its point of use repairs issue #997's defect class inside a
card about discoverability. It is defended in the plan (KTD4), recorded in DECISIONS
`{#998-describe-and-refuse-not-a-second-runner}`, required by R3, and the repository has recorded the
underlying rule twice. Reverting it alone was watched killing the guard, so it is covered rather than
merely adjacent. Accepted: without it, this card ships a `--help` the repository's own rule calls
broken, on the bare interpreter the maintainer runbook tells maintainers to build.

### 4 — `main(argv)`'s explicit argument list is unexercised (recorded)

Every probe runs the file as a subprocess, so `argv` is always `None`. The parameter mirrors
`plan_save_contract.main(argv)`, so it is a convention rather than dead code. Accepted: a test for it
would prove that argparse reads a list, which is not this file's behavior.

### 5 — the plan names a mutation that was not shipped (recorded)

The plan's U3 specifies replacing the `__main__` guard with an unconditional one. That mutation makes
the canary report `error`, not `caught`: the entrypoint fires while pytest imports the module, the run
dies with an INTERNALERROR, and the guard never executes. The shipped mutation returns the success
code from a direct invocation instead — the reported defect itself — and fails the guard cleanly. The
divergence and the reason are recorded in the registry entry's `mutation_description`, in LEARNINGS
`{#998-canary-mutation-must-fail-cleanly}` and in the work session. The plan body was left alone
because the Work skill forbids editing it during execution.

Nothing was suppressed below the confidence-75 admission floor, and no finding was marked
`pre_existing`.

## Lens scores

| Lens | Overall | Lowest applicable dimension |
|---|---|---|
| correctness | 10.0 | 10.0 intent-behavior-completeness |
| security | 9.3 | 9.0 input-trust-boundaries-injection |
| testing | 9.4 | 9.0 requirements-regression-coverage |
| architecture and maintainability | 9.6 | 9.0 readability-naming-error-contracts |
| adversarial | 9.3 | 8.0 scope-creep-risk |
| application-programming-interface contract | 10.0 | 10.0 interface-contract-compatibility |
| documentation clarity | 9.8 | 9.0 shipped-behavior-parity |
| agent usability | 9.2 | 8.0 machine-readable-output-actionable-errors |

**Derived overall 9.6; lowest applicable dimension 8.0.** Both clear the roster's rule, so the
outcome is `accepted`.

The dimension worth naming is agent usability's `discoverability-invocation-schemas` — the one that
scored 6.5 and held this lens below its floor on the issue #926 review that produced this card. It
scores 9.0 here: an agent running `--help` now learns what the file is, that it is a library, the
exact command that runs it, and where the maintainer runbook is.

`machine-readable-output-actionable-errors` is the lowest at 8.0 because the refusal is prose on
standard error rather than a structured object. That is deliberate and defended: standard output must
stay empty so nothing this file prints can be mistaken for the contract tool's JSON envelope, and a
"you cannot run this" message has no consumer that would parse it.

## Independent gates

A failed independent gate blocks readiness even when the numeric outcome accepts. All pass, each run
at the reviewed commit.

| Gate | Result |
|---|---|
| Built versus planned | pass, one documented CHANGED item (finding 5) |
| `uv run ruff check .` | pass, all checks passed |
| `uv run ruff format --check .` | pass, 530 files already formatted |
| `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` | pass, no issues in 355 source files |
| `uv run pytest` over the four affected test files | pass, 100 passed |
| Behavioral canary | pass, `plan-save-contract-proof-cli` reports `caught` |
| `scripts/check_release_surface_parity.py` | pass, all plugins in parity |
| `tools/release_surface_diff_guard.py --base-ref 30c36bb5` | pass, changed plugin bumped its surfaces |

`scripts/gate.sh` was not run: the caller directed the fast inner loop plus the release-surface
checks, with the pull request's CI as the full gate.

## Out-of-diff verification

The correctness lens requires reading code outside the diff for consumer completeness. Every file in
the repository that references `plan_save_proof.py` was enumerated: `plan_save_contract.py` (the
runpy loader, covered by R4), `tests/saga_plan_contract.py` (the second runpy loader),
`tests/test_saga_plan_contract_boundaries.py` (the guard) and `tests/test_saga_plugin.py` (a file
existence check and the version literal). None invokes the file as a subprocess, so no consumer
depended on the exit 0 this change replaces with exit 2.

## Residual risk

The guard builds a throwaway virtual environment, making it the second test in its file to do so.
That cost is accepted: a stub module raising on import would prove the symptom without proving the
repair, which is the reasoning the sibling guard established earlier today.

The load-bearing assumption behind requirement R4 — that `runpy.run_path` names the module it loads
`<run_path>` rather than `__main__` — is documented CPython behavior, was probed directly in this
worktree, and is pinned by a positive test. If a future interpreter changed it, the guard goes red
rather than the defect going silent.

## Next action

Proceed to the pull request. No repair cycle is requested and no override is needed.
