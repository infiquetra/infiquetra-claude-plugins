---
title: "capability: enforcement-coverage gates — classify every standard, guard binding-but-unenforced decisions, fail never-invoked checks"
repo: infiquetra-claude-plugins
type: capability
tier: structural
objective: "Enforce context-library standards at authoring time"
wave: wave-2
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
executor_profile: {model: sonnet, effort: high, backend: team-execution, external_llm: none}
---

# capability: enforcement-coverage gates — classify every standard, guard binding-but-unenforced decisions, fail never-invoked checks

### Intent
Give this repo a machine-readable answer to "is this standard actually enforced, and by what?"
across four mechanisms that were independently proposed for the same underlying gap and are
consolidated here: (1) an enforcement-coverage classifier that reds CI when a binding decision has
no live enforcer, (2) a standards manifest that classifies every convention as
machine-checkable/judgment/advisory and asserts each machine-checkable row maps to a live check,
(3) a check-coverage meta-guard that reds CI when a registered validator check is defined but never
invoked, and (4) a versioned standards lockfile that plan/review artifacts must cite, with
expiring waivers for any cited violation. All four close the same hole from different angles:
today a binding decision, a documented convention, or a registered check can silently go
unenforced, and nothing in this repo's own CI would ever notice.

## Problem / Motivation

- **Standards/ADR enforcement exists only inside infiquetra-context-library today, not in this
  repo.** Per the grounding brief's standards/ADR-enforcement survey
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §4): the context library's own
  `validate.yml` CI runs `check_docs.py` (schema/frontmatter/link lint + promotion-ledger checks)
  and `context_census.py --check` (keeps `llms.txt` honest) — the org convention is
  **schema-validate-in-CI + self-describing index, not runtime-injected blobs**. But the same
  brief names the gap directly: "**Absent:** any pull of the library into `mission-control:issue` /
  `saga:plan` creation; any ADR↔code-pattern lint; any reference to the library from this repo's
  CI." A repo-side search for any equivalent mechanism in this repo confirms the absence: there is
  no `check_docs.py`, `check_coverage.py`, `check_enforcement_coverage.py`, or
  `check_standards_manifest.py` anywhere in this repository, and this repo's own
  `.github/workflows/ci.yml` runs only `pytest`, `ruff check`, `ruff format --check`, and `mypy`
  (`.github/workflows/ci.yml:43,97-101,122-123`) plus one narrow contract-parity check
  (`plugins/mission-control/config/generated/check_issue_contract_parity.py`,
  `.github/workflows/ci.yml:40`) — nothing that walks the binding-decision register or a
  standards manifest.
- **A binding decision can land in `DECISIONS.md` with no corresponding enforcement of any kind.**
  The binding-decision register (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §2) lists
  eight anchors that each impose a standing constraint — e.g.
  `{#external-engines-never-gatekeepers}` (`docs/engineering-journal/DECISIONS.md:1985`),
  `{#external-engine-chaperone-dispatch}` (`docs/engineering-journal/DECISIONS.md:2021`),
  `{#worker-cache-scheduling}` (`docs/engineering-journal/DECISIONS.md:1950`),
  `{#readonly-verifier-fallback-ladder-325}` (`docs/engineering-journal/DECISIONS.md:137`),
  `{#operator-choice-framework}` (`docs/engineering-journal/DECISIONS.md:1601`),
  `{#plugin-portfolio-groom-17-to-7}` (`docs/engineering-journal/DECISIONS.md:1031`). Today nothing
  in this repo classifies any of these anchors as "enforced by check X" versus
  "enforced only by review-lens judgment" versus "not enforced at all" — a new binding decision can
  be written down and never get any enforcement path, silently.
- **Release-surface drift persists despite `CLAUDE.md` step 6 saying it shouldn't.** This repo's
  own root `CLAUDE.md` §"Development Workflow" step 6 already states plugin-behavior changes must
  update `plugin.json`/`marketplace.json`/`CHANGELOG.md`/drift-guard tests "in the same PR" — yet
  the grounding brief's recurring-pain themes name this exact drift as still happening
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §6.3: "Release-surface drift persists
  despite CLAUDE.md step 6 — room for automation"). A documented convention with no machine check
  behind it is precisely the "binding-but-unenforced" failure shape this issue targets, and this
  convention is itself a concrete instance of it.
