# Changelog

## [0.11.1] - 2026-08-16

### Fixed

- The last allowed iteration escalates for a recurring class, an earlier class that remains
  undisposed, an explicitly blocking finding, or an unperformed review. New non-blocking findings
  close the review without escalation.
- Blocking is a required keyword-only boolean on each finding. The loop does not infer it from the
  finding's free-form rank.
- Every verdict produced from a performed report returns that report's findings, including findings
  filed when the last allowed iteration closes.

## [0.11.0] - 2026-08-15

### Added

- A bounded review loop for the orchestration lifecycle. At most three iterations per unit over its
  lifetime, a re-review scoped to the change since the previous iteration, recurrence tracked by a
  defect class the reviewer declares rather than one inferred from prose, and three verdicts:
  `pass`, `halt-and-repair`, `halt-and-escalate`.
- Findings still open on the last allowed iteration escalate mechanically, regardless of the rank
  they carry. There is no remaining iteration in which to repair, so instructing a caller to repair
  would be untrue whether the class is new or recurring.
- Resolution must be authored. A report carries the classes it disposes of, and `pass` is refused
  while a class raised in an earlier iteration is still open, so a reviewer's silence about an
  unchanged path is no longer read as a fix. Disposing a class that was never open is refused, as is
  disposing and re-raising one class in the same report.
- A review that could not be performed is recorded separately from one that found nothing, emits no
  verdict, does not consume the iteration, and has an explicit conclusion that is never `pass`.
- Unit identifiers and defect classes are canonicalised once at a single site each, so surrounding
  whitespace can no longer split one unit into two or hide a recurring class.

## [0.10.0] - 2026-08-15

### Fixed

- An unparseable usage line marks the row and returns. The spend gate refuses,
  and a later parseable sample does not clear the mark. An ordinary output
  line containing the word token no longer kills the subscriber that holds
  the run's event stream.
- A completion verdict and the phase it justifies are one register write. A
  reap records `reaped` and `expected_state=exited` as one write.
- A writer-less upsert of `agent` cannot change what the run is charged.
  Spend excludes supervising rows by the owned `role` column, not by
  matching an `agent` name. `tokens_reserved` is owned by admission's write
  gateway, so a writer-less upsert cannot lower the charge.
- The mirror's owned-column seam names the `role` writer on the same write
  that records the rest of the mirror identity. The column stays owned; the
  identity stays one write.

## [0.9.3] - 2026-08-15

### Fixed

- An owned register column arriving at the generic merger without that
  column's writer is refused. Production writers of `phase` and
  `observed_state` go through the named setters. The reservation record is
  owned by the admission write gateway, not by reserve alone.
- Equal delta usage lines add. A content hash is not a delivery identity.
  A line matching both usage grammars is refused. Unparseable telemetry
  after a prior sample fails the spend gate closed.
- `commit_plan` writes the reservation, generation, phase, and plan row
  under one admission-then-generation critical section. Retirement takes
  the admission lock first, so it cannot split a reserved verdict from its
  reservation.
- A child is charged zero only when its phase is `planned`. A missing
  phase is unknown and fails closed.
- The generation sidecar is written atomically under the generation lock.
  An empty or unreadable sidecar is absent; a generation already stamped
  on the register is restored rather than minting a second one.

## [0.9.2] - 2026-08-15

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

## [0.9.1] - 2026-08-14

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

## [0.9.0] - 2026-08-14

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
## [0.8.0] - 2026-08-15

### Fixed

- **The scanner's bounds now have exactly one way to end, and it is the honest one.** The
  structure walk returned a bare "not found" when it hit its depth limit, and the caller could
  not tell that answer from "no declaration present" — so a nine-level JSON object whose
  innermost `argv` was bound to a proper sequence was accepted, with the scan reporting that it
  had finished cleanly. Depth 7 refused; depth 9 did not.

  This was the third appearance of one shape, once per review round, each with a different
  constant: a decode budget reported clean on exhaustion, then a line sweep did, then the walk
  did. Each was repaired alone while the next one waited. The repair this time is structural
  rather than another remembered rule — every bound (walk depth, walk size, encoding layers,
  decoded bytes, embedded regions) is consumed through a single budget object, and the scan
  builds its one and only result from that budget at a single return point. A bound cannot be
  reached and reported as a clean scan because there is no second place where completeness is
  decided, and a test asserts that single decision point structurally.

