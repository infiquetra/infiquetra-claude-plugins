#!/usr/bin/env python3
"""Sampled shadow-audit: replay-one-rung-down tier-sufficiency evidence (#402 U5).

Samples 1-in-N completed units, computes each sample's one-rung-down tier (reusing the
already-shipped ``execution_spec.adjacent_tier``), records a sufficient/insufficient verdict into
the evidence ledger (#398) under a ``shadow-audit:<stage>:<unit-id>`` namespace, and renders a
per-stage tier-sufficiency-rate report -- turning "was this tier choice actually necessary" from
reasoning into measured, sampled evidence.

This module NEVER spawns an Agent itself -- a Python script cannot call the Agent tool, only a
Claude-driven flow can. It owns: the sampling decision (``sample``/``sample_gated``), the
one-rung-down tier computation, the sufficient/insufficient classification (a built-in
whitespace-normalized exact-match ``classify()`` for simple diffable outputs, or a verdict the
invoking flow supplies when judgment was required), the ledger write (``record``), and the report
(``report``). The actual replay dispatch -- spawning a real agent to redo a completed unit one
rung down -- is performed by whichever Claude-driven flow invokes this module; that flow's own
Agent-tool spawn for the replay MUST follow the sandbox-spawn-site ad-hoc rule
(``subagent_type: saga:readonly-verifier`` + ``isolation: "worktree"``,
``plugins/saga/references/sandbox-spawn-sites.md``).

Gating (R8/KTD9, reusing ``execution_spec.emit_workflow_script``'s existing ``unattended``
vocabulary rather than inventing new terms): attended mode (default) is OFF unless the caller
passes ``--yes`` (a one-shot override) or a committed ``.saga/shadow-audit.json``
``{"enabled": true}`` (a standing per-repo default) is present; unattended mode requires a
mandatory ``--max-samples`` (absent -> HALT, never sample unbounded).

Plan: ``docs/plans/2026-07-12-spend-observability-plan.md`` (KTD6-9). Issue: #402.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

sys.path.insert(0, str(Path(__file__).resolve().parent))

import evidence_ledger  # noqa: E402
import execution_spec  # noqa: E402

Tier = execution_spec.Tier
Verdict = Literal["sufficient", "insufficient"]

# Committed, per-repo (sibling of tier-defaults.json / spend-authority.json under .saga/).
AUTHORITY_PATH = Path(".saga/shadow-audit.json")


class ShadowAuditError(ValueError):
    """Raised for a malformed shadow-audit input (never for a legitimate 'disabled' gate)."""


@dataclass(frozen=True)
class SampledUnit:
    unit_id: str
    stage: str
    tier: Tier
    reviewed_sha: str = ""


# ---------------------------------------------------------------------------
# Sampling (1-in-N, deterministic given a seed)
# ---------------------------------------------------------------------------


def eligible_for_sampling(units: list[SampledUnit]) -> list[SampledUnit]:
    """Units with a runnable one-rung-down tier (a unit already cheapest is excluded, never crashes)."""
    out: list[SampledUnit] = []
    for u in units:
        try:
            execution_spec.adjacent_tier(u.tier, "cheaper")
        except execution_spec.SpecError:
            continue
        out.append(u)
    return out


def sample(units: list[SampledUnit], n: int, seed: int = 0) -> list[SampledUnit]:
    """Deterministically sample ~1-in-``n`` eligible units, given ``seed`` (reproducible)."""
    if n < 1:
        raise ShadowAuditError(f"n must be >= 1, got {n}")
    pool = eligible_for_sampling(units)
    if not pool:
        return []
    k = max(1, len(pool) // n)
    shuffled = list(pool)
    random.Random(seed).shuffle(shuffled)  # nosec B311 — deterministic sampling, not crypto/security
    return shuffled[:k]


# ---------------------------------------------------------------------------
# Gating (R8/KTD9)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GateResult:
    allowed: bool
    reason: str


def _load_authority(root: Path | None = None) -> dict[str, Any]:
    path = (root or Path.cwd()) / AUTHORITY_PATH
    if not path.exists():
        return {"enabled": False}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ShadowAuditError(f"{path}: not valid JSON ({exc})") from exc
    if not isinstance(data, dict):
        raise ShadowAuditError(f"{path}: top level must be an object")
    return data


def gate(
    *, unattended: bool, yes: bool = False, max_samples: int | None = None, root: Path | None = None
) -> GateResult:
    """Resolve whether sampling may proceed at all (R8) -- never a silent default."""
    if unattended:
        if max_samples is None:
            raise ShadowAuditError(
                "unattended mode requires --max-samples (a mandatory bounded cap) -- "
                "HALT, never sample unbounded"
            )
        if max_samples < 1:
            raise ShadowAuditError(f"--max-samples must be >= 1, got {max_samples}")
        return GateResult(allowed=True, reason=f"unattended, budget-capped at {max_samples}")
    if yes:
        return GateResult(allowed=True, reason="explicit --yes for this invocation")
    authority = _load_authority(root)
    if authority.get("enabled") is True:
        return GateResult(allowed=True, reason=".saga/shadow-audit.json enabled=true")
    return GateResult(
        allowed=False,
        reason=(
            "disabled (attended-mode default; pass --yes for this run, or set "
            "'.saga/shadow-audit.json' {\"enabled\": true} as a standing default)"
        ),
    )


def sample_gated(
    units: list[SampledUnit],
    n: int,
    *,
    unattended: bool = False,
    yes: bool = False,
    max_samples: int | None = None,
    seed: int = 0,
    root: Path | None = None,
) -> tuple[list[SampledUnit], GateResult]:
    """The gate-then-sample entry point: returns ``([], disabled-GateResult)`` when gated off."""
    g = gate(unattended=unattended, yes=yes, max_samples=max_samples, root=root)
    if not g.allowed:
        return [], g
    picked = sample(units, n, seed=seed)
    if unattended and max_samples is not None:
        picked = picked[:max_samples]
    return picked, g


# ---------------------------------------------------------------------------
# Sufficiency classification (KTD6 -- built-in exact-match, or an accepted external verdict)
# ---------------------------------------------------------------------------


def classify(original: str, replayed: str) -> Verdict:
    """Whitespace-normalized exact-match classifier for simple diffable text/JSON outputs.

    A strict, conservative default -- no fuzzy-similarity threshold, since an unvalidated
    similarity score is exactly the false-precision this issue's ordinal-only discipline forbids
    elsewhere. Any output ``classify()``'s exact-match is too strict for is a judgment call the
    invoking flow makes itself and passes straight to ``record`` -- this function is never the
    only path to a verdict.
    """

    def _norm(text: str) -> str:
        return " ".join(text.split())

    return "sufficient" if _norm(original) == _norm(replayed) else "insufficient"


# ---------------------------------------------------------------------------
# Ledger write (KTD7 -- reuses evidence_ledger.py via a namespaced check_id)
# ---------------------------------------------------------------------------


def check_id_for(stage: str, unit_id: str) -> str:
    return f"shadow-audit:{stage}:{unit_id}"


def record(
    store: evidence_ledger.Store,
    *,
    stage: str,
    unit_id: str,
    reviewed_sha: str,
    verdict: Verdict,
    original_tier: Tier,
    replayed_tier: Tier,
    notes: str = "",
) -> evidence_ledger.WriteResult:
    """Record one shadow-audit verdict into the evidence ledger (#398), namespaced by stage/unit.

    Reuses ``evidence_ledger.write`` verbatim -- no new ledger file format. The verdict itself is
    ALWAYS caller-supplied (from ``classify()`` or the invoking flow's own judgment); this
    function only accounts, per KTD6.
    """
    payload = {
        "original_tier": original_tier.to_dict(),
        "replayed_tier": replayed_tier.to_dict(),
        "notes": notes,
    }
    content = json.dumps(payload, indent=2, sort_keys=True)
    return evidence_ledger.write(
        store,
        check_id=check_id_for(stage, unit_id),
        reviewed_sha=reviewed_sha,
        producer="shadow-audit",
        verdict=verdict,
        content=content,
        payload=payload,
    )


# ---------------------------------------------------------------------------
# Report (per-stage tier-sufficiency rates)
# ---------------------------------------------------------------------------


def report(root: Path) -> dict[str, dict[str, int]]:
    """Per-stage sufficient/insufficient tally, scanning every ``docs/evidence/*/ledger.jsonl``.

    Read-only -- mirrors the existing ``override_rate_reader.py``/``gate_divergence_reader.py``/
    ``manifest_reader.py`` house pattern (scan-a-tree, aggregate, zero-data-honest).
    """
    tallies: dict[str, dict[str, int]] = {}
    for ledger_path in sorted(root.glob("docs/evidence/*/ledger.jsonl")):
        text = ledger_path.read_text(encoding="utf-8")
        for line in text.splitlines():
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("kind") != "evidence":
                continue
            check_id = str(entry.get("check_id", ""))
            if not check_id.startswith("shadow-audit:"):
                continue
            parts = check_id.split(":", 2)
            if len(parts) < 2:
                continue
            stage = parts[1]
            verdict = entry.get("verdict")
            bucket = tallies.setdefault(stage, {"sufficient": 0, "insufficient": 0})
            if verdict in bucket:
                bucket[verdict] += 1
    return tallies


def render_report(tallies: dict[str, dict[str, int]]) -> str:
    if not tallies:
        return "no data yet — no shadow-audit evidence recorded."
    lines = ["| Stage | Sufficient | Insufficient | Rate |", "|---|---:|---:|---:|"]
    for stage in sorted(tallies):
        counts = tallies[stage]
        total = counts["sufficient"] + counts["insufficient"]
        rate = (counts["sufficient"] / total) if total else 0.0
        lines.append(
            f"| {stage} | {counts['sufficient']} | {counts['insufficient']} | {rate:.0%} |"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _sampled_unit_from_dict(data: dict) -> SampledUnit:
    """Validate one `--units` JSON list element before constructing a `SampledUnit`.

    Raises `ShadowAuditError` (already in `main`'s except tuple) on malformed shape instead of
    letting a raw `TypeError`/`KeyError` escape to an uncaught traceback (#402 code-review finding).
    """
    if not isinstance(data, dict):
        raise ShadowAuditError(f"expected a SampledUnit object, got {type(data).__name__}")
    tier_raw = data.get("tier")
    if not isinstance(tier_raw, dict):
        raise ShadowAuditError(f"expected 'tier' to be an object, got {type(tier_raw).__name__}")
    try:
        return SampledUnit(
            unit_id=str(data["unit_id"]),
            stage=str(data["stage"]),
            tier=Tier(model=str(tier_raw["model"]), effort=str(tier_raw["effort"])),
            reviewed_sha=str(data.get("reviewed_sha", "")),
        )
    except (TypeError, ValueError) as exc:
        raise ShadowAuditError(f"malformed SampledUnit entry: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sampled shadow-audit: replay-one-rung-down tier-sufficiency evidence (#402 U5)."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sample = sub.add_parser("sample", help="gate-then-sample 1-in-N eligible completed units")
    p_sample.add_argument(
        "--units", type=Path, required=True, help="a JSON list of SampledUnit dicts"
    )
    p_sample.add_argument("--n", type=int, required=True)
    p_sample.add_argument("--seed", type=int, default=0)
    p_sample.add_argument("--unattended", action="store_true")
    p_sample.add_argument("--yes", action="store_true")
    p_sample.add_argument("--max-samples", type=int, default=None)
    p_sample.add_argument(
        "--root", type=Path, default=Path("."), help="repo root for the gate config (default: cwd)"
    )

    p_tier_down = sub.add_parser("tier-down", help="report the one-rung-cheaper tier")
    p_tier_down.add_argument("--model", required=True)
    p_tier_down.add_argument("--effort", required=True)

    p_record = sub.add_parser(
        "record", help="record a shadow-audit verdict into the evidence ledger"
    )
    p_record.add_argument("--repo-root", type=Path, default=Path("."))
    p_record.add_argument("--saga-id", required=True)
    p_record.add_argument("--stage", required=True)
    p_record.add_argument("--unit-id", required=True)
    p_record.add_argument("--reviewed-sha", required=True)
    p_record.add_argument("--verdict", required=True, choices=["sufficient", "insufficient"])
    p_record.add_argument("--original-model", required=True)
    p_record.add_argument("--original-effort", required=True)
    p_record.add_argument("--replayed-model", required=True)
    p_record.add_argument("--replayed-effort", required=True)
    p_record.add_argument("--notes", default="")

    p_report = sub.add_parser("report", help="print per-stage tier-sufficiency rates")
    p_report.add_argument("--root", type=Path, default=Path("."))

    args = parser.parse_args(argv)
    try:
        if args.cmd == "sample":
            raw = json.loads(args.units.read_text(encoding="utf-8"))
            if not isinstance(raw, list):
                raise ShadowAuditError(
                    f"expected a JSON list of SampledUnit objects, got {type(raw).__name__}"
                )
            units = [_sampled_unit_from_dict(u) for u in raw]
            picked, gate_result = sample_gated(
                units,
                args.n,
                unattended=args.unattended,
                yes=args.yes,
                max_samples=args.max_samples,
                seed=args.seed,
                root=args.root,
            )
            print(
                json.dumps(
                    {
                        "allowed": gate_result.allowed,
                        "reason": gate_result.reason,
                        "sampled": [u.unit_id for u in picked],
                    },
                    indent=2,
                )
            )
            return 0
        if args.cmd == "tier-down":
            tier = Tier(model=args.model, effort=args.effort)
            down = execution_spec.adjacent_tier(tier, "cheaper")
            print(json.dumps(down.to_dict()))
            return 0
        if args.cmd == "record":
            store = evidence_ledger.Store.for_saga(args.saga_id, args.repo_root).ensure()
            result = record(
                store,
                stage=args.stage,
                unit_id=args.unit_id,
                reviewed_sha=args.reviewed_sha,
                verdict=args.verdict,
                original_tier=Tier(model=args.original_model, effort=args.original_effort),
                replayed_tier=Tier(model=args.replayed_model, effort=args.replayed_effort),
                notes=args.notes,
            )
            print(
                json.dumps(
                    {"content_hash": result.content_hash, "attempt": result.attempt}, indent=2
                )
            )
            return 0
        if args.cmd == "report":
            tallies = report(args.root)
            print(render_report(tallies))
            return 0
    except (execution_spec.SpecError, evidence_ledger.EvidenceLedgerError, ShadowAuditError) as exc:
        print(f"SHADOW AUDIT ERROR: {exc}", file=sys.stderr)
        return 2

    parser.error(f"unknown command {args.cmd!r}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
