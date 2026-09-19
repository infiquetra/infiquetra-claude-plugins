# TypeSafe AI and Jev: prior-art and ecosystem brief

Research done September 18, 2026. TypeSafe AI's model Jev launched three days before this
research, on September 15, 2026, so nearly everything below is first-week reception, not
settled history. Every factual claim below is marked **(fetched)** when I read the source
page directly with a fetch tool, or **(snippet)** when it comes only from a search-result
summary I did not independently open and read in full.

## 1. Company and product facts

TypeSafe AI is a San Francisco AI lab that spent about two years building privately before
launching publicly on September 15, 2026 (fetched: typesafe.ai blog). It was founded by
**Diogo Almeida** (chief executive officer), who co-invented Reinforcement Learning from
Human Feedback (RLHF) and InstructGPT — the training techniques behind ChatGPT and GPT-4 —
while at OpenAI and, before that, Google Brain (fetched: typesafe.ai/team). His co-founders
are **Erik Gafni** (chief technology officer), a repeat founder previously at the
DNA-sequencing company Ravel and an early employee at Invitae and Freenome, and **Sasha
Sheng** (chief operating officer), a former Meta/FAIR (Facebook AI Research) research
engineer who worked on News Feed and published at the NeurIPS and ECCV research conferences
(fetched: typesafe.ai/team). Several independent outlets — Yahoo Finance, HPCWire, Finsmes,
and TheSaaSNews — report a $40 million seed round led by the venture firm DCVC, announced
the same day as the launch (snippet only: the two primary press pages, on Businesswire and
Dealroom, both refused automated fetching with an access-denied error, so I could not
confirm the number from TypeSafe's or the investor's own words; one single search summary,
inconsistent with all the others, cited $25.9 million instead, which I treat as an error in
that summary rather than a real second figure).

The product is **Jev**, which TypeSafe calls the first "System One model" — a name that
borrows from psychologist Daniel Kahneman's "System 1" fast, intuitive thinking in
*Thinking, Fast and Slow* (snippet only). Instead of generating text, Jev takes a block of
plain-text state describing a situation plus one or more typed questions, and returns typed
answers: a **Choice** among up to 255 labeled options with a full probability distribution
over them, a **Score** on an ordered 2-to-10-level rubric, or a **Noul** (a probability that
a yes/no statement is true). All three question types can be sent in a single call and are
evaluated in parallel (fetched: docs.typesafe.ai). The company's manifesto argues that most
software "still isn't meaningfully intelligent" because intelligence has been hard to build
*on*, not because models aren't capable enough, and states its mission as "machine-native
composable AI" that developers wire into software as a reliable primitive — summarized in
its own line, "we're building prod, not God" (fetched: typesafe.ai/manifesto).

The current release is **Jev 1.13.0**; the aliases `jev-latest` and `jev-preview` both point
to it at launch, so no version history is visible yet (fetched: docs.typesafe.ai/models).
Pricing is one flat rate rather than tiers: $0.042 per million input tokens ($42 per
billion), with output tokens free ("too cheap to meter"). Rate limits at launch are 250,000
tokens per second and 1,200 requests per minute, explicitly documented as dynamic and
subject to change without notice, with higher limits available only through a custom or
enterprise sales conversation (fetched: docs.typesafe.ai/models). The context window is
64,000 tokens per request, split roughly in half between the state and the longest single
question, and it accepts text only (fetched: same page). On privacy, TypeSafe's own policy
commits that it will not train or fine-tune any model on customer input and will not share
that input with third parties beyond its own service providers, and that the service is
hosted in the United States; no self-hosting or on-premises option is mentioned anywhere in
the company's materials (fetched: typesafe.ai/legal/privacy-policy).

## 2. Catalog of real uses

