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
evidence, of which **two are withdrawn by this plan's own verification** — see Withdrawn Defects —
leaving 23 live. Three facts from that audit drive this plan:

Code Review has **no numeric scoring at all** — searching the skill for `9.0`, `7.0`, `/10` and
`score` returns nothing, its verdict is binary `blocked`/`clean`, and `SKILL.md:250` escalates gated
consensus *to* Team Execution. Team Execution **states** the thresholds, the mean rule, the
three-cycle rule and full 0-10 anchors in `review-criteria.md`, and executes none of them in code: its
consensus helper has **no production caller**, `consensus-protocol.md` contains zero `python3`
invocations, and the six scripts its skill does invoke do not include the scorer. Team Execution
consensus is prose a model performs.

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
contradicts its dimensions is rejected, and so is a dimension score contradicted by the evidence
recorded against it (R38).

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

R17. Code Review emits a typed result carrying: a schema version; selected and attempted lens
identifiers; the revision each lens reviewed; applicable dimensions with their scores and causes; the
derived overall per lens; findings; cycle history; the failing-lens set; consolidated structured fix
requests; unresolved fix identifiers; the best-available revision; a residual summary; the outcome;
and the next action. **`outcome` is the single decision field — there is no separate `verdict`.**

R18. The outcome is exactly one of `accepted`, `repairs_requested`, `cycle_cap_best_available`,
`review_incomplete`.

R19. Accepted lenses are not rerun and retain the revision they actually reviewed. They are
**delta-checked** against the final revision after repairs (R40); a delta-check is not a rerun.

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

R29. `land` merges inside a throwaway worktree created **detached at the run branch tip**, then
advances the run branch ref explicitly. It never checks out the operator's tree and never refuses
because that tree is dirty. Detached checkout is required rather than incidental: `git worktree add`
**fatals** with `'<branch>' is already used by worktree at ...` when the branch is checked out
anywhere — including the operator's own tree and a retained conflict worktree from a previous land.

R30. The land worktree is created at `.orchestrate/land-<run_id>/`, outside the `orch-<unit>` sibling
namespace so it can never collide with a unit worktree. A successful `land` removes it. A conflicting
`land` retains it, reports its path, and records that path in the run record as
`conflict_worktree`, which `reap` reads so `clean` recognises it rather than treating it as litter.

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

### Acceptance integrity

R38. An unresolved critical finding must be reflected in the evidence and score of the dimension it
bears on. Contradiction validation rejects a dimension scored as passing while carrying unresolved
critical evidence against it. **This is not a priority gate and not an automatic veto** — priority
remains metadata (R8); the mechanism is evidence-grounded scoring plus the R2 floor.

### Result transport

R39. The typed result carries `"schema": "review_result.v1"`, an explicit collection operation, a
revision binding naming the commit each result describes, a mapping into the evidence ledger, and the
named Orchestrate resume transitions a caller may make from each outcome.

R40. After repairs, previously accepted lenses are **delta-checked** against the final revision — not
fully rerun, and not assumed still valid. A delta-check that fails returns its lens to the failing set.

### Roster executability

R41. Every roster lens maps to an executable Code Review procedure **and** a Team Execution agent.
A lens missing either mapping fails the parity check.

R42. Custom reviewers are non-scoring — excluded from the denominator and both thresholds — unless
policy explicitly grants voting authority.

R43. The built-versus-planned audit stays outside numeric scoring and remains an independent gate
alongside the R10 gates.

R44. The external-reviewer seat performs **whole-diff advisory review** and may discover findings not
already raised. It retains its request binding, lifecycle safeguards, external-only admission, and
**non-scoring authority** — it never enters the denominator, the thresholds, or the outcome.

### Routing and recovery

R45. Fix requests route by `owner` **role**, not by unit name. `review-fixer` and
`downstream-resolver` map to a Work worker by role plus touched paths, reusing a live worker where one
matches. `human` and `release` ownership are surfaced to the operator and **never** dispatched as Work.

