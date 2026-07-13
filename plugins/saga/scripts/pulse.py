#!/usr/bin/env python3
"""Pulse — the `/pulse` live fleet-telemetry surface (#400).

A strictly read-only projection of what the fleet is doing right now, rendered from REAL
signals only:

* **Board state** — live projectV2 columns via mission-control's own read path
  (``sdlc_manager.py --format json board view --project <p>``, one subprocess per project,
  runner injectable for tests). Pulse never re-implements the GraphQL read.
* **Agent/run state** — ``saga.py``'s derived-on-read tick history (``scan`` for the fleet,
  ``read_ticks`` for a ``--saga`` focus). Pulse renders exactly the fields the scanner derives;
  it introduces no committed status field anywhere (AC3, the /outcome binding decision).
* **Run-fact ledger** — the hash-chained ``run_ledger.py`` substrate (#401) and its own
  reducers (``rollup``/``reuse_ratio``). The chain verdict is rendered as an explicit banner;
  a broken chain SUPPRESSES all aggregates (they are no longer trustworthy).
* **Outcome economics** — ``outcome_costs.rollup`` for the newest outcome spec under
  ``docs/outcomes/``, inheriting that module's honesty stance verbatim.

Honesty contract (the U8 stance + the ce-product-pulse no-false-precision posture): every
panel is tri-state — ``ok`` / ``no-data`` / ``unavailable`` (the ledger adds ``chain-broken``).
An empty or unreadable source renders an explicit label ("no data yet", "unavailable
(<reason>)"), NEVER a silent zero or a fabricated aggregate. Pulse cites numbers and lets the
operator judge — it hardcodes no thresholds and is not a gate. It has no experiment-loop
primitives (no target, baseline, budget, or stop condition) — that bounded loop is
``/optimize``'s settled territory (AC6).

Zero writes: Pulse writes no tick, no ledger fact, no cache file — enforced by test
(``tests/test_pulse_telemetry.py::test_pulse_writes_nothing_anywhere``).

House pattern: pure functions over explicit values, no I/O at import, ``sys.path`` shim +
same-directory imports, stdlib only. ``--watch`` is a bounded re-render loop (iterations
required), not a daemon. Plan: ``docs/plans/2026-07-13-400-pulse-live-telemetry-plan.md``.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_ledger  # noqa: E402  (after the sys.path shim, by design)
import saga as saga_engine  # noqa: E402
import status_card  # noqa: E402

PULSE_SCHEMA = "pulse_snapshot.v1"

# The saga.scan() candidate fields Pulse projects — EXACTLY the scanner's derived fields, no
# pulse-owned addition (AC3). A test pins this list against scan()'s output keys.
RUN_FIELDS = (
    "saga_id",
    "kind",
    "lifecycle_phase",
    "phase",
    "phase_status",
    "next_step",
    "updated_at",
    "issue_ref",
    "branch",
    "orchestration_mode",
)

_NO_DATA = "no data yet"


def _fmt_num(value: float) -> str:
    """Cite a number exactly: integral floats render as ints, others rounded to 2 places."""
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}"


# --------------------------------------------------------------------------- board (AC1)


def default_sdlc_manager(repo_root: Path) -> Path:
    """The in-repo mission-control read script, resolved from the repo root."""
    return repo_root / "plugins" / "mission-control" / "scripts" / "sdlc_manager.py"


def read_board_state(
    projects: Sequence[str],
    *,
    sdlc_manager_path: Path,
    runner: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    """Live board columns via mission-control's own JSON read path — never a re-implementation.

    Tri-state: ``ok`` (payload read), ``no-data`` (no project requested), ``unavailable``
    (script missing, non-zero exit, or unparseable output — with the reason). A missing field
    on an item renders ``"?"``, never a fabricated value.
    """
    if not projects:
        return {"status": "no-data", "reason": "no project requested", "projects": {}}
    if not sdlc_manager_path.is_file():
        return {
            "status": "unavailable",
            "reason": f"sdlc_manager.py not found at {sdlc_manager_path}",
            "projects": {},
        }
    out: dict[str, Any] = {}
    for project in projects:
        cmd = [
            sys.executable,
            str(sdlc_manager_path),
            "--format",
            "json",
            "board",
            "view",
            "--project",
            project,
        ]
        try:
            proc = runner(cmd, capture_output=True, text=True, timeout=120)
        except Exception as exc:  # noqa: BLE001 — degrade explicitly, never crash the surface
            return {"status": "unavailable", "reason": f"{project}: {exc}", "projects": {}}
        if getattr(proc, "returncode", 1) != 0:
            reason = (getattr(proc, "stderr", "") or "").strip().splitlines()
            detail = reason[-1] if reason else f"exit {getattr(proc, 'returncode', '?')}"
            return {"status": "unavailable", "reason": f"{project}: {detail}", "projects": {}}
        try:
            payload = json.loads(getattr(proc, "stdout", "") or "")
        except (json.JSONDecodeError, ValueError):
            return {
                "status": "unavailable",
                "reason": f"{project}: unparseable board JSON",
                "projects": {},
            }
        columns_raw = payload.get("columns", {}) if isinstance(payload, dict) else {}
        columns: dict[str, dict[str, Any]] = {}
        items: list[dict[str, Any]] = []
        for status_name, nodes in (columns_raw or {}).items():
            node_list = nodes if isinstance(nodes, list) else []
            columns[str(status_name)] = {"count": len(node_list)}
            for node in node_list:
                content = node.get("content", {}) if isinstance(node, dict) else {}
                if not isinstance(content, dict):
                    content = {}
                repo = content.get("repository", {})
                items.append(
                    {
                        "repo": (repo.get("name") if isinstance(repo, dict) else None) or "?",
                        "number": content.get("number", "?"),
                        "title": str(content.get("title") or "?")[:80],
                        "status": str(status_name),
                        "created_at": (node.get("createdAt") if isinstance(node, dict) else None)
                        or "?",
                    }
                )
        out[project] = {"columns": columns, "items": items}
    return {"status": "ok", "projects": out}


# --------------------------------------------------------------------------- runs (AC2/AC3)


def read_run_state(
    repo_root: Path,
    *,
    max_sagas: int = 10,
    focus_saga: str | None = None,
) -> dict[str, Any]:
    """Fleet run state, derived on read from the saga tick history — never a committed status.

    Projects EXACTLY the ``saga.scan()`` candidate fields (``RUN_FIELDS``); with
    ``focus_saga``, adds that saga's whole ``read_ticks`` trajectory. Writes nothing.
    """
    candidates = saga_engine.scan(repo_root)
    sagas = [{f: c.get(f) for f in RUN_FIELDS} for c in candidates[: max(max_sagas, 0)]]
    state: dict[str, Any] = {
        "status": "ok" if candidates else "no-data",
        "total": len(candidates),
        "sagas": sagas,
        "focus_ticks": None,
    }
    if focus_saga:
        state["focus_ticks"] = [
            {
                "phase": t.phase,
                "phase_status": t.phase_status,
                "lifecycle_phase": t.lifecycle_phase,
                "updated_at": t.updated_at,
                "next_step": t.next_step,
            }
            for t in saga_engine.read_ticks(repo_root, focus_saga)
        ]
    return state


# --------------------------------------------------------------------------- ledger (AC2/AC4/AC5)


def read_ledger_state(ledger: run_ledger.RunLedger) -> dict[str, Any]:
    """The run-fact ledger panel, computed by the ledger's OWN reducers — derive-on-read.

    ``chain-broken`` suppresses every aggregate (the numbers are no longer trustworthy); an
    absent/empty ledger is ``no-data`` — an explicit "no data yet", never a silent zero.
    """
    snapshot = run_ledger.read_snapshot(ledger)
    report = snapshot.report
    chain = {"ok": report.ok, "break_index": report.break_index, "reason": report.reason}
    base: dict[str, Any] = {
        "path": str(ledger.path),
        "chain": chain,
        "fact_counts": None,
        "spend": None,
        "reuse_ratio": None,
        "engine": None,
        "last_fact_at": None,
    }
    if not report.ok:
        return {"status": "chain-broken", **base}
    if not snapshot.records:
        return {"status": "no-data", "reason": "no run facts recorded", **base}

    kind_counts = Counter(str(r.get("kind", "?")) for r in snapshot.records)
    base["fact_counts"] = {kind: kind_counts.get(kind, 0) for kind in sorted(run_ledger.FACT_KINDS)}
    spend_rollup = run_ledger.rollup(ledger, "spend")
    base["spend"] = spend_rollup or None
    base["reuse_ratio"] = run_ledger.reuse_ratio(ledger)
    engine_facts = [r for r in snapshot.records if r.get("kind") == "engine"]
    if engine_facts:
        base["engine"] = {
            "by_status": dict(Counter(str(r.get("status", "?")) for r in engine_facts)),
            "proof_integrity": dict(
                Counter(str(r.get("proof_integrity_status", "?")) for r in engine_facts)
            ),
        }
    base["last_fact_at"] = snapshot.records[-1].get("at")
    return {"status": "ok", **base}


# --------------------------------------------------------------------------- outcome economics


def read_outcome_costs_state(
    repo_root: Path,
    *,
    runner: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """The newest outcome's realized-cost rollup via ``outcome_costs.rollup`` — no new source.

    ``{}`` from the reducer is that module's own defined-empty → ``no-data`` here; a read
    failure is ``unavailable (<reason>)``, never a fabricated rollup.
    """
    specs = sorted((repo_root / "docs" / "outcomes").glob("*/outcome-spec.json"))
    if not specs:
        return {
            "status": "no-data",
            "reason": "no outcome specs under docs/outcomes/",
            "outcome_id": None,
            "rollup": None,
        }
    import outcome_costs  # noqa: PLC0415 — lazy, same-directory shim import
    import outcome_spec  # noqa: PLC0415
    import outcome_store  # noqa: PLC0415

    spec_path = max(specs, key=lambda p: p.stat().st_mtime)
    try:
        spec = outcome_spec.OutcomeSpec.from_dict(json.loads(spec_path.read_text(encoding="utf-8")))
        store = outcome_store.Store.for_outcome(spec.outcome_id, repo_root, runner=runner)
        roll = outcome_costs.rollup(spec, store)
    except Exception as exc:  # noqa: BLE001 — degrade explicitly, never crash the surface
        return {
            "status": "unavailable",
            "reason": f"{spec_path.parent.name}: {exc}",
            "outcome_id": None,
            "rollup": None,
        }
    if not roll:
        return {
            "status": "no-data",
            "reason": "no leaf recorded cost yet",
            "outcome_id": spec.outcome_id,
            "rollup": None,
        }
    return {"status": "ok", "outcome_id": spec.outcome_id, "rollup": roll}


# --------------------------------------------------------------------------- snapshot


def snapshot(
    *,
    at: str,
    board: dict[str, Any],
    runs: dict[str, Any],
    ledger: dict[str, Any],
    outcome_costs: dict[str, Any],
) -> dict[str, Any]:
    """Assemble the ``pulse_snapshot.v1`` machine shape. ``at`` is caller-supplied (no clock)."""
    return {
        "schema": PULSE_SCHEMA,
        "at": at,
        "board": board,
        "runs": runs,
        "ledger": ledger,
        "outcome_costs": outcome_costs,
    }


# --------------------------------------------------------------------------- card + render


def _board_row(board: dict[str, Any]) -> status_card.CardRow:
    status = board.get("status")
    if status == "ok":
        parts = []
        for name, proj in board.get("projects", {}).items():
            total = sum(c.get("count", 0) for c in proj.get("columns", {}).values())
            parts.append(f"{name}: {total} items")
        label = "Board — " + ("; ".join(parts) or "0 projects")
        ref = "; ".join(
            f"{name}: "
            + ", ".join(f"{col} {c['count']}" for col, c in sorted(proj["columns"].items()))
            for name, proj in board.get("projects", {}).items()
        )
        return status_card.CardRow("board", label[:52], status_card.CardState.IN_PROGRESS, ref=ref)
    if status == "unavailable":
        label = f"Board — unavailable ({board.get('reason', '?')})"
        return status_card.CardRow("board", label[:52], status_card.CardState.BLOCKED, ref=None)
    label = f"Board — {_NO_DATA} ({board.get('reason', 'no project requested')})"
    return status_card.CardRow("board", label[:52], status_card.CardState.NOT_REACHED, ref=None)


def _runs_row(runs: dict[str, Any]) -> status_card.CardRow:
    if runs.get("status") != "ok":
        return status_card.CardRow(
            "runs",
            f"Runs — {_NO_DATA} (no saga ticks)",
            status_card.CardState.NOT_REACHED,
            ref=None,
        )
    sagas = runs.get("sagas", [])
    newest = sagas[0] if sagas else {}
    label = f"Runs — {runs.get('total', 0)} saga(s), newest {newest.get('saga_id', '?')}"
    ref = (
        f"{newest.get('saga_id', '?')}: lifecycle={newest.get('lifecycle_phase') or '?'} "
        f"phase={newest.get('phase')} status={newest.get('phase_status') or '?'} "
        f"updated={newest.get('updated_at') or '?'}"
    )
    return status_card.CardRow("runs", label[:52], status_card.CardState.IN_PROGRESS, ref=ref)


def _ledger_rows(ledger: dict[str, Any]) -> list[status_card.CardRow]:
    status = ledger.get("status")
    path = ledger.get("path", "?")
    if status == "chain-broken":
        chain = ledger.get("chain", {})
        label = (
            f"Ledger — chain BROKEN at record {chain.get('break_index')} ({chain.get('reason')})"
        )
        return [
            status_card.CardRow("chain", label[:52], status_card.CardState.FAILED, ref=path),
            status_card.CardRow(
                "spend",
                "Spend — suppressed (broken chain)",
                status_card.CardState.FAILED,
                ref=path,
            ),
            status_card.CardRow(
                "engine",
                "Engine facts — suppressed (broken chain)",
                status_card.CardState.FAILED,
                ref=path,
            ),
        ]
    if status == "no-data":
        return [
            status_card.CardRow(
                "chain",
                f"Ledger — {_NO_DATA} (no run facts recorded)",
                status_card.CardState.NOT_REACHED,
                ref=None,
            ),
            status_card.CardRow(
                "spend", f"Spend — {_NO_DATA}", status_card.CardState.NOT_REACHED, ref=None
            ),
            status_card.CardRow(
                "engine",
                f"Engine facts — {_NO_DATA}",
                status_card.CardState.NOT_REACHED,
                ref=None,
            ),
        ]
    counts = ledger.get("fact_counts") or {}
    total = sum(counts.values())
    chain_row = status_card.CardRow(
        "chain",
        f"Ledger — chain ok, {total} fact(s)",
        status_card.CardState.DONE,
        ref=f"{path} — " + ", ".join(f"{k}={v}" for k, v in counts.items()),
    )
    spend = ledger.get("spend") or {}
    tokens = spend.get("tokens", {}).get("sum")
    wall = spend.get("wall_seconds", {}).get("sum")
    reuse = ledger.get("reuse_ratio")
    if tokens is None and wall is None:
        spend_row = status_card.CardRow(
            "spend", f"Spend — {_NO_DATA}", status_card.CardState.NOT_REACHED, ref=None
        )
    else:
        bits = []
        if tokens is not None:
            bits.append(f"{_fmt_num(tokens)} tokens")
        if reuse is not None:
            bits.append(f"reuse {reuse:.2f}")
        if wall is not None:
            bits.append(f"{_fmt_num(wall)} wall-s")
        spend_row = status_card.CardRow(
            "spend",
            ("Spend — " + " · ".join(bits))[:52],
            status_card.CardState.IN_PROGRESS,
            ref=f"{path} — spend facts: " + " · ".join(bits),
        )
    engine = ledger.get("engine")
    if engine:
        by_status = ", ".join(f"{k}={v}" for k, v in sorted(engine["by_status"].items()))
        proof = ", ".join(f"{k}={v}" for k, v in sorted(engine["proof_integrity"].items()))
        engine_row = status_card.CardRow(
            "engine",
            f"Engine facts — {by_status}"[:52],
            status_card.CardState.IN_PROGRESS,
            ref=f"{path} — engine status: {by_status}; proof integrity: {proof}",
        )
    else:
        engine_row = status_card.CardRow(
            "engine", f"Engine facts — {_NO_DATA}", status_card.CardState.NOT_REACHED, ref=None
        )
    return [chain_row, spend_row, engine_row]


def _outcome_row(oc: dict[str, Any]) -> status_card.CardRow:
    status = oc.get("status")
    if status == "ok":
        roll = oc.get("rollup") or {}
        bits = [f"{roll.get('leaves_with_cost', 0)}/{roll.get('leaves_total', 0)} leaves"]
        if "tokens" in roll:
            bits.append(f"{_fmt_num(roll['tokens'])} tokens")
        if "wall_seconds_serial" in roll:
            bits.append(
                f"wall {_fmt_num(roll['wall_seconds_parallel'])}s dag / "
                f"{_fmt_num(roll['wall_seconds_serial'])}s serial"
            )
        label = f"Outcome {oc.get('outcome_id', '?')} — " + " · ".join(bits)
        return status_card.CardRow(
            "outcome",
            label[:52],
            status_card.CardState.IN_PROGRESS,
            ref=f"outcome_costs.rollup({oc.get('outcome_id')}): " + " · ".join(bits),
        )
    if status == "unavailable":
        label = f"Outcome costs — unavailable ({oc.get('reason', '?')})"
        return status_card.CardRow("outcome", label[:52], status_card.CardState.BLOCKED, ref=None)
    label = f"Outcome costs — {_NO_DATA} ({oc.get('reason', '?')})"
    return status_card.CardRow("outcome", label[:52], status_card.CardState.NOT_REACHED, ref=None)


def project_pulse(snap: dict[str, Any]) -> status_card.CardSpec:
    """Build the fixed-row summary-projection card for one pulse snapshot.

    Six rows, always: Board · Runs · Ledger chain · Spend · Engine facts · Outcome costs.
    State encodes SOURCE HEALTH only (ok/no-data/unavailable/chain-broken) — never a judgment
    threshold; the numbers live in the labels and the indexed evidence footer.
    """
    rows = [
        _board_row(snap.get("board", {})),
        _runs_row(snap.get("runs", {})),
        *_ledger_rows(snap.get("ledger", {})),
        _outcome_row(snap.get("outcome_costs", {})),
    ]
    return status_card.CardSpec(
        archetype="summary-projection",
        header=status_card.CardHeader(surface="/pulse", id=str(snap.get("at", "?"))),
        rows=tuple(rows),
    )


def render(snap: dict[str, Any]) -> str:
    """Human render: the constant-height card + per-saga detail lines + focus trajectory."""
    out = [status_card.render(project_pulse(snap))]
    runs = snap.get("runs", {})
    sagas = runs.get("sagas", [])
    if sagas:
        total = runs.get("total", len(sagas))
        out.append(f"sagas (showing {len(sagas)} of {total}, newest first):")
        for s in sagas:
            out.append(
                f"  {s.get('saga_id', '?')}: lifecycle={s.get('lifecycle_phase') or '?'} "
                f"phase={s.get('phase')} status={s.get('phase_status') or '?'} "
                f"next={s.get('next_step') or '?'} updated={s.get('updated_at') or '?'}"
            )
    ticks = runs.get("focus_ticks")
    if ticks is not None:
        out.append(f"focus trajectory ({len(ticks)} tick(s), oldest first):")
        for i, t in enumerate(ticks, 1):
            out.append(
                f"  tick {i}: lifecycle={t.get('lifecycle_phase') or '?'} "
                f"phase={t.get('phase')} status={t.get('phase_status') or '?'} "
                f"updated={t.get('updated_at') or '?'}"
            )
    board = snap.get("board", {})
    if board.get("status") == "ok":
        for name, proj in board.get("projects", {}).items():
            cols = " · ".join(f"{col} {c['count']}" for col, c in sorted(proj["columns"].items()))
            out.append(f"board {name}: {cols or 'no columns'}")
            for item in proj.get("items", [])[:20]:
                out.append(f"  [{item['status']}] {item['repo']}#{item['number']}: {item['title']}")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------- CLI


def build_snapshot(
    *,
    at: str,
    repo_root: Path,
    projects: Sequence[str],
    no_board: bool,
    sdlc_manager_path: Path,
    ledger: run_ledger.RunLedger,
    max_sagas: int,
    focus_saga: str | None,
    board_runner: Callable[..., Any] = subprocess.run,
    outcome_runner: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Read all four sources and assemble one snapshot (the per-refresh unit of work)."""
    if no_board:
        board: dict[str, Any] = {
            "status": "no-data",
            "reason": "board read skipped (--no-board)",
            "projects": {},
        }
    else:
        board = read_board_state(projects, sdlc_manager_path=sdlc_manager_path, runner=board_runner)
    return snapshot(
        at=at,
        board=board,
        runs=read_run_state(repo_root, max_sagas=max_sagas, focus_saga=focus_saga),
        ledger=read_ledger_state(ledger),
        outcome_costs=read_outcome_costs_state(repo_root, runner=outcome_runner),
    )


