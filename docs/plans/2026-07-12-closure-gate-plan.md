---
title: Closure gate — /outcome refuses to close a leaf on missing, stale-SHA, or unsuperseded-FAIL evidence
type: feat
status: active
date: 2026-07-12
origin: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T7.json
---

# Closure gate — /outcome refuses to close a leaf on missing, stale-SHA, or unsuperseded-FAIL evidence

## Summary

Build `plugins/saga/scripts/closure_gate.py` — a read-only consumer of the now-merged evidence
ledger (`evidence_ledger.py`, #398/PR #567) — and wire its verdict into
`outcome_orchestrator.harvest()`'s completion-barrier check, so a leaf is never harvested as `done`
without passing its declared required checks at the exact SHA the outcome is closing at, and a
FAIL can never be silently cleared by an unexplained later PASS.

## Problem Frame

`outcome_orchestrator.harvest()` materializes a leaf as `done` the moment `barrier_satisfied()`
reports the leaf's PR merged or its tracking issue closed (`plugins/saga/scripts/
outcome_orchestrator.py:145-172`). That check never reads an evidence ledger, never checks whether
a required check's evidence was recorded against the SHA the outcome is actually closing at, and
never asks whether a FAIL result was later silently overwritten by a PASS. The grounding brief for
this ideation wave records the exact incident this guards against: "a probe script overwriting a
FAIL evidence artifact with a later PASS" (`docs/plans/2026-07-03-plugin-fleet-grounding-
brief.md:150-151`). #398 shipped the append-only, content-addressed ledger that makes such a
tamper detectable and a supersession explicit; this issue is the consumer that reads that ledger
at harvest time and refuses closure until it is satisfied.

## Requirements

- **R1.** A required check whose chain holds a FAIL at the outcome's close SHA, followed only by an
  unexplained later verdict (no justification attached), derives HALT — closure is refused.
- **R2.** Once a justified supersession is attached to the entry that follows the FAIL (a named
  reason), and that entry is non-FAIL, closure proceeds for that check.
- **R3.** A required check whose only evidence exists at a SHA other than the outcome's current
  close SHA derives HALT `stale-sha:<check_id>`.
- **R4.** A required check with zero evidence entries anywhere in the ledger derives HALT
  `missing-evidence:<check_id>`.
- **R5.** A required check whose latest verdict *at the matching close SHA* is still FAIL (no later
  attempt at all) derives HALT `unresolved-fail:<check_id>` — merged-but-still-failing is not closed.
- **R6.** A required check whose latest verdict at the matching close SHA is non-FAIL, with no
  unresolved supersession gap, is satisfied and does not block closure.
- **R7.** `outcome_orchestrator.harvest()` never writes a `done` completion event for a node until
  the closure gate is satisfied for every check the node declares required.
- **R8.** A node that declares no `required_checks` is unaffected — the gate is trivially satisfied,
  so every existing outcome spec (none of which declare this field today) keeps its current
  behavior exactly.
- **R9.** The gate derives its verdict purely on read, every call, from the ledger plus the node's
  own declared contract — no new committed or cached closure-status field, and no
  degraded/best-effort close on any check failure (HALT-not-degrade, matching the existing
  `barrier_satisfied` posture this gate augments).
- **R10.** Full repo gate stays green (`uv run pytest`, `ruff format --check`, `ruff check`, `mypy
  plugins/ scripts/ tests/ --ignore-missing-imports`) and release surfaces (`plugin.json`,
  `marketplace.json`, `CHANGELOG.md`, drift-guard tests) ship in the same PR.

## Key Technical Decisions

**KTD1 — The required-check set and an optional SHA override live in `node.evidence`.** `Node`
already carries `evidence: dict[str, Any]` as an open pass-through map explicitly documented as the
seam future consuming units extend (`plugins/saga/references/outcome-spec.md:54`: "detailed
schemas land in the consuming units"). This issue is the first consumer to give it a concrete
schema: `evidence["required_checks"]` (`list[str]` of `check_id` values, e.g. `["qa",
"code-review"]`) and an optional `evidence["reviewed_sha"]` override. Rejected: a new top-level
`Node` field (schema surgery on an already-reserved seam for no benefit) or a separate spec-adjacent
file (an extra artifact when `evidence` already exists precisely for this).

**KTD2 — Close-SHA resolution: explicit override wins; else derive from the PR head for a `code`
node.** `node.evidence["reviewed_sha"]` wins when present. Otherwise, for `kind == "code"`, derive
from `outcome_github.head_ref_oid(node.github["pr"])` — the PR's pre-merge head commit SHA, which
is exactly the SHA `/qa` and `/code-review` reviewed against (`REVIEWED_SHA=$(git rev-parse HEAD)`
on the feature branch, per `qa/SKILL.md:299` and `code-review/SKILL.md:341`) — **not** the
post-squash merge-commit SHA that lands on `main`, which never matches any evidence entry and would
make every code leaf's stale-SHA check permanently, spuriously unsatisfiable. A `non-code` node
with no override and no PR has no derivable close SHA; if it declares `required_checks` anyway, the
gate HALTs `unresolvable-close-sha` rather than silently skipping the check (R9).

*Verified, not asserted:* `head_ref_oid` remains resolvable on a merged PR even after its head
branch is deleted — confirmed empirically against this very outcome's own sibling PR (#567,
merged, `headRefOid: 22a66d1825cdea3b259d1dc4c07fcc3ae1e9a7c8`) whose branch
`work/398-evidence-ledger` no longer exists on `origin` (`git ls-remote --heads origin
work/398-evidence-ledger` returns empty). GitHub retains the head SHA on the PR object independent
of ref lifetime, so post-merge branch deletion (this repo's own default hygiene) never breaks
close-SHA resolution.

**KTD3 — Supersession is a `payload["supersession_reason"]` convention, not a new ledger entry
kind.** `evidence_ledger.write()`'s `payload` is an explicitly open, downstream-extensible dict
(evidence-ledger plan R10: "sub-397 (closure gate) extend this module without schema surgery").
The producer that knowingly supersedes a known prior FAIL sets
`payload={"supersession_reason": "<reason>"}` on that later write. Rejected: adding a `kind:
"supersession"` entry type to the already-merged, already-tested ledger schema — that is schema
surgery on a shipped module for a distinction the open payload dict already carries for free.

**KTD4 — One small additive read helper on `evidence_ledger.py`: `history(store, check_id=...)`.**
`evidence_ledger.latest()` is already scoped to one exact `(check_id, reviewed_sha)` pair, so it
cannot by itself distinguish "this check never ran" (R4, missing-evidence) from "this check ran,
but only at a different SHA" (R3, stale-sha). `history()` returns every evidence entry for
`check_id` across every `reviewed_sha`, letting the gate tell the two apart. Additive only — no
change to any existing `evidence_ledger.py` signature or storage format.

**KTD5 — The gate calls `evidence_ledger.verify_chain(store)` once per evaluation before trusting
any read.** `verify_chain` is already shipped, read-only, and idempotent (it raises on tamper,
otherwise returns a report with no side effects) — reusing it here means a tampered chain HALTs the
gate (typed, named) rather than silently trusting a `latest()`/`history()` read taken from a
compromised log.

**KTD6 — `harvest()` and `barrier_report()` gain a new keyword-only `repo_root: Path = Path(".")`.**
The evidence ledger lives at a committed, repo-tree path (`docs/evidence/<saga-id>/`) — distinct
from the git-common-dir cache the existing `store` argument already resolves — so `harvest()` needs
repo-root context it does not carry today. Defaulting to `Path(".")` keeps the ~11 existing test
call sites and every outcome spec that declares no `required_checks` (i.e. every spec that exists
today) behaving exactly as before; only a node that opts into `required_checks` needs a correctly
threaded `repo_root`. The two real production call sites
(`outcome.py`'s `production_harvester`, both closures) already have `repo_root` in scope and are
updated to pass it through explicitly.

**KTD7 — Verdict classification is closure_gate's own closed vocabulary, not
`evidence_ledger.latest()`'s `superseded_fail` flag (added during implementation).**
`evidence_ledger.latest()` hardcodes a literal `"FAIL"` sentinel for its own supersession
detection — correct for a synthetic fixture, but blind to what the shipped producers actually
write: `/qa` records `ship` / `ship-with-deferred` / `no-ship` (never `"FAIL"`/`"PASS"` literally)
and `/code-review` records `clean` / `blocked`. Relying on the literal sentinel would have silently
treated a real `no-ship`/`blocked` verdict as satisfied — exactly the silent-pass failure mode this
issue exists to kill. `closure_gate.py` therefore reads `evidence_ledger.history()` directly and
classifies each entry against its own closed vocabulary (`_FAIL_VERDICTS` = `{FAIL, no-ship,
blocked}`, `_PASS_VERDICTS` = `{PASS, ship, ship-with-deferred, clean}`); an unrecognized string
HALTs `unrecognized-verdict:<check_id>` rather than being assumed to pass (HALT-not-degrade, R9).
No change to `evidence_ledger.py` itself beyond the already-planned additive `history()` helper.

## Implementation Units

### U1. `closure_gate.py` — chain reader, supersession validator, SHA-match, typed verdict

**Goal:** New `plugins/saga/scripts/closure_gate.py` exposing `evaluate(node, *, repo_root,
github_runner=None) -> GateVerdict` (a frozen dataclass: `subplot_id`, `satisfied: bool,
halt_reason: str | None`, `reason: str`, `checks: list[dict]` — one entry per declared required
check with its verdict/attempt/matched-SHA/superseded-fail/justified detail). Implements R1-R6 and
R9 per KTD1-KTD5: resolve the close SHA (KTD2); for each `required_checks` entry, call
`evidence_ledger.verify_chain` (KTD5) then `evidence_ledger.latest`/`evidence_ledger.history`
(KTD4) to classify missing / stale / unresolved-fail / unsuperseded-fail / satisfied; the first
failing check (in declared order) becomes `halt_reason`, all checks are still evaluated into
`checks` for observability. Also adds `evidence_ledger.history()` (KTD4) and a small `evaluate`
CLI subcommand (`python3 closure_gate.py evaluate --repo-root . --spec <spec.json> --subplot-id
<id>`, printing the verdict as JSON) for operator debugging outside a live harvest tick, mirroring
the dual-surface convention `evidence_ledger.py`/`manifest_store.py` already use.

**Requirements:** R1, R2, R3, R4, R5, R6, R9.

**Dependencies:** none (consumes the already-merged `evidence_ledger.py` and `outcome_spec.Node`
as-is).

**Files:** `plugins/saga/scripts/closure_gate.py` (new), `plugins/saga/scripts/evidence_ledger.py`
(add `history()`), `tests/test_closure_gate.py` (new).

**Approach:** Pure function over an injectable `github_runner` (mirrors `outcome_orchestrator`'s
own `barrier_satisfied` signature style) so the module is unit-testable offline against a temp
evidence-ledger directory, no real `gh` calls. `Store.for_saga(node.leaf_saga_id, repo_root)`
resolves the ledger location exactly as `evidence_ledger.py`'s own CLI does.

**Patterns to follow:** `plugins/saga/scripts/outcome_orchestrator.py`'s `BarrierVerdict` dataclass
shape and `barrier_satisfied()`'s pure-function/injectable-runner style; `evidence_ledger.py`'s
`Store.for_saga` / typed-error-on-HALT conventions.

**Test scenarios:** the issue's own Verification section runs `pytest tests/test_closure_gate.py -k
<substring>` for five exact substrings plus a separate `-k golden_fixture` pass — each test
function's **name must literally contain** the paired substring below or that `-k` filter matches
zero tests (a silent "no tests ran", not a real pass) at PR time:

- `test_closure_gate_matching_sha_pass_closes` — happy path, matching-SHA PASS with no supersession
  gap → `satisfied=True` (R6).
- `test_closure_gate_golden_fixture_fail_overwritten_by_unexplained_pass` — **the golden fixture**
  reproducing the grounding-brief incident verbatim (a FAIL, then an unexplained later verdict at
  the same SHA with no `supersession_reason`) → `satisfied=False`,
  `halt_reason="unsuperseded-fail:<check_id>"` (R1). Name contains **both** `golden_fixture` and
  `fail_overwritten_by_unexplained_pass` so both of the issue's `-k` filters match this one test.
- `test_closure_gate_fail_superseded_with_justification` — FAIL then a later verdict at the same
  SHA carrying `payload={"supersession_reason": "..."}` → `satisfied=True` (R2).
- `test_closure_gate_stale_sha_halts` — evidence exists for the check only at a different SHA than
  the resolved close SHA → `halt_reason="stale-sha:<check_id>"` (R3).
- `test_closure_gate_missing_evidence_halts` — no evidence entries anywhere for the check →
  `halt_reason="missing-evidence:<check_id>"` (R4).
- `test_closure_gate_unresolved_fail_halts` — latest (and only) verdict at the matching SHA is
  FAIL, no later attempt → `halt_reason="unresolved-fail:<check_id>"` (R5).
- `test_closure_gate_repeat_fail_pass_cycle` — a second FAIL→justified-PASS cycle after an earlier
  cycle already resolved (FAIL, justified PASS, fresh FAIL, justified PASS) → `satisfied=True`,
  proving the justification check keys off the **latest** entry's own payload, not a global
  once-ever flag (regression guard for R1/R2's interaction).
- `test_closure_gate_no_required_checks_trivially_satisfied` — node declares no `required_checks`
  → `satisfied=True` trivially, no ledger read attempted (R8).
- `test_closure_gate_reviewed_sha_override_for_non_code_node` —
  `node.evidence["reviewed_sha"]` override resolves the close SHA for a `non-code` node with no PR
  (KTD2).
- `test_closure_gate_unresolvable_close_sha_halts` — `non-code` node with `required_checks` set but
  no override and no PR → `halt_reason="unresolvable-close-sha"` (KTD2 edge).
- `test_closure_gate_empty_leaf_saga_id_halts` — `required_checks` declared but `node.leaf_saga_id`
  is empty (a malformed/hand-authored spec that bypassed normal dispatch) →
  `halt_reason="unresolvable-close-sha"`, never a crash or a silent pass (defensive; dispatch always
  sets `leaf_saga_id` before a node can reach `running`/PR-open in the normal path, per
  `outcome_dispatcher.py:187`, but the gate must not trust that invariant blindly).
- `test_closure_gate_tamper_detected_halts` — hand-edited artifact bytes on disk after a PASS write
  → `evaluate()` surfaces the `verify_chain` failure as a HALT rather than a stale trusted read
  (KTD5).
- `test_closure_gate_cli_evaluate_prints_verdict` / `test_closure_gate_cli_evaluate_unknown_subplot`
  — the CLI `evaluate` subcommand against a small fixture spec + saga-id prints the verdict JSON
  and exits 0 on satisfied; an unknown `--subplot-id` exits non-zero with a clear message.

**Verification:** `uv run pytest tests/test_closure_gate.py -v` (every scenario above green) plus
the issue's own exact named checks: `uv run pytest tests/test_closure_gate.py -k
fail_overwritten_by_unexplained_pass`, `-k fail_superseded_with_justification`, `-k
stale_sha_halts`, `-k missing_evidence_halts`, `-k matching_sha_pass_closes`, `-k golden_fixture` —
each must select at least one test (never "no tests ran").

### U2. Wire the gate into `outcome_orchestrator.harvest()` and `barrier_report()`

**Goal:** After `barrier_satisfied()` reports a node satisfied, call `closure_gate.evaluate(node,
repo_root=repo_root, github_runner=github_runner)`; a node whose gate is not satisfied is **not**
harvested (no completion event written) this tick — same silent-skip shape `harvest()` already
uses for a GitHub-unsatisfied barrier, so a later reconcile tick re-evaluates once the gate clears.
`barrier_report()` (the derived-on-read report the `/outcome` cockpit consumes) also runs the gate
and merges its verdict into each node's reported dict under a `closure_gate` key, so an operator
sees *why* closure is stuck (a named HALT reason) even when the GitHub-only barrier itself already
reads satisfied. Thread the new `repo_root` parameter (KTD6) through both functions and through
`outcome.py`'s two `production_harvester` call sites (`plugins/saga/scripts/outcome.py:1117,1128`),
both of which already close over `repo_root`.

**Requirements:** R7, R9.

**Dependencies:** U1.

**Files:** `plugins/saga/scripts/outcome_orchestrator.py`, `plugins/saga/scripts/outcome.py`,
`tests/test_outcome_orchestrator.py` (new).

**Approach:** Insert the gate check as a second condition inside `harvest()`'s per-node loop,
immediately after the existing `if not verdict.satisfied: continue` line — `if not
gate_verdict.satisfied: continue` — before any completion-event write. Do not change
`BarrierVerdict`'s own shape or `barrier_satisfied()`'s signature (existing callers/tests of that
function are untouched); the gate is a second, additive check `harvest()` performs, not a rewrite
of the first.

**Patterns to follow:** `plugins/saga/scripts/outcome_orchestrator.py`'s existing
`harvest()`/`barrier_report()` loop structure and the `payload["contract"]`/manifest-pointer
attach-if-available pattern already in `harvest()` (mirror its "attach only when resolvable, never
fail the harvest on an unrelated absence" posture for `closure_gate`'s own resolution).

**Test scenarios (`tests/test_outcome_orchestrator.py`, new file — function names must literally
contain the paired `-k` substring the issue's own Verification section runs):**

- `test_outcome_orchestrator_gate_blocks_harvest` — a `code` node with `barrier_satisfied()` (via a
  fake `github_runner` reporting the PR merged) satisfied, but a required check with no evidence
  entry recorded (a real, un-stubbed `closure_gate.evaluate` call against an empty ledger dir) →
  `harvest()` returns an empty harvested list for that node and writes no completion event (the
  issue's own `-k gate_blocks_harvest` check).
- `test_outcome_orchestrator_gate_allows_harvest_when_satisfied` — same setup, but the required
  check's evidence is written as a matching-SHA PASS before calling `harvest()` → the node IS
  harvested, exactly as today's contract.
- `test_outcome_orchestrator_harvest_backward_compatible_default_repo_root` — a node with no
  `required_checks` declared, `harvest()` called with no explicit `repo_root` → behaves
  byte-identically to pre-change `harvest()` (regression guard for KTD6's default; this is what
  keeps every pre-existing `tests/test_outcome_*.py` call site green unmodified).
- `test_outcome_orchestrator_barrier_report_surfaces_closure_gate_halt` — `barrier_report()`'s
  per-node dict includes a `closure_gate` sub-key naming the HALT reason when the gate blocks an
  otherwise-satisfied node.

**Verification:** `uv run pytest tests/test_outcome_orchestrator.py -k gate_blocks_harvest -v` (the
issue's own named check, matched by the first scenario above) plus the full new file green, plus
confirming every pre-existing `tests/test_outcome_*.py` file (`test_outcome_completion.py`,
`test_outcome_integration.py`, `test_outcome_liveness.py`, `test_outcome_board_sync.py`,
`test_outcome_report.py`, `test_outcome_reconcile.py`, `test_outcome_from_objective.py`,
`test_outcome_worktrees.py`, `test_outcome_economics.py`, `test_outcome_graph_edit.py`,
`test_outcome_projection.py`, `test_outcome_backends.py`) still passes unmodified (KTD6's
backward-compatibility claim, verified not just asserted).

### U3. Document the `node.evidence` schema on the outcome-spec reference

**Goal:** Extend `plugins/saga/references/outcome-spec.md`'s Node-shape table row for `evidence`
(today: "open pass-through map[s]; detailed schemas land in the consuming units") with the concrete
schema this issue gives it: `required_checks: list[str]` and the optional `reviewed_sha` override,
plus a short paragraph on the HALT-reason vocabulary (`missing-evidence:<id>`, `stale-sha:<id>`,
`unresolved-fail:<id>`, `unsuperseded-fail:<id>`, `unresolvable-close-sha`) so a future reader of
the spec format does not have to reverse-engineer it from `closure_gate.py`.

**Requirements:** none directly (documentation only) — supports the discoverability the other
units' R-IDs depend on being findable.

**Dependencies:** U1, U2 (the schema and HALT vocabulary must be final before documenting them).

**Files:** `plugins/saga/references/outcome-spec.md`.

**Test expectation:** none -- documentation only, no behavioral surface to test.

### U4. Release surfaces + full CI gate

**Goal:** `plugins/saga/.claude-plugin/plugin.json` 0.81.0 → 0.82.0; matching
`.claude-plugin/marketplace.json` entry regenerated via `python3 scripts/sync_marketplace.py`
(never hand-edited); `plugins/saga/CHANGELOG.md` entry describing the new closure gate, its HALT
vocabulary, and the `node.evidence["required_checks"]` schema; confirm existing version/metadata
drift-guard tests stay green. Full repo gate green (R10).

**Requirements:** R10.

**Dependencies:** U1, U2, U3.

**Files:** `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
`plugins/saga/CHANGELOG.md`.

**Test expectation:** none -- release bookkeeping; covered by existing drift-guard tests and the
full-suite run below.

**Verification:** `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run
mypy plugins/ scripts/ tests/ --ignore-missing-imports` all green.

## Risks & Dependencies

- **Signature change blast radius.** `harvest()`/`barrier_report()` gain a new keyword-only
  `repo_root` parameter. Mitigation: defaulted (KTD6) so all ~11 existing `tests/test_outcome_*.py`
  call sites and the two real production call sites in `outcome.py` keep working; only nodes that
  opt into `required_checks` need it threaded correctly, and both real call sites already have
  `repo_root` in scope.
- **Unenforced supersession convention.** `payload["supersession_reason"]` (KTD3) is a convention,
  not schema-validated by `evidence_ledger.py` itself — a producer could omit it on a legitimate
  re-run and trip an `unsuperseded-fail` HALT. This is the intended HALT-not-degrade failure
  direction (mirrors the self-certification HALT precedent in #398's KTD4): a spurious HALT is
  safe and recoverable (the operator adds the reason and the next attempt clears it); a spurious
  silent pass would not be.
- **Dependency:** requires #398's `evidence_ledger.py` and its `/qa`/`/code-review` wiring already
  merged to `main` (confirmed: PR #567, saga 0.81.0).

## Scope Boundaries

Out of scope (from the issue, binding):

- The evidence-ledger producer itself, or any change to its storage format beyond the one additive
  `history()` read helper (KTD4) — #398 already shipped and is not reopened here.
- Any change to `/qa` or `/code-review`'s verdict logic, severity model, or write mechanism — this
  issue only reads what they already write.
- Retroactively re-validating or repairing evidence recorded before this gate ships.
- Any change to `{#readonly-verifier-fallback-ladder-325}` itself.

Deferred to follow-up work (not non-goals):

- A dedicated `outcome_report.py` ambiguity-tier entry for a closure-gate HALT (today it surfaces
  via `barrier_report()`'s per-node `closure_gate` key, U2, not through
  `outcome_report.py`'s `TIER_AMBIGUITY` scan) — a follow-up if operators need it in the standard
  ambiguity report rather than the raw barrier report.
- Cross-process ledger locking — unchanged from #398's own deferred item; still single-writer-per-
  branch today.
- Extending required-check gating to non-`code` nodes without an explicit `reviewed_sha` override —
  today such a node HALTs rather than silently skipping (KTD2); a future issue could add a
  non-code-native close-SHA source (e.g. a tracking-issue close event hash) if that need arises.

## Execution prerequisites

**Backend/tier.** Inline, Sonnet, medium effort — per the issue's own recommended executor
profile: bounded, mechanically-testable wiring against an already-documented `dod_sketch`/
`ac_sketch` pair with no open architectural ambiguity, and a verifier-of-record closure decision
that must not be delegated to an external engine (`{#external-engines-never-gatekeepers}`, #283).

**Recorded override (recommended-vs-chosen).** `lifecycle_state.py recommend-backend` (probed
Workflow-tool availability, absent in this session) mechanically returned `team-execution`, purely
because this plan's `phase_count` (4 units) crosses the tool's own volume/sequencing threshold —
a signal its own docstring explicitly flags as "OUTPUT-BLIND... volume and sequencing, not
governance," not a security/infra/cross-repo/deployment/consensus signal. Overridden to `inline`
given the issue's own authored executor profile and this leaf's single-agent execution setup;
recorded here and in the plan-phase saga tick rather than silently accepted or hidden.

**Branch and merge target.** Leaf work branches from `main` (e.g. `work/397-closure-gate`); the PR
merges to `main`. The outcome branch `outcome/evidence-integrity` holds only the spec — the outcome
coordinator harvests sub-397 completion from the merged PR.
