---
title: Reversibility/Idempotency Certificate — One Authority for Reversibility-Gated Autonomy
type: feat
status: active
date: 2026-06-29
origin: docs/brainstorms/2026-06-27-reversibility-idempotency-certificate-requirements.md
---

# Reversibility/Idempotency Certificate — One Authority for Reversibility-Gated Autonomy

One evaluable authority that declares an operation's reversibility facts and answers a single
`authorize_write` verdict (AUTHORIZED / GATE, **default GATE**) — then ships its first autonomous
consumer: `/outcome` board-sync, saga's first autonomous writes across the saga↔mission-control
boundary. Issue [#279](https://github.com/infiquetra/infiquetra-claude-plugins/issues/279) (capability,
VECU survivor S-2; board objective `improve-claude-plugins`). Built by delegating each feature unit to
**agy Gemini Pro 3.1 High** — n=4 of the external-agent-delegation experiment, the second Pro run.

## Problem Frame (carried from the brainstorm — the WHAT is settled)

Saga's reversibility-based autonomy is decided in **scattered hardcoded sites**, with no shared
definition of what makes an action safe without a human:

- `operator-keystroke-only` — the parent issue never auto-closes (`outcome_projection.py:81`, verified).
- `had_side_effect → HALT` — a side-effected leaf never re-runs on a lesser backend
  (`outcome_dispatcher.py:271`, verified) — a *no-duplicate-side-effect* rule.
- GitHub branch-protection — the existing PR squash-merge write side (`outcome_github.py:175-192`,
  verified) is an autoland-style certified envelope already in the engine.

There is no single answer to "what reversible action may saga take autonomously?" The high-value
behavior this unlocks — **saga moving its own board during an `/outcome` campaign** — is unbuilt:
`outcome.py:1062-1065` documents the sub-issue close adapter as "deferred to a later operator-initiated
mission-control consumer," and `outcome_projection.py:17-18` confirms "the actual mission-control GitHub
write is a separate, operator-initiated consumer … no auto-push here." Observed three times this
campaign as manual board recovery on #275 / #277 / #278.

The WHAT (requirements R1–R21, flows F1–F4, acceptance AE1–AE9, decisions KD1–KD5) is fixed in the
brainstorm and was doc-reviewed READY
(`docs/reviews/2026-06-27-reversibility-idempotency-certificate-readiness.md`). This plan decides only
the **HOW** and resolves the brainstorm's five deferred-to-`/plan` questions.

## Grounding deltas — where the code reality refines the brainstorm

Every cited anchor was read and confirmed. Two HOW-shaping facts the brainstorm under-specified:

1. **v1 spans two plugins.** The mission-control verbs the certificate drives mostly **do not exist**.
   `sdlc_manager.py` exposes only `flow set-field` (`:2172`, Status/Objective) and `board add` (`:993`).
   There is **no** issue close/reopen, **no** issue comment, and **no** standalone issue-label
   add/remove verb (the `--add-label` at `:4469` is embedded in the `create-prepared` flow; the
   `labels_sync_fields`/`_sync_label_fields_for_item` machinery at `:1328-1373` syncs labels *into
   project fields*, it does not add/remove issue labels as a reversible op). The brainstorm anticipated
   this — its "Files expected to change" lists `sdlc_manager.py` for "close, comment" — so building those
   verbs is genuine v1 work, and **mission-control gets a release bump (2.3.1 → 2.4.0)** alongside saga.

2. **Reuse the existing ledger's write-once *mechanism* — in a SEPARATE board-sync ledger, not the
   completion ledger.** The outcome store has a durable, replayable, write-once-link-loser ledger with
   sticky success (`write_completion_event` → `"written"` / `"skipped"`, proven by
   `test_outcome_replay.py:116-150`; DECISIONS `#outcome-store-durability-stance`). **Doc-review caught
   that the completion ledger must NOT be reused directly:** `write_completion_event` validates `state`
   against terminal `COMPLETION_STATES` (`outcome_store.py:264`) and its events feed
   `completed_subplots`/`derive_states` (`outcome_store.py:350-366`, `outcome.py:342-358`), so a board-op
   key like `set-field-status:#279:In-Progress` would crash `validate` (non-terminal state) or pollute the
   leaf frontier. The board-sync idempotency ledger therefore reuses only the **write-once `os.link`
   mechanism + the `"written"`/`"skipped"` contract** in its own namespaced dir (KTD4), never the
   completion `events_dir`.

## Requirements (traceability — full text in the brainstorm)

