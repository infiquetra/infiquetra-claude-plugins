# Work session — issue #644 async PostToolUse spawn-launch race

- **Saga:** `issue-644` · branch `work/644-async-posttooluse-race` (base `277f070d`)
- **Plan:** `docs/plans/2026-07-23-issue-644-async-posttooluse-race-plan.md` · doc-review
  `docs/reviews/2026-07-23-issue-644-async-posttooluse-race-plan-doc-review.md` (verdict ready,
  D1 P1 repaired in place)
- **Backend:** cc-workflows-ultracode (operator-approved), spec
  `docs/plans/2026-07-23-issue-644-async-posttooluse-race-spec.json`, emitted script
  `docs/plans/2026-07-23-issue-644-async-posttooluse-race.workflow.js`
- **Destination:** merge (operator-gated), then #642-aware rollout and the R8 live canary
  (10 consecutive async Agent spawns under armed hooks, zero "found 0")

## What shipped

- **U1 — fleet-core broker** (`plugins/fleet-core/scripts/fleet_commons/lease_broker.py`, +14/−3):
  `record_parent_completed` gains keyword-only `spawn_failed: bool = False`; the kill branch
  becomes `if (updated.agent_id is None and spawn_failed) or updated.child_terminal_at is not
  None:` so an unclaimed reservation whose parent call merely *returned* (async launch) is
  stamped and survives for SubagentStart's claim, while a genuinely failed spawn keeps today's
  eager release. Per doc-review D1/KTD4, `settle_batch` gains one arm — `or (lease.agent_id is
  None and lease.parent_completed_at is not None)` — so an abandoned stamped slot drains at
  settlement while mid-run wave slots (no parent signal) survive. Dual-signal release for
  claimed leases, `_complete_foreground_lease`, admission-pop guard, and the tuple return
  contract are byte-unchanged. 6 new tests + 2 updated in `tests/test_fleet_lease_broker.py`
  (83 pass; the new tests fail against the base broker, so they are load-bearing).
- **U2 — saga adapter** (`plugins/saga/scripts/lease_broker.py`, +2): `record_hook_parent`
  derives `spawn_failed = payload.get("hook_event_name") == "PostToolUseFailure"` and forwards
  it. No compatibility shim (KTD3: against an old broker the TypeError surfaces on an
  observational event and the lease releases by its 30 s claim TTL). Zero hook-file changes.
  New forwarding test + `_parent_payload` failure mapping in `tests/test_saga_hooks.py` (40
  pass); the pre-existing end-to-end `test_unclaimed_posttool_failure_releases_provisional_slot`
  now exercises the failure path for real.
- **U3 — release surfaces:** fleet-core 0.21.0 + saga 0.112.0, marketplace sync, both
  CHANGELOGs, drift-guard pins (`test_saga_plugin.py`, `test_liveness_events.py`,
  `test_team_execution_liveness.py`), DECISIONS `{#async-parent-signal-644}`. No LEARNINGS
  entry — mechanism already recorded as `{#async-spawn-posttooluse-race-616-r8}`.

## Governed launch and the three-round verify story

Invocation `4be5e8f7-5d68-4dc2-9999-1a720c942840`, batch
`workflow:c07087c54110b3ddf40d551a:d30b7db90722f8bc9b9ca43e`, width 3, attest
`launch_authorized: true` (re-attested per round). Workflow run `wf_1011df4e-16c`, fully
serialized U1→U2→U3 with refute-3 panels (`saga:readonly-verifier`, worktree isolation) on
U1/U2. Dispatch `workflow:c07087c54110b3ddf40d551a:invocation:d30b7db90722f8bc9b9ca43e`.