Most of what exists was not built by TypeSafe — it was built by outside developers and
catalogued on a directory the company sponsors, madewithjev.com. At fetch time that
directory listed **133 builds, 45 written or video guides, and 8 use-case categories**
(fetched: madewithjev.com, which self-reports these totals): agents and browsers (36 builds),
tools and apps (40), games and real-time (15), triage and routing (14), content and growth
(13), research and data (11), trading and markets (3), and robotics and devices (1). A
second, larger community-run index, `github.com/kraayenjon/awesome-jev` (fetched), adds
well over a hundred more entries: language SDKs (Software Development Kits) in Go, Rust,
Ruby, Elixir, Swift, Scala, PHP, and .NET, Model Context Protocol servers, coding-agent
routers, benchmarks, and press coverage.

I read both directories in full during this research, so the complete raw listing already
exists in this session's record. The tables below are a representative sample spanning
every category, not the full 250-plus combined entries, to keep this brief a reasonable
length — ask me to dump the complete list if you want every row.

One caveat that applies to every row below: cost and speed figures are self-reported by
each project's own author on the directory page, not independently measured by TypeSafe or
by me — the directory's own tagline says as much ("shows the cost and speed its author
reported"). Star counts were current when I fetched the page and will drift.

**Agents, browsers, and computer use**

| Name | Link | What it does | Pattern | Context | Source |
|---|---|---|---|---|---|
| Jev on the WebMCP benchmark | madewithjev.com/builds/webmcp-benchmark | Browser tool-selection: 49/49 tasks solved | Choice-based routing | benchmark | fetched: madewithjev.com |
| jev-ultrafast (Browser Use) | github.com/browser-use/jev-ultrafast | Browser Use's own agent running on Jev, ~2.9k GitHub stars | real-time action selection | open-source dev tool | fetched: madewithjev.com |
| typesafe-computer-use | madewithjev.com/builds/typesafe-computer-use | macOS computer-use harness, ~$0.0002/task | action selection | hobby/dev tool | fetched: madewithjev.com |
| Jev as an agent safety monitor | madewithjev.com/builds/agent-safety-monitor | Verifies an agent's action before it executes | verification gate | dev tool | fetched: madewithjev.com |
| pi-heed | github.com/user/pi-heed (via awesome-jev) | Validates a tool call against stated intent, for the Pi coding agent | verification gate | dev tool | fetched: awesome-jev |
| A Slack agent, twice as fast | madewithjev.com/builds/slack-agent-skill-routing | Routes Slack agent requests to the right skill, 2x speed-up | skill routing | product feature | fetched: madewithjev.com |

**Games and real-time**

