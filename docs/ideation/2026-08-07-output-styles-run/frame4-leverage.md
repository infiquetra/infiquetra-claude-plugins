# Frame 4 — Leverage & Compounding: raw ideation candidates

Run 2e71b34e, 2026-08-07. Lens: choices that make many future moves cheaper or stronger;
second-order effects. Candidates only — no ranking, no filtering.

Terms used below, expanded on first use per the operator's own Plain English rule:
- **output style** — a Markdown file with YAML frontmatter that Claude Code loads once per
  session and injects into the main conversation's system prompt.
- **`keep-coding-instructions`** — an output-style frontmatter flag; when `false` (its default)
  Claude Code's built-in software-engineering instructions are removed from the system prompt.
- **`force-for-plugin`** — an output-style frontmatter flag that lets a plugin auto-apply its
  own style and override whatever the operator selected.
- **the counter-sample** — the 10 traced messages in this research window that produced
  satisfied or forward-progress replies from the operator, as opposed to complaints.
- **the 57% surface** — subagent-generated assistant text (17,922 messages of 31,587 total),
  which no output style reaches.

---

## 1. The base fragment: one authored file, concatenated into every style at build time

- **title:** The base fragment — solve the shared-base problem at build time, because it cannot be solved in the file
- **summary:** Output-style frontmatter has no `extends`, `include`, or `import` key; only
  `name`, `description`, `keep-coding-instructions`, and `force-for-plugin` are confirmed
  present in the Claude Code binary. So the operator's accepted risk — a rule lives only in the
  active style, and switching styles loses it — has no in-file remedy. Author the shared rules
  once as `base-presentation.md` in the plugin repository, and have the plugin's build step
  concatenate that fragment verbatim into every shipped style file, with the per-style rules
  appended after it. The distributed styles stay plain standalone Markdown, which is what
  Claude Code requires; the authoring surface becomes one file instead of N.
- **axis:** A4 Style architecture and lifecycle
- **basis:** `direct:` — settled decision 3 states the operator "accepted the stated risk: 'a
  rule only lives in the active style — switch styles, lose it, unless every style shares a
  common base.'" Verified mechanics list exactly four frontmatter keys, none of them an
  inheritance mechanism; the plugin loader offers `outputStylesPath` / `outputStylesPaths` with
  `append` merge, which merges *style lists*, not style *contents*.
- **why_it_matters:** This is the one artifact that changes the cost curve of every subsequent
  style. Without it, style number four is authored by copying style number three, and the
  moment a rule is corrected the operator is hand-patching every file — which is precisely how
  the accepted risk turns from theoretical into a live bug. With it, adding a fifth style costs
  only the delta that makes it different, and correcting a shared rule is a one-line edit that
  propagates on the next build. Every other idea in this frame gets cheaper if this one exists
  first.
- **meeting_test:** The team has to decide whether the plugin gets a build step at all, or
  whether styles are hand-maintained files — and that decision is irreversible in practice once
  three styles exist.

---

## 2. A style contract test, with the `keep-coding-instructions` amputation as its first assertion

- **title:** Assert the frontmatter in a test so no future style can silently amputate the coding instructions
- **summary:** `keep-coding-instructions` defaults to `false`, and that default silently strips
  Claude Code's built-in software-engineering instructions — how to scope a change, how to
  write comments, how to verify work. A style author who simply omits the key gets the
  amputation and no warning. Add a small test in the plugin repository that parses every shipped
  style file and asserts a contract: `keep-coding-instructions: true` unless the file carries an
  explicit written waiver, `force-for-plugin` absent or `false`, `name` and `description`
  present, and the base fragment (idea 1) present verbatim.
- **axis:** A4 Style architecture and lifecycle
- **basis:** `direct:` — the grounding names this "the highest-confidence risk in the whole
  research pass, from Anthropic's own docs," and confirms both flag strings are present in
  binary 2.1.224 with `keep-coding-instructions` defaulting to `false`.
