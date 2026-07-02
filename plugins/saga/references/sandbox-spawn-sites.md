# Sandbox spawn-site inventory (#287 U4)

Every delegated-agent spawn site in the `saga` plugin, classified against the two-axis sandbox
contract (`mutation_policy` x `workspace_isolation`, see `docs/plans/2026-07-02-capability-scoped-
sandbox-plan.md`). Absent sandbox = R1 default (ambient x read-write, today's behavior).

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

| Skill | File | Spawn site |
|---|---|---|
| `code-review` | `plugins/saga/skills/code-review/SKILL.md` | Phase 3 lens fan-out (~line 164) |
| `qa` | `plugins/saga/skills/qa/SKILL.md` | Phase 2 parallel verification (~lines 170-171) |
| `investigate` | `plugins/saga/skills/investigate/SKILL.md` | Phase 2 parallel read-only sub-agents (~lines 211-216) |
| `resume` | `plugins/saga/skills/resume/SKILL.md` | Phase 3b Tier-2 synthesis dispatch (~lines 232-233) |

Also in-scope (already wired, U2, not this unit's edit): the three verifier-emitting sites inside
`plugins/saga/scripts/execution_spec.py` — `_emit_verify_panel`, `_emit_verify_loop_singleton`, and
the parallel-layer thunk's inlined iterate-to-consensus loop — each emits `agentType:
'saga:readonly-verifier'` and `isolation: 'worktree'` in every verifier `agent()` call
unconditionally (KTD6).

## Out-of-scope (with rationale)

| Site | Rationale |
|---|---|
| team-execution reviewer/validator registry (`plugins/team-execution/skills/team-execution/...`) | KTD3: team-execution residents run `bypassPermissions` with no per-leaf tool-restriction consumer in v1. Routing a restrictive sandbox at team-execution HALTs at authoring time instead of enforcing anything. Its own reviewer/validator protocol (architecture/security/devils-advocate reviewers, scanner/tester validators) is unchanged and out of scope for this unit. |
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
