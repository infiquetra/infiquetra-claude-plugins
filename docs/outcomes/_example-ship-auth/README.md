# Example: a generated outcome report + projection (U8)

These two files are **generated samples** of the OutcomeOrchestrator's derived-on-read surfaces (U8),
committed here so the output shape is reviewable without running an outcome:

- [`report.md`](report.md) — the `/outcome report` digest (R19/F6): Mermaid topology, the consolidated
  attention prompt (R18/AE5 — type-tier first, then unblock-leverage), the per-subplot state + evidence +
  cost table, the cost rollup (`no data yet` until U10 populates realized cost), and the decision trail.
- [`projection.json`](projection.json) — the `/outcome project` mission-control **secondary** view (R25):
  generated from the spec + store, no operator-writable status, never auto-closes the parent.

Both are **regenerated from state** by `scripts/outcome_report.py` / `scripts/outcome_projection.py` —
never hand-edited, so they physically cannot drift from the truth. A real outcome's files live under
`docs/outcomes/<outcome-id>/` on the outcome's own branch; the `_`-prefix marks this directory as a
static documentation example, not a live outcome.
