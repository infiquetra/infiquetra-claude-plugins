Warning: truncated output (original token count: 136983)
Total output lines: 5225

# Decisions — Infiquetra Claude Plugins

## 2026-07-18

### Recovery accounting is counted at the source, not inferred from ledger diffs {#count-at-source-vs-point-fix-358}

**Decision.** `recover()`'s per-run budget charge and durable `actions_taken` evidence come from a
`ReclaimStats` object that `reclaim_all` increments at the result-landed site inside the per-run
reclaim lock, readable by the caller even when the call raises mid-flight. The before/after ledger
differential (`_count_budgeted_results`) is deleted, not repaired. The counted number keeps its
established definition — budgeted results this call landed — so the mechanism swap is
behavior-preserving for every previously reviewed accounting semantic.

**Rationale.** Four remediation cycles guarded the differential instrument and each next review
found a new corner, because the instrument inherits the failure modes of the shared, durable,
failable store it reads: it can fail independently (r3), diff against a baseline nobody measured
(r4), and attribute a concurrent racer's writes to the measuring pass (reproduced 2026-07-18,
present since birth, unreachable by any guard). An in-memory increment at the action site has none
of these modes — the defect classes become unrepresentable rather than guarded, and the loop body's
accounting branch matrix collapses from 16 corners to 4, which is small enough to enumerate
exhaustively in tests.

**Rejected.** (a) The lens-converged point fix (baseline-measured flag): correct for the r4
fabrication but leaves the misattribution race open and keeps two failable reads plus their guard
machinery — round 5 would be entitled to a finding of the same class round 4 produced. (b) Widening
the reclaim lock to cover `recover()`'s measurement bracket: fixes attribution but keeps the other
failure modes and complicates the lock's lifecycle. (c) Charging on adapter *invocation* rather
than result-landed: more conservative under a raise, but silently changes reviewed budget semantics
(`test_error_path_does_not_charge_unspent_budget`) for no defect-closing gain.

**Revisit when.** A second caller needs cross-process or cross-crash action accounting (stats is
per-call, in-memory by design — a durable counter would reopen the shared-store questions), or
`reclaim_all` grows action kinds whose budget semantics differ from result-landed.

**Refs.** Issue #358; LEARNINGS `{#count-at-source-358}`; `plugins/saga/scripts/team_teardown.py`
(`ReclaimStats`, `_reclaim_all_locked`, `recover`); `TestRecoveryAccountingAtSource`.

---

## 2026-07-17

### Lease-bound outcome worktrees have one teardown authority {#lease-bound-worktree-teardown-356}

**Decision.** A registry entry carrying a fleet worktree lease receipt may be removed only after a
non-mutating proof of its receipt root, exact broker lease id, structured resource, fencing token, and
managed path. Graph prune requires both the Git adapter and authority before changing revision, nodes,
edges, or generated issue state. Generic ship teardown treats the entire canonical
`.saga-worktrees/<outcome>/<subplot>` namespace as managed: store or registry ambiguity retains the
path instead of falling through to raw Git. Production `/outcome prune` passes authority explicitly;
positively identified legacy unleased and unmanaged worktrees retain existing teardown.

**Rationale.** The registry entry and its broker fence are one authority pair. Removing only the Git
worktree and registry record leaves a live lease that can block the bounded pool or let later recovery
misclassify ownership. A missing or corrupt registry cannot prove the opposite; absence of readable
evidence is therefore a retention case, not permission for a raw Git bypass.

**Evidence.** Real-Git/broker regressions prove omitted-adapter, wrong-root, and invalid-token prunes
preserve revision, nodes, edges, issue callback, path, registry, and lease. Missing, malformed, and
unreadable managed registries retain their paths without repair; canonical reap releases its exact
lease before deregistration, while legacy and unmanaged teardown remains green.

**Refs.** Issue #356; `plugins/saga/scripts/outcome_worktrees.py`,
`plugins/saga/scripts/outcome_decompose.py`, `plugins/saga/scripts/ship_teardown.py`.

---

## 2026-07-14

### Tier campaign verification by leaf blast radius: full Fable refute-3 on trust-kernel leaves, single Fable spot-check on mechanical ones {#tiered-verification-by-leaf-risk}

**Decision.** The next autonomy campaign's envelope tiers adversarial verification by leaf
risk class instead of running a uniform full Fable-xhigh refute-3 panel on every leaf, as the
2026-07 campaign (fleet-integrity-gates + intent-envelope-autonomy, 17 leaves, ~10.1M subagent
tokens) did. Two modes, chosen per leaf at wave-planning time and recorded in the envelope:

- **Full Fable xhigh refute-3 panel** — leaves that define contracts, invert a fail posture,
  or touch the merge/authorization/attribution kernel. On an auto-merge campaign the panel is
  the ONLY review before main, so this class never gets under-tiered.
- **Single Fable xhigh spot-check** (~85K tokens vs ~821K for the one fully-attributed panel,
  roughly 10×) — mechanical, additive, telemetry-surface, or doc-alignment leaves. A
  spot-check that refutes anything escalates that leaf to a full panel.
- Ambiguous classification defaults UP to the full panel; the hand-finish-residuals +
  spot-check-only-the-repairs loop is kept unchanged (it was the campaign's best cost
  discovery).

**Evidence (2026-07 campaign scorecard).** Every P1 catch clustered on trust-kernel leaves and
required cross-file invariant reasoning: #422's YAML tokenizer fail-open, #457's fail-open
proof chain, #433's gate side-door + lost-update clobber, #449's era-attribution write-once
honesty (two verifiers found it independently — refute-3 redundancy earned its keep exactly
there). Mechanical leaves produced clean sweeps or P3-grade residuals a cheaper pass finds
too. The #449 spot-check found a real residual the full panel had missed (the stale
`key_recipe`) at ~10× less spend — the cheap mode demonstrably has teeth, it is not a rubber
stamp. Building at Fable does not obviate verifying at Fable: #449 was Fable-built and the
panel still surfaced two genuine P2s. The tiering signal is blast radius, not diff size — the
era-attribution fix was ~15 lines whose absence would have let a dead-era authorization
write-once-suppress a live-era merge record forever. Caveat, stated honestly: there was no
A/B control; nobody measured what a Sonnet panel would have caught. The uniform-Fable envelope
was the right first-campaign call for a campaign building its own trust machinery; the
estimated over-spend it leaves on the table now is ~2–3M tokens per comparable campaign
(extrapolated from the single attributed panel cost — an estimate, not a measurement).

