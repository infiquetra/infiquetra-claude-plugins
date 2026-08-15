---
name: orchestrate
description: The orchestrate register, tracked herdr subscriber, write-ahead child session lifecycle, completion gate, work-shape routing, register-owned admission, spend accounting, paired mirror session, and the composition control flow that assembles them into a supervised multi-vendor run — approved plan, reservation, activation, launch, readiness, dispatch receipt, wake, inline predicate, verified integration, recorded reap, slot release and queue promotion, plus restart recovery, subscriber respawn, ownership reconciliation and retirement. No slash command yet. Triggers on "orchestrate register", "orchestrate subscriber", "orchestrate session lifecycle", "orchestrate completion", "orchestrate planning", "orchestrate admission", "orchestrate routing", "orchestrate spend", "orchestrate predicate", "orchestrate mirror", "orchestrate runner", "the orchestration control flow", "the operator channel", "mirror hang detection", "herdr event catch-up", "the run register", "phase 1 acceptance".
---

# orchestrate — register, subscriber, lifecycle, completion, planning, admission, and the mirror

`orchestrate` coordinates multi-vendor herdr sessions: Claude, Codex, Grok, Muse, Qwen, and agy
children dispatched under one operator-driven run, aggregated back through a mirror and woken by a
subscriber holding herdr's event socket across turns. This skill currently ships the register,
subscriber, child session lifecycle, completion gate, planning, routing, admission, spend
accounting, and the mirror. The register is the whole state model (KTD5) and the
Claude↔Codex handoff seam (R12). The subscriber holds protocol 19 event streams, wakes the
orchestrator, and performs reconnect catch-up (KTD3/KTD12). The session lifecycle owns write-ahead
launch, recovery, interaction readiness, landing isolation, scope checks, and recorded reaping.
Completion is the only path to `verified` (R5): a bounded, typed predicate run inline by the
orchestrator on a settled, run-bound artifact, inside a clean boundary, with integration to the
recorded destination verified before a child can be reaped.
Planning decides the split and the route and then stops. The mirror is the home for the
orchestrator's own unbounded work, so the operator's channel stays answerable.
`scripts/runner.py` is the control flow that assembles all of them; the `/orchestrate` command
itself lands in a later unit of `docs/plans/2026-08-12-orchestrate-plugin-plan.md`.

## What the register is

A single flat JSON document **per run**, addressed by `run_id` alone, held outside every
working tree (default `~/.orchestrate/registers/<run_id>.json`, relocatable by
`ORCHESTRATE_REGISTER_DIR`). One row per tracked entity: one per dispatched child, one for the
mirror, one for the subscriber. A `run_id` is host-global: two callers that name the same id
share one live document in **one checkout**. Two checkouts of one `run_id` are a
collision, not a handoff. `retire_run` forgets the per-run secret first, then archives
the document into the repository at `.orchestrate/runs/<run-id>/register-final.json`,
then deletes the live file and the recorded-root sidecar, so a reused id is a new
authentication identity. Forgetting the key requires the coordinator-recorded work
location, including when the live file is already gone. Every decision and mutation
API requires `run_id`; a row cannot be named without naming its run. A user-facing
`--root` is canonicalized to the git top level before it is validated or stamped.

The implementation is `scripts/register.py`. Read its module docstring before writing to the
register from any later unit — it documents every column's meaning, including two facts measured
first-hand while driving this build by hand (`docs/engineering-journal/LEARNINGS.md`,
`#pane-revision-is-the-liveness-signal` and `#agent-lifecycle-detectors-lie`):
`last_event_at` must be fed by herdr's pane-output `revision` counter, never by the
lifecycle-transition `state_change_seq` counter, which sits still for minutes on a healthy,
working child; and a child's own reported status is not a completion signal, so `expected_state` /
`observed_state` exist to record a disagreement rather than resolve it by trusting one side.

`pane.output_matched` reports `read.revision=0` while the pane's own counter is positive and
advancing, so those counters are never compared. The subscriber instead checks complete run,
child, purpose, and nonce identity. All sentinel producers use the public split-assembly helper so
the assembled marker stays out of echoed dispatch input.

## Contract this unit guarantees

- **Atomic, durable writes.** Every write is temp-sibling-file, `fsync`, then `os.replace` (not
  just temp-plus-`os.replace` — `fsync` before the replace is what keeps a machine crash right
  after a successful replace from leaving the live register present but empty, matching
  `run_ledger.py` / `manifest_store.py` elsewhere in this repository). No reader ever observes a
  torn file. Concurrent read-modify-write cycles are serialized with an exclusive advisory lock
  (`fcntl.flock`) around the register's own `.lock` sidecar, so two sequential writers never lose
  each other's row.