- **Three bounds were refusing the reading work the mirror exists to do.** A 201-line
  comparison of two children's reports — the example this unit uses for work that must leave the
  operator's channel — was refused as unexaminable. So was a one-line question naming seventeen
  `*args`-style identifiers, and thirty-three short Base64 notes. Fail-closed is right; failing
  closed at a threshold ordinary prose crosses is a defect in the same way an accepted
  declaration is.

  The line cap is gone: parsing every line of a worst-case instruction at the byte cap measures
  0.083s, so the byte cap was already the real bound. The decoded-payload cap is now measured in
  bytes rather than in a count of payloads, because a count is not a measure of work. The walk
  depth is raised well above anything a real document reaches, which it can be safely now that
  reaching it refuses.

- **Alias amplification is bounded by the walk, not by counting alias-looking text.** The
  previous guard counted `*name` occurrences, which fired on Python `*args` and markdown
  `*emphasis*` — shapes this repository's own source produces dozens of times per file — and did
  not recognise YAML's numeric aliases (`*1`) at all. A 424-byte document using numeric anchors
  took over nine seconds to scan. The structure walk now visits each shared node once, which
  brings the same document under three milliseconds and makes the count unnecessary; the guard
  that was not protecting anything has been removed rather than tuned.

- **A declaration after a `---` separator was parsed by nothing.** `yaml.safe_load` returns
  only the first document of a multi-document stream, so a second or third document was never
  examined while the scan reported that it had finished — the same shape as the bounds above,
  in a loader rather than a budget. Every document in the stream is now loaded. Found by this
  unit's own adversarial pass rather than by a review.

- **A Python mapping whose `argv` is a tuple, written after a prose prefix, reached the pane.**
  `Run this: {'argv': ('uv', 'run', 'pytest', '-q')}` is not valid YAML, is not the whole text,
  and the textual fallback does not recognise `(`. Balanced `{...}` and `[...]` regions are now
  parsed individually, so the declaration is found by a loader. Locating the region is textual;
  deciding what it means is not.

## [0.7.0] - 2026-08-15

### Changed

- **The predicate detector parses and inspects the result; it no longer pattern-matches
  serialized text.** Matching text was unsound and imprecise at the same time, for one reason.
  YAML can bind the exact key `argv` without those four letters ever standing next to a
  separator — through an escape, or through an anchor and an alias — so a text detector missed
  real declarations. The same pattern fired on `sys.argv:` in an ordinary sentence, so it
  refused requests to read this repository's own source, which is the mirror's whole job.
  Parsing closes both directions with one change: after a safe parse an escaped key **is**
  `argv` and an alias-bound key **is** `argv`, and a sentence mentioning `argv` does not parse
  into a mapping with an `argv` key at all.

  The detector now unwraps Base64 and hexadecimal runs — repeatedly, until they stop decoding,
  so layered wrapping is followed rather than capped — resolves `\uXXXX` escapes, and parses
  under `json`, `yaml.safe_load`, `tomllib`, and `ast.literal_eval`, applying each to the whole
  text, to each individual line, and to string leaves inside a parsed structure. It refuses
  when a result is **a mapping with an `argv` key bound to a sequence**, which is the predicate
  schema's own shape: `PredicateSpec` rejects an `argv` that is a command string, so binding
  the rule to the schema is what lets a type annotation (`argv: list[str]`, an `argv` bound to
  a *string*) survive.

  Every loader is a safe loader — `yaml.safe_load`, never `yaml.load` — because a parser that
  executed untrusted input would be a worse defect than the one being fixed. Alias expansion is
  the one resource risk a safe loader still carries, so text carrying an unusual number of YAML
  aliases is refused as unexaminable rather than expanded. A textual fallback remains for
  material no loader can parse at all, and is documented as a heuristic rather than the
  guarantee.
  *The alias count is superseded in 0.8.0: it counted a text shape this repository's own source
  produces and missed YAML's numeric aliases entirely. A memoised walk bounds the amplification
  instead.*

  Refused now and not before: a YAML escaped key, a YAML anchor and alias, layered Base64, and
  hexadecimal. Accepted now and not before: `argv = permission_argv(runtime)`,
  `argv: list[str]`, `sys.argv:`, `def main(*argv: str)`, an annotation block, and a list of
  seventeen commit identifiers. A mirror that refuses ordinary synthesis is as broken as one
  that accepts a predicate.

