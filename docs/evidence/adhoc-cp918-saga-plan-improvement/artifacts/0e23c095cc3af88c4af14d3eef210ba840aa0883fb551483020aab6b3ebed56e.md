---
title: "Integrated Code Review — issue 918 Wave 1, cycle 3 (terminal)"
type: code-review
status: complete
date: 2026-08-31
reviewed_revision: 053ef43881c2db7d7cee64845e5563a5b73eb43e
merge_base: bbac725a
branch: work/cp918-saga-plan-improvement
issue_ref: infiquetra/infiquetra-claude-plugins#918
plan_path: docs/plans/2026-08-30-saga-plan-improvement-918-wave1-plan.md
prior_cycle_artifacts:
  - docs/code-reviews/2026-08-30-issue-918-wave1-integrated-code-review.md
  - docs/code-reviews/2026-08-30-issue-918-wave1-integrated-code-review-cycle2.md
outcome: cycle_cap_best_available
cycle: 3
terminal: true
---

# Integrated Code Review — issue 918 Wave 1, cycle 3 (terminal)

**The review ends at the cycle cap with `cycle_cap_best_available` at
`053ef43881c2db7d7cee64845e5563a5b73eb43e`: every independent gate now passes, both contract
obligations that were violated at cycle 2 are restored and mutation-proven, and no lens reaches the
roster's numeric acceptance bar.** This is a legitimate ending, not a failed review. The loop stops
here because the protocol allows three cycles and three have run; the best available version is the
revision named above, and every unresolved item is enumerated below so a person can act on it later
without re-reading three artifacts.

The repair fixed what cycle 2 measured. It also did what both previous repairs did: it introduced
defects of its own. Three of the twelve remaining P1 defects were created by this commit, and the
most consequential one has the same shape as the defect it replaced — the lease close-out no longer
expands an unset shell variable, but it now instructs the agent to read a value from a saga tick
field that does not exist.

## Review-result contract

| Field | Value |
|---|---|
| Target | branch `work/cp918-saga-plan-improvement`, merge base `bbac725a` (`origin/main`) |
| Reviewed revision | `053ef43881c2db7d7cee64845e5563a5b73eb43e` |
| Cycle | **3 of 3 — terminal.** No fourth cycle exists |
| Schema | `review_result.v1` |
| Outcome | **`cycle_cap_best_available`** |
| Next action | `continue_with_best_available` |
| Allowed resume transition | `continue_with_best_available` (validated by `require_resume_transition`) |
| `best_available_revision` | `053ef43881c2db7d7cee64845e5563a5b73eb43e` |
| Lens findings | 65, across 45 distinct defects (12 at P1, 19 at P2, 14 at P3; none at P0) |
| Unresolved fix requests | 29 — 23 `review-fixer`, 3 `downstream-resolver`, 2 `release`, 1 `human`; 15 `manual`, 14 `safe_auto` |
| Independent gates | **all four pass** |
| Numeric acceptance | not reached — highest lens is 7.50 against a required 9.00 |
| Round-trip | `ReviewResult.from_json()` returns `cycle_cap_best_available` |

## Method note

The caller supplied the lens roster, which under
`plugins/saga/references/lens-roster.json` `selection_contract.caller_or_orchestrate_selection_is_approval`
**is** the conditional-lens approval; no operator question was asked, and the record was persisted
through `review_consensus.resolve_lens_selection` against reviewed commit
`053ef43881c2db7d7cee64845e5563a5b73eb43e` and cycle 3. Because no lens was ever accepted,
`state.next_lenses` returned all seven in every cycle, so all seven ran again and no delta check was
owed for a retained lens.

Every lens ran as `subagent_type: saga:readonly-verifier` with `isolation: "worktree"`, at most three
at once. The 24-step repository gate was not re-run: it is green at this revision by the caller's
given state.

Cycle 3 was adjudicated against the criteria pre-registered at cycle 1 under
`docs/evidence/adhoc-cp918-saga-plan-improvement/`, with no second freeze, so the pass/fail contract
could not be redefined across the three cycles.

**Routing discipline.** Per the caller's binding instruction, a blocker is a failing lens dimension
or a violated contract obligation; everything else is a residual, recorded and not escalated. Six
lenses named their blockers explicitly. The security lens named none — it has no dimension below the
floor — and said so.

## Consensus — final lens scores

Acceptance is the roster's rule and only the roster's rule: a derived overall of at least 9.0 **and**
every applicable dimension at 7.0 or better. Priority and confidence decide nothing. A gate result
never rescores a lens.

| Lens | Final | Accepted | Dimensions below the 7.0 floor |
|---|---|---|---|
| security | 7.50 | no | **none** — the only lens with no failing dimension, and it named no acceptance blocker |
| testing | 6.90 | no | behavior-sensitive-assertions, requirements-regression-coverage |
| agent-usability | 6.80 | no | capability-parity-reachability, discoverability-invocation-schemas, safe-bounded-idempotent-resumable-context-cost |
| api-contract | 6.75 | no | interface-contract-compatibility, serialization-errors, specification-documentation-parity |
| correctness | 6.50 | no | state-data-invariants-transactions-concurrency, boundary-types-serialization-numeric-time, caller-enum-consumer-completeness |
| documentation-clarity | 6.50 | no | shipped-behavior-parity, terminology-cross-document-consistency, runbook-safety-rollback-links-generated-drift, completeness-audience-prerequisites, runnable-examples-actionability |
| architecture-maintainability | 5.21 | no | all seven |

Two dimensions were recorded non-applicable with a cause, consistently across all three cycles:
security's `secrets-cryptography-session-handling` and api-contract's `pagination-rate-limits`.

### The full three-cycle trajectory

| Lens | `5ec8ea76` | `76533cbe` | `053ef438` |
|---|---|---|---|
| security | 7.50 | 7.50 | 7.50 |
| testing | 5.60 | 7.30 | 6.90 |
| agent-usability | 6.00 | 6.00 | 6.80 |
| api-contract | 7.50 | 6.58 | 6.75 |
| correctness | 8.40 | 6.80 | 6.50 |
| documentation-clarity | 6.00 | 6.92 | 6.50 |
| architecture-maintainability | 7.43 | 4.93 | 5.21 |

The engine recorded three further regressions at cycle 3 — correctness 6.80 to 6.50, testing 7.30 to
6.90, documentation-clarity 6.92 to 6.50 — each on the identical dimension set scored in the previous
cycle. The engine forbids ranking scores across revisions and this review does not; the table is
here because the terminal artifact is the last place anyone will look, and a reader deserves the
shape of the whole run. What it shows is a set of scores that never converged: no lens was ever
accepted in any cycle, and the panel's aggregate did not move decisively in either direction.

**The gates tell the opposite story, and they are the part that changed.** Read the two together:
the contract this work was held to is now met, while the code-quality bar the roster sets is not.

## Independent gates — all four pass

| Gate | Cycle 2 | Cycle 3 | Basis |
|---|---|---|---|
| repository-gate | pass | **pass** | The 24-step gate is green at this revision by the caller's given state: 25 steps, 0 blocking failures, 0 uncovered. Not re-derived here |
| release-surface-parity | pass | **pass** | Saga 0.150.0 in the manifest and at `plugins/saga/CHANGELOG.md:3`, with `## [0.149.0]` intact at line 49 and both bodies whole; cc-workflows 1.0.0; fifteen plugins at marketplace metadata 3.0.0; `python3 scripts/sync_marketplace.py --check` exits 0, so the registry is generated rather than hand-written |
| built-vs-planned | **fail** | **pass** | The plan's requirement R33 is now met: `assert len(specs) >= 18` is gone from `tests/test_wave_file_conflicts.py`, and the named corpus document pin is gone from `tests/test_plan_artifact_conformance.py`, replaced by a corpus-derived `rglob` the testing lens confirmed armed. No change lands outside the plan or the review — all thirteen changed files trace to a named cycle-2 finding |
| contract-obligations | **fail** | **pass** | Obligations 3 and 7 are both restored; see the obligations table |

`review_accepted: false` · `independent_gates_passed: true` · `can_proceed: false`

The last line is the honest summary: nothing external blocks this work any more, and the review's own
numeric bar is still unmet. `can_proceed` is false because numeric acceptance is false, not because a
gate failed.

## The five verifications

### 1. The three regression drivers cycle 2 named

| Driver | Verdict | Evidence |
|---|---|---|
| The Work skill's unset shell variable | **half gone** | The mechanical defect is fixed: all four expansions are quoted, and the release and renew blocks re-establish all three variables themselves. Two lenses proved the fresh-shell blocks now resolve. But the instruction that replaced it cannot be followed — see verification 2 |
| The false idempotency claim in the save-failure recovery line | **gone** | Forced against a real filesystem in a scratch repository: the index-failure message now reads "it rebuilds the index and appends one additional tick carrying the same state — harmless to restore, but visible to `saga.py ticks`, which then report both." Three lenses reproduced the same, counting envelopes before and after |
| The over-firing malformed-carrier stop | **gone** | All three documents that halted at cycle 2 now return exit 0 with `stop: null`. The api-contract lens scanned roughly 300 committed markdown documents and found zero spurious stops. The gate is two-sided: a genuinely malformed carrier still stops, and both mutation directions on the new gate turn tests red |

The envelope-failure branch is also now conditional, which closes the cycle-2 falsehood for the
exact-match case. It is not correct in general — see the P1 table.

**A correction I owe on my own work.** My reproduction of the save-failure fix passed the same
plan-path string on both saves, which was too kind a test. The correctness lens compared by raw
string equality and showed `./docs/plans/p.md` still produces the false stranded claim; the
architecture and documentation lenses then showed the deeper version, that the check reads only the
latest tick. My "driver 2 is gone" reading was right about the idempotency half and too generous
about the stranded half.

### 2. The lease protocol — the repair traded one defect for another

The mechanical half landed. `plugins/saga/skills/work/SKILL.md` release and renew blocks now
re-establish `WORKFLOW_INVOCATION_ID`, `WORKFLOW_LEASE_METADATA` and `CC_WORKFLOWS_SCRIPTS_DIR`, and
quote all four expansions; deleting the repeated assignment turns two tests red.

The instruction that replaced it cannot be followed. The blocks tell the agent to take
`WORKFLOW_INVOCATION_ID` "from the saga tick that recorded it — never mint a new one here."

**No saga tick field records it.** Measured four independent ways:

- `plugins/saga/scripts/saga.py` contains the string `invocation` **zero** times (controller).
- The `Saga` dataclass has 48 fields and none is an invocation id (agent-usability, architecture).
- `saga.py save --help` exposes no such flag; the nearest, `--orchestration-run-id`, is documented as
  the transient Workflow **run handle** returned at launch — a different value obtained later.
- The saga-spec envelope field table has no such row (controller).

Running the shipped release block in a shell that never ran the pre-submit block gives
`workflow-lease: HALT — cannot read lease metadata .saga/workflow-lease-<the invocation id recorded
in the saga tick for this launch>.json`, exit 2.

The id persists only inside `.saga/` filenames. That is the recoverable source and the proportionate
fix. `docs/engineering-journal/LEARNINGS.md` now ships the false premise as a durable rule.

No test covers it: `tests/test_saga_plugin.py` pins the order of the four emitter commands and
nothing about the variables they need.

### 3. Finding T01 and the assertions the repair touched — confirmed

The coordinator's claim holds, and the testing lens measured it: corrupting the index handler's
phrase `rewrite the saga state.json index` turns **one** test red and restoring returns **six**
green; swapping the handler for an unrelated exception gives the same. Applying the same standard to
every assertion the repair touched found one new hole, not a substitution: the stranded branch is
unreachable by any test, so inverting its predicate leaves 6 passed / 0 failed.

Twelve of the mutations the testing lens ran turned tests red as claimed, including both directions
of the new carrier-shape gate and the fresh-shell lease blocks.

### 4. Contract obligations 3 and 7 — both restored

- **Obligation 3 (harness substitution): satisfied.** Cycle 2's single instance is repaired and
  mutation-proven in both directions, and the testing lens states plainly that this repair introduced
  no new fixture, mock, or monkeypatch substitution. The new untested branch is a coverage gap, which
  is a different defect and is recorded as one.
- **Obligation 7 (no pinned corpus value): satisfied on both halves.** The integer floor is gone from
  `tests/test_wave_file_conflicts.py`, which now asserts a non-empty glob with no count; the named
  corpus document pin is gone from `tests/test_plan_artifact_conformance.py`, replaced by a
  corpus-derived `rglob` whose mutation turns 2 tests red. One named directory pin survives at
  `tests/test_workflow_extraction.py:218`, in unit U4's test — and the plan scopes R33 to units U1
  and U2, so it is outside the requirement's letter. It is recorded as a residual.

### 5. Did this repair introduce its own regressions? Yes — three at P1

1. The lease close-out reads an invocation id no tick field holds (four lenses).
2. The envelope-failure guard reads only the latest tick while its own message and the Phase 5.3
   runbook claim "no earlier tick" (four lenses, reproduced with a two-tick chain).
3. The unreadable-file stop promises to name the path and cannot: the errno prefix consumes 37 of the
   40 echo characters, so at most one path character survives (three lenses).

Two more at P2: the new `--established` flag accepts values outside the declared enums, and a
repeated field silently lets the last one win — in a module whose stated discipline stops on
duplicate JSON keys for exactly that reason.

That is the third consecutive cycle in which the repair fixed what was named and broke something
adjacent. It is the most durable finding of this review.

## Contract obligations — final verdicts

| # | Obligation | C1 | C2 | C3 | Basis at `053ef438` |
|---|---|---|---|---|---|
| 1 | Plan phases 0, 1, 2, 4 gained no new question, checklist, questionnaire, or fixed sequence | ok | ok | **satisfied** | Splitting `plugins/saga/skills/plan/SKILL.md` on `## Phase N` headings against the merge base: phases 1, 2 and 4 hash identically. Phase 0 changed only by gaining subsection 0.7, a rule table that removes a question and adds none |
| 2 | No test asserts an exact Plan question, its wording, or the order of the conversation | ok | ok | **satisfied** | No question assertion in any changed test; the only question-adjacent one is an absence check |
| 3 | No test substitutes a fixture, mock, or monkeypatch for the behaviour it claims to prove | **violated** | **violated** | **satisfied** | Cycle 2's instance is repaired and mutation-proven in both directions, and the testing lens confirms this repair added none |
| 4 | Plan's board-move sentences untouched | ok | ok | **satisfied** | Both merge-base blocks present verbatim |
| 5 | Workflow backend runnable and explicit-invocation-only (issue 808) | **violated** | ok | **satisfied** | `tests/test_saga_plugin.py` — 54 passed, including both pins. The carrier stops on both richer backends; Plan's normal offer, its recommend rule and the three-value enum are unchanged |
| 6 | Backend-override telemetry retained | ok | ok | **satisfied** | `override_rate_reader.py` untouched by this repair; consumers in the Retro and Optimize skills; `tests/test_override_rate.py` present. The repair also closed the cycle-2 ambiguity: Plan Phase 5.2 now says explicitly to still call `recommend_execution_backend` and still record `--orchestration-recommended` on the carrier path |
| 7 | No corpus integer or corpus file name pinned in code or tests | partial | **violated** | **satisfied** | Both halves retired; see verification 4. One named directory pin survives in unit U4's test, outside requirement R33's scope, recorded as a residual |
| 8 | No repository-level unreferenced-plan scanner, state store, daemon, registry, queue, or reconciliation pass | ok | ok | **satisfied** | No new module writes anything; the conformance check remains a read-only pass with a command line |
| 9 | Plan-document contract kept out of the tick envelope field table | ok | ok | **satisfied** | The saga-spec envelope field table is unchanged; the plan-doc contract is its own section |
| 10 | Built versus planned | partial | partial | **satisfied** | R33 is met, every requirement is built, and no change lands outside the plan or the review. All thirteen changed files trace to a named cycle-2 finding |

## Carried-forward items — reported, not re-filed

| Finding | Route | Status at `053ef438` |
|---|---|---|
| F10 / F11 — the emitter binds private Saga names; a third copy of the resolver ladder | downstream-resolver | Still open. The repair contains no file under `plugins/cc-workflows/` |
| F25 — the plugin-root ladder matches any marketplace | advisory | Still open |
| F28 / F29 — the corpus pins | downstream-resolver / advisory | **Both closed.** They were the two halves of obligation 7 |
| F31 — the cross-plugin seam has no declared dependency | release, coordinator-owned | Still open. **It does not block** |

### F31 — does it block, and what is proportionate

**No, it does not block**, and two lenses reached that independently.

The runtime coupling is real and it fails loud: `saga_spec_shim.py` resolves Saga through a four-rung
ladder and raises with an actionable message on a total miss, and `plugins/cc-workflows/README.md`
already states that the saga plugin, or a repo checkout containing `plugins/saga/`, is a prerequisite.
Nothing in the repository is broken by the omission today, and both plugins ship at aligned versions.

What is genuinely unenforced is the **version** boundary: no rung applies a minimum Saga version — the
cache-sibling rung takes the highest semver it finds, and the root validator only checks that
`scripts/execution_spec.py` exists — so an incompatible Saga is bound rather than refused.

The smallest proportionate fix is one line of JSON and no code, copying a pattern already in this
repository: `plugins/orchestrate/.claude-plugin/plugin.json` declares
`"dependencies": [{"name": "agent-launcher", "version": ">=1.0.0"}]`. Add
`"dependencies": [{"name": "saga", "version": ">=0.150.0"}]` to
`plugins/cc-workflows/.claude-plugin/plugin.json`. No version-negotiation machinery.

Two caveats a later reader should carry. The api-contract lens did not run the repository's plugin
validators against that hypothetical edit, so the schema's acceptance rests on the orchestrate
precedent rather than on a test. And the agent-usability lens's view is that a declared dependency
would **not** fix the seam's other face: Saga's own hard-block authoring step points at a command
that lives only in the sibling plugin's skill, which is a missing inline command and a missing halt,
not a missing manifest entry.

## The residual set — everything still open, standalone

This section is written to be read on its own. It assumes no knowledge of the two earlier artifacts.
Twenty-nine consolidated fix requests remain unresolved, covering 45 distinct defects. Nothing here
blocks a merge by itself — the gates pass — but nothing here has been fixed either, and the review
has no further cycle in which to check a repair.

### Group A — the three defects this repair introduced (fix these first)

1. **The lease close-out cannot be executed.** `plugins/saga/skills/work/SKILL.md:428`, `:433`, `:445`
   tell an agent to take `WORKFLOW_INVOCATION_ID` from the saga tick. No tick field, no `saga.py save`
   flag, and no spec row holds it; `saga.py` never contains the word. Running the block verbatim
   halts with `cannot read lease metadata .saga/workflow-lease-<the invocation id …>.json`, exit 2.
   **Fix:** point both blocks at the on-disk lease artifact — the id is embedded in the
   `.saga/workflow-lease-*.json` filename and carried in its `invocation_id` field — or add a real
   Saga field plus a save flag and record it at launch before claiming a tick carries it. Then correct
   `docs/engineering-journal/LEARNINGS.md:29`, which now records the false premise as durable practice.
2. **The stranded-document claim is still wrong, in a narrower way.**
   `plugins/saga/scripts/saga.py:1712` decides between "tracked" and "stranded" by comparing
   `restore()` — the **latest** tick only — against `args.plan_path` by raw string equality. A
   two-tick chain whose newest tick names a different plan gets the false stranded claim, and so does
   an equivalent path spelled `./docs/plans/p.md`. The message at `:1720` and the runbook at
   `plugins/saga/skills/plan/SKILL.md:627-630` both say "no earlier tick", which the code does not
   check. **Fix:** scan `read_ticks` for any matching tick and normalize both paths before comparing,
   or narrow both prose surfaces to "the most recent tick".
3. **The unreadable-file stop cannot name the path it promises.**
   `plugins/saga/skills/plan/SKILL.md:152-153` and the module docstring promise a stop naming the
   unreadable path; `_ECHO_LIMIT = 40` is consumed by the 37-character errno prefix. **Fix:**
   interpolate the path outside the bounded echo, or delete the promise from both surfaces.

Plus two at P2, both on the new `--established` flag at `plugins/saga/scripts/plan_pre_answers.py:366`:
it accepts values outside the declared enum (so a typo becomes a false "already-established value"),
and a repeated field silently lets the last one win — in a module whose own discipline stops on
duplicate JSON keys for that exact reason. The flag also appears on no release surface.

### Group B — the cross-plugin seam, untouched by all three repairs

`plugins/cc-workflows/` received no edit in any repair cycle. Four lenses found the same defect
across three cycles: `plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py:1348` calls
`_ES._agent_prompt`, which is absent from the 29-name `SUBSTRATE_SURFACE` at `:48-77`, so
`_bind_substrate` accepts a substrate lacking it and the failure lands as an attribute error at emit
time — the precise failure the guard's docstring says it prevents. The guard test walks only
assignment nodes, so a qualified access is structurally invisible to it. **Fix:** add the name and
teach the guard to walk `_ES.<attribute>` accesses.

Also in this group: `concurrency_governor` crosses the same boundary wholesale outside the declared
seam; the resolution ladder's documented rung 1 is preceded by an undocumented `sys.modules`
short-circuit; and Saga's own `plugins/saga/references/execution-spec.md:399` hard-block step points
at a command that lives only in the sibling plugin's skill, with no halt named for that plugin being
absent.

### Group C — prose that does not match the code

- `docs/engineering-journal/LEARNINGS.md:69` still records the save re-run as idempotent and claims
  "all four prose surfaces corrected" — the runtime message, the Plan skill and the changelog were
  corrected; this entry was not.
- Three surfaces state the schema rule as non-v1-inside-family versus foreign-family and none says
  the version token is compared **exactly**, so an uppercase but otherwise correct token is refused
  whole. The repair replicated the incomplete wording onto a third surface.
- `plugins/saga/scripts/plan_pre_answers.py:48` and the saga-spec still say the validator "reads no
  file" while its documented command line reads one. The repair edited that very saga-spec sentence
  and left the clause standing.
- `plugins/saga/CHANGELOG.md:33` says `docs/plans/` is reserved for plan documents; eleven non-plan
  entries remain, and the parallel journal entry states it accurately.
- `plugins/saga/references/operator-choice.md:59` still says the backend offer is ALWAYS surfaced,
  with no mention of the carrier exception Plan now applies.

**The mechanism behind this whole group is one missing test.** No test binds any carrier prose surface
to the code. The documentation lens proved it: reverting the repaired changelog sentence to the exact
cycle-2 falsehood left 98 tests green. The proportionate fix is the pin cycle 2 specified, in the
shape of the existing required-field pin — parse the sentences out of all three surfaces and bind them
to the module's own constants.

### Group D — guards that do not guard

- The backend-enum rule in the shipped conformance check has no positive test; disabling it leaves 41
  tests green.
- The required-field pin binds two of three declarations and misses the YAML template an authoring
  agent copies; deleting a required key from it leaves 11 tests green.
- The never-pre-select guard is file-level, not sentence-level; `work/SKILL.md` carries two accepted
  phrasings, so corrupting either alone leaves 293 tests green.
- The enum drift pin matches source **text**, so a formatter reflow turns it red and a real semantic
  drift slips past it.
- The stranded branch of the envelope handler is unreachable by any test.
- The shipped conformance check still has no caller outside its own test, and no invocation prose.

### Group E — sharp edges, no action required

Recorded so a later reader is not surprised: an uppercase `JSON` fence silently discards a valid
carrier; a stray triple backtick shifts fence pairing and drops one; a carrier wrapped in a JSON array
is ignored; a carrier truncated before its schema token is now ignored rather than stopped; broken
YAML in a plan reclassifies it as legacy; the two `OSError` subclasses lose `errno` and `filename`;
committed documentation examples are live carriers that settle `backend: inline` and
`destination: plan-only` on a Plan run over them — privilege direction downward, escalation denied.

## Findings

Sixty-five lens findings resolve to forty-five distinct defects. Where several lenses reached
the same defect independently, the `#` column lists every identifier and the Reviewers column
names every lens; the route shown is the most conservative any reviewer assigned. The typed
result keeps all sixty-five, each bound to the lens that scored it.

### P1 — 12 distinct defects

| # | File | Issue | Reviewers | Conf | Route |
|---|---|---|---|---|---|
| N01 | `docs/engineering-journal/LEARNINGS.md:69` | Journal still records the index re-run as idempotent | documentation | 100 | manual -> review-fixer |
| X06 | `plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py:48` | SUBSTRATE_SURFACE still omits _agent_prompt | correctness | 100 | safe_auto -> review-fixer |
| Q01/Z05 | `plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py:1348` | Undeclared private Saga name still crosses the plugin boundary | api-contract, testing | 100 | manual -> review-fixer |
| N05/N08/Y08 | `plugins/saga/CHANGELOG.md:7` | Still no test binds carrier prose to the code | agent-usability, documentation | 100 | manual -> review-fixer |
| N06 | `plugins/saga/references/saga-spec.md:700` | Case-differing v1 token refused, three surfaces say otherwise | documentation | 100 | manual -> review-fixer |
| W05 | `plugins/saga/scripts/plan_pre_answers.py:48` | Purity claim still says reads no file | architecture | 100 | safe_auto -> review-fixer |
| V05/W03/X04/X05/Y09 | `plugins/saga/scripts/plan_pre_answers.py:94` | Two family-membership tests that are not the same test | agent-usability, architecture, correctness, security | 100 | manual -> review-fixer |
| N02/X01/Y02 | `plugins/saga/scripts/plan_pre_answers.py:384` | Unreadable-file stop does not name the path | agent-usability, correctness, documentation | 100 | manual -> review-fixer |
| N03/W01/X03/Z01 | `plugins/saga/scripts/saga.py:1712` | Envelope-failure guard checks the latest tick, prose says any earlier | architecture, correctness, documentation, testing | 100 | manual -> review-fixer |
| W06 | `plugins/saga/scripts/saga.py:1725` | Generic branch still calls a read failure a write | architecture | 100 | manual -> review-fixer |
| N04/V09/W02/Y01 | `plugins/saga/skills/work/SKILL.md:428` | Release block reads an invocation id no tick field holds | agent-usability, architecture, documentation, security | 100 | manual -> review-fixer |
| W04 | `tests/test_plan_artifact_conformance.py:323` | Required-field pin still misses the YAML template | architecture | 100 | manual -> review-fixer |

### P2 — 19 distinct defects

