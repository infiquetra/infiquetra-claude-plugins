---
title: Issue 907 planner handoff — one decision-complete plan for all 91 terminal-validation findings
type: fix
status: handoff
date: 2026-09-01
origin: https://github.com/infiquetra/infiquetra-claude-plugins/issues/907
frozen_revision: dd3593ab7263541ef1ad87e69f2366f64a724d33
authoritative_artifact: docs/code-reviews/2026-08-31-issue-907-terminal-validation-result.v1.json
backend: inline
---

# Issue 907 planner handoff

You are `cp907-planner`. This document is your authoritative brief. It was assembled by the run
coordinator from durable Git state, the checked-in review artifacts, the append-only evidence
ledger, the test tree and the live issue contract. **No part of it came from any worker session's
prose report**, and you must not treat a worker's self-summary as authority either.

Your deliverable is **one decision-complete Saga implementation plan**. You do not write product
code in this phase.

---

## 1. Durable state, verified at handoff time

| Item | Value |
|---|---|
| Worktree | `/Users/jefcox/workspace/infiquetra/orch-claude-plugins-907` |
| Branch | `work/cp907-launcher-session-contract` |
| `HEAD` | `0b7eb0c0` — `docs(review): record the terminal Saga validation review for issue 907` |
| Working tree | Clean at handoff (`git status --short` empty apart from this handoff file, which is uncommitted) |
| Frozen reviewed revision | `dd3593ab7263541ef1ad87e69f2366f64a724d33` |
| Source identical `dd3593ab` → `HEAD`? | Yes. `git diff --stat dd3593ab HEAD -- plugins/` is empty; `0b7eb0c0` is evidence-only |
| Branch vs `origin/main` | 23 commits ahead, **42 commits behind** |
| Merge base | `3b2b7083` |
| Branch pushed? | **No.** The branch has never been pushed and no pull request exists |
| Last full gate | `GATE GREEN — 25 steps ran, 0 blocking failures, 0 uncovered` in `/tmp/gate-cp907-p1c`, `GATE_EXIT=0`, run against `dd3593ab` |
| Saga present? | No. `saga.py scan` returns `{"candidates": [], "count": 0}`. Custody is the no-saga adhoc path |
| Evidence custody id | `adhoc-work-cp907-launcher-session-contract` |
| Ledger integrity | `verify-chain` → `{"entry_count": 10, "verified_artifacts": 5, "verified_criteria": 5}` |
| Issue states | All eight of 907, 890, 897, 896, 889, 888, 887 and 880 are **OPEN** |

### Authoritative artifacts — read these, do not re-derive them

| Path | sha256 (first 16) | What it is |
|---|---|---|
| `docs/code-reviews/2026-08-31-issue-907-terminal-validation-result.v1.json` | `c6a5f1dc2422c8df` | **Your input.** 91 findings bound to `dd3593ab` |
| `docs/code-reviews/2026-08-31-issue-907-terminal-validation-cycle-state.v1.json` | `92da1e871e850c17` | Controller cycle state for the same review |
| `docs/code-reviews/2026-08-31-issue-907-validation-review-result.v1.json` | `ab48176bb0a6bfbc` | Prior validation, bound to `39e66d17`, 22 P1 |
| `docs/code-reviews/2026-08-30-issue-907-cycle-3-review-result.v1.json` | `b6155de1262e5f67` | Terminal numbered cycle, bound to `a7ba2995` |
| `docs/evidence/adhoc-work-cp907-launcher-session-contract/ledger.jsonl` | — | Append-only, 10 entries, alternating criteria/evidence |

Enumerate the full finding set with:

```bash
jq -r '.findings[] | "\(.finding_id)\t\(.severity)\t\(.lens_id)\tpre_existing=\(.pre_existing)\t\(.title)"' \
  docs/code-reviews/2026-08-31-issue-907-terminal-validation-result.v1.json
```

Verified counts: **91 findings, 91 unique identifiers, 18 P1 / 43 P2 / 30 P3, 15 marked
`pre_existing: true`.** Per lens: architecture-maintainability 20, testing 14, correctness 12,
documentation-clarity 12, reliability 12, api-contract 11, security 10.

---

## 2. What happened, in order, and why it matters to your plan

Five reviews have run against this branch. Three were numbered Saga Code Review cycles under a hard
cap of three; two were operator-authorized validation reviews after that cap closed.

