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
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "lease-safe-runtime-continuity/cross-runtime-acceptance.v1"

# R10: environment-variable NAME allowlist. The bundle records which of these names the harness
# actually sets in the hermetic CHILD environment — computed from the real child env dicts, never
# from the harness's own os.environ — never values, never names outside this closed list. A child
# env name outside the list halts the run before any scenario effect.
ENV_NAME_ALLOWLIST: tuple[str, ...] = (
    "HOME",
    "PATH",
    "PWD",
    "PYTHONPATH",
    "INFIQUETRA_FLEET_STATE_DIR",
    "FLEET_COMMONS_ROOT",
    "XDG_STATE_HOME",
    "GIT_AUTHOR_NAME",
    "GIT_AUTHOR_EMAIL",
    "GIT_COMMITTER_NAME",
    "GIT_COMMITTER_EMAIL",
    "GIT_CONFIG_GLOBAL",
    "GIT_CONFIG_NOSYSTEM",
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
    """A HALT: the run stops before (further) scenario effects; the bundle records the code.

    ``facts`` carries whatever bounded, scrub-clean structured evidence the failing scenario had
    already computed (chain summaries, overlap receipts) so the fail path preserves it in the
    bundle instead of flattening it into the summary string.
    """

    def __init__(self, code: str, message: str, *, facts: dict[str, Any] | None = None) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.detail = message
        self.facts = facts or {}


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


def _private_dir(path: Path) -> Path:
    """Create (or adopt) a directory at exactly mode 0o700.

    Broker roots must satisfy the lease authority's private-root predicate — a default-umask
    ``mkdir`` (0o755) is refused with ``UnsafeAuthorityError`` at first acquire.
    """
    path.mkdir(mode=0o700, exist_ok=True)
    os.chmod(path, 0o700)
    return path


# Any absolute filesystem path with two or more segments, under ANY root — not a closed
# top-level-directory denylist. The lookbehind excludes interior slashes of relative paths
# (refs/remotes/…, plugins/saga/…) but deliberately NOT a preceding colon: a colon-prefixed
# path (tmpdir:/var/folders/…) must still flag, and URL slashes are self-protecting because
# the "//" of a scheme fails the first-segment character class.
_ABS_PATH_RE = re.compile(r"(?<![\w/])/(?:[\w.@+~-]+/)+[\w.@+~-]+")


def _bounded(text: str, limit: int = 400) -> str:
    """A bounded, single-line, path-redacted summary — never raw stdout/stderr (R10)."""
    flat = " ".join(text.split())
    flat = flat.replace(str(Path.home()), "<home>")
    flat = _ABS_PATH_RE.sub("<path>", flat)
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
        elif _ABS_PATH_RE.search(node):
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

    def env(
        self,
        *,
        fleet_state_dir: Path,
        repo_root: Path | None = None,
        path_prefix: Path | None = None,
    ) -> dict[str, str]:
        """Hermetic child environment: isolated HOME, pinned fleet root, no ambient state.

        ``path_prefix`` prepends a directory to PATH — the deterministic ``gh`` fixture shim
        (R2) lives there, so the installed runtime's GitHub reads resolve to canned evidence
        instead of the live network.
        """
        path = os.environ.get("PATH", "")
        if path_prefix is not None:
            path = f"{path_prefix}{os.pathsep}{path}"
        env = {
            "HOME": str(self.home),
            "PATH": path,
            "INFIQUETRA_FLEET_STATE_DIR": str(fleet_state_dir),
            "FLEET_COMMONS_ROOT": str(self.install_root / "plugins/fleet-core"),
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
        path_prefix: Path | None = None,
        timeout: int = _TIMEOUT_S,
    ) -> subprocess.CompletedProcess[str]:
        return _run(
            [sys.executable, str(self.outcome_cli), "--repo-root", str(repo_root), *args],
            cwd=self.install_root,
            env=self.env(
                fleet_state_dir=fleet_state_dir, repo_root=repo_root, path_prefix=path_prefix
            ),
            timeout=timeout,
        )

    def python(
        self,
        code: str,
        *argv: str,
        repo_root: Path,
        fleet_state_dir: Path,
        path_prefix: Path | None = None,
        timeout: int = _TIMEOUT_S,
    ) -> subprocess.CompletedProcess[str]:
        """Run a bounded snippet against the INSTALLED package (sys.argv[1] = scripts dir)."""
        return _run(
            [
                sys.executable,
                "-c",
                code,
                str(self.install_root / "plugins/saga/scripts"),
                *argv,
            ],
            cwd=self.install_root,
            env=self.env(
                fleet_state_dir=fleet_state_dir, repo_root=repo_root, path_prefix=path_prefix
            ),
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


# --------------------------------------------------------------------------- R2 fixtures

_FAKE_GH = '''#!/usr/bin/env python3
"""Deterministic gh fixture shim (R2): serves canned issue/PR JSON, never the network."""
import json
import re
import sys
from pathlib import Path

FIXTURES = json.loads((Path(__file__).resolve().parent / "gh-fixtures.json").read_text())
argv = sys.argv[1:]
if len(argv) >= 3 and argv[0] in ("pr", "issue") and argv[1] == "view":
    match = re.search(r"(\\d+)\\s*$", argv[2])
    key = f"{argv[0]}:{match.group(1)}" if match else ""
    entry = FIXTURES.get(key)
    if entry is None:
        print("GraphQL: Could not resolve (fixture absent)", file=sys.stderr)
        sys.exit(1)
    fields = ""
    if "--json" in argv:
        fields = argv[argv.index("--json") + 1]
    payload = {f: entry.get(f) for f in fields.split(",")} if fields else dict(entry)
    print(json.dumps(payload))
    sys.exit(0)
print("fake gh: unsupported invocation", file=sys.stderr)
sys.exit(1)
'''

CANONICAL_REMOTE = "git@github.com:infiquetra/xr-fixture-target.git"
REPO_IDENTITY = "github.com/infiquetra/xr-fixture-target"


def write_fake_gh(bin_dir: Path, fixtures: dict[str, dict[str, Any]]) -> Path:
    """Materialize the ``gh`` shim + its fixture map; returns the PATH-prefix directory."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    shim = bin_dir / "gh"
    shim.write_text(_FAKE_GH, encoding="utf-8")
    shim.chmod(0o755)
    (bin_dir / "gh-fixtures.json").write_text(
        json.dumps(fixtures, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return bin_dir


# --------------------------------------------------------------------------- U2 topology


@dataclass
class Topology:
    """One acceptance target: bare origin, creator clone, clone A, independent clone B."""

    outcome_id: str
    origin: Path
    creator_clone: Path  # where the creating runtime authors + pushes the committed spec
    clone_a: Path  # shared coordination clone (canonical remote shape)
    clone_b: Path  # independent clone: committed spec + gh fixture only, never store state
    gh_bin: Path


_HARNESS_GIT_ENV = {
    "PATH": os.environ.get("PATH", ""),
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "acceptance-harness",
    "GIT_AUTHOR_EMAIL": "acceptance@invalid.example",
    "GIT_COMMITTER_NAME": "acceptance-harness",
    "GIT_COMMITTER_EMAIL": "acceptance@invalid.example",
}


def _git_h(repo: Path | None, *args: str) -> subprocess.CompletedProcess[str]:
    result = _run(["git", *args], cwd=repo, env=dict(_HARNESS_GIT_ENV))
    if result.returncode != 0:
        raise HarnessError(
            "topology-git", f"git {' '.join(args[:2])} failed rc={result.returncode}"
        )
    return result


_START_SNIPPET = (
    "import json, sys; sys.path.insert(0, sys.argv[1]); import outcome; "
    "from pathlib import Path; "
    "outcome.start(Path(sys.argv[2]), sys.argv[3], sys.argv[4], json.loads(sys.argv[5]))"
)


def build_topology(
    bench: Workbench,
    *,
    creator: str,
    outcome_id: str,
    nodes: list[dict[str, Any]],
    fixtures: dict[str, dict[str, Any]],
) -> Topology:
    """Build the acceptance target: the CREATOR runtime authors and commits the Outcome spec
    through its installed package, then two consumer clones are cut from the same origin.

    Clone A and clone B both present the canonical github.com remote shape (discovery refuses
    foreign remotes); neither ever receives git-common-dir coordination state from the creator —
    clone B additionally never hosts broker/handoff/launch state (KTD5).
    """
    root = bench.workdir / f"topology-{outcome_id}"
    origin = root / "origin.git"
    origin.parent.mkdir(parents=True, exist_ok=True)
    _git_h(None, "init", "-q", "--bare", "--initial-branch", "main", str(origin))
    creator_clone = root / "creator"
    _git_h(None, "clone", "-q", str(origin), str(creator_clone))
    _git_h(creator_clone, "checkout", "-q", "-b", f"outcome/{outcome_id}")
    (creator_clone / "README.md").write_text("acceptance fixture target\n", encoding="utf-8")
    _git_h(creator_clone, "add", "-A")
    _git_h(creator_clone, "commit", "-q", "-m", "seed")
    _git_h(creator_clone, "push", "-q", "-u", "origin", f"outcome/{outcome_id}")
    _git_h(origin, "symbolic-ref", "HEAD", f"refs/heads/outcome/{outcome_id}")

    gh_bin = write_fake_gh(root / "gh-bin", fixtures)
    runtime = bench.runtime(creator)
    started = runtime.python(
        _START_SNIPPET,
        str(creator_clone),
        outcome_id,
        f"Acceptance target {outcome_id}",
        json.dumps(nodes),
        repo_root=creator_clone,
        fleet_state_dir=bench.broker_root,
        path_prefix=gh_bin,
    )
    if started.returncode != 0:
        raise HarnessError("topology-start", f"{creator} start failed: {_bounded(started.stderr)}")
    committed = runtime.outcome(
        "commit",
        outcome_id,
        "--push",
        repo_root=creator_clone,
        fleet_state_dir=bench.broker_root,
        path_prefix=gh_bin,
    )
    if committed.returncode != 0:
        raise HarnessError(
            "topology-commit", f"{creator} commit --push failed: {_bounded(committed.stderr)}"
        )

    clone_a = root / "clone-a"
    clone_b = root / "clone-b"
    for clone in (clone_a, clone_b):
        _git_h(None, "clone", "-q", str(origin), str(clone))
        _git_h(clone, "remote", "set-url", "origin", CANONICAL_REMOTE)
    return Topology(
        outcome_id=outcome_id,
        origin=origin,
        creator_clone=creator_clone,
        clone_a=clone_a,
        clone_b=clone_b,
        gh_bin=gh_bin,
    )


DEFAULT_NODES: list[dict[str, Any]] = [
    {
        "subplot_id": "done-leaf",
        "title": "Merged code leaf",
        "backend": "inline",
        "kind": "code",
        "github": {"pr": "infiquetra/xr-fixture-target#11"},
    },
    {
        "subplot_id": "ready-leaf",
        "title": "Open code leaf",
        "backend": "inline",
        "kind": "code",
        "github": {"pr": "infiquetra/xr-fixture-target#12"},
        "deps": ["done-leaf"],
    },
    {
        "subplot_id": "untracked-leaf",
        "title": "Untracked non-code leaf",
        "backend": "inline",
        "kind": "non-code",
        "deps": ["done-leaf"],
    },
]

DEFAULT_FIXTURES: dict[str, dict[str, Any]] = {
    "pr:11": {"state": "MERGED", "mergedAt": "2026-07-20T00:00:00Z"},
    "pr:12": {"state": "OPEN", "mergedAt": None},
}


def _store_dirs(clone: Path) -> list[str]:
    """Repo-relative coordination-state paths under the clone's git dir (empty = none).

    ``saga-outcomes`` is the real ``outcome_store.STORE_NAMESPACE``; the speculative names stay
    as tripwires against a future namespace move silently blinding this check.
    """
    git_dir = clone / ".git"
    hits: list[str] = []
    for candidate in ("saga-outcomes", "outcome", "outcomes", "saga", "handoffs"):
        target = git_dir / candidate
        if target.exists():
            hits.append(f".git/{candidate}")
    return hits


@unit("u2-discovery")
def unit_discovery(bench: Workbench) -> list[ScenarioResult]:
    """R3: canonical discovery + cross-clone read-only reconstruction, both creation directions."""
    results: list[ScenarioResult] = []
    for creator, consumer in (("claude", "codex"), ("codex", "claude")):
        started = time.monotonic()
        outcome_id = f"xr-{creator}-created"
        topo = build_topology(
            bench,
            creator=creator,
            outcome_id=outcome_id,
            nodes=DEFAULT_NODES,
            fixtures=DEFAULT_FIXTURES,
        )
        facts: dict[str, Any] = {}
        verdict, summary = "pass", ""
        try:
            envelopes: dict[str, dict[str, Any]] = {}
            projections: dict[str, dict[str, Any]] = {}
            for name in ("claude", "codex"):
                runtime = bench.runtime(name)
                discover = runtime.outcome(
                    "discover",
                    outcome_id,
                    repo_root=topo.clone_a,
                    fleet_state_dir=bench.broker_root,
                    path_prefix=topo.gh_bin,
                )
                if discover.returncode != 0:
                    raise HarnessError(
                        "discovery-failed", f"{name} discover rc={discover.returncode}"
                    )
                envelopes[name] = json.loads(discover.stdout)
                for clone_name, clone in (("a", topo.clone_a), ("b", topo.clone_b)):
                    attach = runtime.outcome(
                        "attach",
                        outcome_id,
                        repo_root=clone,
                        fleet_state_dir=bench.broker_root,
                        path_prefix=topo.gh_bin,
                    )
                    if attach.returncode != 0:
                        raise HarnessError(
                            "projection-failed",
                            f"{name} attach on clone {clone_name} rc={attach.returncode}",
                        )
                    projections[f"{name}:{clone_name}"] = json.loads(attach.stdout)

            for name, envelope in envelopes.items():
                if envelope["repository"]["identity"] != REPO_IDENTITY:
                    raise HarnessError("discovery-identity", f"{name} envelope identity drifted")
                if envelope["producer"]["runtime"] != name:
                    raise HarnessError("discovery-producer", f"{name} produced foreign label")
            neutral = {
                name: {k: v for k, v in env.items() if k != "producer"}
                for name, env in envelopes.items()
            }
            if neutral["claude"] != neutral["codex"]:
                raise HarnessError("discovery-parity", "envelopes diverge beyond producer")

            serialized = {
                key: json.dumps(proj, sort_keys=True) for key, proj in projections.items()
            }
            if len(set(serialized.values())) != 1:
                raise HarnessError(
                    "projection-parity", "canonical projections diverge across runtimes/clones"
                )
            sample = projections["claude:a"]
            if sample["mutation_allowed"] is not False:
                raise HarnessError("projection-mutation", "projection claims mutation_allowed")
            if sample["completed"] != ["done-leaf"]:
                raise HarnessError("projection-completed", f"completed={sample['completed']}")
            if sample["candidate_frontier"] != ["ready-leaf"]:
                raise HarnessError(
                    "projection-frontier", f"frontier={sample['candidate_frontier']}"
                )
            if sample["unknown"] != ["untracked-leaf"]:
                raise HarnessError("projection-unknown", f"unknown={sample['unknown']}")

            residue = _store_dirs(topo.clone_b)
            if residue:
                raise HarnessError("clone-b-state", f"coordination state on clone B: {residue}")
            denied = bench.runtime(consumer).outcome(
                "attach",
                outcome_id,
                "--advance",
                "--handoff-id",
                "h-none",
                "--subplot",
                "ready-leaf",
                "--session-id",
                "sess-b",
                "--policy-sha256",
                "c" * 64,
                "--session-limit",
                "1",
                "--aggregate-limit",
                "1",
                repo_root=topo.clone_b,
                fleet_state_dir=bench.broker_root,
                path_prefix=topo.gh_bin,
            )
            # The denial must be the TYPED refusal (receipt + exit 3), not any incidental
            # non-zero exit — the same exact-code discipline as the U3 negative matrix.
            if denied.returncode != 3:
                raise HarnessError(
                    "clone-b-mutation",
                    f"clone B attach --advance rc={denied.returncode} (expected typed refusal "
                    f"rc 3): {_bounded(denied.stderr or denied.stdout)}",
                )
            denial_receipt = json.loads(denied.stdout.strip().splitlines()[-1])
            if denial_receipt.get("code") != "handoff-missing":
                raise HarnessError(
                    "clone-b-mutation",
                    f"clone B refusal code {denial_receipt.get('code')!r} != 'handoff-missing'",
                )
            if _store_dirs(topo.clone_b):
                raise HarnessError("clone-b-mutation", "refused attach still wrote state")
            facts = {
                "creator": creator,
                "consumer": consumer,
                "completed": sample["completed"],
                "candidate_frontier": sample["candidate_frontier"],
                "unknown": sample["unknown"],
                "projection_digest": _sha256_text(next(iter(serialized.values()))),
                "clone_b_refusal_rc": denied.returncode,
                "clone_b_refusal_code": str(denial_receipt.get("code")),
            }
            summary = (
                f"{creator}-created spec discovered by both runtimes; projections byte-identical "
                "across runtimes and clones; clone B state-free and mutation-denied"
            )
        except HarnessError as exc:
            verdict = "fail"
            summary = f"{exc.code}: {_bounded(exc.detail)}"
        results.append(
            ScenarioResult(
                scenario_id=f"discovery-{creator}-created",
                requirement="R3",
                verdict=verdict,
                summary=summary,
                facts=facts,
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        )
    return results


# --------------------------------------------------------------------------- U3 handoff (R4)


def _tree_state(root: Path) -> dict[str, str]:
    """Effect spy: relative-path -> content-sha256 map for a tree (empty when absent).

    Captured before and after every refused acceptance; byte-equality of the maps proves the
    refusal produced no mutable effect in that store.
    """
    if not root.exists():
        return {}
    state: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and not path.is_symlink():
            state[path.relative_to(root).as_posix()] = _sha256_file(path)
    return state


_ADMISSION_POLICY = "c" * 64

# Tamper rig for the R4 adversarial cases. Runs against the INSTALLED package so the re-seal
# uses the runtime's own canonical_json — a tamper-and-reseal attacker has exactly this power,
# and the semantic bindings (not the seal) must be what refuses the record.
_TAMPER_SNIPPET = """
import hashlib
import json
import sys

sys.path.insert(0, sys.argv[1])
from pathlib import Path

import outcome_compat as oc

path = Path(sys.argv[2])
mode = sys.argv[3]
record = json.loads(path.read_text(encoding="utf-8"))
if mode == "bump-fence":
    record["token"]["fencing_sequence"] = int(record["token"]["fencing_sequence"]) + 1
else:
    record.update(json.loads(sys.argv[4]))
if mode in ("reseal", "bump-fence"):
    payload = {key: value for key, value in record.items() if key != "sha256"}
    record["sha256"] = hashlib.sha256(oc.canonical_json(payload).encode("utf-8")).hexdigest()
path.write_text(oc.canonical_json(record) + "\\n", encoding="utf-8")
"""

# Offer-side refusals that must fire BEFORE any broker interaction: driven with broker=None so
# a broker touch would crash loudly instead of leaking a lease.
_OFFER_NEGATIVE_SNIPPET = """
import json
import sys

sys.path.insert(0, sys.argv[1])
from pathlib import Path

import outcome_compat as oc

try:
    oc.offer_handoff(
        Path(sys.argv[2]),
        sys.argv[3],
        sys.argv[4],
        operation=sys.argv[5],
        attempt=1,
        broker=None,
        lease=None,
        dispatch_id=sys.argv[6],
        ttl_seconds=int(sys.argv[7]),
    )
except oc.CompatibilityHaltError as halt:
    print(json.dumps(halt.receipt()))
    raise SystemExit(3)
raise SystemExit(0)
"""

# Wrong/stale issuer (offer-side R4): a successful offer RELINQUISHES the issuer's broker
# authority, so a second offer from the same, now-closed lease must refuse
# handoff-issuer-not-current. Both offers must share one process (the lease object is live
# state), so the zero-effect check runs in-process: the store + broker trees are hashed after
# the first (legitimate) offer and compared after the refused re-offer.
_STALE_ISSUER_SNIPPET = """
import hashlib
import json
import sys

sys.path.insert(0, sys.argv[1])
from pathlib import Path

import fleet_commons_shim
import outcome_compat as oc

lease_broker = fleet_commons_shim.load("lease_broker")
root = Path(sys.argv[2])
outcome_id = sys.argv[3]
subplot_id = sys.argv[4]
broker_root = Path(sys.argv[5])
dispatch_id = sys.argv[6]
session_id = sys.argv[7]
policy_sha256 = sys.argv[8]

broker = lease_broker.LeaseBroker(broker_root)
identity = oc.repository_identity(root)
lease = broker.acquire_agent(
    owner_id="u3-stale-issuer",
    session_id=session_id,
    policy_sha256=policy_sha256,
    session_limit=4,
    aggregate_limit=8,
    mutation="read-write",
    resource_ref=oc.outcome_dispatch_resource(identity, outcome_id, subplot_id, 12),
)
oc.offer_handoff(
    root, outcome_id, subplot_id,
    operation="advance-one", attempt=12, broker=broker, lease=lease,
    dispatch_id=dispatch_id, ttl_seconds=60,
)


def _tree() -> dict[str, str]:
    state = {}
    for base in (root / ".git" / "saga-outcomes", broker_root):
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file():
                key = f"{base.name}/{path.relative_to(base)}"
                state[key] = hashlib.sha256(path.read_bytes()).hexdigest()
    return state


before = _tree()
try:
    oc.offer_handoff(
        root, outcome_id, subplot_id,
        operation="advance-one", attempt=12, broker=broker, lease=lease,
        dispatch_id=dispatch_id, ttl_seconds=60,
    )
except oc.CompatibilityHaltError as halt:
    print(json.dumps({**halt.receipt(), "stale_reoffer_unchanged": _tree() == before}))
    raise SystemExit(3)
raise SystemExit(0)
"""

_REVISE_SPEC_SNIPPET = """
import sys

sys.path.insert(0, sys.argv[1])
from pathlib import Path

import outcome

root = Path(sys.argv[2])
spec = outcome.load_spec(root, sys.argv[3])
spec.bump_revision(reason="acceptance wrong-revision rig")
outcome.save_spec(root, spec)
"""


@dataclass
class HandoffRig:
    """Per-direction U3 state: topology, dedicated broker root, and spy targets."""

    topo: Topology
    broker_root: Path
    issuer: str
    receiver: str

    @property
    def store_a(self) -> Path:
        return self.topo.clone_a / ".git" / "saga-outcomes"

    @property
    def store_b(self) -> Path:
        return self.topo.clone_b / ".git" / "saga-outcomes"

    def spy(self) -> dict[str, dict[str, str]]:
        return {
            "store_a": _tree_state(self.store_a),
            "store_b": _tree_state(self.store_b),
            "broker": _tree_state(self.broker_root),
        }

    def offer_path(self, handoff_id: str) -> Path:
        return self.store_a / self.topo.outcome_id / "handoffs" / f"{handoff_id}.offer.json"


def _admission_args(session: str, broker_root: Path) -> list[str]:
    return [
        "--session-id",
        session,
        "--policy-sha256",
        _ADMISSION_POLICY,
        "--session-limit",
        "4",
        "--aggregate-limit",
        "8",
        "--broker-root",
        str(broker_root),
    ]


def _mint(
    bench: Workbench,
    rig: HandoffRig,
    *,
    attempt: int,
    operation: str = "advance-one",
) -> str:
    """Issue a fresh handoff on clone A as the issuing runtime; returns the handoff id."""
    args = [
        "handoff",
        rig.topo.outcome_id,
        "ready-leaf",
        "--operation",
        operation,
        "--attempt",
        str(attempt),
    ]
    if operation == "advance-one":
        args += ["--dispatch-id", f"outcome:{rig.topo.outcome_id}:frontier:ready-leaf"]
    args += _admission_args(f"u3-{rig.issuer}-{attempt}-iss", rig.broker_root)
    minted = bench.runtime(rig.issuer).outcome(
        *args,
        repo_root=rig.topo.clone_a,
        fleet_state_dir=bench.broker_root,
        path_prefix=rig.topo.gh_bin,
    )
    if minted.returncode != 0:
        raise HarnessError(
            "handoff-mint",
            f"{rig.issuer} attempt {attempt} rc={minted.returncode}: {_bounded(minted.stderr)}",
        )
    reference = json.loads(minted.stdout.strip().splitlines()[-1])
    handoff_id = str(reference["handoff_id"])
    if reference.get("schema") != "outcome.handoff-reference.v1" or not re.fullmatch(
        r"[0-9a-f]{32}", handoff_id
    ):
        raise HarnessError("handoff-mint", f"{rig.issuer} attempt {attempt}: malformed reference")
    return handoff_id


def _attempt_accept(
    bench: Workbench,
    rig: HandoffRig,
    *,
    handoff_id: str,
    clone: Path,
    subplot: str = "ready-leaf",
    receiver_id: str | None = None,
    session: str,
    broker_root: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    return bench.runtime(rig.receiver).outcome(
        "attach",
        rig.topo.outcome_id,
        "--advance",
        "--handoff-id",
        handoff_id,
        "--subplot",
        subplot,
        "--receiver",
        receiver_id or f"recv-{rig.receiver}",
        *_admission_args(session, broker_root if broker_root is not None else rig.broker_root),
        repo_root=clone,
        fleet_state_dir=bench.broker_root,
        path_prefix=rig.topo.gh_bin,
    )


def _expect_refusal(
    result: subprocess.CompletedProcess[str],
    *,
    case: str,
    code: str,
    unsupported_contains: str | None = None,
) -> str:
    """A refused acceptance must exit 3 with a receipt carrying exactly the expected code.

    ``unsupported_contains`` additionally pins the receipt's ``unsupported`` text — used where
    two cases share one coarse code (both supersession shapes refuse ``handoff-superseded``)
    so the matrix proves each case took its INTENDED refusal mechanism, not the other's.
    """
    if result.returncode != 3:
        raise HarnessError(
            "handoff-negative-rc",
            f"{case}: rc={result.returncode} (expected 3): {_bounded(result.stderr or result.stdout)}",
        )
    receipt = json.loads(result.stdout.strip().splitlines()[-1])
    observed = str(receipt.get("code"))
    if observed != code:
        raise HarnessError("handoff-negative-code", f"{case}: code {observed!r} != {code!r}")
    if unsupported_contains is not None and unsupported_contains not in str(
        receipt.get("unsupported", "")
    ):
        raise HarnessError(
            "handoff-negative-code",
            f"{case}: receipt mechanism {receipt.get('unsupported')!r} lacks "
            f"{unsupported_contains!r}",
        )
    return observed


def _expect_unchanged(
    pre: dict[str, dict[str, str]], post: dict[str, dict[str, str]], *, case: str
) -> None:
    for name in pre:
        if pre[name] != post[name]:
            raise HarnessError("handoff-negative-effect", f"{case}: {name} mutated on refusal")


def _tamper(
    bench: Workbench, rig: HandoffRig, handoff_id: str, *, mode: str, mutation: dict[str, Any]
) -> None:
    tampered = bench.runtime(rig.issuer).python(
        _TAMPER_SNIPPET,
        str(rig.offer_path(handoff_id)),
        mode,
        json.dumps(mutation),
        repo_root=rig.topo.clone_a,
        fleet_state_dir=bench.broker_root,
    )
    if tampered.returncode != 0:
        raise HarnessError("handoff-tamper-rig", f"{mode}: {_bounded(tampered.stderr)}")


def _handoff_positive(bench: Workbench, rig: HandoffRig) -> dict[str, Any]:
    """R4 positive path: issuer mints on clone A, the OTHER runtime accepts and advances."""
    handoff_id = _mint(bench, rig, attempt=1)
    accepted = _attempt_accept(
        bench,
        rig,
        handoff_id=handoff_id,
        clone=rig.topo.clone_a,
        session=f"u3-{rig.receiver}-1-acc",
    )
    if accepted.returncode != 0:
        raise HarnessError(
            "handoff-accept",
            f"{rig.receiver} accept rc={accepted.returncode}: {_bounded(accepted.stderr)}",
        )
    outcome_result = json.loads(accepted.stdout.strip().splitlines()[-1])
    if outcome_result.get("handoff_id") != handoff_id or not outcome_result.get(
        "successor_lease_id"
    ):
        raise HarnessError("handoff-accept", "accept output missing successor binding")
    for suffix in ("offer", "intent", "commit"):
        record = rig.store_a / rig.topo.outcome_id / "handoffs" / f"{handoff_id}.{suffix}.json"
        if not record.is_file():
            raise HarnessError("handoff-accept", f"missing protected {suffix} record")
    advance = outcome_result.get("advance", {})
    # The one-subplot advance must have MOVED the leaf in the RECEIVER's native vocabulary:
    # claude's inline path reports "dispatched", codex's native outcome.dispatch.v2 path
    # reports "intent-created" (R6). The direction is deterministic, so the expectation is
    # pinned per receiver — a receiver emitting the other runtime's vocabulary must fail.
    leaf_state = advance.get("status", {}).get("states", {}).get("ready-leaf")
    expected_leaf_state = "intent-created" if rig.receiver == "codex" else "dispatched"
    if leaf_state != expected_leaf_state:
        raise HarnessError(
            "handoff-advance",
            f"ready-leaf state {leaf_state!r} after {rig.receiver} advance "
            f"(expected {expected_leaf_state!r})",
        )
    return {
        "handoff_id": handoff_id,
        "successor_lease_id": str(outcome_result["successor_lease_id"]),
        "advance_dispatched": advance.get("dispatched"),
        "ready_leaf_state": leaf_state,
        # Bounded, path-redacted view of the non-empty tick outcomes — enough to diagnose a
        # gated/halted leaf without carrying raw receipts into the bundle.
        "advance_outcomes": _bounded(
            json.dumps({k: v for k, v in advance.items() if v}, sort_keys=True)
        ),
    }


def _handoff_negatives(
    bench: Workbench, rig: HandoffRig, positive_handoff_id: str
) -> dict[str, Any]:
    """The R4 negative matrix; every case must refuse with zero mutable effect.

    One deliberate exception: ``wrong-fence`` refuses inside successor acquisition, AFTER the
    write-once accept-intent (the designed crash-resume artifact) — for that case the spy
    asserts the intent file is the ONLY store delta and broker/ledger stay untouched.
    """
    topo, cases = rig.topo, {}
    now = int(time.time())

    def refused_unchanged(
        case: str, code: str, run: Callable[[], Any], *, unsupported_contains: str | None = None
    ) -> None:
        pre = rig.spy()
        cases[case] = _expect_refusal(
            run(), case=case, code=code, unsupported_contains=unsupported_contains
        )
        _expect_unchanged(pre, rig.spy(), case=case)

    # 1. A copied reference on independent clone B: the printable reference grants nothing
    #    without the protected local record; clone B must also stay entirely state-free.
    h_b = _mint(bench, rig, attempt=2)
    refused_unchanged(
        "copied-reference-clone-b",
        "handoff-missing",
        lambda: _attempt_accept(
            bench, rig, handoff_id=h_b, clone=topo.clone_b, session="u3-neg-clone-b"
        ),
    )
    if _store_dirs(topo.clone_b):
        raise HarnessError("handoff-negative-effect", "clone B grew store state on refusal")

    # 2. A well-formed handoff id with no protected record at all.
    refused_unchanged(
        "missing-record",
        "handoff-missing",
        lambda: _attempt_accept(
            bench, rig, handoff_id="0" * 32, clone=topo.clone_a, session="u3-neg-missing"
        ),
    )

    # 3. Byte tamper without re-seal: the seal check refuses first.
    h_tamper = _mint(bench, rig, attempt=3)
    _tamper(bench, rig, h_tamper, mode="raw", mutation={"subplot_id": "done-leaf"})
    refused_unchanged(
        "byte-tamper",
        "handoff-seal-invalid",
        lambda: _attempt_accept(
            bench, rig, handoff_id=h_tamper, clone=topo.clone_a, session="u3-neg-tamper"
        ),
    )

    # 4. Wrong repository: same clone, remote moved to a foreign identity.
    h_repo = _mint(bench, rig, attempt=4)
    _git_h(topo.clone_a, "remote", "set-url", "origin", "git@github.com:infiquetra/other.git")
    try:
        refused_unchanged(
            "wrong-repository",
            "handoff-wrong-repository",
            lambda: _attempt_accept(
                bench, rig, handoff_id=h_repo, clone=topo.clone_a, session="u3-neg-repo"
            ),
        )
    finally:
        _git_h(topo.clone_a, "remote", "set-url", "origin", CANONICAL_REMOTE)

    # 5. Wrong operation: an attend offer never authorizes an advance.
    h_attend = _mint(bench, rig, attempt=5, operation="attend")
    refused_unchanged(
        "wrong-operation",
        "handoff-wrong-operation",
        lambda: _attempt_accept(
            bench, rig, handoff_id=h_attend, clone=topo.clone_a, session="u3-neg-op"
        ),
    )

    # 6. Wrong subplot: the offer binds exactly one leaf.
    h_subplot = _mint(bench, rig, attempt=6)
    refused_unchanged(
        "wrong-subplot",
        "handoff-wrong-subplot",
        lambda: _attempt_accept(
            bench,
            rig,
            handoff_id=h_subplot,
            clone=topo.clone_a,
            subplot="done-leaf",
            session="u3-neg-subplot",
        ),
    )

    # 7. Replay / second receiver: the consumed positive handoff is bound to its receiver.
    refused_unchanged(
        "replay-second-receiver",
        "handoff-receiver-conflict",
        lambda: _attempt_accept(
            bench,
            rig,
            handoff_id=positive_handoff_id,
            clone=topo.clone_a,
            receiver_id=f"intruder-{rig.receiver}",
            session="u3-neg-replay",
        ),
    )

    # 8. Wrong fence: tamper-and-reseal the fencing token — the seal passes, the broker head
    #    comparison refuses. Runs AFTER the intent write; the intent must be the only delta.
    #    Shares the coarse "handoff-superseded" code with wrong-authority, so the receipt's
    #    mechanism text is pinned too: this case must take the head-moved supersession branch.
    h_fence = _mint(bench, rig, attempt=7)
    _tamper(bench, rig, h_fence, mode="bump-fence", mutation={})
    pre_fence = rig.spy()
    cases["wrong-fence"] = _expect_refusal(
        _attempt_accept(bench, rig, handoff_id=h_fence, clone=topo.clone_a, session="u3-neg-fence"),
        case="wrong-fence",
        code="handoff-superseded",
        unsupported_contains="superseded by another authority",
    )
    post_fence = rig.spy()
    _expect_unchanged(
        {k: v for k, v in pre_fence.items() if k != "store_a"},
        {k: v for k, v in post_fence.items() if k != "store_a"},
        case="wrong-fence",
    )
    fence_delta = set(post_fence["store_a"]) - set(pre_fence["store_a"])
    intent_rel = f"{topo.outcome_id}/handoffs/{h_fence}.intent.json"
    if fence_delta != {intent_rel} or any(
        pre_fence["store_a"][k] != post_fence["store_a"][k] for k in pre_fence["store_a"]
    ):
        raise HarnessError(
            "handoff-negative-effect", f"wrong-fence: store delta {sorted(fence_delta)}"
        )

    # 9. Wrong authority: the record + reference presented against a broker root that never
    #    issued anything — no resource head, no successor, nothing minted anywhere. Must take
    #    the head-ABSENT supersession branch (distinct from wrong-fence's head-moved branch),
    #    and refuse pre-intent: zero store delta, versus wrong-fence's intent-only delta.
    h_auth = _mint(bench, rig, attempt=8)
    foreign = rig.broker_root.parent / f"{rig.broker_root.name}-foreign"
    _private_dir(foreign)
    refused_unchanged(
        "wrong-authority",
        "handoff-superseded",
        lambda: _attempt_accept(
            bench,
            rig,
            handoff_id=h_auth,
            clone=topo.clone_a,
            session="u3-neg-auth",
            broker_root=foreign,
        ),
        unsupported_contains="no longer exists",
    )
    leaked = [
        path
        for path in foreign.rglob("*")
        if path.is_file() and h_auth in path.read_text(encoding="utf-8", errors="ignore")
    ]
    if leaked:
        raise HarnessError("handoff-negative-effect", "wrong-authority: successor state leaked")

    # 10. Wrong/stale issuer (offer-side): the first in-process offer legitimately closes the
    #     issuer's authority; the second offer from that same lease must refuse with zero
    #     effect (the snippet's in-process tree hash covers store AND broker).
    stale = bench.runtime(rig.issuer).python(
        _STALE_ISSUER_SNIPPET,
        str(topo.clone_a),
        topo.outcome_id,
        "ready-leaf",
        str(rig.broker_root),
        f"outcome:{topo.outcome_id}:frontier:ready-leaf",
        "u3-neg-issuer",
        _ADMISSION_POLICY,
        repo_root=topo.clone_a,
        fleet_state_dir=bench.broker_root,
    )
    cases["stale-issuer"] = _expect_refusal(
        stale, case="stale-issuer", code="handoff-issuer-not-current"
    )
    stale_receipt = json.loads(stale.stdout.strip().splitlines()[-1])
    if stale_receipt.get("stale_reoffer_unchanged") is not True:
        raise HarnessError(
            "handoff-negative-effect", "stale-issuer: refused re-offer mutated state"
        )

    # 11/12. Offer-side bounds, driven with broker=None so any broker touch crashes loudly:
    # a TTL beyond the 300s cap and a scope beyond the single-subplot closed vocabulary.
    for case, operation, ttl, code in (
        ("ttl-beyond-bound", "advance-one", 301, "handoff-ttl-too-long"),
        ("broad-scope-operation", "advance-all", 60, "schema-field-type"),
    ):
        pre = rig.spy()
        cases[case] = _expect_refusal(
            bench.runtime(rig.issuer).python(
                _OFFER_NEGATIVE_SNIPPET,
                str(topo.clone_a),
                topo.outcome_id,
                "ready-leaf",
                operation,
                f"outcome:{topo.outcome_id}:frontier:ready-leaf",
                str(ttl),
                repo_root=topo.clone_a,
                fleet_state_dir=bench.broker_root,
            ),
            case=case,
            code=code,
        )
        _expect_unchanged(pre, rig.spy(), case=case)

    # 13/14. Freshness bounds via tamper-and-reseal: expired, and issued in the future.
    for case, times, code in (
        (
            "expired",
            {"issued_at_epoch": now - 4000, "expires_at_epoch": now - 3700},
            "handoff-expired",
        ),
        (
            "future-skew",
            {"issued_at_epoch": now + 3600, "expires_at_epoch": now + 3900},
            "handoff-clock-skew",
        ),
    ):
        h_time = _mint(bench, rig, attempt=9 if case == "expired" else 10)
        _tamper(bench, rig, h_time, mode="reseal", mutation=times)
        pre = rig.spy()
        cases[case] = _expect_refusal(
            _attempt_accept(
                bench, rig, handoff_id=h_time, clone=topo.clone_a, session=f"u3-neg-{case}"
            ),
            case=case,
            code=code,
        )
        _expect_unchanged(pre, rig.spy(), case=case)

    # 15. Wrong revision (LAST — it moves the committed spec): the offer binds the revision at
    #     issue time; the creator advances the spec, clone A pulls, acceptance must refuse.
    h_rev = _mint(bench, rig, attempt=11)
    revised = bench.runtime(rig.issuer).python(
        _REVISE_SPEC_SNIPPET,
        str(topo.creator_clone),
        topo.outcome_id,
        repo_root=topo.creator_clone,
        fleet_state_dir=bench.broker_root,
    )
    if revised.returncode != 0:
        raise HarnessError("handoff-revise-rig", _bounded(revised.stderr))
    committed = bench.runtime(rig.issuer).outcome(
        "commit",
        topo.outcome_id,
        "--push",
        repo_root=topo.creator_clone,
        fleet_state_dir=bench.broker_root,
        path_prefix=topo.gh_bin,
    )
    if (
        committed.returncode != 0
        or json.loads(committed.stdout.strip().splitlines()[-1]).get("pushed") is False
    ):
        raise HarnessError(
            "handoff-revise-rig", f"revision push failed: {_bounded(committed.stderr)}"
        )
    # Clone A's configured origin is the canonical (unreachable) GitHub URL — fetch the bump
    # from the local bare origin by path, keeping the remote-tracking ref in step so every
    # committed-spec candidate ref agrees.
    branch = f"outcome/{topo.outcome_id}"
    _git_h(topo.clone_a, "fetch", "-q", str(topo.origin), f"{branch}:refs/remotes/origin/{branch}")
    _git_h(topo.clone_a, "merge", "-q", "--ff-only", f"refs/remotes/origin/{branch}")
    refused_unchanged(
        "wrong-revision",
        "handoff-wrong-revision",
        lambda: _attempt_accept(
            bench, rig, handoff_id=h_rev, clone=topo.clone_a, session="u3-neg-rev"
        ),
    )

    return {"cases": cases, "intent_artifact_cases": ["wrong-fence"]}


@unit("u3-handoff")
def unit_handoff(bench: Workbench) -> list[ScenarioResult]:
    """R4: protected bounded handoff both directions, plus the adversarial negative matrix."""
    results: list[ScenarioResult] = []
    for issuer, receiver in (("claude", "codex"), ("codex", "claude")):
        started = time.monotonic()
        broker_root = bench.workdir / f"broker-u3-{issuer}"
        _private_dir(broker_root)
        rig = HandoffRig(
            topo=build_topology(
                bench,
                creator=issuer,
                outcome_id=f"xr-u3-{issuer}",
                nodes=DEFAULT_NODES,
                fixtures=DEFAULT_FIXTURES,
            ),
            broker_root=broker_root,
            issuer=issuer,
            receiver=receiver,
        )
        positive_facts: dict[str, Any] = {}
        verdict, summary = "pass", ""
        try:
            positive_facts = _handoff_positive(bench, rig)
            summary = (
                f"{issuer}-issued handoff accepted by {receiver}: successor lease minted, "
                "one-subplot advance ran, all three protected records present"
            )
        except HarnessError as exc:
            verdict = "fail"
            summary = f"{exc.code}: {_bounded(exc.detail)}"
        results.append(
            ScenarioResult(
                scenario_id=f"handoff-{issuer}-issued",
                requirement="R4",
                verdict=verdict,
                summary=summary,
                facts={"issuer": issuer, "receiver": receiver, **positive_facts},
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        )
        started = time.monotonic()
        negative_facts: dict[str, Any] = {}
        verdict, summary = "pass", ""
        if positive_facts:
            try:
                negative_facts = _handoff_negatives(bench, rig, positive_facts["handoff_id"])
                summary = (
                    f"{len(negative_facts['cases'])} adversarial acceptances refused with the "
                    "expected codes and zero mutable effect (intent artifact on wrong-fence only)"
                )
            except HarnessError as exc:
                verdict = "fail"
                summary = f"{exc.code}: {_bounded(exc.detail)}"
        else:
            verdict = "fail"
            summary = "skipped: positive handoff path failed in this direction"
        results.append(
            ScenarioResult(
                scenario_id=f"handoff-negatives-{issuer}-issued",
                requirement="R4",
                verdict=verdict,
                summary=summary,
                facts={"issuer": issuer, "receiver": receiver, **negative_facts},
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        )
    return results


# --------------------------------------------------------------------------- U4 race (R5/R6)

RACE_NODES: list[dict[str, Any]] = [
    {
        "subplot_id": "race-leaf",
        "title": "Race leaf",
        "backend": "inline",
        "kind": "code",
        "github": {"pr": "infiquetra/xr-fixture-target#12"},
    }
]

# Barrier-released advance: record wall-clock enter/exit around the installed CLI's advance so
# the harness can prove the two OS processes genuinely overlapped (R5 monotonic receipts).
_BARRIER_ADVANCE_SNIPPET = """
import json
import os
import sys
import time

sys.path.insert(0, sys.argv[1])
from pathlib import Path

ready = Path(sys.argv[2])
barrier = Path(sys.argv[3])
ready.write_text("ready", encoding="utf-8")
deadline = time.time() + 30
while not barrier.exists():
    if time.time() > deadline:
        raise SystemExit(97)
    time.sleep(0.002)

import io
from contextlib import redirect_stdout

import outcome

enter_ns = time.time_ns()
buffer = io.StringIO()
with redirect_stdout(buffer):
    rc = outcome.main(["--repo-root", sys.argv[4], "advance", sys.argv[5]])
exit_ns = time.time_ns()
result = {}
for line in buffer.getvalue().splitlines():
    if line.startswith("{"):
        result = json.loads(line)
        break
print(
    json.dumps(
        {
            "enter_ns": enter_ns,
            "exit_ns": exit_ns,
            "rc": rc,
            "dispatched": result.get("dispatched"),
            "skipped_busy": result.get("skipped_busy"),
        }
    )
)
"""

# The harness playing the launched Codex runner (R6): read the native dispatch intent, produce
# the write-once backend effect, and materialize the protected launch receipt in the hermetic
# home's user-state root — every path and vocabulary element comes from the INSTALLED package.
_CODEX_LAUNCH_PREP_SNIPPET = """
import hashlib
import json
import os
import sys
import time

sys.path.insert(0, sys.argv[1])
from pathlib import Path

import fleet_commons_shim
import outcome_store

wc = fleet_commons_shim.load("workflow_compat")
root = Path(sys.argv[2]).resolve()
outcome_id = sys.argv[3]
subplot_id = sys.argv[4]
effect_path = Path(sys.argv[5])

common = outcome_store.resolve_common_dir(root)
ledger = common / outcome_store.STORE_NAMESPACE / outcome_id / "ledger.jsonl"
records = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line]
intents = [
    rec
    for rec in records
    if rec.get("kind") == "outcome.dispatch.v2"
    and rec.get("phase") == "intent"
    and rec.get("subplot_id") == subplot_id
]
if not intents:
    raise SystemExit(96)
intent = intents[-1]
leaf = f"leaf-{outcome_id}-{subplot_id}"

fd = os.open(str(effect_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as handle:
    json.dump({"writer": "codex-runner", "pid": os.getpid()}, handle)

receipt = {
    "schema": "saga.outcome-dispatch-launch.v1",
    "producer_kind": wc.emit(wc.PRODUCER_KIND),
    "outcome_id": outcome_id,
    "subplot_id": subplot_id,
    "backend": intent["backend"],
    "dispatch_intent_id": intent["key"],
    "leaf_saga_id": leaf,
    "run_identity": intent["run_identity"],
    "issued_at": time.time(),
}
payload = json.dumps(receipt).encode("utf-8")
digest = hashlib.sha256(payload).hexdigest()
prefix = f"{wc.emit(wc.USER_STATE_ROOT)}{root.name}/"
state_root = Path(prefix).expanduser()
receipts_dir = state_root / "dispatch-receipts"
receipts_dir.mkdir(parents=True, exist_ok=True)
for directory in (state_root, receipts_dir):
    os.chmod(directory, os.stat(directory).st_mode & ~0o022)
marker = state_root / ".repo-identity.json"
marker.write_text(
    json.dumps(
        {
            "schema": "saga.workflow-repo-identity.v1",
            "repo_root_sha256": hashlib.sha256(root.as_posix().encode()).hexdigest(),
        }
    ),
    encoding="utf-8",
)
os.chmod(marker, 0o644)
receipt_file = receipts_dir / "acceptance-launch.json"
receipt_file.write_bytes(payload)
os.chmod(receipt_file, 0o644)
print(json.dumps({"ref": f"{prefix}dispatch-receipts/acceptance-launch.json#sha256={digest}", "leaf": leaf}))
"""

# Crash-window driver (R5): the injected dispatcher IS the write-once fake backend. Modes:
# ``raise`` refuses before any effect; ``crash-after`` writes the effect then dies mid-tick;
# ``recover`` is the idempotent retry (second O_EXCL attempt must find the first write).
_CRASH_ADVANCE_SNIPPET = """
import json
import os
import sys

sys.path.insert(0, sys.argv[1])
from pathlib import Path

import outcome
import outcome_dispatcher

root = Path(sys.argv[2])
outcome_id = sys.argv[3]
mode = sys.argv[4]
effect_path = Path(sys.argv[5])


def dispatcher(req):
    if mode == "raise":
        raise outcome_dispatcher.DispatcherError("acceptance crash-before-effect injection")
    leaf = f"leaf-{req.outcome_id}-{req.subplot_id}"
    try:
        fd = os.open(str(effect_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if mode == "recover":
            return leaf  # idempotent backend: the effect already happened exactly once
        raise outcome_dispatcher.DispatcherError("write-once backend refused a second effect")
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump({"writer": mode, "pid": os.getpid()}, handle)
    if mode == "crash-after":
        os._exit(9)
    return leaf


try:
    result = outcome.advance(root, outcome_id, dispatcher=dispatcher, lease_ttl=0.5)
except Exception as exc:  # noqa: BLE001 - the crash driver reports, never masks
    print(json.dumps({"error": type(exc).__name__}))
    raise SystemExit(8)
print(json.dumps({"dispatched": result.dispatched, "halted": len(result.halted)}))
"""


def _ledger_records(clone: Path, outcome_id: str) -> list[dict[str, Any]]:
    ledger = clone / ".git" / "saga-outcomes" / outcome_id / "ledger.jsonl"
    if not ledger.exists():
        return []
    return [
        json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _chain_summary(records: list[dict[str, Any]], subplot_id: str) -> dict[str, Any]:
    """One leaf's dispatch-chain census across both runtime vocabularies."""
    mine = [rec for rec in records if rec.get("subplot_id") == subplot_id]
    legacy = [rec for rec in mine if rec.get("kind") == "dispatch"]
    native = [rec for rec in mine if rec.get("kind") == "outcome.dispatch.v2"]
    acks = [rec for rec in native if rec.get("phase") in ("ack", "authority-ack")]
    return {
        "legacy_intents": sum(1 for rec in legacy if rec.get("phase") == "intent"),
        "legacy_commits": sum(1 for rec in legacy if rec.get("phase") == "commit"),
        "v2_intents": sum(1 for rec in native if rec.get("phase") == "intent"),
        "v2_acks": len(acks),
        "ack_kinds": sorted({str(rec.get("ack_kind")) for rec in acks}),
        "settled_chains": (
            sum(1 for rec in legacy if rec.get("phase") == "commit")
            + sum(1 for rec in acks if rec.get("ack_kind") == "launched")
        ),
    }


@dataclass
class RaceRig:
    """Per-scenario U4 state: a fresh single-leaf topology with an approved frontier."""

    topo: Topology
    broker_root: Path

    def summary(self) -> dict[str, Any]:
        return _chain_summary(_ledger_records(self.topo.clone_a, self.topo.outcome_id), "race-leaf")


def _race_rig(bench: Workbench, scenario: str, creator: str) -> RaceRig:
    broker_root = _private_dir(bench.workdir / f"broker-u4-{scenario}")
    topo = build_topology(
        bench,
        creator=creator,
        outcome_id=f"xr-u4-{scenario}",
        nodes=RACE_NODES,
        fixtures={"pr:12": {"state": "OPEN", "mergedAt": None}},
    )
    approved = bench.runtime(creator).outcome(
        "approve",
        topo.outcome_id,
        repo_root=topo.clone_a,
        fleet_state_dir=broker_root,
        path_prefix=topo.gh_bin,
    )
    if approved.returncode != 0:
        raise HarnessError("race-approve", f"{scenario}: rc={approved.returncode}")
    return RaceRig(topo=topo, broker_root=broker_root)


def _cli_advance(bench: Workbench, rig: RaceRig, runtime: str) -> tuple[int, dict[str, Any]]:
    result = bench.runtime(runtime).outcome(
        "advance",
        rig.topo.outcome_id,
        repo_root=rig.topo.clone_a,
        fleet_state_dir=rig.broker_root,
        path_prefix=rig.topo.gh_bin,
    )
    payload: dict[str, Any] = {}
    for line in result.stdout.splitlines():
        if line.startswith("{"):
            payload = json.loads(line)
            break
    return result.returncode, payload


def _scenario_claude_first(bench: Workbench, rig: RaceRig) -> dict[str, Any]:
    """R5 ordering + the Claude half of R6: Codex observes shared settlement, invents nothing."""
    rc, first = _cli_advance(bench, rig, "claude")
    if rc != 0 or first.get("dispatched") != ["race-leaf"]:
        raise HarnessError("race-claude-first", f"claude advance rc={rc}")
    after_claude = rig.summary()
    if after_claude["legacy_commits"] != 1 or after_claude["settled_chains"] != 1:
        raise HarnessError("race-claude-first", f"unexpected chain {after_claude}")
    rc, second = _cli_advance(bench, rig, "codex")
    if rc != 0 or second.get("dispatched"):
        raise HarnessError("race-claude-first", f"codex follow-up rc={rc} re-dispatched")
    final = rig.summary()
    if final != after_claude:
        raise HarnessError("race-claude-first", f"codex follow-up mutated the chain: {final}")
    if final["v2_acks"] != 0:
        raise HarnessError("race-claude-first", "codex invented a native ack (R6)")
    return {"chain": final}


def _scenario_codex_first(bench: Workbench, rig: RaceRig) -> dict[str, Any]:
    """R6: the full codex-native chain, then Claude must observe shared settlement."""
    rc, first = _cli_advance(bench, rig, "codex")
    if rc != 0:
        raise HarnessError("race-codex-first", f"codex advance rc={rc}")
    after_intent = rig.summary()
    if after_intent["v2_intents"] != 1 or after_intent["settled_chains"] != 0:
        raise HarnessError("race-codex-first", f"native intent missing: {after_intent}")

    effect = bench.workdir / "effect-codex-first.json"
    prepared = bench.codex.python(
        _CODEX_LAUNCH_PREP_SNIPPET,
        str(rig.topo.clone_a),
        rig.topo.outcome_id,
        "race-leaf",
        str(effect),
        repo_root=rig.topo.clone_a,
        fleet_state_dir=rig.broker_root,
    )
    if prepared.returncode != 0:
        raise HarnessError("race-codex-first", f"launch prep rc={prepared.returncode}")
    launch = json.loads(prepared.stdout.strip().splitlines()[-1])
    acked = bench.codex.outcome(
        "reconcile-dispatch",
        rig.topo.outcome_id,
        "race-leaf",
        "--ack-kind",
        "launched",
        "--dispatch-ack-ref",
        launch["ref"],
        "--leaf-saga-id",
        launch["leaf"],
        repo_root=rig.topo.clone_a,
        fleet_state_dir=rig.broker_root,
        path_prefix=rig.topo.gh_bin,
    )
    if acked.returncode != 0:
        raise HarnessError(
            "race-codex-first", f"launched ack refused: {_bounded(acked.stderr or acked.stdout)}"
        )
    after_ack = rig.summary()
    if after_ack["v2_acks"] != 1 or after_ack["ack_kinds"] != ["launched"]:
        raise HarnessError("race-codex-first", f"launched ack chain missing: {after_ack}")

    rc, follow = _cli_advance(bench, rig, "claude")
    if rc != 0:
        raise HarnessError("race-codex-first", f"claude follow-up rc={rc}")
    final = rig.summary()
    if follow.get("dispatched") or final["settled_chains"] != 1 or final["legacy_commits"] != 0:
        raise HarnessError(
            "race-codex-first",
            "claude re-dispatched a leaf codex already settled natively: "
            f"claude dispatched {follow.get('dispatched')}, chain {final}",
            facts={"chain": final, "claude_dispatched": follow.get("dispatched")},
        )
    if not effect.exists():
        raise HarnessError("race-codex-first", "write-once backend effect missing")
    return {"chain": final, "effect_writer": json.loads(effect.read_text())["writer"]}


def _scenario_simultaneous(bench: Workbench, rig: RaceRig) -> dict[str, Any]:
    """R5: barrier-released two-OS-process race; overlap proven by enter/exit receipts."""
    control = bench.workdir / "race-control"
    control.mkdir(exist_ok=True)
    barrier = control / "go"
    procs: dict[str, subprocess.Popen[str]] = {}
    for name in ("claude", "codex"):
        runtime = bench.runtime(name)
        ready = control / f"ready-{name}"
        procs[name] = subprocess.Popen(  # noqa: S603 — fixed argv, hermetic env
            [
                sys.executable,
                "-c",
                _BARRIER_ADVANCE_SNIPPET,
                str(runtime.install_root / "plugins/saga/scripts"),
                str(ready),
                str(barrier),
                str(rig.topo.clone_a),
                rig.topo.outcome_id,
            ],
            cwd=runtime.install_root,
            env=runtime.env(
                fleet_state_dir=rig.broker_root,
                repo_root=rig.topo.clone_a,
                path_prefix=rig.topo.gh_bin,
            ),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    deadline = time.time() + 30
    while not all((control / f"ready-{name}").exists() for name in procs):
        if time.time() > deadline:
            for proc in procs.values():
                proc.kill()
            raise HarnessError("race-simultaneous", "children never reached the barrier")
        time.sleep(0.005)
    barrier.write_text("go", encoding="utf-8")
    receipts: dict[str, dict[str, Any]] = {}
    for name, proc in procs.items():
        stdout, _stderr = proc.communicate(timeout=_TIMEOUT_S)
        if proc.returncode != 0:
            raise HarnessError("race-simultaneous", f"{name} child rc={proc.returncode}")
        receipts[name] = json.loads(stdout.strip().splitlines()[-1])
    overlap = {
        name: {"enter_ns": r["enter_ns"], "exit_ns": r["exit_ns"], "rc": r["rc"]}
        for name, r in receipts.items()
    }
    if max(r["enter_ns"] for r in receipts.values()) >= min(
        r["exit_ns"] for r in receipts.values()
    ):
        # A scheduling artifact, not a contract verdict: the distinct code lets the unit loop
        # retry on a fresh rig instead of reading a saturated host as a defect (KTD2 demands
        # TRUE overlap, so a serialized run proves nothing either way).
        raise HarnessError(
            "race-serialized", "processes serialized; no true overlap", facts={"overlap": overlap}
        )

    # Loser-retry: both runtimes advance again after the dust settles.
    for name in ("claude", "codex"):
        rc, _payload = _cli_advance(bench, rig, name)
        if rc != 0:
            raise HarnessError("race-simultaneous", f"{name} retry rc={rc}")
    final = rig.summary()
    dangling_native = final["v2_intents"] - sum(
        1 for kind in final["ack_kinds"] if kind == "launched"
    )
    if final["settled_chains"] != 1:
        raise HarnessError(
            "race-simultaneous",
            f"expected exactly one settled chain: {final}",
            facts={"chain": final, "overlap": overlap},
        )
    if final["legacy_intents"] != final["legacy_commits"] or (
        final["v2_acks"] == 0 and dangling_native > 0
    ):
        raise HarnessError(
            "race-simultaneous",
            f"dangling dispatch unit: {final}",
            facts={"chain": final, "overlap": overlap},
        )
    return {"chain": final, "overlap": overlap}


def _crash_advance(
    bench: Workbench, rig: RaceRig, mode: str, effect: Path
) -> subprocess.CompletedProcess[str]:
    return bench.claude.python(
        _CRASH_ADVANCE_SNIPPET,
        str(rig.topo.clone_a),
        rig.topo.outcome_id,
        mode,
        str(effect),
        repo_root=rig.topo.clone_a,
        fleet_state_dir=rig.broker_root,
        path_prefix=rig.topo.gh_bin,
    )


def _scenario_crash(bench: Workbench, rig: RaceRig, *, crash_mode: str) -> dict[str, Any]:
    """R5 crash windows: the write-once backend proves at most one effect across the retry."""
    effect = bench.workdir / f"effect-{crash_mode}.json"
    crashed = _crash_advance(bench, rig, crash_mode, effect)
    if crashed.returncode == 0:
        raise HarnessError("race-crash", f"{crash_mode}: driver did not crash")
    mid = rig.summary()
    if mid["legacy_commits"] != 0:
        raise HarnessError("race-crash", f"{crash_mode}: commit landed despite the crash")
    if crash_mode == "raise" and effect.exists():
        raise HarnessError("race-crash", "crash-before-effect still produced an effect")
    if crash_mode == "crash-after" and not effect.exists():
        raise HarnessError("race-crash", "crash-after-effect lost its effect")

    # Recovery: POLL past the crashed holder's 0.5s coordinator/dispatch leases instead of
    # trusting a single fixed sleep — on a saturated host the lease can outlive a fixed margin,
    # and a retried recovery attempt is harmless (settlement is idempotent, the effect is
    # write-once). Only a deadline exhaust is a contract failure.
    deadline = time.monotonic() + 10
    recovered = _crash_advance(bench, rig, "recover", effect)
    while recovered.returncode != 0 or rig.summary()["legacy_commits"] != 1:
        if time.monotonic() > deadline:
            raise HarnessError(
                "race-crash",
                f"{crash_mode}: recovery never settled: rc={recovered.returncode} "
                f"{_bounded(recovered.stderr or recovered.stdout)}",
            )
        time.sleep(0.3)
        recovered = _crash_advance(bench, rig, "recover", effect)
    final = rig.summary()
    if final["legacy_commits"] != 1 or not effect.exists():
        raise HarnessError("race-crash", f"{crash_mode}: recovery did not settle once: {final}")
    writer = json.loads(effect.read_text(encoding="utf-8"))["writer"]
    expected_writer = "recover" if crash_mode == "raise" else "crash-after"
    if writer != expected_writer:
        raise HarnessError("race-crash", f"{crash_mode}: effect written twice ({writer})")
    return {"chain": final, "effect_writer": writer, "intents_documented": final["legacy_intents"]}


@unit("u4-race")
def unit_race(bench: Workbench) -> list[ScenarioResult]:
    """R5/R6: orderings, a true two-process race, and crash windows over one ready leaf."""
    scenarios: list[tuple[str, str, Callable[[RaceRig], dict[str, Any]], str]] = [
        ("race-claude-first", "claude", lambda rig: _scenario_claude_first(bench, rig), "R5"),
        ("race-codex-first", "codex", lambda rig: _scenario_codex_first(bench, rig), "R6"),
        ("race-simultaneous", "claude", lambda rig: _scenario_simultaneous(bench, rig), "R5"),
        (
            "race-crash-before-effect",
            "claude",
            lambda rig: _scenario_crash(bench, rig, crash_mode="raise"),
            "R5",
        ),
        (
            "race-crash-after-effect",
            "claude",
            lambda rig: _scenario_crash(bench, rig, crash_mode="crash-after"),
            "R5",
        ),
    ]
    results: list[ScenarioResult] = []
    for scenario_id, creator, run, requirement in scenarios:
        started = time.monotonic()
        facts: dict[str, Any] = {}
        verdict, summary = "pass", ""
        try:
            # "race-serialized" is a scheduling artifact (no true overlap), not a verdict —
            # retry on a FRESH rig (a raced rig is already dispatched) up to three times.
            for attempt in range(1, 4):
                suffix = "" if attempt == 1 else f"-r{attempt}"
                rig = _race_rig(bench, scenario_id.removeprefix("race-") + suffix, creator)
                try:
                    facts = run(rig)
                    break
                except HarnessError as exc:
                    if exc.code != "race-serialized" or attempt == 3:
                        raise
            summary = f"{scenario_id}: exactly one settled dispatch chain, contract held"
        except HarnessError as exc:
            verdict = "fail"
            summary = f"{exc.code}: {_bounded(exc.detail)}"
            facts = exc.facts
        results.append(
            ScenarioResult(
                scenario_id=scenario_id,
                requirement=requirement,
                verdict=verdict,
                summary=summary,
                facts=facts,
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        )
    return results


# --------------------------------------------------------------------------- U5 teardown (R8/R9)

DONE_NODES: list[dict[str, Any]] = [
    {
        "subplot_id": "done-leaf",
        "title": "Merged code leaf",
        "backend": "inline",
        "kind": "code",
        "github": {"pr": "infiquetra/xr-fixture-target#11"},
    }
]


def _rig_state(rig: RaceRig) -> dict[str, dict[str, str]]:
    return {
        "store": _tree_state(rig.topo.clone_a / ".git" / "saga-outcomes"),
        "broker": _tree_state(rig.broker_root),
    }


def _fleet_doctor(bench: Workbench, rig: RaceRig) -> dict[str, Any]:
    """Run the INSTALLED claude fleet doctor (#353) strictly read-only over one rig."""
    doctor = bench.claude.install_root / "plugins/saga/scripts/fleet_doctor.py"
    before = _rig_state(rig)
    result = _run(
        [
            sys.executable,
            str(doctor),
            "--repo-root",
            str(rig.topo.clone_a),
            "--lease-store",
            str(rig.broker_root),
            "--format",
            "json",
        ],
        cwd=bench.claude.install_root,
        env=bench.claude.env(fleet_state_dir=rig.broker_root, repo_root=rig.topo.clone_a),
    )
    if result.returncode not in (0, 1):  # 1 = findings present, still a valid report
        raise HarnessError(
            "doctor-run", f"fleet doctor rc={result.returncode}: {_bounded(result.stderr)}"
        )
    if _rig_state(rig) != before:
        raise HarnessError("doctor-mutation", "fleet doctor mutated the rig (must be read-only)")
    report: dict[str, Any] = json.loads(result.stdout)
    if report.get("schema") != "fleet_doctor_report.v1" or report.get("complete") is not True:
        raise HarnessError("doctor-run", "fleet doctor report incomplete or wrong schema")
    return report


def _scenario_reclaim(bench: Workbench, rig: RaceRig) -> dict[str, Any]:
    """R9: harvest-complete the rig, then reclamation twice per runtime must be a no-op."""
    rc, first = _cli_advance(bench, rig, "claude")
    if rc != 0 or first.get("harvested") != ["done-leaf"]:
        raise HarnessError("reclaim", f"initial advance rc={rc} harvested={first.get('harvested')}")
    if not first.get("status", {}).get("complete"):
        raise HarnessError("reclaim", "outcome did not read complete after harvest")
    # Warm-up pass: each runtime's FIRST touch lays down one-time lock-guard scaffolding
    # (e.g. locks/.coordinator.lock.guard) — creation artifacts, not coordination state.
    for name in ("claude", "codex"):
        rc, payload = _cli_advance(bench, rig, name)
        if rc != 0 or payload.get("dispatched"):
            raise HarnessError("reclaim", f"{name} warm-up pass rc={rc} dispatched")
    settled = _rig_state(rig)
    passes = 0
    for _pass in range(2):
        for name in ("claude", "codex"):
            rc, payload = _cli_advance(bench, rig, name)
            if rc != 0 or payload.get("dispatched"):
                raise HarnessError("reclaim", f"{name} reclamation pass rc={rc} dispatched")
            if _rig_state(rig) != settled:
                raise HarnessError("reclaim", f"{name} reclamation pass mutated settled state")
            passes += 1
    return {"reclamation_passes": passes, "complete": True}


def _scenario_doctor(bench: Workbench, clean_rig: RaceRig) -> dict[str, Any]:
    """R9 both halves: zero open positions on the settled rig; a real open position is FLAGGED."""
    clean = _fleet_doctor(bench, clean_rig)
    if clean["counts"]["findings"] != 0:
        diseases = [f.get("disease") for f in clean.get("findings", [])]
        raise HarnessError(
            "doctor-open-positions",
            f"settled rig reports {clean['counts']['findings']} open position(s): {diseases}",
        )
    # Sensitivity half: a dispatched-but-never-settled leaf must be visible, or the zero above
    # is vacuous. Build a rig, dispatch it, leave the execution open.
    open_rig = _race_rig(bench, "doctor-open", "claude")
    rc, payload = _cli_advance(bench, open_rig, "claude")
    if rc != 0 or payload.get("dispatched") != ["race-leaf"]:
        raise HarnessError("doctor-open-positions", f"open-rig dispatch rc={rc}")
    flagged = _fleet_doctor(bench, open_rig)
    # The sensitivity half must flag the PLANTED class — a dispatched-but-unsettled leaf reads
    # as an unledgered spawn — not merely any disease, or the zero above stays vacuous for
    # exactly the class this scenario exists to prove.
    if flagged["counts"]["findings"] < 1 or "unledgered-spawn" not in flagged["counts"].get(
        "by_disease", {}
    ):
        raise HarnessError(
            "doctor-open-positions",
            f"doctor missed the dispatched-unsettled class: {flagged['counts']}",
        )
    return {
        "clean_findings": clean["counts"]["findings"],
        "open_rig_findings": flagged["counts"]["findings"],
        "open_rig_diseases": flagged["counts"]["by_disease"],
    }


def _scenario_legacy_import(bench: Workbench, rig: RaceRig) -> dict[str, Any]:
    """R8: both installed runtimes refuse legacy bundle import with zero writes.

    The refusal is UNCONDITIONAL by upstream design (#604 R10/R7): the CLI never reads the
    bundle file, so the retirement receipt cannot depend on it existing or parsing. The fixture
    below only makes the invocation realistic; the load-bearing oracle is the retirement
    receipt TEXT plus the zero-write spy — not any schema sniffing.
    """
    bundle = bench.workdir / "legacy-bundle.json"
    bundle.write_text(
        json.dumps({"schema": "outcome-bundle/1", "outcome_id": rig.topo.outcome_id}),
        encoding="utf-8",
    )
    refusals: dict[str, str] = {}
    for name in ("claude", "codex"):
        before = _tree_state(rig.topo.clone_b / ".git" / "saga-outcomes")
        result = bench.runtime(name).outcome(
            "import",
            str(bundle),
            repo_root=rig.topo.clone_b,
            fleet_state_dir=rig.broker_root,
            path_prefix=rig.topo.gh_bin,
        )
        if result.returncode == 0:
            raise HarnessError("legacy-import", f"{name} import did not refuse")
        # Pin the refusal REASON, not just a non-zero exit: a crash or argparse error must not
        # read as "contract held".
        blob = (result.stderr or "") + (result.stdout or "")
        if "legacy bundle import is retired" not in blob:
            raise HarnessError(
                "legacy-import",
                f"{name} refusal lacks the retirement receipt: {_bounded(blob)}",
            )
        if _tree_state(rig.topo.clone_b / ".git" / "saga-outcomes") != before or _store_dirs(
            rig.topo.clone_b
        ):
            raise HarnessError("legacy-import", f"{name} refusal wrote state")
        refusals[name] = f"rc={result.returncode} retirement-receipt"
    return {"refusals": refusals}


@unit("u5-teardown")
def unit_teardown(bench: Workbench) -> list[ScenarioResult]:
    """R8/R9: idempotent reclamation, fleet-doctor open-position audit, dead legacy import."""
    started = time.monotonic()
    results: list[ScenarioResult] = []
    settled_rig: RaceRig | None = None
    try:
        broker_root = _private_dir(bench.workdir / "broker-u5")
        topo = build_topology(
            bench,
            creator="claude",
            outcome_id="xr-u5-teardown",
            nodes=DONE_NODES,
            fixtures={"pr:11": {"state": "MERGED", "mergedAt": "2026-07-20T00:00:00Z"}},
        )
        approved = bench.claude.outcome(
            "approve",
            topo.outcome_id,
            repo_root=topo.clone_a,
            fleet_state_dir=broker_root,
            path_prefix=topo.gh_bin,
        )
        if approved.returncode != 0:
            raise HarnessError("race-approve", f"u5 approve rc={approved.returncode}")
        settled_rig = RaceRig(topo=topo, broker_root=broker_root)
    except HarnessError as exc:
        results.append(
            ScenarioResult(
                scenario_id="teardown-reclaim",
                requirement="R9",
                verdict="fail",
                summary=f"{exc.code}: {_bounded(exc.detail)}",
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        )
        return results

    for scenario_id, requirement, run in (
        ("teardown-reclaim", "R9", lambda: _scenario_reclaim(bench, settled_rig)),
        ("fleet-doctor-positions", "R9", lambda: _scenario_doctor(bench, settled_rig)),
        ("legacy-import-refused", "R8", lambda: _scenario_legacy_import(bench, settled_rig)),
    ):
        started = time.monotonic()
        facts: dict[str, Any] = {}
        verdict, summary = "pass", ""
        try:
            facts = run()
            summary = f"{scenario_id}: contract held"
        except HarnessError as exc:
            verdict = "fail"
            summary = f"{exc.code}: {_bounded(exc.detail)}"
            facts = exc.facts
        results.append(
            ScenarioResult(
                scenario_id=scenario_id,
                requirement=requirement,
                verdict=verdict,
                summary=summary,
                facts=facts,
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        )
    return results


# --------------------------------------------------------------------------- main

# R2: each INSTALLED runtime independently resolves the canonical broker root from the hermetic
# child environment (the same resolution the CLIs use at run time) — the harness then asserts
# both agree AND match the configured root, so the recorded digest is run-derived agreement
# evidence, never a constant.
_BROKER_RESOLVE_SNIPPET = """
import json
import os
import sys

sys.path.insert(0, sys.argv[1])

import fleet_commons_shim

lease_broker = fleet_commons_shim.load("lease_broker")
print(json.dumps({"resolved": str(lease_broker.resolve_state_root(dict(os.environ)))}))
"""


def _resolved_broker_digest(
    runtimes: dict[str, InstalledRuntime], broker_root: Path, workdir: Path
) -> str:
    """Digest of the workbench-relative broker root, proven identical across both runtimes."""
    resolved: dict[str, Path] = {}
    for name, runtime in runtimes.items():
        probe = runtime.python(
            _BROKER_RESOLVE_SNIPPET, repo_root=workdir, fleet_state_dir=broker_root
        )
        if probe.returncode != 0:
            raise HarnessError(
                "broker-root-divergence",
                f"{name} broker-root resolve rc={probe.returncode}: {_bounded(probe.stderr)}",
            )
        resolved[name] = Path(
            json.loads(probe.stdout.strip().splitlines()[-1])["resolved"]
        ).resolve()
    if len(set(resolved.values())) != 1 or next(iter(resolved.values())) != broker_root.resolve():
        raise HarnessError(
            "broker-root-divergence",
            "runtimes disagree on the canonical broker root: "
            + ", ".join(f"{n}={_bounded(str(p))}" for n, p in resolved.items()),
        )
    relative = next(iter(resolved.values())).relative_to(workdir.resolve())
    return _sha256_text(str(relative))


def _child_env_names(runtimes: dict[str, InstalledRuntime], broker_root: Path) -> list[str]:
    """The allowlisted names actually SET in the hermetic child env — child truth, not
    the harness's own ``os.environ`` (R2/R10). Any out-of-list child name is a halt."""
    names: set[str] = set()
    for runtime in runtimes.values():
        names |= set(runtime.env(fleet_state_dir=broker_root, repo_root=runtime.install_root))
    unlisted = sorted(names - set(ENV_NAME_ALLOWLIST))
    if unlisted:
        raise HarnessError(
            "env-name-unlisted", f"child env names outside the closed allowlist: {unlisted}"
        )
    return [name for name in ENV_NAME_ALLOWLIST if name in names]


def _should_keep(flag: bool, scenarios: list[ScenarioResult], halt: dict[str, str] | None) -> bool:
    """Failed or halted runs always retain the workdir for post-mortem inspection."""
    return flag or halt is not None or any(s.verdict != "pass" for s in scenarios)


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
        help=(
            "retain the temporary work directory (runs with any failing scenario, or halts, "
            "always retain it)"
        ),
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
    env_names_set: list[str] = []
    try:
        claude_identity = require_clean_pinned(claude_pin)
        codex_identity = require_clean_pinned(codex_pin)
        digests = contract_digests(claude_pin, codex_pin)
        claude_rt = install_isolated(claude_pin, workdir)
        codex_rt = install_isolated(codex_pin, workdir)
        claude_identity["readback"] = claude_rt.identity
        codex_identity["readback"] = codex_rt.identity
        broker_root = workdir / "broker-root"
        _private_dir(broker_root)
        runtimes = {"claude": claude_rt, "codex": codex_rt}
        broker_root_digest = _resolved_broker_digest(runtimes, broker_root, workdir)
        env_names_set = _child_env_names(runtimes, broker_root)
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
    finally:
        bundle = build_bundle(
            claude=claude_pin,
            codex=codex_pin,
            claude_identity=claude_identity,
            codex_identity=codex_identity,
            digests=digests,
            broker_root_digest=broker_root_digest,
            scenarios=scenarios,
            env_names_set=env_names_set,
            started_at_iso=started,
            halt=halt,
        )
        assert_privacy(bundle)
        bundle_sha = atomic_write_json(args.output, bundle)
        print(json.dumps({"ok": halt is None, "bundle_sha256": bundle_sha}))
        if not _should_keep(args.keep_workdir, scenarios, halt):
            shutil.rmtree(workdir, ignore_errors=True)
    if halt:
        return 2
    return 0 if all(s.verdict == "pass" for s in scenarios) else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
