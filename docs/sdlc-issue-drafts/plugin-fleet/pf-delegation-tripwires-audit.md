---
title: "enhancement: runtime delegation tripwires — PreToolUse hook, Stop-hook transcript audit, live agy audit, codex auditor parity, two-signal acceptance"
repo: infiquetra-claude-plugins
type: enhancement
tier: structural
objective: "Stand up the external-engine offload lane"
wave: wave-1
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
objective: "Stand up the external-engine offload lane"
---

# enhancement: runtime delegation tripwires — PreToolUse hook, Stop-hook transcript audit, live agy audit, codex auditor parity, two-signal acceptance

### Objective
Stand up the external-engine offload lane

### Intent
Close the gap between "agy has a transcript auditor" and "every live delegation is actually
audited." Today `plugins/agy/scripts/agy_delegate.py::classify_transcript` (`:989`) and
`audit_harness_transcript.py` exist and are exercised in the release-gate proof
(`plugins/agy/docs/harness-proof.md:6-18`), but nothing wires that auditor into a live run: it is
invoked by hand, after the fact, against a transcript the operator remembers to pass in
(`plugins/agy/docs/harness-proof.md:125`). Nothing stops a zero-engine-call write from landing
silently, nothing runs the audit automatically when a delegation-bearing turn ends, the codex
bridge (the "untested twin" — no `codex` plugin directory exists under `plugins/`, confirmed by
directory listing) has no auditor at all, and a delegation is currently accepted on the engine's
own self-report with no corroborating observer signal. This issue stands up five tripwires that
together make a delegation's "did it really run through the external engine" claim
machine-checked instead of remembered:

1. A `PreToolUse` hook (`delegation_tripwire_hook.py`) that blocks a `Write` when no genuine
   engine invocation preceded it in the active turn, using a `delegation-active` state file as the
   liveness signal, following the existing hook wiring pattern in
   `plugins/saga/hooks/hooks.json` (`plugins/saga/hooks/` already carries five production hooks —
   `precompact_spore_hook.py`, `team_spawn_residency_hook.py`, `journal_nudge_hook.py`,
   `validate_json_hook.py`, `pre_push_gate_hook.py`, `stale_main_session_hook.py`).
2. A `Stop` hook that classifies the latest subagent transcript via the existing
   `classify_transcript` (`plugins/agy/scripts/agy_delegate.py:989`) at turn-end and HALT-banners
   when the classification is `fallback_suspected` (the value already emitted at
   `agy_delegate.py:1015` and `:1368`, currently only consumed at run-result branch time,
   `agy_delegate.py:1614` — never at harness Stop time).
3. Reconciliation between the transcript audit and the delegating agent's own self-reported
   verdict for every live (non-release-gate) delegation, flagging any divergence as a new,
   named `DELEGATION_INTEGRITY` condition rather than silently trusting whichever signal arrives
   first.