| Name | Link | What it does | Pattern | Context | Source |
|---|---|---|---|---|---|
| Jev plays Doom | madewithjev.com/builds/jev-plays-doom | Flagship real-time arcade demo, ~10 queries/sec | real-time decision loop | official demo (built by TypeSafe's own founder) | fetched: madewithjev.com |
| Wikiracing | madewithjev.com/builds/wikiracing | Picks the next Wikipedia link from up to 255 options | stress-tests the Choice primitive's option ceiling | official demo | fetched: madewithjev.com |
| Jev plays Slay the Spire 2 | madewithjev.com/builds/slay-the-spire-2 | Card-game moves at 0.7s each | real-time decision loop | hobby | fetched: madewithjev.com |

**Triage, routing, and fraud/content moderation**

| Name | Link | What it does | Pattern | Context | Source |
|---|---|---|---|---|---|
| 500 emails for 3.5 cents | madewithjev.com/builds/500-emails-3-cents | Classifies 500 emails by volume for $0.035 | classification | demo | fetched: madewithjev.com |
| Fraud detection with Jev and Kimi K3 | madewithjev.com/builds/fraud-detection-jev-kimi | Hybrid pipeline: Jev plus the Kimi K3 model, 96/100 correct in 1.42s | cascade (fast model + reasoning model) | dev tool/demo | fetched: madewithjev.com |
| DiffJury | madewithjev.com/builds/diffjury | Makes merge/no-merge safety calls on a code diff | verification gate | continuous-integration dev tool | fetched: madewithjev.com |
| jev-review-action | madewithjev.com/builds/jev-review-action | GitHub Action that posts automated pull-request review comments | verification/review | continuous-integration dev tool | fetched: madewithjev.com |
| routeKit | madewithjev.com/builds/routekit | Routes a task to a bigger or smaller model by estimated complexity | model routing | dev tool | fetched: madewithjev.com |

**Trading, content/growth, research, robotics (one each)**

| Name | Link | What it does | Pattern | Context | Source |
|---|---|---|---|---|---|
| $10,000 in Jev's hands | madewithjev.com/builds/10k-trading | Autonomous trading experiment with a real $10,000 bankroll | autonomous decision loop | experiment | fetched: madewithjev.com |
| Every's editorial vibe check | madewithjev.com/builds/every-editorial-judgments | 1,709 editorial judgments on written content, under $0.01 total | composite scoring | product/demo (independently tested — see section 5) | fetched: madewithjev.com |
| 1kpapers | madewithjev.com/builds/1kpapers (product: 1kpapers.com) | Classifies and browses 1,018 research papers for $0.08 total | classification | product | fetched: madewithjev.com |
| jev-drone | madewithjev.com/builds/jev-drone | Simulated quadrotor control loop at 2.5 Hz | real-time decision loop | hobby/research | fetched: madewithjev.com |

**Tools, apps, and developer infrastructure**

| Name | Link | What it does | Pattern | Context | Source |
|---|---|---|---|---|---|
| fast-jev-compaction | github.com/tamaratran/fast-jev-compaction | Claude Code plugin that scores and prunes stale session context | compaction/relevance scoring | dev tool | fetched: madewithjev.com |
| jev-mcp | github.com/jkudish/jev-mcp | Model Context Protocol server for screening/ranking, 70 GitHub stars | verification/ranking | dev tool | fetched: madewithjev.com |
| typesafe-mcp | github.com/itsmostafa/typesafe-mcp | Go-based command-line tool and Model Context Protocol connector, 62 stars | general-purpose connector | dev tool | fetched: madewithjev.com |
| TypeSafe AI playground | madewithjev.com/builds/typesafe-ai-playground | 110 interactive worked examples, 110 GitHub stars | reference/education | reference | fetched: madewithjev.com |
| jev() for PostgreSQL | madewithjev.com/builds/postgres-jev-function | Natural-language database search function, 129 rows in ~1s | extraction | dev tool | fetched: madewithjev.com |
| is-malicious | madewithjev.com/builds/is-malicious | Scans a codebase for malicious code | classification/security | dev tool | fetched: madewithjev.com |

**Beyond madewithjev.com**

| Name | Link | What it does | Context | Source |
|---|---|---|---|---|
| langchain-typesafe | pypi.org/project/langchain-typesafe | LangChain integration package for Jev | dev tool (library) | fetched: madewithjev.com |
| Jevbridge | github.com/gamesonrblx/Jevbridge | Adapts Jev into both the Agent Communication Protocol and Model Context Protocol | dev tool | fetched: awesome-jev |
| decider | github.com/Mapika/decider | A fine-tune of the small open Qwen3.5-2B model, built as a self-hostable alternative to Jev | open-source alternative | fetched: awesome-jev |
| ASSAY-001 | github.com/jourdanlabs/assay-001 | An independent project specifically built to calibration-check Jev's outputs | third-party verification | fetched: awesome-jev |
| Hacker News launch thread | news.ycombinator.com/item?id=49717558 | Launch discussion, 1,892 points and 496 comments when I read it | community discussion | fetched directly |

## 3. Recurring patterns and clever ideas

TypeSafe's documentation names four patterns for combining typed questions (fetched:
docs.typesafe.ai/patterns): **Speculative Fan-Out** (send many questions in one call,
including ones the code might not end up needing, because evaluating them in parallel makes
the extra ones nearly free), **Confidence-Gated Routing** (use the confidence score, not
just the answer, as a second axis for deciding what to do — act automatically above a
threshold, escalate to a human or a bigger model below it), **Composite Scoring** (combine
several separate typed judgments into one downstream score, instead of asking one model to
weigh everything at once), and **Intent Routing** (classify what a request wants, then hand
it to a specific handler).

