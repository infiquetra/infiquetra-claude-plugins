---
title: Code review — issue 1022, roles library
reviewed_revision: 71f967c48c5b0e0e8e6f3d5f4a5e0a4f00000000
status: incomplete
date: 2026-09-19
---

# Code review — issue 1022, roles library

**Outcome: `review_incomplete`.** No lens refuted the deliverable, and every finding raised was
repaired. The review is nonetheless incomplete: of the seven lenses approved for this change, four
returned and three did not run. Under this repository's own rule that an outcome computed over a
partial roster reads exactly like a real one, that is not an acceptance, and it blocks. Only the
operator can override it.

The reviewed revision is `71f967c4` on branch `issue/1022`, against merge base `2044c363`.

> The frontmatter above names an abbreviated revision padded to forty characters because the review
> was written before a final commit existed. Treat `71f967c4` as the authoritative short revision
> and re-stamp this field when the review artifact is committed.

## What was reviewed

| Field | Value |
|---|---|
| Target | branch `issue/1022`, no pull request |
| Merge base | `2044c363` (also `main` and the integration branch today) |
| Reviewed revision | `71f967c4` |
| Diff | 2,579 insertions across 24 files at first review; one repair commit since |
| Criteria frozen | `docs/evidence/issue-1022/criteria-code-review-b67701c1...json` |
| Backend | inline |
| Cycles | 1 review cycle, 1 repair cycle |

## Lens roster and what each returned

| Lens | Class | Ran | Gating findings | Result |
|---|---|---|---|---|
| `correctness` | always-on | yes, twice independently | none | findings repaired |
| `testing` | always-on | yes | 3 × P1 | all repaired |
| `security` | always-on | yes | none | 1 × P3 advisory, accepted |
| `architecture-maintainability` | always-on | **no** | — | did not return in time |
| `documentation-clarity` | conditional | **no** | — | recommended, not run |
| `agent-usability` | conditional | **no** | — | recommended, not run |
| `adversarial` | conditional | **no** | — | recommended, not run |

The four conditionals I did **not** recommend, and why each has no applicable dimension against this
change: `deployment-infrastructure`, `reliability`, `performance`, `api-contract`, `privacy`,
`previous-comments` (no prior cycle), `accessibility-human-usability`, `experience`.

## Findings, by priority

### P1 — gating, all repaired

**T1. The seeded fixtures proved a property of the regular-expression library, not that the rules
fire.** The heading rule, the lens-section rule and the forbidden-vocabulary rule existed only as
inline expressions inside the parametrized tests, so a fixture could not call them and instead
re-typed the literal. Changing the rule left every fixture green. *Repaired:* each rule is now a
named checker function that the real test and its fixture both call.

**T2. The live-versus-pinned identifier source degraded silently, and never fired where the gate
runs.** The sibling-checkout resolution looked one level above the repository root; in a git
worktree that is the `worktrees` directory, so the live read never resolved and the suite silently
used the pinned lists — making the drift the design exists to catch invisible exactly where it
matters. *Repaired:* the resolution walks ancestors, and the resolved source is named in every
assertion message so a verdict that differs between machines says why.

**T3. Three plan requirements had no enforcing test.** R7 (no role the lifecycle does not name, and
no scanner, validator or monitor shape), R9 (the three release surfaces agreeing and advancing) and
R10 (the retired-prompt accounting) were asserted in prose and by nothing else. *Repaired:* three
new tests, including a both-directions identity check between the role identifiers the prompts
declare and the lifecycle's staffable set, which is what stops a scanner file passing by reusing a
legitimate identifier.

### P2 — repaired

**C1. The frontmatter parser silently emptied a list.** A mis-indented list item fell through and
vanished, turning a role that emits two contracts into one that appeared to emit none — which the
contract loop then accepted by iterating zero times, indistinguishable from the Lens Reviewer's
legitimate empty list. *Repaired:* items parse at any indent; duplicate keys, indented keys and junk
lines raise instead of being swallowed; empty values no longer satisfy the presence check; and only
the one aggregated prompt may have an empty list.

