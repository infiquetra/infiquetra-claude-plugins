# Code review — #652 gate-before-resolve exit-code contract

- **Unit:** `review-652` of run `orch-2026-08-24-787`. Authority: the *Saga Code Review contract*
  section of issue 787 (operator-approved 2026-08-24), which supersedes the built-in thresholds,
  averaging, cycle count, rerun policy, and terminal outcomes for this run.
- **Mode:** interactive, `inline` backend, no external engine (operator-directed). No advisory
  external seat was requested, launched, or consumed.
- **Target:** pull request 802, branch `orch/orch-2026-08-24-787-b4-652`.
- **Reviewed revision (cycle 1):** `6c3588f028358a86e0da81e08648804d2e3268e1`.
- **Repaired revision (cycle 2):** `44946060f2e7d6531eee4d7ab8f86d60a0565451`.
- **Diff base:** `593361b902c5318aab3c52002d781a458e9adfc1` — verified merge-base with
  `origin/main`, which is post-#799.
- **Leaf:** issue 652. **Plan section:** `docs/plans/2026-08-24-defects-claude-plugins-run-plan.md`
  U10 (KTD4, pinned by S3 finding F16).
- **Terminal outcome: `accepted`** at `44946060`. All ten selected lenses independently at or above
  9.0; no applicable dimension below 7.0; every independent gate passed. Two cycles of the three
  allowed were used.
- **No saga write.** `saga.py scan` returned zero candidates, so there is no work-thread saga to
  append `review_paths` to.

## Built-versus-planned audit

**Scope check: CLEAN.**

- *Intent* — restore the pre-#620 command-line exit-code contract: a certificate-gated operation
  returns `status=gated` / exit 0 even where mission-control is unresolvable, while a non-gated
  operation there still fails loud with exit 1.
- *Delivered* — exactly that, in the two command entry points the leaf and the plan name, plus
  their tests, the saga release surfaces, and (after repair) the engineering-journal entry.

| Plan requirement (U10) | State | Evidence |
| --- | --- | --- |
| Evaluate the certificate first, resolve the mission-control root only on `AUTHORIZED` (the pinned shape, not the lazy-factory fork) | DONE | `plugins/saga/scripts/board_progression.py:540-560`, `plugins/saga/scripts/reconcile_controller.py:414-441` |
| Acceptance criterion 1 — gated operation, unresolvable install, `gated` / exit 0 | DONE | `tests/test_board_progression.py::test_cli_gated_op_unresolvable_mission_control_still_gated_exit_zero`, `tests/test_reconcile_controller.py::test_cli_reconcile_gated_op_unresolvable_mission_control_still_gated_exit_zero` |
| Acceptance criterion 2 — non-gated operation, unresolvable install, exit 1 with the resolution error | DONE | `tests/test_board_progression.py::test_cli_authorized_op_unresolvable_mission_control_exits_nonzero`, `tests/test_reconcile_controller.py::test_cli_reconcile_unresolvable_mission_control_exits_nonzero` |
| Acceptance criterion 3 — regression tests in both modules | DONE | both modules above |
| "New moving parts: none" | CHANGED, disclosed | the repaired revision adds one private module-level stand-in writer, `board_progression._gated_writer`. It is a safety stand-in for an argument the gated path must still pass, not a new mechanism; see finding 1 |
| Saga release surfaces bumped coherently | DONE | `plugin.json`, `.claude-plugin/marketplace.json`, `CHANGELOG.md`, and the drift pin `tests/test_saga_plugin.py:47` all read `0.139.4` against `origin/main` at `0.139.3` |

**Deliberately untouched, and correctly so.** Three other `resolve_mission_control_root` call sites
exist — `plugins/saga/scripts/outcome_board_sync.py:133`, `plugins/saga/scripts/outcome.py:2821`,
and `plugins/saga/scripts/pulse.py:100`. The first is inside `_schema_path`, whose caller
`reconcile_board` converts any exception into a per-operation `failed` record by its own KTD4
contract, so no exit-code surface is involved. The leaf's out-of-scope section excludes the #620
fix itself. Not a requirements gap.

## Lens team

Ten of the fourteen roster lenses selected. `inline` backend; no subagents spawned, so the
concurrency cap is not engaged.

| Lens | Class | Selected because |
| --- | --- | --- |
| correctness | always-on | — |
| security | always-on | — |
| testing | always-on | — |
| architecture-maintainability | always-on | — |
| api-contract | conditional | the change alters a command-line exit-code contract that `/work`, `/loop`, and `orchestrate` all read |
| reliability | conditional | it reorders the failure-handling path that decides whether a consumer sees `gated` or `failed` |
| adversarial | conditional | it moves an authorization gate and rests on an assumption about two verdicts agreeing |
| documentation-clarity | conditional | a CHANGELOG entry ships, and the repository mandates a journal entry |
| deployment-infrastructure | conditional | plugin release surfaces and the version pin change |
| agent-usability | conditional | the machine-readable result an agent interprets is exactly what changes |

**Not applicable**, with cause:

| Lens | Cause |
| --- | --- |
| performance | The change removes one plugin-resolution filesystem walk on the gated path and adds one pure in-memory registry lookup. No latency, throughput, query, memory, or capacity surface is materially affected. |
| privacy | No personal or sensitive data, telemetry, retention, or residency surface is touched. |
| previous-comments | Pull request 802 carries zero reviews and zero comments; there is no prior thread to apply to this revision. |
| accessibility-human-usability | No visual, interactive, or human-content surface exists; the operator-facing output is a JSON record consumed programmatically, scored under api-contract. |

## Findings

Numbering is stable across both cycles.

| # | File | Issue | Lens | Priority | Route | State |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `plugins/saga/scripts/board_progression.py:539` | Stand-in board writer on the gated path reports success instead of raising | adversarial | P3 | `safe_auto` | repaired at `44946060` |
| 2 | `docs/engineering-journal/LEARNINGS.md` | No engineering-journal entry for a non-obvious ordering fix | architecture-maintainability | P2 | `safe_auto` | repaired at `44946060` |
| 3 | `tests/test_board_progression.py:320` | Gated test uses an unenumerated operation, not a registered gated one | testing | P3 | `safe_auto` | repaired at `44946060` |
| 4 | pull request 802 description | Body claims the gated path writes a ledger record; it writes none | documentation-clarity | P3 | `manual` / human | **residual** |
| 5 | `plugins/saga/scripts/board_progression.py:532` | Gated branch duplicates the call site, record print, and exit mapping | architecture-maintainability | P3 | `safe_auto` | repaired at `44946060` |

### 1 — Stand-in board writer on the gated path reports success instead of raising (P3)

