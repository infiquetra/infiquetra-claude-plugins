# Implementation Plan — Issue #400: Pulse live-telemetry component (`/pulse`)

**Repo:** infiquetra/infiquetra-claude-plugins · **Branch base:** `origin/main` @ `2bdc168` · **Plan date:** 2026-07-13
**Issue:** [#400](https://github.com/infiquetra/infiquetra-claude-plugins/issues/400) — board/agent/run state rendered from real signals, wave-2 of the telemetry-substrate-close outcome.
**Plan artifact path:** `docs/plans/2026-07-13-issue-400-pulse-live-telemetry-plan.md`

---

## 0. Evidence-anchor audit (issue anchors vs. origin/main today)

| Issue anchor | Status on `2bdc168` | Current location |
|---|---|---|
| `docs/engineering-journal/QUEUED.md:73` (`{#pulse-live-telemetry-component}`) | **STALE line number** — entry exists, moved | `docs/engineering-journal/QUEUED.md:107` (heading `### P2/P3 — Standalone /pulse live-product telemetry component`) |
| `docs/engineering-journal/QUEUED.md:26` (campaign closer naming `/pulse` open) | Valid | `QUEUED.md:26` |
| `plugins/mission-control/skills/board/SKILL.md` | Valid | Same path; script surface is `plugins/mission-control/scripts/sdlc_manager.py`, `board_view()` at line 984, JSON output via `fmt == "json"` (line ~1001) |
| `saga.py` derived-on-read tick history | Valid | `plugins/saga/scripts/saga.py`: `read_ticks()` line 983, `scan()` line 1029, `restore()` line 971 |
| `pf-run-fact-ledger` (#401) — "find its actual module" | **MERGED** (commit `4ad193c`, PR #489) | `plugins/saga/scripts/run_ledger.py` + reference doc `plugins/saga/references/run-fact-ledger.md`. Schema `run_fact.v1`, kinds `spend|cache|engine|delegation|reconciliation`, file at `<git-common-dir>/saga-run-facts/run-facts.jsonl` |
| `pf-spend-observability-reports` (#402) | **MERGED** (commit `87cfb5d`, PR #570) | `plugins/saga/scripts/spend_estimate.py`, `spend_receipt.py`, `spend_retro.py`, `tier_efficacy.py`, `shadow_audit.py` — readers over `outcome_costs.py`'s leaf-produced cost records (in `outcome_store` events), **not** over `run_ledger.py` |
| `optimize/SKILL.md` (must stay untouched) | Valid | `plugins/saga/skills/optimize/SKILL.md` |
| `/private/tmp/.../issue-map-final.json` | Ephemeral tmp path, gone | Rationale is quoted in the issue body itself; no repo action needed |

**Key factual correction for the builder:** AC5's "if worked before `pf-run-fact-ledger` merges" contingency is moot — the ledger IS merged. AC5's obligation transforms into: an **empty/absent/chain-broken ledger must render an explicit "no data yet" / "unavailable" state, never a silent zero or fabricated aggregate**. No tick-history-as-interim-ledger substitution is needed; tick history is the *run-state* source in its own right (the same source `/outcome` treats as truth), not a ledger stand-in.

---

## 1. Placement decision: Pulse lands in the **saga plugin** as a script + skill

**Decision:** `plugins/saga/scripts/pulse.py` (CLI reader) + `plugins/saga/skills/pulse/SKILL.md` (the `/pulse` command surface). No new plugin.

**Justification (record as KTD1 in DECISIONS.md):**
1. **Every existing read-side consumer of the telemetry substrate landed as a saga script.** `engine_promotion.py` (#455, explicitly documented as "a read-only consumer of the ledger"), `spend_receipt.py`/`spend_retro.py`/`tier_efficacy.py` (#402), `override_rate_reader.py`, `gate_divergence_reader.py`. Pulse is the same shape.
2. **All three data sources it reads are saga-resident or saga-reachable:** `run_ledger.py`, `saga.py` tick history, `outcome_costs.py` — same-directory imports via the established `sys.path` shim pattern. Only the board read crosses a plugin boundary, and saga already crosses that exact boundary in the same direction-pair (`outcome_board_sync.py` writes boards via mission-control's certificate-gated path; Pulse merely *reads* via `sdlc_manager.py board view --format json`).
3. **The consolidation-burden constraint** (`{#plugin-portfolio-groom-17-to-7}`, grounding brief §2) puts the burden of proof on any new plugin. A single read-only surface with zero external-service credentials of its own does not carry that burden.
4. **Rejected: mission-control.** Mission-control owns GitHub/board interaction; it has no access to sagas, the run-fact ledger, or outcome stores, and cannot honor derived-on-read run state without importing saga internals backwards.
5. **Rejected: new `pulse` plugin.** Would duplicate the saga script-import shims, need its own release surfaces forever, and violate the groom constraint for one file.

**Boundary vs `/optimize` — settle the QUEUED open question from the pulse side (record as KTD3):** Pulse **stands beside** `/optimize`; it does not feed it automatically. Pulse is a continuous read-only view and **not a gate**; the operator may read a Pulse snapshot when choosing an `/optimize` target, but there is no programmatic data-flow, no target, no baseline, no budget, no stop condition anywhere in Pulse (AC6). `plugins/saga/skills/optimize/SKILL.md` is untouched by this PR.

---

## 2. Data sources and exact facts consumed (all derive-on-read, zero writes)

### 2.1 Board state (AC1)
- **Read path:** subprocess invocation of `python3 plugins/mission-control/scripts/sdlc_manager.py board view --project <p> --format json`, one call per requested project (`operations`, `asgard`, `campps`). The runner is **injected** (`runner: Callable` parameter defaulting to `subprocess.run`) so tests drive the path without live GitHub — the same injection pattern as `board_progression.py`'s injected `board_writer` and `RunLedger.resolve(runner=)`.
- **JSON shape consumed** (produced by `board_view()` at `sdlc_manager.py:984`): `{"project": <name>, "columns": {<status>: [<projectV2 item nodes>]}}`. Per item, Pulse reads only: title/number/repo (from `content`), the `Status` field (via the same semantics as `get_item_status`), and `createdAt` for age. Pulse tolerates missing fields — a missing field renders as `?`, never a fabricated value.
- **Rendered facts:** per-project column counts, WIP-limit numbers **as configured** by mission-control (cite the configured number; Pulse itself introduces no thresholds — no-false-precision posture), and item count per active status.
- **Path resolution risk:** the mission-control script path is resolved relative to this repo's root (walk up from `Path(__file__)`); overridable via `--sdlc-manager PATH`. Resolution failure or a non-zero exit degrades to the explicit `board: unavailable (<reason>)` state — never a crash, never empty-as-zero.

### 2.2 Agent/run state (AC2, AC3)
- **Source:** `saga.py scan(root, max_candidates=N)` (line 1029) for the fleet view — one latest-tick candidate per saga with `lifecycle_phase`, `phase`, `phase_status`, `next_step`, `updated_at`, `issue_ref`, `branch`, `orchestration_mode` — and `read_ticks(root, saga_id)` (line 983) when `--saga <id>` focus is requested (renders the tick trajectory).
- **Derived-on-read discipline:** Pulse renders exactly the fields `scan()` already derives (`next_phase` is computed, `phase_status` is stored-by-the-writer per the saga schema). Pulse **writes no field anywhere** — no tick, no ledger fact, no cache file. This is the AC3 obligation and is enforced by test (see §5).

### 2.3 Run-fact ledger (AC2, AC4, AC5)
- **Source:** `run_ledger.RunLedger.resolve(repo_root)` → `read_snapshot(ledger)` → `LedgerSnapshot(records, ChainReport)`.
- **Facts consumed:**
  - `spend` facts: `tokens`, `tokens_cached`, `tokens_fresh`, `wall_seconds` → totals via `rollup(ledger, "spend")` and `reuse_ratio(ledger)` (`None` → "no data yet", per the module's own defined-empty contract).
  - `engine` facts: count, per-`status` count, `proof_integrity_status` breakdown, `cost`/`latency_seconds` rollup.
  - `delegation`, `cache`, `reconciliation` facts: counts + most-recent `at`.
  - Chain custody: `verify_chain()` verdict rendered as an explicit banner (`chain: ok (N facts)` or `chain: BROKEN at record <i> — <reason>`). A broken chain suppresses all aggregate numbers (they are no longer trustworthy) and renders the banner instead — explicit degrade, not fabrication.
- **Empty/absent ledger** → `ledger: no data yet (no run facts recorded)` — the AC5 state.

### 2.4 Outcome economics (reuse of the #402-adjacent reducer; no new metric source)
- **Source:** `outcome_costs.rollup(spec, store)` for the newest in-flight outcome under `docs/outcomes/*/outcome-spec.json`, if any. This module already implements the exact honesty posture Pulse inherits ("missing telemetry renders **no data yet**, never a fabricated zero" — `outcome_costs.py:16,200`). Pulse displays its per-outcome totals + the DAG-vs-serial wall numbers when present; `{}` → "no data yet". No outcome present → panel says so. This panel is optional-on-data, always-rendered-as-a-row (constant card height).

---

## 3. Render surface shape

**Decision (KTD2): reuse `status_card.py`, the fleet's single status emitter (#278), with a new `summary-projection` builder `project_pulse(snapshot)`** — constant-height card, position-stable rows, every determinable cell traceable via the indexed evidence footer. Rejected: a bespoke renderer (would fork the single-emitter decision) and an HTML artifact (nothing in the fleet consumes HTML; the operator surface is the terminal).

### 3.1 `pulse_snapshot.v1` (the machine shape, emitted by `--json`)

```python
{
  "schema": "pulse_snapshot.v1",
  "at": "<ISO, caller-supplied like run_ledger — deterministic/testable>",
  "board": {
    "status": "ok" | "no-data" | "unavailable",
    "reason": "<only when unavailable>",
    "projects": {
      "<project>": {
        "columns": {"<status>": {"count": int, "wip_limit": int | None}},
        "items_active": [{"repo": str, "number": int, "title": str, "status": str, "age_days": float}]
      }
    }
  },
  "runs": {
    "status": "ok" | "no-data",
    "sagas": [{"saga_id","kind","lifecycle_phase","phase","phase_status","next_step",
               "updated_at","issue_ref","branch","orchestration_mode"}],   # newest-first, capped by --max-sagas (default 10)
    "focus_ticks": [...] | None    # only with --saga <id>: the read_ticks trajectory
  },
  "ledger": {
    "status": "ok" | "no-data" | "chain-broken",
    "chain": {"ok": bool, "break_index": int|None, "reason": str},
    "fact_counts": {"spend": int, "engine": int, "delegation": int, "cache": int, "reconciliation": int},
    "spend": {"tokens": {...rollup...}, "wall_seconds": {...}} | None,
    "reuse_ratio": float | None,
    "engine": {"by_status": {...}, "proof_integrity": {...}} | None,
    "last_fact_at": str | None
  },
  "outcome_costs": {"status": "ok" | "no-data", "rollup": {...} | None}
}
```

Uniform tri-state per panel — `ok` / `no-data` / `unavailable`(+`chain-broken`) — is the load-bearing honesty mechanism (record as KTD5): a consumer can never mistake "we couldn't read it" or "nothing recorded" for "zero activity".

### 3.2 The card (human shape, default output)

`project_pulse()` returns a `CardSpec` (`archetype="summary-projection"`) with fixed rows: header (`PULSE — live fleet telemetry`, snapshot `at`); one board row per configured project (`operations: Active 3 · Verify 1 · WIP 3/5` or `board: unavailable (gh not authenticated)`); a runs summary row (`sagas: 4 in flight — newest: work-565 (pr_loop, in_progress, 2026-07-13T…)`) plus up to `--max-sagas` per-saga rows rendered from the fixed-row budget (summary-projection keeps height constant); ledger rows (`chain ok · 27 facts`, `spend: 412,930 tokens (reuse 0.63) · 1,842 wall-s`, or `no data yet`); one outcome-costs row. Every number cell footnoted to its evidence source (ledger path, saga id, project) via the existing indexed footer. **No colors-as-judgment, no invented thresholds** — numbers cited, operator judges (ce-product-pulse posture).

### 3.3 CLI

```
python3 plugins/saga/scripts/pulse.py
  [--repo-root PATH] [--project NAME]... (default: none → board panel says "no project requested")
  [--json] [--saga SAGA_ID] [--max-sagas N]
  [--no-board]                  # offline mode: skip subprocess entirely
  [--sdlc-manager PATH]
  [--watch --interval SECONDS --iterations N]   # thin re-render loop; iterations required (no unbounded daemon), sleep injectable for tests
```

`--watch` is a plain re-invoke loop, not a daemon or scheduled harness (KTD4 — mirrors the fleet's settled rejection of standing calibration ceremony; the DoD's "in real time **or on refresh**" is satisfied by refresh-on-invoke, watch is convenience). House pattern throughout: pure functions over explicit values, no I/O at import, `sys.path` shim + lazy imports, stdlib only.

---

## 4. Module-by-module build

### New files
1. **`plugins/saga/scripts/pulse.py`** (~350–450 lines)
   - `read_board_state(projects, *, sdlc_manager_path, runner) -> dict`
   - `read_run_state(repo_root, *, max_sagas, focus_saga=None) -> dict` (wraps `saga.scan`/`saga.read_ticks`)
   - `read_ledger_state(ledger: run_ledger.RunLedger) -> dict`
   - `read_outcome_costs_state(repo_root) -> dict` (lazy-imports `outcome_costs`, `outcome_spec`, `outcome_store`)
   - `snapshot(*, at, board, runs, ledger, outcome_costs) -> dict` (assembles `pulse_snapshot.v1`; `at` caller-supplied)
   - `project_pulse(snapshot) -> status_card.CardSpec`, `render(snapshot) -> str`
   - `main(argv) -> int`
2. **`plugins/saga/skills/pulse/SKILL.md`** — frontmatter `name: pulse`; when-to-use ("what is the fleet doing live?"); the four panels and their sources; the tri-state honesty contract; the settled `/optimize` boundary paragraph (continuous read-only, not a gate, no feed); pointer to the manual recipe.
3. **`plugins/saga/skills/pulse/references/manual-verification.md`** — the human drive-a-run recipe (§6).
4. **`tests/test_pulse_telemetry.py`** (§5).

### Changed files
5. `plugins/saga/.claude-plugin/plugin.json` — `0.87.0` → `0.88.0` (**re-verify the current version at merge time** — sibling-PR version collisions merge silently; known gotcha from evidence-integrity outcome) + description note.
6. `.claude-plugin/marketplace.json` — matching saga entry bump (line ~86).
7. `plugins/saga/CHANGELOG.md` — dated `0.88.0` entry: new `/pulse` surface, its four real sources, the explicit no-data/unavailable/chain-broken degrade states.
8. `plugins/saga/README.md` — add `/pulse` to the skill roster if the README lists skills (confirm at build).
9. `plugins/saga/references/run-fact-ledger.md` — add Pulse to the read-only consumers section (beside `engine_promotion.py`).
10. `docs/engineering-journal/QUEUED.md` — flip `{#pulse-live-telemetry-component}` (now line 107) to **SHIPPED 0.88.0** with cross-refs; note the adapted scope (fleet telemetry, not product-usage analytics — the "pre-revenue, no product data" parking remains true for usage/conversion/retention, which stay out of scope per the issue's non-goals).
11. `docs/engineering-journal/ARCHIVE.md` — ship record `{#pulse-live-telemetry-shipped}`.
12. `docs/engineering-journal/DECISIONS.md` — KTD1–KTD5 from this plan under `{#pulse-live-telemetry-ktds-400}`.

### Explicitly untouched
`plugins/saga/skills/optimize/SKILL.md` (AC6), `saga.py` (zero edits), `run_ledger.py` schema/`FACT_KINDS` (zero edits), `outcome_costs.py` (zero edits).

---

## 5. Test plan — AC-to-test mapping (`tests/test_pulse_telemetry.py`)

Import pattern mirrors `tests/test_mission_control.py` (sys.path insert for `plugins/mission-control/scripts`) and the saga-script tests (sys.path insert for `plugins/saga/scripts`). **No live GitHub:** all board tests seed at the `sdlc_manager._graphql` boundary; consider adding `test_pulse_telemetry` to `conftest._no_live_gh`'s guarded set defensively (it is read-only, but the guard is cheap).

| AC | Test(s) | Mechanism |
|---|---|---|
| **AC1** board reads real path | `test_board_state_renders_seeded_item_through_mission_control_read_path` | Monkeypatch `sdlc_manager._graphql` to return a seeded projectV2 items payload (one item, distinctive title/number/status); produce JSON via the **real** `sdlc_manager` grouping code (`get_project_items` + `board_view` fmt=json, captured); feed Pulse via an injected runner that executes that real path in-process. Assert the rendered card/JSON contains the seeded item's number/status — and assert it is *absent* when the seeded payload omits it (proves no fixture fallback). |
| **AC2** run state from ticks | `test_run_state_reflects_each_tick_transition` | In a tmp repo root, drive a **real disposable saga** through ≥2 lifecycle ticks via `saga.save(...)` (real envelope files); snapshot+render after each tick; assert render 1 shows tick-1 `phase_status`/`lifecycle_phase` and render 2 shows the advanced state — a before/after diff keyed to real transitions. |
| **AC2** ledger facts | `test_ledger_panel_reflects_appended_facts` | Real `RunLedger(path=tmp)`; `append_fact(build_fact("spend", ...tokens=1200, tokens_cached=800...))`; assert rendered spend totals and `reuse_ratio` cite exactly the appended numbers. |
| **AC3** derived-on-read, no writes | `test_pulse_writes_nothing_anywhere` | Byte-hash every file under the tmp repo's saga dir, ledger dir, and outcome store before and after `snapshot()`+`render()`; assert identical. Plus `test_no_pulse_owned_status_field`: assert `run_ledger.FACT_KINDS` unchanged and the snapshot's run-state fields are exactly the `saga.scan()` candidate fields (no new committed field). |
| **AC4** end-to-end proof | `test_drives_real_run_and_surface_updates` (satisfies the issue's `-k drives_real_run` check) | One test composing it all in a tmp repo: create saga tick 1 + append a real hash-chained spend fact → snapshot A; advance the saga tick + append a second fact → snapshot B; assert a **state-transition diff** — run row changed phase, ledger fact-count and token total changed by the appended amounts — not merely "renders without error". |
| **AC5** explicit degrade | `test_absent_ledger_renders_no_data_yet` (no file → "no data yet" label, no zeros); `test_broken_chain_renders_banner_not_aggregates` (tamper one byte mid-file → `chain-broken` status, aggregates suppressed); `test_board_unavailable_labels_not_zero` (runner raises / non-zero exit → `unavailable (<reason>)`) |
| **AC6** no experiment primitives | Primarily a review check (this plan + `/code-review` confirm no target/baseline/budget/stop primitives; `optimize/SKILL.md` untouched in the diff). Belt-and-braces test: `test_snapshot_schema_has_no_experiment_keys` asserts none of `{"target","baseline","budget","stop"}` appear as keys in `pulse_snapshot.v1`. |
| Release surfaces | Existing drift guards (`test_marketplace_hook.py`, `test_sync_marketplace.py`, `test_changelog_heading_lint.py`) must stay green against the 0.88.0 bump — run, don't assume. |

Also: a `--watch` unit test with injected sleep/clock and `--iterations 2` asserting two renders and termination; a `--json` schema smoke test.

**Full gate:** `uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports && uv run bandit -r plugins/` (bandit note: the subprocess call needs the standard `# nosec`-free treatment used by sibling scripts — list-args, no shell).

---

## 6. Manual verification recipe (`skills/pulse/references/manual-verification.md`)

1. In a scratch worktree, start a disposable run (`/work` on a trivial branch, or `saga.py save` directly) — tick 1 written.
2. `python3 plugins/saga/scripts/pulse.py --project operations` → observe the saga listed with its current phase, ledger panel per current chain, board panel showing live Operations columns.
3. Advance the run (next tick; if the run dispatches an engine call, `engine_dispatch` appends a real `engine` fact).
4. Re-run Pulse (or leave `--watch --interval 15 --iterations 20` running) → observe the run row's phase change and the ledger fact-count/spend change.
5. Negative check: `mv` the ledger file aside → re-run → observe `no data yet`, not zeros. Restore it.

---

## 7. Sequencing within the single PR (one branch, ordered commits)

1. **U1 — core reader + renderer:** `pulse.py` (all four `read_*`, `snapshot`, `project_pulse`, `render`, `main`).
2. **U2 — tests:** `tests/test_pulse_telemetry.py` (all of §5). Gate: pytest + lint + mypy green.
3. **U3 — surface docs:** `skills/pulse/SKILL.md` + `references/manual-verification.md` + `run-fact-ledger.md` consumer note.
4. **U4 — release surfaces:** plugin.json 0.88.0 + marketplace.json + CHANGELOG.md + README; re-run drift guards. **Re-check the version number against just-merged siblings immediately before merge** and re-bump if collided.
5. **U5 — journal:** QUEUED flip to SHIPPED, ARCHIVE ship record, DECISIONS KTD entry — same PR, per repo practice.
6. Full quality gate + manual recipe walked once by the builder (evidence in PR body).

U1→U2 are strictly ordered; U3/U4/U5 can be built in parallel after U2 but land as ordered commits.

---

## 8. Risks and pre-mortem

1. **Cross-plugin path resolution** (saga → mission-control script) breaks under installed-plugin layouts where relative repo paths differ. Mitigation: `--sdlc-manager` override + graceful `unavailable` degrade; the SKILL documents the override. This is the most likely field failure.
2. **`board_view` JSON shape drift** — its `columns` values are raw GraphQL item nodes, an implicit contract. Pulse reads defensively (missing field → `?`), and the AC1 test pins the contract at the `_graphql` seam so a mission-control change breaks the test loudly, not Pulse silently.
3. **Version-collision at merge** — sibling telemetry-outcome PRs bump saga concurrently and auto-merge silently (observed 2026-07-13). Mitigation baked into U4.
4. **Constant-height card vs unbounded saga count** — `--max-sagas` cap + summary row keeps the summary-projection archetype honest; the cap is a display bound, not a data threshold (cited in the footer: "showing 10 of N").
5. **`status_card.CardSpec` API fit** — `project_pulse` must satisfy the renderer's constant-size self-test conventions; builder should mirror `project_outcome()` (line 642) closely rather than inventing rows.
6. **Scope-creep pull toward product analytics** — the QUEUED entry's original framing (usage/conversion/retention) stays parked; this ships fleet telemetry only. The QUEUED SHIPPED flip must say so explicitly to avoid a false "product-pulse shipped" reading.

---

## 9. Journal entries to write (same PR)

- **DECISIONS.md `{#pulse-live-telemetry-ktds-400}`:** KTD1 placement in saga (rationale + rejected alternatives, revisit-when: Pulse grows a non-saga consumer or a web surface); KTD2 status_card reuse; KTD3 `/pulse` stands beside `/optimize`, no automatic feed, not a gate (closes the QUEUED open data-flow question from the pulse side); KTD4 snapshot-on-invoke + bounded `--watch`, no daemon; KTD5 tri-state source honesty (`ok`/`no-data`/`unavailable`).
- **ARCHIVE.md `{#pulse-live-telemetry-shipped}`:** ship record with version, PR, AC-to-test table pointer.
- **QUEUED.md:** flip `{#pulse-live-telemetry-component}` to SHIPPED-with-adapted-scope; product-usage analytics remain parked.
- **LEARNINGS.md:** only if the build surfaces a non-obvious mechanism (e.g., the `_graphql`-seam test pattern proving a cross-plugin read path without live GitHub); otherwise omit — no ceremonial entry.
