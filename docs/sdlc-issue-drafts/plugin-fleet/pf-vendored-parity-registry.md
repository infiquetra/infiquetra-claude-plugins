---
title: "capability: one vendored-artifact parity registry — contracts, provenance sidecars, drift classifier, freshness stamps"
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
slug: pf-vendored-parity-registry
---

# capability: one vendored-artifact parity registry — contracts, provenance sidecars, drift classifier, freshness stamps

### Objective

Replace the fleet's bespoke, per-artifact vendoring gates with one generic, table-driven
parity registry: a single `check_vendor_parity.py` that walks a declarative row list (source
ref, vendored path, pinned SHA256, provenance), classifies drift as cosmetic vs. semantic
instead of failing on any byte change, and stamps each row with a half-life freshness header
so staleness is caught even when bytes haven't moved. Bring `sdlc-schema.json` (currently
exempt from any parity gate) and the context-library's `llms.txt` (currently not vendored at
all) under the same registry as their first new rows, alongside the two artifacts the existing
gate already covers.

### Intent

`plugins/mission-control/config/generated/check_issue_contract_parity.py` today hard-codes a
two-row tuple, `VENDORED_ARTIFACTS` (`check_issue_contract_parity.py:40-43`:
`issue_contract_data.py`, `issue_contract_shim.py`), and `parity_errors()`
(`check_issue_contract_parity.py:51-72`) does one thing per row: recompute
`hashlib.sha256(artifact.read_bytes()).hexdigest()` (`check_issue_contract_parity.py:64`) and
compare it to a pinned `.sha256` sidecar. Any byte difference — a reformatted docstring, a
renamed comment, a real contract change — fails the gate identically. There is no third row
for anything else vendored in this repo, and no mechanism to add one without hand-editing this
module.

Two artifacts prove the gap this issue closes:

- `plugins/mission-control/config/sdlc-schema.json` (35,275 bytes) is a vendored copy of
  `infiquetra-sdlc`'s schema, but it is resolved at runtime through
  `_resolve_sdlc_schema()` (`plugins/mission-control/scripts/sdlc_manager.py:291-320`) via a
  GitHub-main → vendored → local-fallback chain, with no SHA256 pin and no parity check at
  all — it is structurally exempt from the one gate this repo does have, despite following
  "the vendoring pattern the plugin already uses" per the existing gate's own docstring
  (`check_issue_contract_parity.py:6`).
- `infiquetra-context-library`'s `llms.txt` (1,463 bytes, confirmed by direct read of
  `infiquetra-context-library/llms.txt`) is not vendored into this repo at all — no copy, no
  pin, nothing a consumer here can check for drift against the library's live index.

Separately, the drift the existing gate does catch is over-broad: `hashlib.sha256` on raw
bytes cannot distinguish a reformatted comment from a change to `issue_contract_shim.py`'s
`__all__` export tuple (`issue_contract_shim.py:89-100`), even though the latter is
plain-data and value-comparable — cosmetic and semantic drift are conflated into one failure
mode today. And even a byte-identical vendored copy can silently go stale relative to its
upstream source with no re-derivation ever having happened; nothing today records *when* an
artifact was last verified against its source, or forces periodic re-proof.

This issue is the machine six separate ideation survivors converged on: a registry of
`(source ref, vendored path, pinned SHA256, provenance)` rows driving one parametrized gate,
plus a cosmetic-vs-semantic classifier and a half-life freshness stamp layered on top of the
same rows — not six separate mechanisms.

## Definition of Done

One generic, registry-driven `check_vendor_parity.py` replaces the hard-coded
`check_issue_contract_parity.py` gate; `sdlc-schema.json` and `llms.txt` are onboarded as new
registry rows alongside the two artifacts the existing gate already covers; a cosmetic-vs-
semantic drift classifier and a `--stamp` half-life freshness header exist on every row; and
adding a future registry row requires no code change — only registry entries plus sidecars.

