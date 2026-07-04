# Phase E Decision Brief — what consolidation means, with real examples

Everything referenced here is reviewable on disk:
**full archive** (all 796 ideas, all verdicts, all kill reasons) at
`docs/plans/plugin-fleet-ideation-2026-07-03/` — `pool-final.json`, `survivors/*.json`,
`dedup-map.json`, `objectives-draft.json`. Appendix A below has the full text of one real
near-neighbor cluster; Appendix B has a 25-survivor sample.

## 1. Why 403 survivors aren't 403 duplicates — and aren't 403 deliverables either

Dedup killed only same-move pairs (42). What remains includes **near-neighbor families:
same target, different mechanism**. The effort/tier family (Appendix A, full text):

| id | mechanism it proposes |
|---|---|
| T12-F2-5 | one dispatch-time **tier resolver seam** replacing N hardcoded `model:` fields |
| T12-F1-2 | **run-start posture** (thrifty/balanced/premium) seeding the per-unit table |
| T12-F1-3 | mandatory **"worth it because…" + named cheaper fallback** on every above-baseline row, validator-enforced |
| T12-F2-7 | **/tier session ceiling** replacing mid-run model-change pauses |
| S-1 | **per-teammate effort** in team-execution (your QUEUED seed) |
| G-hybrids-5 | the gap-synthesis agent's own pre-merge of four of the above |

Six distinct mechanisms — the critics were right not to kill them as dups. But nobody
would ship six PRs; they'd ship roughly two.

## 2. What a consolidated result looks like (mock, from that cluster)

**Issue 1 — "Dispatch-time tier resolver: one seam for model/effort across the fleet"**
(capability, structural, wave-1, absorbs T12-F2-5 primary + G-hybrids-5 + S-1 + T3-F1-7)
- Problem: every agent frontmatter hardcodes `model:`, zero `effort:` fields exist,
  fable/xhigh unreachable outside saga plan vocab (grounding brief §1).
- DoD: a resolver module in saga scripts that maps (role-class, declared effort, palette)
  → concrete tier at dispatch time; team-execution worker/reviewer spawns consume it;
  per-teammate effort becomes a plan-dictated field. New-model onboarding = one palette
  entry.
- AC: each absorbed idea becomes one acceptance criterion (resolver seam; effort field
  round-trips ExecutionSpec→team dispatch; per-teammate override honored; palette is
  single-source).
- Executor: sonnet / high, inline backend, no external LLM.

**Issue 2 — "Spend-posture UX: run-start ask, worth-it receipts, session ceiling"**
(enhancement, structural, wave-1, absorbs T12-F1-2 + T12-F1-3 + T12-F2-7)
- DoD: `posture` field on ExecutionSpec seeded by one run-start question;
  validator hard-blocks above-baseline rows lacking "worth it because…" + named cheaper
  rung; `/tier <ceiling>` session command.

Six survivors → two issues. **Nothing deleted**: every absorbed id is cited in its issue
and the full text stays in the archive. **What you actually lose**: the ability to
schedule T12-F1-3 separately from T12-F1-2 without splitting the issue later — ticket
boundaries, not content. The judgment of *where* to draw those boundaries (1 issue? 2? 3?)
is exactly the task the consolidation architects do 100+ times.

## 3. The ten draft Objectives (from clustering; membership incomplete — Phase E completes it)

| Wave | Objective | Mission (verbatim from clustering agent) |
|---|---|---|
| 1 | Ship run-start intent envelope for lifecycle autonomy | one committed intent/posture envelope captured at start, so spend + autonomy gates read a single settled contract |
| 1 | Make tier + effort a first-class, priced, resolvable lever | scattered literals → dispatch-time resolver, effort field, cheaper-fallback receipts; premium visible, default cheap, auditable |
| 1 | Stand up the external-engine offload lane | codex/agy/Ollama/DeepSeek as governed delegation surface with proof-of-execution guards + bridge lie-detector tests |
| 1 | Govern fleet concurrency and reclaim leaked resources | one admission-control governor (cap, backoff, shed, lease broker) + liveness/reclamation in front of every spawn site |
| 2 | Build the fleet telemetry and ledger substrate | one append-only run-fact spine for spend/cache/engine/delegation; before-baselines; "better" measured, not vibed |
| 2 | Enforce context-library standards at authoring time | llms.txt-indexed standards wired into issue/plan/review flows; ADR-to-code review lens; staleness manifests |
| 2 | Establish single-source-of-truth for shared primitives | extract the consensus kernel once; forbid hand-copied contract mirrors; parity registry so drift is structurally impossible |
| 2 | Gate fleet integrity: agent files, prompts, release surfaces | CI lints for frontmatter/prompt contracts; diff-aware release-surface guards; lifecycle regression harness |
| 3 | Make the backlog and lifecycle self-improving | journal plugin; revisit-when tripwires; throughput-paced backlog admission; PR-thread mining; fold this program back into /ideate |
| 3 | Expand saga + deploy capability breadth (misc/quick-wins) | multi-repo outcome arcs; resume relevance ranking; deploy canary/verify/revert |