R46. `status`, `check` and `clean` remain usable when the run branch does not resolve, reporting the
unresolvable branch rather than failing. Only `land` and `go` refuse.

R47. A terminal `ran-empty` or `died` delivery yields `review_incomplete` without consuming a scoring
cycle. The runner's existing `pending`, collection and no-relaunch behaviour is preserved, not rebuilt.

### Canonical policy

R48. Thresholds, dimensions and 0-10 anchors are declared **once**, in the roster. Other policy
documents point at it rather than restating it. Parity checks cover **live policy consumers only** —
never changelogs, review artifacts or journal entries, which legitimately quote past policy.

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
override, which would be a second terminal gate. The same reasoning answers acceptance integrity
(KTD14): the link between a critical finding and acceptance is the dimension score it drives, not a
veto bolted beside the score.

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
dropping diversity, against which the 0-versus-4 finding split is direct evidence. **KTD15 supplies
the missing half of this decision** — the seat as it ships today reviews one named finding and could
not have produced that split, so keeping diversity requires extending it to whole-diff review.

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

**KTD14 — Acceptance integrity is evidence-grounded scoring, not a priority veto.** An unresolved
critical finding cannot coexist with an implausibly passing dimension because contradiction validation
(R38) rejects that combination, and the R2 floor then blocks. Rejected: an automatic priority veto or
a Priority 0/1 gate — that is the rule R8 settles against, and it would recreate the duplicate gate
this plan removes from Work. Rejected also: leaving the two unlinked, which would let the numeric
result and the findings list disagree in public.

**KTD15 — The external seat becomes whole-diff advisory review.** Today it reviews **one named
finding** (`code-review/SKILL.md:281`) and adjudicates `keep`/`downgrade`/`dismiss`. A single-finding
second opinion cannot surface a finding nobody raised, so as it stands it does **not** deliver the
diversity the 0-versus-4 split argues for. It is extended to whole-diff review while keeping request
binding, lifecycle safeguards, external-only admission and non-scoring authority. Rejected: keeping
the single-finding form and continuing to claim diversity, which was the error in this plan's first
draft; rejected also: letting the seat score, which reopens denominator questions R2 avoids.

**KTD16 — Accepted lenses are delta-checked, not rerun and not trusted.** A full rerun discards the
cost saving R19 exists for; assuming continued validity lets a repair break something an accepted
lens would have caught. Delta-check against the final revision is the middle, and a failing
delta-check returns the lens to the failing set.

**KTD17 — The dead consensus module is quarantined, not patched.** `consensus_advisory.py` has **no
production caller**: no skill, reference or script invokes it, and `consensus-protocol.md` contains
zero `python3` invocations, so Team Execution's consensus is prose a model executes. The live
ingestion path already requires non-empty dimensions
(`dispatch_settlement_adapter.py:192-194`). Patching the unused module would be dead wiring — the pattern
this repository's journal warns about. Rejected: "fix the helper", which this plan's first draft
proposed on the strength of a defect that does not reach production.

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

Three artifacts carry the contract. `plugins/saga/references/lens-roster.json` is the roster —
lenses, triggers, dimensions, 0-10 anchors, and each lens's two implementation mappings.
`plugins/saga/scripts/review_consensus.py` is the scoring and cycle engine. The typed result,
`"schema": "review_result.v1"`, is the versioned serialized output both Orchestrate and Team Execution
consume without interpreting, bound to the commit each per-lens result describes.

The external-reviewer seat sits inside Code Review, reviewing the whole diff and able to discover
findings, adjudicated by Code Review and never entering the denominator, the thresholds or the
outcome.

### Lens dimensions

Each lens scores the dimensions below. Only applicable dimensions are scored; each non-applicable
dimension records an explicit cause (R5), and a lens with zero applicable dimensions is invalid (R3).

