# Issue #350 Concurrency Policy Code Review

Date: 2026-07-16
Target: branch `issue/350-concurrency-policy`
Base revision: `99549aaa2c4cae3003bdb14cd5b71b2bd46b27fd`
Issue: `infiquetra/infiquetra-claude-plugins#350`
Plan: `docs/plans/2026-07-15-issue-350-concurrency-policy-plan.md`
Work session: `docs/work-sessions/2026-07-15-issue-350-concurrency-policy.md`
Backend: agent-native Saga code review
Verdict: CLEAN AFTER REPAIR

## Scope Check

Scope Check: CLEAN

The diff is limited to the concurrency governor, Saga emission and routing integration, the
concurrency inventory, contract and release documentation, and tests required by issue #350. It
does not add a runtime scheduler, change credentials, deploy, or alter another plugin's behavior.

## Review Lenses

- Sol/max correctness and adversarial review: policy precedence, retry semantics, exact-lane
  routing, ordered chunk emission, aggregate guards, and structural bypasses.
- Sol/high security and API review: environment and identifier trust boundaries, generated
  JavaScript safety, resource amplification, routing identity, and compatibility contracts.
- Sol/high testing, reliability, and maintainability review: behavioral proof completeness,
  environment isolation, runtime-version coupling, and focused-oracle maintainability.

Conditional deploy and migration lenses were not selected because this change has neither a deploy
surface nor a data migration.

## Built Versus Planned

COMPLETION: 5/5 DONE, 0 PARTIAL, 0 NOT-DONE, 0 CHANGED, 0 UNVERIFIABLE

- U1 DONE: the closed governor schema resolves spec, environment, run, fleet tier, and exact engine
  lane limits with strict validation and the approved precedence.
- U2 DONE: engine, tier, read-only, lane, mixed-cohort, and retry admission use the same policy.
- U3 DONE: worker, panel, and verifier fan-out emit stable ordered chunks, preserve historical
  bindings, and enforce the aggregate ceiling and dependency barriers.
- U4 DONE: the inventory and focused AST conformance guard bind both executable fan-out sites to a
  direct governor, governed collection, loop chunk, and centralized framing helper.
- U5 DONE: Saga `0.97.0`, marketplace metadata, changelog, reference docs, tests, and the engineering
  journal are synchronized.

## Findings and Resolutions

All findings were reproduced or confirmed against the merge-base diff before repair.

- P2 `architecture.mutable-governor-collection-escape` — FIXED. The structural guard rejects direct
  mutation, indexed replacement, rebinding, and alias escape of `panel_chunks` or `layer_chunks`
  before loop consumption. Eight mutations cover both sites.
- P2 `conformance-indirect-sink-bypass` — FIXED. Direct aliases of `lines.append`, `extend`, or
  `insert` are treated as output sinks; an aliased raw `parallel` opener fails conformance.
- P2 `SEC-350-1` — FIXED. Raw opener recognition accepts JavaScript whitespace and comments and
  rejects unresolved f-string or `.format()` callees that can synthesize a fan-out call.
- P2 `SEC-350-2` — FIXED. The direct loop chunk cannot be rebound, mutated, passed through an
  unproven use, or escaped through an alias before `_emit_parallel_wave` snapshots it.
- P2 `retry-stale-tier-prompt` — FIXED. An unattended retry renders `_agent_prompt` from the climbed
  unit while retaining the frozen exact route. Cheap-to-non-cheap coverage proves the retry drops
  budget and pull-cord riders and uses the non-cheap return schema.
- P2 `ambient-concurrency-env-test-leak` — FIXED. An autouse fixture clears the operator's ambient
  `SAGA_MAX_CONCURRENT`; explicit precedence tests continue to supply their own environment. The
  ordinary emitter test passes with inherited values `1` and `invalid`.
- P2 `node-global-oracle-version-coupling` — FIXED. The independent baseline and every live Node
  `globalThis` name must be reserved, without requiring two supported Node builds to expose identical
  global inventories.
- P2 `lane-widening-precedence-unproved` — FIXED. A five-unit exact lane proves a cap of five can
  widen above a lower spec and environment base through both direct resolution and
  `concurrency_chunks`.
- P2 `multi-chunk-dependency-barrier-unproved` — FIXED. A dependent unit is asserted to begin only
  after the close of the final chunk in its six-unit prerequisite layer.
- P2 `API-350-1` — FIXED. The reference and changelog document the authoritative `repo_root=`
  requirement for capability-routed workflow recompilation; tests cover both the explicit-root and
  fail-closed missing-root paths.
- P2 `architecture.conformance-local-string-alias-bypass` — FIXED. The guard rejects a raw parallel
  delimiter literal at its static assignment site outside `_emit_parallel_wave`, so binding an
  opener or closer to a local name before appending it cannot evade sink inspection. The exact local
  opener/closer mutation is regression-tested.

No P0, P1, unresolved P2, or P3 findings remain.

## Validation

- Full repository tests: 4,437 passed, 1 skipped; 83% coverage.
- Focused repaired concurrency and execution-spec suite: 444 passed.
- Structural conformance suite: 36 cases, including mutation-kill coverage for both production sites.
- Ruff lint and format check: passed; 395 files formatted.
- MyPy: passed across `plugins/`, `scripts/`, and `tests/` (243 source files).
- Changed-production Bandit at medium/high severity: clean.
- Release parity, marketplace synchronization, and changed-plugin release guard: 26 checks passed.
- `git diff --check`: passed.

## Residual Risk

The structural oracle intentionally proves the two inventoried Python emitter boundaries; it is not
a general Python alias engine or complete JavaScript parser. Raw parallel delimiter literals fail at
their assignment or output boundary, including local static bindings. A new executable fan-out site
must add an inventory row and a bounded detector. Cross-runtime Claude/Codex behavior remains the
downstream outcome acceptance node's responsibility rather than this repository leaf.

## Route

Proceed to the final verified reviewer barrier and integration gate.
