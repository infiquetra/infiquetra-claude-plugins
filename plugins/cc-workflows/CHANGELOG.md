# Changelog

## [2.0.0] - 2026-09-20

### Archived -- FINAL RELEASE

**This plugin is archived. It is removed from the marketplace in the next commit, and this is its
last entry.** Issue #1030, under the saga simplification (parent #1018).

**Why.** The emitter could not be separated from the machinery this release removes. Its declared
plugin-boundary surface named thirty names in Saga's `execution_spec.py`, two of which were the
engine-routing functions themselves; `execution_spec.py` imported the whole external-engine family
at its module head, and `dispatch_settlement.py` referenced the run-fact ledger forty-six times as
its substrate. Moving the three modules beside the emitter would have dragged 44 further modules and
24,565 further lines -- including the entire outcome coordinator -- into this plugin. Severing them
instead meant rewriting two large modules and roughly 9,261 lines of tests to remove a capability
(routing units to external engines) that the same release deletes anyway. The operator chose the
archive.

**Where the content went.** Nowhere, and that is the decision: the Workflow backend was reachable
only by explicit operator invocation (issue #808's NARROW ruling) and the September operating record
shows it was not invoked. The lifecycle now has one execution backend, `inline`, and the work a
Workflow used to fan out is done by the build loop and the lensed code review. Saga's
`references/workflow-backend.md` -- the prose describing when to enter a Workflow and how to author
a spec -- goes with this plugin in the same release. The role prompts that a fan-out would have
staffed live in `plugins/agent-launcher/roles/`.

**What a caller must change.** `cc-workflows-ultracode` is no longer a saga execution backend. The
orchestration enumeration is the single value `inline`. A saga tick that recorded
`--orchestration-mode cc-workflows-ultracode` still reads back, because the stored string is durable,
but no new run can select it. Anything resolving this plugin's root by path or through the shared
plugin-resolution ladder will no longer find it.

## [1.0.2] - 2026-09-20

### Changed

- **The skill stops naming `team-execution` as a fallback and as the default offer's second value.**
  Issue #1030 archived that plugin. `inline` is now the only backend the recommender returns, so the
  HALT recovery line points there, the availability-probe note names one non-Workflow path rather
  than two, and the isolation comparison speaks of the archived plugin in the past tense. Nothing
  about when a Workflow may be entered changes: still explicit operator invocation only, per issue
  #808's NARROW ruling.

## [1.0.1] - 2026-09-19

- Issue #1026 removed `plugins/saga/scripts/spec_table.py`. The authoring skill invoked it to
  render the approval table an operator signs off; that command line is replaced by instructions
  for building the same view from the spec — one row per unit with its id, label and
  `{model, effort}` tier, the dependency waves, and spend against budget.
- The boundary note and `saga_spec_shim.load_execution_spec`'s docstring no longer name
  `team_emitter.py`, which issue #1026 also removed. Prohibiting or citing a file that does not
  exist implies it could, and protects nothing.

## [1.0.0] - 2026-08-30

- Initial extraction from Saga (#925, issue #918 wave 1, unit U4): the workflow-script
  emission path (`emit_workflow_script` + the #708 agent-opts guards + the driver-owned
  settlement/lease metadata builders) moved from `plugins/saga/scripts/execution_spec.py`
  into `skills/cc-workflows/scripts/emitter.py`; `workflow_emitter.py` (the frozen
  `workflow_lease_reservation.v1` contract CLI) moved from `plugins/saga/scripts/`.
- The boundary is the typed execution spec: the emitter reads Saga's spec shape (never a
  copy); Saga keeps the spec schema, validation, tier resolution, `team_emitter.py`, and
  the integration contract that delegates `emit` / `settlement` / `lease` here.
- Workflow protocol prose (authoring Steps 2–5, invocation identity, lease-contract
  retirement semantics, release/renew) carried with the plugin; Saga's `/plan` and `/work`
  keep the driver-side seam.
