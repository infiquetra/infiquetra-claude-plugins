---
name: orchestrate
description: Plan work across herdr agent sessions and run it — one worktree per unit, any configured agent, any saga capability
argument-hint: "<prompt> | #<issue> | #<parent> --children | <path/to/doc.md>"
---

Spread one piece of work across several agent sessions, decide together how to split it, then run
it. Each unit gets its own git worktree and branch, so sessions cannot overwrite each other, and
each unit can invoke any saga capability — or none.

## Phase 1 — read the input

The argument is one of:

| Argument | What to read |
|---|---|
| free prose | the prose itself |
| `#123` | that issue: title, body, labels, linked issues |
| `#100 --children` | the parent, then every sub-issue |
| a path ending `.md` | the document — a plan, a requirements doc, a brainstorm |

Read it before asking anything. Come to the interview already knowing what the work is.

## Phase 2 — interview the operator

**Do not presume the shape of the plan.** Do not assume a `/plan → /work → /code-review` pipeline,
or any other. Ask what you cannot infer from what you just read, one question per turn, using
`AskUserQuestion` so the operator answers by picking.

Ask only what changes the plan. Typical questions, not a checklist:

- **Is the WHAT settled?** If the input is a prompt or a thin issue, the first unit may need
  `/brainstorm` or `/spec` before anything else. If it is a reviewed plan document, it does not.
- **Where are the real seams?** Name the split you are considering and ask whether it is right —
  "these two both touch the register schema, one unit or two?" Do not guess at dependencies you can
  ask about.
- **Which agents are in play?** Run `agent --crews` to see what this machine actually has
  configured, and offer those. Never hardcode a roster.
- **Does anything want an independent look?** A second opinion is a unit like any other, not an
  automatic step.
- **Anything to keep out of scope?**

Stop asking once the answers determine the table. Three or four questions is normal.

## Phase 3 — hand over the table

Print exactly this shape and let the operator edit any row:

```
run <run_id>   <-  <what the input was>

 unit  what it does                    saga cap       agent     model         effort  after
 ----  -----------------------------   ------------   -------   -----------   ------  -----
 u1    settle the WHAT on #102         /brainstorm    claude    opus          high    -
 u2    design across #101 #103         /plan          codex     gpt-5.6-sol   xhigh   -
 u3    tear up u2's plan               /doc-review    grok      grok-4.6      xhigh   u2
 u4    build #101                      /work          codex     gpt-5.6-sol   high    u3
 u5    review u4                       /code-review   claude    opus          high    u4
```

Rules for the table:

- **`saga cap` is whatever fits** — `/ideate`, `/brainstorm`, `/spec`, `/plan`, `/doc-review`,
  `/work`, `/code-review`, `/qa`, `/investigate`, `/retro` — or a plain prompt with no command.
  Choose per unit from what the work needs.
- **Match the agent to the work, not to habit.** Judgement, design and adversarial review want a
  stronger model; mechanical and survey work does not. Say why in one line if the choice is not
  obvious.
- **A reviewing unit should not be the agent that produced what it reviews.** Not a rule to enforce
  mechanically — just do not hand a session its own output to bless.
- **`after` is the only ordering.** Units with no dependency run at the same time.

Then ask to approve, edit, or cancel. **Nothing launches before the operator says yes.**

## Phase 4 — run it

Write the approved table to `.orchestrate/plan.json`:

```json
{
  "run_id": "orch-2026-08-16-a",
  "source": "#100 register consolidation",
  "units": [
    {"name": "u1", "vendor": "claude", "model": "opus", "effort": "high",
     "task": "/brainstorm #102", "after": []},
    {"name": "u3", "vendor": "grok", "model": "grok-4.6", "effort": "xhigh",
     "task": "/doc-review docs/plans/....md", "after": ["u2"]}
  ]
}
```

`task` is the literal text sent to the session. Then:

```bash
S=plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py
uv run python $S start --plan .orchestrate/plan.json   # worktree + branch per unit
uv run python $S go                                    # launch everything eligible
uv run python $S status                                # the table, live
uv run python $S settle                                # idle sessions become done
uv run python $S go                                    # dependents are now eligible
uv run python $S collect                               # merge each unit's branch
uv run python $S clean --branches                      # close tabs, remove worktrees
```

Between `go` and `settle`, watch with a Monitor rather than polling in a loop. When `settle` marks
units done, run `go` again — that is what releases the next wave.

## Phase 5 — report

Tell the operator what each unit produced and what merged. If a session went idle without doing the
work, say so plainly — an idle session is not a finished one, and `status` shows you both the unit's
recorded state and what herdr says right now.

## Things this command deliberately does not do

It does not verify that a session "really" finished, count anyone's tokens, enforce a budget,
reserve concurrency slots, run a voting panel, or keep a durable register. If a unit went wrong you
have its worktree, its branch, and its tab — look at them.
