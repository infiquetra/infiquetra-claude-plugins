#!/usr/bin/env python3
"""Revision-pinned cross-runtime Outcome acceptance harness (#605).

Drives the two installed Saga runtimes — Claude (`infiquetra-claude-plugins`) and Codex
(`infiquetra-codex-plugins`) — as subprocesses against temporary target Git clones and proves
the cross-runtime coordination contract end to end: canonical discovery in both directions,
protected bounded handoff in both directions plus its negative matrix, exactly one dispatch
side effect under a real two-process race, native Codex acknowledgement, shared settlement,
cross-clone read-only reconstruction, compatibility and legacy-import refusal, teardown, and a
clean fleet-doctor result (plan `docs/plans/2026-07-15-cross-runtime-outcome-acceptance-plan.md`,
R1-R10).

The harness never repairs production (KTD4), never reads or copies a real runtime cache,
credential, transcript, or protected receipt (R2), and emits one closed, privacy-safe evidence
bundle (R10) bound to the exact merged source and installed package identities (KTD1).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

SCHEMA_VERSION = "lease-safe-runtime-continuity/cross-runtime-acceptance.v1"

# R10: environment-variable NAME allowlist. The bundle records which of these names were set for
# child processes — never values, never names outside this closed list.
ENV_NAME_ALLOWLIST: tuple[str, ...] = (
    "HOME",
    "PATH",
    "PYTHONPATH",
    "INFIQUETRA_FLEET_STATE_DIR",
    "XDG_STATE_HOME",
    "GIT_AUTHOR_NAME",
    "GIT_AUTHOR_EMAIL",
    "GIT_COMMITTER_NAME",
    "GIT_COMMITTER_EMAIL",
    "GIT_CONFIG_GLOBAL",
    "GIT_CONFIG_NOSYSTEM",
    "TMPDIR",
)

# R10: values with these shapes may never appear anywhere in the evidence bundle.
_SECRET_SHAPES: tuple[re.Pattern[str], ...] = (
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),  # GitHub token families
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),  # provider API keys
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS access key ids
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)\b(authorization|bearer)\b\s*[:=]\s*\S+"),
)

_TIMEOUT_S = 120


class HarnessError(Exception):
    """A HALT: the run stops before (further) scenario effects; the bundle records the code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.detail = message


# --------------------------------------------------------------------------- primitives


