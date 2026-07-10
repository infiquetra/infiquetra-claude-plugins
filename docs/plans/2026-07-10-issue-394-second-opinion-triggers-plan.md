---
title: "Issue #394: Second-Opinion Triggers Inside /work and Reviews"
type: feat
status: active
date: 2026-07-10
origin: docs/sdlc-issue-drafts/plugin-fleet/pf-work-review-second-opinion.md
deepened: 2026-07-10
---

# Issue #394: Second-Opinion Triggers Inside /work and Reviews

## Summary

Wire three operator-confirmed, advisory-only second-opinion paths into `/work`, `/code-review`, and
`/doc-review`: a deterministic repeated-test-failure offer, round-N review-finding adjudication, and
per-finding reviewer point-out. Reuse the shipped offer, resolver, dispatch, trust-boundary, and typed
reconciliation substrate; add only the trigger coordination and durable consumer records still missing.

---

## Problem Frame

Issue #394 was written before issues #451 and #393 shipped. Current source already offers external-engine
help at all three lifecycle stages (`plugins/saga/skills/work/SKILL.md:75-82`,
`plugins/saga/skills/code-review/SKILL.md:72-78`, and
`plugins/saga/skills/doc-review/SKILL.md:121-127`) and already has bounded typed dispatch and reconciliation.
The remaining gap is executable trigger-specific behavior: `/work` has no failure-history detector,
review findings have no durable external-opinion/adjudication fields, and direct dispatch cannot stamp an
`advisory-reviewer` role at creation.

`/code-review` and `/doc-review` are also not one shared finding pipeline. Code review owns the structured
schema in `plugins/saga/skills/code-review/references/findings-schema.md:14-30`; document review owns a
separate P0-P3 prose/artifact contract in `plugins/saga/skills/doc-review/SKILL.md:150-184`. The plan must
give both surfaces the same advisory semantics without forcing a schema refactor that the issue does not
require.

---

## Requirements

R1. A specifically identified `/code-review` or `/doc-review` finding can be sent through the existing
external-engine lane with `intent=second-opinion`, `role_kind=advisory-reviewer`, and the established
`opus/high` chaperone posture, only after operator confirmation. (`T1-F3-8`, `T1-F5-1`)

R2. A returned opinion and Claude's own `keep`, `downgrade`, or `dismiss` decision are durably attached to
the source finding. The record must preserve dispatch/reconciliation identity, rationale, and Claude's
final severity/status rather than leaving the decision only in the transcript. (`T1-F3-8`)

R3. `/work` detects a documented repeated-failure signal, emits exactly one one-line second-opinion offer
for an unchanged streak, and never invokes an engine unless the operator accepts. (`T1-F6-7`)

R4. When `/work` receives a flagged round-N review finding, it can obtain the same per-finding opinion and
record Claude's re-adjudication before choosing the next fix/churn action; decline, halt, timeout, or no
response must not block the continuation loop. (`T1-F3-8`)

R5. External opinion request state, payload presence, return timing, halt state, and engine-authored text
never enter a readiness or blocked-verdict formula. Only Claude-owned final finding severity/status may
affect the existing verdict calculation. (`T1-F5-1`)

R6. All three paths remain second-opinion, never offload. They create no new transport, executor kind,
resident teammate, git participant, outcome-DAG behavior, or gate authority, and they do not call
`satisfy_gate()` as a route to acceptance.

R7. Interactive and programmatic modes retain their current ownership boundaries: a human point-out is
confirmation, a Claude-originated suggestion prompts first, and programmatic/report-only review emits a
recommendation for its attended caller without prompting or auto-dispatching.

R8. Executable fixture tests cover the three issue paths and their failure modes, and the Saga manifest,
marketplace entry, changelog, version pin, user-facing skill contracts, and engineering decision record
ship together.

R9. A second-opinion context package contains only the selected finding, reviewed revision, and bounded
repo-grounded excerpts already needed to evaluate that finding. Sensitive findings obey the existing
egress-policy recommendation before resolution; no eligible local-only route means a visible unavailable
result and zero dispatch, never a network fallback.

---

## Requirement Traceability

Every source acceptance criterion has one implementation owner and executable evidence path.

| Source acceptance | Plan requirements | Implementation units | Acceptance evidence |
| --- | --- | --- | --- |
| `T1-F3-8` — flagged finding gets an opinion and Claude re-adjudication | R1, R2, R4, R5 | U1, U2, U3, U4 | `tests/test_review_second_opinion.py` covers dispatch, ready reconciliation, `keep|downgrade|dismiss`, and durable projection; the work fixture covers round-N consumption. |
| `T1-F6-7` — repeated failure surfaces one offer, never auto-dispatches | R3, R7 | U2 | `tests/test_work_second_opinion.py` covers threshold, target-specific reset, debounce, resume, decline, unattended mode, and runner-spy zero-call behavior. |
| `T1-F5-1` — reviewer points out one finding without gating verdict | R1, R5, R7 | U1, U3, U4 | Review fixtures compare identical Claude final state with and without opinion metadata and prove advisory-reviewer gate refusal. |
| Advisory-only chaperone constraints | R5, R6, R9 | U1, U2, U3, U4 | Dispatch, hostile-output, egress, and skill-contract tests prove no gate token, new transport, silent network fallback, or auto-dispatch. |
| Saga release-surface checklist | R8 | U5 | Manifest/marketplace/changelog tri-lock, plugin validation, marketplace validation, release diff guard, and full CI checks. |

---

## High-Level Technical Design

One Saga-local coordinator composes the existing primitives and owns only trigger state plus the durable
consumer projection:

