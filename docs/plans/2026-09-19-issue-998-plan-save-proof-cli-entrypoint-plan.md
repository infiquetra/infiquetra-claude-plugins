---
title: Give plan_save_proof.py a command-line entrypoint that describes itself (issue 998)
type: fix
status: active
date: 2026-09-19
backend: inline
---

# Give plan_save_proof.py a command-line entrypoint that describes itself (issue 998)

## Summary

`plugins/saga/scripts/plan_save_proof.py` is a 507-line executable-shaped file with no
command-line entrypoint, so every direct invocation — `--help` included — exits 0 and prints
nothing at all.

This plan adds an entrypoint that prints what the file is and names the command that actually
runs it, exits 0 for `--help`, and refuses any other direct invocation at exit 2. It deliberately
does **not** make the proof runnable on its own.

## Problem Frame

The proof is the independent check that `plan_save_contract.py` runs before it validates or
writes Plan documentation. It used to be a pytest test; issue #926 turned it into a plain Python
file invoked by path, which is what made the missing entrypoint newly visible — an agent that
finds the file has no way to learn what it does or how it is meant to be called.

Reproduced in this worktree at base commit `30c36bb5`:

| Invocation | Observed |
|---|---|
| `python plugins/saga/scripts/plan_save_proof.py --help` | no output, exit 0 |
| the same file with no arguments | no output, exit 0 |
| the same file with `validate --root .` | no output, exit 0 |

The third row is the sharpest one. A caller who guesses at a subcommand gets silence and a
success code, so a mistyped invocation is indistinguishable from a passing run. Nothing in the
file rejects the arguments, because nothing in the file ever reads them.

This is finding `agentusab06` (severity P3, agent-usability lens, dimension
`discoverability-invocation-schemas`, scored 6.5 against a 7.0 floor) carried forward from the
issue #926 code review, cycle 6, whose outcome was `cycle_cap_best_available`. It is the last of
the three children of parent grouping issue #1005; siblings #996 and #997 merged earlier today as
Saga 0.159.1 and 0.159.2.

### What the siblings already settled, and what they left

Sibling #996 widened the loader in `plan_save_contract.py` to catch `BaseException` around both
seams where this proof's code runs. That is why an entrypoint added here cannot escape the
contract tool's JSON envelope even if it misfired. Parent issue #1005 recorded that fact as
reasoning; no test pins it for this file, and this plan adds one (R4).

Sibling #997 moved PyYAML out of module scope in `plan_save_contract.py` so that tool's `--help`
survives an interpreter without PyYAML. This proof still imports PyYAML at module scope
(`plan_save_proof.py:20`), which is invisible today because the file has no `--help` to break.
Adding one creates that surface, so R3 closes it in the same change.

## Requirements

**R1.** `python3 plugins/saga/scripts/plan_save_proof.py --help` prints usage that names what the
file is (the independent Plan documentation proof) and names the command that actually runs it
(`python3 plugins/saga/scripts/plan_save_contract.py --root <checkout> validate`), and exits 0.

**R2.** Every other direct invocation — no arguments, an unknown flag, or a guessed subcommand —
exits 2, writes usage text to standard error, and writes nothing at all to standard output. The
standard-error text is the entrypoint's own guidance for a bare invocation and argparse's usage
message for a malformed argument; both name the program, and requiring them to be byte-identical
would mean fighting argparse for no gain. The empty standard output is the load-bearing half: a
caller must never be able to mistake this file's output for the contract tool's JSON envelope.

