# Code Review — /outcome attend issue-backed handoff (#491)

**Target:** branch `feat/491-attend-issue-backed-handoff` (diff `main..HEAD`, merge-base `5f4bd41`)
**Reviewed SHA:** `5a92695`
**Mode:** programmatic (pre-PR gate)
**Linked issue:** infiquetra/infiquetra-claude-plugins#491
**Plan:** `docs/plans/2026-07-06-outcome-attend-issue-backed-handoff-plan.md`
**Work session:** `docs/work-sessions/2026-07-06-outcome-attend-issue-backed-handoff.md`
**Blocked:** No — the adversarial panel found 4 P2/P3 gaps; all were fixed and re-verified before this gate closed.

## Verdict

Safe to merge. Scope CLEAN, full suite green (2348 passed pre-hardening; command/completion/integration
74 green post-hardening), and the one adversarial verifier's findings were addressed in commit `5a92695`.

## Scope check: CLEAN

- **Intent:** `/outcome attend` must emit the leaf's real `issue-<N>` saga id, not the dispatcher's raw
  `leaf-<outcome>-<subplot>` handoff.
- **Delivered:** exactly that, `attend`-only. `outcome_report.py` correctly untouched (it never emitted
  the handoff). No unrelated changes.

## Plan-completion audit

| U-ID | Deliverable | Status | Evidence |
|---|---|---|---|
| U1 | `_leaf_handoff_id` resolver + `attend` fix | DONE | `outcome.py` +resolver/attend; `test_outcome_command.py` resolver + attend e2e tests |
| U2 | release surface (0.72.0) + journal | DONE | `plugin.json`/`CHANGELOG`/`marketplace.json`/`test_saga_plugin.py`/`DECISIONS.md` |

## Findings (all resolved before merge)

The adversarial verifier (`saga:readonly-verifier`, worktree, executing counterexample probes) refuted
the resolver's R3 contract with 4 concrete cases. All are **unreachable in production** (GitHub issue
numbers are always ≥1; `Node.github` is always a dict via `from_dict`) → **P2/P3, non-blocking** — but
each violated the resolver's documented "positive number or fall back; never raise" contract, so all were
fixed in `5a92695`.

| # | Finding | Sev | Fix | Re-verified |
|---|---|---|---|---|
| 1 | `sub_issue=0` → `issue-0` (dead pointer) | P2 | `_positive_int_str` rejects non-positive | → `RAW` |
| 2 | `sub_issue=-5` → `issue--5` | P2 | same | → `RAW` |
| 3 | `issue="o/r#0"` → `issue-0` | P2 | same coercion on the parsed path | → `RAW` |
| 4 | non-dict `github` → `AttributeError` | P3 | `isinstance(node.github, dict)` guard | → `RAW`, no raise |

Each case has a dedicated regression test (`test_leaf_handoff_id_hardening_non_positive_and_non_dict`).

## Upheld (survived refutation)

Float/garbage/empty/`None` `sub_issue` fall back safely; whitespace-padded numeric strings parse;
`owner/repo#N` and full-URL issue refs resolve to `issue-<N>`; `sub_issue` deterministically precedes
`issue` (KTD1); `attend` end-to-end emits `/resume issue-<N>`, still raises on a not-dispatched subplot,
and is **read-only** (byte-identical repo tree before/after).

## Coverage

- Gates: full suite 2348 passed / 1 skipped (pre-hardening); post-hardening command/completion/integration
  74 green; `ruff` clean; `mypy plugins/ scripts/ tests/` → no issues (149 files); `bandit` rc=0;
  release-surface diff guard green.
- Residual risk: low. The whole surface is a pure resolver + a read-only `attend` load.

## Route

Clean (findings fixed) → PR-ready. Recommend opening the PR and squash-merging on green CI.