```text
finding or failed-attempt history
              |
              v
second_opinion.py  -- detects/offers/binds; no new transport
       |                              |
       v                              v
engine_offer + resolver + dispatch    review/work-session record
       |
       v
typed AdvisoryEvidence + reconciliation
       |
       v
Claude keep/downgrade/dismiss -> existing verdict computation
```

The external payload remains bounded, opaque advisory data. `run_fact.v1` continues to store only the
structural reconciliation projection already defined by #393; the review artifact or programmatic envelope
is the durable consumer record for opinion text and Claude's decision.

---

## Key Technical Decisions

**KTD1 — add one trigger coordinator, not a second transport:** Add
`plugins/saga/scripts/second_opinion.py` as a typed coordination layer over `engine_recommend.py`,
`engine_resolver.py`, `engine_dispatch.py`, and `reconcile.py`. It exposes pure
prepare/detect/adjudicate/serialize functions; the Markdown stage retains `engine_offer` preference/prompt
policy and passes an already-confirmed request to the coordinator. The stage invokes the already-installed
wrapper selected by `resolution.invocation.via` (`codex:delegate`, `agy:delegate`, or the generic HTTP
bridge). Tests inject the existing `Runner` seam. No cross-plugin Python import, raw provider CLI,
provider-specific bridge, executor, residency, or Team Execution participant is added.

**KTD2 — trigger intent is second-opinion or decline, with an explicit tier record:** A remembered stage
preference of `none` may suppress the automatic stuck offer; a generic remembered `offload` choice is not a
valid trigger preference and cannot change the route. The offer records the established `opus/high`
chaperone recommendation and any explicit operator override; it never silently down-tiers. Human point-out
is acceptance, Claude-originated point-out prompts first, and per-offer decline does not silently write a
permanent stage preference.

**KTD3 — the stuck signal is a target-specific three-attempt streak:** A completed attempt means one applied
fix followed by its test run; a rerun without a new fix reuses the attempt ID and cannot advance the count.
Normalize `./`-prefixed repo-relative pytest node IDs by stripping the `::...` suffix and converting
separators to POSIX form; reject absolute paths, `..`, and unparseable targets. A pass resets all streaks;
a target's absence resets only that target, so incidental additional failures do not hide one persistent
test file. If several targets reach three together, the lexical first wins. The rendered template is exactly
one line: `Second opinion available: {target} failed after 3 fix attempts; dispatch an advisory second opinion?`

**KTD4 — repeated-failure state is a versioned work-session sidecar:** Persist
`saga.work-second-opinion.v1` as
`docs/work-sessions/YYYY-MM-DD-<topic>-second-opinion.json` beside
`docs/work-sessions/YYYY-MM-DD-<topic>.md`. It contains bounded attempts and offers, and the Markdown links
it. Top-level fields are `{schema, round, attempts, offers}`; an attempt carries
`{attempt_id, change_ref, result, failing_test_files}`; an offer carries
`{offer_id, target, streak_epoch_attempt_id, disposition, tier, engine, request_id, request_digest,
execution_id}` with
`disposition ∈ {offered,accepted,declined,unattended,unavailable}` and absent-tolerant post-acceptance
fields. The stable offer key is
`(round, target, streak_epoch_attempt_id)`, where the epoch is the first attempt after that target's last
reset; fourth and later failures retain the same key. Use atomic replace, cap history at 64 attempts and 256
targets per attempt, and fail visibly with zero dispatch on malformed or over-cap state.

**KTD5 — review surfaces keep native findings but share one exact optional projection:** Code review uses
its Stage-A `#N`; document review assigns `D<N>` after sorting by priority, source anchor, then title within
one reviewed revision. Both may carry `external_opinion.state` in
`{recommended,requested,available,unavailable,declined}`. The block's closed fields are `state`,
`intent=second-opinion`, `role_kind=advisory-reviewer`, `requested_by ∈ {human,claude}`, `reason`,
`chaperone_tier={model,effort}`, `engine_id`, `variant`, `egress_policy`, `execution_id`, `request_id`,
`request_digest`, `reconciliation_id`, `evidence_digest`, `findings`, `verified_by_claude`, and
`status_note`; fields that do not yet exist for the current state are omitted rather than filled with
fabricated values.
`claude_adjudication` is absent until Claude acts and then carries `adjudicator_id`, `decision` in
`{keep,downgrade,dismiss}`, `rationale`, `final_severity`, and
`final_status ∈ {active,dismissed}`. Programmatic review emits `state=recommended`
inside the selected finding before its existing terminal `Review complete` line; `/work` consumes that field
rather than parsing prose. Available content is the canonical ordered typed-finding list, not an optional
pointer, and retains #393's 256 KiB cumulative UTF-8 cap.

**KTD6 — #393 reconciliation status and review disposition are distinct:** Every returned engine finding
must be covered by a ready `ReconciliationResult` using `reconciled|dropped|overridden`. Claude's decision
about the original review finding is separately `keep|downgrade|dismiss`; there is no one-to-one enum map.
`keep` preserves active severity, `downgrade` requires an explicitly lower active severity, and `dismiss`
retains the finding with `final_status=dismissed`. Mark immutable evidence reviewed with
`dataclasses.replace(evidence, verified_by_claude=True)`, never mutation.

