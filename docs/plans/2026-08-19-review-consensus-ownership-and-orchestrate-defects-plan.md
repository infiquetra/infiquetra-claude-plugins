# Review consensus ownership, and the Orchestrate defects found beside it

**Status:** ready for review · **Date:** 2026-08-19 · **Scope:** four surfaces —
`plugins/saga/skills/code-review/`, `plugins/saga/skills/work/`, `plugins/team-execution/`,
`plugins/orchestrate/`

This plan is the durable record of two read-only audits run on 2026-08-19 and combined by operator
instruction. Neither audit changed a file. It exists so that implementation can be authorized and
resumed **without the originating session transcript**.

The two audits converge on one root cause: **every surface in the review path states a review policy
that nothing enforces, and Orchestrate was left improvising the gap by hand.**

## What is deliberately not in this plan

The custody question for the stranded Home Lab branch `orch/orch-2026-08-19-a-parity-contract` — ten
commits, on no remote, with a worktree still checked out under a temporary directory — belongs to the
`home-lab` repository and is tracked separately. Nothing in this plan depends on it.

## Evidence base, and how to re-verify it

Two sources, both re-readable:

1. **A live Orchestrate run**, `orch-2026-08-19-a` in the `home-lab` repository, driven by Claude
   session `4107f334-9c41-47a9-9677-b4dfee3755a3` on 2026-08-19 using orchestrate **1.17.0**. Its
   record survives at `home-lab/.orchestrate/run.json` and `plan.json`. Findings below were
   reproduced against orchestrate **1.18.0** source in this repository, so they are current unless
   marked otherwise.
2. **Direct source inspection** of the four surfaces in this repository. Every claim below cites a
   file and line so it can be re-checked without re-running anything.

The consensus audit's own pytest collection was blocked by its read-only environment. Its behavioural
claims were re-verified here by source inspection; the three additions marked below were found during
that re-verification and are not in the original addendum.

---

## Part 1 — The settled ownership ruling

These are operator rulings. They are settled and are not to be re-litigated during implementation.

**Saga Code Review owns** the canonical lens roster, the dimensions, the derived per-lens scores, the
acceptance rule, fix consolidation, rerunning only failing lenses, the three-cycle cap, best-available
termination, and the final score and residual report.

**The acceptance rule** is: overall at least **9.0**, with **no applicable dimension below 7.0**.

**Every selected lens must supply at least one applicable dimension score.** Code Review derives the
arithmetic-mean overall from the dimensions, or rejects a reported overall that contradicts them.

**After the third unsuccessful cycle**, proceed with the best available revision and clearly report
every final score and every unresolved fix. **This is not a human-halt condition.**

**Independent gates stay independent.** Scanner, test, deployment, casualty and operational-safety
gates remain separately authoritative and are never folded into the score.

**Separation of concerns:**

| Surface | Owns | Must not |
|---|---|---|
| Code Review | Review policy and state. Read-only. | Mutate code |
| Orchestrate | Invoking or resuming Code Review; persisting its structured result; mapping fix requests to responsible existing Work workers; landing the updated revision; returning it to Code Review | Interpret review policy; define lenses or scoring |
| Work | The only mutator | Keep its own review gate |
| Team Execution | Transport, settlement, liveness, advisory seats, scanners, worker coordination | Maintain a parallel roster or parallel scoring policy |

**The archived Orchestrate consensus panel and review loop are not restored.**

**Priority and confidence remain finding metadata**, never a second acceptance gate. **Accepted lenses
are not rerun** but retain the revision they reviewed.

---

## Part 2 — The canonical thirteen-lens roster

One versioned, machine-readable roster under Code Review. Team Execution consumes it rather than
maintaining parallel policy. The union preserves both current surfaces:
`plugins/saga/skills/code-review/references/lens-catalog.md` (11 lenses, judgment-selected from the
diff) and `plugins/team-execution/skills/team-execution/references/reviewer-registry.md` (10
reviewers, keyword-selected from the plan).

