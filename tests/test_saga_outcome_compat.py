"""U1 (#678) — settlement and successor handoff WITHOUT the fleet lease broker.

The lease-broker retirement plan's unit U1 unwinds the six broker call sites in
``plugins/saga/scripts/outcome_compat.py`` (verify, prepare_agent_settlement,
commit_agent_settlement, inspect_resource_head, acquire_successor, verify) and lets the
handoff settlement record outcomes directly against the write-once git-common-dir store.
These tests pin the three scenarios the unit requires:

* a settlement records a terminal outcome with no lease present;
* a successor handoff completes without ``acquire_successor``;
* a settlement for an unknown dispatch id still raises rather than silently passing —
  removing the fencing token must not turn a real error into a no-op.

The broader frozen cross-runtime contract (identity, schemas, halt receipts, store safety)
stays pinned by ``test_outcome_cross_runtime_contract.py``.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "plugins" / "saga" / "scripts"
SCRIPT = SCRIPTS / "outcome_compat.py"

OUTCOME_ID = "u1-demo"
SUBPLOT = "sub-2"
ISSUER = "issuer-claude"
RECEIVER = "receiver-codex"
DISPATCH_ID = "outcome:u1:frontier:abc"


def _load() -> ModuleType:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    # A DISTINCT sys.modules key: test_outcome_cross_runtime_contract.py loads the same file
    # under "outcome_compat", and outcome.py's lazy `import outcome_compat` resolves against
    # that key at runtime. Clobbering it here would hand the contract tests a foreign
    # CompatibilityHaltError class in the full suite (their pytest.raises would miss it).
    spec = importlib.util.spec_from_file_location("_test_outcome_compat_u1", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["_test_outcome_compat_u1"] = module
    spec.loader.exec_module(module)
    return module


OC = _load()


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def _spec_dict() -> dict[str, Any]:
    return {
        "outcome_id": OUTCOME_ID,
        "objective": "demo",
        "nodes": [],
        "spec_revision": 3,
        "schema_version": 1,
        "decision_trail": [],
        "cost_rollup": {},
        "created_at": "2026-07-18T00:00:00Z",
        "updated_at": "2026-07-18T00:00:00Z",
    }


@pytest.fixture
def outcome_repo(tmp_path: Path) -> Path:
    """A real git repo with one committed outcome spec and a canonical origin remote."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Test")
    spec_file = repo / "docs" / "outcomes" / OUTCOME_ID / "outcome-spec.json"
    spec_file.parent.mkdir(parents=True)
    spec_file.write_text(json.dumps(_spec_dict(), indent=1), encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "seed outcome spec")
    _git(repo, "remote", "add", "origin", "https://github.com/infiquetra/demo-repo.git")
    return repo


def _offer(repo: Path, **kw: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    defaults: dict[str, Any] = {
        "operation": "advance-one",
        "attempt": 1,
        "issuer_owner_id": ISSUER,
        "dispatch_id": DISPATCH_ID,
    }
    defaults.update(kw)
    return cast(
        "tuple[dict[str, Any], dict[str, Any]]",
        OC.offer_handoff(repo, OUTCOME_ID, SUBPLOT, **defaults),
    )


def _accept(repo: Path, handoff_id: str, **kw: Any) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "operation": "advance-one",
        "subplot_id": SUBPLOT,
        "receiver_owner_id": RECEIVER,
        "receiver_runtime": "codex",
    }
    defaults.update(kw)
    return cast("dict[str, Any]", OC.accept_handoff(repo, OUTCOME_ID, handoff_id, **defaults))


# ---------------------------------------------------------------------------
# Scenario 1 — a settlement records a terminal outcome with no lease present
# ---------------------------------------------------------------------------


class TestSettlementWithoutLease:
    def test_offer_records_a_terminal_outcome_with_no_lease_present(
        self, outcome_repo: Path
    ) -> None:
        """The settlement-close write (prepare -> protected writer -> close receipt) is gone:
        the sealed offer record lands through the store's write-once path alone. No broker,
        no lease, and no lease-derived field anywhere in the recorded outcome."""
        offer, reference = _offer(outcome_repo)
        assert offer["schema"] == OC.SCHEMA_HANDOFF_OFFER
        assert offer["issuer_owner_id"] == ISSUER  # caller-asserted (Option C accepted loss)
        assert offer["dispatch_id"] == DISPATCH_ID
        assert offer["idempotency_key"]  # the #351 settlement identity survives
        for retired_field in ("lease_id", "resource_ref", "token"):
            assert retired_field not in offer
        assert reference["schema"] == OC.SCHEMA_HANDOFF_REFERENCE
        assert reference["digest"] == offer["sha256"]
        # the record is durably in the git-common-dir store, sealed
        stored = OC._load_sealed(
            OC._handoffs_dir(outcome_repo, OUTCOME_ID) / f"{offer['handoff_id']}.offer.json",
            schema=OC.SCHEMA_HANDOFF_OFFER,
            what="handoff offer",
        )
        assert stored["sha256"] == offer["sha256"]

    def test_module_exposes_no_broker_seam(self) -> None:
        """The unwind is structural: no broker loader, no successor helper, no broker-only
        resource naming survive in the module surface."""
        for retired in (
            "_lease_broker_mod",
            "_broker_module",
            "_acquire_successor_or_resume",
            "outcome_dispatch_resource",
        ):
            assert not hasattr(OC, retired)


