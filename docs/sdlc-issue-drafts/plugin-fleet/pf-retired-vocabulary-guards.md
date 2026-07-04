---
title: "enhancement: retired-vocabulary guards — reverse CI guard + executable retirement invariants"
repo: infiquetra-claude-plugins
type: enhancement
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan, quick-win
risk: low
handoff_maturity: requirements-ready
tier: quick-win
wave: wave-2
objective: Establish single-source-of-truth for shared primitives
type: enhancement
---

# enhancement: retired-vocabulary guards — reverse CI guard + executable retirement invariants

### Objective

Establish single-source-of-truth for shared primitives.

### Summary

The fleet has retired a series of names and tokens over multiple rename campaigns
(`infiquetra-lifecycle`→`saga`, `sdlc-manager`→`mission-control`, `infiquetra-deploy`→`deploy`,
`blueprint-reviewer` folded into `saga`, and `Mount Olympus`/`themis` retired as active routing
targets in the SDLC schema) — but every one of these retirements is enforced only by prose: a
migration note, an archive comment, a schema `status` field nobody diffs against. Nothing in CI
stops a retired token or a retired team from creeping back into an active file, and nothing asserts
that active routing surfaces (`phase_board_map`, `wip_limits`, `cross_team_transfer` targets) stay
free of retired teams. This issue ships the two cheap, durable guards that close that gap: a
reverse CI guard over a maintained `retired-vocabulary.txt`, and a schema-derived test that treats
"no active surface routes through a retired term" as an executable invariant instead of a promise.

### Problem / Motivation

**Retired tokens have no forward guard (T14-F4-8).**
`docs/engineering-journal/ARCHIVE.md:9` records the whole-family rename explicitly: "entries below
name plugins by original directory names; the work family was later renamed —
`infiquetra-lifecycle`->`saga`, `sdlc-manager`->`mission-control`, `infiquetra-deploy`->`deploy`,
and `blueprint-reviewer` was folded into `saga`" — and it already carves out a historical-naming
exception for its own entries. That sentence is the entire enforcement mechanism today: nothing
in `.github/workflows/ci.yml` checks a PR diff for reintroduction of any of these five retired
tokens outside the historical-journal files that are allowed to keep them (`ARCHIVE.md`,
`CHANGELOG.md` history). A rename campaign's real failure mode is not the rename itself — it is
silent regression months later, when a new file, script, or doc reintroduces a dead token because
nobody remembers it was retired.

