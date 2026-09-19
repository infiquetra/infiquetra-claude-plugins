---
title: Code review — issue 1022, roles library
reviewed_revision: afa5dad7
status: round-three-stopped-at-re-review
date: 2026-09-19
---

# Round three — stopped

**Outcome: does not accept. Stopped at the re-review, per the repair rule.**

The documentation-clarity lens read all fourteen prompts and both lifecycle documents in full at
`bac820e3` and raised nine P1 findings — the first findings in this whole review about the product
rather than the test harness. They were repaired at `afa5dad7`. The lens re-ran at that head and
**still gates**: five of the nine repairs are wrong or incomplete, and two of them are wrong in the
same way the defects they were fixing were wrong.

The repair allowance for this lens is spent. A further attempt is the operator's call.

## What the re-review found, and why it matters

**D1 — I answered "no source for this input" by inventing a source.** `implementer.md` now says
"Your dispatch names whether the repository declares a branch preview." The `dispatch` contract has
six fields and none of them is that; no lifecycle document says where a repository declares a
preview at all. I also routed the smoke result into `unit_and_child_check_results`, which the
lifecycle defines as something else. The original finding was that the prompt had no source for the
declaration; it now states a false one as fact. Every prompt in this library tells its session that
an invented input is indistinguishable downstream from a given one — and I did exactly that while
fixing that class of defect.

**D2 — I fixed the inversion and left its contradiction standing.** The Functional Tester's stop
rule now correctly marks a scenario blocked and carries on, but the output-contract section above it
still says to record a scenario you could not run as "not run", which the new paragraph and the
contract both forbid. One prompt, two opposite instructions on the same field. This is the
Issue Reviewer's self-contradiction — finding 8 — reproduced in another file by the repair pass.

**D3 — I pointed at two documents that explicitly disclaim holding what I sent the reader for.**
`planning-readiness.md` says in terms that it does not hold the plan-review checklist and redirects
elsewhere; `run-model.md` says the reviewer asks four things where the contract requires three. The
seven checklist questions and the three run-model questions live in `docs/reviewers/plan-review.md`,
which the prompt does not name. The session can now reach the lifecycle and is sent to the wrong
pages.

**D4 — I enumerated two field lists wrongly.** `preflight_results` drops the environment and the
observing role; `per_lens_results` drops the threshold, the floor and the dimension scores, without
which a reader cannot tell whether a lens was met, which is the field's entire purpose. A wrong
enumeration is worse than none: it produces a confidently malformed contract where the absence would
have produced a stop.

**D5 — the ladder is in all fourteen prompts and its verification rule makes the normal case
unreachable.** It requires `HEAD` to start with the pin and orders a stop otherwise — but a clone,
including the ladder's own final rung, lands on the default branch rather than a detached pin, and
the rule forbids the obvious remedies of fetching the pin or reading at the revision. It works today
only because the lifecycle's `main` happens to sit at `5efc869f`. The first merge there turns all
fourteen prompts into a guaranteed stop.

## What the re-review confirmed fixed

Findings 3, 4, 6 and 7 are fixed and verified against the lifecycle: the admissibility test in both
files, the `main_directly_consumed` rule with its source line and its `UNKNOWN` route, the
applicability declaration with its per-unit and always-on rules, and the shared finding schema's
attribution. Of finding 5, the Architect's Risk vocabulary and the Delivery Manager's
`approval_scope` pointer are fixed and the pointer holds; the Planner's persistent-finding
classification is fixed.

The lens also checked the incidental content added during the repair — the advisory seat and
verification-ledger rule, the cycle allowances and recovery rules, the repair accounting, the
Architect's decision scope — and found all of it faithful.

## Roster

| Lens | Revision reviewed | Gating findings | Resolution |
|---|---|---|---|
| correctness | `1cee1bde` | 1 × P0 | repaired, `a9674a3f` |
| testing | `a9674a3f` | 2 × P1 | repaired, `59f05286` |
| security | `59f05286` | none | 5 advisories repaired, `502480d1` |
| architecture-maintainability | `502480d1` | 1 × P1, 2 × P2 | P1 `a9eeded7`; P2s `bac820e3` |
| documentation-clarity | `bac820e3` | 9 × P1 | repaired, `afa5dad7` |
| documentation-clarity, re-run | `afa5dad7` | **5 × P1 open** | **stopped** |
| agent-usability | — | — | not run |
| adversarial | — | — | not run |

