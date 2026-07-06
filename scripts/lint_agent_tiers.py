#!/usr/bin/env python3
"""Thin manual-run wrapper for the agent-tier lint (#363, U1).

The lint itself lives as a pytest test (``tests/test_agent_tier_lint.py``) that
already runs in the existing CI pytest step — no new CI step needed (R3). This
script is a convenience entry point for local/manual runs that don't want to
invoke pytest directly.

Usage:
    python3 scripts/lint_agent_tiers.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


def main() -> int:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_agent_tier_lint.py", "-v"],
        cwd=REPO_ROOT,
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
