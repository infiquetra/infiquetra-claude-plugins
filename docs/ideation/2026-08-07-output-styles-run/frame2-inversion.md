Read in full. Here are my candidates through the inversion / removal / automation lens.

---

## 1. Box-drawing is reserved for pictures, and the Insight callout is deleted

**summary** — Today the operator's terminal draws a bordered box on nearly every turn, and 91 percent of the time that box contains no picture at all. Ban box-drawing characters (`─ │ ┌ ╰ ★`) for emphasis, headers, callouts, or separators, and permit them only inside an actual diagram. The visual channel then carries one meaning: a box on screen means "here is a picture." No new formatting rule is added; one is withdrawn.

**axis** — A3 Visual form selection

**basis** — `direct:` "Box-drawing characters: 341 messages — but 311 (91%) are the `★ Insight` callout box from the currently-active Explanatory style, not diagrams. Genuine diagrams: ~30 (0.19%)."

**why_it_matters** — The operator asked for pictures. He is currently getting borders at a 10:1 ratio over pictures, which is exactly the prior-art anti-pattern "overusing borders until content becomes hard to scan." Making the border rare is what makes a diagram legible when one finally appears; adding more diagram rules on top of a screen already full of boxes does nothing.

**meeting_test** — It reverses a decoration the operator has seen 311 times in 35 days, and the team has to decide whether the box was ever carrying information.

---

## 2. Last-line law: a turn ends on an ask, or it ends

**summary** — Make the final line structurally constrained rather than adding a summary block. The last line of any turn above the trivial threshold must be a single concrete question or a statement of what the assistant is waiting on. Nothing declarative may follow it — no caveat, no "note that," no additional finding, no offer of three options. This is a deletion rule: whatever was trailing after the ask gets cut, not rewritten.

**axis** — A1 Turn shape

**basis** — `direct:` "10 of 10 end with a single explicit concrete ask"; failure taxonomy item 1, "No closing next-step/ask — 5 of 9. Message ends on a declarative fact or aside."

**why_it_matters** — This is the single highest-evidence finding in the grounding: it appears on both sides of the ledger, as the top failure mode and as a perfect-score property of satisfied replies. It is also the cheapest rule to state and the easiest to check by eye. Everything else in the style is speculative by comparison.

**meeting_test** — It is the one rule the measurement would justify shipping even if every other candidate is rejected, so the team should decide whether it is stated as a prohibition or a preference.

---

## 3. Challenge to seed #5: the closing is a subtraction, not a summary

**summary** — The operator asked for an end-of-turn summary of "what's complete and what's next." The evidence does not support a block; it supports one line. Define the closing by removing everything already visible: the statusline redraws model, effort, context used, session and month-to-date cost, git branch, pull request review state, and cloud context every ten seconds. A closing line may contain only what the turn did, what it found, and what remains — and nothing that is already on the operator's screen.

**axis** — A1 Turn shape

**basis** — `direct:` seed #5 ("to often at the end of the output I have no idea what is status... some sort of summary with: what's complete and whats next") set against "The statusline already renders every 10s... => an end-of-turn summary must NOT restate any of these."

**why_it_matters** — Seed #5 is a real complaint with a wrong remedy attached. The satisfied replies did not carry status blocks; they carried a verdict at the top and an ask at the bottom. Granting the operator a literal two-part summary block would add text to a corpus where the complaint replies were already the longer ones. The honest answer is that the operator wants to know where things stand, and a block is not how that gets delivered.

**meeting_test** — It tells the operator his own seed is directionally right and mechanically wrong, which is exactly the kind of call a team should make out loud rather than quietly.

---

## 4. Short turns are exempt from every turn-shape rule

**summary** — Gate the entire turn-shape section behind a threshold. Below roughly 300 characters, or when the turn is a single answer to a single factual question, the response is bare: no verdict line, no heading, no closing ask, no structure of any kind. The rules switch on only for the long tail. Rather than tuning the style to the typical turn, remove the typical turn from the style's jurisdiction.

