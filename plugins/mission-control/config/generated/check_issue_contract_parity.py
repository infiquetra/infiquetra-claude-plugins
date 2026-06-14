#!/usr/bin/env python3
"""Consumer-side parity gate for the vendored issue-contract data (U1, KTD3).

The mission-control plugin is a CONSUMER of the issue-contract pipeline whose
source of truth is ``infiquetra-sdlc`` (``tools/docs/gen_issue_contract.py``) --
the same vendoring pattern the plugin already uses for ``config/sdlc-schema.json``.
The generated validator-DATA module ``issue_contract_data.py`` is vendored here;
a later unit replaces the hand-maintained shim data with it. This gate proves the
vendored copy has not silently drifted.

Design (deliberately does NOT run the sdlc generator): the source generator
emits, in the source repo, the artifact PLUS a pinned SHA256 fingerprint of its
bytes; both are vendored here. This gate recomputes the SHA256 of the vendored
``issue_contract_data.py`` and compares it to the vendored
``issue_contract_data.py.sha256`` manifest. A match means the vendored bytes
equal what the source generator last produced and pinned; any hand-edit to the
vendored data flips the hash and fails the gate. No sdlc checkout, no generator
run -- just stdlib hashlib.

Exit 0 = in sync; exit 1 = drift.

Usage::

    python3 check_issue_contract_parity.py
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

VENDOR_DIR = Path(__file__).resolve().parent
DATA_PATH = VENDOR_DIR / "issue_contract_data.py"
SHA_PATH = VENDOR_DIR / "issue_contract_data.py.sha256"


def parity_errors(
    data_path: Path = DATA_PATH, sha_path: Path = SHA_PATH
) -> list[str]:
    """Return human-readable parity violations; empty list = in sync."""
    errors: list[str] = []
    if not data_path.exists():
        return [f"vendored issue-contract data missing: {data_path}"]
    if not sha_path.exists():
        return [f"vendored issue-contract SHA manifest missing: {sha_path}"]

    actual = hashlib.sha256(data_path.read_bytes()).hexdigest()
    expected = sha_path.read_text(encoding="utf-8").strip()

    if actual != expected:
        errors.append(
            "vendored issue_contract_data.py has drifted from the source-of-truth "
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
    print("issue-contract consumer parity check passed: vendored data is in sync")
    return 0


if __name__ == "__main__":
    sys.exit(main())
