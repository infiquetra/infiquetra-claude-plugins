# Document review — issue 1022 roles library plan

The plan is ready to drive implementation. Five findings were raised and all five were repaired in place with evidence; none remains open, so nothing blocks `/work`.

## Review result

| Field | Value |
|---|---|
| Target | `docs/plans/2026-09-19-issue-1022-roles-library-plan.md` |
| Reviewed revision | working tree, branch `issue/1022`, base commit `2044c363` |
| Blocked | no |
| Findings | 5 raised — 2 `P1`, 3 `P2`; 0 open |
| Applied fixes | 6, all safe fixes in place, across two rounds |
| Rounds | 2 — the second re-read the edited regions and caught one leak |
| Review artifact | `docs/reviews/doc-review-issue-1022-2026-09-19.md` |
| Override rationale | not applicable — no finding was overridden |
| Linked issue | infiquetra/infiquetra-claude-plugins#1022 |
| Linked plan | `docs/plans/2026-09-19-issue-1022-roles-library-plan.md` |
| Saga | `issue-1022`, plan phase complete |

Classification: plan. The document sits under `docs/plans/`, carries `origin:`, `Implementation Units`, `Key Technical Decisions` and the `U1` prefix, so the readiness-skeptic pass applied and the formal rubric engine did not — the rubric phases cover blueprints, architecture decision records and issues, none of which this is.

## Findings

| # | Priority | Finding | Status |
|---|---|---|---|
| D1 | P1 | The forbidden-vocabulary rule contradicted the README's own job | fixed in place |
| D2 | P1 | The `emits` frontmatter key could not hold the contracts two roles emit | fixed in place |
| D3 | P2 | The test was told to read a map the plan never gave a parseable shape | fixed in place |
| D4 | P2 | The sibling SDLC checkout had no resolution rule | fixed in place |
| D5 | P2 | The marketplace regenerator's whole-file scope was an unflagged hazard | fixed in place |

### D1 (P1) — The forbidden-vocabulary rule contradicted the README's own job

Requirement R6 forbade any file in `roles/` from referencing `team-execution`, and unit U6's happy-path scenario said "no file contains `team-execution`". Requirement R10 and unit U1 simultaneously require the README to carry a table accounting for where each of the 25 retired `team-execution` prompts went, which cannot be written without naming them. An implementer following the document literally would write a test that fails against the README the moment both units land.

*Fix.* R6 now binds role prompts only and states the README exemption and its reason; U1's approach states both README exemptions together; U6's happy path and forbidden-vocabulary scenarios now exclude the README and add a positive case asserting the real README passes. The evidence is internal to the document — R10 and U1 already required the accounting — plus the card's own acceptance criterion, which already carves the README out of the `### Stop rule` rule.

### D2 (P1) — The `emits` frontmatter key could not hold the contracts two roles emit

KTD7 and U6 treated `emits` as naming one handoff contract. Unit U2 assigns the Planner two (`planner-to-orchestrator` and `repair-amendment`) and the Delivery Manager five (`orchestrator-to-controller`, `dispatch`, `investigation-request`, `release-handoff`, `run-record`). An implementer would have written a single-string key and then had nowhere to record the Delivery Manager.

*Fix.* R4 and KTD7 now state `emits` is a YAML list, never a bare string, and name the two roles that force it. U6's frontmatter scenario checks every entry, adds a failing case for a bare string, and adds passing cases for the real two-entry and five-entry files. The evidence is the contract catalogue in `infiquetra-sdlc` `docs/process/run-contracts.md:161-217`, which the plan already cites.

### D3 (P2) — The test was told to read a map the plan never gave a parseable shape

U6 said the expected role set is read from the README's map rather than hard-coded, which is the right call, but U1 specified that map only as "a table". Parsing an unanchored Markdown table is brittle, and the plan named neither a heading to find it by nor a column order.

*Fix.* U1 now pins the heading `## Role to file map`, requires the map to be the first table after it, and fixes the three columns in order. U6 cites that shape.

### D4 (P2) — The sibling SDLC checkout had no resolution rule

