---
title: Mission Control alignment with the current infiquetra-sdlc schema — Architect grounding (issues 1004, 999, 1000, 942)
type: architecture-grounding
status: active
date: 2026-09-13
assignment: MC-ALIGN-01-ARCH
base_commit: ea7963a4bbf735b7179bd2d2605af740a1f8c2e7
issues: [1004, 999, 1000, 942]
---

# Mission Control alignment — Architect grounding

This document grounds the three children of parent issue 1004 in the repository as it stands on
`origin/main` at commit `ea7963a4` (2026-09-13). It defines technical interfaces and compatibility
boundaries only. It proposes no code and reopens none of the readiness decisions Jeff recorded on
issue 942 on 2026-09-13; those decisions are restated below as constraints the interface must satisfy.

The three children are: issue 999 (re-vendor the SDLC schema copy), issue 1000 (the fourteenth
issue field `### Risk`, the `repair-window` label write, and the retirement of the queued Technical
Risk project-field item), and issue 942 (Mission Control's readiness inference and vocabulary must
be the Saga-owned ones). SDLC means the software development lifecycle repository
`infiquetra/infiquetra-sdlc`, whose `config/sdlc-schema.json` is the source of the semantics Mission
Control vendors.

## 0. Evidence base and how this was verified

Every claim below was read from a current source on 2026-09-13:

| Source | State verified |
|---|---|
| `infiquetra-claude-plugins` working tree | `HEAD` equals `origin/main` `ea7963a4` after `git fetch`; zero commits behind. Five untracked review documents under `docs/reviews/` are unrelated. |
| `infiquetra-sdlc` working tree | `HEAD` equals `origin/main` `67845cdd`; zero commits behind; `config/sdlc-schema.json` clean. The schema was read with `git show origin/main:config/sdlc-schema.json`. |
| GitHub issues 1004, 999, 1000, 942 | Bodies and all comments read through `gh issue view`. |
| Plugin versions | mission-control 2.15.2, saga 0.157.1, fleet-core 0.25.3, marketplace metadata 3.0.0 (from `plugin.json` files and `.claude-plugin/marketplace.json`). |

All `file:line` references are to `ea7963a4` unless stated otherwise.

## 1. Verdict summary

| Child | What the issue assumed | What the repository shows | Consequence for the plan |
|---|---|---|---|
| 999 | "Expected none" of the plugin code reads `wip_limits` or `component_slices`. | One real reader of `wip_limits` exists: `_wip_limits()` at `plugins/mission-control/scripts/sdlc_manager.py:463`, consumed by `board view` and `board wip`. No reader of `component_slices`. | The issue's own stop condition applies: report the path and behaviour, do not invent a replacement limit source. Section 2 records the finding and the ruling. |
| 999 | The re-sync is one file. | The vendored schema JSON and the two generated issue-contract artifacts are three outputs of one upstream generator run, but the plugin pins them independently. Re-syncing the JSON alone leaves the generated artifacts one field behind with nothing asserting the lag. | Section 2.4 defines the pinning rule and the explicit, dated lag guard so the lag is visible rather than silent. |
| 1000 | `### Risk` is new to the plugin. | The plugin already has two risk shapes: a common `--risk` metadata input that keys the risk-conditional requiredness matrix and a project-field mapping named `Technical Risk`, plus an Asgard-only `### Risk` body section with placeholder `TBD`. | Section 3 reconciles both into the single body-sourced field the schema defines. The Technical Risk item lives in this repository at `sdlc_manager.py:4343`, not only upstream. |
| 1000 | `repair-window` handling belongs on `flow set-field`. | `set-field` writes single-select project fields; the schema says the repair window is a label and "no fourth board field". | Section 3.6 specifies a dedicated label verb with a required citation, sourced from the vendored schema's marker block. |
| 942 | Saga-owned readiness can be called directly. | The Saga owner module is `plugins/saga/scripts/handoff_envelope.py`; cross-plugin path imports are rejected by the repository's standing decision, and the established mover is the fleet-core plugin-resolution ladder that Saga already uses in the opposite direction. The owner's generic fallback is `requirements-ready`, which Jeff's decision 2 rules insufficient for drafts and state files. | Section 4 defines the runtime resolution, the compatibility contract, an additive shared-owner API with a declaration-required class, and the fail-closed routing table. |

## 2. Issue 999 — re-syncing the vendored schema to 2026-09-07.5

### 2.1 What the diff is

The vendored copy at `plugins/mission-control/config/sdlc-schema.json` reads `"schema_version":
"2026-08-29"`. The source on `infiquetra-sdlc` `origin/main` reads `2026-09-07.5`. The structural diff
between the two, computed by loading both files:

| Change class | Vendored (2026-08-29) | Source (2026-09-07.5) |
|---|---|---|
| Top-level key removed | `wip_limits` | — |
| Top-level keys added | — | `status_definitions`, `retro_trigger`, `terminal_outcomes` |
| `work_hierarchy` keys | `component_slices`, `roles`, `source_note` | `components`, `parent_stage_derivation`, `roles`, `source_note` |
| `dispatch_gates` keys | `asgard`, `campps`, `operations` | adds `planning_to_active_readiness`, `rule` |
| `issue_fields.fields` | 13 entries, no `risk` | 14 entries; `risk` inserted after `verification`, before `lifecycle_origin` |
| `issue_fields.required_matrix.rules[0]` | 8 always-required fields | 9: adds `risk` to the always-required core |
| `issue_fields.regexes` | `header` only | `header` only (no first-line vocabulary regex; see 3.1) |
| `lifecycle_field_mutation` keys | 12 | adds `allowed_submissions`, `allowed_submissions_note`, `allowed_submissions_ready_to_close_note` |
| `pause_states` | prose without `Deferred` | prose adds `Deferred`, marks `Parked` retired |
| `migration_notes` | 14 entries | 26 entries |

`issue_fields.placeholder_lines` and `issue_fields.regexes` are unchanged. The `repair_window_encoding`
block now sits at
`work_hierarchy.parent_stage_derivation.parent_outcome_state.own_verification_failed.repair_window_encoding`
and is the source of truth issue 1000 needs (section 3.6).

### 2.2 The `wip_limits` dependency the issue expected not to exist

`_wip_limits(config, project_name, proj)` at `sdlc_manager.py:463` reads
`config["sdlc_schema"]["wip_limits"][<board_key>]`. Two commands consume it:

- `board view` (`board_view`, `sdlc_manager.py:1216`, call at `:1232`) uses the limits to decorate
  each column with `[WIP: n/limit]` and to decide whether to print an empty column.
- `board wip` (`board_wip`, `sdlc_manager.py:1439`, call at `:1445`) iterates the limits and reports
  violations per column.

When the schema block is absent the function falls through two levels: a `legacy_rollout_config`
branch that applies only to the retired `mount-olympus` project, then a hard-coded default of
`{"Ready": 10, "In Progress": 5}`. Both `Ready` and `In Progress` are column names from the
retired six-column vocabulary; no active board has them since the 2026-08-29 Stage migration.

Two facts make this a report-and-stop item rather than a rename:

1. **The live path already lost the block on 2026-09-07.** `_resolve_sdlc_schema()` at
   `sdlc_manager.py:341` resolves GitHub `main` first and uses the vendored copy only when the
   network read fails. So every online `board view` and `board wip` since bump A has been reading a
   schema with no `wip_limits` and silently applying the hard-coded default. The vendored copy only
   governs offline behaviour. Re-vendoring makes offline behaviour match what online behaviour already
   is; it does not change what the operator sees online.
2. **The vendored block was already declared dead.** Its own `source_note` (2026-08-29) reads "NOT a
   live limit source ... re-deriving limits for the Stage vocabulary is deliberately deferred and must
   not happen as a side effect." Issue 999's stop condition says the same: do not invent a replacement.

WIP means work in progress. The board skill documents a "WIP Limits Reference" section
(`plugins/mission-control/skills/board/SKILL.md:144-157`) and the README's config table describes the
schema as a "WIP" source (`plugins/mission-control/README.md:280`). Both are documentation of the
retired block.

**Ruling 999-1 (the WIP reader).** The re-sync retires `_wip_limits` as a schema reader rather than
leaving it to hit a hard-coded default keyed to retired column names. The interface after the change:

- `board wip` reports, in words, that no WIP limits are defined for Stage-vocabulary boards at the
  resolved schema version, and reports per-Status counts with no violations. It does not print
  `Ready` or `In Progress` rows.
- `board view` renders each column with its item count and no limit decoration.
- No new limit source is introduced anywhere. The `legacy_rollout_config.wip_limits` branch for
  `mount-olympus` is retired with the function; it is dead code (the config file it read was removed
  from `infiquetra-sdlc` on 2026-04-26 and the project is retired).
- The board skill's WIP Limits Reference section and the README row are rewritten to say limits are
  not schema-backed, so the documentation stops directing agents to a limit source that does not exist.

This satisfies issue 999's second acceptance criterion literally: after the change,
`grep -rn 'wip_limits\|component_slices' plugins/mission-control` matches nothing outside the CHANGELOG.

**Ruling 999-2 (`component_slices`).** No Mission Control module reads `component_slices` or
`components`. The grep across `plugins/mission-control`, `tests`, `scripts`, and `docs` matched only
the vendored JSON itself. Nothing to rename; the acceptance criterion is satisfied by the re-vendor.

**Ruling 999-3 (new keys).** `status_definitions`, `retro_trigger`, `terminal_outcomes`,
`planning_to_active_readiness`, and `allowed_submissions` gain no Mission Control reader in this
change. The repository's standing rule is that a schema slice needs a real consumer and a producer
before it is wired; the `terminal_outcomes` block itself says the Mission Control operation that would
honour it (an `issue close` with a disposition argument) "does not exist yet". That is a separate
item, not part of this run.

### 2.3 Tests that pin the vendored version

- `plugins/mission-control/tests/test_prompt_alignment.py:173` asserts
  `schema["schema_version"] == "2026-08-29"`. This is the pin issue 999 names; it moves to
  `2026-09-07.5`. The same test (lines 169-190) asserts `work_hierarchy.roles` shape and the Asgard
  field set; those assertions still hold against the source (verified by loading both files).
- `plugins/mission-control/tests/test_issue_contract_parity.py:122-131`
  (`test_vendored_schema_carries_issue_fields_block`) asserts properties of `issue_fields` that hold
  in both versions.
- `tests/test_mission_control.py::TestWipLimitsConfigurable` (two tests, lines 327-378) exercise only
  the retired `mount-olympus` legacy branch. Under ruling 999-1 they are replaced by one test that runs
  `board wip` against a schema without `wip_limits` and asserts the no-limits report and the absence of
  the hard-coded `10` and `5`.
- `plugins/mission-control/tests/test_project_mappings_resolution.py:140-200` covers the
  remote-first resolution order and is unaffected.

### 2.4 The generated artifacts travel with the schema, and the lag must be visible

The plugin vendors three outputs of one upstream generator run
(`infiquetra-sdlc/tools/docs/gen_issue_contract.py`, whose `--check` gate keeps the schema's
`issue_fields` block and the generated modules consistent upstream):

| Vendored artifact | Pinned by | Carries `risk` today |
|---|---|---|
| `config/sdlc-schema.json` | `test_prompt_alignment.py:173` (version string) | No (2026-08-29) |
| `config/generated/issue_contract_data.py` + `.sha256` | `test_issue_contract_parity.py:57` literal SHA-256 oracle and the manifest | No (11 mentions of `risk`, all matrix axes; upstream copy has 20) |
| `config/generated/issue_contract_shim.py` + `.sha256` | `test_issue_contract_parity.py:61` literal SHA-256 oracle and the manifest | No; upstream `REQUIRED_H3_HEADERS` now ends with `'Risk'` |

`check_issue_contract_parity.py` compares vendored bytes to their manifests. Nothing compares the
vendored schema's `issue_fields.fields` headers to the vendored `issue_contract_data.py`
`FIELD_HEADERS`. So a re-sync of the JSON alone would leave the plugin validating cards against a
13-field contract while its schema declares 14, with every test green.

Re-vendoring the two generated modules is not a mechanical step: the shim's `REQUIRED_H3_HEADERS`
gaining `'Risk'` makes `validate_card_body` (`sdlc_manager.py:3884`) demand a `### Risk` section on
every actionable body immediately, and `_contract_scaffold_body` (`:4868`) starts emitting it with the
placeholder `_No response_`. That is issue 1000's behaviour change, not issue 999's.

**Ruling 999-4 (pinning and lag).** Issue 999 re-vendors the schema JSON only and adds one
cross-artifact guard: a test that compares the vendored schema's `issue_fields.fields` header list to
the vendored `issue_contract_data.py` `FIELD_HEADERS`, with an explicit exclusion map recording
`Risk` as "vendored by issue 1000" and dated. Issue 1000 re-vendors the two generated modules from the
same upstream commit (`67845cdd` or later), updates both SHA-256 oracles, and deletes the exclusion.
The exclusion-map shape is the repository's existing precedent for a recorded, dated lag
(`tests/test_handoff_envelope_maturity.py:282` uses one for the vocabulary). If the Lead chooses to
ship 999 and 1000 as one change, the guard ships with an empty exclusion map and the lag never exists.

### 2.5 Re-vendor procedure (no script exists in this repository)

Issue 999 asks whether the vendored copy is generated by a script. It is not, on the plugin side:
the plugin has no re-sync script, and the CHANGELOG entry for 2.15.x describes the last refresh as a
hand copy of "the authoritative 2026-08-29 file from infiquetra-sdlc main". The procedure is: copy
`config/sdlc-schema.json` from `infiquetra-sdlc` at a named commit, record that commit in the
CHANGELOG entry, move the version pin, run the parity gate. The generated modules and their
`.sha256` manifests are copied from `infiquetra-sdlc/tools/docs/generated/` at the same commit.

## 3. Issue 1000 — the Risk field, the repair-window label, and the Technical Risk item

### 3.1 The contract as the schema states it

