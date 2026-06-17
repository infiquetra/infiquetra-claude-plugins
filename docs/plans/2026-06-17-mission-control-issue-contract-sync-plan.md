---
title: Mission-Control Issue-Contract Consumer Sync
type: fix
status: active
date: 2026-06-17
origin: https://github.com/infiquetra/infiquetra-claude-plugins/issues/222
---

# Mission-Control Issue-Contract Consumer Sync

## Summary

Fix issue #222 by making `mission-control` consume the current Hermes issue contract at every local surface: vendored schema/data, body validation, prepared issue body compilation, template documentation, and `saga` handoff inheritance.

The current `main` branch already has the generated-shim-backed always-required validator surface. The remaining work is to sync the stale schema/template surfaces and make prepared issue bodies impossible to compile as incomplete Hermes task cards.

---

## Problem Frame

Issue #222 reports three definitions of a Hermes task card: the real home-lab gate, the mission-control prepared issue templates, and the mission-control preflight validator. Local evidence shows that the preflight validator has already moved forward: `plugins/mission-control/scripts/sdlc_manager.py:2315` imports generated shim data, and `plugins/mission-control/config/generated/issue_contract_shim.py:18` requires `Objective`, `Intent`, `Context library links`, executable `Acceptance criteria`, and `Verification`.

The remaining drift is still real. `_source_to_issue_body` can emit an Asgard-only body with no core Hermes fields and an Olympus body with missing `Intent`, missing `Context library links`, non-executable `Acceptance criteria`, and placeholder-only fields (`plugins/mission-control/scripts/sdlc_manager.py:3234`). The plugin's vendored `plugins/mission-control/config/sdlc-schema.json` lacks `issue_fields`, while `infiquetra-sdlc` `origin/main` carries `issue_fields` at `config/sdlc-schema.json:641`. The template docs renderer still pins the old six required fields and treats context links as optional (`plugins/mission-control/scripts/sync_template_docs.py:25`; `plugins/mission-control/tests/test_template_sync.py:34`).

---

## Requirements

R1. `mission-control` treats `infiquetra-sdlc` `issue_fields` as the contract source and home-lab `card_validator.py` as the runtime gate, not local hand-maintained header lists.

R2. The vendored `mission-control` schema and generated issue-contract artifacts include the current `issue_fields` block, required-field data, executable acceptance data, context parsing data, and risk-conditional matrix.

R3. `validate_card_body(body)` remains a body-only compatibility preflight, while prepared issue readiness uses a context-aware validation path when `issue_type` and `risk` are known.

R4. Prepared Olympus/Hermes-task body compilation emits every contract section: `Objective`, `Intent`, `Out-of-scope / non-goals`, `Files expected to change`, `Tests to add or update`, `Context library links`, `Acceptance criteria`, and `Verification`, plus risk-conditional sections for high and very-high risk.

R5. High and very-high risk cards cannot pass prepared readiness without `Inputs inventory`, `Failure modes / pre-mortem`, and `Stop conditions`.

R6. A `hermes-task` issue type cannot bypass the Hermes contract merely because the target team is `asgard`; Asgard-specific shaping remains valid only for non-actionable Asgard work such as `exploration`.

R7. `saga` `/handoff` keeps delegating issue body ownership to `mission-control`; no SDLC issue template text is copied into Saga.

R8. Template reference docs, issue-skill guidance, and drift tests describe the current contract: `Intent` is required, context links are required-or-`_none_`, executable acceptance is required, and risk-conditional fields exist.

---

## Key Technical Decisions

KTD1. Source-of-truth remains `infiquetra-sdlc` `issue_fields`; `mission-control` vendors the generated consumer artifacts: this preserves the single-source contract while letting the plugin run offline with checked-in data.

KTD2. Generate data, not algorithms: `mission-control` should continue hand-maintaining validation and prepared-issue control flow while importing generated field headers, regex sources, placeholders, executable checks, and the required matrix.

KTD3. Add a context-aware validation wrapper rather than changing `validate_card_body(body)`: callers that only have a body keep the existing API, while prepared drafts can enforce risk-conditional fields because they know `issue_type` and `risk`.

KTD4. Compile fallback prepared bodies from the contract data, not from two freehand team strings: this removes the Asgard/Olympus divergence and keeps future field-order changes data-driven.

KTD5. Separate team profile from Hermes actionability: non-actionable Asgard shaping can keep its Asgard fields, but actionable `capability` / `enhancement` / `defect` cards must satisfy the Hermes contract regardless of target team.