### Acceptance criteria
- [ ] **Covers registry primitive.** A declarative `vendored-contracts.toml` (or equivalent
      structured registry file) lists every vendored artifact as one row: source ref, vendored
      path, pinned SHA256 sidecar path, provenance sidecar path. `plugins/mission-control/config/generated/check_vendor_parity.py`
      replaces `check_issue_contract_parity.py` (or absorbs it) and iterates the registry rather
      than a hard-coded tuple. Check: `uv run python plugins/mission-control/config/generated/check_vendor_parity.py`
      exits 0 against the committed registry with no code change required to add a new row.
- [ ] **Covers `T14-F4-1`.** A one-byte hand-edit to any single registry row's vendored artifact
      fails the gate for that row, and only that row. Check:
      `uv run pytest tests/test_vendor_parity_registry.py -k parametrized_byte_edit_fails` passes,
      parametrized over every row in the registry (new rows added to the registry are covered
      automatically, with no test-file edit).
- [ ] **Covers `T14-F1-2`.** `sdlc-schema.json` is a registry row with its own `.sha256`
      sidecar. A one-byte edit to `plugins/mission-control/config/sdlc-schema.json` produces a
      non-empty `parity_errors()` (or the renamed equivalent) result. Check:
      `uv run pytest tests/test_vendor_parity_registry.py -k sdlc_schema_drift_detected` passes.
- [ ] **Covers `T9-F4-2`.** `infiquetra-context-library`'s `llms.txt` is vendored to
      `plugins/mission-control/config/generated/llms.txt` with a pinned `.sha256` sidecar and a
      registry row. Check: `uv run pytest tests/test_vendor_parity_registry.py -k llms_txt_row_present`
      passes and asserts the vendored copy is byte-identical to its pinned hash.
- [ ] **Covers `T14-F1-6`.** `classify_drift()` distinguishes cosmetic from semantic drift on a
      registry row. Check: `uv run pytest tests/test_vendor_parity_registry.py -k comment_only_classifies_cosmetic`
      passes against a comment-only fixture diff, and
      `uv run pytest tests/test_vendor_parity_registry.py -k header_set_change_classifies_semantic`
      passes against a fixture that changes `issue_contract_shim.py`'s `__all__` tuple contents.
- [ ] **Covers `T14-F1-8`.** Every registry row has a `.provenance.json` sidecar recording the
      upstream source commit/ref that produced the vendored artifact, and `check_vendor_parity.py`
      prints the recorded source per artifact on every run (pass or fail). Check:
      `uv run python plugins/mission-control/config/generated/check_vendor_parity.py --verbose`
      output contains one recorded-source line per registry row, and
      `uv run pytest tests/test_vendor_parity_registry.py -k provenance_sidecar_well_formed` passes.
- [ ] **Covers `T14-F5-1`.** A `--stamp` CLI mode writes a half-life freshness header (stamped
      timestamp + re-derivation deadline) per row. Back-dating a stamp past its half-life fails
      CI; re-running `--stamp` to re-derive it turns the check green again. Check:
      `uv run pytest tests/test_contract_mirror_freshness.py -k backdated_stamp_reds_ci` and
      `uv run pytest tests/test_contract_mirror_freshness.py -k restamp_greens_ci` both pass.
- [ ] **Covers `G-hybrids-6`.** The registry is genuinely generic: adding the `sdlc-schema.json`
      row and the `llms.txt` row required only new registry entries plus their sidecars — no
      change to `check_vendor_parity.py`'s logic. Check: `git log -p` on the merge commit shows
      registry-file and sidecar additions only, with no corresponding edit to the parity-check
      module's control flow for the two new rows.

### Out-of-scope / non-goals
- Do NOT build the fleet-local, census-checked `llms.txt` standards index for
  `infiquetra-claude-plugins`'s own 8 plugins — that is a *different* `llms.txt` (this repo's
  own index, not yet created) and is tracked separately in
  `pf-standards-index-machine-contract`. This issue vendors the *context-library's* existing
  `llms.txt` as a read-only pinned artifact; it does not author or maintain a new index.