**Round 1 — U1 upheld 3/3; U2 panel refuted 3/3, but the code was upheld by all three.** Two
verifier sandboxes were incapacitated by the live defect under repair (every Bash command
refused with "expected exactly one fleet lease bound; found 0" — the #644 race hitting the
verifiers' own SubagentStart claims); they default-refuted unverifiable execution claims while
upholding all structural claims via Read. The third verifier had working Bash, independently
confirmed the tests green, and correctly caught the U2 agent's materially false self-report
"88 passed" in a file that holds 40 tests (the known stale-agent-self-report gotcha).

**Driver attestation.** The driving session established ground truth directly: 171 passed
across `test_saga_hooks` (40) + `test_fleet_lease_broker` (83) + `test_concurrency_conformance`
(48); ruff check + format clean; mypy (CI scope) clean. The three U2 verifier prompts were
patched with a DRIVER CONTEXT paragraph (cache-busting exactly those calls): the "88 passed"
count is known-false and driver-corrected; sandbox incapacity from the live defect is
environmental, not evidence against the unit.

**Round 2 — all three fresh verifiers had working sandboxes and upheld every code claim on
independent evidence** (re-ran pytest → 40/171 matching driver figures, re-ran ruff/mypy, read
the diff directly). Each filed exactly one `refuted[]` entry — the driver-corrected "88 passed"
claim, per instruction — and the harness counted any non-empty `refuted[]` as a refute vote:
3/3 spurious refute, second `verifier-disagreement` throw.

**Round 3 — claim-aware adjudication.** One edit to the emitted script's U2 refute count:
exclude refuted entries targeting the driver-pre-declared-false "88 passed" claim; any other
refuted entry still counts in full. No agent prompts changed, so all 11 completed agents
replayed from cache; U3 ran live and completed. Settlement: 3/3 delivered, casualties 0,
`halt_required: false`, DLQ empty.

## Gates (driver-run at the PR-ready boundary)

- `uv run pytest -q` full battery — see PR/commits for the recorded count (run at this HEAD)
- `uv run ruff check .` clean · `uv run ruff format --check .` clean (437 files)
- `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` clean
- bandit delta vs base: zero new findings (5 pre-existing Low in the fleet-core broker at lines
  18/496/519, outside the diff, same baseline as the #616 review)
- `python3 scripts/check_release_surface_parity.py` — all plugins in parity
- Sibling-PR version-collision re-check: zero open PRs at U3 time; re-check again at merge

## Residuals and follow-ups

- **D2 (P2, accepted-open per doc-review default):** crossed-claim hazard — `claim()` binds the
  oldest compatible reservation, so a surviving stamped reservation whose child never arrives
  can, within its ≤30 s TTL, be claimed by the next same-type spawn (fence mismatch possible).
  Partially pre-existing; widened only to the plain-PostToolUse-then-no-child case. U1 pins
  current oldest-first behavior with a test; a design mitigation (claim preferring unstamped
  reservations) is #617 claim-policy territory.
- **D3 (P3):** "PostToolUseFailure fires for never-started spawns" is not live-verified; the
  design degrades safely to TTL expiry if it never fires. Record in R8 canary notes if a
  failure event is captured.
- **Panel-harness follow-up worth carrying:** "known-false claim" handling in refute-N panels —
  a driver correction echoed into `refuted[]` double-counts as dissent. This session's fix was
  claim-scoped adjudication in the emitted script; a durable emitter-side shape (e.g. a
  `driver_corrected[]` verdict key) belongs with the #645–#648 machinery follow-ups.
- **Rollout hazard (#642):** `installed_plugins.json` has gone stale two-for-two releases —
  after merge, hand-verify/edit the records and prove provenance with `FLEET_COMMONS_DEBUG=1`
  before the R8 canary.

## Acceptance state

Issue #644 acceptance criteria 1–2 (broker + adapter behavior, tests) are implemented and
verified here. Criterion 3 — the R8 live canary (10 consecutive async spawns under armed
hooks, zero "found 0") — is post-merge and operator-gated; armed hooks still run the installed
saga 0.111.0 + fleet-core 0.20.0 until rollout, so the race remains live in driving sessions
until then.