4. Parity for the codex bridge: give it the same transcript auditor agy already has, so a
   Claude-finished but not-actually-delegated read-only run is classified `codex_launched=false`
   instead of passing unaudited (agy has proof-of-execution machinery, codex/team-execution's
   external-engine worker slot per `{#external-engine-chaperone-dispatch}` (#318) does not).
5. Two-signal acceptance: a delegation is accepted only when the engine's own signal and the
   independent observer (transcript-audit) signal corroborate; a disagreement routes the unit to
   re-queue, never to silent accept.

This closes the loop the fleet map already names as unaddressed: "the fleet's ONE
operator-facing model/effort lever ... no dispatch-time override lever anywhere except saga's
readonly-verifier per-call pattern" and the binding decision `{#external-engines-never-gatekeepers}`
(#283) — "Claude is verifier-of-record for every gated decision; codex/agy = generator /
advisory-reviewer / non-gated worker only. Structurally enforced." — which this issue enforces at
runtime, not just architecturally, per the grounding brief's fleet-map note that the never-gatekeeper
posture is currently "structurally enforced" in doc/policy but the runtime tripwire that would make
a violation *fail loud* does not yet exist
(`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §2, binding-decision register).

### Problem Frame
- The agy transcript auditor is real and tested (`plugins/agy/scripts/agy_delegate.py:989`,
  `plugins/agy/scripts/audit_harness_transcript.py`, `plugins/agy/docs/harness-proof.md`) but is a
  manual, after-the-fact, human-invoked step (`harness-proof.md:18`, `:125`) — nothing in the
  harness calls it automatically on a live run.
- `classify_transcript` already distinguishes `real` from `fallback_suspected`
  (`agy_delegate.py:1015`), and `fallback_suspected` is a recognized run-result status
  (`agy_delegate.py:1614`), but that classification only fires at explicit CLI invocation time —
  there is no `PreToolUse` or `Stop` hook consuming it during a live delegating turn, so a silent
  Claude-only fallback (no genuine agy run) can write files and finish a turn with the harness
  never noticing.
- The codex bridge has no equivalent auditor at all — there is no `plugins/codex/` directory in
  this repo (verified via `find . -maxdepth 2 -iname "*codex*"`, which only surfaces the unrelated
  `.codex` config dir) — so the "untested twin" of agy's delegation path has zero proof-of-execution
  coverage.
- Acceptance today is single-signal: whatever the delegating agent (or bridge) self-reports is
  taken at face value. There is no second, independent observer signal required to corroborate it,
  so a bridge that lies about having run (or a Claude agent that silently completes the work itself)
  is indistinguishable from a genuine delegation without the manual audit step above.
- This is a concrete instance of the recurring pain the grounding brief names under theme 10
  ("Cross-repo learning-mining & provenance discipline ... stale-claim pattern; evidence
  integrity") and is explicitly gated by binding decision `{#external-engines-never-gatekeepers}`
  (#283) and `{#external-engine-chaperone-dispatch}` (#318): external engines must never become an
  unaudited second executor, and today nothing at runtime stops that from happening silently.

### Out-of-scope / non-goals
### Out-of-scope / non-goals
- Building a new transcript-classification algorithm — `classify_transcript`
  (`agy_delegate.py:989`) already exists and is reused, not replaced.
- Extending proof-of-execution machinery to the inline execution backend (no fan-out/bridge seam
  exists there; out of scope per the same reasoning `{#external-engines-never-gatekeepers}` applies
  only to bridge/delegation paths).
- Building a standing/scheduled calibration harness that tracks catch-rate over time — the fleet
  already rejected this ceremony shape for a single-tool ecosystem (see the sibling
  silent-omission-completeness-gate issue's `--self-test`-not-calibration-loop precedent,
  `docs/sdlc-issue-drafts/2026-06-27-capability-infiquetra-claude-plugins-campps-work-2.md`); this
  issue's tripwires are always-on hooks, not a measurement loop.
- Changing team-execution's existing consensus/validator cap behavior — this issue only adds the
  auditor and two-signal gate to the delegation path itself.
- Any new external-engine capability, model, or provider — this issue is purely enforcement of
  proof that an already-existing engine call actually happened.
- A full `codex` plugin build-out — only the transcript-auditor parity piece is in scope; broader
  codex-bridge feature work is separate.

### Files expected to change
Indicative only — the exact set is `/plan`'s to determine.
- `.claude/hooks/delegation_tripwire_hook.py` (or `plugins/agy/hooks/delegation_tripwire_hook.py`,
  following `plugins/saga/hooks/` placement convention) — new `PreToolUse` hook.
- `.claude/hooks/delegation_stop_audit_hook.py` (or equivalent `Stop`-hook module) — wires
  `classify_transcript` (`plugins/agy/scripts/agy_delegate.py:989`) into turn-end.
- `plugins/agy/hooks/hooks.json` or repo-root `.claude/settings.json` — hook registration, following
  `plugins/saga/hooks/hooks.json` pattern.
- `plugins/agy/scripts/agy_delegate.py` — add `DELEGATION_INTEGRITY` divergence status alongside
  existing `fallback_suspected` (`:38`, `:1368`).
- A new codex-bridge auditor module (path TBD by `/plan` — no existing `plugins/codex/` directory to
  extend; may live under `plugins/team-execution/` per the external-engine-worker slot referenced in
  `{#external-engine-chaperone-dispatch}` (#318)).
- `tests/test_delegation_tripwire.py` — new hook/auditor tests (repo-root collected per
  `tests/` convention).
- Release-surface files if hook registration changes plugin-visible behavior:
  `plugins/agy/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
  `plugins/agy/CHANGELOG.md`.

### Tests to add or update
- `test_delegation_tripwire.py::test_zero_engine_call_write_blocks` — a `Write` tool call with no
  preceding genuine engine invocation and no `delegation-active` state is blocked by the
  `PreToolUse` hook.
- `test_delegation_tripwire.py::test_genuine_agy_run_passes` — a genuine agy run (evidenced by
  `prompt.txt` only, per the absorbed dod_sketch for T15-F2-3) passes the `PreToolUse` hook
  unblocked.
- `test_delegation_tripwire.py::test_stop_hook_classifies_fallback_suspected` — a transcript whose
  `classify_transcript` result is `fallback_suspected` (`agy_delegate.py:1015`) causes the `Stop`
  hook to emit a HALT banner.
- `test_delegation_tripwire.py::test_stop_hook_passes_real_classification` — a transcript classified
  `real` passes the `Stop` hook without a HALT banner.
- `test_delegation_tripwire.py::test_reconciliation_flags_divergence` — a live delegation where the
  transcript-audit verdict and the agent's self-reported verdict disagree is flagged
  `DELEGATION_INTEGRITY`, not silently accepted.
- `test_delegation_tripwire.py::test_codex_bridge_untested_run_classified_false` — a codex-bridge
  run where Claude finished the work itself (no genuine codex launch) is classified
  `codex_launched=false` by the new auditor.
- `test_delegation_tripwire.py::test_two_signal_disagreement_requeues` — a unit where engine signal
  and observer signal disagree is routed to re-queue, and a unit where they corroborate is accepted.
- Full suite, format, lint, and types stay green.

## Definition of Done
- All five tripwires land together: `PreToolUse` block, `Stop`-hook transcript classification,
  live-delegation reconciliation flagging `DELEGATION_INTEGRITY` divergence, codex-bridge auditor
  parity, and two-signal acceptance with re-queue on disagreement.
- `test_delegation_tripwire.py` covers all five mechanisms and passes, and the full suite, format,
  lint, and types stay green (per Verification below).
- The existing release-gate proof flow (`plugins/agy/docs/harness-proof.md`) and
  `classify_transcript` (`agy_delegate.py:989`) continue to work unmodified in their existing call
  sites; this issue only adds new consumers, not a replacement.

### Acceptance criteria
- [ ] A zero-engine-call `Write` is blocked by the `PreToolUse` delegation tripwire hook, while a
      genuine agy run (`prompt.txt` only, matching agy's own evidence convention) passes. (absorbed
      T15-F2-3) Check: `uv run pytest tests/test_delegation_tripwire.py -k zero_engine_call_write_blocks` and `-k genuine_agy_run_passes` → both pass.
- [ ] The `Stop` hook classifies the latest subagent transcript via
      `classify_transcript` (`plugins/agy/scripts/agy_delegate.py:989`) and emits a HALT banner
      when the result is `fallback_suspected`. (absorbed T15-F3-2) Check:
      `uv run pytest tests/test_delegation_tripwire.py -k stop_hook_classifies_fallback_suspected` → passes.
- [ ] Live delegations reconcile the transcript-audit verdict against the agent's self-reported
      verdict, and any divergence is flagged as a distinct `DELEGATION_INTEGRITY` condition rather
      than silently accepted. (absorbed T15-F1-2) Check:
      `uv run pytest tests/test_delegation_tripwire.py -k reconciliation_flags_divergence` → passes.
- [ ] The codex bridge gets the same transcript auditor agy has: a Claude-finished, read-only run
      with no genuine codex launch is classified `codex_launched=false`. (absorbed T15-F6-2) Check:
      `uv run pytest tests/test_delegation_tripwire.py -k codex_bridge_untested_run_classified_false` → passes.
- [ ] A delegation is accepted only when the engine signal and the independent observer signal
      corroborate; disagreement routes the unit to re-queue, not accept. (absorbed T15-F5-4) Check:
      `uv run pytest tests/test_delegation_tripwire.py -k two_signal_disagreement_requeues` → passes.
- [ ] Full suite, format, lint, and types stay green. Check:
      `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` → all pass.

### Verification
```bash
# New tripwire/auditor tests
uv run pytest tests/test_delegation_tripwire.py -v
# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```
Expected: all green; the `PreToolUse` hook demonstrably blocks a zero-engine-call `Write` in a
manual smoke run and passes a genuine agy run; the `Stop` hook demonstrably HALT-banners a
`fallback_suspected` transcript in a manual smoke run.

## Grounding References
- Absorbed ideas (all `T15`, theme "External-LLM integration across lifecycle", from
  `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T15.json`):
  - `T15-F2-3` (primary) — "Real-time fail-loud tripwire: PreToolUse hook kills the manual
    verify-agy-ran step." dod_sketch: "Merged PR adds a PreToolUse `delegation_tripwire_hook.py` +
    delegation-active state file; verified by `test_delegation_tripwire.py` where a zero-engine-call
    Write blocks and a genuine agy run (`prompt.txt` only) passes."
  - `T15-F3-2` (facet) — "Harness-enforce the transcript audit via a Stop hook instead of a
    remembered manual step." (dod_sketch content expired from the ideation-session cache at
    drafting time; reconstructed here from the title, its `proof-of-execution` axis, and the sibling
    `T15-F2-3` dod_sketch's shared verification pattern — `/plan` should re-derive the exact Stop-hook
    contract from `plugins/agy/scripts/agy_delegate.py:989` at implementation time.)
  - `T15-F1-2` (facet) — "Wire agy transcript audit into every live delegation, not just the release
    gate." (dod_sketch content expired from cache; reconstructed from title + `proof-of-execution`
    axis: the release-gate-only invocation is documented at `plugins/agy/docs/harness-proof.md:6-18`,
    `:125` — this facet requires the same audit to run on every live delegation, not only the
    release-gate proof run.)
  - `T15-F6-2` (facet) — "Codex bridge parity: the untested twin gets agy's transcript auditor."
    (dod_sketch content expired from cache; reconstructed from title + `proof-of-execution` axis: no
    `plugins/codex/` directory exists in this repo, confirmed by directory search, so this facet
    requires building the auditor for whatever the codex-bridge equivalent path turns out to be —
    `/plan` to locate it, likely under team-execution's external-engine worker slot.)
  - `T15-F5-4` (facet) — "Two-signal co-stimulation: a delegation is 'accepted' only when engine and
    observer signals corroborate." (dod_sketch content expired from cache; reconstructed from title +
    `silent-fallback-elimination` axis: acceptance requires both the engine's self-reported signal
    and the independent transcript-audit observer signal to agree.)
- Binding decisions this issue builds on and must not violate:
  - `{#external-engines-never-gatekeepers}` (#283) — Claude is verifier-of-record for every gated
    decision; codex/agy are generator / advisory-reviewer / non-gated worker only, structurally
    enforced. Revisit-when: read-only-sandbox profile ships, team-execution gains external-engine
    worker slot (relevant — this issue is part of making that slot's proof-of-execution real).
  - `{#external-engine-chaperone-dispatch}` (#318) — external engines in teams are chaperone
    dispatch only (offload→sonnet/medium, second-opinion→opus/high), never a second executor kind /
    residency / git participant. The two-signal acceptance gate (T15-F5-4) enforces this at runtime.
  - `{#readonly-verifier-fallback-ladder-325}` + `{#verify-agent-git-checkout-clobber}` — any
    verify-class spawn touched by this issue's hook work must use the readonly profile + worktree
    isolation + Explore-first fallback ladder documented in
    `plugins/saga/references/sandbox-spawn-sites.md`.
- Grounding brief: `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §1 (fleet map — "no
  dispatch-time override lever anywhere except saga's readonly-verifier per-call pattern"), §2
  (binding-decision register, both decisions above), §8 theme 1 ("External-LLM integration across
  lifecycle (constrained by never-gatekeepers + chaperone-dispatch decisions)").
- Existing code this issue extends rather than replaces: `plugins/agy/scripts/agy_delegate.py`
  (`classify_transcript` at `:989`, `fallback_suspected` status at `:1015`/`:1368`/`:1614`),
  `plugins/agy/scripts/audit_harness_transcript.py`, `plugins/agy/docs/harness-proof.md` (manual
  invocation pattern), `plugins/saga/hooks/hooks.json` (hook-registration precedent).

### Recommended executor profile
- Model: sonnet
- Effort: high — *target posture: not a live team-execution dispatch knob until `pf-effort-first-class` lands; teammates inherit session tier until then*
- Backend: team-execution
- External LLM: none
- Justification: mechanical, well-scoped hook/auditor wiring against an already-existing,
  already-tested classification function (`classify_transcript`); no architectural judgment call
  large enough to warrant opus. High effort reflects five coordinated facets (two new hooks, one
  reconciliation path, one bridge-parity auditor, one acceptance-gate change) that must land
  together without breaking the existing release-gate proof flow — not a model-tier escalation.
  Team-execution backend because this spans multiple files across `plugins/agy/` and (likely)
  `plugins/team-execution/` or a new codex-bridge module, benefiting from validator-gated review
  across the split.

### Release-surface checklist
Required in the same PR because this changes plugin-visible hook behavior and agy's audit surface:
- [ ] `plugins/agy/.claude-plugin/plugin.json` — version bump + changelog pointer if hook
      registration or `agy_delegate.py` public behavior changes.
- [ ] `.claude-plugin/marketplace.json` — updated if agy's (or a new codex-bridge module's)
      manifest entry changes.
- [ ] `plugins/agy/CHANGELOG.md` — entry documenting the new `PreToolUse`/`Stop` tripwires and
      `DELEGATION_INTEGRITY` status, mirroring the existing "Add static prompt-contract tests,
      wrapper policy tests, harness transcript auditing, and live ..." entry style (`CHANGELOG.md:14`).
- [ ] Any drift-guard / metadata tests in `tests/` that assert plugin.json/marketplace.json/
      CHANGELOG stay in sync — updated to cover the new hook files.
- [ ] `docs/engineering-journal/DECISIONS.md` — entry if the `PreToolUse`/`Stop` hook placement
      pattern (repo `.claude/hooks/` vs. `plugins/agy/hooks/`) sets a new convention for future
      plugin hooks.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan — in particular to resolve the two
cache-expired facet dod_sketches (`T15-F3-2`, `T15-F1-2`, `T15-F6-2`, `T15-F5-4`) into concrete
mechanism decisions (exact Stop-hook contract, codex-bridge auditor location, reconciliation data
shape) grounded against `plugins/agy/scripts/agy_delegate.py:989` and the binding decisions above.

### Source context
- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T15.json` (ids `T15-F2-3`,
  `T15-F3-2`, `T15-F1-2`, `T15-F6-2`, `T15-F5-4`)
- Source type: ideation survivor set (Gate B, theme T15)
- Source title: External-LLM integration across lifecycle — delegation tripwires facet

### Context library links

_none_

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/384
- Number: 384
- Created at: 2026-07-04T07:56:31.445587+00:00