U6 reads lens identifiers from `infiquetra-sdlc` "when the sibling repository is present" without saying how the test finds it. An implementer would invent a path, and an absolute one would break on every other machine and on a continuous-integration runner.

*Fix.* U6 now names the resolution order — the environment variable `INFIQUETRA_SDLC_ROOT`, else a directory named `infiquetra-sdlc` beside this repository's root — states the pinned fallback with its revision comment, and forbids an absolute path.

### D5 (P2) — The marketplace regenerator's whole-file scope was an unflagged hazard

KTD10 and U7 both said to regenerate the marketplace entry with `scripts/sync_marketplace.py`, which is correct, but `scripts/sync_marketplace.py:158-171` shows the tool takes only `--check` and `--category` and rewrites the whole registry from every plugin manifest. If any unrelated plugin is already ahead of the committed registry, a bare run sweeps that drift into this pull request.

*Fix.* KTD10 gains a paragraph naming the whole-file scope, requiring a `--check` run first, and requiring the written diff to touch only the `agent-launcher` entry; U7's approach points at it.

### Second round — one leak from D1 and D2

Re-reading the edited regions found unit U2's test-scenario line still carrying both defects in miniature: it treated `emits` as a single value and said "no file contains the string `team-execution`" without the README exemption. It now reads "every entry in each file's `emits` list" and "none of the nine contains the string". A grep for both original phrasings returns nothing, so neither defect survives anywhere in the document.

## What was verified, and how

Every load-bearing count, path and line citation in the plan was checked against a current source rather than taken from the plan's own prose.

The retired-prompt accounting adds up: `plugins/team-execution/agents/` holds exactly 25 files — 10 reviewers, 8 testers, 4 scanners, 2 monitors and 1 deploy watcher — matching the plan's destination table row for row, and `wc -l` over those 25 plus the two criteria documents is 2,570, the figure the card states.

The SDLC citations hold at `infiquetra-sdlc` revision `67845cdd`, where local `main` and `origin/main` are the same commit: the fifteen roles and their identifiers at `docs/roles/run-roles.md:180-194`, the handoff comment convention and its four common fields at `docs/process/run-contracts.md:89-107`, the `stop_condition` field at line 357, and the four early-stop conditions at `docs/process/functional-qa.md:133`. The fifteen lens identifiers and their `floor_level` values were read directly out of `config/lens-catalogue.json` rather than transcribed.

The repository-side claims hold too: `is_bump_required_path` at `tools/release_surface_diff_guard.py:193` does exempt `README.md`, `CHANGELOG.md`, `docs/` and `tests/` and nothing else, so `roles/*.md` is genuinely bump-required; the agent lints glob `plugins/*/agents/*.md` only (`tests/test_agent_tier_lint.py:33`, `tools/agent_spec.py:306`), so the new directory is correctly outside them; and `plugins/house-style/references/subagent-presentation-preamble.md` exists as the single canonical copy KTD6 points at.

The plan's Mermaid diagram parses. `scripts/check_mermaid.py` reports 25 fences across 31 files parsed after installing the parser with `npm ci --prefix scripts/mermaid`, so the diagram will not red the gate's Mermaid step.

## Residual risk from limited evidence

Two things this review could not settle, neither of them blocking.

**Prompt quality is not reviewable here.** The plan's test is structural by design, and the card's own acceptance criteria are structural. Whether a role prompt actually briefs a fresh session well is proven by the first roster run under issue 1024, not by this document.

**The SDLC may move during implementation.** The sibling amendment card edits `docs/roles/run-roles.md` and the surrounding documents in the same window. The plan's mitigation — stamping the revision `67845cdd` into the prompts, the README and the test's fallback list — makes a divergence visible, but it does not prevent one.

## Judgment on the one contested scope decision

The plan's KTD1 ships fourteen role prompts where the card enumerates thirteen, adding the Initial Implementation Worker. This review did not treat that as a finding. The card's non-goal forbids only inventing a role the SDLC does not name, the SDLC names this one at `docs/roles/run-roles.md:185`, and the card's acceptance criterion is a floor ("at least 14"), not a cap. The plan states the reasoning and the one-file reversal, which is the right way to carry a decision the operator may want to overturn.
