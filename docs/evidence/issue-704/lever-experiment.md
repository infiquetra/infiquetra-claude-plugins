# Issue 704 — U1 lever reach experiment

**Date:** 2026-08-08
**Repository:** `infiquetra/infiquetra-claude-plugins`, commit `f31066a4` (branch
`docs/output-styles-requirements-review`, clean tree)
**Plan:** `docs/plans/2026-08-08-issue-704-house-style-output-style-plugin-plan.md`, section `### U1.`
**Run context:** executed from inside a saga-emitted workflow, as the U1 unit agent.

## Why this experiment exists

The house-style plugin (issue 704) proposes reaching subagents two ways: by putting a presentation
preamble into the 36 plugin agent definition files (called **Lever A**), and by stamping the same
preamble into saga's workflow emitter so every emitted `agent()` prompt carries it (called **Lever B**).
Both are assumptions until observed. This unit tries to observe each one directly, before any other
unit builds on them.

**Overall result: `pass`, in two stages.** Lever B passed here, decisively and twice over. Lever A could
not be tested at all from the workflow backend, for a reason about the test harness and not about the
lever, and was recorded as `inconclusive` — neither a pass nor a disproof. On operator authorisation it
was then tested from an interactive session and **passed**; that method, its result, and a separate
finding about when an edited definition takes effect are recorded at the end of this document.

---

## Question resolved first: can an agent running inside a workflow spawn another agent?

The plan flags this as unverified anywhere in the repository. It is now answered for this runtime.

**Answer: no.** This workflow agent has no agent-spawning tool.

Evidence, three independent probes:

1. Direct lookup by name — `ToolSearch` with query `select:Task,Agent`:

   ```
   No matching deferred tools found
   ```

2. Keyword search — `ToolSearch` with query `spawn subagent delegate agent task`. Returned `TaskStop`
   (stops an already-running task), `SendMessage` (messages an already-existing agent), and unrelated
   Todoist task tools. No tool that creates an agent.

3. Second keyword search — `ToolSearch` with query `launch new agent subagent_type isolation worktree`.
   Returned `EnterWorktree`, `ExitWorktree`, `SendMessage`, `RemoteTrigger`, and a browser tool. Again
   no tool that creates an agent.

Corroborating: `ListAgents` reports six peer sessions (interactive shells and Remote Control sessions)
and zero in-process subagents. `SendMessage` can address those existing peers, but messaging a session
that is already running is not spawning an agent from a plugin agent definition, so it does not test
the property Lever A depends on.

The complete tool inventory available to this agent is `Artifact`, `Bash`, `Edit`, `ListAgents`, `Read`,
`ReportFindings`, `SendUserFile`, `Skill`, `ToolSearch`, `Write`, `StructuredOutput`, plus deferred
tools and MCP servers. No `Task` tool, no `Agent` tool.

---

## Lever A — does an agent definition file's body govern the agent it defines?

**Result: INCONCLUSIVE (harness limitation, not a lever finding).**

**Method attempted:** the plan's preferred method is to spawn an installed agent whose definition makes
a falsifiable behavioural commitment — `saga:mechanical-executor`, whose definition says it rejects
unknown operations with a clear error rather than guessing — dispatch an unknown operation, and see
whether the rejection matches the definition. The documented fallback is to write a marker into the
installed cache copy under `~/.claude/plugins/cache/infiquetra-plugins/<plugin>/<version>/agents/`,
spawn, observe, and restore the file byte-for-byte.

**Why neither ran:** both methods require spawning an agent, and this runtime exposes no way to spawn
one, as established above. The primary method needs a spawn to dispatch the unknown operation; the
fallback needs a spawn to observe the marker. There is no third method in the plan, and inventing one
would be exactly the adaptation the unit's hard stop forbids.

This is a statement about the test, not about the lever. The plan anticipates it verbatim: *"If it
cannot, Lever A's spawn-based methods are unavailable from this backend and the unit reports
inconclusive rather than failure."*

**Nothing was modified.** No file under `~/.claude/plugins/cache/` was written, so there is nothing to
restore. The working tree was never used for a throwaway agent definition, because the plan correctly
rules that method out — agent definitions load from the versioned plugin cache, so a working-tree file
is invisible to the runtime and would have produced a guaranteed false negative.

