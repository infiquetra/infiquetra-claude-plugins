---
title: house-style — ship the output-style plugin and its two subagent reach levers
type: feat
status: active
date: 2026-08-08
origin: docs/brainstorms/2026-08-07-output-styles-requirements.md
---

# house-style — ship the output-style plugin and its two subagent reach levers

Tracking issue: infiquetra/infiquetra-claude-plugins#704.

## Summary

Ship `house-style`, a new plugin in this repository carrying one Claude Code output style, and deliver
the same presentation contract to subagents through two levers of repository-owned code: a rider
appended by saga's workflow-script emitter, and a preamble duplicated into the 36 agent definition
files under `plugins/*/agents/*.md`.

The work is gated on an experiment. Neither lever has been observed working, and the plan's first unit
proves both before any of the rest runs.

**Reading this plan: two numbering schemes are in play.** `R1`–`R14` below are *this plan's*
requirements. The requirements document at `docs/brainstorms/2026-08-07-output-styles-requirements.md`
has its own `R1`–`R36`, which this plan always cites as "requirements-document R26" and never as a bare
`R26`.

## Problem Frame

Two measured facts drive the work, both re-derived from `docs/measurements/2026-08-07-baseline.json`
rather than carried across document hops.

**Output does not answer the operator's actual question.** The two dominant prompt modes are
approval-or-continuation and status-check, which are the same question — *is this waiting on me?* Across
35 days only **2.70%** of sessions end on a line that answers it. All ten responses that drew a
satisfied reply ended with a single concrete ask; five of nine traced complaints ended on a trailing
aside. Placement discriminates; length and formatting do not.

**A style reaches less than half the output.** Claude Code's documentation is explicit: "Output styles
apply to the main conversation only: a subagent runs its own system prompt, so styles don't change how
subagents respond." Measured, **57.02%** of assistant output is generated inside subagents. The two
levers in this plan reach **45.7%** of that subagent output and no more.

## Grounding

Everything below was verified against the repository or the current documentation during planning, not
assumed. Where a fact contradicts the requirements document, the plan says so.

| Fact | Source | Result |
| --- | --- | --- |
| A plugin can ship an output style | `code.claude.com/docs/en/output-styles` | Confirmed: "Plugins can also ship output styles in an `output-styles/` directory" |
| Where the directory goes | plugins reference, plugin-structure section | `output-styles/` at **plugin root**, never inside `.claude-plugin/` |
| Whether `plugin.json` needs a key | plugins reference field table | No. `outputStyles` only *overrides* the default location |
| `keep-coding-instructions` default | output-styles frontmatter table | `false` — so requirements-document R28 is real and load-bearing |
| `force-for-plugin` exists | output-styles frontmatter table | Real, plugin-styles only; this plan does not use it |
| Style changes need a reload | plugins reference, live-change-detection | `output-styles/` changes need `/reload-plugins` or a restart; only `SKILL.md` is live |
| How the style is selected | output-styles doc | `/config`, or the `outputStyle` setting. The `/output-style` command was **removed in v2.1.91** |
| Agent definition files | `ls plugins/*/agents/*.md` | Exactly **36**, across 9 plugins, 25 of them in `team-execution` |
| The emitter's prompt funnel | `plugins/saga/scripts/execution_spec.py:3244` | `_agent_prompt(spec, unit)` — the single site, already the home of `BUDGET_RIDER` |
| Marketplace state | `.claude-plugin/marketplace.json` | 11 plugins, metadata version `3.0.0`; each entry duplicates the plugin's `version` |
| Existing drift guards | `tests/` | `test_release_surface_parity.py`, `test_agent_registration_drift.py` |

**One correction the plan carries.** The requirements document's Actors section says a style governs
only the main thread. The documentation adds an exception it does not mention: *"A fork is the
exception, because it inherits the parent's full system prompt."* No `attributionAgent` value in the
census names a fork, so no reach credit is claimed for it — the effect is unmeasured, and stays that
way rather than being folded into a number.

## Requirements

- R1. The experiment proving both levers runs **first** and blocks everything else. A failure stops the
  run and reopens the requirements document's R27 blocker; it is reported, never worked around.
- R2. `plugins/house-style/` ships a plugin with an `output-styles/` directory at its root, registered
  in `.claude-plugin/marketplace.json`, with `plugin.json` and `marketplace.json` versions in step.
- R3. The style file declares `keep-coding-instructions: true` explicitly, because the default is
  `false` and silently drops Claude Code's built-in engineering guidance.
- R4. The style file carries a placard section naming what it suppresses and what replaces it.
- R5. The style emits a distinctive literal string containing no box-drawing characters, so the active
  style is confirmable by grep rather than by impression.
