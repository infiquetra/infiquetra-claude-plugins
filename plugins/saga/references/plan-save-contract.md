# Maintaining Plan's documentation contract

Edit `plan-save-contract.yaml`, then run these commands from the target checkout's development
environment (PyYAML and pytest are required):

```bash
python3 plugins/saga/scripts/plan_save_contract.py validate
python3 plugins/saga/scripts/plan_save_contract.py render --check
python3 plugins/saga/scripts/plan_save_contract.py render --write
uv run pytest tests/test_saga_spec_consumer_row.py tests/test_saga_plan_contract_boundaries.py tests/test_saga_plan_save_and_routing.py tests/test_tier_resolver.py -q
```

An installed tool must select the checkout with `--root /absolute/path/to/checkout` before
its subcommand. This selects the YAML, engine code and documents together. Review the diff.
`--help` prints help; other calls return one JSON object with an absolute `root`:

| Exit | Outcome | Meaning |
|---|---|---|
| 0 | `valid`, `clean`, `rendered` | Input validated, output already current, or output written. |
| 1 | `drift` | `changed` contains relative paths; `diff` contains proposed changes. |
| 2 | `invalid` | Nothing should be retried until the reported failure is corrected. |

Refusals include `code`, `file` (a path relative to `root`, an absolute path, or null for
argument errors), `entry`, and `error` with the repair instruction. Codes are:

| Code | Repair |
|---|---|
| `usage` | Correct arguments using `--help`. |
| `schema_family` | Select a Plan save carrier. |
| `schema_version` | Match the tool and carrier revisions; the error reports observed and expected versions. |
| `invalid_contract` | Correct the named structured entry or document boundary. |
| `engine` | Restore the named engine file and its dependencies. |
| `filesystem` | Restore file access; follow retained-backup instructions if rollback failed. |
| `syntax` | Restore valid, readable input and inspect the reported parser failure. |
| `verification` | Correct the saved-example failure or restore the checkout's test dependencies; run its matching tool. |

There is no automatic v1/v2 migration: restore the carrier and tool from the same revision.
v3 placeholders are literal data: remove v2's shell quoting rather than relabeling the schema.
All three operations run `test_plan_examples_save_the_intended_tick` against the target
checkout before reporting success or writing. That test executes every example in temporary
directories and checks the entire saved snapshot. The tool must match the checkout's copy.
`render --check` also checks document boundaries and output drift. Text placeholders are raw scalar values;
the renderer supplies shell quoting. Replace enum placeholders with one listed choice.

Add an example as a unique `templates` entry containing `id` and `fixed`, a mapping of declared
fields to enum choices. A fixed conditional value requires a compatible condition. Examples
fixing `orchestration_mode: cc-workflows-ultracode` render in the workflow group; others render
in the default group. No new markers are needed. Render, run the tests above, and inspect the diff.
Get `--orchestration-recommended` from the `recommended` JSON member of this command, with the
actual work shape; `--orchestration-mode` records the operator's choice:

```bash
python3 plugins/saga/scripts/lifecycle_state.py recommend-backend --file-count 2 --phase-count 1
```

For a merge conflict, resolve the entire conflict, including all Git conflict delimiters.
Preserve surrounding prose, one ordered pair of each generated marker, and one `/plan` row;
then render and run the tests above. Do not repair only the text between generated markers.
Writes stage both documents and roll back earlier replacements on a later write failure;
a failed rollback reports retained backups. Restore those files before retrying. Git is the
recovery path for an interrupted process; concurrent editors and crash-atomic batches are unsupported.