| ID | Requirement (abbrev) | Unit | Acceptance |
|----|----------------------|------|------------|
| R1–R4 | One authority (U4 invokes it, never re-derives); declared enumerated facts; default GATE; facts from durable state only | U1, U4 | AE5 |
| R5 | Reversible tier (registered inverse): set-field Status, issue-label add/remove, sub-issue close | U1 | AE1, AE2 |
| R6 | Additive tier (append-only, abort-cost bounded by coalescing): progress comment | U1, U4 | AE4 |
| R7 | `ALWAYS_OPERATOR` override (parent-close) gates even when reversible | U1, U2 | AE3 |
| R8 | Unenumerated → GATE (the allowlist is the whole envelope) | U1 | AE5 |
| R9 | Idempotency a universal precondition (every write carries a key) | U1, U4 | AE8 |
| R10 | `had_side_effect → HALT` preserved as `side_effected` fact, identical decision | U2 | AE6 |
| R11 | Full degrade order unchanged; certificate supplies only `side_effected` | U2 | AE6 |
| R12 | `operator-keystroke-only` → `ALWAYS_OPERATOR` entry; parent-close stays gated everywhere | U2 | AE3 |
| R13 | Certificate does not subsume presence/guarantee/elevated_risk gates | U2 | AE6 |
| R14 | Only new behavior is autonomous enumerated board writes; equivalence is a shipping requirement | U2, U4 | AE6, AE9 |
| R15 | v1 builds the saga→mission-control adapters incl. the unbuilt close/reopen | U3, U4 | AE2 |
| R16 | `/outcome` performs enumerated reversible/additive writes when AUTHORIZED | U4 | AE1, AE2, AE4 |
| R17 | A GATE'd op surfaces to the operator; no silent write/skip | U4 | AE5 |
| R18 | Failed AUTHORIZED write → bounded idempotent retry → surface on exhaustion | U4 | AE8 |
| R19 | Every autonomous write recorded as a saga tick | U4 | AE1 |
| R20 | PR-merge and deploy never autonomous (no allowlist entry) | U1 | AE7 |
| R21 | Backend recommender unmodified (a future fact-consumer, not v1) | U2 | AE9 |

## Key Technical Decisions

**KTD1 — The certificate is a pure-data authority, not an executor (resolves brainstorm Q1).** It lives
in a new module `plugins/saga/scripts/reversibility_certificate.py`, following the `outcome_*` house
pattern (pure functions over explicit values, lazy imports, no I/O at import — `outcome_projection.py:20`).
It exposes: the enumerated allowlist registry; `facts(op_kind)`; `authorize_write(op_kind)` →
AUTHORIZED / GATE (default GATE); the `side_effected` instance-fact accessor; and `idempotency_key(...)`.
It performs **no** GitHub I/O — declaring and executing are separated, which keeps it serializable and
golden-testable. Rationale: this is the same governance shape saga already uses on itself
(`#self-modifying-engine-needs-a-gate` — tiered by *edit-kind* not edit-target), pointed outward at
external writes; not a novel safety model.

**KTD2 — Ops are identified by an enumerated `OpKind`; the registry is a closed allowlist (resolves
Q-allowlist).** `OpKind` is a small frozen set of canonical names that mirror mission-control verbs:
`set-field-status`, `issue-label-add`, `issue-label-remove`, `sub-issue-close`, `issue-progress-comment`,
`parent-issue-close`. The registry maps each enumerated `OpKind` → `{tier, inverse, idempotency-key
recipe}`. Anything not in the registry (merge, deploy, repo-label-definition delete, any repo mutation)
returns GATE by default-deny (R3/R8/R20). There is no "probably fine" path and no solver (KD2).

**KTD3 — Inverses are declared *declaratively*, not as callables (resolves brainstorm Q2).** Each
reversible `OpKind` declares its inverse as the inverse `OpKind` plus how to derive its args (e.g.
`set-field-status` ⇒ inverse `set-field-status` to the prior value; `sub-issue-close` ⇒ inverse
`sub-issue-reopen`; `issue-label-add` ⇒ inverse `issue-label-remove`). The certificate only *declares*
the registered inverse exists (R5); *executing* a rollback is the consumer's job. A declarative inverse
keeps the authority pure and lets a golden test assert "every reversible op has a registered inverse"
without running anything.

**KTD4 — Idempotency key = `{op_kind}:{issue_number}:{target_state}`, ridden on the existing outcome
ledger (resolves brainstorm Q3).** Deterministic from durable saga state (R4): e.g.
`set-field-status:#279:In-Progress`, `issue-label-add:#279:blocked`, `sub-issue-close:#279:`. The
additive comment uses a **coalescing** key `issue-progress-comment:#279:<leaf-transition-id>` so one
comment is posted per meaningful leaf transition, not per tick (R6/AE4). The consumer records executed
keys in a **separate, namespaced board-sync ledger** that reuses only the write-once `os.link` mechanism
+ the `"written"`/`"skipped"` return contract — it must **not** call `write_completion_event` or write
into the completion `events_dir` (that ledger requires terminal `COMPLETION_STATES` and feeds
`derive_states`; a board-op key would crash `validate` or pollute the leaf frontier — doc-review P2). A
crash/duplicate-trigger retry is then a no-op (R9/AE8). This is **not** the `promote_scan.py:47`
`repo:hash` scanner key (scanner-specific, not reusable, confirmed).

