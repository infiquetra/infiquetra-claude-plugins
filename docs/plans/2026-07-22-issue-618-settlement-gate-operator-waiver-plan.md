---
title: "Issue 618: settlement-gate operator waiver"
type: fix
status: active
date: 2026-07-22
---

# Issue 618: settlement-gate operator waiver

## Summary

Give the outcome coordinator's settlement gate an operator waiver: a provenance-stamped, append-only
run-ledger fact that lets `advance` dispatch new frontier units past a halt-required prior cohort,
without mutating any settlement truth. The waiver is snapshot-scoped — any *new* blocking information
after the grant re-halts automatically (fail-closed).

---

## Problem Frame

Defect infiquetra/infiquetra-claude-plugins#618: the settlement gate
(`plugins/saga/scripts/outcome.py:1197-1224`) blocks every NEW frontier unit while any prior dispatch
cohort has `halt_required=True`, and the operator has no input into that check — `approve` (R20,
revision-scoped) does not touch it. `halt_required` derives as
`progress_halt = not current_complete or unresolved_threshold_breach`
(`plugins/saga/scripts/dispatch_settlement.py:1059`), so **both** an open (honestly in-flight) unit and
a threshold-0 casualty breach deadlock all new dispatch until the blocked unit fully delivers.

First occurrence: outcome `l2-consent-registration` (issue body) — worked around by settling
`silent-no-op` + `claim-retry` + dispatching manually outside `advance`, leaving dispatch records that
did not reflect reality (the anti-goal). Second occurrence is live in this repo: outcome
`governed-execution-integrity` cohort
`outcome:ee6590d89de1aff1cadb5e8c621b8b8b:frontier:6be9782deb6268350d4b9b36` (threshold 0, sub-633
settled `delivered`, four honestly-open units) settlement-halts sub-615's dispatch on every tick, with
durable halt receipts in `.git/saga-outcomes/governed-execution-integrity/ledger.jsonl`. On the
`inline` backend every leaf runs externally over days, so a prior cohort being "incomplete" is the
*normal* state of a healthy DAG — the gate as shipped deadlocks routine outcome progress.

---

## Requirements

- R1. A new `outcome.py waive <outcome-id> --dispatch-id <id> --reason <text> --answerer <who>` verb
  records a provenance-stamped (`waived_by`, `transport`, `at`, `reason`, blocking-roster snapshot)
  append-only `dispatch-waiver` fact in the repo run ledger. `--reason` and `--answerer` are required;
  `--transport` follows the `approve` provenance convention (provenance, not authorization).
- R2. `advance` dispatches new frontier units when every halt-required report is covered by an active
  waiver; the `settlement-halt` receipt no longer fires for covered reports.
- R3. A report NOT covered — no waiver, or blocking information newer than the waived snapshot —
  halts exactly as today, with the existing receipt shape and reason text naming only the uncovered
  dispatch ids.
- R4. Waiver grant validates its target loudly: the dispatch id must have a manifest in the ledger and
  its report must currently be halt-required. Waiving an unknown or healthy cohort is a
  `DispatchSettlementError`, never a silent success.
- R5. No settlement truth is mutated: classifications, `halt_required`, the silent-no-op
  no-fabricated-evidence rule, and every existing fact schema stay byte-identical. Ledgers written
  before this change parse unchanged; ledgers containing waiver facts do not error older readers of
  the settlement stream (they simply keep halting — fail-closed).
- R6. A dispatch that proceeds under waiver leaves a durable `settlement-waived` receipt in the
  outcome store ledger: one receipt per newly dispatched unit, mirroring the halt receipt's per-sid
  shape, naming every covered dispatch id and its waiver provenance. Idempotent via
  `_append_ledger_once`, keyed on subplot id + a digest over the sorted covering-waiver roster
  digests — repeated ticks under the same coverage append nothing; a re-waive (changed roster)
  mints a fresh receipt.
