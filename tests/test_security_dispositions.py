"""Keep the eight reviewed test dispositions visible to the actual locked scanner."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITES = {
    "tests/test_audit_store.py": Counter({"B103": 5}),
    "tests/test_lifecycle_regression_harness.py": Counter({"B506": 1}),
    "tests/test_handoff_envelope_maturity.py": Counter({"B108": 1}),
    "plugins/agent-launcher/tests/test_launcher_contract.py": Counter({"B102": 1}),
}


def test_reviewed_annotations_are_exact_and_ignore_nosec_exposes_each() -> None:
    expected: set[tuple[str, int, str]] = set()
    for path, counts in SITES.items():
        annotations = [
            (n, match.group(1))
            for n, line in enumerate((ROOT / path).read_text().splitlines(), 1)
            if (match := re.search(r"# nosec (B\d{3}) - .+", line))
        ]
        assert Counter(rule for _, rule in annotations) == counts
        expected.update((path, line, rule) for line, rule in annotations)
    for ignore in (False, True):
        command = [sys.executable, "-m", "bandit", *SITES, "-ll", "-f", "json"]
        if ignore:
            command.append("--ignore-nosec")
        process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
        report = json.loads(process.stdout)
        assert report["errors"] == []
        findings = {
            (row["filename"].removeprefix("./"), row["line_number"], row["test_id"])
            for row in report["results"]
        }
        assert findings == (expected if ignore else set())
        assert process.returncode == int(ignore)


def test_private_temporary_fixture_cleanup(tmp_path: Path) -> None:
    assert tmp_path.stat().st_mode & 0o777 == 0o700
    with tempfile.TemporaryDirectory(dir=tmp_path) as name:
        target = Path(name)
        assert target.resolve().is_relative_to(tmp_path.resolve())
        assert target.stat().st_mode & 0o777 == 0o700
    assert not target.exists()