KTD6. Keep `saga` handoff template-free: `plugins/saga/skills/handoff/SKILL.md:21` already states that `mission-control` owns issue body sections, prepared drafts, readiness, labels, board placement, and GitHub mutation.

---

## High-Level Technical Design

Use `infiquetra-sdlc` generated artifacts as the contract input and keep `mission-control` as a consumer with local parity gates.

```text
infiquetra-sdlc origin/main
  config/sdlc-schema.json issue_fields
  tools/docs/gen_issue_contract.py
  tools/docs/generated/issue_contract_*.py
        |
        v
plugins/mission-control/config/
  sdlc-schema.json
  generated/issue_contract_data.py
  generated/issue_contract_shim.py
        |
        +--> sdlc_manager.py validate_card_body(body)
        +--> sdlc_manager.py validate_card_body_for_context(body, issue_type, risk)
        +--> sdlc_manager.py _source_to_issue_body(...)
        |
        v
tests + docs drift guards
```

The implementation should not move home-lab's `card_validator.py` algorithm into this repo. It should only consume the same data surface and prove the consumer contract by tests.

---

## Implementation Units

### U1. Re-vendor the issue-contract source data

Bring the mission-control consumer snapshot up to the current `infiquetra-sdlc` contract.

**Goal:**

Update the vendored schema/data artifacts so the plugin's checked-in contract matches `infiquetra-sdlc` `origin/main` and home-lab's runtime gate.

**Requirements:**

R1, R2.

**Dependencies:**

None.

**Files:**

`plugins/mission-control/config/sdlc-schema.json`

`plugins/mission-control/config/generated/issue_contract_data.py`

`plugins/mission-control/config/generated/issue_contract_data.py.sha256`

`plugins/mission-control/config/generated/issue_contract_shim.py`

`plugins/mission-control/config/generated/issue_contract_shim.py.sha256`

`plugins/mission-control/config/generated/check_issue_contract_parity.py`

`plugins/mission-control/tests/test_issue_contract_parity.py`

**Approach:**

Use `infiquetra-sdlc` `origin/main` as the source, because the local sibling checkout may be on a dirty feature branch. Confirm `issue_fields` exists in `origin/main:config/sdlc-schema.json` before copying or regenerating any artifact.

Keep the existing consumer-side hash oracle pattern in `plugins/mission-control/tests/test_issue_contract_parity.py:37`. If the artifacts change, update the expected hashes deliberately in the same unit.

**Patterns to follow:**

Follow the current generated-data import pattern in `plugins/mission-control/scripts/sdlc_manager.py:2335`.

Follow the source generator boundary documented in `infiquetra-sdlc/tools/docs/gen_issue_contract.py:24`: generated data is vendored, validator algorithms are not generated.

**Test scenarios:**

Happy path: vendored data and shim hashes match the updated `.sha256` manifests and the independent test oracles.

Edge case: a coordinated edit changes a generated artifact and manifest but not the independent oracle; the parity test fails.

Error path: the vendored `sdlc-schema.json` lacks `issue_fields`; a focused test fails with a message naming the missing block.

Integration scenario: `test_vendored_data_carries_risk_matrix` still proves `high` and `very-high` risk conditional fields exist.

**Verification:**

The consumer artifacts import cleanly, the expected hash tests pass, and a direct `rg "issue_fields" plugins/mission-control/config/sdlc-schema.json` finds the block.

### U2. Add context-aware contract validation

Make prepared issue readiness enforce fields that require issue type and risk.

**Goal:**

Add a validation path that keeps the public body-only preflight intact while enforcing the full required matrix for prepared issues.

**Requirements:**

R3, R5, R6.

**Dependencies:**

U1.

**Files:**

`plugins/mission-control/scripts/sdlc_manager.py`

`plugins/mission-control/tests/test_card_validator.py`

`plugins/mission-control/tests/test_issue_prepare.py`

`plugins/mission-control/tests/test_issue_prepare_compile_approve.py`

`plugins/mission-control/tests/test_issue_create_prepared.py`

**Approach:**

Keep `validate_card_body(body)` as the compatibility function currently used by `flow_validate_card` (`plugins/mission-control/scripts/sdlc_manager.py:2471`). Add a small context-aware wrapper that imports the full generated data module, derives required H3 headers from `REQUIRED_MATRIX`, skips auto-populated fields, and then layers those requiredness errors on top of the existing body-only checks.

