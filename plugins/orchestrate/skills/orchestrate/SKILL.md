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
python3 "$S" settle                                # sessions with branch evidence become done
python3 "$S" expand --plan .orchestrate/next.json  # append units a finished phase named
python3 "$S" review-result --file <result.json>     # persist the typed result and route repairs
python3 "$S" land                                  # merge finished unit branches onto the run branch
python3 "$S" collect                               # merge the run branch into the operator tree
python3 "$S" clean --branches                      # close tabs, remove worktrees
```

Standard library only, so `python3` — not `uv run`, which would need the target repo to be a uv
project.

`go` launches only units whose ordering edges are all satisfied — every name in `after` and
`serialize` done — so calling `settle` then `go` again is what releases the next wave.

**Prompt delivery is confirmed before a unit is marked running.** After sending the initial
task prompt, Orchestrate waits for an acceptance signal (`took_the_task` observing the session
leave idle). If the prompt was swallowed (for example by a vendor startup dialog while Herdr
reported `interactive_ready`), Orchestrate retries delivery up to 2 times while the session
remains continuously idle. If still unaccepted, the unit is recorded in the named failure state
`prompt_undelivered` with a warning note, rather than being left silently running.

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

**Single launch seam and no-focus invariant.** Every run unit, including units added at a later
phase boundary, must be persisted through `start` or `expand` before any worktree or session is
created, and must launch only through `go` via the shared `agent-launcher` plugin (`agent_argv`).
Never create worktrees manually or invoke `agents` directly for a run unit. Direct wrapper calls
bypass the background launch flags (`--no-focus --current --herdr --herdr-control-only`) and steal
operator UI focus. The launch contract lives in `plugins/agent-launcher/`; Orchestrate does not
keep a private copy. Orchestrate declares `agent-launcher >=1.0.0` as a dependency; if the companion
is unresolvable, `roster`, `start`, `expand`, and `go` fail fast before any session or worktree is
created, reporting the exact supported remediation (`claude plugin install agent-launcher@infiquetra-plugins`).
Unsupported post-launch setup (such as interactive OpenCode variant selection) is a
controlled post-launch step, not a license to bypass `expand` or `go`. A branch in the run's
`orch/<run-id>-<unit>` series with no row in the table is flagged as unrecorded drift by `status` and
`check`, requiring explicit adoption with `adopt --yes` or run-owned cleanup rather than being
silently treated as valid expansion. That detection reads branches and nothing else: a hand-made
worktree or session named outside that series is invisible to both commands, which is the second
reason never to make one.

**Reviewer seats live in the run record, not engine-prefs.** The `.saga/engine-prefs.json` seam is
retired (#776). External-reviewer selection is a named unit in the plan (`role: external-reviewer`)
launched through `expand`/`go`. A plan that still carries `engine_prefs` is refused. When a Code
Review phase is present, Orchestrate refuses plain review prompts, direct reviewer launches, and
duplicate review units. Halt; never fall back to the retired saga external-engine runner.

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
state, and per unit its name, vendor, model, effort, account, task, role, owned paths, outstanding fix requests,
dependencies, worktree, branch, tab, Herdr agent name, status, `variant`, and `launch_receipt`. If
session state is wrong, `herdr agent list` is the real truth.

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

## Accounts

An explicit operator account selection survives into every worker launch and is verified post-launch.
The run's `account` field (`company` or `personal`) is the default every unit inherits; a unit may set
its own `account` and that wins. There is no other precedence.

For Claude units, selecting `company` emits `--company-account` after the vendor token, directing the
wrapper to swap configuration directories (`~/.claude-company`) before launching. The field is Claude-only
today: other vendors ignore it, and a vendor-specific account flag goes in that unit's `launch_args`.

**Post-launch account verification.** Before the task is submitted, Orchestrate reads the session's own
statusline off the pane, which reports the account the wrapper put the session on (`jefcox [company]`
against a plain `jefcox`). Where a machine does not print that, it falls back to which transcript root
(`~/.claude-company/projects` vs `~/.claude/projects`) holds the session. If the account read back is not
the one the plan asked for — or if no account can be read at all within `ACCOUNT_SETTLE_SECONDS` —
Orchestrate closes the run-owned session and marks the unit launch failed with the named state
`account_mismatch`, never allowing a unit to silently run under the wrong account. A plan naming an
account value other than `company` or `personal` fails the same way rather than quietly launching
under whatever the environment defaults to. A unit that sets no `account` is not checked and keeps
today's behaviour.

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
| opencode | `-m` (as `provider/model`) | via `/variants` picker |

**Model authority boundary: live catalog, never stale tables.** External worker and reviewer
availability, exact model names, and effort or variant controls come **only** from the installed `agents`
wrapper and vendor-native live catalogs or help (such as `roster --models` querying `grok models`,
`agy models`, `opencode models`, or vendor `--help` output) — **never** from Fleet Commons tier data
(`fleet_commons.tier_resolver`) or `~/.config/orchestrate/models.json`.

- **Model-aware dry run proof:** Run `python3 "$S" roster` (or invoke `start` / `expand` with a candidate
  plan JSON) to verify that the wrapper recognizes the vendor and that model/effort flags assemble properly
  via `agent_argv`. Success is exit 0 with the vendor listed and valid launch arguments emitted.
- **Bounded real launch proof:** Dispatch a test or single unit via `python3 "$S" go` under defined timeout
  bounds (`LAUNCH_SETTLE_SECONDS = 30.0` for interactive readiness, `DELIVERY_CHECK_SECONDS = 15.0` for prompt
  acceptance). Success is the session transitioning out of idle, `took_the_task` returning true, and the unit
  entering `running` status rather than `prompt_undelivered` or `account_mismatch`.
- **Herdr verification bounds:** Herdr proves only the workspace, pane, working-directory (`cwd`), and
  readiness facts its own API exposes (`herdr agent list`) — nothing about models.
- **Internal tier decoupling:** Fleet Commons retains internal Team Execution tier semantics intact, but
  never gates or renames external Herdr routes.
- **Provider route preservation:** `opencode-go` is an OpenCode provider (e.g.,
  `opencode-go/muse-spark-1.2-contributor`), not an agent kind (`opencode`); exact provider/model identities
  and advertised variants are preserved verbatim.
- **Refusal and no substitution:** `start` and `expand` refuse unknown vendors (`assert_vendors_available`);
  interactive variant selection refuses unadvertised OpenCode variants (`resolve_opencode_variant`); and
  `agent_argv` emits exact requested parameters with no silent substitution of model, provider, effort,
  account, or agent kind.

**Favourites.** `~/.config/orchestrate/models.json` maps a vendor to the models the operator
actually uses, most-preferred first — `{"opencode": ["deepseek/deepseek-v4-pro"], "codex": [...]}`.
`roster --models` shows them above the vendor's full list. Absent or unreadable, nothing changes; it
is a convenience, never a constraint, and a model not listed is still perfectly usable. Favourites
provide preference ordering only, never an allowlist or reachability constraint, and reordering or
truncating favourites never changes which models are reachable.

**Every vendor can be given a tier.** Where the command line has no flag, tier is established before
task submission: for OpenCode, Orchestrate drives the interactive `/variants` picker inside the
Herdr session and verifies the effective variant; for vendors supporting slash commands, the unit's
`setup` list carries slash commands sent into the session — `["/effort high"]` — before work starts.
`roster --probe` compares this table against each tool's own help and reports drift; run it after an
agent updates.

An OpenCode unit names the variant it wants in its own `variant` field, falling back to `effort`
when it has none. An exact name must appear in the live picker or the launch stops; `max`,
`maximum`, `maximum available`, `max available` and `highest` all mean *the highest the picker
actually offered*, which on Muse is `xhigh` rather than a literal `max`.

**A launch receipt records what was checked, not what was asked for.** Each unit's `launch_receipt`
carries the provider, model, variant, account, working directory, worktree, workspace, pane and readiness it
launched with, plus `confirmed_against_herdr` and `requested_only` naming which of those were held
against `herdr agent list` and which were not. `herdr agent list` publishes `cwd`, `workspace_id`
and `interactive_ready` per session and **publishes no model at all**, so a model is always
`requested_only` — the receipt says so rather than implying a check nothing could perform. A
working directory or workspace that disagrees with the plan closes that run-owned tab and fails the
unit before its task is submitted.

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

**Three supported waiting shapes.** When an agent session needs to wait for work in flight, use the
supported mechanism for the specific waiting shape. Follow the explicit rule: **never chained sleep**
polling in a foreground turn (for example, `sleep 25 && gh pr checks` or `sleep 45 && herdr agent
read`). The execution guard intercepts and rejects chained sleep commands immediately, costing a
turn per occurrence, and its own remedy is to wait through a mechanism that blocks somewhere other
than the turn — a native wait, a Monitor, or a backgrounded run whose completion notifies the
session. Use the supported pattern instead:

1. **Sibling Herdr agent output or unit settlement:** For whole-unit settlement waits across an
   orchestration run, use `orchestrate.py wait` (described below). For a specific sibling Herdr
   session or pane, use Herdr's native `herdr agent wait` or `herdr pane wait-output`. Both wait
   indefinitely without `--timeout`, so pass one. `herdr agent wait` returns on a single `idle`,
   which an agent also shows between turns — for settlement rather than a pause, prefer
   `orchestrate.py wait`, which confirms the reading before it believes it.

   ```bash
   # Wait for any running unit in the orchestration to settle
   python3 "$S" wait

   # Or wait for a specific sibling Herdr session to settle
   herdr agent wait worker-session-name --timeout 600000

   # Or wait for a pane to match a specific output pattern
   herdr pane wait-output "$PANE_ID" --match "UNIT-DONE" --timeout 600000
   ```

2. **Pull request checks and external asynchronous state:** `gh pr checks` waits natively with
   `--watch`, so no poll loop is written at all. Run it detached — a `Monitor`, or a Bash call with
   `run_in_background` — and let its completion notify the session. Read the exit status, never the
   output text: without `--watch`, `gh pr checks` exits `0` when every check passed, `1` when one
   failed and `8` while any is still pending, whereas grepping the table for `pending` reports
   success the moment a single check passes.

   ```bash
   # Detached; blocks inside gh until every required check finishes. Exit 0 all passed, 1 a failure.
   gh pr checks "$PR_NUMBER" --required --watch --fail-fast
   ```

3. **A command the session itself started:** Start it detached with `run_in_background` and let the
   completion notification wake the session; read its result from the log or result marker
   afterwards. Never `wait "$PID"` — that blocks the turn for the command's whole duration, which is
   the foreground wait backgrounding was meant to avoid, and a long gate run then dies on the tool
   timeout instead of finishing.

   ```bash
   # Started with run_in_background; the session is notified when it exits.
   GATE_LOG_DIR=/tmp/gate-run bash scripts/gate.sh > /tmp/gate.log 2>&1

   # Afterwards, read the outcome rather than re-running it
   cat /tmp/gate-run/result.txt
   ```

**Settlement waits with `orchestrate.py wait`.** `orchestrate.py wait` subscribes to herdr's event socket
and blocks until one of the running units settles — nothing is polled for the wake, but a single `idle`
is not a settlement. An agent is also idle between turns, so `wait` confirms across consecutive
observations the same way `settle` does (`--interval`, plus `--confirmations` on `wait` and `--once`
on `settle`). `blocked` returns on
the first sighting and is named. Subscriptions are keyed by pane, which is why a unit records its `pane_id`
at launch; if the socket is unreachable it falls back to one `herdr agent wait` per unit, under the same
confirmation rule.

**Evidence-based settlement.** `orchestrate.py settle` marks running units `done` only when there
is completion evidence on the unit branch (`produced_anything`). A session that is merely idle
without commits stays running — idle is also what an agent looks like between turns, thinking. A
session closed or gone after committing its work settles `done` (never `failed` for committed work),
while a session gone without commits yields a distinct `orphaned` state.

The gate is a reading of a branch, so it covers only units that have one. A unit with no branch of
its own — the review controller, `merge: false`, whose output arrives through `review-result` — is
not commit-gated and settles on the confirmed reading alone; gating it would wedge the review loop
at `running` forever, because no commit can ever appear on a branch it does not have. When the run
branch itself does not resolve the commit count is unknown rather than zero: such a unit stays
`running` and says so, and a gone session is recorded `orphaned` with a note that the commits could
not be checked — the same "branch-dependent checks are unavailable" line `adopt` and `clean` print.

`go` refuses to launch a unit whose `after` dependency committed nothing. A dependent unit opens
on its dependency's branch, so an empty branch means the thing it is supposed to work on does not
exist — and a session given nothing writes something plausible about nothing rather than failing.
The refusal is `after` only: a `serialize` dependency may commit nothing at all, because the unit
waiting on it never needed its output — only for it to be out of the way.

## Per-run worker-pool declarations

Vendors, models, efforts, caps, and the integration target are **per-run operator inputs**, never
hard-coded into this skill. Copying a previous run's pool list into a new run as a default is the
same mistake.

Declare a **worker-pool** table beside the unit table the operator approves, before `start` records
the run. Each row is one pool, and every row records four fields:

| Field | What it records |
| --- | --- |
| Priority order | The highest-priority pool with a free slot takes the next unit; ties break in the approved unit table's own row order. No pool is held idle to spread load, and no parallelism beyond the declared caps is invented |
| Per-pool cap | Simultaneous session cap for that pool |
| Launch template | The vendor · model · effort (and account, if the vendor uses one) used to launch units on that pool |
| Exercised-or-not at closeout | Whether any unit actually ran on this pool. An unexercised pool is recorded as unexercised — it is not evidence that the pool works |

A filled row uses placeholders for everything the operator supplies, so no vendor or model is
baked in here:

| Pool | Priority | Cap | Launch template | Closeout |
| --- | --- | --- | --- | --- |
| `<pool-name>` | 1 | `<n>` | `<vendor>` · `<model>` · `<effort>` · `<account>` | exercised / unexercised |

The table is guidance the orchestrator follows when filling the approved unit table. It is not
scheduler or driver machinery.

## Authoritative integration branch — reintegrate after every serialized landing

Each run declares its **authoritative integration branch** up front. Two example declarations, not
policy: `origin/main` for a flat-PR run; the Orchestrate run branch when the run integrates onto
one. The target is a per-run operator input, never a hardcoded universal.

Pull requests merge one at a time, in a single serialized queue. After each merge, the session
owning each surviving worktree immediately fetches the declared target and merges it, then
re-resolves that repository's release-surface versions against the newly landed target before
continuing. Do not wait for the next wave or for a conflict to appear.

```bash
# From each surviving worktree, after every merge. TARGET is the run's declared branch.
git fetch origin
git merge "$TARGET"        # merge, never rebase
```

**Merge, never rebase.** These branches carry open pull requests, and a rebase rewrites every
commit on them. Orchestrate's review records are revision-bound — each one names the exact reviewed
SHA — so a rebase strands those records against commits that no longer exist, and the force-push it
requires lands on top of the head a reviewer froze.

Shared files re-dirty every still-open pull request on each merge; in this repository those are
`plugin.json`, `CHANGELOG.md` and `.claude-plugin/marketplace.json`. Immediate reintegration is the
standing response.

## What this deliberately does not do

Evidence-based settlement checks completion evidence on the branch (`produced_anything`), but
deliberately does not count tokens, enforce a spend ceiling, reserve concurrency slots, run a
voting panel, or keep a durable register with locks. If a unit went wrong, you have its worktree,
its branch, and its tab — look at them.

An earlier implementation did all of those things, in 14,875 lines of production code and about
15,700 lines of tests. It is preserved on `origin` at `archive/orchestrate-full-implementation` if a
real failure ever justifies pulling a piece of it back.