# Round two

**Outcome: does not accept.** Four of the seven approved lenses ran against the head they were
told to review, and each confirmed that revision before reading. They raised one P0 and three P1s,
all repaired. Three lenses — documentation-clarity, agent-usability, adversarial — have not run, and
the repair allowance is spent. An incomplete roster is not an acceptance, and a further round is the
operator's call.

| Lens | Revision reviewed | Gating findings | Resolution |
|---|---|---|---|
| correctness | `1cee1bde` | 1 × P0 | repaired, `a9674a3f` |
| testing | `a9674a3f` | 2 × P1 | repaired, `59f05286` |
| security | `59f05286` | none | 5 advisories repaired, `502480d1` |
| architecture-maintainability | `502480d1` | 1 × P1, 2 × P2 | P1 repaired, `a9eeded7`; two P2s open |
| documentation-clarity | — | — | **not run** |
| agent-usability | — | — | **not run** |
| adversarial | — | — | **not run** |

## What round two found that round one did not

**P0 — the suite could not pass in continuous integration.** A round-one repair required a sibling
lifecycle checkout no workflow provides, so the suite was green on a developer machine and red on
every runner, with five per-prompt checks degrading to skips. The environment doing the least
verification was the one gating the merge. Repaired by vendoring a pinned lifecycle snapshot that
the prompts are checked against everywhere, with drift as one explicit parity check.

**P1 — the stop-rule body was never checked.** Sections were bounded by the next *required* heading,
so the last one ran to end of file; in the Lens Reviewer, with 170 lines after it, the stop rule
could be deleted entirely and the check stayed clean. The one instruction that makes an autonomous
session terminate was the one section unenforced.

**P1 — a per-lens test asserted a shared-half fact eleven times**, claiming coverage it did not have.

**P1 — the change did the thing the journal recorded rejecting.** Twenty-five lines are byte-identical
across all fourteen prompts, roughly 266 duplicated lines, while the decision entry rejected copying
a shared block on drift grounds — and nothing enforced the copies. The decision is now superseded on
its merits rather than quietly contradicted, and a test holds the blocks identical.

**Five security advisories**, including the prompt-injection surface an earlier lens had flagged as
unexamined: the shared inputs block taught every session that issue comments are the channel work
arrives on without saying that content there is evidence rather than direction.

**Seven of round two's findings are defects introduced by earlier repairs in this same change.**
That is the case for a fresh round after repairs, made concrete seven times.

## Open findings, not repaired

**AM-2 (P2) — the dependency direction is inverted.** `tests/data/lifecycle-snapshot.json` holds
product-shape truth under a directory whose job is verification, and
`test_prompts_cover_every_staffable_lifecycle_role` asserts set equality against it — so adding a
fifteenth role requires editing test data, and the obvious repair for the resulting failure is to
relax the check that stops invented roles. Resolution: move the snapshot out of `tests/`, and add an
"adding a role" checklist to the directory README naming every file that must change.

**AM-3 (P2) — two load-bearing decisions have no journal entry.** The choice to vendor a pinned
snapshot and demote the live comparison to a skipping parity check is recorded only as a defect
narrative in `LEARNINGS.md`; it determines what continuous integration actually verifies and
deserves a decision with its rejected alternatives. And `roles/index.json` now carries a regex that
is a second expression of the lens-slicing rule, with no entry saying who owns it.

**AM-6 (P3)** — the slicing rule's only executable implementation lives in the test suite, so the
first real consumer will write a second one. **AM-7 (P3)** — the test module now has two jobs, the
prompt assertions and a bespoke Markdown and YAML toolkit with 21 seeded tests of its own; a
maintainer adding a role reads 1,240 lines to find the four that concern them.

## Coverage this review does not have