- **why_it_matters:** The failure mode here is invisible: nothing errors, nothing warns, the
  session just quietly loses the instructions that make Claude scope work conservatively and
  verify before claiming completion. For an operator whose top global rule is validation
  discipline, silently deleting the built-in "verify your work" guidance is the worst possible
  regression, and it would be attributed to the model rather than to the style file. One
  assertion buys permanent immunity for every style the operator ever writes, including the
  ones written a year from now by a subagent that has never read this research.
- **meeting_test:** The team should decide whether style files get treated as tested code or as
  prose, because that choice determines whether a silent amputation is caught in seconds or
  discovered months later from degraded behavior.

---

## 3. Make the highest-value rule self-measuring: a fixed-shape closing block

- **title:** Give the closing status block a fixed, greppable shape so "is the style working?" is a one-command question
- **summary:** The research proved output styles do not reach subagents partly by accident: the
  `★ Insight` callout box from the currently-active Explanatory style left a rendered
  fingerprint, appearing in 315 main-thread messages versus 7 subagent messages. Design the new
  style's closing status block to leave the same kind of fingerprint on purpose — a fixed
  header string and a fixed field order, stable across every style in the set. Gate it on turn
  size so it never fires on the short turns that dominate the day.
- **axis:** A1 Turn shape
- **basis:** `direct:` — three measurements converge. Only 3 of 395 sessions (0.76%) end with
  any summary, next-step, or status signal. All 10 of 10 counter-sample messages end with a
  single explicit concrete ask. And response length is bimodal — median 142 characters, 75th
  percentile 292, 90th percentile 1,658, maximum 26,994 — so an always-on closing block would
  tax the typical turn heavily while the turns that actually need it are the top decile.
- **why_it_matters:** Two compounding effects from one design choice. First, a style takes
  effect only after `/clear` or a new session, so silent non-application is a real and
  currently undetectable failure; a stable fingerprint makes "did the style load?" answerable by
  grepping one session file. Second, the same fingerprint makes the rule self-measuring against
  its own measured baseline of 0.76%, which is what lets idea 4 work at all. The threshold gate
  is the durability multiplier: a style that adds ceremony to a 142-character answer gets
  switched off, and a switched-off style delivers zero percent of every other rule in it.
- **meeting_test:** The team has to pick the threshold that triggers the block and the exact
  shape of it, and those two choices determine whether the style survives daily use or gets
  disabled in week one.

---

## 4. Commit the measurement itself, so the baseline becomes a regression suite

- **title:** Ship the corpus scorer with the plugin — turn 2,530 transcripts from a one-time study into a repeatable check
- **summary:** This research pass produced a set of numbers that are all mechanically
  recomputable from transcript files: percentage of sessions ending with a status signal
  (0.76%), messages containing a fenced mermaid block (0.04% main-thread), messages over 4,000
  characters with no table, diagram, or code (0.25%), and messages carrying a bare
  commit-hash-shaped token with no nearby explanatory word (roughly 7.9%). Commit the script
  that computes them alongside the styles, with today's values recorded as the baseline. Every
  future style change then answers "did this help?" with a number rather than an impression.
- **axis:** A4 Style architecture and lifecycle
- **basis:** `direct:` — every figure above is already measured in the grounding across 2,530
  transcript files and 16,029 analyzed main-thread messages, and the counter-sample established
  that the discriminator between satisfied and frustrated replies is structural placement
  (verdict first, ask last, nothing declarative trailing) rather than length or formatting.
  Structural placement is exactly the kind of property a script can detect; tone is not.
