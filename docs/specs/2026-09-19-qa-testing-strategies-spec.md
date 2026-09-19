---
title: Replace the /qa risk router with a prescribed strategy catalogue
type: spec
status: draft
date: 2026-09-19
origin: docs/brainstorms/2026-09-19-qa-testing-strategies-requirements.md
---

# Replace the /qa risk router with a prescribed strategy catalogue

## Context

`/qa` is about to become the lifecycle's functional-test step — the one that runs after the Release Worker deploys to the non-production destination and decides whether the shipped thing actually works (issue 1028; saga simplification review R6 and R30). It is also the only step in the new chain with no prescribed method: it classifies a change into nine risk classes and then improvises the checks for each.

The operator's direction on 2026-09-19 is that the strategies are prescribed, chosen by situation, end-to-end in shape but with more tools than a browser, with a typed judgment helping choose. He confirmed all ten recommendations of the brainstorm as his answers the same day.

Who is affected: the Functional Tester session that runs this step, the worker whose build loop a failure re-enters, and the operator, who today cannot tell from a `/qa` report which checks ran and which were quietly skipped.

## Current State

Verified by reading the shipped surfaces in this repository at commit `2044c363`.

`/qa` today is 883 lines across five files: `plugins/saga/skills/qa/SKILL.md` (409), `plugins/saga/skills/qa/references/qa-report.md` (202), `plugins/saga/skills/qa/references/risk-taxonomy.md` (123), `plugins/saga/scripts/qa_health_score.py` (123), and `plugins/saga/commands/qa.md` (26). One test file covers it: `tests/test_qa_health_score.py` (107 lines).

The selection mechanism is a nine-class risk router — behavior, security, infra, API, deployment, data, config, docs, trivial (`plugins/saga/skills/qa/references/risk-taxonomy.md:10-22`) — driven by a ten-row file-pattern map (`risk-taxonomy.md:55-66`). What the router selects is a *class*, and the class carries an "acceptance / evidence checklist" written as prose instructions to the agent; the actual checks are chosen at run time. There is no declared tool per situation and no declared evidence shape.

The verdict is a language model's severity assignment turned into a number. Each finding gets critical, high, medium, or low; `plugins/saga/scripts/qa_health_score.py` applies fixed deductions over class weights to produce a 0-to-100 health score; a severity-banded ship verdict (`ship`, `ship-with-deferred`, `no-ship`) is derived from a tier threshold (`plugins/saga/skills/qa/SKILL.md:59-68`). The skill states the honest caveat itself: "the score's *inputs* are LLM-assigned severity counts, so the number is **one signal**, not the gate" (`SKILL.md:64-67`).

Two structural facts make the current design unusable in the new chain. First, `/qa` writes and reads the evidence-custody ledger for its criteria freeze (`plugins/saga/skills/qa/SKILL.md:172-181` and `310-313`, calling `plugins/saga/scripts/evidence_ledger.py`), and issue 1028 deletes that ledger along with `run_ledger.py`, `dispatch_settlement.py`, and `effort_ledger.py`. Second, `/qa` is described as an advisory router node that "never blocks the router" and "normally runs post-merge" (`SKILL.md:25-26`), whereas the new functional-test step is authoritative and its failure re-enters the build loop.

There is no missing status. A check that cannot run — no environment, no credential, no toolchain — has nowhere to land except a graceful no-op, which the skill explicitly prescribes for repositories without a browser surface (`SKILL.md:48-50`).

**The design this replaces it with is not new; it is running.** The CAMPPS platform already prescribes testing this way. `campps-context-library/platform-specs/05-technical-specifications/testing/e2e-scenario-registry/` holds seven driver families with their required evidence (`driver-families.md`, 129 lines), a scenario schema with eighteen required fields (`scenario.schema.json`, 597 lines), an evidence-envelope schema with twenty fields of which sixteen are required (`evidence-envelope.schema.json`), and thirty scenario files. `campps-e2e-canary/src/e2e_canary/` implements the drivers (`drivers/dispatcher.py`), a three-status result model with secret redaction at the driver boundary (`drivers/models.py`), and filter-based selection with a cost preflight that can refuse a run (`selection.py`). This specification generalizes that design and calls that executor rather than reimplementing it.