# ---------------------------------------------------------------------------
# Scenario 2 — a successor handoff completes without acquire_successor
# ---------------------------------------------------------------------------


class TestSuccessorHandoffWithoutBroker:
    def test_handoff_completes_without_acquire_successor(self, outcome_repo: Path) -> None:
        """The whole offer -> accept transition runs with no broker argument anywhere: the
        write-once intent/commit pair IS the successor binding now."""
        offer, _reference = _offer(outcome_repo)
        result = _accept(outcome_repo, offer["handoff_id"])
        assert set(result) == {"offer", "intent", "commit"}
        assert result["intent"]["receiver_owner_id"] == RECEIVER
        assert result["commit"]["receiver_owner_id"] == RECEIVER
        for retired_field in ("successor_lease_id", "successor_token"):
            assert retired_field not in result["commit"]

    def test_same_receiver_reacceptance_resumes_the_crash_gap(self, outcome_repo: Path) -> None:
        """A crash between intent and commit retries cleanly: the sealed intent is reused and
        the commit completes — idempotently, byte-identically, with no broker resume path."""
        frozen = 1_800_000_000.0  # deterministic clock: the commit epoch is re-derived on retry
        offer, _reference = _offer(outcome_repo, now=lambda: frozen)
        first = _accept(outcome_repo, offer["handoff_id"], now=lambda: frozen + 5)
        commit_path = (
            OC._handoffs_dir(outcome_repo, OUTCOME_ID) / f"{offer['handoff_id']}.commit.json"
        )
        commit_path.unlink()  # emulate the crash gap
        resumed = _accept(outcome_repo, offer["handoff_id"], now=lambda: frozen + 5)
        assert resumed["intent"]["sha256"] == first["intent"]["sha256"]
        assert resumed["commit"]["sha256"] == first["commit"]["sha256"]

    def test_second_receiver_still_halts_on_the_bound_intent(self, outcome_repo: Path) -> None:
        offer, _reference = _offer(outcome_repo)
        _accept(outcome_repo, offer["handoff_id"])
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            _accept(outcome_repo, offer["handoff_id"], receiver_owner_id="receiver-other")
        assert exc.value.code == "handoff-receiver-conflict"


# ---------------------------------------------------------------------------
# Scenario 3 — unknown dispatch identity still raises (never a silent no-op)
# ---------------------------------------------------------------------------


class TestDispatchIdentityGuardsSurvive:
    def test_advance_one_without_dispatch_identity_raises(self, outcome_repo: Path) -> None:
        """The #351 settled-attempt binding is inert without a dispatch identity, so the
        offer refuses it — the token removal must not turn this error into a no-op."""
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            _offer(outcome_repo, dispatch_id="")
        assert exc.value.code == "schema-field-type"
        assert "dispatch identity" in exc.value.unsupported

    def test_offer_without_issuer_identity_raises(self, outcome_repo: Path) -> None:
        """Identity is caller-asserted now, but the assertion is still REQUIRED — an anonymous
        offer is an error, not a silent pass."""
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            _offer(outcome_repo, issuer_owner_id="   ")
        assert exc.value.code == "schema-field-type"
        assert "issuer owner identity" in exc.value.unsupported

    def test_settled_dispatch_attempt_still_refuses_acceptance(self, outcome_repo: Path) -> None:
        """The #351 lane still decides for a dispatch id the run ledger already settled: the
        guard consults settled_lookup exactly as before the unwind."""
        offer, _reference = _offer(outcome_repo)
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            _accept(
                outcome_repo,
                offer["handoff_id"],
                settled_lookup=lambda dispatch_id, unit_id, attempt: dispatch_id == DISPATCH_ID,
            )
        assert exc.value.code == "handoff-already-settled"

    def test_attend_still_permits_empty_dispatch_id(self, outcome_repo: Path) -> None:
        """Only advance-one carries the settled-attempt binding; attend offers stay unbound."""
        offer, _reference = _offer(outcome_repo, operation="attend", dispatch_id="")
        assert offer["operation"] == "attend"
