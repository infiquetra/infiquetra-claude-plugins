"""Tests for the U6 manifest reader (R7 parroting, R16 verified ratio, R18 disposition rate).

Tests cover:

* **Parroting taxonomy** — only claimed-verified + adjudicated-refuted/unsupported claims
  count; not-adjudicated / scope-excluded / source-stale / already-inferred claims do not.
* **Disposition rate** — mirrors ``override_rate_reader``'s rate semantics (dict of counts +
  fractions), correct over a mix of manifests.
* **Advisory-never-blocks** — an empty/absent manifest tree yields an informative report and
  a zero exit code, never an exception (R8/R12).
* **Verified ratio arithmetic** — R16's verified / (verified + inferred + not-checked).

Determinism / offline discipline: every test writes manifest JSON files into ``tmp_path`` and
points the reader at that directory — the real ``saga-manifests/`` common-dir tree is never
touched.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = ROOT / "plugins" / "saga" / "scripts"


def _load_module(name: str) -> ModuleType:
    path = SCRIPTS_DIR / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name.removesuffix(".py")] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mr() -> ModuleType:
    """Loaded manifest_reader module."""
    return _load_module("manifest_reader.py")


@pytest.fixture(scope="module")
def pm(mr: ModuleType) -> ModuleType:
    """The provenance_manifest module (loaded as a side effect of manifest_reader's import)."""
    return sys.modules["provenance_manifest"]


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _claim(
    *,
    claimed: str = "verified",
    adjudicated: str | None = None,
    mismatch_reason: str | None = None,
) -> dict:
    return {
        "text": "the thing is true",
        "claimed": claimed,
        "source_ref": "file.py:10",
        "source_revision": "",
        "adjudicated": adjudicated,
        "mismatch_reason": mismatch_reason,
        "adjudication": None,
    }


def _manifest(
    execution_id: str,
    *,
    disposition: str = "ran-as-requested",
    claims: list[dict] | None = None,
) -> dict:
    return {
        "schema": "saga.manifest.v1",
        "execution_id": execution_id,
        "saga_ref": "saga-42",
        "attribution": {
            "kind": "external-engine",
            "identity": "gemini-3.1-pro",
            "effort": "high",
            "protocol": "",
        },
        "disposition": disposition,
        "disposition_note": "",
        "created_at": "2026-07-01T00:00:00Z",
        "output_completeness": None,
        "claim_provenance": {"claims": claims} if claims is not None else None,
    }


def _write(root: Path, saga_id: str, execution_id: str, manifest: dict) -> None:
    saga_dir = root / saga_id
    saga_dir.mkdir(parents=True, exist_ok=True)
    (saga_dir / f"{execution_id}.json").write_text(json.dumps(manifest), encoding="utf-8")


# ---------------------------------------------------------------------------
# Parroting taxonomy (R7)
# ---------------------------------------------------------------------------


def test_reader_counts_parroting_only_on_refuted_unsupported(
    tmp_path: Path, mr: ModuleType
) -> None:
    claims = [
        _claim(claimed="verified", adjudicated="refuted"),  # parroting
        _claim(
            claimed="verified", adjudicated="inferred", mismatch_reason="unsupported"
        ),  # parroting
        _claim(claimed="verified", adjudicated="verified"),  # not parroting — confirmed
        _claim(
            claimed="not-checked", adjudicated="refuted"
        ),  # not parroting — not claimed-verified
        _claim(
            claimed="verified", adjudicated=None, mismatch_reason="not-adjudicated"
        ),  # not parroting
        _claim(
            claimed="verified", adjudicated=None, mismatch_reason="scope-excluded"
        ),  # not parroting
    ]
    _write(tmp_path, "saga-1", "exec-1", _manifest("exec-1", claims=claims))

    summary, manifests = mr.read_manifest_summary(tmp_path)

    assert summary.total_manifests == 1
    assert summary.total_claims == len(claims)
    assert summary.parroting_count == 2
    assert summary.parroting_rate == pytest.approx(2 / len(claims))


def test_reader_lightweight_manifest_no_claims_counts_zero_parroting(
    tmp_path: Path, mr: ModuleType
) -> None:
    _write(tmp_path, "saga-1", "exec-1", _manifest("exec-1", claims=None))

    summary, _manifests = mr.read_manifest_summary(tmp_path)

    assert summary.total_manifests == 1
    assert summary.total_claims == 0
    assert summary.parroting_count == 0
    assert summary.parroting_rate is None


# ---------------------------------------------------------------------------
# Disposition rate (R18)
# ---------------------------------------------------------------------------


def test_reader_disposition_rate_over_mixed_manifests(tmp_path: Path, mr: ModuleType) -> None:
    _write(tmp_path, "saga-1", "exec-1", _manifest("exec-1", disposition="ran-as-requested"))
    _write(tmp_path, "saga-1", "exec-2", _manifest("exec-2", disposition="ran-as-requested"))
    _write(tmp_path, "saga-1", "exec-3", _manifest("exec-3", disposition="fell-back-to-claude"))
    _write(tmp_path, "saga-2", "exec-4", _manifest("exec-4", disposition="substituted-engine"))

    summary, _manifests = mr.read_manifest_summary(tmp_path)

    assert summary.total_manifests == 4
    assert summary.disposition_counts["ran-as-requested"] == 2
    assert summary.disposition_counts["fell-back-to-claude"] == 1
    assert summary.disposition_counts["substituted-engine"] == 1
    rate = summary.disposition_rate
    assert rate["ran-as-requested"] == pytest.approx(0.5)
    assert rate["fell-back-to-claude"] == pytest.approx(0.25)
    assert rate["substituted-engine"] == pytest.approx(0.25)


# ---------------------------------------------------------------------------
# Advisory: never blocks, empty tree
# ---------------------------------------------------------------------------


def test_reader_advisory_never_blocks_empty_tree_exits_zero(tmp_path: Path, mr: ModuleType) -> None:
    empty_root = tmp_path / "does-not-exist"

    summary, manifests = mr.read_manifest_summary(empty_root)

    assert summary.total_manifests == 0
    assert manifests == []
    assert summary.disposition_rate == dict.fromkeys(summary.disposition_counts, None)
    assert summary.verified_ratio is None
    assert summary.parroting_rate is None

    report = mr.format_report(summary)
    assert "no manifests recorded yet".lower() in report.lower() or "no data" not in ""
    assert "No manifests recorded yet" in report

    exit_code = mr.main(["--root", str(empty_root)])
    assert exit_code == 0


def test_reader_cli_json_smoke(
    tmp_path: Path, mr: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = mr.main(["--root", str(tmp_path / "absent"), "--json"])
    assert exit_code == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["total_manifests"] == 0
    assert payload["verified_ratio"] is None


# ---------------------------------------------------------------------------
# Verified ratio arithmetic (R16)
# ---------------------------------------------------------------------------


def test_reader_verified_ratio(tmp_path: Path, mr: ModuleType) -> None:
    claims = [
        _claim(claimed="verified", adjudicated="verified"),
        _claim(claimed="verified", adjudicated="verified"),
        _claim(claimed="verified", adjudicated="verified"),
        _claim(claimed="inferred", adjudicated="inferred"),
        _claim(claimed="not-checked", adjudicated="not-checked"),
        _claim(claimed="verified", adjudicated="refuted"),  # excluded from ratio denominator
    ]
    _write(tmp_path, "saga-1", "exec-1", _manifest("exec-1", claims=claims))

    summary, _manifests = mr.read_manifest_summary(tmp_path)

    assert summary.adjudicated_verified_count == 3
    assert summary.adjudicated_inferred_count == 1
    assert summary.adjudicated_not_checked_count == 1
    assert summary.adjudicated_refuted_count == 1
    # denominator excludes refuted: 3 / (3 + 1 + 1) = 0.6
    assert summary.verified_ratio == pytest.approx(0.6)


def test_reader_verified_ratio_none_with_no_adjudication(tmp_path: Path, mr: ModuleType) -> None:
    claims = [_claim(claimed="verified", adjudicated=None, mismatch_reason="not-adjudicated")]
    _write(tmp_path, "saga-1", "exec-1", _manifest("exec-1", claims=claims))

    summary, _manifests = mr.read_manifest_summary(tmp_path)

    assert summary.verified_ratio is None


# ---------------------------------------------------------------------------
# Malformed / unreadable manifests are skipped, not fatal (advisory, R8)
# ---------------------------------------------------------------------------


def test_reader_skips_malformed_manifest_files(tmp_path: Path, mr: ModuleType) -> None:
    saga_dir = tmp_path / "saga-1"
    saga_dir.mkdir(parents=True)
    (saga_dir / "exec-bad.json").write_text("{not valid json", encoding="utf-8")
    (saga_dir / "exec-wrong-schema.json").write_text(
        json.dumps({**_manifest("exec-wrong-schema"), "schema": "saga.manifest.v0"}),
        encoding="utf-8",
    )
    _write(tmp_path, "saga-1", "exec-good", _manifest("exec-good"))

    summary, manifests = mr.read_manifest_summary(tmp_path)

    assert summary.total_manifests == 1
    assert manifests[0].execution_id == "exec-good"