From the source schema at 2026-09-07.5, `issue_fields.fields[12]`:

> key `risk`, header `Risk`, required `true`. "Blast-radius assessment. First line is exactly one of
> low, medium, high, very-high; the next line is one sentence saying why. Written by the Architect as
> part of the technical context; UNKNOWN until then, and the card is not ready while it reads UNKNOWN.
> high and very-high require the Failure modes / pre-mortem, Inputs inventory, and Stop conditions
> fields."

Three facts about where the rule's pieces live matter for the interface:

1. **The schema carries no regex for the first-line vocabulary.** `issue_fields.regexes` holds only
   `header`. The tier vocabulary lives in `issue_fields.required_matrix.axes.risk`
   (`low`, `medium`, `high`, `very-high`, `*`). The token `UNKNOWN` appears in the field description
   and in the readiness rule (`dispatch_gates.planning_to_active_readiness.risk_scaling.effect`: "An
   absent risk value, or one still reading the literal UNKNOWN token, fails C4 and routes to the
   operator; the rule never defaults to a tier"). It is not a matrix axis value.
2. **Field-level validation is "non-empty after placeholder filtering"** (`card-schema.md:93`,
   `:302-306`). `UNKNOWN` is not in `placeholder_lines`, so the field check passes on it. This is by
   design: "UNKNOWN is the honest answer before the Architect has written the assessment, and it is
   accepted by the template — but a card whose Risk reads UNKNOWN is not ready."
3. **The value has one source, the card body.** `risk_scaling.source`: "The tier is read from the
   card body and nowhere else: the risk: labels ... stay a board projection written by the lifecycle
   integration, never a source, and no board field carries the value."

### 3.2 The two risk shapes Mission Control has today

| Shape | Where | Behaviour at `ea7963a4` |
|---|---|---|
| Common metadata `risk` | `issue prepare --risk` (`sdlc_manager.py:6780`); draft frontmatter `risk:` (`:4788`); sidecar `risk` (`:5374`); read back at `:5085` | Keys the risk-conditional requiredness matrix through `_required_contract_field_keys(issue_type, risk)` (`:3972`) and `validate_card_body_for_context` (`:3992`). Required for actionable types: "Missing author-visible risk metadata" (`:5321`). Mapped to a project field named `Technical Risk` by `_prepared_project_fields` (`:4343`, `:4410`). Not written into the body. |
| Asgard-only `### Risk` section | Asgard non-actionable body template at `:5017` with placeholder `TBD`; readiness at `:5328-5345` | Required non-`TBD` section, plus a second "Missing Asgard risk metadata" check on the metadata value. No vocabulary. Only reached for Asgard cards of non-actionable types, because actionable types take the contract scaffold first (`:5000`). |

The matrix already exists and already keys on `risk`; what E1 changes is the *source* of the value
and the *presence* of the field in the body.

### 3.3 Reconciliation into one common field

**Ruling 1000-1 (single reader, body is the source).** One reader owns the field for every team and
issue type. Its input is the card body; its output is one of: a tier in the matrix vocabulary; the
literal `UNKNOWN`; "absent" (no `### Risk` section); or "unrecognized" carrying the first line's text.
The reader takes the first non-placeholder line of the section and compares it exactly (the schema's
values are lowercase hyphenated; `UNKNOWN` is uppercase; nothing else matches). Everything that today
consumes `issue.risk` consumes the reader's output instead:

- the requiredness matrix (`_required_contract_field_keys`) receives the tier; `UNKNOWN`, absent, and
  unrecognized are passed as no tier, which applies the `*` rules only. That is correct because
  readiness blocks or warns on those states anyway (3.4).
- `_read_prepared_issue` derives `issue.risk` from the body, not from frontmatter or sidecar. The
  frontmatter `risk:` line and the sidecar `risk` key become projections of the body value, written
  by prepare, never read as a source. This keeps existing drafts parseable.

**Ruling 1000-2 (`--risk` becomes a seed, and conflicts refuse).** `issue prepare --risk <tier>`
continues to exist. Its value seeds the first line of the scaffolded `### Risk` section when the body
is compiled from the matrix. When the operator supplies both `--risk` and a source body that already
carries a `### Risk` first line, and the two differ, prepare records a blocking gap naming both values
rather than letting either win silently. When the source body carries the section, `--risk` is not
needed and, if equal, is a no-op.

**Ruling 1000-3 (scaffold placeholder is `UNKNOWN`).** `_contract_field_placeholder` (`:4854`) returns
`_No response_` for fields it does not special-case. For `risk` it must return `UNKNOWN` on its own
line, so a compiled draft passes the field check and lands in the state the schema calls "honest but
not ready". `_No response_` is in the placeholder set and would make every scaffolded draft fail the
field check, which is the wrong failure: the missing thing is the Architect's assessment, not the
section.

**Ruling 1000-4 (Asgard binds to the common grammar).** The Asgard non-actionable template keeps its
`### Risk` section but its placeholder becomes `UNKNOWN`, its first line follows the same vocabulary,
and its readiness check is the common reader's outcome, not the `TBD` test plus the metadata test.
`TBD` is retired so there is no third vocabulary. The rest of the Asgard body shape (Intent, Target
repo / surface, Mode, Constraints, Transfer notes) is out of scope; only the Risk section changes.

### 3.4 What UNKNOWN means at each gate — the one default the Lead may override

Mission Control has one gate: `_readiness_for_prepared_issue` (`:5229`), which decides whether a draft
may become a GitHub issue. The SDLC has a later gate: Planning-to-Active readiness, condition C4,
interpreted upstream (`tools/docs/planning_readiness.py`) and by the home-lab card validator, not by
this plugin.

Issue 1000's test line reads "a draft with each of the four values and UNKNOWN passes the field check
(readiness still fails on UNKNOWN)". Read against the schema, "readiness" is the Planning-to-Active
rule: the Architect writes Risk "as part of the technical context written during Shaping", which is
after the card exists, and `card-schema.md:304-306` says the card "stays in Planning until a real value
replaces it". A creation gate that refused `UNKNOWN` would require the Architect's assessment before
there is a card for the Architect to assess.

**Ruling 1000-5 (default, overridable).** At the creation gate:

| Reader outcome | Creation gate | Wording the draft records |
|---|---|---|
| tier in vocabulary | passes | none |
| `UNKNOWN` | **warning**, creation allowed | "Risk is UNKNOWN; the card is not Planning-ready until the Architect writes the tier" |
| absent section | blocking | the matrix's existing "Missing required H3 sections" message, which now names `Risk` |
| unrecognized first line | blocking | names the offending line and the four tiers plus `UNKNOWN` |

If Jeff wants creation itself to refuse `UNKNOWN`, the only change is the second row becoming
blocking; nothing else in this document moves. Issue 1000's first acceptance criterion (a body without
Risk "reports a blocking gap naming Risk") is satisfied by row three under either choice.

### 3.5 What "the plugin's five issue templates" resolves to