- R7. The waive verb is idempotent: re-granting an identical blocking-roster snapshot is a reported
  no-op success, not a duplicate fact and not an error.
- R8. Release surfaces move in the same PR: saga `plugin.json` 0.108.0 → 0.109.0,
  `.claude-plugin/marketplace.json`, saga `CHANGELOG.md`, drift-guard pins, and a
  `docs/engineering-journal/DECISIONS.md` entry for KTD1-KTD5.
- R9. Live acceptance: on the real halted cohort
  `outcome:ee6590d89de1aff1cadb5e8c621b8b8b:frontier:6be9782deb6268350d4b9b36`, `waive` + `advance`
  dispatches sub-615 (record-only inline dispatch) and settlement-halt receipts stop accruing for that
  cohort; evidence captured in the work-session doc. Runs only under explicit operator go at `/work`
  end (it mutates the live outcome ledger).

---

## Key Technical Decisions

- KTD1 — Fix direction: operator waiver only (issue direction 1); directions 2 and 3 deferred.
  A waiver clears *both* halt branches. Direction 3 (renegotiable `casualty_threshold_percent` via
  `repost`) cannot fix the `not current_complete` branch (`dispatch_settlement.py:1059`) that is
  actually halting both known occurrences. Direction 2 (`deferred-external` classification) is the
  core of #626's external-executor settlement model — an adjacent leaf blocked on this one; landing a
  narrow version here would collide with that design. The waiver is the minimal honest unlock.
- KTD2 — The waiver is a NEW run-fact kind (`dispatch-waiver`), never a new event under
  `dispatch-settlement`: the settlement event schema is closed and re-validated per record on every
  snapshot read (`_canonical_fact` `dispatch_settlement.py:392-453`, `_validate_stored_fact` :456,
  `_verified_snapshot` :951-958) — an unknown event would crash every older reader sharing the clone,
  including the byte-frozen codex runtime (`infiquetra-codex-plugins` carries its own
  `run_ledger.py`/`dispatch_settlement.py` copies). `run_ledger.FACT_KINDS` is enforced at build time
  only (`run_ledger.py:112`); the read path only hash-chains — so a new kind written by new code is
  invisible to old readers: they keep halting (fail-closed) and never error. `"dispatch-waiver"` is
  added to `FACT_KINDS` in this repo.
