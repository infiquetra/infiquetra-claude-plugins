"""End-to-end lifecycle regression harness engine (#428).

Runs canonical lifecycle scenarios (``tests/lifecycle-fixture/scenarios/*.json``) headlessly
against a throwaway copy of the fixture repo and asserts on **artifact shape** — the four
canonical families from the issue's R3:

* ``spec-json-valid``      — a produced spec JSON passes its own production validator
  (``execution_spec.py validate`` for execution specs, ``outcome.load_spec`` for outcome specs).
* ``saga-log-append``      — the saga log gained the expected appended tick(s), read back through
  the production reader (``saga.py ticks``) AND cross-checked against the on-disk tick files.
* ``gate-record``          — a required gate verdict is present on the latest saga tick
  (``saga.py restore`` → ``gate_verdicts``).
* ``worktree-reclaimed``   — every worktree a scenario opened is gone from
  ``git worktree list`` and from ``.saga-worktrees/`` at teardown.

Design constraints baked in from this outcome's refute panels:

* **Fail closed, never enumerate-and-shrug.** A scenario definition with an unknown key, an
  unknown step/assertion kind, or a value of the wrong shape raises
  :class:`LifecycleHarnessError` — it can never silently pass. Likewise an assertion that cannot
  determine the state it is asked about (git unreadable, production reader disagreeing with the
  on-disk artifact) raises instead of passing.
* **Production code paths only.** Steps shell out to the real saga CLIs
  (``plugins/saga/scripts/{saga,execution_spec,outcome}.py``) with the throwaway clone as cwd,
  and the worktree steps drive the real ``outcome_worktrees.ensure_worktree`` /
  ``reap_worktree`` wired to the real ``git_worktree_ops`` adapter — no harness-local
  re-implementation of any lifecycle behavior.
* **Isolation.** Every run happens in a fresh temporary clone built from
  ``tests/lifecycle-fixture/seed/`` (the ``wiring_canary`` throwaway-checkout pattern); the
  parent repo's working tree is never read or written by a scenario.
* **Named violations (R4).** A failed assertion produces a specific violation string built on
  the ``VIOLATION_*`` phrases below (e.g. ``"worktree still present: <path>"``), never a bare
  exit code.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess  # nosec B404 — fixed argv (git + repo-local python CLIs), no shell
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SAGA_SCRIPTS = ROOT / "plugins" / "saga" / "scripts"
FIXTURE_DIR = ROOT / "tests" / "lifecycle-fixture"
SCENARIOS_DIR = FIXTURE_DIR / "scenarios"
SEED_DIR = FIXTURE_DIR / "seed"

# The fixture repo's remote deliberately differs from any real remote (RFC 2606 reserved TLD):
# R1's isolation check is "its `remote -v` differs from the parent repo's".
FIXTURE_REMOTE = "https://fixture.invalid/lifecycle-fixture.git"

# The four canonical artifact-shape families (R3). ``families_checked`` on a result records
# which of these a scenario actually verified — a "healthy" verdict that never names its
# families would be unfalsifiable.
FAMILY_SPEC = "spec-json-valid"
FAMILY_SAGA = "saga-log-append"
FAMILY_GATE = "gate-record"
FAMILY_WORKTREE = "worktree-reclaimed"
CANONICAL_FAMILIES = frozenset({FAMILY_SPEC, FAMILY_SAGA, FAMILY_GATE, FAMILY_WORKTREE})

# R4 violation phrases — exact, stable, and greppable. Tests (and the issue's acceptance
# criteria) match on these substrings, so treat them as a frozen contract.
VIOLATION_WORKTREE = "worktree still present"
VIOLATION_SAGA = "saga log missing entry"
VIOLATION_GATE = "gate record missing"
VIOLATION_SPEC_MISSING = "spec JSON missing"
VIOLATION_SPEC_INVALID = "spec JSON failed validation"

_SUBPROCESS_TIMEOUT = 120


class LifecycleHarnessError(RuntimeError):
    """A scenario could not be strictly understood or executed (fail-closed, never a pass)."""


# ---------------------------------------------------------------------------
# Production module loading (the repo's importlib-by-path idiom, dependency-ordered
# exactly like tests/test_outcome_worktrees.py so lazy sibling imports reuse instances).
# ---------------------------------------------------------------------------


def _load(name: str) -> ModuleType:
    if str(SAGA_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SAGA_SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SAGA_SCRIPTS / f"{name}.py")
    if spec is None or spec.loader is None:
        raise LifecycleHarnessError(f"cannot load production module {name!r}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


SPEC = _load("outcome_spec")
STORE = _load("outcome_store")
_load("outcome_orchestrator")
_load("outcome_dispatcher")
_load("outcome_merge")
OUTCOME = _load("outcome")
WT = _load("outcome_worktrees")

# The production CLIs a scenario step may invoke — an unknown script name is an error.
_ALLOWED_CLIS: dict[str, Path] = {
    "saga": SAGA_SCRIPTS / "saga.py",
    "execution_spec": SAGA_SCRIPTS / "execution_spec.py",
    "outcome": SAGA_SCRIPTS / "outcome.py",
}


# ---------------------------------------------------------------------------
# Fixture repo materialization + throwaway clones
# ---------------------------------------------------------------------------


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # nosec B603 — fixed argv, no shell
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT,
        check=False,
    )


def _git_or_raise(args: list[str], cwd: Path, what: str) -> str:
    proc = _git(args, cwd)
    if proc.returncode != 0:
        raise LifecycleHarnessError(
            f"{what}: git {' '.join(args)} exited {proc.returncode}: "
            f"{(proc.stdout + proc.stderr).strip()[-500:]}"
        )
    return proc.stdout


def _init_repo(path: Path) -> None:
    """``git init`` + deterministic identity + the distinct fixture remote, then commit all files."""
    _git_or_raise(["init", "-q", "-b", "main"], path, "fixture init")
    _git_or_raise(["config", "user.email", "lifecycle-fixture@fixture.invalid"], path, "fixture")
    _git_or_raise(["config", "user.name", "lifecycle-fixture"], path, "fixture")
    _git_or_raise(["remote", "add", "origin", FIXTURE_REMOTE], path, "fixture remote")
    _git_or_raise(["add", "-A"], path, "fixture add")
    _git_or_raise(["commit", "-q", "-m", "seed: lifecycle fixture"], path, "fixture commit")


def ensure_fixture_repo(path: Path = FIXTURE_DIR) -> Path:
    """Materialize the in-tree fixture repo's own ``.git`` (R1). Idempotent.

    Git cannot track a nested ``.git`` directory, so the fixture's repo-ness is materialized
    on demand rather than committed; a nested ``.git`` is also hardcoded-invisible to the
    parent repo's ``git status --porcelain``, so this never dirties the parent tree. Scenario
    runs do NOT execute here — they run in throwaway clones from :func:`make_workdir` — this
    in-tree materialization exists so the fixture is a real, inspectable git repository with a
    remote distinct from the parent repo's.
    """
    if not path.is_dir():
        raise LifecycleHarnessError(f"fixture directory missing: {path}")
    git_dir = path / ".git"
    if git_dir.exists():
        if not git_dir.is_dir():
            raise LifecycleHarnessError(f"{git_dir} exists but is not a directory")
        # Deterministic remote, even if a previous materialization predates a URL change.
        _git_or_raise(["remote", "set-url", "origin", FIXTURE_REMOTE], path, "fixture remote")
        return path
    _init_repo(path)
    return path


def make_workdir(base: Path) -> Path:
    """Build a fresh throwaway fixture clone under ``base`` and return its path.

    Copies ``seed/`` into ``<base>/fixture-clone``, then initializes it as its own git repo
    (distinct remote, deterministic identity, one seed commit). Every scenario gets its own
    clone, so runs are independently attributable (R2) and never touch the parent tree (R1).
    """
    if not SEED_DIR.is_dir():
        raise LifecycleHarnessError(f"fixture seed directory missing: {SEED_DIR}")
    workdir = base / "fixture-clone"
    if workdir.exists():
        raise LifecycleHarnessError(f"workdir already exists: {workdir}")
    shutil.copytree(SEED_DIR, workdir)
    _init_repo(workdir)
    return workdir


# ---------------------------------------------------------------------------
# Strict scenario-definition validation (fail closed on anything not understood)
# ---------------------------------------------------------------------------

_SCENARIO_KEYS = frozenset({"id", "title", "description", "steps", "assertions"})

# kind -> (required keys, optional keys). A step/assertion may carry EXACTLY these keys
# (plus "kind"); anything else is an error, never ignored.
_STEP_SHAPES: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    "write_file": (frozenset({"path"}), frozenset({"text", "json"})),
    "run_saga_cli": (frozenset({"script", "args"}), frozenset()),
    "git": (frozenset({"args"}), frozenset()),
    "worktree_open": (frozenset({"outcome_id", "subplot_id"}), frozenset()),
    "worktree_reclaim": (frozenset({"outcome_id", "subplot_id"}), frozenset()),
}

_ASSERTION_SHAPES: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    "execution_spec_valid": (frozenset({"path"}), frozenset()),
    "saga_log_appended": (frozenset({"saga_id", "min_ticks"}), frozenset()),
    "gate_record_present": (frozenset({"saga_id", "gate"}), frozenset({"state"})),
    "worktree_reclaimed": (frozenset(), frozenset()),
    "outcome_spec_valid": (frozenset({"outcome_id", "expect_nodes"}), frozenset()),
    "outcome_state": (frozenset({"outcome_id", "states"}), frozenset()),
}

# assertion kind -> the artifact-shape family it verifies. ``outcome_state`` is a derived-state
# check on top of the canonical four; it deliberately maps to its own (non-canonical) family so
# it can never masquerade as one of the R3 guarantees.
ASSERTION_FAMILY: dict[str, str] = {
    "execution_spec_valid": FAMILY_SPEC,
    "outcome_spec_valid": FAMILY_SPEC,
    "saga_log_appended": FAMILY_SAGA,
    "gate_record_present": FAMILY_GATE,
    "worktree_reclaimed": FAMILY_WORKTREE,
    "outcome_state": "outcome-derived-state",
}


def _require_str(value: Any, what: str) -> str:
    if not isinstance(value, str) or not value:
        raise LifecycleHarnessError(f"{what} must be a non-empty string, got {value!r}")
    return value


def _require_str_list(value: Any, what: str) -> list[str]:
    if not isinstance(value, list) or not value or not all(isinstance(x, str) for x in value):
        raise LifecycleHarnessError(f"{what} must be a non-empty list of strings, got {value!r}")
    return list(value)


def _check_item_shape(
    item: Any, shapes: dict[str, tuple[frozenset[str], frozenset[str]]], where: str
) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise LifecycleHarnessError(f"{where} must be an object, got {type(item).__name__}")
    kind = item.get("kind")
    if kind not in shapes:
        raise LifecycleHarnessError(f"{where}: unknown kind {kind!r} (known: {sorted(shapes)})")
    required, optional = shapes[kind]
    keys = set(item) - {"kind"}
    missing = required - keys
    unknown = keys - required - optional
    if missing:
        raise LifecycleHarnessError(f"{where} ({kind}): missing required keys {sorted(missing)}")
    if unknown:
        raise LifecycleHarnessError(f"{where} ({kind}): unknown keys {sorted(unknown)}")
    return item


def validate_definition(defn: Any) -> dict[str, Any]:
    """Strictly validate one scenario definition. Anything not understood is an error."""
    if not isinstance(defn, dict):
        raise LifecycleHarnessError(f"scenario must be a JSON object, got {type(defn).__name__}")
    unknown = set(defn) - _SCENARIO_KEYS
    missing = _SCENARIO_KEYS - set(defn)
    if unknown:
        raise LifecycleHarnessError(f"scenario has unknown top-level keys {sorted(unknown)}")
    if missing:
        raise LifecycleHarnessError(f"scenario missing required keys {sorted(missing)}")
    _require_str(defn["id"], "scenario id")
    _require_str(defn["title"], "scenario title")
    _require_str(defn["description"], "scenario description")
    steps = defn["steps"]
    assertions = defn["assertions"]
    if not isinstance(steps, list) or not steps:
        raise LifecycleHarnessError("scenario steps must be a non-empty list")
    if not isinstance(assertions, list) or not assertions:
        raise LifecycleHarnessError("scenario assertions must be a non-empty list")
    for i, step in enumerate(steps):
        _check_item_shape(step, _STEP_SHAPES, f"step {i}")
    for i, assertion in enumerate(assertions):
        _check_item_shape(assertion, _ASSERTION_SHAPES, f"assertion {i}")
    return defn


def load_scenario(path: Path) -> dict[str, Any]:
    """Load + strictly validate a scenario file; its ``id`` must equal the file stem."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LifecycleHarnessError(f"cannot parse scenario file {path}: {exc}") from exc
    defn = validate_definition(raw)
    if defn["id"] != path.stem:
        raise LifecycleHarnessError(
            f"scenario id {defn['id']!r} != file stem {path.stem!r} ({path})"
        )
    return defn