The three unrun lenses are not interchangeable with the four that ran. `documentation-clarity` is the
one whose subject is what this change mostly is. `agent-usability` found the P0 of round one.
`adversarial` found six silent-green routes in round one and named, as unexamined, the prose of
twelve prompts and the prompt-injection surface — half of which the security lens has since covered,
and half of which nobody has.

Across both rounds, no lens has read the prose of more than four of the fourteen prompts against the
lifecycle's role definitions. The structural contract is well enforced; whether each prompt is a
faithful and sufficient briefing is still unverified by anything but its author.

# Code review — issue 1022, roles library

**Outcome: `cycle_cap_best_available`.** All seven approved lenses ran and returned. Between them
they raised eighteen gating findings — one P0 and seventeen P1 — and every one is repaired. What has
not happened is a re-review of the final head: the repair allowance of three further cycles was
spent on cycles 3, 4 and 5, so the last repairs stand unreviewed by a lens. That is not `accepted`,
and saying so is the point of this line.

Base `2044c363`. Final head `67172d53`.

## Lens roster

| Lens | Class | Revision reviewed | Gating findings | Outcome |
|---|---|---|---|---|
| `correctness` | always-on | `b67701c1` (twice, independently) | none | advisory findings repaired |
| `testing` | always-on | `b67701c1` | 3 × P1 | all repaired, cycle 1 |
| `security` | always-on | `71f967c4` | none | 1 × P3 accepted; its one open item closed by hand |
| `architecture-maintainability` | always-on | `71f967c4` | 3 × P1 | all repaired, cycle 2 |
| `documentation-clarity` | conditional | `9680b8a1` | 5 × P1 | all repaired, cycle 3 |
| `agent-usability` | conditional | `8b565638` | 1 × P0, 6 × P1 | all repaired, cycle 4 |
| `adversarial` | conditional | `a3832a26` | 6 × P1 | all repaired, cycle 5 |

The eight conditional lenses not selected have no applicable dimension against a change that is
prose plus one test module: `deployment-infrastructure`, `reliability`, `performance`,
`api-contract`, `privacy`, `previous-comments`, `accessibility-human-usability`, `experience`.

## The P0

**A lens slice dropped the instruction that lets eleven of fifteen lenses finish.** The block giving
a conditional lens permission to report findings without scoring sat between the `# The lenses`
heading and the first grouping heading — in neither the shared half nor any `#### <lens-id>` section,
so the documented cut discarded it. A session staffing any of the eleven conditional lenses would
have received an output contract demanding a score for every applicable dimension, a stop rule
satisfied only by those scores, and no permission to report unscored: it would either fabricate
scores or never terminate.

It was introduced by the cycle-3 repair that first wrote the slicing rule down, and found by the
lens whose consumer is an agent. *Repaired:* the permission moved into the shared half under its own
heading, the stop rule names it, and a new test rebuilds the actual slice for each of the fifteen
lenses and runs the whole structural contract over it. Checking the file as a whole is what hid it;
checking the artifact a consumer really sends is what catches it.

## Gating findings by cycle, and how each was resolved

**Cycle 1, from `testing`.** Seeded fixtures re-typed the production regex, so they proved a property
of the regular-expression library rather than that a rule fires — every rule is now a named checker
both the real test and its fixture call. The live-versus-pinned identifier source degraded silently
and, because a worktree's parent is the `worktrees` directory, never resolved where the gate runs —
the resolution walks ancestors and names the resolved source in assertion messages. Three plan
requirements had no enforcing test — R7, R9 and R10 now have one each.

**Cycle 2, from `architecture-maintainability`.** Contract field lists were transcribed from the
lifecycle with nothing able to detect drift — a test now reads each contract's fields from the run
model and asserts the prompt names every required one. Pinned mode could pass vacuously by comparing
this repository's prompts to its own vendored copy — it now fails unless an environment variable
opts out. The prompts' revision pin and the identifiers' source could disagree — the checkout's head
is asserted equal to the pin.

