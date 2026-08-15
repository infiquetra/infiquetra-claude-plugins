# Changelog

## [0.5.2] - 2026-08-15

### Fixed

- Shared register columns name one writer. `phase="planned"` cannot replace a
  terminal phase. `artifact_path` is written only when the artifact is settled.
  Admission writes only the row fields it owns.
- Re-planning a finished child is refused, including when its reservation is
  still held. `activate_slot` refuses a terminal row.
- An inferred snapshot absence is not immediate death. Reclaim of a held slot
  still requires a directly observed exit, an expired holder lease, or a
  terminal phase.
- A silent vendor is charged its declared `tokens_max` once launched. An
  observed value cannot lower that ceiling.
- `commit_plan` no longer accepts per-call limits the rendered plan does not
  own. The durable host policy must still equal the bounds the operator was
  shown. The presentation receipt is bound to a generation and is forgotten
  with the register.
- Queue promotion takes the globally oldest eligible entry by enqueue time.

### Changed

- A planned or queued child has spent zero. A launched metered child with no
  telemetry still fails closed.
- Usage replay is deduplicated by event identity. Cumulative totals keep a
  monotonic maximum; input/output samples add.
- Child `scope` is a sequence of bounded repository-relative paths.
  `tokens_max` is an exact positive integer.
- An absent host policy file still defaults. Every other unreadable or
  malformed file is an admission error that names the path.

## [0.5.1] - 2026-08-14

### Fixed

- Admission owns reservations, the queue, and the host policy. It no longer
  writes `phase`. Occupancy for the bound is the reservation set on every live
  run. Active phases without a reservation are evidence, not enforcement.
- A queued child that has already finished is dropped from the queue rather
  than promoted back to `planned`.
- Host bounds count every live run. An optional `admission.policy` file is
  the durable operator-set rule; reserve never writes it. Absent file means
  the documented defaults. A write still binds a run to its own stored work
  location.
- Reusing a row id for a different vendor or shape is a refusal.
- A planned reservation is not reclaimed because it has no pane yet. An
  observed `exited` holder is reclaimable even if the pane id remains.
- Every planned child declares a positive `tokens_max`. A silent vendor is
  charged that declaration, not an unlabeled estimate. The run-level spend
  gate no longer skips an unaccounted child.
- `commit_plan` requires a presentation receipt whose digest matches the
  rendered plan, which now includes scope, artifact, predicate, and
  integration mode.
- Observed-token writes hold the generation lock across read and write. A
  redelivered usage line is not counted twice. `context left` and token rates
  are not spend.

## [0.5.0] - 2026-08-14

### Added

- Planning decides the split and the route and then stops. `planning.py` never
  imports or calls `launch_child`. The operator is shown the plan before
  `commit_plan` writes a reservation. A plan that has not been presented is
  refused.
- Routing maps a work shape through `tier_policy.json` and the shared tier
  resolver's `resolve_for_runtime`. An unavailable preferred vendor walks
  `claude`, `codex`, `grok`, `qwen`, `muse`, `agy` and records the
  substitution. An explicit operator vendor, model, or effort is recorded as
  an override. See `references/routing.md`.
- Register-owned admission: per-vendor and aggregate work-in-progress bounds,
  a durable FIFO queue at the document root, an atomic reservation under a
  host-wide admission lock taken before the per-run generation lock, a
  release that advances the queue, and reclaim of a dead holder's slot.
  Exceeding a per-vendor bound queues even when aggregate room remains.
- Spend accounting. `tokens_reserved` is produced by `reserve_slot` and
  consumed by `check_spend` when the vendor has no usage line. `tokens_observed`
  is produced from a `pane.output_matched` usage line (the subscriber is the
  writer) and consumed by `check_spend` when the vendor reports usage. Missing
  telemetry fails closed. `authorize_spend` is never passed `None` to mean a
  silent vendor.
- `canonical_work_location` bounds the git subprocess at five seconds. A
  timeout, a missing git, or a non-repository is `intended.resolve()`, not the
  nearest existing ancestor. Two missing siblings of one parent no longer
  compare equal.

## [0.4.0] - 2026-08-13

### Added

