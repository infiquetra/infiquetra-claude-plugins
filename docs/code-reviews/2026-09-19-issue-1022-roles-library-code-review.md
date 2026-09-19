---
title: Code review — issue 1022, roles library
reviewed_revision: 67172d53
status: cycle-cap
date: 2026-09-19
---

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