**Relation to the R4 same-tier rule.** This engages the
[#parallel-refuteN-emitter-plan-work-wiring](#parallel-refuteN-emitter-plan-work-wiring)
revisit-when clause ("the verify panel's same-tier rule proves too expensive → consider a
tiered verifier vocab") — in the *mode* dimension, not the parity dimension. The 2026-07
envelope already ran verify-above-build ("Fable reviews the juniors' work") and the asymmetry
worked; what this decision tiers is panel-vs-spot-check per leaf, while whatever full panels
remain keep running at or above the unit's tier.

**Rejected alternatives.** (a) Uniform Fable refute-3 everywhere (the 2026-07 envelope) —
right once, now demonstrably paying full-panel price for P3-grade findings on mechanical
leaves. (b) Uniform cheaper panels (e.g. Sonnet refute-3, or 2 Sonnet + 1 Fable judge) — no
evidence a cheaper panel catches the invariant-class P1s, and with auto-merge the panel is the
last line of defense; under-tiering the kernel class is the one unrecoverable direction.
(c) Skipping verification on Fable-built leaves — refuted directly by #449. (d) Refute-1 on
kernel leaves — the era-attribution P2 was found independently by two of three verifiers;
on the kernel class, redundancy is diversity insurance, not waste.

**Revisit when.** A spot-check on a mechanical leaf misses a defect a full panel demonstrably
would have caught (then fix the risk classifier, not the mechanism); per-panel spend data from
a real tiered campaign contradicts the ~10× ratio or the ~2–3M savings estimate; wave-planning
classification proves contentious often enough that "default UP" makes the tiering vacuous; or
the #603 issuance era moves the merge trust boundary so that more leaf classes count as
kernel.

**Refs.** Campaign record: auto-memory `project_autonomy_campaign_2026_07.md`. The risk apex
whose panel data anchors this: [#envelope-authorized-merge-449](#envelope-authorized-merge-449).
Panel/spot-check mechanics: `plugins/saga/references/sandbox-spawn-sites.md` (readonly-verifier
+ worktree isolation), LEARNINGS `{#token-era-binding-449}`.

---

### Merge gained a scoped, revocable, attributed exception — and the engine's tokenless auto-merge default died with it (#449) {#envelope-authorized-merge-449}

**Decision.** #449 ships the `AUTONOMOUS_UNDER_ENVELOPE` write class as three composed layers,
engaging the intake §3 revisit condition on the never-autonomous merge binding WITHOUT
flipping the default: (1) a **token store** (`envelope_token.py`, per-outcome
`envelope-tokens/` lane) — closed exact-keys schema, merge-only scope, timezone-aware expiry,
write-once revocation marker, validity derived fresh from disk on every check, era-bound to
the committed envelope's content fingerprint AND `intent_revision` (either alone is forgeable
by documented residuals — LEARNINGS `{#token-era-binding-449}`); (2) a **pure certificate
sibling** (`authorize_write_under_envelope`) — `authorize_write` gained NO token parameter and
still GATEs the class unconditionally (zero regression for every existing caller, R20
untouched for bare merge/deploy), the sibling can never widen a non-envelope op, and a valid
token is necessary-but-not-sufficient (the caller must attest all other gates green);
(3) the **merge queue as the `ceremony_gates.merge` engine consumer** the #433 honesty note
held the R7 monotonic invariant for — every GitHub WRITE (rebase, squash) requires committed
`merge: "auto"` + exactly one active token, re-checked per attempt, with pre-squash
`authorized` and post-squash `merged` attribution records (`authorizing_envelope_id`) in the
board-sync ledger; a merge that cannot be pre-attributed is not performed. **The consequential
call, made fail-closed:** the pre-#449 tokenless R12 auto-merge default is GONE — an
envelope-less campaign now `waits-operator` (matching the #433 validator's "effective gates
default to gate" stance and the SKILL.md binding), rather than keeping byte-identical legacy
auto-merge under the absent-capture convention. Read-only classification (conflict/blocked)
still runs unauthorized so /work re-engagement never depends on merge authority. Gate records
are NOT consulted in v1 (the token is CLI-minted, self-attested at the same filesystem trust
boundary; `gate-record.md` item 4 updated to what actually landed); no fleet-core schema
change (the "tokens on the envelope" forecast was not needed — the token references the
envelope, not vice versa), so fleet-core is not bumped.

**Panel hand-finish (refute-3 survived 0/3; the two demonstrated P2s repaired pre-merge).**
The attribution record key gained the token era coordinate
(`merge-under-envelope:{outcome}:{subplot}:{pr}:{phase}:{token_id}`) — without it, an
`authorized` record left by a capped/gated attempt under a dead era write-once-suppressed the
pre-attribution of the merge actually performed under a later era, so the two phases of one
merge could name different envelopes (found independently by two verifiers). The
record-write-fault→GATE branch gained the red-capable test mutation testing showed it lacked.
The token-id vocabulary now refuses the reserved `.revoked` suffix at the shared path seam
(a `x.revoked` token file collides with token `x`'s revocation marker — audit-invisible to
list/resolve). "No grace window" phrasing was scoped everywhere to the honest bound: a
revocation cannot recall a single already-in-flight GitHub call; every write after it GATEs.

**Rejected alternatives.** Posture-alone authorization (merge=auto with no token — the #380
threat model says the envelope is recorded intent, never a credential); preserving legacy
auto-merge for envelope-less specs (the absent-capture byte-identical convention — rejected
because here the recorded binding says "never autonomous" and the engine contradicted it;
surfaced as an operator decision point on the PR); binding tokens to `intent_revision` only or
fingerprint only (each forgeable — see the learning); any-valid-token-wins on an ambiguous
lane (never pick); per-tick (rather than per-write) token freshness (a mid-tick revocation
must stop the very next squash); backfilling a lost `merged` attribution record on
already-merged detection (post-hoc attribution asserts a pre-merge authorization nobody
re-verified); putting token keys on the gate-record or intent-envelope schemas (both closed;
neither needed).

**Revisit when.** Deploy-to-nonprod wants the same mechanism (new scope in the closed
vocabulary + a deploy-path consumer — explicitly out of #449's scope); the envelope-issuance
UX ships (run-start dialog minting the token alongside the envelope — the companion issue; the
CLI mint verb is the v1 issuance surface) and this token shape needs extending; an attended
flow wants a live gate-record answer to mint (then `is_operator_answerer` is the predicate and
the #371 exact-keys schema step applies); or a real campaign demonstrates the one-tick
in-memory-posture residual matters beyond the documented bound (then thread the on-disk
`intent_reader` through the remaining direct callers).

---

### Gates are durable records with a derived-not-presence answerer contract; the absence lint ratchets by exact count (#371) {#gate-record-absence-contract-371}

**Decision.** #371 ships gates as **records, not widget calls**: `gate_record.py` persists the
declaration (question, options, `absence_behavior` defaulting to HALT, transport, optional
dispatch-era `binding`) BEFORE any transport is invoked, under a derived-on-read store
(`.saga/gates/<id>/` — write-once declaration + write-once `os.link` resolution + append-only
absence audit that deliberately records repeat silence, applying the #598 item-1 dedup lesson
from day one). Transports are a collect-strategy seam (`ask-user-question` push / `file-sentinel`
pull) sharing ONE satisfy path; `resolve-absent` applies only the DECLARED behavior. Three
contract choices bind #449: (1) **derived provenance is not operator presence** — `satisfy`
rejects reserved-prefix answerers (`carried-forward:` / `absence:`), tested in both directions
and drift-guarded against the literal provenance `outcome_intent.repost` writes; a #449 consumer
wanting a carried-forward frontier approval to authorize a merge-class write must mint a live
gate-record answer (`is_operator_answerer` is the predicate). (2) The #598 item-2
set-intent/repost carry-forward asymmetry is **composed with, not closed**: it is
presence-conservative (the set-intent path demands a fresh live approval where repost derives
one), and closing it would extend derived provenance to a second verb — the opposite direction
of this contract; it stays queued in #598. (3) The CI lint
(`lint_gate_absence_contract.py`) enforces declarations fail-closed (section-scoped
`gate-record`/`gate-exempt` markers in markdown, literal `absence_behavior` on every `open_gate`
call, the defining module excluded by documented rule) with legacy debt pinned EXACT-COUNT in a
shrink-only baseline surfaced as `pending migration (applied: false)`. Gate records deliberately
do NOT surface through the `/outcome` consolidated report until #597's halt-receipt kind-filter
fix lands — inheriting that invisibility bug for a gate surface would defeat the point.

**Rejected alternatives.** Fixing `AskUserQuestion` itself (struck by Gate-B as harness-level);
a redis-channel second transport (file-sentinel proves the seam end-to-end in-process and the
channel surfaces already reach records via `satisfy --answer-transport redis-channel`; a live
Redis transport adds an external dependency the record contract does not need); free-text
answers on the record (a diverging answer means the option set was wrong — open a corrected
gate); a file-scoped (rather than section-scoped) marker rule (one marker would silently cover
unrelated gates across a whole SKILL.md); baselining by file-only without counts (a new
undeclared gate in a legacy file would ride in silently).

**Revisit when.** #449 lands envelope tokens (the record's closed v1 schema grows
additive-within-v1, same convention as #373 — tokens belong on the record, edited in
`gate_record.py`, never consumer-tolerated unknowns; note validation is exact-keys, so the
edit must also make the new key optional in the validator or migrate written records); the #597 report fix lands (gate records
can then join the report tier with a `kind` the filter matches); or the lint's candidate
vocabulary needs a second widget family (the documented fast-follow — extend enumeration, roll
out via the baseline).

---

### Team Mimir assignment is a fail-closed label transition over live exact coverage (#557) {#mimir-intake-assignment-557}

**Decision.** Mission Control exposes one idempotent operator verb, `flow assign-mimir`, whose
only mutation is adding the repository-owned `intake:mimir` label. Before that mutation it reads
Team Mimir's coverage registry from authenticated GitHub `main`, requires one exact active entry
whose events include `issues`, verifies the target is an open issue, verifies the current GitHub
principal has triage-or-higher repository authority, and verifies the trigger label already
exists. It then reads the issue back and reports the coverage route plus live Objective field
values from project cards. Repeated calls with the label present perform no mutation or comment.

**Rejected alternatives.** Owner-wide coverage or a default route (would bypass quarantine);
creating the label or admitting the repository from Mission Control (moves policy ownership out of
Team Mimir); a success comment or local ledger (duplicate state beyond GitHub's unique label);
reading a local Team Mimir checkout (stale and machine-specific); PAT or environment-token support
(forks the existing authenticated `gh` rail); treating write failures as success without readback.

**Revisit when.** Team Mimir publishes a versioned intake API that replaces the label contract, or
the coverage schema advances beyond `repository-coverage/v1` and Mission Control can consume that
version without weakening exact-repository quarantine.

---

### Posture renegotiation is one atomic verb over the existing vocabularies; merge/deploy gates are one-way; strand = andon, not a new stop surface (#433) {#outcome-posture-renegotiation-433}

**Decision.** Mid-run posture renegotiation (#433) ships as ONE verb (`outcome repost`, engine
`plugins/saga/scripts/outcome_intent.py`) that mutates ONLY the posture vocabularies that already
exist — campaign posture is the #380 intent envelope (`run_mode` + `ceremony_gates`), node
posture is the existing `degrade_policy`/`sandbox` — through the same atomic
snapshot→validate→`bump_revision`→`decision_trail` shape as every structural edit. Five contract
choices, as hardened by the adversarial verify round: (1) `ceremony_gates.merge`/`deploy_nonprod`
ARE the issue's `merge_gate`/`deploy_gate` (no new fields), and they move only toward MORE gating
— a gate→auto repost is rejected outright, even on an envelope-less campaign whose effective
gates default to `gate`, and the SAME validation runs on a live `set-intent` first attach
(`validate_live_attach`; any dispatch record, either phase, makes the campaign live), with every
accepted attach writing a `set-intent` trail entry — one rule, one trail, no second-verb side
door. They are, honestly, recorded posture with no engine consumer until #449. (2) Overlap
safety is `intent_revision` plus a dispatch-time posture snapshot on each leaf's dispatch
records — BOTH phases, the pre-dispatch `intent` record and the settled `commit` record, so the
crash-after-intent window carries its era — that INCLUDES the campaign envelope
(`posture.intent`, `null` = envelope-less): in-flight leaves finish under dispatch-time posture
for dispatch AND completion (harvest / barrier_report evaluate implied closure checks against
the dispatch-era envelope), pending leaves pick up the amendment — and a committed repost
survives the demonstrated concurrent-tick clobber: `save_spec` is compare-and-swap on the
load-time revision (`StaleSpecError`; the cost processor reloads-and-reapplies loudly) and the
reconcile loop re-checks the on-disk revision per tick and per leaf before dispatching (the
precisely-bounded residual sub-windows — the dispatch-side interleave AND `save_spec`'s own
lockless check→write gap — are documented in `references/outcome-spec.md`, not claimed away). (3) A repost that would strand an in-flight
`destructive` leaf's sandbox authorization — where in-flight fail-closed includes a bare
intent-phase dispatch record (the TOCTOU window) — raises the EXISTING #372 stop surface (a
`coordinator`-writer `andon_halt` via `raise_strand_halt`, append-once per `(writer, scope)`,
with the ledger record append-once per `(phase, key)`) rather than a new campaign-halt
mechanism — the amendment is rejected, spec untouched, no silent resolution either direction,
no duplicate directives on repeats. (4) Approval interplay is derived from the revision-keyed
R20 gate: any repost bump re-closes it; a PURE-tightening repost carries the prior approval
forward with `carried-forward:tightening-repost:r<old>` provenance. (5) The two isolated
`workspace_isolation` values are mutually incomparable, so a move between them classifies
LOOSEN conservatively — the misread costs one extra re-approval, never skips one. The R8
`scoped_repose` offer is restricted to the one halt class the offered verb can actually
resolve (a `degrade_policy`-borne guarantee, no tags); attending / tag-borne / destructive /
availability halts are honestly offer-less.

**Rejected alternatives.** New `merge_gate`/`deploy_gate` fields on `OutcomeSpec` (forks the
#380 vocabulary the issue explicitly says to compose with); a family of per-axis setter verbs
(the issue-map consolidation rationale: one verb, one revision counter, one trail); overloading
`set-intent` for renegotiation (its refuse-overwrite contract is load-bearing for #380's
ask-once story); a rejected-repost error WITHOUT halting the campaign for the strand case
(new work would keep dispatching under a posture the operator just declared unacceptable);
applying #372's standalone `re-tier`/`add-reviewer` amendments through this path in the same PR
(tier is not a #433 posture axis — stays #594 R2).

**Revisit when.** #594 R2 routes standalone envelope amendments through the `intent_revision`
overlap machinery (so `AdvanceResult.adjustment.applied` can become true), or #449's envelope
tokens land and the carried-forward approval provenance should bind to a real authority.

---

### #373 run-start dispatch posture: additive-optional v1 envelope fields, enforced by narrowing the existing seam, spend gate HALT-only and pre-backend (#373)  {#intent-dispatch-seam-shape-373}

**Decision.** The #373 posture (`backends_permitted` / `degrade_policy` / `spend_envelope`)
ships as three **OPTIONAL, additive keys of the canonical `IntentEnvelope` schema v1**
(fleet-core `fleet_commons/intent_envelope.py`) — `SCHEMA_VERSION` stays 1, absent keys mean
"not captured" and emit nothing, so every committed pre-#373 envelope round-trips
byte-identical with unchanged meaning. Layered validation: fleet-core owns field SHAPE
(type-strict, closed sub-schemas, `tier_ceiling` bound to `tier_palette.MODELS`);
saga's `OutcomeSpec.validate` binds `backends_permitted` to `NODE_BACKENDS` (the spec house
owns the executor vocabulary — the fleet schema does not import it). Enforcement lives at the
existing seam: `outcome._reconcile_once` parses the posture once per pass and feeds it to the
unchanged `degrade_decision` (effective menu = captured ∩ runtime per KTD9; unmet → HALT by
default; `operator_away_one_rung` → the availability set is restricted to the immediate
`DEGRADE_LADDER` rung, so at most one rung). The spend gate is **HALT-only and runs BEFORE any
backend resolution** (`outcome_dispatcher.authorize_dispatch_spend` → typed `SpendHaltError`,
deliberately NOT a `BackendHaltError` subclass), reading `outcome_costs.rollup` actuals in one
per-pass snapshot; `Node.tier` (optional, ladder-validated) is the tier the ceiling ranks
against. Authorized-while-strictly-below: actuals AT the ceiling exhaust the budget.

**Rationale.** Bumping `SCHEMA_VERSION` to 2 under the exact-match validator would have
force-invalidated every committed v1 envelope (issue bodies, started specs) — a forced
migration AC7 forbids in spirit; additive-optional-within-v1 is the same convention
`OutcomeSpec.intent` (#380) and `Node.sandbox` (#287) already use. Spend-before-backend makes
"a spend denial never silently degrades" structural: an unauthorized leaf never reaches the
degrade path at all. The distinct exception type keeps backend-unavailability handlers from
swallowing spend denials.

**Rejected alternatives.** (1) A second `Intent` dataclass on `OutcomeSpec` (the issue's
fallback framing) — rejected: the canonical envelope already existed after #380 and its own
docstring reserves the #373 field names; a second schema is exactly the drift the single-asker
rule forbids. (2) `SCHEMA_VERSION = 2` with a v1→v2 migration shim — more machinery for zero
semantic change; revisit when a key's MEANING changes. (3) Validating `backends_permitted`
against the backend vocabulary in fleet-core — rejected: fleet-core would have to import (or
mirror) saga's `NODE_BACKENDS`, inverting the dependency direction.

**Revisit when.** #449's envelope-authorized merge needs tokens on the envelope (the next
additive extension), or #433's mid-run renegotiation needs to AMEND a captured posture (today
`set-intent` refuses to overwrite), or a leaf's tier stops being a single model name (e.g.
model+effort pairs at the outcome seam) — at which point `Node.tier` and
`spend_envelope.tier_ceiling` must grow together.

---

### Mid-run adjustment envelope: one polled control file, four writers, fail-closed, reusing existing boundaries (#372)  {#midrun-adjustment-envelope-shape-372}

**Decision.** The mid-run operator/worker control surface (#372) ships as **one** versioned JSON
control file (`.saga/adjustment-envelope.json`, `adjustment_envelope.ENVELOPE_VERSION = 1`) that
four writers share — operator `quiesce`, plan `pause_after`, worker/reviewer `andon_halt`, and
operator `re-tier`/`add-reviewer`/`cancel`/`abort` amendments — never four separate files. The
parser (`adjustment_envelope.parse`) **fails closed**: an unknown directive/key, missing required
field, wrong version, unrecognized writer, or malformed file raises `EnvelopeError` and HALTs the
run naming the token; an absent file means "proceed". It is polled at the **already-existing**
boundaries — the `/outcome` `advance` tick (after the in-flight harvest drains, before dispatch)
and the `/work` segment boundary — not a new standing poll loop. Poll precedence is `halt > drain
> pause > proceed`, composing with the existing HALT-not-degrade stance
(`{#outcome-backend-degrade-stance}`), not a second halt vocabulary. The reversible-mutation
default (`undo_ledger.py`) is the load-bearing companion: registered reversible ops
(`board_move`/`label_change`/`issue_edit`/`saga_branch`/`saga_pr`) proceed under
act-log-inverse-notify while any op with no registered inverse falls back to the gated pause
(`mutation_disposition` → `"pause"`) — that is what makes "only irreversibles pause by default"
true rather than aspirational.

**Rationale.** The four survivors are all "a durable surface the run polls for operator
directives"; giving each its own file or a bespoke channel would multiply the poll sites and let
the halt semantics diverge. Reusing the tick/segment boundary keeps the change additive and
composable with HALT-not-degrade. `undo_ledger` is deliberately **gh-free** — it computes and
records inverses; the mutation-owning subsystem (mission-control) replays gh writes — so
`scripts/check_ownership_lanes.py` stays green (saga never calls `gh issue`/`gh project`).

**Rejected alternatives.** (1) A file per writer — rejected by the issue's scope boundary (one
schema, four writers). (2) A synchronous `AskUserQuestion`-style prompt — rejected: it silently
auto-proceeds on timeout (theme-6 gate-primitive unreliability); a durable polled file never
treats silence as consent. (3) Backfilling an inverse onto every fleet mutation — out of scope;
only the R10 op set is registered in v1, and unregistered ops keep the gated pause.

**Revisit when.** A second consumer needs authority binding on directives (v1 authenticates
directive *shape*, not writer *authority* — the file is trusted because it lives in the run's
private `.saga/` state); or when sibling #433 (`repost`/`set_intent` posture renegotiation) needs
the pause-point primitives to carry campaign-posture amendments, at which point the amendment
vocabulary here (`re-tier`/`resume_context`) may need to generalize.

---

### One level-triggered reconcile controller supersedes the three hand-wired board paths (#450)  {#one-reconcile-controller-450}

**Decision.** Board consistency for `/work` and `/loop` is now one shared,
Kubernetes-style level-triggered controller — `plugins/saga/scripts/reconcile_controller.py` —
rather than three independently hand-wired paths. It composes the two already-proven halves instead
of re-deriving them: the idempotency-key write mechanism stays in `board_progression.authorize_and_write`
(#344), and the drift vocabulary/record shape (`DRIFT_KINDS`, `_drift_record`, `_drift_id`,
`_close_satisfies_contract`) is single-sourced in the controller and re-exported by
`outcome_reconcile` (zero behavior change to `/outcome`, regression-tested). The controller's own
addition is `reconcile_op`: a per-op tick that recomputes the expected board value from durable saga
fields and re-reads the live board *every tick* (level-triggered, never an "already handled" cache),
so a rapid double tick converges on one write, a crash between compute and ledger-write is retried
not skipped, and an outside edit to a saga-owned field is re-detected — for `/work` and `/loop`, not
just `/outcome`. Auto-correction is fail-closed and doubly gated (certificate `AUTHORIZED` AND op in
the explicit `AUTO_CORRECT_OP_KINDS` allowlist, today exactly `set-field-status`); an irreversible
outside open/closed change, or any certificate-GATE op, HALTs with a named `halt_reason` and is never
overwritten. `/work` §4.4 and `/loop` §0.5 now route through the controller's `reconcile` CLI.

**Rationale.** `outcome_reconcile.py`'s own docstring named the gap this closes: a recorded
idempotency key makes the next tick *skip* an op, so an outside writer who moves a saga-owned field
while saga rests is never noticed and the drift persists forever — and that detector only ran at
`/outcome` resume time, unavailable to `/work`/`/loop`. Consolidating one *mechanism* (idempotency +
drift detection), rather than re-deriving it a third and fourth time inside `/work` and `/loop`, was
the deliberate scope-narrowing move recorded for this idea, deliberately sequenced behind
`pf-board-progression-shared-writer` (`board_progression.py`, #344 — verified landed before this
work). The auto-correct-vs-HALT line is a self-attested policy, not a certificate property (the
certificate marks both `set-field-status` and `sub-issue-close` mechanically reversible): reversing a
board Status field is safe (saga-owned, derived-on-read), but reversing an outside issue open/closed
change would destroy a human/CI lifecycle decision, so only the former auto-corrects.

**Rejected alternatives.** (1) A fourth bespoke drift detector inside `/work`/`/loop` — the exact
re-derivation the consolidation exists to prevent. (2) Auto-correcting every reversible drift
including `sub-issue-close`/`reopen` — silently overriding a human's issue-lifecycle action; HALT is
the honest response. (3) A standing/scheduled reconcile daemon — out of scope; ticks stay
invocation-triggered, matching the existing resume-time trigger model.

**Revisit when.** A fourth lifecycle command needs board writes (route it through the controller, do
not hand-wire), the `AUTO_CORRECT_OP_KINDS` allowlist is proposed to widen beyond `set-field-status`
(that is a reviewed autonomy-scope change, never an accident of a new op_kind), or true simultaneous
(non-lease-serialized) ticks appear and the `os.link` ledger dedup needs the board write itself to be
provably idempotent under concurrency rather than by-nature.

---

### IntentEnvelope canonical home: fleet-core schema, saga re-export, three wired consumers (#380)  {#intent-envelope-canonical-home-380}

**Decision.** The run-start `IntentEnvelope` schema (#380 — `run_mode` + `ceremony_gates`
{`reviews_required`,`merge`,`deploy_nonprod`}, each `gate`|`auto` defaulting to `gate`) lives
canonically in fleet-core (`fleet_commons/intent_envelope.py`), with
`plugins/saga/scripts/intent_envelope.py` a thin re-export that adds only saga-sibling glue
(`compute_stakes` over `outcome_costs.critical_path_wall`, `implied_required_checks`,
`seeded_tier`, the CLI). The schema is CLOSED per `schema_version` (unknown keys / off-vocabulary
values fail loudly); extensions (#373 `backends_permitted`/`degrade_policy`/`spend_envelope`,
#449 tokens, #372/#433 amendments) are made by editing the canonical module, never by consumers
tolerating unknowns. `reviews_required: "gate"` is consumed through the EXISTING closure gate
(`closure_gate.evaluate` grew an `implied_checks` parameter; harvest derives
`("code-review",)` for code leaves from the spec's intent) rather than a new gate mechanism.
Team-execution consumes via a newly vendored `fleet_commons_shim` +
`skills/team-execution/scripts/posture_check.py`; mission-control validates/renders the
issue-carried block in `sdlc_manager.py`.

**Rationale.** The issue proposed `plugins/saga/scripts/intent_envelope.py` as the home, but the
envelope has consumers in three plugins and mission-control/team-execution have no mechanism to
import saga scripts — fleet-commons (`{#fleet-commons-mechanism-463}`) is exactly the mover for a
shared primitive, and the tier_palette re-export precedent keeps the issue's proposed saga path
real without a second schema. Reusing closure_gate for the reviews gate keeps producer+consumer
in one PR with zero new gate machinery (#397/#398 evidence chain already litigated supersession,
SHA-pinning, and tamper detection).

**Rejected.** (a) Canonical-in-saga with cross-plugin path imports — no precedent, couples
mission-control tests to saga internals. (b) A new standalone review-gate mechanism in
`derive_states` — would duplicate the closure gate's evidence semantics and create two
disagreeing authorities for "reviewed". (c) Tolerant envelope parsing (ignore unknown keys) —
directly contradicts the campaign's fail-closed lesson; forward compatibility is owned by the
single schema authority instead.

**Revisit when.** #373 lands backend/degrade/spend fields (same module, `schema_version`
semantics), or #433's `set_intent` needs amendment/versioning hooks beyond `spec_revision`, or a
fourth consumer plugin appears (consider promoting the saga-side glue down into fleet-core).

---

### Lifecycle regression harness: declarative fail-closed scenarios over production CLIs, throwaway clones, scheduled non-gating CI (#428)  {#lifecycle-regression-harness-shape-428}

**Decision.** The end-to-end lifecycle regression harness (#428) is shaped as: (a) strict
declarative scenario JSONs under `tests/lifecycle-fixture/scenarios/` (unknown key / unknown
step-or-assertion kind / id-vs-stem mismatch = hard error, never ignored — fail closed); (b) an
engine (`tests/lifecycle_harness.py`) whose steps drive only production code paths — the real
`saga.py` / `execution_spec.py` / `outcome.py` CLIs as subprocesses with a throwaway fixture clone
as cwd, and the real `outcome_worktrees.ensure_worktree`/`reap_worktree` wired to
`git_worktree_ops` — no harness-local re-implementation of lifecycle behavior; (c) four canonical
artifact-shape assertion families (`spec-json-valid`, `saga-log-append`, `gate-record`,
`worktree-reclaimed`) whose failures carry frozen named-violation phrases (`"worktree still
present: <path>"`, `"saga log missing entry"`, …), with one `test_seeded_failure_*` baseline
control per family proving each green could have gone red; (d) a cron-scheduled
`.github/workflows/lifecycle-regression.yml` separate from the PR-blocking `ci.yml` jobs, while
the pytest surface (fast, hermetic, ~3s) also runs in the normal suite.

**Rationale.** The issue's negative-space gap is behavioral: nothing ran the lifecycle machinery
and inspected what it left on disk. Driving the production CLIs headlessly against a real (toy)
git repo is the cheapest honest cut of "execute the skills" — deterministic, no model calls, no
network — and the refute-panel lessons (fail closed; every pass needs a
could-have-failed control; no unfalsifiable guarantee wording) are structural here, not bolted on.
A load-bearing quirk: the acceptance criterion counts collected pytest node lines containing
`scenario`, so exactly two test callables carry that substring and
`test_collected_names_match_fixture_definitions` pins the invariant mechanically.

**Rejected alternatives.** (1) Skip-by-default scenario tests gated on an env var only the
scheduled job sets — the issue's own verification commands (`pytest … -k healthy_scenario`) would
then skip, and a skip is not a pass. (2) Running scenarios against the in-tree
`tests/lifecycle-fixture/` directly — lifecycle CLIs drop `docs/outcomes/…` and `.claude/saga/…`
artifacts that would dirty parent porcelain; throwaway tmpdir clones (the `wiring_canary` pattern)
keep runs independently attributable. (3) Actually invoking the skills through a live Claude
session in CI — nondeterministic, costly, and the issue's executor profile scopes this to
mechanical infrastructure; the production CLIs are the drivable seam the skills themselves call.

**Revisit when.** The scenario set wants to grow past 5 (the deliberate v1 cap — retire or merge
first), team-execution scenarios land (the issue defers them), or a scenario needs to observe a
skill-level behavior with no CLI seam — that is the signal to build a headless skill driver rather
than stretch the JSON vocabulary.

---

### Delegation-proof artifact schema + two-guard CI gate for bridge plugins (#457)  {#delegation-proof-schema-457}

**Decision.** Behavioral proof-of-execution for bridge-carrying plugins (today only `agy`) is
enforced by one repo-root script, `scripts/check_delegation_proof.py`, with two separably
testable modes wired as two jobs in a new `.github/workflows/delegation-integrity.yml`:
`--mode version-gate` (a bridge plugin's `marketplace.json` version bump must ship a valid
`delegation-proof.v1` artifact) and `--mode fleet-sweep` (every recorded proof/transcript is
classified against the silent-no-op taxonomy). The set of bridge plugins and each one's genuine-run
**discriminator regex** live in a declarative manifest, `marketplace/bridge_plugins.json` — add a
plugin there to bring it under the gate, no code change (mirrors the `ownership_lanes.json` pattern
from #431).

**KTD1 — what counts as sufficient proof: a real recorded external-tool call, never the spawn-path
name.** `LEARNINGS.md:293` (`#agy-delegate-silent-claude-fallback`) already disproved trusting the
name of the spawn path: runs believed to be genuine `agy` delegation (#278/#279) made zero `agy`
calls because the spawned teammate inherited Claude's full toolset and did the work itself. So a
`delegation-proof.v1` artifact **verifies** only when: the schema and all required fields are
present (`schema, plugin, version, run_id, bridge_command, external_tool_calls, actor`); the
`bridge_command` matches the plugin's discriminator regex (a genuine `agy --model` invocation, not
a label); `external_tool_calls` is non-empty (proves work, not a silent no-op); `actor` is non-empty
(proves the write is attributable, not orphaned); and the proof chain is intact **fail-closed**:
the attested `transcript` must resolve to a real file whose recomputed sha256 matches
`transcript_sha256`. *(Corrected in the refute-panel fix round: the first cut compared hashes only
when the attested file happened to exist, so a dangling reference verified cleanly — a demonstrated
fail-open hole. Now a dangling reference, a hash with no file, a file with no hash, and a
transcript-less proof — the distinct `unverifiable_proof` sweep category — each fail both modes,
and a transcript-less proof does not satisfy the version gate. The artifact remains self-attested;
`docs/delegation-proofs/README.md` carries the plain threat model.)*

**KTD1a — fix-round hardening (refute panel).** Three further structural decisions from the same
round: *(a)* `examples/` under the proofs directory is excluded from the enforcement surface
entirely (never loaded as proofs, never swept as standalone transcripts) and the shipped example is
version-pinned to `0.0.0-example` — a demonstrated probe had the example proof pre-attesting the
reachable `agy` 0.4.0 version-gate bump. *(b)* The manifest's script-path discriminator alternative
now requires an execution shape (`python`/`uv run` invoking the wrapper), so `cat`/`grep` of the
bridge script no longer classifies as a genuine run. *(c)* The manifest's `proof_glob` field was
**deleted as dead wiring** (declared, consumed by nothing — the journal dead-wiring rule requires a
producer AND a consumer); proof-to-bridge scoping already flows from each proof's `plugin` field,
which the sweep validates against the registered bridges, so a location glob added no signal.
Standalone `.jsonl` transcripts under the proofs directory are swept by default (and CI passes
`--transcripts-dir` explicitly), closing the untested standalone leg.

**KTD2 — rejected alternatives.** *(a) Trusting the spawn-path name / a `bridge_delegated: true`
label* — the exact failure `LEARNINGS.md:293` caught; a label is set by the same code path that can
silently fall back. *(b) Folding the two guards into one undifferentiated check* — the grounding
brief explicitly distinguishes F4-6 (per-PR version-bump gate) from F6-8 (broad per-run sweep); they
have different triggers (`**/marketplace.json` vs recorded proof artifacts) and different failure
surfaces, so they are two modes / two jobs, independently invocable (`--dry-run` smoke checks) and
independently tested. *(c) Importing `plugins/agy/scripts/agy_delegate.classify_transcript`* — the
gate is repo-root fleet governance that must not depend on one plugin's importability from CI; it
re-implements the small transcript-grep with the same event-shape parsing but keys the discriminator
off the manifest so it generalizes to any future bridge.

**KTD3 — scope: no `agy` runtime behavior change, so no release-surface bump.** This PR only adds
repo-root tooling (`scripts/`, `tests/`, `.github/`, `marketplace/bridge_plugins.json`,
`docs/delegation-proofs/`) that inspects existing/future artifacts; it does not change what `agy`
emits. Per CLAUDE.md step 6's own carve-out (and the issue's Release-Surface Checklist "if it does
*not* touch `agy`'s runtime behavior … the plugin.json/marketplace/CHANGELOG items do not apply"),
no `plugins/agy` version bump is required. A follow-up that makes `agy:delegate` *emit* a
`delegation-proof.v1` artifact on every run would touch runtime behavior and would carry the bump.

**Revisit when** a second bridge-carrying plugin ships (add it to `bridge_plugins.json` with its own
discriminator and confirm the gate generalizes without code change), or when `agy` is made to emit
proof artifacts natively (then wire the version-gate to require the emitted artifact and bump `agy`).

**Refs.** `LEARNINGS.md` `#agy-delegate-silent-claude-fallback`; `#marketplace-drift` (structural
layer this sits on); `{#external-engines-never-gatekeepers}` (#283 — this verifies a *claimed*
delegation, it does not make `agy` a gatekeeper); DECISIONS `#lint-parser-semantics-divergence`
sibling governance-gate pattern; `docs/delegation-proofs/README.md`.
---

### Mutation canary: repo-root `tools/` script, data-driven registry, gitignored ephemeral log, scheduled workflow (#427)  {#mutation-canary-design-427}

**KTD1 — placement: repo-root `tools/wiring_canary.py`, not inside a plugin.** The canary is a
meta-guard over guards the whole fleet ships; it is not a plugin behavior/schema/command/prompt
surface. Placing it in `tools/` (beside `agent_spec.py`, `release_surface_diff_guard.py`,
`stale_main_guard.py`) keeps it exempt from the CLAUDE.md step-6 release-surface tri-lock — no
plugin.json bump, no marketplace entry, no CHANGELOG. Rejected: living inside `saga` (would have
forced a saga version bump + drift-guard update for a repo-governance tool with no runtime surface).

**KTD2 — mutations are data, not code.** `tools/canary_registry.json` names each guard's pytest
node, its one-sentence invariant, and a typed mutation (`replace_text` with a stable anchor, or
`set_json_field`). Adding a guard is a registry entry, not new machinery — matching the issue's
"registering a new guard is a follow-on registry addition" non-goal. A `replace_text` anchor that
no longer matches raises `CanaryError` → `error` outcome, so registry rot fails loud.

**KTD3 — toothless is proven by fixtures, never by weakening a real guard.** Deliberately
regressing a live guard to exercise the `toothless` branch would leave the repo's actual guard
regressed (explicit non-goal). `tests/test_wiring_canary.py` builds a tmp_path "repo" with an
always-green fixture guard + a planted mutation and asserts `toothless` + non-zero canary exit — the
canary's pass/fail logic is proven independent of which real guards are registered (R7).

**KTD4 — canary log is a gitignored ephemeral artifact, not a committed file.** AC5 requires
`git status --porcelain` empty after a run, but every run appends to
`docs/engineering-journal/canary-log.jsonl`; a tracked log would dirty the tree. Gitignored locally
+ uploaded as a CI workflow artifact (`actions/upload-artifact`) gives inspectable history without
committing churn. Revisit-when: if toothless history needs to be durable across machines, promote
to a committed append-only log with a dedicated release-surface exemption note.

**KTD5 — separate scheduled workflow, not a step in `ci.yml`.** `ci.yml` has no `schedule:` trigger
and runs per-PR; the canary is a nightly unattended sweep (`cron: "17 7 * * *"` + `workflow_dispatch`).
A new `.github/workflows/mutation-canary.yml` keeps the per-PR gate fast and the canary's failure
signal distinct from a normal test failure.

---

### Fake-adapter integrity: five mechanisms, repo-root tooling, hard vs advisory split (#458) {#fake-adapter-integrity-458-mechanisms}

**KTD1 — the shape lint lives at repo-root `scripts/lint_test_shape.py`, not in a plugin.** It is a
CI-time, fleet-wide authored-test-shape check (like `tools/release_surface_diff_guard.py`,
`scripts/check_ownership_lanes.py`), not a saga runtime concern. Repo-root tooling is also exempt
from the plugin release-surface tri-lock, so no plugin version bump — this PR touches zero
`plugins/**` files. Same placement for `scripts/check_fake_fixtures.py`.

**KTD2 — production detection is heuristic on the repo's import idioms, not an import graph.** The
lint never imports/executes the linted module (safe, fast, offline). A "crosses into production"
signal is any of: a `plugins` import, a `"plugins"` path-segment string literal (the
`spec_from_file_location(name, ROOT/"plugins"/…)` idiom this repo uses everywhere), or an importlib
loader call. Measured over the whole suite this yields zero false positives once redis-channel's
`server` package is declared via `--prod-module server`. *Rejected:* resolving real imports by
executing the module — a lint must not run arbitrary test code.

**KTD3 — signature parity covers two contract shapes.** The worked example (`WorktreeOps`) is a
*dataclass-of-callables* protocol, so its contract is the fields' `Callable[[…], …]` annotation
arities (parsed from the string annotation under `from __future__ import annotations`). The registry
also handles plain method-bearing classes. A rename on the real class → a name-set mismatch; an
arity change → an arity-drift finding. `verify_registry()` runs at import time so importing
`tests/fakes_registry.py` is itself the gate.

**KTD4 — golden fixtures are advisory, real-adapter lane + shape lint + parity are hard.** Per facet
`T11-F1-6`'s advisory rollout, `check_fake_fixtures.py` runs `--advisory` in CI (reports drift, exits
0); the golden is *derived from the real producer* (a normalized real `git worktree list --porcelain`
capture, paths→`<ROOT>` and SHAs→`<SHA>` for machine-stability) and regenerable via `--regenerate`.
The shape lint, the fakes-registry parity test, and the real-adapter lane are hard CI gates.

**KTD5 — v1 is one worked example per mechanism, by design.** Backfilling a golden/registry entry
for every existing fake, or migrating every fake-backed suite to a real lane, is explicitly out of
scope (#458 non-goals). The mechanisms + conventions ship now; breadth is a follow-on.

**Refs.** `{#fake-adapter-integrity-458}` (LEARNINGS), `{#outcome-decompose-worktree-stance}`,
`{#artifact-pointer-ktds-291}`.

### One agent-file CI lint: repo-root `tools/agent_spec.py`, role-tier-anchored role classes, floor-only scope for the tool guard (#422)

**KTD1 — placement: repo-root `tools/agent_spec.py`, not `plugins/saga/scripts/`.** The issue
left this open for `/plan`'s call. Chosen `tools/` because the lint operates fleet-wide
(`plugins/*/agents/*.md` — 36 agent files across the 9 plugins that carry an `agents/`
directory), matches the existing repo-root governance
scripts that already work this way (`tools/release_surface_diff_guard.py`,
`tools/stale_main_guard.py`, `tools/sha_stamp_stager.py` — none of them are saga-scoped), and
avoids implying the lint is a saga runtime concern when it is a CI-time authored-contract check
over every plugin, saga included. *Rejected:* `plugins/saga/scripts/agent_spec.py` — would need
its own fleet-commons-style vendoring story to be importable from repo-root CI, for no benefit
over a plain repo-root script.

**KTD2 — role classes are anchored in the existing `role-tier:` frontmatter vocabulary, not a
new taxonomy.** `agent-role-classes.json`'s classes (`review`, `tester`, `scanner`, `survey`) map
onto team-execution's already-existing `role-tier:` values (`adversarial-review`,
`contract-test`, `mechanical-scan`) via `role_tier_aliases`. *(Corrected in the #581 round-2
fix: an earlier version of this KTD claimed a class's own key was "directly selectable" as a
`role-tier:` value. It is not — the dispatch consumer, `fleet_commons/tier_resolver.py`,
resolves `role-tier:` exclusively through `ROLE_TIER_ALIASES`, and the class-key set is disjoint
from it. The lint now accepts exactly the dispatch vocabulary, and
`agent_spec.role_tier_vocabulary_drift()` — run on every CLI invocation, plus a dedicated test —
fails the lint if the two alias tables ever diverge. The `survey` class is reserved: it has no
dispatch alias yet, so no authored `role-tier:` value can reach it until an alias is added to
both tables.)* Agents that carry no `role-tier:` field at all (the 4 PINNED_AGENTS
ecosystem-callable agents, the `agy`/`codex` bridge agents, saga's `mechanical-executor`/
`readonly-verifier`) are **out of scope for the model-role-class and tool-scope-floor rules** —
they already have their own governance (`tests/test_agent_tiering.py::PINNED_AGENTS`,
their own hand-set `tools:` fields) and the issue's non-goal explicitly forbids inventing a
taxonomy with no anchor in existing agent framing.

**KTD3 — permitted model tiers per role class are a contiguous rank range, not an arbitrary
set** ({#tier-vocab-ordering}). Each class declares `min_model` (weakest permitted) and
`max_model` (strongest permitted); the permitted set is every model whose
`fleet_commons.tier_palette.model_rank()` falls between the two ranks, inclusive. Concretely:
`review` = `{opus}` only (min=max=opus, matching all 10 current `adversarial-review` pins);
`tester` = `{opus, sonnet}` (min=sonnet, allows escalation to opus, matching all 8 current
`contract-test` pins); `scanner`/`survey` = `{sonnet, haiku}` (max=sonnet, forbids opus/fable —
this ceiling is what makes the issue's "survey agent pinned to opus" red-fixture scenario fail;
since round 2 the fixture drives it through the dispatch-valid `mechanical-scan` alias plus an
injected survey alias, because class keys are not authorable `role-tier:` values, per KTD2).
No current fleet agent needed a `model:` correction — every existing role-tier pin already falls
inside its class's range.

**KTD4 — the tool-scope-floor rule targets exactly the `is_review_class: true` classes (only
`review` in v1), matching the non-goal's "v1 targets review/verify-class only."** This meant all
10 team-execution `adversarial-review` agents needed a `tools:` field added (none had one before
#422 — see `plugins/team-execution/CHANGELOG.md` 2.14.6) since an absent `tools:` fails the rule
by design. The added roster is `tools: Bash, Read, Grep, Glob` — `Bash` is retained deliberately:
these reviewers dereference artifact pointers by running
`plugins/team-execution/skills/team-execution/scripts/artifact_pointer.py deref` via `Bash` (the
"required verification path" per
`plugins/team-execution/skills/team-execution/references/artifact-pointers.md` — a contract that
binds all ten reviewers; three of the ten additionally restate the deref mandate in their own
prompts: `security-reviewer.md:45`, `devils-advocate-reviewer.md:52`,
`architecture-reviewer.md:68`). The `tools:`
frontmatter field IS the spawn-time capability roster a dispatcher reads to scope a leaf (the same
mechanism saga's `readonly-verifier` uses to keep `tools: Bash, Read, Grep, Glob` so verifiers can
run tests) — so the floor forbids only the direct file-mutation tools (`Edit`/`Write`/
`NotebookEdit` since round 2) while retaining the `Bash`-deref path these reviewers require: the
floor is "no direct file-mutation tools", not "read-only". This does not contradict
`plugins/saga/references/sandbox-spawn-sites.md`'s "out-of-scope" table: that decision is about NOT
routing team-execution through saga's `mutation_policy`/`workspace_isolation` sandbox mechanism, not
about whether an authored `tools:` roster may exist, scope the spawn, and be CI-checked.

**KTD5 — `effort:` absence stays warn-only via a `--report` flag, never a blocking exit code,
per the issue's explicit non-goal** (no backfill in this capability). The CI step
(`.github/workflows/ci.yml` "Agent-file spec lint") runs with `--report` so the 32 current
warnings are visible in CI logs without ever failing the build on their account.

**KTD6 — `effort:` warn→block flip has a concrete, implemented condition, not an open deferral.**
`tools/agent_spec.py` ships a `--strict` flag that promotes the warn-only `effort-presence` rule to
blocking. It is NOT wired into CI today (CI still runs `--report`), so the current 32 `effort:`
warnings never fail the build. The documented flip condition: **when the fleet-wide effort-warning
count reaches zero, the CI invocation gains `--strict` and `effort:` absence becomes blocking.**
That ordering matters — flipping while warnings remain would fail the build on the very backlog the
grace period exists to absorb; flipping once the count is zero makes the rule a ratchet that keeps
new agent files from regressing without ever having blocked existing ones. The warn text
(`_check_effort_presence`) points at this condition verbatim.

**Rejected alternatives.** A single flat `permitted_models: [...]` set per class (rejected by
KTD3's binding decision, since it invites an accidental gap/skip in the middle of the ladder).
Leaving the `--strict`/`effort:` flip fully deferred with no flip mechanism at all (rejected by
KTD6 — the DoD requires a documented flip date/condition, so the flag exists now and the condition
is written down, even though CI does not yet pass `--strict`).

**Revisit when:** a real `role-tier: survey` (or any class beyond the current three team-execution
aliases) agent is added to the fleet — verify its model pin against `survey`'s range still makes
sense once it's not just a fixture; or when the `effort:` warn-only grace period's flip condition
is decided (a separate follow-up, not this capability).

---
### Board census records field/option SHAPE only, never item counts; `--live` legs SKIP (not silently pass) when GitHub is unreachable (#424) {#board-census-shape-only-live-skip-424}

**KTD1 — census scope excludes item counts and item content.** `board_census.py`'s committed
`config/board-schema.json` records only field/option shape (id, name, dataType, options) per
tracked project. *Rejected:* including live item counts in the committed snapshot — item counts
mutate on every card move, so a CI `--check` step comparing against a committed count would fail
on essentially every commit unrelated to the board schema itself, training operators to ignore the
gate. Full-item-pagination correctness (the actual defect this issue fixes) is proven independently
by `count_project_items()` / its own tests, which assert the FULL count on a mocked >200-item
response — decoupled from what gets committed.

**KTD2 — `--live`-gated legs (board census `--check`, `check_issue_contract_parity.py --live`)
print an explicit SKIPPED line and exit 0 when live GitHub access is unavailable, never silently
folding "couldn't check" into "passed."** This repo's CI runners have no Projects-scoped `gh`
token, so both legs will SKIP on every normal CI run today — that's intended, not a bug: the
capability exists, is unit-tested with mocked live-resolution, and produces real signal the moment
an operator (or a future CI credential) runs it with access. *Rejected:* wiring a hard-fail `--live`
CI job — this sandbox's live audit surfaced a genuine, pre-existing CAMPPS Status-option drift
(schema says `Idea`/`Committed`/`Parked`; live is `Todo`/`In Progress`/`Done`) that redesigning
board schema is explicitly out of scope to fix in this issue; a hard-fail job would either block
unrelated PRs on a known, accepted drift or force an out-of-scope schema rewrite to unblock CI.

**Revisit when** a CI credential with `read:project` scope is provisioned (upgrade both legs from
SKIP-capable to actually-enforced in the standard pipeline) or when the CAMPPS Status-option drift
found live is deliberately reconciled (separate issue — board-schema redesign is out of #424's
non-goals).

**Refs.** `{#board-pagination-truncation-confirmed-live-424}` (LEARNINGS); `71faf92` /
`{#outcome-board-status-schema-resolve-326}` (the schema-resolve-over-hardcode pattern this
generalizes to mission-control's own board/field write surface).

---
### Write-ownership lanes are an AST lint over a JSON manifest, not a text grep or prose contract (#431) {#ownership-lanes-lint-431}

**Decision.** The saga / mission-control / deploy write-mutation boundary is enforced by
`scripts/check_ownership_lanes.py` reading `marketplace/ownership_lanes.json`, wired as a
marketplace-CI step. The manifest declares, per plugin, the sensitive `gh` subcommands its
scripts may invoke; the lint fails CI when a script crosses lanes (e.g. a deploy-lane script
calling `gh issue`). *Rejected:* a prose ownership contract + drift test (the `T7-F1-7` framing,
explicitly killed upstream in favor of the machine-checked shape).

**KTD1 — AST detection, never text grep.** The scan matches list/tuple literals whose first
element is `"gh"` and reads the second token as the subcommand, so docstrings, comments, and
error-message strings that merely mention `gh pr view` are never mistaken for real calls
(saga's scripts are dense with such strings). The anchor requires the literal list to *start*
with `"gh"`, which means wrapper-shaped invocations are skipped even when the subcommand is
fully literal at the call site — `_run_gh(["issue", "view", ...])` over a `["gh", *args]`
helper (saga's `outcome_github.py`) and `["gh"] + args` (`sdlc_manager.py`) are both invisible
to the lint. saga performs `gh issue view` reads through such a wrapper today, so the clean
pass on the real tree certifies only direct-literal call sites, not the wrapper idiom. This
blind spot (and the verb-insensitive policing below) is tracked in #583.

**KTD2 — two-layer check because `gh api` is a catch-all.** Subcommand allow-listing alone is
toothless for `gh api` (every GitHub-touching plugin uses it). A second `reserved_api_paths`
layer reserves REST path prefixes (`projects/` → mission-control) so a saga/deploy script writing
board fields via `gh api projects/...` is flagged even though `api` is in its lane. This
formalizes the already-behavioral rule that saga routes board writes through mission-control's
`sdlc_manager.py` (the board_writer pattern, #279/#344), never `gh api projects/` directly.
Coverage caveat: the layer reserves REST path prefixes only — the ProjectV2 GraphQL mutations
`sdlc_manager.py` actually uses for board writes (`gh api graphql` +
`updateProjectV2ItemFieldValue`) are not yet covered, so the reserved-path guard is a REST
backstop, not a complete board-write gate (#583).

**KTD3 — enforce only `sensitive_subcommands`.** Subcommands outside the sensitive list
(`gh repo view`, `gh auth status`, `gh search`) are never policed, keeping the gate about
write-ownership rather than every GitHub touch. Within a sensitive subcommand, though,
enforcement is verb-insensitive: a direct-literal `gh issue view` (a read) from a non-owner
lane fails CI the same as `gh issue create` — a latent false positive for the first saga
script that inlines a read it currently makes via wrapper (#583). *Revisit when* a plugin
needs a subcommand it doesn't own for a legitimate read — extend the manifest (or make
policing verb-aware, #583), not the lint code.

**Release surfaces N/A.** Repo-root tooling only (`scripts/`, `marketplace/`, a CI step, tests);
no plugin behavior, schema, command, or prompt changed, so the tri-lock does not apply per
CLAUDE.md step 6.

## 2026-07-13

### `/pulse` is a saga-resident read-only projection: status_card render, tri-state source honesty, beside-not-feeding `/optimize` (#400) {#pulse-live-telemetry-ktds-400}

**KTD1 — placement: saga plugin, not mission-control, not a new plugin.** Every existing
read-side consumer of the telemetry substrate is a saga script (`engine_promotion.py`,
`spend_receipt.py`/`spend_retro.py`/`tier_efficacy.py`, `override_rate_reader.py`), and three of
Pulse's four sources are saga-resident (`run_ledger.py`, `saga.py` ticks, `outcome_costs.py`) —
only the board read crosses to mission-control, and only as a subprocess consumer of
`sdlc_manager.py`'s own JSON output. *Rejected:* mission-control (no access to sagas/ledger
without importing saga internals backwards); a new `pulse` plugin (fails the
`{#plugin-portfolio-groom-17-to-7}` consolidation-burden test for one read-only file).
*Revisit when* Pulse grows a non-saga consumer or a non-terminal (web) surface.

**KTD2 — render through `status_card.py`** (`project_pulse`, archetype `summary-projection`,
fixed six rows), not a bespoke renderer — keeps the fleet's single-status-emitter decision
(#278) intact; numbers live in labels + the indexed evidence footer.

**KTD3 — `/pulse` stands BESIDE `/optimize`; no programmatic feed; not a gate.** Settles the
QUEUED open data-flow question from the pulse side: the operator may read a pulse snapshot when
choosing an `/optimize` target, and that human step is the entire coupling. No target, baseline,
budget, or stop primitive exists anywhere in Pulse (AC6, belt-and-braces schema test).

**KTD4 — snapshot-on-invoke; `--watch` is a bounded loop (`--iterations` required), never a
daemon** — mirrors the fleet's settled rejection of standing calibration ceremony; the DoD's
"real time or on refresh" is satisfied by refresh-on-invoke.

**KTD5 — tri-state source honesty is the load-bearing mechanism**: every panel is
`ok`/`no-data`/`unavailable` (ledger adds `chain-broken`), so a consumer can never mistake
"could not read it" or "nothing recorded" for "zero activity". A broken hash chain suppresses
ALL aggregates and renders the break banner — explicit degrade, not fabrication (the U8 stance,
inherited verbatim from `outcome_costs.py`).
### Earned ratings terminate in proposals a human applies — one write seam, no carve-outs (#459) {#earned-ratings-proposal-only-459}

**Decision.** Every earned-ratings calibration signal — benchmark contradiction
(`engine_benchmark.py`), staleness verdict (`engine_stale_report.py`), reconciliation Elo
divergence (`capability_elo.py`), and SPC drift flag (`provider_control_chart.py`) — terminates in
a `registry_calibration_proposal.v1` that `/retro` Phase 5(f) surfaces propose-diff-and-wait and a
HUMAN applies by hand-editing `engine-registry.yaml`. No module in the pipeline has a registry
write path (`engine_calibration.report`/`render_diff_preview` read only;
`tests/test_saga_retro_calibration.py::test_proposal_only_never_writes_registry` is the byte-identity
guard). Runtime consumption (R4/R5) is strictly reorder-within-an-authored-rating-band and opt-in
(`calibration=None` everywhere is byte-identical): deprioritize, never exclude, never rewrite a
rating. This is `{#external-engines-never-gatekeepers}` (#283) applied to the registry's own data.

**Rejected alternatives.** (a) Auto-applying `last_validated` bumps for corroborated cells —
rejected: the tiered self-edit contract's one auto-apply carve-out is a pure new journal entry;
a registry field edit is not that, and one write seam with no carve-outs is the whole guarantee.
(b) A separate `engine_dispatch_ledger.py` beside `run_ledger.py` (the issue's indicative file
list) — rejected: the wave-2 spine already landed as the one hash-chained ledger; a second chain
forks evidence (see LEARNINGS `{#stale-absence-claims-rescope-459}`). (c) LLM-graded benchmark
probes — rejected: an external engine must never judge another engine's rating (#283);
deterministic string graders only, with nuance left to the human reading the proposal.

**Revisit when** (revisit-when)**:** three consecutive retros where every emitted calibration proposal was applied
unmodified — then consider auto-applying ONLY `last-validated-bump` actions behind an explicit
operator setting (never `rating-change` or `revalidate`).

### HTTP-bridge lanes corroborate receipt-only; no ENGINE_CONFIGS receipt-store row (#524) {#http-receipt-only-corroboration-524}

**Decision.** Two-signal dispatch corroboration for HTTP-transport engines (ollama-cloud,
deepseek — any `via: engine-bridge-http` registry row) validates the observer signal against the
HTTP bridge's own `bridge_receipt.v1` (`engine_dispatch._http_receipt_corroborates`): full receipt
schema including proof extensions, the `http-bridge` `bridge_signatures` emitter policy, the
output attestation bound to the ACTUAL returned output, and engine/variant/transport identity
matching the registry-built resolution. The lane is selected by the invocation dict's `transport`
(built from the registry row, so runner-untouchable), never by the receipt's own transport claim.
`fleet_commons.delegation_audit.ENGINE_CONFIGS` stays a subprocess-bundle-engine table (agy,
codex) and the bundle path is byte-identical (issue #524 fix direction 1).

**Rationale.** The HTTP bridge writes no durable per-run artifact: its receipt travels inside the
runner result (`engine_bridge_http._invoke`), so there is no independent `runs/` bundle for
`delegation_audit.corroborate()` to scan — calling it raised `UnknownEngineError`, the observer
answered NO, and every honest HTTP ok was discarded as `DELEGATION_INTEGRITY` (the #468 drill's
OBS-1). The receipt's output attestation is the strongest observer check available for that lane:
it binds the receipt to the exact returned bytes, so a fabricated-ok or tampered-output run still
diverges and still trips the KTD7 requeue-once-then-HALT tripwire.

**Rejected alternative.** An `ENGINE_CONFIGS` row keyed to a receipt store (fix direction 2):
it would require the bridge to start persisting receipts to disk purely so the bundle-scan
algorithm has something to read — a second copy of the same runner-produced bytes with extra
moving parts (store location, retention, mtime filtering) and no independence gain, since both
"signals" would originate from the identical runner result. Receipt-only names that honestly.

**Revisit when.** An HTTP-lane runner gains a genuinely independent observer artifact (e.g. a
provider-side usage/billing probe, or the bridge moves out-of-process and persists receipts
under its own authority) — then a true second signal becomes possible and the receipt-only
posture should be upgraded rather than trusted further.

## 2026-07-12

### Spend observability reads the leaf-produced ledger at two granularities; no new fallback-tier or ledger schema where one already exists (#402) {#spend-observability-ktds-402}

**Decision.** The #402 spend-observability layer (planned in
`docs/plans/2026-07-12-spend-observability-plan.md`, leaf sub-402 of outcome `evidence-integrity`)
adds five reader/leaf-appender modules over the existing `outcome_costs.py` cost ledger:
`spend_estimate.py` (pre-run ordinal estimate + tier-value score + post-run reconcile),
`spend_receipt.py` (itemized receipt + cheap-fallback counterfactual), `spend_retro.py`
(cross-run tier-mix/spend-vs-outcome aggregator), a new `/retro` tier-efficacy Phase-5
propose-diff-and-wait pass (`tier_efficacy.py`), and `shadow_audit.py` (sampled one-rung-down
replay evidence). Two granularities share one ordinal currency: `execution_spec.Unit` already
carries the fields the issue anticipated stubbing (`cheaper_fallback`/`worth_it_because`, shipped
by `#367`/`#565` — verified by direct read, no stub needed there); `outcome_spec.Node` carries no
tier field at all, so a new read-time fallback-tier lookup (the node's committed `github.issue` →
its stamped tier band via `gh issue view` → `SPEND_BASELINE` default) resolves it there only —
sourced from durable committed/GitHub state alone, never the git-ignored saga cache (`resume/
SKILL.md`'s own committed-docs/GitHub-wins-over-cache precedence), since `spend_retro.py`'s
cross-run aggregation must work long after the fact, possibly from a different machine. The
single-session estimate literally renders inside `/plan`'s own Phase-5.2a tier table (a `plan/
SKILL.md` edit) — the issue's own DoD anchor — while the node-level resolver is a separate,
reusable function `/plan` itself never renders (it is single-session-scoped). The post-run
reconcile never invents a
token-to-ordinal exchange rate — it deltas only the commensurable `outcome_costs.py` fields
(`operator_touches`/`retries`) and renders `tokens`/`wall_seconds` as labeled real-world context,
because zero real telemetry exists in either committed `docs/outcomes/*/outcome-spec.json`
example today (verified: both roll up to `{}`). The shadow-audit tier-evidence ledger reuses
`evidence_ledger.py` (#398) via a namespaced `check_id` (`shadow-audit:<stage>:<unit-id>`) —
exactly the extension seam `{#evidence-ledger-ktds-398}` names — rather than a new ledger format;
`shadow_audit.py` never spawns an Agent itself (only a Claude-driven flow can), so its replay
dispatch site is documented in `sandbox-spawn-sites.md` for whichever flow invokes it. The
tier-efficacy pass is a new Phase-5(e) propose-diff-and-wait target in `/retro` (never an
AUTO-APPLY journal append) and reuses `execution_spec`'s existing `unattended` vocabulary (#364
KTD3) for shadow-audit's attended/unattended gate rather than inventing new terms.

**Rejected alternatives.** Resolving a node's tier via the leaf's own saga `orchestration_ref` /
`.claude/saga/` state (git-ignored, machine-local — the anchor, not the authority, so cross-run
aggregation run long after the fact or on a different machine cannot depend on it); adding a tier
field to `outcome_spec.Node`'s own schema (owned by `#287`, a separate concern from this read-time
convenience lookup); classifying an arbitrary node into a work-shape via an LLM call (unverifiable,
breaks offline testability); fabricating a
token-per-ordinal-unit exchange rate to force a unified estimate/actual delta (no repo data
validates one yet); inventing a second ledger file format for shadow-audit results instead of a
namespaced `evidence_ledger.py` `check_id`; wiring `shadow_audit.py` into `/work`'s default
execution path in this PR (not in the issue's files-expected-to-change list, and it would compete
with R8's "off by default" honesty).

**Revisit when.** Real `outcome_costs.py` telemetry accrues across enough outcomes to validate a
token-to-ordinal calibration (today: zero — both committed example outcome specs roll up empty),
or an operator wants `shadow_audit.py` wired into `/work`'s live per-round loop as a default-on
repo behavior.

### Backend offers enumerate all three backends with availability provenance; verify panels carry their own tier (#565) {#backend-offer-full-enumeration-565}

**Decision.** The #565 fix (planned in
`docs/plans/2026-07-12-issue-565-backend-offer-fix-plan.md`) reshapes the
`recommend_execution_backend` contract: a subtractive `release_surface_file_count` keeps release
bookkeeping out of the team-execution size trigger (KTD1); a frozen validated `workflow_shapes`
vocabulary (`understand/design/research/review/migrate` — the shapes the Workflow tool doc
itself names) widens the ultracode triggers beyond breadth/adversarial (KTD2); availability
carries declared provenance (`workflow_availability_source: probed|asserted`, echoed in the
output — the prose mandates a live ToolSearch probe at offer time, KTD3); and the output's new
`backends` key always enumerates all three backends with per-backend status and an availability
note, with `omit_ultracode` deleted outright and its four prose consumer sites rewritten in
lockstep (KTD4). On the spec side, `Verify` gains an optional panel tier plus its own worth-it
receipts, defaulting to the unit tier so plain specs emit byte-identically (KTD5).

**Rejected alternatives.** Redefining `file_count` as functional-only (silently changes every
caller's semantics); one boolean per workflow shape (kwarg clutter, unversioned vocabulary);
probing availability from inside the recommender (pure Python, no ToolSearch API); keeping
`omit_ultracode` as deprecated (a live key that says "omit" gets consumed again — dead-wiring
risk); borrowing the unit's receipt fields for a premium panel (conflates two independent spend
decisions).

**Revisit when.** Hand-counting `release_surface_file_count` misfires in practice (then build
the path-classifier auto-derivation deferred in the plan), or the Workflow tool doc's shape list
changes (the frozen vocabulary must track it).

### Deploy handoff ack is a saga-side sidecar; gate-or-auto is a saga field defaulting to gate (#395) {#deploy-handoff-ack-sidecar-395}

**Decision.** The #395 positive-handoff layer (planned in
`docs/plans/2026-07-12-issue-395-deploy-handoff-ack-plan.md`) puts the ack envelope in a new
sibling module `plugins/saga/scripts/deploy_handoff.py` storing to the per-saga sidecar
`.claude/saga/sagas/<saga_id>/deploy_handoff.json` (write-once ack, token rotation on re-offer),
and captures the gate-or-auto posture as a new optional saga save field `--deploy-autonomy
{gate,auto}` asked once at `/plan` intent capture — absent always reads `gate`, so a missing
posture can never auto-fire a promotion. Dropped batons are derived on read (`reconcile` verb),
never a committed status field.

**Rejected alternatives.** A `state.json` field for the ack (contention; sidecar discipline
already established by `{#ceremony-sidecars-forward-only-undo-346}`); deriving gate-or-auto from
`destination == nonprod-deploy` alone (conflates "wants deploy" with "authorizes auto-deploy");
a deploy-plugin-side store (deploy has no state model, and `deploy-state/SKILL.md` already
sanctions `.claude/saga/` scratch); wiring the offer into `ship_ceremony.py`'s merge transition
(kept as documented `/work` routing guidance to hold the ceremony diff at zero for this issue).

**Revisit when.** The fleet intent-envelope work lands a richer autonomy posture field (migrate
KTD3's interim `deploy_autonomy` source onto it), or a deploy consumer needs the sidecar
cross-machine.

## 2026-07-11

### Teardown is the ship ceremony's terminal transition; reclaim sweeps porcelain, not the registry (#347) {#ship-teardown-terminal-gate-347}

**Decision.** The #347 teardown layer (planned in
`docs/plans/2026-07-11-issue-347-ship-teardown-reconciliation-plan.md`) appends a `teardown`
transition after `branch_delete` in `ship_ceremony.TRANSITIONS` (tier `reversible`) instead of
adding a skippable post-step or config flag — `next_transition` structurally refuses to call the
ceremony complete until it runs, and a pre-0.78.0 saga sitting at `branch_delete` intentionally
regains one pending transition. The opened-resource manifest is a per-saga sidecar
(`opened_resources.json`, beside `merge_expectation.json` / `rollback_manifest.json`), whose closing
count is derived on read with per-kind reality probes — a closed-claiming entry whose resource still
exists counts as open (discrepancy), never trusted. `reclaim` sweeps `git worktree list --porcelain`
rather than only the outcome registry (the live stale worktrees are unregistered — a registry-only
sweep cannot prevent recurrence), decides merged-ness via `git merge-base --is-ancestor`, and routes
every removal through a new `reversibility_certificate.OpKind.WORKTREE_RECLAIM_MERGED`
`authorize_write` verdict. Receipt immutability is mechanical: `O_CREAT|O_EXCL` + `chmod 0444`,
re-mint raises.

**Rejected.** Folding the layer into `ship_ceremony.py` (tangles gate logic with orchestration);
extending the outcome store's `worktrees.json` for the manifest (outcome-scoped, wrong ownership
axis for a per-saga ceremony); trusting manifest `closed_at` claims without probes (the
green-looking exit the issue exists to kill); content-hash receipt chains (over-engineered for a
single-writer local sidecar); a cron/daemon idle trigger (a SessionStart `--if-idle` nudge
suffices).

**Revisit when.** Background sessions gain a real liveness oracle (today they close only via
explicit evidence-bearing `close`), or teardown needs to run on non-ceremony surfaces
(team-execution's Step B8 sibling, theme T6).

### Ceremony safety state is sidecar JSON; undo is forward-only and tier-gated (#346) {#ceremony-sidecars-forward-only-undo-346}

**Decision.** The #346 safety layer over `ship_ceremony.py` stores its merge expectation and
rollback manifest as JSON sidecars in the saga's own directory
(`.claude/saga/sagas/<saga_id>/merge_expectation.json` / `rollback_manifest.json`), never as saga
tick fields. `ship --undo` (spelled `run --undo` so the installed `git ship` alias survives) is
forward-only — `git revert <recorded squash SHA>` on `main`, branch resurrection from a recorded
SHA, never a history rewrite — and undoing any `always_operator`-reversing entry requires
`--operator-confirmed undo`, the same named-confirmation palette as the forward gate. Hazard
bypasses are equally named: `--acknowledge-hazard <hazard-id>`, with `merge_not_landed`
deliberately non-acknowledgeable. Watcher divergences never auto-heal; `record --force` is the one
re-baseline path.

**Rationale.** Saga list fields are full-snapshot per tick — append-only bookkeeping through
`saga.py save` is clobber-prone, and ceremony-private state does not belong in `saga.py`'s schema
(`.claude/saga/` already hosts non-tick JSON: `effort-ledger.json` on disk, and
`tier_session.py:29` writes `tier-session-override.json` there on demand). Forward-only undo
keeps shared refs safe under the same philosophy
as the #526 gate: destructive intent must be named, and silence never authorizes. Plan:
`docs/plans/2026-07-11-issue-346-ceremony-hazards-watcher-undo-plan.md`.

**Rejected.** Tick-field storage (snapshot clobber, schema churn); a separate `undo` subcommand
(breaks every installed `git ship` alias); reusing `reversibility_certificate.py` (its `OpKind`
allowlist excludes merge/repo mutations — same grounds as #345 KTD1); auto-refreshing the merge
expectation on divergence (silently re-baselining IS the merge-raced-ahead failure being killed).

**Revisit when.** A second consumer needs the expectation/manifest cross-machine (then the sidecar
graduates to a committed or GitHub-backed store), or branch protection lands on `main` (then merge
undo must open a revert PR instead of pushing a revert commit).

### Ceremony operator confirmation names the transition it confirms (#526) {#ceremony-operator-confirm-names-transition-526}

**Decision.** `ship_ceremony.py run` refuses any `always_operator`-tier transition unless the caller
passes `--operator-confirmed <transition>` naming that exact transition; a name that does not match
the upcoming transition refuses regardless of tier. Enforcement is a tier lookup
(`TRANSITION_TIERS[upcoming]`), never a transition-name list.

**Rationale.** A bare boolean confirm flag would spill onto whatever step happens to be next — the
PR #525 breach was precisely a caller mispredicting the ledger position (expected a draft-PR stop,
got `merge`). Binding the word to a named step turns both failure shapes (bare-run bypass and
mispredicted position) into loud refusals. Plan:
`docs/plans/2026-07-11-issue-526-ship-ceremony-operator-gate-plan.md`.

**Rejected.** Bare `--operator-confirmed` boolean (confirmation spill); interactive TTY prompt
(hangs non-TTY agent callers, unusable by `/work`; `git ship` passes trailing args anyway).

**Revisit when.** A transition is added whose confirmation needs an argument of its own (e.g. a
merge-strategy choice), or caller-identity attestation becomes a real requirement — then the flag
grows into a typed confirmation payload rather than a name match.

## 2026-07-10

### GPT-5.6 Codex routing uses explicit registry variants and preserves direct defaults {#codex-gpt56-routing-559}

**Context.** The Codex registry had only GPT-5.5 metadata even though Codex now exposes Sol, Terra,
and Luna. The bridge accepted model/effort overrides, but Saga routing did not forward them and
receipts could not prove the selected reasoning effort.

- **KTD1 - six current selectors plus two legacy selectors.** Register
  `gpt-5.6-{sol,terra,luna}-{high,xhigh}` rows, make `codex/gpt-5.6-sol-high` the sole Codex
  default, and retain GPT-5.5 high/xhigh as explicit non-default legacy selectors.
- **KTD2 - canonical identity is `<model>-<effort>`.** Registry variants are validated against the
  separate row invocation fields. The CLI payload carries `model` and `effort` separately so Codex
  receives `-m` and `model_reasoning_effort`, while receipts and Saga evidence use the canonical
  combined identity for comparison.
- **KTD3 - provisional relative profiles only.** Sol inherits the existing GPT-5.5 profile. Terra
  and Luna use conservative lower ratings for complex review/refactor work, with rank ordering that
  expresses relative speed/cost without changing the existing metered budget or credit contract.
- **KTD4 - direct delegation stays locally configurable.** A direct `/codex:delegate` envelope may
  omit model/effort and use `~/.codex/config.toml`. Registry-backed Codex resolutions fail closed
  before runner execution if either field is missing.
- **KTD5 - safety and economics are unchanged.** Advisory-only authority, read-only Codex posture,
  reviewer-role mapping, disposable-clone behavior, hard write-mode halt, and existing spend guards
  remain intact. Credit accounting is deferred.

**Plan.** Supplied inline implementation plan; issue #559.

**Status.** Implemented on `feat/gpt-56-codex-routing`; release surfaces are bumped in Saga 0.75.23,
Codex 0.1.2, and team-execution 2.14.4 pending final validation and normal PR closeout.

**Revisit when.** Exact-variant bridge evidence is sufficient to replace the provisional Terra/Luna
profiles or calibrate credit economics. Do not infer those changes from registry rank alone.

---

## 2026-07-10

### Issue #394 adds trigger-specific second opinions without changing gate authority {#work-review-second-opinion-394}

**Context.** Issue #394 predates the shared engine-offer helper and typed reconciliation work now
present on `main`. The missing behavior is narrower: deterministic `/work` stuck detection,
single-finding dispatch in both review surfaces, and a durable Claude re-adjudication record.

- **KTD1 - one trigger coordinator, existing host wrappers.** Add one Saga-local typed helper over
  sensitivity recommendation, resolver, dispatch, and #393 reconciliation. Markdown stages retain offer
  policy, remain chaperones, and invoke the already-installed wrapper named by the resolution; the helper
  never imports sibling plugin roots, calls raw provider CLIs, or creates a transport/executor/resident slot.
- **KTD2 - trigger intent is constrained and tier-visible.** The paths allow `second-opinion` or
  decline only. Remembered `none` may suppress the automatic stuck offer; generic `offload` never
  changes trigger semantics. Persist the `opus/high` recommendation and any explicit override; human
  point-out confirms, Claude prompts, and programmatic review emits a typed recommendation only.
- **KTD3 - stuck is a target-specific three-fix streak.** Count distinct applied-fix/test attempts,
  not reruns. A pass resets all targets; a target's absence resets only that target, so incidental
  failures cannot hide a persistent file. The lexical first target wins and emits one fixed line.
- **KTD4 - work debounce is a versioned durable sidecar.** Store bounded attempts/offers in
  `saga.work-second-opinion.v1` beside the linked work-session. Stable key is
  `(round,target,streak_epoch_attempt_id)`; writes are atomic, malformed/over-cap state fails closed,
  and resume cannot repeat an accepted or declined offer.
- **KTD5 - native review schemas share one exact optional projection.** Code review binds Stage-A
  `#N`; doc review deterministically assigns `D<N>`. Both use the closed opinion-state and final-status
  vocabularies. Available content is the canonical typed-finding list under #393's 256 KiB cap;
  programmatic review places `state=recommended` on the finding rather than emitting prose to parse.
- **KTD6 - reconciliation status is not review disposition.** Account every engine finding with
  `reconciled|dropped|overridden`; separately record Claude `keep|downgrade|dismiss`. Keep and downgrade
  remain active, dismiss retains nonblocking history, and immutable evidence is verified via replacement.
- **KTD7 - verdict isolation is content-blind and synchronous.** Stamp a resolver-validated
  `advisory-reviewer` on every dispatch and evidence construction; reviewer wrappers use read-only/no-write
  posture, and `satisfy_gate()` remains a structural refusal. Only Claude final severity/status plus existing
  pre-existing policy enters the verdict. Gate-shaped object keys reject, while the same words in prose stay
  inert. V1 adds no late-result callback or polling after the wrapper's existing timeout.
- **KTD8 - context is bounded and egress-aware.** Canonical JSON carries one finding, reviewed revision,
  request reason, and cited excerpts, never the conversation/system prompt/unrelated findings/credential
  values. Cap the whole rendered UTF-8 context at 128 KiB, 16 excerpts at 16 KiB each, reason at 4 KiB,
  status note at 1 KiB, and adjudication rationale at #393's 4 KiB. A conservative pre-resolution scanner
  treats operator-marked input, credential/secret signatures, and private customer/tenant markers in any
  egressable content as sensitive. Surface provider egress before confirmation; sensitive work requires an
  eligible local-only row and otherwise halts with zero dispatch.
- **KTD9 - pre-dispatch reservation prevents duplicate wrapper calls.** Atomically write `requested` plus
  stable IDs and request digest in the consumer artifact before the wrapper runs. Only its creator may
  dispatch; a retry with an unresolved matching claim becomes visible unavailable rather than redispatching.
  Then append an idempotent matching `reconcile`, atomically write the enriched artifact/sidecar, mark the
  claim `available`, and append the missing `apply`. A crash before raw output reaches the artifact is
  unavailable; after it reaches the artifact, only the marker/apply transitions resume. Raw opinion and
  rationale remain outside `run_fact.v1`, which cannot replay a lost wrapper response.
- **KTD10 - execute as a root-owned native Codex DAG, not a Claude-style team.** Saga writes
  `orchestration_mode=inline`; the root owns the U1 -> {U2, U3, U4} -> U5 barriers, Saga, shared writes,
  Git, and final acceptance. Bounded Codex children may explore, implement one owned slice, review, or
  validate, but they do not form a named team, write Saga, commit, or gate completion. Shared-worktree
  writes stay single-writer; the operator explicitly chose this over the shape recommender's
  `team-execution` result, following the root-owned workflow pattern approved in
  `infiquetra-codex-plugins@3f63910`.

**Plan.** `docs/plans/2026-07-10-issue-394-second-opinion-triggers-plan.md`.

**Status.** Shipped in Saga 0.75.22. The implementation adds the bounded typed coordinator, atomic
requested/available claim flow, deterministic sensitive-content classification, `/work` sidecar debounce,
and native code-review/doc-review point-out contracts. External output remains advisory and opaque; only
Claude's final finding state can affect a gate.

**Revisit when.** A later objective wants automatic dispatch, cross-stage shared finding-schema
unification, or aggregate usefulness measurement. Each is separately scoped and must preserve the
binding [external engines are never gatekeepers](#external-engines-never-gatekeepers) rule.

## 2026-07-09

### Typed reconciliation reuses the run-fact ledger and keeps policy changes approval-only {#typed-second-opinion-reconciliation-393}

**Context.** Issue #393 adds intent-specific reconciliation, rejected-offload recovery,
bounded advisory juries, and retro learning. The issue's early parallel-ledger premise is obsolete:
`run_fact.v1` already supplies the append-only, hash-chained local evidence store.

- **KTD1 - one closed intent-to-recipe registry.** Fleet-core owns the canonical `ENGINE_INTENTS`
  vocabulary: `offload`, `second-opinion`, and `divergence`. Saga maps each intent to exactly one
  data-defined recipe and fails closed on missing, duplicate, or unknown mappings. Offload accounts
  for accepted/dropped/overridden work; second-opinion independently adjudicates review findings;
  divergence makes agreement as well as disagreement an explicit review outcome.
  Runner findings are immutable ordered envelopes with ordinal-bearing content IDs and SHA-256
  digests; their bounded prose remains in memory only, never in a manifest or run fact. Non-empty
  second-opinion/divergence output must exactly equal the canonical ordered envelope, so a runner
  cannot omit a finding from the data Claude sees and adjudicates. Only offload may synthesize one
  opaque artifact source. Typed multi-finding evidence requires exact ordered item coverage.
- **KTD2 - reconciliation extends `run_fact.v1` with bound, locked structural facts.** The in-memory
  result is bound to dispatch execution id, canonical intent/recipe, immutable evidence digest, and
  ordered source IDs, with explicit identifier/finding/rationale/result byte limits. Each helper call
  appends one transition from a verified snapshot under the same exclusive lock: `reconcile`, then at
  most one `apply`. Ledger/lock files are mode `0600`; facts persist only identities, digest, statuses,
  and canonical hash, never rationale or raw engine/panel output.
  Ordinary snapshots are non-healing/read-only: they take a shared lock when one already exists, but
  an absent-ledger read creates no parent, lock, or durable state. Only the append path repairs a torn
  tail while holding the exclusive lock before validation and append.
- **KTD3 - rejected offloads and panels are evidence, never authority.** A rejected offload retains
  the unit's canonical intent and dispatch bindings and requires a non-empty manifest note projected
  as a typed `dropped` item. Shared lower-level `engine_registry` policy enforces normalized role,
  advisory verdict, Claude foreman, and `PANEL_N_CAP = 7`; dispatch adds 64 KiB per-member and 256 KiB
  cumulative UTF-8 caps before foreman reconciliation. Neither path may satisfy a gate; the standing
  [external engines are never gatekeepers](#external-engines-never-gatekeepers) rule remains binding
  and Claude remains verifier-of-record.
  A panel foreman result binds the exact ordered gathered IDs and canonical gathered-evidence digest;
  each typed member finding remains individually accountable, including repeated content at distinct
  ordinals. Rejected-offload projection requires the original dispatched evidence and checks both its
  execution identity and rejection note. Rejection notes are evidence-bound, normalized summaries
  capped at 1024 UTF-8 bytes; fail-open tripwire diagnostics use a separate bounded `tripwire_note`.
  Manifest temporary and final files are mode `0600`.
- **KTD4 - retro proposals are approval-only.** `/retro` verifies the ledger and derives a typed
  `approval_required` recipe-update proposal. It never edits the registry or ledger, and a proposal
  itself is advisory evidence that cannot approve or gate anything.

**Revisit when.** Add or change a fourth intent only when recorded reconciliation outcomes produce an
approval-gated retro proposal and the operator explicitly approves it. That follow-up must update the
fleet-core vocabulary and tier posture, Saga recipe registry and tests, team-execution guidance, and
all affected release surfaces together; telemetry alone never self-modifies policy.

### Provider onboarding targets the generic HTTP bridge and earns advisory standing explicitly {#provider-onboarding-455}

**Context.** Issue #455 joins provider scaffolding, registry-to-dispatch conformance, and probationary standing. Since the issue was written, the generic HTTP bridge landed with an explicit zero-provider-branch contract, and the run-fact ledger gained proof-integrity telemetry.

- **KTD1 - scaffold a row, not a provider-specific bridge.** Version 1 accepts OpenAI-compatible HTTP providers and derives `engine-bridge-http` / `http-bridge` wiring. CLI providers halt with a clear unsupported boundary until a real wrapper exists.
- **KTD2 - authored standing is required and fail-closed.** `trust_tier` is a required `probation|advisory` row field. Existing incumbents are explicitly advisory; scaffolded rows are probationary. Capability advisory selection, explicit advisory resolution, and composing roles all enforce standing while worker/generator offload remains available.
- **KTD3 - conformance proves actual invocation reachability offline.** A distinct CI gate calls the real dispatch invocation builder for every row without preflight, credentials, or network. Existing schema/currency and receipt-emitter guards retain their narrower ownership.
- **KTD4 - preserve registry authorship during apply.** The scaffolder validates a candidate in memory, anchors insertion with parsed YAML node marks, rechecks the source hash, and atomically inserts only the row. It does not rewrite the full file or erase comments.
- **KTD5 - promotion is a read-only evidence assessment.** A probationary exact variant becomes eligible only when its five most recent engine facts are successful, proof-integrity valid, and bridge-run keyed. Telemetry never edits the registry; promotion remains an explicit reviewed PR.

**Status.** Implemented in Saga 0.75.16 for issue #455. The shipped path includes offline
conformance, parser-anchored atomic onboarding, role-aware probation enforcement, and read-only
promotion assessment. Binding decisions `{#external-engines-never-gatekeepers}` and
`{#external-engine-chaperone-dispatch}` remain unchanged.

**Revisit when.** A non-OpenAI-compatible or CLI provider needs onboarding, parser-anchored insertion proves too fragile for the authored registry, or observed promotion evidence shows the five-consecutive-run threshold is mis-sized.

### Task provider recommendation stays advisory and egress-explicit {#task-provider-recommend-391}

**Context.** Issue #391 adds a ranked `recommend()` primitive for task-to-provider routing. The
existing resolver answers a narrower single-selector question, and the registry has cost/rating data
but no explicit no-egress marker.

- **KTD1 - recommendation is not dispatch.** Add `engine_recommend.py` as an advisory helper that
  returns ranked candidates; do not overload `engine_resolver.resolve()` or call provider preflight.
- **KTD2 - sensitivity is row-authored egress policy.** Add a closed `egress_policy` registry field.
  Do not infer no-egress from `substrate`, because in-repo CLIs can still send content to networked
  providers.
- **KTD3 - registry ranking remains the candidate source.** `recommend()` reuses
  `Registry.ranked_candidates()` before applying policy-specific ordering, so overlays, deprecations,
  capability ratings, and tie-breaks stay single-source.
- **KTD4 - policies order viable rows only.** Capability fit, minimum rating, context window, and
  sensitivity constraints filter candidates before `free-first` or `cheapest-viable` ordering.
- **KTD5 - no local-only candidate is an explicit halt.** Sensitive tasks with no local-only viable row
  return an empty/halted recommendation rather than suggesting a network fallback.
- **KTD6 - cheapest-viable has a deterministic v1 price key.** Use
  `cost_per_token.input_usd + cost_per_token.output_usd` after viability filtering, with
  `cost_speed_rank` and `registry_order` as tie-breaks. Default sufficient fit is `MODERATE` or
  stronger, preserving the resolver's current WEAK-as-no-fit posture.

**Revisit when.** A real local/no-egress engine row is validated, provider telemetry becomes reliable
enough to adjust ranking dynamically, or lifecycle skills start calling `recommend()` directly.

### Output attestation proves bridge output, not just bridge launch {#output-attestation-liedetector-388}

**Context.** Issue #388 closes the remaining silent-no-op gap below the existing external-engine
receipt, observer, substitution, and economics gates. #383/#384/#390/#386 already require schema-valid
receipts, observer corroboration, substituted-engine refusal, and economics records; #388 adds proof
that the accepted output and token accounting came from the bridge run.

- **KTD1 - bridge signatures drive proof requirements.** `receipt_emitter` values in the engine
  registry map to `bridge-signatures.json` rows; dispatch must not branch directly on `engine_id`.
- **KTD2 - output attestation lives in fleet-commons.** Agy, Codex, and HTTP bridges emit a shared
  `output_attestation.v1` through their existing shims so installed plugin layouts stay valid.
- **KTD3 - proof-integrity is its own failure class.** Empty output, hash mismatch, zero external
  tokens, and producer/consumer liveness contradictions are distinct from `UNPROVEN`, ordinary
  fallback, `SUBSTITUTED_ENGINE`, and `DELEGATION_INTEGRITY`.
- **KTD4 - ledger de-duplicates by bridge run key.** Run-ledger append remains hash-chained and
  append-only; exactly-once external-token facts are achieved by skipping an already-recorded
  `bridge_run_key` before append.
- **KTD5 - producer and consumer liveness are joined.** A launch receipt alone does not prove accepted
  output, and a manifest alone does not prove a bridge ran; both sides must carry the same bridge run
  key.

**Revisit when.** Bridge output needs cryptographic signatures beyond local SHA-256 artifact binding,
or provider billing APIs become authoritative enough to replace bridge-emitted external-token proof.

### Offload economics compare tokens and provider spend separately {#offload-economics-guards-386}

**Context.** Issue #386 adds break-even halts, provider budget ceilings, cost-delta previews, and
net-savings records for external-engine `offload`. A July 6 issue comment corrected the stale premise:
`run_ledger.py` already exists, so this is ledger-backed logic, not a new meter.

- **KTD1 - run-fact ledger is the telemetry substrate.** #386 reads and writes
  `run_fact.v1` records instead of creating a second spend ledger.
- **KTD2 - token savings and provider spend stay separate.** Break-even compares resident-Claude
  inline tokens avoided against chaperone tokens spent; provider budget ceilings use registry-authored
  external USD estimates. Do not compare tokens, ordinal tier-spend, and dollars as one unit.
- **KTD3 - explicit cost class beats inference.** Registry rows declare `cost_class` (`metered` or
  `free`) and metered budget ceilings; zero `cost_per_token` alone is not treated as a free-class proof.
- **KTD4 - dispatch is the hard stop.** Operator previews are advisory, but uneconomic offload halts
  before `runner(invocation)` inside `engine_dispatch.dispatch()`.
- **KTD5 - manifest economics is schema-owned.** `net_savings` data belongs in typed
  `saga.manifest.v1` and run facts, not unstructured provenance blobs.

**Revisit when.** Claude inline pricing becomes first-class USD metadata, provider billing APIs are
available, or `/retro` needs cross-provider savings rollups richer than token-savings plus provider
ceiling checks.

### `/ideate` external-engine generator lane stays additive and provenance-only {#ideate-engine-generator-lane-454}

**Context.** Issue #454 adds a blind external-engine divergent-generator lane to `/ideate` Phase 2. The
lane expands idea-source diversity, but it must not create a second gate or a privileged convergence path.

- **KTD1 - one additive lane, not a frame replacement.** The external-engine generator runs alongside
  the N Claude frame agents selected by Phase 0.4. Adaptive frame-count logic remains unchanged.
- **KTD2 - direct chaperone-dispatch target.** This generator lane uses the existing external-engine
  chaperone model with `offload` / `sonnet-medium`; it does not inherit the generic `ideate`
  second-opinion offer default.
- **KTD3 - prompt parity preserves blindness.** The external lane receives the same substituted
  frame-agent prompt contract as each Claude frame agent and no in-flight candidate pool.
- **KTD4 - `engine-generated` is provenance only.** The tag may be rendered on candidates and survivors,
  but Phase 3 basis checks, categorical kills, and survivor scoring do not branch on it.
- **KTD5 - external failure degrades to Claude-only ideation.** Missing credentials, unavailable CLI, or
  dispatch errors never block `/ideate`; external engines remain non-gatekeepers.

**Revisit when.** `/ideate` gains a first-class executable frame-dispatch helper, live external-engine
telemetry justifies a different default tier, or provenance tags become machine-readable enough to need a
formal schema.

### Engine visibility overlay stays repo-local and explicit {#engine-visibility-overlay-453}

**Context.** Issue #453 adds `/engines` and `route explain` surfaces so operators can inspect registry
routing and apply repo-local pin/deprecate policy without editing shipped seed data.

- **KTD1 - core ranking remains single-source.** Explanation helpers must reuse the same ordered
  candidates as `Registry.by_capability()` rather than inventing a second ranking implementation.
- **KTD2 - overlay state is explicit repo-local data.** Pins and deprecations live in
  `.saga/engine-overlay.json`, are gitignored, and are passed explicitly into registry/resolver helpers.
  Core registry lookups do not read ambient current-working-directory state.
- **KTD3 - no-overlay behavior is compatibility ground.** Existing callers keep today's results unless
  they supply an overlay or repo root.
- **KTD4 - pins validate before winning.** A pin only outranks registry ranking when the row exists,
  declares the requested capability, and is not deprecated.
- **KTD5 - `/engines` and `route explain` are visibility tools.** They never invoke engines and never
  satisfy gates.

**Revisit when.** Overlay policy needs to become team/shared state rather than repo-local operator state,
or engine routing moves into a dedicated service with a first-class policy store.

### Engine registry schema currency stays data-first {#engine-registry-schema-currency-452}

**Context.** Issue #452 consolidates capability vocabulary, model-family profile inheritance, authored
cost metadata, registry staleness, and surface-intent defaults into one registry/loader change.

- **KTD1 - additive vocabulary, stable winners.** Widen `CAPABILITIES` for local/Ollama-class work while
  preserving existing `Registry.by_capability` rating and `cost_speed_rank` precedence.
- **KTD2 - family defaults materialize before validation.** `model_identity` defaults reduce authoring
  duplication, but the merged row still passes the same strict capability-profile parser.
- **KTD3 - cost metadata is authored, not telemetry.** Store structured `cost_per_token` and
  `latency_class` values for routing visibility without introducing runtime measurement collection.
- **KTD4 - one staleness mechanism, two severities.** CI fails stale registry rows; dispatch records a
  warning only and never treats staleness as gate authority.
- **KTD5 - surface intent defaults are data.** Lifecycle-stage offer defaults move beside the registry
  and are read by `engine_offer.py`, with repo-local preferences still overriding data defaults.

**Revisit when.** Real usage telemetry exists, capability ranking should become price-aware, or
external-engine routing moves from advisory offers into a dedicated router service.

### Engine output trust boundary treats advisory text as hostile data {#engine-output-trust-boundary-385}

**Context.** Issue #385 closes the content-channel injection gap for external-engine advisory text before it reaches gate or executable contexts.

- **KTD1 - contract plus guard, not sanitizer SDK.** Ship a precise trust-boundary reference, structural lint, and adversarial fixture over current advisory text surfaces; do not create a general-purpose sanitization library.
- **KTD2 - AST-backed seeded guard.** The CI guard should inspect the named call sites and prove red behavior with synthetic unsafe fixtures for subprocess-style and gate-token sinks.
- **KTD3 - advisory evidence stays content-blind for gates.** `satisfy_gate` continues to depend on Claude verification, observer corroboration, and manifest adjudication; payload text never becomes a verdict source.
- **KTD4 - Team Execution doc changes imply Team Execution release bump.** If validator reference docs cross-reference the new contract, bump Team Execution release surfaces alongside Saga.

**Revisit when.** New advisory text-bearing fields land, a real sanitizer library becomes warranted, or Team Execution gains a machine-readable validator evidence schema that replaces free-text findings.

### Shared engine offer helper owns lifecycle-stage offer policy {#engine-offer-helper-451}

**Context.** Issue #451 adds a shared `engine_offer` primitive so `ideate`, `brainstorm`, `work`, `doc-review`, and `code-review` do not each invent their own external-engine offer policy.

- **KTD1 - advisory-only helper.** `engine_offer.py` may recommend `none`, `offload`, or `second-opinion` plus model/effort tier, but it never dispatches an engine and never satisfies a gate.
- **KTD2 - stage-owned prompting.** The helper returns prompt-ready choices; markdown-driven stage skills keep their existing blocking-question or channel-inline conventions and call back to persist a selected preference.
- **KTD3 - repo-local remembered preferences.** `.saga/engine-prefs.json` stores schema-versioned per-stage choices under the repo root. Malformed JSON fails loudly instead of silently discarding an operator preference.
- **KTD4 - conservative mechanical defaults.** Explicit unit shape wins. Text fallback defaults to offload only for scaffold/deterministic-transform signals and must not classify judgment or review work as mechanical offload.
- **KTD5 - literal tier vocabulary.** Offers return `model` and `effort` as separate existing Saga vocabulary values, not compound tier strings.

**Revisit when.** A stage gains real runtime engine dispatch ownership, the tier vocabulary moves again, or the preference store needs multi-repo/outcome scope instead of repo/stage scope.

### Consensus external advisory seat is typed non-gating reviewer evidence {#consensus-advisory-seat-382}

**Context.** Issue #382 adds a Team Execution consensus-panel seat for an external-engine
second opinion, but the fleet invariant remains that external engines never satisfy gates.

- **KTD1 — executable helper over prose-only contract.** Add a small Team Execution consensus helper
  that computes gated reviewer consensus and convergence buckets, then keep the docs as the
  operator-facing protocol. Documentation drift guards alone are not enough for the score-invariant.
- **KTD2 — seat authority is explicit.** Model reviewer results as gated or advisory seats. Advisory
  results are available for reporting but excluded from the denominator, the `< 7.0` blocking rule,
  and reviewer re-run selection.
- **KTD3 — convergence matching is key-based first.** Use stable finding keys or fingerprints for
  converged/diverged buckets; defer fuzzy semantic matching because false convergence would weaken
  the audit trail.
- **KTD4 — Saga gate refusal owns reviewer-role evidence.** Add advisory-reviewer role provenance to
  external-engine evidence and make `satisfy_gate()` reject it even when verified and observer
  corroborated.
- **KTD5 — advisory absence is no-op, not fallback.** `role_kind="advisory-reviewer"` uses the
  existing halt-not-fallback role posture; unavailable external engines leave the Claude-only panel
  unchanged.

**Revisit when.** Team Execution gains a machine-owned consensus artifact writer or a semantic
finding-normalization layer with explicit Claude adjudication.

### Outcome/objective execution loop lives in a repo narrative {#objective-execution-loop}

**Context.** Objective-backed work in this repo repeatedly needs the same
`/plan -> /doc-review -> /work -> /code-review -> PR -> CI -> merge -> issue close -> outcome
advance` loop, and old chat sessions are not durable enough to be the operator-facing source.

- **KTD1 — repo artifact over transcript archaeology.** Keep the reusable loop at
  `docs/engineering-journal/narratives/2026-07-09-objective-execution-loop.md`; memory may point to
  it, but the repo narrative is the canonical reference.
- **KTD2 — live state still wins.** The loop is an operating contract, not evidence. Every resume must
  re-read outcome status/report, GitHub issue/PR/CI state, and `origin/main` before acting.

**Revisit when.** `/outcome --loop` or an equivalent first-class command can emit this contract from
the Saga runtime itself.

### Cheap chaperoning uses explicit verifiability and run-scoped policy helpers {#cheap-chaperoning-381}

**Context.** Issue #381 combines batching, evidence-size escalation, verifiability-keyed tiers,
acceptance sampling, and payload caching around the external-engine chaperone protocol.

- **KTD1 — pure policy helper.** Put chaperone economics in a small Saga helper module, then thread its
  decision into dispatch evidence. Do not bury the behavior in prose-only docs or spread policy across
  unrelated call sites.
- **KTD2 — explicit `Unit.verifiability`.** Use `test-gated|unverifiable` as an authored signal instead
  of inferring a test oracle from plan prose. Absent values preserve today's full-review posture.
- **KTD3 — homogeneous batches only.** Batch key includes engine/variant or selector, intent, review
  mode, and compatible write/test handling. Mixed or unsafe units stay one-unit packages.
- **KTD4 — reuse tier vocabulary and one-rung escalation.** Update `tier_policy.json` and generated
  tables; no hand-edited tier rows and no arbitrary retier outside the existing ladder.
- **KTD5 — advisory provenance, not gate authority.** Record batch/tier/sampling/cache decisions in
  advisory evidence provenance, without changing `saga.manifest.v1`. Do not introduce manifest fields
  named verdict, authority, gate, or equivalent.
- **KTD6 — run-scoped payload cache.** Cache assembled payloads by `unit_id+protocol-hash+context-hash`
  inside caller-owned memo state only; no module-global or filesystem cache.

**Revisit when.** team-side worker-cache scheduling lands, or manifest schema v2 is already being minted
for another evidence subrecord.

### Provider auth preflight extends `invocation.auth`, not a second auth schema {#provider-auth-preflight-389}

**Context.** Issue #389 asks for registry-driven provider credential resolution. Since the issue was
filed, HTTP transport rows landed with `invocation.auth.mode: bearer` and `auth.key_env`; the remaining
gap is CLI-row auth still living in resolver constants.

- **KTD1 — `invocation.auth` is the authored registry home.** Add `EngineEntry.auth` as a normalized
  dataclass field copied from `invocation["auth"]`, but keep YAML auth colocated with invocation data.
  A top-level `auth` field would split the schema and fight the HTTP bridge contract.
- **KTD2 — CLI binary and credential requirements move to row data.** CLI rows declare
  `invocation.cli` and `invocation.auth`; `ENGINE_CONFIG_PATHS` goes away and the resolver no longer
  needs provider-specific credential maps.
- **KTD3 — `secret-ref` is a boolean probe seam for now.** No secret backend is adopted in this issue.
  The resolver accepts an injected resolver that answers whether a ref is resolvable, and default
  absence is an unavailable preflight reason.
- **KTD4 — redaction is a resolver-boundary invariant.** Preflight may name env vars, file paths, or
  secret refs; it must never include env values or resolved secret values in return payloads, reasons,
  manifests, or logs reached by this path.
- **KTD5 — preflight memoization is row-aware once auth is row-authored.** `RunMemo` may retain the
  legacy `engine_id` key only for callers that omit `entry`; row-backed preflight must cache by
  `entry.key` or an equivalent row/auth fingerprint so variants sharing an engine do not reuse another
  row's credential result.

**Revisit when.** A concrete secret store is selected, or an operator-facing `/engines` auth-status
surface wants to explain every row's configured credential state.

---

## 2026-07-07

### No silent Claude-fallback (#390): consumer re-grounding, SUBSTITUTED derivation, gate refusal {#no-silent-claude-fallback-390}

**Context.** `docs/plans/2026-07-07-no-silent-claude-fallback-plan.md` (#390, sub-390 of outcome
external-engine-offload #336, absorbing closed #392's invocation-proof facet). Five dead-wiring
gaps where a delegation check has a producer but no consumer; the issue body predated PRs
#516/#518/#521/#522, so consumers were re-grounded before wiring.

- **KTD1 — `provenance_required` wires in as a post-classification status coercion reusing the
  existing status vocabulary and exit mapping (`agy_delegate.py:1167`).** *Rejected:* a dedicated
  exit code — callers already branch on the status set. *Revisit when:* the agy result schema
  versions.
- **KTD2 — facet-2's consumer is what exists: `disposition_note` (already threaded since #384) +
  `manifest_reader`'s R18 report; do NOT build the issue's named `DELEGATION_NOOP` roll-up (zero
  grep hits — never existed) or write run-fact records (#386/#393 own those writers).** The
  generalizable move: when an issue names a consumer, grep for it before building toward it.
  *Revisit when:* #386/#393 land their ledger writers.
- **KTD3 — substitution baseline = optional `expected_identity` threaded through `dispatch()` into
  evidence provenance (additive-defaulted, `runner_receipt` precedent); resolver/registry
  untouched.** Keeps the builder pure and the #388 seam clean. *Rejected:* deriving the baseline
  inside the resolver — couples plan-time preview to run-time routing.
- **KTD4 — disposition precedence: `DELEGATION_INTEGRITY` > halt > `SUBSTITUTED_ENGINE` > receipt
  (`UNPROVEN`/`RAN_AS_REQUESTED`).** Contradiction beats absence; a valid receipt for the wrong
  engine must never read `RAN_AS_REQUESTED`. *Revisit when:* #388 adds attestation legs below the
  substitution branch.
- **KTD5 — the #392 fail-loud leg is a `satisfy_gate` disposition refusal, not a dispatch-time
  exception.** Dispatch keeps recording honest evidence; the gate is where loudness is owed.
  *Rejected:* raising in `build_dispatch_manifest` — loses the manifest record itself.
- **KTD6 — empty-delivery is a new `check_empty_delivery.py` verdict helper GATING the chaperone's
  existing documented commit step; no new auto-commit machinery (none exists; `/optimize` shed its
  own deliberately).** File-delivery axis kept distinct from `record-completeness`'s returned-value
  axis. *Revisit when:* `/work` grows a structured unit-boundary runner.
- **KTD7 — verifier attribution is emitter-stamped where the spawner is code
  (`execution_spec.py` verdict schema), self-recorded where the spawner is Claude prose (ladder
  rule in `sandbox-spawn-sites.md`); render rule is a pure function.** *Rejected:* verifier
  self-declared identity alone — fabricatable by exactly the failure mode this issue closes.

### Zero-token fire drill (#468): both $0 lanes, real-unit target, verdict rubric, one-PR shape {#zero-token-fire-drill-468}

**Context.** `docs/plans/2026-07-07-zero-token-fire-drill-plan.md` (#468, sub-468 of outcome
external-engine-offload #336). Exploration: measure the irreducibility boundary of the cheapest
offload lanes across one real lifecycle loop; the map is evidence, never a gate.

- **KTD1 — dispatch every step down BOTH $0 lanes: `agy/gemini-3.5-flash-high` (rank 1) primary +
  `ollama-cloud/gpt-oss-120b` (rank 5) secondary.** AC1's letter is satisfied by rank 1; the
  ollama-cloud row (never live-dispatched, key wired same-day) gets first real receipts.
  *Rejected:* single-lane variants — either loses AC1 compliance or leaves the newly wired lane
  unmeasured. *Revisit when:* a third $0-class row lands in the registry.
- **KTD2 — drill target is a verified-real QUEUED item: `/code-review` Defect 2
  (`{#code-review-saga-scan-touchups}`), after stale-draft re-triage killed the first pick.**
  `{#marketplace-ci-guard}` turned out already-shipped three ways in CI (validator, generator
  `--check`, tri-lock test) — pruned by this drill. *Rejected:* `{#loop-rounds-seen-placeholder-crash}`
  (two placeholder edits — degenerate implementation signal). *Revisit when:* never — target is
  one-shot.
- **KTD3 — verdict rubric: `offloaded-clean` (<~10% rework) / `degraded` (≥~10% or retry) /
  `claude-irreducible` (unusable or structurally blocked), per step × lane, step verdict = best
  lane.** *Rejected:* binary pass/fail — hides exactly the degradation gradient the map exists to
  measure.
- **KTD7 — one branch, one PR (fix + release surfaces + map + journal), destination merge, hard
  test gate.** *Rejected:* separate evidence-only PR — splits the drill's receipt chain from the
  work it proves.
- **KTD8 — dispatch failure is data: a halt, bridge error, integrity divergence, or unusable
  output fails the step's lane and is recorded; the drill never aborts on lane failure and never
  fixes lane machinery mid-run (measurement contamination).** *Revisit when:* a repeat drill wants
  intervention-and-remeasure semantics.

Full KTD set (incl. KTD4 evidence fabric, KTD5 advisory-ungated posture, KTD6 narratives map
location) in the plan doc.

## 2026-07-06

### External-engine HTTP bridge + bridge_receipt.v1 keystone pair: transport-keyed adapter, fleet-commons receipt schema, receipt-gated disposition, required emitter wiring {#http-bridge-receipt-pair-387-383}

**Context.** `docs/plans/2026-07-06-external-engine-http-bridge-receipt-pair-plan.md` (#387, #383).
Scope-note corrections on both issues named them a keystone pair: a bridge that ships unproven, or
a receipt contract with no consuming emitter, would each ship incomplete — one PR lands both.

- **KTD1 — the adapter table extends `engine_dispatch.py`, keyed on a new top-level registry field
  `transport` (closed vocab `cli | http`, default `cli`).** `_build_invocation` gains a
  transport-keyed branch: `http` builds a generic invocation from row data with zero
  per-provider branching in the bridge; `cli` keeps the existing codex/agy builders unchanged.
  *Rejected:* a new `plugins/team-execution/scripts/engine_dispatch.py` (a draft suggestion) — would
  fork the dispatch substrate; the scope note is explicit that dispatch already lives in saga and
  should be extended, not forked. *Revisit when:* team-execution needs its own dispatch surface for
  a reason unrelated to external engines (none identified).
- **KTD3 — `ollama-cloud` and `deepseek` are new seed registry rows; routing-stability is enforced
  by a literal-baking regression test, not a promise.** Neither row may rate any capability above
  the current `by_capability` winner (verified against `engine-registry.yaml` at authoring time);
  new rows either omit capabilities or rate low enough, or use a losing `cost_speed_rank`, to never
  hijack today's winner. Base URLs and model ids are authored against provider docs, not recalled
  from memory, and proven live only by an availability-gated smoke test (skip-not-fail when no key
  or endpoint unreachable). *Rejected:* trusting rating authorship alone without a regression test —
  a plausible-looking rating is exactly the failure mode a "should be fine" review misses.
  *Revisit when:* `/retro` re-validates ratings against fresh seed data (same posture as the
  2026-06-27 seed data) and the literals need a deliberate, reviewed update.
- **KTD6 — `bridge_receipt.py` is canonical in fleet-commons, vendored into agy via the established
  shim mechanism.** A saga-local module imported directly by agy would break at install time
  (`{#marketplace-install-layout-no-i…76983 tokens truncated… the operator run `/brainstorm` first (with an explicit guard: do NOT claim `/brainstorm` "accepts" a handoff).
- **(Q3) One plan saga via the CLI; epic split → sdlc-manager.** `/plan` emits a single durable **plan saga** via `scripts/saga.py save --lifecycle-phase plan` (runnable, with a hard "never `git add` the tick" boundary). It does NOT mint per-U-ID sagas; multi-unit/epic splits hand to `sdlc-manager`.
- **(Q4) All three backends via the operator-choice doc.** Offer `inline` | `team-execution` | `cc-workflows-ultracode`, cited by path (`references/operator-choice.md`), offered not defaulted — implements the shipped operator-choice contract.

**Key design points.**
- **Review-phase rationale (the gauntlet is NOT dropped).** The full review gauntlet — `/doc-review` + `/code-review` + `/founder-review` — IS the `review` phase, a separate lifecycle stage. `/plan` keeps a CONDENSED deepening self-review and **routes to `/doc-review` (the recommended next exit) before `/work`**. Folding the gauntlet into `/plan` would break the phase model.
- **Doc-frontmatter vs saga-tick split.** The durable plan doc carries human-facing frontmatter (`title`/`type`/`status`/`date`/`origin`) plus the artifact markers (`Implementation Units` / `Key Technical Decisions` / `U1`) so `/doc-review` recognizes it; the machine work-state (lifecycle phase, destination, ADR/KTD refs, orchestration mode) lives in the saga tick. Two surfaces, deliberately not conflated.
- **One-way `/plan`→`/brainstorm` route.** The bounce is a recommendation only, in one direction; `/plan` never claims a handoff contract on the brainstorm side.

**Rejected alternatives.**
- *Lighter agent-consumable variant (thin reskin of the stub).* REJECTED — the stub is exactly the thin-reskin disease the campaign exists to cure; the artifact skeleton is what makes a plan traceable + agent-consumable.
- *Full gstack interrogation in `/plan`.* REJECTED — gstack `spec`'s five-Why + scope/MVP/failure-mode lock is WHAT-rigor that duplicates `/brainstorm`; `/plan` takes only the HOW-interrogation + code-grounding front end. (Seam between the two left as a queued decision-point — see QUEUED [#brainstorm-spec-interrogation-seam](QUEUED.md#brainstorm-spec-interrogation-seam).)
- *Per-U-ID sagas.* REJECTED — over-reach; one plan saga is the durable record, the U-IDs are slices inside it, and epic splitting belongs to `sdlc-manager`.
- *Defer the saga (plan writes a doc only).* REJECTED — contradicts the saga foundation's §11 consumer contract; `/plan` is a saga consumer and emits one plan saga.
- *Run the full review gauntlet inside `/plan`.* REJECTED — breaks the phase model; the gauntlet is the `review` phase, `/plan` only does a condensed self-review + routes to `/doc-review`.
- *CE's full 248-line deepening pass.* REJECTED — over-heavy for infiquetra; ship a condensed confidence pass instead.

**Rationale.** CE's `ce-plan` is the strongest artifact engine of either source (stable IDs, traceability, per-unit test scenarios, three-audience, already agent-consumable); gstack `spec` contributes the code-grounded interrogation discipline CE lacks at the front. Merging the two — taking CE's skeleton wholesale and grafting gstack's HOW-interrogation — gives an infiquetra-owned plan engine that is traceable, agent-runnable, and grounded, without inheriting either source's runtime boilerplate or duplicating the WHAT-rigor that lives upstream. Right-sizing (condensed deepening, one saga, HOW-only) keeps it proportional to a 1-human + agents shop.

**Revisit when.** A real multi-PR epic shows the one-plan-saga + sdlc-manager epic-split seam is awkward (revisit per-slice saga emission); the `/brainstorm` ↔ `spec` interrogation seam gets resolved and changes where HOW vs WHAT interrogation lives (see QUEUED [#brainstorm-spec-interrogation-seam](QUEUED.md#brainstorm-spec-interrogation-seam)); or the condensed deepening pass proves too thin and CE's fuller confidence pass earns its weight.

**Refs.** Plugin `0.7.0`. Part of the engine-merge campaign — see [#lifecycle-engine-merge-campaign](#lifecycle-engine-merge-campaign). Ship record: ARCHIVE [#plan-engine-rebuild-shipped](ARCHIVE.md#plan-engine-rebuild-shipped). Operator-choice contract: [#operator-choice-framework](#operator-choice-framework). Saga foundation: [#saga-schema-foundation](#saga-schema-foundation). Interrogation seam: QUEUED [#brainstorm-spec-interrogation-seam](QUEUED.md#brainstorm-spec-interrogation-seam).

### Rebuild `/office-hours` as a faithful two-mode gstack port adapted to infiquetra (PR `#173`, squash `aec888c`)  {#office-hours-engine-rebuild}

**Decision.** Rebuild `/office-hours` — the first command rebuild of the engine-merge campaign — as a **faithful two-mode gstack diagnostic port**, adapted to infiquetra and merged with the CE boundary contract (front-door framing + the `/ideate`↔`/brainstorm` handshake). Self-contained: ports the gstack engine, no gstack vendoring, no runtime dep on CE. It is the Think-phase **frame-finding front door** — `/ideate` routes unframed asks here; `/brainstorm` bounces open thought-partner work back. The four interview answers settled:

- **(Q1) KEEP both modes** — Startup mode + Builder mode, not collapsed to one diagnostic. **Jeff override:** Infiquetra is a real startup heading toward paying customers, currently pre-revenue greenfield, so the startup forcing-questions earn their place.
- **(Q2) Route always / frame-note optional** — every session closes by naming a next command; writing a frame note is optional.
- **(Q3) Re-target pushback** — hard on vagueness and ungrounded assumptions, **not** on the operator's judgment; push-twice with escape hatches.
- **(Q4) Frame-finding only + plural exits** — stop the moment you can name the problem and a route; clean exits to `/brainstorm`, `/plan`, `/strategy`. HARD GATE (absolute): never implement, plan, or file an SDLC issue.

**Key adaptations.**
- **Stage-aware startup mode** with a **PRE-TRACTION hypothesis-forming register** — a pre-revenue greenfield operator gets hypothesis-forming questions, not an evidence-audit of customers/traction that don't exist yet.
- **Builder-mode DEPTH FLOOR** — Builder mode is infiquetra's high-frequency mode (infra/workflow/internal-tooling), so it carries real discovery/shaping rigor, not a one-liner.
- **Mid-session mode-switch** — startup↔builder can flip within a session.
- **Frame note in its OWN `docs/office-hours/` dir** (frontmatter `kind: frame-note`), NOT `docs/ideation/` — avoids colliding with the `/ideate` resume-scan (`skills/ideate/SKILL.md:56`).

**Rejected alternatives.**
- *Collapse to one "is the frame settled?" diagnostic.* REJECTED — a review recommended it, **OVERRIDDEN** because Infiquetra is a real startup heading to paying customers; the startup forcing-questions matter.
- *Frame note under `docs/ideation/`.* REJECTED — resume collision with the `/ideate` resume scan (`skills/ideate/SKILL.md:56`); the frame note gets its own `docs/office-hours/` home.
- *Thin builder mode (one-liner).* REJECTED — Builder mode is the high-frequency path and must carry depth.
- *Literal evidence-audit startup questions for a pre-traction operator.* REJECTED — wrong register for pre-revenue greenfield; ported stage-aware to hypothesis-forming instead.

**Rationale.** Faithful gstack port keeps the engine that makes the front door repeatable, shedding gstack's runtime boilerplate per the campaign's port model. The two-mode split survives because infiquetra is genuinely both a startup and a builder shop; the stage-aware + depth-floor adaptations make each mode fit the actual operator rather than a generic YC founder or a throwaway builder check.

**Revisit when.** Infiquetra reaches PMF (revisit the pre-traction register — startup questions can shift back toward evidence-audit); `/investigate` + `/spec` ship (add them as routes).

**Refs.** Plugin `0.6.0`. Part of the engine-merge campaign — see [#lifecycle-engine-merge-campaign](#lifecycle-engine-merge-campaign). Ship record: ARCHIVE [#office-hours-engine-rebuild-shipped](ARCHIVE.md#office-hours-engine-rebuild-shipped). Frame-note home: `docs/office-hours/`.

### Operator-choice framework ships doc-only; CLI helper deferred to `/work` (PR `#171`)  {#operator-choice-framework}

> **Update (2026-06-13).** The §3.2 "deterministic fan-out, not review depth" framing introduced here was
> corrected, and `adversarial_confidence` + `has_code_surface` were added to the recommender — see
> [#operator-choice-docs-and-confidence](#operator-choice-docs-and-confidence). The doc-only-then-helper
> sequencing, the three-backend enum, and the always-confirm/capability-gate properties below all stand.

**Decision.** Ship the operator-choice framework as a **DOC-ONLY foundation**: `references/operator-choice.md` — the decision contract for the three execution backends `inline` | `team-execution` | `cc-workflows-ultracode` (these enum strings are the contract; prose labels like "CC workflows"/"ultracode" are not) — plus short prose **offer hooks** in `/loop` and `/work`. Lifecycle owns the **choice**, not execution. No code/helper ships this PR. The four interview answers settled:

- **(a) Who decides** — auto-recommend + **always confirm**. Inline-by-default; escalation is cheap. The agent proposes a backend; the operator confirms.
- **(b) Triggers** — `team-execution` when any `should_offer_team_execution` constant trips (`file_count>=8`, `phase_count>=4`, `has_security`, `has_infra`, `cross_repo`, `deployment_sensitive`) **or** the work needs reviewer consensus; `cc-workflows-ultracode` for broad-independent-parallel-fan-out / exhaustive-sweep work (Claude-Code-only). On **OVERLAP, offer BOTH** — no hard precedence rule.
- **(c) Capability gate** — document all three backends always; **hide** the ultracode option only when the Workflow tool is observably absent; **always graceful-fallback** at execution time.
- **(d) Scope** — `/loop` and `/work` only this PR. The other command rebuilds wire their own offers as they land.

**Rejected alternatives.**
- *Add a library-only `recommend_execution_backend()` helper now.* REJECTED — skills are markdown the agent reads, so a Python helper with no caller would be uncallable and would drift against the doc. This is the verified state of the existing `should_offer_team_execution` (defined in `lifecycle_state.py` but never called outside its own test). The CLI-backed helper is **DEFERRED to the `/work` rebuild**, where it gets a real caller.
- *Silent auto-pick.* REJECTED — violates always-confirm; the operator must see and accept the escalation.
- *Show-but-disable the ultracode option when unavailable.* REJECTED — hide it instead (cleaner; capability is observable).
- *Wire all lifecycle commands now.* REJECTED — scope is `/loop` + `/work`; the rest cite the doc as they rebuild.
- *A hard "risk dominates fan-out" precedence rule on overlap.* REJECTED — cosmetic given always-confirm; offering BOTH lets the operator decide.
- *Copy the brainstorm channel-inline wording verbatim.* REJECTED — reference `skills/brainstorm/SKILL.md`'s canonical channel-inline convention (redis-channel sessions cannot call AskUserQuestion) instead of duplicating it.

**Rationale.** Matches the queue's "no scripts" sizing — one shared reference doc + 2-3 line offer hooks. The doc is the consumed source of truth (the decision contract, complementing `saga-spec.md`'s storage contract). An honest unconsumed-style foundation in the same spirit as the saga ship: settle the contract before consumers calcify it.

**Revisit when.** The `/work` rebuild — wire the CLI-backed execution-backend helper against this doc (or decide the prose offer suffices and no helper is needed).

**Refs.** Plugin `0.5.0`. Part of the engine-merge campaign — see [#lifecycle-engine-merge-campaign](#lifecycle-engine-merge-campaign). Decision contract: `plugins/saga/references/operator-choice.md`; complements storage contract `references/saga-spec.md`. Ship record: ARCHIVE [#operator-choice-framework-shipped](ARCHIVE.md#operator-choice-framework-shipped). Channel-inline convention: `plugins/saga/skills/brainstorm/SKILL.md`. Shipped via PR `#171` (squash `e935bd4`).

### Saga schema: derived `kind-id` identity + append-only envelope log + three-axis state (PR `#170`)  {#saga-schema-foundation}

**Decision.** Define `saga` — the durable, resumable work-state envelope — as the first foundation of the engine-merge campaign, with this schema:

- **Identity: derived `kind-id`** (`issue-<N>` / `task-<slug>`), minted at birth and **sticky**. `round` and `phase` are *fields*, not identity. A task-saga that later gets an issue keeps its id and gains an `issue_ref` (the index cross-references `issue_ref → saga_id` so it stays findable by issue#). Human-legible dirs (`sagas/issue-42/`), deterministic, backward-compatible with the old `{kind}-{id}`.
- **Storage: append-only timestamped envelope log (canonical) + derived `state.json` index (rebuildable).** Each tick is an immutable file `sagas/<saga_id>/<YYYYMMDD-HHMMSS>.md`; ordering is **always by filename string, never mtime** (same-second collision → `-1` suffix). The index is `{last_updated, active_saga_id, sagas:{...}, current_work:{…legacy fields…, saga_id}}`, written atomically (temp+rename); a corrupt index is never fatal because `scan` rebuilds from the log.
- **File format: gstack envelope** — YAML frontmatter (machine fields incl. `extra:` for unknown-key round-trip) + `## Summary` / `## Decisions` (KTDs) / `## Remaining` / `## Notes / Tried` body. Cold-resume reads from frontmatter; matches the shipped CE-artifact house style.
- **Three stored state axes, one derived:** `lifecycle_phase` (CE flow: `ideation|brainstorm|plan|review|work|qa|retro`), `phase_status` (`pending|in_progress|complete`; authoritative, drives `next_phase` = phase+1 if complete else phase), `status` (thread disposition: `active|blocked|paused|handed-off|done|abandoned`; MUST NOT take `pending`/`in_progress`). **`maturity` is derived at `/handoff` time** from `lifecycle_phase` (the existing `infer_maturity` mapping), not stored.
- **List merge: full-snapshot semantics** — a tick's lists replace; absent carries forward; empty clears. Not union.
- **Full unify now:** one `saga.py` engine (`save`/`restore`/`scan`/`context`) with the 3 legacy scripts refactored into thin wrappers.
- **Spec home: plugin-level** `plugins/saga/references/saga-spec.md` (a new convention — no plugin-level `references/` existed before); each consuming SKILL links to it.

**Rejected alternatives.**
- *Minted opaque saga-id (UUID/counter).* Rejected: not human-legible, not deterministic, requires a lookup to resume issue-born work. Derived `kind-id` is self-describing and backward-compatible.
- *Engine-only, migrate the storage format later (PR1 engine+wrappers / PR2 format).* Considered as a de-risk fallback; rejected for this ship in favor of one PR — the user chose "full unify now," and characterize-first tests make the format migration safe in a single change.
- *mtime ordering.* Rejected: mtime is not stable across rsync/backup/snapshot-restore; filename-as-order is deterministic and copy-safe. (Note: the win is for rsync/backup, NOT git worktrees — those don't carry git-ignored state at all.)
- *Union list merge.* Rejected: union-only lists accumulate stale `open_questions`/files and mislead cold resume; gstack ticks are full snapshots, so resume payloads must be able to shrink.
- *Stored `maturity` axis.* Rejected: redundant with `lifecycle_phase`; deriving it at `/handoff` removes a constant axis and the `status`↔`phase_status` ambiguity.
- *Round/phase in the identity.* Rejected: would re-mint a saga id every round, breaking sticky resume; round and phase are mutable fields of a single sticky-id thread.

**Rationale.** Saga is **gstack-dominant** (CE has no saga primitive — single-session assumption — so only its artifact-discipline framing is borrowed): gstack supplies the envelope mechanics (frontmatter+body, filename-as-order, branch-agnostic restore); the payload richness (issue+PR rounds, journal/ADR linkage) is lifecycle's own scripts; CE's contribution is the implied flow recorded in `lifecycle_phase`. Settling the contract semantics (axes, snapshot lists, `current_work`) in the spec **before** consumers calcify them is the whole point of building this foundation first. This ships an **unconsumed primitive** — after this PR no command calls `restore`/`scan`; the 3 legacy CLIs keep working as wrappers and the engine is validated by its own unit tests + manual smoke. Consumer wiring (`/work`, `/resume`, `/loop`, `/plan`) is each consumer's own queued item.

**Revisit when.** A consumer rebuild surfaces a missing/awkward field or enum (extend via `schema_version` + the `extra:` preserve-unknown seam, not a breaking change); append-only growth needs a GC policy (the spec leaves a `max_ticks` seam); or a second identity collision pattern emerges that the derived-id guards don't cover.

**Refs.** Plugin `0.4.0`. Part of the engine-merge campaign — see [#lifecycle-engine-merge-campaign](#lifecycle-engine-merge-campaign). Spec: `plugins/saga/references/saga-spec.md`. Plan `.claude/plans/ok-we-yestereday-we-scalable-fox.md`. ARCHIVE [saga foundation shipped](ARCHIVE.md#saga-foundation-shipped) — consumers remain queued in [QUEUED.md](QUEUED.md).

### Rebuild lifecycle commands by merging gstack + CE engines into self-contained infiquetra engines (commit pending)  {#lifecycle-engine-merge-campaign}

**Decision.** Rebuild each diverged `infiquetra-lifecycle` command — and adopt two missing ones (`/investigate`, `/spec`) — by **merging the best of compound-engineering (CE) and gstack into a new, self-contained infiquetra engine**, worked **1-by-1 via an interview-driven merge**. Port model = the shipped `/ideate` rebuild: extract the engine, adapt to infiquetra (1-human + multi-agent team; `sdlc-manager` owns SDLC issues/boards/readiness; `infiquetra-deploy` owns deploy; the engineering journal; context-libraries), and shed gstack's ~780-line runtime boilerplate **with Jeff's per-item sign-off**. Neither source has priority — Jeff leans CE. Build two foundations first: a first-class `saga` durable/resumable work-state envelope (P0) and a shared inline / team-execution / Claude-Code-workflows operator-choice framework (P1), because the command rebuilds read them. Full per-command queue: [QUEUED.md](QUEUED.md) engine-merge initiative.

**Rejected alternatives.**
- *Adopt one upstream wholesale (just gstack, or just CE).* Rejected — Jeff: "otherwise I would just use one or the other and forget about all this." The value is a merged engine infiquetra owns and evolves, taking bits of both.
- *Vendor gstack / runtime-depend on CE.* Rejected — same standalone-boundary rationale as the `/ideate` ADR ([#ce-ideation-engine-restore](#ce-ideation-engine-restore)); gstack also carries ~780 lines of runtime plumbing (telemetry, gbrain, `~/.gstack`, model overlays) irrelevant to infiquetra.
- *Leave the thin stubs.* Rejected — they bias toward facilitation; the engine is what makes a command repeatable. See LEARNINGS [#lifecycle-thin-reskin-systemic](LEARNINGS.md#lifecycle-thin-reskin-systemic).
- *Auto-shed gstack boilerplate without review.* Rejected — Jeff wants input on what's shed; each rebuild surfaces shed candidates for sign-off.

**Rationale.** CE and gstack each have engine mechanics worth keeping (CE: structured artifacts, causal-chain debugging, persona/findings/validator review; gstack: scope-mode reviews, risk-gated QA, multi-specialist fan-out, save/restore checkpoints). Merging the best of both into an infiquetra-owned engine — rather than depending on either — keeps the plugin self-contained, evolvable, and adapted to a 1-human + agents shop where artifacts must be agent-consumable. Worked 1-by-1 so each merge is a deliberate, interview-settled design, not a bulk port that would re-introduce the stub-disease at engine level.

**Revisit when.** A command's interview shows the merged engine is more than infiquetra needs (ship a lighter version), or CE/gstack ship a materially better engine worth re-syncing, or the parallel-fork maintenance cost exceeds the value of self-containment.

**Refs.** QUEUED engine-merge initiative; LEARNINGS [#lifecycle-thin-reskin-systemic](LEARNINGS.md#lifecycle-thin-reskin-systemic), [#workflow-structuredoutput-budget](LEARNINGS.md#workflow-structuredoutput-budget), [#stub-port-drops-engine](LEARNINGS.md#stub-port-drops-engine); DECISIONS [#ce-ideation-engine-restore](#ce-ideation-engine-restore), [#sdlc-handoff-ownership-boundary](#sdlc-handoff-ownership-boundary).

## 2026-06-01

### Restore the CE ideation engine into `/ideate` + `/brainstorm`, self-contained (commit `30c9099`)  {#ce-ideation-engine-restore}

**Decision.** Rebuild `infiquetra-lifecycle`'s `/ideate` and `/brainstorm` from thin facilitative
stubs into full divergent→convergent engines ported from compound-engineering (CE) and adapted to the
infiquetra world — self-contained, no runtime dependency on CE. `/ideate` generates many candidates
across parallel frame agents, critiques all, and presents only survivors; cut ideas stay revivable.
Two deliberate improvements over CE: (1) a two-way partnership — operator seeds feed *into* the frame
agents and face the same critique; (2) a revival state machine that re-enters the filter with new
evidence (and adjudicates novelty) so revival cannot soft-promote a categorically-cut idea. Added
infiquetra grounding CE never had: context-library reader (`*-context-library` via `gh`), named-repo
reader, grounding-fit gate, read-only `gh` issue-theme clustering. Dropped CE's Proof/HITL,
HTML/output-mode, elsewhere/non-software modes, Slack, and web-research-cache.

**Rejected alternatives.**
- *Delegate to CE at runtime (load `ce-ideate` when present).* Rejected: couples lifecycle to CE
  being installed at a compatible version and drags in CE's ecosystem (Proof, modes, conventions);
  contradicts the plugin's standalone Boundaries.
- *Keep the thin facilitative stubs.* Rejected: "produce a small option set; lead the user through
  choices" biases toward facilitation, which is why ideation felt like the operator supplied all the
  ideas. See LEARNINGS `{#stub-port-drops-engine}`.
- *Issue themes via `sdlc-manager`.* Rejected: `sdlc-manager` has no theme-clustering and issue
  *reads* are not its boundary (it owns mutation). `/ideate` reads issues read-only via `gh` and
  clusters them itself.

**Rationale.** The operator wanted CE's generative engine + survivors back, plus a genuine
partnership where their ideas also enter the pool and rejected ideas are revivable. Self-contained
keeps the plugin's ownership boundaries clean. Forked from CE 3.9.2; authored and adversarially
verified via an ultracode workflow (13 agents; 5 major findings remediated, 0 blocking).

**Revisit when.** CE ships a materially better ideation engine worth re-syncing, or the parallel-fork
maintenance cost exceeds the value of staying self-contained.

**Refs.** Plugin `0.3.0`, marketplace metadata `2.4.0`. LEARNINGS `{#stub-port-drops-engine}`. Plan
`.claude/plans/can-you-review-the-inherited-lantern.md`.

## 2026-05-31

### Rename `infiquetra-loop` → `infiquetra-lifecycle` (commit `0ed70f2`)  {#rename-loop-to-lifecycle}

**Decision.** Rename the plugin to `infiquetra-lifecycle`. "Loop" named only the `/loop` router
command, not the idea-to-ship lifecycle the plugin actually spans (Think → Plan & execute → Hand
off → Review → Improve & route). Renamed the ignored runtime-state dir to
`.claude/infiquetra-lifecycle/` and the handoff-envelope field `loop_owner` → `lifecycle_owner`,
with `sdlc-manager` updated in lockstep (its 4 hardcoded state-path references). Kept the `/loop`
command name unchanged — it's one verb in the lifecycle, not the whole thing. Surfaced the
five-phase command grouping in the plugin description, both READMEs, and the changelog so users see
the categorization.

**Rejected alternatives.**
- *`infiquetra-flow`.* Rejected: still reads too close to "loop" and is vaguer about scope.
- *`infiquetra-sdlc`.* Rejected: collides conceptually with the existing `sdlc-manager` plugin,
  blurring the boundary (lifecycle workflow vs GitHub issue/board ownership).
- *`infiquetra-cadence` / `-forge` / `-workbench`.* Rejected: evocative but less self-describing
  than "lifecycle".
- *Rewrite the old name in dated historical docs (brainstorms, ideation, plans, reviews,
  work-sessions, `ARCHIVE.md`).* Rejected per the journal rule "never silently overwrite history" —
  those artifacts record what the plugin was called at the time.

**Rationale.** The name should describe what the plugin does to a first-time user. "Lifecycle"
matches the description and command taxonomy; "loop" undersold it.

**Revisit when.** The plugin's scope narrows back to pure routing/iteration, or a clearer
single-word name for "full engineering lifecycle" emerges.

**Refs.** Plugin `0.2.0`, `sdlc-manager` `1.6.1`, marketplace metadata `2.3.0`.

### SDLC handoff issue artifacts belong to `sdlc-manager` (commit `2fc317e`)  {#sdlc-handoff-ownership-boundary}

**Decision.** Put handoff issue drafting, source artifact resolution, handoff maturity metadata,
prepared-draft sidecars, mutation plans, labels, board placement, and create-after-confirmation in
`sdlc-manager`. Keep `infiquetra-loop` responsible for lifecycle context and future `/handoff`
routing only.

**Rejected alternatives.**
- *Generate handoff issue bodies inside `infiquetra-loop`.* Rejected: it would duplicate SDLC
  issue semantics and make two plugins responsible for labels, project fields, and readiness.
- *Add a separate handoff artifact format.* Rejected: prepared issue drafts already provide the
  markdown plus JSON sidecar boundary needed for review before mutation.
- *Require recipient teams to have `infiquetra-loop` installed.* Rejected: handoff issues must be
  self-contained for agent teams or humans working only from GitHub.

**Rationale.** This keeps the lifecycle plugin thin at the exit point while centralizing SDLC
mutation rules in the plugin that already owns issue readiness. The prepared draft remains useful
without mutation, and `issue create-prepared` remains the single place where side effects are
rendered and confirmed.

**Revisit when.** Multiple non-SDLC destinations need the same handoff source resolver, or
`infiquetra-loop` grows durable lifecycle state that cannot be represented cleanly in the
prepared issue sidecar.

**Refs.** Plan [Add SDLC handoff flow](../plans/2026-05-30-002-feat-sdlc-handoff-flow-plan.md);
requirements [Infiquetra Loop SDLC Handoff](../brainstorms/2026-05-30-infiquetra-loop-sdlc-handoff-requirements.md).

### Prepared issue workflow uses draft/sidecar boundary plus confirmed mutation (commit `74cd372`)  {#prepared-issue-workflow-boundary}

**Decision.** Add `sdlc-manager issue prepare` and `issue create-prepared` as separate steps.
`issue prepare` writes a markdown draft and JSON sidecar; `issue create-prepared` re-runs
readiness, renders a mutation plan, asks for confirmation, repairs repo prerequisites, handles
mapping PRs, creates the issue, and records the result back onto the draft.

**Rejected alternatives.**
- *Direct source-text to `gh issue create`.* Rejected: bypasses review and makes readiness failures
  visible only after the external issue exists.
- *Put LLM interpretation inside `sdlc_manager.py`.* Rejected: the CLI should stay deterministic;
  skills and agents own rough-source interpretation.
- *Create new issue types for Asgard/Olympus.* Rejected: the six SDLC issue types remain
  canonical; team differences belong in readiness profiles and board/status routing.

**Rationale.** The split gives operators a durable review point before GitHub mutation while still
letting the final create flow perform repo repair and board placement as one visible plan.
Sidecars keep deterministic metadata and lifecycle state out of prose-only markdown, and
re-validation prevents stale edited drafts from bypassing team readiness.

**Revisit when.** Multiple non-agent callers need deterministic text-to-body generation inside the
CLI, or when prepared drafts become common enough to justify a richer review UI or batch create
surface.

**Refs.** LEARNINGS [prepared issue artifact boundary](LEARNINGS.md#prepared-issue-artifact-boundary).

## 2026-05-29

### Split Infiquetra lifecycle orchestration from deployment mutation (commit pending)  {#infiquetra-loop-deploy-boundary}

**Decision.** Add `infiquetra-loop` as the daily lifecycle orchestration plugin and
`infiquetra-deploy` as a separate deployment plugin. `infiquetra-loop` owns office-hours,
strategy, ideation, brainstorm, planning, work execution, code review, optimization, QA, SDLC
issue progress, engineering-journal prompts, retro, and resume. `infiquetra-deploy` owns
tag-promotion deployment, status, release notes, rollback, and hotfix helpers. `team-execution`
remains independent and is offered only when risk, size, or parallelism justify the cost.

**Rejected alternatives.**
- *One merged super-plugin.* Rejected: deployment mutation has a higher blast radius than
  lifecycle coaching and should keep a hard operational boundary.
- *Copy Superpowers, Compound Engineering, gstack, and VECU workflows wholesale.* Rejected:
  the useful pieces need to be adapted to Infiquetra docs, SDLC, and context-library references;
  generic cleanup, GitHub helper, and plugin-management utilities are intentionally out of scope.
- *Version raw loop state as repo artifacts.* Rejected: durable plans and work-session summaries
  belong in repo docs, but raw checkpoint state, API caches, validator JSON, and resume scratch
  are local session data and already covered by the `.claude/` ignore convention.

**Rationale.** The split lets the daily loop replace recurring Superpowers and Compound
Engineering lifecycle use while still enforcing a clear deployment safety boundary. Durable docs
give session-to-session continuity without committing stale runtime state. Keeping `team-execution`
separate preserves its validator and nonprod automation contract without forcing every loop to pay
that token or coordination cost.

**Revisit when.** Deployment policy moves out of tag-promotion, loop usage shows deployment
handoff friction dominates safety value, or `team-execution` becomes cheap enough to run by
default on normal work.

**Refs.** `plugins/infiquetra-loop/`, `plugins/deploy/`,
[team-execution v2 decision](#team-execution-v2-validators).

---

## 2026-05-27

### `team-execution` v2 uses context-selected validators and guarded nonprod automation (commit pending)  {#team-execution-v2-validators}

**Decision.** Evolve `team-execution` from reviewer-only orchestration into a reviewer plus
validator workflow. Validators are a maximum available roster, selected by repository context,
changed files, workflows, contracts, docs, tests, and optional `.team-execution.json`. Automation
is allowed only for `github.com/infiquetra/*`, only after gates pass, and only for nonprod or
publish-nonprod workflows.

**Rejected alternatives.**
- *Spawn every validator on every plan.* Rejected: creates noise, cost, and false blockers for
  validators unrelated to the change.
- *Let validators run before reviewer consensus.* Rejected: reviewer non-consensus means the
  implementation is still unstable; validator findings would be stale or duplicated.
- *Allow generic deployment automation once checks pass.* Rejected: production, staging, branch
  deletion, force-push, and credential changes carry a higher operational risk than this plugin
  should automate.

**Rationale.** Context selection keeps validator evidence proportional to risk while still making
the approved roster available. Gating validators after reviewer consensus creates a stable artifact
to scan and test. Nonprod-only automation gives useful end-to-end validation without turning a
planning plugin into a production deployment system.

**Revisit when.** We have repeated evidence that a validator category is always selected together
with another category and should be merged, or when production deployment safety is owned by a
separate audited release plugin.

**Refs.** LEARNINGS [team setup asset drift](LEARNINGS.md#team-setup-asset-drift).

---

## 2026-05-25

### `redis-channel` plugin: Hermes-agnostic Claude Code channel over Redis Streams (commit pending)  {#redis-bridge-decoupled}

**Decision.** Build the `redis-channel` plugin as a generic Claude Code channel that speaks a documented Redis-streams protocol — no Hermes-specific knowledge in the plugin. The Hermes-side counterpart (`hermes-claude-code-router`) lives in its own public GitHub repo so the protocol is reusable by any future consumer.

**Rejected alternatives.**
- *Embed Hermes/Discord logic directly into the plugin.* Rejected: would reimplement Discord voice-receive that already works (battle-tested) in `hermes-agent`. Verification confirmed the voice-receive code is **not** in `home-lab/asgard_voice_arbiter` (where the initial design assumed it lived) — the arbiter is routing-only; the sink/decode lives in closed-source `hermes-agent.gateway.platforms.discord`. Rebuilding would have been 3–5 days of unknown work.
- *Add the router as a 4th plugin inside `infiquetra/infiquetra-hermes-plugins`.* Considered seriously after `infiquetra-hermes-plugins` was identified as the canonical external-plugin pattern. Rejected per user preference for independent versioning. The router's expected LoC (~1k+) justifies its own home.
- *Use HTTP transport between plugin and router.* Rejected: Redis already runs on Mac mini for `voice_coordinator`; Streams give durable + ordered + consumer-group resume; no port-binding on either side; matches existing Hermes infra patterns.

**Rationale.** Decoupling means: (a) any future consumer (web UI, mobile app, CLI test harness) can drive a Claude Code session by speaking the protocol; (b) the plugin is testable without Hermes infrastructure; (c) protocol changes are version-gated, not implicit. The protocol spec (PROTOCOL.md) and pydantic models (`server/protocol.py`) are copied verbatim into both repos; synchronized PRs enforce drift detection at review time.

**Revisit when.** A second router consumer materializes and surfaces protocol shortcomings, OR the multi-session registry proves unused after 1 month of production data (then collapse to 1:1 lock and merge the router back into a more direct architecture).

**Refs.** [voice-only-permission-approval](#voice-only-permission-approval), [askuserquestion-interception](#askuserquestion-interception), [redis-bridge-verification](LEARNINGS.md#redis-bridge-verification), plan at `/Users/jefcox/.claude/plans/i-would-like-to-distributed-hanrahan.md`.

### Permission approval is voice-only in v1 with destructive echo-confirm (commit pending)  {#voice-only-permission-approval}

**Decision.** Tool-permission relay over the channel accepts only voice approval ("yes <id>" / "no <id>"). Discord button approval (ephemeral DM Allow/Deny) is deferred to v2. Destructive operations (Write/Edit/NotebookEdit + Bash regex matches in `is_destructive`) trigger an echo-confirm safety net: "Approving destructive Bash. Say 'cancel' within 3 seconds."

**Rejected alternatives.**
- *Voice + Discord buttons in parallel (first-wins).* Rejected for v1: adds discord.py interaction handling, ephemeral message lifecycle, race-cancel logic — and the parallel-path UX optimizes for a scenario that doesn't actually exist (you're either hands-free in voice OR at Discord text; rarely both). v2 candidate if usage shows demand.
- *Tool-class allowlist (voice can approve read-only, never destructive).* Rejected by user: they want full hands-free. Mitigated by destructive echo-confirm + audit logging from day 1; revisit if false-positive rate is non-trivial.
- *Always require terminal approval.* Rejected: defeats the hands-free use case.

**Rationale.** Whisper false-positive rate (~1.4% on clean audio, higher in noise) is a real risk for destructive commands. 5-char random IDs (~11.8M space, generated by Claude Code core) make accidental triggering unlikely; 30s window bounds exposure; echo-confirm provides a "did you really mean it" beat. Audit logging from day 1 produces the data needed to tighten or relax this later.

**Revisit when.** Audit logs show ≥1 false-positive destructive approval in a month, OR usage data shows users prefer Discord-button approval to voice approval (would justify the parallel-path build cost). See [Discord button approval](QUEUED.md#discord-button-approval).

**Refs.** [redis-bridge-decoupled](#redis-bridge-decoupled); `is_destructive` classifier at `plugins/redis-channel/server/protocol.py`.

### `AskUserQuestion` interception over agent-file coaching (commit pending)  {#askuserquestion-interception}

**Decision.** When Claude calls `AskUserQuestion` from a `redis-channel` channel session, the CC plugin's MCP server intercepts the tool call and converts the structured question to an inline-choice reply ("Which? A) ..., B) ..., C) ..."). The user's free-text response is parsed against the options and returned as the tool result. Agent-file coaching (in `agents/redis-channel-coach.md`) is provided as a friction-reducing hint but is **not** the enforcement layer.

**Rejected alternatives.**
- *Coach Claude via `agents/redis-channel-coach.md` to avoid AskUserQuestion when source is a channel.* Rejected as primary mechanism: Claude's training pulls it toward AskUserQuestion for clarification; coaching is probabilistic, not deterministic. Verified the channel protocol has no native facility by reading the official Discord channel plugin source + `https://code.claude.com/docs/en/channels-reference`.
- *Wait for the Claude Code channels protocol to add structured-question support.* Rejected: not on the published roadmap; would block v1.
- *Fail the AskUserQuestion call with an error so Claude retries with inline text.* Rejected: poor UX (user sees a tool error, not a question).

**Rationale.** Interception is deterministic. The MCP server sees every tool call before it reaches the user; converting it to a `reply` + parsing the next inbound is a finite-state interaction the server fully controls. Removes a category of "Claude ignored the coach" failures.

**Revisit when.** Claude Code adds a native `notifications/claude/channel/question_request` / `question_verdict` pair to the channel protocol — then replace interception with passthrough. Tracked in `plugins/redis-channel/PROTOCOL.md` "Reserved future expansion."

**Refs.** [redis-bridge-decoupled](#redis-bridge-decoupled); `plugins/redis-channel/PROTOCOL.md` AskUserQuestion section.

---

## 2026-05-08

### Adopt uv as canonical dependency sync (commit pending)  {#uv-canonical-sync}

**Decision.** Use uv as the canonical repository dependency sync tool. Track `uv.lock`, install CI dependencies with `uv sync --locked --extra dev`, and run local and CI checks through `uv run`.

**Rejected alternatives.**
- *Keep using pip in CI.* Rejected: it contradicts the desired repository standard and leaves installs unreproducible.
- *Use `uv pip install` without a lockfile.* Rejected: it is still an ad hoc install path and does not satisfy the existing revisit condition for tracking `uv.lock`.
- *Move all dev dependencies to `[dependency-groups]` now.* Rejected: the existing `dev` extra maps directly from the prior `pip install -e ".[dev]"` workflow, so moving dependency ownership would add churn without improving the conversion.

**Rationale.** The repository already has `pyproject.toml` metadata and had a documented revisit condition to track `uv.lock` once uv became canonical. A checked lockfile plus `uv sync --locked --extra dev` makes CI and local development use the same dependency graph.

**Revisit when.** uv stops being the repository development standard, or the project intentionally changes from extras-based dev dependencies to uv dependency groups.

**Refs.** Supersedes the `uv.lock` portion of [gitignore `.claude/` + no `uv.lock`](#gitignore-claude-and-no-uv-lock); archived pre-correction version in [ARCHIVE](ARCHIVE.md#superseded-no-uv-lock-decision).

---

## 2026-05-01

### Gitignore `.claude/`; `uv.lock` decision superseded (commit `4da5705`)  {#gitignore-claude-and-no-uv-lock}

**Decision.** Add `.claude/` to `.gitignore`. The prior decision not to track `uv.lock` is superseded by [Adopt uv as canonical dependency sync](#uv-canonical-sync).

**Rejected alternatives.**
- *Track `.claude/settings.local.json`.* Rejected: file holds per-user permission grants for the Claude Code session. Sharing one user's allowed-tool list would either leak local preferences or get blindly overwritten by the next user. The file is named `.local.json` for a reason.
- *Track `.claude/context/sdlc-plan-state.json`.* Rejected: mid-session orchestration state from `sdlc-manager`. Stale immediately after the session ends; would create misleading commits if pushed.

**Rationale.** `.claude/` content is per-user / per-session by design (settings.local + context state). The earlier `uv.lock` rationale was correct when the repo used ad hoc pip/uv installs, but no longer applies now that uv is the canonical lock-and-install path.

**Revisit when.** Claude Code introduces a *shared* settings file under `.claude/` that's intended to be checked in. At that point, narrow the gitignore from `.claude/` to specifically `.claude/settings.local.json` and `.claude/context/`.

**Refs.**
- DECISIONS [uv canonical sync](#uv-canonical-sync) — supersedes the lockfile portion of this decision.
- LEARNINGS [marketplace registry drift](LEARNINGS.md#marketplace-drift) — same PR (#112).
- ARCHIVE [PR #112](ARCHIVE.md#pr-112-marketplace-fix) — shipped record.
- ARCHIVE [superseded no-uv-lock decision](ARCHIVE.md#superseded-no-uv-lock-decision) — pre-correction record.

---

## Worker×Model cache scheduling — derive saga-side, reside team-side  {#worker-cache-scheduling}

**Date.** 2026-06-27. **Plan.** `docs/plans/2026-06-27-worker-model-cache-scheduling-plan.md` (from
`docs/brainstorms/2026-06-27-worker-model-cache-scheduling-requirements.md`, ideation S-1 build-first).

Port VECU's worker residency split along infiquetra's existing seam: **saga derives** (segment +
agent-id + tier), **team-execution resides** (named teammate + `SendMessage` reuse).

- **KTD1 — derivation saga-side, residency runtime team-side.** `Unit.depends_on`/`tier` already live
  in saga's `ExecutionSpec` (`execution_spec.py:176,:182`); `team_emitter.py:107` discards them.
  Derivation goes where the data is; team-execution consumes the emitted ids. *Rejected:* VECU's
  team-execution-side `worker_derivation.py` — right for VECU's primitive saga, wrong here.
- **KTD2 — segment boundary = plugin directory.** Single monorepo; VECU's repo-change proxy never fires.
- **KTD3 — stable agent id = segment/unit id**, replacing positional `worker-{i}` (residency needs a
  durable `SendMessage` handle).
- **KTD4 — behavioral residency is markdown protocol; the testable surface is the saga-side plumbing.**
  Reuse/wave/review-loop live in skills prose validated by `/doc-review` + operator runs + headroom
  telemetry; un-flatten + segmentation carry pytest. Consistent with the solo-operator measurement loop.
- **KTD5 — R15a context-GC excluded** — no harness lever (Messages-API-only).

**Revisit when.** Named-teammate residency proves insufficient (revisit warm-pool / crew-pairing); or a
single team-execution run shows enough internal idle-poll to justify a formal within-run wave queue.

**Refs.** Brainstorm requirements (origin); QUEUED [#ideate-brainstorm-do-less-bias](QUEUED.md#ideate-brainstorm-do-less-bias)
(skill-bias catch from the same session); ideation S-1.

**Doc-review addendum (2026-06-27).** A codex + agy adversarial pass + readiness review found 1 P0 + 4
P1, all fixed in the plan: `Unit` carried no file-path data for segmentation (added `Unit.files`); emit
cardinality was undefined (now **one row per segment**, KTD3); segment-level dependency derivation was
missing (KTD4 — collapse the unit dep graph to segments); and segmentation must not mutate the shared
`ExecutionSpec` (KTD5 — side mapping / copy). The "additive emitter" claim was corrected to
schema-breaking. Review record: `docs/reviews/2026-06-27-worker-model-cache-scheduling-review.md`.

---

## External engines are never gatekeepers {#external-engines-never-gatekeepers}

**Date.** 2026-07-01. **Plan.** `docs/plans/2026-07-01-external-engine-capability-routing-plan.md`
(from `docs/brainstorms/2026-06-27-external-engine-capability-routing-requirements.md`, VECU seed S-4,
#283). Saga gains a capability-aware registry + resolver + dispatch adapter for external LLM engines
(Codex, Gemini via agy). This decision fixes the trust boundary the whole capability rides on.

- **KTD — the binding rule.** Claude is verifier-of-record for every gated decision. An external
  engine may occupy generator, advisory-reviewer, or non-gated-worker roles only; it never holds a
  gated verdict that blocks a merge/deploy or persists as a gate. Enforced **structurally, not
  asserted**: external output is an `AdvisoryEvidence` value with no verdict field, and
  `engine_dispatch.satisfy_gate` raises unless a distinct Claude verification step has stamped it.
- **Why this is a NEW decision, not a restatement.** The parroting note (`DECISIONS.md:276-290`) is
  *evidence* (Antigravity parroted while Claude/Codex independently verified), not a standing rule;
  the gated-vs-advisory consensus split (`operator-choice.md:82-95`) is the *mechanism* this rides on.
  Neither previously bound external engines as non-gatekeepers — #283 establishes that rule.
- **KTD — registry home = saga.** The registry (YAML data, R4) + resolver live in saga because every
  seam they hook (the per-unit engine/capability field, `recommend_execution_backend`,
  `saga.orchestration_downgrade`, the reviewer role) is already there. *Rejected:* a new
  `external-engines` plugin (fragments the seams, adds an 8th marketplace plugin); folding into `agy`
  (conflates one engine's containment wrapper with the router; agy is in-repo, codex external).
- **KTD — `engine` is a parallel Unit field, not an extended tier.** `MODELS = (opus,sonnet,haiku)`
  is load-bearing for Claude-agent dispatch; the resolver reads `Unit.engine`/`Unit.capability`
  before `tier.model`. *Rejected:* widening the closed `MODELS` enum.
- **KTD — capability tie-break = cost·speed (operator-confirmed).** When variants rate a capability
  equally, the cheaper·faster variant wins (`cost_speed_rank`, registry order as final backstop).
  *Rejected:* corroboration-strength (operator chose cost·speed); prompt-on-every-tie (breaks
  autonomous dispatch, R20).
- **Revisit when.** The ideation-R14 read-only-sandbox profile ships (external workers may then mutate
  files, R23 second half); team-execution gains an external-engine worker context-package slot (then
  R10/R12 team-execution dispatch, deferred here as U12); or the seed capability data drifts
  materially (re-validated by use via `/retro`, R21, not a measurement loop). Readiness record:
  `docs/reviews/2026-07-01-external-engine-capability-routing-plan-readiness.md`.

---

## External-engine workers in team-execution: chaperone dispatch, not a second executor kind {#external-engine-chaperone-dispatch}

**Date.** 2026-07-02. **Plan.** `docs/plans/2026-07-02-team-execution-external-engine-workers-plan.md`
(#318, U12 follow-up from #283's ship-with-deferred). Fulfills the "team-execution gains an
external-engine worker context-package slot" revisit trigger recorded in
[External engines are never gatekeepers](#external-engines-never-gatekeepers).

- **KTD1 — chaperone worker, not coordinator dispatch.** One resident Claude worker
  (`worker-<engine>` / `worker-<capability>`) owns an engine's units end-to-end: resolve → wrapper
  dispatch → verify → apply as sole-committer → test → manifest. There is no second executor kind
  in wave scheduling — the engine is evidence the chaperone consumes (R23), never a participant in
  residency, review, or git. *Rejected:* the coordinator dispatching inline (context bloat per
  dispatch; a second driver-materialized manifest-writer mode; two executor kinds in wave
  scheduling for what should be one).
- **KTD2 — delegation intent drives chaperone tier, operator confirms.** `offload` defaults the
  chaperone to `sonnet/medium` (a heavier chaperone erases the token savings that motivated the
  delegation); `second-opinion` defaults it to `opus/high` (adversarial verification IS the
  product; extra spend assumed). The two intents pull tier in opposite directions, so this is a
  per-unit operator-confirmed recommendation in the `/plan` tier table, not a fixed policy.
  *Rejected:* one fixed chaperone tier (wrong for one intent by construction).
- **KTD5 — advisory validators are opt-in and structurally incapable of gating.** The
  `external-second-opinion` validator is selected only via `.team-execution.json`'s
  `external_second_opinion` key, never auto-selected by Phase A; its Gate Status can never resolve
  to `hard-fail`/`blocked` for completion purposes (R13/R15), and Required-Evidence Absence does
  not apply to it (it cannot be missing what it was never required to provide).
- **Naming carve-out (KTD3).** An explicit-engine unit renders `worker-<engine-key>` (the bare
  engine id, e.g. `worker-agy` — not `worker-agy/gemini-3.5-flash-high`); a capability-routed unit
  renders `worker-<capability-key>` with Engine cell `cap:<key>` — the plan previews only what is
  knowable at plan time, since the concrete engine for a capability route is resolved at run time.
- **Revisit when.** The ideation-R14 sandbox profile ships and file-mutating external workers
  become possible (issue #287) — this plan's evidence-only chaperone scope would need revisiting;
  or `/retro` surfaces that the sonnet/medium offload default is still eating more than it saves.
  Readiness record: `docs/reviews/2026-07-02-team-execution-external-engine-workers-plan-readiness.md`.

---

## Dispatch-time tier resolver: one seam mapping (role-class, work-shape, overrides) to {model, effort} {#dispatch-time-tier-resolver}

**Date.** 2026-07-05. **Plan.** `docs/plans/2026-07-05-dispatch-tier-resolver-plan.md` (#362, half of
the effort/tier vocabulary work alongside #363 and #370).

- **KTD1 — resolver + registry live in `fleet_commons`, not `saga/scripts`.** The vocabulary this
  work builds on (`tier_palette.py`) already lives in `fleet-core`, and the resolver is consumed
  cross-plugin (saga, team-execution, the workflow emitter) — `executor_profile_lint.py:89` already
  proves the `fleet_commons_shim.load(...)` consumption pattern works. This overrides an earlier
  Gate E draft that proposed `plugins/saga/scripts/tier_resolver.py`.
- **KTD2 — build on `tier_palette.py`, do not create a competing vocabulary.** `cheaper_fallback`'s
  ladder math uses the already-shipped `model_rank`/`effort_rank` (#463); #362 does not block on
  #370's `escalate`/`downgrade`/`clamp` named operations. When #370 lands them, the resolver migrates
  its inline rank math onto them as a later, mechanical swap.
- **KTD3 — `cheaper_fallback` = weaken model first, then effort.** "Cheaper" means stepping down one
  `MODELS` rung (strongest-first) before lowering effort, matching operator intuition ("drop to the
  next cheaper model before turning down reasoning depth"). At the ladder floor (weakest model,
  lowest effort) the fallback equals the resolved tier — a no-op floor, never an error.
- **KTD4 — the expensive-tier gate is pure/testable, `/plan` doc/CLI-driven, runtime-injected.**
  `fable`/`xhigh` tiers are gated behind an operator-confirm flag per the operator-choice framework;
  the gate function itself stays pure and unit-testable, with the confirm prompt injected by the
  caller (`/plan`), not baked into the resolver.
- **KTD5 — `role-tier:` is backward-compatible.** All 25 team-execution agent frontmatters gain a
  `role-tier:` value; the pre-existing bare `model:` literal is kept as a last-resort fallback, never
  removed.
- **KTD6 — dispatch-time resolution is this issue's scope; effort-as-first-class-citizen in the
  plan/worker table schema is #363's.** #362 emits into a table shape that #363 parses; schema
  alignment between the two is called out as a live comment on #363, not solved here.
- **KTD7 — `role-tier` is a small agent-facing vocabulary mapping cleanly onto work-shape registry
  keys, and the team-execution migration is tier-preserving by construction.** Verified against the
  current fleet: all 10 `*-reviewer` agents were `opus`, all 8 `*-tester` agents were `sonnet`, and
  all 7 `*-scanner`/`*-monitor`/`deploy-watcher` agents were `haiku`. Three `role-tier` values
  preserve each group's existing tier — `adversarial-review` → opus/high (reviewers),
  `contract-test` → sonnet/medium (testers), `mechanical-scan` → haiku/low
  (scanners/monitors/deploy-watcher) — resolving through the registry's `judgment`, `mechanical`,
  and `purely-mechanical` work-shape rows respectively (the sonnet-vs-haiku split already named at
  `plugins/saga/skills/plan/SKILL.md:301`). The migration changes no agent's effective model; a
  tier-preservation test asserts each of the 25 agents still resolves to its pre-migration model.
  Intentional re-tiering is explicitly out of scope for #362.
- **Revisit when.** #370 lands `escalate`/`downgrade`/`clamp` as named ladder operations (KTD2's
  planned migration point), or #363 lands the effort-first-class plan/worker table schema and needs
  the emission shape reconciled with what #362 renders (KTD6).

---

### Run-scoped spend budgets — price the tier lever with a guarded ordinal weight table (commit pending)  {#run-scoped-spend-budgets-366}

Issue #366 gives the fleet's one model/effort lever a notion of *magnitude*: a shared ordinal
cost-weight table, a run-scoped `spend_envelope`, an emit-time `cost_budget` HALT, and an effort-escrow
ledger. Operator chose the **full DoD** (escrow ledger in the same PR, not deferred). Outcome leaf
`sub-366` of `tier-effort-first-class`; the spend-*delta* classifier is the separate #367.

- **KTD1 — `cost_weights.json` + its `cost_weights.py` loader live in `fleet_commons/`, beside
  `models.json`, not in `saga/references/`.** The weight table must not drift from the `tier_palette`
  ordering it prices; co-locating it with the ordering source and validating monotonicity at load
  closes the `{#tier-vocab-ordering}` two-contracts gap. `execution_spec.py` loads it via
  `fleet_commons_shim.load("cost_weights")`, symmetric with `tier_palette`. This overrides the issue's
  *indicative* `plugins/saga/references/cost_weights.json` (the issue delegates the path to `/plan`).
- **KTD2 — weights are hand-authored ordinal values (non-linear allowed), not `rank + rung`
  arithmetic.** A hand-authored table lets `xhigh`/`opus`/`fable` be disproportionately expensive (a
  real cost signal) while a load-time monotonicity guard keeps it honest. Weights stay ordinal/relative
  — no dollar prices, stable across provider price changes.
- **KTD3 — the `cost_budget` HALT mirrors `VERIFY_N_CAP` exactly** (`execution_spec.py:489-500`): same
  fail-loud `SpecError`, both sides named, optional soft warn band. This is the correctness-critical
  facet — a false-negative silently lets an over-budget run proceed, violating the `/outcome` campaign's
  binding HALT-not-degrade rule — so its unit carries the adversarial verify gate at merge.
- **KTD4 — `spend_envelope`/`cost_budget` live on `ExecutionSpec` (per-run), not `OutcomeSpec`.**
  `OutcomeSpec` keeps its derived `cost_rollup` (R24 leaf-produced fact); a run-scoped budget on the
  coordinator would fight the grounding-brief `/outcome` law ("cost ledger = leaf-produced fact"). This
  resolves the DoD's "run/outcome spec" ambiguity toward the per-run spec.
- **KTD5 — `SpendEnvelope` is a pure accumulator primitive** (crossing iff `cumulative + delta >
  envelope` while `cumulative <= envelope`), tested in isolation. Its consumers are a new
  `execution_spec.py spend` CLI verb (real read) and `/work`'s #364 between-rounds escalation (doc). No
  autonomous runtime gate is built (#366: "not a new autonomous gate; the envelope is a CLI-set field").
- **KTD6 — the effort-escrow ledger is a self-contained module** (`allocate`/`record_actual`/`refund`/
  `request_escalation`, allocations in `to_spend()` units) with `effort-policy.yaml` real config it
  loads via PyYAML. `/work` records actuals (producer); the refund/escalation compute and `/plan`
  reading the policy are consumers. The escalation-request surfaces pre-execution, mirroring #364's
  between-rounds gate.
- **KTD7 — new test files are `test_cost_weights.py`, `test_spend_envelope.py`, `test_effort_ledger.py`;
  `cost_budget` over/under-budget tests land in the EXISTING `tests/test_saga_execution_spec.py`.** The
  issue names `tests/test_execution_spec.py`, which does not exist (same reconciliation #364 made). The
  AC `-k` selectors become test-function-name fragments so every AC check resolves.
- **KTD8 — the `cost_budget` sum accounts for call MULTIPLICITY, not one weight per unit (surfaced by
  doc-review).** A fan-out unit runs its op `len(targets)` times and a verify panel adds `n` verifier
  calls at the unit's tier (× iterations when it iterates to consensus), so `unit_spend = to_spend(tier)
  × max(len(targets),1) + verify.n × to_spend(tier) × iterations`. A `pilot` is a separate declared unit
  counted on its own row and is deliberately not re-added (double-count guard). A one-weight-per-unit sum
  would undercount exactly the expensive fan-out/panel plans and false-negative the HALT — the
  HALT-not-degrade violation U2 exists to prevent, which is why U2 carries the adversarial gate.
- **Revisit when.** A second emitter (`team-execution`'s markdown path) needs budget parity and must
  consume the shared `cost_weights.json`; or #367's spend-delta classifier lands and the ordinal weight
  unit needs reconciling with its `spend_delta`/`adjacent_tier` ordering math.

---

### Spend-delta machinery — one three-way direction primitive built on the existing ordering (commit pending)  {#spend-delta-machinery-367}

Issue #367 gives `/plan` and `/work` one shared primitive for tier-spend *direction*: a
`spend_delta(old, new) -> {cheapen | escalate | lateral}` classifier, a `worth_it_because` +
`cheaper_fallback` validate hard-block, a relative `adjacent_tier` lever, and a
`.saga/spend-authority.json` silent/ask matrix. The **final leaf** `sub-367` of `tier-effort-first-class`
— merging it completes the outcome (9/9). Backend inline; saga-only.

- **KTD1 — `spend_delta` is per-axis ordering (three-way), not `to_spend` magnitude.** The `lateral`
  bucket is for sideways axis trades (stronger model + weaker effort). `to_spend` (#366) is a total order
  and injective over the 16 distinct cost cells, so a magnitude classifier could never yield `lateral`.
  `to_spend` answers "how much?"; `spend_delta` answers "which way?" — different primitives.
- **KTD2 — `spend_delta` generalizes `is_escalation`; the latter becomes `spend_delta(...)=="escalate"`.**
  One primitive, no parallel two-way/three-way vocabulary. A grid guard test proves equivalence so #365's
  `/tier` gate is behavior-preserved.
- **KTD3 — `spend_delta` + `adjacent_tier` live in `execution_spec.py`, not fleet_commons.** They are
  `Tier`-typed (the dataclass lives in saga) and sit beside `is_escalation`. `adjacent_tier("cheaper")`
  reuses `tier_resolver.cheaper_fallback` (#362, via the shim) so the down-rung logic is not duplicated;
  `dearer` uses `tier_palette.escalate`. This keeps #367 saga-only — no fleet-core bump (reuse, not
  modify).
- **KTD4 — `adjacent_tier` raises at ladder boundaries.** `cheaper_fallback`'s floor no-op (returns the
  same tier) is converted to a raise; `dearer` raises at the ceiling. The issue's explicit "boundary
  calls raise rather than silently clamping/wrapping."
- **KTD5 — one shared `sonnet/high` baseline for both the worth-it hard-block and the spend-authority
  default.** Both trigger on `is_escalation(SPEND_BASELINE, tier)` with `SPEND_BASELINE = sonnet/high`, so
  the two levers cannot disagree about what "premium" means.
- **KTD6 — `.saga/spend-authority.json` is a `silent_ceiling` tier, not a 16-cell map.** Modeled on a
  signature-authority limit ("authorized silently up to tier X"); the resolver compares via
  `is_escalation` (re-expressed on dict tiers, pinned to `is_escalation` by an exhaustive grid test).
  Absent → `sonnet/high`; malformed → loud `SpendAuthorityError` (the #368 `tier_defaults.py` precedent).
- **KTD7 — test placement:** `spend_delta`/`adjacent_tier` → new `tests/test_spend_delta.py`; the
  worth-it hard-block → existing `tests/test_saga_execution_spec.py`; spend-authority →
  `tests/test_spend_authority.py`. The issue's `tests/test_execution_spec.py` does not exist.
- **KTD8 — the worth-it hard-block is `require_receipts`-gated, not unconditional (implementation-forced).**
  The AC says "fails `validate()`", but the non-goal ("no retroactive backfill — new specs going forward")
  forbids an unconditional check: `validate()` runs on every emit and every existing spec (75 emitter
  tests break). Resolution: a `validate(require_receipts=True)` gate `/plan` sets at authoring; `emit()`
  and existing specs use the default `validate()` unchanged. Interaction: `/tier`-patching (#365) up to a
  premium tier is subject to the same authoring gate — a deliberate extension.
- **KTD9 — `SPEND_BASELINE = sonnet/high`, not sonnet/medium.** The issue's premium set "(opus, fable,
  xhigh in either axis)" — which omits `high` — is authoritative over the "sonnet/medium baseline"
  phrasing; `is_escalation(sonnet/high, tier)` yields exactly that set and avoids retroactively flagging
  common `sonnet/high` units.
- **Revisit when.** The `ask` path needs an actual operator-prompt surface (single vs batched), or a
  cross-repo authority registry is wanted beyond the single per-repo `.saga/spend-authority.json`.

---

## 2026-07-06

### /outcome completion harvest — supply the missing PR-ref producer, don't touch the consumers  {#outcome-completion-harvest-writeback-495}

Issue #495 (the first `/outcome` dogfood defect, found running `tier-effort-first-class` / objective
#343): code-leaf completion harvest silently never fired. The `code:pr-merged` barrier and the auto-merge
queue both *consume* `node.github["pr"]`, but the record-only dispatch → native `/work` → squash-merge
flow never *produced* it. Backend inline; saga-only.

- **KTD1 — Supply the one missing producer (`link-pr`); do not change the consumers.** Both the harvester
  barrier (`outcome_orchestrator.py:100-112`) and `outcome_merge._is_mergeable_kind` (`:170`, which
  requires `bool(node.github.get("pr"))` before it will queue a merge) consume the ref, so one producer
  unblocks both. **Rejected: a merge-time writeback** — vacuous, since the merge queue already requires
  the ref to act. **Rejected: a closing-PR timeline resolver** — `issue_close_info`/`_closed_by` surface
  only the closing *actor*, a robust closing-PR query is edge-case-heavy, and it would not even have
  fired for the tier-effort leaves (their sub-issues were closed manually, not by a keyword-closing PR).
- **KTD2 — Normalize refs at READ time, in `outcome_github`, via a components `_parse_ref`.** Read-time
  normalization repairs already-committed specs (tier-effort's `owner/repo#N` issue refs) with no
  migration. `_parse_ref → (owner, repo, number)` is consumed by both the `view` calls (which build a
  gh-consumable URL via `_gh_ref`) and `_closed_by`'s REST events path (which needs the components) — so
  normalizing a view-ref to a URL never starves `_closed_by` (the doc-review coupling guard).
- **KTD3 — `owner/repo#N` → full URL, not `N --repo owner/repo`.** A URL is one cwd-independent positional
  token, uniform across pr/issue; the caller's kind picks `/pull/` vs `/issues/`. Full URLs and bare
  numbers pass through unchanged.
- **KTD4 — `link-pr` writes local + optional `--push`; no auto-commit by default.** Consistent with
  `prune`/`promote` (`save_spec` local) and the R26/R27 explicit-bank cadence. It attaches a *pointer* —
  the barrier re-verifies `merged`, so a wrong/unmerged link never falsely completes a node.
- **KTD5 — R17 is untouched (rejected the "self-describing artifact" broadening).** The fix operates on
  GitHub refs + completion events, never persists derived `node.state`/`complete` into the committed spec
  JSON. The operator confirmed the outcome is already durably reconstructable (committed gh-consumable PR
  refs + reconstruct-on-advance); `node.state: pending` in the JSON is authoring-time by design.
- **KTD6 — "Automatic" = the attended verb, not zero-touch (operator-confirmed scope).** In an attended
  outcome an explicit `link-pr` verb IS the automation (vs hand-editing committed JSON + re-commit). A
  zero-touch autonomous producer is **deferred**, on evidence: no code leaf has ever reached the auto-merge
  queue (all outcomes ran attended/inline), and its auto-mechanisms are fragile or couple the leaf to the
  coordinator.
- **KTD7 — test placement:** ref normalization + the `code:pr-merged` guard → `tests/test_outcome_completion.py`;
  the `link-pr` verb → `tests/test_outcome_command.py`; the end-to-end harvest loop → `tests/test_outcome_integration.py`.
- **Revisit when.** The autonomous auto-merge path is actually exercised (then build the zero-touch
  producer — a coordinator-side read of the dispatched leaf saga's PR ref), or ingestion is changed to
  store full-URL refs at the source.

---

### /outcome attend — resolve the leaf's real issue-backed saga id at the handoff seam  {#outcome-attend-issue-backed-handoff-491}

Issue #491 (last execution-discovered defect of the `tier-effort-first-class` dogfood, objective #343):
`/outcome attend` printed the dispatcher's raw `leaf_saga_id` (`leaf-<outcome>-<subplot>`), a dead
`/resume` pointer — an issue-backed leaf's real native saga is `issue-<N>`. Backend inline; saga-only.

- **KTD1 — Resolve `issue-<N>` from the node, prefer bare `sub_issue`.** A node's `github` carries both
  `sub_issue` (bare int) and `issue` (`owner/repo#N`); prefer the digit `sub_issue`, else parse `issue`
  via `outcome_github._parse_ref` (landed in #495 — the two dogfood defects share one primitive).
- **KTD2 — Inline `f"issue-{N}"`, don't import `saga`.** Mirrors `saga.derive_saga_id` (`saga.py:333`);
  `outcome.py` deliberately imports only its `outcome_*` siblings, so a one-line format doesn't justify
  pulling in the heavy `saga` module. Cited in a comment so drift is catchable.
- **KTD3 — `attend` loads the spec.** It read only the dispatch ledger before; it now `load_spec` +
  `node_by_id` to reach `node.github`, with a node-miss / no-issue fallback to the raw id (never raises).
- **KTD4 — Scope is `attend` only.** `outcome_report.py` was verified to never emit the leaf handoff
  (`AttentionItem` carries only `subplot_id`; it never calls `attend`); the issue title's "attend/report"
  over-scoped. Corrected here so a reader doesn't think the report was missed.
- **Revisit when.** A non-issue-backed (task/ad-hoc) leaf needs a resolvable native id beyond the raw
  `leaf_saga_id` fallback — then extend the resolver for the `task-<slug>` case.

---

### Decompose a stale multi-issue objective into an `/outcome` DAG: re-triage first, seed flat, edge only what is genuinely hard, correct on the issue  {#outcome-dag-decompose-stale-objective-336}

Standing up objective #336 ("external-engine offload lane", 20 children) as the `external-engine-offload` `/outcome` DAG so the operator works it hands-on. The children's drafts were authored at Gate E (2026-07-03/04) and had drifted against substrate that shipped since (#401 ledger, #343 tier/effort, the 2026-07-05 first-party-codex decision).

- **KTD1 — Seed via `outcome start --from-objective`, accept a flat DAG.** Edge inference reads each sub-issue's GitHub `blocked_by` list (`outcome_edges.edges_from_relationships`); the 21 siblings had none, so the seed is a flat 21-node frontier. That is *honest*, not a gap: the lane's substrate (registry/resolver/dispatch/gates/manifests from #283/#285/#318, ledger from #401) already shipped, so the children are independent extensions. Do NOT invent dependency edges to express priority.
- **KTD2 — Value-ordering is operator frontier choice + `approve`-gating, never fake edges.** HTTP-cloud-first is a *priority*, not a hard dependency; overloading `depends_on` with priority lies about the graph and blocks legitimate parallelism. The operator sequences the ready frontier; `advance` only dispatches an `approve`d frontier (R20).
- **KTD3 — Encode only genuinely-hard edges.** Exactly one added by hand: `sub-384 -> {sub-383, sub-476}` — the tripwires audit cannot audit a receipt schema (#383) or a codex bridge (#476) that does not exist. It flipped `sub-384` `ready -> blocked`, confirming the reconcile loop honors it. Hand-edit the spec JSON `depends_on`, then `load_spec` (which `validate()`s declared-target + Kahn acyclicity) before commit.
- **KTD4 — Re-triage before decompose; fold what is already shipped.** A read-only triage of all 21 children against current HEAD found 5 stale "verified absent" draft claims and one fold: #392 -> #390 (3 of its 4 facets already shipped via #318/#319; the surviving invocation-proof discriminator is #390's fail-loud concern). Pruned `sub-392` (R33), closed #392 not-planned, grew #390.
- **KTD5 — Persist corrections onto the artifact the planner reads (the issue), not a side doc.** `/plan` Phase 0.1 reads the issue thread, so 7 scope-note comments (#387/#386/#390/#393/#381/#383/#384) make each stale draft self-correct at plan time — the operator need not remember. Same R17/derived-truth principle one level down: durable state belongs where it is consumed.
- **Durability.** Spec lives on branch `outcome/external-engine-offload` (R26, never main), committed via `outcome commit` (path-limited to the spec file, refuses on main) + pushed; a new machine reconstructs by pulling the branch and re-harvesting from GitHub (R27).
- **Revisit when.** A future `--from-objective` seed where GitHub `blocked_by` IS populated on the children — then edges auto-infer and KTD3's manual step is redundant; consider setting `blocked_by` on GitHub as the durable, re-derivable home for a hard edge instead of a spec-local edit.

---

### First-party codex bridge plugin: agy-grammar mirror, synchronous-only envelope, same-commit drift-guard move {#codex-first-party-bridge-476}

**Context.** `docs/plans/2026-07-06-codex-first-party-bridge-plugin-plan.md` (#476). Wave B keystone of the `external-engine-offload` outcome: the only leaf unblocking another (`sub-384`), and the pending codex receipt emitter the drift guard tracks as `PENDING_EMITTERS = {"codex-bridge": "#476"}`. Retires the openai-codex marketplace plugin lane, whose session-scoped jobs, `--wait`/Bash-ceiling collision, and unmodifiable upstream source made it structurally wrong for fleet dispatch (evidence in #476, 2026-07-05).

- **KTD1 — Mirror the agy delegation grammar (`codex.delegation.v1`), don't invent a codex-shaped one.** Same role/mode/lens/status vocabulary, same bundle file names, `.claude/codex/runs/<run-id>/`. One fleet delegation shape: #384's auditor and operators learn one grammar. *Rejected:* a bespoke codex-specific schema — forks the auditing surface for zero capability gain.
- **KTD2 — Synchronous supervised subprocess; zero plugin-level job state.** Timeout kills the process tree; every exit is a terminal status; the plugin never writes `running`, making the marketplace plugin's zombie-state failure class structurally impossible. Long runs ride the caller's mechanism (harness background Bash). *Rejected:* v1 detach+poll — durable cross-session job state is exactly the surface that rotted upstream; deferred with the issue's hard requirements recorded.
- **KTD3 — Invocation shape verified live on codex-cli 0.142.5.** `codex exec --json -o <last-message> -s <sandbox> -m <model> -c model_reasoning_effort=<effort> --ephemeral`, prompt via stdin (write-then-close; codex appends piped stdin as a `<stdin>` block and blocks on an open pipe). Raw JSONL capture is the transcript contract; token accounting parses tolerantly. *Rejected:* argv prompt delivery (ps-visible, argv-length-bounded) and relying on `~/.codex/sessions` for evidence (host cache, not a contract).
- **KTD4 — Registry recipe correction rides the rewire.** The rows' `recipe: "codex -s read-only --effort high"` names a flag that does not exist on 0.142.5 (verified: no `--effort` in `codex exec --help`; live probe of `-c model_reasoning_effort` succeeded). The registry is machine-consumed truth; a stale recipe there is registry drift, not prose. *Rejected:* deferring the correction to a docs pass.
- **KTD5 — Fleet-dispatch write posture unchanged.** Rows keep `write_capable: false`; `build_codex_invocation`'s halt-on-write stands. Write-capable `task` mode is the plugin's operator surface (patch-capture in a disposable clone), not a dispatch capability, until the patch path has operational history. *Rejected:* enabling sandboxed-mutate dispatch for codex in the keystone landing.
- **KTD6 — Same-commit drift-guard move.** `tests/test_bridge_receipt_drift.py` sentinels on `plugins/codex/` existing; scaffold + emit-wired delegate + `PENDING_EMITTERS -> IN_REPO_EMITTERS` land in one commit so the tree is never intentionally red. *Rejected:* cross-commit sequencing.
- **Revisit when.** Task-mode patch capture has operational history (lift KTD5 toward agy-parity sandboxed-mutate dispatch), or a driving-session need for >10-minute codex runs materializes that background Bash cannot serve (then design detach+poll against the issue's never-`running`-for-dead requirement).

---

### Runtime delegation tripwires: hooks live in saga, the classifier/corroborator lives in fleet-core {#delegation-tripwire-hook-home-384}

**Context.** `docs/plans/2026-07-07-delegation-tripwires-plan.md` (#384, KTD1). Wiring fleet's
existing, manual, post-hoc delegation auditing (agy's `classify_transcript`,
`audit_harness_transcript.py`) into always-on runtime tripwires: an armed `PreToolUse` block plus
a `Stop`/`SubagentStop` audit, with codex needing the same classification algorithm agy already has.

- **KTD1 — Hooks live in `plugins/saga/hooks/`; the engine-parametrized classifier and
  corroborator live in `plugins/fleet-core/scripts/fleet_commons/delegation_audit.py`.** saga is
  the only plugin with hook-registration precedent (`tests/test_spore_hooks_registration.py`) and
  already owns the dispatch layer (`engine_dispatch.py`) the tripwires must arm around; root
  `.claude/settings.json` is gitignored and cannot host hooks at all. The classifier/corroborator,
  by contrast, must serve two engines (agy, codex) identically, so it is one fleet-core module
  loaded through the established vendored-shim mechanism (`{#fleet-commons-mechanism-463}`) —
  the same way `engine_dispatch.py` already loads `bridge_receipt` (`engine_dispatch.py:15,21`).
  *Rejected:* hosting the hooks in agy with a hand-mirrored copy for codex — this is exactly the
  mirroring drift vector `{#unit-panels-vs-whole-diff-lenses-476}` documented one round earlier;
  a second parallel mirror was not worth relitigating.
- **Revisit when.** A third plugin needs its own delegation-bearing hooks (not just an engine
  config in the fleet-core auditor) — then reconsider whether hook ownership should move to a
  dedicated hooks-hosting plugin rather than staying bolted onto saga by precedent alone.

---

### `DELEGATION_INTEGRITY` lives at the dispatch layer, not inside either wrapper's `STATUSES` {#delegation-integrity-dispatch-layer-384}

**Context.** Same plan (#384, KTD6). The issue draft proposed adding `DELEGATION_INTEGRITY`
alongside `fallback_suspected` inside `agy_delegate.py`'s wrapper status vocabulary.

- **KTD6 — Compute divergence in `engine_dispatch.reconcile()`/`provenance_manifest.Disposition`,
  not in either engine wrapper.** Grounding showed `fallback_suspected` already names two
  *unrelated* mechanisms sharing one string inside agy: transcript classification
  (`agy_delegate.py:1021`) and log-marker status (`agy_delegate.py:1374`). Adding a third,
  dispatch-scoped condition into that same wrapper vocabulary would compound the conflation
  rather than resolve it. `DELEGATION_INTEGRITY` names the divergence between the engine's
  self-report and the independent observer signal (transcript classification + bundle
  corroboration) — that reconciliation only makes sense at the dispatch layer, which is the one
  place both signals are visible together; wrappers stay single-signal emitters and never
  self-adjudicate. *Rejected:* the issue draft's "add alongside `fallback_suspected` in
  `agy_delegate.py`" — it would have planted a third meaning on an already-overloaded name inside
  a single-signal component.
- **Revisit when.** agy's `classify_transcript` is eventually consolidated into the fleet-core
  auditor (tracked as deferred follow-up on #384/#517) — at that point re-examine whether
  `fallback_suspected`'s two conflated wrapper meanings can finally be split apart now that the
  dispatch layer no longer depends on either one directly.

---

### Evidence ledger (#398): committed per-saga custody, attempt-keyed identity, HALT on self-certify {#evidence-ledger-ktds-398}

**Date:** 2026-07-12 · **Plan:** `docs/plans/2026-07-12-evidence-ledger-plan.md` · **Issue:** #398
(root leaf of outcome `evidence-integrity`; sub-396/397/402 consume the API)

**Decision.** `/qa` §5.1 and `/code-review` §5.3 durable-verdict writes route through a new
`plugins/saga/scripts/evidence_ledger.py`: content-addressed (sha256) write-once artifacts plus an
append-only, hash-chained JSONL custody log, with frozen pre-registered criteria and a closure-time
re-hash verify that HALTs on tamper or producer self-certification.

- **KTD1 — ledger home is committed, per-saga** (`docs/evidence/<saga-id>/ledger.jsonl`).
  Committed-is-canonical (the R26/R27 philosophy): a fresh clone verifies the chain; custody is
  auditable in PR history; per-saga files remove cross-branch JSONL merge conflicts.
  Rejected: one global ledger (routine EOF conflicts); git-common-dir cache (evidence dies with
  the machine). Operator-confirmed.
- **KTD2 — identity is (check_id, reviewed_sha, attempt).** Same-identity rewrite → rejected;
  a retry is a new attempt that appends. The reader groups by (check_id, reviewed_sha) and flags
  FAIL→PASS as supersession — attempt in the key is what reconciles "no clobber" with
  "preserve FAIL history".
- **KTD3 — per-entry prev-hash chain** over canonical JSON, so tampering with the log itself is
  detectable — git history alone is not sufficient (local edits/force-push rewrite both).
- **KTD4 — self-certification HALTs**, never flags: a flagged violation inside a green run is
  exactly the silent-pass failure mode the issue exists to kill (HALT-not-degrade).
- **KTD5 — dual surface**: argparse CLI (SKILL.md prose call sites) + importable API
  (tests, sub-397 closure gate).
- **KTD6 — reuse `outcome_store._write_once`/`_atomic_write` via import** per the
  `manifest_store` precedent; the only new primitive is an O_APPEND+fsync JSONL append. No
  modification to `outcome_store` (issue's additive-only constraint).

**Revisit when** a multi-writer path appears on one saga's ledger (parallel worktree gates) —
add cross-process locking mirroring `outcome_store`'s locks_dir — or when sub-396/402 need entry
kinds beyond `evidence`/`criteria`/`closure` (the open `payload` dict is the extension seam).

---

### Delegation audit store (#396): machine-local durable mirror, fleet-core home, write-once drafts {#delegation-audit-store-ktds-396}

**Date:** 2026-07-12 · **Plan:** `docs/plans/2026-07-12-issue-396-delegation-audit-store-plan.md` ·
**Issue:** #396 (leaf `sub-396` of outcome `evidence-integrity`; depends on #398/PR #567 and #383
`bridge_receipt.v1`, both already landed)

**Decision.** `agy_delegate.py` and `engine_dispatch.py` mirror every receipt and provenance manifest
to a new durable store (`~/.claude/delegation-audit` by default), the chaperone-dispatch path
snapshots the external engine's raw pre-fix output write-once before applying any fix, and a new
`/delegation-audit` surface reconciles the durable store to flag claimed-but-unproven delegations as
no-ops.

- **KTD1 — shared primitives live in fleet-core** (`fleet_commons/audit_store.py`), not saga: agy,
  saga, and team-execution all need symmetric access, and fleet-core is the existing install-boundary-
  safe home for exactly this shape of cross-plugin primitive (the same rationale `bridge_receipt.py`
  already documents).
- **KTD2 — duplicate, don't cross-import, the small atomic-write/write-once/safe-name primitives.**
  Importing `plugins/saga/scripts/outcome_store.py` from fleet-core would reintroduce the install-time
  break `bridge_receipt.py`'s docstring warns against; the duplicated surface is ~25 lines.
  Deliberately mirrors the opposite call evidence_ledger.py's KTD1 made (see above) — that ledger
  answers "does a fresh clone on a different machine need to verify this," this store answers "does
  this survive worktree teardown on the same machine" — different requirements, different homes.
- **KTD3 — machine-local, uncommitted store root**, chosen deliberately opposite to
  evidence_ledger's committed-per-saga home: delegation evidence must outlive a torn-down worktree on
  the *same* machine, never needs to reach a different developer's clone, and committing raw
  diffs/receipts to every PR would bloat history for no reader.
- **KTD4 — new, distinctly-named module** (`audit_store.py`) beside the existing
  `fleet_commons/delegation_audit.py` (#384) rather than folding into or renaming it: that module
  already owns live-transcript classification and bundle corroboration over the disposable location
  this issue exists to escape; the new `reconcile_store` function extends it to read the durable store
  instead, reusing its `REAL`/`FALLBACK_SUSPECTED` vocabulary rather than inventing a parallel one.
- **KTD5 — default-on lives at the outermost entry point only.** `agy_delegate.py`'s CLI resolves the
  home-dir default when `--audit-store` is omitted; every underlying function defaults its
  `audit_store_root` parameter to `None` (skip), so direct unit-test callers never touch a real
  developer's home directory unless they ask to. `engine_dispatch.py` has no CLI, so its default-on
  behavior lives in the documented chaperone call site instead.
- **KTD6 — every existing subprocess-driven CLI test for `agy_delegate.py` isolates `--audit-store`
  explicitly**, named so the home-directory-pollution risk a CLI-level home-dir default creates is
  never an implicit landmine for a later contributor.

**Revisit when** a future issue asks for cross-machine aggregation of the audit store (KTD3
deliberately keeps it machine-local today) or a retention/pruning policy is needed as
`~/.claude/delegation-audit` grows unbounded.
### Closure gate (#397): required-check set + SHA override in `node.evidence`, supersession is a payload convention {#closure-gate-ktds-397}

**Date:** 2026-07-12 · **Plan:** `docs/plans/2026-07-12-closure-gate-plan.md` · **Issue:** #397
(consumer of #398's evidence ledger; sub-397 of outcome `evidence-integrity`)

**Decision.** `plugins/saga/scripts/closure_gate.py` wires the evidence ledger into
`outcome_orchestrator.harvest()`'s completion barrier: a leaf is never harvested `done` without
passing its declared required checks at the exact SHA the outcome is closing at, and a FAIL can
never be silently cleared by an unexplained later PASS.

- **KTD1 — required-check set + optional SHA override live in `Node.evidence`.** `evidence` was
  already documented as an open pass-through map whose schema lands with its consuming units
  (`references/outcome-spec.md:54`); this is the first consumer to give it one:
  `required_checks: list[str]` + optional `reviewed_sha` override. Rejected: a new top-level
  `Node` field (schema surgery on an already-reserved seam).
- **KTD2 — close-SHA resolution: explicit override wins; else the PR's pre-merge head SHA for a
  `code` node** (`outcome_github.head_ref_oid`), never the post-squash merge-commit SHA on `main`
  (which never matches any evidence entry — `/qa`/`/code-review` reviewed the branch head, not the
  merge commit). A `non-code` node with no override and no PR HALTs `unresolvable-close-sha`
  rather than silently skipping a declared required check.
- **KTD3 — supersession is a `payload["supersession_reason"]` convention, not a new ledger entry
  kind.** `evidence_ledger.write()`'s `payload` is explicitly reserved for downstream extension
  (evidence-ledger plan R10 names sub-397 directly); adding a `kind: "supersession"` entry type
  would be schema surgery on an already-merged, already-tested module for a distinction the open
  payload dict already carries.
- **KTD4 — one additive read helper, `evidence_ledger.history(store, check_id=...)`.**
  `latest()` is scoped to one exact `(check_id, reviewed_sha)`, so it alone cannot distinguish
  "never ran" (missing-evidence) from "ran, but only at a different SHA" (stale-sha); `history()`
  returns every entry for a check across every SHA so the gate can tell them apart.
- **KTD5 — the gate calls the already-shipped `verify_chain()` once per evaluation** before
  trusting any read, so a tampered chain HALTs rather than silently trusting a compromised log.
- **KTD6 — `harvest()`/`barrier_report()` gain a defaulted `repo_root: Path = Path(".")`.** The
  ledger is a committed repo-tree path, distinct from the git-common-dir cache `store` already
  resolves. Defaulted so every existing test call site and every outcome spec that declares no
  `required_checks` (all of them, today) is unaffected; the two real production call sites
  (`outcome.py`'s `production_harvester`) already have `repo_root` in scope.
- **KTD7 — verdict classification is closure_gate's own closed vocabulary, found during
  implementation self-review, not `evidence_ledger.latest()`'s `superseded_fail` flag.**
  `latest()` hardcodes a literal `"FAIL"` sentinel — correct for a synthetic fixture, but blind to
  what the shipped producers actually write (`/qa`: `ship`/`ship-with-deferred`/`no-ship`;
  `/code-review`: `clean`/`blocked`; neither ever writes literal `"FAIL"`/`"PASS"`). Relying on the
  literal sentinel would have silently treated a real `no-ship`/`blocked` verdict as satisfied —
  exactly the silent-pass failure this issue exists to kill. `closure_gate.py` reads
  `evidence_ledger.history()` directly and classifies against its own closed vocabulary; an
  unrecognized verdict HALTs `unrecognized-verdict:<check_id>` rather than being assumed to pass.

**Revisit when** a non-`code` node needs native close-SHA gating without an explicit override
(a tracking-issue close-event hash, e.g.), or when an operator wants closure-gate HALTs surfaced
through `outcome_report.py`'s `TIER_AMBIGUITY` scan rather than only via `barrier_report()`'s
per-node `closure_gate` key.

---
### Delegation-integrity requeue counter lives in the delegation-state marker family {#integrity-counter-home-520}

**Date:** 2026-07-13 · **Issue:** #520 (closes #384 review F1/F4/F5) · **Origin:** #384 plan KTD7

**Decision.** The KTD7 re-queue-once-then-HALT consecutive-divergence count persists in
`.claude/delegation/integrity.json` — a sibling of `active.json` in the delegation-state marker
family, owned by `fleet_commons/delegation_state.py` (`record_integrity_divergence` /
`integrity_attempts` / `clear_integrity_attempts`), keyed `session_id` + `engine`, 4h TTL,
fail-open reads, and writes serialized under the same new `_write_lock` (`fcntl.flock` on a
sibling `.lock` file) that #520 F4 adds for `arm()`/`disarm()`. `engine_dispatch.py` reads the
count back at dispatch entry and keeps its old module-level dict only as a fallback when the
durable store is unavailable (version-skewed fleet-core, unwritable filesystem) — same-process
behavior is then never worse than pre-#520.

**Rejected alternatives.**
- *Manifest record* (the plan KTD7 wording): manifests are per-`execution_id` artifacts written
  by the consumer *after* dispatch returns — dispatch entry would need to scan/index another
  store it doesn't own, and a consumer that never persists the RequeueDisposition's manifest
  would silently break the count. The counter must be written by the same layer that enforces
  the HALT.
- *Module-level dict* (status quo): provably degrades to requeue-forever for
  one-process-per-attempt consumers — the F1 finding itself.
- *A saga-side private file written by `engine_dispatch` directly*: avoids fleet-core version
  coupling but forks `.claude/delegation/` ownership across two plugins and duplicates the
  locking/TTL/fail-open plumbing `delegation_state` already carries; the skew case is already
  handled by the named-degradation fallback.

**Revisit when** a production gated-dispatch consumer needs the counter keyed by something finer
than session+engine (e.g. per-unit), or when the marker family moves out of the repo tree.

---

### Concurrency policy has one nested ExecutionSpec block and one conservative product guard {#concurrency-policy-350}

**Date:** 2026-07-15 · **Plan:**
`docs/plans/2026-07-15-issue-350-concurrency-policy-plan.md` · **Issue:** #350

**Decision.** Concurrency configuration lives only in an optional `ExecutionSpec.concurrency` block.
Its resolved order is spec default, environment, all-read-only cohort lift, tier-weighted admission,
engine lane, then explicit run override. Dependency layers and verify panels share one ordered
chunking primitive, and the aggregate guard uses AC8's conservative layer-width times verifier-width
product even where current panel sequencing makes that an upper bound.

- **KTD1 - no duplicate top-level `max_concurrent`.** The nested policy is the serialized authority;
  absent policy blocks retain the compatibility behavior of existing optional ExecutionSpec fields.
- **KTD2 - the explicit run request is last.** Read-only lift applies before tier admission; a lane is
  the most-specific automatic input, but it cannot silently defeat the operator's explicit run
  override. A capability is resolved once with the repository overlay and calibration signals before
  admission; the governor and emitted runtime selector consume that same exact engine key. The
  authored capability remains provenance, not a second selector, because the runtime contract requires
  capability XOR engine. Fallback, halt, or non-exact resolution fails emission. Every effective width
  remains subject to the aggregate ceiling.
- **KTD3 - tier admission reuses fleet-core `cost_weights.to_spend`.** Saga does not create a second
  model/effort weight table.
- **KTD4 - read-only lifting requires explicit evidence.** Every unit in the cohort must carry the
  existing read-only mutation policy; absence or a mixed cohort uses the base width.
- **KTD5 - aggregate width follows AC8's product.** The guard multiplies worker-chunk width by the
  largest co-running verifier-chunk width (factor 1 without a panel) and fails above the fleet
  ceiling; it does not replace the published acceptance contract with an inferred schedule.
- **KTD6 - concurrency gets a sibling spawn-site inventory.** Sandbox and concurrency inventories
  cross-link, but each retains its own source rows, parser, and failure contract.
- **KTD7 - executable workflow source has one fail-closed naming boundary.** Unit identifiers use a
  closed ASCII grammar and cannot claim JavaScript keywords, harness bindings, the supported
  runtime-global namespace, generated panel/chunk symbols, or iterate-to-consensus loop locals.
  Runtime globals are reserved independently of observed source syntax; an independent
  ECMAScript/Node oracle checks bare, shorthand, call, and member references without treating
  property names as globals, and compares the reservation boundary with Node `globalThis`.
  Free-form comment text is rendered inert, while executable values remain JSON-encoded strings.
  Fan-out framing has one private helper that snapshots a governor-derived chunk before invoking its
  member renderer. Structural conformance requires exactly two inventoried helper call sites, direct
  governor assignments and loop consumption, a helper-call expression directly in each governed loop
  body, no mutation or alias escape of the governed collection before loop consumption, no mutation
  or alias escape of the direct loop chunk before helper entry, the unchanged direct loop chunk as
  the helper input, and no indirect helper loads. Raw parallel delimiters are rejected through direct
  or directly aliased list sinks, including JavaScript trivia and unresolved formatted callees, and
  at any static assignment site outside the helper so a local delimiter binding cannot hide the raw
  emitter. The guard folds constant string concatenation but intentionally does not reconstruct
  general Python alias dataflow or complete JavaScript grammar; centralizing the executable boundary
  removes the need for that test-only mini-analyzer. The independent global oracle owns separate Node
  and Workflow-host baselines, and every host-global identifier has a behavioral emission rejection
  test.
- **KTD8 - calibration is one immutable repository snapshot.** Capability emission reads the strict
  hash-chained ledger once under its shared lock, constructs one verified `LedgerSnapshot`, and
  derives Elo and provider-drift signals from exactly those records. Routing never composes signal
  families from different concurrent ledger revisions.

**Revisit when** `/optimize` explicitly adopts the shared governor, a runtime scheduler can expose
measured overlap instead of emit-time bounds, or a new executable fan-out site is added.

---

### Dispatch settlement extends the run-fact ledger; the DLQ is a derived view {#dispatch-settlement-351}

**Date:** 2026-07-15 · **Plan:**
`docs/plans/2026-07-15-issue-351-dispatch-settlement-plan.md` · **Issue:** #351

**Decision.** Dispatch manifests, pre-call spawn attempts, terminal settlements, and digest-bound
late-delivery observations are append-only `run_fact.v1` records with `kind=dispatch-settlement`;
they do not create another store beside the hash-chained run-fact ledger. Open positions, casualty
reports, and retry-eligible dead letters are derived from a verified snapshot on every read.

- **KTD1 - the facts are the manifest.** One aggregate manifest record plus per-attempt spawn and
  settle records closes the atomicity gap a sidecar manifest or queue file would introduce.
- **KTD2 - dispatch settlement does not overload `kind=reconciliation`.** That existing kind belongs
  to external-engine finding adjudication; the event vocabularies remain distinct.
- **KTD3 - stable identity is `(dispatch_id, unit_id, attempt)` and spawn means committed for
  submission.** At-least-once retries increment the attempt but preserve the unit's idempotency key.
  The coordinator appends immediately before the host call, so a crash or tool failure after append
  stays visible. A late delivery appends evidence after a non-delivered settle instead of rewriting
  history; the ledger never pretends exactly-once delivery.
- **KTD4 - team-execution delivery is a valid worker-exit `saga.manifest.v1`.** `artifact_pointer.py`
  is a post-work diff-transfer snapshot, not an acknowledgment, and receives no invented ACK role.
- **KTD5 - site adapters normalize persisted evidence; one classifier decides.** Agent prose cannot
  satisfy a delivery. A caller cannot establish trust with a Boolean, output list, reference, or
  digest: the classifier loads the receipt under an explicit evidence root, validates its site
  schema and unit/output binding, and computes the digest from the actual bytes. Team artifacts have
  only closed `reviewer-result` and `validator-state` kinds; their deliverables are derived from
  validated payloads and never copied from a caller-authored output list.
- **KTD6 - an omitted casualty threshold means zero percent.** Permissive partial progress is an
  explicit per-dispatch operator choice.
- **KTD7 - stale worktrees are projected read-only.** `reconcile --leaks` may report a registry/on-disk
  mismatch as an unsettled debit but does not append synthetic history or reap resources.
- **KTD8 - workflow settlement is driver-materialized and invocation-bound.** Generated leaves keep
  their no-filesystem boundary; emitted expected-unit metadata and validated host results let the
  root driver write facts. The driver persists one invocation ID before submission, reuses it only
  for crash resume, and mints a new one for a later execution of an unchanged spec.
- **KTD9 - a pre-submit spawn is storage-durable.** The writer synchronizes the appended ledger bytes
  and new directory entry before the runtime call can proceed; advisory locking alone is not the
  crash boundary the contract promises.
- **KTD10 - team-execution resolves Saga rather than copying it.** The independently packaged plugin
  preflights an explicit root, source checkout, installed registry, or cache sibling before any Agent
  call, then invokes the one canonical Saga engine through a coordinator-owned evidence adapter.

**Revisit when** a new fan-out site is introduced, trusted host APIs expose stronger liveness or
rate-limit receipts, or a consumer can prove stronger idempotency than the current at-least-once
contract.

---

### Fleet leases reserve before spawn and fence every delegated mutation {#fleet-ttl-lease-broker-356}

**Date:** 2026-07-15 · **Plan:**
`docs/plans/2026-07-15-issue-356-ttl-lease-broker-plan.md` · **Issue:** #356

**Decision.** One fleet-core registry, protected by one process lock, owns delegated-agent admission
and outcome-worktree ownership in separate named pools. Provisional and workflow-batch leases reserve
capacity before launch, trusted runtime identity binds the child after start, and every delegated
file or Bash mutation verifies the current monotonic fencing token. Expiry is derived from renewal
time plus TTL; Saga alone validates and reaps an expired outcome worktree.

- **KTD1 - #350 owns resolution; fleet-core owns normalized limits.** Fleet-core holds the shared
  default constants and admission record so Saga and team-execution cannot drift. Saga's #350
  resolver alone interprets spec, environment, tier, lane, and run inputs; the broker records the
  result, pins one exact snapshot per live session, rejects any mid-session upshift, and uses the
  minimum aggregate ceiling asserted by all live leases. A pre-spawn pin has the normal five-minute
  TTL, is visible through `inspect`, and is purged after abandonment so crashed preflight cannot
  exhaust the bounded pin registry. Worktrees retain their independent cap-four pool.
- **KTD2 - fleet-core owns the schema.** Saga and team-execution use thin adapters around one
  fleet-commons implementation and one lock/sequence authority. The authority root is runtime-neutral:
  explicit safe `INFIQUETRA_FLEET_STATE_DIR`, then safe absolute XDG state, then
  `~/.local/state/infiquetra/fleet-leases`; it never defaults through Claude, Codex, or plugin-data
  directories. Consumers compare a redacted canonical-root digest before admission.
- **KTD3 - reservation precedes launch.** `Agent|Task` calls get provisional leases in `PreToolUse`;
  `/work` reserves an emitted workflow wave atomically before `Workflow(...)`. `SubagentStart` binds
  trusted `agent_id` after launch but never creates uncounted capacity.
- **KTD4 - foreground release needs both sides of the lifecycle.** Because hooks run independently,
  another hook may block `SubagentStop`, and `SubagentStart` does not expose its parent tool-use ID.
  A foreground lease is removed only after its bound child records terminal intent and the exact
  provisional parent call records completion; resident workers release after explicit stop
  confirmation. Batch settlement and resident session teardown validate all signals and release under
  the same broker lock. Cross-ordered same-type claims may delay release but cannot free a live child.
- **KTD5 - fencing is looked up, not asserted.** Hooks use trusted `agent_id` to verify the broker's
  current resource token. Retrying a logical unit atomically supersedes the old token, so a stale
  process cannot write through file tools or Bash. A per-resource last-granted head survives lease
  removal, allowing later consumers to derive current, expired, closed, or superseded without a
  mutable status field. Closed heads beyond the bounded hot registry move to owner-only cold files
  keyed by resource digest; exact closed/superseded classification survives compaction for both agent
  and worktree pools.
- **KTD6 - a durable worktree is outcome-owned, not coordinator-process-owned.** Same-boot monotonic
  time derives expiry, but a short-lived coordinator PID ending is not abandonment proof for an active
  child. Each active tick transfers the exact persisted token to its current coordinator before sweep;
  a `dispatched` node vetoes destructive reap. Transfer and sweep share the authority lock, and Saga
  persists registry/lease recovery state before physical Git creation. Terminal or otherwise inactive
  resources still require dead-owner or explicit-terminal proof; failed reaps remain visible for retry.
- **KTD7 - hook enforcement is cooperative runtime safety.** Missing, corrupt, or version-skewed
  authority fails closed on armed delegated paths. A local operator able to disable or replace hooks
  remains outside the security boundary.
- **KTD8 - pre-spawn pins and closed heads have separate hot-path bounds.** A session admission pin
  carries same-boot monotonic creation time and a 300-second orphan TTL; live leases keep their exact
  pin, while abandoned pins expire, remain inspectable as derived state, and are swept before the
  64-session cap is applied. The registry retains only 128 closed resource heads across both pools;
  older exact heads move to owner-only, no-follow archive sidecars so closed and superseded remain
  distinguishable without unbounded read-modify-write cost on the hot registry.
- **KTD9 - grant and settlement are indivisible authority transitions.** Nested parent validation and
  child grant occur under one broker lock, eliminating verify-then-acquire races. Registered engine
  adapters enter a persisted, exact-token settlement window immediately after runner return; the
  broker lock then spans disarm, integrity accounting, evidence shaping, and durable fact writes
  before exact release. Advisory panels additionally hold one stable aggregate resource fence across
  every member and enter exact-token settlement for both final reconciliation facts; a newer retry
  either supersedes the stale panel before any append or waits for its settled facts. No accepted
  output is written after its lease can be superseded. Direct renew and release require the exact
  fencing token; owner teardown accepts only broker-recorded terminal evidence.

**Revisit when** Claude exposes an atomic pre-spawn child identity, a durable host lease API replaces
file-backed coordination, or team-execution gains a generic teardown contract under issue #358.

---

### Orphan evidence is rejected or quarantined under the fleet resource fence {#orphan-evidence-fencing-355}

**Date:** 2026-07-15 · **Plan:**
`docs/plans/2026-07-15-issue-355-orphan-runner-containment-plan.md` · **Issue:** #355

**Decision.** Agy, Saga, and Team Execution evidence writers use #356's `LeaseBroker` as the sole
mutation authority. Broker-owned prepare/commit/abort makes the atomic closed-registry replacement
the only acceptance linearization point. A callback failure best-effort records `ambiguous`; an
unwritable registry, signal, or process death leaves the last durable `prepared` or `committing`
state, which retains authority and blocks ordinary retry. Output without the matching closed broker
receipt is quarantine-only evidence and cannot satisfy a gate. `run-lease.json` remains forensic.

- **KTD1 - the broker owns prepare, close, and retained ambiguity.** Protected writers run only from
  the broker's committing phase. Sweep never reclaims prepared, committing, or ambiguous authority,
  and #355 does not claim automatic or restart-safe producer replay. The low-level recovery
  coordinator remains a test/experimental seam; #358 owns lifecycle recovery and teardown. A
  lost-response retry returns the canonical close without replaying the write. This is cooperative
  correctness for an owner-local plugin: same-effective-user processes and the operator are trusted,
  while stale children, crashes, accidental corruption, and external-engine output are not.
- **KTD2 - closed-head CAS is the only successor path.** Registered dispatch, documented Team
  Execution claim, and adjudication share one execution-stable resource. Each successor names the
  exact predecessor token and canonical receipt hash; a stale attempt cannot reacquire after a retry.
  Exact lookup includes cold archive sidecars even when a head has left the bounded inspection
  projection, so archive compaction cannot reopen ordinary acquisition or erase late-write proof.
- **KTD3 - agy admission is resolver-owned and lease-bound.** Direct auto-apply accepts only a bounded
  resource key read from an owner-private `0600` regular file. The raw key is rejected on argv and
  immediately reduced to a repository-scoped digest; only that digest reaches durable resource,
  bundle, receipt, quarantine, or audit records. An in-process resolver derives policy, capacity,
  process, canonical Git identity, and a lease-independent output template, then binds the acquired
  lease to the final output record.
- **KTD4 - closed schemas make disposition evidence executable.** Broker-native UUID epochs,
  provider process identities, tokens, resources, receipts, expected outputs, quarantine manifests,
  events, candidates, reservations, and recovery intents use strict canonical schemas and digests.
- **KTD5 - superseded rejects; expired or closed output quarantines.** A newer head always wins.
  Rejected output never becomes live, and corrupt or contradictory authority yields an explicit
  evidence-integrity error rather than a guessed disposition.
- **KTD6 - quarantine is immutable, reserved, and aggregate-bounded.** Items are below 128 MiB;
  committed plus staging storage is capped at 512 MiB and 256 entries under one owner-only lock.
  Every capacity check and event publication first recovers staging under that lock. Dead-owner
  staging is schema-, identity-, path-, byte-, and digest-verified before finalization or safely
  discarded; referenced evidence is revalidated before its event is written. Committed evidence
  receives at least 30 days retention and is never evicted by the acceptance path.
- **KTD7 - proof and projection remain verifiable but non-destructive.** Mode-bound command receipts
  prove the genuine agy version gate and fleet sweep, bind an immutable merge-base plus every
  receipt-excluded candidate path, mode, and byte digest, require shipped proof/transcript roots, and
  rerun the fixed checker. Orphan candidates are derived only from canonical hot or archived broker
  heads, close seals, leases, and orphan events; event callers cannot assert disposition or
  terminality. #356 owns worktree sweep, #357 owns advanced liveness, and #358 owns generic teardown.
- **KTD8 - incompatible settlement is lease protocol 2.** Fleet-core, Saga, Team Execution, and Agy
  live apply require version 2 before acquiring or dispatching. Agy validation, no-write, and
  patch-only paths lazy-load the new containment modules so independent plugin installation order
  does not break modes that do not use settlement. Ordinary manifest CLI and completeness output is
  noncanonical-only; empty-artifact projection requires a matching bound output record and exact
  trusted template, while optional/no-output contracts emit no candidate.

**Explicit boundary.** This decision does not retrofit agy with an OS sandbox, environment secret
broker, or hostile same-user filesystem defense. Those are separate runner-hardening capabilities;
they are not required to fence stale evidence writes in an owner-local Claude Code plugin.

**Revisit when** a transactional durable store can atomically cover broker and artifact bytes, a
distributed fence replaces host-local coordination, or quarantine encryption becomes mandatory.

---

### Liveness is a shared score plus bounded confirmation, never sole teardown authority {#fleet-shared-liveness-357}

**Date:** 2026-07-15 · **Plan:**
`docs/plans/2026-07-15-issue-357-fleet-shared-liveness-engine-plan.md` · **Issue:** #357

**Decision.** Fleet-core owns one pure liveness engine; Saga keeps coordinator-specific ledger and
terminal adapters, and team-execution polls through Saga's canonical run-fact path. The engine fuses
bounded phi-accrual suspicion, trusted baseline-relative path progress, and append-only idle-notice
acknowledgment. Statistical suspicion requests a bounded reachability probe; it does not itself kill,
release, retry, or delete.

- **KTD1 - five intervals select adaptive scoring; sparse history keeps fixed behavior.** Outcome
  absolute timeout and no-budget opt-out remain unchanged.
- **KTD2 - phi 8 is a configurable suspicion threshold, not a magic terminal.** An armed trusted
  transport may use exclusively attributed artifact progress or a host-correlated acknowledgment to
  refute it and three receipt-proven, unacknowledged re-pings to confirm it. An Outcome backend
  without that transport keeps its exact fixed-gap terminal and treats phi as advisory.
- **KTD3 - a changed scoped digest proves activity, not resident progress.** Whole-tree change,
  pointer epoch, mtime, and chat activity do not count. Even disjoint declared paths remain
  `scoped-activity-unattributed` unless a trusted exclusive-provenance receipt binds the exact
  subject, lease/fence, paths, digest interval, custody, and covered generations.
- **KTD4 - an idle acknowledgment proves consumption, never output delivery.** The #351 complete
  worker manifest remains the delivery ACK.
- **KTD5 - notice/re-ping state is projected from append-only facts.** No mutable queue, status file,
  sleep loop, or second heartbeat registry is introduced.
- **KTD6 - detection and reclamation remain separate.** #357 scores and requests; #358 later owns
  non-skippable stop/release/teardown, while #355/#356 own write and lease safety.

**Revisit when** the host exposes a durable native worker heartbeat/notification receipt API, the
fleet spans multiple boots/hosts, or observed cadence data justifies tuning the committed policy
defaults through `/optimize`.

---

### Team execution closes admission before idempotent B8 teardown {#team-execution-teardown-358}

**Date:** 2026-07-15 · **Plan:**
`docs/plans/2026-07-15-issue-358-non-skippable-teardown-reclamation-plan.md` · **Issue:** #358

**Decision.** Team-execution completion becomes a broker-fenced terminal transition. Step B8 first
closes new admission for the exact run, then projects append-only teardown facts, executes only
resource-specific trusted actions, and records completion only after a zero-open reconciliation.
The #356 broker is live ownership, #351 run facts are history, and #357 confirmed liveness is input;
there is no second reclamation ledger or reaper.

- **KTD1 - closing admission prevents spawn-after-receipt.** Acquire, reserve, claim, and retry are
  refused for a closed run while existing resources remain visible for reconciliation.
- **KTD2 - B7 prepares; B8 completes.** A business result or report draft cannot use `complete`
  until the B8 receipt proves zero open resources against the same closed broker generation.
- **KTD3 - crash cleanup is eventual.** Observed terminals run B8 synchronously; `SIGKILL` and host
  death wait for bounded SessionStart/explicit recovery plus TTL and dead-owner proof.
- **KTD4 - actions are resource-specific.** Residents use trusted runtime stop receipts, owned
  subprocesses require PID/start/boot identity, and outcome worktrees use only #356 sweep.
- **KTD5 - CI plants its own leak.** Developer worktrees are attended evidence, never a destructive
  test fixture or an implicit cleanup target.

**Revisit when** the host provides a durable terminal finalizer, the broker becomes cross-host, or a
native runtime can atomically stop and attest a resident without the current request/confirm pair.

---

### Fleet doctor correlates raw sources independently and never repairs {#fleet-doctor-independent-audit-353}

**Date:** 2026-07-15 · **Plan:**
`docs/plans/2026-07-15-issue-353-fleet-doctor-plan.md` · **Issue:** #353

**Decision.** Fleet doctor is a Saga-local, point-in-time tripwire with a stdlib-only runtime
observation layer. It strictly reads documented raw contracts and independently joins Git worktrees,
outcome registries, broker ownership, run facts, teardown facts, manifests, and durable receipts. It
never calls the tolerant projections or mutation APIs it audits.

- **KTD1 - corruption cannot look absent.** Missing, malformed, unsafe, changed, capped, and unknown
  evidence remain distinct; any incomplete proof exits 2 rather than clean.
- **KTD2 - launch needs two signals.** A #351 spawn fact is pre-submission intent; unledgered requires
  an independent broker, Outcome, audit-store, or bundle observation.
- **KTD3 - managed worktrees only.** Stale detection is confined to canonical
  `.saga-worktrees/<outcome>/<subplot>` resources; unrelated developer worktrees are out of scope.
- **KTD4 - strict doctor complements tolerant delegation audit.** `/delegation-audit` remains its
  focused advisory query; doctor treats corrupt/cross-source receipt evidence as a tripwire error.
- **KTD5 - no repair authority.** Findings point to owners but cannot settle, retry, release, recover,
  quarantine, kill, or reap.

**Revisit when** contracts move to a single independently queryable database, the fleet spans hosts,
or a separate scheduler/alert outcome explicitly consumes the report schema.

---

### Cross-runtime Outcome portability ends at canonical observation {#claude-cross-runtime-outcome-contract-579}

**Date:** 2026-07-15

**Plan:** `docs/plans/2026-07-15-claude-cross-runtime-outcome-contract-plan.md`

**Parent:** #579; executable child: `infiquetra/infiquetra-claude-plugins#604`

**Decision.** The Claude-side cross-runtime contract separates same-clone coordination from
cross-clone reconstruction. A conforming runtime discovers an Outcome from a committed Git object,
canonical GitHub repository identity, Outcome ID, and GitHub completion evidence. Runtimes in one
clone may mutate only after validating a protected local handoff and consuming the #356 fleet-broker
fence plus #351 dispatch settlement identity. A different clone can reconstruct the same canonical
completion/candidate-frontier projection, but its transient dispatch state is unknown and it has no
mutation authority.

- **A public handoff is a reference, not a bearer token.** Acceptance reloads protected local
  evidence and checks current repository/spec/fence/settlement/freshness/use state. Copied or unsigned
  JSON cannot authorize dispatch.
- **Committed blobs anchor compatibility.** Repository identity, commit/blob digest, spec schema and
  revision, capability range, and working-tree equality are checked before cache, broker, fact,
  dispatch, board, GitHub, or spec mutation.
- **Portable status omits transient authority.** Git plus GitHub can prove completion and dependency
  candidates across clones, not the absence of an in-flight dispatch. Cross-clone output is therefore
  read-only and says transient state is unknown.
- **Legacy bundle import is retired as authority transfer.** Replaying a bundled spec, completion
  events, or dispatch ledger into another repository creates a competing truth path and must fail
  with an actionable discovery/attach migration receipt.
- **The producer and consumer release separately.** Claude publishes the runtime-neutral schemas and
  golden fixtures; Codex consumes them in its own linked issue and PR.

**Rejected.** Copying git-common-dir state between hosts; trusting a serialized handoff without its
protected local record; adding a second lease/settlement/completion ledger; treating the newest ref or
matching filesystem path as repository identity; allowing cross-clone advance because the canonical
candidate frontier looks ready; and hiding the Codex port inside the Claude release.

**Revisit when.** A networked, atomic, canonical active-dispatch authority is deliberately added to
the Outcome model. At that point cross-host mutation can be designed against that authority; GitHub
completion evidence alone is insufficient to prove no live dispatch exists elsewhere.

---

### Codex ports shared safety before protocol parity and retains native launch proof {#codex-lease-settlement-parity-579}

**Date:** 2026-07-15

**Plans:** `docs/plans/2026-07-15-codex-shared-runtime-substrate-plan.md`,
`docs/plans/2026-07-15-codex-cross-runtime-outcome-parity-plan.md`

**Parent:** #579; executable children: `infiquetra/infiquetra-codex-plugins#33` and
`infiquetra/infiquetra-codex-plugins#34`

**Decision.** Codex cross-runtime support ships as two independently reviewed proof ports. The first
ports #351/#355/#356's runtime-neutral broker, resource guard, fencing, and dispatch settlement into
Fleet Core plus the Saga adapter. The second consumes that substrate and ports the Outcome
compatibility/discovery/handoff protocol. Both follow the Codex runbook's fresh manifest,
classification, unit/cutover, isolated-install, fresh-session, and rollback gates.

- **The fleet root is shared; protected runtime receipts are not.** Both runtimes resolve one safe
  neutral fleet-state root and compare its redacted canonical digest. Codex protected launch receipts
  remain in their current protected boundary and correlate by dispatch identity.
- **Settlement cannot manufacture a Codex launch.** Codex retains `outcome.dispatch.v2`; only a
  protected `ack_kind=launched` acknowledgement proves dispatch. `handed-off` remains non-launched,
  and legacy facts remain unverified unless the existing migration contract proves them.
- **A handoff authorizes one operation, not a frontier.** Protected same-clone acceptance may enter
  one `advance-one` path, which then creates/observes the normal Codex dispatch intent and launch ack.
- **The dirty primary Codex worktree is not an implementation surface.** Each port starts from a
  fresh `origin/main` worktree and binds its exact target-repo plan/review bytes to the port manifest.

**Rejected.** One oversized Codex parity issue that silently invents its missing substrate; a
runtime-local broker under Claude/Codex/plugin-data homes; treating shared settlement or a handoff as
Codex launch proof; copying protected receipts across clones; and bypassing the port classification
because neutral Claude fixtures exist.

**Revisit when.** Codex replaces `outcome.dispatch.v2` through a separately reviewed native migration,
or the two proof ports become one already-shipped stable substrate whose compatibility adapter can be
changed without cross-package release coupling.

---

### Cross-runtime acceptance measures overlap and closes without repair {#cross-runtime-acceptance-579}

**Date:** 2026-07-15 · **Plan:**
`docs/plans/2026-07-15-cross-runtime-outcome-acceptance-plan.md`

**Issue:** `infiquetra/infiquetra-claude-plugins#605`

**Decision.** Acceptance runs the exact merged and installed Claude/Codex releases in contained Git
fixtures. A same-clone scenario shares one common dir and neutral broker root; a separate clone gets
only committed spec plus deterministic GitHub evidence. Concurrent advance proof requires two OS
processes, a deterministic barrier with monotonic overlap evidence, and a write-once fake backend.
The harness reports failure but never fixes production behavior.

- **Portable parity excludes transient state.** Different clones compare canonical completion and
  candidate frontier; leases, handoffs, launches, and in-flight dispatch remain unknown.
- **Shared settlement and runtime acknowledgement are separate assertions.** Exactly one settlement
  and effect must exist, and Codex must also carry its native protected launched ack when it launches.
- **Cleanup is independently observed.** Idempotent teardown runs twice, then #353 reads raw sources
  and must report zero open positions before QA or outcome close.
- **Evidence is revision-bound and privacy-safe.** The closed bundle records SHAs, versions, digests,
  commands, timings, verdicts, counts, and artifact hashes, never raw credentials, caches,
  transcripts, prompts, child output, or GitHub bodies.

**Rejected.** Sequential calls described as concurrency; copied handoffs in the second clone;
working-tree code described as a released input; equal transient state across clones; a test harness
that patches a failing runtime; and closing #579 with a waiver.

**Revisit when.** A networked active-dispatch authority makes cross-host mutation an accepted product
contract or the runtime packages provide a signed, standardized installed-attestation API that can
replace the current isolated readback evidence.