- KTD3 — Coverage-snapshot subset rule: the waiver stores the blocking roster at grant time — the
  set of `(unit_id, attempt, state)` pairs currently causing `halt_required` — and at gate time covers
  the report iff the *current* blocking roster is a subset of the waived roster. Deliveries shrink the
  roster (waiver stays valid; no re-waive churn as the live cohort's four units settle over days); any
  NEW blocking fact — a fresh casualty, a new attempt cohort, a newly spawned-and-open unit — falls
  outside the snapshot and re-halts with no operator action. Rejected: an unconditional per-dispatch
  waiver (silently suppresses future breaches); whole-report-digest invalidation (every benign
  delivery would demand a re-waive — four re-waives on the live cohort alone).
- KTD4 — Report honesty preserved; waiver applied at the outcome frontier gate only.
  `CasualtyReport.halt_required` remains the honest derived signal everywhere; only the gate at
  `outcome.py:1197-1224` partitions covered/uncovered, and every covered dispatch is visible via the
  R6 receipt. The per-unit terminal-attempt halts (`outcome.py:1414-1441`, `:1481-1500`) and the
  non-outcome sites (`team-execution`, `workflow`) are untouched; #626 may extend.
- KTD5 — The waiver is machine-local, matching the R20 approval precedent: the run ledger lives at
  `<git-common-dir>/saga-run-facts/run-facts.jsonl` (`run_ledger.py:78-80`), never committed. On a
  different machine the halt reappears and the operator re-waives there — fail-closed, and the
  provenance stays with the machine whose operator granted it (same trade `approve_frontier` already
  makes with `_approvals_dir`, `outcome_decompose.py:388-397`).

---

## High-Level Technical Design

Grant path: `outcome.py waive` → resolves the run ledger (`run_ledger.RunLedger.resolve(root)`) →
`dispatch_settlement.record_waiver` recomputes the target's `settlement_report`, derives its blocking
roster, refuses non-halted or manifest-less targets (R4), and appends the `dispatch-waiver` fact
(idempotent on roster digest, R7).

Gate path (each `advance` tick): the existing block at `outcome.py:1197-1224` computes
`outcome_reports` as today, then partitions halt-required reports by
`dispatch_settlement.active_waiver_covers(ledger, report)` — a pure derive-on-read predicate (no
caching, consistent with R17). Uncovered reports halt exactly as before; when all are covered, the
manifest/dispatch flow proceeds unchanged and a `settlement-waived` receipt is appended once per
(subplot, waiver-digest). No state machine is added; the waiver is one more fact consulted by the
level-triggered reconcile loop.

---

## Implementation Units

### U1. Waiver primitives in dispatch_settlement

One new fact kind with its own closed schema, plus the roster derivation and coverage predicate —
site-agnostic core, no outcome.py knowledge.

**Goal:** `record_waiver`, `active_waiver_covers`, and `blocking_roster` exist, validated, hash-chained,
and invisible to settlement-stream readers.

**Requirements:** R1 (fact shape), R4, R5, R7.

**Dependencies:** none.

**Files:** `plugins/saga/scripts/dispatch_settlement.py`, `plugins/saga/scripts/run_ledger.py`
(FACT_KINDS entry), `tests/test_dispatch_settlement.py`.

**Approach:** `WAIVER_KIND = "dispatch-waiver"` added to `run_ledger.FACT_KINDS`.
`blocking_roster(report) -> frozenset[tuple[str, int, str]]` derives, from a `CasualtyReport`, the
`(unit_id, latest_attempt, state)` pairs that make `halt_required` true — units whose latest state is
not a `LEDGER_CLASSIFICATIONS` member (open/unspawned) plus unresolved casualties feeding a breach.
`waiver_fact(...)` builds the closed-schema fact (`dispatch_id`, `waived_by`, `transport`, `reason`,
sorted roster, roster digest via `evidence_digest`) with its own canonicalizer mirroring the
`_canonical_fact` field-exactness discipline — validated only by waiver readers, never by
`_validate_stored_fact`. `record_waiver(ledger, dispatch_id, *, at, waived_by, transport, reason)`
requires a manifest and a currently halt-required report, is idempotent on identical roster digest.
`active_waiver_covers(ledger, report)` is true iff any stored waiver for the dispatch has
`blocking_roster(report) ⊆ waived_roster`. A `waive` subcommand lands beside the existing CLI verbs
(`dispatch_settlement.py:1675+`) for site-agnostic use, with flags matching the fact's own field
names: `--dispatch-id`, `--at`, `--waived-by`, `--reason` (all required) and `--transport`
(optional).

**Patterns to follow:** fact builders + canonicalizers at `dispatch_settlement.py:282-453`; idempotent
append discipline of `ensure_manifest` (:472-498); identifier/reason bounds via `_identifier` /
`_bounded_text`.

**Test scenarios:**
- Happy path: manifest + open unit → `record_waiver` succeeds; `active_waiver_covers` true.
- Delivery shrinks the roster: settle one waived-open unit `delivered` → waiver still covers.
- New casualty after grant: settle a unit `rate-killed` (new pair) → waiver no longer covers.
- New attempt cohort after grant (claim-retry spawn) → waiver no longer covers.
- Grant against a dispatch with no manifest → `DispatchSettlementError`.
- Grant against a healthy (non-halted) cohort → `DispatchSettlementError` (R4).
- Duplicate grant, identical roster → single fact, reported no-op (R7).
- Old-reader isolation: ledger containing a waiver fact → `settlement_report` and
  `_verified_snapshot` succeed and ignore it; chain verifies (R5).
- Empty reason / empty waived_by rejected; over-length reason rejected via `_bounded_text`.

**Verification:** all new scenarios green in `uv run pytest tests/test_dispatch_settlement.py -q`;
no existing settlement test touched.

### U2. Gate integration and the operator verb in outcome.py

The frontier gate honors coverage; the operator gets a first-class `waive` verb with `approve`-style
provenance.

**Goal:** a fully-waived halt dispatches with a visible receipt; an uncovered halt is byte-identical
to today.

**Requirements:** R1 (verb surface), R2, R3, R6.

**Dependencies:** U1.

**Files:** `plugins/saga/scripts/outcome.py`, `tests/test_outcome_command.py`.

**Approach:** in the settlement block (`outcome.py:1197-1224`), partition `blocking_reports` into
covered/uncovered via `dispatch_settlement.active_waiver_covers`; halt only on uncovered (reason text
names only uncovered dispatch ids); when dispatch proceeds under coverage, append one
`settlement-waived` receipt per dispatched sid through `_append_ledger_once` keyed
`settlement-waiver:<sid>:<digest16>` where the digest is `evidence_digest` over the sorted
covering-waiver roster digests — the receipt names every covered dispatch id and its provenance,
mirroring the halt receipt's per-sid shape (R6). New `waive` subparser (beside `approve`,
`outcome.py:2470`) with `--dispatch-id`, `--reason`, `--answerer` (required), `--transport` (optional,
`approve` convention); handler resolves `run_ledger.RunLedger.resolve(root)`, calls
`record_waiver` mapping `--answerer` to the fact's `waived_by` field, prints the record JSON.

