---
title: Code Review owns review consensus; Orchestrate routes and Work mutates
type: feat
status: active
date: 2026-08-19
origin: docs/plans/2026-08-19-review-consensus-ownership-and-orchestrate-defects-plan.md
backend: inline
---

# Code Review owns review consensus; Orchestrate routes and Work mutates

## Summary

Move every review-acceptance decision into Saga's Code Review skill — one versioned fourteen-lens
roster, per-lens dimensions, a derived overall score, two thresholds, a three-cycle loop and a typed
result — and make Team Execution, Work and Orchestrate consume it instead of each carrying a private
copy. Alongside it, repair the three Orchestrate run-integrity defects that made a live run
unlandable.

## Problem Frame

Every surface in the review path states a review policy that nothing enforces, and Orchestrate was
left improvising the gap by hand. The upstream audit (`origin`) records 25 defects with file-and-line
evidence. Three facts from that audit drive this plan:

Code Review has **no numeric scoring at all** — searching the skill for `9.0`, `7.0`, `/10` and
`score` returns nothing, its verdict is binary `blocked`/`clean`, and `SKILL.md:250` escalates gated
consensus *to* Team Execution. Team Execution **has** the thresholds but cannot enforce them: its
helper accepts an empty dimension map, so the per-dimension floor never fires, and it trusts whatever
overall the caller reports.

On the live run that exposed this, one reviewer returned zero findings on a 15,400-line diff while
another returned four independently confirmed defects, and nothing could adjudicate the split. The
orchestrating session read the source itself, invented a triage that dropped a finding, and was
corrected by the operator. The repaired code was never re-reviewed, because no loop exists.

---

## Requirements

### Ownership and policy

R1. Saga Code Review is the single owner of the lens roster, dimensions, derived per-lens overall
scores, acceptance thresholds, fix consolidation, selective failing-lens reruns, three-cycle state,
and the final structured result.

R2. Acceptance is overall at least 9.0 **and** no applicable dimension below 7.0. These are the only
review acceptance thresholds.

R3. Every selected lens must supply at least one applicable dimension score. A selected lens with zero
applicable dimensions is invalid.

R4. The overall is the arithmetic mean of the applicable dimensions. A reported overall that
contradicts its dimensions is rejected.

R5. Each non-applicable dimension carries an explicit recorded cause.

R6. After the third unsuccessful cycle the loop stops, proceeds with the best available revision, and
reports every final lens score and every unresolved fix. This is not a human-halt condition.

R7. No second acceptance or terminal threshold exists. The below-5.0 terminal stop is deleted rather
than ported; a destructive or unrecoverable failure is caught by the R2 per-dimension floor.

R8. Priority and confidence remain finding metadata and routing information, never a second review
acceptance gate.

R9. Code Review never mutates reviewed code. Work is the only mutator.

R10. Scanner, test, deployment, casualty and operational-safety gates remain independently
authoritative and are never folded into the score.

### The canonical roster

R11. One versioned machine-readable roster is the single source of truth, consumed by Code Review and
Team Execution. No second roster exists anywhere in the repository.

R12. The roster carries fourteen lenses: four always-on — `correctness`, `security`, `testing`,
`architecture-maintainability` — and ten conditional — `deployment-infrastructure`, `reliability`,
`performance`, `api-contract`, `adversarial`, `privacy`, `documentation-clarity`, `agent-usability`,
`previous-comments`, `accessibility-human-usability`.

R13. Every conditional lens is selected by judgment with a recorded one-line reason. Keyword matching
alone is not a valid trigger.

R14. Lens identifiers are stable. `api-contract` keeps its identifier while its documented scope
broadens to Hypertext Transfer Protocol, events, command-line interfaces, configuration, exported
types and file formats.

R15. Team Execution's non-scoring external advisory seat keeps its exclusion from the consensus
denominator, the 9.0 acceptance and the 7.0 floor.

R16. Deduplication by fingerprint and cross-reviewer agreement are preserved, so overlap between
lenses strengthens evidence without double-counting a finding.

### The typed result

R17. Code Review emits a typed result carrying: selected and attempted lens identifiers; the revision
each lens reviewed; applicable dimensions; the derived overall; verdict; findings; cycle history; the
failing-lens set; consolidated structured fix requests; unresolved fix identifiers; the best-available
revision; a residual summary; and the next action.

R18. The outcome is exactly one of `accepted`, `repairs_requested`, `cycle_cap_best_available`,
`review_incomplete`.

R19. Accepted lenses are not rerun and retain the revision they actually reviewed.

R20. Best available is the latest successfully integrated revision reviewed in cycle three. No
cross-cycle score ranking is computed, because accepted lenses retain scores against different
revisions and the totals are not comparable.

R21. Delivery failure after bounded retries yields `review_incomplete`: no fabricated score, and no
scoring cycle consumed.

R22. To Orchestrate the typed result is opaque. Orchestrate reads only routing fields — `owner`,
touched paths, outcome — and never derives, recomputes or second-guesses a score, threshold, verdict
or cycle count.

