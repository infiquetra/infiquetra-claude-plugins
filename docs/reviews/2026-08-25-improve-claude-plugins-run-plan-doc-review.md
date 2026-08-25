# Doc review — improve-claude-plugins unattended-run plan (issue #814)

The plan is the S1 HOW for the eleven-leaf #814 run. It is not ready to drive unattended implementation: lane D still HALTs at gates G1/G3 that the operator already ruled NARROW, and unit U11 would add a chaperone dispatch surface that ruling forbids.

| field | value |
| --- | --- |
| target path | `docs/plans/2026-08-25-improve-claude-plugins-run-plan.md` |
| reviewed revision | plan commit `cb09febe` (`docs(plans): run-wide implementation plan for the improve-claude-plugins run (#814)`); worktree `orch/orch-2026-08-25-814-doc-review` at `d8dac2b6`; citations checked against `origin/main` `ebe476d4` after `git fetch` |
| blocked status | **yes** — unresolved P0 and P1 findings. S3 must validate each finding against the tree and repair only the genuine ones. No second broad document review. |
| applied fixes | none. The #814 contract and this session's instruction forbid repairing the plan here. |
| review artifact path | `docs/reviews/2026-08-25-improve-claude-plugins-run-plan-doc-review.md` |
| linked issue | infiquetra/infiquetra-claude-plugins#814 (authoritative contract, including operating-context and proportionality; 2026-08-25 G1/G3 comments are the live gates) |
| linked plan | `docs/plans/2026-08-25-improve-claude-plugins-run-plan.md` |
| override rationale | n/a |

## Readiness summary

The plan honors #814's shape: eleven units, lanes W/O/S/D, serialize/`after` edges, collision surfaces, per-unit smallest-fix / reuse / new-parts / rejected-alternative records, locked lens predeclaration, and inline workers.

It is not implementation-ready. An unattended agent following lane D literally will park a decision the operator already made, or build a cross-vendor chaperone the operator forbade. Unit U7 would add a Stage-field op-kind and a live Stage write for a project field that does not exist on Operations, Asgard, or CAMPPS.

Security and reliability findings below name an in-scope trust boundary or failure mode and a concrete consequence. Hypothetical scale is not used. Justified safeguards at real trust boundaries (certificate-gated board writes, halt-not-fallback on transport removal, emit-time fail-loud, no silent agent substitution, process-launch receipts) are preserved.

## Remaining findings by priority

| id | severity | status | claim |
| --- | --- | --- | --- |
| F1 | P0 | open | U11 would add chaperone-wrapper dispatch that gate G3 forbids |
| F2 | P1 | open | U10 still HALTs at G1 and presents a four-way choice the operator already ruled NARROW |
| F3 | P1 | open | U7 adds `set-field-stage` and a live Stage correction; no Infiquetra board has a Stage field |
| F4 | P1 | open | U7's "writer rejects any field other than Stage or Status" can clamp non-Status board ops |
| F5 | P1 | open | Unit briefs paraphrase; they do not carry each leaf's acceptance criteria, verification commands, and stop conditions |
| F6 | P2 | open | KTD2's mermaid-cli fallback re-authorizes the rejected heavy path |
| F7 | P2 | open | U2 does not pin how Node, mermaid, and the DOM shim land in CI and `gate.sh` |
| F8 | P2 | open | U1/U4 verify-and-close departs from the parent's per-merged-PR close-out shape |
| F9 | P2 | open | Locked lens sets are one conditional short on U6, U7, U10 phase B, and U11 |
| F10 | P2 | open | U6's brief omits the new plugin's release surfaces |
| F11 | P3 | open | The 13-broken-diagram citation is `grounding-brief.md:148-149`, not `:187` |
| F12 | P3 | open | KTD9 attributes `backend: inline` to the #814 decision table, which has no such row |
| F13 | P3 | open | Two line/job-name citations are slightly stale (`code-review` `:45-50`; `ci.yml:159`) |

## Rubric review (issue phase, applied to the plan as the issue-derived S1 artifact)

Core rubrics all applied. Extra rubrics all applied: the plan is a code-change campaign in a non-trivial repo, eleven units, and a named DAG. There is no plan-phase rubric in the engine.