**Retirement in the SDLC schema has no reverse-lookup guard (T14-F1-7).**
`plugins/mission-control/config/sdlc-schema.json:27-33` marks the `olympus` team
`"status": "retired_historical"` with `"board": null` and an explicit instruction ("Preserved
history only; do not route active work or current board state through Mount Olympus"); the
`themis` team (`:60`-ish, same block) carries the identical `retired_historical` status. Line 205
states the same intent in prose for cross-team routing: `"cross_team_transfer_rule": "... Mount
Olympus is retired historical context and is not an active target."` Line 218 carries a
`retired_patterns` list (`["olympus-input-orchestrator", "olympus:agent:input-request",
"#agent-handoffs as canonical HITL channel"]`) with the same "don't route through this" intent.
None of this is tested. Nothing asserts that `phase_board_map` (`:553`), the schema's active
board-status projections, or any other active routing surface actually excludes the
`retired_historical` teams or the `retired_patterns` entries. The migration note at
`sdlc-schema.json:6` ("Retired Mount Olympus as an active board projection...") is a comment, not
a check — an incomplete future rename could silently leave a live routing edge pointed at a dead
team, and CI would stay green.

Both gaps share the same shape: a rename/retirement campaign's core promise ("the old thing is
truly dead in active surfaces") is asserted in a comment and nowhere else. This is exactly the kind
of cheap, durable residue the fleet should be leaving behind after every rename — a permanent,
near-zero-cost guard rather than continued vigilance.

### Definition of Done

- `retired-vocabulary.txt` at repo root (or `tools/retired-vocabulary.txt`, matching this repo's
  existing `tools/` convention alongside `stale_main_guard.py`) lists the five known-retired tokens:
  `infiquetra-lifecycle`, `sdlc-manager`, `infiquetra-deploy`, `blueprint-reviewer`, `Olympus`.
- `scripts/check_retired_vocab.py` scans the repo (or the PR diff) for any retired-vocabulary
  token appearing outside an explicit historical-journal allowlist (at minimum
  `docs/engineering-journal/ARCHIVE.md`, `docs/engineering-journal/CHANGELOG.md`, and any
  `CHANGELOG.md` under `plugins/*/`), and exits non-zero on a hit.
- `check_retired_vocab.py` is wired into `.github/workflows/ci.yml` as a named step (following the
  existing named-step convention used for `check_issue_contract_parity.py`), so a retired-token
  reintroduction fails the PR the same way vendored-parity drift does today.
- A new test (e.g. `tests/test_retired_vocabulary_isolation.py`) derives the retired-team set
  directly from `plugins/mission-control/config/sdlc-schema.json` (every team with
  `"status": "retired_historical"`, plus every entry in `retired_patterns`) and asserts that every
  active routing surface in the schema (`phase_board_map`, `wip_limits`, and any
  `cross_team_transfer`-style target list) contains zero references to that derived retired set.
- Both guards are proven to fire: one test/fixture injects a retired token into a non-allowlisted
  file and shows the CI guard trips; one test injects a retired-team reference into a
  `phase_board_map` fixture and shows the schema-isolation test fails.
- The current tree (retired tokens present only in `ARCHIVE.md`/`CHANGELOG.md` history, no retired
  team referenced in any active routing surface) passes both guards cleanly.

### Acceptance criteria
- [ ] **(T14-F4-8)** A retired token (e.g. `sdlc-manager`) injected into a non-allowlisted file
      trips `check_retired_vocab.py`. Check: `python3 scripts/check_retired_vocab.py` against a
      fixture/tmp file containing the token → non-zero exit, output names the offending token and
      file.
- [ ] **(T14-F4-8)** The current tree passes `check_retired_vocab.py` cleanly (retired tokens exist
      only inside the allowlisted historical-journal files). Check:
      `python3 scripts/check_retired_vocab.py` on the unmodified working tree → exit `0`.
- [ ] **(T14-F4-8)** `check_retired_vocab.py` is invoked as a named step in `.github/workflows/ci.yml`
      and runs on every PR. Check: `grep -n "check_retired_vocab.py" .github/workflows/ci.yml` →
      matches.
- [ ] **(T14-F1-7)** The retired-vocabulary test derives its retired-team set from
      `sdlc-schema.json` at runtime (not a hardcoded literal list), reading every team whose
      `status` equals `retired_historical` plus every entry in `retired_patterns`. Check:
      `uv run pytest tests/test_retired_vocabulary_isolation.py -k derives_retired_set -v` →
      passes, and assertion covers both `olympus` and `themis`.
- [ ] **(T14-F1-7)** Injecting a retired-team reference (e.g. `olympus`) into a `phase_board_map`
      fixture causes the isolation test to fail. Check:
      `uv run pytest tests/test_retired_vocabulary_isolation.py -k phase_board_map_injection -v` →
      fails against the mutated fixture, demonstrating the assertion is load-bearing (invert to
      confirm: same test passes against the real schema).
- [ ] **(T14-F1-7)** The real (unmutated) `sdlc-schema.json`'s active routing surfaces
      (`phase_board_map`, `wip_limits`) contain zero references to the derived retired set today.
      Check: `uv run pytest tests/test_retired_vocabulary_isolation.py -v` → passes against the
      committed schema.
- [ ] Full suite, lint, and type checks stay green. Check: `uv run pytest && uv run ruff check . &&
      uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` → all pass.

### Out-of-scope / non-goals
**In scope:**
- The reverse CI guard over a maintained retired-token list, historical-journal allowlist, and its
  CI wiring.
- The schema-derived executable test asserting active-surface isolation from retired teams and
  retired patterns.
- Fixture-based proof (both directions: injected token/reference trips the guard; current tree
  passes clean).

**Out of scope / non-goals:**
- Adding new tokens or teams to the retired list beyond the five tokens and two teams already
  documented in `ARCHIVE.md` and `sdlc-schema.json` — this issue enforces existing retirements, it
  does not retire anything new.
- Backfilling a retired-vocabulary guard onto other repos in the fleet — this issue is scoped to
  `infiquetra-claude-plugins` only.
- Any change to `sdlc-schema.json`'s actual routing logic (`phase_board_map`, `wip_limits`,
  `cross_team_transfer_rule`) — the isolation test only asserts the current, already-correct state;
  it does not modify schema content.
- Any change to how future rename campaigns are executed (tooling for performing a rename) — this
  is the durable-residue guard left behind after a rename, not the rename executor itself
  (that is a separate, previously-noted idea, `T14-F4-5`, not part of this issue).
- General "vocabulary drift" linting beyond the five known-retired tokens (e.g. no new heuristic
  vocabulary-similarity detection) — the list is explicit and hand-maintained.

### Grounding References