**Anchors are ported, not invented.**
`plugins/team-execution/skills/team-execution/references/review-criteria.md` already carries 0-10
rubric tables with per-score definitions, alongside the mean rule, both thresholds and the three-cycle
best-available rule (`review-criteria.md:3-8`). Those anchors move into the roster as the canonical
copy and that file becomes a pointer (R48). Authoring fresh anchors beside existing ones would be the
drift this plan exists to end.

**Every lens carries two implementation mappings** (R41): an executable Code Review procedure and a
Team Execution agent. A lens missing either fails parity rather than silently scoring nothing.
**Custom reviewers are non-scoring** unless policy grants voting authority (R42), and the
**built-versus-planned audit stays outside the score** as an independent gate (R43).

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

`previous-comments` — selected only for a pull request carrying prior review. Its scoreable dimension
is **resolution completeness**: every unresolved thread inventoried and mapped to the current
revision; resolution verified in code and tests rather than accepted from reply text; regressions
against previously resolved threads detected; and an evidence-backed disposition recorded for each.
Without a scoreable dimension this lens could be selected and then fail R3 on every use, which is why
the activity list alone was insufficient.

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
plugins and 23 live defects; grouping into phases keeps it legible. Group A is independent of
everything else and lands first.

### U1. Land inside a throwaway worktree

`land` stops touching the operator's working tree, so a dirty checkout no longer blocks an entire run.

**Goal:** `land` merges unit branches onto the run branch without checking out or refusing.

**Requirements:** R29, R30.

**Dependencies:** none.

**Files:** `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py`;
`tests/test_orchestrate_land_worktree.py`.

**Approach:** replace the `git status --porcelain` refusal and the `git checkout r.branch` in
`cmd_land` with `git worktree add --detach .orchestrate/land-<run_id> <run branch>`, merge each unit
branch there, then advance the run branch ref explicitly — a detached merge does not move it. Remove
the worktree on success. On conflict, retain it, print its path, and store that path in the run record
as `conflict_worktree` so `reap` recognises it. The existing conflict message, which tells the
operator to finish the merge on the run branch, is rewritten to name the retained directory.

**Why detached, verified by execution.** `git worktree add <path> <branch>` fatals with
`fatal: '<branch>' is already used by worktree at ...` whenever that branch is checked out anywhere.
Two reachable cases hit it: a retained conflict worktree from a previous land still holds the run
branch, and an operator sitting on the run branch in their own checkout — likely right after `start`.
`--detach` succeeds in both. Rejected: refusing when the branch is held, which would reintroduce a
refusal this unit exists to remove.

**Residual risk, named rather than discovered.** Advancing the run branch ref while the operator has
that branch checked out moves their `HEAD` underneath them; their uncommitted work is untouched but
now reads against a new base. `land` says so when it detects that case.

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
- Operator's own checkout sitting on the run branch, dirty: `land` still succeeds, the operator's
  uncommitted files are unchanged, and the run branch ref has advanced.
- A retained conflict worktree from a previous land still holds the run branch: a new `land` still
  creates its detached worktree rather than fatalling.
- Land worktree path never collides with an `orch-<unit>` worktree, including a unit literally named
  `land-<run_id>`.
- `land` on a run whose branch does not resolve: fails loudly (shared with U2).

**Verification:** a land succeeds against a repository with uncommitted tracked changes and leaves
them untouched; a conflicting land leaves a directory the operator can resolve in.

### U2. Resolve the run branch once, and fail loudly

A renamed or deleted run branch stops silently turning every predicate False.

**Goal:** one resolution at load; an unresolvable run branch is an error, not a chorus of False.

**Requirements:** R31, R46.

**Dependencies:** none.

**Files:** `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py`;
`tests/test_orchestrate_run_branch_resolution.py`.

