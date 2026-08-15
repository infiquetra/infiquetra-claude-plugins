# The operator's channel, and the mirror that protects it

The highest-severity failure this plugin exists to prevent is not a wrong model or a run that
overruns. It is **the operator's channel dying under supervision load**: the operator asks a
question, the orchestrator is busy doing work, and the question is never answered. Two of the
questions that went unanswered, verbatim:

> *"Can we use herdr to open up couple other sessions? maybe we need three tabs for codex,
> claude, antigravity to run those proofs in parallel? thoughts?"*

> *"where do we stand on this... the whole session is very, very long"*

The same unanswered question recurs word for word across four separate sessions. That is what
this document is for.

```
   WITHOUT A MIRROR                      WITH A MIRROR

   operator ──?──► orchestrator          operator ──?──► orchestrator
                        │                                     │  answers immediately
                   (doing work)                               ▼
                        │                                 ┌────────┐
                   ...busy...                             │ MIRROR │ ← the work happens here
                        │                                 └────────┘
                    no answer                                 │
                        │                              distilled conclusion
                   operator gives up                          │
                   and checks tabs by hand              operator informed
```

## The rule

**Work goes to the mirror by default.** The orchestrator's channel is for routing, deciding,
recording, and answering — and nothing else.

The rule "the orchestrator must not do work" is not enough on its own, because work genuinely
has to happen. A rule with no home for the work is a rule that gets broken the first time
something needs comparing. The mirror is the home. Children do the *outcome's* work; the mirror
does the *orchestrator's* work.

The exception list below is deliberately short, and every entry earns its place by being
**bounded by construction** — not bounded because it usually turns out small. Anything not on
this list goes to the mirror **even when it looks trivial**, because "this one is quick" is the
sentence that ends with a dead channel.

## The exceptions, in full

### 1. Answering the operator

The orchestrator answers. There is one voice on this channel and it is the orchestrator's — the
mirror never speaks to the operator (R9). One voice, or the channel problem comes back wearing
a different hat.

*Bounded because:* an answer is the orchestrator's own output. It consumes nothing new.

### 2. Reading and writing the run register

`register.read_rows`, `register.upsert_row`, and the status views built on them.

*Bounded because:* the register is one flat document whose row count the orchestrator itself
fixed at admission. It is the orchestrator's own state, not material under study.

### 3. Running a declared validity predicate

`completion.evaluate_completion`, and the predicate it runs, execute **inline** in the
orchestrator's own process tree. This is not a preference; it is KTD6, and it is the one
exception that must never be optimised away. Routing a predicate through the mirror turns
verification back into a **claim**: the mirror reports a pass, the orchestrator never sees the
bytes and cannot re-check, and the evidence-failure class — the largest and most damaging in
the corpus — reappears one layer up with no second reader.

The mirror does unbounded *reading*. It does not do *deciding*.

*Bounded because:* a predicate is a closed schema — a fixed argument vector with a mandatory
`timeout_seconds` and `max_output_bytes`, rejected outright rather than clamped when it exceeds
either, and rejected outright when it is shell text. Its output cannot be large; the schema
will not let it.

### 4. Session control

Launching a child or the mirror, confirming readiness, sending a dispatch line, checking a tab,
reaping a verified child: everything in `session_lifecycle.py`.

*Bounded because:* each call returns a fixed-shape identity record or an error. None of them
returns repository content, a file, or a transcript. The one that reads a pane
(`HerdrControl.pane_text`) is used for a trust-prompt check and for collecting a mirror return
that has already been bounded — never to bring repository material into the channel.

### 5. Deciding

Choosing which child gets which work, which vendor, which tier. Admitting a queued child.
Recording a decision. Parking an operator's question with a reason.

*Bounded because:* a decision is a sentence the orchestrator writes, not a document it reads.

## What is deliberately **not** on the list

Each of these looks like one quick command. Each of them is mirror work.

| It looks like | It is |
|---|---|
| "just reading one file to see what it says" | bulk reading — mirror |
| comparing two children's reports | synthesis — mirror |
| summarising a long log, a diff, or a PR | distillation — mirror |
| searching the repository for where something is done | survey — mirror |
| checking what a child actually produced, in prose | reading — mirror (the *predicate* is inline; reading the artifact to form an opinion is not) |
| "skimming" a requirements document before deciding | bulk reading — mirror |
| reconstructing what happened earlier in the run | recall — mirror |