Wire `_readiness_for_prepared_issue` to use the context-aware wrapper for all `_DISPATCH_ACTIONABLE_TYPES`, not only `team == "olympus"`. Preserve the Asgard-specific required fields for non-actionable Asgard shaping.

**Patterns to follow:**

Follow home-lab's matrix evaluation shape in `home-lab/ansible/roles/hermes_orchestrator/files/card_validator.py:202`.

Follow the prepared-readiness fault aggregation pattern in `plugins/mission-control/scripts/sdlc_manager.py:3363`.

**Test scenarios:**

Happy path: a medium-risk capability body with all always-required fields passes prepared readiness.

Edge case: a high-risk capability body without `Inputs inventory`, `Failure modes / pre-mortem`, and `Stop conditions` is blocked with all three missing-section names.

Edge case: a low-risk capability body does not require the high-risk sections.

Error path: a body with all headers but non-executable acceptance remains blocked by the existing executable-acceptance error.

Integration scenario: an Asgard `exploration` draft still passes Asgard shaping readiness, while an Asgard `capability` draft must satisfy the Hermes-task contract.

**Verification:**

Prepared issue readiness blocks exactly the contract gaps for the known `issue_type` and `risk`, without changing body-only callers that lack that context.

### U3. Compile prepared issue bodies from contract fields

Replace the freehand fallback templates with a generated-data-backed body scaffold.

**Goal:**

Ensure `_source_to_issue_body` never emits an actionable Hermes task body missing required contract sections.

**Requirements:**

R4, R5, R6.

**Dependencies:**

U1, U2.

**Files:**

`plugins/mission-control/scripts/sdlc_manager.py`

`plugins/mission-control/tests/test_issue_prepare.py`

`plugins/mission-control/tests/test_issue_prepare_compile_approve.py`

`plugins/mission-control/tests/test_issue_create_prepared.py`

**Approach:**

Change the fallback path at `plugins/mission-control/scripts/sdlc_manager.py:3234` to build sections from generated contract data for actionable issue types. The minimal scaffold should include meaningful, visibly incomplete placeholders for author-only fields and `_none_` for `Context library links` only when no source context exists.

When the source already contains `###` sections, preserve the existing pass-through behavior but validate it with the context-aware wrapper. When the source is plain text, use it as the initial `Objective` and create the remaining required sections explicitly so the draft tells the author exactly what is missing.

**Patterns to follow:**

Follow the existing sidecar/readiness state model: malformed fallback drafts are allowed to be written, but they must land as `blocked`, not `needs_operator_approval` (`plugins/mission-control/scripts/sdlc_manager.py:3510`).

**Test scenarios:**

Happy path: a fully structured source body compiles to `ready_to_create` and `needs_operator_approval`.

Edge case: a plain-text Olympus source writes every required H3 header and lands as `blocked` with concrete gaps, instead of silently omitting `Intent` or `Context library links`.

Edge case: high-risk fallback includes `Inputs inventory`, `Failure modes / pre-mortem`, and `Stop conditions`.

Error path: placeholder-only required fields still block readiness.

Integration scenario: `saga` `/handoff` sources that call `mission-control issue prepare` inherit the corrected body scaffold without any Saga template edits.

Integration scenario: an approved prepared draft created from the compiled contract body still passes `issue_create_prepared`, preserves project-field mutation behavior, and records the created issue in the sidecar.

**Verification:**

No prepared actionable draft can be missing a required H3 section due to mission-control's fallback compiler.

### U4. Refresh template docs and issue-skill guidance

Remove stale documentation that still describes the old six-field contract.

**Goal:**

Make mission-control docs match the current generated issue contract.

**Requirements:**

R8.

**Dependencies:**

U1.

**Files:**

`plugins/mission-control/scripts/sync_template_docs.py`

`plugins/mission-control/skills/issues/SKILL.md`

`plugins/mission-control/skills/issues/references/templates-reference.md`

`plugins/mission-control/tests/test_template_sync.py`

**Approach:**

Update `CONTRACT_REQUIRED_FIELDS` and the renderer text to include `Intent`, required-or-`_none_` context links, executable acceptance, and risk-conditional fields. The renderer may still read canonical GitHub issue templates, but the shared contract summary should come from or be checked against the vendored issue-contract data so old optional-field assumptions cannot survive.

**Patterns to follow:**

Keep `templates-reference.md` generated by `sync_template_docs.py`; do not hand-edit the generated reference.

**Test scenarios:**

Happy path: generated template reference lists `Intent` and `Context library links` under required shared actionable fields.