def watch(
    build: Callable[[], dict[str, Any]],
    emit: Callable[[str], None],
    *,
    interval: float,
    iterations: int,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Bounded refresh loop — re-snapshot and re-render ``iterations`` times, then stop.

    Not a daemon: ``iterations`` is required and finite (KTD4). ``sleep`` is injectable so the
    loop is unit-testable without wall-clock time.
    """
    for i in range(iterations):
        emit(render(build()))
        if i < iterations - 1:
            sleep(interval)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Pulse — live fleet telemetry from real signals (read-only, #400)."
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--project",
        action="append",
        default=[],
        help="Board project(s) to read (repeatable). None -> board panel reads 'no data'.",
    )
    parser.add_argument("--json", action="store_true", help="Emit pulse_snapshot.v1 JSON.")
    parser.add_argument("--saga", default=None, help="Focus saga id — renders its trajectory.")
    parser.add_argument("--max-sagas", type=int, default=10)
    parser.add_argument("--no-board", action="store_true", help="Skip the board subprocess.")
    parser.add_argument("--sdlc-manager", type=Path, default=None)
    parser.add_argument(
        "--ledger-path",
        type=Path,
        default=None,
        help="Override the run-fact ledger file (default: resolved from the git common dir).",
    )
    parser.add_argument("--watch", action="store_true", help="Bounded refresh loop.")
    parser.add_argument("--interval", type=float, default=15.0)
    parser.add_argument(
        "--iterations", type=int, default=None, help="Required with --watch (no daemon)."
    )
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    sdlc_manager_path = (
        args.sdlc_manager if args.sdlc_manager is not None else default_sdlc_manager(repo_root)
    )
    if args.ledger_path is not None:
        ledger = run_ledger.RunLedger(path=args.ledger_path)
    else:
        try:
            ledger = run_ledger.RunLedger.resolve(repo_root)
        except Exception:  # noqa: BLE001 — not a git repo etc.; an absent ledger is a no-data panel
            ledger = run_ledger.RunLedger(path=repo_root / "run-facts.jsonl")

    def build() -> dict[str, Any]:
        return build_snapshot(
            at=datetime.now(UTC).isoformat(timespec="seconds"),
            repo_root=repo_root,
            projects=args.project,
            no_board=args.no_board,
            sdlc_manager_path=sdlc_manager_path,
            ledger=ledger,
            max_sagas=args.max_sagas,
            focus_saga=args.saga,
        )

    if args.watch:
        if args.iterations is None or args.iterations < 1:
            parser.error("--watch requires --iterations N (a bounded loop, not a daemon)")
        return watch(
            build, lambda text: print(text), interval=args.interval, iterations=args.iterations
        )

    snap = build()
    if args.json:
        print(json.dumps(snap, indent=2, default=str))
    else:
        print(render(snap), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
