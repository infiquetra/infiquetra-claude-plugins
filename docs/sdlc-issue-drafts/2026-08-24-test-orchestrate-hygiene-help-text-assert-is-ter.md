---
title: test_orchestrate_hygiene help-text assert is terminal-width-brittle and blocks the pre-push gate in narrow environments
repo: infiquetra-claude-plugins
type: defect
team: asgard
project: operations
status: Shaping
labels: defect, needs-plan
risk: low
mode: actionable
handoff_maturity: requirements-ready
approval_state: needs_operator_approval
---

# test_orchestrate_hygiene help-text assert is terminal-width-brittle and blocks the pre-push gate in narrow environments

### Objective

Make `tests/test_orchestrate_hygiene.py::test_clean_all_help_and_docstring_name_run_state_retention`
width-stable so the saga pre-push gate stops failing on a rendering artifact in narrow terminal
environments.

### Intent

The test asserts the literal 48-character string `delete run state only when cleanup keeps no work`
appears in `orchestrate clean --help` stdout. argparse wraps help text to the terminal width
(`shutil.get_terminal_size`), so in environments narrower than roughly 62 columns the string wraps
across lines and the assert fails while the help content is correct and complete.

Concrete consequence, observed twice on 2026-08-24 during the #787 orchestration run: the saga
pre-push gate hook (`pre_push_gate_hook.py`) runs the full pytest suite in the session-hook
environment (~40 columns observed), so every `git push` from a Claude session or narrow Herdr pane
is blocked by this single false positive — 6,204/6,206 tests passing, one width wrap red. A
lens-accepted review revision (`1d07a97a`, PR #788) had to be pushed from a plain shell pane
out-of-band, and two full 7-minute gate runs were burned proving the same wrap. An in-scope failure
mode with a named boundary: the pre-push gate's terminal environment versus argparse rendering —
not a code defect in orchestrate itself.

Smallest fix: make the assertion width-stable — normalize the captured help text (collapse newlines
and indentation runs to single spaces) before asserting, or pin `COLUMNS` for the invocation via
monkeypatch. Harden any sibling help-text asserts in the same file the same way. Do not change the
help text and do not relax the gate.

### Out-of-scope / non-goals

- No change to `orchestrate.py` behavior or help wording.
- No change to the pre-push gate hook's steps or blocking semantics.
- No general terminal-width framework — this is a test-assert hardening only.

### Files expected to change

- tests/test_orchestrate_hygiene.py

### Tests to add or update

- tests/test_orchestrate_hygiene.py — the affected assert (and sibling help asserts in the same
  file) made width-stable; no new test files.

### Context library links

- Run record: issue #787 opening comment (run `orch-2026-08-24-787`, S0 preflight + ledger).
- First blocked push evidence: PR #788 (accepted revision pushed out-of-band).
- Gate: `plugins/saga/hooks/pre_push_gate_hook.py` (session PreToolUse hook running the suite).

### Acceptance criteria

- [ ] `COLUMNS=40 uv run pytest tests/test_orchestrate_hygiene.py -q` — expected: all tests pass
      at 40 columns (the wrap case).
- [ ] `COLUMNS=200 uv run pytest tests/test_orchestrate_hygiene.py -q` — expected: all tests pass
      at 200 columns (the unwrapped case).
- [ ] `git diff --stat` for the fix touches only `tests/test_orchestrate_hygiene.py` — expected:
      test-only diff, no plugin release surfaces required.

### Verification

```bash
COLUMNS=40 uv run pytest tests/test_orchestrate_hygiene.py -q
COLUMNS=200 uv run pytest tests/test_orchestrate_hygiene.py -q
git diff --stat HEAD~1
```

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: run orch-2026-08-24-787 S4 review evidence (issue #787 opening comment)
- Source type: local-file
- Source title: width-defect-body

### Recommended Tier Band
opus/high

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/792
- Number: 792
- Created at: 2026-08-24T09:18:21.420061+00:00

