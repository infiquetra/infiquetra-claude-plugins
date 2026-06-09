# Saga Docs Model

`saga-docs-model.yaml` is the maintained source for the Saga manual's command cards, routes, readiness mappings, scenario coverage, ownership boundaries, and generated visuals.

The model is curated. It cites canonical Saga files, but it does not try to mechanically summarize full SKILL prose. Update this model first when command routing, readiness, scenarios, or visual coverage changes, then regenerate docs visuals with `plugins/saga/scripts/render_docs_visuals.py`.

The committed SVG files under `../assets/` are generated outputs. Do not edit them by hand.
