# Maintaining Plan's documentation contract

The YAML lists Plan's save fields, conditions, examples and effort mechanisms. The loader
checks options and enum placeholders against `saga.py`, checks the save flags named by
Plan's upstream instructions, and exercises `effort_rider.inject_effort`. Tests also execute
examples and inspect saved ticks: accepting a real option does not establish that it is the
right Plan field. Neither the renderer nor its output supplies that behavioral oracle.

From the target checkout, using its Python environment with PyYAML:

```bash
python3 plugins/saga/scripts/plan_save_contract.py validate
python3 plugins/saga/scripts/plan_save_contract.py render --check
python3 plugins/saga/scripts/plan_save_contract.py render --write
uv run pytest tests/test_saga_spec_consumer_row.py tests/test_saga_plan_save_and_routing.py tests/test_tier_resolver.py -q
```

A cached/installed copy must use `--root /absolute/path/to/checkout` **before** the command.
That selects the code, YAML and both documents together; there is no foreign `--contract`
input that can overwrite another checkout's documents. Review the diff before committing.
`--help` prints human-readable help. Every other invocation prints one JSON object:

| Exit | Outcome | Meaning and next action |
|---|---|---|
| 0 | `valid`, `clean`, or `rendered` | Validation succeeded, no drift, or requested updates completed. |
| 1 | `drift` | `changed` lists paths and `diff` shows the proposed edits; run `render --write`. |
| 2 | `invalid` | `error` names the file/entry or operation; correct it before retrying. |

`validate` checks the carrier and code bindings. `render --check` additionally checks generated
regions and reports documentation drift. A schema mismatch refuses the whole carrier; align
tool and YAML revisions. v2 removes v1's free-form factual notes, configurable operator-choice
rule and per-template `omit` list. Restore both files from the same revision when migrating an
old checkout; do not merely relabel its schema.

To add an example, append a unique `templates` entry with `id` and `fixed` (a mapping of
declared fields to real enum values), then render and run the checks above. Examples fixing
`orchestration_mode: cc-workflows-ultracode` go into the workflow group; all others go into
the default group. No marker surgery is needed. There is no `omit`: every conditional flag
is emitted either in the command, as a conditional addition, or excluded because a fixed
value makes its condition false. Quote text placeholders containing spaces or `#` as shell
values; enum placeholders must list exactly the current `saga.py` choices in parser order.
Examples containing placeholders require substitution before execution. Obtain the recommended
backend from the JSON `recommended` member of this runnable call, supplying the actual work shape:

```bash
python3 plugins/saga/scripts/lifecycle_state.py recommend-backend --file-count 2 --phase-count 1
```

Use that member as `--orchestration-recommended`; keep the operator's confirmed choice as
`--orchestration-mode`. `orchestration_operator_choice` derives only from an explicitly passed
mode flag unless an explicit choice is supplied; with neither flag, preserve the prior choice
or start empty. A choice that differs from the effective mode **requires** a nonempty
`--orchestration-downgrade` rationale or `saga.py save` refuses it. This is an engine-stored
field, not another flag required in every Plan template. The row lists Plan's payload; identity
(`kind`, `id`) and git provenance (`branch`, `head_sha`, `last_commit_sha`) are also stored by
the save operation. `decisions` is the KTD mirror in the tick's `## Decisions` section.

Generated content has one term: **generated region**. Its inventory is:

| Document | Generated region | Source and owner |
|---|---|---|
| Plan SKILL.md | `PLAN SAVE EXAMPLES: default`, `PLAN SAVE EXAMPLES: workflow`, `EFFORT HONORING NOTE` | This YAML and `plan_save_contract.py`; P5. |
| saga-spec.md §11 | The single `/plan` consumer row | This YAML and `plan_save_contract.py`; P5. |
| Plan SKILL.md | Existing `GENERATED TIER TABLE` table | `tier_policy.json` and `plugins/fleet-core/scripts/fleet_commons/render_tier_table.py`; fleet-core. |

Do not edit generated content to resolve a conflict. Resolve YAML conflicts, restore exactly
one ordered pair of each marker (and exactly one `/plan` row) from the common Git revision,
and rerender. Leave other consumer rows and surrounding prose intact. For an intentionally
new generated region, update the renderer and its tests together; adding an example is not
such a change. The named checks live in `tests/test_saga_spec_consumer_row.py`; their packaging
inventory lives in `tests/test_saga_plugin.py`, and their mutation canaries in
`tools/canary_registry.json`.

Writes stage both documents before replacing either and restore earlier replacements if a
later replacement fails. A rollback failure names retained backup files for manual restoration.
Fix filesystem access, restore those paths, and rerun `render --check` before retrying. This is
a solo maintainer tool: do not run concurrent editors/renderers against these same regions.
It does not promise an atomic multi-file commit across a machine crash; Git remains recovery
for an interrupted run. It never changes Saga runtime behavior to make documentation pass.

The 0.156.0 entry remains unreleased. Its existing date is the integrator's release-heading
convention, not the date of this repair; the integrator owns any version or heading change.
