---
title: Mission Control alignment finite independent test scenarios
type: test
status: active
date: 2026-09-13
origin: https://github.com/infiquetra/infiquetra-claude-plugins/issues/1004
issues: ["#1004", "#999", "#1000", "#942"]
candidate: ea7963a4bbf735b7179bd2d2605af740a1f8c2e7
---

# Mission Control alignment — finite independent test scenarios

Assignment **MC-ALIGN-02-TEST**. Test Author only. This document specifies the
automated cases Dev must satisfy before and during production work. It does not
author production code, reopen Jeff's readiness decisions, or add behavior
beyond issues #999, #1000, and #942.

**Candidate:** `ea7963a4bbf735b7179bd2d2605af740a1f8c2e7` (`origin/main`).
**Source schema:** `infiquetra-sdlc` `config/sdlc-schema.json` `schema_version`
`2026-09-07.5` (`origin/main` `67845cd` as recorded on #999).
**Vendored copy at candidate:** `plugins/mission-control/config/sdlc-schema.json`
`schema_version` `2026-08-29`.

The denominator is **23** named rows (T999-01–T999-04, T1000-01–T1000-09,
T942-01–T942-10). Existing tests that pin the pre-alignment contract are listed
as required updates, not extra T-IDs.

## Problem frame (candidate `ea7963a4`)

These facts are the red baseline the new rows must catch. They are observations,
not new requirements.

1. **#999.** Vendored `schema_version` is `2026-08-29`.
   `plugins/mission-control/tests/test_prompt_alignment.py:173` pins that
   literal. Production still reads the removed keys:
   `sdlc_manager._wip_limits` at
   `plugins/mission-control/scripts/sdlc_manager.py:463-480` does
   `schema.get("wip_limits", {})` and
   `config.get("legacy_rollout_config", {}).get("wip_limits", {})`.
   Callers: `sdlc_manager.py:1232` and `:1445`. The vendored schema still has
   top-level `wip_limits` (`:241`) and `work_hierarchy.component_slices`
   (`:201`). The source schema has neither: `wip_limits` is deleted (E6);
   `work_hierarchy.components` replaced `component_slices` (E7).
2. **#1000.** Vendored `issue_fields.fields` has thirteen keys and no `risk`.
   `config/generated/issue_contract_data.py` `FIELD_HEADERS` / `REQUIRED_FIELDS`
   omit `risk`. `validate_card_body_for_context` therefore cannot require
   `### Risk`. Prepare still treats Risk as sidecar metadata
   (`PreparedIssue.risk`, `--risk`) and maps it to project field
   `Technical Risk` (`_PREPARED_FIELD_RISK` at `sdlc_manager.py:4343`).
   Asgard readiness requires a free-text `### Risk` section
   (`sdlc_manager.py:5328-5344`) whose fixture value is `Low operational risk.`
   (`test_issue_prepare.py:61-62`) — not the E1 token+justification form.
   `flow_set_field` (`sdlc_manager.py:2766`) writes project fields only; it has
   no `repair-window` label arm and no citation requirement.
3. **#942.** `_HANDOFF_MATURITY_CHOICES` (`sdlc_manager.py:4262-4268`) is the
   five routable values and omits `pending-confirmation`.
   `_infer_maturity_from_path` (`:4475-4487`) is path-only:
   `docs/brainstorms/` → `requirements-ready`;
   `docs/sdlc-issue-drafts/` and `.claude/saga/` → `resume-ready`.
   `_suggested_next_action` (`:4803`) KeyErrors on `pending-confirmation`.
   `_render_handoff_context` (`:4819`) defaults a missing maturity to
   `requirements-ready`. Mission Control does not import Saga
   `handoff_envelope.infer_maturity`. Saga's own unmarked-path fallback is
   still `_path_maturity` → `requirements-ready`
   (`plugins/saga/scripts/handoff_envelope.py:324-346`); Jeff's 2026-09-13
   decision on #942 requires drafts and Saga state files to fail closed
   instead of using that fallback.

## Boundaries

- Automated pytest only. No live GitHub, no board mutation, no template push.
- Do not invent Risk tokens, readiness states, or label names beyond the
  vendored schema / Saga vocabulary named below.
- Do not re-specify production design. Call the public Mission Control surfaces
  that already exist (`issue_prepare`, `issue_create_prepared`,
  `validate_card_body` / `validate_card_body_for_context`,
  `_readiness_for_prepared_issue`, `resolve_source_artifact`,
  `_render_handoff_context`, `flow_set_field`) plus the Saga-owned readiness
  function Mission Control must call after #942.
- #1000 rows assume #999 has re-vendored `issue_fields` so `risk` is the
  fourteenth field. #942 is independent of the schema bump.
- High / `very-high` Risk still require the existing risk-conditional trio
  (`Inputs inventory`, `Failure modes / pre-mortem`, `Stop conditions`). Those
  fields are part of the current matrix, not new scope.

## Key test decisions

- **KTD1.** Fixed T-IDs. A row is `pass`, `fail`, or `blocked`. Do not drop a
  row to make a count look green.
- **KTD2.** New rows live in the files named below. Required updates to
  existing files are a closed table; Dev updates those oracles when the
  vendored contract moves. Do not weaken a pin to silence it.
- **KTD3.** No network. Patch `_rest_post`, `_rest_delete`, `_create_github_issue`,
  `flow_set_field` (when the test is not itself the set-field subject), and
  reuse `_intake_exit_patches` from
  `plugins/mission-control/tests/test_issue_create_prepared.py:503-520`.
- **KTD4.** #942 exercises real on-disk documents through `issue_prepare` /
  `resolve_source_artifact`, then asserts agreement with the Saga-owned
  function on the same path. Constant-only maturity strings are not enough
  for T942-01, T942-02, T942-03, T942-05, or T942-06.
- **KTD5.** Suite-pass (T999-03) is `uv run pytest plugins/mission-control/tests -q`
  ending in `passed` with `0 failed`. That is the #999 acceptance command
  (`cd plugins/mission-control && python3 -m pytest -q`) expressed in this
  repo's runner. Do not pin a test count.

## Shared fixtures

Use these exact bodies. Copy into the named test modules; do not load live
issues.

### F-CORE — always-required thirteen-field body (no Risk)

Same shape as `test_issue_prepare.py` `OLYMPUS_BODY` (lines 20–46): Objective,
Intent, Acceptance criteria with a runnable `code span`, Out-of-scope,
Files expected, Tests, Verification fenced block, Context library links
`_none_`. After #1000 this body is schema-invalid because `### Risk` is
missing.

### F-RISK(token, why) — fourteenth field

```text
### Risk
{token}
{why}
```

`{token}` is exactly one of `low`, `medium`, `high`, `very-high`, `UNKNOWN`.
`{why}` is one sentence. Example why: `The change is confined to a pin test.`

### F-CONDITIONAL — risk-conditional trio (required at high / very-high)

```text
### Inputs inventory
- plugins/mission-control/tests/test_issue_risk_field.py

### Failure modes / pre-mortem
If the Risk token is dropped, restore the fourteenth field from issue_fields.

### Stop conditions
Stop if issue_fields.fields has no key risk.
```

### F-VALID(token) — readiness-capable actionable body

`F-CORE` + `F-RISK(token, "The change is confined to a pin test.")` +
(`F-CONDITIONAL` when `token` is `high` or `very-high`).

### F-BRAINSTORM-PENDING — on-disk Path B artifact

Path: `{root}/docs/brainstorms/2026-09-13-alignment-boundary.md`

```text
---
topic: alignment-boundary
date: 2026-09-13
maturity: pending-confirmation
---

# Alignment boundary

Proposed scope only. Not confirmed.
```

### F-DRAFT-BARE — saved issue draft with no readiness key

Path: `{root}/docs/sdlc-issue-drafts/2026-09-13-bare-draft.md`

A markdown card (may include F-CORE) whose frontmatter, if any, has **no**
`maturity` / `handoff_maturity` key.

### F-STATE-BARE — Saga state file with no readiness key

Path: `{root}/.claude/saga/state.json`

```json
{"current_work": {"plan_path": "docs/sdlc-issue-drafts/2026-09-13-bare-draft.md"}}
```

No maturity / readiness field on the state object.

### F-CITE-FAIL / F-CITE-PASS

- Fail: `uv run pytest plugins/mission-control/tests/test_issue_risk_field.py::test_placeholder -q` → `1 failed`
- Pass: `uv run pytest plugins/mission-control/tests/test_issue_risk_field.py::test_placeholder -q` → `1 passed`

## Recognized readiness vocabulary (do not extend)

Saga `HANDOFF_MATURITIES`
(`plugins/saga/scripts/handoff_envelope.py:53-60`):

| State | Routable live `/plan` or `/work`? |
| --- | --- |
| `idea-ready` | yes (`/plan`) |
| `requirements-ready` | yes (`/plan`) |
| `plan-ready` | yes (`/work`) |
| `resume-ready` | yes (`/work`) |
| `deferred-context` | no live plan/work dispatch (clarify; existing deferred prose) |
| `pending-confirmation` | no |

Non-vocabulary shapes that must also stay non-routable (already Saga-owned;
#942 AC additions): empty declaration, `unknown:unreadable`,
`unknown:unterminated:`, `unknown:carrier:`, `unknown:unrecognized:`,
`unknown:out-of-root:`.

`ROUTABLE_MATURITIES` = the five values except `pending-confirmation`.
A live route means the rendered suggested next action contains `/plan` or
`/work` as a runnable command. Deferred-context may keep its current clarify
sentence; it must not gain a `/plan` or `/work` command.

---

## #999 Schema re-sync

**New file:** `plugins/mission-control/tests/test_schema_resync.py`

**Patterns:** `test_prompt_alignment.py:169-173` (version pin),
`test_lifecycle_writer_census.py:64-75` (scan/allowlist),
`test_issue_contract_parity.py:122-132` (issue_fields presence).

### T999-01 — schema version is 2026-09-07.5

| | |
| --- | --- |
| **File** | `plugins/mission-control/tests/test_schema_resync.py` |
| **Input** | `plugins/mission-control/config/sdlc-schema.json` |
| **Action** | `json.loads(...)["schema_version"]` |
| **Assert** | equals `"2026-09-07.5"`. Also assert that
`grep`-equivalent scan of `plugins/mission-control` for `"schema_version"`
finds `2026-09-07.5` in the vendored copy (issue #999 AC1 as amended
2026-09-13). |
| **Red today** | file reads `"2026-08-29"`. |

### T999-02 — no production code reads removed `wip_limits` or `component_slices`

| | |
| --- | --- |
| **File** | `plugins/mission-control/tests/test_schema_resync.py` |
| **Input** | Walk `plugins/mission-control/**`. Match `wip_limits` and
`component_slices` as whole identifiers. |
| **Allow** | `CHANGELOG.md` historical notes; JSON `migration_notes` strings;
`gate_catalogue` retired-row prose; `work_hierarchy.components.source_note`
historical sentence that *names* the old key. |
| **Deny** | any `.py` identifier, any live schema key
(`schema["wip_limits"]` present, or `work_hierarchy["component_slices"]`
present), any `schema.get("wip_limits"` / `["component_slices"]` read. |
| **Assert** | deny-set is empty; ` "wip_limits" not in schema`;
`"component_slices" not in schema.get("work_hierarchy", {})`;
`"components" in schema["work_hierarchy"]`. Failure message lists
path:line of each deny hit. |
| **Red today** | `sdlc_manager.py:467`, `:471`, `:1232`, `:1445`; schema
keys at `sdlc-schema.json:201` and `:241`. |

### T999-03 — existing mission-control plugin suite passes

| | |
| --- | --- |
| **File** | recorded as the CI/gate command, not a pytest that shells itself |
| **Input** | tree after #999 production + required existing-test updates |
| **Action** | `uv run pytest plugins/mission-control/tests -q` |
| **Assert** | summary line ends in `passed`; `0 failed`. Do not pin collected
count. |
| **Note** | this row stays `fail` until the required-update table below is
applied. A green T999-01/02 with a red pin in
`test_prompt_alignment.py` is not suite-pass. |

### T999-04 — required existing-test oracles move with the re-sync

| | |
| --- | --- |
| **File** | existing files listed below (updates, not new T-IDs) |
| **Input** | same vendored schema as T999-01 |
| **Assert** | each listed pin matches `2026-09-07.5` / post-E6/E7 shape, or
the WIP reader it mocked is gone. See Required existing-test updates. |

---

## #1000 Fourteenth field Risk and `repair-window` label

**New files:**

- `plugins/mission-control/tests/test_issue_risk_field.py`
- `plugins/mission-control/tests/test_repair_window_label.py`
- `plugins/mission-control/tests/test_technical_risk_retirement.py`

**Patterns:** `test_issue_prepare.py` prepare+sidecar;
`test_issue_create_prepared.py:696-726` create-prepared +
`_intake_exit_patches`; `test_flow_subcommands.py:1-10` REST mocks;
`test_issue_contract_parity.py:141-167` field-header oracles;
`test_template_sync.py:21-43` stale-term / required-field lists.

Risk is compiled from vendored `issue_fields.fields[key=risk]`:
header `Risk`, required, first line one of `low|medium|high|very-high`,
next line one sentence; `UNKNOWN` is schema-legal and not ready
(source schema `issue_fields` at `infiquetra-sdlc` `:2310-2318`).
`risk:` labels and `--risk` metadata are not a source (issue #1000 E1).

### T1000-01 — missing `### Risk` blocks prepare with a message naming Risk

| | |
| --- | --- |
| **File** | `plugins/mission-control/tests/test_issue_risk_field.py` |
| **Input** | `issue_prepare(repo="hermes-claude-code-router",
issue_type="enhancement", team="asgard", project="asgard", source=F-CORE,
title="t", status=None, risk=None, mode=None, stage="Intake",
draft_dir=tmp_path)` — the #1000 AC command, as the Python callee. |
| **Assert** | sidecar `state == "blocked"`;
`readiness.passed is False`; some `blocking_gaps` item names `Risk`
(the field), not only `author-visible risk metadata`.
`validate_card_body_for_context(F-CORE, "enhancement", None)` is
`(False, errors)` and some error names `Risk`. |
| **Also** | `--risk="medium"` with body F-CORE (no `### Risk`) still
blocks and still names `Risk`. A `risk:medium` label in `labels=`
does not satisfy the field. |

### T1000-02 — missing `### Risk` blocks create-prepared; no GitHub create

| | |
| --- | --- |
| **File** | `plugins/mission-control/tests/test_issue_risk_field.py` |
| **Input** | draft from T1000-01; `_intake_exit_patches(draft)`;
`issue_create_prepared(draft, fmt="text", auto_confirm=True)` |
| **Assert** | `pytest.raises(RuntimeError, match="blocking readiness")`;
`_create_github_issue` not called; sidecar `state != "post_create_pending"`.
Exception text or readiness gaps name `Risk`. |

### T1000-03 — valid tokens `low`, `medium`, `high`, `very-high` pass

| | |
| --- | --- |
| **File** | `plugins/mission-control/tests/test_issue_risk_field.py` |
| **Input** | parametrize `token` in `("low", "medium", "high", "very-high")`.
Body = `F-VALID(token)`. `issue_prepare(..., issue_type="enhancement",
team="campps", project="campps", source=body, risk=None, stage="Intake")`. |
| **Assert** | `validate_card_body_for_context(body, "enhancement", token)`
is `(True, [])` or errors empty of Risk; sidecar `readiness.passed is True`
when the rest of F-VALID is present; sidecar `risk == token` (or the
compiled field value equals `token`); draft body contains `### Risk` with
that first line. High / `very-high` without `F-CONDITIONAL` must still
fail — but on the trio headers, not on Risk format. |

### T1000-04 — `UNKNOWN` passes schema check and fails readiness

| | |
| --- | --- |
| **File** | `plugins/mission-control/tests/test_issue_risk_field.py` |
| **Input** | `F-CORE + F-RISK("UNKNOWN", "Architect has not yet assessed blast radius.")`.
Prepare as T1000-03. |
| **Assert** | field/schema check accepts the block (no "missing Risk", no
"invalid Risk format"). `_readiness_for_prepared_issue` `passed is False`.
A blocking gap names `Risk` and `UNKNOWN` (card is not ready while it
reads UNKNOWN). `issue_create_prepared` raises `blocking readiness` and
does not call `_create_github_issue`. |

### T1000-05 — invalid format or missing justification is blocked

| | |
| --- | --- |
| **File** | `plugins/mission-control/tests/test_issue_risk_field.py` |
| **Input** | parametrize bodies: (1) F-CORE + `### Risk\nLow operational risk.\n`
(current Asgard prose); (2) F-CORE + `### Risk\nmedium\n` (token, no
justification sentence); (3) F-CORE + `### Risk\nextreme\nNot a vocabulary token.\n`;
(4) F-CORE + `### Risk\n\n`. |
| **Assert** | each prepare is `blocked`; `readiness.passed is False`; a gap
names `Risk`. None of these is treated as T1000-03-valid. |

### T1000-06 — `repair-window` set with cited failing result

| | |
| --- | --- |
| **File** | `plugins/mission-control/tests/test_repair_window_label.py` |
| **Input** | `flow set-field` Python callee (`flow_set_field` or the
set-field-owned helper it dispatches to) with label/marker `repair-window`,
set/present action, `reason` or citation = `F-CITE-FAIL`,
`repo="hermes-claude-code-router"`, `number=42`. Patch `_rest_post` /
`issue_label_add`. |
| **Assert** | label write fires once with `"repair-window"`;
citation `F-CITE-FAIL` appears in emitted evidence or the recorded
comment/reason; no project-field GraphQL write for this label
(`QUERY_SET_FIELD_VALUE` not used for `repair-window`). |

### T1000-07 — `repair-window` cleared with cited passing result

| | |
| --- | --- |
| **File** | `plugins/mission-control/tests/test_repair_window_label.py` |
| **Input** | same path, clear/absent action, citation = `F-CITE-PASS`.
Patch `_rest_delete` / `issue_label_remove`. |
| **Assert** | remove (or idempotent 404 success) for `repair-window`;
`F-CITE-PASS` in evidence; no GraphQL project-field write. |

### T1000-08 — `repair-window` refused without citation

| | |
| --- | --- |
| **File** | `plugins/mission-control/tests/test_repair_window_label.py` |
| **Input** | set and clear actions with `reason=None`, `reason=""`, or
omitted citation. |
| **Assert** | `RuntimeError` (or typed error) whose message names
citation/result; `_rest_post` and `_rest_delete` not called. |

### T1000-09 — queued Technical Risk project-field item is retired or removed

| | |
| --- | --- |
| **File** | `plugins/mission-control/tests/test_technical_risk_retirement.py` |
| **Input** | case-insensitive scan of `plugins/mission-control` for
`technical risk`. Exclude `docs/sdlc-issue-drafts/**` (historical
sidecars, not the queue). |
| **Allow** | `CHANGELOG.md` history; `test_template_sync.py`
`STALE_ACTIONABLE_TERMS` denylist (already lists `"Technical Risk"`);
a retirement note that contains `E1`. |
| **Deny** | live queue language
(`"decided, not yet created"` listing Technical Risk at
`sdlc_manager.py:4301-4305` / `:6447` / `:6562` without E1);
`_PREPARED_FIELD_RISK == "Technical Risk"` as a live project-field
source; new prompts that treat Technical Risk as a project field to
create. |
| **Assert** | deny-set empty; vendored `issue_fields` has
`fields_by_key["risk"]["header"] == "Risk"` and `required is True`;
`REQUIRED_MATRIX` always-required rule includes `risk`
(source `required_matrix.rules[0].fields`). |

---

## #942 Saga-owned readiness alignment

**New file:** `plugins/mission-control/tests/test_saga_readiness_alignment.py`

**Also update:** `plugins/mission-control/tests/test_issue_source_artifacts.py`
(path-only inferences that today assert `requirements-ready` /
`resume-ready`).

**Patterns:** `test_issue_source_artifacts.py:17-37` tmp-root writers;
`tests/test_handoff_envelope_maturity.py` declaration-over-path,
containment, unknown sentinels. After #942 Mission Control must call the
Saga-owned owner (today `handoff_envelope.infer_maturity` /
`resolve_source`) rather than `_infer_maturity_from_path`. Tests assert
through MC public APIs **and** that those APIs agree with that owner on
the same fixture. Do not implement a second parser in the test.

Routability check on the MC card: sidecar `handoff_maturity`, body
`### Handoff maturity`, and `### Suggested next action` from
`_render_handoff_context`. A live route is a suggested action containing
`/plan` or `/work`.

### T942-01 — pending-confirmation brainstorm reaches the card as pending-confirmation

| | |
| --- | --- |
| **File** | `plugins/mission-control/tests/test_saga_readiness_alignment.py` |
| **Input** | write `F-BRAINSTORM-PENDING` under `tmp_path`.
`artifact = resolve_source_artifact("docs/brainstorms/2026-09-13-alignment-boundary.md", tmp_path)`.
`issue_prepare(..., source=artifact.content, source_artifact=artifact,
handoff_maturity=None, stage="Intake", draft_dir=tmp_path, source body
may be F-VALID("low") if prepare still scaffolds)`. |
| **Assert** | `artifact.inferred_maturity == "pending-confirmation"`
(not `requirements-ready`). Sidecar `handoff_maturity == "pending-confirmation"`.
Draft `### Handoff maturity` is `pending-confirmation`. Suggested next
action has no `/plan` and no `/work`.
`issue_prepare` does not raise `Unknown handoff maturity 'pending-confirmation'`.
Same path through the Saga-owned function returns `pending-confirmation`. |

### T942-02 — saved issue draft without explicit readiness is non-routable

| | |
| --- | --- |
| **File** | `plugins/mission-control/tests/test_saga_readiness_alignment.py` |
| **Input** | write `F-DRAFT-BARE`. Resolve/prepare from that path with
no `--maturity` override. |
| **Assert** | maturity is **not** `resume-ready` and **not**
`requirements-ready`. Not in `ROUTABLE_MATURITIES`. Suggested next
action has no `/plan` or `/work`. Diagnostic / gap names that readiness
is not established (clarification), and names the draft path class
(`docs/sdlc-issue-drafts`). Both entry points agree. |

### T942-03 — Saga state file without explicit readiness is non-routable

| | |
| --- | --- |
| **File** | `plugins/mission-control/tests/test_saga_readiness_alignment.py` |
| **Input** | write `F-STATE-BARE` (and the draft it points at, also
undeclared). Resolve `.claude/saga/state.json` or the state-backed
source with no maturity override. |
| **Assert** | same fail-closed as T942-02: not `resume-ready`, not
`requirements-ready`, no live `/plan` or `/work`, diagnostic names
missing declaration and the Saga state path class (`.claude/saga`).
Both entry points agree. Location alone is not readiness. |

### T942-04 — all six recognized states; declared state overrides folder

| | |
| --- | --- |
| **File** | `plugins/mission-control/tests/test_saga_readiness_alignment.py` |
| **Input** | parametrize `state` over the six `HANDOFF_MATURITIES`.
Write `{root}/docs/brainstorms/declared.md` with frontmatter
`maturity: {state}` (folder would path-infer `requirements-ready`).
Also write one `docs/plans/declared.md` and one
`docs/sdlc-issue-drafts/declared.md` with the same declared `state`. |
| **Assert** | for every folder, inferred and sidecar maturity equal
`state`. Routability matches the table above. Declared value wins over
folder location. Both entry points agree on maturity and whether a live
route is offered. |

### T942-05 — named-root containment; out-of-root is refused

| | |
| --- | --- |
| **File** | `plugins/mission-control/tests/test_saga_readiness_alignment.py` |
| **Input** | `tmp_path` as declared root. Outside the root, write a
file whose frontmatter says `maturity: requirements-ready` (or
`plan-ready`). Call MC resolve/prepare with (1) an absolute out-of-root
path, (2) a relative `../` escape, (3) an in-root symlink whose target
is out-of-root. No explicit external-source selection. |
| **Assert** | source is not read for its declaration. Maturity is the
`unknown:out-of-root:` sentinel (or MC's equivalent non-routable
diagnostic that names the refused path). No live `/plan` or `/work`.
Published source identity is the refused path, not a silently rewritten
in-root twin presented as the original. An in-root marker-directory
*twin that declares nothing* does not authorize the outside original
(Saga `test_reanchored_missing_twin_is_refused`). Both entry points
agree. |

### T942-06 — explicit external-source selection preserves source identity

| | |
| --- | --- |
| **File** | `plugins/mission-control/tests/test_saga_readiness_alignment.py` |
| **Input** | same out-of-root file as T942-05. Invoke the MC path that
represents an **explicit** operator source choice for that external
document (the selection the #942 decision requires; not a bare path
that bypasses containment). |
| **Assert** | the file that is read is the selected source; the
published handoff `Source:` / `source_artifact.ref` (and Saga envelope
`published` source) is that same identity — not a different in-root
counterpart. Selecting a contained counterpart is a different choice
and must publish *that* counterpart, not the outside original. Without
the explicit selection, T942-05 still refuses. |

### T942-07 — missing Saga dependency diagnostic; no readiness route

| | |
| --- | --- |
| **File** | `plugins/mission-control/tests/test_saga_readiness_alignment.py` |
| **Input** | monkeypatch the MC import site for the Saga-owned
readiness module so import raises `ImportError`. Then call
`resolve_source_artifact` / `issue_prepare` / `_render_handoff_context`
on `F-BRAINSTORM-PENDING`. |
| **Assert** | a clear diagnostic names the missing Saga dependency
(module/import). No live `/plan` or `/work`. No fallback to
`_infer_maturity_from_path` (`requirements-ready` /
`resume-ready`). An unrelated helper still runs (smoke:
`validate_card_body(F-CORE)` or `issue_label_add` with REST patched). |

### T942-08 — incompatible Saga dependency diagnostic; no readiness route

| | |
| --- | --- |
| **File** | `plugins/mission-control/tests/test_saga_readiness_alignment.py` |
| **Input** | two incompatibilities, parametrized: (1) imported module
has no `infer_maturity` (or the named owner attribute); (2) imported
vocabulary omits `pending-confirmation`. |
| **Assert** | diagnostic names incompatibility (missing symbol or
vocabulary). No live route. No silent use of the old MC path-only
logic. |

### T942-09 — invalid, duplicate, malformed, unreadable, unknown: never live-route

| | |
| --- | --- |
| **File** | `plugins/mission-control/tests/test_saga_readiness_alignment.py` |
| **Input** | real files under `tmp_path`, one each: unrecognized
`maturity: bogus-value`; duplicate top-level `maturity` keys (first
`pending-confirmation`, second `plan-ready`); `maturity: plan-ready`
outside a `---` block; unterminated `---`; unreadable / non-UTF8 bytes
with no recoverable `maturity:`; blank `maturity:`. Run through MC
prepare/source **and** the Saga-owned function. |
| **Assert** | each result is a non-routable `unknown:` sentinel or
empty/clarification shape as Saga already defines. No
`requirements-ready` fallback. Suggested action has no `/plan` or
`/work`. Both entry points agree. This preserves #950 / #942
reproduction rows (invalid value; carrier outside fence). |

### T942-10 — both entry points agree on the shared owner; no second parser

| | |
| --- | --- |
| **File** | `plugins/mission-control/tests/test_saga_readiness_alignment.py` |
| **Input** | the fixture set from T942-01–T942-06 and T942-09. |
| **Assert** | for each fixture, MC `SourceArtifact.inferred_maturity`
equals the Saga-owned function's return value. MC suggested-action
liveness (has `/plan` or `/work`) equals
`maturity in ROUTABLE_MATURITIES`. `sdlc_manager.py` text scan:
readiness inference call sites import/call the Saga owner; a new
MC-local maturity parser is not introduced (no second
`_infer_maturity_from_path` semantics). `_HANDOFF_MATURITY_CHOICES`
includes `pending-confirmation`. |

---

## Required existing-test updates (closed list)

These pins will go red when the T-rows above are honest. Updating them is
in scope for the child that owns the pin. Do not add new behavior here.

| File | Why it moves | Child |
| --- | --- | --- |
| `plugins/mission-control/tests/test_prompt_alignment.py:173` | `schema_version == "2026-08-29"` → `"2026-09-07.5"` | #999 |
| `plugins/mission-control/tests/test_issue_contract_parity.py` | `EXPECTED_FIELD_HEADERS` / `EXPECTED_REQUIRED_FIELDS` / `EXPECTED_SHIM_REQUIRED_H3` gain `risk` / `Risk`; `EXPECTED_DATA_SHA256` / `EXPECTED_SHIM_SHA256` retarget after re-vendor | #1000 (after #999 re-vendor) |
| `plugins/mission-control/tests/test_template_sync.py:34-43` | `EXPECTED_ACTIONABLE_REQUIRED_FIELDS` gains `Risk`; keep `"Technical Risk"` in `STALE_ACTIONABLE_TERMS` | #1000 |
| `plugins/mission-control/tests/test_issue_prepare.py` | `OLYMPUS_BODY` needs `F-RISK` for passing cases; `ASGARD_BODY` `Low operational risk.` becomes T1000-05-invalid; `test_olympus_requires_actionable_labels_and_risk` must name `Risk` the field, not only `Missing author-visible risk metadata` | #1000 |
| `plugins/mission-control/tests/test_issue_create_prepared.py` | `OLYMPUS_BODY` / `_ready_draft` need `### Risk` or passing drafts block | #1000 |
| `plugins/mission-control/tests/test_issue_prepare_compile_approve.py:128` | `fields["Technical Risk"]` must not remain a live project-field assert | #1000 |
| `plugins/mission-control/tests/test_issue_source_artifacts.py:24-36, 35, 51, 88, 108` | path-only `requirements-ready` / `resume-ready` asserts become T942-01/02/03 | #942 |
| `tests/test_mission_control.py` `TestWipLimitsConfigurable` | mocks `wip_limits`; production reader must disappear under T999-02. Update or delete the class so the repo gate does not keep a reader alive | #999 |

`docs/sdlc-issue-drafts/**` historical `"Technical Risk"` sidecar keys are
out of scope. Do not rewrite them for T1000-09.

## Verification

```bash
# Authoring check — rows exist and T-IDs are unique
rg -c '^### T(999|1000|942)-' docs/plans/2026-09-13-mission-control-alignment-test-scenarios.md

# After Dev lands production + required updates
uv run pytest plugins/mission-control/tests/test_schema_resync.py \
  plugins/mission-control/tests/test_issue_risk_field.py \
  plugins/mission-control/tests/test_repair_window_label.py \
  plugins/mission-control/tests/test_technical_risk_retirement.py \
  plugins/mission-control/tests/test_saga_readiness_alignment.py -q

uv run pytest plugins/mission-control/tests -q
```

Expected: focused files pass; plugin suite summary ends in `passed` with
`0 failed`.

## Out of scope

- Production implementation, schema authorship, or label-sync to GitHub
  (`infiquetra-sdlc` issue #149).
- Hermes / home-lab `card_validator.py` (#1000 non-goal).
- New readiness states, Risk tokens, or project fields.
- Live board or `gh` acceptance.
- Rewriting historical `docs/sdlc-issue-drafts/**` sidecars.
- Plugin version / marketplace / CHANGELOG release surfaces (Release
  worker). This plan only names test files and oracles.

## Scenario index

| ID | Child | File | Result |
| --- | --- | --- | --- |
| T999-01 | #999 | `test_schema_resync.py` | version `2026-09-07.5` |
| T999-02 | #999 | `test_schema_resync.py` | no live `wip_limits` / `component_slices` reads |
| T999-03 | #999 | plugin suite command | `0 failed` |
| T999-04 | #999 | existing oracles | pins retargeted |
| T1000-01 | #1000 | `test_issue_risk_field.py` | missing `### Risk` names Risk |
| T1000-02 | #1000 | `test_issue_risk_field.py` | create-prepared refused |
| T1000-03 | #1000 | `test_issue_risk_field.py` | four valid tokens pass |
| T1000-04 | #1000 | `test_issue_risk_field.py` | UNKNOWN: schema ok, readiness fail |
| T1000-05 | #1000 | `test_issue_risk_field.py` | bad format / no justification blocked |
| T1000-06 | #1000 | `test_repair_window_label.py` | set with F-CITE-FAIL |
| T1000-07 | #1000 | `test_repair_window_label.py` | clear with F-CITE-PASS |
| T1000-08 | #1000 | `test_repair_window_label.py` | no citation refused |
| T1000-09 | #1000 | `test_technical_risk_retirement.py` | queue retired/removed + E1 |
| T942-01 | #942 | `test_saga_readiness_alignment.py` | pending-confirmation stays pending-confirmation |
| T942-02 | #942 | `test_saga_readiness_alignment.py` | bare draft non-routable |
| T942-03 | #942 | `test_saga_readiness_alignment.py` | bare state non-routable |
| T942-04 | #942 | `test_saga_readiness_alignment.py` | six states; declaration wins |
| T942-05 | #942 | `test_saga_readiness_alignment.py` | named-root refuse |
| T942-06 | #942 | `test_saga_readiness_alignment.py` | explicit external identity |
| T942-07 | #942 | `test_saga_readiness_alignment.py` | missing Saga diagnostic |
| T942-08 | #942 | `test_saga_readiness_alignment.py` | incompatible Saga diagnostic |
| T942-09 | #942 | `test_saga_readiness_alignment.py` | unknown/malformed fail closed |
| T942-10 | #942 | `test_saga_readiness_alignment.py` | both entry points agree |