| Lens | Trigger | Consolidates |
|---|---|---|
| `correctness` | always-on | Code Review only today |
| `security` | always-on | `security-reviewer` |
| `testing` | always-on | `testing-reviewer` |
| `architecture-maintainability` | always-on | `architecture-reviewer` + `code-quality-reviewer` + maintainability/conventions |
| `deployment-infrastructure` | conditional | `infra-reviewer` + deploy/migration-verification |
| `reliability` | conditional | Code Review only today |
| `performance` | conditional | Code Review only today |
| `api-contract` | conditional | `api-reviewer` |
| `adversarial` | conditional | `devils-advocate-reviewer` + red-team |
| `privacy` | conditional | `privacy-reviewer` |
| `documentation-clarity` | conditional | `clarity-reviewer` |
| `agent-usability` | conditional | agent-native + `ai-usefulness-reviewer` |
| `previous-comments` | conditional | Code Review only today |

**Two tier changes fall out of the union and must be stated in the change, not discovered during it:**

- `devils-advocate-reviewer` is **always spawned** in Team Execution today and becomes a
  **conditional** lens.
- `testing-reviewer` is **optional** in Team Execution today and becomes an **always-on** lens.

**Team Execution's non-scoring external advisory seat keeps its exclusion** from the consensus
denominator, the 9.0 acceptance and the 7.0 floor. That exclusion is documented at
`reviewer-registry.md` under "External Advisory Seat (Non-Scoring)" and must survive the move
unchanged, or the arithmetic changes silently.

---

## Part 3 — The typed evidence contract

Code Review emits a typed result beside its existing Markdown artifact. Orchestrate persists it
verbatim and does not interpret policy from it.

**Required fields:** selected lens identifiers; attempted lens identifiers; the revision each lens
reviewed; applicable dimensions per lens; the derived overall per lens; verdict; findings; cycle
history; the failing-lens set; consolidated structured fix requests; unresolved fix identifiers; the
best-available revision; a residual summary; and the next action.

**Outcomes** distinguish exactly four states:

| Outcome | Meaning |
|---|---|
| `accepted` | Every selected lens met the acceptance rule |
| `repairs_requested` | At least one lens failed; fix requests are consolidated and a cycle remains |
| `cycle_cap_best_available` | Three cycles used; proceeding with the best available revision and reporting residuals |
| `review_incomplete` | Reviewer delivery could not be established; no cycle consumed and no score fabricated |

**The fix-request half already exists in design and only needs serializing.**
`plugins/saga/skills/code-review/references/findings-schema.md` already carries `autofix_class`
(`safe_auto` / `gated_auto` / `manual` / `advisory`) and `owner` (`review-fixer` /
`downstream-resolver` / `human` / `release`), and describes itself as routing metadata a downstream
fixer reads. It is emitted only as prose today.

---

## Part 4 — Combined defect register (24)

### Orchestrate (11)

