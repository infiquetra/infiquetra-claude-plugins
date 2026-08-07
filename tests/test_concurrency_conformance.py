"""Structural drift guard for Saga's bounded executable concurrency emitters."""

from __future__ import annotations

import ast
import importlib.util
import json
import re
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).parent.parent
SAGA_ROOT = ROOT / "plugins/saga"
SCRIPT_DIR = SAGA_ROOT / "scripts"
SOURCE_PATH = SCRIPT_DIR / "execution_spec.py"
INVENTORY_PATH = SAGA_ROOT / "references/concurrency-spawn-sites.md"
DECISIONS_PATH = ROOT / "docs/engineering-journal/DECISIONS.md"
REL_SOURCE = SOURCE_PATH.relative_to(ROOT).as_posix()
HELPER_NAME = "_emit_parallel_wave"
ROW_RE = re.compile(
    r"^\| `(?P<source>plugins/[^`]+)` \| `(?P<function>[^`]+)` "
    r"\| (?P<form>[^|]+) \| `(?P<governor>[^`]+)` \| `(?P<pool>agent|worktree)` "
    r"\| `(?P<acquire>[^`]+)` \| `(?P<bind>[^`]+)` \| `(?P<renew>[^`]+)` "
    r"\| `(?P<release>[^`]+)` \|$"
)
_JS_TRIVIA = r"(?:\s|/\*.*?\*/|//[^\r\n\u2028\u2029]*(?:\r\n?|\n|\u2028|\u2029))*"
PARALLEL_OPEN_RE = re.compile(rf"\bparallel{_JS_TRIVIA}\({_JS_TRIVIA}\[", re.DOTALL)
DYNAMIC_CALLEE_SUFFIX_RE = re.compile(rf"^{_JS_TRIVIA}\({_JS_TRIVIA}\[", re.DOTALL)
FORMAT_CALLEE_RE = re.compile(rf"\{{[^}}]*\}}{_JS_TRIVIA}\({_JS_TRIVIA}\[", re.DOTALL)

InventoryRow = tuple[str, str, str, str, str, str, str, str]
ConcurrencyRow = tuple[str, str, str]
EXPECTED_ROWS: frozenset[InventoryRow] = frozenset(
    {
        (
            REL_SOURCE,
            "_emit_panel_reconciliation",
            "concurrency_governor.ordered_chunks",
            "agent",
            "retired:broker-free-(#677/U4)",
            "retired:broker-free-(#677/U5)",
            "retired:broker-free-(#677/U4)",
            "retired:broker-free-(#677/U4)",
        ),
        (
            REL_SOURCE,
            "emit_workflow_script",
            "concurrency_chunks",
            "agent",
            "retired:broker-free-(#677/U4)",
            "retired:broker-free-(#677/U5)",
            "retired:broker-free-(#677/U4)",
            "retired:broker-free-(#677/U4)",
        ),
        (
            "plugins/saga/hooks/hooks.json",
            "Agent|Task",
            "retired:broker-free-(#677/U5)",
            "agent",
            "retired:broker-free-(#677/U5)",
            "retired:broker-free-(#677/U5)",
            "retired:broker-free-(#677/U5)",
            "retired:broker-free-(#677/U5)",
        ),
        # U6 retired the team-execution lease protocol whole — the row is deleted, not retired.
        # Broker-free rows since #677/U3: the lease lifecycle cells are retired markers; the
        # settlement record is the close-receipt mint, the worktree's ownership its registry entry.
        (
            "plugins/saga/scripts/engine_dispatch.py",
            "_dispatch_once",
            "retired:broker-free-(#677/U3)",
            "agent",
            "retired:broker-free-(#677/U3)",
            "not-applicable:in-process-adapter",
            "retired:broker-free-(#677/U3)",
            "saga.close-receipt.v1:mint",
        ),
        (
            "plugins/saga/scripts/outcome.py",
            "_reconcile_once",
            "retired:broker-free-(#677/U3)",
            "agent",
            "retired:broker-free-(#677/U3)",
            "not-applicable:in-process-adapter",
            "retired:broker-free-(#677/U3)",
            "retired:broker-free-(#677/U3)",
        ),
        (
            "plugins/saga/scripts/outcome_worktrees.py",
            "ensure_worktree",
            "WORKTREE_CAP",
            "worktree",
            "registry.register",
            "not-applicable:registry-entry",
            "retired:broker-free-(#677/U3)",
            "reap_worktree.deregister",
        ),
    }
)
EXPECTED_CONCURRENCY_ROWS: frozenset[ConcurrencyRow] = frozenset(
    (source, function, governor)
    for source, function, governor, _pool, _acquire, _bind, _renew, _release in EXPECTED_ROWS
    if source == REL_SOURCE
)
# guarded_runner / guarded_panel_runner are gone with the settlement fence (#677/U3): the runner
# invocation lives directly inside _dispatch_once now.
EXPECTED_EXECUTABLE_SPAWNS = frozenset(
    {
        ("plugins/saga/scripts/engine_dispatch.py", "_dispatch_once", "runner"),
        ("plugins/saga/scripts/outcome.py", "_reconcile_once", "dispatch"),
        ("plugins/saga/scripts/outcome_worktrees.py", "ensure_worktree", "ops.add"),
    }
)