**KTD7 — verdict isolation is content-blind and v1 dispatch remains synchronous:**
`engine_dispatch.dispatch()` accepts a validated additive `role_kind`, defaults to `worker`, validates the
same closed resolver vocabulary in direct `AdvisoryEvidence` construction, and stamps it on every returned
evidence path. Trigger calls use `advisory-reviewer` with `gated=False`; Codex and agy wrapper invocations
use reviewer/read-only or reviewer/no-write posture rather than a worker/coder identity. An accepted wrapper
call may run until its existing timeout, but timeout/halt/unavailable proceeds without an opinion; v1 adds no
callback, polling, or late-result ingestion. Verdicts read only Claude-owned final severity/status and the
existing `pre_existing` rule. Gate-shaped top-level runner keys are rejected, while the same words inside
opinion prose remain escaped opaque data and cannot influence the formula.

**KTD8 — the single-finding context package is bounded and egress-aware:** Send only stable finding ID,
current severity/priority, why/evidence/suggested fix, reviewed revision, request reason, and bounded cited
source excerpts; never forward the system prompt, conversation, unrelated findings, or discovered credential
values. Render those fields as canonical JSON and measure the entire rendered UTF-8 payload before
resolution: at most 16 excerpts, 16 KiB per excerpt, and 128 KiB total. Its byte count is the conservative
token estimate supplied to the existing context-window halt. `reason` and `status_note` cap at 4 KiB and
1 KiB respectively; Claude adjudication rationale reuses #393's 4 KiB rationale cap. The stage sets
`sensitive=true` when the operator marks it, the finding or excerpt contains credentials/secrets, or it
contains private customer/tenant data; security-category alone is not a proxy when the excerpt has no
sensitive data. Surface selected engine/variant plus egress policy before confirmation. Sensitive input
first calls `engine_recommend.recommend()` with `capability=second-opinion`,
`policy=cheapest-viable`, `min_rating=MODERATE`, and `sensitive=true`, and may dispatch only to a
`local-only` eligible row; none currently exists, so that path returns unavailable rather than using a
network provider. A conservative deterministic classifier runs before resolution: explicit operator marking
always wins, and credential/secret signatures or private customer/tenant markers in any egressable finding,
reason, or excerpt force the same local-only path.

**KTD9 — pre-dispatch reservation plus artifact durability prevents duplicate calls:** Derive stable
request, execution, and reconciliation IDs from the canonical context and selected route. Before invoking a
wrapper, atomically claim `state=requested`, the IDs, and the request digest in the durable consumer record;
only the absence-to-requested owner may dispatch. A retry with the same digest sees the prior claim and never
calls the runner again: if an available result is not already durable, it atomically becomes visible
`unavailable` with an interrupted-dispatch note. The same ID with a different digest is a hard error.

After a ready result, append `reconcile` only when an identical fact is not already present, atomically write
the enriched review artifact or work-session sidecar, mark the matching claim `available`, then append
`apply` only when its matching reconcile is present and apply is absent. Conflicting hashes remain hard
errors. A crash before the raw opinion reaches that atomic artifact has no replayable result and becomes
unavailable; a crash after that write resumes only the missing `available` or `apply` transition without a
runner call. Programmatic `/code-review` returns a `recommended` in-memory envelope and cannot
claim/dispatch until `/work` persists the request. Raw opinion and rationale remain in the enriched
review/work artifact only; `run_fact.v1` stores identities, digests, statuses, and hashes but cannot replay a
lost wrapper response.

**KTD10 — execute through a root-owned Codex DAG, not a Claude-style agent team:** Saga records
`orchestration_mode=inline`, while the root Codex thread owns dependency ordering, Saga state, shared-file
integration, Git, verification, and completion decisions. Direct Codex child threads receive bounded U-ID
exploration, implementation, review, or validation tasks; they do not form a named team, update Saga, commit,
or satisfy acceptance gates. Read-heavy and independent checks may fan out, but the shared worktree has one
writer at a time unless the root deliberately creates isolated worktrees with disjoint ownership. The shape
recommender's `team-execution` result remains recorded as recommendation evidence, but the operator explicitly
selected this native Codex strategy and no `Team Structure` or Team Execution receipt is required.

---

## Implementation Units

### U1. Shared second-opinion trigger and record contract

Create the executable domain seam that binds one finding to existing advisory dispatch and typed
reconciliation without acquiring gate authority.

**Goal:** Add typed trigger/result records, a single-finding coordination API, additive dispatch-role
provenance, and serialization/validation for external opinion plus Claude adjudication.

**Requirements:** R1, R2, R5, R6, R7, R9.

**Dependencies:** None; issues #451 and #393 are merged current-source prerequisites.

**Files:** `plugins/saga/scripts/second_opinion.py` (new);
`plugins/saga/scripts/engine_dispatch.py`; `plugins/saga/references/engine-dispatch.md`;
`plugins/saga/references/engine-output-trust-boundary.md`;
`tests/test_review_second_opinion.py` (new); `tests/test_saga_engine_dispatch.py`;
`tests/test_engine_output_trust_boundary.py`.

**Approach:** Prepare a single-finding request, render KTD8's canonical bounded context, classify
sensitivity, and resolve the permitted second-opinion route with `role_kind=advisory-reviewer` and
`mode=dispatch`. The stage atomically persists KTD9's requested projection before passing the existing
wrapper runner to the coordinator; an existing identical claim refuses redispatch and becomes unavailable
when no durable result can be recovered. The coordinator validates the returned Runner contract and binds
successful typed findings to a ready #393 reconciliation. HTTP rows use the existing generic bridge runner;
Codex and agy use their guarded reviewer/read-only or reviewer/no-write delegate posture, never raw CLIs or
imports across installed plugin roots. An adapter maps established wrapper status vocabulary at this boundary;
successful typed findings must already equal the exact canonical ordered envelope so raw-output attestation
is not invalidated by a post-receipt rewrite.

