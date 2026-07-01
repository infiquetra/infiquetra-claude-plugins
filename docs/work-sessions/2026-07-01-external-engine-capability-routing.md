# Work session — External-Engine Capability Routing (#283)

**Date.** 2026-07-01. **Branch.** `feat/283-external-engine-capability-routing`. **Destination.** merge.
**Backend.** inline. **Plan.** `docs/plans/2026-07-01-external-engine-capability-routing-plan.md`.

Built the saga-owned external-engine capability routing capability (U1-U8), **dogfooding Codex as the
delegated coder**: every code unit was drafted by Codex running read-only (`codex:codex-rescue`,
evidence-only, zero tree writes), then verified against the plan's R-IDs, gated (`ruff`/`mypy`/`pytest`),
and committed by Claude as sole-committer (R13). The build is thus a live instance of the very
delegation path the capability formalizes.

## What shipped (by unit)

- **U1** `engine_registry.py` + `engine-registry.yaml` skeleton — registry loader/validator, KTD9 tie-break.
- **U2+U3** `engine_resolver.py` — `resolve()` (capability XOR engine, advisory/dispatch, role-gated
  fallback/halt, byte-verbatim payload, fitness halt) + `preflight()`.
- **U4** `engine_dispatch.py` + `engine-dispatch.md` — `AdvisoryEvidence` + `satisfy_gate` (R13
  structural), codex/agy invocation builders, failure→halt+provenance.
- **U5** `execution_spec.py` — mutually-exclusive `engine`/`capability` Unit selectors + emitter marker.
- **U6** `resolve_role`/`panel_halt` + doc-review opt-in panel (R16).
- **U7** seed capability data (4 variants, per-row source attribution).
- **U8** DECISIONS.md decision record + saga 0.44.0 release surfaces.

## Codex delegation scorecard — how well Codex did

The **fix-delta** (what Claude had to change to make the draft correct + pass the gate) is the signal.

| Unit | Effort | Codex logic quality | Fix delta | Verdict |
|---|---|---|---|---|
| U1 registry | high | Strong — correct first try, repo-idiomatic; inferred the KTD9 tie-break | Trivial: import-sort + 1-line `int()` cast; reconstruct (bad hunk count) | ✅ |
| U2 resolver | xhigh | Strong — full contract correct; used the exact sibling-import idiom | mypy `int()` cast; fixed an `autouse` fixture shadowing 3 preflight tests | ✅ |
| U3 preflight | (w/ U2) | Strong — injectable probes, no live call | folded into U2 | ✅ |
| U4 dispatch | high | Excellent — read `agy_delegate.py` + matched the real envelope; R13 `satisfy_gate` + byte-preservation correct first try | none beyond standard reconstruct | ✅ |
| U5 spec field | high | Strong logic — purely additive, found all 3 emitter sites, emitter suite regression-free | heavy **diff-application** (bad hunk counts + stripped blank lines) → `git apply --reject` landed 8/10, hand-applied 2 emitter hunks. Zero logic/type fixes | ⚠️ delivery |

**Consistent finding across all units:** Codex's *implementation logic was correct on every unit*
(all tests passed on first draft after trivial lint/type fixes). The fix-deltas clustered in two
non-logic places:

1. **Diff-envelope integrity** — Codex miscounts unified-diff hunk line-counts and blank context lines
   get stripped to empty. For **new files** this is harmless (reconstruct file bodies from the `+`
   lines, ignore hunk headers). For **modifications to large existing files** it defeats `git apply`,
   `git apply --recount`, and `patch -F3`; the reliable salvage is `git apply --reject` + hand-applying
   the rejected hunks via Edit.
2. **Test fixtures** — the subtle errors were in test *scaffolding* (an `autouse` fixture that shadowed
   the function under test with a mock), not in the code under test. These pass locally in a
   self-hiding way, which is exactly why a Claude verification gate is required.

**Operational rule for read-only Codex delegation:** prefer **new-file** unit boundaries (clean
reconstruct); when a unit must modify a large existing file, expect `--reject` + hand-finish, and
always run the *existing* suite (not just the new tests) to catch regressions.

**Codex plugin robustness note:** one early rescue job failed in 6s parsing a `file:line` reference
(`agy_delegate.py:1519-1542`) from the prompt as a `--model` flag — the forwarder's flag extraction is
fragile with colon/line-range tokens.

## Checks run

`ruff format --check` (172 files clean) · `ruff check` (clean) · `mypy` (4 modules clean) ·
`pytest` (1567 passed; 1 deselected known-local `.claude`-leak guard) · end-to-end integration smoke
(resolve→dispatch→satisfy_gate + panel expansion) PASS.

## Next step

Open PR and merge; then `/qa` (advisory) and `/retro` to promote the Codex-delegation learnings.
