---
title: "enhancement: local-vs-CI parity — data-defined runner, locked-env simulator, fingerprint doctor, doc drift guard"
repo: infiquetra-claude-plugins
type: enhancement
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
objective: "Gate fleet integrity (agent files, prompts, release surfaces)"
wave: wave-2
type: enhancement
---

# enhancement: local-vs-CI parity — data-defined runner, locked-env simulator, fingerprint doctor, doc drift guard

### Objective

Gate fleet integrity (agent files, prompts, release surfaces)

## Problem / Motivation

This repo's recurring-pain themes call out "local-vs-CI verification parity gaps — CI red
on checks local runs passed" as a two-repo pattern (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:140-141`),
and lists a standing CI branch-trigger gap and doc-vs-workflow drift as separate live
singletons in the same synthesis (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:148-149`).
Six independently surfaced ideas converge on the same underlying defect class — no single
source of truth for "what does CI actually check," no way to reproduce CI's environment
locally, no automated detector when the two drift apart:

- `.github/workflows/ci.yml` hardcodes the check matrix across five separate jobs
  (`tests`, `validate`, `lint`, `type-check`, `security`), each re-declaring its own
  `actions/setup-python` + `astral-sh/setup-uv` + `uv sync --locked --extra dev` steps
  (`.github/workflows/ci.yml:1-160` — five duplicated setup blocks, one per job). There is
  no `tools/ci_local.py` or equivalent that both the workflow and a developer's terminal
  invoke, so "I ran the checks locally" and "CI ran the checks" are two independently
  maintained code paths that can silently diverge.
- One CI step invokes the interpreter directly instead of through `uv run`:
  `.github/workflows/ci.yml:40` — `run: python3 plugins/mission-control/config/generated/check_issue_contract_parity.py`
  — while every other step in the file uses `uv run python ...`
  (`.github/workflows/ci.yml:43,73,76,98,101,123,145,202`). A bare `python3` invocation can
  resolve to a different interpreter/environment locally than the `uv`-managed one CI uses,
  which is exactly the class of drift the grounding brief's theme 11 names.
- `CLAUDE.md:96-119` documents the canonical command set developers are told to run
  locally (`uv run pytest`, `uv run ruff check .`, `uv run mypy plugins/ scripts/ tests/
  --ignore-missing-imports`, `uv run bandit -r plugins/`) with an explicit note that "CI
  checks plugins/ scripts/ tests/, not just plugins/" — a call-out that exists precisely
  because this doc and `ci.yml` have drifted before and nothing fails the build when it
  happens again.
- There is no locked-environment simulator: nothing asserts that a developer's local
  Python interpreter version or `uv.lock` hash matches what CI actually installs, and
  nothing fingerprints tool versions (ruff/mypy/bandit) to produce an actionable diff when
  a locally pinned tool version is older than CI's.
- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:186` and `:148` separately name a
  "stacked-PR auto-close + CI branch-trigger gap" as unresolved — `check_docs.py` (the
  validate.yml consumer of the same class of tooling this issue formalizes,
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:77`) is not wired to a
  branch-push trigger that auto-closes a tracking item on green.

## Definition of Done

- `tools/ci_local.py` exists as a **data-defined check matrix**: a single Python module
  declaring the ordered list of checks (tests+coverage, plugin/marketplace validation,
  ruff check, ruff format check, mypy, bandit) with their exact command lines, consumed by
  both a local CLI entry point and `.github/workflows/ci.yml`'s job steps (via `uv run
  python tools/ci_local.py <job-name>` or equivalent), so there is exactly one place the
  check set is declared.
- `CLAUDE.md`'s "Running Quality Checks" section (`CLAUDE.md:96-119`) is either generated
  from `tools/ci_local.py`'s matrix or covered by a parity test that fails when the two
  diverge.
- A locked-environment simulator (`tools/ci-local.sh` or equivalent) runs the full check
  matrix under `uv sync --locked` and asserts local Python interpreter version and
  `uv.lock` hash match what `ci.yml` pins, exiting nonzero on mismatch.
- `scripts/ci_fingerprint.py` emits a fingerprint artifact (tool versions for
  ruff/mypy/bandit, the `uv.lock` hash, and the Python version) both in a `ci.yml` upload
  step and via a local invocation, and can diff two fingerprints to report the exact
  version delta.
- The bare `python3` invocation at `.github/workflows/ci.yml:40` is normalized to `uv run
  python`, and a guard test fails the build if any bare `python3`/`python` CI step
  invocation is reintroduced anywhere in `.github/workflows/ci.yml`.
- CI wiring exists so a branch-triggered `check_docs.py` run (the existing `validate.yml`
  consumer, `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:77`) auto-closes its
  tracking item on a green run, closing the branch-trigger gap named in
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:148-149`.
- All of the above merges without regressing existing CI: `tests`, `validate`, `lint`,
  `type-check`, `security`, and `publish` jobs in `.github/workflows/ci.yml` stay green
  after the runner/simulator/fingerprint/doc-parity wiring lands.

### Acceptance criteria
Each item below is one testable AC, tagged to the absorbed idea it grounds.

- [ ] **[T11-F4-4 — single source-of-truth runner]** Running `tools/ci_local.py` locally
   reproduces every job currently declared in `.github/workflows/ci.yml` (tests, validate,
   lint, type-check, security), and `ci.yml`'s steps are rewired to invoke it; CI stays
   green on a clean checkout. Check: `uv run python tools/ci_local.py --all` exits `0` on a
   clean checkout, and the corresponding CI run on the same commit is green.
- [ ] **[T11-F5-5 — locked-env simulator]** `tools/ci-local.sh` (or equivalent) runs the check
   matrix under `uv sync --locked` and exits nonzero when the local Python interpreter
   version or `uv.lock` hash does not match the pinned parity value, and exits `0` when
   they match. Check: `tools/ci-local.sh` against a deliberately mismatched interpreter
   (e.g. Python 3.11 instead of 3.12) exits nonzero; against the correct interpreter and a
   clean `uv.lock`, exits `0`.
- [ ] **[T11-F6-3 — fingerprint doctor]** `scripts/ci_fingerprint.py` emits
   `fingerprint.json` (tool versions + `uv.lock` hash + Python version) both from a `ci.yml`
   step and from a local invocation; pinning an older `ruff` version locally and re-running
   the doctor reports the exact version delta (not a generic "mismatch"). Check: `uv run
   python scripts/ci_fingerprint.py --compare ci-fingerprint.json local-fingerprint.json`
   reports `ruff: X.Y.Z (local) != A.B.C (ci)` when versions differ.
- [ ] **[T11-F2-2 — uv-invocation normalization]** Zero bare `python3`/`python` invocations
   remain in `.github/workflows/ci.yml` outside of `uv run python ...` forms; a guard test
   fails (reds) if one is reintroduced. Check: `uv run pytest tests/test_ci_uv_invocation_guard.py`
   passes on the merged state, and fails when a bare `run: python3 ...` line is injected
   into `ci.yml` as a test fixture.
- [ ] **[T11-F4-5 — doc/CI drift guard]** A parity test diffs the command/scope set
   documented in `CLAUDE.md`'s "Running Quality Checks" section against the check matrix
   `ci.yml` actually runs, and fails on injected mismatch. Check:
   `uv run pytest tests/test_ci_command_doc_parity.py` passes on the merged state; fails
   when `tests/` is dropped from the documented mypy scope line in `CLAUDE.md` while
   `ci.yml`'s mypy step still includes it, and passes again once reconciled.
- [ ] **[S-15 — branch-trigger auto-close]** A branch push triggers `check_docs.py` (the
   existing `validate.yml`/`check_docs.py` path) and the corresponding tracking item
   (issue or check run) auto-closes on a green result. Check: push a branch with a
   deliberately broken doc reference, observe the check run red and no auto-close; fix the
   reference, push again, observe the check run green and the tracking item close.

### Out-of-scope / non-goals
**In scope:** `tools/ci_local.py` (or equivalent single-source runner), a locked-env
simulator script, `scripts/ci_fingerprint.py`, the doc/CI parity test, the uv-invocation
guard test, and the branch-trigger wiring for `check_docs.py` auto-close. All changes are
additive tooling plus normalization of one existing bare-`python3` CI step
(`.github/workflows/ci.yml:40`).

**Non-goals:**
- Rewriting or restructuring the five existing CI jobs (`tests`, `validate`, `lint`,
  `type-check`, `security`, `publish`) beyond pointing their steps at the new data-defined
  matrix — job topology, runner labels, and trigger conditions (`on: push`/`pull_request`
  branches) stay as-is except for the specific branch-trigger gap closed by this issue.
- Mermaid syntax validation gap in `check_docs.py` (a separately named singleton in
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:149`) — out of scope, tracked
  separately.
- Any change to `uv sync --extra dev` package contents, ruff/mypy/bandit rule
  configuration, or coverage thresholds — this issue is about parity/detection tooling,
  not changing what the checks enforce.
- Cross-repo rollout of the runner/simulator pattern — this issue delivers it for
  `infiquetra-claude-plugins` only.

## Grounding References

- **T11-F4-4** (primary) — "Single source-of-truth CI runner both GitHub Actions local
  invoke." Basis: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T11.json`
  (theme T11, frame F4). DOD sketch: `tools/ci_local.py` data-defined check matrix, `ci.yml`
  steps rewired to invoke it, `CLAUDE.md` pointer, matrix-parse test.
- **T11-F5-5** (facet) — "Level-D simulator: hermetic locked-env pre-push run certified to
  match CI." Basis: same survivors file, frame F5. DOD sketch: `tools/ci-local.sh` running
  checks under `uv sync --locked` plus interpreter/lockfile-hash parity assertion and test.
- **T11-F6-3** (facet) — "CI-parity fingerprint doctor: autonomous red-vs-green
  environment diff." Basis: same survivors file, frame F6. DOD sketch:
  `scripts/ci_fingerprint.py` plus a `ci.yml` step uploading `fingerprint.json` (tool
  versions + `uv.lock` hash + Python version) and a local target.
- **T11-F2-2** (facet) — "Kill uv-vs-python3 invocation split reproduces differently
  locally." Basis: same survivors file, frame F2. DOD sketch: merged `ci.yml` normalizing
  the bare `python3` parity-check step to `uv run python`, plus a guard rejecting non-`uv
  run` python invocations.
- **T11-F4-5** (facet) — "Drift guard fails when CLAUDE.md's documented checks diverge
  from ci.yml." Basis: same survivors file, frame F4. DOD sketch:
  `tests/test_ci_command_doc_parity.py` parsing both files and diffing the command/scope
  set.
- **S-15** (facet, seed) — "CI branch-trigger auto-close (check_docs.py)." Basis (direct):
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §8 direct-to-candidate
  "CI-trigger"; §8 "auto-close + CI branch-trigger gap" (`:186`, `:148-149`). DOD sketch:
  merged CI wiring so branch-triggered `check_docs.py` runs and auto-closes on pass.
- Consolidation rationale (from `issue-map-final.json`): all six absorbed ideas chase the
  same two-repo CI-red-local-green pattern — single source-of-truth runner, hermetic
  locked-env run, environment fingerprint diff, uv-invocation normalization,
  `CLAUDE.md`-vs-`ci.yml` parity, and the branch-trigger gap seed.
- Binding context this issue builds on: `CLAUDE.md:96-119` ("Running Quality Checks",
  including the explicit CI-scope note "match CI scope — CI checks plugins/ scripts/
  tests/, not just plugins/"); `CLAUDE.md:105-109` (release-surface checklist step 6,
  applicable if any generated tooling touches plugin metadata); recurring-pain theme 11
  and theme 3 ("release-surface drift persists despite CLAUDE.md step 6 — room for
  automation") in `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:143`.

## Recommended Executor Profile

- **Model:** Sonnet
- **Effort:** high — *target posture: not a live team-execution dispatch knob until `pf-effort-first-class` lands; teammates inherit session tier until then*
- **Backend:** team-execution
- **External LLM:** none
- **Justification:** mechanical, well-specified tooling work (data-defined runner, shell
  simulator, fingerprint diff, two guard tests, one workflow-file edit) with no ambiguous
  design decisions left open — Sonnet at high effort is sufficient; no case for an
  above-Sonnet tier or external-engine involvement.

## Release-Surface Checklist

This issue does not change any plugin's runtime behavior, schema, command, prompt, or
user-facing guidance — it adds repo-root CI/tooling (`tools/`, `scripts/`, `tests/`,
`.github/workflows/ci.yml`) with no `plugins/<plugin>/` behavior change. Per `CLAUDE.md`'s
release-surface rule (step 6), no plugin-level `plugin.json`, `marketplace.json`, or
`CHANGELOG.md` update is required. If a later revision of this work touches
`plugins/mission-control/config/generated/check_issue_contract_parity.py` behavior (beyond
its invocation form) or any plugin's documented commands, the release-surface checklist
must be re-run for that plugin at that time:

- [ ] `plugins/<plugin>/.claude-plugin/plugin.json` — not applicable (no plugin behavior
      changed)
- [ ] `.claude-plugin/marketplace.json` — not applicable
- [ ] `plugins/<plugin>/CHANGELOG.md` — not applicable
- [ ] Version/metadata drift-guard tests — not applicable; this issue instead adds new
      drift-guard tests (`tests/test_ci_command_doc_parity.py`,
      `tests/test_ci_uv_invocation_guard.py`) as its own deliverable

## Tests to Add or Update

- `tests/test_ci_command_doc_parity.py` — new; diffs `CLAUDE.md`'s documented check
  commands/scopes against `tools/ci_local.py`'s data-defined matrix.
- `tests/test_ci_uv_invocation_guard.py` — new; greps `.github/workflows/ci.yml` for bare
  `python3`/`python` `run:` lines outside `uv run` and fails if any are found.
- `tests/test_ci_fingerprint.py` — new; unit-tests `scripts/ci_fingerprint.py`'s diff
  output format against a fixture pair of fingerprints with one differing tool version.
- `tests/test_ci_local_runner.py` — new; asserts `tools/ci_local.py`'s matrix entries
  match the step commands actually declared in `.github/workflows/ci.yml` (parsed, not
  hand-duplicated).

## Files Expected to Change

Indicative only; `/plan` determines the exact set.

- `tools/ci_local.py` — new; data-defined check matrix + local CLI entry point.
- `tools/ci-local.sh` — new; locked-env simulator invoking `uv sync --locked` then the
  matrix.
- `scripts/ci_fingerprint.py` — new; environment fingerprint emit + diff.
- `.github/workflows/ci.yml` — edited; rewire job steps to invoke `tools/ci_local.py`,
  normalize the `.github/workflows/ci.yml:40` bare `python3` call to `uv run python`, add
  a fingerprint-upload step, wire branch-trigger auto-close for `check_docs.py`.
- `CLAUDE.md` — edited or verified generated; "Running Quality Checks" section
  (`CLAUDE.md:96-119`) kept in parity with the matrix.
- `tests/test_ci_command_doc_parity.py`, `tests/test_ci_uv_invocation_guard.py`,
  `tests/test_ci_fingerprint.py`, `tests/test_ci_local_runner.py` — new.

### Verification
```bash
# Data-defined runner reproduces CI locally
uv run python tools/ci_local.py --all

# Locked-env simulator: exits nonzero on interpreter/lockfile mismatch, 0 when matched
tools/ci-local.sh

# Fingerprint doctor reports exact version deltas
uv run python scripts/ci_fingerprint.py --emit local-fingerprint.json
uv run python scripts/ci_fingerprint.py --compare ci-fingerprint.json local-fingerprint.json

# Guard tests
uv run pytest tests/test_ci_command_doc_parity.py tests/test_ci_uv_invocation_guard.py \
  tests/test_ci_fingerprint.py tests/test_ci_local_runner.py -v

# Full repo gate stays green
uv run pytest && uv run ruff format --check . && uv run ruff check . && \
  uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports && \
  uv run bandit -r plugins/ scripts/ tests/ -ll
```

Expected: all commands exit `0`; the fingerprint compare shows a concrete diff line
(e.g. `ruff: X.Y.Z (local) != A.B.C (ci)`) when versions are deliberately mismatched in a
test fixture, and no diff when they match.

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

### Source context

- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T11.json`,
  `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json`,
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
- Source type: ideation issue-map (absorbed facets)
- Source title: Local-vs-CI parity: one data-defined runner, locked-env simulator,
  fingerprint doctor, doc drift guard

### Intent

This repo's recurring-pain themes call out "local-vs-CI verification parity gaps — CI red on checks local runs passed" as a two-repo pattern (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:140-141`), and lists a standing CI branch-trigger gap and doc-vs-workflow drift as separate live singletons in the same synthesis (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:148-149`). Six independently surfaced ideas converge on the same underlying defect class — no single source of truth for "what does CI actually check," no way to reproduce CI's environment locally, no automated detector when the two drift apart:

### Context library links

_none_

### Files expected to change

- `.github/workflows/ci.yml`
- `tools/ci_local.py`
- `tools/ci-local.sh`
- `scripts/ci_fingerprint.py`
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T11.json`
- `tests/test_ci_command_doc_parity.py`
- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
- `plugins/mission-control/config/generated/check_issue_contract_parity.py`

### Tests to add or update

- `tests/test_ci_command_doc_parity.py`
- `tests/test_ci_fingerprint.py`
- `tests/test_ci_local_runner.py`
- `tests/test_ci_uv_invocation_guard.py`

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/425
- Number: 425
- Created at: 2026-07-04T08:09:19.479467+00:00