**What would settle it.** Running the same experiment from an interactive Claude Code session, which
does carry an agent-spawning tool, would test Lever A directly. That is an operator decision, not one
this unit takes on its own — and note it answers the lever question, not the separate question of
whether workflow-backend agents can spawn (which is now answered: they cannot).

---

## Lever B — does a rider added at the emitter funnel reach emitted `agent()` prompts?

**Result: PASS.** Proven at emission, and then independently proven at delivery.

### Part 1 — emission

The rider was added inside `_agent_prompt()` in `plugins/saga/scripts/execution_spec.py`, immediately
after `parts: list[str] = [unit.prompt]` at line 3250, so it applies unconditionally to every unit
rather than only cheap-tier ones:

```python
parts.append("LEVER-B-MARKER-704 throwaway rider, reverted before U1 ends.")
```

A control emission was taken **before** the edit, so the marker's absence is measured rather than
assumed. The sample spec is `docs/plans/2026-08-02-issue-686-verify-panel-severity-axis-spec.json`
(3 units).

Exact invocations:

```bash
# control, before the edit
uv run python plugins/saga/scripts/execution_spec.py emit \
  docs/plans/2026-08-02-issue-686-verify-panel-severity-axis-spec.json -o before.js
grep -c "LEVER-B-MARKER-704" before.js     # -> 0

# after the edit
uv run python plugins/saga/scripts/execution_spec.py emit \
  docs/plans/2026-08-02-issue-686-verify-panel-severity-axis-spec.json -o after.js
grep -c "LEVER-B-MARKER-704" after.js      # -> 3
grep -c "agent(" after.js                  # -> 3
```

Three markers across three `agent()` calls: the rider reaches every emitted prompt, exactly once each.
No double-application in this sample.

Byte accounting corroborates the count independently. `before.js` is 23,361 bytes and `after.js` is
23,553 — a difference of exactly 192 bytes, which is 3 × 64, where 64 is the rider's 60 characters plus
the two separating newlines escaped as `\n\n` (4 characters) inside the JSON-encoded prompt string.
Nothing else in the emitted script changed.

Raw output excerpt, the first of the three hits (`after.js` line 365, truncated at both ends):

```
"U1: Split the refute-N verifier verdict into a gating bucket ... do not paraphrase any of
them.\n\nLEVER-B-MARKER-704 throwaway rider, reverted before U1 ends.\n\nRETURN CONTRACT (all
tiers): your FINAL message MUST be ONLY a single JSON object with the keys status, files_changed,
checks_run, notes -- no prose, no markdown code fences, ..."
```

The marker sits between the unit's own prompt text and the return contract, which is where an appended
`parts` entry should land.

### Part 2 — delivery, observed live

Part 1 proves the rider reaches the emitted *script*. The claim the plugin actually depends on is that
the text reaches the *running subagent*. That was confirmed in-band, using this very run as the
specimen — no marker required, because saga already stamps text at the same funnel.

The `RETURN CONTRACT (all tiers)` clause is composed inside `_agent_prompt()` at
`plugins/saga/scripts/execution_spec.py:3263`. It appears 9 times in this run's emitted workflow,
`docs/plans/2026-08-08-issue-704-house-style-output-style-plugin.workflow.js`, once per unit. The U1
copy carries this unit's own return keys:

```
with the keys status, lever_a_result, lever_a_method, lever_b_result, evidence_path, notes
```

That exact string, and the surrounding clause, arrived verbatim in this agent's own prompt. The chain
is closed and every link was observed rather than inferred:

```
execution_spec.py:3263  (text added inside _agent_prompt)
        |
        v
...704-house-style-output-style-plugin.workflow.js   (present, 9 occurrences)
        |
        v
this agent's received prompt                          (present, verbatim, U1-specific keys)
```

This is the strongest form of the Lever B claim, and it holds.

### Scope limit, stated rather than papered over

The sample spec has 3 units and **no verifier panels**, so this experiment covered unit prompts only.
Whether verifier prompts also carry an emitter rider was not tested here. That question is already
assigned to U5's second lens (`verifier_prompts_byte_identical`) and should be answered there, not
assumed from this result.

