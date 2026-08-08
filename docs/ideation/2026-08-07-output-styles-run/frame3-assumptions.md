Read the grounding summary in full. Here are my candidates from the assumption-breaking and reframing lens.

---

## 1. The style's one hard clause is a stopping condition, not a rendering rule

**summary** — An output style is normally read as a spec for how text looks once it exists. The measured failures say the break happens earlier: the model decides it is finished in the wrong place. Make the load-bearing clause a termination contract — a turn may end in exactly one of three ways (a single concrete ask, an explicit "nothing needed from you, here is what runs next," or a stated block) — and everything else in the style becomes secondary preference. This is checkable by the model before emitting and by a script afterward.

**axis** — A1 Turn shape

**basis** — `direct:` "Turn endings: only 3 of 395 sessions (0.76%) end with any summary/next/status signal." Plus failure mode 6 in the taxonomy, where the message ended on "Two scope calls that would change it materially, and they're yours:" and stopped — operator reply: "output stopped." Plus the counter-sample: "10 of 10 end with a single explicit concrete ask."

**why_it_matters** — The largest failure class (5 of 9 traced complaints) is a message ending on a declarative fact. That is not a formatting defect; a perfectly formatted message can commit it. Reframing the rule as a precondition on *stopping* also catches the truncation failure, which no formatting rule would have caught.

**meeting_test** — It decides whether the style set has one non-negotiable clause or a flat list of equal-weight preferences, which changes how every other accepted idea gets written.

---

## 2. Seed #1 is filed against a surface no output style can reach

**summary** — The operator saw mermaid diagrams in a terminal and was right to object. But mermaid appears in 7 of 16,029 main-thread messages. The diagrams he saw came from subagent output relayed upward or from files being written — both outside any output style's reach. A mermaid clause in a style would measure as compliant while the operator keeps seeing diagrams.

**axis** — A5 Reach beyond the main thread

**basis** — `direct:` "```mermaid``` fenced block in rendered text: 7 messages (0.04%) — seed #1's premise is NOT supported at the main-thread level. Mermaid concentrates in subagent traffic (119) and in file contents Claude reads/writes." Operator quote, 2026-07-17: "you always do that... I am in cli, you waste tokens generating mermaid. stop doing that."

**why_it_matters** — This is the clearest case in the corpus where a stated seed and its effective intervention point sit in different files. Shipping the obvious style clause would be the exact failure the operator's own Validation Discipline warns about: a change that looks like work and cannot move the number.

**meeting_test** — It forces a decision on whether the deliverable is styles only, or styles plus the companion surfaces the plugin can already ship (subagent definitions, hooks).

---

## 3. There is no runtime style inheritance, so the shared base has to be a build step

**summary** — The operator accepted the risk that a rule living only in the active style is lost on switch "unless every style shares a common base." No such base can exist at runtime. Author one `presentation-core.md`, generate every style file from it plus a register-specific tail, and add a test that fails the build if a published style's core block has drifted from source.

**axis** — A4 Style architecture and lifecycle

**basis** — `reasoned:` The argument in full: (a) the verified frontmatter fields are `name`, `description`, `keep-coding-instructions`, `force-for-plugin` — there is no `extends` or include mechanism; (b) plugin loading merges style *lists* via `append`, not style *bodies*, so two styles never combine at load; (c) therefore a common base cannot be a runtime construct, and the only remaining place it can exist is before the files are published; (d) the plugin is already a repo shipped through the `infiquetra-plugins` marketplace, so it already has somewhere to put a generator and a test. Conclusion: the shared base is a build artifact or it does not exist.