- **Forward compatibility (C4), at both levels.** A row is always a plain `dict`, never
  reconstructed through a fixed-field type: `upsert_row` merges the fields a caller supplies into
  whatever already exists at that row id rather than replacing the row, so a key nested inside a
  child row that one runtime wrote and the other does not know about survives a write by the
  other. The same holds at the **document root** — the loader returns the document exactly as it
  read it (only normalizing `rows`) rather than rebuilding a known `{schema_version, rows}`
  envelope, so a document-root key one runtime writes (a handoff cursor, say) survives an ordinary
  write by the other, on both the `upsert_row` and the `retire_run` path.
- **A schema version this code does not support halts loudly (C3).** `register.py` writes a halt
  receipt beside the live file (`<run_id>.halt-receipt.json`) and raises, without ever touching
  the live register itself.
- **Retiring a run archives that run's document and frees that generation.** `retire_run`
  forgets the per-run secret first, then writes `.orchestrate/runs/<run-id>/register-final.json`
  in the coordinator-recorded work location (verified against the caller-supplied root by
  filesystem identity, after canonicalizing both sides to the git top level), then deletes
  the live host-local file and the recorded-root sidecar. Sidecar create, key mint, key
  delete, and retirement share one per-run lock, so a concurrent mint cannot complete
  while retirement still holds it. When retirement returns, that generation's key and
  sidecar are gone. A mint that waited is a new generation. A first-writer stamp is not
  enough to authorize retirement or key deletion. A crash after the secret is gone leaves
  receipts that no longer unseal; a second `retire_run` repairs a leftover key only when
  the recorded root is still there to name the generation. No recorded root and no live
  file is a true no-op — the key is not touched. A reused id therefore mints a new key.
  A root that does not match the recorded work location raises and leaves the live file,
  sidecar, and key untouched.
- **Both hang-detection time columns always exist on a row.** `deadline` and `max_quiet_seconds`
  are alternative strategies — a caller sets whichever fits a given dispatch — and `upsert_row`
  seeds whichever one a caller didn't set to `None` at row creation, so this pair specifically
  always round-trips regardless of which strategy a row uses. Every other optional column stays
  genuinely absent until some later phase transition sets it.

## Using the register from Python

```python
from pathlib import Path
import register  # scripts/register.py, on sys.path for the invoking skill/command

root = register.canonical_work_location(Path.cwd())
register.upsert_row(root, "child-1", {"agent": "claude"}, run_id="run-abc")
register.write_phase(root, "child-1", "planned", run_id="run-abc")
rows = register.read_rows(root, run_id="run-abc")
register.retire_run(root, "run-abc")
```

Or from the shell, for quick inspection:

```bash
python3 plugins/orchestrate/skills/orchestrate/scripts/register.py show --run-id run-abc
python3 plugins/orchestrate/skills/orchestrate/scripts/register.py retire run-abc
```

## Event subscription and catch-up

`scripts/herdr_events.py` opens `~/.config/herdr/herdr.sock`, validates every requested
subscription, and sends the request documented in `references/herdr-event-api.md`. Request event
types are dotted (`pane.exited`); broadcast event names are underscored (`pane_exited`). A malformed
or underscored subscription is an error, never an ignored entry.

`scripts/subscriber.py` is the single-purpose process that holds the event stream across turns. It
creates an ordinary register row with `agent="subscriber"`, wakes the orchestrator through
`agent.prompt`, and runs one `session.snapshot` catch-up after every accepted subscription,
including startup. Catch-up updates `observed_state`, reports disagreement with `expected_state`,
and checks the settled `artifact_path` column. A plan declaration is not that
column; catch-up reports presence as unknown until settlement writes it. Its
`observed_state_source` records whether the value
was directly observed or inferred from pane/tab presence. A catch-up failure is reported but does
not close the accepted event stream. It does not evaluate predicates.

The subscriber accepts two closed `pane.output_matched` substring classes: a complete sentinel,
and the accounting usage needle (`token`). A regex or any other ordinary-text match is valid for
Herdr generally but is a startup error here. More than one sentinel subscription may target the
same pane, so readiness and completion interactions can both remain active. A usage match writes
`tokens_observed` on the matching row.

The spawning unit supplies the subscriber pane, orchestrator pane, run identity, and complete JSON
subscription list:

```bash
python3 plugins/orchestrate/skills/orchestrate/scripts/subscriber.py \
  --root "$PWD" \
  --run-id run-abc \
  --row-id subscriber-run-abc \
  --pane-id w1:p2 \
  --orchestrator-pane w1:p1 \
  --subscriptions-json '[{"type":"pane.exited"}]'
```

