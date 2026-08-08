---
date: 2026-08-07
topic: output-styles
maturity: requirements-ready
source: docs/ideation/2026-08-07-output-styles-ideation.md — all ten ranked survivors
---

# Custom Claude Code output styles — requirements

## Summary

Ship one Claude Code output style as a new plugin in `infiquetra-claude-plugins`, distributed through
the `infiquetra-plugins` marketplace that both configurations load, fixing how Claude's terminal
output is shaped: every state-changing turn closes with
a status declaration and one decision, visuals appear when the reader is being oriented and not
otherwise, and relayed subagent output is rewritten rather than pasted. Two supporting pieces ship
outside the style, because a style cannot reach subagents and these must: the word-level language
rules stay in `~/.claude/CLAUDE.md` with an annotation explaining why, and a presentation contract
reaches subagents through the `agents/` directory both configurations already share — by a delivery
mechanism that is now an open blocker rather than a settled one, because a single file in that
directory defines one agent instead of governing all of them.

## Problem Frame

Claude Code's output is measurably not serving the way this operator works, and the failure is
structural rather than stylistic.

The operator supervises five or six concurrent workstreams and does not carry the working references
of whichever thread was just opened. The two dominant prompt modes across every repository are
approval-or-continuation and status-check, which are the same underlying question: *is this waiting on
me?* Measured across 35 days, only 2.70% of sessions end on a line that answers it. The remaining 97%
close on a declarative fact, leaving the reader to derive their own next move. All ten responses that
drew a satisfied reply ended with a single concrete ask; five of nine traced complaints ended on a
trailing aside. Length and formatting do not discriminate between the two sets — placement does.

The second structural fact is reach. Output styles apply only to the main conversation thread.
**57.02% of all assistant output is generated inside subagents, where no style has any effect.** This
was verified two independent ways during ideation and reproduced afterward by a committed scorer using
a different method. Any plan to fix output behaviour with a style alone caps out at 43% of the
surface, which is why two of the ten survivors exist and why the reach partition below is a
first-class requirement rather than an implementation note.

The cost is paid in re-reading. The worst relay in the corpus was 12,347 characters of
literal unformatted JSON — a subagent findings payload delivered undigested, and one of the three
worst offenders on the mountain-of-text measurement. It is not the longest message in the corpus;
that is 26,994 characters. The distinction matters because the fix targets undigested relay, not
length. Complaints about
unrequested Mermaid diagrams sit alongside five separate requests for "pictures," every one of them
made when the operator was already lost. Those are not contradictory preferences; they are one rule
about *when* a visual is warranted, which no current instruction expresses.

## Key Decisions

Six framing choices constrain everything below. Each was settled during this brainstorm or carried in
settled from ideation.

