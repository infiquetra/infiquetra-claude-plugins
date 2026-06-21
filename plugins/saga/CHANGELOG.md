# Changelog

## 0.24.0 - 2026-06-21

- Add `orchestration_recommended` and `orchestration_operator_choice` fields to the saga envelope
  (R12 — choice-vs-recommendation recording). Enables override-rate computation in `/retro`+`/optimize`.
  Both fields default to `""` so pre-0.24.0 sagas parse without error (backward-compatible additive
  evolution per §9 of the saga spec).
- Add `ORCHESTRATION_MODE_LABELS` display-label map to `saga.py` (`cc-workflows-ultracode` →
  "dynamic workflows", `team-execution` → "team execution", `inline` → "inline") and a
  `display_orchestration_mode()` helper that falls back to the raw enum string on a miss — never errors
  (R8 / KTD5).
- Route all offer-surface prose in `/plan`, `/work`, `/code-review`, `/loop`, `/founder-review`,
  `/optimize`, and `/retro` skills through the display labels so operators see "dynamic workflows"
  in descriptions while the stored enum string `cc-workflows-ultracode` remains the frozen wire
  contract (carried in persisted sagas and `--orchestration-mode` CLI choices, byte-for-byte unchanged).

## 0.23.0 - 2026-06-20

- Add the `/promote` skill — the workspace tier of the engineering journal. It promotes the *select few*
  cross-repo "transcendent" learnings into `infiquetra-context-library`'s `LEARNINGS.md` as distilled,
  pull-only org standards: a manual, gated, agent-judged pass with two feeders (the `/retro`-declared
  `**Transcendent.**` marker and a recurrence net over legacy `**Generalizable rule.**` lines). It mirrors
  `/ideate`'s cross-repo grounding, clusters the same lesson across repos by judgment (no vectors), and
  upserts ONE entry per lesson behind a propose-diff-and-wait gate. READ-ONLY on the SDLC; writes only to
  context-library; never writes back to source repos.
- Add `scripts/promote_scan.py` — the deterministic backbone: enumerate `*/docs/engineering-journal/
  LEARNINGS.md`, parse the marker + legacy-rule variants, compute the drift-stable `<repo>:<hash>` source
  key, read context-library's `promote-keys` ledger to drop already-promoted candidates, exclude
  context-library and self-feed entries (two layers), group exact-recurrence clusters, and render the
  idempotent gated upsert (create / update / noop). The marker form, key recipe, parser, entry template,
  and ledger are frozen in `skills/promote/references/promotion-contract.md` (the single source of truth).
- Teach `/retro`'s Phase-4 curation to propose the `**Transcendent.**` marker on the select cross-repo
  learnings (the single-repo, propose-diff-and-wait declare feeder).

## 0.22.1 - 2026-06-13

- Tighten the `adversarial_confidence` guidance: `/work` sets `--adversarial-confidence` only on an explicit
  operator request for many-independent-attempt verification (refute-N / judge-panel / perspective-diverse),
  never inferred from generic "make me more confident" phrasing — closes the oversell risk the adversarial
  review flagged. The trigger stays categorical; a true magnitude gate remains a documented revisit-when.
- Journal bookkeeping: record the 0.22.0 squash SHA (`331505a`).

## 0.22.0 - 2026-06-13

- Correct the execution-backend recommender (`recommend_execution_backend`) and the operator-choice contract
  so `cc-workflows-ultracode` (ultracode) is no longer framed as "fan-out, not review depth": ultracode
  delivers deterministic fan-out **and** independent/adversarial verification. The line to `team-execution`
  is GOVERNANCE (reviewer consensus + named scanner gates + guarded deploy), not review depth.
- Add `adversarial_confidence` as a second `cc-workflows-ultracode` trigger beside `broad_independent_fanout`
  (CLI `--adversarial-confidence`): prove-by-refutation / judge-panel work with no deploy/security signal now
  reaches ultracode instead of silently falling to `inline`.
- Add `has_code_surface` (default True; CLI `--no-code-surface`) so pure docs/spec/research output neutralizes
  the output-blind team-execution proxies — `file_count`, `phase_count`, and the `parse_issue.py` keyword
  flags `has_infra` / `has_security` / `deployment_sensitive` that fire on a doc merely *mentioning* infra or
  auth. `cross_repo` (ownership boundary) and `needs_consensus` (contested) survive as the output-agnostic
  governance signals; the ultracode risk-suppressor is itself gated by `has_code_surface` so broad infra/
  security DOCS still fan out.
