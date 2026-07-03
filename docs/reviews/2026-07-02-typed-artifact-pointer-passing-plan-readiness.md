# Readiness review — typed artifact-pointer passing plan

**Verdict: READY — all findings resolved.** No P0/P1 findings ever surfaced; eight evidence-backed
safe fixes were applied in the first pass, the plan's riskiest mechanism (KTD1) was validated
empirically rather than by assertion, and the three P3 findings were subsequently fixed at operator
request (2026-07-02, second pass — see "Remaining findings" statuses).

- **Target:** `docs/plans/2026-07-02-typed-artifact-pointer-passing-plan.md`
- **Reviewed revision:** working tree on `main` @ `b6bcf5c` (plan + review both uncommitted)
- **Blocked:** no
- **Linked issue:** infiquetra/infiquetra-claude-plugins#291
- **Linked saga:** issue-291 (lifecycle phase: plan, destination: merge)
- **Review mode:** readiness-skeptic pass, single-engine (operator directed no agent delegation
  this session; external cross-family panel not requested)

## Empirical validation performed

KTD1 (temp-index tree snapshot) was executed live in a scratch repo on 2026-07-02, covering all
four load-bearing properties: staged + unstaged + untracked files captured in the tree OID; real
index and working tree untouched (byte-identical `git status` before/after); tree object survived
`git gc --prune=now` via the holding ref; `git cat-file`/`git diff` dereference succeeded from a
linked worktree. This converts the plan's central design bet from claim to observation.

## Applied fixes

| # | Fix | Evidence |
|---|---|---|
| 1 | `DECISIONS.md:503` → `:529` (two sites) — the anchor shifted when this session's own journal entry was prepended | `grep` relocated the no-back-edge quote at :529 |
| 2 | Added note that journal line numbers drift; `{#slug}` anchors are the stable citation | LEARNINGS/DECISIONS both use `{#slug}` anchors |
| 3 | KTD1: pointer now records the **base tree OID** at snapshot time so the deref command is fully pinned (`git diff <base-tree> <snapshot-tree>`), immune to HEAD movement mid-run | KTD2/KTD3 already require self-contained, freshness-checked pointers |
| 4 | KTD1: empirical-validation note added | probe run 2026-07-02 (above) |
| 5 | KTD4 internal inconsistency: "> 4 KB **or** ≥ 2 recipients" would pointerize a 200-byte diff to 3 reviewers, contradicting the plan's own always-inline rule for small context. Amended to: > 4 KB, or > 1 KB with ≥ 2 recipients; ≤ 1 KB always inline | plan's KD3/KTD4 rationale text; issue KD3 |
| 6 | KTD2: Layer-2 `POINTER_STALE` semantics pinned — stale = newer epoch exists for same run-id (monotonic supersession, matching L1 ref-moved semantics) | KTD2's L1 semantics already defined |
| 7 | U2 corrected: `security-reviewer.md` has **no** existing diff-read line (grep verified; only devils-advocate `:49` and architecture `:66` do) — it gains the receiver-contract reference rather than an edit. Validator summaries above threshold reuse the L1 tree pointer with `--stat` deref, removing an implied U3 dependency | grep over `plugins/team-execution/agents/`; U2's depends-on: U1 only |
| 8 | `saga.py:193-196` → `:192-195` (two sites); U6's vague "saga metadata drift-guard test" named as `tests/test_saga_plugin.py:48` | `sed` of saga.py 190-197; grep of tests/ |

## Remaining findings

None. The three P3 findings from the first pass were fixed in the plan on operator request:

| Priority | Finding | Status |
|---|---|---|
| P3 | U4's R11 test spawn-flow fidelity was contestable. | **fixed** — U4's consumer leg now renders the spawn context from the real `consensus-protocol.md` template text read at test time (template drift breaks the test) and extracts the pointer block as a receiving agent would; the plan states template-coupled subprocess replay as the R11 acceptance bar by decision, since CI cannot spawn a live agent. |
| P3 | Bandit suppression convention for git subprocess calls was unspecified. | **fixed** — U1 now pins the established pattern verbatim (`# nosec B404` import + `# nosec B603/B607` per call with "fixed argv, no shell" justification, runner resolved at call time for monkeypatching), citing precedent `plugins/saga/scripts/outcome_github.py:21,40` and `outcome_store.py:41`. |
| P3 | Pre-change line citations self-invalidate once U2 edits the cited files. | **fixed** — the premise section now declares all `file:line` citations pinned to the `b6bcf5c` pre-change snapshot, with U2's doc guards owning the post-change state. |

## Residual risk from limited evidence

- The temp-index probe ran on a standard repo (this repo's shape). `core.splitIndex`,
  sparse-checkout, and submodule interactions remain untested — already named in the plan's Risk
  Analysis with a loud-failure + inline-fallback mitigation, so this is bounded, not blocking.
- The orchestrator-context saving magnitude is deliberately unquantified (issue KD2: observe by
  use, don't assert). No claim in the plan rests on it.
