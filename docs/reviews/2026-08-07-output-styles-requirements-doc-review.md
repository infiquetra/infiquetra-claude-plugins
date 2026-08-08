---
title: Doc review — Custom Claude Code output styles requirements
type: doc-review
date: 2026-08-07
target: docs/brainstorms/2026-08-07-output-styles-requirements.md
blocked: false
blocked_history: "true until 2026-08-07, when the operator settled the R27 delivery route"
---

# Doc review — output-styles requirements

## Review-result contract

| Field | Value |
|---|---|
| Target | `docs/brainstorms/2026-08-07-output-styles-requirements.md` |
| Reviewed revision | working tree (document is untracked); repo `HEAD` = `f6436f6e`; branch `docs/output-styles-requirements-review` |
| Blocked | **No, as of 2026-08-07** — was Yes; the R27 delivery-route blocker this review opened was settled by the operator the same day. See Resolution below. |
| Findings | 19 raised — 1×P0, 4×P1, 7×P2, 7×P3 — all 19 fixed |
| Applied fixes | 17 edits to the requirements document, 2 Python files reformatted |
| Rubric review | Not run — the artifact is a brainstorm requirements document, which maps to none of the engine's `idea` / `issue` / `spec` phases |
| External panel | Not run — `engine_offer.py` returned `prompt_required: false` from a stored preference |
| Linked issue | none |

## Readiness summary

**The document can drive planning, but not yet implementation, and the reason is one requirement
that described a mechanism Claude Code does not have.** R27 proposed reaching subagents by placing a
shared presentation preamble in the `agents/` directory. The symlink it relies on is real, but a `.md`
file in an `agents/` directory defines one named agent rather than prepending text to every agent's
prompt — and `~/.claude/agents/` is empty, so such a file would govern nothing that actually runs.
Since the 57.02% of output generated inside subagents is the document's central structural claim, a
requirement that appears to address it but cannot is the most consequential defect available here.

Everything else is fixed and verified. All six figures in the Success Criteria table were re-derived
from the committed baseline and agree exactly. One figure in the Problem Frame did not, and was
corrected.

## Findings

| # | Pri | Finding | Status |
|---|---|---|---|
| D1 | P0 | Both transferred Python files fail `ruff format --check .`, which CI runs repo-wide; committing them as-is turns CI red | Fixed |
| D2 | P1 | R27's reach mechanism is wrong — an `agents/` file defines one agent, and `~/.claude/agents/` is empty | Fixed in text; underlying decision now an explicit blocker |
| D3 | P1 | The byte-identity test was retired on reasoning that covers only the style file; ideation's survivor 10 needed the same test for preamble duplication across N agent files | Fixed |
| D4 | P1 | R34 said the scorer ships "inside the new plugin", contradicting four other references and the completed transfer | Fixed |
| D5 | P1 | R32 and R33 add metrics with no stated route to a baseline, inviting regeneration of the one file that must never be regenerated | Fixed |
| D6 | P2 | "The worst single message in the corpus was 12,347 characters" — the source says one of the three worst, and the corpus maximum is 26,994 | Fixed |
| D7 | P2 | Key Decisions required a git worktree on the grounds that a feature branch was live; it has landed | Fixed |
| D8 | P2 | R34 described the scorer as running from `~/bin`, "which is not a git repository" — stale after the transfer | Fixed |
| D9 | P2 | R36 was written as outstanding work although the transfer satisfied it | Fixed |
| D10 | P2 | Success Criteria carry directions but no target values, and the gap appeared in no deferral list | Fixed |
| D11 | P2 | Median 142 / p90 1,658 bound R9's threshold but are not reproducible from the committed scorer | Fixed |
| D12 | P2 | Neither `~/.claude` nor `~/.claude-company` is a git repository, so the R18 and R27 deliverables are unversioned — the same concern R34 raises for `~/bin` | Fixed |
| D13 | P3 | The `.saga/` false-positive repository was unnamed, against Plain English rule 2 | Fixed |
| D14 | P3 | `★ Insight` was called "the discriminator"; `LEARNINGS.md:4171` uses it as one of three conjoined signals | Fixed |
| D15 | P3 | The "Deferred to planning" list was split by a stray blank line | Fixed |
| D16 | P3 | "The Communication section is the largest at 25 lines" was ambiguous about whether the heading counts | Fixed |
| D17 | P3 | Actor A3 said "57%" where the rest of the document says 57.02% | Fixed |
| D18 | P3 | R3 specifies a shape but had no acceptance example, and it is the I-PASS element Sources calls least-copied | Fixed — AE8 added |
| D19 | P3 | The marketplace plugin count was unstated | Fixed — 11, recorded under Verified |

## Verification performed

Every claim below was re-derived rather than accepted from the document.