| Review | Bound revision | Outcome | Blocking findings |
|---|---|---|---|
| Cycle 1 | `43498f14` | `repairs_requested` | 10 P1 |
| Cycle 2 | `cbc2fa19` | `repairs_requested` | 5 P1 |
| Cycle 3 (cap reached) | `a7ba2995` | `cycle_cap_best_available` | 3 P0, 15 P1 |
| Validation review | `39e66d17` | `repairs_requested` | 22 P1 |
| **Terminal validation** | **`dd3593ab`** | **`repairs_requested`** | **18 P1** |

Every lens scored **lower** on `dd3593ab` than on the revision the repair set out to improve:

| Lens | `39e66d17` | `dd3593ab` | Delta |
|---|---|---|---|
| correctness | 7.2000 | 5.4000 | −1.8000 |
| security | 7.5000 | 6.2000 | −1.3000 |
| api-contract | 7.0000 | 6.5714 | −0.4286 |
| testing | 6.6000 | 6.2000 | −0.4000 |
| architecture-maintainability | 7.2857 | 7.0000 | −0.2857 |
| reliability | 6.7000 | 6.5000 | −0.2000 |
| documentation-clarity | 7.1667 | 7.1000 | −0.0667 |

Acceptance requires `derived_overall >= 9.0` on every lens with every applicable dimension `>= 7.0`.
Nothing is close.

**The fact that must shape your plan.** The raw P1 count fell from 22 to 18, and that number is
misleading. Only **3 of the 18** are marked pre-existing. The other **15 are attributed to edits
`dd3593ab` itself made**, and **10 of those 15 carry an executed before-and-after comparison against
the immediately prior revision `2fe7c954`** showing behaviour that was correct becoming incorrect.
The repair pass did not stall — it moved backwards.

**The mechanism, stated plainly, because your plan exists to prevent its third occurrence.** Twice
now a repair has satisfied a finding by building that finding's mirror image:

- The prior validation found — its finding `REL-03`, "the staged-input branch in `cmd_go` clears
  the tab id" — that `cmd_go`'s staged-input branch **cleared** the tab identity, orphaning a live
  session beyond the reach of `clean`. The repair **stopped clearing it**, and now the same loop's
  `if unit.tab_id: continue` skip means the unit can never be relaunched by any command. That is
  terminal findings `API-01`, `CORR-03` and `REL-01`.
- The prior validation found — its finding `API-02`, "the new version floor is enforced at import" —
  that every read-only subcommand died on a stale companion. The repair **moved the check out of the
  loader**, and now a below-floor launcher loads and reaches pane writes, and `clean` and `land`
  silently lose close-failure evidence. That is terminal findings `SEC-03` and `API-02`.

Both repairs were correct about the finding and wrong about the invariant. **Every repair unit in
your plan must name the invariant that has to hold on both sides, and must carry a proof for the
direction it is not fixing.** A repair that only proves the new behaviour is how this run got here.

---

## 3. Deduplicated P1 ledger — eight underlying defects behind eighteen findings

This clustering is the coordinator's adjudication of the P1 tier. **Treat it as a starting position
you must verify against the artifact and the tree, not as a conclusion to adopt.** If your own
reading disagrees, say so in the plan with evidence. The P2 and P3 tiers are yours to cluster; this
section does not cover them.

| # | Underlying defect | Findings | Scope class |
|---|---|---|---|
| A | Composer continuation and emptiness rules were retightened on border geometry the real captures do not have | `CORR-01`, `CORR-02`, `TEST-01`, `TEST-02`, `TEST-07` | Latest-repair regression |
| B | Resend guard condition swapped from "did we type into the pane" to "do we own the tab" | `SEC-01` | Latest-repair regression |
| C | Staged-input stop permanently wedges the unit | `API-01`, `CORR-03`, `REL-01` | Latest-repair regression |
| D | Version-floor validation moved from fail-closed to fail-open, with nothing binding which commands are gated | `SEC-03`, `API-02`, `TEST-04`, `TEST-03` | Latest-repair regression |
| E | `SKILL.md` describes an `input_box_text_chars` the code does not compute | `DOCC-01` | Latest-repair regression |
| F | The 43-pane harness claim still stands in the engineering journal | `DOCC-06`, `TEST-06` | Carried unresolved |
| G | `origin/main` ships two orchestrate documentation sentences this branch falsifies, and they auto-merge without a conflict | `DOCC-04` | **Operator decision** |
| H | `review-result` and `land` write into panes with no composer inspection at any ownership | `SEC-02` | **Operator decision** |

