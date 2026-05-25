"""Entry point: `python -m server` launches the redis-bridge MCP server."""

from __future__ import annotations

from .channel import run


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
