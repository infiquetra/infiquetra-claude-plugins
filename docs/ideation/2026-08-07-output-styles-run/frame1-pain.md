## Frame 1 — Pain & Friction: 11 ideation candidates

---

### 1. Terminal-Position Prohibition

**summary** The counter-sample's discriminator is not that good replies *contain* an ask — it is that nothing declarative trails after it. Encode this as a negative rule owning the final line: the last line of every response is either one concrete ask or one explicit "nothing needed from you," and a fixed prohibition list names what may never sit there — a new finding, a caveat, an aside, a bare file path, or anything the statusline already paints (model, effort level, context-window percentage, session/today/month-to-date cost, git branch, PR review state).

**axis** A1 Turn shape

**basis** `direct:` "10 of 10 end with a single explicit concrete ask"; "The discriminator is structural placement: verdict-first, ask-last, nothing declarative trailing after the ask"; failure taxonomy item 1, "No closing next-step/ask — 5 of 9. Message ends on a declarative fact or aside." Bounded by the measured statusline inventory: "an end-of-turn summary must NOT restate any of these."

**why_it_matters** The reflexive answer to "only 3 of 395 sessions end with a status signal" is to bolt a summary block onto the end. The evidence says that would not fix it — a summary block that trails one more caveat still reproduces failure 1. The rule that discriminates is a prohibition on the terminal slot, not an addition to it. The statusline inventory then bounds the closing so it stays cheap: only what the turn *did*, what it *found*, and what *remains*.

**meeting_test** Whether a prompt can enforce a negative rule about a position at all, versus needing a positive template, is a real design argument worth having in the room.

---

### 2. Say the Ask Twice — Truncation Insurance

**summary** Ask-last is the strongest structural rule in the corpus and it is also precisely the part of a response that truncation destroys. For any response past roughly the 75th-percentile length, the decision being requested is named inside the opening verdict sentence and then restated concretely as the terminal line. Short responses keep the single terminal ask.

**axis** A1 Turn shape

**basis** `direct:` failure taxonomy item 6 — "Truncated/incomplete delivery — 1 of 9. Message ended on 'Two scope calls that would change it materially, and they're yours:' and the text stopped. Operator: 'output stopped'." Combined with the measured length bimodality: median 142 chars, p75 292, p90 1,658, max 26,994.

**why_it_matters** These are two separate findings in the corpus that quietly contradict each other, and nobody has named the collision. Verdict-first is partly a truncation insurance policy — if the stream dies, the operator still has the answer. Ask-last has no such protection, and the one traced truncation failure ate exactly the ask. Controlled redundancy resolves it, and the p75 threshold keeps the cost off the 75% of turns that are two sentences long.

**meeting_test** The redundancy spends a clause on every long turn and may read as repetitive to a reader who is not lost; whether that trade is worth it is a judgment call for the team.

---

### 3. Branch on the Prompt, Not on the Filesystem

**summary** Seed 4 asks for per-repo styles, but the research found mode — not content — is the real separator and that orchestration mode has no reliable file-presence signature. Branch instead on the shape of the incoming human prompt, which is always available. A status-check prompt ("where are we with X") gets a fixed four-slot skeleton: what is done, what is in flight, what is blocked and on whom, the one decision needed now — and no new investigation launched in that same turn.

**axis** A1 Turn shape

**basis** `direct:` "DETECTION IS THE WEAK LINK... orchestration-mode has NO reliable file-presence rule"; "Human prompt modes everywhere: approval/continuation ('go ahead', 'approved') and status check ('where are we with X')"; and the 2026-07-27 work quote: "where are we? can you close this outcome yet? you never give me any next steps... I rarely understand what you are telling me, to much extra info and not enough of what is important right now."

**why_it_matters** This is a direct challenge to seed 4's mechanism while honoring its intent. The operator wants behavior to vary by situation; the evidence says situation is not readable from repo structure and that `talaria`'s ADR-gated signature will silently stop firing once it ships code. A prompt-shape branch has no detection weakness, no staleness, and no dependency on committed settings — and it answers the single loudest complaint in the corpus, which was itself a status-check prompt that got a work response.

**meeting_test** "No new work on a status check" is contestable — the operator may well want a status question to trigger a fresh probe rather than a recital of stale state.