def test_issue_355_decision_uses_one_broker_authority() -> None:
    text = DECISIONS_PATH.read_text(encoding="utf-8")
    anchor = "{#orphan-evidence-fencing-355}"
    assert text.count(anchor) == 1
    section = text.split(anchor, 1)[1].split("\n---\n", 1)[0]
    normalized = " ".join(section.split())

    for required in (
        "`LeaseBroker` as the sole mutation authority",
        "prepare/commit/abort",
        "atomic closed-registry replacement",
        "closed-head CAS",
        "does not claim automatic or restart-safe producer replay",
        "same-effective-user processes and the operator are trusted",
        "512 MiB and 256 entries",
    ):
        assert required in normalized

    for obsolete in ("digest-named lock", "resource-scoped lock"):
        assert obsolete not in section


# Broker-free since #677/U3: the engine_dispatch / outcome_dispatcher / outcome_worktrees lease
# lifecycle entries are deleted with their seams, #677/U4 retires the workflow_emitter entries
# with the batch concept itself, and #677/U5 deletes the saga lease hook and wrapper whole —
# their required-call pins are absence pins now (test_lease_hook_and_wrapper_are_absent).
SITE_CONTRACTS = {
    "_emit_panel_reconciliation": {
        "governor": "concurrency_governor.ordered_chunks",
        "collection": "panel_chunks",
        "chunk": "chunk",
        "loop": "zip",
        "renderer": "_emit_verifier_member",
    },
    "emit_workflow_script": {
        "governor": "concurrency_chunks",
        "collection": "layer_chunks",
        "chunk": "chunk_units",
        "loop": "enumerate",
        "renderer": "_emit_worker_member",
    },
}


def _load_execution_spec() -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(
        "concurrency_conformance_execution_spec", SOURCE_PATH
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ES = _load_execution_spec()


def _sources() -> dict[str, str]:
    return {
        path.relative_to(ROOT).as_posix(): path.read_text()
        for path in sorted(SAGA_ROOT.rglob("*.py"))
    }


def _inventory_rows(inventory: str) -> frozenset[InventoryRow]:
    rows = [
        (
            match["source"],
            match["function"],
            match["governor"],
            match["pool"],
            match["acquire"],
            match["bind"],
            match["renew"],
            match["release"],
        )
        for line in inventory.splitlines()
        if (match := ROW_RE.match(line)) is not None
    ]
    assert rows, "concurrency inventory has no machine-readable rows"
    assert len(rows) == len(set(rows)), "concurrency inventory contains duplicate rows"
    return frozenset(rows)


def _parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}


def _enclosing_function(
    node: ast.AST,
    parents: dict[ast.AST, ast.AST],
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    current = parents.get(node)
    while current is not None:
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return current
        current = parents.get(current)
    return None


def _enclosing_for(
    node: ast.AST,
    owner: ast.FunctionDef | ast.AsyncFunctionDef,
    parents: dict[ast.AST, ast.AST],
) -> ast.For:
    current = parents.get(node)
    while current is not None and current is not owner:
        if isinstance(current, ast.For):
            return current
        current = parents.get(current)
    raise AssertionError(f"{owner.name} helper call is not inside its direct chunk loop")


def _qualified_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _qualified_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else None
    return None


def _helper_calls(tree: ast.AST) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _qualified_name(node.func) == HELPER_NAME
    ]


def _string_leaves(node: ast.AST) -> Iterator[str]:
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            yield child.value


def _static_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _static_string(node.left)
        right = _static_string(node.right)
        return left + right if left is not None and right is not None else None
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
                return None
            parts.append(value.value)
        return "".join(parts)
    return None


def _delimiter_fragments(node: ast.AST) -> Iterator[str]:
    static = _static_string(node)
    if static is not None:
        yield static
        return
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        for element in node.elts:
            yield from _delimiter_fragments(element)
        return
    yield from _string_leaves(node)


def _has_unresolved_parallel_callee(node: ast.AST) -> bool:
    if isinstance(node, ast.JoinedStr):
        saw_dynamic = False
        for value in node.values:
            if isinstance(value, ast.FormattedValue):
                saw_dynamic = True
            elif (
                saw_dynamic
                and isinstance(value, ast.Constant)
                and isinstance(value.value, str)
                and DYNAMIC_CALLEE_SUFFIX_RE.search(value.value)
            ):
                return True
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "format"
    ):
        template = _static_string(node.func.value)
        return template is not None and FORMAT_CALLEE_RE.search(template) is not None
    return False


def _has_parallel_open(node: ast.AST) -> bool:
    return any(PARALLEL_OPEN_RE.search(fragment) for fragment in _delimiter_fragments(node)) or (
        _has_unresolved_parallel_callee(node)
    )