`--root` may be the current working directory, including a package subdirectory of a
monorepo. The process canonicalizes it to the git top level before the first validation
and the first stamp, so the documented invocation from `packages/tool` still names the
repository `launch_child` records.

## Child session lifecycle

`scripts/session_lifecycle.py` launches through `agent --herdr-control-only` only after a dry-run
confirms the exact absolute working directory and intended Herdr workspace. A run-bound task label
and `launching` register phase are durable before the launch side effect. A retry discovers that
label before launching, so a crash after process creation cannot duplicate the child.

The wrapper's JSON response is the only source for workspace, tab, pane, reused-workspace status,
and the actual uniquified agent name. Readiness subscribes before dispatch and requires the child
to assemble and emit a nonce-bound sentinel that never appears whole in the echoed prompt. Pane
content is checked for a trust prompt first. The lifecycle never treats `agent_status` alone as
readiness. Qwen receives its resolved `/effort` command in-session and must emit its own
acknowledgement before work is dispatched.

Mutating children receive a branch worktree plus an explicit environment setup; read-only children
stay in the ambient checkout. The lifecycle is fixed to Herdr's default session. Every child gets
its runtime's ordinary workspace-write posture, mutating or not: each is dispatched with an artifact
it must write and no supported CLI accepts a path allowlist, so a read-only flag would forbid the
one write the protocol requires. The scope control
records a launch commit for every child and unions committed changes with uncommitted tracked and
non-ignored changes. A mutating child's declared scope applies only to its isolated landing; every
attributed ambient-checkout change violates that boundary. Git-ignored paths remain an explicit
limitation requiring a separate filesystem boundary. Reaping records the transition before closing
the tab.

See `references/substrate-contract.md` for the adapter, recovery, residual readiness risk, and
failure contract.

## Completion — the only path to `verified`

`scripts/completion.py` decides whether a child is done, and records why either way. A predicate is
a typed, closed schema: a fixed argument vector with a bounded timeout and output cap, rejected
rather than clamped when it exceeds either, and rejected outright when it is shell text. It runs
inline in the orchestrator's own process tree — the mirror never decides (KTD6).

Before dispatch the orchestrator issues a receipt: a run-binding token the child must carry inside
its deliverable, the destination's exact pre-dispatch state, and a digest over the predicate's
resolved dependency closure. A predicate whose closure lives where the child can write is rejected
before evaluation, and a closure that changes between dispatch and evaluation fails as tampered.

The receipt must belong to the child being evaluated: the specification, landing, baseline and
receipt arrive as four independent arguments, so run, row and landing are checked against it first.
The repository is deliberately not a fifth. Issuing derives the store from the landing, refuses
a landing that fails git identity or containment, and compares that store to the run root
recorded at launch — a value whose provenance is not the landing. Evaluation takes the store
from the sealed receipt only after those same checks, and raises rather than records when they
fail — do not add a root parameter back when you wire this up. Record the run root with
`record_run_root` before the first issue, using the same path you will pass to `launch_child`.
Issuance never writes that record. Git identity and containment are two properties: a nested
repository shares ancestry and not identity; a sibling worktree shares identity and not
ancestry. A working directory that is an ordinary subdirectory of the *same* store is still
accepted. A store that is merely an ancestor of a mutating child's worktree is still accepted
when no run root has been recorded. `ambient_root` is not a register column. Reconstruct it
from the orchestrator's own resolved root — the same value `GitLanding.provision` sets — never
from a child's working directory.

Settlement is performed, not inferred. The child writes only an in-flight sibling of its
destination; the orchestrator requires the destination to be untouched and then renames the
in-flight file into place itself, so the predicate only ever reads a renamed path. That rename is
one-shot, so it is recorded and replayed — which is what makes re-evaluation after a restart, and
the two-step sequence judgment work needs, reachable at all. Every child's deliverable lands in a
directory that is exclusively its own and invisible to the repository boundary, which is what lets
concurrent read-only children in one checkout each complete cleanly.

The live register sits outside every landing, addressed by `run_id`. A sandboxed child cannot
write it by working in its landing. Claude and Muse expose no workspace-write flag, so those
runtimes can still reach the host-local directory if they know the path. Mode `0600` on the
run key excludes other operating-system accounts, not a child running as this account. For
runtimes whose sandbox does not deny `~/.orchestrate`, this module does not defend against a
child that reads the run key and seals payloads that verify. A digest that does not match
this run's key authenticates against nothing. The seal does not establish that the
orchestrator was the writer when the child can read the key.

Integration to the recorded destination is verified before `verified` is written, so a child whose
change never landed cannot be reaped. Judgment-shaped work additionally requires a claimed independent
verifier's depth sample, bound by digest to the settled artifact and supporting at least one sampled
claim — all of it persisted, so a sampled child and an unsampled one are not the same green row.

