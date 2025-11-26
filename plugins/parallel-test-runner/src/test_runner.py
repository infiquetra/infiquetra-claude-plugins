#!/usr/bin/env python3
"""
Parallel Test Runner

Runs parallel quality checks for Python projects.
"""

import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

# Color codes
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
BOLD = "\033[1m"
RESET = "\033[0m"


@dataclass
class CheckResult:
    """Result of a single check."""

    name: str
    status: str  # "passed" or "failed"
    duration: float
    output: str
    details: dict[str, Any]


class QualityCheckRunner:
    """Runs parallel quality checks."""

    def __init__(
        self,
        coverage_threshold: int = 80,
        test_dir: str = "tests",
        source_dir: str = "src",
        fail_fast: bool = False,
        verbose: bool = False,
        timeout: int = 300,
    ):
        self.coverage_threshold = coverage_threshold
        self.test_dir = Path(test_dir)
        self.source_dir = Path(source_dir)
        self.fail_fast = fail_fast
        self.verbose = verbose
        self.timeout = timeout
        self.results: list[CheckResult] = []

    def run_check(self, name: str, command: list[str]) -> CheckResult:
        """Run a single check command."""
        start_time = time.time()

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            duration = time.time() - start_time

            status = "passed" if result.returncode == 0 else "failed"
            output = result.stdout + result.stderr

            return CheckResult(
                name=name,
                status=status,
                duration=duration,
                output=output,
                details={"returncode": result.returncode},
            )

        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            return CheckResult(
                name=name,
                status="failed",
                duration=duration,
                output=f"Timeout after {self.timeout}s",
                details={"error": "timeout"},
            )
        except Exception as e:
            duration = time.time() - start_time
            return CheckResult(
                name=name,
                status="failed",
                duration=duration,
                output=str(e),
                details={"error": str(e)},
            )

    def run_pytest(self) -> CheckResult:
        """Run pytest with coverage."""
        command = [
            "pytest",
            str(self.test_dir),
            f"--cov={self.source_dir}",
            "--cov-report=html",
            "--cov-report=term",
            "--cov-report=json",
            "-v",
        ]

        result = self.run_check("pytest", command)

        # Parse coverage from output
        coverage = 0.0
        for line in result.output.split("\n"):
            if "TOTAL" in line and "%" in line:
                parts = line.split()
                for part in parts:
                    if "%" in part:
                        coverage = float(part.replace("%", ""))
                        break

        # Parse test results
        tests_passed = 0
        tests_failed = 0
        for line in result.output.split("\n"):
            if " passed" in line:
                try:
                    tests_passed = int(line.split()[0])
                except (ValueError, IndexError):
                    pass
            if " failed" in line:
                try:
                    tests_failed = int(line.split()[0])
                except (ValueError, IndexError):
                    pass

        result.details.update(
            {
                "tests_passed": tests_passed,
                "tests_failed": tests_failed,
                "coverage": coverage,
                "threshold_met": coverage >= self.coverage_threshold,
            }
        )

        # Override status if coverage is below threshold
        if coverage < self.coverage_threshold:
            result.status = "failed"

        return result

    def run_ruff(self) -> CheckResult:
        """Run ruff linting."""
        command = ["ruff", "check", str(self.source_dir), str(self.test_dir)]
        result = self.run_check("ruff", command)

        # Count issues
        issues = 0
        for line in result.output.split("\n"):
            if line.strip() and not line.startswith("Found"):
                issues += 1

        result.details["issues"] = issues
        return result

    def run_mypy(self) -> CheckResult:
        """Run mypy type checking."""
        command = ["mypy", str(self.source_dir)]
        result = self.run_check("mypy", command)

        # Count errors
        errors = 0
        for line in result.output.split("\n"):
            if ": error:" in line:
                errors += 1

        result.details["errors"] = errors
        return result

    def run_bandit(self) -> CheckResult:
        """Run bandit security scanning."""
        command = [
            "bandit",
            "-r",
            str(self.source_dir),
            "-f",
            "json",
            "--skip",
            "B101",  # Skip assert_used for tests
        ]
        result = self.run_check("bandit", command)

        # Parse JSON output
        issues = 0
        high_severity = 0
        try:
            bandit_data = json.loads(result.output)
            issues = len(bandit_data.get("results", []))
            high_severity = sum(
                1 for r in bandit_data.get("results", []) if r.get("issue_severity") == "HIGH"
            )
        except json.JSONDecodeError:
            pass

        result.details.update({"issues": issues, "high_severity": high_severity})

        # Fail if high severity issues found
        if high_severity > 0:
            result.status = "failed"

        return result

    def run_all_checks(self) -> list[CheckResult]:
        """Run all checks in parallel."""
        print(f"\n{BLUE}Running checks in parallel...{RESET}\n")

        checks: list[tuple[str, Callable[[], CheckResult]]] = [
            ("pytest", self.run_pytest),
            ("ruff", self.run_ruff),
            ("mypy", self.run_mypy),
            ("bandit", self.run_bandit),
        ]

        results = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(check_func): name for name, check_func in checks}

            for i, future in enumerate(as_completed(futures), 1):
                name = futures[future]
                try:
                    result = future.result()
                    status_icon = f"{GREEN}✓{RESET}" if result.status == "passed" else f"{RED}✗{RESET}"
                    print(f"[{i}/4] {name:20s} {status_icon} ({result.duration:.1f}s)")
                    results.append(result)

                    if self.fail_fast and result.status == "failed":
                        print(f"\n{RED}Fail-fast mode: Stopping on first failure{RESET}")
                        executor.shutdown(wait=False, cancel_futures=True)
                        break

                except Exception as e:
                    print(f"[{i}/4] {name:20s} {RED}✗ Error: {e}{RESET}")

        return results

    def print_summary(self, results: list[CheckResult]) -> None:
        """Print summary of all results."""
        print(f"\n{'═' * 45}")
        print(f"{BOLD}Test Results Summary{RESET}")
        print(f"{'═' * 45}\n")

        for result in results:
            status_icon = f"{GREEN}✓{RESET}" if result.status == "passed" else f"{RED}✗{RESET}"
            print(f"{status_icon} {result.name:12s}", end="")

            if result.name == "pytest":
                tests_passed = result.details.get("tests_passed", 0)
                tests_failed = result.details.get("tests_failed", 0)
                coverage = result.details.get("coverage", 0)
                print(f" {tests_passed}/{tests_passed + tests_failed} tests passed   Coverage: {coverage}%")

                if tests_failed > 0 and self.verbose:
                    print(f"  {YELLOW}Failed tests:{RESET}")
                    # Parse failed test names from output
                    for line in result.output.split("\n"):
                        if "FAILED" in line:
                            print(f"    - {line.split('FAILED')[1].strip()}")

                if coverage < self.coverage_threshold:
                    print(f"  {RED}Coverage below threshold ({self.coverage_threshold}%){RESET}")

            elif result.name == "ruff":
                issues = result.details.get("issues", 0)
                print(f" {issues} issues found")
                if issues > 0 and self.verbose:
                    print(f"  {YELLOW}Issues:{RESET}")
                    for line in result.output.split("\n")[:10]:  # Show first 10
                        if line.strip():
                            print(f"    {line}")

            elif result.name == "mypy":
                errors = result.details.get("errors", 0)
                print(f" {errors} type errors")
                if errors > 0 and self.verbose:
                    print(f"  {YELLOW}Errors:{RESET}")
                    for line in result.output.split("\n"):
                        if ": error:" in line:
                            print(f"    {line}")

            elif result.name == "bandit":
                issues = result.details.get("issues", 0)
                high_severity = result.details.get("high_severity", 0)
                print(f" {issues} security issues", end="")
                if high_severity > 0:
                    print(f" ({RED}{high_severity} high severity{RESET})")
                else:
                    print()

        # Overall summary
        total_duration = sum(r.duration for r in results)
        passed = sum(1 for r in results if r.status == "passed")
        failed = len(results) - passed

        print(f"\n{'═' * 45}")
        if failed == 0:
            print(f"{GREEN}All checks passed!{RESET} ({total_duration:.1f}s total)")
        else:
            print(f"{RED}{failed} check(s) failed{RESET} ({total_duration:.1f}s total)")

        # Report location
        if any(r.name == "pytest" and r.status != "failed" for r in results):
            print(f"\n{BLUE}Reports generated:{RESET}")
            print("   - HTML: htmlcov/index.html")
            print("   - Coverage: .coverage")

    def generate_json_output(self, results: list[CheckResult]) -> dict[str, Any]:
        """Generate JSON output for CI/CD integration."""
        return {
            "summary": {
                "total_checks": len(results),
                "passed": sum(1 for r in results if r.status == "passed"),
                "failed": sum(1 for r in results if r.status == "failed"),
                "duration": sum(r.duration for r in results),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
            "checks": {
                r.name: {
                    "status": r.status,
                    "duration": r.duration,
                    **r.details,
                }
                for r in results
            },
        }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Parallel Test Runner")
    parser.add_argument(
        "--coverage",
        type=int,
        default=80,
        help="Minimum coverage threshold (default: 80)",
    )
    parser.add_argument(
        "--test-dir",
        default="tests",
        help="Test directory (default: tests)",
    )
    parser.add_argument(
        "--source-dir",
        default="src",
        help="Source directory (default: src)",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop on first failure",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Timeout per check in seconds (default: 300)",
    )
    parser.add_argument(
        "--output",
        choices=["console", "json"],
        default="console",
        help="Output format (default: console)",
    )
    parser.add_argument(
        "--output-file",
        help="Output file for JSON format",
    )
    parser.add_argument(
        "--checks",
        help="Comma-separated list of checks to run (pytest,ruff,mypy,bandit)",
    )

    args = parser.parse_args()

    # Print header
    print(f"\n{BOLD}Parallel Test Runner{RESET}")
    print(f"{'═' * 45}")

    print(f"\n{BLUE}Configuration:{RESET}")
    print(f"   Coverage threshold: {args.coverage}%")
    print(f"   Test directory: {args.test_dir}/")
    print(f"   Source directory: {args.source_dir}/")

    # Run tests
    runner = QualityCheckRunner(
        coverage_threshold=args.coverage,
        test_dir=args.test_dir,
        source_dir=args.source_dir,
        fail_fast=args.fail_fast,
        verbose=args.verbose,
        timeout=args.timeout,
    )

    results = runner.run_all_checks()

    # Output results
    if args.output == "console":
        runner.print_summary(results)
    elif args.output == "json":
        json_output = runner.generate_json_output(results)
        if args.output_file:
            with open(args.output_file, "w") as f:
                json.dump(json_output, f, indent=2)
            print(f"\n{GREEN}✓ JSON output written to {args.output_file}{RESET}")
        else:
            print(json.dumps(json_output, indent=2))

    # Exit with appropriate code
    failed = sum(1 for r in results if r.status == "failed")
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
