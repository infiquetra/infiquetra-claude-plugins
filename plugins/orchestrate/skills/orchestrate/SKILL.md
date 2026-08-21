---
name: orchestrate
description: Spread one piece of work across several herdr agent sessions — plan it with the operator, run each unit in its own git worktree with any configured agent and any saga capability, then merge the results back. Triggers on "/orchestrate", "orchestrate this", "split this across agents", "run these issues in parallel", "fan this out to multiple sessions", "orchestrate across vendors".
---

# orchestrate

Take one piece of work — a prompt, an issue, a parent issue's children, or a document — decide with
the operator how to split it, and run the pieces across herdr agent sessions.

Each unit gets its own git worktree and branch, so sessions cannot overwrite each other. Each unit
can invoke any saga capability (`/plan`, `/brainstorm`, `/doc-review`, `/work`, `/code-review`,
`/qa`, `/investigate`, …) or just take a plain prompt. Any agent configured on this machine can run
any unit. Code Review is one top-level controller unit, not one Orchestrate unit per lens or reviewer.

## How to use it

Run `/orchestrate <input>`. The command file
(`plugins/orchestrate/commands/orchestrate.md`) carries the full procedure: read the input,
interview the operator, hand over a table for approval, then dispatch.

**Nothing launches until the operator approves the table.**

## The mechanical half

`skills/orchestrate/scripts/orchestrate.py` does the moving parts:

Resolve it first — the operator is rarely in this plugin's own repo:

```bash
S="$CLAUDE_PLUGIN_ROOT/skills/orchestrate/scripts/orchestrate.py"
[ -f "$S" ] || S=$(ls -d ~/.claude/plugins/cache/*/orchestrate/*/skills/orchestrate/scripts/orchestrate.py | sort -V | tail -1)

python3 "$S" roster                                # agents this machine can launch
python3 "$S" start --plan .orchestrate/plan.json   # record the run
python3 "$S" go                                    # launch every eligible unit
python3 "$S" status                                # the table, with live herdr state
python3 "$S" settle                                # idle sessions become done
python3 "$S" expand --plan .orchestrate/next.json  # append units a finished phase named
python3 "$S" review-result --file <result.json>     # persist the typed result and route repairs
python3 "$S" collect                               # merge each finished unit's branch
python3 "$S" clean --branches                      # close tabs, remove worktrees
```

Standard library only, so `python3` — not `uv run`, which would need the target repo to be a uv
project.

`go` launches only units whose ordering edges are all satisfied — every name in `after` and
`serialize` done — so calling `settle` then `go` again is what releases the next wave.

**A unit with dependencies branches from the last one it names**, at launch time rather than up
front — so a `/work` unit opens on top of its `/plan` unit's actual output.

**Two ordering edges, one gate.** `after` and `serialize` both hold a unit until every name they
list is done; what differs is what they claim. `after` — I build on what you produce: a reviewer
after the thing it reviews, a builder after the plan it implements. `serialize` — I must not run
beside you, but I need nothing from you: two units that would edit the same file, or one that must
wait for the other to land before it can rebase. Reaching for `after` in that second case asserts
a dependency that does not exist, and a reader can no longer tell a real one from a scheduling
one. The command file's Phase 4 carries a worked `serialize` pair.

**The later phases have no units until an earlier one names them.** What `/work` splits into is
decided by the plan, which does not exist when the operator approves the first table. So the run
starts with only what can launch now, and `expand` appends the rest once the operator has approved
them — same run, so `after` still reaches back and one `collect` covers everything. `expand` refuses
a duplicate name or a dependency that is in no run.

**Saga's external-engine offer is answered before dispatch.** A `/doc-review` or `/code-review`
session with no stored preference stops and asks the operator, in a tab nobody is watching. The
plan's `engine_prefs` block is written to `<worktree>/.saga/engine-prefs.json` at worktree creation,
which saga reads and skips the question. Keyed by stage (`ideate`, `brainstorm`, `work`,
`doc-review`, `code-review`) with an `intent` of `none`, `offload`, `second-opinion` or
`external-only`, plus a tier `model` and `effort`.

**Code Review has one controller and owns acceptance.** Its plan row declares
`role: "review-controller"`; `start` and `expand` refuse a second. Work rows that may receive repairs
declare `role: "review-fixer"` or `role: "downstream-resolver"` and repository-relative `paths`.
When the controller emits its typed result, run `review-result --file <path>`. Orchestrate first
stores the complete UTF-8 string verbatim, then reads only its routing envelope: outcome and the fix
request identity, owner role, and touched paths. It never imports the scorer or makes a second
acceptance decision.

An overlapping live Work worker is told to merge the current run branch, then receives the request in
its existing session. Otherwise a replacement inherits the matching role's approved vendor and tier
and launches through `go`. `human` and `release` requests are printed and retained as operator
actions and never become Work units. `clean --merged` keeps every worker carrying an outstanding
request; once all Work repairs land, `land` resubmits the landed revision through the same controller.
Operator-owned requests prevent that resubmission.

## State

One file, `.orchestrate/run.json`: run id, source, base commit, the verbatim review result and routing
state, and per unit its name, vendor, model, effort, task, role, owned paths, outstanding fix requests,
dependencies, worktree, branch, tab, Herdr agent name, and status. If session state is wrong,
`herdr agent list` is the real truth.