Eighteen findings, eight defects, and the arithmetic closes: 5 + 1 + 3 + 4 + 1 + 2 + 1 + 1 = 18.

### Confidence caveats you must adjudicate rather than inherit

`CORR-01` and `CORR-02` carry confidence 75 and the reviewer's own written caveat that the vendor
styling assumption was constructed, not observed live. Their probes were executed against the real
guard, so the mechanism is proven; what is not proven is that a live vendor draws that shape.
**Adjudicate both against the two real captures in
`plugins/agent-launcher/tests/fixtures/composer-panes.json` and, if you can, a live pane.** A
disproven finding is a legitimate ledger row — it just needs evidence, not an opinion.

---

## 4. Repair obligations, one per in-scope defect

For each of A through F below the plan must carry, in its own words and with its own verification:
observable failing behaviour, the invariant, the reproducer that proves failure **before** any edit,
the counter-cases that must stay passing, the narrow file set, and the proof after.

### A — Composer continuation and emptiness rules

**Failing behaviour.** `_is_continuation` at `composer.py:193` returns
`_has_leading_border(clean) and column > marker_column`. Neither entry in the repository's only real
pane captures is bordered, so for Claude and Codex no row is ever a continuation and a block is
always exactly one row. Two consequences, both executed by the reviewer: a multi-row draft is
truncated in the receipt (41 characters recorded as 22), and a pane whose first visual row carries
no unstyled character classifies `UNCLASSIFIABLE`, which `guard_pane_before_write` treats as
fail-open, so the dispatched prompt is typed onto the operator's unsent draft. Separately, the
`ambiguous_empty` rule at `composer.py:227` turns an empty marker row followed by an indented row of
real text into `UNCLASSIFIABLE`, which at `2fe7c954` classified `STAGED` and stopped the launch.

**Invariant.** A pane holding operator text must never be written into. Both directions bind: a real
draft must not classify `EMPTY` or `UNCLASSIFIABLE`, and an idle pane must not classify `STAGED`.
The rule that decides this must be expressed against shapes the repository can actually produce.

**Reproducer before editing.** Load `launcher.py` with its sibling `composer.py` at `dd3593ab`, stub
only `launcher.run` to return fixed pane bytes, and call the real `guard_pane_before_write`. The
reviewer's two panes are: (1) the fixture's Claude marker bytes plus a styled at-file mention on row
one, then two-space-indented unstyled text on row two; (2) the fixture's Claude marker alone on row
one, then two-space-indented text on row two. Both must currently report `PROMPT SENT` with receipt
`input_box = unclassifiable`. If they do not, say so — the finding is then wrong and the row becomes
a disproven finding with evidence.

**Counter-cases that must remain passing.** `test_glyph_led_last_visual_row_never_turns_a_staged_draft_into_empty`,
`test_adjacent_staged_and_empty_marker_rows_are_ambiguous`,
`test_ambiguous_composer_geometry_never_records_affirmative_empty`,
`test_echo_above_a_closed_span_placeholder_does_not_false_stop`. The positional
last-block selection in `inspect_composer` (`composer.py:288-302`, the selection itself at
`composer.py:302`) is load-bearing and was mutation-proven: restoring
last-classifiable selection reproduces a real `StagedInputError` false stop. Do not undo it.

**Deleted coverage that must come back.** `dd3593ab` deleted
`test_a_blank_marker_row_with_continuation_rows_is_one_block` and rewrote
`test_styled_wrapped_row_stays_in_a_proven_staged_block` from an unbordered wrapped row to a bordered
one, and changed `test_menu_marker_terminates_the_composer_block`'s expectation from
`draftcontinuation` to `draft`. Restoring behaviour without restoring these counter-cases repeats
the failure.

**Files.** `plugins/agent-launcher/skills/agent-launcher/scripts/composer.py`,
`plugins/agent-launcher/tests/test_launcher_contract.py`,
`plugins/agent-launcher/tests/fixtures/composer-panes.json`.

**Proof after.** Two surviving mutations are named in the artifact and both must be killed: C23
replaces the `ambiguous_empty` condition with `if not clean.strip():` (survived at 317 passed), and
C2 flips the `_is_continuation` blank-row `return False` to `return True` (survived at 317 passed
and at 6613 passed). A third region, the horizontal-rule clause at `composer.py:232`, is called out
as untested.

### B — Resend guard condition