**KTD5 — Subsumption equivalence is proven by mirroring the existing enumerated degrade tests (resolves
brainstorm Q4).** `degrade_decision` (`outcome_dispatcher.py:242-290`) is a pure
5-input → 3-tuple function tested today by **7 enumerated case functions** in `tests/test_outcome_backends.py`
(`test_available_backend_dispatches` … `test_degrade_skips_an_unavailable_intermediate_rung`, lines
75-145; the file has 17 test functions total). The equivalence proof routes only the `had_side_effect`
branch through the certificate's `side_effected` fact and asserts each of those cases returns the
**identical** `(action, backend, reason)`. The order, and the `attending` / `guarantee_bearing` /
no-lower-rung branches, never move (R11/R13/AE6). The test mirrors the existing per-case style (not a new
parametrize framework) so the diff is reviewable. **Doc-review hardening:** the proof must also pin the
*pass-through* — assert the certificate's `side_effected` fact equals the value wired at the real call
site today (`had_side_effect=node.destructive`, `outcome.py:623`), not a re-derivation that could
diverge; otherwise a `True→HALT` could silently become `False→degrade` (a duplicate side effect — the
exact R14 corruption). The 7 golden tuples **plus** this pass-through identity are the whole proof; an
exhaustive cartesian sweep is unnecessary (the function is an unchanged pure boolean if-chain).

**KTD6 — Leaf-state → board-transition mapping is grounded in `derive_states` (resolves brainstorm
Q5).** The consumer maps the `/outcome` live states (from `outcome_engine.derive_states`, the same
source `outcome_projection.project` uses — `outcome_projection.py:47`) to board writes: a leaf entering
`ready`/in-progress → `set-field-status` "In Progress"; a leaf reaching tester-ACCEPT after
nonprod-deploy → `sub-issue-close`; a leaf advancing a phase → one coalesced `issue-progress-comment`.
The mapping reads derived state only — never an operator-set field — so it inherits the projection's
derived-on-read invariant. **The firing point is the `advance` reconcile tick** (`AdvanceResult`,
`outcome.py:398-544`), where `derive_states` values change (it emits
`ready`/`dispatched`/`done`/`blocked`/`failed`/`rejected`/`stalled`; "In Progress" is the board
write-*target* label, not a source state). **Negative terminals** (`failed`/`rejected`/`stalled`) have
**no** board-revert in v1 — an explicit deferred non-goal (Scope Boundaries), not an omission.

**KTD7 — Execution method: each feature unit (U1–U5) is delegated to agy Gemini Pro 3.1 High** (the
contract is its own section below). **U6 (release surfaces) is Claude-written.** Saga orchestration
backend = **inline** (Claude drives, delegates each unit, verifies) — matches #275 / #277 / #278.

**KTD8 — No dead-wiring: U1 is inert until U4 (honor `#dead-wiring-needs-producer-and-consumer`).** A new
authority/field is live only when a real producer sets it *and* a real consumer changes behavior, tested
end-to-end through the real entrypoint (not fixtures that fabricate shape). U1 (the authority) is
**dead-wired by construction** until U4 (the `/outcome` consumer) drives it. U4's tests therefore exercise
the real board-sync entrypoint; U1's own tests are unit-level and explicitly labelled as proving the
authority in isolation, not as proving it is wired.

## High-Level Technical Design

```
                         reversibility_certificate.py  (U1 — pure authority)
                         ┌───────────────────────────────────────────────┐
                         │ ALLOWLIST: OpKind -> {tier, inverse, key-recipe}│
                         │ facts(op) · authorize_write(op) -> AUTH | GATE  │
                         │ side_effected(...) · idempotency_key(...)       │
                         └───────────────────────────────────────────────┘
                            ▲ side_effected fact         ▲ verdict + key
                            │ (U2)                        │ (U4)
   outcome_dispatcher.py    │                             │     outcome_board_sync.py  (U4 — consumer)
   degrade_decision  ───────┘                             └──── derive_states -> transition map
   (had_side_effect branch routed; order UNCHANGED)             authorize_write -> AUTH? drive verb
                                                                bounded-retry(key) -> tick | surface
   outcome_projection.py                                                   │ drives
   operator-keystroke-only -> ALWAYS_OPERATOR (U2)                         ▼
                                                          sdlc_manager.py  (U3 — mission-control verbs)
                                                          issue close/reopen · comment · label add/remove
                                                          (idempotent: ApiAlreadyExistsError + GraphQL no-op)
```

Files (read-broad / write-narrow blast radius):