def list_scenarios(directory: Path = SCENARIOS_DIR) -> list[Path]:
    """Every scenario file, sorted. A missing/empty scenarios directory is an error."""
    if not directory.is_dir():
        raise LifecycleHarnessError(f"scenarios directory missing: {directory}")
    paths = sorted(directory.glob("*.json"))
    if not paths:
        raise LifecycleHarnessError(f"no scenario files in {directory}")
    return paths


# ---------------------------------------------------------------------------
# Step execution — every step drives a production code path
# ---------------------------------------------------------------------------


def _safe_rel_path(workdir: Path, rel: str, what: str) -> Path:
    p = Path(rel)
    if p.is_absolute() or ".." in p.parts:
        raise LifecycleHarnessError(f"{what}: path must be relative and traversal-free: {rel!r}")
    return workdir / p


def _run_cli(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # nosec B603 — fixed interpreter + repo-local script, no shell
        argv,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT,
        check=False,
    )


def _step_write_file(step: dict[str, Any], workdir: Path) -> None:
    target = _safe_rel_path(workdir, _require_str(step["path"], "write_file path"), "write_file")
    has_text = "text" in step
    has_json = "json" in step
    if has_text == has_json:  # both or neither
        raise LifecycleHarnessError("write_file needs exactly one of 'text' or 'json'")
    target.parent.mkdir(parents=True, exist_ok=True)
    if has_text:
        target.write_text(_require_str(step["text"], "write_file text"), encoding="utf-8")
    else:
        target.write_text(json.dumps(step["json"], indent=2) + "\n", encoding="utf-8")


