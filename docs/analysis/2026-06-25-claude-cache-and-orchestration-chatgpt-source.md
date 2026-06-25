# Source: ChatGPT — "Claude Cache Writes Costs" → orchestration architecture

**Type:** External conversation transcript — seed/source material, NOT a saga artifact.
**Origin:** Jeff's own ChatGPT conversation, shared link:
<https://chatgpt.com/share/6a3d4d7c-daac-83ea-883c-2dee8a8221fb>
**Pulled:** 2026-06-25. Page fetch returns only a JS shell and the browser extension was
unavailable, so the transcript was decoded from the share page's embedded React Router
`turbo-stream` payload. ChatGPT's `code` turns (web-search tool calls) were stripped; the
user/assistant text turns remain verbatim.

**Why it's here:** seed for a candidate saga improvement — an **outcome-level DAG layer**
("plugin-managed DAG runner") above saga's single-work-thread lifecycle, with
workflow / agent-team / subagent / fork / `/goal` as **interchangeable execution backends**.

## The saga-relevant thesis (turns 43–52)
Make a durable DAG runner the control plane OUTSIDE the chat session; let workflows, agent
teams, subagents, forks, and `/goal` be interchangeable execution backends; keep the human on
gates and exceptions. Saga already owns the *backend-choice* half (operator-choice: inline /
team-execution / cc-workflows-ultracode) plus per-work-thread durable state. The **new** idea is
the layer ABOVE: outcome → sub-outcomes → tasks, dependency ordering, per-node executor
recommendation, evidence rollup, and a `/outcome next` operator cockpit — i.e. the
saga ↔ mission-control (issues/sub-issues = DAG persistence) boundary.

