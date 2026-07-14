# Gate Records — durable approvals with a linted operator-absence contract (#371)

<!-- gate-exempt: this reference documents the gate-record mechanism itself; it fires no gate -->

A gate is a **record**, not an `AskUserQuestion` call. The record — question, options, a
machine-readable `absence_behavior`, the eventual answer, the answerer, timestamps, transport —
is persisted **before** any transport is invoked, and consumers read the persisted record
(`poll`), never a widget call's raw return value. `AskUserQuestion` is one pluggable transport
among several; a widget timeout, dropped session, or primitive error can no longer be
indistinguishable from an affirmative answer. This generalizes the `engine_dispatch.satisfy_gate()`
precedent ("structural refusal, not prompt discipline", `{#external-engines-never-gatekeepers}`)
from the external-engine gate to the fleet's operator-approval gates — without touching
`satisfy_gate()` itself, which remains the sole authority for that gate.

Engine: `plugins/saga/scripts/gate_record.py` (stdlib-only). Lint:
`plugins/saga/scripts/lint_gate_absence_contract.py` (CI, fail-closed). Store: `.saga/gates/`
(git-ignored, repo-local, one directory per gate).

## Record store — derived-on-read, write-once commits

| File | Role | Mutability |
| --- | --- | --- |
| `.saga/gates/<gate_id>/record.json` | the declaration | write-once (`os.link`), immutable |
| `.saga/gates/<gate_id>/resolution.json` | the answer | write-once (`os.link`) — the commit point |
| `.saga/gates/<gate_id>/absence.jsonl` | absence-event audit | append-only, repeats recorded |
| `.saga/gates/<gate_id>/answer.json` | file-sentinel inbox | written by operator/router, ingested by `poll` |

Status is **derived on every read** (`pending` / `answered` / `answered-by-default` / `halted` /
`escalated`), never held in memory across a session boundary — a restarted session re-reads the
same pending gate instead of re-prompting (`open` on an identical declaration resumes; a mismatch
errors). Of two concurrent satisfy attempts on a local POSIX filesystem, exactly one creates
`resolution.json`; the other fails loudly. A crash between the safe-default resolution commit and
its audit-event append loses only the audit line — the resolution self-describes via
`applied_by_absence`, so the record can never claim a live answer it did not get.

## Declaration schema (v1, closed — unknown keys and wrong types are errors)

```json
{
  "schema_version": 1,
  "gate_id": "code-review-fixer-routing-a1b2",
  "question": "Dispatch the P1 findings to a fixer?",
  "options": ["dispatch", "fix-inline", "skip"],
  "absence_behavior": "HALT",
  "safe_default": null,
  "transport": "ask-user-question",
  "opened_by": "saga:code-review",
  "created_at": "2026-07-14T18:00:00+00:00",
  "binding": {"outcome_id": "campaign-x", "spec_revision": 3}
}
```

