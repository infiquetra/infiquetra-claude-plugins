---
date: 2026-06-29
topic: antigravity-plugin-socratic-seeds
focus: Claude Code Antigravity plugin reliability and custom Infiquetra plugin shape
status: seed-notes
---

# Socratic Seeds: Antigravity Plugin Direction

## Grounded Context

- Current pain is not just Antigravity quality; it is Claude Code harness behavior around
  `/agy:delegate`, provenance, runner lifetime, and fallback detection.
- Existing `antigravity-cc/agy` prior art is intentionally a thin forwarder:
  Claude Code command to `agy:runner` to `agy-run.sh` to local `agy -p`.
- Hermes prior art treats Antigravity as an agent backend procedure: verify binary, auth,
  settings, logs, shell-vs-TUI command surface, and bounded `agy -p` runs.
- Local journal evidence says an apparent delegated agy run can silently be a Claude clone
  unless the transcript proves a real `agy` shell call.
- Local dogfood evidence says prompt guards alone did not prevent wander, rogue commit,
  rogue push, test-gaming, overclaim, or silent no-op failures.
- The strongest recurring design signal is authority/provenance: prove what process ran,
  bound what it may mutate, and have the orchestrator re-derive truth afterward.
- Existing delegate-agent ideation from 2026-05-30 recommended provider-neutral delegation,
  read-only reviewer/explorer delegates first, and Antigravity control-surface spike before
  write-capable coder delegation.

## Session Notes

### Round 1: What Problem Are We Actually Solving?

Prompt:

What is the single failure you most want a custom plugin to make impossible, or at least loud?

Candidate failure shapes to test against:

- Claude thinks it delegated to Antigravity, but no `agy` process actually ran.
- A long delegation hangs or detaches and returns no useful output.
- Antigravity writes outside the intended scope.
- Antigravity commits, pushes, or changes git state.
- Antigravity reports success without full evidence.
- Claude misuses the plugin because the exposed command shape invites the wrong action.

User answer:

Priority order:

1. Claude misuses the plugin because the command shape invites the wrong action.
2. Long jobs detach or hang.
3. Claude thinks it delegated, but no `agy` process ran.

Implication: treat command UX and exposed affordances as the first design surface,
before backend invocation mechanics. A safer plugin should make the intended action
obvious, make dangerous/raw routes harder to reach, and preserve evidence that the
selected route actually executed.

### Round 2: What Should The Claude-Facing Command Shape Be?

Prompt:

If misuse is the top failure, should the plugin expose one opinionated front door or
several specialized commands?

Tension to resolve:

- One front door can force safe defaults and evidence capture, but may become vague.
- Specialized commands can make intent explicit, but Claude may pick the wrong one.
- A raw runner can be useful for debugging, but it may invite exactly the misuse we
  want to eliminate.

User answer:

Primary surface should be agent-team integration, not just a quick slash command.

Desired shape:

1. Inline or single-session use can ask for a prompt to be delegated to Antigravity.
2. Agent-team workflows should allow choosing teammates that are Antigravity teammates.
3. The prompt that would have been run by a Claude Code team member should instead be
   executed by Antigravity.
4. Same concept should apply to subagents and ultracode-style workflows.
5. Preference is a preconfigured agent that always uses `agy`, rather than relying on
   each task prompt to remember "use agy."
6. Claude Code should mostly orchestrate: pick agy-based agent, pass prompt, receive result.
7. The agy-based agent should take the prompt, create an ideal `agy` prompt, call `agy`,
   then return to the orchestrator.
8. Multiple turns should also delegate each turn to `agy`, so the Claude teammate is a
   thin runtime bridge rather than the worker.
9. A secondary quick-use command like the existing plugin style is still useful.

Design implication: the main abstraction is an Antigravity-backed teammate role. The
safe command shape should make "delegate this teammate turn to agy" the default behavior,
with a secondary command for ad hoc one-shot delegation. A raw runner remains an internal
mechanism, not the product surface.

