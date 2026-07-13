# Implementation Plan — Issue #459: Earned ratings — dispatch/benchmark evidence drives retro-gated engine-registry calibration

**Repo:** `infiquetra/infiquetra-claude-plugins` · **Planned against:** `origin/main` @ `2bdc168` (2026-07-13) · **One reviewable PR** · **Binding constraint:** `{#external-engines-never-gatekeepers}` (#283) — nothing writes `engine-registry.yaml` autonomously; every signal terminates in a human-applied proposal.

---

## 0. Evidence-anchor audit (issue vs current main)

Every anchor in the issue was re-verified at `2bdc168`. Several moved; one premise is now materially different.

| Issue anchor | Status at `2bdc168` |
|---|---|
| `engine_registry.py:22-24` `RATINGS`/`_RATING_SCORE` | **Moved → `:28-29`** (sort-key use at `:747`, `:768`) |
| `engine_registry.py:174-176` `EngineEntry.last_validated` | **Moved → `:362`** (parse at `:413-414`, `:433`) |
| `engine_registry.py:349-350` `by_capability` sort | **Moved** — `by_capability` at `:607`; ranking now lives in `ranked_candidates` (`:616`) + `_capability_sort_key` (`:745-747`) |
| `engine_registry.py:377-385` `Registry.stale()` | **Moved → `:713-720`** and **signature changed**: `stale(entry, known_revision_dates)` compares `last_validated` against per-model-identity release dates from `references/model-releases.yaml`, not a plain cutoff |
| `engine_resolver.py:178-214` / `:346-350` | **Moved** — `resolve` `:330`, `_resolve_capability` `:452`, `_resolve_entry` `:572`, `_capability_fit_failure` `:828` |
| `outcome_store.py:408` `append_ledger`, no hash | **Still accurate** (append-only, un-chained — confirmed) |
| `outcome_costs.py:1-23` leaf-produced-fact pattern | Still accurate (`record_cost`/`rollup`) |
| "No per-call dispatch ledger exists anywhere" | **NO LONGER TRUE.** The wave-2 ledger spine landed as `plugins/saga/scripts/run_ledger.py` (#401): an **append-only, hash-chained** (`prev_hash`→`this_hash`, SHA-256) run-fact ledger at `<git-common-dir>/saga-run-facts/run-facts.jsonl` with `verify_chain()` (mutation / middle-deletion / reorder detection), `append_fact`, `append_fact_atomic`, `read_snapshot`, `rollup`, `last_n_prior`. `engine_dispatch.py:1105-1153` (`_record_advisory_facts`) already appends an `engine` fact per real advisory dispatch (engine, variant, status, cost, latency_seconds, tokens, proof fields, economics). `reconcile.py:708-757` already appends hash-chained `reconciliation` facts. `tests/test_engine_dispatch_ledger.py` and `tests/test_run_ledger.py` already exist. |
| `/retro` SKILL.md has no registry-calibration content | Still true — but SKILL.md now has the exact house pattern to extend: read-only evidence passes **1.6–1.10** (each with a zero-data contract) and propose-diff-and-wait passes **5(a)–5(e)**, with `tier_efficacy.py` (#402) as the canonical "proposal engine that never writes" precedent |
| `evidence_ledger.py` (#398) | New since issue: committed per-saga hash-chained custody log — precedent for chain-verify-before-trust reads |

**Consequence for R1:** we do **not** create `engine_dispatch_ledger.py`. Building a second hash-chained ledger beside `run_ledger.py` would fork the "one ledger, six consumers" premise the issue itself demands. R1 becomes a **gap-closing extension** of the landed spine: the engine fact today carries **no `capability`, no claimed rating, and no `execution_id`**, so nothing can join a dispatch fact to a registry **cell** `(engine_key, capability)` or to a reconciliation. That join is the entire substrate for R3–R6. `verify_ledger` is satisfied by the existing `run_ledger.verify_chain`; AE1 is proven **through the dispatch write path** in the already-named test file.

---

## 1. Architecture at a glance

```
                      ┌──────────────────────────────────────────────────────┐
                      │  run_ledger.py  (EXISTS — hash-chained, verify_chain) │
  engine_dispatch ───►│  engine facts       + capability/rating_claimed/     │
   (R1: extend)       │                       execution_id   (NEW fields)    │
  reconcile ─────────►│  reconciliation facts + member_index (NEW, optional) │
  engine_benchmark ──►│  benchmark facts     (NEW kind)                      │
                      └───────────────┬──────────────────────────────────────┘
                                      │ derive-on-read, chain-verified first
        ┌──────────────┬──────────────┼──────────────┬─────────────────┐
        ▼              ▼              ▼              ▼                 │
 engine_benchmark  engine_stale   capability_elo  provider_control    │
 (R2, active)      _report (R3)   (R4)            _chart (R5)         │
        └──────────────┴──────┬───────┴──────────────┘                 │
                              ▼                                        │
                   engine_calibration.py (R6 aggregator)               │
                   registry_calibration_proposal.v1                    │
                              │                                        ▼
                              ▼                          CalibrationSignals (opt-in)
              /retro Phase 1.11 (read) + Phase 5(f)      → ranked_candidates /
              (propose-diff-and-wait; HUMAN applies)       resolve(calibration=…)
                              │                            reorder-within-rating-band only
                              ▼
              engine-registry.yaml  ◄── manual human edit ONLY
```

One write seam into the registry: a human, after a `/retro` Phase-5(f) proposal. The runtime Elo/SPC influence (R4/R5) reorders candidates **within** an authored rating band and deprioritizes drift-flagged providers — it never rewrites a rating, never excludes a provider, and is opt-in (`calibration=None` everywhere today ⇒ byte-identical behavior).

---

## 2. Module-by-module design

### 2.1 R1 — Ledger gap closure (changed files, no new module)

**`plugins/saga/scripts/engine_resolver.py`**
- `Resolution` (frozen dataclass, `:40`) gains two **additive, defaulted** fields (same posture as `invocation`'s R11 note):
  - `capability: str | None = None` — the capability the request resolved through (`None` for explicit-engine requests and role members).
  - `rating_claimed: str | None = None` — `entry.capability_profile[capability]["rating"]` **at resolution time** (so historical facts stay joinable even after the registry is later hand-edited).
- Threading: `_resolve_capability` (`:452`) passes `capability` through `_resolve_entry` → `_resolution_from_entry`, and sets both fields; `_fallback_resolution` and `_no_fit_resolution` (which already have `capability` in scope) set `capability` with `rating_claimed=None`. Explicit-engine path (`_entry_for_engine_request` → `_resolve_entry`) leaves both `None`.
- The memoized `_CapabilityDecision` stores the *entry*, not the Resolution — no cache-shape change needed for this part.

**`plugins/saga/scripts/engine_dispatch.py`**
- `_record_advisory_facts` (`:1105`) gains a `resolution: Any | None = None` keyword; `dispatch()` (which has `resolution` in scope at all three call sites: `:600`, `:619`, `:657`) passes it. The engine fact gains three **string** fields (non-numeric ⇒ `run_ledger.rollup`'s `_numeric_fields` aggregation is untouched):
  - `capability`: `resolution.capability or ""`
  - `rating_claimed`: `resolution.rating_claimed or ""`
  - `execution_id`: `evidence.execution_id or ""` (the reconciliation join key — `reconcile` facts already carry `execution_id`)
- The `bridge_run_key` dedup guard (`:1121-1125`) is untouched — new fields ride inside the same single append.

**`plugins/saga/scripts/run_ledger.py`**
- `FACT_KINDS` (`:44`) gains `"benchmark"` (six kinds). Nothing else changes — chaining, locking, verification are already correct.

**`plugins/saga/scripts/reconcile.py`** (Elo attribution substrate)
- `append_reconciliation_fact` (`:708`) gains optional `member_index: Mapping[str, Sequence[str]] | None = None` — `{source_finding_id: [engine_key, …]}`. `dispatch_advisory_panel` (`engine_dispatch.py:764-777`) builds it from the `gathered` `PanelMemberEvidence` (which already carries `member_ids` per finding — `reconcile.py:556-563`) and passes it on both RECONCILE and APPLY appends.
- `_validated_reconciliation_facts` (`:765`) currently enforces **exact** field-set equality (`:776`). Relax to: `required ⊆ set(fact) ⊆ required | {"member_index"}`; when present, validate `member_index` is a mapping whose keys ⊆ the fact's `source_finding_ids` and whose values are non-empty lists of id-shaped strings. Old facts (no `member_index`) remain valid; identity/transition logic (`result_hash` over the ReconciliationResult) is untouched because `member_index` is fact metadata, not part of `canonical_result_hash`.

### 2.2 R3 — `plugins/saga/scripts/engine_stale_report.py` (new)

Pure derive-on-read reducer, house style (module docstring states the contract; no I/O at import; `sys.path` shim; lazy heavy imports).

- `stale_report(registry: Registry, ledger: RunLedger, *, now: date, min_samples: int = 3, failure_share_floor: float = 0.5) -> dict` — verifies the chain first via `run_ledger.read_snapshot` (a chain break **raises**, per the 1.9 precedent: visible evidence failure, never silently skipped), then for every registry cell (each `entry.key` × each key of `entry.capability_profile`):
  - Select `engine` + `benchmark` facts with matching `(engine, variant, capability)` and `at` **strictly newer than `entry.last_validated`** (the join the issue names).
  - **`contradicted`**: any joined `benchmark` fact with `contradicts: true`, **or** ≥ `min_samples` joined dispatch facts with failure share ≥ `failure_share_floor` (failure = `status` not ok, or `proof_integrity_status == "failed"`).
  - **`corroborated`**: not contradicted, and ≥ 1 joined fact with an ok outcome. Carries `latest_corroborated_at` (the newest ok `at`) — the R6 `last_validated`-bump source.
  - **`unexercised`**: no joined facts.
- Output shape:

```json
{"schema": "engine_stale_report.v1", "generated_at": "...", "chain_ok": true,
 "cells": [{"engine_key": "codex/gpt-5.6-sol-high", "engine_id": "codex",
   "variant": "gpt-5.6-sol-high", "capability": "adversarial-review",
   "verdict": "corroborated", "last_validated": "2026-06-27",
   "evidence": {"ok_count": 4, "fail_count": 0, "benchmark_contradictions": 0,
                "latest_corroborated_at": "2026-07-10T..."}}]}
```

- Zero-data contract: an empty/absent ledger yields every cell `unexercised` with a top-level `"note": "no dispatch evidence yet"` — never a fabricated verdict.
- CLI: `python3 engine_stale_report.py report --root . [--registry <path>] [--json]`.

### 2.3 R4 — `plugins/saga/scripts/capability_elo.py` (new)

Derive-on-read Elo; **no persisted score file** (run_ledger's "no committed summary" discipline — scores are a fold over match history on each read).

- Constants: `ELO_BASE = 1200.0`, `K = 32.0`.
- `Match` dataclass: `capability: str`, `winner: str`, `loser: str`, `draw: bool`, `at: str` (winner/loser are `engine_key`s).
- `expected(r_a, r_b) -> float` and `apply_match(scores, match) -> None` — textbook Elo, pure.
- `derive_matches(reconciliation_facts) -> list[Match]`:
  - Dedupe by `reconciliation_id`, use the RECONCILE-action fact.
  - Require `member_index` with ≥ 2 distinct members (head-to-head evidence only; solo reconciliations produce no match — no synthetic opponents, no fabricated signal).
  - Per member: attributed non-empty findings (skip `panel-empty:*` ids); survival share = `#status==reconciled / #attributed`; a member with zero attributed non-empty findings scores 0.0.
  - Emit one pairwise `Match` per member pair: strictly higher share wins; equal shares ⇒ `draw`.
  - Capability from an explicit `_INTENT_CAPABILITY` map over `reconcile.RECIPE_REGISTRY` keys (`tier_palette.ENGINE_INTENTS`), e.g. `"second-opinion" → "second-opinion"`; intents with no clean capability mapping are **skipped and counted** in an `unattributed_matches` stat (zero-data honesty, never guessed).
- `scores(ledger) -> dict[tuple[str, str], float]` — chain-verify, `reconcile.read_reconciliation_facts`, derive, fold chronologically (`at`, then ledger order). Keyed `(engine_key, capability)`.
- `signals(ledger, registry, *, min_matches: int = 5) -> list[dict]` — cells where the Elo ordering between two providers **inverts** their authored-rating ordering (or diverges within a shared band by > 1 K-step) with ≥ `min_matches` matches: the R6 proposal candidates. Elo alone proposes **`revalidate`** with a direction, never a concrete rating value (a rating value only comes from measured benchmark evidence, R2).
- **Production accrual note (stated in the module docstring):** panel member attribution only accrues after the `member_index` extension (2.1) ships; until real panels run, `scores` legitimately reports no data — the same "signal accrues over time" posture as Phase 1.6/1.10.

### 2.4 R5 — `plugins/saga/scripts/provider_control_chart.py` (new)

XmR (individuals + moving range) control chart — *shift detection*, explicitly distinct from R3's staleness join.

- `control_chart(series: list[float], *, baseline_n: int = 12) -> ChartVerdict`:
  - `< baseline_n + 1` points ⇒ `status="no-data"` (never a flag from thin evidence).
  - Centerline = mean of first `baseline_n`; `mR̄` = mean moving range of baseline; `UCL/LCL = centerline ± 2.66 × mR̄` (LCL floored at 0).
  - Post-baseline points evaluated with two Western-Electric-style rules: **rule 1** — any point beyond a limit; **rule 4** — 8 consecutive points on one side of the centerline. Either ⇒ `status="out-of-control"` with `rule` and `breach_indices`.
- `ChartVerdict` dataclass: `status: str` (`no-data|in-control|out-of-control`), `centerline`, `ucl`, `lcl`, `breach_indices: tuple[int, ...]`, `rule: str`.
- `provider_flags(ledger, *, baseline_n=12) -> dict[str, dict[str, ChartVerdict]]` — chain-verify; group `engine` facts by `engine_id` (provider level, per the issue), ordered by `at`; two metric series per provider: `cost`, `latency_seconds`; **values ≤ 0 are excluded as unmeasured** (`engine_dispatch._num` writes `0.0` for absent metrics — a zero is "no data", never a real observation, per the U8 honesty stance).
- `drift_flagged(ledger) -> frozenset[str]` — providers with any `out-of-control` metric; this is the resolution-time deprioritization input and the R6 `revalidate` source.
- CLI: `python3 provider_control_chart.py report --root . [--json]`.

### 2.5 R2 — `plugins/saga/scripts/engine_benchmark.py` (new) + suite fixture + gate doc

**`plugins/saga/references/benchmark-suite.yaml`** (new) — the fixed per-capability eval suite:

```yaml
schema: benchmark_suite.v1
suites:
  - suite_id: adversarial-review-v1     # versioned: editing probes REQUIRES a new suite_id
    capability: adversarial-review
    thresholds: {STRONG: 0.8, MODERATE: 0.5}   # pass-share floors; below MODERATE -> WEAK
    probes:
      - id: ar-001
        prompt: "…snippet with a planted off-by-one…Identify the bug and name the line."
        grader: {kind: regex, pattern: "(?i)off.by.one|line\\s*7"}
  - suite_id: code-generation-v1
    capability: code-generation
    thresholds: {STRONG: 0.8, MODERATE: 0.5}
    probes:
      - id: cg-001
        prompt: "Write a Python function slugify(s) …"
        grader: {kind: contains, value: "def slugify("}
```

Seed 3–5 probes for each of two capabilities (`adversarial-review`, `code-generation`). Graders are **deterministic string checks only** (`contains`, `regex`, `json-parses`) — no LLM-graded scoring, so the harness never makes an external engine a judge of anything (consistent with #283; nuanced judgment stays with the human reading the `/retro` proposal).

**`engine_benchmark.py`**:
- `load_suite(path) -> Suite` with strict validation (unknown grader kind, missing thresholds, non-monotone thresholds ⇒ error).
- `measured_rating(passed, total, thresholds) -> str` — pass share vs floors ⇒ `WEAK|MODERATE|STRONG`.
- `run_suite(entry: EngineEntry, suite, runner: Callable[[EngineEntry, str], str], *, ledger=None, subplot_id="", at="") -> BenchmarkResult` — runs every probe through the **injected** runner, grades deterministically, and (when `ledger`+`subplot_id`+`at` supplied — same telemetry-only trio as `dispatch`) appends one `benchmark` fact:

```json
{"kind": "benchmark", "schema": "run_fact.v1", "subplot_id": "...", "at": "...",
 "engine": "codex", "variant": "gpt-5.6-sol-high", "capability": "adversarial-review",
 "suite_id": "adversarial-review-v1", "probes_total": 4, "probes_passed": 1,
 "measured_rating": "WEAK", "claimed_rating": "STRONG", "contradicts": true}
```

- `proposal(result, entry) -> dict | None` — `registry_calibration_proposal.v1` **cell** (see 2.6) when `measured != claimed`, else `None`. **No code path in this module opens the registry for writing** — it takes an already-loaded `Registry`/`EngineEntry` and returns dicts.
- CLI: `python3 engine_benchmark.py run --engine <engine_id/variant> --capability <cap> [--suite <path>] [--runner-cmd '<shell cmd, prompt on stdin>'] [--ledger] [--json]`. The live path is **operator-invoked** via `--runner-cmd` (e.g. a one-shot `codex exec` / bridge invocation) — real query, real engine, human-triggered; this PR deliberately does **not** build a scheduled or autonomous benchmark loop (issue non-goal: no standing calibration ceremony).

**`plugins/saga/references/benchmark-loop.md`** (new) — documents the propose-not-commit gate (T2-F1-7 `dod_sketch`): how to run the harness, suite versioning rules (`suite_id` immutability), threshold semantics, how a contradiction becomes a `/retro` Phase-5(f) proposal, and the hard rule that a benchmark result never edits the registry.

### 2.6 R6 — `plugins/saga/scripts/engine_calibration.py` (new): the aggregator + the runtime signals object

Mirrors `tier_efficacy.py`: a proposal engine `/retro` reads (Phase 1.11) and proposes from (Phase 5(f)), that **never writes**.

- `CalibrationSignals` (frozen dataclass): `elo: Mapping[tuple[str, str], float]`, `drift_flagged: frozenset[str]`, plus `calibration_fingerprint(signals | None) -> str` (sha256 over canonical JSON; `""` for `None`) for memo keying.
- `load_calibration(ledger, *, min_matches=5, baseline_n=12) -> CalibrationSignals` — one chain-verified read producing both runtime signals (compute once per run, thread explicitly; **no I/O inside the resolver hot path unless the caller opts in**).
- `report(registry, ledger, *, now, benchmark_results: list[dict] | None = None) -> dict` — verify chain (break ⇒ raise, visible failure); run stale report, Elo `signals`, `provider_flags`; read `benchmark` facts from the ledger (plus any freshly-passed results); aggregate into:

```json
{"schema": "registry_calibration_proposal.v1", "generated_at": "...",
 "status": "proposal",            // or the explicit zero-data "no-proposal"
 "approval_required": true,        // ALWAYS true — a proposal is never an authorization
 "cells": [
   {"engine_key": "codex/gpt-5.6-sol-high", "capability": "adversarial-review",
    "action": "rating-change",     // rating-change | revalidate | last-validated-bump
    "current": {"rating": "STRONG", "last_validated": "2026-06-27"},
    "proposed": {"rating": "WEAK",  "last_validated": "2026-07-13"},
    "signals": {"benchmark": {"suite_id": "…", "measured": "WEAK", "passed": 1, "total": 4},
                 "staleness": "contradicted", "elo": null, "spc": null}}],
 "evidence": {"ledger_path": "…", "chain_ok": true}}
```

  Aggregation rules (deterministic, precedence top-down per cell):
  1. Benchmark contradiction ⇒ `rating-change` to the **measured** rating (+ `last_validated` = now).
  2. Staleness `contradicted` (dispatch-failure share) or Elo divergence or provider SPC drift ⇒ `revalidate` (with the signal attached; no invented rating value).
  3. Staleness `corroborated` ⇒ `last-validated-bump` to `latest_corroborated_at`.
  4. `unexercised` cells are listed under a `"unexercised"` array (calibration *candidates* for `/retro`'s attention, not diffs).
  5. No signals at all ⇒ `status: "no-proposal"` (zero-data contract).
- `render_diff_preview(proposal, registry_path) -> str` — reads the YAML **read-only** and renders a unified-diff-style preview of proposed cell edits (the `tier_efficacy.render_diff_preview` analog) for the Phase-5(f) `AskUserQuestion`.
- CLI: `python3 engine_calibration.py report --root . [--json]` and `… preview --root .`.
- **The module exposes no write API for the registry** — `report`/`preview` accept paths only to read. AE6's byte-identity test is the durable guard.

### 2.7 R4/R5 runtime consumption (changed files)

**`plugins/saga/scripts/engine_registry.py`**
- `ranked_candidates(capability, *, overlay=None, calibration: Any | None = None)` — duck-typed like `overlay` (no import of `engine_calibration`; no cycle). When `calibration` is provided, the sort key becomes `(-rating_score, drift, -elo, cost_speed_rank, registry_order)` where `drift = 1 if entry.engine_id in calibration.drift_flagged else 0` and `elo = calibration.elo.get((entry.key, capability), 1200.0)`. Semantics: **reorder within an authored rating band only** — rating score still dominates; a drift-flagged or Elo-losing provider is deprioritized, never excluded (deprioritize ≠ gatekeep). `calibration=None` (the default everywhere) is byte-identical to today. Overlay pins still win (pin insertion happens after the sort, unchanged).
- `explain_capability` threads the same optional param.

**`plugins/saga/scripts/engine_resolver.py`**
- `resolve(..., calibration: Any | None = None)` → `_resolve_capability` → `_decide_capability` → `ranked_candidates(capability, overlay=…, calibration=…)`.
- `RunMemo` capability-decision keys gain a fifth component: `calibration_fingerprint` string (defaults `""`) — internal tuple-shape change only.

**`plugins/saga/scripts/engine_registry_cli.py` + `plugins/saga/commands/engines.md`**
- `route explain <capability>` gains `--calibration`: resolves `run_ledger.RunLedger.resolve(repo_root)`, calls `engine_calibration.load_calibration`, and shows the calibrated ranking beside the authored one plus per-provider drift/Elo columns. This is the committed, operator-visible consumer of R4/R5 at resolution time. **Deliberately deferred** (named non-goal, see §7): threading `calibration` into the hot dispatch paths (`outcome_dispatcher`, `second_opinion`) — the opt-in parameter is the mechanism; wiring every call site is follow-up scope with its own blast radius.

### 2.8 R6 — `plugins/saga/skills/retro/SKILL.md` (changed)

Three surgical insertions, following the exact house register:

1. **Phase 1.11 — Engine-registry calibration evidence (read-only, issue #459).** After 1.10: run `python3 plugins/saga/scripts/engine_calibration.py report --root . --json`; the reader chain-verifies the run-fact ledger first (a chain break is a **visible evidence failure**, 1.9's rule); include the output verbatim in the evidence block. **Zero-data contract** (same as 1.6/1.7/1.9/1.10): `no-proposal` / all-`unexercised` is carried as "no dispatch evidence yet", never a fabricated calibration.
2. **Phase 5(f) — engine-registry calibration (issue #459).** When Phase 1.11 returned `status: "proposal"`: render `engine_calibration.render_diff_preview` and present per-cell with `AskUserQuestion` (apply / skip / modify) — exactly like 5(e). **This pass never writes `engine-registry.yaml`**; an "apply" answer means the **operator** (or a follow-up `/plan`) performs the hand-edit. Cite `{#external-engines-never-gatekeepers}` (#283) inline. No proposal is a normal silent no-op.
3. **Reference files** — add bullets for `../../scripts/engine_calibration.py` (Phase 1.11 reads, Phase 5(f) proposes; never writes), `engine_stale_report.py`, `capability_elo.py`, `provider_control_chart.py`, `engine_benchmark.py`, and `../../references/benchmark-loop.md`.

---

## 3. Test plan (per requirement; acceptance-check `-k` names honored)

New test files follow the house `importlib.util.spec_from_file_location` loader pattern (`tests/test_engine_dispatch_ledger.py:15-24`). Coverage floor: ≥ 80 % on every new module — all five new modules are pure-function-first, so this is met by direct unit tests; CLI `main()`s get one smoke test each.

**R1 — extend `tests/test_engine_dispatch_ledger.py`** (existing file; existing #388 tests must stay green)
- `test_chain_verification_fails_on_mutated_dispatch_record` (AE1): append 3 engine facts **through `engine_dispatch.dispatch`** with a fake runner + real `RunLedger(tmp_path)`; rewrite the middle JSONL line's payload in place → `run_ledger.verify_chain(...).ok is False` with `this_hash mismatch`; restore the original bytes → `ok is True`.
- `test_chain_verification_fails_on_deleted_dispatch_record` (AE1): delete the middle line → `prev_hash` break.
- `test_engine_fact_carries_capability_claimed_rating_and_execution_id`: capability-resolved `Resolution` → fact has all three; explicit-engine resolution → empty strings; `bridge_run_key` dedup still single-append.
- `tests/test_run_ledger.py`: update `test_schema_covers_all_five_kinds` → six kinds incl. `benchmark`.
- `tests/test_reconcile.py`: `member_index` round-trip through `append_reconciliation_fact`/`read_reconciliation_facts`; absent-field facts still validate (backward compat); malformed `member_index` (key not in `source_finding_ids`, empty member list) rejected.

**R2 — `tests/test_engine_benchmark.py`** (new)
- `test_contradicted_rating_emits_proposal_never_a_write` (AE2, `-k contradicted_rating`): fake registry fixture with a `STRONG` row, injected runner returning failing outputs ⇒ measured `WEAK`; assert a `registry_calibration_proposal.v1` cell naming the row+capability is returned **and** the on-disk registry fixture is byte-identical before/after.
- Threshold mapping boundaries (`0.8`/`0.5`/below); each grader kind pass+fail; suite-loader validation errors; `benchmark` fact appended when ledger trio supplied, none otherwise.

**R3 — `tests/test_engine_stale_report.py`** (new)
- `test_all_verdicts_over_synthetic_fixtures` (AE3, `-k all_verdicts`): three-row synthetic registry + seeded ledger → one `corroborated` (recent ok facts), one `contradicted` (benchmark `contradicts:true`; second variant via ≥3 failing dispatches), one `unexercised` (no facts).
- Facts **older** than `last_validated` do not corroborate; empty ledger ⇒ all `unexercised` + zero-data note; chain break ⇒ raises.

**R4 — `tests/test_capability_elo.py`** (new)
- `test_elo_drop_reroutes_fallback_prior_selection` (AE4, `-k elo_drop_reroutes`): seed 5 panel reconciliation facts (via `append_reconciliation_fact` with `member_index`) where provider A's findings are all `dropped` and B's all `reconciled` → `scores[B] > scores[A]`; two same-rating registry rows; `resolve({"capability": …}, mode="advisory", registry=…, calibration=load_calibration(ledger))` (preflight stubbed per existing resolver-test pattern) selects B; **assert the registry YAML bytes and `entry.capability_profile[...]["rating"]` are unchanged**.
- Pure Elo math (symmetry, draw ≈ no movement at equal ratings); `derive_matches`: panel-empty exclusion, unmapped-intent skip counted in `unattributed_matches`, solo reconciliation ⇒ no match; deterministic fold order.

**R5 — `tests/test_provider_control_chart.py`** (new)
- `test_spc_drift_flag_on_sustained_spike_not_common_cause` (AE5, `-k spc_drift_flag`): synthetic latency series — provider X stable baseline then sustained ~3× spike ⇒ `out-of-control`; provider Y same-variance noise ⇒ `in-control`.
- `< baseline_n+1` points ⇒ `no-data`; zero/absent metric values excluded; rule-4 (8-run shift below UCL) fires; `drift_flagged` aggregates per `engine_id` across variants.

**R6 — `tests/test_saga_retro_calibration.py`** (new)
- `test_proposal_only_never_writes_registry` (AE6, `-k proposal_only_never_writes`): seed a ledger with all four signal families (benchmark contradiction, corroborating dispatches, Elo matches, SPC spike); snapshot `engine-registry.yaml` fixture bytes; run `report()` **and** `render_diff_preview()`; assert output is a `registry_calibration_proposal.v1` containing ≥1 `rating-change` and ≥1 `last-validated-bump` with `approval_required: true`, and the registry file is **byte-identical** before and after. (This is the release-surface checklist's drift guard, wired into plain `uv run pytest`.)
- `no-proposal` on empty ledger; chain break ⇒ raises; aggregation precedence (benchmark beats bump on the same cell).
- SKILL drift guards: assert `retro/SKILL.md` contains the `1.11` pass, the `5(f)` pass, the `{#external-engines-never-gatekeepers}` citation, and the never-writes sentence (string-presence lint, same style as existing SKILL-content tests).

**Resolver/registry parity** (in the existing resolver/registry test homes)
- `ranked_candidates(..., calibration=None)` ordering identical to pre-change for the real registry (parity guard).
- Drift-flagged provider drops within its band but is **never excluded** and never crosses a rating band; overlay pin still beats calibration reorder; memo key differentiates calibration fingerprints.

## 4. Release surfaces (tri-lock — `tests/test_release_surface_parity.py` enforces all three agreeing)

- `plugins/saga/.claude-plugin/plugin.json` — `0.87.0` → **`0.88.0`**.
- `.claude-plugin/marketplace.json` — saga entry version → `0.88.0`.
- `plugins/saga/CHANGELOG.md` — `## [0.88.0] - <merge date>` dated heading (format per `changelog_heading_lint`), `### Added` covering: capability/claimed-rating/execution-id dispatch facts + `benchmark` fact kind (R1), `engine_benchmark.py` + `benchmark-suite.yaml` + `benchmark-loop.md` (R2), `engine_stale_report.py` (R3), `capability_elo.py` + reconciliation `member_index` (R4), `provider_control_chart.py` (R5), `engine_calibration.py` + `/retro` Phase 1.11/5(f) + `engines route explain --calibration` (R6) — each line naming the proposal-only posture.
- `plugins/saga/commands/engines.md` — document `--calibration`.

## 5. Engineering journal (same PR)

- `docs/engineering-journal/DECISIONS.md` — new anchored entry `{#earned-ratings-proposal-only-459}`: every calibration signal terminates in a `registry_calibration_proposal.v1` a human applies by hand via `/retro` Phase 5(f); **rejected alternatives**: (a) auto-applying `last_validated` bumps for corroborated cells (rejected — one write seam, no carve-outs beyond the journal-append rule), (b) a separate `engine_dispatch_ledger.py` file (rejected — `run_ledger.py` is the landed one-ledger spine; a second chain forks evidence), (c) LLM-graded benchmark probes (rejected — #283: engines never judge); **revisit-when**: ≥ 3 consecutive retros where every emitted proposal was applied unmodified — then consider auto-applying *only* `last-validated-bump` actions behind an operator setting.
- `docs/engineering-journal/LEARNINGS.md` — dated entry: issue #459's central premise ("no dispatch ledger exists") was invalidated by the merge train (#401/#388/#393 landed the chained spine + engine/reconciliation facts) — **Evidence:** `run_ledger.py:1-24`, `engine_dispatch.py:1136-1153`, this plan §0; **Mechanism:** wave-3 issues authored against wave-2 evidence go stale as the spine lands; **Generalizable rule:** re-verify every "verified absent today" claim at plan time and re-scope to gap-closure rather than duplicating landed substrate.

## 6. Sequencing within the PR (each commit green: pytest + ruff check + ruff format + mypy)

1. **Substrate:** `run_ledger` sixth kind; `Resolution.capability/rating_claimed` + resolver threading; engine-fact field extension in `engine_dispatch`; `reconcile` `member_index` (+ validator relax). Tests: ledger/dispatch/reconcile/run_ledger updates.
2. **Reducers (mutually independent):** `engine_stale_report.py`, `capability_elo.py` (pure parts), `provider_control_chart.py` + their test files.
3. **Benchmark:** `engine_benchmark.py`, `references/benchmark-suite.yaml`, `references/benchmark-loop.md` + tests.
4. **Aggregator + runtime signals:** `engine_calibration.py` (`CalibrationSignals`, `load_calibration`, `report`, `render_diff_preview`) + `test_saga_retro_calibration.py`; `ranked_candidates`/`resolve` `calibration` param + memo fingerprint + parity tests; `capability_elo` resolution-path test (AE4) lands here (needs the param).
5. **Surfaces:** retro `SKILL.md` (1.11, 5(f), references); `engine_registry_cli.py` `--calibration` + `commands/engines.md`.
6. **Release + journal:** plugin.json / marketplace.json / CHANGELOG tri-lock bump; DECISIONS + LEARNINGS entries.

## 7. Explicit non-goals (inherited + plan-added)

- No `engine-registry.yaml` schema change (sibling `pf-engine-registry-schema`); proposals target `rating`/`last_validated` only.
- No automated/scheduled benchmark or calibration ceremony — everything runs on `/retro`'s operator cadence or explicit CLI invocation.
- No direct-write path from any of R2–R5 (structural constraint; a reviewer finding one fails the PR).
- **Plan-added:** no `calibration` wiring into `outcome_dispatcher`/`second_opinion` hot paths this PR — the opt-in `resolve(calibration=…)` parameter plus the `engines route explain --calibration` consumer land the mechanism; hot-path adoption is a named follow-up (queue via `/retro`/`QUEUED.md`), keeping this PR's dispatch blast radius at zero-by-default.
- No new `engine_dispatch_ledger.py` module (see §0 — deliberate divergence from the issue's indicative file list, with the acceptance test file name preserved).

## 8. Risks and mitigations

| Risk | Mitigation |
|---|---|
| `FACT_KINDS` extension breaks strict consumers | Only known kind-set assertion is `test_run_ledger.test_schema_covers_all_five_kinds` (updated); `rollup`/readers filter by kind, tolerant of new kinds. Grep for other `FACT_KINDS` consumers at build time. |
| `reconcile` fact validator is exact-set (`reconcile.py:776`) — old facts must stay valid | Subset/superset relaxation admits only `member_index`; explicit backward-compat test on a legacy-shaped fact. |
| Resolution ordering regression from the calibration sort key | `calibration=None` default everywhere + byte-parity test on the real registry; calibration reorders only within a rating band; pins unaffected. |
| Frozen `Resolution` consumers constructing positionally | New fields appended after existing defaults; audit constructors (`tests/test_engine_dispatch_ledger.py:34` uses keywords). |
| SPC false positives on thin/noisy series | `baseline_n` gate ⇒ `no-data`; two conservative rules only; flag deprioritizes, never excludes; terminates in a `revalidate` proposal, not an action. |
| Elo starves (panels rare; attribution only accrues post-`member_index`) | Zero-data honesty end-to-end (`no-proposal`, `unattributed_matches` stat); documented "signal accrues over time" — same stance as Phase 1.10 today. |
| Benchmark suite triviality/gaming | Deterministic graders + versioned immutable `suite_id`s + `benchmark-loop.md` rules; measured ratings only ever **proposed**. |
| Registry hand-edit races the ledger (facts joined against a rating that changed) | `rating_claimed` is stamped **at resolution time** into each fact — joins are self-contained historical records. |
| Tri-lock version collision with sibling in-flight PRs (known gotcha: silent auto-merge of version bumps) | Re-verify `0.88.0` is still the next free version at merge time; re-bump if a sibling landed first. |
| mypy/ruff scope (CI checks `plugins/ scripts/ tests/`; format gate separate from check) | Every commit runs the full four-command gate from CLAUDE.md. |

## 9. Acceptance-criterion → test mapping

| Acceptance criterion (issue) | Test | Requirement |
|---|---|---|
| Chain-verify fails on mutated/deleted earlier record — `test_engine_dispatch_ledger.py -k chain_verification` | `test_chain_verification_fails_on_mutated_dispatch_record`, `…_on_deleted_dispatch_record` | R1 / F1 / AE1 |
| Benchmark emits diff proposal, never a write — `test_engine_benchmark.py -k contradicted_rating` | `test_contradicted_rating_emits_proposal_never_a_write` | R2 / F2 / AE2 |
| Three staleness verdicts — `test_engine_stale_report.py -k all_verdicts` | `test_all_verdicts_over_synthetic_fixtures` | R3 / F3 / AE3 |
| Elo drop reroutes fallback-prior selection, authored rating untouched — `test_capability_elo.py -k elo_drop_reroutes` | `test_elo_drop_reroutes_fallback_prior_selection` | R4 / F4 / AE4 |
| SPC flags spike, not common cause — `test_provider_control_chart.py -k spc_drift_flag` | `test_spc_drift_flag_on_sustained_spike_not_common_cause` | R5 / F5 / AE5 |
| `/retro` calibration proposal; registry byte-identical — `test_saga_retro_calibration.py -k proposal_only_never_writes` | `test_proposal_only_never_writes_registry` | R6 / F3, F6 / AE6 |
| `DECISIONS.md` revisit-when entry | `grep -n "revisit-when" docs/engineering-journal/DECISIONS.md` (manual check in Verification) | DoD |
| Release surfaces in same PR | `tests/test_release_surface_parity.py` tri-lock (existing, must pass with `0.88.0`) | DoD |
| Full gate green | `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` | DoD |
