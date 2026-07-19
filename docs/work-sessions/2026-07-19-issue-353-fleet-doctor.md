# Work session — issue #353 fleet doctor cross-source audit (2026-07-19)

- **Saga:** `issue-353` (lifecycle work) · branch `work/353-fleet-doctor` from `origin/main`
  `97d2fb15` (carries merged #604 + #358) · worktree `.claude/worktrees/issue-353-fleet-doctor`
- **Plan:** `docs/plans/2026-07-15-issue-353-fleet-doctor-plan.md` (outcome-branch copy is the
  authority; ceremony anchor `d10d602e…` over 5695 section bytes approved by Jeff in-session
  2026-07-18, recorded commit `24813d8a`; codex second opinion adjudicated pre-execution — two
  P2s fixed with the anchor byte-identical)
- **Outcome leaf:** `sub-353` of `lease-safe-runtime-continuity`, dispatched attempt 1 (scoped
  one-leaf advance, quiesce envelope bypassed under the satisfied operator gate), leaf saga id
  `leaf-lease-safe-runtime-continuity-sub-353`

## Built (by unit)

- **U1** (`2b3d4914`) — `plugins/saga/scripts/fleet_doctor.py` strict observation layer: closed
  `fleet_doctor_report.v1`, capped bounded readers (pre-stat → `O_RDONLY|O_NOFOLLOW` → post-stat,
  mid-scan change = incomplete), independent #351 hash-chain re-derivation with the documented
  torn-tail tolerance, `Redactor` path policy, deterministic sorted report, fail-closed 0/1/2
  exit contract.
- **U2** (`9c56b1f1`) — managed-worktree + terminal-resource reconciliation: both drift
  directions (`stale-worktree` / `dangling-registry`) from git porcelain + filesystem +
  registry triangulation, `ownership-drift` (path mismatch, fencing drift, broker-only lease),
  `terminal-resource-open` (released/already-absent teardown vs live lease, closed-owner
  admissions, close-receipted fences), `retained` disposition = warning by design (KTD4 scope:
  `.saga-worktrees/<outcome>/<subplot>` only).
- **U3** (`fafaa7ab`) — dispatch + delegation correlation: settlement view over the
  chain-verified facts keyed by exact `(dispatch_id, unit_id, attempt)`, outcome-ledger commit
  events as the independent observation (KTD3: one fact never proves a launch), the two broker
  agent-lease vocabularies, `receiptless-delegation` vs `delegation-evidence-error` split with
  a conformance-tested `bridge_receipt.v1` gate, 30-position stability matrix.
- **U4** (`ee4d9f1c`) — production CLI + `/fleet-doctor` command + skill + machine-checked
  source matrix (`references/fleet-doctor-sources.md`); AST mutation-import/call denylist and
  read-only conformance oracles; no repair surface exists (`--fix`/`--reap`/`--retry`/
  `--watch`/`--fixture` all rejected).
- **U5** (`6ce73825` + `300db775`) — release surfaces saga 0.103.0 → 0.104.0 (plugin.json /
  marketplace / CHANGELOG / version guards / README) and the docs-model + manual card for the
  25th command file (24 routable); journal entries DECISIONS
  `{#fleet-doctor-independent-audit-353}`, LEARNINGS `{#fleet-doctor-census-353}`.

## Key decisions in execution

- The doctor never imports a producer (KTD1): the conformance suite loads the REAL producers to
  build genuine bytes in fixtures, then the doctor's own strict readers parse them — the test
  asymmetry is the proof of independence.
- Absence / corruption / incompleteness are three verdicts (KTD2): every cap, unsafe path, or
  mid-scan change fails closed to exit 2; nothing ever truncates to clean.
- The receipt gate re-derives fleet-core's canonical `validate_receipt` verdict instead of
  importing it, with a fixture-matrix equality proof (conformance-vs-runtime split).
- The run-facts source verdict is `verified-prefix`, deliberately: the hash chain proves the
  surviving prefix only, and whole-record trailing truncation is undetectable by design — the
  bound is documented in the module, source matrix, skill, and command doc.

## Checks run

Focused suites grew 45 → 64 → 114 → 137 across U1–U5 + remediation
(`tests/test_fleet_doctor.py` + `tests/test_saga_plugin.py`; 92 doctor oracles). Full
repository gate green twice: at `300db775` (pytest 5180/0/1) and re-run after remediation at
`1efd8121` — pytest 5203 passed / 0 failed / 1 skipped, `ruff check` + `ruff format --check`,
mypy 267 files, bandit at the house baseline (`{LOW: 755, MEDIUM: 3, HIGH: 1}` — the three
doctor Lows are the fixed-argv subprocess trio), release parity, marketplace sync, BOTH CI
validators (`marketplace/validator/validate.py` + `scripts/validate_plugins.py`), release-surface
diff guard, whitespace. `GATE_OVERALL=0`.

Gate-fix commit `300db775` before round 1: the docs-model coverage suite machine-models the
command surface (`saga-docs-model.yaml` + manual + README + coverage pins) and the pre-branch
tree was already one command stale — all four surfaces re-pinned at 25 files / 24 routable
with a full fleet-doctor card.

## Six-lens cc-workflow ceremony (anchor `d10d602e…`, approved 2026-07-18)

Reviewers devils-advocate / security / architecture / testing at opus+high; validators
event-flow / scenarios at sonnet+medium; every lens `saga:readonly-verifier` + worktree
isolation; bounded pool 3.

- **Round 1** `wf_b00a5c5d-9d3` at `300db775` — 6/6 lenses. P0=0 **P1=1 P2=6 P3=3**; validators
  event-flow (95) and scenarios (95) clean with hands-on fixture-driven validation (all disease
  paths, retry-generation attempt keying, text/json parity, before/after no-write hashing).
  Findings: OSError text defeats the redactor in default mode (security P1, reproduced
  end-to-end), uncaught `os.open` OSError (security P2), symlinked run-facts ledger degrades to
  absent/exit 0 (devils-advocate P2), receipt-subset vs canonical validator divergence in both
  directions (architecture P2), dead `MAX_DEPTH` constant + five untested caps + entry-cap
  proven at 1 of 7 sites (testing P2×3), truncation bound undisclosed (devils-advocate P3),
  control characters unsanitized in text rendering (security P3), three uncovered
  reconciliation branches (testing P3).
- **Remediation 1** `1efd8121` — `_safe_oserror()` (errno+strerror, never a filename) routed
  through every OSError interpolation site with induced-failure redaction oracles; `_open` seam
  + `os.scandir` enumerations fail closed to `unsafe-path`/exit 2; symlinked ledger reaches the
  strict reader; `_receipt_subset_valid` rewritten as an exact canonical-mirror (18-fixture
  equality matrix incl. optional-field and type-divergent corruption); `_require_depth`
  enforced at all four enumerations; artifact/git-stdout/git-stderr/git-timeout/output caps
  each got a tripping oracle; entry-cap sites normalized to one post-append `>` pattern with
  per-site oracles + exact-boundary clean proof; verdict renamed `verified-prefix` with the
  bound documented; `_sanitize_text` in the text renderer; broker-absent drift /
  already-absent teardown / late-delivery oracles. Focused pair 137 passed; full gate green at
  `1efd8121`; LEARNINGS `{#error-text-defeats-redaction-353}`.
- **Round 2** `wf_5fc0fea2-990` at `1efd8121` — 4 affected lenses fresh. Devils-advocate (95),
  security (95), testing (95) **clean** with all nine of their r1 fixes adjudicated
  fixed-adequately at the byte level (security independently probed `_safe_oserror` and
  re-grepped every path-bearing interpolation; testing re-enumerated all 20 emitted
  classifications and all 10 caps against real tripping oracles). Architecture (60) adjudicated
  the receipt fix **not-fixed** — a 300k-sample fuzz against the real fleet-core module proved
  exactly one residual divergence class (canon accepts `transport: null`, the subset rejects
  it), breaching the fix's exact-equality claim — and filed one new **P2**: an unhashable
  transport (JSON array/object) crashes `transport not in _RECEIPT_RUNNER_FIELDS` with an
  uncaught `TypeError` out of `run_scan` (the canonical validator crashes on the same input).
- **Remediation 2** — `isinstance(transport, str)` guard closes the TypeError fail-open; the
  equality claim replaced with the truthful, pinned relation: verdict equality wherever the
  canon is well-defined, plus ONE enumerated deliberate divergence (every non-string transport
  rejected fail-closed, where the canon accepts `null` and crashes on unhashables) asserted by
  the conformance test itself; end-to-end oracles for both degenerate classes
  (`delegation-evidence-error`, exit 2, no traceback); the canon's two gaps queued upstream as
  QUEUED `{#bridge-receipt-transport-hardening}` (KTD8 keeps fleet-core untouched this
  release). Focused pair 139 passed.

## Next step

On round-3 convergence (architecture lens fresh): programmatic `/code-review` (capture
`REVIEWED_SHA`), `/qa`, PR, merge under Jeff's standing outcome approval, leaf harvest with
`leaf_saga_id` backfill, board reconcile.