### Consumers

R23. Team Execution consumes the roster and the transition engine, retaining transport,
evidence-based settlement, liveness, advisory seats, scanners and worker coordination.

R24. Team Execution's settlement stays evidence-based: a typed result is evidence to be validated, not
a claim to be trusted.

R25. Work drops its own Priority 0/1 hard gate and reads Code Review's acceptance.

R26. A review phase is one top-level Code Review controller invocation, not N units each running a
full review.

R27. Orchestrate persists the typed result, maps fix requests to responsible existing Work workers
where one matches, lands the updated revision, and resubmits to Code Review.

R28. Cross-vendor reviewer diversity lives in Code Review's non-scoring external-reviewer seat.
External-reviewer identity, request, typed evidence, adjudication and lifecycle semantics belong to
Code Review; launch and collection are a replaceable transport.

### Orchestrate run integrity

R29. `land` merges inside a throwaway worktree created on the run branch. It never checks out the
operator's tree and never refuses because that tree is dirty.

R30. A successful `land` removes its worktree. A conflicting `land` retains it and reports its
location, and the cleanup path recognises a retained conflict worktree.

R31. The run branch is resolved once at load. When it does not resolve, the failure is reported
loudly rather than each predicate independently answering False.

R32. The delivery-failure note is surfaced in `status`, appended rather than overwritten, and cleared
on the unit's first commit. `check` reports a unit carrying the warning with no commits.

R33. `status` renders one row per unit with no column overflow on a 21-character model name and no
raw newlines from task text, and shows commit count and landed state.

R34. `settle` is unchanged. A delivery warning plus zero commits does not hold a unit at running.

### Tests and release

R35. Behavioural tests cover roster parity, required dimensions, derived-score validation, the exact
thresholds at their boundaries, selective reruns, no fourth cycle, cycle-cap residuals, independent
safety gates, worker reuse and replacement, state reload, and one end-to-end flow in a real temporary
Git repository.

R36. Every touched plugin updates `plugins/<plugin>/.claude-plugin/plugin.json`,
`.claude-plugin/marketplace.json` and its `CHANGELOG.md` in the same pull request as the change.

R37. `scripts/gate.sh` is green before any push.

---

## Key Technical Decisions

**KTD1 — Scoring is Python under `plugins/saga/scripts/`, not skill prose.** Code Review ships zero
Python and zero tests today; it is a markdown skill that already drives six saga helpers
(`engine_offer.py`, `engine_session_runner.py`, `evidence_ledger.py`, `manifest_reader.py`, `saga.py`,
`status_card.py`). A derived mean, a contradiction check, two thresholds and a cycle counter stated in
prose are exactly what Team Execution has today — and defects T2 and T3 are the proof that unenforced
prose drifts from its implementation. Rejected: markdown-only instructions, because they cannot be
tested and the repository's own history shows they do not hold.

**KTD2 — The roster is versioned JSON at `plugins/saga/references/lens-roster.json`.**
`plugins/saga/references/bridge-signatures.json` is the existing precedent for a cross-surface
machine-readable contract and opens with `"schema": "bridge_signatures.v1"`; the roster follows with
`"schema": "lens_roster.v1"`. It lives under `plugins/saga/references/` rather than under the
code-review skill because Team Execution must read it too. Rejected: duplicating it per consumer,
which is defect T1 restated.

**KTD3 — Fourteen lenses, the union plus accessibility.** Operator-approved, amended from a
thirteen-lens draft. The union preserves four lenses that had no Team Execution reviewer
(`correctness`, `reliability`, `performance`, `previous-comments`) and three reviewers that had no
Code Review lens (`privacy`, `clarity`, architecture as distinct from maintainability), and adds
`accessibility-human-usability`. Rejected: an intersection, which would delete `correctness` — the
always-on lens that catches silent breakage.

**KTD4 — Conditional triggers are judgment with a recorded reason.** Keyword matching against a plan
document cannot see what the code actually touched. Rejected: Team Execution's current keyword table,
which is why its reviewer set and Code Review's lens set drifted apart without anything noticing.

**KTD5 — The per-dimension 7.0 floor is the only mechanism preventing a destructive finding being
averaged away.** No override threshold is added. A destructive-failure dimension scoring below 7.0
already blocks acceptance regardless of how the mean is pulled. Rejected: a special destructive-finding
override, which would be a second terminal gate.

**KTD6 — The below-5.0 terminal stop is deleted, not ported.** Arithmetically it changes no
acceptance, since 4.9 is already below 7.0 and its own release condition is that same 7.0. Its only
distinct effect — "no completion until that dimension reaches >= 7.0" — forbids the termination R6
requires. Its routing half survives as fix-request priority.

**KTD7 — Best available is the latest successfully integrated revision reviewed in cycle three.**
Rejected: highest-scoring across cycles. Because R19 keeps accepted lenses on the revision they
reviewed, a cycle-three result is a mosaic across revisions and the totals are not comparable; any
ranking would need a tie-break policy invented at the moment the loop has already failed three times.