The plugin owns no template files. `plugins/mission-control/scripts/sync_template_docs.py` reads the
five forms from the `infiquetra-sdlc` checkout's `.github/ISSUE_TEMPLATE/` (resolved through
`INFIQUETRA_SDLC_PATH` or the default workspace path) and renders
`skills/issues/references/templates-reference.md`. Upstream, the actionable forms already carry Risk
(`capability.yml`, `defect.yml`, `enhancement.yml` at `67845cdd`). So the template surface for this
plugin is:

1. `templates-reference.md`, re-rendered by the existing script once the sdlc checkout is at or past
   the bump B commit. This is a generated surface; it is not hand-edited.
2. The scaffold bodies inside `sdlc_manager.py`: the matrix-driven contract scaffold (gains Risk
   automatically once the generated data is re-vendored, with the placeholder fixed by ruling 1000-3)
   and the two hand-typed bodies (Asgard non-actionable, ruling 1000-4; the generic non-actionable body
   at `:5023`, which carries no Risk today and is not an actionable contract body, so it gains none).
3. `plugins/mission-control/tests/test_template_sync.py:38-47`
   `EXPECTED_ACTIONABLE_REQUIRED_FIELDS`, which lists eight required fields and must gain `Risk`. The
   same file's `STALE_ACTIONABLE_TERMS` already forbids "Technical Risk" and "Risk Level" in the
   rendered reference; `Risk` alone is not a stale term.

Adjacent and outside the plugin's custody: this repository's own `.github/ISSUE_TEMPLATE/*.yml` forms
carry a generated region (`# BEGIN generated:issue-contract-fields`) that does not yet contain Risk.
That region is regenerated by the upstream generator against consumer repositories; it is a
repository-hygiene item, not a Mission Control change, and is named here so it is not mistaken for
one of the five templates.

### 3.6 The `repair-window` label — technical interface

The schema's `repair_window_encoding` block (source, 2026-09-07.5) defines the whole contract:

| Element | Value |
|---|---|
| `marker_kind` / `marker` / `marker_source` | `label` / `repair-window` / `config/labels.json` (present upstream: colour `E99695`, description "Parent's own verification failed; open until a later deployed version passes") |
| `writer` | "The Delivery Manager, through the lifecycle integration. No acting role writes it, and no consumer sets it as a side effect of reading." |
| `events.set` | "When the Delivery Manager records the parent's Status as Verification failed, citing the failing test result that caused it." |
| `events.clear` | "Only after a later deployed version passes every prescribed scenario, citing that passing result. Nothing else clears it." |
| `why_a_label` | "no fourth board field, no new Status, and no parsing of prose" |
| `interpreter` | "`tools/docs/parent_stage.py labels_signal_repair_window()` is the one runtime reading of the marker name; no consumer copies the literal." |

On the Mission Control side, the writer surfaces that exist today are: `issue_label_add`
(`sdlc_manager.py:3635`, idempotent REST add), `issue_label_remove` (`:3642`, idempotent, 404 is
success), `flow verify-label` (`:3769`, self-healing create), and the lifecycle correction seam
`flow set-field --correction` (`:2766`, restricted to `CORRECTION_FIELDS = {"Status", "Stage"}`,
`:2665`). Saga's `board_progression.py` is the lifecycle integration on the Saga side; it emits
`set-field-status` operations (`plugins/saga/scripts/board_progression.py:687-705`) and is the process
that records `Verification failed`.

**Ruling 1000-6 (a dedicated label verb, not `set-field`).** The write lands on a new `flow` verb whose
name says what it is (for example `flow repair-window`), because `set-field` is the single-select
project-field writer and the schema forbids a field for this. The verb's contract:

- Arguments: repository, issue number, one of open or close, and a required citation string. The
  citation is a non-empty reference to the test result on the record (an evidence path, a URL, or an
  issue-comment reference). Mission Control validates that it is present and non-empty; it does not
  fetch or interpret it. Verifying that the cited result says what the writer claims is the Delivery
  Manager's responsibility, consistent with the no-defensive-architecture rule for this repository's
  tools.
- Refusal: no citation, or a blank one, refuses before any network call, with a message that names the
  event and the schema clause requiring the citation.
- Marker name: read from the vendored schema at
  `work_hierarchy.parent_stage_derivation.parent_outcome_state.own_verification_failed.repair_window_encoding.marker`,
  never a literal in `sdlc_manager.py`. This is why issue 1000 depends on issue 999's re-vendor: at
  `2026-08-29` the path does not exist and the verb must refuse with a schema-too-old diagnostic.
- Label definition: before an open, the verb self-heals the label on the repository through the
  existing `verify-label` path using the definition from `config/labels.json` (resolved through
  `get_sdlc_path()`, the same source `labels deploy` uses), so an open never fails on a repository that
  has not had the label pushed. Pushing labels to every repository remains the operator-confirmed
  `label-sync.py` action tracked upstream (sdlc issue 149).
- Durability of the citation: the label carries no text, and "citing" means the citation is on the
  parent's record. The verb posts one issue comment carrying the event and the citation through the
  existing comment helper. When the open is a no-op because the label is already present, no comment
  is posted, so a retried open does not duplicate the record.
- Idempotency: open on a present label and close on an absent label are successes reported as no-ops,
  matching the existing helpers.
- Evidence output: the JSON result mirrors the `set-field` evidence shape (`action`, repository,
  number, the event, the citation verbatim, and whether the write was a no-op).

**Ruling 1000-7 (custody of the emission).** Issue 1000 delivers the Mission Control verb and its
tests. Wiring Saga's `board_progression.py` to emit the open when it records `Verification failed`
and the close after a passing deployed run is a Saga change under a separate issue; the Delivery
Manager is the writer and that integration lives in Saga. The two writes (Status, then label) are two
independent idempotent operations. No transaction or compensation machinery couples them; the
schema's atomicity clause governs project-field writes across boards, and a label is a single
repository-issue property.

### 3.7 Disposition of the stale Technical Risk item

Issue 1000's cleanup amendment found only the test guard. The item exists in three places:

| Location | What it is | Disposition |
|---|---|---|
| `sdlc_manager.py:4343` `_PREPARED_FIELD_RISK = "Technical Risk"` and `_prepared_project_fields` (`:4410`) | Records the metadata risk value into the draft sidecar's `project_fields` under a project field that was "decided, not yet created" (the PROJECT FIELD REALITY note at `:4304`). The sidecar key is documented as recorded-but-never-consumed (`:4400-4407`). | Retire the key: prepare stops recording it. E1 says no board field carries the value. Existing sidecars keep their historical key; nothing reads it, so no migration. |
| `sdlc_manager.py:6562` interactive `issue create` capability-adaptive prompt list (`Capability Size`, `Business Value`, `Technical Risk`, `Target Quarter`) and the reality note at `:6447` | Prompts only if the live project exposes the field; it never has. | Remove `Technical Risk` from the list and rewrite the note to point at decision E1. |
| `infiquetra-sdlc/docs/engineering-journal/QUEUED.md` "Wire live consumption of prepared `project_fields` at `create`" | The upstream queued item; names Technical Risk among the fields a create-time consumer would set. | Upstream custody. Issue 1000 leaves a comment on itself naming that entry and stating that the Technical Risk half is retired by E1 while Issue Type, Lifecycle Origin, and Objective stand. The plugin's `DECISIONS.md` records the retirement. |