- **NEW** `plugins/saga/scripts/reversibility_certificate.py` (U1)
- **EDIT** `plugins/saga/scripts/outcome_dispatcher.py` (U2 — route `side_effected`; `:271`)
- **EDIT** `plugins/saga/scripts/outcome_projection.py` (U2 — `ALWAYS_OPERATOR`; `:81`)
- **EDIT** `plugins/mission-control/scripts/sdlc_manager.py` (U3 — new issue-write verbs)
- **NEW** `plugins/saga/scripts/outcome_board_sync.py` (U4 — consumer + adapters + retry)
- **EDIT** `plugins/saga/scripts/outcome.py` (U4 — minimal CLI wiring of the consumer; the deferred
  note at `:1062-1065`)
- **EDIT** `plugins/saga/skills/outcome/SKILL.md` (U5 — prose)
- Tests: **NEW** `tests/test_reversibility_certificate.py` (U1); **EDIT** `tests/test_outcome_backends.py`
  (U2 equivalence + AE9); **EDIT** `tests/test_mission_control.py` (U3 verbs); **NEW**
  `tests/test_outcome_board_sync.py` (U4); **EDIT** `tests/test_saga_plugin.py` (U5 doc-contract + U6 pin)
- Release (U6): `plugins/saga/.claude-plugin/plugin.json`,
  `plugins/mission-control/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` (both entries),
  `plugins/saga/CHANGELOG.md`, `plugins/mission-control/CHANGELOG.md`, version-pin tests.

## Implementation Units

Dependency order: **U1 → {U2, U3} → U4 → U5 → U6.** (U2 and U3 are independent of each other — different
plugins — but agy runs serially under the settings.json model-lock, so they execute in listed order.)

### U1. Certificate authority — facts, verdict, allowlist, idempotency key

The pure-data authority (KTD1–KTD4). New `reversibility_certificate.py`: the enumerated `OpKind`
allowlist registry (reversible / additive / `ALWAYS_OPERATOR`), `facts(op_kind)`,
`authorize_write(op_kind)` (default GATE), declared inverses (KTD3), and `idempotency_key(...)`. No
GitHub I/O, no consumers yet (dead-wired until U4 — KTD8).

**Write-set:** `plugins/saga/scripts/reversibility_certificate.py`, `tests/test_reversibility_certificate.py`.

**depends_on:** none.

**Test scenarios** (`tests/test_reversibility_certificate.py`):
- Enumerated reversible op (`set-field-status`) → `authorize_write` AUTHORIZED; its declared inverse is
  `set-field-status`-to-prior. **(R5)**
- Enumerated additive op (`issue-progress-comment`) → AUTHORIZED; has **no** inverse, carries an
  `abort_cost` bound. **(R6)**
- `parent-issue-close` (`ALWAYS_OPERATOR`) → GATE even though it is closeable. **(R7, AE3)**
- An unenumerated op (`repo-label-definition-delete`, arbitrary string) → GATE (default-deny). **(R3, R8, AE5)**
- `merge` / `deploy` are absent from the registry → GATE. **(R20, AE7)**
- `idempotency_key("set-field-status", 279, "In-Progress")` is deterministic and distinct from the same
  op to a different target / issue. **(R9)**
- Every reversible `OpKind` has a registered inverse (iterate the registry). **(R5)**

### U2. Subsumption + golden equivalence

Route the `had_side_effect` branch (`outcome_dispatcher.py:271`) through the certificate's
`side_effected` fact, and express `operator-keystroke-only` (`outcome_projection.py:81`) as the
`ALWAYS_OPERATOR` entry — both behavior-identical (R10–R14). The certificate supplies *only* the
`side_effected` fact into the **unchanged** degrade order.

**Write-set:** `plugins/saga/scripts/outcome_dispatcher.py`, `plugins/saga/scripts/outcome_projection.py`,
`tests/test_outcome_backends.py`.

**depends_on:** U1.

**Test scenarios** (`tests/test_outcome_backends.py` — mirror the 7 existing degrade case functions):
- For each of the 7 enumerated `degrade_decision` cases (available / attending / guarantee-bearing /
  side-effected / not-on-ladder / skip-rung), the certificate-routed path returns the **identical**
  `(action, backend, reason)` tuple. **(R10, R11, AE6)**
- **Pass-through identity (doc-review fix):** the certificate's `side_effected` fact equals
  `node.destructive` at the real call site (`outcome.py:623`) — mutate the wiring to return the negation
  and a `True→HALT` case must flip to `degrade`, proving the assertion is load-bearing. **(R10, R14)**
- `parent-close` remains GATE in every case it is gated today (drive `outcome_projection.project` and
  assert `parent_close` still resolves to the operator-only outcome via the `ALWAYS_OPERATOR` entry).
  **(R12, AE3)**
- `recommend_outcome_backend` output is byte-identical before/after (the certificate is not consulted by
  the recommender). **(R21, AE9)**