- R6. Tests assert R3, R4, and R5, so none can be lost to an edit.
- R7. The presentation preamble is authored **once** as a single canonical file, and both levers consume
  that one file rather than carrying independent copies of the text.
- R8. Saga's emitter appends the preamble to every emitted `agent()` prompt, through the existing
  single funnel `_agent_prompt()`, following the `BUDGET_RIDER` precedent.
- R9. The preamble is duplicated into all 36 agent definition files, and a test asserts every copy is
  byte-identical to the canonical file.
- R10. The scorer gains a visual-gating measurement and a relay-quality measurement, each with a
  pre-style value obtained by re-running the scorer over the archived window to a **new** output path.
- R11. `docs/measurements/2026-08-07-baseline.json` is byte-identical to its committed state at the end
  of the run. Any unit that would write to it stops instead.
- R12. No artifact produced by this work claims subagent reach above **45.7%**.
- R13. `~/.claude/CLAUDE.md` gains the reach annotation on its Communication section, and all seven
  Plain English rules are unchanged.
- R14. The full local gate passes: `ruff check`, `ruff format --check`, `mypy`, `bandit`, and
  `pytest --cov=plugins`.

## Key Technical Decisions

**KTD1 — The experiment is a plan unit, not a pre-flight check.** Both levers are inference from
repository structure and transcript fields. The requirements document already lost one 44-percentage-point
claim to an unverified inference about the same subsystem, so the experiment gets a unit with its own
evidence artifact and a hard stop rather than a checkbox someone can tick from reasoning. *Rejected:*
proving the levers as part of the units that use them, which hides a failed premise inside a unit that
reports success on its own terms.

**KTD2 — The preamble is one file, consumed twice; it is not written twice.** Both levers need the same
text. Authoring it once at `plugins/house-style/references/subagent-presentation-preamble.md` and having
the emitter read it and the 36 agent files copy it makes the byte-identity test meaningful — the test
compares copies against a canonical source rather than against each other. *Rejected:* a constant
embedded in `execution_spec.py` with the agent files copying from that, which buries the product's text
inside saga's implementation and makes the plugin the derived artifact rather than the source.

**KTD3 — The emitter stamp goes in `_agent_prompt()` and nowhere else.** Grounding found exactly one
funnel: `execution_spec.py:3244`, called from three sites (2241, 3215, 3953), already the home of
`BUDGET_RIDER` and the fan-out reconciliation rider. A new module-level `PRESENTATION_RIDER` appended
there inherits the existing pattern and the existing tests' shape. *Rejected:* stamping at each of
`_emit_thunk` / `_emit_parallel_wave` / `_emit_verify_panel`, which is three edits where one will do and
three places for a future path to be added without the stamp.

**KTD4 — Verify panels are deliberately not stamped by the emitter.** Saga spawns every verify agent as
`saga:readonly-verifier`, which has a definition file and is therefore already covered by the R9 lever.
Stamping them from the emitter as well would double-apply the preamble to the same agents while adding
nothing to reach. The census's disjointness by `attributionAgent` is what makes this safe to reason
about.

**KTD5 — The 43.64% written by hand stays uncovered in this plan.** Route (c) — the style instructing
the main thread to stamp each `agent()` prompt it authors — is the only route to the largest block of
subagent output, and the requirements document reopened it as a live option. It is **out of scope
here** and recorded as follow-up work, because it changes what the style file asks of the main thread
and should be decided after the two mechanical levers are proven, not bundled with them. Naming it as
deferred is the point; absorbing it silently is the failure mode this whole document exists to avoid.

**KTD6 — Release surfaces land in one unit at the end.** The preamble duplication touches 9 plugins, so
9 `plugin.json` versions, 9 `CHANGELOG.md` files, and 11 `marketplace.json` entries move. Spreading
that across units puts several agents in `marketplace.json` at once, which the emitter halts on and no
backend can make safe. *Rejected:* each unit bumping its own surfaces.

## Implementation Units

Nine units. U1 gates everything; U9 closes everything.

### U1. Prove both levers by experiment

Create a throwaway agent definition carrying a distinctive marker, spawn that agent type, and check
whether the marker reaches its output. Then add a throwaway rider in `_agent_prompt()`, emit a workflow
script, run one unit through it, and check the same way. Record both results — including the exact spawn
invocation and the raw output excerpt — in `docs/evidence/issue-704/lever-experiment.md`.

**Blocking behaviour:** if either marker fails to appear, stop the run, write the finding, and reopen
the requirements document's R27 blocker. Do not adapt the plan around a lever that does not work.

**Files:** `docs/evidence/issue-704/lever-experiment.md`; throwaway files removed before the unit ends.

**Test expectation:** the evidence document is the artifact. No repository test — the experiment
observes runtime behaviour that no unit test can reach.

