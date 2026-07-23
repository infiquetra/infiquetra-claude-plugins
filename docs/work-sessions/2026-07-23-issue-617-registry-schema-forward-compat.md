# Work session — issue #617 registry schema forward-compatibility

- **Issue**: infiquetra/infiquetra-claude-plugins#617 (defect, high-priority) — fleet-lease registry
  has no schema forward-compatibility; one newer write bricks every older reader fleet-wide
  (`RegistryCorruptError` from `_closed_mapping` on any unknown key; struck 2026-07-17 and
  2026-07-22, LEARNINGS `{#broker-schema-forward-poisoning-616}`).
- **Saga**: `issue-issue-617` · branch `work/617-registry-schema-forward-compat` · base `4eb2fe15`
  (= main at cut) · destination merge · outcome `governed-execution-integrity` leaf sub-617.
- **Plan package**: `docs/plans/2026-07-23-issue-617-registry-schema-forward-compat-plan.md` +
  spec (3 units) + doc-review (verdict ready, advisories D1/D2 discharged in-unit, see below).
- **Backend**: cc-workflows-ultracode (operator override of the team-execution recommendation,
  recorded at plan time) — run `wf_ea848fca-97c`, invocation `997992b3-d10f-4ac6-a62e-aa8dab157928`,
  fully serialized U1→U2→U3, refute-3 panels at unit tier on U1/U2.

## What shipped (working tree, pre-PR)

- **U1 — broker tolerance layer** (`plugins/fleet-core/scripts/fleet_commons/lease_broker.py`):
  `_tolerant_mapping` returning `(known, extras)` beside the verbatim strict `_closed_mapping`;
  per-dataclass `extras` capture at `from_dict` and merge-last at `to_dict` on Registry, Lease,
  ResourceFence, SessionAdmission, SettlementRecord (outer record only), OwnerAdmissionClose;
  64 KiB total-extras-per-document cap summed across all records → `RegistryCorruptError`;
  digest-covered commitment records strictly closed with audit comments at every carve-out site
  (`validate_settlement_close`, `_validate_legacy_settlement_close`, worktree
  `canonical_resource_ref`, `FencingToken` — audited, kept closed per D1); four legacy migration
  arms, schema-identity gate, capacities, and invariants semantically untouched; extras-free
  output byte-identical (R5). Ten new/repurposed tests in `tests/test_fleet_lease_broker.py`.
- **U2 — doctor/repair verbs**: broker methods `doctor()` (read-only report: valid |
  tolerated-unknowns | corrupt, extras inventory with JSON paths; never mutates) and `repair()`
  (timestamped backup, strip extras, strict revalidate, atomic 0600 write, refuses when strict
  revalidation still fails, explicit no-op on clean); saga adapter CLI verbs `doctor` (exit
  0/3/4) and `repair` (requires `--strip-unknown`) in `plugins/saga/scripts/lease_broker.py`.
  11 new tests (7 broker-method + 4 CLI-seam in `tests/test_saga_hooks.py`).
- **U3 — release surfaces**: fleet-core 0.21.0→**0.22.0**, saga 0.112.0→**0.113.0**, marketplace
  sync, CHANGELOGs (doctor exit codes 0/3/4 stated explicitly per D2), drift-guard pins updated
  (`test_saga_plugin.py`, `test_liveness_events.py`, `test_team_execution_liveness.py`),
  DECISIONS `{#registry-forward-compat-617}` incl. the mid-run reload writer-swap hazard note
  (documented-not-built). No new LEARNINGS entry (conditional honored — nothing beyond
  `{#broker-schema-forward-poisoning-616}`).

Diff vs base: 13 files, +1018/−27, exactly the spec-declared surfaces.

## Machinery incident: false 3/3 refutation of U1 (operator-adjudicated resume)

The first run segment halted with `verifier-disagreement: U1 refuted by 3/3`. Adjudication from
the run journal showed a **false halt**: all three `saga:readonly-verifier` seats upheld every
implementation claim by direct file reading and refuted only the builder's "92/92 pass / ruff /
mypy clean" execution metric — because the fleet-lease PreToolUse hook blocked every Bash command
in their seats ("expected exactly one fleet lease bound; found 0"). The worktree-isolated verifier
children could not claim the width-1 reservation that the primary-tree U1 builder bound without
issue; the reservation schema (`workflow_lease_reservation.v1`) carries no isolation declaration.

- **Mechanism evidence**: differential — primary-tree builder bound and ran gates; all three
  worktree verifiers refused. Matches the pre-existing draft
  `docs/sdlc-issue-drafts/2026-07-23-defect-fleet-worktree-declared-reservation-claim.*`; the
  tally gap (three "cannot execute" abstentions counted as three refutations) is the #648
  panel-validity enhancement territory. Both now have a live reproduction in run
  `wf_ea848fca-97c` (journal, verifier entries 2–4).
- **Driver adjudication** (operator-approved recovery "Resume, driver-adjudicated panels"): the
  refuted execution claim was verified true driver-side (92/92 broker tests; full battery 5396
  passed / 0 failed / 1 skipped at the U1 tree; ruff check+format clean; mypy clean). The
  workflow script's panel tally was amended — logic only, agent calls byte-identical so cached
  results replayed — to classify refuted entries that are *solely* execution-visibility gaps as
  abstentions for driver adjudication; static file-read refutations retain full force and still
  halt. The classifier was validated against the three cached verdicts before relaunch.
