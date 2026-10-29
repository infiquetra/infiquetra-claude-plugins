"""Exercise the real locked scanner and its fail-closed report boundary."""

from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

SPEC = importlib.util.spec_from_file_location(
    "bandit_gate", Path(__file__).resolve().parents[1] / "scripts/bandit_gate.py"
)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


def _tree(root: Path, seed: str = "value = 1\n", selected: str = "plugins") -> Path:
    for name in GATE.ROOTS:
        directory = root / name
        directory.mkdir(parents=True)
        (directory / "seed.py").write_text(seed if name == selected else "value = 1\n")
    return root


@pytest.fixture(scope="module")
def clean(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, Any]]:
    root = _tree(tmp_path_factory.mktemp("locked-bandit"))
    assert GATE.run_scan(root) == 0
    status = json.loads((root / GATE.STATUS).read_text())
    assert status["scanner_exit"] == 0
    return root, json.loads((root / GATE.REPORT).read_text())


def test_real_clean_report_covers_exact_four_roots(clean: tuple[Path, dict[str, Any]]) -> None:
    root, report = clean
    assert set(report["metrics"]) == {"_totals", *(f"{p}/seed.py" for p in GATE.ROOTS)}
    assert report["errors"] == report["results"] == []
    assert set(GATE.input_inventory(root)) == {f"{p}/seed.py" for p in GATE.ROOTS}
    status = json.loads((root / GATE.STATUS).read_text())
    assert status["command"][2:] == [
        "bandit",
        "-r",
        "plugins/",
        "scripts/",
        "tests/",
        "tools/",
        "-ll",
        "-f",
        "json",
        "-o",
        GATE.REPORT,
    ]


def test_low_only_policy_still_passes(tmp_path: Path) -> None:
    root = _tree(tmp_path, "import random\nvalue = random.random()\n")
    assert GATE.run_scan(root) == 0
    report = json.loads((root / GATE.REPORT).read_text())
    assert report["metrics"]["_totals"]["SEVERITY.LOW"] > 0
    assert report["results"] == []


@pytest.mark.parametrize("root_name", ["plugins", "scripts", "tests", "tools"])
@pytest.mark.parametrize(
    ("seed", "rule", "confidence"),
    [
        ('exec("value = 1")\n', "B102", "HIGH"),
        ('import os\nos.chmod("fixture", 0o777)\n', "B103", "HIGH"),
        ('path = "/tmp/predictable"\n', "B108", "MEDIUM"),
        ('import yaml\nyaml.load("value: 1", Loader=yaml.Loader)\n', "B506", "HIGH"),
        ('query = "SELECT * FROM users WHERE name = %s" % name\n', "B608", "LOW"),
    ],
)
def test_unannotated_policy_seeds_fail_at_every_root(
    tmp_path: Path, root_name: str, seed: str, rule: str, confidence: str
) -> None:
    root = _tree(tmp_path, seed, root_name)
    assert GATE.run_scan(root) == 1
    report = json.loads((root / GATE.REPORT).read_text())
    assert any(
        row["test_id"] == rule
        and row["issue_confidence"] == confidence
        and row["filename"] == f"{root_name}/seed.py"
        for row in report["results"]
    )
    assert json.loads((root / GATE.STATUS).read_text())["scanner_exit"] == 1
    assert (root / GATE.LOG).is_file()


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "malformed",
        "stale",
        "future",
        "errors",
        "missing-field",
        "missing-file",
        "extra-file",
        "bad-total",
        "bad-metric",
        "missing-metric",
        "missing-results",
        "hidden-finding",
        "bad-result",
        "internal-error",
        "execution-exit",
        "startup",
        "changed-input",
    ],
)
def test_failed_or_incomplete_scanner_never_reuses_clean_evidence(
    tmp_path: Path, clean: tuple[Path, dict[str, Any]], monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    root = _tree(tmp_path)
    report = copy.deepcopy(clean[1])
    report["generated_at"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    (root / GATE.REPORT).write_text(json.dumps(report))  # stale clean output must be deleted

    def scanner(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        assert not (root / GATE.REPORT).exists()
        assert command == [
            GATE.sys.executable,
            "-m",
            "bandit",
            "-r",
            "plugins/",
            "scripts/",
            "tests/",
            "tools/",
            "-ll",
            "-f",
            "json",
            "-o",
            GATE.REPORT,
        ]
        if fault == "startup":
            raise FileNotFoundError("scanner unavailable")
        if fault == "missing":
            return subprocess.CompletedProcess(command, 0)
        if fault in {"stale", "future"}:
            delta = -timedelta(days=1) if fault == "stale" else timedelta(days=1)
            report["generated_at"] = (datetime.now(UTC) + delta).strftime("%Y-%m-%dT%H:%M:%SZ")
        if fault == "errors":
            report["errors"] = [{"filename": "tools/seed.py", "reason": "syntax error"}]
        if fault == "missing-field":
            del report["errors"]
        if fault == "missing-file":
            del report["metrics"]["tools/seed.py"]
        if fault == "extra-file":
            report["metrics"]["extra.py"] = report["metrics"]["tools/seed.py"]
        if fault == "bad-total":
            report["metrics"]["_totals"]["loc"] += 1
        if fault == "bad-metric":
            report["metrics"]["tools/seed.py"]["loc"] = True
        if fault == "missing-metric":
            del report["metrics"]["tools/seed.py"]["loc"]
        if fault == "missing-results":
            del report["results"]
        if fault == "hidden-finding":
            report["metrics"]["tools/seed.py"]["SEVERITY.MEDIUM"] += 1
            report["metrics"]["_totals"]["SEVERITY.MEDIUM"] += 1
        if fault == "bad-result":
            report["results"] = [{}]
        if fault == "internal-error":
            kwargs["stdout"].write("[manager] ERROR internal scanner failure\n")
        if fault == "changed-input":
            (root / "tools/seed.py").write_text("changed = 2\n")
        (root / GATE.REPORT).write_text("{" if fault == "malformed" else json.dumps(report))
        return subprocess.CompletedProcess(command, 2 if fault == "execution-exit" else 0)

    monkeypatch.setattr(GATE.subprocess, "run", scanner)
    assert GATE.run_scan(root) == 1
    status = json.loads((root / GATE.STATUS).read_text())
    assert status["ok"] is False and status["error"]
    assert (root / GATE.LOG).is_file()
    assert (root / GATE.REPORT).exists() == (fault not in {"missing", "startup"})


def test_real_scanner_syntax_errors_fail_with_retained_artifacts(tmp_path: Path) -> None:
    root = _tree(tmp_path, "def broken(:\n", "tools")
    assert GATE.run_scan(root) == 1
    assert json.loads((root / GATE.REPORT).read_text())["errors"]
    assert (root / GATE.LOG).is_file()


def test_missing_root_is_not_a_clean_scan(tmp_path: Path) -> None:
    assert GATE.run_scan(tmp_path) == 1
    assert "missing scan root" in json.loads((tmp_path / GATE.STATUS).read_text())["error"]


def test_inventory_includes_default_python_extension_only(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    (root / "tools/README.md").write_text("documentation")
    (root / "tools/nested").mkdir()
    (root / "tools/nested/extra.py").write_text("value = 2\n")
    assert set(GATE.input_inventory(root)) == {
        *(f"{p}/seed.py" for p in GATE.ROOTS),
        "tools/nested/extra.py",
    }