The distinction in row five is the one worth re-reading. Running the predicate is exception 3
and stays inline. Reading the artifact to form a view about it is mirror work. Those are two
different acts on the same file, and only one of them is bounded.

## What the mirror guarantees, mechanically

These are enforced in `skills/orchestrate/scripts/mirror.py`, not merely intended.

- **A return over its declared bound is rejected, not truncated.** Truncation would turn an
  oversized return into an apparent success, which is worse than a failure. The rejection
  carries the byte count and never the material — an error that quoted the return would perform
  the very absorption it is reporting. The mirror protects the orchestrator's *time*, not its
  context: the orchestrator still reads whatever comes back, so a 50 KB "distillation" degrades
  the main session anyway.
- **The bound a request may declare is itself capped** (16 KiB, default 4 KiB). This
  requirement does not erode by someone deleting it. It erodes by someone raising it.
- **The mirror is never *asked* for a verdict through this API.** That is deliberately weaker
  than "a predicate never reaches the mirror", which is what this page previously claimed. That
  claim was false, and a published guarantee that is false is worse than a narrower one that
  holds. What is actually enforced:

  - Deciding request kinds are refused by name.
  - An instruction carrying a machine-readable predicate declaration is refused. The detector
    keys on the declaration's *signature* — the name `argv` bound to a value — rather than on one
    serialisation of it, so JSON, a YAML block or flow mapping, TOML, a Python literal, a string
    nested inside another object, unicode-escaped braces, and Base64 are all caught. Enumerating
    serialisations is a race the enumerator loses; keying on the signature is not.
  - The scan **fails closed**. An instruction it cannot finish examining within its budget is
    refused rather than passed. The previous revision reported "clean" on exhaustion, which
    turned a denial-of-service bound into the bypass: a real declaration parked behind 512 decoy
    braces was never inspected, and was accepted.
  - `dispatch_request` **re-runs those checks on the object it is handed**. They live in
    `MirrorRequest`'s constructor, and dispatch is the one function that talks to the pane, so
    reading attributes off whatever arrived left them out of the path that matters — any object
    with the right attribute names satisfied it.

  **What is not enforced, stated because it is the part that matters.** An instruction that
  describes a check in ordinary English is not detectable by any scanner, and a mirror so
  instructed can run it: the live agent on the far side of the pane is itself a program executor,
  and its runtime's workspace-write posture contains nothing inside the workspace. The mirror not
  writing `phase` does **not** contain this. It stops a mirror's opinion becoming a `verified`
  row; it does not stop a claimed verdict being produced, and a claimed verdict with no second
  reader is precisely the failure R6b names.

  What remains true is narrower and worth having: `completion.evaluate_completion` is the only
  path to `verified`; it requires a dispatch receipt the mirror is never issued; nothing here
  returns anything completion accepts as evidence; and a mirror return is bounded material the
  orchestrator reads with its own eyes rather than a verdict delivered behind its back. The
  control for the English case is the routing rule on this page — a rule, labelled as a rule.
- **The mirror has a register row from creation**, written before any launch side effect, so a
  mirror whose launch failed is visible rather than absent. The row carries what a restart needs:
  `resume_mirror` rebuilds a live session from it, because the pane and the subscriber outlive an
  orchestrator that dies and a session that outlives its only handle is not persistent in any
  useful sense.
- **A subscriber started without the mirror's subscription is loud, not silent.**
  `acknowledge_subscription` compares the mirror's expected subscription against the list the
  subscriber was actually given and refuses a mismatch; until something confirms it,
  `check_liveness` raises `MirrorSubscriptionUnconfirmedError` rather than reporting a state. A
  mirror nobody is listening to and a hung mirror produce identical silence, and reporting the
  first as the second sends the operator hunting a hang that is not there.
- **The mirror never addresses the operator.** Dispatch writes only to the mirror's own pane.
- **A repository-visible change during a request window is observed and recorded.** The mirror is
  read-only by contract and nothing prevents it writing: `mutating=False` keeps it in the ambient
  checkout, it is not a write fence, and because the mirror declares no artifact it never reaches
  the post-hoc scope check either — so a violation used to be not merely unprevented but
  unobserved. Detection is now on the request/return path. It is reported rather than raised, and
  `assert_no_repository_change` is opt-in, because this session reads the operator's live working
  tree: the operator's own edit lands in the same window and attribution is not established.
  Isolation was rejected on purpose — a worktree would give the mirror a tree nobody is working
  in, which is the one thing it must not read.