Add `role_kind` to `dispatch()` with validation against the resolver vocabulary in both dispatch input and
`AdvisoryEvidence`, then propagate it through every return path; retain `worker` as the default so existing
callers are unchanged. Panel callers stamp `panel` through that same validated path. The coordinator emits
KTD5's exact optional projection and fixed state vocabulary. A halt, timeout, malformed response, empty typed
response, sensitivity halt, or missing output becomes visible unavailable advisory evidence rather than a
gate or silent Claude or network fallback. Add the new opaque advisory fields and call sites to #385's
trust-boundary table and AST guard. Reconciliation/artifact/availability/apply follow KTD9's idempotent
order.

**Patterns to follow:** `plugins/saga/scripts/engine_offer.py:163-207` for advisory stage policy;
`plugins/saga/scripts/engine_resolver.py:330-407` for advisory-reviewer resolution;
`plugins/saga/scripts/engine_dispatch.py:53-132,243-388` for bounded typed evidence; and
`plugins/saga/scripts/reconcile.py:323-520` for Claude-only reconciliation identity and coverage. Follow
`plugins/saga/scripts/engine_recommend.py:114-170` for sensitivity/egress filtering and
`plugins/saga/references/engine-output-trust-boundary.md` for opaque rendering.

**Test scenarios:** A seeded finding accepted for a second opinion resolves and dispatches once, produces
ordered typed `AdvisoryEvidence` stamped `advisory-reviewer`, reconciles every source ID, and serializes the
bounded record. A halted, timed-out, empty, or malformed runner produces no adjudication and leaves the
source finding unchanged. Invalid role kinds, mismatched finding IDs, duplicate source IDs, an unready
reconciliation, 17th excerpt, 16 KiB + 1 excerpt, 128 KiB + 1 canonical context, oversized returned
findings, over-cap reason/status-note/adjudication rationale, and runner-authored gatekeeper fields fail
visibly. Exact cap values pass. A sensitive request with no local-only candidate produces no resolver or
wrapper call. Gate-shaped words inside a typed finding remain inert opaque data. Existing callers that omit
`role_kind` still return byte-equivalent worker evidence. Calling `satisfy_gate()` with the resulting
advisory-reviewer evidence remains a hard refusal. A crash after the requested claim or reconciliation but
before the atomic raw-opinion artifact produces unavailable on retry with zero runner calls; a crash after
that artifact write resumes only the missing availability/apply transition.

**Verification:** Focused helper, dispatch, and reconciliation tests prove all engine calls use the shipped
resolver/runner path, all returned findings are accounted for, and the new record cannot become a gate.

### U2. `/work` repeated-failure and round-N finding triggers

Make stuck detection deterministic and debounced, then put the operator in control of both work-stage
trigger paths.

**Goal:** Record completed test attempts, detect the three-attempt common-target streak, surface one fixed
offer line, and route an accepted stuck or flagged-finding request through U1 before the next fix decision.

**Requirements:** R3, R4, R5, R6, R7, R9.

**Dependencies:** U1.

**Files:** `plugins/saga/scripts/second_opinion.py`;
`plugins/saga/skills/work/SKILL.md`;
`plugins/saga/skills/work/references/pr-continuation-loop.md`;
`tests/test_work_second_opinion.py` (new); `tests/test_saga_plugin.py`.

**Approach:** Add a pure detector over the versioned KTD4 state. `/work` assigns one attempt ID only after a
fix is applied, records the following test result, maintains target-specific streak epochs, and atomically
writes the sidecar before another fix. If the phase's work-session pair does not exist yet, initialize the
Markdown record and sidecar together; the Markdown links the sidecar and remains the narrative record. The
helper validates all fields and caps before evaluation; malformed or oversized state is a visible fail-closed
condition with no offer and no dispatch.

When one target first reaches three, `/work` records the stable offer key and prints KTD3's exact line.
Stored `none` suppresses this automatic offer; stored `offload` is not applicable. Acceptance atomically
claims KTD9's requested state in the sidecar before invoking U1; decline, no response, unattended mode, or
dispatch failure records a disposition and proceeds through current gates. A programmatic `/code-review` point-out
arrives as `external_opinion.state=recommended` on the selected finding, and `/work` owns attended
confirmation, durable enrichment, verdict recomputation, and the KTD9 apply transition.

**Patterns to follow:** `plugins/saga/skills/work/SKILL.md:124-142` for round-N entry;
`plugins/saga/skills/work/SKILL.md:334-385` for test-gate recording;
`plugins/saga/skills/work/SKILL.md:434-472` for direct review-envelope consumption; and
`plugins/saga/skills/work/references/pr-continuation-loop.md:41-81` for between-round state.

**Test scenarios:** Two matching failures do not trigger; the third emits exactly one line; fourth and later
matching failures in the same epoch do not duplicate it. A pass or a target's absence resets that target; a
new round creates a new epoch. Extra incidental failures do not reset a persistent target. Three-way
no-intersection histories, reruns with the same attempt ID, absolute/traversal/unparseable paths, empty state,
malformed state, more than 64 attempts, and more than 256 targets fail or no-op as specified with zero
dispatch. Atomic save/load followed by a fresh-process resume retains the debounce key.

A stored `none` suppresses the offer; stored `offload` cannot change the trigger intent. Decline, missing
answer, and unattended mode leave a runner spy untouched; explicit acceptance calls it once. A runner
halt/failure and unavailable opinion leave the existing gate verdict unchanged. An accepted flagged review
finding is re-adjudicated and durably written before `/work` selects its next fix action; crash/retry around
the write and ledger transitions is idempotent.

