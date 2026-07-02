# Work session — #285 evidence/provenance manifests (2026-07-01)

**Saga:** issue-285 · **Plan:** docs/plans/2026-07-01-evidence-provenance-manifests-plan.md ·
**Branch:** feat/285-evidence-provenance-manifests · **Backend:** cc-workflows-ultracode
(run `wf_c34a8d66-b84`, 13 agents, ~663k subagent tokens)

## Built (by U-ID)

- **U0** `766145a` — fable/xhigh tiers in the execution-spec validator. MODELS *prepended*
  ("fable"), EFFORTS *appended* ("xhigh") — ordering is load-bearing for the
  `segment_units()` upgrade-only merge (`min(MODELS.index)` / `max(EFFORTS.index)`); merge-order
  guard test + LEARNINGS entry (`#tier-vocab-ordering`). Run inline pre-workflow.
- **U1** `f2f7160` — `provenance_manifest.py`: saga.manifest.v1 envelope, Attribution/Disposition,
  OutputCompleteness + ClaimProvenance subrecords, parroting taxonomy as pure predicates,
  two-tier sizing. Fable/xhigh; refute-3 panel upheld 2-1 (the refutation misfiled a U2 test).
- **U2** `f2f7160` — `manifest_store.py`: git-common-dir `saga-manifests/` tree via
  `outcome_store.resolve_common_dir`, write/read/list CLI, CompletionEvent `manifest_ref`
  pointer helpers, traversal guards. **Gate incident:** agent did the work but returned prose,
  failing the harness output gate; recovered via driver-verified literal in the workflow script
  (31 tests, ruff/mypy verified by the driver before resume).
- **U3** `4054849` — `engine_dispatch.py` emits typed manifests; `satisfy_gate` enforces R11
  (gated verdict requires Claude-adjudicated claims). Fable/xhigh; refute-3 panel unanimous uphold.
- **U4** `10959eb` — driver-materialized `output_completeness` via `completeness_gate.Contract`;
  `check_manifest` → `check_required_keys` rename; /work SKILL post-run persistence step.
- **U5** `e3840e4` — team-execution worker-exit manifest contract (`worker-manifest.md`, evidence-only).
- **U6** `ba309b4` — `manifest_reader.py` advisory consumers wired into /code-review, /qa, /retro.
- **U7** `4f2bba1` — saga-spec §13 + `test_manifest_consumer_matrix.py` no-orphan-field guard.
- **U8** `2422137` — saga 0.45.0, team-execution 2.5.0, marketplace mirror, CHANGELOGs, DECISIONS.
- Recovery edits to the emitted workflow: `bfa1383`.

## Key decisions in flight

- U2 recovery pattern: hand-verify on-disk work (tests/lint/type), commit, replace the agent call
  with a literal carrying the commit SHA — never re-pay for completed work, never trust the
  agent's claim without the driver check.
- OUTPUT CONTRACT rider appended to U3-U8 prompts after the U2 prose fumble (fable complied
  unprompted; sonnet needed it explicit). Durable fix queued: emitter should use the Workflow
  `schema` option instead of prose-JSON pleading.
- U3 refute panel serialized (was parallel): identical prompt prefixes get cache reads.

## Checks run

Full suite 1620 passed / 1 failed — `test_suite_does_not_create_claude_dir_under_repo_root`,
the documented local-only leak-guard artifact (real operator saga dirs issue-283/issue-285;
green in CI). ruff check, ruff format --check, mypy: clean. marketplace.json parse: OK.
Merge base current with origin/main (`fd2ca9e`).

## Next step

/code-review programmatic gate, then PR open (operator-confirmed).
