# Code review — issue 997, cycle 1

The change is accepted. One finding was repaired during the review; six residuals are recorded and none of them blocks.

## Review-result contract

| Field | Value |
|---|---|
| Target | branch `issue/997` |
| Base | commit `9f1bae8a` on `main` (confirmed as the merge base with `origin/main` by `git merge-base`) |
| Reviewed commit | `5c1fd6fd` (`refactor(saga): drop a type-ignore no type checker evaluates`), the head after the cycle-1 repair; the reviewed content is `1b00d357` plus that one-line repair |
| Mode | programmatic, called by the run driver |
| Outcome | `accepted` |
| Derived overall | 9.5 of 10 |
| Lowest applicable dimension | 9 (testing, and documentation clarity) |
| Acceptance rule | overall at or above 9.0 and every applicable dimension at or above 7.0, per `plugins/saga/references/lens-roster.json` |
| Findings | 7 total: 0 at P0, 0 at P1, 0 at P2, 1 at P3 repaired, 6 at P3 recorded and accepted |
| Saga | `issue-997` |
| Linked issue | infiquetra/infiquetra-claude-plugins#997, child of #1005 |
| Artifact | this file |

## How this review was run

The caller approved the recommended lens set (`accept-recommended`) in its launch message, which is a caller-supplied selection and therefore stands in for the operator question the skill would otherwise ask. The caller also forbade spawning subagents. The lens fan-out was executed in this thread rather than as parallel read-only agents in disposable worktrees, which is a transport deviation from the skill's Phase 3 and is recorded here rather than left implicit. It changes who ran each lens, not which lenses ran or what each was asked.