def _sink_calls(tree: ast.AST, parents: dict[ast.AST, ast.AST]) -> Iterator[ast.Call]:
    aliases: dict[ast.FunctionDef | ast.AsyncFunctionDef, set[str]] = {}
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Attribute)
            and isinstance(node.value.value, ast.Name)
            and node.value.value.id == "lines"
            and node.value.attr in {"append", "extend", "insert"}
        ):
            owner = _enclosing_function(node, parents)
            if owner is not None:
                aliases.setdefault(owner, set()).add(node.targets[0].id)
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"append", "extend", "insert"}
        ):
            yield node
            continue
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            owner = _enclosing_function(node, parents)
            if owner is not None and node.func.id in aliases.get(owner, set()):
                yield node


def _assert_no_raw_assignment(
    node: ast.Assign | ast.AnnAssign | ast.AugAssign,
    parents: dict[ast.AST, ast.AST],
    source_path: str,
) -> None:
    value = node.value
    if value is None:
        return
    fragments = list(_delimiter_fragments(value))
    if not _has_parallel_open(value) and not any(
        fragment.strip() == "])" for fragment in fragments
    ):
        return
    owner = _enclosing_function(node, parents)
    if owner is None or owner.name != HELPER_NAME:
        raise AssertionError(
            f"raw parallel delimiter emitter outside {HELPER_NAME}: {source_path}:{node.lineno}"
        )


def _assert_no_raw_parallel_emitters(
    tree: ast.AST,
    parents: dict[ast.AST, ast.AST],
    source_path: str,
) -> None:
    for call in _sink_calls(tree, parents):
        owner = _enclosing_function(call, parents)
        fragments = [
            fragment for argument in call.args for fragment in _delimiter_fragments(argument)
        ]
        raw_open = any(_has_parallel_open(argument) for argument in call.args)
        raw_close = any(fragment.strip() == "])" for fragment in fragments)
        if (raw_open or raw_close) and (owner is None or owner.name != HELPER_NAME):
            line = getattr(call, "lineno", "?")
            raise AssertionError(
                f"raw parallel delimiter emitter outside {HELPER_NAME}: {source_path}:{line}"
            )
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            _assert_no_raw_assignment(node, parents, source_path)


def _assert_helper_references_are_direct(
    tree: ast.AST,
    parents: dict[ast.AST, ast.AST],
    helper_calls: list[ast.Call],
) -> None:
    direct_loads = {call.func for call in helper_calls}
    helper_loads = {
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id == HELPER_NAME
    }
    assert helper_loads == direct_loads, (
        f"every {HELPER_NAME} reference must be one of the validated direct calls"
    )


def _direct_append_call(statement: ast.stmt) -> ast.Call:
    assert isinstance(statement, ast.Expr)
    assert isinstance(statement.value, ast.Call)
    call = statement.value
    assert isinstance(call.func, ast.Attribute)
    assert isinstance(call.func.value, ast.Name)
    assert call.func.value.id == "lines"
    assert call.func.attr == "append"
    assert len(call.args) == 1
    assert not call.keywords
    return call


def _assert_helper_contract(helper: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
    body = list(helper.body)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]
    assert len(body) == 4, "parallel helper must contain snapshot, opener, loop, and closer only"

    snapshot, opener, member_loop, closer = body
    assert isinstance(snapshot, ast.Assign)
    assert len(snapshot.targets) == 1
    assert isinstance(snapshot.targets[0], ast.Name)
    assert snapshot.targets[0].id == "member_snapshot"
    assert isinstance(snapshot.value, ast.Call)
    assert _qualified_name(snapshot.value.func) == "tuple"
    assert len(snapshot.value.args) == 1
    assert isinstance(snapshot.value.args[0], ast.Name)
    assert snapshot.value.args[0].id == "bounded_members"
    assert not snapshot.value.keywords

    opener_call = _direct_append_call(opener)
    assert any("parallel([" in leaf for leaf in _string_leaves(opener_call.args[0]))

    assert isinstance(member_loop, ast.For)
    assert isinstance(member_loop.target, ast.Name)
    assert member_loop.target.id == "member"
    assert isinstance(member_loop.iter, ast.Name)
    assert member_loop.iter.id == "member_snapshot"
    assert len(member_loop.body) == 1
    assert isinstance(member_loop.body[0], ast.Expr)
    assert isinstance(member_loop.body[0].value, ast.Call)
    callback = member_loop.body[0].value
    assert _qualified_name(callback.func) == "render_member"
    assert len(callback.args) == 1
    assert isinstance(callback.args[0], ast.Name)
    assert callback.args[0].id == "member"
    assert not callback.keywords
    assert not member_loop.orelse

    closer_call = _direct_append_call(closer)
    assert any(leaf.strip() == "])" for leaf in _string_leaves(closer_call.args[0]))


def _name_tuple(node: ast.AST) -> tuple[str, ...]:
    assert isinstance(node, (ast.Tuple, ast.List))
    names: list[str] = []
    for element in node.elts:
        assert isinstance(element, ast.Name)
        names.append(element.id)
    return tuple(names)


