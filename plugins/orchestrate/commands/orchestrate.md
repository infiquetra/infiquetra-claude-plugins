---
name: orchestrate
description: Plan work across herdr agent sessions and run it — one worktree per unit, any configured agent, any saga capability
argument-hint: "<prompt> | #<issue> | #<parent> --children | <path/to/doc.md>"
---

Spread one piece of work across several agent sessions, decide together how to split it, then run
it. Each unit gets its own git worktree and branch, so sessions cannot overwrite each other.

## The layers

```
/orchestrate <input>
  └── lifecycle       one per issue — one input can carry several
        └── phase     /plan, /doc-review, /work, /code-review — the umbrella steps
              └── unit    one session, one worktree, one branch
```

A single issue is one lifecycle. A parent issue with children is one lifecycle per child, each with
its own phases. A phase is not always one unit: three vendors writing competing plans is one phase
and three units, and `/work` is one phase and however many units the plan calls for.

**Choices are made at the layer that owns them and inherited downward.** The operator picks which
vendors may be used at all, and how many reviewers each review phase gets. `/work` takes its vendors
from the plan and `/code-review` takes its lenses from the plan, not from the interview.

**A review phase is a panel.** "Two reviewers on the plan" is two units, two tabs, two worktrees,
two vendors — never one vendor holding a review seat.

## Phase 1 — read the input

| Argument | What to read |
|---|---|
| free prose | the prose itself |
| `#123` | that issue: title, body, labels, linked issues |
| `#100 --children` | the parent, then every sub-issue — one lifecycle each |
| a path ending `.md` | the document — a plan, a requirements doc, a brainstorm |

Read it before asking anything. Come to the interview already knowing what the work is, and say so
in a few lines: what the work actually is, where the real seams are, and where you think it does
*not* split well. That framing is worth more than any question you could ask instead.

## Phase 2 — interview the operator

**Recommend.** Every question carries your recommendation and one line of why. The operator is
choosing between options you have already thought about, not doing the thinking.

**Ask one question per turn** with `AskUserQuestion`. For an abstract fork, put a small worked
picture in the `preview` field — a table, a before-and-after, an arrow chain. Labels alone lose.

**A note attached to an answer is an instruction, not a comment.** The operator can press `n` and
write "use grok for the second plan instead of codex", or "qwen not opencode", or "drop the third
reviewer". Apply it, say in one line what you changed, and carry it into the table. A note that
contradicts the option they picked wins — they wrote it after seeing the options.

**If a question is declined, do not stall and do not re-ask.** Take the most defensible answer, say
in one line which you took and why, and continue. The table is the real gate and every row is
editable there.

**Say only what you can show from this repository and this issue.** Do not bring in remembered
opinions about a vendor — that one went idle once, that one is unreliable — from other work or
recalled context. The operator did not ask for a reputation report, it is not checkable from here,
and it quietly steers a choice that is theirs. Vendor commentary is limited to what `roster`
reports: whether the agent takes model and effort flags.

**Do not presume the shape of the plan.** These are the questions that usually matter, in this
order — not a checklist, and stop as soon as the answers determine the table:

1. **Is the WHAT settled?** A thin issue or a bare prompt may want `/brainstorm` or `/spec` first. A
   reviewed plan document does not.
2. **Which phases?** `/plan`, `/doc-review`, `/work`, `/code-review`, `/qa`, `/investigate` — or a
   plain prompt with no saga command at all. This is the question that shapes everything after it.
3. **Which vendors may be used at all?** Get the list from `python3 "$S" roster` — never from
   `agents --crews`, which is the operator's own saved workspace layout and has nothing to do with
   orchestration. `roster` reports the vendors orchestrate knows how to drive **that are available
   on this machine**; it is an intersection, and both halves matter. One allow-list for the whole
   orchestration, **not one vendor per unit**.

   **Every vendor can be given a model and an effort.** Where the command line has no flag for it,
   the unit's `setup` carries a slash command instead. Never present a vendor as untierable.

   **Never write a model name from memory.** Run `python3 "$S" roster --models`, which asks each
   vendor that can answer. `grok` and `opencode` can; `claude` documents its aliases in
   `claude --help` (`fable`, `opus`, `sonnet`, and full names); the rest cannot answer, and for
   those you ask the operator rather than guessing. A recalled model name that has since been
   renamed does not fail politely — the session starts on some default and nobody is told.
   `opencode` needs `provider/model`, not a bare name.