| rubric | score | note |
| --- | --- | --- |
| acceptance_criteria_clarity | 7 | Leaf ACs are executable. The plan paraphrases them. U7's Stage live-check, U10's HALT, and U11's chaperone shape are not pass/fail against the live gates and the live board. |
| devils_advocate_issue | 6 | U7 Stage machinery, U11 chaperone, and the mermaid-cli fallback bundle work the current failure does not need. REVISE, not BLOCK at rubric level. The P0/P1 readiness findings are the gate. |
| spec_fidelity | 7 | Descent from #814 is named. Lane DAG, G2, and the eight-row decision table match. Live G1/G3 NARROW comments are not inherited. Verify-and-close is disclosed, not silent. |
| context_completeness | 8 | File and line pointers are dense; most hold at `ebe476d4`. The misses that would make an agent invent a path are U7 Stage, U11 `workflow_emitter.py` vs `execution_spec.py` (already corrected in KTD5), and U2's Node wiring. |
| issue_sizing | 9 | One unit per leaf, one PR per unit, matching the contract. U6 is large because the leaf is an extract, not because the plan bundled extras. |
| prerequisite_mapping | 8 | Lane DAG matches #814. The G1 HALT edge is now stale; S2 → D1-impl → D2 is still the right serialize order once G1 is treated as already ruled. |

Rubric findings are not reclassified as readiness findings. The F-series below are the readiness-skeptic pass, including proportionality.

## Lens predeclaration (decision row 7)

The always-on four (`architecture-maintainability`, `correctness`, `security`, `testing`) are correctly locked for every reviewed revision. Verify-and-close units U1 and U4 correctly declare no review when no diff ships. Conditionals that are present have a one-line reason. No lens in the roster is selected without a reason.

Do not add `performance`, `privacy`, `previous-comments`, or `accessibility-human-usability` later. Those triggers do not fit this run. `previous-comments` can only apply once a PR has threads; it is not predeclarable.

S3 may add only the conditionals named in F9. That is this review validating the locked set, not a mid-run lens addition. Adding anything else still requires returning to the operator.

| Unit | Plan set | This review |
| --- | --- | --- |
| U1 #792 | none (contingency: always-on four) | Confirmed |
| U2 #405 | + `deployment-infrastructure` | Confirmed. Inside that lens, do not demand high availability or multi-tenant rollout; the change is a CI step and a gate coverage line. |
| U3 #407 | always-on four | Confirmed |
| U4 #725 | none (contingency: + `documentation-clarity`) | Confirmed |
| U5 #813 | + `documentation-clarity`, `agent-usability` | Confirmed |
| U6 #777 | + `api-contract`, `reliability`, `agent-usability` | Add `adversarial` (F9). Process-launch, silent substitution, and unowned cleanup are the leaf's named failure modes. |
| U7 #812 | + `reliability` | Add `api-contract` only if a new op-kind still ships. If F3 stands (no `set-field-stage`), reliability alone is enough. |
| U8 #776 | + `reliability`, `agent-usability`, `api-contract` | Confirmed. Do not add a fourth conditional. |
| U9 #778 | + `agent-usability` | Confirmed |
| U10 #808 | + `documentation-clarity` (decision PR); + `api-contract` (phase-B impl) | Add `agent-usability` on the phase-B skill-text diff (plan/work SKILL.md). |
| U11 #708 | + `api-contract` | Add `reliability`. After G3 the whole unit is fail-loud vs silent native fallback. |

## Decisions taken without asking

This session is S2 (the single Grok 4.6 extra-high document review). No question was left open.