---

### 4. Ship the Gloss Rule With Its Exemption List

**summary** CLAUDE.md already mandates expanding every acronym on first use, but the measurement shows the trigger fires on roughly 20% of messages and about half the top hits are `NOT`, `DONE`, `PASS`, `GET`, `POST`, `HEAD` — emphasis-caps and HTTP verbs. Carry both measured lists inside the style text: the real offenders needing a gloss (ADR, HITL, DAG, COPPA, SOUL, BP, REG, DR, TUI, DRIFT, INV, SKILL) and the exemptions that must never trigger it.

**axis** A2 Word-level discipline

**basis** `direct:` "All-caps 2-5 letter tokens: 20% of messages — but ~half the top offenders are `NOT`, `DONE`, `PASS`, `GET`, `POST`, `HEAD`... Genuine internal terms needing a gloss: ADR, HITL, DAG, COPPA, SOUL, BP, REG, DR, TUI, DRIFT, INV, SKILL." Builds on the existing ratified CLAUDE.md rule 3, which already exempts API, URL, CI, PR.

**why_it_matters** A rule that fires constantly and is mostly wrong is a rule that gets tuned out — by a model and by a reader. The failure of the current CLAUDE.md rule is not that it is absent, it is that it is imprecise, and imprecision is why "unglossed term of art" still shows up in 2 of 9 traced complaints despite ratified policy. Precision is the entire delta between a rule that exists and a rule that executes.

**meeting_test** A measured offender list is a snapshot that will rot; whether it gets regenerated periodically or frozen is a maintenance decision the team should make deliberately.

---

### 5. Identifier Density Cap With Table Overflow

**summary** Cap bare identifiers at two per paragraph, each preceded by what it is. Past that cap, they move out of prose into a table with a name column. Applies to issue numbers, commit hashes, PR numbers, branch names, and `path:line` references alike.

**axis** A2 Word-level discipline

**basis** `direct:` failure taxonomy item 3 — "Bare identifier as a noun — 2 of 9 (one message carried 15+ bare issue numbers)"; "Bare commit-hash-shaped hex with no nearby explanatory word: ~7.9% of messages"; "`path:line` references: 597 messages (3.72%), avg 1.79 per message when present, max 25"; seed 3, "excessive abreviations or referencing lines of code don't help."

**why_it_matters** CLAUDE.md's naming rule is unbounded, and obeying it literally on a message carrying 15 issue numbers produces exactly the dense wall the operator objects to elsewhere. The density cap is what makes the naming rule survivable, and it turns a table into a functional overflow container rather than decoration. This engages seed 3 directly on a point the operator believed was already handled — the rule is in place, the count says it is still failing, and the missing piece is a threshold.

**meeting_test** Two-per-paragraph is a chosen number, not a measured one; the right threshold is worth arguing rather than assuming.

---

### 6. Choose ASCII Forms by How They Fail, Not by How They Look

**summary** Width drift in ASCII output cannot be prevented by prompting — no validated technique exists. So select permitted forms by their failure mode instead: forms where a misalignment degrades gracefully. Permit file trees, small dependency chains, indented layer stacks, and simple sequence ladders. Forbid boxed dashboards, Gantt charts, and many-node graphs. State the criterion in the style so the reasoning travels with the rule.

**axis** A3 Visual form selection

**basis** `external:` ArtPrompt (ACL 2024, arxiv 2402.11753) measured GPT-4 at 25.19% accuracy on single-character ASCII-art recognition; the research found "NO validated prompt-only technique for preventing width-drift." Safe forms come from RFC 793's 40-year state-machine and sequence convention and from `tree` / `git log --graph`; known-bad forms from "Gantt charts and dense many-node graphs are known-bad."

**why_it_matters** Every ASCII layout guide surfaced — including the IoTeacher zones gist with its named top band, main area, side rail, bottom band — prescribes elaborate boxed structures, and not one carries a drift-prevention technique. The measurement says the model is bad at exactly the spatial reasoning those layouts require. A misaligned pipe in a file tree is still readable; a broken border on a boxed dashboard is garbage. Failure mode is the only selection criterion the evidence actually supports, and it happens to match the two forms already appearing in the operator's real traffic.

