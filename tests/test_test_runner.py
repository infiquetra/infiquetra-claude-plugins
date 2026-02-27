"""Unit tests for test_runner.py."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
import sys

# Add plugin skills directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "test-suite" / "skills" / "run-quality-checks" / "scripts"))

from test_runner import QualityCheckRunner, CheckResult


class TestTestRunner:
    """Test QualityCheckRunner class."""

    def test_init_default_values(self):
        """Test QualityCheckRunner initialization with defaults."""
        runner = QualityCheckRunner()

        assert runner.coverage_threshold == 80
        assert runner.test_dir == Path("tests")
        assert runner.source_dir == Path("src")
        assert runner.fail_fast is False
        assert runner.verbose is False

    def test_init_custom_values(self):
        """Test QualityCheckRunner initialization with custom values."""
        runner = QualityCheckRunner(
            coverage_threshold=85,
            test_dir="test",
            source_dir="source",
            fail_fast=True,
            verbose=True,
        )

        assert runner.coverage_threshold == 85
        assert runner.test_dir == Path("test")
        assert runner.source_dir == Path("source")
        assert runner.fail_fast is True
        assert runner.verbose is True

    def test_run_check_success(self, mock_subprocess_run):
        """Test successful check execution."""
        mock_subprocess_run.return_value.returncode = 0
        mock_subprocess_run.return_value.stdout = "All tests passed"
        mock_subprocess_run.return_value.stderr = ""

        runner = QualityCheckRunner()
        result = runner.run_check("pytest", ["pytest", "tests/"])

        assert result.name == "pytest"
        assert result.status == "passed"
        assert result.duration > 0
        assert "All tests passed" in result.output

    def test_run_check_failure(self, mock_subprocess_run):
        """Test failed check execution."""
        mock_subprocess_run.return_value.returncode = 1
        mock_subprocess_run.return_value.stdout = ""
        mock_subprocess_run.return_value.stderr = "Test failed"

        runner = QualityCheckRunner()
        result = runner.run_check("pytest", ["pytest", "tests/"])

        assert result.name == "pytest"
        assert result.status == "failed"
        assert "Test failed" in result.output

    def test_run_pytest_parses_coverage(self, mock_subprocess_run):
        """Test pytest execution parses coverage correctly."""
        mock_subprocess_run.return_value.returncode = 0
        mock_subprocess_run.return_value.stdout = """
        ====== test session starts ======
        collected 10 items

        tests/test_example.py::test_one PASSED
        tests/test_example.py::test_two PASSED

        ---------- coverage: platform linux ----------
        Name                 Stmts   Miss  Cover
        ----------------------------------------
        src/module.py           100     15    85%
        ----------------------------------------
        TOTAL                   100     15    85%
        """
        mock_subprocess_run.return_value.stderr = ""

        runner = QualityCheckRunner(coverage_threshold=80)
        result = runner.run_pytest()

        assert result.status == "passed"
        assert result.details["coverage"] == 85.0
        assert result.details["threshold_met"] is True

    def test_run_pytest_below_threshold(self, mock_subprocess_run):
        """Test pytest fails when coverage below threshold."""
        mock_subprocess_run.return_value.returncode = 0
        mock_subprocess_run.return_value.stdout = """
        TOTAL                   100     30    70%
        """
        mock_subprocess_run.return_value.stderr = ""

        runner = QualityCheckRunner(coverage_threshold=80)
        result = runner.run_pytest()

        assert result.status == "failed"
        assert result.details["coverage"] == 70.0
        assert result.details["threshold_met"] is False

    def test_generate_json_output(self):
        """Test JSON output generation."""
        runner = QualityCheckRunner()

        results = [
            CheckResult(
                name="pytest",
                status="passed",
                duration=12.3,
                output="All tests passed",
                details={"tests_passed": 45, "tests_failed": 0, "coverage": 82.0},
            ),
            CheckResult(
                name="ruff",
                status="passed",
                duration=1.8,
                output="No issues",
                details={"issues": 0},
            ),
        ]

        json_output = runner.generate_json_output(results)

        assert json_output["summary"]["total_checks"] == 2
        assert json_output["summary"]["passed"] == 2
        assert json_output["summary"]["failed"] == 0
        assert json_output["checks"]["pytest"]["status"] == "passed"
        assert json_output["checks"]["pytest"]["coverage"] == 82.0
        assert json_output["checks"]["ruff"]["issues"] == 0


class TestCheckResult:
    """Test CheckResult dataclass."""

    def test_check_result_creation(self):
        """Test CheckResult creation."""
        result = CheckResult(
            name="test",
            status="passed",
            duration=1.5,
            output="output",
            details={"key": "value"},
        )

        assert result.name == "test"
        assert result.status == "passed"
        assert result.duration == 1.5
        assert result.output == "output"
        assert result.details == {"key": "value"}