def _step_run_saga_cli(step: dict[str, Any], workdir: Path) -> None:
    script = _require_str(step["script"], "run_saga_cli script")
    if script not in _ALLOWED_CLIS:
        raise LifecycleHarnessError(
            f"run_saga_cli: unknown script {script!r} (known: {sorted(_ALLOWED_CLIS)})"
        )
    args = _require_str_list(step["args"], "run_saga_cli args")
    proc = _run_cli([sys.executable, str(_ALLOWED_CLIS[script]), *args], workdir)
    if proc.returncode != 0:
        raise LifecycleHarnessError(
            f"run_saga_cli {script} {' '.join(args)} exited {proc.returncode}: "
            f"{(proc.stdout + proc.stderr).strip()[-500:]}"
        )


def _step_git(step: dict[str, Any], workdir: Path) -> None:
    args = _require_str_list(step["args"], "git args")
    _git_or_raise(args, workdir, "scenario git step")


def _worktree_context(step: dict[str, Any], workdir: Path) -> tuple[Any, Any, Any, Any]:
    """Build the production spec/store/node/ops quartet for a worktree step."""
    outcome_id = _require_str(step["outcome_id"], "worktree outcome_id")
    subplot_id = _require_str(step["subplot_id"], "worktree subplot_id")
    node = SPEC.Node.from_dict(
        {
            "subplot_id": subplot_id,
            "title": subplot_id,
            "kind": "code",
            # child_spec_ref set => Node.is_outcome True => the worktree lifecycle manages it.
            "child_spec_ref": f"child-{subplot_id}",
        }
    )
    spec = SPEC.OutcomeSpec.from_dict(
        {"outcome_id": outcome_id, "objective": "lifecycle-harness", "nodes": [node.to_dict()]}
    )
    store = STORE.Store.for_outcome(outcome_id, workdir).ensure()
    ops = WT.git_worktree_ops(workdir)
    return spec, store, node, ops