**meeting_test** Forbidding boxed dashboards sits in visible tension with seed 2's request for "pictures, graphs, tables," and the team should decide that tension out loud rather than letting the style decide it silently.

---

### 7. The Rule Is About Triggering, Not Format

**summary** Restrict unrequested visuals to two named triggers: the operator signals confusion, or the content is structurally comparative (three or more items sharing two or more attributes, which becomes a table). Response length never triggers a visual. The style carries an explicit note that seed 1's premise does not hold at the main thread, so a mermaid ban there would be aimed at a nearly empty target.

**axis** A3 Visual form selection

**basis** `direct:` "The operator asked for 'pictures' five separate times across the window, always when already lost. TENSION RESOLVED: the objection is to an UNREQUESTED diagram in a routine update, not to diagrams. This is a rule about TRIGGERING, not about format." Against seed 1's premise: "```mermaid``` fenced block in rendered text: 7 messages (0.04%) — seed #1's premise is NOT supported at the main-thread level."

**why_it_matters** Seeds 1 and 2 look contradictory — stop making diagrams, give me more pictures — and a style that tries to satisfy both as format rules will oscillate. They are not contradictory once you see they are about different moments. Encoding the trigger resolves both seeds with one rule, and it stops the style from spending its budget banning something that happens 7 times in 16,029 messages.

**meeting_test** "Three items, two attributes" is an invented threshold and the confusion-signal trigger needs a concrete detection definition — both are exactly the kind of thing a room should nail down.

---

### 8. One Generated Base Block, Asserted by Test

**summary** Output styles have no include mechanism, so the shared base the operator's accepted risk depends on has to be a build-and-test property, not an inheritance property. Keep one base source file, concatenate it into every shipped style at build time, and add a test asserting every style file contains the base block verbatim and declares `keep-coding-instructions: true`. This mirrors the enforcement pattern already working in the operator's own repo.

**axis** A4 Style architecture and lifecycle

**basis** `direct:` settled decision 3 and its accepted risk — "a rule only lives in the active style — switch styles, lose it, unless every style shares a common base"; "`keep-coding-instructions: false` is the DEFAULT and it SILENTLY REMOVES Claude Code's built-in software-engineering instructions... Highest-confidence risk in the whole research pass"; and "`saga/references/formatting-style.md` is a COMPETING, pytest-enforced formatting authority (`tests/test_saga_doc_formatting.py`)."

**why_it_matters** The operator accepted a risk without a mitigation attached, and the mitigation is not exotic — a working precedent for enforcing a formatting authority by test already sits in their own codebase. Borrowing it costs nothing in new concepts. Bundling the `keep-coding-instructions: true` assertion into the same test closes the single highest-confidence risk found in the research, and it closes it in a way that cannot be forgotten when a new style is added six months from now.

**meeting_test** Where the test lives — the plugin repo, a CI job, a pre-commit hook — and whether the plugin marketplace can carry it, is a concrete packaging question the team needs to settle.

---

### 9. Build In a Proof-of-Life Marker

**summary** Each style emits one short, unmistakable marker naming itself. The operator gets a glance-check that the intended style is actually live after `/clear`, and any future transcript analysis can attribute a message to the style that produced it.

**axis** A4 Style architecture and lifecycle

**basis** `direct:` the research's own reach proof — "the `★ Insight` box (rendered only under Explanatory) appears in 315 main-thread vs 7 subagent messages (98:2)"; "Style takes effect only after `/clear` or a new session"; "The `/output-style` slash command was deprecated (v2.1.73) and removed (v2.1.91). The operator runs 2.1.224"; and "Pure praise language ('perfect', 'thanks') is absent from this operator's corpus entirely."

**why_it_matters** With the slash command gone, there is no cheap in-session way to confirm which style is active, and the style only takes effect at a session boundary — so a silent misconfiguration looks identical to a style that is on but ignored. Worse, the corpus contains no positive feedback signal at all: the operator never praises, so the only available evidence a style is working is the absence of complaint, which is unmeasurable in the short term. Verification has to be structural. The whole reach investigation only succeeded because Explanatory happened to leave a fingerprint; making that fingerprint deliberate is the cheapest instrumentation available.