**Cycle 3, from `documentation-clarity`.** The Delivery Manager listed the fields of four contracts
but never their names, so a session would write four malformed headers. Two inputs had no resolvable
location. The README claimed the directory holds no policy while every prompt transcribes a field
list. Its frontmatter table claimed a spelling the lifecycle contradicts — the lifecycle disagrees
with itself, its run model in sentence case and its role catalogue in Title Case. Its section table
claimed every role posts a handoff, which the Lens Reviewer refutes.

**Cycle 4, from `agent-usability`.** The P0 above, plus: inputs headed "from the run record" with no
prompt saying what the run record is; selection requiring a Markdown parse, now answered by
`index.json`; an unstated slice terminator and a slicing instruction addressed to the agent rather
than the consumer; a Lens Reviewer told to ask a question it has nobody to ask, now given a
resolution ladder; a field check matching any backticked token anywhere in a file, now scoped to the
output-contract section; and an unrenderable field convention, now stated with an example.

## What the returned lenses upheld

`correctness` verified element by element that all three pinned identifier lists match the live
configuration and that every prompt's `role_id` and `emits` agree with the lifecycle — all sixteen
contracts have exactly one producing prompt.

`security` checked every prompt's authority boundary against the role catalogue and found no
widening: no self-approval, no self-granted merge turn, no production promotion, no scope widening,
no threshold override. No secret, no egress instruction, no directive to obey untrusted content.

`agent-usability` confirmed prompt sizing is appropriate, stop rules are self-checkable, and the
refusal to copy dimensions, anchors and thresholds holds with no violation.

**Cycle 5, from `adversarial`.** Six more silent-green routes, including a third instance of the
pattern that produced the first two. `index.json` published a slicing algorithm the tests did not
use — a consumer would cut by the index, the tests by their own copy, agreeing only by coincidence.
The resolver reported a live lifecycle source while falling back per reader, so a renamed key would
have reverted every check to this repository's own vendored lists. The revision gate skipped, which
is green, whenever the sibling checkout was itself a worktree. The transcription check would have
gone vacuous on a status-vocabulary change. The handoff shape was checked per file, so one good
example covered five contracts — and fixing it immediately caught four incomplete examples in the
Delivery Manager. The output-contract window was found by unanchored search, which can only widen
and so can only make the check greener.

## Two things the checks caught after the lenses finished

**The version drift guard.** The gate went red on one step for one test: a packaging test that
states the expected plugin version independently and still said `1.5.2`. The release-surface test
added in cycle 2 did not catch it, because agreement among the manifest, the registry and the
changelog says nothing about a fourth place that states the version on its own.

**The lifecycle moved mid-run.** The repaired revision gate fired on its first real evaluation: the
sibling checkout had advanced from `67845cdd` to `5efc869f` while this work was in progress, as
another card landed the branch-preview exit criterion. Before re-pinning, the two revisions were
compared over exactly what this library depends on — role identifiers and names, contract
identifiers, senders, display names and required-field sets, lens identifiers and floors — and found
identical. The re-pin is therefore mechanical, and `index.json` now derives the revision from the
prompts rather than holding a fourth hand-maintained copy.

## Why this is not an acceptance

The roster is complete and every gating finding is repaired, but the repairs of cycle 5 and the two
above have not themselves been through a lens. The repair allowance was three further cycles and it
is spent. A seventh pass would most usefully be `adversarial` again, since each of its findings was
a route to green over a broken library, and its own report names what it did not examine: the prose
of twelve of the fourteen prompts, and the prompt-injection surface of the instructions those
prompts give to sessions.

## Residual risk

Nothing validates a posted handoff. The suite reads the prompts and asserts they mention each
required field; it says nothing about what a session actually emits, so a malformed handoff reaches
the next role undetected. That validator belongs with whatever first consumes these handoffs, and is
recorded in the README rather than silently omitted.

Prompt quality is not provable structurally. The suite proves headings, frontmatter, identifiers,
coverage and now slice completeness; whether a role prompt briefs a session well is proven by the
first roster run.

The lifecycle may move. Every prompt, the README, `index.json` and the test's pinned lists stamp
revision `67845cdd`, and tests assert both the prompts' `source:` and the checkout's head against
it, so divergence is loud rather than silent.