- **T14-F4-8** ("Retired-vocabulary reverse guard") — basis:
  `docs/engineering-journal/ARCHIVE.md:9` names the retired tokens explicitly
  (`infiquetra-lifecycle`->`saga`, `sdlc-manager`->`mission-control`, `infiquetra-deploy`->`deploy`,
  `blueprint-reviewer` folded into `saga`) and already carves out a historical-naming exception,
  evidencing both the retired-token set and the need for an allowlist.
- **T14-F1-7** ("Executable retired-vocabulary invariant") — basis:
  `plugins/mission-control/config/sdlc-schema.json` — `teams.olympus` at `status:
  "retired_historical"` with `board: null` (and `teams.themis` carrying the same status);
  `retired_patterns` list at line 218; `cross_team_transfer_rule` at line 205 stating "Mount
  Olympus is retired historical context and is not an active target" as prose with no test
  enforcing that active surfaces exclude the retired set.
- Binding decisions this builds on: `{#plugin-portfolio-groom-17-to-7}` (plugin/tooling sprawl is
  an active concern — this issue adds one small guard script and one test file, not a new plugin,
  keeping blast radius minimal per that decision's spirit).
- Wave/objective placement: `wave-2`, objective "Establish single-source-of-truth for shared
  primitives" — per `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T14.json` and
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §5-6 (recurring-pain theme: rename
  campaigns leave prose-only enforcement of their own retirement promise; this issue converts that
  residue into an executable, CI-checked invariant).

### Recommended Executor Profile

- **Model:** sonnet
- **Effort:** medium
- **Backend:** inline
- **External LLM:** none
- **Justification:** Mechanical, well-scoped work — a token-scan script, an allowlist file, and a
  schema-derived pytest module, all following existing repo conventions (`tools/stale_main_guard.py`
  for the scan-script shape, `check_issue_contract_parity.py` for the CI-step-naming convention).
  No architectural judgment calls or adversarial review needed; sonnet at medium effort matches the
  fleet's tiering guidance for mechanical/deterministic work.

### Release-Surface Checklist

This issue does not change any plugin's user-facing behavior, schema, command, or prompt surface —
it adds a repo-root CI guard and a repo-root test file, neither of which lives inside a plugin
directory or changes a plugin's `plugin.json`-declared contract. Per the repo's release-surface
rule, the checklist below is evaluated and found not-applicable, but is recorded explicitly rather
than silently skipped:

- [ ] N/A — no `plugins/<plugin>/.claude-plugin/plugin.json` version bump required (no plugin
      behavior, schema, or command changed).
- [ ] N/A — no `.claude-plugin/marketplace.json` update required (no plugin's marketplace listing
      changed).
- [ ] N/A — no plugin `CHANGELOG.md` entry required (change is a repo-level CI/test guard, not a
      plugin-level change). A `docs/engineering-journal/DECISIONS.md` entry documenting the
      retired-vocabulary-guard pattern is expected in the same PR per this repo's engineering-journal
      practice.
- [ ] N/A — no version/metadata drift-guard test needs updating (no plugin metadata changed).

### Tier

quick-win

### Type

enhancement

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

### Context library links

_none_

### Files expected to change

- `.github/workflows/ci.yml`
- `scripts/check_retired_vocab.py`
- `docs/engineering-journal/ARCHIVE.md`
- `docs/engineering-journal/CHANGELOG.md`
- `tests/test_retired_vocabulary_isolation.py`
- `plugins/mission-control/config/sdlc-schema.json`
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T14.json`
- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`

### Tests to add or update

- `tests/test_retired_vocabulary_isolation.py`

### Verification

```bash
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

### Intent

The fleet has retired a series of names and tokens over multiple rename campaigns (`infiquetra-lifecycle`→`saga`, `sdlc-manager`→`mission-control`, `infiquetra-deploy`→`deploy`, `blueprint-reviewer` folded into `saga`, and `Mount Olympus`/`themis` retired as active routing targets in the SDLC schema) — but every one of these retirements is enforced only by prose: a migration note, an archive comment, a schema `status` field nobody diffs against. Nothing in CI stops a retired token or a retired team from creeping back into an active file, and nothing asserts that active routing surfaces (`phase_board_map`, `wip_limits`, `cross_team_transfer` targets) stay free of retired teams. This issue ships the two cheap, durable guards that close that gap: a reverse CI guard over a maintained `retired-vocabulary.txt`, and a schema-derived test that treats "no active surface routes through a retired term" as an executable invariant instead of a promise.

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/456
- Number: 456
- Created at: 2026-07-04T08:24:52.453462+00:00

