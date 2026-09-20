# saga

Saga is the Infiquetra lifecycle spine for turning vague work into reviewed plans, PRs, merges, handoffs, QA evidence, and durable learning.

It is an operating model, not just a command bundle. Saga owns lifecycle choice, local saga state, routing, and handoff envelopes. Adjacent plugins own their own mutation surfaces: `mission-control` owns SDLC issues and board state, and `deploy` owns deployment mutation. Review and testing roles are herdr sessions launched from the roles library in `plugins/agent-launcher/roles/`.

## Start Here

Use the situation, not the command list, as the entry point.

| Situation | Command | Next artifact |
|-----------|---------|---------------|
| The ask is still unframed | `/office-hours` | frame note and route |
| You want grounded options | `/ideate` | `docs/ideation/` |
| One idea needs requirements | `/brainstorm` | `docs/brainstorms/` |
| The WHAT is vague | `/spec` | `docs/specs/` |
| The WHAT is settled and needs HOW | `/plan` | `docs/plans/` |
| A plan needs readiness review | `/doc-review` | `docs/reviews/` |
| A reviewed plan should be built | `/work` | `docs/work-sessions/`, PR |
| A built branch needs pre-PR review | `/code-review` | `docs/code-reviews/` |
| Merged or merge-bound work needs evidence | `/qa` | `docs/qa/` |
| A defect or failure needs a root cause | `/investigate` | debug report |
| Finished work should teach the lifecycle | `/retro` | journal or retro artifact |

The repository contains 14 command files and 13 routable commands, pinned by `tests/test_command_surface.py`. `/ceo-review` is an alias for `/founder-review`, not a separate lifecycle node.

**What issue 1030 removed.** Eleven commands and their families left the plugin in the 1.0.0 release: `/outcome`, `/loop`, `/resume`, `/handoff`, `/optimize`, `/pulse`, `/delegation-audit`, `/promote`, `/engines`, `/tier` and `/fleet-doctor`. SDLC issue preparation, which `/handoff` used to front, is reached through the `mission-control` plugin directly. Run coordination across several sessions, which `/outcome` used to own, is the `orchestrate` plugin's.

## Manual

The manual pages are the maintained user-facing reference.

| Page | Use it for |
|------|------------|
| [Manual index](docs/README.md) | Documentation map and maintenance path |
| [Lifecycle](docs/lifecycle.md) | Main chain, off-chain routes, gates, and destination horizon |
| [Command selection](docs/commands.md) | Comparable cards for every command |
| [State and readiness](docs/state-readiness.md) | Stored saga state vs derived handoff maturity |
| [Scenarios](docs/scenarios.md) | User-situation journeys and example routes |
| [Boundaries](docs/boundaries.md) | Saga vs adjacent plugin ownership, Claude vs Codex adapter notes |

## Lifecycle In One Pass

The main chain is:

```text
idea/requirements-ready -> /plan -> /doc-review -> /work -> /code-review -> /qa -> /retro
```

Off-chain commands are still first-class, but they do not become linear saga phases. `/spec` sharpens WHAT, `/investigate` diagnoses root cause, `/strategy` records direction, and `/retro` captures learning after work is complete.

Destination sets the routing horizon:

| Destination | Horizon |
|-------------|---------|
| `plan-only` | stop at a written, reviewed plan |
| `pr` | run through `/work` to an open PR |
| `merge` | add `/work`'s confirmed merge of the PR |
| `nonprod-deploy` | after merge, route deployment mutation to `deploy` |

## State And Readiness

Saga stores three axes in local, git-ignored saga ticks: `lifecycle_phase`, `phase_status`, and `status`.

`maturity` is different. It is derived at handoff time from the source artifact or lifecycle phase and must not be stored as saga state.

| Artifact root | Derived maturity | Consumer |
|---------------|------------------|----------|
| `docs/ideation/` | `idea-ready` | `/plan` |
| `docs/brainstorms/`, `docs/specs/` | `requirements-ready` | `/plan` |
| `docs/plans/`, `docs/reviews/` | `plan-ready` | `/work` |
| `docs/work-sessions/`, branch refs | `resume-ready` | `/work` |

See [state and readiness](docs/state-readiness.md) for the full passport.

## Maintainer Workflow

Update the pages under [docs/](docs/) directly when command routes, readiness mappings, ownership boundaries or scenarios change. The generated atlas and its source model were retired with the eleven removed commands.

Check drift:

```bash
uv run pytest tests/test_command_surface.py tests/test_saga_doc_formatting.py
```

Core implementation contracts still live in canonical references:

- [Saga spec](references/saga-spec.md)
- [Operator choice](references/operator-choice.md)
- [Run record](references/run-record.md)
- [Formatting style](references/formatting-style.md)