1. **Do not repair the plan.** The contract says S3 validates and repairs. This file is the S2 ledger input.
2. **No engine-offer prompt and no second reviewer.** #814 forbids a second broad document review. An interactive offer would halt an unattended run.
3. **Live gates G1 and G3 are the 2026-08-25 NARROW rulings**, not the original HALT text in the #814 body. Plan commit `cb09febe` is 05:07 UTC; the G1 comment is 04:54 UTC and the G3 comment is 04:55 UTC. The committed plan did not inherit them.
4. **U11 is fail-loud validation in `execution_spec.py` only.** No chaperone-wrapper prompts, no model/effort bridging, no alias translation, no engine lifecycle in the workflow emitter.
5. **U10 implements NARROW in this run** after S2 (shared work-skill text). It does not HALT for a choice already recorded. Evidence inventory still runs. The four-way keep/narrow/replace/retire presentation is not re-opened.
6. **U1 and U4 close with evidence, no no-op PR.** Minting empty PRs on sole-writer surfaces has real collision cost. The parent close-out names the historical fixing commits.
7. **U7 is Status-only.** Do not create a Stage project field. Do not add `set-field-stage`. Keep a static "no Stage write exists" guard. Leave close/reopen/comment/label op-kinds untouched.
8. **U8 keeps `engine-registry.yaml` as explicitly non-transport metadata.** The leaf allows that carve-out. Deleting the registry exceeds every leaf.
9. **U2's Node dependency is accepted in both CI and `gate.sh`.** The gate's own contract forbids marking a CI-blocking step advisory. Do not take the mermaid-cli fallback unless `mermaid.parse()` is proven infeasible, and then disclose it in the PR rather than silently swapping.
10. **Issue-phase rubrics** were applied because this plan is the issue-derived S1 artifact.

## What holds (do not re-litigate)

Lane table, `after`/`serialize` edges, and collision surfaces match the #814 inventory. Writers for `plugins/orchestrate/**`, `plugins/saga/**`, `plugins/mission-control/**`, `plugins/agent-launcher/**`, `ci.yml`/`gate.sh`, `lint_journal_order.py`, `tests/test_orchestrate_hygiene.py`, and `CLAUDE.md` (no writer) are respected. No invented cross-lane edges.