- **Registered checks can go stale and never fire, with nothing to notice.** The same enforcement
  gap cuts both ways: not only can a standard lack a check, a check can exist in code (a
  `check_*`-shaped validator function, e.g. in `plugins/team-execution`'s validator family
  documented in `validator-registry.md`) but never actually be wired into any invoked CI or
  runtime path, so it silently rots as dead code that looks like coverage but provides none.

## Definition of Done

Merged PR(s) delivering, at the repo root (not inside any single plugin, since the register and
manifest span the whole fleet):

1. `enforcement-registry.yaml` — one row per binding-register anchor from
   `docs/engineering-journal/DECISIONS.md`, each tagged with its enforcer:
   `check-id: <script>` (a live, invoked check), `review-lens: <lens-name>` (an existing review-lens
   catalog entry), or `operator-judgment` (explicitly acknowledged as un-automatable, with a
   one-line reason).
2. `standards-manifest.json` (+ schema) — one row per documented convention in this repo (CLAUDE.md
   step 6, the `.claude-plugin` metadata-parity rules, testing/lint/type requirements, etc.),
   classifying each as `machine-checkable | judgment | advisory` and, for `machine-checkable` rows,
   naming the live check that enforces it.
3. `plugins/saga/scripts/check_enforcement_coverage.py` (or equivalent repo-root `scripts/`
   location) — CI check that reds when an `enforcement-registry.yaml` row's `check-id` does not
   resolve to a check that CI actually invokes, or is missing entirely for a binding anchor.
4. `scripts/check_standards_manifest.py` — CI check that reds when a `standards-manifest.json` row
   marked `machine-checkable` has no resolvable, invoked check.
5. `scripts/check_coverage.py` — CI meta-guard that statically discovers every `check_*`-shaped
   validator function/script registered in the repo (enforcement registry, standards manifest,
   team-execution's validator family) and asserts each is reachable from an actually-invoked CI or
   runtime path; reds on any defined-but-never-invoked check.
6. `standards.lock` (generated from the enforcement registry + standards manifest) +
   `standards_resolver.py`, consumed by `saga:plan` and `saga:code-review` so plan/review artifacts
   cite the exact standards version used; a violation may only proceed with an explicit, expiring
   waiver entry (`waiver_id`, `anchor_or_row`, `reason`, `expires_on`).
7. Release-surface updates (checklist below) reflecting the new `saga` scripts and any
   `team-execution` validator-registry wiring touched by #5.

Verify: deleting a `check-id` referenced by an `enforcement-registry.yaml` row reds CI
(`check_enforcement_coverage.py`); marking a `standards-manifest.json` row `machine-checkable` with
a bogus check name reds CI (`check_standards_manifest.py`); adding a `check_*`-shaped function that
no invoked path calls reds CI (`check_coverage.py`); a plan/review artifact citing a missing or
stale `standards.lock` version reds the gate, and the same artifact with a waiver bearing a
not-yet-expired `expires_on` passes; a waiver with a past `expires_on` reds the gate.

### Acceptance criteria
- [ ] **AC1 (T9-F3-6, primary).** Every anchor in the binding-decision register
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §2 /
  `docs/engineering-journal/DECISIONS.md`) has a corresponding row in `enforcement-registry.yaml`
  tagged `check-id`, `review-lens`, or `operator-judgment`. Check:
  `uv run pytest tests/test_check_enforcement_coverage.py -k anchor_has_enforcer_row` → passes;
  deleting the `check-id` a row references (e.g. removing its script or unwiring it from CI) makes
  `python3 scripts/check_enforcement_coverage.py` exit non-zero, naming the anchor.
- [ ] **AC2 (T9-F4-3, facet).** Every convention documented in this repo's `CLAUDE.md` and
  `docs/sdlc-issue-drafts/` house-format conventions has a row in `standards-manifest.json`
  classified `machine-checkable | judgment | advisory`, and every `machine-checkable` row resolves
  to a live, CI-invoked check. Check:
  `uv run pytest tests/test_standards_manifest.py -k machine_row_resolves_live_check` → passes; a
  scratch row marked `machine-checkable` pointing at a nonexistent check makes
  `python3 scripts/check_standards_manifest.py` exit non-zero.
