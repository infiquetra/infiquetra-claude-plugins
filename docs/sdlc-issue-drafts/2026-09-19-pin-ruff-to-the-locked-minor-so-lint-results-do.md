---
title: Pin ruff to the locked minor so lint results do not depend on the resolver
repo: infiquetra-claude-plugins
type: defect
team: asgard
project: operations
labels: defect, needs-plan
risk: low
stage: Shaping
handoff_maturity: requirements-ready
---

# Pin ruff to the locked minor so lint results do not depend on the resolver

### Objective
Pin the declared ruff specifier in `pyproject.toml` to the locked 0.15 minor so a resolver
drift to a newer minor version cannot introduce lint findings in files nobody touched.

### Intent
Carried from the issue 1020 code review
(`docs/code-reviews/2026-09-19-issue-1020-board-vocabulary-code-review.md`, round three, P3
findings, "A toolchain caveat on the inner-loop claim").

`pyproject.toml:26` declares `ruff>=0.4`, while `uv.lock` resolves ruff 0.15.12 (verified via
`grep -n 'name = "ruff"' -A2 uv.lock`, which shows `version = "0.15.12"` at `uv.lock:1451`). A
reviewer environment that independently resolved ruff 0.16.5 flagged pre-existing issues in
`plugins/home-lab-ops` and some `docs/analysis` code blocks — files outside the issue-1020 diff —
while the project's synced 0.15.12 environment passed both `ruff check .` and
`ruff format --check .` clean. Both observations were true; the difference was version drift. An
open floor with no ceiling means continuous integration's lint gate can start failing on files
nobody touched the day a contributor's environment, or a future `uv sync`, resolves a newer minor.

### Out-of-scope / non-goals
- No change to any ruff rule configuration in `[tool.ruff]` or `[tool.ruff.lint]`.
- No fix to the specific ruff 0.16.5 findings in `plugins/home-lab-ops` or `docs/analysis`; those
  are a distinct, not-yet-triaged consequence of drift, not this card's target.
- No bump of any other pinned dev dependency (`safety`, `types-pyyaml`).

### Files expected to change
- `pyproject.toml`

### Tests to add or update
None new; the existing gate steps (`uv run ruff check .`, `uv run ruff format --check .`)
already assert the pinned version lints clean — this card only narrows the floor those steps run
against.

### Context library links
_none_

### Acceptance criteria
- [ ] `grep -n '"ruff' pyproject.toml` shows a specifier that pins the locked 0.15 minor (for example `ruff>=0.15,<0.16`), not `ruff>=0.4`.
- [ ] `uv sync --locked --extra dev` exits 0.
- [ ] `uv run ruff check .` exits 0.
- [ ] `uv run ruff format --check .` exits 0.

### Verification
```bash
grep -n 'name = "ruff"' -A2 uv.lock
grep -n '"ruff' pyproject.toml
uv sync --locked --extra dev
uv run ruff check .
uv run ruff format --check .
```

### Risk
low

One version specifier in `pyproject.toml`. The new pin matches what `uv.lock` already resolves,
so no dependency version actually moves and no lint rule changes — this only removes the gap
between the declared floor and the locked reality.

### Handoff maturity
requirements-ready

### Suggested next action
/plan docs/analysis/_filing-seeds/card2-ruff-pin.md

### Source context
- Source: docs/analysis/_filing-seeds/card2-ruff-pin.md
- Source type: local-file
- Source title: Pin ruff to the locked minor so lint results do not depend on the resolver

### Recommended Tier Band
opus/high

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/1043
- Number: 1043
- Created at: 2026-09-19T19:23:03.295697+00:00