4. **Does `/plan` want competing plans?** One vendor plans by default. The operator may instead have
   two or three vendors each write a plan independently, in their own worktrees, with no knowledge
   of each other. If so, **this session reads all of them and writes the merged plan itself** — no
   merge unit, no extra tab. Say which parts came from where.
5. **How many reviewers does each review phase get?** **A review is a panel, not a seat.** Ask for a
   count per review phase, not a vendor — "two reviewers on the plan" — and turn each into its own
   unit with its own tab, worktree and vendor. Three reviewers is three rows. Assign them yourself
   from the allow-list, never the vendor that produced the thing being reviewed.

   The count is a **default for when nobody is watching**, not a lock. The operator re-confirms the
   actual reviewer rows at the expansion gate (Phase 5), in this session, where they are present.
6. **Anything out of scope?**

Do **not** ask about `/work` vendors or `/code-review` lenses. Those come from the plan.
Do **not** ask about inline versus a workflow backend — orchestrate is always inline.

### Answering saga's offer up front

`/doc-review` and `/code-review` open by resolving saga's external-engine offer. With nothing
stored they **stop and ask the operator** — in a background tab nobody is watching, which means the
unit waits forever. So the plan carries `engine_prefs`, which lands in every worktree before its
session starts:

```json
"engine_prefs": {
  "doc-review":  {"intent": "none"},
  "code-review": {"intent": "none"}
}
```

**Use `none` for review stages.** The panel is orchestrate's job: the operator asked for N
reviewers and gets N units. Letting each of those *also* take a saga second opinion doubles the
sessions without being asked for. The value of the stored answer here is that it stops the tab
hanging, not that it adds an opinion.

Stages: `ideate`, `brainstorm`, `work`, `doc-review`, `code-review` — there is no `plan` stage.
Intents: `none`, `offload`, `second-opinion`, `external-only`. Models are tier names —
`fable`, `opus`, `sonnet`, `haiku`. Efforts: `low`, `medium`, `high`, `xhigh`.

`/code-review` still runs its own lens consensus inside each unit — its lenses, quorum and
gated-versus-advisory verdicts are its business, not something to rebuild here. The plan chooses
which lenses; the interview does not ask.

## Phase 3 — hand over the table

Show phases and policy. **Later phases have no units yet** — what `/work` splits into is decided by
the plan, which does not exist when the operator is reading this. Say so rather than guessing:

```
run <run_id>   <-  <what the input was>
vendors allowed: claude, codex, grok, qwen        reviewers: 2 on the plan, 2 on the code

 phase  what it does                    saga cap       agent     model         effort  after
 -----  -----------------------------   ------------   -------   -----------   ------  -----
 p1a    plan #48                        /plan          claude    opus          high    -
 p1b    plan #48, independently         /plan          codex     gpt-5.6-sol   xhigh   -
 (merge of p1a and p1b happens in this session — no unit)
 p2a    tear up the merged plan         /doc-review    grok      grok-4.6      xhigh   p1a p1b
 p2b    tear up the merged plan         /doc-review    qwen      qwen3-max     high*   p1a p1b
 p3     build it                        /work          <from the plan>                 p2a p2b
 p4a    review the build                /code-review   <from the plan>                 p3
 p4b    review the build                /code-review   <from the plan>                 p3
```

Rules for the table:

- **Match the agent to the work, not to habit.** Judgement, design and adversarial review want a
  stronger model; mechanical and survey work does not. One line of why if it is not obvious.
- **A reviewing unit is never the agent that produced what it reviews.** Do not hand a session its
  own output to bless.