**Patterns to follow:** `approve` verb wiring (`outcome.py:2628-2645`) and `approve_frontier`
provenance semantics (`outcome_decompose.py:367-397`); `_append_ledger_once` keying of the existing
settlement-gate receipt (`outcome.py:1216-1223`).

**Test scenarios:**
- Halted cohort + covering waiver → `advance` dispatches the new unit; `settlement-waived` receipt
  present; no `settlement-halt` receipt for that tick.
- No waiver → halt receipt byte-shape unchanged (regression guard for R3).
- Stale waiver (new casualty after grant) → halt returns, reason names the dispatch id.
- Two blocking reports, one covered → still halts, reason names only the uncovered id.
- Receipt idempotence: repeated `advance` ticks under the same waiver append one receipt per sid.
- Two blocking reports each covered by a distinct waiver → one receipt per dispatched sid naming
  both covered dispatch ids; a re-waive after roster change mints a receipt under the new digest.
- Verb error paths: unknown outcome id, dispatch without manifest, healthy cohort → non-zero exit
  with the loud error.
- Verb happy path: JSON output carries `waived_by`, `transport`, `reason`, roster digest.

**Verification:** all new scenarios green in `uv run pytest tests/test_outcome_command.py -q`; full
battery, ruff (check + format), mypy, bandit clean at the branch head.

### U3. Release surfaces and journal

Ship the metadata story with the diff, per repo policy.

**Goal:** installed-plugin metadata tells the same story as the code.

**Requirements:** R8.

**Dependencies:** U1, U2.