def _containing_block(loop: ast.For, parents: dict[ast.AST, ast.AST]) -> list[ast.stmt]:
    container = parents[loop]
    for _field, value in ast.iter_fields(container):
        if isinstance(value, list) and loop in value:
            assert all(isinstance(statement, ast.stmt) for statement in value)
            return value
    raise AssertionError("chunk loop has no direct statement block")


def _assert_direct_governor_definition(
    owner: ast.FunctionDef | ast.AsyncFunctionDef,
    outer_loop: ast.For,
    parents: dict[ast.AST, ast.AST],
    *,
    collection: str,
    governor: str,
) -> None:
    block = _containing_block(outer_loop, parents)
    loop_index = block.index(outer_loop)
    definitions: list[ast.Assign] = []
    for statement in block[:loop_index]:
        if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
            continue
        target = statement.targets[0]
        if not isinstance(target, ast.Name) or target.id != collection:
            continue
        assert isinstance(statement.value, ast.Call), (
            f"{owner.name} {collection} must be assigned directly from {governor}"
        )
        assert _qualified_name(statement.value.func) == governor, (
            f"{owner.name} {collection} must be assigned directly from {governor}"
        )
        definitions.append(statement)
    assert len(definitions) == 1, (
        f"{owner.name} requires exactly one direct reaching {governor} definition"
    )
    definition_index = block.index(definitions[0])
    for statement in block[definition_index + 1 : loop_index]:
        for node in ast.walk(statement):
            if not isinstance(node, ast.Name) or node.id != collection:
                continue
            if isinstance(node.ctx, (ast.Store, ast.Del)):
                raise AssertionError(
                    f"{owner.name} governed collection changed before loop consumption"
                )
            parent = parents[node]
            safe_len = (
                isinstance(parent, ast.Call)
                and _qualified_name(parent.func) == "len"
                and parent.args == [node]
                and not parent.keywords
            )
            safe_comprehension = isinstance(parent, ast.comprehension) and parent.iter is node
            if not safe_len and not safe_comprehension:
                raise AssertionError(
                    f"{owner.name} governed collection escaped before loop consumption"
                )


def _assert_loop_contract(
    owner: ast.FunctionDef | ast.AsyncFunctionDef,
    outer_loop: ast.For,
    *,
    loop_kind: str,
    collection: str,
    chunk: str,
) -> None:
    target_names = _name_tuple(outer_loop.target)
    assert target_names[-1] == chunk, f"{owner.name} must bind direct chunk target {chunk}"
    assert isinstance(outer_loop.iter, ast.Call)
    assert _qualified_name(outer_loop.iter.func) == loop_kind

    if loop_kind == "zip":
        assert len(outer_loop.iter.args) == 2
        source = outer_loop.iter.args[1]
    else:
        assert loop_kind == "enumerate"
        assert len(outer_loop.iter.args) == 1
        source = outer_loop.iter.args[0]
    assert isinstance(source, ast.Name) and source.id == collection, (
        f"{owner.name} must iterate the direct governed collection {collection}"
    )


def _assert_chunk_unchanged_before_call(
    call: ast.Call,
    outer_loop: ast.For,
    parents: dict[ast.AST, ast.AST],
    chunk: str,
) -> None:
    statement: ast.AST = call
    while parents.get(statement) is not outer_loop:
        statement = parents[statement]
    assert isinstance(statement, ast.stmt)
    call_index = outer_loop.body.index(statement)
    for preceding in outer_loop.body[:call_index]:
        for node in ast.walk(preceding):
            if not isinstance(node, ast.Name) or node.id != chunk:
                continue
            if isinstance(node.ctx, (ast.Store, ast.Del)):
                raise AssertionError(f"direct chunk target {chunk} changed before helper call")
            parent = parents[node]
            safe_len = (
                isinstance(parent, ast.Call)
                and _qualified_name(parent.func) == "len"
                and parent.args == [node]
                and not parent.keywords
            )
            safe_comprehension = isinstance(parent, ast.comprehension) and parent.iter is node
            if not safe_len and not safe_comprehension:
                raise AssertionError(f"direct chunk target {chunk} escaped before helper call")


def _assert_direct_loop_body_call(
    call: ast.Call,
    outer_loop: ast.For,
    parents: dict[ast.AST, ast.AST],
) -> None:
    statement = parents.get(call)
    assert (
        isinstance(statement, ast.Expr)
        and statement.value is call
        and parents.get(statement) is outer_loop
        and statement in outer_loop.body
    ), "parallel-wave helper must be a direct expression in the governed loop body"


