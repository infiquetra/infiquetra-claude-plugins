---
title: "capability: guarded rename-campaign executor with historical-journal allowlist, aliasable deprecation windows, and positive consumer acknowledgment"
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
objective: Establish single-source-of-truth for shared primitives
wave: wave-2
---

# capability: guarded rename-campaign executor with historical-journal allowlist, aliasable deprecation windows, and positive consumer acknowledgment

### Objective

Establish single-source-of-truth for shared primitives.

## Problem / motivation

The plugin family has already absorbed four hand-done token renames — `infiquetra-lifecycle`→`saga`,
`sdlc-manager`→`mission-control`, `infiquetra-deploy`→`deploy`, and `blueprint-reviewer` folded into
`saga` — recorded as a bare prose note in
`docs/engineering-journal/ARCHIVE.md:9`. On top of that, the Olympus→CAMPPS board-vocabulary retirement
landed as a hand-copy lockstep sweep across roughly four independent repos, described in the grounding
brief as the fleet's single largest recurring cross-repo pain (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`,
§3 finding 1: "Rename/vocabulary churn + contract-mirror drift (4 repos): saga rename lockstep landings,
Olympus→CAMPPS, `validate_card_body` stale hand-copy of the real `card_validator.py` (343 'clean' cards
failed the live contract → #222), re-vendored `sdlc-schema.json`"). None of this is tool-assisted today:

- There is no map-driven executor. Every rename so far has been a manual, ad hoc multi-file sweep with no
  systematic guard against leaving a stray occurrence of the old token outside intentionally-historical
  prose (`ARCHIVE.md`, `CHANGELOG.md` history entries).
- There is no deprecation window. Renames have shipped as one synchronized "big-bang" edit event rather
  than a declared ledger entry with an alias-until date and a forbid-after date, so consumers on either
  side of a lockstep landing window have no grace period and no automated signal when they've fallen
  behind.
- There is no positive-acknowledgment gate. Retirement of the old vocabulary has been assumed complete
  once the primary repo's edit lands, with no per-consumer-repo verification that the new term is present
  and the old term is actually gone before the old term is treated as dead. This is exactly the failure
  class that produced the #222 stale-mirror incident (343 cards silently validated against a hand-copied,
  already-stale contract).
- The binding decision `{#plugin-portfolio-groom-17-to-7}` (`docs/engineering-journal/DECISIONS.md:1031`)
  treats plugin sprawl as an active concern — "new plugin" ideas must carry consolidation-burden proof.
  This capability must ship as tooling inside an existing plugin (`mission-control` or `saga`), not as a
  ninth plugin.

## Definition of Done

- `tools/rename_campaign.py` (or an equivalent script under an existing plugin's `scripts/` directory,
  e.g. `plugins/mission-control/scripts/rename_campaign.py`) that:
  - Accepts an old→new token map plus an allowlist of paths/patterns where the old token may legitimately
    survive verbatim (historical journal entries such as `ARCHIVE.md`, `CHANGELOG.md` history blocks).
  - Supports `--dry-run`, producing a reviewable rewrite plan (not an auto-applied patch) that a human or
    `/plan`/`/work` gate signs off on before any repo-wide guarded replace runs.
  - Performs the guarded, repo-wide replace and emits a single atomic PR (or PR-ready diff) for the primary
    repo's sweep.
  - Runs a post-rename leak assertion that fails if any non-allowlisted occurrence of the old token
    remains anywhere in the tree.
- A renames ledger (e.g. `tools/vocabulary-ledger/renames.jsonl` or `rename-manifest.json`) recording, per
  rename, the old term, new term, `alias-until` date, and `forbid-after` date — both terms are accepted
  during the window; a vocabulary-lint CI check fails only when the retired term reappears past its
  `forbid-after` date, and merely warns while inside the grace window.
- A `--status` (or equivalent) mode that tracks, per registered consumer repo, an explicit adoption
  acknowledgment (new term present AND old term absent, machine-verified, e.g. via `gh` cross-repo grep)
  and refuses to authorize decommissioning the old term until every registered consumer has acked.