**KTD8 — Cross-vendor diversity stays in the non-scoring external-reviewer seat, behind a transport
seam.** Code Review owns identity, request, typed evidence, adjudication and lifecycle;
`plugins/saga/scripts/engine_session_runner.py` is the planned transport and is replaceable. Rejected:
letting the second seat score, which reopens denominator and quorum questions R2 avoids; and rejected:
dropping diversity, against which the 0-versus-4 finding split is direct evidence.

**KTD9 — `land` moves into a throwaway worktree; `collect` is untouched.** `land` merges unit branches
onto the run branch and never needs the operator's tree — its `git checkout` is gratuitous. `collect`
exists to merge into that tree, so a worktree cannot help it and its refusal is git's constraint, not
an Orchestrate invention. Rejected: a promote-and-push exit, which is new capability rather than
defect repair.

**KTD10 — `settle` is unchanged; the delivery warning is surfaced, not gating.** The 15-second
delivery window produced two false positives out of two on the only measured run, and one flagged unit
never committed on its own — under a stricter rule it would have stalled at running in an unwatched
tab. Rejected: holding a unit at running on warning-plus-no-commits.

**KTD11 — One top-level Code Review controller; the typed result is opaque to Orchestrate.** Replaces
the N-units-per-reviewer shape at `plugins/orchestrate/commands/orchestrate.md:27,112` and
`plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py:457`. Rejected: restoring the archived
Orchestrate consensus panel.

**KTD13 — The execution backend is `inline`, overriding the recommender.**
`lifecycle_state.py recommend-backend` returned `team-execution` on the size trigger alone —
roughly 30 functional files once release bookkeeping is subtracted. Overridden for two reasons the
heuristic cannot see. First, **circularity**: U7 rewrites Team Execution's consensus helper, so using
`team-execution` as the standing gate would mean a failing consensus check might be the code under
repair rather than the code under review, with no way to tell which. Second, **shape**: the eleven
units are almost entirely dependency-chained (U4 gates U5 gates U6 gates U7/U8/U9 gates U10), leaving
little parallelism for a fan-out backend. Rejected: `cc-workflows-ultracode`, which serves breadth or
independent-attempt confidence, neither of which this work needs. The standing-verdict cost is
mitigated inside the plan rather than by the backend — U10's end-to-end flow runs in a real Git
repository with no mock for git, the roster or scoring, and `scripts/gate.sh` gates every push.

**KTD12 — Lens identifiers are stable across scope changes.** `api-contract` broadens without
renaming, so stored results and roster-parity tests survive. Rejected: renaming to match new scope,
which would break every prior result.

---

## High-Level Technical Design

```
Code Review (read-only, owns policy+state)
     |  typed result (opaque to callers)
     v
Orchestrate  -- fix requests by owner/paths -->  Work (the only mutator)
     ^                                              |
     |                 lands the revision           |
     +----------------- resubmit <------------------+

Team Execution --reads--> lens-roster.json <--reads-- Code Review
```

Three artifacts carry the contract. `plugins/saga/references/lens-roster.json` is the roster.
`plugins/saga/scripts/review_consensus.py` is the scoring and cycle engine. The typed result is the
serialized output both Orchestrate and Team Execution consume without interpreting.

### Lens dimensions

Each lens scores the dimensions below. Only applicable dimensions are scored; each non-applicable
dimension records an explicit cause (R5), and a lens with zero applicable dimensions is invalid (R3).

`correctness` — intent and behaviour completeness; state and data invariants, transactions,
concurrency and state transitions; boundary types, serialization, numeric and time handling; side
effects, errors and resource lifecycle; exhaustive callers and enum consumers.

`security` — authentication, authorization, tenant isolation and default-deny; input trust boundaries
including injection, server-side request forgery, paths, deserialization and prompt injection; secrets,
cryptography and session handling; dependency and supply-chain provenance, pinning and vulnerabilities;
confidentiality and exposure through logs, errors and egress. Privacy policy concerns stay in
`privacy` and are not diluted here.

`testing` — requirements and regression behaviour; negative, edge, state, concurrency and time cases;
assertions that would fail on behaviour change; realistic seams, mocks, integration and behavioural
evidence; determinism, isolation, diagnostics and maintainability. The universal ninety-percent
coverage rule is deleted — repository-specific gates and behaviour risk govern, because a percentage
is not proof.

`architecture-maintainability` — architectural fit, ownership and single sources of truth; separation
and dependency direction; simplicity, abstraction, duplication and changeability; readability, naming
and error contracts; conventions, portability, configuration and significant-decision documentation.
Architecture-documentation dimensions may be excluded only with a recorded precondition absence.

`deployment-infrastructure` — infrastructure and configuration correctness plus least privilege;
migrations, backfills, compatibility and rollout order; rollback, reversibility and drift; cost and
resilience; deployed-state verification and infrastructure observability. Both source domains are
preserved as applicable subprofiles rather than flattened.