**axis** — A1 Turn shape

**basis** — `direct:` "Length is bimodal: median 142 chars, p75 292, p90 1,658, max 26,994. A style tuned to the median will look fine daily and still fail the 10% of turns that matter most."

**why_it_matters** — Read the other direction, the same measurement is a warning: three quarters of turns are short, and a mandatory verdict-plus-ask wrapper would triple the length of a one-line answer. That is how a style designed to reduce friction becomes a new source of it. An explicit exemption is what lets the long-turn rules be strict, because they no longer have to be safe for a two-sentence reply.

**meeting_test** — Every other turn-shape candidate is unsafe to ship without deciding this, so the threshold needs a number agreed in the room.

---

## 5. Identifiers are appositives, never nouns

**summary** — State the rule as a grammatical prohibition instead of an instruction to be helpful. A commit hash, issue number, pull request number, branch name, test name, or file path may never serve as the subject or object of a sentence. It may only sit in apposition to a real noun that names what it is. "458b983 is unreviewed" is malformed; "the latest commit (458b983) is unreviewed" is well-formed. The check is syntactic, so it is applied by deletion and reinsertion rather than by judgment.

**axis** — A2 Word-level discipline

**basis** — `direct:` failure taxonomy item 3, "Bare identifier as a noun — 2 of 9 (one message carried 15+ bare issue numbers)," and the ratified rule in the operator's global instructions: "A bare identifier used as a noun... means nothing on its own."

**why_it_matters** — The ratified version tells the model to add a name, which is an aspiration the model can believe it satisfied while producing the same output. The grammatical version has a mechanical test with no room for good intentions, and it is greppable, which means the regression harness in candidate 10 can actually assert it. Turning a preference into a syntax rule is what makes it survive contact with a busy turn.

**meeting_test** — It converts one of the operator's own ratified rules into an enforceable form, and the team should decide whether the other six rules get the same treatment.

---

## 6. Delete before you gloss

**summary** — Invert the expand-every-term rule. When a term of art needs explanation, the first move is to try removing it: if the sentence still says the same thing without it, the term goes and no gloss is written. Only a term that names a real object with no plain-English equivalent survives, and then it is expanded. Academic register words — vacuous, orthogonal, canonical, non-trivial — have no object behind them and are always deleted, never defined.

**axis** — A2 Word-level discipline

**basis** — `direct:` 2026-07-26, campps-context-library: "stop saying \"vacuous\" and be more descriptive... more like a developer, less like an academic."

**why_it_matters** — The operator did not ask for "vacuous" to be defined. He asked for it to stop. A gloss rule preserves the jargon and adds words around it, which is the additive reflex this frame exists to catch. Deletion is strictly shorter and strictly clearer, and it separates the two cases the current rule conflates: an acronym that names a thing needs expanding, an adjective that flatters the writer needs removing.

**meeting_test** — It sets a general policy on how the style treats every hard word, which governs a large fraction of the word-level section's eventual content.

---

## 7. Prune the Plain English rules before absorbing them

**summary** — The migration of presentation rules into the style is settled, but which rules make the trip is not. Three of the seven Plain English rules have a traced failure behind them: name the thing rather than gesture at it, expand codes and acronyms, and lead with the plain-language claim. Three have no measured antecedent at all: situate before you detail, no invented shorthand, and never stack two pieces of jargon in one clause. Absorb the rules with evidence and drop the rest, revivable if a future complaint traces to them.

**axis** — A2 Word-level discipline

**basis** — `direct:` the failure taxonomy maps antecedents onto rules 2, 3 and 6 ("Unglossed term of art — 2 of 9"; "Bare identifier as a noun — 2 of 9"; "Dense technical wall, no plain framing — 2 of 9" plus "10 of 10 open with a bolded one-sentence plain-language verdict"), and no traced complaint maps onto rules 1, 4 or 5.