## When the mirror is busy

An operator question is **never silently dropped** (R8). If a request is already outstanding,
a second dispatch is refused explicitly with the outstanding request's id. The orchestrator
then does one of two things, and says which:

- answers from what it already knows, or
- **parks the question with a reason** — "the mirror is comparing the two reports; I will have
  this in a moment" — which is an answer, not silence.

## The hang, and the honest limit of its detector

Every other failure in this system shows up as a **disagreement**: expected state against
observed state, declared artifact against artifact on disk, claimed completion against a
predicate that runs. A hung mirror produces no disagreement at all. Its expected state and its
observed state agree perfectly, every child still looks healthy, and the operator's channel is
dead — precisely the failure the mirror exists to prevent, arriving through the mirror itself.

So the only detector is a clock: `last_event_at` exceeding the declared `max_quiet_seconds` on
the mirror's row. `mirror.check_liveness` takes the current instant as an argument rather than
reading the system clock, so its test does not sleep.

**State plainly what it does and does not establish.** It asserts that the row has not been
observed emitting for longer than the operator declared it should ever be silent. What counts as
"observed" is the whole question, and there are two feeds:

- **`last_event_at`** — written by the subscriber when a matching sentinel appears in the
  mirror's pane. The mirror's only subscribed sentinel is its return marker, so within one
  request this never moves. On its own it makes `max_quiet_seconds` a **per-request tolerance**
  rather than a within-request liveness probe.
- **Pane revision** — herdr's pane-output counter, read by `observe_pane_activity` from a
  `session.snapshot` and recorded on the mirror's own row. **This is what distinguishes a mirror
  that is quiet because it is thinking from one that is quiet because it is dead**, and it is the
  feed `register.py` names for exactly this purpose, naming this unit as its reader. The
  measurement behind that is in the journal
  (`LEARNINGS.md#pane-revision-is-the-liveness-signal`): over one real dispatch window the
  lifecycle counter `state_change_seq` moved twice and then sat still for minutes while the
  session worked hard, while `revision` moved roughly 47 times.

An earlier revision of this page said nothing distinguishes the two. That was too strong, and the
correction matters more than the original claim did. The honest sentence: **the subscription path
alone cannot distinguish them; pane revision can; and a heartbeat subscription is still not how it
may be attached.**

- A within-request heartbeat *subscription* remains deliberately unbuilt. The subscriber wakes
  the orchestrator on every handled event, so a heartbeat subscription would wake the operator's
  channel on a timer — the exact channel-load failure this unit exists to prevent. Reading a
  snapshot goes nowhere near that wake path, which is why the revision feed is a supervision-tick
  read rather than a subscription.
- The revision feed only exists while something is ticking it. `check_liveness` reports which
  feed its answer rests on in `reference_source`, so "working" from a stale clock and "working"
  from a live one are not the same word. With no ticks, the clock degrades to the per-request
  tolerance above — set `max_quiet_seconds` accordingly.
- Corroborating the clock with herdr's `agent_status` would make it **worse**, not better.
  Vendor lifecycle detectors are wrong in vendor-specific ways: one runtime reports `idle`
  while working, another reported settled from launch straight through completion. A second
  detector that agreed would supply false confidence rather than a second reader. Pane revision
  is not that: it counts output, not opinion.

The alarm is therefore advisory. `check_liveness` reads and raises; it writes nothing, closes
nothing, and demotes nothing. What to do about a quiet mirror — probe the pane, re-ask, replace
it, tell the operator — is a decision, and decisions belong to the orchestrator.

An idle mirror is legitimately silent forever, so the clock is armed only while a request is
outstanding. A detector that alarmed between requests would fire on every healthy run, and an
alarm that always fires is an alarm nobody reads.

## Context is a managed resource

The mirror is persistent for the life of the orchestration — for prompt-cache benefit and for
continuity of context. That persistence has a cost: **a mirror that has silently degraded is
worse than no mirror, because the orchestrator will still believe its answers.**

So its context is directed, not left to fill: `mirror.request_context_reset` compacts or clears
it on the orchestrator's instruction, at a natural boundary rather than mid-request. Only the
Claude Code commands are established here; every other runtime is refused rather than guessed,
because sending an unrecognised slash command puts prose into a coding agent's input — a silent
no-op that looks exactly like a reset.
