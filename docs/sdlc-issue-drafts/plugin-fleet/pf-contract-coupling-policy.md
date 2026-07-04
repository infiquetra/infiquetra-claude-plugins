---
title: "enhancement: machine-checkable contract-coupling policy (pin-vs-float, additive auto-adopt, guard-coverage census)"
repo: infiquetra-claude-plugins
type: enhancement
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
objective: "Establish single-source-of-truth for shared primitives"
wave: wave-2
---

# enhancement: machine-checkable contract-coupling policy (pin-vs-float, additive auto-adopt, guard-coverage census)

### Objective
Establish single-source-of-truth for shared primitives

### Intent
The fleet mixes three pinning strategies for vendored/cross-repo contracts with no stated policy
governing which strategy applies where: semver in `plugin.json`, an exact date-string
`schema_version` literal in `plugins/mission-control/config/sdlc-schema.json` asserted with
`==` in `plugins/mission-control/tests/test_prompt_alignment.py:121`, and SHA256-manifest
byte-identity pins on vendored generated modules
(`plugins/mission-control/config/generated/issue_contract_data.py.sha256`,
`plugins/mission-control/config/generated/issue_contract_shim.py.sha256`, checked by
`plugins/mission-control/config/generated/check_issue_contract_parity.py`). Which contracts pin,
which float, and how a bump in one is supposed to couple to (or be independent of) another is
re-decided ad hoc by whoever touches the file that day — the rule lives in the operator's head,
not in the repo.

Two concrete failure shapes follow from this:

1. **False-negative brittleness.** `sdlc-schema.json`'s own `migration_notes` (lines 4-6)
   classify each change as "strictly additive" or breaking in prose, but the sole consumer pin
   (`test_prompt_alignment.py:121`, `assert schema["schema_version"] == "2026-06-17"`) is an
   exact-literal equality check. A legitimate additive bump — the exact kind `migration_notes`
   says is safe — trips this test anyway, while no logic anywhere actually distinguishes additive
   from breaking at the point of consumption.
