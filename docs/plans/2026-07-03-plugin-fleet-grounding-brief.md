# Grounding Brief — Plugin-Fleet Ideation (Gate B)

- **Date:** 2026-07-03
- **Status:** 4 of 5 streams complete; session-mining synthesis PENDING (workflow `wf_7e5d77a2-5c0`, 70 skeletons)
- **Feeds:** Phase C workflow design (Gate C) and Phase D theme dispatch
- **Companion:** [Intake Brief](2026-07-03-plugin-fleet-ideation-intake-brief.md)

## 1. Fleet map (re-verified today)

8 plugins: saga 0.51.0 (skills, lifecycle + /outcome DAG), team-execution 2.9.0 (hybrid,
consensus review), mission-control 2.4.0 (CLI, SDLC), agy 0.1.0, deploy 0.1.2,
home-lab-ops 1.2.0, redis-channel 0.5.0, unifi 1.1.0.

**Model/effort reality:**
- The fleet's ONE operator-facing model/effort lever: saga `/plan`'s unit tier table
  (`plan/SKILL.md:296-352`), vocabulary `MODELS=("fable","opus","sonnet","haiku")` /
  `EFFORTS=(...,"xhigh")` (`execution_spec.py:52-53`).
- Every agent frontmatter across all 8 plugins hardcodes `model:` (opus/sonnet/haiku), zero
  `effort:` fields (0 of 24 in team-execution), no dispatch-time override lever anywhere
  except saga's readonly-verifier per-call pattern.
- `fable`/`xhigh` unreachable outside saga plan vocabulary.

**Corrections to intake §9:**
- (c) CHANGED: `ENGINE_INTENTS` is a producer/consumer pair — authored in `/plan`
  (`plan/SKILL.md:303-304`), rendered in team-execution Step A7 worker table
  (`team-execution/SKILL.md:229-233`, → `references/external-engine-workers.md`). Still
  absent from `/ideate`, `/brainstorm`, `/work` interactive flow.
- (h) NUANCE: `/outcome start` = 2-node starter DAG, but `outcome_decompose.py` (U7) is the
  real decomposition path — just not at start-time and not from an existing GitHub
  Objective. No ingestion path confirmed. PR merge/deploy documented "never autonomous."
- (e) CAVEAT: `.team-execution.json` model/effort absence confirmed by absence of contrary
  evidence (no schema file exists to inspect), not direct inspection.

**Concurrency governance:** the only orchestration-level cap is `VERIFY_N_CAP = 7`
(`execution_spec.py:114`, born from a real 22-judge panel incident). team-execution
reviewer fan-out, `/outcome` leaf dispatch, and engine bridges are unbounded. Notably,
`/optimize` **deliberately removed** a `max_concurrent` knob (`optimize/SKILL.md:18`) —
ideation on theme 13 must engage why. HTTP-level 429 handling exists only in unifi and
mission-control clients.

## 2. Binding-decision register (ideas contradicting one must engage its revisit-when)