**Failing behaviour.** `launcher.py:1419` reads `if not session_owned(unit):`, where `2fe7c954` read
`if used_pane:`. A pane the launcher created is therefore never inspected before a resend. Driven end
to end with an identical stubbed herdr and an identical pane holding text, the prior revision issued
one pane write then stopped with `StagedInputError`; the reviewed revision issued three unguarded
pane writes and never called the guard. `used_pane` is assigned at `launcher.py:1408` and `1421` and
never read — the dead store the swap left behind.

**Invariant.** Ownership is a claim about who created the tab, never about who last typed into it.
Any pane write that follows a first send which fell back to typing must re-inspect.

**The reviewer states the correct condition.** The disjunction `(not session_owned(unit) or
used_pane)`, not either half alone. Verify that before adopting it.

**Counter-cases.** `test_pane_fallback_resend_rechecks_for_staged_input` and
`test_agent_prompt_resend_rechecks_before_it_can_fall_back_to_the_pane` both build units whose receipt
tab is already in the pre-existing tab set, so `owned` is False in both and the two conditions are
indistinguishable. **Both tests pass under the defect.** A new case with `owned=True` is required, or
the repair is unbound again.

**Files.** `plugins/agent-launcher/skills/agent-launcher/scripts/launcher.py`, its contract tests.

### C — Staged-input stop wedges the unit permanently

**Failing behaviour.** The `except StagedInputError` branch at `orchestrate.py:2697` no longer clears
`tab_id`, `pane_id`, `agent_name`, `reused`, `owned` or `launch_receipt`. Fifteen lines earlier the
same loop opens with `if unit.tab_id: print("already has tab ...") ; continue` at
`orchestrate.py:2682`. The unit is saved `PENDING` carrying a tab, and every later `go` skips it before
`launch` is ever called. No subcommand in `orchestrate.py` assigns `tab_id` back to `None`, so
`clean`, `park`, `resume`, `adopt` and `check` cannot recover it either. Because `Run.eligible()`
requires every `after` dependency `DONE`, every downstream unit is blocked for the life of the run.
The only exit is hand-editing `.orchestrate/run.json`, which no document mentions.

**Invariant — and this is the one the last repair broke.** Both of these must hold at once:

1. A session the wrapper genuinely created must remain reachable by `clean` after a staged-input
   stop. This is the **prior validation's** finding `REL-03` — "the staged-input branch in `cmd_go`
   clears the tab id, so a tab the launcher created but could not prove it owns is orphaned beyond
   the reach of `clean`" — and it is the reason the clearing was removed.
2. A unit stopped for staged input must be relaunchable once the operator clears the composer,
   without hand-editing run state.

Neither revision satisfies both. `2fe7c954` satisfied (2) and violated (1); `dd3593ab` satisfies (1)
and violates (2). **Your plan must satisfy both, and must prove both.** A repair that flips back to
`2fe7c954`'s behaviour is a regression against a finding this run already accepted.

**Reproducer before editing.** Drive `cmd_go` twice against a run holding one `PENDING` unit, with
`launch` stubbed to set the identifiers then raise `StagedInputError`, and a second `launch` stub
that succeeds. At `dd3593ab` the second call prints `already has tab ...; not launching twice` and
total launch calls is 1. At `2fe7c954` the second call prints `launching ...` and total launch calls
is 2.

**Counter-case that currently locks the regression in.**
`tests/test_orchestrate_launch_and_land.py:426`, named
`test_staged_input_stop_returns_the_unit_to_retryable_pending`, calls `cmd_go` once and asserts only
that the identifiers were retained. It never attempts the retry. That test must exercise the retry,
or be replaced by one that does. **A test whose name claims a property it does not exercise is worse
than no test**, and this repository has a standing hazard record for exactly that shape.

**Files.** `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py`,
`tests/test_orchestrate_launch_and_land.py`, and whichever orchestrate document gains the
staged-input recovery runbook. There is currently no such runbook anywhere.

### D — Version-floor validation is fail-open with nothing binding the gate

**Failing behaviour.** `_ingest_agent_launcher` records a floor failure at the `except SystemExit`
branch of `orchestrate.py:1667-1672`
in `_AGENT_LAUNCHER_ERROR` and still returns `True`, so `_AGENT_LAUNCHER_AVAILABLE` stays `True` and
every launcher symbol comes from the below-floor plugin. The only brake is
`assert_agent_launcher_available()`, which exactly five commands call — `start`, `saga`, `roster`,
`expand`, `go` — and which `review-result` and `land` do not, and those two write into panes. Since
the composer guard itself shipped in agent-launcher 1.2.x, a downgraded 1.0.0 companion is precisely
a launcher with no guard, and it still reaches a pane write. Verified live: agent-launcher **1.0.0**
is what is in this machine's plugin cache, and its `close_run_session` is annotated as returning
`None` where 1.2.1 returns a `CompletedProcess`; the `reap` close-failure branch is guarded by
`close_result is not None`, so under 1.0.0 a failed tab close reads as success, the worktree is
force-removed, and stdout says `closed`. The evidence retention both CHANGELOGs advertise is
silently inoperative.