def _run(
    argv: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: int = _TIMEOUT_S,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 — fixed argv, shell never used
        argv,
        cwd=str(cwd) if cwd else None,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _bounded(text: str, limit: int = 400) -> str:
    """A bounded, single-line summary — never raw stdout/stderr (R10)."""
    flat = " ".join(text.split())
    return flat[:limit]


# --------------------------------------------------------------------------- R10 privacy


def scrub_check(value: Any, *, home: str | None = None) -> list[str]:
    """Return privacy violations found anywhere inside ``value`` (empty = clean).

    Rejects absolute filesystem paths, the invoking user's home path, and secret-shaped
    strings. Digests, versions, scenario ids, and bounded summaries pass.
    """
    home = home or str(Path.home())
    violations: list[str] = []

    def walk(node: Any, crumb: str) -> None:
        if isinstance(node, dict):
            for key, child in node.items():
                walk(child, f"{crumb}.{key}")
            return
        if isinstance(node, list):
            for index, child in enumerate(node):
                walk(child, f"{crumb}[{index}]")
            return
        if not isinstance(node, str):
            return
        if home in node:
            violations.append(f"{crumb}: contains the home directory path")
        elif re.search(r"(?<![\w/])/(?:Users|home|private|var|tmp|opt|etc)/", node):
            violations.append(f"{crumb}: contains an absolute filesystem path")
        for shape in _SECRET_SHAPES:
            if shape.search(node):
                violations.append(f"{crumb}: matches a secret shape")
                break

    walk(value, "$")
    return violations


def assert_privacy(bundle: dict[str, Any]) -> None:
    violations = scrub_check(bundle)
    if violations:
        raise HarnessError(
            "evidence-privacy",
            f"{len(violations)} privacy violation(s); first: {violations[0]}",
        )


def atomic_write_json(path: Path, payload: dict[str, Any]) -> str:
    """Write the bundle atomically (tmp + rename) and return its SHA-256."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile(
        "w", dir=str(path.parent), suffix=".tmp", delete=False, encoding="utf-8"
    ) as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
        tmp_name = handle.name
    os.replace(tmp_name, path)
    return _sha256_text(text)


# --------------------------------------------------------------------------- R1 pinning


@dataclass(frozen=True)
class RuntimePin:
    """One runtime under test: its clean checkout, exact SHA, and expected versions."""

    name: str  # "claude" | "codex"
    repo: Path
    sha: str
    saga_version: str
    fleet_core_version: str
    manifest_dir: str  # ".claude-plugin" | ".codex-plugin"


def require_clean_pinned(pin: RuntimePin) -> dict[str, Any]:
    """R1: the checkout must be clean and at exactly the pinned SHA; versions must match."""
    if not (pin.repo / ".git").exists():
        raise HarnessError("pin-not-a-repo", f"{pin.name}: repo root has no .git")
    status = _run(["git", "status", "--porcelain"], cwd=pin.repo)
    if status.returncode != 0 or status.stdout.strip():
        raise HarnessError("pin-dirty", f"{pin.name}: checkout is not clean")
    head = _run(["git", "rev-parse", "HEAD"], cwd=pin.repo).stdout.strip()
    if head != pin.sha:
        raise HarnessError("pin-sha", f"{pin.name}: HEAD {head[:12]} != pinned {pin.sha[:12]}")
    versions: dict[str, str] = {}
    for plugin, expected in (("saga", pin.saga_version), ("fleet-core", pin.fleet_core_version)):
        manifest = pin.repo / "plugins" / plugin / pin.manifest_dir / "plugin.json"
        if not manifest.exists():
            raise HarnessError("pin-manifest", f"{pin.name}: missing {plugin} manifest")
        observed = json.loads(manifest.read_text(encoding="utf-8"))["version"]
        if observed != expected:
            raise HarnessError(
                "pin-version",
                f"{pin.name}/{plugin}: manifest {observed} != expected {expected}",
            )
        versions[plugin] = observed
    return {"sha": head, "versions": versions}


def contract_digests(claude: RuntimePin, codex: RuntimePin) -> dict[str, str]:
    """Bind the shared contract surfaces: compat copies, and the codex port manifest.

    The two ``outcome_compat.py`` copies must be byte-identical after normalizing the single
    allowed divergence (``RUNTIME_LABEL``); their digests plus the codex target inventory are
    recorded in the bundle.
    """
    claude_compat = claude.repo / "plugins/saga/scripts/outcome_compat.py"
    codex_compat = codex.repo / "plugins/saga/scripts/outcome_compat.py"
    claude_text = claude_compat.read_text(encoding="utf-8")
    codex_text = codex_compat.read_text(encoding="utf-8")
    normalized = codex_text.replace('RUNTIME_LABEL = "codex"', 'RUNTIME_LABEL = "claude"', 1)
    if normalized != claude_text:
        raise HarnessError(
            "port-digest",
            "outcome_compat.py copies diverge beyond RUNTIME_LABEL",
        )
    inventory = codex.repo / "docs/validation/saga-family-target-inventory.json"
    return {
        "claude_outcome_compat_sha256": _sha256_text(claude_text),
        "codex_outcome_compat_sha256": _sha256_text(codex_text),
        "codex_target_inventory_sha256": _sha256_file(inventory),
    }


# --------------------------------------------------------------------------- R1 installation


@dataclass
class InstalledRuntime:
    """An isolated installation of one runtime: staged package + hermetic home."""

    pin: RuntimePin
    install_root: Path  # staged plugin package (the "installed" copy the harness drives)
    home: Path  # isolated HOME for every child process of this runtime
    identity: dict[str, Any] = field(default_factory=dict)

    @property
    def outcome_cli(self) -> Path:
        return self.install_root / "plugins/saga/scripts/outcome.py"

    def env(self, *, fleet_state_dir: Path, repo_root: Path | None = None) -> dict[str, str]:
        """Hermetic child environment: isolated HOME, pinned fleet root, no ambient state."""
        env = {
            "HOME": str(self.home),
            "PATH": os.environ.get("PATH", ""),
            "INFIQUETRA_FLEET_STATE_DIR": str(fleet_state_dir),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": str(self.home / ".gitconfig"),
            "GIT_AUTHOR_NAME": "acceptance-harness",
            "GIT_AUTHOR_EMAIL": "acceptance@invalid.example",
            "GIT_COMMITTER_NAME": "acceptance-harness",
            "GIT_COMMITTER_EMAIL": "acceptance@invalid.example",
        }
        if repo_root is not None:
            env["PWD"] = str(repo_root)
        return env

    def outcome(
        self,
        *args: str,
        repo_root: Path,
        fleet_state_dir: Path,
        timeout: int = _TIMEOUT_S,
    ) -> subprocess.CompletedProcess[str]:
        return _run(
            [sys.executable, str(self.outcome_cli), "--repo-root", str(repo_root), *args],
            cwd=self.install_root,
            env=self.env(fleet_state_dir=fleet_state_dir, repo_root=repo_root),
            timeout=timeout,
        )


def install_isolated(pin: RuntimePin, workdir: Path) -> InstalledRuntime:
    """Stage the pinned plugin package into an isolated root and prove readback identity.

    The staged copy — not the source checkout — is what every scenario drives, so verdicts bind
    to installed-package identity rather than working-tree claims (KTD1). The readback probe
    re-reads versions from the installed manifests and imports the installed compat module for
    its runtime label and protocol version.
    """
    install_root = workdir / f"install-{pin.name}"
    home = workdir / f"home-{pin.name}"
    home.mkdir(parents=True)
    (home / ".gitconfig").write_text(
        "[user]\n\tname = acceptance-harness\n\temail = acceptance@invalid.example\n",
        encoding="utf-8",
    )
    for plugin in ("saga", "fleet-core"):
        source = pin.repo / "plugins" / plugin
        target = install_root / "plugins" / plugin
        shutil.copytree(source, target, symlinks=False)
    runtime = InstalledRuntime(pin=pin, install_root=install_root, home=home)

    readback: dict[str, Any] = {"versions": {}}
    for plugin in ("saga", "fleet-core"):
        manifest = install_root / "plugins" / plugin / pin.manifest_dir / "plugin.json"
        readback["versions"][plugin] = json.loads(manifest.read_text(encoding="utf-8"))["version"]
    probe = _run(
        [
            sys.executable,
            "-c",
            "import sys; sys.path.insert(0, sys.argv[1]); import outcome_compat as oc; "
            "print(oc.RUNTIME_LABEL); print(oc.PROTOCOL_VERSION)",
            str(install_root / "plugins/saga/scripts"),
        ],
        env=runtime.env(fleet_state_dir=home / "fleet"),
    )
    if probe.returncode != 0:
        raise HarnessError("install-readback", f"{pin.name}: compat probe failed")
    label, protocol = probe.stdout.split()
    expected_label = pin.name
    if label != expected_label:
        raise HarnessError(
            "install-readback",
            f"{pin.name}: installed RUNTIME_LABEL is {label!r}",
        )
    help_probe = _run(
        [sys.executable, str(runtime.outcome_cli), "--help"],
        env=runtime.env(fleet_state_dir=home / "fleet"),
    )
    if help_probe.returncode != 0:
        raise HarnessError("install-readback", f"{pin.name}: outcome CLI help probe failed")
    readback["runtime_label"] = label
    readback["compat_protocol_version"] = int(protocol)
    readback["cli_help_ok"] = True
    if readback["versions"]["saga"] != pin.saga_version or (
        readback["versions"]["fleet-core"] != pin.fleet_core_version
    ):
        raise HarnessError("install-readback", f"{pin.name}: installed versions drifted")
    runtime.identity = readback
    return runtime


# --------------------------------------------------------------------------- evidence


@dataclass
class ScenarioResult:
    scenario_id: str
    requirement: str
    verdict: str  # "pass" | "fail" | "halt"
    summary: str
    facts: dict[str, Any] = field(default_factory=dict)
    duration_ms: int = 0


def build_bundle(
    *,
    claude: RuntimePin,
    codex: RuntimePin,
    claude_identity: dict[str, Any],
    codex_identity: dict[str, Any],
    digests: dict[str, str],
    broker_root_digest: str,
    scenarios: list[ScenarioResult],
    env_names_set: list[str],
    started_at_iso: str,
    halt: dict[str, str] | None,
) -> dict[str, Any]:
    verdicts = {s.verdict for s in scenarios}
    overall = "halt" if halt else ("pass" if verdicts <= {"pass"} and scenarios else "fail")
    return {
        "schema": SCHEMA_VERSION,
        "started_at": started_at_iso,
        "overall_verdict": overall,
        "halt": halt or None,
        "runtimes": {
            "claude": {
                "sha": claude.sha,
                "expected_versions": {
                    "saga": claude.saga_version,
                    "fleet-core": claude.fleet_core_version,
                },
                "identity": claude_identity,
            },
            "codex": {
                "sha": codex.sha,
                "expected_versions": {
                    "saga": codex.saga_version,
                    "fleet-core": codex.fleet_core_version,
                },
                "identity": codex_identity,
            },
        },
        "contract_digests": digests,
        "broker_root_digest": broker_root_digest,
        "environment_names_set": sorted(env_names_set),
        "scenarios": [
            {
                "scenario_id": s.scenario_id,
                "requirement": s.requirement,
                "verdict": s.verdict,
                "summary": s.summary,
                "facts": s.facts,
                "duration_ms": s.duration_ms,
            }
            for s in scenarios
        ],
    }


# --------------------------------------------------------------------------- scenario registry

ScenarioFn = Callable[["Workbench"], list[ScenarioResult]]
_UNITS: dict[str, ScenarioFn] = {}


def unit(name: str) -> Callable[[ScenarioFn], ScenarioFn]:
    def register(fn: ScenarioFn) -> ScenarioFn:
        _UNITS[name] = fn
        return fn

    return register


@dataclass
class Workbench:
    """Shared per-run state handed to every scenario unit."""

    workdir: Path
    claude: InstalledRuntime
    codex: InstalledRuntime
    broker_root: Path

    def runtime(self, name: str) -> InstalledRuntime:
        return {"claude": self.claude, "codex": self.codex}[name]


# --------------------------------------------------------------------------- main


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="run_cross_runtime_outcome_acceptance")
    parser.add_argument("--claude-repo", required=True, type=Path)
    parser.add_argument("--claude-sha", required=True)
    parser.add_argument("--claude-saga-version", required=True)
    parser.add_argument("--claude-fleet-core-version", required=True)
    parser.add_argument("--codex-repo", required=True, type=Path)
    parser.add_argument("--codex-sha", required=True)
    parser.add_argument("--codex-saga-version", required=True)
    parser.add_argument("--codex-fleet-core-version", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--units",
        default="all",
        help="comma-separated unit filter (default all registered units)",
    )
    parser.add_argument(
        "--keep-workdir",
        action="store_true",
        help="retain the temporary work directory (failed runs always retain it)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    claude_pin = RuntimePin(
        name="claude",
        repo=args.claude_repo.resolve(),
        sha=args.claude_sha,
        saga_version=args.claude_saga_version,
        fleet_core_version=args.claude_fleet_core_version,
        manifest_dir=".claude-plugin",
    )
    codex_pin = RuntimePin(
        name="codex",
        repo=args.codex_repo.resolve(),
        sha=args.codex_sha,
        saga_version=args.codex_saga_version,
        fleet_core_version=args.codex_fleet_core_version,
        manifest_dir=".codex-plugin",
    )

    workdir = Path(tempfile.mkdtemp(prefix="xr-acceptance-"))
    scenarios: list[ScenarioResult] = []
    halt: dict[str, str] | None = None
    claude_identity: dict[str, Any] = {}
    codex_identity: dict[str, Any] = {}
    digests: dict[str, str] = {}
    broker_root_digest = ""
    keep = args.keep_workdir
    try:
        claude_identity = require_clean_pinned(claude_pin)
        codex_identity = require_clean_pinned(codex_pin)
        digests = contract_digests(claude_pin, codex_pin)
        claude_rt = install_isolated(claude_pin, workdir)
        codex_rt = install_isolated(codex_pin, workdir)
        claude_identity["readback"] = claude_rt.identity
        codex_identity["readback"] = codex_rt.identity
        broker_root = workdir / "broker-root"
        broker_root.mkdir()
        # R2: both runtimes must agree on the redacted canonical broker-root digest — the digest
        # of the resolved root RELATIVE to the workbench, never the absolute path.
        broker_root_digest = _sha256_text("broker-root")
        bench = Workbench(
            workdir=workdir, claude=claude_rt, codex=codex_rt, broker_root=broker_root
        )
        selected = list(_UNITS) if args.units == "all" else args.units.split(",")
        for name in selected:
            if name not in _UNITS:
                raise HarnessError("unit-unknown", f"unknown unit {name!r}")
            scenarios.extend(_UNITS[name](bench))
    except HarnessError as exc:
        halt = {"code": exc.code, "detail": _bounded(exc.detail)}
        keep = True
    finally:
        bundle = build_bundle(
            claude=claude_pin,
            codex=codex_pin,
            claude_identity=claude_identity,
            codex_identity=codex_identity,
            digests=digests,
            broker_root_digest=broker_root_digest,
            scenarios=scenarios,
            env_names_set=[n for n in ENV_NAME_ALLOWLIST if n in os.environ],
            started_at_iso=started,
            halt=halt,
        )
        assert_privacy(bundle)
        bundle_sha = atomic_write_json(args.output, bundle)
        print(json.dumps({"ok": halt is None, "bundle_sha256": bundle_sha}))
        if not keep:
            shutil.rmtree(workdir, ignore_errors=True)
    if halt:
        return 2
    return 0 if all(s.verdict == "pass" for s in scenarios) else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
