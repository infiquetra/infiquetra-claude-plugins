# Code Review — board vocabulary drift, issue 1020

**Verdict: NOT ACCEPTED.** Four cycles ran. The overall score went 9.2 (two lenses), then 7.9, 8.1
and 7.6 across the five-lens set, against an acceptance bar of 9.0 with every applicable dimension
at 7.0 or better. At the branch head two dimensions sit below the per-dimension floor and one P1
finding is open. The three repair cycles allowed by the run coordinator are spent, so this review
stops here and hands the finding to the operator. Only the operator can override a blocking gate.

## Review-result contract

| Field | Value |
|---|---|
| Target | Branch `issue/1020` against base `2044c363` (today both `main` and the integration branch `parent/1018`) |
| Reviewed revision | `9ab008b3` |
| Outcome | `repairs requested` — not `accepted` |
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

## Also open

**P3 — the cycle-time note inverts first for last, in four places.** It says the start boundary is
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