Edge case: canonical templates still mark context links optional in GitHub form YAML, but the rendered contract note explains required-or-`_none_` for Hermes readiness.

Error path: stale terms such as "optional Context library links" or "six required fields" fail focused tests.

Integration scenario: `uv run python plugins/mission-control/scripts/sync_template_docs.py --check` passes after regeneration.

**Verification:**

The docs generated from the renderer match the checked-in reference and no longer contradict the validator.

### U5. Prove Saga inherits the corrected mission-control boundary

Keep Saga template-free and verify the handoff path routes through mission-control.

**Goal:**

Ensure issue #222 is closed without adding duplicate issue templates to Saga.

**Requirements:**

R7, R8.

**Dependencies:**

U2, U3, U4.

**Files:**

`plugins/saga/skills/handoff/SKILL.md`

`plugins/mission-control/commands/issue.md`

`plugins/mission-control/tests/test_prompt_alignment.py`

**Approach:**

Prefer tests and wording checks over Saga implementation changes. `plugins/saga/skills/handoff/SKILL.md:29` already says not to copy SDLC issue templates into the skill, and lines 46-49 route to `/issue --prepare`. Update only if wording still implies stale fields or direct template ownership.

**Patterns to follow:**

Follow the existing boundary decision in `docs/engineering-journal/DECISIONS.md:692`: `sdlc-manager` owns handoff issue artifacts.

**Test scenarios:**

Happy path: prompt-alignment tests confirm Saga guidance still routes to `mission-control issue prepare`.

Edge case: no Saga skill file contains copied `Objective` / `Acceptance criteria` template blocks.

Error path: a future edit adding SDLC issue template body text to Saga fails a focused no-copy drift test.

Integration scenario: a prepared issue created from a Saga handoff uses the mission-control body compiler and readiness gates.

**Verification:**

Saga remains an ownership/routing layer, and the corrected issue contract lives in mission-control.

---

## Risks & Dependencies

| risk | mitigation |
|------|------------|
| The local `infiquetra-sdlc` checkout is dirty and not on `main`. | Read from `origin/main` or explicitly update that checkout in a separate step; do not switch or clean the sibling repo during this work. |
| Body-only validation cannot know risk-conditional requirements. | Keep body-only compatibility and add a context-aware wrapper for prepared issue flows that know `issue_type` and `risk`. |
| Generated docs may reflect GitHub form optionality while Hermes readiness treats context as required-or-`_none_`. | Document both layers: form UI optionality can remain a human convenience, but Hermes readiness contract is stricter. |
| Asgard shaping and Olympus execution have different readiness profiles. | Gate by actionability as well as team; actionable types use Hermes contract, non-actionable Asgard work uses Asgard shaping fields. |

---

## Scope Boundaries

This plan does not move the home-lab `card_validator.py` algorithm into `infiquetra-sdlc`; that remains queued tech debt in the SDLC repo.

This plan does not change live GitHub issue form templates in target repositories. It updates this plugin's consumer snapshots, prepared body compiler, docs, and tests.

This plan does not create, mutate, or close issue #222. It produces the implementation plan and saga state only.

### Deferred to Follow-Up Work

If the implementation proves the GitHub issue forms themselves need regenerated fields, handle that in `infiquetra-sdlc` as a separate source-repo change before re-vendoring again.

---

## Sources / Research

GitHub issue: `infiquetra/infiquetra-claude-plugins#222`.

Current generated-shim validator: `plugins/mission-control/scripts/sdlc_manager.py:2315`; `plugins/mission-control/config/generated/issue_contract_shim.py:18`.

Remaining fallback-template gap: `plugins/mission-control/scripts/sdlc_manager.py:3234`.

Prepared readiness split: `plugins/mission-control/scripts/sdlc_manager.py:3363`.

Actionability labels and issue types: `plugins/mission-control/scripts/sdlc_manager.py:2680`.

Stale template docs renderer/tests: `plugins/mission-control/scripts/sync_template_docs.py:25`; `plugins/mission-control/tests/test_template_sync.py:34`.

Source contract on remote `main`: `infiquetra-sdlc/config/sdlc-schema.json:641`; `infiquetra-sdlc/tools/docs/gen_issue_contract.py:24`.

Home-lab runtime gate data: `home-lab/ansible/roles/hermes_orchestrator/files/card_validator.py:25`; `home-lab/ansible/roles/hermes_orchestrator/files/issue_contract/issue_contract_data.py:15`.

Saga handoff ownership boundary: `plugins/saga/skills/handoff/SKILL.md:21`.
