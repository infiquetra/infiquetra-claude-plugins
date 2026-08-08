---
date: 2026-08-07
topic: output-styles
focus: custom Claude Code output styles for the ~/.claude and ~/.claude-company configurations
scope: broad
repo: bin
maturity: idea-ready
---

# Ideation: Custom Claude Code Output Styles

Run id `2e71b34e`. Six frame agents, 67 raw candidates, ~22 distinct ideas after dedupe,
10 survivors. Scratch and frame outputs under `docs/ideation/2026-08-07-output-styles-run/`.

## Operator decisions settled during this run

| decision | choice |
|---|---|
| Deliverable | Ranked ideas with revivable rejections; no style files authored this run |
| Distribution | Ship as a plugin through the `infiquetra-plugins` marketplace both configurations load |
| Relationship to CLAUDE.md | Styles absorb presentation; CLAUDE.md slims to non-presentation policy — **qualified by survivor 9** |
| Selection | Committed per-repo settings — **qualified by survivor 6** |
| Volume | Go deep; 8-10 survivors (overrides the engine default of 5-7) |
| External engine lane | None; Claude only (persisted to `.saga/engine-prefs.json`) |
| **Shared-base mechanism** | **Authored files plus a byte-identity test. No generator, no build step.** Settled 2026-08-07 |

## Grounding Context

**Repo:** The subject is not `~/bin` itself but the two Claude Code configuration trees it
administers. Neither `~/.claude/output-styles/` nor `~/.claude-company/output-styles/` exists and
neither `settings.json` sets an `outputStyle` key — fully greenfield. `~/.claude-company` symlinks
`agents`, `commands`, `hooks`, and `CLAUDE.md` back to `~/.claude`; `skills`, `plugins`, `projects`,
and `settings.json` are separate. One behavioral divergence matters: the `repo-freshness` SessionStart
hook fires on personal sessions and is absent from the work configuration.

Measured across 2,530 transcript files from the last 35 days, both configurations:

- 13,665 main-thread assistant text messages against 17,922 subagent messages. **57% of assistant
  text is generated outside any output style's reach.** Proven twice — the `★ Insight` box (rendered
  only under Explanatory) appears 315 times main-thread against 7 in subagent messages, and binary
  2.1.224 namespaces prompts `repl_main_thread:outputStyle:<name>` while agents resolve to a separate
  `agent:custom` identifier.
- Only **3 of 395 sessions (0.76%)** end with any summary, next-step, or status signal.
- Mermaid fenced blocks in rendered main-thread text: **7 of 16,029 messages (0.04%)**. Mermaid
  concentrates in subagent traffic (119) and in file contents Claude writes.
- Box-drawing characters appear in 341 messages, but **311 (91%) are the `★ Insight` callout**, not
  diagrams. Genuine diagrams: ~30 (0.19%), and only two shapes — file trees and small dependency
  chains.
- Response length is bimodal: median 142 characters, p75 292, p90 1,658, max 26,994.
- 765 genuine human main-thread messages. Friction is **near-identical between personal and work**
  (format 21 vs 21, clarity 29 vs 26) and clusters by repo shape, not by configuration.

**Antecedent analysis — nine traced complaints, with the assistant message that preceded each:**

| failure shape | traced cases |
|---|---|
| No closing next-step or ask | 5 of 9 |
| Unglossed term of art | 2 of 9 |
| Bare identifier used as a noun | 2 of 9 |
| Dense technical wall, no plain framing | 2 of 9 |
| Wrong-medium rendering (Mermaid in a terminal) | 1 of 9 |
| Truncated delivery — promised content never arrived | 1 of 9 |