**Dispatch a verifier the way you dispatch any other child: issue it a receipt.** The named verifier
must carry an authenticated dispatch receipt for this run, sealed under this repository, and its
vendor is compared against that sealed receipt rather than against a register column — so a verifier
that is only *registered*, with no receipt issued, is refused and every judgment child that names it
stays unverified. What this establishes is that a verifier was dispatched in this repository, for
this run, with this vendor; it does not establish that the verifier ran, because the phase and model
it is checked against are register columns any write-capable actor can set.
`references/predicates.md` sets out where that stops.

A row's phase is `verified` if and only if its latest verdict is a pass: a failing re-evaluation
demotes a previously verified row rather than leaving a contradiction the reap gate would read as a
pass, and a `reaped` row keeps its terminal phase whichever way the verdict goes. The receipt binds
every input the verdict depends on — the repository root, work shape, scope, mutability, integration
target and the changed-paths baseline, not only the identity labels — and the predicate runs in its
own process group, whose surviving members are killed before the evidence is re-observed.

See `references/predicates.md` for the full contract, including what each control does **not**
establish.

## Planning, routing, admission, and spend

`scripts/planning.py` is the judgment step. It maps each child's work shape through
`tier_policy.json` and `resolve_for_runtime`, walks the declared vendor order when the
preferred vendor is unavailable, and records every substitution and every explicit
operator override. See `references/routing.md`.

`scripts/admission.py` owns the work-in-progress bounds. Occupancy for the bound is
the reservation set on every live run on this host. Active phases without a
reservation are reconciliation evidence (`unreserved_active`); they are not the
atomic enforcement. Exceeding a per-vendor bound **queues**. The queue is a real
FIFO at the document root and `advance_queue` is the only thing that turns a queued
child into a reservation. Admission never writes `phase`. A planned reservation
expires only by abandonment or a declared lease; an observed `exited` row is
reclaimable even if its pane id remains.

The generation lock is per run and is not reentrant. Bounds are host-wide, so
admission takes `admission.lock` first, then the run's generation lock, and never
the reverse. An optional `admission.policy` file beside that lock is the durable
operator-set rule. Reserve never writes it. If the file is absent the module
defaults apply. Any other unreadable or malformed file is an admission error that
names the path; only exact positive integers are accepted. `write_host_policy` is
the only writer. Work-location binding on a write is unchanged: a run still
belongs to one directory. When promoting a queued child of another run, the write
uses *that* run's stored location. Promotion takes the globally oldest eligible
entry by enqueue time.

`scripts/accounting.py` is the spend gate. Every planned child declares a positive
integer `tokens_max`. That number is `tokens_reserved`. A child whose phase is
explicitly `planned` has spent zero. Queued is an admission status, not a phase.
A missing or unknown phase fails closed. Once launched, a vendor with no usage
line is charged that declared maximum; an observed value cannot lower it. `tokens_observed` is produced
from a usage `pane.output_matched` line. Cumulative totals keep a monotonic
maximum; equal delta samples add. A content hash is not a delivery identity.
A line matching both grammars is refused. Unparseable telemetry after a prior
sample fails closed; a later parseable sample does not reopen the gate. A
launched metered child with no telemetry fails closed.
`authorize_spend` is never passed `None` to mean a silent vendor.

`launching` is written before the native launcher runs, so a `launching` row with no recorded pane
is charged zero here — it is the durable launch intent, not evidence a session exists. That is a
cheap answer this module gives from the row alone; it does not by itself prove no session exists,
only that this process has not recorded one. The composition unit is the one caller positioned to
settle that: before treating such a row's silence as nothing to wait for, it asks the launcher's own
label discovery whether a session already exists for it, and fails closed on an inconclusive answer
the same way it fails closed on a metered vendor's genuine silence.

The run's spend total and the unreserved-active reconciliation evidence both exclude the rows that
supervise a run rather than doing its work, and both ask `register.is_supervisory_row`. The test
reads the owned `role` column alone: `agent` cannot carry the decision, because the mirror is
launched through the ordinary session path, which overwrites `agent` with the launcher's uniquified
name, so an `agent`-only test misses it entirely and the run's spend then demands telemetry from the
mirror forever. `role="mirror"` / `role="subscriber"` is written before each one's own launch side
effect, so a supervising row is classified from the moment it exists.