- **why_it_matters:** The operator's global rule is that "fixed" and "working" require a
  confirming signal, and that a plausible guess dressed as fact is worse than "I don't know."
  Right now a style change has no confirming signal at all — the only feedback loop is whether
  the operator gets annoyed again. A committed scorer converts style work from taste into
  engineering, and it compounds with the existing engineering-journal discipline: a
  `LEARNINGS.md` entry about a style change can cite a before-and-after number as its Evidence
  line instead of an anecdote. Worth noting one config-hygiene dependency: the `hooks` directory
  is symlinked between the two configurations but `settings.json` is not, which is exactly why
  the `repo-freshness` SessionStart hook fires on personal sessions and is absent from work.
  Scripts are shared for free; hook *registration* is paid once per configuration.
- **meeting_test:** The team should decide whether style changes require a measured
  before-and-after, because that single policy determines whether this style set improves over
  years or drifts on vibes.

---

## 5. Govern the seam, not the surface: a digestion rule at the subagent boundary

- **title:** The main thread must digest what a subagent hands it — buying coverage of the 57% surface from inside the 43%
- **summary:** No output style reaches subagents, and no proposed mechanism changes that. But
  the worst formatting failure in the entire corpus was not a subagent's fault in the place it
  occurred — it was a 12,347-character block of literal unformatted JSON, produced by a
  subagent, relayed into a main-thread reply undigested. That relay happens in the main thread,
  which *is* governed. A rule that forbids pasting a subagent's raw payload, and requires the
  main thread to state the finding in plain language before any structured detail, fixes the
  observed harm without needing to reach the agent that caused it.
- **axis:** A5 Reach beyond the main thread
- **basis:** `direct:` — the grounding records 17,922 subagent messages versus 13,665
  main-thread messages, giving the 57% figure, and separately identifies that "one of the three
  worst was literal unformatted JSON (a subagent findings payload, 12,347 chars) dumped into a
  main-thread reply undigested."
- **why_it_matters:** This reframes the largest apparent gap in the whole design from
  intractable to partly solved. The 57% surface is not read by the operator directly — subagent
  text is consumed by the main thread, and only what the main thread chooses to surface reaches
  a human. Governing the seam therefore covers the part of the 57% that actually has an
  audience, at zero mechanism cost, using a surface the style already controls. It also makes
  the eventual full fix cheaper: if the boundary rule is already written down, extending
  presentation discipline into agent definitions later means reusing text rather than
  rediscovering the requirement.
- **meeting_test:** The team should decide whether the 57% subagent surface is a gap to engineer
  around or a gap to close directly, and this idea is the cheap option that makes the expensive
  one optional.

---

## 6. Split the rules by reach, not by category

- **title:** Word-level rules stay in CLAUDE.md because it reaches subagents; turn-shape rules move to the style because they only make sense in the main thread
- **summary:** Settled decision 3 moves presentation rules out of `CLAUDE.md` and into styles.
  Applied uniformly, that is a coverage regression: `CLAUDE.md` is loaded for main thread and
  subagents alike, while a style reaches only the main thread. Moving the Plain English
  word-level rules — gloss every acronym on first use, name the referent before the identifier,
  never stack two pieces of jargon in one clause — would drop them from near-total coverage to
  43%. Split by reach instead: rules about *words* stay where they reach every agent, rules
  about *turn shape and visual triggering* move to the style, because opening with a verdict and
  closing with an ask is a main-thread concept that means nothing in a subagent's return value.
- **axis:** A5 Reach beyond the main thread
- **basis:** `direct:` — the grounding gives two independent proofs that styles do not reach
  subagents (the 315-versus-7 `★ Insight` fingerprint, and the binary's separate
  `repl_main_thread:outputStyle:<name>` versus `agent:custom` prompt namespaces), and separately
  records that the Plain English section is "RATIFIED POLICY, not a new proposal," originating
  from the operator's 2026-07-20 instruction to "udpate the global claude file to keep this in
  check."
- **why_it_matters:** This is the second-order debt the frame asks about, and it is real: a
  clean-looking refactor that moves presentation into styles would silently halve the reach of
  the rules the operator explicitly asked to be made global. The distinction also happens to be
  principled rather than arbitrary, which is what makes it durable — "does this rule mean
  anything to an agent whose output is consumed by another agent?" is a question a future author
  can answer without re-reading this research. It fully honors the settled decision to have
  styles absorb presentation; it just says which presentation.
