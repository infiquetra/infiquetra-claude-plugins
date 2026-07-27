# Sandbox spawn-site inventory (#287 U4)

Every delegated-agent spawn site in the `saga` plugin, classified against the two-axis sandbox
contract (`mutation_policy` x `workspace_isolation`, see `docs/plans/2026-07-02-capability-scoped-
sandbox-plan.md`). Absent sandbox = R1 default (ambient x read-write, today's behavior).

Executable fan-out admission is tracked separately in
`plugins/saga/references/concurrency-spawn-sites.md`. Verify-panel rows appear conceptually in both
inventories because they require both containment and bounded admission, but each inventory keeps
its own machine contract.

Three classes:

- **in-scope** — attach the `read-only-verify` profile (`mutation_policy: read-only` x
  `workspace_isolation: disposable-worktree`): `subagent_type: saga:readonly-verifier` +
  `isolation: "worktree"`.
- **out-of-scope** — deliberately NOT sandboxed here, with rationale.
- **default** — no sandbox; R1 ambient x read-write (today's behavior), because the leaf must
  write (a builder).

## In-scope: verify/review-class skill spawns

Each of these four skills spawns verify- or review-class sub-agents whose job is to *check*, not
*build*. Each now names `subagent_type: saga:readonly-verifier` and `isolation: "worktree"` at its
spawn site.

| Skill | File | Spawn site | Resolver work-shape (#362 U5) |
|---|---|---|---|
| `code-review` | `plugins/saga/skills/code-review/SKILL.md` | Phase 3 lens fan-out (~line 164) | `judgment` |
| `qa` | `plugins/saga/skills/qa/SKILL.md` | Phase 2 parallel verification (~lines 170-171) | `judgment` |
| `investigate` | `plugins/saga/skills/investigate/SKILL.md` | Phase 2 parallel read-only sub-agents (~lines 211-216) | `read-only-survey` |
| `resume` | `plugins/saga/skills/resume/SKILL.md` | Phase 3b Tier-2 synthesis dispatch (~lines 232-233) | `judgment` |

Also in-scope (already wired, U2, not this unit's edit): the three verifier-emitting sites inside
`plugins/saga/scripts/execution_spec.py` — `_emit_verify_panel`, `_emit_verify_loop_singleton`, and
the parallel-layer thunk's inlined iterate-to-consensus loop — each emits `agentType:
'saga:readonly-verifier'` and `isolation: 'worktree'` in every verifier `agent()` call
unconditionally (KTD6). Resolver work-shape: `judgment` (verify/refute-class work — same shape as
the four skill spawns above).

**Resolver work-shape column (#362 U5, R7):** each row above names the `tier_policy.json` registry
key (or `role-tier:` alias, KTD7) that `fleet_commons.tier_resolver.resolve()` would use to tier
this spawn site — a routing pointer, not a claim that the site dispatches a model today (the four
skill spawns above name a `subagent_type`, not a `{model, effort}` tier). Every entry here must be
a real registry key or `role-tier:` alias — `tests/test_tier_resolver.py::
test_spawn_site_enumeration_routes_through_resolver` fails the moment a new bare palette literal
(e.g. a hardcoded `opus` / `haiku` string instead of a work-shape key) lands in this column.

## Out-of-scope (with rationale)

| Site | Rationale |
|---|---|
| team-execution reviewer/validator registry (`plugins/team-execution/skills/team-execution/...`) | KTD3: team-execution residents run `bypassPermissions` and are deliberately NOT routed through saga's `mutation_policy`/`workspace_isolation` sandbox mechanism — routing a restrictive sandbox at team-execution HALTs at authoring time instead of enforcing anything. What IS enforced there is the authored `tools:` frontmatter: it is the spawn-time capability roster a dispatcher reads to scope a leaf (the same mechanism `readonly-verifier` uses), and `tools/agent_spec.py`'s tool-scope floor CI-lints it on review-class agents (#422). Out of scope here means the saga sandbox routing only, not the `tools:` roster. Its own reviewer/validator protocol (architecture/security/devils-advocate reviewers, scanner/tester validators) is unchanged and out of scope for this unit. |
| `/agy:delegate` junior-draft loop (`plugins/agy/scripts/agy_delegate.py`) | Settled decision `{#agy-delegated-build-no-jail}` (`docs/engineering-journal/DECISIONS.md`): this loop deliberately uses post-hoc verification (diff review after the fact), not pre-hoc isolation. Do not re-jail it. |
| `mechanical-executor` agent (`plugins/saga/agents/mechanical-executor.md`) | Already Bash-only — no Edit/Write tool in its toolset. No additional `mutation_policy: read-only` restriction is needed; it has nothing further to omit. |
| Builder leaves (any unit whose job is to write code/docs) | R1 default: ambient x read-write. A builder leaf must write — sandboxing it would break its own contract. This is today's unsandboxed behavior, unchanged. |

## Ad-hoc spawn rule

Any verify- or review-class Agent-tool spawn made **outside** a skill listed above (a one-off
adversarial check, an ad-hoc "have a sub-agent double check this" dispatch, a new skill added later
that spawns a verifier) **MUST** pass:

- `subagent_type: saga:readonly-verifier`
- `isolation: "worktree"`

This is the least-instruction-guarded spawn class — nothing in a skill file catches it — so the rule
lives here as the one place every agent reading repo context can find it. The repo-root `CLAUDE.md`
carries a one-line pointer to this section.

## Fallback when `saga:readonly-verifier` is unavailable (#325 Key Technical Decision 1)

Agent rosters change between sessions — the mandate above must not become a hard failure just
because the current session's plugin roster predates a just-merged agent (this is exactly what
happened in #325: `saga:readonly-verifier` was merged via #287/#320 but a session loaded before
that merge could not resolve it). When a spawn following the ad-hoc rule above fails to resolve
`saga:readonly-verifier`, degrade through this two-step ladder instead of failing the spawn
outright or silently reverting to an unsandboxed spawn:

1. **`subagent_type: Explore` + `isolation: "worktree"`.** The built-in `Explore` agent type
   structurally lacks `Edit` / `Write` / `NotebookEdit` while retaining `Bash` — so the
   `mutation_policy: read-only` axis survives by tool omission, the same enforcement mechanism
   `saga:readonly-verifier` uses, not a prose instruction hoping the agent complies. Preserved:
   both sandbox axes (read-only by tool omission, worktree isolation). Lost: the verifier-specific
   system prompt (the REFUTE-first framing, the structured `{refuted, upheld}` verdict contract) —
   restate that framing in the dispatch prompt itself.
2. **`subagent_type: general-purpose` + `isolation: "worktree"` + an explicit read-only
   instruction in the prompt** — only if `Explore` is *also* absent from the session. Preserved:
   worktree isolation (accidental-clobber protection per KTD7 below). Lost: the structural
   mutation-by-tool-omission guarantee — `general-purpose` retains `Edit`/`Write`, so read-only is
   now a request, not an enforced constraint. This is the terminal rung because `general-purpose`
   is the harness's default agent type and is assumed always present.

A rung applies only when its named agent type is actually present in the current session's roster
— do not assume `Explore` exists any more than the original mandate assumed
`saga:readonly-verifier` did; the same staleness class that motivated this ladder can affect any
agent type. If neither rung resolves, surface the gap to the operator rather than spawning
unsandboxed.

### Recording rule — carry the fallback depth (#390 U6, R8, KTD7)

Descending this ladder is never silent. An **inline** spawner (a Claude-prose spawn following the
ad-hoc rule, not a workflow `agent()` call) that drops to rung 1 or rung 2 MUST carry the rung
index as `fallback_depth` into whatever verdict or tick it records: first-choice
`saga:readonly-verifier` is `fallback_depth: 0`, the `Explore` rung is `fallback_depth: 1`, the
`general-purpose` rung is `fallback_depth: 2` — alongside the `verifier_identity` of the agent type
actually spawned. The panel gate summary keys off exactly these two fields to render an explicit
"fallback tier N" marker naming the degraded reporter (see
`render_fallback_tier_marker` in `execution_spec.py`), so a run that quietly degraded its verifier
cannot pass as a first-choice pass. Workflow `agent()` calls need no manual recording — the emitter
stamps `fallback_depth: 0` because an unresolvable `agentType` fails the call outright rather than
descending. This is attribution only; the ladder's order and contract are unchanged (binding
decision `{#readonly-verifier-fallback-ladder-325}`).

## KTD7 residual boundary (documented, not defended)

A git worktree shares `.git` with the primary checkout. A `git push` or a branch-ref mutation run via
`Bash` inside a disposable worktree is therefore still *possible* — the isolation axis defends
against **accidental clobber** (a stray `git checkout <tracked>` or `git reset` overwriting
uncommitted work in the primary tree), not against a deliberate or adversarial push. This is outside
the accidental-clobber threat model this unit addresses (issue D2) and is documented here as a known
boundary rather than defended against. The external-engine face (`sandboxed-mutate`, U5) has a
stronger answer for its own threat model: it dispatches against a remotes-stripped clone that cannot
push at all, because that face's harvest path already required patch-only clone isolation
independent of this sandbox contract.
