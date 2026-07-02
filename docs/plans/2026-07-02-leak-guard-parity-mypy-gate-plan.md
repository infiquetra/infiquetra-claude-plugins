---
title: Leak-guard legacy-branch parity + local mypy gate step
type: fix
status: active
date: 2026-07-02
origin: infiquetra/infiquetra-claude-plugins#314
---

# Leak-guard legacy-branch parity + local mypy gate step

Close the two remaining gaps behind issue #314's "local gate disagrees with CI" theme. The main
saga-dirs leak-guard already got its baseline-diff fix in #317; what's left is (1) apply the same
baseline treatment to the **legacy-checkpoint** branch of the same guard and give the guard logic a
real proof-test, and (2) add the missing **mypy** step to the local pre-push gate so a type error
that fails CI also fails locally. Test-infrastructure only — no `saga.py` runtime, hook, or storage
change.

## Issue / origin

- Issue: infiquetra/infiquetra-claude-plugins#314 (`enhancement`, OPEN)
- Scope-addition comment (mypy gate) by @namredips, 2026-06-30:
  https://github.com/infiquetra/infiquetra-claude-plugins/issues/314#issuecomment-4847728983
- Provenance per the issue: surfaced shipping #281 (PreCompact spore); guard last touched in #308,
  pre-existing test-harness debt unrelated to that feature.

## Drift audit — issue premises re-verified 2026-07-02

Issue #314 was filed against the pre-#317 tree. The evidence-manifest work (`e901ae1`, #317) added a
baseline snapshot to the guard's **main** branch after the issue was written, so the issue body
describes code that no longer exists. Every load-bearing claim was re-checked against the current
tree; this plan supersedes the issue where they disagree.