- **meeting_test:** The team has to agree on the partition line before any rule is moved,
  because moving them and then moving some back is churn across two configurations and a plugin
  release.

---

## 7. Read mode from the operator's prompt, not from the repository's files

- **title:** Mode detection belongs in the prompt register, which costs nothing per repo, rather than in file-presence rules that cost forever
- **summary:** Seed 4 proposes more than one style depending on repository contents, and the
  evidence only partly supports it. `Bash` is the plurality tool in every repository at 57-84%,
  and two repositories with unrelated subject matter — specification Markdown and governance
  Python — show nearly identical tool profiles. The real separator is whether the repository is
  being driven through an orchestration workflow *that turn*, which has no reliable
  file-presence signal. But the operator's own prompt register does carry the signal reliably,
  in two modes that appear everywhere: approval and continuation ("go ahead", "approved") and
  status check ("where are we with X"). Put the mode switch in the style, keyed on what the
  operator just typed.
- **axis:** A4 Style architecture and lifecycle
- **basis:** `direct:` — the grounding states "DETECTION IS THE WEAK LINK," notes that a
  `.saga/` directory exists in the Ansible collections repository which shows almost no
  orchestration usage, warns that the `talaria` repository's decision-record signature "is
  temporal and will silently stop firing once it ships code," and records that the two human
  prompt modes appear in every repository.
- **why_it_matters:** This is the difference between a design the operator gets for free in
  every future repository and one he pays for per repository, forever. A file-presence rule
  needs authoring, committing, and maintaining in each new repository, and the grounding already
  shows two ways it produces wrong answers — a false positive from a stale `.saga/` directory
  and a guaranteed future false negative when `talaria` ships. A prompt-register switch costs
  one section in one style file and works in a repository created next year that nobody
  configured. It also degrades gracefully: guessing the mode wrong from a prompt costs one turn,
  while guessing it wrong from a committed file costs every turn until someone notices.
- **meeting_test:** This directly challenges one of the operator's own seed ideas on measured
  evidence, and the team should resolve it before anyone authors a second style file.

---

## 8. Default the style on at the user level; commit per-repo settings only for genuine exceptions

- **title:** Free by default, paid only for deviation — and a deliberate decision about `force-for-plugin`
- **summary:** Making a style *available* per repository and *selecting* it per repository are
  different problems, and only selection needs a settings key. Set the base style once as the
  user-level default in each configuration so every repository — including ones that do not
  exist yet — gets it with no per-repository action. Commit an `outputStyle` key in a
  repository's `settings.json` only where that repository genuinely needs something other than
  the default. Separately and explicitly: decide against `force-for-plugin: true`, which would
  let the plugin auto-apply its style and override the operator's own selection in both
  configurations at once.
- **axis:** A4 Style architecture and lifecycle
- **basis:** `direct:` — the grounding records that of 18 repositories with Claude settings,
  only 6 have a committed `settings.json` and every one sets only `permissions` or
  `worktree.bgIsolation`, so "no repo has ever committed a behavior key. This would be a first."
  It also confirms `force-for-plugin: true` lets a plugin override the user setting, and that
  Anthropic closed a per-directory output-style configuration request as "not planned"
  (issue 25612).
- **why_it_matters:** The asymmetry is the whole point: a user-level default covers the long tail
  of repositories at zero marginal cost and never goes stale, while every committed
  per-repository key is a small permanent maintenance obligation and a first-of-its-kind
  precedent in this operator's repositories. The second-order cost of committing behavior keys
  is worth naming out loud — a committed `outputStyle` changes how Claude behaves for anyone or
  anything that opens that repository, including automated sessions, and it does so without
  appearing in any diff a reviewer would think to read. Restricting commits to genuine
  exceptions keeps that precedent small and auditable.
