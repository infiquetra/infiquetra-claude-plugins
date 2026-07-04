---
title: "capability: contract-consumer manifest, self-registering consumer graph, and blast-radius ranking"
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
objective: "Establish single-source-of-truth for shared primitives"
wave: wave-2
slug: pf-contract-consumer-graph
---

# capability: contract-consumer manifest, self-registering consumer graph, and blast-radius ranking

### Objective

Establish single-source-of-truth for shared primitives

### Intent

The fleet has no single dataset answering "who consumes contract X, and how exposed are they to a
change in it." That question currently gets answered by manual grep at incident time — the same
grepping that let 343 "clean" cards pass a stale hand-copy of the real contract before anyone
noticed (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §3, finding 1: "Rename/vocabulary
churn + contract-mirror drift (4 repos): saga rename lockstep landings, Olympus→CAMPPS,
`validate_card_body` stale hand-copy of the real `card_validator.py` (343 'clean' cards failed the
live contract, → #222), re-vendored `sdlc-schema.json`"). The existing vendoring gate,
`plugins/mission-control/config/generated/check_issue_contract_parity.py`, only proves the vendored
*bytes* for one artifact pair (`issue_contract_data.py`, `issue_contract_shim.py`) match a pinned
SHA256 manifest computed from `config/sdlc-schema.json` — it answers "did this one copy drift from
its own last-vendored snapshot," never "which consumers across the fleet would be exposed if this
contract changed, and how deeply." There is no manifest, no registry, and no ranking; every "who
uses this" question today is answered by ad hoc `grep -rn` across repos.

This issue merges three views of one underlying dataset — hand-authored intent, self-registered
fact, and field-level exposure ranking — because they are the same "who consumes X" question asked
at three different moments in a contract's lifecycle: authoring time (a human writes down who they
believe depends on this), change time (each vendoring gate proves what it actually consumes, into
one place), and diff time (given a concrete schema diff, which consumers are actually touched, and
how badly). Building only one view leaves the other two moments unanswered by the same tooling that
answers the first.

1. **Contract-consumer manifest + change-time impact report (`T14-F4-4`, primary).** A
   hand-authored `contract-consumers.toml` records, per contract, the consumer modules/files that
   depend on it (the human-declared intent). `scripts/contract_impact.py` reads it and, given a
   contract name, prints every declared consumer — starting with the two current known consumers of
   the issue-contract pair, `plugins/mission-control/scripts/sdlc_manager.py` (via
   `validate_card_body`, `sdlc_manager.py:2481`) and
   `plugins/mission-control/config/generated/check_issue_contract_parity.py` (the parity gate
   itself), plus the fleet's parity test,
   `plugins/mission-control/tests/test_issue_contract_parity.py`.
2. **Self-registering consumer graph (`T14-F6-7`, facet).** Rather than trusting the hand-authored
   manifest to stay current, each vendoring gate in the fleet (starting with
   `check_issue_contract_parity.py`) gains a `register-consumer` step that writes its own consumption
   fact into a central `consumers.json` registry at gate-run time — the gate becomes both a checker
   and a self-reporting node in the graph. A query (`contract_impact.py --registered` or equivalent)
   answers "who consumes contract X" from live registration data, not stale prose.
3. **Blast-radius ranking on a schema diff (`T14-F5-5`, facet).** Given a schema diff (e.g. a
   proposed change to `config/sdlc-schema.json`) and the consumer index from (1)/(2),
   `scripts/blast_radius.py` ranks exposed consumers by how deeply they are touched: consumers that
   read specific changed fields rank as directly exposed, consumers that merely import the whole
   schema rank as exposed-but-unaffected, and non-importing repos rank as unexposed — an
   epidemiological "contact tracing" view of a contract change's actual reach, instead of a flat
   grep hit-list with no severity ordering.

All three views share one consumer index; this issue does not ship three independent tools that
each maintain their own notion of "who consumes what."

## Definition of Done

`contract-consumers.toml` and `scripts/contract_impact.py` exist and resolve the issue-contract
pair's known consumers; `check_issue_contract_parity.py` gains a `register-consumer` step writing
into a central `consumers.json`; `scripts/blast_radius.py` ranks exposed consumers into
field-touching / schema-only / non-importing tiers; all three views resolve consumers through one
shared consumer-index module. Full suite, format, lint, and types stay green
(`uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`).

### Acceptance criteria
- [ ] `contract-consumers.toml` exists at the repo root (or an agreed shared-config location) and
      declares, for the issue-contract pair at minimum, its known consumers: `sdlc_manager.py`'s
      `validate_card_body`, `check_issue_contract_parity.py`, and
      `test_issue_contract_parity.py`. Check: `scripts/contract_impact.py issue-contract` lists all
      three, per `T14-F4-4`'s `dod_sketch` ("impact for issue-contract lists both modules +
      sdlc_manager + parity test").
- [ ] `scripts/contract_impact.py` exits non-zero and names the contract when given an unknown
      contract name, rather than silently returning an empty list — an unrecognized query must be
      loud, not a quiet no-op. Check: `uv run python scripts/contract_impact.py nonexistent-contract`
      exits non-zero.
- [ ] At least one existing vendoring gate — `check_issue_contract_parity.py` — gains a
      `register-consumer` step that writes its consumption fact (contract name, consumer path, gate
      script) into a central `consumers.json` on every run. Check: running
      `check_issue_contract_parity.py` once produces or updates an entry for
      `sdlc-schema.json`/issue-contract in `consumers.json` with the gate's own path recorded as the
      registering consumer.
- [ ] A "who consumes `sdlc-schema.json`" query against the self-registered `consumers.json` matches
      the manually-scanned known consumer set (the same set enumerated for the manifest, above), per
      `T14-F6-7`'s `dod_sketch` ("verified 'who consumes sdlc-schema' matches the manually-scanned
      known set"). Check: `uv run python scripts/contract_impact.py sdlc-schema --registered` output
      set equals the hand-verified consumer set with no omissions or spurious entries.
- [ ] `scripts/blast_radius.py`, given a schema diff and the consumer index, ranks exposed consumers
      in three tiers — field-touching (imports and reads a specific changed field), schema-only
      (imports the whole schema but does not touch the changed field), and non-importing (absent) —
      and orders them field-touching before schema-only before absent. Check: against 3 mock
      consumer repos constructed for the test (one touching a changed field, one importing the whole
      schema untouched, one not importing at all), `uv run pytest tests/test_blast_radius.py
      -k ranking_order` passes, per `T14-F5-5`'s `dod_sketch` ("ranking orders field-touching close,
      schema-only distant, non-importing absent").
- [ ] The manifest, the self-registered registry, and the blast-radius ranker all resolve consumers
      through one shared consumer-index module — no view maintains an independent, divergent notion
      of "who is a consumer." Check: `grep -rn "consumers.json\|contract-consumers.toml"
      scripts/contract_impact.py scripts/blast_radius.py` shows both scripts reading through the same
      index-loading function rather than each parsing the files ad hoc.

### Out-of-scope / non-goals
- Do NOT rewrite `check_issue_contract_parity.py`'s existing byte-parity check or replace it with
  behavioral/corpus-based validation — that is `pf-abolish-contract-mirrors`'s scope (a separate,
  already-drafted issue), not this one. This issue only adds a `register-consumer` step alongside
  the existing check.