### U3. mission-control issue-write verbs

Add the missing `sdlc_manager.py` verbs the certificate's ops require (R15): `issue close` / `issue
reopen`, `issue comment`, and standalone `issue-label add` / `issue-label remove`. Each is **idempotent**
reusing the established pattern (`ApiAlreadyExistsError` from `_classify_gh_error` + GraphQL no-op
semantics; see `flow_link_sub_issue:2249-2281`, `flow_set_field:2172-2225`) and, where multi-step,
**resumable** per `#create-prepared-graphql-resolver-stance` (record-before / finalize-after). No
certificate import — these are plain mission-control verbs the U4 adapter calls.

**Write-set:** `plugins/mission-control/scripts/sdlc_manager.py`, `tests/test_mission_control.py`,
`tests/conftest.py` (the autouse no-live-`gh` guard fixture — see Execution Method).

**depends_on:** none (independent of U1/U2). **Highest blast radius — see Risk Analysis; recommend an
adversarial-verify pass at `/work`.**

**Test scenarios** (`tests/test_mission_control.py` — fake gh runner, the `mock_github_cli` /
`SimpleNamespace(returncode,stdout,stderr)` injection pattern):
- `issue close` issues the correct `gh`/GraphQL call; a re-close of an already-closed issue returns
  success (idempotent), not error.
- `issue reopen` is the inverse and round-trips (close → reopen → state restored).
- `issue comment` posts; the verb is callable with a stable body.
- `issue-label add` then `remove` round-trips; re-adding an existing label is a no-op success.
- A transient (non-422) gh error surfaces as a failure (not swallowed) so the U4 retry path can act.

### U4. `/outcome` board-sync consumer (makes U1 live)

The first autonomous consumer (R16–R19). New `outcome_board_sync.py`: the leaf-state→board-transition
map (KTD6), the `authorize_write` gate, the adapter that drives the U3 verbs, bounded idempotent retry
(KTD4 ledger) with fail-loud surfacing on exhaustion, and a saga tick per autonomous write. **Wiring
entrypoint (doc-review fix):** board-sync fires from the `advance` reconcile tick — where leaf states
actually change (`AdvanceResult`, `outcome.py:398-544`), gated to the autonomous path
(`advance --autonomous`); the `prune`-command deferral note (`outcome.py:1062-1065`) is replaced only for
the `sub-issue-close` op, **not** treated as the sole wiring site. This unit makes U1 a live
producer+consumer (KTD8) — its tests drive the real `advance` entrypoint.

**Write-set:** `plugins/saga/scripts/outcome_board_sync.py`, `plugins/saga/scripts/outcome.py`,
`tests/test_outcome_board_sync.py`.

**depends_on:** U1, U3. **High stakes (the autonomous writes) — recommend an adversarial-verify pass at
`/work`.**

**Test scenarios** (`tests/test_outcome_board_sync.py` — fake gh runner + real store; drive the real
board-sync entrypoint, not fabricated shape):
- AE1: a leaf enters review → `set-field-status` "In Progress" is AUTHORIZED → performed → a saga tick
  records what/when/why-authorized. **(R5, R16, R19)**
- AE2: a leaf reaches tester-ACCEPT after nonprod-deploy → `sub-issue-close` AUTHORIZED → performed via
  the v1-built adapter (reopen is its inverse). **(R5, R15, R16)**
- AE4: a leaf advances a phase → one coalesced progress comment; rapid successive ticks do **not** each
  spawn a comment (same coalescing key). **(R6, R16)**
- AE5: an unenumerated/`ALWAYS_OPERATOR` op → GATE → surfaced to the operator, no write, no silent skip.
  **(R17)**
- AE8: an AUTHORIZED `set-field` write fails on the boundary → bounded idempotent retry (no duplicate
  under its key) → surfaced to the operator on exhaustion; the campaign is not wedged. **(R9, R18)**
- **R1 single-authority (doc-review fix):** spy/mock `reversibility_certificate.authorize_write` and
  assert the board-sync entrypoint *invokes* it for the verdict — a consumer that re-derives its own
  verdict goes red. This is the only falsifiable test of "no consumer re-derives". **(R1)**
- **Ledger isolation (doc-review fix):** board-op idempotency keys never appear in `completed_subplots` /
  `derive_states` (the board-sync ledger is namespaced separately from the completion `events_dir` —
  KTD4); a board-op key fed to the completion ledger would fail fast. **(R9)**

### U5. `/outcome` SKILL.md prose + doc-contract test

Document the new operator-facing behavior in `outcome/SKILL.md`: which ops are autonomous (the enumerated
allowlist), that everything else GATEs to the operator, the never-autonomous guarantees (merge / deploy /
parent-close), the fail-loud-on-exhaustion path, and that every autonomous write is recorded as a tick.
**This is the prose-heavy unit — exactly where agy's n=2 F6 silent no-op appeared; archive the draft and
budget Claude hand-finish.**