**C2. `emits` was checked for membership but not producership.** Any of the sixteen contract
identifiers satisfied the check, so `product.md` claiming `run-record` would have passed.
*Repaired:* the emitting role must be the contract's sender of record, with the two repair roles
licensed to reuse the initial worker's contract exactly as the lifecycle's own sender note allows.

**C3. Two prompts omitted required contract fields.** The Delivery Manager declared
`investigation-request` and `release-handoff` without naming any of their eight required fields, and
the Functional Tester dropped `grouped_failures` and reduced `per_target_conditions` to a phrase.
Both matter because the README states a prompt is the whole of a fresh session's briefing.
*Repaired:* both enumerate their fields, and the Functional Tester restores the grouping discipline
together with its epistemic hedge — group by suspected cause without claiming the cause is
established.

**C4. The Functional Tester named its contract differently from the lifecycle.** The only one of the
fifteen handoff headings that disagreed. *Repaired.*

**C5. The file count was counted over the whole directory, including the README**, so deleting a
prompt still satisfied the floor. *Repaired:* counted over prompts, plus an exact set-equality check
between the files and the README's map.

### P3 — repaired or accepted

Repaired: the repair prompts now cite the lifecycle's sender note that licenses their contract reuse
rather than presenting it as an inference; the plugin README points at the new directory, which
nothing referenced; an unmapped file now fails with a message rather than a bare `KeyError`; the
strictness-value check matches a pattern rather than three exact spellings; the retired-vocabulary
list covers more than two tokens; heading order and non-empty sections are enforced, and headings
inside fenced examples no longer count.

Accepted without change: the test reads an environment variable and walks parent directories. The
security lens judged this noise rather than risk — anyone who can set that variable already has
local execution — and the determinism concern it raises is now mitigated by naming the resolved
source in assertion messages.

## What the lenses upheld

The correctness lens verified, element by element, that all three pinned identifier lists match the
lifecycle's live configuration, and that every one of the fourteen prompts declares a `role_id` and
an `emits` the lifecycle agrees with — all sixteen contracts have exactly one producing prompt, and
the Human Operator correctly has none.

The security lens checked every prompt's authority boundary against the lifecycle's role catalogue
and found no widening: no self-approval, no self-granted merge turn, no production promotion, no
scope widening beyond operator grant, no threshold override. It found no secret, no egress
instruction, and no directive telling a session to obey content from an untrusted source.

I closed the one item the security lens could not reach: the marketplace and manifest diffs are one
version line each, introducing no source, dependency or install-location change.

## Why this is not an acceptance

Three approved lenses did not run, and one of them —`architecture-maintainability` — is one of the
four the roster always selects. The most valuable unrun lens for a change of this shape is
`documentation-clarity`, because the change is almost entirely documentation, followed by
`agent-usability`, because these files are consumed by agents rather than read by people.

Finishing them is bounded work: each returned lens took between one and seven minutes. The reason
they did not run is a concurrency limit of one subagent in flight combined with the wall time each
lens costs, not anything about the change.

## A mechanism finding worth carrying

A lens spawned with worktree isolation received a worktree at the **base** commit rather than at the
branch head, so it could read the changed files only by reaching into the sibling worktree and could
not run `git diff` at all. It said so plainly, which is why its unverified item was visible and
could be closed by hand. A lens less careful about naming what it did not examine would have
returned a confident review of the wrong revision.

## Residual risk

Prompt quality is not provable by a structural test. The suite proves headings, frontmatter,
identifiers and coverage; whether a role prompt actually briefs a fresh session well is proven by
the first roster run that consumes it.

The lifecycle may move. Every prompt, the README and the test's pinned lists stamp revision
`67845cdd`, and a new test asserts each prompt's `source:` names it, so divergence is visible rather
than silent — but nothing prevents it.
