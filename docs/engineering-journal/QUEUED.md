# Queued — Infiquetra Claude Plugins

> **Future-work items by priority with explicit "worth it when" triggers.** When a promising idea surfaces but we don't build it right now, it goes here. Don't skip the entry just because it feels minor — undocumented good ideas decay into forgotten good ideas.
>
> **Format** (organized by priority section, no date headers — items are durable until they ship or get rejected):
>
> ```markdown
> ### Short title  {#slug}
>
> **Priority.** P0 (must-ship-before-X) / P1 (urgent) / P2 (important) / P3 (nice-to-have) / Maybe.
> **Effort.** Rough estimate (hours / half-day / day / week / multi-day).
> **Worth it when.** Specific trigger that would make this pressing.
> **Context.** What surfaced this; cross-references.
> ```
>
> When a queued item ships, move the entry to [ARCHIVE.md](ARCHIVE.md) as SHIPPED with the commit hash. When rejected, move with REJECTED + reason.

---

## Initiative — infiquetra-lifecycle engine merge (gstack + CE → infiquetra)

> **What this is.** `infiquetra-lifecycle` was built as a thin facilitative reskin of two source arts — **compound-engineering (CE)** and **[gstack](https://github.com/garrytan/gstack)** — and dropped most of their engines. Only `/ideate`, `/brainstorm`, and `/doc-review` carry real engines today; `/ideate` was the first rebuild (shipped 0.3.0). This initiative rebuilds the rest by **merging the best of CE and gstack into a new infiquetra engine we own and evolve** (Jeff: "otherwise I would just use one or the other and forget about all this"). Neither source has priority — Jeff leans CE. See DECISIONS [#lifecycle-engine-merge-campaign](DECISIONS.md#lifecycle-engine-merge-campaign) and LEARNINGS [#lifecycle-thin-reskin-systemic](LEARNINGS.md#lifecycle-thin-reskin-systemic).
>
> **Port model (the `/ideate` model).** Self-contained — **not** vendoring gstack, **not** a runtime dep on CE. Extract the engine, adapt to infiquetra (1-human + multi-agent team; SDLC owned by `sdlc-manager`; deploy by `infiquetra-deploy`; the journal; context-libraries), and **shed gstack's ~780-line runtime boilerplate — with Jeff's per-item sign-off** (each entry's *Shed* field lists candidates).
>
> **Process.** Each item is worked 1-by-1 as an **interview-driven merge**: lay out how the gstack and CE engines actually work, settle the merge via the *Interview* questions, then build. **Both foundations have shipped AND are now both consumed** — the saga primitive (P0, **SHIPPED** 0.4.0 as an engine + spec; schema in DECISIONS [#saga-schema-foundation](DECISIONS.md#saga-schema-foundation), ship record in ARCHIVE [#saga-foundation-shipped](ARCHIVE.md#saga-foundation-shipped); now consumed by `/plan` + `/code-review` + `/work` as primary writer) and the operator-choice framework (P1, **SHIPPED** 0.5.0 as a doc-only decision contract; schema in DECISIONS [#operator-choice-framework](DECISIONS.md#operator-choice-framework), ship record in ARCHIVE [#operator-choice-framework-shipped](ARCHIVE.md#operator-choice-framework-shipped); its **deferred CLI helper `recommend_execution_backend()` SHIPPED in 0.10.0 with the `/work` rebuild — closing the operator-choice deferral**) — so the command rebuilds now read both. **Command rebuilds shipped so far: `/office-hours` — SHIPPED 0.6.0** (faithful two-mode gstack port + infiquetra adaptations; schema in DECISIONS [#office-hours-engine-rebuild](DECISIONS.md#office-hours-engine-rebuild), ship record in ARCHIVE [#office-hours-engine-rebuild-shipped](ARCHIVE.md#office-hours-engine-rebuild-shipped)); **`/plan` — SHIPPED 0.7.0** (CE `ce-plan` artifact engine + gstack `spec` HOW-interrogation; schema in DECISIONS [#plan-engine-rebuild](DECISIONS.md#plan-engine-rebuild), ship record in ARCHIVE [#plan-engine-rebuild-shipped](ARCHIVE.md#plan-engine-rebuild-shipped)); **`/code-review` — SHIPPED 0.8.0** (CE `ce-code-review` findings/validator/judgment-lens spine + gstack `/review` scope-drift + plan-completion audit; saga's first review-track consumer, gate-only; schema in DECISIONS [#code-review-engine-rebuild](DECISIONS.md#code-review-engine-rebuild), ship record in ARCHIVE [#code-review-engine-rebuild-shipped](ARCHIVE.md#code-review-engine-rebuild-shipped)); **`/founder-review` (alias `/ceo-review`) — SHIPPED 0.9.0** (PORT of gstack `plan-ceo-review` — 4 scope modes + 18 CEO patterns + 9 Prime Directives + adapted system audit + the sharpened CE `product-pulse` no-false-precision posture steal; the scope/ambition/direction review lens, review-only, closed-loop routing to `/doc-review` + `/code-review`, NO saga write; schema in DECISIONS [#founder-review-engine-rebuild](DECISIONS.md#founder-review-engine-rebuild), ship record in ARCHIVE [#founder-review-engine-rebuild-shipped](ARCHIVE.md#founder-review-engine-rebuild-shipped)); **`/work` — SHIPPED 0.10.0** (CE `ce-work` execution engine + gstack `ship`/`land-and-deploy` autonomy/readiness/staleness gates; saga's **primary writer** — mints + names the work-thread saga `/code-review` appends to; lands the deferred `recommend_execution_backend()` helper; PR-ready boundary + round-N PR continuation loop + hard review gate; schema in DECISIONS [#work-engine-rebuild](DECISIONS.md#work-engine-rebuild), ship record in ARCHIVE [#work-engine-rebuild-shipped](ARCHIVE.md#work-engine-rebuild-shipped)); **`/loop` — SHIPPED 0.11.0** (the campaign's **one NATIVE rebuild** — no upstream engine to port/merge: CE has no router, the gstack "dispatch table SKILL" the brief named is phantom, and gstack context-save/restore is the saga + the queued `/resume`'s engine; three modes Route/Drive/Resume; saga-resume wiring + per-decision operator-choice offer for `/loop`-owned work; also ships the additive `saga.py scan()` picker-field extension, closing **Defect 1** of the `#code-review-saga-scan-touchups` item (Defect 2 — the `/code-review` programmatic-mode append — remains queued); schema in DECISIONS [#loop-engine-rebuild](DECISIONS.md#loop-engine-rebuild), ship record in ARCHIVE [#loop-engine-rebuild-shipped](ARCHIVE.md#loop-engine-rebuild-shipped)); **`/resume` — SHIPPED 0.12.0** (the lifecycle's **heavy forensic reconstruction engine** + the unblocked heavy partner `/loop` deferred to it; a **real CE `ce-sessions` PORT** — verified TRUE + portable, the opposite of the `/loop` phantom; two tiers — Tier 1 saga-anchored all-ticks deep reconstruction [the NEW `saga.py read_ticks` all-ticks reader + PR archaeology + conflict reconciliation], Tier 2 FALLBACK-ONLY [no saga AND no resolvable issue] Claude-only `ce-sessions` port [discover → file-mediated skeleton extract → generic-agent synthesis, context-safe by construction]; drops the `[gstack-context]` trailer; routes via the shared `loop/references/dispatch-table.md`, no ping-pong; writes one git-ignored re-entry tick reusing the restored `saga_id`; schema in DECISIONS [#resume-engine-rebuild](DECISIONS.md#resume-engine-rebuild), ship record in ARCHIVE [#resume-engine-rebuild-shipped](ARCHIVE.md#resume-engine-rebuild-shipped)); **`/qa` — SHIPPED 0.13.0** (the **gate-only acceptance-evidence engine** — a real gstack `/qa`+`/qa-only` merge [adopting gstack's own report-only `/qa-only` model: tests, gathers evidence, assigns severity, derives a ship verdict, routes, NEVER fixes] + a CE `ce-debug` falsifiable-prediction graft; **severity-banded verdict + a PORTED deterministic 0-100 health score reported alongside it** — Q2 RE-OPENED to its final state: an interim review wrongly read gstack's score as "no formula" and briefly slated it dropped → zero new Python, but the formula **is real** (`scripts/resolvers/utility.ts:286-321`, the `{{QA_METHODOLOGY}}` macro), so Jeff PORTED it — gstack's deduction values verbatim (critical -25 / high -15 / medium -8 / low -3) + documented infiquetra 9-way ship-risk-class weights, re-normalized over the in-scope classes, baseline-delta; the score's inputs are LLM-assigned, so it is one signal and the severity-banded verdict is the gate; saga's **qa-track consumer** — lands the deferred `work`→`qa` `lifecycle_phase` advance, zero `saga.py` edits; merge-state failure routing [pre-merge→`/work`, post-merge→`/handoff`]; **one new script — `scripts/qa_health_score.py` (the ported scorer) + its oracle test**; schema in DECISIONS [#qa-engine-rebuild](DECISIONS.md#qa-engine-rebuild), ship record in ARCHIVE [#qa-engine-rebuild-shipped](ARCHIVE.md#qa-engine-rebuild-shipped)); **`/strategy` — SHIPPED 0.14.0** (the **interview-driven STRATEGY.md engine** — a faithful single-source CE `ce-strategy` PORT, not a merge: gstack has no strategy engine [`cso` = Chief SECURITY Officer, the wrong officer]; Rumelt-grounded kernel + 8-section interview + mandatory 2-round pushback per section + a locked root-`STRATEGY.md` template; off-chain / pre-saga, NO saga write, records-vs-challenges complement to `/founder-review`; no new Python; schema in DECISIONS [#strategy-engine-rebuild](DECISIONS.md#strategy-engine-rebuild), ship record in ARCHIVE [#strategy-engine-rebuild-shipped](ARCHIVE.md#strategy-engine-rebuild-shipped)); **`/retro` — SHIPPED 0.15.0** (the **meta-improvement engine** — a real 3-source merge of gstack `retro` [forensics + stale-base/wrong-"today" BLOCK guard, scoped to the windowed mode] + gstack `learn` [the curation loop] + CE `ce-compound` [the compounding frame]; FULL engine in v1 — all 6 net-new passes [interview / transcript review / new-skill-or-plugin / refine-lifecycle-itself / refine-directives / memory-pruning] + a lean metrics snapshot; single `/retro` + optional pass arg; a **tiered self-edit gate** [pure-additive journal appends auto-apply; every delete/modify/move of existing durable state propose-diff-and-wait; an extra cross-project-impact warning before any global/cross-project edit incl. the antigravity directive class] over the **full** self-modification blast radius incl. the lifecycle SKILLs; **saga READ-ONLY — the dead-wiring `->retro` advance dropped, zero `saga.py` edits, NO `saga-spec.md §11` change**; **zero new Python** via reuse; schema in DECISIONS [#retro-engine-rebuild](DECISIONS.md#retro-engine-rebuild), ship record in ARCHIVE [#retro-engine-rebuild-shipped](ARCHIVE.md#retro-engine-rebuild-shipped)); **`/investigate` — SHIPPED 0.16.0** (the net-new **systematic-debugging engine** — a CE `ce-debug` causal-chain SPINE [falsifiable predictions for uncertain links, assumption audit, Phase-0 triage + trivial fast-path, parallel read-only sub-agent dispatch] + gstack `investigate` GRAFTS [pattern-signature table, two distinct numeric stop gates (hypothesis-exhaustion + 3-failed-fix), DEBUG REPORT Status enum] + a superpowers systematic-debugging borrow; **diagnosis-primary** — produces an agent-consumable DEBUG REPORT and routes the fix OUT [`/work` via `/handoff`, `/code-review`, `/handoff` for a trackable defect, `/brainstorm` for a design-level root cause], never fixes/commits/deploys; **saga READ-ONLY, off-chain** [advisory, never blocks `/loop`]; **zero new Python, zero `saga.py`/`handoff_envelope.py`/`saga-spec.md` edits**; the pre-decision "verification CALLS `/qa`" was **OVERRIDDEN to own-minimal verification** [a `/qa` back-call would create a routing cycle — `/qa` already routes INTO `/investigate`]; learning-capture BOTH-SPLIT [journal LEARNINGS + sdlc-manager defect]; **closes `/qa`'s deferred `/investigate` route at every site** [5 `/qa` mentions + 2 other-file notes]; schema in DECISIONS [#investigate-systematic-debugging-engine-rebuild](DECISIONS.md#investigate-systematic-debugging-engine-rebuild), ship record in ARCHIVE [#investigate-systematic-debugging-engine-shipped](ARCHIVE.md#investigate-systematic-debugging-engine-shipped)); **`/spec` — SHIPPED 0.17.0** (the net-new **spec-interrogation engine** — a gstack `spec` SINGLE-SOURCE WHAT-interrogation port, the WHAT-rigor sibling of `/plan`'s HOW-rigor; off-chain, saga-UNTOUCHED; schema in DECISIONS [#spec-interrogation-engine-rebuild](DECISIONS.md#spec-interrogation-engine-rebuild), ship record in ARCHIVE [#spec-interrogation-engine-shipped](ARCHIVE.md#spec-interrogation-engine-shipped)); **`/optimize` — SHIPPED 0.18.0** (the **metric-driven optimization engine** and the campaign CLOSER — a CE `ce-optimize` SINGLE-SOURCE port, NOT a merge [gstack `plan-tune` supplies nothing portable — a full-file grep for the agent-usability terms returned ZERO]; a bounded-experiment loop across 8 metric classes incl. the infiquetra-native agent-usability class; off-chain, saga-UNTOUCHED, zero new Python; schema in DECISIONS [#optimize-engine-rebuild](DECISIONS.md#optimize-engine-rebuild), ship record in ARCHIVE [#optimize-engine-rebuild-shipped](ARCHIVE.md#optimize-engine-rebuild-shipped)). **CAMPAIGN COMPLETE — all 13 command rebuilds shipped; the `#lifecycle-engine-merge-campaign` decision is CLOSED** (capstone in ARCHIVE [#lifecycle-engine-merge-campaign-complete](ARCHIVE.md#lifecycle-engine-merge-campaign-complete)). Scope: "complete" = the COMMAND-rebuild campaign; `/pulse` (continuous live telemetry, [#pulse-live-telemetry-component](#pulse-live-telemetry-component)) and other enhancements remain SEPARATE open queued items.
>
> **Provenance.** Briefs generated by the `lifecycle-engine-audit-queue` workflow (19 agents over gstack + CE + current stubs). Correction vs the pre-audit table: gstack `cso/` is **Chief SECURITY Officer**, not Strategy — `/strategy`'s engine source is **CE `ce-strategy` only**.

### Tracking — fleet-commons dependent survivors (build against fleet-core + vendored shim)  {#fleet-commons-dependents}

**Priority.** Tracking table, not a work item — each row lands with its own issue.
**Context.** Issue #463 settled the fleet-commons distribution mechanism (DECISIONS
[#fleet-commons-mechanism-463](DECISIONS.md#fleet-commons-mechanism-463)). The recorded
deterministic census there (survivor keyword query ∪ the 7 issue-named ids) enumerates the 28
ideation survivors that presuppose a shared-primitive home. **Every id below builds against
fleet-core + the vendored shim** — none should mint a new distribution mechanism or hand-copy a
primitive. Ids named in issue #463 itself are marked ★.

| Survivor id | Title (abridged) |
|---|---|
| `G-hybrids-10` | Portable consensus kernel: typed gated/advisory bit, worthiness entry gate, non-scoring external seat |
| `G-negative-space-3` | Name the import mechanism (this issue — shipped) |
| `H-F1-8` | Forbid contract mirrors: consumers exec the source-of-truth validator |
| `H-F2-5` | Producer-push contract propagation: source repo opens the refresh PRs |
| `H-F5-6` | Consumer-driven contract tests (Pact-style) for vocabulary propagation |
| `H-F6-8` | Marketplace as contract bus: distribute shared contracts as plugin surface |
| `T13-F4-1` ★ | Single shared concurrency-resolver primitive every fan-out site imports |
| `T13-F4-5` | Encode /optimize's serial=1 as a first-class exception in the cap registry |
| `T14-F1-4` | Vocabulary-rename campaign runner for lockstep cross-repo landings |
| `T14-F2-5` | Rename-campaign engine: token-pair driver replaces hand-grep landings |
| `T14-F5-2` | ATC positive handoff: no vocabulary term retired until consumers acknowledge |
| `T14-F5-6` | Aviation NOTAM broadcast: consumers subscribe to a contract, owner broadcasts |
| `T14-F6-2` | One canonical ref, N zero hand-mirrors: contract from a single pinned subtree |
| `T14-F6-5` | Manifest-driven autonomous rename campaign with all-green lockstep landing |
| `T15-F4-1` ★ | Fleet-shared delegation-receipt primitive (generalize agy's transcript auditor) |
| `T3-F1-1` | One canonical tier-palette module the whole fleet imports (shipped with #463) |
| `T3-F1-2` | Tier-resolution shim so single-agent plugins stop hardcoding model frontmatter |
| `T3-F4-1` ★ | Extract tier vocabulary into a shared importable primitive (shipped with #463) |
| `T3-F6-2` | Per-phase tier declaration blocks in the interactive judgment skills |
| `T4-F4-1` ★ | Shared run-posture primitive (`execution_posture.py`) every fan-out site imports |
| `T4-F5-6` | Intermodal container: segment+residency derivation as a shared primitive |
| `T5-F1-2` | Single-source the consensus threshold constants hand-copied into ~24 prompts |
| `T5-F2-6` | Collapse saga /code-review lenses + team-execution reviewers into one lens registry |
| `T5-F4-1` | Single consensus-contract source of truth both plugins conform to |
| `T5-F6-1` ★ | One consensus kernel: scoring contract as a single versioned spec |
| `T5-F6-4` | Plan-declared threshold profiles: per-outcome consensus stringency dial |
| `T6-F4-1` ★ | Shared reclamation-ledger primitive: register-on-spawn, idempotent reclaim_all |
| `T6-F4-3` ★ | Extract outcome_liveness into a fleet-shared heartbeat/stalled engine |

### P2 — Deferred `promote` hardening from the team-execution review  {#promote-review-hardening}

**Priority.** P2 (important; none blocks the initial ship). **Effort.** Half-day. **Category.** saga `promote`.
**Worth it when.** The `promote` pass runs against the real ~785-line / ~30-repo corpus and a false-merge or a dropped lesson actually surfaces — or before the frozen `promotion-contract.md` is unfrozen for any other reason.
**Context.** The four-reviewer team-execution pass on the transcendent-learnings PR confirmed and fixed the P1s (ledger-key injection, multi-entry upsert key duplication, empty-hash false cluster, write-guard containment). These remaining items were **deliberately deferred** because they would change the FROZEN contract (`plugins/saga/skills/promote/references/promotion-contract.md`, §2/§3) and re-key the golden vectors `87c4c366deb7` / `821928016ab6` that U1/U2 already depend on — a contract-unfreeze decision, not an in-PR change:
- **Normalization over-strips `_` and `` ` `` (contract §2 step 3).** `my_var` and `myvar`, or `` `code_path` `` and `codepath`, collide to one key → a possible false-merge of two genuinely different rules. The human gate + SKILL near-duplicate judgment mitigate, but the recipe is broader than "cosmetic." Revisit: strip `*`/`` ` `` and emphasis-role `_` only, not intra-word `_`. Re-freezes §2 and re-computes the golden vectors.
- **§3 parser scope (contract §3).** The regex matches the 7 enumerated legacy forms but not numbered-list bullets (`1. **Generalizable rule.**`), nested-paren labels, or space-before-colon (`rule :`). Each miss is a silently dropped lesson. Revisit: either broaden the regex (allow `\d+[.)]` bullets, tolerate one paren nesting level) or scope §3 explicitly to the enumerated forms. Add a real-corpus coverage assertion (parse the ~785 lines, assert match count within tolerance) instead of only 7 synthetic lines.
- **Re-key-on-edit (contract §2).** Editing a promoted rule's wording changes its content-addressed key, so `compute_upsert` returns `create` → a second entry for the same lesson. By design the SKILL's near-duplicate folding catches it; worth one explicit sentence in §2 + a SKILL Phase-2 note so the behavior is documented, not surprising.
- **Source-journal size cap (DoS).** `scan` now reads with `errors="replace"` (one bad file can't abort the run) but has no size cap; a multi-GB or `/dev/zero`-symlinked journal would exhaust memory. Add a `stat().st_size` guard that skips + `log`s oversized journals.
**Cross-ref.** The plan's AE3 prose (`docs/plans/2026-06-20-global-transcendent-learnings-plan.md:135`, "three `**Sources.**` lines") is stale vs the frozen contract §4 (one `**Sources.**` line, `; `-separated) — fixed in the same PR. LEARNINGS [[#work-mechanism-not-just-label]].

### P1 — Add a canary-verify / offer-revert capability to `infiquetra-deploy` (relocated from the `/work` rebuild)  {#infiquetra-deploy-canary-verify-revert}

**Priority.** P1 (when a prod deploy path exists). **Effort.** Medium (port gstack's canary-verify + offer-revert mechanics onto `infiquetra-deploy`'s tag-promotion model; ground on real prod health signals). **Category.** cross-plugin (relocation target).
**Worth it when.** A real prod deploy path exists with health signals to read. Today Infiquetra is pre-revenue greenfield with no live prod to canary; the capability has nothing to verify against.
**Relocation context.** The `/work` rebuild (DECISIONS [#work-engine-rebuild](DECISIONS.md#work-engine-rebuild)) merged gstack `ship`/`land-and-deploy`, whose engine includes **canary-verify + offer-revert on prod health failure**. That capability is on the **wrong side** of the lifecycle boundary for `/work` (deploy/canary is `infiquetra-deploy`'s hard boundary, saga-spec §1.1/§10), so it was **read-then-relocated** here rather than dropped silently — a deliberate brief deviation recorded in the `/work` ADR.
**Engine.** gstack `canary` (+ the canary/revert fragment of `ship`/`land-and-deploy`) IS the engine source — post-deploy health probe → verify → offer-revert on failure. Port it the campaign way (extract, adapt, shed; no vendoring/runtime dep), grounded on `infiquetra-deploy`'s tag-promotion + real prod health signals (not gstack's browse daemon).
**Boundary.** Lives in `infiquetra-deploy` (owns deploy mutation); `/work` + `/qa` route TO it, never own it. Surfaces evidence into the handoff envelope / issue progress via the existing channels.
**Context.** Cross-ref DECISIONS [#work-engine-rebuild](DECISIONS.md#work-engine-rebuild) (where it was relocated); QUEUED [#other-gstack-skills-triage](#other-gstack-skills-triage) (canary was already triaged ADOPT-as-own-item). Also overlaps the queued `/qa` ship-readiness gate.

### P3/Maybe — Port CE keyword/branch relevance ranking into `/resume` Tier 2  {#resume-session-relevance-ranking}

**Priority.** P3 / Maybe. **Effort.** Small (port CE `extract-metadata.py`'s keyword/branch relevance ranking into the Tier-2 candidate-discovery step; replace the recency-MVP sort). **Category.** engine-port (deferred slice of the `/resume` rebuild).
**Worth it when.** A no-saga Tier-2 forensic returns **>5 candidate sessions** and recency-only ranking mis-ranks — i.e. the most-relevant session is not the most-recent one and the operator has to scroll past noise. Until then recency-MVP is enough (the common path is Tier 1, saga-anchored; Tier 2 is the rare fallback).
**Today.** The `/resume` rebuild (0.12.0, DECISIONS [#resume-engine-rebuild](DECISIONS.md#resume-engine-rebuild)) ships Tier 2 with **recency-MVP ranking** — candidate sessions sorted newest-first, capped. CE `ce-sessions`' richer keyword + branch relevance scoring (`extract-metadata.py`) was deliberately deferred: it adds value only when candidate count is high enough that recency mis-ranks, which is not the common path for a same-machine cold resume.
**Engine.** CE `ce-sessions` `extract-metadata.py` IS the engine source — keyword-overlap + branch-match relevance scoring over the discovered candidate skeletons. Port it the campaign way (extract, adapt, shed; no vendoring/runtime dep), grounded on the file-mediated skeleton extraction Tier 2 already does (rank the skeletons, don't read the raw JSONL).
**Boundary.** A Tier-2-only enhancement — Tier 1 (saga all-ticks) does not rank candidates (it has the saga_id). Stays context-safe by ranking the already-extracted skeletons, never the multi-MB session files.
**Context.** Cross-ref DECISIONS [#resume-engine-rebuild](DECISIONS.md#resume-engine-rebuild) (Q1 — CE port staged behind Tier 1; ranking deferred as the rejected "port-keyword-ranking-now" alternative).

### P2 — `/code-review` programmatic-mode append contradiction (Defect 2 of the scan touch-ups)  {#code-review-saga-scan-touchups}

**Priority.** P2. **Effort.** Small (one `/code-review` SKILL mode-gate). **Category.** cross-skill defect (surfaced by the `/work` build review; **Defect 1 — the `saga.py scan()` match-key omission — SHIPPED** with the `/loop` rebuild, ARCHIVE [#code-review-saga-scan-touchups-shipped](ARCHIVE.md#code-review-saga-scan-touchups-shipped); this item is the **remaining Defect 2**).
**Worth it when.** The **standalone** `/code-review` review-track is actually exercised (human-run, not `/work`'s programmatic in-loop call). `/work`'s own gate does NOT depend on this (it reads the envelope directly), so it is not urgent.
**Defect 2 — `/code-review` programmatic-mode append contradiction.** code-review Phase 5.3 says programmatic/report-only mode writes ZERO files and the caller owns persistence, but Phase 5.4 unconditionally appends `--review-paths docs/code-reviews/<file>.md` to the saga — a path never created in that mode. Fix: mode-gate 5.4 to skip the append in programmatic mode (caller owns persistence), or have programmatic mode also write the durable artifact.
**Boundary.** This is a `/code-review` SKILL change — deliberately OUT of scope for the `/loop` rebuild (which touched no other skill). Fold into the next `/code-review` touch-up. Cross-ref DECISIONS [#code-review-engine-rebuild](DECISIONS.md#code-review-engine-rebuild), [#work-engine-rebuild](DECISIONS.md#work-engine-rebuild) (the forward-coupling residual), [#loop-engine-rebuild](DECISIONS.md#loop-engine-rebuild) (where Defect 1 shipped).

### P3 — `/loop` re-entry tick `--rounds-seen` placeholder crashes on multi-round values (latent, surfaced by the `/resume` build review)  {#loop-rounds-seen-placeholder-crash}

**Priority.** P3. **Effort.** Tiny (two markdown placeholder edits). **Category.** cross-skill latent defect (surfaced by the `/resume` build review; `/resume`'s own occurrence was fixed in 0.12.0).
**Worth it when.** Any operator copies `/loop`'s re-entry-tick `saga.py save` command verbatim with a multi-round value. `saga.py _split_int_list` splits on `|` only then `int()`s each part, so `--rounds-seen "1 2"` or `"1, 2"` raises `ValueError` → the save exits rc=1 and writes ZERO ticks (single-round `"1"` masks it).
**Defect.** `skills/loop/SKILL.md:271` emits `--rounds-seen "<observed round numbers>"` and `skills/loop/references/drive-and-resume.md:96` emits `--rounds-seen "<observed rounds>"` — both bare, no pipe hint. Fix: make the placeholder pipe-explicit, matching the `/work` precedent (`pr-continuation-loop.md` documents the pipe form) and the `/resume` 0.12.0 fix (`--rounds-seen "<observed rounds, pipe-separated; e.g. 1|2>"`).
**Boundary.** A `/loop` SKILL change — deliberately OUT of scope for the `/resume` rebuild (the plan marked `/loop` files verify-only; `/resume`'s own occurrence is already fixed). Fold into the next `/loop` touch-up. Cross-ref DECISIONS [#resume-engine-rebuild](DECISIONS.md#resume-engine-rebuild) (surfaced + fixed for `/resume`), [#loop-engine-rebuild](DECISIONS.md#loop-engine-rebuild).

### P2/P3 — Standalone `/pulse` live-product telemetry component (CE `product-pulse` as the engine source)  {#pulse-live-telemetry-component}

**Priority.** P2 if/when a live product ships with telemetry; P3 until then. **Effort.** Multi-day (a distinct lifecycle component — read-only analytics loop + metric-source wiring + the report artifact). **Category.** new-component (CE port).
**Worth it when.** A live Infiquetra product has **real telemetry** to read (usage/conversion/retention/cost signals). Infiquetra is currently **pre-revenue greenfield** — there is no product data yet, so a telemetry loop has nothing to report. Build it when "what is the product doing live?" becomes a real, repeatable question with data behind it.
**Today.** Does not exist. Surfaced by the `/founder-review` port (DECISIONS [#founder-review-engine-rebuild](DECISIONS.md#founder-review-engine-rebuild)): founder-review steals only the **sharpened no-false-precision posture** of CE `ce-product-pulse` (cite numbers, let the operator judge; no hardcoded thresholds), deliberately NOT the full telemetry artifact — because founder-review is qualitative and there is no live data. The full `product-pulse` engine is a separate job parked here.
**Engine.** CE `ce-product-pulse` IS the engine source — a read-only analytics/usage report that reads like a founder. Port it the campaign way (extract, adapt, shed; no vendoring/runtime dep) if greenlit.
**Boundary (the optimize-side is now SETTLED; the pulse-side is settled when `/pulse` is built).** `/pulse` = "what is the product doing live?" (a **continuous live-telemetry** read). `/optimize` (SHIPPED 0.18.0) is a **bounded experiment loop** — a target, a baseline, and a budget — that runs and stops. The `/optimize`-side boundary is settled by its decision (DECISIONS [#optimize-engine-rebuild](DECISIONS.md#optimize-engine-rebuild) decision e): `/optimize` is **bounded**, `/pulse` is **continuous**, and `/pulse` is **not a gate**. The remaining open question is the data-flow direction (does `/pulse`'s continuous telemetry **feed** `/optimize`'s next experiment target, or stand beside it?) — settle that when `/pulse` is greenlit, from the pulse side; `/optimize` does not need it. founder-review = "is this the right thing to build?" (qualitative, upstream); `/pulse` = "is the built thing working live?" (quantitative, downstream, continuous) — distinct jobs.
**Context.** Cross-ref `/optimize` (SHIPPED — DECISIONS [#optimize-engine-rebuild](DECISIONS.md#optimize-engine-rebuild), decision e settles the bounded-vs-continuous boundary from the optimize side) + `STRATEGY.md` metrics; DECISIONS [#founder-review-engine-rebuild](DECISIONS.md#founder-review-engine-rebuild) (Q1 — posture stolen, component queued).

### P3 — `/optimize` experiment-log helper: a tiny `optimize_log.py` append+verify (declined at build)  {#optimize-log-helper}

**Priority.** P3. **Effort.** Small (~half day: a tiny append-only writer + a read-back verify + an oracle test, mirroring `qa_health_score.py`'s shape). **Category.** engine touch-up.
**Worth it when.** The **prose-only experiment log** that `/optimize` keeps (baseline → hypotheses → per-experiment deltas → keep/discard decisions) **demonstrably drifts or corrupts across context compaction in real runs** — e.g. an experiment row gets dropped, a baseline number mutates, or the kept/discarded ledger goes inconsistent after a long session. Until that is observed, the prose log is sufficient.
**Today.** `/optimize` (SHIPPED 0.18.0) records its run **narratively** with **ZERO new Python** — a deliberate build decision (the helper was declined at build; the engine is SKILL-resident, saga-untouched). The risk being parked: a long optimization loop spanning multiple compactions could lose or mutate prose log state with no structural guard.
**Fix (if greenlit).** A small `scripts/optimize_log.py`: an append-only writer for experiment records + a read-back verify that the appended row round-trips (catch silent truncation/corruption), plus an oracle test — same minimal-script discipline as the ported `qa_health_score.py`. Keep it OFF the saga (the run stays off-chain); the helper guards the prose log's integrity, it does not add a saga track.
**Context.** Surfaced by the `/optimize` rebuild — DECISIONS [#optimize-engine-rebuild](DECISIONS.md#optimize-engine-rebuild) (Q2 ZERO-new-Python + the revisit-when condition), ARCHIVE [#optimize-engine-rebuild-shipped](ARCHIVE.md#optimize-engine-rebuild-shipped). The minimal-script precedent — `/qa`'s `qa_health_score.py` (DECISIONS [#qa-engine-rebuild](DECISIONS.md#qa-engine-rebuild)).

### P2 — `/doc-review`: confirm healthy + add the workflows/team-execution operator-choice (KEEP LIGHT)  {#doc-review-confirm-healthy-operator-choice}

**Priority.** P2 (confirm-healthy — the one CE port that carried its engine). **Effort.** Small (1-2h: one operator-choice block + optional headless flag; larger only if adopting CE parallel-lens dispatch). **Category.** confirm-healthy.
**Worth it when.** doc-review starts feeding `/work` or `/loop` programmatically (headless), or a reviewed doc routinely fans into multi-stream work needing an orchestration handoff.
**Today.** Single-pass self-driven readiness review (178L): CE classification taxonomy + SDLC routing (blueprint/spec/issue-review), readiness-skeptic lenses, safe-fix tiers, P0-P3 findings, durable `docs/reviews/` artifacts, `/work` blocking on unresolved P0/P1. Healthy and well-routed.
**Engines.** *CE* `ce-doc-review` = multi-persona PARALLEL reviewer fan-out (coherence + feasibility always-on; conditional product/design/security/scope/adversarial) + a 4-option finding interaction + headless mode. *gstack* — N/A (no gstack doc-review in scope).
**Merge.** Confirm healthy as-is. Optionally steal two CE mechanics if cheap: headless mode (lets `/work`/`/loop` call doc-review programmatically) and parallel-lens dispatch for large/high-stakes docs. Drop CE's heavy 4-option interaction (infiquetra's safe-fix + findings + override already covers it). **Primary ask: add the workflows operator-choice.**
**Infiquetra.** Lifecycle owns readiness review + the handoff envelope; sdlc-manager owns issues/boards/readiness. Findings/artifacts agent-consumable (headless); durable review artifacts feed the journal.
**Operator choice.** Add a single operator-choice after findings: when remaining work is large/parallel/risky, offer team-execution vs CC workflows/ultracode vs proceed solo (mirror ideate/founder-review phrasing).
**Shed (sign-off).** CE's AskUserQuestion-preload rules, headless plumbing, multi-platform subagent-primitive notes — unless headless/parallel-lens is adopted.
**Interview (1-by-1).**
- Just add the operator-choice and leave doc-review as-is, or also steal CE's parallel-lens dispatch + headless mode?
- Operator-choice fire only on large/risky docs, or always after findings?
- Offer all three backends, or just workflows + solo to keep it light?
- Does `/work` need a headless doc-review call, or is same-session/artifact handoff enough?

### P2 — Triage the remaining gstack skills (no lifecycle equivalent): adopt/fold/skip  {#other-gstack-skills-triage}

**Priority.** P2. **Effort.** ~30-45 min triage call; promoted skills (canary, autoplan) then become their own queue items. **Category.** missing-candidate.
**Worth it when.** The core merges (ideate/plan/work/review) are settled and Jeff wants to close lifecycle coverage gaps.
**Today.** No lifecycle equivalent for 10 leftover gstack skills.
**Triage verdicts.** `health` = FOLD into `/qa` or `/code-review` (quality dashboard). `learn` = FOLD into `/retro` + journal. `autoplan` = FOLD into `/loop` (or rebuild as a CC workflow pipeline — own item). `pair-agent` = SKIP (browser pairing). `freeze`/`guard` = SKIP / route to team-execution (edit-scope + destructive-command safety). `canary` = **ADOPT** as its own item (post-deploy monitoring). `skillify` = SKIP (browser-scrape). `document-generate`/`document-release` = SKIP/FOLD (docs-generator owns).
**Infiquetra.** Most overlaps are already owned (docs-generator, engineering-journal, infiquetra-deploy, team-execution, sdlc-manager). Lifecycle should only absorb engines that fit the idea-to-deploy loop (canary post-deploy verify; autoplan review chaining).
**Operator choice.** canary post-deploy monitoring could be a CC workflow/ultracode loop; autoplan's sequential review maps onto `/loop` routing or a workflow.
**Shed (sign-off).** For any adopted skill, shed the entire gstack preamble; keep only the engine. canary/skillify depend on gstack's browse daemon → re-ground canary on installed browser/qa tooling, don't vendor.
**Interview (1-by-1).**
- canary: promote to its own queue item (post-deploy monitoring) — in lifecycle `/qa` or paired with infiquetra-deploy?
- autoplan: fold its sequential auto-review into `/loop`, or rebuild as a CC workflow/ultracode pipeline (own item)?
- freeze/guard: confirm SKIP (team-execution owns edit-scoping + destructive-command safety)?
- document-generate/release: confirm these stay with docs-generator, lifecycle only triggering via `/handoff` or `/retro`?

### P3 — `/handoff`: confirm the 0.3.0 build matches intent (boundary, envelope flags, maturity)  {#handoff-confirm-healthy}

**Priority.** P3 (confirm-as-intended — just built). **Effort.** Small (~30-60 min if drift needs fixing; near-zero if Jeff signs off). **Category.** confirm-healthy.
**Worth it when.** A real handoff drops context fields, or a recipient without the plugin gets a non-self-contained issue.
**Today.** SKILL (68L) + `handoff_envelope.py` (165L) build a thin JSON envelope (source, inferred phase/maturity, reason/blockers/open-questions, target team/repo, suggested `/create-issue --prepare`, ownership keys) → sdlc-manager. Matches the documented boundary cleanly.
**Engines.** N/A — infiquetra-native exit point; the keep-worthy mechanic is the deterministic envelope script stamping `lifecycle_owner`/`issue_artifact_owner` so the boundary is machine-enforced.
**Merge.** No merge — a healthy build to confirm. Close three small drifts (below).
**Infiquetra.** Boundary correctly honored (lifecycle owns the handoff moment; sdlc-manager owns issue body/readiness/labels/board/mutation per [#sdlc-handoff-ownership-boundary](DECISIONS.md#sdlc-handoff-ownership-boundary)).
**Shed (sign-off).** `handoff_envelope.py` docstring still says "Infiquetra loop" (pre-rename) → "lifecycle."
**Interview (1-by-1).**
- The SKILL example omits `--reason`/`--blockers`/`--open-questions`/`--issue-type` — should the skill prompt for and pass these, or are they intentionally optional? (Risk: the LLM never populates the context fields.)
- `deferred-context` maturity appears only in prose with no code path (script falls back to `requirements-ready`) — should `infer_maturity` handle it, or does the LLM own that override?
- Want the docstring rename + a quick validation that the envelope schema is what sdlc-manager `/create-issue --prepare` actually consumes?
- Should the envelope ever emit a team-execution hint when blockers/parallelism are present, or keep it strictly thin?

### Maybe — gstack `/design-review` + `/design-consultation` (visual/UI engines): keep or skip  {#design-review-consultation-keep-skip}

**Priority.** Maybe (recommend SKIP now — explicit scope decision, not a rebuild). **Effort.** Decision: trivial (15 min). Full port if triggered: large (browser binary + mockup tooling). **Category.** missing-candidate.
**Worth it when.** Infiquetra ships a user-facing web/iOS UI (dashboard, portal, marketing site) needing visual-quality gating or a design system.
**Today.** No design/visual command. No equivalent exists.
**Engines.** *gstack* `design-review` = live-site visual audit→fix→verify (CDP browser, screenshots, computed-style extraction, severity grading vs DESIGN.md, regression baseline); `design-consultation` = conversational design-system builder (competitive research, AI mockups, writes DESIGN.md). *CE* — none.
**Merge.** Recommend SKIP — both presume a rendered web UI, CDP browser, and AI-mockup tooling infiquetra has no use for (serverless/AWS, agent-team, no heavy UI surface). Drop until a real frontend exists.
**Infiquetra.** If ever built: DESIGN.md baseline + severity findings could feed a `/qa` visual sub-check; otherwise leave as this stub only.
**Interview (1-by-1).**
- Confirm SKIP — any web/iOS UI on the near-term roadmap needing visual review?
- If ever wanted, should design checks live inside `/qa` or as a standalone `/design` command?
- Is a lightweight text-only DESIGN.md (tokens/conventions for agents) worth keeping even without the browser engine?

---

## P1 — urgent

### `/ideate` + `/brainstorm` over-fire scope-shrink / measure-before-build on already-converged solo handoffs  {#ideate-brainstorm-do-less-bias}

**Priority.** P1.

**Effort.** Half-day. SKILL.md edits to `brainstorm` (Phase 0/1/2) + `ideate` convergence; no code.

> **Worth it when.** Now — it misfired live this session (S-1 cache-scheduling brainstorm) and the operator flagged it as a recurring cross-session pattern. Fix before the next `/ideate` or `/brainstorm` run.

**Context.** The two engines lean systematically toward "get the operator to do less," which backfires for a solo operator who has *already* converged. Concretely:

- **brainstorm's attachment-gap probe** ("smallest version that proves the bet, what's excluded?") + Phase 2 "prefer simpler solutions" + the *optional* higher-upside challenger (simpler is the default, bigger is the opt-in) all push toward **smaller scope by default**.
- When the topic arrives as a **build-first `/ideate` survivor the operator already promoted** (and already killed the defer/measure framing upstream), re-firing those probes **re-litigates a settled decision**. This session: I reopened S-1's settled scope and recommended the smallest slice with "let usage tell you if you need more" — which the operator rejected hard.
- That "smallest-slice-then-expand / let usage tell you" framing is **structurally identical to measurement-first-ROI** for a solo tool where the operator IS the measurement loop — the exact ceremony killed as ideation S-6 and recorded in the `no-roi-ceremony-solo-tools` memory. The skills don't encode that exception.
- `/ideate`'s second-opinion + convergence stages also lean cut/rework/defer, compounding the shrink in the handoff.

**Fix direction:**
1. **Respect upstream convergence.** In brainstorm Phase 0/1, when the handoff is a build-first survivor with operator scope already set, **suppress the attachment/smallest-version + simpler-bias probes** and default to HOW-capture, not WHAT-re-litigation. Reopen scope only if the operator invites it or grounding reveals genuine infeasibility (e.g. this session's R15a context-GC = unbuildable).
2. **Encode the solo-operator exception** in both skills: never propose measure-before-build / smallest-slice-then-expand / ROI-threshold framing for single-operator tooling; the operator + `/retro` is the measurement loop. Cross-ref the `no-roi-ceremony-solo-tools` memory.
3. **Make the challenger symmetric.** The "higher-upside challenger" should surface a *do-the-whole-valuable-thing* option as readily as a *simpler* one — the bias is currently one-directional.
- Cross-ref: [LEARNINGS.md](LEARNINGS.md) no-ROI-ceremony pattern; [#ideate-brainstorm-handoff-symmetry](#ideate-brainstorm-handoff-symmetry) (related handoff-contract item); ideation S-1 build-first in `docs/ideation/2026-06-26-vecu-port-seeds-ideation.md`.

---

### CI guard: assert plugin directories match marketplace.json entries  {#marketplace-ci-guard}

**Priority.** P1.

**Effort.** Half-day. GitHub Actions workflow + a small Python script (~30 lines).

**Worth it when.** Right now — the bug it prevents has shipped twice in a row (PRs #110, #111) and required a third PR (#112) to fix. The class of bug ("file A and file B must stay in sync but reviewers don't notice the absence in B") will recur with every new plugin or rename.

**Context.**
- See [LEARNINGS.md](LEARNINGS.md#marketplace-drift) for the bug's history + mechanism.
- Spec sketch:
  - Walk `plugins/*/` directories that contain `.claude-plugin/plugin.json`.
  - Read `.claude-plugin/marketplace.json`.
  - Assert: `set(plugin dir names) == set(p["name"] for p in marketplace["plugins"])`.
  - Optional v2: assert each entry's `source: ./plugins/<name>` resolves and the entry's `version` equals the plugin's own `plugin.json` version.
- Run on every push + PR via `.github/workflows/marketplace-consistency.yml`.
- Should also run on `main` post-merge so a slip is caught immediately rather than at next-PR time.

---

## P2 — important

### `execution_spec` emitter: verifiers must see unit output, and UNDER-STRENGTH panels must fail the run  {#execution-spec-verifier-visibility}

**Priority.** P2 (P1 the moment another ultracode run relies on refute-N for its assurance story).

**Effort.** Half-day (`execution_spec.py` panel emission + quorum handling + regression test with a
deliberately uncommitted-tree fixture).

**Worth it when.** Any next `cc-workflows-ultracode` run — on the first real run (#387+#383,
`wf_6f7f3de8-926`) all three refute-3 panels computed their verdict over 0/3 verifiers and the run
still returned success. See LEARNINGS `{#verify-panels-blind-to-uncommitted-tree}`.

**Context.** Verifiers spawn with `isolation: worktree`, cut from the DEFAULT branch (main) — not
the driving session's branch — so panels verify a tree with no implementation in it: uncommitted
worker output is always invisible, and committed branch work is too unless the verifier manually
materializes the target commit. Three fixes, all needed: (1) give verifiers sight of the unit's
output — the emitter injects the unit's diff/result AND the target commit sha + a mandatory
materialization step (`git checkout <sha> -- .`) into the verifier prompt; (2) treat a panel below
its quorum floor as a workflow failure (throw/halt), not a `log()` line — a vacuous pass is
indistinguishable from a real pass in the return value today; (3) a verifier verdict must carry
the sha it actually examined, so a false kill against the wrong revision is detectable
mechanically (two of nine verifiers on `wf_5afd99b3-636` confidently refuted main's code).

### `execution_spec` emitter: spec-level concurrency cap replacing serialize-by-construction  {#execution-spec-concurrency-cap}

**Priority.** P2.

**Effort.** Half-day to a day (`execution_spec.py` emitter change + regression tests for the
existing serial-by-construction call sites).

**Worth it when.** The next time an operator needs deliberate bounded parallelism above what
today's ad hoc serial emission allows — flagged now off the 2026-07-04 operator rate-limit
incident (concurrency-and-spend-discipline memory: "no launches without a go; concurrency 3 hard
default"), before another spend incident forces it.

**Context.** Today the `execution_spec` emitter avoids concurrency problems by serializing at
construction time — the spec simply never asks for more than one runner at once for a given
fan-out, rather than declaring a cap the runtime enforces. That works but has no explicit
ceiling: nothing in the spec schema stops a future emitter change from fanning out unbounded.
Proposed direction: add a spec-level `concurrency` field (e.g. `{default: 3, cheap: 6}`,
mirroring the operator's standing hard default of 3 concurrent launches, with a higher ceiling for
demonstrably cheap/low-risk units) that the emitter honors as a bounded pool rather than a serial
queue — same operator-facing ceiling, but expressed as policy the spec carries instead of an
emission-order accident. Needs: where the field lives in the spec schema (top-level vs
per-workflow), how it composes with the existing tier/backend ladder, and a regression test
proving the default (3) reproduces today's de facto serial behavior for every existing caller.

### `recommend_execution_backend`'s ultracode risk suppressor has no reachable escape hatch for large security-touching changes  {#ultracode-elevated-risk-suppressor-reachability}

**Priority.** P2.

**Effort.** Half-day (mostly threading a size-vs-risk interaction test through
`lifecycle_state.py`; the fix itself is likely a small branch-order or precedence change).

**Worth it when.** A real security-touching change at or above the file-count/phase-count
threshold needs `cc-workflows-ultracode`'s deterministic independent-verification shape and
currently cannot reach it — surfaced during the #387/#383 release-surface pass while reading
`recommend_execution_backend` (`plugins/saga/scripts/lifecycle_state.py:100-223`).

**Context.**
- `should_offer_team_execution`'s size trigger (`file_count` / `phase_count` thresholds) already
  ORs its way past the GATED-vs-ADVISORY consensus split — a big-enough change routes to
  `team-execution` regardless of whether consensus is gated. That is intentional per KTD/R7 (size
  alone earns the review-consensus + gates fit).
- Separately, `elevated_risk = (has_security or has_infra or deployment_sensitive) and
  has_code_surface` unconditionally suppresses the `ultracode` branch
  (`ultracode = (broad_independent_fanout or adversarial_confidence or advisory_consensus) and not
  elevated_risk`, `lifecycle_state.py:183-186`).
- Net effect: for a security-touching change with a real code surface at or above the size
  threshold, `team` already fires first (size alone), so the suppressor never gets exercised in
  that shape today — but for a security-touching change *below* the team-execution size
  threshold that still wants `ultracode`'s broad-fanout/adversarial-confidence verification, the
  suppressor unconditionally rules it out with no alternative path back to `ultracode`. The
  `alternatives` list still names `cc-workflows-ultracode` as reachable
  (`workflow_available`-gated) even when `elevated_risk` is what actually excluded it as the
  *recommendation* — so the operator sees it listed as an escalation option that the function's
  own logic will re-suppress if chosen via the same recommend path.
- **Fix direction (needs design, not just a flip):** decouple "does a gate exist for this risk
  class" from "should ultracode ever be an option here." One option: only suppress `ultracode`
  when `elevated_risk` AND no `team-execution` gate is actually reachable for that risk class
  (i.e., the suppressor should reflect *gate absence*, not *risk presence*) — today it conflates
  the two, exactly the framing in the task description ("size trigger ORs past the gated/advisory
  answer AND elevated_risk suppresses ultracode... revisit the suppressor so backend choice is
  decoupled from gate existence"). Needs a size-vs-risk interaction test matrix (below threshold +
  elevated risk + fanout signal) added to whatever test module owns
  `recommend_execution_backend` today before changing the branch.
- Cross-ref: `operator-choice.md` section 3 (GATED vs ADVISORY consensus split, precedence
  ordering); `plugins/saga/scripts/lifecycle_state.py:100-223`.

### Evaluate joined `doc-review` plus `blueprint-reviewer` review flow  {#doc-review-blueprint-unification}

**Priority.** P2.

**Effort.** Half-day to 1 day after v1 has real examples.

**Worth it when.** `/doc-review` and `blueprint-reviewer` are both being used on the same
formal SDLC artifacts often enough that the sequential handoff feels repetitive or findings
start duplicating each other.

**Context.**
- Shipped v1 keeps ownership clear: `blueprint-reviewer` owns formal rubric quality;
  `/doc-review` owns implementation-readiness skepticism.
- Revisit whether a unified review flow or shared artifact schema is better once there are
  real `docs/reviews/` examples to compare.

### Consider deterministic `doc-review` classification helper  {#doc-review-classifier}

**Priority.** P2.

**Effort.** Half-day.

**Worth it when.** Real `/doc-review` runs route the same kind of artifact differently across
sessions, or formal SDLC artifacts miss `blueprint-reviewer` delegation because instruction-only
classification is too variable.

**Context.**
- v1 uses explicit classification precedence and representative examples in the skill instead
  of a helper script.
- A future helper could return `blueprint`, `spec`, `issue`, `plan`, `requirements`, or
  `strategy-scope` from path and content-shape signals.

### Delegate agents plugin for Codex and Antigravity  {#delegate-agents-plugin}

**Priority.** P2.

**Effort.** Spike: half-day. Minimal plugin v1: 1-2 days.

**Worth it when.** We want `team-execution` reviewers/explorers, or other parallel agents, to run
through local Codex or Antigravity accounts instead of Claude Code subagents, especially for
independent read-only review, exploration, or implementation-plan critique.

**Context.**
- Ideation doc: [delegate-agent plugin feasibility](../ideation/2026-05-30-delegate-agent-plugin-ideation.md).
- Recommended path: create a separate `delegate-agents` plugin first, prove read-only Codex and
  Antigravity delegates with structured results, then add optional `team-execution` routing.
- Follow-up route analysis changed the spike shape: compare Codex `exec`, Codex App Server, and
  `codex mcp-server`; compare Antigravity CLI, SDK, and any documented Antigravity 2.0 app control
  surface.
- Do not start with write-capable coder agents. Coder delegation should wait for worktree or strict
  file-ownership mechanics plus explicit consent.
- **Proven prompt assets to fold in (2026-06-27).** The worker-cache `/doc-review` ran codex
  (`gpt-5.5` xhigh) + agy (Gemini 3.1 Pro High) as adversarial plan-critique generators — they caught a
  real P0 + 4 P1. The reusable bit is the prompt *structure*: adversarial staff-engineer role → forced
  first-line disagreement → `[P0|P1|P2|P3] | claim/gap | evidence(file:line) | fix` enumeration →
  explicit CHECK list → read-only / cite-everything. When this is built, genericize that into the
  delegate surface (and the saga `doc-review` skill) rather than re-deriving per run. Durable know-how
  already lives in memory `reference_gemini_prompting_best_practices.md` (Gemini-specific: structural
  adversarial role, disagreement-first, `thinking_level=high`, why "be brutally honest" fails) +
  `reference_codex_second_opinion.md` (the `codex exec -m gpt-5.5 … -s read-only` STDIN pattern); the
  method is narrated in `docs/reviews/2026-06-27-worker-model-cache-scheduling-review.md`. The concrete
  `agy_prompt.txt` / `codex_prompt.txt` were session-scratch and are ephemeral — the structure above is
  the keeper, not the throwaway copies. Pairs with the gated-generator posture in the vecu-port-seeds
  ideation (survivor #4, "Heterogeneous Engines as Gated Generators + Fault-Exclusion") — generators
  only, never verifiers-of-record, Claude verifies every finding against source.

### Phase 5 spawn primitive: tmux-wrapped foreground sessions (replaces `--bg` from current plan)  {#phase5-spawn-via-tmux}

**Priority.** P2. Blocks Phase 5 implementation but Phase 5 hasn't started yet.

**Effort.** ~Half-day. Add a `--tmux` mode (or equivalent) to `claude-channel` that runs `tmux new-session -d -s <session-name> 'claude-channel ...'` instead of execing claude directly. Update PROTOCOL.md launch contract. Update plan §5 to mandate this path.

**Worth it when.** Starting Phase 5 implementation. Right now we don't need it because the foreground path works for testing; Phase 5's Mimir LLM tools are when we actually need programmatic spawn.

**Context.**
- Phase 2.5 PROTOCOL.md launch contract currently documents `claude-channel --bg ...` for Phase 5 consumers. That doesn't work today — see [[cc-channels-bg-not-supported]] for the empirical finding (channel notifications don't surface in bg-dispatched processes because `--dangerously-load-development-channels` isn't in Claude Code's bg-carry-through flag set).
- tmux works: detached from user's terminal but foreground from claude's POV, gives a real PTY, has the dev flag in argv, channels work, can `tmux attach -t <name>` for inspection, can `tmux kill-session -t <name>` for cleanup.
- My v0.4.15 work (PR #148, later removed in v0.4.16 PR #149) had the right architecture, wrong reasoning. The actual reason tmux helps is keeping claude foreground from Claude Code's POV, not PTY allocation per se.
- When `--channels` graduates from research preview + Anthropic adds it to the carry-through flag set: revisit and possibly switch back to native `--bg`.

### Channels in bg sessions: file feature request with Anthropic  {#channels-in-bg-feature-request}

**Priority.** P2. Long-term cleanup; tmux workaround is fine for now.

**Effort.** ~1 hour. Write a clear issue/discussion against the Claude Code repo or research-preview channel-of-record.

**Worth it when.** Phase 5 has shipped with the tmux workaround and we've used it for a month. By then we'll know: how often the tmux dependency is annoying, what UX wishes the workaround papers over, whether Anthropic's docs on channels-in-bg have changed.

**Context.**
- Carry-through flags doc'd in agent-view: `--mcp-config`, `--strict-mcp-config`, `--settings`, `--add-dir`, `--plugin-dir`, `--fallback-model`, `/add-dir`-added dirs. Notably excludes `--dangerously-load-development-channels` and `--channels`.
- The MCP server's `claude/channel` capability declaration IS sufficient for the server side; the gap is purely on the client (claude process) side — it needs the explicit opt-in flag.
- Possible fix Anthropic could make: add `--channels` (and dev variant) to the carry-through set, OR add a `~/.claude/settings.json` key like `defaultChannels: ["plugin:redis-channel"]` that bg sessions read at startup.

### Discord button approval for permissions (redis-channel v2)  {#discord-button-approval}

**Priority.** P2.

**Effort.** Half-day to 1 day. Add an ephemeral DM with Allow/Deny buttons in `hermes-claude-code-router`'s permission handler, plus discord.py interaction handler + custom_id parsing + race-cancel with the voice path.

**Worth it when.** Audit logs from `~/.hermes/plugins/hermes_claude_code_router/audit.jsonl` show non-trivial false-positive rate on voice approvals (≥1/month with destructive impact), OR user reports voice approval failing reliably in their actual usage environment (noisy car etc).

**Context.**
- Deferred from `redis-channel` v1 per [voice-only-permission-approval](DECISIONS.md#voice-only-permission-approval).
- Reference pattern: official Anthropic Discord channel plugin (`server.ts:486-518`) already does Allow/Deny buttons in DMs for permission relay. We mirror that exact shape.
- v1 already speaks `{verdict, source}` in the verdict stream where `source` includes a slot for `"button"` — the protocol is forward-compatible. Just need to add the button code paths on the router side; CC plugin needs no changes.

### Proactive notifications: push session-needs-attention to user  {#proactive-notifications}

**Priority.** P2.

**Effort.** 1 day. Router-side: detect when a CC session has emitted a permission_request that's been pending >5s, OR has been idle but produced output ("long task done"), and proactively DM the user via Mimir without being asked. Needs subscription state ("user wants notifications for session X") and pub/sub plumbing on `cc-sessions:events:<name>`.

**Worth it when.** User reports missing approval prompts because they weren't actively listening — i.e., the v1 model ("you have to be in voice channel actively") breaks down for async workflows. Likely shows up first when user wants to start a long task and step away.

**Context.**
- Deferred from `redis-channel` v1; the v1 model assumes the user is actively engaged.
- Builds on the lifecycle events pub/sub channel already in protocol.
- See PROTOCOL.md "Lifecycle events" — `presence_ping` and `mode_change` are the existing event types; a new `attention_required` type would join them.

### Build the `plugins/engineering-journal/` plugin  {#engineering-journal-plugin}

**Priority.** P2.

**Effort.** Multi-day (1–2 days of focused work for v1, more for the polish + the SDLC-philosophy doc).

**Worth it when.** A second or third Infiquetra repo wants the journal pattern and the manual setup labor (4 template files + CLAUDE.md section) starts to feel repetitive. Right now we have two adopters (home-lab, this repo); the third will be the trigger.

**Context.**
- Decided in `infiquetra/home-lab/docs/engineering-journal/DECISIONS.md` entry dated 2026-05-01: a two-tier split where `infiquetra-sdlc/docs/philosophy/engineering-journal.md` holds the canonical "what + why" and a `plugins/engineering-journal/` plugin in *this* repo holds the operational tooling.
- Five sub-decisions already pinned in that entry: standalone plugin (not folded into `sdlc-manager`); router skill (`using-engineering-journal`), not always-on hook; embedded templates (offline-friendly); `/journal-init` command with `--upgrade` mode for non-canonical existing layouts; naming convention.
- Full design walkthrough lives in `home-lab/docs/engineering-journal/narratives/2026-05-01-engineering-journal-distribution-design.md`.
- This plan's adoption of the journal in `infiquetra-claude-plugins` is **not** the plugin — it's a hand-built journal for this repo's own meta-work. The plugin work is downstream and uses this repo + home-lab as proven references when it's built.

### Saga arc binds one repo only — let a saga carry multiple repo subplots  {#saga-multi-repo-arc}

**Priority.** P2 (important — core to the saga metaphor; today every cross-repo feature rides an out-of-band workaround). **Effort.** Multi-day (a `Saga` record schema change + a `/work` execution change + a back-compat path for existing single-`issue_ref` sagas). **Category.** saga-primitive / `/work` engine.

**The gap.** A saga is meant to be a long arc of many subplots, but the record binds exactly one repo. Verified: `Saga.issue_ref` is a single `owner/repo#N` (`plugins/saga/scripts/saga.py:154`; saga-spec §1 boundary table + frontmatter row, `plugins/saga/references/saga-spec.md:40,123`); `current_git_state(root)` reads one working tree (`saga.py:472-478`); `journal_entries(root, …)` reads one repo's `docs/engineering-journal/` (`saga.py:924-927`); `prior_prs(owner, repo, issue)` / `aggregate_context` track one repo's PRs (`saga.py:881`; saga-spec `:405`). `/work`'s PR-continuation loop is keyed to that single `issue_ref` — one branch / one PR per saga. So a feature that lands across repos cannot live under one arc.

**What is NOT the blocker.** Storage location already floats above repos: state is written at `root = Path.cwd()` under `.claude/saga/` (`saga.py:1126,44`), so the ledger can — and currently does — sit at the workspace root above every repo. The refactor is in the *record schema + execution*, not where the files live.

**The shape (when built).** Let one saga arc carry a SET of repo subplots — each subplot its own `issue_ref` / branch / PR / journal — so `/work` can open a branch+PR per repo under a single `saga_id`, in dependency order, with the arc tracking all of them. Needs: a subplots list on the record (back-compat: treat the existing scalar `issue_ref` as a subplot-of-one), per-subplot git/PR/journal resolution, and a `/work` loop that iterates subplots. Preserve the saga-spec §3.5 unknown-key round-trip and the §10 invariants.

**Worth it when.** Now-ish to design; the build-trigger is the first real multi-repo feature actually executed — the global transcendent-learnings build is that trigger (3 repos: `infiquetra-claude-plugins`, `infiquetra-context-library`, `infiquetra-sdlc`). Today's workaround (Option A: one workspace `/work` session opening one PR per repo in dependency order, coordinated by hand) ships that feature without the refactor but *proves* the gap — the cross-repo coordination lives in the operator's head and the plan's prose, not in the saga.

**Context.** Surfaced 2026-06-20 while planning the global transcendent-learnings build (`docs/plans/2026-06-20-global-transcendent-learnings-plan.md`, landing-surfaces / Option A note). Companion to the team-execution per-teammate work ([#team-execution-per-teammate-effort](#team-execution-per-teammate-effort)) — both are "the plan wants to drive richer per-repo / per-teammate execution than the current single-axis engine exposes." Cross-ref the lifecycle-engine-merge initiative (`/work` = DECISIONS [#work-engine-rebuild](DECISIONS.md#work-engine-rebuild)) and the saga spec (`plugins/saga/references/saga-spec.md`).


---

## P3 — nice-to-have

### Live-resolution spore regression test (real on-disk saga → both hooks)  {#spore-live-resolution-regression}

**Priority.** P3.
**Effort.** S (~1 hour — one integration test).
**Worth it when.** Before the next change to `resolve_active_saga` / the spore hooks, or if a spore
re-grounding ever silently no-ops in the field. `/qa` #281 ran this acceptance **by hand** (built a real
`issue-281` saga, drove both hooks as subprocesses, asserted the active `saga_id` in `additionalContext`);
`test_spore_seam_roundtrip.py` covers the *synthetic* seam but not the `state.json active_saga_id`
resolution path against a real on-disk saga. Codify the manual check so CI guards it.
**Context.** Surfaced in `docs/qa/qa-issue-281-2026-06-30.md` (Recommended regression tests) and
`docs/retros/issue-281-2026-06-30.md` F3.

### `override_rate_reader` counts an empty `orchestration_downgrade` as a downgrade  {#override-rate-reader-empty-downgrade}

**Priority.** P3.
**Effort.** XS (a truthiness check + a test).
**Worth it when.** Before R12 downgrade telemetry is used to drive any default re-weighting — an
empty-string false positive would inflate the "capability degradation" count. `/retro` #281 saw the reader
report "Sagas with a recorded orchestration downgrade: 1" for issue-281 while its `orchestration_downgrade`
note is `""`. Looks like a field-present vs field-non-empty check in `scripts/override_rate_reader.py`.
**Context.** `docs/retros/issue-281-2026-06-30.md` F4. Read-only telemetry, so low blast radius today.

### Demonstrate or relax R5 (no-hard-wrap soft-wrap) for generated saga docs  {#saga-doc-soft-wrap-r5}

**Priority.** P3.
**Effort.** S (a contract edit, or a lint + a regenerate pass).
**Worth it when.** A markdown viewer is observed to actually jumble a blank-line-separated, hard-wrapped saga doc, OR the no-hard-wrap-vs-repo-hard-wrap-habit tension becomes recurring friction. Then either enforce R5 (lint + regenerate the key docs no-hard-wrap) or relax it to blank-line-separation-only in `formatting-style.md`.
**Context.** `formatting-style.md` rule 5 prescribes no-hard-wrap for generated output, but generated docs still hard-wrap at ~100 chars; the jumbling problem is already solved by blank-line separation + tables. QA #201 flagged this as the one LOW deferred (F1); operator chose "leave as-is, opportunistic" at the 2026-06-07 retro. Refs: `docs/qa/qa-issue-201-2026-06-07.md`; DECISIONS {#saga-doc-formatting-contract}.

### Symmetric `/ideate` → `/brainstorm` handoff field contract  {#ideate-brainstorm-handoff-symmetry}

**Priority.** P3.

**Effort.** ~1 hour (tighten `/ideate` Phase 6.6 wording).

**Worth it when.** The `/ideate` → `/brainstorm` handoff starts dropping survivor context in practice
— e.g. a brainstorm opens missing the axis / basis / ideation-doc path it should have inherited.

**Context.** `/ideate` Phase 6.6 (`skills/ideate/references/convergence-and-partnership.md`) hands off
by loading `brainstorm/SKILL.md` "with the chosen idea as the seed" without enumerating which SURVIVOR
SCHEMA fields and the ideation-doc path travel. The brainstorm side is already robust (Phase 0.2 pulls
from the named SURVIVOR SCHEMA and asks once for the doc path if absent), so this is a symmetry/clarity
improvement, not a correctness bug. Surfaced by the rebuild's adversarial review (the brainstorm-side
mismatch was fixed; the producer side was left as-is). See DECISIONS
[#ce-ideation-engine-restore](DECISIONS.md#ce-ideation-engine-restore).

---

### `deploy-status` per_page lookback can miss old tag refs  {#deploy-status-perpage-cap}

**Priority.** P3.

**Effort.** ~1 hour.

**Worth it when.** A tag-promotion repo accrues more than 20 CI-auto `environment:`-key
Deployment records (branch/SHA refs) since its last real tag promotion. Then
`latest_deployment()` (which fetches `per_page=20` and filters to the newest tag-ref record)
scrolls the real tag off the page and reports "no deployment found".

**Context.**
- Introduced by the #161 fix (`query_deployments.py latest_deployment()`): GET + `is_tag_ref()`
  filtering on a single 20-record page.
- Current behavior degrades gracefully (no crash, just a missing env line).
- Fix options when triggered: paginate until a tag-ref is found or N pages exhausted, or use the
  `environment` filter combined with a larger page. See [LEARNINGS.md#gh-api-f-defaults-post](LEARNINGS.md#gh-api-f-defaults-post).

### ~~Plan-dictated per-teammate effort levels for `/work` + team-execution~~ — RESOLVED via `inject_effort()` seam (#363)  {#team-execution-per-teammate-effort}

**Resolved 2026-07-05** via the `inject_effort()` seam (#363, saga 0.63.0 / team-execution
2.11.0 / fleet-core 0.4.0), **not** the re-architect-onto-Workflow path this entry originally
assumed. `effort:` is now a real first-class frontmatter value (validated against
`fleet_commons.tier_palette.EFFORTS`, R1/R2), resolved through a three-layer cascade
(`team_emitter.resolve_teammate_effort`, R5, KTD4) and honored two ways: a **real** per-call knob
on the paths that already had one (Workflow/ultracode `agent({effort})`, external-engine offload —
unchanged, out of scope here) and a **labeled proxy** (`EFFORT_RIDER`, `fleet_commons.effort_rider`)
on the native Agent-tool teammate path, which has no real per-call effort knob (KTD1/KTD2). A
native subagent-effort knob remains a tracked residual follow-up — swapping the proxy for a real
call is a one-function change behind the same seam, not a re-architecture. See `plugins/saga`,
`plugins/team-execution`, and `plugins/fleet-core` CHANGELOGs (2026-07-05) and DECISIONS.md
KTD1–KTD7 for the full record.

### `/outcome graph` — render the DAG as an Artifact (visual board), not only Mermaid text  {#outcome-graph-artifact-render}

**Priority.** P3.
**Effort.** Small-to-medium (a new render path + an operator flag/default decision; the node data already exists in the spec). **Category.** saga `/outcome` operator-UX.
**Worth it when.** Now-ish — the trigger already fired: `/outcome graph` emits a Mermaid `flowchart` block that a **CLI operator cannot see rendered** (Jeff, 2026-07-05: "the chart isn't really visible in the CLI"). Any outcome past ~5 nodes makes the raw Mermaid hard to read in a terminal. The manual workaround this session was to hand-build an HTML Artifact of the `tier-effort-first-class` DAG; codify it so `graph` produces a viewable artifact directly.
**Today.** `outcome.py graph <id>` (the `graph` verb, `plugins/saga/skills/outcome/SKILL.md` thin-surface table) prints a Mermaid `flowchart TD` annotated with each node's derived-on-read live state (`ready`/`blocked`). Great for a Markdown viewer or the Mermaid MCP; opaque in a bare CLI. The data behind it — nodes, `depends_on` edges, derived state, backend, model/effort, `github` issue refs — is all in the committed spec, so an Artifact renderer needs no new state.
**Fix (when greenlit).** Add an Artifact/HTML render of the DAG — a 2-tier (or layered) dispatch board with per-node status lamps, backend + tier chips, clickable issue links, and dependency traces. Open question to settle at build: **artifact by default, or by choice** (e.g. `graph --artifact` / `graph --format=mermaid|artifact|both`, or a persisted operator preference). Keep the Mermaid path (it feeds the Mermaid MCP + Markdown surfaces); the artifact is an additional emitter, not a replacement. Consider the same treatment for `report`/`project` status cards (they already emit an operator-facing summary that would benefit from a visual surface). Reference implementation: the hand-built board at `scratchpad/outcome-dag.html` from the 2026-07-05 session (2-tier layout, SVG edges computed from node positions, light/dark themes, derived-on-read state encoded as lamps).
**Context.** Now that Claude Code Artifacts are available (self-contained hosted HTML), the CLI-invisible-Mermaid gap has a clean fix. Cross-ref `plugins/saga/skills/outcome/SKILL.md` (the `graph`/`report`/`project` verbs) and `plugins/saga/scripts/status_card.py` (`project_outcome`, the status-card emitter — the other candidate for a visual surface). Surfaced live while reviewing the `tier-effort-first-class` outcome DAG.
