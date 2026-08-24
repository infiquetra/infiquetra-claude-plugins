# Doc review — defects-claude-plugins unattended-run plan (issue #787)

The plan is the S1 HOW for the twenty-leaf #787 run. It is not ready to drive unattended implementation: one unit would reopen a shipped fail-loud path, and several units invent machinery the tree already has.

| field | value |
| --- | --- |
| target path | `docs/plans/2026-08-24-defects-claude-plugins-run-plan.md` |
| reviewed revision | plan commit `a1a50fef` (`docs(plans): defects-claude-plugins run plan for #787 — 20 leaves, 4 lanes`); worktree `orch/orch-2026-08-24-787-docreview-grok` at `6f85f7eb`; citations checked against `origin/main` `818fd684` after `git fetch` |
| blocked status | **yes** — unresolved P0 and P1 findings. S3 must validate each finding against the tree and repair only the genuine ones. No second broad document review. |
| applied fixes | none. The #787 contract and this session's instruction forbid repairing the plan here. |
| review artifact path | `docs/reviews/2026-08-24-defects-run-plan-doc-review.md` |
| linked issue | infiquetra/infiquetra-claude-plugins#787 (authoritative contract, including operating-context and proportionality) |
| linked plan | `docs/plans/2026-08-24-defects-claude-plugins-run-plan.md` |
| override rationale | n/a |

## Readiness summary

The plan honors #787's shape: twenty units, four serialized lanes, no vendor binding, per-unit smallest-fix / reuse / new-parts / rejected-alternative records, and the #692 park path.

It is not implementation-ready. Several HOW sections name the wrong function, the wrong line, or a detector that already exists, so an unattended agent following the plan literally will add lock/probe/doctor/RuntimeError machinery the acceptance criteria do not need.

Security and reliability findings below name an in-scope trust boundary or failure mode and a concrete consequence. Hypothetical scale is not used.

## Remaining findings by priority

| id | severity | status | claim |
| --- | --- | --- | --- |
| F1 | P0 | open | U20 R4 would reopen a shipped fail-loud `board_move` path |
| F2 | P1 | open | U20 R3 / KTD7 does not make CI print the live-leg skip |
| F3 | P1 | open | U20 tells the agent to find a generator that does not produce the parity script |
| F4 | P1 | open | U8's TTL floor of 300 fails the 10-minute acceptance criterion |
| F5 | P1 | open | U1 invents a transcript-delta probe and skips `took_the_task` |
| F6 | P1 | open | U2 cites `cmd_land` instead of `produced_anything`, which settle already calls |
| F7 | P1 | open | U3 invents status/doctor detection; `cmd_check` already reports unrecorded branches |
| F8 | P1 | open | KTD1's "filter the top-level return by attaching unit" is ill-defined |
| F9 | P1 | open | U19/U20 verification paths contradict the leaves' close-out commands |
| F10 | P2 | open | U3/U4 stop-condition tables are deferred to unwritten task briefs |
| F11 | P2 | open | U18 item 5 writes a saga plugin file from lane C |
| F12 | P2 | open | U6 would add a second Waiting section; U2 cites that section as settlement |
| F13 | P2 | open | U1 does not pin the retry count the docs AC requires |
| F14 | P2 | open | U16 overstates that a lock is required by the grep AC |
| F15 | P3 | open | U16 leaves the test location as an open choice |
| F16 | P3 | open | U10 leaves pre-gate vs lazy factory as an open choice |
| F17 | P3 | open | #691 mutation-proof wording still says "reset" |

## Rubric review (issue phase, applied to the plan as the issue-derived S1 artifact)

Core rubrics all applied. Extra rubrics all applied: the plan is a code-change campaign in a non-trivial repo, twenty units, and a named DAG.

