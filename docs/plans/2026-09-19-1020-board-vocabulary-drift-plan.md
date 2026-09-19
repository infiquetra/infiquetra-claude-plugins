---
title: Fix the mission-control board vocabulary drift (issue #1020)
type: fix
status: active
date: 2026-09-19
origin: docs/analysis/2026-09-19-improve-claude-plugins-objective-plan.md
backend: inline
---

# Fix the mission-control board vocabulary drift (issue #1020)

## Summary

The mission-control plugin ships a cached snapshot of the three GitHub project boards,
`plugins/mission-control/config/board-schema.json`, that was last regenerated on 2026-07-14 and has
since fallen two board migrations behind. This plan regenerates that snapshot from the live boards,
rewrites the board reference document that admits its own staleness, adds an offline drift guard so
the same gap cannot reopen silently, and clears a third stale vocabulary label that is currently
making mission-control resolve a workflow the contract no longer defines.

## Problem Frame

Five facts, each verified against a current source during planning rather than carried from the
card.

**The cached snapshot is wrong, and the live boards are right.** Running the existing census script
against the live GitHub Projects API in this worktree
(`uv run python plugins/mission-control/scripts/board_census.py --check`) prints `FAIL
board-schema.json has drifted from the live board schema.` Reading the live field options directly
through `board_census.derive_census` shows that all three boards — Operations (project 3), Asgard
(project 2) and CAMPPS (project 4) — each carry a `Stage` single-select field with exactly the six
stages `Intake, Shaping, Planning, Active, Verify, Retro`, and a `Status` single-select field with
exactly the 26 stage-flow options. The committed snapshot carries none of that: it records no `Stage`
field on any board, gives Operations and Asgard the retired six-value ladder `Idea, Shaping, Ready,
Active, Verify, Done`, and gives CAMPPS an even older `Todo, In Progress, Done`.

**The declared contract is already current, so nothing needs deciding.** The vendored contract file
`plugins/mission-control/config/sdlc-schema.json` (schema version `2026-09-07.5`) points all three
boards at the `stage_flow` workflow and lists the same six stages and same 26 statuses the live
boards carry. The standing decision `{#board-vocabulary-schema-is-truth-584}` says that when a live
board and that contract file disagree, the contract wins and the board is migrated. They do not
disagree. This work therefore touches only a derived cache and a prose document; no board is
migrated and no operator decision is needed.

**The drift is wider than the status vocabulary: whole fields have come and gone.** Diffing the live
field names against the committed ones shows the cache is behind on field membership too. Operations
gained `Stage` and lost `Risk` and `Work Type`. Asgard gained `Stage` and `Priority` and lost `Jeff
Needed`, `Mode`, `Risk`, `Target Repository` and `Transfer Target`. CAMPPS gained `Stage` and
`Priority` and lost `Initiative`, `Start`, `Target` and `Test Strategy`. None of this is alarming —
`sdlc-schema.json` declares exactly four board fields (`Stage`, `Status`, `Objective`, `Priority`)
for all three boards, so `Risk` and the rest now live in the issue body rather than on the board —
but it means the regenerated file will be a large diff, not a narrow one.

**A third vocabulary source is stale, and it is the copy that ships.** The plugin's own
`plugins/mission-control/config/project-mappings.json` labels Operations and Asgard with `"workflow":
"intent_flow"` (lines 11 and 20) and CAMPPS with `"workflow": "campps_initiative"` (line 29).
`sdlc-schema.json` no longer contains an `intent_flow` workflow at all — its `workflows` block holds
only `stage_flow` and the retired-historical `campps_initiative`. `_project_workflow_name`
(`sdlc_manager.py:417-426`) prefers the project mapping's label over the board's own declared
workflow, so the stale label decides the vocabulary.

**This does not misbehave on the planning machine, and that is the trap.**
`_resolve_project_mappings` (`sdlc_manager.py:305-317`) tries an external override at
`$INFIQUETRA_SDLC_PATH/config/project-mappings.json` before the vendored copy, and
`get_sdlc_path()` resolves to the sibling checkout `/Users/jefcox/workspace/infiquetra/infiquetra-sdlc`
whose copy is current. Resolution there returns `stage_flow` for all three boards and a correct
26-entry status order, so nothing looks wrong here. Where that checkout is absent — a fresh plugin
install, a continuous-integration runner, another operator's machine — the vendored copy is served
instead. Driving `_project_workflow_name` and `_status_order` with the vendored mappings shows what
those environments get: Operations and Asgard collapse to a one-entry status order, `['No Status']`,
and CAMPPS resolves to the retired `Idea, Committed, In Progress, Done, Parked` ladder. This is a
latent shipping defect rather than a live one, which is precisely why it has survived: the machine
that would notice it is the one machine configured not to.

**The prose reference is stale in a way the drift guard cannot catch.**
`plugins/mission-control/skills/board/references/kanban-workflow.md` still documents the retired
`Idea -> Shaping -> Ready -> Active -> Verify -> Done` ladder for Operations and Asgard, and says so
about itself in the CAMPPS section (lines 52-55: "The Operations and Asgard section above still
shows the retired `intent_flow` names; correcting them is tracked as a separate change and is not
done here"). Issue #1020 is that separate change. The same document also carries a "WIP Limits"
section that documents a policy the contract file retired outright.

## Requirements

**R1.** `plugins/mission-control/config/board-schema.json` records, for each of Operations, Asgard
and CAMPPS, a `Stage` field whose six option names are the same set as `workflows.stage_flow.stages`
and a `Status` field whose 26 option names are the same set as `workflows.stage_flow.statuses`, both
as declared in `sdlc-schema.json`, and is produced by running the existing census script rather than
by hand. Exact counts, so that the implementer and the reviewer reach the same verdict from this
sentence alone; same set and not same sequence, because the census sorts options by name while the
schema lists them in lifecycle order.

**R2.** The census file exposes its fields keyed by field name, so that
`jq -r '.boards.operations.fields.Status.options[].name'` and `jq -r '.boards.campps.fields |
keys[]'` — the two executable checks issue #1020 states — return what the card says they return.

**R3.** `grep -n "retired" plugins/mission-control/skills/board/references/kanban-workflow.md`
returns nothing, and the document describes the live stage-flow vocabulary for all three boards. The
same correction is applied to `plugins/mission-control/skills/board/SKILL.md`, which carries a
duplicate of the same stale table and the same staleness admission; no board-facing surface is left
describing a vocabulary the boards do not have.

**R4.** The retired work-in-progress-limit policy is removed from the board reference and from every
live instruction that still tells an agent to enforce it, rather than being restated in stage-flow
terms. In the same pass, every terminal-status and cycle-time boundary table across the board and
metrics skills stops naming `Done` or `In Progress`, neither of which is an option on any live board.
U4 names each line.

**R5.** `plugins/mission-control/config/project-mappings.json` no longer overrides the workflow each
board declares for itself, so `sdlc_manager._status_order` driven from the vendored mappings alone —
with no `infiquetra-sdlc` checkout in the resolution path — returns the 26 stage-flow statuses for
all three boards. Today it returns `['No Status']` for Operations and Asgard, whose label names an
`intent_flow` workflow the schema no longer defines, and the five-status retired ladder for CAMPPS,
whose label names `campps_initiative` — a workflow the schema does still define, marked
`retired_historical` with `"active_routing": false`. Two different wrong answers, one cause.

**R6.** A test at `tests/test_board_schema_drift.py` fails when the committed census disagrees with
the declared contract in `sdlc-schema.json`. It runs with no network access and no GitHub
credentials, so it gives signal on every continuous-integration run.

**R7.** The same test file carries an opt-in leg that compares the committed census against the live
boards, skipped by default and enabled by setting the environment variable `BOARD_SCHEMA_LIVE` to
`1`. The name is fixed here so it is a contract rather than an implementer's invention.

**R8.** The existing census drift check (`board_census.py --check`), the existing census tests
(`plugins/mission-control/tests/test_board_census.py`) and the existing stale-phrase guard
(`plugins/mission-control/tests/test_prompt_alignment.py`) all still pass.

**R9.** The mission-control release surfaces tell the same story as the diff: `plugin.json`,
`.claude-plugin/marketplace.json` and the plugin `CHANGELOG.md` all carry the new version.

**R10.** The engineering journal records the decision behind R2 and the findings behind R4 and R5,
in the commit that ships them.

## Key Technical Decisions

**KTD1 — key the census `fields` by field name instead of listing them.** The census currently emits
`fields` as a sorted list of objects — assembled at `board_census.py:79-92`, returned at `:94-99` —
so the card's two `jq` acceptance
checks cannot pass as written; they index `fields` as a mapping. Change the writer to emit a mapping
from field name to field record. The diff stability the sorted list was chosen for is preserved,
because the writer already serializes with `sort_keys=True`.

> **Corrected during implementation, 2026-09-19.** This section originally claimed the blast radius
> was "exactly two files", on the strength of a repository-wide search for the strings `board-schema`
> and `board_schema`. That was wrong. The search finds files that name the *artifact*; it cannot find
> a consumer that imports the *producing function* and never mentions the file.
> `plugins/mission-control/config/generated/check_issue_contract_parity.py` does exactly that, and
> consumed `fields` positionally at line 158. The real consumer set is four files — the census script,
> its test, that parity gate, and the parity gate's test. All four are updated, and the fix is
> verified against the live boards rather than only against fixtures. See LEARNINGS
> `{#1020-blast-radius-search-the-producer}`.

*Rejected: keep the list and treat the card's `jq` checks as approximate.* They are executable
criteria the operator wrote, and a mapping is also the shape a consumer of this file actually wants
— issue #1028 makes saga's automatic board moves read it.

**KTD2 — a duplicate field name is a hard error, not a silent overwrite.** A mapping keyed by name
can lose a field that a list cannot, so the writer raises rather than dropping one. It will not fire
during U2: counting field names across the three live boards during planning found 16 fields on each
and no duplicate anywhere, so the regeneration cannot trip it.

**KTD3 — the new drift guard compares the census to the contract file, not to the live boards.** The
existing live comparison (`board_census.py --check`) already exists, is wired into continuous
integration and into `scripts/gate.sh`, and deliberately reports SKIPPED and exits 0 when no
project-scoped credential is available — which is every normal continuous-integration run, per
`{#board-census-shape-only-live-skip-424}`. That is precisely how this drift sat unnoticed for two
months. The new test closes the gap by asserting an invariant that needs no network: every `Status`
option in the committed census is one of the 26 statuses `sdlc-schema.json` declares, and every
board carries a `Stage` field whose options are the six declared stages.

*Rejected: make the live check blocking.* It would fail on credential absence rather than on drift,
and the decision not to do that is already recorded and still holds.

**KTD4 — the work-in-progress limits in the board reference are deleted, not translated.** Decision
E6 in `sdlc-schema.json`'s migration notes removed the `wip_limits` block outright and retired the
checking script. The code already says so in two places: `sdlc_manager.py:1227-1228` reads "WIP limits are
retired (#999): the schema defines none, so columns report a plain count without limit decoration",
and `:1409` reads "Show WIP counts per status (limits are retired; the schema defines none)".
Rewriting the table into stage-flow terms would reinstate a policy the contract deleted.

**KTD5 — the two legitimate mentions of the closed Mount Olympus board are reworded to "closed and
archived".** Issue #1020's third acceptance check is a bare `grep -n "retired"` over the board
reference. Besides the self-admitted staleness sentence, the word appears twice about the former
project 1, correctly. Rewording those two sentences satisfies the check as literally written and
loses no meaning; narrowing the check instead would weaken a criterion the operator set. The phrase
"Mount Olympus is retired historical context" that `test_prompt_alignment.py` requires lives in
`sdlc-schema.json`, not in this document, so the guard is unaffected.

**KTD6 — the stale workflow labels in `project-mappings.json` are fixed here, although the card does
not list that file.** The card's "Files expected to change" is a list of expectations; its
"Out-of-scope" section names only `sdlc-schema.json` and the set of moves saga may submit, neither of
which this touches. The defect is the same drift the card is named for, it is three deleted keys, and
leaving it would ship a "vocabulary drift fixed" claim while the copy of the mappings that actually
ships still names a workflow the contract deleted — a false green of exactly the kind the
repository's validation rule warns about. It is called out here, rather than folded in quietly, so
plan review and the operator can cut it if they would rather it were its own card.

The defect is latent, not live, and the plan says so in the problem frame rather than overstating it:
on a machine with an `infiquetra-sdlc` checkout the override masks it completely. That is an argument
for fixing it, not against — a defect only reachable by other people's machines is the kind that
survives longest.

*Rejected: file a separate card.* Defensible, and it costs a round trip on a three-key change whose
evidence is already gathered and whose fix is the fall-through branch the function already has.

## Implementation Units

### U1. Key the census fields by name

Change `fetch_project_fields_census` in `plugins/mission-control/scripts/board_census.py` to build
`fields` as a name-keyed mapping, raising on a duplicate name (KTD1, KTD2). The per-field record and
the sorted option list are otherwise unchanged. Update the module docstring's description of the
census shape.

**Depends on:** nothing.

**Files:** `plugins/mission-control/scripts/board_census.py`,
`plugins/mission-control/tests/test_board_census.py`.

**Test scenarios** (`plugins/mission-control/tests/test_board_census.py`): a census derived from a
mocked two-field project exposes `fields` as a mapping whose keys are the field names; a field with
no options still appears with no `options` key; two fields sharing a name raise rather than
overwriting; the existing drift, missing-file and unreachable-API cases still behave as they did.

Two existing tests break under a mapping and must be rewritten, not merely re-run:

- `test_returns_sorted_field_and_option_shape` (`plugins/mission-control/tests/test_board_census.py:36-61`)
  breaks in two ways. At `:58-59` it builds `names = [f["name"] for f in census["fields"]]` and asserts
  `names == sorted(names)`; under a mapping this becomes a key-set assertion. At `:60-61` it does
  `next(f for f in census["fields"] if f["name"] == "Status")` — iterating a name-keyed dict yields
  strings, so `f["name"]` raises `TypeError`; index the mapping directly instead. Note the sort property
  genuinely weakens: the file on disk stays ordered because `cmd_write` serializes with `sort_keys=True`
  (`board_census.py:139`), but an in-memory dict does not guarantee it, so assert on `sorted(fields)` or
  on the serialized text, never on dict iteration order.
- `test_over_thirty_fields_returns_full_census_not_truncated` (`:63-97`) asserts
  `census["fields"][0]["name"] == "Field_00"` and `[-1]["name"] == "Field_44"`. Integer indexing raises
  `KeyError` on a name-keyed dict. Replace with `len(fields) == 45` plus membership of the first and
  last names — the property under test is that pagination returned all 45, and that survives the shape
  change intact.

Four `--check` fixtures build list-shaped `fields` values and move to the mapping: the census literals
at `:189`, `:205`, `:210` and `:247` (the `schema_path` anchor lines sit just above three of them, at
`:188`, `:203` and `:246`). The fixture in `test_check_skips_not_passes_when_live_unavailable` around
`:231` is `{"boards": {}}` with no `fields` value at all and needs no change.

No other test in the file breaks: both pagination tests raise before the mapping is built, and
`test_derive_census_covers_every_tracked_project` (`:172`) stubs `fetch_project_fields_census`
outright. The mocked GraphQL response helper `_fields_response` at `:23` takes the API's own list
shape and does not change; only what the census returns does.

**One interaction to get right.** The runaway-pagination test at `:99` feeds 30 fields that all share
the name `X`. That is a duplicate-name input, so KTD2's raise must stay where the mapping is built —
after `paginate_or_raise` has already raised `PaginationExhaustedError` — and must not be hoisted
into the page loop. Hoisting it would turn that test's expected pagination error into a duplicate-name
error and silently retire the truncation guard `{#board-pagination-truncation-confirmed-live-424}`
was written to protect.

### U2. Regenerate the census from the live boards

Run `uv run python plugins/mission-control/scripts/board_census.py --write` against the live boards
and commit the resulting `plugins/mission-control/config/board-schema.json`. Read the diff before
committing. It is a large diff, and the expected content is known in advance: a `Stage` field added
to all three boards; `Priority` added to Asgard and CAMPPS; the Operations, Asgard and CAMPPS
`Status` options all replaced by the same 26 stage-flow options; and these field removals — `Risk`
and `Work Type` from Operations, `Jeff Needed`, `Mode`, `Risk`, `Target Repository` and `Transfer
Target` from Asgard, and `Initiative`, `Start`, `Target` and `Test Strategy` from CAMPPS. Anything
outside that list is unexpected and belongs in the pull request description.

This unit needs a GitHub token carrying the `project` scope. The session that planned this work has
one, and `--check` reached the live API from this worktree.

**Depends on:** U1 (regenerating before the shape change would mean regenerating twice).

**Files:** `plugins/mission-control/config/board-schema.json`.

**Test expectation:** none — this unit regenerates a derived artifact; U3 is the assertion about its
content.

### U3. Add the offline drift guard

Add `tests/test_board_schema_drift.py` at the repository root. That path is the card's choice — issue
#1020 names it in an executable acceptance check — and it is consistent with `CLAUDE.md`'s "Unit tests
for all CLI-based plugins (in `tests/` at repo root)", but it is not the observed local practice:
mission-control's 34 existing `test_*.py` files all sit in `plugins/mission-control/tests/`. Follow
the card.
The file loads the committed census and the committed `sdlc-schema.json`, asserts the invariants in
KTD3, and carries an opt-in live leg.

**Depends on:** U2 (the assertions describe the regenerated file).

**Files:** `tests/test_board_schema_drift.py`.

**Test scenarios** (`tests/test_board_schema_drift.py`): every board named in `sdlc-schema.json`'s
`boards` block is present in the census; each carries a `Status` field whose option names are the
same **set** as `workflows.stage_flow.statuses`; each carries a `Stage` field whose option names are
the same **set** as `workflows.stage_flow.stages`; no board's `Status` options contain any of `Idea`,
`Ready`, `Active`, `Done`, `Todo`; `fields` is a mapping for every board; and a live leg, skipped
unless `BOARD_SCHEMA_LIVE` is set to `1`, that derives a fresh census and compares it to the
committed one.

**Compare as sets, not as ordered sequences.** The census sorts options alphabetically
(`board_census.py:86-90`), so a correct regenerated census records `Stage` as `Active, Intake,
Planning, Retro, Shaping, Verify`, while `stage_flow.stages` lists them in lifecycle order —
`Intake, Shaping, Planning, Active, Verify, Retro`. An ordered equality assertion goes red against a
perfectly correct file, and the failure reads like drift, which is the worst possible way to be
wrong here.

**Compare option names by exact equality, never by substring.** Three live statuses — `Ready for
Active`, `Ready for Planning`, `Ready to merge` — contain the retired name `Ready`, and the `Stage`
field legitimately has an option called `Active`. A substring check would fail against a correct
census.

**Key the boards through `board_key`.** Census keys come from the project names in
`project-mappings.json`; `sdlc-schema.json` keys its `boards` block by board key, and
`_project_board_key` (`sdlc_manager.py:408-414`) shows the two can diverge. They coincide today only
because each mapping sets `board_key` explicitly, so the test should cross-walk through it rather
than assuming the names match.

**Prove the guard before trusting it.** The second, third, fourth and fifth assertions must be
observed failing against the pre-U2 census, not merely asserted to — the fifth included, because
`jq '.boards.operations.fields | type'` on the committed census returns `array`, so the
"`fields` is a mapping" assertion is red before U1 and U2 land. (The first — board presence — already
passes today, since the committed census carries exactly `asgard`, `campps` and `operations`.) Write
the test, run it against the census as it stood at the branch base, confirm those four fail, then
run it against the regenerated census and confirm all pass. A guard that has only ever been seen
green is not known to guard anything, which is the exact failure mode KTD3 exists to correct.

### U4. Rewrite the board reference onto stage flow

Rewrite `plugins/mission-control/skills/board/references/kanban-workflow.md`:

Replace the "Operations And Asgard" workflow section with the shared stage-flow ladder and the
per-stage status table, transcribed from `sdlc-schema.json`'s `workflows.stage_flow` block — which
is what the CAMPPS section already does — and fold the three sections into one shared workflow
section, since `canonical_for` names all three boards. Delete the sentence admitting the section is
stale. Delete the "WIP Limits" section (KTD4). Restate the standup review order in stage terms for
all three boards. Correct the "Common Scenarios" steps that name `Idea` and `Ready`. Reword the two
Mount Olympus sentences per KTD5.

The word "retired" appears exactly three times in the document today — lines 21 and 86 about Mount
Olympus, and line 54's staleness admission. The rewritten prose must not reintroduce it: describe
the superseded vocabularies as "superseded" or "no longer in use", not as "retired", or the card's
third acceptance check fails on the new text.

Two further blocks in the same document are stale and are easy to miss, so they are named rather than
left to the rewrite. The "Metrics Boundaries" table at lines 159-166 gives `Operations / Asgard |
Active | Done` at line 165, and `Done` is an option on no live board — restate both rows in
stage-flow terms, with `Ready to close` as the terminal for all three boards. The "Asgard modes"
table at lines 43-49 documents the `Mode` board field, which the live Asgard board no longer carries
(it is among the five fields U2 removes from the Asgard census) — delete it, and say in the changelog
entry that Asgard modes are no longer a board field.

`plugins/mission-control/skills/board/SKILL.md` carries the same defect as the reference document and
must be fixed in the same pass. Its workflow table at lines 37-41 gives Operations and Asgard the
retired `Idea -> Shaping -> Ready -> Active -> Verify -> Done` ladder, and lines 47-48 carry the same
self-admitted staleness sentence as the reference ("still show the retired `intent_flow` ladder names;
correcting them is tracked as a separate change and is not done here"). Issue #1020 is that separate
change for this file too. Restate all three rows on `stage_flow` and delete the admission. Line 43's
"retired-historical" description of Mount Olympus is fine to keep, since R3's grep covers only the
reference document — but rewording it to "closed and archived" for consistency with KTD5 costs
nothing.

Correct the pointer lines that advertise the deleted work-in-progress section, and the live
instructions that still tell an agent to enforce the retired policy. `board/SKILL.md:144-148` is
already correct ("WIP limits are retired (#999)") and must not be touched. The five that must change:

- `plugins/mission-control/skills/board/SKILL.md:175` — pointer line naming "WIP limits".
- `plugins/mission-control/skills/metrics/SKILL.md:152` — the same pointer line.
- `plugins/mission-control/skills/metrics/SKILL.md:133` — "Check whether WIP limits are being
  respected."
- `plugins/mission-control/skills/metrics/SKILL.md:138` — "Check whether active statuses are at or
  over WIP."
- `plugins/mission-control/skills/metrics/references/metrics-targets.md:92` — "Check WIP limits."

**The terminal-status tables are the same defect in four more places.** `Done` is the terminal status
in every one of them and is an option on no live board; `In Progress` likewise. All four restate on
`Ready to close` as the terminal for all three boards, matching the disposition given above for the
"Metrics Boundaries" table:

- `plugins/mission-control/skills/board/SKILL.md:122` — "For Operations and Asgard that means
  `Done`." (Line 123 already handles CAMPPS correctly with `Ready to close`.)
- `plugins/mission-control/skills/metrics/SKILL.md:45-47` — cycle-time boundary table, `Operations |
  Active | Done`, `Asgard | Active | Done`, `CAMPPS | In Progress | Done`.
- `plugins/mission-control/skills/metrics/references/metrics-targets.md:16-18` — the same table.
- `plugins/mission-control/skills/metrics/references/metrics-targets.md:48-50` — "Counted terminal
  statuses", `Done` for all three boards.

The `Mount Olympus` legacy rows immediately below two of those tables are correct history and stay.

Two more lines in those files name the retired status `Ready`, which R3's grep cannot catch because
it scans only the board reference: `skills/metrics/SKILL.md:140` and `metrics-targets.md:94`. Restate
both in stage-flow terms. `metrics-targets.md:72-74` is the same problem in a denser form and moves
with them: it defines active work as `In Progress` for CAMPPS, then "For intent-flow boards, active
work is `Active` plus `Verify`. `Ready` and `Shaping` are wait or preparation states". `In Progress` is on no live board,
`intent_flow` is the workflow the schema deleted, and the whole passage should be restated against
the `Active` stage.

**Depends on:** nothing.

**Files:** `plugins/mission-control/skills/board/references/kanban-workflow.md`,
`plugins/mission-control/skills/board/SKILL.md`,
`plugins/mission-control/skills/metrics/SKILL.md`,
`plugins/mission-control/skills/metrics/references/metrics-targets.md`.

**Completeness check for this unit.** Sweeping the plugin's prose surfaces during planning
(`grep -rn "Idea ->\|-> Ready ->" plugins/mission-control/skills/ plugins/mission-control/agents/
plugins/mission-control/commands/ plugins/mission-control/README.md`) found the retired ladder in
exactly two files, both named above: `skills/board/SKILL.md:39-40` and
`skills/board/references/kanban-workflow.md:31,36,118`. The one other hit,
`kanban-workflow.md:85`, is the Mount Olympus legacy ladder and is correct history. Re-run that
sweep after the edits and expect no hit outside line 85.

**Test expectation:** the existing stale-phrase guard
`plugins/mission-control/tests/test_prompt_alignment.py` covers this document and must still pass;
the card's `grep -n "retired"` check over the document must return nothing. No new test — this is a
prose surface with an existing guard.

### U5. Drop the stale workflow labels from the project mappings

Delete the three `"workflow"` keys from `plugins/mission-control/config/project-mappings.json` (lines
11, 20 and 29), so `_project_workflow_name` falls through to the board's declared workflow in
`sdlc-schema.json`, which is `stage_flow` for all three boards (KTD6). Do not replace them with
`"workflow": "stage_flow"`: duplicating the declaration is how this file went stale in the first
place.

**Depends on:** nothing.

**Files:** `plugins/mission-control/config/project-mappings.json`.

**Test scenarios** (`plugins/mission-control/tests/test_project_mappings_resolution.py`, which
already owns this resolution order): driving `_project_workflow_name` with the **vendored** mappings
and the committed contract file returns `stage_flow` for each of `operations`, `asgard` and `campps`;
`_status_order` on the same input returns an order containing `Capturing` and `Ready to close` and
none of `Idea`, `Ready`, `Done`, `Committed` or `Parked`; and an explicit `"workflow"` key in a
mapping still wins over the board declaration, so the precedence branch itself is not removed, only
the stale data that used it.

These tests must read the vendored file rather than `load_config()`. `load_config()` prefers the
external `infiquetra-sdlc` checkout when one is present, which on the planning machine masks the
defect entirely — a test written against it would pass before the fix and prove nothing.

### U6. Release surfaces and journal

Bump `plugins/mission-control/.claude-plugin/plugin.json` from 2.16.0 to 2.17.0, run
`uv run python scripts/sync_marketplace.py` so `.claude-plugin/marketplace.json` matches, and add a
2.17.0 entry to `plugins/mission-control/CHANGELOG.md` describing the regenerated census, the
name-keyed shape, the new guard, the reference rewrite and the project-mapping fix.

Add a `DECISIONS.md` entry for KTD1 (why the census is keyed by name, with the two-file blast-radius
evidence and the rejected alternative) and two `LEARNINGS.md` entries: the mechanism behind KTD3 — a
drift check that skips on a missing credential reports success on every run that cannot check, so a
credential-free invariant has to sit beside it — and the mechanism behind U5, which is the sharper
one: a config file that duplicates a name the schema owns can outlive the name, a lookup that prefers
the duplicate then resolves to nothing rather than failing, and a resolution order that tries a
developer's local checkout first will hide the whole thing from the only person able to notice it.
The generalizable rule: when a loader has a precedence ladder, test the rung that ships, not the rung
your machine happens to land on.

**Depends on:** U1, U2, U3, U4, U5.

**Files:** `plugins/mission-control/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
`plugins/mission-control/CHANGELOG.md`, `docs/engineering-journal/DECISIONS.md`,
`docs/engineering-journal/LEARNINGS.md`.

**Test expectation:** none — release metadata and journal prose; `scripts/check_release_surface_parity.py`
and `scripts/sync_marketplace.py --check` in the gate are the assertions.

## Scope Boundaries

**Out of scope, permanently.**

- No change to `plugins/mission-control/config/sdlc-schema.json`. It is current at schema version
  `2026-09-07.5` and the live boards match it.
- No board migration and no change to any live board. The boards are correct; the cache was not.
- No change to which lifecycle moves saga may submit, and no change to the constrained
  lifecycle-field mutation surface.
- No change to the live-gated `board_census.py --check` posture in `.github/workflows/ci.yml` or
  `scripts/gate.sh`. It stays advisory and credential-gated.
- No change to the `infiquetra-sdlc` repository. Its `config/project-mappings.json` is the external
  override in the resolution ladder, it is already current, and it is a different repository
  entirely. U5 touches only this repository's vendored copy.
- No change to the precedence order in `_resolve_project_mappings`. The override-then-vendored ladder
  is deliberate; U5 fixes the data the ladder serves, not the ladder.

**Deferred to follow-up work.**

- Making saga submit board moves automatically at each boundary is issue #1028 (recommendation R19
  in the simplification review). It depends on this card and is not part of it.
- The one-off board hygiene pass — the 31 cards whose GitHub issue is closed but whose board status
  has not caught up — is recommendation R20 and a separate card.

## Verification

```bash
jq -r '.boards.operations.fields.Status.options[].name' plugins/mission-control/config/board-schema.json
jq -r '.boards.campps.fields | keys[]' plugins/mission-control/config/board-schema.json
grep -n "retired" plugins/mission-control/skills/board/references/kanban-workflow.md
uv run pytest tests/test_board_schema_drift.py -q
uv run pytest plugins/mission-control/tests/test_board_census.py \
  plugins/mission-control/tests/test_prompt_alignment.py \
  plugins/mission-control/tests/test_project_mappings_resolution.py -q

# U5 proof: drive the resolver from the VENDORED mappings, not load_config(), which
# would consult the external infiquetra-sdlc checkout and mask the defect.
# Before U5 this prints ['No Status'] for operations and asgard; after, the 26 statuses.
python3 - <<'PY'
import sys, json
sys.path.insert(0, "plugins/mission-control/scripts")
import sdlc_manager as sm
cfg = sm.load_config()
vendored = json.load(open("plugins/mission-control/config/project-mappings.json"))
for name, proj in vendored["projects"].items():
    print(name, sm._project_workflow_name(cfg.get("sdlc_schema", {}), name, proj),
          len(sm._status_order(cfg, name, proj)))
PY
GATE_LOG_DIR=/tmp/gate-1020 bash scripts/gate.sh > /tmp/gate-1020.log 2>&1 &
```

The full gate is backgrounded because it exceeds the ten-minute foreground tool timeout; read
`/tmp/gate-1020/result.txt` for the verdict once it exists.

## Risks

**The implementing session may lack a project-scoped GitHub token**, which blocks U2 — `--write`
cannot reach the live boards and the census cannot be regenerated. The planning session's token
carries the `project` scope and reached the API, so this is a property of where the work runs, not
of the work. If it fires, stop and say so rather than hand-editing the census: a hand-written census
is exactly the failure this card exists to repair.

**The regenerated census carries churn beyond the stage migration** — eleven fields removed and four
added across the three boards, listed in U2. This is not a risk of the unknown so much as a risk of a
reviewer seeing a large diff and reading only its top. U2 names the expected content in advance so
the review is a comparison rather than an inspection.

**U5 changes runtime behavior in environments without an `infiquetra-sdlc` checkout, and the card
does not list the file it touches.** Mitigated by naming
it in KTD6 rather than folding it in quietly, by pinning it with tests in the file that already owns
that resolution order, and by keeping it a separate unit that can be dropped without disturbing the
other five.

**U5's tests could be written so they pass before the fix.** If they go through `load_config()` they
will read the external `infiquetra-sdlc` checkout, which is already correct, and prove nothing. U5
says to drive the resolver from the vendored file directly, and the proving command in the
verification section shows the before-and-after values to expect.

## Questions answered from the card

Issue #1020 was planned without an operator present. Every question the planning skill would
normally put to the operator is recorded below with the answer taken and where it came from. No
answer was invented in any of the categories that require an operator — production, destructive
change, credentials, permissions, billing, external commitments, process authority, or a
plan-review override.

| Question | Answer taken | Source |
|---|---|---|
| Destination — plan only, pull request, merge, or non-production deploy? | Pull request | A structured pre-answer carrier (schema `plan_pre_answers.v1`) supplied by the caller "improve-claude-plugins run driver", validated by `plan_pre_answers.py`, which applied it with no stop. |
| Execution backend — inline, team execution, or dynamic workflows? | Inline | The same carrier, applied by the same validator. Recorded as an override: `lifecycle_state.py recommend-backend` with this plan's shape (nine functional files, six units) recommended `team-execution` on its size signal. The carrier's `inline` stands, and the divergence is recorded in the saga tick as recommended-versus-chosen. |
| Resume an existing saga, or mint a new one? | Mint a new one | `saga.py scan` returned zero candidates. |
| Is a plan document warranted, or is the work atomic? | Warranted | The work spans a script change, a regenerated artifact, a new test, a prose rewrite and a release bump, and carries the six key technical decisions above. |
| Scope class — lightweight, standard, or deep? | Standard | Six units, one load-bearing shape decision, no cross-repository or strategic surface. |
| Grounding turned up a latent defect in the vendored `project-mappings.json` that the card does not name. Fix it here, or file a separate card? | Fix it here, as its own unit | KTD6. It is the same drift the card is named for and it is three deleted keys. Surfaced rather than folded in, so it can be cut. |
| The vendored mappings look fine when exercised through `load_config()`. Is the defect real? | Real, but latent | `load_config()` prefers an external `infiquetra-sdlc` checkout, which exists on the planning machine and is current. Driving the resolver from the vendored file directly reproduces it: `['No Status']` for Operations and Asgard, the retired ladder for CAMPPS. An earlier draft of this plan called it a live defect; that was wrong and is corrected in the problem frame. |
| The live boards have dropped fields the cache still records (`Risk`, `Mode`, `Test Strategy` and eight others). Is that a problem to fix? | No — record it and move on | `sdlc-schema.json` declares exactly four board fields (`Stage`, `Status`, `Objective`, `Priority`); the dropped ones moved into the issue body. The census records what is live, so the removals are the correct result, not a regression. |
| The card's `jq` acceptance checks assume a field mapping; the census writes a list. Change the shape, or narrow the check? | Change the shape | KTD1. The checks are executable criteria the operator wrote. Narrowing an operator's criterion to fit the code is weakening the card. (The blast radius was estimated at two files here and turned out to be four — see the correction under KTD1.) |
| The card's `grep "retired"` check would also catch two correct sentences about the closed Mount Olympus board. Reword them, or narrow the check? | Reword them | KTD5. Zero meaning lost, and the check passes as written. |
| The board reference documents work-in-progress limits. Restate them in stage terms, or delete them? | Delete them | KTD4. `sdlc-schema.json`'s decision E6 removed the `wip_limits` block and retired the checking script; `sdlc_manager.py` already reports that no limits exist. |
| Where does the new test live — repository root `tests/`, or the plugin's own `plugins/mission-control/tests/`? | Repository root `tests/test_board_schema_drift.py` | The card names that path in an executable criterion, and it is the convention the repository's `CLAUDE.md` states. |
| Should the card be moved on the Operations board when planning starts and when the plan is ready? | No move submitted | The coordinator running this stage holds the board read-only for the planning stage and will make the moves itself. This is a deliberate, recorded departure from the planning skill's board-move steps, not an omission. |

## Deviations from the installed skill

The planning skill submits two board moves, at the start of planning (`Stage` = Planning, `Status` =
Designing) and after the plan is written (`Stage` = Planning, `Status` = Ready for Active). Neither
was submitted: the run coordinator scoped the Operations board read-only for this stage and owns
those moves. The board was queried, never written.