Secondary operating conclusions worth keeping: worktree-per-sub-outcome (not per-task —
disposable worktrees = cold cache writes); persistent session per sub-outcome; forks when a
worker needs full context vs named subagents for isolation/different model; stage-bounded
workflows with human gates between (workflows can't take arbitrary mid-run input).

## ⚠️ Validation caveat (read before acting)
The Claude Code feature claims below — forks share the parent prompt cache; named subagents have
separate/cold caches; `/goal` evaluator semantics; agent teams ≈7× tokens in plan mode;
`CLAUDE_CODE_SUBAGENT_MODEL`; `workflowKeywordTriggerEnabled`; `/usage` attribution — carry
ChatGPT's internal `citeturn…` markers, which are NOT verifiable links and several are
drift-prone. Verify against current Claude Code docs before relying on any of them in a design.

**→ Verified 2026-06-25 against current Claude Code docs (results below).**

## Verification results (2026-06-25)

Checked against `code.claude.com/docs` and `platform.claude.com/docs`. **8/10 CONFIRMED, 2 NUANCED** — the architecture's foundation holds; neither nuance touches the outcome-DAG concept.

| # | Claim | Verdict | Note |
|---|---|---|---|
| 1 | Fork inherits parent context; first request reuses parent's cache | ✅ CONFIRMED | The crux of "interchangeable backends" |
| 2 | Named subagent: own prompt/tools, cold first call; 5-min TTL even on subscription | ✅ CONFIRMED | 1-hr TTL applies only to the main conversation |
| 3 | `/goal` real; small evaluator judges only what's surfaced in conversation | ✅ CONFIRMED | v2.1.139+; evaluator defaults to Haiku, configurable, calls no tools |
| 4 | Agent teams ≈7× tokens in plan mode | ✅ CONFIRMED | Verbatim in cost docs |
| 5 | `CLAUDE_CODE_SUBAGENT_MODEL` sets subagent model | ✅ CONFIRMED | Highest priority in subagent model resolution |
| 6 | `workflowKeywordTriggerEnabled` setting; `ultracode` keyword trigger | ⚠️ NUANCED | Keyword + `/effort` real; **that JSON key is not documented** — only `disableWorkflows`; keyword toggle is a `/config` UI control |
| 7 | `/usage` attributes to skills/subagents/plugins/MCP; `/workflows` token totals by phase/agent | ✅ CONFIRMED | Paid plans only |
| 8 | Workflows: only permission prompts pause; script in session dir; intermediates stay in script vars | ✅ CONFIRMED | Load-bearing: why human gates require splitting into stage-bounded workflows |
| 9 | Writes 1.25×(5m)/2×(1h), reads 0.1×; break-even after 1/2 reuses | ✅ CONFIRMED | Multipliers exact; break-even derivable |
| 10 | Cache key = model + effort + fast-mode header; MCP deferred by default | ⚠️ NUANCED | model+effort ✓; fast-mode **only initial enable** misses (v2.1.86+ preserves on toggle); MCP deferral **not** on Haiku/Vertex/custom `ANTHROPIC_BASE_URL` |

**Corrections a design must NOT carry forward:**
1. No `workflowKeywordTriggerEnabled` JSON key — only `disableWorkflows: true`. The keyword-only toggle is a `/config` UI control with no documented JSON equivalent.
2. Fast-mode cache invalidation is asymmetric — only the initial enable forces a full miss; on v2.1.86+ later off/on toggles preserve the cache.
3. MCP tool-definition deferral is model/provider-conditional — Haiku, Vertex AI, and sessions behind a custom `ANTHROPIC_BASE_URL` gateway do NOT defer (tools load into the prefix).

Sources: `code.claude.com/docs/en/{prompt-caching,goal,costs,model-config,workflows}`, `platform.claude.com/docs/en/build-with-claude/prompt-caching`.

---

## Transcript: Claude Cache Writes Costs


===== USER =====

Telll me about Claude cache wrights. It’s my biggest cost. How does it work? I can’t for the life of me figure out how do reduce. Does ultracode use more cache writes?

===== CHATGPT =====

I’ll verify current Anthropic cache pricing, explain what cache writes are, then connect the mechanics to coding-agent workflows like UltraCode and concrete ways to reduce costs.

===== CHATGPT =====

The docs point to repeated cold prompt prefixes as the real issue: writes are front-loaded cache storage, and savings only appear when later requests reuse them as cheaper reads.

===== CHATGPT =====

You’re probably looking at **`cache_creation_input_tokens`**. That is Claude’s “cache writes” line.

The key thing: **cache writes are not some mysterious extra activity by your code. They are newly cached prompt-prefix tokens.** Claude Code sends a large prompt context over and over: system prompt, tools, project instructions, repo context, conversation history, tool results, and your latest instruction. Prompt caching lets Anthropic store the unchanged beginning of that prompt so later turns can pay the much cheaper **cache read** price instead of full input price. Claude Code’s docs describe this as automatic prefix caching, not per-file caching or per-segment caching. citeturn999974view0

## The mental model

Think of each Claude request like this:

```text
[stable prefix: system/tools/CLAUDE.md/history/repo context] [new stuff this turn]
```

When Claude sees a stable prefix for the first time, it may create a cache entry:

```text
cache write = cache_creation_input_tokens
```

On later turns, if the prefix is **exactly the same**, Claude can reuse it:

```text
cache read = cache_read_input_tokens
```

The “exactly the same” part matters. Anthropic says cache hits depend on exact prefix matching, stable ordering, the same model/configuration, the same TTL, and an unchanged cached section. Changing things before the cache breakpoint creates a different hash and therefore a new write. citeturn252413view0

## Why it feels expensive

Cache writes cost more than normal input tokens, but cache reads are much cheaper.

Current Anthropic pricing docs say prompt-cache writes are billed at **1.25× base input** for 5-minute cache, **2× base input** for 1-hour cache, while cache reads are **0.1× base input**. For example, Claude Sonnet 4.6 is listed at $3/MTok base input, $3.75/MTok 5-minute cache write, $6/MTok 1-hour cache write, and $0.30/MTok cache hit. Opus 4.8 is $5 base input, $6.25 5-minute write, $10 1-hour write, and $0.50 cache hit. citeturn743063view1 citeturn588517view1

So cache writes can look terrible in the bill, but the question is whether they are followed by enough reads.

Break-even is roughly:

```text
5-minute cache write: pays off after 1 reuse
1-hour cache write: pays off after 2 reuses
```

Anthropic’s docs say the same thing: 5-minute cache writes pay off after one read, and 1-hour cache writes after two reads. citeturn743063view1

So the bad pattern is not:

```text
high cache writes
```

The bad pattern is:

```text
high cache writes + low cache reads
```

A healthy coding session often looks like:

```text
Turn 1: big cache_creation_input_tokens, low cache_read_input_tokens
Turn 2: small new write, huge cache_read_input_tokens
Turn 3: small new write, huge cache_read_input_tokens
```

An unhealthy setup looks like:

```text
Turn 1: huge cache_creation_input_tokens
Turn 2: huge cache_creation_input_tokens again
Turn 3: huge cache_creation_input_tokens again
```

That means Claude is repeatedly seeing “new” prefixes instead of reusing the old one.

## Why your cache writes are probably high

Given your Hermes / agent-VM style setup, I’d suspect **lots of cold Claude sessions, subagents, changing directories, changing effort levels, and UltraCode workflows** before I’d suspect “normal Claude Code usage.”

Claude Code says the cache is effectively scoped to the same machine and directory. Worktrees can differ. Parallel sessions in the same directory can share more effectively, but sequential sessions only share if the git status snapshot matches. citeturn452093view0

Also, model and effort level are part of the cache key. So if you switch between Sonnet, Opus, `opusplan`, high effort, xhigh effort, UltraCode, or fast mode, you can blow the cache and create a new write-heavy prefix. citeturn999974view2 citeturn999974view3

Other common invalidators:

```text
/model changes
/effort changes
/compact
/clear
new Claude Code process
different repo path or worktree
different tool definitions
MCP server changes
tool permission changes in some cases
image inputs
thinking parameter changes
web search / citations toggles
subagent starts
TTL expiry
```

Anthropic’s prompt-caching docs specifically call out tool definitions, tool choice, images, thinking parameters, web-search/citation changes, and other request-structure changes as cache-affecting. citeturn252413view3

## Does UltraCode use more cache writes?

**Yes, usually.**

Not because “UltraCode cache writes are priced differently,” but because UltraCode tends to create **more unique work**, **more agents**, **more requests**, and **more fresh prefixes**.

Claude Code’s docs describe UltraCode as a setting that uses `xhigh` effort and can orchestrate dynamic workflows for substantive tasks. Dynamic workflows can run many subagents; Anthropic’s docs say these workflows can scale to dozens or hundreds of agents and can consume substantially more tokens than a typical session. citeturn248235view2 citeturn506436view0 citeturn506436view4

The killer detail: Claude Code says **a subagent starts its own conversation with its own system prompt and tool set**, and that subagent starts with **no cache hits**. On subscriptions, subagents still use a five-minute TTL according to the Claude Code caching docs. citeturn452093view0

So UltraCode can be great for a big migration, broad codebase audit, or multi-pass verification task. But for normal “edit this file,” “fix this bug,” or “implement this small feature,” it can be overkill and can absolutely inflate cache writes.

My read: **UltraCode is likely one of your biggest cache-write multipliers** if you’re using it as a default mode.

## What I would change first

### 1. Stop using UltraCode as the default

Use normal Sonnet for routine coding. Save UltraCode for large, cross-cutting tasks where many agents are actually valuable.

Good UltraCode tasks:

```text
audit this whole repo for auth bugs
migrate this package from SDK v2 to SDK v3
compare three architecture options across the codebase
find all API compatibility breaks
large refactor with verification
```

Bad UltraCode tasks:

```text
fix this failing test
add one endpoint
update this CloudFormation resource
explain this file
write a small script
```

In Claude Code, UltraCode can also be triggered by the keyword `ultracode`; the config has a `workflowKeywordTriggerEnabled` setting for whether that keyword starts a workflow. Turning that off helps prevent accidental expensive workflows. citeturn506436view2 citeturn743063view3

### 2. Pick model and effort at session start, then stop switching

This matters a lot. Model and effort are part of the cache key. Switching midstream can force new cache writes. citeturn999974view2

For your setup, I’d default to something like:

```text
Routine coding:       Sonnet, medium/high
Architecture review:  Opus, high/xhigh
Massive workflow:     UltraCode, only intentionally
Tiny subagents:       Haiku or Sonnet where acceptable
```

Claude Code also supports setting the subagent model through `CLAUDE_CODE_SUBAGENT_MODEL`, which can help keep subagents from defaulting to something too expensive. citeturn506436view3

### 3. Reduce short-lived Claude processes

This is probably huge for Hermes.

If your orchestrator is doing this repeatedly:

```text
start Claude
send one task
exit
start Claude again
send another task
exit
```

you are creating lots of cold cache-write opportunities.

Better:

```text
keep one Claude session warm per repo/task lane
reuse the same working directory
batch related work into one session
avoid unnecessary worktrees
avoid restarting the agent for each tiny step
```

Claude Code says each message is a new API request, but caching works best when the start of the prompt is stable across those requests. It is not magic global memory across arbitrary directories and machines. citeturn999974view0 citeturn452093view0

### 4. Watch the read/write ratio, not just writes

In Claude Code, use:

```text
/usage
```

Claude Code exposes session token stats, including estimated cost and usage breakdowns. Anthropic specifically says to look at `cache_creation_input_tokens` for writes and `cache_read_input_tokens` for reads; high read-to-creation is good, while high creation turn after turn suggests the prefix is changing. citeturn626385view0 citeturn452093view0

My practical heuristic:

```text
Good:
cache_read_input_tokens >> cache_creation_input_tokens after warmup

Suspicious:
cache_creation_input_tokens stays large every turn

Bad:
cache_creation_input_tokens ≈ cache_read_input_tokens, or reads stay near zero
```

For 1-hour cache, I’d want at least **2+ reads per write**. For 5-minute cache, at least **1+ read per write**.

### 5. Shrink the stable prefix

Big `CLAUDE.md`, lots of loaded MCP tools, giant project context, and broad always-on instructions all increase the amount that may be written.

Claude Code’s cost docs recommend keeping `CLAUDE.md` concise, moving specialized instructions into skills, disabling unused MCP servers, preferring CLI tools where possible, and using hooks/skills to reduce repeated context-heavy work. citeturn626385view4 citeturn626385view5

For you, I’d be aggressive here:

```text
Root CLAUDE.md: only universal rules
Repo CLAUDE.md: repo-specific rules only
Skills: task-specific procedures
MCP: only enabled when actively needed
Logs/test output: summarize or filter before feeding to Claude
```

### 6. Use `/compact` intentionally, not constantly

`/compact` replaces conversation history with a summary. That can be useful, but it invalidates the conversation-history layer of the cache. Claude Code docs recommend running it at natural task boundaries rather than constantly. citeturn999974view4

Bad:

```text
compact every few turns
```

Better:

```text
finish one logical task
compact with clear instructions
start next task
```

Also, `/clear` is good between unrelated tasks, but it creates a fresh context. So it reduces long-context cost but may increase cold writes. Use it when changing tasks, not as a random cleanup reflex. citeturn626385view3

### 7. Consider 1-hour cache only when your sessions have gaps

For API/Bedrock/Vertex/Foundry usage, Claude Code defaults to 5-minute caching unless 1-hour caching is enabled. Claude Code docs say subscription users normally get 1-hour TTL automatically, but usage credits can drop to 5-minute TTL. citeturn452093view0

For API-style usage, this can matter:

```bash
export ENABLE_PROMPT_CACHING_1H=1
```

But don’t blindly enable it. One-hour writes cost 2× base input, so they are only worth it when you will reuse the prefix after more than five minutes but within an hour. Anthropic’s guidance is basically: use 5-minute cache for frequent reuse, 1-hour cache when reuse happens less often but still within the hour. citeturn252413view5

## The likely diagnosis

For your setup, I’d bet the biggest contributors are:

```text
1. UltraCode / dynamic workflows spawning many agents
2. Subagents starting with fresh cache state
3. Many short Claude Code sessions from Hermes
4. Model/effort switching
5. Different VM/repo/worktree directories
6. Large always-on CLAUDE.md / MCP/tool context
7. 5-minute TTL expiry between agent steps
```

The fastest cost cut is probably:

```text
Turn UltraCode off by default.
Keep sessions warm.
Stop switching effort/model mid-task.
Use Sonnet for most work.
Use cheaper subagent models.
Trim always-on context.
Track cache_read/cache_creation ratio per task type.
```

And don’t disable prompt caching as a cost fix. That usually makes total cost worse, because you lose the 0.1× cache-read price and go back to paying normal input price for repeated context. Anthropic exposes `DISABLE_PROMPT_CACHING`, but the Claude Code docs frame it as something to use for special cases, not normal cost optimization. citeturn999974view8

===== USER =====

So actually for home lab it’s not bad. It’s at works it’s worse. For home, 91% cache hit and $12 cache write premium. At work it’s 88% cache hit and $75 cache write premium

===== CHATGPT =====

That changes the read: those hit rates are actually healthy. The remaining question is whether work has much higher total volume or a few workflows creating expensive cold prefixes.

===== CHATGPT =====

Yeah — that changes the interpretation a lot.

**Home lab is fine. Work is not “bad caching”; it is “much more volume.”**

A **91% cache hit rate** at home means roughly:

```text
For every 1 token written to cache,
~10.1 tokens are read from cache.
```

An **88% cache hit rate** at work means roughly:

```text
For every 1 token written to cache,
~7.3 tokens are read from cache.
```

That is worse, but it is still a pretty good cache ratio. Anthropic’s pricing says cache reads cost about **10% of normal input**, while cache writes cost **1.25× normal input for 5-minute cache** or **2× for 1-hour cache**; they say 5-minute cache pays off after one reuse, and 1-hour cache after two reuses. At 88%, you are way beyond break-even. citeturn988023view2

The real clue is this:

```text
Home: 91% hit, $12 cache-write premium
Work: 88% hit, $75 cache-write premium
```

Work’s premium is:

```text
$75 / $12 = 6.25× home
```

But the miss/churn rate only changed from:

```text
Home miss side: 9%
Work miss side: 12%
12 / 9 = 1.33× worse
```

So the hit-rate difference explains only a small part of the cost. If model, TTL, and pricing basis are similar, work is probably creating roughly:

```text
6.25 / 1.33 ≈ 4.7×
```

more cacheable-prefix churn than home.

So I would **not** frame work as “cache is failing.” I’d frame it as:

> Work has an okay cache hit rate, but the cached prefix being rewritten is much larger or happens much more often.

## What $75 might actually mean

Assuming your report’s **cache write premium** means “extra cost above normal input”:

For **5-minute cache**, the write premium is 25% over base input. So:

```text
$75 premium ≈ $300 of base-equivalent input written to cache
$12 premium ≈ $48 of base-equivalent input written to cache
```

For **1-hour cache**, the write premium is effectively another full base-input charge. So:

```text
$75 premium ≈ $75 of base-equivalent input written to cache
$12 premium ≈ $12 of base-equivalent input written to cache
```

The exact conversion depends on whether work is using API/Bedrock/Vertex/Foundry versus a Claude subscription, because Claude Code uses different TTL behavior depending on authentication. On API or third-party providers, Claude Code defaults to cheaper 5-minute caching unless you opt into 1-hour caching; on a Claude subscription, the main conversation gets 1-hour TTL automatically, while subagents still use 5-minute TTL. citeturn493369search1

## The practical conclusion

Your home numbers are good. I would not spend much effort optimizing home.

At work, I would look for **absolute token volume**, not just hit rate.

The likely culprits are:

```text
large CLAUDE.md / repo instructions
large MCP/tool context
agent teams or dynamic workflows
subagents
long sessions resumed after TTL expiry
model or effort switching
fast mode toggles
/compact at awkward times
multiple worktrees or different directories
huge tool outputs: logs, test output, grep results, build output
broad prompts like “analyze this repo”
```

Claude Code’s own docs say costs scale with context size, recommend `/usage`, `/context`, concise `CLAUDE.md`, disabling unused MCP servers, using CLI tools where possible, and moving specialized instructions into skills. citeturn858299view0

## My read on the work setup

At **88%**, cache is still doing its job. The scary number is **$75 premium**, but that premium may be buying a lot of savings if the reads are large.

The thing to optimize is probably:

```text
cache_creation_input_tokens per task
```

not merely:

```text
cache hit %
```

You want to find which workflows are creating huge cache writes. I’d break work usage down by:

```text
repo
user
session
model
effort level
subagent/agent team usage
MCP server
workflow type
UltraCode/dynamic workflow usage
```

Claude Code’s `/usage` can now attribute recent usage to skills, subagents, plugins, and MCP servers, which is exactly where I’d start. citeturn858299view0

## What I would do next at work

First, identify whether the $75 is coming from **a few monster sessions** or **constant small rewrites**.

If it is a few monster sessions, the cause is probably:

```text
UltraCode / agent teams
large repo scans
big test/log outputs
long stale sessions resumed after cache expiry
```

If it is constant small rewrites, the cause is probably:

```text
model switching
effort switching
fast mode toggles
MCP/plugin changes
different directories/worktrees
frequent /compact or /clear
Claude Code upgrades
```

Claude Code’s prompt-caching docs explicitly call out model switches, effort changes, fast mode, MCP/plugin changes, tool-denial changes, compaction, and upgrades as cache invalidators. It also says model and effort are part of the cache key, so switching either can force the next request to recompute the whole request even when the text is identical. citeturn858299view1

## Bottom line

**Home:** 91% hit / $12 premium = healthy. Leave it mostly alone.

**Work:** 88% hit / $75 premium = not terrible caching, but much higher token churn. The biggest win is probably reducing the amount of context Claude Code carries and reducing multi-agent/dynamic workflow usage, not trying to squeeze 88% to 91%.

The target is not “zero cache writes.” The target is:

```text
high cache reads
low unnecessary cache creation
small stable prefix
fewer expensive agent/team sessions
no accidental model/effort/workflow switches
```

===== USER =====

does /clear reset the cache?

===== CHATGPT =====

I’ll verify this against the current Claude Code docs, since `/clear` can affect conversation context differently from underlying cache entries and future cache-hit eligibility.

===== CHATGPT =====

Yes — **for the conversation cache, `/clear` effectively resets it.** But it does **not** delete Anthropic’s server-side cache entries like a “flush cache” command.

More precise:

```text
/clear = start a new conversation with empty context
```

Claude Code’s command docs say `/clear` starts a new conversation with empty context, while the previous conversation remains resumable via `/resume`. citeturn159054search0

So after `/clear`, Claude no longer sends the old conversation history, tool outputs, file reads, corrections, etc. That means the old long conversation prefix is no longer being reused. The next request has to build a new cache path for the fresh conversation.

But this does **not necessarily mean 0 cache hits** on the next turn. Claude Code’s cache is layered:

```text
system prompt / tools
project context / CLAUDE.md / memory
conversation history
```

Claude Code docs say `/clear` causes project context to reload, and prompt caching works by exact prefix matching. If the system prompt, tools, directory, model, effort, git status, and project context are the same, part of that prefix may still hit cache. The old conversation layer, though, is gone. citeturn944406view0

So the practical answer is:

```text
Does /clear reset the old conversation cache?     Yes.
Does it delete all server-side cache entries?     No.
Will the next turn often create cache writes?     Yes.
Will it always be a total cold start?             Not necessarily.
```

Cost-wise, `/clear` is usually good **between unrelated tasks**, because it prevents Claude from carrying a huge stale history. Claude’s best-practices docs explicitly recommend `/clear` between unrelated tasks to reset context. citeturn159054search7

But don’t use `/clear` repeatedly inside the same task. That can create this pattern:

```text
work a little
/clear
re-read files
rewrite project/context cache
work a little
/clear
re-read files
rewrite project/context cache
```

For same-task cleanup, `/compact` is often better because it replaces history with a summary instead of starting fresh. For a truly separate task, `/clear` is the right move.

===== USER =====

Lets consider this information:

large CLAUDE.md / repo instructions
large MCP/tool context
agent teams or dynamic workflows
subagents
long sessions resumed after TTL expiry
model or effort switching
fast mode toggles
/compact at awkward times
multiple worktrees or different directories
huge tool outputs: logs, test output, grep results, build output
broad prompts like “analyze this repo”

can we break them down and explain it to me in more detail. Let me add some context on at least some of them to better understand how I could even make a difference:

Large claude, large mcp I can understand and easily take action on if an issue
agent teams or dynamic workflows I have questions on: how does this make a difference. What are the tradeoff here. Let me explain:
1. are you saying I should do everything in the main session? given a task I would be switching models and efforts all over the place. as it stands I try to have either situation pick the right model/effort for each "agent" in the mix. Also isn't it still the same amount of tokens to get the job done? If I use agent teams, or a workflow or just do it all inline. What does that look like if I do it all inline. does that mean individual sessions? doesn't individual session mean new cache writes. I am struggling to see what the difference is, as I think given outcome A: if I use many subagents to orchestrate that completion vs doing every indvidual task 1 at a time that there would be any difference. Other than the HITL being the orchestrator and the time to complete the outcome being different. Stated differently... if an outcome has has 10 sub-outcome and each sub-outome has 10 sub-tasks. What is the difference if the HITL does each task in a different session? or does each sub-outcome in a different session. A typical way I work is: 1. take an outcome and plan what is needed to achieve it 2. That outcome becomes 10 sub-outcome and then 10-sub-tasks for each outcome. I am using claude to define all this and ultimately turn it into github issue with linked sub-issues. Then I start a session and ask claude to create a workflow (or an agent team) to complete the outcome. we plan out that execution. Then it runs while I manage the problems, failures, validations, etc... my 'feeling" is that if I did that all independently even bringing in other team members. It would take a week instead of hours. ok enough on that

long sessions: how do I properly manage this, whats the difference between this and new session? compact before I walk away? kill the session and start over? all of them seem like the would still create cache writes
model or effort... I try to keep main session all same, then subagents are form fit to the model/effort
worktrees. Here might be a big one actually. I was looking at a worktree as a task or branch. It sounds like you are saying I should maybe create a worktree in a repo once for the day. I often "clean up the worktree" between activities. You make it sound like that will create a brand new cache write. I should maybe just commit and PR/merge multiple times a day out of the same work tree

for tool output I have recently started using RTK
I do things like "analyze this repos" thats not often, and usually in one session to produce a single file output that is then handed off to another session. LIke gap analysis or reviews of documentations, etc...

===== CHATGPT =====

I’ll separate cache mechanics from workflow design: the answer is not “never use agents,” but choosing orchestration boundaries where parallelism or isolation outweighs duplicated context and cold starts.

===== CHATGPT =====

Your workflow may be rational; the target is avoiding expensive independent contexts for sequential or overlapping work. Subagents keep parent cache intact, but each named subagent starts separate; forks can inherit.

===== CHATGPT =====

Yes. Let’s break it down with your actual workflow in mind.

My main conclusion up front: **I would not tell you to stop using subagents, workflows, or agent teams.** Your workflow is trading money for wall-clock time, quality checks, and less HITL coordination. That can be a very good trade. The optimization is not “do everything in the main session”; it is **use the right parallelism shape for the amount of shared context each worker needs.**

The cache issue is this:

```text
Cache reuse is best when the same prefix keeps being reused.
Agent/workflow parallelism is best when work can be split into independent contexts.
Those two goals are sometimes in tension.
```

Claude Code’s prompt cache is prefix-based. Each turn re-sends system prompt, tools, project context, prior conversation, tool results, and the new message; the API can reuse the unchanged beginning of that request, but the match is exact. Claude Code orders the request roughly as system/tools first, then project context, then conversation history. Model and effort level are separate cache keys, so switching either causes a full cache miss even if the text is identical. citeturn356097view0

## The big distinction: cache reuse vs context isolation

There are four different patterns that can all look like “multiple agents,” but they have very different cache behavior.

```text
1. Main session only
2. Named subagents
3. Forks
4. Agent teams / dynamic workflows
```

### 1. Main session only

This gives you the best cache reuse **inside one model/effort/session/directory**, because each turn is mostly the same prefix plus new appended work. The downside is that every file read, test output, failed approach, discussion, and correction stays in the main context until you compact or clear.

So main-session-only is cheapest when the task is sequential and focused:

```text
add one endpoint
fix one failing test
change one CloudFormation resource
update one service method
```

But it becomes expensive in a different way when you ask it to investigate 100 files, run verbose tests, read logs, compare approaches, then implement. The cache hit rate may stay good, but every future turn is dragging around a huge conversation. Claude Code’s cost docs are explicit that token costs scale with context size, and stale context wastes tokens on later messages. citeturn932384view1

### 2. Named subagents

A named subagent starts its own conversation with its own system prompt and tool set. The parent session’s cache is unaffected, but the subagent starts with no cache hits on its first call and warms its own cache across its own turns. Subagents also use a five-minute TTL even when the main subscription session gets a one-hour TTL. citeturn356097view0

That means a subagent is **not free**, but it can still save money and quality because it keeps noisy exploration out of the main transcript.

Good subagent use:

```text
“Search the repo for all places this pattern appears and return only the relevant files.”
“Run the tests and summarize only failures.”
“Review this diff for correctness gaps.”
“Investigate auth flow and return a concise map.”
```

Bad subagent use:

```text
Spawn 20 one-shot agents that each need the same big project context and only do 30 seconds of work.
Spawn a new subagent every time instead of continuing an existing one.
Give every subagent a giant spawn prompt and access to every tool.
Use subagents for highly sequential same-file edits.
```

Claude’s docs describe subagents as useful when a side task would flood the main conversation with search results, logs, or file contents you will not reference again. They also emphasize that each subagent runs in its own context window and can use a focused model/tool set. citeturn307823view2

A useful nuance for your workflow: if a subagent is doing continuing work, **resume the same subagent** rather than repeatedly spawning a fresh one. Claude Code supports continuing a prior subagent; its transcript persists within the session and can be resumed after restarting the same session. citeturn436403view0

### 3. Forks

Forks are the missing middle ground.

A fork inherits the main session’s full conversation, system prompt, tools, and model. Unlike a named subagent, its first request can reuse the parent’s prompt cache. Claude’s docs explicitly say forks share the parent prompt cache, while named subagents have separate caches. citeturn436403view1

So the rule of thumb is:

```text
Use a named subagent when the worker does NOT need full main-session context.
Use a fork when the worker DOES need the same context as the main session.
```

Examples where a fork makes sense:

```text
“Given everything we’ve discussed, draft unit tests in parallel.”
“Try an alternate implementation approach from this exact current state.”
“Review the current plan using the same context, but don’t pollute the main thread.”
```

Tradeoff: a fork uses the same model as the main session. If you specifically want a cheaper or stronger different model, a named subagent or teammate is the more natural fit. citeturn436403view1

### 4. Agent teams and dynamic workflows

Agent teams are multiple Claude Code instances. Each teammate has its own context window. Token usage scales with the number of active teammates and how long they run. Claude’s docs say agent teams use significantly more tokens than a single session, and the cost guide says token usage is roughly proportional to team size; it even says agent teams can use approximately 7× more tokens than standard sessions when teammates run in plan mode. citeturn834220view5 citeturn932384view1

Dynamic workflows are different: Claude writes a JavaScript orchestration script, and the workflow runtime coordinates many subagents. Intermediate results stay in script variables instead of landing in the main conversation; the final report lands back in your session. This is excellent when you need a repeatable fan-out/fan-in pattern, but a workflow can spawn many agents and use meaningfully more tokens than working through a task conversationally. citeturn834220view0 citeturn834220view2

So no, I am **not** saying “don’t use them.” I am saying:

```text
Use workflows when scale/repeatability/cross-checking is the point.
Use agent teams when workers need to coordinate with each other.
Use subagents when you need isolated workers that report back.
Use forks when you need parallel work from the same exact context.
Use main session when the task is sequential and focused.
```

## “Isn’t it the same amount of tokens either way?”

Not necessarily.

The **work** might be the same, but the **context duplication** is not.

Imagine your project startup context is 40k tokens:

```text
CLAUDE.md
auto memory
tools
MCP tool names or definitions
repo status
spawn prompt
skill instructions
```

If you do one focused task in the main session:

```text
main session writes 40k once
future turns mostly read cached prefix
```

If you spawn 10 named subagents, each short-lived:

```text
subagent 1 writes its own startup/context
subagent 2 writes its own startup/context
subagent 3 writes its own startup/context
...
subagent 10 writes its own startup/context
```

Even if cache hit rate looks good overall, the absolute cache creation can be high because each worker has its own prefix. Claude Code explicitly says a subagent starts its own conversation with no cache hits on first call. citeturn356097view0

But the reverse can also be true. If doing it inline means the main session reads 80 files, 10 test runs, 3 failed approaches, 2 huge logs, and 20k lines of grep output, then every future turn drags that baggage around. In that case, a subagent that returns a 500-token summary may be cheaper overall even though it had a cold start.

So the correct comparison is not:

```text
same outcome = same tokens
```

It is:

```text
same outcome =
  base context duplicated across workers
+ exploration duplicated across workers
+ tool output retained or summarized
+ coordination messages
+ model/effort differences
+ rework avoided by parallel review
+ wall-clock time saved
```

That is why your intuition is partly right and partly incomplete. Agent teams/workflows often spend more tokens, but they may avoid days of human orchestration, prevent rework, and improve quality.

## Your 10 sub-outcomes × 10 sub-tasks example

You described:

```text
1 outcome
  -> 10 sub-outcomes
      -> 10 sub-tasks each
```

Here are the main execution shapes.

### Option A: 100 separate human-driven sessions

```text
100 cold starts
high HITL control
slowest wall-clock
lots of repeated context loading
good isolation
```

This is probably not what you want. It may be cheaper than a runaway workflow in some cases, but it destroys your time advantage.

### Option B: 10 persistent sessions, one per sub-outcome

```text
10 cold starts
good context reuse inside each sub-outcome
manageable human oversight
good PR/branch mapping
```

This is probably your best default.

I would map:

```text
one GitHub issue / sub-outcome = one persistent session + one persistent worktree/branch
```

Then use subagents/forks inside that session for investigation, test review, edge-case review, and documentation checks.

### Option C: one giant main session for all 100 sub-tasks

```text
1 cold start
best cache locality
terrible context hygiene over time
one model/effort unless you invalidate cache
harder review boundaries
more accumulated failed attempts
```

I would only use this if all 100 sub-tasks are tightly coupled and sequential.

### Option D: one agent team or dynamic workflow for the whole outcome

```text
many worker contexts
more token spend
much faster wall-clock
potentially better cross-checking
risk of duplicated exploration
risk of broad over-scanning
```

This is appropriate when the sub-outcomes are genuinely independent or when you need cross-checking. It is bad when the work is sequential and every worker needs the previous worker’s result.

### My preferred hybrid for you

Given how you work, I would use:

```text
Main planning session:
  define outcome -> sub-outcomes -> issues -> acceptance criteria

For each sub-outcome:
  one persistent worktree
  one persistent Claude session
  stable main model/effort
  subagents for narrow investigation/log/test/review tasks
  forks when the worker needs full current context
  workflow only for broad fan-out over many files
  agent team only when teammates need to coordinate
```

That gives you most of the wall-clock benefit without exploding into 100 cold-start sessions.

## Your current “main session stable, subagents form-fit model/effort” approach

That is actually reasonable.

You said:

> I try to keep main session all same, then subagents are form fit to the model/effort.

That is the right instinct. Switching the main session’s model or effort is expensive because model and effort are cache keys. Claude Code says switching models or changing effort level causes the next request to read the entire conversation with no cache hits. citeturn356097view0

So this pattern is good:

```text
main session: stable Sonnet/high
planning/review subagent: Opus or xhigh when needed
simple search/test subagent: Haiku/Sonnet
review fork: same model/context when useful
```

What I would refine is:

```text
Do not always use named subagents.
Use forks when the agent needs the same context.
Use named subagents when the agent needs isolation or a different model.
Use workflows only for large fan-out.
Use agent teams only when teammate-to-teammate communication matters.
```

## Long sessions: what to do before walking away

There are two separate problems:

```text
1. TTL expiry
2. stale context
```

Claude Code says cached prefixes expire after inactivity. Each cache hit resets the timer. On subscriptions, Claude Code requests a one-hour TTL automatically, but if usage credits are being billed it drops to five minutes. With API keys, Bedrock, Vertex, Foundry, or Claude Platform on AWS, the default TTL is the cheaper five-minute cache unless you enable one-hour caching. citeturn356097view0

So if you walk away longer than the TTL, the first turn back can be expensive because it recomputes the full input and re-establishes the cache. But this is where long sessions and new sessions differ:

```text
Resume long session after TTL:
  pays to reprocess full old conversation

Start new session:
  pays to process startup/project context only
  loses detailed continuity

Compact then resume:
  pays to replace history with summary
  future context is much smaller

Clear:
  starts empty context
  best when switching to unrelated work
```

Claude Code says `/compact` replaces message history with a summary and invalidates the conversation layer, but keeps/reuses system prompt and reloads project context. It also recommends compacting at natural breaks rather than letting auto-compaction hit mid-task. citeturn356097view0

So my practical advice:

### Do not compact just because you are stepping away for five minutes

If the cache is still warm and you are mid-task, compaction may create unnecessary churn.

### Compact before a long break when you are at a natural boundary

Good time to compact:

```text
plan approved
implementation phase done
tests passing but review remains
PR ready but documentation remains
one sub-outcome complete
```

Bad time to compact:

```text
middle of debugging
right after a complex failed test
while Claude is juggling many active details
before it has written down current state
```

### Before a long break, create a durable handoff artifact

This is especially useful at work where TTL may be five minutes. Ask Claude to write something like:

```text
TASK_STATE.md
PLAN.md
IMPLEMENTATION_NOTES.md
CURRENT_DIFF_REVIEW.md
```

Include:

```text
goal
files changed
commands run
test results
open problems
next command to run
decisions made
acceptance criteria
```

Then either compact or clear depending on whether the next session needs the prior discussion.

My recommended break ritual:

```text
1. Ask Claude: “Write a concise handoff file for resuming this work.”
2. Commit current safe changes, or at least save patch/diff.
3. If continuing same sub-outcome later: /compact with focused instructions.
4. If switching tasks: /rename, then /clear.
5. If abandoning a bad path: /rewind instead of compact.
```

The important nuance: if you wait until after the cache expired and then run `/compact`, that compaction request itself may have to reprocess the long history. If you know you are done for the day and the session is huge, compacting before walking away can make the next day cheaper.

## Worktrees: yes, this may be a big one for you

You are probably right to suspect this.

Claude Code says the cache is effectively scoped to one machine and directory. The system prompt embeds working directory, platform, shell, OS version, auto-memory paths, and git information. It explicitly says different worktrees of the same repository have different working directories and therefore miss each other’s cache. Sequential sessions only share the prefix when the git status snapshot at startup matches. citeturn356097view0

So if your pattern is:

```text
create worktree
do a small task
delete/clean worktree
create new worktree
do another small task
delete/clean worktree
```

then yes, you are likely creating lots of fresh cache writes.

But I would not say “one worktree for the whole day” as the universal rule. I’d say:

```text
one persistent worktree per active branch / PR / sub-outcome
```

That gives you isolation without destroying reuse every 20 minutes.

Better pattern:

```text
repo-main/
repo-worktrees/
  issue-123-auth-refactor/
  issue-124-api-validation/
  issue-125-test-cleanup/
```

Keep the worktree alive until the PR/sub-outcome is done. Commit frequently inside it. Reuse the same Claude session for that worktree. Only delete it when the PR is merged or abandoned.

For sequential, related work, yes, it may be better to commit/PR/merge multiple times from the same working directory rather than constantly creating and destroying worktrees. For unrelated work or true parallel branches, worktrees are still the right tool. Claude’s worktree docs frame worktrees as file-edit isolation for parallel sessions, not as a thing you must use for every small task. citeturn436295view0

A good rule:

```text
Use worktrees for parallel isolation.
Use branch switching or a persistent worktree for sequential related work.
Do not create a disposable worktree for every tiny subtask unless file isolation is actually needed.
```

Also: if subagents are writing code, worktree isolation can prevent collisions. Claude Code supports subagents running in their own worktrees. That is useful for safety, but it is not free; use it when agents may edit overlapping files, not for every read-only investigation. citeturn436295view0

## `/compact` at awkward times

`/compact` is not bad. It is a tool for turning a messy transcript into a smaller summary.

The cost problem is using it at the wrong boundary.

Good:

```text
finish discovery -> compact -> implement
finish implementation -> compact -> review
finish review -> compact -> PR cleanup
```

Bad:

```text
compact while debugging a subtle issue
compact every few turns
compact before important details have been externalized
compact after every subtask even though the next subtask needs the prior context
```

Claude Code says compaction invalidates the conversation layer because the next request has a new shorter history, but it works in your favor when the discarded context is no longer needed. citeturn356097view0

## Model or effort switching

This is one of the cleanest rules:

```text
Pick main model/effort at session start.
Do not switch the main session mid-task.
Route exceptions to subagents/forks/workflows.
```

The reason is not just price per token. It is cache shape. Claude Code says each model has its own cache, and each effort level has its own cache for the same model. Switching means the next request reads the whole conversation with no cache hits. citeturn356097view0

Your current pattern is good:

```text
main session stable
specialist agents choose their own model/effort
```

The refinement is: use a **fork** instead of a named subagent when the specialist needs the same context and can use the same model.

## Fast mode toggles

If you use `/fast`, enable it at the beginning of a session rather than deep into a long one. Claude Code says enabling fast mode adds a request header that is part of the cache key, so the next request reads the full conversation with no cache hits; enabling it from a non-Opus model can also switch the model. Newer versions keep the header across later toggles, but `/clear` and `/compact` reset this. citeturn356097view0

So:

```text
Good: start session in fast mode intentionally.
Bad: turn fast on halfway through a massive conversation.
```

## Large CLAUDE.md and repo instructions

You already get this one, but one important detail: every regular session and teammate loads project context. Claude’s docs say CLAUDE.md files are loaded into context at session start and recommend keeping them concise, with a target under 200 lines. They also say detailed workflow instructions should move to skills or path-scoped rules when they only matter sometimes. citeturn307823view5

The principle:

```text
CLAUDE.md = what every session always needs
skills = what some tasks need
path rules = what only some files need
handoff files = what this task needs
```

A bloated `CLAUDE.md` becomes expensive because it is multiplied by:

```text
main sessions
worktrees
teammates
subagents
workflow agents
new starts after TTL expiry
```

## Large MCP/tool context

Claude Code now defers MCP tool definitions by default on supported models, which helps. But if tools load into the prefix, MCP server changes can invalidate the cache. Claude Code says this can happen when tool search is unavailable or disabled, on Haiku models, on Vertex AI, custom gateways, tools marked `alwaysLoad`, or threshold-based upfront loading. It also notes that reconnects or dynamic tool updates can change the tool list and invalidate cache. citeturn356097view0

So the optimization is:

```text
Disable MCP servers you are not using.
Prefer CLI tools like gh/aws/gcloud/sentry-cli when they are enough.
Avoid unstable MCP servers that reconnect or dynamically change tools mid-session.
Check /context to see what is actually consuming space.
```

Claude’s cost docs specifically say CLI tools are often more context-efficient than MCP servers because they do not add per-tool listings, and they recommend `/mcp` and `/context` for visibility. citeturn932384view1

## Huge tool output, logs, test output, grep output

This is where RTK can help, but it is a different problem from cache invalidation.

Verbose output hurts because once it enters the conversation, it becomes part of future context. Even if cached, it still increases the size of the cached/read prefix and can force compaction sooner. Claude Code recommends hooks that preprocess output, for example filtering a 10,000-line log down to matching errors before Claude sees it. citeturn932384view1

If by RTK you mean `rtk-ai/rtk`, it works by rewriting Bash commands such as `git status` into compact RTK equivalents. Its docs say the hook applies to Bash tool calls, but Claude Code built-in `Read`, `Grep`, and `Glob` do not pass through that hook, so those are not auto-rewritten. citeturn269124view0

So RTK is good for:

```text
git status/log/diff
test output
build output
lint output
grep/find through shell
large command outputs
```

RTK does **not** directly solve:

```text
new worktree cold starts
model/effort switches
subagent first-call cache misses
large CLAUDE.md
MCP tool prefix churn
```

It can still reduce total cost by keeping conversation history smaller.

Caution: compression can backfire if Claude needs the missing detail and has to ask for more output. There is at least one closed RTK issue where a user reported higher total cost because compressed output caused more Claude output and extra investigation. I would not treat that as universal, but it is a reason to measure with and without RTK on your own workflow. citeturn269124view1

## Broad prompts like “analyze this repo”

Your use case sounds reasonable because you do it intentionally:

> usually in one session to produce a single file output that is then handed off to another session.

That is a good pattern **if the output file is concise and becomes the durable artifact**.

Bad pattern:

```text
analyze this repo
read everything
carry all findings in conversation forever
continue implementation in same bloated context
```

Good pattern:

```text
analyze this repo for X only
write GAP_ANALYSIS.md
include file paths, evidence, confidence, and recommended next issues
clear/compact
future sessions read only the relevant section
```

For repo-wide analysis, I’d explicitly constrain:

```text
Scope: only src/api and src/auth
Output: one markdown file
Do not read generated files
Do not inspect test snapshots unless needed
Return file paths and line references
Summarize uncertainty
Stop after identifying top 10 gaps
```

Claude Code’s cost docs call out vague prompts like “improve this codebase” as causing broad scanning, while specific prompts reduce file reads. citeturn932384view1

## A better decision table for your workflow

Use this as your default routing logic:

| Situation | Best tool | Why |
|---|---|---|
| Small sequential edit | Main session | Best cache locality, least coordination |
| Same context, parallel side path | Fork | Shares parent cache, keeps main cleaner |
| Read lots of files/logs/tests, return summary | Named subagent | Keeps noisy context out of main |
| Need different model/effort for specialist work | Named subagent | Avoids switching main model/effort |
| Multiple independent branches/features | Persistent worktrees + sessions | Isolation with reuse inside each workstream |
| Workers need to talk to each other | Agent team | Team coordination is the point |
| Dozens/hundreds of similar independent checks | Dynamic workflow | Scripted fan-out/fan-in, repeatable |
| Repo-wide audit/migration | Workflow on a small slice first | Controls runaway token use |
| Same-file sequential dependency chain | Main session or one subagent | Agent team overhead is likely wasted |
| Review after implementation | Fresh subagent or fork | Less bias; clean verification |

## The thing I would change in your process

I would keep your high-level flow:

```text
outcome -> plan -> GitHub issues -> linked sub-issues -> execution session -> validation
```

But I would change the execution shape to:

```text
1. One planning session for the overall outcome.
2. One durable plan/issue artifact.
3. One persistent worktree/session per sub-outcome, not per sub-task.
4. Inside that sub-outcome session:
   - main session for implementation
   - forks for parallel same-context work
   - named subagents for noisy or different-model work
   - workflow only for large fan-out
   - agent team only for independent teammates that need coordination
5. Compact at phase boundaries.
6. Clear only when switching to unrelated work.
7. Keep the worktree alive until PR/sub-outcome is done.
```

That gives you the speed advantage without turning every subtask into a fresh cache write.

## What I would measure next

For one representative work outcome, compare these three approaches:

```text
A. Your current agent team/workflow approach
B. One persistent sub-outcome session with named subagents only
C. One persistent sub-outcome session using forks where context is shared
```

Track:

```text
total cost
cache_creation_input_tokens
cache_read_input_tokens
output tokens
wall-clock time
number of tool calls
number of subagents/teammates
number of worktrees
accepted diff size
review defects found
rework required
```

Claude Code’s `/usage` now attributes recent usage to skills, subagents, plugins, and individual MCP servers, and `/workflows` shows token totals by phase/agent while a workflow runs. citeturn932384view2 citeturn834220view1

The goal is not to minimize cache writes to zero. The goal is:

```text
stable main session
fewer disposable worktrees
fewer one-shot cold agents
subagents only where isolation helps
forks where shared context helps
workflows only where fan-out helps
agent teams only where coordination helps
compact at phase boundaries
durable handoff files between sessions
```

For your specific comments, the biggest likely wins are:

```text
1. Stop treating worktree as “task”; treat it as “sub-outcome / PR / branch.”
2. Prefer persistent sessions per sub-outcome over new sessions per subtask.
3. Use forks more when a worker needs the same context.
4. Keep main model/effort stable, as you already do.
5. Use named subagents for noisy investigation, logs, tests, and specialist model/effort work.
6. Use workflows for broad fan-out, but run on a small slice first.
7. Compact before long breaks only at natural boundaries.
8. Keep RTK for command-output reduction, but measure whether it actually reduces total cost in your workload.
```

===== USER =====

I want to dig into the inline/workflow/agent teams a bit more. Wouldn't it be better to run the whole outcome across a workflow or an agent team. with checks and validations between sub issues. Where I let the AI orchestrate the DAG of that work? or would it be better to have the AI generate a document that I follow marking each thing off as the DAG (which have done as an experiment, it can be difficult to follow). or maybe a plugin that 1. takes the outcome plans the DAG 2. stores it in some way that can be tracked and communicates to the operator what to do next, where he operator provides updates on the completion. 3. provides all the prompts, workflows or agent team construction up front. ... what re your thoughts here. worth asking in final, doing all this... how much am I really saving vs my time. the full outcome and work it as a workflow or a agent team because they mostly just "go" I can do 2 or 3 at a time in a day (workflows work better for this). I don't use workflows for simple things, mostly carying an outcome to completion. agent teams I tend to use because I have three phases: development, scanning, testing such that when its done, quality is high...

===== CHATGPT =====

I’ll frame this as an architecture tradeoff: optimizing for wall-clock throughput, dollar cost, and operator attention can lead to different orchestration choices.

===== CHATGPT =====

Yes — for the kind of work you’re describing, I think the best answer is **not** “do it inline.” It is also not “always run the entire outcome as one giant agent team.” The best shape is probably:

```text
AI plans the outcome DAG
persistent tracker owns the DAG
workflow/team/session executes bounded stages
operator approves gates and handles ambiguous decisions
verification evidence is recorded back into the DAG
```

In other words: **a plugin or orchestration layer is probably the right abstraction.**

## My answer in one sentence

For your workflow, I would aim for **DAG-managed autonomy**: let AI generate and maintain the DAG, let workflows/agent teams execute the high-parallelism phases, but keep durable state and human checkpoints outside the chat session.

That gives you most of the “it just goes” benefit without turning every outcome into an expensive, opaque, runaway multi-agent blob.

## The core distinction

There are really four modes:

```text
1. Inline session
2. Static DAG document
3. One big workflow or agent team
4. Plugin-managed DAG with workflows/teams as execution engines
```

I think mode 4 is the interesting one.

### Inline session

Inline is good when the work is sequential and tightly coupled:

```text
change this service method
fix this test
implement this one endpoint
debug this specific failure
```

It has the best cache locality and the least orchestration overhead. But for a real outcome with planning, development, scanning, testing, fixing, retesting, review, and documentation, inline work becomes a babysitting loop. It is cheaper in tokens but expensive in your attention.

### Static DAG document

This is the “AI writes a plan, human follows the checklist” model.

It is cheap and reviewable, but you already found the problem: it is hard to follow. The moment reality diverges, the document starts rotting. You become the scheduler, status tracker, dependency resolver, prompt writer, verifier, and exception handler.

That is not a good use of you.

A static document is useful as an artifact, but not as the actual control plane.

### One big workflow or one big agent team

This is closer to what you want because the AI keeps going. Claude Code workflows are explicitly designed for codebase audits, large migrations, cross-checked research, and tasks needing more agents than one conversation can coordinate. The key design point is that a workflow moves the plan into a script: the script owns the loop, branching, and intermediate results, and only the final result lands back in the chat context. citeturn227854view0

That matters a lot. A workflow is not just “more agents.” It is **orchestration in code**.

Agent teams are different. They are multiple Claude Code sessions with a lead, peer communication, and a shared task list. They work best when teammates need to communicate, challenge each other, and coordinate independent work. Claude’s docs specifically call out research/review, separate feature modules, competing debugging hypotheses, and cross-layer frontend/backend/test work as strong cases. citeturn227854view2

But both have real costs. Agent teams use separate context windows, cost scales with active teammates, and Claude’s docs say teams are best when teammates can operate independently; for sequential tasks, same-file edits, or work with many dependencies, a single session or subagents are usually better. citeturn227854view2

### Plugin-managed DAG

This is the model I think fits your brain and your workflow best.

The plugin does not replace workflows or agent teams. It **decides when to use them**, tracks state, generates prompts, stores evidence, and tells the operator what to do next.

That means the plugin owns this:

```text
Outcome
  -> sub-outcomes
      -> tasks
          -> dependencies
          -> required evidence
          -> recommended executor
          -> current status
          -> next action
          -> validation result
```

Then execution can be delegated to:

```text
inline session
subagent
fork
workflow
agent team
/goal loop
manual operator step
GitHub issue
CI job
```

That is the piece you are missing: not “more autonomous Claude,” but **a durable control plane outside Claude’s transient conversation context**.

## Why “whole outcome as workflow/team” is tempting

Your instinct is right. For a full outcome, the workflow/team approach can be dramatically better because it reduces your role from:

```text
human project manager + prompt router + tester + reviewer + debugger
```

to:

```text
operator / reviewer / exception handler
```

That is a huge difference.

If you can run two or three outcomes in a day using workflows, where manual/HITL-driven execution would take a week, then the cache-write premium is almost certainly not the right thing to optimize first. Your scarce resource is not input tokens. It is your attention, cycle time, and ability to maintain quality across multiple workstreams.

So I would not over-index on “could this have been cheaper inline?” Maybe yes. But cheaper inline may mean you lose the actual strategic benefit: parallel throughput.

The better question is:

```text
Was the extra AI spend buying real autonomy, quality, and throughput?
```

For your usage, often yes.

## Where a full workflow is best

A workflow is best when the DAG is mostly knowable up front and the work can be decomposed into independent or repeatable stages.

Good examples:

```text
scan every service for deprecated SDK usage
migrate N files from pattern A to pattern B
run security/performance/test-coverage reviewers independently
compare implementations against acceptance criteria
generate and cross-check documentation gaps
produce a migration plan from multiple independent analyses
```

Workflows are especially good when you want the orchestration to be repeatable. Claude’s docs say the workflow script is written to a file under the session directory, can be read, diffed, edited, and relaunched. Intermediate results stay in script variables instead of bloating the main conversation. citeturn227854view1

That is very close to your desired “AI orchestrates the DAG” model.

But there is an important catch: **workflow runs do not support arbitrary mid-run user input**. Claude’s docs say only permission prompts can pause a workflow; for sign-off between stages, each stage should be run as its own workflow. citeturn227854view1

That matters for your “checks and validations between sub-issues” idea.

If the validation is deterministic, put it inside the workflow:

```text
run tests
run scanner
check lint
verify generated files
compare diff against acceptance criteria
```

If the validation requires human judgment, split the workflow:

```text
Workflow A: plan and implement sub-outcome
Human gate: review diff / approve direction
Workflow B: scan and repair
Human gate: review findings
Workflow C: test and harden
Human gate: approve PR
```

So I would not run one giant unbroken workflow for a high-stakes outcome. I would run **stage-bounded workflows**.

## Where an agent team is best

Agent teams are best when the agents need to talk to each other.

That is the key distinction.

Use an agent team when the work is like:

```text
frontend agent owns UI
backend agent owns API
test agent owns integration tests
security agent challenges both
lead coordinates conflicts
```

or:

```text
agent A investigates hypothesis 1
agent B investigates hypothesis 2
agent C investigates hypothesis 3
they challenge each other
lead synthesizes the surviving answer
```

Claude’s docs explicitly describe agent teams as a lead plus independent teammates in separate context windows, with teammates communicating directly and sharing a task list. They also recommend teams for work where parallel exploration adds real value, and warn that token usage and coordination overhead scale with the number of teammates. citeturn227854view2

Your “development, scanning, testing” pattern is close, but I would refine it.

If “development, scanning, testing” means three agents all working at once, there is a risk of waste:

```text
tester tests code that is still changing
scanner reports issues dev is about to remove
dev ignores findings because it is mid-edit
lead spends tokens reconciling churn
```

A cleaner structure is often:

```text
Phase 1: development agent/team
Phase 2: scanner agents
Phase 3: test agents
Phase 4: repair loop
Phase 5: final review
```

That can be a workflow or a plugin-managed sequence of workflows.

Agent team is best when “development” itself has independent slices:

```text
agent 1: API
agent 2: domain/service logic
agent 3: tests
agent 4: docs/config
lead: integration
```

Then after that, run scan/test as validation phases.

## Where `/goal` fits

There is also a third Claude Code primitive that matters here: `/goal`.

`/goal` sets a verifiable completion condition and Claude keeps working across turns until a small evaluator model decides the condition is met. Anthropic gives examples like migrating a module until call sites compile and tests pass, implementing a design doc until acceptance criteria hold, or working through a labeled issue backlog until the queue is empty. citeturn285402view0

That is useful for long sequential work where you do not necessarily need parallel agents.

Example:

```text
/goal The auth migration described in OUTCOME.md is complete:
- all old auth imports are removed
- npm test exits 0
- npm run lint exits 0
- git diff only touches src/auth, test/auth, and docs/auth.md
- stop after 20 turns if blocked
```

The evaluator only sees what Claude surfaced in the conversation, so the goal must require visible proof: test output, build result, file count, clean git status, or explicit acceptance criteria. citeturn285402view0

So I would think of `/goal` as:

```text
best for sequential autonomous loops
```

Workflow as:

```text
best for scripted fan-out/fan-in
```

Agent team as:

```text
best for peer coordination and adversarial collaboration
```

Plugin-managed DAG as:

```text
best for managing the whole outcome lifecycle
```

## The architecture I would build

I would build a plugin or Hermes-style “Outcome Runner” that creates a durable DAG and then emits the right execution primitive for each node.

Something like this:

```text
/outcome plan <GitHub issue | design doc | prompt>
    -> generates DAG
    -> writes .ai/outcomes/<outcome-id>/dag.yaml
    -> creates/links GitHub issues
    -> defines acceptance criteria
    -> defines validation gates

/outcome next
    -> shows ready nodes
    -> recommends executor:
       inline | subagent | fork | workflow | agent-team | goal | manual

/outcome run <node-id>
    -> generates exact prompt
    -> starts workflow/team/goal/session
    -> records session id, branch, worktree, model, effort

/outcome update <node-id>
    -> records status, evidence, blockers, PR links, test results

/outcome validate <node-id>
    -> runs deterministic checks
    -> launches scanner/test/reviewer agents if needed

/outcome report
    -> summarizes status, cost, risks, next action
```

Store the durable state somewhere boring:

```text
.ai/outcomes/<id>/dag.yaml
.ai/outcomes/<id>/events.jsonl
.ai/outcomes/<id>/evidence/
.ai/outcomes/<id>/prompts/
.ai/outcomes/<id>/runs/
```

And mirror the human-facing state into GitHub issues/comments.

The key is that the plugin should not be “a giant prompt.” It should be a state machine plus prompt generator.

## What the DAG node should contain

Each node should be explicit enough that an agent can run it and a human can audit it:

```yaml
id: AUTH-003
title: Replace legacy token parser
type: implementation
depends_on:
  - AUTH-001
  - AUTH-002
executor: workflow
model: sonnet
effort: high
worktree: auth-migration
scope:
  include:
    - src/auth/**
    - test/auth/**
  exclude:
    - src/payments/**
acceptance:
  - no imports from legacyTokenParser remain
  - npm test -- test/auth exits 0
  - npm run lint exits 0
validation:
  deterministic:
    - rg "legacyTokenParser" src test should return no matches
    - npm test -- test/auth
    - npm run lint
  ai_review:
    - security-reviewer
    - test-coverage-reviewer
evidence:
  required:
    - git diff summary
    - test output
    - scanner output
status: ready
```

This solves a bunch of problems at once:

```text
Claude does not need to remember the whole plan.
You do not need to manually track the DAG in your head.
The next operator action is obvious.
The right execution primitive can be chosen per node.
Validation evidence is not lost in chat.
GitHub issues stay aligned with actual execution.
```

## How I would map your three phases

You said agent teams tend to map to:

```text
development
scanning
testing
```

I would make that more stage-gated:

```text
Stage 0: outcome planning
Stage 1: implementation
Stage 2: static/diff scanning
Stage 3: test generation and execution
Stage 4: repair loop
Stage 5: final review and PR packaging
```

For each stage:

### Stage 0: planning

Use inline or `/goal`, not a big team yet.

Output:

```text
DAG
acceptance criteria
risk register
recommended execution shape
```

### Stage 1: implementation

Use agent team only if there are independent areas of ownership.

Good team:

```text
backend agent
frontend agent
test harness agent
integration lead
```

Bad team:

```text
three agents editing the same service file
```

Claude’s docs explicitly warn that two teammates editing the same file can lead to overwrites, so you want ownership boundaries. citeturn227854view3

### Stage 2: scanning

Use subagents or workflow.

This is a great workflow phase:

```text
security scanner
performance scanner
correctness scanner
dependency scanner
API compatibility scanner
```

Each scanner is independent. They should not all dump findings into the main context. The workflow should synthesize, dedupe, and rank.

### Stage 3: testing

Use workflow or subagents.

Good:

```text
unit test agent
integration test agent
edge-case test agent
flaky-test reviewer
```

### Stage 4: repair loop

Use `/goal` or a single focused session.

The repair loop is often sequential:

```text
fix one class of failure
rerun tests
inspect next failure
fix
rerun
```

This is where a big agent team can waste tokens unless failures are separable.

### Stage 5: final review

Use fresh reviewers.

This is where agent teams are excellent:

```text
security reviewer
maintainability reviewer
test coverage reviewer
release-risk reviewer
```

Claude’s docs use a similar example of splitting PR review across security, performance, and test coverage reviewers. citeturn227854view3

## The real tradeoff: not tokens, but control-plane ownership

Here is the practical difference:

```text
Inline session:
  human owns the DAG

Static document:
  document describes the DAG
  human still owns the DAG

Workflow:
  workflow script owns the DAG during the run
  weak human interleaving mid-run

Agent team:
  lead agent owns the DAG turn by turn
  teammates coordinate through shared task list

Plugin:
  durable system owns the DAG
  AI executes nodes
  human handles gates/exceptions
```

For your style, I strongly prefer the last one.

## Would this actually save money?

Maybe not in raw Claude dollars.

But I do not think that is the right question.

A workflow or agent team may cost more tokens than inline execution. Claude’s docs are explicit that workflows can use meaningfully more tokens than doing the same task conversationally, and agent teams can use significantly more tokens because each teammate has its own context window. citeturn227854view1 citeturn227854view3

But if the workflow lets you run two or three high-quality outcomes in a day, the economic win is probably not token savings. It is:

```text
less operator attention
shorter cycle time
more parallel throughput
better validation coverage
less rework
faster PR readiness
fewer missed edge cases
```

So I would measure it as:

```text
incremental AI cost per accepted PR
operator minutes per accepted PR
calendar time from issue start to PR ready
defects found before human review
defects found after human review
rework turns after validation
```

If a full outcome workflow costs, say, an extra $10–$50 but saves you even 30–60 minutes of high-focus orchestration, it is probably a good trade. If it saves days, it is obviously a good trade. If it produces noisy diffs that require hours of cleanup, it is not.

## The thing I would not do

I would not blindly run every full outcome as one giant agent team.

That can work, but it hides too much inside one autonomous episode:

```text
planning mistakes amplify
agents duplicate effort
scan/test may run against unstable code
file conflicts increase
validation evidence gets hard to audit
cost attribution gets blurry
human gate happens too late
```

I would also not go back to pure “AI writes a DAG doc and Jeffrey follows it.” That burns your attention on exactly the work the machine should be helping with.

## The thing I would do

I would build or prototype the plugin.

Start small. Not a full orchestration platform. Just enough to remove the pain:

```text
1. Parse an outcome into a DAG.
2. Store the DAG in repo state.
3. Show ready tasks.
4. Generate the exact prompt/workflow/team spec for the next node.
5. Record evidence and status.
6. Recommend the next action.
```

Then add automation:

```text
GitHub issue creation/linking
worktree naming
model/effort recommendations
workflow script generation
agent team templates
validation commands
cost/run telemetry
PR readiness report
```

Claude Code plugins can bundle skills, agents, hooks, MCP servers, LSP servers, and monitors, and plugin hooks can respond to lifecycle events such as session start, tool use, subagent start/stop, task created/completed, teammate idle, file changes, and instruction loading. That is enough surface area to build an operator cockpit around your workflow. citeturn268696view0

Skills are also a natural fit for the prompt-generation part because Claude loads skill bodies only when used, instead of carrying all that procedure in `CLAUDE.md` on every turn. citeturn268696view3

## My recommended operating model

For your real work, I would use this:

```text
Outcome intake:
  plugin creates DAG + acceptance criteria + issues

Implementation:
  workflow if many independent nodes
  agent team if cross-component coordination is needed
  /goal if one bounded sequential objective
  inline if small or highly coupled

Validation:
  scanner/test workflow
  independent reviewer agents
  deterministic commands required as evidence

Repair:
  focused /goal or inline session

Completion:
  plugin checks evidence
  produces PR summary
  updates GitHub issues
  marks DAG complete
```

That gives you autonomy without surrendering the control plane.

## Decision rule

Use this as the practical rule:

```text
If the work is sequential and local:
  inline or /goal

If the work is broad and decomposable:
  workflow

If agents need to debate/coordinate:
  agent team

If the outcome spans many stages, issues, validations, and PRs:
  plugin-managed DAG

If the only artifact is a markdown checklist:
  useful for planning, insufficient for execution
```

## Final take

Your instinct is basically right: for serious outcomes, letting AI orchestrate the work is often better than manually walking a DAG.

But I would not make Claude’s live conversation the source of truth. I would make a **durable DAG runner** the source of truth, and let Claude Code workflows, agent teams, subagents, forks, and `/goal` be interchangeable execution backends.

That is probably the sweet spot for you:

```text
more autonomy than checklist-driven HITL
more control than one giant unattended workflow
better cost attribution
better resumption
better GitHub alignment
better quality gates
less cognitive load
```

And yes — based on how you describe running two or three substantial workflows in a day, this is almost certainly worth more than the cache-write premium you are trying to shave down.