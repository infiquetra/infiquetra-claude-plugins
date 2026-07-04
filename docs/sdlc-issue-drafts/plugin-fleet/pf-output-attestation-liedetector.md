---
title: "capability: output must prove its origin — server-authoritative attestation, external-token accounting, producer+consumer liveness, bridge lie-detector tests"
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
objective: "Stand up the external-engine offload lane"
---

capability: output must prove its origin — server-authoritative attestation, external-token accounting, producer+consumer liveness, bridge lie-detector tests

## Objective
Stand up the external-engine offload lane

## Tier
structural

## Wave
wave-1

## Problem / motivation (grounded)

The fleet's engine-dispatch path already gates *whether an engine's evidence is allowed to
count* (`{#external-engines-never-gatekeepers}`, #283 — Claude is verifier-of-record, external
engines are advisory/generator-only), but it does not yet gate *whether the evidence is true*.
Once a bridge (codex, agy, or a future engine) reports success, nothing on the fleet's side
independently proves the reported diff came from that engine's run, that the run actually spent
the tokens it claims, or that both halves of the delegation (the dispatch that launched the
engine and the consumption that read its result) actually fired. This is theme T15 —
"Delegation integrity: silent-no-op detection across all bridges" — from
`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §3/§8 (item 15) and §7's session-mining
finding of a recurring no-ops-masquerading-as-success pattern (5+ occurrences of
Claude-fallback / dead-wiring / test-shape-masks-dead-wiring / fake-adapter mismatch across
scanned repos).

Verified gaps in the current dispatch/gate code:

- `plugins/saga/scripts/engine_dispatch.py:163-186` (`build_dispatch_manifest`) assigns
  `Disposition.RAN_AS_REQUESTED` from `evidence.halt is None` alone — there is no check that the
  *delivered diff* is one only that engine's run could have produced (no content-provenance or
  hash-binding check against the actual bundle diff), so a hash-mismatched or empty delivery is
  accepted the same as a genuine one.
- `plugins/saga/scripts/engine_dispatch.py:281-296` (`satisfy_gate`) hard-requires
  `evidence.verified_by_claude is True` before advisory evidence counts toward any verdict, but
  this is a self-reported boolean on `AdvisoryEvidence` (`engine_dispatch.py:28-36`) — nothing
  independently ties a spend claim to the fleet's own cost ledger, so a zero-external-token
  receipt (the engine did nothing but still returned "ok") passes the same gate a real,
  metered run would.
- Neither `engine_dispatch.py` nor `plugins/team-execution/skills/team-execution/references/
  external-engine-workers.md` (the chaperone-dispatch contract, #318) currently distinguishes
  "the chaperone launched the engine but never consumed its result" from "the engine was
  consumed but never actually launched" — both look identical to today's e2e liveness check,
  which only asserts *a* result reached the manifest, not that producer and consumer both fired.
- There is no registry of which bridges are wired to emit a verifiable signature and no gate
  that fails a run when a bridge's transcript shows zero external calls despite a clean-looking
  report — i.e., nothing catches Claude quietly answering in place of the engine and dressing it
  up as a delegated run (the exact "Claude-fallback" no-op pattern named in the grounding brief).
- Binding decision `{#external-engine-chaperone-dispatch}` (#318) already fixes engines as
  offload/second-opinion workers only, never a second executor kind — this capability is the
  mechanical enforcement layer underneath that decision: it makes the fleet unable to be fooled
  about whether the offload actually happened, not a redesign of who is allowed to offload.

## Definition of Done

Merged PR that:

1. Adds a server-authoritative output-attestation check to the dispatch/manifest path: the
   delivered bundle diff is rejected with a distinct, non-zero exit code when it is empty or its
   content hash does not match what the engine's own run record claims to have produced — so a
   clone/replay/no-op delivery cannot pass as a genuine one.
2. Adds external-token accounting to `AdvisoryEvidence`/`build_dispatch_manifest` as the
   fail-loud silent-fallback discriminator: a zero-external-token receipt trips a `HALT`
   disposition instead of `RAN_AS_REQUESTED`, and the spend value is written to the cost ledger
   exactly once per dispatch (no double-count on retry, no silent drop on failure).
3. Adds a producer+consumer liveness check to the chaperone-dispatch e2e path
   (`external-engine-workers.md`'s launch → dispatch → verify → apply flow): a run where the
   engine was launched but its result never consumed, and a run where a result was consumed but
   no launch record exists, both fail the same e2e liveness test — "wired" requires both halves,
   not either alone.
4. Adds a `bridge-signatures.json` registry (one entry per registered bridge naming its expected
   signature/receipt shape) plus an `assert_bridge_ran` HALT gate consulted post-run: a fixture
   transcript with zero external calls exits non-zero with a `clone-detected`-style message
   instead of passing silently.
5. Adds sentinel/adversarial fixture tests (bridge lie-detector tests) that fail when Claude
   answers plausibly in place of the engine without the engine's proof signature present —
   proving the whole stack (1–4) actually discriminates a real delegated run from a Claude-only
   answer dressed up as one.
6. Bumps the release surface for every plugin whose behavior or schema changed (see checklist
   below) in the same PR.

### Acceptance criteria
- [ ] An empty-bundle-diff or hash-mismatched delivery from an external engine is rejected with
  a distinct, documented exit code — not silently accepted as `RAN_AS_REQUESTED`. Check:
  `uv run pytest tests/test_engine_dispatch_attestation.py -k hash_mismatch_rejected` → passes.
  *(covers T15-F5-2, primary)*
- [ ] A zero-external-token receipt trips `HALT` instead of `RAN_AS_REQUESTED`, and the spend
  value for that dispatch appears exactly once in the cost ledger (no duplicate entry on
  retry, no silent omission on halt). Check: `uv run pytest tests/test_engine_dispatch_ledger.py
  -k zero_token_halts_and_ledgers_once` → passes. *(covers T15-F4-7)*
- [ ] A launched-but-unconsumed dispatch (engine ran, result never read by the chaperone) fails
  the e2e liveness test. Check: `uv run pytest tests/test_chaperone_liveness.py -k
  launched_unconsumed_fails` → passes. *(covers T15-F6-7)*
- [ ] A consumed-but-unlaunched dispatch (a result is present with no matching launch record)
  fails the same e2e liveness test. Check: `uv run pytest tests/test_chaperone_liveness.py -k
  consumed_unlaunched_fails` → passes. *(covers T15-F6-7)*
- [ ] A zero-external-call fixture transcript exits non-zero with a clone-detected-style message
  when checked against the `bridge-signatures.json` registry via `assert_bridge_ran`. Check:
  `uv run pytest tests/test_bridge_signatures.py -k zero_call_transcript_exits_nonzero` →
  passes. *(covers T15-F4-2)*
- [ ] A sentinel fixture where Claude answers plausibly in place of the engine (no engine proof
  signature present) fails the lie-detector test suite. Check: `uv run pytest
  tests/test_bridge_lie_detector.py -k claude_fallback_without_signature_fails` → passes.
  *(covers X-codex-5)*
- [ ] Full suite, lint, and types stay green. Check: `uv run pytest && uv run ruff check . &&
  uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` → all pass.

### Out-of-scope / non-goals
**In scope:**
- Server-side output-attestation check on the delivered diff (hash/empty-bundle rejection).
- External-token accounting wired into the existing cost ledger as a HALT discriminator.
- Producer+consumer liveness check on the chaperone-dispatch e2e path (both existing bridges:
  codex, agy).
- `bridge-signatures.json` registry + `assert_bridge_ran` HALT gate.
- Adversarial/sentinel lie-detector fixture tests proving the above actually discriminate a
  real delegated run from an undelegated Claude answer.

**Non-goals:**
- Making external engines gatekeepers or granting them gating authority — Claude stays
  verifier-of-record per `{#external-engines-never-gatekeepers}` (#283); this issue only makes
  the *evidence feeding that verifier* harder to fake.
- Redesigning `team-execution`'s chaperone-dispatch model or team roster/residency — per
  `{#external-engine-chaperone-dispatch}` (#318), engines remain offload/second-opinion workers
  only; this issue does not add a second executor kind.
- A standing/scheduled catch-rate monitoring dashboard — this ships an enforced gate plus
  fixture tests, not an ongoing telemetry loop.
- Retrofitting historical manifests/dispatches emitted before this change — no backfill of past
  `RAN_AS_REQUESTED` dispositions.
- Building a general-purpose content-provenance system beyond the bundle-diff/hash check needed
  to satisfy T15-F5-2 — cryptographic signing of engine outputs is out of scope for v1.

## Grounding References

- Absorbed ideas (full bases in
  `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T15.json`):
  - `T15-F5-2` (primary) — "Server-authoritative output attestation: the delivered diff must be
    one only the engine's run could emit." Axis: proof-of-execution.
  - `T15-F4-7` (facet) — "External-token accounting as the fail-loud silent-fallback
    discriminator, wired to the cost ledger." Axis: silent-fallback-elimination.
  - `T15-F6-7` (facet) — "Every-issue-self-executing flip: a bridge is 'wired' only if producer
    AND consumer both fired." Axis: silent-fallback-elimination.
  - `X-codex-5` (facet) — "Bridge Lie-Detector Tests." Axis: adversarial silent-no-op detection.
  - `T15-F4-2` (facet) — "Bridge-signature registry with a fail-loud post-run HALT gate." Axis:
    silent-fallback-elimination.
  - Consolidation rationale (issue-map): these five facets are the proof-of-execution and
    liveness half of theme T15 — attestation of *what* was delivered (F5-2), accounting of
    *whether spend actually happened* (F4-7), liveness of *both delegation halves* (F6-7),
    a registry-backed *fail-loud gate* over bridge signatures (F4-2), and the *adversarial test
    suite* that proves the first four actually discriminate a real run from a dressed-up no-op
    (X-codex-5) — merged into one PR because they share the same dispatch/manifest seam and
    ship no value independently of each other (a signature registry without lie-detector tests
    proving it fires is unverified; lie-detector tests without an attestation/ledger/liveness
    mechanism to test have nothing to exercise).
- Binding decisions engaged (grounding brief §2):
  - `{#external-engines-never-gatekeepers}` (#283) — Claude is verifier-of-record; this issue
    hardens the evidence Claude adjudicates, it does not change who adjudicates.
  - `{#external-engine-chaperone-dispatch}` (#318) — external engines in teams are chaperone
    dispatch (offload/second-opinion) only; this issue does not touch team roster or residency.
- Recurring-pain evidence (grounding brief §7): 5+ occurrences across scanned repos of
  Claude-fallback / dead-wiring / test-shape-masks-dead-wiring / fake-adapter mismatch — the
  exact failure class this capability closes structurally instead of catching it after the fact
  in a retro.
- Current-state code citations verified during grounding (2026-07-03):
  - `plugins/saga/scripts/engine_dispatch.py:163-186` (`build_dispatch_manifest`; disposition
    derived from `evidence.halt is None` alone, no content-provenance check today).
  - `plugins/saga/scripts/engine_dispatch.py:281-296` (`satisfy_gate`; gates on the self-reported
    `evidence.verified_by_claude` bit alone).
  - `plugins/saga/scripts/engine_dispatch.py:28-36` (`AdvisoryEvidence` dataclass — no
    signature/liveness fields today).
  - `plugins/team-execution/skills/team-execution/references/external-engine-workers.md`
    (chaperone-dispatch protocol: resolve → dispatch → verify → apply → test → manifest; no
    producer+consumer liveness check on this path today).
  - `docs/engineering-journal/LEARNINGS.md` §6.1-area entries documenting the Claude-fallback /
    dead-wiring / fake-adapter no-op pattern referenced in the grounding brief.

## Executor Profile

- **Model:** sonnet
- **Effort:** medium
- **Backend:** inline
- **External-LLM posture:** none
- **Justification:** not above sonnet — the mechanism (attestation check, ledger wiring,
  liveness check, signature registry, adversarial fixtures) is fully specified by the five
  absorbed ideas' acceptance sketches; there is no open design ambiguity requiring opus-tier
  judgment, and this issue explicitly does not touch the gating-authority or team-residency
  decisions that would warrant it.

## Release-Surface Checklist (plugin changes — required)

- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump + description update reflecting
  the new attestation/ledger/liveness/signature-registry behavior in the dispatch path.
- [ ] `.claude-plugin/marketplace.json` — mirrored version/description update for `saga`.
- [ ] `plugins/saga/CHANGELOG.md` — entry documenting the attestation check, token-accounting
  HALT discriminator, producer+consumer liveness gate, `bridge-signatures.json` registry, and
  the lie-detector fixture suite; note no backward-compatibility break for historical manifests
  (no backfill, per non-goals).
- [ ] `plugins/agy/.claude-plugin/plugin.json` + `plugins/agy/CHANGELOG.md` — updated if the
  agy bridge's evidence emission changes to satisfy the new signature registry.
- [ ] Version/metadata drift-guard tests — confirm `plugin.json` / `marketplace.json` /
  `CHANGELOG.md` all tell the same story as the diff before the PR is treated as ready.

## Files Expected to Change

Indicative only — the exact set is `/plan`'s to determine.
- `plugins/saga/scripts/engine_dispatch.py` — attestation check in `build_dispatch_manifest`;
  token-accounting HALT discriminator wired to the cost ledger; producer+consumer liveness check.
- `plugins/saga/scripts/bridge_signatures.py` — new module: `bridge-signatures.json` registry
  loader + `assert_bridge_ran` HALT gate (proposed path).
- `plugins/saga/references/bridge-signatures.json` — new registry file, one entry per bridge.
- `plugins/team-execution/skills/team-execution/references/external-engine-workers.md` —
  document the producer+consumer liveness requirement on the chaperone-dispatch e2e path.
- `tests/test_engine_dispatch_attestation.py` — new hash-mismatch / empty-bundle rejection tests.
- `tests/test_engine_dispatch_ledger.py` — new zero-token HALT + single-ledger-entry tests.
- `tests/test_chaperone_liveness.py` — new launched-unconsumed / consumed-unlaunched tests.
- `tests/test_bridge_signatures.py` — new zero-call transcript / registry gate tests.
- `tests/test_bridge_lie_detector.py` — new adversarial sentinel fixture tests.

## Tests to Add or Update

- Attestation: empty-bundle or hash-mismatched delivery rejected with a distinct exit code.
- Ledger: zero-external-token receipt trips `HALT`; spend value ledgered exactly once (no
  double-count on retry).
- Liveness: launched-but-unconsumed and consumed-but-unlaunched dispatches both fail the e2e
  liveness test.
- Signature registry: zero-external-call fixture transcript exits non-zero with a
  clone-detected-style message via `assert_bridge_ran`.
- Lie-detector: sentinel fixture where Claude answers in place of the engine without the
  engine's proof signature fails the suite.

### Verification
```bash
uv run pytest tests/test_engine_dispatch_attestation.py -v
uv run pytest tests/test_engine_dispatch_ledger.py -v
uv run pytest tests/test_chaperone_liveness.py -v
uv run pytest tests/test_bridge_signatures.py -v
uv run pytest tests/test_bridge_lie_detector.py -v
uv run pytest && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all green; the zero-token, hash-mismatch, launched-unconsumed, consumed-unlaunched,
and zero-external-call fixtures each fail loud with the documented exit code/message, and the
lie-detector sentinel fixture fails when the engine's proof signature is absent.

## Handoff Maturity
requirements-ready

## Suggested Next Action
Use `/plan <issue>` to create an implementation plan.

## Source Context
- Source: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T15.json (ids: T15-F5-2
  (primary), T15-F4-7, T15-F6-7, X-codex-5, T15-F4-2 (facets))
- Source type: ideation-issue-map
- Source title: Output must prove its origin: server-authoritative attestation, external-token
  accounting, producer+consumer liveness, bridge lie-detector tests

### Intent

The fleet's engine-dispatch path already gates *whether an engine's evidence is allowed to count* (`{#external-engines-never-gatekeepers}`, #283 — Claude is verifier-of-record, external engines are advisory/generator-only), but it does not yet gate *whether the evidence is true*. Once a bridge (codex, agy, or a future engine) reports success, nothing on the fleet's side independently proves the reported diff came from that engine's run, that the run actually spent the tokens it claims, or that both halves of the delegation (the dispatch that launched the engine and the consumption that read its result) actually fired. This is theme T15 — "Delegation integrity: silent-no-op detection across all bridges" — from `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §3/§8 (item 15) and §7's session-mining finding of a recurring no-ops-masquerading-as-success pattern (5+ occurrences of Claude-fallback / dead-wiring / test-shape-masks-dead-wiring / fake-adapter mismatch across scanned repos).

### Context library links

_none_

### Files expected to change

- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T15.json`
- `plugins/team-execution/skills/team-execution/references/external-engine-workers.md`
- `docs/engineering-journal/LEARNINGS.md`
- `plugins/saga/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `plugins/saga/CHANGELOG.md`
- `plugins/agy/.claude-plugin/plugin.json`

### Tests to add or update

- `tests/test_bridge_lie_detector.py`
- `tests/test_bridge_signatures.py`
- `tests/test_chaperone_liveness.py`
- `tests/test_engine_dispatch_attestation.py`
- `tests/test_engine_dispatch_ledger.py`

### Objective

"Stand up the external-engine offload lane"

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/388
- Number: 388
- Created at: 2026-07-04T07:57:41.315774+00:00