| # | Defect | Evidence | Priority |
|---|---|---|---|
| O1 | `land` and `collect` run in the operator's checkout and refuse on a dirty tree | `orchestrate.py` `cmd_land` — `git status --porcelain` refuse, then `git checkout r.branch`; `cmd_collect` carries the same pair. Live refusal on the Home Lab run at 16:14:24Z: `your working tree has uncommitted changes; commit or stash them, then rerun land` | P0 |
| O2 | The run branch is stored by name and never re-verified; predicates degrade to False | `branch_produced_anything` runs `git merge-base <run branch> <unit branch>` and returns False on non-zero exit; `landed_by_merge` fails the same way. `r.branch` is tested for presence in six places and for resolution only at `start`. Reproduced: `check` reports `NO COMMITS` on four units that are ancestors of `origin/main` | P0 |
| O3 | The delivery-failure note is write-only | `unit.note` assigned in seven places, read in one (`if not unit.note:`, a guard). `cmd_status` and `cmd_check` never reference it | P1 |
| O4 | The delivery check fires falsely and overwrites the handover note | `took_the_task` gives 15s then writes the warning; it fired on two Home Lab reviewers that produced 846 and 2010 word reviews. `pane_text` sets a file-handover note that `took_the_task` then clobbers — `.orchestrate/tasks/review-qwen.md` exists while that unit's note records only the false warning | P1 |
| O5 | `cmd_status` breaks on real data and omits what matters | 14-character model column overflows on `gemini-3.7-flash-high` and `qwen3.8-max-preview`; task text printed raw so newlines break the table; no branch, commits, landed or note column | P1 |
| O6 | No end-of-run hygiene; run state left untracked in the driven repository | This repository gitignores `.orchestrate/` and `.saga/`; nothing carries that to the repository being driven. Both sit untracked in `home-lab` | P2 |
| O7 | Hand-authored briefs recorded as session-temporary paths | The Home Lab `fix-grok` unit's permanent task is `Read /private/tmp/claude-501/.../scratchpad/fix-brief.md`. The plugin owns a durable `.orchestrate/tasks/` with a path-containment guard and does not teach its use | P2 |
| O8 | The `orch/<run_id>-*` branch namespace is not reserved | Two codex sessions created `orch/orch-2026-08-19-a-parity-contract` after the run ended. `check` and `adopt` detect and repair this; nothing warns at creation | P3 |
| O9 | Only a Boolean Code Review marker; no review-result state and no loop seam | `Run.reviews_separately()` is a regex over unit task text returning `bool`, passed as `review_elsewhere=`. No review result is persisted anywhere | P1 |
| O10 | Worker sessions are reaped at land time, destroying the session a repair would reuse | `reapable()` keys on DONE plus work landed — which is exactly when a fix request arrives | P1 |
| O11 | README documents six modules the plugin does not ship | The plugin ships `orchestrate.py` and `herdr_events.py`. `README.md` cites `scripts/register.py`, `subscriber.py`, `session_lifecycle.py`, `completion.py`, `mirror.py`, `runner.py` across eight lines — the deleted pre-rewrite architecture | P2 |

### Code Review (5)

| # | Gap | Evidence | Priority |
|---|---|---|---|
| C1 | Gates on Priority 0 and Priority 1; no numeric acceptance rule | Searching the skill for `9.0`, `7.0`, `/10` and `score` returns nothing. Verdict is binary — `SKILL.md:389`, `--verdict "<blocked\|clean>"` | P0 |
| C2 | No per-lens scores, no dimensions, no cycle state, no failing-lens set | Absent from `SKILL.md` and every reference file | P0 |
| C3 | Escalates gated consensus **to** Team Execution — the ruling reverses this | `SKILL.md:250` — "Escalate to `team-execution` … when the review needs **gated** consensus" | P0 |
| C4 | Emits Markdown only; no machine-readable result | `SKILL.md:389` writes `--artifact-file <path-to-composed-review.md>`; `findings-schema.md` describes no serialization | P1 |
| C5 | The consensus panel is deferred in-source as unbuilt | `SKILL.md:90` — "The in-session lens fan-out is governed by the consensus-panel roster, **which is separate work**" | P1 |

### Team Execution (7)

| # | Defect | Evidence | Priority |
|---|---|---|---|
| T1 | Maintains a parallel reviewer registry that diverges from the lens catalog | `references/reviewer-registry.md` (10 reviewers) versus `code-review/references/lens-catalog.md` (11 lenses); three map cleanly, a fourth arguably | P0 |
| T2 | The helper accepts an empty dimension map, disabling the 7.0 floor | `consensus_advisory.py:44` — `dimension_scores: Mapping[str, float] = field(default_factory=dict)`; `:99` — `any(score < 7.0 for score in result.dimension_scores.values())` is False over an empty map; `_validate_result` (`:173-195`) iterates the map and so requires nothing | P0 |
| T3 | Trusts the caller's reported overall | `consensus_advisory.py:100,102` use `result.score` directly; nothing derives it from the dimensions or cross-checks it | P0 |
| T4 | A second terminal stop at `< 5.0` contradicts best-available termination and must be **removed**, not implemented | `references/consensus-protocol.md:283` — "A score < 5.0 on any security or auth dimension is treated as a **blocking stop** — no completion until that dimension reaches >= 7.0". See the note below | P0 |
| T5 | Cycle-three termination is stated five ways, two of them contradictory | `review-criteria.md:8` "proceed with the best available version"; `consensus-protocol.md:216` "Flag to user"; `SKILL.md:263,490` and `README.md:115` and `validator-execution-order.md:30` "escalate". `andon-cord.md:57` miscites `consensus-protocol.md` as best-available-proceed when that file says flag-to-user | P1 |
| T6 | `SKILL.md:489` halts to the operator on non-consensus, contradicting best-available | "Reviewer non-consensus blocks validators unless the user explicitly overrides" | P1 |
| T7 | A test fixture encodes the empty-dimension defect as valid input | `tests/test_team_execution_settlement_adapter.py:165` — `{"reviewer": "security-reviewer", "score": 9, "dimension_scores": {}, "findings": []}` | P1 |

