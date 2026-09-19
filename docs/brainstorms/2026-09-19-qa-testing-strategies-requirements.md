---
date: 2026-09-19
topic: qa-testing-strategies
capability: brainstorm
activity: brainstorm-qa-testing-strategies-20260919T171858Z
maturity: requirements-ready
---

# `/qa` as prescribed testing strategies

## Summary

Replace `/qa`'s nine-way risk router and its language-model-scored health number with a catalogue of ten prescribed testing strategies, each carrying its own tools, its evidence shape, and its pass threshold, selected for a change by a declared repository profile that code reads, widened (never narrowed) by an advisory typed judgment, and run by the Functional Tester after the non-production deployment.

## Problem Frame

`/qa` today is a gate-only verdict command. It restores a work-thread saga, classifies a change into nine risk classes, improvises the checks per class, has a language model assign severities, and turns those severities into a 0-to-100 health score and a ship verdict (`plugins/saga/skills/qa/SKILL.md`, 409 lines). Three things are wrong with that for the lifecycle the simplification review describes.

First, the checks are improvised. The risk taxonomy says which class a change lands in, not what proves the class works; the agent decides at run time. The operator's direction on 2026-09-19 is the opposite: the strategies are prescribed, not improvised.

Second, the evidence base is being removed underneath it. `/qa` writes and reads the evidence-custody ledger (`evidence_ledger.py`) for its pre-registered criteria freeze; issue 1028 deletes that ledger and every sibling ledger, leaving `/qa` to read the run record instead. Whatever the new `/qa` stores has to be a run-record shape, not a ledger shape.

Third, the position in the chain has changed. `/qa` used to be an advisory node that never blocked a router and normally ran post-merge. In the target chain it is the functional-test step: it runs after the Release Worker deploys to the non-production destination, and its failure re-enters the build loop under the post-merge repair allowance (issue 1028; simplification review R6 and R30). A step that re-enters a build loop needs a deterministic verdict, not a number whose inputs are language-model severity counts.

The cost of leaving it as is: the one step in the chain that answers "does the shipped thing actually work" is the one step with no prescribed method, on the day every other step becomes mechanical.

## Key Decisions

**The catalogue generalizes something that already works, rather than inventing one.** The CAMPPS platform already runs this design. `campps-context-library/platform-specs/05-technical-specifications/testing/e2e-scenario-registry/` defines seven driver families (`api-workflow`, `contract-event`, `flutter-integration`, `playwright-hosted-surface`, `manual-runbook`, `deploy-boundary`, `cost-evidence`), a 597-line JSON schema for a scenario row, an evidence-envelope schema, a fixture-manifest schema, and thirty scenario files; `campps-e2e-canary` implements the matching drivers, a filter-based scenario selector, a cost preflight that can refuse a run, and a results model with three statuses (`passed`, `failed`, `blocked`) and built-in secret redaction. The saga catalogue should be that design, generalized to the repositories CAMPPS does not cover, and should call the canary rather than reimplement it where the canary already owns a family.

