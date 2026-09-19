# Where Jev-style typed judgments fit in infiquetra-agent-operations

This brief surveys `/Users/jefcox/workspace/infiquetra/infiquetra-agent-operations`, the operator's
private coordination record for coding-agent sessions, for places a fast typed-judgment model could
plug into its daily operating loop. The model, TypeSafe AI's Jev, is a "System One" model: the caller
posts a block of state (text or JSON, up to roughly 32,000 tokens) plus a batch of typed questions, and
gets typed answers back in about 0.35 seconds at $0.042 per million input tokens, with no free-text
generation. Three question shapes: **noul** (yes/no, answered with a probability), **choice** (pick
one option from a list, returned with the full probability distribution and a confidence value), and
**score** (place something on an ordered scale, returned as a weighted score plus per-level
probabilities and confidence). Many independent questions batch into one request. It performs poorly
on arithmetic, comparing dates, and adversarial or manipulated input, and answers literally.

## A. How the daily operating loop works

The repository is the durable companion to a recurring Codex voice task called "Daily Operations" in
Codex Desktop (Codex is OpenAI's coding-agent product). The voice task is a long-lived spoken
conversation the operator returns to across days; because its transcript does not survive app restarts
or context compaction cleanly, this repository holds the state that must survive those events: the
queue, workspace snapshots, handoffs, and a journal. Herdr, named throughout, is the terminal-
multiplexer product that holds many coding-agent sessions ("panes") open across work areas
("workspaces") at once.

The loop as an arrow chain: **start of day** -> open the pinned Daily Operations task and start voice
chat -> read `docs/operations/session-queue.md` -> refresh only the workspaces the operator actually
asks about, from Herdr, GitHub, and the source repositories, never from the file alone ->
**during the day** -> for each workstream, read its status and pick which of a small set of labels
applies (Section B); for a new multi-session workspace or a Lead-to-Lead handoff, follow
`docs/operations/lead-handoff-role-boundaries.md` to build an explicit role table before work starts ->
attend to sessions by reading Herdr lifecycle state plus the agent's own reported result, never the
lifecycle label alone -> update the queue and `docs/operations/workspaces.md` only when the
observation will guide later work -> **end of day** -> follow the nine-step
`docs/operations/end-of-day-closeout.md` runbook: fix a cutoff time, refresh only the sources actually
discussed, sort every discussed workstream into one of four queue buckets, refresh the workspace
snapshot, write that day's file under `docs/operations/daily/`, promote durable knowledge into the
engineering journal, sweep for anything sensitive, run `python3 scripts/check_docs.py` and
`git diff --check`, and push through a pull request.

Artifacts written: `session-queue.md` (current attention, a snapshot only), `workspaces.md` (a
timestamped Herdr inventory), one dated file per day under `daily/`, Lead-handoff or workspace-planning
documents for multi-session runs, and entries in `docs/engineering-journal/{LEARNINGS,DECISIONS,
QUEUED,ARCHIVE}.md`, plus occasional standalone files under `narratives/` or `audits/` for write-ups
too long for one journal entry. The voice task itself is never edited by this loop; it is the spoken
front end, and everything above is what the next voice session, or the next person, reads to
reconstruct where things stand without replaying the conversation.

## B. Recurring decisions table

Each row is a judgment made repeatedly today, by a human, a prose rule an agent applies by hand, or a
script. "Candidate primitive" names the Jev question shape that fits the decision's shape, not a claim
that the decision should run unsupervised.

| # | File (lines) | Decision | How it is made today | Input available as state | Primitive | Benefit | Risk |
|---|---|---|---|---|---|---|---|
| 1 | `session-queue.md:95-141` | Which of four buckets (Needs Operator / In Progress / Waiting / Parked) a workstream belongs in | Prose judgment, reading Herdr state and the last agent report | Latest status text; whether a blocker is named | choice (4) | Instant label instead of re-reading a paragraph, every workstream, every day | Wrong bucket if the pasted status is already stale |
| 2 | `tooling.md:125-138` | Which of seven status words (Working/Idle/Waiting on process/Waiting on agent/Waiting on operator/Complete/Unknown) fits one session | Prose judgment on Herdr's lifecycle label plus last output | Lifecycle label + last terminal text | choice (7) | Reused in the queue, inventory, and daily record | Herdr `idle`/`done` is explicitly not proof of success; a model reading only the label repeats that mistake |
| 3 | `operating-model.md:43-58` | Classify a problem claim as a requirement, a suspected gap, or a verified defect before authorizing repair | Three-way prose rule, applied by hand under delivery pressure | Claim text plus any attached evidence | choice (3) | Same triage recurs on every incoming defect report | Wrongly calling something a verified defect can authorize repair that should not happen; keep advisory only |
| 4 | `QUEUED.md:60,64,155,359,374` | Priority tier (P0 highest to P3, or an unscheduled Maybe list) for a newly deferred item | Whoever writes the entry picks by feel | Short description plus reason for deferral | score | Consistent triage across many small deferred items | Real priority depends on business context this repository does not hold |
| 5 | `end-of-day-closeout.md:88-97` | Which of five journal destinations (LEARNINGS/DECISIONS/QUEUED/ARCHIVE/standalone write-up) fits a piece of knowledge | Applied by hand every evening | Short description of the item | choice (5) | Happens every closeout; a clean text-to-category task | "Learning" versus "decision" is fuzzy even in the source material |
| 6 | `unattended-orchestration.md:107-111` | Whether a supervising Codex task is a genuine persistent monitor or "misconfigured" (one snapshot, empty turn while blocked, timer polling, doing the work itself, idling after one report) | Transcript read against a five-way prose checklist | The monitor's recent turns, as text | noul x5 | Documented failure (2026-09-09, 2026-09-11); cheap insurance every time a monitor starts | Passing the checklist does not prove the monitor is alive right now |
| 7 | `docs/reference/models/README.md:58-69` | Whether a proposed roster row is Launchable, Capable, and Behaves | Three reference files read by hand | Matching launch-surface, benchmark, and observation rows | noul x3 | Already the named procedure for every roster review | "Capable" mixes real measurements with unverified claims |
| 8 | `docs/reference/models/operational-observations.md` (whole file) | Which status label ("Failure observed," "Observed," "Unresolved," "Unverified claim") fits a new behavior row | Whoever appends the row picks it | Observation text plus any evidence link | choice (4) | Keeps vocabulary consistent as sessions append rows over time | Low stakes; existing writers usually get it right anyway |
| 9 | `lead-handoff-role-boundaries.md:255-256` | Whether a Lead's rendered handoff matches the approved roster (one Code Reviewer, two distinct repair-developer roles, correct accounts) | Operator compares by hand | Approved roster table plus the Lead's reply text | noul, batched | Already failed once: a Lead's own plan used loose "expert reviews" wording implying an unapproved reviewer | The failure was semantic; a literal-reading model can miss a differently worded repeat |
| 10 | `lead-handoff-role-boundaries.md:137-146` | Whether an operator correction is scoped to one batch or the whole run, and whether that scope is ambiguous | Prose rule; a coordinator once over-applied a narrow exception run-wide | The correction's own wording | noul | Catches under-specified instructions before over-generalization | Model is weak on ambiguous phrasing, the exact failure mode here |
| 11 | `lead-handoff-role-boundaries.md:24-26,109-111` | Whether a proposed test case is backed by a demonstrated defect or contract gap, versus open-ended edge-case generation | Architect or Lead judges by hand | Proposed case plus the gap it claims to cover | noul | Filters the scope creep the source material calls out | Telling real gaps from manufactured ones needs domain knowledge a short state block may lack |
| 12 | `unattended-orchestration.md:78-89` | Whether a review finding blocks the first operator-usable build (prevents build/launch, is destructive/irreversible, crosses a credential/data/security boundary) or must wait | Reviewers apply this by hand under delivery pressure | Finding text plus any attached evidence | choice (blocks / waits) | Recurs every review cycle, every run | Launch-gating; must narrow reviewer attention, never replace sign-off |
| 13 | `session-queue.md` + `workspaces.md` (whole files) | Given several open workstreams, which to attend to next | Operator scans both files and picks | Per workstream: bucket, time since last touch, named blocker | score, then rank | Minutes of re-reading become a ranked list almost instantly | Urgency the text omits (a person waiting, a cost accruing) will not surface |
| 14 | `workspaces.md:175-180` | Whether a workspace is stale/abandoned or legitimately still open | No real check today; rule only says preserve "unless authorized," so staleness accumulates unseen | Last-observed timestamp, current date, last stated reason it was kept | score (leak risk) | A real, currently empty gap this would fill | Date comparison is a named weakness; elapsed days must be computed in code first, never asked of the model |
| 15 | `daily/README.md:32-40`; `daily/2026-09-12.md:63-69` | Whether a daily-record item is settled (drop) or needs a named follow-up (carry forward) | Writer judges each item by hand | Outcome text; whether a next action and owner are named | noul | Applied to every item, every daily record | "Settled" can hide missing live evidence, as when a passing check read as complete while a required review was still open |
| 16 | `end-of-day-closeout.md:51-58` | Same four-way bucket as row 1, applied at closeout, including whether the item drops out of the queue entirely | Closeout step 3, by hand | That day's discussion and evidence | choice (4, or remove) | Same benefit as row 1, concentrated at one checkpoint | Same staleness risk as row 1 |
| 17 | `single-issue-delivery.md:8-16` | Whether an issue fits the lightweight single-issue loop's five preconditions, or needs the heavier orchestration runbook or a Brainstorm pass | Reader judges each bullet by hand | Short description of scope and settledness | noul x5, or choice of route | Runs before every new piece of work starts | "Settled enough to plan" can be faked by a well-written but under-specified issue |
| 18 | `unattended-orchestration.md:122-134` | Whether a parent issue is "decision-complete" enough to launch an unattended run, i.e. nine listed questions each have a real answer | Reader checks each question by hand | Parent issue body text | noul x9 | Concrete, repeatable precondition gate; a missing answer here is what stalls a run mid-flight | Presence of an answer is not the same as a good one |
| 19 | `lead-handoff-role-boundaries.md` (controller continuation contract) | Which client/model/effort to assign as Lead/Delivery Manager for a new run | Explicitly not resolved by benchmark ranking; a required bounded live test plus operator choice decides | Dated, evidence-labeled rows in `operational-observations.md` | score/choice, advisory input only | Fast summary of track record before the required live test | The most explicitly warned-against use in the repository: the controller-selection note says its own ranking "must not determine staffing defaults" |
| 20 | `lead-handoff-role-boundaries.md` (recovery bullets) | Whether a Lead's callback is a completed assignment or just a claim of one | Prose rule, checked by hand | Report text plus cited evidence link | noul | Targets the most common failure pattern described: progress claimed without durable evidence | Confident prose without real evidence can fool a text judgment the same way it fools a person; the link still needs a real fetch |
| 21 | `docs/reference/models/launch-surface-2026-09-12.md:60-71` | How strong a proposed model identifier's "proof status" already is | Reader reads the table row by row | Proof-status text already in the table | score | Quick triage of which rows need a disposable test launch | Small gain; close to a lookup already |
| 22 | Pattern in `2026-09-13-l7-web-app-recovery-handoff.md` | For each blocked child issue, which existing role is accountable and the next authorized step | Lead rebuilds this table by hand for every recovery handoff | Child issue description plus the roster's role list | choice (pick role) | Saves real first-draft time on a table built fresh each time | Right role often depends on which repository or provider owns the work, scattered across prior issues |

## C. Runbook inventory

No `docs/runbooks/` directory exists; runbooks live under `docs/operations/`, named by function, plus
one unrelated runbook for a periodic retrospective process.

| Runbook | Purpose | Steps with a judgment call | Where a typed judgment could be inserted |
|---|---|---|---|
| `voice-console.md` | Resume/operate the recurring Codex voice task | "Surface real decision gates; do not ask for routine continuation already authorized" (line 22); distinguish working/idle/waiting-on-process/waiting-on-agent/waiting-on-operator (line 33) | At "Beginning Of A Work Period": a choice call per queue item, state = its latest status text |
| `operating-model.md` | States the operating loop and its evidence rules | Requirement/suspected-gap/verified-defect triage (lines 43-58); report what's known/unknown when evidence is partial (line 36) | A choice call when a new claim is logged, before escalation to repair |
| `tooling.md` | Reference for the `agents` launcher, Herdr, and the shared status vocabulary | Mapping raw evidence to one of seven status words (lines 125-138) | A choice call whenever a session's state is written into the queue or inventory |
| `end-of-day-closeout.md` | The nightly settlement procedure | Step 3's four-way bucket choice (51-58); step 6's five-way journal-destination choice (88-97) | Two choice calls: one per workstream for the bucket, one per knowledge item for the journal file |
| `unattended-orchestration.md` | Prepare, launch, supervise, resume, and close an objective-wide Orchestrate run | Parent decision-completeness, nine questions (122-134); monitor misconfiguration, five patterns (107-111); checkpoint-blocking, two-way (78-89) | noul batches at preflight (completeness, monitor health); a choice at each review-finding triage |
| `single-issue-delivery.md` | The smaller, three-agent-tab loop for one settled issue | "When This Fits," five preconditions (8-16) | noul x5 at intake, before a workspace is created |
| `lead-handoff-role-boundaries.md` | Closest thing to a handoff template: preparing and verifying a multi-session handoff | Roster-match checklist (255-256); scope-ambiguity check (137-146); demonstrated-defect check for new tests (24-26, 109-111) | noul batch right after the incoming Lead's first understanding-check reply, before dependent dispatch |
| `controller-model-selection-and-loop-discipline.md` | A research note (marked "not operating policy") on model/loop-discipline choices for the Delivery Manager role | Which client/model to assign as controller | Flagged as needing the strongest disclaimer: the document itself calls its own ranking unproven |
| `docs/reference/models/README.md` | Standing procedure for reviewing any proposed roster, not a step runbook | Launchable/Capable/Behaves check (58-69) | noul x3 per candidate, drawing on the launch-surface, benchmark, and observation files |
| `docs/operations/retrospectives/RUNBOOK.md` | Periodic, evidence-led retrospective across a batch of past runs | Classifying collected evidence into schema record types | Out of scope for the daily loop: runs occasionally, after the fact, on closed work |

## D. Handoff format

Two kinds of document are called "handoff," and neither has one blank template file; both follow a
shape by convention plus the prose rules in `lead-handoff-role-boundaries.md`.

**Lead handoffs** move ownership of a multi-session Herdr workspace between coordinating sessions
("Leads"), often across different coding-agent products. The clearest recent example,
`2026-09-15-talaria-w7W-lead-handoff.md`, uses nine numbered sections: (1) Current Objective and
Version, (2) What Shipped, (3) What Is in Flight, (4) What Is Next and Why, (5) Blockers and Decisions
Pending, (6) Team Roster (a table of Herdr name, pane, tab, agent/model, role, last assignment), (7)
Board Cards and Statuses, (8) Repo, Worktree, and Branch State, (9) Operator Instructions That Must
Survive Takeover. The incoming Lead then appends its own timestamped "Incoming-lead verification"
section, re-checking the outgoing Lead's claims against live sources rather than editing the original
text, and naming which earlier section is now superseded ("Do not treat section 8B as current"). A
different example, `2026-09-13-l7-web-app-recovery-handoff.md`, uses a looser prose-plus-table shape —
the nine-section form is a strong convention, not an enforced schema.

The second kind is a **console handoff** between successive Codex voice-console sessions, really a
specially named daily record — for example `daily/2026-09-03-early-handoff.md`, sectioned as Scope and
Observation Boundary, In Flight, Settled Since the Previous Closeout (a table), Held and Retained Work,
Publication and Custody, and Next Action and Authority.

The outgoing Lead, in whatever product it runs (the Talaria example was written by an Antigravity
session and read by a Cursor session running Grok), writes the handoff as a checked-in Markdown file.
The incoming session, possibly a different product entirely, reads it at startup, treats every section
as a starting hypothesis rather than fact, and appends its own verification under a new heading rather
than rewriting the original.

`scripts/check_docs.py` is the one automated reader, and it enforces exactly three narrow things:
that a fixed list of 22 required files exists (no Lead-handoff or daily-handoff file is on that list);
that three specific, named transitional documents about a since-superseded planning pause still
contain a required phrase and omit a forbidden one, scoped only to those three files; and that every
relative Markdown link in every `.md` file (excluding the immutable evidence inside a retrospective's
`extracts/` folders) resolves to a real file. It checks no section names, table columns, or field
presence in any handoff document.

Because that enforcement is so narrow, a "judgment source" note (for example, "bucket chosen by Jev,
confidence 0.91") can be added safely two ways: as a short parenthetical next to the line it explains
(inside section 5, "Blockers and Decisions Pending," for instance), or, following the pattern the
repository already uses for incoming-Lead verification, as a new trailing section such as "Judgment
Provenance," appended rather than edited in. Either avoids the required-file list, the three
phrase-guarded files, and every relative link. Best avoided: adding a new column to an existing table
such as the Team Roster — nothing parses these tables by position today, but a bare new column is more
likely to be misread by a future session skimming it than a clearly labeled trailing note would be.

## E. Model and harness reference notes

`docs/reference/models/` is four Markdown files plus one JSON file, and states its own authority
boundary up front: "reference material, not operating policy" — live availability belongs to the
installed `agents` launcher and each vendor's catalog, and benchmark scores explicitly "do not decide
staffing." Every figure carries one of three evidence labels: vendor-documented, third-party-measured,
or locally-observed; a figure without a source must say so.

`README.md` (69 lines) is the index and the closest thing to an explicit, reusable selection rule: for
any proposed roster row it names a three-part check — Launchable (the identifier exists in the current
launch surface, effort mechanism known), Capable (external data places it in the right capability and
cost class for the role), Behaves (the observation log shows no unresolved failure mode for that
pairing in that role). That check is short enough to hand to Jev as policy text almost verbatim.

`launch-surface-2026-09-12.md` (71 lines) is a dated, read-only survey of what one machine could
actually launch that day: nine harnesses in one table — Codex CLI, Claude Code, Antigravity (which
runs Google's Gemini models here), Grok (xAI's client), Cursor Agent, native Muse Code, OpenCode, Qwen
Code, and Hermes — each row giving version, catalog-discovery method, model-selection flag, how it
exposes reasoning effort (a config key for Codex, a CLI flag for most others, a token embedded in the
model identifier for Cursor), and its autonomy/permission flag. It does not rank harnesses; it records
what each currently accepts.

`external-benchmarks-2026-09-12.md` (379 lines) holds fetched third-party facts, organized first by
vendor (OpenAI, Google, xAI, Anthropic, Meta for Muse, Cursor, DeepSeek, Zhipu AI, and Alibaba, which
covers Qwen) and then by benchmark family (Artificial Analysis and LMArena leaderboard positions, then
Terminal-Bench 4.0, SWE-bench Verified, the tau-bench family, OSWorld-Verified, and AppWorld). Hermes
has no vendor-documented section, consistent with it being an open-weight model without a vendor
product page rather than an oversight.

`operational-observations.md` (55 lines) is the living record of what this operation has actually seen,
split into Controllers and monitors, Workers and reviewers, Compaction and context handling, and
Concurrency and rate limits. It records both the Gemini 3.8 Flash controller-stall failure and the
concurrency caps already in force (three simultaneous Claude subagents above Haiku tier, six when every
one is Haiku).

Beyond the README's three-part check, the sharpest explicit selection rule anywhere in the reference
set is a negative one, repeated in `controller-model-selection-and-loop-discipline.md`'s own header: a
benchmark comparison table "has no reproducible evaluation record and must not determine staffing
defaults." Any Jev-based selection help here should obey that same rule, not work around it.

## F. Observations, ranked by leverage

1. **Highest leverage: the four-way queue bucket** (Needs Operator/In Progress/Waiting/Parked). The
   single most repeated judgment in the loop — every workstream, every closeout, every voice-console
   start — already written as clean prose rules in three files. A choice call replaces re-reading a
   paragraph with an instant label, repeatedly, every day.
2. **The requirement/suspected-gap/verified-defect triage** is the highest error-cost judgment made
   casually today, by hand, under delivery pressure. A typed second opinion, kept strictly advisory, is
   cheap insurance against exactly the class of mistake the repository's own history shows.
3. **Workspace staleness has no signal at all today** — the recording rules only say to preserve a
   workspace "unless authorized," so it accumulates until a human notices. Precomputing elapsed time in
   ordinary code, then handing Jev the resulting number plus the last stated reason for keeping the
   workspace open, fills a real, currently empty gap.
4. **The roster Launchable/Capable/Behaves check** is already three yes/no questions over three short
   rows of text that already exist. A natural, low-risk noul batch that saves reading three reference
   files by hand for every proposed roster row.
5. **End-of-day journal routing** is a clean, moderate-leverage target: easy classification, one
   predictable point per day rather than continuous, cheap to correct later if it lands slightly wrong.
6. **The Lead-handoff roster-match check** is worth adding because it already failed once in
   production — a Lead's own generated plan used loose "expert reviews" language implying an extra,
   unapproved reviewer, caught only because a human happened to compare the wording by hand.
7. **Poor fit: date or elapsed-time arithmetic.** Workspace staleness, timeout comparisons, and
   cross-vendor effort-level equivalence all depend on arithmetic this model does badly. Compute it in
   ordinary code first; only the resulting number or category should reach Jev.
8. **Poor fit: ranking controller models by benchmark table.** The repository's own research note
   explicitly disclaims its model-comparison table as unproven and says it "must not determine staffing
   defaults." Asking Jev to rank models from that table would launder an already-rejected use of the
   same data through a new interface.
9. **Poor fit: anything gated on live external state this repository does not hold** — whether a pull
   request merged, whether continuous integration is green at the exact final commit, whether a
   deployment succeeded. These need a real tool call, not a text judgment; a *reported* outcome is
   explicitly not a *verified* one here, and feeding Jev a claim instead of live evidence only produces
   a fast, confidently wrong answer.
10. **Poor fit: the pre-commit privacy sweep** (scanning a diff for credentials, tokens, or raw
    transcripts). This is adversarial-content-shaped and expensive to get wrong, exactly the profile
    the background material warns this model handles poorly. A deterministic secret scanner is cheaper
    and more trustworthy here than a probabilistic judgment call.