- Always-on: correctness, security, testing, architecture and maintainability.
- Conditional, approved: adversarial (this change repairs an adversarial-lens finding, and its `environment-operator-failure` dimension is the one that scored the card, so the same lens should judge the repair); application-programming-interface contract (the tool's JSON envelope and exit-code set is a contract other programs read); documentation clarity (the change ships a changelog entry, two journal entries and load-bearing code comments); agent usability (the refusal envelope is consumed by agents, so its wording and its `entry` vocabulary matter).
- Not selected: previous-comments (no pull request existed at review time, so there are no review comments to carry), deployment and infrastructure, performance, reliability, privacy, accessibility — none has an applicable dimension in this difference.

## Scope check

**Result: clean.** Intent, from the plan and the commit messages: stop a missing PyYAML from killing `plan_save_contract.py` outside its documented JSON envelope, and stop it reporting the drift exit code while doing so. Delivered: exactly that, plus the `--help` facet the plan records as found during reproduction, plus the tests, the release bookkeeping and the journal entries the repository requires to ship with a behaviour change. No file in the difference is unrelated to that intent.

The `TOOL` constant and the one-line change inside `verify_saved_examples` are the closest thing to an expansion. They are not scope creep: the refusal needed this script's repo-relative path, that function already spelled the same literal, and leaving both would have put the same string in two places in one file.

## Plan-completion audit

Every requirement in the plan is done and confirmable from the difference or from a run.

| Requirement | Verdict | Evidence |
|---|---|---|
| R1 — `validate`, `render --check` and `render --write` each print one JSON object and exit 2 with PyYAML absent, nothing on standard error | done | Asserted for all three in the new guard, including the empty standard error. |
| R2 — the refusal carries `code: engine`, `entry: python dependency`, `file` naming this script, and `PyYAML` in the error | done | All four asserted literally in the new guard; the source emits them from `yaml_module()`. |
| R3 — `--help` prints usage and exits 0 with PyYAML absent | done | Asserted in the new guard, including that the output does not parse as JSON. |
| R4 — every existing behaviour byte-identical with PyYAML present | done | The named suite plus `tests/test_saga_plugin.py` and `tests/test_wiring_canary.py` pass, 106 tests, with no existing assertion changed. |
| R5 — a guard in an interpreter that genuinely lacks PyYAML, plus a canary entry | done | The guard builds a virtual environment without PyYAML and asserts the absence before proving anything; canary `plan-save-contract-missing-pyyaml` reports `caught` at `baseline_exit: 0`. |
| R6 — the release surfaces move together | done | Plugin manifest, marketplace entry, changelog and the drift-guard literal in `tests/test_saga_plugin.py` all read `0.159.2`; parity and diff-guard scripts both pass. |

Units U1 through U4 are each done. The plan's "watch it fail first" step was performed in the condition the plan's fourth decision names — a real virtual environment, not the `PYTHONPATH` stub the card used — and the failure recorded was `ModuleNotFoundError: No module named 'yaml'` at `plan_save_contract.py:26`, exit 1, no JSON.

## Findings

| Key | Priority | Lens | Finding | Status |
|---|---|---|---|---|
| F1 | P3 | architecture and maintainability | The nested `UniqueLoader` carried `# type: ignore[misc]` for subclassing a value typed `Any`. mypy accepts the class without it under both the direct invocation and the full CI scope, so the annotation suppressed nothing — and a type-ignore no checker evaluates silently swallows a real error the day the rules tighten. | Repaired in commit `5c1fd6fd`, verified by running mypy both ways. |
| F2 | P3 | correctness | `except ImportError` catches a missing or unimportable PyYAML. A PyYAML that is present but raises some other exception from its own module body falls through to `main()`'s handler, which converts it to `code: syntax` with `file` naming the YAML carrier — inside the envelope, but attributed to the contract file rather than to the interpreter. | Accepted. The failure stays inside the documented envelope, which is the contract the card is about, and widening the catch would mislabel genuine carrier faults as dependency faults. |
| F3 | P3 | testing | The new guard does not run the tool under `python -O`, while its sibling `test_contract_cli_without_pytest` does. | Accepted. The refusal path uses no `assert` and reads no docstring, so `-O` cannot change it; the sibling needs `-O` because the proof it exercises does read docstrings. |
| F4 | P3 | documentation clarity | The published repair for `code: engine` reads "Restore the named engine file and its dependencies". It now covers two distinct situations: a broken file in the checkout named by `--root`, and a missing dependency of the tool's own interpreter. | Accepted, and this is the decision the plan took deliberately rather than opening the closed code set. The two are told apart by `entry` and `file`, both of which the guard pins. |
| F5 | P3 | architecture and maintainability | The source calls this script's path `TOOL` while `tests/test_saga_spec_consumer_row.py` calls the same path `SCRIPT`, and the new guard asserts one against the other. | Accepted. `SCRIPT` predates this change and is imported by several tests; renaming it would touch files this card does not name. |
| F6 | P3 | adversarial | The plan and the work-session write-up both state that the identical module-scope `import yaml` in `plan_save_proof.py` is already enveloped by the `module()` loader's `BaseException` guard. That is true but unreachable in the missing-PyYAML case: `load()` refuses at `yaml_module()` long before any proof is loaded, so no test covers the claim. | Accepted as a recorded claim rather than a proven one. It is stated as reasoning for leaving that file alone, not as a tested property, and the file belongs to sibling card 998. |
| F7 | P3 | agent usability | The refusal names the package and its requirement specifier (`pyyaml>=6.0`, matching `pyproject.toml:14`) but no install command, so an agent must know its own package manager. | Accepted, and correct for an installed plugin: this tool is documented to run from an arbitrary checkout on an arbitrary machine, where naming `uv sync` would often be wrong. |

## Scores

| Dimension | Score | Note |
|---|---|---|
| Correctness | 10 | The defect was reproduced before and after in the real condition, across all three subcommands and `--help`; the one fall-through path, F2, still lands inside the envelope. |
| Security | 10 | No new input handling, no shell, no secrets. The `# nosec B506` justification is unchanged and still true: the loader is a `SafeLoader` subclass registering no object constructors. |
| Testing | 9 | Watched failing in the genuine condition before the fix and re-proven mechanically by the canary at `baseline_exit: 0`; F3 is the one untested permutation and it cannot differ. |
| Architecture and maintainability | 10 | F1 repaired. The deferral is documented at both new functions with the reason a future editor needs, including why the sentinel repair does not work, and the duplicated path literal was removed rather than added to. |
| Adversarial | 9 | The escape class is closed for the reported condition and for the unreported `--help` facet; F6 is an unproven adjacent claim, correctly left to the sibling card. |
| Application-programming-interface contract | 10 | No documented error code, exit code or JSON field changed; the closed code set in `tests/test_saga_spec_consumer_row.py` and the runbook table are both untouched, which was the deliberate decision. |
| Documentation clarity | 9 | The changelog names the code, the entry and the `--help` facet; two journal entries carry the mechanism and the rejected alternatives. F4 is a small widening of one published row's meaning. |
| Agent usability | 10 | The refusal is one JSON object with a machine-readable code, a distinguishing entry, the offending file and a remedy naming the package and its version floor. |

Derived overall 9.5; lowest applicable dimension 9. Both acceptance rules are satisfied, so the outcome is `accepted`.

## Residual risk

Nothing in this change alters behaviour on a machine that has PyYAML, which is every machine the test suite and continuous integration run on. The repaired path is therefore exercised only by the new guard, which is why that guard builds a real interpreter without PyYAML rather than stubbing the import — a stub proves the symptom and would keep passing against a module that exists and misbehaves.

The Saga version `0.159.2` is correct against `origin/main` as of this review, which is still at `9f1bae8a`. Sibling card 998 touches the same three release files, and the coordinator owns resolving a collision at merge time.