**A declared mapping is the floor; the typed judgment may only widen it.** Each repository declares, in a profile, which strategies exist for it, which file patterns require which strategy, which environments and secret handles each needs, and what its scenarios are. Code computes the required set from that declaration. The typed judgment (TypeSafe's Jev) may add strategies the declaration under-selected for a mixed or novel change; it may never remove one, and it never computes the verdict. This is house rule 3 of the TypeSafe research (`docs/analysis/2026-09-18-typesafe-jev-integration-research.md`, section 8): an existing pattern rule is a floor, and the judgment may only widen what triggers a mandatory gate.

**`blocked` is a first-class result, distinct from pass and fail.** A missing environment, an absent credential, or an unconfigured target is `blocked`. Today's `/qa` has no such status, and a check that cannot run tends to read as a check that passed. The CAMPPS driver families are explicit that a missing URL, auth configuration, or permission is "blocked or failed proof, not pass", and that deploy-boundary scenarios "must fail loud when environment configuration is missing or when a post-deploy test silently skips". Carry that rule.

**Verdict by counting statuses, not by scoring severity.** The functional test passes when every required strategy returned `passed`. Nothing is weighted, nothing is scored, and no language model assigns a severity that then becomes a number. This deletes the ported health-score formula and `qa_health_score.py` along with it.

**The same catalogue serves the cheap pre-merge boundary.** The build loop's exit criterion includes a branch preview deployment and a scenario smoke where the repository declares a preview (issue 1027; simplification review R21). That smoke is the same catalogue run at a narrower proof boundary, not a second mechanism. One catalogue, two boundaries.

**Proof debt is recorded, not hidden.** When an optional strategy is `blocked`, the run passes with proof debt: the run record carries the strategy, the reason, and a revisit condition. CAMPPS already models this (`e2e-proof-debt-ttl.yaml` in its scenario registry). A required strategy that is `blocked` never passes.

## Actors

- A1. **Functional Tester** — the herdr session that runs the strategies after the non-production deployment, from the roles library (simplification review R12). It invokes `/qa`; it does not choose the strategies by hand.
- A2. **Planner** — names the scenarios in the plan, drawn from the repository profile's declared scenario set, and adds a scenario to the profile when the change introduces behavior the profile does not yet cover.
- A3. **Release Worker** — deploys to the non-production destination and hands the environment identity (base URL, deployed version marker) to the Functional Tester through the run record.
- A4. **The typed judgment (Jev)** — proposes additional strategies and a target variant; advisory, logged, overridable, never a decider.
- A5. **The operator** — overrides any selection with a word, and is the only party who may authorize a paid external service, a credential, or a production target.

## Requirements

**The catalogue**

- R1. Saga owns a strategy catalogue as code plus data: one row per strategy carrying its identifier, the situation triggers that select it, its tool or tools, its required evidence fields, its pass threshold, and whether a repository may mark it optional.
- R2. The catalogue's initial rows are the ten strategies in the table below. The row set is data, so a new strategy is a data change plus a driver, not a rewrite of the skill.
- R3. Every strategy declares a *proof boundary* — the narrowest environment at which its evidence is meaningful (`hermetic`, `branch-preview`, `non-production`). The boundary decides whether the strategy runs in the build loop's smoke, the post-deploy functional test, or both.
- R4. Each strategy driver returns exactly one of `passed`, `failed`, `blocked`, with a reason string, and never returns `passed` when its environment or credentials were absent.
- R5. Every driver redacts secrets from its evidence before the evidence reaches the run record, by pattern, at the driver boundary rather than at the report boundary. `campps-e2e-canary`'s `drivers/models.py` redaction patterns are the starting set.

**Selection**

- R6. Each repository carries a profile declaring: which catalogue strategies apply, the file patterns that require each, the environments and secret handles each needs, the target variants available (for example `macos`, `web`, `ios-simulator`), and the scenario identifiers the strategies can run.
- R7. Code computes the required strategy set from the profile and the change's file list, and that set is the floor.
- R8. The typed judgment receives the change summary, the file list, the profile's strategy descriptions, and the environment identity, and returns one probability per catalogue strategy for "this change needs this strategy's proof". Strategies above the act band are added to the set; nothing is ever removed. The suggestion, the probabilities, and any operator override are logged.
- R9. Selection is preflighted before any strategy runs: missing environments, missing secret handles, and estimated cost and duration are reported as one block, and an over-budget or unauthorized selection refuses rather than partially running. `campps-e2e-canary`'s `selection.py` preflight is the model.
- R10. For a repository whose family is already owned by an external executor — CAMPPS, through `campps-e2e-canary` — the strategy invokes that executor's command-line tool and ingests its evidence envelope. Saga does not reimplement a family that an executor already owns.

**Evidence and verdict**

- R11. Each strategy run appends one evidence envelope to the run record: strategy identifier, target variant, proof boundary, the command or request with secrets redacted, status, reason, evidence pointers (paths to captured output, screenshots, logs), duration, and estimated cost.
- R12. The verdict is computed by code: `pass` when every required strategy returned `passed`; `pass-with-proof-debt` when every required strategy returned `passed` and an optional strategy returned `blocked`, with the debt and a revisit condition recorded; `fail` otherwise.
- R13. A `fail` re-enters the build loop under the post-merge repair allowance and carries, per failing strategy, the evidence that identifies the failing behavior. A `blocked` on a required strategy stops and comes to the operator, because its causes are environment, credential, or permission — the approval boundaries the operator owns.
- R14. `/qa` reports, verdicts, and routes. It does not fix, commit, push, open or merge a pull request, deploy, or file issues. This principle of today's skill survives intact.
- R15. The 0-to-100 health score, its ported rubric, and `qa_health_score.py` are removed. The per-strategy statuses are the report.

**Invocation**

- R16. The Functional Tester invokes one command in its own session, against the run record for the issue: it reads the environment identity the Release Worker wrote, selects, preflights, runs, writes envelopes, computes the verdict, posts one comment, and routes. No sub-selection is left to the session's judgment.
- R17. The build loop invokes the same command at the `branch-preview` boundary, which selects only the strategies whose proof boundary the preview supports.
- R18. Every operator-facing choice the command would otherwise make — an over-budget run, a required credential, an external service — is a stop, not a default.

## The strategy catalogue

Ten rows. Columns: the situation that selects it, the tool that runs it, what it proves, and the evidence that makes the result checkable.

| Strategy | Situation | Tool | Proves | Evidence |
|---|---|---|---|---|
| S1 `api-workflow` | A change to a deployed HTTP surface, a handler, a route, or an authorization rule | A request driver (the canary's `api-workflow` driver for CAMPPS; a repository driver elsewhere) | The deployed service answers the real request across a service boundary | Target without secrets, status or redirect class, required headers or response markers, correlation identifier, deployed version |
| S2 `contract-check` | A change to an OpenAPI document, an event schema, a generated client, or a pinned contract package | `oasdiff`, Schemathesis, the repository's contract fixtures and code generation | Producer and consumer still agree, and no unintended drift shipped | Contract package version, fixture or schema revision, producer and consumer source references, drift result |
| S3 `app-ui` | A change to Flutter widget or screen behavior | `flutter test integration_test` on a declared target variant (`macos`, `web`, `ios-simulator`, `android-emulator`); Patrol where a native permission dialog is in the path | The rendered application behaves for a user on a real target | Repository and test path, Flutter channel and version, target variant and device identifier, per-test result, sanitized failure summary |
| S4 `hosted-surface` | A change touching a non-Flutter hosted page — an identity provider, a payment page, a marketing surface | Playwright, or the installed Chrome DevTools automation | The third-party surface is reachable and configured as the flow expects | Starting URL without secrets, expected host or URL pattern, reachability result, sanitized screenshot where permitted |
| S5 `cli-smoke` | A change to a command-line entry point, a console script, or a plugin script | The repository's own commands under its runner (`uv run …`), exercising `--help`, a dry run, and one real invocation against a fixture | The command starts, parses, and does its narrowest real job | Command line, exit code, first and last output lines, version reported by the tool |
| S6 `deploy-boundary` | Any change that reaches a deployed environment | A reachability probe plus the deployment record from the deploy plugin | The artifact that was built is the artifact serving at the edge | Environment and URL, deployment marker or version, cache or edge headers, expected content marker, observed result and timestamp |
| S7 `data-check` | A change to a schema, a migration, a write path, or an idempotency key | A read-only query against the non-production store | The change's effect on stored data is what the plan said it would be | Query, row count or shape, redacted sample, store identity and region |
| S8 `infrastructure-read-back` | A change to Ansible roles, cluster configuration, or network configuration | `ansible --check --diff`, the cluster's own read commands, the UniFi plugin's read operations | Live state matches declared state after the change | Command, declared value, observed value, host identity, timestamp |
| S9 `installed-surface` | A change to a Claude plugin's skills, commands, agents, or metadata | Plugin registry resolution plus a one-turn activation smoke in both installed plugin trees | The released plugin actually resolves and loads where it is installed | Resolved plugin root per tree, version per tree, command and skill inventory, activation result |
| S10 `manual-runbook` | Automation is unavailable, unsafe, or needs operator-held credentials | The runbook, run by the operator | The behavior was observed by a person, with a named revisit condition | Runbook path, operator, environment, step results, sanitized artifacts, privacy attestation, automation follow-up condition |

Seven of these ten are the CAMPPS driver families, renamed where the CAMPPS name was product-specific (`flutter-integration` becomes `app-ui` with target variants; `playwright-hosted-surface` becomes `hosted-surface` because the tool is a choice within the strategy, not the strategy). Three are new because the CAMPPS registry does not cover the other repositories: `cli-smoke` for the Python plugin and tooling repositories, `infrastructure-read-back` for the home-lab cluster, and `installed-surface` for this repository, where the product is a set of installed plugin files and "does it work" means "does the installed tree resolve the new version". The CAMPPS `cost-evidence` family is not carried as a strategy; its job — refusing a selection whose cost or evidence shape is not sound — becomes the preflight in R9, which is code, not a strategy row.

## What the typed judgment decides

Four judgments, all advisory, all logged with their probabilities, all overridable, none of them computing a verdict.

| Judgment | Question shape | Where it helps | Where it would mislead |
|---|---|---|---|
| J1 Strategy widening | One `noul` per catalogue strategy: "does this change need this strategy's proof?", with the profile's strategy descriptions and the change's file list as state | A mixed change whose file patterns match one strategy but whose behavior crosses two — the exact case a glob table under-selects. The reviewer-selection probe in the TypeSafe research is the same shape and produced a sensible graded middle (0.92 infrastructure, 0.42 privacy) | If it could remove a strategy. It cannot: the declaration is a floor and J1 is additive only |
| J2 Target variant | One `choice` over the profile's declared target variants for `app-ui` | Choosing `macos` versus `web` versus `ios-simulator` when the change touches shared widget code and every target is declared | If it invented a target the profile does not declare, or chose a target whose toolchain is absent. Code filters the choice set to declared, available targets first |
| J3 Scenario relevance | One `score` per candidate scenario: "how likely is this scenario to catch a regression from this change?" | A repository with more declared scenarios than the cost preflight permits — ranking is exactly what the budget refusal needs and the filter-based selector in `campps-e2e-canary` does not provide | If the ranking were allowed to drop a scenario the declaration marks mandatory. Mandatory scenarios are outside the ranking |
| J4 Failure triage | One `choice` over `product-defect`, `environment`, `flake`, per failing strategy | Routing: a product defect re-enters the build loop; an environment cause comes to the operator; a suspected flake earns exactly one re-run | If it decided the verdict. The verdict is already computed; J4 only routes, and a wrong route costs one re-run or one operator question |

Five things the judgment must never do here, each traceable to a documented weakness in the TypeSafe research (section 1.4): compare deployment timestamps or freshness windows (dates are read as text, not ordered quantities); count findings, failures, or coverage (weak arithmetic); decide whether a threshold is met (that is code's job by construction); screen evidence text for adversarial content (not adversarially robust, and driver output is untrusted); and read live external state (it sees only the state passed to it).

## Key Flows

- F1. **Post-deploy functional test.** **Trigger:** the Release Worker records a succeeded non-production deployment in the run record. The Functional Tester's session runs the `/qa` command against the issue. Code reads the repository profile and the change's file list, computes the required strategy set, asks J1 for widening and J2 for a target variant, preflights environments, secret handles, cost, and duration, and reports the selection. Each selected strategy's driver runs and appends an evidence envelope. Code computes the verdict from the statuses. One comment publishes the selection, the statuses, and the evidence pointers. A `pass` advances the run record to close; a `fail` routes to the build loop with J4's triage attached; a required `blocked` stops for the operator.

- F2. **Build-loop scenario smoke.** **Trigger:** the build loop has a green mechanical baseline and the repository declares a branch preview. The same command runs at boundary `branch-preview`, which filters the catalogue to the strategies whose proof boundary the preview supports — typically `cli-smoke`, `contract-check`, and `app-ui` at a hermetic or preview target, rarely `api-workflow` and never `deploy-boundary` against the non-production edge. A failure is a loop iteration, not a gate.

- F3. **Proof debt.** **Trigger:** an optional strategy returns `blocked` — a target toolchain that is not installed, an environment not yet provisioned. The verdict is `pass-with-proof-debt`; the run record carries the strategy, the reason, and a revisit condition; the closing comment names it. No silent skip exists anywhere in the flow.

## Acceptance Examples

- AE1. **Covers R4, R12.** A repository declares `api-workflow` as required and the non-production base URL is unset. The driver returns `blocked`, the verdict is `fail`, and the run stops for the operator rather than reporting a pass with zero checks.
- AE2. **Covers R7, R8.** A change touches one Dart widget file and one OpenAPI document. The profile's patterns select `app-ui` and `contract-check`. J1 returns 0.81 for `hosted-surface` because the changed widget is the login entry point. `hosted-surface` is added, and the log records the probability and the addition.
- AE3. **Covers R8.** The same change, with J1 returning 0.11 for `contract-check`. `contract-check` still runs: the declaration selected it, and the judgment cannot remove it.
- AE4. **Covers R10.** A change lands in a CAMPPS service repository. The `api-workflow` strategy invokes `campps-e2e-canary`'s command-line tool with the scenario identifiers from the plan and ingests its evidence envelope, rather than issuing its own requests.
- AE5. **Covers R17.** The build loop runs the catalogue at `branch-preview`. `deploy-boundary` is not selected, because its proof boundary is `non-production`, and its absence is recorded as out-of-boundary rather than as proof debt.
- AE6. **Covers R9, R18.** A selection's cost preflight exceeds the declared budget. The command refuses the whole selection and asks the operator, rather than running the affordable subset and reporting a partial pass.

## Scope Boundaries

In scope for the implementing capability:

- The catalogue, the repository profile shape, the selection procedure, the evidence envelope, the verdict rule, and the invocation surface.
- Drivers for the strategies whose tools are already installed and free: `cli-smoke`, `contract-check`, `deploy-boundary`, `installed-surface`, `app-ui` at the `macos` and `web` targets, `manual-runbook`.
- Delegation to `campps-e2e-canary` for the families it owns.

Deferred for later:

- Drivers for `data-check`, `infrastructure-read-back`, and `app-ui` at simulator or emulator targets. Each of these needs an environment decision (a non-production store identity, a cluster read credential, a simulator toolchain) that the first release does not need to make.
- Visual regression and golden-image comparison. CAMPPS has a strategy for it; generalizing it means solving cross-platform font rendering, which is a project of its own.
- Any performance or load strategy.

Outside this thing's identity:

- Fixing anything. `/qa` reports, verdicts, and routes.
- Scoring. No health number returns, in any form.
- Any paid external service — a device farm, a hosted browser grid, a commercial monitor. Local toolchains and open-source tools only (decision Q5).

## Dependencies / Assumptions

- D1. Issue 1023's run record must exist before the evidence envelopes have a home; issue 1028 gives `/qa` its environment identity and its place in the chain. The implementing card is blocked on both.
- D2. Issue 1032's TypeSafe client, judgment logging, and evaluation harness must exist before J1 through J4 can be built. Without it the catalogue still works: the declared mapping alone is a complete selection procedure, and the judgment is a later widening. This is the degradation path the TypeSafe house rules require (fail open to the pre-judgment path).
- D3. **Verified:** Auralis today is a macOS-only Flutter application. The `auralis` repository carries a `macos/` directory and the platform packages `auralis_audio_macos` and `auralis_notifications_macos`, and carries no `ios/` or `android/` directory. The operator's example of an iPhone simulator is therefore a target Auralis does not have yet. The catalogue should carry `ios-simulator` as a declared-but-unavailable target variant rather than as a first driver (decision Q3).
- D4. **Verified:** the CAMPPS design this generalizes exists and is populated — seven driver families, a scenario schema with eighteen required fields, thirty scenario files, and a matching executor with cost preflight and redaction. Assumed but not verified: that it is currently green in use. The implementing card should read its last run before adopting its thresholds.
- D5. Assumed: the strategies are the same for every repository and only the profile differs. If a repository family needs a strategy the catalogue does not carry, the catalogue grows a row; it does not fork.
- D6. Assumed: `blocked` is preferable to a skip in every case. This is a deliberate strictness increase over today's `/qa`, which no-ops gracefully for repositories without a browser surface. Under the new rule a graceful no-op becomes an explicit out-of-boundary record, which is the same behavior with an audit trail.

## Questions for the operator

Every question below was genuinely open after the card, the simplification review, the objective plan, and the TypeSafe research were read; none of those documents answers it. Each was written with a recommendation, and the rest of this document was written under those recommendations.

**Answered on 2026-09-19.** The operator confirmed every recommendation below as his own answer: "regarding /qa I agreed with all your recommendations, you can record those as my answers." Each item's recommendation is therefore recorded below as a decision, in its original wording. Nothing in this section remains open.

**Q1. What is the verdict vocabulary?**
Options: (a) keep today's `ship` / `ship-with-deferred` / `no-ship`; (b) `pass` / `pass-with-proof-debt` / `fail`.
Decision (confirmed by the operator, 2026-09-19): (b). `/qa` now runs after the release deployment, so it no longer decides whether to ship; it decides whether the shipped thing works. Keeping ship-shaped words would describe a decision the step no longer makes.

**Q2. Where does the catalogue live, and who owns the scenarios?**
Options: (a) saga owns the strategy families and each repository owns its scenarios in a profile, with CAMPPS repositories delegating to `campps-e2e-canary`; (b) saga owns families and scenarios centrally; (c) `campps-e2e-canary` generalizes into the executor for every repository and saga only calls it.
Decision (confirmed by the operator, 2026-09-19): (a). Option (b) duplicates a populated, working registry and would drift from it within a release. Option (c) moves the work into a CAMPPS service repository and makes every non-CAMPPS repository's functional test depend on a CAMPPS deployment, which is a coupling with no benefit.

**Q3. Is a device simulator a strategy or a target?**
Options: (a) `ios-simulator` is a target variant of the `app-ui` strategy, alongside `macos` and `web`; (b) it is a strategy of its own with its own evidence shape.
Decision (confirmed by the operator, 2026-09-19): (a). The evidence shape is the same (repository, test path, target, result); only the launch mechanics differ. Carried with it: Auralis has no iOS surface today (D3), so the first release should declare the target and ship no driver for it. Worth your correction if an iOS surface is planned sooner than this reading suggests.

**Q4. Does the build loop's scenario smoke use this same catalogue?**
Options: (a) yes, the same command at a `branch-preview` boundary; (b) no, the build loop keeps its own lighter notion of smoke and the catalogue is post-deploy only.
Decision (confirmed by the operator, 2026-09-19): (a). Two mechanisms for "run the scenario" would drift, and the boundary field already expresses the difference. This does mean issue 1027's build loop and this card share a component, which is a coordination cost worth naming.

**Q5. May any strategy use a paid external service?**
Options: (a) local toolchains and open-source tools only; (b) a named paid service (a device farm, a hosted browser grid) is allowed with a budget.
Decision (confirmed by the operator, 2026-09-19): (a), and this is the one question where the recommendation is also a refusal to proceed without you: a paid service is an external commitment, and the specification will not name one unless you do.

**Q6. What happens when a required strategy is `blocked`?**
Options: (a) the run fails and stops for you, because the causes are environment, credential, and permission; (b) the run fails and re-enters the build loop like any other failure; (c) the run records proof debt and passes.
Decision (confirmed by the operator, 2026-09-19): (a). A build loop cannot fix a missing credential, and (c) is the silent-skip failure the CAMPPS families explicitly forbid.

**Q7. Does the health score survive in any form?**
Options: (a) removed entirely, per-strategy statuses are the whole report; (b) kept as a reported-but-not-gating signal, as today.
Decision (confirmed by the operator, 2026-09-19): (a). Its inputs are language-model severity counts, the new model has no severity assignment to count, and a number that no longer has inputs is worse than no number.

**Q8. Who writes a new scenario, and when?**
Options: (a) the Planner writes it into the repository profile during planning, so the functional test's scenarios are settled before implementation; (b) the Functional Tester writes it at test time when the declared set does not cover the change.
Decision (confirmed by the operator, 2026-09-19): (a). It matches the lens-declaration pattern the review adopts for code review — decide what proof is needed before the code exists, not after — and it keeps the Functional Tester mechanical.

**Q9. Which judgments ship in the first release?**
Options: (a) J1 (strategy widening) only, with J2 through J4 following after the harness has recorded agreement; (b) all four at once; (c) none in the first release, the declaration alone.
Decision (confirmed by the operator, 2026-09-19): (a). J1 is the one whose absence actually costs something (an under-selected mixed change), and the TypeSafe house rules require suggest-mode and a recorded harness run per decision before any of them becomes automatic. J4 is the cheapest second candidate.

**Q10. What is the cost and duration budget for one functional test?**
Options: (a) inherit the CAMPPS canary's declared per-scenario cost estimates and its aggregate refusal; (b) set a per-run wall-clock and dollar ceiling in the repository profile; (c) no budget in the first release.
Decision (confirmed by the operator, 2026-09-19): (b) with (a)'s mechanism — the preflight and refusal come from the canary's design, the numbers come from each repository's profile. The canary's numbers are CAMPPS-specific and would not mean anything for a plugin repository.

## Success Criteria

- The specification that follows this document can be handed to `/plan` without the planner inventing a strategy, an evidence field, a status value, or a threshold.
- A reader who has not seen the CAMPPS registry can tell, from the catalogue table alone, which strategy a given change selects.
- Every strategy in the catalogue has a named tool that exists on this machine or in a repository, or is explicitly deferred with its blocking dependency named.
- The judgment's four jobs each name what they would get wrong, not only what they help with.

## Sources / Research

- `plugins/saga/skills/qa/SKILL.md` and `plugins/saga/commands/qa.md` as installed at saga 0.159.0 — today's nine-way risk router, the ported health score, the evidence-ledger criteria freeze, and the gate-only principle that survives.
- `docs/analysis/2026-09-19-saga-simplification-review.md` — section 0's decisions block (the operator's direction for `/qa`), R6 (the functional-test step), R21 (the build loop's preview and smoke), R30 (the redesign), R12 (the roles library and the Functional Tester).
- `docs/analysis/2026-09-19-improve-claude-plugins-objective-plan.md` section 7, card A15 — the research question, the success criteria, and the four key questions this document answers.
- `docs/analysis/2026-09-18-typesafe-jev-integration-research.md` — section 1.2 (the three primitives), section 1.4 (the documented weaknesses each judgment is checked against), section 2 (the reviewer-selection probe that J1 imitates), section 8 (the house rules, in particular rules 1, 3, 8, and 10).
- `campps-context-library/platform-specs/05-technical-specifications/testing/e2e-scenario-registry/driver-families.md`, `scenario.schema.json`, `evidence-envelope.schema.json`, and the thirty files under `scenarios/` — the seven families, their required evidence, and the blocked-not-pass rule.
- `campps-e2e-canary/src/e2e_canary/` — `drivers/dispatcher.py`, `drivers/models.py` (three statuses and the redaction patterns), `selection.py` (filter-based selection with cost preflight and budget refusal), `registry/validation.py`.
- Issues 1023 (the run record), 1027 (the build loop and its exit criterion), 1028 (integrate, release, functional test, and close — the card that gives `/qa` its position), and 1032 (the TypeSafe client and harness).
- Repository shapes read directly: `auralis` (Flutter, macOS only), `campps-web-app` (Flutter with an `integration_test/` directory), `campps-contracts` (OpenAPI with code generation), `infiquetra-claude-plugins` (Python plugins with a twenty-four-step gate).
