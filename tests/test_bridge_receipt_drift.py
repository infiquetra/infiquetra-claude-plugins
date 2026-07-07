"""Bridge-enumeration drift guard (plan U7, #383 R10/DoD 4, KTD9).

Every ``receipt_emitter`` tag declared in the live engine registry must resolve to a bridge
that provably emits a ``bridge_receipt.v1`` through the *shared* fleet-commons path
(``fleet_commons_shim.load("bridge_receipt").emit_receipt(...)``). In-repo emitters
(``http-bridge``, ``agy-delegate``) are proven by static analysis of their source; emitters that
are named in the registry but not yet wired in-repo live in ``PENDING_EMITTERS`` as an explicit,
issue-pinned entry (``codex-bridge`` -> #476, landing with the ``plugins/codex/`` work).

Forcing-function discipline (journal ``{#verify-the-guard-reds}``): a guard is only trustworthy if
it is shown to red on the drift it claims to catch. This module therefore also proves that the
matcher goes red when the emit call is stubbed out of a real emitter, and that it is not fooled by
a realistic evasion (an aliased import / renamed local that only *looks* like it emits).

HERMETIC CONTRACT: every red condition here reads filesystem and parsed-registry state ONLY.
There is NO network access and NO GitHub-issue-state lookup anywhere in this module -- the pending
entry is a static, dated declaration, and its "has the plugin landed yet" check is a pure
directory-existence test. (An issue-state probe would make the suite non-hermetic and flaky, so it
is deliberately excluded per the U7 spec.)
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parent.parent
REGISTRY_PATH = ROOT / "plugins" / "saga" / "references" / "engine-registry.yaml"
REGISTRY_SCRIPT = ROOT / "plugins" / "saga" / "scripts" / "engine_registry.py"

# --- Emitter tag -> in-repo source file that must contain the shared emit call. ----------------
IN_REPO_EMITTERS: dict[str, Path] = {
    "http-bridge": ROOT / "plugins" / "saga" / "scripts" / "engine_bridge_http.py",
    "agy-delegate": ROOT / "plugins" / "agy" / "scripts" / "agy_delegate.py",
}

# --- Emitters named in the registry with NO in-repo wiring yet, each pinned to its tracking -----
# issue. Dated explicit declaration (KTD9): codex-bridge lands with #476's ``plugins/codex/`` work.
# The value is the issue reference for humans; NOTHING in this module queries its live state.
PENDING_EMITTERS: dict[str, str] = {"codex-bridge": "#476"}

# The plugin directory whose appearance means a pending emitter must now be wired in-repo.
# Purely a filesystem sentinel -- no network, no issue-state.
PENDING_EMITTER_PLUGIN_DIR: dict[str, Path] = {"codex-bridge": ROOT / "plugins" / "codex"}

# --- Shared-path vocabulary (KTD6): the one and only sanctioned emit route. --------------------
_SHIM_MODULE = "fleet_commons_shim"
_SHIM_LOADER_ATTR = "load"  # fleet_commons_shim.load("bridge_receipt")
_SHARED_LOADER_ARG = "bridge_receipt"
_SHARED_EMIT_ATTR = "emit_receipt"


# ================================================================================================
# Registry enumeration (hermetic: reads the yaml, no live services).
# ================================================================================================
def _load_registry_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("engine_registry_drift", REGISTRY_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _registry_emitters() -> set[str]:
    module = _load_registry_module()
    registry = module.Registry.load(REGISTRY_PATH)
    return {entry.receipt_emitter for entry in registry.engines}


# ================================================================================================
# Static shared-path matcher (hermetic: AST of source text, never imports/executes the emitter).
# Alias-robust by design so a legitimate refactor (aliased import, renamed local handle) still
# passes, while a fake emit that skips the shared handle is rejected.
# ================================================================================================
def _shim_alias_names(tree: ast.AST) -> set[str]:
    """Local names bound to the ``fleet_commons_shim`` module (``import ... as X`` robust)."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == _SHIM_MODULE:
                    names.add(alias.asname or alias.name)
    return names