`plan` and `present_plan` write nothing. `present_plan` only renders. `commit_plan`
requires a presentation receipt whose digest and generation match this plan, and
whose rendered host bounds still equal the durable policy. This unit can write
that receipt; the composition unit is the producer that should write it after the
operator channel delivers the text. The generation sidecar is written atomically
under the generation lock. An empty or unreadable sidecar is absent; a generation
already stamped on the register is restored rather than minting a second one.
`retire_run` forgets the receipt with the generation and takes the admission lock
first, so it cannot split a reserved verdict from its reservation. None of them launch a child. `commit_plan` does
not write the settled `artifact_path` column. The reservation, generation,
phase, and plan row are one critical section.

`activate_slot` marks a matching reservation `held`. It does not launch and does
not write `phase`.

## The mirror — the operator's channel, and the clock that watches it

`scripts/mirror.py` is the home for the orchestrator's own work: synthesis, comparison, bulk
reading. Children do the outcome's work; the mirror does the orchestrator's, so the operator's
channel stays answerable while work happens. The highest-severity failure in the corpus behind
this plugin is that channel dying under supervision load, and the rule "the orchestrator must not
do work" is insufficient on its own, because work genuinely has to happen somewhere.

The mirror is launched through the same `session_lifecycle` path as any child — write-ahead label,
dry-run preview, trust-prompt check, nonce-bound readiness sentinel — and it holds an ordinary
register row. That row is written **before** the launch side effect, so a mirror whose launch
failed is visible rather than absent (R6c).

Four contracts are mechanical rather than aspirational:

- **A return over its declared bound is rejected, never truncated**, and the rejection carries the
  byte count without the material — an error that quoted the return would perform the absorption
  it reports. The bound a request may declare is itself capped, because this requirement erodes by
  being raised, not by being deleted.
- **The mirror is never *asked* for a verdict through this API (KTD6)** — deliberately weaker than
  "the validity predicate never runs in the mirror", which an earlier revision claimed and which
  is not true. Deciding request kinds are refused by name. An instruction whose content
  **parses** into the predicate schema's shape is refused: the detector unwraps Base64 and
  hexadecimal layers, resolves `\uXXXX` escapes, parses under `json`, `yaml.safe_load`,
  `tomllib` and `ast.literal_eval` — whole text, every document of a multi-document YAML stream,
  each line, each balanced `{...}`/`[...]` region, and string leaves — and refuses when a result is a mapping with an `argv` key bound to a
  sequence. It parses and inspects keys; it does not pattern-match text, which is what lets it
  catch a YAML escaped key and an anchor-bound key while *accepting* `sys.argv: list[str]` in an
  ordinary sentence. Only safe loaders are used, and alias amplification is bounded by visiting
  each shared node once rather than by counting alias-looking text. The scan **fails closed
  through a single path**: every bound funnels through one budget object and one result is built
  from it, so a bound cannot be reached and reported as a finished, clean scan. The bounds are
  sized so ordinary reading — a 201-line comparison, seventeen `*args` names, thirty-three Base64
  notes — does not reach them. And `dispatch_request` re-runs those checks on the object it is
  handed, because they live in a constructor and dispatch is the one function that talks to the
  pane.
  **What is not caught:** a format none of those loaders parses, and an instruction that
  describes a check in English — no general detector for intent is achievable. The mirror not
  writing `phase` does not contain that; it stops a mirror's opinion becoming a `verified` row,
  not a claimed verdict being produced. What makes the English case survivable is that
  completion requires a dispatch receipt the mirror is never issued.
  `references/operator-channel.md` states the contract in full, in two halves.
- **The mirror never addresses the operator (R9).** Dispatch writes only to the mirror's own pane.
- **Dispatch does not block.** No subscription is held open, no pane is polled, and there is no
  timeout parameter. The return arrives later as an event on the subscription `create_mirror`
  built. That the orchestrator *answers* while a request is outstanding is a property of the
  calling control flow and is established end to end, not by this module.

**Column ownership is checkable, not just documented.** Every register write in `mirror.py` goes
through one seam that refuses, at runtime, any column outside `role`, `max_quiet_seconds`,
`mirror_request`, `mirror_last_return`, `mirror_identity`, `mirror_subscription`, and
`mirror_pane_activity` — and only on the mirror's own row. It does not write `artifact_path`, does
not write `observed_state` (the subscriber owns that, and rewrites it on every catch-up), does not
write `last_event_at` (the subscriber owns that too, which is why the revision feed has its own
column and `check_liveness` reads both and takes the later), and never promotes its own phase. The
mirror row is identified by `role`, not by `agent`: `agent` carries the launcher's actual agent
name for every launched row, and a second writer of a shared column is the defect class this build
has paid for most.