2. **Blind-spot on byte pins.** `check_issue_contract_parity.py`'s SHA256 comparison is pure byte
   identity (see its own docstring: "Design (deliberately does NOT run the sdlc generator)... A
   match means the vendored bytes equal what the source generator last produced"). It cannot tell
   an additive, backward-compatible upstream change (a new optional field) from a breaking one
   (a removed/renamed required field) — both flip the hash identically and both currently demand
   the same manual re-vendor ceremony, with nothing distinguishing "safe to auto-adopt" from
   "must gate."

This is the repo's own recurring pain, not a hypothetical: the grounding brief's cross-repo
consumer-signal scan (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:61-64`) ranks
"rename/vocabulary churn + contract-mirror drift" as the #1 recurring cross-repo finding (4
independent repos) — including `validate_card_body` drifting from the real `card_validator`
algorithm until 343 "clean" cards failed the live contract (tracked as issue #222, landed as
`{#mission-control-issue-contract-consumer-sync}` in
`docs/engineering-journal/DECISIONS.md:1045`). That decision explicitly settled the
vendor-vs-generate boundary (mission-control vendors generated data, keeps hand-maintained
consumer algorithms) but did not settle *how a bump propagates* — this issue is the missing
machine-checkable half of that already-settled boundary.

The org already has proof this pattern works: `infiquetra-context-library`'s `validate.yml` CI
runs `context_census.py --check` to keep `llms.txt` honest — a self-describing-index +
census-gate pattern (grounding brief `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:77-79`
and `:86-88`). This issue ports that same meta-pattern onto the fleet's contract surface instead
of inventing a new one.

### Key decisions this issue must honor
- **Declare pin-kind once, check it on disk** (absorbed T14-F2-7, primary). One
  `config/contract_coupling.json` (or equivalent) states, per contract, which pinning strategy
  applies — semver-range, schema-version-floor/compat-block, or byte-SHA256 — and a test asserts
  each contract's actual on-disk pin matches its declared kind. This replaces "re-decide it every
  time" with "stated once, enforced always."
- **Compat block, not exact-literal, for schema-version coupling** (absorbed T14-F1-5, facet).
  `sdlc-schema.json` gains a machine-readable `compat_floor` / `breaking-since` field; consumers
  assert "vendored `schema_version` >= my required floor," not "== frozen string." This turns
  `migration_notes`' existing additive-vs-breaking prose into enforced version-coupling semantics.
- **Auto-adopt additive, gate breaking, for byte-pinned contracts** (absorbed T14-F6-6, facet).
  The parity gate (`check_issue_contract_parity.py` and its `sdlc-schema.json` sibling) gains a
  contract-version + compat-policy manifest so it can tell "new optional field" (safe, auto-adopt,
  no re-vendor ceremony) from "required field removed" (must gate) instead of flipping the same
  binary drift signal for both.
- **Census every declared contract for guard coverage** (absorbed T14-F4-7, facet). Port
  `context_census.py --check`'s exact shape: `scripts/contract_census.py --check` reads the
  contract-coupling manifest, asserts every enumerated contract maps to at least one registered
  guard (parity gate, mirror-drift test, or generator), and fails CI on any `UNGUARDED` row. It
  also emits a generated `CONTRACTS.md` self-describing index. This is the deepest-leverage facet:
  introducing an unguarded contract becomes structurally impossible instead of depending on
  whoever remembers to write the guard.

## Definition of Done
Merged `DECISIONS.md` coupling entry, `config/contract_coupling.json`, and an on-disk pin-kind
check; a compat block (`compat_floor` / `breaking-since`) in `sdlc-schema.json` replacing the
exact-literal assertion; the vendored-contract parity gate auto-adopting additive diffs while
gating breaking ones; and `scripts/contract_census.py --check` plus generated `CONTRACTS.md`
enforcing that every declared contract has a registered guard.

### Out-of-scope / non-goals
- Rewriting or relocating the validator algorithm itself (`validate_card_body` /
  `sdlc_manager.py`) — settled by `{#mission-control-issue-contract-consumer-sync}`; this issue
  only adds the coupling-declaration and drift/guard machinery around already-settled vendor
  boundaries.
- Backfilling contract-version/compat metadata onto every vendored artifact across the fleet in
  one pass — v1 covers the three contracts already named above (`sdlc-schema.json` schema_version,
  `issue_contract_data.py`/`issue_contract_shim.py` SHA256 pins, `plugin.json` semver) as the
  reference set; the census (`contract_census.py --check`) is what prevents future contracts from
  going unguarded, not a one-time backfill of every conceivable pin site.
- Building the generator side in `infiquetra-sdlc` — this issue is entirely within
  `infiquetra-claude-plugins` on the consumer/coupling-declaration side; it does not touch the
  upstream `tools/docs/gen_issue_contract.py` generator.
- Changing what mission-control vendors vs. hand-maintains — that boundary is out of scope; only
  the machine-checkability of the *coupling* between vendored artifacts and their consumers is in
  scope.
- A general-purpose dependency-management tool — this is scoped to the fleet's own declared
  contract surface (schema files, generated/vendored modules, plugin manifests), not third-party
  package pinning (uv/pip already own that).

### Files expected to change
- `config/contract_coupling.json` (new, repo root or `plugins/mission-control/config/`, exact
  location is `/plan`'s to determine) — per-contract declared pin-kind (semver / compat-floor /
  byte-sha256) and its guard reference.
- `plugins/mission-control/config/sdlc-schema.json` — add `compat_floor` / `breaking-since`
  machine-readable field alongside existing `migration_notes` prose.
- `plugins/mission-control/tests/test_prompt_alignment.py` — replace the `schema["schema_version"]
  == "2026-06-17"` exact-literal assertion (line 121) with a floor/range compat-block assertion.
- `plugins/mission-control/config/generated/check_issue_contract_parity.py` — extend with a
  contract-version + compat-policy read so additive vendored diffs auto-adopt and breaking ones
  still gate (currently pure byte-SHA256 comparison per its own docstring).
- `scripts/contract_census.py` (new) — `--check` mode; reads `contract_coupling.json`, asserts
  every declared contract has at least one registered guard, emits generated `CONTRACTS.md`.
- `tests/test_contract_coupling.py` (new) — asserts each declared contract's on-disk pin matches
  its declared pin-kind; a swapped pin-kind fixture fails the check.
- `.github/workflows/*.yml` (or equivalent CI entry point) — wire `contract_census.py --check` into
  CI alongside existing pytest/ruff/mypy/bandit gates.
- `docs/engineering-journal/DECISIONS.md` — new coupling-policy entry recording the pin-kind
  taxonomy and its revisit-when condition.

### Tests to add or update
- `tests/test_contract_coupling.py` — swapping a contract's declared pin-kind (e.g. relabeling the
  byte-SHA256 `issue_contract_data.py` pin as `semver`) fails the on-disk check; the correctly
  declared fleet passes.
- `plugins/mission-control/tests/test_prompt_alignment.py` — an additive `schema_version` bump
  (within the declared `compat_floor`) passes; a bump past the declared `breaking-since` value
  fails.
- A parity-gate fixture test for `check_issue_contract_parity.py` — an additive-only vendored diff
  (new optional field) is auto-adopted without requiring a re-vendor; a field-removal vendored
  diff still gates (fails until re-vendored/acknowledged).
- `tests/test_contract_census.py` (new) — a manifest row with no guard reference makes
  `contract_census.py --check` exit 1; the current fleet's fully-guarded manifest exits 0.

### Acceptance criteria
- [ ] A declared contract's on-disk pin is checked against its declared pin-kind, and swapping the
      kind fails. Check: `uv run pytest tests/test_contract_coupling.py -k pin_kind_mismatch` →
      fails as expected on the swapped fixture, passes on the fleet's real manifest.
- [ ] `sdlc-schema.json` consumers assert a compat floor/range, not an exact-literal string, and an
      additive bump passes while a past-breaking-since bump fails. Check:
      `uv run pytest plugins/mission-control/tests/test_prompt_alignment.py -k schema_version_compat`
      → passes on an additive fixture, fails on a past-breaking-since fixture.
- [ ] The vendored-contract parity gate distinguishes additive from breaking diffs: an additive
      fixture auto-adopts without re-vendor, a field-removal fixture still gates. Check:
      `python3 plugins/mission-control/config/generated/check_issue_contract_parity.py --self-test`
      (or the equivalent pytest fixture the plan lands) → additive case exit `0`
      without manual re-vendor, breaking case exit `1`.
- [ ] Every declared contract in the coupling manifest maps to at least one registered guard;
      adding an unguarded contract row fails the census. Check:
      `python3 scripts/contract_census.py --check` → exit `0` on current fleet; exit `1` after
      inserting a contract row with no guard reference.
- [ ] `contract_census.py` emits a generated, current `CONTRACTS.md` self-describing index. Check:
      `python3 scripts/contract_census.py --check` regenerates `CONTRACTS.md` and the file matches
      what is committed (no diff) — a stale/hand-edited `CONTRACTS.md` fails the check.
- [ ] A `DECISIONS.md` entry records the coupling policy (pin-kind taxonomy, which contracts pin
      vs. float, revisit-when condition). Check: `grep -n "contract-coupling" docs/engineering-journal/DECISIONS.md`
      → finds the new entry.
- [ ] Release-surface metadata reflects the behavior change (this changes mission-control's tested
      contract behavior). Check: `git diff --stat plugins/mission-control/.claude-plugin/plugin.json
      .claude-plugin/marketplace.json plugins/mission-control/CHANGELOG.md` → all three show a diff
      in the same PR.
- [ ] Full suite, format, lint, types, and security scan stay green. Check:
      `uv run pytest && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports && uv run bandit -r plugins/`
      → all pass.

### Verification
```bash
# Coupling-policy pin-kind check
uv run pytest tests/test_contract_coupling.py -v

# Schema-version compat-floor assertion (replaces exact-literal pin)
uv run pytest plugins/mission-control/tests/test_prompt_alignment.py -v

# Parity gate: additive auto-adopt vs breaking gate
python3 plugins/mission-control/config/generated/check_issue_contract_parity.py

# Guard-coverage census (CI parity)
python3 scripts/contract_census.py --check

# Full repo gate (CI parity)
uv run pytest && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports && uv run bandit -r plugins/
```
Expected: all green; the census exits `0` on the current fleet and `1` only when a fixture
deliberately introduces an unguarded contract or a pin-kind mismatch.

### Recommended executor profile
- **Model:** sonnet
- **Effort:** high
- **Backend:** inline
- **External-LLM posture:** none — no external-engine dispatch warranted; this is deterministic
  schema/test/CI plumbing with no research or generation-quality tradeoff, consistent with the
  fleet's stated posture that external engines are never gatekeepers
  (`{#external-engines-never-gatekeepers}`, #283) and this work has no gate to hand off in the
  first place.
- **Justification for sonnet/high (no escalation above sonnet needed):** the four absorbed facets
  are each a bounded, mechanically verifiable change (a manifest schema, a compat-block field, a
  parity-gate extension, a census script) with concrete acceptance fixtures already sketched by
  the ideation absorption — this is structural plumbing work, not judgment-heavy design; `high`
  effort (not `xhigh`) because the surface is well-scoped and grounded in code that already exists
  (`check_issue_contract_parity.py`, `sdlc-schema.json`, `test_prompt_alignment.py`) rather than
  open-ended.

### Release-surface checklist
This changes mission-control's tested contract-consumption behavior (schema-version assertion
semantics, parity-gate pass/fail conditions) and adds a new repo-root script + CI job, so the
following must land in the same PR:
- [ ] `plugins/mission-control/.claude-plugin/plugin.json` — version bump reflecting the contract
      behavior change.
- [ ] `.claude-plugin/marketplace.json` — mission-control entry updated to match.
- [ ] `plugins/mission-control/CHANGELOG.md` — entry describing the compat-floor semantics change
      and the new coupling-policy/census machinery.
- [ ] Version/metadata drift-guard tests (e.g. `plugins/mission-control/tests/test_prompt_alignment.py`
      or the repo's marketplace-drift test) updated so they assert the new schema fields rather
      than silently passing on stale expectations.

### Context library links
- source_context: docs/plans/2026-07-03-plugin-fleet-grounding-brief.md (grounding brief, §3
  cross-repo consumer signal; §4 standards/ADR enforcement)

## Grounding References
- **T14-F2-7** (primary, "Machine-checkable contract-coupling policy: what pins, what floats,
  stated once") — basis: fleet mixes semver (`plugin.json`), date-string `schema_version`
  (`sdlc-schema.json`), and SHA256 manifests (`issue_contract_*.py.sha256`) with no stated policy;
  operator carries the coupling rules in their head. `dod_sketch`: merged `DECISIONS.md` coupling
  entry + `contract_coupling.json` + `test_contract_coupling.py`; verified swapping a declared
  pin-kind fails the on-disk check.
- **T14-F1-5** (facet, "Declare pin-vs-float compat instead of the brittle exact-literal
  assertion") — basis: `plugins/mission-control/tests/test_prompt_alignment.py:121`
  (`assert schema["schema_version"] == "2026-06-17"`), the sole consumer exact-literal pin;
  `sdlc-schema.json` `migration_notes` (lines 4-6) already classify changes additive-vs-breaking in
  prose with no machine-readable compat field. `dod_sketch`: merged compat block in
  `sdlc-schema.json` + floor/range assertion replacing the exact-literal test; verified an additive
  bump passes, a past-breaking-since bump fails.
- **T14-F6-6** (facet, "Pin-vs-float compat manifest: auto-adopt additive contract changes, gate
  only breaking ones") — basis (reasoned): `check_issue_contract_parity.py`'s SHA256 byte
  comparison has no notion of backward compatibility, so an additive schema change (new optional
  field) and a breaking one (removed required field) flip the hash identically and both demand
  manual re-vendor today. `dod_sketch`: merged contract-version + compat-policy in
  `sdlc-schema.json` + parity gate auto-adopt-additive vs gate-breaking; verified an additive
  fixture passes without re-vendor and a field-removal fixture fails.
- **T14-F4-7** (facet, "Contract census + guard-coverage gate") — basis (external, ported
  pattern): `infiquetra-context-library`'s `validate.yml` CI already runs `context_census.py
  --check` to keep `llms.txt` honest (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:77-79`,
  `:86-88`) — the exact self-describing-index + census-gate pattern this issue ports onto the
  contract surface. `dod_sketch`: merged `scripts/contract_census.py --check` + generated
  `CONTRACTS.md` + CI job; verified adding an unguarded contract row exits 1, current fleet passes
  once every existing guard is registered.
- **Binding decisions this issue builds on:**
  - `{#mission-control-issue-contract-consumer-sync}` (issue #222,
    `docs/engineering-journal/DECISIONS.md:1045`) — settled that mission-control vendors generated
    contract data and keeps hand-maintained consumer algorithms; this issue adds the
    machine-checkable coupling/guard layer on top of that already-settled boundary, without
    reopening it.
  - Cross-repo consumer-signal finding #1, `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:61-64`
    — "rename/vocabulary churn + contract-mirror drift" ranked the top recurring cross-repo pain
    (4 independent repos), directly motivating this theme.
  - `{#plugin-portfolio-groom-17-to-7}` — plugin sprawl is an active concern; this issue adds a
    script and manifest, not a new plugin, keeping blast radius inside mission-control/repo-root
    tooling.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: docs/plans/2026-07-03-plugin-fleet-grounding-brief.md
- Source type: grounding-brief
- Source title: Grounding Brief — Plugin-Fleet Ideation (Gate B)

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/414
- Number: 414
- Created at: 2026-07-04T08:05:44.221845+00:00

