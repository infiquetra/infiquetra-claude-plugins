---
title: "capability(house-style): ship the house-style output-style plugin and its two subagent reach levers"
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
risk: high
labels: capability, hermes-task, needs-plan
handoff_maturity: requirements-ready
---

# capability(house-style): ship the house-style output-style plugin and its two subagent reach levers

### Objective

Ship one Claude Code output style as a new plugin, `house-style`, in this repository and distributed
through the `infiquetra-plugins` marketplace that both the `~/.claude` and `~/.claude-company`
configurations load. The style fixes three measured failures in how terminal output is shaped: every
state-changing turn closes with a statement of what is now true plus the one decision belonging to the
operator; visuals appear when the reader is being oriented and not otherwise; and subagent output is
digested into the main thread's own voice rather than pasted.

Because an output style governs only the main conversation thread, and **57.02% of all assistant
output is generated inside subagents where no style has any effect**, the presentation contract also
ships through two levers that are code this repository owns: a stamp added by saga's workflow emitter,
and a duplicated preamble in the agent definition files under `plugins/*/agents/*.md`.

All 36 requirements, the evidence behind each, and eleven settled framing decisions are in
`docs/brainstorms/2026-08-07-output-styles-requirements.md`. That document is the specification; this
card is its tracking surface and does not restate it.

### Intent

The operator supervises five or six concurrent workstreams and does not carry the working references
of whichever thread was just opened. The two dominant prompt modes across every repository are
approval-or-continuation and status-check, which are the same underlying question: *is this waiting on
me?* Measured across 35 days, only **2.70%** of sessions end on a line that answers it. All ten
responses that drew a satisfied reply ended with a single concrete ask; five of nine traced complaints
ended on a trailing aside. Length and formatting do not discriminate between the two sets — placement
does. The cost is paid in re-reading, and the fix is a turn shape, not a tone.

**Reach is bounded and the bound is stated up front, because it moved once already.** The two levers
together reach **45.7%** of subagent output — the emitter stamp 15.73%, the definition-file preamble
29.93% — and nothing in this work may claim more. That ceiling replaces an earlier figure of 89.4%,
which credited the emitter with all `workflow-subagent` traffic. Partitioning that traffic by the
script that spawned it shows the emitter produces 26.46% of it and hand-authored workflow scripts
produce 73.41%. The largest single block of subagent output in the corpus is therefore the **43.64%**
written by hand, which neither lever touches, and it is named rather than absorbed.

### Out-of-scope / non-goals

- **Per-repository committed settings** and the `.gitignore` change they would require. Deferred by the
  one-style decision, not cancelled.
- **A second style file**, and with it any byte-identity test policing two style files against each
  other. The byte-identity test itself is **in** scope, for a different artifact — it polices the
  preamble duplicated across the 36 agent definition files.
- **Any generator or build step.** There is no build step in the loading path, so whatever ships must
  be plain Markdown.
- **Pruning any Plain English rule from `~/.claude/CLAUDE.md`.** All seven stay, unpruned and
  unrewritten. The style is purely additive.
- **The bare-Default control run.** Skipped by operator decision on 2026-08-07 — ruled out, not
  scheduled. The cost is accepted and stated: the after-measurement can show whether shipping the style
  improved things but cannot attribute how much belongs to the style versus to `CLAUDE.md`.
- **Regenerating `docs/measurements/2026-08-07-baseline.json`.** It records behaviour before any custom
  style existed and that window closed permanently once one ships. Re-running the scorer to any *other*
  output path is safe and expected.
- **`force-for-plugin: true`.** The plugin does not override the operator's own style selection.

### Files expected to change

- plugins/house-style/.claude-plugin/plugin.json — new plugin manifest
- plugins/house-style/output-styles/house-style.md — the style file itself
- plugins/house-style/README.md and plugins/house-style/CHANGELOG.md — release surfaces
- .claude-plugin/marketplace.json — register the new plugin
- plugins/saga/scripts/execution_spec.py — stamp the presentation preamble into emitted `agent()`
  prompts (`emit_workflow_script()` line 3590; per-unit `prompt` field line 1249)