`reliability` — timeouts, retries, circuit breakers and idempotency; queues, jobs, dead letters,
ordering and backpressure; concurrency, partial failure and recovery; graceful degradation,
cancellation and cleanup; health signals, logs, metrics, traces, alerts and runbook or service-level
evidence.

`performance` — measured latency and throughput; algorithmic and query or index cost; input-output
batching, concurrency and waterfalls; memory and resource use; cache correctness and invalidation;
capacity and cost tradeoffs. An unsupported performance claim is a finding.

`api-contract` — interface and contract compatibility across Hypertext Transfer Protocol, events,
command-line interfaces, configuration, exported types and file formats; versioning and deprecation;
serialization and errors; retry and idempotency semantics; pagination and rate limits; software
development kit and generated-client impact; specification and documentation parity.

`adversarial` — load-bearing assumptions; abuse and edge cases; failure amplification and silent-green
paths; environment or operator failure; scope and alternatives; recovery. Selected semantically for
authentication, money, mutations, external integrations, lifecycle or state-machine changes, policy
and gates, deployment and agent orchestration, plus large or complex diffs.

`privacy` — data-flow inventory and classification; minimization, purpose and consent; personal-data
protection, sharing and third parties; retention and deletion across primary stores, logs, caches and
backups; portability, residency and legal flags; artificial-intelligence, telemetry and training use
including re-identification risk.

`documentation-clarity` — parity with shipped behaviour; completeness, audience and prerequisites;
structure and navigation; terminology and cross-document consistency; runnable examples and
actionability; runbook safety, rollback, links and generated-document drift.

`agent-usability` — capability parity and reachability through tool, command-line,
application-programming and skill surfaces; discoverability and invocation schemas; explicit context,
constraints, acceptance criteria and examples; deterministic machine-readable outputs and actionable
errors; safe bounded, idempotent, resumable operation with reasonable context cost. Both source
concerns are preserved rather than conflated.

`previous-comments` — selected only for a pull request carrying prior review. Inventory every
unresolved thread; map each to the current revision; verify resolution in code and tests rather than
accepting reply text; detect regressions; record an evidence-backed disposition.

`accessibility-human-usability` — semantic and assistive-technology support; keyboard and focus
behaviour; contrast, zoom, motion and responsiveness; labels, forms, loading, empty and error states;
localization and content resilience; discoverability, safe defaults and error recovery for
human-operated command surfaces. Runtime browser verification stays Quality Assurance work; this lens
reviews implementation quality before merge.

**No fifteenth domain exists.** Data integrity belongs in `correctness`, application observability in
`reliability`, infrastructure observability and cost in `deployment-infrastructure`, supply chain in
`security`, developer and operator experience in `accessibility-human-usability`. Product ambition
remains Founder Review's, not Code Review's.

---

## Implementation Units

Eleven units in four groups. The count exceeds the usual Deep guidance because the change spans four
plugins and 25 recorded defects; grouping into phases keeps it legible. Group A is independent of
everything else and lands first.

### U1. Land inside a throwaway worktree

`land` stops touching the operator's working tree, so a dirty checkout no longer blocks an entire run.

**Goal:** `land` merges unit branches onto the run branch without checking out or refusing.

**Requirements:** R29, R30.

**Dependencies:** none.

**Files:** `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py`;
`tests/test_orchestrate_land_worktree.py`.

**Approach:** replace the `git status --porcelain` refusal and the `git checkout r.branch` in
`cmd_land` with a worktree created on the run branch, merging there and removing it on success. On
conflict, retain the worktree, print its path, and record it so `reap` recognises a retained conflict
worktree rather than treating it as litter. The existing conflict message, which tells the operator to
finish the merge on the run branch, is rewritten to name the retained directory.

**Patterns to follow:** `make_worktree` in the same file already creates and names worktrees;
`cmd_clean`'s `reap` already distinguishes what may and may not be removed.

**Test scenarios:**

- Dirty tree, real repository, one unit ahead: run `land` — the merge succeeds and `git status`
  reports the same uncommitted files afterwards.
- Clean tree, two units ahead: run `land` — both merge, no worktree remains on disk.
- Conflicting unit branch: run `land` — exit 1, the retained worktree exists at the reported path, and
  the message names that path rather than the run branch.
- Retained conflict worktree present, then `clean --merged`: the retained worktree is recognised and
  not silently destroyed.
- `land` on a run whose branch does not resolve: fails loudly (shared with U2).

**Verification:** a land succeeds against a repository with uncommitted tracked changes and leaves
them untouched; a conflicting land leaves a directory the operator can resolve in.

### U2. Resolve the run branch once, and fail loudly

A renamed or deleted run branch stops silently turning every predicate False.

**Goal:** one resolution at load; an unresolvable run branch is an error, not a chorus of False.

**Requirements:** R31.