def _step_worktree_open(step: dict[str, Any], workdir: Path) -> None:
    spec, store, node, ops = _worktree_context(step, workdir)
    result = WT.ensure_worktree(
        workdir, spec, store, node, ops, owner="lifecycle-harness", at="lifecycle-harness"
    )
    if result.state != "created":
        raise LifecycleHarnessError(
            f"worktree_open for {node.subplot_id!r}: expected 'created', got "
            f"{result.state!r} ({result.reason})"
        )


def _step_worktree_reclaim(step: dict[str, Any], workdir: Path) -> None:
    _spec, store, node, ops = _worktree_context(step, workdir)
    if not WT.reap_worktree(store, node.subplot_id, ops, at="lifecycle-harness"):
        raise LifecycleHarnessError(
            f"worktree_reclaim for {node.subplot_id!r}: reap_worktree reported nothing reclaimed"
        )


_STEP_EXECUTORS = {
    "write_file": _step_write_file,
    "run_saga_cli": _step_run_saga_cli,
    "git": _step_git,
    "worktree_open": _step_worktree_open,
    "worktree_reclaim": _step_worktree_reclaim,
}


# ---------------------------------------------------------------------------
# Assertion execution — each returns a list of NAMED violations (R4), or raises
# LifecycleHarnessError when the state it is asked about cannot be determined.
# ---------------------------------------------------------------------------