**why_it_matters** — Absorption is being treated as a move operation, and a move quietly ratifies every rule it carries. These rules were written in one sitting after a single sharp complaint, and prompt budget spent on a rule with no antecedent is budget not spent on the two rules that appear in every satisfied reply. The grounding pass produced the evidence to make this call; not making it wastes the pass.

**meeting_test** — It proposes deleting text the operator wrote himself and marked as ratified policy, which needs his explicit agreement rather than a silent omission.

---

## 8. Challenge to seed #1: the mermaid rule does not belong in an output style

**summary** — The operator's first seed asks the style to stop emitting mermaid in the terminal. At the main-thread level the behavior is essentially absent: seven messages out of sixteen thousand. The volume lives in two places a style cannot reach — subagent replies, and the contents of files Claude writes. Drop the mermaid rule from the style entirely and place it where it bites: a file-authoring rule about diagram format in generated documents, which is policy about artifacts rather than about the conversation's presentation, and therefore stays outside the presentation-absorption constraint.

**axis** — A3 Visual form selection

**basis** — `direct:` "```mermaid``` fenced block in rendered text: 7 messages (0.04%) — seed #1's premise is NOT supported at the main-thread level. Mermaid concentrates in subagent traffic (119) and in file contents Claude reads/writes (~23 of 30 assistant-line hits are Write/Edit payloads)."

**why_it_matters** — A style rule is a permanent tax on every turn. Paying it to suppress a behavior that occurs on four turns in ten thousand is the worst return in the whole candidate set, and it would leave the operator believing the problem was handled while the 119 subagent occurrences continue. The complaint is real; the location is wrong.

**meeting_test** — It tells the operator his most concrete seed is aimed at the wrong surface, backed by a count, and the team has to decide where the rule actually goes.

---

## 9. Diagrams are default-off and condition-triggered

**summary** — Remove the assistant's authority to decide a picture would be nice. A diagram appears only when a named condition fires: the operator asks where things stand, the operator has just signalled he is lost or has misunderstood, or the content is a containment or dependency relationship among more than three named things. Outside those conditions, no diagram, regardless of how well it would illustrate the point. Restrict the permitted forms to the two the corpus shows actually working — file trees and small dependency chains — and forbid the forms with no good text rendering.

**axis** — A3 Visual form selection

**basis** — `direct:` "The operator asked for 'pictures' five separate times across the window, always when already lost. TENSION RESOLVED: the objection is to an UNREQUESTED diagram in a routine update, not to diagrams. This is a rule about TRIGGERING, not about format," combined with "Genuine ASCII diagram shapes actually in use: file trees and small dependency-chain graphs. Not flowcharts, not sequence diagrams, not state machines."

**why_it_matters** — Seeds #1 and #2 look contradictory — stop drawing, draw more — and both are true under different conditions. Any style that resolves them by tuning format will keep getting it wrong, because format was never the variable. Making the trigger explicit and the default off means the operator gets a picture exactly when he wanted one and never when he did not, and it sidesteps the measured weakness of language models at spatial text by simply drawing far less.

**meeting_test** — The trigger list has to be enumerated by hand and agreed, because a wrong or vague condition reproduces the original complaint.

---

## 10. Subtract first: run bare Default for two weeks before authoring anything

**summary** — Every friction measurement in the grounding was taken while the Explanatory style was active. Before authoring a library, switch both configurations to Default, keep the terminal otherwise unchanged, and re-run the same counts after two weeks. The result establishes which complaints the current style caused and which it merely failed to prevent. Only rules that address friction surviving the removal get authored.

**axis** — A4 Style architecture and lifecycle

