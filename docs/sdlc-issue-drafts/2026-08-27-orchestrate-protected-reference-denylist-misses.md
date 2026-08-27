---
title: Orchestrate protected-reference denylist misses whitespace and case variants of refs/heads/ spellings
repo: infiquetra-claude-plugins
type: defect
team: asgard
project: operations
status: Shaping
labels: defect, needs-plan
risk: low
mode: execute
handoff_maturity: requirements-ready
---

# Orchestrate protected-reference denylist misses whitespace and case variants of refs/heads/ spellings

### Objective

Make `is_protected_remote_branch` classify every spelling of a protected reference as protected, so
the denylist guarding Orchestrate's only destructive capability does not depend on an encoding
accident elsewhere in the call path.

### Intent

`plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py:3401` peels the `refs/heads/` prefix
**before** stripping whitespace, and the peel is case sensitive:

```python
norm = branch.removeprefix("refs/heads/").strip()
```

A name with leading whitespace does not match the prefix, so the peel is a no-op and `norm` keeps
the `refs/heads/` prefix, which is not in the denylist. A name whose prefix differs in case fails
the same way. Four spellings of `main` are therefore **not** classified as protected:

| Input | Classified protected? |
| --- | --- |
| `"main"` | yes |
| `"MAIN"` | yes |
| `"refs/heads/main"` | yes |
| `"  main  "` | yes |
| `" refs/heads/main"` | **no** |
| `"refs/HEADS/main"` | **no** |
| `"Refs/Heads/main"` | **no** |
| `"\trefs/heads/main"` | **no** |

The same peel-before-strip ordering repeats at lines 3406, 3408, and 3410 for the run-branch,
resolved-branch, and base comparisons, so a run branch spelled with a stray prefix or leading
whitespace is likewise not recognised as its own protected reference.

**This is hygiene, not a live exploit.** The issue-844 review accepted it as a P3 because the
current `git ls-remote` and `git push` encoding does not turn those spellings into a real deletion
of `origin/main`. That is a property of the *caller*, not of this function. The denylist is the last
guard on the only destructive operation Orchestrate performs, and it should hold on its own terms
rather than by depending on how a caller happens to normalise a name today.

### Out-of-scope / non-goals

- Do not widen the denylist membership set. `main`, `master`, `head`, `develop`, `release`, `trunk`,
  the run branch, the resolved branch, and the base are the current members and stay the members.
- Do not change deletion eligibility, merged-pull-request proof, or ancestry proof. Those were
  settled by issue 844 and are not reopened here.
- Do not make the function reject valid unit branch names; `orch/<run>-<unit>` must stay deletable.
- Do not alter `clean --branches` behaviour, its read-back, or its refusal reporting.

### Files expected to change

- `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py`
- `tests/test_orchestrate_land_clean.py`
- Orchestrate release surfaces required by repository policy: `plugins/orchestrate/.claude-plugin/plugin.json`, `plugins/orchestrate/CHANGELOG.md`, `.claude-plugin/marketplace.json`

### Tests to add or update

Extend `tests/test_orchestrate_land_clean.py`:

- Parametrise `is_protected_remote_branch` over the spellings above and assert every one is
  protected, including a leading space, a leading tab, `refs/HEADS/`, and `Refs/Heads/`.
- Assert the same normalisation applies to the run-branch, resolved-branch, and base comparisons at
  lines 3406, 3408, and 3410, not only to the literal denylist.
- Assert an ordinary unit branch such as `orch/orch-2026-01-01-x-u1` remains **not** protected, so
  the fix does not make legitimate cleanup impossible.
- Mutation-prove the new coverage: restoring the peel-before-strip ordering must fail the new
  assertions. A test that passes both before and after proves nothing.

### Context library links

- Origin finding: F-04, issue 844 Code Review cycle 2, accepted as a P3 residual
- Parent campaign closeout: issue 847 closeout comment, "Residual" section
- Current implementation: `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py:3399-3410`
- Sibling guard settled by issue 844: `prove_remote_branch_merged`
- Repository release procedure: `CLAUDE.md`, "Development Workflow" step 6

### Verification

```bash
uv run pytest tests/test_orchestrate_land_clean.py -q
uv run ruff check plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py tests/test_orchestrate_land_clean.py
uv run ruff format --check .
uv run python -m mypy plugins/ scripts/ tests/ --ignore-missing-imports
GATE_LOG_DIR=/tmp/gate-run bash scripts/gate.sh > /tmp/gate.log 2>&1
cat /tmp/gate-run/result.txt
```

### Acceptance criteria

- [ ] Whitespace is stripped and the name is casefolded **before** any `refs/heads/` peel, and the
      peel itself is case insensitive.
- [ ] All four currently-escaping spellings classify as protected.
- [ ] The run-branch, resolved-branch, and base comparisons use the same normalisation.
- [ ] An ordinary `orch/<run>-<unit>` branch remains deletable.
- [ ] New assertions fail against the current peel-before-strip ordering.
- [ ] `bash scripts/gate.sh` exits 0 and Orchestrate release surfaces stay aligned.

### Notes / conventions

Suggested repair, recorded by the reviewer: strip, then casefold the full name, then peel any
`refs/heads/` prefix in any case, before the allow or deny compare. Keep the change confined to
normalisation; the membership set and the deletion-eligibility logic are already settled.

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/874
- Number: 874
- Created at: 2026-08-27T00:52:21.197419+00:00