def _assert_site_contract(
    call: ast.Call,
    owner: ast.FunctionDef | ast.AsyncFunctionDef,
    parents: dict[ast.AST, ast.AST],
) -> None:
    contract = SITE_CONTRACTS[owner.name]
    assert len(call.args) == 1
    assert isinstance(call.args[0], ast.Name) and call.args[0].id == "lines"
    assert all(keyword.arg is not None for keyword in call.keywords)
    keywords = {keyword.arg: keyword.value for keyword in call.keywords}
    assert len(keywords) == len(call.keywords)
    assert set(keywords) == {"binding", "bounded_members", "render_member"} or set(keywords) == {
        "binding",
        "bounded_members",
        "render_member",
        "indent",
    }
    bounded_members = keywords["bounded_members"]
    assert isinstance(bounded_members, ast.Name) and bounded_members.id == contract["chunk"], (
        f"{owner.name} must pass its direct chunk target as bounded_members"
    )
    renderer = keywords["render_member"]
    assert isinstance(renderer, ast.Name) and renderer.id == contract["renderer"]

    outer_loop = _enclosing_for(call, owner, parents)
    _assert_loop_contract(
        owner,
        outer_loop,
        loop_kind=contract["loop"],
        collection=contract["collection"],
        chunk=contract["chunk"],
    )
    _assert_direct_loop_body_call(call, outer_loop, parents)
    _assert_chunk_unchanged_before_call(call, outer_loop, parents, contract["chunk"])
    _assert_direct_governor_definition(
        owner,
        outer_loop,
        parents,
        collection=contract["collection"],
        governor=contract["governor"],
    )


def _assert_executable_spawn_inventory(
    parsed: dict[str, tuple[ast.Module, dict[ast.AST, ast.AST]]],
    rows: frozenset[InventoryRow],
) -> None:
    watched = {
        "plugins/saga/scripts/engine_dispatch.py": {"runner"},
        "plugins/saga/scripts/outcome.py": {"dispatch"},
        "plugins/saga/scripts/outcome_worktrees.py": {"ops.add"},
    }
    discovered: set[tuple[str, str, str]] = set()
    for source_path, callees in watched.items():
        tree, parents = parsed[source_path]
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            callee = _qualified_name(node.func)
            if callee not in callees:
                continue
            owner = _enclosing_function(node, parents)
            assert owner is not None, f"spawn call {source_path}:{node.lineno} has no owner"
            discovered.add((source_path, owner.name, callee))
    assert frozenset(discovered) == EXPECTED_EXECUTABLE_SPAWNS, (
        "executable spawn-site inventory drift"
    )

    inventoried = {(row[0], row[1]) for row in rows}
    for source_path, function, _callee in discovered:
        assert (source_path, function) in inventoried, (
            f"executable spawn lacks lease lifecycle row: {source_path}:{function}"
        )


def _hook_commands(entries: list[dict[str, Any]], matcher: str | None = None) -> list[str]:
    commands: list[str] = []
    for entry in entries:
        if matcher is not None and entry.get("matcher") != matcher:
            continue
        commands.extend(
            str(hook["command"])
            for hook in entry.get("hooks", [])
            if isinstance(hook, dict) and "command" in hook
        )
    return commands


def _assert_host_spawn_contracts() -> None:
    # #677/U5: the lease lifecycle hook is deleted and unregistered everywhere — pin ABSENCE
    # across every event so re-arming it through the manifest fails loudly.
    hooks_path = ROOT / "plugins/saga/hooks/hooks.json"
    events = json.loads(hooks_path.read_text(encoding="utf-8"))["hooks"]
    for event, entries in events.items():
        assert not any(
            "lease_lifecycle_hook.py" in command for command in _hook_commands(entries)
        ), f"lease lifecycle hook re-registered on {event}"

    team_path = ROOT / "plugins/team-execution/skills/team-execution/scripts/lease_protocol.py"
    assert not team_path.exists(), (
        "lease_protocol.py was deleted in #677/U6 — the team-execution lease wrapper is gone; "
        "remove any remaining reference to its preflight/renew/teardown lifecycle"
    )


def assert_conformance(sources: dict[str, str], inventory: str) -> None:
    rows = _inventory_rows(inventory)
    assert rows == EXPECTED_ROWS, "concurrency and lease inventory drift"

    parsed: dict[str, tuple[ast.Module, dict[ast.AST, ast.AST]]] = {}
    helper_defs: list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]] = []
    helper_calls: list[tuple[str, ast.Call]] = []
    for source_path, source in sources.items():
        tree = ast.parse(source, filename=source_path)
        parents = _parents(tree)
        parsed[source_path] = (tree, parents)
        _assert_no_raw_parallel_emitters(tree, parents, source_path)
        helper_defs.extend(
            (source_path, node)
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == HELPER_NAME
        )
        source_helper_calls = _helper_calls(tree)
        _assert_helper_references_are_direct(tree, parents, source_helper_calls)
        helper_calls.extend((source_path, call) for call in source_helper_calls)

    _assert_executable_spawn_inventory(parsed, rows)
    _assert_host_spawn_contracts()

    assert len(helper_defs) == 1, f"expected one {HELPER_NAME} definition"
    helper_path, helper = helper_defs[0]
    assert helper_path == REL_SOURCE
    _assert_helper_contract(helper)

    assert len(helper_calls) == 2, f"expected exactly two {HELPER_NAME} call sites"
    discovered: set[ConcurrencyRow] = set()
    seen_owners: set[str] = set()
    for source_path, call in helper_calls:
        _tree, parents = parsed[source_path]
        owner = _enclosing_function(call, parents)
        assert owner is not None
        assert owner.name in SITE_CONTRACTS, f"unexpected {HELPER_NAME} owner: {owner.name}"
        assert owner.name not in seen_owners, f"duplicate {HELPER_NAME} call in {owner.name}"
        seen_owners.add(owner.name)
        contract = SITE_CONTRACTS[owner.name]
        discovered.add((source_path, owner.name, contract["governor"]))
        _assert_site_contract(call, owner, parents)
    assert frozenset(discovered) == EXPECTED_CONCURRENCY_ROWS, "helper call-site inventory drift"