def _saga_cli_json(args: list[str], workdir: Path, what: str) -> dict[str, Any]:
    proc = _run_cli([sys.executable, str(_ALLOWED_CLIS["saga"]), *args], workdir)
    if proc.returncode != 0:
        raise LifecycleHarnessError(
            f"{what}: saga.py {' '.join(args)} exited {proc.returncode}: "
            f"{(proc.stdout + proc.stderr).strip()[-500:]}"
        )
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise LifecycleHarnessError(f"{what}: saga.py emitted non-JSON output: {exc}") from exc
    if not isinstance(data, dict):
        raise LifecycleHarnessError(f"{what}: saga.py emitted a non-object payload")
    return data


def _assert_execution_spec_valid(assertion: dict[str, Any], workdir: Path) -> list[str]:
    rel = _require_str(assertion["path"], "execution_spec_valid path")
    target = _safe_rel_path(workdir, rel, "execution_spec_valid")
    if not target.is_file():
        return [f"{VIOLATION_SPEC_MISSING}: {rel}"]
    proc = _run_cli(
        [sys.executable, str(_ALLOWED_CLIS["execution_spec"]), "validate", str(target)], workdir
    )
    if proc.returncode != 0:
        detail = (proc.stdout + proc.stderr).strip()[-500:]
        return [f"{VIOLATION_SPEC_INVALID}: {rel}: {detail}"]
    return []


