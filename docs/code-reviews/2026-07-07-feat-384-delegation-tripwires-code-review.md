# Code review — feat/384-delegation-tripwires (issue #384)

**Target:** branch `feat/384-delegation-tripwires`, 8 commits ahead of main.
**Reviewed SHA:** `5e41244` (`5e412442d5d2e458ad0c8ec61561004e8d3848fe`) · merge base = `origin/main` = `b0376e7` (fetched at review time, stale-base guard clean).
**Mode:** programmatic report-only, called by `/work` (pre-PR gate). Zero writes to reviewed code.
**Saga:** `issue-384` · destination merge · closes infiquetra/infiquetra-claude-plugins#384.
**BLOCKED: NO** — zero P0/P1 findings; review is fresh at `5e41244`.

## Verdict summary

| Gate input | Result |
|---|---|
| P0 / P1 findings | 0 / 0 |
| P2 findings | 2 (F1, F3 — both validated, neither blocking) |
| P3 findings | 4 (F4, F5, F6, F7 — validated; F2 reclassified advisory) |
| Scope check | CLEAN |
| Built-vs-planned | 7/7 units DONE |
| Suppressed (below confidence gate) | 3 |
| Validator outcome | 7/7 survivors validated (none dropped) |

## Method

Five judgment-selected lenses over the full merge-base diff (34 files, +3863/−16), each spawned as
`saga:readonly-verifier` + worktree with mandatory branch materialization + examined-SHA quoting
(all five examined `5e41244...3848fe`): correctness (opus), security (opus), reliability (opus),
testing (sonnet), maintainability/conventions (sonnet) — deploy/migration and performance lenses
judged to have no real work on this diff. Stage B: one independent validator per Stage-A survivor
(7 validators, sonnet, same sandbox profile), conservative bias, all three questions
(real / this-diff / handled-elsewhere) answered with cited evidence. Stage B.0 manifest check:
0 attested adjudications (completeness manifests only) — no validator skips taken.

## Built-vs-planned (5-state audit)

U1 `9a56620` DONE · U2 `7499df2` DONE · U3 `9e84657` DONE · U4 `1fd7f12` DONE ·
U5 `bdf5302` DONE · U6 `88a31be` DONE · U7 `eb09448` DONE. Testing lens mapped every
plan-listed scenario to a concrete test; all seven DoD-named tests exist and assert what their
names claim (bodies read). The R7 fixture-parity test genuinely importlib-loads both classifiers
over every fixture. Scope check CLEAN — every changed file maps to a plan unit or `/work`
lifecycle artifact; no requirements missing.

## Findings