def _mutate_source(sources: dict[str, str], old: str, new: str) -> dict[str, str]:
    source = sources[REL_SOURCE]
    assert old in source, f"mutation target not found: {old}"
    mutated = dict(sources)
    mutated[REL_SOURCE] = source.replace(old, new, 1)
    return mutated


def test_parallel_wave_preserves_snapshot_order_despite_callback_mutation() -> None:
    members = [1, 2, 3]
    lines: list[str] = []
    rendered: list[int] = []

    def render_member(member: int) -> None:
        rendered.append(member)
        lines.append(f"  member:{member}")
        if member == 1:
            members.clear()
            members.extend([4, 5])

    ES._emit_parallel_wave(
        lines,
        binding="const wave",
        bounded_members=members,
        render_member=render_member,
    )

    assert rendered == [1, 2, 3]
    assert lines == [
        "const wave = await parallel([",
        "  member:1",
        "  member:2",
        "  member:3",
        "])",
    ]
    assert members == [4, 5]


@pytest.mark.parametrize(
    ("indent", "binding", "expected"),
    [
        ("", "const values", ["const values = await parallel([", "])"]),
        ("  ", "let [a, b]", ["  let [a, b] = await parallel([", "  ])"]),
    ],
)
def test_parallel_wave_emits_exact_delimiters(
    indent: str,
    binding: str,
    expected: list[str],
) -> None:
    lines: list[str] = []
    ES._emit_parallel_wave(
        lines,
        binding=binding,
        bounded_members=(),
        render_member=lambda _member: None,
        indent=indent,
    )
    assert lines == expected


def test_checked_in_inventory_exactly_matches_structural_emitters() -> None:
    assert_conformance(_sources(), INVENTORY_PATH.read_text())


@pytest.mark.parametrize("sink", ["append", "extend"])
def test_raw_parallel_emitter_outside_helper_is_rejected(sink: str) -> None:
    argument = '"const rogue = await parallel(["'
    if sink == "extend":
        argument = f"[{argument}]"
    injection = f"\n\ndef _rogue(lines):\n    lines.{sink}({argument})\n"
    sources = _sources()
    sources[REL_SOURCE] += injection
    with pytest.raises(AssertionError, match="raw parallel delimiter emitter"):
        assert_conformance(sources, INVENTORY_PATH.read_text())


@pytest.mark.parametrize(
    "statement",
    [
        'lines += ["const rogue = await parallel([", "])"]',
        'lines.append("const rogue = await " + "parallel" + "([")',
    ],
)
def test_alternate_raw_parallel_output_is_rejected(statement: str) -> None:
    sources = _sources()
    sources[REL_SOURCE] += f"\n\ndef _rogue(lines):\n    {statement}\n"
    with pytest.raises(AssertionError, match="raw parallel delimiter emitter"):
        assert_conformance(sources, INVENTORY_PATH.read_text())


@pytest.mark.parametrize(
    "body",
    [
        '    emit = lines.append\n    emit("const rogue = await parallel([")',
        '    lines.append("const rogue = await parallel /* drift */ ([")',
        '    lines.append(f"{callee}([")',
        '    lines.append("{}([".format(callee))',
        '    opener = "const rogue = await parallel(["\n'
        '    closer = "])"\n'
        "    lines.append(opener)\n"
        "    lines.append(closer)",
    ],
)
def test_indirect_or_obscured_raw_parallel_output_is_rejected(body: str) -> None:
    sources = _sources()
    sources[REL_SOURCE] += f'\n\ndef _rogue(lines, callee="parallel"):\n{body}\n'
    with pytest.raises(AssertionError, match="raw parallel delimiter emitter"):
        assert_conformance(sources, INVENTORY_PATH.read_text())


def test_third_helper_call_is_rejected_as_inventory_drift() -> None:
    sources = _sources()
    sources[REL_SOURCE] += (
        "\n\ndef _rogue(lines):\n"
        "    _emit_parallel_wave(\n"
        '        lines, binding="const rogue", bounded_members=(), '
        "render_member=lambda _item: None\n"
        "    )\n"
    )
    with pytest.raises(AssertionError, match="exactly two"):
        assert_conformance(sources, INVENTORY_PATH.read_text())