**Verification:** The executable transcript fixture proves threshold, fixed line, debounce, persistence,
and zero auto-dispatch; work-skill contract tests prove both trigger placements and advisory-only wording.

### U3. `/code-review` per-finding point-out and durable projection

Attach advisory evidence to one stable code-review finding while preserving the existing Stage-A/Stage-B
and programmatic-envelope contracts.

**Goal:** Add the point-out step after Stage-A stable numbering, persist the U1 projection on the finding,
and recompute blocked status only from Claude's final finding state.

**Requirements:** R1, R2, R4, R5, R6, R7, R9.

**Dependencies:** U1.

**Files:** `plugins/saga/skills/code-review/SKILL.md`;
`plugins/saga/skills/code-review/references/findings-schema.md`;
`tests/test_review_second_opinion.py`; `tests/test_saga_plugin.py`.

**Approach:** Add KTD5's optional blocks to the durable finding shape after Stage A has deduplicated,
sorted, and numbered findings. A human reviewer naming `#N` is confirmation; a Claude-originated point-out
asks first in interactive mode. Programmatic/report-only mode never prompts or dispatches: it adds
`external_opinion.state=recommended`, requester, and reason to that finding before `Review complete`, so
`/work` consumes a typed field instead of prose.

For accepted interactive requests, build KTD8's single-finding context and surface provider/egress/tier
before atomically persisting `state=requested` in the durable artifact. Only that claim owner invokes U1;
a resumed unresolved claim becomes visible unavailable rather than repeating a wrapper call. Claude verifies
any available response against the source, creates a ready reconciliation, records `keep|downgrade|dismiss`,
atomically persists the enriched artifact, then records apply. Stage B and verdict code use only
`final_status`, `final_severity`, and existing `pre_existing`; recommended, requested, unavailable, declined,
or omitted states are no-ops.

**Patterns to follow:** `plugins/saga/skills/code-review/SKILL.md:210-255` for Stage A/B ordering;
`plugins/saga/skills/code-review/SKILL.md:271-302` for output persistence; and
`plugins/saga/skills/code-review/references/findings-schema.md:100-125` for stable numbering and durable
artifact fields.

**Test scenarios:** Parameterized `keep`, valid lower-severity `downgrade`, and `dismiss` decisions persist
with rationale and `active|dismissed` final state. Missing opinion, halt, timeout, and decline leave the
original finding and verdict unchanged; v1 creates no late-result callback. Invalid state/decision values, a
downgrade without a lower severity, a finding-ID mismatch, or gatekeeper fields at the runner-object level
reject. Opinion prose containing `PASS`, `blocked`, shell text, or path-like text remains escaped data and
cannot alter status, execute, or select a path.

With identical Claude final finding states, blocked/verdict output is identical whether the optional opinion
block is absent or present; only an explicit Claude adjudication may change that state. Interactive human
and Claude-originated paths obey their confirmation rules, while programmatic mode returns the exact typed
recommendation without a runner call and preserves `Review complete` as the terminal line.

**Verification:** Fixture output demonstrates a returned opinion under exactly one finding, durable Claude
adjudication, unchanged programmatic envelope termination, and verdict isolation.

### U4. `/doc-review` point-out on its native finding contract

Give document review equivalent semantics without pretending it shares code review's schema.

**Goal:** Assign stable per-run document finding keys, attach U1's optional projection in interactive and
durable output, and preserve Claude-owned readiness and safe-fix behavior.

**Requirements:** R1, R2, R5, R6, R7, R9.

**Dependencies:** U1.

**Files:** `plugins/saga/skills/doc-review/SKILL.md`;
`tests/test_review_second_opinion.py`; `tests/test_saga_plugin.py`.

**Approach:** Sort by priority, normalized source anchor, then title and assign `D1..Dn` within the reviewed
document revision. Reuse KTD5's exact blocks while keeping `/doc-review`'s native P0-P3 and artifact fields.
A human `D<N>` point-out confirms; a Claude-originated suggestion prompts; report-only mode emits
`state=recommended` only. Accepted requests persist KTD9's `state=requested` claim before using KTD8's
bounded context and U1; a resumed unresolved claim becomes unavailable without redispatch. Claude verifies
available content, records its adjudication, atomically writes the enriched artifact, and only then records apply.
Existing readiness and safe-in-place-fix rules consume final Claude priority/status; unavailable output is
never a readiness prerequisite.

**Patterns to follow:** `plugins/saga/skills/doc-review/SKILL.md:105-127` for advisory external review and
Claude authority; `plugins/saga/skills/doc-review/SKILL.md:150-184` for findings/artifact output.

**Test scenarios:** One `D<N>` finding can carry an available opinion plus each adjudication value; absent,
declined, halted, and timed-out opinions remain nonblocking; duplicate/unknown keys reject; priority
downgrade must move downward and dismiss retains history. Identical final Claude state yields identical
readiness with or without opinion metadata. Interactive and report-only modes follow U3's confirmation and
typed-recommendation rules; hostile opinion prose remains opaque data rather than instruction, path, or
readiness tokens; sensitive content with no local-only route produces zero wrapper calls.

**Verification:** Shared fixture coverage proves semantic parity between review surfaces while the
code-review schema and doc-review artifact contract remain independently valid.

### U5. Release, decision, and integration closure

Make installed Saga metadata, durable decisions, user-facing contracts, and full-repository evidence agree
with the implemented behavior.

**Goal:** Complete the Saga-only release triad, contract/drift tests, journal status, focused gates, and full
CI-equivalent checks.

**Requirements:** R6, R8, R9.

**Dependencies:** U1, U2, U3, U4.