def _assert_saga_log_appended(assertion: dict[str, Any], workdir: Path) -> list[str]:
    saga_id = _require_str(assertion["saga_id"], "saga_log_appended saga_id")
    min_ticks = assertion["min_ticks"]
    if not isinstance(min_ticks, int) or isinstance(min_ticks, bool) or min_ticks < 1:
        raise LifecycleHarnessError(
            f"saga_log_appended min_ticks must be an int >= 1: {min_ticks!r}"
        )
    data = _saga_cli_json(["ticks", "--saga-id", saga_id], workdir, "saga_log_appended")
    cli_count = data.get("count")
    if not isinstance(cli_count, int):
        raise LifecycleHarnessError("saga_log_appended: saga.py ticks emitted no integer count")
    # Boundary cross-check: the production reader and the persisted tick files must agree —
    # a reader that reports ticks no file backs (or vice versa) is a harness-level error.
    tick_dir = workdir / ".claude" / "saga" / "sagas" / saga_id
    disk_count = len(list(tick_dir.glob("*.md"))) if tick_dir.is_dir() else 0
    if disk_count != cli_count:
        raise LifecycleHarnessError(
            f"saga_log_appended: production reader reports {cli_count} tick(s) but "
            f"{tick_dir} holds {disk_count} — persistence boundary disagreement"
        )
    if cli_count < min_ticks:
        return [
            f"{VIOLATION_SAGA}: expected >= {min_ticks} tick(s) on saga {saga_id!r}, "
            f"found {cli_count}"
        ]
    return []


def _assert_gate_record_present(assertion: dict[str, Any], workdir: Path) -> list[str]:
    saga_id = _require_str(assertion["saga_id"], "gate_record_present saga_id")
    gate = _require_str(assertion["gate"], "gate_record_present gate")
    state = assertion.get("state")
    if state is not None:
        state = _require_str(state, "gate_record_present state")
    data = _saga_cli_json(["restore", "--saga-id", saga_id], workdir, "gate_record_present")
    if data.get("found") is not True:
        return [f"{VIOLATION_GATE}: saga {saga_id!r} has no ticks to carry a {gate!r} verdict"]
    verdicts = data.get("gate_verdicts") or []
    if not isinstance(verdicts, list):
        raise LifecycleHarnessError("gate_record_present: gate_verdicts is not a list")
    for entry in verdicts:
        if not isinstance(entry, str):
            raise LifecycleHarnessError(f"gate_record_present: non-string verdict {entry!r}")
        head, _, rest = entry.partition(":")
        entry_state = rest.partition(":")[0]
        if head == gate and (state is None or entry_state == state):
            return []
    wanted = gate if state is None else f"{gate}:{state}"
    return [f"{VIOLATION_GATE}: no {wanted!r} verdict on saga {saga_id!r} (found: {verdicts!r})"]


def _assert_worktree_reclaimed(_assertion: dict[str, Any], workdir: Path) -> list[str]:
    out = _git_or_raise(["worktree", "list", "--porcelain"], workdir, "worktree_reclaimed")
    main_path = os.path.realpath(workdir)
    leftovers = [
        line[len("worktree ") :]
        for line in out.splitlines()
        if line.startswith("worktree ") and os.path.realpath(line[len("worktree ") :]) != main_path
    ]
    violations = [f"{VIOLATION_WORKTREE}: {path}" for path in sorted(leftovers)]
    # Belt-and-suspenders: a worktree pruned from git's registry but left on disk under the
    # managed root is still a leak (the grounding brief's "15 stale abandoned worktrees" shape).
    managed_root = workdir / ".saga-worktrees"
    if managed_root.is_dir():
        for outcome_dir in sorted(managed_root.iterdir()):
            if not outcome_dir.is_dir():
                continue
            for sub in sorted(outcome_dir.iterdir()):
                if sub.is_dir() and sub.name != "_shared-install":
                    violation = f"{VIOLATION_WORKTREE}: {sub}"
                    if violation not in violations:
                        violations.append(violation)
    return violations


