# Issue #350 Concurrency Policy Work Session

Date: 2026-07-15
Branch: `issue/350-concurrency-policy`
Plan: `docs/plans/2026-07-15-issue-350-concurrency-policy-plan.md`
Doc review: `docs/reviews/2026-07-15-issue-350-concurrency-policy-plan-doc-review.md`

## Summary

Implemented one bounded-concurrency policy for Saga emitters and external-engine routing. The policy
resolves run overrides, engine-registry caps, fleet-class weights, and environment defaults before work
is admitted. Layer, panel, and verifier fan-out now use a shared ordered chunker, while existing
aggregate variable names remain stable for downstream consumers.

## Implementation Units

- U1: Added `concurrency_governor.py` with the closed policy schema, defaults of 3/4/7, environment
  parsing, run overrides, engine caps, lane caps, mixed-lane accounting, and deterministic chunking.
- U2: Extended execution-spec validation and rendering so effective verification tiers are admitted
  through the same policy and retry re-resolution cannot bypass current limits.
- U3: Bounded layered, panel, and verifier emission while retaining historical aggregate bindings and
  deterministic input order across chunks.
- U4: Added an explicit spawn-site inventory and centralized executable parallel framing in one
  snapshotting helper. Structural conformance now rejects unregistered helper calls, raw literal
  delimiter sinks, indirect governed collections, mutation or alias escape before loop consumption,
  and non-chunk helper inputs.
- U5: Bumped Saga to `0.97.0`, synchronized marketplace and changelog surfaces, updated the registry
  and execution contracts, and recorded the policy decision in the engineering journal.

## Review Repairs

- Repaired the final architecture-lane collection escape: the focused structural oracle now rejects
  direct mutation, indexed replacement, rebinding, and alias escape of either governed collection
  before its outer loop consumes it. Eight mutation cases cover both verifier and worker emitters
  without changing the governor's public return type.
- Closed the final code-review set: direct chunk aliases cannot mutate a helper input; direct sink
  aliases, JavaScript trivia, and unresolved formatted callees cannot hide a raw fan-out opener;
  lane widening and multi-chunk dependency barriers have behavioral proofs; ambient shell
  concurrency is isolated from ordinary tests; and Node runtime globals may vary by supported
  version only when every discovered name remains reserved.
- Unattended cheap-to-non-cheap retries now render the climbed tier's prompt contract while retaining
  the frozen exact engine route. Capability workflow recompilation documents and tests its required
  authoritative `repo_root=` boundary.
- Corrected verification admission to use the effective tier selected after fallback, not the requested
  tier.
- Expanded conformance detection to indirect emitter paths and corrected stale contract comments.
- Hardened generated JavaScript against identifier collisions and comment/template injection by
  validating unit identifiers, reserving harness symbols and referenced JavaScript globals,
  rendering inert comments, and using JSON executable literals. Adversarial fixtures are
  syntax-checked with Node.
- Reserved iterate-to-consensus loop and reconciliation locals, added an executable Node runtime
  fixture, derived the referenced-global inventory from emitted source, and normalized whitespace
  variants in concurrency conformance detection.
- After the authorized fourth remediation attempt, reserved the complete supported runtime-global
  boundary independently of observed call syntax. The global oracle now detects bare assignments,
  object shorthand, and `URL` calls while ignoring property names.
- Statically resolved constant f-string and `.format()` emitter construction and rejected unresolved
  formatted callee slots. Regression fixtures cover both bypass forms and preserve the existing
  whitespace, split-string, and prose-only behavior.
- In the operator-approved fifth attempt, resolved both exact-engine and capability selectors to the
  selected registry lane before concurrency admission. The resolved lane is passed separately from
  the authored routing selector, and regression coverage proves both forms share a cap of one while
  ordinary units remain concurrent.
- Made fan-out detection JavaScript-trivia aware across block and line comments, then replaced the
  function-scope governor-name check with an AST dataflow proof from the governor result through the
  bounded outer chunk loop, inner thunk/verifier loop, and matching parallel open/close emissions.
  Outer-loop, worker-loop, and verifier-loop bypass mutations all fail.
- Replaced the circular production-derived runtime-global oracle with an independent ECMAScript/Node
  baseline, live Node `globalThis` readback, and a mutation test that removes `Reflect` from the
  production reservation while injecting a free `Reflect` reference.
- Preserved the original `<variable>_verdicts` aggregate binding and append later chunks with
  `.push(...)`, avoiding a compatibility regression in existing workflow consumers.
