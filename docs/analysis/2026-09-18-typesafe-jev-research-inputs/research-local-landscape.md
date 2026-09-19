# Local landscape survey: decision points in `infiquetra-claude-plugins` and the operator's coding-agent harnesses

This is a read-only survey of the repository `infiquetra-claude-plugins`
(`/Users/jefcox/workspace/infiquetra/infiquetra-claude-plugins`) and the operator's local
coding-agent harnesses, done to find where TypeSafe AI's fast typed-judgment model ("Jev") could
plug in, and how a shared skill does or doesn't reach each harness. Jev answers three kinds of
question in about 0.4 seconds with no free-text generation: **noul** (yes/no, as a probability of
yes), **choice** (pick one option from a defined set, with a full probability distribution and a
confidence number), and **score** (a position on ordered levels, as a weighted score with
per-level probabilities and a confidence number). Part A is the decision-point table inside this
repository's plugins, Part B is the harness inventory, Part C is the reusable plumbing a client
would sit on, and Part D is where the highest-leverage plug-in points are and why.

Two short forms recur: **large language model (LLM)**, the reasoning model doing free-text
judgment today, and **regular expression (regex)**, the pattern-matching several decision points
use instead. This repository's issue severity scale runs from **P0** (the most severe finding,
blocking) through **P1** and **P2** to **P3** (least severe, optional).

## Part A — decision points inside the plugins

Four points illustrate the pattern best, because the codebase's own comments already say the
current mechanism isn't good enough.