| # | Sev | Conf | File | Finding | Route | Validation |
|---|-----|------|------|---------|-------|------------|
| F1 | P2 | 75 | `plugins/saga/scripts/engine_dispatch.py:79` | Requeue-once-then-HALT counter (`_INTEGRITY_ATTEMPTS`) is a process-local dict; plan KTD7 (`plan.md:346`) specifies "attempt counter in the manifest record". A one-process-per-attempt consumer always sees attempt=1 → HALT never fires (unbounded requeue). Reachability today nil: no production caller of `dispatch(gated=True)`; DoD test proves same-process only. Flagged independently by correctness + testing lenses. | manual | VALIDATED — no manifest read-back exists (grep `attempt` in manifest code: zero); no documented same-process constraint |
| F2 | P3 (advisory) | 88 | `plugins/saga/hooks/delegation_stop_audit_hook.py:187` | Crashed-dispatcher wedge: armed-unproven marker blocks file tools + HALTs turn ends until 4h TTL or manual disarm; no auto-disarm on failure paths. | advisory — accepted design | VALIDATED technically, but plan Risks + KTD2/KTD4 explicitly chose this posture (disarm on audit-pass only, TTL safety valve, CLI escape in stderr); validator also found a self-heal path (a retry's `arm()` supersedes then disarms). Hardening candidate: shorter unproven-arm TTL |
| F3 | P2 | 75 | `plugins/fleet-core/scripts/fleet_commons/delegation_state.py:115` | TTL fencepost untested: strict `>` semantics at exact `now − armed_at == ttl` never pinned; a `>`→`>=` flip passes the whole suite. Tests inject `now=` so the boundary test is trivially constructible. | safe_auto (add boundary test) | VALIDATED — repo-wide grep: no exact-boundary test, no docstring pin |
| F4 | P3 | 90 | `plugins/fleet-core/scripts/fleet_commons/delegation_state.py:142` | Lock-free read-modify-write on the shared marker: two sessions arming concurrently can lose an entry (last-writer-wins) — lost tripwire protection, fail-open direction. Only "concurrent" test is sequential. | manual (flock or O_EXCL spin; add real concurrent-writer test) | VALIDATED — no locking primitive anywhere; plan covers torn-file atomicity only, never the RMW race |
| F5 | P3 | 80 | `plugins/saga/scripts/engine_dispatch.py:23` | Module-level `shim.load()` of the two new commons modules crashes `engine_dispatch` import under version skew (saga 0.74.0 + fleet-core < 0.8.0); hooks guard the identical loads and fail open. Pattern pre-existing (`bridge_receipt`), window widened by this diff. | manual (lazy guarded accessor) | VALIDATED — no version pin anywhere (plugin.json, marketplace.json, shim ladder all uncoupled); skew is a reachable install state |
| F6 | P3 | 85 | `plugins/saga/hooks/delegation_tripwire_hook.py:96` | `delegation_audit` (358 lines) loaded before the unarmed early-out — every unarmed file-tool call fleet-wide pays it; docstring "zero further I/O" overstated. Measured: ~2.6 ms avoidable vs ~20–25 ms interpreter startup. | safe_auto (move load below the `entry is None` guard) | VALIDATED — move is behavior-preserving (armed-path try/except already fails open); no documented reason for eager load |
| F7 | P3 | 75 | `plugins/saga/hooks/delegation_tripwire_hook.py:97` | Documented shim-absent fail-open branch never test-driven in either hook — a narrowed except ships a fleet-wide hook crash with a green suite. | safe_auto (monkeypatch the loader, assert exit 0) | VALIDATED — zero import-failure simulation repo-wide; gap consistent with existing hook-test convention (weakens, does not refute) |

**Suppressed (3):** SubagentStop-shaped payload test gap (conf 50), concurrent-writer stress-test
gap (conf 50, code side survives as F4), security hardening note — unsanitized `session_id`
interpolated into the audit-record filename (`delegation_stop_audit_hook.py:66`; `../` would
traverse; below threshold under the harness-trusted model, worth a `Path(...).name` guard).

## Lens clean results worth keeping

- **Security (0 findings):** `observer_corroborated` is uninjectable — provenance built fresh
  dispatch-side, runner result contributes only status/output/receipt; `satisfy_gate` reads only
  the dispatch-stamped mark. Stop-hook second layer genuinely catches the evidence-forgery bypass;
  full bundle forgery remains the plan's accepted KTD5 risk. Evidence lines carry no command
  text; audit records gitignored (`.gitignore:55`). No shell construction anywhere.
- **Correctness:** `reconcile()` reverse-asymmetry unreachable (stop hook always
  `self_report="ok"`; dispatch never calls it). New Disposition member safe in every consumer
  (`manifest_reader.py:160` iterates the enum). Underscore/hyphen vocabularies never
  cross-compared. All hook exit paths match their documented contracts.
- **Maintainability (0 findings):** hooks genuinely mirror `pre_push_gate_hook.py`'s contract;
  commons modules follow sibling conventions; only the shim is vendored (new modules correctly
  need no vendor copies); versions consistent across all four release surfaces with passing pin
  tests; the stderr-printed CLI commands were actually run and match; CHANGELOGs neither over-
  nor under-claim. No fleet-core version-pin test exists — a pre-existing gap, not this branch's.

## Coverage and residual risk

- Gates at review time: pytest 2544 passed/1 skipped, ruff clean, mypy clean (160 files), bandit
  diff-scope 2×B110 LOW (specified fail-open contract), merge base fresh.
- Residual: F1 must be resolved (code or documented constraint) before any production consumer
  drives `dispatch(gated=True)` cross-process; F4's race window is real but requires simultaneous
  multi-session arms in one repo; fleet-core/saga version-skew (F5) is mitigated in practice by
  same-commit marketplace bumps but unpinned.

## Routing

No P0/P1 → PR-ready gate PASSES. safe_auto set (F3, F6, F7) offered for fixer dispatch;
manual set (F1, F4, F5) routes to operator decision (fix in-branch or follow-up issue).