**A restarted orchestrator can rebuild the session.** The row carries the nonce and return
markers, so `resume_mirror` reconstructs a live `MirrorSession` from the register alone — the pane
and the subscriber outlive an orchestrator that dies, and a session that outlives its only handle
is not persistent in any useful sense (R6a). The row also carries the subscription the mirror's
returns require, and `acknowledge_subscription` refuses a subscriber list that lacks it, which
turns a forgotten cross-unit handoff into a raised error instead of a clock that quietly never
advances.

**Hang detection is a clock, because nothing else can reach it.** Every other failure here appears
as a disagreement between two values; a hung mirror's values agree perfectly while the channel is
dead. So `check_liveness` compares silence against the row's declared `max_quiet_seconds`, taking
the current instant as an argument rather than reading the system clock. It reads and raises — it
writes nothing, closes nothing, demotes nothing. Every clock input must be finite: a NaN or
infinite threshold made a dead mirror report `working` forever, reaching the affirmative state the
unarmed error exists to prevent by a different door. An unarmed row raises a distinct error rather
than reporting health, an unconfirmed subscription raises a *different* distinct error rather than
being reported as a hang, and an idle mirror is never alarmed, because a mirror between requests is
legitimately silent forever.

**What tells a thinking mirror from a dead one is pane revision.** The subscriber only advances
`last_event_at` on a matched sentinel, and the mirror's only subscribed sentinel is its return
marker, so that feed alone makes the clock a per-request tolerance. `observe_pane_activity` reads
herdr's pane-output `revision` counter from a `session.snapshot` — the feed `register.py` names for
this and names this unit as the reader of — and records it on the mirror's own row. A pane still
emitting keeps the clock fed; a pane that has stopped lets it trip. It is a snapshot read rather
than a heartbeat subscription precisely because the subscriber wakes the orchestrator on every
handled event, so a heartbeat would wake the operator's channel on a timer. `MirrorLiveness`
reports which feed the answer rested on.

The first look at a counter records a baseline and does **not** advance the clock: a counter is
only evidence of emission when there is a previous one to compare it against, so treating the
first integer as an advance let a supervision loop that started late report a long-dead mirror as
`working`. A counter that goes backwards — a herdr reconnect restarts the series — re-baselines
without advancing, rather than leaving the old high-water mark stuck.

`references/operator-channel.md` carries the routing rule itself: the full exception list of work
the orchestrator does inline, why each entry is bounded by construction, the temptations that are
*not* on it, and the plain statement of what the clock does and does not establish — in
particular that the subscription path alone cannot distinguish a mirror quiet because it is
thinking from one quiet because it is dead, that pane revision can, and that a heartbeat
subscription is still not how it may be attached.

## The control flow — `scripts/runner.py`

Every other script owns one mechanism and stops at its boundary. `runner.py` is the only caller
that sees two at once, so it owns every property that lives *between* them. It decides nothing a
module already decides: it does not re-implement the queue, re-derive a route, re-run a predicate,
or interpret a reported status.

**The order, and why each step is where it is.**

```
start_run                 record_run_root, before the first launch and the first receipt
plan_run                  planning.plan; refuse a terminal row and an overlapping artifact location
approve_plan              deliver the rendered text, take the decision, THEN issue the receipt
commit                    planning.commit_plan; reservations and planned rows, no launch
reconcile_startup         name every reservation this coordinator does not own; decide each
create_mirror             the mirror row exists before its launch side effect
ensure_subscriber         start the subscriber with the complete subscription set from the register
launch_ready_children     per child, routed by durable state: a fresh or pane-less row ->
                          launch_child (spend gate -> claim -> activate_slot -> claim re-check ->
                          confirm_ready -> issue_receipt -> send the protocol); a pane-bearing row
                          with a sealed receipt and no confirmed send -> redeliver_artifact_protocol
                          (resend only, no native launch); a pane-bearing row with neither ->
                          withheld, resumable only by an explicit abandon decision
integrate_child           on a wake: settle, predicate inline, boundary, integration, record
reap_child                authorise from evidence -> reap_verified -> release_slot -> promote
stop_writers / retire     stop every writer and free every slot, then archive as one generation
```

**Approval is produced here, not asserted here.** `planning.issue_presentation_receipt` can be
called by code with no operator involved. What this establishes is narrower and real: the receipt
does not exist unless the operator channel accepted the exact rendered text and the answer was an
approval. A channel that raises, or a decline, leaves no receipt, and `commit_plan` refuses without
one. The approved plan is then persisted beside the register — `commit_plan` does not persist the
spend ceiling, and the ceiling is what every later admission decision is measured against. That
sidecar is untrusted on the way back in: it is re-rendered and its digest must equal the
presentation receipt's, which is bound to the live generation. An edited ceiling changes the
rendered text, changes the digest, and is refused.