- **meeting_test:** Committing the first behavior key in any of these repositories sets a
  precedent for what belongs in version control versus local settings, and that is a team-level
  call rather than a per-repository one.

---

## 9. The gloss ledger: make the glossary a file that accumulates, not a rule that repeats

- **title:** First gloss of an internal term gets written to a repo-local glossary, so the cost of Plain English rule 3 declines instead of recurring
- **summary:** The operator's ratified Plain English rule 3 requires expanding every code,
  acronym, and initialism on first use *in every response*, and the corpus shows a real
  inventory of terms that need it: ADR, HITL, DAG, COPPA, SOUL, BP, REG, DR, TUI, DRIFT, INV,
  SKILL. Rather than the style carrying a static list that goes stale, have it require that the
  first gloss of an internal term in a repository be appended to a repository-local glossary
  file, and that subsequent turns read that file and reuse the exact wording. The rule stays
  identical; what changes is that the answer accumulates.
- **axis:** A2 Word-level discipline
- **basis:** `direct:` — the measured all-caps analysis separated genuine internal terms needing
  a gloss from emphasis-caps and HTTP verbs, producing the specific list above, and two of nine
  traced complaints were unglossed terms of art ("clone", "vacuous"). The operator's own words
  on 2026-07-20: "when you say clone, what the fuck are you talking about... you always act as
  if I have the references you do."
- **why_it_matters:** Three compounding effects. Glosses become *consistent* — the ASD-STE100
  principle of one word, one meaning is unenforceable when each response invents its own
  phrasing, and a written ledger enforces it mechanically. The file reaches agents that the
  style cannot, so the 57% surface inherits the glossary for free without any style mechanism.
  And it feeds the existing engineering-journal discipline directly: a glossary is exactly the
  kind of durable repository knowledge `/retro` is meant to curate, so it gets maintenance for
  free from a process that already runs.
- **meeting_test:** The team should decide whether the style is allowed to write files as a side
  effect of a formatting rule, which is a genuinely new category of behavior for an output
  style and needs a deliberate yes or no.

---

## 10. A closed catalog of exactly two ASCII forms, shipped as literal skeletons

- **title:** Ship copyable skeletons for the two diagram shapes actually in use, and forbid the rest by name
- **summary:** Only two genuine ASCII diagram shapes appear in this operator's corpus — file
  trees and small dependency chains — and the model is architecturally weak at composing
  spatial text from scratch. Put literal, copyable skeletons for exactly those two forms in the
  base fragment, so the model reproduces a known-good shape rather than composing a new one, and
  name the forms that are forbidden because no good ASCII rendering exists for them. Every
  future style inherits the catalog through the base fragment rather than re-deciding format.
- **axis:** A3 Visual form selection
- **basis:** `external:` — ArtPrompt (Association for Computational Linguistics 2024,
  arXiv 2402.11753) measured GPT-4 at 25.19% accuracy on single-character ASCII-art
  recognition, and the research found no validated prompt-only technique for preventing
  width-drift, meaning any drift-prevention claim must be treated as unverified until tested.
  Prior art supports directory trees (the `tree` utility, `git log --graph`), state machines and
  sequence diagrams (the RFC 793 convention, in use for over forty years), and identifies Gantt
  charts and dense many-node graphs as known-bad with no good ASCII rendering. The IoTeacher
  ASCII dashboard gist names "inconsistent mixing of ASCII and Unicode styles" and "overusing
  borders until content becomes hard to scan" as anti-patterns and has no width-drift-prevention
  technique of its own.
- **why_it_matters:** A closed catalog inverts the failure mode. An open instruction — "use
  ASCII diagrams when helpful" — asks the model to do the thing it is measurably worst at, and
  produces drift the operator has to read past. A skeleton makes the common case a fill-in
  rather than a composition, which is the only mechanism with any prior-art support. Closing the
  catalog also settles the format question permanently: styles authored later inherit the two
  approved forms and the named prohibitions instead of each author re-litigating what ASCII is
  safe, and the ban list prevents the specific known-bad outputs rather than hoping they do not
  come up.