### Work (1)

| # | Defect | Evidence | Priority |
|---|---|---|---|
| W1 | Independently gates hard on Priority 0 and Priority 1 | `work/SKILL.md:3,57,766,855` — "gates hard on P0/P1 and stale reviews" | P1 |

**Note on the `< 5.0` rule, and why T4 removes rather than implements it.** The rule at
`consensus-protocol.md:268-284` has two halves and they must be separated.

Its *routing* half — raise the priority of the fix request, route it to the responsible worker, and
make the residual prominent — is **repair-routing severity**, it is legitimate, and it survives as
finding metadata. It does **not** override the three-cycle outcome.

Its *terminal* half — "no completion until that dimension reaches >= 7.0" — is a **second terminal
stop and must be deleted.** Two reasons, and the first alone is sufficient. Arithmetically it adds
nothing: 4.9 is already below 7.0, so the settled floor already refuses acceptance, and the rule's own
release condition is that same 7.0. Its only distinct effect is to forbid termination, which directly
contradicts the settled rule that the third unsuccessful cycle proceeds with the best available
revision and reports residuals. It is a review-dimension threshold inside the review loop, **not** an
independent scanner, test, deployment, casualty or operational-safety gate, so it does not qualify for
the carve-out those gates hold.

The same section's "Flag to user (do not wait for cycle to complete)" and "pause other reviewers" are
resolved the same way: a notification and a routing priority are fine; neither may halt the loop or
gate its outcome. Item 12 reconciles that prose.

**The Priority column in the four tables above is this backlog's triage order.** It is not Code
Review's finding severity and it is not an acceptance gate. Nothing in this plan grants Priority 0 or
Priority 1 a gating role — item 11 removes the last one that had it.

### Why this matters, from the run that exposed it

On the Home Lab run, one reviewer returned **zero findings on a 15,400-line diff** while another
returned **four**, every one independently confirmed real. Nothing could adjudicate that split: no
score, no dimension floor, no quorum. The orchestrating session read the source itself, invented a
triage that proposed fixing three of the four findings, and was corrected by the operator — *"go
ahead, but lets fix all 4 not just 1 through 3"*. The repaired code was then never re-reviewed,
because no loop exists. That sequence is the argument for this whole plan.

---

## Part 5 — Implementation phases

```
A (independent) --> ship first
B (foundation) --> C (consumers) --> D (orchestrate loop) --> E (tests)
F (independent) --> any time
```

### The twenty implementation items, in dependency order