Open concern: previous failures may have been caused by background-session behavior, by
prompting, or by both. The design should not assume background delegation is healthy
without proving it.

### Round 3: Should Agy Teammates Be Stateful?

Prompt:

For an Antigravity teammate used across multiple turns, should each teammate preserve an
`agy` conversation/session identity, or should every turn be a fresh `agy` run with prior
context summarized in the prompt?

Tension to resolve:

- Preserving an `agy` conversation may make the teammate feel real and reduce repeated
  context, but increases state, recovery, and hang/detach complexity.
- Fresh runs are easier to prove and recover, but Claude may spend more tokens rebuilding
  context unless the plugin writes compact turn packets.
- A hybrid could keep a per-teammate evidence log and only use `agy --conversation` when
  the prior turn completed cleanly with a verified real `agy` invocation.

User answer:

Agree with fresh-by-default. Agy teammates should not preserve an `agy`
conversation/session identity by default. Stateful `agy --conversation` should be
allowed only after the plugin proves clean provenance and no hang/detach behavior.

Design implication: every delegated teammate turn should be independently auditable:
Claude passes a compact turn packet, the agy bridge runs a bounded fresh invocation,
and the result comes back with enough evidence that the orchestrator can trust the
route happened without trusting the delegate's self-report.

### Round 4: What Evidence Must Every Turn Return?

Prompt:

What minimum evidence should an Antigravity teammate return to the orchestrator every
time, even for read-only work?

Candidate fields:

- original teammate prompt received from Claude Code
- rendered `agy` prompt actually sent
- exact `agy` command shape, without secrets
- process return code and wall time
- transcript/log path
- proof that an `agy` process was invoked
- final answer/result
- structured status: `success`, `timeout`, `no-output`, `fallback-suspected`, `error`
- for write-capable modes: changed paths and git-state proof

User answer:

Agree with the default evidence set. Evidence level should be configurable per
delegation so future workflows can reduce Claude Code token usage when the route has
proven reliable.

Design implication: evidence policy should be an explicit delegation option, not an
implicit omission. Early/default mode should return full evidence. Later modes can
return summarized evidence or evidence-by-reference, but the run should still write the
full local evidence bundle for audit/replay when needed.

Possible evidence levels:

- `full`: return key evidence inline plus write local bundle.
- `summary`: return status, result, and evidence path; keep details on disk.
- `minimal`: return status/result only, allowed only for low-risk read-only work after
  the plugin has proven stable.

### Round 5: What Modes Should Exist First?

Prompt:

Should the first version support only read-only Antigravity teammates, or should it include
a write-capable mode from the beginning?

Tension to resolve:

- Read-only teammates solve review, investigation, planning, and adversarial-lens work
  with much lower blast radius.
- Write-capable teammates are closer to the original "delegate worker" dream, but they
  need changed-path checks, git-state proof, verification gates, and recovery rules.
- A staged design can still name the write mode now while shipping it later.

User answer:

Write-capable Antigravity teammates are required from the start. Read-only-only v1
would not satisfy the core goal.

Design implication: v1 must include a write-capable delegation mode, not just reserve
schema space for it. The first version therefore needs changed-path checks, git-state
proof, bounded execution, full local evidence bundles, and explicit recovery behavior
for no-output, timeout, fallback-suspected, and out-of-scope mutation cases.

### Round 6: What Write Boundary Should V1 Use?

Prompt:

For write-capable Antigravity teammates in v1, where should Antigravity be allowed to
write?

Candidate boundaries:

- Directly in the current working tree, with a declared write-set and post-hoc checks.
- A per-delegation git worktree, then import the patch if it passes checks.
- A disposable clone with origin removed, then harvest a diff if it passes checks.

Tension to resolve:

- Current tree is simplest and preserves the teammate feel, but late writes and git misuse
  are harder to isolate.
- Worktrees isolate files better, but still share git state with the repo.
- Disposable clones are strongest against rogue git actions, but add setup and patch import
  complexity.

User answer:

Either boundary is acceptable as long as it actually works. Prior attempts hit
challenges with both worktree-style and clone-style isolation, so this should be
treated as an empirical implementation choice rather than a product preference.

Design implication: the Claude-facing API should not require the orchestrator to pick
`clone` versus `worktree` for normal use. V1 should expose a simple write-capable mode
and let the plugin choose a proven boundary internally, with a debug/override option
only for diagnostics. The chosen boundary must be validated by a spike, not assumed.

### Round 7: What Should The Orchestrator See On Write Delegation?

Prompt:

When Claude delegates a write-capable task to an Antigravity teammate, should the
orchestrator receive a patch/diff for explicit import, or should the plugin apply the
patch automatically after checks pass?

Tension to resolve:

- Returning a patch keeps Claude as explicit importer/reviewer, but adds one more manual
  step to every teammate turn.
- Auto-applying after checks preserves the teammate feel, but raises the bar for the
  plugin's checks and rollback behavior.
- A hybrid could auto-apply only when changed paths stay inside the declared write-set
  and checks pass, otherwise return the patch plus failure evidence for Claude review.

User answer:

Agree with hybrid behavior. Auto-apply only when the Antigravity run stays inside the
declared write-set and required checks pass. If the run changes out-of-scope paths,
times out, produces no output, has fallback-suspected provenance, or fails checks, return
the patch plus evidence for Claude/orchestrator review instead of applying.

Design implication: write-capable v1 needs an explicit apply policy:

- `auto-if-clean`: default for normal teammate use.
- `patch-only`: never apply; return diff/evidence.
- `no-write`: read-only mode.

### Round 8: How Explicit Should The Write-Set Be?

Prompt:

When delegating write-capable work, should Claude have to provide an explicit write-set
of allowed files/directories, or should the Antigravity teammate infer it from the task?

Tension to resolve:

- Explicit write-sets reduce wander and enable auto-apply checks.
- Inferred write-sets reduce orchestration friction, but can reproduce the old failure
  where the delegate edits plausible-but-unintended files.
- A hybrid could require an explicit write-set for auto-apply and allow inferred write-sets
  only in patch-only mode.

User answer:

Agree with explicit write-set for `auto-if-clean`. Inferred write-sets should be allowed
only for `patch-only`.

Design implication: the plugin should enforce "no explicit write-set, no automatic live
tree mutation." The Antigravity teammate may infer or propose additional paths, but those
become review evidence (`PLAN_GAP` / out-of-scope patch), not automatically applied edits.

### Round 9: How Should Teammates Be Selected?

Prompt:

How should Claude Code/team-execution choose Antigravity-backed teammates?

Candidate selection surfaces:

- Separate preconfigured agents, e.g. `agy-coder`, `agy-reviewer`, `agy-investigator`.
- A runtime flag on existing roles, e.g. same reviewer prompt but `runtime=agy`.
- A team roster file that maps role names to runtime/provider/model/evidence/apply policy.
- A slash command that creates or launches an Antigravity-backed teammate ad hoc.

Tension to resolve:

- Separate agents make misuse harder because the agent identity carries the runtime.
- Runtime flags preserve existing team prompts, but Claude can forget or misapply the flag.
- Roster mapping is explicit and scalable for teams, but adds configuration surface.

User answer:

Strongly agree with separate preconfigured agents, assuming Claude Code plugin mechanics
can support it.

Design implication: v1 should try to ship role-specific Antigravity-backed agents such
as `agy-coder` and `agy-reviewer`, where the agent identity carries
the runtime rule: always delegate the received task to `agy`; do not solve it directly.
Team roster/runtime mapping can exist as a higher-level configuration layer, but the
safe primitive should be a preconfigured agy-backed teammate.

Feasibility spike required: prove a Claude Code plugin-packaged agent can be constrained
enough to behave as a thin `agy` bridge, ideally with only the wrapper/tooling it needs
and without general repo mutation tools. If Claude Code cannot enforce that strongly,
the plugin must compensate in the wrapper and evidence/provenance checks.

