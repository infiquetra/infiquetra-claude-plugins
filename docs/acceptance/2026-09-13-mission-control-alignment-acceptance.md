---
title: Mission Control alignment independent acceptance
type: acceptance
status: passed
date: 2026-09-13
candidate: 829f67a3ab29faed854aa95d9ad86d9e56239791
issues: ["#1004", "#999", "#1000", "#942"]
test_seat: w86:p5
---

# Mission Control alignment — independent acceptance

This is the read-only Test seat result for candidate
`829f67a3ab29faed854aa95d9ad86d9e56239791` (test: fix type annotations in
alignment tests, repair-window schema branch, and envelope maturity parity).
The 23 finite scenarios passed against the actual plugin code and its Saga
readiness owner. No code, commit, merge, board, or release mutation was made.

## Environment and candidate

| Item | Value |
| --- | --- |
| Repository | /Users/jefcox/workspace/infiquetra/infiquetra-claude-plugins |
| Branch / HEAD | main / 829f67a3ab29faed854aa95d9ad86d9e56239791 |
| Python / uv | Python 3.12.11 / uv 0.12.7 |
| Host | jeff-mac-studio.infiquetra.com, Darwin 25.5.0, arm64 |
| Tree state | Pre-existing untracked planning/review documents retained; no unrelated file was changed |

The assignment names plugins/mission-control/skills/sdlc_schema/, but that
directory is absent in this repository. The repository's vendored schema,
used by production and the finite tests, is
plugins/mission-control/config/sdlc-schema.json; that file is the path tested
below and reports version 2026-09-07.5.

## Commands and evidence

### Required suites

~~~text
uv run pytest plugins/mission-control/tests/test_schema_resync.py plugins/mission-control/tests/test_issue_risk_field.py plugins/mission-control/tests/test_repair_window_label.py plugins/mission-control/tests/test_technical_risk_retirement.py plugins/mission-control/tests/test_saga_readiness_alignment.py tests/test_handoff_envelope_maturity.py -q
Pytest: 169 passed

uv run pytest plugins/mission-control/tests -q
Pytest: 503 passed, 0 failed, 1 xfailed
Expected-failure outcomes:
  XFAIL plugins/mission-control/tests/test_card_validator_agreement.py::test_verdict_agreement_unclosed_verification_co...
~~~

The one expected failure is an existing, explicitly marked expected-failure
oracle; it is not a new failure.

### Schema, retired readers, and count-only board output

A direct read-only probe reported:

~~~text
schema_path=plugins/mission-control/config/sdlc-schema.json
schema_version=2026-09-07.5
skills_sdlc_schema_exists=False
top_level_wip_limits=False
component_slices=False
work_hierarchy_components=True
production_retired_key_hits=[]

WIP Status — Asgard
==================================================
  Planning              2
  Active                1
~~~

The production Python census found no wip_limits or component_slices reads.
The board WIP helper emitted status counts only, with no numerical or
threshold limit decoration.

### Risk field and Planning-to-Active gate

The direct parser/prepare/create probe reported:

~~~text
low VALID
medium VALID
high VALID
very-high VALID
UNKNOWN VALID
extreme INVALID
missing INVALID
missing_justification INVALID
unknown_prepare ready_to_create True warning=True
unknown_create True planning_to_active False
~~~

High and very-high included the schema-required Inputs inventory, Failure modes
/ pre-mortem, and Stop conditions sections. The UNKNOWN create used
network/mutation stubs and confirmed the warning is retained while
planning_to_active_risk_ready refuses the transition.

The schema/producer probe also reported:

~~~text
prepared_field_risk=None
risk_field.header=Risk
risk_field.required=True
risk_required_matrix=True
technical_risk_live_producer=False
~~~

### flow repair-window CLI and invocation semantics

Help and refusal probes were run without making a GitHub request:

~~~text
uv run python plugins/mission-control/scripts/sdlc_manager.py flow repair-window --help
help_rc=0
usage: sdlc_manager.py flow repair-window [-h] --repo REPO --number NUMBER
                                          --action {open,close} --citation
                                          CITATION

missing_citation_rc=2
blank_citation_rc=1
ERROR: flow repair-window requires a --citation carrying the test result ...
~~~

A recording harness then exercised the public function with the live network
operations replaced by stubs:

~~~text
repair_window_event_summary:
  open: verify-label, add repair-window, comment containing failing citation
  repeated open: no additional events (idempotent)
  close: remove repair-window, comment containing passing citation
  labels_after: []
  graphql_set_field_calls: 0