`docs/sdlc-issue-drafts/` holds 215 draft files; the sidecars written since 2026-06 carry
`"Technical Risk"` under `project_fields`. They are historical records and stay as they are.

### 3.8 Test surfaces issue 1000 touches

- `plugins/mission-control/tests/test_issue_prepare.py` (15 tests): every fixture body lacks
  `### Risk`; after the generated data is re-vendored they need the section. The test named
  `test_prepare_high_risk_fallback_includes_risk_conditional_sections` becomes the body-sourced case.
- `plugins/mission-control/tests/test_issue_create_prepared.py` (29) and
  `test_issue_prepare_compile_approve.py` (7): draft fixtures gain the section; new cases cover the
  four tiers, `UNKNOWN`, absent, unrecognized, and the `--risk` conflict refusal.
- `plugins/mission-control/tests/test_card_validator.py` (24) and `test_card_validator_agreement.py`
  (27): the shim's required headers gain `Risk`; the agreement test pins the shim against the
  home-lab validator's surface and needs the matching upstream bump.
- `plugins/mission-control/tests/test_issue_contract_parity.py`: both SHA-256 oracles and
  `EXPECTED_REQUIRED_FIELDS` / `EXPECTED_SHIM_REQUIRED_H3`.
- `plugins/mission-control/tests/test_template_sync.py`: `EXPECTED_ACTIONABLE_REQUIRED_FIELDS`.
- `plugins/mission-control/tests/test_flow_subcommands.py` (35): the new verb's open, close,
  refusal-without-citation, no-op, and schema-too-old cases, run against mocked REST calls the way the
  existing label tests in `tests/test_mission_control.py:511-568` do.

## 4. Issue 942 — Saga-owned readiness in Mission Control

### 4.1 The two implementations as they stand

**Saga owner: `plugins/saga/scripts/handoff_envelope.py` (645 lines).**

| Symbol | Line | Contract |
|---|---|---|
| `HANDOFF_MATURITIES` | 53 | six values: `idea-ready`, `requirements-ready`, `plan-ready`, `resume-ready`, `deferred-context`, `pending-confirmation` |
| `ROUTABLE_MATURITIES` | 65 | the six minus `pending-confirmation` |
| `SOURCE_DIRS` / `MARKER_DIRS` | 44, 70 | `docs/plans`, `docs/brainstorms`, `docs/specs`, `docs/ideation`, `docs/reviews`, `docs/work-sessions` |
| `ResolvedSource` | 77 | `path_to_read`, `published`, `reanchored`, `refused` — "one source decision shared by inference and envelope publication" |
| `resolve_source(source, root)` | 302 | Containment: inside root, read; outside root with a marker-directory twin inside root, read the twin and publish the twin's path; otherwise refuse. |
| `_read_frontmatter_maturity(path)` | 232 | Strict YAML frontmatter read of the top-level `maturity:` key; returns a vocabulary value, `""`, or an `unknown:` sentinel (`unreadable`, `unterminated:`, `carrier:`, `unrecognized:`). |
| `_path_maturity(published)` | 324 | Folder fallback; default `requirements-ready`; `branch:` prefix gives `resume-ready`. |
| `infer_maturity(source, root)` | 349 | `_resolved_maturity(resolve_source(...))`: refused gives `unknown:out-of-root:`, declared wins, re-anchored twin without a declaration is refused, else path fallback. |
| `_maturity_diagnostic(...)` | 474 | Prose per non-routable state; `None` for routable ones. |
| `_suggested_command(...)` | 522 | `/issue --prepare --from <published> --maturity <m>` for routable, the diagnostic otherwise. |
| `build_handoff_envelope(...)` | 542 | JSON, `schema_version` `1.1`, `lifecycle_owner: saga`, `issue_artifact_owner: mission-control`. |
| `read_state` / `_state_source` | 369, 380 | `.claude/saga/state.json` is read only to *select* a source (`current_work.plan_path` or `work_session_path`); it is never a maturity carrier. |

The vocabulary is mirrored by `plugins/saga/scripts/parse_issue.py:25` `HANDOFF_MATURITY_VALUES`, and
the two are held equal by `tests/test_handoff_envelope_maturity.py:282`
`test_maturity_vocabularies_in_sync`, which also checks Mission Control's tuple against an explicit
exclusion map whose only entry is `pending-confirmation`.

**Mission Control's parallel implementation, `sdlc_manager.py`.**

| Symbol | Line | Behaviour at `ea7963a4` |
|---|---|---|
| `_HANDOFF_MATURITY_CHOICES` | 4262 | five values, no `pending-confirmation`; gates argparse (`:6789`), `issue_prepare` (`:5423`), and readiness (`:5289`) |
| `_SOURCE_SEARCH_DIRS`, `_SOURCE_HINT_DIRS` | 4268, 4278 | Saga's six directories plus `.claude/saga` and `docs/sdlc-issue-drafts` |
| `_infer_maturity_from_path` | 4475 | path only; `docs/sdlc-issue-drafts/` and `.claude/saga/` give `resume-ready`; default `requirements-ready` |
| `_source_from_local_path` | 4509 | reads the file, discards content for maturity; no containment (`resolve_source_artifact` at `:4666` accepts any existing path, absolute paths included) |
| `_source_from_github_url` | 4531 | issue gives `requirements-ready`, pull request gives `resume-ready` |
| `_source_from_branch_ref` | 4574 | `resume-ready` |
| `issue_prepare` | 5419 | `maturity = --maturity or inferred or "requirements-ready"`; raises on a value outside the five |
| `_render_handoff_context` | 4813 | `maturity or "requirements-ready"`; `### Suggested next action` from `_suggested_next_action` (`:4803`), a bare dict subscript that raises `KeyError` outside the five |
| `_read_prepared_issue` | 5090 | `handoff_maturity` from draft frontmatter or sidecar |
| `_readiness_for_prepared_issue` | 5289 | outside the five: blocking; absent: warning |
| `_prepared_project_fields` | 4414 | records `handoff_maturity` verbatim as the `Lifecycle Origin` project-field value |

The reproductions on issue 942 and its folded duplicate 950 follow from that table and were not
re-run here; the lines they cite are unchanged at `ea7963a4`.

### 4.2 Jeff's decisions of 2026-09-13, restated as constraints

1. Mission Control calls Saga readiness inference and uses its vocabulary. No independent parser, no
   silent legacy fallback. `pending-confirmation` and invalid or unknown states never offer an
   actionable planning or execution route. Unknown values produce diagnostics, not crashes.
2. Saved issue drafts (`docs/sdlc-issue-drafts/`) and Saga state files require an explicit readiness
   declaration. Location alone and generic defaults are both insufficient. Absence means readiness is
   not established. The rule lives in the shared owner so both entry points agree; "a direct call to
   today's Saga function alone is insufficient because its generic fallback is requirements-ready."
3. Saga's named-repository source boundary is kept. External documents require an explicit source
   choice. Source identity is preserved between the document read and the published handoff. Selecting
   a contained counterpart is not authorization to read the outside original.