**why_it_matters** — It converts a risk the operator accepted verbally into an invariant enforced by machinery the plugin repo needs anyway, and it does so without asking Anthropic for a feature (they closed the adjacent per-directory request, issue #25612, as "not planned").

**meeting_test** — Hand-authored versus generated style files is a fork in the entire deliverable's shape; it has to be settled before anything is written.

---

## 4. The `★ Insight` box is spending the turn's whole visual budget on prose

**summary** — The operator asked for pictures, graphs and tables instead of walls of text. What he actually receives on nearly every turn is a decorative frame containing more prose. In a terminal, salience is rivalrous: an element that appears every turn carries no information. Treat "one salient block per turn" as a budget and decide deliberately what buys it — and let nothing routine buy it.

**axis** — A3 Visual form selection

**basis** — `direct:` "Box-drawing characters: 341 messages — but 311 (91%) are the `★ Insight` callout box from the currently-active Explanatory style, not diagrams. Genuine diagrams: ~30 (0.19%)." Against seed #2: "I generally want good explainations with pictures, graphs, tables over a mountain of text."

**why_it_matters** — The most-rendered visual element in this operator's entire corpus is one no seed asked for, and it is the direct competitor for the attention that any status block or genuine diagram would need. Whatever the new styles do visually, they are building on top of an inherited habit nobody chose.

**meeting_test** — It settles whether the new styles inherit Explanatory's per-turn callout or explicitly kill it — a visible, immediate change the operator will notice on turn one.

---

## 5. "Verify a style works" is already possible — the harness that produced this grounding is the instrument

**summary** — The assumption is that a style's effect is subjective. But the transcript analysis behind this run produced hard baselines from the same corpus a future pass would read. Reframe the deliverable from "a style" to "a style plus a pre-registered metric and a baseline captured before it ships," re-run in N days.

**axis** — A4 Style architecture and lifecycle

**basis** — `direct:` The baselines already exist in the grounding: 0.76% of sessions end with a status signal; format complaints 43 of 765 human messages (5.6%); clarity 55 (7.2%); status confusion 14 (1.8%); mountain-of-text 40 messages (0.25%). Against CLAUDE.md: "'Fixed' / 'working' / 'shipped' needs a confirming signal."

**why_it_matters** — Without a captured baseline, the operator is structurally forbidden by his own ratified policy from ever calling the style working. The window for capturing it closes the moment the first style lands, because after that the corpus is contaminated.

**meeting_test** — It decides whether "snapshot the baselines before anything ships" is a blocking first step or an optional nicety, and that ordering cannot be recovered later.

---

## 6. The operator diagnosed the location wrong: status belongs at the top, and the bottom belongs to the ask alone

**summary** — Seed #5 describes the symptom accurately and prescribes the remedy in the wrong position. The measured satisfied turns do not carry an end summary; they carry a front verdict and a bare closing ask. A bottom-heavy status block competes with the ask for the last-read position. Proposal: verdict sentence first, ask last and alone, and if a complete/next list is wanted it sits directly under the verdict at the top.

**axis** — A1 Turn shape

**basis** — `direct:` Seed #5: "to often at the end of the output I have no idea what is status. I think some sort of summary with: what's complete and whats next might be ideal." Against the counter-sample: "10 of 10 open with a bolded one-sentence plain-language verdict" and "the discriminator is structural placement: verdict-first, ask-last, nothing declarative trailing after the ask."

**why_it_matters** — This is the seed most likely to be implemented literally, and on this evidence a literal implementation would degrade the one structural property that separates satisfied turns from complaint turns. It is also the seed the measured evidence supports most strongly in *motivation* and contradicts most directly in *mechanism*.

**meeting_test** — Implementing seed #5 as written and implementing the counter-sample are two different designs; someone has to choose, out loud, with the operator present.

---

## 7. Detection can happen at inference time instead of at load time

**summary** — Selecting a style is assumed to mean a file-presence rule resolved when the session starts. But the committed setting only has to pick the *content-type* register, which the evidence says is cleanly detectable. The undetectable variable — orchestration mode versus direct ops — is a property of the turn, and the model is present at turn time and can see its own tool mix. Put the mode switch in the style body as a conditional the model evaluates, and leave `settings.json` carrying only the stable choice.

**axis** — A4 Style architecture and lifecycle

**basis** — `direct:` "DETECTION IS THE WEAK LINK. Content-type rules are clean: `constitution.md` => agent-governance; `.claude-plugin/` => plugin-dev; `ansible/` => infra. But orchestration-mode has NO reliable file-presence rule — `.saga/` exists in ansible-collections too... Mode must be read from live tool-use mix, not repo structure. `talaria`'s ADR signature is temporal and will silently stop firing once it ships code."

**why_it_matters** — It keeps the settled committed-per-repo-selection decision fully intact while routing around the single finding that would otherwise make that selection silently wrong in two named repos. Silently wrong is the worst failure shape here, because a stale rule presents as working.

**meeting_test** — It determines how many files ship — a cross-product of content-type and mode, or a smaller set of content-type files each carrying a mode conditional.

---

## 8. Do not try to govern the 57% — govern what crosses back into the main thread

**summary** — The 57% figure invites an attempt to reach subagents, which the binary's prompt namespacing says a style cannot do. But the operator does not read subagent transcripts; he reads the main thread, and every subagent contribution reaches him through a main-thread message that *is* in scope. The reachable rule is an intake contract: main-thread text may never carry a subagent payload verbatim.

**axis** — A5 Reach beyond the main thread

**basis** — `direct:` "13,665 main-thread assistant text messages vs 17,922 subagent messages... 57% of all assistant text is generated outside any output style's reach." And the specific worst case: "one of the three worst was **literal unformatted JSON** (a subagent findings payload, 12,347 chars) dumped into a main-thread reply undigested."

**why_it_matters** — It converts the research pass's largest and most discouraging number into a single clause a style can actually enforce, and the worst measured message in the entire corpus is precisely this failure. The coverage gap is real; the *experienced* gap is much smaller and sits inside the style's reach.

**meeting_test** — It reframes A5 from "we cannot fix 57%" into "here is the clause covering the part of it the operator sees," which changes whether A5 produces a deliverable at all.

---

## 9. A style file can be a corpus of rewrites rather than a list of rules

**summary** — The operator already learned once that stated principles do not change behavior, and his fix was to make the principles more specific. The dated record shows the more-specific version also failed within a week. Push the same move one step further: for each of the six failure modes in the taxonomy, carry one real before-line from the operator's own transcripts and its rewrite. A style file does not have to be prose rules.

**axis** — A2 Word-level discipline

**basis** — `direct:` The Plain English section entered CLAUDE.md after 2026-07-20 ("you always act as if I have the references you do... udpate the global claude file to keep this in check"). The same class of complaint recurred on 2026-07-26 ("stop saying \"vacuous\" and be more descriptive... more like a developer, less like an academic") and 2026-07-27 ("I rarely understand what you are telling me, to much extra info and not enough of what is important right now"). And the operator's own line inside that section: "Vague direction ('be clear', 'clarity over cleverness') proved too weak to change behavior, so these rules are specific and testable."

**why_it_matters** — This is the only proposal here that responds to the measured fact that the ratified prose rules did not hold, instead of assuming a better-worded version will. The raw material — real bad lines paired with what the operator accepted — is already sitting in the corpus that this run just indexed.

**meeting_test** — Rules versus demonstrated examples changes the authored form of every other accepted idea, so it has to be decided before drafting, not after.

---

## 10. `keep-coding-instructions` proves styles are not presentation-only

**summary** — Settled decision 3 assumes styles carry presentation and CLAUDE.md carries policy. One frontmatter field falsifies that cleanly: at its default, a style silently removes Claude Code's built-in engineering instructions. Under that default, switching register also changes what Claude does, disguised as a change in how it talks. Lock the field set-wide and let the same generator and test that enforce the shared base fail the build if any style omits or flips it.

**axis** — A4 Style architecture and lifecycle

**basis** — `direct:` "`keep-coding-instructions: false` is the DEFAULT and it SILENTLY REMOVES Claude Code's built-in software-engineering instructions — how to scope changes, write comments, and verify work. Highest-confidence risk in the whole research pass, from Anthropic's own docs." Against settled decision 3: "styles ABSORB presentation rules; CLAUDE.md slims to non-presentation policy."

**why_it_matters** — It is the one path by which the "switch styles, lose it" risk the operator knowingly accepted costs him *capability* rather than phrasing — and a capability loss is the variant he is least likely to notice, because nothing about the output announces it.

**meeting_test** — It decides whether that frontmatter field is an author's choice per style or a locked, test-enforced field, which is a small decision with a silent and expensive failure mode.

---

## 11. The trigger for a picture lives in the operator's message, not in the content

**summary** — Content-keyed rules ("architecture gets a diagram") are exactly what produced the unwanted mermaid. Key the trigger on the user's message instead, with one detectable predicate: a re-ask. First explanation of something is prose; a second pass at the same subject in the same session escalates modality to a tree, table, or small dependency chain. The model can evaluate this from the conversation it already has.

**axis** — A3 Visual form selection

**basis** — `direct:` "The operator asked for 'pictures' **five separate times** across the window, always when already lost. TENSION RESOLVED: the objection is to an UNREQUESTED diagram in a routine update, not to diagrams. This is a rule about TRIGGERING, not about format." Corroborating re-ask instances: "where are we? can you close this outcome yet?" and "when you say clone, what the fuck are you talking about."

**why_it_matters** — The grounding identifies triggering as the real question but does not supply a predicate. Re-ask fits all five observed picture requests, is cheap to state, and is evaluable without any file inspection — and it survives in the profile where a content taxonomy misfires.

**meeting_test** — It is the only concrete answer on the table to the open trigger question, so accepting or rejecting it closes A3's central gap either way.