## Proposed Change

`/qa` becomes a prescribed catalogue of ten testing strategies. Code selects from a per-repository declaration, an advisory typed judgment may widen the selection but never narrow it, each strategy's driver returns one of three statuses with a declared evidence envelope, and code computes the verdict by counting statuses. No language model assigns a severity and no score is produced.

### The catalogue: which situation, which tool, which repository family

Ten strategies. The "repository family" column answers the card's first key question — which situations recur across the repositories and which tool serves each — using the repositories verified on this machine: `auralis` (Flutter, macOS only), `campps-web-app` (Flutter with an `integration_test/` directory), the CAMPPS service repositories, `campps-contracts` (OpenAPI with code generation), this repository and its sibling Python tooling, and the home-lab infrastructure repositories.

| Strategy | Situation that selects it | Tool | Repository family where it recurs |
|---|---|---|---|
| `api-workflow` | A change to a deployed HTTP surface, handler, route, or authorization rule | A request driver; `campps-e2e-canary`'s own driver for CAMPPS repositories | CAMPPS services (`campps-identity-access`, `campps-registration`, `campps-payments`, and siblings) |
| `contract-check` | A change to an OpenAPI document, event schema, generated client, or pinned contract package | oasdiff, Schemathesis, the repository's contract fixtures and code generation | `campps-contracts`, and every service that consumes it |
| `app-ui` | A change to Flutter widget or screen behavior | `flutter test integration_test` at a declared target variant; Patrol where a native permission dialog is in the path | `auralis` (target `macos`), `campps-web-app` (target `web`) |
| `hosted-surface` | A change touching a non-Flutter hosted page — identity provider, payment, marketing | Playwright, or the installed Chrome DevTools automation | `campps-identity-access`, `campps-payments`, `campps-marketing` |
| `cli-smoke` | A change to a command-line entry point, console script, or plugin script | The repository's own commands under its runner (`uv run …`): help, dry run, one real invocation against a fixture | This repository, `fleet-core`, the Python tooling repositories |
| `deploy-boundary` | Any change that reaches a deployed environment | A reachability probe plus the deployment record from the deploy plugin | Every repository with a non-production destination |
| `data-check` | A change to a schema, migration, write path, or idempotency key | A read-only query against the non-production store | CAMPPS services with persisted state |
| `infrastructure-read-back` | A change to Ansible roles, cluster configuration, or network configuration | `ansible --check --diff`, the cluster's read commands, the UniFi plugin's read operations | `asgard` and the home-lab infrastructure repositories |
| `installed-surface` | A change to a Claude plugin's skills, commands, agents, or metadata | Plugin registry resolution plus a one-turn activation smoke in both installed plugin trees | This repository, `vecu-claude-plugins`, `mimir-pilot-claude-plugins` |
| `manual-runbook` | Automation is unavailable, unsafe, or needs operator-held credentials | The runbook, run by a person | Any repository, as the escape hatch |

Seven of the ten are the CAMPPS driver families, renamed where the CAMPPS name named a tool rather than a situation. Three are new because the CAMPPS registry covers only CAMPPS: `cli-smoke`, `infrastructure-read-back`, and `installed-surface`. The CAMPPS `cost-evidence` family is not a strategy here; its job becomes the preflight below, which is code.

Each catalogue row is data carrying: the identifier, the file patterns that require it, the tool and its invocation shape, the required evidence fields, the proof boundary (`hermetic`, `branch-preview`, or `non-production`), and whether a repository may mark it optional. A new strategy is a data row plus a driver, never a rewrite of the skill.

### The repository profile

Each repository carries one profile declaring which strategies apply to it, the file patterns that require each, the environments and secret handles each needs, the target variants available, its scenario identifiers, and its cost and duration ceiling. The field set is taken from the CAMPPS scenario schema's proven blocks — `automation` (repository, runner, entrypoint, required environment), `cost_estimate` (runner class, estimated duration, estimated direct cost, frequency, default enabled), `test_data_profile`, and `evidence_policy` (classification, artifact policy, screenshots allowed, retention, privacy prohibitions) — because those blocks already survived thirty real scenarios.