**Approach:** resolve `r.branch` once in `Run.load` using the existing `resolve_ref` and record the
result as run state — **resolved, or unresolvable-and-named**. An unresolvable run branch makes `land`
and `go` refuse, while `status`, `check` and `clean` still run and report it (R46): those are the
diagnostics an operator needs precisely when the branch is gone, and an exception at load would take
them away. `branch_produced_anything`, `landed_by_merge`,
`cmd_check`, `cmd_land` and `cmd_go`'s dependency gate then stop each independently answering False
on a failed `git merge-base`.

**Patterns to follow:** `resolve_ref` in the same file, already used at three call sites.

**Test scenarios:**

- Run branch renamed, four units each with commits: run `check` — it names the missing run branch and
  does not report `NO COMMITS` for any unit.
- Run branch renamed: run `go` with a dependent unit — it reports the missing branch rather than
  skipping the unit as having committed nothing.
- Run branch present and resolvable: every command behaves exactly as before.
- Run branch renamed: `status`, `check` and `clean` each still run and each name the unresolvable
  branch instead of raising.
- Run branch renamed: `land` and `go` refuse, naming the branch.
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

**Requirements:** R1, R11, R12, R13, R14, R15, R16, R41, R42, R48.

**Dependencies:** none.

**Files:** `plugins/saga/references/lens-roster.json`;
`plugins/saga/skills/code-review/references/lens-catalog.md`;
`tests/test_lens_roster.py`.

**Approach:** author the roster as `"schema": "lens_roster.v1"` carrying, per lens, a stable
identifier, an always-on or conditional trigger class, the trigger's judgment guidance, its dimension
identifiers **with their 0-10 anchors ported from `review-criteria.md`**, and the two implementation
mappings R41 requires — an executable Code Review procedure and a Team Execution agent. Custom
reviewers are represented as non-scoring (R42). `lens-catalog.md` becomes prose that points at the roster rather than a second
copy of it. The non-scoring external advisory seat is represented explicitly so its exclusion from the
denominator and both thresholds is data rather than prose.

**Patterns to follow:** `plugins/saga/references/bridge-signatures.json` for shape and schema-key
convention.

**Test scenarios:**

- Load the roster: exactly fourteen lenses, four always-on and ten conditional, identifiers matching
  R12 verbatim.
- Every lens declares at least one dimension.
- The advisory seat is marked non-scoring and excluded from the denominator.
- Every lens declares both implementation mappings; removing either fails parity.
- Every dimension declares 0-10 anchors, and they match the ported `review-criteria.md` definitions.
- A custom reviewer is excluded from the denominator and both thresholds.
- Roster parity across **live policy consumers only**: a threshold quoted in a changelog, a review
  artifact or a journal entry does not fail the check.
- Schema key is `lens_roster.v1` and the file parses as JSON.

**Verification:** one roster exists, and a parity test fails if a second appears.

### U5. Dimensions, derived overall, and the acceptance rule

The arithmetic becomes code that can be tested rather than prose that drifts.

**Goal:** enforce R2 through R5 deterministically.

**Requirements:** R1, R2, R3, R4, R5, R7, R8, R10, R38, R43.

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
- A dimension scored 9.0 while an unresolved critical finding is recorded against that same dimension:
  rejected as contradictory. No priority gate is consulted and no veto is applied — the rejection is
  the same contradiction check that catches a false overall.
- The same unresolved critical finding with the dimension honestly scored below 7.0: accepted as a
  valid result, and blocked by the floor rather than by any priority rule.
- Built-versus-planned failing while every dimension passes: the score is unchanged and the gate
  blocks independently.
- Scanner, test and deployment gate results passed alongside: the score is unchanged by them.

**Verification:** searching the module for any numeric threshold returns only 9.0 and 7.0.

### U6. Cycle state, selective rerun, termination, and the typed result

The three-cycle loop and the contract Orchestrate consumes.

**Goal:** implement R6, R17 through R22 as state plus a serializable result.

