# Frame 5 — Cross-domain analogy candidates (run 2e71b34e)

11 candidates. Axis distribution: A1 x3, A2 x2, A3 x2, A4 x2, A5 x2.

Every candidate carries named external prior art with a source URL, and every one is
carried through to the literal instruction a style file could contain.

---

## 1. The closing block is a state declaration, not an activity log

- **title** — Shift turnover: declare the state of the system, never narrate the shift
- **summary** — Industrial and nuclear shift handover does not ask the outgoing operator to
  recount what they did. It asks for the current configuration of the plant, the status of
  activities still running, and anything the oncoming watch is not free to change. Applied
  here, the end-of-turn block stops being a summary of the response and becomes a declaration
  of what is now true of the system. A summary can be skimmed and skipped; a state declaration
  is the only place that information exists.
- **axis** — A1
- **basis** — `external:` IAEA Safety Standards, *Conduct of Operations at Nuclear Power
  Plants*, which treats shift turnover as its own governed activity alongside shift rounds and
  log keeping (https://www-pub.iaea.org/MTCD/Publications/PDF/PUB2032_web.pdf). US Nuclear
  Regulatory Commission guidance describes turnover content as "the status of plant equipment,
  and the status of ongoing activities, such as extended tests of safety systems and
  components" — equipment state and activity state, not a chronology
  (https://www.nrc.gov/docs/ml0834/ml083450028.pdf).
- **why_it_matters** — The measured corpus shows only 3 of 395 sessions (0.76%) end with any
  status signal at all, and the counter-sample shows 10 of 10 satisfied replies end on a single
  explicit ask with nothing declarative trailing after it. "Add a summary" is the weak version
  of that finding and will drift back into narration. The turnover framing gives the rule a
  test that survives drift: if a line describes what the agent did rather than what is now
  true, it does not belong in the block. It also supplies the deletion rule the statusline
  requires — the statusline already renders model, effort, context percentage, cost, branch,
  and PR review state every 10 seconds, and a handover that reads gauges the oncoming watch can
  already see is exactly what turnover discipline forbids.
- **concrete instruction** — Every turn that changed system state ends with exactly three
  labelled lines, always all three, in this order, with "none" written out rather than the line
  omitted:
  `State now:` what is true of the system after this turn, named in plain words;
  `Not done:` what was in scope and is not finished;
  `Yours:` the one decision or approval that is the operator's.
  No sentence may follow the `Yours:` line. The block may not restate model, effort, context
  use, cost, branch name, or PR review state.
- **meeting_test** — It converts the highest-evidence finding in the research into a rule with
  a failure test, and it forces a decision on whether the three labels are fixed strings across
  every style in the set or vary by mode.

---

## 2. Hand over pre-committed branches, not next steps

- **title** — I-PASS contingency planning: the ask is an if-then list the operator selects from
- **summary** — The medical handoff mnemonic I-PASS stands for Illness severity, Patient
  summary, Action list, Situation awareness and contingency planning, and Synthesis by
  receiver. The element that gets copied least is the second S: contingencies are written in
  advance as if-then pairs, so the receiving clinician selects a prepared branch instead of
  deriving a plan under load. A "next steps" list makes the reader generate the decision. An
  if-then list makes the reader pick one, in one word.
- **axis** — A1
- **basis** — `external:` Starmer AJ et al., "Changes in Medical Errors after Implementation of
  a Handoff Program," *N Engl J Med* 2014;371:1803-12. Across 10,740 admissions at nine
  pediatric residency programs the medical-error rate fell 23% (24.5 to 18.8 per 100
  admissions, P<0.001) and preventable adverse events fell 30% (4.7 to 3.3 per 100 admissions,
  P<0.001), with no negative effect on workflow
  (https://pubmed.ncbi.nlm.nih.gov/25372088/).
- **why_it_matters** — This is the only handoff format in any domain with a measured effect
  size on outcomes rather than on satisfaction, which makes it the strongest possible answer to
  "does structured handoff actually work." It also sharpens the operator's own seed. The seed
  asks for "what's complete and what's next"; the counter-sample shows the satisfied replies
  end on "Want me to run the merge?" and "Holding here until you weigh in." Those are branches,
  not next steps. The two dominant human prompt modes in the corpus are approval/continuation
  ("go ahead", "approved") and status check — an operator who answers in one word is being
  served by a format that only needs one word.
- **concrete instruction** — When the turn ends with a choice, write the `Yours:` line as at
  most three pre-committed branches in the form `if <condition> -> I will <action>`, each
  action stated fully enough that "go" is a complete instruction. Never end on an open question
  that requires the operator to specify the work. When the turn was long or multi-part, precede
  the branches with one line restating the objective the work is serving, so a drifted
  objective is caught before the operator approves a branch — the written-out inversion of
  I-PASS's synthesis-by-receiver step, which an agent cannot demand of the operator but can
  perform on itself.
- **meeting_test** — It challenges the seed's own wording, replacing "what's next" with a
  selectable branch list, and it needs a decision on the cap (three branches) and on whether
  the objective-restatement line fires on every long turn or only after a subagent returns.

---

## 3. After the first orientation, issue only the delta

- **title** — Fragmentary order: two turn shapes, and a named trigger list for the full one
- **summary** — A fragmentary order is an abbreviated order issued after a full operations
  order. It keeps the same five-paragraph skeleton but fills only the paragraphs that changed,
  leaving everything else in the base order standing. Nobody re-reads the base order; nobody
  loses it either. Applied here, the style defines a full-orientation turn and a delta turn,
  and names exactly what triggers the full one, instead of asking every turn to orient from
  scratch.
- **axis** — A1
- **basis** — `external:` US Army doctrine, *ADP 5-0, The Operations Process*
  (https://armypubs.army.mil/epubs/DR_pubs/DR_a/ARN18126-ADP_5-0-000-WEB-3.pdf), and the
  fragmentary-order format, which "addresses only those parts of the original OPORD that have
  changed" and follows the base order's structure in abbreviated form
  (https://www.utoledo.edu/rotc/pdfs/FRAGO.pdf).
- **why_it_matters** — The measured length distribution is bimodal: median 142 characters, p75
  292, p90 1,658, max 26,994. A single turn shape cannot serve both ends — orientation on every
  142-character turn is noise, and no orientation on the p90 turns is the failure the operator
  actually complained about. The fragmentary-order model is the only convention found that
  resolves "always orient" against "stop repeating yourself" without a judgment call per turn,
  because the trigger list is enumerable. It also gives seed #4 (more than one style per repo) a
  cheaper answer than repo detection: the split that matters is turn-level, not repo-level, and
  the research already found that repo-shape detection has no reliable file-presence rule for
  the orchestration mode.
- **concrete instruction** — Define two shapes. A **full orientation** opens with one sentence
  naming the repo, the system, and why this matters now, and closes with the three-line block.
  It is mandatory on the first substantive turn of a session, on a topic change, after any tool
  run longer than about two minutes, and after any subagent returns. Every other turn is a
  **delta turn**: it reports only what changed, and must open with a clause anchoring it to the
  last full orientation ("Against the plan from earlier: ..."). A delta turn is forbidden if no
  full orientation has been issued in the session.
- **meeting_test** — It replaces a per-turn judgment with an enumerated trigger list, and the
  team has to decide whether "after any subagent returns" is one trigger too many given how
  much of this operator's work is fan-out.

---

## 4. No bare number, ever — the type word comes first

- **title** — Air traffic control phraseology: an identifier is never a noun
- **summary** — Controllers never speak a number alone. Every number carries the word that
  says what kind of number it is — runway, heading, flight level, knots — because a bare "two
  three zero" is ambiguous and because dropping the key word changes how the receiver processes
  the whole message. The same discipline turns the operator's existing "name the thing" rule
  from a style preference into a banned-pattern list a response can be checked against.
- **axis** — A2
- **basis** — `external:` FAA Air Traffic Bulletin 2018-1, *Phraseology*, which states that
  numbers such as "two three zero" have ambiguous meaning unless connected to another word such
  as "knots," "heading," or "flight level," and that eliminating key words ("cross two" without
  the runway designator) reduces clarity and affects how a pilot processes the message
  (https://www.faa.gov/media/70826). Governing order: FAA JO 7110.65, *Air Traffic Control*
  (https://www.faa.gov/air_traffic/publications/atpubs/atc_html/).
- **why_it_matters** — Bare identifier as a noun is 2 of the 9 traced complaints, one message
  carried more than fifteen bare issue numbers, roughly 7.9% of messages carry commit-hash-shaped
  hex with no explanatory word nearby, and `path:line` references appear in 3.72% of messages
  averaging 1.79 per message with a maximum of 25. The existing Plain English rule already
  states the principle and is still being violated, which suggests the principle needs a
  mechanical form. Air traffic control is the domain that took the same principle and made it
  mechanical, and it is worth copying the mechanism rather than the sentiment.
- **concrete instruction** — A token matching `#\d+`, a hex string of 7 or more characters, a
  branch name, a test name, or a `path:line` reference may never be the subject or object of a
  sentence. On first use in a turn it must be preceded, in the same clause, by a type noun and a
  plain-language descriptor: "issue #42, the one that adds retry on the webhook", "commit
  458b983 ('kill six surviving mutants')". Later uses in the same turn may be bare. A sentence
  may carry at most two distinct identifiers; a third means the content belongs in a table with
  the identifier in one column and its descriptor in another.
- **meeting_test** — The last clause converts a word-level rule into a format trigger, which
  links A2 to A3, and the team should decide whether the two-identifier cap is the right
  threshold given a corpus message that carried 25.

---

## 5. Earn the abbreviation with a use count

- **title** — The Associated Press alphabet-soup rule: if it needs a gloss, do not use it
- **summary** — AP style forbids following an organization's full name with its acronym in
  parentheses, and adds that if the acronym would not be clear on second reference without that
  introduction, do not use the acronym at all. This is strictly stronger than gloss-on-first-use,
  which is the rule already in policy: AP treats the need for a gloss as evidence the short form
  should not exist. The implementable version is a use-count test, which is checkable in a way
  that "avoid jargon" is not.
- **axis** — A2
- **basis** — `external:` AP Stylebook, abbreviations and acronyms entry — "Do not follow the
  full name of an organization or company with an abbreviation or acronym in parentheses or set
  off by dashes. If an abbreviation or acronym would not be clear on second reference without
  this arrangement, don't use it," and "Names not commonly before the public should not be
  reduced to acronyms solely to save a few words"
  (https://x.com/APStylebook/status/1503764242851414019).
  Cautionary precedent from a field that compressed instead: aviation NOTAMs are contraction-dense
  and all-caps, and in the Air Canada flight 759 near-miss at San Francisco on 7 July 2017 the
  runway-closure information was present but buried in more than ten pages of pre-flight NOTAMs
  and comprehended by neither pilot. The NTSB's response was to recommend changing how the
  information is presented, not to ask crews to read more carefully
  (NTSB/AIR-18-01, https://www.ntsb.gov/investigations/accidentreports/reports/air1801.pdf).
- **why_it_matters** — The NOTAM case is the strongest available argument for the operator's own
  line that compression which saves characters and costs comprehension is a net loss: an entire
  safety-critical industry optimized for terseness, nearly lost four aircraft to a true but
  unranked item, and is now reversing. It also supplies the missing calibration. A naive acronym
  rule would fire constantly and be ignored, because the measured data shows all-caps 2-5 letter
  tokens appear in 20% of messages and about half the top offenders are `NOT`, `DONE`, `PASS`,
  and HTTP verbs. The genuine offenders are a short, nameable list: ADR, HITL, DAG, COPPA, SOUL,
  BP, REG, DR, TUI, DRIFT, INV, SKILL.
- **concrete instruction** — Do not introduce an abbreviation you will use fewer than three
  times in the same response; repeat the words instead, even when longer. Never write
  `Full Name (ABC)` — if ABC needs that introduction to be understood later, do not use ABC.
  Never coin a new short form for a project concept inside a response. Fixed exempt list, and it
  does not grow: API, URL, CI, PR, HTTP verbs, and all-caps emphasis words.
- **meeting_test** — It supersedes rather than restates the existing gloss rule, and the team
  must agree the exempt list is closed, because an open exempt list is how alphabet soup returns.

---

## 6. Visuals are phase-gated: barred in routine, required in orientation

- **title** — Sterile cockpit: the same diagram is a violation on approach and correct at cruise
- **summary** — The sterile flight deck rule bars all non-essential activity below 10,000 feet
  and during taxi, takeoff, and landing — and permits the identical activity at cruise. It is a
  phase rule, not a volume rule. The research already established that this operator's objection
  is to an unrequested diagram in a routine update, and that they asked for pictures five
  separate times, always when already lost. That is precisely a phase distinction, and aviation
  has a fifty-year-old, federally codified form of it.
- **axis** — A3
- **basis** — `external:` 14 CFR 121.542, flight crewmember duties, imposed by the FAA in 1981
  after a series of accidents caused by crews distracted by non-essential conversation during
  critical phases; critical phases are defined as all ground operations involving taxi, takeoff
  and landing, and all other operations below 10,000 feet except cruise
  (https://www.ecfr.gov/current/title-14/chapter-I/subchapter-G/part-121/subpart-T/section-121.542).
- **why_it_matters** — The verified tension resolution says this is a rule about triggering, not
  about format, and no other domain states a triggering rule this cleanly. The non-obvious half
  is the second half: sterile cockpit works because the same regulation *mandates* the required
  callouts during the critical phase — it is not one-sided suppression. A style that only
  suppresses visuals will produce an agent that is visual-shy in exactly the turns where five
  recorded requests say visuals are wanted. Both directions have to be written or the rule fails
  asymmetrically.
- **concrete instruction** — Name the phases and what each permits.
  *Routine* (a progress update, a single-file edit, a command result, an approval
  acknowledgement): no unrequested visual of any kind, regardless of how good it would be —
  prose plus the closing block only.
  *Orientation* (the operator asked where things stand, a subject is being introduced for the
  first time this session, a subagent's findings are being delivered, or more than two entities
  relate to each other): a visual is required, not optional.
  *Comparison* (three or more items sharing the same attributes): a table is required.
  An explicit request for a picture overrides the phase in every case.
- **meeting_test** — The "required, not optional" clause is a real commitment that will change
  behavior in both directions, and the orientation trigger list is the part that needs argument.

---

## 7. Three visual forms, drawn identically every time

- **title** — The basic-T: sameness beats expressiveness, because the reader's scan is trained
- **summary** — Every instrument panel since the RAF standardized the layout in 1937 puts
  attitude top-centre, airspeed left, altimeter right, heading below — and glass cockpits kept
  it. The layout is not optimal for any individual instrument. Its value is that it is identical
  in every aircraft, so the scan costs nothing. A bespoke diagram charges the reader a
  layout-parse before any information arrives; the same three forms drawn the same way every
  time cost that once.
- **axis** — A3
- **basis** — `external:` Basic-T flight instrument arrangement, standardized by the Royal Air
  Force in 1937 and preserved in modern glass cockpit layouts
  (https://eng.libretexts.org/Bookshelves/Aerospace_Engineering/Fundamentals_of_Aerospace_Engineering_(Arnedo)/05%3A_Aircraft_instruments_and_systems/5.01%3A_Aircraft_instruments/5.1.04%3A_Instruments_layout).
- **why_it_matters** — Two measured facts converge on this. The genuine ASCII diagram shapes
  actually in use across the corpus are file trees and small dependency chains — nothing else,
  no flowcharts, no sequence diagrams, no state machines. And ArtPrompt (ACL 2024, arXiv
  2402.11753) measured GPT-4 at 25.19% accuracy on single-character ASCII-art recognition, so
  the ambitious spatial forms are also the ones most likely to render wrong, with no validated
  prompt-only technique for preventing width drift. The counterintuitive claim worth arguing is
  that a style should forbid a *better* bespoke diagram in favour of a worse repeated one.
- **concrete instruction** — Enumerate exactly three permitted inline visual forms and forbid a
  fourth.
  (1) **File tree** — `tree`-style with `├─` and `└─` connectors, for anything hierarchical:
  directories, issue and sub-issue, plan and units.
  (2) **Arrow chain** — `A -> B -> C` on one line, or one hop per line when longer, for anything
  sequential or causal; maximum seven nodes, beyond which it becomes a table.
  (3) **Two-column state table** — Markdown, left column the thing named in plain words, right
  column its state drawn from a fixed vocabulary.
  Anything needing a box-drawing frame, a swimlane, a timeline, or a grid is not drawn; it
  becomes a table. Box-drawing characters are permitted only as file-tree connectors.
- **why the frame supports the last clause** — 341 messages contain box-drawing characters and
  311 of them (91%) are the `★ Insight` callout box, not a diagram. The IoTeacher ASCII dashboard
  prior art names "overusing borders until content becomes hard to scan" and "inconsistent mixing
  of ASCII and Unicode styles" as its own anti-patterns.
- **meeting_test** — It proposes forbidding a better diagram on purpose, which is the kind of
  claim that should not pass without argument.

---

## 8. Declare what the style turns off, and the compensating procedure

- **title** — Minimum Equipment List: nothing is allowed to be silently missing
- **summary** — An aircraft may be dispatched with specified equipment inoperative only under an
  approved Minimum Equipment List, which names each item, how many must work, and the provisos —
  including the operational and maintenance procedures that compensate for the missing item. The
  inoperative control is placarded so the crew sees the degraded state from the seat. The style
  files should carry the same declaration, because the single highest-confidence risk found in
  the research is a silent removal.
- **axis** — A4
- **basis** — `external:` 14 CFR 91.213, inoperative instruments and equipment
  (https://www.ecfr.gov/current/title-14/chapter-I/subchapter-F/part-91/subpart-C/section-91.213);
  National Business Aviation Association summary of the MEL structure and placarding requirement
  (https://nbaa.org/aircraft-operations/maintenance/inoperative-instruments-equipment/).
- **why_it_matters** — `keep-coding-instructions` defaults to **false**, and false silently
  removes Claude Code's built-in software-engineering instructions covering how to scope changes,
  write comments, and verify work. That is a dispatch with an inoperative item and no placard,
  and it will not announce itself — it will present as an agent that has quietly become worse at
  engineering while the presentation improves. The same hazard covers the risk the operator
  already accepted when agreeing to absorb presentation rules out of CLAUDE.md: a rule that lives
  only in the active style disappears on a style switch, and a cross-reference to a file whose
  rules were moved out is the un-placarded case.
- **concrete instruction** — Every style file this operator ships carries a required section:
  ```
  ## What this style suppresses, and what replaces it
  - Built-in coding instructions: KEPT (keep-coding-instructions: true)
  - CLAUDE.md "Plain English" rules 1-7: ABSORBED — restated in full below, not referenced
  - Nothing else is removed.
  ```
  Two hard conventions accompany it. First, `keep-coding-instructions: true` is written
  explicitly in every style's frontmatter and never left to default, so the value is visible in
  the file rather than inferred from documentation. Second, any rule absorbed out of CLAUDE.md is
  restated verbatim in every style in the set — never cross-referenced — so switching styles
  cannot drop it.
- **meeting_test** — It turns the research's highest-confidence risk into a file convention, and
  the verbatim-duplication requirement is a real maintenance cost the team should accept or
  reject deliberately.

---

## 9. Every style carries a cheap, unique, always-on tell

- **title** — The reporter tag: make "which style is loaded" observable without reading anything
- **summary** — Green fluorescent protein is fused to a protein of interest so its location and
  behavior can be watched inside a living cell, continuously, without destroying the cell. The
  observation is free and always running. Each style in the set should carry an equivalent
  marker — a distinctive, greppable string that appears in every response under that style and
  nowhere else — so which style was actually active is answerable at a glance and, more
  importantly, retroactively across the transcript archive.
- **axis** — A4
- **basis** — `external:` Nobel Prize in Chemistry 2008, awarded to Osamu Shimomura, Martin
  Chalfie, and Roger Y. Tsien for the discovery and development of green fluorescent protein,
  which makes it possible to study processes inside living cells without destroying them
  (https://www.nobelprize.org/prizes/chemistry/2008/press-release/).
  `direct:` the mechanism is already proven in this exact system — the research pass identified
  which style was active by counting the `★ Insight` callout box, which appeared in 315
  main-thread versus 7 subagent messages, a 98:2 split that supplied one of the two independent
  proofs that output styles do not reach subagents. The marker performed the measurement. Nobody
  designed it as a marker.
- **why_it_matters** — Verification is currently expensive and indirect. A style takes effect
  only after `/clear` or a new session because the system prompt is read once; the
  `/output-style` command was deprecated in v2.1.73 and removed in v2.1.91; selection now lives
  in `/config`, writing `outputStyle` into `settings.local.json`, which is typically not
  committed. So "am I running the style I think I am" has no cheap answer today. It gets worse
  under the operator's per-repo selection decision, because the failure mode of per-repo
  selection is silently getting the wrong style, not getting no style. A per-style tell turns
  that from invisible to greppable, and the same grep becomes the rollout's verification method.
- **concrete instruction** — Each style in the set mandates one distinctive string emitted in
  every response and by no other style — for example, the closing block's third label is
  `Yours:` in the orchestration style and `Your call:` in the direct-ops style. Two properties
  are required: the tell must be distinct per style, so the operator learns *which* style is
  loaded rather than merely that one is; and it must be a fixed literal string, so one grep over
  the transcript directory reports which style was actually active per session after the fact.
- **meeting_test** — It answers the "how would the operator verify a style is working" part of
  A4 with a mechanism whose effectiveness is already demonstrated in this operator's own data.

---

## 10. The presentation contract travels in the assignment

- **title** — Master's standing orders: govern the writer of the order, since you cannot govern
  the watch
- **summary** — At sea the Master's Standing Orders are a permanent set of rules for the conduct
  of any watch; they are signed by the Master and by each Officer of the Watch on joining, and
  Night Orders add case-specific instructions on top for a particular watch. The orders bind
  whoever holds the con, not a named person, and acknowledgement renews at every handover.
  Output styles cannot reach subagents — but the main thread that writes the subagent's prompt
  *is* inside the style's reach, so the style can require that the contract be stamped into
  every assignment.
- **axis** — A5
- **basis** — `external:` Master's Standing Orders and Night Orders as practised under bridge
  procedures, signed by the Master and by the officers of the watch on joining the ship, with
  night orders adding case-specific instructions on top of the standing set
  (https://www.marineinsight.com/guidelines/masters-standing-and-night-orders/).
- **why_it_matters** — This is the only mechanism found that reaches the 57% of assistant text
  generated outside any style's reach without waiting on a product change, and it costs one
  paragraph per spawn. It also relocates seed #1 to where the evidence actually puts it: Mermaid
  fenced blocks appear in only 7 main-thread messages (0.04%), which does not support the seed's
  premise at the main-thread level — but Mermaid concentrates in subagent traffic at 119
  messages. A no-Mermaid rule in the main-thread style would be aimed at the wrong surface. In
  the spawn contract it is aimed at the right one.
- **concrete instruction** — The style requires that every subagent prompt the main thread
  writes ends with a fixed, verbatim returning-format contract, quoted below the rule in the
  style file so it is copied rather than paraphrased. Three clauses, one per measured failure on
  that surface:
  (1) "Open with a one-sentence plain-language verdict, then the evidence."
  (2) "Your reader is a monospace terminal that renders no images and no Mermaid. Any diagram
  must be literal characters."
  (3) "Return findings as prose with named referents. Do not return JSON, and never use a bare
  identifier without saying what it is."
- **meeting_test** — It is the only candidate that touches the 57% surface at all, and the team
  needs to decide whether the contract is a fixed block in the style file or a skill/agent-level
  convention that the style merely points at.

---

## 11. The parent is the copy desk, not a pass-through

- **title** — Wire copy is rewritten, never printed raw
- **summary** — Newsrooms do not publish agency copy as it arrives. A sub-editor or copy chief
  on the news desk selects and rewrites incoming wire material into the paper's single voice;
  rewriting is defined as restructuring at the sentence and paragraph level, as distinct from
  editing, which is minor cleanup for flow and length. The reporter in the field is not
  responsible for house style — the desk is. The main thread is the desk, and a subagent return
  is source material, not output.
- **axis** — A5
- **basis** — `external:` newsroom practice on levels of editing, distinguishing rewriting
  (reorganising at sentence and paragraph level) from editing (minor changes for flow and
  wordiness) (https://journalism.university/writing-and-editing-for-print-media/levels-of-editing-journalism-explained/);
  wire service workflow, in which newspapers develop dedicated editors responsible for selecting
  and modifying incoming wire reports into a single cohesive voice
  (https://www.encyclopedia.com/media/encyclopedias-almanacs-transcripts-and-maps/wire-services).
- **why_it_matters** — One of the three worst "mountain of text" messages in the whole corpus was
  literal unformatted JSON — a subagent findings payload of 12,347 characters — dumped into a
  main-thread reply undigested. That is wire copy printed raw, and it is the single most
  concrete rendering failure in the measured data. It is also the failure the standing-orders
  contract in candidate 10 will only partly prevent, because a subagent can always return more
  than the parent asked for. Governing the source and governing the desk are different controls
  and both are needed; the desk rule is the one enforceable entirely inside the main-thread
  style, which is the surface an output style actually reaches.
- **concrete instruction** — A subagent return is source material, not output.
  Quote at most ten contiguous lines of it, and only when the exact text is load-bearing — an
  error string, a function signature, a diff hunk.
  Never emit JSON, YAML, or a raw tool payload as the body of a reply; if the structure matters
  it becomes a table, if the values matter they become a sentence.
  The first sentence of the reply after a subagent returns is the main thread's own verdict in
  plain language, not the subagent's opening line.
  If the subagent returned nothing usable, say so in one sentence and do not pad with its
  process narration.
- **meeting_test** — It is enforceable on the surface a style actually governs, it targets the
  worst single measured message in the corpus, and it pairs with candidate 10 as source control
  versus desk control — the team should take both or explicitly choose one.

---

## Sources

- Starmer AJ et al., *N Engl J Med* 2014;371:1803-12 — https://pubmed.ncbi.nlm.nih.gov/25372088/
- IAEA, *Conduct of Operations at Nuclear Power Plants* — https://www-pub.iaea.org/MTCD/Publications/PDF/PUB2032_web.pdf
- US NRC Regulatory Guide (shift turnover content) — https://www.nrc.gov/docs/ml0834/ml083450028.pdf
- US Army *ADP 5-0, The Operations Process* — https://armypubs.army.mil/epubs/DR_pubs/DR_a/ARN18126-ADP_5-0-000-WEB-3.pdf
- Fragmentary order format — https://www.utoledo.edu/rotc/pdfs/FRAGO.pdf
- FAA Air Traffic Bulletin 2018-1, *Phraseology* — https://www.faa.gov/media/70826
- FAA Order JO 7110.65, *Air Traffic Control* — https://www.faa.gov/air_traffic/publications/atpubs/atc_html/
- AP Stylebook, abbreviations and acronyms — https://x.com/APStylebook/status/1503764242851414019
- NTSB/AIR-18-01, *Taxiway Overflight, Air Canada Flight 759* — https://www.ntsb.gov/investigations/accidentreports/reports/air1801.pdf
- 14 CFR 121.542, flight crewmember duties (sterile flight deck) — https://www.ecfr.gov/current/title-14/chapter-I/subchapter-G/part-121/subpart-T/section-121.542
- Basic-T instrument arrangement — https://eng.libretexts.org/Bookshelves/Aerospace_Engineering/Fundamentals_of_Aerospace_Engineering_(Arnedo)/05%3A_Aircraft_instruments_and_systems/5.01%3A_Aircraft_instruments/5.1.04%3A_Instruments_layout
- 14 CFR 91.213, inoperative instruments and equipment — https://www.ecfr.gov/current/title-14/chapter-I/subchapter-F/part-91/subpart-C/section-91.213
- NBAA, inoperative instruments and equipment / MEL — https://nbaa.org/aircraft-operations/maintenance/inoperative-instruments-equipment/
- Nobel Prize in Chemistry 2008 (green fluorescent protein) — https://www.nobelprize.org/prizes/chemistry/2008/press-release/
- Master's Standing and Night Orders — https://www.marineinsight.com/guidelines/masters-standing-and-night-orders/
- Levels of editing in journalism — https://journalism.university/writing-and-editing-for-print-media/levels-of-editing-journalism-explained/
- Wire services (newsroom workflow) — https://www.encyclopedia.com/media/encyclopedias-almanacs-transcripts-and-maps/wire-services