### Evidence in the run record, and the threshold that turns it into a pass

This answers the card's second key question.

Each strategy run appends exactly one evidence envelope to the run record, in the shape the CAMPPS envelope schema already proves, with `strategy_id` in place of `driver_family`: envelope identifier, scenario identifier and version, profile revision, environment, strategy identifier, proof boundary, proof mode (`automated`, `manual`, `hybrid`), result, status reason, start and completion timestamps, duration in seconds, estimated and observed cost, privacy attestation, and artifact pointers. Secrets are redacted by pattern inside the driver, before the envelope exists, not at report time.

The result is one of exactly three values. `passed` — the strategy ran and its threshold was met. `failed` — the strategy ran and its threshold was not met. `blocked` — the strategy could not run: missing environment, missing credential, missing toolchain, missing permission. There is no fourth value and no silent skip; a strategy the boundary excludes is recorded as out-of-boundary in the selection block, not as a result.

The threshold per strategy is declared in the catalogue row, is mechanical, and is evaluated by code. Worked examples: `api-workflow` passes when the observed status or redirect class matches the declared expectation and every declared response marker is present; `contract-check` passes when the drift result is empty or contains only changes the profile marks permitted; `app-ui` passes when every named integration test reports success on the declared target; `cli-smoke` passes when each declared invocation exits zero and the reported version matches the deployed version marker; `deploy-boundary` passes when the deployment marker served at the edge equals the revision the Release Worker recorded; `installed-surface` passes when both installed plugin trees resolve the released version and the expected commands and skills are present in each.

The run verdict is then arithmetic over the envelopes, performed by code:

- `pass` — every required strategy returned `passed`.
- `pass-with-proof-debt` — every required strategy returned `passed`, and at least one optional strategy returned `blocked`; the debt, its reason, and a revisit condition are written to the run record and named in the closing comment.
- `fail` — anything else.

A `fail` re-enters the build loop under the post-merge repair allowance, carrying per failing strategy the evidence that identifies the failing behavior. A required strategy that returned `blocked` does not re-enter the build loop: its causes are environment, credential, and permission, which are the operator's approval boundaries, so the run stops and asks him.

### Where the typed judgment helps, and where it would mislead

This answers the card's third key question. Four judgments, all advisory, all logged with their probabilities and any override, none of them computing a verdict. They use TypeSafe's Jev through the client that issue 1032 delivers.

| Judgment | Question shape | Value beyond the lookup table | Where it would mislead |
|---|---|---|---|
| J1 strategy widening | One yes/no probability per catalogue row: "does this change need this strategy's proof?", with the profile's strategy descriptions, the change's file list, and a change summary as state | The lookup table matches file patterns; it cannot see that a changed widget is a login entry point or that a handler change implies a write. J1 catches the mixed change the table under-selects. The reviewer-selection probe of 2026-09-18 is the same shape and produced a usefully graded middle | If it could remove a strategy. It cannot: the declaration is a floor and J1 is additive only, per house rule 3 of the TypeSafe research |
| J2 target variant | One choice over the profile's declared, installed target variants for `app-ui` | Picks `macos` versus `web` when shared widget code changes and more than one target is declared | If it invented an undeclared target or one whose toolchain is absent; code filters the choice set before asking |
| J3 scenario relevance | One score per candidate scenario: "how likely is this scenario to catch a regression from this change?" | Ranking, which the CAMPPS filter-based selector does not provide, is exactly what a budget refusal needs in order to choose a subset honestly | If ranking could drop a scenario the profile marks mandatory; mandatory scenarios are outside the ranking |
| J4 failure triage | One choice over `product-defect`, `environment`, `flake`, per failing strategy | Routing: a defect re-enters the build loop, an environment cause goes to the operator, a suspected flake earns exactly one re-run | If it decided the verdict. The verdict is already computed; a wrong triage costs one re-run or one operator question |