**Dependencies:** none.

**Files:** `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py`;
`tests/test_orchestrate_run_branch_resolution.py`.

**Approach:** resolve `r.branch` in `Run.load` using the existing `resolve_ref`. When it does not
resolve, report the missing branch by name and stop. `branch_produced_anything`, `landed_by_merge`,
`cmd_check`, `cmd_land` and `cmd_go`'s dependency gate then stop each independently answering False
on a failed `git merge-base`.

**Patterns to follow:** `resolve_ref` in the same file, already used at three call sites.

**Test scenarios:**

- Run branch renamed, four units each with commits: run `check` — it names the missing run branch and
  does not report `NO COMMITS` for any unit.
- Run branch renamed: run `go` with a dependent unit — it reports the missing branch rather than
  skipping the unit as having committed nothing.
- Run branch present and resolvable: every command behaves exactly as before.
- Run record with no `branch` field at all (legacy): the existing legacy path is preserved.

**Verification:** with the run branch renamed, no command reports a false negative about unit commits.

### U3. Honest unit reporting

The delivery warning becomes visible and self-healing, and `status` becomes readable.

**Goal:** surface what Orchestrate already detects, and stop the table breaking on real data.

**Requirements:** R32, R33, R34.

**Dependencies:** none.

**Files:** `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py`;
`tests/test_orchestrate_status_and_notes.py`.

**Approach:** append to `unit.note` rather than overwriting it, so the file-handover pointer survives
the delivery warning. Clear the delivery warning in `settle` once the unit has commits. Add a `check`
finding for a unit carrying the warning with no commits. Size `status` columns from the data, collapse
whitespace in the task excerpt, and add commit-count and landed columns. `settle`'s state machine is
unchanged.

**Patterns to follow:** `read_unit` already appends with `f"{unit.note}; {note}"`; `cmd_check` already
composes a findings list.

**Test scenarios:**

- Unit whose task was handed over as a file and which then trips the delivery check: both notes are
  present, neither overwritten.
- Unit with the delivery warning that later commits: after `settle`, the warning is gone.
- Unit with the delivery warning and no commits: `check` reports it and exits non-zero.
- `status` with a 21-character model name and a task containing newlines: one row per unit, no column
  overflow, no raw newline in the table.
- `settle` with a warned, zero-commit unit reading idle twice: the unit still becomes done.

**Verification:** the warning is visible from `status` and `check` without opening the run file, and
disappears once the unit produces work.

### U4. The canonical fourteen-lens roster

One versioned roster replaces two drifting ones.

**Goal:** a single machine-readable source of truth for lenses, triggers and dimensions.

**Requirements:** R1, R11, R12, R13, R14, R15, R16.

**Dependencies:** none.

**Files:** `plugins/saga/references/lens-roster.json`;
`plugins/saga/skills/code-review/references/lens-catalog.md`;
`tests/test_lens_roster.py`.

**Approach:** author the roster as `"schema": "lens_roster.v1"` carrying, per lens, a stable
identifier, an always-on or conditional trigger class, the trigger's judgment guidance, and its
dimension identifiers. `lens-catalog.md` becomes prose that points at the roster rather than a second
copy of it. The non-scoring external advisory seat is represented explicitly so its exclusion from the
denominator and both thresholds is data rather than prose.

**Patterns to follow:** `plugins/saga/references/bridge-signatures.json` for shape and schema-key
convention.

**Test scenarios:**

- Load the roster: exactly fourteen lenses, four always-on and ten conditional, identifiers matching
  R12 verbatim.
- Every lens declares at least one dimension.
- The advisory seat is marked non-scoring and excluded from the denominator.
- Roster parity: no other file in the repository declares a reviewer or lens roster.
- Schema key is `lens_roster.v1` and the file parses as JSON.

**Verification:** one roster exists, and a parity test fails if a second appears.

### U5. Dimensions, derived overall, and the acceptance rule

The arithmetic becomes code that can be tested rather than prose that drifts.

**Goal:** enforce R2 through R5 deterministically.

**Requirements:** R1, R2, R3, R4, R5, R7, R8, R10.

**Dependencies:** U4.

**Files:** `plugins/saga/scripts/review_consensus.py`; `tests/test_review_consensus.py`.

**Approach:** a module that takes per-lens dimension maps, refuses a selected lens with no applicable
dimensions, refuses a non-applicable dimension with no recorded cause, derives the arithmetic-mean
overall, rejects a reported overall that contradicts it, and applies exactly two thresholds. No
threshold beyond 9.0 and 7.0 exists anywhere in the module.

**Patterns to follow:** `plugins/team-execution/skills/team-execution/scripts/consensus_advisory.py`
for the frozen-dataclass and validation shape — while fixing the two defects it demonstrates.

**Test scenarios:**

