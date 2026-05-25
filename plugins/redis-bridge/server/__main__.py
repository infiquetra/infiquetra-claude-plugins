"""Entry point: `python -m server` launches the redis-bridge MCP server.

Phase 0 stub — actual MCP wiring lands in Phase 1. For now, this verifies
the module imports cleanly and exposes the package version.
"""

from __future__ import annotations

import sys

from . import __version__


def main() -> int:
    print(f"redis-bridge MCP channel server v{__version__}", file=sys.stderr)
    print("Phase 0 scaffold: real MCP loop arrives in Phase 1.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
