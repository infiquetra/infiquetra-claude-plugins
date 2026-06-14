"""Consumer-side parity test for the vendored issue-contract artifacts (U1/U4, KTD3).

The mission-control plugin consumes the issue-contract pipeline (source of truth:
``infiquetra-sdlc`` ``tools/docs/gen_issue_contract.py``) -- the same vendoring
pattern the plugin already uses for ``config/sdlc-schema.json``. TWO generated
modules are vendored under ``plugins/mission-control/config/generated/``, each
with a pinned SHA256 manifest:

  * ``issue_contract_data.py`` -- the WHOLE validator data surface (U1);
  * ``issue_contract_shim.py`` -- the shim DATA ``sdlc_manager.py``'s
    ``validate_card_body`` imports (U4).

This test proves both vendored copies are in sync and that the gate catches
drift -- WITHOUT running the sdlc generator.

Two layers of defence:
  1. the gate's sidecar-manifest comparison (re-vendored from sdlc, carries the
     source's authority); and
  2. INDEPENDENT hard-coded expected-hash oracles in this test (modeled on the
     mission-control drift-guard pattern). A coordinated edit of BOTH a vendored
     module and its sidecar manifest would still fail these literals, which
     change only via a reviewed update to this test.
"""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
VENDOR_DIR = ROOT / "plugins" / "mission-control" / "config" / "generated"
DATA_PATH = VENDOR_DIR / "issue_contract_data.py"
SHIM_PATH = VENDOR_DIR / "issue_contract_shim.py"
PARITY_PATH = VENDOR_DIR / "check_issue_contract_parity.py"

# INDEPENDENT oracle: the sha256 of the vendored issue_contract_data.py, pinned
# here as a literal. Update this DELIBERATELY when re-vendoring a new artifact
# from infiquetra-sdlc -- a silent data+manifest edit cannot pass this.
EXPECTED_DATA_SHA256 = "3eace49017da09f9981035f2aec1bdfe0dae0b770ac0cf3a399f78099bde7f4d"
# INDEPENDENT oracle for the vendored shim module (same discipline as the data
# oracle above). Update DELIBERATELY when re-vendoring the shim from sdlc.
EXPECTED_SHIM_SHA256 = "ef825769172cdc9148705bc19f7a01108f6c986f70719980309fcf69f4365285"


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


def test_vendored_shim_matches_independent_oracle() -> None:
    """Hard-coded expected hash for the vendored shim, independent of its manifest."""
    actual = hashlib.sha256(SHIM_PATH.read_bytes()).hexdigest()
    assert actual == EXPECTED_SHIM_SHA256, (
        "vendored issue_contract_shim.py does not match the pinned oracle hash; "
        "re-vendor from infiquetra-sdlc and update EXPECTED_SHIM_SHA256 if intended"
    )


def test_parity_gate_passes_in_sync() -> None:
    assert _load_parity().parity_errors() == []


def test_parity_gate_fails_on_injected_drift() -> None:
    """Inject a one-byte drift into the DATA module; the gate must catch it."""
    mod = _load_parity()
    original = DATA_PATH.read_bytes()
    try:
        DATA_PATH.write_bytes(original + b"\n# injected drift\n")
        errors = mod.parity_errors()
        assert errors, "parity gate did not catch injected DATA drift"
        assert any("drifted" in e for e in errors)
    finally:
        DATA_PATH.write_bytes(original)
    assert mod.parity_errors() == []


def test_parity_gate_fails_on_injected_shim_drift() -> None:
    """Inject a one-byte drift into the SHIM module; the gate must catch it."""
    mod = _load_parity()
    original = SHIM_PATH.read_bytes()
    try:
        SHIM_PATH.write_bytes(original + b"\n# injected drift\n")
        errors = mod.parity_errors()
        assert errors, "parity gate did not catch injected SHIM drift"
        assert any("drifted" in e for e in errors)
    finally:
        SHIM_PATH.write_bytes(original)
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


# The shim DATA surface the vendored shim must carry, pinned independently of the
# round-trip. These are the names sdlc_manager.py's validate_card_body imports
# (U4); a wrong header, a lost lowercased-placeholder, or a renamed regex const
# fails here. The 6 required H3 headers mirror EXPECTED_FIELD_HEADERS' required
# subset (header values), and the placeholder set is LOWERCASED on purpose --
# the shim compares ``ln.lower() in PLACEHOLDER_LINES``.
EXPECTED_SHIM_REQUIRED_H3 = (
    "Objective",
    "Acceptance criteria",
    "Out-of-scope / non-goals",
    "Files expected to change",
    "Tests to add or update",
    "Verification",
)
EXPECTED_SHIM_OPTIONAL_H3 = (
    "Notes / conventions",
    "Context library links",
)
EXPECTED_SHIM_PLACEHOLDER_LINES = (
    "- [ ]",
    "-",
    "* [ ]",
    "*",
    "_no response_",
    "none",
    "<!-- placeholder -->",
)


def test_vendored_shim_is_importable_data_only() -> None:
    """The vendored shim is valid importable DATA (the exact names
    validate_card_body imports): required/optional H3 headers, the named regex
    constants, and the LOWERCASED placeholder set. DATA only -- no algorithm."""
    namespace: dict = {}
    exec(SHIM_PATH.read_text(encoding="utf-8"), namespace)
    assert namespace["REQUIRED_H3_HEADERS"] == EXPECTED_SHIM_REQUIRED_H3
    assert namespace["OPTIONAL_H3_HEADERS"] == EXPECTED_SHIM_OPTIONAL_H3
    assert namespace["PLACEHOLDER_LINES"] == EXPECTED_SHIM_PLACEHOLDER_LINES
    # The named regex constants the shim algorithm re-compiles.
    for const in (
        "HEADER_RE_PATTERN",
        "CHECKLIST_RE_PATTERN",
        "CODE_BLOCK_RE_PATTERN",
        "PATH_LINE_RE_PATTERN",
    ):
        assert const in namespace, f"vendored shim missing {const}"
