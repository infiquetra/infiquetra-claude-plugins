#!/usr/bin/env python3
"""Derived-on-read report + the attention consolidator (U8).

Two operator-facing surfaces, both **derived on read** (R17) — computed every call from the committed
spec + the store, never from an operator-writable status field, so they **physically cannot drift**:

* **The attention consolidator** (R18/AE5/F3): when several leaves need the operator at once, bubble
  them into **one** ranked prompt — **type-tier first** (a *gate* = ready-to-ship → an *ambiguity* =
  needs-a-decision → a *failure* = needs-a-fix), then **unblock-leverage** within a tier (the item
  holding up the most downstream work first). Never N separate pages. A healthy steady state consolidates
  to an empty surface.
* **The report** (R19/F6): ``/outcome report`` regenerates a markdown digest to
  ``docs/outcomes/<id>/report.md`` — the Mermaid topology, per-subplot state + evidence + cost, the
  decision trail, and the consolidated attention prompt. **Overwritten from state** (never hand-edited),
  and **deterministic** (no wall-clock in the body), so re-running it on unchanged state yields a
  byte-identical artifact — it cannot drift from the truth.

Facet scope (the U8<->U10 acyclicity rule): this module depends only on the U5 completion barrier + the
U6 merge state — **never on U10**. The realized **cost** rollup (R24) is rendered **when present** and as
**"no data yet"** when absent, so U10 can populate it later without U8 depending on U10.

House pattern (mirrors the other ``outcome_*`` modules): pure functions over explicit values,
``outcome`` imported lazily to avoid a cycle, no I/O at import.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import outcome_orchestrator  # noqa: E402  (after the sys.path shim, by design)
import outcome_spec  # noqa: E402
import outcome_store  # noqa: E402

# Attention type-tiers (R18/AE5). LOWER sorts FIRST: a ready-to-ship gate is surfaced before a decision,
# which is surfaced before a failure — the operator ships the easy wins, then decides, then fixes.
TIER_GATE = 1  # a subplot ready to ship — needs the operator's merge/approve keystroke
TIER_AMBIGUITY = 2  # a backend HALT / unsatisfiable barrier — needs a decision
TIER_FAILURE = 3  # a negative terminal (failed/rejected/stalled) — needs a fix

_NEGATIVE_TERMINALS = frozenset({"failed", "rejected", "stalled"})


@dataclass
class AttentionItem:
    """One item the operator must attend — classified into a type-tier and ranked by unblock-leverage."""

    subplot_id: str
    kind: str  # gate / ambiguity / failure
    tier: int
    leverage: int  # how many downstream subplots this item is holding up (R18 unblock-leverage)
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "subplot_id": self.subplot_id,
            "kind": self.kind,
            "tier": self.tier,
            "leverage": self.leverage,
            "reason": self.reason,
        }


def _halted_subplots(store: Any) -> set[str]:
    """Subplots whose LATEST dispatch ledger record is a HALT (a still-live backend HALT — R23).

    State-aware, not sticky: a later ``commit`` (a successful re-dispatch) **supersedes** an earlier
    ``halt``, so a halted-then-recovered subplot is NOT reported as an ambiguity forever. We walk the
    ledger in order and keep, per subplot, the phase of its most recent ``dispatch`` record.
    """
    latest: dict[str, str] = {}
    for rec in outcome_store.read_ledger(store):
        if rec.get("kind") == "dispatch" and rec.get("phase") in ("halt", "commit"):
            sid = str(rec.get("subplot_id", ""))
            if sid:
                latest[sid] = str(rec.get("phase"))
    return {sid for sid, phase in latest.items() if phase == "halt"}


def consolidate(spec: Any, store: Any) -> list[AttentionItem]:
    """The single ranked operator prompt (R18/AE5): type-tier first, then unblock-leverage.

    Derived purely from state (R17). Each node is classified into **at most one** attention kind, in
    precedence order so the classification is unambiguous:

    * **failure** (tier 3) — its live derived state is a negative terminal (``failed`` / ``rejected`` /
      ``stalled``); needs a fix.
    * **ambiguity** (tier 2) — its LATEST dispatch is a HALT **and** it is not terminal (a still-live
      backend HALT, not a halted-then-recovered/-done node); needs a decision.
    * **gate** (tier 1) — it is ``gated`` / ``risky`` / ``destructive`` and currently ``dispatched``
      (in-flight, so it will stop at the operator's merge/approve gate); ready to ship pending a keystroke.

    Plus **one outcome-level approval gate** (tier 1) when the current ``spec_revision``'s frontier is
    **unapproved** while a ready frontier exists (R20): nothing dispatches until the operator approves,
    so this is the real #1 action — and it is why a started-but-unapproved outcome is NOT a healthy empty
    surface.

    Sorted **tier ascending** (gate -> ambiguity -> failure, AE5), then **leverage descending** (the item
    holding up the most downstream work first), then ``subplot_id`` for a deterministic tie-break.
    ``leverage`` is ``len(blocked_subtree({sid}))`` — the downstream subtree the item is gating (R22).
    """
    import outcome as outcome_engine
    import outcome_decompose

    states = outcome_engine.derive_states(spec, store)
    halted = _halted_subplots(store)
    items: list[AttentionItem] = []

    # The outcome-level R20 approval gate: an unapproved frontier dispatches nothing -> the #1 action.
    ready = sorted(sid for sid, st in states.items() if st == "ready")
    if ready and not outcome_decompose.frontier_approved(store, spec.spec_revision):
        items.append(
            AttentionItem(
                "<frontier>",
                "approval",
                TIER_GATE,
                len(ready),
                f"frontier r{spec.spec_revision} awaiting `/outcome approve` — no leaf dispatches "
                f"until approved (R20)",
            )
        )

    for node in spec.nodes:
        sid = node.subplot_id
        state = states.get(sid, "")
        leverage = len(outcome_orchestrator.blocked_subtree(spec, {sid}))
        if state in _NEGATIVE_TERMINALS:
            items.append(
                AttentionItem(
                    sid, "failure", TIER_FAILURE, leverage, f"{state} — needs a fix (R18)"
                )
            )
        elif sid in halted and state not in outcome_spec.TERMINAL_STATES:
            # A still-live HALT (not a halted-then-done/recovered node, which has superseded the halt).
            items.append(
                AttentionItem(
                    sid,
                    "ambiguity",
                    TIER_AMBIGUITY,
                    leverage,
                    "backend HALT — needs a decision (R23)",
                )
            )
        elif (node.gated or node.risky or node.destructive) and state == "dispatched":
            flags = ",".join(
                f
                for f, on in (
                    ("gated", node.gated),
                    ("risky", node.risky),
                    ("destructive", node.destructive),
                )
                if on
            )
            items.append(
                AttentionItem(
                    sid, "gate", TIER_GATE, leverage, f"ready to ship ({flags}) — operator merges"
                )
            )
    items.sort(key=lambda it: (it.tier, -it.leverage, it.subplot_id))
    return items


def consolidated_prompt(items: list[AttentionItem]) -> str:
    """Render the ranked attention items as the ONE operator prompt (R18) — empty surface when healthy."""
    if not items:
        return "✓ no operator attention needed — every non-gated leaf is auto-advancing (R17)."
    lines = [f"Operator attention ({len(items)} item{'s' if len(items) != 1 else ''}, ranked):"]
    for i, it in enumerate(items, 1):
        lev = f" · holds up {it.leverage} downstream" if it.leverage else ""
        lines.append(f"{i}. [{it.kind}] {it.subplot_id} — {it.reason}{lev}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# The derived-on-read report (R19/F6) — overwritten from state, deterministic, cannot drift
# ---------------------------------------------------------------------------


def _degrade_receipts(store: Any) -> list[dict[str, Any]]:
    """Every recorded backend-degrade receipt (R23), in ledger order (deterministic)."""
    return [
        rec
        for rec in outcome_store.read_ledger(store)
        if rec.get("phase") == "degrade" and rec.get("kind") == "degrade"
    ]


def _evidence_cell(node: Any) -> str:
    """A one-line evidence summary for a subplot (PR / issue / recorded evidence) — '—' when none."""
    bits: list[str] = []
    pr = str(node.github.get("pr", ""))
    issue = str(node.github.get("issue", "") or node.github.get("sub_issue", ""))
    if pr:
        bits.append(f"PR {pr}")
    if issue:
        bits.append(f"issue {issue}")
    for key in ("ci", "review", "qa"):
        val = node.evidence.get(key)
        if val:
            bits.append(f"{key}:{val}")
    return ", ".join(bits) if bits else "—"


_COST_RENAME = {"wall_seconds": "wall_s"}


def _cost_cell(node: Any) -> str:
    """A subplot's realized cost (R24) — 'no data yet' only when the cost dict is EMPTY (U10 populates it).

    Renders **every** present key (sorted for determinism; ``wall_seconds`` shown as ``wall_s``), so a
    non-empty cost dict with only an unmodelled key (e.g. ``operator_touches``) is shown, not dropped to
    "no data yet" — and a real ``0`` value renders rather than being treated as absent.
    """
    if not node.cost:
        return "no data yet"
    return ", ".join(f"{_COST_RENAME.get(k, k)}:{node.cost[k]}" for k in sorted(node.cost))


def display_percent(done: int, total: int) -> int:
    """Progress percent for DISPLAY — never 100 unless actually complete, never rounds a real-progress
    outcome to 0. ``round()`` is banker's (100*199/200 -> 100), which would show 100% for an incomplete
    outcome and invite a premature parent-close; cap at 99 below completion and floor a non-zero at 1.
    """
    if not total:
        return 0
    if done >= total:
        return 100
    pct = int(100 * done / total + 0.5)  # half-up, intuitive
    return min(99, max(1 if done else 0, pct))


def report_markdown(repo_root: Path, outcome_id: str, *, store: Any | None = None) -> str:
    """Build the deterministic markdown report from state (R19) — no wall-clock, so it cannot drift.

    Carries the Mermaid topology (KTD12), the consolidated attention prompt (R18), a per-subplot table
    (state + evidence + cost), the cost rollup (R24, "no data yet" when absent), and the decision trail
    (R26) — the "why" that makes cold re-entry non-lossy (F5).
    """
    import outcome as outcome_engine

    spec = outcome_engine.load_spec(repo_root, outcome_id)
    store = store if store is not None else outcome_engine._store(repo_root, outcome_id)
    states = outcome_engine.derive_states(spec, store)
    done = sum(1 for s in states.values() if s == "done")
    total = len(spec.nodes)
    pct = display_percent(done, total)
    # Strip newlines from the objective so a multi-line objective cannot split the H1 (determinism +
    # render-safety); the objective is prose so other punctuation is fine in an H1.
    objective = " ".join(spec.objective.splitlines())

    lines: list[str] = [
        f"# Outcome: {objective}",
        "",
        f"**Outcome ID:** `{spec.outcome_id}` · **Revision:** {spec.spec_revision} · "
        f"**Progress:** {done}/{total} ({pct}%)",
        "",
        "## Topology",
        "",
        "```mermaid",
        outcome_engine.graph_mermaid(repo_root, outcome_id, store=store).rstrip("\n"),
        "```",
        "",
        "## Attention (consolidated)",
        "",
        consolidated_prompt(consolidate(spec, store)),
        "",
        "## Subplots",
        "",
        "| Subplot | State | Evidence | Cost |",
        "| --- | --- | --- | --- |",
    ]
    for node in spec.nodes:
        sid = node.subplot_id
        lines.append(
            f"| `{sid}` | {states.get(sid, '?')} | {_evidence_cell(node)} | {_cost_cell(node)} |"
        )

    degrades = _degrade_receipts(store)
    if degrades:
        # R23: a visible downgrade receipt for every autonomous+away leaf that degraded one rung.
        lines += ["", "## Degradations", ""]
        for d in degrades:
            lines.append(
                f"- `{d.get('subplot_id', '?')}`: {d.get('from_backend', '?')} → "
                f"{d.get('to_backend', '?')} — {d.get('reason', '')}"
            )

    lines += ["", "## Cost rollup", ""]
    if spec.cost_rollup:
        for key, val in sorted(spec.cost_rollup.items()):
            lines.append(f"- **{key}:** {val}")
    else:
        lines.append("_no data yet — the realized cost rollup (R24) is populated by U10._")

    lines += ["", "## Decision trail", ""]
    if spec.decision_trail:
        for entry in spec.decision_trail:
            rev = entry.get("revision", "?")
            reason = entry.get("reason", "")
            lines.append(f"- r{rev}: {reason}" if reason else f"- r{rev}")
    else:
        lines.append("_—_")

    return "\n".join(lines) + "\n"


def write_report(repo_root: Path, outcome_id: str, *, store: Any | None = None) -> Path:
    """Overwrite ``docs/outcomes/<id>/report.md`` from state (R19) and return its path.

    Deterministic + overwrite-from-state: regenerating on unchanged state produces a byte-identical file,
    so the report physically cannot drift from the truth (it is never hand-edited).
    """
    text = report_markdown(repo_root, outcome_id, store=store)
    path = (
        Path(repo_root)
        / "docs"
        / "outcomes"
        / outcome_store._safe_name(outcome_id, what="outcome_id")
        / "report.md"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Outcome report + attention consolidator (U8).")
    parser.add_argument("--repo-root", default=".")
    sub = parser.add_subparsers(dest="command", required=True)
    p_report = sub.add_parser("report", help="regenerate docs/outcomes/<id>/report.md from state")
    p_report.add_argument("outcome_id")
    p_attend = sub.add_parser("attend", help="print the consolidated attention prompt")
    p_attend.add_argument("outcome_id")

    args = parser.parse_args(argv)
    import outcome as outcome_engine

    root = Path(args.repo_root).resolve()
    if args.command == "report":
        path = write_report(root, args.outcome_id)
        print(json.dumps({"report": str(path)}))
    elif args.command == "attend":
        spec = outcome_engine.load_spec(root, args.outcome_id)
        store = outcome_engine._store(root, args.outcome_id)
        print(consolidated_prompt(consolidate(spec, store)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