### Revert, verified three ways

The throwaway edit is gone. Confirmed by:

1. `git status --porcelain` — empty output, clean tree.
2. `git diff --exit-code plugins/saga/scripts/execution_spec.py` — exit code 0, byte-for-byte restored.
3. Re-emitting the same spec after the revert produced a file identical to the pre-edit control
   (`diff -q before.js restored.js` reports no difference) and `grep -c "LEVER-B-MARKER-704"` returns 0.

---

## Summary

| Lever | Result | Basis |
| --- | --- | --- |
| A — agent definition body governs the spawned agent | **PASS** | A spawned `saga:mechanical-executor` reproduced, byte-for-byte, a three-line rejection block that exists only in its definition's body and nowhere in its frontmatter or in the dispatch it was sent. Tested from an interactive session on operator authorisation, after the workflow backend proved unable to spawn. |
| B — emitter rider reaches emitted `agent()` prompts | PASS | 0 → 3 markers across 3 `agent()` calls, exact byte accounting, plus live in-band confirmation that emitted prompt text arrives verbatim in the running subagent. |

Both levers work. Requirements-document R27 was never reopened and does not reopen now.

---

## Lever A — method and result (added 2026-08-08, interactive session)

**Why this ran separately.** The U1 unit could not test Lever A: a workflow-backend agent has no
agent-spawning tool, so both prescribed methods were unavailable. The operator authorised the test from
an interactive session, which does carry the tool.

**Design, against the three ways this test produces a false pass.**

*Marker leakage.* Rather than write a marker, the test used one already present: the
`saga:mechanical-executor` definition's body specifies an exact rejection string for an unapproved
operation, ending `No work was performed.` That string was verified absent from the file's frontmatter
(`sed -n '1,41p' … | grep -c` returns 0) and it appeared nowhere in the dispatch. The dispatch was three
lines: `op: verify-checksum`, a target path, and an algorithm. Nothing else.

*An unloaded definition reading as a failure.* The agent type resolved and ran — it did not fail to
spawn and did not fall back to a default. Its answer was on-contract behaviour, so the loaded-definition
precondition is satisfied by the result itself rather than assumed.

**Result.** The returned text was:

```
ERROR: unknown op "verify-checksum".
Approved ops: census, file-exist, json-validate, grep-count, link-check.
No work was performed.
```

Byte-identical to the body's fenced block. The body of an agent definition governs the agent it
defines. **Lever A passes.**

## The restart finding — a definition edited on disk does NOT reach a running session

The operator asked for this either way, and the answer is the more consequential of the two.

**Method.** The installed cache copy at
`~/.claude/plugins/cache/infiquetra-plugins/saga/0.131.0/agents/mechanical-executor.md` was edited in
its body only, twice, with progressively stronger markers:

1. A formatting instruction — begin every response with a literal token. The next spawn omitted the
   token, but also *paraphrased* the rejection rather than reproducing it, so a dropped instruction was
   as good an explanation as a stale definition. Recorded as confounded, not as a result.
2. Markers placed inside content the agent had by then reproduced twice: a sixth, invented operation
   (`quantum-audit`) added to the body's approved-ops list, and the token appended to the sentence
   `No work was performed.` itself.

**Result.** The next spawn returned the **old** block verbatim — five operations, no invented sixth, no
token — while the file on disk carried all three changes. That is not an agent ignoring an instruction;
it is an agent reproducing a stale copy exactly.

**Conclusion.** Agent definitions are read once and cached in the running process. **A session must be
restarted before an edited definition takes effect.** For this work that means shipping the preamble in
36 agent definitions governs no subagent until the change merges, versions bump,
`/plugin marketplace update infiquetra-plugins` runs, *and the operator starts a new session*. The
restart is a fourth step, not implied by the first three.

**Cleanup.** The cache file was restored from a byte-for-byte backup and its SHA-256 re-verified as
`385c42290ac8567554faf693e127f45d94dcdd3c3fddc39710ffc4d6c3adb674`, identical to the pre-edit value. A
recursive search of the plugin cache, `~/.claude/agents/`, and the repository finds no surviving marker.
