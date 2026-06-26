# Saga Manual

This manual explains Saga as a lifecycle operating model: where work starts, which command owns each phase, how local saga state differs from handoff readiness, and where Saga stops in favor of adjacent Infiquetra plugins.

The source model for command coverage and visuals is [model/saga-docs-model.yaml](model/saga-docs-model.yaml). Rendered SVGs live in [assets/](assets/).

## Reading Path

| Need | Page |
|------|------|
| Understand the main lifecycle | [Lifecycle](lifecycle.md) |
| Pick the right command | [Command selection](commands.md) |
| Interpret saga state or artifact maturity | [State and readiness](state-readiness.md) |
| Start from a real user situation | [Scenarios](scenarios.md) |
| Know which plugin owns what | [Boundaries](boundaries.md) |
| Maintain or regenerate diagrams | [Visuals](visuals.md) |

## Operating Model

Saga has 20 command files and 19 routable commands. `/ceo-review` is a compatibility alias for `/founder-review`.

The main chain is a reviewed-work spine:

```text
idea/requirements-ready -> /plan -> /doc-review -> /work -> /code-review -> /qa -> /handoff or /retro
```

Several commands intentionally sit off the linear spine. `/spec`, `/investigate`, `/optimize`, and `/strategy` are not stored lifecycle phases; they produce artifacts or decisions that route back into the chain.

## Maintainer Path

Update [model/saga-docs-model.yaml](model/saga-docs-model.yaml) first when the command surface, routes, state/readiness mappings, scenarios, ownership boundaries, or visual inventory changes.

Then regenerate visuals:

```bash
uv run python plugins/saga/scripts/render_docs_visuals.py
```

Then run:

```bash
uv run pytest tests/test_saga_docs_coverage.py tests/test_saga_doc_formatting.py
```