| # | Item | Phase | Surface | Closes |
|---|---|---|---|---|
| 1 | Land and collect in a throwaway worktree | A | orchestrate | O1 |
| 2 | Resolve the run branch once; fail loudly when gone | A | orchestrate | O2 |
| 3 | Versioned machine-readable thirteen-lens roster | B | saga | C5, T1 |
| 4 | Dimensions, derived overall, contradiction rejection, thresholds | B | saga | C1, C2 |
| 5 | Cycle state, selective rerun, three-cycle cap, best-available | B | saga | C2, C3 |
| 6 | Typed result emission beside the Markdown artifact | B | saga | C4 |
| 7 | Team Execution consumes the roster; parallel registry deleted | C | team-execution | T1 |
| 8 | Helper requires dimensions and derives the overall; the `< 5.0` terminal stop is deleted from the prose | C | team-execution | T2, T3, T4 |
| 9 | Orchestrate persists the result, maps fixes, lands, resubmits | D | orchestrate | O9 |
| 10 | Stop reaping a worker a pending fix request still needs | D | orchestrate | O10 |
| 11 | Work drops its own gate and reads Code Review's acceptance | C | saga | W1 |
| 12 | Reconcile the cycle-three prose to one statement | C | team-execution | T5, T6 |
| 13 | Surface the delivery note in status and check | A | orchestrate | O3 |
| 14 | Append rather than overwrite the note; clear it on commits | A | orchestrate | O4 |
| 15 | Size status columns from data; add commits and landed | A | orchestrate | O5 |
| 16 | Behavioural test matrix, including the real-repository flow | E | all four | T7 |
| 17 | Rewrite the Orchestrate README to the shipped architecture | F | orchestrate | O11 |
| 18 | Write `.orchestrate/` to `.git/info/exclude` at start | F | orchestrate | O6 |
| 19 | Point hand-authored briefs at `.orchestrate/tasks/` | F | orchestrate | O7 |
| 20 | Warn on an unrecorded branch in the run namespace | F | orchestrate | O8 |

Every one of the 24 defects is closed by at least one item.

### Phase A — Orchestrate run integrity · depends on nothing · release surface: orchestrate

Items O1, O2, O3, O4, O5.

1. `land` and `collect` merge inside a throwaway worktree created on the run branch, then remove it.
   No `git checkout` of the operator's tree, no dirty-tree refusal.
2. Resolve `r.branch` once at load. When it does not resolve, say so and stop, rather than letting
   each predicate answer False independently. `resolve_ref` already exists and is used elsewhere.
3. Print the note in `status`; add a `check` finding for a unit whose note records a delivery failure.
4. Append to the note rather than replacing it (`read_unit` already has the
   `f"{unit.note}; {note}"` idiom); clear the delivery warning in `settle` once the unit has commits.
5. Size the status columns from the data, collapse whitespace in the task excerpt, add a
   commits-and-landed column.

**Acceptance:** a land succeeds against a repository with uncommitted tracked changes and leaves those
changes untouched; with the run branch renamed, every command either works or names the missing
branch, and none reports `NO COMMITS` for a unit that has commits; `status` renders one row per unit
with no column overflow on a 21-character model name.

### Phase B — The canonical contract in Code Review · depends on decisions A and D · release surface: saga

Items C1–C5.

1. The versioned machine-readable thirteen-lens roster, with a stable identifier per lens.
2. Dimensions per lens, the derived arithmetic-mean overall, rejection of a contradictory reported
   overall, and the exact thresholds.
3. The typed result of Part 3, emitted beside the existing Markdown artifact.
4. Cycle state, failing-lens-only rerun, the three-cycle cap, and best-available termination.

**Acceptance:** a lens with no applicable dimension is refused; a reported overall that disagrees with
the mean of its dimensions is refused; 9.0 accepts and 8.9 does not; 7.0 accepts and 6.9 blocks; a
fourth cycle can never be attempted; a dimension at 4.9 terminates in `cycle_cap_best_available` after
the third cycle exactly as any other failing dimension does, with **no** additional stop; and the
typed result carries all fourteen required fields and exactly one of the four outcomes.

### Phase C — Consumers align · depends on B · release surfaces: team-execution, saga

Items T1–T7, W1.

1. Team Execution consumes the roster and transition engine; its parallel registry is deleted.
2. `consensus_advisory.py` requires at least one dimension per gated reviewer and derives the
   overall. It gains **no** new threshold: the `< 5.0` terminal stop is deleted from
   `consensus-protocol.md`, and its routing half survives only as fix-request priority. The helper's
   current silence on 5.0 is correct and stays.
3. Work drops its own Priority 0/1 gate and reads Code Review's acceptance.
4. The five cycle-three statements are reconciled to one, and `andon-cord.md`'s miscitation corrected.

**Acceptance:** exactly one roster exists in the repository; the helper rejects an empty dimension map
and a contradictory overall; a search for cycle-cap termination returns one consistent statement.

