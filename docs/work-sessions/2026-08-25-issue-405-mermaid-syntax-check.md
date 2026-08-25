# Work session — U2 always-on Mermaid syntax check (#405)

- **Thread:** saga `issue-405`, `lifecycle_phase=work`
- **Branch:** `orch/orch-2026-08-25-814-u-405`
- **Destination:** pr
- **Execution backend:** inline — plan frontmatter `backend: inline`; not re-offered
- **Engine:** none — stored work preference, and the unit instruction

## What was built (U2)

CI now parses every tracked ```` ```mermaid ```` fence through mermaid's own parser and fails on syntax errors, naming file and line. `scripts/gate.sh` covers the new step by exact name.

## Key decisions

- Headless `mermaid.parse()` + jsdom (pinned mermaid 11.17.1, jsdom 30.0.1). No mermaid-cli fallback (plan KTD2 / doc-review F6).
- Enumerate with `git grep -l -F '```mermaid'` then extract real fences in Python so prose mentions are not parsed.
- Node/npm missing locally is gate exit 3, matching the existing missing-dev-dependency precondition.
- Worker sessions do not write the board (plan R7 — the orchestrating session is the single writer).
- No `/code-review` in this unit — the run's Saga Code Review session reviews the frozen head.
- Current tree: 14 real fences across 11 files, all already valid; no diagram repairs.

## Files modified

- `scripts/check_mermaid.py`
- `scripts/mermaid/package.json`, `package-lock.json`, `parse.mjs`, `.gitignore`
- `scripts/gate.sh`
- `.github/workflows/ci.yml`
- `tests/test_check_mermaid.py`
- `docs/engineering-journal/LEARNINGS.md`, `docs/engineering-journal/DECISIONS.md`
- `docs/work-sessions/2026-08-25-issue-405-mermaid-syntax-check.md`

## Checks run

- `uv run pytest tests/ -k mermaid -q` — 9 passed (7 in `tests/test_check_mermaid.py`; 2 incidental `-k mermaid` matches elsewhere)
- `uv run python scripts/check_mermaid.py` — `check_mermaid: 14 mermaid fence(s) parsed`
- `GATE_LOG_DIR=/tmp/gate-u-405 bash scripts/gate.sh` — `GATE GREEN — 25 steps ran, 0 blocking failures, 0 uncovered.` Mermaid syntax check was step 22; coverage self-check counted it (no `GATE INCOMPLETE`).

## Next step

Open the PR for #405 and freeze the head for the run's Saga Code Review unit.
