---
target: branch work/637-refuse-mode-hardening (diff 47dacede..e86a4b45)
reviewed_revision: e86a4b45
blocked: false
verdict: CLEAN
scope_check: CLEAN
linked_issue: infiquetra/infiquetra-claude-plugins#637
linked_plan: docs/plans/2026-07-21-issue-637-refuse-mode-hardening-plan.md
work_sessions:
  - docs/work-sessions/2026-07-21-issue-637-work-halt-stale-hooks.md
  - docs/work-sessions/2026-07-22-issue-637-refuse-mode-hardening-work.md
date: 2026-07-22
mode: programmatic (driven by /work)
backend: inline (3 lens spawns, saga:readonly-verifier + worktree, opus; 1 Stage-B validator, sonnet)
---

# Code review — issue #637 refuse-mode hardening

**Verdict: CLEAN — not blocked.** No P0/P1/P2. One P3 found, independently validated, and
repaired in the same commit that lands this artifact (docs-only delta over `e86a4b45`,
delta-adjudicated below). REVIEWED_SHA `e86a4b45`, diff base `47dacede` (= origin/main at
review time; merge-base re-verified fresh).

## Scope

Commit `e86a4b45` (14 files, +382/−29: `lease_broker.py`, `outcome_dispatcher.py`,
`outcome.py`, 6 test files, 2 plugin.json, marketplace.json, 2 CHANGELOGs) plus four docs-only
commits (`26c9281a`, `cde45a38`, `30db8761`, `d23a6d6c` — plan artifacts and halt forensics).
Excluded from review: the operator's uncommitted `docs/outcomes/external-engine-offload/report.md`
edit and untracked `docs/sdlc-issue-drafts/*` (not part of this change).

## Scope check — CLEAN

- **Intent**: the two validated P3 advisories from #627's CLEAN review — pid-liveness at the
  refuse-mode admission gate, and a typed transient/permanent dispatcher contract with loud
  tick-abort for permanent faults — plus release surfaces (plan U1–U3).
- **Delivered**: exactly that; no unrelated files, no "while I was in there" changes.

## Plan-completion audit (R1–R9)