**Requirements:** R1, R6, R17, R18, R19, R20, R21, R22, R28, R39, R40, R44, R47.

**Dependencies:** U5.

**Files:** `plugins/saga/scripts/review_consensus.py`;
`plugins/saga/skills/code-review/SKILL.md`;
`plugins/saga/skills/code-review/references/findings-schema.md`;
`tests/test_review_consensus_cycles.py`.

**Approach:** carry cycle state across rounds, rerun only failing lenses, retain each accepted lens's
reviewed revision, and **delta-check accepted lenses against the final revision after repairs** (R40)
— a failing delta-check returns that lens to the failing set. Terminate at three cycles with
`cycle_cap_best_available` naming the latest successfully integrated revision reviewed in cycle three.
Serialize the typed result as `"schema": "review_result.v1"` with an explicit collection operation, a
revision binding naming the commit each per-lens result describes, a mapping into the evidence ledger,
and the named resume transitions a caller may make from each outcome (R39). **`outcome` is the single
decision field; there is no separate `verdict`.** A terminal `ran-empty` or `died` delivery maps to
`review_incomplete` without consuming a cycle (R47), reusing the runner's existing `pending`,
collection and no-relaunch behaviour rather than rebuilding it. The external seat becomes **whole-diff
advisory review** able to discover findings, keeping its request binding, lifecycle safeguards,
external-only admission and non-scoring authority (R44). `SKILL.md` drops its escalation of gated
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
- The serialized result round-trips, carries its schema version, and binds each per-lens result to
  the commit it describes.
- A consumer given a result whose schema version it does not know refuses it rather than guessing.
- Each outcome offers only its named resume transitions; an undefined transition is refused.
- A lens accepted in cycle one, then delta-checked against the cycle-three revision and failing:
  returns to the failing set and its earlier acceptance does not survive.
- A lens accepted in cycle one whose delta-check passes: retains its original reviewed revision and is
  not fully rerun.
- Runner returns `ran-empty`: outcome is `review_incomplete`, cycle counter unchanged.
- Runner returns `died`: same, and no relaunch is attempted.
- Runner returns `pending`: collected, never relaunched, never read as an empty review.
- The external seat reviews the whole diff and raises a finding no other lens raised: the finding is
  adjudicated by Code Review and the seat's own opinion enters neither the denominator, the
  thresholds, nor the outcome.

**Verification:** a caller can determine what to do next from the outcome alone, without recomputing
any score.

### U7. Team Execution consumes the roster, and its policy stops being prose

The parallel roster and the prose-only policy go away; the dead helper is quarantined, not patched.

**Goal:** one roster and one policy source for Team Execution, its consensus computed by the U5
scorer rather than by prose, and the second terminal stop removed.

**Requirements:** R7, R11, R15, R23, R24, R48.

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
agent files remain as the implementations behind the shared lens identifiers, and each is named in the
roster's Team Execution mapping (R41). `review-criteria.md` surrenders its thresholds, mean rule,
cycle rule and 0-10 anchors to the roster and becomes a pointer (R48); `consensus-protocol.md` does
the same for the policy it restates. The below-5.0 terminal stop is deleted; its routing half survives
as fix-request priority. The five conflicting cycle-three statements are reconciled to one, and
`andon-cord.md`'s miscitation of `consensus-protocol.md` is corrected.

`consensus_advisory.py` is **quarantined, not patched** (KTD17). It has no production caller, so
correcting its arithmetic would be dead wiring; the live path is Team Execution invoking the U5
scorer. The module is marked unused and its tests are retained only as characterisation of what is
being retired.

**The settlement adapter is left alone.** It already requires non-empty `dimension_scores` at
`dispatch_settlement_adapter.py:192-194`, and the fixture at
`tests/test_team_execution_settlement_adapter.py:165` is a **negative** case asserting
`SettlementAdapterError` — correct behaviour, not a defect. An earlier revision of this plan said
otherwise and was wrong.