- The live register is one JSON document per run, addressed by `run_id` in an
  orchestrator-owned host-local directory (default `~/.orchestrate/registers/<run_id>.json`,
  relocatable by `ORCHESTRATE_REGISTER_DIR`). A child cannot write it by working in its
  landing. A `run_id` is host-global: two callers that name the same id share one live
  document in one checkout. Two checkouts of one `run_id` are a collision. Every
  decision and mutation API requires `run_id`. `retire_run` forgets the per-run secret
  first, then archives the document into the recorded work location, then deletes the
  live file and the recorded-root sidecar, so a reused id is a new authentication
  identity. Sidecar create, key mint, key delete, and retirement share one per-run lock,
  so a concurrent mint cannot complete while retirement still holds it. Forgetting the
  key requires the coordinator-recorded work location, including when the live file is
  already gone. Both sides of a work-location comparison are canonicalized to the git
  top level. Claude and Muse have no
  workspace-write flag; mode `0600` does not exclude a child running as this account, so
  the seal does not defend that residual.
- Completion is the only path to `verified`. A child reaches it when its predicate's dependency
  closure is unchanged, its artifact was settled by the orchestrator's own rename, that artifact
  carries this dispatch's pre-established run binding, the predicate passes, the repository
  boundary is clean, the recorded destination has actually changed, and — for judgment-shaped work
  — a claimed independent verifier's depth sample is on record. A failure records a verdict when
  the landing belongs to the receipt's git repository; a landing in a different repository raises
  rather than records, because neither register is then a store this evaluation may write. A
  row's phase is `verified` if and only if its latest verdict is a pass: a first failure leaves
  the phase alone, and a failing re-evaluation demotes a previously verified row so the reap
  gate cannot consume a contradiction as a pass.
- The receipt binds **every input the verdict depends on**, not the labels that name the dispatch.
  The specification, landing, baseline and receipt arrive as four independent arguments. A landing
  that belongs to the receipt's git repository has its outcome recorded under the specification's
  row in that register; a landing that does not raises rather than records. So the run, row,
  landing, work shape, mutability, declared scope, base commit, ambient root and changed-paths
  baseline must all agree with the receipt before anything else is read. Otherwise a
  receipt issued for judgment work verified under a mechanical shape, which skips the depth gate
  entirely, and an out-of-scope write verified under a widened scope. `runtime`, `integration_mode`
  and `destination` are also compared, but as consistency fields rather than deciding inputs:
  evaluation reads them from the receipt, never from the supplied arguments, so a mismatch is a
  muddled caller rather than a substitution. `write_scope` is sealed and deliberately **not**
  compared — it is a pure function of inputs that are each compared individually, so a comparison
  against it could never be the check that catches anything.
- **The repository is derived, not supplied.** It is the work location the receipt binds —
  where git runs, where artifacts settle, where retirement archives — not the address of the
  live register. The live register is addressed by `run_id`. A caller who could name a
  second repository could still bind a landing in one tree to a receipt sealed for another;
  that is why issuance derives the work location from the landing and compares it to the
  recorded run root. The per-run secret does not cover this: it is named for the run alone
  and lives outside every repository, so it is shared by `run_id` on this host. R12 is
  one checkout: a second checkout cannot write the register. The secret is still shared,
  which is why it cannot stand in for a work-location check.
  Comparing a supplied root against the receipt was not enough, because the receipt's copy was made
  from that same supplied value at issue time — that catches a caller who changes it in between and
  cannot catch one that was wrong to begin with. So `issue_receipt` derives it from
  `landing.ambient_root`, refuses a landing that fails git identity or containment, and compares
  the derived store to the run root recorded at launch — a value whose provenance is not the
  landing. `evaluate_completion`, `settle_artifact` and `settlement_record` take it from the
  sealed receipt; none of the four accepts it as an argument. Git identity and containment are
  two properties: a nested repository shares ancestry and not identity; a sibling worktree
  shares identity and not ancestry. The live register is addressed by run id, not by working
  tree. Evaluation raises rather than records when the landing does not belong in the receipt's
  store.
  A landing that does not name its repository is refused rather than defaulted to its working
  directory. `read_receipt` is
  the one function that still takes a repository, because it is handed one with a row id and has no
  receipt yet — it checks the sealed root against the register it read, which is what stops an
  authentic verifier dispatch copied from another checkout of the same run from satisfying the
  depth gate here.
- The changed-paths baseline is bound by digest, because it is the one deciding input with no label:
  a baseline is repository state at an instant, and the same landing has different valid snapshots
  before and after a write, so binding the landing says nothing about when the snapshot was taken.
  Without it, an out-of-scope write verified against a baseline taken after the write. The snapshot
  is still produced once by the readiness path and passed in, rather than re-taken at issue, because
  two producers of one snapshot is the shape that hid a defect in the previous round.
