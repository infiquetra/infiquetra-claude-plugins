# Code Review — board vocabulary drift, issue 1020

**Outcome: ACCEPTED BY EXPLICIT OPERATOR OVERRIDE at 8.6, on 2026-09-19.** The review itself did
not reach the 9.0 bar in any of its three rounds. The operator overrode that bar in these words:

> "8.6 is fine, its accepted"

That is an override of a blocking gate, not a passing score, and it is recorded here as such so no
later reader mistakes the one for the other. The numbers below are what the lenses actually
returned.

**Three rounds ran; the last came closest at 8.6 with nothing gating open.** Round one finished at
7.6 with an open P1. Round two, a fresh run on the repaired tree, finished at 8.5 with two P2s, both
then repaired. Round three was a scoring pass on the final head, ordered because the last two
commits had never been reviewed: it found no P0 and no P1 in any of the seven lenses, every
dimension at or above the 7.0 floor, and an overall of 8.6.

## Residuals carried past the override

Two P2 findings were recorded and deliberately not repaired. The run coordinator will file each as a
follow-up defect card; neither is a defect this change introduced, and both concern a different
retired vocabulary from the one this card names.

1. **Retired Mount Olympus vocabulary reads as current in three files this change edited.**
   `plugins/mission-control/skills/milestones/SKILL.md:122` names `Assigned` and `In Review` as
   states to watch; `:123`, `plugins/mission-control/skills/metrics/SKILL.md:145` and
   `plugins/mission-control/skills/metrics/references/metrics-targets.md:96` present `Needs Question`
   as a live state; and `metrics-targets.md:111` instructs an agent to write it. None is a Status on
   any live board and `LIVE_LEGACY_STATUS_ALIASES` has no key for any of them, so no migration hint
   fires. The prose guard added by this card cannot see them: it covers the names the board-stage
   migration renamed plus `Done`, not the older Mount Olympus set.

2. **The `--status` help string offers three values no board accepts.**
   `plugins/mission-control/scripts/sdlc_manager.py:7313` reads
   `help="Target status (e.g. 'Assigned', 'In Review', 'Active')"`, which argparse prints on a parse
   error — so an agent whose Status was just rejected is handed three more rejected ones. Pre-existing
   and untouched here. `:7320` similarly registers `board wip` as "Show WIP counts and limits" while
   the function's own docstring and the rewritten reference both say limits are retired.

Together these mark the guard's boundary: it sweeps Markdown instruction surfaces and the
W13-renamed names. Argparse help strings in the Python sources and the Mount Olympus vocabulary sit
outside it.

The honest summary across all three rounds: every finding raised was real, every one was verified
against repository source before being accepted, and six of them were defects the driver had
introduced while repairing earlier ones. That pattern is set out under "What the rounds cost".

## Review-result contract

| Field | Value |
|---|---|
| Target | Branch `issue/1020` against base `2044c363` (today both `main` and the integration branch `parent/1018`) |
| Reviewed revision | `9ab008b3` |
| Outcome | `accepted` **by operator override**, 2026-09-19 — the lenses returned 8.6 against a 9.0 bar, which is `repairs requested` on the roster's own rule |
| Override | Explicit, by the operator, quoted verbatim: "8.6 is fine, its accepted" |
| Residuals carried | Two P2 findings, to be filed as follow-up defect cards by the run coordinator |
| Mode | Interactive, caller-supplied lens selection |
| Lens selection | `accept-recommended`, supplied by the run coordinator |
| Lenses | Always-on four: architecture-maintainability, correctness, security, testing. Conditionals: api-contract, documentation-clarity, agent-usability |
| Acceptance rule | `review_result.v1`: derived overall ≥ 9.0 and every applicable dimension ≥ 7.0 |
| Criteria frozen | `docs/evidence/issue-1020/criteria-code-review-e2f63f95285bc897801c1ff4f732b55fca292ace.json`, hash-chained in `ledger.jsonl` |
| Repair cycles used | 3 of 3 |
| Fixer dispatch | Never offered; all repairs were made by hand in this worktree |
| Pull request | None opened; nothing pushed |

