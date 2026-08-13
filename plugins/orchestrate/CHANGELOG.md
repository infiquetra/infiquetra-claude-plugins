# Changelog

## [0.3.0] - 2026-08-13

### Added

- Launch children through the `agent` wrapper's control-only path after validating its dry-run
  working directory and Herdr workspace. Launch intent and a run-bound task label are durable
  before the side effect, and interrupted launches recover by discovering that label.
- Resolve model and effort through fleet-core's runtime adapter. Qwen's in-session effort command
  is sent after launch and accepted only after its own acknowledgement is observed.
- Classify readiness through a nonce-bound `pane.output_matched` interaction whose complete
  sentinel never appears in echoed dispatch input. Trust prompts are surfaced before dispatch,
  and a launch without a child-produced sentinel remains not-ready.
- Repair the subscriber's inert cross-counter revision guard. A captured live output-match event
  proves protocol 19 reports `read.revision=0`; the event envelope is now schema-validated through
  the production decoder instead of being discarded as stale.
- Provision mutating children in branch worktrees with an explicit environment-setup step; keep
  read-only children in the ambient checkout. Committed branch and ambient-checkout changes plus
  repository-visible uncommitted changes are checked against scope independently of predicate
  success; Git-ignored paths are documented as outside this control.
- Record reaping before closing a Herdr tab and distinguish a recorded reap from an unexplained
  disappearance.

### Fixed

- Correct Herdr pane-read argument ordering and pin every command-line adapter shape with an
  argv-validating executable test double.
- Fix launch, command-line observation, socket observation, and register state to the same default
  Herdr session instead of exposing a partly routed named-session option.
- Record the branch base before worktree creation, detect committed and ambient-checkout escapes,
  and write the planned register row before worktree or environment side effects.
- Centralize echo-safe sentinel instructions, enforce dry-run preview mismatches, diagnose Qwen's
  disabled-thinking acknowledgement, and remove the withdrawn revision-baseline schema wiring.

### Not in this release

- Predicate implementations, the integration gate that authorizes live reaping, spend and
  concurrency admission, hang detection, mirror behavior, and the `/orchestrate` command.

## [0.2.2] - 2026-08-13

### Fixed

- Reject output-match subscriptions that cannot produce a complete substring sentinel instead of
  starting a subscriber that can only discard their events. Multiple valid sentinel interactions
  for the same pane remain independently matchable.
- Report catch-up failures without closing an accepted event stream, and count every accepted
  subscription toward reconnect limits even when its catch-up fails.
- Record how each lifecycle state was learned, including explicit inference labels for a missing
  snapshot pane and a closed tab.
- Avoid register locking for an empty catch-up batch and avoid waking for registered events that
  make no register change.
- Exercise schema-valid pane and agent payloads through the response parser and catch-up consumer.

## [0.2.1] - 2026-08-13

### Fixed

- Unwrap `session.snapshot` from Herdr's real `result.snapshot` response shape, now validated
  end-to-end against the committed success-response schema through a Unix-socket test.
- Resolve `tab_closed` through registered `tab_id` values, and record pane/tab terminal events as
  `exited` before waking the orchestrator.
- Fail fast when the subscriber's first socket connection cannot open; its register row now records
  `exited` and the command returns non-zero instead of retrying forever as `working`.
- Compare sentinel purpose and nonce as well as run and child identity, so an earlier dispatch or a
  readiness marker cannot satisfy a later completion interaction.
- Batch reconnect catch-up updates into one register rewrite and reset once-only diagnostics at
  each accepted connection.
- Clarify that the three subscription-event broadcasts remain dotted even though the 26 general
  broadcast events are underscored.

## [0.2.0] - 2026-08-13

### Added

- A strict protocol 19 event client for `~/.config/herdr/herdr.sock`. It emits dotted
  `events.subscribe` request types, rejects underscored broadcast names and malformed entries, and
  verifies the `subscription_started` acknowledgement before dispatching events.
- A single-purpose tracked subscriber process that holds the socket across turns and wakes the
  orchestrator pane through `agent.prompt`.
- Startup and reconnect catch-up through `session.snapshot`. It records `expected_state` versus
  `observed_state` disagreement and checks run-bound `artifact_path` presence without adding
  predicate wiring before predicate evaluation exists.
- `dispatch_revision_baseline`, the optional register column holding the pane revision sampled at
  dispatch. Run-and-child sentinels are honoured only at a later revision, preventing stale
  scrollback from satisfying a new interaction.
- A schema fixture captured from the installed herdr binary plus real Unix-socket tests for stream
  closure, reconnect, missed child exit recovery, and the remaining event-client error cases.

### Not in this release

- Session launching, readiness or reap transitions, predicate evaluation, routing, mirror
  behaviour, spend gating, hang detection, and the `/orchestrate` command.

## [0.1.0] - 2026-08-13

### Added

Initial scaffold (U2 of `docs/plans/2026-08-12-orchestrate-plugin-plan.md`). This ships the
plugin shape and the register only — the state model for a herdr-driven multi-vendor run, plus
the Claude<->Codex handoff seam (R12). Nothing else in the plan ships yet.

- `scripts/register.py`: a flat, global, `run_id`-keyed JSON register at
  `.orchestrate/register.json`, with atomic durable writes (temp sibling file, `fsync`, then
  `os.replace` — matching `run_ledger.py` and `manifest_store.py` elsewhere in this repository),
  an exclusive advisory lock around read-modify-write cycles so concurrent writers never lose
  each other's row, and a schema-version gate that halts with a durable receipt at
  `.orchestrate/halt-receipt.json` rather than mutating the register on an unsupported version
  (C3). Columns are grouped Identity / Substrate / Work / Lifecycle / Time / Accounting,
  documented in the module docstring.
- **Forward compatibility (C4) at both levels.** A key written by one runtime and unknown to the
  other survives a write by the other, whether it sits **inside a child row** or **at the
  document root**. Both matter to the handoff: rows are merged rather than replaced, and the
  loader preserves the document it read instead of rebuilding a known envelope, on both the
  upsert and the retire path. Genuinely optional columns stay absent rather than being seeded, so
  "unknown key" remains distinguishable from "known but unset" across the seam.
- **Retirement is idempotent.** Retiring a run moves its rows to
  `.orchestrate/runs/<run-id>/register-final.json` and leaves other runs untouched; retiring the
  same run again returns the existing archive rather than overwriting it. The durable copy is
  written before the live register is rewritten, so an interrupted retirement duplicates rows
  rather than losing them — and re-running it, which is the documented recovery, is safe.
- `skills/orchestrate/SKILL.md`: documents the register contract for later units to build against.
- `plugin.json` manifest and `README.md`.

### Not in this release

- The subscriber, `events.subscribe` client, session launching, predicate evaluation, spend
  gating, hang detection, routing, or the `/orchestrate` command itself. Those are later units
  (U3-U10) of the same plan.
