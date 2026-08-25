---
title: improve-claude-plugins unattended run — implementation plan (issue #814, 11 leaves)
type: feat
status: active
date: 2026-08-25
origin: infiquetra/infiquetra-claude-plugins#814
backend: inline
---

# improve-claude-plugins unattended run — implementation plan (issue #814, 11 leaves)

## Summary

One run-wide implementation plan for the eleven sub-issues of the improve-claude-plugins
orchestration contract (issue #814): three repo-root quality fixes (lane W), three orchestrate-plugin
changes (lane O), three saga ownership-seam changes (lane S), and a two-step workflow-backend
decision chain (lane D). Every unit records its smallest viable fix, the repository mechanism it
reuses, any new moving part with the current in-scope failure that requires it, and the larger
alternative deliberately rejected. Two units (U1 #792, U4 #725) were found already resolved on
`origin/main` during planning and become verify-and-close units. Execution backend: **inline**
(recorded from the launch prompt and the Orchestrate driver default — not a ninth
decision-table row — and consistent with the G1 NARROW ruling).

**S3 repairs (2026-08-25):** all 13 findings of the single broad doc review
(`docs/reviews/2026-08-25-improve-claude-plugins-run-plan-doc-review.md`, reviewed revision
`cb09febe`) were validated genuine against the live tree and repaired in this revision: the
2026-08-25 G1/G3 NARROW rulings are inherited (U10/U11 rewritten — no HALT for a made
decision, no chaperone dispatch), U7 is Status-only against the live board schema (no Stage
field exists), each unit brief now carries its leaf's acceptance criteria, verification, and
stop conditions pasted with any command substitutions disclosed, the mermaid-cli fallback is
withdrawn, and the lens roster carries the review-validated conditionals. Disposition ledger:
the S3 comment on issue #814.

## Problem Frame

The Operations-board Objective `improve-claude-plugins` holds exactly eleven open cards
(audited 2026-08-24 against `origin/main` at `d8289513`). Issue #814 is the orchestration
contract that drives all eleven to merged-and-closed in one unattended Orchestrate run. This
plan is the run's S1 Saga Plan: it refines each leaf into a unit brief and predeclares the
Saga Code Review lenses, and it may not contradict the contract's lane ownership, dependency
edges, collision surfaces, gates, or operator-decision table.

## Operating context and proportionality (constraints carried forward)

This repository is a private, single-user developer-tool plugin suite operated by Jeff. Units
must choose the smallest change that fixes the verified defect and satisfies the leaf's
acceptance criteria, reusing existing repository mechanisms. A new abstraction, dependency,
background process, persistent state, framework, or extra operator workflow is permitted only
when the unit names the current in-scope failure it prevents and why a smaller change cannot
work. No multi-tenancy, internet-scale, high-availability, or hostile-co-tenant design.
Security and reliability findings must name an actual trust boundary or failure mode with a
concrete consequence. Justified safeguards around credentials, shell/process execution,
filesystem or Git mutation, external input, privacy, and destructive operations are preserved.
The Saga Doc Review validates this plan against exactly this policy.

## Repository freshness and baseline

Planning base: `origin/main` fetched 2026-08-25 in worktree branch
`orch/orch-2026-08-25-814-saga-plan` (clean at `ebe476d4`, equal to `origin/main` at planning
time; `git diff HEAD origin/main --stat` empty). The run's S0 preflight re-records the launch
pin; every unit's first action is `git fetch origin && git merge origin/main` and re-anchoring
of the file/line references in its brief. Two planning-time discoveries below (U1, U4) were
verified against `origin/main`, not against a stale working tree.

## Requirements

- **R1.** Every unit implements to its own leaf's acceptance criteria verbatim; the eleven
  child issue bodies are the authoritative per-unit contracts. This plan copies each leaf's
  dispositions, owned files, tests, and stop conditions into its unit brief and adds nothing
  the leaf or the parent contract does not authorize.
- **R2.** Lane ownership and the `after`/`serialize` edges are honored exactly as the #814
  inventory table states them: W1→W2→W3 (serialize), O1→O2→O3 (serialize), S1→S2→S3
  (serialize, with S2 `after: O3`), D1→D2 (`after: D1 ruling`), D1 implementation
  `serialize: S2`. No invented cross-lane edges.
- **R3.** Collision surfaces per the contract: `.claude-plugin/marketplace.json` resolved only
  by global merge serialization plus version re-resolution at merge time (sibling same-version
  bumps auto-merge silently — re-bump at merge); `plugins/orchestrate/**` writers strictly
  #725→#813→#777→#776; `plugins/saga/**` writers #812→#776→#778→#808-impl→#708;
  `plugins/mission-control/**` #812 sole writer; `plugins/agent-launcher/**` #777 sole writer;
  `CLAUDE.md` no writer.
- **R4.** Merges serialized globally, one PR at a time; each merge requires the typed review
  outcome per decision row 7, `mergeStateStatus` CLEAN, and green CI on the PR head; after
  every merge, every surviving branch reintegrates `origin/main` and re-resolves
  release-surface versions. CI on main at the final merged commit is verified, not only the
  last PR.
- **R5.** Gates — G1 and G3 were operator-resolved on 2026-08-25 and are inherited here
  (F2/F1 repairs). **G1 = NARROW** (#808, issuecomment-5405414716): Claude Code Workflows
  remain only explicitly invoked task-local mechanisms inside Herdr-managed sessions — not
  Saga's default or automatic backend and not a generic interchangeable execution backend;
  U10 still gathers the required evidence, then validates and implements this ruling instead
  of re-presenting the four-way choice, and HALTs only if evidence proves the narrowed shape
  internally contradictory or impossible. **G3 = NARROW** (#708, issuecomment-5405419292):
  fail-loud emit-time rejection only — no chaperone-wrapper dispatch, model/effort bridging,
  alias translation, or engine lifecycle management in the emitter; Herdr and Orchestrate own
  cross-vendor sessions. G2 — resolved 2026-08-24 (single-repository split; the Agent Plugins
  port is infiquetra-agent-plugins#22, outside this run).
- **R6.** Review contract (decision row 7): the lenses predeclared in this plan are the
  applicable lens set per unit; no lens is added later without returning to the operator. Per
  applicable lens: overall ≥ 9.0, no applicable dimension below 7.0, never averaged across
  lenses; findings validated before repair; every genuine finding repaired; at most 3
  repair-and-review cycles; after cycle 3, `cycle_cap_best_available` with full disclosure.
- **R7.** Board writes happen only through mission-control `flow set-field` executed by the
  orchestrating session (the designated single writer); worker and reviewer sessions never
  write the board. In-run ladder: parent Active at run start; each child Active at launch,
  Verify when frozen under review, Done only after merged-and-closed.
- **R8.** Source pinning per unit: record base SHA, frozen reviewed SHA(s), merged SHA; a
  stale or dirty revision is never reviewed or merged.
- **R9.** Journal obligations ship in the same commit where a leaf's mechanism warrants an
  entry, newest-first placement; `docs/engineering-journal/` writers in this run are #808's
  decision entry plus per-leaf obligations (see KTD8 for why this plan itself adds none).
- **R10.** Verify-and-close units (U1, U4) close only on a fresh evidence rerun at the launch
  pin; if the rerun shows a residual defect, the unit implements per its leaf instead.

## Key Technical Decisions

The KTDs below are plan-scoped run decisions. Leaf-level mechanism decisions that warrant a
journal entry ship with their leaf's commit (R9).

- **KTD1 — Already-resolved leaves close on evidence, not on ceremony.** Planning verified two
  leaves are already fixed on `origin/main`: #792's width-brittle assert was hardened by
  PR #790 (commit `6396455a` — `tests/test_orchestrate_hygiene.py:197-202` collapses
  whitespace before asserting), and #725's defective mirror was deleted wholesale by commit
  `84e53a72` (1,881 lines of `mirror.py` removed; the `plugins/orchestrate/references/`
  claim pages are gone too). Rationale: re-implementing a landed fix or fixing deleted code
  churns sole-writer surfaces for nothing; the truthful terminal state is
  close-with-evidence after a fresh rerun at the launch pin. Rejected alternative: minting
  no-op PRs to satisfy the merged-PR closure shape — ceremony with real collision cost.
- **KTD2 — Mermaid validation uses mermaid's own parser via a pinned Node dev dependency.**
  #405 needs a real parse of every tracked fence; no Python Mermaid parser exists, and a
  heuristic regex lint would have passed broken diagrams (false green — worse than no check).
  Chosen: a Python entrypoint `scripts/check_mermaid.py` (enumeration via `git grep`,
  file:line reporting, fixture-testable) shelling to a small Node helper that calls
  `mermaid.parse()` headless with a DOM shim, with the mermaid version pinned. Node absent
  locally → gate exit 3 (the existing missing-dev-dependency precondition). Rejected:
  `@mermaid-js/mermaid-cli` (puppeteer/chromium render — hundreds of MB, slow, flaky in CI;
  rendering is not needed to parse) and any validator framework (removed from scope by the
  operator's Phase 2 ruling). **No fallback to mermaid-cli is authorized** (F6 repair — it is
  the rejected heavy path): if headless `mermaid.parse()` proves infeasible at the pinned
  version, the unit HALTs and returns that evidence for an operator decision rather than
  silently swapping in a browser renderer. Wiring pinned (F7 repair): `actions/setup-node` in
  the existing Lint job; `scripts/mermaid/package.json` pinning the exact mermaid version with
  `jsdom` as the DOM shim; the `gate.sh` step text matches the `ci.yml` step name so coverage
  cannot be satisfied by renaming; Node absent locally → gate exit 3 (existing
  missing-dev-dependency semantics).
- **KTD3 — #812 is guard-and-tighten, not a migration.** Planning found zero direct GraphQL
  Stage/Status writes in saga: every Status write already funnels through
  `board_progression.default_board_writer` → mission-control `sdlc_manager.py flow set-field`
  (`plugins/saga/scripts/board_progression.py:369-491` →
  `plugins/mission-control/scripts/sdlc_manager.py:2416`), and no saga code path writes a
  Stage field at all. The unit therefore: confirms this inventory at the launch pin, scopes
  the saga submission seam to Stage/Status by name (rejecting other fields), adds the
  field-named op-kind for Stage beside the existing `set-field-status`, and lands the static
  single-writer guard test. Rejected: the #593-style deepening of a saga-owned board writer
  (closed by operator ruling) and any generic correction intake.
- **KTD4 — #776 retires the transport, keeps the registry as non-transport metadata.** The
  transport trio (`engine_offer.py` 581 lines, `engine_session_runner.py` 749,
  `external_only.py` 112) and the `.saga/engine-prefs.json` seam are removed; the
  `engine-registry.yaml` capability/calibration data (17 registry-side consumer scripts,
  none of them transport) is retained and explicitly marked non-transport, unable to
  override the live Orchestrate/Herdr roster — exactly the carve-out the leaf's contract
  allows. Rejected: deleting the registry subsystem too (17 consumers, calibration history,
  and #808's evidence base depend on it; that is a separate decision no leaf authorizes).
- **KTD5 — #708's live seam is `execution_spec.py`, not `workflow_emitter.py`.** On the
  current tree the inert emission is `_agent_opts` at
  `plugins/saga/scripts/execution_spec.py:2682-2694`: an engine-routed unit emits
  `dispatch: "external-engine"` / `engine:` / `verifiability:` opts keys the cc-workflows
  runtime ignores, and — the `else` branch — no `model`/`effort`.
  `plugins/saga/scripts/workflow_emitter.py` (214 lines) is today a workflow-lease contract
  module with zero dispatch code; the leaf's file list is stale on this point and the unit
  brief carries the correction.
- **KTD6 — #777 extracts the seam as-is into `plugins/agent-launcher/`, absorbing the
  machine-local skill contract.** The launcher seam is fully inline in
  `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py` (argv assembly
  `agent_argv` :1380-1418; launch orchestration `launch` :1942-1983; receipt verification
  `verify_unit_preflight` :1843-1939; readiness :1461-1497; delivery :2002-2056; cleanup
  :1650-1653, :4010-4145). A machine-local `agent-launcher` skill already exists at
  `~/.agents/skills/agent-launcher/SKILL.md` (symlinked into `~/.claude/skills/`) — the
  plugin absorbs that creation-only contract and declares an explicit dependency on the
  canonical `herdr` skill rather than duplicating it. Layout follows the in-repo
  `skills/<name>/scripts/` convention (as orchestrate does), not `tools/create-plugin.sh`'s
  literal `src/` default. Behavior moves; it is not redesigned. Rejected: leaving a
  duplicated launch path in orchestrate (the drift failure mode the leaf names) and any new
  vendor/model registry (prohibited by the leaf).
- **KTD7 — Lens predeclaration is locked in this plan.** The per-unit lens sets in the
  Implementation Units below are the complete applicable sets (operator ruling, decision
  row 7). The four always-on lenses (`architecture-maintainability`, `correctness`,
  `security`, `testing` — `plugins/saga/references/lens-roster.json`) run for every review;
  conditionals are listed per unit with a one-line reason. Adding any lens later requires
  returning to the operator. A unit that ships no diff produces no frozen revision and gets
  no code review.
- **KTD8 — This plan writes no engineering-journal entry.** The contract enumerates
  `docs/engineering-journal/` writers for this run (#808's decision entry plus per-leaf
  obligations) and lists the journal as an append-only collision surface. The plan session is
  not an enumerated writer, so the KTDs live in this committed document and in the saga tick;
  leaf-level decisions journal with their leaves. This deliberately overrides the saga plan
  skill's default journal mirror for this run only.
- **KTD9 — Backend inline (recorded, not decided).** All eleven units execute inline on
  worker sessions; no cc-workflows backend, no team-execution. Recorded from the launch
  prompt and the Orchestrate driver default — not a ninth decision-table row (F12
  correction) — and consistent with G1 NARROW (`/work` honours the `backend:` frontmatter
  and does not re-ask).

## Lanes, dependency edges, and collision surfaces

The authoritative inventory, dependency graph, decision table, gates, merge-serialization
rules, settlement rules, and stop conditions live in the #814 issue body and its 2026-08-24
operator-ruling comment; this plan restates only what unit briefs need and contradicts none of
it.

| Lane | Order | Unit | Issue | Depends on | Gate |
| --- | --- | --- | --- | --- | --- |
| W | W1 | U1 | #792 | — | — |
| W | W2 | U2 | #405 | serialize: W1 | — |
| W | W3 | U3 | #407 | serialize: W2 | — |
| O | O1 | U4 | #725 | — | — |
| O | O2 | U5 | #813 | serialize: O1 | — |
| O | O3 | U6 | #777 | serialize: O2 | G2 resolved |
| S | S1 | U7 | #812 | — | — |
| S | S2 | U8 | #776 | after: O3; serialize: S1 | — |
| S | S3 | U9 | #778 | serialize: S2 | — |
| D | D1 | U10 | #808 | evidence read-only from start; impl serialize: S2 | G1 resolved: NARROW |
| D | D2 | U11 | #708 | after: D1 | G3 resolved: NARROW |

Lanes W, O, S-head (U7), and D-head evidence (U10 phase A) start concurrently at run start.
With U1 and U4 expected to settle as verify-and-close (KTD1), lanes W and O reach their second
units almost immediately; the serialize edges still gate ordering and cost nothing.

Same-file overlaps the serialize edges exist for: `plugins/orchestrate/skills/orchestrate/SKILL.md`
(four-way: #725→#813→#777→#776), the code-review skill (#776, #778), plan/work skill text
(#776, #808), `execution_spec.py` (#808, #708), and `.claude-plugin/marketplace.json` (every
plugin PR, merge-serialized with re-bump at merge).

## Tier table (per the #814 operator-decision table — every assignment is a 2026-08-24 ruling)

| Role | Assignment | Cap |
| --- | --- | --- |
| Saga Plan (this document) | Claude Fable 5 (`claude-fable-5`) · effort xhigh · company account | 1 |
| Saga Doc Review | Grok (`grok-4.6`) · xhigh reasoning · standard Grok account · exactly one broad review | 1 |
| Work pool P1 (primary) | Grok (`grok-4.6`) · high reasoning · standard Grok account | 10 simultaneous |
| Work pool P2 (overflow) | Antigravity (`agy`) · `gemini-3.7-flash-high` (effort in the id) | 4 simultaneous |
| Saga Code Review | Claude Opus 5 (`claude-opus-5`) · effort xhigh · company account · one direct session per frozen revision | 4 simultaneous |

Every ready unit dispatches to P1 while it has free capacity; P2 engages only when genuine
readiness exceeds P1's free capacity (with four lanes, steady-state readiness ≤ 4, so P2 is
expected unexercised — closeout states which pools went unexercised). No unit carries a
per-unit model override; the decision table governs every assignment.

## Implementation Units

Every unit: first action `git fetch origin && git merge origin/main`, re-anchor references;
implement to the leaf's acceptance criteria; run the leaf's Verification block; run the repo
gate backgrounded (`GATE_LOG_DIR=... bash scripts/gate.sh`, read `result.txt`); exactly one
Saga Code Review process per frozen revision (when a diff ships); merge under the global
serialization rules; close the leaf with its evidence; journal in the same commit where the
mechanism warrants. Each unit inherits its leaf's stop conditions verbatim plus the run-level
stop conditions in #814.

### U1. #792 — width-stable help-text assert (lane W, W1)

**Goal:** the pre-push gate no longer false-positives on argparse help wrapping in narrow
terminals.

**Planning evidence (verified 2026-08-25):** the fix already landed on `origin/main` — PR #790,
commit `6396455a`, added the whitespace-collapse normalization with an explanatory comment at
`tests/test_orchestrate_hygiene.py:197-202`. Both leaf acceptance commands pass on the current
tree: `COLUMNS=40` and `COLUMNS=200` runs of `uv run pytest tests/test_orchestrate_hygiene.py -q`
each report 13 passed. The file's only terminal-width-sensitive assert is that one (line 194 is
the file's sole `--help` invocation; the line-184 sibling reads `SKILL.md` text, which is
width-independent).

**Smallest viable fix:** none — verify-and-close (KTD1, R10). Rerun both acceptance commands at
the launch pin, then close #792 with an evidence comment naming PR #790 / `6396455a` and the
rerun receipts. No PR, no code review (no frozen revision).

**Mechanism reused:** the leaf's own acceptance commands as the verification oracle.

**New moving part:** none.

**Rejected alternative:** re-implementing a `COLUMNS` monkeypatch pin on top of the landed
normalization — a redundant diff on a sole-writer file that W2/W3 would then serialize behind.

**Contingency:** if the launch-pin rerun fails, implement per the leaf (normalize the captured
help text or pin `COLUMNS` via monkeypatch; harden any sibling assert), test-only diff to
`tests/test_orchestrate_hygiene.py`, then the always-on lens set applies.

**Run note:** #814's "environmental hazard until W1 merges" is already discharged — the hazard's
fix merged with PR #790, so the disclosed out-of-band push path should not be needed.

**Test scenarios:** the two `COLUMNS` acceptance runs (`tests/test_orchestrate_hygiene.py`).

**Predeclared lenses:** none — no diff expected. Contingency diff: always-on four only
(test-assert hardening touches no conditional domain).

**Leaf contract (#792, pasted — F5 repair):** Acceptance criteria: (1) `COLUMNS=40 uv run
pytest tests/test_orchestrate_hygiene.py -q` — all tests pass at 40 columns; (2)
`COLUMNS=200 uv run pytest tests/test_orchestrate_hygiene.py -q` — all tests pass at 200
columns; (3) the fix touches only `tests/test_orchestrate_hygiene.py` *(satisfied vacuously:
verify-and-close ships no diff)*. Verification: the two COLUMNS commands. Stop conditions:
none in the leaf. Closure shape (F8 disposition): evidence comment naming PR #790 / commit
`6396455a` plus launch-pin rerun receipts; the #814 closing comment discloses the parent-AC
substitution (the closing PR reference is historical, not a run PR).

### U2. #405 — always-on Mermaid syntax check (lane W, W2)

**Goal:** CI parses every Mermaid fence in tracked Markdown and fails on syntax errors, naming
file and line; the gate covers the step.

**Smallest viable fix:** one new check script plus one CI step. `scripts/check_mermaid.py`
enumerates ```` ```mermaid ```` fences in tracked `*.md` (population today: 20 fences across 16
files, via `git grep`), extracts each fence with its line offset, and validates it through a
small pinned Node helper calling `mermaid.parse()` headless (KTD2); failures name file and
line. New step in the existing **Lint** job of `.github/workflows/ci.yml` (beside the other
content lints, e.g. the journal ordering lint at `.github/workflows/ci.yml:215`); no new
workflow.

**Mechanism reused:** `scripts/gate.sh`'s coverage self-check — the gate compares its own step
list against `ci.yml` and fails `GATE INCOMPLETE` until the new CI step is covered
(`scripts/gate.sh:14-15`), so gate parity is forced by the existing mechanism, not by hand
bookkeeping. Enumeration reuses `git grep` (tracked-files-only semantics for free).

**New moving part:** a pinned Node dev dependency for mermaid's own parser — named in-scope
failure: 13 broken diagrams shipped undetected
(`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:148-149` — F11 correction), and no
Python Mermaid parser exists; a regex heuristic yields false green. Wiring per KTD2's F7 pin:
`actions/setup-node` in the Lint job, `scripts/mermaid/package.json` (exact mermaid version +
`jsdom`), gate step text matching the `ci.yml` step name. Node missing locally → gate exit 3
precondition (existing semantics). No mermaid-cli fallback (F6): infeasibility HALTs with
evidence.

**Rejected alternative:** `@mermaid-js/mermaid-cli` (full browser render to validate a parse —
disproportionate), the generic checkable-surface census / registry / drift framework (removed
by the operator's Phase 2 ruling).

**Test scenarios:** `tests/test_check_mermaid.py` — one valid fence passes; one broken fence
fails naming file and line; the current tree run exits 0 (repairing any broken tracked fence in
the same change if found).

**Predeclared lenses:** always-on four + `deployment-infrastructure` — the unit edits
`.github/workflows/ci.yml` and `scripts/gate.sh`, which is CI/infrastructure configuration
surface. (S2 note: inside that lens, do not demand high availability or multi-tenant rollout;
the change is a CI step and a gate coverage line.)

**Leaf contract (#405, pasted — F5 repair):** Acceptance criteria: (1) `uv run pytest tests/
-k mermaid -q` — fixture tests pass, including one broken fence failing with its file and
line named and one valid fence passing; (2) the new check run against the current tree exits
0 — every tracked Mermaid fence parses, or is repaired in the same change (`git grep -l
'\`\`\`mermaid' -- '*.md'` enumerates the population); (3) `GATE_LOG_DIR=/tmp/gate-run bash
scripts/gate.sh` — no `GATE INCOMPLETE`; the coverage self-check counts the new CI step.
Verification: `uv run pytest tests/ -k mermaid -q`; backgrounded gate run; read
`/tmp/gate-run/result.txt`. Stop conditions: none in the leaf (KTD2's HALT-on-infeasible-parse
applies).

### U3. #407 — journal lint: duplicate and dangling anchors (lane W, W3)

**Goal:** `scripts/lint_journal_order.py` also fails on duplicate `{#slug}` definitions (both
sites named) and on references to anchors with no definition (referencing line named).

**Smallest viable fix:** extend the existing 188-line lint in place. It already enumerates the
covered files (`scripts/lint_journal_order.py:36-37`) and already parses heading anchors (the
`key()` helper at `:108-113`). Add: a definition pass (heading-attached `{#slug}` across the
covered file set, jointly — cross-file duplicates count), and a reference pass (`](#slug)`
link targets and non-heading `{#slug}` mentions) checked against the joint definition set.

**Mechanism reused:** the lint's own file roster, anchor parsing, and its two existing CI
homes — the script already runs in the Lint job (`ci.yml:215`) and the Release Surface Parity
job (`ci.yml:159`), so the new checks run everywhere the lint runs today with zero wiring.

**New moving part:** none.

**Rejected alternative:** prose-field enforcement (`Revisit when`, commit hashes) and general
journal schema validation — removed by the operator's Phase 2 ruling.

**Test scenarios:** `tests/test_lint_journal_order.py` (exists, extended) — fixture with a
duplicate anchor fails naming both definition sites; fixture with a dangling reference fails
naming the referencing line; the current journal passes (violations found are repaired in the
same change).

**Predeclared lenses:** always-on four only — a self-contained lint script and its fixtures
touch no conditional domain.

**Leaf contract (#407, pasted — F5 repair):** Acceptance criteria: (1) `uv run pytest tests/
-k journal -q` — fixtures pass; a duplicate anchor fails naming both definition sites; a
dangling reference fails naming the referencing line; (2) `python3
scripts/lint_journal_order.py` — exit 0 on the current journal, or violations found are
repaired in the same change; (3) the checks run wherever the lint runs today (CI and the
gate), no new workflow — gate reports no `GATE INCOMPLETE`. Verification: the two commands
above. Stop conditions: none in the leaf. (F13 correction: `ci.yml:159` is the PR-scoped
"Journal newest-first guard (new entries)" step, not a job named Release Surface Parity;
`ci.yml:215` is the Lint-job home.)

### U4. #725 — mirror embedded-region bound (lane O, O1)

**Goal:** the mirror accepts ordinary in-budget source files, or the published bounds claim
stops being made.

**Planning evidence (verified 2026-08-25):** the defect surface no longer exists. Commit
`84e53a72` (the orchestrate worktree-per-unit rebuild) deleted
`plugins/orchestrate/skills/orchestrate/scripts/mirror.py` in full (1,881 lines);
`_MAX_EMBEDDED_REGIONS` and `PredicateInMirrorError` appear nowhere in the tree;
`plugins/orchestrate/references/` (home of the `operator-channel.md` claim page) is gone; and
`rg "ordinary reading" plugins/orchestrate/` returns nothing — the leaf's third acceptance
criterion ("the claim is corrected/removed") is satisfied by removal.

**Smallest viable fix:** none — verify-and-close (KTD1, R10). At the launch pin, rerun the
sweeps (`rg -n "_MAX_EMBEDDED_REGIONS|PredicateInMirrorError|ordinary reading"` over the tree),
then close #725 with an evidence comment citing `84e53a72` and the sweep receipts. No PR, no
code review.

**Mechanism reused:** the leaf's own verification greps.

**New moving part:** none.

**Rejected alternative:** writing a regression fixture for a module that no longer exists —
untestable ceremony.

**Contingency:** none realistic at a frozen pin; if a successor mirror surface exists that
re-asserts the bounds claim, the unit implements the leaf's smallest-change branch against it
and the lens set below applies.

**Test scenarios:** none (no diff). Contingency diff: always-on four + `documentation-clarity`
if the change is a published-claim correction.

**Predeclared lenses:** none — no diff expected. Contingency: always-on four
(+ `documentation-clarity` for a claim-correction diff — the deliverable would be published
prose).

**Leaf contract (#725, pasted with substitutions — F5 repair):** Acceptance criteria: (1)
`uv run pytest tests/ -k mirror -q` *(substitution: no mirror module or mirror tests exist
after `84e53a72` — vacuously satisfied, disclosed)*; (2) the issue's reproduction is accepted
by the fixed mirror *(substitution: the module is deleted; nothing refuses the file)*; (3)
`rg -n "ordinary reading" plugins/orchestrate/` — the published bounds claim is corrected or
removed — satisfied by removal, 0 hits. Verification: launch-pin sweeps
`rg -n "_MAX_EMBEDDED_REGIONS|PredicateInMirrorError|ordinary reading"` over the tree.
Stop conditions: none in the leaf. Closure shape (F8 disposition): evidence comment citing
`84e53a72` and the sweep receipts; parent-AC substitution disclosed in the #814 closing
comment.

### U5. #813 — per-run pool declarations and reintegration docs (lane O, O2)

**Goal:** `plugins/orchestrate/skills/orchestrate/SKILL.md` documents the per-run worker-pool
declaration table and the reintegrate-after-every-serialized-landing practice, both proven in
run orch-2026-08-24-787.

**Smallest viable fix:** docs-only. Two additions to the orchestrate SKILL.md: (1) a per-run
worker-pool declaration shape — priority order, per-pool cap, launch template,
exercised-or-not at closeout — with vendors/models/efforts/caps stated as per-run operator
inputs, never hard-coded; (2) the merge-queue practice against the run's explicitly declared
authoritative integration branch (declared up front; `origin/main` as an example declaration,
not policy), with every surviving branch reintegrating the declared target after each
serialized landing and re-resolving release-surface versions before continuing. Wording must
literally satisfy the leaf's three acceptance greps ("worker-pool", "authoritative
integration branch", "per-run operator inputs").

**Mechanism reused:** the retro's approved text as source
(`docs/retros/issue-787-2026-08-24.md` section 6, items 6-7); the existing release-surface
bump flow (orchestrate `plugin.json` + `CHANGELOG.md` + `.claude-plugin/marketplace.json` in
the same PR, guarded by the existing parity checks).

**New moving part:** none — guidance only, no automation, no scheduler/driver change.

**Rejected alternative:** building pool/reintegration machinery into the driver — the leaf
explicitly scopes this to guidance, and the retro classifies the practices as proven guidance,
not mechanism.

**Test scenarios:** none — docs-only (`Test expectation: none — docs-only change; the existing
release-surface parity checks and CI docs steps cover it`, per the leaf).

**Predeclared lenses:** always-on four + `documentation-clarity` (the deliverable is guidance
prose) + `agent-usability` (SKILL.md is instruction text consumed by orchestrator agents).

**Leaf contract (#813, pasted — F5 repair):** Acceptance criteria: (1) `grep -n "worker-pool"
plugins/orchestrate/skills/orchestrate/SKILL.md` returns the per-run pool declaration section
(priority order, per-pool cap, launch template, exercised-or-not at closeout); (2)
`grep -in "authoritative integration branch" plugins/orchestrate/skills/orchestrate/SKILL.md`
returns the reintegration practice (target declared per run; every surviving branch
reintegrates it after each serialized landing; release-surface versions re-resolved before
continuing); (3) `grep -in "per-run operator inputs" plugins/orchestrate/skills/orchestrate/SKILL.md`
returns the statement that vendors, models, efforts, caps, and the integration target are
per-run operator inputs, never hard-coded. Verification: the three greps; release surfaces
bumped in the shipping PR (`plugins/orchestrate/.claude-plugin/plugin.json`, `CHANGELOG.md`,
`.claude-plugin/marketplace.json`). Stop conditions: none in the leaf.

### U6. #777 — portable agent-launcher plugin + orchestrate refactor (lane O, O3)

**Goal:** a standalone `plugins/agent-launcher/` plugin owns the single-session launch
contract (create via the installed `agents` wrapper, verify and interact via Herdr); an
ordinary session can launch one verified agent without an Orchestrate run; Orchestrate
consumes the shared surface and drops its private copy. G2 is resolved: the Agent Plugins
port is infiquetra-agent-plugins#22 and does not gate this unit.

**Smallest viable fix:** extract, don't redesign (KTD6). Move the launcher seam out of
`orchestrate.py` — vendor flag tables (`VENDOR_FLAGS` :65, `VENDOR_PERMISSION` :143), argv
assembly (`agent_argv` :1380-1418), wrapper resolution and roster (`launcher`/`launchable`/
`roster` :1245-1302), launch orchestration (`launch` :1942-1983), receipt verification
(`verify_unit_preflight` :1843-1939), readiness (`agent_row`/`await_ready`/`took_the_task`
:1461-1497), delivery (`pane_text`/`say`/`send` :2002-2056), owned cleanup
(`close_run_session` :1650-1653) — into `plugins/agent-launcher/skills/agent-launcher/scripts/`,
with `skills/agent-launcher/SKILL.md` absorbing the machine-local creation-only contract
(`~/.agents/skills/agent-launcher/SKILL.md`) and declaring an explicit dependency on the
canonical `herdr` skill (no duplicated herdr skill). Orchestrate imports the shared module and
deletes the transferred private implementation; run-scheduling, landing, review policy, and
run-ledger behavior stay in orchestrate.

**Mechanism reused:** the installed `agents` wrapper (`~/.local/bin/agents`) as the only
creation path and Herdr as the only interaction path (both already authoritative); the
existing launcher test suites as the behavior oracle for the refactor
(`tests/test_orchestrate_launch_and_land.py` 38 tests, `tests/test_orchestrate_delivery.py` 8,
`tests/test_orchestrate_account.py` ~30, `tests/test_orchestrate_vendor_permissions.py` 8);
the repo's `skills/<name>/scripts/` plugin layout convention.

**New moving part:** the new plugin itself — named in-scope failure (from the leaf): a normal
session cannot discover or apply the verified launch contract without starting a full
Orchestrate run, and Orchestrate's private implementation plus the machine-local skill are
already two drifting copies of the same contract. Why smaller can't work: the reusable
behavior currently lives inside a 4,602-line orchestrate module; no smaller change exposes it
to ordinary sessions without a third copy.

**Rejected alternative:** keeping a second launcher implementation in orchestrate (the drift
failure the leaf pre-mortems); a new vendor/model registry (prohibited — the live wrapper and
Herdr state remain authoritative); headless/hidden subprocess paths (prohibited).

**Test scenarios:** per the leaf, under `plugins/agent-launcher/tests/` and `tests/`: contract
tests for exact wrapper argv ordering (`--no-focus`, `--current`, `--herdr`,
`--herdr-control-only`, task, cwd, permissions, model, effort); real-subprocess tests for exit
status, malformed receipts, startup timeout, prompt-delivery failure; Herdr readback tests
(name, workspace, tab, pane, cwd, kind, model, effort, readiness, unchanged focus);
regression proof a plain session launches one reviewer without Orchestrate; regression proof
Orchestrate calls the shared launcher (no private copy). Migrated orchestrate launcher tests
stay green. Final live smoke: one named, no-focus Codex reviewer at explicit extra-high
reasoning, verified through Herdr, owned cleanup only.

**Owned release surfaces (F10 repair):** in the same PR — `plugins/agent-launcher/.claude-plugin/plugin.json`
(new), `plugins/agent-launcher/CHANGELOG.md` (new), the `.claude-plugin/marketplace.json`
entry, `plugins/agent-launcher/tests/`, orchestrate's own `plugin.json`/`CHANGELOG.md`
(behavior moves), and the existing plugin-validation / release-surface parity checks.

**Predeclared lenses:** always-on four + `api-contract` (the launcher exposes a
launch/readback contract consumed by two callers — ordinary sessions and orchestrate) +
`reliability` (readiness polling, timeouts, partial-launch and duplicate-session failure
modes) + `agent-usability` (a new SKILL.md consumed by ordinary sessions) + `adversarial`
(F9, S2-validated: process-launch, silent substitution, and unowned cleanup are the leaf's
named failure modes).

**Leaf contract (#777, pasted — F5 repair):** Acceptance criteria: (1) a standalone plugin
exposes one clear launch skill and one clear Herdr interaction boundary; (2) an ordinary
session launches one supported agent in the current Herdr workspace without Orchestrate; (3)
every launch is previewed, no-focus, preserves the explicit working directory, and records
the exact wrapper receipt; (4) Herdr verifies live kind, model, effort, permissions, cwd,
workspace, tab, pane, and readiness before work is submitted; (5) all post-creation
interaction uses Herdr prompt/wait/read/input and owned cleanup; (6) no private vendor/model
roster, no silent substitution; (7) Orchestrate consumes the shared surface and removes its
duplicate implementation where ownership transfers; (8) #776 is implemented against this
ownership boundary; (9) the plugin is released in `infiquetra-claude-plugins` before its port
begins; (10) the Agent Plugins port is tracked in infiquetra-agent-plugins#22 (linked
sub-issue) and does not block this issue once Claude-side criteria are met; (11) a live smoke
test launches one independent Codex reviewer at explicit extra-high reasoning without
changing operator focus, verifies through Herdr, and cleans up only that owned session.
Verification: `uv sync --all-extras`; `uv run pytest plugins/agent-launcher/tests
plugins/orchestrate/tests`; `uv run ruff check plugins/agent-launcher plugins/orchestrate`;
`uv run mypy plugins/agent-launcher plugins/orchestrate`; `uv run pytest`; plus the live
named no-focus Herdr smoke session with readback receipts. Stop conditions (leaf, verbatim):
stop before launch if the wrapper dry run does not resolve the requested working directory
and current Herdr workspace; stop before prompting if Herdr cannot verify the requested
agent kind, model, effort, permissions, pane, and readiness; stop rather than silently
substituting an unavailable agent or launch setting; stop cleanup if ownership of the target
session cannot be proven; the port-representability stop transfers to
infiquetra-agent-plugins#22 with the port.

### U7. #812 — Stage/Status corrections through mission-control (lane S, S1)

**Goal:** mission-control is the sole writer of board Stage and Status; saga only submits
corrections through the existing narrow `flow set-field` operation, with the field name in
the operation, its authorization, and its retry identity; a static guard proves no direct
composition remains.

**Smallest viable fix (KTD3, rewritten per F3/F4):** the inventory step records the planning
finding — zero direct GraphQL Stage/Status writes in saga; the *Status set-field* writes
funnel through `default_board_writer` → `sdlc_manager.py flow set-field --field Status`
(`board_progression.py:428-442`), while the writer's other op-kinds (`sub-issue-close`,
`sub-issue-reopen`, `issue-progress-comment`, `issue-label-add`/`-remove`) are unrelated
board writes that the leaf explicitly leaves untouched. **No Stage project field exists on
Operations, Asgard, or CAMPPS** (live `flow field-options` receipt, 2026-08-25 — F3). The
work is therefore: (1) record the inventory, including the live field-list receipt, as the
leaf's step-1 deliverable; (2) constrain only the *set-field* seam by field name — a
set-field submission naming any project field other than Status is rejected (and other than
Stage if a Stage field ever exists), with the field name carried through operation,
authorization, and retry identity; **no `set-field-stage` op-kind and no Stage field are
created** — dead API surface for a nonexistent field (F3), and no clamp on the writer's
non-set-field op-kinds (F4); (3) retire nothing beyond asserting none of the hypothesized
direct composition exists; (4) land the static guard (covering BOTH fields: no direct Status
write and no write to a field named Stage anywhere in saga) and the round-trip tests. The
leaf's Stage-side live-check acceptance is satisfied as a documented substitution: the
static guard proves no Stage write exists, and the field-options receipt proves no Stage
field exists to correct — recorded in the PR body. Mission-control's set-field surface
changes only if the field-named identity needs tightening on its side — no new operation,
no generic intake.

**Mechanism reused:** `board_progression.authorize_and_write` and its certificate gate
(default-GATE allowlist in `plugins/saga/scripts/reversibility_certificate.py:292`), the
existing `flow set-field` CLI (`sdlc_manager.py:6046-6066`, mutation at `:2477-2491`), and
the existing idempotent reconcile-op identity (target-state-keyed).

**New moving part:** one new test file `tests/test_saga_single_writer_guard.py` — named
in-scope failure: the single-writer policy exists by operator ruling but nothing enforces it,
so a future saga script could silently re-introduce direct board composition (the exact class
the ruling against #593 was meant to close). A static guard is the smallest enforcement.

**Rejected alternative:** the #593 deepening of a saga-owned board writer (closed by the same
ruling); a generic correction intake or arbitrary-field writer (explicitly out of scope);
new safety machinery beyond the existing certificate gate.

**Test scenarios:** `tests/test_saga_single_writer_guard.py` — static guard over both fields:
no saga call site composes a direct board Stage or Status write; every surviving reference to
the write utilities is submission-path. `plugins/mission-control/tests/` (`-k "set_field or
correction"`) — an in-scope correction round-trips through `flow set-field` with the field
name present in operation, authorization, and retry identity; a set-field submission naming
any other project field is rejected. `plugins/mission-control/tests/` (`-k certificate`) —
existing certificate gates unchanged and still enforcing. Live verification (F3
substitution): one live **Status** correction on a scratch issue executed by
mission-control's set-field with the certificate gate engaged; the Stage live-check is
substituted by the static no-Stage-write guard plus the field-options receipt, disclosed in
the PR.

**Predeclared lenses:** always-on four + `reliability` (retry identity and idempotency
semantics of the write seam are acceptance-bearing). (F9 note: `api-contract` is skipped
because no new op-kind ships under the F3 disposition.)

**Leaf contract (#812, pasted with substitutions — F5 repair):** Acceptance criteria: (1)
`uv run pytest tests/test_saga_single_writer_guard.py -v` passes — no direct Stage write AND
no direct Status write remains in saga; every surviving reference to the write utilities is
submission-path only; (2) `uv run pytest plugins/mission-control/tests/ -k "set_field or
correction" -v` passes — submissions carry the field name in operation, authorization, and
retry identity; a non-Status (non-Stage) set-field is rejected; (3) `uv run pytest
plugins/mission-control/tests/ -k "certificate" -v` passes — certificate gates unchanged and
enforcing. Verification: `uv run pytest tests/test_saga_single_writer_guard.py
plugins/mission-control/tests/ -v`; then one live Status correction end-to-end on a scratch
issue *(Stage live-check substituted per F3 — no Stage field exists; receipt attached)*.
Stop conditions: none in the leaf.

### U8. #776 — retire the saga external-engine transport (lane S, S2; after O3, serialize S1)

**Goal:** Orchestrate owns all reviewer-session transport; saga keeps review policy (lenses,
scoring, consensus, typed `review_result.v1`); the legacy transport subsystem is removed with
no fallback path.

**Smallest viable fix (KTD4):** pure removal plus re-homing against U6's ownership boundary.
Remove the transport trio — `plugins/saga/scripts/engine_offer.py`,
`engine_session_runner.py`, `external_only.py` — and every stage-skill instruction that
invokes them: doc-review (`SKILL.md:124-165`), brainstorm (`:62-64`), code-review
(`:87-109`, `:294-295`), work (`:82-85`), ideate (`:51-53`); migrate the
`external_only_admitted` field carried by `review_consensus.py:478,497` and
`code-review/references/findings-schema.md:236` out with its writer (bounded migration note
in the PR). Orchestrate side: retire the `.saga/engine-prefs.json` seam — `write_engine_prefs`
(`orchestrate.py:1130-1148`, call at `:1241`), `Run.engine_prefs` (`:483-489`, `:525`, `:583`,
`:2502`, `:2807`), and the docs (`commands/orchestrate.md:129,133,254`,
`skills/orchestrate/SKILL.md:91`) — external-reviewer selection lives in the run plan and
persisted run record. `engine-registry.yaml` is retained and marked explicitly non-transport
(KTD4): it cannot override the live roster, and its 17 registry/calibration consumers are
untouched. The review-controller machinery orchestrate already has
(`REVIEW_CONTROLLER_ROLE`, `orchestrate.py:291`, `:610-614`, `:716`) is the reuse point for
"exactly one review-controller unit"; the unit verifies the refusal of plain review prompts /
direct reviewer launches / duplicate review units when a Code Review phase is present, and
adds the guard where it is missing, mutation-tested.

**Mechanism reused:** U6's shared launcher as the only session transport; orchestrate's
existing review-controller role and run record; the leaf's own required-behavior list as the
review checklist for the PR body.

**New moving part:** none — the change is removal and re-homing.

**Rejected alternative:** keeping `engine_session_runner` as a fallback (the leaf prohibits
fallback — halt instead); a replacement transport abstraction; deleting the registry
subsystem (KTD4 — no leaf authorizes it, 17 consumers depend on it).

**Test scenarios:** per the leaf: integration regression — one Opus 5 review controller plus
one Grok 4.6 reviewer seat, both as Orchestrate-owned named Herdr sessions, one typed
`review_result.v1`, no bespoke prompt, no `engine_session_runner` process, focus unchanged,
run-owned cleanup only; mutation guard — a plain review prompt or direct reviewer launch is
rejected before session creation. Transport tests are deleted with their code
(`tests/test_engine_offer.py`; the transport subset of `tests/test_saga_second_opinion.py` —
18 of 49 tests load the transport modules directly), per the contract's explicit
tests-deleted-with-code allowance; registry-side tests stay. Sweeps:
`rg -n "engine_session_runner|engine-registry|engine-prefs" plugins/saga plugins/orchestrate`
shows no launch authority outside the run record and only explicitly non-transport registry
metadata.

**Predeclared lenses:** always-on four + `reliability` (halt-not-fallback paths; the
half-migrated-stage failure mode the leaf pre-mortems) + `agent-usability` (five stage
skills' instruction text changes steer agent behavior) + `api-contract` (the
`review_result.v1` seam and the orchestrate refusal contract). (S2 note: do not add a fourth
conditional.)

**Leaf contract (#776, pasted — F5 repair):** Acceptance criteria: (1) `rg -n
"engine_session_runner" plugins/saga` — no launch-path reference remains; any surviving
mention is explicitly bounded migration/deprecation text; (2) `uv run pytest tests/ -k
"engine or review_transport" -q` — the integration regression passes (controller plus
reviewer seat both via Orchestrate-owned named Herdr sessions, one typed `review_result.v1`,
no duplicate review) and the mutation guard rejects a plain-prompt or direct-launch reviewer
before session creation; (3) `rg -n "engine-registry|engine-prefs" plugins/saga
plugins/orchestrate` — no session-launch authority outside the Orchestrate run plan and
persisted run record; retained capability metadata explicitly non-transport; (4) every
Required-behavior bullet implemented or carrying a written bounded-migration note in the PR
body. Verification: the two `rg` sweeps; `uv run pytest tests/ -k "engine or
review_transport" -q`; `uv run pytest tests/ -q`. Stop conditions (leaf, verbatim): stop
before launching when a reviewer is not represented in the Orchestrate run record; stop
before submitting work when Herdr cannot verify the requested vendor, model, effort,
worktree, and pane; stop rather than falling back to the legacy external-engine runner or
inventing a custom review; block landing and publication until the official Saga typed
result is terminal and accepted.

### U9. #778 — conditional-lens operator approval in Code Review (lane S, S3; serialize S2)

**Goal:** Code Review runs the exact four always-on lenses automatically and asks the
operator once — a single batched question — before launching any conditional lens; an
explicit caller/Orchestrate-supplied selection counts as approval; the approved set persists
per reviewed commit and cycle.

**Smallest viable fix:** skill-text plus a small approval record. Rewrite the lens-selection
instructions in `plugins/saga/skills/code-review/SKILL.md` (the current judgment-selection
text at `:45-50` and `:221-230`, which requires only announcement) to the leaf's nine
required behaviors: auto-run the always-on four; recommend conditionals with one
plain-language reason each; one batched choice (accept-recommended default / always-on only /
customize), combined with backend selection when the client supports it; caller-supplied
selection = approval, no re-ask; persist the approval against reviewed commit + review cycle;
reuse on repair cycles unless the diff materially changes applicability, then ask only about
the delta; pause with no conditional launches on dismissal/no answer; no hidden lens reviews.
Annotate `references/lens-catalog.md` and `plugins/saga/references/lens-roster.json` where
the selection contract is stated. The approval record reuses the existing review-cycle state
(the reviewed-commit + cycle record in `plugins/saga/scripts/review_consensus.py`) rather
than a new store.

**Mechanism reused:** the lens roster's `always-on`/`conditional` trigger classes (already in
`lens-roster.json`); the existing review-cycle state as the persistence home; the existing
`AskUserQuestion` / channel-inline interaction convention already documented in the skill
(`SKILL.md:66-70`).

**New moving part:** the approval record bound to commit + cycle — named in-scope failure:
the 2026-08-23 incident (session `34130998-1497-48bc-831b-424237e0e0b0`) where six lenses
launched with no question, four unapproved conditionals added and two always-on lenses
silently omitted; nothing structural prevents recurrence without a persisted approval the
launch path checks.

**Rejected alternative:** granting #418's selection adapter autonomous approval (explicitly
refused by the leaf); changing scoring/consensus/typed-result mechanics (out of scope).

**Test scenarios:** `tests/test_lens_roster.py` — the four always-on lenses are pinned;
removing any one fails. New focused lens-selection interaction test — a documentation-only
diff recommends `documentation-clarity` and declining launches only the always-on four; an
API/agent-facing diff recommends `api-contract` + `agent-usability` and approving launches
exactly those plus the always-on set; no conditional `Agent` call occurs before the approval
record exists (mutation-tested); a caller-provided selection is honored without a duplicate
question; an unchanged repair cycle does not re-ask; a materially changed diff asks once
about only the delta.

**Predeclared lenses:** always-on four + `agent-usability` (the change is agent-facing
instruction text plus an interaction contract agents must follow unattended).

**Leaf contract (#778, pasted — F5 repair):** Acceptance criteria: (1) `uv run pytest
tests/test_lens_roster.py -q` — the four always-on lenses are pinned and cannot be silently
omitted (removing any one fails); (2) `uv run pytest tests/ -k lens -q` — no conditional-lens
`Agent` call occurs without an approval record bound to the reviewed commit and cycle; a
caller- or Orchestrate-provided selection is honored without a duplicate question; an
unchanged repair cycle does not re-ask; a materially changed diff asks once about only the
delta; (3) `rg -n "always-on" plugins/saga/skills/code-review/SKILL.md` — the skill states
the automatic always-on set and the one batched conditional-lens question
(accept-recommended / always-on-only / customize) with the pause-on-no-answer rule.
Verification: the two pytest commands. Stop conditions: none in the leaf (required behavior
8 — pause with no conditional launches on dismissal/no answer — is the in-skill stop). (F13
correction: the judgment-selection text sits at `code-review/SKILL.md:48-51` and `:218-231`.)

### U10. #808 — Claude Code Workflow backend fit decision (lane D, D1; gate G1)

**Goal:** an evidence-backed operator decision — keep / narrow / replace / retire — on saga's
cc-workflows backend and its embedded verifier panels, recorded in
`docs/engineering-journal/DECISIONS.md`, then implemented or delegated to dependency-aware
follow-ups. Decision-first: current behavior is preserved until the operator rules.

**Smallest viable fix (rewritten per F2 — G1 is resolved: NARROW,
issuecomment-5405414716):** two phases, no HALT for a made decision. **Phase A (evidence,
read-only, starts at run start):** inventory every producer and consumer per the leaf's sweep
(`rg -n "cc-workflows-ultracode|Workflow\(|readonly-verifier|verify panel" plugins/saga
docs/plans docs/work-sessions`; planning baseline drifted already — `docs/plans/` now holds
20 committed `*-spec.json` files against the leaf's recorded 16, so the unit re-counts at the
pin); quantify observed unique findings, false halts, retries, token/session cost, and
operational failures with durable work-session evidence links; write the DECISIONS entry as
**validation of the recorded NARROW ruling** — the entry presents the evidence, cites
keep/replace/retire as considered-and-ruled-out by the operator's comment (not as an open
menu), and records the ruling's terms: Claude Code Workflows remain only explicitly invoked
task-local mechanisms inside Herdr-managed sessions, never a default/automatic Saga backend,
never a generic interchangeable execution backend. **Phase B (serialize S2 for the shared
work-skill text):** implement the smallest truthful narrowed shape — `plugins/saga/skills/plan/SKILL.md`
and `plugins/saga/skills/work/SKILL.md` text making explicit invocation the only path to a
Claude Code Workflow (no default/automatic backend selection, no silent substitute, no
backend-switching abstraction), `plugins/saga/references/execution-spec.md` and
`execution_spec.py`/its tests only if runtime behavior must change to enforce that — or file
dependency-aware follow-up issues whose combined acceptance criteria fully implement it.
HALT only if the evidence proves the narrowed shape internally contradictory or impossible;
that HALT returns to the operator with the contradiction, not with the four-way menu.

**Mechanism reused:** the engineering journal as the decision record (this unit is the
contract's enumerated DECISIONS writer); the existing regression suites
(`tests/test_saga_execution_spec.py`, `tests/test_saga_plugin.py`) as the retained-behavior
oracle.

**New moving part:** none in phase A. Phase B's shape is the ruling's to define.

**Rejected alternative:** re-presenting the four-way choice the operator already ruled on
(F2 — parking #808 and #708 for a decision already made); building a mechanism-neutral
backend-switching abstraction (prohibited by the ruling's own terms).

**Correction carried in the brief:** the leaf's verification names
`python3 scripts/check_docs.py`, which does not exist in the current tree; the unit runs the
repo's actual documentation checks (`scripts/lint_journal_order.py`,
`scripts/changelog_heading_lint.py`, `git diff --check`) and notes the substitution in its
evidence.

**Test scenarios:** phase A: inventory checks pinning every live producer/consumer (the
sweep's output reconciled against the decision record). Phase B (contingent): focused
execution-spec tests for the chosen disposition; regression proof that Saga Plan and Saga
Work cannot silently select an unsupported backend after implementation
(`tests/test_saga_execution_spec.py`).

**Predeclared lenses:** for the decision-record PR: always-on four + `documentation-clarity`
(the deliverable is a decision document read by a future operator). For a phase-B
implementation diff in this run: always-on four + `api-contract` (execution-spec surface
contract) + `agent-usability` (F9, S2-validated: the phase-B diff is plan/work SKILL.md
instruction text agents follow). Any other lens requires returning to the operator.

**Leaf contract (#808, pasted with substitutions — F5 repair):** Acceptance criteria: (1)
the sweep `rg -n "cc-workflows-ultracode|Workflow\(|readonly-verifier|verify panel"
plugins/saga docs/plans docs/work-sessions` — every producer, executor, generated artifact,
and committed spec it surfaces appears in the decision record's inventory (re-counted at the
pin; leaf baseline 37 panels / 16 specs is stale); (2) `grep -n "Claude Code Workflow"
docs/engineering-journal/DECISIONS.md` — a decision entry comparing the backend with Herdr
and Orchestrate responsibilities in concrete operating scenarios; (3) the entry quantifies
unique findings, false halts, retries, token/session cost, and operational failures with
durable evidence links; (4) the entry records the options and the explicit operator ruling
*(substitution per G1: the standing NARROW ruling issuecomment-5405414716 is cited as the
recorded decision — the four-way menu is not re-presented)*; (5) the selected decision is
implemented or dependency-aware follow-ups exist — `gh issue list --repo
infiquetra/infiquetra-claude-plugins --search "cc-workflows in:title,body" --state open`
names them; (6) `gh issue view 787 --json state -q .state` returns `CLOSED`, #787 and its
children unchanged; (7) `uv run pytest tests/test_saga_execution_spec.py
tests/test_saga_plugin.py -q` green; (8) documentation checks clean *(substitution: `python3
scripts/check_docs.py` does not exist — run `python3 scripts/lint_journal_order.py`,
`uv run python scripts/changelog_heading_lint.py` where applicable, and `git diff --check`,
noted in the evidence)*. Verification: the sweep, the pytest commands, and the substituted
documentation checks. Stop conditions: preserve current behavior until the recorded ruling's
implementation lands; HALT only on internal contradiction of the narrowed shape.

### U11. #708 — emitter engine-dispatch opts inert in the cc-workflows runtime (lane D, D2; after D1 ruling; gate G3)

**Goal:** engine-dispatch options in emitted execution specs are honored by the target
runtime or rejected loudly at emit time — never silently dropped so an engine unit runs as a
native Claude subagent.

**Smallest viable fix (rewritten per F1 — G3 is resolved: NARROW,
issuecomment-5405419292; KTD5):** the live defect is in `_agent_opts` at
`plugins/saga/scripts/execution_spec.py:2682-2694` — an engine-routed unit emits
`dispatch:`/`engine:`/`verifiability:` opts keys the cc-workflows runtime ignores and
carries no `model`/`effort` (the `else` branch adds them only for non-engine units); the
`// external-engine dispatch:` lines the emitter writes (`execution_spec.py:3097`, `:3122`,
`:3162`, `:3319`, `:3896`) are JS comments, visible but inert. The fix is **fail-loud
emit-time validation only**: an execution spec containing an external-engine unit, or opts
keys the cc-workflows runtime does not honor, is **rejected at emit** with a named,
actionable `SpecError` (the existing validator seam) telling the operator to route
cross-vendor work through Herdr/Orchestrate sessions instead. Never a silent fallback to a
native Claude subagent. **Prohibited by the ruling:** chaperone-wrapper prompts,
model/effort bridging, alias translation, long-running engine process management, or any
other cross-vendor dispatch surface in the emitter — Herdr and Orchestrate own cross-vendor
sessions. The leaf's chaperone-shaped acceptance items are satisfied as documented
substitutions: the reject path covers every case the chaperone form would have handled,
including bare model aliases (an engine unit fails at emit regardless of alias form).

**Mechanism reused:** the spec validator's existing HALT-not-degrade posture (emit-time
`SpecError` machinery in `execution_spec.py`) as the home for opts-key validation; the
guarded delegate wrappers as the only engine invocation path.

**New moving part:** none — validation added to an existing validator.

**Rejected alternative:** redesigning the workflow backend (that is U10's operator decision);
touching transport beyond the emitter seam (that is U8).

**Correction carried in the brief:** the leaf's file list names
`plugins/saga/scripts/workflow_emitter.py`, but on the current tree that module is a
workflow-lease contract (reserve/attest/renew/release; zero dispatch code) — the emitter seam
is `execution_spec.py` (KTD5). The unit re-anchors at its pin and records the correction in
its PR body.

**Test scenarios:** `tests/test_saga_execution_spec.py` — an execution spec carrying an
external-engine unit fails at emit with a named actionable error (no chaperone form is
emitted); a spec carrying opts keys the runtime does not honor fails at emit naming the key;
no code path emits inert engine opts or falls back silently to a native Claude subagent
(mutation-tested); a bare model alias in an engine unit fails at emit via the same reject
path.

**Predeclared lenses:** always-on four + `api-contract` (the fix is a spec→runtime options
contract made explicit and validated) + `reliability` (F9, S2-validated: post-G3 the whole
unit is fail-loud versus silent native fallback).

**Leaf contract (#708, pasted with substitutions — F5 repair):** Acceptance criteria: (1)
`uv run pytest tests/test_saga_execution_spec.py -q` — emit-time tests prove an engine unit
cannot emit inert dispatch opts *(substitution per G3: the honored form is rejection with a
named error; no chaperone alternative exists)*; (2) `rg -n "external-engine|dispatch"
plugins/saga/scripts/execution_spec.py` — every engine dispatch site routes through
emit-time validation; no silent-drop path remains *(substitution: the leaf's `rg` targeted
`workflow_emitter.py`, which is now a workflow-lease module with zero dispatch code —
KTD5)*; (3) a bare model alias in an engine unit fails at emit *(via the reject path — no
alias translation added, per the ruling)*. Verification: `uv run pytest
tests/test_saga_execution_spec.py -q`; `rg -n "external-engine|dispatch"
plugins/saga/scripts/execution_spec.py`. Stop conditions: the G3 boundary itself — no
chaperone, bridging, alias, or lifecycle machinery; reject-only; disposition questions
beyond the narrowed shape return to the operator.

## Predeclared lens roster (run view)

Always-on for every reviewed revision: `architecture-maintainability`, `correctness`,
`security`, `testing` (`plugins/saga/references/lens-roster.json`). Conditionals per unit,
locked by KTD7 — no addition without returning to the operator:

| Unit | Issue | Conditional lenses | One-line reason |
| --- | --- | --- | --- |
| U1 | #792 | — (no diff expected) | Verify-and-close; contingency diff is test-only → always-on only |
| U2 | #405 | deployment-infrastructure | Edits `ci.yml` and `gate.sh` — CI/infra configuration surface |
| U3 | #407 | — | Self-contained lint script + fixtures; no conditional domain |
| U4 | #725 | — (no diff expected) | Verify-and-close; contingency docs diff adds documentation-clarity |
| U5 | #813 | documentation-clarity, agent-usability | Docs-only guidance prose in an agent-consumed SKILL.md |
| U6 | #777 | api-contract, reliability, agent-usability, adversarial | New launch/readback contract with two consumers; readiness/timeout failure modes; new agent-facing skill; process-launch / silent-substitution / unowned-cleanup failure modes (F9) |
| U7 | #812 | reliability | Retry identity and idempotency of the board-write seam are acceptance-bearing (api-contract skipped — no new op-kind ships under F3) |
| U8 | #776 | reliability, agent-usability, api-contract | Halt-not-fallback removal paths; five stage skills' instruction text; `review_result.v1` + refusal contract |
| U9 | #778 | agent-usability | Agent-facing instruction text and an unattended interaction contract |
| U10 | #808 | documentation-clarity (decision PR); api-contract + agent-usability (phase-B impl diff) | Decision document deliverable; phase-B edits agent-followed plan/work skill text (F9) |
| U11 | #708 | api-contract, reliability | Spec→runtime options contract validated at emit; fail-loud versus silent native fallback (F9) |

## Scope Boundaries

Out of scope for the run (from the contract, binding): closed historical Objective members;
the two board draft cards; #704's stale board status; anything under other Objectives;
Herdr-core and `agents`-wrapper changes; all `infiquetra-agent-plugins` work (the #777 port is
infiquetra-agent-plugins#22 by the executed G2 ruling); deployment or tag promotion; new
intermediate parent issues; a second broad document review; new recovery/watcher/settlement
frameworks; `CLAUDE.md` (no writer this run).

Out of scope per leaf (binding, selected): #405 — the checkable-surface census, JSON
registries, drift detection, validator frameworks; #407 — prose-field enforcement and journal
schema validation; #776 — changes to saga review policy, any new vendor/model registry;
#778 — scoring/consensus/typed-result mechanics, external advisory seats; #808 — changing the
#692 quorum decision or draft PR #807; #708 — backend redesign, transport changes; #812 — the
#593 deepening, generic correction intake, arbitrary-field writers.

Deferred to follow-up work (distinct from non-goals): infiquetra-agent-plugins#22 (the #777
port); any #808 phase-B follow-up issues the ruling spawns.

## Risks and mitigations

- **A verify-and-close disposition (U1, U4) meets a contract written for merged-PR closures.**
  Mitigated: R10 requires the fresh rerun at the launch pin; the closing comment carries the
  fixing commit and receipts; the open-questions section flags the shape for the doc review.
- **The mermaid parser proves awkward headless (U2).** Mitigated: KTD2 names the bounded
  fallback (mermaid-cli), disclosed in the PR rather than silently swapped.
- **U8's removal breaks a stage that silently depended on engine-prefs.** Mitigated: the
  leaf's own pre-mortem; the sweep acceptance (`rg` over both plugins) plus the full suite at
  every merge point; halt-not-fallback preserved.
- **Sibling marketplace version collisions.** Known trap (silently auto-merging same-version
  bumps): serialized merges + re-bump at merge time + immediate reintegration (R3, R4).
- **Journal ordering guard reds a leaf PR.** LEARNINGS/DECISIONS are append-only newest-first
  with a PR-only CI step; leaves place entries at the top and reintegrate after every merge.
- **Lane D drifts from the recorded rulings.** Prevented: the U10/U11 briefs carry the G1/G3
  NARROW rulings verbatim; chaperone machinery and a re-opened four-way menu are named
  prohibitions; U11 remains `after: D1`.

## Run-level verification

Per the contract: every retained child truthfully terminal or parked-and-named; `bash
scripts/gate.sh` green at the final merged HEAD and GitHub CI green on main at that SHA; the
closing GraphQL board sweep shows every closed leaf Status=Done and Objective
`improve-claude-plugins` on all twelve cards; the closing comment enumerates PRs, per-lane
outcomes, typed review outcomes with any cycle-cap residuals, parked items with gates,
operator rulings, unexercised pools, and residual risks.

## Open questions — all resolved at S2/S3 (2026-08-25)

1. **No-PR closures for U1 (#792) and U4 (#725).** RESOLVED (S2 F8 + S3): verify-and-close
   per KTD1/R10 stands — evidence comments naming the historical fixing commits (PR #790 /
   `6396455a`; `84e53a72`), no no-op PRs; the parent-AC substitution is disclosed in the
   #814 closing comment.
2. **U2's Node dev dependency reaches `scripts/gate.sh` local runs.** RESOLVED (S2 question 5
   + F7): CI-blocking implies gate-blocking; the step is not advisory; Node missing locally
   stays exit 3; no mermaid-cli fallback (F6) — infeasibility HALTs with evidence.
3. **U8 retains `engine-registry.yaml` as non-transport metadata (KTD4).** RESOLVED (S2
   question 4): confirmed — the leaf's prohibition covers launch authorities, not calibration
   data with 17 script consumers; deleting the registry exceeds every leaf's scope.
