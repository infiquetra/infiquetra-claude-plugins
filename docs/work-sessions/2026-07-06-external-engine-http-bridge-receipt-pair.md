# Work session: external-engine HTTP bridge + bridge_receipt.v1 pair (#387 + #383)

**Saga:** `issue-387` · **Branch:** `feat/387-383-http-bridge-receipt-pair` · **Destination:** merge
**Plan:** `docs/plans/2026-07-06-external-engine-http-bridge-receipt-pair-plan.md`
**Backend:** `cc-workflows-ultracode` (operator-chosen; recommender said `team-execution` — divergence recorded on the saga)

## What was built (by U-ID)

Executed via Workflow run `wf_6f7f3de8-926` — 8 serialized workers + refute-3 panels on
U5/U6/U7, 17 agents, peak concurrency 3 by construction. All eight units DONE:

- **U1** `bridge_receipt.v1` schema module in fleet-commons (`plugins/fleet-core/scripts/fleet_commons/bridge_receipt.py`) — common core + transport-discriminated runner section (cli: pid/argv/exit_code; http: url/status_code/model).
- **U3** registry: top-level `transport` field (closed vocab, default `cli`), required `receipt_emitter` key, seed rows `ollama-cloud` + `deepseek` with routing-stability literals baked into a regression test.
- **U4** transport-aware preflight + run-scoped RunMemo in `engine_resolver.py`.
- **U5** generic OpenAI-compatible HTTP bridge (`engine_bridge_http.py`, stdlib urllib behind the Runner seam) + transport-keyed `_build_invocation`; secret lifecycle enforced (key from `auth.key_env` only at request-build time, name-only elsewhere) with a serialized-blob non-leak test.
- **U6** receipt-gated disposition: schema-valid receipt → `RAN_AS_REQUESTED`, receipt-less ok → new `Disposition.UNPROVEN`, halt → `FELL_BACK_TO_CLAUDE`; never-gatekeeper structural guard intact.
- **U2** agy delegate emits the shared receipt through a vendored byte-identical `fleet_commons_shim.py`.
- **U7** bridge-enumeration drift guard (`tests/test_bridge_receipt_drift.py`), forcing-function verified, `PENDING_EMITTERS = {"codex-bridge": "#476"}`, hermetic red conditions.
- **U8** release surfaces: saga 0.73.0, agy 0.1.2, fleet-core 0.7.0, team-execution 2.12.1 + marketplace + CHANGELOGs + DECISIONS/QUEUED entries.

## Verification story

- Gates: pytest 2423 passed / 1 skipped; ruff clean; mypy clean (CI scope); bandit — nothing new.
- The workflow's verify panels ran **vacuous** (0/3 quorum on all three): verifier worktrees
  are cut from main and workers hadn't committed. Re-ran all three panels against committed
  code (`wf_5afd99b3-636`): U5 3/3, U7 3/3 upheld; U6's two refuters had *still* examined
  main (false kill — their citations matched main's line numbers) and were re-run with
  mandatory materialization (`wf_dbffe1aa-8a6`): 2/2 upheld. Net: 0 refutations across 11
  valid verdicts. Learning + emitter fix queued: LEARNINGS
  `{#verify-panels-blind-to-uncommitted-tree}`, QUEUED `{#execution-spec-verifier-visibility}`.
- Programmatic `/code-review` (5 lenses + 1 validator): one P2 (HTTPError socket leak on
  non-2xx), validated and fixed in `39569c4` with a regression assertion. Artifact:
  `docs/code-reviews/2026-07-06-feat-387-383-http-bridge-receipt-pair-code-review.md`.
- Per-unit completeness manifests persisted under `.git/saga-manifests/issue-387/` (U5
  recorded `missing-output` — worker returned prose instead of the contract dict; deliverables
  verified present by panel + tests).

## Key decisions

See DECISIONS `{#http-bridge-receipt-pair-387-383}` (KTD1/3/6/8/9 with rejected alternatives).

## Files modified

40 files, ~4,050 insertions net of the plan artifacts — see the branch diff
(`git diff 9a84311..39569c4 --stat`) rather than a duplicated list here.

## Next step

Open the PR (closes #387, closes #383), merge on green checks (operator pre-approved), then
`outcome.py link-pr external-engine-offload sub-387 <pr-url> --push`, same for `sub-383`,
and `outcome.py advance external-engine-offload --persist` to harvest.