**Invariant.** A companion below the declared floor must not reach a pane write. Recovery commands
that genuinely need to run on a stale companion must be an explicit, named, tested allowlist — not a
side effect of which functions happen to be bound.

**Reproducer before editing.** Build a synthetic installed tree with the agent-launcher manifest
rewritten to 1.0.0 while the orchestrate manifest declares `>=1.2.1`, then import each revision.
`dd3593ab` reports `_AGENT_LAUNCHER_AVAILABLE = True` and `say()` then issues
`herdr pane run p1 ...`. `2fe7c954` fails closed at import.

**Surviving mutations that must be killed.** O5 appends `return False` to that `except SystemExit`
branch (`orchestrate.py:1669-1672`) and survives at 317 passed, though it genuinely breaks the documented recovery behaviour.
O18 deletes `orchestrate.py:1574-1586` — the whole `CLAUDE_PLUGIN_ROOT` discovery branch — and
survives, because the test helper `_run_installed_orchestrate` strips `CLAUDE_PLUGIN_ROOT` from the
child environment and never restores it. O16 and O17 degrade version selection to first-match and
lexical and both survive. O21 removes the `AGENT_LAUNCHER_ROOT` `SystemExit` and survives.

**Counter-case that cannot tell the mutant apart.**
`test_read_only_help_survives_a_stale_launcher_while_roster_enforces_the_floor` asserts only that
`help` exits 0 — which argparse satisfies before `assert_agent_launcher_available` runs — and that
`roster` fails with the floor message. Both are true under the mutant.

**Related surface the artifact also flags.** The `_agent_launcher_required` stub roster at
`orchestrate.py:1690-1704` — seventeen names, `launch` first and `clear_delivery_warning` last — is a
hand-maintained mirror of the launcher's export surface with nothing
binding the two, and the `except (SystemExit, Exception)` at `orchestrate.py:1679` can swallow a
partially completed `exec` that has already overwritten an unknown subset of module globals. The
directory-layout fact the floor depends on is written out five times as bare `parents[N]` literals.
Cluster these with D if your reading supports it.

**Files.** `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py`,
`tests/test_agent_launcher_plugin.py`, `plugins/orchestrate/skills/orchestrate/SKILL.md`.

### E — `input_box_text_chars` does not mean what the documents say

**Failing behaviour.** `SKILL.md:41` and `plugins/agent-launcher/README.md:35` both say the receipt records "the number of
characters positively recognized as staged". The parser positively recognizes only **unstyled**
characters as operator authorship, but `launcher.py:814` records `len(staged)` where `staged` is the
full visible text including client-styled runs. Executed: a pane where the operator typed two
characters and the client styled a 28-character remainder records **30**, where the positively
recognized count is **2**. Separately `_visible_after_marker` strips each row and joins rows with the
empty string, so a two-row 28-character draft records **27**. The prior wording, "the staged text's
length", was accurate; the repair replaced an accurate sentence with a false one.

**Invariant.** One definition of the number, in one place, with a test binding the document to the
behaviour. Either compute what the sentence says or say what the code computes — the plan must pick
one and justify it. This number is quoted back to the operator in a safety stop message, and a
`SKILL.md` in this repository is executable instruction an agent acts on.

**Coupling.** The value is also wrong because of defect A's truncation. Sequence E after A.

**Counter-case that does not bind.** `test_documented_input_box_receipt_schema_is_complete` asserts
only that seven value strings and two key names appear in the two surfaces. Nothing binds this clause.

**Files.** `plugins/agent-launcher/skills/agent-launcher/SKILL.md`,
`plugins/agent-launcher/README.md`, `launcher.py`, contract tests.

### F — The 43-pane claim still stands in the engineering journal

**Failing behaviour, verified by the coordinator at `HEAD`.** Three citations survive:

- `docs/engineering-journal/LEARNINGS.md:59` — "The cycle-3 reliability capture set contains 43 real
  pane viewports ... the repaired parser produces zero false stops on the same bytes."