At `6c3588f0` both entry points passed `board_writer=lambda **_kw: None` into a function whose
module contract is fail-loud (`board_progression.py:5`; `:167-171` — "no write and no ledger
entry ... fail-loud, never silent").

**Validated, and validated as not live.** `reversibility_certificate.authorize_write` is a pure
lookup over a module-level registry with no input, environment, or filesystem dependency
(`:292-324`), so the entry point's verdict and the library's cannot disagree, and the stub is
unreachable today. The finding is the *shape*, not a live defect: on a divergence the stub's
`None` return would be read as a committed board write, `authorize_and_write` would write the
idempotency key (`:246`), the record would say `written`, exit would be 0 — and the key would
suppress the real write on every later tick. A silent no-op that is also sticky is the worst
available failure here, and the module's own contract forbids exactly it.

**Repaired** by `board_progression._gated_writer`, a named module-level function with a docstring
naming the assumption and its citation, which raises. A divergence now runs the bounded retry three
times, returns `{"status": "failed"}` with **no** ledger key, and exits 1 — retryable, loud.
Pinned directly by `tests/test_board_progression.py::test_gated_writer_raises_rather_than_silently_succeeding`.

### 2 — No engineering-journal entry for a non-obvious ordering fix (P2)

`CLAUDE.md` mandates a dated `LEARNINGS.md` entry in the same commit that ships a non-obvious fix,
and all four preceding merges in this run carry one (`593361b9`, `6e352d7d`, `e81219d6`,
`f401f3bf`). `6c3588f0` carried none. The generalizable rule here — evaluate the gate before
acquiring what only the passing branch needs — is precisely the journal's shape.

**Repaired**: a dated 2026-08-24 entry with Context, Evidence, Mechanism, Fix, Validation, and
Generalizable rule. `scripts/lint_journal_order.py` passes in both structural and diff-scoped modes.

### 3 — Gated test uses an unenumerated operation, not a registered gated one (P3)

The new board-progression gated test passed `--op merge-pr`, which is absent from `OpKind`
(`reversibility_certificate.py:62-78`), so its GATE verdict arrived through the string-coercion
default-deny branch (`:308-312`) rather than the `ALWAYS_OPERATOR` branch (`:318-319`) the leaf
describes — "the certificate deliberately withholding the write pending operator confirmation".
The sibling reconcile test already used `parent-issue-close`, so the two-command symmetry the fix
claims was not mirrored in its tests. Minor: nothing in either entry point branches on which GATE
path produced the verdict, which is why the `testing` lens still accepted at cycle 1.

**Repaired**: the board-progression case now uses `parent-issue-close`, and both modules assert the
gated path leaves the ledger directory empty — the property that keeps a later tick in a healthy
environment able to perform the real write.

### 4 — Pull-request body claims the gated path writes a ledger record; it writes none (P3, RESIDUAL)

The pull request 802 description states the gated operation "writes the ledger record with
`status=gated`". It does not. `authorize_and_write` returns the gated record at `:191-194`, before
`key = cert.idempotency_key(...)` at `:195` and before any ledger file is touched; its docstring at
`:167-168` says "no write and no ledger entry". `reconcile_op` behaves identically at `:203-209`.

**Not repaired here.** Code Review is a gate and does not edit a pull-request body. The correction
is published verbatim in the typed-outcome comment on pull request 802, so the merge record carries
it. Routed `manual` / human.

### 5 — Gated branch duplicates the call site, record print, and exit mapping (P3)

At `6c3588f0` each command had two `authorize_and_write` / `reconcile_op` call sites and two
exit-code mappings — the gated branch returning 0 unconditionally, the authorized branch mapping
status to an exit code. The plan's KTD4 asked for "the smaller diff against the linear
command-line shape".

**Repaired**: each command binds the stand-in writer, evaluates the certificate, and resolves only
inside the `AUTHORIZED` branch. One call site, one exit-code mapping. In the reconcile command the
live reader also moves inside that branch, so a gated tick no longer imports `outcome_github` for a
reader it can never use. The repaired diff is smaller than the reviewed one.

**Suppressed below the confidence-75 admission gate: none.** Every finding above is anchored at 100
with `file:line` evidence read in this worktree.

## Scores

Acceptance rule: derived overall (the arithmetic mean of applicable dimensions) at or above 9.0,
**and** no applicable dimension below 7.0, **per lens, with no averaging across lenses**. Computed
by `plugins/saga/scripts/review_consensus.py`, not by hand.

### Cycle 1 — `6c3588f0` — outcome `repairs_requested`

| Lens | Derived overall | Result |
| --- | --- | --- |
| deployment-infrastructure | 10.000 | accepted |
| reliability | 9.750 | accepted |
| security | 9.750 | accepted |
| agent-usability | 9.600 | accepted |
| api-contract | 9.600 | accepted |
| testing | 9.600 | accepted |
| correctness | 9.400 | accepted |
| adversarial | 8.857 | **failed** |
| documentation-clarity | 8.750 | **failed** |
| architecture-maintainability | 8.429 | **failed** |

No dimension fell below 7.0 in any lens, so the floor was never the binding constraint — the three
failures were mean shortfalls driven by findings 1, 2, 4, and 5.

### Cycle 2 — `44946060` — outcome `accepted`

Delta-scoped: the three failing lenses were reattempted; the seven accepted lenses were retained at
`6c3588f0` under recorded delta-checks, each passing with a cause naming what was re-verified and
citing the re-run tests.

| Lens | Derived overall | Result | Revision |
| --- | --- | --- | --- |
| adversarial | 9.857 | accepted | `44946060` |
| documentation-clarity | 9.750 | accepted | `44946060` |
| architecture-maintainability | 9.714 | accepted | `44946060` |
| deployment-infrastructure | 10.000 | retained, delta-check passed | `6c3588f0` |
| reliability | 9.750 | retained, delta-check passed | `6c3588f0` |
| security | 9.750 | retained, delta-check passed | `6c3588f0` |
| agent-usability | 9.600 | retained, delta-check passed | `6c3588f0` |
| api-contract | 9.600 | retained, delta-check passed | `6c3588f0` |
| testing | 9.600 | retained, delta-check passed | `6c3588f0` |
| correctness | 9.400 | retained, delta-check passed | `6c3588f0` |

No score regressed between cycles.

## Independent gates

Non-scoring; a failure blocks readiness regardless of the numbers. All passed.

| Gate | Result |
| --- | --- |
| built-versus-planned | passed — scope CLEAN, every plan requirement DONE or CHANGED-and-disclosed |
| touched tests | passed — `uv run pytest -q tests/test_board_progression.py tests/test_reconcile_controller.py tests/test_saga_plugin.py` → 90 passed |
| lint | passed — `ruff check` clean, `ruff format --check` clean |
| types | passed — `mypy plugins/ scripts/ tests/ --ignore-missing-imports` exit 0 |
| journal-order lint | passed — structural and diff-scoped, 0 violations |
| full pre-merge gate | passed — `GATE_LOG_DIR=... bash scripts/gate.sh` at `44946060` → `GATE GREEN — 24 steps ran, 0 blocking failures, 0 uncovered` |

`ReviewReadiness.can_proceed` is `True`; `next_action` is `continue`.

## Residuals and disclosures

1. **Finding 4 is unrepaired** and routed to a human: the pull request description misstates ledger
   behavior on the gated path. The correction is published in the typed-outcome comment.
2. **The serialized result lists two unresolved fix identifiers**, `fix-cee393be2152` (finding 4)
   and `fix-2deb702c67cf` (finding 3). Finding 3's repair *did* land in `44946060`; the consensus
   engine cannot mark it resolved because it belongs to the `testing` lens, which accepted at cycle
   1, and the contract forbids reattempting an accepted lens. This is a bookkeeping artifact of the
   delta-scoped rerun rule, not an outstanding repair. The `testing` delta-check records the repair.
3. **Merge-time obligation, not a defect at this revision.** `origin/main` is at saga `0.139.3` and
   this branch bumps to `0.139.4`. Sibling lane-B pull requests bump the same surfaces, and
   same-version sibling bumps auto-merge silently. Re-resolve the version at merge time.
4. **No external advisory review** was requested, launched, or consumed; the seat is `unavailable`
   by operator direction, not by a failed launch.

## Verdict

**`accepted` at `44946060f2e7d6531eee4d7ab8f86d60a0565451`**, two cycles of three, with finding 4
disclosed as an open residual routed to a human.