**Reaping is authorised by evidence, never by `phase`.** `phase` is a writable column; a child that
produced nothing can set it to `verified`. Four independent things are required and none of them is
the phase alone: a dispatch receipt that unseals under this run's secret and was issued under this
store; a settlement sealed under that receipt's own attempt nonce; a recorded verdict whose result
is a pass; and the artifact still on disk, still carrying this dispatch's binding token, still
digesting to the value the verdict was recorded against. The landing is separately re-observed
against a durable snapshot taken at the verdict, because the window between the verdict and the
reap is observed by nothing else. This closes every route that does not require the run key; it
does not close the one that does — see `references/predicates.md`.

**The route the operator approved is the route that runs.** `launch_child` re-resolves model and
effort from the work shape and runtime rather than accepting them, so an explicit operator override
— the one case where the approved values are deliberately not the policy values — would silently
become the policy values at launch. The runner compares before the launch side effect and again
against the register after it, and refuses rather than adapting: a substitution needs a new plan
presentation. The comparison covers every field the operator was shown — vendor, model, effort,
scope and integration mode — not only the tier, because a landing they did not approve is false
provenance even when the work ends up isolated more than they asked for. The approval has no
destination field to compare against — planning names a mode, not a path — so the landing's
destination is instead checked against this control flow's own deterministic naming rule for it: a
mutating child's branch name, or the literal `none`. A provisioner that returns anything else was
not the one this control flow recognises as its own.

`GitLanding` decides the landing from `mutating` alone: a branch worktree for a mutating child, the
ambient checkout for a read-only one. It never sees the approved mode. Planning's vocabulary is
wider than that, so `PRODUCIBLE_INTEGRATION_MODES` names what this control flow can actually land
and `assert_plan_is_executable` refuses the rest when the plan is built, before anything durable
exists. Judgment-shaped work is refused there for the same reason: it needs an independently
dispatched verifier and this control flow has no path that dispatches one, so refusing costs
nothing where discovering it after the child ran costs the child.

**Dispatch ownership is a durable claim, not an in-memory set.** Every other guard against
launching a child twice reads state and then acts on it, and two coordinators can both pass every
read before either acts: the in-process dispatch set is local to one object, and marking a
reservation active accepts one that is already active, so it is not a compare-and-set on dispatch.
`claim_dispatch` is: under this run's generation lock it re-reads the row, re-checks the facts that
decide double dispatch, and writes one named coordinator's claim in the same transaction. A
coordinator that does not hold the claim never reaches the launcher.

That claim is also what makes an interrupted launch recoverable, in either of two shapes.
`interrupted_dispatches` offers a row as long as it is claimed, not terminal, not abandoned, and
carries no record that the artifact protocol reached it — a durable marker written only once the
child was actually told where to write. A wrapper error or a crash before the launcher returns an
identity leaves the row holding a slot with no pane at all; `reconcile_startup` asks resume-or-
abandon, and resuming re-enters the launcher's own label recovery rather than opening a second
session. A crash or a control-plane failure *after* the launcher returned — the receipt sealed, the
final send that names the artifact never confirmed landing — leaves a live pane the coordinator
cannot vouch for; resuming resends those same, nonce-bound instructions to the existing pane, never
the launcher. Neither shape is decided by how the row got there before this coordinator reaches it:
whether an explicit resume decision changed which coordinator owns the claim, or a second thread of
the same coordinator raced to take it, the claim record is re-read immediately before the one
irreversible call — the native launcher — and a coordinator whose copy no longer matches the
durable one is refused there, not merely asked to be careful. A claim is never taken over because
its holder looks dead — that is a clock in a different hat — and the claimant's process liveness is
reported to the operator as evidence for the decision, never as the decision. Abandoning a claimed
row — of either shape — also excuses it from the spend gate the same way it already excuses it from
retirement, so abandon is a real way out of a stalled run rather than a decision the gate cannot
hear.

**The subscriber outlives its parent, so a new parent has to find it.** Its identity is durable
beside the register, not only in the coordinator that started it. A restarted coordinator adopts a
running subscriber whose subscription set still matches, replaces one whose set is stale, and
otherwise starts one; without that it started a second event stream beside a first it could not
see — two writers of the same row's observed state and token counts. Reading the record, deciding,
and writing the new one back is one transaction under the run's generation lock, because two
coordinators can otherwise both read "no record" before either writes one. Retirement asks the
durable record whether *any* subscriber of this run is alive, not whether this object holds a
handle, and a stop is not treated as done until a liveness re-check confirms the process is
actually gone — a signal sent is a request, not a fact, and forgetting the record before that fact
is confirmed is how a live writer outlives the archive it should have blocked.