**The counter-sample (the run's highest-value finding).** Ten antecedents to satisfied replies:
10 of 10 open with a bolded one-sentence plain-language verdict; 10 of 10 end with a single explicit
concrete ask. Length overlaps the complaint set (835-4,197 against 2,060-4,462) and headings/tables
are inconsistent in both. **Length is not the discriminator. Formatting is not the discriminator.
Structural placement is** — verdict first, ask last, nothing declarative trailing.

**Verified mechanics (binary 2.1.224 plus Anthropic docs):** frontmatter is `name`, `description`,
`keep-coding-instructions` (default **false**, silently removes built-in software-engineering
instructions), `force-for-plugin`. Four built-ins: Default, Proactive, Explanatory, Learning. Styles
load from the config dir, project `.claude/output-styles/` (closest-to-cwd wins), managed policy, and
plugins. A style applies only after `/clear` or a new session. The `/output-style` command was removed
in v2.1.91; selection now writes `outputStyle` into `settings.local.json`, typically uncommitted. Of
18 repos with Claude settings, only 6 have a committed `settings.json` and every one carries only
`permissions` or `worktree.bgIsolation` — **no repo has ever committed a behavior key.**

**Repo-shape hypothesis test:** partly holds. `Bash` is the plurality tool in every repo (57-84%), and
`campps-context-library` (spec Markdown) and `team-norns` (governance Python) have near-identical tool
profiles. The real separator is whether a repo is driven through an orchestration workflow that turn —
which has **no reliable file-presence rule**. `.saga/` exists in `infiquetra-ansible-collections`,
which shows almost no orchestration usage; `talaria`'s decision-record signature is temporal and stops
firing once it ships code.

**Context-libraries:** `infiquetra-context-library` and `campps-context-library` journals consulted;
both are dominated by code-correctness and evidence discipline rather than communication style. No
org-wide document governs how an agent should talk to a person. `saga/references/formatting-style.md`
is a competing, pytest-enforced formatting authority governing generated saga documents.

**Named repos:** none named by the operator; the run is configuration-scoped.

## Topic Axes

- **A1 Turn shape** — where the verdict, the evidence, and the ask sit in a response.
- **A2 Word-level discipline** — glossing terms of art, naming referents before identifiers, jargon control.
- **A3 Visual form selection** — table vs diagram vs prose, safe ASCII forms, what triggers an unrequested visual.
- **A4 Style architecture and lifecycle** — shared base, `keep-coding-instructions`, plugin packaging, selection and its detection weakness, verifying a style works.
- **A5 Reach beyond the main thread** — the 57% subagent surface no output style governs.

## Ranked Survivors

### 1. The closing law — the last line is a state declaration and an ask, and nothing follows it

Every turn that changed state ends with what is now true, what is unfinished, and the one decision
that is yours — with nothing after it.

The block declares state, not activity: if a line describes what the agent did rather than what is now
true, it does not belong. The closing ask is written as pre-committed branches (`if X -> I will Y`) so
"go" is a complete answer. It may not restate anything the statusline already renders — model, effort,
context percentage, cost, branch, PR review state.

Three independent evidence lines converge. All ten satisfied replies end with a single concrete ask;
five of nine traced complaints end on a trailing aside; only 0.76% of sessions close with any status
signal. The I-PASS medical handoff — the only such format with a measured outcome effect — cut medical
errors 23% and preventable adverse events 30% across 10,740 admissions, and its least-copied element
is exactly this: contingencies written in advance so the receiver selects rather than derives.

The ceremony is real, and if it fires on trivial turns it becomes noise that gets switched off — which
is why survivor 2 is not optional. There is also a genuine risk of degrading into a boilerplate footer
that restates the middle.

| field | value |
|-------|-------|
| basis | `direct:` counter-sample 10/10 ask-last; 5 of 9 traced failures; 3 of 395 sessions · `external:` Starmer et al., *NEJM* 2014;371:1803-12; US NRC shift-turnover guidance |
| source | combined — user-seed #5 corrected + frame-agent (4-frame convergence) |
| confidence | 95 |
| complexity | Low |
| axis | A1 Turn shape |
| status | Unexplored |

### 2. Two turn shapes, with an enumerated trigger list

A full-orientation turn and a delta turn, and a named list of what triggers the full one.

Full orientation is mandatory on the first substantive turn of a session, on a topic change, after a
long tool run, and after a subagent returns. Every other turn is a delta turn reporting only what
changed, anchored to the last full orientation. The military fragmentary order works this way — same
skeleton, only changed paragraphs filled, base order left standing.

Response length is bimodal (median 142, p90 1,658), so one turn shape cannot serve both ends. This is
the multiplier on every other rule: a style whose ceremony makes fifty short exchanges a day feel
bureaucratic gets switched off, and that costs every rule in the file.

Trigger lists are guesses until tested. "After any subagent returns" may be one trigger too many given
how much of this operator's work is agent fan-out.

| field | value |
|-------|-------|
| basis | `direct:` measured bimodality across 16,029 messages · `external:` US Army *ADP 5-0*, fragmentary-order format |
| source | frame-agent (2-frame convergence) |
| confidence | 90 |
| complexity | Low |
| axis | A1 Turn shape |
| status | Unexplored |

### 3. Word-level rules restated in mechanical form, not aspirational form

An identifier may never be a sentence's subject or object; an abbreviation must be earned by use count.

An issue number, commit hash, branch, test name, or `path:line` reference may only sit in apposition
to a real noun naming what it is. An abbreviation used fewer than three times in a response is not
introduced at all — and the pattern `Full Name (ABC)` is banned outright, because needing that
introduction is evidence the short form should not exist.

The ratified Plain English rules are still being violated: bare identifiers are 2 of 9 traced
complaints, one message carried more than fifteen bare issue numbers, ~7.9% of messages use
commit-shaped hex with no explanatory word nearby. Air traffic control solved the identical problem
mechanically — a number never appears without the word saying what kind of number it is. "Add a name"
is an aspiration a model can believe it satisfied while producing identical output; a grammatical
prohibition has a test and is greppable.

A use-count rule needs a closed exemption list. Measured data shows a naive acronym trigger misfires
constantly on `NOT`, `DONE`, `PASS`, `GET`, `POST`, `HEAD` — roughly half the top all-caps tokens.

| field | value |
|-------|-------|
| basis | `direct:` 2 of 9 failures; 7.9% bare hex; 20% all-caps with ~half false positives · `external:` FAA Air Traffic Bulletin 2018-1; AP Stylebook; NTSB/AIR-18-01 (Air Canada 759) |
| source | combined — frame-agent + user-seed #3 |
| confidence | 85 |
| complexity | Low |
| axis | A2 Word-level discipline |
| status | Unexplored |

### 4. Visuals are phase-gated — barred in routine, required in orientation

The same diagram is wrong in a progress update and mandatory when the operator is being oriented.

Routine turns (progress update, single-file edit, command result, approval acknowledgement) get no
unrequested visual of any kind. Orientation turns (operator asks where things stand, a subject is
introduced for the first time this session, a subagent's findings are being delivered, more than two
entities relate to each other) **require** one. Comparison of three or more items sharing attributes
requires a table. An explicit request overrides the phase.

The operator objected to unrequested Mermaid and separately asked for "pictures" five times, always
when already lost. That is a phase distinction, and aviation's sterile flight deck rule is its
codified form. The non-obvious half is that the same regulation mandates callouts during the critical
phase — a rule that only suppresses produces an agent that is visual-shy in exactly the turns where
five recorded requests say a visual is wanted.

The orientation trigger list must be enumerated by hand; a vague condition reproduces the original
complaint.

| field | value |
|-------|-------|
| basis | `direct:` five "with pictures" requests, all when lost; verbatim 2026-07-17 Mermaid objection · `external:` 14 CFR 121.542, sterile flight deck |
| source | combined — user-seeds #1 and #2 + frame-agent (3-frame convergence) |
| confidence | 87 |
| complexity | Low |
| axis | A3 Visual form selection |
| status | Unexplored |

### 5. A closed catalog of line-local forms, with syntax keyed to destination

Three permitted visual forms drawn identically every time, and Mermaid allowed wherever it renders.

Permit only forms whose correctness is line-local — an indented file tree, a single-line arrow chain
(maximum seven nodes), a two-column state table. Markdown tables qualify because the renderer does the
alignment. Forbid anything requiring a character on line 3 to align with one on line 9. Key syntax to
destination: terminal-bound bytes use the catalog; bytes going into a file, a PR body, or an artifact
use Mermaid.

A blanket Mermaid ban would degrade saga documents, journal entries, and PR bodies to fix 7 messages
out of 16,029. The line-local criterion is the only selection rule the evidence supports — GPT-4 was
measured at 25.19% accuracy on single-character ASCII-art recognition and no validated prompt
technique for preventing width drift exists. Aviation's basic-T instrument layout makes the deeper
argument: sameness beats expressiveness, because a bespoke diagram charges the reader a layout-parse
before any information arrives.

The tradeoff should be accepted knowingly: some diagram the operator may want is permanently off the
menu, and the style deliberately prefers a worse repeated form over a better bespoke one. Restricting
box-drawing to file-tree connectors also retires the `★ Insight` callout by construction.

| field | value |
|-------|-------|
| basis | `direct:` only file trees and dependency chains appear in the corpus; Mermaid 7 of 16,029 main-thread against 119 in subagent traffic · `external:` ArtPrompt, arXiv 2402.11753; RAF basic-T layout |
| source | combined — user-seed #1 corrected + frame-agent (3-frame convergence) |
| confidence | 85 |
| complexity | Med |
| axis | A3 Visual form selection |
| status | Unexplored |

### 6. Read mode from the operator's prompt, not from the repository's files

Committed per-repo settings carry only what file structure can detect; the orchestration-versus-direct-ops
split is read from what the operator just typed.

Content-type detection is clean and stays in settings: `constitution.md` marks agent-governance,
`.claude-plugin/` marks plugin development, `ansible/` marks infrastructure. Mode is not detectable —
`.saga/` exists in a repo showing almost no orchestration usage, and `talaria`'s signature will stop
firing once it ships code. The two human prompt modes present in every repo — approval/continuation
and status check — carry the signal reliably.

This is seed #4 with its mechanism corrected rather than its intent rejected. It avoids the worst
failure available here: the wrong style loads silently and the operator has no way to tell. Guessing
mode wrong from a prompt costs one turn; guessing wrong from a committed file costs every turn until
someone notices.

Prompt-mode classification is itself a heuristic, and it puts a conditional inside the style body
rather than in configuration where it would be inspectable.

| field | value |
|-------|-------|
| basis | `direct:` "detection is the weak link"; the `.saga/` false positive in `infiquetra-ansible-collections`; `talaria`'s temporal signature; two prompt modes in every repo |
| source | combined — user-seed #4 corrected + frame-agent (4-frame convergence) |
| confidence | 88 |
| complexity | Low |
| axis | A4 Style architecture and lifecycle |
| status | Unexplored |

### 7. A style-file contract: shared base, locked flag, and a placard for what is suppressed

Every style declares what it removes, keeps the coding instructions explicitly, and carries the shared
rules verbatim — enforced by test, not by discipline.

**Mechanism settled 2026-08-07: authored files plus a byte-identity test.** Each style file contains
the shared block verbatim; a test asserts every file's block matches a fixture byte-for-byte, that
`keep-coding-instructions: true` is written explicitly rather than left to default, and that the
suppression placard section is present. No generator, no build step. A propagate script is added only
if the style count grows.

`keep-coding-instructions` defaults to false, and false silently strips Claude Code's guidance on
scoping changes, writing comments, and verifying work — the highest-confidence risk found, from
Anthropic's own documentation. Aviation's Minimum Equipment List is the matching discipline: an
aircraft flies with equipment inoperative only when the item is named, the compensating procedure is
written, and the degraded state is placarded where the crew sees it.

Whatever ships must be a plain Markdown file either way, since there is no build step in the loading
path — so "generated versus authored" was only ever a question about the authoring workflow. The test
is what prevents drift in either design. The rejected build-step option was cheaper to edit but
created a class of bug where editing a shipped file gets silently reverted on the next build.

| field | value |
|-------|-------|
| basis | `direct:` binary 2.1.224 confirms both frontmatter flags; Anthropic docs confirm the silent removal · `external:` 14 CFR 91.213, Minimum Equipment List |
| source | frame-agent (4-frame convergence, split on mechanism; fork resolved by operator) |
| confidence | 93 |
| complexity | Med |
| axis | A4 Style architecture and lifecycle |
| status | Unexplored |

### 8. Verification: snapshot the baseline now, commit the scorer, give each style a tell

Answer "is this working?" with a number and a grep rather than an impression.

Three parts. Snapshot today's measurements as the pre-change baseline — **that window closes the
moment a style ships**, because the corpus is contaminated afterward. Commit the counting scripts this
run produced so every future change answers "did this help?" mechanically. Give each style a
distinctive literal string it emits and no other style does.

The tell has proof behind it: this research pass identified which style was active by counting the
`★ Insight` box (315 main-thread against 7 subagent), and that accidental marker supplied one of the
two independent proofs that styles do not reach subagents. The operator's standing rule is that
"fixed" needs a confirming signal, and a style change has none today. It matters more under per-repo
selection, whose failure mode is silently getting the wrong style rather than getting none.

The cost is a visible marker on every turn, and a commitment to maintain test infrastructure for
prompt text.

| field | value |
|-------|-------|
| basis | `direct:` baselines measured across 2,530 files; the 315-against-7 fingerprint; `/output-style` removed in v2.1.91 · `external:` green fluorescent protein as reporter, Nobel Chemistry 2008 |
| source | frame-agent (4-frame convergence) |
| confidence | 90 |
| complexity | Med |
| axis | A4 Style architecture and lifecycle |
| status | Unexplored |

### 9. Split the rules by reach, not by category

Word-level rules stay in CLAUDE.md because it reaches subagents; turn-shape rules move to the style
because they only mean something in the main thread.

This qualifies settled decision 3. CLAUDE.md loads for the main thread and subagents alike; a style
reaches only the main thread. Applied uniformly, absorbing presentation into styles would drop "gloss
every acronym on first use" and "name the referent before the identifier" from near-total coverage to
43%.

The partition is principled rather than arbitrary, which is what makes it durable. A future author
applies it by asking one question without re-reading this research: does this rule mean anything to an
agent whose output is consumed by another agent? Opening with a verdict and closing with an ask is
meaningless in a subagent's return value; naming a thing before its identifier is not.

It partially walks back the clean split the operator chose, and leaves CLAUDE.md carrying presentation
content rather than slimming to pure policy.

| field | value |
|-------|-------|
| basis | `direct:` two independent reach proofs (98:2 fingerprint; `repl_main_thread` against `agent:custom` namespacing); the Plain English section is ratified global policy from 2026-07-20 |
| source | frame-agent |
| confidence | 88 |
| complexity | Low |
| axis | A5 Reach beyond the main thread |
| status | Unexplored |

### 10. The subagent seam: the parent is a copy desk, and the assignment carries the contract

The main thread never pastes a subagent payload verbatim, and every spawn prompt states the return
format.

Two controls, both needed. **Desk control:** a subagent return is source material, not output — quote
at most a few contiguous lines and only when the exact text is load-bearing, never emit a raw payload
as the body of a reply, open with the main thread's own verdict rather than the subagent's. **Source
control:** a fixed presentation contract stamped into every spawn prompt, plus a shared preamble in
`~/.claude/agents/`, which the work configuration already symlinks — one edit governs both
configurations and it can ship before the plugin does.

Newsrooms do not print wire copy raw; a desk rewrites it into one voice, and the reporter in the field
is not responsible for house style. This targets the single worst measured message in the corpus — a
12,347-character block of literal unformatted JSON, a subagent findings payload relayed undigested. It
also relocates the Mermaid complaint to where the 119 occurrences actually live.

The desk rule needs a carve-out for cases where verbatim is correct (exact error strings, diff hunks),
and the agent preamble duplicates a block across N definition files — the same byte-identity test from
survivor 7 can cover both.

| field | value |
|-------|-------|
| basis | `direct:` 57% of assistant text is subagent-generated; the 12,347-character JSON relay; `agents/` symlink verified · `external:` newsroom wire-desk practice; Master's Standing Orders |
| source | combined — frame-agent (4-frame convergence) + user-seed #1 relocated |
| confidence | 92 |
| complexity | Med |
| axis | A5 Reach beyond the main thread |
| status | Unexplored |

## Did not survive (revivable)

Explicit rejection is the quality mechanism. Cut ideas keep stable ids so they can be revived, which
re-enters the Phase 3 filter with new evidence. Never renumber on a status change.

| id | title | summary | reason | status |
|----|-------|---------|--------|--------|
| R1 | Seed #6 — search prior art | Find external prior art to seed the ideas | Process instruction, not a candidate; executed in grounding and cited across six survivors | rejected |
| R2 | Seed #1 as stated — ban Mermaid in the style | Stop emitting Mermaid in the terminal | Premise not supported at the stated surface (7 of 16,029); a style rule taxes every turn to fix 0.04%. Intent survives in survivors 5 and 10 | rejected |
| R3 | Seed #2 as stated — pictures over a mountain of text | Prefer visuals to long prose | Too vague to action; measured "mountain of text" is 1.16% (corrected 2026-08-07, see note below) and the worst case was undigested relay, not verbosity. Intent survives in survivors 4, 5, 10 | rejected |
| R4 | Seed #3 as stated — fewer abbreviations and line references | Reduce shorthand and `path:line` density | Already ratified policy in CLAUDE.md; restating adds nothing. Enforceable form is survivor 3 | rejected |
| R5 | Seed #4 as stated — styles by repository contents | Different styles per repo content type | Mechanism contradicted: Bash is the plurality tool in every repo (57-84%) and two unrelated repos have near-identical profiles. Corrected form is survivor 6 | rejected |
| R6 | Run bare Default for two weeks as a control | Switch off Explanatory, re-measure, author only rules that survive removal | Could invalidate the other survivors, but is a sequencing decision that delays the deliverable; survivor 8's baseline snapshot captures most of the value without the wait | rejected |
| R7 | Prune the Plain English rules before absorbing | Drop the three rules with no traced failure behind them | Needs an operator ruling on ratified text; partly superseded by survivor 9, which changes which rules move at all | rejected |
| R8 | Few-shot pairs from the operator's own transcripts | Embed real before/after response pairs instead of prose rules | An authoring technique for whatever rules survive, not a rule itself; folds into how survivors 1-5 get written | rejected |
| R9 | Delete the `★ Insight` callout box | Ban box-drawing except inside real diagrams | Duplicates a stronger idea: survivor 5 permits box-drawing only as file-tree connectors, retiring the callout by construction | rejected |
| R10 | The accumulating gloss ledger | First gloss of a term is written to a repo-local glossary and reused | Requires a style to write files as a side effect of a formatting rule — a new behavior category with unclear cost; partly redundant with survivor 9 | rejected |
| R11 | Say the ask twice (truncation insurance) | Name the decision in the opening verdict, restate it as the closing line | Traced truncation is 1 of 9 and the redundancy taxes every long turn; survivor 1's ownership line partly covers it | rejected |
| R12 | Evidence grade on the verdict sentence | Mark each verdict verified / inferred / unknown | Verification callouts are ~0 in the friction data, so the evidenced need is weak; sits on the policy/presentation line survivor 9 redraws | rejected |
| R13 | User-level default, commit only exceptions | Set the base style once per config; decide against `force-for-plugin` | Packaging decision rather than an idea; below the meeting-test bar alone. Folds into survivor 6 | rejected |
| R14 | Unify with saga's formatting authority | Derive the style base and `formatting-style.md` from one source | Real governance question, but about an existing artifact rather than a style design idea; low novelty | rejected |
| R15 | Two-identifiers-per-paragraph density cap | Cap bare identifiers, overflow to a table | Threshold is an invented number with no measured basis; the qualitative rule survives inside survivor 3 | rejected |

**Rejection summary.** 67 raw candidates became ~22 distinct ideas after dedupe, then 10 survivors.
Five of the fifteen cuts are operator seeds — four rejected as stated because measurement contradicted
their mechanism or premise, with intent carried into named survivors rather than dropped. Four (R6,
R7, R8, R10) are strong ideas cut on sequencing or scope rather than quality and are the most likely
revival candidates. Axis A2 consolidated into a single survivor rather than spreading thin —
deliberate concentration, not a coverage gap. No axis has zero survivors.

## Co-ideation log

Seeds were passed INTO the Phase 2 frame agents to build on, challenge, or combine, AND entered the
merged pool facing the identical critique. Every frame prompt stated explicitly that the evidence
contradicts seed #1 and qualifies seed #4, and that challenging a seed on evidence was high-value work.

| source | entered | idea / seed | outcome |
|--------|---------|-------------|---------|
| user-seed | Phase 0 | #1 Mermaid instead of ASCII in the CLI | Cut as stated → R2 (premise unsupported at that surface); intent survives as survivor 5 (destination-keyed syntax) and survivor 10 (relay contract) |
| user-seed | Phase 0 | #2 pictures, graphs, tables over a mountain of text | Cut as stated → R3 (too vague; 1.16% measured, corrected from 0.25%); reframed by 3 frames as undigested relay; survives as survivors 4, 5, 10 |
| user-seed | Phase 0 | #3 excessive abbreviations and line references | Cut as stated → R4 (already ratified policy); enforceable form survives as survivor 3 |
| user-seed | Phase 0 | #4 more than one style depending on repo contents | Cut as stated → R5 (content type does not drive interaction); corrected mechanism survives as survivor 6 |
| user-seed | Phase 0 | #5 end-of-turn summary of what is complete and next | Survived as **#1**, corrected in mechanism — state declaration and branch-list ask rather than a summary block |
| user-seed | Phase 0 | #6 search for prior art | Cut → R1 (process instruction); executed in grounding, cited across six survivors |
| frame-agent | Phase 2 | Frame 1 pain & friction, 11 candidates | 3 into survivors 1, 6, 10 |
| frame-agent | Phase 2 | Frame 2 inversion & removal, 12 candidates | 2 into survivors 2, 7; R6, R7, R9 cut |
| frame-agent | Phase 2 | Frame 3 assumption-breaking, 11 candidates | 3 into survivors 1, 6, 8; R8 cut |
| frame-agent | Phase 2 | Frame 4 leverage & compounding, 12 candidates | **Survivor 9 originated here** (split by reach) plus 7, 8; R10, R13, R14 cut |
| frame-agent | Phase 2 | Frame 5 cross-domain analogy, 11 candidates | Strongest external basis in the run — I-PASS, nuclear turnover, FRAGO, ATC phraseology, sterile cockpit, basic-T, MEL, GFP, wire desk. Into survivors 1, 2, 3, 4, 5, 7, 8, 10 |
| frame-agent | Phase 2 | Frame 6 constraint-flipping, 10 candidates | Line-local criterion and destination-keyed syntax into survivor 5; agent preamble into survivor 10; shared-base fork into survivor 7 |

## Settled after publication

**R7 — pruning the ratified Plain English rules: rejected. Settled 2026-08-07.** The operator's
ruling is that nothing gets pruned; all seven Plain English rules stay exactly as written. Three
have a traced failure behind them (name the thing, expand acronyms, lead with the plain claim) and
three do not (situate before detail, no invented shorthand, no jargon-stacking), but absence of a
traced failure in a 35-day window is not evidence a rule is idle — it is equally consistent with the
rule doing its job. R7 is closed and is no longer revivable on the "unevidenced" argument.

Consequence for survivor 9: the reach partition now has to place seven rules, not four. Every one of
them is word-level, so on survivor 9's own logic every one of them stays in `CLAUDE.md`, which
reaches subagents, rather than moving into a style, which does not.

**Measurement correction — mountain of text was 0.25%, is actually 1.16%. Corrected 2026-08-07.**
The original figure counted 40 messages, but 40 was a `head -40` display cap in the throwaway script,
not the number of messages over a length threshold. Recomputed with an actual 4,000-character
threshold, the rate is 172 of 14,787 main-thread messages. This does not revive R3, which was cut
primarily for being too vague to action rather than for the size of the number. Full reconciliation:
`docs/measurements/2026-08-07-baseline.md`.

**Survivor 8's baseline — captured 2026-08-07, before any style shipped.** The instrument is
`tools/output_style_scorer.py` with 29 tests in `tests/test_output_style_scorer.py`; the numbers are
in `docs/measurements/2026-08-07-baseline.{json,md}`. The time-sensitive half of survivor 8 is done.
The scorer, its tests, the baseline, and this document moved into `infiquetra-claude-plugins` on
2026-08-07 and are now version-controlled alongside the plugin they verify.

## Open questions carried forward

1. **R6 — the bare-Default control run.** Every measurement here was taken while Explanatory was
   active, so it sits on both sides of the analysis. Two weeks on Default would separate problems the
   style caused from problems it failed to prevent, at the cost of delaying everything.
2. **The committed-behavior-key precedent.** Survivor 6 narrows what per-repo settings carry, but a
   committed `outputStyle` key would still be the first behavior key in any of these repos.
3. **The plugin's name.** Permanent, and it appears in the marketplace listing beside `saga`,
   `deploy`, and `fleet-core`. Recommendation on the table: `house-style`.

## Process note

Two frame agents completed their work but their return messages were lost in delivery; both were
recovered intact from their subagent transcripts, and a file-write requirement was added to every
subsequent frame. No candidate was lost. All six frame outputs are preserved under
`docs/ideation/2026-08-07-output-styles-run/`.