Five things the judgment must never do here, each traceable to a documented weakness of the model: compare deployment timestamps or freshness windows (dates are read as text, not ordered quantities); count findings, failures, or coverage (weak arithmetic); decide whether a threshold is met (code's job by construction); screen evidence text for adversarial content (not adversarially robust, and driver output is untrusted); and read live external state (it sees only the state passed to it).

J1 ships first. J2, J3, and J4 ship only after the evaluation harness has recorded agreement for J1 at the chosen band, per the suggest-first house rule. With no judgment at all, the declared mapping remains a complete selection procedure — that is the documented degradation path.

### How the Functional Tester invokes a strategy

This answers the card's fourth key question. The Functional Tester is a herdr pane created by the roster helper from the roles library. Its prompt names one command and one issue, and it makes no selection decisions of its own:

1. The Release Worker records the succeeded non-production deployment in the run record, with the environment identity: base URL, deployed version marker, region where it applies.
2. The Functional Tester's session runs the `/qa` command against that issue. Code reads the run record and the repository profile, computes the required strategy set from the profile's file patterns and the change's file list, asks J1 for widening and J2 for a target variant, and prints the selection with the reason for each entry.
3. Code preflights: missing environments, missing secret handles, estimated cost, estimated duration. Over the profile's ceiling, or missing an authorization the operator owns, the whole selection refuses — it never runs the affordable subset and reports a partial pass.
4. Each selected strategy's driver runs and appends its envelope. A driver failure to start is `blocked`, not an exception that ends the run.
5. Code computes the verdict, writes it to the run record, and publishes one comment carrying the selection, the per-strategy statuses, and the artifact pointers.
6. Code routes: `pass` advances the run record to close; `fail` returns to the build loop with J4's triage attached; a required `blocked` stops for the operator.

The build loop invokes the identical command at the `branch-preview` boundary (issue 1027), which filters the catalogue to the strategies whose proof boundary a preview supports. One mechanism, two boundaries.

## Acceptance Criteria

1. The catalogue file lists exactly the ten strategy identifiers named above, and each row carries a non-empty tool invocation, file-pattern list, required-evidence field list, proof boundary, and threshold rule.
2. Selecting strategies for a change whose file list matches two profile patterns returns those two strategies with no judgment call made, and the printed selection names the matching pattern for each.
3. With the judgment returning a probability above the act band for a third strategy, the selection returns three strategies; with the judgment returning a probability below the band for a declared strategy, that strategy is still selected. Both outcomes are asserted by a test with a stubbed judgment client.
4. With the judgment client absent or erroring, selection returns the declared set and the run continues; no run fails because the judgment was unavailable.
5. A driver whose required environment variable is unset returns `blocked` with a reason naming the variable, and never `passed`.
6. The verdict function returns `pass` for all-required-passed, `pass-with-proof-debt` for all-required-passed with an optional `blocked`, and `fail` for every other combination, asserted over the full status matrix.
7. A required strategy returning `blocked` produces the operator stop, not a build-loop re-entry, asserted by a test on the routing decision.
8. Every evidence envelope written to the run record validates against the envelope schema, and a driver given a bearer token in its output writes an envelope containing no token, asserted against the redaction patterns.
9. Running at boundary `branch-preview` omits every strategy whose proof boundary is `non-production`, records them as out-of-boundary, and never records them as proof debt.
10. A selection whose estimated cost exceeds the profile ceiling refuses the whole selection and runs zero drivers.
11. `test ! -f plugins/saga/scripts/qa_health_score.py` and `test ! -f tests/test_qa_health_score.py`; no file under `plugins/saga/` contains the string `health score`.
12. No file under `plugins/saga/skills/qa/` references `evidence_ledger.py`.
13. For a CAMPPS repository profile, the `api-workflow` strategy invokes the `campps-e2e-canary` entrypoint declared in the profile and ingests its envelope rather than issuing its own requests, asserted with a recorded invocation.
14. `uv run pytest tests/test_qa_strategies.py` passes, and the repository gate (`scripts/gate.sh`) exits zero.

## Scope Boundaries

**Out of scope:**

- Fixing anything. `/qa` reports, verdicts, and routes; every repair belongs to the build loop.
- Any score, rating, or severity assignment, in any form.
- Any paid external service — a device farm, a hosted browser grid, a commercial monitor. Local toolchains and open-source tools only, by the operator's decision of 2026-09-19.
- Drivers for `data-check`, `infrastructure-read-back`, and `app-ui` at simulator or emulator targets. Each needs an environment decision the first release does not need to make; each is declared in the catalogue and ships without a driver, so selecting one yields `blocked` with a named reason.
- Visual regression and golden-image comparison.
- Any performance or load strategy.
- Reimplementing what `campps-e2e-canary` owns.
- Production. The destination is non-production.

**The MVP cut, surfaced but not taken as the whole:** the catalogue, the profile, selection with no judgment, the envelope, the verdict, and four drivers (`cli-smoke`, `contract-check`, `deploy-boundary`, `installed-surface`) would deliver a working prescribed functional test for this repository alone. It is named here because it is a legitimate fallback if the dependencies slip; the specification's scope is the full first release.

## Failure Modes & Rollback

| Failure mode | What happens if shipped wrong | Rollback |
|---|---|---|
| A driver cannot reach its environment and returns `passed` | The chain reports working software on zero evidence — the exact failure the redesign exists to remove | Acceptance criterion 5 and the three-value result type; a driver returning `passed` with an unresolved required environment is a test failure, not a run-time judgment |
| The judgment narrows the selection | A required proof silently disappears on the change that most needed it | The floor is computed before the judgment is called and the judgment's output is unioned, never intersected; criterion 3 asserts it in both directions |
| The judgment service is down or slow | The functional test stalls or fails for a reason unrelated to the software | Criterion 4: the judgment is called with a timeout and its absence degrades to the declared set |
| A driver leaks a token or personal data into the run record | A secret lands in a durable, committed record | Redaction inside the driver before the envelope exists, with the CAMPPS pattern set as the floor; criterion 8 |
| The profile is missing or malformed for a repository | Either every strategy is selected or none is | A missing profile is a `blocked` run with a message naming the expected path, never an empty selection that reports `pass` |
| The catalogue and the build loop's smoke drift apart | Two definitions of "the scenario ran" | One component, two boundaries; the boundary is a field, not a fork. This is the shared-component coupling with issue 1027 |
| Cost runs away on a repository with many scenarios | A functional test that costs more than the change | The preflight refuses the whole selection at the profile ceiling; criterion 10 |
| Removal of the ledger call lands before issue 1028 | `/qa` calls a script that no longer exists | This card merges after issue 1028; the dependency is stated in Related |
| The whole design proves wrong in use | The functional test is worse than the improvised one it replaced | The change is additive in files: the old skill is replaced in one commit and restorable from history; no data migration exists to unwind, because the run record is written fresh per issue |

## Files Reference

| File | What changes |
|---|---|
| `plugins/saga/skills/qa/SKILL.md:1-409` | Rewritten: the nine-way router, the severity assignment, the score, the ledger freeze, and the advisory-router framing are replaced by the catalogue, the profile, the selection procedure, the envelope, and the three-value verdict |
| `plugins/saga/commands/qa.md:1-26` | Rewritten to describe the functional-test step rather than a gate-only ship verdict |
| `plugins/saga/skills/qa/references/risk-taxonomy.md:1-123` | Replaced by the catalogue reference: ten strategies with situation, tool, boundary, evidence, and threshold |
| `plugins/saga/skills/qa/references/qa-report.md:1-202` | Replaced by the envelope and verdict reference |
| `plugins/saga/scripts/qa_health_score.py:1-123` | Deleted |
| `tests/test_qa_health_score.py:1-107` | Deleted |
| `plugins/saga/scripts/qa_strategies.py` | New: the catalogue loader, the selection procedure, the preflight, the driver dispatch, and the verdict function |
| `plugins/saga/references/qa-catalogue.yaml` | New: the ten catalogue rows as data |
| `plugins/saga/references/qa-profile.schema.json` | New: the repository profile shape |
| `tests/test_qa_strategies.py` | New: the fourteen acceptance criteria as tests |
| `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `plugins/saga/CHANGELOG.md` | The release surfaces, bumped in the same pull request per this repository's rule |

Cross-repository references, read but not changed: `campps-context-library/platform-specs/05-technical-specifications/testing/e2e-scenario-registry/driver-families.md`, `scenario.schema.json`, `evidence-envelope.schema.json`; `campps-e2e-canary/src/e2e_canary/drivers/models.py` and `selection.py`.

## Effort

Rough, per component, in implementer-sessions rather than hours:

- Catalogue data and profile schema: 1 session. Mostly transcription from the CAMPPS schema blocks.
- Selection, preflight, and verdict in `qa_strategies.py`: 2 sessions. This is where the floor-then-widen rule and the three-value type live, so it carries the tests that matter.
- The four first-release drivers (`cli-smoke`, `contract-check`, `deploy-boundary`, `installed-surface`): 2 sessions. `installed-surface` is the one with a known trap — two installed plugin trees that drift after a release, which this repository's history has hit repeatedly.
- The `app-ui` driver at the `macos` and `web` targets: 1 session, plus unknown Flutter toolchain time. Unknown — measure by running one existing `campps-web-app` integration test from a cold worktree and recording the wall clock.
- The `campps-e2e-canary` delegation for `api-workflow` and `hosted-surface`: 1 session, contingent on the canary's command-line interface being stable; measure by running its `run-scenario` entrypoint once before committing to the shape.
- Rewriting the skill and its two references, and deleting the score: 1 session.
- The J1 judgment, behind issue 1032's client: 1 session, and not startable before it lands.

Total: 9 sessions with one genuine unknown (the Flutter toolchain) and one external dependency (the canary's interface).

## Related

- `docs/brainstorms/2026-09-19-qa-testing-strategies-requirements.md` — the requirements document this sharpens, carrying the operator's ten answers.
- Issue 1031 — the exploration card that produced both documents.
- Issue 1018 — the saga simplification parent.
- Issue 1023 — the run record. Depends on it: the evidence envelopes have no home until it exists.
- Issue 1028 — integrate, release, functional test, and close. Depends on it: the environment identity and this step's position in the chain come from it, and it deletes the evidence ledger this rewrite stops calling.
- Issue 1032 — the TypeSafe client, the `jev` tool, and the evaluation harness. Depends on it for the judgment parts only; the declared mapping works without it.
- Issue 1027 — the build loop. Not a dependency, but the shared strategy-runner component: whichever card ships second inherits the runner rather than writing a second one.
- Issue 1039 — the implementing capability card filed from this specification, "/qa as a prescribed strategy catalogue with declared evidence and a computed verdict" (https://github.com/infiquetra/infiquetra-claude-plugins/issues/1039), a sub-issue of 1018 on the Operations board at Stage Planning with Objective improve-claude-plugins.

## Open Questions

Three questions arose while sharpening the requirements into this specification; none is answered by the operator's ten decisions of 2026-09-19. Each is carried below with a recommendation, and the specification above is written under that recommendation, marked here as an assumption.

- **Which store does `data-check` read, and with which credential?** Options: a read-only role in the non-production account, scoped per service; or the service's own read endpoint rather than the store. Recommendation and working assumption: defer the driver to a later card, as the scope boundary does, because either answer is a credential decision the operator owns. Nothing above depends on the answer.
- **Does `installed-surface` verify both installed plugin trees, or only the one the session runs from?** Options: both, or one. Recommendation and working assumption: both. This repository's operating history records six consecutive releases where one tree updated and the other did not, and a check that reads only the live tree would have passed every one of them. The cost is one extra path read.
- **When a scenario the plan named does not exist in the repository profile, is that a `blocked` run or an automatic profile addition?** Options: block and ask the planner, or add the scenario row from the plan. Recommendation and working assumption: block. The operator's decision Q8 puts scenario authorship with the Planner at plan time, and a functional test that writes its own scenarios would be grading its own homework.
