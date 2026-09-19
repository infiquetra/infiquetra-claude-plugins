# Work session — one staffing component in fleet-core, issue 1021

**What this built.** One data file and one resolver in the fleet-core plugin that answer "role or
work shape, and for review the lens, to vendor, model and effort", merging the four places that used
to hold that knowledge. Six implementation units, six commits, on branch `issue/1021` based on
commit `2044c363`.

## What was built, by unit

**U1 — the merged data file and the repointed loaders.** `staffing.json` absorbs `models.json` and
`tier_policy.json`, which are deleted. It carries the model palette, the effort vocabulary, the
scalar effort superset, the work-shape tier policy under a new `work_shapes` key, the execution
classes and the root orchestration profile, at schema version 3. Three path constants in two modules
move; the public Python surface does not, so the 61 files that reference the tier vocabulary stay
put. `load_policy()` reads the `work_shapes` block and fails loud when it is absent rather than
handing back the whole registry as if every key were a work shape.

**U2 — the resolver core.** `staffing.py` answers the work-shape question: the per-repository
overlay at `.saga/tier-defaults.json` first, then the shared policy, with the decision record naming
which layer answered. The command line prints the short `model/effort` pair the card asserts, with
`--json` for the whole record.

**U3 — the vendor palette as data.** The five module-level tables in `tier_resolver.py` become one
`vendors` block, and the resolver derives its runtime tables from it. The palette covers all seven
vendors the agent-launcher can start; `opencode` carries `runtime_supported: false` with its reason
in the data.

**U4 — capability ratings, trust tiers, roles and the explain view.** Four model families and
thirteen engine variants come across from the engine registry with their ratings, trust tiers,
cost-and-speed ranks and validation dates. Seven roles each name a work shape and a rated
capability. `explain --role` lists candidates strongest rating first, breaking ties on the cheaper
cost-and-speed rank.

**U5 — lens staffing and the qualification ledger.** A reviewing role can be asked for a lens, and
the answer carries the qualification status read from the software-development-lifecycle
repository's ledger through the environment-variable checkout ladder. Everything short of a full
match is the documented-policy outcome with its reason named, and an absent checkout never raises.

**U6 — the shim, the reference document and the release.** saga's `tier_defaults.py` delegates.
`references/staffing.md` supersedes `tier-palette.md` and `effort-convention.md`. fleet-core goes to
0.26.0 across the plugin manifest, the marketplace registry and the changelog together.

## Key decisions taken during execution

**The tier validation became one shared public function.** `write_tier_default` validated an
operator-confirmed override with its own copy of the check that the overlay reader used. Two copies
is how a write starts accepting a pair the read would refuse, so `staffing.validate_tier` is public
and both call it.

**The data schema version went to 3.** The document's shape changed materially — a new top-level
`work_shapes` key — so a consumer that validates the version should notice. The assertion in
`tests/test_fleet_core_execution_classes.py` moved with it.

**Two live saga reference documents also named the deleted data file** and were repointed:
`plugins/saga/skills/work/references/execution-strategy.md` and
`plugins/saga/references/sandbox-spawn-sites.md`. A test asserted the first one's wording.

## change_kinds

`behavior`, `api`

Behaviour, because the resolver is new code on a path every subagent spawn reads. Programming
interface, because `load_policy()` narrowed what it returns and `tier_defaults.py`'s internals
moved while its public functions did not. This list is what the hard test gate was applied to, and
the gate demands tests: `tests/test_staffing.py` is new with 59 cases, and the four existing suites
that read the deleted files were updated rather than deleted.

## Checks run

| Check | Result |
|---|---|
| `pytest tests/test_staffing.py` | 59 passed |
| `pytest` across the six affected suites | 119 passed |
| `ruff check` over `plugins/fleet-core`, `plugins/saga`, `tests/`, `scripts/` | clean |
| `ruff format --check` over the same | clean |
| `mypy plugins/ scripts/ tests/ --ignore-missing-imports` | clean, 356 files |
| `check_release_surface_parity.py` | all plugins in parity |
| `lint_journal_order.py` | no violations |
| The card's four acceptance criteria, run as commands | all four as asserted |

## Answers taken from the coordinator, with the source

Every choice the work and code-review skills would have asked was answered in advance by the
coordinator's stage-two message. Each is recorded here with the answer taken.

| Question | Answer | Source |
|---|---|---|
| Resume an existing saga or mint one | Resume `issue-1021` | coordinator |
| Branch | Stay on `issue/1021`; create no other | coordinator |
| Execution backend | `inline`, as the plan's frontmatter says; no other offered | coordinator, and the plan |
| Document-review gate | Passed, no blocking finding; no override needed or permitted | coordinator |
| Complexity triage | Large — the skill's documented sizing for a cross-cutting change above ten files | skill default |
| Execution strategy | Inline rather than subagents: units U2 through U5 all edit the same two files, so the parallel safety check fails on overlap and serial dispatch would re-read a growing file each time | skill default |
| Round-N detection | Fresh build; the saga carries no pull-request references | skill default |
| Front-loaded ship-ceremony start | Declined — no pull request in this stage | coordinator |
| Board moves | Submitted through the reconcile controller: Active/Implementing at the start of work | coordinator |
| Pull request, merge confirmation | None; the coordinator merges onto `parent/1018` by merge turn | coordinator |
| Continuation routing | Return to the coordinator | coordinator |
| Attribution lines in commits | None of any kind | coordinator, and the operator's standing rule |

## Two facts the coordinator supplied

The sibling software-development-lifecycle checkout was verified against its remote at the start of
this run — `main` equals `origin/main`, clean, at commit `67845cdd` — so the acceptance criteria and
the qualification ledger this work read are current. That closes the residual risk the document
review recorded.

The question of whether `.saga/tier-defaults.json` should be tracked stays open exactly as the plan
records it. `.gitignore` was not edited.

## One pre-existing condition, not caused by this work

`ruff format --check .` at the repository scope reports twelve markdown files it would reformat, and
every one of them is untouched by this branch and equally affected at the base commit `2044c363`.
The installed ruff is 0.16.5 against a `ruff>=0.4` dependency floor, and a newer ruff formats Python
code blocks inside markdown that an older one left alone. It is reported rather than fixed: the
files belong to other cards, and rewriting twelve unrelated documents to make a gate green is not
this card's to do.

## Next step

Code review of this branch against its base, then the full repository gate.