- `docs/engineering-journal/LEARNINGS.md:62` — "`test_echo_above_a_closed_span_placeholder_does_not_false_stop`
  and the external 43-pane harness pin the original false-stop shape."
- `docs/engineering-journal/DECISIONS.md:47` — "which the 43-pane capture harness measured directly."

The checked-in fixture `plugins/agent-launcher/tests/fixtures/composer-panes.json` holds **two**
entries: `claude_echo_above_empty` and `codex_closed_placeholder`. No harness producing 43 exists
anywhere in the tree. A prior commit message carrying the same false claim was corrected, and
`dd3593ab` edited both journal files in the same commit that declined this finding, without adding a
caveat to either.

**Invariant.** This repository's `CLAUDE.md` requires a `LEARNINGS.md` entry to carry evidence a
reader can follow. Three citations here cannot be followed.

**Correct disposition.** A transparent residual recorded in the journal — the sweep happened, it was
a one-off against captures held outside the repository, it is not reproducible from this tree, and no
test reproduces it. Not a deletion that hides the history, and not a silent decline.

**Files.** `docs/engineering-journal/LEARNINGS.md`, `docs/engineering-journal/DECISIONS.md`. Note
both files also appear in the `origin/main` merge set — see section 7.

---

## 5. How the plan must be built — binding constraints

1. **No finding-by-finding example patching.** Every repair is class-level: fix the rule, not the
   listed instance. The artifact's examples are proof that a class is broken, not the definition of
   the work. A plan unit that says "patch the four cited lines" is not accepted.
2. **Mutation-first, evidence-before-edit.** Each unit reproduces the failure before any edit. Each
   unit names the mutation or behavioural probe that will kill the repair if it regresses, and runs
   it. A unit whose only evidence is "the suite is green" is not accepted — this repository has a
   standing hazard record for green suites that stand over real defects, and both failed repair
   rounds committed before anything independent had tried to break them.
3. **Prove the direction you are not fixing.** Defects C and D exist because a repair proved only its
   new behaviour. Every unit that changes a two-sided rule carries a counter-case for the old side.
4. **Prohibited overreach, stated per unit.** Name what the unit must not touch. Do not repair P2 or
   P3 findings inside a P1 unit unless the P1 fix unavoidably requires it, and say so when it does.
5. **No speculative hardening.** See the threat model in section 6.
6. **Preserve all prior artifacts.** Every review result, cycle state, frozen criteria file and
   ledger entry stays byte-identical. The evidence ledger is append-only. **Do not rewrite history**,
   do not amend or rebase the existing commits, and do not force-push anything.
7. **Ordering and dependencies are part of the plan.** At minimum: A before E; B and C are
   independent of A; D is independent but touches the same file as C. State the real graph.
8. **Release surfaces once.** Per this repository's `CLAUDE.md`, plugin behaviour changes update
   `plugin.json`, `.claude-plugin/marketplace.json` and the plugin `CHANGELOG.md` in the same
   pull request — and the diff-aware release-surface bump guard **reads committed state, not the
   working tree**, so a version bump must be committed before the gate can pass. Two gate runs in
   this run went red on exactly that.

### The 91-row traceability ledger

> **Identifiers are scoped to one review, and they collide across reviews.** Verified by the
> coordinator: `REL-03`, `API-02`, `CORR-01`, `CORR-02`, `CORR-03`, `SEC-01`, `TEST-01`, `TEST-02`,
> `TEST-03` and `TEST-04` all exist in **both** the terminal validation artifact and the prior
> validation artifact, and in every case they name a **different finding**. The prior validation's
> `REL-03` is a P1 about `cmd_go` clearing the tab id; the terminal artifact's `REL-03` is a P2 about
> `review-result` and `land` performing pane writes. **The ledger keys exclusively on
> `2026-08-31-issue-907-terminal-validation-result.v1.json`.** Anywhere the plan refers to a finding
> from an earlier review, name the artifact in the same sentence. Never write a bare identifier and
> expect a reader to know which review it came from.

The plan carries a ledger with **one row per finding, all 91, keyed by the artifact's own
`finding_id`.** No identifier may be dropped, merged away, or renamed. Each row resolves to exactly
one of:

| Disposition | Meaning | Required evidence |
|---|---|---|
| `repair-unit:<id>` | Mapped to a plan unit | The unit id, and the root cause it shares with its cluster |
| `duplicate-of:<finding_id>` | Same underlying defect as another row | Why they are the same defect, not merely the same file |
| `disproven` | The finding does not hold at the frozen revision | The executed check that disproves it |
| `pre-existing-followup` | Genuine, but not caused by this branch | Evidence of pre-existence, plus proposed custody — a new issue number or a named residual |
| `out-of-scope-followup` | Genuine, but outside the seven children | Why, plus proposed custody |

Deduplicate by root cause **for implementation**. Never drop a finding **from the ledger**. The
ledger is what makes the residual set honest, and an honest residual set is what this run has been
missing.

---

## 6. Threat model — read this before proposing any hardening

This is a **single-operator, single-machine, flat-subscription** tool. One person, one laptop, no
tenants, no untrusted callers, no network exposure.

The staged-input hazards in this artifact are **local correctness, data-preservation and
command-safety** risks. Concretely: the operator's unsent draft gets concatenated with a dispatched
task and submitted; a failed tab close is reported as success and a worktree is force-removed with
its evidence; a run wedges and cannot be recovered without hand-editing state. Those are real and
worth fixing precisely because they destroy the operator's work.

They are **not** multi-tenant, authentication, authorization, or internet-facing security problems.
Do not plan defence in depth, capability tokens, admission control, audit chains, consensus panels,
rate limiting, or cost guards. This repository has a standing record of a plugin that reached 14,875
lines for a five-step job by exactly that reasoning. Isolation here is a git worktree plus a merge.
If a proposed control would only matter to a second untrusted user, it does not belong in this plan.

---

## 7. Genuine operator decisions — report before crossing

The run contract stops for scope expansion. Four decisions sit above your authority. **Put them in
the plan as explicit open questions with your recommendation and the cost of each branch; do not
resolve them yourself, and do not let the worker resolve them either.**

**Decision 1 — `SEC-02`: extend the composer guard to `review-result` and `land`?**
`dispatch_review_routing` at `orchestrate.py:1387` and `_resubmit_one` at `orchestrate.py:1492` both
write a full prompt into a pane through `say()` with no composer inspection at any ownership, and
both are reached from registered subcommands. The reviewer notes the exposure window is worse than
the launch window the guard does cover: a review resubmit lands minutes to hours after the session
was created, which is exactly when an operator has typed something and left it unsent. The finding is
marked `pre_existing: true` — the guard was only ever wired into `launch()`. Fixing it is new
capability, not repair of a regression. Coordinator's read: it is the single highest-value item in
the artifact, and it is also unambiguously scope expansion.

