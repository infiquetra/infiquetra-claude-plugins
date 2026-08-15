---
name: orchestrate
description: The orchestrate register, tracked herdr subscriber, write-ahead child session lifecycle, completion gate, and paired mirror session for multi-vendor runs, with interaction readiness, scoped worktrees, nonce-bound sentinels, reconnect catch-up, bounded predicates on settled run-bound artifacts, verified integration, recorded reaping, distilled mirror returns under an enforced byte bound, and clock-based mirror hang detection. No routing or spend gate yet. Triggers on "orchestrate register", "orchestrate subscriber", "orchestrate session lifecycle", "orchestrate completion", "orchestrate predicate", "orchestrate mirror", "the operator channel", "mirror hang detection", "herdr event catch-up", "the run register".
---

# orchestrate — register, event subscriber, session lifecycle, completion, and the mirror

`orchestrate` coordinates multi-vendor herdr sessions: Claude, Codex, Grok, Muse, Qwen, and agy
children dispatched under one operator-driven run, aggregated back through a mirror and woken by a
subscriber holding herdr's event socket across turns. This skill currently ships **five pieces of
that system: the register, subscriber, child session lifecycle, completion gate, and mirror**. The register is the whole state model (KTD5) and the
Claude↔Codex handoff seam (R12). The subscriber holds protocol 19 event streams, wakes the
orchestrator, and performs reconnect catch-up (KTD3/KTD12). The session lifecycle owns write-ahead
launch, recovery, interaction readiness, landing isolation, scope checks, and recorded reaping.
Completion is the only path to `verified` (R5): a bounded, typed predicate run inline by the
orchestrator on a settled, run-bound artifact, inside a clean boundary, with integration to the
recorded destination verified before a child can be reaped. The mirror is the home for the
orchestrator's own unbounded work, so the operator's channel stays answerable.
Routing, spend gating, and the `/orchestrate` command itself land in later units of
`docs/plans/2026-08-12-orchestrate-plugin-plan.md` and are deliberately absent here.

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
register.upsert_row(
    root, "child-1", {"phase": "planned", "agent": "claude"}, run_id="run-abc"
)
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
and checks declared `artifact_path` presence. Its `observed_state_source` records whether the value
was directly observed or inferred from pane/tab presence. A catch-up failure is reported but does
not close the accepted event stream. It does not evaluate predicates.

The subscriber only accepts `pane.output_matched` entries built from a complete substring sentinel;
a regex or ordinary-text output match is valid for Herdr generally but is a startup error here
because it cannot satisfy the subscriber's identity guard. More than one sentinel subscription may
target the same pane, so readiness and completion interactions can both remain active.

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
  `tomllib` and `ast.literal_eval` — whole text, each line, and string leaves — and refuses when
  a result is a mapping with an `argv` key bound to a sequence. It parses and inspects keys; it
  does not pattern-match text, which is what lets it catch a YAML escaped key and an
  anchor-bound key while *accepting* `sys.argv: list[str]` in an ordinary sentence. Only safe
  loaders are used. The scan **fails closed**, refusing material it could not finish examining;
  and `dispatch_request` re-runs those checks on the object it is handed, because they live in a
  constructor and dispatch is the one function that talks to the pane.
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

## What is deliberately not here

No `commands/` entry (`/orchestrate` lands with the units that need an invocable surface — KTD2),
no planning or vendor routing, no admission control, and no spend gate. The mirror's mechanisms are
here; the supervision loop that calls the clock on a schedule, and the control flow that proves the
operator is answered while a mirror request is outstanding, belong to the composition unit.