def _bare_loader_names(tree: ast.AST) -> set[str]:
    """Names bound to the shim's ``load`` via ``from fleet_commons_shim import load [as X]``."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == _SHIM_MODULE:
            for alias in node.names:
                if alias.name == _SHIM_LOADER_ATTR:
                    names.add(alias.asname or alias.name)
    return names


def _is_shared_loader_call(
    value: ast.expr, shim_names: set[str], bare_loader_names: set[str]
) -> bool:
    """True iff ``value`` is ``<shim>.load("bridge_receipt")`` or bare ``load("bridge_receipt")``."""
    if not isinstance(value, ast.Call):
        return False
    func = value.func
    ok_func = False
    if isinstance(func, ast.Attribute) and func.attr == _SHIM_LOADER_ATTR:
        ok_func = isinstance(func.value, ast.Name) and func.value.id in shim_names
    elif isinstance(func, ast.Name):
        ok_func = func.id in bare_loader_names
    if not ok_func or not value.args:
        return False
    arg0 = value.args[0]
    return isinstance(arg0, ast.Constant) and arg0.value == _SHARED_LOADER_ARG


def _receipt_handles(tree: ast.AST, shim_names: set[str], bare_loader_names: set[str]) -> set[str]:
    """Local names assigned the shared receipt module (``_br = shim.load("bridge_receipt")``)."""
    handles: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and _is_shared_loader_call(
            node.value, shim_names, bare_loader_names
        ):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    handles.add(target.id)
        elif (
            isinstance(node, ast.AnnAssign)
            and node.value is not None
            and _is_shared_loader_call(node.value, shim_names, bare_loader_names)
            and isinstance(node.target, ast.Name)
        ):
            handles.add(node.target.id)
    return handles


def emits_through_shared_path(source: str) -> bool:
    """True iff ``source`` calls ``emit_receipt`` on a handle bound to the shared receipt module.

    A bare ``emit_receipt(...)`` (aliased import) or an ``emit_receipt`` attribute on any object
    that is NOT the shared-loader handle (renamed local pointing elsewhere) is rejected -- those
    are exactly the evasions the guard must not be fooled by.
    """
    tree = ast.parse(source)
    shim_names = _shim_alias_names(tree)
    bare_loader_names = _bare_loader_names(tree)
    handles = _receipt_handles(tree, shim_names, bare_loader_names)
    if not handles:
        return False
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == _SHARED_EMIT_ATTR
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in handles
        ):
            return True
    return False


# ================================================================================================
# Accounting: every registered emitter is either wired in-repo or explicitly pending.
# ================================================================================================
def test_every_registry_emitter_is_accounted_for() -> None:
    accounted = set(IN_REPO_EMITTERS) | set(PENDING_EMITTERS)
    unaccounted = _registry_emitters() - accounted
    assert not unaccounted, (
        f"registry declares receipt_emitter(s) {sorted(unaccounted)} that are neither wired "
        f"in-repo (IN_REPO_EMITTERS) nor explicitly pending (PENDING_EMITTERS) -- add wiring "
        f"or a dated pending entry with a tracking issue"
    )


def test_in_repo_and_pending_emitters_are_disjoint() -> None:
    overlap = set(IN_REPO_EMITTERS) & set(PENDING_EMITTERS)
    assert not overlap, f"emitter(s) {sorted(overlap)} listed as both wired and pending"


def test_in_repo_emitter_sources_exist() -> None:
    missing = {tag: str(path) for tag, path in IN_REPO_EMITTERS.items() if not path.is_file()}
    assert not missing, f"declared in-repo emitter source(s) missing on disk: {missing}"


# ================================================================================================
# Every in-repo bridge provably emits through the shared path.
# ================================================================================================
@pytest.mark.parametrize("emitter_tag", sorted(IN_REPO_EMITTERS))
def test_all_bridges_emit_through_shared_path(emitter_tag: str) -> None:
    source = IN_REPO_EMITTERS[emitter_tag].read_text(encoding="utf-8")
    assert emits_through_shared_path(source), (
        f"in-repo emitter {emitter_tag!r} ({IN_REPO_EMITTERS[emitter_tag]}) does not emit a "
        f"bridge_receipt through the shared fleet_commons path"
    )


# ================================================================================================
# Pending-emitter discipline (hermetic: static declaration + directory sentinel only).
# ================================================================================================
def test_pending_emitters_is_the_explicit_dated_entry() -> None:
    # KTD9: exactly the codex-bridge -> #476 entry, no silent skips of anything else.
    assert PENDING_EMITTERS == {"codex-bridge": "#476"}


def test_pending_emitter_plugin_absent_until_wired() -> None:
    """If a pending emitter's plugin directory appears, it must be wired in-repo, not left pending.

    Pure filesystem check -- reds when ``plugins/codex/`` shows up without moving codex-bridge into
    IN_REPO_EMITTERS. No GitHub-issue-state lookup (that would break the hermetic contract).
    """
    for emitter, issue in PENDING_EMITTERS.items():
        plugin_dir = PENDING_EMITTER_PLUGIN_DIR[emitter]
        if plugin_dir.exists():
            assert emitter in IN_REPO_EMITTERS, (
                f"{plugin_dir} now exists but {emitter!r} is still pending ({issue}); wire its "
                f"shared emit call and move it from PENDING_EMITTERS to IN_REPO_EMITTERS"
            )


# ================================================================================================
# Forcing-function red proofs (journal {#verify-the-guard-reds}).
# ================================================================================================
@pytest.mark.parametrize("emitter_tag", sorted(IN_REPO_EMITTERS))
def test_guard_reds_when_emit_call_is_stubbed_out(emitter_tag: str) -> None:
    """Remove the emit call from a real emitter and prove the matcher flips to red.

    Renaming the ``.emit_receipt`` attribute simulates the emit call being deleted/refactored out;
    the guard MUST then report the bridge as non-emitting.
    """
    source = IN_REPO_EMITTERS[emitter_tag].read_text(encoding="utf-8")
    assert emits_through_shared_path(source)  # sanity: it emits before we stub it
    stubbed = source.replace(f".{_SHARED_EMIT_ATTR}(", ".__emit_stubbed_out__(")
    assert stubbed != source, "expected to find an emit call to stub out"
    assert not emits_through_shared_path(stubbed), (
        f"guard failed to red after {emitter_tag!r}'s emit call was stubbed out"
    )


# A genuine, aliased-and-renamed emitter MUST still pass -- proves the matcher is not overfit to
# the literal ``_bridge_receipt`` name and won't red on a legitimate refactor.
_GENUINE_ALIASED = """
import fleet_commons_shim as _fcs
_receipt_mod = _fcs.load("bridge_receipt")