**Decision 2 — `DOCC-04`: edit two orchestrate documents this branch does not own?**
Verified by the coordinator: `origin/main` carries
`plugins/orchestrate/README.md:96` ("floors are declared for the installer and nothing verifies
them") and `plugins/orchestrate/commands/orchestrate.md:504` ("a declaration the installer reads and
no code checks"). This branch makes the agent-launcher floor runtime-enforced and **touches neither
file**, and a three-way merge produces **no conflict** in either — so both false sentences survive
the merge silently while the branch's `SKILL.md` asserts the opposite. Fixing it widens the diff into
files outside the seven children. Coordinator's read: caused by this branch's own behaviour change,
therefore in scope on the merits, but it is the operator's call.

**Decision 3 — release-surface reconciliation.** Verified: the branch declares orchestrate **4.0.2**
with a single dependency `agent-launcher >=1.2.1`. `origin/main` declares **4.0.1** with **three**
dependencies: `agent-launcher >=1.0.0`, `mission-control >=2.15.1`, `saga >=0.151.0`. Merging as-is
**drops two declared dependencies**. The orchestrate `CHANGELOG.md` also jumps 3.2.0 to 4.0.2 with no
entry for 4.0.0 or 4.0.1 and no explanation of the major bump. The manifest and the CHANGELOG are two
of the real merge conflicts, so a human will see them — but which version number and which dependency
set ships is an operator call, not a merge-resolution reflex.

**Decision 4 — merge `origin/main` before or after the repairs?** The branch is 42 commits behind.
Every mutation and probe in the artifact was measured against `dd3593ab`, which predates main's
orchestrate 4.0.1 release. Repairing first keeps the proofs reproducible against the revision they
were measured on; merging first means the repairs are built on what will actually ship. The real
merge conflict set is small and known: `plugins/orchestrate/.claude-plugin/plugin.json` and
`plugins/orchestrate/CHANGELOG.md`. Files main changed that this branch also owns:
`.claude-plugin/marketplace.json`, both engineering-journal files,
`plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py` and its `SKILL.md`. Coordinator's
read: repair first against the frozen revision so the proofs hold, then merge main as its own commit
before the gate and the final review — but say so in the plan and let the operator confirm.

---

## 8. Custody — hard boundaries

- **Touch nothing belonging to issue 912 or any other run.** Do not inspect, interrupt, read, or
  terminate its processes, gate runs, log directories, worktrees, sessions, or branches. A gate
  process in another checkout was killed by accident earlier in this run; that must not recur.
  Anything named `912`, `918`, `919`, or living in workspace `wEW`, `wEX`, `wF8` or `wF9` is off
  limits. Your workspace is `wEV` and your checkout is `orch-claude-plugins-907`.
- Run the gate only with a `GATE_LOG_DIR` unique to this phase, backgrounded per this repository's
  `CLAUDE.md`. Before starting one, check `pgrep -fl "scripts/gate.sh"` and kill **only** a stale pid
  you can prove is yours. Never `pkill -f "scripts/gate.sh"` — it kills every gate on this machine,
  including other checkouts'.
- Do not push, open a pull request, merge, close any issue, or mutate lifecycle state during the
  planning phase.
- This handoff file is uncommitted in the worktree. You may commit it with your plan; you may not
  amend any existing commit.

---

## 9. Phase topology and the stop condition

```
cp907-planner  -->  cp907-plan-review  -->  cp907-planner (repairs)  -->  cp907-worker  -->  gate  -->  cp907-code-review  -->  STOP
```

1. **Plan.** You write one decision-complete Saga implementation plan with the 91-row ledger. You do
   not implement.
2. **Plan review.** The coordinator dispatches your exact plan to `cp907-plan-review` for the normal
   Saga Plan Document Review. You repair the plan and it is re-reviewed until that review returns
   ready. This loop is bounded by the plan review's own contract, not by improvisation.
3. **Implement.** Only after the plan is accepted does the coordinator dispatch it to `cp907-worker`.
4. **Gate.** The full 25-step repository gate, backgrounded, green, against the repaired revision.
5. **Terminal Code Review.** **Exactly one** fresh Saga Code Review through `cp907-code-review`,
   bound to the repaired revision, with the seven approved lenses and no more than three concurrent.
6. **Stop.** If that review accepts, the run continues to the already-authorized integration, merged
   gate, release update, installed-state verification, board synchronization, closure and cleanup.
   **If it does not accept, the typed result is surfaced to the operator and the run stops there.**
   There is no further repair-review loop. Do not plan one, do not propose one, and do not let a unit
   assume one exists.

Three numbered cycles are closed and capped. Nothing in this phase reopens them.

---

## 10. Session roster, verified live at handoff

| Role | Herdr name | Pane | Kind | Model / effort |
|---|---|---|---|---|
| Planner | `cp907-planner` | `wEV:pG` | claude | **Fable 5.1 / xhigh**, bypass permissions |
| Plan review | `cp907-plan-review` | `wEV:p4` | cursor | **Cursor Grok 4.6 Extra High Fast** |
| Worker | `cp907-worker` | `wEV:pM` | claude | **GLM 5.3 / xhigh**, bypass permissions |
| Code review | `cp907-code-review` | `wEV:p6` | claude | **Opus 5 / high**, bypass permissions |

All four are in workspace `wEV`, all four sit in the `orch-claude-plugins-907` checkout on
`work/cp907-launcher-session-contract`, and all four were idle with an empty composer at handoff.

The operator set the planner and worker routes directly. **Those routes are authoritative.** Do not
propose replacing, restarting, re-authenticating, or re-tiering any of them, and do not describe a
model the operator chose as drift. If a session genuinely fails, report it and stop — do not
substitute a vendor, model, account or session.

On proportionality, for the record only: the repair work in section 4 is dense adjudication against
executed evidence, and the coordinator would have recommended a top-tier reasoning model at high or
extra-high effort for the worker. The operator's GLM 5.3 at xhigh is a top-tier extra-high route and
is consistent with that. No change is being requested.

---

## 11. Coordinator's note on the one thing to change

Both failed repair rounds committed before anything independent had tried to break them, and the one
fix that was mutation-tested before commit — positional last-block selection in the composer — is
the one that survived review. **The verification order is the thing to change.** Build the proof
first, watch it fail, then edit until it passes, and keep the counter-case that would catch the
mirror-image mistake. Everything else in this handoff is downstream of that.
