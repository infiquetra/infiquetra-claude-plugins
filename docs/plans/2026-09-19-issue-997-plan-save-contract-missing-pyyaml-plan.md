---
title: Keep a missing PyYAML inside the plan_save_contract JSON envelope (issue 997)
type: fix
status: active
date: 2026-09-19
backend: inline
---

# Keep a missing PyYAML inside the plan_save_contract JSON envelope (issue 997)

## Summary

`plugins/saga/scripts/plan_save_contract.py` imports PyYAML at module level (line 26). When
PyYAML is absent the tool dies with a raw traceback, empty standard output, and exit 1 — the
exit code it documents for *drift*, so a broken Python environment is indistinguishable from a
genuine documentation failure.

This plan defers the PyYAML import to the moment the tool actually parses YAML, so the failure
arrives as the documented refusal — one JSON object, exit 2 — and so `--help` keeps working
without PyYAML installed at all.

## Problem Frame

The tool's own docstring (`plan_save_contract.py:5`) promises: "Every invocation except --help
returns JSON: 0 success, 1 drift, 2 refusal." Three things break that promise when PyYAML is
missing, and only the first is named on the card.

Reproduced at base commit `9f1bae8a` in this worktree, with a stub `yaml.py` on `PYTHONPATH`
that raises `ImportError`:

| Invocation | Observed | Documented |
|---|---|---|
| `validate` | traceback on standard error, empty standard output, exit 1 | one JSON object, exit 0/1/2 |
| `render --check` | traceback on standard error, empty standard output, exit 1 | one JSON object, exit 0/1/2 |
| `--help` | traceback on standard error, empty standard output, exit 1 | usage text, exit 0 |