**The subscription set is rebuilt from the register, and the subscriber restarted when it changes.**
`Subscriber` takes its subscriptions at construction and has no API to add one mid-run. Restarting
is safe rather than wasteful, because the subscriber runs a bounded `session.snapshot` catch-up on
every accepted subscription including startup. Three classes and no fourth: the run's lifecycle
events, one nonce-bound completion sentinel and one usage needle per launched child, and the
mirror's own return subscription read from the column `mirror.py` owns. Omitting the last one loses
every mirror return and stops its clock, so it is taken from the register rather than remembered,
and `acknowledge_subscription` is called with the list the subscriber was actually given.

**Recovery is by ownership, never by a clock.** A planned reservation has no wall-clock expiry on
purpose: an operator who approves a plan and walks away must not lose the slot to a timer, and a
timer would equally steal a slot from a live but paused child. `reconcile_startup` names every
occupant it does not own — run, row, vendor, shape, tokens, state, work location, phase, pane, tab
— and takes an explicit abandon-or-resume decision for each. Launching before that has run is
refused: a coordinator that has not decided about the reservations already on this host must not
add to them.

**The changed-paths baseline is persisted at dispatch.** It is a snapshot taken at readiness, and
`issue_receipt` seals a digest over it. A restarted coordinator that re-took the snapshot would
compute a different digest and every child it had launched would fail as `receipt_mismatch` — work
lost to a restart rather than to a fault. The receipt's digest is what makes reading the stored
copy back safe.

**Reaping is fenced, because a comparison cannot cover a moving target.** Comparing a landing
digest and then closing the tab as a separate step leaves a window in which the child is still
running: it can write after the comparison and before the closure, and the row is recorded reaped
with that write never evaluated. So the producer is stopped first. The fence is written durably
*before* the tab closes — a crash between the two leaves a closed tab beside a live row, and the
record is what tells a coordinator coming back that the closure was deliberate — and the evidence
chain is then re-run behind it, against something that can no longer change. A disagreement refuses
the reap and leaves the row non-terminal with the work on disk. Only a child that has already
passed is fenced, so a failing verdict still leaves a live session to recover a defective artifact
from. The fence record and the tab's actual closure are two different facts, and a retry checks
both: an existing fence record is not treated as proof the producer stopped, so a crash strictly
between the write and the close still gets the close retried before anything downstream reads the
landing as settled.

**The acceptance receipt is sealed while the evidence still exists.** Every pass criterion is
computed from the live register, and retirement archives and deletes it along with the run key. A
receipt computed afterwards reported no child lost, no false completion and zero spend — a pass by
having nothing left to check, on the gate that blocks the next phase. `retire()` seals one first,
and `acceptance_receipt()` refuses after retirement instead of answering.

**Column ownership is checkable, not just documented.** Every register write in `runner.py` goes
through one seam that refuses, at runtime, any column outside `completion_sentinel`,
`changed_paths_baseline`, `post_verdict_observation`, `coordinator_disposition`, `dispatch_claim`,
`reap_fence` and `artifact_protocol_sent`. The seam has a second entry point for a caller already
holding the generation lock, because that lock is not reentrant and the claim transaction has to be
atomic — one seam with two doors, not two writers. Which columns may pass through either door is
checked at runtime; which *functions* may use the already-locked door is checked too, closed to
exactly the two locked dispatch transactions, so a column guard can never be quietly widened by a
caller that never takes the lock at all.

```python
from pathlib import Path
import runner  # scripts/runner.py, on sys.path for the invoking skill/command

coordinator = runner.Coordinator(Path.cwd(), run_id="run-abc", ...)
coordinator.start_run()
request = runner.parse_outcome(argument, issue_reader=..., root=Path.cwd())
plan = coordinator.plan_run(request, children, ceiling=250_000)
coordinator.approve_plan(plan)
coordinator.commit()
coordinator.reconcile_startup()
coordinator.create_mirror()
coordinator.ensure_subscriber()
coordinator.launch_ready_children()
```

`references/phase-1-acceptance.md` defines the acceptance gate: one real unrelated task, two
children on different vendors, one mutating and one read-only, one deliberate mid-run restart, five
pass criteria computed from the durable record, and evidence at `.orchestrate/runs/<run-id>/`.

## What is deliberately not here

No `commands/` entry — `/orchestrate` lands with the unit that needs an invocable surface (KTD2).
Reading an issue is injected rather than performed: `parse_outcome` accepts an issue reader and
never reaches a network itself.

The runner calls `reserve_slot` through `commit_plan`, `activate_slot` immediately before
`launch_child`, and `release_slot` only after a recorded reap. `launch_child` and `reap_verified`
still do not call admission themselves, and should not: only the control flow sees both operations
succeed.