`start` adds `.orchestrate/` to the driven repository's local `.git/info/exclude`, preserving every
existing rule and never duplicating its own. The run record and task material therefore stay local
without making a fresh run appear as untracked source work.

**Hand-authored briefs belong in `.orchestrate/tasks/`.** Create that directory in the driven
repository, put the brief there, and give the unit the brief's absolute path (a unit runs in a
different worktree, so a repository-relative path points at the wrong tree). Do not use a session
scratchpad or `/tmp`: those paths can disappear while the run record still names them. Generated
long-task handovers already use this directory and the same containment boundary.

The unit's `name` is the dependency key and never changes. The wrapper uniquifies agent names, so
what herdr calls the session is recorded separately as `agent_name`.

## Workspaces

A herdr workspace is the unit of attention, not of isolation — isolation is the worktree. Below
about six concurrent units, one workspace is right and a second is overhead; above that, one
workspace becomes a wall of tabs and the operator can no longer see what is waiting on them. One
issue is one lifecycle and a lifecycle is the natural workspace, so a parent with nine children is
nine workspaces plus the umbrella the orchestrator sits in.

The run's `workspace` field is the name every unit inherits; a unit may set its own `workspace` and
that wins. There is no other precedence. `agent_argv` emits `--workspace <name>` with `--task` and
`--cwd`, before the vendor token. Absent both fields, the session lands in the caller's workspace —
today's behaviour.

The agent wrapper's `--workspace` takes a **name**, not an ID: handed an ID it creates a new
workspace called that rather than joining the one you meant. Do not pass it through `launch_args` —
that position is after the vendor token, and a live run that did so lost the session into the
caller's workspace.

## Agents

`orchestrate.py roster` intersects the vendors orchestrate knows how to drive with what the wrapper
can launch here, asked every time — the `Tools:` section of
`agents --help`, **never `--crews`**, which is the operator's own workspace presets and silently
drops installed agents. `start` and `expand` refuse a unit naming an agent the wrapper cannot
launch, so a typo fails before any worktree exists. The wrapper is `agents`, with an `s`; override
with `ORCHESTRATE_AGENT_LAUNCHER`. Model and effort flags are per vendor:

| Vendor | model | effort |
|---|---|---|
| claude | `--model` | `--effort` |
| codex | `--model` | `-c model_reasoning_effort=` |
| grok | `-m` | `--reasoning-effort` |
| muse | `--model` | `--reasoning-effort` |
| agy | `--model` | `--effort` |
| qwen | `-m` | via `setup` |
| opencode | `-m` (as `provider/model`) | via `setup` |

**Favourites.** `~/.config/orchestrate/models.json` maps a vendor to the models the operator
actually uses, most-preferred first — `{"opencode": ["deepseek/deepseek-v4-pro"], "codex": [...]}`.
`roster --models` shows them above the vendor's full list. Absent or unreadable, nothing changes; it
is a convenience, never a constraint, and a model not listed is still perfectly usable.

**Every vendor can be given a tier.** Where the command line has no flag, the unit's `setup` list
carries slash commands sent into the session before its task — `["/effort high"]` — so the session
is at the requested tier before it is given work. `roster --probe` compares this table against each
tool's own help and reports drift; run it after an agent updates.

An agent not listed launches with no model flags. **qwen does not report interactive readiness**, so
`herdr agent prompt` refuses it; the script falls back to typing into its pane, which is what an
operator would do by hand.

## Writing, and saga commands

**Every unit is launched able to write its own worktree** — `--permission-mode acceptEdits` for
claude, `--sandbox workspace-write` for codex, and so on per vendor. Without it each one runs at its
vendor's default, which is read-only or ask-first: two competing plans were once produced at xhigh
and both lost, because neither session could save a file. The worktree is the blast radius, so this
grants writing there and nothing wider.

**Saga is installed for every vendor, but invoked differently.** `orchestrate.py saga <cap>` prints
the right form — `/saga:plan` for claude, `$saga:plan` for codex, `/plan` for grok, qwen and
opencode. A bare `/plan` is a command nowhere and arrives as prose.

## Waiting, and empty dependencies

`orchestrate.py wait` subscribes to herdr's event socket and blocks until one of the running units
settles — nothing is polled for the wake, but a single `idle` is not a settlement. An agent is also
idle between turns, so `wait` confirms across consecutive observations the same way `settle` does
(`--interval`, `--confirmations`, `--once`). `blocked` returns on the first sighting and is named.
Subscriptions are keyed by pane, which is why a unit records its `pane_id` at launch; if the socket
is unreachable it falls back to one `herdr agent wait` per unit, under the same confirmation rule.

`go` refuses to launch a unit whose `after` dependency committed nothing. A dependent unit opens
on its dependency's branch, so an empty branch means the thing it is supposed to work on does not
exist — and a session given nothing writes something plausible about nothing rather than failing.
The refusal is `after` only: a `serialize` dependency may commit nothing at all, because the unit
waiting on it never needed its output — only for it to be out of the way.

## What this deliberately does not do

It does not verify that a session "really" finished, count tokens, enforce a spend ceiling, reserve
concurrency slots, run a voting panel, or keep a durable register with locks. If a unit went wrong,
you have its worktree, its branch, and its tab — look at them.

An earlier implementation did all of those things, in 14,875 lines of production code and about
15,700 lines of tests. It is preserved on `origin` at `archive/orchestrate-full-implementation` if a
real failure ever justifies pulling a piece of it back.