- Do NOT register every vendoring gate in the fleet in v1 — `check_issue_contract_parity.py` is the
  reference registration; extending `register-consumer` to every other vendoring surface (e.g. the
  separate `sdlc-schema.json` re-vendoring path, or non-mission-control gates) is a follow-on, not
  required for this issue's acceptance.
- Do NOT build a producer-push notification/dispatch system that emails or opens PRs against
  consumers when a contract changes — this issue delivers a queryable index and a ranked report, not
  an automated dispatch mechanism.
- Do NOT build a general cross-repo dependency scanner covering non-contract code dependencies (e.g.
  arbitrary Python imports) — scope is contract-consumer relationships specifically (schema/validator
  surfaces), not a general import graph.
- Do NOT change the risk-conditional validation matrix or any validator behavior — this issue is
  purely about tracking and ranking who depends on a contract, not changing what the contract
  enforces.

### Files expected to change

- `contract-consumers.toml` (new) — hand-authored manifest of contract → consumer declarations.
- `scripts/contract_impact.py` (new) — reads the manifest and/or `consumers.json`, prints declared
  or registered consumers for a named contract.
- `scripts/blast_radius.py` (new) — given a schema diff and the consumer index, emits a
  field-touching/schema-only/non-importing ranked report.
- `consumers.json` (new, generated/updated at gate-run time) — central self-registered consumer
  registry.