| rubric | score | note |
| --- | --- | --- |
| acceptance_criteria_clarity | 7 | Load-bearing ACs map unit-by-unit, but U8's formula, U20 R3/R4, and U1's probe are not pass/fail from the plan text alone. |
| devils_advocate_issue | 6 | Several units bundle new detectors, locks, or API changes on top of helpers that already exist. Not unbounded; REVISE, not BLOCK at rubric level. The P0/P1 readiness findings are the gate. |
| spec_fidelity | 8 | Descent from #787 is named. Path corrections vs the inventory table are fidelity improvements. R4 and the parity-script generator are drift against the live tree. |
| context_completeness | 7 | Files and many line numbers are right at `818fd684`. The wrong ones (U20 R4, U2 `cmd_land`, U3 doctor, U1 probe, U7 top-level filter) are exactly the ones that would make an agent invent a path. |
| issue_sizing | 9 | One unit per leaf, one PR per unit, matching the contract. |
| prerequisite_mapping | 8 | Lane DAG matches #787. U18's saga-file write is the missed collision. |

Rubric findings are not reclassified as readiness findings. The F-series below are the readiness-skeptic pass, including proportionality.

## Decisions taken without asking

This session is S2 (the single Grok 4.6 extra-high document review). No question was left open.

1. **Do not repair the plan.** The contract says S3 validates and repairs. This file is the S2 ledger input.
2. **No engine-offer prompt and no second reviewer.** #787 forbids a second broad document review. Interactive offer would halt an unattended run.
3. **U20 R4 is already done.** Treat `test_board_move_exit.py` as the current contract; do not raise `RuntimeError`.
4. **U20 R3:** the bare CI invocation (no `--live`) must print SKIP-with-reason. Do not edit `ci.yml` from lane D. Do not hunt `infiquetra-sdlc`.
5. **U8 floor:** at least 600 seconds so a one-unit spec still meets the 10-minute AC, unless the unit drops that AC after the consumer sweep.
6. **U1:** reuse `took_the_task`; do not add a transcript-delta probe.
7. **U7:** filter `__halt` only; keep the top-level `__advisories` list keyed by `unit`.
8. **U18 both-ends docs:** prefer documenting the coupling in the canary test (quoting the saga path). If the leaf's "both ends" is read strictly, list the one-line saga comment as an explicit collision exception rather than a silent lane-C write.
9. **Issue-phase rubrics** were applied to this plan because it is the issue-derived S1 artifact. There is no plan-phase rubric in the engine.

---

### F1 — U20 R4 would reopen a shipped fail-loud path

**Severity:** P0

**Exact claim.** U20 tells the implementer that `board_move` soft-continues on an unresolvable Status option at `sdlc_manager.py:1259-1266` and should be changed to match `flow_set_field`'s `RuntimeError` at `:2387-2393`. At `818fd684` those line numbers are not that defect, and the fail-loud behavior already ships.

**Evidence.**

- Plan U20 R4 bullet (`docs/plans/2026-08-24-defects-claude-plugins-run-plan.md`, U20 "Smallest viable fix").
- `plugins/mission-control/scripts/sdlc_manager.py:1259-1266` is item-not-found, already `failed = True`.
- Unresolvable Status option is `:1293-1301`, also `failed = True; continue`.
- `:2387-2393` is `flow_set_field`'s signature, not a raise. The option `RuntimeError` is `_resolve_field_option` at `:2425-2430`.
- CLI already maps a false return to `SystemExit(1)` at `:6040-6047`.
- `plugins/mission-control/tests/test_board_move_exit.py` (`test_unavailable_status_returns_false_lists_options_and_does_not_mutate`, `test_cli_exits_one_only_after_board_move_reports_failure`) pins this as issue #609.

**In-scope failure mode.** Board writes to GitHub Projects. A wrong Status option must not report success. That failure already exits 1. Raising `RuntimeError` from `board_move` would break the bool-return API those tests pin, so callers that handle `False` would see an uncaught exception instead of a mapped exit.

**Suggested repair.** First step of U20: re-run the #609 tests. If they still pass, record R4 as already satisfied in the PR and the #584 close-out. Do not change `board_move` to raise. Fix the line citations if any residual remains.

---

### F2 — U20 R3 does not make CI print the live-leg skip

**Severity:** P1

**Exact claim.** KTD7 says the parity script will self-report `SKIP: unauthenticated (<reason>)` when the live leg cannot run, so CI shows the skip without touching `ci.yml`. The script already prints that skip — but only when `--live` is passed. CI never passes `--live`, so the live leg stays silently absent.

**Evidence.**