## Scores at the reviewed revision

| Lens | Cycle 2 | Cycle 3 | Cycle 4 (head) |
|---|---|---|---|
| architecture-maintainability | 8.5 | 9.0 | 9.0 |
| testing | 8.5 | 8.5 | 7.5 |
| api-contract | 8.5 | 9.0 | 9.0 |
| documentation-clarity | 7.0 | 6.5 | **6.0** |
| agent-usability | 7.0 | 7.5 | **6.5** |
| correctness (cycle 1) | 9.0 | — | — |
| security (cycle 1) | 9.5 | — | — |
| **Overall** | **7.9** | **8.1** | **7.6** |

Documentation-clarity and agent-usability are both below the 7.0 per-dimension floor, so the
shortfall is disqualifying rather than merely short of the average.

## The open P1

**Six invalid Status values still ship in agent-facing prose, and the guard written to catch them
cannot see any of them.** Each was verified by reading the file at the branch head.

| Location | Text | Why it fails |
|---|---|---|
| `agents/sdlc-operator.md:412` | `board move … --status Ready` | `Ready` is retired; unquoted, so the guard's pattern misses it |
| `agents/sdlc-operator.md:411` | `# 4. Move to Ready if context complete; else keep in Backlog or Shaping` | `Ready` retired, `Shaping` is a Stage |
| `commands/triage.md:27` | `Recommends initial board status (Ready if context complete, Backlog or Shaping if missing context)` | same two names |
| `commands/triage.md:51` | `--field Status --option Ready` | writes Status without the `--status` flag |
| `skills/flow/SKILL.md:84` | `--field Status --option Active` | `Active` is a Stage, not a Status |
| `skills/flow/SKILL.md:89` and `:94` | `--field Status --option Idea` | `Idea` is retired |

`LIVE_LEGACY_STATUS_ALIASES` (`sdlc_manager.py:297`) carries no entry for `Ready`, `Active`, `Idea`
or `Shaping`, so an agent following any of these lines gets a rejected option with no migration hint.

**Two things make this worse than the same defect scored P2 a cycle earlier, and both are mine.**

First, `CHANGELOG.md:44` now asserts "**No prose surface shows a command that cannot succeed**". That
is false at this head. A future reader has a written reason not to look.

Second, `commands/triage.md` contradicts itself 47 lines apart, inside the very diff that claimed to
fix it: line 27 still summarizes step 8 as "Ready … Backlog or Shaping" while lines 73-79, which I
rewrote, say `Implementing` / `Ready for Planning` / `Backlog` or `Discovering`.

**The guard does exactly what its own journal entry forbids.** `tests/test_board_schema_drift.py`
matches `--status\s+"([^"]+)"`, which requires the double quotes and that one flag spelling. The
plugin writes Status three other ways: unquoted after `--status`, via `--field Status --option`, and
as a bare English name in a sentence. The learning committed alongside it
(`{#1020-sweep-names-not-ladders}`) states the rule "match the NAME, and check each hit against the
authoritative list — do not match the syntax the name happened to appear in". The guard encodes a
syntax. I wrote the rule and then broke it in the same commit, which is the sharpest evidence in
this review that a guard has to be tested against the thing it is guarding, not against the case its
author had in mind.

**Smallest fix**, for whoever picks this up: broaden the pattern to
`--status\s+(?:"([^"]+)"|'([^']+)'|(\S+))`, add a second pattern for
`--field\s+Status\s+--option\s+(?:"([^"]+)"|(\S+))`, correct the six lines
(`Ready` → `Ready for Planning`, `Idea` → `Capturing`, `Active` → `Implementing`,
`Shaping` → `Discovering`), and either fix the two bare-English lines by hand or narrow the
changelog sentence to what the test actually proves. The bare-name case resists guarding without
false positives against ordinary prose such as "Active board".

## Also open at the end of round one (since closed)

**P3 — the cycle-time note inverted first for last, in four places.** Closed in `9ab008b3`;
all four copies now read "first carried".

