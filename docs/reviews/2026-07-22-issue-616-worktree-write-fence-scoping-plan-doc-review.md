# Doc review — issue #616 worktree write-fence scoping plan

**Verdict:** ready to drive `/work` once the operator pins D1 — every mechanism anchor verified
against the live tree; three safe fixes applied in place; one P1 remains and it is an operator
decision, not a plan defect.

## Review-result contract

- **Target:** `docs/plans/2026-07-22-issue-616-worktree-write-fence-scoping-plan.md`
- **Companion spec (also reviewed):** `docs/plans/2026-07-22-issue-616-worktree-write-fence-scoping-spec.json`
  (re-validated with receipts and re-emitted after fixes)
- **Reviewed revision:** working tree (plan uncommitted) on `main` at `ab84003b`
- **Blocked:** no — D1 pinned by the operator (Jeff, 2026-07-22) to resolution (i); no P0s
- **Linked:** issue #616, saga `issue-616` (lifecycle `plan`, destination `merge`,
  orchestration `cc-workflows-ultracode`), outcome `governed-execution-integrity`
  leaf `leaf-governed-execution-integrity-sub-616`
- **External opinion:** stored preference `none` for stage doc-review (`engine_offer.py`,
  advisory-only; no dispatch)

## Applied fixes

1. **U2 test-home hedge pinned.** "tests/test_concurrency_conformance.py or the adapter's
   existing coverage home" replaced with `tests/test_saga_hooks.py` (the hook payload-contract
   home; fixtures `:96-103`) in both plan U2 and spec U2 (prompt + files).
2. **SubagentStart claim now evidence-cited.** The "no isolation field" assertion in the Problem
   Frame now cites the repo's own payload-contract fixtures
   (`tests/test_saga_hooks.py:96-103` — exactly
   `{hook_event_name, session_id, cwd, agent_id, agent_type}`).
3. **Adapter↔broker code-version skew risk added.** New Risk Analysis bullet: a stale-shim
   resolution (#642 shape) pairing the 0.111.0 adapter with a 0.19.0 broker fails closed with a
   loud `TypeError` at PreToolUse — never a silent wrong-fence; the R8 `FLEET_COMMONS_DEBUG=1`
   provenance check is the guard.

## Readiness summary

Every `path:line` anchor in the plan was verified against the live tree this session (adapter
`:80-90/:288-353`; broker `:176/:370-374/:812/:845-930/:969-970/:2246/:2477/:2580/:2653-2658/
:2711/:3044-3088/:3892`). The KTD chain is internally consistent and grounded: KTD1's carrier
claim is backed by shipped `_agent_type` behavior plus the fixture cite from fix 2; KTD3 row 3
preserves #615's R9-proven batch behavior byte-for-byte; KTD5 reuses a demonstrated schema idiom.
Spec and plan agree on U-IDs, tiers, `depends_on` chain, and the n=3 verify panels on U1/U2.
Scope fences against #615 (merged, additive), #617 (schema layer, rebases onto this diff), #626
(extends a named field), and #642 (operational hazard only) are explicit.

## Remaining findings

| Key | Priority | Status | Finding |
|---|---|---|---|
| D1 | P1 | **pinned** — operator (Jeff), 2026-07-22 | KTD3's middle branch removes the write-fence for declared non-isolated spawns. Jeff pinned resolution (i) — unfenced; admission + mutation mode + hook verification remain — as the go for `/work` (in response to the D1-blocked notification). |
| D5 | P3 | open — deferred to work/ship | R8's live acceptance canary has no scripted recipe yet (the #615 R9 canary does). Author the cross-repo canary script (positive, negative, and R9-rerun halves) during `/work`'s ship phase; the R-criterion itself is fully specified. |

D2-D4 were resolved by the applied fixes above.

## Residual risk from limited evidence

The Agent tool's PreToolUse `tool_input` carrying `isolation` verbatim is inferred from the
shipped `subagent_type` precedent in the same payload path, not from a captured live payload —
U1/U2 tests plus the R8 canary make this assumption fail loud, not silent, if the harness ever
renames the field.
