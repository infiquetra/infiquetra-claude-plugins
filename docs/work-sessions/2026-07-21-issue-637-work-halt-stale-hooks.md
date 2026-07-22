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

## Root cause

Version skew between the repo scripts driving the lease protocol and the installed plugin
snapshot the hooks execute from:

- Driver-side reserve/attest ran repo code (saga 0.107.0 / fleet-core 0.17.0 protocol), which
  binds workflow children to the live batch **by trusted session id** (`claim_hook_agent(...,
  batch_id=active_batch_id(payload, env))`).
- The session's hooks resolved to the **installed cache snapshot at saga 0.104.0 /
  fleet-core 0.15.0**, which predates batch-discovery binding: with no per-agent
  `PreToolUse Agent|Task` reservation (workflow-runtime spawns never fire one in the driving
  session), `SubagentStart` claim found nothing and the child's mutations fail-closed —
  exactly the hook's designed posture, applied by a stale implementation.

This same skew is the likely mechanism behind the #616-shaped direct-Agent lease-binding
failures observed on 2026-07-21.

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

## Resume (next session)

1. Restart Claude Code (picks up 0.107.0/0.17.0 hooks).
2. `/saga:work` — Phase 0 restores saga `issue-637` on `work/637-refuse-mode-hardening`.
3. Re-run the Phase 1.5 pre-launch protocol with a **fresh** `WORKFLOW_INVOCATION_ID`
   (same spec `docs/plans/2026-07-21-issue-637-refuse-mode-hardening-spec.json`), then
   relaunch the workflow. U1 re-executes at opus with mutation authority.

## Checks run

Preflight git/saga/session-id; `recommend_execution_backend()`; lease reserve + attest;
journal parse of `wf_881dd2cb-fa1`; hook source inspection (installed 0.104.0 vs marketplace
`8882bdc` 0.107.0); installed-registry verification. No pytest/ruff/mypy this phase — no code
changed.