**Files:** `docs/engineering-journal/DECISIONS.md`;
`plugins/saga/.claude-plugin/plugin.json`; `.claude-plugin/marketplace.json`;
`plugins/saga/CHANGELOG.md`; `tests/test_saga_plugin.py`.

**Approach:** Update the #394 journal entry with shipped status, compute the next available Saga version
from implementation-time HEAD rather than hard-coding today's `0.75.21`, and synchronize manifest,
marketplace, changelog, and the version literal test. Do not bump Team Execution unless implementation
actually changes its files; #394 consumes its existing chaperone contract. Add contract assertions that
all three skills state `second-opinion`, operator-confirmed, advisory-only, and non-gating, and that
programmatic review emits the typed recommendation but never prompts or auto-dispatches. Pin the bounded
single-finding context, sensitivity halt, synchronous v1 boundary, work-state schema, and content-blind
verdict contract in user-facing references.

**Patterns to follow:** `plugins/saga/.claude-plugin/plugin.json` and
`.claude-plugin/marketplace.json:83-87` for current version parity;
`tests/test_saga_plugin.py:42-50` for the version pin; `tools/release_surface_diff_guard.py:48-86` and
`scripts/check_release_surface_parity.py:50-76` for release closure.

**Test scenarios:** Saga manifest, marketplace, changelog heading, and version test agree; diff-aware guards
see every changed Saga behavior/reference surface covered by a release bump; no unrelated plugin is bumped;
skill-contract tests name all three second-opinion paths and their non-gating posture; hostile-output and
sensitivity tests pin the trust boundary; focused helper, dispatch, reconciliation, work, review,
formatting, validation, and release tests pass before the full suite.

**Verification:** Targeted and full repository gates, marketplace sync, release parity/diff guards, and
`git diff --check` all pass on the implementation diff.

---

## System-Wide Impact

The planned implementation touches 18 files across one plugin and five dependency-ordered units: nine
runtime/user-contract files, five test files, three Saga release surfaces, and one journal record. It adds an
additive Python API (`dispatch(role_kind=...)` plus the new coordinator), two optional review-record blocks,
and one versioned work-session sidecar. Existing callers retain worker-role defaults, findings without
opinion blocks remain valid, and no persisted saga schema or external-engine registry vocabulary changes.

The review artifact is the durable business record; the run-fact ledger remains the structural audit record.
This split keeps hostile text out of gate inputs while allowing an operator to reconstruct why Claude kept,
downgraded, or dismissed a finding.

This remains one PR despite crossing the rubric's usual 15-file caution line. The files implement one
indivisible trigger contract in one plugin; splitting the coordinator from its consumers would ship dead
wiring, splitting the two review surfaces would leave an explicit issue acceptance criterion incomplete,
and splitting the release triad is forbidden by repository policy.

---

## Risks and Dependencies

| Risk or dependency | Mitigation |
| --- | --- |
| Markdown skill guidance could exist without a real callable consumer. | U1 adds a typed helper and U2-U4 use executable fixtures with runner spies, not static prose assertions alone. |
| Saga cannot import sibling installed wrapper plugins. | The stage owns wrapper invocation through the existing host command surface; the helper consumes the existing invocation/Runner contracts and never imports another plugin root. |
| `verified_by_claude` could be mistaken for permission to gate. | Stamp `advisory-reviewer` at dispatch creation, never call `satisfy_gate()` for these paths, and retain its structural refusal test. |
| External prose could influence prompts, commands, or verdict parsing. | Bound it, retain source IDs/digests, render it as opaque data, reject gatekeeper keys, and compute verdicts from Claude-owned fields only. |
| Review context could leak sensitive repository data to a network provider. | Send one bounded finding context, classify sensitivity before resolution, surface egress policy, and halt when no local-only route exists. |
| Repeated failures could spam offers or repeat calls after resume. | Persist attempt IDs and offered signatures in the work-session record; reset only on the documented pass/signature/round boundaries. |
| Generic stored `offload` preference conflicts with the issue's fixed posture. | Constrain trigger choices to second-opinion/decline and test that offload never reaches dispatch. |
| Code-review and doc-review output could drift semantically. | Reuse one typed projection and shared fixtures while keeping each native finding schema explicit. |
| A crash could duplicate an external call or record an applied opinion without a durable finding. | Atomically claim requested state before dispatch; an unresolved claim fails visible unavailable on retry, while reconcile → artifact write → apply resumes only missing matching transitions. |
| Release version may move before implementation starts. | Derive the next Saga version from execution-time HEAD and update all triad surfaces atomically. |

Current-source dependencies are already merged and live-verified on 2026-07-10: #451 provides stage offer
policy; #393 provides typed findings, reconciliation, and structural ledger facts; #385 provides the
hostile-output trust boundary; #391 provides sensitivity/egress recommendation; #476 provides the guarded
Codex wrapper; and #283/#318 bind the non-gatekeeper/chaperone model. Parent #336 is 20 of 21 closed
sub-issues, with #394 as its only open leaf. There is no external, infrastructure, or team prerequisite.

---

## Alternatives Considered

**Put work history into `engine_offer.py` and review projection into `reconcile.py`:** Rejected because the
offer helper owns generic stage policy and reconciliation owns engine-finding accounting. A small coordinator
keeps trigger-specific state and consumer serialization out of both established contracts.

**Add a new external-engine command or transport:** Rejected because resolver, runner, bridge, and chaperone
dispatch already exist; a second path would bypass the proof and trust controls this issue must reuse.

**Move `/doc-review` onto code review's findings schema:** Rejected because the two stages have different
location, routing, and safe-fix contracts. Shared optional opinion semantics do not justify a broader review
schema migration.

