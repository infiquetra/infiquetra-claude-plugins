---
title: Orchestrate / Agent Launcher companion-contract findings from issue 1003
type: fix
status: active
date: 2026-09-16
origin: docs/plans/2026-09-16-issue-1003-companion-contract-finite-test-plan.md
backend: inline
---

# Orchestrate / Agent Launcher companion-contract findings from issue 1003

Repair the eight companion-contract findings grouped under GitHub issue 1003 so Orchestrate's ingest, bind, `status`, and `check` share one companion-state classification, the bound-name contract is enforced in both directions, and the documents that describe that contract match the code, then ship an Orchestrate version ready to pull into Claude Code.

## Problem Frame

Issue 907 shipped Orchestrate 4.x binding Agent Launcher names through `_ingest_agent_launcher` and `_bind_missing_launcher_names`. The terminal review (cycle 3, revision `851ed8d3`) found the contract enforced in one direction only, a name-only stub treated as fully usable, and `status`/`check` lying when the companion was present but unusable. Those eight findings were grouped under #1003 without a run. This plan is the run. Current pairing on `origin/main`: Orchestrate 4.3.0, Agent Launcher 1.5.1, floor still `>=1.4.0`. Orchestrate 4.3.0 no longer calls `say()` as a function; comments and two test docstrings still do. Issue 1002 restored `PANE_INSPECT_MAX_CHARS`; F111's character-cap half already holds and must not be "fixed" away.

## Requirements