**Patterns to follow:** `dispatch_settlement_adapter.py`'s evidence validation, which is the live
ingestion path this unit must not weaken; and U5's scorer, which becomes the callee.

**Test scenarios:**

- Reviewer selection reads the shared roster: removing a lens from the roster removes it here.
- `review-criteria.md` and `consensus-protocol.md` declare no threshold, mean rule, cycle count or
  anchor of their own; a grep for `9.0` and `7.0` in live policy documents finds them only in the
  roster.
- Cycle-cap termination has exactly one statement across all five files that previously disagreed.
- Team Execution consensus is computed by invoking the U5 scorer, not by prose.
- Settlement of a prose-only result: still `silent-no-op` — unchanged, and re-asserted so the
  evidence-based behaviour is not lost in the move.
- Settlement of a result with an empty dimension map: still rejected — unchanged.
- `consensus_advisory.py` has no production caller before or after this unit.

**Verification:** exactly one roster in the repository, and one consistent cycle-cap statement.

### U8. Work drops its own review gate

The last duplicate acceptance rule is removed.

**Goal:** Work reads Code Review's acceptance instead of gating on Priority 0/1.

**Requirements:** R8, R9, R25.

**Dependencies:** U6.

**Files:** `plugins/saga/skills/work/SKILL.md`; `tests/test_work_review_contract.py`.

**Approach:** the hard gate at `work/SKILL.md:57` and section 5.3 reads the typed result's outcome
rather than counting Priority 0 and Priority 1 findings. The stale-review check is preserved — it is
about freshness, not acceptance.

**Patterns to follow:** Work already reads the code-review envelope programmatically.

Work is a markdown skill, so a Python test cannot exercise it — a test that appeared to would be
testing its own fixture. `tests/test_work_review_contract.py` is therefore a **contract check**: it
asserts the skill text declares the outcome-driven gate and no longer declares a Priority 0/1 gate,
and that the outcomes it names are exactly the four the roster contract defines.

**Test scenarios:**

- Typed result `accepted` with Priority 2 findings present: Work proceeds.
- Typed result `repairs_requested`: Work blocks.
- Typed result `cycle_cap_best_available`: Work proceeds and surfaces the residuals.
- Typed result `review_incomplete`: Work blocks and says the review did not run.
- Stale review: still blocks, unchanged.
- Contract check: `work/SKILL.md` names all four outcomes and no Priority-based acceptance rule
  survives anywhere in it.

**Verification:** no Priority-based acceptance decision remains in Work.

### U9. The Orchestrate review loop seam

One controller, an opaque result, repairs routed to existing workers, and resubmission.

**Goal:** R26, R27, and worker preservation.

**Requirements:** R22, R26, R27, R45.

**Dependencies:** U6.

**Files:** `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py`;
`plugins/orchestrate/commands/orchestrate.md`;
`plugins/orchestrate/skills/orchestrate/SKILL.md`;
`tests/test_orchestrate_review_loop.py`.

**Approach:** a review phase becomes one Code Review controller unit rather than one unit per
reviewer. The typed result is persisted verbatim against the run and never parsed for policy.
Fix requests route by `owner` **role**, not by unit name — the schema's values are
`review-fixer`, `downstream-resolver`, `human` and `release`. `review-fixer` and
`downstream-resolver` map to a Work worker by role plus touched paths, reusing a live worker whose
paths overlap and creating a replacement when none matches. `human` and `release` ownership are
surfaced to the operator and **never dispatched as Work** (R45). After landing, the revision is resubmitted. Reaping no longer
removes a worker that carries an outstanding fix request.

**Patterns to follow:** `Run.save` for durable run state; `reapable` for the reaping predicate.

**Test scenarios:**

- Plan naming a review phase: exactly one review unit is created, not N.
- Typed result `repairs_requested` with two fix requests whose owners match two existing workers:
  both are dispatched to those workers, and neither worker was reaped.
