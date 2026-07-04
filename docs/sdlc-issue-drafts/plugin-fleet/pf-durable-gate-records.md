---
title: "capability: gates as durable approval records with a linted operator-absence contract"
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
wave: wave-1
objective: "Ship run-start intent envelope for lifecycle autonomy"
---

# capability: gates as durable approval records with a linted operator-absence contract

### Objective
Ship run-start intent envelope for lifecycle autonomy

### Intent
Replace the fleet's implicit "gate = an `AskUserQuestion` call" assumption with an explicit,
durable gate-record contract, and make every gate site prove it declared what happens when the
operator never answers. A gate becomes a record — question, options, declared no-answer behavior
(HALT / safe-default-with-record / escalate, default HALT), the eventual answer, the answerer, and a
timestamp — written before any consumer proceeds, with `AskUserQuestion` demoted to one pluggable
transport among several rather than the record itself. A fleet-wide CI lint walks every saga and
team-execution gate site and fails the build if a gate has no declared absence contract, so "we
forgot to say what happens on silence" becomes a build failure, not an operator surprise discovered
in production.

This closes two adjacent, previously-separate survivor candidates from the same ideation pass into
one mechanism: the durable-record primitive (`H-F3-3`) and the static absence-contract lint
(`H-F6-5`). They are the same "distrust the widget" instinct at two different points — runtime
(the record never resolves on silence) and build time (the lint refuses to let a gate ship without
declaring what silence means) — and belong in one PR because the lint's schema check is only
meaningful once the record schema it checks against exists.

### Problem / motivation

**The primitive itself is unreliable, repeatedly, across repos.** Session-mining synthesis
(workflow `wf_7e5d77a2-5c0`, 27 sessions, 175 findings) ranks "gate-primitive unreliability" as the
#2 recurring pattern by repo spread: `AskUserQuestion` silently auto-proceeds on timeout — treating
silence as consent — fires before an answer is actually captured, or errors outright; agents in 6
different repos worked around it by falling back to plain-text questions
(`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:113-116`). That is exactly the shape this
capability targets: a gate today has no durable state independent of the widget call that raised it,
so a timeout, a dropped session, or a primitive error all collapse into the same silent-proceed
failure mode, indistinguishable from an affirmative answer.

**Every existing gate site in this fleet is a live instance of the problem, not a hypothetical one.**
`AskUserQuestion` is the gate mechanism named directly in `plugins/saga/skills/brainstorm/SKILL.md:31`,
`plugins/saga/skills/code-review/SKILL.md:61-65`, `plugins/saga/skills/founder-review/SKILL.md:80-85`,
`plugins/saga/skills/ideate/SKILL.md:36-37`, `plugins/saga/skills/investigate/SKILL.md:91-98`, and
`plugins/saga/skills/loop/SKILL.md:72-74` — each of these is a distinct gate with no shared durable
record, no shared absence-behavior declaration, and no lint checking either exists. Each skill
independently documents a channel-session fallback ("inline the choices") but none of them declare a
machine-readable no-answer behavior; the fallback is prose guidance an agent can miss, not a
structural guarantee.

