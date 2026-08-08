# Grounding Summary — Output Styles Ideation (run 2e71b34e, 2026-08-07)

## Focus

Design custom Claude Code output styles for the operator's two configurations
(`~/.claude` personal, `~/.claude-company` work).

## Operator's four settled decisions (CONSTRAINTS, not open questions)

1. **Deliverable** — ranked ideas with revivable rejections. No files authored this run.
2. **Distribution** — ship as a plugin through the `infiquetra-plugins` marketplace both
   configurations already load.
3. **Relationship to CLAUDE.md** — styles ABSORB presentation rules; CLAUDE.md slims to
   non-presentation policy (validation discipline, tooling, delegation, tiering, journal).
   The operator accepted the stated risk: "a rule only lives in the active style — switch
   styles, lose it, unless every style shares a common base."
4. **Selection** — committed per-repo settings.
5. **Volume** — go deep; 8-10 survivors (overrides the default 5-7 ceiling).
6. **Engine lane** — Claude only.

## Operator's six verbatim seed ideas

1. "often I am getting mermaid diagrams instead of ascii, when I am in the cli."
2. "I generally want good explainations with pictures, graphs, tables over a mountain of text"
3. "excessive abreviations or referencing lines of code don't help. I think have some things
   related to this in my global claude.md file already"
4. "probably more than one output style depending on the repo's contents."
5. (numbered 6 by the operator) "to often at the end of the output I have no idea what is
   status. I think some sort of summary with: what's complete and whats next might be ideal"
6. (numbered 7) "I can't be the first person to want better output for the type of work I do,
   search for prior art to seed these ideas"

## MEASURED FACTS (verified, not assumed)

### Volume and reach
- 2,530 transcript files, 35 days, both configurations.
- **13,665 main-thread assistant text messages vs 17,922 subagent messages.**
- **Output styles DO NOT reach subagents.** Two independent proofs:
  (a) empirical — the `★ Insight` box (rendered only under Explanatory) appears in 315
      main-thread vs 7 subagent messages (98:2);
  (b) code — binary 2.1.224 namespaces prompts as `repl_main_thread:outputStyle:<name>`,
      while agents resolve to a separate `agent:custom` identifier.
- **=> 57% of all assistant text is generated outside any output style's reach.**

### Rendering (16,029 main-thread messages analyzed)
- ```mermaid``` fenced block in rendered text: **7 messages (0.04%)** — seed #1's premise is
  NOT supported at the main-thread level. Mermaid concentrates in subagent traffic (119) and
  in file contents Claude reads/writes (~23 of 30 assistant-line hits are Write/Edit payloads).
- Box-drawing characters: 341 messages — but **311 (91%) are the `★ Insight` callout box**
  from the currently-active Explanatory style, not diagrams. Genuine diagrams: ~30 (0.19%).
- Genuine ASCII diagram shapes actually in use: **file trees** and **small dependency-chain
  graphs**. Not flowcharts, not sequence diagrams, not state machines.
- Markdown tables: 438 messages (2.73%). Bullets-only-no-table-no-code: 895 (5.58%).
- "Mountain of text" (>4,000 chars, no table/diagram/code): 40 messages (0.25%) — small, BUT
  one of the three worst was **literal unformatted JSON** (a subagent findings payload,
  12,347 chars) dumped into a main-thread reply undigested.
- Length is **bimodal**: median 142 chars, p75 292, p90 1,658, max 26,994. A style tuned to the
  median will look fine daily and still fail the 10% of turns that matter most.
- `path:line` references: 597 messages (3.72%), avg 1.79 per message when present, max 25.
- All-caps 2-5 letter tokens: 20% of messages — but ~half the top offenders are `NOT`, `DONE`,
  `PASS`, `GET`, `POST`, `HEAD` (emphasis-caps and HTTP verbs). Genuine internal terms needing
  a gloss: ADR, HITL, DAG, COPPA, SOUL, BP, REG, DR, TUI, DRIFT, INV, SKILL.
