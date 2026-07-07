# Doc review: codex first-party bridge plugin plan (#476)

**Target:** `docs/plans/2026-07-06-codex-first-party-bridge-plugin-plan.md` (+ canonical execution
spec `docs/plans/2026-07-06-codex-first-party-bridge-plugin-spec.json`, reviewed for same-story
consistency per operator instruction)
**Reviewed revision:** working tree (pre-branch; plan artifacts uncommitted at review time)
**Mode:** readiness-skeptic pass, operator-directed fix-ALL (every severity applied in place)
**Blocked:** no — all findings fixed; zero remain open
**Linked:** issue #476 · saga `issue-476` · outcome `external-engine-offload` (`sub-476`)

## Verdict

Ready to drive implementation. Six findings (2 P1, 2 P2, 2 P3) — all evidence-backed and all
fixed in place in both the plan and the spec, which were re-validated
(`execution_spec.py validate --require-receipts` OK) and re-emitted with the verifier
materialization patch re-applied (9/9 sites, syntax-checked).

## Findings (all fixed)

| # | Pri | Finding | Evidence | Fix |
|---|-----|---------|----------|-----|
| 1 | P1 | U6 scenario (c) tested "delegate killed mid-run leaves a terminal bundle" but **no unit implemented signal handling** — an agent following the plan literally ships a delegate whose external kill (the Bash tool's 10-minute SIGTERM, the issue's own exit-143 evidence) leaves a non-terminal bundle | issue #476 body (`--wait` collision, exit 143); Bash tool 600s cap vs 900s default timeout | R4 + U2 goal/deliverables/scenarios + HTD + Risk bullet now require a SIGTERM/SIGINT die-clean handler (kill tree, terminal bundle, nonzero exit); spec U2 prompt + test list updated |
| 2 | P1 | Reviewer-mode diff scan specified "**any** dirt ⇒ `out_of_scope_mutation`" — false-positives on every pre-dirty operator tree (the common case) | adversarial literal-execution check; agy runs against live trees | U3 + HTD now scan against a pre-run `git status --porcelain` snapshot (only **new** dirt flags); dirty-tree no-false-positive test scenario added; spec U3 prompt updated |
| 3 | P2 | `invocation.via` left as "the plugins/codex delegate identifier" — an open naming choice the implementing agent would invent | registry `:85`/`:116` show the sibling convention `agy:delegate` | Pinned `via: codex:delegate` in plan U4 and spec U4 |
| 4 | P2 | Plan and spec told different stories: backend choice, serialization guardrail, panels, U6 fable/xhigh operator bump, spend, and the post-emit verifier patch existed only in the spec/session | operator instruction "keep plan and spec telling the same story" | New `## Execution` section in the plan: backend + divergence record, branch, tier/panel/spend table (656 total), re-emit-loses-patch warning |
| 5 | P3 | Stale citation `agy_delegate.py:1388-1412` (function starts at `:1390`) | `grep -n "def _supervised_receipt"` → 1390 | Corrected in plan R8 and spec U1 prompt |
| 6 | P3 | Live-smoke gate said "when codex auth is unavailable" without a probe — unpinned availability check | verified live: `codex login status` exits 0 when authenticated | Pinned the gate to `codex login status` exit code in plan U6 and spec U6; also pinned omit-`-m`-when-no-model in KTD3/spec U2 |

## Verification of fixes

- `execution_spec.py validate --require-receipts` → OK (7 units) after spec edits.
- Re-emitted `.workflow.js`: `node --check` clean; 9/9 verifier prompts carry the branch
  materialization + examined-SHA guardrail; 4 `fable/xhigh` agent sites (U6 worker + 3 verifiers).
- Spend re-priced after the U6 operator bump: 656 ordinal units (was 420 at opus/high).

## Residual risk from limited evidence

- codex `--json` usage-event shape was probed shallowly (thread/turn/item events observed; usage
  fields unconfirmed) — mitigated by design: token accounting is tolerant-parse, degrade-to-null,
  raw transcript is the contract.
- Provider-side behavior of `--ephemeral` + `-o` together was not live-probed as a pair; both
  flags verified individually. U2's fake-bin tests are hermetic either way; the live smoke covers
  the real pairing.
