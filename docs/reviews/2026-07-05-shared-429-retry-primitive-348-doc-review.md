# Doc-review — shared 429 retry/backoff primitive (#348)

- **Target:** `docs/plans/2026-07-05-shared-429-retry-primitive-348-plan.md`
- **Reviewed revision:** working tree (plan authored this session, pre-`/work`)
- **Blocked:** No — no P0/P1 remain after the safe fix; `/work` may proceed.
- **Linked:** issue #348; saga `issue-348`; execution-order row 9.

## Verdict

Ready. One P1 found and **fixed in place**; both deliberate scope decisions (agy scoped out, JS-helper
mirror) scrutinized and judged **sound**; P2/P3 residual, none blocking.

## Applied fix (safe, in-place)

| # | Priority | Was | Fix | Evidence |
|---|---|---|---|---|
| F1 | P1 | KTD4/U4 spoke of classifying a 429'd leaf as `retriable-pending` in a way that read as a node state — but `NODE_STATES` has no such value, so `OutcomeSpec.validate()` would reject it, and adding it is the committed-field change the issue forbids. | Clarified: a 429'd dispatch does **not** advance the leaf to `dispatched`; the leaf stays at derived `ready` and is re-picked next tick; `retriable-pending` is a dispatch-RESULT label, never a persisted node state. Test asserts the node's `state` is never set to it. | `outcome_spec.py:61-73` (`NODE_STATES` list); issue's "no committed status field" constraint. |

## Scope decisions scrutinized (as requested)

| Decision | Verdict | Reasoning |
|---|---|---|
| **agy scoped out (KTD2)** | Sound — and *safer* than the alternative | `agy_delegate.py` makes no HTTP calls (subprocess launcher, timeout-only supervision — verified). No 429 signal at that boundary. Auto-relaunching a long, token-expensive agy run on an ambiguous non-429 failure would risk double-spend. The breaker is still built + fault-injection tested in the primitive (satisfies the breaker acceptance intent); only the vacuous wiring defers. |
| **JS-helper mirror (KTD3)** | Sound | The workflow runs as JS; a `parallel([...])` wave cannot import the Python module, so a JS retry helper (like the existing `_JS_GATE_HELPER`) is necessary. Drift risk is real but small and pinned by the golden test (see P3-1). |

## Remaining findings

| # | Priority | Finding | Status |
|---|---|---|---|
| 1 | P2 | Confirm a new `fleet_commons/` module needs no registry/manifest update — the shim loads by name/path, so adding the file should suffice; verify in `/work`. | Open (verify) |
| 2 | P2 | The emitted per-thunk retry must compose with the existing `__gate` helper: retry the `agent()` call on a 429, then gate the *successful* result (retry inside, gate outside). Note in `/work`. | Open (impl order) |
| 3 | P3 | Python primitive ↔ emitted JS helper can drift (two impls of exp-backoff). Mitigated by the golden test + the logic's simplicity. | Open (by design) |
| 4 | P3 | `bandit -r plugins/` (in the DoD) may flag `random` for jitter (B311); jitter is non-security — a `# nosec B311` or `secrets`-free note suffices. | Open (mechanical) |

## Residual risk

Low. The one correctness hazard (`retriable-pending` as an invalid node state) is fixed. The scope
reductions are evidence-based and the core value (retry at the surfaces that actually 429 today) is
intact. The cross-plugin adoption is guarded by each site keeping its existing tests green plus the
golden-JS assertion.