- Replaced mutable protocol attributes with read-only properties and used a bounded generic so MyPy
  verifies the new policy and emitter paths.
- In the operator-approved sixth attempt, froze one prompt and one exact resolver result per unit
  for the complete emission. Capability overlays and calibration now select the same exact registry
  lane used by admission, markers, runtime options, chunks, panels, and unattended retries; resolver
  fallback, halt, Claude substitution, and non-registry output fail closed.
- Required an explicit repository root for production capability routing, loaded overlay and strict
  chain-verified calibration snapshots once, and distinguished absent or empty ledgers from corrupt
  or unreadable ledgers. Tests may inject only a complete overlay/calibration snapshot pair.
- Reconstructed consecutive emitted JavaScript fragments with real newline joins, recognized all
  ECMAScript line terminators including U+2028/U+2029, and strengthened the source guard to require
  one dominating, un-killed governor definition through direct, `enumerate`, or structurally matched
  `zip` loops.
- Added a separate test-owned Workflow host-global oracle for `agent`, `log`, and `parallel`, with a
  mutation test for removal of every production reservation.
- Attempt-6 preflight then closed six additional findings in one repair pass. The executable-source
  guard now normalizes ECMAScript Unicode identifier escapes, recognizes parenthesized `parallel`
  callees, reconstructs output across inert Python statements, and proves every member-emitting
  statement between a paired parallel open and close is governed by the bounded chunk target.
- Repository calibration now reads and chain-verifies one strict `LedgerSnapshot`, then derives both
  Elo and provider-drift signals from those same immutable records. An interleaving regression
  corrupts the file after the first read and proves routing never observes a second revision.
- Added behavioral rejection for every independently owned Workflow host global and an explicit
  capability-provenance mismatch fixture. Corrected both tester workflow rows to bind the installed
  `tester-evidence.v1` schema to one protected composite command-output record.

## Modified Files

- `.claude-plugin/marketplace.json`
- `docs/engineering-journal/DECISIONS.md`
- `docs/plans/2026-07-15-issue-350-concurrency-policy-plan.md`
- `plugins/saga/.claude-plugin/plugin.json`
- `plugins/saga/CHANGELOG.md`
- `plugins/saga/references/concurrency-spawn-sites.md`
- `plugins/saga/references/engine-registry.yaml`
- `plugins/saga/references/execution-spec.md`
- `plugins/saga/references/sandbox-spawn-sites.md`
- `plugins/saga/scripts/concurrency_governor.py`
- `plugins/saga/scripts/engine_registry.py`
- `plugins/saga/scripts/execution_spec.py`
- `tests/test_concurrency_conformance.py`
- `tests/test_concurrency_policy.py`
- `tests/test_saga_engine_registry.py`
- `tests/test_saga_execution_spec.py`
- `tests/test_saga_plugin.py`

## Checks

- Attempt-5 focused gate: 441 tests passed across concurrency policy, conformance, execution-spec,
  and engine-registry suites.
- Attempt-5 scoped Ruff and MyPy checks passed for all changed Python and test paths.
- Attempt-5 full gate: 4,375 passed, 1 skipped at 83% coverage; Ruff, MyPy, release parity,
  marketplace synchronization, release diff guard, and `git diff --check` passed.
- Required security review blocked at 9.2/10 with four open findings: late-bound capability lane
  selection, split/Unicode JavaScript comment trivia, intervening governor-result overwrite, and a
  missing Workflow-host portion of the independent global oracle.
- The architecture child updated ignored `.coverage`; the protected mutation audit rejected that
  receipt. No architecture pass is claimed.
- Attempt-6 Sol/max repair design ran read-only with a clean repository mutation audit and a verified
  `gpt-5.6-sol`/max runtime receipt. Its diagnostic result retained the four current-code blockers;
  the root-inline design review accepted the decision-complete repair and advanced implementation.
- Attempt-6 repair authoring occurred only in a disposable `/tmp` copy. Its focused checks reported
  484 passed, 1 skipped; scoped Ruff, format, focused MyPy, and `git diff --check` passed. Root then
  reviewed and imported exactly five files.
- Root focused verification after import: 484 passed, 1 skipped across concurrency conformance,
  concurrency policy, execution-spec, and engine-registry suites; Ruff check and format passed for
  the five imported files; MyPy passed for both production modules; `git diff --check` passed.