| Decision (anchor) | Constraint it imposes on ideation |
|---|---|
| `{#external-engines-never-gatekeepers}` (#283) | Claude is verifier-of-record for every gated decision; codex/agy = generator / advisory-reviewer / non-gated worker only. Structurally enforced. Revisit-when: read-only-sandbox profile ships, or team-execution gains an external-engine worker slot. |
| `{#external-engine-chaperone-dispatch}` (#318) | External engines in teams = chaperone dispatch (offload→sonnet/medium, second-opinion→opus/high), never a second executor kind / residency / git participant. |
| `{#worker-cache-scheduling}` (2026-06-27) | Cache economics theme has a settled architecture: derive (segment+agent+tier) saga-side, reside team-side; segment boundary = plugin directory. Revisit-when: named-teammate residency proves insufficient, or idle-poll justifies a formal wave queue. |
| `/outcome` campaign (U1–U11) | Derived-on-read status, never committed status fields; HALT-not-degrade; backend menu off-by-default with host-conditional degrade; cost ledger = leaf-produced fact. |
| `{#operator-choice-framework}` | Operator-choice = doc-only, CLI-driven `/work`; ultracode framed as review-depth, not fan-out. |
| `{#readonly-verifier-fallback-ladder-325}` + `{#verify-agent-git-checkout-clobber}` | Verify-class spawns: readonly profile + worktree isolation, Explore-first fallback ladder. |
| `{#tier-vocab-ordering}` | Tier tuples are ordered escalation ladders, not just closed sets. |
| `{#plugin-portfolio-groom-17-to-7}` | Plugin sprawl is an active concern — "new plugin" ideas carry a consolidation burden of proof. |

**Alignment note:** the operator's stated external-LLM posture ("evaluated and incorporated
based on the analysis of the main LLM") already matches never-gatekeepers — no tension,
but issue text must be explicit that consensus participation is advisory-only.

## 3. Consumer-side signal (cross-repo journals, 19 repos scanned)

Ranked by independent-repo recurrence:
1. **Rename/vocabulary churn + contract-mirror drift** (4 repos): saga rename lockstep
   landings, Olympus→CAMPPS, `validate_card_body` stale hand-copy of the real
   `card_validator.py` (343 "clean" cards failed the live contract, → #222), re-vendored
   `sdlc-schema.json`. → NEW THEME candidate 14.
2. **team-execution consensus review catching defects green suites missed** (2 independent
   repos, operator-praised). Strengthens theme 5 (consensus portability).
3. **mission-control/saga contract copies drifting from source of truth** (2 repos) —
   overlaps finding 1.
4. Claude Code runtime quirks recorded as durable build constraints (bg-dispatch loses
   channel notifications; agents/*.md not auto-loaded; protocol byte-identity) — 1 repo,
   4 distinct quirks.
5. **Promote ledger: 0 learnings ever promoted; no genuine ≥3-repo transcendent cluster.**
   The cross-repo learning loop exists but has never fired. Strengthens theme 10.

## 4. Standards/ADR enforcement (context library)

- Enforcement already exists *inside the library*: `validate.yml` CI runs `check_docs.py`
  (schema/frontmatter/link lint + promotion-ledger checks) + `context_census.py --check`
  (keeps `llms.txt` honest). The org convention is **schema-validate-in-CI + self-describing
  index**, not runtime-injected blobs.
- `authority-model.md` defines the agent priority order incl. "stop and surface conflict."
- **Absent:** any pull of the library into `mission-control:issue` / `saga:plan` creation;
  any ADR↔code-pattern lint; any reference to the library from this repo's CI.
- Consumption shape: `llms.txt` (~1-2KB) whole-injectable; per-topic READMEs (8-12KB) load
  on demand; whole-library injection infeasible (platform-specs dominates).
- Hygiene find: **15 stale abandoned saga worktrees** in `.worktrees/` inflating the repo
  10×+ → direct evidence for theme 6 (teardown/reclamation), same disease as
  team-execution's missing Step B8.

## 5. Pre-existing seeds (this repo's QUEUED.md — carry into Phase D as seed candidates)

Direct matches to operator asks: `{#team-execution-per-teammate-effort}` (plan-dictated
per-teammate effort — exactly the "why can't I pick effort?" ask),
`{#delegate-agents-plugin}`, `{#engineering-journal-plugin}`, `{#saga-multi-repo-arc}`,
`{#marketplace-ci-guard}`, `{#resume-session-relevance-ranking}`,
`{#infiquetra-deploy-canary-verify-revert}`, `{#pulse-live-telemetry-component}`,
`{#proactive-notifications}`, `{#discord-button-approval}`, plus ~15 smaller items.

## 6. Recurring-pain themes from this repo's journal

1. **Silent no-ops in delegation & dead wiring** (5+ learnings: agy silent Claude-fallback,
   dead-wiring producer+consumer, test-shape-masks-dead-wiring, fake-adapter mismatch) —
   any bridge/delegation idea needs "did it actually run/persist" verification. → NEW THEME
   candidate 15 (delegation integrity).
2. Provenance/status claims must be re-verified against current state (4 learnings).
3. Release-surface drift persists despite CLAUDE.md step 6 — room for automation.
4. External-engine containment = hottest active frontier (3 decisions + 5 learnings in two
   weeks).
5. Derive-on-read over committed state — recurring rejected alternative.

## 7. Session-mining synthesis (COMPLETE)

Workflow `wf_7e5d77a2-5c0`: 70/70 skeletons distilled (0 dropped), 27 sessions yielded 175
findings → 10 recurring patterns + 8 singletons. Per-agent detail in the workflow journal.
Also: **219 codex sessions in-window with no mining substrate** — grounded gap, feeds
theme 10.

Recurring patterns, ranked by repo spread:
1. **Manual ship ceremony** — commit→PR→merge→checkout-main→pull→cleanup done by raw
   git/gh in session after session, even where saga/mission-control is installed
   (8 repos). → theme 7.
2. **Gate-primitive unreliability** — AskUserQuestion silently auto-proceeds on timeout
   treating silence as consent (documented operator fury), fires before answers are
   captured, errors outright; agents fall back to plain-text questions (6 repos). → theme
   6 (new facet).
3. **mission-control board/field drift** — nonexistent fields assumed, hardcoded aliases,
   item-list pagination silently truncating at 200 of 375 items, create/board-add/field-set
   racing (4 repos). → themes 9/14.
4. **Rate-limit fan-out kills** — "6 of 7 agents failed on rate-limiting"; "the emitter has
   no concurrency knob... KTD6 was aspiration, not machinery" (3 repos). → theme 13.
5. **saga scratch dir not gitignored in scaffolded repos** (4 repos). → direct-to-candidate.
6. **Ad hoc tier reasoning every time** — "xhigh-Opus on everything is wasteful"; manual
   per-unit tier tables; operator asking for mid-run model-change pauses (3 repos). →
   theme 12.
7. **Stale memory/doc claims asserted as fact**, caught only by operator recall or lucky
   re-verification (2 repos). → theme 10.
8. **Background-session/worktree write-routing failures** — Edit fails after worktree
   removal; Read-first dance (3 repos). → direct-to-candidate.
9. **Subagents idle without delivering; stale idle notifications** — coordinator must
   detect and re-ping (2 repos; also reproduced live in this very session). → theme 6.
10. **Local-vs-CI verification parity gaps** — CI red on checks local runs passed (2
    repos). → theme 11.

Singletons carried forward: bare `uv publish` globbing a Dart tarball into the Python
publisher; **350–450k tokens in <20 min for read-only recon fan-outs** (cache-economics
number); **Claude+Codex independent syntheses converging 15/17, hand-reconciled** (theme 5
prior art); `gh pr merge --auto`/`--delete-branch` behavior surprises; stacked-PR
auto-close + CI branch-trigger gap; mermaid syntax never validated by check_docs.py (13
broken diagrams shipped); AWS SSO interactive login as a structural background-automation
constraint; a probe script overwriting a FAIL evidence artifact with a later PASS
(audit chain-of-custody).

## 8. Final theme roster (Gate B decision object)

**Dispatch themes** (each gets the full 6-frame divergent treatment in Phase D):

1. External-LLM integration across the lifecycle (constrained by never-gatekeepers +
   chaperone-dispatch decisions)
2. Provider/model routing beyond CLI engines (one router plugin, registry-driven — intake)
3. Model/effort tier-palette currency (fable/xhigh reachability; effort in agent
   frontmatter; QUEUED per-teammate-effort seed)
4. Cache economics & worker reuse (constrained by worker-cache-scheduling; 350–450k recon
   number)
5. Consensus-protocol portability (gated-vs-advisory split preserved; 15/17 convergence
   prior art)
6. Agent-team & gate lifecycle: teardown, pause points, liveness (teardown gap, stale
   worktrees, idle-without-delivering). Gate-B resolution: AskUserQuestion primitive
   reliability struck — harness-level, out of scope for this backlog.
7. Lifecycle auto-progression & the ship ceremony (8-repo manual ritual; stacked-PR gaps)
8. /outcome intent capture & Objective ingestion (envelope autonomy per intake)
9. Standards/ADR enforcement locus (context-library conventions outward; board/field drift)
10. Cross-repo learning-mining & provenance discipline (promote loop never fired; 219
    codex sessions dark; stale-claim pattern; evidence integrity)
11. Fleet quality: comprehensive code review + agent-prompt audit + local-vs-CI parity +
    release-surface drift automation
12. Operator-facing model/effort levers (mode-dependent spend lever; tier recommendations)
13. Rate-limit-aware concurrency governance (VERIFY_N_CAP to extend; /optimize's shed
    knob to engage; aspiration-not-machinery finding)
14. Contract/vocabulary propagation & drift guards (4-repo churn evidence)
15. Delegation integrity — silent-no-op detection across all bridges (agy silent
    fallback; dead-wiring learnings)

**Direct-to-candidate pool** (pre-grounded, narrow; skip divergent frames, enter Phase E
convergence directly as seed candidates): saga scratch-dir gitignore hygiene;
worktree/background write routing; uv-publish glob guard; gh CLI behavior docs; stacked-PR
CI-trigger support; mermaid validation gap; AWS SSO constraint doc; evidence-artifact
immutability; all §5 QUEUED items; operator raw-notes appendix items not already themed.
