---
name: engines
description: Inspect Saga external-engine registry rows, manage repo-local routing overlays, and dry-run capability routing without invoking an engine.
argument-hint: "list | pin <capability> <engine_id>/<variant> | deprecate <engine_id>/<variant> | clear pin <capability> | clear deprecate <engine_id>/<variant> | clear all | route explain <capability>"
---

Inspect and tune Saga external-engine routing state. `/engines` is a visibility and local-overlay command:
it never dispatches to an external engine and `route explain` is read-only.

## Forms

1. **List registry rows**:
   ```bash
   python3 plugins/saga/scripts/engine_registry_cli.py engines list
   ```

2. **Pin a capability locally**:
   ```bash
   python3 plugins/saga/scripts/engine_registry_cli.py engines pin <capability> <engine_id>/<variant>
   ```

3. **Deprecate a row locally**:
   ```bash
   python3 plugins/saga/scripts/engine_registry_cli.py engines deprecate <engine_id>/<variant>
   ```

4. **Clear local overlay state**:
   ```bash
   python3 plugins/saga/scripts/engine_registry_cli.py engines clear pin <capability>
   python3 plugins/saga/scripts/engine_registry_cli.py engines clear deprecate <engine_id>/<variant>
   python3 plugins/saga/scripts/engine_registry_cli.py engines clear all
   ```

5. **Explain a capability route**:
   ```bash
   python3 plugins/saga/scripts/engine_registry_cli.py route explain <capability>
   ```

## Behavior

- Overlay state is repo-local at `.saga/engine-overlay.json` and is never committed.
- List output includes each row's authored `trust_tier`. Probation rows remain eligible for worker
  and generator offload but cannot serve advisory-reviewer or composing-panel roles.
- Valid pins override registry ranking only when the target row exists, is not deprecated, and declares
  the requested capability.
- Deprecated rows are filtered before ranking.
- Ranking remains registry-owned: rating first, then `cost_speed_rank`, then `registry_order`.
- `route explain` does not write overlay state, call engine CLIs, call HTTP transports, or evaluate live
  credentials.