def test_indirect_helper_reference_is_rejected() -> None:
    sources = _sources()
    sources[REL_SOURCE] += (
        "\n\ndef _rogue(lines):\n"
        f"    emit = {HELPER_NAME}\n"
        '    emit(lines, binding="const rogue", bounded_members=range(99), '
        "render_member=lambda _item: None)\n"
    )
    with pytest.raises(AssertionError, match="validated direct calls"):
        assert_conformance(sources, INVENTORY_PATH.read_text())


def test_injected_unguarded_executable_spawn_is_rejected() -> None:
    source_path = "plugins/saga/scripts/engine_dispatch.py"
    sources = _sources()
    sources[source_path] += "\n\ndef _rogue(runner):\n    return runner({})\n"

    with pytest.raises(AssertionError, match="executable spawn-site inventory drift"):
        assert_conformance(sources, INVENTORY_PATH.read_text())


# The batch lease lifecycle calls retired with the batch concept itself (#677/U4, plan KTD4):
# pin their ABSENCE so re-arming the workflow emitter against any fleet lease authority is a
# loud test failure, not a silent regression.
@pytest.mark.parametrize(
    ("source_path", "call"),
    [
        ("plugins/saga/scripts/workflow_emitter.py", "selected.reserve_batch"),
        ("plugins/saga/scripts/workflow_emitter.py", "selected.renew_batch"),
        ("plugins/saga/scripts/workflow_emitter.py", "selected.settle_batch"),
    ],
)
def test_retired_lease_lifecycle_calls_are_absent(source_path: str, call: str) -> None:
    sources = _sources()
    assert call not in sources[source_path]


def test_lease_hook_and_wrapper_are_absent_from_saga() -> None:
    """#677/U5 deletes the lease lifecycle hook and the saga broker wrapper whole.

    Pin the ABSENCE of both files — and of the four hook adapter entry points anywhere in
    saga — so re-adding the wrapper or rewiring a hook seam to it is a loud test failure,
    not a silent regression.
    """
    sources = _sources()
    assert "plugins/saga/hooks/lease_lifecycle_hook.py" not in sources
    assert "plugins/saga/scripts/lease_broker.py" not in sources
    for name in (
        "reserve_hook_agent",
        "claim_hook_agent",
        "record_hook_terminal",
        "record_hook_parent",
    ):
        assert not any(name in source for source in sources.values()), name


@pytest.mark.parametrize("drift", ["remove", "add"])
def test_inventory_row_drift_is_rejected(drift: str) -> None:
    inventory = INVENTORY_PATH.read_text()
    row = (
        "| `plugins/saga/scripts/execution_spec.py` | `_emit_panel_reconciliation` "
        "| verify-panel verdict agents | `concurrency_governor.ordered_chunks` | `agent` "
        "| `retired:broker-free-(#677/U4)` | `retired:broker-free-(#677/U5)` "
        "| `retired:broker-free-(#677/U4)` | `retired:broker-free-(#677/U4)` |"
    )
    assert row in inventory
    if drift == "remove":
        inventory = inventory.replace(f"{row}\n", "", 1)
    else:
        inventory += (
            "\n| `plugins/saga/scripts/execution_spec.py` | `_rogue` "
            "| rogue agents | `concurrency_chunks` | `agent` | `rogue.acquire` "
            "| `rogue.bind` | `rogue.renew` | `rogue.release` |\n"
        )
    with pytest.raises(AssertionError, match="inventory drift"):
        assert_conformance(_sources(), inventory)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("bounded_members=chunk,", "bounded_members=list(chunk),"),
        ("bounded_members=chunk_units,", "bounded_members=concrete_units,"),
    ],
)
def test_bounded_members_must_be_the_direct_chunk_target(old: str, new: str) -> None:
    with pytest.raises(AssertionError, match="direct chunk target"):
        assert_conformance(
            _mutate_source(_sources(), old, new),
            INVENTORY_PATH.read_text(),
        )


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (
            "for chunk_var, chunk in zip(verdict_chunk_vars, panel_chunks, strict=True):\n"
            "        _emit_parallel_wave(",
            "for chunk_var, chunk in zip(verdict_chunk_vars, panel_chunks, strict=True):\n"
            "        chunk = list(range(99))\n"
            "        _emit_parallel_wave(",
        ),
        (
            "            _emit_parallel_wave(\n"
            "                lines,\n"
            "                binding=f\"{wave_decl} [{', '.join(chunk_vars)}]\",",
            "            chunk_units = concrete_units\n"
            "            _emit_parallel_wave(\n"
            "                lines,\n"
            "                binding=f\"{wave_decl} [{', '.join(chunk_vars)}]\",",
        ),
    ],
)
def test_direct_chunk_rebind_before_helper_is_rejected(old: str, new: str) -> None:
    with pytest.raises(AssertionError, match="changed before helper"):
        assert_conformance(
            _mutate_source(_sources(), old, new),
            INVENTORY_PATH.read_text(),
        )


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (
            "for chunk_var, chunk in zip(verdict_chunk_vars, panel_chunks, strict=True):\n"
            "        _emit_parallel_wave(",
            "for chunk_var, chunk in zip(verdict_chunk_vars, panel_chunks, strict=True):\n"
            "        chunk_alias = chunk\n"
            "        chunk_alias.extend(range(99))\n"
            "        _emit_parallel_wave(",
        ),
        (
            "            _emit_parallel_wave(\n"
            "                lines,\n"
            "                binding=f\"{wave_decl} [{', '.join(chunk_vars)}]\",",
            "            chunk_alias = chunk_units\n"
            "            chunk_alias.extend(concrete_units)\n"
            "            _emit_parallel_wave(\n"
            "                lines,\n"
            "                binding=f\"{wave_decl} [{', '.join(chunk_vars)}]\",",
        ),
    ],
)
def test_direct_chunk_alias_escape_before_helper_is_rejected(old: str, new: str) -> None:
    with pytest.raises(AssertionError, match="escaped before helper"):
        assert_conformance(
            _mutate_source(_sources(), old, new),
            INVENTORY_PATH.read_text(),
        )