*Original finding, for the record:* the note said the start boundary is It says the start boundary is
"whichever field **last** carried an option named `Active`". `metrics_cycle_time` pins `dev_start` on
the earliest matching transition, not the latest. The four copies are
`skills/metrics/SKILL.md:47`, `skills/metrics/references/metrics-targets.md:18`,
`skills/board/references/kanban-workflow.md:131` and `CHANGELOG.md:39`.

## What the four cycles did close

Fourteen findings were raised across the run, verified against repository source, and repaired. The
ones worth remembering:

- **A P1 the plan's own blast-radius analysis missed.** `check_issue_contract_parity.py` consumes the
  census by importing the producing function and never naming the artifact, so a search for the
  filename could not find it. It would have raised `TypeError`, and neither the gate nor continuous
  integration would have caught it: the path is live-gated and skips without a token, and its tests
  inject a fixture in place of the real producer.
- **A guard that could have covered nothing.** Every assertion in the new drift test is parametrized
  over the active-board list, and nothing asserted the list was populated. Confirmed empirically
  against pytest, then pinned.
- **A regression introduced by a repair.** A bare `except ValueError` added to stop a duplicate-name
  error being swallowed also caught `json.JSONDecodeError`, turning a documented skip into a hard
  failure. Now a typed `DuplicateFieldNameError`, with both paths proven and pinned.
- **A silent green introduced by a repair.** Moving the live leg onto `cmd_check()` was right, but
  that function returns 0 both on a match and on missing credentials, and pytest hides output on a
  pass. Now converted to a real skip, proven by forcing the unavailable path.
- **An overclaim introduced by a repair.** A note asserting `metrics cycle-time` "matches nothing on
  any board" was not supported by the code; the timeline query cannot distinguish the two fields at
  all. Retracted and rewritten to what the code shows.

## Verification performed rather than asserted

- Both live checks pass against the real boards: `board_census.py --check` and
  `check_issue_contract_parity.py --live`.
- The drift guard was proven red against the pre-regeneration census (12 failures) before being
  trusted, and the prose guard was proven red by seeding an invalid value.
- The census is byte-stable under its own serialization and internally consistent: every field
  record's name equals its key, across all three boards.
- No live board has a duplicate field name, so the new hard error is unreachable during this
  regeneration.
- The full inner loop is green at the head: `ruff check .`, `ruff format --check .`,
  `mypy plugins/ scripts/ tests/`, 525 tests passed with 1 skipped and 1 xfailed,
  `check_release_surface_parity.py`, `release_surface_diff_guard.py --base-ref 2044c363`, and
  `sync_marketplace.py --check`.

## A note on the evidence ledger

The ledger carries two criteria entries. Sequence 1 is keyed to a commit identifier that does not
exist — the reviewer typed a revision from memory instead of reading it. It is left in place rather
than edited, because the ledger is append-only and hash-chained and removing a row is what the chain
exists to prevent. Sequence 2 is the real freeze. `verify-chain` reports two entries, two verified
criteria.

---

# Round two — fresh run on the repaired tree

Approved by the run coordinator with the same seven-lens roster and `accept-recommended`, a fresh
repair allowance, backend inline. Each lens was spawned with worktree isolation and instructed to
`/usr/bin/git checkout --detach <sha>` before reading, because an isolated worktree otherwise starts
on the base commit and would review the wrong tree.

## Roster

| Lens | Revision reviewed | Score | Gating findings | Resolution |
|---|---|---|---|---|
| correctness | `1197c986` | 8.5 | P2: the prose guard shipped with a live instance of the class it exists to stop (`Done` missing from the bare-name pattern) | Repaired in `bf69f927` |
| security | `1197c986` | 10.0 | None | — |
| architecture-maintainability | `da9d2a05` | 8.5 | None | — |
| testing | `da9d2a05` | 9.0 | P2 (on `bf69f927`): the guard's own helpers had no direct test; two evasions demonstrated | Repaired in `da9d2a05` |
| api-contract | `da9d2a05` | 8.0 | P2: a documented command exits 2 | Repaired in `b7b859bf` |
| documentation-clarity | `da9d2a05` | 8.0 | Same broken command | Repaired in `b7b859bf` |
| agent-usability | `da9d2a05` | 7.5 | P2 (on `bf69f927`): instructions wrote a Status without the Stage it implies | Repaired in `da9d2a05`; the repair itself carried the broken command, fixed in `b7b859bf` |