**A structurally similar, narrower gate already exists and sets the pattern to extend, not invent.**
`engine_dispatch.satisfy_gate()` (`plugins/saga/scripts/engine_dispatch.py:281-303`) already refuses to
let external-engine advisory evidence satisfy a gate unless `verified_by_claude is True` — a
structural guard, not a prompt convention (`plugins/saga/references/engine-dispatch.md:31`,
`docs/engineering-journal/DECISIONS.md:1985-1996`, binding decision
`{#external-engines-never-gatekeepers}` (#283)). This capability generalizes that same
"structural refusal, not prompt discipline" move from one narrow gate (external-engine verification)
to the fleet's general operator-approval gates — but it must not weaken or bypass the existing
external-engine gate; `satisfy_gate()` stays the authority for that specific gate and is out of scope
here except as the precedent this new mechanism follows.

**Binding decisions this capability must honor, not re-litigate.** The `/outcome` campaign settled
HALT-not-degrade as the fleet's default failure posture (`docs/engineering-journal/DECISIONS.md`,
`plugins/saga/scripts/outcome_dispatcher.py:8-22` — "an unavailable backend HALTs when the operator is
not present... never degrades silently") and derived-on-read status over committed state
(`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:44` — the `/outcome` campaign decision
register). The new gate-record's default no-answer behavior must be HALT, matching this posture, and
the record itself must be derivable/pollable rather than requiring the coordinator to hold gate state
in memory across a session boundary — the T6-F3-3 pause primitive (a `.saga/pause` sentinel with
QUIESCE drain semantics, same ideation theme) is a sibling mechanism, not a substitute; this issue
does not build the pause sentinel.

**Gate-B (the ideation pass's own convergence checkpoint) explicitly struck the harness-level
primitive fix as out of scope**, redirecting to routing around it plugin-side instead of fixing
`AskUserQuestion` itself (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:170-172`,
theme 6 resolution: "AskUserQuestion primitive reliability struck — harness-level, out of scope for
this backlog"). This capability is that redirection: it does not modify or attempt to fix the
`AskUserQuestion` tool; it builds a durable record layer that treats `AskUserQuestion` as a
replaceable, distrusted transport.

### Out-of-scope / non-goals
In scope:
- A durable gate-record schema and read/write/poll helpers, callable from saga skills and
  team-execution, with `AskUserQuestion` wired as one transport implementation.
- A second, alternate transport wired end-to-end (e.g. a file-based or redis-channel transport) to
  prove the transport seam is genuinely pluggable, not `AskUserQuestion` with extra steps.
- A machine-readable `absence_behavior` field (`HALT` / `safe-default-with-record` / `escalate`,
  default `HALT`) required on every gate-record.
- A CI lint that enumerates every gate call site across `plugins/saga` and
  `plugins/team-execution` and fails if any declares no `absence_behavior`.
- Migrating the six existing `AskUserQuestion`-documented gate sites listed above to construct a
  gate-record (even if they keep using `AskUserQuestion` as their transport) so the lint has
  something real to check on day one.

Out of scope (non-goals):
- Fixing or modifying the `AskUserQuestion` tool itself — struck by Gate-B as harness-level.
- The `.saga/pause` sentinel / QUIESCE drain primitive (`T6-F3-3`'s sibling, sits under the same
  ideation theme but is a distinct mechanism: pausing a running plan vs. gating a single decision).
  Not built here.
- Changing `engine_dispatch.satisfy_gate()`'s external-engine verification gate — referenced as
  precedent only; its behavior and authority are unchanged.
- Backfilling every gate site in every plugin in one PR. v1 migrates the six sites cited above (the
  ones with documented `AskUserQuestion` usage in `saga`); a fleet-wide sweep of any remaining
  undiscovered gate sites is a fast-follow the lint itself will surface (any site the lint doesn't
  yet know to check is a gap the lint's own site-enumeration step should make visible, not silently
  skip).
- A new consensus or escalation UI. `escalate` is a declared enum value with defined semantics
  (surface to a human channel and HALT pending response); it does not require building a new
  notification surface in this issue.

## Definition of Done

A merged PR that adds:
1. A gate-record module (proposed: `plugins/saga/scripts/gate_record.py`) defining the record schema
   (question, options, `absence_behavior`, answer, answerer, timestamp, transport) plus
   `open_gate()` / `poll_gate()` / `satisfy_gate_record()` helpers that block/poll on the record, not
   on a widget call's return value.
2. Two wired transports: `AskUserQuestion` (existing) and one alternate (file-sentinel or
   redis-channel), selected via the same transport seam.
3. A CI lint script (proposed: `plugins/saga/scripts/lint_gate_absence_contract.py`, wired into the
   existing CI check suite) that walks all `plugins/saga` and `plugins/team-execution` gate call
   sites and fails the build on any gate lacking a declared `absence_behavior`.
4. The six existing `AskUserQuestion` gate sites (brainstorm, code-review, founder-review, ideate,
   investigate, loop) updated to construct a gate-record with an explicit `absence_behavior` before
   invoking their transport.
5. Tests proving: silence never resolves to an implicit affirmative answer; a gate-record's answer
   is captured and readable before any consumer proceeds; the lint fails on a gate call site with no
   declared absence contract and passes once one is declared; a gate-record survives a simulated
   session restart (re-read from disk/store resumes the same pending gate rather than re-prompting
   or silently dropping it).
6. Release-surface updates: `plugins/saga/CHANGELOG.md` entry, `plugins/saga/.claude-plugin/plugin.json`
   version bump, root `.claude-plugin/marketplace.json` version sync, and any drift-guard test that
   checks plugin/marketplace version parity updated to reflect the bump.

### Acceptance criteria
- [ ] **(H-F3-3 facet — durable record, not a widget timeout.)** A gate opened via `open_gate()`
  writes a persisted record before the transport is invoked, and a session interrupted mid-gate (no
  answer captured) resumes against the same pending record on restart rather than re-issuing a fresh
  prompt or silently proceeding. Check: `uv run pytest tests/test_gate_record.py -k session_restart`
  → passes.
- [ ] **(H-F3-3 facet — silence never times out to consent.)** A gate whose transport returns no
  answer (timeout, error, or dropped call) resolves to the gate's declared `absence_behavior`, never
  to an implicit "yes"/proceed. Check:
  `uv run pytest tests/test_gate_record.py -k silence_never_consent` → passes.
- [ ] **(H-F3-3 facet — pluggable transport, `AskUserQuestion` demoted.)** The same `open_gate()` call
  succeeds against both the `AskUserQuestion` transport and the alternate transport, with identical
  record semantics; `AskUserQuestion` is not special-cased in the record schema or the poll/satisfy
  helpers. Check: `uv run pytest tests/test_gate_record.py -k transport_parity` → passes.
- [ ] **(H-F3-3 facet — answer captured before consumer proceeds.)** A consumer awaiting a gate result
  reads the persisted record's answer field, never the transport call's raw return value directly.
  Check: `uv run pytest tests/test_gate_record.py -k answer_read_from_record` → passes.
- [ ] **(H-F6-5 facet — lint enumerates and fails on missing absence contract.)** Running the lint
  against a fixture gate site with no declared `absence_behavior` exits non-zero and names the site.
  Check: `python3 plugins/saga/scripts/lint_gate_absence_contract.py --fixture tests/fixtures/gate_missing_absence.py`
  → exit code `1`, output names the offending call site.
- [ ] **(H-F6-5 facet — lint passes once declared.)** The same fixture with `absence_behavior="HALT"`
  added passes the lint. Check:
  `python3 plugins/saga/scripts/lint_gate_absence_contract.py --fixture tests/fixtures/gate_with_absence.py`
  → exit code `0`.
- [ ] **(H-F6-5 facet — default is HALT, matching the fleet's binding failure posture.)** A gate
  constructed without an explicit `absence_behavior` argument defaults to `HALT`, not
  `safe-default-with-record` or `escalate`. Check: `uv run pytest tests/test_gate_record.py -k default_is_halt` → passes.
- [ ] **(Migration — six existing gate sites carry the contract.)** Each of the six
  `AskUserQuestion`-documented gate sites (`brainstorm`, `code-review`, `founder-review`, `ideate`,
  `investigate`, `loop`) constructs a gate-record with a declared `absence_behavior` before calling its
  transport. Check: `python3 plugins/saga/scripts/lint_gate_absence_contract.py --scan plugins/saga/skills`
  → exit code `0`, report lists all six sites as compliant.
- [ ] **(Precedent respected — `satisfy_gate()` unchanged.)** `engine_dispatch.satisfy_gate()`'s
  existing external-engine verification behavior is untouched by this change. Check:
  `uv run pytest tests/test_engine_dispatch.py -k satisfy_gate` → passes, no diff in
  `plugins/saga/scripts/engine_dispatch.py` gate-authority logic.
- [ ] **(Release surface.)** `plugins/saga/.claude-plugin/plugin.json` version, root
  `.claude-plugin/marketplace.json` version, and `plugins/saga/CHANGELOG.md` all reflect this change
  in the same PR. Check: `uv run pytest tests/test_marketplace_drift.py` (or the repo's existing
  version-parity drift-guard test) → passes.
- [ ] Full suite, format, lint, and types stay green. Check:
  `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` → all pass.

### Release-surface checklist
- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump
- [ ] `.claude-plugin/marketplace.json` — version sync
- [ ] `plugins/saga/CHANGELOG.md` — entry for this change
- [ ] Drift-guard test (`tests/test_marketplace_drift.py` or equivalent) updated and passing to
  confirm plugin/marketplace version parity

## Grounding References

- **Absorbed idea `H-F3-3`** — "Gates are durable approval records with pluggable transports, not
  AskUserQuestion widgets" (tier: structural, survive). `dod_sketch`: a durable pending-approval
  gate-record contract with write/poll/satisfy helpers in saga, blocking on the record rather than a
  widget timeout, with one alternate transport wired; test asserts silence never times out to consent
  and a gate survives a session restart. Basis: the recurring cross-repo pattern at
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:113-116` (gate-primitive unreliability,
  6 repos) and the existing `satisfy_gate()` precedent at
  `plugins/saga/scripts/engine_dispatch.py:281-303`.
- **Absorbed idea `H-F6-5`** — "Operator-absence contract: every gate declares its machine-readable
  no-answer behavior, linted fleet-wide" (tier: structural, survive). `dod_sketch`: a declared
  absence-behavior field (HALT/safe-default-with-record/escalate, default HALT) on every saga/
  team-execution gate site, plus a CI lint that walks all plugins and fails on any undeclared gate;
  test asserts an undeclared gate fails the lint. Explicitly distinguished from `H-F3-3` as static
  enforcement vs. runtime record — merged into one issue here because the lint's schema check has
  no meaning without the record schema `H-F3-3` defines.
- **Binding decision `{#external-engines-never-gatekeepers}` (#283)** — Claude is verifier-of-record
  for every gated decision; this capability's gate-record mechanism does not create a new path for an
  external engine to satisfy a gate, and must not weaken `satisfy_gate()`'s existing structural
  refusal (`docs/engineering-journal/DECISIONS.md:1985-1996`).
- **`/outcome` campaign decision register** — HALT-not-degrade as the default failure posture
  (`plugins/saga/scripts/outcome_dispatcher.py:8-22`) and derived-on-read status over committed state
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:44`) — both bind this capability's default
  `absence_behavior` and its record's poll-not-hold-in-memory shape.
- **Gate-B resolution (theme 6)** — "AskUserQuestion primitive reliability struck — harness-level,
  out of scope for this backlog" (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:170-172`).
  This capability is the plugin-side routing-around move Gate-B redirected to, not an attempt to
  fix the primitive.
- **Killed duplicates absorbed by `H-F3-3`, not separately tracked**: `H-F1-1` ("Consent-receipt
  protocol") and `H-F4-8` ("Confirmed-gate wrapper") were both struck as duplicates of `H-F3-3`
  during convergence — their intent (silence=HALT, captured affirmative artifact) is already covered
  by this issue's acceptance criteria and does not need separate treatment.
- **Sibling, out-of-scope theme-6 mechanism**: `T6-F3-3` (the `.saga/pause` sentinel / QUIESCE drain
  primitive) shares this ideation theme but gates a *running plan's* pause point, not a single
  operator decision; it is a distinct future capability, not built here.

### Files expected to change

Indicative only — the exact set is `/plan`'s to determine.
- `plugins/saga/scripts/gate_record.py` — new gate-record schema + open/poll/satisfy helpers (proposed path).
- `plugins/saga/scripts/lint_gate_absence_contract.py` — new CI lint walking gate call sites (proposed path).
- `plugins/saga/skills/brainstorm/SKILL.md`, `plugins/saga/skills/code-review/SKILL.md`,
  `plugins/saga/skills/founder-review/SKILL.md`, `plugins/saga/skills/ideate/SKILL.md`,
  `plugins/saga/skills/investigate/SKILL.md`, `plugins/saga/skills/loop/SKILL.md` — each gate call
  site updated to construct a gate-record with a declared `absence_behavior`.
- `plugins/saga/.claude-plugin/plugin.json` — version bump.
- `.claude-plugin/marketplace.json` — version sync.
- `plugins/saga/CHANGELOG.md` — entry for this change.
- `tests/test_gate_record.py` — new record/transport/absence-behavior tests (repo-root collected).
- `tests/fixtures/gate_missing_absence.py`, `tests/fixtures/gate_with_absence.py` — lint fixtures.

### Tests to add or update
- Gate-record: writes before transport invocation; survives simulated session restart; answer read
  from record, not transport return value.
- Absence behavior: defaults to `HALT`; silence never resolves to implicit consent; each of
  `HALT`/`safe-default-with-record`/`escalate` is a distinct, testable resolution path.
- Transport parity: `AskUserQuestion` and the alternate transport produce identical record semantics.
- Lint: fails on a fixture gate site with no declared `absence_behavior`; passes once declared; scans
  and reports all six migrated `saga` gate sites as compliant.
- Regression: `engine_dispatch.satisfy_gate()`'s existing external-engine gate behavior is unchanged.
- Release-surface drift-guard test (plugin.json/marketplace.json version parity) still passes.

### Context library links
- source_context: docs/plans/2026-07-03-plugin-fleet-grounding-brief.md

### Recommended executor profile
- **Model:** Sonnet
- **Effort:** xhigh — *target posture: not a live team-execution dispatch knob until `pf-effort-first-class` lands; teammates inherit session tier until then*
- **Backend:** team-execution
- **External-LLM posture:** none
- **Justification:** This is mechanical-but-wide-blast-radius work — a new shared primitive consumed
  by six existing gate sites plus a fleet-wide CI lint. It does not require Opus-tier judgment (the
  schema, transports, and lint logic are fully specified above), but xhigh effort at Sonnet matches
  the coordination cost of touching six skill files consistently and getting the lint's site-scan
  logic right without missing a call site. team-execution is recommended over inline/saga direct
  execution because the six-site migration plus new-module-plus-lint shape benefits from validator
  gates checking each migrated site independently rather than one large diff self-certifying.

### Verification
```bash
# New gate-record + lint unit tests
uv run pytest tests/test_gate_record.py -v
# Lint fails on missing absence contract, passes once declared
python3 plugins/saga/scripts/lint_gate_absence_contract.py --fixture tests/fixtures/gate_missing_absence.py; echo "exit: $?"
python3 plugins/saga/scripts/lint_gate_absence_contract.py --fixture tests/fixtures/gate_with_absence.py; echo "exit: $?"
# Lint scan confirms all six migrated saga gate sites are compliant
python3 plugins/saga/scripts/lint_gate_absence_contract.py --scan plugins/saga/skills
# Existing external-engine gate is unaffected
uv run pytest tests/test_engine_dispatch.py -k satisfy_gate
# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```
Expected: all green; the missing-absence fixture exits `1` naming the offending site, the
with-absence fixture exits `0`, and the six-site scan reports full compliance.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: docs/plans/2026-07-03-plugin-fleet-grounding-brief.md
- Source type: grounding-brief
- Source title: Plugin Fleet Ideation 2026-07-03 — Grounding Brief

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/371
- Number: 371
- Created at: 2026-07-04T07:52:33.857278+00:00