- Lens with dimensions averaging 9.4, none below 7.0: accepted.
- Lens with overall 9.4 and one dimension at 6.9: rejected by the floor.
- Boundary: mean exactly 9.0 accepts; 8.9 does not. A dimension at exactly 7.0 accepts; 6.9 blocks.
- Lens with an empty dimension map: raises, rather than passing as Team Execution's helper does today.
- Reported overall 9.9 with dimensions averaging 7.0: rejected as contradictory.
- Non-applicable dimension with no cause: raises.
- A dimension at 4.9: blocks via the floor, with no separate code path and no additional threshold.
- Scanner, test and deployment gate results passed alongside: the score is unchanged by them.

**Verification:** searching the module for any numeric threshold returns only 9.0 and 7.0.

### U6. Cycle state, selective rerun, termination, and the typed result

The three-cycle loop and the contract Orchestrate consumes.

**Goal:** implement R6, R17 through R22 as state plus a serializable result.

**Requirements:** R1, R6, R17, R18, R19, R20, R21, R22, R28.

**Dependencies:** U5.

**Files:** `plugins/saga/scripts/review_consensus.py`;
`plugins/saga/skills/code-review/SKILL.md`;
`plugins/saga/skills/code-review/references/findings-schema.md`;
`tests/test_review_consensus_cycles.py`.

**Approach:** carry cycle state across rounds, rerun only failing lenses, retain each accepted lens's
reviewed revision, and terminate at three cycles with `cycle_cap_best_available` naming the latest
successfully integrated revision reviewed in cycle three. Serialize the typed result with all
fourteen required fields and exactly one of four outcomes. `SKILL.md` drops its escalation of gated
consensus to Team Execution and its Priority 0/1 gate language, and states the external-reviewer seam
— identity, request, typed evidence, adjudication and lifecycle are Code Review's, launch and
collection are a replaceable transport currently served by `engine_session_runner.py`; `findings-schema.md` gains the
serialization for the `autofix_class` and `owner` routing metadata it already describes.

**Patterns to follow:** `plugins/saga/scripts/evidence_ledger.py` for durable typed artifacts.

**Test scenarios:**

- Two lenses fail in cycle one, one in cycle two, none in cycle three: only failing lenses are rerun,
  and accepted lenses report the revision they reviewed, not the latest.
- Three cycles all failing: outcome is `cycle_cap_best_available`, best available is the cycle-three
  revision, and every final score and unresolved fix appears in residuals.
- A fourth cycle is never attempted.
- Cycle three regresses a previously higher-scoring lens: the regression is reported in residuals and
  nothing is gated on it.
- Reviewer delivery exhausts bounded retries: outcome is `review_incomplete`, the cycle counter is
  unchanged, and no score is present.
- The serialized result round-trips and carries all fourteen fields.
- An external-reviewer seat result is adjudicated by Code Review and excluded from the denominator
  and both thresholds, whatever transport produced it.

**Verification:** a caller can determine what to do next from the outcome alone, without recomputing
any score.

### U7. Team Execution consumes the roster, and its helper is corrected

The parallel roster and the two unenforceable rules go away together.

**Goal:** R23, R24, and the removal of the second terminal stop.

**Requirements:** R7, R11, R15, R23, R24.

**Dependencies:** U4, U5.

**Files:** `plugins/team-execution/skills/team-execution/references/reviewer-registry.md`;
`plugins/team-execution/skills/team-execution/references/consensus-protocol.md`;
`plugins/team-execution/skills/team-execution/references/review-criteria.md`;
`plugins/team-execution/skills/team-execution/references/andon-cord.md`;
`plugins/team-execution/skills/team-execution/references/validator-execution-order.md`;
`plugins/team-execution/skills/team-execution/SKILL.md`;
`plugins/team-execution/README.md`;
`plugins/team-execution/skills/team-execution/scripts/consensus_advisory.py`;
`tests/test_team_execution_consensus_advisory.py`;
`tests/test_team_execution_settlement_adapter.py`.

**Approach:** the reviewer registry stops defining a roster and reads `lens-roster.json`; the reviewer
agent files remain as the implementations behind the shared lens identifiers. `consensus_advisory.py`
requires at least one dimension per gated reviewer and derives the overall instead of trusting the
caller. The below-5.0 terminal stop is deleted from `consensus-protocol.md`; its routing half survives
as fix-request priority. The five conflicting cycle-three statements are reconciled to one, and
`andon-cord.md`'s miscitation of `consensus-protocol.md` is corrected. The settlement adapter fixture
that encodes an empty dimension map as valid is inverted.

**Patterns to follow:** the existing frozen-dataclass validation in the same module.

**Test scenarios:**

- Gated reviewer with an empty dimension map: rejected, where today it passes.
- Gated reviewer reporting 9.5 with dimensions averaging 7.2: rejected as contradictory.
- Advisory seat with any score: excluded from the denominator and from both thresholds.
- A dimension at 4.9 on a security reviewer: blocked by the 7.0 floor, and the module contains no
  `5.0` anywhere.
- Reviewer selection reads the shared roster: removing a lens from the roster removes it here.
- Settlement of a prose-only result: still `silent-no-op`.