- **Every published claim now states the same boundary.** The reference, this changelog, the
  skill page, the module docstring and the test names had drifted apart: the docstring
  disclosed an encoding depth limit while four other places said Base64 was caught. The
  contract is now written in two halves in `references/operator-channel.md` — what is
  mechanically refused (machine-readable declarations), what is not detectable (an English
  request, for which no general detector is achievable), and what makes the undetectable case
  survivable (a mirror opinion cannot become `verified`, because completion requires a dispatch
  receipt the mirror is never issued).

- **The skill page no longer says nothing distinguishes a thinking mirror from a dead one.**
  That sentence was retracted in 0.6.0 and survived in one place fifteen lines from its own
  correction.

### Fixed

- **The first look at a pane's revision counter no longer advances the clock.** A counter is
  only evidence of emission when there is a previous one to compare it against, so the first
  observation now records a baseline and leaves the reference where it was. Treating it as an
  advance let a supervision loop that started late report a long-dead mirror as `working` with
  the pane-revision feed named as the source — health the counter had not established. It
  delayed a hang rather than suppressing one, but it made calling the reader strictly worse
  than not calling it, because the dispatch clock would already have tripped.
- **A revision counter that goes backwards re-baselines instead of sticking.** A herdr
  reconnect restarts the series; previously a decrease wrote nothing at all, so real output
  stayed invisible until the new series climbed past the old maximum. The safe direction is
  kept — a restarted counter is not evidence of emission — while letting the feed recover.
- **A failed subscription acknowledgement retracts the previous one.** The acknowledgement is
  durable and the subscriber process is not, so a replacement subscriber could inherit a dead
  process's confirmation, turning the distinct missing-wire state back into a working-or-hung
  report. A caller presenting a list without the mirror's subscription is evidence the wire is
  gone, and is now treated as such.
- **A request to summarise commit identifiers is no longer refused.** Base64 candidates were
  counted before being decoded, so seventeen hexadecimal identifiers exhausted a budget and the
  scan reported itself incomplete. Only runs that decode to valid UTF-8 are payloads now.

## [0.6.0] - 2026-08-15

### Changed

- **A published guarantee was false and is now accurate.** The mirror's documentation stated
  that a predicate never reaches it. A predicate did reach it, three ways, and the claim has
  been narrowed to what the mechanism actually does while the mechanism itself has been made as
  strong as it honestly can be. The honest sentence is that the mirror is never *asked* for a
  verdict through this API. An instruction that describes a check in ordinary English is not
  detectable by any scanner, and the live agent beyond the pane is itself a program executor.
  Column ownership was previously offered as the containment for this and does not contain it:
  it stops a mirror's opinion becoming a `verified` row, not a claimed verdict being produced,
  and a claimed verdict with no second reader is the failure the requirement names.