`binding` is the dispatch-era hook for downstream consumers (#449): a closed vocabulary —
`outcome_id` / `saga_id` / `leaf_id` (strings), `spec_revision` / `intent_revision` (integers) —
validated strictly and filterable via `gate_record.py list --binding k=v`. A gate opened for an
outcome-campaign decision binds the spec/intent revision it was asked under, so a consumer can
refuse an answer minted under a superseded era, the same way dispatch records carry their
dispatch-era posture (#433).

The resolution sub-record carries `answer`, `answerer`, `answer_transport`, `answered_at`,
`provenance` (`operator` | `absence-safe-default`), and `applied_by_absence`. A decision applied
by absence always **says so** — never a silently-defaulted answer.

## Absence behaviors (default `HALT`)

Declared at `open`; `resolve-absent` applies **the declared behavior only** — the caller cannot
pick a different one at resolution time. Silence therefore never resolves to an implicit "yes":

- **`HALT`** (default — the fleet's HALT-not-degrade posture): the gate stays unanswered,
  `consumable: false`; consumers stop. A late live answer may still satisfy it. Repeated
  `resolve-absent` calls append further audit events — never deduplicated, so repeat silence is
  never under-reported (the #598 item-1 lesson applied from day one).
- **`safe-default-with-record`**: the `safe_default` declared at `open` (must be one of
  `options`; declaring it under any other behavior is an error) becomes the answer with
  `applied_by_absence: true` and answerer `absence:safe-default`.
- **`escalate`**: surface `compose_escalation_notice()` to a human channel and HALT pending a
  live response. No new notification surface — the session relays the notice over whatever
  channel is connected (redis-channel / Discord), and the eventual reply satisfies the record
  with its real arrival transport as provenance.

## Transports — the seam, and what "pluggable" means here

A transport contributes only how an answer **arrives**; the schema, `poll`, and `satisfy` are
transport-agnostic:

- **`ask-user-question`** (push): the session that ran the widget pushes the captured answer via
  `satisfy`. The record layer never trusts the widget's return value directly — the persisted
  record is the truth consumers read.
- **`file-sentinel`** (pull): an operator or router process drops
  `.saga/gates/<gate_id>/answer.json` (`{"answer": ..., "answerer": ...}`, strict); `poll`
  ingests it through the **same** `satisfy` path with identical validation and record semantics.
  A malformed sentinel raises — surfaced, never skipped. A sentinel dropped for a push-transport
  gate is a transport mismatch and errors rather than being ingested.

Late/live answers over `redis-channel` / `discord` are accepted at `satisfy` with the real
transport recorded (the escalate flow's whole point).

## Operator-absence contract — the deliberate position (binding on #449)

**Derived provenance is not operator presence.** Answerer strings are classified
(`classify_answerer`): a reserved prefix — `carried-forward:` (the #433 tightening-repost
approval provenance) or `absence:` (this module's safe-default resolutions) — classifies as
`derived` / `absence`; anything else non-empty classifies as `operator`. `satisfy` **rejects**
any non-`operator` answerer: a carried-forward approval can never satisfy a gate record as a live
answer, in either direction of the seam (direct `satisfy` and file-sentinel ingestion). Both
directions are test-asserted, including against the literal provenance string a real
`outcome_intent.repost` writes into `approvals/r<rev>.json`.

What this does **not** change: the R20 frontier approval (`outcome_decompose.approve_frontier` /
`frontier_approved`) keeps its #433 contract unchanged — a pure-tightening repost still carries
the prior approval forward for the **frontier dispatch gate**. The position taken here is that
such a carried-forward approval is *derived* authority, valid for what #433 defined it for, and
does not constitute an operator being present at a gate. A #449 consumer that wants a
carried-forward frontier approval to authorize a merge-class write must therefore mint a live
gate-record answer instead — `is_operator_answerer()` is the exported predicate to classify with.

**The #598 item-2 asymmetry is composed with, not closed, and here is which and why.** A live
pure-tightening `set-intent` attach does **not** carry the frontier approval forward while
`repost` does. Under this contract the asymmetry is *presence-conservative*: the `set-intent`
path demands a fresh **live** operator approval where `repost` derives one — it costs one extra
re-approval and never skips one, and because derived provenance never counts as presence, no
gate-record consumer can treat the two verbs differently by accident. Closing the asymmetry
(extending carried-forward provenance to a second verb) would move in the opposite direction of
this leaf's presence contract, and it is #433 machinery already queued in #598 — deliberately not
touched here.

## The lint — "we forgot to say what silence means" is a build failure

`lint_gate_absence_contract.py` runs in CI over `plugins/saga` + `plugins/team-execution`:

- **Markdown**: every `AskUserQuestion` mention in a scanned `*.md` (basenames `CHANGELOG.md` /
  `README.md` excluded) must sit in a markdown section carrying a marker — a gate-record
  declaration (`id=` a gate-id slug, `absence=` one of `HALT` / `safe-default-with-record` /
  `escalate`, `transport=` one of `ask-user-question` / `file-sentinel`), like
  `<!-- gate-record: id=example-gate absence=HALT transport=ask-user-question -->`, or a non-gate
  exemption like `<!-- gate-exempt: prose mention, fires no gate -->`. An HTML comment beginning
  with `gate-` that does not parse exactly as one of these fails the build. Coverage granularity
  is the section: a new mention added inside an already-marked section rides that marker — the
  build-failure guarantee holds for new sections and new files, not for additions beside an
  existing marker (named in the lint's residuals, deliberately traded against one-marker-per-
  mention noise).
- **Python**: every `open_gate(...)` call must pass a literal, in-vocabulary
  `absence_behavior=` keyword (the runtime API defaults to `HALT`; shipping code must still
  declare — defense in depth). The module *defining* `open_gate` is the primitive's own surface,
  excluded from call-site enumeration by documented rule and reported as such.
- **Ratchet baseline** (`gate_absence_baseline.json`): legacy files not yet migrated are pinned
  with exact uncovered-mention counts and reported as `pending migration — surfaced, not
  enforced (applied: false)`. Any drift — count grew, count shrank, file vanished, stale entry —
  fails the build. New files are fully enforced from their first mention.

## Consumers of a gate record — enumerated (the #433 lesson 9)

Every phase of a record (pending, halted, escalated, answered, answered-by-default) carries the
full schema for every consumer:

1. **The opening skill/session** — `open` → transport → `satisfy` / `resolve-absent` → `poll`.
   v1 producers: the six migrated saga gate sites (brainstorm, code-review, founder-review,
   ideate, investigate, loop) plus their marker declarations.
2. **The CI lint** — consumes declarations (markers / call-site keywords), not runtime records.
3. **Operator audit** — `gate_record.py list [--status ...] [--binding k=v]`.
4. **#449 envelope-authorized merge — landed WITHOUT consuming gate records (v1 honesty
   note).** #449 shipped its token as a separate store artifact (`envelope_token.py`,
   `references/envelope-token.md`) bound to the committed envelope's content fingerprint +
   `intent_revision`; its authorization path reads the token lane fresh per merge attempt and
   does **not** read gate records, so the record's closed v1 schema gained no token keys (the
   forecast additive-within-v1 step was not needed). What #449 DOES inherit from this
   contract, binding on any future attended flow: a carried-forward frontier approval never
   authorizes a merge-class write — a flow that mints a token from an operator's live gate
   answer must classify with `is_operator_answerer` (`carried-forward:` / `absence:`
   provenance never mints) and bind the dispatch era via `binding.spec_revision` /
   `binding.intent_revision`. If that flow ever puts token keys ON the record, the schema is
   closed per `schema_version` and validation is exact-keys (missing keys are errors too), so
   the edit must make the new key optional in the validator or migrate written records — a
   deliberate schema step, not a free field drop-in.

Gate records deliberately do **not** flow through the `/outcome` consolidated report in v1: the
report's ambiguity tier currently filters halt receipts out by `kind` (#597), and surfacing gate
records there before that filter is fixed would inherit the same invisibility bug. When #597's
report fix lands, gate records can join the report tier with a `kind` the filter actually matches.

## Honest bounds — what a gate record does and does not prove

<!-- gate-exempt: bounds discussion of the mechanism; fires no gate -->

- `answerer` and `opened_by` are **self-attested** strings relayed by the session; the record
  proves the declared contract, the timing, the transport, and the provenance **class** of the
  answer — not the biological identity of the answerer. Sender authorization belongs to the
  transport's access policy upstream (the `outcome_gate_transport` stance).
- The record layer cannot force a rogue consumer to consult it. What the tests demonstrate:
  `poll` never returns a consumable answer for a silent gate, and every silence path resolves to
  the declared behavior. The lint makes undeclared sites visible at build time; a runtime
  consumer that bypasses the record layer entirely is out of contract and out of this
  mechanism's reach — that residual is bounded by migration coverage, which the lint's baseline
  makes exact and shrink-only.
- The lint enumerates `AskUserQuestion` mentions and `open_gate` calls under its scanned roots.
  Gates built on other widgets or outside those roots are not enumerated; extending the
  candidate vocabulary is the documented fast-follow path.