**Verification:** exactly one roster in the repository, and one consistent cycle-cap statement.

### U8. Work drops its own review gate

The last duplicate acceptance rule is removed.

**Goal:** Work reads Code Review's acceptance instead of gating on Priority 0/1.

**Requirements:** R8, R9, R25.

**Dependencies:** U6.

**Files:** `plugins/saga/skills/work/SKILL.md`; `tests/test_work_review_gate.py`.

**Approach:** the hard gate at `work/SKILL.md:57` and section 5.3 reads the typed result's outcome
rather than counting Priority 0 and Priority 1 findings. The stale-review check is preserved — it is
about freshness, not acceptance.

**Patterns to follow:** Work already reads the code-review envelope programmatically.

**Test scenarios:**

- Typed result `accepted` with Priority 2 findings present: Work proceeds.
- Typed result `repairs_requested`: Work blocks.
- Typed result `cycle_cap_best_available`: Work proceeds and surfaces the residuals.
- Typed result `review_incomplete`: Work blocks and says the review did not run.
- Stale review: still blocks, unchanged.

**Verification:** no Priority-based acceptance decision remains in Work.

### U9. The Orchestrate review loop seam

One controller, an opaque result, repairs routed to existing workers, and resubmission.

**Goal:** R26, R27, and worker preservation.

**Requirements:** R22, R26, R27.

**Dependencies:** U6.

**Files:** `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py`;
`plugins/orchestrate/commands/orchestrate.md`;
`plugins/orchestrate/skills/orchestrate/SKILL.md`;
`tests/test_orchestrate_review_loop.py`.

**Approach:** a review phase becomes one Code Review controller unit rather than one unit per
reviewer. The typed result is persisted verbatim against the run and never parsed for policy.
Fix requests map to a responsible existing worker by `owner` and touched paths, falling back to a
replacement worker when none matches. After landing, the revision is resubmitted. Reaping no longer
removes a worker that carries an outstanding fix request.

**Patterns to follow:** `Run.save` for durable run state; `reapable` for the reaping predicate.

**Test scenarios:**

- Plan naming a review phase: exactly one review unit is created, not N.
- Typed result `repairs_requested` with two fix requests whose owners match two existing workers:
  both are dispatched to those workers, and neither worker was reaped.
- Fix request whose owner matches no live worker: a replacement is created.
- Typed result persisted and reloaded: byte-identical, and no score or threshold is recomputed.
- Outcome `accepted`: no repair is dispatched and no resubmission occurs.
- `clean --merged` with an outstanding fix request: the worker is kept.

**Verification:** the run record carries the review result and Orchestrate makes no policy decision
from it.

### U10. End-to-end flow in a real temporary Git repository

The one test that proves the chain rather than its parts.

**Goal:** R35's integration scenario.

**Requirements:** R35.

**Dependencies:** U1, U2, U3, U5, U6, U7, U8, U9.

**Files:** `tests/test_review_loop_end_to_end.py`.

**Approach:** build a real temporary Git repository with real branches, run a review that fails, route
a repair, land it, resubmit, and reach acceptance — with no mock standing in for git, the roster, or
the scoring module. This exists because defect T7 is a fixture that encoded the bug as valid input;
that fixture is inverted in U7 and this test is why the inversion holds.

**Patterns to follow:** `tests/test_orchestrate_launch_and_land.py`, which already builds a real
temporary Git repository.

**Test scenarios:**

- Failing review, one repair, resubmission, acceptance: the final outcome is `accepted` and the
  landed revision contains the repair.
- Three failing cycles: outcome is `cycle_cap_best_available` and residuals list every score.
- State reload mid-loop: the cycle counter and accepted-lens revisions survive.
- Independent safety gate failing while the score accepts: the gate still blocks.

**Verification:** the flow passes without any mock for git, the roster, or scoring.

### U11. Documentation and hygiene

Stale documentation and run-state litter, none of which blocks the other units.

**Goal:** R36 in documentation form, and the four hygiene defects.

**Requirements:** none behavioural; closes O11, O6, O7, O8.

**Dependencies:** none.

**Files:** `plugins/orchestrate/README.md`;
`plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py`;
`plugins/orchestrate/skills/orchestrate/SKILL.md`;
`tests/test_orchestrate_hygiene.py`.

**Approach:** rewrite the README to the two modules the plugin actually ships, removing the six
citations to deleted modules. Write `.orchestrate/` to `.git/info/exclude` at `start`. Point
hand-authored briefs at `.orchestrate/tasks/`. Warn when a branch appears in the run namespace with no
unit.

**Patterns to follow:** the skill already teaches a `.git/info/attributes` append for union merges —
the same local, uncommitted mechanism.

**Test scenarios:**

- `start` in a repository with no exclude entry: `.orchestrate/` is excluded afterwards and the file's
  prior contents are preserved.