- **Hang detection can now tell a thinking mirror from a dead one, and the earlier claim that
  nothing could was too strong.** The subscriber advances `last_event_at` only on a matched
  sentinel and the mirror's only subscribed sentinel is its return marker, so that feed alone
  makes the clock a per-request tolerance. `observe_pane_activity` reads herdr's pane-output
  `revision` counter from a `session.snapshot` — the feed the register names for this, naming
  this unit as its reader — and records it on the mirror's own row, so a pane still emitting
  keeps the clock fed and a pane that has stopped lets it trip. It is a snapshot read rather
  than a heartbeat subscription because the subscriber wakes the orchestrator on every handled
  event, so a heartbeat would wake the operator's channel on a timer. `MirrorLiveness` now
  reports which feed the answer rested on, so "working" from a stale clock and "working" from a
  live one are not the same word.

### Fixed

- **The predicate-declaration scan keys on the declaration's signature, not on one
  serialisation.** A predicate is the name `argv` bound to a value; JSON, a YAML block or flow
  mapping, TOML, a Python literal, a string nested inside another object, unicode-escaped
  braces, and Base64 are the same declaration in different clothes, and all are refused.
  Enumerating serialisations is a race the enumerator loses.
  *Superseded in 0.7.0, which replaces text matching with parsing — see that entry for why
  matching a signature in serialized text was still both unsound and imprecise.*
- **The scan fails closed.** An instruction it cannot finish examining within its budget is
  refused rather than passed. Reporting "clean" on exhaustion had turned a denial-of-service
  bound into the bypass: a real declaration parked behind 512 decoy braces was never inspected
  and was accepted, while 511 decoys were correctly refused.
- **Dispatch re-runs the request's checks on the object it is handed.** Every load-bearing
  check lived in a constructor while the one function that talks to the pane read attributes
  off whatever arrived, so any object with the right attribute names bypassed the closed kind
  vocabulary and the scan together. This closes the class rather than an instance of it.
- **Every clock input must be finite.** A NaN threshold passed validation because every ordered
  comparison with NaN is false, and positive infinity passed honestly; either made a dead
  mirror report `working` forever, reaching the affirmative state the unarmed error exists to
  prevent by a different door. Thresholds, dispatch instants, observed instants and the
  supplied `now` are all now required to be finite, and a non-finite threshold is refused at
  creation.
- **A zero or negative default return bound is refused at creation.** It is interpolated into
  the charter as the session's standing default, so zero told the mirror its default budget was
  nothing, which would make every return that honoured the charter oversized.

### Added

- **`resume_mirror` rebuilds a live session from the register alone.** The mirror's nonce and
  return markers previously existed only in an in-memory session object, so an orchestrator
  that died could not collect from a mirror that was still running — which contradicts the
  requirement that the mirror is persistent for the life of the orchestration. The row now
  carries them, and the identity is written before the launch side effect alongside the row
  itself. The run's single mirror is located by its `role` column when no row id is given, and
  two mirrors in one run are refused rather than guessed.
- **A missing subscriber wire is loud instead of silent.** The mirror's row records the
  `pane.output_matched` subscription its returns require. `acknowledge_subscription` compares
  it against the list the subscriber was actually given and refuses a mismatch; until something
  confirms it, `check_liveness` raises a distinct unconfirmed-subscription error rather than
  reporting a state. A mirror nobody is listening to and a hung mirror produce identical
  silence, and reporting the first as the second sends the operator hunting a hang that is not
  there.
- **Repository-visible change over a request window is observed and recorded.** The mirror is
  read-only by contract and nothing prevents it writing — `mutating=False` keeps it in the
  ambient checkout but is not a write fence, and because the mirror declares no artifact it
  never reaches the post-hoc scope check, so a violation was previously not merely unprevented
  but unobserved. The observation is reported on the return and recorded durably; escalation is
  opt-in through `assert_no_repository_change`, because this session reads the operator's live
  working tree, so the operator's own edit lands in the same window and attribution is not
  established. Isolation was rejected deliberately: a worktree would give the mirror a tree
  nobody is working in.

## [0.5.0] - 2026-08-15

### Added

- **The mirror**: a persistent paired session that performs the orchestrator's own work —
  synthesis, comparison, bulk reading — so the operator's channel stays answerable while work
  happens. Children do the outcome's work; the mirror does the orchestrator's. It is launched
  through the same session path as any child (dry-run preview, write-ahead label, trust-prompt
  check, nonce-bound readiness sentinel) and holds an ordinary register row, written **before**
  the launch side effect so a mirror whose launch failed is visible rather than absent.