- Fix request whose owner matches no live worker: a replacement is created.
- Fix request owned by `human`: surfaced to the operator, no Work unit dispatched, and the run does
  not resubmit as though it were repaired.
- Fix request owned by `release`: same, and it is not converted into code-fix work.
- Two fix requests owned by `review-fixer` touching disjoint paths: routed to different workers.
- Typed result persisted and reloaded: byte-identical, and no score or threshold is recomputed.
- Outcome `accepted`: no repair is dispatched and no resubmission occurs.
- `clean --merged` with an outstanding fix request: the worker is kept.

**Verification:** the run record carries the review result and Orchestrate makes no policy decision
from it.

### U10. End-to-end flow in a real temporary Git repository

The one test that proves the chain rather than its parts.

**Goal:** R35's integration scenario.

**Requirements:** R35, R40.

**Dependencies:** U1, U2, U3, U5, U6, U7, U8, U9.

**Files:** `tests/test_review_loop_end_to_end.py`.

**Approach:** build a real temporary Git repository with real branches, run a review that fails, route
a repair, land it, resubmit, and reach acceptance — with no mock standing in for git, the roster, or
the scoring module. It exists because a fixture standing in for the component under test is this
repository's standing failure mode — and because this plan's own first draft fell to it, asserting
defect T7 from a grep line without reading that the case was a `pytest.raises` negative test.

**Patterns to follow:** `tests/test_orchestrate_launch_and_land.py`, which already builds a real
temporary Git repository.

**Test scenarios:**

- Failing review, one repair, resubmission, acceptance: the final outcome is `accepted`, the landed
  revision contains the repair, and every accepted lens was delta-checked against it.

The cycle-cap, state-reload and independent-gate cases are **focused tests**, not part of this flow:
three failing cycles and their residuals belong to `tests/test_review_consensus_cycles.py` (U6),
state reload to the same file, and the independent-gate case to `tests/test_review_consensus.py` (U5),
where the gate named is **built-versus-planned** (R43). Bundling them here would make one slow test
the only evidence for four separate behaviours, and a failure in it would not say which broke.

**Verification:** the flow passes without any mock for git, the roster, or scoring.

### U11. Documentation and hygiene

Stale documentation and run-state litter, none of which blocks the other units.

**Goal:** R36 in documentation form, and the four hygiene defects.

**Requirements:** none behavioural; closes O11, O6, O7. (O8 withdrawn — already implemented.)

**Dependencies:** none.

**Files:** `plugins/orchestrate/README.md`;
`plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py`;
`plugins/orchestrate/skills/orchestrate/SKILL.md`;
`tests/test_orchestrate_hygiene.py`.

**Approach:** rewrite the README to the two modules the plugin actually ships, removing the seven
citations to deleted modules (`planning.py`, `admission.py`, `accounting.py`, `register.py`,
`subscriber.py`, `session_lifecycle.py`, `completion.py`) and keeping the one that is real,
`herdr_events.py`. Write `.orchestrate/` to `.git/info/exclude` at `start`. Point
hand-authored briefs at `.orchestrate/tasks/`.

**No unrecorded-branch warning is added.** `check` already reports `UNRECORDED` for a branch in the
run namespace with no unit — verified by running it against the live Home Lab record. Defect O8 is
withdrawn as already satisfied, and upstream item 20 with it.

**Patterns to follow:** the skill already teaches a `.git/info/attributes` append for union merges —
the same local, uncommitted mechanism.

**Test scenarios:**

- `start` in a repository with no exclude entry: `.orchestrate/` is excluded afterwards and the file's
  prior contents are preserved.
- `start` run twice: the exclude entry is not duplicated.
- README cites no module the plugin does not ship: every `scripts/*.py` reference in it resolves to
  a file that exists.

**Verification:** a fresh run leaves no untracked run state in the driven repository.

