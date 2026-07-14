# The mid-run adjustment envelope (schema v1)

A run-start intent envelope captures the operator's directives *before* a run starts. The
**adjustment envelope** is its mid-run counterpart: one durable, versioned control file that a
`/work` or `/outcome` run polls at its existing segment/frontier boundaries so an operator or a
worker can steer a live run — pause, drain, stop, re-tier, add a reviewer — **without killing the
run or hand-editing state**.

One file, five writers. This is the load-bearing scope decision: quiesce, plan-declared pause
points, the worker-raised andon-cord, and the coordinator strand-halt (#433) all write into the
**same** envelope. A design that gives each writer its own file is out of scope. The
reversible-mutation default (the undo ledger) is the adjacent concern that decides *when a pause
is even needed*.

Implemented by `plugins/saga/scripts/adjustment_envelope.py` (parser + poll + writers) and
`plugins/saga/scripts/undo_ledger.py` (the reversible-mutation default). Polled by
`plugins/saga/scripts/outcome.py` (`advance` tick boundary) and the `/work` segment boundary.

## File location

Per-run, in the run's private, git-ignored state:

```
.saga/adjustment-envelope.json    # the polled control file
.saga/undo-ledger.jsonl           # the reversible-mutation act log (inverse ops)
```

Both are git-ignored (`.gitignore`) so no run log ever dirties `git status --porcelain`.

## Schema (version 1)

```json
{
  "version": 1,
  "directives": [
    {"directive": "quiesce",      "writer": "operator", "reason": "pausing the fleet"},
    {"directive": "pause_after",  "writer": "plan",     "segment": "code-review",
     "resume_tier": "opus:xhigh"},
    {"directive": "andon_halt",   "writer": "worker",   "scope": "leaf-3",
     "reason": "tests look fabricated"},
    {"directive": "re-tier",      "writer": "operator", "tier": "sonnet:high"},
    {"directive": "add-reviewer", "writer": "operator", "reviewer": "security"},
    {"directive": "cancel",       "writer": "operator"},
    {"directive": "abort",        "writer": "operator"}
  ]
}
```

`version` is a required int and must equal the parser's `ENVELOPE_VERSION` (currently `1`); any
other value fails closed. `directives` is a list; each entry names one directive from the closed
vocabulary below.

### Directive vocabulary

| directive | writer(s) | effect at poll | extra fields |
|---|---|---|---|
| `quiesce` | operator | **drain** — in-flight leaves finish, dispatch nothing new, surface a resume point | — |
| `pause_after` | plan | **pause** at exactly the named `segment`; resume only on an explicit continue (acknowledge) | `segment` (required), `resume_tier`, `resume_context` |
| `andon_halt` | worker / reviewer / coordinator | **halt** — block the next wave/tick from dispatching; write an operator-surface HALT record. The `coordinator` writer is the #433 strand-halt: a posture `repost` that would strand an in-flight leaf's irreversible-op authorization raises this (via `raise_strand_halt`) instead of silently applying or dropping the amendment | `scope` |
| `re-tier` | operator | amendment honored on resume (no stop) | `tier` (required) |
| `add-reviewer` | operator | amendment honored on the next review cycle (no stop) | `reviewer` (required) |
| `cancel` | operator | **halt** — stop this run at the next boundary | — |
| `abort` | operator | **halt** — hardest stop at the next boundary | — |

Universally optional fields on any directive: `reason`, `at`, `id`, `acknowledged`.

### Poll precedence

`halt > drain > pause > proceed`. HALT always wins — the envelope **composes with, never weakens**,
the `/outcome` campaign's existing HALT-not-degrade precedence (`{#outcome-backend-degrade-stance}`,
`docs/engineering-journal/DECISIONS.md`). An `andon_halt`/`cancel`/`abort` here never degrades to a
lower rung; it just stops. Amendments (`re-tier`, `add-reviewer`) never stop the run; they accumulate
for the boundary consumer to apply on resume.

## Fail-closed contract (R3)

The parser is the trust boundary for operator/worker directives, so it **fails closed** — it raises
`EnvelopeError` (naming the offending token) and the run HALTs and surfaces it, rather than silently
proceeding, on any of:

- an unknown directive name (`unrecognized directive: 'frobnicate'`);
- an unknown top-level or per-directive key;
- a missing required field (`pause_after` without `segment`, etc.);
- a wrong/unsupported `version`; an unrecognized `writer`;
- malformed JSON, or a present-but-unreadable file.

An input the parser cannot fully model is an error, never an enumerate-and-skip pass. An **absent**
file is not an error — it means "no directives, proceed".

## Poll boundaries (no new poll loop)

The envelope reuses boundaries that already exist; it does **not** add a standing poll loop:

- **`/outcome` tick boundary** — `advance` re-reads the envelope each tick, after the in-flight
  harvest drains and before dispatch, so a `quiesce`/`andon_halt`/fail-closed directive stops the
  next tick from dispatching. The decision is surfaced on `AdvanceResult.adjustment`. Scope
  honesty: `advance` polls with no segment identifier, so **`pause_after` never fires at an
  `/outcome` tick boundary** (outcome ticks have no plan segments) — the reachable `/outcome`
  directives are `quiesce` and `andon_halt`. A proceed decision carrying standalone amendments
  (re-tier / add-reviewer) is surfaced on `AdvanceResult.adjustment` with `applied: false` — the
  coordinator still never applies these envelope amendments to its own dispatches. #433 shipped
  the *posture* renegotiation path (`outcome repost` — sandbox / degrade policy / run mode /
  ceremony gates, with `intent_revision` dispatch-time overlap); routing the standalone
  re-tier/add-reviewer directives through that overlap machinery so `applied` can become true
  remains the #594 R2 follow-up.
- **`/work` segment boundary** — `/work` polls the envelope at each phase/segment boundary (see
  `skills/work/SKILL.md`), honoring a `pause_after: <segment>` deterministically and applying any
  `resume_tier`/`resume_context` amendment on the explicit continue.

Delivery scope: the envelope lives at the run's private `.saga/adjustment-envelope.json` under the
polling command's `--repo-root` — per-worktree, while outcome state is deliberately
worktree-shared. A worker in an isolated worktree raising andon writes its OWN worktree's
envelope; delivery to a coordinator polling a different root is not yet wired (follow-up).

## The reversible-mutation default (R6, R10, R11) — why pauses are rare

Absent an explicit `pause_after`, **only irreversible actions pause by default**. Reversible
mutations proceed under an act-log-inverse-notify path instead: the run performs the mutation, writes
a proven inverse to `undo-ledger.jsonl`, and notifies the operator post-hoc. `/undo` replays the
inverse.

Enforcement honesty (v1): the act-log-inverse path is **prompt-mediated** — the `/undo` command
and the skills instruct runs to call `undo_ledger.record()` around reversible mutations, but no
production mutation site (mission-control board/label/issue writes included) is mechanically
wired to the ledger yet. The ledger, replay (`undo` CLI), and disposition classifier are real and
tested; the producer wiring is tracked as follow-up. Until then an unrecorded reversible mutation
simply has nothing for `/undo` to replay.

Registered reversible operations (the v1 set — the fleet is **not** backfilled):

| op type | forward | inverse |
|---|---|---|
| `board_move` | move board status | move back to prior status |
| `label_change` | set labels | restore prior labels |
| `issue_edit` | set an issue field | restore prior value |
| `saga_branch` | create a branch | delete it |
| `saga_pr` | open a PR | close it |

`undo_ledger.mutation_disposition(op_type)` returns `"proceed-with-undo"` for a registered op and
`"pause"` for any op with no registered inverse. This is what makes "only irreversibles pause by
default" true rather than aspirational: without a working inverse, an operation is definitionally not
reversible and falls back to the gated pause (R11). `undo_ledger` is deliberately **gh-free** (it
computes and records inverses; the mutation-owning subsystem, e.g. mission-control, replays them), so
it never crosses the gh write-ownership lane.

## Writer helpers (the producers)

```python
adjustment_envelope.raise_quiesce(path, reason=...)                 # operator writer 1
adjustment_envelope.declare_pause_after(path, segment, resume_tier=...)  # plan writer 2
adjustment_envelope.raise_andon(path, writer="worker", scope=...)  # worker writer 3
adjustment_envelope.raise_strand_halt(path, scope=..., reason=...)  # coordinator writer (#433 R6)
adjustment_envelope.acknowledge_pause(path, segment)               # the explicit continue signal
undo_ledger.record(ledger, op_type, target=..., before=..., after=...)  # reversible default
undo_ledger.undo(ledger, state)                                    # the /undo replay path
```

CLI: `python3 adjustment_envelope.py {show,quiesce,andon,continue}` and
`python3 undo_ledger.py {show,ops}`.

## Threat model / self-attestation

Directive records are **self-attested** by whoever wrote the file; the parser authenticates the
*shape*, not the *authority* of the writer — an `andon_halt` claiming `writer: "reviewer"` is trusted
to be from a reviewer. Authority binding is out of scope for v1: the file lives under the run's
private `.saga/` state, writable only by the run's own operator/worker processes. Likewise the undo
ledger records *what a leaf claims it did* (its reported `before`/`after`); it authenticates that the
op type is reversible, not that the reported world state is true.
