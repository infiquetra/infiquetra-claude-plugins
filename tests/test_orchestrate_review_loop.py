"""The Orchestrate seam around Code Review's opaque typed result.

Code Review owns acceptance and cycle policy. These tests prove that Orchestrate has one controller,
stores the controller's bytes, routes repair ownership to Work, protects active workers, and never
turns operator-owned work or finding metadata into another acceptance gate.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "plugins"
    / "orchestrate"
    / "skills"
    / "orchestrate"
    / "scripts"
    / "orchestrate.py"
)


@pytest.fixture(scope="module")
def orchestrate() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_orchestrate_review_loop", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _controller(orchestrate: ModuleType) -> Any:
    return orchestrate.Unit(
        name="code-review-controller",
        vendor="grok",
        task="/saga:code-review review the run branch",
        role="review-controller",
        merge=False,
        pane_id="pane-review",
        agent_name="review-agent",
        status="done",
    )


def _worker(
    orchestrate: ModuleType,
    name: str,
    role: str,
    *paths: str,
    live: bool = True,
) -> Any:
    return orchestrate.Unit(
        name=name,
        vendor="claude",
        model="opus",
        effort="high",
        task="/saga:work docs/plans/build.md",
        role=role,
        paths=list(paths),
        pane_id=f"pane-{name}" if live else None,
        agent_name=f"agent-{name}" if live else None,
        status="done",
    )


def _run(orchestrate: ModuleType, *units: Any) -> Any:
    return orchestrate.Run(run_id="review-run", source="test", base="base", units=list(units))


def _request(fix_id: str, owner: str, *paths: str) -> dict[str, Any]:
    return {
        "fix_id": fix_id,
        "finding_ids": [f"finding-{fix_id}"],
        "autofix_class": "safe_auto",
        "owner": owner,
        "touched_paths": list(paths),
        "summary": f"repair {fix_id}",
        "requires_verification": True,
    }


def _result(outcome: str, *requests: dict[str, Any], **extra: Any) -> str:
    payload: dict[str, Any] = {
        "schema": "review_result.v1",
        "outcome": outcome,
        "fix_requests": list(requests),
        **extra,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _live(*workers: Any) -> list[dict[str, str]]:
    return [
        {"name": worker.agent_name, "pane_id": worker.pane_id, "agent_status": "idle"}
        for worker in workers
    ]


def test_a_code_review_phase_has_exactly_one_controller(orchestrate: ModuleType) -> None:
    plan = {
        "units": [
            {
                "name": "builder",
                "vendor": "claude",
                "task": "/saga:work docs/plans/build.md",
                "role": "review-fixer",
                "paths": ["src"],
            },
            {
                "name": "review",
                "vendor": "grok",
                "task": "/saga:code-review the build",
            },
        ]
    }

    units = orchestrate.plan_units(plan)

    controllers = [unit for unit in units if unit.role == "review-controller"]
    assert [unit.name for unit in controllers] == ["review"]

    plan["units"].append(
        {"name": "review-two", "vendor": "codex", "task": "$saga:code-review the build"}
    )
    with pytest.raises(SystemExit, match="exactly one top-level Code Review controller"):
        orchestrate.plan_units(plan)


def test_two_role_and_path_matches_reuse_live_workers_and_protect_them(
    orchestrate: ModuleType,
) -> None:
    controller = _controller(orchestrate)
    fixer = _worker(orchestrate, "api-builder", "review-fixer", "src/api")
    resolver = _worker(
        orchestrate,
        "contract-builder",
        "downstream-resolver",
        "packages/contracts",
    )
    run = _run(orchestrate, fixer, resolver, controller)
    raw = _result(
        "repairs_requested",
        _request("fix-api", "review-fixer", "src/api/routes.py"),
        _request("fix-contract", "downstream-resolver", "packages/contracts/schema.json"),
    )

    routing = orchestrate.route_review_result(run, raw, agents=_live(fixer, resolver))
    sent: list[tuple[str, str]] = []
    dispatched = orchestrate.dispatch_review_routing(
        routing, sender=lambda unit, text: sent.append((unit.name, text))
    )

    assert dispatched == ["api-builder", "contract-builder"]
    assert [name for name, _ in sent] == dispatched
    assert [item["fix_id"] for item in fixer.fix_requests] == ["fix-api"]
    assert [item["fix_id"] for item in resolver.fix_requests] == ["fix-contract"]
    assert orchestrate.reapable(fixer, run) is False
    assert orchestrate.reapable(resolver, run) is False
    assert routing.replacements == []
    assert run.review_resubmit_pending is True


def test_a_missing_live_match_creates_a_replacement_work_worker(
    orchestrate: ModuleType,
) -> None:
    controller = _controller(orchestrate)
    original = _worker(
        orchestrate,
        "retired-api-builder",
        "review-fixer",
        "src/api",
        live=False,
    )
    run = _run(orchestrate, original, controller)

    routing = orchestrate.route_review_result(
        run,
        _result(
            "repairs_requested",
            _request("fix-new-route", "review-fixer", "src/api/new_route.py"),
        ),
        agents=[],
    )

    assert routing.dispatches == []
    assert len(routing.replacements) == 1
    replacement = routing.replacements[0]
    assert replacement is run.units[-1]
    assert replacement.vendor == original.vendor
    assert replacement.model == original.model
    assert replacement.effort == original.effort
    assert replacement.role == "review-fixer"
    assert replacement.paths == ["src/api/new_route.py"]
    assert replacement.serialize == [controller.name]
    assert replacement.status == "pending"


@pytest.mark.parametrize("owner", ["human", "release"])
def test_operator_owned_requests_are_surfaced_and_never_dispatched_as_work(
    orchestrate: ModuleType,
    owner: str,
) -> None:
    controller = _controller(orchestrate)
    worker = _worker(orchestrate, "builder", "review-fixer", "src")
    run = _run(orchestrate, worker, controller)

    routing = orchestrate.route_review_result(
        run,
        _result("repairs_requested", _request(f"fix-{owner}", owner, "src/release.py")),
        agents=_live(worker),
    )

    assert routing.dispatches == []
    assert routing.replacements == []
    assert [item["owner"] for item in routing.operator_requests] == [owner]
    assert run.operator_fix_requests == routing.operator_requests
    assert run.review_resubmit_pending is False
    assert len(run.units) == 2
    assert (
        orchestrate.resubmit_review_if_ready(
            run,
            "landed-revision",
            sender=lambda _unit, _text: pytest.fail("operator-owned work was resubmitted"),
        )
        is False
    )


def test_disjoint_review_fixes_route_to_different_path_owners(orchestrate: ModuleType) -> None:
    first = _worker(orchestrate, "worker-a", "review-fixer", "src/a")
    second = _worker(orchestrate, "worker-b", "review-fixer", "src/b")
    run = _run(orchestrate, first, second, _controller(orchestrate))

    routing = orchestrate.route_review_result(
        run,
        _result(
            "repairs_requested",
            _request("fix-a", "review-fixer", "src/a/a.py"),
            _request("fix-b", "review-fixer", "src/b/b.py"),
        ),
        agents=_live(first, second),
    )

    assert [unit.name for unit, _ in routing.dispatches] == ["worker-a", "worker-b"]


def test_typed_result_round_trips_byte_identically_without_policy_parsing(
    orchestrate: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = (
        '{\r\n  "schema": "review_result.v1",\r\n  "outcome": "accepted",\r\n'
        '  "fix_requests": [],\r\n  "lens_results": {"derived_overall": "not a number",'
        ' "dimensions": null},\r\n  "finding_metadata": {"priority": "P0",'
        ' "confidence": 100}\r\n}\r\n'
    )
    run = _run(orchestrate, _controller(orchestrate))
    run_path = tmp_path / ".orchestrate" / "run.json"
    result_path = tmp_path / "result.json"
    result_path.write_bytes(raw.encode("utf-8"))
    run.save(run_path)
    monkeypatch.chdir(tmp_path)

    assert orchestrate.cmd_review_result(argparse.Namespace(file=str(result_path))) == 0
    restored = orchestrate.Run.load()

    assert restored.review_outcome == "accepted"
    assert restored.review_result == raw
    assert restored.review_result.encode("utf-8") == raw.encode("utf-8")


def test_accepted_outcome_dispatches_nothing_and_adds_no_metadata_gate(
    orchestrate: ModuleType,
) -> None:
    worker = _worker(orchestrate, "builder", "review-fixer", "src")
    run = _run(orchestrate, worker, _controller(orchestrate))
    raw = _result(
        "accepted",
        _request("must-be-ignored", "review-fixer", "src/file.py"),
        findings=[{"priority": "P0", "confidence": 100}],
    )

    routing = orchestrate.route_review_result(run, raw, agents=_live(worker))

    assert routing.dispatches == []
    assert routing.replacements == []
    assert worker.fix_requests == []
    assert run.review_resubmit_pending is False
    assert orchestrate.resubmit_review_if_ready(run, "revision") is False


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _git_out(cwd: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def _commit(cwd: Path, name: str) -> None:
    (cwd / name).write_text(f"{name}\n")
    _git(cwd, "add", name)
    _git(cwd, "commit", "-m", f"add {name}")


def test_clean_merged_keeps_a_landed_worker_with_an_outstanding_fix(
    orchestrate: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _commit(repo, "base.txt")
    base = _git_out(repo, "rev-parse", "HEAD")
    _git(repo, "branch", "orch/review-run")
    worktree = tmp_path / "orch-worker"
    _git(
        repo,
        "worktree",
        "add",
        str(worktree),
        "-b",
        "orch/review-run-worker",
        "orch/review-run",
    )
    _commit(worktree, "repair.txt")
    _git(repo, "checkout", "orch/review-run")
    _git(repo, "merge", "--no-ff", "--no-edit", "orch/review-run-worker")
    _git(repo, "checkout", "main")
    worker = orchestrate.Unit(
        name="worker",
        vendor="claude",
        task="/saga:work repair",
        role="review-fixer",
        paths=["repair.txt"],
        branch="orch/review-run-worker",
        worktree=str(worktree),
        status="done",
    )
    run = orchestrate.Run(
        run_id="review-run",
        source="test",
        base=base,
        branch="orch/review-run",
        units=[worker],
    )
    monkeypatch.chdir(repo)
    run.resolve_branch_once()
    assert orchestrate.reapable(worker, run) is True
    worker.fix_requests.append(_request("still-open", "review-fixer", "repair.txt"))

    closed, kept = orchestrate.reap(run, merged_only=True)

    assert closed == []
    assert kept == ["worker"]
    assert worktree.exists()
    assert _git_out(repo, "rev-parse", "--verify", "orch/review-run-worker")

    closed, kept = orchestrate.reap(run, merged_only=False)
    assert closed == []
    assert kept == ["worker"]
    assert worktree.exists()


def test_landed_work_repairs_resubmit_the_exact_revision_to_the_same_controller(
    orchestrate: ModuleType,
) -> None:
    controller = _controller(orchestrate)
    worker = _worker(orchestrate, "builder", "review-fixer", "src")
    run = _run(orchestrate, worker, controller)
    run.review_resubmit_pending = True
    sent: list[tuple[Any, str]] = []

    resubmitted = orchestrate.resubmit_review_if_ready(
        run,
        "0123456789abcdef",
        sender=lambda unit, text: sent.append((unit, text)),
    )

    assert resubmitted is True
    assert sent[0][0] is controller
    assert "0123456789abcdef" in sent[0][1]
    assert "same Code Review controller" in sent[0][1]
    assert controller.status == "running"
    assert run.review_resubmit_pending is False
    assert len(run.units) == 2
