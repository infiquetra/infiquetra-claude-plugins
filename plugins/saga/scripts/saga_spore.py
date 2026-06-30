#!/usr/bin/env python3
"""Saga spore: the structured re-grounding cache for the mid-run compaction boundary (issue #281).

When a long ``/work`` / ``/loop`` / ``/outcome`` session fills the context window the harness
**auto-compacts** — it replaces the conversation with a prose summary and the *same* session keeps
running. The structured saga facts the run depends on (the OutcomeOrchestrator ready frontier, open
leaf ids, per-leaf state, the active saga's phase / ``next_step``) get blurred into that prose or
dropped. The **spore** guards exactly that boundary: a ``PreCompact`` hook freezes those facts here at
the boundary, and a ``SessionStart(source=compact)`` hook re-injects them so the continuing session
re-grounds on facts, not prose.

This module is the pure, offline-testable core — the two hooks (``precompact_spore_hook`` /
``compact_spore_session_hook``) are thin shells over it:

* :func:`build_spore` freezes the active saga box + the DAG (via :func:`outcome.status`, derived-on-read
  at the instant of the call — KTD3/KTD4) into a structured dict.
* :func:`serialize` renders that dict into the self-describing ``additionalContext`` block, applying the
  deterministic R5 byte budget with the **ready frontier never dropped**.
* :func:`dump` / :func:`load_and_validate` are the on-disk write / read seam (session-keyed JSON under
  ``<git-common-dir>/saga-spores/``, with the R9 ``saga_id`` + repo-root mismatch guard).

House pattern (mirrors ``outcome_store.py`` / ``saga.py``): pure-ish functions over explicit values, a
dependency-injected ``now``, a ``sys.path`` shim to import the sibling modules, and **no I/O at import**.
The spore is the *anchor, not the authority* (R11) — it AUGMENTS the post-compaction window beside the
harness summary; committed docs + GitHub stay authoritative on conflict about durable state.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# Import the sibling scripts by path so the spore reuses the single source of truth for the DAG
# (``outcome``), the git-common-dir cache mechanics (``outcome_store``), and the saga envelope
# (``saga``) rather than re-deriving any of them. Mirrors the shim ``outcome_store`` itself uses.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import outcome  # noqa: E402  (after the sys.path shim, by design)
import outcome_store  # noqa: E402
import saga  # noqa: E402

SCHEMA = "saga.spore.v1"

# The subdirectory under the git common dir that holds every session's spore. Namespaced beside
# ``outcome_store``'s ``saga-outcomes`` so it is shared by every worktree but never committed (R6/KD3).
SPORE_NAMESPACE = "saga-spores"

# Byte budget for the *rendered block* (KTD2). The harness SessionStart ``additionalContext`` cap is
# 10,000 chars and spills to a file beyond it (GC1) — so this ~9k budget keeps the resumable core in the
# immediately-visible preview rather than behind a file read, while leaving headroom under the cap.
SPORE_BUDGET_CHARS = 9000

# The leading authority instruction (R10/KD6): structured facts win on *durable* conflict, but newer
# in-flight work in the prose summary is real — reconcile, do not regress.
_AUTHORITY = (
    "The preceding prose summary is lossy. The structured facts below are AUTHORITATIVE for durable "
    "state on conflict (open leaves, the ready frontier, the saga's phase/next_step) — but reconcile "
    "any newer in-flight progress from the summary; do not regress to this snapshot's floor."
)


# ---------------------------------------------------------------------------
# Path
# ---------------------------------------------------------------------------


def spore_path(common_dir: Path, session_id: str) -> Path:
    """``<common-dir>/saga-spores/<session_id>.json`` — session-keyed, worktree-stable (R6/R9).

    Reuses ``outcome_store._safe_name`` so a hostile ``session_id`` cannot escape the directory.
    """
    safe = outcome_store._safe_name(session_id, what="session_id")
    return Path(common_dir) / SPORE_NAMESPACE / f"{safe}.json"


# ---------------------------------------------------------------------------
# Resolve the active saga (R2) + its outcome (R3/KTD4)
# ---------------------------------------------------------------------------


def resolve_active_saga(repo_root: Path) -> dict[str, Any] | None:
    """The active saga's box + pointer fields, or None when absent/malformed (never raises).

    ``state.json:active_saga_id`` (``saga.py`` per-worktree last-write) names *which* saga; ``saga.restore``
    cold-reconstructs it from its latest tick (no git/subprocess), giving the five index-resident R2
    fields PLUS ``blockers`` / ``open_questions`` (the C1 fields the ``state.json`` summary omits) and the
    R4 pointers in one read. ``checks_run`` is intentionally absent — it is persisted nowhere, so it
    cannot be carried (C1).
    """
    repo_root = Path(repo_root)
    state_path = repo_root / saga.STATE_DIR / "state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(state, dict):
        return None
    active_id = state.get("active_saga_id")
    if not isinstance(active_id, str) or not active_id:
        return None
    try:
        restored = saga.restore(repo_root, active_id)
    except Exception:  # noqa: BLE001 — the spore never raises into a hook; absence is data
        return None
    if restored is None:
        return None
    box: dict[str, Any] = {
        "saga_id": restored.saga_id,
        "lifecycle_phase": restored.lifecycle_phase,
        "phase_status": restored.phase_status,
        "status": restored.status,
        "next_step": restored.next_step,
    }
    blockers = (getattr(restored, "blockers", "") or "").strip()
    if blockers:
        box["blockers"] = blockers
    open_qs = [str(q) for q in (getattr(restored, "open_questions", None) or [])]
    if open_qs:
        box["open_questions"] = open_qs
    # R4 pointers (paths/refs, never contents) — authority stays in committed docs + GitHub.
    box["_pointers"] = {
        "plan_path": getattr(restored, "plan_path", "") or "",
        "issue_ref": getattr(restored, "issue_ref", "") or "",
        "work_session_paths": [
            str(p) for p in (getattr(restored, "work_session_paths", None) or [])
        ],
    }
    return box


def _store_mtime(common_dir: Path, outcome_id: str) -> float:
    """Newest-activity mtime for an outcome store: its ``ledger.jsonl`` if present, else the dir."""
    root = Path(common_dir) / outcome_store.STORE_NAMESPACE / outcome_id
    ledger = root / "ledger.jsonl"
    try:
        return ledger.stat().st_mtime
    except OSError:
        try:
            return root.stat().st_mtime
        except OSError:
            return 0.0


def _outcome_is_complete(repo_root: Path, outcome_id: str) -> bool | None:
    """``outcome.status(...).complete`` for one outcome, or None when it cannot be determined."""
    try:
        return bool(outcome.status(Path(repo_root), outcome_id)["complete"])
    except Exception:  # noqa: BLE001 — a partial/corrupt store is "unknown", not fatal
        return None


def resolve_outcome_id(
    active_saga_id: str | None, common_dir: Path, *, repo_root: Path
) -> str | None:
    """Resolve which OutcomeOrchestrator (if any) the session is attending (KTD4 — no new saga field).

    Order (deadline-bounded by the calling hook, KTD7):

    1. **leaf-id fast-path (authoritative).** A leaf saga id is ``leaf-<outcome_id>-<subplot_id>``
       (``outcome_dispatcher``). Because both halves may contain hyphens, the split is resolved by
       disk: the existing ``saga-outcomes/<dir>`` whose name is the longest prefix of the stripped id
       is the outcome. This covers the dominant campaign case (the session attends a leaf).
    2. **bounded best-effort scan.** Otherwise scan ``saga-outcomes/`` newest-first by ledger mtime and
       return the single **non-complete** store. With **two or more** non-complete stores and no leaf id
       the frontier is ambiguous (a paused campaign + a hotfix) → return None (the DAG is omitted and the
       ambiguity logged by the caller; never inject a guessed frontier).
    3. None when nothing resolves → a single-saga-only spore.
    """
    outcomes_dir = Path(common_dir) / outcome_store.STORE_NAMESPACE
    try:
        existing = sorted(p.name for p in outcomes_dir.iterdir() if p.is_dir())
    except OSError:
        return None
    if not existing:
        return None

    if active_saga_id and active_saga_id.startswith("leaf-"):
        rest = active_saga_id[len("leaf-") :]
        candidates = [oid for oid in existing if rest == oid or rest.startswith(oid + "-")]
        if candidates:
            return max(candidates, key=len)

    # Scan newest-first; collect non-complete. Stop once a second non-complete proves ambiguity.
    non_complete: list[str] = []
    for oid in sorted(existing, key=lambda o: _store_mtime(common_dir, o), reverse=True):
        if _outcome_is_complete(repo_root, oid) is False:
            non_complete.append(oid)
            if len(non_complete) >= 2:
                return None  # ambiguous frontier — never guess
    if len(non_complete) == 1:
        return non_complete[0]
    return None


def freeze_dag(repo_root: Path, outcome_id: str | None) -> dict[str, Any] | None:
    """Freeze the DAG box from :func:`outcome.status` at this instant (KTD3), or None on any failure.

    ``status`` is the single source of truth — derived-on-read with the U8 cross-surface fix baked in
    (a negative-terminal leaf is never re-listed as dispatchable). Per-leaf ``gated`` comes from the spec
    node and ``last_completion_event_ref`` from the latest completion event; both are best-effort
    enrichments that never break the freeze.
    """
    if not outcome_id:
        return None
    repo_root = Path(repo_root)
    try:
        spec = outcome.load_spec(repo_root, outcome_id)
        store = outcome._store(repo_root, outcome_id)
        st = outcome.status(repo_root, outcome_id, spec=spec, store=store)
    except Exception:  # noqa: BLE001 — a corrupt/partial store degrades to single-saga-only (R12)
        return None

    gated_map: dict[str, bool] = {}
    try:
        gated_map = {n.subplot_id: bool(getattr(n, "gated", False)) for n in spec.nodes}
    except Exception:  # noqa: BLE001
        gated_map = {}

    states: dict[str, str] = st.get("states", {})
    leaves: dict[str, dict[str, Any]] = {}
    for sid, state in states.items():
        ref: str | None = None
        try:
            events = outcome_store.read_completion_events(store, sid)
            if events:
                last = events[-1]
                ref = f"attempt:{getattr(last, 'attempt', '?')}:{getattr(last, 'state', '?')}"
        except Exception:  # noqa: BLE001 — event read is enrichment only
            ref = None
        leaves[sid] = {
            "state": state,
            "gated": gated_map.get(sid, False),
            "last_completion_event_ref": ref,
        }
    return {
        "outcome_id": st.get("outcome_id", outcome_id),
        "objective": st.get("objective", ""),
        "spec_revision": st.get("spec_revision"),
        "counts": st.get("counts", {}),
        "frontier": list(st.get("frontier", [])),
        "complete": st.get("complete"),
        "leaves": leaves,
    }


# ---------------------------------------------------------------------------
# Build + serialize (R1/R3/R5/R10)
# ---------------------------------------------------------------------------


def build_spore(repo_root: Path, session_id: str, *, now: str) -> dict[str, Any]:
    """Assemble the structured spore: ``{provenance, saga_box, dag, pointers}`` (``dag`` None for the

    single-saga case). ``now`` is an ISO timestamp injected by the caller (the hook passes
    ``datetime.now(UTC).isoformat()``; tests pass a fixed string) so the module stays wall-clock-free.
    """
    repo_root = Path(repo_root)
    box = resolve_active_saga(repo_root)
    common = outcome_store.resolve_common_dir(
        repo_root
    )  # raises OutcomeStoreError if git is absent

    active_id = box["saga_id"] if box else None
    pointers = box.pop("_pointers", {}) if box else {}
    outcome_id = resolve_outcome_id(active_id, common, repo_root=repo_root) if active_id else None
    dag = freeze_dag(repo_root, outcome_id)

    source_tick = saga.latest_envelope_for(repo_root, active_id) if active_id else None
    provenance = {
        "schema": SCHEMA,
        "generated_at": now,
        "session_id": session_id,
        "repo_root": str(repo_root),
        "saga_id": active_id,
        "spec_revision": dag.get("spec_revision") if dag else None,
        "source_tick": _repo_relative(source_tick, repo_root),
    }
    if dag:
        pointers = {
            **pointers,
            "outcome_id": dag["outcome_id"],
            "outcome_objective": dag["objective"],
        }
    return {"provenance": provenance, "saga_box": box, "dag": dag, "pointers": pointers}


def _repo_relative(path: Path | None, repo_root: Path) -> str:
    if path is None:
        return ""
    try:
        return str(Path(path).resolve().relative_to(Path(repo_root).resolve()))
    except (ValueError, OSError):
        return str(path)


def _leaf_priority(state: str) -> int:
    """R5 drop order: ready leaves are the resumable core (never dropped); ``done`` leaves go first.

    Lower rank = kept longer. ready < dispatched/other non-terminal < negative-terminal < done.
    """
    if state == "ready":
        return 0
    if state in ("dispatched", "blocked"):
        return 1
    if state == "done":
        return 3
    return 2  # failed / rejected / stalled and any other non-ready terminal


def serialize(spore: dict[str, Any]) -> str:
    """Render the self-describing ``additionalContext`` block (R10) under the R5 byte budget.

    Ordering guarantees: the **resumable core** — authority + provenance + saga box + the full ready
    frontier — is emitted first and **never dropped**; per-leaf detail lines are appended in
    :func:`_leaf_priority` order and trimmed from the end (``done`` first, then waiting/terminal) with a
    counted ``(+K more …)`` pointer when over budget. If even the core exceeds budget it is emitted in
    full anyway (the F3 degenerate case — accept the harness spill-to-file rather than truncate the
    frontier), with the spill noted. Truncation is always logged in-band, never silent (no-silent-caps).
    """
    prov = spore.get("provenance", {})
    box = spore.get("saga_box")
    dag = spore.get("dag")
    pointers = spore.get("pointers", {})

    head: list[str] = ["=== SAGA SPORE (structured re-grounding after compaction) ==="]
    head.append(f"AUTHORITY: {_AUTHORITY}")
    head.append("")
    head.append(
        "Provenance: generated_at={generated_at} · saga_id={saga_id} · spec_revision={spec_revision}".format(
            generated_at=prov.get("generated_at", "?"),
            saga_id=prov.get("saga_id") or "(none)",
            spec_revision=prov.get("spec_revision")
            if prov.get("spec_revision") is not None
            else "-",
        )
    )
    refs = []
    if pointers.get("plan_path"):
        refs.append(f"plan={pointers['plan_path']}")
    if pointers.get("issue_ref"):
        refs.append(f"issue={pointers['issue_ref']}")
    if prov.get("source_tick"):
        refs.append(f"source_tick={prov['source_tick']}")
    if pointers.get("outcome_id"):
        refs.append(f"outcome={pointers['outcome_id']}")
    if refs:
        head.append("Canonical refs: " + " · ".join(refs))

    if box:
        head.append("")
        head.append("ACTIVE SAGA")
        head.append(f"  saga_id: {box.get('saga_id')}")
        head.append(
            f"  phase: {box.get('lifecycle_phase')} ({box.get('phase_status')}) · status: {box.get('status')}"
        )
        head.append(f"  next_step: {box.get('next_step')}")
        if box.get("blockers"):
            head.append(f"  blockers: {box['blockers']}")
        if box.get("open_questions"):
            head.append("  open_questions: " + "; ".join(box["open_questions"]))
    else:
        head.append("")
        head.append("ACTIVE SAGA: (none resolved at the boundary)")

    # The ready frontier is part of the resumable core — always inline, never dropped.
    frontier_block: list[str] = []
    leaf_lines: list[str] = []
    spec_ref = pointers.get("outcome_id") or "the outcome spec"
    if dag:
        counts = dag.get("counts", {})
        counts_str = " ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "(none)"
        frontier = list(dag.get("frontier", []))
        frontier_block.append("")
        frontier_block.append("OUTCOME DAG (frozen at the compaction boundary)")
        frontier_block.append(
            f"  outcome: {dag.get('outcome_id')} · spec_revision: {dag.get('spec_revision')} · counts: {counts_str}"
        )
        frontier_block.append(
            "  READY FRONTIER (act on these): " + (", ".join(frontier) if frontier else "(empty)")
        )
        leaves = dag.get("leaves", {})
        ordered = sorted(
            leaves.items(),
            key=lambda kv: (_leaf_priority(kv[1].get("state", "")), kv[0]),
        )
        for sid, info in ordered:
            flag = " [gated]" if info.get("gated") else ""
            ref = info.get("last_completion_event_ref")
            ref_str = f" (last={ref})" if ref else ""
            leaf_lines.append(f"    {sid}: {info.get('state')}{flag}{ref_str}")

    # Assemble with the budget: head + frontier_block are the never-dropped core; leaf_lines trim.
    core = "\n".join(head + frontier_block)
    if not leaf_lines:
        tail = "\n=== END SPORE ==="
        out = core + tail
        return out

    leaf_header = "\n  Leaves:"
    fixed = core + leaf_header
    end = "\n=== END SPORE ==="
    # Greedily keep leaf lines while the whole block stays under budget, reserving room for a pointer.
    kept: list[str] = []
    dropped = 0
    pointer_tmpl = "\n    (+{k} more leaves — see {spec})"
    for i, line in enumerate(leaf_lines):
        remaining = len(leaf_lines) - i
        candidate = fixed + "\n" + "\n".join(kept + [line])
        pointer = pointer_tmpl.format(k=remaining - 1, spec=spec_ref) if remaining - 1 > 0 else ""
        if len(candidate + pointer + end) <= SPORE_BUDGET_CHARS:
            kept.append(line)
        else:
            dropped = len(leaf_lines) - len(kept)
            break

    body = fixed + ("\n" + "\n".join(kept) if kept else "")
    if dropped:
        body += pointer_tmpl.format(k=dropped, spec=spec_ref)
    out = body + end

    # F3 degenerate case: even the resumable core overflowed. Emit it in full anyway (the frontier is
    # never sacrificed); the harness spills to a file (GC1). Log the spill in-band, never silently.
    if len(out) > SPORE_BUDGET_CHARS and not kept:
        out += f"\n[spore note: resumable core exceeds {SPORE_BUDGET_CHARS} chars; emitted in full — harness spills to file]"
    return out


# ---------------------------------------------------------------------------
# On-disk seam: dump (write) / load_and_validate (read) — R8/R9/R13
# ---------------------------------------------------------------------------


def dump(spore: dict[str, Any]) -> str:
    """The on-disk JSON the PreCompact hook writes: validation fields + the pre-rendered block.

    The rendering (and the R5 budget) runs once here at PreCompact time — under the hook's wall-clock
    deadline — so the SessionStart read is a trivial validate-and-return and the block reflects the
    state *frozen at the boundary*.
    """
    prov = spore.get("provenance", {})
    payload = {
        "schema": SCHEMA,
        "session_id": prov.get("session_id"),
        "repo_root": prov.get("repo_root"),
        "saga_id": prov.get("saga_id"),
        "generated_at": prov.get("generated_at"),
        "block": serialize(spore),
    }
    return json.dumps(payload, indent=2)


def load_and_validate(text: str, expected_session_id: str, expected_repo_root: str) -> str | None:
    """Parse the on-disk spore and return its renderable block, or None on mismatch/corruption (R9).

    The filename already keys the spore to ``<session_id>``; this re-checks ``session_id`` and the
    ``repo_root`` from the payload (defense in depth) and requires a ``saga_id`` so a content mismatch is
    skipped rather than injected. Never raises — a malformed spore is treated as absent.
    """
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("schema") != SCHEMA:
        return None
    if payload.get("session_id") != expected_session_id:
        return None
    if str(payload.get("repo_root")) != str(expected_repo_root):
        return None
    if not payload.get("saga_id"):
        return None
    block = payload.get("block")
    if not isinstance(block, str) or not block:
        return None
    return block