| # | File | Issue | Reviewers | Conf | Route |
|---|---|---|---|---|---|
| W08 | `docs/engineering-journal/LEARNINGS.md:29` | Journal codifies a rule about a nonexistent tick field | architecture | 100 | manual -> review-fixer |
| V02 | `docs/plans/2026-08-30-saga-plan-improvement-918-wave1-plan.md:346` | Committed documentation examples are live carriers | security | 100 | manual -> downstream-resolver |
| Q06 | `plugins/saga/CHANGELOG.md:9` | New repeatable flag absent from every release surface | api-contract | 100 | manual -> release |
| N07 | `plugins/saga/CHANGELOG.md:33` | Changelog says docs/plans is reserved for plan documents | documentation | 100 | safe_auto -> review-fixer |
| Y07 | `plugins/saga/references/execution-spec.md:399` | HARD BLOCK step still points across plugins with no fallback | agent-usability | 100 | safe_auto -> review-fixer |
| Y04 | `plugins/saga/references/saga-spec.md:699` | Version-token exactness still unstated | agent-usability | 100 | safe_auto -> review-fixer |
| Y05 | `plugins/saga/scripts/plan_artifact_conformance.py:18` | Conformance checker still undiscoverable, exit 2 still undocumented | agent-usability | 100 | safe_auto -> review-fixer |
| X07 | `plugins/saga/scripts/plan_artifact_conformance.py:81` | Broken YAML still reclassifies a backend plan as legacy | correctness | 100 | manual -> review-fixer |
| Q05 | `plugins/saga/scripts/plan_artifact_conformance.py:102` | Conformance script still crashes with the failure exit code | api-contract | 100 | manual -> review-fixer |
| Z02 | `plugins/saga/scripts/plan_artifact_conformance.py:122` | Backend-enum rule still has no positive test | testing | 100 | safe_auto -> review-fixer |
| X08 | `plugins/saga/scripts/plan_pre_answers.py:87` | Stray triple backtick still drops the carrier | correctness | 100 | manual -> review-fixer |
| X09 | `plugins/saga/scripts/plan_pre_answers.py:197` | Carrier-shaped non-object JSON still slips the stop | correctness | 100 | manual -> review-fixer |
| V01 | `plugins/saga/scripts/plan_pre_answers.py:242` | Unknown-key refusal still echoes caller keys raw and unbounded | security | 100 | safe_auto -> review-fixer |
| Q02/V04/X02/Y03/Z07 | `plugins/saga/scripts/plan_pre_answers.py:366` | New --established flag validates the field, never the value | agent-usability, api-contract, correctness, security, testing | 100 | manual -> review-fixer |
| Q03 | `plugins/saga/scripts/plan_pre_answers.py:371` | Repeated --established for one field silently lets the last win | api-contract | 100 | manual -> review-fixer |
| Q04 | `plugins/saga/scripts/plan_pre_answers.py:394` | Outcome report still stamped with the carrier's own version token | api-contract | 100 | manual -> review-fixer |
| Q07/W09 | `plugins/saga/scripts/saga.py:856` | Wrapped tick errors still drop errno and filename | api-contract, architecture | 100 | safe_auto -> review-fixer |
| W07 | `plugins/saga/scripts/saga.py:1706` | Exception handler re-reads state save already computed | architecture | 100 | manual -> review-fixer |
| Y06 | `plugins/saga/skills/work/SKILL.md:350` | False parity claim now replicated across three lease blocks | agent-usability | 100 | manual -> review-fixer |

### P3 — 14 distinct defects

| # | File | Issue | Reviewers | Conf | Route |
|---|---|---|---|---|---|
| N09 | `docs/engineering-journal/DECISIONS.md:17` | Undefined internal code still in the journal | documentation | 100 | safe_auto -> review-fixer |
| V07 | `plugins/cc-workflows/README.md:34` | Documented resolution ladder still omits the sys.modules short-circuit | security | 100 | safe_auto -> review-fixer |
| V08 | `plugins/saga/references/operator-choice.md:59` | Decision contract still states ALWAYS-surface with no carrier exception | security | 100 | safe_auto -> review-fixer |
| Z06 | `plugins/saga/scripts/plan_artifact_conformance.py:163` | Conformance check still has no caller outside its test | testing | 100 | manual -> human |
| Q08 | `plugins/saga/scripts/plan_pre_answers.py:179` | Uppercase JSON fence still discards a valid carrier silently | api-contract | 100 | manual -> review-fixer |
| V03 | `plugins/saga/scripts/plan_pre_answers.py:255` | caller still unbounded and narrated verbatim | security | 100 | safe_auto -> review-fixer |
| X10 | `plugins/saga/scripts/plan_pre_answers.py:282` | Invocation-only stop still masks the established conflict | correctness | 100 | manual -> review-fixer |
| V06 | `tests/test_plan_pre_answers.py:361` | The half of the echo fix that landed has no regression test | security | 100 | safe_auto -> review-fixer |
| Z04 | `tests/test_plan_pre_answers.py:540` | Drift pin matches source text, wrong in both directions | testing | 100 | safe_auto -> review-fixer |
| Z08 | `tests/test_saga_plan_save_and_routing.py:213` | Re-run tick claim asserted only as word absence | testing | 100 | advisory -> review-fixer |
| Z03 | `tests/test_workflow_extraction.py:113` | Never-pre-select guard remains file-level, not sentence-level | testing | 100 | safe_auto -> review-fixer |
| Z09 | `tests/test_workflow_extraction.py:218` | One named corpus directory pin survives in the U4 test | testing | 100 | advisory -> downstream-resolver |
| Y10 | `tests/test_workflow_extraction.py:312` | Fresh-shell structural guard covers one of three variables | agent-usability | 100 | safe_auto -> review-fixer |
| W10 | `tests/test_workflow_extraction.py:343` | Fresh-shell guard fails as StopIteration, not a diagnosis | architecture | 100 | safe_auto -> review-fixer |

## Finding detail

Each finding cites evidence the reviewer personally checked. Mutation results quote the command and
its pass/fail counts; where a lens was independently confirmed by another lens or by the controller,
that is said so.

### P1

**Y01 — Release block sources the invocation id from a nonexistent tick field** · `plugins/saga/skills/work/SKILL.md:428` · lens `agent-usability` · dimension `safe-bounded-idempotent-resumable-context-cost`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

The repaired release and renew blocks tell the agent to take WORKFLOW_INVOCATION_ID from the saga tick, but no saga envelope field, command-line flag, or spec row records it, so on the crash-resume path the protocol names as its reason for existing the value is unrecoverable and the lease never closes.

Evidence:

- plugins/saga/skills/work/SKILL.md:428 and the placeholder exports at :433 and :445
- lens measurement: a grep for 'invocation' in plugins/saga/scripts/saga.py returned 0; saga.py save --help exposes --orchestration-run-id documented as the transient workflow RUN handle and nothing for an invocation id; the saga-spec frontmatter field table has no such row
- lens run of the shipped release block verbatim in a shell with none of the three variables set: 'workflow-lease: HALT — cannot read lease metadata .saga/workflow-lease-<the invocation id recorded in the saga tick for this launch>.json', exit 2
- docs/engineering-journal/LEARNINGS.md now codifies the same false premise as a durable rule
- the pre-existing instruction to RECORD it was never backed by a field; what is NEW is the release path depending on reading it back
- controller independently confirmed: saga.py contains the string 'invocation' zero times, and the forty-field envelope table has no such field
- no test covers it -- tests/test_saga_plugin.py:88-102 pins the ORDER of the four emitter commands and nothing about the variables they need

Suggested fix: Either add an invocation-id flag plus envelope field to saga.py and cite it, or change the instruction to name the real source -- the lease receipt already on disk under .saga/, which can be enumerated without any tick.

**Q01 — Undeclared private Saga name still crosses the plugin boundary** · `plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py:1348` · lens `api-contract` · dimension `interface-contract-compatibility`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

_bind_substrate admits a substrate lacking _agent_prompt, so an incompatible Saga binds cleanly and dies with an attribute error at emit time instead of at bind time.

Evidence:

- the repair commit contains no file under plugins/cc-workflows/ at all
- static scan: 29 names declared at emitter.py:48-77 and _agent_prompt is the sole qualified substrate access absent from it
- stub proof: a module carrying every declared name and nothing else passed _bind_substrate with no error, leaving the attribute absent; the surface test reports 3 passed with the gap present
- nothing breaks at runtime today because the definition exists in Saga
- found independently by the correctness, architecture and testing lenses and by the controller; four lenses found it at cycle 2

Suggested fix: Add the name to SUBSTRATE_SURFACE and bind it like the others, and extend the guard test to walk qualified attribute accesses on the substrate module.

**W01 — Envelope-failure branch checks only the latest tick** · `plugins/saga/scripts/saga.py:1709` · lens `architecture-maintainability` · dimension `readability-naming-error-contracts`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

restore() returns the newest tick only, so a chain whose latest tick names a different plan makes the handler tell the operator a plan document has NO tick referencing it when an earlier tick on disk does.

Evidence:

- saga.py:1709 calls restore(root, incoming.saga_id) and compares prior.plan_path; restore is documented latest-tick-only at :1014-1023 while read_ticks at :1026 is the chain reader
- lens reproduction: saved a tick for plan a, then a tick for plan b, made the saga directory read-only and re-saved with plan a -- exit 2 with 'now has NO saga tick referencing it', while the first envelope on disk still records plan a
- NEW defect introduced by this repair; complements the correctness lens's normalization finding on the same branch

Suggested fix: Walk read_ticks and test whether ANY tick's plan_path matches, or narrow the message to 'no tick since the last one recorded this plan path'.

**W02 — Release block reads an invocation id no tick carries** · `plugins/saga/skills/work/SKILL.md:428` · lens `architecture-maintainability` · dimension `conventions-portability-configuration`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

The repair replaced the unset shell variable with an instruction to take WORKFLOW_INVOCATION_ID from the saga tick, but no Saga field and no save flag holds it, so an agent following the block literally cannot recover the launch identity and the lease still never closes.

Evidence:

- work/SKILL.md:428 and the placeholders at :433 and :445
- lens measurement: enumerating the Saga dataclass fields lists 48, none for a workflow invocation id; saga.py save --help exposes no such flag; the id is written only into .saga/ filenames at :349, :360, :384 and :508 and never into a tick
- controller and agent-usability lens confirmed the same independently

Suggested fix: Point the two blocks at the on-disk lease artifact instead, or add a real Saga field plus a save flag and record it in the launch tick before saying a tick carries it.

**W03 — Two family-membership tests that are not the same test** · `plugins/saga/scripts/plan_pre_answers.py:94` · lens `architecture-maintainability` · dimension `simplicity-abstraction-duplication-changeability`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

_is_carrier_shaped is a raw-text regex over the whole block while _is_family_schema is a prefix test on the parsed schema value, so a foreign-family carrier with a malformed body now stops a Plan run that the same carrier well-formed would silently ignore -- a second, divergent authority over family membership.

Evidence:

- the two functions at plan_pre_answers.py:94-98 and :129-139; the comment at :90-91, the module docstring at :43-45 and saga-spec.md:716-719 all assert they are the same membership test
- lens probe: a foreign-family block with a trailing comma returns carrier-shaped True, family-schema False, and stops; the same block well-formed returns no stop
- a block whose only family mention is a prose value also stops
- the security lens found the mirror evasion: a JSON-escaped family token is admitted by the parsed test but not the raw one

Suggested fix: Gate the malformed stop on the block's declared schema token rather than any occurrence of the family name, then delete the equivalence claim or pin it with a test over both functions.

**W04 — Required-field pin still misses the YAML template** · `tests/test_plan_artifact_conformance.py:323` · lens `architecture-maintainability` · dimension `architectural-fit-ownership-single-sources`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

The required-field contract has three declarations and only two are bound, so deleting a required key from the template authoring agents copy leaves the suite green and every new plan failing the shipped check.

Evidence:

- the pin at tests/test_plan_artifact_conformance.py:323-348 parses only the plan-sections bullet and one collapsed sentence; the template is at plugins/saga/skills/plan/SKILL.md:265-273
- lens mutation: deleting a required key from the template left tests/test_plan_artifact_conformance.py at 11 passed and the seven files reading that skill at 135 passed; restored
- carried from cycle 2 finding A07, not addressed

Suggested fix: Extend that test to parse the YAML block in the Plan skill and assert its keys are a superset of the required-field tuple.

**W05 — Purity claim still says reads no file** · `plugins/saga/scripts/plan_pre_answers.py:48` · lens `architecture-maintainability` · dimension `significant-decision-documentation`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

Both surfaces still promise the validator reads no file while its documented command line reads one, so a maintainer refactoring for purity will contradict the shipped entry point.

Evidence:

- plan_pre_answers.py:48 and plugins/saga/references/saga-spec.md:723; the read is at plan_pre_answers.py:374
- the repair edited that very saga-spec line in this commit to append the --established clause and left 'reads no file' in the same sentence
- carried from cycle 2 finding A09, not addressed

Suggested fix: Replace both sentences with the wording already applied to the emitter docstring: the evaluation functions are pure, the command line reads only the invocation file it is given.

**W06 — Generic branch still calls a read failure a write** · `plugins/saga/scripts/saga.py:1725` · lens `architecture-maintainability` · dimension `readability-naming-error-contracts`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

save() reads the prior tick before either write, so a read-side error lands in the generic branch and prints 'failed to write the saga tick' when nothing was written, prescribing a restore that fails identically.

Evidence:

- the read at saga.py:802 precedes both writes at :854 and :860; the generic handler at :1725-1734 is unchanged by this commit
- lens reproduction: making the saga directory unreadable then saving gave the write-framed message and the restore prescription, and running that prescribed restore gave a bare traceback with exit 1
- carried from cycle 2 finding A06, not addressed

Suggested fix: Wrap the prior-tick read in its own named error, or reword the generic branch and drop the restore prescription from a branch that cannot distinguish read from write.

**X06 — SUBSTRATE_SURFACE still omits _agent_prompt** · `plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py:48` · lens `correctness` · dimension `caller-enum-consumer-completeness`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

The emitter calls _ES._agent_prompt on the escalate-on-signal retry path but never declares it, so _bind_substrate accepts a substrate lacking it and the failure lands as an AttributeError at emit time -- precisely what the guard's docstring says it prevents.

Evidence:

- emitter.py:48-78 lists 29 names with _agent_prompt absent; emitter.py:1348 reads _ES._agent_prompt(spec, retry_unit)
- lens proof: _bind_substrate against a stub carrying exactly the 29 declared names and nothing else SUCCEEDED, guard silent
- the repair commit 053ef438 does not touch emitter.py at all
- controller static confirmation, and four lenses found this independently at cycle 2

Suggested fix: Add _agent_prompt to SUBSTRATE_SURFACE and extend the guard test to walk _ES.<attr> accesses, not just assignments inside _bind_substrate.

**N01 — Journal still records the index re-run as idempotent** · `docs/engineering-journal/LEARNINGS.md:69` · lens `documentation-clarity` · dimension `terminology-cross-document-consistency`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

The durable learning tells future maintainers the re-run rebuilds the index idempotently and that all four prose surfaces were corrected, so a maintainer reading it would restore the exact false claim the runtime message, the Plan skill and the changelog were just repaired to drop.

Evidence:

- LEARNINGS.md:69 is unchanged by this repair -- the diff to that file is additions only
- lens reproduction: forcing the index failure in a scratch repository gave two envelopes before the re-run and three after, and the runtime message now correctly says it appends one additional tick
- the exception docstring at plugins/saga/scripts/saga.py:697-701 states the same non-idempotence
- carried from cycle 2 finding D06, not addressed

Suggested fix: Rewrite the Fix and Mechanism lines of that entry to say the re-run appends one additional tick, and drop or scope the 'all four prose surfaces corrected' sentence.

**N02 — Unreadable-file stop does not name the path** · `plugins/saga/skills/plan/SKILL.md:153` · lens `documentation-clarity` · dimension `shipped-behavior-parity`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

Two surfaces added by this repair promise the stop names the unreadable path, but the forty-character echo budget truncates the message before the path can appear, so an agent told to surface the path has nothing to surface.

Evidence:

- plugins/saga/skills/plan/SKILL.md:152-153 and the module docstring at plan_pre_answers.py:337
- lens run: the errno prefix alone consumes 37 of the 40 echo characters, so at most one path character ever survives
- the guard at tests/test_plan_pre_answers.py:498 asserts only that the word appears, never the path
- NEW false claim introduced by this repair; found independently by the correctness and agent-usability lenses

Suggested fix: Interpolate the path outside the bounded echo, or delete the naming promise from both surfaces.

**N03 — Envelope-failure guard checks the latest tick, prose says any earlier** · `plugins/saga/scripts/saga.py:1720` · lens `documentation-clarity` · dimension `runbook-safety-rollback-links-generated-drift`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

The message and the Phase 5.3 runbook both condition on no earlier tick referencing the plan, but the code tests only the latest tick, so a saga whose newest tick names a different plan document is told a tracked plan is stranded.

Evidence:

- saga.py:1712 compares the latest tick's plan path; saga.py:1720 and plugins/saga/skills/plan/SKILL.md:627-630 state the any-earlier-tick claim
- lens reproduction: a two-tick chain where the newest names a different plan produced the stranded claim while the first envelope on disk carries the plan path
- the new regression test covers only the single-prior-tick same-path case
- NEW defect introduced by this repair; found independently by the architecture lens

Suggested fix: Scan the tick chain for any tick whose plan path matches instead of reading only the latest, or narrow both prose surfaces to 'the most recent tick'.

**N04 — Release block reads an invocation id no tick field holds** · `plugins/saga/skills/work/SKILL.md:433` · lens `documentation-clarity` · dimension `completeness-audience-prerequisites`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

The rewritten fresh-shell blocks tell the agent to take the invocation id from the saga tick and forbid minting a new one, but no saga tick field and no save flag record that value, so the lease close-out has no reachable source for its only required input.

Evidence:

- the Saga dataclass carries no invocation-id field among its 48 names; the save parser has no flag for it
- the only recording step in the Work skill is the orchestration run handle, which the flag's own help text calls a different value obtained after launch
- the instruction is at work/SKILL.md:428, :433 and :445, and the journal records it as the shipped fix
- the root claim is pre-existing at the merge base, but this repair turned it into a runnable placeholder
- found independently by the controller and the agent-usability and architecture lenses

Suggested fix: Either add a recording path and name it in the two blocks, or point the blocks at the on-disk lease metadata where the id actually persists.

**N05 — Still no test binds carrier prose to the code** · `plugins/saga/CHANGELOG.md:7` · lens `documentation-clarity` · dimension `runbook-safety-rollback-links-generated-drift`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

Three documents state the carrier contract and none is bound to the code, which is the mechanism that let two false changelog claims survive cycle 1 and five of cycle 2's ten findings survive cycle 2 -- the gate cannot see a prose regression.

Evidence:

- the 108 lines added to tests/test_plan_pre_answers.py are all behavioural; none references the changelog, the spec or the skill
- lens mutation: replacing the repaired changelog sentence with the exact cycle-2 falsehood left 98 tests passing across three modules; restored
- carried from cycle 2 finding D07, not addressed

Suggested fix: Add the pin cycle 2 specified, in the shape of the existing required-field pin: parse the two-case schema sentence and the inline-only sentence out of all three surfaces and bind them to the module's own constants.

**N06 — Case-differing v1 token refused, three surfaces say otherwise** · `plugins/saga/references/saga-spec.md:700` · lens `documentation-clarity` · dimension `shipped-behavior-parity`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

All three surfaces say the family match is case-insensitive and that only a non-v1 token is refused, so a caller writing an uppercase but otherwise correct version token expects it applied and instead gets a whole-carrier refusal calling its own token unrecognised.

Evidence:

- saga-spec.md:699-702, plugins/saga/skills/plan/SKILL.md:170-172, and the sentence the repair ADDED at plugins/saga/CHANGELOG.md:14-15 all state the rule the same incomplete way
- lens run: an uppercase version token gave exit 2 with the whole-refusal stop
- the mechanism is the family test lowercasing at :133-137 while the token comparison at :227 is exact; only the internal docstring names the case correctly
- carried from cycle 2 finding D08, not addressed, and now replicated onto a third surface

Suggested fix: Add one clause to all three surfaces: the version token itself is matched exactly, so any other casing is inside the family and refused whole.

### P2

**Y02 — Unreadable-file stop never names the path the prose promises** · `plugins/saga/skills/plan/SKILL.md:152` · lens `agent-usability` · dimension `machine-readable-output-actionable-errors`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

Phase 0.7 tells the agent the stop names the unreadable path and to surface it exactly, but the forty-character echo budget is consumed by the errno prefix, so the operator is told a file is unreadable without being told which one.

Evidence:

- plugins/saga/skills/plan/SKILL.md:152-153 versus plan_pre_answers.py:103
- lens run: even a short relative filename truncates mid-path
- the rest of the exit contract IS genuinely fixed: missing file, permission-denied, non-UTF-8 and a directory all exit 2 with the same JSON shape, and four malformed command lines all exit 2 through argparse with usage and no JSON
- found independently by the correctness lens

Suggested fix: Echo the path separately from the exception text, or raise the echo limit for this one message.

**Y03 — Phase 0.7's own example command halts Plan with a false conflict** · `plugins/saga/skills/plan/SKILL.md:143` · lens `agent-usability` · dimension `context-constraints-acceptance-examples`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

The --established flag validates the field name but never the value, so the skill's canonical command block run as printed treats the literal placeholder as an established decision and stops Plan at entry on a conflict that does not exist.

Evidence:

- plugins/saga/skills/plan/SKILL.md:143 prints both flags unconditionally; plan_pre_answers.py:366 checks only that the field is known
- lens run of the block as written against a valid inline carrier: exit 2 with 'supplied backend value inline contradicts the already-established value <already-settled-value>'
- the same command with a nonsense value also stopped rather than erroring, so a typo is indistinguishable from a real conflict
- the mitigating sentence at :146-148 exists but the command block contradicts it

Suggested fix: Validate each --established value against its enum in the argument parser, and mark the two flags optional in the command block.

**Y04 — Version-token exactness still unstated** · `plugins/saga/references/saga-spec.md:699` · lens `agent-usability` · dimension `discoverability-invocation-schemas`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

A carrier-authoring agent reading the case-insensitive family rule predicts an uppercase token is applied, but the version token is compared exactly, so a case variant is refused whole and its settled decisions are lost.

Evidence:

- saga-spec.md:699 is untouched by the repair
- lens run: a carrier declaring an uppercase family token returned the whole-refusal stop, while the canonical token applied both decision fields
- the same gap exists in the skill an agent executes at plugins/saga/skills/plan/SKILL.md:161-163
- carried from cycle 2 finding U10, not addressed

Suggested fix: Append the sentence to both places: family membership is matched case-insensitively; the full token is compared exactly, so any case variation is a non-v1 token and is refused whole.

**Y05 — Conformance checker still undiscoverable, exit 2 still undocumented** · `plugins/saga/scripts/plan_artifact_conformance.py:18` · lens `agent-usability` · dimension `discoverability-invocation-schemas`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

No shipped skill tells an agent when or how to run the plan-artifact conformance check, and its docstring still promises only exits 0 and 1 while a bad root exits 2, so an agent treats a configuration mistake as a contract failure.

Evidence:

- a grep across plugins/ matches only prose in saga-spec.md and the script itself -- no hit under plugins/saga/skills/
- lens run: the script against a nonexistent root printed a one-key JSON error and exited 2, against a docstring promising only 0 and 1
- carried from cycle 2 finding U08, not addressed; the testing lens found the same absence of any caller

Suggested fix: Add the literal command and all three exit codes as a Phase 5-side step in the Plan skill, and add the bad-root case to the module docstring.

**Y06 — False parity claim now replicated across three lease blocks** · `plugins/saga/skills/work/SKILL.md:350` · lens `agent-usability` · dimension `capability-parity-reachability`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

The comment says the shell resolves the scripts directory the same way the Python seam does, but the shell has one environment rung plus a working-directory-relative default while the Python seam has four, so outside a repo-root working directory all three blocks die on a bare interpreter error instead of the seam's guided halt.

Evidence:

- plugins/saga/skills/work/SKILL.md:350-352 against the ladder message at plugins/saga/scripts/execution_spec.py:2466
- the repair copied the two-rung line verbatim into the release and renew blocks at :435 and :447 without the caveat
- lens run of the shipped release block from a non-checkout working directory: a bare interpreter file-not-found, exit 2, with no halt text
- the new guard at tests/test_workflow_extraction.py:312 runs with the repo root as its working directory, so it cannot see this

Suggested fix: Replace the parity claim with the true statement, and add a guard that halts with the resolver's own message when the resolved path is absent.

**Y07 — HARD BLOCK step still points across plugins with no fallback** · `plugins/saga/references/execution-spec.md:399` · lens `agent-usability` · dimension `capability-parity-reachability`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

Step 2 of Saga's own authoring flow is a hard block whose only command lives in another plugin's skill file at a repo-relative path that does not resolve in an installed-plugin session, and no halt is named for that plugin being absent, so the agent cannot complete the gate it is forbidden to skip.

Evidence:

- plugins/saga/references/execution-spec.md:399-401; the equivalent Saga command differing only in runner already sits inline at :429
- untouched by the repair -- the thirteen changed files do not include this one
- the lens's view on carried-forward finding F31: a declared dependency would NOT fix this, because the failure is a missing inline command and a missing halt, not a missing manifest entry
- carried from cycle 2 finding U07, not addressed

Suggested fix: Keep the cross-reference for rationale, restate the one-line validate command inline, and name the halt when the sibling plugin is not installed.

**Y08 — New --established flag missing from the release surface** · `plugins/saga/CHANGELOG.md:7` · lens `agent-usability` · dimension `discoverability-invocation-schemas`  
Route `safe_auto -> release` · confidence 100 · pre-existing: no

The repair added a repeatable agent-facing command-line flag that the release surface never mentions, so an agent or caller reading the changelog to learn the carrier's interface cannot discover the only way to make the contradiction rule fire.

Evidence:

- a grep for the flag name across plugins/saga/CHANGELOG.md at this revision returns nothing
- the 0.150.0 pre-answer entry at :7-17 describes the contradiction stop without naming the flag that supplies the established value, which is defined at plan_pre_answers.py:351-361
- the repository's own CLAUDE.md step 6 requires the plugin release surfaces to move with any command change in the same pull request
- NEW gap introduced by this repair; the cycle-2 half of this line was fixed -- the two-case unknown-schema wording is now correct

Suggested fix: Add one clause to the 0.150.0 entry naming the repeatable flag as the way a caller supplies already-settled decisions.

**Y09 — Carrier-shape gate silently drops a truncated carrier** · `plugins/saga/scripts/plan_pre_answers.py:191` · lens `agent-usability` · dimension `context-constraints-acceptance-examples`  
Route `manual -> downstream-resolver` · confidence 100 · pre-existing: no

The new gate requires the raw block text to name the family before a parse failure stops, so a carrier truncated before its schema token completes is ignored with exit 0 -- the silent drop the malformed-carrier rule was added to prevent.

Evidence:

- plan_pre_answers.py:184 and :191 continue when the block is not carrier-shaped
- lens runs: a fence containing a schema key truncated mid-token returned applied {} stop None, as did a hyphenated variant; a carrier truncated AFTER the token still stops correctly
- at the cycle-2 revision every one of these stopped, so the safety property narrowed
- the shipped rule in the Plan skill describes this behaviour accurately, so the prose is not wrong
- found independently by the correctness lens

Suggested fix: Warn carrier-authoring agents in the saga-spec carrier section that a carrier truncated before its schema token is silently ignored, or widen the shape test to the other admitted keys.

**Q02 — New --established flag validates the field, never the value** · `plugins/saga/scripts/plan_pre_answers.py:366` · lens `api-contract` · dimension `interface-contract-compatibility`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

The flag accepts a value outside the field's declared enum, then manufactures an exit-2 stop asserting a contradiction with an already-established value that is not a legal value of that field at all, and the Plan skill instructs the agent to surface that reason verbatim.

Evidence:

- plan_pre_answers.py:366 tests only the separator, a non-empty value and a known field
- lens runs: an out-of-enum established value against a valid carrier gave exit 2 and a false conflict; a realistic case-typo produced the same; a value containing a second separator is likewise accepted
- the module rejects an out-of-enum value on the carrier side at :265-273; the flag side has no equivalent
- NEW surface introduced by this repair; found independently by the correctness, security and agent-usability lenses

Suggested fix: Require the value to be in the field's enum and route the failure through the same argument-parser error, naming the enum.

**Q03 — Repeated --established for one field silently lets the last win** · `plugins/saga/scripts/plan_pre_answers.py:371` · lens `api-contract` · dimension `interface-contract-compatibility`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

The same two flags in opposite order give opposite verdicts with no diagnostic, in a module whose stated discipline stops on duplicate JSON keys for exactly this reason.

Evidence:

- the assignment at :371 overwrites without checking membership
- lens runs: the same carrier with the two orderings gave exit 0 with an applied value in one order and exit 2 with a contradiction in the other
- no test repeats a field -- the two added subprocess cases pass one flag each
- NEW defect introduced by this repair

Suggested fix: Stop when the field is already present with a different value, using the same never-resolved-silently wording the duplicate-key stop uses.

**Q04 — Outcome report still stamped with the carrier's own version token** · `plugins/saga/scripts/plan_pre_answers.py:394` · lens `api-contract` · dimension `serialization-errors`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

One version token names two incompatible objects -- the four-field carrier and the four-field report -- so the report is refused by the very evaluator that emitted it.

Evidence:

- plan_pre_answers.py:394 is unchanged from cycle 2
- lens round-trip: the exact stdout of a clean run, re-fenced and fed back to the evaluator, was refused as carrying unadmitted keys
- no shipped surface documents the report's shape; the Plan skill names only the stop field and the exit codes
- carried from cycle 2 finding P06, not addressed

Suggested fix: Emit a distinct outcome token for the report and document its four fields in the saga-spec carrier section.

**Q05 — Conformance script still crashes with the failure exit code** · `plugins/saga/scripts/plan_artifact_conformance.py:102` · lens `api-contract` · dimension `serialization-errors`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

An unreadable document exits 1 with a raw traceback and no output -- the same code the docstring reserves for a real conformance failure -- so a consumer cannot tell a crash from a finding.

Evidence:

- the read at :102 is unguarded; a scratch root holding one non-UTF-8 file gave a decode error, exit 1, empty stdout
- the docstring at :18-19 still declares only 0 and 1 while main() returns 2 on a non-directory root, which the lens confirmed
- the sibling entry point was repaired to exactly the right shape in this same change, so the correct pattern already exists
- carried from cycle 2 finding P05, half-fixed

Suggested fix: Wrap the per-document read, emit the one-key JSON error and exit 2 the bad-root branch already uses, and add exit 2 to the docstring.

**Q06 — New repeatable flag absent from every release surface** · `plugins/saga/CHANGELOG.md:9` · lens `api-contract` · dimension `specification-documentation-parity`  
Route `manual -> release` · confidence 100 · pre-existing: no

A new public flag on a shipped script ships with no changelog line and no stated failure modes, so an integrating caller has no authoritative account of what a bad or repeated value does.

Evidence:

- a grep for the flag across the changelog returns zero; the 0.150.0 entry names the validator script but never the flag
- the Plan skill and the saga-spec show the happy path only -- neither states what an out-of-enum value or a repeated field does
- the repository's own contributing rule requires the release surfaces to move with a command change
- version metadata itself is consistent: saga 0.150.0 and cc-workflows 1.0.0 in both the manifests and the registry
- NEW gap introduced by this repair; found independently by the agent-usability lens

Suggested fix: Add one 0.150.0 bullet naming the repeatable flag, its two fields, and that a contradicting carrier stops.

**W07 — Exception handler re-reads state save already computed** · `plugins/saga/scripts/saga.py:1706` · lens `architecture-maintainability` · dimension `separation-of-concerns`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

The error-presentation path performs a second filesystem read of the same envelope save() already loaded, and swallows four exception classes behind a comment asserting a false inference, so a diagnostic message depends on I/O succeeding at the exact moment the filesystem is failing.

Evidence:

- saga.py:1709 duplicates the read at :802 where save() already binds prior; :1710-1711 swallows four classes behind the comment 'an unreadable prior proves no reference'
- because :802 runs first, any read fault reaches the generic branch instead, leaving this swallow reachable only in a race
- NEW structure introduced by this repair

Suggested fix: Carry the already-computed prior on the exception itself, set at the raise site, and drop the re-read and its four-class catch.

**W08 — Journal codifies a rule about a nonexistent tick field** · `docs/engineering-journal/LEARNINGS.md:29` · lens `architecture-maintainability` · dimension `significant-decision-documentation`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

The entry records as durable practice that the lease-metadata path is derived from the invocation id taken from the saga tick, so a future maintainer will look for a tick field that has never existed and will trust the release path as closed.

Evidence:

- LEARNINGS.md:29 under the fresh-shell-block-scope anchor at :24; the Saga dataclass has no such field and the save command no such flag
- the same entry's validation paragraph IS accurate about the shell mechanics: deleting the repeated assignment from the release block turned tests/test_workflow_extraction.py to 2 failed / 12 passed
- NEW false durable record introduced by this repair

Suggested fix: Rewrite the Fix paragraph to name the real recovery source, and keep the generalizable fresh-shell rule, which is correct and proven.

**W09 — Wrapped tick errors still drop errno and filename** · `plugins/saga/scripts/saga.py:856` · lens `architecture-maintainability` · dimension `readability-naming-error-contracts`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

Both OSError subclasses are still constructed from a single string, so a caller cannot tell a full disk from a permission failure, and there is still no shared base to catch both without naming both.

Evidence:

- saga.py:856 and :861-863; only the class docstrings at :683-702 changed in this commit
- lens probe: wrapping a disk-full error gave errno, strerror and filename all None on the wrapper while the original kept its errno
- carried from cycle 2 finding A12, not addressed

Suggested fix: Construct with errno, message and filename, and give both classes a shared base.

**X01 — Unreadable-file stop names none of the path** · `plugins/saga/scripts/plan_pre_answers.py:384` · lens `correctness` · dimension `side-effects-errors-resource-lifecycle`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

_ECHO_LIMIT truncates the echoed OSError before a single path character survives, so the stop the repair added for cycle-2 C10 cannot tell an operator which file failed.

Evidence:

- plan_pre_answers.py:103 sets the limit, :384-386 builds the stop, and :336-337 plus plugins/saga/skills/plan/SKILL.md:152-153 both promise a stop naming the unreadable path
- lens run against a deep nonexistent path: rc 2 and a stop truncated mid-errno, with no path character surviving
- the new test at tests/test_plan_pre_answers.py:521 asserts only that the word 'unreadable' appears, so the promise its own comment at :505 makes is unpinned
- NEW defect introduced by this repair

Suggested fix: Echo the path itself rather than the exception string.

**X02 — --established accepts values outside the decision enums** · `plugins/saga/scripts/plan_pre_answers.py:366` · lens `correctness` · dimension `caller-enum-consumer-completeness`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

The guard checks only that the field is a known field, never that the value is in that field's enum, so a typo or an unsubstituted placeholder becomes a settled decision and stops a perfectly valid carrier.

Evidence:

- plan_pre_answers.py:366 reads 'if not separator or not value or field not in DECISION_ENUMS'
- lens run: a valid inline carrier with --established backend=totally-bogus returned rc 2 and 'supplied backend value inline contradicts the already-established value totally-bogus'
- DECISION_ENUMS[field] is in hand on that line and unused
- NEW defect introduced by this repair

Suggested fix: Extend the guard to reject a value outside DECISION_ENUMS[field] and name the legal values in the parser error text.

**X03 — Stranded-plan test is raw string equality on plan_path** · `plugins/saga/scripts/saga.py:1712` · lens `correctness` · dimension `state-data-invariants-transactions-concurrency`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

The same plan document spelled differently fails the comparison, so the operator is told the document has no tick referencing it while an earlier tick does -- the cycle-2 C02 falsehood moved rather than removed.

Evidence:

- saga.py:1709-1723
- lens reproduction: with a prior tick recorded under docs/plans/p.md, an envelope failure for ./docs/plans/p.md produced 'now has NO saga tick referencing it', and identically for docs/../docs/plans/p.md, while the exact string produced the correct 'an earlier tick still references'
- two further weaknesses on the same branch: restore reads only the LATEST tick, so an earlier tick naming the plan is invisible once a later tick names a different one; and parse_envelope('') returns a Saga with an empty plan_path, so a mid-write envelope failure also yields the false claim
- the except (OSError, ValueError, TypeError, KeyError) fallback at :1710-1711 is unreachable from the command line, because save() calls restore at :800 before the envelope write; its comment 'an unreadable prior proves no reference' is wrong reasoning on dead code
- the controller's own reproduction used the exact path string and therefore missed this

Suggested fix: Normalize both sides before comparing, and scan every tick rather than only the latest; replace the fallback comment and emit the uncertain message there.

**X04 — Shape gate still halts on prose that names the family** · `plugins/saga/scripts/plan_pre_answers.py:191` · lens `correctness` · dimension `intent-behavior-completeness`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

_CARRIER_SHAPE_RE searches the whole raw block, so an unrelated malformed JSON example that merely mentions the family token in a string value or a comment still stops the entire Plan run.

Evidence:

- plan_pre_answers.py:94 and :184/:191
- lens runs: a json fence holding a note string mentioning the family token plus a comment returned the malformed-carrier stop; so did a duplicate-key block whose comment mentioned it
- the two cycle-2 reproductions no longer halt, so the fix is real but partial
- the docstring at :89-93 claims the gate is the same membership test _is_family_schema performs; that one tests the parsed schema value, this tests raw text anywhere in the block

Suggested fix: Gate on a schema-position match rather than a bare token search, and correct the docstring's equivalence claim.

**X05 — Truncated carrier is now silently dropped with no stop** · `plugins/saga/scripts/plan_pre_answers.py:192` · lens `correctness` · dimension `intent-behavior-completeness`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

A carrier whose malformation removed the family token is no longer carrier-shaped, so it takes the continue and becomes indistinguishable from absence -- the silent-resolution hole the module exists to close, reopened for the truncation case.

Evidence:

- plan_pre_answers.py:191-192
- lens run: a carrier clipped before its schema line returned applied {} omitted (backend, destination) stop None; the same block with the schema line present returns the malformed-carrier stop, so the gate is the difference
- NEW hole opened by this repair's shape gate

Suggested fix: Treat a json fence naming caller, backend or destination keys as carrier-shaped too, or narrow the continue to blocks that parse cleanly as a foreign schema.

**X07 — Broken YAML still reclassifies a backend plan as legacy** · `plugins/saga/scripts/plan_artifact_conformance.py:81` · lens `correctness` · dimension `state-data-invariants-transactions-concurrency`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

split_frontmatter swallows a YAML error into empty fields, so a plan that does declare backend but has any YAML syntax slip is reported non-failing legacy and passes the gate, violating the module's own rule that legacy means the absence of backend and nothing else.

Evidence:

- plan_artifact_conformance.py:79-85 and the classification at :104
- lens run: check_document on frontmatter carrying backend inline plus an unclosed list returned legacy-no-backend with legacy True
- the repair commit does not touch this file

Suggested fix: Emit a distinct failing unparseable-frontmatter finding in the YAML-error arm instead of collapsing it into the legacy bucket.

**X08 — Stray triple backtick still drops the carrier** · `plugins/saga/scripts/plan_pre_answers.py:87` · lens `correctness` · dimension `boundary-types-serialization-numeric-time`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

_FENCE_RE pairs fence markers left to right with no odd-count handling, so one inline triple backtick before the carrier shifts the pairing and the caller's settled decision vanishes with no stop.

Evidence:

- plan_pre_answers.py:87 and :178
- lens run: a well-formed carrier alone applied backend inline; the identical carrier preceded by a line containing a stray triple backtick returned applied {} stop None
- unchanged by this repair

Suggested fix: Anchor the fence match to line starts and count backticks so an unpaired or longer fence cannot offset the scan.

**X09 — Carrier-shaped non-object JSON still slips the stop** · `plugins/saga/scripts/plan_pre_answers.py:197` · lens `correctness` · dimension `boundary-types-serialization-numeric-time`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

The isinstance dict guard continues on any scalar or array, so a carrier a caller wrapped in a JSON array is dropped as absence even though the block plainly names the family.

Evidence:

- plan_pre_answers.py:197-198
- lens runs: a json fence holding a one-element array wrapping a valid carrier returned applied {} stop None; so did a fence holding the bare schema string
- the repair built _is_carrier_shaped -- exactly cycle-2's suggested fix for this line -- and never applied it here

Suggested fix: Return the malformed-carrier stop at :197 when the block is carrier-shaped, keeping continue only for non-object blocks with no family token.

**N07 — Changelog says docs/plans is reserved for plan documents** · `plugins/saga/CHANGELOG.md:33` · lens `documentation-clarity` · dimension `completeness-audience-prerequisites`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

A reader acting on the release note would treat eleven surviving non-plan entries as misfiled, and the sentence contradicts the parallel journal entry that is accurate.

Evidence:

- CHANGELOG.md:32-33 unchanged by this repair; the lens counted eleven non-plan entries including two decision briefs and the ideation subtree
- docs/engineering-journal/DECISIONS.md:16 states the accurate wording
- carried from cycle 2 finding D10, not addressed

Suggested fix: Match the journal wording: the directory no longer holds generated artifacts and retains plan documents plus the ideation subtree.

**N08 — 0.150.0 entry omits the new --established flag** · `plugins/saga/CHANGELOG.md:7` · lens `documentation-clarity` · dimension `completeness-audience-prerequisites`  
Route `manual -> release` · confidence 100 · pre-existing: no

The repair added a repeatable command-line option and the repository's contributing rule requires a command change to move with the release surfaces in the same change, so a reader of the release entry cannot discover the flag the contradiction rule now depends on.

Evidence:

- the flag is added at plan_pre_answers.py:351-361 and documented in the spec and the skill, but a grep across the changelog returns nothing
- the plugin manifest is at 0.150.0, so this release is the right one to carry it
- NEW gap introduced by this repair; found independently by the agent-usability and api-contract lenses

Suggested fix: Add one clause to the carrier bullet naming the repeatable flag as how a caller supplies an already-settled decision.

**V01 — Unknown-key refusal still echoes caller keys raw and unbounded** · `plugins/saga/scripts/plan_pre_answers.py:242` · lens `security` · dimension `confidentiality-logs-errors-egress`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

A refusal message Plan is told to surface exactly can still be inflated to 50,162 characters and can still carry unescaped newlines and fence delimiters, because only the duplicate-key half was routed through the bounded echo.

Evidence:

- plan_pre_answers.py:242 builds the listing with a bare f-string and never calls _echo, while the repaired duplicate-key path at :187 now does
- lens measurement: one 50,000-character unknown key gave a 50,162-character stop, byte-identical to cycle 2's number; 2,000 unknown keys gave 17,049; every other refusal path is now bounded between 85 and 218 characters
- injection reproduced: an unknown key containing a newline and a fence produced a stop whose text opens a fence and reads like an operator confirmation
- carried from cycle 2 finding S02, half-fixed

Suggested fix: Route the listing through the bounded echo, and extend the bounded-echo test to the unknown-key and duplicate-key paths.

**V02 — Committed documentation examples are live carriers** · `docs/plans/2026-08-30-saga-plan-improvement-918-wave1-plan.md:346` · lens `security` · dimension `authentication-authorization-tenant-isolation`  
Route `manual -> downstream-resolver` · confidence 100 · pre-existing: no

Running Plan on a plan document that merely documents the carrier silently settles backend and destination and suppresses the Phase 5.1 and 5.2 operator questions, attributing the decision to a caller that never ran.

Evidence:

- the lens scanned every committed markdown file under docs/ and plugins/ through the shipped evaluator: two return a non-empty apply, the wave-1 plan at :346 and plugins/saga/references/saga-spec.md:692, both yielding an applied inline backend and plan-only destination with a caller of orchestrate and no stop
- the Plan skill directs the validator at the invocation text, and plan documents are inputs Plan legitimately receives
- caller is never authenticated -- only an isinstance check -- so the narrated provenance is whatever the text claims
- the same scan found zero documents that now halt, which is what closes cycle-2 finding S01
- privilege direction is downward and escalation is denied: a carrier naming the Workflow backend still stops

Suggested fix: Require the carrier fence to be the first fenced block, or require an explicit opt-in token the documentation examples omit; alternatively fence the two examples with an info string the scanner already treats as not-a-carrier.

**Z01 — New envelope-handler branch has one untested side** · `plugins/saga/scripts/saga.py:1712` · lens `testing` · dimension `negative-edge-state-concurrency-time`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

The repair split the envelope-write failure message into a tracked branch and a stranded branch, and only the tracked branch is proven, so inverting the predicate makes the command tell an operator a genuinely stranded plan is tracked with nothing going red.

Evidence:

- lens mutation: the predicate at saga.py:1712 forced to True left 6 passed, 0 failed; corrupting the else-branch text at :1718 also left 6 passed, 0 failed
- controls arm correctly: forcing the predicate False gave 1 failed / 5 passed, and swapping the except clause for an unrelated exception gave the same
- grep for the stranded phrase across tests/ returns only this one module, so no other suite covers it
- NEW coverage hole introduced by this repair

Suggested fix: Add a sibling test that fails the envelope write with NO prior tick recording the plan path and asserts the stranded branch's own words, the way the new tracked test asserts its own.

**Z02 — Backend-enum rule still has no positive test** · `plugins/saga/scripts/plan_artifact_conformance.py:122` · lens `testing` · dimension `requirements-regression-coverage`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

The unit U1 contract's backend enum can stop being enforced, or shrink to a single value, and the whole suite stays green -- no fixture ever carries an out-of-enum backend value.

Evidence:

- lens mutation: the enum check at :122 forced False left 41 passed, 0 failed across both conformance suites
- appending a one-value BACKEND_ENUM after :45 left tests/test_plan_artifact_conformance.py at 11 passed, 0 failed
- the enum finding kind appears in the test file only as an absence assertion
- carried from cycle 2, not addressed

Suggested fix: Add a tmp_path fixture whose frontmatter carries an out-of-enum backend value and assert the enum finding with a failing corpus exit.

**Z05 — SUBSTRATE_SURFACE still under-declares the plugin boundary** · `plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py:1348` · lens `testing` · dimension `realistic-seams-mocks-integration-evidence`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

_agent_prompt crosses the cc-workflows and saga seam through a qualified call but is absent from the declared surface, so the guard a reader trusts to describe the boundary is wrong about the boundary it describes.

Evidence:

- emitter.py:1348 calls _ES._agent_prompt; the name is absent from the surface tuple at :48-78
- lens mutation: renaming the definition in plugins/saga/scripts/execution_spec.py:2199 left tests/test_cc_workflows_emitter_surface.py at 3 passed, 0 failed
- commit 053ef438 does not touch emitter.py at all -- the thirteen changed files include none under plugins/cc-workflows/
- found independently by the correctness lens and the controller; four lenses found it at cycle 2

Suggested fix: Add _agent_prompt to SUBSTRATE_SURFACE and extend the guard's name collection to walk qualified attribute accesses on the substrate module.

### P3

**Y10 — Fresh-shell structural guard covers one of three variables** · `tests/test_workflow_extraction.py:312` · lens `agent-usability` · dimension `safe-bounded-idempotent-resumable-context-cost`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

The guard asserts only that the scripts-directory assignment precedes its first use, so deleting either of the other two assignments from a close-out block reintroduces the empty-expansion class the guard exists to prevent, and stays green.

Evidence:

- tests/test_workflow_extraction.py:312-326 partitions on the scripts-directory variable only
- the companion subprocess proof at :329 substitutes the invocation-id placeholder before running, so it cannot fail on a missing assignment either

Suggested fix: Loop the structural assertion over all three variable names rather than hard-coding the scripts-directory one.

**Q07 — New OSError subclasses still carry no errno, strerror, filename** · `plugins/saga/scripts/saga.py:856` · lens `api-contract` · dimension `serialization-errors`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

A handler branching on the error number -- the machine-actionable contract, and the shape this repository's own diagnostics read -- silently takes the None path.

Evidence:

- saga.py:856 and :861-863 are unchanged; the repair edited only the two class docstrings and the operator messages
- lens probe: both classes constructed from a disk-full error reported no error number, message or filename while the string form kept the full text
- no production consumer reads the error number today, which is why this is a residual
- carried from cycle 2 finding P04, not addressed

Suggested fix: Construct with the error number, message and filename from the cause.

**Q08 — Uppercase JSON fence still discards a valid carrier silently** · `plugins/saga/scripts/plan_pre_answers.py:179` · lens `api-contract` · dimension `serialization-errors`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

The fence info string is compared case-sensitively while the schema family is matched case-insensitively to catch near-misses loudly, so a caller writing an uppercase fence loses a fully valid settled decision with no stop.

Evidence:

- plan_pre_answers.py:179 is unchanged; the family test lowercases
- lens run: an uppercase-fenced valid carrier returned a result identical to the no-carrier case
- downgraded from cycle 2's P2 because the repair DID document the drop in both authoritative surfaces, so parity now holds and only the sharp edge remains

Suggested fix: Lowercase the info string before comparison, and add a case-variant fence case beside the existing fence tests.

**W10 — Fresh-shell guard fails as StopIteration, not a diagnosis** · `tests/test_workflow_extraction.py:343` · lens `architecture-maintainability` · dimension `readability-naming-error-contracts`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

The guard selects its block with a needle containing the quote character, so unquoting the expansion makes the test die with a bare StopIteration inside a generator rather than reporting what broke.

Evidence:

- tests/test_workflow_extraction.py:343 selects the block by a quoted needle
- lens mutation: removing the quotes from all four expansions gave 1 failed / 67 passed, the failure being StopIteration at that line rather than the block's own assertions; restored

Suggested fix: Select the block quote-tolerantly and add an explicit assertion that a block was found.

**X10 — Invocation-only stop still masks the established conflict** · `plugins/saga/scripts/plan_pre_answers.py:282` · lens `correctness` · dimension `side-effects-errors-resource-lifecycle`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

The invocation-only backend check returns before the established comparison, so a carrier escalating from an operator-settled inline is diagnosed as merely needing invocation -- and the new --established flag makes that path reachable from the documented command for the first time.

Evidence:

- plan_pre_answers.py:282-295 precedes :296-307
- lens run: an ultracode carrier against an established inline returned the invocation-only stop with no mention of the established value; nothing is applied either way, so only the diagnosis is wrong

Suggested fix: Run the established comparison first and, when both fire, emit one stop naming the contradiction and the invocation-only rule together.

**N09 — Undefined internal code still in the journal** · `docs/engineering-journal/DECISIONS.md:17` · lens `documentation-clarity` · dimension `terminology-cross-document-consistency`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

A maintainer reading the decision entry cannot learn which settled decision the extraction served, because the code is expanded nowhere in the repository.

Evidence:

- a repository grep returns exactly three sites and none defines it; the plan's sibling code is likewise used without expansion
- carried from cycle 2 finding D09, not addressed

Suggested fix: Expand on first use in both the journal entry and the test comment.

**V03 — caller still unbounded and narrated verbatim** · `plugins/saga/scripts/plan_pre_answers.py:255` · lens `security` · dimension `input-trust-boundaries-injection`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

A caller-supplied string of any length with newlines intact still lands in operator-facing narration on the path where the run continues rather than stops, so the narration surface is shaped by the supplying capability.

Evidence:

- plan_pre_answers.py:255-263 is still the only validation and :311 still returns caller unchanged; the repair did not touch either
- lens reproduction: a caller carrying newlines and bold markup returned applied with no stop and the caller byte-for-byte; a 100,000-character caller returned intact
- carried from cycle 2 finding S03, not addressed

Suggested fix: Return the bounded echo of caller, or reject a caller containing a newline or longer than a fixed width.

**V04 — New --established flag validates the field but never the value** · `plugins/saga/scripts/plan_pre_answers.py:366` · lens `security` · dimension `input-trust-boundaries-injection`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

The new command-line surface accepts any value for a decision field, so the validator stops a legal carrier and tells the operator that an impossible value is the already-established value.

Evidence:

- plan_pre_answers.py:366 checks only the separator, a non-empty value and a known field -- no membership check, unlike carrier values at :271
- lens run: an out-of-enum established value against a valid inline carrier gave exit 2 and a contradiction stop naming the impossible value
- injection does NOT hold -- a newline-and-fence payload came back repr-escaped and truncated -- and escalation does NOT hold: an established Workflow backend still hits the invocation-only stop
- NEW surface introduced by this repair; found independently by the correctness and agent-usability lenses

Suggested fix: Add a membership check against the field's enum to the argument-parser error condition.

**V05 — Shape gate matches raw text where the family gate matches parsed values** · `plugins/saga/scripts/plan_pre_answers.py:94` · lens `security` · dimension `input-trust-boundaries-injection`  
Route `manual -> downstream-resolver` · confidence 100 · pre-existing: no

One test reads bytes and the other reads parsed values, so the same block can be a carrier to one and prose to the other -- which makes the duplicate-key stop evadable and lets a truncated carrier pass as no carrier.

Evidence:

- plan_pre_answers.py:94 gates :184 and :191 while :129-139 gates :199
- lens reproduction: a block whose schema token is JSON-escaped is admitted by the parsed test but not the raw one, so a duplicated key in that block was silently skipped instead of stopping
- a carrier truncated before its schema line returns no stop -- the malformed-is-indistinguishable-from-absence defect, surviving for the subset that does not literally spell the family
- both evasions fail SAFE: nothing is applied and both fields fall through to the operator conversation
- both mutation directions on the gate go red, so the repair itself is properly guarded

Suggested fix: Decode JSON string escapes before the shape test, or make the shape test a lenient parse that looks for a schema value in the family.

**V06 — The half of the echo fix that landed has no regression test** · `tests/test_plan_pre_answers.py:361` · lens `security` · dimension `confidentiality-logs-errors-egress`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

The duplicate-key bounded-echo guard can be deleted and nothing goes red, so the one bounded refusal path the repair added is unguarded against the next edit.

Evidence:

- lens mutation: reverting the bounded echo at plan_pre_answers.py:187 left tests/test_plan_pre_answers.py at 30 passed, the same as baseline; restored
- cycle 2's suggested fix explicitly asked for the bounded-echo test to cover all four refusal paths; it still exercises only the schema-token path

Suggested fix: Parametrize the bounded-echo test over the unknown-key, duplicate-key, bad-enum and established-conflict paths with a large payload each.

**V07 — Documented resolution ladder still omits the sys.modules short-circuit** · `plugins/cc-workflows/README.md:34` · lens `security` · dimension `dependency-supply-chain`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

The README's rung-one promise that an invalid root override raises rather than falls through does not hold on the cached path, so a reader auditing which code the plugin loads is told the wrong thing.

Evidence:

- the repair's thirteen files include neither this README nor operator-choice.md
- lens re-reproduction at this revision: with an invalid root override and a stub pre-registered under the module name, the loader returned the stub with no exception while resolving the root directly raised
- carried from cycle 2 finding S04, not addressed

Suggested fix: One sentence in the README's resolution section naming the module-cache reuse as the step above rung one, and the same line in the shim docstring.

**V08 — Decision contract still states ALWAYS-surface with no carrier exception** · `plugins/saga/references/operator-choice.md:59` · lens `security` · dimension `authentication-authorization-tenant-isolation`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

The authority Plan Phase 5.2 defers to says the backend offer is always surfaced, while Plan now skips that offer when a carrier applied an inline backend, so the two shipped surfaces disagree about when an operator gets asked.

Evidence:

- operator-choice.md:58-60 still reads ALWAYS surface with no carrier mention, and a grep for the carrier across that file returns nothing
- plugins/saga/skills/plan/SKILL.md:348 carries the exception
- the repair commit's file list does not include operator-choice.md; carried from cycle 2 finding S06, not addressed

Suggested fix: One bullet naming the Phase 0.7 carrier as the single exception, scoped to the inline backend.

**V09 — New invocation-id placeholder flows unvalidated into a lease filename** · `plugins/saga/skills/work/SKILL.md:433` · lens `security` · dimension `input-trust-boundaries-injection`  
Route `manual -> downstream-resolver` · confidence 100 · pre-existing: no

The repair added two blocks that tell the agent to paste a saga-tick value into a shell assignment whose result becomes a filename, and no layer validates the value's shape, so a value containing a parent-directory segment writes the lease metadata outside the state directory.

Evidence:

- cycle-2 finding S05 is FIXED: all four expansions are quoted and the two fresh-shell blocks now re-establish the variables that were previously undefined there
- the new surface is the placeholder export at :433 and :445 feeding the lease filename at :434 and :446
- lens reproduction in bash: a value containing a parent-directory segment resolves the lease path to the repository root; no layer constrains it -- the emitter's text validator accepts any non-empty string
- the first block mints from uuidgen and is unaffected, and the surrounding file already uses unquoted angle-bracket placeholders, so this is a new instance of an existing pattern rather than a repair regression

Suggested fix: Constrain the invocation id to a hexadecimal-and-hyphen shape in the emitter's metadata validator, and add a guard beside the two placeholder assignments.

**Z03 — Never-pre-select guard remains file-level, not sentence-level** · `tests/test_workflow_extraction.py:113` · lens `testing` · dimension `behavior-sensitive-assertions`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

Deleting the prohibition sentence the guard is named for from the Work skill leaves every test green, because a second unrelated phrasing elsewhere in the same file satisfies the substring check.