- plugins/*/agents/*.md — duplicate the shared presentation preamble into all 36 definition files
- tools/output_style_scorer.py — add the visual-gating and relay-quality measurements (R32, R33)
- tests/test_output_style_scorer.py — extend the 29 existing tests to cover the two new metrics
- docs/engineering-journal/LEARNINGS.md — update the provenance procedure for the new tell (R35)
- `~/.claude/CLAUDE.md` — annotate the Communication section with the reach partition and its
  one-question test (R18). Outside version control; see Failure modes.

### Tests to add or update

- `tests/test_output_style_scorer.py` — extend the existing 29 tests to cover the two new metrics.
- A byte-identity test asserting the presentation preamble is identical across all 36 agent definition
  files. This is required, not conditional: ideation's survivor 10 asked for it specifically because
  the preamble duplicates one block across N files.
- A test asserting the style declares `keep-coding-instructions: true` explicitly (R28) and carries its
  placard section (R29), so neither can be lost to an edit (R30).
- A test asserting the emitter stamp is present in emitted scripts, added beside the existing
  `execution_spec.py` suite.
- Release-surface parity: `plugin.json` version, `marketplace.json` entry, and `CHANGELOG.md` must tell
  the same story as the diff, per the repository's standing rule.

### Context library links

- `docs/brainstorms/2026-08-07-output-styles-requirements.md` — the specification: 36 requirements,
  8 acceptance examples, 11 settled decisions, the agent census, and the emitter partition.
- `docs/reviews/2026-08-07-output-styles-requirements-doc-review.md` — the document review, 19 findings
  all fixed, with the rejected lines of reasoning and the residual risk.
- `docs/ideation/2026-08-07-output-styles-ideation.md` — ten ranked survivors and fifteen revivable
  rejects.
- `docs/measurements/2026-08-07-baseline.md` and `.json` — the pre-change measurements. Write-once.
- `docs/engineering-journal/DECISIONS.md` `{#house-style-hybrid-subagent-route}` — the three operator
  decisions and the 2026-08-08 amendment correcting the ceiling.
- `docs/engineering-journal/LEARNINGS.md` `{#attribution-labels-name-the-runtime-not-the-author}` and
  `{#measure-the-agent-population-before-choosing-a-lever}`.

### Acceptance criteria

- [ ] **Both levers are proven by experiment before anything is built on them.** Create an agent
      definition carrying a distinctive marker, spawn that agent type, and confirm the marker reaches
      the output; then the same for the emitter lever. A failure reopens the R27 blocker and is
      reported rather than worked around.
- [ ] `plugins/house-style/` exists, is registered in `.claude-plugin/marketplace.json`, and loads in
      both configurations.
- [ ] The style declares `keep-coding-instructions: true` explicitly and carries a placard naming what
      it suppresses, with a test asserting both.
- [ ] The presentation preamble is byte-identical across all 36 agent definition files, with a test
      asserting it.
- [ ] The emitter stamps the preamble into emitted `agent()` prompts, with a test asserting it.
- [ ] The style emits a distinctive literal string containing no box-drawing characters, so the active
      style is confirmable by grep rather than by impression (R31).
- [ ] The scorer measures visual gating and relay quality, and both have a pre-style value produced by
      re-running it over the archived window to a **new** output path.
- [ ] No document, commit message, or code comment claims reach above **45.7%**, and the 54.3% residue
      is named rather than assigned to either lever.
- [ ] `docs/measurements/2026-08-07-baseline.json` is byte-identical to its committed state.
- [ ] The `~/.claude/CLAUDE.md` Communication annotation is in place and all seven Plain English rules
      are unchanged.

### Verification

```bash
# Full local gate — CI runs ruff check AND ruff format --check; a check-clean tree still fails the format gate
uv run ruff check .
uv run ruff format --check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
uv run bandit -r plugins/
uv run pytest --cov=plugins

# The baseline must be untouched
git diff --exit-code docs/measurements/2026-08-07-baseline.json

# The style is confirmable by grep, not by impression (R31)
grep -rn "<the tell>" plugins/house-style/output-styles/

# The preamble is byte-identical across all 36 definition files
uv run pytest tests/ -k preamble_identity -v

# No downstream claim exceeds the ceiling
grep -rn "89\.4\|59\.44%" docs/plans/ plugins/house-style/ || echo "no stale reach claims"
```

### Inputs inventory

- `docs/brainstorms/2026-08-07-output-styles-requirements.md` — the specification.
- `docs/measurements/2026-08-07-baseline.json` — six Success Criteria figures, read-only.
- `tools/output_style_scorer.py` — the instrument, 29 passing tests, extended by R32 and R33.
- `plugins/saga/scripts/execution_spec.py` — the emitter, 4,405 lines; the stamp site is a design
  question still open.
- The 36 files matching `plugins/*/agents/*.md`, 25 of them in `team-execution`.
- `~/.claude/CLAUDE.md`, 99 lines, and its symlink from `~/.claude-company/CLAUDE.md`.

### Failure modes / pre-mortem

- **The experiment fails and a lever does not work.** Both levers are inference from repository
  structure and transcript fields; neither has been observed working. This is why the experiment is the
  first acceptance criterion rather than a later validation step. A failure reopens the blocker.
- **The reach number inflates again in a downstream document.** It already inflated once, from 45.7% to
  89.4%, by crediting a lever with traffic that carried a label naming the runtime rather than the
  author. The same shape recurs whenever a percentage is copied across a document hop without its
  derivation. The verification block greps for the stale figures.
- **Editing `execution_spec.py` has repository-wide blast radius.** It composes the prompt for every
  agent every saga workflow spawns. A malformed stamp degrades every workflow agent in every repository
  that runs saga, not only this work.
- **The 36 duplicated preambles drift.** Duplication across N files is exactly the failure the
  byte-identity test exists to catch, which is why the test is required rather than conditional.
- **The R18 annotation lands outside version control.** Neither `~/.claude` nor `~/.claude-company` is a
  git repository, so that one deliverable is unversioned and unbacked wherever it lands. Whether it
  needs a version-controlled home of its own is deferred to planning, not settled.
- **The style gets switched off.** A ceremony firing on fifty short exchanges a day becomes noise, and
  a disabled style costs every rule in the file rather than just the annoying one. R9's size-threshold
  exemption is the control, and its threshold is still unset.
- **`tools/` is outside the `mypy` and `bandit` CI scopes** and `pytest --cov=plugins` gives the
  scorer's tests no coverage credit. The scorer is linted and format-gated but not type-gated in CI.

### Stop conditions

- Either lever fails its marker experiment → stop, report, reopen the R27 blocker. Do not route around.
- Any change would write to `docs/measurements/2026-08-07-baseline.json` → stop. That file is
  write-once and the pre-style window has closed permanently.
- A reach claim above 45.7% appears in any artifact → stop and re-derive before proceeding.
- The emitter stamp breaks any existing `execution_spec.py` test → stop; the blast radius is every saga
  workflow in every repository.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: docs/brainstorms/2026-08-07-output-styles-requirements.md
- Source type: brainstorm
- Source title: Custom Claude Code output styles — requirements

### Recommended Tier Band
opus/high

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/704
- Number: 704
- Created at: 2026-08-08T04:13:27.859902+00:00