### Round 10: What Models/Roles Should V1 Include?

Prompt:

Which Antigravity-backed teammate roles should v1 include by default?

Candidate roles:

- `agy-coder`: write-capable implementation teammate.
- `agy-reviewer`: read-only or patch-only reviewer/adversarial lens.
- `agy-investigator`: read/search-heavy debugging or codebase exploration teammate.
- `agy-planner`: plan/spec drafting teammate.
- `agy-general`: generic fallback, mostly for quick one-off delegation.

Tension to resolve:

- Fewer roles reduce misuse and implementation work.
- More roles make team workflows easier and reduce prompt adaptation per turn.
- A generic role is convenient, but can reintroduce ambiguity if Claude overuses it.

User answer:

Start with `agy-coder` and `agy-reviewer`. Do not include `agy-investigator` in v1 unless
later evidence shows it is necessary.

`agy-coder` must be very well defined and optimized to be a great coder, because Gemini
models, especially Flash models, have shown flaky behavior in the local dogfood evidence.
The coder role needs strong guidance, clear write boundaries, verification expectations,
and failure channels.

`agy-reviewer` may need to be more than one role. The important current pattern is
"second opinion" reviewer: adversarial, devil's-advocate, or independent critique. The
plugin should explore whether this is one reviewer role with selectable lenses or several
preconfigured reviewer agents.

Design implication: v1 default roles should be narrow:

- `agy-coder`: write-capable implementation teammate with strong coding protocol.
- `agy-reviewer`: second-opinion/adversarial reviewer, possibly lens-configurable.

Avoid `agy-general` and `agy-investigator` as default team roles in v1.

### Round 11: What Makes `agy-coder` Great?

Prompt:

What should the `agy-coder` prompt/protocol optimize for first?

Candidate priorities:

- Produce complete implementation plus tests inside the explicit write-set.
- Surface `PLAN_GAP` when required files are outside the write-set.
- Avoid git operations entirely; orchestrator owns commit/push.
- Run or request the right verification commands and report real output.
- Prefer small, focused diffs over broad cleanup.
- Explicitly stop on uncertainty instead of guessing or silently no-oping.
- Return patch/evidence in a shape the wrapper can verify.

User answer:

The contractor-style protocol is right, but `agy-coder` also needs stronger steering
than a newer model might require. The existing docs already contain prompt/template
material such as the blueprint task packet (`SYSTEM PREAMBLE`, write-set, `PLAN_GAP`,
`TEST-CONFLICT`, verification, run report). V1 should reuse that prior art and add a
stronger coder persona, e.g. "you are an expert software engineer" / production-grade
implementation framing, because Gemini models, especially Flash, need more explicit
guidance.

Design implication: `agy-coder` should have two layers:

1. Stable harness contract: write-set, no git, failure channels, verification report,
   evidence shape.
2. Strong role steering: expert software engineer, focused implementer, tests-first or
   tests-aware, production-quality diff, no broad cleanup, no bluffing.

The key is not replacing the safety contract with persona prompting. Persona/quality
steering should sit on top of the hard task packet.

### Round 12: What Reviewer Lenses Should Exist?

Prompt:

For `agy-reviewer`, should v1 ship one adversarial second-opinion reviewer with a lens
parameter, or multiple preconfigured reviewer agents?

Candidate reviewer lenses:

- adversarial/devil's-advocate: find what will break.
- implementation-quality: correctness, maintainability, tests.
- scope/plan-gap: missing work, hidden assumptions, under-specified requirements.
- security/ops risk: trust boundaries, secrets, deployment/runtime hazards.

Tension to resolve:

- One reviewer with a required lens is simpler.
- Multiple agents are harder for Claude to misuse because the agent name encodes the role.
- Too many reviewer agents could make team selection noisy.

User answer:

Agree with one `agy-reviewer` that defaults to adversarial/devil's-advocate, plus a
small required or explicit lens option for other review styles.

Initial lenses:

- `adversarial`: default second opinion; find what breaks, what is overclaimed, and what
  the main agent missed.
- `quality`: correctness, maintainability, tests, implementation soundness.
- `scope-gap`: missing work, hidden assumptions, under-specified requirements.
- `security-ops`: trust boundaries, secrets, deployment/runtime hazards.

Design implication: keep one reviewer agent in v1 to avoid noisy team selection. Split
into multiple named reviewer agents only if Claude repeatedly chooses the wrong lens or
the prompt packets become too divergent.

### Round 13: What Is The Quick-Use Command?

Prompt:

What should the secondary quick-use command do?

Candidate shapes:

- `/agy:ask`: one-shot read-only answer/review, no write.
- `/agy:code`: one-shot write-capable delegation with explicit write-set and apply policy.
- `/agy:delegate`: generic command with mode/role options.
- `/agy:review`: one-shot reviewer with lens.

Tension to resolve:

- Fewer commands reduce misuse.
- Separate quick commands can be ergonomic, but may recreate the current plugin's ambiguity.
- The quick path should probably route through the same wrapper/evidence machinery as teammates.

User answer:

Agree with one generic quick command, with explicit role and mode, routed through the
same wrapper/evidence machinery as teammate agents.

Candidate command shape:

```text
/agy:delegate --role coder|reviewer --mode no-write|patch-only|auto-if-clean ...
```

Do not create separate `/agy:ask`, `/agy:code`, and `/agy:review` commands in v1 unless
the generic command proves too clunky. The quick path must not become a weaker/raw path
around the teammate harness.

### Round 14: What Are The First Feasibility Spikes?

Prompt:

What should be proven before writing the full plugin?

Candidate spikes:

- Can a plugin-packaged agent be constrained into a thin `agy` bridge that does not solve
  the task directly?
- Can the wrapper run a long `agy` job without background detach/hang?
- Can each run prove a real `agy` process was invoked and distinguish Claude fallback?
- Can write-capable runs use a worktree or disposable clone boundary and return/import a
  patch reliably?
- Can `auto-if-clean` enforce explicit write-set, checks, and failure-to-patch behavior?
- Can the quick command and teammate agents share the exact same request/result schema?

User answer:

Must-prove spikes: 1, 2, 4, and 6.

Selected spikes:

1. Prove a plugin-packaged agent can be constrained into a thin `agy` bridge that does
   not solve the task directly.
2. Prove the wrapper can run a long `agy` job without background detach/hang.
3. Prove write-capable runs can use a worktree or disposable clone boundary and
   return/import a patch reliably.
4. Prove the quick command and teammate agents share the exact same request/result schema.

Explicit concern: some of this likely cannot be fully proven without running Claude Code.
In particular, the "plugin-packaged agent behaves as a thin bridge" spike is a live Claude
Code harness question, not something static tests alone can answer.

Design implication: split spike evidence into layers:

- Static/repo proof: plugin manifests, agent prompts, command docs, wrapper request/result
  schema, and unit tests.
- Wrapper proof: invoke the wrapper directly from shell with fake/minimal tasks to prove
  long-running behavior, boundaries, patch import, evidence bundle, and failure statuses.
- Claude Code harness proof: run at least one live Claude Code delegated teammate task and
  confirm the packaged agent calls the wrapper/`agy`, returns evidence, and does not solve
  the task itself.

### Round 15: What Is An Acceptable Claude Harness Proof?

Prompt:

For the Claude-dependent spike, what is the minimum live proof that would make you trust
the agent surface enough to continue?

Candidate proof:

- A tiny `agy-reviewer` run where Claude Code selects the packaged agent, the agent calls
  the wrapper, and the result includes evidence path/status.
- A tiny `agy-coder` write run in a scratch repo or throwaway fixture, proving write-set,
  patch import, and no direct Claude Write/Edit.
- Transcript audit showing the agent used only the wrapper/Bash path and did not solve
  the task with Claude Code tools.

User answer:

Agree with the two-run Claude harness proof.

Minimum live proof:

1. A tiny `agy-reviewer` run where Claude Code selects the packaged agent, the agent
   calls the wrapper/`agy`, and the result includes status plus evidence path.
2. A tiny `agy-coder` write run in a scratch repo or throwaway fixture, proving explicit
   write-set handling, patch import or auto-apply behavior, and no direct Claude Write/Edit.
3. Transcript audit for both runs proving the packaged agent used only the intended
   wrapper/Bash path and did not solve the task with Claude Code tools.

Design implication: the implementation plan must include a live Claude Code harness gate.
Unit tests and direct wrapper tests are necessary but not sufficient to call the teammate
surface proven.

### Round 16: New Plugin, Fork, Or Copy?

Prompt:

Should this be built as a new Infiquetra plugin, a fork/patch of the current
`antigravity-cc/agy` plugin, or a copy/own-the-surface plugin that borrows prior art?

Tension to resolve:

- New plugin can expose the teammate/runtime abstraction cleanly without inheriting the
  current plugin's ambiguous command shape.
- Forking the current plugin may preserve compatibility and reduce initial code, but it
  also carries the current surface area and upstream drift.
- Copying prior art gives full control, but creates maintenance ownership for every
  Antigravity integration detail.

User answer:

Build this as a new Infiquetra plugin, not a fork/patch of `antigravity-cc/agy`.

Design implication: borrow prior art from the existing Antigravity plugin and Hermes, but
do not inherit the current plugin's thin-forwarder command shape as the product surface.
The new plugin should center the Antigravity-backed teammate abstraction, shared wrapper,
evidence/provenance bundle, write-capable apply policy, and quick command as a secondary
front door.

### Round 17: What Should Be Handed To `saga:ideate`?

Prompt:

Should the handoff to `saga:ideate` ask for ranked product/design ideas, or should it ask
for a narrower implementation-shape ideation around this already-chosen product direction?

Tension to resolve:

- Broad ideation could still find better variants or challenge assumptions.
- Narrow ideation may be more useful now because the desired product surface is becoming
  clear: new plugin, `agy-coder`, `agy-reviewer`, wrapper/evidence harness, write-capable v1.

User answer:

Agree with narrow implementation-shape ideation. The major product direction is now
settled enough that `saga:ideate` should focus on variants for making the new plugin
work reliably and avoid repeating the current failure modes, rather than reopening the
entire product question.

### Seed Hypotheses To Challenge Later

Current locked constraints from the Socratic session:

- Build a new Infiquetra plugin, not a fork of `antigravity-cc/agy`.
- v1 must include write-capable delegation from the start; read-only-only is not enough.
- The primary surface is preconfigured Antigravity-backed teammates: `agy-coder` and
  `agy-reviewer`.
- The quick command is secondary and must route through the same wrapper/evidence schema.
- Write-capable delegation should produce a local evidence bundle: command invoked,
  transcript path, changed paths, git-state proof, verification commands, and explicit
  "real agy vs fallback" verdict.

- A custom Infiquetra plugin should probably not be "the same thin wrapper, but ours."
- The primary product may be a provenance-enforcing delegation harness, not an Antigravity
convenience command.
- The first shippable slice may be read-only review/exploration with hard evidence capture,
  not write-capable implementation.
- If write-capable delegation is kept, the plugin should make the run produce a local evidence
  bundle: command invoked, transcript path, changed paths, git-state proof, verification commands,
  and an explicit "real agy vs fallback" verdict.
- The command UX should make the safe path shorter than the unsafe path.

## References To Reconcile During Ideation

- `docs/ideation/2026-05-30-delegate-agent-plugin-ideation.md`
- `docs/external-agent-delegation/README.md`
- `docs/external-agent-delegation/blueprint.md`
- `docs/external-agent-delegation/agy-plugin-fork-decision.md`
- `docs/external-agent-delegation/next-run-handoff.md`
- `docs/engineering-journal/LEARNINGS.md`
- `docs/engineering-journal/DECISIONS.md`
