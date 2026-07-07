---
title: Runtime delegation tripwires — armed PreToolUse block, Stop-hook audit, two-signal acceptance
type: feat
status: active
date: 2026-07-07
origin: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T15.json
---

# Runtime delegation tripwires — armed PreToolUse block, Stop-hook audit, two-signal acceptance

## Summary

Wire the fleet's existing, manual, post-hoc delegation auditing into always-on runtime tripwires:
a marker-armed `PreToolUse` hook that blocks Claude file-tool calls during an unproven delegation,
a `Stop`/`SubagentStop` hook that classifies the turn's transcript and hard-blocks on suspected
silent fallback, a dispatch-layer reconciliation that names engine-vs-observer divergence
`DELEGATION_INTEGRITY`, codex auditor parity via one engine-parametrized fleet-core module, and a
two-signal acceptance gate (engine signal + independent observer signal, disagreement re-queues
once then HALTs — never silent accept). Closes issue #384 (leaf `sub-384` of outcome
`external-engine-offload`).

---

## Problem Frame

Acceptance of an external-engine delegation is single-signal everywhere today, and every auditor
we own is post-hoc and manually invoked:

- `plugins/saga/scripts/engine_dispatch.py` accepts on `result.get("status") == "ok"`
  (`engine_dispatch.py:171`) and threads the receipt through **unvalidated** at accept time
  (`:168`); gate satisfaction checks only Claude's own `verified_by_claude` bit
  (`satisfy_gate`, `:409-435`). The receipt-schema check exists but only *labels* the proof
  manifest (`RAN_AS_REQUESTED` vs `UNPROVEN`, `:282-330`) — it gates nothing.
- agy's transcript auditor is real and tested (`plugins/agy/scripts/agy_delegate.py:995`
  `classify_transcript`, `plugins/agy/scripts/audit_harness_transcript.py`) but is invoked by
  hand, after the fact, only in the release-gate proof ritual
  (`plugins/agy/docs/harness-proof.md`). Nothing runs it on a live delegation.
- **No delegation-liveness marker exists anywhere** — `run-lease.json` (`agy_delegate.py:1594`)
  is written once, post-exit. A Claude agent that never calls the wrapper at all is
  indistinguishable, at runtime, from a genuine delegation.