The card (issue #997, finding `adv10`, severity P3, adversarial lens) reports only the
`validate` row. The `--help` row is the same defect reaching the one invocation the docstring
explicitly exempts, and it is fixed by the same repair rather than by a separate one. This mirrors
what its sibling issue #996 turned up when it was repaired earlier today: that card also named one
seam, and reproducing it found a second.

Why this matters beyond tidiness: the maintainer runbook
(`plugins/saga/references/plan-save-contract.md:3`) tells maintainers to run this tool "offline
with Python 3.12+ and PyYAML", and `tests/test_saga_plan_contract_boundaries.py:248`
(`test_contract_cli_without_pytest`) already pins that the tool works in a bare interpreter
carrying PyYAML and nothing else. A maintainer who builds that environment and forgets PyYAML
gets exit 1 and reasonably concludes the documentation has drifted.

## Requirements

**R1.** With PyYAML absent, `validate`, `render --check` and `render --write` each print exactly
one JSON object on standard output and exit 2, with nothing on standard error.

**R2.** That refusal carries the repair instruction naming PyYAML, so the operator can act on it
without reading the source. Its fields are fixed here so the guard and the reviewer read the same
text: `code` is the existing `engine`, `entry` is the literal string `python dependency`, `file`
is the repo-relative `plugins/saga/scripts/plan_save_contract.py`, and `error` contains `PyYAML`.
No new documented error code is introduced (KTD2).

**R3.** With PyYAML absent, `--help` prints usage text and exits 0 — the one invocation the
docstring exempts from the JSON envelope.

**R4.** With PyYAML present, every existing behaviour is byte-identical: the `valid` / `clean` /
`drift` / `rendered` outcomes, every refusal `code`, `file` and `entry`, and the rendered
documents themselves. Proved by the existing suite over the three files that exercise this tool,
with no assertion changed:
`uv run pytest tests/test_saga_spec_consumer_row.py tests/test_saga_plan_contract_boundaries.py tests/test_saga_plan_save_and_routing.py -q`.

**R5.** A new guard in `tests/test_saga_plan_contract_boundaries.py` exercises R1, R2 and R3
through the real command-line boundary in an interpreter that genuinely lacks PyYAML — not a
monkeypatched import — and a matching behavioural mutation is registered in
`tools/canary_registry.json` so `tests/test_wiring_canary.py` proves the guard has teeth.

**R6.** The Saga plugin's release surfaces move together in the same pull request: the plugin
manifest, the marketplace entry and the changelog.

## Key Technical Decisions

**KTD1 — Defer the PyYAML import to first use inside `load()`, rather than guarding the
module-level import with a sentinel.** The module does not merely *call* PyYAML; it *subclasses*
it. `class UniqueLoader(yaml.SafeLoader)` at line 128 needs the real `yaml.SafeLoader` object at
class-creation time, so setting `yaml = None` in an `except ImportError` at line 26 moves the
crash three lines down into the class statement and fixes nothing. Deferring both the import and
the `UniqueLoader` class construction into the parsing path puts the failure inside `main()`'s
existing `try`, where the tool already knows how to answer, and leaves argparse — which runs
before any YAML is touched — free to serve `--help`. *Rejected:* a module-level sentinel plus a
lazily-built loader (two mechanisms where one suffices, and the sentinel is visible to the proof
through `SimpleNamespace(**globals())`); importing PyYAML inside `main()` before parsing (the
import site and the use site drift apart on the next edit); making PyYAML optional with a
hand-rolled YAML reader (a parser is not a thing to grow here).

**KTD2 — Report the missing dependency as the existing `code: engine` with a distinct `entry`,
not as a new documented code.** The documented error-code vocabulary is a closed set pinned by
`tests/test_saga_spec_consumer_row.py:405-412` against the table in
`plugins/saga/references/plan-save-contract.md:29-38`. `engine`'s published repair already reads
"Restore the named engine file and its dependencies", which is exactly this failure, and the
`entry` and `file` fields carry the discrimination a caller needs. Adding a `dependency` code
would widen a published contract and force every consumer that branches on codes to learn a new
branch, for a failure the operator repairs with one `uv sync`. *Rejected:* a new `dependency`
code (widens the published vocabulary; requires editing the runbook table, the closed-set guard
and the changelog for no caller-visible gain); reusing `syntax` via the top-level handler's
default conversion (the message would blame the YAML carrier for an interpreter fault).

**KTD3 — `main()`'s handler stays `except Exception`, unchanged.** `ImportError` is an ordinary
`Exception`, so once the import is deferred into `load()` the existing handler already converts
it. This plan touches no handler. Issue #996 recorded in DECISIONS
`{#996-envelope-seam-not-top-handler}` exactly why that handler must not be widened — argparse
raises `SystemExit(0)` for `--help` from inside it — and this repair is only correct if that
decision stands. *Rejected:* widening the handler (breaks `--help`, already ruled out for #996).

**KTD4 — Prove the guard in a real interpreter without PyYAML, reusing the existing virtual
environment harness.** `tests/test_saga_plan_contract_boundaries.py:248`
(`test_contract_cli_without_pytest`) already builds a throwaway virtual environment with
`venv.EnvBuilder(with_pip=False, symlinks=True)` and copies PyYAML into it. The new guard builds
the same environment and *omits* that copy, which is the honest reproduction of the operator's
broken machine. *Rejected:* a `PYTHONPATH` stub whose `yaml.py` raises (what the card's own
reproduction used, and what this plan used to reproduce — it proves the symptom but leaves the
guard passing against a module that exists and misbehaves rather than one that is absent);
monkeypatching `sys.modules` in-process (never reaches the command-line boundary the contract is
written about).

## Implementation Units

### U1. Defer the PyYAML import and the `UniqueLoader` class into the parsing path

Move `import yaml` out of the module preamble and build `UniqueLoader` where the contract is
actually parsed, so a missing PyYAML becomes an ordinary exception inside `main()`'s existing
`try` instead of a module-import crash.

**Files:** `plugins/saga/scripts/plan_save_contract.py`

**Approach:** the import and the loader class move together into the YAML-parsing path used by
`load()` (lines 148-158). The `# nosec B506` annotation on the `yaml.load(...)` call and its
justification move with it unchanged. The raised failure is a `ContractError` with
`code="engine"`, `entry="python dependency"`, `source="plugins/saga/scripts/plan_save_contract.py"`
(the repo-relative spelling `verify_saved_examples` already uses at line 458), and a message that
names PyYAML and the repair. A comment at the deferred import states why it is not at the top of
the file, in the same register as the comments issue #996 left at lines 115-118 and 530-533, so
the next editor does not "tidy" it back.

**Constraint:** `verify_saved_examples` hands the checkout's proof `SimpleNamespace(**globals())`
(line 473), so both `yaml` and `UniqueLoader` leave module globals when they move. Neither is read
by the proof — `plugins/saga/scripts/plan_save_proof.py:19` imports PyYAML itself and references
no `api.yaml` or `api.UniqueLoader` — and `UniqueLoader` has exactly two references in the whole
repository, both inside this script (lines 128 and 158). This unit must also not leave a
half-built or sentinel `yaml` name behind in globals for the proof to trip over. The proof's own
import is already enveloped, because `module()` loads that file under the `except BaseException`
guard at line 119.

**Test scenario:** covered by U2's guard; this unit also keeps
`tests/test_saga_spec_consumer_row.py` green, whose `contract_api` fixture executes this module
directly and calls `api.load(...)`.

**Test file:** `tests/test_saga_plan_contract_boundaries.py`, `tests/test_saga_spec_consumer_row.py`

### U2. Guard the envelope in an interpreter that genuinely lacks PyYAML

Add one test that builds a bare virtual environment without PyYAML and drives the real
command line through it, pinning all three documented outcomes.

**Files:** `tests/test_saga_plan_contract_boundaries.py`

**Test function name:** `test_contract_cli_envelopes_a_missing_pyyaml`. U3's registry `guard`
string must repeat this name character-for-character; if implementation picks a different name,
both places change together.

**Approach:** modelled on `test_contract_cli_without_pytest` at line 248 — same
`venv.EnvBuilder(with_pip=False, symlinks=True)`, same `tree(api, checkout)` fixture checkout,
same `-I` isolated invocation — but without the `shutil.copytree(Path(yaml.__file__).parent, ...)`
line. The test first asserts the environment really cannot import PyYAML, so it can never pass by
silently finding a system copy.

**Test scenario:**

1. `validate` → exit 2, standard error empty, standard output parses as one JSON object with
   `outcome: invalid`, `code: engine`, `entry: python dependency`, `file:
   plugins/saga/scripts/plan_save_contract.py`, and `error` containing `PyYAML`.
2. `render --check` → the same refusal. This is the row that matters most: exit 1 here is
   `drift`, and the whole point of the card is that the two were indistinguishable.
3. `render --write` → the same refusal, and neither owned document
   (`plugins/saga/skills/plan/SKILL.md`, `plugins/saga/references/saga-spec.md`) changed on disk.
4. `--help` → exit 0, usage text on standard output, standard error empty, and the output is not
   JSON.
5. The same checkout under the ordinary test interpreter (PyYAML present) still returns
   `outcome: valid` at exit 0, so the guard has not smuggled in a regression.

**Test file:** `tests/test_saga_plan_contract_boundaries.py`

**Watch it fail first:** run the new test against the unmodified script and record that it fails
on the traceback and exit 1, before U1 lands.

### U3. Register the behavioural mutation in the canary registry

The repository requires a behavioural mutation for every new guard in these test files;
`tests/test_wiring_canary.py::test_plan_contract_guards_have_teeth` executes every registry entry
whose `id` starts with `plan-save-contract-` and demands the verdict `caught`.

**Files:** `tools/canary_registry.json`

**Approach:** one new entry with `id: plan-save-contract-missing-pyyaml`, `guard` naming U2's test
by its full `path::name`, an `invariant` sentence, and a `replace_text` mutation that puts the
PyYAML import back at module scope — the exact regression this work prevents. The entry sits
beside `plan-save-contract-baseexception` (registry lines 285-296), which is the shape to copy.

**Guard-name rule:** the `guard` string must name U2's test function character-for-character as it
is defined in the test file. Verify by running `tests/test_wiring_canary.py` and confirming the
new entry reports `caught`, not by reading the two strings side by side.

**Test scenario:** `uv run pytest tests/test_wiring_canary.py -q` passes, and the new entry's
record is `caught`. Then hand-apply the mutation, confirm U2's test fails, and revert — the
registry proving itself is not a substitute for watching it.

**Test file:** `tests/test_wiring_canary.py`

### U4. Move the Saga release surfaces and record the decision

**Files:** `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
`plugins/saga/CHANGELOG.md`, `docs/engineering-journal/LEARNINGS.md`,
`docs/engineering-journal/DECISIONS.md`

**Approach:** Saga `0.159.1` → `0.159.2`. A defect repair with no interface change is a patch
bump; the documented error codes, exit codes and JSON shape are all unchanged by KTD2 and KTD3.
The changelog entry says what a missing PyYAML did and what it does now, including the `--help`
row the card does not mention. The journal gets one `LEARNINGS.md` entry (a module-level import is
outside every handler a tool has, and subclassing a dependency makes the sentinel repair
impossible) and one `DECISIONS.md` entry (KTD1 and KTD2 together, with their rejected
alternatives and a revisit-when condition).

**Sibling-collision watch:** issue #996 shipped `0.159.1` earlier today and issue #998 follows in
this same lane and touches the same plugin. If #998 merges first, re-derive the bump at merge
time rather than trusting the number chosen here — a same-version collision between sibling pull
requests has recurred in this repository often enough to be a known trap.

**Test expectation:** `scripts/check_release_surface_parity.py` reports parity, and
`tools/release_surface_diff_guard.py --base-ref 9f1bae8a` reports the changed plugin bumped.

## Scope Boundaries

**Out of scope (true non-goals):**

- Issue #998 (`plan_save_proof.py --help` exits 0 with no output). It is the third child of
  parent #1005, it follows in this same lane, and it has its own pull request.
- Any change to `main()`'s exception handler. KTD3 and DECISIONS
  `{#996-envelope-seam-not-top-handler}` both say it stays narrow.
- Any new documented error code, and any change to the exit-code protocol table in
  `plugins/saga/references/plan-save-contract.md`. KTD2 chose the existing vocabulary precisely so
  that table does not move.
- Deferring any other module-level import in this script. `yaml` is the only third-party import;
  everything else at lines 10-24 is the standard library, which is present whenever the
  interpreter is.
- The identical top-level `import yaml` in `plugins/saga/scripts/plan_save_proof.py:19`. It is
  already inside this tool's envelope: `module()` loads that file under the `except BaseException`
  guard at line 119, so a missing PyYAML there already becomes a `code: engine` refusal at exit 2.

**A note on the file list.** Parent grouping issue #1005 names only
`plugins/saga/scripts/plan_save_contract.py` and `plugins/saga/scripts/plan_save_proof.py` under
"Files expected to change". This plan also touches a test file, the canary registry, three
release-surface files and the journal. That is not scope creep: the repository's own `CLAUDE.md`
step 6 requires the release surfaces to move in the same pull request as any behaviour change, the
canary registry is required for every new guard in these test files, and the journal capture is
mandated for a non-obvious fix. Sibling pull request 1040 (issue #996) changed the same set.

**Deferred to follow-up work:**

- A repository-wide sweep for the same shape — a command-line tool whose third-party import sits
  outside every handler it owns — across the other Saga and fleet-core scripts. Worth a card of
  its own after this one lands, sized from the sweep rather than guessed at here.

## Questions answered from the card

`AskUserQuestion` is unavailable in this run, so every question the installed skill would have put
to the operator is answered below from the card, the code, or the documented default. None of
these is a production, destructive, credential, permission, billing, external-commitment or
process-authority decision.

| Skill phase | Question | Answer | Where the answer came from |
|---|---|---|---|
| 0.4 warranted-gate | Is a plan document warranted? | Yes | Not atomic: four units across a script, a test file, the canary registry and the release surfaces, plus two load-bearing decisions (KTD1, KTD2) that constrain the implementation. |
| 0.5 scope class | Lightweight, Standard or Deep? | Standard | One bounded defect with real technical decisions to document; four units, no optional analysis sections earned. |
| 5.1 destination | plan-only, pr, merge or nonprod-deploy? | `pr` | Applied by the `plan_pre_answers.v1` carrier from the caller `improve-claude-plugins run driver`; the validator exited 0 with no stop. Not asked. |
| 5.1 deploy autonomy | Gate or auto at the deploy edge? | Not asked | The skill asks this only when the destination is `nonprod-deploy`. |
| 5.2 execution backend | inline, team-execution or dynamic workflows? | `inline` | Applied by the same carrier. The recommender was still called: it returned `team-execution` on the size/risk trigger, so this plan records recommended `team-execution` against chosen `inline` — a visible override, not a silent one. |
| 5.2 KTD4 consensus | Gated or advisory consensus? | Not asked | The skill asks this only when a consensus, multi-reviewer or many-attempt signal is present. None is: this is a single-defect repair with no verdict to record. |
| 0.3 saga resume | Resume an existing saga or mint a new one? | Mint | `saga.py scan` returned zero candidates. |
| KTD2 | New error code or existing vocabulary? | Existing `code: engine` | The closed-set guard at `tests/test_saga_spec_consumer_row.py:405-412` and the published repair text in `plugins/saga/references/plan-save-contract.md:33`. |
| U4 | What version bump? | Patch, `0.159.1` → `0.159.2` | A defect repair with no interface change; the current version is in `plugins/saga/.claude-plugin/plugin.json`. |