- [ ] **AC3 (T9-F4-4, facet).** Every `check_*`-shaped validator function/script registered anywhere in
  the enforcement registry, standards manifest, or team-execution's validator family
  (`plugins/team-execution/skills/team-execution/references/validator-registry.md`) is reachable
  from an actually-invoked CI or runtime path. Check:
  `uv run pytest tests/test_check_coverage.py -k defined_but_uninvoked_check_reds` → passes; adding
  a scratch `check_*` function that no invoked path calls makes `python3 scripts/check_coverage.py`
  exit non-zero, naming the orphaned function.
- [ ] **AC4 (X-codex-11, facet).** `standards.lock` names an explicit version of the combined
  enforcement registry + standards manifest; `saga:plan` and `saga:code-review` artifacts must cite
  that version, and a violation may only proceed with a waiver entry carrying an `expires_on` date.
  Check: `uv run pytest tests/test_standards_resolver.py -k stale_or_missing_version_fails` →
  passes (a plan artifact with a missing or stale `standards.lock` version fails the check);
  `uv run pytest tests/test_standards_resolver.py -k unexpired_waiver_passes_expired_fails` →
  passes (a waiver with a future `expires_on` lets the cited violation through, one with a past
  `expires_on` fails the check).

### Out-of-scope / non-goals
- This issue operates on this repo's own binding-decision register, documented conventions, and
  registered checks. It does **not** reach into infiquetra-context-library's existing
  `validate.yml`/`check_docs.py`/`context_census.py` enforcement (grounding brief §4) — those
  already exist and are out of this repo's blast radius; this issue only closes the "pull the
  library in" and "reference the library from this repo's CI" absences named in the same section,
  to the extent they concern this repo's own manifest/registry, not by rewriting the library's
  tooling.
- Does not add a new runtime-injection or blob-loading mechanism — the manifest/registry/lockfile
  are schema-validated, CI-checked artifacts, matching the org's existing
  schema-validate-in-CI + self-describing-index convention (grounding brief §4), not a new
  injected-context shape.
- Does not itself implement new domain-specific checks for every convention discovered — rows
  classified `judgment` or `advisory` are recorded as such, not force-fit into machine checks; this
  issue delivers the classification and coverage-guard machinery, not a hunt to make every
  convention machine-checkable.
- Does not change what a violation means downstream (still routes through existing plan/review
  gates) — it adds the citation-and-waiver requirement to those gates, not a new gate class beyond
  them.
- Does not touch saga's `readonly-verifier` fallback ladder or verify-agent sandboxing mechanics
  (`{#readonly-verifier-fallback-ladder-325}`) beyond registering that anchor's existing enforcer in
  the new registry — no change to the ladder itself.

## Grounding References

| Absorbed idea | Basis | Role |
|---|---|---|
| `T9-F3-6` | `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T9.json` (`dod_sketch`: "Merged machine-readable enforcement-registry.yaml (binding-register anchor tagged with enforcer: check-id \| review-lens \| operator-judgment) + check_enforcement_coverage.py; verified by deleting a referenced check id and observing the machine-checkable anchor fail CI as unenforced-drift. Tier corrected quick-win→structural: one-time triage of ~8 register decisions plus a new meta-check.") | primary |
| `T9-F4-3` | `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T9.json` (`dod_sketch`: "Merged standards-manifest.json (per-convention checkability + locus) + schema + check_standards_manifest.py asserting every machine-checkable row maps to a live check, plus code-review loading judgment rows into its lens menu; verified by CI failing when a machine row points at a missing check.") | facet |
| `T9-F4-4` | `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T9.json` (`dod_sketch`: "Merged check_coverage.py that discovers every check_* function a validator module registers and asserts it is reachable from an invoked CI path (closing the expected-invoked-vs-defined-but-uninvoked CI gap).") | facet |
| `X-codex-11` | `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T9.json` (`dod_sketch`: "Merged standards.lock generated from the context library + standards_resolver.py + plan/review checks that cite the exact standards version used and require explicit expiring waivers for violations; verified by a stale/missing standards-version in a plan failing the check and a waiver with expiry passing. tier_guess corrected sonnet/medium→structural: the score here is a backlog tier, not a model tier.") | facet |