Looking across the full catalog, five broader shapes recur beyond those four:

- **Routing at every layer.** Not just user-intent routing, but *model* routing (deciding
  which Large Language Model to call next for a given step) and *skill* routing (deciding
  which tool or agent capability to invoke). At least six catalogued projects are dedicated
  routers, and coding-agent-specific routers are common enough to list separately in
  section 4.
- **A fast model deciding, a slow model reasoning.** Builders pair Jev with a reasoning
  Large Language Model far more often than they replace one with the other. "The Large
  Language Model plans, Jev decides" shows up almost verbatim in project descriptions — one
  browser agent literally describes itself as "LLM planning + Jev decisions," another as
  "Claude plans, Jev reacts." Even TypeSafe's own Home Assistant demo, according to a
  Hacker News commenter, falls back to an Anthropic model for anything that needs real
  reasoning (fetched: Hacker News thread) — the pattern is delegation of the fast, narrow
  steps, not wholesale replacement of the reasoning model.
- **Turning a fuzzy judgment into a numeric feature.** Several "content and growth"
  projects fire dozens of parallel typed questions at a single piece of content and combine
  the resulting scores downstream as engineered features — one project asked 3,282 social
  posts eight questions each to find growth patterns; another asked 61 questions per post to
  predict virality.
- **Verification and safety gating on top of another agent's actions.** A whole cluster of
  projects exist purely to check something else's output before it takes effect: validating
  a tool call against stated intent, blocking a risky agent action, detecting a secret
  accidentally included in a code diff, or catching an agent stuck repeating the same failed
  step.
- **Compaction: scoring conversation relevance to prune agent context.** Several projects
  use Jev's speed to score which parts of a long agent transcript are still relevant and
  discard the rest; one reported report claims a reduction from roughly one million tokens
  to about 86,000 in about a second (snippet only — a single reported social-media post, not
  independently reproduced by me).

## 4. Uses in agent, coding-agent, or developer-tool contexts specifically

This is where the catalog concentrates: 36 of the 133 madewithjev.com builds sit in the
"agents and browsers" category alone, and the developer-tool projects inside "tools and
apps" and "triage and routing" add several dozen more.

TypeSafe ships its own **Agent Skill** — installable directly into Claude Code through the
plugin marketplace, or into Codex and other agents through the `npx skills add` command from
skills.sh, or by manual copy into an agent's skills folder — which teaches a coding agent
when a typed judgment call would replace fragile string-matching code, and points it at
worked examples to copy from (fetched: docs.typesafe.ai/agent-skill).

On top of that one official integration, a large unofficial ecosystem has grown around
specific coding agents:

- **Claude Code**: a community per-turn model router (`jev-router`) and a context-compaction
  plugin (`fast-jev-compaction`, published by developer Tamara Tran) that scores which parts
  of a session are still worth keeping.
- **Codex**: a separate per-turn router (`jev-codex-router`), a context-trimming plugin
  (`codex-context-diet`), and an open issue in a third-party project called "codex-skills,"
  where the maintainer is actively evaluating Jev as what they call "a calibrated judgment
  tier" for that project's own workflow gates (snippet only — I found the issue's title and
  repository, not the full discussion inside it).
- **Pi**, a coding-agent framework distinct from both Claude Code and Codex: the single
  largest named sub-cluster in the whole ecosystem. At least nine separate community
  projects — including one named `pi-heed`, one named `pi-jev-compaction`, one named
  `pi-warden`, and one named `Bicameral` — add Jev-based guardrails, permission gating,
  context compaction, or tool-call validation to Pi.
- **Model Context Protocol servers.** At least four independent servers wrap Jev for general
  agent use: `jev-mcp` exists in both a Node.js version (by Joey Kudish) and a separate
  Python version (by a developer using the handle blakestone-x), `typesafe-mcp` is written
  in Go, and `Jevbridge` adapts Jev into both the Model Context Protocol and the separate
  Agent Communication Protocol.