**Round overall: 8.5.** Every dimension at or above 7.0; the bar is 9.0, so the round does not
accept. The reviewer's own assessment was that the two remaining P2s were "a one-token fix and a
one-condition fix" that together would carry the round over the bar. Both are now made, in
`b7b859bf`, which no lens has reviewed.

## What the rounds cost, and what that is worth recording

Six findings across the two rounds were defects introduced by a repair to an earlier finding:

1. A bare `except ValueError` added to stop a duplicate-name error being swallowed also caught
   `json.JSONDecodeError`, turning a documented skip into a hard failure.
2. Moving the live leg onto `cmd_check()` made it return green when credentials were missing,
   because that function returns 0 for two different reasons and pytest hides output on a pass.
3. A note written to correct someone else's inaccuracy asserted a mechanism that had not been
   traced: the timeline query cannot distinguish a Stage change from a Status change at all.
4. A comment claimed a `json.JSONDecodeError` reaches a SKIP branch it does not reach.
5. The prose guard, written from a rule that says "match the NAME, not the syntax", encoded a
   syntax — and shipped in the same commit as the rule it violated.
6. The command added to fix the Stage-and-Status pairing omitted a required argument and exited 2,
   which is worse than the omission it was meant to fix.

The pattern is one thing, not six: each repair was made confidently and verified narrowly. The
counter-measure that actually worked was mechanical rather than attentional — proving a guard red
before trusting it green, and mutation-testing a test by reverting the fix it covers. Every guard
in `tests/test_board_schema_drift.py` has now been watched to fail, and the two newest were
confirmed to die when their fix is reverted.

## Open at the final head

Nothing gating that a lens has named. The reviewer recorded four further value-syntax evasions
(`--field "Status"`, `--field=Status --option=Done`, reversed flag order, and a backslash-wrapped
`--status`) as P3. None appears in the plugin's prose today. An earlier version of this section
said three of the four were "backstopped by the bare-name scan"; round three corrected that --
the bare-name scan catches a value only when it is itself a retired name, so a live Stage name
such as `Active` written as a Status escapes all four forms with no backstop at all.

Two findings were deliberately declined and the reviewer ruled on both. The 2.17.0 minor bump for a
change labelled BREAKING is defensible under the repository's own recorded test — whether a caller
can observe the change — with the caveat that the "no external consumer" premise was verified only
within this repository. The reviewer withdrew the test-file-location finding outright: the card
names that path in an executable criterion and the repository instruction agrees.

---

# Round three — scoring pass on the final head

Ordered by the run coordinator because nothing gating was open and the only gap was that the last
two commits had never been reviewed. A scoring pass, not a repair pass: P0 and P1 would trigger one
repair, and P2 and P3 are recorded rather than acted on. Same seven-lens roster,
`accept-recommended`, backend inline, opus/high, one reviewer in flight, each lens instructed to
`/usr/bin/git checkout --detach 87f9316b` and to confirm the revision in its first line. Both groups
confirmed `87f9316b261619dd425312fff0bacc8c86e8a1bf`.

## Roster

| Lens | Revision reviewed | Score | Gating findings | Resolution |
|---|---|---|---|---|
| correctness | `87f9316b` | 9.0 | None | — |
| security | `87f9316b` | 10.0 | None | — |
| architecture-maintainability | `87f9316b` | 8.5 | None | — |
| testing | `87f9316b` | 9.0 | None | — |
| api-contract | `87f9316b` | 9.0 | None | — |
| documentation-clarity | `87f9316b` | 7.5 | None | — |
| agent-usability | `87f9316b` | 7.5 | None | — |

**Round overall: 8.6.** No P0 and no P1 anywhere in the roster. Every dimension is at or above the
7.0 floor. The bar is 9.0, so the round does not accept, and because nothing gating was raised no
repair was permitted in it.