- The first attempt-6 implementation receipt could not be sealed after a temporary edit to an
  out-of-scope production file was reverted: a subsequent `git status` refreshed the Git index stat
  cache, changing the protected index hash without staging content. The index was not manually
  rewritten. A fresh attempt-6 receipt-continuity run starts from the reviewed current content and
  re-records design, implementation, and validation evidence before preflight; this is receipt
  recovery, not a seventh code-repair attempt.
- Attempt-6 preflight: Terra/medium validation passed 485 tests plus Ruff, format, MyPy, and diff
  checks. Sol/high testing review reported one P2 and two P3 test-proof gaps; Sol/max adversarial
  review independently reproduced three P2 gaps in JavaScript source reconstruction, member-emitter
  dataflow, and calibration snapshot consistency. All six findings were accepted for repair.
- Post-repair focused verification: 494 tests passed across concurrency conformance, policy,
  execution-spec, and engine-registry suites. Scoped Ruff, MyPy, and `git diff --check` passed.
- Post-repair full gate: 4,428 passed, 1 skipped at 83% coverage. Full Ruff and format checks,
  MyPy across 243 source files, release parity, marketplace synchronization, and the changed-plugin
  release guard passed.
- The fresh Sol/max architecture seal scored 8.9/10 and found two open P2s: aggregate preflight and
  rendering can observe different mutable environment revisions, and mutation through a direct alias
  of the governed chunk collection is invisible to the conformance reaching-definition proof. The
  attempt-6 stop rule forbids another automatic repair; no acceptance receipt or code-review pass is
  claimed.
- Attempt 7 copied the supplied environment or `os.environ` once into an immutable emit-scoped
  mapping and reused it for aggregate validation, worker chunks, verifier admission, and retries. It
  also tracked top-level direct aliases in the reaching-definition proof. Both exact regressions
  failed before the repairs and passed afterward. The broad focused run reached 495 passing tests
  before one stale source-fixture variable name failed; after updating that fixture, all 48
  conformance tests passed.
- The frozen attempt-7 review barrier used verified `gpt-5.6-sol`/max architecture and security
  contexts plus `gpt-5.6-sol`/high testing. Its before/after workspace audit was clean. The reviews
  recorded six P2 findings, one duplicated across testing and security, and one P3 documentation
  finding. The unique repair set is: verifier/retry environment and lane consumer-matrix tests;
  compound-statement and helper/unbound-call alias escape handling; real JavaScript close pairing;
  fragment preservation across proven read-only output-list access; and the execution-spec reference
  correction. The attempt-7 stop rule prohibits automatic repair.
- Attempt 8 replaced sibling-only alias checks with conservative compound-aware alias transfer,
  paired JavaScript closes lexically across comments, strings, and templates, preserved pending
  fragments across proven read-only output access, added the full 3x5 environment/lane consumer
  matrix, and corrected the exact-lane provenance contract. Its focused gate passed 73 conformance,
  54 policy, 24 mutation-subset, and 15 consumer-matrix cases.
- Attempt 8's verified Sol/max and Sol/high review barrier reproduced three remaining P2 oracle
  bypasses: governed mutation inside an inner member loop, regex-literal false closes, and fragments
  emitted through a pre-bound output alias. The Terra/medium validator otherwise passed the bounded
  concurrency behavior.
- Attempt 9 used a fresh host-verified `gpt-5.6-sol`/max design context. It accepted a three-repair,
  test-only design at 9.625/10, and its protected before/after audit reported no workspace mutation.
- Attempt 9 now transfers governed alias state through the full member-loop body and its back edge,
  recognizes JavaScript regex literals and character classes while failing closed on ambiguous slash
  contexts, and reconstructs fragments through straight-line and dominated aliases of `lines`.
- Attempt-9 focused verification passed 101 conformance and 54 policy cases (155 total). Scoped Ruff
  and `git diff --check` passed with all caches outside the worktree.
- Attempt 9's fresh review barrier used host-verified `gpt-5.6-sol`/max adversarial,
  `gpt-5.6-sol`/high testing, and `gpt-5.6-terra`/medium validator contexts. The shared protected
  before/after audit reported no workspace mutation. The validator passed all four required cases.
- The Sol/high reviewer found one P2 chained-output-alias bypass. Sol/max independently confirmed
  that bypass and added two P2s: an alias introduced through a governed inner-loop header can grow
  the iterated collection, and an unresolved Name-valued emitted fragment can hide a nested open so
  its close terminates the outer parallel region early. Root reproduced all three mutations; each
  returned normally from `assert_conformance`.