**The five content flags in `parse_issue.py` gate a mandatory check, not an advisory one.**
`plugins/saga/scripts/parse_issue.py:16-23` define five regexes (`SECURITY_RE`, `API_RE`,
`INFRA_RE`, `PRIVACY_RE`, `REFACTOR_RE`), each a short literal word list. Around line 110 they
become boolean flags (`has_security`, `has_api`, `has_infra`, `has_privacy`, `has_refactor`) on a
parsed issue body. `plugins/saga/skills/loop/SKILL.md:123-124` says these flags "feed the hard
test-gate check" — the one non-advisory gate in the router — plus the backend recommendation. A
word list is a blunt instrument for a mandatory gate: an issue calling itself a "sign-in flow"
never trips `has_security`. A **noul** call reading the same text ("does this describe
security-sensitive or infrastructure-sensitive work?") would catch paraphrases a fixed list can't
— though since this flag gates a mandatory check, any replacement should only ever widen what
triggers it, never narrow it.

**Ten judgment calls happen on every code review, and the registry defining them already says a
keyword match isn't enough.** `plugins/saga/references/lens-roster.json` lists four always-on
review lenses and ten conditional ones (deployment-infrastructure, reliability, performance,
api-contract, adversarial, privacy, documentation-clarity, agent-usability, previous-comments,
accessibility-human-usability), each marked `"judgment_required": true,
"keyword_match_sufficient": false`. The consumer,
`plugins/team-execution/skills/team-execution/references/reviewer-registry.md`, states the rule
directly in its Selection Procedure: "Keyword matching may inform that judgment but never selects
a lens by itself." Today a reasoning model reads the whole diff against all ten lens descriptions
on every review — an expensive pass, repeated every run. Ten parallel **noul** calls, or one
**choice**, keyed to each lens's own guidance text as state, could pre-screen the clear cases and
leave the model's judgment for genuinely close ones.

**The refute-N verifier panel spends a full model call to answer one yes/no question per
finding.** `plugins/saga/agents/readonly-verifier.md` defines the read-only adversarial agent
saga's verify panels spawn; `plugins/saga/scripts/execution_spec.py:95-96` states the rule: "a
finding survives unless refuted... majority => >= ceil(N/2) verifiers refute; unanimous => all N
refute." Each verifier is a full agent invocation at the unit's own tier — potentially
Opus-class — spent to answer, per finding, whether one specific claim holds up. A **noul** call
can't replace a verifier that runs tests and reads code, but it's a plausible extra vote at
near-zero marginal cost, or a pre-screen deciding whether the full panel is worth convening at
all.

**The per-unit tier and "work shape" classification runs once for every planned unit of work
across the fleet.** `plugins/saga/skills/plan/SKILL.md:476-490` maps work-shape descriptions
("Judgment, design, adversarial review," "Mechanical, deterministic, scripted transforms,"
"Read-only survey, search, grep, sampling," and others) to a default model/effort tier, then
instructs: "Apply the heuristic per unit." `plugins/fleet-core/scripts/fleet_commons/tier_resolver.py`'s
own docstring calls this "the prose-only heuristic table" and says the resolver itself "never
hardcodes a heuristic in code" — the classification is pure LLM prose judgment; only the lookup
from a classified shape to a `{model, effort}` pair is code. A **choice** call, with the work-shape
labels as options and the unit's task text as state, would make that mapping consistent across
separate planning sessions in a way prose applied by a large reasoning model isn't guaranteed to
be. (Small aside: that same docstring cites the heuristic table at "plan/SKILL.md:298-304," a
range that has since drifted to 476-490 as the file grew — a live example of citation staleness in
this codebase.)

The table below covers thirty-six points, including the ten lenses above as individual rows since
each triggers independently on its own guidance text. Mechanism values: **regex** (a fixed
pattern/word list), **LLM prose** (a reasoning model applying written guidance, no code backing
it), **hand rule** (a coded threshold/rule engine over already-typed inputs), **human** (the
operator decides unassisted).

| # | Plugin | File : line | Decision | Mechanism | Input state | Primitive | Benefit | Risk |
|---|---|---|---|---|---|---|---|---|
| 1 | saga | `parse_issue.py:16-19` | Flag issue security-sensitive | regex | issue body | noul | catches paraphrases | widen-only |
| 2 | saga | `parse_issue.py:20` | Flag issue API-shaped | regex | issue body | noul | same | widen-only |
| 3 | saga | `parse_issue.py:21` | Flag issue infra-shaped | regex | issue body | noul | feeds gate + backend pick | widen-only |
| 4 | saga | `parse_issue.py:22-23` | Flag issue privacy/refactor-shaped | regex | issue body | noul x2 | cheap, parallel | lower stakes, advisory only |
| 5 | saga | `loop/SKILL.md:142-149` | Classify turn as Route/Drive/Resume | LLM prose | operator input | choice | skips a manual read | needs fallback question |
| 6 | saga/team-exec | `lens-roster.json` | Select `deployment-infrastructure` lens | LLM prose (keyword banned) | diff + guidance | noul | pre-screens expensive read | false negative skips a lens |
| 7 | saga/team-exec | `lens-roster.json` | Select `reliability` lens | LLM prose | diff + guidance | noul | same | same |
| 8 | saga/team-exec | `lens-roster.json` | Select `performance` lens | LLM prose | diff + guidance | noul | same | same |
| 9 | saga/team-exec | `lens-roster.json` | Select `api-contract` lens | LLM prose | diff + guidance | noul | same | same |
| 10 | saga/team-exec | `lens-roster.json` | Select `adversarial` lens | LLM prose | diff + guidance | noul | same | same |
| 11 | saga/team-exec | `lens-roster.json` | Select `privacy` lens | LLM prose | diff + guidance | noul | same | same |
| 12 | saga/team-exec | `lens-roster.json` | Select `documentation-clarity` lens | LLM prose | diff + guidance | noul | same | same |
| 13 | saga/team-exec | `lens-roster.json` | Select `agent-usability` lens | LLM prose | diff + guidance | noul | same | same |
| 14 | saga/team-exec | `lens-roster.json` | Select `previous-comments` lens | LLM prose | diff + prior comments | noul | same | same |
| 15 | saga/team-exec | `lens-roster.json` | Select `accessibility-human-usability` lens | LLM prose | diff + guidance | noul | same | same |
| 16 | team-execution | `reviewer-registry.md` | Classify plan as code/docs/mixed | LLM prose | plan text | choice | cheap routing call | mixed plans are boundary cases |
| 17 | saga | `code-review/SKILL.md:316-318,373,378-379` | Suppress finding below confidence 75 (P0 at 50+ survives) | hand rule on the reviewer's own self-reported number | finding's self-assessed severity/confidence | score (cross-check) | independent check on over/under-confidence | adds a second opinion to reconcile |
| 18 | saga | `execution_spec.py:95-96,631-633` | Decide if a finding is refuted (N-verifier vote) | N full LLM agent calls, majority/unanimous | unit diff + the finding | noul | one more vote, near-zero cost | not a substitute for a real verifier |
| 19 | orchestrate | `orchestrate.py:1047-1056` | Detect a Code Review controller invocation | regex, anchored | unit task text | noul | already precise for known spelling | low priority, works well already |
| 20 | orchestrate | `orchestrate.py:189,1187-1209` | Detect a "bespoke" review request | regex on the single word "review" | unit task text | noul | docstring admits wording "cannot carry this decision" | miss routes review down wrong path |
| 21 | mission-control | `sdlc_manager.py:1730-1751` | Apply auto-labels from issue text | regex (`auto_label_rules`, docs call it legacy) | issue title + body | choice/noul | already marked legacy — natural first swap | repos may depend on current exact behavior |
| 22 | mission-control | `issues/SKILL.md:306-317` | Choose 1 of 6 issue types | LLM prose decision tree, or ask human | issue text | choice | pre-fills a suggestion + confidence | wrong high-confidence guess worse than asking |
| 23 | mission-control | `commands/triage.md` step 3 | Assess defect priority | human (asked directly) | issue text | score | ordered levels fit `score` well | priority often needs business context |
| 24 | mission-control | `commands/triage.md` step 3 | Suggest Initiative/Objective field value | LLM prose matching free text to option list | issue text + live option list | choice | clean closed-set choice | option list must be fetched live, not cached |
| 25 | mission-control | `commands/triage.md` step 8 | Recommend board status (Ready/Backlog/Shaping) | LLM prose | issue completeness | choice | cheap triage-time suggestion | same context judgment as issue type |
| 26 | saga | `plan/SKILL.md:476-490`; `tier_resolver.py` | Classify unit "work shape" before tier lookup | LLM prose ("apply the heuristic per unit") | unit task text | choice | consistent answer across sessions | novel work shape needs a real fallback |
| 27 | saga | `lifecycle_state.py:135-220` | Recommend execution backend | hand rule (thresholds over counts + flags 1-3) | file/phase counts + security/infra flags | — (contrast) | already deterministic, tested | inherits upstream regex blind spots |
| 28 | saga | `ideate/SKILL.md:161-163` | Detect "tactical scope" ask, lower ambition floor | regex/keyword list | operator focus-hint text | noul | catches unlisted phrasings | under-trigger just keeps safer default |
| 29 | saga | `ideate/SKILL.md:562-566` | Decide if a generated idea survives critique | LLM prose, full critique per idea | one idea + grounding summary | score (pre-screen) | cheap pre-rank before expensive critique | ideate's design demands reasons, not silent drops |
| 30 | saga | `office-hours/SKILL.md` | Choose Startup mode vs. Builder mode | LLM prose rubric | operator topic text | choice | clean binary front-door choice | must stay overridable |
| 31 | saga | `handoff/SKILL.md:98` | Decide if text says execution should wait | LLM prose over deterministic path rules | source artifact text | noul | isolated, well-scoped judgment | low frequency, low leverage alone |
| 32 | saga | `promote_scan.py:1-10`; `promote/SKILL.md` | Cluster near-duplicate learnings pre-promotion | LLM prose over an exact-match floor | two candidate learnings | noul (pairwise) | assists clustering between floor and full judgment | clustering itself isn't a single-call primitive |
| 33 | saga | `journal_nudge_hook.py:29` | Decide if a commit deserves a journal nudge | regex (`feat`/`fix` prefix) | commit message | noul | real policy is "non-obvious fix," prefix only approximates | over-nudging gets ignored |
| 34 | saga | `team_spawn_residency_hook.py:46-47` | Decide if a spawned agent is review/verify-class | regex on naming convention | agent-name token | noul | catches a reviewer role without the literal suffix | naming checks are usually reliable already |
| 35 | fleet-core | `delegation_audit.py:227-240` | Decide if a shell command is a genuine engine invocation | regex (6 OR'd substrings) | shell command string | noul | feeds a real-vs-faked governance verdict | missed genuine call falsely flags as faked |
| 36 | mission-control | `sdlc_manager.py:4034`; `issues/SKILL.md:155` | Assign card risk level | human (`--risk` passed explicitly) | issue body text | score | ordered levels fit `score`; can pre-fill | high/very-high unlocks extra sections — must still ask on low confidence |

## Part B — harness inventory and the shared-skill mechanism

`~/.agents/skills` is managed by a general skill installer whose lock file
(`~/.agents/.skill-lock.json`) names its sources by GitHub repository: `typesafe-ai/skills` for
`typesafe-ai`, `vercel-labs/skills` for `find-skills`, `herdrdev/herdr` for `herdr`. That file's
`lastSelectedAgents` list names sixteen harnesses the installer knows how to target, including
`codex`, `gemini-cli`, `grok`, `hermes-agent`, `qwen-code` — but knowing about a harness isn't the
same as having synced a skill into it, as the table shows. Only three of the eleven directories
under `~/.agents/skills` are lock-tracked at all; the other eight (including `agent-launcher`) came
from some other, untracked install.

| Harness | Instruction file(s) | Skills directory | `typesafe-ai` visible? | Shell/Python/HTTP | Model/provider selection |
|---|---|---|---|---|---|
| Claude Code, personal | `~/.claude/CLAUDE.md` (10.7 KB) | `~/.claude/skills` | Yes — symlinked to `~/.agents/skills/typesafe-ai` | Yes | Live in-session picker (Opus/Sonnet/Haiku/Fable) |
| Claude Code, company | `~/.claude-company/CLAUDE.md`, a symlink to the file above | `~/.claude-company/skills` — a **separate**, non-symlinked dir with only `herdr` + `typesafe-ai` (also symlinked); missing `agent-launcher`/`find-skills` | Yes | Yes | Same picker |
| Codex | `~/.codex/AGENTS.md` (6.0 KB, roughly half Claude's/Gemini's size); `config.toml`'s `project_doc_fallback_filenames = ["CLAUDE.md"]` falls back to a repo's `CLAUDE.md` only when it has no `AGENTS.md` (this repo has one, so no fallback here) | `~/.codex/skills`: `.system`, `agent-launcher`, `hermes-agent`, `honcho-memory`, `langfuse` | **No** — and its `agent-launcher` is a real copy, not a symlink, so Codex's skills sit on a separate, non-shared path | Yes (`sandbox_mode = "danger-full-access"`, `approval_policy = "never"`) | `config.toml`: `model = "gpt-6-astra"`, separate reasoning-effort per mode |
| Gemini/Antigravity (via `agy`) | `~/.gemini/GEMINI.md` (11.0 KB); its own text says shared-register sections mirror `~/.claude/CLAUDE.md` | `~/.gemini/skills` — confirmed **completely empty**; Antigravity may resolve skills via `~/.gemini/antigravity-cli` instead, not opened this pass | **No** | Yes, via `agy` | Not inspected this pass |
| Qwen (qwen-code) | No top-level instruction markdown found (only a narrow `output-language.md`); likely `~/.qwen/settings.json`, not opened | `~/.qwen/skills`: `herdr` (real copy) + `agent-launcher`/`find-skills`/`typesafe-ai` symlinked | Yes | Yes | Not inspected this pass |
| Grok | No top-level instruction markdown at `~/.grok`'s root; config lives in `config.toml` | Does **not** use `~/.agents`. Runs its own marketplace (`xai-org/plugin-marketplace.git`) and already holds real, non-symlinked snapshots of this repo's own `saga`/`orchestrate`/`mission-control`/`deploy` plugins under `~/.grok/installed-plugins/` | **No** — would need publishing through Grok's own marketplace, or embedding inside the mirrored plugin content | Yes (`permission_mode = "always-approve"`) | `config.toml`: `default = "grok-4.6"`, `default_reasoning_effort = "high"` |
| Hermes | `~/.hermes/SOUL.md` — not an `AGENTS.md`/`CLAUDE.md`/`GEMINI.md`-shaped file; matches this repo's `hermes-profile-evolution` plugin, which edits Hermes's persona only through a governed suggestion flow | `~/.hermes/asgard-skills`: at least one custom skill (`asgard-run`) synced by its own `sync_live_skill.sh`, unrelated to the vercel-labs convention | Unconfirmed — nothing opened this pass shows Hermes reading `~/.agents/skills` | Yes (`asgard-run` is itself Python CLI scripts) | Not inspected |
| `agents` wrapper | Not a harness — a 3,083-line shell launcher for all of the above (plus cursor/muse/opencode), mapping model/effort flags per vendor. Loads no instructions or skills itself | — | — | Yes (it starts the others) | Delegates to the launched harness |

`TYPESAFE_API_KEY` was not found anywhere on this machine: not in `~/.bash_profile`, `~/.bashrc`,
`~/.zshrc`, `~/.zprofile`, `~/.profile`, or `~/.zshenv`; not in the macOS keychain's
generic-password store under that exact name ("the specified item could not be found"); not in
Claude Code's own `settings.json` env blocks. The `typesafe-ai` skill's own `SKILL.md` doesn't
document provisioning. The skill-lock file timestamps the install at 2026-09-18T01:47:04Z — earlier
today — so this most likely hasn't been wired into a persistent, subprocess-visible location yet
rather than hidden somewhere this survey missed. Worth confirming directly before any plugin script
tries to call the API.

## Part C — reusable plumbing

**HTTP calls.** `pyproject.toml` declares `requests>=2.31.0`, and mission-control's
`sdlc_manager.py` uses it for GitHub's REST API. But the one place already calling a third-party,
secret-bearing external API — saga's `engine_bridge_http.py`, dispatching to Ollama Cloud and
DeepSeek — deliberately uses the standard library's `urllib.request` instead, via a `runner()`
factory taking three injectable arguments (`urlopen`, `getenv`, `clock`) that default to the real
implementations, so tests substitute fakes with zero live network and zero monkeypatching. Its
secret rule: a registry row names the bearer-token's environment-variable *name*; that name
resolves to its value exactly once, at request-build time, placed only in the outgoing header —
never in the invocation record, receipt, result, or any log line (only the name may appear in a
failure message, never the value). Its status vocabulary is closed — `ok`/`error`/`timeout`/
`malformed` — and never fabricates success. A TypeSafe client should copy this shape rather than
the `requests` convention, since the codebase already treats a bearer-token call to a third-party
AI vendor as a different trust tier than a GitHub call.

**Where shared code lives.** Cross-plugin code lives under
`plugins/fleet-core/scripts/fleet_commons/`. Every consumer plugin vendors a byte-identical
`fleet_commons_shim.py` into its own `scripts/` (a drift-guard test enforces the match), which
resolves the real fleet-core location through four fallback rungs in order — an explicit
`FLEET_COMMONS_ROOT` override, a repo-checkout walk-up, `~/.claude/plugins/installed_plugins.json`,
a cache-sibling scan — failing loudly if none succeed. A `typesafe_client.py` module belongs there,
reached the same one-line way as everything else: `fleet_commons_shim.load("typesafe_client")`.

**Config and environment.** No repo-wide settings framework is in use (no `python-dotenv`, no
Pydantic Settings, despite `pydantic>=2.5` being a dependency used elsewhere for validation).
Scripts read a local JSON config through their own `load_config()` helper, or call
`os.environ.get(...)` directly for secrets.

**Exposing a script to a skill.** The house pattern, cited by
`artifact_pointer.py`'s own docstring (precedent: `saga/scripts/outcome_github.py`): Python 3.12,
standard-library where practical, an `argparse` command-line interface, external-effect calls
resolved as keyword arguments at call time rather than import-time defaults so tests can
substitute them. A `typesafe_client.py` command-line tool fits this directly; the skill's
`SKILL.md` would document its `--help` surface rather than embed a bespoke prompt.

**Tests.** `pytest`, with a root `tests/conftest.py` supplying autouse fixtures reaching every
`plugins/*/tests` (e.g., a fake `herdr` binary placed ahead of the real one on `PATH`, so a test
that forgets to stub it fails loudly instead of quietly passing against whatever's installed).
Nothing mocks HTTP via a library (no `responses`, no `httpretty`); `tests/test_engine_bridge_http.py`
is the existing model — a fake `urlopen`/`getenv` passed through the same keyword arguments the
real factory exposes.

**Release surface.** A "tri-lock" gate (`scripts/check_release_surface_parity.py`) requires each
plugin's `plugin.json` version, its `marketplace.json` entry, and its `CHANGELOG.md`'s newest
heading to agree, failing and naming exactly the plugin(s) out of step. Any new TypeSafe surface —
a new plugin, or a new `fleet-core`/`saga` version carrying the client — must bump all three
together.

## Part D — where the leverage is, and why

1. **The conditional-lens selection in `lens-roster.json` is the single highest-leverage point.**
   It runs on every code review and team-execution plan, ten judgment calls each time, and the
   governing document already states in plain English the requirement a typed judgment answers.
   The target behavior is already specified; it just isn't implemented as anything faster than a
   full reasoning-model read today.

2. **The refute-N verifier panel is the highest-leverage point for cost and latency, not quality.**
   Each verifier is a complete agent invocation at the unit's tier, potentially Opus-class, spent
   on a single per-finding yes/no question. A typed judgment can't replace a verifier that runs
   tests and reads code, but it's a plausible extra vote at near-zero cost, or a pre-screen on
   whether the full panel is worth convening.

3. **The `parse_issue.py` regex flags are the one point where a wrong replacement costs more than
   usual**, because they feed a mandatory gate, not a suggestion. A false negative means the hard
   test-gate silently never fires. Any change here should widen what triggers the gate, never
   narrow it, and deserves a higher bar than the rest of this list.

4. **The per-unit tier/work-shape classification has the broadest reach of any point**, running
   once per planned unit across the whole fleet and directly implementing the operator's own
   standing tiering policy. A structured choice call would make that mapping consistent in a way
   prose applied across separate sessions by a large reasoning model isn't guaranteed to be.

5. **Because every decision point here is reached from plugin Python code that whichever coding
   agent is driving invokes over its shell tool, the harness-inventory findings matter less than
   they first appear to.** The `typesafe-ai` skill file only teaches an interactively-reasoning
   model to reach for the primitives on its own initiative; none of the thirty-six rows need that
   skill visible in the driving harness, since they'd be called from inside the plugin's own
   scripts regardless. The real question for width of reach is whether a harness's session can
   shell out to a Python process with network access and the key — not whether Codex, Grok,
   Gemini, Qwen, or Hermes has the skill symlinked.

6. **Nothing can be wired up anywhere yet, because `TYPESAFE_API_KEY` wasn't found exported in any
   shell profile, the keychain, or Claude Code's settings.** Closing that gap, somewhere a plain
   subprocess can read it regardless of which harness spawned it, is a precondition for every row
   in Part A, not only the ones reached from Claude Code.

7. **`engine_bridge_http.py` is a ready-made template for this client, and a better one than the
   `requests` convention already used for GitHub.** Its stdlib-only approach, injectable seams,
   closed status vocabulary, and "read the secret's name, resolve the value once, never log it"
   discipline exist because the codebase already treats a bearer-token call to a third-party AI
   vendor as a different trust tier than a GitHub call — exactly the distinction a TypeSafe client
   needs to respect.

8. **The strongest evidence for where to start is the codebase's own comments, not this survey's
   judgment.** `_REVIEW_SHAPED`'s single-word regex is introduced by a docstring that says outright
   no regex is trustworthy for that decision, and `_looks_like_engine_command`'s six OR'd
   substrings decide a real-vs-faked delegation governance verdict. Both are places where the
   author already wanted better than string matching and shipped it anyway for lack of a fast
   alternative — a stronger signal to act on than a heuristic nobody has complained about.