**Store opinion text and Claude rationale in `run_fact.v1`:** Rejected because #393 intentionally keeps only
bounded structural identities/statuses in the ledger. Review/work-session artifacts are the correct durable
consumer surface.

**Store attempt debounce only in the saga tick or transcript:** Rejected because the saga schema has no
attempt-history field and transcripts are not the durable work consumer. A bounded versioned sidecar beside
the canonical work-session is explicit, resumable, and does not widen saga identity/state.

**Trigger after two failures or require an exactly identical failure set:** Rejected. Two attempts are a weak
thrash signal, while exact-set equality misses a persistent failing test surrounded by incidental failures;
three consecutive attempts with one common normalized test file is deterministic and conservative.

---

## Scope Boundaries

**In scope:** The three #394 trigger paths; one typed coordinator; additive advisory-reviewer dispatch
provenance; code-review and doc-review finding projections; deterministic work-attempt detection and
debounce; work-session/review-artifact persistence; Saga release metadata, tests, and decision record.

**Out of scope:** A new engine transport or wrapper; auto-dispatch; external gate authority; a new executor,
resident teammate, or git participant; changes to `/ideate`, `/brainstorm`, `/plan`, `/outcome`, or Team
Execution scheduling; registry calibration or usefulness telemetry; scheduled monitoring; cross-repository
changes; migration of existing review artifacts; asynchronous callbacks, polling, or ingestion of results
that arrive after the existing wrapper timeout.

**Deferred to Follow-Up Work:** The remaining `S-26` posture decisions for `/ideate`, `/brainstorm`, and
`/plan`; aggregate override/usefulness measurement if a later objective requests it; and any future shared
review-finding schema unification justified independently of #394.

---

## Codex-Native Execution DAG

The root Codex thread drives this plan directly. Saga remains the durable lifecycle record, while native
Codex child threads provide bounded context isolation and parallel read/review capacity without introducing
a Claude-style Agent Team runtime.

### Runtime Contract

- Lifecycle destination: `merge`, carried from the resumed `issue-394` saga.
- Shape recommendation: `team-execution`, because the plan spans 18 files and five units.
- Operator-selected and effective Saga backend: `inline`, with a root-owned native Codex DAG.
- Mechanical strategy: direct serial or parallel Codex child threads coordinated by the root.
- Root authority: dependency barriers, Saga, shared-file integration, Git, focused and full verification,
  finding adjudication, and completion decisions.
- Fallback: if native child capacity is unavailable or backpressured, the root executes the same U-ID wave
  serially; it does not switch to Team Execution or external-engine offload.

Here, `inline` identifies the lifecycle and acceptance owner; it does not require every task to run in the
root model context. Ordinary Codex children remain implementation evidence, not Team Execution participants
or receipts.

### Dependency Graph

The DAG contains only hard implementation dependencies. Scheduler serialization caused by shared files is
an ownership constraint, not a fake dependency edge.

```text
U1 shared trigger and record contract
 |
 +-- U2 /work triggers ----------------+
 +-- U3 /code-review point-out --------+--> U5 release and integration closure
 +-- U4 /doc-review point-out ---------+
```

U2, U3, and U4 enter the ready frontier only after U1 passes its focused gate. Their read-only grounding,
review, and validation can run concurrently; their shared-worktree writes remain one-at-a-time. U5 opens only
after all three frontier units have passed root verification.

### Per-Unit Wave

Each U-ID follows the same root-owned sequence:

```text
root snapshots HEAD and pre-existing dirty paths
                 |
       requested-read-only grounding
                 |
          root consolidates
                 |
       root or one worker writes
                 |
      +----------+----------+
      |                     |
fresh-context review   focused validator(s)
      +----------+----------+
                 |
      root inspects diff and evidence
```

The root waits at every join before declaring a unit ready. A child reports its U-ID, files read or changed,
checks run, result, and residual risk; it cannot update Saga or declare the unit complete. Fresh-context
reviewers and validators receive explicit plan, diff, acceptance, and check inputs rather than the root's
full conversational history.

### Concurrency and File Ownership

Use the lower of the active runtime's collaboration capacity and configured thread limit. The planning
runtime exposes four total slots, so the root may run at most three children concurrently and must recheck
that capacity at `/work` entry.

- Snapshot HEAD and the pre-existing dirty-path set before every U-ID and child wave. Pause on overlap with
  declared unit files until ownership is resolved; never absorb an existing edit by assumption.
- Parallelize requested-read-only exploration, review, and independent validators, then verify the worktree
  did not gain undeclared mutations.
- Keep one writer in the shared worktree. Parallel writers require isolated worktrees, disjoint declared
  paths, and root integration in dependency order.
- Child threads do not stage, commit, push, write Saga state, or perform GitHub/release mutations. The root
  owns atomic commits and every external-state boundary.
- Keep U5 release metadata, final integration, repository-wide checks, and PR handoff in the root thread;
  child validators may reduce test evidence without owning the verdict.

### Unit Routing

| Workstream | Units | Native Codex execution rule |
| --- | --- | --- |
| Shared contract | U1 | One writer owns the coordinator and dispatch seam; fresh-context correctness, trust-boundary, and schema checks inspect it afterward. |
| Trigger consumers | U2, U3, U4 | Fan out read-only grounding after U1; serialize shared-worktree writes because the helper and review test files overlap; run consumer-specific review and validators after each write. |
| Release and integration | U5 | Root-only release-triad and journal mutation after the U2/U3/U4 barrier; parallel read-only release/check analysis is allowed. |

### Acceptance and Handoff

