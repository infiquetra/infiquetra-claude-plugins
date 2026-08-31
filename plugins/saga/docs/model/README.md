# Saga Docs Model

`saga-docs-model.yaml` is the maintained source for the Saga manual's command cards, routes, readiness mappings, scenario coverage, ownership boundaries, and generated visuals.

The model is curated. It cites canonical Saga files, but it does not try to mechanically summarize full SKILL prose. Update this model first when command routing, readiness, scenarios, or visual coverage changes, then regenerate docs visuals with `plugins/saga/scripts/render_docs_visuals.py`.

The committed SVG files under `../assets/` are generated outputs. Do not edit them by hand.

## Maturity fields

- `consumed_by`: the command that **consumes** the maturity as its terminal routing destination (the dispatch table row's destination). Every maturity has exactly one consumer.
- `read_by`: commands that **read** the maturity value to branch on it but do not consume it as a terminal destination (they route onward). For example, `pending-confirmation` is consumed by `/brainstorm` but read by `/resume` (which restores the boundary and routes onward), `/loop` (which routes the value onward), and `/handoff` (which branches to decide stop versus route). Most maturities have no `read_by`; only `pending-confirmation` currently has readers, recorded here explicitly so a new reader is not missed.
