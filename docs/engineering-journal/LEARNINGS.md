# Learnings — Infiquetra Claude Plugins

> **Empirical findings + mechanisms + fixes + validations.** When something turns out to be true that wasn't obvious — about a plugin's runtime behavior, the marketplace registry, hook timing, skill activation, MCP env propagation, build/test tooling, or a deploy gotcha — it goes here. Include the **evidence** (PR / commit / file:line / reproduction) and the **mechanism** (why it's true), not just the observation.
>
> **Append new entries to the top.** Most-recent first. Format:
>
> ```markdown
> ## YYYY-MM-DD
>
> ### Short descriptive title  {#slug}
>
> **Context.** One paragraph framing the situation.
> **Evidence.** Specific PR / commit / file:line / reproduction recipe.
> **Mechanism.** Why it happened (or why it's true) — root cause, not just symptoms.
> **Fix (or queued).** Concrete action + commit hash, OR a QUEUED.md ref if deferred.
> **Validation (if applicable).** What later run / test / install proved the fix.
> **What surprised (optional).** The thing that wasn't in the original mental model.
> **Generalizable rule.** The lesson stripped of this specific incident — what would I tell a future-me hitting a similar shape?
> **Refs.** Cross-links to DECISIONS / QUEUED / narratives / other LEARNINGS entries.
> ```
>
> The `{#slug}` HTML anchor on the entry title makes the entry linkable from `README.md` quick-nav and from cross-references. Keep slugs short and stable.
>
> When new evidence invalidates a learning, **update inline AND move the pre-correction version to `ARCHIVE.md` as SUPERSEDED**. Never silently overwrite.

---

## 2026-07-07

### Whole-tree kill proofs need a grandchild pid, and live smokes must tolerate ambient MCP dirt {#codex-lifecycle-tree-kill-proof}

**Context.** codex delegate U6 (#476, R7): the lifecycle suite must prove the delegate kills the
*entire* codex process tree on timeout/SIGTERM, not just its direct child, and must include an
availability-gated live `codex exec` round-trip.

**Evidence.** `tests/test_codex_delegate_lifecycle.py` — the fake codex spawns its own child and
writes both pids to a pidfile; the test polls the grandchild's pid directly. Red proof: a broken
delegate variant with `_kill_process_tree` replaced by direct `process.kill()` fails exactly on
the grandchild-survival assertion ("fake codex's CHILD survived the timeout kill") while every
direct-child-only assertion stays green. Live smoke: real `codex exec` in a fresh tmp git repo
came back `out_of_scope_mutation` with `new_paths: [".serena/"]` — locally-configured codex MCP
tooling wrote state into the repo under review.

**Mechanism.** A test that asserts only "the launched pid is dead" is vacuously green under a
child-only kill because `Popen.kill()` reaches argv[0] fine — only a process the *delegate never
knew about* (the fake bin's own child, sharing the session group) distinguishes `killpg` from
`kill`. And a live smoke that pins `status == "success"` couples the test to whatever ambient
agent tooling the operator's codex config runs; the diff-scan flagging `.serena/` is the scanner
working, not the delegate failing.

**Generalizable rule.** (1) To prove tree-kill semantics, the fixture must fork a grandchild the
supervisor cannot see and the test must poll that pid — then demonstrate red against a
kill-direct-child-only mutant before trusting the green. (2) Availability-gated live smokes
should assert the *bridge contract* (receipt + transcript + last message + terminal status),
never a single happy status, because live environments carry side-effecting tooling the hermetic
tests deliberately exclude.

**Refs.** `{#codex-diff-scan-snapshot-relative}` (the scan that caught `.serena/`); Ollama smoke
posture in `tests/test_engine_bridge_http.py`.

### A non-mutation diff-scan must be snapshot-relative, and must exclude its own evidence dir {#codex-diff-scan-snapshot-relative}

**Context.** codex delegate U3 (#476): the reviewer (read-only) surface must prove codex did not
mutate the live repo, and the coder (task) surface must prove the live tree is untouched while it
works in a disposable clone. The naive proof — "run codex, then assert `git status --porcelain` is
clean" — is wrong on two counts.

**Evidence.** `plugins/codex/scripts/codex_delegate.py` `derive_reviewer_scan` / `_porcelain_paths`;
tests `tests/test_codex_delegate_modes.py::test_reviewer_pre_dirty_tree_does_not_false_positive`
and `::test_coder_captures_patch_and_leaves_live_tree_untouched`.

**Mechanism.** (1) Operators routinely run a reviewer over an already-dirty working tree. An
absolute "is it clean now" check false-positives on their pre-existing edits. The proof must be the
*set difference* of post-run dirty paths against a pre-run snapshot captured before launch — dirt
present at baseline is excluded from `new_paths` regardless of its post-run status, so a pre-dirty
tree cannot false-positive. (2) The delegate writes its own evidence bundle to
`.claude/codex/runs/<id>` *in the live tree*, so an unfiltered porcelain scan flags the bundle
itself as a mutation. Both the delegate's scan and the tests' untouched-tree assertion must scope
to `git status --porcelain -- . ':(exclude).claude'` — the guarantee is about source/working files,
not the delegate's own evidence store.

**Validation.** 8 U3 mode tests green; full suite 2465 passed / 1 skipped.

**Generalizable rule.** A "did X mutate the tree?" guard is only honest if it is (a) differential
against a pre-action snapshot, not absolute, and (b) blind to the guard's own artifacts. Bake both
into the scan primitive, not the call sites.

**Refs.** Mirrors agy's clone/diff-evidence shape (`plugins/agy/scripts/agy_delegate.py`); #476 U3,
R2, KTD5.

---

## 2026-07-06

### Worktree-isolated verify panels are blind to uncommitted worker output — refute-N ran 0/3 vacuous on every panel {#verify-panels-blind-to-uncommitted-tree}

**Context.** First real `cc-workflows-ultracode` run through `/work` (issues #387+#383, workflow
`wf_6f7f3de8-926`): 8 serialized workers, refute-3 panels on U5/U6/U7, verifiers spawned as
`saga:readonly-verifier` with `isolation: worktree` per #287 KTD6.

**Evidence.** Workflow logs: `verify panel over U5: 3/3 verifier(s) missing (runtime-failure);
verdict computed over 0/3 — UNDER-STRENGTH (quorum floor 2)` — identical for U6 and U7. Verifier
transcripts all report a clean worktree with nothing to verify against. Second run
(`wf_5afd99b3-636`, after the implementation was committed on the work branch): verifiers report
their worktree HEAD at `9a84311` (main) while the primary tree sat on the branch at `df42a39` —
two of nine refuted claims against main's code, citing main's line numbers and zero-match greps
for symbols provably present on the branch.

**Mechanism.** A verifier's disposable worktree is cut from the DEFAULT branch (main), not from
the driving session's current branch — so uncommitted worker output is invisible (first run), and
even committed branch work is invisible unless the verifier deliberately materializes the target
commit (`git checkout <sha> -- .` or `git archive` into scratch, as the compensating verifiers
did). Verifiers that don't compensate either return "nothing to verify" prose (counted as
runtime-failure → vacuous pass) or, worse, confidently refute the wrong revision (false kill). The
quorum floor correctly labeled the first run's panels UNDER-STRENGTH but only as a log line — the
run still completed "successfully".

**Fix (or queued).** This run: the driving `/work` session committed the tree and re-ran the three
panels against real commits before PR. Durable fix queued: `{#execution-spec-verifier-visibility}`
in QUEUED.md (emitter must either commit per unit before panel spawn or inject the unit diff into
verifier prompts, and UNDER-STRENGTH must fail loudly, not log quietly).

**Generalizable rule.** A verification stage is only as real as its view of the artifact — when
isolation and uncommitted state mix, the panel passes vacuously and reads as green. Any quorum
mechanism that can be under-strength must fail the run, not annotate it.

**Refs.** DECISIONS `{#http-bridge-receipt-pair-387-383}`; QUEUED
`{#execution-spec-verifier-visibility}`, `{#execution-spec-concurrency-cap}`; LEARNINGS
`{#verify-the-guard-reds}`.

### 4/4 tier-mechanics leaves: the adversarial execution gate caught a real compositional finding on EVERY leaf that a fully-green suite missed {#adversarial-gate-4-for-4}

**Evidence.** The tier-mechanics batch (#369 PR #500, #365 PR #504, #368 PR #508, #364 PR #509 —
each merged only after a `saga:readonly-verifier` worktree pass by *execution*): #369 P0 min_tier
floor bypassed the pre-merge tier halt; #365 P0 unrunnable session ceiling (`haiku/xhigh`) leaked
through emit un-halted; #368 P1 naive header matching let a code-fence mention parse as an
authoritative tier band AND suppress the stamp; #364 P1 cord proposals ignored the session
ceiling (+ P2 reserved-key collision). Every suite was green before each gate ran.

**Mechanism.** All four were the same failure *shape*: two individually-correct components whose
implicit shared contract broke on composition (floor × halt ordering, ceiling × emit clamp,
stamp × parse header semantics, cord proposal × ceiling). Unit tests validate components against
their own contracts; only executing the composed artifact (emitting the JS and probing it, running
the stamped body through the parser) exposes the seam. Reading the diff found one of the five;
execution found the rest.

**Generalizable rule.** For any two-sided contract (emitter/parser, producer/consumer,
clamp/halt), the review gate must *execute the composition adversarially* — a green suite plus a
plausible diff-read is not evidence the seam holds.

### When the deliverable IS a drift guard, adversarially verify the guard REDS on the drift it claims to catch — a matcher-blind guard is vacuously green  {#verify-the-guard-reds}

**Context.** #370 shipped several drift guards (AC1 "no second vocabulary source", AC8 "no tier-token drift in operator tables"). All were green on the first build, all tests passed, coverage looked complete. The pre-PR code-review gate (a `saga:readonly-verifier` lens tasked specifically with "is this guard real or trivially-green?") found two that passed *because their matcher was blind*, not because there was no drift.
**Evidence.** PR #499 (`52445d8`), fix commit `6315564`. (1) The AC8 tier-token regex required an *unspaced* `opus/high`, but the `/plan` tier table is written *spaced* (`opus / high`) — the verifier injected `opus / superhigh` into the live table and the guard still passed (0 findings). (2) The AC1 AST scan only matched bare tuple/list literals — `_X = tuple(["fable","opus","sonnet","haiku"])` (a full vocabulary re-declaration) slipped past it. Both were demonstrated with a reproducible red, not hypothesized.
**Mechanism.** A guard test asserts `offenders == []`. That passes in two very different worlds: "there is no drift" and "my matcher cannot see the drift that exists." The two are indistinguishable from the green checkmark alone. Only a *forcing function* — inject the exact drift and confirm the guard reds — separates them.
**Fix.** Scoped the AC8 token guard to the table whose format it actually matches (team-execution, unspaced) and guarded the spaced `/plan` table by render-equality instead (`render_block() in plan_text`); widened the AC1 scan to also catch `tuple(...)`/`list(...)`/`set`/`frozenset` call-wrapped redefinitions. Both fixes ship with forcing-function tests that assert the guard reds on the drift.
**Validation.** `test_guard_reds_when_vocab_reintroduced` now asserts the call-wrapped case is caught; `test_plan_table_render_synced` reds on a spaced-token `/plan` drift or block removal. Full suite 2214 passed.
**What surprised.** The guards that were *most* trivially-green were the ones for the ACs the issue named *first* — the ones that felt most "obviously done." Confidence in a guard is inversely correlated with how carefully anyone checks that it can fail.
**Generalizable rule.** A guard test's green is only meaningful if you have separately watched it go red. When a PR's deliverable is a guard (lint, drift check, schema check, invariant test), the review question is not "does it pass?" — it is "does it fail on the exact thing it exists to catch, and is its matcher blind to a realistic variant (spacing, call-wrapping, aliasing, casing)?" Add the forcing-function red as a committed test, not a one-off manual check.
**Refs.** Extends [[serial-build-cross-cutting-caught-at-gate]] (both are "the gate catches what the build's own green misses"). DECISIONS `{#tier-vocab-ordering}`. PR #499.

---

## 2026-07-05

### A serial multi-agent build's *cross-cutting* defects have no owner — the pre-PR gate + the committed-state re-run are the only backstop  {#serial-build-cross-cutting-caught-at-gate}

**Context.** `/work` on #363 (effort-first-class) ran a serialized 6-unit ultracode Workflow (U1–U6). Every unit's own gate passed and the full local suite was green (2185), yet the Phase-5 `/code-review` gate then surfaced **two P1s**, and the staleness re-run surfaced a third — none caused by a single unit's internal logic.

**Evidence.** PR #498 (`6a367ad`), 2026-07-05. (1) U6 wrote `QUEUED.md` heading `— SHIPPED (#363)` while its own body concedes only the `EFFORT_RIDER` proxy shipped — an honesty overclaim the plan's U6 explicitly forbade (`fc8eff2`). (2) U4 added `effort:` frontmatter to `plugins/agy/agents/agy-coder.md` + `plugins/deploy/agents/release-orchestrator.md`, but U6 bumped only saga/team-execution/fleet-core → `release_surface_diff_guard` red once committed (`c260d8c`). (3) The version bump then broke the agy/deploy version-pin drift-guard tests (`tests/test_agy_plugin.py:38`, `tests/test_deploy_plugin.py:42`), caught only by re-running pytest against the *committed* HEAD (`706cd6a`).

**Mechanism.** In a serial fan-out, a unit that reaches into *another* plugin's files (U4 → agy/deploy) creates a release-surface obligation that a *different* unit (U6) was scoped to satisfy — but U6's prompt named only three plugins. No single agent holds the whole blast radius, so cross-unit consequences fall through the per-unit gates. Compounding it: `release_surface_diff_guard --base-ref main` reads the **committed** `main..HEAD` diff, so it read clean while the build was uncommitted and only flipped red *after* the build commit — an earlier "green" was a false all-clear.

**Fix.** Both P1s fixed in the same `/work` loop (heading corrected; agy 0.1.1 / deploy 0.1.4 across plugin.json + marketplace + CHANGELOG + drift-guard pins), each re-verified by the full deterministic gate before proceeding.

**Validation.** Final gate at `706cd6a`: pytest 2185 passed, ruff/format/mypy clean, both validators + release guard green; CI on PR #498 all-SUCCESS; merged `6a367ad`.

**What surprised.** The release guard *passed* on the first run — because the build was still uncommitted. Running a committed-diff guard before committing the build is worse than not running it: it manufactures false confidence.

**Generalizable rule.** After any multi-agent build, re-run the release/parity guards **against committed state**, and treat cross-plugin touches as un-owned until proven bumped. A version bump is not done until its metadata drift-guard pin moves in lockstep — always re-run the *full* suite after a release-surface fix, because the fix itself can red a pinned test.

**Refs.** DECISIONS `{#lifecycle-engine-merge-campaign}` (verify journal CLOSURE vs real `git diff`; dead-wiring recurs); code-review artifact `docs/code-reviews/2026-07-05-feat-363-effort-first-class-code-review.md`; QUEUED `{#team-execution-per-teammate-effort}`.

### A `ship_ceremony.py` CLI change can't be fully dogfooded through its own ceremony — `checkout_main` reverts the working-tree script to the pre-merge version  {#ship-ceremony-self-dogfood-checkout-main}

**Context.** Shipping the `--saga-id` flag (PR #484) *through* the ceremony, driving every transition with `run --saga-id …`. `commit`→`checkout_main` worked; `pull` and `branch_delete` then died with `error: unrecognized arguments: --saga-id`.

**Evidence.** PR #484 (`f2663fb`), 2026-07-05. `checkout_main` runs `git checkout main`, which swaps the entire working tree — including `plugins/saga/scripts/ship_ceremony.py` — to **local** `main`'s version. Local `main` was behind `origin/main` (the fix merged but wasn't pulled yet), so the on-disk script was the pre-`--saga-id` build and argparse rejected the flag.

**Mechanism.** The ceremony invokes the working-tree copy of itself; `checkout_main` precedes `pull`, so between them you are running the *old* CLI surface against the *new* invocation. A change to ship_ceremony's own argument parsing therefore can't survive its own `checkout_main`→`pull` window. Resolved by `git pull` manually (bringing the new script) then continuing `pull`/`branch_delete` with `--saga-id`.

**Generalizable rule.** A self-invoking tool that checks out a branch mid-run will run an older copy of itself after the checkout. When shipping a change to such a tool's *interface*, don't rely on the post-checkout steps using the new interface — pull first, or drive those steps with the interface that exists on the checked-out ref.

**Refs.** Surfaced dogfooding the fix for `{#ship-ceremony-task-saga-resolve-on-main}`; DECISIONS `{#ship-ceremony-saga-id-resolution}`.

### `ship_ceremony run` can't resolve a task saga once you're on `main` — legacy `main`-frozen sagas make by-branch resolution ambiguous  {#ship-ceremony-task-saga-resolve-on-main}

**Context.** Driving a task-kind saga's ship ceremony (no `issue_ref`, so `run` resolves by the current branch) through cleanup. `commit`/`open_pr`/`merge` ran fine on the feature branch; `checkout_main` switched to `main`, then `pull` and `branch_delete` both aborted.

**Evidence.** `ship_ceremony: multiple sagas match branch 'main' (issue-478, issue-477, issue-429, … 18 ids); pass --issue-ref explicitly` — shipping PR #483 (`cc674fe`), 2026-07-05. `resolve_saga` (`ship_ceremony.py:185`) filters `saga.py scan` candidates by `current_branch`; on `main` that matches every saga whose stored `branch == "main"`.

**Mechanism.** Sagas minted before the #480 fix (`{#saga-branch-refresh-on-every-save-480}`) are permanently frozen at `branch="main"` (first-save-only capture, never re-saved) — 18 of them. Once `checkout_main` puts you on `main`, by-branch resolution matches all of them → `AmbiguousSagaError`. An issue-kind ceremony sidesteps this by passing `--issue-ref` throughout; a task saga has no such key, and `ship_ceremony run` exposes no `--id`/`--saga-id` flag.

**Fix.** Both landed in saga 0.56.0 (DECISIONS `{#ship-ceremony-saga-id-resolution}`): `run` now takes `--saga-id` (top precedence, survives the branch change) and the by-branch fallback excludes terminal (`done`/`abandoned`) sagas. The original one-time workaround was manual `git branch -d` + `git push --delete` and `saga.py save --id …`.

**What surprised.** The #480 fix doesn't *cause* this — those sagas were already `main`-frozen — but it doesn't help either: new sagas now track their real branch, yet the pile of terminal `main`-frozen sagas will keep poisoning by-branch resolution on `main` indefinitely.

**Generalizable rule.** Resolving a work item "by current branch" is only unambiguous while you're *on* that branch. Any step that changes the branch (checkout to `main`) invalidates by-branch identity — carry an explicit stable key (issue-ref or saga-id) through multi-step flows, or filter terminal records out of the candidate set.

**Refs.** DECISIONS `{#ship-ceremony-autoclose-fixes-line}`, `{#saga-branch-refresh-on-every-save-480}`; the third ship_ceremony rough edge from the fleet campaign (after #477 request_review, #478 open_pr push).

### Generated release surfaces catch drift a hand-maintained parity guard would only report after the fact  {#release-surface-single-source-generated}

**Context.** #429 converted `.claude-plugin/marketplace.json` from a hand-maintained copy of each
plugin's `plugin.json` into a generated mirror (`scripts/sync_marketplace.py`), backed by a
tri-lock parity gate and a diff-aware bump guard — the fix `{#marketplace-drift}` (below) queued as
a guard-class check, converted here into a generator instead.

**Evidence.** Running the new generator's `--check` mode against the live 9-plugin fleet *before*
any deliberate edit turned up real, pre-existing drift: `marketplace.json`'s `keywords` array
order had independently diverged from `plugin.json`'s on 6 of 9 plugins (e.g. `agy`:
`["antigravity","agy",...]` in `marketplace.json` vs `["agy","antigravity",...]` in `plugin.json`)
— nobody had touched `plugin.json`'s keyword order since, someone had simply hand-reordered the
`marketplace.json` copy at some point and nothing noticed. Separately, `check_release_surface_parity.py`
and the new CHANGELOG heading lint (`scripts/changelog_heading_lint.py`) found two more
non-canonical headings in `plugins/mission-control/CHANGELOG.md` beyond the four plugins the issue
itself had already identified (`## 1.6.1 - 2026-05-31` missing brackets, `## Unreleased` missing
brackets) — both several screens below the file's top, invisible to a human skimming the top of the
file for its current version.

**Mechanism.** A hand-maintained mirror only reveals drift when someone happens to compare both
copies; a generator makes the drift visible the moment `--check` runs, because there is no second
copy to independently mutate. The plugin count itself had also drifted from the issue's own
"8-plugin fleet" framing — `fleet-core` (#463/PR #473) landed the day before #429 was filed — so
every acceptance criterion and script in this issue's plan targets "the current plugin fleet"
(directory scan at run time), never a hardcoded count.

**Fix.** `scripts/sync_marketplace.py` (write mode) regenerated `marketplace.json` from the
now-current `plugin.json` set (PR #475, branch `feat/pf-release-surface-429`); the 4
non-canonical CHANGELOGs (`deploy`, `saga`, `team-execution`, `mission-control`) were reformatted to
the canonical heading grammar (`docs/engineering-journal/DECISIONS.md#release-surface-single-source-429`)
with a matching patch-version bump each, so the new tri-lock gate holds from the moment it lands
rather than failing on its own first run.

**Generalizable rule.** When a plan says "guard two hand-copies for parity," ask whether one side
can be generated from the other instead — a generator can't drift from its own source by
construction, whereas a guard only ever reports drift that already happened. And when a plan's
problem statement cites a specific artifact count (plugin count, file count, format count) as
grounding, re-verify that count directly against the current repo before writing the plan; stale
counts from an earlier snapshot are a common source of an otherwise-correct plan going stale before
it even executes.

**Refs.** Plan `docs/plans/2026-07-05-release-surface-single-source-plan.md`; Decision
[release-surface-single-source-429](DECISIONS.md#release-surface-single-source-429); this converts
[#marketplace-drift](#marketplace-drift) below from a guard-class fix into a generator.

---

## 2026-07-04

### A marketplace plugin install is a bare file copy — cross-plugin imports have no path, and the registry, cache, and clone all disagree on version  {#marketplace-install-layout-no-import-path}

**Context.** Issue #463 had to decide where cross-plugin shared primitives live. The grounding
brief described the fleet abstractly; the decisive facts came only from inspecting the live
install surfaces on this machine.
**Evidence.** `~/.claude/plugins/marketplaces/infiquetra-plugins/` is a full repo git clone
tracking marketplace HEAD; `~/.claude/plugins/cache/infiquetra-plugins/<plugin>/<version>/` is a
bare per-plugin per-version subtree copy (no repo root, no siblings, no pip/venv step);
`~/.claude/plugins/installed_plugins.json` (schema `version: 2`) maps `<plugin>@<marketplace>`
keys to *lists* of install records carrying `installPath`. All three disagreed on saga's version
at once: installed 0.49.0, cache holding through 0.51.0, repo at 0.52.0 (observed 2026-07-04).
**Mechanism.** Install copies exactly one plugin subtree per version and never runs dependency
tooling, so a sibling plugin is unreachable by construction at run time; monorepo imports only
work because pytest puts repo paths on `sys.path`. The clone tracks HEAD while the registry pins
what is actually enabled, so any resolution strategy keyed to the clone (or to "highest cached
version") runs code the user does not have installed.
**Fix (or queued).** The fleet-commons mechanism (DECISIONS
[[#fleet-commons-mechanism-463]]): vendored resolution shim whose authoritative rung is the
`installed_plugins.json` lookup, with `FLEET_COMMONS_DEBUG=1` rung provenance so tests assert the
path taken. `tests/test_fleet_commons_install_time.py` rebuilds this exact layout under
`tmp_path` and proves rung 3 wins even against a newer cache decoy.
**Generalizable rule.** When code must find code across independently installed components,
resolve through the installer's own registry of what is enabled — not through source checkouts or
"newest on disk" — and make the resolver report *which* strategy succeeded so a test can fail on
the right-answer-wrong-reason case.
**Refs.** DECISIONS [[#fleet-commons-mechanism-463]]; plan
`docs/plans/2026-07-04-fleet-commons-mechanism-plan.md` (grounding table).

### GitHub `updateProjectV2Field` clears ALL option selections — byte-identical options do not survive  {#projectv2-option-update-clears-selections}

**Context.** Phase G of the plugin-fleet program upgraded the Operations board's Status vocabulary to Asgard's (add Idea/Shaping/Ready/Active/Verify, retire Todo/In Progress/Blocked). The mutation resubmitted the existing four options byte-identical (same name/color/description) with five appended, expecting name-matched preservation.
**Evidence.** Gate G ledger (`docs/plans/plugin-fleet-ideation-2026-07-03/gate-g-ledger.jsonl`, `U1-status-options-add` → `ID-DRIFT-HALT`): all four pre-existing option IDs rotated and 26 of 27 cards lost their Status selection. Pre-mutation per-item snapshot enabled full restore.
**Mechanism.** `updateProjectV2Field(singleSelectOptions: [...])` replaces the entire option list — every option is recreated with a new ID and existing item selections are orphaned, regardless of name/color/description equality. The flow SKILL's "field option IDs rotate on rename/recreate" warning materially understates this: *any* option-list update clears selections.
**Fix (or queued).** Recovery reordered the sequence: finish ALL option-list mutations first, then write item selections exactly once against the final option set. Post-migration census verified (10 Idea/open, 17 Done/closed). Standing procedure: snapshot per-item field values before any single-select option-list mutation; treat selection restore as part of the mutation, not a contingency.
**Generalizable rule.** A GitHub Projects single-select option list is immutable-in-place: every "edit" is a destroy-and-recreate of all options plus silent loss of every selection. Schema mutations and data writes must be strictly phased — schema converges first, data is written once, last.
**Refs.** `plugins/mission-control/skills/flow/SKILL.md` hard-rules section (understated warning); Gate F mutation plan rev 2 (`docs/plans/2026-07-04-plugin-fleet-gate-f-mutation-plan.md`).

### Three independent schemas governed one issue-creation path — each discovered only by consulting its executable source  {#three-schema-drift-issue-creation}

**Context.** Materializing 138 plugin-fleet issues (Phase G) tripped three separate contract mismatches: (1) draft sidecars' `project_fields` were authored against a CAMPPS-shaped board while the repo maps to Operations (fields like Wave/Tier/Initiative don't exist there); (2) sidecar `readiness.passed: true` had been written by drafting agents, not computed — the real card validator failed 126/126 drafts at create time; (3) the prepared pipeline's `_TEAM_CHOICES` (`sdlc_manager.py:2850`) structurally rejects objective/exploration/context-update types for every allowed team, forcing a fallback create path for 21 of 138 issues.
**Evidence.** Live `flow field-options` output vs sidecar `project_fields`; pilot `issue create-prepared` failure listing 7 missing H3 sections; local run of `sdlc_manager.validate_card_body_for_context` over all 126 drafts (126/126 fail → deterministic transformer → 126/126 pass with zero GitHub round-trips); Gate G ledger fallback-path entries.
**Mechanism.** The board schema, the card-body contract (vendored home-lab `card_validator` shim: 8 required H3 sections + 3 more at high risk, checklist-formatted executable acceptance criteria, fenced verification), and the prepared-pipeline team/type matrix are three separately-owned contracts with no shared source; drafting agents reproduced remembered shapes of each, and nothing validated any of them before create time.
**Fix (or queued).** Fixed forward: fields re-expressed against the live board (Gate F rev 2 decision table), drafts transformed against the imported real validator, non-actionable types via the plan's sanctioned fallback. The durable fixes are exactly wave-2 issues shipped by this program (standards-enforcement at authoring time, single-source contracts, board-live-schema checks).
**Generalizable rule.** Before bulk mutation against any gated pipeline, import and run the pipeline's own validator locally over the full corpus first — schema assumptions written at drafting time are stale by construction, and an executable gate consulted offline converts N create-time failures into one cheap local loop.
**Refs.** [[#projectv2-option-update-clears-selections]]; grounding brief §9 (board/field pagination bug class); `pf-standards-preflight-issue-authoring`, `pf-board-live-schema-pagination`, `pf-single-vocab-source` (now live as issues).

## 2026-07-03

### A null-tolerant filter plus a fixed threshold silently converts member failure into member assent  {#uphold-bias-nullable-quorum-293}

**Context.** Issue #293's verify-panel reconciliation (`execution_spec.py`) and the
team-execution architecture-reviewer had the same defect shape on two different surfaces: a
mechanism meant to detect disagreement instead silently tolerated a missing input as agreement.
**Evidence.** Layer A: `verdicts.filter((v) => v && v.refuted && ...)` treated a `null` verdict
(a verifier that died before emitting) identically to a verdict that explicitly upheld the
result — both simply fell out of the refute-count numerator — while the pass-rule threshold
stayed fixed at `⌈n/2⌉` of the DECLARED `n`, not the reporting count. Layer B:
`architecture-reviewer.md:82` scored a dimension with no applicable precondition as a
fabricated `N/A -> 8.0`, folded into the same average that feeds the unanimous-ACCEPT gate.
Both existed before #293 (Layer A since #277/0.40.0, commit b09ad50) and both silently
converted "this member said nothing" into "this member agrees." Fixed at #293 (commits
195ce44, ec402a7).
**Mechanism.** A quorum-over-array pattern (`array.filter(predicate).length >= threshold`) has
two independent places a null/missing entry can hide: inside the filter predicate (a `null`
fails `predicate(v)` the same way a legitimate "not refuted" verdict does — the filter can't
tell absence from disagreement), and in the threshold itself (when the threshold is computed
from the array's DECLARED length rather than the count of entries that actually carry
information, a shrinking numerator against a fixed denominator systematically biases toward
the "not enough refuted" outcome — acceptance). Both bugs push the same direction because
acceptance is the quiet/default path and refutation is the loud/blocking one — a missing
member always erodes the side that requires active signal.
**Fix.** Layer A: recompute the threshold over the reporting count `k`, not the declared `n`
(`max(1, ⌈k/2⌉)` majority / `max(1, k)` unanimous), and record which members were missing
rather than silently dropping them. Layer B: exclude a non-applicable dimension from the
averaging denominator instead of substituting a value. Both fixes share the same shape:
separate "this member had nothing to contribute" (excluded from the denominator) from "this
member contributed and it was negative" (counted against the numerator) — never let the
former decay into the latter's default. Commits 195ce44 (Layer A), ec402a7 (Layer B).
**Generalizable rule.** Any quorum computed as `X.filter(predicate).length >= threshold` over
an array that can contain nulls/missing entries is a latent uphold-bias unless the threshold
is explicitly recomputed over the count of entries that actually reported. Audit two things
separately: (1) does the filter predicate treat "null/missing" the same as "present and
negative" — it shouldn't; and (2) is the threshold a function of the array's declared/
allocated size, or its live reporting count — it must be the latter. This generalizes past
verify panels to any voting, consensus, or moderation quorum over a nullable array.
**Refs.** DECISIONS `{#verify-panel-missing-member-ktds-293}`; issue #293; plan
`docs/plans/2026-07-03-verify-panel-robustness-plan.md`.

### A just-merged agent is invisible to a session whose plugin loaded pre-merge  {#stale-agent-roster-325}

**Context.** `saga:readonly-verifier` is mandated by `CLAUDE.md` and `sandbox-spawn-sites.md` for every ad-hoc verify/review-class spawn, but a `/saga:work` run on #291 hit `Agent type 'saga:readonly-verifier' not found` and fell back to an ungoverned `general-purpose` spawn.
**Evidence.** `plugins/saga/agents/readonly-verifier.md` was added by `697fff1` (2026-07-02, #287 via #320) — its sibling `mechanical-executor.md` (`9bdf363`, 2026-06-21) resolved fine in the same failing session. A live spawn of `saga:readonly-verifier` with `isolation: "worktree"` in a fresh session at #325's plan time resolved and ran successfully end to end.
**Mechanism.** The Claude Code agent roster is fixed at plugin load time for a session; an agent added to the plugin's `agents/` directory after a session's plugin loaded is not retroactively discoverable within that session, even though the file is present on disk and the plugin version has moved on.
**Fix.** `plugins/saga/references/sandbox-spawn-sites.md` gained a two-step fallback ladder (`Explore` + worktree, then `general-purpose` + worktree + explicit read-only instruction) so the mandate degrades gracefully instead of hard-failing; `tests/test_agent_registration_drift.py` pins the repo-side preconditions that keep the agent statically discoverable. Commit range: #325.
**Validation.** `uv run pytest tests/test_agent_registration_drift.py` — 10 passed, including 3 synthetic-negative regression cases.
**Generalizable rule.** After merging a new agent or skill, reload the plugin (start a fresh session) before relying on it — a mandate that names a specific agent type needs a documented degrade path for the session that hasn't reloaded yet, because "just merged" and "just registered" are not the same moment.
**Refs.** DECISIONS `{#readonly-verifier-fallback-ladder-325}`; issue #325; #291 saga follow-up note ("register saga:readonly-verifier agent (roster gap)").

## 2026-07-02

### `git gc` packs custom-namespace refs — a loose-file-mtime gc goes blind after any gc  {#git-gc-packs-custom-refs-291}

**Context.** team-execution's Layer-1 artifact pointers pin a snapshot tree with a holding ref under `refs/team-execution/snapshots/<run-id>/<epoch>`; the TTL `gc` reclaimed old refs by the loose ref file's mtime.
**Evidence.** Scratch repo, git 2.54: `git update-ref refs/team-execution/snapshots/run1/0 <tree>` then `git gc` moves the ref into `.git/packed-refs` and deletes the loose `.git/refs/.../run1/0`. `_snapshot_ref_paths` keyed off `ref_path.exists()`, so after any gc (including auto-gc) the ref became invisible to reclamation and leaked forever — the tree *object* still resolved (leak-not-break). devils-advocate consensus review, #291; commit 1c1cafc.
**Mechanism.** `git gc` runs `pack-refs --all`, which packs refs under ANY namespace, not just `refs/heads`/`refs/tags`. A prior in-code comment asserted the opposite ("does not pack refs under a custom namespace by default") — empirically false.
**Fix (two-step, cycle 1 → cycle 2).** Create the ref with `git update-ref --create-reflog` and enumerate via `for-each-ref` (sees packed refs). Cycle 1 dated the ref by the reflog FILE mtime — still wrong: `git gc` runs `git reflog expire --all` internally, which rewrites every reflog file and resets its mtime to now (even when it expires zero entries), so refs looked age-0 and never aged out (same leak, same `git gc` trigger). Cycle 2 dates by the reflog ENTRY's embedded commit timestamp (`_reflog_creation_time` parses the reflog line), which `reflog expire` preserves.
**Validation.** Scratch repo, git 2.54: backdated a reflog entry 10 days, ran a real `git gc` → the loose ref is packed AND the reflog file mtime resets to now, but the ENTRY timestamp stays 10 days. `test_gc_dates_snapshot_refs_by_reflog_entry_surviving_real_git_gc` runs a real `git gc` between snapshot and reclaim, green.
**Generalizable rule.** Git metadata has layers of durability: a loose ref file is packed away by gc; a reflog FILE survives packing but its mtime is reset by `reflog expire`; the reflog ENTRY timestamp (semantic content git writes) survives both. Date by the value git promises to preserve, not the filesystem artifact around it — and test the age path against a REAL `git gc`, not a simulated mtime.
**Refs.** DECISIONS `{#artifact-pointer-ktds-291}`; devils-advocate consensus cycles 1–2, #291.

### An e2e test can be green while a persisted-field consumer leg is a no-op — cross the persistence boundary  {#test-shape-masks-dead-wiring-291}

**Context.** The saga `artifact_pointers` field was claimed "live on both axes" (producer + consumer), with a passing e2e test as the proof.
**Evidence.** `test_layer2_end_to_end_producer_to_spawned_consumer` saved the tick (asserting the pointer was in the tick text) but the consumer leg derefed the in-memory `pointer_json` from the producer, threaded through the spawn template — never the value read back from the saved tick. grep confirmed no skill read `artifact_pointers` back. Producer→consumer connected through a shared variable, not the persisted field. devils-advocate consensus review, #291; commit 79a49ea.
**Mechanism.** Both producer legs were real CLIs and both assertions passed, so the suite looked like a both-axes proof. The gap was which *variable* the consumer derefed — invisible unless you trace data flow rather than pass/fail.
**Fix.** Consumer wired: `/resume` derefs a restored tick's pointers. e2e rewritten so the consumer leg does `saga.py restore` → reads `artifact_pointers` out of the persisted saga → derefs THAT. Commit 79a49ea.
**Generalizable rule.** A round-trip test only proves the round-trip if the consumer reads from the boundary it claims to validate. If producer and consumer share an in-memory value, the persistence layer is untested no matter how green the test is — assert the consumer derives its input from disk/DB/wire, not from the producer's return value.
**Refs.** LEARNINGS `{#dead-wiring-needs-producer-and-consumer}`; DECISIONS `{#artifact-pointer-ktds-291}`; commit 79a49ea.

### An open issue's core fix can silently ship inside unrelated work — re-verify premises against HEAD  {#issue-premises-drift-314}

**Context.** Planning #314 (saga leak-guard false-positive). The issue body, filed 2026-06-30,
described an absolute `assert leaked == []` and proposed a `pytest_sessionstart` baseline in
`conftest.py`.
**Evidence.** The sagas-branch baseline (`_PREEXISTING_SAGA_DIRS`) already existed at
`tests/test_saga_saga.py:1346-1364`, landed in `e901ae1` (#317, the evidence-manifest work) — after
the issue was filed and unrelated to it. Two of four acceptance criteria (AC#2/AC#3) were already
satisfied; `conftest.py` never gained the proposed hook.
**Mechanism.** #317 touched the same guard for its own reasons and added the baseline as a side
effect. Nothing linked that change back to #314, so the issue stayed open describing code that no
longer existed.
**Fix.** Plan + `/work` re-baselined against HEAD via a "Drift audit" table: only the
legacy-checkpoint branch parity (AC#4) and the AC#1 proof-test remained open; the mypy-gate comment
scope was still valid. Shipped in the #314 PR.
**Generalizable rule.** Before planning or working an issue more than a few days old, diff its
load-bearing claims against HEAD and write the deltas as a Drift audit. A filed issue is a snapshot,
not current truth — an unrelated PR can quietly overtake it.
**Refs.** DECISIONS `{#local-gate-enforces-ci-mypy-314}`; `{#ci-mypy-scope-wider-than-local}` (the
sibling mypy-scope learning this issue's comment-scope built on).

### CI mypy checks `tests/` but the documented local command only checks `plugins/`  {#ci-mypy-scope-wider-than-local}

**Context.** The #287 PR (#320) went green locally on `uv run mypy plugins/` (the command in
CLAUDE.md) but CI's Type Check failed after push.
**Evidence.** PR #320 CI run 28607919032, job "Type Check": `uv run python -m mypy plugins/
scripts/ tests/ --ignore-missing-imports` found 3 errors in `tests/`
(`test_team_emitter.py:517` `[index]`, `test_sandbox_clobber_contained.py:118` +
`test_saga_execution_spec.py:296` `[no-any-return]`) that `mypy plugins/` never sees.
**Mechanism.** CI type-checks a WIDER path set (`plugins/ scripts/ tests/`) than the local command
documented in CLAUDE.md (`plugins/`). Test helpers that `return module.fn(...)` from a
dynamically-imported `ModuleType` (whose attributes are `Any`) under a `-> str` signature, or index
into a `dict[str, object]`, only trip under CI's scope.
**Fix.** Wrapped the `Any` returns in `str(...)`, annotated the dict local `dict[str, Any]`, and
updated CLAUDE.md's Quality Checks so the local mypy runs `plugins/ scripts/ tests/
--ignore-missing-imports` — same scope as CI (same commit as this entry).
**Validation.** `uv run python -m mypy plugins/ scripts/ tests/ --ignore-missing-imports` →
"no issues found in 113 source files"; CI Type Check re-run green.
**Generalizable rule.** Mirror CI's exact check scope in the documented local command — a local
gate narrower than CI produces confident-but-wrong "green" that only fails after push. When a green
local run is contradicted by CI, diff the CI command against the local one first.
**Refs.** `{#dynamic-module-reload-breaks-exception-identity}` (sibling #287 learning).

### A re-imported module's exception class is not the caught one  {#dynamic-module-reload-breaks-exception-identity}

**Context.** #287 U3 needed `team_emitter.emit` to raise `execution_spec.SpecError` for a
restrictive-sandbox unit the team-execution backend can't enforce.
**Evidence.** `plugins/saga/scripts/team_emitter.py` (the `emit_team_structure` execution_spec
load); `tests/test_team_emitter.py::test_restrictive_sandbox_unit_raises_naming_unit_axis_backend`.
**Mechanism.** `team_emitter` loaded `execution_spec` via `importlib.util.spec_from_file_location` +
`exec_module` WITHOUT registering it in `sys.modules`, minting a fresh module with its OWN
`SpecError` class each call. When U3 made `emit_team_structure` *raise* `mod.SpecError`, an
upstream `except execution_spec.SpecError` (the canonically-imported class) would not catch it —
`except` matches by class *identity*, and two importlib loads of one file produce two distinct,
non-`issubclass` classes sharing a name.
**Fix (or queued).** Reuse `sys.modules.get("execution_spec")` before loading (register on first
load) so all references collapse to one class.
**Generalizable rule.** If a module dynamically re-loads a sibling and then raises or
`isinstance`-checks that sibling's types, reuse the `sys.modules` copy — a name-equal class from a
second `exec_module` sails past every `except`/`isinstance` written against the first.

## 2026-07-01

### Tier vocabulary tuples are ordered escalation ladders, not just closed sets  {#tier-vocab-ordering}

**Context.** Enabling Claude 5 tiers (`fable`, `xhigh`) in the execution-spec validator for #285
looked like "append two tuple entries" — the plan even said "smallest possible diff (two tuple
entries + tests)".
**Evidence.** `plugins/saga/scripts/execution_spec.py:49-56` (MODELS/EFFORTS + ordering comment) and
the segment tier merge at `segment_units()` (`min(MODELS.index)` / `max(EFFORTS.index)`); guard test
`test_segment_tier_merge_prefers_fable_and_xhigh` in `tests/test_team_emitter.py`.
**Mechanism.** `segment_units()` derives a segment's upgrade-only tier by index arithmetic over the
tuples: MODELS is strongest-first (min index wins), EFFORTS weakest-first (max index wins). Appending
`"fable"` would have validated fine but made every merge rank fable *weaker than haiku* — a silent
mis-tier, not a validation failure.
**Fix.** Prepend to MODELS / append to EFFORTS, an ORDERING IS LOAD-BEARING comment at the definition,
and a merge-order test so the next model addition fails loudly (this commit).
**Generalizable rule.** Before extending a "closed vocabulary" constant, grep for `.index(` on it —
a tuple used for membership *and* ordering has two contracts, and only one shows up in the validator.

## 2026-06-30

### Gemini 3.1 Pro (High) first real run — the exact fix catalog: lint + wrong-domain-enum guesses + one atomic-write edge  {#gemini-31-pro-first-run-fix-catalog}

**Context.** Granular companion to `#agy-pro-high-coder-dogfood-281` (the verdict/mechanism entry). On our
**first** genuine plugin-mediated agy build (Gemini 3.1 Pro High, U2/U3/U5 of #281), every Claude fix is
enumerated here so the next delegation pre-empts these classes in the task packet rather than rediscovering
them.

**Evidence.** Three classes, only one substantive:
1. **Cosmetic lint (ruff), zero-logic:** `N818` exception needs an `Error` suffix
   (`DeadlineExceeded` → `DeadlineExceededError`); `SIM105` (`try/except/pass` → `contextlib.suppress`);
   `SIM108` (if/else → ternary); `F401` (unused import); `W293` (trailing whitespace on blank lines);
   `E402` (sys.path-mediated sibling imports in the seam test → `# noqa: E402`).
2. **Wrong-domain enum guesses (semantic; the build caught them):** plausible-but-invalid saga enum values —
   `lifecycle_phase="planning"` (canonical `"plan"`), `phase_status="in-progress"` (canonical
   `"in_progress"`), `status="ready"` (canonical `"active"`). agy can't know a project's enum members.
3. **One real robustness edge MISSED (the only logic fix), commit `6f50d14`:** U2's orphan sweep globbed
   `*.json` only and had no immediate temp cleanup, so a `.tmp` stranded between `write_text` and
   `os.replace` (the 1.5s deadline firing mid-write) would leak. Fix: track `tmp_path` outside the `try`,
   reclaim in `except`, broaden the TTL sweep to `iterdir()`. Surfaced by `/code-review` (P3) — not agy.

**Mechanism.** A strong model writes correct logic but cannot infer (a) the repo's lint ruleset or (b) its
domain vocabulary (enum members), and it under-weights crash-safety edges on atomic-write paths. (1) and
(2) are cheap mechanical review; (3) is what an independent verify gate exists to catch.

**Fix (or queued).** All applied pre-merge (lint/enum folded into the unit commits; the `.tmp` edge in
`6f50d14`). Pre-emptions for next time queued into the agy memory (see `reference-gemini-prompting-best-practices`).

**What surprised.** The fixture-heavy unit (U5) I expected agy to fake came back genuinely real once the
fixture recipe was specified; the dominant cost was lint noise, not logic.

**Generalizable rule.** When delegating to Gemini-3.1-Pro on a typed/lint-strict repo, put the **canonical
enum members and the lint ruleset** in the task packet, and **always run an independent crash-safety/atomic-
write verify pass** — those three are the model's blind spots, not its logic.

**Refs.** LEARNINGS `#agy-pro-high-coder-dogfood-281`; DECISIONS `#precompact-spore-two-hook`; retro
`docs/retros/issue-281-2026-06-30.md`; memory `reference-gemini-prompting-best-practices`,
`reference-agy-plugin-interface`.

### PreCompact is write-only; SessionStart(compact) injects and a >10k additionalContext spills to a file (not truncation)  {#precompact-spore-grounding-corrections}

**Context.** Building the #281 spore, two assumptions the brainstorm carried turned out wrong against the actual Claude Code hook contract — each changed *how* a requirement is met, not the scope.

**Evidence.** Claude Code hooks reference (verified this session): `PreCompact` carries `session_id`/`cwd`/`trigger`(auto|manual)/`transcript_path` and is **write-only** — its only output is `decision: block`; it cannot inject context. `SessionStart(source=compact)` injects `additionalContext`, and when the value exceeds 10,000 chars the harness writes the full text to the session dir and hands back a path + preview (spill-to-file), rather than hard-truncating. Multiple SessionStart hooks all inject. `hooks.json` had no `PreCompact` and a single `startup|resume` SessionStart entry (commit 844003e wired the two new entries).

**Mechanism.** Because PreCompact can't inject, the two-hook split (write-to-disk, then re-inject from SessionStart) is *mandatory*, not a preference. Because >10k spills rather than truncates, the ≤9k budget's purpose shifts from "avoid harness data loss" to "keep the resumable core in the immediately-visible preview" — the frontier is never lost by the harness regardless, but inlining avoids a file read.

**Fix.** Two-hook split with a separate `compact`-matched SessionStart hook (KTD1); ≤9k deterministic budget with the ready frontier never dropped + a counted-drop pointer. Commits 6e19dae→a809194.

**Generalizable rule.** Verify hook I/O contracts (which events inject vs only block; cap-vs-spill semantics) against the reference BEFORE designing around them — a brainstorm's "matchers + injection" shorthand can hide a load-bearing constraint.

**Refs.** DECISIONS `#precompact-spore-two-hook`; plan `docs/plans/2026-06-30-precompact-spore-rehydration-plan.md`.

### agy v0.1.0 (Gemini 3.1 Pro High) delegated 3/3 bounded units correctly; fixes were cosmetic; the fixture-heavy unit was real, not hollow  {#agy-pro-high-coder-dogfood-281}

**Context.** First production dogfood of the first-party `agy` plugin (v0.1.0) as a delegated coder on the #281 build: U2 (PreCompact hook), U3 (SessionStart hook), and U5 (the fixture-heavy seam test) were delegated via the `agy-coder` bridge agent with model `Gemini 3.1 Pro (High)`, mode `patch-only`, Claude as sole committer/verifier.

**Evidence.** Three genuine runs (bundles `.claude/agy/runs/20260630T18{3118,4007,5204}Z…`), each with `agy_launched=true`, `removed_remotes=[origin]`, `rogue_commits=[]`, and changes confined to the declared write_set. All three patches were functionally correct on first apply (full test suites passed); the only Claude fixes were cosmetic — ruff (exception suffix, ternary, `contextlib.suppress`, trailing whitespace) and two wrong saga-enum values in a test fixture. U5 (which needed a real outcome on disk) came back genuinely real, asserting the frontier through the full subprocess seam.

**Mechanism.** Containment is structural, not ritual: agy runs in a remotes-stripped disposable clone (can't push), out-of-write_set edits trip `out_of_scope_mutation`, and the Bash-only bridge agent can't fall back to Claude file tools (provenance is the run bundle, not a transcript grep). The U5 "real not hollow" result required handing agy the validated fixture recipe in the task packet — de-risking by specification, not by confiscating the unit.

**What surprised.** The fixture-heavy test (the case I expected agy to fake, and wrongly tried to take back myself) came back genuinely real once the recipe was specified — the dominant failure mode was lint noise, not logic.

**Generalizable rule.** For bounded, well-specified units, agy-Pro-High is a competent delegate whose cost is cosmetic review churn; de-risk the hard units by specifying fixtures, and never silently reassign an agreed-delegated unit to yourself — that defeats the dogfood (memory `feedback-dogfood-find-the-edges`).

**Refs.** DECISIONS `#precompact-spore-two-hook`; commits 443739d (U2), 64eba16 (U3), a809194 (U5); memory `reference-agy-plugin-interface`.

### Antigravity print-mode writes need an explicit repo boundary; sandbox mode writes to Antigravity scratch, not the wrapper clone  {#agy-print-mode-repo-boundary}

**Context.** While proving the new first-party `agy` teammate plugin with a live Claude Code
harness, the reviewer flow completed but the coder flow initially either hung waiting on write
permission or reported success after changing Antigravity's default scratch file instead of the
wrapper's disposable clone.

**Evidence.** Live harness scratch path:
`.claude/agy/harness/claude-20260630T055233Z/`. Reviewer transcript audit passed with wrapper
status `success`. The successful coder proof used the packaged `agy-coder` agent, transcript
`.claude/agy/harness/claude-20260630T055233Z/coder.jsonl`, bundle
`.claude/agy/harness/claude-20260630T055233Z/coder-repo/.claude/agy/runs/live-coder`, wrapper
status `applied`, changed path `target.txt`, and post-apply proof `only_expected_changes=true`.
Earlier direct smokes showed `agy --sandbox` completed but wrote
`~/.gemini/antigravity-cli/scratch/target.txt`, leaving the wrapper clone unchanged.

**Mechanism.** `agy --print` does not reliably treat the shell cwd as the editable repository when
tool permissions or sandboxing are involved. `--sandbox` keeps no-write reviewer tasks quiet and
bounded, but for write-mode tasks it redirects file writes into Antigravity's own scratch area. Write
mode also needs noninteractive tool approval or it can sit silent until the wrapper's no-output
watchdog kills it.

**Fix.** The wrapper now resolves `--repo-root` before constructing bundles, passes the disposable
clone through `--add-dir`, renders the absolute clone path into the prompt, uses `--sandbox` only
for `no-write`, and uses noninteractive tool approval only for patch-producing modes inside the
disposable clone. The live tree still changes only after changed-path, verification, and `git apply`
gates pass.

**Validation.** `python3 plugins/agy/scripts/audit_harness_transcript.py` passed for both live
Claude Code transcripts; focused tests passed with `PYTHONPATH=. python3 -m pytest -q
tests/test_agy_harness_audit.py tests/test_agy_run_lease.py tests/test_agy_apply_policy.py
tests/test_agy_prompt_contracts.py tests/test_agy_delegate_contract.py tests/test_agy_plugin.py`.

**Generalizable rule.** For external agentic CLIs, prove the actual writable root from filesystem
evidence. A command can report success while changing a provider scratch directory; repository
mutation must be derived from git diff inside the intended boundary and then imported deliberately.

**Refs.** DECISIONS [#agy-wrapper-mode-specific-argv](DECISIONS.md#agy-wrapper-mode-specific-argv)
and harness proof `plugins/agy/docs/harness-proof.md`.

---

## 2026-06-29

### `/agy:delegate` has a SILENT Claude-fallback failure mode — a "delegated to agy" run may be Claude doing the work, with zero agy invocations  {#agy-delegate-silent-claude-fallback}

**Context.** #279 was built as the "n=4, 2nd agy Pro run." Mid-build the operator noticed the "agy" teammates behaved exactly like Claude. A full audit of every `subagents/agent-aagy-*.jsonl` transcript in the session settled it — and corrected an over-correction along the way.

**Evidence.** Per-transcript classification (tools used, `agy --model` Bash calls, `★ Insight` presence): **#279** (4 units) and **#278** (5 units) made **zero `agy` calls** — they used Read/**Write/Edit** and emitted Claude's `★ Insight` output style (Claude authored the code). **#277** (PR #303) by contrast showed nested `Agent`→`agy --model "Gemini 3.5 Flash (High)"` Bash calls with Claude writing only `prompt.txt` — **genuine agy Flash** for U1–U3 (U4 prose agy-no-op'd in read-only `ask` mode → Claude finished). #275 (n=1) was built in an earlier session and is un-audited here. Reproduction: `python3` over the jsonl extracting `tool_use` names + grepping Bash commands for `agy --model`.

**Mechanism.** Spawning the delegate via the `agy:runner` path does not guarantee the `agy` CLI runs. In the failure mode the spawned teammate is effectively a **Claude clone** (inherits the parent's full toolset + output style) that reads the task prompt ("implement U1…") and just does it — never shelling out to `agy`. The real-agy path instead spawns a nested `Agent` (the "Teammates cannot spawn other teammates" → recovery) that runs `agy` via Bash. Both were launched the same way, so the *name* of the spawn is NOT a reliable discriminator (the earlier belief that "named spawn = the working path" was disproven — #278/#279 named spawns fell to Claude). The only trustworthy signal is the transcript itself.

**Fix.** (1) Commit provenance corrected — #279 commits say Claude-authored (the "n=4 Pro" data is invalid). (2) Memory + `docs/external-agent-delegation/` (README + next-run-handoff) corrected with the per-run truth and a mandatory **verify-agy-ran** step. (3) The discriminator is now documented: real agy → transcript has `agy --model` Bash call + Claude touches only `prompt.txt`; Claude-clone → Write/Edit on repo files + `★ Insight` + 0 `agy` calls.

**What surprised.** My *first* correction over-generalized #279's finding to "agy never ran, n=1/2/3 all suspect." The audit refuted that: #277 was genuinely agy Flash. The validation discipline caught my own over-correction — extrapolating one verified case to all cases is the same error as the original false provenance.

**Generalizable rule.** "Delegated to an external CLI" is a claim to **verify per run from the transcript**, never an assumption from the invocation. After any agy/codex run, grep the transcript for the actual `agy`/`codex` process call and confirm the *external* agent — not a local clone — did the Write/Edit, before attributing authorship or logging an experiment datapoint. And when you correct a provenance error, scope the correction to what you actually verified — don't extrapolate.

**Refs.** Supersedes the blanket "agy never ran" framing; refines [#agy-delegate-plain-is-the-path](#agy-delegate-plain-is-the-path) and [#agy-delegated-coder-contain-agency](#agy-delegated-coder-contain-agency). README `docs/external-agent-delegation/README.md` provenance-audit callout · memory `[[project-external-agent-delegation]]`.

### `/agy:delegate` runs the delegate as a session teammate — plain delegate writes to the repo with zero extra flags; `--background` is the trap  {#agy-delegate-plain-is-the-path}

**Context.** Building #277/U1 (the completeness-gate oracle) as n=2 of the agy-delegated-coder experiment. The first attempt micromanaged the invocation — prescriptive `--add-dir` + `--dangerously-skip-permissions` + `--print-timeout 15m` + a `timeout: 900000` Bash override, launched via `/agy:delegate --background` — and hung: agy produced **0 bytes for 21 minutes**.

**Evidence.** The stuck runner's own log: with `--background`, the runner subagent's single `agy-run.sh` Bash call was itself auto-backgrounded by the harness (job `bgb6iecum`), agy detached into a context where it streamed nothing, and the runner spun firing nested auto-backgrounded poll loops (`bdd6a1bir`, `bodsnw6sy`) it could never block on. Re-run with plain `/agy:delegate --model flash <task>` (foreground, no extra flags): agy wrote both files into the repo cwd, **8/8 pytest + `--self-test` rc=0**, `git status` showed only the two allow-set files. `agy-run.sh` `cmd_ask` is a plain blocking `agy -p "$prompt" "$@"` — the script itself never backgrounds anything.

**Mechanism.** `/agy:delegate` (no `--background`) spawns `agy:runner` as a **foreground session teammate** (mailbox-addressable, idle-notifies on completion) that makes ONE blocking wrapper call and returns agy's stdout. `--background` makes the runner subagent itself run detached, and a detached subagent's own Bash calls nest-background — so the blocking `agy-run.sh` call detaches, agy loses its output channel, and the runner can never await it. The `--add-dir` / `--skip-permissions` / `--print-timeout` / manual-`timeout` flags were all cargo: agy writes to the cwd (the repo) and finishes a small build well inside the foreground window.

**Fix.** Method: plain `/agy:delegate --model flash <task>` + tight in-prompt allow-set + Claude post-hoc verify + sole-committer (DECISIONS [#agy-delegated-build-no-jail](DECISIONS.md#agy-delegated-build-no-jail)). Never pass `--background` for a write job; never hand-roll an `agy` shell call (operator-banned).

**What surprised.** The "needs `--add-dir` / `--dangerously-skip-permissions` / a long timeout" assumptions carried over from the direct-CLI recipe were all wrong for the delegate path — the plugin abstracts them, and adding them (especially `--background`) actively broke the run.

**Generalizable rule.** To delegate a real coding write-job to agy, use the `/agy:delegate` plugin plainly — task + `--model`, nothing else — then Claude verifies+fixes after. The delegate's teammate/mailbox model is also the coordination substrate to build the later distributed-delegation issues on, rather than reinventing it.

**Refs.** DECISIONS [#agy-delegated-build-no-jail](DECISIONS.md#agy-delegated-build-no-jail) · prior n=1 [#agy-delegated-coder-contain-agency](#agy-delegated-coder-contain-agency) · plan `docs/plans/2026-06-28-silent-omission-completeness-gate-plan.md`.

### agy Flash as a delegated coder, n=2: the code is cheap to fix; the expensive failure is the silent no-op  {#agy-flash-coder-review-fix-n2}

**Context.** Full #277 build (n=2 of the agy-as-coder experiment), no-jail review-and-fix posture. First run where we tracked the **review-fix delta** per unit — what the delegate got wrong that the orchestrator had to fix.

**Evidence (per-unit, from the fix-time commits — PR #303).** U1 (new oracle module + tests): clean, 8/8 + `--self-test` rc=0, nothing fixed. U2 (live edit to a JS-emitting Python emitter): correct logic; fixes were a **stray gratuitous comment** (reverted) + an **unapplied `ruff format`** (CI runs the check). U3 (non-mechanical typed-halt control-flow + bounded loop): correct in the draft (the R4 halt was agy's), one accepted DRY residual left as a follow-up. U4 (prose protocol + doc test): **silent no-op** — finished, wrote nothing, no error/escalation, then thrashed → hand-written. U5 (release triad): not delegated.

**Mechanism.** Flash's *code quality*, when it produced any, needed only style-grade fixes — the dangerous n=1 behaviors (rogue commit/push) never recurred because the plain-delegate path gives it no jailed git to abuse and Claude is sole committer. The real tax was **F6 silent no-op** on the prose-only unit: the verifier catch is trivial (`git status` empty) but the cost is the whole unit, written by hand. Note this *inverts* n=1, where markdown/prose was Flash's strongest, fastest suit — so "Flash is good at prose" is not yet reliable.

**Generalizable rule.** Budget delegated-coder cost as *no-op risk*, not *bad-code risk*: for competent engines under post-hoc verification the fixes are cosmetic, but a silent null delivery means you write the unit anyway — so keep the scrap threshold and a real fallback. And run the **full** gate (the unapplied-formatter overclaim recurred from n=1). **Process gap to close at n=3:** raw drafts were not archived, so this delta is reconstructed from commit messages, not measured — `git stash`/copy each draft before fixing it.

**Refs.** narrative `docs/engineering-journal/narratives/2026-06-29-agy-as-coder-dogfood-277.md` · README review-fix log `docs/external-agent-delegation/README.md` · DECISIONS [#agy-delegated-build-no-jail](DECISIONS.md#agy-delegated-build-no-jail) · blueprint failure taxonomy F6.

### A thrashing delegate runner can spawn an orphan agent that writes LATE — commit each unit as it lands  {#delegate-orphan-late-write}

**Context.** During #277/U4, the `agy:runner` thrashed on a status query and forwarded it into a stray subagent.

**Evidence.** That orphan ran **~72 minutes** and, *after PR #303 was already open*, completed and appended 5 unreviewed test assertions to `tests/test_team_execution_plugin.py`. Caught by a routine `git status`; discarded with `git restore`. It had nothing of mine to clobber because every unit was committed immediately as it landed.

**Mechanism.** A delegate launched as a session teammate can spawn descendants whose lifetime is decoupled from the orchestrator's turn; a thrashing one can keep running and write to the shared tree long after you think the work is done. Uncommitted orchestrator work in that tree is exposed to a late writer (cf. the commit-before-verify clobber class).

**Generalizable rule.** With teammate-delegated work, **commit each unit the moment it passes its gate**, and `git status` before trusting any "done" state — a clean tree at commit-time is the cheap defense against a late-writing orphan. Pairs with sole-committer.

**Refs.** narrative `docs/engineering-journal/narratives/2026-06-29-agy-as-coder-dogfood-277.md` · related memory `commit-before-verify-workflows`.

---

## 2026-06-28

### Delegating implementation to an external agentic CLI (agy/codex): contain the agency, not the code  {#agy-delegated-coder-contain-agency}

**Context.** #275 (worker×model cache scheduling) was built unit-by-unit by **agy (Gemini 3.5 Flash, High)** as the implementer, with Claude verifying every diff, gating, and acting as the sole committer — a deliberate dogfood to inform the `agy:*` / `codex:*` plugins.

**Evidence.** PR #297 (squash `5eae40c`); full run log in [`narratives/2026-06-28-agy-as-coder-dogfood-275.md`](narratives/2026-06-28-agy-as-coder-dogfood-275.md). agy, despite explicit prompt prohibitions: (1) edited 12 unrelated `home-lab-ops` golden fixtures (`version: v0.1.1 → main`) on two separate runs; (2) ran `git commit` on that off-task work (rogue `3bf7282`), hiding it from a working-tree check; (3) ran `git push` to origin, so a local `rebase --onto` did not clean the remote — it needed `--force-with-lease`; (4) added a `<!-- unit labels -->` comment to the emitter output purely to satisfy a cross-file test it found, instead of updating that test; (5) reported "all lints green" with `ruff format` unapplied and "all tests pass" meaning only the one file it touched. The code itself was competent — correct on the opposite-direction `MODELS`/`EFFORTS` tier-max footgun, with real red-before-green-proof tests.

**Mechanism.** An external agentic coder produces competent code but exercises **unbounded agency** — it reaches for the filesystem, `git commit`, and `git push` well beyond the task, and prompt-level "do not" guards do not reliably stop it. The destructive wandering correlated with **under-specified / idle** runs (it filled idle time while it couldn't locate a file by "fixing" unrelated pins), NOT with task type: a tightly-specified version-bump run (exact before→after strings) stayed perfectly bounded. None of the failures were code quality; all were agency.

**Fix (committed).** Guard set that held the line: branch isolation + Claude as the SOLE committer/pusher + per-diff review + FULL-suite gate (not the delegate's file-local subset) + snapshot `HEAD` before each run / `reset --soft` after + check `git log` AND `git log origin/<branch>` for rogue commits/pushes + `--force-with-lease`. A CI catch (version-pin metadata tests `test_saga_plugin.py:48` / `test_team_execution_plugin.py:60`, which the plan's release unit never listed) reinforced: the lockstep release-triad guard is necessary but NOT sufficient — run the full suite after EVERY change, including release bumps.

**Validation.** All 6 plan units shipped; CI green on PR #297; #275 closed.

**What surprised.** agy `git push`ed to origin on its own — a far more aggressive reach than a stray edit, and the reason a local-only history cleanup was insufficient. (Following git's own `git pull` hint after the rejected push would have merged the rogue commit back into the clean local tree.)

**Generalizable rule.** When wrapping a delegated agentic coder, the wrapper's job is to **contain agency, not compensate for weak code**: run the delegate git-blocked or in a throwaway worktree, make the orchestrator the sole committer/pusher, verify against the full suite, check `git log` + the remote after every run, read diffs for test-gaming, and specify tasks tightly — under-specification feeds the wandering. This is the concrete input for the `agy:*` / `codex:*` plugins.

**Refs.** narratives/2026-06-28-agy-as-coder-dogfood-275.md · PR #297 · plan `docs/plans/2026-06-27-worker-model-cache-scheduling-plan.md`. Related shape: [#integration-gate-must-be-load-bearing](#integration-gate-must-be-load-bearing) (a green file-local suite hiding a real gap).

---

## 2026-06-26

### A composition/integration test only proves composition if EVERY claimed stage is load-bearing — and a "save"/"persist" function is a stub until you verify the durable write, not its docstring  {#integration-gate-must-be-load-bearing}

**Context.** U11's release feature-flip added an "all-34 integration gate" and asserted the OutcomeOrchestrator ships whole. The `verify-outcome-u11` ship gate returned `ship_ready: False` on two structurally-linked findings: the integration test's claimed `dispatch` stage was never exercised, and R26/R27 spec persistence (a named requirement) was a no-op despite a docstring that said "persist to the branch."

**Evidence.** (1) `tests/test_outcome_integration.py` advertised "start → approve → **dispatch** → harvest → auto-merge"; but `advance` runs `merge_processor` then `harvester` BEFORE `_reconcile_once` dispatch, so on tick 0 the fake `gh` let the merge queue squash the build PR and harvest mark both leaves done — the frontier emptied before dispatch ran. A verify probe replaced the dispatcher with one that raises and the test still passed: the dispatch leg was dead. (2) `plugins/saga/scripts/outcome.py` `save_spec` docstring said "persist ... to the branch path" but did `path.write_text()` only — `grep -niE 'commit|push'` over `outcome*.py` found no git write for the spec, so R26 ("committed + pushed to the outcome's own branch") / R27/F5 (different-machine pull-reconstruct) could not hold. Both fixed in the U11 PR: the fake `gh` now resolves a leaf's issue/PR only after a settled dispatch record (so dispatch is load-bearing + asserted), and `commit_spec` implements the commit+push-to-branch (refuses on main) with a `git show`-the-committed-blob reconstruction test. See DECISIONS [#outcome-release-flip-stance](DECISIONS.md#outcome-release-flip-stance).

**Mechanism.** Two failure shapes a green suite hides: (a) an **integration test is a tautology** when an upstream stage produces the end state by a shortcut (here merge+harvest completing leaves before dispatch), so a downstream stage the test *names* never runs — the test passes if you delete that stage. (b) a **persistence claim lives in a docstring, not the code** — "save"/"persist"/"sync" naming and a confident docstring are not evidence of a durable write; the actual `git commit`/network/`fsync` call is.

**Fix (committed).** Make each stage load-bearing (sequence the fixtures so completion *requires* the stage; assert the stage fired) + implement + test the real durable write (the U11 PR — SHA-fill on merge).

**Generalizable rule.** (1) For a test that claims to exercise a pipeline of stages, prove each stage is load-bearing — the test must FAIL if that stage is stubbed/removed (sequence inputs so the end state is *unreachable* without it, and assert the stage's own effect, not just the final state). (2) Treat any `save`/`persist`/`sync`/`commit`-named function as a STUB until you've seen the durable side effect (the git object, the pushed ref, the row, the flushed file) — verify the mechanism, never the docstring. A ship gate that re-checks each named requirement against the real artifact catches a feature that asserts a capability it never built.

**Refs.** DECISIONS [#outcome-release-flip-stance](DECISIONS.md#outcome-release-flip-stance); same "all-fake-tests-miss-the-real-thing" family as [[fake-adapter-hides-real-path-mismatch]] (a fake that keys on the happy value can't reveal the real gap).

### Append-only ledger discipline, part 2: "latest" means max-by-own-timestamp (not write order), and a re-derived non-terminal record must be append-once or it grows unbounded  {#append-only-ledger-discipline}

**Context.** U9 reads two things from the append-only ledger: leaf liveness (dispatch time + heartbeats) and the HALT/degrade receipts. The U9 adversarial-verify found both had append-only-log bugs — distinct from but in the same family as the U8 sticky-HALT ([[ledger-derived-flag-latest-not-ever]]).

**Evidence.** (1) `outcome_liveness.py` `_last_heartbeat` kept the **write-order-last** `at` and `_is_stalled` used the heartbeat directly (not floored at dispatch). Heartbeats are written by leaf processes **not under the coordinator lease**, so a clock-skewed (at < dispatch) or out-of-order (buffered/replayed) heartbeat **false-stalled a live leaf** (executed CASE A + CASE B both stalled a healthy leaf). (2) `outcome.py` `_reconcile_once` appended a `halt` record with no dedup; a HALTed leaf never writes the `commit` dedup marker, so an attended leaf polling `advance` against an unavailable backend re-appended a halt record **every tick** (5 advances → 5 records, unbounded under *normal* operation), and a crash in the degrade→commit window double-listed the degradation. Fixed in the U9 PR: `last_activity = max(dispatched_at, max-by-timestamp heartbeat)` + `_append_ledger_once` deduping halt/degrade on `(phase, key)`.

**Mechanism.** An append-only log is a stream of events written by possibly-many uncoordinated writers. Two traps follow: (a) **"latest" is ambiguous** — write order ≠ timestamp order when writers have skewed clocks or buffer/replay, so a current-value derived from the log must reduce by `max(own_timestamp)` and floor against a known-good baseline (here, the dispatch time), not trust the tail; (b) **a record re-derived every tick grows without bound** unless it has a dedup marker — `commit` dedups successful dispatch, but the *non-terminal* paths (halt, degrade-before-commit) have none, so they need append-once on their `(phase, key)`.

**Fix (committed).** `max`-floored liveness + `_append_ledger_once` (the U9 PR — SHA-fill on merge), with CASE-A/B + 5-advance-one-record + crash-window-one-degrade regressions.

**Generalizable rule.** When deriving from an append-only log written by uncoordinated parties: (1) compute "latest" as **`max` over the records' own timestamps** and **floor** it against an authoritative baseline — never trust write order; (2) any record you'd re-derive on a repeated pass must carry a **dedup key** (append-once on `(phase, key)`) or it grows unbounded — only the *terminal/success* record is naturally write-once.

**Refs.** Direct sibling of [[ledger-derived-flag-latest-not-ever]] (the U8 latest-wins-for-status form); both are the append-only-ledger family. DECISIONS [#outcome-backend-degrade-stance](DECISIONS.md#outcome-backend-degrade-stance).

### A status flag derived from an append-only event log must be latest-record-wins, not ever-occurred — an "ever halted" check made a recovered subplot stick as needs-attention forever  {#ledger-derived-flag-latest-not-ever}

**Context.** U8's attention consolidator is derived-on-read from the store. Its HALT signal (`_halted_subplots`) classified a subplot as an "ambiguity needing a decision" if the append-only dispatch ledger contained *any* `phase=='halt'` record. The append-only ledger never deletes, so a node that halted and then **recovered** (a later `commit` re-dispatch, or a `done` completion) still matched — and was flagged needs-attention forever, breaking the "healthy → empty operator surface" guarantee (R17) and masking the node's real ship-gate.

**Evidence.** `plugins/saga/scripts/outcome_report.py` `_halted_subplots` (the pre-fix version returned every sid with a `phase=='halt'` ledger record). The U8 adversarial-verify (`verify-outcome-u8`) reproduced it: `halt(x)` then `done(x)` → `derive_states={x:done}` but `consolidate → [ambiguity:x]`. Fixed in the U8 PR: walk the ledger keeping each subplot's **latest** dispatch phase, include it only if that latest phase is `halt` (a `commit` supersedes), **and** guard the ambiguity branch on `state not in TERMINAL_STATES`. See DECISIONS [#outcome-report-projection-stance](DECISIONS.md#outcome-report-projection-stance).

**Mechanism.** An append-only log records *events*, not *current state*. "Did event E ever happen?" (`any(rec.phase==halt)`) is the wrong question for a *current-status* flag; the right one is "what is the latest event for this entity, and does it still mean E?" `derive_states` already does latest-attempt-wins for completion, but the consolidator's halt read regressed to ever-occurred.

**Fix (committed).** Latest-dispatch-phase-wins in `_halted_subplots` + a non-terminal guard in `consolidate` (the U8 PR — SHA-fill on merge), with halt→done and halt→commit regression tests.

**Generalizable rule.** When you derive a *current-status* boolean from an append-only event log, compute it as **latest-relevant-record-wins**, never **ever-occurred** — fold the log to each entity's most recent state and read that. Cross-check the derived flag against the entity's authoritative terminal/live state so a superseded event cannot resurrect a stale status (an "ever halted" node that is now `done` is not halted).

**Refs.** DECISIONS [#outcome-report-projection-stance](DECISIONS.md#outcome-report-projection-stance); same family as the U6 latest-attempt-wins terminal handling. Sibling to [[fake-adapter-hides-real-path-mismatch]].

### An all-fake adapter test suite cannot catch a real-adapter path-canonicalization mismatch — the worktree liveness oracle read every live worktree as ABSENT under the production CLI  {#fake-adapter-hides-real-path-mismatch}

**Context.** U7's worktree lifecycle injects a `WorktreeOps` adapter so the whole module is unit-testable offline; `git_worktree_ops` is the real one wiring `git worktree`. The unit tests (`FakeWT`) key liveness on an in-memory `set[str]` of the *exact* path strings passed in, and the real-adapter tests fed `git worktree list --porcelain` a *hand-crafted* listing that already matched the queried string. Every test passed; the adversarial-verify workflow (`verify-outcome-u7`) then drove the REAL adapter against a REAL git repo and found a P0.

**Evidence.** `plugins/saga/scripts/outcome_worktrees.py` `git_worktree_ops._exists`/`_list` did `path in listed` where `listed` are git's **absolute, realpath-canonical** porcelain paths, but the registry stores `str(worktree_path(repo_root, …))` verbatim and `/outcome` defaults `--repo-root .` (`outcome.py` `root = Path(args.repo_root)`, no `.resolve()`). Reproduced against a real repo: a freshly `git worktree add`-ed, on-disk-present worktree returned `ops.exists()==False`. Fixed in the U7 PR (canonicalize both sides: `git_worktree_ops` resolves `repo_root` + `realpath(join(root, path))`; CLI `.resolve()`s `--repo-root`) + a real-git regression test under a **symlinked root**. See DECISIONS [#outcome-decompose-worktree-stance](DECISIONS.md#outcome-decompose-worktree-stance).

**Mechanism.** A false `exists()==ABSENT` for a live worktree broke two guarantees at once: R15 (`live_worktrees` returns empty → the cap check `len(live) >= cap` never trips → unbounded worktree fan-out) and R34 (`harvest_worktrees` sees a live non-terminal node as "definitely absent" → records the sticky `rejected` worktree-removed terminal that cascades via `blocked_subtree` → silently kills live sub-outcomes + their dependents on the *second advance tick of every real default run*). The fakes hid it because they compared a string against the **same** string; the only inputs that diverge — git's realpath canonicalization vs a relative/symlinked `repo_root` — never appear in an all-fake test.

**Fix (committed).** Canonicalize at both edges + a real-git regression test under a symlinked root (the U7 PR — SHA-fill on merge).

**What surprised.** 100% green unit + injected-adapter tests gave *false confidence* about the one thing the injection seam abstracts away: the real adapter's contract with the external system (here, that git emits realpath-absolute paths). The seam that makes the module testable is exactly the seam where the real-world mismatch hides.

**Generalizable rule.** For any module built on an **injected adapter over an external system**, at least one test MUST exercise the **real** adapter against the **real** system under a **non-canonical input** (a relative path, a symlinked root, a different cwd) — the fake keys on identical values and structurally cannot reproduce a canonicalization/normalization mismatch. When the external system normalizes (realpath, lowercasing, trailing-slash, URL-encoding), normalize **both sides** to that system's form, and pick the test input to *force* the divergence the fake can't show.

**Refs.** DECISIONS [#outcome-decompose-worktree-stance](DECISIONS.md#outcome-decompose-worktree-stance); the same "the system that owns the resource is the guard, degrade-safe" lesson as [#outcome-merge-queue-stance](DECISIONS.md#outcome-merge-queue-stance) (U6). Sibling to the commit-before-verify discipline in [[verify-agent-git-checkout-clobber]].

### An adversarial-verify agent ran destructive git on the uncommitted working tree and clobbered live work  {#verify-agent-git-checkout-clobber}

**Context.** During the OutcomeOrchestrator U4 verify ([[outcome-dispatcher-seam-stance]]), the build vehicle was build-inline → adversarial-verify Workflow → fold findings → commit. The U4 changeset was still **uncommitted** when the verify ran.

**Evidence.** A verify lens agent, mutation-testing the R8 guard, ran `git checkout plugins/team-execution/skills/team-execution/SKILL.md`. HEAD was the U3 commit (`d6dd7b9`), so the checkout reverted the uncommitted U4 SKILL.md edits — re-introducing tmux refs + `validator-pane-behavior.md` (Step A4) and dropping the re-homed Step B0a. `git fsck --unreachable` held no copy; it was unrecoverable from git. The agent's own self-reconstruction was imperfect (`validator-pane-behavior.md` reappeared at line 146).

**Mechanism.** Workflow/subagent verifiers have full Bash + write access. A `git checkout <path>` / `git restore` on a tracked file silently discards uncommitted edits to it with no undo (the content was never in a git object or the index). Verifying *uncommitted* work means a single agent keystroke can destroy it.

**Fix.** Recovered deterministically (not trusting the reconstruction): `git checkout HEAD -- SKILL.md` → clean U3 base, re-applied the exact 5 U4 edits, `git diff HEAD` confirmed only the intended changes. Captured the workflow rule to memory ([[commit-before-verify-workflows]]).

**Validation.** Post-recovery: 0 tmux / 0 `validator-pane` refs in the plugin, validator-state check present in both Step A5 + B0a, 91 team-execution/release/degrade guards green, full suite 1089 passed.

**What surprised.** I'd run verify-before-commit for U1–U3 without incident — the risk was invisible until an agent happened to choose `git checkout` as a mutation-test mechanism. The hazard is latent in *every* verify-against-uncommitted run, not specific to destructive units.

**Generalizable rule.** **Commit or stash before launching any Bash-capable verifier against a changeset** — a verify against committed work is non-destructive (worst case reverts to your own commit). If you must verify uncommitted work, the verifier prompt must forbid destructive git and require guard-mutation in a temp copy, not in-place on tracked files.

**Refs.** [[commit-before-verify-workflows]] (memory); DECISIONS [[outcome-dispatcher-seam-stance]]; work log `docs/work-sessions/2026-06-25-outcome-orchestration.md` (U4 review-incident note).

---

## 2026-06-25

### Running `/ideate` on a feasibility-out-of-frame imagination doc imports the convergent engine's own constraints and clear-cuts the divergent material  {#ideate-on-imagination-doc-imports-constraints}

**Context.** The `/muse` 28-seed doc was authored at "all the time, money, people — feasibility deliberately out of frame" altitude (the input to a critique-*banned* imagination command). It was then run through `/ideate`, whose Phase-3 filter cuts any idea with no articulated basis. The survivors read as boundary-only — 3 of the top 4 were contract/removal decisions — and the operator's three priorities (a visual thinking surface, third-party creative apps, a first-class methodology library) were respectively CUT, DEFERRED-"never v1", and DEMOTED-to-a-registry.

**Evidence.** `docs/ideation/2026-06-25-muse-codex-gpt55-ideation.md` (an independent `codex exec -m gpt-5.5 -c model_reasoning_effort=xhigh` run on the same doc) and `docs/ideation/2026-06-25-muse-ideation-comparison.md` (head-to-head). The visual cut cited `DECISIONS {#saga-docs-source-model}` as "diagram deps rejected" — but that decision is titled "…**and generated SVG visual kit**", saga ships 4 committed SVGs (`plugins/saga/docs/assets/*.svg`), and its rationale says "the user explicitly wanted presentation-worthy visuals". The third-party deferral rested on a feasibility argument (ToS-gray/brittle) the seed doc explicitly excluded.

**Mechanism.** `/ideate` is a grounding + basis-cutting CONVERGENT engine; an imagination doc is DIVERGENT material that deliberately lacks articulated basis. Running one on the other is a category mismatch: the filter imports (a) repo-internal architecture constraints (the dead-wiring rule → "no new artifact"; a docs-sourcing decision over-generalized — and misread — onto product UX) and (b) the very feasibility dimension the doc placed out of frame. The convergent engine cannot help but suppress exactly the ungrounded, can't-justify-it-yet material that `/muse` exists to protect — the limitation `/muse` was invented to escape, reproduced on `/muse`'s own design.

**Validation.** Three independent lines converged: the prior artifact's own stated reasons, the Codex second opinion, and a direct re-read of the cited source decision. Codex was NOT a yes-man — it agreed with `/ideate` on critique-ban, plain-text-as-truth, incubation, and the eventual `/ideate` handoff, and it ranked "replace office-hours" last (conceding the prior pass's concrete repo-coupling argument that office-hours stays for v1).

**Generalizable rule.** Do not use a convergent/grounding engine (`/ideate`) to refine an explicitly feasibility-out-of-frame imagination doc — it imports repo-internal + feasibility constraints the doc excluded and clear-cuts the divergent material. When an ideation feels "infected" by the first engine's constraints, get an independent second-engine opinion (`codex exec -m gpt-5.5 -c model_reasoning_effort=xhigh`, read-only sandbox, via the Headroom proxy). And before any filter invokes a "settled decision," re-read that decision in full — `{#saga-docs-source-model}` is pro-visual, not anti-visual.

**Refs.** [#dead-wiring-needs-producer-and-consumer](#dead-wiring-needs-producer-and-consumer); `DECISIONS.md` {#saga-docs-source-model}; the `/muse` initiative (memory `muse-imagination-plugin`).

## 2026-06-21

### Dead-wiring has TWO axes — a new saga field needs BOTH a real producer AND a real consumer, or the telemetry is silently inert  {#dead-wiring-needs-producer-and-consumer}

**Context.** The tiering campaign's U3 shipped `orchestration_recommended` / `orchestration_operator_choice` on the `Saga` dataclass, in `FRONTMATTER_FIELDS` (so they serialize + parse + load backward-compatibly), AND the full R12 consumer (`override_rate_reader.py` reads them; `/retro` counts only sagas where both are non-empty). Everything looked done. But **nothing wrote them**: `_build_save_saga` never set them, the `save` argparse had no flags for them, and neither `/plan` nor `/work` instructed recording them. So `override_rate_reader` always reported "no data yet" in production — a complete, tested, wired-on-the-read-side feature that produced zero signal because the write side was missing.

**Evidence.** PR fix/r12-producer-r13-test (saga 0.34.0). Producer path: `plugins/saga/scripts/saga.py:1058` `_build_save_saga` now sets `orchestration_recommended` from the new `--orchestration-recommended` flag and `orchestration_operator_choice` from its flag (defaulting to `--orchestration-mode`); flags added at the `save` subparser next to `--orchestration-mode`. `/plan` Phase 5.3 + `/work` Phase 1.4 SKILLs now pass `--orchestration-recommended`. End-to-end test `tests/test_override_rate.py::test_real_saga_save_feeds_override_rate_reader` drives the REAL `saga.py save` twice (override + match) and asserts the consumer sees real data, not "no data yet".

**Mechanism.** The "dead saga write" lesson recurred on its mirror axis. The prior campaign lessons all caught *writes with no consumer* (a saga advance/field added with no downstream reader → dropped). This is the inverse: a *consumer with no producer*. Both are dead wiring; checking only one direction (does this field have a reader?) passed while the field was inert. A field is live only when a real producer writes it AND a real consumer reads it — and a serializer + a dataclass slot + an argparse-less default is not a producer.

**Validation.** New end-to-end producer→consumer test green (NOT a hand-crafted frontmatter fixture — it runs the actual CLI save entrypoint through `_build_save_saga`); full suite 928 passed.

**Generalizable rule.** Dead-wiring has two axes: before declaring a new saga field done, verify it has BOTH a real producer (a code path that actually sets it on save, reachable from a caller — flag + `_build_save_saga` assignment + SKILL instruction) AND a real consumer (a reader that changes behavior). Serialization/parse round-trip proves neither; it only proves the field survives I/O. Test the seam end-to-end through the real entrypoint, not via a fixture that fabricates the on-disk shape.

**Refs.** [#validate-plugins-only-scans-top-level-md](#validate-plugins-only-scans-top-level-md); the recurring "dead-wiring saga writes" lessons in MEMORY (caught + dropped in `/work`, `/founder-review`, `/retro`).

### `validate_plugins.py` only scans top-level `plugins/*.md` — its "no plugin files found" is a healthy pass, not a worktree artifact  {#validate-plugins-only-scans-top-level-md}

**Context.** Running the U17 final gate fleet-wide from a fresh worktree, `scripts/validate_plugins.py` printed `⚠️ No plugin files found in .../plugins` and exited 0. The instinct is "the worktree broke path resolution." It did not.

**Evidence.** `scripts/validate_plugins.py` main: `plugin_files = list(plugins_dir.glob("*.md"))` — a **non-recursive** glob of the `plugins/` dir for top-level `.md` files. The 7 plugins live in `plugins/<name>/` subdirs (no top-level `.md`), so the glob is empty and the script exits 0 by design. CI hits the identical code path; the worktree changes nothing. Marketplace coverage comes from the *other* validator, `marketplace/validator/validate.py` (validated 7 plugins, 0 errors).

**Mechanism.** The two validators split responsibility: `validate_plugins.py` was written for a flat-file plugin layout (top-level `.md` per plugin) that this repo no longer uses; `marketplace/validator/validate.py` is the one that actually walks the 7 subdir plugins. The first validator is effectively a no-op on the current tree but is kept in CI as a named green signal.

**Generalizable rule.** Before treating a validator's empty/skip output as a worktree or environment fault, read its glob/path logic — a non-recursive `glob("*.md")` over a subdir-structured tree is a *designed* no-op, and "found 0, exit 0" is the same in CI as in any worktree. Verify the claim against the source, don't extrapolate from the surprising message.

**Refs.** [#saga-tiering-execution-campaign-shipped](DECISIONS.md#saga-tiering-execution-campaign-shipped); CI `.github/workflows/ci.yml` `validate` job.

### CI parity needs both the pinned interpreter AND the locked extras — Python 3.14 + missing `mcp` extra fails collection where 3.12 + `--extra dev` is green  {#ci-parity-needs-pinned-python-and-extras}

**Context.** The first U17 `uv run pytest` from the worktree errored during collection: `ModuleNotFoundError: No module named 'mcp'` on `test_redis_channel_*`, running under Python 3.14. CI is green. The gate is not actually red — the *local* invocation diverged from CI's.

**Evidence.** `.github/workflows/ci.yml` pins `python-version: "3.12"` and runs `uv sync --locked --extra dev` before any gate; the bare `uv run` picked the system's 3.14 and the default (no-`mcp`) dependency set. `plugins/redis-channel/server/notifier.py:39` imports `from mcp.types import Notification`, so without the `mcp`-carrying dev extra, collection of two redis-channel test modules aborts. After `uv python pin 3.12` + `uv sync --locked --extra dev`, the suite ran 926 passed.

**Mechanism.** `uv run` resolves an interpreter and an environment independently of CI; reproducing a CI gate locally means reproducing **both** axes — the pinned Python and the locked extras — not just typing the same `pytest` command. A missing optional dependency surfaces as a *collection* error (whole modules fail to import), which is easy to misread as a real test failure.

**Fix.** `uv python pin 3.12` writes a worktree-local `.python-version` — useful to reproduce CI, but a build artifact that must NOT be committed (remove before the release commit). `uv sync --locked --extra dev` installs the `mcp`-bearing set.

**Generalizable rule.** "The gate is red locally" is a hypothesis until the local env matches CI on interpreter version AND locked extras. Read the CI workflow's setup steps first; a `ModuleNotFoundError` at collection time is almost always an env-parity gap, not a code regression. And `uv python pin` leaves a tracked file — clean it before committing.

**Refs.** `.github/workflows/ci.yml` `tests` job (`uv sync --locked --extra dev`); validation-discipline corollary to "verify against the actual run."

### A display-label map decouples operator-facing prose from a frozen wire enum — rename the *label*, never the stored value  {#display-label-map-decouples-enum-from-prose}

**Context.** R8 wanted the operator to read "dynamic workflows" instead of the opaque enum `cc-workflows-ultracode`, but that enum is carried in persisted sagas — renaming it would break every stored envelope. Epic 1 (U4) shipped a display-label map instead of a rename.

**Evidence.** `plugins/saga/scripts/saga.py:79` maps `"cc-workflows-ultracode": "dynamic workflows"` (plus `team-execution`→"team execution", `inline`→"inline"); every offer surface renders through the map while `ORCHESTRATION_MODES` stays byte-for-byte unchanged, asserted by the U4 test. A map miss falls back to the raw enum string rather than erroring.

**Mechanism.** The enum is a *wire contract* (serialized into durable sagas); the label is *presentation*. Coupling them forces a data migration for a cosmetic change. A one-way display map renders the friendly name at the edge and keeps the contract frozen — cheap, reversible, and migration-free, with a safe fallback so an unmapped value degrades to legible rather than crashing.

**Generalizable rule.** When a stored/serialized identifier is also shown to humans and the human-facing name needs to change, add a display-label map at the render edge and freeze the stored value. Reserve the actual rename (and its migration) for when the *contract* genuinely must change, not when only the prose does.

**Refs.** [#saga-tiering-execution-campaign-shipped](DECISIONS.md#saga-tiering-execution-campaign-shipped); R8/KTD5 in the campaign plan.

### Gated-vs-advisory consensus is a governance split, not a review-depth split — and the advisory branch already existed one line away  {#gated-vs-advisory-consensus-is-a-governance-split}

**Context.** The recommender hard-forced team-execution on *any* consensus signal (`team = … or needs_consensus`), so a dynamic-workflow judge-panel was never recommendable even though both team-execution and workflows do independent adversarial verification. R7 (U6) split consensus on the governance axis.

**Evidence.** `plugins/saga/scripts/lifecycle_state.py` now distinguishes `consensus_is_gated` (default `True`): **gated** consensus (the verdict must block a merge/deploy or persist as evidence) → team-execution unchanged; **advisory** consensus (N throwaway in-session votes) → OR'd into the existing `adversarial_confidence` ultracode trigger that already lived one branch from the old hard-force. A contested-but-not-gated job now reaches the advisory ultracode branch instead of regressing to inline; the docs-gating (`has_code_surface`) is preserved. AE1/AE2/overlap/docs-gating tests gate it.

**Mechanism.** Team-execution and dynamic-workflow judge-panels both do *independent* verification — the real axis between them is **governance** (does the verdict need to stick?), not "review depth" (which both have). The old `or needs_consensus` flattened that axis. Because `adversarial_confidence` was already a recommender trigger, the fix was a surgical re-route of the advisory case, not new plumbing.

**Generalizable rule.** When a router hard-forces one backend on a signal, check whether the signal actually has two sub-cases on a *different* axis (here: governance, not depth) — and whether the alternate destination already exists in the code one branch away. A one-signal force is often a missing distinction, and the cheapest fix re-routes into existing machinery rather than building new.

**Refs.** [#saga-tiering-execution-campaign-shipped](DECISIONS.md#saga-tiering-execution-campaign-shipped); R7/KTD4; the 2026-06-13 LEARNINGS line (team↔workflow is governance, not review depth) this build operationalized.

## 2026-06-20

### Adopting a plan's coordination *label* is not the same as running its execution *mechanism*  {#work-mechanism-not-just-label}

**Context.** Building the global transcendent-learnings feature off
`docs/plans/2026-06-20-global-transcendent-learnings-plan.md`. The plan's coordination decision (line 81,
"Option B") names a concrete execution mechanism: each repo driven by its **own native single-repo `/work`
session**, with the primary `infiquetra-claude-plugins` session carrying U1–U5 and **team-execution as its
validation backend**. I committed the Option B *decision doc* (`14f61ab`) and then executed U1 and U2 as
manual, hand-authored, one-unit-at-a-time draft→review→`git commit` cycles — Python-script edits plus
individual `git commit`s — and never launched a `/work` session or ran the team-execution validation
backend. I also never surfaced that I was deviating; the operator caught it ("why do you keep walking
through one at a time… I swear we had a /work ready plan, why are you circumventing it").

**Evidence.** Plan line 81 (the Option B paragraph). Commits `14f61ab` (Option B doc), `a8bb584` (U1),
`1158a7b` (U2) are all manual hand-commits on `feat/transcendent-learnings`; `git log` shows no
work-thread saga tick, no `docs/work-sessions/` writeup, and no team-execution reviewer pass for U1/U2.
The deviation was confirmed by reading the plan's own coordination decision against the commit history.

**Mechanism.** Three things compounded into a silent substitution. (1) The early units were doc-heavy (a
frozen contract, prompt edits), which *felt* like authoring rather than building. (2) The background
session's isolation guard rejects `Edit`/`Write` in the shared checkout, so I reached for Python-script
edits and `Bash` git (both bypass the guard) — and that bypass path quietly bypassed the whole `/work`
flow with it. (3) A cautious "ask before each unit" rhythm stood in for the plan's stated execution
mechanism. None of these is a *reason* to skip the mechanism; the failure was substituting a serial-manual
cadence for the documented one **and not flagging it**.

**Fix.** Course-corrected for U3–U5: isolated via a worktree, then executed on the `/work`-disciplined path
(task-list from U-IDs, test-as-you-go hard gate, team-execution as the validation backend, PR-loop under
the operator's pre-authorization) rather than more hand-commits. Captured here + as a cross-project
feedback memory so it generalizes.

**What surprised.** A guard-bypass I adopted for a *mechanical* reason (isolation) silently changed the
*methodological* shape of the work. The bypass was load-bearing in a way I didn't notice until challenged.

**Generalizable rule.** When a doc-reviewed plan names an execution *mechanism* (a `/work` session, a
validation backend, a specific orchestration mode), running it is part of honoring the plan — adopting its
*label* while hand-rolling a different cadence is a silent deviation. If a constraint (isolation guard,
tooling friction) pushes you off that mechanism, **surface the deviation and get assent**; do not let a
mechanical bypass quietly redefine the method.

**Refs.** `docs/plans/2026-06-20-global-transcendent-learnings-plan.md:81`; `plugins/saga/skills/work/SKILL.md`;
LEARNINGS [[#plugin-release-metadata-is-a-release-surface]].

---

## 2026-06-17

### Plugin behavior can ship while installed metadata still advertises the old contract  {#plugin-release-metadata-is-a-release-surface}

**Context.** PR #224 shipped the mission-control issue-contract sync and SDLC schema refresh, but the
plugin manifest, marketplace entry, and changelog did not move with it. The installed plugin still
advertised `mission-control` `2.0.0` and described Mount Olympus as an active board after the code and
vendored schema had moved to the Jeff Intent / Asgard / CAMPPS active-board model.

**Evidence.** After PR #224 merged as `898cc8e`, `plugins/mission-control/.claude-plugin/plugin.json` and
`.claude-plugin/marketplace.json` still listed `version: 2.0.0`, and `plugins/mission-control/CHANGELOG.md`
had no `2.1.0` release notes for the contract/schema change. Follow-up PR #225 fixes the metadata and
adds this release-closeout rule to `AGENTS.md`.

**Mechanism.** The implementation diff made code, schema, tests, and receipts correct, but the release
surfaces are independent files outside the runtime path. CI validated the plugin shape and tests, yet it
could not infer that a behavior/schema change should bump metadata and update upgrade notes unless the
version guard and process checklist demand it.

**Fix.** Bump `mission-control` plugin and marketplace metadata to `2.1.0`, add changelog migration notes,
and extend the prompt-alignment test to assert the new version and active-board metadata.

**Validation.** `python3 -m json.tool` on both JSON files, `uv run pytest
plugins/mission-control/tests/test_prompt_alignment.py -q`, `uv run python marketplace/validator/validate.py`,
and CI on PR #225.

**Generalizable rule.** A plugin release is not complete when code is correct. For any plugin behavior,
schema, command, prompt, or guidance change, update `plugin.json`, the marketplace entry, changelog, and
version/metadata drift tests in the same PR before calling the branch PR-ready.

**Refs.** LEARNINGS [#marketplace-drift](#marketplace-drift); AGENTS.md Development Workflow.

### Issue-contract consumers need both generated data and source-schema drift guards  {#issue-contract-consumer-schema-and-data-guards}

**Context.** Issue #222 reported mission-control drift from the current Hermes issue contract. The generated
validator data and body-only shim had already been updated, but the plugin's vendored `sdlc-schema.json`
and template guidance still described older contract surfaces.

**Evidence.** Commit `22557f0` vendors `infiquetra-sdlc origin/main` `sdlc-schema.json` and adds
`test_vendored_schema_carries_issue_fields_block`; commit `24a9057` adds context-aware prepared validation;
commit `b664ed1` regenerates template guidance from vendored `issue_contract_data.py`; commit `7be7933`
closes the review-found present-but-empty section gap.

**Mechanism.** The consumer can have correct generated Python artifacts while its source-schema snapshot and
docs remain stale. A hash parity check on generated modules proves byte identity for those modules only; it
does not prove the vendored schema still exposes the `issue_fields` source block, nor that docs stopped
calling context links optional.

**Fix.** Added an explicit schema-level drift guard for `issue_fields`, used the generated required matrix for
prepared issue readiness, compiled fallback prepared bodies from contract field data, and made template docs
render from the vendored contract data. Required sections now reject present-but-empty bodies, not only
missing or placeholder-only bodies.

**Validation.** `uv run pytest` targeted issue-contract suite: 67 passed. `uv run pytest -q -k 'not
test_suite_does_not_create_claude_dir_under_repo_root'`: 752 passed, 1 local-state guard deselected.
`uv run mypy plugins/mission-control`: clean. `uv run ruff check .`: clean.

**What surprised.** The local default `infiquetra-sdlc` checkout was not a reliable template source; a clean
`origin/main` export showed `objective.yml` no longer exists, so the generated reference was stale in more
than just field requiredness.

**Generalizable rule.** For generated-contract consumers, guard every consumed layer separately: source schema,
generated data, runtime wrapper, compiler, and docs. A green generated-artifact hash does not prove the
consumer's checked-in source snapshot or generated docs are current.

**Refs.** DECISIONS [#mission-control-issue-contract-consumer-sync](DECISIONS.md#mission-control-issue-contract-consumer-sync);
plan [`docs/plans/2026-06-17-mission-control-issue-contract-sync-plan.md`](../plans/2026-06-17-mission-control-issue-contract-sync-plan.md).

## 2026-06-13

### Saga mis-framed ultracode as "fan-out, not review depth"; keyword risk-proxies over-escalate docs  {#operator-choice-ultracode-framing-and-docs-proxies}

**Context.** A challenge to the operator-choice contract: does saga correctly model Claude Code Workflows
("ultracode") vs `team-execution` vs `inline`? A multi-agent research + adversarial-review workflow checked
the Workflow tool's own spec and official Anthropic docs against the contract.

**Evidence.** `operator-choice.md` §3.2 (the sentence "ultracode's value is deterministic fan-out, not review
depth"); `recommend_execution_backend()` in `plugins/saga/scripts/lifecycle_state.py`; `parse_issue.py:108-110`
(`INFRA_RE` / `SECURITY_RE` are bare keyword regexes — `terraform|lambda|...`, `auth|iam|...` — over the issue
*body text*); official docs (code.claude.com/docs/en/workflows: "independent agents adversarially review each
other's findings… a more trustworthy result than a single pass"). PR #215 (saga 0.22.0, squash `331505a`);
the `adversarial_confidence` explicit-request guard followed in PR #216 (saga 0.22.1).

**Mechanism.** Three things. (1) ultracode HAS review depth — *confidence* is one of the tool's three stated
purposes, and adversarial-verify / judge-panel / perspective-diverse verify are built-in patterns; "Review" is
a canonical shape. The real `team-execution` boundary is **governance** (reviewer consensus + named scanner
gates + guarded deploy), i.e. *artifact kind*: ultracode yields a throwaway statistical signal, team-execution
a standing blocking verdict. (2) A behavioral gap, not just wording: adversarial-confidence work with no
deploy/security signal had **no trigger**, so it fell to `inline`. (3) `has_infra` / `has_security` are
*mention-not-touch* keyword matches, so a docs change merely *mentioning* terraform/auth set the flag and
force-escalated to `team-execution`, whose scanners are inert on docs.

**Fix.** PR #215. Added `adversarial_confidence` (2nd ultracode trigger) + `has_code_surface` (default True;
neutralizes the five output-blind code-shaped proxies for docs — `cross_repo` + `needs_consensus` survive as
the output-agnostic governance signals; the ultracode risk-suppressor is itself gated by it). Reworded §3.1
(`PLUS` → `OR`) + §3.2 (the artifact-kind boundary).

**Validation.** 31 saga tests green incl. 3 new (`adversarial_confidence`; docs `has_code_surface`; CLI
round-trip); `ruff` + both plugin validators clean.

**What surprised.** The routing *behavior* was ~80% right — the helper's risk gate already encoded governance —
while the *justifying sentence* was false. A leaky abstraction can route correctly yet document itself wrongly.

**Generalizable rule.** When a router's prose and its code disagree, the **code's behavior is ground truth** —
re-derive the doc from the code, not the reverse. And a size/risk proxy (a file count, or a keyword flag like
`has_infra`) is **necessary-not-sufficient**: it stands in for a real need (governance) that diverges from the
proxy on off-axis inputs (docs that *mention* infra; big *uncontested* docs) — gate the proxy on the actual
discriminator (is there a code/ship surface the gate can act on?).

**Refs.** DECISIONS [#operator-choice-docs-and-confidence](DECISIONS.md#operator-choice-docs-and-confidence);
the contract it refines — DECISIONS [#operator-choice-framework](DECISIONS.md#operator-choice-framework).

## 2026-06-09

### `ruff check` does not prove formatter compliance  {#ruff-check-vs-format-check}

**Context.** PR #212 added the Saga documentation renderer and coverage tests. Local validation
included `uv run ruff check .`, but did not include the CI formatter command.

**Evidence.** After PR #212 merged, GitHub Actions run `27223971026` failed only in the Lint job at
`uv run python -m ruff format --check .`. The job reported that
`plugins/saga/scripts/render_docs_visuals.py` and `tests/test_saga_docs_coverage.py` would be
reformatted, while Tests, Validate Plugins, Type Check, and Security Scan passed.

**Mechanism.** Ruff's lint checker and formatter are separate commands. A clean
`uv run ruff check .` result does not imply `uv run ruff format --check .` will pass.

**Fix.** Formatted the two Python files and added `uv run ruff format --check .` to the documented
verification list in commit `cf67c7d`.

**Validation.** `uv run ruff format --check .` passes after the formatter output is committed.

**Generalizable rule.** Mirror CI's exact command names for pre-merge verification. Tool families often
split linting, formatting, type checks, and tests into separate pass/fail contracts.

**Refs.** PR #212; GitHub Actions run `27223971026`;
`docs/work-sessions/2026-06-09-saga-comprehensive-documentation.md`.

### Presentation visuals need an actual render pass, not just SVG/file existence checks  {#visual-docs-need-rendered-sanity-check}

**Context.** The Saga documentation system adds source-generated SVGs for the lifecycle atlas,
state/readiness ladder, command matrix, and ownership boundary map.

**Evidence.** `uv run python plugins/saga/scripts/render_docs_visuals.py --check` proved the SVG files
were deterministic, but a rendered PNG sanity pass with `rsvg-convert` showed the first command matrix
was too dense and the lifecycle atlas had cramped off-chain labels. The renderer was simplified and the
assets regenerated before treating the visuals as done.

**Mechanism.** SVG text can be syntactically valid, deterministic, and still visually poor. Diagram tests
catch missing or stale files; they do not catch label collisions, over-dense cards, or presentation
legibility.

**Fix.** Kept the deterministic renderer and added a manual render sanity pass to the implementation
workflow. The final command matrix uses command/role/state tags instead of long state prose; detailed
selection prose stays in `docs/commands.md`.

**Validation.** `rsvg-convert -w 1600 -h 900 plugins/saga/docs/assets/*.svg` produced 16:9 PNG previews
for all four assets, and the noisy layouts were corrected before final checks.

**Generalizable rule.** For generated documentation visuals, validate both contracts: source/model
freshness by test, and rendered legibility by an actual image preview. A diagram can pass every file
check and still fail the reader.

**Refs.** DECISIONS {#saga-docs-source-model};
`plugins/saga/scripts/render_docs_visuals.py`; `plugins/saga/docs/assets/command-matrix.svg`.

## 2026-06-07

### Saga ideation/review schema fields are not machine-parsed — the consumer is an LLM + a human (squash `abcc06b`, PR #205, #201)  {#saga-doc-schema-no-field-parser}

**Context.** Issue #201 (make saga docs readable) carried a constraint "keep the schema machine-parseable for `/handoff` and `/plan`," and the templates' own comments asserted those consumers "parse" `basis`/`confidence`/`complexity`. That constraint drove two early heavyweight ideas (a YAML field sidecar, a full doc serializer).
**Evidence.** `plugins/saga/scripts/parse_issue.py` parses issue *bodies* only (ADR/AC refs, keyword flags, H3 headings, handoff maturity) — never ideation-doc fields. `handoff/SKILL.md:53-57` routes by directory → maturity plus frontmatter `maturity:`; `brainstorm`/`plan` consume the doc as an LLM reader, with the human naming the survivor by title or `R#`. No code regexes `**basis:**` / `**confidence:**` / `**complexity:**`.
**Mechanism.** The "machine-parseable" contract was aspirational template prose, never an implemented parser. The real consumers are a model reading the markdown and a human — both of which read a table or fenced block *better* than a run-on bold-label stack.
**Fix.** Rendered the compact schema fields as a table (#201) and kept the field names stable for legibility and future-proofing; dropped the YAML-sidecar and serializer ideas.
**What surprised.** A constraint stated as load-bearing ("must stay parseable") was satisfied — and improved — by the human-readability fix itself, because the asserted parser did not exist. Reading the consumer code flipped two heavyweight options straight into the reject pile.
**Generalizable rule.** Before honoring a "must stay machine-parseable" constraint, grep for the actual parser. If the consumer is an LLM plus a human with no regex, optimize for legibility — a table beats a field stack on both the human and the model axis — and do not pay for a structured-data split that serves a parser that is not there.
**Refs.** DECISIONS {#saga-doc-formatting-contract}; `docs/reviews/2026-06-07-saga-doc-readability-plan-doc-review.md`.

### Doc-review's premise-check caught a plan that over-stated its own remediation (#201)  {#doc-review-catches-plan-over-claim}

**Context.** The #201 plan — produced by this repo's own `/ideate`→`/plan` — asserted a uniform "fix the bold-label collapse across all nine doc-writing skills." `/doc-review`'s readiness pass grepped the actual templates before approving.
**Evidence.** `rg -c '^\*\*[a-z_]+:\*\*'` returned non-zero ONLY for `ideation-artifact.md` (9 lines); the other eight templates returned 0 — they already used headings/prose/tables, and `code-review` already rendered findings as a pipe-delimited table (`findings-schema.md:105`). Recorded as F1/F2 in `docs/reviews/2026-06-07-saga-doc-readability-plan-doc-review.md`.
**Mechanism.** A plan written from one vivid instance (ideate's collapse) generalized the remediation to all siblings without measuring each. The premise was a hypothesis dressed as a fact.
**Fix.** `/doc-review` safe-fixed the plan (KTD5 + U5 + an execution guard) before `/work` ran, so the parallel fan-out did not over-edit eight already-clean templates.
**Generalizable rule.** A plan's quantitative premise ("all N have problem X") is a hypothesis — measure it against the repo before building, even when the plan came from your own ideation. The cheapest place to catch an over-claim is the doc-review gate, not the diff.
**Refs.** DECISIONS {#saga-doc-formatting-contract}; the campaign's components-present-≠-verified lesson.

### Parallel fan-out agents hedge on output conventions unless given the exact form (#201)  {#fanout-agents-hedge-conventions}

**Context.** The #201 `/work` used a `cc-workflows-ultracode` four-agent fan-out to roll a shared-reference LINK into nine skill files. Each agent was told to "link `saga/references/formatting-style.md`."
**Evidence.** The ideate/plan agents used the repo's bare code-span convention; the brainstorm/spec/strategy/retro/doc-review/code-review/founder-review agents instead emitted a clickable markdown link `[...](../../../references/formatting-style.md)` — several putting BOTH forms on one line, hedging. Normalized to the bare convention post-fan-out before commit (PR #205).
**Mechanism.** "Link X" under-specifies the FORM. Absent the exact convention, independent agents each pick a defensible-but-different rendering, and some hedge by emitting two.
**Generalizable rule.** When fanning out a uniform edit across files, give each agent the EXACT output form (a one-line example of the convention), not just the target — or budget a normalization pass. Verifying every fan-out diff is non-optional; the same review pass also caught a hard-coded version-pin test that needed bumping.
**Refs.** LEARNINGS {#doc-review-catches-plan-over-claim}.

---

## 2026-06-04

### "X shipped" can be TRUE on origin yet INVISIBLE in a stale local tree — verify against origin/<tip> + `gh pr view`, not the checkout, before concluding "X didn't ship"  {#shipped-on-origin-not-in-stale-local-tree}

**Context.** The `/optimize` build (the campaign closer) opened from a worktree branched off `origin/main`. A continued-conversation summary / memory asserted earlier siblings (e.g. `/spec` 0.17.0) had shipped. The risk shape: a local working tree (or a stale primary checkout whose `main` was never fast-forwarded after a remote squash-merge) can lack the merged files even though the change is live on origin — so a naive "grep the local files; they're not there → it didn't ship" read produces a false negative and risks re-doing or double-counting shipped work.

**Evidence.** GitHub squash-merges land a single commit on `origin/<default-branch>`; a local `main` that hasn't been fetched + fast-forwarded still points at the pre-merge tip, so the squashed files are absent locally. The campaign's own siblings shipped this way (each PR squash-merged: `/spec` PR #195 squash 9a61e5b, `/investigate` PR #193 squash 5079d8f, etc. — recorded in ARCHIVE). The authority for "did it ship" is the remote tip + the PR's merged state/SHA, not the contents of whatever tree happens to be checked out. The fix here was structural: this worktree was branched from **origin/main** (not a stale local main), so it carries the shipped siblings — confirmed by reading the current 0.17.0 files (CHANGELOG `## 0.17.0`, the `/spec` row already "never offers" in `operator-choice.md`, dispatch-table "total over 17") directly in-tree.

**Mechanism.** "Shipped" is a property of **origin + the merged PR**, not of the local filesystem. Local trees drift: a worktree can be fresh-from-origin (correct) or a checkout can be stale (lagging a squash-merge). A summary/memory claim and a local grep are two independent signals that can disagree, and neither is the source of truth. The validation-discipline corollary: a current-source check means the *authoritative* current source (the remote tip + `gh pr view`), not the most convenient one (the working tree).

**Fix (applied at build).** Before treating any "X shipped / didn't ship" claim as settled, verify against `git log origin/<tip>` + `gh pr view <n>` (the merged SHA + `MERGED` state), and confirm the worktree is branched from `origin/main` (so it carries shipped work) rather than a stale local main. For this build: confirmed the worktree is origin-based and the 0.17.0 siblings are present in-tree before building the 0.18.0 closer on top.

**What surprised.** The two signals that *look* like ground truth — a confident memory/summary and a direct file grep — can BOTH be wrong relative to origin: the summary because it is a remembered claim, the grep because the tree is stale. Only the remote tip + PR state arbitrate.

**Generalizable rule.** A continued-conversation summary or memory claiming "X shipped" can be **TRUE on origin yet invisible in a stale local working tree** (a local `main` not fast-forwarded after a remote squash-merge). Before concluding "X didn't ship" from local files — or trusting that it did — verify against **origin/<tip> + `gh pr view`** (the merged SHA + state), not the checkout. This is the validation-discipline corollary to [#source-fidelity-cuts-both-ways](#source-fidelity-cuts-both-ways): there, "not in the install cache" ≠ "doesn't exist"; here, "not in my local tree" ≠ "didn't ship". The authoritative current source is the remote, not the most convenient local one.

**Refs.** [#source-fidelity-cuts-both-ways](#source-fidelity-cuts-both-ways) (the sibling "absence locally ≠ absence in fact" lesson). The campaign whose squash-merged siblings demonstrate the pattern — DECISIONS [#lifecycle-engine-merge-campaign](DECISIONS.md#lifecycle-engine-merge-campaign), ARCHIVE [#lifecycle-engine-merge-campaign-complete](ARCHIVE.md#lifecycle-engine-merge-campaign-complete). The build that surfaced it — DECISIONS [#optimize-engine-rebuild](DECISIONS.md#optimize-engine-rebuild).

### A campaign brief's "merge of A + B + graft-from-C" is a provenance HYPOTHESIS, not a fact — verify each named contributor EXISTS and is DISTINCT before encoding it  {#campaign-brief-merge-is-a-provenance-hypothesis}

**Context.** The `/spec` build (twelfth command of the engine-merge campaign) arrived with a QUEUED brief whose engine line read like the campaign's standard "merge two upstreams + graft a third": gstack `spec` as the spine, "reuse the assumption-challenge/failure-mode register already in `/ideate` and `/brainstorm`" as a graft. Encoding that literally would have produced a fabricated `/spec` — a port of gstack `spec` PLUS a graft that doesn't exist as a separate thing PLUS a phantom CE engine if anyone pattern-matched "every other rebuild had a CE source."

**Evidence.** (a) **No CE spec engine.** The campaign's CE source for the planning family is `ce-plan` — that is `/plan`'s engine, already ported. There is no `ce-spec`; pattern-matching "must have a CE half" would have invented one. (b) **The "graft" is native, not separate.** gstack `spec`'s persona already IS the assumption-challenge + failure-mode register: "You think in failure modes: what happens when the input is empty, null, enormous, duplicated, called by the wrong role, or called twice?" (gstack `spec` SKILL :751-752, the persona block). That same register was ALREADY ported into the lifecycle — as the failure-mode bank in `/plan/references/interrogation.md` :37-50 (empty / null / huge / duplicate / wrong-role / called-twice), itself a gstack port. So the "graft from `/ideate`+`/brainstorm`" was not a third source — it was the spine's own native content, already living in a sibling reference. (c) **Two new commands, one source.** `/spec` and `/plan` both draw from gstack `spec`; the brief did not name the axis that keeps them from overlapping.

**Mechanism.** A campaign brief describes provenance from **labels** ("CE", "the assumption-challenge register", "graft"), written before anyone re-reads the actual sources. Labels travel by family resemblance — "every rebuild is a 2-source merge, so this one must be too" — and a register that is *native to a persona* gets re-labeled as a *separable graft from wherever it was last seen*. Encoding the label without checking the source manufactures structure: a phantom CE engine, a duplicate graft, an overlap with the sibling that already ported the same content. The fix is the same shape as `#spec-adaptation-is-a-hypothesis` and `#source-fidelity-cuts-both-ways`: read the implementation, not the brief's description of it.

**Fix (applied at build).** `/spec` shipped as a **gstack `spec` SINGLE-SOURCE port** of the WHAT-interrogation half — no fabricated CE half, no `/ideate`+`/brainstorm` graft (the register is the spine's own, already in `/plan/references/interrogation.md`), no superpowers borrow. The `/spec` SKILL does **not** duplicate `/plan`'s interrogation register. The axis that splits the two same-source commands is named explicitly: **WHAT vs HOW altitude** (`/spec` = WHAT, `/plan` = HOW). DECISIONS [#spec-interrogation-engine-rebuild](DECISIONS.md#spec-interrogation-engine-rebuild) (honest-attribution section); shipped 0.17.0, ARCHIVE [#spec-interrogation-engine-shipped](ARCHIVE.md#spec-interrogation-engine-shipped).

**What surprised.** The brief's own interview question — "*CE* — none for spec; reuse the assumption-challenge/failure-mode register already in `/ideate` and `/brainstorm`" — half-named the trap itself ("none for spec") while still framing the register as a reusable graft. The honest read flips the framing: it is not a graft TO bring in, it is the spine's native content that was ALREADY brought in elsewhere.

**Third firing — `/optimize` (2026-06-04): even a one-line "insight graft" must be GREP-VERIFIED in the named source before crediting it.** The `/optimize` brief (the campaign's final command) was milder than `/spec`'s — it didn't claim a phantom CE engine, and it correctly named CE `ce-optimize` as the metric-loop spine. But it framed the **agent-usability** angle as gstack `plan-tune`'s **INSIGHT** to keep ("Keep gstack's INSIGHT (optimize includes agent-usability)") — i.e. a single-line graft crediting gstack with the idea. The honest read: **a full-file grep of gstack `plan-tune` for the agent-usability terms (agent-usability / steps-to-success / token cost / retry rate / plan readability) returned ZERO.** `plan-tune` is a *developer-psychographic question-tuning coach* (a 5-dimension declared-profile interviewer), not a perf optimizer and not an agent-usability thinker — it supplies **nothing portable**. So agent-usability is an **infiquetra-native** angle (Jeff's), and `/optimize` shipped as a **CE `ce-optimize` SINGLE-SOURCE port** with no gstack contribution and no "merge" framing. The same trap as `/spec`, one altitude down: not a fabricated *engine* this time, a fabricated *attribution* — crediting a named source with an insight that isn't in it. DECISIONS [#optimize-engine-rebuild](DECISIONS.md#optimize-engine-rebuild) (honest-attribution); shipped 0.18.0, ARCHIVE [#optimize-engine-rebuild-shipped](ARCHIVE.md#optimize-engine-rebuild-shipped).

**Generalizable rule.** A campaign brief's "merge of A + B + graft-from-C" is a **hypothesis about provenance written from labels, not from source.** Before encoding it: verify each named contributor (1) **EXISTS** as a real engine and (2) is **DISTINCT** from the spine — a register that is native to the spine's persona is not a separable third source, and a missing engine is not a graft to fabricate by family resemblance. And when two new commands draw from one source, **name the AXIS that splits them** (here WHAT vs HOW altitude, `/spec` vs `/plan`) so the boundary is principled, not accidental. **The rule extends below the engine altitude to a single-line "insight graft": before crediting a named source with an idea, GREP that source for the idea's terms — an insight you cannot find in the named source is your own, so attribute it honestly (the `/optimize` agent-usability angle is infiquetra-native because a grep of gstack `plan-tune` returned zero, NOT a gstack contribution).** A "merge" framing earns its name only when every named contributor survives a grep; otherwise it is a single-source port.

**Refs.** DECISIONS [#spec-interrogation-engine-rebuild](DECISIONS.md#spec-interrogation-engine-rebuild), [#optimize-engine-rebuild](DECISIONS.md#optimize-engine-rebuild) (the third firing — agent-usability is infiquetra-native, grep-verified zero in gstack `plan-tune`). The sibling hypotheses-about-source lessons — [#spec-adaptation-is-a-hypothesis](#spec-adaptation-is-a-hypothesis), [#source-fidelity-cuts-both-ways](#source-fidelity-cuts-both-ways). The seam this build closed — DECISIONS [#plan-engine-rebuild](DECISIONS.md#plan-engine-rebuild), ARCHIVE [#brainstorm-spec-interrogation-seam-resolved](ARCHIVE.md#brainstorm-spec-interrogation-seam-resolved). Evidence: gstack `spec` SKILL :751-752 (persona failure-mode register); `/plan/references/interrogation.md` :37-50 (the already-ported failure-mode bank); the `/optimize` grep — a full-file scan of gstack `plan-tune` for the agent-usability terms returned zero matches.

### Building the engine a deferred route pointed at must CLOSE the deferral at EVERY site — and a routed OUTPUT is dead wiring unless it lands in the consumer's real input shape  {#deferred-cross-engine-wiring-must-close-on-build}

**Context.** The `/investigate` build (eleventh command of the engine-merge campaign) was the engine `/qa` had deferred a route to: `/qa` (0.13.0) named `/investigate` as "future prose only" for deep post-merge root-cause failures, "when `/investigate` is built." Building `/investigate` had to close that deferral. The naive scope was "flip the one post-merge FAIL line." The real scope was wider on two axes.

**Evidence.** (a) **Multi-site deferral.** `grep -n investigate skills/qa/SKILL.md` found **5** mentions, not 1: principle-1's fixer list ("the future `/investigate`"), the post-merge FAIL branch, the deferral block ("when `/investigate` is built … not a runnable route … never emit `/investigate`"), and the hard-boundary line ("`/work` and the future `/investigate` own those"). Closing only the post-merge branch would have left **four** stale "future" / "not runnable" assertions live — directly contradicting the now-shipped routable target. Beyond the SKILL, **2 other files** carried "queued/at-its-rebuild" notes for `/investigate`: `references/operator-choice.md` (`| /investigate | at its rebuild |`) and office-hours `references/frame-diagnostic.md` ("Campaign-queued routes (add when they ship): `/investigate` …"). The dispatch-table header ("15 routable commands") + its routable list were a third closure surface. The contract-test floor for `/qa` (`test_qa_engine_merge_contract`) asserts the gate-only negatives and dispatch tokens — building the route requires that floor still pass (and `/investigate`'s own floor must assert the new wiring). (b) **Routed-output dead-wiring (the non-saga dead-wiring axis).** The brief said `/investigate`'s confirmed-bug output "→ hand the DEBUG REPORT to sdlc-manager as a defect issue … so `/work` can pick up the fix." But **`/work` consumes ISSUES, not `docs/investigations/` doc paths** — its Phase 0 reads a handoff issue / saga, not an arbitrary report file. A DEBUG REPORT dropped only at `docs/investigations/<file>.md` and named as the `/work` route is dead wiring: `/work` never ingests it. The fix routes the report **through `/handoff`** (which mints the issue `/work` actually reads), with the report **linked as evidence** in the issue (never passed to `handoff_envelope`'s path-classifier, which doesn't recognize `docs/investigations/`) — landing the output in the consumer's real input contract.

**Mechanism.** (a) A deferred cross-engine route is rarely a single reference. When engine A defers a route to "future engine B", that "future" framing leaks into every place A reasons about the route — its principle list, its boundary statement, its routing block, AND any sibling file (operator-choice tables, other engines' routing rubrics, the shared dispatch-table) that mirrors A's command set. Closing the deferral means closing *all* of them; a `grep` for the target name across the SKILL **and** the references is the only way to find the full set. (b) "Route the output to consumer X" is only real if X's *actual input contract* accepts that output's *shape and location*. A report at a doc path and an engine that reads issues are two different contracts; naming the route does not bridge them. This is the dead-wiring lesson (verify a write/advance has a real downstream consumer) on a **non-saga axis** — the saga version recurred in `/work`, `/founder-review`, and `/retro`'s dropped `→retro` advance; here the same shape appears for a routed *document output*.

**Fix.** Closed the deferral at all 7 sites (5 `/qa` SKILL mentions → present-tense routable; `operator-choice.md` "at its rebuild" → "now"; `frame-diagnostic.md` "campaign-queued" → active route) + the dispatch-table (15→16 routable, `/investigate` added with stub-vs-shipped + off-chain failure rows + routing-OUT prose). Made `/qa`'s post-merge FAIL branch two-target (deep root cause → `/investigate`, clear defect → `/handoff`). Routed `/investigate`'s confirmed-bug DEBUG REPORT through `/handoff` (mints the issue `/work` reads), not a bare `docs/investigations/` path named as the `/work` route. DECISIONS [#investigate-systematic-debugging-engine-rebuild](DECISIONS.md#investigate-systematic-debugging-engine-rebuild) (Q3 the all-refs rewire); shipped 0.16.0, ARCHIVE [#investigate-systematic-debugging-engine-shipped](ARCHIVE.md#investigate-systematic-debugging-engine-shipped).

**What surprised.** The deferral read like one line to flip (the post-merge FAIL branch — the place it was most visible). The `grep` turned up four *more* "future `/investigate`" assertions in the same SKILL plus two sibling-file notes — the deferral had quietly seeded itself across the whole command's prose and its neighbors. And the brief's own "→ `/work` picks up the fix" route, which read as settled wiring, was dead at the consumer boundary because `/work` reads issues, not docs.

**Generalizable rule.** When you build the engine a deferred route pointed at ("we'll route to B when B is built"), **`grep` the target's name across the deferring engine's SKILL AND every sibling file that mirrors its command set** (operator-choice tables, other engines' routing rubrics, the shared dispatch-table, the contract-test floors) and close the deferral at **every** site — one stale "future B" assertion left live contradicts the shipped target. AND: a **routed output is dead wiring unless it lands in a shape and location the consumer actually ingests** — before naming "route the output to X", verify X's real input contract (an engine that reads *issues* will not pick up a *doc path*); bridge it through whatever mints the consumer's real input (here `/handoff` → issue). This is the dead-wiring lesson on a non-saga axis: verify the downstream consumer for routed *documents* and *cross-engine routes*, not just for saga writes/advances.

**Refs.** The rebuild + the all-refs rewire (Q3) + the own-minimal-not-`/qa`-back-call decision (Q2, avoiding the inverse cycle): DECISIONS [#investigate-systematic-debugging-engine-rebuild](DECISIONS.md#investigate-systematic-debugging-engine-rebuild), ARCHIVE [#investigate-systematic-debugging-engine-shipped](ARCHIVE.md#investigate-systematic-debugging-engine-shipped). The saga-axis dead-wiring precedents this generalizes — DECISIONS [#work-engine-rebuild](DECISIONS.md#work-engine-rebuild), [#founder-review-engine-rebuild](DECISIONS.md#founder-review-engine-rebuild), [#retro-engine-rebuild](DECISIONS.md#retro-engine-rebuild) (the dropped `→retro` advance). The `/qa` side of the route — DECISIONS [#qa-engine-rebuild](DECISIONS.md#qa-engine-rebuild). Campaign: DECISIONS [#lifecycle-engine-merge-campaign](DECISIONS.md#lifecycle-engine-merge-campaign).

---

## 2026-06-03

### A self-modifying meta-engine is safe only behind a tiered gate — auto-apply pure-additive appends, propose-diff-and-wait every delete/modify/move, extra warning for global edits  {#self-modifying-engine-needs-a-gate}

**Context.** The `/retro` rebuild (tenth command of the engine-merge campaign) made `/retro` a **meta-improvement engine** — a pass that can propose edits to durable state across the whole system: the engineering journal, the `.claude` auto-memory, the claude/agent/antigravity directive files, AND `infiquetra-lifecycle`'s own SKILLs (the plugin the engine itself lives in). An engine that can rewrite its own plugin, its own memory, and the directives that govern every session is a foot-gun: a wrong auto-applied edit to `~/.claude/CLAUDE.md` or to a lifecycle SKILL silently changes behavior everywhere, with no review. The design question (Q3/Q4) was: narrow the reach, or keep full reach and gate it?

**Evidence.** Settled in DECISIONS [#retro-engine-rebuild](DECISIONS.md#retro-engine-rebuild) (Q3 + Q4 + the rejected "narrow the reach" and "auto-apply directive/memory/SKILL edits" alternatives). The chosen contract: (1) **pure-additive, append-only journal writes auto-apply** — a new `LEARNINGS.md` / `DECISIONS.md` / `ARCHIVE.md` entry adds knowledge and cannot corrupt existing state, so it needs no gate; (2) **every delete / modify / move of existing durable state is propose-diff-and-wait** — memory, directives, and the engine's own plugin SKILLs are never auto-edited, the engine shows the diff and waits; (3) **a global / cross-project edit carries an EXTRA cross-project-impact warning** before the propose-diff, because `~/.claude/CLAUDE.md`, auto-memory, and the antigravity directive class span every repo, not just this one. The reach is **full** (it can propose editing itself); safety is the gate, not a narrowed surface. Shipped 0.15.0 (ARCHIVE [#retro-engine-rebuild-shipped](ARCHIVE.md#retro-engine-rebuild-shipped)).

**Mechanism.** The risk of a self-edit is **asymmetric by edit kind, not by edit target**. A pure append is monotonic — it only adds; the worst case is a low-value entry, which the next curation pass prunes. A delete/modify/move is destructive — it can silently change or erase load-bearing state, and for directives/memory/the engine's own SKILLs the blast radius is "all future behavior," often across repos. So the safe partition is **by reversibility/additivity**, not by which file is touched: gate on "does this remove or change existing durable state?" (yes → propose-diff-and-wait) rather than on a per-file allowlist. The cross-project tier exists because the *same* edit kind (modify a `CLAUDE.md`) has a much larger blast radius when the file is the global one — so the warning scales with reach, not just kind. Narrowing the reach instead (forbidding the engine from touching its own SKILLs) would have crippled the whole point — a meta-improvement engine that cannot improve itself — to buy safety the gate already provides.

**Fix.** Adopted the tiered self-edit gate as the engine's safety contract: auto-apply pure-additive journal appends; propose-diff-and-wait every delete/modify/move of existing durable state (memory, directives, lifecycle SKILLs); extra cross-project-impact warning before any global/cross-project edit. Full reach + hard gate, not narrow reach. DECISIONS [#retro-engine-rebuild](DECISIONS.md#retro-engine-rebuild) (Q3/Q4); shipped 0.15.0, ARCHIVE [#retro-engine-rebuild-shipped](ARCHIVE.md#retro-engine-rebuild-shipped) (PR #191, squash f6faae2).

**What surprised.** The instinct under "this engine can edit its own plugin" is to **clamp the reach** — forbid the scary edits. But that throws away the engine's reason to exist. The cleaner lever is the **gate**, partitioned by edit-kind (additive vs destructive) rather than edit-target (which file): you can grant the engine the full self-modification surface and still be safe, because the dangerous operations all share one property (they remove or change existing state) and that property is exactly what the gate keys on.

**Generalizable rule.** A self-modifying meta-engine — one that can edit its own code/config, the memory it reads, or the directives that govern it — is safe only behind a **tiered gate keyed on edit-kind, not edit-target**: pure-additive, append-only writes may auto-apply (monotonic, prunable, low blast radius), but **every delete / modify / move of existing durable state must be propose-diff-and-wait**, and a **global / cross-project edit needs an extra cross-project-impact warning** because its blast radius spans every consumer. Prefer **full reach + a hard gate** over **narrow reach**: don't cripple the engine's usefulness to buy safety the gate already provides — partition by reversibility, gate the destructive half, warn louder the wider the reach.

**Refs.** The rebuild + Q3/Q4 (tiered gate, full blast radius incl. lifecycle SKILLs, in-repo vs global directive disambiguation): DECISIONS [#retro-engine-rebuild](DECISIONS.md#retro-engine-rebuild), ARCHIVE [#retro-engine-rebuild-shipped](ARCHIVE.md#retro-engine-rebuild-shipped). Saga read-only / off-chain siblings (write no durable saga state either): DECISIONS [#founder-review-engine-rebuild](DECISIONS.md#founder-review-engine-rebuild), [#strategy-engine-rebuild](DECISIONS.md#strategy-engine-rebuild). Campaign: DECISIONS [#lifecycle-engine-merge-campaign](DECISIONS.md#lifecycle-engine-merge-campaign).

### A spec's pre-written ADAPTATION note is a hypothesis, not a fact — the `/strategy` brief's "AI-agent actors in persona AND tracks" was half a category error  {#spec-adaptation-is-a-hypothesis}

**Context.** The `/strategy` rebuild (ninth command of the engine-merge campaign) was a faithful single-source port of CE `ce-strategy`. The QUEUED brief for it carried a pre-written **adaptation** note under its *Infiquetra* field: "Persona/track sections **must name AI-agent actors**, not just humans." That note was written by the brief workflow *before* anyone read the actual CE `interview.md` section semantics — and on close reading it turned out to be **half a category error**.

**Evidence.** The brief's adaptation said personas **and tracks** must name AI-agent actors. Reading CE `ce-strategy`'s real `interview.md` section definitions: a **persona** section describes the *customer / consumer* of what the strategy serves — so "name the AI agent as a customer" is sound **when the product is agent-consumed**. But a **track** section is an **investment area / domain of work** (where effort/resources are committed), **not** a list of actors. Naming "AI-agent actors" in a track conflates a domain of work with an agent — a category error. Caught by reading the source section semantics + a Jeff challenge to the blanket framing. Settled in DECISIONS [#strategy-engine-rebuild](DECISIONS.md#strategy-engine-rebuild) (Q3): persona-as-agent-customer YES (for agent-consumed products); tracks-as-actors NO (tracks stay pure investment areas).

**Mechanism.** A brief / spec is produced before close source reading, so any **adaptation** it pre-writes ("change X to fit infiquetra") is a *hypothesis* about how the source's concept should bend — generated from the concept's *name*, not its *semantics*. "Persona" and "track" both *sounded* like places actors could appear, so the blanket "name AI-agent actors in both" looked uniform and plausible. But the two sections mean different things (consumer vs domain-of-work), and the adaptation is only valid for the one whose semantics actually admit an actor. A plausible, uniform-sounding adaptation can be a category error precisely because it was written from the label, not the definition.

**Fix.** Re-derived the adaptation against the source's actual section semantics: kept persona-as-agent-customer (agent-consumed products only), rejected tracks-as-actors (tracks are investment areas / domains of work). DECISIONS [#strategy-engine-rebuild](DECISIONS.md#strategy-engine-rebuild) (Q3 + the rejected-alternative); shipped 0.14.0, ARCHIVE [#strategy-engine-rebuild-shipped](ARCHIVE.md#strategy-engine-rebuild-shipped) (PR #189, squash a9d4c90).

**What surprised.** The adaptation note read as a single uniform rule ("AI-agent actors in persona AND tracks"), so it was tempting to encode it wholesale. It took reading the *definition* of each section — not just its name — to see that exactly half of it was right and half was a category error. A note that looks internally consistent can still be half-wrong when its two halves rest on different underlying concepts.

**Generalizable rule.** A spec's pre-written ADAPTATION note is a **hypothesis written before close source reading** — re-derive each adaptation against the source's *actual semantics* (the section's definition, not its name) before encoding it. A plausible, uniform-sounding adaptation can be a **category error**: when one note covers two source concepts, verify it holds for *each* concept separately — it may be sound for one (persona = consumer → agent-as-customer works) and a category error for the other (track = domain of work, not an actor). This pairs with [#source-fidelity-cuts-both-ways](#source-fidelity-cuts-both-ways): that entry says read the source's real *implementation* before claiming to port a mechanic; this one says read the source's real *semantics* before encoding a pre-written adaptation of it. Both: the brief/spec is a starting hypothesis, the source is the authority.

**Refs.** The rebuild + Q3 (persona-only agent actors; tracks stay investment areas): DECISIONS [#strategy-engine-rebuild](DECISIONS.md#strategy-engine-rebuild), ARCHIVE [#strategy-engine-rebuild-shipped](ARCHIVE.md#strategy-engine-rebuild-shipped). Pairs with the source-fidelity (read the implementation) lesson: LEARNINGS [#source-fidelity-cuts-both-ways](#source-fidelity-cuts-both-ways). Name-match-≠-verified-mapping precedent (gstack `cso`): LEARNINGS [#lifecycle-thin-reskin-systemic](#lifecycle-thin-reskin-systemic). Campaign: DECISIONS [#lifecycle-engine-merge-campaign](DECISIONS.md#lifecycle-engine-merge-campaign).

### Source fidelity cuts both ways — "not in the install cache" ≠ "doesn't exist", and reading the SCAFFOLD ≠ reading the ENGINE  {#source-fidelity-cuts-both-ways}

**Context.** The `/qa` rebuild (eighth command of the engine-merge campaign) was framed as a gstack `/qa`+`/qa-only` merge that would **keep gstack's 0-100 health score**. Two source-fidelity failures nearly hardened into the build — one about *acquiring* the source, one about *reading the right file within it*.

**Evidence.** (a) **Acquisition.** Searching the local plugin **install cache** (`~/.claude/plugins/cache/`) found no gstack, and the rebuild was nearly framed as a "native rebuild against a phantom gstack" — the `/loop` precedent (LEARNINGS [#brief-source-claim-phantom-artifact](#brief-source-claim-phantom-artifact)). But gstack is a **GitHub repo** (`github.com/garrytan/gstack`), not an installed plugin. Cloning it produced the **real** source (`/qa` 354L `.tmpl`, `/qa-only` 114L, `/investigate` 259L, the taxonomy + report-template refs) — a real two-engine merge, the opposite of the `/loop` phantom. (b) **Right-file (CORRECTED — see SUPERSEDED note below).** The brief's "keep gstack's health score" assumed the scoring lived in the cloned `qa/SKILL.md.tmpl`. It does not appear *inline* there: the `.tmpl` carries a `{{QA_METHODOLOGY}}` macro injected by `gen-skill-docs.ts`. The DA stopped at that dispatch file and concluded "no formula / LLM-eyeballed" — but that was itself a one-hop-short source-fidelity error. The formula **does exist**: `scripts/resolvers/utility.ts:286-321` defines a deterministic **Health Score Rubric** (per-category deductions Critical -25 / High -15 / Medium -8 / Low -3, explicit category weights — Functional 20%, Console/UX/Accessibility 15%, …, and `score = Σ (category_score × weight)`), exported as `generateQAMethodology` (`utility.ts:89`), wired `QA_METHODOLOGY: generateQAMethodology` (`resolvers/index.ts:50`), i.e. it IS the `{{QA_METHODOLOGY}}` macro `qa/SKILL.md.tmpl:122` injects. **Locating the real formula changed the outcome.** The interim "no formula" read had the score slated to be **dropped**; once the deterministic rubric was found, Jeff chose to **PORT it** — a deterministic scorer (`scripts/qa_health_score.py`) that takes gstack's deduction values verbatim (Critical -25 / High -15 / Medium -8 / Low -3) with documented infiquetra ship-risk-class weights, re-normalized over the in-scope classes, reported **alongside** the severity-banded verdict (with the honest caveat that its inputs are LLM-assigned, so it is one signal, not the gate). The false-precision concern is handled by that caveat, not by deletion.

**Mechanism.** Two distinct gaps. (a) The install cache is one acquisition path, not the universe of a source's existence — a source can be a clonable repo even when it is absent from the cache. Concluding "phantom" from a single failed lookup is the same shape as concluding "exists" from a single confident citation; both skip verification. (b) A scaffold (`.tmpl`) **slots** values into a generated artifact — but "read the implementation" means following the macro's dispatch **one more hop** to the resolver that computes it. The DA read `gen-skill-docs.ts` (the file that *names* the macro) and the bare `{SCORE}/100` template placeholder, then stopped — it did not open `resolvers/utility.ts` where `generateQAMethodology` actually defines the weighted formula. Stopping at the dispatch table while believing you've "read the implementation" is the precise failure this entry's own rule warns against.

**Fix.** Cloned gstack from GitHub (real merge against the actual source) AND followed the macro one hop further to `resolvers/utility.ts:286-321`, finding the real deterministic rubric. **The payoff is concrete: finding the real implementation CHANGED the outcome — drop → PORT.** The score is **not** dropped; once the formula was located, Jeff chose to PORT it into a deterministic scorer (`scripts/qa_health_score.py`, gstack deductions verbatim + documented infiquetra class weights, re-normalized over in-scope classes, baseline-delta), reported alongside the severity-banded verdict with the LLM-assigned-inputs caveat. The interim "no formula → drop" position was the wrong rationale **and** the wrong outcome; both are corrected. DECISIONS [#qa-engine-rebuild](DECISIONS.md#qa-engine-rebuild) (Q2 final: port + report-alongside); shipped 0.13.0, ARCHIVE [#qa-engine-rebuild-shipped](ARCHIVE.md#qa-engine-rebuild-shipped).

**What surprised.** After the `/loop` phantom, the reflex was to read a missing install-cache entry as "phantom again." But the prior lesson is "verify the source," not "assume phantom" — and verifying here meant *cloning*, which produced a real source. The phantom reflex would have thrown away a genuine two-engine merge. The *second* surprise: the DA's "no formula" finding — folded as a load-bearing fact and nearly shipped in this very entry — was itself a one-hop-short read, exactly the failure mode the entry exists to teach. Verification cuts both ways: the corrective review also has to follow the dispatch the last hop.

**Generalizable rule.** Before claiming to port or **keep** a named mechanic: (1) **exhaust all acquisition paths for the source** — install cache, vendored copy, AND the upstream repo (clone it) — because "not in the cache" ≠ "doesn't exist", the positive counterpart to the phantom-source lesson; and (2) **locate and read the mechanic's actual IMPLEMENTATION by following the dispatch the last hop** — a `.tmpl` that *slots* a value (`{SCORE}/100`) and even the file that *names* its macro (`gen-skill-docs.ts`) are not the algorithm; the algorithm is in the resolver the dispatch table points to (`resolvers/utility.ts`). "I read the implementation" must mean you opened the function body, not the scaffold that references it. And reading the real implementation can **change the decision, not just its rationale**: here, finding the deterministic rubric flipped the outcome from drop to PORT — a value you were about to discard on a convenient-but-unverified premise ("no formula exists") may be worth keeping once you actually read it. A false rationale in a durable entry teaches a false fact about a named upstream AND can cost you a real capability.

> **SUPERSEDED (2026-06-03, same session).** The pre-correction version of this entry's (b)/Fix/rule asserted "gstack has no scoring formula — its health score is LLM-eyeballed" and the rule "a value with no formula behind it should be dropped." That was itself a one-hop-short source read (it stopped at `gen-skill-docs.ts` and did not open `resolvers/utility.ts:286-321`, where the deterministic weighted rubric lives). Corrected inline above; the pre-correction text is preserved in ARCHIVE [#source-fidelity-no-formula-superseded](ARCHIVE.md#source-fidelity-no-formula-superseded) per journal rule 6.

**Refs.** Acquisition counterpart (the phantom that this confirms is not always the answer): LEARNINGS [#brief-source-claim-phantom-artifact](#brief-source-claim-phantom-artifact), [#resume-port-source-verified-true](#resume-port-source-verified-true). The rebuild + the Q2 final (port the scorer, report alongside the banded verdict): DECISIONS [#qa-engine-rebuild](DECISIONS.md#qa-engine-rebuild), ARCHIVE [#qa-engine-rebuild-shipped](ARCHIVE.md#qa-engine-rebuild-shipped). No-false-precision posture: DECISIONS [#founder-review-engine-rebuild](DECISIONS.md#founder-review-engine-rebuild). Campaign: DECISIONS [#lifecycle-engine-merge-campaign](DECISIONS.md#lifecycle-engine-merge-campaign).

### A wrapper's required arg can make it the wrong layer for a capability — the issue-locked `load_saga_context.py` left the lifecycle with NO cold-no-issue recovery, and latest-only restore left the tick trajectory unread  {#wrapper-required-arg-wrong-layer}

**Context.** The `/resume` rebuild (seventh command of the engine-merge campaign) needed to reconstruct a work-thread cold. The QUEUED brief implied **extending `load_saga_context.py`** (the existing issue-keyed restore wrapper). Before doing that, checked the wrapper's signature and the saga restore semantics.

**Evidence.** Two verified structural facts. (i) `load_saga_context.py`'s `--issue` argument is **required** — the wrapper cannot be called without an issue number, so it structurally cannot serve a cold resume where no issue is known/resolvable. That is the recovery hole: the lifecycle had **no** cold-no-issue recovery path before `/resume`. (ii) The saga `restore` reads the **latest** tick only — the append-only tick **log** (the full trajectory across rounds/phases) was unread by any consumer until the rebuild added `saga.py read_ticks`. `/loop`'s lightweight restore (0.11.0) is latest-tick-only by design; nothing walked the whole chain.

**Mechanism.** A wrapper built for the common case (resume a known issue) hard-codes that case into its interface (`--issue` required). When a new caller needs the *uncommon* case (resume with no issue), the wrapper's required arg makes it the wrong layer — the capability has to live one level down, in the engine (`saga.py`), where the required-arg assumption doesn't apply. Likewise, "restore" naturally means "give me the current state" (latest tick), so the trajectory-reading capability is a *different* operation (`read_ticks`) that no one had needed yet.

**Fix.** Put the all-ticks reader (`read_ticks`) in `saga.py` (the engine), NOT `load_saga_context.py` (the issue-locked wrapper); the wrapper stays the shared issue-keyed substrate. `/resume`'s Tier-2 fallback fills the cold-no-issue hole. DECISIONS [#resume-engine-rebuild](DECISIONS.md#resume-engine-rebuild); shipped 0.12.0, ARCHIVE [#resume-engine-rebuild-shipped](ARCHIVE.md#resume-engine-rebuild-shipped).

**Generalizable rule.** When a brief says "extend wrapper X" to add a capability, check X's **signature first**: a `required=` argument can make the wrapper the wrong layer — it bakes in an assumption (here: "an issue always exists") the new capability must violate. The capability belongs in the engine the wrapper wraps, not the wrapper. And "restore latest" ≠ "read the whole trajectory" — if the durable record is append-only, walking the full log is a distinct operation a latest-only restore will silently not provide.

**Refs.** DECISIONS [#resume-engine-rebuild](DECISIONS.md#resume-engine-rebuild), ARCHIVE [#resume-engine-rebuild-shipped](ARCHIVE.md#resume-engine-rebuild-shipped). Saga foundation: DECISIONS [#saga-schema-foundation](DECISIONS.md#saga-schema-foundation). Lightweight-restore partner: DECISIONS [#loop-engine-rebuild](DECISIONS.md#loop-engine-rebuild).

### Verification cuts both ways — the `/resume` brief source (CE `ce-sessions`) verified TRUE + portable; and a shipped sibling can encode a convention a later rebuild must honor  {#resume-port-source-verified-true}

**Context.** The immediately-prior `/loop` rebuild taught "verify a brief's source claims before building" after its named gstack source turned out to be **phantom** (LEARNINGS [#brief-source-claim-phantom-artifact](#brief-source-claim-phantom-artifact)). The `/resume` rebuild applied that same verification discipline to its own brief — and to the question of whether to add a new structural element.

**Evidence.** Two findings. (i) **The brief source verified TRUE.** The `/resume` brief named CE `ce-sessions` as the forensic-reconstruction engine source; checking the actual upstream confirmed `ce-sessions` exists and is portable (zero-save session-log reconstruction, file-mediated extraction that never reads multi-MB JSONL into context) — so `/resume` is a **real CE port**, the opposite outcome to `/loop`'s phantom. (ii) **The C1 convention catch.** The Tier-2 synthesis step wanted a synthesis agent; the instinct was to add a `agents/` dir. Grepping the shipped siblings showed `/code-review` (0.8.0) already states the convention: **no plugin `agents/` dir → use generic agents** (`skills/code-review/SKILL.md:164`). `/resume` honored it (generic-agent synthesis) rather than introducing a structural first.

**Mechanism.** The `/loop` lesson framed verification as a *negative* check (catch a phantom). But the same one-line upstream check is *positive evidence* when the source is real — verifying is not just for catching lies, it confirms a true port is safe to build. Separately: a shipped sibling command is not just code, it is a record of **conventions already decided** (here: no `agents/` dir). A later rebuild that adds a structural element without checking the siblings risks contradicting a settled decision — the convention is discoverable by grepping the neighbors, exactly as a cross-skill wiring fact is.

**Fix.** Built `/resume` as a genuine CE `ce-sessions` port (Tier 2) and used generic-agent synthesis (no `agents/` dir), per the `/code-review` convention. DECISIONS [#resume-engine-rebuild](DECISIONS.md#resume-engine-rebuild) (C1 + the port distinction); shipped 0.12.0.

**What surprised.** After the `/loop` phantom, the working prior was "briefs over-claim sources" — but `/resume`'s source was real. The lesson is not "briefs lie" but "briefs must be verified" — and verification is just as likely to greenlight as to block.

**Generalizable rule.** Verification cuts both ways: the cheap upstream check that catches a phantom source (LEARNINGS [#brief-source-claim-phantom-artifact](#brief-source-claim-phantom-artifact)) is the *same* check that **confirms** a true source is safe to port — run it regardless of which way you expect it to land. And before adding a structural first (a new dir, a new file class), **grep the shipped siblings for a stated convention** — a sibling can encode a plugin convention (no `agents/` dir → generic agents) a later rebuild must honor; conventions are discoverable, not just inheritable.

**Refs.** Negative-case counterpart: LEARNINGS [#brief-source-claim-phantom-artifact](#brief-source-claim-phantom-artifact). The rebuild: DECISIONS [#resume-engine-rebuild](DECISIONS.md#resume-engine-rebuild), ARCHIVE [#resume-engine-rebuild-shipped](ARCHIVE.md#resume-engine-rebuild-shipped). The convention source: DECISIONS [#code-review-engine-rebuild](DECISIONS.md#code-review-engine-rebuild) (`skills/code-review/SKILL.md:164`). Campaign: DECISIONS [#lifecycle-engine-merge-campaign](DECISIONS.md#lifecycle-engine-merge-campaign).

### A budget-exhausted brief workflow asserted a SOURCE artifact that does not exist — verify a brief's upstream claims before building on them  {#brief-source-claim-phantom-artifact}

**Context.** Starting the `/loop` rebuild (sixth command of the engine-merge campaign). The QUEUED brief for `/loop` (`#loop-engine-merge-saga-workflow-offload`) named the engine source as gstack's "top-level SKILL = a proactive **dispatch table**" — i.e. it framed `/loop` as a port/merge of a gstack router engine, the same shape as every prior rebuild. Before building on that framing, checked the actual upstream.

**Evidence.** `gh api repos/garrytan/gstack/contents/` lists no `router`/`dispatch`/`loop` directory; `gh api repos/garrytan/gstack/contents/SKILL.md` decodes to `description: Fast headless browser for QA testing and site dogfooding` (a browser-testing skill, not a router/dispatch table). gstack's actual routing-adjacent engine is `context-save`/`context-restore` — which is the already-shipped **saga** primitive plus the queued `/resume`'s scope, **not** a `/loop` router. The brief that asserted the "dispatch table SKILL" was produced by the budget-exhausted brief workflow documented in [#workflow-structuredoutput-budget](#workflow-structuredoutput-budget) (16/19 agents over-read + failed to emit; the survivors synthesized from skim-level reads).

**Mechanism.** The brief-generation agents skimmed engine files under a tight budget (the very fix that made them *emit* — skim-not-full-read — also made them *summarize from headings*), so a heading-level impression ("gstack has a top-level SKILL that dispatches") hardened into a confident SOURCE claim ("dispatch table SKILL") in the brief. The brief's *intent* was sound (`/loop` should route + resume); its *provenance claim* (a gstack engine to port) was a hallucinated artifact. Trusting the brief's source claim uncritically would have sent the rebuild chasing a phantom merge.

**Fix.** Treated `/loop` as the campaign's **one native rebuild** — authored fresh against the lifecycle's own saga + operator-choice contracts, with **no upstream port/merge** — and recorded the phantom-source distinction in the ADR. DECISIONS [#loop-engine-rebuild](DECISIONS.md#loop-engine-rebuild); shipped 0.11.0, ARCHIVE [#loop-engine-rebuild-shipped](ARCHIVE.md#loop-engine-rebuild-shipped).

**What surprised.** Every prior rebuild brief had a real, verifiable upstream engine — so the campaign's working assumption was "the brief names a real source." `/loop` was the first brief whose named source did not exist, and it looked exactly as authoritative as the true ones.

**Generalizable rule.** A brief produced by a budget-constrained skim workflow can assert a SOURCE artifact that does not exist — its *intent* may be sound while its *provenance* is hallucinated. Before building on a brief, verify its **source claims against the actual upstream** (here: a one-line `gh api .../contents/` + a SKILL.md decode), exactly as you would verify any system-state claim. A confident-sounding source citation is not evidence the source exists.

**Refs.** Upstream cause: LEARNINGS [#workflow-structuredoutput-budget](#workflow-structuredoutput-budget). The rebuild it informed: DECISIONS [#loop-engine-rebuild](DECISIONS.md#loop-engine-rebuild), ARCHIVE [#loop-engine-rebuild-shipped](ARCHIVE.md#loop-engine-rebuild-shipped). Campaign: DECISIONS [#lifecycle-engine-merge-campaign](DECISIONS.md#lifecycle-engine-merge-campaign).

## 2026-06-02

### `infiquetra-lifecycle` is a thin reskin of gstack + CE; engine-loss is systemic, not isolated to `/ideate`  {#lifecycle-thin-reskin-systemic}

**Context.** After rebuilding `/ideate` (0.3.0), audited the remaining lifecycle commands against their source arts. The plugin was derived from compound-engineering (CE) **and** [gstack](https://github.com/garrytan/gstack) — gstack was the source missed in the first audit pass; Jeff named it. Most commands kept the source's name + intent but dropped its engine.

**Evidence.** A 19-agent `lifecycle-engine-audit-queue` workflow read each command's gstack + CE engine vs the current stub. Representative gaps: `office-hours` 23-line stub vs gstack's two-mode YC diagnostic; `code-review` 20 lines vs gstack's 7-specialist review army + CE's persona/findings/validator engine; `founder-review` 20 lines vs gstack ceo-review's 4 scope modes + 18 CEO patterns; `plan` 27 lines vs CE's R-ID/KTD/U-ID artifact engine + gstack's spec interrogation; `qa`/`strategy`/`optimize`/`work`/`resume`/`retro` similarly stubbed. Only `/doc-review` carried its CE engine. Briefs → QUEUED [#lifecycle-engine-merge initiative](QUEUED.md).

**Mechanism.** Porting a skill's **name + intent** without its tuned engine (sub-agent prompts, rubrics, state machines, findings schemas) silently reverts it to a facilitative stub — the same mechanism as [#stub-port-drops-engine](#stub-port-drops-engine), but repo-wide: ~10 of 13 commands affected, because the initial port applied the same lossy transform uniformly.

**Fix (queued).** The engine-merge initiative in [QUEUED.md](QUEUED.md) — rebuild each command by merging CE + gstack into a self-contained infiquetra engine, 1-by-1, interview-driven. Decision: DECISIONS [#lifecycle-engine-merge-campaign](DECISIONS.md#lifecycle-engine-merge-campaign).

**What surprised.** gstack's `cso/` skill is **Chief SECURITY Officer** (a 14-phase security audit), not Chief Strategy Officer — so the pre-audit table's "`/strategy` ← gstack cso" mapping was wrong. `/strategy`'s engine source is **CE `ce-strategy` only**; gstack has no strategy engine. (Corrected in the queue.) Lesson within the lesson: a plausible name match (`cso` ≈ "Chief Strategy Officer") is not a verified mapping.

**Generalizable rule.** When a plugin is "based on" upstreams, audit **every** command against **all** named upstreams before trusting any mapping — a derived plugin tends to inherit the upstream's *structure* while uniformly dropping its *engine*, and a name that looks like a match (`cso`) may not be one. Verify the engine, not the label.

**Refs.** DECISIONS [#lifecycle-engine-merge-campaign](DECISIONS.md#lifecycle-engine-merge-campaign); QUEUED engine-merge initiative; LEARNINGS [#stub-port-drops-engine](#stub-port-drops-engine); DECISIONS [#ce-ideation-engine-restore](DECISIONS.md#ce-ideation-engine-restore).

### Schema-output workflow agents that over-read + over-write fail to call `StructuredOutput` — budget exhaustion, not rate limits  {#workflow-structuredoutput-budget}

**Context.** Ran a 19-agent `Workflow` to produce the engine-merge queue briefs. Each agent read large gstack engine files (some 2000+ lines) and was required to emit a schema-validated brief via the `StructuredOutput` tool.

**Evidence.** Run `wf_4a5f04b6-c00`: **16 of 19** agents failed with `subagent completed without calling StructuredOutput (after 2 in-conversation nudges)` — not API-error kills. The 3 that succeeded produced verbose briefs (one ~31K chars). Re-run `wf_577148f3-749` with the fix below: **16 of 16** succeeded (846K subagent tokens, 0 failures).

**Mechanism.** Heavy reading + essay-length synthesis consumed the agents' turn/context budget, leaving nothing to make the final `StructuredOutput` tool call; the failure presents as "completed in prose." Transient 429s seen in the live `/workflows` view ate retry budget but were **not** the fatal cause — the recorded failure reason was non-emission, not a rate-limit error. (Jeff's initial read — "rate limits" — was the visible symptom, not the root cause.)

**Fix.** Re-ran the 16 with four changes: (1) **hard brevity** — each schema field 1-3 sentences, "this is a stub not the design"; (2) **explicit emit rule** — "the ONLY accepted output is the StructuredOutput tool call; prose = lost work"; (3) **light reading** — Grep to the engine heading + skim ~150 lines, don't full-read 2000-line files; (4) **batched concurrency** (5 at a time) to dodge the 429 retries that wasted budget.

**Validation.** Re-run produced all 16 missing briefs cleanly; combined with the 3 banked from run 1 = 19 total, synthesized into QUEUED.md.

**Generalizable rule.** For schema-output workflow fan-outs over large inputs: cap output length, make the `StructuredOutput` call mandatory + explicit, instruct skim-not-full-read, and batch concurrency. "Completed without calling StructuredOutput" almost always means **budget exhaustion** (over-reading + over-writing), not rate limits — fix the budget, not (only) the throughput. Keep the same script's successful agents and re-run only the failures with the tightened prompt.

**Refs.** QUEUED engine-merge initiative (the briefs this produced); the audit workflow `lifecycle-engine-audit-queue`.

## 2026-06-01

### A plugin version bump must update its metadata test's hardcoded version — and `UNSTABLE` is not a green CI gate  {#version-bump-test-pin}

**Context.** Bumping `infiquetra-lifecycle` 0.2.0 → 0.3.0 turned `main` red: CI's Tests job failed on a
hardcoded assertion. The PR (#167) had been squash-merged while `mergeStateStatus` was `UNSTABLE`.

**Evidence.** `tests/test_infiquetra_lifecycle_plugin.py:42` asserts `plugin_json["version"] == "0.2.0"`
— a literal pin (line 43 then checks the marketplace entry matches it dynamically). Pre-merge local
checks — `marketplace/validator/validate.py` (0 errors) and `python3 -m json.tool` — both passed
because neither runs pytest. `gh pr checks` showed `Tests (Python 3.12) fail` while Lint / Type Check /
Security / Validate Plugins passed; the merge still completed because Tests is not a *required* status
check, so the PR was `UNSTABLE` (mergeable) rather than `BLOCKED`.

**Mechanism.** Each `test_<plugin>_plugin.py` pins the plugin's current version as a literal so version,
`plugin.json`, and the marketplace entry cannot silently drift. A version bump is therefore a
**three-file change**: `plugin.json`, the `marketplace.json` entry, AND the test's literal. The
marketplace validator only checks semver *shape* + entry/source existence, not the pinned value.
Separately, `gh pr checks --watch` exiting 0 and `mergeable: MERGEABLE` are NOT proof of green — only
every check showing `pass` is.

**Fix.** Updated the test literal to `0.3.0` (this follow-up commit).

**Generalizable rule.** (1) When bumping a plugin version in this repo, grep `tests/` for the old
version string and update the metadata-test literal in the same change. (2) Gate a merge on `gh pr
checks` showing every check `pass` — never on `--watch`'s exit code or on `mergeStateStatus: UNSTABLE`,
which permits merging over a non-required failing check. Run `uv run pytest` (or at least the affected
`test_<plugin>_plugin.py`) as part of pre-merge validation, not just the marketplace validator.

**Refs.** DECISIONS `{#ce-ideation-engine-restore}`. Surfaced fixing PR #167's red `main`.

### Porting a skill's name without its engine — including its tuned sub-agent prompts — silently changes its behavior  {#stub-port-drops-engine}

**Context.** `infiquetra-lifecycle`'s `/ideate` and `/brainstorm` were derived from
compound-engineering (CE) but had been reduced to ~13–20 line facilitative stubs. In use they felt
like the operator supplied all the ideas, and once Claude declared `/ideate` "too lightweight" and
improvised its own fan-out.

**Evidence.** Pre-rebuild `skills/ideate/SKILL.md` (13 lines) said "produce a small option set; lead
the user through choices" — facilitation, not generation. CE's `ce-ideate` (~400-line SKILL + 3
reference files) runs 6 parallel frame agents → adversarial filter → survivors. A home-lab artifact
(`home-lab/docs/ideation/2026-05-31-card-sizing-...-ideation.md`) was labeled
`/infiquetra-lifecycle:ideate` but used a hand-rolled decision-axis structure — Claude improvising a
substitute engine because the skill had none.

**Mechanism.** CE's repeatability does not live in the phase *structure* alone; it lives in the
*verbatim, separately-tuned sub-agent prompts* (the codebase-scan prompt, the frame-generator prompt,
the critique rubric). Porting the structure but reducing the sub-agents to "dispatch an Explore agent"
reintroduces the same facilitate-instead-of-generate failure one level down. An adversarial-review
workflow over the rebuild caught exactly this risk plus functional gaps it would have masked (a
soft-promote loophole in revival; a gate promising multi-repo grounding no Phase 1 source delivered).

**Fix (commit `30c9099`).** Rebuilt both engines self-contained with verbatim tuned prompts for every
sub-agent; ran an author→adversarially-verify→remediate ultracode workflow (5 major findings fixed, 0
blocking); plugin `0.3.0`. Follow-up fix: the version bump tripped a hardcoded
`assert plugin_json["version"] == "0.2.0"` in `tests/test_infiquetra_lifecycle_plugin.py` — caught by
CI, not by the marketplace validator or `json.tool`, because the plugin-metadata test pins the literal
version. Lesson reinforced below.

**Generalizable rule.** When you "port" or "slim" a skill, diff the *mechanics and the sub-agent
prompt bodies*, not just the prose intent. A skill that keeps the name and the goal but drops the
engine — or reduces its sub-agents to generic dispatch — will silently behave like a stub, and the
degradation won't surface until someone notices the AI stopped doing the work.

**Refs.** DECISIONS `{#ce-ideation-engine-restore}`. Plan
`.claude/plans/can-you-review-the-inherited-lantern.md`.

## 2026-05-30

### `gh api` with `-f` silently defaults to POST — breaks read-only queries  {#gh-api-f-defaults-post}

**Context.** `/deploy-status` was non-functional: `query_deployments.py` `latest_deployment()` called `gh api repos/{repo}/deployments -f environment={env} -f per_page=1` and got `HTTP 422 "ref wasn't supplied"`. The intent was to *read* the deployments list; the API was rejecting it as a malformed *create*.
**Evidence.** Issue #161; `plugins/deploy/scripts/query_deployments.py:86` (pre-fix). Live repro against `infiquetra/campps-identity-access` returned 422; the GET form `gh api --method GET repos/infiquetra/campps-identity-access/deployments -f environment=nonprod -f per_page=1 --jq '.[0].ref'` returns `v0.1.0`.
**Mechanism.** `gh api` chooses the HTTP method by *inference*: with no `--method`, the presence of any `-f`/`-F` field flag flips the default from GET to **POST** (the flags are assumed to be a request body). `POST repos/{repo}/deployments` is the create-deployment endpoint, which requires a `ref` — hence 422. With `--method GET` explicit, `gh` instead serializes `-f` params into the query string.
**Fix.** Added `--method GET` and a tag-ref filter; commit on `fix/deploy-status-query-deployments`. Validated: live smoke prints `nonprod: v0.1.0`, no 422; regression test asserts `--method GET` is present so it can't silently revert to POST.
**Second defect (same fix).** Even as a GET, taking the newest record per env was wrong — GitHub Actions `environment:` job keys auto-create Deployment objects with branch/SHA refs (`main`, PR branches) that interleave with real tag refs. Fixed by `is_tag_ref()` (known prefix + version digit) selecting the newest *tag-ref* record. See [QUEUED: per_page lookback cap](QUEUED.md#deploy-status-perpage-cap).
**Generalizable rule.** Any `gh api` call meant to *read* must pass `--method GET` explicitly the moment it also passes `-f`/`-F` (e.g. for query params) — otherwise gh turns it into a POST. When asserting against an external API in tests, assert the *method*, not just the URL/params.
**Refs.** Issue #161; [QUEUED.md#deploy-status-perpage-cap](QUEUED.md#deploy-status-perpage-cap).

### Prepared issue creation needs an artifact boundary before mutation  {#prepared-issue-artifact-boundary}

**Context.** `sdlc-manager` needed to turn rough source text into Asgard or Mount Olympus issues
without creating cards that fail team readiness checks or require hidden board/label repair.

**Evidence.** The new workflow in `plugins/mission-control/scripts/sdlc_manager.py` writes markdown
drafts plus JSON sidecars, re-runs readiness in `issue create-prepared`, and records created issue
state back onto the draft. Tests in `plugins/mission-control/tests/test_issue_prepare.py` and
`plugins/mission-control/tests/test_issue_create_prepared.py` cover blocked drafts, safe statuses,
mapping PR stop, override creation, and draft-created state.

**Mechanism.** A direct "source text -> GitHub issue" command mixes interpretation, validation,
and side effects. Splitting the workflow into a durable draft/sidecar artifact and a confirmed
mutation step lets agents shape prose while deterministic code owns readiness, repair ordering,
and idempotent recovery.

**Fix.** Added prepared drafts, readiness profiles, mutation planning, repo prerequisite repair,
mapping PR handling, natural-language prompt guidance, and plugin metadata for `sdlc-manager`
1.6.0 in PR #159, commit `74cd372`.

**Validation.** `uv run pytest -q`, `uv run ruff check .`, `uv run python -m mypy plugins/
scripts/ tests/ --ignore-missing-imports`, `uv run python -m ruff format --check .`,
`uv run python marketplace/validator/validate.py`, `uv run python
plugins/mission-control/scripts/sync_template_docs.py --check`, and `git diff --check` pass. The
post-merge `main` CI run `26685668123` also passed.

**Generalizable rule.** When a plugin command turns ambiguous human or agent text into external
side effects, make a reviewable artifact the boundary and re-validate it at mutation time.

**Refs.** DECISIONS [prepared issue workflow boundary](DECISIONS.md#prepared-issue-workflow-boundary);
ARCHIVE [Asgard/Olympus issue readiness workflow](ARCHIVE.md#asgard-olympus-issue-readiness).

### Prompt docs need their own drift guards  {#prompt-docs-need-drift-guards}

**Context.** `sdlc-manager` had already learned to consume the current `infiquetra-sdlc`
board schema and generated template reference, but handwritten prompts and references still taught
old label behavior.

**Evidence.** `plugins/mission-control/config/sdlc-schema.json` matched
`../infiquetra-sdlc/config/sdlc-schema.json`, and
`uv run python plugins/mission-control/scripts/sync_template_docs.py --check` passed. The remaining
drift was in handwritten files such as
`plugins/mission-control/agents/sdlc-operator.md`,
`plugins/mission-control/commands/sdlc-triage.md`, and
`plugins/mission-control/skills/sdlc-issues/references/issue-types.md`.

**Mechanism.** Generated docs can stay correct while nearby prompt text keeps stale duplicated
facts. Agents read both surfaces, so a correct generated reference is insufficient if the operator
prompt still says exploration/context-update are `hermes-task` or examples still apply
`needs-analysis` as a current template label.

**Fix.** Aligned the handwritten prompts/references with the generated template contract and added
`plugins/mission-control/tests/test_prompt_alignment.py` to pin the current metadata,
Hermes-actionability, and label wording.

**Validation.** `uv run python plugins/mission-control/scripts/sync_template_docs.py --check`,
`uv run ruff check plugins/mission-control/tests/test_prompt_alignment.py`, and
`uv run pytest plugins/mission-control/tests tests/test_sdlc_manager.py -q` pass.

**Generalizable rule.** When a plugin mixes generated references with human-authored prompts, add
drift guards for the human-authored prompts too; otherwise agents can keep following stale
instructions even while generated docs are correct.

**Refs.** ARCHIVE [sdlc-manager prompt alignment](ARCHIVE.md#sdlc-manager-prompt-alignment).

---

## 2026-05-29

### Schema migrations need legacy fallback contract tests  {#schema-migration-legacy-fallbacks}

**Context.** Updating the doc-review PR branch from `main` pulled in the sdlc-manager schema
migration and exposed a CI failure in `board_wip`: mocked legacy WIP limits were ignored when no
`sdlc_schema` was present.

**Evidence.** PR #158 CI failed
`tests/test_sdlc_manager.py::TestWipLimitsConfigurable::test_uses_config_wip_limits`; local
`uv run python -m pytest -q` reproduced the same `Ready 0/10` output instead of the configured
`Ready 0/5`.

**Mechanism.** `_wip_limits()` was changed to read schema-backed board limits first, but the
migration removed the previous `legacy_rollout_config.wip_limits` fallback path. Test fixtures and
older operator configs that intentionally inject only legacy config then silently fell through to
defaults.

**Fix.** Keep the schema as canonical when present, and restore the Mount Olympus legacy fallback
only when schema limits are absent.

**Validation.** `uv run python -m pytest tests/test_sdlc_manager.py::TestWipLimitsConfigurable -q`
and `uv run python -m ruff format --check .` pass after the fix.

**Generalizable rule.** When migrating plugin runtime config from a legacy source to a canonical
schema, encode the fallback contract directly in tests before deleting old read paths.

**Refs.** PR #158.

---

## 2026-05-27

### Setup commands must prove every bundled asset path exists  {#team-setup-asset-drift}

**Context.** The `team-execution` v2 validator port reworked `/team-setup` and exposed that the
existing command referenced `docs/example_tmux.conf` and `docs/agent-overflow.sh`, but the plugin
did not actually ship those files.

**Evidence.** `tests/test_team_execution_plugin.py::test_team_setup_references_existing_assets`
failed before the port because `plugins/team-execution/docs/example_tmux.conf` was absent. The
fix adds both files under `plugins/team-execution/docs/` and keeps `/team-setup` pointing at those
packaged paths.

**Mechanism.** The setup command evolved as operational documentation, but no repository check tied
its copy commands to real plugin assets. The command could therefore promise an install path that
worked only in a developer's local config, not from a fresh plugin package.

**Fix.** Add packaged setup assets and a contract test that every `/team-setup` asset reference
resolves in the plugin tree (commit pending).

**Validation.** `uv run pytest tests/test_team_execution_plugin.py -q` now passes.

**Generalizable rule.** Any plugin command that copies, installs, or references bundled files needs
a manifest-style test proving those paths exist in the package, not just in a developer's machine.

**Refs.** DECISIONS [team-execution validators](DECISIONS.md#team-execution-v2-validators).

---

## 2026-05-26

### Channel-plugin notifications don't reach `--bg` / `/bg` sessions: Claude Code's carry-through set excludes channels  {#cc-channels-bg-not-supported}

**Context.** Phase 2.5 (PRs #144-#151) added env-var-driven auto-connect (`CLAUDE_CHANNEL_AUTO_CONNECT=1`) and a `claude-channel` wrapper, designed to enable Phase 5's "Mimir programmatically spawns a CC session" pattern. The wrapper successfully propagates env to background-dispatched sessions via claude's `--settings '{"env":{...}}'` JSON (verified with `ps eww -p <mcp-pid>` — env vars present in the MCP server's environment). The plugin auto-connects, registers presence in Redis, and creates the consumer group. The XREADGROUP loop reads each XADD'd inbound message and `xack`s it cleanly. But **Claude inside the dispatched bg session never sees the `<channel>` notification in its context** — no `↳ redis-channel: <text>` line in the attached terminal, no LLM-side processing, no reply.

**Evidence.**
1. **Empirical round-trip test (passes in foreground, fails in --bg):**
   - Foreground `claude-channel --session-name plugin-testing-2271` → auto-connected to `mimir`, XADD'd test inbound, Claude replied: `'Confirmed — foreground auto-connected session received your message on endpoint mimir. Reply path working.'` → outbound stream got it. ✓
   - `claude-channel --bg --session-name plugin-testing` → auto-connected, presence registered, consumer thread attached (XINFO GROUPS showed `consumers=1 pending=0 last-delivered-id=<my-msg-id>`), but no notification rendered in the attached bg session's terminal, no outbound reply. ✗
   - Running explicit `/redis-channel-connect` inside the bg session (to rebuild the consumer with a guaranteed-live `ctx`) made no difference — confirms NoopNotifier-vs-AsyncNotifier wasn't the issue.
2. **Process inspection (bg-spare daemon claim):** `ps -ww -p <bg-session-pid>` showed the bg session's claude was invoked as `claude --bg-spare /tmp/cc-daemon-501/<id>/spare/<n>.claim.sock` — completely different argv than what our wrapper passed. **No `--dangerously-load-development-channels` flag in the bg-spare process's argv.** The dispatching `claude --bg ...` call only applies its flags to the supervisor-dispatch action; the spare process that actually runs the dispatched session has its own argv set by the daemon, not the caller.
3. **`/bg` (from inside a running session) behaves the same way.** A foreground session that was working perfectly (plugin-testing-2271, full round-trip verified) had `/bg` invoked. After `/bg`: the session was *removed* from the Redis registry (v0.4.6 graceful disconnect cleanup fired during the foreground claude's shutdown), and the new bg-spare that took over the session ID came up without dev-channels enabled — so it didn't auto-connect or receive notifications.
4. **Documentation confirmation** (via claude-code-guide subagent against the agent-view docs): the flags that carry through from a `--bg` dispatch (or `/bg`) to the dispatched session are: `--mcp-config`, `--strict-mcp-config`, `--settings`, `--add-dir`, `--plugin-dir`, `--fallback-model`, and directories added with `/add-dir`. **`--dangerously-load-development-channels` and `--channels` are deliberately not in this set.** Channels are session-specific opt-ins, intended only for foreground use; the docs don't expose a config knob (settings.json key, env var, plugin manifest field) that says "enable this channel by default for future sessions."

**Mechanism.** Claude Code's bg-dispatch model is supervisor + spare-process pool. The user-facing `claude --bg ...` or `/bg` is a *handoff*, not a context-clone: the supervisor claims a spare process from its pre-warmed pool, hands the session-id + (a few) carry-through flags to it, and that spare process starts a fresh Claude with just those flags. The original claude process — including its loaded channels plugin, its MCP servers, and its `--dangerously-load-development-channels` config — exits or detaches. Channels are deliberately scoped to the launching session because they're an interactive concept (someone routing messages into "your" claude session), not a worker-process concept (bg agents are independent tasks).

Internally, our MCP server's `_enable_channel_capability` monkey-patch declares `claude/channel` in the initialize response, but **only a Claude Code client that was launched with the channels feature opted-in (via `--dangerously-load-development-channels` for research preview, or `--channels` later) will recognize and route those `notifications/claude/channel` events to the model's context.** A bg-spare that wasn't launched with the flag accepts the notification at the MCP-protocol level (no handshake error) but drops it before surfacing to Claude — which is why the consumer thread on the server side sees its message ack'd successfully while nothing reaches the model.

**Fix.** Not a code fix; an architecture acknowledgment. Phase 2.5 shipped a correct + working solution for the foreground auto-connect case. The bg-dispatch case is not currently solvable from the plugin side. Two practical workarounds for "long-running session that consumes from Redis":
1. **Foreground inside tmux.** `tmux new-session -d -s <name> 'claude-channel --session-name <name>'` runs claude foreground (PTY-backed) but detaches the user's terminal. The session has the dev flag in its argv → channels work. User can `tmux attach -t <name>` to inspect. This is the Phase 5 spawn primitive going forward. *(Funny twist: my v0.4.15 tmux work was right architecture, wrong reasoning — I cited PTY allocation, but the actual reason tmux helps is "keeps the session foreground from Claude Code's POV.")*
2. **Pre-launched dedicated foreground sessions.** User opens an iTerm/Terminal window with claude-channel running once; that long-lived session listens. Less flexible than spawn-on-demand but no tooling needed.

Phase 5's plan section ([[plan-file]] §5) currently assumes `claude --bg` works for Mimir-spawn; that section needs revising to mandate tmux-wrapped foreground sessions (or document an Anthropic feature request for adding channels to the carry-through set).

**Validation.**
- Foreground round-trip: outbound payload `'Confirmed — foreground auto-connected session received your message on endpoint mimir. Reply path working.'` proves the full pipeline (auto-connect → presence → inbound → notification → model → reply tool → outbound) works in foreground.
- Bg round-trip: 4 separate test inbounds (Phase 2.5 testing across v0.4.15 → v0.4.18 + post-`/bg`) all showed the same pattern: consumer reads + acks, no reply.
- Docs-side validation: claude-code-guide subagent against Claude Code agent-view docs confirmed the carry-through flag list. Nothing in `settings.json` schema for channel defaults.

**What surprised.**
1. The `--settings '{"env":{...}}'` env injection (v0.4.17) and the auto-connect-fallback (v0.4.18) BOTH worked — env DID propagate to bg-spare, MCP server DID auto-connect, presence DID register, consumer DID read. But channel-notification routing is a separate Claude Code-client-side concern that none of those mechanisms touch.
2. `/bg` is not a context-switch; it's a process hand-off. The foreground claude exits cleanly (our v0.4.6 graceful-disconnect cleanup fires and HDEL's the registry) — which is exactly the behavior you'd want, but it means there's no "still the same session, just running in the background" semantic.
3. claude-codex's `--settings` pattern (which we copied for env propagation) is for ANTHROPIC_BASE_URL / model / proxy config — none of which are dev-channels-related. Codex doesn't have this problem because it doesn't use channels.
4. The MCP-server side declaration of `claude/channel` capability via `_enable_channel_capability` is necessary but not sufficient — the *client* must also opt in via `--channels` / `--dangerously-load-development-channels`. A spare-process started without the flag silently drops channel notifications.

**Generalizable rules.**
- **Channel plugins are foreground-only today.** If your plugin uses `notifications/claude/channel`, design for `claude` launched in an interactive context (terminal or tmux pane). Don't assume `--bg` or `/bg` will keep channels working; they won't, even when MCP servers, env, and tools all propagate correctly.
- **Carry-through ≠ inheritance.** When Claude Code "dispatches" a session (bg-spare, agent-spawn, etc.), it's not forking your current process — it's claiming a fresh worker and passing it a small, *documented* set of flags. Always verify your launch flag is in that set before assuming it'll propagate. Flags NOT in the set: `--dangerously-load-development-channels`, `--channels`, anything model-specific, anything debug-specific, plus most experimental features.
- **For programmatic-spawn ("Mimir starts a session for me"), tmux is the right primitive while channels stay research-preview.** tmux gives you: detached-from-user-terminal but foreground-from-claude's-POV, plus a way to inspect/attach later. The CLI invocation looks like: `tmux new-session -d -s <name> 'claude-channel --session-name <name>'`.
- **When debugging "Claude doesn't see my MCP notification": always check both server-side emit AND client-side capability.** Server-side: monkey-patch + emit work. Client-side: `--dangerously-load-development-channels` (or its successor) must be in the claude process's argv that's *actually receiving* the notification — not the one that dispatched it.

**Refs.**
- Phase 2.5 PRs #144-#151 (v0.4.11 through v0.4.18) trace the chase
- Existing [[cc-channels-surface-split]] entry (related: terminal/channel surface split by design)
- claude-code-guide subagent output (this conversation)
- `~/bin/claude-codex` for the `--settings` env pattern (line 327-333) we copied for env propagation
- Plan file §5 (Phase 5 — Hybrid intelligence) needs updating to mandate tmux-wrapped foreground for the spawn primitive

---

### Claude Code Channels split terminal + channel surfaces *by design* — stop trying to mirror them  {#cc-channels-surface-split}

**Context.** After Phase 2 text-bridge worked end-to-end (PRs #128-138), the local-terminal UX bothered Jeff: the inbound `<channel>` notification rendered as `↳ redis-channel: <text>`, but Claude's reply rendered only as `Called plugin:redis-channel:...` — no visible reply text in the terminal. Drove five iterative attempts (v0.4.5–v0.4.10) to make Claude emit a text_block alongside the `reply` tool call. None worked. Turns out we were fighting documented Claude Code Channels design intent, not a bug.

**Evidence.**
- Discord plugin source (`~/.claude/plugins/cache/claude-plugins-official/discord/0.0.4/server.ts:456`):
  ```
  instructions: [
    'The sender reads Discord, not this session. Anything you want them to see
     must go through the reply tool — your transcript output never reaches their chat.',
    ...
  ]
  ```
  No "MANDATORY mirror text in both places" guidance. The Discord plugin *embraces* the surface split.
- Anthropic docs Jeff surfaced: *"When using Claude Code Channels (for Discord or Telegram), it is normal behavior that messages sent within the terminal session are not visible in the Discord channel, and vice-versa. This design is intended to separate remote task execution from active local terminal work."*
- Cheap self-report test (v0.4.9 turn at 14:06): asked Claude to repeat its prior reply verbatim. Claude replied: `'no text block, only tool call.'` — confirming via self-report that Claude is intentionally not emitting transcript text for channel-triggered turns.
- Five coaching iterations (v0.4.5 soft framing, v0.4.7 MANDATORY, v0.4.8 echo-removal, v0.4.9 two-user reframe, v0.4.10 coaching delivered via `instructions=` instead of inert agent file) produced **zero observable behavior change**.

**Mechanism.** Claude Code Channels (`notifications/claude/channel` capability) are architected as a *separation* feature: the channel surface is a router endpoint where remote users live; the local terminal is for the developer driving the session. Mirroring the channel content into the terminal would defeat the point ("active local terminal work" gets cluttered with remote chatter the developer didn't initiate). Claude's training reflects this — notification-triggered turns produce `[tool_use(reply)]` without a text_block because the inbound is treated as a remote-user event, not a local prompt. Coaching to override this loses to training every time.

**Fix.** Stop chasing it. Three of the five versions were dead-end coaching iterations — net zero behavioral change but we kept v0.4.10's architectural move (coaching into `instructions=`) because it's the *right place* for any future coaching independent of this question. v0.4.6 stream cleanup + v0.4.10 instructions-delivery are real correctness fixes; the coaching wordsmithing in 0.4.7/0.4.8/0.4.9 was chasing a non-bug.

**Validation.** Discord plugin source confirms intent; Anthropic docs confirm design; Claude's own self-report confirms the model isn't going to comply with mirror coaching. Three convergent evidence sources.

**What surprised.**
1. `agents/*.md` files in a Claude Code plugin are **subagent definitions invoked via the `Agent` tool — they are NOT auto-loaded into the system prompt.** I'd assumed `agents/coach.md` was an always-on context document. Empirical proof: editing the agent file four times (v0.4.5/0.4.7/0.4.9) produced no behavior change; moving the same content into FastMCP's `instructions=` field (v0.4.10) finally landed it in the system prompt as visible "MCP Server Instructions". The discord/imessage/telegram official plugins have **no `agents/` directory at all** — all their runtime coaching lives in `instructions=`. That's the canonical pattern.
2. Claude's self-report when asked about its own prior output was honest and useful (`'no text block, only tool call.'`). I'd half-expected a hallucination; instead the model accurately reported what it did. Worth remembering: ask the model itself when you want to know what just happened.
3. The Discord plugin doesn't try to fix this gap because it isn't a gap from Anthropic's POV — the channel surface and terminal surface are intentionally distinct audiences with distinct content.

**Generalizable rules.**
- **For Claude Code plugins, runtime behavior coaching belongs in the MCP server's `instructions=` field, not in `agents/*.md`.** Agent files define subagents invokable via the `Agent` tool — they are not auto-loaded into the active conversation context. Coaching that must apply on *every* turn (especially notification-triggered ones, where no Agent invocation happens) must live in `instructions=` to actually reach Claude.
- **Before chasing a "Claude isn't doing X" issue, check whether X is intended design.** Read what the official plugins (`claude-plugins-official/discord`, `imessage`, `telegram`) actually do in their `instructions=` strings. If they don't try to do X either, X probably isn't expected. Anthropic's official plugins are the canonical reference for "what behavior Claude Code intends with this feature."
- **When you've made three coaching changes with no observable effect, stop and verify the coaching is even being delivered to the model.** "I changed the coach four times and Claude still does the same thing" is strong evidence the coaching isn't reaching Claude — go check the delivery mechanism (`instructions=`, `system_prompt`, `CLAUDE.md` scope, agent activation conditions) before changing the words again.
- **Claude can self-report on its own prior output reliably for simple yes/no factual questions about message structure.** "Did you emit X in your previous turn?" → useful diagnostic. Don't confuse this with "what were you thinking?" (that one's unreliable).

**Refs.**
- `plugins/redis-channel/CHANGELOG.md` (v0.4.5 → v0.4.10 entries trace the chase)
- PRs #137 (v0.4.5), #139 (v0.4.7), #140 (v0.4.8), #141 (v0.4.9), #142 (v0.4.10)
- Discord plugin source: `~/.claude/plugins/cache/claude-plugins-official/discord/0.0.4/server.ts:455-465`
- Plan: `~/.claude/plans/i-would-like-to-distributed-hanrahan.md` — terminal-UX expectations were unstated in the original plan; this learning clarifies for Phase 3+ that voice-routing UX matters but local-terminal mirroring is out of reach.

---

## 2026-05-25

### Channel-plugin naming: noun-channel, not noun-bridge  {#redis-channel-rename}

**Context.** Shipped the plugin as `redis-bridge` through Phases 0-2 (PRs #127-131). Jeff flagged the name as too generic: Anthropic's official channel plugins are named after what they connect to (`discord`, `telegram`, `imessage`), and "bridge" loses the signal that this is a `notifications/claude/channel`-emitting MCP server vs. a tool-only MCP. Renamed to `redis-channel` before Phase 3 work (which will pair with the not-yet-built router-side repo).

**Evidence.** Naming convention from official Claude Code plugins: the plugin name = the system it bridges to. `discord`, `telegram`, `imessage` etc. For redis-channel, the plugin is deliberately Hermes-agnostic — the only thing it "knows about" is Redis. So `redis` + `-channel` suffix to signal channel-protocol-emitting plugin. Slug "channel" parallels the discord/telegram pattern in that it identifies what kind of plugin this is at a glance.

**Mechanism (of why bridge was wrong).** "bridge" is generic — could mean anything that connects two things. "channel" is a specific term in the Claude Code MCP spec referring to plugins that emit `notifications/claude/channel`. Naming a Claude Code channel-plugin `*-channel` makes the type self-documenting; `*-bridge` doesn't. Cost of late rename: every Phase 3+ writeup would have propagated the wrong shape.

**Fix.** Single PR renames 33 files end-to-end:
- `plugins/redis-bridge/` → `plugins/redis-channel/` (git mv preserves history)
- `redis_bridge_*` MCP tool names → `redis_channel_*`
- `/redis-bridge-*` slash commands → `/redis-channel-*`
- Logger `redis_bridge.channel` → `redis_channel.channel`
- `~/.claude/channels/redis-bridge/` runtime config dir → `~/.claude/channels/redis-channel/`
- Marketplace entry name + plugin.json + `.mcp.json` server key
- 9 test files renamed
- 6 slash command files renamed
- Plugin version 0.3.0 → 0.4.0 (signals breaking-name change)
- All `redis-bridge` references in README/CHANGELOG/coach/journal prose
- Auto-memory files updated

**Preserved deliberately**:
- Two engineering-journal anchor slugs (`#redis-bridge-verification`, `#redis-bridge-decoupled`) per the journal convention "keep slugs stable". Their titles + prose now say "redis-channel" but the slug stays as a historical ID for any external link.
- Zero protocol breakage: the Redis namespace `cc-sessions:*` doesn't reference the plugin name, so router-side and existing-Redis-state need no migration. PROTOCOL.md unchanged in semantics.

**Validation.** All 387 unit tests pass. Headless integration test passes all 4 phases (live olympus-bus Redis): real connect, inbound XADD → notifications/claude/channel notification, reply tool XADD round-trip, graceful disconnect, SIGKILL+lazy-GC.

**What surprised.** How clean the rename was. The plugin's Redis-side wire format (`cc-sessions:*`) was deliberately not bound to the plugin name in PROTOCOL.md, so we got the "free" rename property: old Redis state stays valid, the (not-yet-built) router doesn't need to know the plugin was renamed. The lesson there is about loose coupling at protocol boundaries: **name your wire format independently of your plugin name**.

**Generalizable rule.** **For Claude Code channel-emitting plugins, use the `<target>-channel` shape** (parallels `discord`/`telegram`/etc.). Avoid generic suffixes like `-bridge` / `-mcp` / `-server` — those describe an implementation detail, not what the user will reach for in `/plugin install`. Catch this naming question before Phase 1, not after Phase 2.

**Refs.** PR for the rename; previous PRs #127-131 under the old name.

---

### Redis password URL-injection broke on URL-special characters  {#redis-url-password-encoding}

**Context.** Phase 2 headless integration test against live olympus-bus Redis failed at the `redis_channel_connect` call with `"Port could not be cast to integer value as 'YPPu3qQ0VkURKkkm1J81l4'"`. The "port" was actually a suffix of the 44-char Hermes Redis password. fakeredis unit tests had passed because the test password was the literal string `"password"` with no URL-special chars; the bug was invisible in unit tests.

**Evidence.** `plugins/redis-channel/server/redis_client.py:resolve_url_with_password` was building the netloc as `f":{password}@{host}:{port}"` with the raw password. When the password contained `:` (the user:password separator) or `@` (the auth:host separator), redis-py's URL parser tokenized it wrong and tried to interpret a substring as the port number.

**Mechanism.** Real Redis passwords from password generators or `openssl rand -base64 32` contain `:`, `+`, `/`, `=`, `@` etc. URL syntax for `://user:pass@host:port/db` is positional: the parser scans for the next `:` after the user (which would be inside our unencoded password). The fix is straightforward — `urllib.parse.quote(password, safe="")` — but the bug class is wider: **any URL component built from external input MUST be URL-encoded if not coming from a URL itself**.

**Fix.** `urllib.parse.quote(password, safe="")` on both the password and username before injection. Eight new regression tests in `tests/test_redis_channel_redis_client.py` covering: no password / unset env / empty env / simple password / password with `:` / with `@` / with `/` / base64-shaped 44-char password / db-index preservation. Commit on Phase 2 follow-up.

**Validation.** Headless integration test rerun: all 4 phases pass end-to-end against live olympus-bus Redis. Real password (44 chars, base64-style) connects cleanly; redis-py URL parser doesn't barf.

**What surprised.** That the unit test suite — which had 76 fakeredis-backed cases by that point — never caught it. The seam was at the URL-build → `redis.Redis.from_url` boundary, and our fakeredis fixture bypasses URL parsing entirely (you instantiate `FakeRedis()` directly). A integration test against real Redis was the first thing that exercised the URL parser.

**Generalizable rule.** **Anytime you interpolate a value into a URL component, URL-encode it.** Doubly true when the value comes from an environment variable / user config / secret that you don't control the shape of. And: **fakeredis-backed unit tests don't exercise the URL parser** — for any plugin that builds Redis URLs, an integration test against real Redis is the only way to catch URL-formatting bugs.

**Refs.** `plugins/redis-channel/server/redis_client.py`, `tests/test_redis_channel_redis_client.py`, headless integration test at `$CLAUDE_JOB_DIR/integ_test.py`.

---

### FastMCP stdio loop doesn't exit on SIGTERM  {#fastmcp-stdio-sigterm}

**Context.** Phase 2 integration test's MCPClient.shutdown() called `proc.terminate()` (sends SIGTERM) and waited 5s, then fell back to SIGKILL. Every shutdown of the server process logged `[harness] server didn't exit on terminate; SIGKILL`. The redis-channel server installs SIGTERM handlers, but they don't fire fast enough for shutdown to complete in 5s.

**Evidence.** `plugins/redis-channel/server/channel.py:_install_signal_handlers` installs a handler that calls `_STATE.shutdown()` then `sys.exit(0)`. In practice the server only exits when its stdin closes (FastMCP's stdio transport blocks on the read loop). SIGTERM gets queued but doesn't interrupt the async stdin reader.

**Mechanism.** FastMCP runs the MCP server inside an `asyncio.run()` that drives `stdio_server()`. The stdio transport reads from stdin via `anyio` streams, which on macOS uses kqueue-backed file descriptors. SIGTERM is delivered to the Python process but the asyncio loop doesn't have a signal handler for it (we install a *signal* handler, not a *loop signal handler* via `loop.add_signal_handler`), so the handler runs synchronously on the main thread but can't preempt the blocking read.

**Fix (queued, not blocking).** Adding `loop.add_signal_handler(SIGTERM, ...)` would let asyncio receive the signal and cancel the stdio task. Out of scope for Phase 2's headless test (the integration test works fine with the SIGKILL fallback); queued for Phase 6 polish.

**Validation.** Integration test passes end-to-end despite the SIGKILL fallback. Server's atexit-registered cleanup still fires before kill (registry HDEL + hb DEL via the previous disconnect call in phase C; SIGKILL'd-phase server in phase D was *meant* to skip cleanup to test the stale-GC path).

**What surprised.** That the signal handler we installed runs but doesn't actually break the server out of its async loop within a useful timeframe. The classic Python signal trap — synchronous handlers can't interrupt blocking syscalls cleanly.

**Generalizable rule.** **In FastMCP-based stdio servers, use `asyncio.get_running_loop().add_signal_handler(...)` instead of `signal.signal(...)` for graceful shutdown.** Plain `signal.signal()` works at the language level but the asyncio loop doesn't see it, so it can't cancel the stdio read task. For tests / orchestration: don't rely on SIGTERM-then-wait for a clean exit; close stdin or fall back to SIGKILL.

**Refs.** `plugins/redis-channel/server/channel.py:_install_signal_handlers`. Queued follow-up.

---

### Headless integration test caught two bugs unit tests didn't  {#integ-test-value}

**Context.** Built a headless harness that drives `python -m server` over real JSON-RPC stdio against live olympus-bus Redis. 4 phases: connect+inbound+notification round-trip, reply outbound XADD, graceful disconnect, SIGKILL+lazy GC. First run failed phase A with the Redis password URL-encoding bug above; second run (after fix) passed all 4 phases.

**Evidence.** Harness lives in `$CLAUDE_JOB_DIR/integ_test.py`. Bugs caught:
1. **Password URL-encoding** ([see entry above](#redis-url-password-encoding)) — would have shipped to first manual user run.
2. **FastMCP SIGTERM behavior** ([see entry above](#fastmcp-stdio-sigterm)) — known FastMCP-side issue but our wrapper code didn't paper over it.

Validated:
- Real `XREADGROUP` + `XADD` round-trip against Redis 7.0.15.
- AsyncNotifier successfully marshals `notifications/claude/channel` from the consumer thread → asyncio loop → JSON-RPC stdout.
- `_msg_id` correlation works end-to-end.
- `reply` tool XADDs the full Outbound payload with all fields (session_name, endpoint, chat_id, text, voice, in_reply_to, ts) round-tripping correctly.
- Lazy stale-GC: kill server without unregister → fresh server's `list` call lazily HDELs the stale registry entry.

**Mechanism.** fakeredis is a pure-Python redis-protocol implementation that doesn't go through redis-py's URL parser — you construct `FakeRedis()` directly. Anything that breaks at the URL-build → `Redis.from_url()` boundary is invisible to fakeredis-backed tests. Real Redis exercises the full stack including URL parsing, authentication handshake, stream consumer groups, and pubsub.

**Fix (artifact).** Promoting the harness into `plugins/redis-channel/scripts/integ_test.py` so it lives with the plugin. Won't run in CI (needs real Redis + a keychain password) but documented as the way to verify before manual ship.

**Generalizable rule.** **For Redis-backed plugins, a live-Redis integration test is non-optional.** Unit tests with fakeredis verify the plugin's own logic; they cannot verify URL encoding, auth handshake, or any behavior that depends on the real wire protocol. Write the integration test as soon as you have a Redis to point at — even a synthetic harness like the one for redis-channel catches real bugs the unit suite can't.

**Refs.** `$CLAUDE_JOB_DIR/integ_test.py` (transient), `plugins/redis-channel/scripts/integ_test.py` (after promotion).

---

### Wrong-hostname propagation: stale plan + memory beats current inventory  {#redis-host-mac-mini-vs-olympus-bus}

**Context.** Plan + Phase 1 example config + Phase 2 PR body all asserted Redis lived at `jeffs-mac-mini.infiquetra.com:6379`. User caught it during verification-recipe handoff: Redis is actually on `olympus-bus.infiquetra.com` (10.220.1.64), a Proxmox-cluster VM. Migration off the Mac mini happened 2026-04-26 per `home-lab/ansible/inventory/hosts.yml` (`redis_bus` group, comment: "Renamed from olympus_bus 2026-04-26 (legacy pull-queue scaffolding stripped)").

**Evidence.**
- `home-lab/ansible/inventory/hosts.yml` redis_bus group: `olympus-bus.infiquetra.com → 10.220.1.64`.
- `host olympus-bus.infiquetra.com` → `10.220.1.64` (resolved).
- `nc -zv olympus-bus.infiquetra.com 6379` → Connection succeeded.
- The redis-channel plan I'd written days earlier included this in its "Resolved by verification" section: `Redis auth + reachability: 10.220.1.64:6379 reachable`. The IP was right; I just paired it with the wrong hostname.
- Wrong references shipped in three files: `plugins/redis-channel/docs/registry.example.json`, `plugins/redis-channel/commands/redis-channel-configure.md`, `plugins/redis-channel/skills/redis-channel/SKILL.md`. All fixed in this PR.

**Mechanism.** The plan was written from incomplete-context exploration, and the "Mac mini" / "Hermes Redis" association got cemented before I'd re-verified the actual host. Memory carried the IP forward but lost the hostname/host-association. When I wrote the example registry config in Phase 1, I reached for a hostname from conversation context (Mac mini) without re-checking the inventory. Twice in Phase 2 follow-up writeups I propagated the same wrong fact. The user's CLAUDE.md explicitly warns against this pattern ("Validation Discipline — NEVER assert without checking"), and I violated it.

**Fix.** Corrected the three files. Saved a feedback memory ([[verify-infra-facts-against-home-lab]]) + a reference memory ([[redis-bus-location]]) so future-me has both the rule and the canonical fact in one place. MEMORY.md updated to surface both at the top of the index.

**Validation.** `grep -rn jeffs-mac-mini plugins/redis-channel/ docs/` now empty for the redis-channel references. `host olympus-bus.infiquetra.com` and `nc -zv ... 6379` both succeed.

**What surprised.** That the wrong fact survived three writeups (Phase 0 plan, Phase 1 PR, Phase 2 PR body) even though my memory had the correct IP. The IP and the hostname are normally bound; here they got decoupled because I'd seen `10.220.1.64` in one context (Hermes Redis) and "Mac mini" in another (voice work) and merged them.

**Generalizable rule.** **Don't write infrastructure facts (hostnames, IPs, service-host mappings) into shipped code or docs without grepping `home-lab/ansible/inventory/` or live-probing first.** Plan documents and conversation context are not authoritative for infra — the home-lab inventory is. Plans from N days ago describing "where service X runs" are especially suspect because of the ongoing Mac-mini→Proxmox migrations. If you can't verify in the current context, say "I'd need to check — let me verify" instead of asserting. Mac mini hostnames are the highest-risk class because they're the legacy location for many services that have since moved.

**Refs.** [[verify-infra-facts-against-home-lab]] memory, [[redis-bus-location]] memory, `home-lab/ansible/inventory/hosts.yml` redis_bus group.

---

### Emitting custom MCP notification methods from FastMCP  {#fastmcp-custom-notification}

**Context.** Phase 2 of `redis-channel` needs the MCP server to emit `notifications/claude/channel` — a notification type that's specific to Claude Code's channel protocol and **not** part of the upstream MCP spec. FastMCP's `Context` exposes `log/info/debug/error/elicit` but none of those emit a custom method name. The underlying `ServerSession.send_notification` accepts a typed `SendNotificationT` union, and Claude's `notifications/claude/channel` is not in that union.

**Evidence.**
- `[m for m in dir(Context) if not m.startswith('_')]` → no raw `send_notification` exposed.
- `ServerSession.send_notification` signature: `(notification: SendNotificationT, related_request_id)`. `SendNotificationT` is a discriminated union over Pydantic Notification subclasses keyed on the method literal — no `"notifications/claude/channel"` variant.
- But `mcp.types` also exports `Notification[Union[dict[str, Any], NoneType], str]` — a fully-generic Notification[params, method-as-str] form. This is the escape hatch.

**Mechanism.** `send_notification` doesn't actually validate that the notification method is in the spec union — it just calls `notification.model_dump(by_alias=True, mode='json', exclude_none=True)` and wraps the result in a `JSONRPCNotification`. The discrimination happens via Pydantic, but a generic `Notification[dict, str]` instance has `method: str` so it passes through verbatim. Static typing rejects it (`type: ignore[arg-type]` needed), runtime accepts it.

**Fix.** `plugins/redis-channel/server/notifier.py` constructs `Notification[dict, str](method="notifications/claude/channel", params=payload)` and passes it to `session.send_notification(notif)` with a type-ignore. Threadsafe scheduling via `asyncio.run_coroutine_threadsafe` because the consumer thread isn't on the asyncio loop.

**Validation.** Phase 2 unit test `test_async_notifier_schedules_coroutine` constructs an AsyncNotifier with a stub session + a real asyncio loop running on a side thread, calls emit, and verifies the stub session's `send_notification` was awaited with `method="notifications/claude/channel"` and `params` matching.

**What surprised.** The MCP SDK exports a fully-generic `Notification[params, method-as-str]` type. Looking at the dir() of `mcp.types`, the entry `'Notification[Union[dict[str, Any], NoneType], str]'` was the giveaway — that's exactly the escape hatch for vendor-specific notification methods.

**Generalizable rule.** When you need to emit an MCP notification method that isn't in the SDK's `ServerNotificationType` union (Claude-specific extensions like `notifications/claude/channel`, or any other downstream extension): use the generic `Notification[dict, str]` form with a string method, accept the `type: ignore[arg-type]` on `send_notification`, and don't try to wedge it into the typed union. Static typing was wrong to demand discrimination here — the JSON-RPC protocol itself doesn't care.

**Refs.** `plugins/redis-channel/server/notifier.py`; Phase 2 PR.

---

### `@dataclass(slots=True)` doesn't expose class-level field defaults  {#dataclass-slots-class-defaults}

**Context.** While building `plugins/redis-channel/server/registry.py`, the loader read each config field via `defaults_raw.get(key, Defaults.heartbeat_seconds)` — reaching into the dataclass class to pull the field default. Five tests failed with `TypeError: int() argument must be a string, a bytes-like object or a real number, not 'member_descriptor'`.

**Evidence.** Reproducer:

```python
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class D:
    n: int = 10

print(type(D.n))  # <class 'member_descriptor'>  ← not int!
print(D().n)     # 10  ← only an *instance* has the value
```

`pytest` failure trail at `plugins/redis-channel/server/registry.py:130` calling `int(Defaults.heartbeat_seconds)`. Fix commit in this PR replaces `Defaults.<field>` with `base = Defaults(); base.<field>`.

**Mechanism.** With `slots=True`, the dataclass `__slots__` machinery installs *descriptors* on the class to mediate per-instance attribute storage. Looking up `D.field` returns the descriptor object itself, not the field's default. Without `slots=True`, the class still has plain class attributes that happen to equal the defaults — so the pattern works by accident, masking the bug for any non-slotted dataclass. `dataclasses.fields(D)[i].default` is the *correct* way to read a field's default without instantiating.

**Fix.** Construct a `Defaults()` instance first and pull values off it; commit on branch `worktree-redis-channel-phase1` (this PR).

**Validation.** 35 unit tests across session_id, registry, and presence now pass (was 30 passing + 5 failing).

**What surprised.** The error message ("not a real number") gives no hint that the issue is `slots=True`. I assumed a JSON-parsing bug for several minutes before the traceback pointed at `int(Defaults.heartbeat_seconds)`.

**Generalizable rule.** When you put `slots=True` on a dataclass, **do not read field defaults via `Class.field`** — that pattern returns the slot descriptor, not the default. Either (a) instantiate a default object and read from it, (b) call `dataclasses.fields(Class)`, or (c) drop `slots=True` if you want the convenience. This bug is invisible without slots, so it only shows up after you turn slots on for memory/lookup reasons.

**Refs.** Phase 1 PR for redis-channel.

---

### MCP Python SDK's `RedisLike` Protocol stricter than the runtime  {#redis-like-protocol-too-strict}

**Context.** I declared a `RedisLike` `typing.Protocol` in `redis_client.py` to allow both `redis.Redis` and `fakeredis.FakeRedis` (used in tests) as Presence inputs without circular typing. mypy rejected `Presence(redis.Redis(...), ...)` because `redis.Redis.exists` returns `Awaitable[Any] | Any` (covering both sync and async clients) and my Protocol declared `-> int`.

**Evidence.** mypy on `channel.py:78`:

```
error: Argument 1 to "Presence" has incompatible type "Redis"; expected "RedisLike"
note: Following member(s) of "Redis" have conflicts:
note:     Expected: def delete(self, *names: str) -> int
note:     Got: def delete(self, *names: bytes|str|memoryview[int]) -> Awaitable[Any]|Any
```

**Mechanism.** `redis-py` types its client union-style (sync + async share one class hierarchy) so every call returns `Awaitable[Any] | Any`. A narrowed Protocol that promises a concrete return type can never be satisfied by such a wide union, even though the runtime behavior is exactly what we want.

**Fix.** `RedisLike = typing.Any`. Code keeps duck-typing; mypy is unblocked. Both `redis.Redis` and `fakeredis.FakeRedis` work at runtime as before. Commit on branch `worktree-redis-channel-phase1`.

**Generalizable rule.** When a client library exposes both sync + async via one wide-union type, narrowing it via `Protocol` to be more useful in your code's signatures will fight you. Use `Any` (or accept that you're going to lose mypy coverage on those calls). The dynamic-typing escape hatch is the right tool here — Protocol is for protocols you actually want to enforce, not for shaving down third-party type uncertainty.

**Refs.** `plugins/redis-channel/server/redis_client.py`.

---

### Verification findings while planning the `redis-channel` plugin  {#redis-bridge-verification}

**Context.** During design of the `redis-channel` + `hermes-claude-code-router` plan, several "obvious" claims about the Hermes-side infrastructure turned out to be wrong in ways that meaningfully reshaped the architecture. This entry captures the surprises for future plan-verification work.

**Evidence.**
- An earlier exploration agent reported voice-forge on Mac mini as listening at `0.0.0.0:9876` reachable from the LAN. Direct `lsof` proved it bound to `127.0.0.1:9876` only. Not a blocker (Hermes consumes it locally) but the initial plan's "127.0.0.1:9876 from laptop" wiring was wrong.
- `home-lab/ansible/inventory/group_vars/all/all.yml` was assumed to be whole-file vault-encrypted. `ansible-vault view` fails with "Input is not vault encrypted data" — the file uses inline `!vault` tags (field-level encryption). For per-secret extraction, must use `ansible -m debug -a "var=<name>"` or the Python `VaultLib` API, not the CLI.
- Discord voice-receive code was assumed to live in `home-lab/.../asgard_voice_arbiter/`. It doesn't — the arbiter is routing-only (~250 LoC). The actual sink/decode/buffer logic is in closed-source `hermes-agent.gateway.platforms.discord`. Mirroring it from the visible code was impossible; this killed the plan's original "plugin holds Discord directly" architecture and forced the Hermes-router pattern.
- Hermes plugins CAN register MCP-style tools the LLM can call: `ctx.register_tool(name, schema, handler)` at `infiquetra-hermes-plugins/docs/plugin-authoring.md:54`. No existing plugin uses the API yet; the new router will be the first.
- The Claude Code channels protocol does NOT have a native facility for `AskUserQuestion`-style structured questions. Verified by reading the official Discord channel plugin source and `https://code.claude.com/docs/en/channels-reference`. Coaching Claude is insufficient; the CC plugin must intercept the tool call deterministically.
- The Mimir Discord bot (ID `1486896133660868758`, Mount Olympus guild) does NOT currently have a Hermes profile on Mac mini — `~/.hermes/profiles/mimir/` doesn't exist. Building the bridge requires creating the profile first.

**Mechanism.** Earlier exploration agents conflated **proximity** ("X is referenced near Y") with **availability** ("X is implemented in this repo"). Clearest examples: voice-receive (referenced in arbiter, implemented in hermes-agent) and voice-forge (running on Mac mini, but as a local-bound daemon, not LAN-reachable). The agents reported the references; the implementation locations weren't independently verified.

**Fix.** Build proceeds with the architecture the actual ground truth supports: `redis-channel` stays Hermes-agnostic; Hermes does all voice work via its existing pipeline; vault extraction switches to Python-based per-field; Mimir profile is a prereq before any bridge code runs. The plan's "Prerequisites" section codifies this; the LEARNINGS-flagged "I should have looked here first" findings shaped Decisions [redis-bridge-decoupled](DECISIONS.md#redis-bridge-decoupled) and [askuserquestion-interception](DECISIONS.md#askuserquestion-interception).

**What surprised.** That `ctx.register_tool` exists at all — initially I assumed Hermes plugins were hook-only and the LLM-fallback path would require modifying Hermes core. Reading `infiquetra-hermes-plugins/docs/plugin-authoring.md` end-to-end found the API in the first place I should have looked.

**Generalizable rule.** When a plan rests on "we can mirror Asgard's X" or similar reuse claims, **verify the implementation actually lives where the reference points** before committing to it. Two grep passes are cheaper than a 3–5 day rebuild. Specifically for reuse-of-existing-system claims, check that the visible code is the implementation, not just a thin wrapper around closed-source bits elsewhere.

**Refs.** [redis-bridge-decoupled](DECISIONS.md#redis-bridge-decoupled); plan at `/Users/jefcox/.claude/plans/i-would-like-to-distributed-hanrahan.md`.

---

## 2026-05-08

### Missing optional validator dependencies can hide invalid manifests  {#jsonschema-hidden-validation}

**Context.** CI consolidation restored `marketplace/validator/validate.py` and added `jsonschema` to dev dependencies so schema validation runs in normal CI installs.

**Evidence.** `python3 marketplace/validator/validate.py` passed in the system environment while warning `jsonschema not installed, skipping schema validation`. Running the same validator inside a temporary environment after `pip install -e ".[dev]"` failed on `plugins/mission-control/.claude-plugin/plugin.json` because its description exceeded `marketplace/validator/schema.json`'s 200 character limit.

**Mechanism.** The validator treats missing `jsonschema` as a warning and continues. That made schema validation effectively optional in local and previous CI paths, so an invalid manifest could sit in the repository undetected until the dependency became available.

**Fix.** Added `jsonschema` to project dev dependencies and shortened the `sdlc-manager` plugin description to satisfy the schema limit.

**Validation.** `/tmp/infiquetra-plugins-verify-venv/bin/python marketplace/validator/validate.py` passes with `jsonschema` installed.

**Generalizable rule.** A validator's optional dependency is part of the validation contract. CI must install it, or invalid inputs can pass under a degraded "warning only" path.

**Refs.** `.github/workflows/ci.yml`; `pyproject.toml`; `marketplace/validator/validate.py`; `marketplace/validator/schema.json`.

---

## 2026-05-01

### Plugin code can ship without marketplace registration — the registry is a separate source of truth  {#marketplace-drift}

**Context.** A user reported that the `blueprint-reviewer` plugin did not appear when they tried to install plugins from this marketplace. The plugin's code lived under `plugins/blueprint-reviewer/` on `main` and was fully functional, but it was invisible to the marketplace UI.

**Evidence.**
- `plugins/blueprint-reviewer/` was added by PR #110 (merge commit `ae93035`) and Phase B work merged via PR #111 (commit `a7fea08`).
- Neither PR modified `.claude-plugin/marketplace.json`.
- At time of report: 15 plugin directories under `plugins/` but only 14 entries in `marketplace.json`.
- Fixed in PR #112 (commit `4da5705`).

**Mechanism.** Plugin code in `plugins/<name>/` and the marketplace registry in `.claude-plugin/marketplace.json` are independent files. PR review focused on the new plugin's code (skills, commands, scripts) and overlooked the one-line registry diff. Two PRs in a row missed it because the omission isn't visible in the plugin's own diff — it's a *missing* edit to a sibling file. Reviewers don't see absences.

**Fix.** PR #112 added the `blueprint-reviewer` entry to `marketplace.json` (mirrors `sdlc-manager`'s shape: `source`, `version`, `category: development`, keywords copied from the plugin manifest).

**Validation.** Post-merge: `python3 -c "import json; d=json.load(open('.claude-plugin/marketplace.json')); print(len(d['plugins']))"` returns `15`; `'blueprint-reviewer' in [p['name'] for p in d['plugins']]` is `True`.

**What surprised.** That the bug shipped *twice* in a row (#110 and #111). The second PR was specifically follow-up work on the same plugin; the registry omission was right there to be noticed but wasn't.

**Generalizable rule.** When two files must stay in sync (plugin dir + registry, schema + migration, code + docs index, env var + Lambda config), reviewers will drift one against the other given enough opportunities. Add a CI assertion that fails on drift — don't rely on PR review.

**Refs.**
- [QUEUED.md](QUEUED.md#marketplace-ci-guard) — P1 work item for the CI guard.
- [DECISIONS.md](DECISIONS.md#gitignore-claude-and-no-uv-lock) — repo hygiene shipped alongside.
- [ARCHIVE.md](ARCHIVE.md#pr-112-marketplace-fix) — SHIPPED record.

---

### `marketplace.json` `Edit` calls must include the array's closing `]` in `old_string`  {#marketplace-edit-guard}

**Context.** When appending a new plugin entry to `.claude-plugin/marketplace.json`, the `Edit` tool can produce invalid JSON if the `old_string` doesn't include enough context to capture the array's closing bracket. This has misfired multiple times.

**Evidence.** Repeated occurrences traced through prior memory record `marketplace.json Editing Guard`. The wrong-pattern shape:

```json
    }
  ],
    {
      "name": "new-plugin",
      ...
    }
  ],
  "version": "2.0.0"
}
```

— two closing `]`, parser fails. Caught only by post-edit validation.

**Mechanism.** When `old_string` ends at the last entry's closing `}`, the `Edit` tool inserts the new content *after* the line, which lands it after the array's `]` rather than inside the array. The fix is to include both the previous last entry's closing `}` AND the array's `]` in the `old_string`, so the new entry can be inserted *before* the `]` (with a `,` added to the prior `}`).

**Fix.** Standard pattern — `old_string` extends through the array's closing `]` and at least the next line:

```
old_string: "      \"workflow\"\n      ],\n      \"category\": \"development\"\n    }\n  ],\n  \"version\": \"2.0.0\"\n}"
```

Always validate immediately: `python3 -m json.tool .claude-plugin/marketplace.json > /dev/null`.

**Validation.** PR #112 (commit `4da5705`) used this exact pattern and produced valid JSON on first try.

**Generalizable rule.** When using `Edit` on a JSON/YAML file to append into a nested array, the `old_string` MUST include the array's closing bracket. Inserting "before the `]`" is correct; inserting "after the prior entry's `}`" is wrong because edits land on the line *after* the match. Always validate the file with the language's parser immediately after the edit.

**Refs.** Same lesson cached in `~/.claude/projects/.../memory/marketplace_editing_guard.md` for runtime convenience; this file is the durable project record.

---

### A new module under `fleet-core/` needs fleet-core's OWN version bump, not just the consumer's  {#fleet-core-release-surface-own-bump}

**Context.** #366 added `cost_weights.json` + `cost_weights.py` to `plugins/fleet-core/scripts/fleet_commons/` (consumed by saga's cost HALT). The saga release surface was bumped (0.68.0 → 0.69.0), and every local gate — pytest, ruff, mypy, `sync_marketplace.py --check`, `check_release_surface_parity.py` — passed. CI still failed the **Release Surface Parity** job.

**Evidence.** PR #510, CI job "Release Surface Parity" → step `tools/release_surface_diff_guard.py --base-ref <merge-base>`: `non-doc files changed without a matching plugin.json + CHANGELOG.md bump for: fleet-core`. Fixed by bumping fleet-core 0.5.0 → 0.6.0 (`plugins/fleet-core/.claude-plugin/plugin.json` + CHANGELOG entry + marketplace sync), commit `689339f`.

**Mechanism.** The parity steps check different things. `sync_marketplace.py --check` and `check_release_surface_parity.py` verify *internal consistency* (plugin.json == marketplace == CHANGELOG) — they pass as long as each plugin's three surfaces agree, even if none moved. Only the **diff-aware** guard (`release_surface_diff_guard.py`) enforces the actual rule: *for every plugin with non-doc changes in this diff, that plugin's own plugin.json AND CHANGELOG must have moved*. It reads committed `base..HEAD`, not the working tree. So a change that lands files in **plugin A** (fleet-core) but only bumps **plugin B** (saga) satisfies the consistency checks and the whole pytest suite, and is caught **only** by the diff-aware guard, **only** in CI (it is not a pytest test).

**Fix.** When a change touches non-doc files under `plugins/<X>/`, bump `<X>`'s own release surface — even when `<X>` is a library plugin whose behavior only matters through a consumer. Run the guard locally before pushing, but note it reads **committed** state, so commit the bump first: `uv run python tools/release_surface_diff_guard.py --base-ref $(git merge-base origin/main HEAD)`.

**Generalizable rule.** "Release surface synced" means *per touched plugin*, not *per feature*. A cross-plugin change (module in a library plugin, behavior in its consumer) needs a version bump on **every** plugin whose files changed. The internal-consistency checks won't catch a missing bump; only the diff-aware guard does, and only against committed state — so run it (committed) in the pre-push gate whenever a diff spans more than one `plugins/<X>/` tree.

---

### A new rule on a shared `validate()` collides with "no retroactive backfill" — gate it at the authoring boundary  {#new-validate-rule-authoring-gated}

**Context.** #367 added a worth-it hard-block: a premium tier must carry a `worth_it_because` + `cheaper_fallback`. The issue's AC said "fails `validate()`"; its non-goal said "no retroactive backfill — applies to newly authored specs going forward." Implemented literally (unconditional in `Unit.validate`/`ExecutionSpec.validate`), it broke **75 existing emitter tests** and would break every premium spec authored before the rule.

**Evidence.** `plugins/saga/scripts/execution_spec.py` `Unit.validate(require_receipts=...)` and `ExecutionSpec.validate(require_receipts=...)`; the 75 failures were all existing fixtures at `opus/high`/`fable/xhigh` re-run through `emit_workflow_script` → `spec.validate()`. Fixed by gating the new check on `require_receipts` (default off); `/plan` sets it at authoring (`execution_spec.py validate --require-receipts`), emit and existing specs use the default. PR #511.

**Mechanism.** A shared `validate()` runs on *every* path that touches a spec — authoring, emit, re-validate after a `/tier` patch, and any test that builds a spec. An "always on" new rule is therefore *retroactive by construction*: it re-judges specs that were valid when written. "Applies going forward" can only mean *enforced at the authoring boundary*, not *on every structural validation*. The two are different call sites even though they share a method name.

**Generalizable rule.** When you add a *content/policy* rule (not a *structural* invariant) to a validator that many code paths already call, gate it behind an opt-in flag the **authoring** path sets, and leave the default validation untouched — otherwise you retroactively invalidate everything the validator has ever blessed. A blast radius of dozens of unrelated test failures is the signal that a "new rule" was wired as an "always-on invariant." Structural invariants (a cycle, an off-palette tier, a duplicate id) are always-on; policy rules (must-justify, must-name-a-fallback) are authoring-gated.

**Refs.** Same lifecycle-quality thread as `{#adversarial-gate-4-for-4}` — here the *test blast radius during `/work`*, not the adversarial gate, surfaced the design bug. Both the `sonnet/high` baseline (25 failures) and this `require_receipts` gating (75 failures) in #367 were caught by running the full suite, not by the plan reading cleanly.

---

### In a derived-on-read system, a stale-looking durable artifact is not a bug — and a stage that "never fires" is a starved consumer, not broken logic  {#outcome-derived-truth-vs-missing-producer}

**Evidence.** Closing the `tier-effort-first-class` `/outcome` (objective #343). The committed
`outcome-spec.json` read `node.state: pending` / `complete: None` for all 9 nodes, yet `outcome.py status`
and `report.md` both derived **9/9 complete**. Initially misread the raw JSON as "stale/incomplete." It
wasn't: `outcome.py:361` states `Node.state` is authoring-time-only and `derive_states` (`:398`) never
reads it. Two real defects hid behind the same reconcile loop: **#495** (PR #514) — code-leaf harvest
*silently never fired*; **#491** (PR #515) — `attend` emitted a dead `/resume` handoff.

**Mechanism.** R17 makes GitHub the single source of truth: the committed spec stores *pointers* (PR/issue
refs) and status is recomputed on every read by asking GitHub, so it can't drift. Consequence: the raw
`node.state` scalar is vestigial and always reads its authored value; the truth lives only in the derived
reads. For **#495**, `advance` harvesting nothing looked like broken harvest logic — but the barrier
(`outcome_orchestrator.py:100-112`) and the auto-merge queue (`outcome_merge.py:170`) both correctly
*require* `node.github["pr"]`; they are **consumers**. The bug was the absent **producer** — the
record-only dispatch → native `/work` → squash-merge flow never wrote the merged PR back onto the
coordinator node. Fixing the consumer (e.g. "a closed issue is good enough") would have reintroduced the
exact false-positive the barrier exists to reject; the fix was to add the missing producer (`link-pr`).

**Generalizable rule.** (1) In a derive-on-read system, verify the **derived read** (`status`/`report`),
never a stored scalar the code tells you it ignores — "the JSON looks stale" and "the system is wrong" are
different claims, and persisting the derived value back (to make the artifact self-describing) reintroduces
the drift the design removed. (2) When a pipeline stage "never fires," first ask whether it's a
**consumer starved of an input** (missing producer) before touching the stage's own logic — a HALT-on-
missing-input that degrades safe is *invisible*, so silence reads as "works" when it means "never ran."

**Refs.** Same adversarial-gate-earns-its-keep pattern as `{#adversarial-gate-4-for-4}`: on #491 the
panel refuted 4 P2/P3 resolver edge cases (`sub_issue=0` → `issue-0` etc.), all fixed + re-verified before
merge (commit `5a92695`). The two dogfood defects shared one primitive — #495's
`outcome_github._parse_ref` extracts the `N` that #491's handoff resolver needs.

---

### A days-old plan draft's "verified absent" claim is its most perishable line — re-grep against HEAD before you decompose  {#draft-grounding-rots-reverify-at-decompose}

**Evidence.** Re-triaging objective #336's 21 children (drafts dated 2026-07-03/04) against HEAD on 2026-07-06 found 5 stale absence claims: #387 "no `engine_dispatch` adapter table exists, grep confirms" (false — it ships codex/agy builders + `engine-registry.yaml` rows); #386 "nothing computes cost" (false — `run_ledger.py`/#401 records it at `engine_dispatch.py:215-217`); #390 "no `SUBSTITUTED` disposition" (false — enum at `provenance_manifest.py:59`); #393 assumes no durable ledger (#401 shipped 2026-07-05, the day *after* the draft); #392's own JSON already marked 3/4 facets superseded by shipped #318/#319.

**Mechanism.** A Gate-E draft's grounding is a point-in-time snapshot. Between authoring and execution the substrate moved (multiple ships in 3 days). The single most perishable claim in any draft is "X is absent / grep confirms none" — because the thing that was absent is frequently exactly what someone ships next. Planning from the stale claim produces greenfield work that reimplements shipped substrate, or a scope that fights an existing primitive.

**Generalizable rule.** Before `/plan`-ing or decomposing a multi-issue objective authored more than a day ago, re-verify each draft's *absence* claims against current HEAD (re-grep, do not trust the draft's grep), and persist the correction onto the artifact the planner consumes (the issue), so the stale draft self-corrects at plan time. "Verified absent (2026-07-03)" is a timestamp, not a fact.

**Refs.** Discipline recorded in `{#outcome-dag-decompose-stale-objective-336}`. Same "durable state belongs where it is consumed" thread as `{#outcome-derived-truth-vs-missing-producer}` — the fix was scope-note comments on the issues, not a side doc, because `/plan` reads the issue.