- Unit/integration tests exercising all three facets below (see Acceptance Criteria), runnable via
  `uv run pytest`.
- Release-surface updates to whichever plugin hosts the script (see Release-surface checklist).
- A `docs/engineering-journal/DECISIONS.md` entry recording the rename-campaign-tooling pattern (single
  executor + ledger + ack-gate) and a `docs/engineering-journal/LEARNINGS.md` entry closing out the
  fact that renames were, until now, unguarded manual sweeps.

### Acceptance criteria
One per absorbed facet, each independently testable:

- [ ] **Guarded executor (absorbed: T14-F4-5, primary).** Running `rename_campaign.py` with a synthetic
   old→new map against a test fixture directory rewrites every live consumer occurrence, leaves
   allowlisted historical strings (e.g. an `ARCHIVE.md`-style entry) intact and byte-unchanged, and the
   leak assertion exits non-zero when a non-allowlisted old-token occurrence is deliberately left behind.
   Check: `uv run pytest tests/test_rename_campaign.py -k leak_assertion` → passes, and a fixture run with
   zero stray tokens exits `0`.
- [ ] **Aliasable deprecation window, not big-bang lockstep (absorbed: T14-F3-4).** A ledger entry (e.g. in
   `renames.jsonl`) whose `forbid-after` date is in the past, paired with a fixture that still contains
   the old term, causes the vocabulary-lint CI check to fail, citing the specific ledger line. The same
   term with a `forbid-after` date still in the future ("in-grace") produces only a warning, and CI stays
   green. Check: `uv run pytest tests/test_check_forbidden_vocabulary.py -k past_forbid_after` fails
   (asserts non-zero exit) and `-k in_grace` passes with warning output captured.
- [ ] **Positive consumer acknowledgment before decommission (absorbed: T14-F5-2).** Against a synthetic
   two-repo fixture where one repo has adopted the new term (old term absent) and the other still contains
   the old term, `rename_campaign.py --status` reports the first repo as acked and the second as unacked,
   names the unacked repo explicitly, and any subsequent decommission/retire step refuses to proceed while
   at least one consumer is unacked. Check: `uv run pytest tests/test_rename_campaign.py -k
   status_refuses_decommission` → passes, and asserts the laggard repo's name appears in the refusal
   message.
- [ ] **Manifest-driven, not free-form (absorbed: T14-F6-5, scoped down from its moonshot "all-green
   autonomous landing" tier to this issue's structural scope).** The old→new map, allowlist, and
   alias/forbid dates are all sourced from a single manifest file (not scattered flags or inline
   constants), so a second rename campaign requires only a new manifest entry, not new code. Check:
   `uv run pytest tests/test_rename_campaign.py -k manifest_driven` asserts two independent rename
   campaigns run through the same script driven only by different manifest fixtures.

### Out-of-scope / non-goals
In scope:
- A single guarded executor script, its ledger/manifest schema, and its CI-wired vocabulary lint.
- The dry-run → guarded-replace → leak-assertion pipeline for one primary repo at a time.
- Per-consumer-repo acknowledgment tracking and decommission refusal.

Out of scope (non-goals), to keep blast radius minimal:
- **Autonomous multi-repo PR generation and a landing-coordinator that opens/merges PRs across repos**
  (the moonshot half of T14-F6-5 — "100 renames, zero manual edits, landed atomically" with a
  merge-refusing coordinator). This issue ships the single-repo executor plus the cross-repo
  acknowledgment ledger; a fleet-wide autonomous landing coordinator is a follow-on moonshot, not this
  issue's Definition of Done.
- Building a new plugin. Per `{#plugin-portfolio-groom-17-to-7}`, this ships inside an existing plugin
  (`mission-control` or `saga`) — the executor script lives under that plugin's `scripts/` tree, not a new
  `plugins/rename-campaign/` directory.
- Retroactively re-running the tool against the four already-completed historical renames
  (`infiquetra-lifecycle`→`saga`, etc.) or the Olympus→CAMPPS landing — those are done; this issue's DOD
  is the tool and its test fixtures, not a re-execution of past campaigns.
- A generic contract-consumer registry (`contract-consumers.toml` / `blast_radius.py`) — that is a
  separate absorbed-elsewhere theme (see `T14-F4-4`) and is not part of this issue's DOD, though the
  per-consumer acknowledgment ledger here may later be read by such a registry.
- Any change to `check_issue_contract_parity.py` or the vendored-contract SHA-pinning gates — those are a
  distinct drift-detection axis, not rename tooling.

## Grounding References

- **T14-F4-5** (primary, role: primary) — "Guarded rename-campaign executor with historical-journal
  allowlist + atomic PR." Basis: `docs/engineering-journal/ARCHIVE.md:9` (the four hand-done family
  renames) plus grounding brief §3 finding 1 (Olympus→CAMPPS lockstep churn, 4-repo recurrence).
  `dod_sketch`: "Merged tools/rename_campaign.py + rename-allowlist.txt + dry-run fixture; verified a
  synthetic map rewrites consumers, leaves allowlisted history intact, and leak-assertion fails on a
  stray non-allowlisted old token."