## 4. Proposed Phase E (your Fable suggestion adopted — Fable consolidates, it doesn't re-check)

| Stage | Model / effort | Agents | Concurrency | Role |
|---|---|---|---|---|
| E1a Consolidation architects, by domain | fable / xhigh | 5 (~80 ideas each) | 3 | Draw ticket boundaries; cite every absorbed id; per-domain issue map |
| E1b Cross-domain reconciler | fable / xhigh | 1 | 1 | Merge cross-domain overlaps; finalize Objective list; hard partition contract |
| E1c Partition verification | haiku / low | 1 | — | Mechanical: all 403 ids land exactly once (anti-silent-drop) |
| E2 Issue drafting | sonnet / medium | ≈100–150 (data-driven) | 3 | Full Issue Quality Contract bodies → `docs/sdlc-issue-drafts/plugin-fleet/` |
| E3 Contract lint | haiku / low | ~10–15 | 6 | Field presence, id coverage, release-surface checklist — your concurrency bump, safe here |

Domain split: A autonomy+ship (T7,T8) · B tiering+levers+cache (T3,T12,T4) · C
engines+providers+delegation (T1,T2,T15) · D concurrency+teams+consensus (T13,T6,T5) ·
E quality+standards+contracts+knowledge (T9,T10,T11,T14) — seeds/OTHER routed by content.

Envelope: ~6–10M subagent tokens, ~2.5–3.5h. Known data defect E2 must fix: seed entries
(e.g. S-1) carry thin bodies (null idea text) — drafters flesh them from the QUEUED anchor
and grounding brief.

## 5. The two decisions

1. **Granularity/mechanism:** Fable consolidation (recommended) · Opus consolidation
   (same architecture, cheaper tier) · one-issue-per-survivor (~403 issues, no merging).
2. **Envelope approval** for the table above.

---

## Appendix A — the effort/tier cluster, full text