R1. A launcher that dropped a name in `REQUIRED_LAUNCHER_NAMES` cannot be selected as a usable write companion, including when `_agent_launcher_script` would pick the highest installed cache version. The shipped `launcher.py` defines every name in that tuple. Dropping one without a major Agent Launcher bump plus an Orchestrate floor move fails the suite. (#952 F101)

R2. Ingesting companion source that fails the usability probe, or a name-only stub whose bound names exist but do not inspect (`guard_pane_before_write` does not call `pane_input_inspection`), does not leave Orchestrate treating that companion as fully usable for pane inspection or writes. The stub is not exec'd into `globals()` as the live guard. (#957 F106)

R3. Read-only `status` degrades (does not `SystemExit`) when the companion is present at the floor but missing a bound name, including a read-path name such as `live_agents`. (#958 F107)

R4. `check` does not print `the record agrees with the repository` and exit 0 when liveness was not performed because the companion is missing or unusable. A usable companion with an empty `live_agents` list still agrees. (#978 F127)

R5. LEARNINGS `{#907-osc-regex-quadratic}` keeps `PANE_INSPECT_MAX_CHARS` as a present-tense fact. The two live helper docstrings in `test_launcher_contract.py` (`_prepare_resend_launch`, `test_redeliver_inspects_before_the_first_write_on_an_owned_unit`) do not present `say()` or `used_pane` as current. Historical past-tense LEARNINGS about those names stay. (#962 F111)

R6. The bolded install sentence in `plugins/orchestrate/commands/orchestrate.md` names the agent-launcher version floor declared in `plugin.json`. The floor number itself does not move. (#973 F122)

R7. The `assert_agent_launcher_available` comments on `cmd_land` and `cmd_review_result` name the live write path (`PaneWriter` / pane-guard send), not `say`. (#977 F126)

R8. The reader-facing bound-name list in `plugins/agent-launcher/skills/agent-launcher/SKILL.md` ("The surface Orchestrate binds") and `REQUIRED_LAUNCHER_NAMES` are the same set, including `ComposerState`. A test fails if they drift. (#980 F129)

R9. Tests drive the shipped ingest, bind, `cmd_status`, and `cmd_check` entry points (and the bound-name cross-check) from real companion trees via `AGENT_LAUNCHER_ROOT` or the installed-plugin cache. They do not mock the unit under test or start past ingest.

R10. Orchestrate version bumps with `plugin.json` / marketplace / CHANGELOG parity. Agent Launcher bumps only if SKILL.md's user-facing bound-name list changed. Companion floor stays `>=1.4.0`. Children #952, #957, #958, #962, #973, #977, #978, #980 close when the PR's required checks succeed.

## Key Technical Decisions

KTD1. One companion-state classification, four values: `missing`, `below-floor`, `ingested-but-unusable`, `usable`. `status`, `check`, and the write gates all read it. `below-floor` still ingests so read-only Herdr commands keep working (`{#907-agent-launcher-floor-owner}`). `ingested-but-unusable` sets `_AGENT_LAUNCHER_AVAILABLE` false so F107 reuses the existing `status` degrade path instead of a second flag that can drift.

KTD2. AST-validate companion source before exec for the F106 probe: required names are defined at module top level, and `guard_pane_before_write` contains a call to `pane_input_inspection`. A source that fails that probe is `ingested-but-unusable` and is **not** exec'd into Orchestrate's globals, so a 30-line stub cannot no-op composer inspection. Floor failures still exec (reads). Post-exec `_bind_missing_launcher_names` remains as belt-and-suspenders for a tree that passed the AST but is missing a name at runtime. Rejected: exec-then-trust-names (F106). Rejected: restricted-namespace exec (out of scope). Rejected: wrapping `guard_pane_before_write` with an Orchestrate-owned inspect (would fork the write rule `{#907-pane-writer-owns-the-write-rule}`).

KTD3. `check` treats skipped liveness as a finding, not agreement. When the classification is `missing` or `ingested-but-unusable`, `cmd_check` records `LIVENESS UNCHECKED -- companion missing or unusable; herdr was not asked` and exits 1. It never prints `the record agrees with the repository` in that state. `below-floor` and `usable` still ask Herdr. Existing agreement tests that import the in-repo launcher stay green; they are a usable companion. Rejected: exit 0 with different prose (still claims success). Rejected: collapsing `below-floor` into unusable (violates KTD7 of #907).

KTD4. Bidirectional pairing is a test, not a floor bump. Direction Orchestrate→launcher: ingest refuses writes when a required name is absent (already true; F107 extends that to reads). Direction launcher→Orchestrate: `test_shipped_launcher_defines_every_name_orchestrate_requires` fails if shipped `launcher.py` drops a required name. The test compares the shipped tree to `REQUIRED_LAUNCHER_NAMES`; it does not encode semver. A legitimate major bump is a later change that updates the tuple, SKILL.md, and the floor together, after which this test compares the new pair. A two-version cache fixture proves the highest cache directory that dropped a name is not a usable write companion even though `_agent_launcher_script` sorts by version. Do not bump the floor; this issue adds no new public name (`{#907-agent-launcher-floor-owner}`, `{#993-release-bump-owns-drift-guards}`). Do not restore `say()`. Rejected: skip-to-next-compatible-cache-version (hides the fault; refuse the write instead). Rejected: a compatibility `say()` shim (the live door is `PaneWriter`).

KTD5. `ComposerState` joins `REQUIRED_LAUNCHER_NAMES`. SKILL.md already lists it; ingest already binds it from `launcher.py` (`ComposerState = _COMPOSER.ComposerState`); `test_the_staged_marker_is_the_composer_enum_value` already reads `orchestrate.ComposerState`. Adding it to the tuple makes the two enumerations agree. SKILL.md names `AccountMismatchError` explicitly so the parser can match the tuple. Rejected: drop `ComposerState` from SKILL.md (would contradict the F25 binding test).

KTD6. Release Orchestrate 4.4.0. Agent Launcher 1.5.2 only if SKILL.md's bound-name wording changed. Floor stays `>=1.4.0`.

## Implementation Units

### U1. Companion ingest and usability

Classify the companion once. A name-only stub and a floor-satisfying tree missing a bound name are unusable for writes and for live reads.

**Goal:** `_ingest_agent_launcher` AST-validates before exec (KTD2), `_bind_missing_launcher_names` still records missing names after a successful exec, and `_AGENT_LAUNCHER_AVAILABLE` is true only for `usable` and `below-floor`.

**Requirements:** R1, R2, R3

**Dependencies:** none

**Files:** `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py`, `tests/test_agent_launcher_plugin.py`, `plugins/agent-launcher/tests/test_launcher_contract.py`

**Approach:** Introduce one helper, called from ingest, that returns the classification. Missing script → `missing` (install remedy). Unreadable or AST-failing source (required name absent, or `guard_pane_before_write` does not call `pane_input_inspection`) → `ingested-but-unusable`, **no exec**. Floor failure on an otherwise usable tree → exec, keep `_AGENT_LAUNCHER_ERROR` as the update remedy, `_AGENT_LAUNCHER_AVAILABLE` true. `_validated_agent_launcher` remaining the floor check is not F106; F106 is the AST usability probe. AST collection counts `FunctionDef` / `ClassDef` **and assignment targets** (`ComposerState = _COMPOSER.ComposerState` in `launcher.py` is the name). For AST-missing names, compose the same operator-visible fault `_bind_missing_launcher_names` already prints — `does not define {names}; Orchestrate requires a release that does` plus `claude plugin update agent-launcher@infiquetra-plugins` — so `test_a_launcher_root_that_lacks_the_bound_names_is_the_named_companion_fault` keeps matching on the write side. A name-only stub (names present, no `pane_input_inspection` call) uses that same update-remedy family, wording that it is unusable, not `not found`. Successful exec whose runtime globals still lack a required name → bind stubs, set `_AGENT_LAUNCHER_AVAILABLE` false, keep that same named error (belt-and-suspenders). `cmd_status` keeps branching on `_AGENT_LAUNCHER_AVAILABLE`; do not add a third flag. Extend `_strip_new_launcher_names` (or a sibling) so a fixture can rename `live_agents` away. Add a ~30-line stub tree and a two-version cache tree (complete floor version plus a higher version with one required name renamed). Discovery still picks the highest cache path; ingest then classifies it unusable.

**Patterns to follow:** `_ingest_agent_launcher` at `orchestrate.py:1851`, `_bind_missing_launcher_names` at `orchestrate.py:1949`, `_agent_launcher_script` cache sort at `orchestrate.py:1743`, `test_a_launcher_root_that_lacks_the_bound_names_is_the_named_companion_fault` at `tests/test_agent_launcher_plugin.py:426`, `{#907-agent-launcher-floor-owner}`.

**Test scenarios:** TP-F101, TP-F106, TP-F107.

**Verification:** `status` against a tree missing `live_agents` exits 0 with no traceback. `go` against a 30-line stub refuses. `go` against a cache whose highest version dropped `PaneWriter` refuses.

---

### U2. Honest `check` when liveness did not run

`check` must not report agreement when it never asked Herdr.

**Goal:** `cmd_check` exits 1 with a `LIVENESS UNCHECKED` finding when the companion classification is `missing` or `ingested-but-unusable`.

**Requirements:** R4

**Dependencies:** U1 (so unusable companions take the same `agents is None` path `status` already uses)

**Files:** `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py`, `tests/test_orchestrate_drift_and_adopt.py`, `tests/test_agent_launcher_plugin.py`

**Approach:** After the existing `if _AGENT_LAUNCHER_AVAILABLE: agents = live_agents() else: agents = None` block, if `agents is None` append the liveness finding. The `if not findings:` agreement branch then cannot fire for that state. Do not change the agreement tests that import the in-repo launcher and monkeypatch `live_agents` to `[]` — those are usable companions whose liveness **did** run. That includes `test_a_clean_run_reports_nothing` and its siblings in `tests/test_orchestrate_drift_and_adopt.py`, plus the agreement assertions in `tests/test_orchestrate_land_clean.py` and `tests/test_orchestrate_run_branch_resolution.py`. Drive the new case through ingest (`AGENT_LAUNCHER_ROOT` or installed cache), not by patching `_AGENT_LAUNCHER_AVAILABLE`.

**Patterns to follow:** `cmd_check` at `orchestrate.py:5372`, `_print_companion_fault_once` at `orchestrate.py:1808`, `test_a_clean_run_reports_nothing` at `tests/test_orchestrate_drift_and_adopt.py:128`.

**Test scenarios:** TP-F127.

**Verification:** `check` with `AGENT_LAUNCHER_ROOT` pointing at a missing tree, a stub, or a missing-name tree does not print `the record agrees with the repository` and does not exit 0. The same command against the shipped launcher with an empty session list still agrees.

---

### U3. Documents, comments, and bound-name agreement

Make the reader-facing contract match the names Orchestrate actually requires, without rewriting history or the restored inspect cap.

**Goal:** SKILL.md list equals `REQUIRED_LAUNCHER_NAMES` (including `ComposerState` and `AccountMismatchError`). `orchestrate.md`'s bolded install sentence names the agent-launcher floor. `cmd_land` / `cmd_review_result` comments name `PaneWriter`. Live test docstrings do not present `say()` / `used_pane` as current. `PANE_INSPECT_MAX_CHARS` stays in LEARNINGS.

**Requirements:** R5, R6, R7, R8

**Dependencies:** U1 (tuple membership of `ComposerState`)

**Files:** `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py`, `plugins/orchestrate/commands/orchestrate.md`, `plugins/agent-launcher/skills/agent-launcher/SKILL.md`, `plugins/agent-launcher/tests/test_launcher_contract.py`, `docs/engineering-journal/LEARNINGS.md` (read-only unless a present-tense `say()`/`used_pane` claim exists outside the historical `{#907-write-flag-tracked-the-door}` entry), `tests/test_agent_launcher_plugin.py`, `docs/engineering-journal/DECISIONS.md`

**Approach:** Append `ComposerState` to `REQUIRED_LAUNCHER_NAMES`. Rewrite SKILL.md's bound-name paragraph so every tuple member appears in backticks, except the account-mismatch error, which stays the prose phrase (the CamelCase class name is a 20-character credential-shaped literal the SKILL.md scanner refuses). The F129 parser maps that phrase to `AccountMismatchError`. Change the bolded install sentence to `Install saga 0.151.0 or later, mission-control 2.15.1 or later, and agent-launcher 1.4.0 or later before relying on this.` — interpolate the floor from the same declared value the tests already read, do not hard-code a new number. Replace `reaching \`say\` and \`close_run_session\`` / `routing resubmits reach \`say\`` with `PaneWriter` / pane-guard send. Edit the two test docstrings to name `PaneWriter` and `should_guard_pane_write` / `wrote_before`. Record KTD1–KTD6 in `DECISIONS.md`. Do not edit `{#907-osc-regex-quadratic}`'s `PANE_INSPECT_MAX_CHARS` sentence.

**Patterns to follow:** SKILL.md "The surface Orchestrate binds" at `SKILL.md:62`, install sentence at `orchestrate.md:500`, comments at `orchestrate.py:3548` and `orchestrate.py:4404`.

**Test scenarios:** TP-F111, TP-F122, TP-F126, TP-F129.

**Verification:** the SKILL.md parser and `REQUIRED_LAUNCHER_NAMES` compare equal. Grep of the two command functions' comments has no `say`. The install sentence contains `agent-launcher` and `1.4.0`.

---

### U4. Release surfaces

Bump only the plugins whose user-facing contract changed, keep marketplace and CHANGELOG in the same commit.

**Goal:** Orchestrate 4.4.0 on `plugin.json`, `.claude-plugin/marketplace.json`, and `plugins/orchestrate/CHANGELOG.md`. Agent Launcher 1.5.2 on the same three surfaces only if U3 changed SKILL.md's bound-name wording. Floor stays `>=1.4.0`.

**Requirements:** R10

**Dependencies:** U1, U2, U3

**Files:** `plugins/orchestrate/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `plugins/orchestrate/CHANGELOG.md`, and the Agent Launcher equivalents if SKILL.md changed

**Approach:** Follow `{#993-release-bump-owns-drift-guards}`. Update every assertion that pins Orchestrate `4.3.0` as the current version. Do not touch `AGENT_LAUNCHER_FLOOR_RELEASE`.

**Patterns to follow:** issue 1002's 1.5.0/1.5.1 bump, `test_agent_launcher_metadata_is_marketplace_registered`.

**Test scenarios:** version-parity rows in the finite test plan.

**Verification:** marketplace `orchestrate` version equals `plugin.json`; CHANGELOG has `## [4.4.0]`.

## Scope Boundaries

Out of scope:

- Findings grouped under #908, #909, #910, or #1002.
- Nesting a further parent under #1003, or treating the parent's "grouping, not a run" sentence as a refusal of this plan.
- Restoring `say()` as the live write path.
- Bumping the Orchestrate companion floor in lockstep with an Agent Launcher patch that adds no new public name.
- Merging to `main` by force-push.
- `/founder-review` or `/ceo-review` unless a doc-review finding demands it.
- Repairing in-the-wild Orchestrate 4.0.1 that still called `say()`; this tree no longer does.

Deferred to follow-up: none. The eight children are this plan.

## Success Metrics

- Finite test plan rows TP-F101, TP-F106, TP-F107, TP-F111, TP-F122, TP-F126, TP-F127, TP-F129 are green against the shipped entry points.
- Four-state CLI matrix (`--help`, `status`, `check`, one write command) matches twice.
- `/code-review` `derived_overall >= 9.0`, every selected lens `accepted`, applicable-dimension floor `>= 7.0`, at most three repair cycles. `cycle_cap_best_available` below 9.0 is failure.
- PR targeting `main` with required checks (Tests Python 3.12, Validate Plugins, Lint, Type Check, Security Scan strict) concluding success.
- Children #952, #957, #958, #962, #973, #977, #978, #980 closed.