- The predicate runs in its own process group, and the group is killed and waited out before the
  evidence is re-observed — on every exit path, success included. Waiting for the direct process
  only established that *that* process finished: a descendant outlived it, was reparented away, and
  rewrote the artifact after the snapshot that certified it, leaving a recorded pass whose durable
  digest did not match the file. A group that will not drain is `predicate_descendants`, a refusal.
  Group membership is the whole of that claim: a descendant that leaves the group with its own
  `setsid` is not reached by the kill, and `references/predicates.md` enumerates every actor the
  control does and does not cover.
- A `reaped` row keeps its terminal phase whichever way a later verdict goes. Demotion on a failing
  re-evaluation already worked; a *passing* re-evaluation wrote `verified` over `reaped`, and needed
  no forgery to do it — catch-up re-evaluates run-bound artifacts on startup and settlement replays
  cleanly, so a closed tab returned as a live verified child.
- The durable records the register holds are authenticated. The live file sits outside every
  landing, so a sandboxed child cannot rewrite it by address. Claude and Muse have no
  workspace-write flag, so the dispatch receipt and settlement record each carry a keyed
  digest under a per-run orchestrator secret held outside every landing. A digest that
  does not match this run's key authenticates against nothing and is refused. A
  same-account child that can read the key can produce a matching digest; the seal does
  not establish authorship against that residual. An added field is a mismatch rather
  than an ignored key, and a secret directory inside the repository is refused outright.
- Evaluation is safe to re-run for one dispatch. Settlement is recorded and replayed rather than
  re-attempted, which is what makes the restart path and judgment work reachable at all: the rename
  is one-shot, so without a record a second evaluation of a correct child fails as though it had
  written its destination directly.
- Predicates are a typed, closed schema: a fixed argument vector with a bounded timeout and output
  cap. Shell text, an `argv` string, a shell program, an inline-source flag, an unknown key, and an
  out-of-range limit are all rejected rather than clamped or ignored. The check runs inline in the
  orchestrator's process tree; a non-zero exit, a hang, an unlaunchable program, and output past
  the cap are each a failure and never a pass, with output streamed so an unbounded predicate is
  killed while still writing rather than buffered.
- A predicate cannot be weakened by the child it certifies. Its resolved import closure — not only
  its entry-point path — must lie outside everything the child may write, and a digest over that
  closure's contents is captured before dispatch and re-checked before evaluation, so a change to
  any statically known dependency fails even when that file sits outside the child's declared
  scope. The closure includes every parent package initializer along a dotted import, because Python
  executes those before the leaf module. The analysis is bounded and fails closed, and every route
  to other code it does *not* follow — dynamic import, `sys.path` insertion, installed distributions,
  native extensions' own imports, data files, non-Python entry points — is enumerated member by
  member in `references/predicates.md`.
- Settlement is performed rather than inferred, because a file on disk does not record whether it
  arrived by rename or by direct write. The child writes only an in-flight sibling of its
  destination; the orchestrator requires the destination to be byte-for-byte its pre-dispatch state
  and then renames the in-flight file into place itself. The predicate therefore reads only a
  renamed path. A directly written artifact, a missing deliverable, and an in-flight symlink are
  each refused with a real observation.
- Run binding is established before the child runs and stored in the register, never read from a
  file beside the artifact. An artifact from another run, another child, or another attempt is
  rejected, and the failure names the binding it does carry.
- Every child's deliverable lands in a directory that is exclusively its own and required to be
  invisible to the repository boundary. That is asked as the stronger question than "matched by an
  ignore rule": a tracked path stays visible to the boundary whatever the ignore rules say, so an
  artifact tree someone force-added is refused at dispatch with an actionable message rather than
  failing every later child on a control firing on the orchestrator's own rename. A read-only child's declared scope is a read scope, not a repository
  write allowlist. Concurrent read-only children with disjoint scopes therefore both complete
  cleanly, which they previously did not, while a read-only child that does write into the shared
  checkout still fails.
- The completion evaluator is held to the same boundary it enforces. Three surfaces are snapshotted
  immediately before the predicate runs and compared after it: the landing, the ambient checkout,
  and the artifact directory itself. The third is not redundant — that directory is required to be
  invisible to Git, so a predicate that rewrote the settled artifact after its digest was taken was
  previously a clean pass with a recorded digest that no longer matched the file. Any
  predicate-authored change fails as a predicate defect rather than being attributed to the child.
- Integration to the recorded destination is verified before reaping is possible — a `branch` tip
  that has not advanced and a `path` whose content has not changed both block verification, while
  `none` states that read-only work integrates nowhere instead of silently skipping the check.