4. Missing or incompatible Saga is reported as a dependency problem and readiness-based routing stops.
   The old Mission Control logic is not used. Unrelated Mission Control operations keep working.

### 4.3 How Mission Control reaches Saga at run time

The repository's standing decisions constrain the mechanism, and they are compatible with decision 1:

- `{#fleet-commons-mechanism-463}` (DECISIONS.md line 7381): there is "no resolvable cross-plugin
  import path at install time — imports only work inside the monorepo". The decision recorded at line
  5436 rejected "canonical-in-saga with cross-plugin path imports — no precedent, couples
  mission-control tests to saga internals" for the intent envelope.
- `{#board-sync-plugin-resolution-620}` (line 4056): the generic resolver
  `fleet_commons.plugin_resolution.resolve_plugin_root(name, markers=..., env_var=...)` is the one
  substrate for finding a sibling plugin. Saga already uses it to find Mission Control
  (`plugins/saga/scripts/board_progression.py:60-89`, markers `scripts/sdlc_manager.py` and
  `config/sdlc-schema.json`, env override `MISSION_CONTROL_ROOT`). Its "revisit when" clause names
  "a third consumer needs `resolve_plugin_root`".

Mission Control already vendors `scripts/fleet_commons_shim.py` and loads fleet-core lazily
(`_load_intent_envelope`, `sdlc_manager.py:5129`). So the mirror image of the Saga-to-Mission-Control
edge is the established path, and no new import mechanism is needed.

**Ruling 942-1 (resolution).** Mission Control resolves the Saga root through
`fleet_commons_shim.load("plugin_resolution").resolve_plugin_root("saga", markers=("scripts/handoff_envelope.py",), env_var="SAGA_ROOT")`
and loads `handoff_envelope.py` by path from that root, the same way the shim loads a fleet-core
module. Resolution and load happen lazily, only on the readiness-bearing paths (4.4); `board`, `flow`,
`labels`, `metrics`, `issue create`, `issue close`, and a text-only `issue prepare` with neither a
source nor `--maturity` never touch Saga. The debug switch `FLEET_COMMONS_DEBUG=1` prints rung
provenance, as it does for every other resolution.

**Ruling 942-2 (compatibility contract).** The shared owner exports a readiness contract version
constant (a string, starting at `"1"`). Mission Control pins the version it requires. "Incompatible"
means: the module loads but has no such constant (a Saga from before this change), or the constant's
major differs. Within a major, changes to the shared owner are additive only, the same rule fleet-core
follows. Any change to the sentinel shapes, the vocabulary, or the meaning of a returned field bumps
the major. The envelope's own `schema_version` `1.1` is a separate contract for `/handoff` consumers
and does not move under this work.

**Ruling 942-3 (the dependency diagnostic, decision 4).** Both failure modes surface as one error
class at the call site, as `board_progression.py:65-84` does for the opposite edge: the ladder
exhausting its rungs, a fleet-core too old to carry `plugin_resolution`, a Saga root without the owner
module, and a version mismatch. The message names what was tried, the version required and found, and
the fix ("install or update the saga plugin from the infiquetra-plugins marketplace, or set `SAGA_ROOT`
to a checkout's `plugins/saga` directory"). `issue prepare` and `create-prepared` stop at that point
with no draft written and no readiness recorded. PyYAML is a run-time need of the owner module; a
missing PyYAML on a readiness path is reported through the same class, and
`test_sdlc_manager_optional_deps.py`'s rule that `sdlc_manager.py` has no module-scope `yaml` import
still holds because the load is lazy.

### 4.4 The shared-owner API (Saga custody, additive)

Decision 2 makes a direct call to `infer_maturity` insufficient. The owner must grow, additively, a
readiness assessment that covers two more source classes and returns everything a consumer needs to
route or refuse without re-deriving anything. The shape:

| Returned field | Meaning |
|---|---|
| `maturity` | one of the six vocabulary values, `""` (declared but blank), or an `unknown:<cause>[:<detail>]` sentinel, bounded as today |
| `routable` | true only for `ROUTABLE_MATURITIES` |
| `published_source` | the identity to publish (the twin's path when re-anchored, the caller's spelling otherwise) |
| `path_read` | the file actually read, or none |
| `reanchored`, `refused` | as `ResolvedSource` today |
| `declaration_required` | true for the draft and state-file classes |
| `diagnostic` | the prose `_maturity_diagnostic` produces, or none for routable states |
| `next_action` | the runnable suggested command for routable states; the diagnostic for the rest |
| `contract_version` | the constant from ruling 942-2 |

Two entry points produce it:

- **`assess_source(source, root)`** for documents: `resolve_source` then the declaration read, exactly
  today's `infer_maturity` path, plus the class rule below.
- **`assess_declared(value, published_source, *, declaration_required)`** for a declaration the caller
  already holds: `--maturity` on the Mission Control side, and any caller that has read a carrier the
  owner does not parse.

**Ruling 942-4 (declaration-required classes and their carriers).** The owner recognises two classes
by location, using constants it already owns (`STATE_DIR` at line 43; a new constant for
`docs/sdlc-issue-drafts`):

| Class | Carrier of the explicit declaration | Absent |
|---|---|---|
| Saved issue draft (`docs/sdlc-issue-drafts/*.md`) | the draft's sidecar `<draft>.json`, key `handoff_maturity`, read as strict JSON | `unknown:undeclared:<published>` |
| Saga state file (`.claude/saga/state.json`, and any JSON under `.claude/saga/`) | top-level key `handoff_maturity` in that JSON file | `unknown:undeclared:<published>` |

The draft's Markdown frontmatter is not the carrier because it is not YAML-safe: it is written and read
by a naive `key: value` split (`_render_draft_markdown`, `sdlc_manager.py:4769`; `_parse_draft_frontmatter`,
`:4718`), and a title containing a colon breaks a strict YAML read. The sidecar is written from the same
value by the same prepare step, is strict JSON, and is already the source Mission Control's reader
falls back to (`:5074`). Mission Control's existing frontmatter-versus-sidecar conflict check
(`:5100-5110`) extends to `handoff_maturity` so the mirror cannot disagree silently.

No Saga writer records `handoff_maturity` in `state.json` today, and `_state_source` reads the state
file only to select a document. Under this ruling, every current state file given as a source is
non-routable until a Saga writer declares readiness in it. That is the fail-closed default decision 2
asks for; which Saga command writes the declaration, and when, is a Saga design question outside this
grounding and is listed in section 6.

`unknown:undeclared` is a new discriminator under the existing `unknown:` prefix. The sentinel
decision's own revisit clause (`{#913-maturity-unknown-sentinel}`, DECISIONS.md line 263) anticipated
both triggers now present: "a second sentinel consumer appears (then extract the prefix into a shared
constant), or mission-control adds `pending-confirmation` to its prepare vocabulary". The prefix
becomes an exported constant of the owner, and the DECISIONS entry for this work amends that clause.

### 4.5 Mission Control consumption map