- Bare commit-hash-shaped hex with no nearby explanatory word: ~7.9% of messages (heuristic).
- **Turn endings: only 3 of 395 sessions (0.76%) end with any summary/next/status signal.**

### Human friction (765 genuine human main-thread messages)
- Format complaints 43 (5.6%), clarity 55 (7.2%), status confusion 14 (1.8%),
  correction/frustration 41 (5.4%), verification callouts ~0.
- **Personal vs work friction is nearly identical** (format 21 vs 21; clarity 29 vs 26;
  corrections 22 vs 18). Friction clusters by REPO SHAPE, not by configuration.
  => argues for ONE shared style set varying by repo/mode, not two divergent config sets.

Key verbatim quotes:
- 2026-07-17 campps-context-library: "you always do that... I am in cli, you waste tokens
  generating mermaid. stop doing that"
- 2026-07-27 infiquetra-claude-plugins (WORK): "where are we? can you close this outcome yet?
  you never give me any next steps... I rarely understand what you are telling me, to much
  extra info and not enough of what is important right now"
- 2026-07-20 infiquetra-claude-plugins: "when you say clone, what the fuck are you talking
  about... you always act as if I have the references you do... I am bouncing around to 5 or 6
  different things. udpate the global claude file to keep this in check"  <-- ORIGIN of the
  Plain English section now in CLAUDE.md. It is RATIFIED POLICY, not a new proposal.
- 2026-07-26 campps-context-library: "stop saying \"vacuous\" and be more descriptive... more
  like a developer, less like an academic"
- The operator asked for "pictures" **five separate times** across the window, always when
  already lost. TENSION RESOLVED: the objection is to an UNREQUESTED diagram in a routine
  update, not to diagrams. This is a rule about TRIGGERING, not about format.

### Antecedent analysis — 9 traced complaints, failure taxonomy
1. **No closing next-step/ask** — 5 of 9. Message ends on a declarative fact or aside.
2. **Unglossed term of art** — 2 of 9 ("clone", "vacuous").
3. **Bare identifier as a noun** — 2 of 9 (one message carried 15+ bare issue numbers).
4. **Dense technical wall, no plain framing** — 2 of 9 (IAM ARN detail; SOUL/atlas jargon).
5. **Wrong-medium rendering** — 1 of 9 (mermaid in CLI).
6. **Truncated/incomplete delivery** — 1 of 9. Message ended on "Two scope calls that would
   change it materially, and they're yours:" and the text stopped. Operator: "output stopped".

