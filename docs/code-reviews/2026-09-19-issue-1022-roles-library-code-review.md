---
title: Code review — issue 1022, roles library
reviewed_revision: a3832a26
status: incomplete
date: 2026-09-19
---

# Code review — issue 1022, roles library

**Outcome: `review_incomplete`.** Six of the seven approved lenses returned. Between them they
raised twelve gating findings, including one P0, and every one is repaired across four cycles. The
seventh lens — `adversarial` — was launched against the current head and has not returned. Under the
rule that an outcome computed over a partial roster reads exactly like a real one, that is not an
acceptance, and it blocks. Only the operator can override.

Base `2044c363`. Head at the time of writing `a3832a26`.

## Lens roster

| Lens | Class | Revision reviewed | Gating findings | Outcome |
|---|---|---|---|---|
| `correctness` | always-on | `b67701c1` (twice, independently) | none | advisory findings repaired |
| `testing` | always-on | `b67701c1` | 3 × P1 | all repaired, cycle 1 |
| `security` | always-on | `71f967c4` | none | 1 × P3 accepted; its one open item closed by hand |
| `architecture-maintainability` | always-on | `71f967c4` | 3 × P1 | all repaired, cycle 2 |
| `documentation-clarity` | conditional | `9680b8a1` | 5 × P1 | all repaired, cycle 3 |
| `agent-usability` | conditional | `8b565638` | 1 × P0, 6 × P1 | all repaired, cycle 4 |
| `adversarial` | conditional | `a3832a26` | — | **did not return** |

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

## Why this is not an acceptance

One approved lens has not reported. `adversarial` is the lens most likely to find what the other six
missed, because its dimensions are exactly the class of defect this review kept turning up:
load-bearing assumptions and silent green. Two such defects were already found and fixed — a search
for files lacking a heading that returned empty because the contract document quotes the heading,
and a slice that dropped an instruction because the test examined the file rather than the artifact.
A third is plausible and unlooked-for.

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
