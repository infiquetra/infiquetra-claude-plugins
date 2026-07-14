"""NEGATIVE fixture for ``scripts/lint_test_shape.py`` (#458, T11-F2-8).

This module imports/patches ONLY a fake and never imports or exercises the real production module
it purports to cover, so ``lint_test_shape.py`` must flag it (non-zero exit). It is deliberately NOT
named ``test_*.py`` so pytest does not collect it — it exists purely as lint input.
"""

from __future__ import annotations

from unittest.mock import MagicMock


class FakeWorktreeOps:
    """A stand-in liveness oracle that never crosses into real git — the hazard this lint gates."""

    def exists(self, path: str) -> bool:
        return True


def test_liveness_with_fake_only() -> None:
    fake = FakeWorktreeOps()
    patched = MagicMock(wraps=fake)
    # Asserts against the fake's hand-wired answer, never against a real adapter.
    assert patched.exists("/any/path") is True