| Today (`sdlc_manager.py`) | Under the contract |
|---|---|
| `_HANDOFF_MATURITY_CHOICES` (`:4262`) | Deleted. The vocabulary has one source, the owner. `--maturity` is a free string at parse time and is classified after parsing through `assess_declared`, so a missing Saga yields the dependency diagnostic instead of an argparse error, and `pending-confirmation` is accepted (issue 942's third acceptance criterion). |
| `_infer_maturity_from_path` (`:4475`) | Deleted. `_infer_kind_from_path` (`:4490`) stays; it names the source *kind* for `### Source context` and is not a readiness rule. |
| `_source_from_local_path` (`:4509`) | Calls `assess_source` with the named repository root; publishes `published_source`; carries `maturity`, `routable`, `diagnostic`, `next_action`, `reanchored`, `refused` on `SourceArtifact` in place of `inferred_maturity`. |
| `_source_from_github_url` (`:4531`), `_source_from_branch_ref` (`:4574`) | These are the explicit external and branch source choices. Their maturity values pass through `assess_declared` so the vocabulary and routing text come from the owner; the values themselves (`requirements-ready` for an issue, `resume-ready` for a pull request or a branch) are unchanged. |
| `resolve_source_artifact` (`:4660`) | Local paths go through the owner's `resolve_source` before any read; a refused source is never opened (today it is read whenever it exists). |
| `issue_prepare` maturity resolution (`:5419-5425`) | `--maturity` and the source assessment are reconciled by ruling 942-5. |
| `_suggested_next_action` (`:4803`) | Replaced by the owner's `next_action`. No dict subscript, no `KeyError`. |
| `_render_handoff_context` (`:4813`) | `### Handoff maturity` carries `maturity` verbatim (bounded sentinels included); `### Suggested next action` carries `next_action`. The `or "requirements-ready"` default is deleted. |
| `_readiness_for_prepared_issue` (`:5289`) | Classifies through `assess_declared` and applies the creation-gate table in 4.6. |
| `_prepared_project_fields` Lifecycle Origin (`:4414`) | Records the value only when it is a vocabulary member. Sentinels and the empty string are not recorded on a project field. |

### 4.6 Routing and the creation gate

**Ruling 942-5 (`--maturity` versus the source).** `--maturity` is an explicit declaration by the
operator, or by Saga's own `suggested_command`, which passes the assessed value through. Reconciliation:

- Source carries a declaration (any vocabulary value, `""`, or a sentinel) and `--maturity` differs:
  blocking gap naming both. Readiness never substitutes for operator authorization, and an override
  must not promote an artifact whose own declaration says otherwise.
- Source carries no declaration (path fallback applied) and `--maturity` is given: the declared value
  wins, classified through the owner.
- Equal: no-op.

**Ruling 942-6 (creation gate by state).** For a draft with source assessment or declared maturity:

| Maturity | Draft written | `create-prepared` | `### Suggested next action` |
|---|---|---|---|
| `idea-ready`, `requirements-ready` | yes | allowed | the owner's `/plan` route (unchanged text) |
| `plan-ready`, `resume-ready` | yes | allowed | the owner's `/work` route (unchanged text) |
| `deferred-context` | yes | allowed | "clarify current intent" (unchanged) |
| `pending-confirmation` | yes | allowed, non-routable | the owner's diagnostic: boundary recorded but unconfirmed, no durable route until Phase 2.5 confirms |
| `""` (declared blank) | no | blocking | the owner's diagnostic |
| `unknown:*` (any cause, including `undeclared` and `out-of-root`) | no | blocking | the owner's diagnostic |
| absent (no source, no `--maturity`, text-only prepare) | yes | warning "Missing handoff maturity metadata" (unchanged) | none rendered |

`pending-confirmation` is creatable because issue 942's first acceptance criterion says the
checkpoint "reaches a card as `pending-confirmation`"; it is a real vocabulary state that records an
unconfirmed boundary. Blank and sentinel states are not creatable: the diagnostic tells the operator to
fix the declaring artifact, and a GitHub issue whose maturity is `unknown:carrier:` would publish an
authoring defect as a card.

### 4.7 Containment and source identity (decision 3)

- The named repository root is the directory `issue prepare` runs in, as today (`root or Path.cwd()`).
  Tests pass an explicit root, as they do now.
- A local path outside the root is never read. With a marker-directory twin inside the root, the twin
  is read and the twin's path is what is published; without one, the source is refused as
  `unknown:out-of-root:` and creation blocks. `.claude/saga/` and `docs/sdlc-issue-drafts/` are not
  marker directories for re-anchoring; an outside draft or state file is refused, never twinned.
- The explicit external choices are the ones that already exist: a GitHub issue or pull-request URL,
  and a branch reference. No new flag for reading arbitrary external files is added; adding one would
  be the "arbitrary external path" decision 3 forbids.
- Source identity: `SourceArtifact.ref` and `.path`, the `### Source context` lines, the
  `context_library_links` line built by `_context_links_from_source` (`:4844`), and the sidecar
  `source_artifact` all carry `published_source`. The sidecar additionally records the operator's
  requested spelling and the `reanchored` flag so a later reader can see that a twin was chosen. When
  re-anchored, `### Source context` names the re-anchoring in the same words Saga's diagnostic uses
  (`_diagnostic_source`, `handoff_envelope.py:456`).

### 4.8 Flow under the contract

```mermaid
sequenceDiagram
    participant Op as Operator or Saga /handoff
    participant MC as Mission Control issue prepare
    participant FC as fleet-core plugin_resolution
    participant SO as Saga handoff_envelope (shared owner)
    Op->>MC: issue prepare --from <source> [--maturity m]
    MC->>FC: resolve_plugin_root("saga", markers, env SAGA_ROOT)
    alt no root, no owner module, or contract major mismatch
        FC-->>MC: RuntimeError
        MC-->>Op: dependency diagnostic; no draft, no route
    else resolved
        MC->>SO: assess_source(source, root)  /  assess_declared(m, ...)
        SO-->>MC: maturity, routable, published_source, diagnostic, next_action
        MC->>MC: reconcile --maturity vs source (ruling 942-5)
        MC->>MC: creation gate table (ruling 942-6)
        MC-->>Op: draft + sidecar, or blocking gaps with the owner's diagnostic
    end
```

### 4.9 Parity acceptance cases and where the shared fixtures live

Issue 942's acceptance additions ask for shared example cases exercised by both entry points on real
source documents. The Saga side already has 77 tests in `tests/test_handoff_envelope_maturity.py`
covering the six states, declared-over-folder, absent, invalid, duplicate, malformed, unterminated,
carrier, unreadable, and out-of-root cases. The interface for parity:

- A fixture directory at the repository root (both suites are collected from the root:
  `pyproject.toml` `testpaths = ["tests", "plugins/*/tests"]`), holding one real document per case,
  plus one draft-with-sidecar pair per declaration case and one `state.json` per state case. Each
  fixture states its expected assessment in a small manifest so both suites read one expectation.
- The Saga suite asserts the owner's assessment per fixture.
- A Mission Control test runs the real command `issue prepare --from <fixture>` in a subprocess with a
  scrubbed environment and a temporary root that contains the fixtures, then asserts the draft's
  `### Handoff maturity`, that `### Suggested next action` never contains `/plan` or `/work` for a
  non-routable state, the sidecar's `handoff_maturity`, and the creation-gate outcome. This is the
  "real source documents through issue preparation, not merely constant fixtures" criterion, and it
  follows the repository's rule that a harness substitute hides the defect.
- An install-time test in the shape of `tests/test_fleet_commons_install_time.py`: a fake
  `~/.claude/plugins` layout with saga and fleet-core installed, cwd outside the repository, a scrubbed
  `PYTHONPATH`, asserting rung-3 provenance for the Saga resolution; and the same layout with saga
  removed or old, asserting the dependency diagnostic and that `board view` still runs.
- `test_maturity_vocabularies_in_sync` (`tests/test_handoff_envelope_maturity.py:282`) drops its
  `pending-confirmation` exclusion and stops loading `_HANDOFF_MATURITY_CHOICES`; it asserts instead
  that `sdlc_manager.py` carries no literal maturity vocabulary, so a second vocabulary cannot return.

### 4.10 Adjacent findings outside issue 942's custody

- `plugins/saga/scripts/parse_issue.py:69-90` `extract_handoff` returns `can_plan`, `can_work`, and
  `requires_clarification` all false for `pending-confirmation`. Once Mission Control publishes cards
  with that maturity, `/loop`'s branching on those three flags needs a defined outcome. This is a Saga
  reader question and belongs on a Saga issue.
- Saga state files carry no readiness declaration today (4.4). The writer side is Saga's.

## 5. Serialized shared surface — custody on `sdlc_manager.py` under one Dev

### 5.1 Touch map

| Region of `sdlc_manager.py` (line at `ea7963a4`) | 999 | 1000 | 942 |
|---|---|---|---|
| `_resolve_sdlc_schema`, `_wip_limits`, `board_view`, `board_wip` (341, 463, 1216, 1439) | retire WIP reader | | |
| generated-data load (3812-3860), `_required_contract_field_keys`, `validate_card_body_for_context` (3972-4030) | | re-vendored data; body-sourced tier | |
| `_HANDOFF_MATURITY_CHOICES`, `_SOURCE_SEARCH_DIRS`, `_SOURCE_HINT_DIRS` (4262-4288) | | | delete choices; dirs stay |
| `_PREPARED_FIELD_RISK`, `_prepared_project_fields` (4343, 4393-4420) | | retire Technical Risk | Lifecycle Origin vocabulary-only rule |
| `_infer_maturity_from_path`, `_source_from_*`, `resolve_source_artifact` (4475-4717) | | | owner-backed |
| `_render_draft_markdown` (4769) | | `risk:` line becomes a projection | `handoff_maturity:` mirror check |
| `_suggested_next_action`, `_render_handoff_context` (4803-4841) | | | owner's `next_action` |
| `_contract_field_placeholder`, `_contract_scaffold_body` (4854-4879) | | `UNKNOWN` placeholder | |
| Asgard body template (5017) | | `UNKNOWN`, common grammar | |
| `_read_prepared_issue` (5059-5124) | | `risk` from body | `handoff_maturity` conflict check |
| `_readiness_for_prepared_issue` (5229-5350) | | Risk rows (3.4) in the actionable branch and the Asgard branch | maturity rows (4.6) in the existing maturity block (5289) |
| `issue_prepare` (5386-5445) | | `--risk` seed and conflict | `--maturity` reconciliation; owner load |
| label helpers and `flow` parser (3635-3665, 7036-7123) | | new `repair-window` verb | |
| interactive `issue create` (6440-6572) | | drop Technical Risk prompt | |
| argparse `issue prepare` (6780-6795) | | | `--maturity` free string |

The two children share three functions: `_readiness_for_prepared_issue`, `_read_prepared_issue`, and
`issue_prepare`. In each, the Risk logic and the maturity logic are separate blocks already (the
maturity block at `:5289` sits apart from the actionable-type block at `:5310`), and the rulings above
keep them separate.

### 5.2 Ordering, branch shape, and release surfaces

- Order: 999, then 1000, then 942, as parent 1004's inventory lists them. 999 is mechanical and
  unblocks 1000's schema reads (the `repair_window_encoding` marker path and the fourteen-field
  `issue_fields`). 942 touches the prepare spine last so its owner-backed reader lands on a body
  contract that is already fourteen fields. One Dev, one branch per child or one branch with three
  commits; each child is a separately reviewable diff either way.