**Depends on:** nothing.

### U2. Scaffold the plugin and its release surfaces

Create `plugins/house-style/.claude-plugin/plugin.json` (name `house-style`, version `0.1.0`, at most
10 keywords per the repository's cap), `README.md`, and `CHANGELOG.md`. Do **not** add an `outputStyles`
key — grounding confirmed the default `output-styles/` location is auto-discovered and the key exists
only to override it. Do not create the style file; U3 owns it.

**Files:** `plugins/house-style/.claude-plugin/plugin.json`, `plugins/house-style/README.md`,
`plugins/house-style/CHANGELOG.md`.

**Test scenarios** (`tests/test_house_style_contract.py`): `plugin.json` parses; required fields present;
keyword count ≤ 10; no `outputStyles` key.

**Depends on:** U1.

### U3. Author the style file and the canonical preamble

The judgment unit — this is the product. Write `output-styles/house-style.md` covering the turn-shape
and visual rules (requirements-document R1–R16), the enforcement pointers (R19–R21), the explicit
`keep-coding-instructions: true`, the placard, and the tell. Separately write the canonical subagent
presentation preamble that both levers consume.

The tell must contain no box-drawing characters and must not collide with the `★ Insight` marker, which
`docs/engineering-journal/LEARNINGS.md` still uses as one of three conjoined provenance signals.

**Files:** `plugins/house-style/output-styles/house-style.md`,
`plugins/house-style/references/subagent-presentation-preamble.md`.

**Test scenarios** (`tests/test_house_style_contract.py`): frontmatter parses and sets
`keep-coding-instructions: true` literally; a placard section exists; the tell is present, is a single
literal string, and contains no character in the box-drawing Unicode block; `force-for-plugin` is absent.

**Depends on:** U2.

### U4. Style-file contract tests

Write the assertions U2 and U3 declare, plus a test that the style file is discoverable at the path
Claude Code expects (`output-styles/` at plugin root, not under `.claude-plugin/`).

**Files:** `tests/test_house_style_contract.py`.

**Test scenarios:** the file itself is the deliverable; it must fail if the frontmatter, the placard, or
the tell is removed, which the unit demonstrates by mutating each and observing the failure.

**Depends on:** U3.

### U5. Stamp the preamble into saga's emitter

Add a module-level `PRESENTATION_RIDER` beside `BUDGET_RIDER` (`execution_spec.py:464`), sourced from
the canonical preamble file, and append it in `_agent_prompt()` at line 3244. Unconditional — every
emitted `agent()` prompt carries it.

**Blast radius:** this file composes the prompt for every agent every saga workflow spawns in every
repository. A malformed rider degrades all of them. The unit's first action is running the existing
`execution_spec.py` suite to establish a green baseline.

**Files:** `plugins/saga/scripts/execution_spec.py`,
`tests/test_execution_spec_presentation_rider.py`.

**Test scenarios:** an emitted script contains the rider in every `agent()` prompt; the rider text is
byte-identical to the canonical preamble file; the existing `execution_spec.py` suite still passes; a
spec with zero units emits without error.

**Depends on:** U3.

### U6. Duplicate the preamble into the 36 agent definitions

Insert the canonical preamble into all 36 files matching `plugins/*/agents/*.md`, and write the
byte-identity test that polices the copies. The count is exact and enumerated, not globbed at test time
into whatever happens to be present — a test that discovers its own population cannot detect a file that
was never given the preamble.

**Files:** the 36 files under `plugins/*/agents/*.md`;
`tests/test_agent_preamble_identity.py`.

**Test scenarios:** all 36 files contain the preamble; every copy is byte-identical to
`plugins/house-style/references/subagent-presentation-preamble.md`; the file count is exactly 36 and a
37th agent file without the preamble fails; existing `tests/test_agent_registration_drift.py` still
passes.

**Depends on:** U3.

### U7. Extend the scorer with visual-gating and relay-quality measurements

Add the two measurements requirements-document R32 and R33 name, then produce their pre-style values by
running the scorer over the archived window to a **new** output path:
`docs/measurements/2026-08-08-extended-metrics.json`.

**Hard stop:** `docs/measurements/2026-08-07-baseline.json` is never the `--out` target. The unit
verifies with `git diff --exit-code` on that path before it reports done.

**Files:** `tools/output_style_scorer.py`, `tests/test_output_style_scorer.py`,
`docs/measurements/2026-08-08-extended-metrics.json` and its `.md` companion.

**Test scenarios:** each new metric returns a value on a synthetic corpus with a known answer; both are
labelled heuristic where they are heuristic, matching `bare_identifier_rate`'s existing honesty; the nine
existing metrics are unchanged on the same input; the committed baseline file is untouched.

**Depends on:** U1.

### U8. The annotation outside version control, and the provenance update

Add the reach annotation to the Communication section of `~/.claude/CLAUDE.md` (requirements-document
R18) with its one-question test, changing none of the seven Plain English rules. Update the provenance
procedure in `docs/engineering-journal/LEARNINGS.md` so the diagnostic that detects Claude-clone
teammates references the new tell (requirements-document R35).

**Known gap, carried not solved:** `~/.claude` is not a git repository, so the annotation is unversioned
wherever it lands. Whether it needs a version-controlled home is deferred, and the unit records the
annotation's exact text in the repository so it can be reconstructed.

**Files:** `~/.claude/CLAUDE.md`, `docs/engineering-journal/LEARNINGS.md`,
`plugins/house-style/references/claude-md-annotation.md`.

**Test scenarios:** the annotation text committed to the repository matches what was written to
`~/.claude/CLAUDE.md`; the seven Plain English rules are byte-identical before and after.

**Depends on:** U3.

### U9. Release surfaces, journal, and the ceiling sweep

Bump `plugin.json` and `CHANGELOG.md` for `house-style` and for each of the 9 plugins U6 touched; add
the `house-style` entry to `.claude-plugin/marketplace.json` with a matching version; write the
`LEARNINGS` and `DECISIONS` entries; and sweep every artifact for a reach claim above 45.7%.

**Files:** `.claude-plugin/marketplace.json`, 10 `plugin.json` files, 10 `CHANGELOG.md` files,
`docs/engineering-journal/LEARNINGS.md`, `docs/engineering-journal/DECISIONS.md`.

**Test scenarios:** `tests/test_release_surface_parity.py` passes; `marketplace.json` parses as JSON
after editing (the double-`]` insertion footgun has broken this repository's parse more than once);
plugin count is 12; no artifact matches `89\.4` or claims reach above 45.7% except where explicitly
labelled as the superseded figure.

**Depends on:** U2, U4, U5, U6, U7, U8.

## Dependency waves

| Wave | Units | Concurrency |
| --- | --- | --- |
| 1 | U1 | 1 |
| 2 | U2, U7 | 2 |
| 3 | U3 | 1 |
| 4 | U5, U6, U8 | 3 |
| 5 | U4 | 1 |
| 6 | U9 | 1 |

Maximum concurrent width is 3, at the session cap. No two units in any wave declare the same file: U5
owns `execution_spec.py`, U6 owns `plugins/*/agents/*.md`, U8 owns `~/.claude/CLAUDE.md` and the
LEARNINGS provenance entry. U8 and U9 both touch `docs/engineering-journal/LEARNINGS.md` but land in
different waves.

## Risk Analysis & Mitigation

| Risk | Likelihood | Mitigation |
| --- | --- | --- |
| A lever does not work | Real — never observed | U1 gates the run and stops on failure |
| The emitter rider degrades every saga workflow everywhere | Low, high impact | U5 establishes a green baseline first; the rider is additive text at one funnel |
| The 36 copies drift | High over time | The byte-identity test, with an exact expected count so a new agent file cannot slip through |
| The baseline is overwritten | Low, unrecoverable | R11, a hard stop in U7, and a `git diff --exit-code` check |
| The reach number inflates again downstream | Demonstrated once already | R12 plus the U9 sweep |
| The style is switched off in use | Unknown | Requirements-document R9's size threshold is the control, and it is still unset — carried as an open question, not solved here |
| `tools/` is outside the `mypy` and `bandit` CI scopes | Certain, low impact | Recorded; whether to widen CI scope is deferred |

## Scope Boundaries

**Deferred to follow-up work.**

- **Route (c), the main-thread stamp** — the only route to the 43.64% of subagent output written by
  hand. Deliberately deferred per KTD5, not cancelled.
- **Widening `mypy` and `bandit` to `tools/`** in continuous integration.
- **A version-controlled home for the `~/.claude/CLAUDE.md` annotation.**
- **Concrete target values for the Success Criteria directions**, and the size threshold for
  requirements-document R9. Both are open in the requirements document and are not invented here.

**True non-goals.**

- Per-repository committed settings, and the `.gitignore` change they would need.
- A second style file, and any generator or build step.
- `force-for-plugin: true` — the plugin does not override the operator's style selection.
- Pruning or rewriting any of the seven Plain English rules.
- The bare-Default control run, skipped by operator decision on 2026-08-07.
- Regenerating `docs/measurements/2026-08-07-baseline.json`.

## Open Questions

- The exact text of the tell (requirements-document R31) and the trigger-list membership for
  requirements-document R7 and R11 are authored in U3 rather than pre-decided here; they are design
  choices the unit makes and records, not gaps in the plan.
- Whether forks inherit the style in a way that changes reach is unmeasured. No credit is claimed.
