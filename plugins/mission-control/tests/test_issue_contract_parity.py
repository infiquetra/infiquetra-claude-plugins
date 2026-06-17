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
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = ROOT / "plugins" / "mission-control" / "config" / "sdlc-schema.json"
VENDOR_DIR = ROOT / "plugins" / "mission-control" / "config" / "generated"
DATA_PATH = VENDOR_DIR / "issue_contract_data.py"
SHIM_PATH = VENDOR_DIR / "issue_contract_shim.py"
PARITY_PATH = VENDOR_DIR / "check_issue_contract_parity.py"

# INDEPENDENT oracle: the sha256 of the vendored issue_contract_data.py, pinned
# here as a literal. Update this DELIBERATELY when re-vendoring a new artifact
# from infiquetra-sdlc -- a silent data+manifest edit cannot pass this.
# Updated 2026-06-14 for the U8 context-package expansion.
EXPECTED_DATA_SHA256 = "22fa2b5b77acd739a7a0648d163f3292ddf433903e3f2c97f8c8f2e2feb0afec"
# INDEPENDENT oracle for the vendored shim module (same discipline as the data
# oracle above). Update DELIBERATELY when re-vendoring the shim from sdlc.
# Updated 2026-06-14 for the U8 context-package expansion.
EXPECTED_SHIM_SHA256 = "65d972ff3a049ba8103c501d61cdf16266f12eba35c749d76a937fcfe87357ff"


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


def test_vendored_schema_carries_issue_fields_block() -> None:
    """The consumer schema must include the source issue_fields block, not just
    the generated Python artifacts."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    issue_fields = schema.get("issue_fields")
    assert issue_fields, "vendored sdlc-schema.json is missing issue_fields"
    fields_by_key = {field["key"]: field for field in issue_fields["fields"]}
    assert fields_by_key["intent"]["required"] is True
    assert fields_by_key["context_library_links"]["required"] is True
    assert issue_fields["required_matrix"]["auto_populated_fields"] == ["lifecycle_origin"]
    assert "very-high" in issue_fields["required_matrix"]["axes"]["risk"]


# The full validator DATA the vendored artifact must carry, pinned independently
# of the round-trip (faithful extraction of card_validator.py FIELD_HEADERS /
# REQUIRED_FIELDS). A wrong header or a required-flag flip fails here.
# Updated 2026-06-14 for the U8 context-package expansion (Intent + risk-
# conditional fields + Lifecycle Origin; context_library_links promoted to
# required). Order is the U10/R11 canonical order.
EXPECTED_FIELD_HEADERS = {
    "objective": "Objective",
    "intent": "Intent",
    "non_goals": "Out-of-scope / non-goals",
    "inputs": "Inputs inventory",
    "files_expected": "Files expected to change",
    "tests_required": "Tests to add or update",
    "failure_modes": "Failure modes / pre-mortem",
    "stop_conditions": "Stop conditions",
    "context_library_links": "Context library links",
    "notes": "Notes / conventions",
    "acceptance_criteria": "Acceptance criteria",
    "verification": "Verification",
    "lifecycle_origin": "Lifecycle Origin",
}
# The always-required core (risk-independent). The risk-conditional + auto fields
# are NOT here; the REQUIRED_MATRIX (also vendored) keys them.
EXPECTED_REQUIRED_FIELDS = (
    "objective",
    "intent",
    "non_goals",
    "files_expected",
    "tests_required",
    "context_library_links",
    "acceptance_criteria",
    "verification",
)


def test_vendored_data_is_importable_data_only() -> None:
    """The vendored artifact is valid importable DATA (full FIELD_HEADERS +
    REQUIRED_FIELDS tuple), pinned to a faithful extraction of card_validator.py."""
    namespace: dict = {}
    exec(DATA_PATH.read_text(encoding="utf-8"), namespace)
    assert namespace["FIELD_HEADERS"] == EXPECTED_FIELD_HEADERS
    assert namespace["REQUIRED_FIELDS"] == EXPECTED_REQUIRED_FIELDS


def test_vendored_data_carries_risk_matrix() -> None:
    """U8/R12: the vendored DATA carries the field x type x risk REQUIRED_MATRIX
    + the EXECUTABLE_CHECKS the home-lab algorithm evaluates."""
    namespace: dict = {}
    exec(DATA_PATH.read_text(encoding="utf-8"), namespace)
    matrix = namespace["REQUIRED_MATRIX"]
    assert set(matrix["axes"]["risk"]) == {"low", "medium", "high", "very-high", "*"}
    assert matrix["auto_populated_fields"] == ["lifecycle_origin"]
    assert "acceptance_criteria" in namespace["EXECUTABLE_CHECKS"]


# The shim DATA surface the vendored shim must carry, pinned independently of the
# round-trip. These are the names sdlc_manager.py's validate_card_body imports
# (U4); a wrong header, a lost lowercased-placeholder, or a renamed regex const
# fails here. Updated 2026-06-14: Intent + Context library links are now required
# H3 headers (R1/R4); the risk-conditional fields + Lifecycle Origin are OPTIONAL
# at the shim layer (it has no Risk input). The placeholder set stays LOWERCASED.
EXPECTED_SHIM_REQUIRED_H3 = (
    "Objective",
    "Intent",
    "Out-of-scope / non-goals",
    "Files expected to change",
    "Tests to add or update",
    "Context library links",
    "Acceptance criteria",
    "Verification",
)
EXPECTED_SHIM_OPTIONAL_H3 = (
    "Inputs inventory",
    "Failure modes / pre-mortem",
    "Stop conditions",
    "Notes / conventions",
    "Lifecycle Origin",
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
        "ACCEPTANCE_EXECUTABLE_RE_PATTERN",
    ):
        assert const in namespace, f"vendored shim missing {const}"
