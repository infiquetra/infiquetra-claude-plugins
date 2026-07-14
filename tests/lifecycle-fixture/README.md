# Lifecycle regression fixture repo (#428)

A minimal but real git repository plus the canonical lifecycle scenario definitions the
end-to-end regression harness runs. Nothing in the fleet's other checks *executes* the
lifecycle machinery against a repo; this fixture closes that gap: each scenario drives the
production saga CLIs headlessly against a throwaway clone of this fixture and asserts on the
**artifact shape** the run left behind.

## Layout

```
tests/lifecycle-fixture/
├── README.md          # this file
├── seed/              # the fixture repo's seed content (copied into every throwaway clone)
│   ├── README.md
│   └── fixture_app.py
├── scenarios/         # one JSON file per canonical scenario (3-5 files, enforced by test)
│   ├── spec-plan-work.json      # the happy path — asserts ALL FOUR artifact-shape families
│   ├── code-review-gate.json
│   ├── outcome-round-trip.json
│   └── worktree-reclaim.json
└── .git/              # materialized on demand (see "Repo-ness"), never committed
```

The engine lives in `tests/lifecycle_harness.py`; the pytest surface is
`tests/test_lifecycle_regression_harness.py`; the scheduled CI job is
`.github/workflows/lifecycle-regression.yml` (cron, separate from the PR-blocking `ci.yml`).

## Repo-ness (why `.git` is not committed)

Git cannot track a nested `.git` directory, so the fixture's own repository is **materialized
on demand** by `lifecycle_harness.ensure_fixture_repo()` (git init, deterministic identity,
remote `https://fixture.invalid/lifecycle-fixture.git` — deliberately distinct from any real
remote). A nested `.git` is hardcoded-invisible to the parent repo's `git status --porcelain`,
so materialization never dirties the parent tree; `test_fixture_repo_is_a_real_isolated_git_repo`
pins both facts.

Scenario runs never execute against this in-tree directory: every run gets a **fresh throwaway
clone** (`lifecycle_harness.make_workdir`) built from `seed/` in a pytest tmpdir — the
`wiring_canary` throwaway-checkout pattern — so runs are independently attributable and the
parent working tree is never touched.

## Scenario file conventions

A scenario is one strict JSON object. **Parsing is fail-closed**: an unknown top-level key,
an unknown step/assertion `kind`, an unknown key on a step/assertion, or an `id` that does not
match the file stem is a hard error — never silently ignored.

```json
{
  "id": "<must equal the file stem>",
  "title": "one line",
  "description": "what the scenario drives and what it asserts",
  "steps": [ ... ],
  "assertions": [ ... ]
}
```

### Step kinds (each drives a production code path)

| kind | keys | what it does |
| --- | --- | --- |
| `write_file` | `path`, exactly one of `text`/`json` | seed a file in the clone (relative, traversal-free paths only) |
| `run_saga_cli` | `script`, `args` | run a production CLI (`saga`, `execution_spec`, `outcome` — allowlisted) with the clone as cwd; non-zero exit is a scenario error |
| `git` | `args` | run git in the clone (seeded diffs, branches) |
| `worktree_open` | `outcome_id`, `subplot_id` | production `outcome_worktrees.ensure_worktree` + real `git_worktree_ops` |
| `worktree_reclaim` | `outcome_id`, `subplot_id` | production `outcome_worktrees.reap_worktree` |

### Assertion kinds and their artifact-shape families

| kind | family | violation phrase on failure |
| --- | --- | --- |
| `execution_spec_valid` | `spec-json-valid` | `spec JSON missing` / `spec JSON failed validation` |
| `outcome_spec_valid` | `spec-json-valid` | `spec JSON missing` / `spec JSON failed validation` |
| `saga_log_appended` | `saga-log-append` | `saga log missing entry` |
| `gate_record_present` | `gate-record` | `gate record missing` |
| `worktree_reclaimed` | `worktree-reclaimed` | `worktree still present` |
| `outcome_state` | `outcome-derived-state` (non-canonical) | `outcome derived state mismatch` |

Violations are **named** (R4): the failure string carries the phrase above plus the concrete
artifact (path, saga id, worktree path), never a bare exit code. An assertion that cannot
determine the state it is asked about (git unreadable, the production reader disagreeing with
the on-disk tick files) raises a harness error instead of passing.

## Adding a new scenario

1. Create `scenarios/<new-id>.json` with `"id": "<new-id>"` following the conventions above.
   The runner's parametrization is glob-driven, so the new file is collected automatically —
   no test-code change needed.
2. Keep the canonical count between 3 and 5 (`test_definition_count_is_canonical` enforces it);
   growing past 5 means retiring or merging a scenario deliberately, not silently.
3. Do **not** put the substring `scenario` in the file stem, and do not add new test functions
   whose names contain it: the issue's acceptance check counts collected node lines matching
   `scenario`, and `test_collected_names_match_fixture_definitions` pins that invariant.
4. Every "passed" verdict needs its baseline control: if the new scenario introduces a new
   assertion kind, add a `test_seeded_failure_*` case proving a deliberately broken run fails
   with the named violation. A green that cannot go red is vacuous.
5. Run it: `uv run pytest tests/test_lifecycle_regression_harness.py -v` (add `-rP` to see the
   happy path's per-family printout).

## What this harness does NOT claim

It asserts the artifact shapes the canonical scenarios produce on a healthy run and that the
named violations fire on seeded-bad runs. It does not replace the structural/unit suites, does
not exercise team-execution's consensus machinery, does not measure timing, and does not gate
merges — the scheduled workflow is a detection instrument (R5).
