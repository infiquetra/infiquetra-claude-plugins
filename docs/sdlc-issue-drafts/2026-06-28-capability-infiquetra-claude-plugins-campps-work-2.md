---
title: capability: evidence/provenance manifests — a verified-vs-adjudicated record per delegated output
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
---

# capability: evidence/provenance manifests — a verified-vs-adjudicated record per delegated output

### Objective

Give saga a uniform provenance-manifest envelope on every delegated agent output — one record per
execution with an `output_completeness` subrecord (declared vs produced) and a `claim_provenance`
subrecord (source-attributed claims plus a two-layer producer-claimed vs Claude-adjudicated tag). S-7's
completeness gate reads the first subrecord; S-4's verifier-of-record reads the second. R11 defines the
shared contract; a claimed-`verified` claim whose cited source contradicts it is the machine-readable
parroting signal.

### Intent

Turn saga's prose-only provenance habit (`/doc-review`, `/code-review`, `/brainstorm`, `/investigate`
all verify by instruction text, leaving no machine record) into a durable record modeled on the
machinery that already works (`orchestration_downgrade`, `validator-evidence-state`). The payoff:
evidence is verified once and reused instead of re-checked at every boundary; parroting is caught
structurally rather than by luck (the outcome-orchestration build shipped wrong degrade wiring because
an engine parroted two code claims — `DECISIONS.md:290`); and the two filed gate issues (#277, #283)
consume one contract instead of each inventing its own audit trail. Actors: the producing agent
(external engine / team-execution worker / cc-workflows agent) emits the manifest; Claude
(verifier-of-record) adjudicates gate-relevant claims and attests its own adjudication; the scheduled
gate consumers are S-7 (#277) and S-4 (#283); the live advisory consumers today are `/code-review`,
`/qa`, and `/retro`.

### Out-of-scope / non-goals

- Exact manifest schema, subrecord field names, carrier choice, serialization (→ `/plan`).
- Build-sequencing of #277 / #283 / this issue (→ `/plan`).
- Mutating external workers (waits on the ideation-R14 read-only sandbox; R11 is evidence-only).
- A manifest store / browser / query UI; inline-Claude self-attestation; any gate of R11's own.
- Backfill of historical outputs (manifests begin at adoption).

### Files expected to change

Exact files are a `/plan` decision; the expected surfaces are:

- `plugins/saga/scripts/` — manifest envelope + subrecords producer and carrier (e.g. `outcome_store.py`, `execution_spec.py`)
- `plugins/saga/skills/code-review/` — R15 advisory-consumer wiring (skip re-verifying adjudicated-`verified` claims)
- `plugins/saga/skills/qa/` — R16 confidence-signal consumer
- `plugins/saga/skills/retro/` — R16 parroting-count + disposition-rate consumer
- `plugins/saga/references/saga-spec.md` — manifest contract + producer/consumer matrix documentation
- `tests/` — manifest contract + consumer tests

### Tests to add or update

- `tests/` — manifest envelope schema (two subrecords; declared-vs-produced diff)
- parroting taxonomy: claimed-`verified` + adjudicated-`refuted` counted; `not-adjudicated` / `source-stale` not counted
- R10 scoping: missing manifest trips only on contract-bearing delegated leaves
- advisory-never-blocks; evidence-only (no mutation, no standalone verdict)
- producer/consumer matrix guard: no manifest field without a live-or-scheduled reader

### Context library links

- `docs/brainstorms/2026-06-28-evidence-provenance-manifests-requirements.md` — requirements doc
- `docs/reviews/2026-06-28-evidence-provenance-manifests-readiness.md` — readiness review (verdict READY)
- `docs/ideation/2026-06-26-vecu-port-seeds-ideation.md` — survivor R11
- #277 (S-7 completeness gate) and #283 (S-4 capability routing) — the two scheduled gate consumers

### Acceptance criteria

Each criterion is a check that must pass once built:

- [ ] Manifest envelope with both subrecords per delegated output — `uv run pytest tests/ -k manifest_envelope` → pass
- [ ] Parroting counted only on `refuted`/`unsupported`, benign divergence excluded — `uv run pytest tests/ -k parroting_taxonomy` → pass
- [ ] Missing manifest trips only on contract-bearing leaves — `uv run pytest tests/ -k completeness_contract_bearing` → pass
- [ ] Advisory tier never blocks — `uv run pytest tests/ -k advisory_never_blocks` → pass
- [ ] No manifest field without a live-or-scheduled reader — `uv run pytest tests/ -k manifest_no_orphan_field` → pass
- [ ] Lint, types, security clean — `uv run ruff check . && uv run mypy plugins/ && uv run bandit -r plugins/` → exit 0

### Verification

```bash
# Full local gate (mirrors CI)
uv run pytest -q
uv run ruff format --check .
uv run ruff check .
uv run mypy plugins/
uv run bandit -r plugins/ -q
# Manifest-specific suites
uv run pytest tests/ -k "manifest or parroting or completeness" -v
```

Expected: all green; the manifest / parroting / completeness suites pass.

---
date: 2026-06-28
topic: evidence-provenance-manifests
maturity: requirements-ready
source: docs/ideation/2026-06-26-vecu-port-seeds-ideation.md (survivor R11 — Evidence / Provenance Manifests)
---

# Evidence / Provenance Manifests

## Summary

Give saga a uniform provenance **manifest envelope** that travels with every delegated agent output —
one record per execution carrying two subrecords: an `output_completeness` subrecord (what was declared
vs what was produced) and a `claim_provenance` subrecord (per-claim source refs and a two-layer
epistemic tag: producer-*claimed* vs Claude-*adjudicated*). The completeness subrecord is what S-7's
gate checks; the provenance subrecord is what S-4's verifier-of-record checks. R11 defines the shared
contract those two future consumers will read; its live consumers today are the advisory ones
(`/code-review`, `/qa`, `/retro`). A claim whose source is checked and *contradicted* is the
machine-readable signal for parroting.

## Problem Frame

Saga already does provenance two distinct ways, and it is important not to conflate them. First, a
**prose habit**: `/doc-review` requires every claim to cite evidence or be flagged unverified
(`plugins/saga/skills/doc-review/SKILL.md:83-94`); `/code-review` mandates "verify, don't guess — cite
the proving line or flag unverified" (`plugins/saga/skills/code-review/SKILL.md:39-43`); `/brainstorm`
says "label it an unverified assumption" (`plugins/saga/skills/brainstorm/SKILL.md:137-141`);
`/investigate` runs an assumption audit marking each belief *verified* or *assumed*
(`plugins/saga/skills/investigate/SKILL.md:57-61`). These are habits enforced only by instruction text;
none emits a record a later consumer can act on.

Second, **durable machinery** that is real but narrow: `orchestration_downgrade` is a complete
produce→persist→consume provenance loop, and `validator-evidence-state` is a per-run machine-readable
evidence record for team-execution validators. Neither generalizes to arbitrary agent output. R11's job
is to turn the prose habit into the missing machine-readable record, modeled on the durable machinery
that already works.

The cost of prose-only provenance is paid every time evidence crosses an agent boundary.
`/code-review`'s validator pass re-verifies every surviving finding from scratch
(`plugins/saga/skills/code-review/SKILL.md:39-43`); `/qa` openly admits its ship inputs are
LLM-assigned and therefore "one signal, not the gate" (`plugins/saga/skills/qa/SKILL.md:49-58`); the
verifier-of-record obligation is pure operator discipline with no machine trace.

The motivating failure is on the record. In the outcome-orchestration build, three engines independently
drafted a plan under trust-but-verify; Antigravity **parroted two code claims** that Claude and Codex
each checked against source and rejected, and its degrade wiring was wrong as a result
(`docs/engineering-journal/DECISIONS.md:290`). A human verifier caught it that time. Nothing structural
prevents the next one.

Two issues already on the operations board point at the same absent record from opposite directions.
S-7 (#277, silent-omission completeness gate) needs a post-execution record to diff *declared* against
*produced* output. S-4 (#283, external-engine capability routing) needs an attributable record to
verify external output "before it feeds any gate," and its Scope Boundaries section explicitly names
R11 as the owner of the "verified-vs-parroted audit trail." Both issues are *proposals*, not built code
— so R11 defines the contract they will consume, rather than wiring into gates that exist today.

## Key Decisions

- **D1. Extend the existing provenance machinery; do not build a parallel store.**
  `orchestration_downgrade` is a complete provenance loop — *produced* in
  `plugins/saga/scripts/lifecycle_state.py:238-304`, *guarded and persisted* in
  `plugins/saga/scripts/saga.py:630-687`, *consumed* in
  `plugins/saga/scripts/override_rate_reader.py:74,137,215`; `validator-evidence-state` is a per-run
  evidence record with input tracing
  (`plugins/team-execution/skills/team-execution/references/validator-evidence-state.md`). R11
  generalizes these. A net-new manifest store reinvents `validator-evidence-state`; and because saga
  preserves unknown frontmatter keys for forward compatibility
  (`plugins/saga/references/saga-spec.md:274-278`), a field added without a reader would persist
  silently rather than error — which is exactly why every manifest field must name a live or scheduled
  consumer (see the producer/consumer matrix under Requirements).

- **D2. Two-layer epistemic tag: producer claims, Claude adjudicates — and only a *contradiction*
  signals parroting.** Each claim carries a producer-*claimed* status plus the source ref that makes it
  checkable, and a Claude-*adjudicated* status. The adjudicated status is authoritative wherever the
  manifest feeds a gate. The parroting signal is narrow: a claim claimed-`verified` whose source, when
  checked, *contradicts* it (`refuted`/`unsupported`). A claim left `not-checked` because the verifier
  spent no budget, or one whose source legitimately drifted, is **not** parroting — each carries a
  distinct `mismatch_reason` (see R7). A producer self-tag alone is worthless — a parroting engine
  claims "verified" for everything — so its only job is to point the verifier at what to check.

- **D3. Tiered enforcement, mapped onto saga's existing gated/advisory split.** Advisory by default
  (surfaced to `/qa`, `/retro`, `/code-review` as a confidence signal — these consumers are live
  today); a hard gate only where a gate is *defined* — S-7's completeness gate and S-4's R13 boundary —
  which activates when those issues build. No new gate is imposed on inline, exploratory, or
  contract-less work.

- **D4. R11 owns the manifest envelope and its two subrecords; S-4 and S-7 read one subrecord each.**
  The envelope (carrier, lifecycle, attribution, disposition, existence bit) is shared. S-7's gate reads
  the `output_completeness` subrecord (declared vs produced); S-4's verifier-of-record reads the
  `claim_provenance` subrecord (source-attributed claims + two-layer tags). One record produced once at
  agent exit, two consumers reading different subrecords — this is the "unifies S-4 + S-7" payoff, and
  it is why the answer is one envelope with two subrecords, not two records sharing a name.

- **D5. Manifests cover delegated outputs; Claude adjudicates and its adjudication is itself attested.**
  Every delegated output (external engine, team-execution worker, cc-workflows agent) carries a
  manifest. Inline Claude is the verifier-of-record — it writes the adjudication, it does not
  self-attest, which avoids the who-verifies-the-verifier regress. To keep the verifier honest without
  that regress, the adjudication record itself stores `{adjudicator, source refs read, scope checked,
  source revision, decision}` — so a later consumer that trusts an adjudicated-`verified` claim (R15)
  can see exactly what was checked.

- **D6. The never-gatekeeper rule is supported by, not invented from, the parroting finding.** Per S-4,
  the parroting evidence (`DECISIONS.md:290`) is rationale, not a standing governance decision. R11
  operationalizes the rule — an external engine's claimed status can never persist as a gated verdict —
  but `/plan` writes any new `DECISIONS.md` entry when this lands.

- **D7. R11 is a contract definition first, a wiring second.** Because S-7 (#277) and S-4 (#283) are
  proposals, R11 ships in two speeds: the envelope plus the *live* advisory wirings (`/code-review`,
  `/qa`, `/retro`) land against code that exists today; the *gate* wirings (S-7 completeness, S-4 R13)
  activate when those issues build. Whether R11 builds before, alongside, or as a shared schema unit
  inside S-7/S-4 is a build-sequencing decision for `/plan`.

## Actors

- A1. **Producing agent** — an external engine, a team-execution worker, or a cc-workflows agent. Emits
  the manifest: the `output_completeness` subrecord (declared/produced) and the `claim_provenance`
  subrecord (claims, source refs, claimed tags).
- A2. **Claude (verifier-of-record)** — adjudicates each gate-relevant claim against its cited source,
  writes the (attested) adjudication, and is accountable for any gated verdict. Never an external
  engine.
- A3. **Gate consumers (scheduled, not yet built)** — S-7's completeness gate (reads
  `output_completeness`) and the S-4 R13 boundary (reads `claim_provenance`). They block; they activate
  when #277/#283 build.
- A4. **Advisory consumers (live today)** — `/code-review`'s validator pass, `/qa`, `/retro`,
  `/investigate`. Read the manifest as a signal; never block.

## Requirements

### Manifest envelope and subrecords

- R1. A manifest is a per-execution record bound to a single delegated agent invocation. It is an
  *envelope* carrying shared fields — producer attribution (R2), provenance disposition (R18), an
  existence bit, and lifecycle/carrier metadata — plus two subrecords: `output_completeness` (R3) and
  `claim_provenance` (R4-R6). (Exact schema, field names, and serialization → `/plan`.)
- R2. The envelope records **who produced it**: engine identity plus effort/protocol for external
  engines; the validator/worker name for team-execution; the agent label for cc-workflows. This is the
  attribution S-4 R13 requires to make a result verifiable and repeatable.
- R3. The `output_completeness` subrecord records **declared vs produced**: the required output keys the
  agent was asked to emit (the `Unit.returns` contract, `plugins/saga/scripts/execution_spec.py:180`)
  and what it actually emitted (keys, count, envelope completeness). This is the diff S-7's gate needs
  and cannot perform today.
- R4. The `claim_provenance` subrecord records each substantive **claim** with a source ref (a
  `file:line`, a URL, or a command and its output) and a source revision/timestamp (R7). A claim
  carrying no source ref is recorded as `not-checkable` — a distinct protocol state, never silently
  dropped and never counted as parroting.

### Adjudication (two-layer tag)

- R5. Each claim carries a producer-**claimed** status — `verified | inferred | not-checked`. It is
  self-reported and non-authoritative; its sole function is to direct the verifier's attention. Each
  value must carry a defined gate-effect at `/plan` (what an `inferred` or `not-checked` claim does when
  it reaches a gate); whether the producer layer collapses to `verified | unverified` is an open
  `/plan` question.
- R6. Each claim carries a Claude-**adjudicated** status — `verified | inferred | not-checked | refuted`
  — plus the attested adjudication record (D5). The adjudicated status is authoritative wherever the
  manifest feeds a gate; an external engine never holds the adjudicated tag (S-4 R13).
- R7. A claim whose claimed and adjudicated statuses diverge carries a `mismatch_reason`:
  `not-adjudicated` (verifier spent no budget), `scope-excluded` (out of the adjudication's scope),
  `source-stale` (the cited source changed after the claim was made — detected via the source revision
  in R4), or `unsupported`/`refuted` (the source does not support, or contradicts, the claim). **Only
  `unsupported`/`refuted` is counted as parroting**, surfaced to `/retro` and tallied the way
  `override_rate_reader.py` tallies degradation events.

### Enforcement (tiered)

- R8. The default tier is **advisory**: the manifest is surfaced and consumed as a confidence signal by
  live consumers and never blocks.
- R9. A **full** manifest (with adjudication) is required only for outputs that feed a gate or that
  carry a declared output contract. Advisory, non-gated, contract-less outputs carry **lightweight run
  metadata** (attribution + disposition + existence bit), not a full adjudicated manifest — the payload
  is sized to the tier so "every delegated output" does not impose adjudication cost where nothing reads
  it.
- R10. At S-7's completeness gate, a required, non-skipped, **contract-bearing** delegated leaf whose
  manifest is missing is a `missing-output` trip. This matches S-7's opportunistic, contract-optional
  boundary (`docs/brainstorms/2026-06-27-silent-omission-completeness-gate-requirements.md:104-105`): a
  leaf with no contract is not tripped for lacking a manifest.
- R11. At an S-4 R13 gated decision, a gated verdict cannot persist unless the manifest's gate-relevant
  claims carry a Claude-adjudicated status. An external engine's claimed-`verified` is insufficient on
  its own.
- R12. R11 adds **no gate of its own**. It supplies evidence to the S-7 and S-4 gates; work outside
  those gates' scope — inline, exploratory, contract-less — is never blocked by the manifest.

### Consumers and the producer/consumer matrix

- R13. S-7's completeness gate consumes the `output_completeness` subrecord (R3); it does not define its
  own manifest shape. (Scheduled consumer — activates when #277 builds.)
- R14. S-4's verifier-of-record consumes the envelope attribution (R2) and the `claim_provenance`
  subrecord (R4-R6); it does not define its own audit-trail shape. (Scheduled consumer — activates when
  #283 builds, and depends on the S-4 team-execution external-wrapper context contract, itself a
  prerequisite —
  `docs/brainstorms/2026-06-27-external-engine-capability-routing-requirements.md:323-327`.)
- R15. `/code-review`'s validator pass (live today) consumes adjudicated tags to skip re-verifying
  already-`verified` claims and concentrate its budget on `not-checked`/`inferred` ones
  (`plugins/saga/skills/code-review/SKILL.md:39-43`). It may trust an adjudicated-`verified` claim only
  because the adjudication is attested (D5).
- R16. `/qa` (live today) consumes the ratio of adjudicated-`verified` to `inferred`/`not-checked`
  claims as the confidence signal it currently lacks (`plugins/saga/skills/qa/SKILL.md:49-58`); `/retro`
  (live today) consumes the parroting count (R7) and the disposition rate (R18).
- R17. Every manifest field must appear in a producer/consumer matrix at `/plan` naming, per field, its
  producer, its reader, and whether that reader is live today or scheduled with #277/#283. A field with
  no live or scheduled reader stays out of the schema. The v1 live readers are the advisory consumers
  (R15, R16); the gate readers (R13, R14) are scheduled.

### Durability, provenance, and carrier

- R18. Every manifest carries a provenance **disposition** mirroring `orchestration_downgrade`:
  `ran-as-requested | fell-back-to-claude | substituted-engine`. A fallback or substitution is recorded
  in the result, the saga tick, and the report — never silent (S-4 R24;
  `plugins/saga/references/execution-spec.md:136`). `/retro` reports the disposition rate (R16).
- R19. The manifest is durable and **cross-session readable**: it persists on a carrier reachable from
  any worktree and any session, so `/code-review` (a separate run) can read a manifest produced
  elsewhere. The git-common-dir outcome-store cache satisfies this
  (`plugins/saga/scripts/outcome_store.py:93-148`); a session-local file would not. Selecting a carrier
  (e.g. the outcome-store cache, `CompletionEvent.payload`, or a tick pointer field) requires a typed
  key and a reader contract — `CompletionEvent.payload` is an open dict today
  (`plugins/saga/scripts/outcome_store.py:252-296`), not yet a consumer surface. (Carrier choice →
  `/plan`.)

### Safety and scope

- R20. A manifest is evidence, never authority: it does not itself mutate state and does not hold a
  verdict (S-4 R23, evidence-only).
- R21. Producing a manifest grants no new privilege. Recording "what I read / what I ran" reflects
  actions the agent already took; it never authorizes mutation. Manifests for *mutating* external
  workers wait on the read-only sandbox (ideation R14) — until then, external workers are evidence-only.

## Key Flows

- F1. **External engine as gated generator (S-4 path).** **Trigger:** an external engine runs as a
  gated generator. The engine emits a manifest whose `claim_provenance` subrecord carries claims, source
  refs, and claimed tags → Claude adjudicates each gate-relevant claim against its cited source and
  writes the attested adjudication → the gate reads the adjudicated status → the verdict persists only
  if the gate-relevant claims are adjudicated-`verified`. A claimed-`verified` claim adjudicated
  `refuted` is logged as parroting. **Covers R2, R4-R7, R11, R14.**

- F2. **Team-execution leaf completeness (S-7 path).** **Trigger:** a required, non-skipped,
  contract-bearing leaf exits. The leaf emits a manifest whose `output_completeness` subrecord carries
  declared vs produced → the completeness gate diffs them → a missing manifest, or `declared >
  produced`, is a `missing-output` trip. A contract-less leaf is not tripped for lacking a manifest.
  **Covers R3, R10, R13.**

- F3. **Advisory consumption (live today).** **Trigger:** any delegated output completes outside a gate.
  A lightweight manifest is logged → `/qa` reads the verified/inferred ratio as a confidence input →
  `/retro` counts parroting and disposition rates → `/code-review`'s validator skips re-verifying
  adjudicated-`verified` claims. Nothing blocks. **Covers R8, R9, R12, R15, R16.**

- F4. **Fallback or substitution.** **Trigger:** the requested engine is unavailable. Saga substitutes
  another engine or falls back to Claude → the disposition (`substituted-engine` /
  `fell-back-to-claude`) is recorded in the result, tick, and report. **Covers R18.**

## Acceptance Examples

- AE1. **Parroting caught.** **Covers R6, R7, R11.** Given an external engine claims a code fact
  `verified` with a source ref that, when read, *contradicts* it, when Claude adjudicates, then the
  adjudicated status is `refuted` with `mismatch_reason: unsupported`, the gated verdict does not
  persist, and the case is counted as parroting in `/retro`.
- AE2. **Benign divergence is not parroting.** **Covers R7.** Given an external engine claims a fact
  `verified` and Claude does not spend budget to check it, when the manifest is read, then the claim is
  adjudicated `not-checked` with `mismatch_reason: not-adjudicated` and is **not** counted as parroting.
- AE3. **Missing manifest at the completeness gate.** **Covers R10, R13.** Given a required,
  non-skipped, contract-bearing team-execution leaf produces no manifest, when the completeness gate
  runs at exit, then a `missing-output` trip fires; a contract-less leaf in the same run does not trip.
- AE4. **Advisory work is never blocked.** **Covers R8, R9, R12.** Given an inline exploratory output
  with no manifest, when work proceeds, then nothing blocks and no gate is created.
- AE5. **Validator skips re-verification safely.** **Covers R15, D5.** Given a `/code-review` finding
  whose claim is adjudicated-`verified` with an attested adjudication record, when the validator pass
  runs, then it does not re-verify that claim and spends its budget on `not-checked` claims.
- AE6. **Fallback disposition is visible.** **Covers R18.** Given a requested engine is unavailable and
  Claude runs instead, when the manifest is written, then `disposition: fell-back-to-claude` appears in
  the result, the tick, and the report.
- AE7. **Manifest is evidence, not authority.** **Covers R20.** Given a manifest records
  `files_inspected`, when any consumer reads it, then no consumer treats the manifest as authority to
  mutate state or as a standalone verdict.

## Scope Boundaries

**In scope:** the manifest envelope and its two subrecords (R1-R4); the two-layer tag and the parroting
taxonomy (R5-R7); tiered enforcement with payload sized to tier (R8-R12); the consumer wirings and the
producer/consumer matrix — live advisory now, scheduled gates with #277/#283 (R13-R17); durability,
disposition, and the cross-session carrier (R18-R19); evidence-only safety (R20-R21).

**Deferred for later (not v1, or owned elsewhere):**

- Exact manifest schema, field names, storage format, serialization, and the producer/consumer matrix's
  concrete code owners → `/plan`.
- Build-sequencing of #277 (S-7), #283 (S-4), and this capability — before, alongside, or as a shared
  schema unit → `/plan`.
- The S-4 team-execution external-wrapper context contract is an upstream prerequisite before R14's
  team-execution consumer is real (it is already a prerequisite for S-4).
- Mutating external workers — wait on the read-only sandbox (ideation R14). R11 is evidence-only until
  then (R21).
- Backfill of historical outputs — manifests begin at adoption; no retrofit.

**Outside this capability's identity:**

- A manifest "store," browser, or query UI — manifests live on existing carriers (D1), not a new
  database.
- Inline-Claude self-attestation — explicitly out (D5); inline Claude adjudicates (and attests the
  adjudication), it does not attest to its own primary work.
- A new gate of its own — R11 supplies evidence to gates that already exist or are scheduled; it does
  not add a gate (R12).

## Dependencies / Assumptions

- **S-7 (#277) and S-4 (#283) are proposals, not built code.** R11 defines the contract they will
  consume. Its v1 *live* consumers are the advisory ones (`/code-review`, `/qa`, `/retro`); the gate
  consumers (R13, R14) activate when those issues build. Build order is a `/plan` decision (D7).
- **The carrier must be cross-session and cross-worktree readable.** The git-common-dir outcome-store
  cache satisfies this (`outcome_store.py:93-148`) and is not a parallel store; a session-local file
  would break `/code-review` reading a manifest produced elsewhere. Whichever carrier `/plan` picks
  needs a typed key and reader contract (R19).
- **The expensive half is already paid where it is mandatory.** The claimed layer is near-free — the
  producing agent already knows what it read. Adjudication is mandatory only where the manifest feeds a
  gate (R9, R11), and saga already performs that verification today as prose (`/doc-review`,
  `/code-review`). R11 *structures* that work; it does not add a new verification pass where one is not
  already done. Advisory outputs carry lightweight metadata, so "every delegated output" does not blow
  up cost.
- **External attestation vocabularies are prior art, not a dependency.** in-toto attestations, SLSA
  provenance, and W3C PROV are established provenance schemas `/plan` may align the manifest to rather
  than rolling its own vocabulary. Flagged for `/plan`; not researched here.

## Outstanding Questions

No "resolve before planning" questions remain — the tagging-authority, enforcement, envelope-structure,
and adjudication-granularity spine are decided (D2, D3, D4, R9). The following are deferred to `/plan`:

- The exact manifest schema, the two subrecords' field names, and which carrier holds the envelope (R1,
  R19).
- The producer/consumer matrix's concrete code owners and read paths per field (R17).
- The defined gate-effect of each producer-claimed status, and whether the producer layer collapses to
  `verified | unverified` (R5).
- Build-sequencing of the three issues (#277 / #283 / this), including whether a shared schema unit
  lands first (D7).
- How `/retro` surfaces the parroting and disposition counts — new fields, or the existing
  `override_rate_reader` machinery (R7, R18).
- Whether to adopt an external attestation vocabulary (in-toto / SLSA / PROV) or define a saga-local
  schema.

## Sources / Research

**Existing provenance machinery (the substrate R11 extends):**

- `orchestration_downgrade` produce→persist→consume loop — *produced* in
  `plugins/saga/scripts/lifecycle_state.py:238-304`; *guarded/persisted* in
  `plugins/saga/scripts/saga.py:630-687`; *consumed* in
  `plugins/saga/scripts/override_rate_reader.py:74,137,215`; surfaced in
  `plugins/saga/skills/retro/SKILL.md:199` and `plugins/saga/skills/work/SKILL.md:256,262`.
- `validator-evidence-state` (closest existing manifest) —
  `plugins/team-execution/skills/team-execution/references/validator-evidence-state.md`.
- `Unit.returns` declared-output contract — `plugins/saga/scripts/execution_spec.py:180,536-537`.
- Carrier candidates — git-common-dir cache `plugins/saga/scripts/outcome_store.py:93-148`;
  `CompletionEvent.payload` open dict `plugins/saga/scripts/outcome_store.py:252-296`.
- Per-output cost-record precedent — `plugins/saga/scripts/outcome_costs.py:44-85,153-160`.
- Unknown-key preservation (forward-compat round-trip; the mechanism by which an unread field would
  persist silently) — `plugins/saga/references/saga-spec.md:274-278`.

**Claim-tag precedents (all prose or scoped today):**

- `/investigate` `verified`/`assumed` — `plugins/saga/skills/investigate/SKILL.md:57-61`.
- `/code-review` `DONE/PARTIAL/NOT-DONE/CHANGED/UNVERIFIABLE` —
  `plugins/saga/skills/code-review/references/built-vs-planned.md:49-81`.
- `/doc-review` cite-or-flag — `plugins/saga/skills/doc-review/SKILL.md:83-94`.

**Motivating evidence and consumer map:**

- Parroting finding (Rationale block, not a standing decision) — `docs/engineering-journal/DECISIONS.md:290`.
- Saga consumer map (writers vs read-only) — `plugins/saga/references/saga-spec.md:481-488`.

**Upstream issues this unifies (both proposals, not built):**

- S-7 #277 — `docs/brainstorms/2026-06-27-silent-omission-completeness-gate-requirements.md` (its
  opportunistic, contract-optional boundary at `:104-105`).
- S-4 #283 — `docs/brainstorms/2026-06-27-external-engine-capability-routing-requirements.md` (names R11
  as the audit-trail owner; team-execution wrapper prerequisite at `:323-327`).

**Ideation origin:** `docs/ideation/2026-06-26-vecu-port-seeds-ideation.md` (survivor R11).

**External prior art (for `/plan` schema alignment):** in-toto attestation framework, SLSA provenance,
W3C PROV.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: docs/brainstorms/2026-06-28-evidence-provenance-manifests-requirements.md
- Source type: brainstorm
- Source title: Evidence / Provenance Manifests

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/285
- Number: 285
- Created at: 2026-06-28T05:16:53.775630+00:00