- Do NOT abolish the hand-copied `validate_card_body` shim or migrate consumers onto a
  callable contract surface — that is `pf-abolish-contract-mirrors`'s scope (behavioral
  parity via a real-card corpus), a distinct and larger structural change. This issue only
  generalizes and extends the existing byte/provenance/freshness parity mechanism.
- Do NOT add release-surface tri-lock rows (per-plugin `plugin.json` /
  `marketplace.json` / `CHANGELOG.md` version-consistency checks) to this registry in v1. The
  hybrid rationale names this as a future row family; `G-hybrids-6`'s own `dod_sketch` scopes
  v1 to `sdlc-schema.json` + `llms.txt` initial rows only, and `tests/test_release_triad.py`
  already covers release-surface drift by a separate mechanism — folding it into this registry
  is a distinct follow-on, not this issue.
- Do NOT build a producer-push notification system that opens PRs against consumers when an
  upstream source changes — this registry is pull/CI-checked only (consumer runs the gate),
  matching the existing gate's design.
- Do NOT change `_resolve_sdlc_schema()`'s runtime GitHub-main → vendored → local-fallback
  resolution order in `sdlc_manager.py` — this issue only adds a parity *check* against the
  vendored copy; it does not touch which copy is read at runtime.

### Files expected to change

- `plugins/mission-control/config/generated/vendored-contracts.toml` (new) — the declarative
  registry: one row per vendored artifact (source ref, vendored path, `.sha256` sidecar path,
  `.provenance.json` sidecar path).
- `plugins/mission-control/config/generated/check_vendor_parity.py` (new, replaces
  `check_issue_contract_parity.py`) — generic, registry-driven parity gate; owns
  `parity_errors()`, `classify_drift()`, and the `--stamp` / `--verbose` CLI modes.
- `plugins/mission-control/config/generated/check_issue_contract_parity.py` — retired or
  reduced to a thin backward-compatible wrapper calling into `check_vendor_parity.py`, per
  the repo's existing pattern of not breaking direct-invocation call sites without a
  transition.
- `plugins/mission-control/config/sdlc-schema.json.sha256` (new) — pinned hash sidecar.
- `plugins/mission-control/config/sdlc-schema.json.provenance.json` (new) — provenance sidecar.
- `plugins/mission-control/config/generated/llms.txt` (new) — vendored copy of
  `infiquetra-context-library/llms.txt`.
- `plugins/mission-control/config/generated/llms.txt.sha256` (new) and
  `llms.txt.provenance.json` (new).
- `plugins/mission-control/config/generated/issue_contract_data.py.provenance.json` (new) and
  `issue_contract_shim.py.provenance.json` (new) — provenance sidecars for the two artifacts
  the existing gate already covers, brought up to the new contract.
- `plugins/mission-control/tests/test_issue_contract_parity.py` — updated to exercise the new
  registry-driven gate (independent hard-coded hash oracles preserved per the file's existing
  two-layer-defence pattern) or superseded by `tests/test_vendor_parity_registry.py`.
- `tests/test_vendor_parity_registry.py` (new) — parametrized-over-registry-rows parity tests,
  drift classifier tests, provenance sidecar tests.
- `tests/test_contract_mirror_freshness.py` (new) — half-life stamp tests.
- `plugins/mission-control/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
  `plugins/mission-control/CHANGELOG.md` — release-surface updates (see checklist below).

### Tests to add or update

- `tests/test_vendor_parity_registry.py::test_parametrized_byte_edit_fails` — parametrized over
  every registry row; a one-byte edit to that row's vendored artifact fails only that row.
- `tests/test_vendor_parity_registry.py::test_sdlc_schema_drift_detected` — `sdlc-schema.json`
  edit produces a non-empty parity error.
- `tests/test_vendor_parity_registry.py::test_llms_txt_row_present` — vendored `llms.txt` row
  exists and matches its pinned hash.
- `tests/test_vendor_parity_registry.py::test_comment_only_classifies_cosmetic` — comment-only
  fixture diff classifies `cosmetic`.
- `tests/test_vendor_parity_registry.py::test_header_set_change_classifies_semantic` —
  `__all__`-tuple-changing fixture diff classifies `semantic`.
- `tests/test_vendor_parity_registry.py::test_provenance_sidecar_well_formed` — every registry
  row's `.provenance.json` sidecar parses and has required keys (source repo, ref/commit,
  vendored-at timestamp).
- `tests/test_contract_mirror_freshness.py::test_backdated_stamp_reds_ci` — a stamp header
  older than its half-life fails the check.
- `tests/test_contract_mirror_freshness.py::test_restamp_greens_ci` — re-running `--stamp`
  clears the failure.

### Verification

```bash
# New registry-driven parity + freshness tests
uv run pytest tests/test_vendor_parity_registry.py tests/test_contract_mirror_freshness.py -v