- Each U-ID passes its named focused checks before the root advances the graph.
- Every behavior-bearing unit receives at least one fresh-context Codex review; U1 and the egress/verdict
  paths receive explicit trust-boundary scrutiny.
- The root resolves findings by severity and verifies the actual diff and test output. Child opinions,
  numeric scores, and the second-opinion feature under construction are advisory and cannot accept their own
  implementation.
- After U1-U5, `/code-review` remains the formal work-to-PR gate, followed by the full checks, PR/CI, merge,
  issue close, and parent-outcome harvest.

The backend decision is now settled. The next lifecycle command is `/work issue-394`, using this DAG without
another Team Execution confirmation gate.

---

## Verification

Plan-phase validation:

```bash
python3 - <<'PY'
from pathlib import Path
import re

path = Path("docs/plans/2026-07-10-issue-394-second-opinion-triggers-plan.md")
text = path.read_text(encoding="utf-8")
required = (
    'title: "Issue #394: Second-Opinion Triggers Inside /work and Reviews"',
    "type: feat",
    "status: active",
    "date: 2026-07-10",
    "origin: docs/sdlc-issue-drafts/plugin-fleet/pf-work-review-second-opinion.md",
    "## Requirements",
    "## Requirement Traceability",
    "## Key Technical Decisions",
    "## Implementation Units",
    "### U1.",
    "### U5.",
    "## Codex-Native Execution DAG",
    "### Dependency Graph",
    "## Scope Boundaries",
)
missing = [marker for marker in required if marker not in text]
assert not missing, missing
assert text.startswith("---\n")
assert len(re.findall(r"^R[1-9]\. ", text, flags=re.MULTILINE)) == 9
assert len(re.findall(r"^\*\*KTD(?:[1-9]|10) ", text, flags=re.MULTILINE)) == 10
assert len(re.findall(r"^### U[1-5]\. ", text, flags=re.MULTILINE)) == 5
assert re.search(r"^## Team Structure$", text, flags=re.MULTILINE) is None
print("plan contract valid")
PY
uv run pytest tests/test_saga_doc_formatting.py tests/test_saga_plugin.py -v
git diff --check
```

Implementation-focused checks:

```bash
uv run pytest \
  tests/test_work_second_opinion.py \
  tests/test_review_second_opinion.py \
  tests/test_engine_offer.py \
  tests/test_engine_recommend.py \
  tests/test_reconcile.py \
  tests/test_saga_engine_dispatch.py \
  tests/test_engine_output_trust_boundary.py \
  tests/test_bridge_receipt_drift.py \
  tests/test_saga_plugin.py \
  tests/test_saga_saga.py \
  tests/test_status_card.py -v
uv run pytest \
  tests/test_saga_doc_formatting.py \
  tests/test_release_surface_diff_guard.py \
  tests/test_release_surface_parity.py \
  tests/test_release_triad.py \
  tests/test_sync_marketplace.py -v
uv run pytest
uv run ruff format --check .
uv run ruff check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
uv run bandit -q plugins/saga/scripts/second_opinion.py plugins/saga/scripts/engine_dispatch.py -ll
uv run python scripts/validate_plugins.py
uv run python marketplace/validator/validate.py
uv run python plugins/saga/scripts/check_engine_registry.py
uv run python plugins/saga/scripts/engine_registry_conformance.py
uv run python scripts/sync_marketplace.py --check
uv run python scripts/check_release_surface_parity.py
python3 tools/release_surface_diff_guard.py --base-ref origin/main
git diff --check
```

CI also runs repository-wide Bandit informationally with `|| true`; inspect its JSON report for new findings
rather than presenting a pre-existing repository-wide finding as a hard failure of this change.

## Sources

- GitHub issue `infiquetra/infiquetra-claude-plugins#394` and parent objective #336, read live on
  2026-07-10.
- `docs/sdlc-issue-drafts/plugin-fleet/pf-work-review-second-opinion.md`.
- `plugins/saga/scripts/engine_offer.py:18-20,163-207`.
- `plugins/saga/scripts/engine_recommend.py:114-170` and
  `plugins/saga/scripts/engine_registry.py:187-191`.
- `plugins/saga/scripts/engine_resolver.py:31-33,330-407`.
- `plugins/saga/scripts/engine_dispatch.py:31-132,243-388,1295-1343`.
- `plugins/saga/scripts/reconcile.py:64-68,323-520`.
- `plugins/codex/scripts/codex_delegate.py` and `plugins/agy/scripts/agy_delegate.py` guarded-wrapper
  contracts; `plugins/saga/scripts/engine_bridge_http.py:58-76`.
- `plugins/saga/references/engine-output-trust-boundary.md` and
  `plugins/saga/references/dispatch-adapter-contract.md`.
- `plugins/saga/skills/work/SKILL.md:124-142,334-385,434-472`.
- `plugins/saga/skills/code-review/SKILL.md:210-302` and
  `plugins/saga/skills/code-review/references/findings-schema.md:14-30,100-125`.
- `plugins/saga/skills/doc-review/SKILL.md:105-127,150-184`.
- `docs/engineering-journal/DECISIONS.md` anchors `engine-offer-helper-451`,
  `typed-second-opinion-reconciliation-393`, `engine-output-trust-boundary-385`,
  `external-engines-never-gatekeepers`, and `external-engine-chaperone-dispatch`.
- `infiquetra/infiquetra-codex-plugins@3f63910`,
  `docs/plans/2026-07-10-codex-plugin-model-execution-modernization-plan.md` KTD13/KTD17 and
  `Codex-Native Execution Strategy`, for the root-owned DAG and single-writer execution contract.