def test_nested_chunk_rebind_and_helper_call_are_rejected() -> None:
    old = (
        "    for chunk_var, chunk in zip(verdict_chunk_vars, panel_chunks, strict=True):\n"
        "        _emit_parallel_wave(\n"
        "            lines,\n"
        '            binding=f"const {chunk_var}",\n'
        "            bounded_members=chunk,\n"
        "            render_member=_emit_verifier_member,\n"
        "            indent=indent,\n"
        "        )"
    )
    new = (
        "    for chunk_var, chunk in zip(verdict_chunk_vars, panel_chunks, strict=True):\n"
        "        if True:\n"
        "            chunk = list(range(99))\n"
        "            _emit_parallel_wave(\n"
        "                lines,\n"
        '                binding=f"const {chunk_var}",\n'
        "                bounded_members=chunk,\n"
        "                render_member=_emit_verifier_member,\n"
        "                indent=indent,\n"
        "            )"
    )
    with pytest.raises(AssertionError, match="direct expression in the governed loop body"):
        assert_conformance(
            _mutate_source(_sources(), old, new),
            INVENTORY_PATH.read_text(),
        )


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (
            "panel_chunks = concurrency_governor.ordered_chunks(",
            "panel_chunks = list(",
        ),
        ("layer_chunks = concurrency_chunks(", "layer_chunks = list("),
    ],
)
def test_chunk_collection_must_come_directly_from_its_governor(old: str, new: str) -> None:
    with pytest.raises(AssertionError, match="assigned directly"):
        assert_conformance(
            _mutate_source(_sources(), old, new),
            INVENTORY_PATH.read_text(),
        )


@pytest.mark.parametrize(
    ("marker", "mutation"),
    [
        ("    if len(panel_chunks) == 1:", "    panel_chunks.clear()"),
        (
            "    if len(panel_chunks) == 1:",
            "    panel_chunks.extend([list(range(99))])",
        ),
        (
            "    if len(panel_chunks) == 1:",
            "    panel_chunks[0] = list(range(99))",
        ),
        (
            "    if len(panel_chunks) == 1:",
            "    chunk_alias = panel_chunks\n    chunk_alias.clear()",
        ),
        (
            "        layer_width = max(len(chunk) for chunk in layer_chunks)",
            "        layer_chunks.clear()",
        ),
        (
            "        layer_width = max(len(chunk) for chunk in layer_chunks)",
            "        layer_chunks.extend([concrete_units])",
        ),
        (
            "        layer_width = max(len(chunk) for chunk in layer_chunks)",
            "        layer_chunks[0] = concrete_units",
        ),
        (
            "        layer_width = max(len(chunk) for chunk in layer_chunks)",
            "        chunk_alias = layer_chunks\n        chunk_alias.clear()",
        ),
    ],
)
def test_governed_collection_cannot_change_or_escape_before_loop(
    marker: str,
    mutation: str,
) -> None:
    with pytest.raises(AssertionError, match="governed collection (changed|escaped)"):
        assert_conformance(
            _mutate_source(_sources(), marker, f"{mutation}\n{marker}"),
            INVENTORY_PATH.read_text(),
        )


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (
            "zip(verdict_chunk_vars, panel_chunks, strict=True)",
            "zip(verdict_chunk_vars, list(panel_chunks), strict=True)",
        ),
        (
            "enumerate(layer_chunks, start=1)",
            "enumerate(list(layer_chunks), start=1)",
        ),
    ],
)
def test_outer_loop_must_consume_the_direct_governed_collection(old: str, new: str) -> None:
    with pytest.raises(AssertionError, match="direct governed collection"):
        assert_conformance(
            _mutate_source(_sources(), old, new),
            INVENTORY_PATH.read_text(),
        )
