# Work session — issue #637 workflow halt: stale installed hooks fail-closed workflow children

- **Saga**: `issue-637` · branch `work/637-refuse-mode-hardening` (from `origin/main` `47dacede`)
- **Plan**: `docs/plans/2026-07-21-issue-637-refuse-mode-hardening-plan.md` (doc-review READY,
  `docs/reviews/2026-07-21-issue-637-refuse-mode-hardening-plan-doc-review.md`)
- **Backend**: `cc-workflows-ultracode` (operator-chosen; `recommend_execution_backend()` agreed —
  no divergence)

## What happened

1. Phase 0–1 completed clean: branch created, plan artifacts + DECISIONS entry committed
   (`26c9281a`), saga advanced to `lifecycle_phase=work`, lease reserve → attest returned
   `launch_authorized: true`, settlement manifest + attempt-1 spawns recorded for U1–U3.
2. Workflow `wf_881dd2cb-fa1` launched (task `whh8n6poo`, invocation
   `6d92d7c1-8f54-4236-b48f-c3f508ea3c11`).
3. **U1's agent was fail-closed on every mutation tool** by the `lease_mutation_hook`
   PreToolUse gate: `no fleet lease bound to agent 'a007fa899613a0eb0'; found 0`. The agent
   completed the full U1 design read-only and returned it as a structured result (journaled),
   applied nothing, and messaged the driver.
4. Driver stopped the run (host-confirmed), released the reservation
   (`dcf8513b-7581-40bf-bab5-8c31d7a581da`), and diagnosed.

## Root cause — CORRECTED 2026-07-22 (original skew diagnosis was wrong)

> The version-skew story recorded here on 2026-07-21 is superseded — see LEARNINGS
> `{#installed-hook-skew-fail-close-637}` and ARCHIVE `{#installed-hook-skew-fail-close-637-v1}`.

Deterministic protocol defect, version-independent. The child's verbatim SubagentStart warning
(`wf_881dd2cb-fa1`, agent `a007fa899613a0eb0`) was `no live provisional reservation for
session='a2c17e16-…', agent_type='workflow-subagent', batch_id='workflow:922e…'` — batch
discovery **succeeded**; there was no claimable slot. `LeaseBroker.claim`
(`fleet_commons/lease_broker.py:2619-2634`) requires a batch slot stamped with a
`tool_use_id`, and only `prepare_batch_call` (`:2660`) writes that stamp — reached solely from
the `PreToolUse Agent|Task` hook. Workflow-runtime spawns never fire that event, so **every
workflow child fails the claim on every saga version** (0.104.0/0.105.0/0.107.0 adapters all
carry `active_batch_id`). The plugin update + restart prescribed below changed nothing about
this seam.

Also found: the installed cache lease hooks were hand-disabled (early `return`, `.orig-*`
backups) on 2026-07-17 (0.99.1), 2026-07-19 (0.104.0), and 2026-07-21 23:22:57 (0.107.0) —
author untraced; under those no-op hooks workflow runs proceed ungoverned, which is evidently
how #627 shipped. The #616 attribution below is likewise unproven.

## State at halt

- Tree: **no unit mutations** — only the plan-artifacts commit `26c9281a` on the branch.
- U1 design (verbatim patch + 6 test bodies): journaled in the workflow transcript
  (`subagents/workflows/wf_881dd2cb-fa1/`, agent `a007fa899613a0eb0`). Unverified by
  execution; do **not** hand-apply — re-execution under a bound lease preserves the
  refute-3 verification the backend guarantees.
- Settlement ledger: dispatch
  `workflow:922e7a2d96eb74d4d21b6b48:invocation:91dfbc4a3a3a14aa30cc2b00` holds attempt-1
  spawns for U1–U3, unsettled. The relaunch mints a new invocation id → a new dispatch id;
  the old dispatch record stays open and is superseded (documented casualty, not corruption).
- Installed plugins: updated/confirmed at saga **0.107.0** / fleet-core **0.17.0** (user
  scope). **Restart required** for hooks to load the new snapshot.

## Resume (next session) — amended 2026-07-22 per operator decision

Operator-chosen path (2026-07-22): **relaunch ungoverned** under the disabled cache hooks
(the #627 precedent) with a fresh `WORKFLOW_INVOCATION_ID` on the same spec; the seam defect
already exists as **#615** (filed 2026-07-17 with the same mechanism and the neutralization
workaround documented, revert hazard included); **restore the armed `.orig-2026-07-22` hooks
after the run completes**. The originally-prescribed restart was performed (plugins reloaded
at saga 0.107.0 / fleet-core 0.17.0) but is causally irrelevant to the halt. Relaunched as
`wf_36c601cc-5a6`, invocation `98d9b60a-db43-4608-9f45-9fb95b100563`, after canary
`wf_428d7af7-c5a` proved workflow-child mutation lands under the current hook plane.

## Checks run

Preflight git/saga/session-id; `recommend_execution_backend()`; lease reserve + attest;
journal parse of `wf_881dd2cb-fa1`; hook source inspection (installed 0.104.0 vs marketplace
`8882bdc` 0.107.0); installed-registry verification. No pytest/ruff/mypy this phase — no code
changed.