- **T14-F3-4** (facet) — "Renames as an aliasable deprecation window, not a big-bang lockstep landing."
  Basis: grounding brief §3 finding 1 (documented lockstep-landing pain across 4 repos); distinct from the
  unrelated `{#marketplace-ci-guard}` seed (that one guards directory-vs-marketplace drift, not
  vocabulary terms). `dod_sketch`: "Merged tools/vocabulary-ledger/renames.jsonl +
  check_forbidden_vocabulary.py in CI; verified a past-forbid-after term with a lingering occurrence fails
  CI while an in-grace term only warns."
- **T14-F5-2** (facet) — "ATC positive handoff: no vocabulary term is retired until every consumer sector
  acknowledges." Basis (external): FAA JO 7110.65 positive two-way handoff / "radar contact"
  acknowledgment procedure, applied to per-consumer-repo ack gating before old-vocabulary decommission.
  `dod_sketch`: "Merged rename_campaign.py + rename-manifest.json + --status dry-run; verified against a
  two-repo fixture the tool refuses decommission and names the unacked laggard."
- **T14-F6-5** (facet, tier_guess: moonshot, absorbed here only for its manifest-driven-execution and
  operator-gated-dry-run facets, not its autonomous multi-repo landing-coordinator ambition) —
  "Manifest-driven autonomous rename campaign with all-green lockstep landing." Basis: grounding brief §3
  finding 1; engages `{#plugin-portfolio-groom-17-to-7}` by extending an existing plugin rather than
  adding one. `dod_sketch`: "Merged rename-campaign skill+script (manifest + codemod + landing-coordinator)
  under an existing plugin; verified a two-repo dry-run diffs generated PRs and the coordinator refuses to
  merge while any member PR is red." — the landing-coordinator/multi-repo-PR half of this sketch is
  explicitly excluded from this issue's scope (see Scope & non-goals) and left for a follow-on.
- **Binding decision** `{#plugin-portfolio-groom-17-to-7}` (`docs/engineering-journal/DECISIONS.md:1031`,
  also referenced at `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` binding-register): plugin
  sprawl is an active concern; this capability must extend `mission-control` or `saga`, not create a new
  plugin.
- **Consolidation rationale** (from `issue-map-final.json`): this issue merges T14-F4-5 (primary
  executor), T14-F3-4 (deprecation-window facet), T14-F5-2 (ack-gate facet), and T14-F6-5's
  manifest-driven/operator-gated facets, because all four attack the same underlying gap — renames are
  currently manual, ungraced, and unacknowledged — and a single tool naturally hosts a map-driven
  executor, a dated ledger, and a per-consumer ack status in one coherent CLI surface.

## Recommended executor profile

