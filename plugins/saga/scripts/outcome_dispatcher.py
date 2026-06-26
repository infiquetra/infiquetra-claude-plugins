#!/usr/bin/env python3
"""OutcomeOrchestrator dispatcher seam — route a leaf to its backend (U4).

This is the **single dispatcher seam** every subplot routes through (R5). It is the outcome-layer
counterpart to ``execution_spec.recompile_for_tier`` (the by-mode emitter fork, now extended with the
``team_emitter`` third leg): given a leaf and its chosen backend, it either **dispatches** — minting a
leaf saga id and a ``/resume`` return channel (the R9 bidirectional envelope's re-entry token out) —
or, when the backend cannot actually run, emits a **visible HALT-not-degrade receipt** (R5/R23) rather
than silently substituting a lesser backend.

U4 makes **team-execution the first real backend** (R6); the rest of the menu (fork / subagent /
cc-workflows-ultracode / `/goal` / manual) is wired in U9, so dispatching to one of those today yields a
HALT receipt — never a silent inline fallback. The *degrade-one-rung vs halt* decision based on operator
presence (R23) is U9; U4 owns only the HALT receipt: a chosen-but-unavailable backend halts and pages.

``make_dispatcher`` returns a ``Dispatcher`` (the callable ``outcome.advance`` consumes): it returns the
leaf saga id on a successful dispatch and raises ``BackendHaltError`` (carrying the receipt) on a HALT,
which the reconcile loop records and surfaces instead of dispatching to a lesser backend.

House pattern (mirrors the other ``outcome_*`` modules): pure functions over explicit values, the
``team_emitter`` wiring loaded lazily by path, no I/O at import.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import outcome_spec  # noqa: E402  (after the sys.path shim, by design)

# The backends actually runnable as of U4. team-execution is the first real backend (R6); inline is
# the always-available floor. The full menu (fork/subagent/cc-workflows-ultracode/goal/manual) is R6's
# remit but lands in U9 — until then, choosing one of those HALTs with a visible receipt (R5), never a
# silent substitution. Validated against the spec's closed NODE_BACKENDS vocabulary.
DEFAULT_AVAILABLE: tuple[str, ...] = ("inline", "team-execution")


class DispatcherError(ValueError):
    """A dispatch was rejected for a malformed request (unknown backend vocabulary, etc.)."""


@dataclass(frozen=True)
class HaltReceipt:
    """A visible record that a chosen backend could not run — the coordinator HALTED, not degraded.

    R5/R23: the seam never silently substitutes a lesser backend. The receipt names the unavailable
    backend, what *is* available, and why, so the report (U8) and the operator see exactly why a leaf
    is paused rather than silently running on an inferior tier.
    """

    outcome_id: str
    subplot_id: str
    backend: str
    reason: str
    available: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "halt",
            "outcome_id": self.outcome_id,
            "subplot_id": self.subplot_id,
            "backend": self.backend,
            "reason": self.reason,
            "available": list(self.available),
        }


class BackendHaltError(Exception):
    """A backend HALT (R5/R23): the chosen backend cannot run. Carries the :class:`HaltReceipt`.

    Owned by this backend module (never run as ``__main__``), so the engine's reconcile loop and this
    dispatcher reference the SAME class regardless of how the engine is launched — the per-leaf
    ``except`` in ``outcome._reconcile_once`` reliably catches it.
    """

    def __init__(self, receipt: HaltReceipt) -> None:
        super().__init__(receipt.reason)
        self.receipt = receipt


def dispatch(req: Any, *, available: Sequence[str] = DEFAULT_AVAILABLE) -> dict[str, Any]:
    """Route a leaf to its backend. Returns a ``dispatched`` or a ``halt`` result dict.

    ``req`` is duck-typed (``outcome_id`` / ``subplot_id`` / ``title`` / ``backend`` / ``repo_root``)
    so this module does not import ``outcome``. A dispatched result carries the minted leaf saga id and
    the ``/resume`` return channel (R9); a halt result carries a :class:`HaltReceipt` dict (R5/R23).
    """
    backend = str(req.backend)
    if backend not in outcome_spec.NODE_BACKENDS:
        raise DispatcherError(
            f"backend {backend!r} is not in the executor menu {outcome_spec.NODE_BACKENDS}"
        )
    if backend not in tuple(available):
        receipt = HaltReceipt(
            outcome_id=str(req.outcome_id),
            subplot_id=str(req.subplot_id),
            backend=backend,
            reason=(
                f"backend {backend!r} is not available yet (runnable backends: "
                f"{tuple(available)}) — HALT and page rather than silently substitute a lesser "
                f"backend (the full menu + degrade decision land in U9)"
            ),
            available=tuple(available),
        )
        return {"status": "halt", "receipt": receipt.to_dict()}
    leaf_saga_id = f"leaf-{req.outcome_id}-{req.subplot_id}"
    return {
        "status": "dispatched",
        "subplot_id": str(req.subplot_id),
        "backend": backend,
        "leaf_saga_id": leaf_saga_id,
        # The R9 re-entry token OUT — a stable native handoff, not a drift-prone pasted prompt.
        "return_channel": f"/resume {leaf_saga_id}",
    }


def make_dispatcher(*, available: Sequence[str] = DEFAULT_AVAILABLE) -> Callable[[Any], str]:
    """A ``Dispatcher`` for ``outcome.advance``: leaf saga id on dispatch, HALT raises (never silent)."""

    def _dispatch(req: Any) -> str:
        result = dispatch(req, available=available)
        if result["status"] == "halt":
            raise BackendHaltError(HaltReceipt(**_receipt_kwargs(result["receipt"])))
        return str(result["leaf_saga_id"])

    return _dispatch


def _receipt_kwargs(receipt: dict[str, Any]) -> dict[str, Any]:
    return {
        "outcome_id": receipt["outcome_id"],
        "subplot_id": receipt["subplot_id"],
        "backend": receipt["backend"],
        "reason": receipt["reason"],
        "available": tuple(receipt["available"]),
    }


# ---------------------------------------------------------------------------
# team-execution artifact (R5 — wiring the existing team_emitter)
# ---------------------------------------------------------------------------


def team_execution_artifact(execution_spec_obj: Any) -> str:
    """Emit the team-execution ``## Team Structure`` markdown for a leaf's execution spec (R5).

    Delegates to ``execution_spec.recompile_for_tier(spec, "team-execution")`` — the by-mode
    dispatcher seam whose third leg is now ``team_emitter`` — so the team-execution backend's runnable
    artifact is produced through the single seam, not reinvented here. Lazily loaded by path so this
    module is importable standalone.
    """
    import importlib.util

    path = Path(__file__).resolve().parent / "execution_spec.py"
    loaded = importlib.util.spec_from_file_location("execution_spec", path)
    assert loaded is not None and loaded.loader is not None
    module = importlib.util.module_from_spec(loaded)
    sys.modules.setdefault("execution_spec", module)
    loaded.loader.exec_module(module)
    return str(module.recompile_for_tier(execution_spec_obj, "team-execution"))


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Outcome dispatcher seam (R5) — dry-run a dispatch."
    )
    parser.add_argument("outcome_id")
    parser.add_argument("subplot_id")
    parser.add_argument("backend")
    parser.add_argument("--available", default=",".join(DEFAULT_AVAILABLE))
    args = parser.parse_args(argv)

    @dataclass(frozen=True)
    class _Req:
        outcome_id: str
        subplot_id: str
        title: str
        backend: str
        repo_root: Path

    req = _Req(args.outcome_id, args.subplot_id, args.subplot_id, args.backend, Path("."))
    try:
        result = dispatch(req, available=tuple(a for a in args.available.split(",") if a))
    except DispatcherError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