blank_citation_refusal: RuntimeError before network
~~~

### Saga-owned readiness and handoff envelope

The actual Saga owner (plugins/saga/scripts/handoff_envelope.py) and Mission
Control consumer were exercised on temporary on-disk fixtures:

~~~text
pending_confirmation:
  saga_maturity=pending-confirmation, saga_routable=False,
  mc_maturity=pending-confirmation, route_in_next_action=False

twin_read:
  saga_maturity=plan-ready, reanchored=True,
  published_source=docs/brainstorms/twin.md,
  mc_ref=docs/brainstorms/twin.md, mc_maturity=plan-ready,
  twin_bytes_read=True, outside_bytes_read=False

fail_closed_bogus: unknown:unrecognized:bogus-value, routable=False, has_live_route=False
fail_closed_carrier: unknown:carrier:plan-ready, routable=False, has_live_route=False
fail_closed_unterminated: unknown:unterminated:plan-ready, routable=False, has_live_route=False
fail_closed_blank: blank maturity, routable=False, has_live_route=False
fail_closed_unreadable: unknown:unreadable, routable=False, has_live_route=False

missing_draft:
  unknown:undeclared:docs/sdlc-issue-drafts/missing.md,
  routable=False, diagnostic names the undeclared draft
mc_missing_brainstorm_error:
  RuntimeError No source artifact matched 'docs/brainstorms/missing.md'. Searched: docs/brainstorms
~~~

This proves pending-confirmation remains non-routable, malformed and unreadable
sentinels fail closed, the assessed twin supplies both bytes and published
identity, and missing-path diagnostics are explicit.

## Scenario ledger — all 23 rows

| Scenario | Result | Evidence |
| --- | --- | --- |
| T999-01 | PASS | test_schema_resync.py; schema version probe |
| T999-02 | PASS | test_schema_resync.py; schema and production-reader census |
| T999-03 | PASS | Full plugin suite: 503 passed, 0 failed |
| T999-04 | PASS | Full suite existing schema/contract/template/prepare oracle pins |
| T1000-01 | PASS | test_issue_risk_field.py; missing Risk blocks and names Risk |
| T1000-02 | PASS | test_issue_risk_field.py; create-prepared refuses and does not call create |
| T1000-03 | PASS | Four tier tokens plus high-risk conditional trio |
| T1000-04 | PASS | UNKNOWN validates, creates with warning, Planning-to-Active returns false |
| T1000-05 | PASS | Invalid token, prose, empty, and missing-justification cases block |
| T1000-06 | PASS | Cited open sets repair-window label and comment |
| T1000-07 | PASS | Cited close removes label and comments; no project-field write |
| T1000-08 | PASS | Missing citation, old schema, and missing label-definition refusals |
| T1000-09 | PASS | Technical Risk producer retired; Risk is required schema field |
| T942-01 | PASS | Pending-confirmation brainstorm remains pending and non-routable |
| T942-02 | PASS | Undeclared saved draft is refused and does not write a draft |
| T942-03 | PASS | Undeclared Saga state is refused and non-routable |
| T942-04 | PASS | All six declared states override folder inference |
| T942-05 | PASS | Out-of-root and symlink escapes fail closed |
| T942-06 | PASS | Explicit contained source preserves source identity; twin bytes agree |
| T942-07 | PASS | Missing Saga dependency produces a named diagnostic |
| T942-08 | PASS | Incompatible Saga contract/vocabulary produces a named diagnostic |
| T942-09 | PASS | Unknown, duplicate, carrier, unterminated, blank, unreadable cases fail closed |
| T942-10 | PASS | Mission Control and Saga agree; no local maturity parser remains |

## Boundary and residual notes

GitHub label/comment writes, project-field writes, issue creation, board reads,
and deployment behavior were not exercised against live services because this
seat is explicitly read-only. The repair-window and UNKNOWN-create probes used
recording stubs and verified that the mutation paths selected by the plugin are
the expected ones.

The old WIP-limit table remains in the historical
plugins/mission-control/skills/board/references/kanban-workflow.md reference,
and some metrics prose still says “WIP limits.” This is documentation drift
outside the 23 production-reader scenarios; the active Python readers and
count-only output are clean.

## Acceptance verdict

PASSED for all 23 Mission Control alignment scenarios at candidate
829f67a3ab29faed854aa95d9ad86d9e56239791.

Blocker or decision: none.
