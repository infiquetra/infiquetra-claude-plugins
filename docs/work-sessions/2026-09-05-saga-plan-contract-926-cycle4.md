# P5 cycle 4 — documentation contract repair (#926)

The operator authorized this fourth repair cycle after the cycle-3 cap outcome at `b4ef1925`.
The worker resumed the existing issue-926 Saga Work thread inline. Independent review remains
coordinator-owned; no review acceptance is claimed. No push, PR, merge, board or issue write.

## U1 — smaller contract and behavior boundaries

Implemented the cycle-4 amendment in
[the decision record](../engineering-journal/DECISIONS.md#926-plan-save-contract-single-source).
The loader binds real options, enum placeholders, producer flags and effort mechanisms before
rendering. The edit-time tool has stable example groups, explicit checkout ownership, JSON
refusals, staged writes and rollback. Tests parse emitted facts independently, execute saves,
and exercise refusal/recovery, with one scheduled mutation per guard. The removed configuration
and rejected no-check alternative are recorded in the decision. The maintainer runbook is at
`plugins/saga/references/plan-save-contract.md`.

Focused validation: 118 tests passed across contract, routing, tier, packaging and canary modules.
Ruff and focused mypy passed. The byte audit against `a736c166` passed for entire §0.6, §5.0,
and §5.2a outside the permitted effort comment (including unchanged model/effort confirmation),
the five unrelated rows, both runtime files, and manifest/marketplace files.

## U2 — mutation receipts and final gate

In progress. Next: run the independent mutation matrix and canaries, record per-finding evidence,
commit the frozen revision, and run the full gate on that exact commit. Gate logs and its final
SHA receipt stay machine-local until reported so a post-gate documentation commit cannot make
the gate evidence stale.