**meeting_test** The marker costs visible noise on every single turn, and whether it survives past an initial rollout window or gets removed once trust is established is worth deciding up front.

---

### 10. Subagent Output Is Raw Material, Never a Deliverable

**summary** The style cannot govern subagents, but it fully governs the boundary where their text enters the operator's view. Put a relay contract in the shared base: never paste a returned payload verbatim, restate the finding as a plain-language verdict in the main thread's own words, convert or drop any returned mermaid and any table too wide for the terminal, and name which agent produced each finding.

**axis** A5 Reach beyond the main thread

**basis** `direct:` "57% of all assistant text is generated outside any output style's reach"; "'Mountain of text' (>4,000 chars, no table/diagram/code): 40 messages (0.25%) — small, BUT one of the three worst was **literal unformatted JSON** (a subagent findings payload, 12,347 chars) dumped into a main-thread reply undigested"; "Mermaid concentrates in subagent traffic (119)"; seed 2's "mountain of text."

**why_it_matters** This reframes what seed 2 is actually complaining about. Only 0.25% of messages are genuinely long-and-unstructured, so volume cannot be the real grievance — but the worst single case was undigested relay. The operator's "mountain of text" means "you handed me your raw materials," not "you wrote a lot." That also explains where the mermaid complaint really comes from: 119 mermaid blocks live in subagent traffic and only 7 reached the main thread, so the rare offender is almost certainly a relay. One boundary rule converts the largest ungovernable surface into a governed one, with no new mechanism required.

**meeting_test** Whether verbatim relay is ever correct — exact error strings, exact command output the operator will paste elsewhere — needs a carve-out the team should define rather than leave to judgment.

---

### 11. Spawn Prompts Carry a Two-Line Presentation Contract

**summary** The style requires that every subagent spawn prompt embed a short presentation contract — verdict first, no mermaid — capped at a couple of lines. This is the only prompt-level lever on the 57% surface, and its context cost is real and stated as part of the proposal.

**axis** A5 Reach beyond the main thread

**basis** `reasoned:` The argument in full. Output styles are namespaced in the binary as `repl_main_thread:outputStyle:<name>`, while agents resolve to a separate `agent:custom` identifier — so no configuration key, plugin flag, or file placement can push a style into a subagent. That is a hard architectural boundary, not a gap to be worked around. The main thread does, however, author every subagent prompt; that prompt text is the only channel it controls into the subagent process. Therefore the only prompt-level influence over 57% of assistant output is text the main thread deliberately embeds at spawn. Two rules earn that space over any others: verdict-first, because it is the corpus's proven discriminator and because a verdict-first return is far cheaper for the main thread to relay under idea 10; and no-mermaid, because 119 of the corpus's mermaid blocks originate here and cleaning them at relay costs more than not generating them. Against this sits a genuine cost — CLAUDE.md's Delegation & Context Economy section explicitly prizes a clean thread, and this adds tokens to every spawn. The cap at two lines is the concession.

**why_it_matters** The alternative is accepting that the majority of assistant text stays ungoverned, which quietly caps the ceiling of this entire effort at 43% of the surface. This is the only mechanism the verified mechanics permit, and it is stronger for naming its own cost rather than hiding it.

**meeting_test** There is a real argument that this belongs in agent definitions rather than an output style — a scope boundary the team should draw explicitly, since drawing it wrong makes the style responsible for something it cannot verify.

---

**Axis coverage:** A1 × 3 (1, 2, 3), A2 × 2 (4, 5), A3 × 2 (6, 7), A4 × 2 (8, 9), A5 × 2 (10, 11).
**Basis mix:** 9 `direct:`, 1 `external:` (6), 1 `reasoned:` (11).
**Seeds engaged:** seed 1 challenged on measurement and rerouted to the relay boundary (7, 10); seed 2 reframed from volume to undigested content (10) and its trigger isolated (7); seed 3 built on with a density threshold and an exemption list (4, 5); seed 4 challenged — its detection mechanism replaced with prompt-shape branching (3); seed 5 built on but inverted from an added summary block to a terminal-position prohibition, bounded by the statusline (1); seed 6's prior art carried into the ASCII selection criterion (6).