- **Settlement integrity**: attempt 1 settled honestly (U1 delivered `cfc96d00…`, U2/U3
  `silent-no-op` casualties, cohort `halt_required: true`); U2/U3 claimed from the dead-letter
  queue as attempt 2 under the same idempotency keys; attempt 2 settled delivered (U2
  `4fb1a9cb…`, U3 `519f01ce…`), `halt_required: false`, queue empty. Lease batch re-reserved,
  attested, and released clean after each segment.
- **U2 panel**: three verifiers reported, zero refuted entries (6–7 upheld claims each); U2's
  execution claims adjudicated driver-side via the whole-repo gate battery below.

## Gates (driver-run at the post-U3 tree)

- Full pytest battery: 5407 passed, 0 failed, 1 skipped (post-U3 tree; U1-tree run earlier:
  5396 passed / 0 failed / 1 skipped).
- `ruff check .` clean; `ruff format --check .` **correction**: recorded clean here at the
  post-U3 tree, but the committed `4b0a0ae7` actually failed it (one over-wrapped assert in
  `tests/test_saga_plugin.py` from the U3 builder). Caught and fixed in the review-repair
  commit; the gate record above was wrong at time of writing.
- `mypy plugins/ scripts/ tests/ --ignore-missing-imports` clean (exit 0).
- Bandit delta vs base on the two changed production files: zero new findings (5 pre-existing
  Low, identical at base and HEAD).
- `check_release_surface_parity.py`: all plugins in parity.

## Code review (Phase 5, programmatic) — round 1 blocked, repaired

Review at `4b0a0ae7` (base `4eb2fe15`): three opus lenses (correctness+reliability,
security+integrity, testing+release-surfaces; `saga:readonly-verifier` + worktree), Stage A
merged 4 raw findings, Stage B validated 4/4 (one adversarial validator per finding). Verdict
**blocked** — artifact
`docs/code-reviews/2026-07-23-issue-617-registry-schema-forward-compat-code-review.md`, ledger
`code-review:blocked` at `4b0a0ae7...`.

- **F1 P1 (validated 96, live repro)**: `_commit_settlement_locked` rebuilt the CAS-verified
  fence with a bare constructor, silently dropping preserved extras — the exact KTD2/R1
  newer-writer data-loss hazard. Fixed with `replace(head, close_receipt=close)` + a
  prepare→commit regression test over an extras-carrying fence.
- **F2 P3 (85)**: archived closed-fence sidecars parsed outside the KTD5 cap (a regression —
  pre-#617 this channel failed closed) plus a 64 KiB single-read truncation edge. Fixed with a
  bounded EOF read (`_MAX_ARCHIVED_FENCE_BYTES` = 4x cap) + per-record extras cap; three-leg
  regression test.
- **F3 P3 (90)**: doctor CLI exit map defaulted an unmapped status to 0 (fail-open, latent).
  Default now 4; mapping test pins the branch; CHANGELOG wording updated.
- **F4 P3 (92)**: the R5 byte-identity test was self-referential (passes unmodified against the
  base broker). Added a golden pin: SHA-256 of the base-broker (`4eb2fe15`) document for the
  deterministic fixture, verified identical to the tolerant broker's output (`fb0bc764…`, 2925
  bytes).

Repair commit `62c88cad` (also carries the `test_saga_plugin.py` format fix and CHANGELOG
amendments). Gates at the repaired tree: full battery **5410 passed / 0 failed / 1 skipped**,
ruff check + format clean (437 files), mypy exit 0, bandit delta zero (same 5 pre-existing
Low), parity clean. Round-2 delta adjudication: opus verifier over `4b0a0ae7..62c88cad` —
see the code-review artifact for the outcome.

Machinery note: two lens seats and two validators hit fleet-lease hook HALTs on Bash mid-run
(the known worktree-reservation-claim gap; token expiry) and fell back to Read-tool static
verification; F1's validator retained Bash and live-reproduced the defect. Review spend: 3
lenses (~243k tokens) + 4 validators (~156k) + 1 delta adjudicator, all within the 3-concurrent
cap.

## Spend / telemetry

Two run segments, 9 agent seats total: first segment 4 agents (~400k subagent tokens, ~22 min),
resumed segment 5 live agents (~367k tokens, ~22 min) with U1 and its panel replayed from cache. Engine offer at Phase 1.5 was advisory-only second-opinion intent; not dispatched
(refute-3 panels fill the adversarial role; backend operator-locked at plan time).

## Follow-ups (not this PR)

- Worktree-reservation-claim defect draft → file as an issue with the `wf_ea848fca-97c`
  reproduction attached (verifier seats lease-blind under armed hooks).
- #648 verifier-health panel-validity: this run is the concrete false-halt case (3/3
  execution-abstentions tallied as refutations; casualty threshold 0 halted the run).
- #642 installed-plugins registry hand-repair remains a mandatory rollout step post-merge.
- R10 live acceptance (backup live registry → inject synthetic field → doctor/repair round-trip
  under armed hooks) — operator-gated, post-merge.