- Plan KTD7 and U20 R3 residual.
- #584 curation AC: "CI either runs the parity `--live` leg with an explicit printed SKIP-with-reason when unauthenticated (never silently absent), or `ci.yml` carries an inline decision comment saying why not."
- `.github/workflows/ci.yml:40` and `scripts/gate.sh:119` invoke `check_issue_contract_parity.py` with no `--live`.
- `plugins/mission-control/config/generated/check_issue_contract_parity.py:184-201` — skip print is inside `if args.live`.

**Suggested repair.** On the default (no `--live`) path, print `SKIPPED live parity leg: <reason>` so the existing CI step's log satisfies the AC. Do not add `--live` to `ci.yml` from lane D (U18 is the sole writer). The AC's other branch (inline `ci.yml` comment) belongs to U18 if U20 cannot change the script's default path.

---

### F3 — U20's "locate the generator" step has no in-repo producer

**Severity:** P1

**Exact claim.** U20 says `check_issue_contract_parity.py` sits under `config/generated/` and the unit must locate the generator and change the source, never only the generated artifact. That instruction sends the agent into `infiquetra-sdlc` (out of this run's owned surfaces) for a file this repo already hand-edits.

**Evidence.**

- Plan KTD7 and U20 owned paths.
- The script's own docstring: the *data* modules (`issue_contract_data.py`, `issue_contract_shim.py`) are vendored from `infiquetra-sdlc` with `.sha256` sidecars. The parity *gate* is the checker, not one of those two artifacts.
- `plugins/mission-control/config/generated/` contains `.sha256` files only for the two data modules. The parity script has none.
- This repo already added the `--live` leg to that script (mission-control CHANGELOG: "Add a third, `--live`-gated reconciliation leg").

**Suggested repair.** Edit `plugins/mission-control/config/generated/check_issue_contract_parity.py` in this repo. Do not open `infiquetra-sdlc`. Do not invent a generator.

---

### F4 — U8's TTL floor of 300 fails the 10-minute AC

**Severity:** P1

**Exact claim.** KTD2 / U8 derive `execution_ttl_seconds` from run scale "with a floor no lower than the current 300". Leaf #694 AC1 requires the lease still held at the 10-minute mark, proven by advancing time past 300 seconds. A one-unit spec at floor 300 expires at five minutes and fails that AC.

**Evidence.**

- Plan KTD2 and U8 Tests / AC mapping.
- #694 AC: "A workflow lease minted for a run of arbitrary length is still held at the 10-minute mark, proven by a test that advances time past 300 seconds."
- `execution_spec.py:3649` is the current literal 300 — the value the defect calls too short.
- The per-unit allowance is unspecified, so the implementer can pick 300 × unit count and ship a still-broken one-unit TTL.

**In-scope failure mode.** Post-#677 the payload is emit-time only. If anything still reads `execution_ttl_seconds` as a hold duration, a 300-second floor leaves long runs unguarded after five minutes — the original #686 32.2-minute incident. If nothing reads it, the 10-minute test is theater unless the formula actually exceeds 600.

**Suggested repair.** Pin the formula. Floor at least 600 seconds (or 10 minutes plus a named margin) so a one-unit spec meets AC1. If the consumer sweep finds zero readers, drop AC1 explicitly (same move the plan already allows for the teardown criterion) instead of deriving a dead 300.

---

### F5 — U1 invents a transcript-delta probe and skips `took_the_task`

**Severity:** P1

**Exact claim.** U1 adds "one delivery-check helper" that confirms acceptance via "pane transcript/consumption delta after the send". The helper already exists. The actual bug is that `launch` records the unit as running *before* the check, and a failed check only appends a warning.

**Evidence.**

- Plan U1 "Smallest viable fix" / "New moving parts".
- `orchestrate.py:1419-1433` `took_the_task` — post-send, agent_status not in idle/done/unknown.
- `orchestrate.py:1447-1451` — `unit.status = RUNNING` then `if not took_the_task: append_unit_note(..., DELIVERY_WARNING)`.
- Tests already pin `took_the_task` in `tests/test_orchestrate_task_dispatch.py` and `tests/test_orchestrate_status_and_notes.py`.
- #779 AC needs a named failure state and no silently-tasked unit, not a new Herdr-read surface.

**In-scope failure mode.** First-prompt loss to folder-trust / account-verification dialogs (session b31ec85e / #779). Consequence of the plan as written: a second probe (transcript delta) that the AC's stubbed pane does not require, plus a missed one-line order change that is the silent-tasked bug.

**Suggested repair.** Reuse `took_the_task`. On failure, bounded retry of the send, then set `prompt_undelivered` instead of `RUNNING`. Do not add a transcript/consumption probe unless a named test shows `took_the_task` cannot see the dialog-swallow case (the 2026-08-19 plan records false positives on fast-idle, which is a reason to tune this helper, not to replace it).

---

### F6 — U2 cites `cmd_land` instead of `produced_anything`

**Severity:** P1

**Exact claim.** U2 says to apply `land`'s branch-truth model at settle by consulting `cmd_land` (`orchestrate.py:2974`) before accepting a pane-state verdict. The reusable helper is `produced_anything` at `:1128`, and `cmd_settle` already calls it — only to clear a delivery warning, not to gate the idle→done and gone→failed transitions.

**Evidence.**

- Plan U2 "Smallest viable fix".
- `cmd_settle` at `:2526-2538`: idle+idle → `DONE` with no evidence check; gone+gone → `FAILED` always.
- `produced_anything` at `:1128-1150`; settle uses it at `:2528` only to `clear_delivery_warning`.
- `cmd_check` at `:3653-3680` already reports `NO COMMITS`, `SESSION GONE`, and `LOOKS DONE` using that helper. That is the evidence model #780 wants at settle time.

**Suggested repair.** Gate settle on `produced_anything`: idle without evidence stays running; gone with commits → `done`; gone without → `orphaned`. Cite `:1128` and the `cmd_check` findings, not `cmd_land:2974` (the merge command).

---

### F7 — U3 invents status/doctor detection that `cmd_check` already performs

**Severity:** P1

**Exact claim.** U3 adds "unrecorded-resource detection in status/doctor". There is no `doctor` command. `cmd_check` already prints `UNRECORDED {name} -- branch {branch} is not a unit in this run` via `discover_unrecorded`.

**Evidence.**

- Plan U3 "Smallest viable fix" item (2) and "New moving parts".
- #773 AC: "Status or doctor output identifies coordinator-created worktrees or sessions that match the run but are absent from its record".
- Grep of `plugins/orchestrate/` for `doctor` — no hits.
- `discover_unrecorded` at `orchestrate.py:1633`; `cmd_check` at `:3637-3638`.
- `cmd_adopt` already exists for the AC's "explicit adoption" repair.

**Suggested repair.** Surface `discover_unrecorded` (and the rest of `cmd_check`'s unrecorded findings) from `status`, or name `check` as the AC's "doctor". Do not add a `doctor` command. Do not write a second detector.

---

### F8 — KTD1 would filter the harness-wide return by a unit that does not exist there

**Severity:** P1

**Exact claim.** KTD1 / U7 change both attach sites so each attaches only entries whose `unit` matches "the attaching unit". `__halt` has a unit. The final `return { units, advisory_corrections: __advisories }` does not. Filtering that list to one unit would drop the other units' advisories from the run-level return.

**Evidence.**

- Plan KTD1 and U7.
- `__halt` at `execution_spec.py:781-784` attaches the whole `__advisories` array to the error — this is the real bleed (unit 2's halt carries unit 1's entries).
- `__logAdvisory` already stores `{ unit, round, corrections, dropped }` at `:812`.
- Top-level return at `:3949-3952` is the whole harness. Comment at `:3941-3945` says `units` carries each unit's result and `advisory_corrections` is the non-gating half reaching the driving session.
- #691 AC: "the second unit's returned array has length 1, not 2" — that is the halt/per-unit array, not "the run return contains only unit 2".

**Suggested repair.** Filter only in `__halt` (pass `unitId` in). Leave the top-level `__advisories` as the full keyed list. Pin the test against `error.advisory_corrections` (and/or `result.advisory_corrections.filter(e => e.unit === u2)`), not against a run return that has been stripped to one unit.

---

### F9 — U19/U20 close-out paths do not match the leaves

**Severity:** P1

**Exact claim.** The plan correctly relocates mission-control tests and `check_pagination.py` into the plugin tree, but it never says the leaves' verification commands are superseded. An unattended close-out that runs the leaf blocks will fail even when the work is right.

**Evidence.**

- Plan KTD8, U19 Tests, U20 owned paths.
- #785 AC: `uv run pytest tests/test_sdlc_draft_revision.py -q`. That path is missing on `origin/main`. Mission-control tests live in `plugins/mission-control/tests/` (`pyproject.toml` `testpaths = ["tests", "plugins/*/tests"]`).
- #584 curation AC R2: `scripts/check_pagination.py`. That path is missing. The file is `plugins/mission-control/scripts/check_pagination.py`.
- #787 "Files expected to change" still lists repo-root `scripts/check_pagination.py`. The plan's inventory correction is right; the close-out mapping is not written down.

**Suggested repair.** In U19/U20, state that the leaf verification commands are superseded by the plugin paths, and that close-out uses those paths. Do not add shim files at the stale locations just to satisfy a grep.

---

### F10 — U3/U4 stop conditions live only in a future task brief

**Severity:** P2

**Exact claim.** U3 and U4 say the leaf stop conditions and failure-mode tables are "copied into the unit's task brief verbatim". Those tables are not in the plan. The briefs do not exist yet. #787 says to stop a unit on those leaf conditions.

**Evidence.** Plan U3 last AC-mapping paragraph; U4 last AC-mapping paragraph. #773 and #772 bodies carry the tables. #787 "Review and stop conditions".

**Suggested repair.** Paste the two tables into U3 and U4. Do not rely on a brief the orchestrator has not written.

---

### F11 — U18 item 5 writes a saga file from lane C

**Severity:** P2

**Exact claim.** #588 AC requires the `readonly-verifier` coupling documented at both ends. U18 therefore edits `plugins/saga/agents/readonly-verifier.md` from lane C. #787's stop condition is a cross-lane write to an owned surface. Lane B owns saga release surfaces; the plan calls this comment-only and coordinated by merge serialization, but does not grant an exception.

**Evidence.** Plan U18 item 5 and Owned paths. #588 curation AC checkbox 5. #787 collision list and "Stop the run on: a cross-lane write to an owned surface."

**Suggested repair.** Prefer documenting both ends in `tests/test_wiring_canary.py` (the test names the saga path). If the leaf is read as requiring a comment in the agent file, add that path to the collision list as a permitted one-line exception so the stop condition does not fire.

---

### F12 — U6 would add a second Waiting section; U2 cites that section as settlement

**Severity:** P2

**Exact claim.** SKILL.md already has `## Waiting, and empty dependencies` at line 174. U6 says to add "a Waiting section". U2 tells the agent to update the settlement contract at `SKILL.md:176-181`, which is the wait paragraph, not settlement. The settlement "What this deliberately does not do" paragraph is `:189-193` (U2's second citation, which is correct).

**Evidence.** Plan U2 and U6. `plugins/orchestrate/skills/orchestrate/SKILL.md:174-193`. #783 AC greps `waiting` / `sleep` / `wait` — the heading already matches `waiting`.

**Suggested repair.** U6 extends the existing Waiting section with the three shapes, copy-paste examples, and "never chained sleep". U2 cites only `:189-193` for the settlement non-goals paragraph.

---

### F13 — U1 does not pin the retry count

**Severity:** P2

**Exact claim.** #779 AC3 requires the SKILL to document "the retry-or-fail policy". U1 says "retry a small fixed number of times" and does not name the number. Two implementers will pick different counts; the test will invent one.

**Evidence.** Plan U1 New moving parts / Tests. #779 AC3.

**Suggested repair.** Pin the count (most defensible: 2 retries after the first send, then `prompt_undelivered` — enough for a dialog to clear, not a delivery manager).

---

### F14 — U16 overstates that a lock is required by the grep AC

**Severity:** P2

**Exact claim.** U16 says a docs-only fix cannot satisfy the grep-pinned lock/re-entry criterion. #782 AC3 is `duplicate-run protection *or* an explicit safe re-entry rule`, grepped as `lock|already running|re-entry`. A documented re-entry rule matches the grep without a lock. The lock is a new persistent-state mechanism.

**Evidence.** Plan U16 New moving parts. #782 AC3, Intent ("duplicate-run protection or a stated safe re-entry rule"), Files expected ("duplicate-run guard, *if implemented rather than documented*"), Tests ("If gate.sh gains a lock… otherwise documentation-only").

**In-scope failure mode.** Observed overlapping gate runs after a 600s kill, mutating the same logs. A lock addresses that. A stale lock without re-entry would block every later gate — so *if* a lock is kept, stale-lock re-entry is required. The grep AC itself does not require the lock.

**Suggested repair.** Keep the stable result marker (AC2 requires it). Choose lock *or* documented re-entry; do not claim the grep forces both. If choosing the lock, keep the stale-lock rule (the kill-at-timeout case is why).

---

### F15 — U16 leaves the test location as an open choice

**Severity:** P3

**Exact claim.** U16 says `tests/test_gate_invocation.py` (new) or an in-script self-test, "whichever the lock mechanism makes cheaper; the unit picks one".

**Evidence.** Plan U16 Owned paths / Tests. #782 Tests to add: the same either/or.

**Suggested repair.** If a lock or stable marker lands in `gate.sh`, add `tests/test_gate_invocation.py`. If docs-only re-entry, `Test expectation: none` plus the grep ACs.

---

### F16 — U10 leaves two implementation shapes open

**Severity:** P3

**Exact claim.** U10 allows "a pre-gate check or a lazy writer factory, whichever the existing call shape absorbs with the smaller diff." Both satisfy the AC. The implementer should not spend the unit re-deriving the fork.

**Evidence.** Plan U10 Smallest viable fix. `board_progression.py:532-541` resolves then builds the writer then calls `authorize_and_write`. `reversibility_certificate.authorize_write` (`:292`) needs no mission-control root.

**Suggested repair.** Default to evaluate the certificate first, then resolve the root only on `AUTHORIZED`. That is the smaller diff against the current linear CLI.

---

### F17 — #691 mutation-proof wording still says "reset"

**Severity:** P3

**Exact claim.** #691 AC3 says "Reverting the reset in a scratch copy". U7 correctly implements a filter, not a reset, and its mutation proof says "revert the filter". Close-out against the leaf's "reset" wording can look like a miss.

**Evidence.** Plan U7 Tests / AC mapping. #691 AC3. KTD1.

**Suggested repair.** In the PR body, quote both: leaf said "reset"; the shipped change is the attach-time filter; reverting *that* filter makes the new test fail.

## What was checked and held

These are not findings. They are claims that survived the tree and the leaves.

- Twenty leaves, four lanes, serialize edges, and the #692 park path match #787.
- `backend: inline` and no vendor/pool binding match the contract's dispatch rule.
- Line citations for U7 accumulator tag `:812`, U8 TTL `:3648-3649`, U9 `resolve_available` `:286-300`, U10 eager resolve `:533`, U15 clamp `:60` vs `:110`, U17 `first == "gh"` `:163-166`, U18 bandit `ci.yml:260` and vacuous disjunct `:74`, U19 no `revise` subcommand, U11 `record_cycle` missing docstring with `ReviewFinding` / `evaluate_review_readiness` already documented — all match `818fd684`.
- `lease_broker.py` is absent. #694 curation shapes (a)/(b) are the right fork; choosing (a) with a consumer sweep is allowed.
- U4's interactive picker is required by #772's ACs, not speculative.
- U5's account field and post-launch probe are required by #781; the trust boundary is the operator account / billing pool on this machine.
- U19's multi-fence validator is required by the #785 curation addition (contamination reached created issue bodies).
- Operating-context prose in the plan matches #787. New parts that *are* justified by a current AC were not flagged.

## Residual risk

Citations were checked against `origin/main` `818fd684`, the revision the contract froze. This worktree also contains the plan commit `a1a50fef`. If `origin/main` moves before a unit starts, that unit's freshness rule (fetch and rebase) still applies.

Leaf bodies for #583/#584/#588/#598 were read through their 2026-08-24 curation comments, which the contract says are the executable ACs.

The #787 Saga Code Review contract (per-lens ≥ 9.0, dimension floor 7.0, at most three cycles, `cycle_cap_best_available`) lives on the issue, not in this plan. Review briefs for S4 must be cut from the issue. That is run-level, not a plan-unit HOW gap.

No `/founder-review` lens: this is a defects-run HOW, not a product-scope decision.