### S-1 — Per-teammate effort selection in team-execution (plan-dictated)
[T3/seed, structural]
null
BASIS (direct): QUEUED anchor {#team-execution-per-teammate-effort} (brief §5); directly matches operator ask 'why can't I pick effort per teammate?'
OUTCOME: null

### T12-F1-2 — Run-start tier posture asked once, seeding the per-unit table instead of per-unit interrogation
[T12/lever-placement, structural]
The per-unit confirm loop asks about tiers after the whole table is built, which is late and repetitive; the intake resolution says the spend lever should be 'asked once per run start, mode-based recommendation.' Add a single run-start posture selector (thrifty / balanced / premium, mode-aware: unattended defaults thrifty-silent, attended surfaces the choice) that seeds every unit's default tier before the table is rendered, so the operator confirms a table already shaped by their posture rather than reasoning rung-by-rung. The posture becomes a field on the ExecutionSpec so /work re-emits it and the choice survives. This moves the decision point earlier and collapses N per-unit micro-decisions into one.
BASIS (direct): Intake brief §Resolved tensions 1: 'Asked once per run start, mode-based recommendation' and unattended→silent-cache-first / attended→always-ask asymmetry. Grounding §7 pattern 6: 'operator asking for mid-run model-change pauses' + 'manual per-unit tier tables' — the current per-unit locus (`plan/SKILL.md:306`) is the friction. Engages intake tension 1's mode-based rule directly.
OUTCOME: PR adding a `posture` field + validation to `plugins/saga/scripts/execution_spec.py` and a run-start posture step to `plan/SKILL.md` §5.2a; verified by an execution_spec unit test asserting posture seeds per-unit defaults and round-trips through to_dict, plus release-surface bump.

### T12-F1-3 — Mandatory 'worth it, because…' + named cheaper fallback on every above-baseline tier row
[T12/recommendation-quality, structural]
The /plan tier table has a Rationale column but no per-row cheaper fallback, and Fable appears only as 'available as a per-unit override, never a default' with no worth-it justification. Make every row above the sonnet/medium baseline (opus, fable, xhigh) carry two required fields: a one-line 'worth it because…' and the explicitly named adjacent-cheaper rung it beats, computed from the ordered tier ladder via the same index arithmetic segment_units() already uses. The validator hard-blocks an above-baseline unit that ships without both. This makes premium spend always self-justifying and always one keystroke from a documented downgrade.
BASIS (direct): Intake brief §Resolved tensions 4: 'Fable-tier line in any plan or issue carries recommendation plus cheaper fallback; expensive never silent default.' `plan/SKILL.md:304` shows fable is mentioned but with no fallback field. `{#tier-vocab-ordering}` (LEARNINGS.md:164-179) confirms MODELS/EFFORTS are ordered ladders whose adjacent-cheaper rung is computable by index arithmetic — engaged directly as the mechanism for naming the fallback.
OUTCOME: PR editing `plan/SKILL.md` §5.2a tier-table spec + adding `fallback`/`justification` fields with validate() hard-block in `execution_spec.py`; verified by a new test asserting an above-baseline unit missing either field fails validate, plus release-surface bump.

### T12-F2-5 — One dispatch-time tier resolver seam instead of N hardcoded model: fields
[T12/lever-placement, structural]
The lever exists at exactly one authoring point (cc-workflows-ultracode plan tiers); every other spawn — team-execution workers, verify-panel judges, readonly-verifier calls — hardcodes model with no override. Rather than sprinkle a prompt at every spawn (noise the operator will hate), collapse the 'which decision points ask' question to ONE: a resolve_tier(unit, repo_defaults, session_override) resolver that all spawn sites funnel through, so the lever is set once at run start and applied everywhere. A drift-guard test enumerates spawn sites and asserts each routes through the resolver, mirroring the existing sandbox-spawn-sites.md inventory discipline.
BASIS (direct): Grounding brief §1 lines 18-20: 'Every agent frontmatter across all 8 plugins hardcodes model: (opus/sonnet/haiku), zero effort: fields... no dispatch-time override lever anywhere except saga's readonly-verifier per-call pattern.' Engages {#operator-choice-framework} (revisit-when it stops being doc-only/CLI-driven): a single CLI-invoked resolver reading config keeps operator-choice CLI-driven and centralizes it rather than injecting runtime blobs.
OUTCOME: Merged PR adding plugins/saga/scripts/tier_resolver.py, refactoring execution_spec._agent_opts and the team worker-table render to call it, plus a spawn-site drift-guard test (list of sites, each asserted to route through resolve_tier). Verified by that enumeration test and by existing emit/render tests staying green.

### T12-F2-7 — /tier session ceiling: automate away the mid-run model-change pause
[T12/choice-persistence, structural]
Session mining caught operators pausing mid-run to ask for a model change — a manual interruption with no lever. Replace the pause with a persisted session ceiling: a /tier command writes a run-scoped cap (e.g. 'nothing above sonnet/medium this run') to a session-local override file, honored by the tier resolver so all subsequent spawns clamp to it without re-prompting. The operator sets intent once and the run self-enforces it; the recurring interrupt-and-negotiate step is removed.
BASIS (direct): Grounding brief session-mining pattern #6 line 133: 'operator asking mid-run model-change pauses' (ranked recurring pain across 3 repos). Engages {#operator-choice-framework} (revisit-when it stops being doc-only/CLI-driven): /tier is a CLI command writing a config file the resolver reads, staying within the CLI-driven operator-choice envelope rather than introducing runtime injection.
OUTCOME: Merged PR adding a /tier command doc + a session-override file schema + resolver clamp logic + tests. Verified by a test that sets a sonnet/medium ceiling and asserts a subsequently-resolved opus/high unit is clamped to the ceiling with a logged downgrade and no prompt.

### T3-F1-7 — A 'new model onboarding' kit that makes adding Claude 6 a one-file change with a self-arming guard
[T3/palette-drift-proofing, quick-win]
The `{#tier-vocab-ordering}` learning exists because enabling `fable`/`xhigh` LOOKED like 'append two tuple entries' but a wrong insertion point silently mis-tiered every merge and passed validation. Ship a runbook (`plugins/saga/references/tier-palette.md`) plus a generated guard-test template that, for any model/effort tuple, asserts the intended strength ordering AND greps for every `.index(` call over the tuple so a future addition that breaks a second (ordering) contract fails loudly. The kit encodes the learning's own generalizable rule ('grep for `.index(` before extending a closed vocabulary') as executable machinery, so the next model arrives without a fleet-wide manual audit. This is the drift-proofing that turns a remembered gotcha into a standing gate.
BASIS (direct): LEARNINGS.md:164 `{#tier-vocab-ordering}` — Evidence cites `execution_spec.py:49-56`, `segment_units()` merge, and guard test `test_segment_tier_merge_prefers_fable_and_xhigh`; Generalizable rule: 'grep for `.index(` on it — a tuple used for membership and ordering has two contracts.' This idea operationalizes that exact rule; it honors, not contradicts, the binding learning.
OUTCOME: PR adding `plugins/saga/references/tier-palette.md` (onboarding runbook) + a parametrized ordering/`.index(`-coverage guard test in `tests/test_team_emitter.py`/`test_tier_vocab_single_source.py`. Verified: intentionally mis-inserting a fake `"model6"` at the wrong index makes the guard test red; correct prepend makes it green.

### G-hybrids-5 — Dispatch-time tier resolver: single palette source, effort field, because+fallback, priors from the ledger
[T3/tier-resolver-with-priors, structural]
Fuse the tier-currency stack into one seam: T3-F4-1's shared palette module (kill the literal-string scatter), H-F4-2's dispatch-time resolver (instead of 24 frontmatter edits), T3-F2-3's effort-injection shim generalizing the readonly-verifier per-call pattern, T12-F3-2's requirement that every recommendation emit a 'because' plus a cheaper fallback, and H-F4-4's cost-fact priors so the 'because' cites measured history instead of re-reasoned vibes. The resolver takes (role_kind, work_shape, envelope tier ceiling) and returns (model, effort, because, cheaper_fallback), reading the run-fact ledger for precedent. This makes fable/xhigh reachable everywhere, retires hardcoded model: fields incrementally, and satisfies the never-silent-expensive rule structurally.
BASIS (direct): Grounding brief §1: 'The fleet's ONE operator-facing model/effort lever: saga /plan's unit tier table... Every agent frontmatter across all 8 plugins hardcodes model:, zero effort: fields (0 of 24 in team-execution)... fable/xhigh unreachable outside saga plan vocabulary' — plus QUEUED seed {#team-execution-per-teammate-effort} (§5). Parents H-F4-2, T3-F4-1, T3-F2-3, T12-F3-2, H-F4-4 partition the fix; separately they leave either the vocabulary scattered, the effort field dead, or the recommendation unjustified. Respects {#tier-vocab-ordering}: the resolver's fallback is one rung down the ordered ladder.
OUTCOME: PR adding tier_resolver.py beside execution_spec.py (palette imported, not copied), an effort-injection spawn shim, and first consumer wiring in team-execution's A7 worker table; verified by unit tests for resolution + fallback ordering and a drift-guard failing on any new hardcoded palette literal.


## Appendix B — 25-survivor random sample (id · theme · tier · title · first sentence)

- **G-negative-space-11** [NEW:dark-plugin-parity, incremental] The dark half of the fleet: an explicit in-or-out verdict and primitive-parity pass for deploy, home-lab-ops, unifi, and redis-channel — The grounding brief maps 8 plugins; the 15 themes and ~771 ideas concentrate almost entirely on saga, team-execution, mission-control, and agy
- **S-17** [T10, structural] Evidence-artifact chain-of-custody (no overwrite) — (seed: body drafted in Phase E)
- **S-36** [T11, structural] Full comprehensive code-review — (seed: body drafted in Phase E)
- **T1-F3-7** [T1, moonshot] The registry calibrates itself from real reconciliation outcomes — retro-gated — (seed: body drafted in Phase E)
- **T10-F3-8** [T10, structural] Closed-loop retirement — a merged fix must silence its originating pattern — The mining→issue pipeline is assumed one-directional: patterns flow out, issues get filed, done
- **H-F5-3** [T10, quick-win] Chain-of-custody evidence ledger with content-addressed immutability — Forensic evidence handling and blockchain both solve 'prove this artifact was not silently overwritten' via content-addressing and an append-only custody log
- **T11-F4-2** [T11, structural] One durable agent-prompt scorecard doc scoring all 34 agents on a written quality rubric — (seed: body drafted in Phase E)
- **G-hybrids-13** [T11, structural] One agent-file CI lint: frontmatter schema, tier/effort fields, prompt rubric, and cache-prefix stability — (seed: body drafted in Phase E)
- **T12-F4-6** [T12, structural] A mid-run /tier lever that re-emits from the canonical spec instead of restarting — Mining records operators 'asking mid-run model-change pauses' — today changing a tier mid-flight means aborting and re-planning
- **T13-F1-2** [T13, structural] A single concurrency-policy block in execution_spec with a resolution ladder (spec default → env → run override) — Today the only cap lives as a bare `VERIFY_N_CAP` literal; there is no home for a general concurrency knob, so every proposal scatters magic numbers
- **T13-F6-7** [T13, structural] Per-lane concurrency: max_concurrent as an engine-registry field — Flip 'the cap is one global number' — that is wrong the moment provider routing lands: a local Ollama lane ($0 offload target) can run 100 concurrent while the Anthropic lane must stay ≤3, because rate limits are per-provider, not fleet-uniform
- **T14-F3-7** [T14, quick-win] Byte-parity is not behavioral-parity: lock the validator against a real-card verdict corpus — The 343-card disaster was not a byte problem — the mirror parsed fine and passed its own tests; it simply DISAGREED with the live contract on real inputs, surfacing only when real cards hit production
- **T14-F6-6** [T14, structural] Pin-vs-float compat manifest: auto-adopt additive contract changes, gate only breaking ones — Flip both extremes — 'everything pinned' vs 'everything floats' — to mine the middle kernel
- **T15-F2-2** [T15, structural] Provider-registry receipt guard: no bridge enters the router without proof-of-execution wiring — (seed: body drafted in Phase E)
- **T15-F5-2** [T15, structural] Server-authoritative output attestation: the delivered diff must be one only the engine's run could emit — (seed: body drafted in Phase E)
- **T2-F3-3** [T2, structural] Widen the capability vocabulary to what local models are actually for — (seed: body drafted in Phase E)
- **H-F6-3** [T2, structural] Zero-token fire drill: run one canonical lifecycle loop entirely on the $0 registry entry and publish the irreducibility map — (seed: body drafted in Phase E)
- **T3-F4-6** [T3, quick-win] Fleet-wide agent-frontmatter tier lint wired into CI — The execution_spec validator only guards tiers authored in a spec JSON; the 33 agent frontmatters that hardcode model: are unchecked, so a typo or a retired model name ('opus-4', 'med') sits latent until spawn
- **T4-F2-2** [T4, structural] Remove the runtime shed judgment — saga emits an explicit shed/summary-handoff marker per segment boundary — R11 and KTD7 admit there is no live context-GC lever, so shedding is a runtime judgment a resident worker must make from markdown prose — a manual, untestable decision KTD4 concedes is "markdown protocol only." Automate the step away by moving the decision to where the data already lives: saga's segmentation derivation stamps each emitted worker row with an explicit boundary action — reuse, summary-handoff, or shed — so team-execution executes a derived instruction instead of re-deciding at runtime
- **T4-F6-8** [T4, quick-win] Cache-prefix stability regression guard in CI — Flip to 'a refactor can never silently break the cache': resident cache reuse depends on `segment_units()` producing byte-stable resident prefixes across runs, but nothing pins that — a benign refactor to the emitter or an agent prompt can reorder a prefix and quietly convert every re-engagement from a cache hit to a cache miss, invisible until a token bill spikes
- **T5-F4-5** [T5, structural] One shared lens/reviewer registry feeding both consensus loci — Reviewer membership is defined twice with divergent selection models: team-execution's reviewer-registry.md (keyword-triggered optional reviewers atop a fixed base 3) and saga /code-review's judgment-selected lens-catalog (4 always-on + conditional)
- **T6-F5-3** [T6, structural] Phi-accrual failure detector for subagent liveness — (seed: body drafted in Phase E)
- **T7-F2-2** [T7, quick-win] Idle-triggered worktree reclamation — automate the cleanup nobody ever does — (seed: body drafted in Phase E)
- **T7-F6-2** [T7, moonshot] Envelope-authorized merge in the /outcome autonomous allowlist — (seed: body drafted in Phase E)
- **T8-F3-8** [T8, structural] A HALT is a latent renegotiation point, not just a dead stop — (seed: body drafted in Phase E)