def emit(engine_id):
    return _receipt_mod.emit_receipt(engine_id=engine_id, variant="v", transport="http",
                                     wall_time_s=0.0, bytes_produced=0, runner={})
"""

_GENUINE_FROM_IMPORT = """
from fleet_commons_shim import load as _load_commons
_rm = _load_commons("bridge_receipt")
_rm.emit_receipt(engine_id="e", variant="v", transport="cli", wall_time_s=0.0,
                 bytes_produced=0, runner={})
"""

# Realistic evasions that only LOOK like they emit -- the matcher must reject every one.
# 1. Aliased import of a fake local emit_receipt, called bare (never through the shared handle).
_EVASION_ALIASED_LOCAL = """
import fleet_commons_shim as _fcs
_receipt_mod = _fcs.load("bridge_receipt")  # genuine handle, but deliberately never used to emit


def emit_receipt(**kwargs):
    return {"schema": "bridge_receipt.v1"}   # counterfeit stamp


receipt = emit_receipt(engine_id="x", variant="v", transport="http",
                       wall_time_s=0.0, bytes_produced=0, runner={})
"""

# 2. Renamed local that carries emit_receipt but points at some other object, not the shared module.
_EVASION_RENAMED_LOCAL = """
import fleet_commons_shim as _fcs
_genuine = _fcs.load("bridge_receipt")   # real handle, never emitted through


class _Counterfeit:
    def emit_receipt(self, **kwargs):
        return {"schema": "bridge_receipt.v1"}


_fake = _Counterfeit()
receipt = _fake.emit_receipt(engine_id="x", variant="v", transport="http",
                             wall_time_s=0.0, bytes_produced=0, runner={})
"""


@pytest.mark.parametrize("source", [_GENUINE_ALIASED, _GENUINE_FROM_IMPORT])
def test_matcher_accepts_genuine_aliased_emit(source: str) -> None:
    assert emits_through_shared_path(source)


@pytest.mark.parametrize("source", [_EVASION_ALIASED_LOCAL, _EVASION_RENAMED_LOCAL])
def test_matcher_rejects_realistic_evasion(source: str) -> None:
    assert not emits_through_shared_path(source), (
        "matcher was fooled by a counterfeit emit that bypasses the shared receipt handle"
    )