- **`after` is the only ordering.** Units with no dependency run at the same time.
- **Every vendor in the table must be in the allow-list** from question 3.
- **Every row carries a model and an effort.** A `*` marks an effort delivered by a slash command
  in `setup` rather than a launch flag — same result, different door. Never leave a tier blank.

Then ask to approve, edit, or cancel. **Nothing launches before the operator says yes.**

**Editing is plain language, not a form.** "Make p1b grok", "swap the two reviewers", "drop p2b",
"opus on the builder", "add a third plan from qwen" — take it, redraw the whole table, and show it
again. Any cell is fair game, including which vendor sits in a competing-plan row. Redraw rather
than describing the change, so what they approve is what runs.

## Phase 4 — run it

Write only the units that can actually launch now — the `<from the plan>` rows are not units yet and
do not belong in the JSON. `task` is the literal text sent to the session.

```json
{
  "run_id": "orch-2026-08-16-a",
  "source": "#48 deploy-guard remediation",
  "engine_prefs": {"code-review": {"intent": "second-opinion", "model": "opus", "effort": "high"}},
  "units": [
    {"name": "p1a", "vendor": "claude", "model": "opus", "effort": "high",
     "task": "/plan #48", "after": []},
    {"name": "p2a", "vendor": "grok", "model": "grok-4.6", "effort": "xhigh",
     "task": "/doc-review docs/plans/....md", "after": ["p1a"]},
    {"name": "p2b", "vendor": "qwen", "model": "qwen3-max", "setup": ["/effort high"],
     "task": "/doc-review docs/plans/....md", "after": ["p1a"]}
  ]
}
```

Find the script first — the operator is rarely in this plugin's own repo, and `roster` in Phase 2
needs it too:

```bash
S="$CLAUDE_PLUGIN_ROOT/skills/orchestrate/scripts/orchestrate.py"
[ -f "$S" ] || S=$(ls -d ~/.claude/plugins/cache/*/orchestrate/*/skills/orchestrate/scripts/orchestrate.py | sort -V | tail -1)
```

Then, from the operator's repo:

```bash
python3 "$S" roster                                # what this machine can launch
python3 "$S" start --plan .orchestrate/plan.json   # worktree + branch per unit
python3 "$S" go                                    # launch everything eligible
python3 "$S" status                                # the table, live
python3 "$S" settle                                # idle sessions become done
python3 "$S" go                                    # dependents are now eligible
python3 "$S" collect                               # merge each unit's branch
python3 "$S" clean --branches                      # close tabs, remove worktrees
```

`python3`, not `uv run` — the script imports nothing outside the standard library, and the target
repo may not be a uv project at all.

Between `go` and `settle`, watch with a Monitor rather than polling in a loop.

## Phase 5 — expand at each phase boundary

When a phase finishes and it is the one that decides the next phase's units, read what it produced
and bring the operator a table for **those rows only**:

1. `settle`, then read the finished phase's output from its worktree — for `/plan`, the plan
   document it wrote.
2. Derive the next phase's units from it: what `/work` splits into, which vendor and tier each piece
   wants, what depends on what. The plan is human prose; read it and propose. If it is vague, say
   so and propose the best reading — the operator is about to edit it anyway.
3. Show that table alone. Approve or edit.
4. Append and launch:

```bash
python3 "$S" expand --plan .orchestrate/expand-p3.json
python3 "$S" go
```

`expand` refuses a name already in the run and a dependency that is in no run, so a bad table fails
before anything launches.

**Competing plans are read, not merged by git.** When `/plan` ran in several vendors' worktrees, open
each one's plan document directly and write the merged plan yourself. Do not `collect` those
branches into each other.

## Phase 6 — report

What each unit produced, and what merged. If a session went idle without doing the work, say so
plainly — an idle session is not a finished one, and `status` shows both the recorded state and what
herdr says right now. A unit sitting at `blocked` is waiting on a question in its own tab.

## Things this command deliberately does not do

It does not verify that a session "really" finished, count anyone's tokens, enforce a budget,
reserve concurrency slots, run its own voting panel, or keep a durable register. If a unit went
wrong you have its worktree, its branch, and its tab — look at them.
