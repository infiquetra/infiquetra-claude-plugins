---
title: "capability: producer-push contract propagation and consumer-driven contract guard"
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
slug: pf-producer-push-propagation
---

# capability: producer-push contract propagation and consumer-driven contract guard

### Objective

Establish single-source-of-truth for shared primitives

### Intent

Every shared-contract mechanism the fleet has today is consumer-pull: a consumer vendors a
generated artifact, pins its SHA256, and finds out it drifted only when its own CI runs the parity
check. `plugins/mission-control/config/generated/check_issue_contract_parity.py` is exactly this —
it recomputes the SHA256 of `issue_contract_data.py` / `issue_contract_shim.py` and compares it to a
pinned `.sha256` manifest (`check_issue_contract_parity.py:51-66`), catching a hand-edit or a stale
copy, but only when someone runs it. Nothing on the producer side ever tells the consumer a change
happened; the consumer has to notice on its own schedule. That gap is exactly how issue #222
happened: `validate_card_body` (`plugins/mission-control/scripts/sdlc_manager.py:2481`) held a stale
hand-copy of the real `card_validator.py` contract long enough that 343 "clean" cards passed a check
that no longer matched the live contract before anyone noticed
(`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §3, finding 1: "Rename/vocabulary churn +
contract-mirror drift (4 repos): saga rename lockstep landings, Olympus→CAMPPS, `validate_card_body`
stale hand-copy of the real `card_validator.py` (343 'clean' cards failed the live contract, →
#222), re-vendored `sdlc-schema.json`"). The 2026-06-17 decision that shipped the current
consumer-sync fix deliberately kept `mission-control` as a vendoring consumer of
`infiquetra-sdlc`'s `issue_fields` contract rather than relocating the validator
(`docs/engineering-journal/DECISIONS.md:1045`, `{#mission-control-issue-contract-consumer-sync}`) —
this issue does not revisit that boundary; it inverts who has to notice when the vendored side goes
stale.

This issue merges three views of the same underlying gap — a contract change happens on the
producer side, and nothing pushes that change (or a guard against it) toward the consumers who
depend on it — because building only one leaves the others unanswered by the same registry:

1. **Producer-push contract propagation (`H-F2-5`, primary).** A registry declares, per contract,
   which consumers should receive a refresh when the contract's generated output changes.
   `scripts/contract_dispatch.py` reads the registry and, given a changed contract artifact, opens
   (or updates) a refresh delivery for each registered consumer — abolishing the "consumer notices
   on its own CI run" pattern for whichever contracts opt in.
2. **Consumer-driven contract test / Pact-style guard (`H-F5-6`, facet).** A consumer-authored
   contract manifest declares the specific fields/keys that consumer actually depends on (not "the
   whole schema," a field-level expectation). `scripts/contract_manifest_guard.py` diffs the
   producer's current contract against each declared manifest and fails loud, naming the missing
   field, when a provider rename or removal breaks a declared dependency — seeded with the
   `card_validator` / `sdlc-schema.json` pair that #222 already proved needs it.
3. **Lightweight NOTAM-style broadcast (`T14-F5-6`, facet).** Not every registered consumer needs a
   code-bearing refresh PR — some only need to be told a contract they name changed. The same
   registry supports a second, lighter delivery mode: a NOTAM-style broadcast (an issue opened in
   the consumer, naming the change) for consumers that register for notification only, without a
   generated-artifact refresh.

All three share one registry and one dispatch entry point; this issue does not ship three
independent notification mechanisms that each maintain their own notion of "who is registered for
this contract."

**Scope note on cross-repo credentials.** The producer for the issue-contract pair is
`infiquetra-sdlc` and the producer for `card_validator.py`'s algorithm is the home-lab-ops repo —
both external to `infiquetra-claude-plugins`. Opening a live PR or issue against another
organization repo from a scheduled workflow requires a cross-repo GitHub App/PAT with write access,
which is an infrastructure dependency outside this issue's authority to provision. v1 therefore
proves the dispatch and guard logic end-to-end against fixture consumers and mocked `gh` calls
(`--dry-run`), and converts mission-control's own existing hand-copy consumer to be
registry-declared (which is fully within this repo's control); wiring the dispatcher to run as a
scheduled job inside the actual `infiquetra-sdlc` producer repo is a follow-on once that credential
exists (see Out-of-scope, below).

## Definition of Done

One registry (`contracts/consumers.json`) declares, per contract name, the registered consumers and
their delivery mode (`pr` refresh or `notam-issue` broadcast). `scripts/contract_dispatch.py` reads
that registry and, given a changed contract artifact, dispatches a refresh (or NOTAM broadcast) to
each registered consumer — abolishing the "consumer notices on its own CI run" pattern (`H-F2-5`).
`scripts/contract_manifest_guard.py` diffs the producer's current contract against each consumer's
declared field-level manifest and fails loud, naming the missing field, on a breaking rename or
removal (`H-F5-6`), while leaving unrelated-field changes silent. Mission-control's existing
hand-copy consumer (`issue_contract_data.py` / `issue_contract_shim.py`) is converted end-to-end to
registry-declared vendoring, with its own seeded manifest, while the existing
`check_issue_contract_parity.py` byte-parity gate continues to pass unmodified.

### Acceptance criteria
- [ ] `contracts/consumers.json` (or an agreed shared-config location) declares, per contract name,
      a list of registered consumers, each with a delivery mode (`pr` or `notam-issue`) and a target
      path/repo. Check: `uv run python scripts/contract_dispatch.py --list issue-contract` prints the
      registered consumer(s) for the `issue-contract` name.
- [ ] Editing a fixture contract artifact and running `contract_dispatch.py --dry-run` against it
      opens a refresh-delivery payload only for consumers registered against that contract name; a
      consumer registered against a different contract name produces no payload. Check: `uv run
      pytest tests/test_contract_dispatch.py -k registered_only_dispatch` passes, per `H-F2-5`'s
      `dod_sketch` ("dispatch workflow opening refresh PRs on contract-change merge").
- [ ] A provider rename or removal of a field a consumer's manifest declares dependence on trips
      `contract_manifest_guard.py` loudly, naming the missing field, rather than passing silently.
      Check: `uv run pytest tests/test_contract_manifest_guard.py -k provider_rename_breaks_build`
      passes, per `H-F5-6`'s `dod_sketch` ("provider rename breaks the consumer build loudly").
- [ ] A provider change that does NOT touch any field a consumer's manifest declares dependence on
      does not trip the guard for that consumer. Check: `uv run pytest
      tests/test_contract_manifest_guard.py -k unrelated_field_change_passes` passes.
- [ ] A consumer registered with delivery mode `notam-issue` receives a lighter-weight broadcast
      payload (naming the change, no generated-artifact diff) instead of a PR payload, proving the
      same registry serves both delivery modes. Check: `uv run pytest
      tests/test_contract_dispatch.py -k notam_delivery_mode` passes, per `T14-F5-6`'s `dod_sketch`
      ("verified editing a fixture contract opens a NOTAM issue only in the repo whose
      `contracts.lock` names it").
- [ ] Mission-control's existing hand-copy consumer (`issue_contract_data.py` /
      `issue_contract_shim.py`, generated from `infiquetra-sdlc`'s `issue_fields` block) is converted
      end-to-end to registry-declared vendoring: it appears in `contracts/consumers.json` with its
      own seeded manifest (`contracts/mission-control-issue-contract.manifest.json`), and the
      existing `check_issue_contract_parity.py` byte-parity gate continues to pass unmodified. Check:
      `uv run python plugins/mission-control/config/generated/check_issue_contract_parity.py` exits
      `0`, and `uv run python scripts/contract_dispatch.py --list issue-contract` lists
      `plugins/mission-control/config/generated/issue_contract_data.py` as a registered consumer.
- [ ] An unregistered/unknown contract name given to either script exits non-zero and names the
      contract, rather than silently returning an empty result. Check: `uv run python
      scripts/contract_dispatch.py --dry-run nonexistent-contract` exits non-zero.
- [ ] Full suite, format, lint, and types stay green. Check: `uv run pytest && uv run ruff format
      --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/
      --ignore-missing-imports`.

### Out-of-scope / non-goals
- Do NOT provision or wire a live cross-repo GitHub App/PAT that lets a workflow in
  `infiquetra-sdlc` or home-lab-ops actually open a PR/issue against `infiquetra-claude-plugins` (or
  vice versa) in CI. That credential is an infrastructure dependency outside this issue's authority;
  v1 proves the dispatch/guard logic against fixtures and mocked `gh` invocations only.
- Do NOT rewrite or replace `check_issue_contract_parity.py`'s existing byte-parity check — this
  issue is additive (a field-level Pact-style guard plus a push-dispatch registry), consistent with
  the non-overlap already drawn for `pf-contract-consumer-graph`.
- Do NOT rewrite `validate_card_body` or remove the hand-copied shim algorithm — replacing the
  mirror with a callable contract surface is `pf-abolish-contract-mirrors`'s scope (ids `H-F1-8`,
  `H-F6-8`, `T14-F3-7`), not this one.
- Do NOT build the fleet-wide "who consumes what" tracking dataset (manifest + self-registering
  graph + blast-radius ranking) — that is `pf-contract-consumer-graph`'s scope (ids `T14-F4-4`,
  `T14-F6-7`, `T14-F5-5`). This issue's registry is deliberately narrow (dispatch-target list plus
  per-consumer field manifests), not a general consumer-impact index; the two registries may later
  be unified, but that unification is a follow-on, not required here.
- Do NOT register every vendoring gate in the fleet — v1 seeds exactly one real pair (mission-control
  issue-contract) plus fixture consumers used for testing; extending the registry to other
  vendoring surfaces is a follow-on.
- Do NOT build a standing polling/cron scheduler — v1 ships a triggerable dispatch entry point
  (`contract_dispatch.py`), not a scheduled service; wiring it to a real trigger (a producer-side
  merge hook) is deferred to the credentialed follow-on described above.

### Files expected to change

- `contracts/consumers.json` (new) — registry of contract name → registered consumers, each with a
  delivery mode (`pr` | `notam-issue`) and target path/repo.
- `contracts/mission-control-issue-contract.manifest.json` (new) — the seeded consumer-declared
  field manifest for the issue-contract pair (`card_validator` / `sdlc-schema.json`).
- `scripts/contract_dispatch.py` (new) — reads the registry, given a changed contract artifact
  dispatches a refresh payload (`pr` mode) or a broadcast payload (`notam-issue` mode) per
  registered consumer; supports `--list` and `--dry-run`.
- `scripts/contract_manifest_guard.py` (new) — diffs a producer's current contract against each
  registered consumer's field manifest; fails loud naming the missing field on a breaking rename or
  removal.
- `tests/test_contract_dispatch.py` (new) — registered-only dispatch, NOTAM delivery-mode, and
  unknown-contract-error tests.
- `tests/test_contract_manifest_guard.py` (new) — provider-rename-breaks-build and
  unrelated-field-change-passes tests.
- `plugins/mission-control/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
  `plugins/mission-control/CHANGELOG.md` — release-surface updates (see checklist below), since
  mission-control's issue-contract vendoring path gains a registry-declared entry point.

### Tests to add or update

- `tests/test_contract_dispatch.py::test_registered_only_dispatch` — a fixture contract change
  dispatches only to consumers registered for that contract name; an unrelated registered consumer
  is untouched.
- `tests/test_contract_dispatch.py::test_notam_delivery_mode` — a consumer registered with
  `notam-issue` delivery receives a broadcast-shaped payload distinct from the `pr`-mode payload.
- `tests/test_contract_dispatch.py::test_unknown_contract_errors` — a non-zero exit and a named
  error for an unregistered contract name.
- `tests/test_contract_manifest_guard.py::test_provider_rename_breaks_build` — a provider rename of a
  manifest-declared field trips the guard and names the missing field.
- `tests/test_contract_manifest_guard.py::test_unrelated_field_change_passes` — a provider change to
  a field the manifest does not declare dependence on does not trip the guard.
- `tests/test_contract_manifest_guard.py::test_mission_control_manifest_seeded` — the seeded
  `contracts/mission-control-issue-contract.manifest.json` validates cleanly against the current
  vendored `issue_contract_data.py` / `issue_contract_shim.py` pair.

### Context library links

- `_none_`

### Acceptance criteria (executable checks summary)

- [ ] `uv run python scripts/contract_dispatch.py --list issue-contract` → lists the registered
      issue-contract consumer(s)
- [ ] `uv run pytest tests/test_contract_dispatch.py -k registered_only_dispatch` → passes
- [ ] `uv run pytest tests/test_contract_manifest_guard.py -k provider_rename_breaks_build` → passes
- [ ] `uv run pytest tests/test_contract_manifest_guard.py -k unrelated_field_change_passes` →
      passes
- [ ] `uv run pytest tests/test_contract_dispatch.py -k notam_delivery_mode` → passes
- [ ] `uv run python plugins/mission-control/config/generated/check_issue_contract_parity.py` →
      exits `0`
- [ ] `uv run python scripts/contract_dispatch.py --dry-run nonexistent-contract` → exits non-zero
- [ ] Full suite, format, lint, types stay green. Check: `uv run pytest && uv run ruff format
      --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/
      --ignore-missing-imports`

### Verification

```bash
# Registry lookup
uv run python scripts/contract_dispatch.py --list issue-contract

# Fixture dispatch: registered-only + NOTAM delivery mode
uv run pytest tests/test_contract_dispatch.py -v

# Consumer-driven contract guard: provider rename trips loud, unrelated change does not
uv run pytest tests/test_contract_manifest_guard.py -v

# Existing byte-parity gate still passes after registry conversion
uv run python plugins/mission-control/config/generated/check_issue_contract_parity.py

# Unknown-contract error path
uv run python scripts/contract_dispatch.py --dry-run nonexistent-contract; echo "exit: $?"

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . \
  && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all green; the registry lookup lists the seeded issue-contract consumer; the dispatch
tests prove registered-only routing and the two delivery modes; the manifest-guard tests prove a
provider rename trips loud and an unrelated change does not; the existing parity gate still exits
`0` after mission-control's conversion to registry-declared vendoring; the unknown-contract query
exits non-zero.

### Release-surface checklist

Because this issue converts mission-control's existing issue-contract vendoring path to be
registry-declared (adding a new dispatch/guard entry point around an existing gate), update in the
same PR:

- [ ] `plugins/mission-control/.claude-plugin/plugin.json` — version bump reflecting the new
      registry-declared vendoring entry point.
- [ ] `.claude-plugin/marketplace.json` — entry synced with the plugin.json version.
- [ ] `plugins/mission-control/CHANGELOG.md` — entry documenting `contracts/consumers.json`, the
      seeded manifest, `contract_dispatch.py`, and `contract_manifest_guard.py`.
- [ ] Any existing version/metadata drift-guard tests (e.g. plugin.json vs. marketplace.json parity
      tests) pass against the bumped version.

## Grounding References

- Absorbed ideas (all `theme: T14`, survivors file
  `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T14.json`):
  - `H-F2-5` (primary) — "Producer-push contract propagation: the source repo opens the refresh
    PRs, hand-copying abolished." Basis: direct — the current consumer-pull model
    (`{#mission-control-issue-contract-consumer-sync}`) only detects drift when the consumer's own
    CI runs; nothing on the producer side pushes a change toward registered consumers.
  - `H-F5-6` (facet) — "Consumer-driven contract tests (Pact-style) for vocabulary propagation."
    Basis: direct — the same #222 stale-mirror incident; a byte-parity check alone
    (`check_issue_contract_parity.py`) cannot express "which specific fields does this consumer
    actually depend on," so a provider rename of an unrelated field is indistinguishable from one
    that breaks a real consumer dependency.
  - `T14-F5-6` (facet) — "Aviation NOTAM broadcast: consumers subscribe to a contract, the owner
    broadcasts changes to them." Basis: external (aviation NOTAM broadcast pattern, moonshot-tier
    idea) — not every registered consumer needs a code-bearing refresh PR; some only need to be told
    a contract they named changed, which is a lighter delivery mode on the same registry.
- Grounding brief: `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §3 ("Consumer-side signal
  (cross-repo journals, 19 repos scanned)"), finding 1 (the 343-card/#222 stale-mirror incident and
  the `sdlc-schema.json` re-vendoring pattern) and finding 3 ("mission-control/saga contract copies
  drifting from source of truth (2 repos) — overlaps finding 1").
- Binding decision this builds on: `{#mission-control-issue-contract-consumer-sync}`
  (`docs/engineering-journal/DECISIONS.md:1045`) — the 2026-06-17 decision that kept
  `mission-control` as a vendoring consumer of `infiquetra-sdlc`'s `issue_fields` contract rather
  than relocating the validator algorithm. This issue does not revisit that consumer/producer
  boundary; it adds a push-notification and field-level guard layer on top of it.
- Existing gate this issue is additive to (not a replacement for):
  `plugins/mission-control/config/generated/check_issue_contract_parity.py:51-66` (the pinned-SHA256
  byte-parity check for `issue_contract_data.py` / `issue_contract_shim.py`).
- Consolidation rationale (issue map): "Inverts the propagation burden the consumer-graph issue only
  maps: producer dispatches refresh PRs on contract change, consumers publish Pact-style
  expectations the provider CI honors; NOTAM broadcast is the same push model at moonshot scale."
- Related but distinct issues: `pf-contract-consumer-graph` (builds the fleet-wide who-consumes-what
  tracking dataset this issue's registry deliberately does not duplicate) and
  `pf-abolish-contract-mirrors` (replaces the hand-copied `validate_card_body` shim itself, which
  this issue does not touch).

### Recommended executor profile

- **Model:** Sonnet
- **Effort:** high
- **Backend:** inline
- **External-LLM posture:** none
- **Justification:** matches the issue-map's own executor recommendation for this slug. The work
  spans two coordinated CLI scripts (a registry-driven dispatcher with two delivery modes, and a
  field-level manifest guard) plus a real conversion of an existing production consumer
  (mission-control's issue-contract vendoring) without breaking its existing byte-parity gate —
  higher-context mechanical-plus-integration work than a single-script build, warranting high effort
  over medium, but still a well-understood existing-gate extension rather than open-ended
  architectural judgment, so sonnet/inline is sufficient without cross-subsystem reviewer consensus.

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

### Source context

- Source: `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §3, plus
  `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T14.json` (`H-F2-5`, `H-F5-6`, `T14-F5-6`)
- Source type: ideation-survivor-consolidation
- Source title: pf-producer-push-propagation (issue-map-final.json)

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/416
- Number: 416
- Created at: 2026-07-04T08:06:17.118406+00:00