**Write-set:** `plugins/saga/skills/outcome/SKILL.md`, `tests/test_saga_plugin.py`.

**depends_on:** U4.

**Test scenarios** (`tests/test_saga_plugin.py` — mirror the existing doc-contract test style,
`_read(PLUGIN_ROOT / "skills" / "outcome" / "SKILL.md")`):
- The SKILL documents that enumerated reversible/additive board ops are performed autonomously when
  authorized (assert multiple distinguishing phrases — semantic content, not one keyword).
- The SKILL documents that merge, deploy, and parent-close are **never** autonomous (assert each).
- The SKILL documents the GATE-surfaces-to-operator and fail-loud-on-exhaustion behavior.
- **Mutation-proof:** breaking the intended prose makes the assertion go red (no vacuous absence
  assertions — the n=3 #278/U5 lesson).

### U6. Release surfaces (mechanical — Claude-written, not delegated)

Both plugins bump (per the engineering-journal practice, mechanical units are not delegated):

**Write-set:** `plugins/saga/.claude-plugin/plugin.json` (0.41.0 → **0.42.0**),
`plugins/mission-control/.claude-plugin/plugin.json` (2.3.1 → **2.4.0**),
`.claude-plugin/marketplace.json` (both entries), `plugins/saga/CHANGELOG.md`,
`plugins/mission-control/CHANGELOG.md`, version-pin tests in `tests/test_saga_plugin.py` and
`tests/test_mission_control.py`.

**depends_on:** U5.

**Test expectation:** version-pin asserts in both plugin test files match the new versions
(`assert plugin_json["version"] == "0.42.0"` / `"2.4.0"`); marketplace.json validates as JSON
(`python3 -m json.tool`); the two plugin validators pass.

## Execution Method (agy Pro delegation contract — KTD7)

Per `docs/external-agent-delegation/` and memory `[[reference-agy-delegated-coder]]` /
`[[project-external-agent-delegation]]`. **This is n=4 and the second Pro run** (n=1 #275 Flash, n=2 #277
Flash, n=3 #278 Pro).

- **Front door:** `/agy:delegate --model pro <task>` (canonical `Gemini 3.1 Pro (High)`). Never a
  hand-rolled `agy` shell call (operator-banned).
- **NAMED spawn is the only working invocation** (operator-confirmed). Spawn `agy:runner` with
  `name: agy-u<N>` so it is a persistent teammate that survives the main loop's ~2-min Bash cap. Its
  **first action fails** (`Teammates cannot spawn other teammates`) then **recovers** — expected; do not
  strip the name over it. The nameless variant dies; a long Bash `timeout` is **not** a substitute.
- **Never `--background`** — it detaches agy into a 0-output context (the n=2/U1 21-min hang).
  Foreground only.
- **Claude is the sole committer/pusher.** agy is told "Do NOT run any git command." Commit each unit the
  moment it passes its gate (the n=2 orphan-late-write hazard).
- **Tight in-prompt allow-set** per unit (the unit's write-set above) + a hard scope guard ("if you need
  another file, STOP and report `PLAN_GAP` — never silently edit elsewhere"). Read broad, write narrow.
- **Post-hoc verification before integrating** any unit: `git status` ⊆ the unit's allow-set; the **full
  CI-parity gate** (`uv run pytest && uv run python -m ruff format --check . && uv run ruff check . &&
  uv run python -m mypy plugins/ scripts/ tests/ --ignore-missing-imports`) — note the mypy scope is
  `plugins/ scripts/ tests/`, the exact gap that red-CI'd #278; read the diff for test-gaming **AND
  mutation-proof any tests agy wrote**; confirm no rogue commit/push (`git log` + `git log origin/<branch>`).
- **Track-3 provenance:** archive each agy draft (`git stash` or a copy) **before** fixing it, so the
  review-fix delta is measured, not reconstructed. Log per-unit churn to
  `docs/external-agent-delegation/README.md` (Review-fix cycle log) — and this run writes the **owed n=3
  #278 matrix + review-fix-log rows** (doc-review confirmed the n=2 #277 rows already exist, README
  `:65` / `:80-84` — do not duplicate them), adds the **n=4 #279** rows, and refreshes the stale
  "n=2 done" line + unbuilt-list in `next-run-handoff.md`.
- **Hard floor for the GitHub-write units (doc-review fix):** before U3, add an **autouse** `conftest`
  fixture (scoped to the new test modules) that fails any **unmocked** `gh`/`subprocess` call (and unsets
  `GH_TOKEN`) so the build provably **cannot** mutate the live operations board — the existing
  `mock_subprocess_run` is opt-in, not autouse (`conftest.py:66`). This is the concrete tripwire that
  makes the escalate-off-agy trigger ("a real-`gh` call in a test") enforceable rather than convention.
- **U3 and U4 are the high-stakes units** (mission-control GitHub-mutating verbs; the autonomous-write
  consumer). The build itself touches no live GitHub (tests inject fake gh runners; Claude is sole
  committer; the autonomous writes only fire when a future `/outcome` campaign runs the consumer). Still:
  if Pro's draft shows any agency leak on these units (writes outside allow-set, a real-gh call in a
  test), **escalate that unit to Claude-written or a throwaway git worktree per DECISIONS
  `#agy-delegated-build-no-jail` revisit trigger** — do not keep delegating it un-jailed. Recommend an
  adversarial-verify pass (ultracode judge-panel, refute-N) on U2 (equivalence) and U4 (autonomous
  writes) at `/work` given their stakes.

## Scope Boundaries

**In scope (v1):** the single facts authority + `authorize_write` verdict (R1–R4); the two-tier allowlist
+ `ALWAYS_OPERATOR` override + default-gate + universal idempotency (R5–R9); subsumption of the two
reversibility-based checks with proven equivalence, degrade order preserved in full (R10–R14); the first
autonomous consumer (`/outcome` board-sync over the saga↔mission-control boundary) including the
**net-new mission-control verbs** and the saga-side adapters and the failure-surfacing path (R15–R19);
both plugins' release surfaces.

**Out of scope / deferred (true non-goals, carried from the issue):**
- The backend recommender rewrite — `elevated_risk` (`lifecycle_state.py:180`) stays as-is; it is a
  *future* fact-consumer, not v1 (R21).
- The presence (`attending`) and guarantee (`guarantee_bearing`) gates in `degrade_decision` — separate
  autonomy-adjacent judgments, left unchanged (R13).
- PR-merge and deploy autonomy — permanently HITL, never allowlisted (R20); not a deferral.
- Any static reversibility solver — the envelope is enumerated by construction (KD2).
- Repo label-definition create/delete — only issue-field labels are in the reversible tier.
- Mid-flight interrupt / agent hot-swap and capability-scoped agent sandboxing (separate ideation items;
  enforcement home #287).
- **Negative-terminal board-revert** (doc-review): a leaf that regresses (`failed` / `rejected` /
  `stalled`) does **not** auto-revert its prior autonomous board write in v1. This is recoverable drift —
  the derived-on-read projection stays the source of truth — and a deliberate deferred non-goal,
  promotable later; it is not an omission.

## Risk Analysis & Mitigation

| Risk | Likelihood | Mitigation |
|---|---|---|
| **Dead-wiring** — U1 authority ships with no live consumer | Med | KTD8: U4 is the producer+consumer; U4 tests drive the real board-sync entrypoint, not fixtures; review gate fails the no-dead-wiring check if U1 lands without U4 |
| **Subsumption changes behavior** (R14 violation) — the highest-stakes correctness risk | Med | KTD5 golden-equivalence over the 7 existing `degrade_decision` cases; certificate supplies *only* `side_effected`; recommend adversarial-verify on U2 at `/work` |
| **U3 mission-control verbs mutate the real board incorrectly** (the `create-prepared` defect lives on this boundary) | Med | Idempotent (ApiAlreadyExistsError + GraphQL no-op) + resumable-sidecar (`#create-prepared-graphql-resolver-stance`); fake-gh-runner tests; recommend adversarial-verify on U3 |
| **U4 autonomous write fires when it shouldn't / duplicates** | Low-Med | Default-GATE authority (R3); idempotency key on the write-once ledger (R9); bounded-retry + fail-loud (R18); merge/deploy/parent-close never allowlisted (R20) |
| **U5 prose migration triggers agy F6 silent no-op** (the n=2 failure mode) | Med | Archive the draft; Claude hand-finish budget; mutation-proof the doc-contract test (no vacuous absence asserts — the n=3 lesson) |
| **agy agency leak on the GitHub-write units (U3/U4)** | Med | Build touches no live GitHub (fake runners, sole-committer, immediate per-unit commit); escalate U3/U4 to Claude-written / worktree if Pro writes outside allow-set |
| **CI mypy scope gap** (`plugins/` vs `plugins/ scripts/ tests/`) recurring from #278 | Low | The Execution Method pins the full CI-parity gate incl. `mypy plugins/ scripts/ tests/` per unit |
| **Two-plugin release drift** (saga bumped, mission-control forgotten, or marketplace out of sync) | Low | U6 bumps both plugin.jsons + both marketplace entries + both CHANGELOGs + both version-pin tests; `json.tool` validate marketplace |

## Alternatives Considered

- **Saga-side `gh` adapters for the missing verbs (bypass mission-control)** — rejected: it would put
  issue close/comment/label mutations on the saga side, violating the layering (board/portfolio ops are
  mission-control's domain; saga's existing `outcome_github.py` gh calls are PR/work-lifecycle, saga's
  own domain). The brainstorm is explicit: "the real board ops are mission-control verbs, not
  abstractions." Building the verbs in mission-control (U3) keeps the boundary clean.
- **Narrow v1 to set-field-only (defer close/comment until the verbs exist)** — rejected: it would fail
  AE2 (sub-issue close) and AE4 (coalesced comment), which the brainstorm names as v1 deliverables, and
  the doc-review passed on that scope. Building the verbs is bounded, idempotent, and well-precedented.
- **Inverse as a live callable** — rejected (KTD3): a callable makes the authority non-serializable and
  forces execution into the declaration layer; a declared inverse is golden-testable and keeps the
  certificate a pure allowlist (KD2).
- **A new idempotency cache** — rejected (KTD4): the outcome store's write-once-link-loser ledger already
  gives `"written"`/`"skipped"` semantics with sticky success; a parallel cache would duplicate and could
  diverge.

## Verification (CI parity)

```bash
uv run pytest tests/test_reversibility_certificate.py -v   # U1 authority + verdict + idempotency key
uv run pytest tests/test_outcome_backends.py -v            # U2 subsumption equivalence + recommender-unchanged
uv run pytest tests/test_mission_control.py -v             # U3 new issue-write verbs (fake gh)
uv run pytest tests/test_outcome_board_sync.py -v          # U4 autonomous board-sync + retry/surface
uv run pytest tests/test_saga_plugin.py -v                 # U5 doc-contract + U6 saga version pin
# FULL CI-parity gate (the mypy scope is the #278 red-CI gap — pin it):
uv run pytest && uv run python -m ruff format --check . && uv run ruff check . && \
  uv run python -m mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all green; the certificate is the one authority for reversibility-gated autonomous writes,
subsumption is proven-equivalent on the degrade path, and `/outcome` autonomously syncs the board inside
the enumerated envelope with a fail-loud failure path. Merging arms the capability for future `/outcome`
campaigns; it does not itself perform any board write.

## Doc-Review (2026-06-29) — verdict READY, blocked=false

Reviewed at working-tree revision (commit `1cdc294`) via a 4-lens adversarial workflow (agy-contract,
requirement/AE mapping, technical soundness, adversarial/security-autonomy) + a refute-pass verifier.
**18 findings → 10 confirmed, 8 refuted. 0 P0, 0 P1.** Artifact:
`docs/reviews/2026-06-29-reversibility-certificate-readiness.md`.

The agy-contract lens found KTD7 **fully compliant** with the documented `/agy:delegate` findings — its
only hit was a P3 bookkeeping nit (the n=2 #277 README rows already exist). Technical soundness
**confirmed** the two-plugin scope, the KTD5 method, every cited anchor, and both version bumps. Safe
fixes applied in place (all evidence-backed):

- **P2** KTD4 — board-sync uses a **separate namespaced** idempotency ledger (write-once mechanism only),
  never the completion `events_dir` (which requires terminal states + feeds `derive_states`).
- **P2** KTD5 — added the `side_effected == node.destructive` **pass-through identity** test
  (`outcome.py:623`); the 7 golden tuples alone didn't exercise the substitution seam.
- **P2** R1 — added a U4 spy test asserting the consumer **invokes** `authorize_write` (no re-derivation).
- **P2** KTD7/U3 — added an **autouse no-live-`gh` conftest guard** so the build provably can't mutate the
  real board (the existing mock is opt-in).
- **P2** U4 — fixed the wiring entrypoint to the **`advance` reconcile tick** (not the `prune` note).
- **P3** KTD6 / Scope — declared **negative-terminal board-revert** an explicit deferred non-goal; fixed
  the Track-3 bookkeeping wording.

## Routing

Doc-review is **complete (READY)** — `/work` is unblocked. Next: `/work` (inline backend, agy-Pro
delegation of U1–U5, Claude-written U6, destination = **merge**).

## Execution reality (2026-06-29 — post-build correction)

**KTD7's agy-Pro delegation did NOT happen.** Built 2026-06-29 on `feat/279-reversibility-certificate`
(U1–U6 + a fix commit; saga 0.42.0 + mc 2.4.0; full suite green). Mid-build the operator flagged — and the
agent transcripts confirmed — that the named `agy:runner` spawns were **Claude clones** (Read/Write/Edit
tools + Claude output style, **zero `agy` invocations**), not the agy wrapper. **All units are therefore
Claude-authored**, the commit messages say so, and the "n=4 agy Pro run" experiment data is invalid (no agy
signal). The plan above is preserved as written; this note records what actually executed. The
operator-requested adversarial-verify on U2 (672-sweep, 0 diffs) and U4 (found + fixed two real P2 holes —
repo-blind idempotency key, ledger-fault wedge) still ran and added real value. See work-session
`docs/work-sessions/2026-06-29-reversibility-certificate.md`.