## What this round added that the earlier ones could not

Two independent verifications that had previously rested on the driver's own word:

- **The census really does match the live boards.** A lens with a project-scoped token ran the
  opt-in leg (`BOARD_SCHEMA_LIVE=1`), which calls `board_census.cmd_check()` against the three real
  GitHub project boards. It passed. Until this round that claim rested on the driver's regeneration
  run.
- **The prose guard really was red before the fix.** A lens ran `_status_values` and
  `_history_exempt_lines` over `git show 2044c363:` copies of all 21 surfaces and counted 12
  flag-form offenders and 46 bare-name offenders, substantiating the "confirmed red" claim rather
  than accepting it. The same lens mutation-tested twelve changes to the guard's logic; eleven
  killed a test, and the one survivor was a vacuity pin rather than logic.

## The two P2 findings, recorded and not repaired

**P2-A — retired Mount Olympus vocabulary still reads as current in three files this change edited.**
`skills/milestones/SKILL.md:122` names `Assigned` and `In Review` as states to watch; `:123`,
`skills/metrics/SKILL.md:145` and `skills/metrics/references/metrics-targets.md:96` present
`Needs Question` as a live state; and `metrics-targets.md:111` instructs an agent to *write* it.
None is a Status on any live board, and `LIVE_LEGACY_STATUS_ALIASES` has no key for any of them, so
no migration hint fires. This is the same defect class the card exists to close, inside the scope the
card edited, and the guard cannot see it: `BARE_RETIRED_NAME` covers the six names the board-stage
migration renamed plus `Done`, not the older Mount Olympus set.

**P2-B — the `--status` help string offers three values no board accepts.**
`scripts/sdlc_manager.py:7313` reads `help="Target status (e.g. 'Assigned', 'In Review', 'Active')"`,
which argparse prints on a parse error — so an agent whose Status was rejected is handed three more
rejected ones. It is pre-existing and untouched here, but the guard sweeps `*.md` only, and the
changelog's bolded claim reads broader than the body's own scoping to the 21 Markdown surfaces.
`sdlc_manager.py:7320` similarly still registers `board wip` as "Show WIP counts and limits" while
the function's own docstring and the rewritten reference both say limits are retired.

Together these say something the earlier rounds did not: the guard's boundary is `*.md` instruction
surfaces and the W13-renamed names. Argparse help strings and the Mount Olympus vocabulary both sit
outside it, and the prose describing the guard should say so rather than implying it covers the
class.

## P3 findings, recorded

- The guard misses four alternate spellings — `--status=Active`, `--field=Status --option=Active`,
  reversed flag order, and `--field "Status"`. None appears in the plugin today. Two documents
  overstate this: the learning says the guard "checks every syntax" and the round-two section says
  three of the four are "backstopped by the bare-name scan", which holds only when the value is a
  retired name, not a live Stage name used as a Status.
- The work-session write-up says thirteen synthetic helper tests; there are fifteen at this head.
- A latent false positive: a `--field Status` with no `--option` and no later `--field` lets the
  whole-file scan run to end-of-file and read an unrelated `--option` as a Status. It can only fail
  a build wrongly, never pass a real offender.
- The `except ImportError` fallback in `check_issue_contract_parity.py` and the two new `cmd_check`
  branches in `board_census.py` have no direct tests, where their parity-script equivalents do.
- The "Also open" heading in the round-one section is stale: the first-versus-last inversion it
  describes was closed in `9ab008b3`. The heading does not say which revision it belonged to.
- **A toolchain caveat on the inner-loop claim.** A lens reported `ruff check .` and
  `ruff format --check .` failing in its worktree. Re-verified at this head with the project's
  synced environment (ruff 0.15.12): both pass, exit 0. The lens resolved ruff 0.16.5, which flags
  pre-existing issues in `plugins/home-lab-ops` and some `docs/analysis` code blocks — files outside
  this diff. `pyproject.toml` pins only `ruff>=0.4`, so both observations are true and the
  difference is version drift. That loose pin is worth a card of its own: continuous integration can
  start failing on files nobody touched.
