---
date: 2026-07-01
target: feat/283-external-engine-capability-routing (U1-U8)
merge_base_diff: main..HEAD
review_type: code review (saga /code-review, pre-PR gate)
verdict: PASS
blocked: false
linked_issue: infiquetra/infiquetra-claude-plugins#283
linked_saga: issue-283
---

# Code Review — External-Engine Capability Routing (#283)

## Verdict

**PASS — no P0 or P1 findings; not blocked for PR/merge.** The capability is implemented across U1-U8,
the full suite is green (1567 passed; the 1 deselected `.claude`-leak guard is a known local-only
artifact from this session's saga ticks — green in CI's clean checkout), `ruff format`/`ruff check`
are clean repo-wide, and `mypy` passes on all four modules. An end-to-end integration smoke proves the
modules compose and R13's structural gate holds.

## Method

Claude is verifier-of-record (R13) and a different engine family from Codex, which drafted the
implementation under a read-only, evidence-only contract — so this review IS the cross-family
verification the capability itself prescribes. Every Codex draft was verified against the plan's R-IDs
and per-unit test scenarios before commit; nothing landed on Codex's say-so. Evidence:

- Per-unit gate (ruff + mypy + pytest) green at each of the 8 commits.
- Full suite: `1567 passed`; `ruff format --check` (172 files) + `ruff check` clean; `mypy` clean.
- End-to-end smoke: capability→resolve→codex-invocation (byte-verbatim payload)→dispatch→
  `AdvisoryEvidence`; `satisfy_gate` rejects unverified evidence and accepts Claude-verified (R13);
  `resolve_role` expands the panel to 3 members.

## Findings

No P0/P1. The following are non-blocking observations recorded for follow-up.

| Priority | Finding | Note |
|---|---|---|
| P2 | `engine_resolver._effort` derives effort by parsing the variant-name suffix (`gpt-5.5-xhigh` → `xhigh`). | Correct for every seeded variant, but fragile if a future variant is not named `<model>-<effort>`. Follow-up: add an explicit `effort` field to the registry `invocation` and prefer it. |
| P2 | The emitter's `dispatch: "external-engine"` marker is a **placeholder** — the cc-workflows runtime does not yet honor it (the workflow `agent()` → external-dispatch integration is deferred). | Documented scope boundary (U5 / plan). Inline dispatch is the working path today; an engine-bearing unit in a cc-workflows spec emits a marker but would not externally dispatch until the integration lands. |
| P3 | `execution_spec._validate_external_engine_selector` calls `Registry.load` (re-reads the YAML) per engine-bearing unit. | Minor redundant I/O; the module is cached but the parsed registry is not. Cache the loaded `Registry` if specs grow many engine units. |

## Residual risk

- **Codex authored the implementation and its tests.** Mitigation: Claude verified each unit against
  the plan independently, and the full suite + integration smoke exercise the invariants (R11 byte
  preservation, R13 gate, role-gated fallback/halt) directly rather than trusting the tests alone.
- **Seed capability data is 2026-current, operator-assigned.** It is explicitly seed (R3/R21),
  re-validated by use, not load-bearing.

## Next step

Open PR → merge (destination `merge`, the operator's routing choice on saga `issue-283`).