### THE COUNTER-SAMPLE (highest-value finding)
10 antecedents to satisfied/forward-progress replies:
- **10 of 10 open with a bolded one-sentence plain-language verdict** ("PR #656 is green —
  6/6 passed.", "#169 is done and live on `main`.").
- **10 of 10 end with a single explicit concrete ask** ("Want me to run the merge?",
  "Holding here until you weigh in.").
- Length 835-4,197 (avg 2,306) vs complaints 2,060-4,462 (avg 3,015) — **OVERLAPPING.
  Length is NOT the discriminator.**
- Headings/tables inconsistent — **formatting is NOT the discriminator.**
- **The discriminator is structural placement: verdict-first, ask-last, nothing declarative
  trailing after the ask.**
- Pure praise language ("perfect", "thanks") is absent from this operator's corpus entirely.

### Repo-shape hypothesis test (seed #4) — PARTLY HOLDS
- `Bash` is the plurality tool in EVERY repo (57-84%). Content type does not drive interaction.
- `campps-context-library` (spec Markdown) and `team-norns` (governance Python) have nearly
  identical tool profiles and prompt register despite unrelated subject matter.
- Real separator: **whether the repo is being driven through an orchestration workflow that
  turn.** Cuts across content type.
- Evidence supports **TWO interaction profiles**: orchestration-mode (team-norns,
  campps-context-library, infiquetra-claude-plugins, team-mimir, campps-e2e-canary) and
  direct-ops (home-lab 84% Bash, infiquetra-ansible-collections). `talaria` is a third,
  temporary, decision-log register (ADR-gated pre-implementation).
- Human prompt modes everywhere: **approval/continuation** ("go ahead", "approved") and
  **status check** ("where are we with X"). This is an operator supervising a fleet.
- **DETECTION IS THE WEAK LINK.** Content-type rules are clean: `constitution.md` =>
  agent-governance; `.claude-plugin/` => plugin-dev; `ansible/` => infra. But
  **orchestration-mode has NO reliable file-presence rule** — `.saga/` exists in
  ansible-collections too, which shows almost no orchestration usage. Mode must be read from
  live tool-use mix, not repo structure. `talaria`'s ADR signature is temporal and will
  silently stop firing once it ships code.

## MECHANICS (verified against binary 2.1.224 + Anthropic docs)

- Frontmatter: `name`, `description`, `keep-coding-instructions` (default **false**),
  `force-for-plugin` (default false). Both strings confirmed present in the binary.
- **`keep-coding-instructions: false` is the DEFAULT and it SILENTLY REMOVES Claude Code's
  built-in software-engineering instructions** — how to scope changes, write comments, and
  verify work. Highest-confidence risk in the whole research pass, from Anthropic's own docs.
- Four built-ins confirmed in binary: Default, **Proactive**, Explanatory, Learning.
- Load tiers: user config dir, project `.claude/output-styles/` (loads from every such dir
  between cwd and repo root; closest-to-cwd wins; since v2.1.178), managed policy, and
  **plugins** (`outputStylesPath` / `outputStylesPaths`, with `append` merge).
- `force-for-plugin: true` lets a plugin auto-apply its style and override the user setting.
- Style takes effect only after `/clear` or a new session (system prompt read once).
- The `/output-style` slash command was deprecated (v2.1.73) and removed (v2.1.91). The
  operator runs 2.1.224. Selection now lives in `/config`, writing `outputStyle` to
  `settings.local.json` (typically NOT committed).
- **TENSION**: making a style AVAILABLE per repo (drop the file in `.claude/output-styles/`)
  is a different problem from SELECTING it per repo (needs an `outputStyle` settings key).
  Committed selection needs `settings.json`. Of 18 repos with Claude settings, only 6 have a
  committed `settings.json` and every one sets only `permissions` or `worktree.bgIsolation` —
  **no repo has ever committed a behavior key. This would be a first.**
- Anthropic closed a per-directory output-style config request as "not planned" (issue #25612).
- No first-party terminal image rendering; a Kitty/iTerm2/Sixel request (#2266) closed
  unimplemented. ASCII/Unicode is the only portable path.
- `--append-system-prompt` is the documented non-destructive alternative (appends, removes
  nothing).

## EXISTING CONFIGURATION CONTEXT

- **Neither configuration has an `output-styles/` directory; neither sets `outputStyle`.**
  Fully greenfield.
- `~/.claude-company` symlinks `agents`, `commands`, `hooks`, `CLAUDE.md` to `~/.claude`.
  `skills`, `plugins`, `projects`, `settings.json` are separate.
- **Behavioral divergence: the `repo-freshness` SessionStart hook fires on personal sessions
  and is ABSENT from the work configuration's hook list.** Work sessions lack a safeguard
  personal sessions have.
- Both configs: `effortLevel: xhigh`, `alwaysThinkingEnabled: true`,
  `permissions.defaultMode: bypassPermissions`.
- **The statusline already renders every 10s**: model/effort, context-window used/total/%,
  cost (session/today/month-to-date), git branch, PR review state, AWS/K8s context, venv.
  => an end-of-turn summary must NOT restate any of these. Only what the turn DID, what was
  FOUND, and what REMAINS earns space.
- Hooks: only `repo-freshness.sh` injects context Claude sees. `cmux-notify.sh` and
  `herdr-agent-state.sh` write to external sockets, not context.
- `saga/references/formatting-style.md` is a COMPETING, pytest-enforced formatting authority
  (`tests/test_saga_doc_formatting.py`) governing generated saga documents. A style must be
  compatible with it, not fight it. Its rules: <=3-sentence paragraphs, one-line summary
  first, tables for comparative data, no stacked `**label:**` lines (CommonMark collapse bug).
- CLAUDE.md PRESENTATION sections (candidates to absorb): "Plain English" (7 numbered rules),
  "Communication & Feedback". POLICY sections (must stay): Validation Discipline, Workflow,
  Tooling & Git, Delegation & Context Economy, Model & effort tiering, Engineering Journal,
  Prohibited Content.

## EXTERNAL PRIOR ART (`external:` basis material)

- **ASD-STE100 Simplified Technical English** adapted as an output style
  (gist L1nefeed/4164ecaaf77879e76dca3c06f142f1c2): "One word, one meaning"; mandated verbs
  (check not verify, start not initiate) to kill synonym rotation; active voice, "name the
  actor"; <=20 words/instruction sentence, <=25 words/explanation; noun clusters capped at 3
  words; **"Lead with the result. The first sentence of a response answers the question."**
  Best-matched prior art for seed #3.
- **tldr-claude-skill** (github.com/ksuleymanoglu/tldr-claude-skill): "Lead with the answer —
  TL;DR up top, detail underneath"; "Tables for parallel structure — comparisons, options,
  mappings"; "Cut filler — just, really, basically"; ships intensity variants (lite ~25-35%,
  full ~50-60%, ultra ~70-75% compression) AND an explicit safety carve-out: "drops back to
  normal prose for security warnings, destructive operations, and ambiguous multi-step
  instructions."
- **IoTeacher ASCII dashboard gist**: named layout zones — "Top band -> title/scope/status/
  KPIs; Main area -> dominant chart/topology/table; Side rail -> alerts/ranked items;
  Bottom band -> logs/timeline/next actions." Anti-patterns: "Overusing borders until content
  becomes hard to scan", "Inconsistent mixing of ASCII and Unicode styles." Has NO
  width-drift-prevention technique.
- **ASCII diagram types with real prior art**: state machines and sequence diagrams
  (RFC 793 convention, 40+ years), directory trees (`tree`, `git log --graph`). Layered
  architecture degrades gracefully. **Gantt charts and dense many-node graphs are known-bad —
  no good ASCII rendering found.**
- **LLMs are architecturally weak at spatial text**: ArtPrompt (ACL 2024, arxiv 2402.11753)
  measured GPT-4 at **25.19% accuracy on single-character ASCII-art recognition**. NO
  validated prompt-only technique for preventing width-drift was found. Treat any
  drift-prevention claim as unverified until tested.
- **Over-compression caution** (knightli.com): do NOT compress onboarding, architecture
  tradeoffs, complex incident review, security risk analysis, database migration plans, or
  unclear requirements. Do not remove warnings about destructive commands, databases,
  permissions, production config, or file deletion.
- **Diátaxis** four modes (tutorial / how-to / reference / explanation) as a cheap
  mode-selection step before choosing prose vs table vs diagram.
- **C4 model**: notation-independent; prescribes WHICH abstraction level to show, not syntax.
- No evidence found that output styles degrade tool-calling or multi-step reliability. The
  honest gap is "under-researched", not "known to fail". Do not manufacture this risk.

## TOPIC AXES (Phase 1.5)

- **A1 Turn shape** — how a response opens and closes; where the verdict, the evidence, and
  the ask sit. Highest-evidence axis (5 of 9 traced failures; 10 of 10 counter-samples).
- **A2 Word-level discipline** — glossing terms of art, naming a referent before its
  identifier, plain-language framing, jargon and acronym control.
- **A3 Visual form selection** — when a table/diagram/prose is right, which ASCII forms are
  safe, medium-awareness, and what triggers an unrequested visual.
- **A4 Style architecture and lifecycle** — the shared base problem, `keep-coding-instructions`,
  plugin packaging, per-repo/per-mode selection and its detection weakness, and how the
  operator would VERIFY a style is working.
- **A5 Reach beyond the main thread** — the 57% subagent surface no style governs, and any
  mechanism that could address it.