Evidence:

- tests/test_workflow_extraction.py:113 and tests/test_saga_plugin.py:741 are both an OR over two phrasings across whole-file text
- lens mutation: corrupting the sentence at plugins/saga/skills/work/SKILL.md:53 while leaving the second phrasing at :275 intact, then running all ten modules that read that skill, gave 293 passed, 0 failed
- the repair touched tests/test_saga_plugin.py only for quote tolerance, not for this guard

Suggested fix: Assert a collapsed-text regex binding the pre-select prohibition to the backend it governs within one clause, and require a per-file match count rather than an OR over two phrasings.

**Z04 — Drift pin matches source text, wrong in both directions** · `tests/test_plan_pre_answers.py:540` · lens `testing` · dimension `determinism-isolation-diagnostics-maintainability`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

A formatter reflow with zero semantic change turns the pin red, and a real semantic drift of the same constant slips past it, so the pin reports the opposite of the contract it claims to guard.

Evidence:

- tests/test_plan_pre_answers.py:537-540 reads the conformance module as text and asserts the literal line
- lens mutation: reflowing the tuple onto four lines with an identical value gave 1 failed / 29 passed; appending a semantically different redefinition after it, so the pinned text still matched, gave 30 passed / 0 failed
- the file already imports the module properly at :526-532

Suggested fix: Load the conformance module and compare the two constants directly, deleting the text pin.

**Z06 — Conformance check still has no caller outside its test** · `plugins/saga/scripts/plan_artifact_conformance.py:163` · lens `testing` · dimension `requirements-regression-coverage`  
Route `manual -> human` · confidence 100 · pre-existing: no

The shipped contract check runs only when pytest runs, so a non-conforming plan artifact authored outside a test run is never reported -- the condition cycle-1 finding F06t was filed against.

Evidence:

- a repo-wide grep outside tests/ and the module itself returns only prose in plugins/saga/references/saga-spec.md and the module's own usage line
- scripts/gate.sh:186 and .github/workflows/ci.yml:95 call a different script
- the 47-line Plan skill diff in 053ef438 adds no runnable command block for this check

Suggested fix: Add a gate step running the conformance check over docs/plans, or give Plan Phase 5.3 a runnable command block the way Phase 0.7 has one.

**Z07 — New --established validation branch is untested** · `plugins/saga/scripts/plan_pre_answers.py:366` · lens `testing` · dimension `negative-edge-state-concurrency-time`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

The whole rejection path for a malformed --established argument -- missing separator, empty value, unknown field, and its bounded echo of caller input -- can be disabled without any test noticing.

Evidence:

- lens mutation: the guard at :366 forced False left 30 passed, 0 failed
- the positive halves ARE armed: neutering the assignment at :371 gave 1 failed / 29 passed, and dropping the established argument at :390 gave the same
- tests/test_plan_pre_answers.py is the only module that passes this flag

Suggested fix: Extend the entry-point test with a subprocess call passing a malformed --established value and assert exit 2 with argparse usage on stderr and no JSON on stdout.

**Z08 — Re-run tick claim asserted only as word absence** · `tests/test_saga_plan_save_and_routing.py:213` · lens `testing` · dimension `behavior-sensitive-assertions`  
Route `advisory -> review-fixer` · confidence 100 · pre-existing: no

The index handler now tells the operator the re-run appends one additional tick, and the only guard is that the message does not say idempotent, so the claim's truth is unverified by the suite even though it is true today.

Evidence:

- tests/test_saga_plan_save_and_routing.py:213 is a pure absence check; nothing counts ticks after a re-run
- the lens verified the claim by hand outside the suite: first save exit 2 with one tick, then a clean re-run exit 0 with two ticks

Suggested fix: In the same test, clear the blocker, re-run the identical arguments, and assert two ticks both carrying the completed phase status.

**Z09 — One named corpus directory pin survives in the U4 test** · `tests/test_workflow_extraction.py:218` · lens `testing` · dimension `requirements-regression-coverage`  
Route `advisory -> downstream-resolver` · confidence 100 · pre-existing: no

A test asserts a specific corpus subdirectory name, so renaming or archiving that directory fails a test that has nothing to do with the rename.

Evidence:

- tests/test_workflow_extraction.py:218 asserts a named ideation subdirectory is a directory
- the two instances cycle 2 charged under obligation 7 are both genuinely retired: the wave-conflict test now asserts a non-empty glob with no integer, and the conformance test replaced the named constant with a corpus-derived rglob, which the lens confirmed armed (rglob to glob gave 2 failed / 9 passed)
- this surviving pin sits in unit U4's test, and the plan scopes requirement R33 to units U1 and U2, so it is outside R33's letter

Suggested fix: Replace the named directory with the relation the assertion actually cares about -- that at least one subdirectory under docs/plans survived the move.

## Coverage

- **Suppressed by the confidence-admission rule:** none. Every lens reported at anchor 100.
- **Pre-existing, not charged to this diff:** two — the named directory pin in unit U4's test, and the
  cc-workflows resolution-ladder documentation gap.
- **Not verified here:** the 24-step repository gate, supplied green by the caller; an installed-plugin
  session and a live Workflow-tool launch, so the non-repo-working-directory failure and the
  crash-resume path are reproduced from shipped prose and a clean shell rather than from a real run;
  and the repository's plugin validators against the hypothetical `dependencies` edit.
- **Cross-reviewer agreement:** 45 distinct defects from 65 lens findings. Four lenses independently
  reached the lease-close-out defect, four the envelope-guard defect, four the substrate-surface
  defect, and three the unreadable-path defect.

## Fix routing

Twenty-nine consolidated fix requests, all unresolved: 23 to `review-fixer`, 3 to
`downstream-resolver`, 2 to `release`, 1 to `human`; 15 `manual` and 14 `safe_auto`. Grouping follows
`consolidate_fix_requests`, which groups only active, non-pre-existing, non-advisory findings sharing
an owner, a class, and overlapping paths.

If this work is picked up again, the residual set above is ordered by leverage: Group A first (three
defects this repair created, one of which stops a shipped protocol), then the single missing prose
parity pin in Group C, which is the mechanism that let false prose survive all three cycles.

## Boundary

This review mutated no reviewed source. `git diff 053ef438 HEAD -- plugins/ tests/ scripts/
.claude-plugin/` is empty. No version or release surface changed. Nothing was pushed, no pull request
was opened or updated, no merge was performed, and no GitHub issue, comment, label, or project field
was touched. The only durable writes are this artifact and its evidence-ledger copy.

## Typed result

The complete `review_result.v1` payload follows. `outcome` is its only decision field, and
`require_resume_transition("continue_with_best_available")` was validated against it.