**Binding decisions this issue builds on / must not contradict:**
- Standards/ADR-enforcement org convention (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
  §4): schema-validate-in-CI + self-describing index, not runtime-injected blobs. All four
  mechanisms (registry, manifest, coverage meta-guard, lockfile) follow this shape.
- Every binding-decision anchor named in §2 of the grounding brief (`{#external-engines-never-
  gatekeepers}`, `{#external-engine-chaperone-dispatch}`, `{#worker-cache-scheduling}`,
  `{#readonly-verifier-fallback-ladder-325}`, `{#operator-choice-framework}`,
  `{#plugin-portfolio-groom-17-to-7}`) must appear in `enforcement-registry.yaml` with a correct
  enforcer classification — this issue registers their existing enforcement state, it does not
  change any of them.
- Release-surface checklist requirement (`CLAUDE.md` §"Development Workflow" step 6): this issue's
  own release-surface checklist below is itself an instance of the convention it is building
  machinery to enforce.

## Recommended Executor Profile

- **Model:** sonnet
- **Effort:** high — *target posture: not a live team-execution dispatch knob until `pf-effort-first-class` lands; teammates inherit session tier until then*
- **Backend:** team-execution
- **External LLM:** none
- **Justification:** this is bounded, mechanical-but-careful build-out (a registry file, a schema
  + manifest, three coverage-guard scripts, a lockfile + resolver, and their tests) with real
  cross-cutting correctness risk — the coverage guards must correctly discover and classify checks
  across `saga`, `team-execution`, and `mission-control` script trees without false negatives that
  would defeat the whole point of the issue. `team-execution`'s consensus review is warranted over
  plain inline execution because a coverage-detection false negative is exactly the kind of subtle
  defect a single-pass build is prone to miss and a green test suite would not catch (the checks
  under test are themselves the thing verifying coverage). No external-LLM chaperone dispatch is
  needed; this stays within Claude-run team-execution consensus review, consistent with
  `{#external-engines-never-gatekeepers}`.

## Release-Surface Checklist

This issue adds new `saga` scripts and touches team-execution's validator-registry documentation,
so the following must update in the same PR:
- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump reflecting the new
      `check_enforcement_coverage.py`, `check_standards_manifest.py`, `check_coverage.py`,
      `standards_resolver.py` scripts and `standards.lock` consumption in `saga:plan`/
      `saga:code-review`.
- [ ] `plugins/team-execution/.claude-plugin/plugin.json` — version bump if
      `validator-registry.md` gains any coverage-guard cross-reference (needed to satisfy AC3's
      reachability check across the team-execution validator family).
- [ ] `.claude-plugin/marketplace.json` — `saga` (and `team-execution` if touched) entries'
      versions/descriptions kept in sync with their `plugin.json` bumps.
- [ ] `plugins/saga/CHANGELOG.md` — entry describing the enforcement registry, standards manifest,
      check-coverage meta-guard, and standards lockfile/resolver.
- [ ] `plugins/team-execution/CHANGELOG.md` — entry describing any validator-registry
      cross-reference addition, if touched.
- [ ] Drift-guard/version-metadata tests (this repo's existing marketplace/plugin-metadata drift
      tests) updated or confirmed still green against both version bumps.

## Files Expected to Change

- `enforcement-registry.yaml` — new, repo root.
- `standards-manifest.json` + its schema — new, repo root.
- `scripts/check_enforcement_coverage.py` — new (or `plugins/saga/scripts/` if kept saga-scoped;
  exact location resolved by `/plan`).
- `scripts/check_standards_manifest.py` — new.
- `scripts/check_coverage.py` — new.
- `standards.lock` — new, generated artifact.
- `plugins/saga/scripts/standards_resolver.py` — new.
- `plugins/saga/skills/plan/SKILL.md`, `plugins/saga/skills/code-review/SKILL.md` — updated to
  cite `standards.lock` version and require waivers for violations.