- Release surfaces per child, in the same change: `plugins/mission-control/.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json` (the mission-control entry must match), `plugins/mission-control/CHANGELOG.md`,
  and any drift-guard test that pins a version. Mission Control moves from 2.15.2 by one minor per
  child (2.16.0, 2.17.0, 2.18.0) or one minor for a combined change. Issue 942 also changes Saga
  (the shared-owner API, the contract constant, the `undeclared` sentinel, the drafts and state-file
  classes) and so bumps saga from 0.157.1 to 0.158.0 with its own CHANGELOG entry and the marketplace
  entry; those Saga edits are additive and leave `build_handoff_envelope`'s output for existing
  sources byte-identical.
- Engineering journal, same commit: a `DECISIONS.md` entry for the WIP reader retirement (999), one
  for the body-sourced Risk field and the Technical Risk retirement (1000), and one for the
  Mission-Control-to-Saga readiness edge that amends the sentinel decision's revisit clause (942).
- Gate: the full `scripts/gate.sh` run, backgrounded per `CLAUDE.md`, before each push; scoped test
  runs are not a green gate. Commit before any adversarial verification workflow runs.

## 6. Defaults the Lead may confirm, and what is out of scope

Non-blocking defaults stated above, each with the alternative named:

1. Ruling 1000-5: `UNKNOWN` at the creation gate is a warning, not a block. Alternative: block.
2. Ruling 1000-6: a dedicated `flow` verb for the repair window rather than a mode on `set-field`.
   Alternative: a `--label` mode on `set-field`, which this grounding argues against because the schema
   says the window is not a field.
3. Ruling 942-4: the draft's sidecar JSON is the declaration carrier for saved drafts. Alternative: the
   draft's Markdown frontmatter line, which would require the owner to adopt Mission Control's naive
   frontmatter parser.
4. Ruling 999-1: retire `_wip_limits` and the `mount-olympus` legacy branch together, so the grep
   criterion holds literally. Alternative: retire only the schema read and leave the legacy branch,
   which leaves `wip_limits` in the file and fails the criterion as written.

Out of scope for this run, named so they are not picked up by accident: a Mission Control reader for
`status_definitions`, `retro_trigger`, `terminal_outcomes`, or `allowed_submissions`; the Saga-side
emission of the repair-window open and close from `board_progression.py`; the Saga writer that
declares readiness in `state.json`; `parse_issue.py`'s flags for `pending-confirmation`; this
repository's own `.github/ISSUE_TEMPLATE` generated region; the upstream `label-sync.py` push of
`repair-window` to live repositories (sdlc issue 149); and the home-lab card validator (home-lab
issue 364).
