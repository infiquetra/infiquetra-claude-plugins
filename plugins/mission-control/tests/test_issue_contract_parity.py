"""Consumer-side parity test for the vendored issue-contract data (U1, KTD3).

The mission-control plugin consumes the issue-contract pipeline (source of truth:
``infiquetra-sdlc`` ``tools/docs/gen_issue_contract.py``) -- the same vendoring
pattern the plugin already uses for ``config/sdlc-schema.json``. The generated
validator-DATA module is vendored at
``plugins/mission-control/config/generated/issue_contract_data.py`` with a pinned
SHA256 manifest. This test proves the vendored copy is in sync and that the gate
catches drift -- WITHOUT running the sdlc generator.

Two layers of defence:
  1. the gate's sidecar-manifest comparison (re-vendored from sdlc, carries the
     source's authority); and
  2. an INDEPENDENT hard-coded expected-hash oracle in this test (modeled on the
     mission-control drift-guard pattern). A coordinated edit of BOTH the
     vendored data and its sidecar manifest would still fail this literal, which
     changes only via a reviewed update to this test.
"""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
VENDOR_DIR = ROOT / "plugins" / "mission-control" / "config" / "generated"
DATA_PATH = VENDOR_DIR / "issue_contract_data.py"
PARITY_PATH = VENDOR_DIR / "check_issue_contract_parity.py"

# INDEPENDENT oracle: the sha256 of the vendored issue_contract_data.py, pinned
# here as a literal. Update this DELIBERATELY when re-vendoring a new artifact
# from infiquetra-sdlc -- a silent data+manifest edit cannot pass this.
EXPECTED_DATA_SHA256 = (
    "078a27c9b84bb3e2de11c925a39a802f10d34b0e4cd5d33288f2f06ec7dc5a73"
)


def _load_parity():
    spec = importlib.util.spec_from_file_location("mc_parity", PARITY_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_vendored_data_matches_independent_oracle() -> None:
    """Hard-coded expected hash, independent of the sidecar manifest."""
    actual = hashlib.sha256(DATA_PATH.read_bytes()).hexdigest()
    assert actual == EXPECTED_DATA_SHA256, (
        "vendored issue_contract_data.py does not match the pinned oracle hash; "
        "re-vendor from infiquetra-sdlc and update EXPECTED_DATA_SHA256 if intended"
    )


def test_parity_gate_passes_in_sync() -> None:
    assert _load_parity().parity_errors() == []


def test_parity_gate_fails_on_injected_drift() -> None:
    """Inject a one-byte drift; the gate must catch it. Restore afterward."""
    mod = _load_parity()
    original = DATA_PATH.read_bytes()
    try:
        DATA_PATH.write_bytes(original + b"\n# injected drift\n")
        errors = mod.parity_errors()
        assert errors, "parity gate did not catch injected drift"
        assert "drifted" in errors[0]
    finally:
        DATA_PATH.write_bytes(original)
    assert mod.parity_errors() == []


# The full validator DATA the vendored artifact must carry, pinned independently
# of the round-trip (faithful extraction of card_validator.py FIELD_HEADERS /
# REQUIRED_FIELDS). A wrong header or a required-flag flip fails here.
EXPECTED_FIELD_HEADERS = {
    "objective": "Objective",
    "acceptance_criteria": "Acceptance criteria",
    "non_goals": "Out-of-scope / non-goals",
    "files_expected": "Files expected to change",
    "tests_required": "Tests to add or update",
    "verification": "Verification",
    "notes": "Notes / conventions",
    "context_library_links": "Context library links",
}
EXPECTED_REQUIRED_FIELDS = (
    "objective",
    "acceptance_criteria",
    "non_goals",
    "files_expected",
    "tests_required",
    "verification",
)


def test_vendored_data_is_importable_data_only() -> None:
    """The vendored artifact is valid importable DATA (full FIELD_HEADERS +
    REQUIRED_FIELDS tuple), pinned to a faithful extraction of card_validator.py."""
    namespace: dict = {}
    exec(DATA_PATH.read_text(encoding="utf-8"), namespace)
    assert namespace["FIELD_HEADERS"] == EXPECTED_FIELD_HEADERS
    assert namespace["REQUIRED_FIELDS"] == EXPECTED_REQUIRED_FIELDS