**Files:** `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
`plugins/saga/CHANGELOG.md`, `docs/engineering-journal/DECISIONS.md`, drift-guard pins in
`tests/test_saga_plugin.py` (verify the exact pin set at implementation time — the 0.108.0 bump
touched `test_saga_plugin.py`, `test_liveness_events.py`, `test_team_execution_liveness.py`).

**Approach:** saga 0.108.0 → 0.109.0 everywhere the parity checker looks
(`scripts/check_release_surface_parity.py` clean); CHANGELOG entry for the waiver verb + gate change;
DECISIONS entry recording KTD1-KTD5 with the rejected alternatives and a "revisit when" pointing at
#626's settlement model.

**Test expectation:** none — release-surface parity is enforced by the existing drift-guard tests and
parity script; no new behavior.

**Verification:** `uv run pytest tests/test_saga_plugin.py -q` green;
`python3 scripts/check_release_surface_parity.py` clean.

---

## Scope Boundaries

Out of scope (true non-goals for this leaf):

- Any change to settlement classifications or their semantics — `deferred-external` belongs to #626
  (external-executor settlement model), which this leaf must not pre-empt.
- `casualty_threshold_percent` renegotiation via `repost` (issue direction 3) — does not fix the
  completeness branch; revisit inside #626 if still wanted.
- The per-unit terminal-attempt halt paths (`outcome.py:1414-1441`, `:1481-1500`) — honest per-unit
  terminal states, not cohort gates.
- Non-outcome settlement sites (`team-execution`, `workflow`) honoring waivers.
- The byte-frozen `outcome_compat` seam and any codex-side mirroring (codex#45 sequencing) — the
  codex runtime stays waiver-unaware and fail-closed until its re-freeze.
- #615 (workflow lease seam), #616/#617 (lease_broker registry), #620 (board-sync), TOCTOU
  `audit_store.py:194`.

Deferred to follow-up work:

- Waiver revocation verb and a `report`/`status` view listing active waivers — nice-to-have
  observability; the R6 receipt covers the audit need now.
- Cross-machine waiver travel (committing waivers to the outcome branch) — deliberately not done
  (KTD5); revisit if multi-host coordination lands (#617/Herdr arc).

---

## Risks & Dependencies

- Race between grant and a settling unit: the gate recomputes the roster under `_verified_snapshot`
  each tick; a post-grant settle either shrinks the roster (delivered — still covered) or adds a
  blocking pair (casualty — re-halts). Both directions are safe; no lock needed beyond the ledger's
  own append lock.
- Cross-runtime asymmetry: the codex coordinator on a shared clone keeps halting until codex#45
  re-freezes the ported surfaces. Mitigation: note the new kind in the codex#45 retarget comment at
  harvest time — it is additive, so the re-freeze picks it up wholesale.
- Roster-derivation drift: `blocking_roster` must stay faithful to `settlement_report`'s own halt
  derivation (:1045-1059) or coverage could disagree with the halt it suppresses. Mitigation: derive
  the roster from the same `CasualtyReport` entries the halt derives from, and pin the equivalence
  with a property-style test (roster empty ⇔ halt_required false) in U1.

---

## Sources

- Gate: `plugins/saga/scripts/outcome.py:1197-1224` (frontier settlement block), `:1414-1441` and
  `:1481-1500` (per-unit terminal halts, untouched), `:2628-2645` (approve wiring).
- Report derivation: `plugins/saga/scripts/dispatch_settlement.py:961-1068` (`settlement_report`,
  `progress_halt` :1059), `:39` (CASUALTY_CLASSIFICATIONS), `:392-458` (closed schema + per-read
  validation), `:1561-1577` (`outcome_reports`), `:1514-1527` (frontier identity).
- Ledger: `plugins/saga/scripts/run_ledger.py:44-55` (FACT_KINDS), `:78-80` (resolve path),
  `:104-121` (build_fact kind check — write-side only).
- Provenance precedent: `plugins/saga/scripts/outcome_decompose.py:367-403` (`approve_frontier`,
  machine-local `_approvals_dir`).
- Defect: infiquetra/infiquetra-claude-plugins#618 (first occurrence + three fix directions); live
  second occurrence: `.git/saga-outcomes/governed-execution-integrity/ledger.jsonl` settlement-halt
  receipts for sub-615, cohort `outcome:ee6590d89de1aff1cadb5e8c621b8b8b:frontier:6be9782deb6268350d4b9b36`.
