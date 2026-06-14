#!/usr/bin/env python3
"""Consumer-side parity gate for the vendored issue-contract artifacts (U1/U4, KTD3).

The mission-control plugin is a CONSUMER of the issue-contract pipeline whose
source of truth is ``infiquetra-sdlc`` (``tools/docs/gen_issue_contract.py``) --
the same vendoring pattern the plugin already uses for ``config/sdlc-schema.json``.
TWO generated modules are vendored here, each next to its pinned SHA256 manifest:

  * ``issue_contract_data.py`` -- the WHOLE validator data surface (U1);
  * ``issue_contract_shim.py`` -- the mission-control validation-shim DATA the
    ``sdlc_manager.py`` ``validate_card_body`` algorithm imports (U4).

This gate proves both vendored copies have not silently drifted.

Design (deliberately does NOT run the sdlc generator): the source generator
emits, in the source repo, each artifact PLUS a pinned SHA256 fingerprint of its
bytes; both are vendored here. This gate recomputes the SHA256 of each vendored
module and compares it to its vendored ``.sha256`` manifest. A match means the
vendored bytes equal what the source generator last produced and pinned; any
hand-edit to a vendored module flips its hash and fails the gate. No sdlc
checkout, no generator run -- just stdlib hashlib.

Exit 0 = in sync; exit 1 = drift.

Usage::

    python3 check_issue_contract_parity.py
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

VENDOR_DIR = Path(__file__).resolve().parent

# Each vendored artifact + its pinned SHA256 sidecar manifest. Adding a future
# vendored artifact here extends the gate with no other change.
VENDORED_ARTIFACTS = (
    VENDOR_DIR / "issue_contract_data.py",
    VENDOR_DIR / "issue_contract_shim.py",
)


def _sha_path(artifact: Path) -> Path:
    """The pinned-SHA sidecar manifest path for a vendored artifact."""
    return artifact.with_suffix(artifact.suffix + ".sha256")


def parity_errors(artifacts: tuple[Path, ...] = VENDORED_ARTIFACTS) -> list[str]:
    """Return human-readable parity violations across every vendored artifact;
    empty list = all in sync."""
    errors: list[str] = []
    for artifact in artifacts:
        sha_path = _sha_path(artifact)
        if not artifact.exists():
            errors.append(f"vendored issue-contract artifact missing: {artifact}")
            continue
        if not sha_path.exists():
            errors.append(f"vendored issue-contract SHA manifest missing: {sha_path}")
            continue

        actual = hashlib.sha256(artifact.read_bytes()).hexdigest()
        expected = sha_path.read_text(encoding="utf-8").strip()
        if actual != expected:
            errors.append(
                f"vendored {artifact.name} has drifted from the source-of-truth "
                "pinned hash (infiquetra-sdlc gen_issue_contract.py):\n"
                f"  expected (pinned): {expected}\n"
                f"  actual   (vendor): {actual}\n"
                "Re-vendor the generated artifact from infiquetra-sdlc."
            )
    return errors


def main() -> int:
    errors = parity_errors()
    if errors:
        for err in errors:
            print(f"FAIL {err}")
        print("\nissue-contract consumer parity check FAILED")
        return 1
    print("issue-contract consumer parity check passed: vendored artifacts are in sync")
    return 0


if __name__ == "__main__":
    sys.exit(main())