- **Continuous-integration and pull-request triage.** A GitHub Action called
  `jev-review-action` posts automated pull-request review comments; a project called
  `DiffJury` makes merge/no-merge safety calls on a diff; a separate project, also commonly
  called "Jev Review" but built by a different author, runs a staged code-review workflow;
  `Clean Code Judge` scores pull requests on code smells; and `commit-miner` classifies
  commits for reporting.
- **Log and on-call triage.** A project called `Jev Logs` triages OpenTelemetry logs, and a
  separate project called `typeful-triage` is a multiplayer issue-triage dashboard.
- **LangChain and LangGraph.** LangChain published its own guide, "Building a harness with
  Jev," covering model routing and blocking risky actions (fetched: langchain.com blog); a
  `langchain-typesafe` package is published to the Python Package Index; and one project
  (`typesafe-jev-workflow`) specifically uses LangGraph to route email by intent.
- **Agent hosting and gateway infrastructure.** Jev is listed as a model on the Vercel AI
  Gateway and the Vercel AI Software Development Kit, with a dedicated Vercel agent
  framework (`eve`) built around it; it is also reachable through Cloudflare Workers AI,
  Netlify's AI Gateway, OpenRouter (in beta), and as a pass-through model in LiteLLM
  (fetched: madewithjev.com, which links each announcement).

I found no evidence that Jev is built into Claude Code, Codex, or any agent platform by the
platform vendor itself (Anthropic, OpenAI, and so on). Every coding-agent integration above
is a third-party plugin or router that hooks into an existing agent's extension points, not
a first-party feature shipped by the agent vendor.

## 5. Critiques, limitations, gotchas

TypeSafe's own launch post discloses real caveats up front, before any outside critic does:
its headline "193.6 times faster, 444.6 times cheaper" figure is itself described as "the
higher end" of results, produced by TypeSafe's own capabilities team, who write that "some
bias could exist"; the comparison also wrapped competing Large Language Models in a
constrained adapter that the company admits "may be slower and more expensive" than those
models running unconstrained (fetched: typesafe.ai blog). Independent commentary goes
further: one analysis piece points out that the reported 67.8% accuracy figure is measured
by *agreement with two other Large Language Models* — GPT-6 Astra and Claude Fable 5.1 — not
against independently verified ground truth, and that no named production customers,
revenue, or company valuation have been disclosed (fetched: forkast.news and ts2.tech).

TypeSafe's own documentation is candid about the model's rough edges, publishing an explicit
list of eleven known failure modes for the current version, Jev 1.13 (fetched:
docs.typesafe.ai's model-jaggedness page): it reads instructions literally rather than by
intent; it cannot count reliably; it struggles with raw numeric encodings like hexadecimal
colors or RGB triples; it cannot reconstruct an exact number by interpolating between score
levels; it treats dates as text rather than as ordered quantities, so date comparisons are
unreliable; its accuracy drops as irrelevant detail is added to the state it's given; it can
be steered by adversarial or injected content; contradictory instructions confuse it; there
is no guarantee that logically complementary questions (two opposite yes/no questions, say)
will add up correctly; and, by design, it was never trained to generate free text and
performs poorly if forced to try.

An independent hands-on test by the media company Every, covering 37 documents and 777
separate judgments, found Jev fast and cheap as advertised, but it missed one of seven
intentionally planted defects in a writing sample that Anthropic's Claude Fable 5.1 caught;
the author's conclusion was to treat it as "an early warning system," not a final judge,
until validated on your own data (fetched: every.to). The Hacker News launch discussion
(1,892 points, 496 comments when I read it) raised two sharper objections: that calling a
model "unable to hallucinate" is reassuring-sounding but misleading, because a wrong answer
delivered in a valid, well-typed format is still a wrong answer; and that the flagship
Doom-playing demo fed Jev pre-structured game state rather than raw pixels, which critics
say makes the speed comparison to a Large Language Model less impressive than the headline
suggests (fetched: Hacker News thread). Operationally, the published rate limits are
explicitly called dynamic and subject to change without notice — a real gotcha for anyone
building production systems on the early-access application programming interface (API)
today. There is no official self-hosting option; the existence of several community
"open replica" projects trying to reproduce Jev's behavior locally (`openjev`, `jevlike`,
`PocketJev`, `decider`) is itself indirect evidence that some users want one and don't have
it.

