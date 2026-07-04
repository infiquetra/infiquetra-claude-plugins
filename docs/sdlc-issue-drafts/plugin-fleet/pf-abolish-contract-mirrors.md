---
title: "capability: forbid hand-copied validators — consumers exec the source-of-truth surface, behavior locked by a real-card corpus"
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: high
handoff_maturity: requirements-ready
tier: structural
objective: "Establish single-source-of-truth for shared primitives"
wave: wave-2
slug: pf-abolish-contract-mirrors
---

# capability: forbid hand-copied validators — consumers exec the source-of-truth surface, behavior locked by a real-card corpus

### Objective

Abolish the hand-copied `validate_card_body` mirror in `mission-control` by making the real
card-validation surface a versioned, callable contract that consumers execute directly instead of
re-implementing — and lock its *behavior*, not just its bytes, with a differential test against
real anonymized card verdicts. This is the structural fix behind the 343-card incident: stop
policing copies with sync/drift-guard automation and instead remove the copy that can drift.

### Intent

`plugins/mission-control/scripts/sdlc_manager.py:2481-2500` (`validate_card_body`) is a hand-copy of
`ansible/roles/hermes_orchestrator/files/card_validator.py` (the home-lab-ops repo's authoritative
validator). Its own docstring says so explicitly: "Mirrors home-lab card_validator.py's high-leverage
checks... If [source] file's contract changes, update shim in same PR." That "update it yourself"
convention is exactly what failed: 343 "clean" cards passed the mission-control shim while the real
contract had moved on, and the drift was only caught by a live incident (`#222`,
grounding brief §3: "validate_card_body stale hand-copy of the real card_validator.py (343 'clean'
cards failed the live contract, → #222), re-vendored sdlc-schema.json").

The repo's existing defense, `plugins/mission-control/config/generated/check_issue_contract_parity.py`,
does not close this gap — it recomputes SHA256 over vendored *bytes* and compares against a pinned
`.sha256` manifest (`check_issue_contract_parity.py:15-21`: "Design (deliberately NOT run sdlc
generator)... match means vendored bytes [equal what the] source generator last produced pinned").
That is byte-parity, not behavioral-parity: if nobody re-vendors after a source change, the gate
stays green forever, structurally blind to the source moving ahead
(`check_issue_contract_parity.py:64` hashes raw bytes; no source-commit provenance is recorded
anywhere in the vendoring surface — verified via `check_issue_contract_parity.py:64-65`, which reads
only `sha_path.read_text().strip()`).

The fix is not another sync job. It is removing the copy: expose the card-validation surface as a
versioned, callable contract owned by `mission-control` (or, per the grounding brief's marketplace
framing, distributed as installed-plugin surface so drift becomes an ordinary version check), rewrite
at least one consumer to call it directly instead of hand-copying it, add a lint that forbids
reintroducing a local mirror, and back the validator's *behavior* — not just its byte identity — with
a corpus of real, anonymized card bodies and their captured verdicts, so a future edit to any
governing regex is caught the moment it changes an outcome on a real card, independent of whether
anyone remembered to re-vendor anything.

### Definition of Done

`mission-control` exposes the card-validation surface (`card_validator` and its schema) as a
versioned, callable contract that consumers execute directly instead of hand-copying. At least
one consumer is rewritten to call that contract, with the removed hand-copy itself standing as
proof. A no-local-mirror lint bans reintroducing a local mirror, and a card-corpus differential
test locks the validator's behavior — not just its byte identity — against real, anonymized
card verdicts.

### Executor Profile

- **Model**: sonnet
- **Effort**: high — *target posture: not a live team-execution dispatch knob until `pf-effort-first-class` lands; teammates inherit session tier until then*
- **Backend**: team-execution
- **External LLM**: none

### Acceptance criteria
- [ ] `sdlc_manager.py`'s hand-copied `validate_card_body` (lines ~2481-2500, mirroring
      `ansible/roles/hermes_orchestrator/files/card_validator.py`) is deleted and replaced by a call
      into a versioned CLI/callable contract surface exposed by `mission-control`; the removed
      hand-copy diff is itself the proof artifact (per `H-F1-8`'s `dod_sketch`). Check:
      `git log -p -- plugins/mission-control/scripts/sdlc_manager.py` on the merge commit shows the
      hand-copied implementation removed, not merely refactored in place.
- [ ] At least one consumer repo/check that previously depended on the hand-copy (starting with
      `plugins/mission-control/tests/test_card_validator.py` and `sdlc_manager.py`'s own
      `validate_card_body` call sites) is rewritten to exec the new versioned contract surface
      instead of running local logic. Check: `grep -rn "validate_card_body" plugins/mission-control`
      shows the call delegating to the new contract entrypoint, not reimplementing checks inline.
- [ ] A no-local-mirror lint rule exists in the validate/CI suite and fails when a locally-implemented
      validation contract (a second independent implementation of the required-header/executable-
      acceptance/placeholder checks) is reintroduced anywhere in the fleet. Check: reintroducing a
      trivial local copy of the required-header check in a scratch file and running the lint reproduces
      a red result; removing the scratch file turns it green again.
- [ ] A real-card verdict corpus (`tests/fixtures/card_corpus/` or equivalent: anonymized real card
      bodies plus their captured pass/fail verdicts) is merged, with a differential test that replays
      every corpus card through the contract surface and asserts its verdict is unchanged. Check:
      `uv run pytest tests/fixtures/card_corpus -v` (or the plugin-local equivalent path) passes on
      the merged state.
- [ ] Mutating exactly one governing regex in the contract surface (e.g. the executable-acceptance
      or checklist regex) fails the corpus differential test on precisely the cards that regex
      governs — and does not fail unrelated cards. Check: apply a scoped one-line regex mutation,
      rerun the corpus test, and confirm the failure set matches the cards whose verdict depends on
      that regex (per `T14-F3-7`'s `dod_sketch`: "verified mutating one shim regex fails the corpus
      test on exactly the cards that regex governs").
- [ ] The contract surface's version/provenance is discoverable by a consumer at call time (e.g. a
      `--version` flag or exported constant), so a future consumer-side check can assert "installed
      contract version X vs. upstream Y" instead of a bytes-only pin. Check:
      the CLI/callable surface exposes a version identifier consumable without parsing implementation
      internals.

### Out-of-scope / non-goals
- Do NOT build a producer-push registry (`contracts/consumers.json`, dispatch-on-change refresh PRs)
  — that is the `H-F2-5` inversion idea, a distinct facet not absorbed into this issue.
- Do NOT build the fleet-wide capability/tier-vocabulary generator-over-guard registry (`H-F4-1`) —
  out of scope; this issue is scoped to the card-validation contract specifically, not every
  producer/consumer mirror in the fleet.
- Do NOT stand up a full Pact-style consumer-driven contract-broker convention with per-pair CI
  guards for every fleet contract (`H-F5-6`) — this issue delivers one migrated contract
  (card validation) as the reference case, not a general broker.
- Do NOT change the risk-conditional matrix (R5-R7) that remains authoritative in the home-lab-ops
  gate — the mission-control surface stays a body-only pre-flight; risk/issue-type-conditional
  checks are explicitly out of scope for this shim's replacement.
- Do NOT attempt to migrate `sdlc-schema.json`'s separate vendoring pattern in this issue — it shares
  the vendoring failure mode but is a distinct artifact; migrating it is a follow-on, not this issue's
  scope.
- Do NOT scope this to a nightly/scheduled upstream-parity CI job (`T14-F1-1`) — that facet was not
  absorbed here; this issue's defense is the corpus differential test, not a scheduled drift sweep.

### Files expected to change

- `plugins/mission-control/scripts/sdlc_manager.py` — remove hand-copied `validate_card_body`
  (lines ~2481-2500), replace with a call into the new contract surface.
- `plugins/mission-control/config/generated/issue_contract_shim.py` — retire or repoint as data-only
  once the callable surface owns the algorithm (KTD2 boundary preserved: data generated, algorithm
  never generated).
- `plugins/mission-control/config/generated/check_issue_contract_parity.py` — update or supplement so
  byte-parity checking does not mask the new callable-surface path.
- `plugins/mission-control/tests/test_card_validator.py` — rewritten to exercise the callable contract
  surface rather than the removed local shim.
- `tests/fixtures/card_corpus/` (new) — anonymized real card bodies + captured verdicts.
- `tests/test_card_corpus_differential.py` (new) — differential test replaying the corpus.
- New or extended lint script under `plugins/mission-control/scripts/` or `tools/` for the
  no-local-mirror rule.
- `plugins/mission-control/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
  `plugins/mission-control/CHANGELOG.md` — release-surface updates (see checklist below).

### Tests to add or update

- `tests/test_card_corpus_differential.py::test_corpus_verdicts_unchanged` — replays every corpus
  card through the contract surface, asserts stored verdict matches.
- `tests/test_card_corpus_differential.py::test_regex_mutation_fails_scoped_cards` — mutates one
  governing regex and asserts only the cards that regex governs flip verdict.
- `plugins/mission-control/tests/test_card_validator.py` — updated to call the new contract entrypoint
  instead of the removed local implementation; existing well-formed/malformed card fixtures continue
  to pass/fail as before through the new path.
- A new lint test (e.g. `tests/test_no_local_mirror_lint.py`) asserting the lint rule fires on a
  planted local-mirror fixture and stays clean on the real tree.

### Context library links

- `_none_`

### Acceptance criteria (executable checks summary)

- [ ] `uv run pytest tests/test_card_corpus_differential.py -v` → passes
- [ ] `uv run pytest plugins/mission-control/tests/test_card_validator.py -v` → passes
- [ ] `uv run pytest tests/test_no_local_mirror_lint.py -v` → passes
- [ ] Full suite, format, lint, types stay green. Check:
      `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`

### Verification

```bash
# Corpus differential test (the behavioral lock)
uv run pytest tests/test_card_corpus_differential.py -v

# No-local-mirror lint (plant a scratch mirror, confirm it reds, then remove it)
uv run python plugins/mission-control/scripts/<no_local_mirror_lint_script> --check

# Consumer path exercises the contract surface, not local logic
uv run pytest plugins/mission-control/tests/test_card_validator.py -v

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . \
  && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all green; the corpus differential test fails only on cards governed by a deliberately
introduced regex mutation (verified manually as part of implementation, not part of the standing
suite).

### Release-surface checklist

Because this changes `mission-control` plugin behavior (removes a hand-copied validator, changes the
call path consumers use), update in the same PR:

- [ ] `plugins/mission-control/.claude-plugin/plugin.json` — version bump reflecting the
      behavior-changing contract-surface migration.
- [ ] `.claude-plugin/marketplace.json` — entry synced with the plugin.json version.
- [ ] `plugins/mission-control/CHANGELOG.md` — entry documenting the hand-copy removal and the new
      callable contract surface / corpus test.
- [ ] Any existing version/metadata drift-guard tests (e.g. plugin.json vs marketplace.json parity
      tests) pass against the bumped version.

### Grounding References

- Absorbed ideas (all `theme: T14`, survivors file
  `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T14.json`):
  - `H-F1-8` (primary) — "Forbid contract mirrors: consumers exec the source-of-truth validator, and a
    lint bans hand-copies." Basis: grounding brief §3 item 1, "validate_card_body stale hand-copy [of]
    the real card_validator.py (343 clean cards failed the live contract, → #222), re-vendored
    sdlc-schema.json" — 4 independent repos, top-ranked consumer-side pain; named issue anchor #222.
  - `H-F6-8` (facet) — "The marketplace is the contract bus: distribute shared contracts as plugin
    surface, making drift a version check." Basis: same grounding-brief §3 finding; additionally
    engages binding decision `{#plugin-portfolio-groom-17-to-7}` — no new plugin is created here,
    the contract surface consolidates into the already-installed `mission-control` plugin.
  - `T14-F3-7` (facet) — "Byte-parity is not behavioral-parity: lock the validator against a real-card
    verdict corpus." Basis: `check_issue_contract_parity.py:15-21` docstring, "Design (deliberately
    NOT run sdlc generator)... match means vendored bytes [equal what the] source generator last
    produced pinned" — the existing gate structurally cannot detect an upstream advance; grounding
    brief §3 records the same 343-card stale-mirror (#222) as the precise blind spot this closes.
- Binding decision engaged: `{#plugin-portfolio-groom-17-to-7}` — this issue must not create a new
  plugin; the contract surface is added to `mission-control`, already installed across consumer repos.
- Grounding brief: `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §3 ("Consumer-side signal
  (cross-repo journals, 19 repos scanned)"), finding 1: "Rename/vocabulary churn + contract-mirror
  drift (4 repos): saga rename lockstep landings, Olympus→CAMPPS, `validate_card_body` stale hand-copy
  [of the] real `card_validator.py` (343 'clean' cards failed [the] live contract, → #222),
  re-vendored [sdlc-schema.json]."
- Consolidation rationale (issue map): "The structural fix behind the 343-card disaster: abolish
  copies rather than police them — versioned CLI/plugin contract surface, a lint banning local
  mirrors, and a real-card verdict corpus locking the validator's behavior, not just its bytes."

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

### Source context

- Source: `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §3, plus
  `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T14.json` (`H-F1-8`, `H-F6-8`, `T14-F3-7`)
- Source type: ideation-survivor-consolidation
- Source title: pf-abolish-contract-mirrors (issue-map-final.json)

### Inputs inventory

- `ansible/roles/hermes_orchestrator/files/card_validator.py`
- `plugins/mission-control/config/generated/check_issue_contract_parity.py`
- `plugins/mission-control/tests/test_card_validator.py`
- `contracts/consumers.json`
- `plugins/mission-control/scripts/sdlc_manager.py`
- `plugins/mission-control/config/generated/issue_contract_shim.py`
- Gate E issue plan: `docs/plans/2026-07-04-plugin-fleet-issue-plan.md`
- Grounding References section of this issue (absorbed-idea bases)

### Failure modes / pre-mortem

- The mechanism ships partially against the Definition of Done — caught by the Acceptance criteria checks below going red.
- Scope creeps past Out-of-scope / non-goals during implementation — caught at PR review against this issue body.
- Release surfaces (plugin.json / marketplace.json / CHANGELOG) drift from the change — caught by the release-surface drift-guard tests.
- `/plan` should deepen this pre-mortem with issue-specific failure modes before implementation.

### Stop conditions

- Any acceptance check cannot go green without widening scope beyond the stated non-goals → HALT, return to operator.
- A load-bearing grounding reference turns out stale against live sources → HALT, re-verify before proceeding.
- Release-surface drift guards fail after version bumps → HALT, reconcile before PR.

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/410
- Number: 410
- Created at: 2026-07-04T08:04:32.368729+00:00

