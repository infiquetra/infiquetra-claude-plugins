# Doc review — house-style implementation plan (issue #704)

**Target.** `docs/plans/2026-08-08-issue-704-house-style-output-style-plugin-plan.md`, reviewed together
with the two artifacts that actually execute: the execution spec
`...-spec.json` and the emitted workflow `...workflow.js`.

**Reviewed revision.** Working tree on branch `docs/output-styles-requirements-review`, parent commit
`c9e0ca48`, after the refute-3 verify panel was added to U5 at the operator's instruction.

**Blocked status.** Not blocked. One P0 and two P1 findings were found and all were fixed in place. No
unresolved P0 or P1 remains, so `/work` is not gated.

**Linked artifacts.** Issue infiquetra/infiquetra-claude-plugins#704 · plan and spec as above ·
requirements document `docs/brainstorms/2026-08-07-output-styles-requirements.md` · saga `issue-704`.

## Verdict

The plan was structurally sound and its numbers held up, but two of its safety mechanisms were not
doing the work the document claimed for them — one gate would have halted the run on a broken test, and
one guard was passing over empty input. Both are fixed. The document can now drive implementation.

## Findings

| # | Priority | Finding | Status |
| --- | --- | --- | --- |
| D1 | P0 | U1's Lever A experiment tests a file the runtime never loads, so the gate would halt the run and reopen a blocker over a working mechanism | Fixed |
| D2 | P1 | The concurrent-writer guard was vacuous: no unit declared any file, so it compared empty sets and reported safety it never checked | Fixed |
| D3 | P1 | U4's stated dependency (`U3`) contradicted the execution spec (`U3, U5, U6, U8`), and the plan is what each agent reads as authoritative | Fixed |
| D4 | P1 | U1's Lever B told the agent to execute the emitted workflow, which a workflow agent cannot do; the spec said emit-and-grep | Fixed |
| D5 | P2 | The Problem Frame claimed baseline provenance for a hand-labelled 10-and-9 sample that is not in the baseline file | Fixed |
| D6 | P2 | KTD6's release-surface arithmetic ("11 `marketplace.json` entries move") was wrong on every reading | Fixed |
| D7 | P2 | U9 read as bumping `house-style` to 0.2.0 for its first release | Fixed |
| D8 | P2 | Roughly 70 files in one pull request, above the sizing rubric's threshold; the natural split is U5 | Recorded, not applied |
| D9 | P3 | No requirement-to-unit mapping table; coverage was verified by hand and is complete (R1–R14 all land) | Not applied |

### D1 — the gate would have fired on the harness

U1 is the plan's gate: it proves both reach levers before anything is built on them, and its instruction
is deliberately absolute — a marker that does not appear halts the run and reopens the requirements
document's R27 blocker, with no adapting around it.

Its method for Lever A was to write a throwaway agent definition into `plugins/<p>/agents/` and spawn
that agent type. Agent definitions are not loaded from the working tree.
`~/.claude/plugins/installed_plugins.json` resolves every Infiquetra plugin to a versioned cache
directory — saga at `0.131.0`, team-execution at `3.0.0` — and `~/.claude/plugins/marketplaces/
infiquetra-plugins` is a separate clone pinned at `f6436f6` with a different inode from the working
tree. The marker would have been absent, and absence would have been read as disproof.

**Applied fix.** U1 now tests through the loaded cache: the preferred method writes nothing and checks
whether an installed agent honours a falsifiable commitment its definition makes. The hard stop is
untouched. A third outcome was added — a harness failure returns `inconclusive`, never a disproof and
never a pass — and the escalation now halts on `inconclusive` too, because a test that could not run is
not a lever that works. The load-path fact is in the Grounding table so it cannot be lost again.

**Related, unresolved by evidence.** Whether an agent running inside a workflow can spawn another agent
at all is undocumented in this repository and was not established during planning. It is recorded as an
unverified assumption that U1 resolves as its first action, rather than asserted either way.

### D2 — a guard passing over nothing

The plan's dependency-waves section claimed no two units in a wave declare the same file, and the
tooling agreed. `Unit.files` exists (`execution_spec.py:1255`) and `assert_no_wave_file_conflicts`
compares declared paths pairwise per authored wave at emit time (`:1888`, called from `:3627`) — but not
one of the nine units declared a `files` field, so the guard intersected empty sets. It would have
reported the same reassurance for a spec in which every unit wrote the same path.