**basis** — `reasoned:` The corpus is not a neutral sample of Claude's behavior — it is a sample of Claude under Explanatory, a style that mandates a teaching callout on every turn regardless of whether the turn has anything to teach. Explanatory therefore appears on both sides of the analysis: as the thing being measured and as a likely cause of what was measured. The 311 insight boxes prove it fires unconditionally. Without a no-style baseline, there is no way to distinguish a rule that fixes a real problem from a rule that patches damage the previous style did, and the second kind of rule becomes permanent overhead the moment the first style is removed. The subtraction is free, reversible in one setting change, and produces the only control group this project will ever get.

**why_it_matters** — The whole effort rests on the assumption that the right response to bad output is more instructions. That assumption is testable in two weeks at zero cost, and it is the only candidate here that could invalidate the others rather than compete with them.

**meeting_test** — It proposes delaying the deliverable to gather a control, which is a scheduling and confidence tradeoff only the operator can settle.

---

## 11. Automated conformance: a frontmatter lint and a transcript regression harness

**summary** — Answer "how do I know the style is working" with checks rather than impressions. Two automated pieces live in the plugin repository. A static lint fails the build if any style file omits `keep-coding-instructions: true`, since the default is false and silently strips Claude Code's built-in engineering instructions. A behavioral harness re-runs the counting scripts this research already produced over recent transcripts and asserts thresholds: box-drawing outside diagrams near zero, turns ending without an ask below a bound, bare identifiers used as nouns trending down.

**axis** — A4 Style architecture and lifecycle

**basis** — `direct:` "`keep-coding-instructions: false` is the DEFAULT and it SILENTLY REMOVES Claude Code's built-in software-engineering instructions... Highest-confidence risk in the whole research pass," together with the measurement set already computed over 2,530 transcript files (341 box-drawing messages, 7 mermaid, 597 path:line, 3 of 395 sessions ending with a status signal).

**why_it_matters** — Prompt rules have no failure signal. A rule can silently stop working after a model update, a style edit, or a plugin merge, and the only symptom is the operator getting annoyed again three weeks later. The frontmatter risk is worse: forgetting one line degrades how Claude scopes and verifies code, with no error and no visible change. The measurement harness already exists as scratch work from this pass; promoting it to a committed check is the difference between a style that is believed to work and one that is known to.

**meeting_test** — It commits the team to maintaining test infrastructure for prompt text, which is unusual enough to need an explicit yes.

---

## 12. Take orchestration mode out of the selection problem and read it from the prompt

**summary** — Per-repo selection stays committed as decided, but it should only carry the distinctions that file structure can actually detect: a governance repo, a plugin repo, an infrastructure repo. The orchestration-versus-direct-ops split has no reliable file signature and should be removed from selection entirely. Instead, every style reads it from the inbound turn, because the operator's own prompt already declares it — a status check ("where are we with X") and an approval or continuation ("go ahead") are the two modes present in every repo.

**axis** — A4 Style architecture and lifecycle

**basis** — `direct:` "DETECTION IS THE WEAK LINK... orchestration-mode has NO reliable file-presence rule — `.saga/` exists in ansible-collections too, which shows almost no orchestration usage. Mode must be read from live tool-use mix, not repo structure. `talaria`'s ADR signature is temporal and will silently stop firing once it ships code," set against "Human prompt modes everywhere: approval/continuation and status check."

**why_it_matters** — This is the qualification seed #4 needs. Repo shape is a real signal but a partial one, and building selection on a detector known to misfire produces the worst failure available here: the wrong style loads silently, and the operator has no way to tell. The prompt mode is a signal that is present on every turn, requires no detection heuristic, cannot go stale when a repo evolves, and is the one the operator is already sending deliberately.

**meeting_test** — It narrows what the settled per-repo selection is allowed to decide, so the team needs to agree on the boundary before any style file is scoped.

---

Twelve rather than eight; the frame turned out to have more grounded material behind it than expected. Candidates 3, 7 and 8 are the direct challenges to operator seeds, and candidate 10 is the one that could invalidate the rest.
