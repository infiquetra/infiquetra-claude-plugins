---
title: Code Review result and repair-lifecycle integrity from issue 908
type: fix
status: active
date: 2026-09-16
origin: docs/plans/2026-09-16-issue-908-review-integrity-finite-test-plan.md
backend: inline
---

# Code Review result and repair-lifecycle integrity from issue 908

Close all twelve nested children of GitHub issue 908 so a typed review result is stored in the right slot, cannot be overwritten by a regressed artifact, cannot serialize as accepted while findings are still active, is visible in `status`, and routes its repairs to a live non-terminal unit under an identifier that cannot collide across lifecycles, then ship Orchestrate and Saga versions ready to pull into Claude Code.

## Problem Frame

Issue 908 groups the defects that share one subject: the typed Code Review result and the repair lifecycle that consumes it. Seven children were the original run (898, 902, 892, 893, 895, 894, 899). Five more (884, 956, 959, 974, 976) were admitted by the operator launch that authorized this plan. All twelve are open on `origin/main` at `a1fc25f80cd19d08859ce8574110ce21aa6d3166`. Orchestrate is 4.4.0; Saga is 0.158.0. Adjacent open parents 909 and 910 also edit `orchestrate.py` and are not in this run.

Two file-disjoint lanes. Saga produces the artifact (`plugins/saga/scripts/review_consensus.py`). Orchestrate stores, displays, and routes it (`plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py`). Neither lane changes the review artifact schema, lens scoring, lens selection, or the consensus protocol.

## Requirements