- The codex bridge (`plugins/codex/`, merged 2026-07-07 via #476/PR #518) emits full evidence
  bundles and launch-gated receipts but has no transcript auditor.
- No re-queue path exists for a *disputed* delegation result — `dispatch()` raises
  `DispatchError` or downgrades; disagreement between signals is not even representable.

Binding decisions this enforces at runtime: `{#external-engines-never-gatekeepers}` (#283) and
`{#external-engine-chaperone-dispatch}` (#318). Scope-note corrections applied: the codex audit
target is the first-party `plugins/codex/` evidence bundle surface, not "TBD under
team-execution".

---

## Requirements

- R1. While a delegation is **armed** and no genuine engine invocation is evidenced, a
  `Write`/`Edit`/`MultiEdit`/`NotebookEdit` tool call is blocked (exit 2). Unarmed sessions see
  zero behavior change; every error path fails open (exit 0).
- R2. A genuine engine run — evidenced by a run directory under the engine's bundle root
  (`.claude/agy/runs/` or `.claude/codex/runs/`) containing `prompt.txt` with mtime ≥ the
  armed-at timestamp — passes the tripwire.
- R3. At `Stop`/`SubagentStop` on an armed turn, the transcript is classified with the
  engine-parametrized auditor; `fallback_suspected` hard-blocks the stop (exit 2, stderr reason)
  with a `stop_hook_active` loop guard (one blocked continuation max, then banner + audit
  record).
- R4. Transcript-audit verdict vs engine self-report divergence is surfaced as a named
  `DELEGATION_INTEGRITY` condition (dispatch layer and Stop-hook audit record), never silently
  resolved in either direction.
- R5. Codex parity: a Claude-finished run with no genuine codex launch is classified
  `codex_launched=false` by the same parametrized auditor that handles agy — one algorithm, two
  engine configs.
- R6. Two-signal acceptance: a gated delegation is accepted only when Claude's verification AND
  the observer corroboration (schema-valid receipt + bundle launch flag true) agree; disagreement
  routes to re-queue once, then HALT. Advisory (non-gated) paths downgrade with a note instead.
- R7. agy's `classify_transcript`, `audit_harness_transcript.py`, and the harness-proof flow are
  **unmodified**; a fixture-parity test pins the fleet-core auditor's agy classification to
  `classify_transcript`'s output on shared fixtures.
- R8. All seven DoD-named tests live in `tests/test_delegation_tripwire.py` and pass with the
  issue's `-k` selectors; full suite, format, lint, types stay green.
- R9. Release surfaces updated in the same PR for every plugin whose behavior changes
  (fleet-core, saga, team-execution): `plugin.json`, `.claude-plugin/marketplace.json`,
  `CHANGELOG.md`, drift-guard version-pin tests.

---

## Key Technical Decisions

- KTD1 — **Hooks live in saga; auditor logic lives in fleet-core** (operator-confirmed
  2026-07-07): saga is the only plugin with hook precedent, registration tests
  (`tests/test_spore_hooks_registration.py`), and ownership of `engine_dispatch.py`; root
  `.claude/settings.json` is gitignored and cannot host hooks. The classifier/corroborator is an
  engine-parametrized fleet-core commons module loaded via the established vendored-shim
  mechanism (`{#fleet-commons-mechanism-463}`; saga already loads `bridge_receipt` this way,
  `engine_dispatch.py:15,21`). Rejected: agy-hosted hooks + codex mirror — mirroring is the
  drift vector `{#unit-panels-vs-whole-diff-lenses-476}` just documented.
- KTD2 — **Hard-block HALT posture** (operator-confirmed): Stop-hook audit failure exits 2 so
  the turn cannot end unaddressed — the fail-loud runtime enforcement #384 exists for. Loop
  guard: when `stop_hook_active` is true and the audit still fails, emit a banner + audit record
  and exit 0 (one forced continuation, never an infinite block).
- KTD3 — **Block scope = `Write|Edit|MultiEdit|NotebookEdit`** (operator-confirmed): the
  enforcer uses `classify_transcript`'s own claude-file-tool vocabulary so observer and enforcer
  agree on what "Claude did the work itself" means.
- KTD4 — **Arming authority is the dispatch layer, with wrapper entry as defense in depth**:
  `PreToolUse` cannot see the calling agent's profile or intent (journaled twice,
  `DECISIONS.md:1124,:1145`), so a filesystem marker is the only cross-call channel. The
  zero-engine-call attack is catchable only if arming precedes the agent's work — so
  `engine_dispatch.py` arms before running the adapter, and a CLI (`arm`/`disarm`/`status`)
  lets any other dispatch surface (chaperone protocol, delegate agent prompts) arm explicitly.
  Marker: `.claude/delegation/active.json`, atomic tmp+rename writes, entries keyed by
  `session_id` + engine + `armed_at`, TTL-staleness ignored-and-reaped (default 4h).
- KTD5 — **Genuine-invocation evidence is bundle artifacts, not process introspection**:
  tripwire pass = `prompt.txt` newer than `armed_at` under the engine's bundle root (the issue's
  own dod_sketch names `prompt.txt` as the evidence convention); full Stop-time corroboration
  additionally checks `result.json` launch flags (`agy_launched` / `codex_launched`) and receipt
  presence (receipt ⇔ launched is guaranteed by both wrappers — `codex_delegate.py:273-297`,
  `agy_delegate.py:1390`).
- KTD6 — **`DELEGATION_INTEGRITY` lives at the dispatch/manifest layer, not in wrapper
  STATUSES**: divergence is only computable where both signals meet. Add it to
  `provenance_manifest.Disposition` (`provenance_manifest.py:54`) and compute it in
  `engine_dispatch`; wrappers stay single-signal emitters. This supersedes the issue draft's
  "add alongside `fallback_suspected` in `agy_delegate.py`" — grounding showed
  `fallback_suspected` is already TWO unrelated mechanisms sharing a name (transcript
  classification at `agy_delegate.py:1021` vs log-marker status at `:1374`); adding a third
  wrapper status would compound the conflation.
- KTD7 — **Re-queue-once-then-HALT**: on two-signal disagreement, `dispatch()` returns a typed
  re-queue disposition; consumers re-dispatch at most once, then HALT (mirrors
  HALT-not-degrade). Rejected: unbounded retry (masks a lying bridge), immediate HALT (denies
  the one legitimate transient case — a torn bundle read).
- KTD8 — **Stop-hook cost bounds**: marker stat first — unarmed turns exit without reading
  anything; armed turns stream the transcript line-by-line with a byte cap (8 MiB, matching
  codex's `MAX_LAST_MESSAGE_BYTES` precedent). Register both `Stop` and `SubagentStop` with the
  same script (both marker-gated); `SubagentStop` receives the subagent's own transcript path,
  which is exactly the delegation-bearing transcript for bridge-agent runs.

---

## High-Level Technical Design

Signal flow — two independent signals meet at two enforcement points:

```
             arm (engine_dispatch / CLI)          disarm (terminal result / audit pass)
                     │                                        ▲
                     ▼                                        │
        .claude/delegation/active.json  ◄──── TTL reaper ─────┘
                     │
     ┌───────────────┴────────────────┐
     ▼                                ▼
PreToolUse hook (saga)          Stop/SubagentStop hook (saga)
 armed? ──no──► exit 0           armed? ──no──► exit 0
 armed+evidence? ──► exit 0      classify transcript (fleet-core auditor)
 armed, no evidence ──► exit 2   + corroborate bundles (result.json, receipt)
                                  real+corroborated ──► disarm, exit 0
                                  fallback_suspected / divergence ──► exit 2 (loop-guarded)
                                                    │
                                                    ▼
                              engine_dispatch: reconcile self-report vs observer
                               agree ──► accept (satisfy_gate requires BOTH)
                               disagree ──► DELEGATION_INTEGRITY → re-queue once → HALT
```

Engine parametrization (fleet-core `delegation_audit.py`): per-engine config rows
`{command_re, bundle_root, launch_key}` for `agy` and `codex`; the classification algorithm is
one implementation generalizing `classify_transcript`'s scan (engine Bash command seen vs Claude
file tool seen), left byte-untouched in agy.

---

## Implementation Units

### U1. fleet-core `delegation_audit.py` — engine-parametrized classifier + corroborator

One auditor, two engine configs; agy's original stays untouched with a parity tripwire.

**Goal:** `classify(transcript_path, engine=None) -> AuditClassification` (vocabulary `real` /
`fallback_suspected`, plus per-line evidence), `corroborate(engine, since_ts) ->
BundleCorroboration` (launch flag, receipt presence, statuses from `result.json` under the
engine's bundle root), `reconcile(classification, corroboration, self_report) -> verdict`
(`real` / `fallback_suspected` / `delegation_integrity`).

**Requirements:** R4, R5, R7.

**Dependencies:** none (first unit).

**Files:** `plugins/fleet-core/scripts/fleet_commons/delegation_audit.py` (new — must live
under `scripts/fleet_commons/`: the vendored shim loads `<root>/scripts/fleet_commons/<module>.py`,
`fleet_commons_shim.py:153`; a module directly under `scripts/` is unreachable via
`fleet_commons_shim.load`), `tests/test_delegation_audit.py` (new),
`tests/test_delegation_tripwire.py` (new — born here with the codex-parity DoD test, extended by
U3–U6), fixtures under `tests/fixtures/delegation/` (new).

**Approach:** generalize the scan at `agy_delegate.py:995-1021` — parametrize the engine-command
regex (`_looks_like_agy_command` equivalent per engine) and the claude-file-tool set
(`Write|Edit|MultiEdit|NotebookEdit`); stream lines with an 8 MiB cap (KTD8). Engine config:
`{"agy": {command_re, "bundle_root": ".claude/agy/runs", "launch_key": "agy_launched"},
"codex": {..., "launch_key": "codex_launched"}}`. Corroboration reads `result.json` +
`bridge-receipt.json` presence only — data contract, no cross-plugin code import.

**Patterns to follow:** `plugins/agy/scripts/audit_harness_transcript.py` (transcript+bundle
cross-check shape, `PASS_STATUSES` idea), `plugins/codex/scripts/codex_delegate.py` bounded
reads.

**Test scenarios:** (happy) agy fixture transcript with genuine agy Bash command and no file
tools → `real`; codex equivalent → `real`. (edge) empty transcript → `fallback_suspected` with
empty evidence; transcript over byte cap → classified from the capped prefix without error;
unknown engine → explicit error. (error) missing/corrupt `result.json` → corroboration reports
unproven, never raises. (parity — R7) every fixture through fleet-core `classify(engine="agy")`
equals `agy_delegate.classify_transcript` output on classification and both seen-flags.
(codex parity — R5, DoD name) `test_codex_bridge_untested_run_classified_false` in
`tests/test_delegation_tripwire.py`: fixture where Claude edits files, no codex launch, bundle
`codex_launched=false` → verdict flags it.

**Verification:** parity test green against real `agy_delegate` import; all classifier scenarios
pass; mypy clean on the new module.

### U2. fleet-core `delegation_state.py` — arm/disarm marker protocol + CLI

The liveness channel the whole feature hangs on: filesystem state, because hooks can't see
caller context.

**Goal:** `arm(engine, session_id) -> entry`, `disarm(...)`, `active(session_id) -> entries`
over `.claude/delegation/active.json`; CLI verbs `arm` / `disarm` / `status`.

**Requirements:** R1, R2 (the marker side), R8 groundwork.

**Dependencies:** none (parallel with U1).

**Files:** `plugins/fleet-core/scripts/fleet_commons/delegation_state.py` (new — same
`scripts/fleet_commons/` placement rule as U1), `tests/test_delegation_audit.py` (extend).

**Approach:** atomic tmp+rename writes (codex `_write_json` precedent); entries
`{engine, session_id, armed_at, armed_by}`; reads ignore + reap entries older than the TTL
(default 4h, constant); multiple concurrent entries allowed (keyed reads by session_id).

**Patterns to follow:** `codex_delegate.py` atomic `_write_json`; ledger latest-wins reduction
style (`outcome_report.py:71`) for entry supersession.

**Test scenarios:** (happy) arm → status shows entry → disarm → empty. (edge) stale entry past
TTL invisible to `active()` and reaped on next write; two sessions armed concurrently — each
sees only its own; arm twice same session/engine → single superseding entry. (error) corrupt
JSON file → treated as unarmed (fail-open) and rewritten on next arm; read-only filesystem →
arm raises for the dispatcher but `active()` never raises for hooks.

**Verification:** CLI round-trip works from a scratch repo dir; hook-facing reads never raise in
any scenario.

### U3. saga `delegation_tripwire_hook.py` — PreToolUse block + registration

The runtime tripwire: armed and unproven means no file mutations.

**Goal:** block `Write`/`Edit`/`MultiEdit`/`NotebookEdit` (exit 2, stderr names the armed
engine and the missing evidence) when armed with no genuine-invocation evidence; exit 0
otherwise, fail-open on every error path.

**Requirements:** R1, R2.

**Dependencies:** U1, U2.

**Files:** `plugins/saga/hooks/delegation_tripwire_hook.py` (new),
`plugins/saga/hooks/hooks.json` (append a matcher entry to the **existing** `PreToolUse`
array, matcher `Write|Edit|MultiEdit|NotebookEdit`), `tests/test_delegation_tripwire.py`
(extend — created in U1),
`tests/test_spore_hooks_registration.py` (extend).

**Approach:** stdin JSON `tool_name`/`tool_input` per the repo's PreToolUse contract; marker
check first (unarmed → silent exit 0); evidence check = any run dir under the armed engine's
bundle root with `prompt.txt` mtime ≥ `armed_at` (KTD5). Import fleet-core modules via saga's
vendored `fleet_commons_shim` (hook inserts `../scripts` on `sys.path` relative to its own
file). Blocking and degrade semantics copied from `pre_push_gate_hook.py` exactly.

**Patterns to follow:** `plugins/saga/hooks/pre_push_gate_hook.py` (exit-2/stderr, fail-open),
hook-test convention (`importlib.util.spec_from_file_location`, stdin-mocked `main()`).

**Test scenarios:** (DoD names, in `tests/test_delegation_tripwire.py`)
`test_zero_engine_call_write_blocks` — armed, no bundle evidence, `Write` → exit 2;
`test_genuine_agy_run_passes` — armed, fresh `prompt.txt` in `.claude/agy/runs/<id>/` → exit 0.
(edge) unarmed session `Write` → exit 0 with no marker file at all; stale armed entry past TTL →
exit 0; evidence older than `armed_at` → blocked; `Edit`/`MultiEdit`/`NotebookEdit` each
blocked when armed-unproven. (error) malformed stdin JSON → exit 0; unreadable marker → exit 0.

**Verification:** all matcher tools blocked/passed per scenario; registration test asserts the
new hooks.json entry; a manual smoke in a scratch repo shows the block message.

### U4. saga `delegation_stop_audit_hook.py` — Stop/SubagentStop audit + registration

Turn-end enforcement: the transcript itself is the witness.

**Goal:** on armed turns, classify the transcript (U1) and corroborate bundles; hard-block
(exit 2) on `fallback_suspected` or transcript-vs-bundle divergence; disarm + exit 0 on a clean
`real` + corroborated pass; write an audit record either way.

**Requirements:** R3, R4 (hook flavor), R8.

**Dependencies:** U1, U2.

**Files:** `plugins/saga/hooks/delegation_stop_audit_hook.py` (new),
`plugins/saga/hooks/hooks.json` (register under BOTH `Stop` and `SubagentStop` — both event
keys are new to hooks.json),
`tests/test_delegation_tripwire.py` (extend), `tests/test_spore_hooks_registration.py`
(extend).

**Approach:** input carries `transcript_path` + `stop_hook_active` (+ `agent_id`/`agent_type`
on SubagentStop — the transcript is the subagent's own, which is the delegation-bearing one for
bridge-agent runs). Marker stat first; armed → `classify` + `corroborate` + `reconcile`.
Block = exit 2 with stderr instructing Claude to surface the audit failure and re-run the
delegation genuinely. Loop guard (KTD2): `stop_hook_active` true + still failing → write audit
record to `.claude/delegation/audits/<ts>.json`, print banner to stderr, exit 0. Disarm on
clean pass so the next turn starts unarmed.

**Patterns to follow:** `stale_main_session_hook.py` (classify-state-and-message shape,
swallow-everything `_run`), KTD8 bounded streaming.

**Test scenarios:** (DoD names) `test_stop_hook_classifies_fallback_suspected` — armed turn,
transcript shows Claude `Edit` and no engine command → exit 2 with HALT text;
`test_stop_hook_passes_real_classification` — armed, genuine engine transcript + corroborating
bundle → exit 0 and marker disarmed. (edge) `stop_hook_active=true` and still failing → exit 0
+ audit record written; unarmed turn → exit 0 without opening the transcript (assert via a
missing transcript path that would otherwise error); divergence case — transcript `real` but
bundle `launch=false` → exit 2 naming `DELEGATION_INTEGRITY`. (error) transcript path missing
while armed → banner not crash, fail-open exit 0.

**Verification:** both event registrations asserted; scenario matrix green; manual smoke: an
armed turn with no delegation visibly refuses to end once.

### U5. saga dispatch-layer two-signal acceptance + `DELEGATION_INTEGRITY`

Where the two signals formally meet: dispatch computes, the manifest names, the gate requires.

**Goal:** `engine_dispatch.dispatch()` arms/disarms around the adapter run (KTD4), reconciles
engine self-report against observer corroboration (receipt validity + bundle launch flag),
surfaces divergence as `Disposition.DELEGATION_INTEGRITY`, and returns a typed re-queue
disposition consumed as re-queue-once-then-HALT (KTD7); `satisfy_gate()` additionally requires
observer corroboration (R6).

**Requirements:** R4, R6.

**Dependencies:** U1, U2.

**Files:** `plugins/saga/scripts/engine_dispatch.py` (modify),
`plugins/saga/scripts/provenance_manifest.py` (add enum member),
`tests/test_delegation_tripwire.py` (extend; DoD names), existing engine-dispatch tests
(extend where acceptance semantics change).

**Approach:** arm before adapter invocation, disarm in a `finally`; after the run, corroborate
via U1 (`launch_key` true + `_receipt_problems()`-clean receipt = observer-yes). Self-report
"ok" + observer-no → `DELEGATION_INTEGRITY`, dispatch returns
`{"disposition": "requeue", "reason": ...}` once (attempt counter in the manifest record),
second divergence → `DispatchError` HALT. Advisory path keeps the existing `downgrade_note`
mechanism with the integrity reason attached. `satisfy_gate` gains the corroboration
requirement beside `verified_by_claude` (`engine_dispatch.py:409-435`).

**Patterns to follow:** existing `_receipt_problems` (`engine_dispatch.py:197-205`) and
manifest construction (`:282-330`); `_reject_gatekeeper_keys` posture (engines never
self-adjudicate).

**Test scenarios:** (DoD names) `test_reconciliation_flags_divergence` — self-report ok, bundle
launch flag false → `DELEGATION_INTEGRITY`, not accepted;
`test_two_signal_disagreement_requeues` — first divergence returns re-queue disposition,
corroborating retry accepted, second consecutive divergence HALTs. (happy) both signals agree →
accepted, manifest `RAN_AS_REQUESTED`, gate satisfiable. (edge) receipt schema-valid but launch
flag missing → observer-no (conservative); advisory dispatch divergence → downgrade note, no
re-queue loop. (error) arming fails (read-only fs) → dispatch still runs but manifest records
`tripwire_unarmed` (fail-open, named).

**Verification:** existing engine-dispatch tests still green (single-signal advisory behavior
preserved); gate now provably rejects an uncorroborated "ok".

### U6. Chaperone contract + end-to-end integration scenarios

Make the runtime contract legible to the one consumer that dispatches delegations inside teams.

**Goal:** update
`plugins/team-execution/skills/team-execution/references/external-engine-workers.md` §5 with
the two-signal acceptance + re-queue-once rule and the arm/disarm CLI expectation; add the
cross-mechanism integration scenarios that no single unit proves.

**Requirements:** R6 (contract surface), R8.

**Dependencies:** U1–U5.

**Files:** `plugins/team-execution/skills/team-execution/references/external-engine-workers.md`
(modify §5), `tests/test_delegation_tripwire.py` (extend).

**Approach:** doc change is additive — chaperone step: arm via CLI before dispatch, accept only
on two-signal agreement, one re-queue then HALT, `DELEGATION_INTEGRITY` in the halt reason. No
behavior change to team-execution code (the issue's non-goal); this is the documented protocol
the saga-side mechanics already enforce.

**Patterns to follow:** existing §4/§5 disposition prose style.

**Test scenarios:** (integration) full arc in a scratch repo — arm → fake genuine bundle →
PreToolUse passes → Stop hook passes and disarms; full arc with zero-engine-call → PreToolUse
blocks, Stop hook (forced past the block) exits 2. Test expectation for the doc itself:
none — prose contract, covered by the §5 wording review in code review.

**Verification:** doc §5 names both signals, the re-queue bound, and the CLI verbs; integration
scenarios green.

### U7. Release surfaces + journal

Same-PR release hygiene across the three touched plugins (repo rule 6).

**Goal:** version bumps + changelogs + marketplace + drift-guard pins for fleet-core
(0.7.0 → 0.8.0, new modules), saga (0.73.1 → 0.74.0, new hooks + dispatch behavior),
team-execution (patch bump, doc contract); `DECISIONS.md` entry for KTD1 (hook home) and KTD6
(integrity lives at dispatch layer).

**Requirements:** R9.

**Dependencies:** U1–U6.

**Files:** `plugins/fleet-core/.claude-plugin/plugin.json`, `plugins/fleet-core/CHANGELOG.md`,
`plugins/saga/.claude-plugin/plugin.json`, `plugins/saga/CHANGELOG.md`,
`plugins/team-execution/.claude-plugin/plugin.json`, `plugins/team-execution/CHANGELOG.md`,
`.claude-plugin/marketplace.json`, `tests/test_saga_plugin.py`,
`tests/test_team_execution_plugin.py`, any fleet-core version-pin tests,
`docs/engineering-journal/DECISIONS.md`.

**Approach:** mirror the #476 release-surface pattern; verify pin tests by running them, not by
assumption (the #476 lesson — U7 bumped surfaces but missed pins).

**Test expectation:** none — metadata unit; the drift-guard tests ARE the verification.

**Verification:** `uv run pytest tests/test_saga_plugin.py tests/test_team_execution_plugin.py`
green with new pins; marketplace validation green.

---

## Execution

Canonical execution artifact: `docs/plans/2026-07-07-delegation-tripwires-spec.json`
(cc-workflows-ultracode backend; emitted script
`docs/plans/2026-07-07-delegation-tripwires.workflow.js`; team-execution was the recommended
backend, operator chose cc-workflows-ultracode). The per-unit **Dependencies** above describe
the logical partial order; the spec deliberately **serializes** the chain
U1 → U2 → U3 → U4 → U5 → U6 → U7. Two reasons: the operator rate-limit cap is max 3 concurrent
non-haiku agents (the n=3 refute panels on U1/U3/U4/U5 are the only fan-out, so peak concurrency
is exactly 3), and serialization prevents concurrent edits to the shared files
`plugins/saga/hooks/hooks.json` (U3, U4) and `tests/test_delegation_tripwire.py` (U1, U3–U6).
Executors follow the spec's order, not the logical partial order.

Tiers (operator-approved 2026-07-07): U1/U3 sonnet/high with refute-3 panels; U2/U6/U7
sonnet/medium; U4/U5 operator-bumped from opus/high to fable/xhigh (U4: first Stop-hook in the
fleet with fleet-wide block semantics; U5: acceptance-gate change on the live dispatch path).
Priced spend: 842 units.

/work-time guardrail (journal `{#verify-panels-blind-to-uncommitted-tree}`): verify-panel
worktrees are cut from `main`, so each unit's worker must **commit** its work before its panel
runs (the spec's unit prompts mandate one conventional commit per unit), and the emitted
verifier prompts must be patched at /work time with branch materialization
(`git checkout <branch> -- .` plus examined-SHA quoting) — the emitter does not include this
yet.

---

## Scope Boundaries

Out of scope (true non-goals, from the issue):

- A new transcript-classification algorithm — the fleet-core module generalizes the existing
  scan; agy's original is untouched (R7).
- Proof-of-execution for the inline backend (no bridge seam exists there).
- A standing calibration harness / catch-rate measurement loop.
- Changing team-execution's consensus or validator-cap behavior (U6 is a documented protocol
  for the delegation path only).
- New engines, models, or providers.
- HTTP-bridge (ollama/deepseek) observer signals — transcript+bundle auditing only covers
  subprocess bridges (agy, codex); server-side attestation for HTTP rows is #388's charter.

Deferred to follow-up work:

- Consolidating agy's `classify_transcript` into the fleet-core auditor (removing the R7
  duplication) — candidate for #517's agy-parity wave once the parity test has soaked.
- Wiring the arm/disarm CLI into the execution-spec emitter's delegation riders (offload units
  arming automatically) — natural follow-on once #384's mechanics are proven.

---

## Risks & Dependencies

- **Fleet-wide hook blast radius** — saga's hooks fire in every repo where saga is installed.
  Mitigation: marker-gating (unarmed = stat + exit 0), fail-open on every error path, and the
  hard rule that only dispatch surfaces arm.
- **Stop-block loop** — a genuinely stuck audit could ping-pong. Mitigation: `stop_hook_active`
  one-continuation policy (KTD2) with a durable audit record as the escape evidence.
- **Installed-plugin path coupling** — hooks read engine bundles via cwd-relative `.claude/`
  paths (data contract) and load fleet-core via saga's vendored shim; no cross-plugin code
  imports. If fleet-core is absent, `fleet_commons_shim.load` failure is caught and the hooks
  fail open.
- **Transcript size** — bounded streaming (KTD8) keeps the Stop hook O(cap) worst-case.
- **Two `fallback_suspected` taxonomies** — the transcript classification and agy's log-marker
  status share a name (`agy_delegate.py:1021` vs `:1374`); the plan keeps them separate and
  names the dispatch-layer condition `DELEGATION_INTEGRITY` precisely to avoid minting a third.

---

## Sources / Research

- Issue #384 + scope-note comment (2026-07-06) + Update section (2026-07-05, codex targets
  `plugins/codex/`).
- agy auditor surface: `plugins/agy/scripts/agy_delegate.py:995` (`classify_transcript`),
  `:1021` (two-value vocabulary), `:34-47` (`STATUSES`), `:1374` (log-marker
  `fallback_suspected`), `:1594` (`run-lease.json`, post-hoc), `:1390` (`_supervised_receipt`,
  launch-gated); `plugins/agy/scripts/audit_harness_transcript.py:16,20,32,38,43-50`;
  `plugins/agy/docs/harness-proof.md` (manual ritual).
- Acceptance seams: `plugins/saga/scripts/engine_dispatch.py:119-194,158,168,171,197-205,
  282-330,409-435` and `_GATEKEEPER_KEYS:29`; `plugins/saga/scripts/provenance_manifest.py:54`
  (`Disposition`); no re-queue exists (nearest: ledger latest-wins `outcome_report.py:71`,
  429 retry `execution_spec.py:331`).
- codex evidence surface: `plugins/codex/scripts/codex_delegate.py` `result.json` keys incl.
  `codex_launched`/`receipt_emitted`; `_supervised_receipt:273-297` (receipt ⇔ launched);
  bundle layout `.claude/codex/runs/<run-id>/`.
- Hook contracts: repo convention (exit-2/stderr block, fail-open) per
  `plugins/saga/hooks/pre_push_gate_hook.py`; Stop/SubagentStop/PreToolUse I/O verified against
  the Claude Code hooks reference (code.claude.com/docs/en/hooks) 2026-07-07 — Stop exit 2
  blocks the stop and feeds stderr to Claude; `stop_hook_active` loop flag; SubagentStop
  carries the subagent's own transcript; plugins may register all events.
- Journal constraints: `DECISIONS.md:1124,:1145` (PreToolUse can't see caller profile),
  `:646-656` (hooks = no-confirmation reactions), `:1101-1103` (externalize hook rule sets),
  `LEARNINGS.md:528-538` (verify hook contracts against the reference first),
  `{#unit-panels-vs-whole-diff-lenses-476}` (mirroring is a drift vector).
- Binding decisions: `{#external-engines-never-gatekeepers}` (#283),
  `{#external-engine-chaperone-dispatch}` (#318), `{#fleet-commons-mechanism-463}`.