- **Model:** sonnet
- **Effort:** high — *target posture: not a live team-execution dispatch knob until `pf-effort-first-class` lands; teammates inherit session tier until then*
- **Backend:** team-execution
- **External-LLM posture:** none
- **Justification:** This is deterministic scaffolding and CLI-tool work (file rewriting, ledger schema,
  CI wiring, test fixtures) with well-specified acceptance criteria — it does not require Opus-level
  judgment or design ambiguity resolution. Sonnet at high effort is appropriate given the number of
  interacting facets (executor + ledger + ack-gate + CI lint) that must compose correctly across several
  test fixtures; team-execution backend is recommended so consensus review can catch the class of defect
  this repo has repeatedly hit with vendored/mirrored artifacts (silent drift, incomplete leak checks)
  before merge, per the grounding brief's team-execution "catches defects green suites missed" finding
  (§3 finding 2).

## Release-surface checklist

This changes plugin behavior (new script, new CLI surface, new CI check) inside whichever plugin hosts
it. Update in the same PR:

- [ ] `plugins/<host-plugin>/.claude-plugin/plugin.json` — version bump, updated description/keywords if
      the rename-campaign capability is user-facing.
- [ ] `.claude-plugin/marketplace.json` — matching version bump for the host plugin entry.
- [ ] `plugins/<host-plugin>/CHANGELOG.md` — entry describing the new rename-campaign executor, ledger
      format, and ack-gate, using the fleet's canonical CHANGELOG heading grammar.
- [ ] Any version/metadata drift-guard tests (e.g. `tests/test_release_triad.py` or equivalent
      release-surface parity test) — must still pass after the bump, proving plugin.json, marketplace.json,
      and CHANGELOG stay in lockstep.
- [ ] If the script is added under `mission-control`, confirm `docs/README.md` for that plugin documents
      the new command/skill entry point.

### Tests to add or update
- `tests/test_rename_campaign.py` — dry-run rewrite, allowlist preservation, leak assertion, manifest-driven
  execution, `--status` acknowledgment refusal.
- `tests/test_check_forbidden_vocabulary.py` — past-forbid-after failure, in-grace warning.
- Release-surface parity test for the host plugin (existing or new), asserting the version bump is
  reflected in `plugin.json`, `marketplace.json`, and `CHANGELOG.md` together.

### Verification
```bash
# Unit tests for the executor and vocabulary lint
uv run pytest tests/test_rename_campaign.py tests/test_check_forbidden_vocabulary.py -v

# Full repo gate (CI parity)
uv run pytest && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports && uv run bandit -r plugins/
```

Expected: all green; the leak assertion, past-forbid-after check, and status-refuses-decommission test
each demonstrably fail when their guarded condition is deliberately violated in a scratch fixture, and
pass otherwise.

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

### Source context

- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T14.json` (ideas T14-F4-5, T14-F3-4,
  T14-F5-2, T14-F6-5)
- Source type: ideation survivor set
- Source title: Plugin-Fleet Ideation — Theme 14 (contract/vocabulary hygiene), rename-campaign-tooling axis

### Intent

The plugin family has already absorbed four hand-done token renames — `infiquetra-lifecycle`→`saga`, `sdlc-manager`→`mission-control`, `infiquetra-deploy`→`deploy`, and `blueprint-reviewer` folded into `saga` — recorded as a bare prose note in `docs/engineering-journal/ARCHIVE.md:9`. On top of that, the Olympus→CAMPPS board-vocabulary retirement landed as a hand-copy lockstep sweep across roughly four independent repos, described in the grounding brief as the fleet's single largest recurring cross-repo pain (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`, §3 finding 1: "Rename/vocabulary churn + contract-mirror drift (4 repos): saga rename lockstep landings, Olympus→CAMPPS, `validate_card_body` stale hand-copy of the real `card_validator.py` (343 'clean' cards failed the live contract → #222), re-vendored `sdlc-schema.json`"). None of this is tool-assisted today:

### Context library links

_none_

### Files expected to change

- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
- `tools/rename_campaign.py`
- `plugins/mission-control/scripts/rename_campaign.py`
- `docs/engineering-journal/DECISIONS.md`
- `docs/engineering-journal/LEARNINGS.md`
- `.claude-plugin/marketplace.json`
- `tests/test_release_triad.py`
- `docs/README.md`

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/417
- Number: 417
- Created at: 2026-07-04T08:06:33.000652+00:00