- `plugins/mission-control/config/generated/check_issue_contract_parity.py` — add a
  `register-consumer` step that writes its consumption fact into `consumers.json`.
- `tests/test_contract_impact.py` (new) — manifest-lookup and unknown-contract-error tests.
- `tests/test_consumer_registration.py` (new) — asserts `check_issue_contract_parity.py`'s
  `register-consumer` step writes the expected `consumers.json` entry.
- `tests/test_blast_radius.py` (new) — 3-mock-repo ranking-order test.
- `plugins/mission-control/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
  `plugins/mission-control/CHANGELOG.md` — release-surface updates (see checklist below), since the
  `register-consumer` step changes `check_issue_contract_parity.py`'s runtime behavior.

### Tests to add or update

- `tests/test_contract_impact.py::test_issue_contract_lists_known_consumers` — asserts
  `contract_impact.py issue-contract` lists `sdlc_manager.py`, `check_issue_contract_parity.py`, and
  `test_issue_contract_parity.py`.
- `tests/test_contract_impact.py::test_unknown_contract_errors` — asserts a non-zero exit and a
  named error for an unrecognized contract.
- `tests/test_consumer_registration.py::test_gate_run_registers_consumer` — runs
  `check_issue_contract_parity.py` once and asserts `consumers.json` gains/updates an entry naming
  the gate as a registered consumer of the issue-contract/`sdlc-schema.json` pair.
- `tests/test_contract_impact.py::test_registered_query_matches_manual_scan` — asserts the
  `--registered` query for `sdlc-schema.json` equals the hand-verified consumer set.
- `tests/test_blast_radius.py::test_ranking_order` — against 3 constructed mock consumer repos,
  asserts field-touching ranks before schema-only ranks before non-importing/absent.

### Context library links

- `_none_`

### Acceptance criteria (executable checks summary)

- [ ] `uv run python scripts/contract_impact.py issue-contract` → lists `sdlc_manager.py`,
      `check_issue_contract_parity.py`, `test_issue_contract_parity.py`
- [ ] `uv run python scripts/contract_impact.py nonexistent-contract` → exits non-zero
- [ ] `uv run pytest tests/test_consumer_registration.py -v` → passes
- [ ] `uv run python scripts/contract_impact.py sdlc-schema --registered` → matches the
      hand-verified consumer set
- [ ] `uv run pytest tests/test_blast_radius.py -k ranking_order` → passes
- [ ] Full suite, format, lint, types stay green. Check:
      `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`

### Verification

```bash
# Manifest impact report
uv run python scripts/contract_impact.py issue-contract

# Unknown-contract error path
uv run python scripts/contract_impact.py nonexistent-contract; echo "exit: $?"

# Self-registration: run the gate, then query the registry
uv run python plugins/mission-control/config/generated/check_issue_contract_parity.py
uv run python scripts/contract_impact.py sdlc-schema --registered

# Blast-radius ranking against 3 mock repos
uv run pytest tests/test_blast_radius.py -k ranking_order -v

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . \
  && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all green; the manifest report lists the three known issue-contract consumers; the
unknown-contract query exits non-zero; running the parity gate once populates/updates
`consumers.json` with itself as a registered consumer; the registered query for `sdlc-schema.json`
matches the manually-scanned consumer set with no omissions; the blast-radius ranker orders the 3
mock repos field-touching, then schema-only, then non-importing.

### Release-surface checklist