- `start` run twice: the exclude entry is not duplicated.
- Branch in the run namespace with no unit: `check` warns.
- README cites no module the plugin does not ship.

**Verification:** a fresh run leaves no untracked run state in the driven repository.

---

## Scope Boundaries

**Out of scope — not doing this, and not later either.** Restoring the archived Orchestrate consensus
panel or review loop. Adding any review acceptance or terminal threshold beyond 9.0 and 7.0. Making
Priority or confidence a gate. Letting the external-reviewer seat score. Changing scanner, test,
deployment, casualty or operational-safety gates, which stay independently authoritative.

**Out of scope — a known limitation, recorded rather than fixed.** `collect` still requires a clean
operator working tree. That is git's constraint for a merge into the tree, not an Orchestrate defect,
and no promote, push or pull-request exit is added.

**Out of scope — a known limitation with a named eventual fix.** A genuinely undelivered task can
still reach `done`. The fix is a better delivery signal, not a stricter state transition built on the
current fifteen-second heuristic.

**Deferred to follow-up work.** Replacing the external-reviewer transport with a named Herdr agent,
admissible only once Herdr satisfies cross-vendor selection, durable agent identity, visible lifecycle
state, resumable collection, timeout and failure handling, and provenance-equivalent typed output —
and only if the swap changes nothing above the seam.

---

## Risk Analysis and Mitigation

**A green gate that proves nothing.** The repository's standing lesson, and defect T7 is it recurring:
a fixture encoded the bug as valid input. Mitigation: U7 inverts that fixture and U10 runs the flow in
a real repository with no mock for git, the roster or scoring.

**Reviewer-tier surprise.** The union moves `devils-advocate-reviewer` from always-spawned to
conditional and `testing-reviewer` from optional to always-on. Anyone running a review today sees both
changes. Mitigation: both are stated in KTD3 and in the changelog rather than discovered.

**A second gate creeping back.** Three separate rules in the source read like thresholds — the
below-5.0 stop, the Priority 0/1 gates in Work and Code Review, and "cannot be averaged away".
Mitigation: R7 states the rule, U5's verification is a search of the module for any threshold other
than 9.0 and 7.0, and KTD5 records the destructive-finding reading explicitly.

**Cross-plugin release skew.** Four surfaces, three plugin versions. Mitigation: R36, and the
repository's existing tri-lock release-surface parity and diff-aware bump guards in `scripts/gate.sh`.

**Scope of the roster.** Roughly seventy-five dimensions across fourteen lenses is a large data
artifact to author correctly. Mitigation: U4 lands the roster alone, before anything consumes it, so
its parity and completeness tests fail early rather than during scoring work.

---

## Alternatives Considered

**Keep consensus in Team Execution and have Code Review escalate to it** — today's behaviour at
`code-review/SKILL.md:250`. Rejected: it makes the review verdict unavailable to any caller not
running a team, and Orchestrate is exactly such a caller.

**Keep two rosters synchronised by convention.** Rejected: they already drifted to where only three of
ten reviewers map cleanly onto a lens, with no mechanism that would have reported it.

**Intersect the two rosters instead of uniting them.** Rejected: it would delete `correctness` and
`privacy` from the review path.

**Let Orchestrate keep its multi-vendor panel.** Rejected by ruling, and superseded by KTD8, which
preserves the diversity the panel provided without the duplicate full reviews.

---

## Traceability

Every one of the twenty upstream backlog items maps to a unit, and every one of the twenty-five
upstream defects is closed.

| Upstream item | Unit | Upstream defects closed |
|---|---|---|
| 1 land in a worktree | U1 | O1 |
| 2 run-branch resolution | U2 | O2 |
| 13, 14, 15 notes and status | U3 | O3, O4, O5 |
| 3 canonical roster | U4 | C5, T1 |
| 4 scoring and thresholds | U5 | C1, C2 |
| 5, 6 cycle state and typed result | U6 | C2, C3, C4 |
| 7, 8, 12 consumers and helper | U7 | T1, T2, T3, T4, T5, T6 |
| 11 Work gate | U8 | W1 |
| 9, 10 loop seam and worker preservation | U9 | O9, O10, O12 |
| 16 behavioural tests | U10 | T7 |
| 17, 18, 19, 20 documentation and hygiene | U11 | O11, O6, O7, O8 |

Upstream item 1 is narrowed from land-and-collect to land-only by operator ruling; `collect` moves to
Scope Boundaries as a known limitation.

---

## Release Shape

R36 and R37 are cross-cutting and belong to every pull request rather than to one unit: each
touched plugin updates its manifest, the marketplace registry and its changelog in the same pull
request as the change, and `scripts/gate.sh` is green before any push.

Group A — U1, U2, U3 — is independent of the review contract and ships alone as an Orchestrate
release. Groups B through D — U4 through U10 — are the single coordinated cross-plugin change across
saga, team-execution and orchestrate, with plugin manifests, the marketplace registry and every
touched changelog updated in the same pull request. U11 may ride either.