### Phase D — The Orchestrate review loop · depends on B, and C for consistency · release surface: orchestrate

Items O9, O10.

1. Orchestrate persists the typed result, maps each fix request to a responsible existing Work worker
   by `owner` and touched paths, lands the updated revision, and returns it to Code Review.
2. Reaping no longer destroys a worker that a pending fix request may still need.

**Acceptance:** a run that receives `repairs_requested` dispatches repairs to the existing worker
where one matches and to a replacement where none does, lands, and resubmits; no policy decision is
made in Orchestrate; a worker with an outstanding fix request is not reaped.

### Phase E — Behavioural tests · depends on B, C, D · spans all four surfaces

Roster parity between Code Review and Team Execution; required dimensions; derived-score validation;
the exact thresholds at their boundaries; selective reruns preserving accepted lenses' reviewed
revisions; no fourth cycle; cycle-cap residuals; independent safety gates unaffected by the score;
worker reuse and worker replacement; state reload; and **one end-to-end flow in a real temporary Git
repository**.

The end-to-end test is load-bearing. This repository's standing lesson is that a green gate proves
nothing when a fixture stands in for the component under test, and defect T7 is that lesson
recurring — a fixture that encodes the bug as valid input. That fixture must be **inverted**, not
extended.

### Phase F — Documentation and hygiene · depends on nothing · release surface: orchestrate

Items O11, O6, O7, O8. Rewrite the Orchestrate README to the shipped two-module architecture; write
`.orchestrate/` to `.git/info/exclude` at `start`; point hand-authored briefs at `.orchestrate/tasks/`;
warn when an unrecorded branch appears in the run namespace.

### Release shape

Phase A ships alone as an Orchestrate release. **Phases B through E are the single coordinated
cross-plugin change**, with `plugins/<plugin>/.claude-plugin/plugin.json`,
`.claude-plugin/marketplace.json`, every touched `CHANGELOG.md` and the version drift guards updated
in the same pull request. Phase F may ride either.

---

## Part 6 — Remaining choices

Implementation of Phase B is blocked until choices A and D are answered. Phase A is blocked only on F.

| # | Choice | Recommendation | Reason |
|---|---|---|---|
| A | Approve the thirteen-lens union | **Approve** | Preserves both surfaces; closes the four lenses with no reviewer and the three reviewers with no lens |
| B | Best available is the latest successfully integrated revision reviewed in cycle three | **Approve** | Ranking revisions would be new policy invented at the worst moment |
| C | Exhausted reviewer-delivery retries are `review_incomplete`, consuming no cycle and fabricating no score | **Approve** | Two Home Lab units were flagged as never started and had produced full reviews; a fabricated score there would have been worse than an honest "incomplete" |
| D | Lens selection trigger: judgment from the diff, or keyword match against the plan | **Judgment from the diff** | Keyword matching a plan document cannot see what the code actually touched |
| E | Where cross-vendor review diversity lives, now that the Orchestrate panel is not restored | **Code Review's external-reviewer seat**, via its existing managed-session runner | Otherwise multi-vendor review disappears; the 0-versus-4 finding split is the argument for keeping it |
| F | Whether `land` and `collect` may merge in a throwaway worktree | **Yes** | It is what the operator's session did by hand; it never touches the operator's tree, and the refusal buys nothing |
| G | Whether `settle` should refuse `done` for a unit with a delivery note and no commits | **No** | It would have been wrong on this run — both flagged units were working normally. Surface the note instead (item O3) |

---

## Part 7 — Resuming without the originating transcript

Everything needed is in this file plus the cited lines. To re-establish the two headline
reproductions:

- **O1** — run `land` in any repository with an uncommitted tracked change and read the refusal.
- **O2** — rename a run branch, then run `check`; every unit reports `NO COMMITS` regardless of its
  actual commits.

The Home Lab record at `home-lab/.orchestrate/run.json` is the primary artefact for the run-derived
findings and has not been modified by either audit. The originating Claude session transcript is
`4107f334-9c41-47a9-9677-b4dfee3755a3`, retained under the `home-lab` project directory, but this plan
is written so that reading it is not required.