On the positive side, TypeSafe's own privacy policy is unusually direct: it commits not to
train on customer input and not to share that input with third parties beyond its service
providers (fetched: typesafe.ai/legal/privacy-policy).

## 6. Alternatives people compare it with

Search results and community write-ups most often compare Jev to two Large-Language-Model
structured-output libraries: **Instructor**, a Python library that wraps a call to any
Large Language Model and validates the response against a schema, retrying on failure, and
**BAML**, a small language for defining typed function interfaces across many programming
languages, which recovers structured data from malformed model output using what its
authors call "Schema-Aligned Parsing" (snippet only — I found no page where TypeSafe itself
names either competitor directly). The distinction both comparisons draw is the same:
Instructor and BAML are wrappers around a general-purpose Large Language Model, paying that
model's full latency and cost on every call and repairing its output after the fact; Jev is
a separately trained, hosted model that natively emits only a closed-form answer, at a
fraction of the latency and cost, but never free text. I found no direct comparison between
TypeSafe and **Outlines**, a similar constrained-decoding library, in this search — see
section 7.

Beyond libraries, the catalog itself is full of head-to-head comparisons against **small
fine-tuned classifiers and cross-encoder rerankers**, which are the categories Jev is most
directly trying to displace. One catalogued benchmark runs Jev against a small Qwen model;
a separate open-source project, `decider`, is an explicit fine-tune of the small open
Qwen3.5-2B model, built as a self-hostable alternative to Jev; another catalogued build
reports a seven-times reranking speedup over its previous search-ranking setup. TypeSafe's
own manifesto frames the pitch this way: keep Large Language Models for open-ended reasoning
and conversation, and replace the fine-tuned classifier or reranker a team would otherwise
have trained and hosted itself with a call to Jev instead (fetched: typesafe.ai/manifesto
and typesafe.ai blog; the specific word "zero-shot" for this comparison came from a Hacker
News commenter's paraphrase, not from a TypeSafe document, so treat that word as a
commenter's gloss rather than the company's own term).

## 7. What is unknown

A few things this search could not pin down. First, the $40 million funding figure and
DCVC's role as lead investor rest entirely on converging secondhand press coverage; both
primary press-release pages, on Businesswire and on Dealroom, refused automated fetching, so
I could not confirm the number from TypeSafe's or the investor's own words. Second,
independent, ground-truth accuracy numbers do not appear to exist publicly yet — every
accuracy figure I found is either self-reported by TypeSafe or measured by agreement with
other Large Language Models rather than against a verified correct answer. Third, no named
enterprise customers, revenue, or usage volume have been disclosed anywhere I found. Fourth,
I could not confirm the claim that the name "Jev" references the economic idea called
Jevons Paradox — it appeared in one search result's summary only, never on a company page I
read directly. Fifth, exact weekly download counts for the Python Package Index and npm
packages were not retrievable from the pages I reached, and I found two slightly different
reported names for the JavaScript package — `typesafe-sdk-js` as the GitHub repository name
versus `@typesafe-ai/sdk` as a possible published package name — that I could not reconcile
by reading the npm registry page directly. Sixth, no comparison between TypeSafe and the
Outlines library turned up anywhere in this search, despite Outlines being a commonly cited
alternative for constrained model output elsewhere in the industry. Finally, because Jev
launched only three days before this research, there is no track record yet on
longer-run questions such as price stability, how the rate limits behave in practice once
raised, or whether the early-access waitlist converts to open availability on any announced
timeline.
