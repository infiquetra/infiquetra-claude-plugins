"""Shared pytest fixtures for redis-bridge tests."""

from __future__ import annotations

import sys
from pathlib import Path

# Make `server` importable without installing the package.
_HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_HERE))