- Judgment-shaped work, classified through fleet-core's authoritative work-shape vocabulary
  including its role-tier aliases, cannot reach `verified` on mechanical coverage alone. A depth
  sample records verifier identity, the digest binding it to this artifact, sampled claims, evidence
  locations, and dispositions from a closed set, and all of it is persisted to the register so a
  child that was genuinely sampled and one whose sample certified nothing are not the same green row.
  The named verifier must be a dispatch this orchestrator issued: an authenticated receipt for the
  verifier row, sealed under this repository, whose run matches and whose sealed runtime matches the
  sample's vendor, plus a phase that is one of the phases past launch and a matching recorded model.
  A register row alone is something a child can write. **What that establishes is that a verifier was
  dispatched in this repository, for this run, with this vendor — not that it ran.** The phase and
  model are register columns, not sealed fields, so moving a receipt-bearing verifier's phase from
  `planned` to `working` presents a session that never read anything; the phase check refuses the
  honest never-started case and not a planted one. It asks for membership in `launched`, `ready`,
  `working`, `verified`, `reaped` rather than refusing `planned` and `launching` by name, because a
  refusal written as exclusions accepts every value nobody thought of, including ones that are not
  phases at all. Sealing it needs post-launch evidence that lives in other units, and it is the same
  defect as the accepted residual on a child's own `phase` column, against a different column of the
  same untrusted store. A sample from the child
  itself, one recorded against another artifact, one with no claims, any unsupported claim, and a
  sample with no supported claim at all each block verification. Malformed external depth data is
  recorded as a closed failure rather than raised, because a control that raises instead of recording
  leaves the register showing a working child with no verdict.
- `references/predicates.md` states the completion contract, including for every control what it
  does **not** establish — notably that settlement does not prove how the child produced its
  in-flight file, that closure analysis does not follow dynamic imports, and that a depth sample
  cannot prove the verifier was blind.

### Changed

- Every child is launched with its runtime's ordinary workspace-write posture, mutating or not.
  A read-only flag forbade the artifact every child is required to write, and no supported CLI
  accepts a repository-relative path allowlist, so it never contained a read-only child — it only
  made its dispatch impossible to satisfy. That posture contains writes *outside* the workspace and
  nothing inside it; the boundary check is post-hoc, partial, repository-visible change detection
  that fails a child's completion rather than preventing its write, and a read-only child's
  repository write allowlist is empty.
- `GitLanding` answers two further boundary questions it already owned: whether a revision exists,
  and whether a path is genuinely invisible to the boundary — ignored *and* untracked. The scope
  helpers it shares with completion are now part of its public surface.
- A child's default environment command is `uv sync --locked --extra dev`, matching how this
  repository's CI provisions. A bare `uv sync` leaves a fresh worktree with no pytest, ruff or mypy,
  which is the set of programs a predicate is most likely to be, and that field exists precisely
  because a worktree cannot otherwise run its predicate at all.

### Not in this release

- Planning and vendor routing, admission control, spend and concurrency bounds, hang detection,
  mirror behavior, and the `/orchestrate` command.

## [0.3.0] - 2026-08-13

### Added

- Launch children through the `agent` wrapper's control-only path after validating its dry-run
  working directory and Herdr workspace. Launch intent and a run-bound task label are durable
  before the side effect, interrupted launches recover by discovering that label, and executable
  adapter tests pin every Herdr command to the default session and the installed argument grammar.
- Resolve model and effort through fleet-core's runtime adapter. Qwen's in-session effort command
  is sent after launch and accepted only after its own acknowledgement is observed; a timeout or
  disabled-thinking acknowledgement records a distinct not-ready source.
- Classify readiness through a nonce-bound `pane.output_matched` interaction whose complete
  sentinel never appears in echoed dispatch input. Trust prompts are surfaced before dispatch,
  dry-run routing mismatches fail before launch, and silent or continuously chatty panes remain
  bounded by the readiness deadline.
- Repair the subscriber's inert cross-counter revision guard. A captured live output-match event
  proves protocol 19 reports `read.revision=0`; the event envelope is now schema-validated through
  the production decoder instead of being discarded as stale.
- Provision mutating children in branch worktrees with an explicit environment-setup step; keep
  read-only children in the ambient checkout. Every child records a launch commit. Isolated child
  changes are compared with the current upstream merge base after merges or rebases, and any
  attributed ambient-checkout change by a mutating child violates the landing boundary regardless
  of its relative path. Shared-checkout violations state that authorship is not established, and the
  Git repository must contain a commit so committed-change observation cannot silently disable.
  Repository-visible changes are checked independently of predicate success; Git-ignored paths are
  documented as outside this control.
- Record reaping before closing a Herdr tab and distinguish a recorded reap from an unexplained
  disappearance.

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