- Per the operator-approved attempt-9 stop rule, no automatic repair, full gate, integration, commit,
  or PR is claimed. Attempt 10 requires explicit operator approval.
- The operator approved Attempt 10 as a consolidation pass. A fresh host-verified
  `gpt-5.6-sol`/max architecture review accepted the bounded design at 9.8/10 with no findings, and
  its protected before/after audit reported no workspace mutation.
- Attempt 10 introduced one private `_emit_parallel_wave` helper that snapshots each supplied
  governor-derived chunk before invoking its member renderer. The verifier-panel and worker-layer
  paths are its only call sites and retain their existing JavaScript bindings, ordering, delimiters,
  gates, and reconciliation behavior.
- The 1,905-line test-only Python/JavaScript mini-analyzer was replaced with a focused structural AST
  contract. It requires the two inventoried direct governor-to-loop-to-helper paths and prohibits raw
  parallel delimiter sinks outside the helper. It handles direct collection, chunk, and list-sink
  aliases plus the JavaScript trivia needed to recognize a fan-out call, without restoring a general
  Python dataflow engine or complete JavaScript parser.
- Attempt-10 initial focused verification passed 420 tests across conformance, policy, and
  execution-spec suites. The Terra/medium validator independently passed a 521-test superset, and
  Sol/high testing review accepted with no findings.
- Sol/max adversarial review found three bounded structural holes: a direct chunk rebind before the
  helper, a helper load through a local alias, and raw delimiters through augmented assignment or
  constant concatenation. Attempt 10 now rejects those forms without adding general alias dataflow or
  JavaScript parsing. A fresh follow-up reproduced one residual form: nesting the rebind and helper
  call in the same statement block bypassed the direct-loop scan. The structural contract now requires
  each helper call to be a direct expression in the governed loop body, and the exact nested mutation
  is covered. The repaired structural suite has 35 cases; the 545-test repaired superset, Ruff,
  format, full-project MyPy across 243 source files, and `git diff --check` pass.
- The final agent-native code review selected correctness/adversarial, security/API, and
  testing/reliability lenses. It found nine unique P2s; all are fixed and regression-tested. The only
  production defect was a climbed unattended retry reusing the original cheap-tier prompt while its
  options and schema came from the climbed tier. The remaining findings closed conformance and test
  proof gaps plus the stale capability-recompile documentation contract.
- The final immutable receipt-chain architecture lens found one additional P2 structural mutation:
  a raw parallel opener bound to a local static name before `lines.append` bypassed direct sink
  inspection. The guard now rejects raw delimiter literals at any assignment site outside the sole
  framing helper, and the exact local opener/closer mutation passes as a kill test. The focused
  conformance and policy suites pass 92 tests after the repair.

- `RUFF_CACHE_DIR=/private/tmp/issue350-final-ruff uv run ruff format --check .` - 395 files already formatted.
- `RUFF_CACHE_DIR=/private/tmp/issue350-final-ruff uv run ruff check .` - passed.
- `MYPY_CACHE_DIR=/private/tmp/issue350-final-mypy uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`
  - passed across 243 source files.
- `PYTHONDONTWRITEBYTECODE=1 COVERAGE_FILE=/private/tmp/issue350-postalias-finalfull.coverage uv run pytest -p no:cacheprovider`
  - 4,437 passed, 1 skipped; 83% total coverage on the final formatted tree.
- `uv run bandit -q -ll plugins/saga/scripts/concurrency_governor.py plugins/saga/scripts/engine_registry.py plugins/saga/scripts/execution_spec.py`
  - no medium- or high-severity findings in changed production Python surfaces. The repository-wide
    baseline still reports pre-existing findings outside this issue's diff.
- Release parity, marketplace synchronization, and the changed-plugin release-surface diff guard:
  26 focused checks passed.
- `git diff --check` - passed.

## Residual Risk

The conformance inventory makes new Saga Python emitter paths fail closed, but non-Python runtime
integration remains part of the outcome-level cross-runtime acceptance node rather than this leaf.
Attempt 10 removes the prior broad alias and JavaScript grammar attack surface by centralizing
executable parallel framing. Its structural guard is intentionally limited to that production
boundary rather than attempting arbitrary Python or JavaScript semantic equivalence; static raw
delimiter bindings fail at assignment before they can flow to a sink. Full implementation and
code-review checks are green; the final verified reviewer barrier, integration, issue closeout, and
PR publication remain pending.