**Applied fix.** All nine units now declare their files: 76 paths, with the 36 agent definitions
enumerated by name rather than globbed, which also gives U6 the exact expected-file list its own
requirement asks for. The guard was verified non-vacuous by making U6 and U8 share
`plugins/saga/agents/readonly-verifier.md`, which fails emission with `wave 4: U6 and U8 both declare
...`; the real spec emits clean.

**Worth knowing.** The guard reasons over *authored* waves. This spec emits every wave serialized to
width 1, so nothing runs concurrently in practice and the guard could not have found a collision even
with perfect data. Two independent reasons for a vacuous pass, stacked.

### D3, D4 — plan and spec disagreed

U4's section said "Depends on: U3" while the spec said `["U3","U5","U6","U8"]`. Every unit prompt tells
its agent to read the plan as authoritative, so the stale line was the one that would have been obeyed.
The spec's version is also the correct one, and now the plan says why: U4 proves its assertions by
temporarily stripping the contract from the style file, so nothing that reads that file can be in
flight beside it.

U1's Lever B told the agent to "run one unit through" the emitted workflow. A workflow cannot be
launched from inside a workflow agent, and the spec had it right — emit the script and grep it, which is
what the reach claim is actually about. The plan now matches, and says why executing is neither possible
nor necessary.

### D5–D7 — smaller corrections

The Problem Frame said two facts were "re-derived from the baseline rather than carried across document
hops", then stated four figures, two of which are a hand-labelled 19-case sample living in the
requirements document. The baseline's two complaint metrics are explicitly keyword proxies, not that
sample. Both real figures were re-derived here (11/407 = 2.7027%, 128,622/225,579 = 57.0186%) and the
hand-labelled pair is now labelled as direction-only evidence with its true source named.

KTD6 said "9 `plugin.json` versions, 9 `CHANGELOG.md` files, and 11 `marketplace.json` entries move".
Nine plugins get preamble edits, plus `house-style` itself makes 10 of each; in the marketplace, 9
entries are re-versioned and 1 is added, taking the file from 11 entries to 12. No reading made 11
correct.

U9 said to "bump `plugin.json` … for house-style", which would ship a brand-new plugin as 0.2.0. It is
released at the 0.1.0 U2 creates.

### D8 — recorded, deliberately not applied

At roughly 70 files this exceeds the sizing rubric's one-pull-request guidance, and the natural split is
U5, the single edit whose blast radius leaves this repository. Splitting is not applied: it is a scope
decision belonging to the operator, and it costs a second round of the same U1 gate. It is recorded in
Open Questions and in the risk table so the choice is visible rather than implicit.

## Verified rather than assumed

Every figure in the Grounding table was re-derived. All held: 36 agent definitions across 9 plugins with
25 in `team-execution`; `execution_spec.py:464` is `BUDGET_RIDER` and `:3244` is `_agent_prompt`; the
marketplace carries 11 plugins at metadata `3.0.0`, and all 9 agent-owning plugins are among them; both
named drift-guard tests exist.

Two figures were checked because they looked wrong and turned out to be right. The scorer's test count is
**29**, not the 21 a `grep -c "def test_"` reports — the tests are parametrized, and
`pytest --collect-only` is the authority. The baseline carries exactly **9** metrics, so U7's "the nine
existing metrics" is exact. Three rows recording these were added to the Grounding table so the same
false alarm is not raised twice.

`docs/measurements/2026-08-07-baseline.json` is byte-identical to its committed state and was never
opened for writing.

## Residual risk

The largest remaining unknown is not in the document: whether a workflow agent can spawn another agent.
If it cannot, U1 cannot test Lever A from the chosen backend and will report `inconclusive`, which halts
for an operator decision rather than failing the lever. That is the designed behaviour, but it means the
run can stop at its first unit for a reason no amount of document review could settle in advance.

Second: both levers edit the working tree while the runtime loads from a versioned cache, so "merged"
and "in effect" are different events. The after-measurement is only meaningful once the plugin versions
are published and a new session has started. This is recorded in the plan's Open Questions.