- **A distilled return under an enforced byte bound.** A return larger than its request's
  declared bound is rejected whole rather than truncated, because a truncated return is an
  oversized one wearing the appearance of success. The rejection carries the byte count and
  never the material — an error that quoted the return would perform the absorption it reports
  — and it is recorded durably, so a rejection is distinguishable from a return that never
  happened. The bound a request may declare is itself capped at 16 KiB (default 4 KiB): this
  contract does not erode by being deleted, it erodes by being raised. A rejected return leaves
  the mirror ready and holding its context, so the cost is one round trip rather than the
  session.
- **The validity predicate never runs in the mirror.** Routing it there would turn verification
  back into a claim: the mirror reports a pass, the orchestrator never sees the bytes and cannot
  re-check, and the evidence-failure class reappears one layer up with no second reader. Three
  independent guards — a closed vocabulary of reading request kinds with deciding kinds refused
  by name; refusal of any instruction carrying a predicate declaration; and a module that
  contains no program-execution route and does not import the completion module. What no guard
  catches is an instruction that describes a check in prose; the containment for that is the
  written routing rule plus the fact that the mirror writes no `phase`, so its opinion cannot
  become a verified row.
- **Clock-based hang detection**, because nothing else reaches this failure. Every other failure
  in this system appears as a disagreement between two values; a hung mirror's expected and
  observed states agree perfectly, every child still looks healthy, and the operator's channel
  is dead. `check_liveness` therefore compares silence against the row's declared
  `max_quiet_seconds`, taking the current instant as an argument rather than reading the system
  clock. It reads and raises: it writes nothing, closes nothing, and demotes nothing, because
  what to do about a quiet mirror is a decision. A row with no declared tolerance raises a
  distinct "not armed" error rather than reporting health, and an idle mirror is never alarmed,
  because a mirror between requests is legitimately silent forever.
- **Non-blocking dispatch.** No subscription is held open, no pane is polled, and there is no
  timeout parameter. The outstanding request is durable before the line is sent, so a failed
  send leaves an armed clock rather than an idle-looking mirror. A second request while one is
  outstanding is refused explicitly with the outstanding id, never silently dropped.
- **Checkable column ownership.** Every register write in the mirror module passes through one
  seam that refuses, at runtime, any column outside `role`, `max_quiet_seconds`,
  `mirror_request` and `mirror_last_return`, and only on the mirror's own row. It does not write
  `artifact_path`, does not write `observed_state` (the subscriber owns that and rewrites it on
  every catch-up pass), and never promotes its own phase. The mirror row is identified by `role`
  rather than by `agent`, because `agent` carries the launcher's actual agent name for every
  launched row and a second writer of a shared column is a defect this codebase has paid for.
- **`references/operator-channel.md`**: the routing rule in writing. Work goes to the mirror by
  default; the exception list is five entries, each with the reason it is bounded by
  construction; anything not on the list goes to the mirror even when it looks trivial. It also
  states plainly what the clock does not establish — nothing distinguishes a mirror quiet
  because it is thinking from one quiet because it is dead, and the within-request heartbeat
  that would narrow the gap is deliberately not built, because the subscriber wakes the
  orchestrator on every matched event and a heartbeat would wake the operator's channel on a
  timer.
  *Half superseded in 0.6.0: the heartbeat reasoning holds, but pane revision does distinguish
  the two, and 0.6.0 builds that feed.*
- **Deliberate context management.** The mirror is persistent for prompt-cache benefit and
  continuity, and a mirror that has silently degraded is worse than no mirror because the
  orchestrator will still believe its answers. Its context is compacted or cleared on
  instruction, refused while a request is outstanding, and refused outright for runtimes whose
  context commands are not established here rather than guessed — an unrecognised slash command
  is a silent no-op that looks like a reset.

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