# The gate itself, run directly (CI parity) — must exit 0 against the committed registry
uv run python plugins/mission-control/config/generated/check_vendor_parity.py

# Provenance is printed per artifact
uv run python plugins/mission-control/config/generated/check_vendor_parity.py --verbose

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . \
  && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all green against the committed registry; deliberately mutated fixtures (byte edit,
comment-only edit, `__all__`-tuple edit, back-dated stamp) fail only their corresponding
targeted test, verified manually as part of implementation, not part of the standing suite.

### Release-surface checklist

This issue changes `mission-control`'s runtime behavior (retires/wraps
`check_issue_contract_parity.py`, adds new vendored artifacts and a new CLI). Confirm on merge:

- [ ] `plugins/mission-control/.claude-plugin/plugin.json` — version bump reflecting the new
  generic parity gate and additional vendored rows.
- [ ] `.claude-plugin/marketplace.json` — entry synced to the bumped `plugin.json` version.
- [ ] `plugins/mission-control/CHANGELOG.md` — entry documenting the registry-driven gate,
  the two new rows (`sdlc-schema.json`, `llms.txt`), the drift classifier, and the freshness
  stamp.
- [ ] `tests/test_release_triad.py` (the repo's existing version/metadata drift-guard test)
  passes against the bumped version and updated CHANGELOG.
- [ ] If `check_issue_contract_parity.py` is kept as a thin wrapper rather than deleted,
  confirm no existing direct-invocation call site (CI workflow, doc reference) breaks.

## Grounding References

- Absorbed idea `G-hybrids-6` (role: primary) — "One vendored-artifact parity registry
  covering contracts, the standards index, and release surfaces." Parents:
  `T14-F4-1`, `T9-F4-2`, `T14-F4-3`, `T11-F1-8`. Basis: source-of-truth registry pattern
  the fleet's four existing per-artifact gates already imply but never generalized.
  DoD sketch: "Merged vendored-artifact registry (YAML) + one parametrized CI check, with
  initial rows for `sdlc-schema.json`, `llms.txt`, and per-plugin release-surface tri-locks;
  verified a red-test per row family catching injected drift." (Note: this issue's v1 scope
  is the registry + the `sdlc-schema.json`/`llms.txt` rows only — the release-surface
  tri-lock row family is explicitly deferred; see Out-of-scope.)
- Absorbed idea `T14-F4-1` (facet) — "Generic vendored-contract parity primitive + registry
  (one gate, N contracts)." Basis: `check_issue_contract_parity.py`'s hard-coded
  `VENDORED_ARTIFACTS` tuple (`check_issue_contract_parity.py:40-43`) as the concrete
  instance of the bespoke-gate-per-artifact anti-pattern this facet generalizes. DoD sketch:
  "Merged `vendored-contracts.toml` + generic `check_vendor_parity.py` replacing the bespoke
  gate + `sdlc-schema.json.sha256` + parametrized test; verified every registry row's byte
  edit fails the gate."
- Absorbed idea `T14-F1-2` (facet) — "Bring `sdlc-schema.json` under the parity umbrella it is
  currently exempt from." Basis: `sdlc-schema.json` is resolved via `_resolve_sdlc_schema()`
  (`plugins/mission-control/scripts/sdlc_manager.py:291-320`, GitHub-main → vendored →
  local-fallback) with no SHA256 pin — structurally exempt from the one gate this repo has.
  DoD sketch: "Merged `sdlc-schema.json.sha256` + extended `VENDORED_ARTIFACTS` + test;
  verified by a one-byte schema edit making `parity_errors()` non-empty."
