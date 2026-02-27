#!/usr/bin/env python3
"""
SDK Security Audit Script

Performs comprehensive security review of SDK projects including dependency
scanning, OWASP checklist validation, and security scorecard generation.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional


class SecurityAuditor:
    """Main security auditor class."""

    def __init__(self, project_path: Path, language: Optional[str] = None):
        self.project_path = project_path
        self.language = language or self._detect_language()
        self.findings: List[Dict[str, Any]] = []
        self.score = 100

    def _detect_language(self) -> str:
        """Detect project language from files."""
        if (self.project_path / "pyproject.toml").exists():
            return "python"
        elif list(self.project_path.glob("**/*.csproj")):
            return "dotnet"
        elif (self.project_path / "package.json").exists():
            return "typescript"
        else:
            raise ValueError("Could not detect project language")

    def run_audit(self) -> Dict[str, Any]:
        """Run complete security audit."""
        print(f"🔍 Running security audit for {self.language.upper()} project...")

        # Run language-specific checks
        if self.language == "python":
            self._audit_python()
        elif self.language == "dotnet":
            self._audit_dotnet()
        elif self.language == "typescript":
            self._audit_typescript()

        # Run common checks
        self._check_secrets()
        self._check_owasp_compliance()

        return self._generate_report()

    def _audit_python(self) -> None:
        """Audit Python project."""
        print("  Scanning Python dependencies...")

        # Check if safety is installed
        try:
            result = subprocess.run(
                ["safety", "check", "--json"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                vulnerabilities = json.loads(result.stdout) if result.stdout else []
                for vuln in vulnerabilities:
                    self.findings.append({
                        "type": "vulnerable_dependency",
                        "severity": "high",
                        "package": vuln.get("package"),
                        "version": vuln.get("installed_version"),
                        "cve": vuln.get("id"),
                        "description": vuln.get("advisory"),
                    })
                    self.score -= 10
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print("  ⚠️  safety not installed or check failed")

        # Check for bandit (security linter)
        try:
            result = subprocess.run(
                ["bandit", "-r", "src/", "-f", "json"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.stdout:
                bandit_results = json.loads(result.stdout)
                for issue in bandit_results.get("results", []):
                    self.findings.append({
                        "type": "code_issue",
                        "severity": issue.get("issue_severity", "").lower(),
                        "file": issue.get("filename"),
                        "line": issue.get("line_number"),
                        "description": issue.get("issue_text"),
                        "cwe": issue.get("issue_cwe", {}).get("id"),
                    })
                    if issue.get("issue_severity") == "HIGH":
                        self.score -= 5
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print("  ⚠️  bandit not installed or check failed")

    def _audit_dotnet(self) -> None:
        """Audit .NET project."""
        print("  Scanning .NET dependencies...")

        try:
            result = subprocess.run(
                ["dotnet", "list", "package", "--vulnerable", "--include-transitive"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if "has the following vulnerable packages" in result.stdout:
                self.findings.append({
                    "type": "vulnerable_dependency",
                    "severity": "high",
                    "description": "Vulnerable .NET packages detected. Run 'dotnet list package --vulnerable' for details.",
                })
                self.score -= 10
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print("  ⚠️  dotnet CLI not available")

    def _audit_typescript(self) -> None:
        """Audit TypeScript project."""
        print("  Scanning npm dependencies...")

        try:
            result = subprocess.run(
                ["npm", "audit", "--json"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.stdout:
                audit_results = json.loads(result.stdout)
                vulnerabilities = audit_results.get("vulnerabilities", {})
                for pkg, vuln_info in vulnerabilities.items():
                    severity = vuln_info.get("severity", "low")
                    self.findings.append({
                        "type": "vulnerable_dependency",
                        "severity": severity,
                        "package": pkg,
                        "description": vuln_info.get("via", [{}])[0].get("title", ""),
                    })
                    if severity in ["critical", "high"]:
                        self.score -= 10
                    elif severity == "medium":
                        self.score -= 5
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
            print("  ⚠️  npm audit failed")

    def _check_secrets(self) -> None:
        """Check for hardcoded secrets."""
        print("  Checking for hardcoded secrets...")

        secret_patterns = [
            "api_key",
            "api-key",
            "apikey",
            "password",
            "secret",
            "token",
            "bearer",
        ]

        for pattern in ["**/*.py", "**/*.cs", "**/*.ts", "**/*.js"]:
            for file in self.project_path.glob(pattern):
                if "node_modules" in str(file) or "venv" in str(file):
                    continue

                try:
                    content = file.read_text().lower()
                    for secret_pattern in secret_patterns:
                        if f'"{secret_pattern}"' in content or f"'{secret_pattern}'" in content:
                            # Potential hardcoded secret (simplified check)
                            if "example" not in str(file) and "test" not in str(file):
                                self.findings.append({
                                    "type": "potential_secret",
                                    "severity": "medium",
                                    "file": str(file.relative_to(self.project_path)),
                                    "description": f"Potential hardcoded secret pattern: {secret_pattern}",
                                })
                except Exception:
                    continue

    def _check_owasp_compliance(self) -> None:
        """Check OWASP compliance (simplified)."""
        print("  Checking OWASP compliance...")

        # Check for SECURITY.md
        if not (self.project_path / "SECURITY.md").exists():
            self.findings.append({
                "type": "missing_security_policy",
                "severity": "low",
                "description": "Missing SECURITY.md file for vulnerability reporting",
            })
            self.score -= 5

        # Check for proper README
        readme = self.project_path / "README.md"
        if readme.exists():
            content = readme.read_text().lower()
            if "security" not in content:
                self.findings.append({
                    "type": "missing_security_docs",
                    "severity": "low",
                    "description": "README.md missing security section",
                })
                self.score -= 2

    def _generate_report(self) -> Dict[str, Any]:
        """Generate security audit report."""
        severity_counts = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
        }

        for finding in self.findings:
            severity = finding.get("severity", "low")
            if severity in severity_counts:
                severity_counts[severity] += 1

        return {
            "project_path": str(self.project_path),
            "language": self.language,
            "score": max(0, self.score),
            "grade": self._calculate_grade(self.score),
            "severity_counts": severity_counts,
            "total_findings": len(self.findings),
            "findings": self.findings,
        }

    def _calculate_grade(self, score: int) -> str:
        """Calculate letter grade from score."""
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"


def print_report(report: Dict[str, Any], format: str = "text") -> None:
    """Print security audit report."""
    if format == "json":
        print(json.dumps(report, indent=2))
        return

    print("\n" + "=" * 60)
    print("Infiquetra SDK Security Audit Report")
    print("=" * 60)
    print(f"Project: {report['project_path']}")
    print(f"Language: {report['language'].upper()}")
    print(f"Score: {report['score']}/100 ({report['grade']})")
    print()

    print("Vulnerability Summary")
    print("-" * 60)
    for severity, count in report["severity_counts"].items():
        icon = "🔴" if severity in ["critical", "high"] else "🟡" if severity == "medium" else "🟢"
        print(f"{icon} {severity.capitalize()}: {count}")
    print()

    if report["findings"]:
        print("Findings")
        print("-" * 60)
        for i, finding in enumerate(report["findings"][:10], 1):  # Show first 10
            print(f"{i}. [{finding['severity'].upper()}] {finding.get('description', 'No description')}")
            if "file" in finding:
                print(f"   File: {finding['file']}")
            if "package" in finding:
                print(f"   Package: {finding['package']}")
            print()

        if len(report["findings"]) > 10:
            print(f"... and {len(report['findings']) - 10} more findings")
    else:
        print("✅ No security issues found!")

    print()
    print("Recommendations")
    print("-" * 60)
    if report["score"] < 70:
        print("- Address critical and high severity findings immediately")
        print("- Update vulnerable dependencies")
        print("- Add security documentation (SECURITY.md)")
    elif report["score"] < 90:
        print("- Address remaining security findings")
        print("- Add automated security scanning to CI/CD")
    else:
        print("- Maintain current security practices")
        print("- Schedule regular security reviews")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="SDK Security Audit")
    parser.add_argument(
        "--project-path",
        type=Path,
        default=Path.cwd(),
        help="Path to SDK project"
    )
    parser.add_argument(
        "--language",
        choices=["python", "dotnet", "typescript"],
        help="Project language (auto-detected if not specified)"
    )
    parser.add_argument(
        "--report-format",
        choices=["text", "json"],
        default="text",
        help="Report output format"
    )
    parser.add_argument(
        "--fail-on",
        help="Comma-separated severities to fail on (e.g., 'critical,high')"
    )

    args = parser.parse_args()

    try:
        auditor = SecurityAuditor(args.project_path, args.language)
        report = auditor.run_audit()
        print_report(report, args.report_format)

        # Check if should fail
        if args.fail_on:
            fail_severities = [s.strip() for s in args.fail_on.split(",")]
            for severity in fail_severities:
                if report["severity_counts"].get(severity, 0) > 0:
                    print(f"\n❌ Build failed due to {severity} severity findings")
                    sys.exit(1)

        sys.exit(0)

    except Exception as e:
        print(f"❌ Security audit failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