```json
{
  "attempted_lenses": [
    "architecture-maintainability",
    "correctness",
    "security",
    "testing",
    "api-contract",
    "agent-usability",
    "documentation-clarity"
  ],
  "best_available_revision": "053ef43881c2db7d7cee64845e5563a5b73eb43e",
  "collection_operation": {
    "operation": "collect",
    "schema": "review_result.v1"
  },
  "cycle_history": [
    {
      "attempted_lenses": [
        "architecture-maintainability",
        "correctness",
        "security",
        "testing",
        "api-contract",
        "agent-usability",
        "documentation-clarity"
      ],
      "cycle": 1,
      "delta_checks": [],
      "failing_lenses": [
        "architecture-maintainability",
        "correctness",
        "security",
        "testing",
        "api-contract",
        "agent-usability",
        "documentation-clarity"
      ],
      "lens_results": [
        {
          "accepted": false,
          "applicable_dimensions": {
            "architectural-fit-ownership-single-sources": 7.0,
            "conventions-portability-configuration": 7.5,
            "dependency-direction": 7.5,
            "readability-naming-error-contracts": 8.5,
            "separation-of-concerns": 7.5,
            "significant-decision-documentation": 7.0,
            "simplicity-abstraction-duplication-changeability": 7.0
          },
          "cycle": 1,
          "delta_check": null,
          "derived_overall": 7.428571428571429,
          "failing_dimensions": [],
          "lens_id": "architecture-maintainability",
          "non_applicable_dimensions": {},
          "reviewed_revision": "5ec8ea7682706aa9f06e359c373cfd2032ee6ba9",
          "score_accepted": false,
          "scoring_findings": [
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "architectural-fit-ownership-single-sources",
              "finding_id": "F04",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "architectural-fit-ownership-single-sources",
              "finding_id": "F06",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "separation-of-concerns",
              "finding_id": "F09",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "dependency-direction",
              "finding_id": "F10",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "simplicity-abstraction-duplication-changeability",
              "finding_id": "F11",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "conventions-portability-configuration",
              "finding_id": "F12",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "significant-decision-documentation",
              "finding_id": "F13",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "readability-naming-error-contracts",
              "finding_id": "F19",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "conventions-portability-configuration",
              "finding_id": "F20",
              "priority": "P3",
              "resolved": false
            }
          ]
        },
        {
          "accepted": false,
          "applicable_dimensions": {
            "boundary-types-serialization-numeric-time": 9.0,
            "caller-enum-consumer-completeness": 8.0,
            "intent-behavior-completeness": 8.0,
            "side-effects-errors-resource-lifecycle": 8.0,
            "state-data-invariants-transactions-concurrency": 9.0
          },
          "cycle": 1,
          "delta_check": null,
          "derived_overall": 8.4,
          "failing_dimensions": [],
          "lens_id": "correctness",
          "non_applicable_dimensions": {},
          "reviewed_revision": "5ec8ea7682706aa9f06e359c373cfd2032ee6ba9",
          "score_accepted": false,
          "scoring_findings": [
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "caller-enum-consumer-completeness",
              "finding_id": "F02c",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 75,
              "critical": false,
              "dimension_id": "intent-behavior-completeness",
              "finding_id": "F03c",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "side-effects-errors-resource-lifecycle",
              "finding_id": "F05",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "intent-behavior-completeness",
              "finding_id": "F07",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "caller-enum-consumer-completeness",
              "finding_id": "F14",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "boundary-types-serialization-numeric-time",
              "finding_id": "F21",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "caller-enum-consumer-completeness",
              "finding_id": "F22",
              "priority": "P3",
              "resolved": false
            }
          ]
        },
        {
          "accepted": false,
          "applicable_dimensions": {
            "authentication-authorization-tenant-isolation": 7.0,
            "confidentiality-logs-errors-egress": 8.0,
            "dependency-supply-chain": 8.0,
            "input-trust-boundaries-injection": 7.0
          },
          "cycle": 1,
          "delta_check": null,
          "derived_overall": 7.5,
          "failing_dimensions": [],
          "lens_id": "security",
          "non_applicable_dimensions": {
            "secrets-cryptography-session-handling": "the diff introduces no secret material, credential, session, token issuance, or encryption; the only primitive is hashlib.sha256 used as a content digest for spec identity, moved byte-identically from the merge base and not a security control"
          },
          "reviewed_revision": "5ec8ea7682706aa9f06e359c373cfd2032ee6ba9",
          "score_accepted": false,
          "scoring_findings": [
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "authentication-authorization-tenant-isolation",
              "finding_id": "F03",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "input-trust-boundaries-injection",
              "finding_id": "F08",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "input-trust-boundaries-injection",
              "finding_id": "F15",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "input-trust-boundaries-injection",
              "finding_id": "F23",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "confidentiality-logs-errors-egress",
              "finding_id": "F24",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "dependency-supply-chain",
              "finding_id": "F25",
              "priority": "P3",
              "resolved": false
            }
          ]
        },
        {
          "accepted": false,
          "applicable_dimensions": {
            "behavior-sensitive-assertions": 4.0,
            "determinism-isolation-diagnostics-maintainability": 7.0,
            "negative-edge-state-concurrency-time": 8.0,
            "realistic-seams-mocks-integration-evidence": 4.0,
            "requirements-regression-coverage": 5.0
          },
          "cycle": 1,
          "delta_check": null,
          "derived_overall": 5.6,
          "failing_dimensions": [
            "requirements-regression-coverage",
            "behavior-sensitive-assertions",
            "realistic-seams-mocks-integration-evidence"
          ],
          "lens_id": "testing",
          "non_applicable_dimensions": {},
          "reviewed_revision": "5ec8ea7682706aa9f06e359c373cfd2032ee6ba9",
          "score_accepted": false,
          "scoring_findings": [
            {
              "confidence": 100,
              "critical": true,
              "dimension_id": "requirements-regression-coverage",
              "finding_id": "F01",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": true,
              "dimension_id": "behavior-sensitive-assertions",
              "finding_id": "F02",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "realistic-seams-mocks-integration-evidence",
              "finding_id": "F04t",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": true,
              "dimension_id": "realistic-seams-mocks-integration-evidence",
              "finding_id": "F06t",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "realistic-seams-mocks-integration-evidence",
              "finding_id": "F16",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "behavior-sensitive-assertions",
              "finding_id": "F17",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "requirements-regression-coverage",
              "finding_id": "F18",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "behavior-sensitive-assertions",
              "finding_id": "F26",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "behavior-sensitive-assertions",
              "finding_id": "F27",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "determinism-isolation-diagnostics-maintainability",
              "finding_id": "F28",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "requirements-regression-coverage",
              "finding_id": "F29",
              "priority": "P3",
              "resolved": false
            }
          ]
        },
        {
          "accepted": false,
          "applicable_dimensions": {
            "interface-contract-compatibility": 7.0,
            "retry-idempotency-semantics": 9.0,
            "sdk-generated-client-impact": 9.0,
            "serialization-errors": 6.0,
            "specification-documentation-parity": 7.0,
            "versioning-deprecation": 7.0
          },
          "cycle": 1,
          "delta_check": null,
          "derived_overall": 7.5,
          "failing_dimensions": [
            "serialization-errors"
          ],
          "lens_id": "api-contract",
          "non_applicable_dimensions": {
            "pagination-rate-limits": "no HTTP paging or throttling surface exists in this repository; the nearest analogue, agent-spawn concurrency, moved with the emitter and its drift guard followed it"
          },
          "reviewed_revision": "5ec8ea7682706aa9f06e359c373cfd2032ee6ba9",
          "score_accepted": false,
          "scoring_findings": [
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "specification-documentation-parity",
              "finding_id": "F07a",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "serialization-errors",
              "finding_id": "F08a",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "interface-contract-compatibility",
              "finding_id": "F10a",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "interface-contract-compatibility",
              "finding_id": "F14a",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "specification-documentation-parity",
              "finding_id": "F21a",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "serialization-errors",
              "finding_id": "F30",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "versioning-deprecation",
              "finding_id": "F31",
              "priority": "P2",
              "resolved": false
            }
          ]
        },
        {
          "accepted": false,
          "applicable_dimensions": {
            "capability-parity-reachability": 4.0,
            "context-constraints-acceptance-examples": 6.0,
            "discoverability-invocation-schemas": 6.0,
            "machine-readable-output-actionable-errors": 6.0,
            "safe-bounded-idempotent-resumable-context-cost": 8.0
          },
          "cycle": 1,
          "delta_check": null,
          "derived_overall": 6.0,
          "failing_dimensions": [
            "capability-parity-reachability",
            "discoverability-invocation-schemas",
            "context-constraints-acceptance-examples",
            "machine-readable-output-actionable-errors"
          ],
          "lens_id": "agent-usability",
          "non_applicable_dimensions": {},
          "reviewed_revision": "5ec8ea7682706aa9f06e359c373cfd2032ee6ba9",
          "score_accepted": false,
          "scoring_findings": [
            {
              "confidence": 100,
              "critical": true,
              "dimension_id": "capability-parity-reachability",
              "finding_id": "F02u",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "machine-readable-output-actionable-errors",
              "finding_id": "F05u",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "context-constraints-acceptance-examples",
              "finding_id": "F07u",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "context-constraints-acceptance-examples",
              "finding_id": "F32",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "discoverability-invocation-schemas",
              "finding_id": "F33",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "discoverability-invocation-schemas",
              "finding_id": "F34",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "discoverability-invocation-schemas",
              "finding_id": "F35",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "machine-readable-output-actionable-errors",
              "finding_id": "F36",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 75,
              "critical": false,
              "dimension_id": "context-constraints-acceptance-examples",
              "finding_id": "F37",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 75,
              "critical": false,
              "dimension_id": "safe-bounded-idempotent-resumable-context-cost",
              "finding_id": "F38",
              "priority": "P3",
              "resolved": false
            }
          ]
        },
        {
          "accepted": false,
          "applicable_dimensions": {
            "completeness-audience-prerequisites": 6.0,
            "runbook-safety-rollback-links-generated-drift": 5.0,
            "runnable-examples-actionability": 7.0,
            "shipped-behavior-parity": 4.0,
            "structure-navigation": 7.0,
            "terminology-cross-document-consistency": 7.0
          },
          "cycle": 1,
          "delta_check": null,
          "derived_overall": 6.0,
          "failing_dimensions": [
            "shipped-behavior-parity",
            "completeness-audience-prerequisites",
            "runbook-safety-rollback-links-generated-drift"
          ],
          "lens_id": "documentation-clarity",
          "non_applicable_dimensions": {},
          "reviewed_revision": "5ec8ea7682706aa9f06e359c373cfd2032ee6ba9",
          "score_accepted": false,
          "scoring_findings": [
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "runnable-examples-actionability",
              "finding_id": "F02d",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": true,
              "dimension_id": "shipped-behavior-parity",
              "finding_id": "F05d",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "terminology-cross-document-consistency",
              "finding_id": "F06d",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": true,
              "dimension_id": "shipped-behavior-parity",
              "finding_id": "F07d",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "runbook-safety-rollback-links-generated-drift",
              "finding_id": "F09d",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "completeness-audience-prerequisites",
              "finding_id": "F13d",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "shipped-behavior-parity",
              "finding_id": "F19d",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "completeness-audience-prerequisites",
              "finding_id": "F20d",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "structure-navigation",
              "finding_id": "F35d",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "runbook-safety-rollback-links-generated-drift",
              "finding_id": "F39",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "structure-navigation",
              "finding_id": "F40",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "terminology-cross-document-consistency",
              "finding_id": "F41",
              "priority": "P3",
              "resolved": false
            }
          ]
        }
      ],
      "revision": "5ec8ea7682706aa9f06e359c373cfd2032ee6ba9",
      "unresolved_fix_ids": [
        "fix-cdedfbeff16d",
        "fix-47d14d72de14",
        "fix-30b14aa8860e",
        "fix-1e32f8de29bc",
        "fix-14dcdc14fb95",
        "fix-d4838903cdba",
        "fix-f6635448f785",
        "fix-ea8359027302",
        "fix-c77fb632f03a",
        "fix-07564e57d245",
        "fix-f21fbcdde228",
        "fix-4da2d62e8302",
        "fix-1ae49b5c69f0",
        "fix-0e28b4be689a",
        "fix-7bbe44049715",
        "fix-a2b3dcd68eb8",
        "fix-1a0d08a0aa66",
        "fix-3d055db303b8",
        "fix-4d72b7bf33e2",
        "fix-176784886a82",
        "fix-e28b316be7df",
        "fix-a6614db521d4",
        "fix-682af25ab42f",
        "fix-0ddffb195d12",
        "fix-0dd7e9a29e05",
        "fix-f1f46aac5b08",
        "fix-16799de10934",
        "fix-59c7c02e9c83",
        "fix-fb69a7a42548"
      ]
    },
    {
      "attempted_lenses": [
        "architecture-maintainability",
        "correctness",
        "security",
        "testing",
        "api-contract",
        "agent-usability",
        "documentation-clarity"
      ],
      "cycle": 2,
      "delta_checks": [],
      "failing_lenses": [
        "architecture-maintainability",
        "correctness",
        "security",
        "testing",
        "api-contract",
        "agent-usability",
        "documentation-clarity"
      ],
      "lens_results": [
        {
          "accepted": false,
          "applicable_dimensions": {
            "architectural-fit-ownership-single-sources": 5.5,
            "conventions-portability-configuration": 4.5,
            "dependency-direction": 4.0,
            "readability-naming-error-contracts": 5.0,
            "separation-of-concerns": 5.0,
            "significant-decision-documentation": 6.0,
            "simplicity-abstraction-duplication-changeability": 4.5
          },
          "cycle": 2,
          "delta_check": null,
          "derived_overall": 4.928571428571429,
          "failing_dimensions": [
            "architectural-fit-ownership-single-sources",
            "separation-of-concerns",
            "dependency-direction",
            "simplicity-abstraction-duplication-changeability",
            "readability-naming-error-contracts",
            "conventions-portability-configuration",
            "significant-decision-documentation"
          ],
          "lens_id": "architecture-maintainability",
          "non_applicable_dimensions": {},
          "reviewed_revision": "76533cbeba4007cb89e9acf5842027d24cda99de",
          "score_accepted": false,
          "scoring_findings": [
            {
              "confidence": 100,
              "critical": true,
              "dimension_id": "conventions-portability-configuration",
              "finding_id": "A01",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "simplicity-abstraction-duplication-changeability",
              "finding_id": "A02",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "dependency-direction",
              "finding_id": "A03",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "separation-of-concerns",
              "finding_id": "A04",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "separation-of-concerns",
              "finding_id": "A05",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "readability-naming-error-contracts",
              "finding_id": "A06",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "architectural-fit-ownership-single-sources",
              "finding_id": "A07",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "conventions-portability-configuration",
              "finding_id": "A08",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "significant-decision-documentation",
              "finding_id": "A09",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "dependency-direction",
              "finding_id": "A10",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "dependency-direction",
              "finding_id": "A11",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "readability-naming-error-contracts",
              "finding_id": "A12",
              "priority": "P3",
              "resolved": false
            }
          ]
        },
        {
          "accepted": false,
          "applicable_dimensions": {
            "boundary-types-serialization-numeric-time": 7.0,
            "caller-enum-consumer-completeness": 7.0,
            "intent-behavior-completeness": 6.5,
            "side-effects-errors-resource-lifecycle": 6.0,
            "state-data-invariants-transactions-concurrency": 7.5
          },
          "cycle": 2,
          "delta_check": null,
          "derived_overall": 6.8,
          "failing_dimensions": [
            "intent-behavior-completeness",
            "side-effects-errors-resource-lifecycle"
          ],
          "lens_id": "correctness",
          "non_applicable_dimensions": {},
          "reviewed_revision": "76533cbeba4007cb89e9acf5842027d24cda99de",
          "score_accepted": false,
          "scoring_findings": [
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "side-effects-errors-resource-lifecycle",
              "finding_id": "C01",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "side-effects-errors-resource-lifecycle",
              "finding_id": "C02",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "intent-behavior-completeness",
              "finding_id": "C03",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "caller-enum-consumer-completeness",
              "finding_id": "C04",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "caller-enum-consumer-completeness",
              "finding_id": "C05",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "state-data-invariants-transactions-concurrency",
              "finding_id": "C06",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "boundary-types-serialization-numeric-time",
              "finding_id": "C07",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "boundary-types-serialization-numeric-time",
              "finding_id": "C08",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "side-effects-errors-resource-lifecycle",
              "finding_id": "C09",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "side-effects-errors-resource-lifecycle",
              "finding_id": "C10",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "intent-behavior-completeness",
              "finding_id": "C11",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "boundary-types-serialization-numeric-time",
              "finding_id": "C12",
              "priority": "P3",
              "resolved": false
            }
          ]
        },
        {
          "accepted": false,
          "applicable_dimensions": {
            "authentication-authorization-tenant-isolation": 8.5,
            "confidentiality-logs-errors-egress": 7.5,
            "dependency-supply-chain": 7.0,
            "input-trust-boundaries-injection": 7.0
          },
          "cycle": 2,
          "delta_check": null,
          "derived_overall": 7.5,
          "failing_dimensions": [],
          "lens_id": "security",
          "non_applicable_dimensions": {
            "secrets-cryptography-session-handling": "no secret material, credential, session issuance or cryptographic control is introduced; the only primitive is hashlib.sha256 as a spec-identity content digest, and the one session-adjacent surface (--session-id threaded into reserve/attest) is a byte-identical move writing only to git-ignored .saga/"
          },
          "reviewed_revision": "76533cbeba4007cb89e9acf5842027d24cda99de",
          "score_accepted": false,
          "scoring_findings": [
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "input-trust-boundaries-injection",
              "finding_id": "S01",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "confidentiality-logs-errors-egress",
              "finding_id": "S02",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "input-trust-boundaries-injection",
              "finding_id": "S03",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "dependency-supply-chain",
              "finding_id": "S04",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "input-trust-boundaries-injection",
              "finding_id": "S05",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "authentication-authorization-tenant-isolation",
              "finding_id": "S06",
              "priority": "P3",
              "resolved": false
            }
          ]
        },
        {
          "accepted": false,
          "applicable_dimensions": {
            "behavior-sensitive-assertions": 6.5,
            "determinism-isolation-diagnostics-maintainability": 7.5,
            "negative-edge-state-concurrency-time": 8.0,
            "realistic-seams-mocks-integration-evidence": 7.5,
            "requirements-regression-coverage": 7.0
          },
          "cycle": 2,
          "delta_check": null,
          "derived_overall": 7.3,
          "failing_dimensions": [
            "behavior-sensitive-assertions"
          ],
          "lens_id": "testing",
          "non_applicable_dimensions": {},
          "reviewed_revision": "76533cbeba4007cb89e9acf5842027d24cda99de",
          "score_accepted": false,
          "scoring_findings": [
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "behavior-sensitive-assertions",
              "finding_id": "T01",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "requirements-regression-coverage",
              "finding_id": "T02",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "requirements-regression-coverage",
              "finding_id": "T03",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "realistic-seams-mocks-integration-evidence",
              "finding_id": "T04",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "behavior-sensitive-assertions",
              "finding_id": "T05",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "requirements-regression-coverage",
              "finding_id": "T06",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "determinism-isolation-diagnostics-maintainability",
              "finding_id": "T07",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "requirements-regression-coverage",
              "finding_id": "T08",
              "priority": "P3",
              "resolved": false
            }
          ]
        },
        {
          "accepted": false,
          "applicable_dimensions": {
            "interface-contract-compatibility": 6.5,
            "retry-idempotency-semantics": 6.0,
            "sdk-generated-client-impact": 7.5,
            "serialization-errors": 6.0,
            "specification-documentation-parity": 6.0,
            "versioning-deprecation": 7.5
          },
          "cycle": 2,
          "delta_check": null,
          "derived_overall": 6.583333333333333,
          "failing_dimensions": [
            "interface-contract-compatibility",
            "serialization-errors",
            "retry-idempotency-semantics",
            "specification-documentation-parity"
          ],
          "lens_id": "api-contract",
          "non_applicable_dimensions": {
            "pagination-rate-limits": "the change adds no paged collection, cursor, quota or throttled interface; the one collection surface (check_plan_corpus, a sorted rglob over a local directory) is deterministic, complete, and has no client-visible ordering or limit contract"
          },
          "reviewed_revision": "76533cbeba4007cb89e9acf5842027d24cda99de",
          "score_accepted": false,
          "scoring_findings": [
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "retry-idempotency-semantics",
              "finding_id": "P01",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": true,
              "dimension_id": "interface-contract-compatibility",
              "finding_id": "P02",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "interface-contract-compatibility",
              "finding_id": "P03",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "serialization-errors",
              "finding_id": "P04",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "serialization-errors",
              "finding_id": "P05",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "serialization-errors",
              "finding_id": "P06",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "serialization-errors",
              "finding_id": "P07",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "specification-documentation-parity",
              "finding_id": "P08",
              "priority": "P2",
              "resolved": false
            }
          ]
        },
        {
          "accepted": false,
          "applicable_dimensions": {
            "capability-parity-reachability": 6.0,
            "context-constraints-acceptance-examples": 6.5,
            "discoverability-invocation-schemas": 6.0,
            "machine-readable-output-actionable-errors": 6.0,
            "safe-bounded-idempotent-resumable-context-cost": 5.5
          },
          "cycle": 2,
          "delta_check": null,
          "derived_overall": 6.0,
          "failing_dimensions": [
            "capability-parity-reachability",
            "discoverability-invocation-schemas",
            "context-constraints-acceptance-examples",
            "machine-readable-output-actionable-errors",
            "safe-bounded-idempotent-resumable-context-cost"
          ],
          "lens_id": "agent-usability",
          "non_applicable_dimensions": {},
          "reviewed_revision": "76533cbeba4007cb89e9acf5842027d24cda99de",
          "score_accepted": false,
          "scoring_findings": [
            {
              "confidence": 100,
              "critical": true,
              "dimension_id": "safe-bounded-idempotent-resumable-context-cost",
              "finding_id": "U01",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "capability-parity-reachability",
              "finding_id": "U02",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": true,
              "dimension_id": "machine-readable-output-actionable-errors",
              "finding_id": "U03",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": true,
              "dimension_id": "capability-parity-reachability",
              "finding_id": "U04",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "context-constraints-acceptance-examples",
              "finding_id": "U05",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": true,
              "dimension_id": "context-constraints-acceptance-examples",
              "finding_id": "U06",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "capability-parity-reachability",
              "finding_id": "U07",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "discoverability-invocation-schemas",
              "finding_id": "U08",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": true,
              "dimension_id": "safe-bounded-idempotent-resumable-context-cost",
              "finding_id": "U09",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "discoverability-invocation-schemas",
              "finding_id": "U10",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "discoverability-invocation-schemas",
              "finding_id": "U11",
              "priority": "P3",
              "resolved": false
            }
          ]
        },
        {
          "accepted": false,
          "applicable_dimensions": {
            "completeness-audience-prerequisites": 7.5,
            "runbook-safety-rollback-links-generated-drift": 5.5,
            "runnable-examples-actionability": 8.0,
            "shipped-behavior-parity": 5.5,
            "structure-navigation": 8.5,
            "terminology-cross-document-consistency": 6.5
          },
          "cycle": 2,
          "delta_check": null,
          "derived_overall": 6.916666666666667,
          "failing_dimensions": [
            "shipped-behavior-parity",
            "terminology-cross-document-consistency",
            "runbook-safety-rollback-links-generated-drift"
          ],
          "lens_id": "documentation-clarity",
          "non_applicable_dimensions": {},
          "reviewed_revision": "76533cbeba4007cb89e9acf5842027d24cda99de",
          "score_accepted": false,
          "scoring_findings": [
            {
              "confidence": 100,
              "critical": true,
              "dimension_id": "shipped-behavior-parity",
              "finding_id": "D01",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": true,
              "dimension_id": "shipped-behavior-parity",
              "finding_id": "D02",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": true,
              "dimension_id": "runbook-safety-rollback-links-generated-drift",
              "finding_id": "D03",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": true,
              "dimension_id": "shipped-behavior-parity",
              "finding_id": "D04",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": true,
              "dimension_id": "runbook-safety-rollback-links-generated-drift",
              "finding_id": "D05",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "runbook-safety-rollback-links-generated-drift",
              "finding_id": "D06",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "runbook-safety-rollback-links-generated-drift",
              "finding_id": "D07",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "shipped-behavior-parity",
              "finding_id": "D08",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "terminology-cross-document-consistency",
              "finding_id": "D09",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "completeness-audience-prerequisites",
              "finding_id": "D10",
              "priority": "P3",
              "resolved": false
            }
          ]
        }
      ],
      "revision": "76533cbeba4007cb89e9acf5842027d24cda99de",
      "unresolved_fix_ids": [
        "fix-8f87c9f3fa94",
        "fix-c77192119e7b",
        "fix-a34ff0c91932",
        "fix-35e0c83d365a",
        "fix-222ac29adc40",
        "fix-9a088bef2da2",
        "fix-8e3aec8e83c2",
        "fix-f0a36e7e26f8",
        "fix-a69fd443ef72",
        "fix-c1ecbf4f719a",
        "fix-9818846b9df7",
        "fix-2e198411f792",
        "fix-170084318624",
        "fix-3c9e1cd3a093",
        "fix-1db694550386",
        "fix-f03ab7a6f650",
        "fix-f78699abc585",
        "fix-ac87c3d71a22",
        "fix-4c0030371644",
        "fix-8a63bd53812c",
        "fix-5d21ac319010",
        "fix-9e055d1381da",
        "fix-64c523292cb9",
        "fix-1dca06ef0b96",
        "fix-cbe0f53498e0",
        "fix-b6525c38e39a",
        "fix-c4fbecfc8247",
        "fix-6cffb84cfd8a",
        "fix-8cc4f3f1ff3c"
      ]
    },
    {
      "attempted_lenses": [
        "architecture-maintainability",
        "correctness",
        "security",
        "testing",
        "api-contract",
        "agent-usability",
        "documentation-clarity"
      ],
      "cycle": 3,
      "delta_checks": [],
      "failing_lenses": [
        "architecture-maintainability",
        "correctness",
        "security",
        "testing",
        "api-contract",
        "agent-usability",
        "documentation-clarity"
      ],
      "lens_results": [
        {
          "accepted": false,
          "applicable_dimensions": {
            "architectural-fit-ownership-single-sources": 5.5,
            "conventions-portability-configuration": 6.0,
            "dependency-direction": 5.5,
            "readability-naming-error-contracts": 4.5,
            "separation-of-concerns": 5.5,
            "significant-decision-documentation": 4.5,
            "simplicity-abstraction-duplication-changeability": 5.0
          },
          "cycle": 3,
          "delta_check": null,
          "derived_overall": 5.214285714285714,
          "failing_dimensions": [
            "architectural-fit-ownership-single-sources",
            "separation-of-concerns",
            "dependency-direction",
            "simplicity-abstraction-duplication-changeability",
            "readability-naming-error-contracts",
            "conventions-portability-configuration",
            "significant-decision-documentation"
          ],
          "lens_id": "architecture-maintainability",
          "non_applicable_dimensions": {},
          "reviewed_revision": "053ef43881c2db7d7cee64845e5563a5b73eb43e",
          "score_accepted": false,
          "scoring_findings": [
            {
              "confidence": 100,
              "critical": true,
              "dimension_id": "readability-naming-error-contracts",
              "finding_id": "W01",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": true,
              "dimension_id": "conventions-portability-configuration",
              "finding_id": "W02",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": true,
              "dimension_id": "simplicity-abstraction-duplication-changeability",
              "finding_id": "W03",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "architectural-fit-ownership-single-sources",
              "finding_id": "W04",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "significant-decision-documentation",
              "finding_id": "W05",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "readability-naming-error-contracts",
              "finding_id": "W06",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "separation-of-concerns",
              "finding_id": "W07",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "significant-decision-documentation",
              "finding_id": "W08",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "readability-naming-error-contracts",
              "finding_id": "W09",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "readability-naming-error-contracts",
              "finding_id": "W10",
              "priority": "P3",
              "resolved": false
            }
          ]
        },
        {
          "accepted": false,
          "applicable_dimensions": {
            "boundary-types-serialization-numeric-time": 5.5,
            "caller-enum-consumer-completeness": 6.5,
            "intent-behavior-completeness": 7.0,
            "side-effects-errors-resource-lifecycle": 7.0,
            "state-data-invariants-transactions-concurrency": 6.5
          },
          "cycle": 3,
          "delta_check": null,
          "derived_overall": 6.5,
          "failing_dimensions": [
            "state-data-invariants-transactions-concurrency",
            "boundary-types-serialization-numeric-time",
            "caller-enum-consumer-completeness"
          ],
          "lens_id": "correctness",
          "non_applicable_dimensions": {},
          "reviewed_revision": "053ef43881c2db7d7cee64845e5563a5b73eb43e",
          "score_accepted": false,
          "scoring_findings": [
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "side-effects-errors-resource-lifecycle",
              "finding_id": "X01",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "caller-enum-consumer-completeness",
              "finding_id": "X02",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "state-data-invariants-transactions-concurrency",
              "finding_id": "X03",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "intent-behavior-completeness",
              "finding_id": "X04",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "intent-behavior-completeness",
              "finding_id": "X05",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "caller-enum-consumer-completeness",
              "finding_id": "X06",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "state-data-invariants-transactions-concurrency",
              "finding_id": "X07",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "boundary-types-serialization-numeric-time",
              "finding_id": "X08",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "boundary-types-serialization-numeric-time",
              "finding_id": "X09",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "side-effects-errors-resource-lifecycle",
              "finding_id": "X10",
              "priority": "P3",
              "resolved": false
            }
          ]
        },
        {
          "accepted": false,
          "applicable_dimensions": {
            "authentication-authorization-tenant-isolation": 7.5,
            "confidentiality-logs-errors-egress": 7.5,
            "dependency-supply-chain": 7.0,
            "input-trust-boundaries-injection": 8.0
          },
          "cycle": 3,
          "delta_check": null,
          "derived_overall": 7.5,
          "failing_dimensions": [],
          "lens_id": "security",
          "non_applicable_dimensions": {
            "secrets-cryptography-session-handling": "the change introduces no secret material, credential, session issuance or cryptographic control; the only primitive is a content digest carried over unchanged, and uuidgen mints a correlation id rather than an authorization token"
          },
          "reviewed_revision": "053ef43881c2db7d7cee64845e5563a5b73eb43e",
          "score_accepted": false,
          "scoring_findings": [
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "confidentiality-logs-errors-egress",
              "finding_id": "V01",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "authentication-authorization-tenant-isolation",
              "finding_id": "V02",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "input-trust-boundaries-injection",
              "finding_id": "V03",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "input-trust-boundaries-injection",
              "finding_id": "V04",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "input-trust-boundaries-injection",
              "finding_id": "V05",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "confidentiality-logs-errors-egress",
              "finding_id": "V06",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "dependency-supply-chain",
              "finding_id": "V07",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "authentication-authorization-tenant-isolation",
              "finding_id": "V08",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "input-trust-boundaries-injection",
              "finding_id": "V09",
              "priority": "P3",
              "resolved": false
            }
          ]
        },
        {
          "accepted": false,
          "applicable_dimensions": {
            "behavior-sensitive-assertions": 6.5,
            "determinism-isolation-diagnostics-maintainability": 7.0,
            "negative-edge-state-concurrency-time": 7.0,
            "realistic-seams-mocks-integration-evidence": 7.5,
            "requirements-regression-coverage": 6.5
          },
          "cycle": 3,
          "delta_check": null,
          "derived_overall": 6.9,
          "failing_dimensions": [
            "requirements-regression-coverage",
            "behavior-sensitive-assertions"
          ],
          "lens_id": "testing",
          "non_applicable_dimensions": {},
          "reviewed_revision": "053ef43881c2db7d7cee64845e5563a5b73eb43e",
          "score_accepted": false,
          "scoring_findings": [
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "negative-edge-state-concurrency-time",
              "finding_id": "Z01",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "requirements-regression-coverage",
              "finding_id": "Z02",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "behavior-sensitive-assertions",
              "finding_id": "Z03",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "determinism-isolation-diagnostics-maintainability",
              "finding_id": "Z04",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "realistic-seams-mocks-integration-evidence",
              "finding_id": "Z05",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "requirements-regression-coverage",
              "finding_id": "Z06",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "negative-edge-state-concurrency-time",
              "finding_id": "Z07",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "behavior-sensitive-assertions",
              "finding_id": "Z08",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "requirements-regression-coverage",
              "finding_id": "Z09",
              "priority": "P3",
              "resolved": false
            }
          ]
        },
        {
          "accepted": false,
          "applicable_dimensions": {
            "interface-contract-compatibility": 6.0,
            "retry-idempotency-semantics": 8.5,
            "sdk-generated-client-impact": 7.0,
            "serialization-errors": 5.5,
            "specification-documentation-parity": 6.5,
            "versioning-deprecation": 7.0
          },
          "cycle": 3,
          "delta_check": null,
          "derived_overall": 6.75,
          "failing_dimensions": [
            "interface-contract-compatibility",
            "serialization-errors",
            "specification-documentation-parity"
          ],
          "lens_id": "api-contract",
          "non_applicable_dimensions": {
            "pagination-rate-limits": "no paged collection, cursor, quota or throttled interface exists anywhere in this change; the nearest analogue, agent-spawn concurrency, moved with the emitter in unit U4 and is unchanged at this revision"
          },
          "reviewed_revision": "053ef43881c2db7d7cee64845e5563a5b73eb43e",
          "score_accepted": false,
          "scoring_findings": [
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "interface-contract-compatibility",
              "finding_id": "Q01",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "interface-contract-compatibility",
              "finding_id": "Q02",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "interface-contract-compatibility",
              "finding_id": "Q03",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "serialization-errors",
              "finding_id": "Q04",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "serialization-errors",
              "finding_id": "Q05",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "specification-documentation-parity",
              "finding_id": "Q06",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "serialization-errors",
              "finding_id": "Q07",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "serialization-errors",
              "finding_id": "Q08",
              "priority": "P3",
              "resolved": false
            }
          ]
        },
        {
          "accepted": false,
          "applicable_dimensions": {
            "capability-parity-reachability": 6.5,
            "context-constraints-acceptance-examples": 7.5,
            "discoverability-invocation-schemas": 6.0,
            "machine-readable-output-actionable-errors": 7.5,
            "safe-bounded-idempotent-resumable-context-cost": 6.5
          },
          "cycle": 3,
          "delta_check": null,
          "derived_overall": 6.8,
          "failing_dimensions": [
            "capability-parity-reachability",
            "discoverability-invocation-schemas",
            "safe-bounded-idempotent-resumable-context-cost"
          ],
          "lens_id": "agent-usability",
          "non_applicable_dimensions": {},
          "reviewed_revision": "053ef43881c2db7d7cee64845e5563a5b73eb43e",
          "score_accepted": false,
          "scoring_findings": [
            {
              "confidence": 100,
              "critical": true,
              "dimension_id": "safe-bounded-idempotent-resumable-context-cost",
              "finding_id": "Y01",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "machine-readable-output-actionable-errors",
              "finding_id": "Y02",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "context-constraints-acceptance-examples",
              "finding_id": "Y03",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "discoverability-invocation-schemas",
              "finding_id": "Y04",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "discoverability-invocation-schemas",
              "finding_id": "Y05",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "capability-parity-reachability",
              "finding_id": "Y06",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "capability-parity-reachability",
              "finding_id": "Y07",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "discoverability-invocation-schemas",
              "finding_id": "Y08",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "context-constraints-acceptance-examples",
              "finding_id": "Y09",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "safe-bounded-idempotent-resumable-context-cost",
              "finding_id": "Y10",
              "priority": "P3",
              "resolved": false
            }
          ]
        },
        {
          "accepted": false,
          "applicable_dimensions": {
            "completeness-audience-prerequisites": 6.5,
            "runbook-safety-rollback-links-generated-drift": 6.0,
            "runnable-examples-actionability": 6.5,
            "shipped-behavior-parity": 6.0,
            "structure-navigation": 8.0,
            "terminology-cross-document-consistency": 6.0
          },
          "cycle": 3,
          "delta_check": null,
          "derived_overall": 6.5,
          "failing_dimensions": [
            "shipped-behavior-parity",
            "completeness-audience-prerequisites",
            "terminology-cross-document-consistency",
            "runnable-examples-actionability",
            "runbook-safety-rollback-links-generated-drift"
          ],
          "lens_id": "documentation-clarity",
          "non_applicable_dimensions": {},
          "reviewed_revision": "053ef43881c2db7d7cee64845e5563a5b73eb43e",
          "score_accepted": false,
          "scoring_findings": [
            {
              "confidence": 100,
              "critical": true,
              "dimension_id": "terminology-cross-document-consistency",
              "finding_id": "N01",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": true,
              "dimension_id": "shipped-behavior-parity",
              "finding_id": "N02",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": true,
              "dimension_id": "runbook-safety-rollback-links-generated-drift",
              "finding_id": "N03",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": true,
              "dimension_id": "completeness-audience-prerequisites",
              "finding_id": "N04",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "runbook-safety-rollback-links-generated-drift",
              "finding_id": "N05",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "shipped-behavior-parity",
              "finding_id": "N06",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "completeness-audience-prerequisites",
              "finding_id": "N07",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "completeness-audience-prerequisites",
              "finding_id": "N08",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "terminology-cross-document-consistency",
              "finding_id": "N09",
              "priority": "P3",
              "resolved": false
            }
          ]
        }
      ],
      "revision": "053ef43881c2db7d7cee64845e5563a5b73eb43e",
      "unresolved_fix_ids": [
        "fix-b5b1cf54bd9e",
        "fix-9e3a294949a8",
        "fix-77bb21ac351e",
        "fix-640332b3460b",
        "fix-111b3a5ba6bf",
        "fix-e37ed06c14a3",
        "fix-e84d08faaae9",
        "fix-d954059184c4",
        "fix-aeb801cf93a4",
        "fix-2b465af21a75",
        "fix-79b89f62dfaf",
        "fix-884d9322d0b8",
        "fix-52a145d37865",
        "fix-31db917d5077",
        "fix-f6054d24ef3a",
        "fix-87eaea4a209e",
        "fix-052d76cce82b",
        "fix-9e622b08b047",
        "fix-22d6efb8abe2",
        "fix-c0968b07f9e0",
        "fix-f3a3ac0178de",
        "fix-61319972cc18",
        "fix-31f8c6081fcc",
        "fix-5bd1d98b52fb",
        "fix-7ce7e909ff55",
        "fix-e024cd2b6ff4",
        "fix-6667f5be6029",
        "fix-1c0cb019d7a8",
        "fix-24db8e598169"
      ]
    }
  ],
  "evidence_ledger": {
    "criteria": "docs/evidence/adhoc-cp918-saga-plan-improvement/criteria-code-review-5ec8ea7682706aa9f06e359c373cfd2032ee6ba9.json"
  },
  "external_advisory_reviews": [],
  "failing_lenses": [
    "architecture-maintainability",
    "correctness",
    "security",
    "testing",
    "api-contract",
    "agent-usability",
    "documentation-clarity"
  ],
  "findings": [
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "terminology-cross-document-consistency",
      "evidence": [
        "LEARNINGS.md:69 is unchanged by this repair -- the diff to that file is additions only",
        "lens reproduction: forcing the index failure in a scratch repository gave two envelopes before the re-run and three after, and the runtime message now correctly says it appends one additional tick",
        "the exception docstring at plugins/saga/scripts/saga.py:697-701 states the same non-idempotence",
        "carried from cycle 2 finding D06, not addressed"
      ],
      "file": "docs/engineering-journal/LEARNINGS.md",
      "finding_id": "N01",
      "lens_id": "documentation-clarity",
      "line": 69,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P1",
      "status": "active",
      "suggested_fix": "Rewrite the Fix and Mechanism lines of that entry to say the re-run appends one additional tick, and drop or scope the 'all four prose surfaces corrected' sentence.",
      "title": "Journal still records the index re-run as idempotent",
      "touched_paths": [
        "docs/engineering-journal/LEARNINGS.md"
      ],
      "why_it_matters": "The durable learning tells future maintainers the re-run rebuilds the index idempotently and that all four prose surfaces were corrected, so a maintainer reading it would restore the exact false claim the runtime message, the Plan skill and the changelog were just repaired to drop."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "caller-enum-consumer-completeness",
      "evidence": [
        "emitter.py:48-78 lists 29 names with _agent_prompt absent; emitter.py:1348 reads _ES._agent_prompt(spec, retry_unit)",
        "lens proof: _bind_substrate against a stub carrying exactly the 29 declared names and nothing else SUCCEEDED, guard silent",
        "the repair commit 053ef438 does not touch emitter.py at all",
        "controller static confirmation, and four lenses found this independently at cycle 2"
      ],
      "file": "plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py",
      "finding_id": "X06",
      "lens_id": "correctness",
      "line": 48,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P1",
      "status": "active",
      "suggested_fix": "Add _agent_prompt to SUBSTRATE_SURFACE and extend the guard test to walk _ES.<attr> accesses, not just assignments inside _bind_substrate.",
      "title": "SUBSTRATE_SURFACE still omits _agent_prompt",
      "touched_paths": [
        "plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py"
      ],
      "why_it_matters": "The emitter calls _ES._agent_prompt on the escalate-on-signal retry path but never declares it, so _bind_substrate accepts a substrate lacking it and the failure lands as an AttributeError at emit time -- precisely what the guard's docstring says it prevents."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "interface-contract-compatibility",
      "evidence": [
        "the repair commit contains no file under plugins/cc-workflows/ at all",
        "static scan: 29 names declared at emitter.py:48-77 and _agent_prompt is the sole qualified substrate access absent from it",
        "stub proof: a module carrying every declared name and nothing else passed _bind_substrate with no error, leaving the attribute absent; the surface test reports 3 passed with the gap present",
        "nothing breaks at runtime today because the definition exists in Saga",
        "found independently by the correctness, architecture and testing lenses and by the controller; four lenses found it at cycle 2"
      ],
      "file": "plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py",
      "finding_id": "Q01",
      "lens_id": "api-contract",
      "line": 1348,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P1",
      "status": "active",
      "suggested_fix": "Add the name to SUBSTRATE_SURFACE and bind it like the others, and extend the guard test to walk qualified attribute accesses on the substrate module.",
      "title": "Undeclared private Saga name still crosses the plugin boundary",
      "touched_paths": [
        "plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py"
      ],
      "why_it_matters": "_bind_substrate admits a substrate lacking _agent_prompt, so an incompatible Saga binds cleanly and dies with an attribute error at emit time instead of at bind time."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "runbook-safety-rollback-links-generated-drift",
      "evidence": [
        "the 108 lines added to tests/test_plan_pre_answers.py are all behavioural; none references the changelog, the spec or the skill",
        "lens mutation: replacing the repaired changelog sentence with the exact cycle-2 falsehood left 98 tests passing across three modules; restored",
        "carried from cycle 2 finding D07, not addressed"
      ],
      "file": "plugins/saga/CHANGELOG.md",
      "finding_id": "N05",
      "lens_id": "documentation-clarity",
      "line": 7,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P1",
      "status": "active",
      "suggested_fix": "Add the pin cycle 2 specified, in the shape of the existing required-field pin: parse the two-case schema sentence and the inline-only sentence out of all three surfaces and bind them to the module's own constants.",
      "title": "Still no test binds carrier prose to the code",
      "touched_paths": [
        "plugins/saga/CHANGELOG.md"
      ],
      "why_it_matters": "Three documents state the carrier contract and none is bound to the code, which is the mechanism that let two false changelog claims survive cycle 1 and five of cycle 2's ten findings survive cycle 2 -- the gate cannot see a prose regression."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "shipped-behavior-parity",
      "evidence": [
        "saga-spec.md:699-702, plugins/saga/skills/plan/SKILL.md:170-172, and the sentence the repair ADDED at plugins/saga/CHANGELOG.md:14-15 all state the rule the same incomplete way",
        "lens run: an uppercase version token gave exit 2 with the whole-refusal stop",
        "the mechanism is the family test lowercasing at :133-137 while the token comparison at :227 is exact; only the internal docstring names the case correctly",
        "carried from cycle 2 finding D08, not addressed, and now replicated onto a third surface"
      ],
      "file": "plugins/saga/references/saga-spec.md",
      "finding_id": "N06",
      "lens_id": "documentation-clarity",
      "line": 700,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P1",
      "status": "active",
      "suggested_fix": "Add one clause to all three surfaces: the version token itself is matched exactly, so any other casing is inside the family and refused whole.",
      "title": "Case-differing v1 token refused, three surfaces say otherwise",
      "touched_paths": [
        "plugins/saga/references/saga-spec.md"
      ],
      "why_it_matters": "All three surfaces say the family match is case-insensitive and that only a non-v1 token is refused, so a caller writing an uppercase but otherwise correct version token expects it applied and instead gets a whole-carrier refusal calling its own token unrecognised."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "significant-decision-documentation",
      "evidence": [
        "plan_pre_answers.py:48 and plugins/saga/references/saga-spec.md:723; the read is at plan_pre_answers.py:374",
        "the repair edited that very saga-spec line in this commit to append the --established clause and left 'reads no file' in the same sentence",
        "carried from cycle 2 finding A09, not addressed"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "W05",
      "lens_id": "architecture-maintainability",
      "line": 48,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P1",
      "status": "active",
      "suggested_fix": "Replace both sentences with the wording already applied to the emitter docstring: the evaluation functions are pure, the command line reads only the invocation file it is given.",
      "title": "Purity claim still says reads no file",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "Both surfaces still promise the validator reads no file while its documented command line reads one, so a maintainer refactoring for purity will contradict the shipped entry point."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "simplicity-abstraction-duplication-changeability",
      "evidence": [
        "the two functions at plan_pre_answers.py:94-98 and :129-139; the comment at :90-91, the module docstring at :43-45 and saga-spec.md:716-719 all assert they are the same membership test",
        "lens probe: a foreign-family block with a trailing comma returns carrier-shaped True, family-schema False, and stops; the same block well-formed returns no stop",
        "a block whose only family mention is a prose value also stops",
        "the security lens found the mirror evasion: a JSON-escaped family token is admitted by the parsed test but not the raw one"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "W03",
      "lens_id": "architecture-maintainability",
      "line": 94,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P1",
      "status": "active",
      "suggested_fix": "Gate the malformed stop on the block's declared schema token rather than any occurrence of the family name, then delete the equivalence claim or pin it with a test over both functions.",
      "title": "Two family-membership tests that are not the same test",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "_is_carrier_shaped is a raw-text regex over the whole block while _is_family_schema is a prefix test on the parsed schema value, so a foreign-family carrier with a malformed body now stops a Plan run that the same carrier well-formed would silently ignore -- a second, divergent authority over family membership."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "readability-naming-error-contracts",
      "evidence": [
        "saga.py:1709 calls restore(root, incoming.saga_id) and compares prior.plan_path; restore is documented latest-tick-only at :1014-1023 while read_ticks at :1026 is the chain reader",
        "lens reproduction: saved a tick for plan a, then a tick for plan b, made the saga directory read-only and re-saved with plan a -- exit 2 with 'now has NO saga tick referencing it', while the first envelope on disk still records plan a",
        "NEW defect introduced by this repair; complements the correctness lens's normalization finding on the same branch"
      ],
      "file": "plugins/saga/scripts/saga.py",
      "finding_id": "W01",
      "lens_id": "architecture-maintainability",
      "line": 1709,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P1",
      "status": "active",
      "suggested_fix": "Walk read_ticks and test whether ANY tick's plan_path matches, or narrow the message to 'no tick since the last one recorded this plan path'.",
      "title": "Envelope-failure branch checks only the latest tick",
      "touched_paths": [
        "plugins/saga/scripts/saga.py"
      ],
      "why_it_matters": "restore() returns the newest tick only, so a chain whose latest tick names a different plan makes the handler tell the operator a plan document has NO tick referencing it when an earlier tick on disk does."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "runbook-safety-rollback-links-generated-drift",
      "evidence": [
        "saga.py:1712 compares the latest tick's plan path; saga.py:1720 and plugins/saga/skills/plan/SKILL.md:627-630 state the any-earlier-tick claim",
        "lens reproduction: a two-tick chain where the newest names a different plan produced the stranded claim while the first envelope on disk carries the plan path",
        "the new regression test covers only the single-prior-tick same-path case",
        "NEW defect introduced by this repair; found independently by the architecture lens"
      ],
      "file": "plugins/saga/scripts/saga.py",
      "finding_id": "N03",
      "lens_id": "documentation-clarity",
      "line": 1720,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P1",
      "status": "active",
      "suggested_fix": "Scan the tick chain for any tick whose plan path matches instead of reading only the latest, or narrow both prose surfaces to 'the most recent tick'.",
      "title": "Envelope-failure guard checks the latest tick, prose says any earlier",
      "touched_paths": [
        "plugins/saga/scripts/saga.py"
      ],
      "why_it_matters": "The message and the Phase 5.3 runbook both condition on no earlier tick referencing the plan, but the code tests only the latest tick, so a saga whose newest tick names a different plan document is told a tracked plan is stranded."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "readability-naming-error-contracts",
      "evidence": [
        "the read at saga.py:802 precedes both writes at :854 and :860; the generic handler at :1725-1734 is unchanged by this commit",
        "lens reproduction: making the saga directory unreadable then saving gave the write-framed message and the restore prescription, and running that prescribed restore gave a bare traceback with exit 1",
        "carried from cycle 2 finding A06, not addressed"
      ],
      "file": "plugins/saga/scripts/saga.py",
      "finding_id": "W06",
      "lens_id": "architecture-maintainability",
      "line": 1725,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P1",
      "status": "active",
      "suggested_fix": "Wrap the prior-tick read in its own named error, or reword the generic branch and drop the restore prescription from a branch that cannot distinguish read from write.",
      "title": "Generic branch still calls a read failure a write",
      "touched_paths": [
        "plugins/saga/scripts/saga.py"
      ],
      "why_it_matters": "save() reads the prior tick before either write, so a read-side error lands in the generic branch and prints 'failed to write the saga tick' when nothing was written, prescribing a restore that fails identically."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "shipped-behavior-parity",
      "evidence": [
        "plugins/saga/skills/plan/SKILL.md:152-153 and the module docstring at plan_pre_answers.py:337",
        "lens run: the errno prefix alone consumes 37 of the 40 echo characters, so at most one path character ever survives",
        "the guard at tests/test_plan_pre_answers.py:498 asserts only that the word appears, never the path",
        "NEW false claim introduced by this repair; found independently by the correctness and agent-usability lenses"
      ],
      "file": "plugins/saga/skills/plan/SKILL.md",
      "finding_id": "N02",
      "lens_id": "documentation-clarity",
      "line": 153,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P1",
      "status": "active",
      "suggested_fix": "Interpolate the path outside the bounded echo, or delete the naming promise from both surfaces.",
      "title": "Unreadable-file stop does not name the path",
      "touched_paths": [
        "plugins/saga/skills/plan/SKILL.md"
      ],
      "why_it_matters": "Two surfaces added by this repair promise the stop names the unreadable path, but the forty-character echo budget truncates the message before the path can appear, so an agent told to surface the path has nothing to surface."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "conventions-portability-configuration",
      "evidence": [
        "work/SKILL.md:428 and the placeholders at :433 and :445",
        "lens measurement: enumerating the Saga dataclass fields lists 48, none for a workflow invocation id; saga.py save --help exposes no such flag; the id is written only into .saga/ filenames at :349, :360, :384 and :508 and never into a tick",
        "controller and agent-usability lens confirmed the same independently"
      ],
      "file": "plugins/saga/skills/work/SKILL.md",
      "finding_id": "W02",
      "lens_id": "architecture-maintainability",
      "line": 428,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P1",
      "status": "active",
      "suggested_fix": "Point the two blocks at the on-disk lease artifact instead, or add a real Saga field plus a save flag and record it in the launch tick before saying a tick carries it.",
      "title": "Release block reads an invocation id no tick carries",
      "touched_paths": [
        "plugins/saga/skills/work/SKILL.md"
      ],
      "why_it_matters": "The repair replaced the unset shell variable with an instruction to take WORKFLOW_INVOCATION_ID from the saga tick, but no Saga field and no save flag holds it, so an agent following the block literally cannot recover the launch identity and the lease still never closes."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "safe-bounded-idempotent-resumable-context-cost",
      "evidence": [
        "plugins/saga/skills/work/SKILL.md:428 and the placeholder exports at :433 and :445",
        "lens measurement: a grep for 'invocation' in plugins/saga/scripts/saga.py returned 0; saga.py save --help exposes --orchestration-run-id documented as the transient workflow RUN handle and nothing for an invocation id; the saga-spec frontmatter field table has no such row",
        "lens run of the shipped release block verbatim in a shell with none of the three variables set: 'workflow-lease: HALT \u2014 cannot read lease metadata .saga/workflow-lease-<the invocation id recorded in the saga tick for this launch>.json', exit 2",
        "docs/engineering-journal/LEARNINGS.md now codifies the same false premise as a durable rule",
        "the pre-existing instruction to RECORD it was never backed by a field; what is NEW is the release path depending on reading it back",
        "controller independently confirmed: saga.py contains the string 'invocation' zero times, and the forty-field envelope table has no such field",
        "no test covers it -- tests/test_saga_plugin.py:88-102 pins the ORDER of the four emitter commands and nothing about the variables they need"
      ],
      "file": "plugins/saga/skills/work/SKILL.md",
      "finding_id": "Y01",
      "lens_id": "agent-usability",
      "line": 428,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P1",
      "status": "active",
      "suggested_fix": "Either add an invocation-id flag plus envelope field to saga.py and cite it, or change the instruction to name the real source -- the lease receipt already on disk under .saga/, which can be enumerated without any tick.",
      "title": "Release block sources the invocation id from a nonexistent tick field",
      "touched_paths": [
        "plugins/saga/skills/work/SKILL.md"
      ],
      "why_it_matters": "The repaired release and renew blocks tell the agent to take WORKFLOW_INVOCATION_ID from the saga tick, but no saga envelope field, command-line flag, or spec row records it, so on the crash-resume path the protocol names as its reason for existing the value is unrecoverable and the lease never closes."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "completeness-audience-prerequisites",
      "evidence": [
        "the Saga dataclass carries no invocation-id field among its 48 names; the save parser has no flag for it",
        "the only recording step in the Work skill is the orchestration run handle, which the flag's own help text calls a different value obtained after launch",
        "the instruction is at work/SKILL.md:428, :433 and :445, and the journal records it as the shipped fix",
        "the root claim is pre-existing at the merge base, but this repair turned it into a runnable placeholder",
        "found independently by the controller and the agent-usability and architecture lenses"
      ],
      "file": "plugins/saga/skills/work/SKILL.md",
      "finding_id": "N04",
      "lens_id": "documentation-clarity",
      "line": 433,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P1",
      "status": "active",
      "suggested_fix": "Either add a recording path and name it in the two blocks, or point the blocks at the on-disk lease metadata where the id actually persists.",
      "title": "Release block reads an invocation id no tick field holds",
      "touched_paths": [
        "plugins/saga/skills/work/SKILL.md"
      ],
      "why_it_matters": "The rewritten fresh-shell blocks tell the agent to take the invocation id from the saga tick and forbid minting a new one, but no saga tick field and no save flag record that value, so the lease close-out has no reachable source for its only required input."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "architectural-fit-ownership-single-sources",
      "evidence": [
        "the pin at tests/test_plan_artifact_conformance.py:323-348 parses only the plan-sections bullet and one collapsed sentence; the template is at plugins/saga/skills/plan/SKILL.md:265-273",
        "lens mutation: deleting a required key from the template left tests/test_plan_artifact_conformance.py at 11 passed and the seven files reading that skill at 135 passed; restored",
        "carried from cycle 2 finding A07, not addressed"
      ],
      "file": "tests/test_plan_artifact_conformance.py",
      "finding_id": "W04",
      "lens_id": "architecture-maintainability",
      "line": 323,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P1",
      "status": "active",
      "suggested_fix": "Extend that test to parse the YAML block in the Plan skill and assert its keys are a superset of the required-field tuple.",
      "title": "Required-field pin still misses the YAML template",
      "touched_paths": [
        "tests/test_plan_artifact_conformance.py"
      ],
      "why_it_matters": "The required-field contract has three declarations and only two are bound, so deleting a required key from the template authoring agents copy leaves the suite green and every new plan failing the shipped check."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "significant-decision-documentation",
      "evidence": [
        "LEARNINGS.md:29 under the fresh-shell-block-scope anchor at :24; the Saga dataclass has no such field and the save command no such flag",
        "the same entry's validation paragraph IS accurate about the shell mechanics: deleting the repeated assignment from the release block turned tests/test_workflow_extraction.py to 2 failed / 12 passed",
        "NEW false durable record introduced by this repair"
      ],
      "file": "docs/engineering-journal/LEARNINGS.md",
      "finding_id": "W08",
      "lens_id": "architecture-maintainability",
      "line": 29,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Rewrite the Fix paragraph to name the real recovery source, and keep the generalizable fresh-shell rule, which is correct and proven.",
      "title": "Journal codifies a rule about a nonexistent tick field",
      "touched_paths": [
        "docs/engineering-journal/LEARNINGS.md"
      ],
      "why_it_matters": "The entry records as durable practice that the lease-metadata path is derived from the invocation id taken from the saga tick, so a future maintainer will look for a tick field that has never existed and will trust the release path as closed."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "authentication-authorization-tenant-isolation",
      "evidence": [
        "the lens scanned every committed markdown file under docs/ and plugins/ through the shipped evaluator: two return a non-empty apply, the wave-1 plan at :346 and plugins/saga/references/saga-spec.md:692, both yielding an applied inline backend and plan-only destination with a caller of orchestrate and no stop",
        "the Plan skill directs the validator at the invocation text, and plan documents are inputs Plan legitimately receives",
        "caller is never authenticated -- only an isinstance check -- so the narrated provenance is whatever the text claims",
        "the same scan found zero documents that now halt, which is what closes cycle-2 finding S01",
        "privilege direction is downward and escalation is denied: a carrier naming the Workflow backend still stops"
      ],
      "file": "docs/plans/2026-08-30-saga-plan-improvement-918-wave1-plan.md",
      "finding_id": "V02",
      "lens_id": "security",
      "line": 346,
      "owner": "downstream-resolver",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Require the carrier fence to be the first fenced block, or require an explicit opt-in token the documentation examples omit; alternatively fence the two examples with an info string the scanner already treats as not-a-carrier.",
      "title": "Committed documentation examples are live carriers",
      "touched_paths": [
        "docs/plans/2026-08-30-saga-plan-improvement-918-wave1-plan.md"
      ],
      "why_it_matters": "Running Plan on a plan document that merely documents the carrier silently settles backend and destination and suppresses the Phase 5.1 and 5.2 operator questions, attributing the decision to a caller that never ran."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "realistic-seams-mocks-integration-evidence",
      "evidence": [
        "emitter.py:1348 calls _ES._agent_prompt; the name is absent from the surface tuple at :48-78",
        "lens mutation: renaming the definition in plugins/saga/scripts/execution_spec.py:2199 left tests/test_cc_workflows_emitter_surface.py at 3 passed, 0 failed",
        "commit 053ef438 does not touch emitter.py at all -- the thirteen changed files include none under plugins/cc-workflows/",
        "found independently by the correctness lens and the controller; four lenses found it at cycle 2"
      ],
      "file": "plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py",
      "finding_id": "Z05",
      "lens_id": "testing",
      "line": 1348,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Add _agent_prompt to SUBSTRATE_SURFACE and extend the guard's name collection to walk qualified attribute accesses on the substrate module.",
      "title": "SUBSTRATE_SURFACE still under-declares the plugin boundary",
      "touched_paths": [
        "plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py"
      ],
      "why_it_matters": "_agent_prompt crosses the cc-workflows and saga seam through a qualified call but is absent from the declared surface, so the guard a reader trusts to describe the boundary is wrong about the boundary it describes."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "completeness-audience-prerequisites",
      "evidence": [
        "the flag is added at plan_pre_answers.py:351-361 and documented in the spec and the skill, but a grep across the changelog returns nothing",
        "the plugin manifest is at 0.150.0, so this release is the right one to carry it",
        "NEW gap introduced by this repair; found independently by the agent-usability and api-contract lenses"
      ],
      "file": "plugins/saga/CHANGELOG.md",
      "finding_id": "N08",
      "lens_id": "documentation-clarity",
      "line": 7,
      "owner": "release",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Add one clause to the carrier bullet naming the repeatable flag as how a caller supplies an already-settled decision.",
      "title": "0.150.0 entry omits the new --established flag",
      "touched_paths": [
        "plugins/saga/CHANGELOG.md"
      ],
      "why_it_matters": "The repair added a repeatable command-line option and the repository's contributing rule requires a command change to move with the release surfaces in the same change, so a reader of the release entry cannot discover the flag the contradiction rule now depends on."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "discoverability-invocation-schemas",
      "evidence": [
        "a grep for the flag name across plugins/saga/CHANGELOG.md at this revision returns nothing",
        "the 0.150.0 pre-answer entry at :7-17 describes the contradiction stop without naming the flag that supplies the established value, which is defined at plan_pre_answers.py:351-361",
        "the repository's own CLAUDE.md step 6 requires the plugin release surfaces to move with any command change in the same pull request",
        "NEW gap introduced by this repair; the cycle-2 half of this line was fixed -- the two-case unknown-schema wording is now correct"
      ],
      "file": "plugins/saga/CHANGELOG.md",
      "finding_id": "Y08",
      "lens_id": "agent-usability",
      "line": 7,
      "owner": "release",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Add one clause to the 0.150.0 entry naming the repeatable flag as the way a caller supplies already-settled decisions.",
      "title": "New --established flag missing from the release surface",
      "touched_paths": [
        "plugins/saga/CHANGELOG.md"
      ],
      "why_it_matters": "The repair added a repeatable agent-facing command-line flag that the release surface never mentions, so an agent or caller reading the changelog to learn the carrier's interface cannot discover the only way to make the contradiction rule fire."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "specification-documentation-parity",
      "evidence": [
        "a grep for the flag across the changelog returns zero; the 0.150.0 entry names the validator script but never the flag",
        "the Plan skill and the saga-spec show the happy path only -- neither states what an out-of-enum value or a repeated field does",
        "the repository's own contributing rule requires the release surfaces to move with a command change",
        "version metadata itself is consistent: saga 0.150.0 and cc-workflows 1.0.0 in both the manifests and the registry",
        "NEW gap introduced by this repair; found independently by the agent-usability lens"
      ],
      "file": "plugins/saga/CHANGELOG.md",
      "finding_id": "Q06",
      "lens_id": "api-contract",
      "line": 9,
      "owner": "release",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Add one 0.150.0 bullet naming the repeatable flag, its two fields, and that a contradicting carrier stops.",
      "title": "New repeatable flag absent from every release surface",
      "touched_paths": [
        "plugins/saga/CHANGELOG.md"
      ],
      "why_it_matters": "A new public flag on a shipped script ships with no changelog line and no stated failure modes, so an integrating caller has no authoritative account of what a bad or repeated value does."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "completeness-audience-prerequisites",
      "evidence": [
        "CHANGELOG.md:32-33 unchanged by this repair; the lens counted eleven non-plan entries including two decision briefs and the ideation subtree",
        "docs/engineering-journal/DECISIONS.md:16 states the accurate wording",
        "carried from cycle 2 finding D10, not addressed"
      ],
      "file": "plugins/saga/CHANGELOG.md",
      "finding_id": "N07",
      "lens_id": "documentation-clarity",
      "line": 33,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Match the journal wording: the directory no longer holds generated artifacts and retains plan documents plus the ideation subtree.",
      "title": "Changelog says docs/plans is reserved for plan documents",
      "touched_paths": [
        "plugins/saga/CHANGELOG.md"
      ],
      "why_it_matters": "A reader acting on the release note would treat eleven surviving non-plan entries as misfiled, and the sentence contradicts the parallel journal entry that is accurate."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "capability-parity-reachability",
      "evidence": [
        "plugins/saga/references/execution-spec.md:399-401; the equivalent Saga command differing only in runner already sits inline at :429",
        "untouched by the repair -- the thirteen changed files do not include this one",
        "the lens's view on carried-forward finding F31: a declared dependency would NOT fix this, because the failure is a missing inline command and a missing halt, not a missing manifest entry",
        "carried from cycle 2 finding U07, not addressed"
      ],
      "file": "plugins/saga/references/execution-spec.md",
      "finding_id": "Y07",
      "lens_id": "agent-usability",
      "line": 399,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Keep the cross-reference for rationale, restate the one-line validate command inline, and name the halt when the sibling plugin is not installed.",
      "title": "HARD BLOCK step still points across plugins with no fallback",
      "touched_paths": [
        "plugins/saga/references/execution-spec.md"
      ],
      "why_it_matters": "Step 2 of Saga's own authoring flow is a hard block whose only command lives in another plugin's skill file at a repo-relative path that does not resolve in an installed-plugin session, and no halt is named for that plugin being absent, so the agent cannot complete the gate it is forbidden to skip."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "discoverability-invocation-schemas",
      "evidence": [
        "saga-spec.md:699 is untouched by the repair",
        "lens run: a carrier declaring an uppercase family token returned the whole-refusal stop, while the canonical token applied both decision fields",
        "the same gap exists in the skill an agent executes at plugins/saga/skills/plan/SKILL.md:161-163",
        "carried from cycle 2 finding U10, not addressed"
      ],
      "file": "plugins/saga/references/saga-spec.md",
      "finding_id": "Y04",
      "lens_id": "agent-usability",
      "line": 699,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Append the sentence to both places: family membership is matched case-insensitively; the full token is compared exactly, so any case variation is a non-v1 token and is refused whole.",
      "title": "Version-token exactness still unstated",
      "touched_paths": [
        "plugins/saga/references/saga-spec.md"
      ],
      "why_it_matters": "A carrier-authoring agent reading the case-insensitive family rule predicts an uppercase token is applied, but the version token is compared exactly, so a case variant is refused whole and its settled decisions are lost."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "discoverability-invocation-schemas",
      "evidence": [
        "a grep across plugins/ matches only prose in saga-spec.md and the script itself -- no hit under plugins/saga/skills/",
        "lens run: the script against a nonexistent root printed a one-key JSON error and exited 2, against a docstring promising only 0 and 1",
        "carried from cycle 2 finding U08, not addressed; the testing lens found the same absence of any caller"
      ],
      "file": "plugins/saga/scripts/plan_artifact_conformance.py",
      "finding_id": "Y05",
      "lens_id": "agent-usability",
      "line": 18,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Add the literal command and all three exit codes as a Phase 5-side step in the Plan skill, and add the bad-root case to the module docstring.",
      "title": "Conformance checker still undiscoverable, exit 2 still undocumented",
      "touched_paths": [
        "plugins/saga/scripts/plan_artifact_conformance.py"
      ],
      "why_it_matters": "No shipped skill tells an agent when or how to run the plan-artifact conformance check, and its docstring still promises only exits 0 and 1 while a bad root exits 2, so an agent treats a configuration mistake as a contract failure."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "state-data-invariants-transactions-concurrency",
      "evidence": [
        "plan_artifact_conformance.py:79-85 and the classification at :104",
        "lens run: check_document on frontmatter carrying backend inline plus an unclosed list returned legacy-no-backend with legacy True",
        "the repair commit does not touch this file"
      ],
      "file": "plugins/saga/scripts/plan_artifact_conformance.py",
      "finding_id": "X07",
      "lens_id": "correctness",
      "line": 81,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Emit a distinct failing unparseable-frontmatter finding in the YAML-error arm instead of collapsing it into the legacy bucket.",
      "title": "Broken YAML still reclassifies a backend plan as legacy",
      "touched_paths": [
        "plugins/saga/scripts/plan_artifact_conformance.py"
      ],
      "why_it_matters": "split_frontmatter swallows a YAML error into empty fields, so a plan that does declare backend but has any YAML syntax slip is reported non-failing legacy and passes the gate, violating the module's own rule that legacy means the absence of backend and nothing else."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "serialization-errors",
      "evidence": [
        "the read at :102 is unguarded; a scratch root holding one non-UTF-8 file gave a decode error, exit 1, empty stdout",
        "the docstring at :18-19 still declares only 0 and 1 while main() returns 2 on a non-directory root, which the lens confirmed",
        "the sibling entry point was repaired to exactly the right shape in this same change, so the correct pattern already exists",
        "carried from cycle 2 finding P05, half-fixed"
      ],
      "file": "plugins/saga/scripts/plan_artifact_conformance.py",
      "finding_id": "Q05",
      "lens_id": "api-contract",
      "line": 102,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Wrap the per-document read, emit the one-key JSON error and exit 2 the bad-root branch already uses, and add exit 2 to the docstring.",
      "title": "Conformance script still crashes with the failure exit code",
      "touched_paths": [
        "plugins/saga/scripts/plan_artifact_conformance.py"
      ],
      "why_it_matters": "An unreadable document exits 1 with a raw traceback and no output -- the same code the docstring reserves for a real conformance failure -- so a consumer cannot tell a crash from a finding."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "requirements-regression-coverage",
      "evidence": [
        "lens mutation: the enum check at :122 forced False left 41 passed, 0 failed across both conformance suites",
        "appending a one-value BACKEND_ENUM after :45 left tests/test_plan_artifact_conformance.py at 11 passed, 0 failed",
        "the enum finding kind appears in the test file only as an absence assertion",
        "carried from cycle 2, not addressed"
      ],
      "file": "plugins/saga/scripts/plan_artifact_conformance.py",
      "finding_id": "Z02",
      "lens_id": "testing",
      "line": 122,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Add a tmp_path fixture whose frontmatter carries an out-of-enum backend value and assert the enum finding with a failing corpus exit.",
      "title": "Backend-enum rule still has no positive test",
      "touched_paths": [
        "plugins/saga/scripts/plan_artifact_conformance.py"
      ],
      "why_it_matters": "The unit U1 contract's backend enum can stop being enforced, or shrink to a single value, and the whole suite stays green -- no fixture ever carries an out-of-enum backend value."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "boundary-types-serialization-numeric-time",
      "evidence": [
        "plan_pre_answers.py:87 and :178",
        "lens run: a well-formed carrier alone applied backend inline; the identical carrier preceded by a line containing a stray triple backtick returned applied {} stop None",
        "unchanged by this repair"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "X08",
      "lens_id": "correctness",
      "line": 87,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Anchor the fence match to line starts and count backticks so an unpaired or longer fence cannot offset the scan.",
      "title": "Stray triple backtick still drops the carrier",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "_FENCE_RE pairs fence markers left to right with no odd-count handling, so one inline triple backtick before the carrier shifts the pairing and the caller's settled decision vanishes with no stop."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "intent-behavior-completeness",
      "evidence": [
        "plan_pre_answers.py:94 and :184/:191",
        "lens runs: a json fence holding a note string mentioning the family token plus a comment returned the malformed-carrier stop; so did a duplicate-key block whose comment mentioned it",
        "the two cycle-2 reproductions no longer halt, so the fix is real but partial",
        "the docstring at :89-93 claims the gate is the same membership test _is_family_schema performs; that one tests the parsed schema value, this tests raw text anywhere in the block"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "X04",
      "lens_id": "correctness",
      "line": 191,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Gate on a schema-position match rather than a bare token search, and correct the docstring's equivalence claim.",
      "title": "Shape gate still halts on prose that names the family",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "_CARRIER_SHAPE_RE searches the whole raw block, so an unrelated malformed JSON example that merely mentions the family token in a string value or a comment still stops the entire Plan run."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "context-constraints-acceptance-examples",
      "evidence": [
        "plan_pre_answers.py:184 and :191 continue when the block is not carrier-shaped",
        "lens runs: a fence containing a schema key truncated mid-token returned applied {} stop None, as did a hyphenated variant; a carrier truncated AFTER the token still stops correctly",
        "at the cycle-2 revision every one of these stopped, so the safety property narrowed",
        "the shipped rule in the Plan skill describes this behaviour accurately, so the prose is not wrong",
        "found independently by the correctness lens"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "Y09",
      "lens_id": "agent-usability",
      "line": 191,
      "owner": "downstream-resolver",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Warn carrier-authoring agents in the saga-spec carrier section that a carrier truncated before its schema token is silently ignored, or widen the shape test to the other admitted keys.",
      "title": "Carrier-shape gate silently drops a truncated carrier",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "The new gate requires the raw block text to name the family before a parse failure stops, so a carrier truncated before its schema token completes is ignored with exit 0 -- the silent drop the malformed-carrier rule was added to prevent."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "intent-behavior-completeness",
      "evidence": [
        "plan_pre_answers.py:191-192",
        "lens run: a carrier clipped before its schema line returned applied {} omitted (backend, destination) stop None; the same block with the schema line present returns the malformed-carrier stop, so the gate is the difference",
        "NEW hole opened by this repair's shape gate"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "X05",
      "lens_id": "correctness",
      "line": 192,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Treat a json fence naming caller, backend or destination keys as carrier-shaped too, or narrow the continue to blocks that parse cleanly as a foreign schema.",
      "title": "Truncated carrier is now silently dropped with no stop",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "A carrier whose malformation removed the family token is no longer carrier-shaped, so it takes the continue and becomes indistinguishable from absence -- the silent-resolution hole the module exists to close, reopened for the truncation case."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "boundary-types-serialization-numeric-time",
      "evidence": [
        "plan_pre_answers.py:197-198",
        "lens runs: a json fence holding a one-element array wrapping a valid carrier returned applied {} stop None; so did a fence holding the bare schema string",
        "the repair built _is_carrier_shaped -- exactly cycle-2's suggested fix for this line -- and never applied it here"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "X09",
      "lens_id": "correctness",
      "line": 197,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Return the malformed-carrier stop at :197 when the block is carrier-shaped, keeping continue only for non-object blocks with no family token.",
      "title": "Carrier-shaped non-object JSON still slips the stop",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "The isinstance dict guard continues on any scalar or array, so a carrier a caller wrapped in a JSON array is dropped as absence even though the block plainly names the family."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "confidentiality-logs-errors-egress",
      "evidence": [
        "plan_pre_answers.py:242 builds the listing with a bare f-string and never calls _echo, while the repaired duplicate-key path at :187 now does",
        "lens measurement: one 50,000-character unknown key gave a 50,162-character stop, byte-identical to cycle 2's number; 2,000 unknown keys gave 17,049; every other refusal path is now bounded between 85 and 218 characters",
        "injection reproduced: an unknown key containing a newline and a fence produced a stop whose text opens a fence and reads like an operator confirmation",
        "carried from cycle 2 finding S02, half-fixed"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "V01",
      "lens_id": "security",
      "line": 242,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Route the listing through the bounded echo, and extend the bounded-echo test to the unknown-key and duplicate-key paths.",
      "title": "Unknown-key refusal still echoes caller keys raw and unbounded",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "A refusal message Plan is told to surface exactly can still be inflated to 50,162 characters and can still carry unescaped newlines and fence delimiters, because only the duplicate-key half was routed through the bounded echo."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "interface-contract-compatibility",
      "evidence": [
        "plan_pre_answers.py:366 tests only the separator, a non-empty value and a known field",
        "lens runs: an out-of-enum established value against a valid carrier gave exit 2 and a false conflict; a realistic case-typo produced the same; a value containing a second separator is likewise accepted",
        "the module rejects an out-of-enum value on the carrier side at :265-273; the flag side has no equivalent",
        "NEW surface introduced by this repair; found independently by the correctness, security and agent-usability lenses"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "Q02",
      "lens_id": "api-contract",
      "line": 366,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Require the value to be in the field's enum and route the failure through the same argument-parser error, naming the enum.",
      "title": "New --established flag validates the field, never the value",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "The flag accepts a value outside the field's declared enum, then manufactures an exit-2 stop asserting a contradiction with an already-established value that is not a legal value of that field at all, and the Plan skill instructs the agent to surface that reason verbatim."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "caller-enum-consumer-completeness",
      "evidence": [
        "plan_pre_answers.py:366 reads 'if not separator or not value or field not in DECISION_ENUMS'",
        "lens run: a valid inline carrier with --established backend=totally-bogus returned rc 2 and 'supplied backend value inline contradicts the already-established value totally-bogus'",
        "DECISION_ENUMS[field] is in hand on that line and unused",
        "NEW defect introduced by this repair"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "X02",
      "lens_id": "correctness",
      "line": 366,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Extend the guard to reject a value outside DECISION_ENUMS[field] and name the legal values in the parser error text.",
      "title": "--established accepts values outside the decision enums",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "The guard checks only that the field is a known field, never that the value is in that field's enum, so a typo or an unsubstituted placeholder becomes a settled decision and stops a perfectly valid carrier."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "interface-contract-compatibility",
      "evidence": [
        "the assignment at :371 overwrites without checking membership",
        "lens runs: the same carrier with the two orderings gave exit 0 with an applied value in one order and exit 2 with a contradiction in the other",
        "no test repeats a field -- the two added subprocess cases pass one flag each",
        "NEW defect introduced by this repair"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "Q03",
      "lens_id": "api-contract",
      "line": 371,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Stop when the field is already present with a different value, using the same never-resolved-silently wording the duplicate-key stop uses.",
      "title": "Repeated --established for one field silently lets the last win",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "The same two flags in opposite order give opposite verdicts with no diagnostic, in a module whose stated discipline stops on duplicate JSON keys for exactly this reason."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "side-effects-errors-resource-lifecycle",
      "evidence": [
        "plan_pre_answers.py:103 sets the limit, :384-386 builds the stop, and :336-337 plus plugins/saga/skills/plan/SKILL.md:152-153 both promise a stop naming the unreadable path",
        "lens run against a deep nonexistent path: rc 2 and a stop truncated mid-errno, with no path character surviving",
        "the new test at tests/test_plan_pre_answers.py:521 asserts only that the word 'unreadable' appears, so the promise its own comment at :505 makes is unpinned",
        "NEW defect introduced by this repair"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "X01",
      "lens_id": "correctness",
      "line": 384,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Echo the path itself rather than the exception string.",
      "title": "Unreadable-file stop names none of the path",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "_ECHO_LIMIT truncates the echoed OSError before a single path character survives, so the stop the repair added for cycle-2 C10 cannot tell an operator which file failed."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "serialization-errors",
      "evidence": [
        "plan_pre_answers.py:394 is unchanged from cycle 2",
        "lens round-trip: the exact stdout of a clean run, re-fenced and fed back to the evaluator, was refused as carrying unadmitted keys",
        "no shipped surface documents the report's shape; the Plan skill names only the stop field and the exit codes",
        "carried from cycle 2 finding P06, not addressed"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "Q04",
      "lens_id": "api-contract",
      "line": 394,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Emit a distinct outcome token for the report and document its four fields in the saga-spec carrier section.",
      "title": "Outcome report still stamped with the carrier's own version token",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "One version token names two incompatible objects -- the four-field carrier and the four-field report -- so the report is refused by the very evaluator that emitted it."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "readability-naming-error-contracts",
      "evidence": [
        "saga.py:856 and :861-863; only the class docstrings at :683-702 changed in this commit",
        "lens probe: wrapping a disk-full error gave errno, strerror and filename all None on the wrapper while the original kept its errno",
        "carried from cycle 2 finding A12, not addressed"
      ],
      "file": "plugins/saga/scripts/saga.py",
      "finding_id": "W09",
      "lens_id": "architecture-maintainability",
      "line": 856,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Construct with errno, message and filename, and give both classes a shared base.",
      "title": "Wrapped tick errors still drop errno and filename",
      "touched_paths": [
        "plugins/saga/scripts/saga.py"
      ],
      "why_it_matters": "Both OSError subclasses are still constructed from a single string, so a caller cannot tell a full disk from a permission failure, and there is still no shared base to catch both without naming both."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "separation-of-concerns",
      "evidence": [
        "saga.py:1709 duplicates the read at :802 where save() already binds prior; :1710-1711 swallows four classes behind the comment 'an unreadable prior proves no reference'",
        "because :802 runs first, any read fault reaches the generic branch instead, leaving this swallow reachable only in a race",
        "NEW structure introduced by this repair"
      ],
      "file": "plugins/saga/scripts/saga.py",
      "finding_id": "W07",
      "lens_id": "architecture-maintainability",
      "line": 1706,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Carry the already-computed prior on the exception itself, set at the raise site, and drop the re-read and its four-class catch.",
      "title": "Exception handler re-reads state save already computed",
      "touched_paths": [
        "plugins/saga/scripts/saga.py"
      ],
      "why_it_matters": "The error-presentation path performs a second filesystem read of the same envelope save() already loaded, and swallows four exception classes behind a comment asserting a false inference, so a diagnostic message depends on I/O succeeding at the exact moment the filesystem is failing."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "state-data-invariants-transactions-concurrency",
      "evidence": [
        "saga.py:1709-1723",
        "lens reproduction: with a prior tick recorded under docs/plans/p.md, an envelope failure for ./docs/plans/p.md produced 'now has NO saga tick referencing it', and identically for docs/../docs/plans/p.md, while the exact string produced the correct 'an earlier tick still references'",
        "two further weaknesses on the same branch: restore reads only the LATEST tick, so an earlier tick naming the plan is invisible once a later tick names a different one; and parse_envelope('') returns a Saga with an empty plan_path, so a mid-write envelope failure also yields the false claim",
        "the except (OSError, ValueError, TypeError, KeyError) fallback at :1710-1711 is unreachable from the command line, because save() calls restore at :800 before the envelope write; its comment 'an unreadable prior proves no reference' is wrong reasoning on dead code",
        "the controller's own reproduction used the exact path string and therefore missed this"
      ],
      "file": "plugins/saga/scripts/saga.py",
      "finding_id": "X03",
      "lens_id": "correctness",
      "line": 1712,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Normalize both sides before comparing, and scan every tick rather than only the latest; replace the fallback comment and emit the uncertain message there.",
      "title": "Stranded-plan test is raw string equality on plan_path",
      "touched_paths": [
        "plugins/saga/scripts/saga.py"
      ],
      "why_it_matters": "The same plan document spelled differently fails the comparison, so the operator is told the document has no tick referencing it while an earlier tick does -- the cycle-2 C02 falsehood moved rather than removed."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "negative-edge-state-concurrency-time",
      "evidence": [
        "lens mutation: the predicate at saga.py:1712 forced to True left 6 passed, 0 failed; corrupting the else-branch text at :1718 also left 6 passed, 0 failed",
        "controls arm correctly: forcing the predicate False gave 1 failed / 5 passed, and swapping the except clause for an unrelated exception gave the same",
        "grep for the stranded phrase across tests/ returns only this one module, so no other suite covers it",
        "NEW coverage hole introduced by this repair"
      ],
      "file": "plugins/saga/scripts/saga.py",
      "finding_id": "Z01",
      "lens_id": "testing",
      "line": 1712,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Add a sibling test that fails the envelope write with NO prior tick recording the plan path and asserts the stranded branch's own words, the way the new tracked test asserts its own.",
      "title": "New envelope-handler branch has one untested side",
      "touched_paths": [
        "plugins/saga/scripts/saga.py"
      ],
      "why_it_matters": "The repair split the envelope-write failure message into a tracked branch and a stranded branch, and only the tracked branch is proven, so inverting the predicate makes the command tell an operator a genuinely stranded plan is tracked with nothing going red."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "context-constraints-acceptance-examples",
      "evidence": [
        "plugins/saga/skills/plan/SKILL.md:143 prints both flags unconditionally; plan_pre_answers.py:366 checks only that the field is known",
        "lens run of the block as written against a valid inline carrier: exit 2 with 'supplied backend value inline contradicts the already-established value <already-settled-value>'",
        "the same command with a nonsense value also stopped rather than erroring, so a typo is indistinguishable from a real conflict",
        "the mitigating sentence at :146-148 exists but the command block contradicts it"
      ],
      "file": "plugins/saga/skills/plan/SKILL.md",
      "finding_id": "Y03",
      "lens_id": "agent-usability",
      "line": 143,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Validate each --established value against its enum in the argument parser, and mark the two flags optional in the command block.",
      "title": "Phase 0.7's own example command halts Plan with a false conflict",
      "touched_paths": [
        "plugins/saga/skills/plan/SKILL.md"
      ],
      "why_it_matters": "The --established flag validates the field name but never the value, so the skill's canonical command block run as printed treats the literal placeholder as an established decision and stops Plan at entry on a conflict that does not exist."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "machine-readable-output-actionable-errors",
      "evidence": [
        "plugins/saga/skills/plan/SKILL.md:152-153 versus plan_pre_answers.py:103",
        "lens run: even a short relative filename truncates mid-path",
        "the rest of the exit contract IS genuinely fixed: missing file, permission-denied, non-UTF-8 and a directory all exit 2 with the same JSON shape, and four malformed command lines all exit 2 through argparse with usage and no JSON",
        "found independently by the correctness lens"
      ],
      "file": "plugins/saga/skills/plan/SKILL.md",
      "finding_id": "Y02",
      "lens_id": "agent-usability",
      "line": 152,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Echo the path separately from the exception text, or raise the echo limit for this one message.",
      "title": "Unreadable-file stop never names the path the prose promises",
      "touched_paths": [
        "plugins/saga/skills/plan/SKILL.md"
      ],
      "why_it_matters": "Phase 0.7 tells the agent the stop names the unreadable path and to surface it exactly, but the forty-character echo budget is consumed by the errno prefix, so the operator is told a file is unreadable without being told which one."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "capability-parity-reachability",
      "evidence": [
        "plugins/saga/skills/work/SKILL.md:350-352 against the ladder message at plugins/saga/scripts/execution_spec.py:2466",
        "the repair copied the two-rung line verbatim into the release and renew blocks at :435 and :447 without the caveat",
        "lens run of the shipped release block from a non-checkout working directory: a bare interpreter file-not-found, exit 2, with no halt text",
        "the new guard at tests/test_workflow_extraction.py:312 runs with the repo root as its working directory, so it cannot see this"
      ],
      "file": "plugins/saga/skills/work/SKILL.md",
      "finding_id": "Y06",
      "lens_id": "agent-usability",
      "line": 350,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Replace the parity claim with the true statement, and add a guard that halts with the resolver's own message when the resolved path is absent.",
      "title": "False parity claim now replicated across three lease blocks",
      "touched_paths": [
        "plugins/saga/skills/work/SKILL.md"
      ],
      "why_it_matters": "The comment says the shell resolves the scripts directory the same way the Python seam does, but the shell has one environment rung plus a working-directory-relative default while the Python seam has four, so outside a repo-root working directory all three blocks die on a bare interpreter error instead of the seam's guided halt."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "terminology-cross-document-consistency",
      "evidence": [
        "a repository grep returns exactly three sites and none defines it; the plan's sibling code is likewise used without expansion",
        "carried from cycle 2 finding D09, not addressed"
      ],
      "file": "docs/engineering-journal/DECISIONS.md",
      "finding_id": "N09",
      "lens_id": "documentation-clarity",
      "line": 17,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Expand on first use in both the journal entry and the test comment.",
      "title": "Undefined internal code still in the journal",
      "touched_paths": [
        "docs/engineering-journal/DECISIONS.md"
      ],
      "why_it_matters": "A maintainer reading the decision entry cannot learn which settled decision the extraction served, because the code is expanded nowhere in the repository."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "dependency-supply-chain",
      "evidence": [
        "the repair's thirteen files include neither this README nor operator-choice.md",
        "lens re-reproduction at this revision: with an invalid root override and a stub pre-registered under the module name, the loader returned the stub with no exception while resolving the root directly raised",
        "carried from cycle 2 finding S04, not addressed"
      ],
      "file": "plugins/cc-workflows/README.md",
      "finding_id": "V07",
      "lens_id": "security",
      "line": 34,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "One sentence in the README's resolution section naming the module-cache reuse as the step above rung one, and the same line in the shim docstring.",
      "title": "Documented resolution ladder still omits the sys.modules short-circuit",
      "touched_paths": [
        "plugins/cc-workflows/README.md"
      ],
      "why_it_matters": "The README's rung-one promise that an invalid root override raises rather than falls through does not hold on the cached path, so a reader auditing which code the plugin loads is told the wrong thing."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "authentication-authorization-tenant-isolation",
      "evidence": [
        "operator-choice.md:58-60 still reads ALWAYS surface with no carrier mention, and a grep for the carrier across that file returns nothing",
        "plugins/saga/skills/plan/SKILL.md:348 carries the exception",
        "the repair commit's file list does not include operator-choice.md; carried from cycle 2 finding S06, not addressed"
      ],
      "file": "plugins/saga/references/operator-choice.md",
      "finding_id": "V08",
      "lens_id": "security",
      "line": 59,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "One bullet naming the Phase 0.7 carrier as the single exception, scoped to the inline backend.",
      "title": "Decision contract still states ALWAYS-surface with no carrier exception",
      "touched_paths": [
        "plugins/saga/references/operator-choice.md"
      ],
      "why_it_matters": "The authority Plan Phase 5.2 defers to says the backend offer is always surfaced, while Plan now skips that offer when a carrier applied an inline backend, so the two shipped surfaces disagree about when an operator gets asked."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "requirements-regression-coverage",
      "evidence": [
        "a repo-wide grep outside tests/ and the module itself returns only prose in plugins/saga/references/saga-spec.md and the module's own usage line",
        "scripts/gate.sh:186 and .github/workflows/ci.yml:95 call a different script",
        "the 47-line Plan skill diff in 053ef438 adds no runnable command block for this check"
      ],
      "file": "plugins/saga/scripts/plan_artifact_conformance.py",
      "finding_id": "Z06",
      "lens_id": "testing",
      "line": 163,
      "owner": "human",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Add a gate step running the conformance check over docs/plans, or give Plan Phase 5.3 a runnable command block the way Phase 0.7 has one.",
      "title": "Conformance check still has no caller outside its test",
      "touched_paths": [
        "plugins/saga/scripts/plan_artifact_conformance.py"
      ],
      "why_it_matters": "The shipped contract check runs only when pytest runs, so a non-conforming plan artifact authored outside a test run is never reported -- the condition cycle-1 finding F06t was filed against."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "input-trust-boundaries-injection",
      "evidence": [
        "plan_pre_answers.py:94 gates :184 and :191 while :129-139 gates :199",
        "lens reproduction: a block whose schema token is JSON-escaped is admitted by the parsed test but not the raw one, so a duplicated key in that block was silently skipped instead of stopping",
        "a carrier truncated before its schema line returns no stop -- the malformed-is-indistinguishable-from-absence defect, surviving for the subset that does not literally spell the family",
        "both evasions fail SAFE: nothing is applied and both fields fall through to the operator conversation",
        "both mutation directions on the gate go red, so the repair itself is properly guarded"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "V05",
      "lens_id": "security",
      "line": 94,
      "owner": "downstream-resolver",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Decode JSON string escapes before the shape test, or make the shape test a lenient parse that looks for a schema value in the family.",
      "title": "Shape gate matches raw text where the family gate matches parsed values",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "One test reads bytes and the other reads parsed values, so the same block can be a carrier to one and prose to the other -- which makes the duplicate-key stop evadable and lets a truncated carrier pass as no carrier."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "serialization-errors",
      "evidence": [
        "plan_pre_answers.py:179 is unchanged; the family test lowercases",
        "lens run: an uppercase-fenced valid carrier returned a result identical to the no-carrier case",
        "downgraded from cycle 2's P2 because the repair DID document the drop in both authoritative surfaces, so parity now holds and only the sharp edge remains"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "Q08",
      "lens_id": "api-contract",
      "line": 179,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Lowercase the info string before comparison, and add a case-variant fence case beside the existing fence tests.",
      "title": "Uppercase JSON fence still discards a valid carrier silently",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "The fence info string is compared case-sensitively while the schema family is matched case-insensitively to catch near-misses loudly, so a caller writing an uppercase fence loses a fully valid settled decision with no stop."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "input-trust-boundaries-injection",
      "evidence": [
        "plan_pre_answers.py:255-263 is still the only validation and :311 still returns caller unchanged; the repair did not touch either",
        "lens reproduction: a caller carrying newlines and bold markup returned applied with no stop and the caller byte-for-byte; a 100,000-character caller returned intact",
        "carried from cycle 2 finding S03, not addressed"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "V03",
      "lens_id": "security",
      "line": 255,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Return the bounded echo of caller, or reject a caller containing a newline or longer than a fixed width.",
      "title": "caller still unbounded and narrated verbatim",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "A caller-supplied string of any length with newlines intact still lands in operator-facing narration on the path where the run continues rather than stops, so the narration surface is shaped by the supplying capability."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "side-effects-errors-resource-lifecycle",
      "evidence": [
        "plan_pre_answers.py:282-295 precedes :296-307",
        "lens run: an ultracode carrier against an established inline returned the invocation-only stop with no mention of the established value; nothing is applied either way, so only the diagnosis is wrong"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "X10",
      "lens_id": "correctness",
      "line": 282,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Run the established comparison first and, when both fire, emit one stop naming the contradiction and the invocation-only rule together.",
      "title": "Invocation-only stop still masks the established conflict",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "The invocation-only backend check returns before the established comparison, so a carrier escalating from an operator-settled inline is diagnosed as merely needing invocation -- and the new --established flag makes that path reachable from the documented command for the first time."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "input-trust-boundaries-injection",
      "evidence": [
        "plan_pre_answers.py:366 checks only the separator, a non-empty value and a known field -- no membership check, unlike carrier values at :271",
        "lens run: an out-of-enum established value against a valid inline carrier gave exit 2 and a contradiction stop naming the impossible value",
        "injection does NOT hold -- a newline-and-fence payload came back repr-escaped and truncated -- and escalation does NOT hold: an established Workflow backend still hits the invocation-only stop",
        "NEW surface introduced by this repair; found independently by the correctness and agent-usability lenses"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "V04",
      "lens_id": "security",
      "line": 366,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Add a membership check against the field's enum to the argument-parser error condition.",
      "title": "New --established flag validates the field but never the value",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "The new command-line surface accepts any value for a decision field, so the validator stops a legal carrier and tells the operator that an impossible value is the already-established value."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "negative-edge-state-concurrency-time",
      "evidence": [
        "lens mutation: the guard at :366 forced False left 30 passed, 0 failed",
        "the positive halves ARE armed: neutering the assignment at :371 gave 1 failed / 29 passed, and dropping the established argument at :390 gave the same",
        "tests/test_plan_pre_answers.py is the only module that passes this flag"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "Z07",
      "lens_id": "testing",
      "line": 366,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Extend the entry-point test with a subprocess call passing a malformed --established value and assert exit 2 with argparse usage on stderr and no JSON on stdout.",
      "title": "New --established validation branch is untested",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "The whole rejection path for a malformed --established argument -- missing separator, empty value, unknown field, and its bounded echo of caller input -- can be disabled without any test noticing."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "serialization-errors",
      "evidence": [
        "saga.py:856 and :861-863 are unchanged; the repair edited only the two class docstrings and the operator messages",
        "lens probe: both classes constructed from a disk-full error reported no error number, message or filename while the string form kept the full text",
        "no production consumer reads the error number today, which is why this is a residual",
        "carried from cycle 2 finding P04, not addressed"
      ],
      "file": "plugins/saga/scripts/saga.py",
      "finding_id": "Q07",
      "lens_id": "api-contract",
      "line": 856,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Construct with the error number, message and filename from the cause.",
      "title": "New OSError subclasses still carry no errno, strerror, filename",
      "touched_paths": [
        "plugins/saga/scripts/saga.py"
      ],
      "why_it_matters": "A handler branching on the error number -- the machine-actionable contract, and the shape this repository's own diagnostics read -- silently takes the None path."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "input-trust-boundaries-injection",
      "evidence": [
        "cycle-2 finding S05 is FIXED: all four expansions are quoted and the two fresh-shell blocks now re-establish the variables that were previously undefined there",
        "the new surface is the placeholder export at :433 and :445 feeding the lease filename at :434 and :446",
        "lens reproduction in bash: a value containing a parent-directory segment resolves the lease path to the repository root; no layer constrains it -- the emitter's text validator accepts any non-empty string",
        "the first block mints from uuidgen and is unaffected, and the surrounding file already uses unquoted angle-bracket placeholders, so this is a new instance of an existing pattern rather than a repair regression"
      ],
      "file": "plugins/saga/skills/work/SKILL.md",
      "finding_id": "V09",
      "lens_id": "security",
      "line": 433,
      "owner": "downstream-resolver",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Constrain the invocation id to a hexadecimal-and-hyphen shape in the emitter's metadata validator, and add a guard beside the two placeholder assignments.",
      "title": "New invocation-id placeholder flows unvalidated into a lease filename",
      "touched_paths": [
        "plugins/saga/skills/work/SKILL.md"
      ],
      "why_it_matters": "The repair added two blocks that tell the agent to paste a saga-tick value into a shell assignment whose result becomes a filename, and no layer validates the value's shape, so a value containing a parent-directory segment writes the lease metadata outside the state directory."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "confidentiality-logs-errors-egress",
      "evidence": [
        "lens mutation: reverting the bounded echo at plan_pre_answers.py:187 left tests/test_plan_pre_answers.py at 30 passed, the same as baseline; restored",
        "cycle 2's suggested fix explicitly asked for the bounded-echo test to cover all four refusal paths; it still exercises only the schema-token path"
      ],
      "file": "tests/test_plan_pre_answers.py",
      "finding_id": "V06",
      "lens_id": "security",
      "line": 361,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Parametrize the bounded-echo test over the unknown-key, duplicate-key, bad-enum and established-conflict paths with a large payload each.",
      "title": "The half of the echo fix that landed has no regression test",
      "touched_paths": [
        "tests/test_plan_pre_answers.py"
      ],
      "why_it_matters": "The duplicate-key bounded-echo guard can be deleted and nothing goes red, so the one bounded refusal path the repair added is unguarded against the next edit."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "determinism-isolation-diagnostics-maintainability",
      "evidence": [
        "tests/test_plan_pre_answers.py:537-540 reads the conformance module as text and asserts the literal line",
        "lens mutation: reflowing the tuple onto four lines with an identical value gave 1 failed / 29 passed; appending a semantically different redefinition after it, so the pinned text still matched, gave 30 passed / 0 failed",
        "the file already imports the module properly at :526-532"
      ],
      "file": "tests/test_plan_pre_answers.py",
      "finding_id": "Z04",
      "lens_id": "testing",
      "line": 540,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Load the conformance module and compare the two constants directly, deleting the text pin.",
      "title": "Drift pin matches source text, wrong in both directions",
      "touched_paths": [
        "tests/test_plan_pre_answers.py"
      ],
      "why_it_matters": "A formatter reflow with zero semantic change turns the pin red, and a real semantic drift of the same constant slips past it, so the pin reports the opposite of the contract it claims to guard."
    },
    {
      "autofix_class": "advisory",
      "confidence": 100,
      "dimension_id": "behavior-sensitive-assertions",
      "evidence": [
        "tests/test_saga_plan_save_and_routing.py:213 is a pure absence check; nothing counts ticks after a re-run",
        "the lens verified the claim by hand outside the suite: first save exit 2 with one tick, then a clean re-run exit 0 with two ticks"
      ],
      "file": "tests/test_saga_plan_save_and_routing.py",
      "finding_id": "Z08",
      "lens_id": "testing",
      "line": 213,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "In the same test, clear the blocker, re-run the identical arguments, and assert two ticks both carrying the completed phase status.",
      "title": "Re-run tick claim asserted only as word absence",
      "touched_paths": [
        "tests/test_saga_plan_save_and_routing.py"
      ],
      "why_it_matters": "The index handler now tells the operator the re-run appends one additional tick, and the only guard is that the message does not say idempotent, so the claim's truth is unverified by the suite even though it is true today."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "behavior-sensitive-assertions",
      "evidence": [
        "tests/test_workflow_extraction.py:113 and tests/test_saga_plugin.py:741 are both an OR over two phrasings across whole-file text",
        "lens mutation: corrupting the sentence at plugins/saga/skills/work/SKILL.md:53 while leaving the second phrasing at :275 intact, then running all ten modules that read that skill, gave 293 passed, 0 failed",
        "the repair touched tests/test_saga_plugin.py only for quote tolerance, not for this guard"
      ],
      "file": "tests/test_workflow_extraction.py",
      "finding_id": "Z03",
      "lens_id": "testing",
      "line": 113,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Assert a collapsed-text regex binding the pre-select prohibition to the backend it governs within one clause, and require a per-file match count rather than an OR over two phrasings.",
      "title": "Never-pre-select guard remains file-level, not sentence-level",
      "touched_paths": [
        "tests/test_workflow_extraction.py"
      ],
      "why_it_matters": "Deleting the prohibition sentence the guard is named for from the Work skill leaves every test green, because a second unrelated phrasing elsewhere in the same file satisfies the substring check."
    },
    {
      "autofix_class": "advisory",
      "confidence": 100,
      "dimension_id": "requirements-regression-coverage",
      "evidence": [
        "tests/test_workflow_extraction.py:218 asserts a named ideation subdirectory is a directory",
        "the two instances cycle 2 charged under obligation 7 are both genuinely retired: the wave-conflict test now asserts a non-empty glob with no integer, and the conformance test replaced the named constant with a corpus-derived rglob, which the lens confirmed armed (rglob to glob gave 2 failed / 9 passed)",
        "this surviving pin sits in unit U4's test, and the plan scopes requirement R33 to units U1 and U2, so it is outside R33's letter"
      ],
      "file": "tests/test_workflow_extraction.py",
      "finding_id": "Z09",
      "lens_id": "testing",
      "line": 218,
      "owner": "downstream-resolver",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Replace the named directory with the relation the assertion actually cares about -- that at least one subdirectory under docs/plans survived the move.",
      "title": "One named corpus directory pin survives in the U4 test",
      "touched_paths": [
        "tests/test_workflow_extraction.py"
      ],
      "why_it_matters": "A test asserts a specific corpus subdirectory name, so renaming or archiving that directory fails a test that has nothing to do with the rename."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "safe-bounded-idempotent-resumable-context-cost",
      "evidence": [
        "tests/test_workflow_extraction.py:312-326 partitions on the scripts-directory variable only",
        "the companion subprocess proof at :329 substitutes the invocation-id placeholder before running, so it cannot fail on a missing assignment either"
      ],
      "file": "tests/test_workflow_extraction.py",
      "finding_id": "Y10",
      "lens_id": "agent-usability",
      "line": 312,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Loop the structural assertion over all three variable names rather than hard-coding the scripts-directory one.",
      "title": "Fresh-shell structural guard covers one of three variables",
      "touched_paths": [
        "tests/test_workflow_extraction.py"
      ],
      "why_it_matters": "The guard asserts only that the scripts-directory assignment precedes its first use, so deleting either of the other two assignments from a close-out block reintroduces the empty-expansion class the guard exists to prevent, and stays green."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "readability-naming-error-contracts",
      "evidence": [
        "tests/test_workflow_extraction.py:343 selects the block by a quoted needle",
        "lens mutation: removing the quotes from all four expansions gave 1 failed / 67 passed, the failure being StopIteration at that line rather than the block's own assertions; restored"
      ],
      "file": "tests/test_workflow_extraction.py",
      "finding_id": "W10",
      "lens_id": "architecture-maintainability",
      "line": 343,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Select the block quote-tolerantly and add an explicit assertion that a block was found.",
      "title": "Fresh-shell guard fails as StopIteration, not a diagnosis",
      "touched_paths": [
        "tests/test_workflow_extraction.py"
      ],
      "why_it_matters": "The guard selects its block with a needle containing the quote character, so unquoting the expansion makes the test die with a bare StopIteration inside a generator rather than reporting what broke."
    }
  ],
  "fix_requests": [
    {
      "autofix_class": "manual",
      "finding_ids": [
        "V02"
      ],
      "fix_id": "fix-b5b1cf54bd9e",
      "owner": "downstream-resolver",
      "requires_verification": false,
      "summary": "Committed documentation examples are live carriers",
      "touched_paths": [
        "docs/plans/2026-08-30-saga-plan-improvement-918-wave1-plan.md"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "V05",
        "Y09"
      ],
      "fix_id": "fix-9e3a294949a8",
      "owner": "downstream-resolver",
      "requires_verification": false,
      "summary": "Shape gate matches raw text where the family gate matches parsed values; Carrier-shape gate silently drops a truncated carrier",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "V09"
      ],
      "fix_id": "fix-77bb21ac351e",
      "owner": "downstream-resolver",
      "requires_verification": false,
      "summary": "New invocation-id placeholder flows unvalidated into a lease filename",
      "touched_paths": [
        "plugins/saga/skills/work/SKILL.md"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "Z06"
      ],
      "fix_id": "fix-640332b3460b",
      "owner": "human",
      "requires_verification": false,
      "summary": "Conformance check still has no caller outside its test",
      "touched_paths": [
        "plugins/saga/scripts/plan_artifact_conformance.py"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "N08",
        "Q06"
      ],
      "fix_id": "fix-111b3a5ba6bf",
      "owner": "release",
      "requires_verification": false,
      "summary": "0.150.0 entry omits the new --established flag; New repeatable flag absent from every release surface",
      "touched_paths": [
        "plugins/saga/CHANGELOG.md"
      ]
    },
    {
      "autofix_class": "safe_auto",
      "finding_ids": [
        "Y08"
      ],
      "fix_id": "fix-e37ed06c14a3",
      "owner": "release",
      "requires_verification": false,
      "summary": "New --established flag missing from the release surface",
      "touched_paths": [
        "plugins/saga/CHANGELOG.md"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "N01",
        "W08"
      ],
      "fix_id": "fix-e84d08faaae9",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Journal still records the index re-run as idempotent; Journal codifies a rule about a nonexistent tick field",
      "touched_paths": [
        "docs/engineering-journal/LEARNINGS.md"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "Q01",
        "Z05"
      ],
      "fix_id": "fix-d954059184c4",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Undeclared private Saga name still crosses the plugin boundary; SUBSTRATE_SURFACE still under-declares the plugin boundary",
      "touched_paths": [
        "plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "N05"
      ],
      "fix_id": "fix-aeb801cf93a4",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Still no test binds carrier prose to the code",
      "touched_paths": [
        "plugins/saga/CHANGELOG.md"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "N06"
      ],
      "fix_id": "fix-2b465af21a75",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Case-differing v1 token refused, three surfaces say otherwise",
      "touched_paths": [
        "plugins/saga/references/saga-spec.md"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "Q05",
        "X07"
      ],
      "fix_id": "fix-79b89f62dfaf",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Conformance script still crashes with the failure exit code; Broken YAML still reclassifies a backend plan as legacy",
      "touched_paths": [
        "plugins/saga/scripts/plan_artifact_conformance.py"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "Q02",
        "Q03",
        "Q04",
        "Q08",
        "W03",
        "X04",
        "X05",
        "X08",
        "X09",
        "X10"
      ],
      "fix_id": "fix-884d9322d0b8",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "New --established flag validates the field, never the value; Repeated --established for one field silently lets the last win; Outcome report still stamped with the carrier's own version token; Uppercase JSON fence still discards a valid carrier silently; Two family-membership tests that are not the same test; Shape gate still halts on prose that names the family; Truncated carrier is now silently dropped with no stop; Stray triple backtick still drops the carrier; Carrier-shaped non-object JSON still slips the stop; Invocation-only stop still masks the established conflict",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "N03",
        "W01",
        "W06",
        "W07",
        "X03"
      ],
      "fix_id": "fix-52a145d37865",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Envelope-failure guard checks the latest tick, prose says any earlier; Envelope-failure branch checks only the latest tick; Generic branch still calls a read failure a write; Exception handler re-reads state save already computed; Stranded-plan test is raw string equality on plan_path",
      "touched_paths": [
        "plugins/saga/scripts/saga.py"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "N02",
        "Y03"
      ],
      "fix_id": "fix-31db917d5077",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Unreadable-file stop does not name the path; Phase 0.7's own example command halts Plan with a false conflict",
      "touched_paths": [
        "plugins/saga/skills/plan/SKILL.md"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "N04",
        "W02",
        "Y01",
        "Y06"
      ],
      "fix_id": "fix-f6054d24ef3a",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Release block reads an invocation id no tick field holds; Release block reads an invocation id no tick carries; Release block sources the invocation id from a nonexistent tick field; False parity claim now replicated across three lease blocks",
      "touched_paths": [
        "plugins/saga/skills/work/SKILL.md"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "W04"
      ],
      "fix_id": "fix-87eaea4a209e",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Required-field pin still misses the YAML template",
      "touched_paths": [
        "tests/test_plan_artifact_conformance.py"
      ]
    },
    {
      "autofix_class": "safe_auto",
      "finding_ids": [
        "N09"
      ],
      "fix_id": "fix-052d76cce82b",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Undefined internal code still in the journal",
      "touched_paths": [
        "docs/engineering-journal/DECISIONS.md"
      ]
    },
    {
      "autofix_class": "safe_auto",
      "finding_ids": [
        "V07"
      ],
      "fix_id": "fix-9e622b08b047",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Documented resolution ladder still omits the sys.modules short-circuit",
      "touched_paths": [
        "plugins/cc-workflows/README.md"
      ]
    },
    {
      "autofix_class": "safe_auto",
      "finding_ids": [
        "X06"
      ],
      "fix_id": "fix-22d6efb8abe2",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "SUBSTRATE_SURFACE still omits _agent_prompt",
      "touched_paths": [
        "plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py"
      ]
    },
    {
      "autofix_class": "safe_auto",
      "finding_ids": [
        "N07"
      ],
      "fix_id": "fix-c0968b07f9e0",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Changelog says docs/plans is reserved for plan documents",
      "touched_paths": [
        "plugins/saga/CHANGELOG.md"
      ]
    },
    {
      "autofix_class": "safe_auto",
      "finding_ids": [
        "Y07"
      ],
      "fix_id": "fix-f3a3ac0178de",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "HARD BLOCK step still points across plugins with no fallback",
      "touched_paths": [
        "plugins/saga/references/execution-spec.md"
      ]
    },
    {
      "autofix_class": "safe_auto",
      "finding_ids": [
        "V08"
      ],
      "fix_id": "fix-61319972cc18",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Decision contract still states ALWAYS-surface with no carrier exception",
      "touched_paths": [
        "plugins/saga/references/operator-choice.md"
      ]
    },
    {
      "autofix_class": "safe_auto",
      "finding_ids": [
        "Y04"
      ],
      "fix_id": "fix-31f8c6081fcc",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Version-token exactness still unstated",
      "touched_paths": [
        "plugins/saga/references/saga-spec.md"
      ]
    },
    {
      "autofix_class": "safe_auto",
      "finding_ids": [
        "Y05",
        "Z02"
      ],
      "fix_id": "fix-5bd1d98b52fb",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Conformance checker still undiscoverable, exit 2 still undocumented; Backend-enum rule still has no positive test",
      "touched_paths": [
        "plugins/saga/scripts/plan_artifact_conformance.py"
      ]
    },
    {
      "autofix_class": "safe_auto",
      "finding_ids": [
        "V01",
        "V03",
        "V04",
        "W05",
        "X01",
        "X02",
        "Z07"
      ],
      "fix_id": "fix-7ce7e909ff55",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Unknown-key refusal still echoes caller keys raw and unbounded; caller still unbounded and narrated verbatim; New --established flag validates the field but never the value; Purity claim still says reads no file; Unreadable-file stop names none of the path; --established accepts values outside the decision enums; New --established validation branch is untested",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ]
    },
    {
      "autofix_class": "safe_auto",
      "finding_ids": [
        "Q07",
        "W09",
        "Z01"
      ],
      "fix_id": "fix-e024cd2b6ff4",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "New OSError subclasses still carry no errno, strerror, filename; Wrapped tick errors still drop errno and filename; New envelope-handler branch has one untested side",
      "touched_paths": [
        "plugins/saga/scripts/saga.py"
      ]
    },
    {
      "autofix_class": "safe_auto",
      "finding_ids": [
        "Y02"
      ],
      "fix_id": "fix-6667f5be6029",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Unreadable-file stop never names the path the prose promises",
      "touched_paths": [
        "plugins/saga/skills/plan/SKILL.md"
      ]
    },
    {
      "autofix_class": "safe_auto",
      "finding_ids": [
        "V06",
        "Z04"
      ],
      "fix_id": "fix-1c0cb019d7a8",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "The half of the echo fix that landed has no regression test; Drift pin matches source text, wrong in both directions",
      "touched_paths": [
        "tests/test_plan_pre_answers.py"
      ]
    },
    {
      "autofix_class": "safe_auto",
      "finding_ids": [
        "W10",
        "Y10",
        "Z03"
      ],
      "fix_id": "fix-24db8e598169",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Fresh-shell guard fails as StopIteration, not a diagnosis; Fresh-shell structural guard covers one of three variables; Never-pre-select guard remains file-level, not sentence-level",
      "touched_paths": [
        "tests/test_workflow_extraction.py"
      ]
    }
  ],
  "lens_results": [
    {
      "accepted": false,
      "applicable_dimensions": {
        "architectural-fit-ownership-single-sources": 5.5,
        "conventions-portability-configuration": 6.0,
        "dependency-direction": 5.5,
        "readability-naming-error-contracts": 4.5,
        "separation-of-concerns": 5.5,
        "significant-decision-documentation": 4.5,
        "simplicity-abstraction-duplication-changeability": 5.0
      },
      "cycle": 3,
      "delta_check": null,
      "derived_overall": 5.214285714285714,
      "failing_dimensions": [
        "architectural-fit-ownership-single-sources",
        "separation-of-concerns",
        "dependency-direction",
        "simplicity-abstraction-duplication-changeability",
        "readability-naming-error-contracts",
        "conventions-portability-configuration",
        "significant-decision-documentation"
      ],
      "lens_id": "architecture-maintainability",
      "non_applicable_dimensions": {},
      "reviewed_revision": "053ef43881c2db7d7cee64845e5563a5b73eb43e",
      "score_accepted": false,
      "scoring_findings": [
        {
          "confidence": 100,
          "critical": true,
          "dimension_id": "readability-naming-error-contracts",
          "finding_id": "W01",
          "priority": "P1",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": true,
          "dimension_id": "conventions-portability-configuration",
          "finding_id": "W02",
          "priority": "P1",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": true,
          "dimension_id": "simplicity-abstraction-duplication-changeability",
          "finding_id": "W03",
          "priority": "P1",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "architectural-fit-ownership-single-sources",
          "finding_id": "W04",
          "priority": "P1",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "significant-decision-documentation",
          "finding_id": "W05",
          "priority": "P1",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "readability-naming-error-contracts",
          "finding_id": "W06",
          "priority": "P1",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "separation-of-concerns",
          "finding_id": "W07",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "significant-decision-documentation",
          "finding_id": "W08",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "readability-naming-error-contracts",
          "finding_id": "W09",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "readability-naming-error-contracts",
          "finding_id": "W10",
          "priority": "P3",
          "resolved": false
        }
      ]
    },
    {
      "accepted": false,
      "applicable_dimensions": {
        "boundary-types-serialization-numeric-time": 5.5,
        "caller-enum-consumer-completeness": 6.5,
        "intent-behavior-completeness": 7.0,
        "side-effects-errors-resource-lifecycle": 7.0,
        "state-data-invariants-transactions-concurrency": 6.5
      },
      "cycle": 3,
      "delta_check": null,
      "derived_overall": 6.5,
      "failing_dimensions": [
        "state-data-invariants-transactions-concurrency",
        "boundary-types-serialization-numeric-time",
        "caller-enum-consumer-completeness"
      ],
      "lens_id": "correctness",
      "non_applicable_dimensions": {},
      "reviewed_revision": "053ef43881c2db7d7cee64845e5563a5b73eb43e",
      "score_accepted": false,
      "scoring_findings": [
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "side-effects-errors-resource-lifecycle",
          "finding_id": "X01",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "caller-enum-consumer-completeness",
          "finding_id": "X02",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "state-data-invariants-transactions-concurrency",
          "finding_id": "X03",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "intent-behavior-completeness",
          "finding_id": "X04",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "intent-behavior-completeness",
          "finding_id": "X05",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "caller-enum-consumer-completeness",
          "finding_id": "X06",
          "priority": "P1",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "state-data-invariants-transactions-concurrency",
          "finding_id": "X07",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "boundary-types-serialization-numeric-time",
          "finding_id": "X08",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "boundary-types-serialization-numeric-time",
          "finding_id": "X09",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "side-effects-errors-resource-lifecycle",
          "finding_id": "X10",
          "priority": "P3",
          "resolved": false
        }
      ]
    },
    {
      "accepted": false,
      "applicable_dimensions": {
        "authentication-authorization-tenant-isolation": 7.5,
        "confidentiality-logs-errors-egress": 7.5,
        "dependency-supply-chain": 7.0,
        "input-trust-boundaries-injection": 8.0
      },
      "cycle": 3,
      "delta_check": null,
      "derived_overall": 7.5,
      "failing_dimensions": [],
      "lens_id": "security",
      "non_applicable_dimensions": {
        "secrets-cryptography-session-handling": "the change introduces no secret material, credential, session issuance or cryptographic control; the only primitive is a content digest carried over unchanged, and uuidgen mints a correlation id rather than an authorization token"
      },
      "reviewed_revision": "053ef43881c2db7d7cee64845e5563a5b73eb43e",
      "score_accepted": false,
      "scoring_findings": [
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "confidentiality-logs-errors-egress",
          "finding_id": "V01",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "authentication-authorization-tenant-isolation",
          "finding_id": "V02",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "input-trust-boundaries-injection",
          "finding_id": "V03",
          "priority": "P3",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "input-trust-boundaries-injection",
          "finding_id": "V04",
          "priority": "P3",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "input-trust-boundaries-injection",
          "finding_id": "V05",
          "priority": "P3",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "confidentiality-logs-errors-egress",
          "finding_id": "V06",
          "priority": "P3",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "dependency-supply-chain",
          "finding_id": "V07",
          "priority": "P3",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "authentication-authorization-tenant-isolation",
          "finding_id": "V08",
          "priority": "P3",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "input-trust-boundaries-injection",
          "finding_id": "V09",
          "priority": "P3",
          "resolved": false
        }
      ]
    },
    {
      "accepted": false,
      "applicable_dimensions": {
        "behavior-sensitive-assertions": 6.5,
        "determinism-isolation-diagnostics-maintainability": 7.0,
        "negative-edge-state-concurrency-time": 7.0,
        "realistic-seams-mocks-integration-evidence": 7.5,
        "requirements-regression-coverage": 6.5
      },
      "cycle": 3,
      "delta_check": null,
      "derived_overall": 6.9,
      "failing_dimensions": [
        "requirements-regression-coverage",
        "behavior-sensitive-assertions"
      ],
      "lens_id": "testing",
      "non_applicable_dimensions": {},
      "reviewed_revision": "053ef43881c2db7d7cee64845e5563a5b73eb43e",
      "score_accepted": false,
      "scoring_findings": [
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "negative-edge-state-concurrency-time",
          "finding_id": "Z01",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "requirements-regression-coverage",
          "finding_id": "Z02",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "behavior-sensitive-assertions",
          "finding_id": "Z03",
          "priority": "P3",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "determinism-isolation-diagnostics-maintainability",
          "finding_id": "Z04",
          "priority": "P3",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "realistic-seams-mocks-integration-evidence",
          "finding_id": "Z05",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "requirements-regression-coverage",
          "finding_id": "Z06",
          "priority": "P3",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "negative-edge-state-concurrency-time",
          "finding_id": "Z07",
          "priority": "P3",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "behavior-sensitive-assertions",
          "finding_id": "Z08",
          "priority": "P3",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "requirements-regression-coverage",
          "finding_id": "Z09",
          "priority": "P3",
          "resolved": false
        }
      ]
    },
    {
      "accepted": false,
      "applicable_dimensions": {
        "interface-contract-compatibility": 6.0,
        "retry-idempotency-semantics": 8.5,
        "sdk-generated-client-impact": 7.0,
        "serialization-errors": 5.5,
        "specification-documentation-parity": 6.5,
        "versioning-deprecation": 7.0
      },
      "cycle": 3,
      "delta_check": null,
      "derived_overall": 6.75,
      "failing_dimensions": [
        "interface-contract-compatibility",
        "serialization-errors",
        "specification-documentation-parity"
      ],
      "lens_id": "api-contract",
      "non_applicable_dimensions": {
        "pagination-rate-limits": "no paged collection, cursor, quota or throttled interface exists anywhere in this change; the nearest analogue, agent-spawn concurrency, moved with the emitter in unit U4 and is unchanged at this revision"
      },
      "reviewed_revision": "053ef43881c2db7d7cee64845e5563a5b73eb43e",
      "score_accepted": false,
      "scoring_findings": [
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "interface-contract-compatibility",
          "finding_id": "Q01",
          "priority": "P1",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "interface-contract-compatibility",
          "finding_id": "Q02",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "interface-contract-compatibility",
          "finding_id": "Q03",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "serialization-errors",
          "finding_id": "Q04",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "serialization-errors",
          "finding_id": "Q05",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "specification-documentation-parity",
          "finding_id": "Q06",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "serialization-errors",
          "finding_id": "Q07",
          "priority": "P3",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "serialization-errors",
          "finding_id": "Q08",
          "priority": "P3",
          "resolved": false
        }
      ]
    },
    {
      "accepted": false,
      "applicable_dimensions": {
        "capability-parity-reachability": 6.5,
        "context-constraints-acceptance-examples": 7.5,
        "discoverability-invocation-schemas": 6.0,
        "machine-readable-output-actionable-errors": 7.5,
        "safe-bounded-idempotent-resumable-context-cost": 6.5
      },
      "cycle": 3,
      "delta_check": null,
      "derived_overall": 6.8,
      "failing_dimensions": [
        "capability-parity-reachability",
        "discoverability-invocation-schemas",
        "safe-bounded-idempotent-resumable-context-cost"
      ],
      "lens_id": "agent-usability",
      "non_applicable_dimensions": {},
      "reviewed_revision": "053ef43881c2db7d7cee64845e5563a5b73eb43e",
      "score_accepted": false,
      "scoring_findings": [
        {
          "confidence": 100,
          "critical": true,
          "dimension_id": "safe-bounded-idempotent-resumable-context-cost",
          "finding_id": "Y01",
          "priority": "P1",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "machine-readable-output-actionable-errors",
          "finding_id": "Y02",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "context-constraints-acceptance-examples",
          "finding_id": "Y03",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "discoverability-invocation-schemas",
          "finding_id": "Y04",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "discoverability-invocation-schemas",
          "finding_id": "Y05",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "capability-parity-reachability",
          "finding_id": "Y06",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "capability-parity-reachability",
          "finding_id": "Y07",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "discoverability-invocation-schemas",
          "finding_id": "Y08",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "context-constraints-acceptance-examples",
          "finding_id": "Y09",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "safe-bounded-idempotent-resumable-context-cost",
          "finding_id": "Y10",
          "priority": "P3",
          "resolved": false
        }
      ]
    },
    {
      "accepted": false,
      "applicable_dimensions": {
        "completeness-audience-prerequisites": 6.5,
        "runbook-safety-rollback-links-generated-drift": 6.0,
        "runnable-examples-actionability": 6.5,
        "shipped-behavior-parity": 6.0,
        "structure-navigation": 8.0,
        "terminology-cross-document-consistency": 6.0
      },
      "cycle": 3,
      "delta_check": null,
      "derived_overall": 6.5,
      "failing_dimensions": [
        "shipped-behavior-parity",
        "completeness-audience-prerequisites",
        "terminology-cross-document-consistency",
        "runnable-examples-actionability",
        "runbook-safety-rollback-links-generated-drift"
      ],
      "lens_id": "documentation-clarity",
      "non_applicable_dimensions": {},
      "reviewed_revision": "053ef43881c2db7d7cee64845e5563a5b73eb43e",
      "score_accepted": false,
      "scoring_findings": [
        {
          "confidence": 100,
          "critical": true,
          "dimension_id": "terminology-cross-document-consistency",
          "finding_id": "N01",
          "priority": "P1",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": true,
          "dimension_id": "shipped-behavior-parity",
          "finding_id": "N02",
          "priority": "P1",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": true,
          "dimension_id": "runbook-safety-rollback-links-generated-drift",
          "finding_id": "N03",
          "priority": "P1",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": true,
          "dimension_id": "completeness-audience-prerequisites",
          "finding_id": "N04",
          "priority": "P1",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "runbook-safety-rollback-links-generated-drift",
          "finding_id": "N05",
          "priority": "P1",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "shipped-behavior-parity",
          "finding_id": "N06",
          "priority": "P1",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "completeness-audience-prerequisites",
          "finding_id": "N07",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "completeness-audience-prerequisites",
          "finding_id": "N08",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "terminology-cross-document-consistency",
          "finding_id": "N09",
          "priority": "P3",
          "resolved": false
        }
      ]
    }
  ],
  "next_action": "continue_with_best_available",
  "outcome": "cycle_cap_best_available",
  "residual_summary": {
    "final_lens_scores": {
      "agent-usability": {
        "accepted": false,
        "delta_check": null,
        "derived_overall": 6.8,
        "failing_dimensions": [
          "capability-parity-reachability",
          "discoverability-invocation-schemas",
          "safe-bounded-idempotent-resumable-context-cost"
        ],
        "reviewed_revision": "053ef43881c2db7d7cee64845e5563a5b73eb43e"
      },
      "api-contract": {
        "accepted": false,
        "delta_check": null,
        "derived_overall": 6.75,
        "failing_dimensions": [
          "interface-contract-compatibility",
          "serialization-errors",
          "specification-documentation-parity"
        ],
        "reviewed_revision": "053ef43881c2db7d7cee64845e5563a5b73eb43e"
      },
      "architecture-maintainability": {
        "accepted": false,
        "delta_check": null,
        "derived_overall": 5.214285714285714,
        "failing_dimensions": [
          "architectural-fit-ownership-single-sources",
          "separation-of-concerns",
          "dependency-direction",
          "simplicity-abstraction-duplication-changeability",
          "readability-naming-error-contracts",
          "conventions-portability-configuration",
          "significant-decision-documentation"
        ],
        "reviewed_revision": "053ef43881c2db7d7cee64845e5563a5b73eb43e"
      },
      "correctness": {
        "accepted": false,
        "delta_check": null,
        "derived_overall": 6.5,
        "failing_dimensions": [
          "state-data-invariants-transactions-concurrency",
          "boundary-types-serialization-numeric-time",
          "caller-enum-consumer-completeness"
        ],
        "reviewed_revision": "053ef43881c2db7d7cee64845e5563a5b73eb43e"
      },
      "documentation-clarity": {
        "accepted": false,
        "delta_check": null,
        "derived_overall": 6.5,
        "failing_dimensions": [
          "shipped-behavior-parity",
          "completeness-audience-prerequisites",
          "terminology-cross-document-consistency",
          "runnable-examples-actionability",
          "runbook-safety-rollback-links-generated-drift"
        ],
        "reviewed_revision": "053ef43881c2db7d7cee64845e5563a5b73eb43e"
      },
      "security": {
        "accepted": false,
        "delta_check": null,
        "derived_overall": 7.5,
        "failing_dimensions": [],
        "reviewed_revision": "053ef43881c2db7d7cee64845e5563a5b73eb43e"
      },
      "testing": {
        "accepted": false,
        "delta_check": null,
        "derived_overall": 6.9,
        "failing_dimensions": [
          "requirements-regression-coverage",
          "behavior-sensitive-assertions"
        ],
        "reviewed_revision": "053ef43881c2db7d7cee64845e5563a5b73eb43e"
      }
    },
    "review_incomplete_reason": null,
    "score_regressions": [
      {
        "current_overall": 4.928571428571429,
        "current_revision": "76533cbeba4007cb89e9acf5842027d24cda99de",
        "cycle": 2,
        "lens_id": "architecture-maintainability",
        "previous_overall": 7.428571428571429,
        "previous_revision": "5ec8ea7682706aa9f06e359c373cfd2032ee6ba9"
      },
      {
        "current_overall": 6.8,
        "current_revision": "76533cbeba4007cb89e9acf5842027d24cda99de",
        "cycle": 2,
        "lens_id": "correctness",
        "previous_overall": 8.4,
        "previous_revision": "5ec8ea7682706aa9f06e359c373cfd2032ee6ba9"
      },
      {
        "current_overall": 6.583333333333333,
        "current_revision": "76533cbeba4007cb89e9acf5842027d24cda99de",
        "cycle": 2,
        "lens_id": "api-contract",
        "previous_overall": 7.5,
        "previous_revision": "5ec8ea7682706aa9f06e359c373cfd2032ee6ba9"
      },
      {
        "current_overall": 6.5,
        "current_revision": "053ef43881c2db7d7cee64845e5563a5b73eb43e",
        "cycle": 3,
        "lens_id": "correctness",
        "previous_overall": 6.8,
        "previous_revision": "76533cbeba4007cb89e9acf5842027d24cda99de"
      },
      {
        "current_overall": 6.9,
        "current_revision": "053ef43881c2db7d7cee64845e5563a5b73eb43e",
        "cycle": 3,
        "lens_id": "testing",
        "previous_overall": 7.3,
        "previous_revision": "76533cbeba4007cb89e9acf5842027d24cda99de"
      },
      {
        "current_overall": 6.5,
        "current_revision": "053ef43881c2db7d7cee64845e5563a5b73eb43e",
        "cycle": 3,
        "lens_id": "documentation-clarity",
        "previous_overall": 6.916666666666667,
        "previous_revision": "76533cbeba4007cb89e9acf5842027d24cda99de"
      }
    ],
    "unresolved_fix_ids": [
      "fix-b5b1cf54bd9e",
      "fix-9e3a294949a8",
      "fix-77bb21ac351e",
      "fix-640332b3460b",
      "fix-111b3a5ba6bf",
      "fix-e37ed06c14a3",
      "fix-e84d08faaae9",
      "fix-d954059184c4",
      "fix-aeb801cf93a4",
      "fix-2b465af21a75",
      "fix-79b89f62dfaf",
      "fix-884d9322d0b8",
      "fix-52a145d37865",
      "fix-31db917d5077",
      "fix-f6054d24ef3a",
      "fix-87eaea4a209e",
      "fix-052d76cce82b",
      "fix-9e622b08b047",
      "fix-22d6efb8abe2",
      "fix-c0968b07f9e0",
      "fix-f3a3ac0178de",
      "fix-61319972cc18",
      "fix-31f8c6081fcc",
      "fix-5bd1d98b52fb",
      "fix-7ce7e909ff55",
      "fix-e024cd2b6ff4",
      "fix-6667f5be6029",
      "fix-1c0cb019d7a8",
      "fix-24db8e598169"
    ]
  },
  "resume_transitions": [
    "continue_with_best_available"
  ],
  "revision_binding": {
    "best_available_revision": "053ef43881c2db7d7cee64845e5563a5b73eb43e",
    "lens_revisions": {
      "agent-usability": "053ef43881c2db7d7cee64845e5563a5b73eb43e",
      "api-contract": "053ef43881c2db7d7cee64845e5563a5b73eb43e",
      "architecture-maintainability": "053ef43881c2db7d7cee64845e5563a5b73eb43e",
      "correctness": "053ef43881c2db7d7cee64845e5563a5b73eb43e",
      "documentation-clarity": "053ef43881c2db7d7cee64845e5563a5b73eb43e",
      "security": "053ef43881c2db7d7cee64845e5563a5b73eb43e",
      "testing": "053ef43881c2db7d7cee64845e5563a5b73eb43e"
    }
  },
  "schema": "review_result.v1",
  "selected_lenses": [
    "architecture-maintainability",
    "correctness",
    "security",
    "testing",
    "api-contract",
    "agent-usability",
    "documentation-clarity"
  ],
  "unresolved_fix_ids": [
    "fix-b5b1cf54bd9e",
    "fix-9e3a294949a8",
    "fix-77bb21ac351e",
    "fix-640332b3460b",
    "fix-111b3a5ba6bf",
    "fix-e37ed06c14a3",
    "fix-e84d08faaae9",
    "fix-d954059184c4",
    "fix-aeb801cf93a4",
    "fix-2b465af21a75",
    "fix-79b89f62dfaf",
    "fix-884d9322d0b8",
    "fix-52a145d37865",
    "fix-31db917d5077",
    "fix-f6054d24ef3a",
    "fix-87eaea4a209e",
    "fix-052d76cce82b",
    "fix-9e622b08b047",
    "fix-22d6efb8abe2",
    "fix-c0968b07f9e0",
    "fix-f3a3ac0178de",
    "fix-61319972cc18",
    "fix-31f8c6081fcc",
    "fix-5bd1d98b52fb",
    "fix-7ce7e909ff55",
    "fix-e024cd2b6ff4",
    "fix-6667f5be6029",
    "fix-1c0cb019d7a8",
    "fix-24db8e598169"
  ]
}
```