- Absorbed idea `T14-F1-8` (facet) — "Provenance sidecars: record which upstream commit
  produced each vendored artifact." Basis: the existing gate proves byte-parity but never
  records *which* upstream commit was last vendored — no consumer-side answer to "what
  source state does this pin correspond to." DoD sketch: "Merged `.provenance.json` sidecars
  + gate prints provenance + generator emits them; verified gate prints recorded source commit
  and a test asserts well-formed sidecar per artifact."
- Absorbed idea `T14-F1-6` (facet) — "Cosmetic-vs-substantive drift classifier to kill false
  re-vendor churn." Basis: `check_issue_contract_parity.py:64` hashes raw bytes
  (`hashlib.sha256(artifact.read_bytes())`); `issue_contract_shim.py:89-100`'s `__all__`
  exports are pure tuples/dicts, making value-level comparison feasible — byte drift and
  semantic drift are conflated today. DoD sketch: "Merged `classify_drift()` + CLI flag + unit
  test; verified a comment-only fixture reports 'cosmetic' and a header-set change reports
  'semantic'."
- Absorbed idea `T14-F5-1` (facet) — "mRNA half-life: give every vendored contract mirror a
  self-expiring transcript." Basis (external): periodic re-proof-of-freshness pattern applied
  to vendored artifacts that could be byte-identical yet stale relative to an upstream that
  moved without a corresponding re-vendor ever having been triggered. DoD sketch: "Merged
  `--stamp` half-life header emitter + `test_contract_mirror_freshness.py`; verified
  back-dating a stamp turns CI red and re-derivation turns it green."
- Absorbed idea `T9-F4-2` (facet) — "Vendor the 1.4KB `llms.txt` as a SHA-pinned artifact on
  the existing parity registry." Basis: `infiquetra-context-library/llms.txt` (confirmed 1,463
  bytes) is the library's whole-injectable standards index but is not vendored into this repo
  at all, so no consumer-side check can catch it going stale. DoD sketch: "Merged
  `plugins/mission-control/config/generated/llms.txt` + `.sha256`, one `VENDORED_ARTIFACTS`
  tuple entry in `check_issue_contract_parity.py`, and a `CLAUDE.md` step-6 sync note; verified
  by the existing CI parity job failing on a one-byte edit and passing on the pinned copy."
- Grounding brief `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §3 ("Consumer-side
  signal"), finding 1: contract-mirror drift as a recorded, live incident class (the same
  disease this registry generalizes a defense against, distinct from `pf-abolish-contract-mirrors`'s
  behavioral-parity fix).
- Grounding brief `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §4 ("Standards/ADR
  enforcement"): confirms `infiquetra-context-library` already runs
  `context_census.py --check` to keep its own `llms.txt` honest, and that `llms.txt` is the
  library's whole-injectable (~1-2KB) consumption artifact — the artifact this issue vendors
  a pinned copy of.

### Executor profile

- **Model:** sonnet
- **Effort:** high — *target posture: not a live team-execution dispatch knob until `pf-effort-first-class` lands; teammates inherit session tier until then*
- **Backend:** team-execution
- **External LLM:** none
- **Justification:** mechanical-but-structural generalization of an existing, well-understood
  gate (registry-driven refactor + two new rows + a classifier + a freshness stamp) with a
  clear done-state and no open-ended design surface; does not warrant opus-tier judgment or
  any external-engine involvement.

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

### Source context

- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T14.json` (ids `G-hybrids-6`,
  `T14-F4-1`, `T14-F1-2`, `T14-F1-8`, `T14-F1-6`, `T14-F5-1`),
  `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T9.json` (id `T9-F4-2`)
- Source type: ideation-survivor-consolidation
- Source title: One vendored-artifact parity registry covering contracts, the standards index,
  and release surfaces (issue-map-final.json#pf-vendored-parity-registry)

### Context library links

_none_

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/421
- Number: 421
- Created at: 2026-07-04T08:08:13.473452+00:00