**One style file, with per-turn triggers doing all the varying.** The evidence supports variation at
the turn, not at the repository. Response length is bimodal (median 142 characters, p90 1,658 —
unverified figures from ideation's throwaway scripts, not the committed scorer; see Assumptions), and
ideation went looking for reliable per-repository mode signal and largely failed to find it — the
`.saga/` directory marker produced a false positive in the `infiquetra-ansible-collections` repository,
which shows almost no orchestration use, and the `talaria` repository's signature was temporal and will
stop firing once that repository ships code. Shipping one style defers
per-repository selection, the `.gitignore` change it would require, and the first committed
behaviour key in any Infiquetra repository. Splitting one working style into two later is cheap;
retracting a committed behaviour key from several repositories after setting the precedent is not.

**All ten survivors ship as one release.** Chosen with the attribution cost stated and accepted. Most
survivors map to distinct measurements, so the loss is narrower than it first appears: the word-level
rules own the bare-identifier rate, the visual rules own the Mermaid rate, the relay rule owns the
long-message rate. The genuine entanglement is that the closing law and the turn-shape trigger list
both move the same three closing measurements, because the trigger list decides when the closing law
fires.

**The word-level rules do not move.** Applying the reach test to the actual text of
`~/.claude/CLAUDE.md` places every rule in the Communication section on the subagent-reaching side,
including the two that read like opening-shape rules — orienting a parent agent is precisely a
subagent's job. Nothing migrates out. The style is therefore purely additive: it carries turn-shape
content that was never in `CLAUDE.md` to begin with. This supersedes the earlier decision that
"styles absorb presentation and `CLAUDE.md` slims," which is no longer true in any part.

**The reach partition is annotated where the temptation is.** Because no rule moves, the partition
would otherwise exist only as reasoning inside a document nobody opens while editing `CLAUDE.md`. A
short header on the Communication section carries the rule and its one-question test, so a future
author applies it without re-deriving the research.

**The style's tell is plain text, not a drawn box.** The `★ Insight` box is retired as a box —
box-drawing is a rivalrous salience resource that should be spent on file trees and real pictures —
but its marker function is preserved as a distinctive literal string. That marker is load-bearing
beyond this project: `docs/engineering-journal/LEARNINGS.md` in the plugins repository (the entry at
line 4171) uses it as one of three conjoined signals that revealed the "agy" teammates on issues 278
and 279 were Claude clones rather than the external command-line tool, which invalidated an
experiment's provenance. The other two signals are the absence of any `agy --model` shell call and the
presence of `Write`/`Edit` calls against repository files. The marker is therefore not sufficient on
its own, but it is the cheapest of the three to grep for, and retiring its function would have
degraded a diagnostic in active use.

**The style-file contract shrinks but does not disappear.** With a single file there is no shared base
to hold in sync, so the byte-identity test has nothing to police. The two clauses that carry the actual
risk remain: `keep-coding-instructions` must be written `true` explicitly, and the style must placard
what it suppresses.

**Everything lands in `infiquetra-claude-plugins`, with the style as one new plugin.** The style ships
as a new plugin directory registered in the marketplace, beside `saga`, `deploy`, and the rest. The
scorer, its tests, the captured baseline, and the documents that justify the rules ship in the same
repository at their established repo-root locations rather than inside the plugin directory — see R34,
which records the placement and why. Nothing remains in `~/bin`, which held this work only because it
happened to be the ideation session's working directory.

The transfer is done: all six paths are present in the repository as untracked additions, the 29
scorer tests pass there, and the scorer reproduces its headline 57.019% figure from that checkout.
A git worktree is not required. The feature branch that made one advisable has landed — commit
`e2ba7db5` on `main` is that work, and `feat/684-u7-delete-lease-broker-and-orphan-evidence` no longer
exists on `origin` — so a plain branch off `main` is sufficient.

**Plain English rule 2 keeps its text; R19 is its enforcement test.** The mechanical grammatical
prohibition sits beside the ratified rule rather than rewriting it, consistent with the ruling that all
seven rules stay as written.

## Actors

Three parties whose different reach is the central constraint of this work.

- A1. **The operator** — reads terminal output while supervising several concurrent workstreams, and
  is the only consumer whose comprehension the presentation rules exist to serve.
- A2. **The main thread** — the only surface an output style governs. Also the copy desk: everything a
  subagent produces reaches the operator only by passing through here.
- A3. **Subagents** — generate 57.02% of assistant output, are unreachable by any style, and are
  governed instead by three levers of unequal reach: `~/.claude/CLAUDE.md`, which reaches every
  subagent; definition files under the shared `agents/` directory, each of which reaches only
  invocations naming that one agent; and the spawn prompt the main thread writes, which reaches only
  that one spawn. R27 depends on this distinction and is where it bites.

## Key Flows

Three turn shapes the style must produce. The distinction between the first two is what keeps the
ceremony from becoming noise.

- F1. **Full-orientation turn.** **Trigger:** first substantive turn of a session, a topic change,
  return from a long tool run, or a subagent returning. **Behaviour:** situate the reader — which
  repository, which system, why it matters now — then deliver findings, then close with the state
  declaration and the single decision. A visual is required, not optional. **Covers R6, R7, R11.**
- F2. **Delta turn.** **Trigger:** any turn that is not F1 and is above the size threshold.
  **Behaviour:** report only what changed since the last full orientation, anchored to it, with no
  re-establishment of context and no unrequested visual. Closes the same way F1 does. **Covers R6, R8,
  R10.**
- F3. **Subagent relay turn.** **Trigger:** a subagent has returned and its findings are being
  delivered. **Behaviour:** the main thread states its own verdict first, then presents digested
  findings in its own voice. The raw payload is never the body of the reply. This is simultaneously an
  orientation turn, so a visual is required. **Covers R22, R23, R25, R11.**

## Requirements

### Turn shape — the closing law and the two shapes

- R1. Every turn that changed state ends with a closing block stating what is now true, what is
  unfinished, and the one decision that belongs to the operator.
- R2. The closing block declares state, not activity. A line describing what the agent did, rather
  than what is now true, does not belong in it.
- R3. The closing ask is written as pre-committed branches (`if X then I will Y`) so that "go" is a
  complete answer.
- R4. Nothing follows the closing block. No trailing aside, no restatement of the middle, no further
  declarative content.
- R5. The closing block does not restate anything the statusline already renders: model, effort,
  context percentage, cost, branch, or pull-request review state.
- R6. Two turn shapes exist — full orientation and delta — and every turn is one of them.
- R7. Full orientation is triggered by an enumerated, named list of conditions, not by judgement.
- R8. A delta turn reports only what changed and is anchored to the last full orientation.
- R9. Turns below a size threshold are exempt from the closing ceremony entirely.

### Visual form — when a visual appears and what shape it may take

- R10. Routine turns receive no unrequested visual of any kind. Routine means a progress update, a
  single-file edit, a command result, or an approval acknowledgement.
- R11. Orientation turns require a visual. Orientation means the operator asked where things stand, a
  subject is being introduced for the first time this session, a subagent's findings are being
  delivered, or more than two entities relate to one another.
- R12. A comparison of three or more items sharing attributes is rendered as a table.
- R13. An explicit request for a visual overrides the phase gate in either direction.
- R14. Only forms whose correctness is line-local are permitted, drawn identically every time. Any
  form requiring a character on one line to align with a character nine lines away is forbidden.
- R15. Syntax is keyed to destination. Bytes bound for the terminal use the permitted catalog; bytes
  bound for a file, a pull-request body, or a rendered artifact use Mermaid.
- R16. Box-drawing characters are reserved for file-tree connectors and genuine pictures. They are not
  used for callouts, banners, or emphasis.

### Word-level discipline — and where it lives

- R17. All seven Plain English rules remain in `~/.claude/CLAUDE.md`, unpruned and unrewritten.
- R18. The Communication section of `~/.claude/CLAUDE.md` carries a short annotation stating that its
  rules live there rather than in a style because `CLAUDE.md` reaches every subagent while a style
  reaches only the main thread, and giving the test for any future move: does this rule mean anything
  to an agent whose output is read by another agent?
- R19. The prohibition on bare identifiers is expressed mechanically and testably: an issue number,
  commit hash, branch name, test name, or `path:line` reference may only appear in apposition to a
  noun naming what it is, never as a sentence's subject or object. This sits **beside** Plain English
  rule 2 as its enforcement test, and does not replace or rewrite that rule's text.
- R20. An abbreviation used fewer than three times in a response is not introduced at all, and the
  `Full Name (ABC)` introduction pattern is not used — needing the introduction is evidence the short
  form should not exist.
- R21. R20 carries a closed exemption list. A naive all-caps trigger misfires on roughly half of the
  most common all-caps tokens in the corpus, including `NOT`, `DONE`, `PASS`, `GET`, `POST`, and
  `HEAD`.

### The subagent seam — the 57% the style cannot reach

- R22. The main thread never emits a raw subagent payload as the body of a reply. A subagent's return
  is source material, not output.
- R23. Quotation from a subagent return is limited to a few contiguous lines, and only when the exact
  text is load-bearing.
- R24. R22 and R23 carry a carve-out: verbatim reproduction is correct for exact error strings, diff
  hunks, and command output whose precise characters matter.
- R25. A relay turn opens with the main thread's own verdict, not with the subagent's framing.
- R26. Every spawn prompt the main thread writes carries a fixed presentation contract stating the
  expected return format.
- R27. A shared presentation preamble reaches subagents through the `agents/` directory. The symlink
  half of this is verified: `~/.claude-company/agents` points at `~/.claude/agents`, so any file placed
  there is seen identically by both configurations, and it may ship before the plugin does. The reach
  half is not what the earlier wording assumed, and the difference is load-bearing. A `.md` file in an
  `agents/` directory **defines one named agent**; it does not prepend text to other agents' prompts.
  Every one of the 36 agent definitions in `infiquetra-claude-plugins` is a single agent keyed by a
  `name:` frontmatter field, and `~/.claude/agents/` is currently **empty** — every agent available in
  a session today ships from a plugin's own `agents/` directory or is built into Claude Code. A single
  file dropped into `~/.claude/agents/` would therefore govern zero of the subagents that actually run.
  How the contract reaches them instead is an open blocker; see Outstanding Questions.

### Style-file contract

- R28. The style declares `keep-coding-instructions: true` explicitly rather than relying on the
  default, which is `false` and silently removes Claude Code's built-in guidance on scoping changes,
  writing comments, and verifying work.
- R29. The style carries a placard section naming what it suppresses and what compensating behaviour
  replaces it.
- R30. A test asserts R28 and R29 hold, so neither can be lost to an edit.

### Verification

- R31. The style emits a distinctive literal string that no other style emits, containing no
  box-drawing characters, so that the active style can be confirmed by grep rather than by impression.
- R32. The scorer gains a measurement for visual gating — whether visuals appear on orientation turns
  and stay absent from routine ones. It has none today.
- R33. The scorer gains a measurement for relay quality, distinguishing a digested finding from a
  pasted payload. It has none today.

Because R32 and R33 add metrics after the baseline was captured, they need a stated route to a
"before" value, and the obvious wrong route is tempting. **`docs/measurements/2026-08-07-baseline.json`
is never regenerated.** It is a snapshot of behaviour before any custom style existed, and that window
closed permanently the moment one ships; re-running the scorer over its own path would overwrite the
only record of the unstyled world with a styled measurement and call it a baseline.

The right route costs nothing. Transcripts are immutable once written and the ones in the measured
window are still on disk — 2,515 files carry a modification time inside 2026-07-03 to 2026-08-07. So
the extended scorer is pointed at **the same window with `--since 2026-07-03 --until 2026-08-07` and a
new `--out` path**, which yields genuine pre-style values for the new metrics without touching the
committed file. Re-running the scorer to any path other than the committed baseline is safe and
encouraged; re-running it to that path is not.
- R34. The scorer, its tests, and the captured baseline ship in `infiquetra-claude-plugins` at the
  repository's established locations — `tools/output_style_scorer.py`,
  `tests/test_output_style_scorer.py`, and `docs/measurements/` — not inside the new plugin directory.
  This is already done; the six paths are present as untracked additions and the 29 tests pass there.
  Repo root is the correct home rather than the plugin directory for three reasons: `pyproject.toml`
  sets `testpaths = ["tests", "plugins/*/tests"]`, so repo-root `tests/` is canonical; the committed
  baseline's own reproduce command and its `instrument:` frontmatter both name
  `tools/output_style_scorer.py`, and moving the file silently breaks a recorded reproduction; and the
  Success Criteria and Sources sections of this document already cite that path. The earlier wording,
  "ship inside the new plugin", contradicted all four and is superseded.

  One consequence of repo root must be carried into planning rather than discovered later. Continuous
  integration runs `ruff check .` and `ruff format --check .` repo-wide, so `tools/` is linted and
  format-gated; but it runs `mypy plugins/ scripts/ tests/` and `bandit -r plugins/ scripts/ tests/`,
  which **exclude** `tools/`, and `pytest --cov=plugins`, which gives the scorer's 29 tests no
  coverage credit. The scorer type-checks clean under `mypy --ignore-missing-imports` when pointed at
  it by hand, so the gap is one of enforcement, not of correctness.
- R35. The provenance procedure in the plugins repository's `docs/engineering-journal/LEARNINGS.md` is
  updated to reference the new tell, so the diagnostic that detects Claude-clone teammates keeps
  working across the change.
- R36. **Satisfied.** The ideation document, this requirements document, the ideation run directory,
  and the baseline are in `infiquetra-claude-plugins` as untracked additions awaiting their first
  commit, so the artifacts that justify the rules are version-controlled with the rules themselves.
  Nothing here remains outstanding; the requirement is retained for traceability rather than as work.

## Acceptance Examples

Covering the requirements whose shape is conditional, which is where prose alone leaves room for
invention.

- AE1. **Covers R10, R11.** The operator asks "where are we with the migration?" after a day away.
  This is an orientation turn: it opens by situating (which repository, which stage, what changed since
  they last looked), includes a visual, and closes with the state declaration and one decision. The
  next turn, "go ahead," produces a delta turn with no visual at all.
- AE2. **Covers R13.** In the middle of a routine sequence of file edits the operator asks "can you
  draw me how these three modules call each other?" The phase gate says routine, but the explicit
  request overrides it and a visual is produced.
- AE3. **Covers R15.** The same dependency relationship is being expressed twice in one turn: once in
  the terminal reply and once written into a pull-request body. The terminal gets a single-line arrow
  chain from the permitted catalog; the pull-request body gets Mermaid, because that surface renders
  it.
- AE4. **Covers R22, R24.** A subagent returns 12,000 characters of findings including a stack trace.
  The reply opens with the main thread's own verdict, presents the findings digested in its own voice,
  and reproduces only the stack trace verbatim — because its exact characters are load-bearing, which
  is what the carve-out is for.
- AE5. **Covers R9.** The operator asks "what's the branch name?" The answer is one line. No closing
  block, no state declaration, no ceremony — the turn is below the threshold, and wrapping a one-line
  answer in structure is its own friction.
- AE6. **Covers R1, R4.** A turn completes a migration and discovers one unresolved question. It ends
  with what is now true, what is unfinished, and the question — and then stops. It does not append a
  summary of what was done, a note about what the agent found interesting, or an unrelated
  observation.
- AE7. **Covers R19.** "#656 is green" is a violation. "Pull request #656 is green" is not. The test is
  grammatical and greppable rather than a matter of judgement.
- AE8. **Covers R3.** A turn ends with work paused on a test result that is not back yet. "Let me know
  how you want to proceed" fails R3, because the operator must derive the branches before answering.
  "If the suite comes back green I will merge and delete the branch; if it fails I will stop and bring
  you the failing case" satisfies it, because the branches are written in advance and "go" is now a
  complete answer. This is the I-PASS contingency element named in Sources — the least-copied part of
  that format, and so the part most likely to be quietly dropped.

## Success Criteria

The measurements that decide whether this worked, all produced by `tools/output_style_scorer.py`
against the captured baseline in `docs/measurements/2026-08-07-baseline.md`.

| Measurement | Baseline, 2026-08-07 | Direction |
| --- | ---: | --- |
| Sessions ending with a closing ask | 2.70% | Up, substantially |
| Turns ending with a closing ask | 5.53% | Up, substantially |
| Turns opening with a plain-language verdict | 2.98% | Up |
| Messages of 4,000+ characters | 1.16% | Down |
| Main-thread messages containing Mermaid | 0.05% (7 messages) | To zero |
| Messages with a bare identifier as a noun | 1.69% | Down |

Every figure in this table was re-derived from `docs/measurements/2026-08-07-baseline.json` and agrees
with it to the stated precision. The table carries directions and no target values, which is a
deliberate gap rather than an omission — but it is a gap, because a direction alone cannot decide
whether the work succeeded, and "up, substantially" is not a test anything can fail. Picking the
numbers is listed under Deferred to planning. The two new metrics R32 and R33 add do not appear here,
because they have no baseline value until the extended scorer is re-run over the archived window as
R33's note describes.

Two qualitative criteria that no measurement covers:

- The style is not switched off. A ceremony that fires on fifty short exchanges a day becomes noise,
  and a style that gets disabled costs every rule in the file, not just the annoying one. R9's
  threshold exemption is the control for this, and its adequacy is a judgement the operator makes from
  use.
- The active style can be confirmed rather than assumed. Today a style change has no confirming
  signal, which conflicts with the standing rule that "fixed" requires one.

## Scope Boundaries

Named because several are tempting and one was explicitly deferred rather than rejected.

- **Per-repository committed settings** — deferred by the one-style decision, not cancelled. Revisit
  when a repository demonstrates a durable need the per-turn triggers cannot serve.
- **The `.gitignore` change in the plugins repository** — `.claude/` is ignored wholesale there
  (`.gitignore` line 56, and `git ls-files .claude/` returns nothing), so committing any per-repository
  setting requires changing it first. Deferred with the setting itself.
- **A second style file** — unnecessary with one file, and with it the byte-identity test that would
  have policed the two style files against each other.

  The byte-identity test itself is **not** retired, because ideation asked for it twice for two
  different artifacts. Survivor 7 wanted it to police two style files, which the one-style decision
  does dispose of. Survivor 10 wanted the same test for a different reason — the presentation preamble
  "duplicates a block across N definition files" — and that reason survives untouched by the one-style
  decision. If R27's blocker resolves toward duplicating the preamble into each agent definition, the
  test comes back with it. Retiring it on survivor 7's reasoning alone would drop a control survivor 10
  still needs.
- **Any generator or build step** — settled during ideation. Whatever ships must be plain Markdown
  because there is no build step in the loading path, so a generator would only ever have been an
  authoring convenience, and it creates a class of bug where editing a shipped file is silently
  reverted.
- **Pruning any Plain English rule** — closed. Absence of a traced failure in a 35-day window is not
  evidence a rule is idle; it is equally consistent with the rule working.
- **The bare-Default control run** — still open as a question, not scheduled as work. See Outstanding
  Questions.
- **`force-for-plugin: true`** — not used. The plugin does not override the operator's own style
  selection.
- **Any change to subagent behaviour beyond the three named vehicles** — `CLAUDE.md`, the shared
  `agents/` directory, and the spawn prompt. There is no fourth lever.

## Dependencies / Assumptions

Load-bearing facts this work rests on. The first four were verified during this brainstorm; the rest
are assumptions and are labelled as such.

**Verified.**

- `~/.claude-company/agents` is a symlink to `~/.claude/agents`, so one edit to an agent definition
  governs both configurations. R27 depends on this.
- `~/.claude-company/CLAUDE.md` is a symlink to `~/.claude/CLAUDE.md`. One physical file governs both
  configurations, which makes R17 and R18 cheap — but also means the reach partition cannot differ
  between the personal and work configurations without breaking that symlink.
- Neither configuration has an `output-styles/` directory today. This is greenfield; nothing is being
  migrated or overwritten.
- No plugin in the marketplace currently declares an output style. This would be the first. The
  marketplace holds 11 plugins at the time of review.
- `~/.claude/agents/` is empty. The symlink is real but currently shares an empty directory, so no
  subagent in either configuration is governed by anything in it today. R27 turns on this.
- Neither `~/.claude` nor `~/.claude-company` is a git repository. This is the same condition that
  R34 cites as the reason to move the scorer out of `~/bin`, and it applies undiminished to the two
  deliverables that stay outside this repository: the R18 annotation and the R27 preamble. Both will
  be unversioned and unbacked wherever they land. Whether that is acceptable is a planning question,
  not a settled one — the transfer solved the problem for the scorer and left it standing for the
  other two.

**Assumed.**

- The trigger lists in R7 and R11 are guesses until used. Ideation says so explicitly, and flags
  "after any subagent returns" as possibly one trigger too many given how much of this operator's work
  is agent fan-out. Expect to revise them after first contact.
- The size threshold in R9 is unset, and the two figures usually quoted to bound it are weaker
  evidence than they look. Median response length of 142 characters and p90 of 1,658 come from
  ideation's throwaway scripts, not from the committed scorer, which computes no length percentiles at
  all and so cannot re-derive either number. That matters because the same class of throwaway script
  produced the one figure the instrument later proved wrong: ideation's mountain-of-text rate of 0.25%
  was a `head -40` display cap misread as a count, and the true rate is 1.16%, roughly 4.7 times
  higher. Treat 142 and 1,658 as unverified until either the scorer grows a length-distribution
  measurement or they are re-derived some other way. R9's threshold is the most operationally
  consequential unset number in this document, and it currently rests on the least verified pair.
- The baseline was recorded while Claude Code's built-in Explanatory style was active. It therefore
  measures *current* behaviour, not *unstyled* behaviour, and sits on both sides of any comparison
  drawn against it.

## Outstanding Questions

**Resolve before planning.**

The two prior blockers were settled on 2026-08-07 and are recorded in Key Decisions. The document
review on 2026-08-07 opened one new one.

- **How the presentation contract actually reaches subagents (R27).** The requirement named the
  `agents/` directory as the vehicle and assumed one file there would govern every subagent. It will
  not: a `.md` file in `agents/` defines one named agent, and `~/.claude/agents/` is empty today, so
  the file would govern nothing that runs. Three candidate routes exist and the choice is an
  architecture decision, not a detail. (a) Duplicate the preamble block into every agent definition
  file, which is what ideation's survivor 10 actually proposed, and restore the byte-identity test to
  police the copies. (b) Put the contract in `~/.claude/CLAUDE.md`, which is the one lever verified to
  reach every subagent — but which cuts against the Key Decision that the style is purely additive and
  that `CLAUDE.md` is not growing presentation content. (c) Rely on R26's per-spawn contract alone and
  drop R27, accepting that coverage then depends on the main thread remembering to stamp every spawn.
  This blocks planning because it decides whether R27 survives, whether the byte-identity test returns,
  and how much of the 57.02% out-of-reach surface the work claims to address.

**Deferred to planning.**

- The plugin's name, which is permanent and appears in the marketplace listing beside `saga`,
  `deploy`, and `fleet-core`. A recommendation is on the table and the choice is the operator's; it is
  not made here.
- The concrete size threshold for R9. Note that the two figures usually quoted to bound it, median 142
  and p90 1,658, are unverified and not reproducible from the committed scorer — see Assumptions
  before treating them as a range.
- The target values behind the Success Criteria directions. The table says "up, substantially" and
  "down", which cannot decide whether the work succeeded.
- The exact membership of the trigger lists for R7 and R11.
- The literal text of the tell in R31.
- The closed exemption list in R21.
- How R32 and R33 detect what they detect. Both measure something no current metric approximates, and
  the detection approach is a design question rather than a product one.
- Whether the two deliverables that land outside this repository, the R18 annotation and whatever R27
  resolves to, need a version-control home of their own, given that neither `~/.claude` nor
  `~/.claude-company` is a git repository.
- Whether `tools/` should be added to the `mypy` and `bandit` scopes in continuous integration, so the
  scorer is gated rather than merely lintable. See R34.

**Open, and deliberately not resolved here.**

- The bare-Default control run. Every baseline number was recorded under the Explanatory style, so a
  two-week run on Default would separate problems that style caused from problems it failed to prevent.
  The one-style decision does not force the question either way, and the cost is delaying everything
  by two weeks.

## Sources / Research

Breadcrumbs a planner reading this cold would need.

- `docs/ideation/2026-08-07-output-styles-ideation.md` — the ten ranked survivors with their evidence
  and downsides, fifteen revivable rejected ideas with reasons, and the decisions settled after
  publication.
- `docs/measurements/2026-08-07-baseline.md` — the pre-change measurements, how each is computed, and
  a reconciliation against the ideation document including one figure the ideation document got wrong.
- `tools/output_style_scorer.py` and `tests/test_output_style_scorer.py` — the instrument, 29 tests.
- `docs/ideation/2026-08-07-output-styles-run/` — the six frame-agent outputs behind the survivors, including the
  cross-domain frame that supplied the external prior art.
- `~/.claude/CLAUDE.md` — the ratified global rules, 99 lines. The Communication section is the
  largest, spanning lines 15 to 40 for 25 lines of content under its heading, and holds all seven
  Plain English rules.
- `docs/engineering-journal/LEARNINGS.md` in `infiquetra-claude-plugins`, the entry at line 4171 — it
  establishes the `★ Insight` marker as one of three conjoined provenance signals, which is why R31
  preserves the marker's function while retiring its box, and why R35 updates the procedure rather
  than leaving it pointing at a retired form.
- External prior art carried forward from ideation, strongest first: Starmer et al., *NEJM*
  2014;371:1803-12 (the I-PASS handoff, the only such format with a measured outcome effect — a 23%
  reduction in medical errors across 10,740 admissions, whose least-copied element is contingencies
  written in advance so the receiver selects rather than derives); 14 CFR 121.542, the sterile flight
  deck rule, which both suppresses and *mandates* communication by phase; 14 CFR 91.213, the Minimum
  Equipment List discipline of placarding a degraded state where the crew sees it; US Army *ADP 5-0*
  on fragmentary orders, which fill only changed paragraphs against a standing base order.