- Reword operator-choice §3.1 (`PLUS` -> `OR`, matching the code's sufficient-on-its-own consensus) and §3.2
  (the corrected ultracode framing + the throwaway-signal-vs-standing-verdict mechanical boundary).

## 0.21.0 - 2026-06-09

- Add a comprehensive Saga documentation system: README atlas, manual pages under
  `plugins/saga/docs/`, curated source model, and generated SVG visual kit.
- Document every Saga command as a comparable decision card, including the 18 command-file /
  17 routable-command distinction and the `/ceo-review` -> `/founder-review` alias.
- Add dedicated lifecycle, state/readiness, scenario, boundary, and visual-maintenance pages.
- Add `plugins/saga/scripts/render_docs_visuals.py` to generate presentation-ready SVG assets from
  `plugins/saga/docs/model/saga-docs-model.yaml`.
- Add `tests/test_saga_docs_coverage.py` to guard command coverage, alias handling, derived
  readiness maturity, scenario coverage, manual links, source references, and visual inventory.

## 0.20.0 - 2026-06-07

- Add a shared formatting contract, `saga/references/formatting-style.md`, linked by all nine
  doc-writing skills (ideate, plan, brainstorm, spec, strategy, retro, doc-review, code-review,
  founder-review). It mandates scannable output: ≤3-sentence blank-line-separated paragraphs, a
  one-line summary opening each ranked item/section, comparative data as tables, the compact
  engineer-facing schema fields rendered as a table (narrative fields stay prose), no-hard-wrap
  soft-wrap for generated output, and dropping fields a heading already carries. (#201)
- Fix the triggering case: `ideate`'s `ideation-artifact.md` SURVIVOR SCHEMA no longer stacks
  bold-label lines (the CommonMark collapse that read as "all jumbled together") — it now leads with
  a one-line summary and renders the schema as a table.
- Enforce it: `tests/test_saga_doc_formatting.py` fails CI on a stacked-bold-label collapse and on
  any doc-writing skill that does not link the contract.

## 0.19.0 - 2026-06-05

- Rename the engine plugin to `saga` (Scheme Y plugin-family rename) and fold `blueprint-reviewer`
  into it. Metadata/marketplace change; no command behavior change. (#199)

## 0.18.0 - 2026-06-04

- Rebuild `/optimize` from a 20-line stub into a **metric-driven optimization engine** — the
  **thirteenth and final command rebuild** of the engine-merge campaign (after `/office-hours`,
  `/plan`, `/code-review`, `/founder-review`, `/work`, `/loop`, `/resume`, `/qa`, `/strategy`,
  `/retro`, `/investigate`, `/spec`). It runs a **bounded-experiment loop** toward a measurable
  target: pick a metric, baseline it, hypothesize, run a bounded experiment, measure the delta,
  keep or discard, repeat until the target is hit or the budget is spent.
- **Honest attribution — single source, no merge.** `/optimize` is a **CE `ce-optimize`
  single-source PORT**. The **agent-usability** metric class is an **infiquetra-native** angle
  (Jeff's), **NOT a gstack port** — a full-file grep of gstack `plan-tune` for the agent-usability
  terms returned **zero**; `plan-tune` is a developer-psychographic question-coach that supplies
  nothing portable and is not ported. This is **NOT a merge** of any kind, and gstack is credited
  with **no insight**.
- **Off-chain, saga UNTOUCHED.** `/optimize` writes no saga, advances no `lifecycle_phase`, and
  makes **no `saga.py` edit** (mirrors `/strategy` / `/spec`). **No new Python** — no
  `handoff_envelope.py` edit either; the `docs/optimize/` handoff source dir is deliberately
  **deferred**.
- **Eight metric classes (the maximal v1 taxonomy):** performance, cost, reliability,
  **agent-usability**, security, quality, developer-experience, maintainability.
- **OFFERS operator-choice** for independent experiment fan-out (default serial inline); the choice
  is recorded **narratively** (saga-untouched) — not via an `orchestration_mode` saga field.
- **Campaign-closer.** With `/optimize` shipped, **all 13 command rebuilds of the engine-merge
  campaign are complete.** (Scope: this closes the *command-rebuild* campaign; `/pulse` live
  telemetry and other enhancements remain separate, queued items.)
- **Periphery** — version bumps (plugin `0.18.0`, marketplace entry `0.18.0`; keywords stay at 10);
  dispatch-table `/optimize` row flipped stub → shipped (metric-loop engine, advisory + off-chain),
  routing-rubric row updated, plus a `/qa`-vs-`/optimize` boundary note (gate-to-ship vs
  loop-toward-target); `operator-choice.md` `/optimize` row "at its rebuild" → "now, offers";
  README `/optimize` command-summary line tightened to the bounded-experiment loop + 8 metric
  classes. Dispatch-table command count stays **17** (`/optimize` was already counted).
- Documented in the engineering journal (PR #197): DECISIONS `#optimize-engine-rebuild`, ARCHIVE
  `#optimize-engine-rebuild-shipped` + the campaign-complete capstone (closes
  `#lifecycle-engine-merge-campaign`), LEARNINGS `#shipped-on-origin-not-in-stale-local-tree` +
  the third firing of `#campaign-brief-merge-is-a-provenance-hypothesis`; consumed
  `#optimize-engine-merge` from QUEUED, added `#optimize-log-helper`.

## 0.17.0 - 2026-06-04

- Add `/spec` — the lifecycle's net-new **spec-interrogation engine** and the **twelfth command
  rebuild** of the engine-merge campaign (after `/office-hours`, `/plan`, `/code-review`,
  `/founder-review`, `/work`, `/loop`, `/resume`, `/qa`, `/strategy`, `/retro`, `/investigate`). It
  owns the relentless **WHAT-rigor** — the sibling of `/plan`'s HOW-rigor. A **gstack `spec`
  single-source port** of the WHAT-interrogation half: the principal-engineer-who-refuses-ambiguous-work
  persona, the HARD GATE (no spec after message 1 — always start the interview), Phase-1 five-Why,
  Phase-2 scope / MVP / out-of-scope / failure-mode lock, Phase-3 **read-code-first grounding** (cite
  `path:line` before asking, with a non-code escape), quantify-everything, and a draft-review pass.
- **Honest attribution — single source, no merge.** There is **NO CE spec engine** (ce-plan is
  `/plan`'s planning engine, not ported here), **NO /ideate+/brainstorm graft** (the
  assumption-challenge + failure-mode register is native to gstack's persona — the failure-mode bank
  already lives in `/plan/references/interrogation.md`, itself a gstack port), and no superpowers
  borrow. `/spec` and `/plan` split one source along the **WHAT vs HOW** altitude axis. The `/spec`
  SKILL does not duplicate `/plan`'s interrogation register. Sheds the entire gstack preamble,
  dedupe machinery, codex quality gate, two-layer redaction, `--execute` worktree spawn, gh issue
  authoring/filing, and the `~/.gstack` store.
- **Off-chain, saga UNTOUCHED.** `/spec` writes no saga, advances no `lifecycle_phase`, and makes no
  `saga.py` edit at all (mirrors `/strategy`). Its only durable output is a sharp WHAT artifact under
  `docs/specs/`. **No new Python.**
- **Q2 handoff wiring — the functional edit.** `handoff_envelope.py` now treats `docs/specs/` as an
  auto-discoverable handoff SOURCE: added `Path("docs/specs")` to `SOURCE_DIRS`, and
  `infer_maturity()` maps `docs/specs/` → `requirements-ready` (equals the existing default — a spec
  is a sharp WHAT, **not** plan-ready — set for consistency with the other source dirs, not a
  behavior change). `infer_lifecycle_phase()` leaves `docs/specs/` returning `"unknown"` (off-chain,
  no lifecycle phase). `references/saga-spec.md` §3.3 and `skills/handoff/SKILL.md` document the
  `docs/specs/ → requirements-ready` doc-path mapping; no `spec` phase is added to `LIFECYCLE_PHASES`.
- **Q4 + operator-choice honesty.** An offered `/doc-review` pass on a spec hits the **requirements**
  lens (`docs/specs/ → requirements` path tie-breaker added), not the blueprint route.
  Operator-choice **never offers** for `/spec` — a single durable spec artifact, no parallelism to
  escalate; size/risk lives in its scope sections and the downstream executor (`/plan` / `/work`)
  owns backend selection.
- **Brainstorm-seam resolution (decision d).** The `#brainstorm-spec-interrogation-seam` is resolved
  in favor of a **standalone `/spec`** that owns WHAT-rigor; `/brainstorm` stays the divergent
  explorer. `/brainstorm`'s Phase-4 handoff menu now offers **Sharpen with `/spec`** (divergent
  `/brainstorm` → convergent `/spec`).
- **Periphery** — version bumps (plugin `0.17.0`, marketplace entry `0.17.0`; keywords stay at 10);
  dispatch-table now **total over 17 routable commands** with `/spec` added (off-chain advisory route,
  routing OUT to `/handoff` / `/plan` / optional `/doc-review`); README `/spec` command-summary line.
  Two deferral closures: `operator-choice.md` `/spec` row "at its rebuild" → "never offers";
  office-hours `frame-diagnostic.md` `/spec` moved from "campaign-queued" to an active routing-rubric
  row.
- Documented in the engineering journal (PR #195): DECISIONS
  `#spec-interrogation-engine-rebuild`, ARCHIVE `#spec-interrogation-engine-shipped` +
  `#brainstorm-spec-interrogation-seam-resolved`, LEARNINGS
  `#campaign-brief-merge-is-a-provenance-hypothesis`; consumed both `#spec-interrogation-engine` and
  `#brainstorm-spec-interrogation-seam` from QUEUED.

## 0.16.0 - 2026-06-04

- Add `/investigate` — the lifecycle's net-new **systematic-debugging engine** and the **eleventh
  command rebuild** of the engine-merge campaign (after `/office-hours`, `/plan`, `/code-review`,
  `/founder-review`, `/work`, `/loop`, `/resume`, `/qa`, `/strategy`, `/retro`). It answers "what is
  actually broken, and why?" — the diagnostic brain `/qa` (the gate) deliberately does not own. A
  **CE `ce-debug` spine** (causal-chain gate, falsifiable predictions for uncertain links, assumption
  audit, Phase-0 triage with trivial fast-path, smart-escalation, parallel read-only sub-agent
  dispatch) + **gstack `investigate` grafts** (the pattern-signature table — race/null/state/integration/config/cache
  — the two distinct numeric stop gates (hypothesis-exhaustion + 3-failed-fix), and the DEBUG REPORT
  Status enum) + a **superpowers
  systematic-debugging borrow**. Drops gstack scope-lock/freeze and all gstack runtime bins.
- **Diagnosis-primary, never a fixer.** `/investigate` produces a DEBUG REPORT (file:line, causal
  chain, regression-test path, Status enum) and **routes** the work out: a real fix → `/work` (via a
  `/handoff` issue); an applied inline fix → `/work` or `/code-review` to ship; a trackable defect →
  `/handoff`; a design-level root cause → `/brainstorm`. It does not commit, push, open/merge a PR, or
  deploy.
- **Saga READ-ONLY — zero saga edits.** `/investigate` reads saga context for evidence but writes no
  saga; **off-chain** (advisory, never blocks `/loop`). `saga.py`, `handoff_envelope.py`, and
  `references/saga-spec.md` are untouched. **No new Python** — `/investigate` is a markdown engine
  (SKILL + references + command). Verification is **own-minimal** (carries its own light verification),
  NOT a call back into `/qa`, overriding the pre-decision "verification CALLS /qa".
- **Full `/qa` cross-engine rewire — closes the deferred route at every site.** `/qa` deferred deep
  post-merge root-cause failures to "when `/investigate` is built." Building it closes that deferral
  **everywhere** (5 `/qa` SKILL mentions + 2 other-file notes): `/qa`'s post-merge FAIL branch is now
  **two-target** — deep-root-cause failures route to `/investigate` (now on the dispatch-table's
  routable list), clear/trackable defects still route to `/handoff`; pre-merge still routes to `/work`.
  Routing still **reads** `loop/references/dispatch-table.md`. No `/investigate`→`/qa` verify loop.
- **Periphery** — version bumps (plugin `0.16.0`, marketplace entry `0.16.0`; keywords stay at 10);
  dispatch-table now **total over 16 routable commands** with `/investigate` added (off-chain failure
  route); README `/investigate` command-summary entry; `operator-choice.md` + office-hours
  `frame-diagnostic.md` `/investigate` notes moved from "at its rebuild" / "campaign-queued" to active.
- Documented in the engineering journal (PR #193, squash 5079d8f):
  DECISIONS `#investigate-systematic-debugging-engine-rebuild`, ARCHIVE
  `#investigate-systematic-debugging-engine-shipped`, LEARNINGS
  `#deferred-cross-engine-wiring-must-close-on-build`; consumed from QUEUED.

## 0.15.0 - 2026-06-03

- Rebuild `/retro` from a 19-line stub into the lifecycle's **meta-improvement engine** — the **tenth
  command rebuild** of the engine-merge campaign (after `/office-hours`, `/plan`, `/code-review`,
  `/founder-review`, `/work`, `/loop`, `/resume`, `/qa`, `/strategy`). A **real 3-source merge**, not a
  port: gstack's `retro` + `learn` passes merged with CE's `ce-compound` framing into one engine that
  captures lifecycle learnings, distills durable knowledge, and proposes improvements to the workflow
  itself.
- **Six net-new passes on top of the merged retro+learn+compound base** plus a lean metrics surface —
  the FULL engine shipped in v1, nothing deferred. `/retro` runs as a single command with an optional
  pass argument so a focused sub-pass can be invoked directly.
- **Tiered self-edit gate — the safety contract for a self-modifying engine.** Pure-additive,
  append-only journal writes auto-apply; every delete / modify / move of existing durable state
  (memory, directives, the lifecycle plugin's own SKILLs) is **propose-diff-and-wait**, and any
  global / cross-project edit carries an extra cross-project-impact warning. The blast radius is the
  full self-modification surface **including the lifecycle SKILLs**, gated rather than narrowed.
- **In-repo vs global/cross-project directive disambiguation.** `/retro` distinguishes a repo-local
  directive from a global / cross-project one and warns before touching cross-project surfaces.
- **Saga READ-ONLY — zero saga edits, no §11 change.** The planned `->retro` saga advance was dead
  wiring; it is dropped. `/retro` reads saga context but writes none, so `saga.py` and `saga-spec.md`
  are untouched. **No new Python** — `/retro` is a markdown engine (SKILL + references + command) that
  reuses existing helpers; the windowed mode keeps a stale-base guard scoped to that mode.
- Version bumps: plugin `0.15.0`, marketplace entry `0.15.0`. keywords stay at 10 (unchanged).

## 0.14.0 - 2026-06-03

- Rebuild `/strategy` from a 21-line stub into the lifecycle's **interview-driven STRATEGY.md
  engine** — the **ninth command rebuild** of the engine-merge campaign (after `/office-hours`,
  `/plan`, `/code-review`, `/founder-review`, `/work`, `/loop`, `/resume`, `/qa`). A **faithful
  single-source PORT of CE `ce-strategy`**, NOT a merge: gstack has **no** strategy engine — `cso/`
  is the Chief **SECURITY** Officer (a 14-phase security audit), so the pre-audit "gstack cso ≈ Chief
  Strategy Officer" mapping was a name-match mixup. CE `ce-strategy` is the sole engine source.
- **The whole engine, ported.** Rumelt-grounded kernel (diagnosis / guiding-policy / coherent-action)
  + Phase-0 file-state routing (new STRATEGY.md vs targeted-section update vs pick-a-section) +
  Phase-1 **8-section interview with a mandatory 2-round pushback per section** + a **locked
  root-`STRATEGY.md` template** (3-5 metrics, 2-4 tracks) + rerunnable update-in-place. All 8
  sections and the Rumelt kernel are kept (no trimming).
- **Agent-as-customer is persona-only.** Personas may name AI-agent actors **when the product is
  agent-consumed**; **tracks stay pure investment areas / domains of work, NOT actors**. The QUEUED
  brief's blanket "personas/tracks must name AI-agent actors" was half a category error — tracks are
  domains of work, not actors — caught by reading the real CE `interview.md` section semantics.
- **Zero saga edits, off-chain / pre-saga.** `/strategy` owns the durable `STRATEGY.md` direction
  and writes no saga (like `/founder-review`, it runs upstream of the work loop); `/founder-review`
  challenges the direction, `/strategy` records it. **No new Python** — `/strategy` is a markdown
  engine (SKILL + references + command). `saga.py` is untouched.
- Version bumps: plugin `0.14.0`, marketplace entry `0.14.0`. keywords stay at 10 (`strategy` was
  already a keyword; unchanged).

## 0.13.0 - 2026-06-03

- Rebuild `/qa` from a 19-line stub into the lifecycle's **gate-only acceptance-evidence engine** — the
  **eighth command rebuild** of the engine-merge campaign (after `/office-hours`, `/plan`,
  `/code-review`, `/founder-review`, `/work`, `/loop`, `/resume`). A **real two-engine merge** against
  the cloned gstack source (`/qa` + `/qa-only` + `/investigate`) plus a CE `ce-debug` graft, **not** a
  phantom port: `/qa` adopts gstack's own report-only `/qa-only` model — it tests, gathers evidence,
  assigns severity, derives a verdict, and routes, but **never fixes, commits, pushes, opens/merges a
  PR, or deploys**.
- **Severity-banded verdict + a ported deterministic health score, reported alongside each other.** Each
  finding carries critical / high / medium / low (with a documented ↔ P0-P3 cross-walk to `/code-review`);
  pass/fail is stated per risk class and the overall ship verdict (`ship` / `ship-with-deferred` /
  `no-ship`) is derived from the tier's blocking threshold — and that verdict is the gate decision. A new
  deterministic scorer `scripts/qa_health_score.py` **ports gstack's Health Score Rubric**
  (`scripts/resolvers/utility.ts:286-321`, injected as the `{{QA_METHODOLOGY}}` macro): gstack's deduction
  values verbatim (critical -25 / high -15 / medium -8 / low -3) with documented infiquetra 9-way
  ship-risk-class weights, re-normalized over the in-scope classes, plus a baseline-from-prior-report
  delta. The 0-100 number is reported **alongside** the banded verdict, with the explicit caveat that its
  inputs are LLM-assigned severities — so it is one signal, not the gate decision.
- **Saga qa-track consumer — lands the deferred work→qa advance.** `/qa` `restore`s the work-thread
  saga, writes `qa_paths`, and **on PASS advances `lifecycle_phase` from `work` to `qa`** — the advance
  `/work` (0.10.0) explicitly deferred to this rebuild. On FAIL it keeps `lifecycle_phase=work` and
  records evidence. Every flag already exists (`--lifecycle-phase qa`, `--qa-paths`, the `qa` phase) —
  **zero `saga.py` edits**.
- **Durable risk reference + falsifiable-prediction graft.** Ships a `references/risk-taxonomy.md`
  (9-way risk router + per-class checklists + diff-aware file→class map + severity defs + the P0-P3
  cross-walk; gstack's 7 web categories fold under behavior/browser as **one MCP-driven class**, a
  graceful no-op off-UI) and `references/qa-report.md` (the report shape + ship-verdict derivation +
  tier→blocking-threshold table). Grafts CE `ce-debug`'s **falsifiable-prediction** discipline: for
  each uncertain-cause failure, state a prediction another path must also fail if the cause is real,
  giving the routed fixer a head start.
- **Merge-state failure routing.** PASS routes to `/handoff` or `/retro`; FAIL routes by merge state —
  pre-merge to `/work` (re-enter the round-N loop), post-merge to `/handoff` (open a new defect
  thread). `/investigate` is future-prose only (not on the dispatch-table's routable list). Routing
  **reads** `loop/references/dispatch-table.md`, never restating it.
- **One new script.** The Q2 final ports gstack's formula into `scripts/qa_health_score.py` (the scorer)
  with an oracle test; otherwise `/qa` is a markdown engine (SKILL + 2 refs + command + the scorer +
  tests), and `saga.py` is untouched. Also resolves the present-tense `docs/qa/` collision with the
  `/optimize` stub (one-line `/optimize` → `docs/optimize/`).
- Version bumps: plugin `0.13.0`, marketplace entry `0.13.0`. keywords stay at 10.

## 0.12.0 - 2026-06-03

- Rebuild `/resume` from a 23-line "read committed docs first" doc into the lifecycle's **heavy
  forensic reconstruction engine** — the **seventh command rebuild** of the engine-merge campaign
  (after `/office-hours`, `/plan`, `/code-review`, `/founder-review`, `/work`, `/loop`) and the
  **unblocked heavy partner** the `/loop` rebuild (0.11.0) explicitly deferred to it. `/loop` owns the
  **lightweight** scan → restore → route + inline cold-reconstruction; `/resume` owns the **heavy**
  forensic half. Unlike `/loop` (the campaign's native rebuild against a phantom brief source),
  `/resume` is a **real CE `ce-sessions` PORT** — verified TRUE and portable against the actual
  upstream, the positive counterpart to the `/loop` phantom-source lesson.
- **Two-tier design.** **Tier 1** (the common path) = saga-anchored deep reconstruction: a NEW saga
  **all-ticks reader** (`saga.py` `read_ticks`) that walks the full append-only tick-chain trajectory —
  the trajectory `/loop`'s latest-tick-only `restore` cannot see — plus PR archaeology and conflict
  reconciliation. **Tier 2** (FALLBACK ONLY, when there is **no saga AND no resolvable issue**) = a slim
  Claude-only port of CE `ce-sessions`: discover → file-mediated skeleton extract to scratch → **generic
  agent synthesis**, never reading multi-MB session JSONL into context (context-safety by construction).
- **The all-ticks reader lives in `saga.py`, NOT `load_saga_context.py`.** A brief deviation: the
  `load_saga_context.py` wrapper is **issue-locked** (its `--issue` arg is required), so it is the wrong
  layer for a cold-no-issue trajectory read. The all-ticks capability belongs in the saga engine itself
  (`read_ticks`); `load_saga_context.py` stays the shared issue-keyed substrate `/loop` and `/resume`
  both use.
- **Generic-agent synthesis — no `agents/` dir.** Tier-2 synthesis uses generic agents, honoring the
  shipped `/code-review` convention (no plugin `agents/` dir → generic agents, SKILL:164) rather than
  adding a structural first.
- **Drop the `[gstack-context]` commit trailer.** `/resume` does NOT adopt gstack's WIP-commit trailer —
  the saga's append-only tick log already IS the durable trajectory; a parallel trailer would duplicate
  it. Corrected Tier-2 trigger: same-machine work that never wrote a saga (NOT fresh-clone).
- **Routing + the one re-entry tick.** Routes to any phase via the **shared**
  `loop/references/dispatch-table.md` (referenced, never duplicated — no `/loop` ↔ `/resume` ping-pong).
  Writes exactly **one** git-ignored re-entry saga tick, **reusing the restored `saga_id`** (never-mint
  discipline — `/resume` is a reader/restorer, not a saga primary writer).
- **Recency-MVP ranking** for Tier-2 candidate sessions; keyword/branch relevance ranking deferred
  (QUEUED `#resume-session-relevance-ranking`).
- Version bumps: plugin `0.12.0`, marketplace entry `0.12.0`. keywords stay at 10.

## 0.11.0 - 2026-06-03

- Rebuild `/loop` from a router stub into a native router engine — the **sixth command rebuild** of the
  engine-merge campaign (after `/office-hours`, `/plan`, `/code-review`, `/founder-review`, `/work`) and the
  campaign's **one native rebuild**: there is no upstream engine to port or merge. CE ships no router; the
  gstack "dispatch table" the QUEUED brief named is **phantom** (gstack's root SKILL is browser-testing, no
  router dir), and gstack's context-save/restore is the shipped saga + the queued `/resume`'s engine, not
  `/loop`'s. Three modes: **Route** (classify intent → hand to the right lifecycle command), **Drive**
  (inline phase walk with a per-decision operator-choice offer for `/loop`-owned work), **Resume** (scan →
  restore → route a durable work-thread).
- **Saga resume wiring.** `/loop` `scan`s for the matching work-thread saga, `tick`s a routing event, and
  `restore`s state on re-entry — plus inline cold-reconstruction via `load_saga_context.py` when re-entering
  without a live session. The routing tick carries the existing saga fields plus an offload pointer only for
  `/loop`-owned offloads (no schema change).
- **Operator-choice offer for `/loop`-owned work.** `/loop` offers the three execution backends
  (`inline` / `team-execution` / `cc-workflows-ultracode`) per decision point in Drive mode for work it owns.
  The offload pointer is scoped to `/loop`-owned work only — `/loop` does **not** instruct a routed command's
  backend (`/work` writes but never reads `orchestration_mode`).
- **Additive saga picker-field extension.** `saga.py` `scan()` / `_saga_summary` gained the issue_ref /
  plan_path / branch picker fields so a resuming `/loop` (and `/code-review`) can match the right thread —
  closing the `#code-review-saga-scan-touchups` queued item.

## 0.10.0 - 2026-06-03

- Rebuild `/work` from a 39-line facilitator stub into a real execution-loop engine — the **fifth command
  rebuild** of the engine-merge campaign (after `/office-hours`, `/plan`, `/code-review`, `/founder-review`)
  and the most architecturally entangled, because it lands two deferred foundations at once. A genuine
  **merge**: CE `ce-work`'s execution engine (Phase-0 complexity triage, task-list from plan U-IDs, the
  Execution-Strategy table + Parallel Safety Check, test discovery + scenario-completeness + system-wide
  check, incremental-commit heuristic, "already shipped → verify don't reimplement") + gstack `ship` /
  `land-and-deploy`'s autonomy contract, Review-Readiness + staleness gate, and merge-base-before-tests.
  Five numbered phases: enter + scan saga + triage + detect round-N → setup + task-list + backend → execute
  phase-by-phase → record (saga tick + work-session + issue progress) → code-review gate + PR-ready +
  continuation routing.
- **Saga becomes first-class — `/work` is its primary writer (saga-spec §11).** `/work` `scan`s/`restore`s on
  re-entry (rehydrate round/phase/checks_run/next_step), mints/advances the work-thread saga to
  `lifecycle_phase=work` with `--plan-path` set + saved on-branch, and writes a tick per phase boundary
  (round bump via `--rounds-seen`, never `next_round`). Crucially it **mints + names the exact saga that
  `/code-review` (shipped 0.8.0, append-only/never-mint) appends `review_paths` to** — and passes the saga
  identity (`kind`+`id`) into the programmatic `/code-review` call so code-review hits that thread instead of
  scan-guessing. This closes the forward-coupling for both issue AND ad-hoc task work.
- **The deferred `recommend_execution_backend()` helper lands here** — its first real caller (a library-only
  helper would be uncallable from markdown). A pure function in `scripts/lifecycle_state.py` next to
  `should_offer_team_execution` (reused), plus a `recommend-backend` CLI subcommand returning
  `{recommended, rationale, alternatives, omit_ultracode}`. `alternatives` is computed independently of the
  precedence winner so an overlap case (consensus AND broad fan-out) still offers `cc-workflows-ultracode` as
  a one-keystroke escalation. `main()` refactored into `normalize` + `recommend-backend` subcommands.
  Closes the operator-choice 0.5.0 deferral.
- **`issue_progress.py`'s CLI extended** to forward the full field set the function already accepts
  (`--work-session-path --commit-sha --checks-run` [pipe-separated] `--blockers --pr-url --review-status
  --doc-review-artifact --doc-review-blocked --doc-review-findings` [pipe-separated] `--doc-review-override
  --deploy-status --workflow-url --evidence-link`) — the Phase-4 progress comment was previously
  uninvokable from markdown (only 8 of the function's fields had argparse flags).
- **PR-ready boundary + round-N PR continuation loop (`/work` owns it, NOT `/resume`).** `/work` executes to
  PR-ready, then on re-entry reads PR state with a total `gh pr view --json
  state,reviewDecision,mergeable,mergeStateStatus,statusCheckRollup,isDraft,mergedAt` and walks a total
  transition table (draft → mark-ready; review-required → pause; changes-requested/conflicting/failing-checks
  → round N+1; approved+clean+fresh → offer merge). **Merge is a confirmed git op `/work` owns**
  (`gh pr merge` only under explicit operator confirmation, never silent); only deploy mutation is delegated
  to `deploy`.
- **Hard review gate + honest override + computed staleness.** PR-ready blocks on unresolved P0/P1 (read from
  `/code-review`'s programmatic envelope + the saga `review_paths`) OR a stale review (parse the reviewed SHA
  from the newest review artifact → `git rev-list <reviewed_sha>..HEAD --count > 0`). Override only with a
  recorded rationale, never silent. `requires_hard_test_gate` blocks risky change-kinds at the test gate.
- **Boundary.** `/work` builds, gates, records, and coordinates the PR loop (merge under confirmation); it does
  NOT silently mutate GitHub, own deploy/canary (gstack's canary-verify + offer-revert are **relocated** to
  `deploy`, queued there), file SDLC issues (`mission-control`), or advance `lifecycle_phase` past
  `work` (the `qa` advance is honestly deferred to the `/qa` rebuild — the saga sits at `work` post-merge;
  `/qa`/`/resume` routing is advisory).
- Three new references: `skills/work/references/{execution-strategy,test-and-gates,pr-continuation-loop}.md`
  (CE execution strategy + the `recommend_execution_backend()` integration; test discovery + hard-gate +
  computed-staleness + the gstack autonomy contract; the total PR-state transition table). Thin
  `commands/work.md` launcher (saga-primary-writer + PR-ready boundary + hard review gate +
  merge-under-confirmation; no deploy/canary ownership). Surgical flip of `references/operator-choice.md`'s
  deferred-helper notes now that the helper has shipped. Self-contained: merges the CE + gstack engines, no
  vendoring, no runtime dep.

## 0.9.0 - 2026-06-03

- Rebuild `/founder-review` (alias `/ceo-review`) from a 20-line stub into a real scope/ambition/direction
  review engine — the fourth command rebuild of the engine-merge campaign (after `/office-hours`, `/plan`,
  and `/code-review`). A **port, not a merge**: gstack `plan-ceo-review` is the sole engine source (4
  user-selected scope modes + 18 internalized CEO cognitive patterns + 9 Prime Directives + an adapted
  pre-review system audit), with only CE `product-pulse`'s sharpened no-false-precision posture stolen.
  Fires upstream of execution on a `/plan` artifact, a `STRATEGY.md`, a `/brainstorm` output, or an ad-hoc
  scope question — the third member of the review trio (`/doc-review` = plan-readiness, `/code-review` =
  code quality, **`/founder-review` = is this the right, ambitious-enough thing to build at all?**).
- **Four scope modes, committed for the whole review (no silent drift)** — SCOPE EXPANSION (cathedral) /
  SELECTIVE EXPANSION (hold + cherry-pick) / HOLD SCOPE (bulletproof) / SCOPE REDUCTION (surgeon), selected
  via `AskUserQuestion` with context-defaults (greenfield→Expansion, enhancement→Selective, bugfix/refactor
  →Hold, >15 files→suggest Reduction). Each is distinct; all relevant pre-traction.
- **Review-only boundary** — `/founder-review` challenges scope/ambition/direction + captures a scope
  decision; it never makes code changes, never commits/pushes/opens PRs, never files SDLC issues, and never
  *records* the direction (`/strategy` records; founder-review challenges). On a `STRATEGY.md`, founder-review
  is the *ambition lens* and `/doc-review` the *readiness lens* — complementary, not a collision.
- **CLOSED-LOOP routing (not a hand-wave)** — accepted scope routes to `/plan` to re-plan; the (re-)expanded
  plan artifact is written/updated and handed **back** to `/doc-review` (readiness) + `/code-review` (code)
  **with the concrete path**, so expanding scope re-rigors that scope rather than dropping it. Phase 3
  applies the directives + patterns as scope-level lenses producing **named scope findings**, not vibes.
- **Target-conditional Step-0 ceremonies** — gstack's 0C-bis (implementation alternatives) + 0E (temporal
  interrogation) are plan-specific, so they run on a plan target and are skipped/recast on a
  strategy/brainstorm/scope-question target (0A/0B/0C/0F always run). An **office-hours escape** in 0A
  offers `/office-hours` when the session is vague/unframed, resuming after.
- **NO saga write** — founder-review runs upstream/pre-saga and its output is a scope decision, not a
  readiness/code-review artifact; `saga.py`'s `review_paths` is the wrong home and the guard would skip
  ~always. Cross-session persistence = the `docs/founder-reviews/` scope-decision artifact + the journal ADR.
- Durable artifacts land in their own `docs/founder-reviews/` scope-decision dir (intentionally NOT a
  `/handoff` source and NOT `docs/reviews/`), carrying the Mode + Vision + a Scope-Decisions table
  (ACCEPTED/DEFERRED/SKIPPED) + the founder verdict (ship / sharpen / scrap-and-rethink) + the next-command
  handback. **Operator-choice** offer — all three backends (`inline` | `team-execution` |
  `cc-workflows-ultracode`) cited by path (`references/operator-choice.md`) on a scope-expansion/scrap verdict.
- Two new references: `skills/founder-review/references/{ceo-cognition,review-modes}.md` (the 18 patterns + 9
  directives + sharpened posture; the 4 modes + ceremonies + adapted audit + target-conditional gating).
  Thin `commands/founder-review.md` + `commands/ceo-review.md` (alias) launchers (review-only, no saga
  mention). Self-contained: ports the gstack engine, no gstack vendoring, no runtime dep on CE.

## 0.8.0 - 2026-06-03

- Rebuild `/code-review` from a 20-line stub into a real pre-PR code-quality review engine — the third
  command rebuild of the engine-merge campaign (after `/office-hours` and `/plan`). Merges CE's
  `ce-code-review` findings/validator/judgment-lens spine (the Jeff-preferred backbone) with gstack
  `/review`'s scope-drift detection + plan-completion audit + high-signal checklist categories into a
  self-contained infiquetra engine. Fires at the work→PR boundary (after `/work` produces code, before
  PR/merge) — it is a within-work gate, NOT the saga `review` lifecycle slot (`/doc-review` owns that).
  Six numbered phases: enter + scope → intent + built-vs-planned audit → select lenses (judgment) →
  review fan-out → merge + validate → report + route + saga.
- **Gate-only boundary** — `/code-review` reports + classifies + routes; it never mutates code, commits,
  pushes, opens PRs, or files SDLC issues (`/work` / `deploy` / `mission-control` own those).
  Adopts CE's full findings schema (`autofix_class` / `owner` / anchored `confidence` / `suggested_fix` /
  `pre_existing` / `evidence`) as agent-consumable routing metadata; fixer dispatch is offered, never
  auto-run. The programmatic mode (for `/work`'s future call) is zero-write to reviewed code.
- **Judgment-based lenses** — read the diff, spawn only lenses with real work, announce the team with a
  one-line justification each. Four always-on lenses (correctness, security, testing,
  maintainability/conventions) plus conditional-by-judgment lenses including a distinct
  deploy/migration-verification lens (DynamoDB/IaC/Ansible checklist) and a reliability lens. gstack's
  Rails/Swift/Stimulus specialists dropped; its high-signal checklist categories (enum-completeness,
  LLM-output-trust-boundary, SQL/shell-injection, race conditions) fold into the lens checklists.
- **Built-vs-planned audit** — scope-drift detection (informational: CLEAN / DRIFT / REQUIREMENTS-MISSING)
  plus the 5-state plan-completion audit (DONE / PARTIAL / NOT-DONE / CHANGED / UNVERIFIABLE) with the
  three verification modes (DIFF / CROSS-REPO / EXTERNAL-STATE) and the honesty rule, reading the
  `docs/plans/` artifact + the journal. The audit always emits findings; the normal P0/P1 findings gate
  is what blocks the PR.
- **Independent validator pass, right-sized by MODE** — programmatic/headless runs a fresh per-finding
  validator over all Stage-A survivors (capped 15, ordered P0→P3, validator-reject/failure → drop);
  interactive mode lets the operator be the per-finding validator. The cost control is the upstream
  suppress-<75 confidence gate + the 15-cap, not a severity carve-out.
- `/code-review` becomes **saga's first review-track consumer** — append-only to an EXISTING work-thread
  saga (found via `saga.py scan`): appends the artifact path to `review_paths` + records the backend in
  `orchestration_mode`, preserving `lifecycle_phase` (it does NOT advance the phase). If no saga exists it
  skips the saga write — never mints, never invents `--kind/--id`. Never `git add` the tick.
- Durable artifacts land in their own `docs/code-reviews/` dir (NOT `docs/reviews/` — avoids the
  handoff/mission-control plan-ready classifier collision), carrying the reviewed SHA + a review-result
  contract. **Operator-choice** offer — all three execution backends (`inline` | `team-execution` |
  `cc-workflows-ultracode`) cited by path (`references/operator-choice.md`) for the fan-out + validator
  pass.
- Four new references: `skills/code-review/references/{lens-catalog,findings-schema,validator,built-vs-planned}.md`.
  Thin `commands/code-review.md` launcher reflecting the engine (gate-only + saga append + the hard
  boundary). Self-contained: ports both source engines, no gstack vendoring, no runtime dep on CE.

## 0.7.0 - 2026-06-02

- Rebuild `/plan` from a 27-line stub into a real implementation-plan engine — the second command
  rebuild of the engine-merge campaign. Merges CE's `ce-plan` structured-artifact engine (the
  Jeff-preferred spine) with gstack `spec`'s code-grounded HOW-interrogation front end into a
  self-contained infiquetra engine. Six numbered phases: enter + warranted-gate → ground (HOW) →
  interrogate (HOW) → synthesize the plan artifact → condensed deepening pass → saga + route +
  operator-choice.
- Artifact contract (CE wholesale): stable **R-IDs** (requirements), **KTDs** (Key Technical
  Decisions), independently-landable **U-IDs** with per-unit enumerated **test scenarios** + explicit
  test-file paths; requirements traceability; "decisions not code"; three-audience design (human +
  agent + `/work` consumer). The plan doc carries `origin:` + `Implementation Units` +
  `Key Technical Decisions` + `U1` markers so `/doc-review` recognizes it.
- **Warranted-gate** + scope classes up front — a `/plan` invocation that doesn't warrant a durable
  plan is named and routed, not force-fit into the artifact.
- **HOW-only interrogation** — `/plan` assumes the WHAT (requirements/scope) settled upstream
  (`/ideate` → `/brainstorm` → `/office-hours`); open WHAT-ambiguity bounces back with a recommendation
  to run `/brainstorm` first (it does NOT claim `/brainstorm` "accepts" a handoff). The interrogation
  register grounds in code (cite `path:line`) before asking.
- **Condensed deepening pass** — a conditional confidence self-review (not CE's full 248-line
  deepening), kept proportional. The full review gauntlet is NOT dropped — it's the `review` phase
  (`/doc-review` + `/code-review` + `/founder-review`); `/plan` keeps the condensed self-review and
  routes to `/doc-review` (the recommended next step) before `/work`.
- One **plan saga** via the saga CLI (`scripts/saga.py save`, `--lifecycle-phase plan`) — runnable,
  with an explicit "never `git add` the tick" boundary; epic/multi-unit splits hand to `mission-control`.
- **Operator-choice** offer: all three execution backends (`inline` | `team-execution` |
  `cc-workflows-ultracode`) cited by path (`references/operator-choice.md`), offered not defaulted.
- Hard boundary: `/plan` does NOT implement, does NOT file SDLC issues (`mission-control` owns that), and
  does NOT run the full review gauntlet (`/doc-review` owns that). Position: `/plan` answers
  "How should it be built?".

## 0.6.0 - 2026-06-02

- Rebuild `/office-hours` from a 23-line facilitative stub into a real two-mode thought-partner
  diagnostic ported from gstack and adapted to infiquetra — the Think-phase frame-finding front
  door that `/ideate` routes unframed asks to and `/brainstorm` bounces open thought-partner work
  back to. Keeps that handshake.
- Two modes: **Startup mode** — gstack's six market/customer forcing questions, made
  **stage-aware** (a pre-traction / pre-revenue greenfield operator gets a hypothesis-forming
  register, not an evidence-audit of customers that don't exist yet); **Builder mode** —
  discovery/shaping for infra, workflow, and internal-tooling asks, infiquetra's high-frequency
  mode, carrying real depth (not a one-liner). Modes can switch mid-session.
- Anti-sycophancy + pushback re-targeted: hard on vagueness and ungrounded assumptions, not on
  the operator's judgment; push-twice with escape hatches. **HARD GATE** (absolute): never
  implement, plan, or file an SDLC issue — frame-finding only. Stops the moment it can name the
  problem and a route, with plural clean exits (`/brainstorm`, `/plan`, `/strategy`).
- Route always (close by naming a next command); an optional **frame note** lands in its own
  `docs/office-hours/<date>-<topic>-frame.md` (frontmatter `kind: frame-note`) — kept out of
  `docs/ideation/` to avoid colliding with the `/ideate` resume scan.
- Self-contained: ports the gstack engine, sheds its runtime boilerplate (brain-context preflight,
  gbrain sync, learnings-search, telemetry, `~/.gstack` path conventions). No gstack vendoring, no
  runtime dependency on compound-engineering.

## 0.5.0 - 2026-06-02

- Add the operator-choice framework: a new contract document, `references/operator-choice.md`, that
  codifies the 3-way execution-backend choice — `inline` / `team-execution` / `cc-workflows-ultracode`
  (the canonical `ORCHESTRATION_MODES` enum strings). Lifecycle owns the *choice* of backend; it does
  not own execution.
- Add short prose offer hooks to `/loop` and `/work` that surface the operator-choice when work
  warrants a non-inline backend, pointing at the decision contract.
- Fix the `saga-spec.md` `orchestration_mode` cross-ref: it pointed at §7 (the save/restore/scan
  operation contract) instead of the decision contract; it now references
  `references/operator-choice.md`.
- Doc-only foundation. No code or helper is added in this release — the CLI-backed
  orchestration-choice helper is deferred to the `/work` rebuild.

## 0.4.0 - 2026-06-02

- Add a unified saga engine (`scripts/saga.py`): one source of truth for durable, resumable
  work-state with a stable derived identity (`issue-<N>` / `task-<slug>`, sticky for the life of
  the work), save/restore/scan, and gh-context aggregation. Sagas are written as an append-only,
  timestamped envelope log under `.claude/saga/sagas/<saga_id>/<YYYYMMDD-HHMMSS>.md`
  (gstack-style YAML frontmatter + `Summary`/`Decisions`/`Remaining`/`Notes` body), plus a derived,
  rebuildable `state.json` index. Envelopes are immutable; each save appends a new tick.
- The three legacy scripts — `scaffold_checkpoint.py`, `find_inflight_work.py`, and
  `load_saga_context.py` — are now thin wrappers that delegate to `saga.py`. Every CLI flag and JSON
  output key is preserved, so existing callers keep working.
- Behavior changes from this unification:
  - Storage moved from per-phase `checkpoints/` files to per-saga `sagas/<saga_id>/` envelope
    directories.
  - Ordering is now by envelope filename (the timestamped name **is** the canonical order), never by
    filesystem `mtime`. This makes ordering deterministic and robust under rsync/backup/snapshot
    restore.
  - Saves are append-only (a new immutable tick per save) instead of overwriting a single checkpoint.
  - Three stored state axes — `lifecycle_phase` (CE flow position), `phase_status` (phase
    completion, drives the next phase), and `status` (thread disposition) — replace the prior
    ad-hoc fields; `maturity` is derived at `/handoff` time, not stored. Frontmatter lists use
    full-snapshot replace semantics (a tick's lists replace; absent carries forward; empty clears).
- Add a plugin-level contract document, `references/saga-spec.md`, that the lifecycle consumers
  (`/plan`, `/work`, `/resume`, `/loop`) implement against.
- **Upgrade warning:** complete any in-flight `/loop` work before upgrading. Legacy
  `.claude/saga/checkpoints/` state is read as a low-priority `scan` fallback for one
  version only and then dropped — finish or re-save active loops so they migrate into the new
  `sagas/` layout.

## 0.3.0 - 2026-06-01

- Rebuild `/ideate` from a thin facilitative stub into a full divergent→convergent engine ported from
  compound-engineering and adapted to the infiquetra world: parallel frame agents generate many
  grounded candidates, the orchestrator critiques all and presents only the survivors, and cut ideas
  stay first-class and revivable. Adds a two-way thought-partnership — the operator's seed ideas feed
  *into* the frame agents (build on / challenge / combine) and face the identical critique — and a
  revival state machine that re-enters the filter with new evidence, preserving explicit rejection as
  the quality mechanism.
- Add infiquetra-specific grounding to `/ideate`: a grounding-fit gate (proceed / decline /
  recommend `/office-hours` / ask) weighing idea breadth against available grounding; a
  context-library reader (`*-context-library` repos via `gh`, local-clone preferred); a named-repo
  reader for multi-repo asks; read-only `gh` issue-theme clustering on backlog intent; and smart-auto
  web research for the cross-domain-analogy frame. Adaptive frame count (1–6) scales to scope.
- Rebuild `/brainstorm` into a thinking-partner engine that deep-dives one chosen idea (a `/ideate`
  survivor or a named topic) into a right-sized requirements document: scope assessment, a product
  pressure-test, one-question-at-a-time dialogue, 2–3 approaches with a non-obvious angle, and a
  `requirements-ready` artifact under `docs/brainstorms/` for `/plan`.
- Add reference files: `skills/ideate/references/convergence-and-partnership.md`,
  `skills/ideate/references/ideation-artifact.md`, and
  `skills/brainstorm/references/requirements-sections.md`. Self-contained — no runtime dependency on
  compound-engineering.
- Add `/handoff` to route durable lifecycle artifacts to `mission-control` prepared issue drafts, with a
  thin handoff-envelope helper that records source, maturity, target hints, blockers, open questions,
  and the `/issue --prepare` routing command without owning SDLC issue bodies. Teach
  `/plan <issue>` and `/work <issue>` to consume handoff maturity and source context from prepared
  SDLC issues.

## 0.2.0 - 2026-05-31

- Rename the plugin from `infiquetra-loop` to `saga`; "loop" named only the `/loop`
  router command, not the whole idea-to-ship lifecycle the plugin covers. The `/loop` command name
  is unchanged.
- Rename the ignored runtime-state directory from `.claude/infiquetra-loop/` to
  `.claude/saga/`; `mission-control` updated in lockstep.
- Rename the handoff-envelope `loop_owner` field to `lifecycle_owner`.
- Document the command set by lifecycle phase: Think, Plan & execute, Hand off, Review, and
  Improve & route.

## 0.1.0 - 2026-05-29

- Add the Infiquetra lifecycle command set from office-hours through resume.
- Add `/doc-review` for plan, requirements, and formal SDLC implementation-readiness review.
- Add durable repository artifact guidance and ignored local runtime-state guidance.
- Add helper scripts for destination selection, issue progress comments, deploy strategy
  detection, team-execution escalation, and engineering-journal triggers.
- Preserve VECU work-loop mechanics source-neutrally: issue parsing, ignored checkpoints,
  inflight resume discovery, saga context loading, sub-issue discovery, and cached deploy
  strategy detection.