| Issue claim | Status today | Evidence |
|---|---|---|
| Guard asserts absolute `leaked == []` at `test_saga_saga.py:1350-1353` | **FALSE — already fixed for the sagas branch** | `tests/test_saga_saga.py:1346-1350` (`_PREEXISTING_SAGA_DIRS` snapshot), `:1364` (`if p.name not in _PREEXISTING_SAGA_DIRS`) — landed in `e901ae1` (#317) |
| Fix should live in a `pytest_sessionstart` hook in `tests/conftest.py` | **Superseded** — shipped fix used a module-level collection-time snapshot in the test file; `conftest.py` has no session hook and no `SAGAS_DIR`/`LEGACY_CHECKPOINT_DIR` reference | grep of `tests/conftest.py` returns 0 matches for `sessionstart`/`SAGAS_DIR`/`_PREEXISTING` |
| Legacy-checkpoint branch still needs baseline treatment (AC#4) | **Still true — genuinely outstanding** | `tests/test_saga_saga.py:1366-1369` — absolute `leaked_cp == []`, no baseline |
| "add/keep a test proving the guard still catches a *new* dir" (AC#1) | **Partially unmet** — no dedicated proof-test exists; only the live guard reads real state | grep: `_PREEXISTING_SAGA_DIRS` referenced only inside the guard, no meta-test |
| Local pre-push gate omits mypy while CI runs it (comment scope) | **Still true** | `tools/gate-manifest.json` steps = ruff-format, ruff-lint, validate-plugins, validate-marketplace, pytest (no mypy); CI runs `uv run python -m mypy plugins/ scripts/ tests/ --ignore-missing-imports` at `.github/workflows/ci.yml:123` |

Net: the plan is smaller than the issue implies. AC#2 and AC#3 (sagas-branch false-positive fixed,
`uv run pytest` green with a live saga present) are **already satisfied by #317** and require no
work — this plan does not re-touch the sagas branch beyond routing it through a shared helper.

## Requirements

Carried forward from issue #314's acceptance criteria and the mypy-scope comment, re-baselined to
the current tree.

- R1. The leak-guard's **legacy-checkpoint** branch must not false-positive on a legacy checkpoint
  file (`issue-*-phase*.md`) that existed under `.claude/saga/checkpoints/` before the suite started
  — same baseline-diff semantics the sagas branch already has (issue AC#4).
- R2. The guard must **still fail** when a run creates a genuinely *new* saga dir or a *new* legacy
  checkpoint under the repo-root `.claude/` — the original protection is preserved and proven by a
  dedicated test (issue AC#1).
- R3. The local pre-push gate must run mypy with the **exact** CI invocation
  (`uv run python -m mypy plugins/ scripts/ tests/ --ignore-missing-imports`), so a type error that
  fails CI also fails the local gate (comment scope; local↔CI "green" parity).
- R4. The gate-manifest drift-guard test must recognize mypy as a required step so the manifest and
  CI can't silently re-diverge (`tests/test_pre_push_gate.py:76-91`).

## Key Technical Decisions

- **KTD1 — extract a pure `_leaked_children(current, baseline)` helper; both guard branches call it.**
  The guard reads live filesystem state against a module-frozen baseline constant, which cannot be
  unit-tested without polluting the real repo (and ironically tripping itself). Extracting the set
  diff into a pure `frozenset → sorted list` helper makes both branches one-liners and gives R2 a
  filesystem-free proof-test. Rationale: standard "separate logic from I/O to test it." *Rejected:*
  monkeypatching `_PREEXISTING_SAGA_DIRS` and `mkdir`-ing real dirs under `ROOT` — pollutes the
  working tree and is exactly the leak the guard exists to catch.
- **KTD2 — follow the shipped module-level-snapshot pattern, not the issue's `conftest` hook.** The
  sagas branch already snapshots at module import (collection) time; the legacy branch will mirror it
  with a sibling `_PREEXISTING_LEGACY_CHECKPOINTS` constant. Rationale: consistency with proven,
  already-merged code beats reintroducing a second, divergent baseline mechanism in `conftest.py`.
  *Rejected:* the issue's proposed `pytest_sessionstart` hook — it would fork the baseline logic
  across two files for no behavioral gain.
- **KTD3 — place the mypy step among the static checks, before pytest.** Order becomes ruff-format →
  ruff-lint → **mypy** → validate-plugins → validate-marketplace → pytest. Rationale: group the fast
  static analyzers together and keep the slow test suite last so a type error fails fast. CI runs the
  jobs in parallel so gate order is purely a local-ergonomics choice. *Rejected:* appending mypy
  after pytest — pays the full suite cost before catching a static error.

## Implementation Units

Dependency-ordered. Both units are independently landable; each lives in a distinct file pair. No
runtime code is touched.

### U1. Legacy-branch baseline parity + pure diff helper + proof-tests

Bring the legacy-checkpoint branch to parity with the sagas branch by routing both through a new
pure helper, and add the dedicated proof-tests R2/AC#1 require.

**Files:** `tests/test_saga_saga.py` (guard block at `:1338-1369`, plus new helper + new tests).

**Changes:**

- Add a module-level `_PREEXISTING_LEGACY_CHECKPOINTS` snapshot beside `_PREEXISTING_SAGA_DIRS`
  (`:1346`), computed at collection time from `(ROOT / LEGACY_CHECKPOINT_DIR).glob("issue-*-phase*.md")`
  names, empty-frozenset when the dir is absent — mirroring the sagas snapshot exactly.
- Extract `_leaked_children(current: frozenset[str], baseline: frozenset[str]) -> list[str]`
  returning `sorted(current - baseline)`.
- Rewrite both branches of `test_suite_does_not_create_claude_dir_under_repo_root` (`:1362-1369`) to
  build a `current` frozenset and delegate to `_leaked_children` — the sagas branch keeps identical
  behavior; the legacy branch gains the baseline diff (R1).

**Test expectation:** New tests in `tests/test_saga_saga.py`:

*Helper-level (pure logic):*
- `test_leaked_children_flags_new_entries` — `_leaked_children({"issue-99"}, frozenset())` returns
  `["issue-99"]` (proves R2: a new dir is caught).
- `test_leaked_children_ignores_preexisting_entries` —
  `_leaked_children({"issue-42"}, frozenset({"issue-42"}))` returns `[]` (proves the false-positive
  is gone).
- `test_leaked_children_flags_only_the_new_among_preexisting` —
  `_leaked_children({"issue-42", "issue-99"}, frozenset({"issue-42"}))` returns `["issue-99"]`
  (proves a live saga coexists with leak detection — the exact #281 scenario).

*Guard-wiring (integration — proves the guard itself, not just the helper, per AC#1 literally):*
- `test_guard_raises_on_new_saga_dir_under_root` — `monkeypatch.setattr` the module's `ROOT` to a
  `tmp_path` and `_PREEXISTING_SAGA_DIRS` to an empty frozenset, `mkdir` a fresh
  `tmp_path / SAGAS_DIR / "issue-99"`, then assert `test_suite_does_not_create_claude_dir_under_repo_root()`
  raises `AssertionError`. This exercises the real guard's current-state read + baseline diff end to
  end, safely (state lives under `tmp_path`, never the real repo — honoring KTD1's no-pollution
  constraint).
- `test_guard_passes_when_only_preexisting_saga_dir_present` — same setup but with `"issue-99"` in
  the patched baseline; assert the guard does **not** raise (guard-level proof the false-positive is
  gone). Mirror both with a legacy-checkpoint pair (`tmp_path / LEGACY_CHECKPOINT_DIR / "issue-1-phase2.md"`)
  so the legacy branch's wiring is proven too.

The helper tests pin the diff logic; the guard-wiring tests pin the wiring. Both branches call the
same helper, so the legacy glob shape (`issue-*-phase*.md`) is a filename-vs-dirname difference only.

### U2. Add mypy step to the local pre-push gate

Add the missing mypy gate step mirroring CI, and update the drift-guard so the manifest can't silently
lose it again.

**Files:** `tools/gate-manifest.json`, `tests/test_pre_push_gate.py`.

**Changes:**

- Insert a `mypy` step into `tools/gate-manifest.json` after `ruff-lint` (KTD3):
  `{"id": "mypy", "label": "mypy type check", "command": ["uv", "run", "python", "-m", "mypy",
  "plugins/", "scripts/", "tests/", "--ignore-missing-imports"], "failure_hint": "Run `uv run python
  -m mypy plugins/ scripts/ tests/ --ignore-missing-imports` and fix the type errors reported
  above."}` — both `command` array and `failure_hint` use the `python -m` form, mirroring
  `.github/workflows/ci.yml:123` token-for-token and matching the existing ruff steps' hint style
  (R3).
- In `tests/test_pre_push_gate.py`, add `"mypy"` to the `required` set in
  `test_manifest_contains_required_gate_steps` (`:83-89`) and update its docstring + the module
  docstring (`:9`, `:78`) from "5 gate steps" to "6" (R4).

**Precondition (verified 2026-07-02):** the tree is already mypy-clean —
`uv run python -m mypy plugins/ scripts/ tests/ --ignore-missing-imports` reports "Success: no
issues found in 113 source files". So the new gate step lands green and does not red-block the
pre-push gate on merge; no type-error cleanup precedes this unit.

**Test expectation:** `tests/test_pre_push_gate.py::TestGateManifest::test_manifest_contains_required_gate_steps`
now asserts mypy is present; the existing `test_every_step_has_command / _has_label / _has_failure_hint`
loops already validate the new step's shape — no new test file needed. Full-suite green
(`uv run pytest`) plus a manual `uv run python plugins/saga/hooks/pre_push_gate_hook.py` dry-run
proving the 6-step gate runs mypy.

## Scope Boundaries

Out of scope:

- **The sagas-branch baseline fix** — already shipped in #317; this plan does not re-implement it,
  only routes it through the shared helper (KTD1) without behavior change.
- **Any `saga.py` runtime, hook logic, or saga storage-layout change** — the issue explicitly scopes
  this to test infrastructure and the gate manifest; the `pre_push_gate_hook.py` runner is unchanged
  (it already reads whatever steps the manifest lists).
- **Removing or weakening the guard** — its real job (catch test state leaking into the working tree)
  is preserved and now proven; U1 makes it precise, not looser.
- **Reconciling every other local↔CI gate difference** — only mypy is in scope. A broader
  gate-vs-CI parity audit is a separate exploration.

### Deferred Follow-Up Work

- **Close #314** once merged, noting in the close comment that the sagas-branch AC (#2/#3) was
  already satisfied by #317 and this PR completed AC#1 (proof-test) + AC#4 (legacy parity) + the
  mypy-gate comment scope.
- **Optional:** a single "gate manifest == CI job set" reconciliation test that diffs
  `gate-manifest.json` step ids against the CI workflow jobs, so future CI additions auto-flag a
  local-gate gap. Left out here to avoid coupling the manifest test to CI YAML parsing; worth an
  exploration issue if local↔CI drift recurs.