| Req | State | Evidence |
| --- | --- | --- |
| R1 dead owner supersedes, no TTL wait | DONE | `lease_broker.py:2175-2178`; `test_refuse_mode_admits_crash_orphan_without_ttl_wait`, `..._admits_after_reboot_without_ttl_wait` |
| R2 live AND unknown refuse (fail-closed) | DONE | `_owner_state:3908-3918` tri-state; `!= "dead"` guard; pid-None/unreadable-identity tests |
| R3 no same-owner bypass | DONE | condition has no owner comparison; `test_refuse_mode_refuses_same_owner_when_live` |
| R4 typed transient/permanent contract | DONE | `DispatcherLeaseTransientError` (`outcome_dispatcher.py:66`), shim-safe classifier (`:79-92`); full raise-site enumeration below |
| R5 transient branch byte-preserving | DONE (wording nuance → finding #1) | transient arm executable body byte-identical to base; the pin test's raise type updated to the subclass — behavior pin intact |
| R6 permanent fault aborts loudly, before release/ledger | DONE | `outcome.py:1603-1604` precedes release `:1625`, ledger `:1633`, settle `:1647`; coordinator lock freed by outer `finally :1072-1073`; `test_advance_permanent_dispatcher_fault_aborts_tick_loudly` |
| R7 no new LEDGER_CLASSIFICATIONS, shapes unchanged | DONE | diff shows no vocabulary or halt-record shape change |
| R8 release surfaces in the same PR | DONE | 0.18.0/0.108.0 across plugin.json + marketplace.json + CHANGELOGs + drift pins; parity script clean |
| R9 full battery green | DONE | pytest 5329 passed/1 skipped; ruff check + format clean; mypy clean; bandit no new findings (all 6 highs pre-existing/vendored) |

## Lens results (3 lenses, all citations re-verified at `e86a4b45`)

**U1 correctness/reliability — zero findings.** Cross-host safety proven structurally: the
refuse condition short-circuits on `_expired` (boot-id guard `lease_broker.py:1824-1825`, boot
id per-host per-boot `:469-496`), so a cross-host prior never reaches the local pid probe;
`_owner_state:3909-3910` independently maps boot mismatch to dead-by-supersede. The
probe-then-supersede sequence is atomic under the exclusive `flock` (`:2297`, `:1579`); pid
reuse is neutralized by the `owner_process_start` identity check (`:3915-3918`).
Settlement-retained (`:2159-2162`) and canonically-closed (`:2163-2171`) precedence preserved;
supersede path byte-untouched; `_owner_state` and its sweep (`:3964`) / recovery (`:4209`)
consumers unmodified.

**U2 contract completeness — zero findings.** Every `DispatcherError` construction site
enumerated: permanent (plain) at `outcome_dispatcher.py:98` (protocol skew), `:204` (malformed
request), `:263` (shim load), `:323` (non-conflict admission failure), `:363` (release refused
— integrity fault); transient (subclass) at `:320` (admission `LeaseConflictError`), `:330`
(lost authority), `:335` (renew failure), `:346` (lost authority during settlement), `:374`
(lease disappeared at release). Matches plan R4's named set exactly — no lease-lifecycle raise
left plain, no permanent fault typed transient. Shim class identity holds (`fleet_commons_shim`
memoizes via `sys.modules`, `fleet_commons_shim.py:149-152`) so the `isinstance` classification
cannot false-negative across loads. Exception chaining and primary-error precedence preserved.

**Tests/conventions/release surfaces — one finding (#1).** The six U1 tests drive the real
`_owner_state` probe through fake runtime providers (not a mocked probe); the zero-mutation
test asserts byte-identical registry state; both contract directions pinned including an
explicit `assert not isinstance(..., DispatcherLeaseTransientError)` on the permanent arm;
targeted suites 180 passed in the reviewer's worktree; parity clean; no attribution lines;
security checklist full pass (no new subprocess/network/file-permission/injection surface).

## Findings

| # | Sev | File | Issue | Confidence | Validation | Route | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | P3 | plugins/saga/CHANGELOG.md:19 | Entry claimed `test_advance_records_lease_refusal_as_halt_and_continues` is "green unmodified"; the same commit changed that test's raise from `DispatcherError` to `DispatcherLeaseTransientError` (necessary — production now emits the subclass at that site). Behavior claim true; "unmodified" false. | 100 | validated (independent Stage-B validator: quote + diff evidence confirmed, no disclosure elsewhere) | safe_auto | REPAIRED — reworded to "stays green (its dispatcher raise updated to the transient subclass…)" in the commit landing this artifact |

Suppressed below confidence 75: none (nothing suppressed). Over-budget validator drops: none
(1 survivor, cap 15).

## Delta adjudication (repair over REVIEWED_SHA)

The repair delta over `e86a4b45` is docs-only: the CHANGELOG rewording plus this artifact.
No production code, test, or release-surface bytes changed after review — finding #1 resolved,
zero new findings. The review verdict CLEAN carries to the repaired head.

## Coverage and residual risk

- In-run refute-3 workflow panels (6/6 upheld) were treated as advisory; this review is the
  independent gate and re-derived the load-bearing claims from source.
- Residual: the R6 loud-abort intentionally leaves the `dispatch-{sid}` store lock held until
  the 900 s stale-reclaim — an operator-adjudicated tradeoff (plan KTD3), documented in code.
- Defect #615 (workflow children cannot bind a fleet lease) remains open and is out of scope
  here; #637's changes do not touch that seam.

## External opinion

`external_opinion.state=none` — stored preference `none` for this stage; no external engine
consulted.
