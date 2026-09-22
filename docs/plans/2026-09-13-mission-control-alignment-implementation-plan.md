---
title: Mission Control alignment — implementation plan for issues 999, 1000, and 942
type: fix
status: active
date: 2026-09-13
origin: docs/plans/2026-09-13-mission-control-alignment-architect-grounding.md
backend: team-execution
candidate: ea7963a4bbf735b7179bd2d2605af740a1f8c2e7
source_schema_commit: 67845cdd19948c9c10608436174d11a9b80d43ca
source_schema_version: 2026-09-07.5
---

# Mission Control alignment — implementation plan for issues 999, 1000, and 942

## Summary

This plan aligns the Mission Control plugin with the pinned software development lifecycle (SDLC)
schema and the Saga plugin's readiness rules. It covers the three open children of grouping issue
[#1004](https://github.com/infiquetra/infiquetra-claude-plugins/issues/1004): schema re-sync
[#999](https://github.com/infiquetra/infiquetra-claude-plugins/issues/999), common Risk field and
repair-window label [#1000](https://github.com/infiquetra/infiquetra-claude-plugins/issues/1000),
and Saga-owned readiness [#942](https://github.com/infiquetra/infiquetra-claude-plugins/issues/942).
This is a planning artifact, not implementation approval or a review verdict.

## Problem Frame and evidence

At candidate commit `ea7963a4bbf735b7179bd2d2605af740a1f8c2e7`, Mission Control vendors
`schema_version` `2026-08-29`; the SDLC source at commit
`67845cdd19948c9c10608436174d11a9b80d43ca` is `2026-09-07.5`. The local source file matches
that commit byte-for-byte (SHA-256
`5a8c0c93e022b8f48f0e10745f0a7871e636a07458892985501cfb6216de65b7`). The Architect
found a live `wip_limits` reader despite issue #999's expectation that none existed. Adding `Risk`
takes `issue_fields` from thirteen keys to fourteen; the schema places it after `Verification` and
before `Lifecycle Origin`. Mission Control still uses risk metadata and a queued `Technical Risk`
project field. It also infers handoff maturity from a path, whereas Saga parses document content and
recognizes `pending-confirmation`.

The source-grounded interface, code locations, and operator decisions are in
[Architect grounding](2026-09-13-mission-control-alignment-architect-grounding.md), sections 2–5.
The 23 independent scenarios are in
[Test Author scenarios](2026-09-13-mission-control-alignment-test-scenarios.md). The
[workspace plan](../../../infiquetra-agent-operations/docs/operations/2026-09-13-mission-control-alignment-workspace-planning.md)
controls role and authority boundaries; its relative link is informational because that file lives
in a sibling repository. GitHub issue comments and the pinned source schema govern where old issue
body wording conflicts with Jeff's 2026-09-13 decisions.

## Requirements

- R1. Re-vendor only the SDLC schema JSON from the pinned source revision for #999, and pin the
  `2026-09-07.5` version. Report and retire the live reader of removed `wip_limits`, with truthful
  count-only board output; do not invent new limits. No production reader of `component_slices`
  remains.
- R2. Make the temporary one-field lag between the new schema and old generated issue-contract
  modules explicit and dated. #1000 then copies both generated modules and their manifests from the
  same source revision, updates hash oracles, and removes the lag allowance.
- R3. Compile one common `### Risk` body field from vendored `issue_fields` for actionable cards and
  reconcile the Asgard body. Accept only `low`, `medium`, `high`, `very-high`, or `UNKNOWN` as the first
  line, followed by one sentence of justification; preserve the high-tier conditional trio. The body
  is the source; metadata, sidecars, labels, and `--risk` are projections or scaffold seeds.
- R4. A missing, malformed, or unrecognized Risk field blocks prepare and create-prepared. `UNKNOWN`
  passes field-shape validation and the issue creation gate; prepare and create-prepared retain a
  warning naming the missing Architect assessment. The card stays in Planning because the later
  Planning-to-Active readiness gate refuses `UNKNOWN` until the Architect records a tier. A `--risk`
  value that conflicts with a source body's value blocks.
- R5. Expose a dedicated, schema-sourced `flow repair-window` label write for an open with a cited
  failing result and a close with a cited later deployed passing result. Refuse absent or blank
  citations before network access; preserve idempotency and record the event and citation on the
  parent issue. Never write a fourth project field for this label.
- R6. Retire the active `Technical Risk` project-field mapping and interactive prompt under SDLC
  decision E1. Keep historical sidecars intact; identify the upstream queued item as upstream
  custody without editing it in this repository.
- R7. For #942, Mission Control obtains readiness assessment and routing text from the Saga plugin's
  shared owner. Keep the six Saga maturities and its strict declaration diagnostics; eliminate the
  local maturity parser, local vocabulary, and `requirements-ready` default on readiness paths.
- R8. Saved issue drafts and Saga state JSON require an explicit readiness declaration in the Saga
  owner. Pending confirmation, blank, undeclared, invalid, malformed, unreadable, and other unknown
  states never produce live `/plan` or `/work` routes. A pending-confirmation card may be created with
  its non-routable diagnostic; a `deferred-context` card is creatable with the existing "clarify
  current intent" next action and no live plan/work route; unknown and blank declarations block
  creation.
- R9. Resolve local sources against the named repository root before reading. A contained twin may
  be selected and published as that twin; a bare out-of-root path is refused. Existing explicit
  GitHub URL and branch source choices retain their chosen identity. Read, draft, sidecar, and
  published handoff must agree on the chosen source.
- R10. Resolve Saga lazily through the existing fleet-core plugin-resolution ladder. Missing or
  incompatible Saga stops readiness-bearing operations with a repairable dependency diagnostic and
  no legacy fallback; unrelated Mission Control commands remain usable.
- R11. Preserve the settled sequence and custody: #999 before #1000; #1000 and #942 serialized on
  `plugins/mission-control/scripts/sdlc_manager.py` under the sole Dev seat `w86:p9`. The Test Author
  owns finite test authoring before Dev production edits, and independent reviewers retain their
  separate gates.
- R12. Ship plugin version, marketplace metadata, changelog, and journal entries in the same future
  change as behavior; retain all existing meaningful test pins and run the repository gate before
  any delivery claim. No merge, deployment, card closure, or live board write is authorized by this
  plan.

The card-creation rule in R8 has these complete dispositions. This table concerns handoff maturity;
the separate Risk field rule in R4 still applies to the same card.

| Handoff maturity | Card creation | Suggested next action |
| --- | --- | --- |
| `idea-ready`, `requirements-ready` | Allowed | Saga-owned `/plan` route |
| `plan-ready`, `resume-ready` | Allowed | Saga-owned `/work` route |
| `deferred-context` | Allowed | "Clarify current intent"; no live `/plan` or `/work` |
| `pending-confirmation` | Allowed | Saga-owned boundary diagnostic; no live `/plan` or `/work` |
| Declared blank or `unknown:*` | Blocked before draft | Saga-owned diagnostic, no live route |
| No source and no `--maturity` on text-only prepare | Draft allowed with missing-maturity warning | No readiness route |

## Key Technical Decisions

- KTD1. Use the exact SDLC source commit above, not a moving `main`: generated issue-contract data
  and the schema must share provenance. A source SHA or schema version change requires a plan amendment
  and a fresh parity check, not a silent substitution. Supports R1–R3.
- KTD2. Retire `_wip_limits` and its retired `mount-olympus` fallback together: the current Stage
  vocabulary has no defined limits, and the hard-coded `Ready` / `In Progress` output is misleading.
  `board wip` reports counts and no defined limits; `board view` prints counts without a limit
  decoration. This is the reported #999 stop-condition finding and its proposed resolution; the Lead
  must record acceptance of this disposition before Dev changes it. Supports R1.
- KTD3. For a separated #999 change, permit exactly `Risk` as a dated schema-to-generated-header lag;
  the guard must fail on every other difference. #1000 removes the allowance. This prevents a green
  parity test from hiding the thirteen-versus-fourteen-field split. Supports R2.
- KTD4. Read Risk from the body once, using the schema's tier vocabulary. `--risk` seeds a generated
  scaffold only; an existing source body without `### Risk` stays invalid. Metadata cannot override
  body content. Supports R3–R4.
- KTD5. `UNKNOWN` is a valid Risk field value and does not block `create-prepared`. Record a warning
  naming the missing Architect assessment, then create the card in Planning; the later
  Planning-to-Active gate refuses it until the Architect replaces `UNKNOWN` with a tier. The pinned
  SDLC `docs/process/card-schema.md` states this sequence, and the independent Plan Reviewer
  rejected the earlier creation-blocking oracle in blocking finding B1. Supports R4.
- KTD6. Use a dedicated `flow repair-window` verb, not `flow set-field`: the schema encodes a label,
  and `set-field` writes single-select project fields. Mission Control only provides the verb; the
  Delivery Manager's Saga emission on verification events is separate follow-up work. Supports R5.
- KTD7. Add Saga-owned `assess_source` and `assess_declared` APIs with a readiness-contract major
  version. The owner returns maturity, routability, diagnostic, next action, source read and published
  identities. The envelope's existing schema version remains separate. This keeps Mission Control
  from deriving or mirroring readiness. Supports R7–R10.
- KTD8. Saved draft sidecar JSON key `handoff_maturity` and Saga state JSON top-level key
  `handoff_maturity` are the explicit-declaration carriers. A draft's naive Markdown frontmatter is a
  mirror and must agree with the sidecar; it is not the owner's YAML carrier. Supports R8.
- KTD9. Explicit external choice means the existing GitHub issue or pull-request URL or branch
  reference, or an operator-selected contained counterpart. No new arbitrary external-file override
  is introduced. The selected/read source is the published identity. Supports R9.
- KTD10. The approved live Dev session stays `w86:p9`; no additional writer or session is planned.
  Even though #942 does not depend on the schema, it follows #1000 on the shared prepare spine.
  Supports R11.

## Implementation Units and exclusive custody

The Test Author seat `w86:p8` writes the five new Mission Control test modules named in the finite
test plan, plus Saga-owner parity cases in `tests/test_handoff_envelope_maturity.py`, **before** the
Dev touches production. These may be red on the pinned candidate. The Dev alone updates existing
test fixtures and pins during the corresponding unit. The Test Author does not edit those existing
Mission Control files, and the Dev does not rewrite the Test Author's new files without returning a
specific mismatch for a test-author amendment. The Plan Reviewer seat `w86:p4` reviews both plans;
the Review seat `w86:p3` later reviews code only. Neither is a production writer.

| Order | Unit | Child | Sole production and existing-oracle writer | Required preceding unit |
| --- | --- | --- | --- | --- |
| 1 | U1 | #999 | Dev `w86:p9` | Test Author's T999 rows recorded |
| 2 | U2 | #1000 | Dev `w86:p9` | U1 accepted at its local gate |
| 3 | U3 | #1000 | Dev `w86:p9` | U2 |
| 4 | U4 | #942 | Dev `w86:p9` | U3; Saga owner first |
| 5 | U5 | #942 | Dev `w86:p9` | U4 |
| 6 | U6 | integration | Dev `w86:p9` | U1–U5 |

### U1. Re-vendor the schema and retire obsolete limit reads

Bring the vendored JSON to `2026-09-07.5` without silently activating Risk validation early.

**Goal:** Satisfy R1–R2 for #999 with truthful board output and an explicit generated-artifact lag.

**Requirements:** R1, R2, R11, R12.

**Dependencies:** Test Author has authored T999-01–04; the Lead has recorded the KTD2 stop-condition
disposition. No #1000 edit precedes this unit.

**Files:** `plugins/mission-control/config/sdlc-schema.json`,
`plugins/mission-control/scripts/sdlc_manager.py`,
`plugins/mission-control/skills/board/SKILL.md`, `plugins/mission-control/README.md`,
`plugins/mission-control/tests/test_prompt_alignment.py`,
`plugins/mission-control/tests/test_issue_contract_parity.py`, `tests/test_mission_control.py`,
`plugins/mission-control/tests/test_schema_resync.py` (Test Author owned), and the release and journal
files named under U6.

**Approach:** Copy the source JSON from the pinned SDLC commit. Remove `_wip_limits`, its callers,
and the legacy limits branch. Keep Status counts. Replace the retired WIP guidance. Add a header
comparison guard with only the dated `Risk` exclusion; update the version pin, not the generated
contract yet. Preserve remote-first schema resolution behavior and report when a live remote schema
differs from the pinned vendored version.

**Patterns to follow:** `test_prompt_alignment.py` version pin,
`test_issue_contract_parity.py` manifest guard, `test_project_mappings_resolution.py` resolution
tests, and `board_view` / `board_wip` in `sdlc_manager.py`.

**Test scenarios:** T999-01 exact version; T999-02 no removed-key production readers and the new
`components` key; T999-03 full plugin suite; T999-04 existing pin and WIP-oracle updates. Add a
behavior assertion that `board wip` has counts but no fictional `10` / `5` limit.

**Verification:** The pinned schema hash and version match; the removed keys have no production
reader; the lag guard reports precisely one intentional Risk difference; #999-scoped tests pass.
The full plugin-suite row T999-03 remains pending until the pre-authored #1000 and #942 tests can pass.

### U2. Make Risk a common body field

Bring the prepared-issue contract, scaffold, templates reference, and gate onto one body-sourced Risk.

**Goal:** Satisfy R2–R4 for #1000 after the schema is present.

**Requirements:** R2, R3, R4, R11, R12.

**Dependencies:** U1 complete. Under the same Dev seat `w86:p9`, #1000 edits to `sdlc_manager.py`
complete at U3 before #942 edits begin at U5.

**Files:** `plugins/mission-control/config/generated/issue_contract_data.py`, its `.sha256`,
`plugins/mission-control/config/generated/issue_contract_shim.py`, its `.sha256`,
`plugins/mission-control/scripts/sdlc_manager.py`,
`plugins/mission-control/skills/issues/references/templates-reference.md`,
`plugins/mission-control/tests/test_issue_contract_parity.py`,
`plugins/mission-control/tests/test_template_sync.py`,
`plugins/mission-control/tests/test_issue_prepare.py`,
`plugins/mission-control/tests/test_issue_create_prepared.py`,
`plugins/mission-control/tests/test_issue_prepare_compile_approve.py`,
`plugins/mission-control/tests/test_card_validator.py`,
`plugins/mission-control/tests/test_card_validator_agreement.py`,
`plugins/mission-control/tests/test_issue_risk_field.py` (Test Author owned), and U6 release files.

**Approach:** Copy the generated data, shim, and manifests from the same SDLC commit as U1; update
hash oracles and remove the Risk lag allowance. Re-render the five-form reference with the existing
`sync_template_docs.py` rather than editing its generated output by hand. Make a single Risk reader
for both actionable and Asgard bodies. Seed compiled scaffolds with a supplied tier or `UNKNOWN`;
reject a missing Risk section in supplied bodies. Derive sidecar `risk` and frontmatter `risk:` from
the body; retire `TBD` and the separate Asgard metadata gate. Allow `UNKNOWN` through prepare and
create-prepared with a warning naming the missing Architect assessment; leave the card in Planning
until the later Planning-to-Active gate receives a real tier.

**Patterns to follow:** `_contract_scaffold_body`, `_required_contract_field_keys`,
`_read_prepared_issue`, `_readiness_for_prepared_issue`, and the upstream
`tools/docs/gen_issue_contract.py` outputs at the pinned revision.

**Test scenarios:** T1000-01–05, including missing section despite `--risk` or label, four exact
tiers with the high-tier conditional trio, the `UNKNOWN` creation-versus-Active-readiness
distinction, and invalid format or missing justification. Existing actionable fixture and SHA-256
oracles must remain strong.

**Verification:** Vendored schema and both generated modules have identical field headers after the
exclusion is removed; a missing Risk field cannot reach GitHub create; `UNKNOWN` can reach the
mocked create path with its warning; valid tiers retain their conditional requirements; focused
and plugin tests pass.

### U3. Add the repair-window label verb and retire Technical Risk

Finish #1000 without turning a label into a project field or rewriting historical drafts.

**Goal:** Satisfy R5–R6 and complete #1000's local behavior.

**Requirements:** R5, R6, R11, R12.

**Dependencies:** U2; same Dev seat and same `sdlc_manager.py` custody.

**Files:** `plugins/mission-control/scripts/sdlc_manager.py`,
`plugins/mission-control/tests/test_flow_subcommands.py`,
`plugins/mission-control/tests/test_repair_window_label.py` and
`plugins/mission-control/tests/test_technical_risk_retirement.py` (Test Author owned),
`plugins/mission-control/skills/flow/SKILL.md`, `plugins/mission-control/README.md`, and U6 release
files. The upstream `infiquetra-sdlc/docs/engineering-journal/QUEUED.md` is read-only here.

**Approach:** Add `flow repair-window --repo --number --action open|close --citation` using the marker
name from the vendored schema. Validate citation before any remote call; open self-heals the label
definition from the SDLC labels source, then adds the label and posts a single event/citation
comment; close removes it and posts its cited event. No-op retries neither duplicate comments nor
project-field writes. A schema too old to supply the marker fails clearly. Remove the live
`Technical Risk` sidecar project-field mapping and interactive prompt; point the current reality
note and journal decision at E1. Preserve historical sidecars. Record the upstream queued item and
its limited retirement on #1000 only when the Lead separately authorizes the issue comment.

**Patterns to follow:** `issue_label_add`, `issue_label_remove`, `flow verify-label`, existing
comment helper and label REST mocks in `tests/test_mission_control.py`.

**Test scenarios:** T1000-06 cited open, T1000-07 cited close and idempotent no-op, T1000-08
missing/blank citation refusal before REST, T1000-09 no live Technical Risk queue or mapping. Add
schema-too-old and repeated-operation assertions inside those rows.

**Verification:** No GraphQL project-field mutation occurs for the label; the verb's evidence names
the event and citation; static and runtime retirement checks pass.

### U4. Extend Saga's shared readiness owner

Make Saga capable of assessing the two declaration-required source classes before Mission Control
consumes the new contract.

**Goal:** Satisfy the Saga-owned part of R7–R10 without changing existing handoff envelopes.

**Requirements:** R7, R8, R9, R10, R11, R12.

**Dependencies:** U3 frees the serialized Dev spine; Saga owner changes precede U5.

**Files:** `plugins/saga/scripts/handoff_envelope.py`,
`tests/test_handoff_envelope_maturity.py` (Test Author's new parity cases; Dev changes only unrelated
existing assertions after custody handoff), `tests/test_handoff_envelope.py`, and U6 Saga release
files.

**Approach:** Add an exported readiness-contract major `1`, an exported unknown-prefix constant,
`assess_source(source, root)`, and `assess_declared(value, published_source, *,
declaration_required)`. The returned assessment carries maturity, routability, diagnostic,
`next_action`, `path_read`, `published_source`, re-anchoring, refusal, declaration-required flag, and
contract version. For saved drafts, strictly read sidecar JSON `handoff_maturity`; for Saga state JSON,
strictly read its top-level `handoff_maturity`. Absent declarations yield
`unknown:undeclared:<published>`. Preserve Saga's existing frontmatter parsing, named-root
containment, ordinary-document fallback, and byte-identical envelope output for existing sources.
Do not add the state writer in this unit.

**Patterns to follow:** `ResolvedSource`, `resolve_source`, `_read_frontmatter_maturity`,
`infer_maturity`, and `_maturity_diagnostic` in the owner module.

**Test scenarios:** Owner-side halves of T942-01–06 and T942-09–10 on real files: all six states,
declaration precedence, draft and state undeclared, malformed or unreadable carriers, out-of-root,
and selected twin identity. `deferred-context` keeps its clarification text, not a live `/plan` or
`/work` command. Keep envelope regression tests green.

**Verification:** Owner tests return bounded non-routable diagnostics for all invalid and undeclared
inputs; no old envelope bytes change; the new owner contract is versioned and importable.

### U5. Replace Mission Control's parallel readiness inference

Consume Saga's assessment lazily on readiness-bearing paths and preserve unrelated command reach.

**Goal:** Complete R7–R10 for #942 under the same sole Dev custody.

**Requirements:** R7, R8, R9, R10, R11, R12.

**Dependencies:** U4. No #1000 writer may still be editing `sdlc_manager.py`.

**Files:** `plugins/mission-control/scripts/sdlc_manager.py`,
`plugins/mission-control/tests/test_issue_source_artifacts.py`,
`plugins/mission-control/tests/test_saga_readiness_alignment.py` (Test Author owned),
`tests/test_handoff_envelope_maturity.py` (vocabulary-sync oracle),
`tests/test_fleet_commons_install_time.py`,
`plugins/mission-control/skills/issues/SKILL.md`, and U6 release files.

**Approach:** Resolve the Saga root through
`fleet_commons_shim.load("plugin_resolution").resolve_plugin_root("saga", markers=("scripts/handoff_envelope.py",), env_var="SAGA_ROOT")`.
The resolver returns `tuple[Path, int]`: use the Path as the Saga root and retain the integer
resolution rung as provenance.
Load the owner module only when a source or `--maturity` requires assessment. Check contract major
and required API; a missing module, missing PyYAML, or incompatible contract yields one actionable
dependency error and writes no draft. Delete `_HANDOFF_MATURITY_CHOICES`,
`_infer_maturity_from_path`, the local next-action lookup, and maturity defaults on routed paths.
Keep source-kind inference. Reconcile an explicit `--maturity` with source declaration; a differing
declaration blocks, while an explicit override of path-only fallback wins. Render and persist the owner's
maturity and diagnostic; publish Lifecycle Origin only for a recognized vocabulary value. Keep
pending-confirmation creatable but without a live route; block blank or `unknown:*` before draft.
Maintain frontmatter-sidecar mirror agreement and the chosen source identity in every field.

**Patterns to follow:** Saga's reverse Mission-Control resolver in `board_progression.py`, the
fleet-core shim, `test_fleet_commons_install_time.py`, and the existing issue prepare subprocess
tests. Do not import Saga at module scope.

**Test scenarios:** T942-01–10. Cover pending confirmation through the actual prepare path; both
declaration-required classes; six states; escapes and symlinks; explicit URL/branch or selected-twin
identity; missing or incompatible installed Saga; malformed cases; and owner parity. Verify a
text-only `issue prepare` and `board view` still work with Saga absent.

**Verification:** No Mission Control parser or local tuple remains; real source documents give the
same assessment as Saga; a failed dependency cannot publish a route or draft; root plugin tests pass.

### U6. Integrate metadata, journal, and gates

Make the installed-plugin description and verified candidate agree with the final code.

**Goal:** Satisfy R12, preserve separate child evidence, and prepare a reviewable candidate.

**Requirements:** R11, R12.

**Dependencies:** U1–U5; metadata is updated within the same final implementation change, not
deferred to an unsynchronized Release writer.

**Files:** `plugins/mission-control/.claude-plugin/plugin.json`,
`plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
`plugins/mission-control/CHANGELOG.md`, `plugins/saga/CHANGELOG.md`,
`docs/engineering-journal/DECISIONS.md`, `docs/engineering-journal/LEARNINGS.md`, and any existing
version-drift guard. Release seat `w86:p7` later collects evidence but does not edit these files while
Dev owns them.

**Approach:** Record the #999 WIP disposition, #1000 body-sourced Risk and E1 retirement, and #942
shared Saga dependency/sentinel decision in the journal. Capture a learning only for a durable
surprise, such as generated-module lag or install-time resolution. Use one combined implementation
change with child-scoped reviewable commits in U1, U3, and U5 order; include a final metadata and
journal commit in that same change. Bump Mission Control once from 2.15.2 to 2.16.0 and Saga once
from 0.157.1 to 0.158.0. The changelogs name the owning children; plugin.json and marketplace agree.
The Dev runs narrow checks at each boundary and the full
`scripts/gate.sh` before an exact-revision code review. No PR, push, merge, deploy, or card closure
is implied by this unit.

**Patterns to follow:** Current plugin manifests, marketplace entry, changelogs, journal anchors,
and `CLAUDE.md`'s background gate invocation.

**Test scenarios:** Existing metadata drift guard and all T999/T1000/T942 rows; no new behavior
scenario. Independent Code Review later evaluates the exact committed revision, not an earlier green
run.

**Verification:** Each relevant manifest and marketplace version agrees, the journal decisions are
present, the finite table has 23 dispositions, and the full gate returns success on the candidate.

## Tier and spend estimate

These are planning estimates, not authority to launch or change a session. Keep the workspace plan's
approved roster and accounts. The existing Dev is Claude Code through Ollama Cloud GLM-5.3-Flash at
maximum effort; Test Author is Cursor Grok 4.6 at extra-high; Plan Reviewer is Claude Code Opus 5 at
extra-high. No replacement model or added agent is proposed.

| Work | Complexity tier | Expected active agent time | Rough token envelope | Reason |
| --- | --- | ---: | ---: | --- |
| Test Author, 23 rows before Dev | high | 1.5–3 h | 25k–45k | real-file parity, fail-closed cases |
| U1 schema and obsolete reader | medium | 1–2 h | 12k–22k | pinned copy plus behavioral retirement |
| U2–U3 Risk and label | high | 2.5–4.5 h | 30k–55k | prepared issue, REST evidence, generated parity |
| U4–U5 Saga owner and consumer | high | 3–5 h | 40k–70k | installed-plugin compatibility and containment |
| U6 integration and gates | medium | 1–2 h | 10k–20k | version, journal, broad gate |

The total planning envelope is 9–16.5 active agent hours and approximately 117k–212k tokens, before
independent review or repairs. This is an estimate, not a token cap or currency quote: provider
billing rates are not pinned in the source documents. The Lead should record observed spend rather
than claim a dollar total from this table.

## Risks, rollback, and holds

| Risk or trigger | Contained response | Rollback or disposition |
| --- | --- | --- |
| #999's removed WIP key still has a production reader | Lead records the KTD2 finding and disposition before Dev starts; test count-only output | Revert only the #999 child change if board output regresses; never restore fictional limits as a silent fallback |
| Schema and generated modules come from different SDLC commits | Compare source commit, byte hashes, headers and manifest checks at each boundary | Stop U2; restore the pinned files as a set, then repeat parity checks |
| An `UNKNOWN` card is treated as Active-ready before Architect assessment | Preserve the creation warning and assert the later Planning-to-Active gate refuses `UNKNOWN` | Keep the card in Planning and repair the readiness interpretation; do not block initial card creation |
| A cited label operation partially succeeds | Treat label and comment as two observable operations; report evidence and retry idempotently after inspection | Never clear a live repair window merely to revert code; clear only after the schema's cited later deployed pass |
| Historical sidecars contain Technical Risk | Keep them read-compatible without new writes | No migration or mass rewrite; only active producer is retired |
| Saga absent, too old, or missing PyYAML | Stop readiness operation with dependency diagnostic; keep unrelated commands available | Revert coupled #942 consumer and owner changes together; never fall back to Mission Control's path parser |
| External path or symlink escapes named root | Refuse before read; test selected twin identity and original spelling | No automatic external-file access or source rewrite |
| Test and Architect oracles differ | Use the reconciliations in the finite plan and require Plan Reviewer sign-off | No production edit starts on an unresolved blocking review finding |

Holds: the Lead must verify fresh base, source pin, Saga availability for later implementation,
Test Author red/green evidence, and an independent Plan Reviewer acceptance of **both** plans. The
Lead records the KTD2 disposition and the Plan Reviewer's B1 ruling on KTD5. Planning acceptance is
not implementation, merge, deployment, or GitHub issue closure. Parent #1004 remains a grouping;
#999, #1000, and #942 retain individual
evidence and dispositions.

## Scope Boundaries

The implementation does not change the SDLC source schema, the home-lab card validator, upstream
label synchronization, this repository's own generated `.github/ISSUE_TEMPLATE` region, Saga's
`board_progression.py` emission of repair-window events, Saga's state-file declaration writer, or
Saga `parse_issue.py` handling of pending-confirmation flags. It adds no Stage/Status writer, project
field, readiness state, external-file override, session, or monitor. It does not rewrite the 215
historical draft sidecars or assign an Objective to any GitHub card.

## Verification and handoff

The companion finite plan gives exact test IDs, inputs, commands, and expected outcomes. During a
later authorized implementation, run the focused tests first, then
`uv run pytest plugins/mission-control/tests -q`, the relevant root Saga and install-time tests, and
the full `scripts/gate.sh` using the repository's documented background invocation. Capture the
candidate commit, exit codes, test summary, generated-file hashes, and metadata versions. An
independent Plan Reviewer checks these two documents; a later Code Reviewer checks the exact code
revision. Release and Test remain separate evidence gates under their own authority.