R1. Assigning a lifecycle to a controller that already has run-global review state migrates or links `review_result`, `review_outcome`, `review_resubmit_pending`, and `operator_fix_requests` into the named slot as copies, not aliases. A conflicting result already in that slot is a named `SystemExit`, not an overwrite. Run-level mirror fields stay. Existing records are not batch-rewritten. (#898)

R2. A minted replacement's `name` and `workspace` identify the lifecycle it serves, not an unrelated template slice, and do not compound `-fix-` segments. Template lineage stays recoverable (note or `serialize`). Execution-config inheritance from the template is unchanged. (#902)

R3. `route_review_result` skips every terminal unit (`failed`, `orphaned`, `account_mismatch`, `parked`) even when Herdr still reports a live pane, and never flips one back to `running`. A request whose only path match is terminal falls through to minting a new worker. Live non-terminal matches are still reused. Finding grouping, owner, and `touched_paths` are unchanged. (#892)

R4. `cmd_review_result` refuses a cycle-regressed artifact and refuses any non-identical ingest into an already-terminal slot (`accepted` or `cycle_cap_best_available`). A byte-identical replay still returns 0 and dispatches nothing. The refusal names the stop and leaves the stored bytes untouched. (#893)

R5. `cmd_status` prints a stored result whose `review_outcome` is unset as recorded-but-unrouted. A free-text `note` that contradicts the typed outcome does not displace that typed outcome; the disagreement is named. The `note` column stays. The persist-then-route sequence in `cmd_review_result` is unchanged. (#895)

R6. An `accepted` result with empty failing lenses and empty unresolved fix identifiers cannot serialize, including after a `to_json`/`from_json` round trip, with any finding still `status=active`. `repairs_requested` and `cycle_cap_best_available` may still carry `active` findings. Finding status vocabulary, lens scoring, lens selection, and the consensus protocol are unchanged. (#894)

R7. Two lifecycles that share owner, autofix class, and finding labels mint different fix identifiers. The same lifecycle re-deriving the same grouped findings across cycles mints the same identifier. The derivation is a pure function of those inputs plus the lifecycle identifier; no clock, counter, or randomness. Finding labels (`F-1`, …) and grouping rules are unchanged. The digest is not lengthened as the fix. No identifier registry is added. Unscoped state keeps today's identity string. (#899)

R8. Landing a unit in lifecycle A does not resubmit a controller in lifecycle B. A controller already `running` on its own frozen target is not resubmitted. A resubmit names that lifecycle's landed-repair revision, not merely the run-branch head. A lifecycle with no landed repairs in this invocation receives no resubmit. A single-lifecycle run keeps today's resubmit-after-own-repairs behaviour. (#884)

R9. In a multi-controller run, a resubmission write failure other than staged input on one controller does not abort the loop for later independent controllers. The skipped controller is named. `StagedInputError` isolation already shipped for issue 907 stays. (#956)

R10. When a review resubmission is owed and unmade, `cmd_land` returns 4, including when a leftover landing path would otherwise return 3, and including when the unmade resubmission is operator-hold. An operator-held resubmission is not exit 0. The documented exit-code table matches the command's return statements. (#959, #974)

R11. Retrying `review-result` after a partial dispatch does not re-prompt a worker that already took its repair. A per-request dispatched marker, not bag-dedup alone, is what makes the skip real. `review_outcome` stays unset until every Work request has dispatched or been replaced. (#976)

R12. Tests drive the shipped functions named in the finite test plan. Each child's negative case fails if its guard is removed.

R13. Orchestrate versions strictly above the 4.4.0 currently on `origin/main`, Saga strictly above 0.158.0, with `plugin.json` / CHANGELOG / `.claude-plugin/marketplace.json` parity per plugin. Children close when the PR's required GitHub checks succeed, or are parked by a ruling recorded on issue 908. Re-read both versions from `origin/main` at bump time.

## Key Technical Decisions

KTD1. Slot migration lives in `Run.review_slot`, which is the documented sole authority. When the named slot is still default-empty and run-global state holds a result, copy the four fields into the named slot. Copy lists; never alias. If two or more scoped controllers would inherit the same run-global result, stop and name the ambiguity rather than copy it into both. If the named slot already holds a different result, stop. Do not clear run-level fields (older Orchestrate still loads them). Do not scan and rewrite records on disk. Rejected: a one-shot migrate command (operators read through `status` and `review-result`, which already call `review_slot`). Rejected: aliasing the named slot to `RUN_SLOT` (the module already forbids aliasing those lists).

KTD2. Replacement identity is lifecycle-first when the controller is scoped. `_replacement_name` stems from the controller's lifecycle (fallback: controller name, then template name for unscoped). Strip an existing `-fix-` suffix from any inherited stem so a repair-of-a-repair does not compound. `workspace` for a scoped mint is a label that names that lifecycle, not `template.workspace`. Lineage is a unit note `minted from {template.name}` plus the existing `serialize=[controller.name]`. Execution config (vendor, model, effort, permission, setup, launch_args, account, role, paths) still copies from the template. Rejected: keeping the template name and only changing workspace (the incident's unit table was the wrong slice). Rejected: a lineage registry.

KTD3. Terminal routing is a status predicate on the reusable set, applied before `_unit_is_live`. Terminal statuses are `failed`, `orphaned`, `account_mismatch`, and `parked`. `done` is not terminal for routing: a finished worker with a live pane is still a legal holder; the incident was a worker retired for cause (`failed`) that still had a pane. After the filter, today's mint fall-through already handles "no reusable match". `dispatch_review_routing` also refuses to set a terminal unit to `running` as belt-and-suspenders. Rejected: treating `done` as terminal (would mint a replacement for every completed worker). Rejected: ignoring liveness and routing only by status.

KTD4. Ingest continuity is a pre-persist check in `cmd_review_result` against the slot already owned by the resolved controller. Parse `cycle_history` length and `outcome` when both the stored and incoming payloads are JSON objects. Terminal stored outcomes are `accepted` and `cycle_cap_best_available`. Any non-identical ingest into a terminal slot is a named `SystemExit`. An incoming `cycle_history` shorter than the stored one is a named `SystemExit` even when the slot is not yet terminal. Byte-identical replay (already implemented) remains the only exception and still requires `review_outcome is not None`. Unparseable stored bytes do not block a well-formed incoming result. Rejected: comparing only `outcome` (the incident was cycle-1 accepted over cycle-3 cap). Rejected: a schema-version framework.

KTD5. `cmd_status` treats a non-empty `review_result` as the existence signal, not `review_outcome`. When the result is present and the outcome is unset, print recorded-but-unrouted. When both are present, print the typed outcome as today. After the table, if a controller's `note` contains an outcome token (`accepted`, `repairs_requested`, `cycle_cap_best_available`, `review_incomplete`) that disagrees with the typed outcome, print one contradiction line; do not edit the note. Rejected: adding a `review` table column (the trailing block is the existing review surface; the bug is that the block is skipped). Rejected: making persist-then-route atomic (out of scope on #895).

KTD6. Accepted-result consistency is a `ReviewResult.__post_init__` invariant, so serialize and deserialize both refuse the illegal shape. When `record_cycle` / `result()` would emit `accepted` with empty failing lenses and empty unresolved fix identifiers, remaining `active` findings are reconciled to `resolved` via `dataclasses.replace` before the `ReviewResult` is constructed. That matches the observed incident (findings repaired in the tree, record left `active`). `repairs_requested` and `cycle_cap_best_available` do not reconcile. Rejected: refusing without reconciling (the producer would have to grow a second pass the incident showed it already missed). Rejected: changing scoring so a P2 active finding fails the lens (out of scope; protocol unchanged).

KTD7. Fix-identifier namespacing is a constructor argument on `ReviewCycleState`, not a new `ReviewResult` field. `consolidate_fix_requests(findings, lifecycle=...)` includes the lifecycle token in the identity string when it is a non-empty string; omitted or empty keeps today's `owner|autofix_class|finding_ids` bytes so unscoped tests stay stable. The optional `lifecycle` key is persisted on `review_cycle_state.v1` (`to_dict` / `from_dict` / `from_json`) so a resumed cycle in the same lifecycle keeps the same identifiers; absent in an old payload means unscoped. `review_result.v1` field set is unchanged. The code-review skill passes the lifecycle at the SKILL.md sentence that currently says "Then create `ReviewCycleState` with the selected roster identifiers" (`plugins/saga/skills/code-review/SKILL.md:398`). No registry, no longer digest. Rejected: putting lifecycle on `ReviewFinding` or on `ReviewResult` (artifact schema change). Rejected: lengthening the hex truncation (identical identity strings still collide). Rejected: constructor-only with no cycle-state round trip (a restore would mint unscoped ids and collide again).

KTD8. Resubmit is filtered by the units this `cmd_land` invocation actually merged. `resubmit_review_if_ready` takes the landed unit names (or the caller passes them) and resubmits only a pending controller whose lifecycle owns at least one of those names, whose own Work bag is clear, and whose status is not `running`. The revision in the prompt is the merge commit that landed that lifecycle's repairs (the landed unit's post-merge run-branch tip for that merge), not a later head produced by a different lifecycle in the same invocation. When `cmd_land` still passes a single `branch_tip`, compute per-controller revision from the landed set before prompting. Unscoped single-controller path is unchanged: any land of its repairs still resubmits. Rejected: resubmitting every pending controller with the final run-branch head (the incident). Rejected: dropping automatic resubmit (operators rely on it inside one lifecycle).

KTD9. The multi-controller resubmit loop catches `SystemExit` per controller the same way it already catches `StagedInputError`. A non-staged write failure is recorded, named, and the loop continues. After every controller has had its turn, withheld staged controllers still raise the combined `StagedInputError` (exit 4 via today's land handler) and non-staged failures raise a `SystemExit` listing the skipped names so land still exits 4. One success among failures does not return 0. Rejected: swallowing the failure and returning True because a later controller succeeded.

KTD10. Land exit precedence is computed before any return 3. After merges, derive `resubmit_owed_unmade` from: `resubmit_failed`, a raised `StagedInputError`, or any controller whose slot is still `review_resubmit_pending` with operator fix requests (the current "HELD" print). If that flag is set, return 4 even when `cleanup_failures` is non-empty. Cleanup is still printed. Operator-hold therefore leaves 0. Update `plugins/orchestrate/commands/orchestrate.md` row 4 to name operator-hold, and row 3 to say it is outranked by 4. `test_the_documented_land_exit_codes_are_the_ones_the_command_returns` keeps pinning the sets equal. Rejected: a precedence column of new exit codes. Rejected: leaving operator-hold at 0 because the prose already says "HELD".

KTD11. Partial-dispatch retry uses a per-fix-id list on the controller's review slot (`dispatched_fix_ids`), not on the request dict and not on the worker unit. `dispatch_review_routing` appends the fix_id only after `send_one` returns. On retry, `cmd_review_result` still re-runs `route_review_result`, which rebuilds request dicts from the artifact and `_park_fix_request` replaces the parked bag — so a flag on the request dict would be wiped. A marker on the worker would miss a retry that mints or selects a different holder for the same fix_id and would prompt a second session to do work already taken. `dispatch_review_routing` therefore takes the slot (or `Run` plus controller), skips a send when `_fix_request_id(request)` is already in `slot["dispatched_fix_ids"]`, and writes the id after a successful send. Replacements and assignments are unchanged. `setdefault` to `[]` so older records load. The marker is run-record state, not a `review_result.v1` field. Rejected: a `dispatched` key on the request dict (wiped on retry). Rejected: a list on `Unit` (wrong holder on retry). Rejected: skipping by unit name. Rejected: treating bag-dedup in `_park_fix_request` as coverage.

KTD12. One branch, two file-disjoint lanes, one PR against `main`. Saga units land in `review_consensus.py` first (894 then 899) so Orchestrate ingest tests can consume a consistent artifact. Orchestrate units then land in the recorded child order. Release bump is one unit at the end of both lanes. Backend: `lifecycle_state.recommend_execution_backend` recommended `team-execution` on functional-file count (16 files, 5 of them release bookkeeping). This session is the authorized executor, so `backend: inline` is the recorded choice. Destination is `pr`. Rejected: two PRs (the goal is one pull-ready version). Rejected: a fourth code-review cycle.

## Implementation Units

### U1. Accepted-result consistency

An accepted result with nothing outstanding cannot still list findings as open.

**Goal:** `ReviewResult` refuses the accepted+empty-failing+empty-unresolved+active-finding shape, and `record_cycle` reconciles remaining active findings to `resolved` before constructing that shape.

**Requirements:** R6, R12

**Dependencies:** none

**Files:** `plugins/saga/scripts/review_consensus.py`, `plugins/saga/skills/code-review/SKILL.md`, `tests/test_review_consensus_cycles.py`

**Approach:** In `ReviewResult.__post_init__`, after the existing accepted-cannot-carry-failing-lenses check, if `outcome == "accepted"` and not `failing_lenses` and not `unresolved_fix_ids` and any `finding.status == "active"`, raise `ReviewConsensusError`. In `ReviewCycleState.result()`, when that same triple holds, replace each remaining active finding with `dataclasses.replace(finding, status="resolved")` before passing `findings=` into `ReviewResult`. Do not touch findings when the outcome is `repairs_requested` or `cycle_cap_best_available`. Document the invariant in the code-review skill next to the outcome vocabulary. Do not add an evidence-file-exists check.

**Patterns to follow:** `ReviewResult.__post_init__` at `plugins/saga/scripts/review_consensus.py:1074`, `result()` at `review_consensus.py:1719`, `_accepted_result` / `_finding` helpers in `tests/test_review_consensus_cycles.py`.

**Test scenarios:** TP-894. Happy: passing scores plus a P2 pre_existing or advisory active finding round-trip with that finding `resolved`. Edge: `repairs_requested` still carries `active`. Error: constructing `ReviewResult` directly in the illegal shape raises. Mutation: deleting the `__post_init__` check lets `from_json` accept the illegal shape.

**Verification:** `test_accepted_result_cannot_carry_active_findings` fails if an accepted JSON blob still has `"status": "active"`. `test_repairs_requested_may_carry_active_findings` stays green.

---

### U2. Fix-identifier namespacing

Two lifecycles cannot mint the same repair identity for different findings.

**Goal:** `consolidate_fix_requests` includes a lifecycle token in the identity string when one is supplied, and the same inputs plus the same lifecycle still hash to the same `fix_id`.

**Requirements:** R7, R12

**Dependencies:** U1 (same module; accepted-result invariant must already hold so a namespaced request cannot smuggle an illegal accepted shape)

**Files:** `plugins/saga/scripts/review_consensus.py`, `plugins/saga/skills/code-review/SKILL.md`, `tests/test_review_consensus_cycles.py`

**Approach:** Add an optional `lifecycle: str | None = None` argument to `ReviewCycleState.__init__` and to `consolidate_fix_requests`. Store it on the state; do not add it to `ReviewResult`. Persist it as an optional `lifecycle` key on `review_cycle_state.v1` in `to_dict`; `from_dict` / `from_json` pass it back into `__init__`; an old payload without the key is unscoped. When hashing, if the lifecycle is a non-empty string, prepend it to the identity tuple; otherwise keep today's `owner|autofix_class|*finding_ids` bytes. `record_cycle` and `result()` pass `self._lifecycle` into `consolidate_fix_requests`. Edit the SKILL.md sentence at `plugins/saga/skills/code-review/SKILL.md:398` so construction passes the lifecycle the review is serving (Orchestrate controller lifecycle when present, else omitted). Existing `test_finding_routes_serialize_into_consolidated_fix_requests` stays green because it constructs state without a lifecycle. `test_cycle_state_round_trips_and_resumes_the_same_selective_rerun` must still round-trip; extend it or add a sibling that round-trips a non-empty lifecycle and then re-derives the same `fix_id`.

**Patterns to follow:** identity construction at `review_consensus.py:1352`, `ReviewCycleState.__init__` at `review_consensus.py:1386`.

**Test scenarios:** TP-899. Happy: two states with `lifecycle="c2"` and `lifecycle="c6"`, identical findings, different `fix_id`. Edge: same lifecycle, two `record_cycle` calls that re-derive the same group, identical `fix_id`. Resume: `to_json` / `from_json` then re-derive, same `fix_id`. Error: none beyond existing grouping errors. Mutation: dropping the lifecycle from the identity, or from cycle-state restore, makes the two states collide or the resume mint a different id.

**Verification:** the cross-lifecycle test's two `fix_id` values differ, and the within-lifecycle pair is equal.

---

### U3. Review-slot migration on late lifecycle assignment

A result written while unscoped must still be the result after the controller is scoped.

**Goal:** `Run.review_slot` copies run-global review state into the named slot on first scoped read, and refuses a conflicting named slot.

**Requirements:** R1, R12

**Dependencies:** none (Orchestrate lane; file-disjoint from U1–U2)

**Files:** `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py`, `plugins/orchestrate/skills/orchestrate/SKILL.md`, `tests/test_orchestrate_scoped_review_controllers.py`

**Approach:** After computing `key` in `review_slot`, if `key != RUN_SLOT`, consider migration. Source is `review_states.get(RUN_SLOT)` filled the same way today's `key == RUN_SLOT` branch fills from run-level fields. If the named slot is default-empty (`review_result is None`, `review_outcome is None`, `review_resubmit_pending` is False, `operator_fix_requests` is empty) and the source holds a `review_result`, copy the four fields (list-copy `operator_fix_requests`). If more than one scoped controller exists and more than one named slot is still default-empty, raise `SystemExit` naming the ambiguity instead of copying into both. If the named slot already holds a `review_result` that is not byte-identical to the source, raise `SystemExit` naming both. Do not write the named slot back onto run-level fields (`write_review_slot` already skips that for scoped controllers). Document the late-assignment path in SKILL.md next to the existing "read through `review_slot`" rule.

**Patterns to follow:** `review_slot` at `orchestrate.py:653`, `write_review_slot` at `orchestrate.py:681`, `test_each_scoped_controller_keeps_its_own_typed_state` in `tests/test_orchestrate_scoped_review_controllers.py`.

**Test scenarios:** TP-898. Happy: unscoped persist, assign `lifecycle`, read named slot, four fields present and not the same list object as run-level. Error: pre-populate the named slot with different bytes, expect `SystemExit` and unchanged slots. Mutation: removing the copy leaves `review_result is None` after assignment.

**Verification:** `status` after late assignment prints the typed outcome that was stored unscoped.

---

### U4. Replacement identity

A repair unit's name and workspace must name the slice it actually serves.

**Goal:** `_replacement_name` and `_replacement_worker` stamp lifecycle identity on scoped mints without compounding `-fix-` and without dropping template lineage.

**Requirements:** R2, R12

**Dependencies:** U3 (replacements are stored on the run the slot now owns)

**Files:** `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py`, `plugins/orchestrate/skills/orchestrate/SKILL.md`, `tests/test_orchestrate_review_loop.py`

**Approach:** Change `_replacement_name` to take the controller (or its lifecycle). Stem is `str(controller.lifecycle)` when scoped, else `controller.name` if present, else `template.name`. If that stem already contains `-fix-`, keep only the prefix before the first `-fix-`. Then append `-repair-{slug}` (not a second `-fix-`) and apply today's 80-character trim and numeric suffix for uniqueness. In `_replacement_worker`, when the controller is scoped, set `workspace` to `{lifecycle}-repair` (the lifecycle string, already the run's identifier for that slice) instead of `template.workspace`. Append a unit note `minted from {template.name}`. Leave vendor/model/effort/permission/setup/launch_args/account/role/paths/fix_requests/serialize/lifecycle assignment as they are, including `lifecycle=template.lifecycle or controller.lifecycle`. Update `test_a_missing_live_match_creates_a_replacement_work_worker` if it asserts the old `{template.name}-fix-` stem for a scoped fixture; keep it for unscoped.

**Patterns to follow:** `_replacement_name` at `orchestrate.py:1329`, `_replacement_worker` at `orchestrate.py:1341`, `test_a_missing_live_match_creates_a_replacement_work_worker` at `tests/test_orchestrate_review_loop.py:208`.

**Test scenarios:** TP-902. Happy: scoped controller + unscoped shell template → name and workspace contain the providers lifecycle, not `shell`. Edge: template name already contains `-fix-` → no `-fix-fix-`. Unscoped mint still uses a non-compounded stem from the template. Mutation: restoring `stem = f"{template.name}-fix-{slug}"` fails the scoped case.

**Verification:** the replacement unit's `name` and `workspace` are greppable for the lifecycle token and not for the template slice token.

---

### U5. Terminal-unit routing

A worker retired for cause must not be handed a repair just because its pane is still live.

**Goal:** `route_review_result` never selects a terminal unit as reusable, and a request whose only match is terminal mints a replacement instead of flipping the retired unit to `running`.

**Requirements:** R3, R12

**Dependencies:** U4 (mint path must already produce a lifecycle-accurate replacement)

**Files:** `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py`, `plugins/orchestrate/skills/orchestrate/SKILL.md`, `tests/test_orchestrate_review_loop.py`

**Approach:** Introduce a small helper `_unit_is_terminal(unit)` true for `failed`, `orphaned`, `account_mismatch`, `parked`. Filter `reusable` with `not _unit_is_terminal(unit)` in addition to `_unit_is_live` and the existing scoped-unscoped guard. Filter the `assigned` search the same way so a terminal unit that already carries the fix_id is not reused. Today's `templates = matching or role_workers` still includes terminal units as mint templates (their execution config is the point); the minted copy is a new `pending` unit. In `dispatch_review_routing`, skip (or refuse) a dispatch whose unit is terminal rather than setting `unit.status = RUNNING`. Document the status predicate next to the live-pane rule in SKILL.md.

**Patterns to follow:** reusable filter at `orchestrate.py:1421`, `dispatch_review_routing` at `orchestrate.py:1482`, `test_two_role_and_path_matches_reuse_live_workers_and_protect_them` at `tests/test_orchestrate_review_loop.py:174`.

**Test scenarios:** TP-892. Happy: failed+live match, no other live match → replacement minted, failed unit still `failed`. Edge: running match beside a failed match → running reused, failed untouched. Error: none new; missing-role `SystemExit` stays. Mutation: dropping the status filter dispatches the failed unit and the test sees `status == running`.

**Verification:** after `route_review_result` + `dispatch_review_routing`, the failed unit's status is `failed` and `routing.replacements` is non-empty.

---

### U6. Terminal-outcome and cycle-regressed ingest

A capped lifecycle cannot be silently reopened by a cycle-one acceptance.

**Goal:** `cmd_review_result` refuses a non-identical ingest into a terminal slot and refuses a shorter `cycle_history` than the slot already stored.

**Requirements:** R4, R12

**Dependencies:** U3 (the slot being compared must be the controller's real slot, including after late assignment)

**Files:** `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py`, `plugins/orchestrate/skills/orchestrate/SKILL.md`, `tests/test_orchestrate_review_loop.py`

**Approach:** After resolving `controller` and reading `slot`, and after the existing byte-identical replay return, parse stored and incoming JSON when both are objects. If stored `outcome` is `accepted` or `cycle_cap_best_available` and incoming bytes differ, `SystemExit` naming the stored outcome and the incoming cycle length; do not call `write_review_slot`. If both payloads have a `cycle_history` list and `len(incoming) < len(stored)`, same named stop even when stored is not terminal. If stored bytes are not JSON, continue with today's persist-then-route path. Do not add a `cycle_history` field to the run record; read it from the stored artifact. Document the refusal in SKILL.md next to `review-result`.

**Patterns to follow:** replay guard at `orchestrate.py:3674`, persist-then-route at `orchestrate.py:3679`, `test_typed_result_round_trips_byte_identically_without_policy_parsing` at `tests/test_orchestrate_review_loop.py:419`.

**Test scenarios:** TP-893. Happy: byte-identical replay still exits 0. Error: terminal slot + cycle-1 accepted → non-zero, slot unchanged. Error: non-terminal slot with history length 2 receiving length 1 → refused. Mutation: deleting the check lets the slot's outcome become `accepted`.

**Verification:** `Run.load().review_slot(controller)["review_outcome"]` is still `cycle_cap_best_available` after the refused ingest.

---

### U7. Faithful status

`status` must show a stored result even when routing has not yet written an outcome, and must not let a note contradict that outcome in silence.

**Goal:** `cmd_status` prints recorded-but-unrouted for a stored result with unset outcome, always prints the typed outcome when set, and names a note that contradicts it.

**Requirements:** R5, R12

**Dependencies:** U6 (the intermediate persist-with-unset-outcome state is the same two-phase write U6 leaves in place)

**Files:** `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py`, `plugins/orchestrate/skills/orchestrate/SKILL.md`, `tests/test_orchestrate_status_and_notes.py`

**Approach:** In the per-slot loop in `cmd_status`, do not `continue` solely because `review_outcome` is falsy. If `review_result` is set and `review_outcome` is not, print `Code Review result{scope}: recorded-but-unrouted`. If the outcome is set, print it as today. After that line, if `owner` is not None and `owner.note` contains an outcome token that is not the typed outcome (case-insensitive whole-word match on the four `REVIEW_OUTCOMES` members), print `note contradicts typed outcome: note has {token}, slot has {outcome}`. Do not add a table column. Do not edit the note. Do not change `cmd_review_result`'s two-phase write.

**Patterns to follow:** slot loop at `orchestrate.py:3927`, `test_status_collapses_untrusted_review_fields_to_one_line` at `tests/test_orchestrate_review_loop.py:595`, `tests/test_orchestrate_status_and_notes.py`.

**Test scenarios:** TP-895. Happy: persist without completing route (or write the slot that way) → stdout contains `recorded-but-unrouted`. Edge: typed `cycle_cap_best_available` + note `cycle 4 ACCEPTED` → typed outcome still printed, contradiction line present, note column still present. Mutation: restoring the `if not slot["review_outcome"]: continue` skip hides the stored result.

**Verification:** `cmd_status` exit 0, stdout contains the unrouted phrase in the first case and the typed outcome token in the second.

---

### U8. Lifecycle-scoped resubmit and write-failure isolation

A land in one lifecycle must not retarget another lifecycle's in-flight controller, and a write failure on one controller must not skip the rest.

**Goal:** `resubmit_review_if_ready` resubmits only controllers whose own lifecycle landed repairs in this invocation, never a controller already `running`, names that lifecycle's landed revision, and continues after a non-staged `SystemExit` on one controller.

**Requirements:** R8, R9, R12

**Dependencies:** U5 (repairs must already sit on the right non-terminal unit before land resubmits)

**Files:** `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py`, `plugins/orchestrate/skills/orchestrate/SKILL.md`, `tests/test_orchestrate_review_loop.py`

**Approach:** Change `resubmit_review_if_ready` to accept the landed unit names (default empty: today's "any pending" unscoped path). For the multi-controller loop, skip a candidate whose lifecycle owns none of those names, skip a candidate whose `status == RUNNING`, and pass `_resubmit_one` the revision of that lifecycle's landed repair (the run-branch tip after that unit's merge, recorded while `cmd_land` walks `landed_names`) rather than the invocation's final `branch_tip` when they differ. Catch `StagedInputError` first, then `SystemExit`, per candidate: when the launcher is live, `StagedInputError` is a `SystemExit` subclass (`plugins/agent-launcher/skills/agent-launcher/scripts/launcher.py:346`), so the reverse order would classify a withhold as a hard write failure. Append the name and message, continue. After the loop, raise combined `StagedInputError` if any were withheld; raise `SystemExit` listing non-staged failures if any occurred; return whether any send succeeded only when neither list is populated. `cmd_land` passes `landed_names` and, if it has them, per-unit merged tips. Single-controller unscoped path does not take the landed-name filter (a land of its repairs still resubmits). Document the lifecycle filter in SKILL.md; the 884 incident is the example.

**Patterns to follow:** `resubmit_review_if_ready` at `orchestrate.py:1541`, `_resubmit_one` at `orchestrate.py:1589`, `test_a_staged_stop_on_one_controller_does_not_block_the_other_controllers_resubmit` at `tests/test_orchestrate_review_loop.py:1303`, `test_landed_work_repairs_resubmit_the_exact_revision_to_the_same_controller` at `tests/test_orchestrate_review_loop.py:997`.

**Test scenarios:** TP-884, TP-956. Happy: land A, B running → only A prompted, prompt names A's landed revision. Edge: no landed repairs for a pending controller → no prompt. Error: first sender `SystemExit`, second succeeds → second prompted, first named, land can still exit 4. Existing staged-input isolation stays green. Mutation: walking every pending controller with `branch_tip` prompts B.

**Verification:** captured sender calls contain A's controller and A's revision, and do not contain B.

---

### U9. Land exit 4 outranks leftover-path 3 and operator-hold

The exit code that means "a repair cycle is stalled" must be the one the caller sees.

**Goal:** `cmd_land` returns 4 whenever a review resubmission was owed and not made, including operator-hold and including when a leftover landing path would otherwise return 3.

**Requirements:** R10, R12

**Dependencies:** U8 (the owed/unmade signal is what U8's withheld and failed lists produce)

**Files:** `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py`, `plugins/orchestrate/commands/orchestrate.md`, `tests/test_orchestrate_review_loop.py`

**Approach:** After the resubmit block and the HELD prints, set `resubmit_owed_unmade` true if `resubmit_failed` or any controller slot is still `review_resubmit_pending` with operator fix requests (scoped or unscoped). Catch `StagedInputError` from `resubmit_review_if_ready` in `cmd_land` the same way today's `SystemExit` handler sets `resubmit_failed` (if it does not already). Move the `if cleanup_failures: return 3` so that `resubmit_owed_unmade` returns 4 first; still print the cleanup failures. Operator-hold therefore returns 4. Update the exit-code table: row 4 names prompt failure, staged withhold, and operator-hold; row 3 says it is not returned when 4 applies. Change `test_land_names_the_operator_request_holding_review_resubmission` from `== 0` to `== 4`. Keep `test_the_documented_land_exit_codes_are_the_ones_the_command_returns` as the pin between table and `return` statements.

**Patterns to follow:** cleanup return at `orchestrate.py:4857`, resubmit_failed return at `orchestrate.py:4880`, HELD print at `orchestrate.py:4809`, exit-code table at `plugins/orchestrate/commands/orchestrate.md:513`, `test_land_exits_4_when_the_resubmission_is_withheld_on_staged_input` at `tests/test_orchestrate_review_loop.py:1347`.

**Test scenarios:** TP-959, TP-974. Happy: leftover path + staged withhold → exit 4, cleanup prose present. Happy: operator-hold only → exit 4, HELD prose present. Edge: leftover path and no owed resubmit → still exit 3. Mutation: returning 3 before the owed check fails TP-959; returning 0 on HELD fails TP-974.

**Verification:** `cmd_land` return value is 4 in both owed cases; the documented table still equals the command's returned constants.

---

### U10. Dispatch-once retry

A partial `review-result` retry must not re-prompt a worker that already took its repair.

**Goal:** `dispatch_review_routing` records a per-request dispatched marker after a successful send, and a retry skips requests that already carry it.

**Requirements:** R11, R12

**Dependencies:** U5 (terminal units are already out of the dispatch set)

**Files:** `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py`, `plugins/orchestrate/skills/orchestrate/SKILL.md`, `tests/test_orchestrate_review_loop.py`

**Approach:** `review_slot` already `setdefault`s four keys; add `dispatched_fix_ids` defaulting to `[]`. Change `dispatch_review_routing` to accept the slot (or `Run` plus controller — smallest compatible extra argument). Skip a send when `_fix_request_id(request)` is in that list; after `send_one` returns, append the id and let the caller `save`. Do not store the marker on the request dict: `route_review_result` rebuilds request dicts from the artifact and `_park_fix_request` (`orchestrate.py:1296`) strips same-id bags and appends the new dict, which would wipe a request-level flag. Do not store it on `Unit`: a retry that mints or selects a different holder for the same fix_id would prompt a second session. `cmd_review_result` keeps today's "outcome unset, retryable, exit 1" path on partial dispatch. Existing callers of `dispatch_review_routing` in tests pass the slot or get a default empty list. The marker is run-record state, not a `review_result.v1` field. Existing `_park_fix_request` bag-dedup stays; it is not this unit's coverage.

**Patterns to follow:** `dispatch_review_routing` at `orchestrate.py:1482`, `cmd_review_result` partial path at `orchestrate.py:3697`, `test_failed_live_dispatch_keeps_the_result_retryable_and_the_worker_protected` at `tests/test_orchestrate_review_loop.py:445`.

**Test scenarios:** TP-976. Happy: two workers, second `StagedInputError`, retry → sender called once for the first worker across both attempts, and again for the second. Edge: byte-identical replay with outcome already set still returns 0 without dispatching (existing test). Mutation: storing the marker on the request dict (wiped by `_park_fix_request` on retry), on the worker unit (wrong holder), skipping only by unit name, or relying on bag-dedup, re-prompts the first worker.

**Verification:** a list of `(unit.name, request["fix_id"])` captured from the sender has the first pair once.

---

### U11. Release surfaces, journal, and child closeout

Bump only the plugins whose contract changed, keep the three surfaces in parity, and close children on green required checks.

**Goal:** Orchestrate strictly above 4.4.0 and Saga strictly above 0.158.0 on `plugin.json`, marketplace, and CHANGELOG; KTDs recorded in `DECISIONS.md`; LEARNINGS for the non-obvious guards; PR against `main` with GitHub required checks green; every nested child of 908 closed or parked on 908.

**Requirements:** R13

**Dependencies:** U1–U10

**Files:** `plugins/orchestrate/.claude-plugin/plugin.json`, `plugins/orchestrate/CHANGELOG.md`, `plugins/saga/.claude-plugin/plugin.json`, `plugins/saga/CHANGELOG.md`, `.claude-plugin/marketplace.json`, `docs/engineering-journal/DECISIONS.md`, `docs/engineering-journal/LEARNINGS.md`, and any test that pins the current Orchestrate or Saga version

**Approach:** Re-read both versions from `origin/main` at bump time. Write CHANGELOG headings that name the twelve children. Record KTD1–KTD11 in `DECISIONS.md` with a revisit-when. Add LEARNINGS for slot migration, ingest continuity, land-exit precedence, and fix-id namespacing (non-obvious guards). Follow `{#993-release-bump-owns-drift-guards}`. Open one PR against `main`. Close each child on merged-or-equivalent evidence (green required checks on the reviewed head), or park it on 908 with a named ruling if a child cannot be satisfied without a schema change.

**Patterns to follow:** issue 1003's 4.4.0 bump, marketplace entries, `{#993-release-bump-owns-drift-guards}`.

**Test scenarios:** version-parity rows in the finite test plan. `Test expectation: none` is not used; the marketplace contract tests in this repo are the check.

**Verification:** marketplace version equals `plugin.json` per plugin; both are strictly above the `origin/main` read; CHANGELOG has the new headings; `gh pr checks` shows Tests (Python 3.12), Validate Plugins, Lint, Type Check, and Security Scan (strict) success.

## Scope Boundaries

Out of scope:

- Issue 885 and any child not nested under 908.
- Issues 909 and 910 (merge-order care only).
- Changing the review artifact schema, lens scoring, lens selection, or the consensus protocol.
- Migrating or rewriting existing Orchestrate run records as a batch; renaming units already in a run.
- Reopening the scoped-controller design settled by issue 877.
- Adding validation that a finding's cited evidence file exists.
- Removing run-level review mirror fields.
- Changing unscoped backfill, execution-config inheritance from a replacement template, or lifecycle-fallback precedence beyond U4's name and workspace.
- A fourth `/code-review` scoring cycle.
- Direct push to protected `main`.
- Installing or enabling the new versions inside a live Claude Code session.

Deferred to follow-up work: none from this parent. A child that cannot be satisfied without a schema change is parked on 908 rather than deferred into a new issue from this plan.

## Risks

- `/code-review` must reach overall 9.0 in at most three cycles. If cycle three is `cycle_cap_best_available` below 9.0, do not run a fourth cycle; surface that to the operator.
- `main` is protected. Required checks are Tests (Python 3.12), Validate Plugins, Lint, Type Check, Security Scan (strict). Local `scripts/gate.sh` is not a substitute.
- Orchestrate 4.4.0 / Saga 0.158.0 on `origin/main` may move if 909 or 910 lands first; re-read at bump time.
- Issue 908's 2026-09-13 amendment said backlog grouping did not authorize implementation. This plan is the operator launch approval for all twelve current nested children, including 884.

## Execution backend

`lifecycle_state.recommend_execution_backend` (16 files, 5 release-bookkeeping, 2 lanes, `has_code_surface=True`) recommended `team-execution`. This goal session is the authorized executor, so the recorded choice is `inline`. Destination is `pr`.