- `plugins/team-execution/skills/team-execution/references/validator-registry.md` — cross-reference
  addition so its `check_*` functions are discoverable by `check_coverage.py`.
- `tests/test_check_enforcement_coverage.py`, `tests/test_standards_manifest.py`,
  `tests/test_check_coverage.py`, `tests/test_standards_resolver.py` — new (repo-root `tests/`,
  collected by the existing pytest config).
- `plugins/saga/.claude-plugin/plugin.json`, `plugins/team-execution/.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`, `plugins/saga/CHANGELOG.md`,
  `plugins/team-execution/CHANGELOG.md` — release-surface updates.

## Tests to Add or Update

- `tests/test_check_enforcement_coverage.py::test_anchor_has_enforcer_row` — every binding-register
  anchor has an `enforcement-registry.yaml` row; a row with a deleted/unwired `check-id` reds.
- `tests/test_standards_manifest.py::test_machine_row_resolves_live_check` — every
  `machine-checkable` manifest row resolves to a live, invoked check; a bogus check name reds.
- `tests/test_check_coverage.py::test_defined_but_uninvoked_check_reds` — a `check_*`-shaped
  function with no invoked call site is detected and reds; a properly wired one passes.
- `tests/test_standards_resolver.py::test_stale_or_missing_version_fails` — a plan/review artifact
  missing or citing a stale `standards.lock` version fails the resolver check.
- `tests/test_standards_resolver.py::test_unexpired_waiver_passes_expired_fails` — a waiver with a
  future `expires_on` passes; one with a past `expires_on` fails.

### Verification
```bash
# Enforcement-registry coverage guard
uv run pytest tests/test_check_enforcement_coverage.py -v
python3 scripts/check_enforcement_coverage.py

# Standards-manifest coverage guard
uv run pytest tests/test_standards_manifest.py -v
python3 scripts/check_standards_manifest.py

# Check-coverage meta-guard (never-invoked check detection)
uv run pytest tests/test_check_coverage.py -v
python3 scripts/check_coverage.py

# Standards lockfile / resolver (versioned plan/review citation + waivers)
uv run pytest tests/test_standards_resolver.py -v

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```
Expected: all green; deleting a referenced `check-id` from `enforcement-registry.yaml`'s target
reds `check_enforcement_coverage.py`; a scratch `standards-manifest.json` row marked
`machine-checkable` with a bogus check name reds `check_standards_manifest.py`; a scratch
never-invoked `check_*` function reds `check_coverage.py`; a scratch plan artifact citing a stale
`standards.lock` version fails `standards_resolver.py` until a valid, unexpired waiver is added.

## Handoff Maturity

requirements-ready

## Suggested Next Action

Use `/plan <issue>` to create an implementation plan.

## Source Context

- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T9.json` (ids `T9-F3-6`,
  `T9-F4-3`, `T9-F4-4`, `X-codex-11`); `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
  (§2 binding-decision register, §4 standards/ADR enforcement, §6 recurring-pain theme 3)
- Source type: ideation survivors + issue-map consolidation
- Source title: Enforcement coverage: classify every convention, guard binding-but-unenforced
  decisions, fail never-invoked checks

### Context library links

_none_

### Files expected to change

- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
- `.github/workflows/ci.yml`
- `plugins/mission-control/config/generated/check_issue_contract_parity.py`
- `docs/engineering-journal/DECISIONS.md`
- `plugins/saga/scripts/check_enforcement_coverage.py`
- `scripts/check_standards_manifest.py`
- `scripts/check_coverage.py`
- `plugins/team-execution/skills/team-execution/references/validator-registry.md`

### Tests to add or update

- `tests/test_check_coverage.py`
- `tests/test_check_enforcement_coverage.py`
- `tests/test_standards_manifest.py`
- `tests/test_standards_resolver.py`

### Objective

"Enforce context-library standards at authoring time"

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/406
- Number: 406
- Created at: 2026-07-04T08:03:28.013761+00:00