| Claim | Method | Result |
|---|---|---|
| Six Success Criteria figures | Compared against `docs/measurements/2026-08-07-baseline.json` | All six agree to stated precision |
| 57.019% subagent share | Re-ran the scorer over the same window to a scratch path | Reproduced; all 9 metrics identical after reformatting |
| 35-day window | `2026-07-03` to `2026-08-07` | 35 days |
| `~/.claude-company/agents` symlink | `ls -ld` | Points at `~/.claude/agents` |
| `~/.claude-company/CLAUDE.md` symlink | `ls -ld` | Points at `~/.claude/CLAUDE.md` |
| `~/.claude/agents/` contents | `ls -la` | **Empty** |
| No `output-styles/` in either configuration | `ls -d` | Neither exists |
| No plugin declares an output style | Grep of `marketplace.json` and every `plugin.json`; `find` for `output-styles` dirs | None; 11 plugins present |
| `CLAUDE.md` is 99 lines | `wc -l` | 99 |
| Communication is the largest section | Heading offsets | Lines 15–40, largest of nine |
| `.gitignore` line 56 is `.claude/` | `grep -n` | Confirmed |
| `git ls-files .claude/` returns nothing | Direct | 0 files |
| `★ Insight` provenance entry | `LEARNINGS.md` | Present at line 4171, three conjoined signals |
| 10 survivors, 15 rejected, 6 frame outputs | Counted in the ideation document and run directory | 10 / 15 / 6 |
| 12,347-character message was the worst | `frame1-pain.md:137` and ideation line 49 | **False** — one of three worst; maximum is 26,994 |
| Scorer computes length percentiles | Grep for median/p90/percentile | **It does not** |
| Baseline-window transcripts retained | `find -newermt` | 2,515 files still on disk |
| CI gate scopes | `.github/workflows/ci.yml` | `ruff` repo-wide; `mypy`/`bandit` exclude `tools/`; `--cov=plugins` |
| 29 scorer tests pass after reformatting | `pytest -q` | 29 passed |

## Rejected lines of reasoning

- **"R32 and R33 can never have a baseline, because the pre-style window has closed."** Rejected. The
  transcripts in the measured window are immutable and still on disk, so pointing the extended scorer
  at the same window with a new `--out` path yields genuine pre-style values. The document now records
  this route.
- **"Regenerate the baseline so the new metrics are included."** Rejected on the operator's standing
  instruction and on the merits: `docs/measurements/2026-08-07-baseline.json` records behaviour before
  any custom style existed, and that window closed permanently once one ships. Overwriting it would
  replace the only record of the unstyled world with a styled measurement.
- **Adding an acceptance example for R2.** Rejected. R2 is an unconditional prohibition and states its
  own test; an example would be invention rather than illustration. AE8 was added for R3 only, because
  R3 specifies a shape and the document's own Sources section flags that shape as the one most often
  dropped.

## Residual risk

The three candidate routes recorded under R27's blocker were reasoned from verified repository
evidence, not tested. Nobody has yet placed a preamble file in `~/.claude/agents/` and observed
whether a running subagent picks it up. The finding rests on the directory being empty, on all 36
agent definitions in this repository being single-agent files keyed by a `name:` field, and on every
agent available in the session coming from a plugin or from Claude Code itself. That is strong
circumstantial evidence for the mechanism, and it is not a direct experiment.

The `bare_identifier_rate` metric is labelled heuristic by the instrument itself and is a trend line
rather than a verdict on any single message. The Success Criteria table inherits that limitation.

## Resolution — 2026-08-07, same day

The blocker this review opened is closed. The operator settled three decisions, and one of them was
settled by a measurement this review should have taken and did not.

**The census.** Every subagent transcript record carries an `attributionAgent` field, so the question
"which agents actually produce the 57.02%?" was answerable directly rather than by reasoning about
repository structure. Counted over the baseline's exact window, roots, and exclusion, the total is
128,622 — equal to `subagent_assistant_messages` in the committed baseline, so it is cross-validated
against the instrument rather than being an independent guess. `workflow-subagent` is 59.44% and has
no definition file; the four agent types that do have one total 29.93%. That retired route (a), the
route this review had presented as ideation's own answer.

**Decisions recorded.** The plugin is named `house-style`. R27 takes a hybrid route: the preamble is
stamped into spawn prompts by saga's emitter (`plugins/saga/scripts/execution_spec.py`,
`emit_workflow_script()` line 3590) for the 59.44%, and duplicated into the 36 repo-owned agent
definitions with the byte-identity test restored for the 29.93% — combined ceiling ~89.4%, with the
10.63% residue named rather than absorbed. The bare-Default control run is skipped, not deferred, with
its attribution cost recorded.

**One correction to this review's own figures.** It reported "the 400 agent files under
`~/.claude/plugins/cache/`" secondhand, attaching a whole-tree count to a subtree path. Both counts
are right at their own scope: 226 agent `.md` files under `~/.claude/plugins/cache/`, and 400 under
all of `~/.claude/plugins/`, which also spans `marketplaces/` and `repos/`. The document now uses 226
and names the scope. The conclusion is unaffected — neither tree is a durable lever, because both are
overwritten on plugin update.

**The reach ceiling fell from 89.4% to 45.7%, and the cause was a measurement this Resolution had
left open.** The paragraph below originally recorded, as an open question, whether all
`workflow-subagent` traffic comes from saga-emitted scripts. It does not, and the question was
answerable from the same transcripts: each workflow subagent file sits under a `wf_<runid>` directory
naming its run, and each run persists the full text of the script that ran. Classifying those scripts
by an emitter helper that has been byte-stable since before the window opened gives 26.46%
emitter-produced and 73.41% hand-authored. R26's reach is therefore 15.73% of subagent output rather
than 59.44%, the combined ceiling is 45.7%, and the largest single block of subagent output in the
corpus — 43.64%, from workflow scripts written by hand — is reached by neither lever. The hybrid
decision stands; only its reach figure changed. See LEARNINGS
`{#attribution-labels-name-the-runtime-not-the-author}`.

**Still unverified, and gating the plan.** Neither lever has been observed working. The mechanism is
inference from repository structure and transcript fields. The plan must create an agent definition
carrying a distinctive marker, spawn that type, confirm the marker reaches the output, and repeat for
the emitter lever. A failure reopens the blocker rather than being routed around.

See DECISIONS `{#house-style-hybrid-subagent-route}` and LEARNINGS
`{#measure-the-agent-population-before-choosing-a-lever}`.