def _assert_outcome_spec_valid(assertion: dict[str, Any], workdir: Path) -> list[str]:
    outcome_id = _require_str(assertion["outcome_id"], "outcome_spec_valid outcome_id")
    expect_nodes = _require_str_list(assertion["expect_nodes"], "outcome_spec_valid expect_nodes")
    rel = f"docs/outcomes/{outcome_id}/outcome-spec.json"
    if not (workdir / rel).is_file():
        return [f"{VIOLATION_SPEC_MISSING}: {rel}"]
    try:
        spec = OUTCOME.load_spec(workdir, outcome_id)  # the production loader validates
    except (OUTCOME.OutcomeError, SPEC.OutcomeSpecError, ValueError) as exc:
        return [f"{VIOLATION_SPEC_INVALID}: {rel}: {exc}"]
    got = sorted(node.subplot_id for node in spec.nodes)
    if got != sorted(expect_nodes):
        return [
            f"{VIOLATION_SPEC_INVALID}: {rel}: node set {got} != expected {sorted(expect_nodes)}"
        ]
    return []


def _assert_outcome_state(assertion: dict[str, Any], workdir: Path) -> list[str]:
    outcome_id = _require_str(assertion["outcome_id"], "outcome_state outcome_id")
    expected = assertion["states"]
    if not isinstance(expected, dict) or not expected:
        raise LifecycleHarnessError("outcome_state states must be a non-empty object")
    try:
        snapshot = OUTCOME.status(workdir, outcome_id)
    except (OUTCOME.OutcomeError, SPEC.OutcomeSpecError, ValueError) as exc:
        return [f"{VIOLATION_SPEC_INVALID}: outcome {outcome_id!r} status unreadable: {exc}"]
    states = snapshot.get("states", {})
    violations = []
    for sid, want in expected.items():
        got = states.get(sid)
        if got != want:
            violations.append(
                f"outcome derived state mismatch: node {sid!r} is {got!r}, expected {want!r}"
            )
    return violations


_ASSERTION_EXECUTORS = {
    "execution_spec_valid": _assert_execution_spec_valid,
    "saga_log_appended": _assert_saga_log_appended,
    "gate_record_present": _assert_gate_record_present,
    "worktree_reclaimed": _assert_worktree_reclaimed,
    "outcome_spec_valid": _assert_outcome_spec_valid,
    "outcome_state": _assert_outcome_state,
}


# ---------------------------------------------------------------------------
# The runner
# ---------------------------------------------------------------------------


@dataclass
class ScenarioResult:
    """What one scenario run actually did and found — the falsifiable record."""

    scenario_id: str
    steps_run: int = 0
    families_checked: set[str] = field(default_factory=set)
    violations: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.violations


def run_scenario(defn: dict[str, Any], workdir: Path) -> ScenarioResult:
    """Execute one validated scenario definition against ``workdir`` (a throwaway clone).

    Steps run in order; a failing step is a :class:`LifecycleHarnessError` (the scenario could
    not be driven — an error, not a red assertion). Assertions then run — ALL of them, so one
    violation never masks another — and their named violations are collected on the result.
    """
    defn = validate_definition(defn)
    if not workdir.is_dir() or not (workdir / ".git").exists():
        raise LifecycleHarnessError(f"workdir is not an initialized fixture clone: {workdir}")
    result = ScenarioResult(scenario_id=defn["id"])
    for i, step in enumerate(defn["steps"]):
        try:
            _STEP_EXECUTORS[step["kind"]](step, workdir)
        except LifecycleHarnessError as exc:
            raise LifecycleHarnessError(
                f"scenario {defn['id']!r} step {i} ({step['kind']}) failed: {exc}"
            ) from exc
        result.steps_run += 1
    for assertion in defn["assertions"]:
        kind = assertion["kind"]
        result.families_checked.add(ASSERTION_FAMILY[kind])
        result.violations.extend(_ASSERTION_EXECUTORS[kind](assertion, workdir))
    return result


def run_scenario_file(path: Path, workdir: Path) -> ScenarioResult:
    return run_scenario(load_scenario(path), workdir)
