# Saga Visuals

Saga visuals are generated from the curated source model, not edited by hand.

## Source And Outputs

| Visual | File | Purpose |
|--------|------|---------|
| Lifecycle atlas | [assets/lifecycle-atlas.svg](assets/lifecycle-atlas.svg) | spine, gates, off-chain routes, destination horizon |
| State/readiness ladder | [assets/state-readiness-ladder.svg](assets/state-readiness-ladder.svg) | stored state axes vs derived maturity |
| Command matrix | [assets/command-matrix.svg](assets/command-matrix.svg) | command ownership and alias note |
| Ownership boundary map | [assets/ownership-boundary-map.svg](assets/ownership-boundary-map.svg) | Saga vs adjacent plugin ownership |

The maintained source is [model/saga-docs-model.yaml](model/saga-docs-model.yaml).

## Regenerate

Run:

```bash
uv run python plugins/saga/scripts/render_docs_visuals.py
```

Check committed outputs are current:

```bash
uv run python plugins/saga/scripts/render_docs_visuals.py --check
```

## Design Contract

The v1 visuals are SVG because they are readable in Markdown, reviewable in git, and usable in 16:9 presentation contexts without a separate export step.

Every visual must have nearby text fallback in the manual. The image helps explain; the table remains the operational truth for plain Markdown readers.

Do not edit files under [assets/](assets/) directly. Update the model and renderer, then regenerate.