- **meeting_test:** Committing to a closed catalog means accepting that some future diagram
  request gets prose instead of a picture, and the team should make that trade knowingly rather
  than discovering it.

---

## 11. One formatting authority, two consumers — inherit saga's existing pytest enforcement

- **title:** Derive the base fragment and saga's formatting reference from one source, so the shared rules get a test suite the operator already wrote
- **summary:** `saga/references/formatting-style.md` is a competing formatting authority that is
  already enforced by `tests/test_saga_doc_formatting.py`, governing generated saga documents
  with rules that overlap the style's remit: paragraphs of three sentences or fewer, a one-line
  summary first, tables for comparative data, and no stacked `**label:**` lines because of a
  CommonMark collapse bug. Rather than writing a second set of rules that will drift from the
  first, make the shared subset a single source that both consume — the base fragment for
  conversational output, the saga reference for generated documents. Where they must differ,
  make the difference explicit rather than accidental.
- **axis:** A4 Style architecture and lifecycle
- **basis:** `direct:` — the grounding names the file and its enforcing test by path, lists its
  four rules, and states plainly that "a style must be compatible with it, not fight it."
- **why_it_matters:** The compounding win is that enforcement machinery already exists and is
  free to inherit — the shared rules arrive with a passing test suite rather than needing one
  built. The debt avoided is specific and likely: two authorities covering the same ground,
  edited independently, until a saga document and a conversational reply follow contradictory
  rules and nobody can say which is correct. There is also an immediately usable finding buried
  in the saga file — the CommonMark collapse bug that breaks stacked `**label:**` lines is a
  fact about how Markdown renders, not a fact about saga documents, so it belongs in the shared
  base and applies to every response the operator ever reads.
- **meeting_test:** Two formatting authorities in one ecosystem is a governance question, and
  deciding which one is primary is exactly the kind of call that gets made badly if it is made
  implicitly by whoever edits second.

---

## 12. Threshold-gated ceremony: let the style's cost scale with the turn

- **title:** Every ceremonial rule fires above a measured size threshold and stays silent below it, because a style that annoys daily gets switched off
- **summary:** Response length in this corpus is sharply bimodal — median 142 characters, 75th
  percentile 292, 90th percentile 1,658, maximum 26,994 — and the grounding warns directly that
  "a style tuned to the median will look fine daily and still fail the 10% of turns that matter
  most." Rather than choosing between a style tuned for short turns and one tuned for long ones,
  make every ceremonial rule in the style conditional on a stated trigger: turns that crossed a
  tool-use boundary, changed state, or exceed a length threshold get the verdict line and the
  closing block; a one-line factual answer gets neither.
- **axis:** A1 Turn shape
- **basis:** `direct:` — the length distribution above is measured across 16,029 main-thread
  messages, and the counter-sample established that length is explicitly *not* the discriminator
  between satisfied and frustrated replies (satisfied replies ran 835 to 4,197 characters,
  complaints 2,060 to 4,462 — overlapping ranges). The tension over pictures resolved the same
  way: the operator asked for pictures five separate times and also objected to unrequested
  ones, so the rule is about triggering rather than about format.
- **why_it_matters:** This is the multiplier on everything else in the design. A style is a
  single on-or-off choice — if its ceremony makes the fifty short exchanges of a normal day feel
  bureaucratic, it gets switched off, and switching it off costs the operator every other rule
  in the file including the ones with the strongest evidence behind them. Triggering rules are
  also the shape the evidence keeps pointing at independently: the closing block, the unrequested
  diagram, and the length ceiling are all trigger problems rather than format problems, so
  establishing a trigger vocabulary once gives every future rule a place to attach.
- **meeting_test:** The team should decide the trigger vocabulary once and reuse it, because
  three rules with three inconsistent trigger conditions is how a style becomes unpredictable
  and then gets disabled.