Because this issue adds a new `register-consumer` step to `check_issue_contract_parity.py`'s
runtime behavior (an existing mission-control vendoring gate), update in the same PR:

- [ ] `plugins/mission-control/.claude-plugin/plugin.json` — version bump reflecting the new
      registration side-effect on the existing parity gate.
- [ ] `.claude-plugin/marketplace.json` — entry synced with the plugin.json version.
- [ ] `plugins/mission-control/CHANGELOG.md` — entry documenting `register-consumer`, the new
      `consumers.json` registry, `contract_impact.py`, and `blast_radius.py`.
- [ ] Any existing version/metadata drift-guard tests (e.g. plugin.json vs. marketplace.json parity
      tests) pass against the bumped version.

## Grounding References

- Absorbed ideas (all `theme: T14`, survivors file
  `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T14.json`):
  - `T14-F4-4` (primary) — "Contract-consumer manifest + change-time re-vendor checklist generator."
    Basis: direct — the fleet's contract-mirror drift finding (grounding brief §3, finding 1: the
    343-card/#222 incident and the `sdlc-schema.json` re-vendoring pattern) has no hand-authored
    "who declares dependence on this contract" record anywhere today.
  - `T14-F6-7` (facet) — "Self-registering consumer graph: instant who-consumes-X blast radius."
    Basis: direct — the same §3 finding; a hand-authored manifest alone cannot be trusted to stay
    current the way `check_issue_contract_parity.py`'s own byte-parity check already proves
    mattered, so consumption facts should be self-reported by the gates themselves at run time.
  - `T14-F5-5` (facet) — "Epidemiological contact tracing: rank exposed consumers by which fields
    they actually touch." Basis: external — a schema diff alone (as produced by any future change to
    `config/sdlc-schema.json`) says nothing about which consumers are actually exposed versus merely
    adjacent; this facet ranks exposure severity rather than producing a flat, unranked consumer
    list.
- Grounding brief: `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §3 ("Consumer-side signal
  (cross-repo journals, 19 repos scanned)"), finding 1 (the 343-card/#222 stale-mirror incident and
  the `sdlc-schema.json` re-vendoring pattern) and finding 3 ("mission-control/saga contract copies
  drifting from source of truth (2 repos) — overlaps finding 1"); and §4 ("Standards/ADR enforcement
  (context library)"), which records that no existing tooling anywhere in the fleet answers
  "who consumes contract X" other than manual grep at incident time.
- Consolidation rationale (issue map): "Who-consumes-X is one dataset with three views: the
  hand-authored manifest with change-time checklists, gates self-registering their copies centrally,
  and field-level exposure ranking on a schema diff."
- Related but distinct issue: `pf-abolish-contract-mirrors` (theme `T14`, ids `H-F1-8`, `H-F6-8`,
  `T14-F3-7`) replaces the hand-copied `validate_card_body` shim with a callable contract surface and
  a behavioral corpus test. This issue is complementary and does not overlap it: that issue removes
  one specific mirror and locks its behavior; this issue builds the fleet-wide "who depends on any
  contract" tracking dataset that would have surfaced the mirror's existence and exposure before the
  #222 incident, not after.

## Recommended Executor Profile

- **Model:** Sonnet
- **Effort:** medium
- **Backend:** inline
- **External-LLM posture:** none
- **Justification:** matches the issue-map's own executor recommendation for this slug. The work is
  three coordinated CLI/data-modeling scripts (a TOML manifest reader, a JSON self-registration
  writer, and a ranking script) sharing one consumer-index module — mechanical scaffolding and
  wiring against an already-understood existing gate (`check_issue_contract_parity.py`), not
  open-ended architectural judgment. Inline is sufficient because all three views share one file/data
  boundary and do not require cross-subsystem reviewer consensus.

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

### Source context

- Source: `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §3, plus
  `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T14.json` (`T14-F4-4`, `T14-F6-7`,
  `T14-F5-5`)
- Source type: ideation-survivor-consolidation
- Source title: pf-contract-consumer-graph (issue-map-final.json)

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/413
- Number: 413
- Created at: 2026-07-04T08:05:28.185657+00:00

