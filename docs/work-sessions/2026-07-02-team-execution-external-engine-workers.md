# Work session — #318 team-execution external-engine workers (2026-07-02)

**Saga:** issue-318 · **Plan:** docs/plans/2026-07-02-team-execution-external-engine-workers-plan.md ·
**Branch:** feat/318-external-engine-workers · **Backend:** inline (operator-confirmed over the
file/phase-count heuristic's `team-execution` suggestion — 5 of 6 units are settled
contract-markdown; only U3 touches code)

## Built (by U-ID)

- **U1** `bb85ac4` — new `references/external-engine-workers.md`: the chaperone protocol
  (context package → resolve → dispatch, protocol forwarded verbatim → substitution detection →
  verify/apply/test/manifest), grounded against `engine_resolver.py`, `engine_dispatch.py`,
  `provenance_manifest.py` line-by-line.
- **U2** `bb85ac4` (same commit) — team-execution SKILL.md's `### Workers` table gains
  Engine/Intent columns + a Chaperone Dispatch residency bullet; saga `/plan` SKILL.md's tier
  table gains the KTD2 intent→tier rows and the plan-time resolution-preview requirement.
- **U3** `4f78e36` — `Unit.engine_intent` (offload/second-opinion, defaults offload, valid only
  alongside engine/capability). `segment_units()` now gives an engine/capability unit its own
  resident boundary (keyed on the bare engine id — `worker-agy`, not `worker-agy/<variant>` —
  matching KTD1's own naming example) instead of grouping by file path; `team_emitter.py` renders
  the new columns. Added the column-shape oracles the Workers table had none of before.
- **U4** `111c8cf` — `worker-manifest.md`: replaced "reserved for #283 U12" with the live
  attribution/disposition/claim-provenance contract for a chaperone worker.
- **U5** `0bb77cb` — `external-second-opinion` advisory validator: opt-in via
  `.team-execution.json`'s `external_second_opinion` key, structurally incapable of gating (Gate
  Status carve-out in `validator-criteria.md`), exempt from Required-Evidence Absence.
- **U6** `135a8c0` — team-execution 2.5.0→2.6.0, saga 0.45.0→0.46.0, marketplace mirror, both
  version-pinned drift-guard tests updated, DECISIONS.md entry cross-linked to the #283 entry
  whose "team-execution gains an external-engine worker context-package slot" revisit trigger
  this fulfills.

## Key decisions in flight (beyond the plan's own KTD1–KTD7)

- `segment_units()`'s file-path boundary key needed a real fix, not just an emitter-side rename:
  the function is shared by both emitters (`emit_workflow_script` and `team_emitter.py`), and
  without an engine-aware boundary an engine unit could silently merge into a plain Claude
  segment sharing the same file path. Verified `emit_workflow_script` doesn't consume
  `resident_id` at all (it renders engine markers per-unit via `_agent_opts`), so the fix is
  scoped to `team_emitter.py`'s consumer only — confirmed via all 4 existing `test_workflow_emitter.py`
  segmentation tests staying green (they don't exercise engine/capability units).
- `unit.engine` can be a full `engine/variant` selector (existing behavior, e.g.
  `"codex/gpt-5.5-xhigh"`), but KTD1/KTD3's own naming example (`worker-agy`) wants the bare
  engine id. Segmentation and the Engine table cell both use `unit.engine.split("/", 1)[0]`.
- Found (pre-existing, out of scope for #318): `team_emitter.py`'s standalone CLI entrypoint
  (`_load_spec` → `main()`) fails with `'NoneType' object has no attribute '__dict__'` — it loads
  `execution_spec.py` via `importlib.util` without registering the module in `sys.modules` first,
  which trips `@dataclass`'s module lookup. Reproduced identically at `main` HEAD (`e901ae1`)
  before any of this session's changes, so it isn't a regression from U3's `Segment`/`Unit`
  field additions. Not fixed here (unrelated to this plan's scope); worth a follow-up issue.
  `emit_team_structure()` itself and `execution_spec.py`'s own CLI (`validate`/`emit`) are
  unaffected — both manually verified against a sample two-unit spec (one plain, one
  capability-routed `second-opinion` unit) with the expected Workers-table output.

## Checks run

Full suite 1633 passed / 0 failed. ruff check, ruff format --check, mypy (plugins/ and
plugins/+scripts/+tests/): clean. bandit -r plugins/: only pre-existing house-pattern
`assert`-based B101 low-severity notes (same idiom already used elsewhere in this file), nothing
new. marketplace.json + both plugin.json: valid JSON, versions mirrored. Merge base current with
origin/main (`e901ae1`) — no rebase needed before review.

## Next step

/code-review programmatic gate (base:main), then PR open (operator-confirmed).
