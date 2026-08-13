# Doc review — `orchestrate` implementation plan

**Verdict: BLOCKED.** Four P0 and eleven P1 findings. The plan is well-grounded — nearly every file,
module, and line it cites exists and says what it claims — but four of its twelve requirements name
a mechanism that cannot fire, and all four fail silently. None of the findings is a broken concept;
every one is a missing decision or a mis-read mechanism. This is a revision pass, not a redesign.

| field | value |
|---|---|
| target | `docs/plans/2026-08-12-orchestrate-plugin-plan.md` |
| reviewed revision | working tree at commit `5f1329a7` (PR #711) plus this review's two safe fixes |
| origin | `docs/brainstorms/2026-08-12-orchestrate-requirements.md` (PR #710, squash `d8a9e6aa`) and the Codex companion |
| classification | plan — maps to no saga rubric phase (`idea` / `spec` / `issue` only), so no rubric engine ran |
| panel | Claude (this session, in-place fixes) · codex `gpt-5.6-sol` max · grok-4.6 xhigh |
| companion repo revision | `infiquetra-codex-plugins` `origin/main` at `0383f82` |
| blocked | yes — unresolved P0/P1 |
| applied fixes | 2 (below) |
| saga | `task-orchestrate-plugin`, phase plan/complete |

## Applied fixes

Two safe fixes were applied in place. Both are corrections of internal references settled by
repository evidence.

| # | fix | evidence |
|---|---|---|
| F1 | Problem Frame cited `outcome_spec.py:678` as stating the outcome layer has no session concept. That line says it has no notion of `execution_spec`'s **pilot barrier edge** — narrower. Rewritten to cite the real evidence. | `grep -c herdr` → 0 in both `outcome_spec.py` and `references/outcome-spec.md` |
| F2 | KTD2 described the Claude command loader as "~10-line". It is 21 lines and carries a scope paragraph the plan omitted — which matters, because `/orchestrate`'s loader should carry one too. | `wc -l plugins/saga/commands/plan.md` |

## Findings

Ranked by cost × silence — damage done multiplied by how long it goes unnoticed — not by count.
Attribution shows which panel members found each finding independently.

| id | pri | where | finding | found by |
|---|---|---|---|---|
| D1 | **P0** | U3 · Scope Boundaries | Events during any socket gap or restart are lost with no recovery path | codex |
| D2 | **P0** | R2 · KTD3 · U3 · Scope Boundaries | No process is specified to hold the subscription open | all three |
| D3 | **P0** | KTD7 · U1 · U6 · U9 | U1 ports the table the Codex repo labels legacy; the authoritative one is `execution_classes` | grok, codex |
| D4 | **P0** | R9 · U6 | The spend ceiling can never engage | all three |
| D5 | P1 | U2–U8 | No unit owns composition of the modules into a working orchestrator | codex |
| D6 | P1 | U2 · U4 · U9 | The register cannot address a child — no `pane_id`, `tab_id`, `workspace_id`, or host | grok, codex |
| D7 | P1 | U3 | The recorded subscribe `type` strings are the payload spellings, not the request spellings | grok, codex |
| D8 | P1 | U3 · U4 | Pre-existing scrollback can satisfy a content match, certifying a child before it reacts | codex |
| D9 | P1 | R5 · U5 | Judgment work has no depth gate, though origin R14 was explicitly retained for it | codex |
| D10 | P1 | U4 | No write-ahead launch ordering — a crash between launch and register write orphans a child | codex |
| D11 | P1 | R7 · U4 · U5 | Mutation scope is recorded as prose with no enforcement and no landing model | grok, codex |
| D12 | P1 | U9 · C1 · C14–C15 | The round-trip is not an executable procedure, and same-host vs cross-machine is undecided | all three |
| D13 | P1 | U2 · U4 · U7 | No temporal column, yet hang detection is an acceptance test in two units | Claude |
| D14 | P1 | R8 · U6 | Capacity-based vendor routing has no declared input anywhere | Claude |
| D15 | P1 | U1 | Changes a Python API with 12 dependent files; the risk section covers only the JSON | Claude, grok |
| D16 | P2 | U2 | `tools/create-plugin.sh` emits the wrong plugin shape and breaks marketplace sync | grok, codex |
| D17 | P2 | U5 | "Settled artifact" is never defined | Claude, codex |
| D18 | P2 | U2 | Register is ambiguous between per-run and global; no row-retirement rule | Claude |
| D19 | P2 | U4 → U5 | Reap ships one unit before the gate that stops it discarding verified work | Claude |
| D20 | P2 | U1 · U4–U9 | Several acceptance criteria have no fixed bound, command, or observable result | codex |
| D21 | P2 | U2 | Unknown-field preservation is tested only at top level; nested child-row keys can still drop | codex |
| D22 | P2 | R10 · U6 | Concurrency limits are aggregate-only; no per-vendor representation exists | codex |
| D23 | P3 | Problem Frame | The evidence ledger behind the severity ranking lives only in a session scratchpad | Claude |
| D24 | P3 | Phase boundaries | Phase 1 is unlabeled and "dogfooded on real work" is not a gate | grok |

---

## The four P0s

### D1 — events during any socket gap are lost, and nothing recovers them

**What breaks.** U3 requires that "a socket close mid-stream triggers reconnect without losing the
subscription set." Protocol 19 has no subscription cursor, no `since` parameter, no replay request,
and no event id. Every `seq` in the schema is either a write-side optimistic-concurrency token
(`PaneReportAgentParams.seq` and five siblings) or a read-side state counter
(`AgentInfo.state_change_seq`). **Re-subscribing restores future delivery only.**

Scope Boundaries then rules out the only other recovery mechanism: *"A reconcile loop. `/outcome`
already implements level-triggered reconciliation."*

**Failure scenario.** The orchestrator restarts, compacts, or drops the socket for any reason. A
child finishes and exits during the gap. Its `pane.output_matched` and `pane.exited` are delivered
to nobody. The register says `running` forever, the work-in-progress slot stays occupied, and no
future event ever re-triggers the predicate. U3's reconnect test passes throughout, because it
asserts the subscription set survives — which it does. The data loss is untested.

**Why it ranks first.** It is guaranteed rather than occasional, totally silent, and it defeats the
plugin's core promise in precisely the situation autonomy exists for: the operator is away.

**Fix.** Add a bounded catch-up pass at startup and after every reconnect: read the live herdr
snapshot for every registered handle, compare expected against observed state, and re-evaluate
run-bound artifacts and predicates. Test an exit and a completion artifact created between
disconnect and re-subscribe. This is edge-triggered boundary recovery, not the rejected polling
daemon and not a second general-purpose reconcile engine — it runs once per reconnect, not on a
schedule.

### D2 — no process is specified to hold the subscription

**What breaks.** R2 promises the orchestrator "never requires an operator turn to make progress."
KTD3 says "any process that can open a unix socket can subscribe." U3 builds a **client library**.
Scope Boundaries excludes "a background daemon or controller process."

A socket subscription requires a live process. The plan rules out the only kind that survives
between turns and names no replacement. This is not the settled autonomy question — herdr genuinely
does push, verified live. It is narrower: *what stays subscribed, and what re-enters the
orchestrator when an event arrives?*

**Failure scenario.** U3, U4, and U5 are all built correctly and every test passes. `/orchestrate`
plans, launches, prints "subscribed," and the turn ends. A child emits its match. herdr pushes to
nobody. The operator returns to a register that still says `running` and a plugin that reports
success because the unit tests were green.

**Fix.** Name the holder. Three candidates, and the plan must pick one: a blocking `events.wait`
loop inside an open orchestrator turn (what this session does in practice — honest, but it needs an
explicit statement of what happens at turn end and how a run resumes); a small subscriber process
the orchestrator spawns, which is a controller process and therefore requires amending Scope
Boundaries; or injection back into the orchestrator's own pane via `agent.prompt` / `pane.send_text`,
which exist on the same socket. Give U3 or U4 an acceptance scenario runnable with the operator
idle: child emits the match, orchestrator evaluates the predicate, no new operator message was typed.

### D3 — U1 ports the legacy table, and it covers one vendor

**What breaks.** KTD7's premise is that Codex's `lineage_models` is the right cross-vendor shape and
Claude should converge onto it. The Codex `models.json` `_comment` says the opposite, verbatim:

> *"Canonical Fleet Core policy. **lineage_models/lineage_efforts preserve the pre-cutover
> Claude-derived vocabulary for existing consumers only.** scalar_efforts, execution_classes, and
> root_orchestration_profiles are the **authoritative Codex policy**."*

Three consequences follow:

1. The "known drift" U1 tells the implementer to resolve first — `lineage_models` naming `gpt-5.5`
   while `root_orchestration_profiles` names `gpt-5.6-sol` — **is not drift.** It is a frozen legacy
   table beside a live one, as designed. The plan asks for a contradiction to be resolved that does
   not exist, which means inventing an answer.
2. `lineage_models` contains **only Codex mappings** (`codex_model` / `codex_effort`). The table the
   plan calls the right multi-vendor shape resolves exactly one vendor. There is no Grok, Muse,
   Qwen, or agy resolution in it.
3. U9 cannot converge the two files by adding keys. Codex's `tier_palette.py` requires the complete
   five-section version-2 shape and rejects unexpected sections, so Claude's `models` / `efforts`
   keys would make Codex fail at import. U1 also omits `schema_version` and `scalar_efforts` from
   its port list.

**Failure scenario.** One implementer "fixes" the lineage rows up to Sol and Terra, silently
changing legacy consumers while bypassing the authoritative execution classes. Another keeps Codex
policy intact and adds Claude's keys, breaking Codex at import. Neither can route a Qwen child.

**Fix.** Correcting this costs no scope and *buys* two requirements. The authoritative
`execution_classes` shape already models what the plan needs and `lineage_models` does not:

```
execution_classes."review-max" = {
  order: 0,
  workspace_boundary: "read-only",   ← R7's per-child mutation scope
  external_boundary:  "none",
  preferred:  {model: "gpt-5.6-sol", effort: "max"},
  fallbacks: [ {gpt-5.6-terra, max}, {gpt-5.5, "strongest-supported"} ]
}                                     ← D14's capacity routing
```

Put a routing-contract decision ahead of U1: define the vendor-neutral work-shape input, the
concrete model and effort output for each of the six CLIs, the availability fallback, and the
argument adapter per vendor (the `agent` wrapper passes tool arguments through rather than
normalizing them, so each CLI needs its own flag mapping). Keep Claude's `models` / `efforts` as
the Claude vocabulary and add a **sibling** resolver — `resolve_for_runtime(tier, runtime)` — rather
than changing `resolve()`'s meaning. Keep `execution_classes` authoritative on Codex. Replace
byte-equal `models.json` convergence with an explicit portable subset plus runtime-owned policy.

### D4 — the spend ceiling can never engage

**What breaks.** U6 enforces the ceiling via the envelope's `cost_ceiling_tokens`. That field is
real. `authorize_spend` (`intent_envelope.py:798-803`) states its own honesty stance: *"`None`
actuals mean no telemetry has been recorded yet … nothing is measured against the ceiling, so the
cost gate does not engage."* And: *"Actuals are leaf-produced and self-attested."*

orchestrate's children are external CLI sessions on codex, grok, qwen, muse, and agy. Nothing makes
them attest usage, no register column holds it, no unit produces it. `actual_tokens` is permanently
`None` and the gate fails open.

**Failure scenario.** U6's test stubs a huge `actual_tokens` and sees a halt. Production always
passes `None`. R9 presents as shipped, an autonomous multi-vendor fan-out at high effort runs
unbounded, and the operator discovers it via a vendor bill.

**Fix.** Specify the counter: what is added, when, where it is stored (a register column), and the
fail-closed rule when a vendor exposes no usage. The design already owns the right instrument —
`pane.output_matched` with a per-vendor regex can scrape each CLI's own token counter, the same
mechanism KTD4 chose for completion. Alternatively restate R9 honestly as an operator-declared
ceiling checked against operator-supplied actuals, and say plainly that the run is not
automatically bounded. Do not leave `cost_ceiling_tokens` cited as if it enforced R9 by itself.

---

## The eleven P1s

**D5 — nothing composes the parts into a product.** U2 creates the skill, U3–U7 add isolated
modules, U8 adds a loader and the deprecation edit. No unit owns the control flow that persists an
approved plan, launches with write-ahead state, subscribes, dispatches events, calls completion,
advances queued children, supervises the mirror, and resumes after failure. Seven green module
suites can land with no working orchestrator. U7's "an operator message is answerable while the
mirror is busy" cannot be established by a unit test at all if the skill blocks synchronously on
the mirror. *Fix:* assign composition to a named unit, add a fake-herdr integration test over the
full approved-plan-to-reap path, and make the answerable-while-busy property a live Phase 1 proof.

**D6 — the register cannot address a child.** U2's columns are id, agent, vendor, model/effort,
task, scope, artifact path, predicate, run id, expected state, observed state. There is no
`pane_id`, `tab_id`, `workspace_id`, host, herdr session, working directory, or destination. U3's
per-pane subscriptions require `pane_id`; U4 needs `tab_id` to reap a specific tab; U9 needs both
plus host to resume another runtime's running child. The launcher already returns all three
(`agent-herdr` emits `workspace_id`, `tab_id`, `pane_id`) and the plan discards them. U2's test "a
row round-trips every column" would freeze the incomplete list. *Fix:* add them as required
columns, persist on launch before any subscribe, round-trip them in the U2 test.

**D7 — the recorded wire format is wrong.** U3's "Verified contract details" lists global
subscriptions as `tab_closed` and `pane_exited`. The schema carries both spellings and they are not
interchangeable: `tab.closed` / `pane.exited` (dotted) are **subscribe request** types;
`tab_closed` / `pane_exited` (underscored) are **broadcast envelope** names. `pane.output_matched`
is a `SubscriptionEventKind`, not one of the 26 `EventKind` values, and its subscribe object
requires `type`, `pane_id`, `source`, and `match` — not `type` and `pane_id` alone. The working
probe run during requirements discovery used the dotted form; the plan transcribed the wrong one
into the section that exists to prevent exactly this. *Fix:* record both namespaces in
`herdr-event-api.md` copied from `herdr api schema --json`, test serialisation against a committed
schema excerpt, and treat an unrecognised subscribe `type` as a hard error rather than an ignored
unknown kind.

**D8 — stale scrollback can certify a child.** `pane.output_matched` searches existing pane content.
A newly dispatched child can match text already in scrollback and be classified ready or complete
before it has reacted. The plan defines no per-agent content pattern, no run-specific sentinel, and
no pre-dispatch output baseline. This is the same defect class as a stale artifact satisfying a
predicate, one layer down at the event boundary. *Fix:* inject a unique run-and-child sentinel into
every readiness and completion interaction, capture the pre-dispatch output revision, and require a
later revision. Add a test that events for unregistered pane ids cannot mutate any row.

**D9 — judgment work has no depth gate.** The requirements' own review disposition retained R14
explicitly: *"'Cut blanket depth verification (R14).' **Kept**, narrowed rather than cut: depth
verification applies to judgment work whose output cannot be checked mechanically, not to every
child."* U5 permits only mechanical predicates — file test, required section, schema parse, test
exit code — while U6 explicitly routes judgment-shaped work. A retained requirement was dropped in
the plan without a deferral note. *Fix:* add a judgment-work completion branch requiring mechanical
coverage plus a blind independent depth sample by a separate verifier session, recording verifier
identity, sampled claims, and disposition. Mechanical children stay exempt.

**D10 — no write-ahead launch ordering.** Launching a child is an external side effect. If the
orchestrator dies between the launch returning and the register write, the row is absent or still
`planned`: on resume a duplicate child launches and the original pane's events cannot be attributed
to anything. *Fix:* specify `planned → launching → launched → ready` with a run-bound unique task
label written **before** the launch, and exact herdr identifiers recorded immediately after the
control-only launch returns. On recovery, discover by that run label and reconcile to the pending row.

**D11 — mutation scope is prose, not enforcement, and has no landing model.** R7 records a
per-child mutation scope; no unit translates it into sandbox or permission flags, provisions a
worktree for a mutating child, or audits changed paths against the declared scope. Separately, U5
refuses to reap "while the destination branch is unchanged" but no unit creates a worktree, records
a destination branch, or merges. `outcome_worktrees.py` is not a drop-in: it manages autonomous
sub-outcomes and deliberately leaves plain leaves in the ambient worktree. Cutting
one-worktree-per-**read-only**-child did not define the model for mutating ones. *Fix:* pick the
landing model explicitly in U4/U5 — either U4 provisions a worktree and U5 checks the destination
ref, or children write in-tree and U5's check is artifact-present-at-declared-path. State whether
origin R20 is adopted or deferred. Add a pre-dispatch baseline and a changed-path comparison before
completion.

**D12 — the cross-runtime round-trip is not executable.** U9 mixes schema-compatibility assertions
(a pytest file can do those with fixtures) with "the live round-trip launches a child under one
runtime, hands off, and reaps it under the other" (a pytest file in the Claude repo cannot drive a
Codex runtime). It also never defines "hand off": whether the first runtime detaches its
subscription, whether both may subscribe, whether both must share one herdr session — pane ids are
session-local — or which command the second runtime runs to resume. Cross-machine remains
unresolved: companion C1 says another machine, but a repository file in one checkout does not reach
another clone and a local herdr socket cannot observe a remote pane. *Fix:* first decide whether
this release promises same-host runtime handoff or cross-machine handoff. Then write the procedure
as a named checklist with commands, run it in both directions, and split U9 into port, fixture
conformance, release surfaces, and the two live directional proofs.

**D13 — no temporal column, but hang detection is an acceptance test.** U7 requires "a hung mirror
raises divergence like any other child." A hung mirror's expected state is working and its observed
state is working — that is agreement, not divergence. Detecting a hang requires elapsed time against
a bound, and no column holds a timestamp or deadline. U4's stall detection has the same problem.
*Fix:* add `dispatched_at` and a per-row `deadline` or `max_quiet_seconds`, and restate both tests
in terms of them.

**D14 — capacity routing has no input.** R8 permits routing for available capacity. Scope
Boundaries says "the operator supplies quota state for now" — but no unit accepts it: no register
column, no config file, no envelope field. There are zero `quota` references anywhere in
`fleet-core`. *Fix:* either give U6 a declared input, or adopt `execution_classes.fallbacks` from
D3's corrected foundation, which already models preferred-then-fallback, or move R8 to Deferred.

**D15 — U1 changes a Python API with 12 dependent files.** U1 adds resolution mapping "a tier name
plus runtime" to `tier_resolver.py`. Today `resolve(role_kind, work_shape, envelope_ceiling,
operator_override, *, policy)` has no runtime parameter. Twelve files reference `tier_resolver`,
including `team_emitter.py`, which explicitly wraps `resolve()`, and `tier_defaults.py:71`, which
calls it positionally. The risk section mitigates "additive keys only" — that protects
`models.json`, not the function signature. *Fix:* state that U1 adds a sibling resolver rather than
extending `resolve()`, and test that existing positional call sites are unaffected.

---

## P2 and P3

| id | finding and fix |
|---|---|
| D16 | `tools/create-plugin.sh` creates `src/main.py`, `tests/test_main.py`, `docs/`, and a manifest keyed `"id"` with `"main": "src/main.py"` — the CLI-plugin layout, not the skills layout. `scripts/sync_marketplace.py:51` indexes `plugin_json["name"]`, so sync raises on the scaffold's output. *Fix:* copy the shape from a current skills plugin (`house-style`, `saga`) instead. |
| D17 | "Settled artifact" is never defined — size stable across reads, a sentinel line, a rename-into-place contract? A truncated but valid-JSON file passes a schema parse. *Fix:* require children to write to a temp path and rename, and have the predicate accept only the renamed path. |
| D18 | The register is ambiguous between per-run and global. U2's "two sequential writers do not lose the first writer's row" implies one shared file, but nothing says how a completed run's rows are retired. *Fix:* state which, and the retirement rule. |
| D19 | U4 ships a working reap; U5 adds the integration gate that stops it discarding verified work. Between them the data-loss defect exists. *Fix:* one line in U4 stating reap is not exercised on real work until U5 lands. |
| D20 | Undefined values that two implementers would resolve incompatibly: the readiness window, the mirror distillation bound, "orchestration-intent vocabulary", the "judgment-shaped" input schema, "schema round-trips byte-identically", and "dogfooded on real work" — which has no task, pass criterion, command, evidence path, or failure disposition. *Fix:* fixed fixtures, explicit bounds, exact commands, and a named Phase 1 scenario with an evidence receipt. |
| D21 | U2's unknown-key preservation test covers a **top-level** key only; an unknown field nested in a child row can still be dropped on a cross-runtime write, which is C4's actual failure mode. *Fix:* test nested preservation. |
| D22 | `concurrency_policy.py` defines three **aggregate** limits and a digest — no per-vendor representation, no queueing. Its docstring still says *"the lease broker records and enforces"* it, and the lease broker is deleted from Claude's `fleet-core` (guarded by `tests/test_no_lease_broker_readd.py`). Saga's `concurrency_governor.py` resolves and chunks cohorts but is not named as a dependency. *Fix:* define register-owned per-vendor admission — limits, active counting, atomic slot reservation, release, restart behaviour — and name the real dependency. |
| D23 | The Problem Frame's evidence (552 transcripts, 243 failures, 477 occurrences) drives the whole severity ranking but its ledger exists only in a session scratchpad that will not survive. *Fix:* commit the ledger or cite where it lives. |
| D24 | Phase 1 is never labelled as such in the unit headings (only Phase 0 and Phase 2 are), and "dogfooded on real work" is stated as a boundary without being a gate. *Fix:* label it and give it a pass criterion. |

---

## What the panel showed

The three reviews agreed on the two mechanism failures every reader could see — the missing
subscription holder (D2) and the inert spend ceiling (D4) — and diverged usefully everywhere else.

**codex `gpt-5.6-sol` max** contributed the most severe finding and three of the four novel
structural ones: the unrecoverable event gap (D1), the missing composition unit (D5), stale
scrollback matching (D8), the retained-but-dropped depth requirement (D9), and write-ahead launch
ordering (D10). Its strength was reasoning about *sequences of state changes* — what happens between
two operations, at a crash boundary, or across a reconnect.

**grok-4.6 xhigh** contributed the deepest source-grounding: it read the Codex `models.json`
comment, the schema's `Subscription` definitions, and the scaffold's actual output, producing D3,
D6, D7, and D16. Its strength was checking what a cited module *says about itself* rather than
whether it exists.

**Claude (this session)** contributed the register-shape and requirement-coverage findings — the
missing temporal column (D13), the unowned capacity input (D14), the API-ripple risk (D15), and the
per-run ambiguity (D18) — and applied both safe fixes.

One pattern runs through D2, D4, and D22, and it is worth carrying into the revision: **each names a
real, correctly-cited, currently-shipping module whose enforcing half is absent, deleted, or
unowned.** The spend gate declines to engage without telemetry nobody produces; the concurrency
module holds limits whose enforcer was deleted with `lease_broker`; `events.subscribe` works and
nothing stays subscribed. Verifying that a module exists is not the same as verifying that something
consumes what it produces. The revision should apply that test to every remaining reuse claim.

## What was not examined

- The 552-transcript evidence corpus behind the Problem Frame. Treated as given by all three
  reviewers; see D23.
- The Headroom proxy source. Deferred in the plan and not a dependency for native CLIs.
- Live `events.subscribe` behaviour under a deliberately dropped socket. D1 is reasoned from the
  protocol-19 schema, which has no replay primitive, not from an induced disconnect.
- Whether two clients may subscribe to the same pane simultaneously — relevant to D12's handoff.
- Vendor quota state, model availability beyond confirming all six CLIs are installed, and the
  Hermes and Antigravity plugin repositories.
- No child session was launched, prompted, or reaped by the external reviewers; no plugin was
  installed; no repository test suite was run.

## Residual risk

herdr's binary and the machine-local `agent` wrapper are not versioned by this repository, so the
schema and launcher observations here are current to this host and this day rather than permanent.
A revised plan should re-run the read-only schema and wrapper checks immediately before
implementation and prove behaviour with the live acceptance cases, rather than carrying these
observations forward as settled.

The plan file was edited during the review by the two safe fixes above. This review applies to the
revision described in the header.
