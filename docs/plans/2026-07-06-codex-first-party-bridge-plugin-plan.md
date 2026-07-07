---
title: First-party codex bridge plugin — retire openai-codex marketplace plugin, guarded delegate like agy
type: feat
status: active
date: 2026-07-06
origin: infiquetra/infiquetra-claude-plugins#476
---

# First-party codex bridge plugin — retire openai-codex marketplace plugin, guarded delegate like agy

## Summary

Build `plugins/codex/` — a first-party, guarded, synchronous codex delegation plugin mirroring the
agy wrapper's shape (`plugins/agy/scripts/agy_delegate.py`) — and rewire the saga engine registry
and dispatch seam to it, retiring every in-repo reference to the openai-codex marketplace plugin's
`codex:codex-rescue` agent. This is the Wave B keystone of outcome `external-engine-offload`
(#336): the only leaf that unblocks another (`sub-384`), and the pending codex receipt emitter for
`bridge_receipt.v1` (#383) — the drift guard already carries
`PENDING_EMITTERS = {"codex-bridge": "#476"}` (`tests/test_bridge_receipt_drift.py:45`).

## Problem Frame

The codex lane rides an upstream marketplace plugin that is structurally wrong for fleet dispatch
(evidence in #476, verified 2026-07-05): its jobs are session-scoped (`SessionEnd` hook reaps the
process tree, so any dispatch from an ephemeral workflow unit or subagent dies with its launcher),
its foreground `--wait` collides with the Bash tool's 10-minute ceiling, reaped jobs stay
`status: running` forever, and — being upstream code — we cannot add receipt emission (#383),
credential preflight (#389), or economics guards (#386) to it. The agy lane never had these
failures because `agy_delegate.py` is synchronous, bounded, and evidence-emitting by construction.
The codex lane needs the same shape.

## Requirements

- **R1.** `plugins/codex/` first-party plugin with a guarded `codex_delegate.py` wrapping the
  `codex` CLI (0.142.5 verified present at `~/.local/bin/codex`): a synchronous bounded envelope,
  callable from ephemeral subagents and workflow units without lifecycle loss.
- **R2.** Modes matching the agy role/mode/lens surface: `reviewer` role (review / second-opinion
  lenses) is **enforced read-only** with diff-scan proof; `coder` role (task) is write-capable but
  scoped — patch capture in a disposable clone, never direct mutation of the live tree.
- **R3.** Evidence bundle per run at `.claude/codex/runs/<run-id>/` (mirroring
  `.claude/agy/runs/`): envelope, prompt, raw JSONL transcript, last agent message, diff-scan
  read-only proof, token accounting, `result.json`, projection — feeding `bridge_receipt.v1`
  (#383) and attestation (#388).
- **R4.** No background jobs: the delegate blocks; callers own their timeout budget. On timeout the
  delegate kills the codex process tree and records a **terminal** status — on-disk state never
  says `running` for a dead worker. The same die-clean semantics apply to external termination:
  the delegate handles SIGTERM/SIGINT by killing the codex process tree, finalizing a terminal
  bundle, and exiting nonzero (a caller's Bash-tool timeout is the expected delivery vector).
- **R5.** Registry rewire: both codex rows in `plugins/saga/references/engine-registry.yaml`
  (`:27`, `:58`) point their `invocation.via` at the new delegate; the stale `recipe` string is
  corrected (`--effort` is not a flag on 0.142.5 — verified live; effort rides
  `-c model_reasoning_effort=<effort>`); `build_codex_invocation`
  (`plugins/saga/scripts/engine_dispatch.py:55`) builds the new envelope; dispatch docs updated.
- **R6.** Retirement: every in-repo `codex:codex-rescue` reference replaced (registry, dispatch,
  `plugins/saga/references/engine-dispatch.md`,
  `plugins/team-execution/skills/team-execution/references/external-engine-workers.md`, tests);
  an operator runbook note documents uninstalling the openai-codex marketplace plugin.
- **R7.** Lifecycle test proving a subagent-dispatched delegation survives the launcher's exit or
  fails loud: hermetic fake-codex-bin tests (timeout → terminal status, dead process tree, no
  `running` record) plus an availability-gated live smoke.
- **R8.** Receipt emission through the shared path only: vendored byte-identical
  `fleet_commons_shim.py` + `emit_receipt(...)`, emit-only-when-launched (agy's
  `_supervised_receipt` contract, `plugins/agy/scripts/agy_delegate.py:1390-1412`); the drift
  guard's `codex-bridge` entry moves `PENDING_EMITTERS` → `IN_REPO_EMITTERS` in the same commit
  that creates `plugins/codex/` (the guard's plugin-dir sentinel reds otherwise —
  `tests/test_bridge_receipt_drift.py:209`).

## Key Technical Decisions

**KTD1 — Mirror the agy delegation grammar, don't invent a codex-shaped one.** Schema
`codex.delegation.v1` with the same role/mode/lens/status vocabulary as `agy.delegation.v1`
(dropping agy-only members where inapplicable), same bundle file names, same
`.claude/<plugin>/runs/<run-id>/` home. One fleet delegation shape means #384's transcript auditor
and every operator learn one grammar. Rejected: a bespoke schema shaped around codex CLI
specifics — it would fork the auditing surface for zero capability gain.

**KTD2 — Synchronous supervised subprocess; zero plugin-level job state.** The delegate launches
`codex exec`, supervises it with a wall-clock timeout and no-output watchdog (agy's
`SupervisedRunResult` pattern), kills the process tree on expiry, and always exits with a terminal
status. Long runs ride the *caller's* mechanism (e.g. the harness's background Bash) — the plugin
never writes a `running` record, so the marketplace plugin's zombie-state failure class is
structurally impossible. Rejected: a v1 detach+poll mode — deferred (see Scope Boundaries) with
hard requirements recorded, because durable cross-session job state is exactly the surface that
rotted upstream.

**KTD3 — codex invocation shape (verified live on 0.142.5).**
`codex exec --json -o <bundle>/last-message.txt -s <sandbox> -m <model>
-c model_reasoning_effort=<effort> --ephemeral` with the prompt delivered via stdin (closed after
write); `-m` is omitted when the envelope names no model (codex falls back to the user config
default). Rationale: `--json` gives a machine-parseable JSONL event stream captured raw as the
transcript; `-o` pins the final message; stdin delivery keeps large prompts out of ps-visible
argv (codex appends piped stdin as a `<stdin>` block — verified); `--ephemeral` keeps host-level
`~/.codex/sessions` state out of the contract (the bundle is the evidence, not codex's cache).
Clone runs add `--cd <clone>` and `--skip-git-repo-check`. Token accounting is a best-effort parse
of usage events from the JSONL; the raw transcript is the durable fallback (tolerant parse —
JSONL schema may drift across codex versions).

**KTD4 — Registry recipe correction is part of the rewire, not a drive-by.** The current rows'
`recipe: "codex -s read-only --effort high"` names a flag that does not exist on 0.142.5
(verified: `codex exec --help` has no `--effort`; `~/.codex/config.toml` and a live probe confirm
`model_reasoning_effort`). U4 corrects both rows' `recipe` and bumps `last_validated`. Rejected:
leaving the recipe as prose-only documentation — the registry is the machine-consumed source of
truth and a wrong recipe there is exactly the drift class the journal warns about.

**KTD5 — Fleet-dispatch write posture unchanged.** Registry rows keep `write_capable: false`;
`build_codex_invocation`'s halt-on-write guard (halt-not-downgrade, #287 R4/R6) stays. The
write-capable `task` mode is the plugin's own operator surface (like agy's `patch-only`), not a
fleet-dispatch capability in v1 — wiring sandboxed-mutate dispatch for codex is follow-up work
once the patch-capture path has operational history. Rejected: enabling write dispatch now —
it couples an untested write path to the keystone landing.

**KTD6 — Same-commit drift-guard move.** `tests/test_bridge_receipt_drift.py` sentinels on the
existence of `plugins/codex/` (`PENDING_EMITTER_PLUGIN_DIR`); the moment the directory exists the
suite reds unless `codex-bridge` has moved to `IN_REPO_EMITTERS` pointing at a delegate source
containing the shim-loaded `emit_receipt` call. Therefore U1 lands the scaffold, the delegate file
with its receipt builder, **and** the guard move together. Rejected: sequencing them across
commits — an intentionally-red intermediate tree buys nothing.

## High-Level Technical Design

One script, one flow (agy's proven shape): envelope in (CLI flags or `--envelope` JSON) →
validate against `codex.delegation.v1` (fail loud, `EnvelopeError`) → create bundle skeleton at
`.claude/codex/runs/<run-id>/` → resolve workspace (live repo read-only for reviewer; disposable
clone for coder/task) → snapshot the workspace state (`git status --porcelain` baseline) →
launch `codex exec` per KTD3 → supervise (timeout, no-output watchdog, SIGTERM/SIGINT die-clean
handler, stream capture) → post-run diff scan against the pre-run snapshot (reviewer: any **new**
mutation relative to the baseline ⇒ `out_of_scope_mutation` — a pre-dirty operator tree must not
false-positive; coder: diff ⇒ patch file, preserve-patch policy) → build receipt iff launched →
write `result.json` + projection → exit with mapped status. `--validate-only`/`--dry-run` stops
after the bundle skeleton, exactly like agy.

Dispatch seam: `_build_invocation` (`engine_dispatch.py:481`) keeps its `engine_id == "codex"`
arm; `build_codex_invocation` returns the new delegate invocation (via the plugin's delegate
identifier) instead of `via: "codex:codex-rescue"`, preserving the R11 byte-preservation guarantee
and the write-halt guard.

## Implementation Units

### U1. Plugin scaffold + envelope schema + drift-guard move

**Goal:** `plugins/codex/` exists with plugin metadata, the vendored shim, `codex_delegate.py`
carrying the `codex.delegation.v1` envelope schema/validation and the receipt builder, and the
drift guard moved to `IN_REPO_EMITTERS` — one commit, tree stays green (KTD6).

**Deliverables:** `plugins/codex/.claude-plugin/plugin.json` (0.1.0), `README.md`, `CHANGELOG.md`,
`commands/delegate.md`, `skills/codex-delegate/SKILL.md`, `agents/codex-coder.md` +
`agents/codex-reviewer.md`, byte-identical `scripts/fleet_commons_shim.py`,
`scripts/codex_delegate.py` (schema constants, `Envelope` dataclass, validation, `_supervised_receipt`-parity
receipt builder), `tests/test_bridge_receipt_drift.py` entry move.

**Test scenarios** (`tests/test_codex_delegate_contract.py`, `tests/test_codex_plugin.py`):
envelope round-trip valid/invalid (unknown role, unknown mode, reviewer+write_set rejection, empty
task); plugin.json required fields; vendored shim byte-equality (existing fleet-core drift guard
picks this up automatically); drift-guard suite green with the dir present.

### U2. Supervised synchronous runner + evidence bundle

**Goal:** the delegate launches and supervises `codex exec` (KTD2/KTD3), captures the JSONL
transcript and last message, kills the tree on timeout/no-output, handles SIGTERM/SIGINT with the
same die-clean semantics (kill tree, finalize a terminal bundle, exit nonzero — R4), maps exit
conditions onto the status vocabulary, writes the full bundle, and emits the receipt iff launched
(R8).

**Depends on:** U1.

**Deliverables:** run loop in `codex_delegate.py` (`--codex-bin` override for hermetic tests,
mirroring agy's `--agy-bin`); bundle files: `envelope.json`, `prompt.txt`, `command.json`,
`transcript.jsonl`, `last-message.txt`, `result.json`, `projection.md`; token-accounting
best-effort parse; stdin prompt delivery with explicit close.

**Test scenarios** (`tests/test_codex_delegate_contract.py`): fake-bin success run produces full
bundle + receipt with `engine_id="codex"`, `transport="cli"`, pid/argv/exit_code; launch failure
(missing bin) → fail-loud status, `codex_launched=false`, **no receipt**, result still validates;
timeout → process tree dead (poll the fake bin's child pid), terminal `timeout` status, no
`running` anywhere in the bundle (R4/R7 lifecycle guarantee); SIGTERM delivered mid-run → tree
killed, terminal bundle finalized, nonzero exit (the die-clean handler, R4); malformed JSONL
lines tolerated (raw transcript intact, accounting degrades to nulls, run does not fail).

### U3. Modes — enforced read-only review, patch-capture task

**Goal:** reviewer role runs `-s read-only` against the live repo with a post-run diff scan that
proves non-mutation against a pre-run `git status --porcelain` snapshot (any **new** dirt relative
to the baseline ⇒ `out_of_scope_mutation`; a pre-dirty operator tree must not false-positive);
coder role runs `-s workspace-write` inside a disposable remotes-stripped clone with `--cd`,
captures the diff as a patch artifact (`preserve-patch`), and never touches the live tree
(R2, KTD5).

**Depends on:** U2.

**Test scenarios** (`tests/test_codex_delegate_modes.py`): reviewer + fake bin that mutates a file
→ `out_of_scope_mutation` with the diff-scan proof in the bundle; reviewer on a **pre-dirty**
workspace + non-mutating fake bin → success, no false positive (snapshot-based scan); coder +
fake bin writing in the clone → patch file present, live repo untouched (assert the primary
tree's `git status` is unchanged from its pre-run snapshot); coder respecting `write_set` scoping
(out-of-set mutation flagged); clone teardown on both success and failure paths.

### U4. Registry + dispatch rewire

**Goal:** both codex registry rows point at the first-party delegate; the stale recipe is
corrected (KTD4); `build_codex_invocation` builds the new envelope; dispatch reference docs match.

**Depends on:** U1 (delegate identifier exists); independent of U2/U3 internals.

**Deliverables:** `engine-registry.yaml` rows — `invocation.via: codex:delegate` (mirroring the
`agy:delegate` convention at registry `:85`/`:116`), corrected recipe, `last_validated:
2026-07-06`, `receipt_emitter: codex-bridge` unchanged; `engine_dispatch.py`
`build_codex_invocation` rewrite emitting `via: "codex:delegate"` while preserving the write-halt
guard and `_assert_payload_preserved`;
`plugins/saga/references/engine-dispatch.md` and
`plugins/team-execution/skills/team-execution/references/external-engine-workers.md` updated.

**Test scenarios** (existing suites updated: `tests/test_saga_engine_dispatch.py`,
`tests/test_saga_engine_registry.py`, `tests/test_saga_engine_resolver.py`): invocation carries
the new via and verbatim payload; sandboxed-mutate unit routed to codex still HALTS; registry
routing-stability literals updated alongside the row change (the regression test pins them).

### U5. Retirement dereference + operator runbook

**Goal:** zero in-repo references to `codex:codex-rescue` remain outside historical
CHANGELOG/journal entries; the uninstall path for the marketplace plugin is documented.

**Depends on:** U4.

**Deliverables:** reference sweep (grep-verified); runbook section in `plugins/codex/README.md`
(uninstall openai-codex marketplace plugin, name-collision note: both plugins claim the `codex:`
namespace, so the marketplace copy must be uninstalled before this plugin's agents resolve
cleanly); note in saga CHANGELOG.

**Test expectation:** none — documentation and dereference sweep; the U4 suites already lock the
behavioral surface. Verification is the grep sweep recorded in the work session.

### U6. Lifecycle + live conformance tests

**Goal:** the R7 lifecycle proof and the availability-gated live smoke.

**Depends on:** U2, U3.

**Test scenarios** (`tests/test_codex_delegate_lifecycle.py`): launcher-exit survival — start a
delegation from a child process that exits immediately after the delegate returns (synchronous
contract: the delegate cannot outlive its caller, so the proof is that a completed run's bundle is
terminal and self-contained, and a killed-mid-run delegate leaves a killed process tree and a
resumable-diagnosable bundle, never `running`); fake-bin sleep-past-timeout → tree dead within the
grace window; live smoke (skip-not-fail): gated on `codex login status` exiting 0 (verified live —
exits 0 when authenticated), one `codex exec` round-trip through the delegate asserting receipt +
transcript + last message (mirrors the Ollama availability-gated smoke posture).

### U7. Release surfaces + journal

**Goal:** installed-plugin metadata tells the same story as the diff (repo development-workflow
rule).

**Depends on:** U1–U6.

**Deliverables:** `.claude-plugin/marketplace.json` gains the codex plugin (0.1.0); saga version
bump (registry + dispatch + docs changed); team-execution version bump (reference doc changed);
all touched CHANGELOGs; DECISIONS entry for KTD1–KTD6 (`{#codex-first-party-bridge-476}`);
LEARNINGS entry for the stale-recipe catch if it generalizes; drift-guard metadata tests
(`tests/test_plugin_versions.py` or equivalent parity guard) green.

**Test expectation:** none beyond the existing Release Surface Parity CI gate — metadata-only unit.

## Execution

Backend: `cc-workflows-ultracode` (operator-chosen 2026-07-06; recommender said `team-execution` —
divergence recorded on saga `issue-476`). The canonical execution artifact is
`docs/plans/2026-07-06-codex-first-party-bridge-plugin-spec.json`; the emitted
`docs/plans/2026-07-06-codex-first-party-bridge-plugin.workflow.js` carries a **post-emit hand
patch** on all 9 verifier prompts (mandatory `git checkout feat/476-codex-first-party-bridge -- .`
materialization + examined-SHA quoting, per journal `{#verify-panels-blind-to-uncommitted-tree}`)
— re-emitting from the spec loses the patch; re-apply before running.

Work branch: `feat/476-codex-first-party-bridge` from `main`. The unit chain is fully serialized
(operator rate-limit guardrail: max 3 concurrent non-haiku agents); every worker commits its
completed unit so verify panels evaluate committed state; refute-3 panels ride U2/U3/U6.

| Unit | Tier | Panel | Spend |
|------|------|-------|-------|
| U1 | sonnet/high | — | 12 |
| U2 | opus/high | refute-3 majority | 128 |
| U3 | opus/high | refute-3 majority | 128 |
| U4 | sonnet/high | — | 12 |
| U5 | sonnet/medium | — | 6 |
| U6 | **fable/xhigh** (operator-directed 2026-07-06) | refute-3 majority | 364 |
| U7 | sonnet/medium | — | 6 |

Total spend 656 ordinal units (`execution_spec.py spend`, validated with `--require-receipts`).
U6's bump rationale: the lifecycle proof is the highest-leverage unit — a vacuous-green suite
fails invisibly and re-ships the zombie-`running` class; the panel rides the unit tier, so fable
also refutes fable's test design.

## Scope Boundaries

**Non-goals (from the issue, held):** the shared HTTP substrate (#387 — shipped, this sits beside
it behind `engine_dispatch`); the transcript auditor (#384 — consumes this plugin's bundles);
second-opinion reconciliation logic (#393).

**Deferred to Follow-Up Work:**
- Detach+poll mode for driving-session long runs — only with durable job state that survives the
  launcher and can never report `running` for a dead worker (the issue's own hard requirement);
  v1 callers use the harness's background-Bash for long runs.
- Write-capable fleet dispatch for codex (sandboxed-mutate → patch import parity with agy) —
  after the task-mode patch path has operational history (KTD5).
- Cross-repo retirement: removing openai-codex from fleet-standard install manifests lives in the
  fleet/ops repos (home-lab, context-library), not here — tracked as an ops follow-up in the
  work-session notes.
- Economics guards (#386) and credential preflight (#389) integration — those issues consume this
  plugin; nothing here blocks them.

## Risk Analysis & Mitigation

- **codex auth dependency:** live smoke requires a ChatGPT-authenticated codex; hermetic fake-bin
  tests carry the suite, live smoke is skip-not-fail (same posture as the Ollama smoke).
- **JSONL event-schema drift across codex versions:** raw transcript capture is the contract;
  token accounting parses tolerantly and degrades to nulls (KTD3).
- **stdin handling:** codex appends piped stdin as a `<stdin>` block and blocks reading it —
  verified live; the delegate must write-then-close stdin deliberately. U2 test covers a fake bin
  that echoes stdin to prove delivery and no hang.
- **`codex:` namespace collision while both plugins are installed:** documented in the U5 runbook;
  the retirement ordering (uninstall marketplace copy) resolves it; nothing in-repo depends on the
  marketplace agent after U4/U5.
- **Timeout semantics vs Bash-tool ceiling:** the default `--timeout-seconds` mirrors agy (900s),
  which exceeds the Bash tool's 10-minute foreground cap — a foreground caller gets SIGTERM'd
  before the delegate's own timeout fires. That is why the SIGTERM die-clean handler is a hard R4
  requirement, not polish: external kill must produce the same terminal-bundle guarantee as
  internal timeout. Callers either lower the timeout, or run the delegate in background Bash —
  documented in SKILL.md.