---

## Scope Boundaries

**Out of scope — not doing this, and not later either.** Restoring the archived Orchestrate consensus
panel or review loop. Adding any review acceptance or terminal threshold beyond 9.0 and 7.0. Making
Priority or confidence a gate. Letting the external-reviewer seat score. Changing scanner, test,
deployment, casualty or operational-safety gates, which stay independently authoritative.

**Out of scope — deliberately rejected during review.** Patching `consensus_advisory.py` as though it
were live: it has no production caller and the fix would be dead wiring. Adding an unrecorded-branch
warning: `check` already reports it. Parity-scanning historical repository mentions of a threshold:
changelogs, review artifacts and journal entries legitimately quote past policy, so parity covers
live policy consumers only (R48).

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

**A green gate that proves nothing.** The repository's standing lesson, and this plan's own first
draft fell to it: defect T7 claimed a fixture encoded the bug as valid input, when the case was a
`pytest.raises` negative test asserting correct rejection. Mitigation: T7 is withdrawn, and U10 runs
the flow in a real repository with no mock for git, the roster or scoring.

**Fixing code nothing calls.** `consensus_advisory.py` has no production caller, so a plan that
"corrects" it would ship a fix that changes no behaviour while the prose path stays unenforced.
Mitigation: KTD17 quarantines rather than patches, and U7's verification asserts the module has no
production caller before **and after** the unit.

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
| 7, 8, 12 consumers and policy consolidation | U7 | T1, T2, T3, T4, T5, T6 |
| 11 Work gate | U8 | W1 |
| 9, 10 loop seam and worker preservation | U9 | O9, O10, O12 |
| 16 behavioural tests | U10, and the focused tests in U5 and U6 | none — T7 withdrawn |
| 17, 18, 19 documentation and hygiene | U11 | O11, O6, O7 |
| 20 unrecorded-branch warning | **withdrawn** — `check` already reports it | O8 withdrawn |

Upstream item 1 is narrowed from land-and-collect to land-only by operator ruling; `collect` moves to
Scope Boundaries as a known limitation. Upstream item 20 is withdrawn.

### Withdrawn defects

Two of the audit's 25 defects do not survive verification against source, and both errors were this
plan's. Recording them rather than deleting them keeps the register honest.

**T7 — withdrawn.** The claim was that
`tests/test_team_execution_settlement_adapter.py:165` encodes an empty dimension map as valid input.
It is a `@pytest.mark.parametrize` case for
`test_reviewer_success_prose_or_artifact_pointer_cannot_materialize_delivery`, which asserts
`pytest.raises(SettlementAdapterError)` — the adapter **correctly rejects** it, and
`dispatch_settlement_adapter.py:192-194` raises `"reviewer result requires non-empty dimension_scores"` on
the live path. The claim came from reading a grep line without its context.

**O8 — withdrawn.** The claim was that nothing warns when a branch appears in the run namespace with
no unit. `check` already reports `UNRECORDED`, verified by running it against the live Home Lab
record. Upstream item 20 is withdrawn with it.

**T2, T3 and T4 survive but are re-scoped.** They describe `consensus_advisory.py`, which has no
production caller. They are real statements about that module and irrelevant to production behaviour;
KTD17 quarantines it rather than patching it, and the live gap they gestured at — Team Execution
consensus being prose — is what U7 actually closes.

---

## Release Shape

R36 and R37 are cross-cutting and belong to every pull request rather than to one unit: each
touched plugin updates its manifest, the marketplace registry and its changelog in the same pull
request as the change, and `scripts/gate.sh` is green before any push.

Group A — U1, U2, U3 — is independent of the review contract and ships alone as an Orchestrate
release. Groups B through D — U4 through U10 — are the single coordinated cross-plugin change across
saga, team-execution and orchestrate, with plugin manifests, the marketplace registry and every
touched changelog updated in the same pull request. U11 may ride either.