**R2a.** The entrypoint reads `sys.argv` — it parses the real command line rather than ignoring
it. This is what gives U3's canary mutation teeth: the mutation makes the entrypoint fire while
`runpy` loads the file, and it only changes behavior if the arguments it then sees (the contract
tool's own) drive it to a `SystemExit`.

**R3.** R1 holds on an interpreter with no PyYAML installed at all.

**R4.** Loading this file the way `plan_save_contract.py` loads it — `runpy.run_path` — does not
execute the entrypoint. `plan_save_contract.py --root <clean checkout> validate` still prints
`{"outcome": "valid"}` and exits 0.

**R5.** One named guard covers R1 through R4, and a behavioral mutation registered in
`tools/canary_registry.json` proves the guard has teeth. This is not optional here: the inventory
assertion at `tests/test_saga_plugin.py:211-214` requires every test function in
`tests/test_saga_plan_contract_boundaries.py` to appear as a registry `guard`.

**R6.** The plugin release surfaces move together in the same pull request — Saga `0.159.3` in
`plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
`plugins/saga/CHANGELOG.md`, and the pinned version assertion at `tests/test_saga_plugin.py:49`.
Re-derive that number from `origin/main` at commit time rather than trusting it from this plan: a
sibling pull request taking the same version has silently auto-merged in this repository before.

## Key Technical Decisions

**KTD1 — the entrypoint describes and refuses; it does not run the proof standalone.**
`verify(api, contract, candidate)` needs the contract module's globals, a loaded contract and a
rendered candidate. Producing those means doing what `plan_save_contract.py main()` already does,
so a standalone runner would duplicate an existing command and add a dependency edge from the
proof back to the contract tool, reversing the one-way direction the two files have today. Worse,
it would bypass the tool-revision check at `plan_save_contract.py:496`, which exists so the
renderer that writes is the one that was verified — a second, weaker way to "verify" the
documentation is a liability, not a feature. Rejected alternatives: a standalone `--root` runner
(above); leaving the file alone on the grounds that 27 other scripts under
`plugins/saga/scripts/` also have no entrypoint (counted in this worktree — true, but they are
not invoked by path as this one is, and the card is tracked work with a named acceptance).

**KTD2 — a non-help direct invocation exits 2 with an empty standard output.** Exit 2 is
argparse's own usage-error code and the same refusal code the sibling contract tool uses, so a
caller reading exit codes across the pair sees one vocabulary. Silence on standard output is the
load-bearing half: the contract tool's callers parse standard output as JSON, and this file must
never emit anything they could parse. Rejected: exit 0 with guidance (that is the defect, with
prose added); exit 1 (the contract tool reserves 1 for drift).

**KTD3 — the `__main__` guard is inert under the loader because `runpy.run_path` names the module
`<run_path>`, and that is pinned by a test rather than assumed.** Probed directly in this worktree:
`runpy.run_path` on a file that records `__name__` reports `<run_path>`, not `__main__`, so an
`if __name__ == "__main__":` block cannot fire when `plan_save_contract.py` loads this file. The
reason to pin it anyway is that sibling #996's guard would *convert* a misfire into a clean-looking
refusal at exit 2 blaming the engine, so the failure would be invisible rather than loud. R4 is
therefore a positive test against a clean checkout, not a negative one.

**KTD4 — PyYAML moves to its point of use in this change, because `--help` is the surface this
card creates.** The module's only use of PyYAML is `yaml.safe_load` inside `SaveProbe.__call__`
(`plan_save_proof.py:478`); the import at line 20 is module scope, which is outside every handler
the file owns. The repository has recorded this same rule twice — LEARNINGS
`{#828-defer-module-scope-yaml-import-sdlc-manager}` ("defer domain-specific imports to their leaf
functions, so baseline entrypoints like `--help` run on minimal interpreters") and
`{#997-import-outside-every-handler}`, closed earlier today in the sibling file. This is not a
separate fix smuggled in: it is the condition under which R1 holds on the bare interpreter the
maintainer runbook (`plugins/saga/references/plan-save-contract.md:3`) tells maintainers to build.
Rejected: shipping the entrypoint over the module-scope import and filing the breakage separately
(it would ship a `--help` the repository's own recorded rule already calls broken).

**KTD5 — the guard lives in `tests/test_saga_plan_contract_boundaries.py`, and the narrower
explicit inventory list is left alone.** That file is where both siblings put their guards, and
membership there makes the canary registry entry mandatory by the assertion at
`tests/test_saga_plugin.py:211-214`. The separate hand-listed `for name in (...)` tuple at
`tests/test_saga_plugin.py:185` is not extended: sibling #997 did not extend it either, and the
registry assertion already covers the new guard without a second hand-maintained list.

## Implementation Units

Units land in order; U2 depends on U1 only for R3 to be provable, and U3 pins R1 through R4 in
one guard.

### U1. Import PyYAML at its point of use

Move the module-scope `import yaml` at `plan_save_proof.py:20` into the one place that uses it,
`SaveProbe.__call__`, so nothing outside a function body depends on PyYAML being installed. The
proof needs no import-time subclass of a PyYAML type, so the complication that forced sibling
#997 into a `yaml_module()` / `unique_loader()` pair does not arise here — this is a plain move.

**Files:** `plugins/saga/scripts/plan_save_proof.py`.

**Test expectation:** covered by U3's guard, requirement R3 — `--help` succeeds on an interpreter
built without PyYAML. The existing contract-tool tests must stay green, which proves the move did
not break the proof's actual verification path.

### U2. Add the self-describing entrypoint

Add an argparse-based entrypoint guarded by `if __name__ == "__main__":` at the end of the file.
Its description says what the file is and names the runnable command that executes it; `--help`
serves that text at exit 0, and any other direct invocation writes usage to standard error and
exits 2 with standard output empty. It parses the real command line (R2a). The module docstring
gains a matching line so the two do not drift, and the guard block carries a comment naming
`runpy.run_path` and the reason it cannot fire under the loader (KTD3).

**Files:** `plugins/saga/scripts/plan_save_proof.py`.

**Test expectation:** covered by U3's guard, requirements R1, R2 and R4.

### U3. Add the named guard and its behavioral mutation

Add `test_proof_cli_describes_itself_and_stays_inert_under_the_loader` to
`tests/test_saga_plan_contract_boundaries.py`, covering R1 through R4 in one function:
`--help` text and exit 0 (R1); a bare invocation and an unknown flag at exit 2 with empty standard
output (R2); `--help` under a throwaway virtual environment built without PyYAML, asserting that
absence first the way `test_contract_cli_envelopes_a_missing_pyyaml` does, before it proves
anything (R3); and `plan_save_contract.py validate` against a clean temporary checkout still
returning `outcome: valid` at exit 0 (R4).

Register the matching canary in `tools/canary_registry.json` under the id
`plan-save-contract-proof-cli`. **The `plan-save-contract-` prefix is load-bearing, not
cosmetic:** `tests/test_wiring_canary.py:40` selects the entries it executes with
`entry["id"].startswith("plan-save-contract-")`, so an id outside that prefix would satisfy the
membership assertion in `tests/test_saga_plugin.py` while never being run — a registered canary
whose teeth are never proven. The two existing entries that mutate this same proof file,
`plan-save-contract-proof-containment` and `plan-save-contract-proof-required`, already follow
the convention. Its `guard` reads
`tests/test_saga_plan_contract_boundaries.py::test_proof_cli_describes_itself_and_stays_inert_under_the_loader`
— the same spelling as the test function, verbatim. The mutation replaces the
`if __name__ == "__main__":` line with an unconditional one, so the entrypoint fires while
`runpy` loads the file during a contract `validate`, argparse sees the contract tool's own
arguments, and the resulting `SystemExit` becomes a refusal at exit 2. That turns R4 red, which is
what gives the guard teeth.

Watch the guard fail before it passes: run it against the unmodified file first and confirm the
`--help` assertion reports empty output, then again after U1 and U2.

**Files:** `tests/test_saga_plan_contract_boundaries.py`, `tools/canary_registry.json`.

**Test expectation:** this unit is the test. `uv run pytest tests/test_saga_plan_contract_boundaries.py tests/test_saga_plugin.py tests/test_wiring_canary.py tests/test_saga_spec_consumer_row.py -q` is green, and the canary reports `result: caught`.

### U4. Move the release surfaces and the journal together

Bump Saga to `0.159.3` across `plugins/saga/.claude-plugin/plugin.json`,
`.claude-plugin/marketplace.json` and `plugins/saga/CHANGELOG.md`, and update the pinned version
plus its explanatory comment at `tests/test_saga_plugin.py:49`. Add the dated LEARNINGS entry (a
file with no entrypoint reports success for every invocation, including a mistyped one) and the
DECISIONS entry for KTD1 and KTD2, in this same commit.

**Files:** `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
`plugins/saga/CHANGELOG.md`, `tests/test_saga_plugin.py`,
`docs/engineering-journal/LEARNINGS.md`, `docs/engineering-journal/DECISIONS.md`.

**Test expectation:** `uv run python scripts/check_release_surface_parity.py` reports all plugins
in parity, and `uv run python tools/release_surface_diff_guard.py --base-ref 30c36bb5` reports the
changed plugin bumped its release surfaces.

## Scope Boundaries

**Out of scope — true non-goals.**

- Making the proof runnable standalone (KTD1). The runnable command is
  `plan_save_contract.py --root <checkout> validate` and stays the only one.
- Any change to `plan_save_contract.py`. Its two envelope repairs merged today and this card does
  not touch them.
- Any new documented error code, exit code or JSON field. This file emits no JSON and gains none.
- Adding entrypoints to the other 27 files under `plugins/saga/scripts/` that have none. They are
  libraries imported by name, not invoked by path.

**Deferred to follow-up work.**

- Nothing. This card closes the last child of parent grouping issue #1005.

## Questions answered from the card

`AskUserQuestion` was unavailable in this session, so each question the skill would have asked was
answered from the card, the code, or the documented default, and recorded here.

| Question | Answer | Where the answer came from |
|---|---|---|
| Phase 0.4 — is a plan document warranted? | Yes | Five load-bearing decisions (KTD1 through KTD5), a mandatory canary registry entry and a release bump; not atomic in the skill's sense |
| Phase 0.5 — scope class | Lightweight | Three functional files, four units, no ambiguity left after grounding |
| Phase 5.1 — destination | `pr` | Applied from the `plan_pre_answers.v1` carrier supplied by the caller "improve-claude-plugins run driver"; validator exited 0 with no stop |
| Phase 5.1 — deploy autonomy | Not asked | The skill asks it only for `nonprod-deploy`; the destination is `pr` |
| Phase 5.2 — execution backend | `inline` | Applied from the same carrier. `lifecycle_state.recommend_execution_backend` was still called and returned `team-execution`; the divergence is recorded below and in the saga tick |
| Phase 5.2 KTD4 — gated or advisory consensus | Not asked | No consensus, multi-reviewer or many-attempt signal is present in this work, and the backend was already settled by the carrier |
| Phase 2 — does the entrypoint run the proof or describe it? | Describe and refuse | Answered from the code: `verify()` requires the contract module's globals, a loaded contract and a rendered candidate, none of which exist standalone (KTD1) |
| Phase 2 — exit code for a non-help direct invocation | 2, standard output empty | Answered from the sibling tool's documented refusal code and from the risk of emitting parseable output (KTD2) |
| Phase 2 — is the PyYAML move in scope? | Yes | Answered from two recorded repository rules, LEARNINGS `{#828-defer-module-scope-yaml-import-sdlc-manager}` and `{#997-import-outside-every-handler}` (KTD4) |

No question requiring operator authority arose. Nothing here touches production, destructive
operations, credentials, permissions, billing, external commitments or process authority.

## Recommended versus chosen backend

`recommend_execution_backend` was called with the shape of this work — three functional files,
four units, no security, infrastructure, cross-repository or deployment sensitivity, no consensus
signal, four release-surface files — and returned `team-execution` with the rationale "size/risk or
consensus signal -> review consensus + gates fit", driven by the unit count reaching the
four-phase threshold.

The chosen backend is `inline`, settled by the caller's carrier. The override is recorded rather
than hidden: the tick carries `--orchestration-recommended team-execution` beside
`--orchestration-mode inline`, which is the override-rate telemetry that flag exists for. The
recommendation is worth reading as a signal that four units is the ceiling for this card, not a
reason to escalate a three-file P3 fix to gated consensus.