Decision-table rows 1–4, 7, and 8 are restated, not re-decided. G2 is treated as resolved. Backend `inline` is the Orchestrate default and matches G1 NARROW (Claude Code Workflows are not the run's execution backend).

U1: `tests/test_orchestrate_hygiene.py:197-202` is the whitespace-collapse fix from commit `6396455a` (PR #790). Rerun on this tree: `COLUMNS=40` and `COLUMNS=200` each report 13 passed.

U4: `mirror.py` is absent on `origin/main`; commit `84e53a72` deleted it. `_MAX_EMBEDDED_REGIONS`, `PredicateInMirrorError`, and `ordinary reading` have no hits under `plugins/orchestrate/`. No mirror test file remains.

U2: 20 ```` ```mermaid ```` fences across 16 tracked files. `scripts/gate.sh:14-15` is the coverage self-check against `ci.yml`. `ci.yml:215` is the Lint-job journal ordering step.

U3: `scripts/lint_journal_order.py` is 188 lines; `DEFAULT_JOURNALS` at `:36-37`; `key()` at `:108-117`. The lint already runs in Lint (`ci.yml:215`) and in the PR-scoped newest-first step (`ci.yml:159-165`).

U5: docs-only; the three acceptance greps are in the brief; no new machinery.

U6: cited `orchestrate.py` symbols and line ranges match `origin/main` (4602 lines). Test counts match (38 / 8 / 30 / 8). Extract-don't-redesign and the explicit `herdr` dependency are the smallest change the leaf allows.

U8: transport trio line counts match (581 / 749 / 112). `engine-prefs` sites match. Seventeen registry-side *scripts* consume `engine-registry` / `engine_registry`; the leaf's non-transport carve-out is the right reading.

U9: judgment-selection text is at `code-review/SKILL.md:48-51` and `:218-231`. The 2026-08-23 incident is a named current failure; persisting approval on the existing review-cycle record is proportionate.

U10: `scripts/check_docs.py` is absent; substituting `lint_journal_order.py`, `changelog_heading_lint.py`, and `git diff --check` is the truthful check. `docs/plans/` holds 20 committed `*-spec.json` files (leaf baseline was 16).

U11 KTD5 is right: `workflow_emitter.py` is a workflow-lease contract with zero dispatch; `_agent_opts` at `execution_spec.py:2682-2694` is the live inert-opts defect; the `// external-engine dispatch:` comments at `:3097`, `:3122`, `:3162`, `:3319`, `:3896` are comments, not runtime.

Proportionality that is already good and must not be "hardened": U3 extends the existing lint in place; U5 is guidance only; U6 forbids a new vendor/model registry; U8 forbids a fallback runner; U9 forbids autonomous approval for the #418 adapter; U10 does not pre-decide the backend (the operator already did).

---

### F1 — U11 would add chaperone-wrapper dispatch that gate G3 forbids

**Severity:** P0

**Exact claim.** U11's smallest viable fix, contingent on a keep-or-narrow ruling "with an engine surface", tells the implementer to emit a chaperone form: explicit `model`/`effort` plus a prompt block driving `agy_delegate.py` / `codex_delegate.py`, and to enforce full model ids at emit. Gate G3 already ruled NARROW the other way.

**Evidence.**

- Plan U11 "Smallest viable fix" and KTD5 (`docs/plans/2026-08-25-improve-claude-plugins-run-plan.md`).
- G3 operator ruling on #708 (https://github.com/infiquetra/infiquetra-claude-plugins/issues/708#issuecomment-5405419292, 2026-08-25T04:55:15Z): preserve fail-loud rejection of an unsupported external-engine unit; do **not** add chaperone-wrapper prompts, model/effort bridging, alias translation, long-running engine process management, or another cross-vendor dispatch surface to the workflow emitter; Herdr and Orchestrate own cross-vendor sessions.
- Parent restatement on #814 (https://github.com/infiquetra/infiquetra-claude-plugins/issues/814#issuecomment-5405426586): "#708 stays the fail-loud validation defect"; "Orchestration parent #814 must not halt merely to request this disposition again."
- Live defect at `plugins/saga/scripts/execution_spec.py:2682-2694` (verified on `origin/main` `ebe476d4`): engine units emit `dispatch`/`engine`/`verifiability` opts the cc-workflows runtime ignores, and skip `model`/`effort`. That is silent native fallback today.

**In-scope trust boundary.** Execution-spec emission vs the Claude Code Workflow `agent()` runtime. An engine unit that the spec assigned to an external engine must not run as a native Claude subagent.

**Concrete consequence.** Following the plan adds a third dispatch path (chaperone wrappers inside the workflow emitter) while U8 is removing saga's extra transport and G1 is narrowing workflows to task-local Claude behavior. The silent-drop defect is real; the chaperone is the larger change G3 says cannot be the fix. The smaller change is emit-time `SpecError` naming the unsupported key or engine unit, on the existing validator seam.

**Suggested repair.** Rewrite U11 to: reject unsupported external-engine units and unsupported opts keys at emit with a named actionable error; add tests for fail-loud and for "no silent native fallback"; do not emit wrapper-driving prompts, model/effort bridges, or alias translation. Keep KTD5's file correction (`execution_spec.py`, not `workflow_emitter.py`). Re-anchor the leaf's `rg` on `workflow_emitter.py` in the PR body as a documented AC substitution.

---

### F2 — U10 still HALTs at G1 after the operator ruled NARROW

**Severity:** P1

**Exact claim.** R5, the lane table, U10 phase A, and the run-level stop condition still say #808 drafts keep/narrow/replace/retire, then HALTs; resume only on a recorded ruling; 9/11 closed is success if no ruling arrives. The ruling arrived before this plan was committed.

**Evidence.**

- Plan R5, U10 "then **HALT at G1**", Risks ("#708 starts before the G1 ruling exists"), stop-condition inheritance of "#814".
- G1 operator ruling on #808 (https://github.com/infiquetra/infiquetra-claude-plugins/issues/808#issuecomment-5405414716, 2026-08-25T04:54:41Z): NARROW; Claude Code Workflows remain only as explicitly invoked task-local mechanisms inside Herdr-managed sessions; not Saga Plan or Saga Work's default or automatic backend; no silent substitute or mechanism-neutral backend-switching abstraction; evidence phase still inventories, then **validates and implements this ruling instead of presenting the four-way choice again**; parent #814 must not halt merely to request G1 again.
- Plan commit `cb09febe` at 2026-08-25T05:07:50Z is after that comment.
- Leaf #808 AC still requires a DECISIONS entry and either implementation or dependency-aware follow-ups. With NARROW recorded, parking is no longer a successful 9/11 outcome unless evidence proves the narrowed shape internally contradictory.

**In-scope failure mode.** Decision-first backend fate. Implementing a keep/replace/retire direction, or building a generic backend switcher, would fight G1. Halting for a choice already made parks #808 and therefore #708 for no reason.

**Suggested repair.** Restate G1 NARROW verbatim in U10. Phase A still inventories producers/consumers/costs/failures and writes the DECISIONS entry, citing evidence, as validation of NARROW — not as a four-option menu. Phase B implements the smallest truthful narrowed shape (plan/work skill text and execution-spec surfaces only if runtime behavior must change) after S2, still serialized on shared work-skill text. HALT only if evidence proves NARROW internally contradictory or impossible. Drop "9/11 closed is success" as the default no-ruling path.

---

### F3 — U7 adds Stage machinery for a project field that does not exist

**Severity:** P1

**Exact claim.** U7 pre-commits to a new `set-field-stage` op-kind beside `set-field-status`, a writer that accepts Stage or Status by name, and a live Stage correction on a scratch issue. Planning already found zero Stage writes. Live project field discovery finds no Stage field.

**Evidence.**

- Plan KTD3 and U7 steps (2)–(4), including "live verification per the leaf: one Stage and one Status correction".
- Leaf #812 AC requires both fields, including `tests/test_saga_single_writer_guard.py` covering Stage and a live Stage correction.
- Read-only `flow field-options --project operations --field Stage` on this machine (2026-08-25): `Field(s) ['Stage'] not found on project 'operations'. Available fields: ['Title', 'Assignees', 'Status', 'Labels', 'Linked pull requests', 'Milestone', 'Repository', 'Reviewers', 'Parent issue', 'Sub-issues progress', 'Created', 'Updated', 'Closed', 'Objective', 'Priority']`. The same miss on `asgard` and `campps`. Status options match the #814 ladder (Idea / Shaping / Ready / Active / Verify / Done).
- `rg` over `plugins/saga` and `plugins/mission-control` for a Stage field write: no `set-field-stage`, no `--field Stage`. KTD3's own inventory ("no saga code path writes a Stage field at all") is consistent with the field's absence.
- #814 operating context: a new abstraction is permitted only when the unit names the current in-scope failure it prevents. There is no current Stage-write failure.

**In-scope trust boundary.** GitHub Projects field writes through mission-control `flow set-field`.

**Concrete consequence.** A live Stage correction fails because the field does not exist. Creating a Stage field would change board schema on every Infiquetra project this suite writes — out of scope, and a new operator workflow the leaf does not authorize. Adding `set-field-stage` to the certificate registry without a field is dead API surface.

**Suggested repair.** Keep inventory as step 1 and record the live field list. Implement Status-only: field name in the set-field operation, authorization, and retry identity; reject *set-field* submissions that name a project field other than Status (and other than Stage if a Stage field later exists); static guard that no saga call site composes a direct Status write or a write to a field named Stage. Do one live Status correction on a scratch issue. Do not create a Stage field. Do not add `set-field-stage` unless inventory finds a real Stage field on a board this repo writes. Note the leaf's Stage ACs as a documented substitution in the PR, with the field-options receipt attached.

---

### F4 — U7 can be read as clamping every board op to Stage/Status

**Severity:** P1

**Exact claim.** U7 says the five writer-invocation sites "all terminate in `default_board_writer` → `sdlc_manager.py flow set-field --field Status`" and "the writer rejects any field other than Stage or Status". On `origin/main` those sites are generic `board_writer` calls. `default_board_writer` also closes sub-issues, reopens them, posts progress comments, and adds/removes labels.

**Evidence.**

- Plan U7 "Smallest viable fix" list: `outcome_board_sync.py:370`, `outcome_reconcile.py:461`, `reconcile_controller.py:219`, `:269`, `board_progression.py:230`.
- Verified at `ebe476d4`: `:370` and `:219` are `authorize_and_write`; `:461`, `:269`, and `:230` are `board_writer(...)` with whatever `op_kind` the caller passed.
- `default_board_writer` at `board_progression.py:428-486` maps `set-field-status` to `flow set-field --field Status`, and also maps `sub-issue-close`, `sub-issue-reopen`, `issue-progress-comment`, `issue-label-add`, `issue-label-remove`. Anything else raises `ValueError`.
- Leaf #812 out-of-scope: "Unrelated board, audit, and merge writes remain untouched." Certificate registry at `reversibility_certificate.py:62-67` enumerates those other op-kinds on purpose.

**In-scope trust boundary.** The certificate-gated board-write seam. Status corrections must go through mission-control set-field. Close/comment/label writes must keep their existing verbs.

**Concrete consequence.** An agent that "rejects any field other than Stage or Status" on `default_board_writer` as a whole would raise on close/reopen/comment/label. Saga skills that post progress comments or close sub-issues (`/work`, `/loop`, `/plan` write paths) would fail closed. That is a current, in-scope failure the leaf forbids introducing.

**Suggested repair.** Constrain only the *set-field* field-name (Status now; Stage only if F3 is overturned by a real field). Leave other `OpKind` mappings untouched. Do not rewrite `outcome_reconcile.py:461` or `reconcile_controller.py:269` to `flow set-field`. Phrase the inventory as "Status set-field writes funnel through `default_board_writer`; other op-kinds are out of scope."

---

### F5 — Unit briefs do not carry leaf acceptance criteria, verification commands, or stop conditions

**Severity:** P1

**Exact claim.** #814's per-unit execution contract and this plan's R1 both say the plan copies each leaf's dispositions, owned files, tests, and stop conditions into the unit brief. The briefs paraphrase a goal and test scenarios. They do not paste the leaf acceptance criteria, verification blocks, or stop conditions. A global sentence says units "inherit" them.

**Evidence.**

- #814: "the run-wide plan copies each leaf's dispositions, proportionality constraint, owned files, tests, and stop conditions into its unit brief"; "Each leaf's own stop conditions, pasted into its unit brief."
- Plan R1 claims that copy happened.
- U6 leaf stop conditions (not in the U6 brief): stop before launch if wrapper dry-run does not resolve cwd and workspace; stop before prompting if Herdr cannot verify kind/model/effort/permissions/pane/readiness; stop rather than silently substituting; stop cleanup if ownership cannot be proven.
- U8 leaf stop conditions (not in the U8 brief): stop before launching when a reviewer is not in the Orchestrate run record; stop before submitting when Herdr cannot verify vendor/model/effort/worktree/pane; stop rather than falling back to `engine_session_runner` or inventing a custom review; block landing until the typed result is terminal.
- U8 required-behavior list is fourteen bullets. The plan points at it as a "PR body checklist" and does not paste it.
- U7/U10/U11 verification commands in the leaves (`pytest -k`, `rg`, `python3 scripts/check_docs.py`, live Stage/Status) are not reproduced as the unit's Verification block. The global "run the leaf's Verification block" is a pointer, not a copy.

**In-scope failure mode.** Process execution (U6) and reviewer transport (U8). Without the stop conditions in the brief an unattended worker that is handed the plan section as the task can skip fail-loud stops and silently substitute a model, effort, or launch path, or fall back to the runner U8 is deleting.

**Suggested repair.** Paste each leaf's Acceptance criteria, Verification, and Stop conditions (or "none — leaf has no stop-conditions section") under that unit. Keep the plan's HOW (smallest fix, reuse, rejected alternative) above them. For ACs this review already substitutes (U4 `pytest -k mirror`, U10 `check_docs.py`, U11 `workflow_emitter.py` rg, U7 Stage live-check), put the substitution next to the pasted AC so the worker does not run the stale command.

---

### F6 — KTD2's mermaid-cli fallback re-authorizes the rejected heavy path

**Severity:** P2

**Exact claim.** KTD2 rejects `@mermaid-js/mermaid-cli` as disproportionate (puppeteer/chromium, hundreds of MB, slow, flaky; rendering is not needed to parse), then authorizes that same package as the bounded fallback "if headless `mermaid.parse()` proves infeasible."

**Evidence.**

- Plan KTD2 and U2 "Rejected alternative" vs "Bounded fallback".
- Leaf #405 out-of-scope: no validator framework; one syntax check.
- No `package.json` on `origin/main`. The Node helper, mermaid pin, and DOM shim are all new moving parts. The named current failure (13 broken diagrams at `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:148-149`) justifies a real parser, not a browser renderer.

**Suggested repair.** Delete mermaid-cli from the authorized fallback. If headless `mermaid.parse()` is infeasible at the pinned version, HALT and return that evidence; do not silently swap in a browser renderer. The operator already removed validator frameworks from this leaf.

---

### F7 — U2 does not pin Node, mermaid, or CI wiring

**Severity:** P2

**Exact claim.** U2 specifies `scripts/check_mermaid.py` shelling to a pinned Node helper calling `mermaid.parse()` headless with a DOM shim, plus a new Lint-job step. It does not name the pin file, the mermaid version, the DOM shim, whether CI needs `actions/setup-node`, or the exact `gate.sh` step name the coverage self-check will look for.

**Evidence.**

- Plan KTD2 and U2 "Smallest viable fix" / "New moving part".
- `origin/main` has no root `package.json`. Lint job (`.github/workflows/ci.yml:167-216`) has Python/uv only.
- `scripts/gate.sh:18-23`: a CI-blocking step cannot be advisory in the gate. Open question 2 already flags local Node-missing as exit 3.

**Suggested repair.** Pin in the unit brief: add `actions/setup-node` (or equivalent) in the same Lint job; a root or `scripts/`-local pin file with an exact mermaid version; the DOM shim library named; `gate.sh` step text that will match `ci.yml` so `GATE INCOMPLETE` cannot be "fixed" by renaming. Node missing locally stays exit 3, matching existing missing-dev-dependency semantics. Do not invent a second package manager.

---

### F8 — U1/U4 verify-and-close vs the parent's merged-PR close-out

**Severity:** P2

**Exact claim.** KTD1/R10 close #792 and #725 with evidence comments and no PR. #814 close-out and acceptance criteria still say each retained child is closed with merged-PR evidence, or parked-and-named.

**Evidence.**

- Plan Open questions item 1; KTD1; R10. This review reran U1's two COLUMNS commands (13 passed) and confirmed U4's surface is gone.
- #814 AC: `gh issue view <n> --json state,closedByPullRequestsReferences` shows `CLOSED` with its merged PR.
- Historical fixes: PR #790 / `6396455a` for #792; `84e53a72` for #725. Neither is a PR of this run.

**Disposition taken (do not mint no-op PRs).** Close each leaf with an evidence comment naming the fixing commit, the launch-pin rerun receipts, and why a no-op PR would churn a sole-writer surface. Parent close-out names those historical SHAs under U1/U4 rather than claiming a run PR. If GitHub will not attach `closedByPullRequestsReferences` to a historical PR, disclose that parent-AC substitution in the #814 closing comment. Contingency paths in the plan (U1 test-only diff; U4 successor-mirror) stay.

---

### F9 — Locked lens sets miss one warranted conditional on four units

**Severity:** P2

**Exact claim.** Decision row 7 makes this review the last chance to correct the locked set. Four units are one conditional short of the roster trigger. Adding them later from a code-review session would require returning to the operator.

**Evidence.**

- Roster `plugins/saga/references/lens-roster.json`: `adversarial` triggers on agent orchestration or a large/complex diff; `api-contract` on CLI/exported-type changes; `agent-usability` on skill/command text an agent must follow; `reliability` on failure handling, retries, cancellation.
- U6 is the launch extract (leaf failure modes: silent substitution, wrong workspace, unowned cleanup, duplicate session). Always-on security and `reliability` cover part of it; `adversarial` is the roster's named lens for agent-orchestration assumption and silent-green paths.
- U7 adds a field-named op-kind only if F3 is rejected; that is an interface contract (`api-contract`). If F3 stands, skip this add.
- U10 phase B, once G1 NARROW is implemented in-run, edits `plugins/saga/skills/plan/SKILL.md` and `work/SKILL.md` — `agent-usability`.
- U11 after G3 is fail-loud vs silent native fallback — `reliability` in addition to `api-contract`.

**Suggested repair.** Amend the predeclared-lens table per the lens section above. Do not add `performance`, `privacy`, `accessibility-human-usability`, or extra reliability on U3/U5. Do not add `adversarial` on U8 on top of the three conditionals already there.

---

### F10 — U6's brief omits the new plugin's release surfaces

**Severity:** P2

**Exact claim.** U6 describes the extract into `plugins/agent-launcher/skills/agent-launcher/scripts/` and the orchestrate deletion. It does not list `plugins/agent-launcher/.claude-plugin/plugin.json`, `CHANGELOG.md`, marketplace registration, or `scripts/validate_plugins.py` / release-surface parity. R3 says every plugin PR touches `.claude-plugin/marketplace.json`.

**Evidence.**

- Plan U6 "Smallest viable fix" file list vs leaf "Files expected to change" (plugin.json, skills, scripts, tests, marketplace/changelog/validation).
- KTD6 correctly rejects `tools/create-plugin.sh`'s `src/` default in favor of `skills/<name>/scripts/`. That layout decision should stay.
- Collision surface: marketplace.json is merge-serialized with re-bump at merge. Omitting it from the brief is how a worker ships a plugin that CI's parity check then reds.

**Suggested repair.** Add the new plugin's `plugin.json`, CHANGELOG, tests path, marketplace entry, and the existing parity checks to U6's owned files. Keep orchestrate's release surfaces in the same PR because orchestrate behavior moves. Do not invent a second marketplace writer.

---

### F11 — 13-broken-diagram citation is off by one heading

**Severity:** P3

**Exact claim.** U2 names `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:187` as the 13-broken-diagram incident. On `origin/main` that sentence is at `:148-149`. Line 187 is "immutability; all §5 QUEUED items; …". The incident is real; the pointer is copied from leaf #405.

**Suggested repair.** Cite `:148-149`. Do not treat the incident as unverified.

---

### F12 — `backend: inline` is not a decision-table row

**Severity:** P3

**Exact claim.** KTD9 says all eleven units execute inline "per the operator-decision table". The #814 table has eight rows. None is an execution-backend row. The run-opened comment on #814 told S1 to record inline. Orchestrate's `launch(..., backend: str = "inline")` at `orchestrate.py:1942` is the driver's default.

**Disposition taken.** Keep `backend: inline` in frontmatter. It matches G1 NARROW (this run is Herdr/Orchestrate sessions, not cc-workflows as the default Saga backend). Reword KTD9 to "recorded from the launch prompt and the Orchestrate default, not a ninth decision-table row."

---

### F13 — Two stale line and job-name citations

**Severity:** P3

**Exact claim.** U9 cites judgment-selection text at `code-review/SKILL.md:45-50`; the always-on / judgment-select paragraph starts at `:48`. U3 cites "Release Surface Parity job (`ci.yml:159`)"; `:159` is the step "Journal newest-first guard (new entries)" inside the job that also runs the release-surface bump, not a job named Release Surface Parity. Lint-job `:215` is correct.

**Suggested repair.** Re-anchor at launch pin. No behavior change.

---

## Operator questions (none blocking; dispositions already taken)

1. **G1/G3 NARROW vs the original HALT text.** Disposition: live 2026-08-25 comments win (F1, F2). S3 restates them in the U10/U11 briefs. Do not re-ask the four-way choice or the chaperone-vs-reject choice.
2. **No-PR closures for U1/U4.** Disposition: verify-and-close (F8).
3. **#812 Stage ACs vs a board with no Stage field.** Disposition: Status-only; do not create the field (F3).
4. **Retaining `engine-registry.yaml`.** Disposition: keep as explicitly non-transport (KTD4). The leaf's "no new vendor/model registry" forbids launch authorities, not calibration data with 17 script consumers.
5. **Node on the local gate for U2.** Disposition: CI-blocking implies gate-blocking (F7). Do not mark the step advisory.

## Residual risk from limited evidence

Grok reasoning-effort tokens `high`/`xhigh` were composition-validated at S0, not by this session. That is S0's disclosed residual, not a plan defect.

U8's "18 of 49 tests in `tests/test_saga_second_opinion.py` load the transport modules directly" was not re-counted test-by-test (`test_engine_offer.py` has 23 tests; the second-opinion file has 49). The tests-deleted-with-code allowance stands regardless of the exact split.

Live Stage/Status field discovery used this machine's authenticated `gh` against the live Operations/Asgard/CAMPPS projects. If a fourth project this repo writes has a Stage field, U7's inventory step will see it at the launch pin; F3's "do not create a field" still holds.

This review did not re-run `scripts/gate.sh` or the full suite; U1's two COLUMNS commands were rerun and passed.
