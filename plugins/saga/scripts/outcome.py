#!/usr/bin/env python3
"""OutcomeOrchestrator reconcile engine + thin ``/outcome`` CLI (U3).

This is the coordinator runtime that sits on top of the spec (U1, structure) and the store (U2,
cache + completion + locks). It is a **level-triggered reconcile loop** (R29), not a long-lived
imperative process: every ``advance`` tick reconstructs live state from the durable store, advances
the ready frontier, **dispatches** non-gated leaves to their executors, and pages on exceptions —
holding no authoritative in-memory DAG, so it is crash-tolerant and host-agnostic (a local ``/loop``
session or a scheduled routine drives the repeats).

Two invariants this module enforces structurally:

* **The coordinator routes, it never executes** (R2/R3). ``advance`` only *dispatches* (hands a leaf
  off to a backend via an injected ``dispatcher`` and records it) and *harvests* (reads completion
  events). It never runs a leaf's work in the advance process — so a coordinator failure can never
  collapse the whole DAG into one inline context. The default dispatcher is record-only; real
  backends (team-execution, workflows, ``/goal``, …) arrive in U4/U9 as dispatcher implementations.
* **Status is derived on read** (R17/R29). There is no operator-writable status field. A node's live
  state is *computed* every call from the committed spec + completion events + dispatch records —
  never read from a stored scalar — so the cockpit physically cannot drift.

The ``/outcome`` surface is deliberately thin (KTD11, R16): ``start``, ``graph``, ``advance``,
``attend``, ``resume``, ``export``, ``import``, ``status``. Leaf work stays the native ``/resume
<leaf-saga-id>`` / ``/work`` / ``/code-review`` / ``/qa`` — there is no ``/outcome work``; ``attend``
just prints the native re-entry handoff (R16 altitude seam).

House pattern (mirrors ``outcome_spec`` / ``outcome_store`` / ``saga``): pure-ish functions over
explicit values, dependency-injected ``dispatcher`` / ``now`` / ``runner`` so the loop is unit-testable
offline with no real git repo, no backend, and no wall clock; no I/O at import.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

# Make sibling scripts importable when loaded by path (tests, CLI).
sys.path.insert(0, str(Path(__file__).resolve().parent))

# The backend dispatcher module owns the HALT contract (it is never run as ``__main__``, so there is
# exactly one ``BackendHaltError`` class regardless of how the engine is launched). The reconcile loop
# catches ``outcome_dispatcher.BackendHaltError`` per leaf. outcome_dispatcher does NOT import this
# module (it duck-types the request), so there is no import cycle.
import adjustment_envelope  # noqa: E402  (the #372 mid-run control surface, polled per tick)
import dispatch_settlement  # noqa: E402  (#351 shared fan-out accounting contract)
import intent_envelope  # noqa: E402  (the canonical #380 envelope schema, via the fleet shim)
import outcome_dispatcher  # noqa: E402
import outcome_intent  # noqa: E402  (the #433 posture-renegotiation engine; no import cycle)
import outcome_spec  # noqa: E402  (after the sys.path shim, by design)
import outcome_store  # noqa: E402
import run_ledger  # noqa: E402  (#351 canonical hash-chained run-fact store)

# Where the canonical spec lives on the outcome's own branch (KTD1/R26). The committed spec is the
# structural source of truth; the store under the git-common-dir is its performance cache.
OUTCOMES_DIR = "docs/outcomes"

# Default coordinator-lease TTL (seconds): a tick that dies without releasing is reclaimable after
# this. The host drives ticks far more often than this, so a healthy loop always refreshes in time.
DEFAULT_LEASE_TTL = 900.0


class OutcomeError(ValueError):
    """An ``/outcome`` operation violated an invariant (bad id, missing spec, etc.)."""


class StaleSpecError(OutcomeError):
    """A save was built on a spec revision another writer has since superseded (#433).

    Raised by :func:`save_spec` when the on-disk ``spec_revision`` no longer matches the
    revision this in-memory spec was loaded at — e.g. a mid-tick ``repost``/``set-intent``
    committed a newer revision while an ``advance`` tick still held the older one in memory.
    The stale write is REFUSED so the newer revision (its posture, its revision bump, its
    decision-trail entry) survives; the caller either surfaces the error loudly or reloads
    the newer spec and re-applies its change on top (the cost processor does the latter).
    """


# A dispatcher hands a ready leaf off to a backend and returns its leaf saga id. It MUST NOT run the
# leaf's work in-process (R3) — it records/launches and returns. The record-only default is the
# skeleton; U4/U9 supply real backend dispatchers with the same signature.
Dispatcher = Callable[["DispatchRequest"], str]


@dataclass(frozen=True)
class DispatchRequest:
    """Everything a backend needs to launch a leaf — passed to the injected dispatcher."""

    outcome_id: str
    subplot_id: str
    title: str
    backend: str
    repo_root: Path
    # The leaf's declared sandbox (#287 U3), so the dispatcher can probe backend enforceability and
    # HALT rather than silently run the leaf uncontained. Absent (None) => ambient x read-write.
    sandbox: outcome_spec.Sandbox | None = None
    # The posture era this dispatch happens under (#433 R4): the spec's intent_revision at the
    # moment of dispatch (1 = the never-renegotiated run-start baseline). The leaf finishes under
    # THIS posture even if a later repost amends the campaign (R5 dispatch-time overlap).
    intent_revision: int = 1
    # Dispatch-settlement identity. Empty identifiers preserve the pre-#351 dispatcher contract;
    # settlement-backed production dispatches supply durable values for crash replay deduplication.
    dispatch_id: str = ""
    attempt: int = 1
    idempotency_key: str = ""


def _default_dispatcher(req: DispatchRequest) -> str:
    """Record-only dispatch: mint a stable leaf saga id, run NOTHING (R3).

    Real execution backends (team-execution, cc-workflows-ultracode, ``/goal``, fork, subagent,
    manual) are dispatcher implementations that arrive in U4/U9. The skeleton just allocates the
    handoff address; the leaf is executed by its own native saga, never here.
    """
    return f"leaf-{req.outcome_id}-{req.subplot_id}"


def _append_ledger_once(store: Any, record: dict[str, Any]) -> bool:
    """Append a ledger record only if no record with the same ``(phase, key)`` already exists.

    The ``commit`` dispatch record is the dedup marker for SUCCESSFUL dispatch, but a HALTed or
    degrade-then-crashed leaf never writes a commit, so it is re-evaluated every tick. Without this, an
    attended leaf polling ``advance`` against a persistently-unavailable backend re-appends a ``halt``
    record on every tick (unbounded ledger growth), and a crash in the degrade->commit window
    double-lists the degradation. Delegates to :func:`outcome_store.append_ledger_once` — the ONE
    (phase, key) append-once implementation, shared with the #433 repost strand-halt writer.
    """
    appended: bool = outcome_store.append_ledger_once(store, record)
    return appended


def _default_holder() -> str:
    """A holder id UNIQUE to this advance invocation (pid + a monotonic nonce).

    The coordinator lease only excludes a *different* holder (same-holder acquire is a refresh). A
    constant holder would therefore let two concurrent / re-entrant advances both "acquire" and
    both dispatch the same leaf (R13 violated). A per-invocation unique id makes a concurrent
    advance a genuinely different holder, so it no-ops on the held lease as intended.
    """
    return f"coordinator-{os.getpid()}-{time.monotonic_ns()}"


# ---------------------------------------------------------------------------
# Spec placement + load/save on the outcome's branch
# ---------------------------------------------------------------------------


def spec_path(repo_root: Path, outcome_id: str) -> Path:
    return Path(repo_root) / OUTCOMES_DIR / _safe(outcome_id) / "outcome-spec.json"


def _safe(outcome_id: str) -> str:
    # Reuse the store's path-traversal guard so ids are validated identically everywhere.
    return outcome_store._safe_name(outcome_id, what="outcome_id")


def load_spec(repo_root: Path, outcome_id: str) -> outcome_spec.OutcomeSpec:
    path = spec_path(repo_root, outcome_id)
    try:
        spec = outcome_spec.OutcomeSpec.from_json(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise OutcomeError(f"no outcome spec at {path} — run `outcome start` first") from exc
    spec.validate()
    # Stamp the revision this instance was loaded at — save_spec's stale-write guard compares
    # it against the on-disk revision so a save built on a superseded load fails loudly (#433).
    spec.loaded_revision = spec.spec_revision
    return spec


def _on_disk_revision(repo_root: Path, outcome_id: str) -> int | None:
    """The ``spec_revision`` currently on disk, or ``None`` when absent/unreadable.

    ``None`` is deliberately never treated as "safe": a reader that cannot verify the on-disk
    revision must fail toward NOT acting on possibly-stale posture (save_spec refuses the
    write; the reconcile loop reloads, which raises loudly on a genuinely broken file).
    """
    try:
        data = json.loads(spec_path(repo_root, outcome_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    revision = data.get("spec_revision") if isinstance(data, dict) else None
    if isinstance(revision, bool) or not isinstance(revision, int):
        return None
    return revision


def save_spec(repo_root: Path, spec: outcome_spec.OutcomeSpec) -> Path:
    """Persist the canonical spec (structure + decision-trail + cost) to the branch path.

    Writes the working-tree file only; the **git commit + push** to the outcome's own branch (the R26/R27
    cross-machine-durability step) is :func:`commit_spec`, run explicitly via ``/outcome commit`` or
    ``/outcome advance --persist`` — never silently per tick. node live-state stays derived-on-read (R17),
    so the branch history is not polluted with state churn.

    **Stale-write guard (#433 overlap safety).** The write is compare-and-swap on the revision
    this spec was loaded at (``spec.loaded_revision``; a spec never loaded from disk compares
    against its own ``spec_revision``): if the on-disk ``spec_revision`` has moved since our
    load — a concurrent ``repost``/``set-intent``/edit committed a newer revision — the save
    raises :class:`StaleSpecError` instead of silently reverting the newer revision's posture,
    revision bump, and decision-trail entry. An unreadable-but-present spec file also refuses
    (fail closed: a write we cannot verify is not a write we may make).

    **Residual window — documented, not claimed away.** The guard is check-then-write with no
    cross-process lock (the repost CLI deliberately takes no coordinator lease): a writer that
    commits between this function's revision read and its ``write_text`` is still silently
    overwritten, and two simultaneous writers can mint the same revision with the second
    erasing the first's trail entry. The gap spans one JSON serialization plus one write
    syscall — the same scale as the strand sub-window recorded in
    ``references/outcome-spec.md`` (§Mid-run posture renegotiation). Closing it would take an
    OS-level lock or lease on every spec save; deliberately not done in this change (blast
    radius).
    """
    spec.validate()
    path = spec_path(repo_root, spec.outcome_id)
    if path.exists():
        on_disk = _on_disk_revision(repo_root, spec.outcome_id)
        expected = spec.loaded_revision or spec.spec_revision
        if on_disk != expected:
            raise StaleSpecError(
                f"refusing to save outcome {spec.outcome_id!r}: the on-disk spec_revision is "
                f"{on_disk!r} but this spec was loaded at revision {expected} — a concurrent "
                f"writer (e.g. a mid-run repost) has superseded it. Reload the spec and "
                f"re-apply the change on top of the newer revision."
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(spec.to_json(), encoding="utf-8")
    # This instance now IS the on-disk revision — later saves of the same object CAS
    # against what was just written.
    spec.loaded_revision = spec.spec_revision
    return path


# The branches the spec must NEVER be committed to mid-run (R26: "the outcome's own branch, not main").
_PROTECTED_BRANCHES = frozenset({"main", "master"})


def _git(
    args: list[str], repo_root: Path, runner: Callable[..., Any] | None = None
) -> tuple[int, str, str]:
    """Run a ``git`` subcommand in ``repo_root``; ``(rc, stdout, stderr)``. ``runner`` injectable (tests)."""
    import subprocess  # nosec B404 — git CLI only, fixed argv, no shell

    run = runner if runner is not None else subprocess.run
    try:
        result = run(  # nosec B603 — fixed argv, no shell
            ["git", *args], cwd=str(repo_root), capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, "", str(exc)
    return (
        getattr(result, "returncode", 1),
        (getattr(result, "stdout", "") or "").strip(),
        (getattr(result, "stderr", "") or "").strip(),
    )


def commit_spec(
    repo_root: Path,
    outcome_id: str,
    *,
    message: str = "",
    push: bool = False,
    runner: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Commit the canonical outcome spec to the **outcome's own branch** (R26/R27 cross-machine durability).

    The spec artifact is canonical for structure + decision-trail + cost (R26); committing + pushing it to
    the outcome's branch is what lets a **different machine reconstruct the whole outcome by pulling the
    repo** (R27/F5) — load the committed spec, then re-harvest completion from GitHub (canonical), no
    dependence on the local cache. This is the **mechanism**; the *cadence* (how often it runs) is the
    operator's / `/loop`'s call (the deferred half of R26).

    **Refuses to commit to ``main``/``master``** (R26: "not main mid-run") so an outcome's structural churn
    never pollutes the default branch. A path-limited commit (only the spec file) leaves the operator's
    other working-tree changes untouched. Idempotent: a no-op when the spec is already committed.
    """
    branch = ""
    rc, out, _ = _git(["rev-parse", "--abbrev-ref", "HEAD"], repo_root, runner)
    if rc == 0:
        branch = out
    if branch in _PROTECTED_BRANCHES:
        raise OutcomeError(
            f"refusing to commit the {outcome_id!r} spec to {branch!r} — R26: the outcome spec lives on "
            f"its own branch (outcome/<slug>), never main mid-run. Switch to the outcome branch first."
        )
    path = spec_path(repo_root, outcome_id)
    rel = str(path)
    _git(["add", "--", rel], repo_root, runner)
    staged_rc, _o, _e = _git(["diff", "--cached", "--quiet", "--", rel], repo_root, runner)
    if staged_rc == 0:  # nothing staged -> the spec is already committed (idempotent no-op)
        return {"committed": False, "branch": branch, "pushed": False, "reason": "spec unchanged"}
    msg = message or f"chore(outcome): persist {outcome_id} spec"
    crc, _o, cerr = _git(["commit", "-m", msg, "--", rel], repo_root, runner)
    if crc != 0:
        raise OutcomeError(f"could not commit the {outcome_id!r} spec: {cerr}")
    pushed = False
    if push:
        prc, _po, _pe = _git(["push"], repo_root, runner)
        pushed = prc == 0
    return {"committed": True, "branch": branch, "pushed": pushed}


# A github pull-request URL — the gh-consumable, cwd-independent form the harvester barrier re-verifies
# (#495 U2). link-pr requires this exact shape so the stored ref is unambiguous across machines.
_PR_URL_RE = re.compile(r"^https?://github\.com/[^/\s]+/[^/\s]+/pull/\d+(?:[/?#].*)?$")


def link_pr(
    repo_root: Path, outcome_id: str, subplot_id: str, pr_url: str, *, push: bool = False
) -> dict[str, Any]:
    """Attach a code leaf's merged PR to its coordinator node — the attended gap-1 producer (#495 U2).

    The record-only dispatch -> native ``/work`` -> squash-merge flow never writes a leaf's merged PR
    back onto the coordinator node, so the ``code:pr-merged`` barrier reads "no PR ref yet" forever
    (``outcome_orchestrator.py:102-103``). This verb writes ``node.github["pr"]`` so the next ``advance``
    harvests the leaf. It is the single missing *producer* both consumers wait on — the harvester barrier
    and the auto-merge queue's ``_is_mergeable_kind``. It attaches a POINTER only: the barrier still
    re-verifies ``merged`` on GitHub, so a wrong or not-yet-merged URL never falsely completes a node.
    Idempotent. With ``push`` it commits the spec to the outcome's own branch (run it on that branch).
    """
    pr = str(pr_url).strip()
    if not _PR_URL_RE.match(pr):
        raise OutcomeError(
            f"link-pr: {pr_url!r} is not a github pull-request URL "
            f"(https://github.com/<owner>/<repo>/pull/<N>)"
        )
    spec = load_spec(repo_root, outcome_id)
    node = spec.node_by_id(subplot_id)
    if node is None:
        raise OutcomeError(f"link-pr: no subplot {subplot_id!r} in outcome {outcome_id!r}")
    if node.kind != "code":
        raise OutcomeError(
            f"link-pr: subplot {subplot_id!r} is kind={node.kind!r}, not 'code' — only a code leaf's "
            f"completion is gated on a merged PR"
        )
    already = str(node.github.get("pr", ""))
    changed = already != pr
    node.github["pr"] = pr
    spec.validate()
    save_spec(repo_root, spec)
    result: dict[str, Any] = {
        "outcome_id": outcome_id,
        "subplot_id": subplot_id,
        "pr": pr,
        "changed": changed,
    }
    if push:
        result["persisted"] = commit_spec(repo_root, outcome_id, push=True)
    return result


def _store(repo_root: Path, outcome_id: str, *, runner: Callable[..., Any] | None = None) -> Any:
    return outcome_store.Store.for_outcome(outcome_id, Path(repo_root), runner=runner).ensure()


# ---------------------------------------------------------------------------
# start / resume
# ---------------------------------------------------------------------------


def start(
    repo_root: Path,
    outcome_id: str,
    objective: str,
    nodes: list[dict[str, Any]] | None = None,
    *,
    intent: dict[str, Any] | None = None,
    runner: Callable[..., Any] | None = None,
) -> outcome_spec.OutcomeSpec:
    """Create the branch-local spec + its store. Idempotent only if no spec exists yet.

    ``nodes`` defaults to a minimal 2-node design->build DAG so the skeleton is usable immediately;
    the real graph is authored/decomposed via U7. Fails if a spec already exists (use ``resume``).
    ``intent`` (#380) is the committed run-start intent envelope — schema-validated by
    ``spec.validate()`` before anything is written, so an invalid envelope never lands on disk.
    """
    path = spec_path(repo_root, outcome_id)
    if path.exists():
        raise OutcomeError(f"outcome {outcome_id!r} already started ({path}); use `resume`")
    node_dicts = nodes if nodes is not None else _starter_nodes()
    payload: dict[str, Any] = {
        "outcome_id": outcome_id,
        "objective": objective,
        "nodes": node_dicts,
    }
    if intent is not None:
        payload["intent"] = intent
    spec = outcome_spec.OutcomeSpec.from_dict(payload)
    spec.validate()
    save_spec(repo_root, spec)
    _store(repo_root, outcome_id, runner=runner)  # materialize the cache tree
    return spec


def set_intent(
    repo_root: Path,
    outcome_id: str,
    intent_file: Path,
    *,
    runner: Callable[..., Any] | None = None,
) -> outcome_spec.OutcomeSpec:
    """Attach a run-start intent envelope to an ALREADY-started outcome (#380).

    The landing place for an interview captured after ``start`` reported
    ``interview_required: true`` — ``start`` is non-idempotent, so the captured envelope needs a
    verb of its own. Validated exactly like ``start --intent-file`` (an invalid file is a loud
    error, never adopted); bumps ``spec_revision`` through ``bump_revision`` (one revision
    counter, one decision-trail entry — re-``approve`` before the next dispatch). Refuses to
    overwrite a committed envelope: mid-run posture renegotiation is #433's contract, not this
    verb's.

    **Live-campaign monotonic validation (#433 AC5).** Attaching a first envelope BEFORE any
    dispatch is run-start posture and may carry any gate values (the #380 interview-fallback
    contract). But once the campaign is LIVE (any dispatch ledger record exists), a first
    attach is the same semantic transition as a repost against the effective (default-gated,
    ``gate``-everywhere) posture — so it passes the SAME monotonic validation: an envelope
    carrying ``merge: "auto"`` or ``deploy_nonprod: "auto"`` is rejected outright
    (``outcome_intent.RepostError``), never accepted through the sibling verb. One rule, both
    verbs.
    """
    spec = load_spec(repo_root, outcome_id)
    if getattr(spec, "intent", None):
        raise OutcomeError(
            f"outcome {outcome_id!r} already carries a committed intent envelope; "
            "mid-run renegotiation is the `repost` verb's contract (#433), not set-intent's"
        )
    resolution = resolve_start_intent(None, intent_file)
    store = _store(repo_root, outcome_id, runner=runner)
    live = outcome_intent.campaign_live(store)
    deltas: tuple[Any, ...] = ()
    if live:
        # AC5: the attach must clear the same monotonic gate a repost would — computed against
        # the effective (default-gated) no-envelope posture. Raises RepostError on a violation,
        # leaving the spec (and the on-disk file) byte-identical.
        deltas = outcome_intent.validate_live_attach(spec, resolution["intent"])
    spec.intent = resolution["intent"]
    # One verb, one revision counter, one trail (#433): the attach is a posture change, so it
    # records a structured decision-trail entry exactly like a repost does — never a bare
    # revision bump with no audit record.
    new_revision = spec.bump_revision(
        reason="set-intent: attach run-start intent envelope"
        + (" to a live campaign" if live else "")
    )
    spec.decision_trail[-1].update(
        {
            "kind": "set-intent",
            "scope": "",
            "live": live,
            "deltas": [d.to_dict() for d in deltas],
            "intent_revision": new_revision,
        }
    )
    # #433 R4: attaching the envelope IS a posture change — tag the revision that introduced
    # it so dispatch records distinguish pre- from post-envelope dispatches.
    spec.intent_revision = new_revision
    spec.validate()
    save_spec(repo_root, spec)
    return spec


def resolve_start_intent(
    parent_body: str | None, intent_file: Path | None = None
) -> dict[str, Any]:
    """Resolve the run-start intent for ``start`` (#380): explicit file, else issue-carried.

    Precedence: an explicit ``--intent-file`` envelope wins (an invalid file is a loud error —
    it is direct operator input); otherwise the parent issue's envelope block decides via
    ``intent_envelope.outcome_start_decision`` — a valid issue envelope skips the run-start
    interview, absent/invalid falls back to asking (surfaced, never silently adopted).
    """
    import intent_envelope  # noqa: PLC0415

    if intent_file is not None:
        try:
            data = json.loads(intent_file.read_text(encoding="utf-8"))
            envelope = intent_envelope.IntentEnvelope.from_dict(data)
        except (OSError, ValueError) as exc:  # IntentEnvelopeError is a ValueError
            raise OutcomeError(f"--intent-file {intent_file}: {exc}") from exc
        return {
            "intent": envelope.to_dict(),
            "intent_source": "file",
            "interview_required": False,
            "interview_reason": f"envelope supplied via --intent-file {intent_file}",
        }
    decision = intent_envelope.outcome_start_decision(parent_body)
    return {
        "intent": decision.envelope.to_dict() if decision.envelope is not None else None,
        "intent_source": "issue" if decision.envelope is not None else None,
        "interview_required": decision.interview_required,
        "interview_reason": decision.reason,
    }


def _starter_nodes() -> list[dict[str, Any]]:
    return [
        {"subplot_id": "design", "title": "Design", "kind": "non-code"},
        {"subplot_id": "build", "title": "Build", "kind": "code", "depends_on": ["design"]},
    ]


def _ingest_state(state: Any, state_reason: Any) -> str:
    """Map a GitHub issue state+reason to an authored ``Node.state`` (#375 KTD2).

    OPEN -> ``pending``; CLOSED+NOT_PLANNED -> ``rejected``; any other CLOSED -> ``done``. This is
    structural authored spec state (permitted), never a committed status field or a completion event.
    """
    if str(state or "").upper() != "CLOSED":
        return "pending"
    return "rejected" if str(state_reason or "").upper() == "NOT_PLANNED" else "done"


def nodes_from_objective(
    owner: str, repo: str, number: int, *, runner: Callable[..., Any] | None = None
) -> tuple[list[dict[str, Any]], list[dict[str, str]], str, str]:
    """Build outcome node dicts from a GitHub Objective's sub-issues (#375 U3).

    Returns ``(nodes, dropped_edges, objective_title, parent_body)``. Each node carries a stable
    ``subplot_id`` derived from the sub-issue identity (repo-qualified only on same-number
    collisions), a ``kind`` from labels (``non-code`` -> ``non-code``, else ``code``), an authored
    ``state`` from the sub-issue's state+reason, a ``github`` provenance stamp the
    reconcile/board-sync consumers read, and ``depends_on`` from the inferred (cycle-safe) edges.
    ``parent_body`` (#380) is the Objective's issue body — the surface an issue-authored intent
    envelope rides in on (``resolve_start_intent`` reads it).
    """
    import discover_subissues  # noqa: PLC0415
    import outcome_edges  # noqa: PLC0415

    data = discover_subissues.fetch_objective(owner, repo, number, runner=runner)
    raw_subissues = data.get("subissues", [])
    subissues = (
        [sub for sub in raw_subissues if isinstance(sub, dict)]
        if isinstance(raw_subissues, list)
        else []
    )
    depends_on_by_subplot, dropped = outcome_edges.edges_from_relationships(subissues)
    subplot_ids = outcome_edges.subplot_ids_for_subissues(subissues)

    repo_full = f"{owner}/{repo}"
    nodes: list[dict[str, Any]] = []
    for sub in subissues:
        n = sub["number"]
        sub_repo = str(sub.get("repo") or repo_full)
        sid = subplot_ids[(str(sub.get("repo") or ""), int(n))]
        labels = [str(x).lower() for x in (sub.get("labels") or [])]
        kind = "non-code" if "non-code" in labels else "code"
        node: dict[str, Any] = {
            "subplot_id": sid,
            "title": sub.get("title") or sid,
            "kind": kind,
            "state": _ingest_state(sub.get("state"), sub.get("state_reason")),
            # Stamp the sub-issue's OWN repository+number so reconcile/board-sync resolve it, never
            # the parent Objective (#375 KTD4/R5, #513).
            "github": {"repo": sub_repo, "issue": f"{sub_repo}#{n}", "sub_issue": n},
        }
        deps = depends_on_by_subplot.get(sid)
        if deps:
            node["depends_on"] = deps
        nodes.append(node)

    parent = data.get("parent")
    objective_title = str(parent.get("title") or "") if isinstance(parent, dict) else ""
    parent_body = str(parent.get("body") or "") if isinstance(parent, dict) else ""
    return nodes, dropped, objective_title, parent_body


def _parse_objective_ref(ref: str) -> tuple[str, str, int]:
    """Parse ``<owner>/<repo>#<N>`` into ``(owner, repo, number)`` (#375 U4)."""
    m = re.fullmatch(r"(?P<owner>[^/]+)/(?P<repo>[^#]+)#(?P<number>\d+)", ref.strip())
    if not m:
        raise OutcomeError(f"--from-objective must be '<owner>/<repo>#<N>', got {ref!r}")
    return m.group("owner"), m.group("repo"), int(m.group("number"))


def resume(
    repo_root: Path, outcome_id: str, *, runner: Callable[..., Any] | None = None
) -> dict[str, Any]:
    """Reconstruct live status from the canonical spec + store — the spec always survives a cache wipe.

    The committed spec (on the branch) is canonical structure, so it always reloads after any cache
    loss. **Completion is a different facet**: in U3 completion events live ONLY in the cache, so a
    cache wipe currently *does* drop completion (a done leaf reverts to the frontier). The full R27
    "rebuild completion from GitHub" leg is U5 (`outcome_github`); until it lands, ``export`` is the
    durable completion checkpoint. ``resume`` recomputes the frontier from whatever completion truth
    survives (R27/R29) — lossless for structure today, lossless for completion once U5 reads GitHub.
    """
    spec = load_spec(repo_root, outcome_id)
    store = _store(repo_root, outcome_id, runner=runner)
    return status(repo_root, outcome_id, spec=spec, store=store)


# ---------------------------------------------------------------------------
# Derived live state (R17 — computed every read, never a stored status field)
# ---------------------------------------------------------------------------

# Live node states the coordinator derives (computed from completion events + dispatch records,
# never persisted). NOTE: ``Node.state`` on the committed spec is the AUTHORING-time declared state
# only — derive_states never reads it; live state comes solely from the store (R17). The negative
# terminals are surfaced (not masked as "dispatched") so the cockpit never shows a dead leaf as
# in-flight; the cascade/handling of those terminals is U6.
LIVE_READY = "ready"
LIVE_DISPATCHED = "dispatched"
LIVE_DONE = "done"
LIVE_BLOCKED = "blocked"


def _dispatch_records(store: Any) -> dict[str, str]:
    """subplot_id -> leaf_saga_id for every SETTLED dispatch (a ``commit`` record in the ledger).

    Keyed on the ``commit`` phase, not ``intent``: a dispatch is recorded intent -> effect -> commit,
    so a leaf whose intent was written but whose dispatch then failed (no commit) is NOT counted as
    dispatched here — it falls back to the frontier and is re-driven, and ``replay_pending`` flags its
    dangling intent. This makes the dedup durable AND a failed dispatch recoverable rather than stuck.
    """
    out: dict[str, str] = {}
    for rec in outcome_store.read_ledger(store):
        if rec.get("kind") == "dispatch" and rec.get("phase") == "commit":
            sid = str(rec.get("subplot_id", ""))
            if sid:
                out[sid] = str(rec.get("leaf_saga_id", ""))
    return out


def _dispatch_commit_records(store: Any) -> dict[str, dict[str, Any]]:
    """Return the latest durable dispatch commit per subplot, including settlement binding."""
    out: dict[str, dict[str, Any]] = {}
    for rec in outcome_store.read_ledger(store):
        if rec.get("kind") == "dispatch" and rec.get("phase") == "commit":
            sid = str(rec.get("subplot_id", ""))
            if sid:
                out[sid] = dict(rec)
    return out


def _terminal_state_map(store: Any) -> dict[str, str]:
    """subplot_id -> its terminal completion state (done/failed/rejected/stalled), latest attempt wins."""
    out: dict[str, str] = {}
    for node_id in outcome_store.completed_subplots(store, successful_only=False):
        events = outcome_store.read_completion_events(store, node_id)
        if events:
            out[node_id] = events[-1].state  # events sorted by attempt; latest is authoritative
    return out


def derive_states(spec: outcome_spec.OutcomeSpec, store: Any) -> dict[str, str]:
    """Compute each node's LIVE state from the spec + store — the load-bearing derived-on-read map.

    Precedence per node: a SUCCESS completion -> ``done``; any other terminal completion ->
    its actual negative terminal (``failed`` / ``rejected`` / ``stalled``) so a dead leaf is never
    mislabeled as in-flight; else a settled dispatch -> ``dispatched``; else in the ready frontier ->
    ``ready``; else ``blocked`` (an upstream is not yet done). No node's state is ever read from a
    stored scalar (R17) — ``Node.state`` on the spec is authoring-time-only and ignored here.
    """
    success = outcome_store.completed_subplots(store, successful_only=True)
    terminals = _terminal_state_map(store)
    dispatched = _dispatch_records(store)
    frontier = set(outcome_spec.ready_frontier(spec, success))
    states: dict[str, str] = {}
    for node in spec.nodes:
        sid = node.subplot_id
        if sid in success:
            states[sid] = LIVE_DONE
        elif sid in terminals:
            states[sid] = terminals[sid]  # negative terminal — surfaced, not masked
        elif sid in dispatched:
            states[sid] = LIVE_DISPATCHED
        elif sid in frontier:
            states[sid] = LIVE_READY
        else:
            states[sid] = LIVE_BLOCKED
    return states


def status(
    repo_root: Path,
    outcome_id: str,
    *,
    spec: outcome_spec.OutcomeSpec | None = None,
    store: Any | None = None,
) -> dict[str, Any]:
    """A computed cockpit snapshot — derived on read, never from a stored status field (R17)."""
    spec = spec if spec is not None else load_spec(repo_root, outcome_id)
    store = store if store is not None else _store(repo_root, outcome_id)
    states = derive_states(spec, store)
    counts: dict[str, int] = {}
    for st in states.values():
        counts[st] = counts.get(st, 0) + 1
    done = {sid for sid, st in states.items() if st == LIVE_DONE}
    return {
        "outcome_id": spec.outcome_id,
        "objective": spec.objective,
        "spec_revision": spec.spec_revision,
        "nodes": len(spec.nodes),
        "states": states,
        "counts": counts,
        # Derive the frontier from the SAME states map, not a separate success-only ready_frontier:
        # otherwise a negative-terminal (failed/rejected/stalled) node whose deps are satisfied would be
        # re-listed as dispatchable, contradicting its own `states` entry (the U8 cross-surface fix).
        "frontier": sorted(sid for sid, st in states.items() if st == LIVE_READY),
        "complete": len(done) == len(spec.nodes),
    }


# ---------------------------------------------------------------------------
# advance — the level-triggered reconcile tick (R29)
# ---------------------------------------------------------------------------


@dataclass
class AdvanceResult:
    dispatched: list[str] = field(default_factory=list)  # subplots handed to a backend this tick
    harvested: list[str] = field(
        default_factory=list
    )  # completions materialized from GitHub (U5/R10)
    halted: list[dict[str, Any]] = field(
        default_factory=list
    )  # HALT receipts — backend down (kind=halt, R5/R23) or spend gate (kind=spend-halt, #373)
    merges: list[Any] = field(default_factory=list)  # per-tick auto-merge queue results (U6/R12)
    worktrees: list[Any] = field(
        default_factory=list
    )  # per-tick worktree reap/removed/provision (U7/R15/R32)
    liveness: list[Any] = field(default_factory=list)  # per-tick stalled-leaf reclaim (U9/R31)
    costs: list[Any] = field(
        default_factory=list
    )  # per-tick realized-cost rollup materialization (U10/R24)
    gated: list[str] = field(
        default_factory=list
    )  # ready leaves held back by the approval gate (U7/R20)
    retriable: list[str] = field(
        default_factory=list
    )  # leaves whose dispatch hit a 429 -> retriable-pending, left ready to re-pick (#348/R4/KTD4)
    degraded: list[dict[str, Any]] = field(
        default_factory=list
    )  # leaves degraded one rung autonomous+away (U9/R23)
    board_synced: list[dict[str, Any]] = field(
        default_factory=list
    )  # per-tick autonomous board-sync records (U4/#279 — only when autonomous=True)
    drift: list[dict[str, Any]] = field(
        default_factory=list
    )  # per-tick board<->saga drift/recovered records (#295 — only when autonomous=True)
    skipped_busy: bool = False  # coordinator lease held by another tick -> no-op (R13)
    ticks: int = 1
    spec_reloads: int = 0  # mid-run on-disk revision moves detected -> spec re-read (#433 M2/M4)
    status: dict[str, Any] = field(default_factory=dict)
    adjustment: dict[str, Any] = field(
        default_factory=dict
    )  # #372: the mid-run adjustment-envelope poll decision that stopped dispatch, if any
    # (action/surfaced/amendments); empty when the envelope was absent or said "proceed".

    def to_dict(self) -> dict[str, Any]:
        return {
            "dispatched": self.dispatched,
            "harvested": self.harvested,
            "halted": self.halted,
            "merges": self.merges,
            "worktrees": self.worktrees,
            "liveness": self.liveness,
            "costs": self.costs,
            "gated": self.gated,
            "retriable": self.retriable,
            "degraded": self.degraded,
            "board_synced": self.board_synced,
            "drift": self.drift,
            "skipped_busy": self.skipped_busy,
            "ticks": self.ticks,
            "spec_reloads": self.spec_reloads,
            "status": self.status,
            "adjustment": self.adjustment,
        }


def _default_board_writer(
    repo_root: Path,
    *,
    project: str = "operations",
    runner: Callable[..., Any] | None = None,
) -> Callable[..., None]:
    """Re-export of ``board_progression.default_board_writer`` (#344 KTD6).

    The production board_writer (the ``OpKind`` → ``sdlc_manager.py`` verb mapping) moved to
    ``board_progression`` so the skill consumers (`/work`, `/loop`) can reach it through the CLI.
    Kept here so ``advance``'s call sites and any test references remain valid.
    """
    import board_progression as _m  # noqa: PLC0415

    return _m.default_board_writer(repo_root, project=project, runner=runner)


def advance(
    repo_root: Path,
    outcome_id: str,
    *,
    loop: bool = False,
    max_ticks: int = 100,
    dispatcher: Dispatcher | None = None,
    harvester: Callable[[Any, Any], list[str]] | None = None,
    merge_processor: Callable[[Any, Any], Any] | None = None,
    worktree_processor: Callable[[Any, Any], Any] | None = None,
    liveness_processor: Callable[[Any, Any], Any] | None = None,
    cost_processor: Callable[[Any, Any], Any] | None = None,
    gate_factory: Callable[[Any, Any], Callable[[str], bool]] | None = None,
    available: Sequence[str] | None = None,
    attending: bool = True,
    holder: str | None = None,
    lease_ttl: float = DEFAULT_LEASE_TTL,
    now: Callable[[], float] = time.time,
    runner: Callable[..., Any] | None = None,
    autonomous: bool = False,
    board_writer: Callable[..., None] | None = None,
    board_reader: Callable[[str], str] | None = None,
    issue_reader: Callable[[str], dict[str, str]] | None = None,
    project: str = "operations",
    envelope_path: Path | None = None,
    envelope_poll: Callable[[], adjustment_envelope.PollDecision] | None = None,
    settlement_ledger: run_ledger.RunLedger | None = None,
) -> AdvanceResult:
    """Run one (``loop=False``) or repeated (``loop=True``) reconcile ticks.

    A tick: acquire the coordinator lease under a per-invocation unique ``holder`` (a second
    concurrent / re-entrant ``advance`` is a different holder, so it no-ops on the held lease, R13);
    **harvest** GitHub-canonical completions into the cache (the optional ``harvester``, U5 — a
    code leaf's merged PR / a non-code leaf's closed issue becomes a completion event that unlocks the
    next Kahn layer, R10/R11); recompute the ready frontier; for each ready, not-yet-dispatched,
    not-completed leaf, take its per-subplot dispatch lock and **dispatch** it — never running the
    leaf's work here (R3); then return the derived status. Idempotent: a leaf with a settled
    (``commit``) dispatch record is skipped, so repeated ticks never double-dispatch. ``loop`` repeats
    until the frontier is empty or ``max_ticks``, which the host (`/loop`/cron) would otherwise drive.

    ``project`` (#326) names the target mission-control board/workflow and is the single source
    threaded to both the default board writer and ``outcome_board_sync.reconcile_board`` — the two
    must never disagree about which board they're resolving statuses against.

    The spec's committed run-start intent envelope (#373) is enforced inside each tick's
    reconcile pass (see ``_reconcile_once``): ``backends_permitted`` intersects the runtime
    ``available`` set, ``degrade_policy`` bounds the degrade path, and ``spend_envelope`` is a
    HALT-only pre-dispatch authorization against the leaf-produced cost actuals. Specs without
    a captured posture behave exactly as before.
    """
    holder = holder if holder is not None else _default_holder()
    dispatch = dispatcher if dispatcher is not None else _default_dispatcher
    spec = load_spec(repo_root, outcome_id)
    store = _store(repo_root, outcome_id, runner=runner)
    # The R20 approval gate is built from the loaded spec/store so it sees the CURRENT spec_revision —
    # a graph edit (which bumps the revision + re-closes the gate) is reflected on the next advance.
    dispatch_gate = gate_factory(spec, store) if gate_factory is not None else None

    # #372: the mid-run adjustment-envelope poll. Reuses the EXISTING tick-quiescence boundary
    # (no new poll loop): each tick re-reads the operator/worker control file so a quiesce, an
    # andon_halt, or an unknown directive (fail-closed) stops dispatch after the in-flight harvest
    # drains. A missing file polls "proceed". The poll is re-read every tick (not cached) so a
    # directive written mid-run is seen on the very next tick.
    if envelope_poll is not None:
        _poll = envelope_poll
    else:
        _env_path = (
            envelope_path
            if envelope_path is not None
            else adjustment_envelope.default_envelope_path(repo_root)
        )

        def _poll() -> adjustment_envelope.PollDecision:
            return adjustment_envelope.poll(adjustment_envelope.load(_env_path))

    if not outcome_store.acquire_coordinator(store, holder, lease_ttl, now=now):
        return AdvanceResult(
            skipped_busy=True, ticks=0, status=status(repo_root, outcome_id, spec=spec, store=store)
        )

    all_dispatched: list[str] = []
    all_halted: list[dict[str, Any]] = []
    all_harvested: list[str] = []
    all_gated: list[str] = []
    all_retriable: list[str] = []
    # #348/KTD4: sids that hit a 429 this advance() CALL are skipped for the rest of the call so a
    # loop=True run never hammers a rate-limited backend. Per-call (never persisted): a fresh advance
    # re-derives the leaf as `ready` and re-attempts it -- the derived-on-read re-pick.
    retriable_seen: set[str] = set()
    all_degraded: list[dict[str, Any]] = []
    all_board_synced: list[dict[str, Any]] = []
    all_drift: list[dict[str, Any]] = []
    merge_runs: list[Any] = []
    worktree_runs: list[Any] = []
    liveness_runs: list[Any] = []
    cost_runs: list[Any] = []
    # #372: set when an envelope directive stops dispatch, OR when a proceed decision carries
    # amendments/surfaced info (recorded with applied=False — surfaced, never silently dropped).
    adjustment_decision: dict[str, Any] = {}
    ticks = 0
    spec_reloads = 0
    try:
        while True:
            ticks += 1
            # #433 (M2/M4): the canonical spec can move under a running coordinator — a mid-run
            # `repost`/`set-intent` bumps the on-disk revision while this process still holds
            # the load-time spec in memory. Re-check at every tick boundary and reload so this
            # tick's harvest/dispatch act on the posture actually in force, never on a revision
            # the operator has already superseded. (load_spec raises loudly on a broken file —
            # fail closed, never dispatch under a posture we cannot verify.)
            if _on_disk_revision(repo_root, outcome_id) != spec.spec_revision:
                spec = load_spec(repo_root, outcome_id)
                if gate_factory is not None:
                    dispatch_gate = gate_factory(spec, store)
                spec_reloads += 1
            if merge_processor is not None:
                # Auto-merge clean PRs FIRST (under the held coordinator lease, so serialized
                # cross-process, R12/R13), then harvest reads the now-merged PRs as completions.
                merge_runs.append(merge_processor(spec, store))
            if harvester is not None:
                # Materialize GitHub-canonical completions BEFORE the frontier read so a leaf whose
                # PR just merged unlocks its dependents this same tick (R10/R11).
                all_harvested.extend(harvester(spec, store))
            if worktree_processor is not None:
                # Reap terminal sub-outcomes' worktrees + record the worktree-removed terminal (R32)
                # BEFORE the frontier read so a vanished worktree cascades this tick (R22/R15).
                worktree_runs.append(worktree_processor(spec, store))
            if liveness_processor is not None:
                # Reclaim any hung dispatched leaf as `stalled` (R31) BEFORE the frontier read so its
                # downstream cascade is reflected this tick (R22).
                liveness_runs.append(liveness_processor(spec, store))
            # #372: poll the adjustment envelope at the tick boundary AFTER the in-flight harvest
            # (so a quiesce drains the leaf that just completed) and BEFORE dispatch (so nothing new
            # is handed out once stopped). A halting/draining/pausing decision — or a fail-closed
            # EnvelopeError from an unrecognized directive — records the surfaced decision and breaks
            # the loop; the in-flight leaves finish in their own worktrees, the coordinator dispatches
            # nothing new, and status() below is the resume point. This composes with HALT-not-degrade
            # (a halt here never dispatches on a lower rung; it just stops).
            try:
                decision = _poll()
            except adjustment_envelope.EnvelopeError as exc:
                adjustment_decision = {
                    "action": "halt",
                    "surfaced": [f"fail-closed: {exc}"],
                    "amendments": [],
                }
                break
            if decision.stops_dispatch:
                adjustment_decision = {
                    "action": decision.action,
                    "surfaced": list(decision.surfaced),
                    "amendments": list(decision.amendments),
                }
                break
            if decision.amendments or decision.surfaced:
                # A proceed decision that still carries amendments (standalone re-tier /
                # add-reviewer) must be SURFACED, never silently dropped: the coordinator does
                # not apply amendments to its own dispatches (mid-run application is #433's
                # renegotiation contract), so the operator-visible result is the only place the
                # directive registers. applied=False says so explicitly.
                adjustment_decision = {
                    "action": decision.action,
                    "surfaced": list(decision.surfaced),
                    "amendments": list(decision.amendments),
                    "applied": False,
                }
            (
                tick_dispatched,
                tick_halted,
                tick_gated,
                tick_degraded,
                tick_retriable,
                tick_stale,
            ) = _reconcile_once(
                repo_root,
                spec,
                store,
                dispatch,
                holder,
                lease_ttl,
                now,
                dispatch_gate=dispatch_gate,
                available=available,
                attending=attending,
                retriable_seen=retriable_seen,
                settlement_ledger=settlement_ledger,
            )
            all_dispatched.extend(tick_dispatched)
            all_halted.extend(tick_halted)
            all_gated.extend(tick_gated)
            all_degraded.extend(tick_degraded)
            all_retriable.extend(tick_retriable)
            if tick_stale:
                # #433 (M2/M4): the spec went stale MID-pass (a repost committed while this
                # pass was dispatching) — the pass stopped handing out work under the revoked
                # posture. Reload immediately so the processors below (and a loop=True re-tick)
                # act on the revision actually in force.
                spec = load_spec(repo_root, outcome_id)
                if gate_factory is not None:
                    dispatch_gate = gate_factory(spec, store)
                spec_reloads += 1
            if cost_processor is not None:
                # Materialize the realized-cost rollup into spec.cost_rollup AFTER dispatch/harvest so it
                # reflects this tick's completions (U10/R24). The U8 report renders spec.cost_rollup.
                cost_runs.append(cost_processor(spec, store))
            if autonomous:
                # Autonomous board-sync (U4/#279): reconcile each leaf's derived state to the
                # reversibility-authorized board ops. The default-GATE certificate + the separate
                # idempotency ledger bound it; it only fires on the explicit autonomous path, and runs
                # under the coordinator lease so board-sync is serialized per outcome.
                import outcome_board_sync
                import outcome_github
                import outcome_reconcile

                _bw = (
                    board_writer
                    if board_writer is not None
                    else _default_board_writer(repo_root, project=project)
                )
                _br = (
                    board_reader
                    if board_reader is not None
                    else (lambda ref: outcome_github.board_status(ref, project=project))
                )
                _ir = issue_reader if issue_reader is not None else outcome_github.issue_close_info

                # #295 U5/KTD2: DETECT board<->saga drift BEFORE any board write. A detected drift
                # withholds that issue's ops (hold_issues) so the write never acts on a board that
                # moved underneath saga; a detection failure degrades to a note, never wedges the tick.
                try:
                    drift_records = outcome_reconcile.detect(
                        spec, store, board_reader=_br, issue_reader=_ir, project=project, now=now
                    )
                except Exception as exc:  # noqa: BLE001 — best-effort; never tick-fatal
                    drift_records = [{"kind": "unreadable", "error": str(exc)}]
                all_drift.extend(drift_records)
                hold_issues = {
                    (str(r["repo"]), int(r["number"]))
                    for r in drift_records
                    if r.get("kind") in outcome_reconcile.DRIFT_KINDS
                }
                all_board_synced.extend(
                    outcome_board_sync.reconcile_board(
                        spec,
                        store,
                        board_writer=_bw,
                        now=now,
                        project=project,
                        hold_issues=hold_issues,
                    )
                )
            if not loop:
                break
            if not tick_dispatched and not tick_stale:
                break  # quiescent: nothing new to dispatch this tick (HALTed/gated leaves wait)
            if ticks >= max_ticks:
                break
    finally:
        outcome_store.release_lease(store, outcome_store.COORDINATOR_LOCK, holder)

    return AdvanceResult(
        dispatched=all_dispatched,
        harvested=all_harvested,
        halted=all_halted,
        merges=merge_runs,
        worktrees=worktree_runs,
        liveness=liveness_runs,
        costs=cost_runs,
        gated=sorted(set(all_gated)),
        retriable=sorted(set(all_retriable)),
        degraded=all_degraded,
        board_synced=all_board_synced,
        drift=all_drift,
        ticks=ticks,
        spec_reloads=spec_reloads,
        status=status(repo_root, outcome_id, spec=spec, store=store),
        adjustment=adjustment_decision,
    )


def _reconcile_once(
    repo_root: Path,
    spec: outcome_spec.OutcomeSpec,
    store: Any,
    dispatch: Dispatcher,
    holder: str,
    lease_ttl: float,
    now: Callable[[], float],
    *,
    dispatch_gate: Callable[[str], bool] | None = None,
    available: Sequence[str] | None = None,
    attending: bool = True,
    retriable_seen: set[str] | None = None,
    settlement_ledger: run_ledger.RunLedger | None = None,
) -> tuple[list[str], list[dict[str, Any]], list[str], list[dict[str, Any]], list[str], bool]:
    """One level-triggered pass: dispatch every ready, not-yet-settled leaf exactly once.

    Returns ``(dispatched, halted, gated, degraded, retriable, stale)``. ``stale`` (#433
    M2/M4) is True when the on-disk ``spec_revision`` moved mid-pass (a concurrent
    ``repost``/``set-intent`` committed): the pass STOPS dispatching immediately — a tick
    whose spec went stale must never hand out work under a revoked posture — and the caller
    reloads before the next pass. Each dispatch is recorded
    **intent -> effect ->
    commit** (the store's replay protocol): the intent is written BEFORE the backend is invoked, so a
    crash/append-failure after the effect leaves a durable dangling intent that ``replay_pending``
    surfaces and the next reconcile re-drives. The ``commit`` is the durable dedup marker (and carries an
    ``at`` timestamp for the U9 liveness check) — a settled dispatch is skipped on every later tick.

    The optional ``dispatch_gate`` is the R20 approval gate: a ready leaf the gate rejects is **held
    back** (added to ``gated``, NOT dispatched) until the operator approves the current frontier.

    The presence-conditional **degrade decision** (R23/AE1, ``outcome_dispatcher.degrade_decision``) runs
    per leaf before dispatch when ``available`` is given: a leaf whose chosen backend is unavailable
    **HALTs** if the operator is attending / it is guarantee-bearing / it already side-effected
    (destructive), else **degrades one rung** down the ladder (recording a visible :class:`DegradeReceipt`
    in the ledger) and dispatches on the lower backend. ``available=None`` keeps the legacy behavior (the
    chosen backend is dispatched as-is, and a dispatcher that raises ``BackendHaltError`` still HALTs).

    A backend HALT is recorded in the ledger (durable + visible) and reconcile CONTINUES to other
    runnable leaves — one unavailable backend never starves the frontier, and a HALT/degrade is never a
    silent substitution.

    A backend 429 (``BackendRateLimitError``) is classified **retriable-pending** (#348/R4/KTD4): it
    writes NO commit, so the leaf's derived state stays ``ready`` and the frontier re-picks it on the
    next advance() call — a derived-on-read RESULT label, never a committed ``NODE_STATE``. The optional
    ``retriable_seen`` set is the per-call de-hammer guard: a sid that 429'd earlier in the SAME
    advance() call is skipped for the rest of the call (a fresh call re-derives + re-attempts it).

    The **captured run-start posture** (#373) is enforced here, per pass: the spec's committed
    intent envelope may carry ``backends_permitted`` (the effective menu becomes captured ∩
    runtime — consumed, never re-derived ad hoc per call), ``degrade_policy`` (an unmet backend
    HALTs by default; ``operator_away_one_rung`` lets the UNCHANGED presence-conditional
    mechanism degrade at most ONE ladder rung, never a cascade), and ``spend_envelope`` (a
    HALT-only pre-dispatch authorization read against ``outcome_costs``'s leaf-produced
    actuals BEFORE any backend resolution — an over-ceiling or tier-escalating leaf records a
    visible ``spend-halt`` receipt and never silently degrades). A spec with no intent — or a
    #380 intent carrying none of the #373 fields — leaves every path byte-identical to before.
    """
    # #373: parse the committed posture ONCE per pass. Captured at run start, consumed here.
    posture = outcome_dispatcher.captured_posture(spec.intent)
    permitted = posture.backends_permitted if posture is not None else None
    posture_degrade_policy: str = posture.degrade_policy if posture is not None else ""
    backend_posture_engaged = permitted is not None or bool(posture_degrade_policy)
    spend_env = posture.spend_envelope if posture is not None else None
    effective = outcome_dispatcher.effective_available(permitted, available)
    actual_tokens: float | None = None
    if spend_env is not None and spend_env.cost_ceiling_tokens is not None:
        import outcome_costs  # noqa: PLC0415  (sibling; lazy, mirrors production_cost_processor)

        # One consistent snapshot of the leaf-produced actuals per pass — read through the
        # SAME rollup producer ``materialize`` uses (the R24 ledger), BEFORE any dispatch.
        # An absent "tokens" total means no leaf has reported cost yet ("no data yet"):
        # nothing is measured against the ceiling, so the cost gate does not engage.
        actual_tokens = outcome_costs.rollup(spec, store).get("tokens")

    success = outcome_store.completed_subplots(store)  # success-only -> the frontier input
    settled = set(_dispatch_records(store))  # subplots with a COMMIT dispatch record
    frontier = outcome_spec.ready_frontier(spec, success)
    dispatched: list[str] = []
    halted: list[dict[str, Any]] = []
    gated: list[str] = []
    degraded: list[dict[str, Any]] = []
    retriable: list[str] = []
    stale = False
    settlement_bindings: dict[str, tuple[str, dispatch_settlement.UnitSpec]] = {}
    settlement_blocked: set[str] = set()
    settlement_frontier = [sid for sid in frontier if sid not in settled]
    if settlement_ledger is not None and settlement_frontier:
        settlement_bindings = dispatch_settlement.outcome_dispatch_bindings(
            settlement_ledger, spec.outcome_id, settlement_frontier
        )
        new_units = [sid for sid in settlement_frontier if sid not in settlement_bindings]
        blocking_reports = [
            report
            for report in dispatch_settlement.outcome_reports(settlement_ledger, spec.outcome_id)
            if report.halt_required
        ]
        if new_units and blocking_reports:
            settlement_blocked.update(new_units)
            for sid in new_units:
                report_ids = ",".join(report.dispatch_id for report in blocking_reports)
                gate_receipt: dict[str, Any] = {
                    "kind": "settlement-halt",
                    "outcome_id": spec.outcome_id,
                    "subplot_id": sid,
                    "reason": (
                        "prior dispatch cohort has missing evidence or exceeds its casualty "
                        f"threshold: {report_ids}"
                    ),
                    "dispatch_ids": [report.dispatch_id for report in blocking_reports],
                }
                _append_ledger_once(
                    store,
                    {
                        "phase": "halt",
                        "key": f"settlement-gate:{sid}:{dispatch_settlement.evidence_digest(report_ids)[:16]}",
                        **gate_receipt,
                    },
                )
                halted.append(gate_receipt)
        elif new_units:
            dispatch_id, units = dispatch_settlement.outcome_frontier_identity(
                spec.outcome_id, new_units
            )
            dispatch_settlement.ensure_manifest(
                settlement_ledger,
                dispatch_settlement.manifest_fact(
                    subplot_id=spec.outcome_id,
                    at=dispatch_settlement.iso_at(now()),
                    dispatch_id=dispatch_id,
                    site="outcome",
                    units=units,
                ),
            )
            settlement_bindings.update({unit.unit_id: (dispatch_id, unit) for unit in units})
    # #433 R4: the posture era every dispatch THIS pass happens under. None (never renegotiated)
    # reads as the revision-1 run-start baseline.
    active_intent_revision = getattr(spec, "intent_revision", None) or 1
    for sid in frontier:
        if sid in settled:
            continue  # settled dispatch record exists -> idempotent skip (no double-dispatch)
        if sid in settlement_blocked:
            continue  # a prior cohort blocks this new fan-out boundary until it is reconciled
        if retriable_seen is not None and sid in retriable_seen:
            continue  # already 429'd this advance() call -> don't hammer; re-picked on the next call
        if dispatch_gate is not None and not dispatch_gate(sid):
            gated.append(sid)  # R20: frontier not approved at the current revision -> hold back
            continue
        node = spec.node_by_id(sid)
        if node is None:
            continue
        # Per-subplot lock guards the concurrent-tick race within the TTL window; the commit record
        # is the durable dedup. If another tick holds the lock right now, skip — it owns this leaf.
        if not outcome_store.acquire_dispatch(store, sid, holder, lease_ttl, now=now):
            continue

        # #433 (M2/M4): re-verify the on-disk revision per leaf, AFTER the lock and BEFORE the
        # dispatch intent is written. A mid-pass repost/set-intent means the posture this pass
        # loaded may be revoked — stop dispatching (the caller reloads and re-ticks) rather
        # than hand this leaf out under a posture the operator has already superseded. The
        # residual sub-window this cannot close is documented in references/outcome-spec.md
        # (§Mid-run posture renegotiation — remaining overlap window).
        if _on_disk_revision(repo_root, spec.outcome_id) != spec.spec_revision:
            outcome_store.release_lease(store, f"dispatch-{sid}", holder)
            stale = True
            break

        # #373 (T8-F5-7): the pre-dispatch spend-authorization gate — HALT-only, checked
        # BEFORE any backend resolution so an unauthorized leaf never resolves a backend and
        # never enters the degrade path (a spend denial must not silently degrade a tier).
        if spend_env is not None:
            try:
                outcome_dispatcher.authorize_dispatch_spend(
                    spend_env,
                    outcome_id=spec.outcome_id,
                    subplot_id=sid,
                    backend=node.backend,
                    requested_tier=node.tier or None,
                    actual_tokens=actual_tokens,
                )
            except outcome_dispatcher.SpendHaltError as spend_halt:
                outcome_store.release_lease(store, f"dispatch-{sid}", holder)
                receipt = spend_halt.receipt.to_dict()
                # Append-once on (halt, spend:<sid>) — a persistently over-ceiling leaf
                # re-surfaces on every advance without unbounded ledger growth. Its dedup
                # lane is distinct from the backend-halt ``dispatch:<sid>`` lane so neither
                # halt kind can mask the other.
                _append_ledger_once(
                    store,
                    {"phase": "halt", "kind": "dispatch", "key": f"spend:{sid}", **receipt},
                )
                halted.append(receipt)
                continue

        # The presence-conditional degrade decision (R23). Resolves the backend to dispatch on, or HALTs.
        resolved_backend = node.backend
        degrade_receipt: dict[str, Any] | None = None
        if backend_posture_engaged or available is not None:
            if backend_posture_engaged:
                # #373 (T8-F6-8): consume the CAPTURED posture through the existing
                # mechanism — effective menu = captured ∩ runtime, HALT by default,
                # at most one ladder rung when the posture permits degrade.
                action, resolved_backend, reason = outcome_dispatcher.captured_degrade_decision(
                    node.backend,
                    effective=effective,
                    degrade_policy=posture_degrade_policy,
                    attending=attending,
                    guarantee_bearing=outcome_dispatcher.is_guarantee_bearing(node),
                    had_side_effect=node.destructive,
                )
                receipt_available = tuple(effective or ())
            else:
                action, resolved_backend, reason = outcome_dispatcher.degrade_decision(
                    node.backend,
                    available=available or (),
                    attending=attending,
                    guarantee_bearing=outcome_dispatcher.is_guarantee_bearing(node),
                    had_side_effect=node.destructive,
                )
                receipt_available = tuple(available or ())
            if action == "halt":
                outcome_store.release_lease(store, f"dispatch-{sid}", holder)
                # #433 R8: the scoped-repose option is offered ONLY where the offered hint
                # (`repost --scope <sid> --set degrade_policy=...`) can actually resolve the
                # halt — the guarantee class, when the guarantee is borne by the node's own
                # `degrade_policy: "halt"` (no `guarantee_tags`, which a repost cannot remove).
                # Every other halt class is honestly offer-less: an ATTENDING halt fires before
                # degrade_policy is even consulted (the operator is present — R23 pages them
                # directly); a side-effected/destructive halt is HALT-not-degrade by design (no
                # posture value re-runs a side-effected leaf on a lesser backend); a captured
                # #373 envelope degrade_policy that forbids degrade is not a repost axis; an
                # availability halt (no lower rung) is not posture at all.
                offers_repose = (
                    not attending
                    and not node.destructive
                    and outcome_dispatcher.is_guarantee_bearing(node)
                    and not getattr(node, "guarantee_tags", None)
                    and (
                        not backend_posture_engaged
                        or posture_degrade_policy == intent_envelope.INTENT_DEGRADE_ONE_RUNG
                    )
                )
                receipt = outcome_dispatcher.HaltReceipt(
                    outcome_id=spec.outcome_id,
                    subplot_id=sid,
                    backend=node.backend,
                    reason=reason,
                    available=receipt_available,
                    scoped_repose=(
                        outcome_dispatcher.scoped_repose_option(spec.outcome_id, sid)
                        if offers_repose
                        else None
                    ),
                ).to_dict()
                # Append-once on (halt, key): an attended leaf polling against a persistently-unavailable
                # backend must not re-append a halt record every tick (unbounded ledger growth).
                _append_ledger_once(
                    store,
                    {"phase": "halt", "kind": "dispatch", "key": f"dispatch:{sid}", **receipt},
                )
                halted.append(receipt)
                continue
            if action == "degrade":
                degrade_receipt = outcome_dispatcher.DegradeReceipt(
                    outcome_id=spec.outcome_id,
                    subplot_id=sid,
                    from_backend=node.backend,
                    to_backend=resolved_backend,
                    reason=reason,
                ).to_dict()

        key = f"dispatch:{sid}"
        settlement_dispatch_id = ""
        settlement_unit: dispatch_settlement.UnitSpec | None = None
        settlement_attempt: int | None = None
        if settlement_ledger is not None:
            settlement_dispatch_id, settlement_unit = settlement_bindings[sid]
            terminal = dispatch_settlement.terminal_attempt_status(
                settlement_ledger,
                dispatch_id=settlement_dispatch_id,
                unit_id=settlement_unit.unit_id,
            )
            if terminal is not None:
                outcome_store.release_lease(store, f"dispatch-{sid}", holder)
                preexisting_terminal_receipt: dict[str, Any] = {
                    "kind": "settlement-halt",
                    "outcome_id": spec.outcome_id,
                    "subplot_id": sid,
                    "dispatch_id": settlement_dispatch_id,
                    "attempt": int(terminal["attempt"]),
                    "reason": (
                        f"settlement is terminal ({terminal['status']}): "
                        f"{terminal.get('reason', '')}"
                    ),
                }
                _append_ledger_once(
                    store,
                    {
                        "phase": "halt",
                        "key": f"settlement-terminal:{sid}:{terminal['attempt']}",
                        **preexisting_terminal_receipt,
                    },
                )
                halted.append(preexisting_terminal_receipt)
                continue
        # #433 R4/R5: the posture era is captured on the INTENT record too — the same snapshot
        # the commit record carries below. A leaf stranded in the crash-after-intent window
        # (backend effect possibly live, commit record never written) is in flight for EVERY
        # consumer: the strand check (R6) already counts it, so the harvest/closure-gate era
        # map must see the same era — otherwise a loosening repost landing in that window
        # retroactively releases the leaf's completion gate under the CURRENT-intent fallback.
        era_posture = {
            "intent_revision": active_intent_revision,
            "intent": spec.intent,
            "degrade_policy": node.degrade_policy,
            "mutation_policy": (
                node.sandbox.mutation_policy if node.sandbox is not None else "read-write"
            ),
            "workspace_isolation": (
                node.sandbox.workspace_isolation if node.sandbox is not None else "ambient"
            ),
        }
        outcome_store.append_ledger(
            store,
            {
                "phase": "intent",
                "kind": "dispatch",
                "key": key,
                "subplot_id": sid,
                "intent_revision": active_intent_revision,
                "posture": dict(era_posture),
            },
        )
        if settlement_ledger is not None and settlement_unit is not None:
            # The run-fact spawn is the last durable action before the host call. A crash or tool
            # failure after this point remains an open position instead of disappearing.
            prepared = dispatch_settlement.prepare_attempt(
                settlement_ledger,
                subplot_id=sid,
                at=dispatch_settlement.iso_at(now()),
                dispatch_id=settlement_dispatch_id,
                site="outcome",
                unit=settlement_unit,
            )
            if prepared.get("status") in {
                "retry-exhausted",
                "already-delivered",
                "late-delivered",
            }:
                outcome_store.release_lease(store, f"dispatch-{sid}", holder)
                terminal_receipt: dict[str, Any] = {
                    "kind": "settlement-halt",
                    "outcome_id": spec.outcome_id,
                    "subplot_id": sid,
                    "dispatch_id": settlement_dispatch_id,
                    "attempt": int(prepared["attempt"]),
                    "reason": (
                        f"settlement is terminal ({prepared['status']}): "
                        f"{prepared.get('reason', '')}"
                    ),
                }
                _append_ledger_once(
                    store,
                    {
                        "phase": "halt",
                        "key": f"settlement-terminal:{sid}:{prepared['attempt']}",
                        **terminal_receipt,
                    },
                )
                halted.append(terminal_receipt)
                continue
            settlement_attempt = int(prepared["attempt"])
        try:
            leaf_saga_id = dispatch(
                DispatchRequest(
                    outcome_id=spec.outcome_id,
                    subplot_id=sid,
                    title=node.title,
                    backend=resolved_backend,
                    repo_root=Path(repo_root),
                    # Producer half of the U3 sandbox probe: the resolved backend (post-degrade)
                    # must be able to enforce this node's declared containment or dispatch HALTs.
                    sandbox=node.sandbox,
                    # #433 R4/R5: the posture era this leaf runs under — captured at dispatch,
                    # never re-evaluated when a later repost amends the campaign.
                    intent_revision=active_intent_revision,
                    # Preserve the durable pre-call spawn identity at the real runtime boundary.
                    dispatch_id=settlement_dispatch_id,
                    attempt=settlement_attempt if settlement_attempt is not None else 1,
                    idempotency_key=(
                        settlement_unit.idempotency_key if settlement_unit is not None else ""
                    ),
                )
            )
        except outcome_dispatcher.BackendRateLimitError as rate_limit:
            # #348/R4/KTD4: a 429 during dispatch is TRANSIENT, not a HALT. Release the lock and write
            # NO commit -> the leaf's derived state stays `ready`, so the ready frontier re-picks it on
            # the next advance() call. `retriable-pending` is a derived-on-read RESULT label, never a
            # committed NODE_STATE, and this path mutates no git/ledger state (the dangling intent at
            # `key` is re-driven exactly like the HALT path). Skip it for the rest of THIS call so a
            # loop=True run never hammers the rate-limited backend. Non-429 failures HALT as before.
            outcome_store.release_lease(store, f"dispatch-{sid}", holder)
            retriable.append(sid)
            if retriable_seen is not None:
                retriable_seen.add(sid)
            if settlement_ledger is not None:
                receipt = rate_limit.receipt.to_dict()
                if settlement_attempt is None:
                    raise OutcomeError("settlement attempt binding is missing") from rate_limit
                dispatch_settlement.settle_attempt(
                    settlement_ledger,
                    subplot_id=sid,
                    at=dispatch_settlement.iso_at(now()),
                    dispatch_id=settlement_dispatch_id,
                    unit_id=sid,
                    attempt=settlement_attempt,
                    classification=dispatch_settlement.RATE_KILLED,
                    reason="outcome backend returned a trusted rate-limit receipt",
                    evidence_ref="outcome-rate-limit",
                    evidence_sha256=dispatch_settlement.evidence_digest(receipt),
                )
            continue
        except outcome_dispatcher.BackendHaltError as halt:
            # A dispatcher-raised HALT (legacy / a restricted injected dispatcher). Release the lock so a
            # later tick re-attempts + re-surfaces it; record the receipt durably; never abort the tick.
            outcome_store.release_lease(store, f"dispatch-{sid}", holder)
            receipt = halt.receipt.to_dict()
            _append_ledger_once(store, {"phase": "halt", "kind": "dispatch", "key": key, **receipt})
            halted.append(receipt)
            if settlement_ledger is not None:
                if settlement_attempt is None:
                    raise OutcomeError("settlement attempt binding is missing") from halt
                dispatch_settlement.settle_attempt(
                    settlement_ledger,
                    subplot_id=sid,
                    at=dispatch_settlement.iso_at(now()),
                    dispatch_id=settlement_dispatch_id,
                    unit_id=sid,
                    attempt=settlement_attempt,
                    classification=dispatch_settlement.SILENT_NOOP,
                    reason="backend halted before returning a dispatch handle",
                )
            continue
        if degrade_receipt is not None:
            # A visible downgrade receipt (R23) — surfaced in the report's Degradations section.
            # Append-once on (degrade, key) so a crash in the degrade->commit window (recovery re-runs the
            # intent) cannot double-list the degradation.
            _append_ledger_once(store, {"phase": "degrade", "key": key, **degrade_receipt})
            degraded.append(degrade_receipt)
        outcome_store.append_ledger(
            store,
            {
                "phase": "commit",
                "kind": "dispatch",
                "key": key,
                "subplot_id": sid,
                "leaf_saga_id": leaf_saga_id,
                "backend": resolved_backend,
                "at": now(),  # dispatch timestamp for the U9 liveness check (R31)
                # #433 R4: dispatch-time posture. The leaf finishes under THIS posture even if
                # a later repost amends the campaign (R5); the repost strand check (R6) reads
                # it back to decide whether an amendment would revoke authorization the leaf
                # already carries, and the harvest/closure-gate seam reads "intent" back so an
                # in-flight leaf's COMPLETION gate (e.g. an implied code-review check under
                # reviews_required: "gate") is evaluated against the campaign envelope in
                # force at dispatch — never against a later loosening. "intent": null says
                # explicitly "dispatched with no committed envelope" (implies no checks, even
                # if an envelope attaches later); an absent key is a pre-capture record and
                # falls back to the spec's current intent.
                "intent_revision": active_intent_revision,
                "posture": dict(era_posture),
                "settlement": (
                    {
                        "dispatch_id": settlement_dispatch_id,
                        "unit_id": sid,
                        "attempt": settlement_attempt,
                    }
                    if settlement_attempt is not None
                    else None
                ),
            },
        )
        dispatched.append(sid)
    return dispatched, halted, gated, degraded, retriable, stale


# ---------------------------------------------------------------------------
# attend — print the native leaf re-entry handoff (R16 altitude seam)
# ---------------------------------------------------------------------------


def _positive_int_str(value: object) -> str:
    """The decimal string of ``value`` iff it is a **positive** integer, else ``""``.

    A GitHub issue number is always ``>= 1``, so a zero/negative/garbage value is never a valid
    ``issue-<N>`` saga id — coerce it to ``""`` so the caller falls back to the raw handoff rather than
    emitting a dead pointer like ``issue-0`` (the very class of bug #491 fixes). ``bool`` is excluded
    though it is an ``int`` subclass.
    """
    if isinstance(value, bool):
        return ""
    if isinstance(value, int) and value > 0:
        return str(value)
    if isinstance(value, str) and value.strip().isdigit() and int(value.strip()) > 0:
        return str(int(value.strip()))
    return ""


def _leaf_handoff_id(node: Any, leaf_saga_id: str) -> str:
    """The operator-facing native saga id for a dispatched leaf's re-entry handoff (#491).

    An issue-backed leaf's REAL native saga is ``issue-<N>`` — what ``/plan``/``/work`` mint via
    ``saga.derive_saga_id("issue", N)`` (``saga.py:333``) — not the dispatcher's record-keeping
    ``leaf-<outcome>-<subplot>`` id. Prefer the node's bare ``sub_issue`` number; else parse an
    ``owner/repo#N`` ``issue`` ref (reusing ``outcome_github._parse_ref``, #495). A leaf with no
    resolvable **positive** issue number (a task/ad-hoc leaf, or a malformed ref) keeps the raw
    ``leaf_saga_id`` — never raises, never emits a non-positive ``issue-<N>`` (R3).
    """
    if node is None:
        return leaf_saga_id
    import outcome_github  # noqa: PLC0415 — lazy, matching this module's outcome_github import sites

    github = node.github if isinstance(getattr(node, "github", None), dict) else {}
    number = _positive_int_str(github.get("sub_issue"))
    if not number:
        parsed = outcome_github._parse_ref(str(github.get("issue", "")))
        if parsed is not None:
            number = _positive_int_str(parsed[2])
    # ``issue-<N>`` mirrors ``saga.derive_saga_id("issue", N)`` (saga.py:333) — inlined to avoid pulling
    # the heavy ``saga`` module into ``outcome.py`` for a one-line format (KTD2).
    return f"issue-{number}" if number else leaf_saga_id


def attend(repo_root: Path, outcome_id: str, subplot_id: str) -> str:
    """Return the native ``/resume <saga-id>`` handoff for a dispatched leaf.

    The coordinator does not run the leaf — it hands the operator the exact native command to drop
    into that leaf's own saga (R16). Leaf verbs (`/work`, `/code-review`, `/qa`) are reused, never
    shadowed by an `/outcome work`. For an issue-backed leaf the handoff is the real ``issue-<N>`` saga
    (#491), resolved from the node; a non-issue-backed leaf keeps the raw dispatcher id.
    """
    store = _store(repo_root, outcome_id)
    records = _dispatch_records(store)
    leaf = records.get(subplot_id)
    if not leaf:
        raise OutcomeError(
            f"subplot {subplot_id!r} is not dispatched yet — nothing to attend "
            f"(dispatched: {sorted(records)})"
        )
    node = load_spec(repo_root, outcome_id).node_by_id(subplot_id)
    return f"/resume {_leaf_handoff_id(node, leaf)}"


def _saga_version() -> str:
    """The installed saga plugin version, for the discovery envelope's producer block."""
    manifest = Path(__file__).resolve().parent.parent / ".claude-plugin" / "plugin.json"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "0"
    return str(data.get("version", "0")) if isinstance(data, dict) else "0"


def _cli_broker(broker_root: str | None) -> Any:
    """The production #356 broker (host state root), or an explicit root for tests."""
    import fleet_commons_shim

    lease_broker = fleet_commons_shim.load("lease_broker")
    return (
        lease_broker.LeaseBroker(Path(broker_root)) if broker_root else lease_broker.LeaseBroker()
    )


def _cli_broker_error() -> type[Exception]:
    """The #356 broker's error root, resolved lazily so broker-free verbs never load fleet-core."""
    import fleet_commons_shim

    return cast("type[Exception]", fleet_commons_shim.load("lease_broker").LeaseBrokerError)


def _cli_admission(args: Any) -> dict[str, Any]:
    """The session-admission snapshot (resolved by the caller, never invented here)."""
    values = {
        "session_id": args.session_id,
        "policy_sha256": args.policy_sha256,
        "session_limit": args.session_limit,
        "aggregate_limit": args.aggregate_limit,
    }
    missing = sorted(key for key, value in values.items() if value in (None, ""))
    if missing:
        raise OutcomeError(
            f"missing session-admission flags: {', '.join('--' + k.replace('_', '-') for k in missing)}"
            " (pass the canonical resolved snapshot; admission values are never defaulted)"
        )
    return values


def _settled_lookup(repo_root: Path):
    """A #351-backed settled-attempt query for handoff acceptance (R5) — never a new ledger."""
    import dispatch_settlement

    ledger = run_ledger.RunLedger.resolve(repo_root)

    def lookup(dispatch_id: str, unit_id: str, attempt: int) -> bool:
        del attempt  # terminal_attempt_status resolves the latest attempt itself
        if not dispatch_id:
            return False
        try:
            return (
                dispatch_settlement.terminal_attempt_status(
                    ledger, dispatch_id=dispatch_id, unit_id=unit_id
                )
                is not None
            )
        except dispatch_settlement.DispatchSettlementError:
            return False  # cannot prove settled -> the advance layer still dedups (R7)

    return lookup


def attached_advance(
    repo_root: Path,
    outcome_id: str,
    subplot_id: str,
    *,
    handoff_id: str,
    receiver_owner_id: str,
    admission: dict[str, Any],
    broker: Any,
    settled_lookup: Callable[[str, str, int], bool] | None = None,
) -> dict[str, Any]:
    """Accept an ``advance-one`` handoff, then run ONE allowlisted one-subplot tick (R5/R7).

    The handoff authorizes exactly one subplot: after acceptance this re-checks the committed
    revision and the ready frontier (KTD7 — a moved spec or a frontier that no longer offers
    this leaf HALTs loudly rather than silently broadening or shrinking the authorization),
    then enters the existing ``advance`` behind a one-subplot gate. There is no ``--loop`` and
    no frontier-wide form; the coordinator's per-subplot locks and #351 settlement dedup stay
    in force as secondary containment.
    """
    import outcome_compat

    accepted = outcome_compat.accept_handoff(
        repo_root,
        outcome_id,
        handoff_id,
        operation="advance-one",
        subplot_id=subplot_id,
        receiver_owner_id=receiver_owner_id,
        receiver_runtime=outcome_compat.RUNTIME_LABEL,
        admission=admission,
        broker=broker,
        settled_lookup=settled_lookup,
    )
    binding = outcome_compat.resolve_committed_spec(repo_root, outcome_id)
    if int(binding["spec_revision"]) != int(accepted["offer"]["spec_revision"]):
        raise outcome_compat.CompatibilityHaltError(
            "handoff-wrong-revision",
            unsupported=(
                f"an advance under a handoff bound to revision {accepted['offer']['spec_revision']}"
            ),
            supported=f"the committed spec revision {binding['spec_revision']}",
            next_action="re-discover the outcome and request a fresh handoff at this revision",
        )
    spec = load_spec(repo_root, outcome_id)
    store = _store(repo_root, outcome_id)
    frontier = outcome_spec.ready_frontier(spec, outcome_store.completed_subplots(store))
    if subplot_id not in frontier:
        raise outcome_compat.CompatibilityHaltError(
            "handoff-frontier-changed",
            unsupported=f"an advance for {subplot_id!r} which is no longer on the ready frontier",
            supported="an advance for a leaf still on the dependency-derived ready frontier",
            next_action="re-discover the outcome; the frontier moved since the handoff was issued",
        )
    result = advance(
        repo_root,
        outcome_id,
        gate_factory=lambda _spec, _store: lambda sid: sid == subplot_id,
    )
    return {
        "handoff_id": handoff_id,
        "subplot_id": subplot_id,
        "successor_lease_id": accepted["lease"].lease_id,
        "advance": result.to_dict(),
    }


def attended_handoff(
    repo_root: Path,
    outcome_id: str,
    subplot_id: str,
    *,
    handoff_id: str,
    receiver_owner_id: str,
    admission: dict[str, Any],
    broker: Any,
) -> str:
    """Accept an ``attend`` handoff, then derive the native resume command (R11).

    The printable command is derived only AFTER every binding validates — a copied or replayed
    reference never turns into operator guidance.
    """
    import outcome_compat

    outcome_compat.accept_handoff(
        repo_root,
        outcome_id,
        handoff_id,
        operation="attend",
        subplot_id=subplot_id,
        receiver_owner_id=receiver_owner_id,
        receiver_runtime=outcome_compat.RUNTIME_LABEL,
        admission=admission,
        broker=broker,
    )
    return attend(repo_root, outcome_id, subplot_id)


# ---------------------------------------------------------------------------
# export / import — retired outcome-bundle/1 surface (#604 R10: export aliases discover;
# import always refuses)
# ---------------------------------------------------------------------------


def export_bundle(
    repo_root: Path, outcome_id: str, *, runner: Callable[..., Any] | None = None
) -> dict[str, Any]:
    """DEPRECATED alias of ``discover`` (#604 R10 — legacy portable authority is retired).

    The old ``outcome-bundle/1`` snapshot copied cache completion and dispatch records across
    repositories and wrote the bundled spec on import — exactly the second authority path #579
    retires. This entrypoint now returns the ``outcome.discovery.v1`` envelope byte-for-byte
    (the same JSON ``discover`` prints): committed/GitHub references and digests only, never a
    mutable cache fact. Import-side authority transfer is refused entirely
    (:func:`import_bundle`).
    """
    import outcome_compat

    return outcome_compat.build_discovery_envelope(
        Path(repo_root), outcome_id, saga_version=_saga_version(), runner=runner
    )


def import_bundle(
    repo_root: Path, bundle: dict[str, Any], *, runner: Callable[..., Any] | None = None
) -> outcome_spec.OutcomeSpec:
    """REFUSED (#604 R10): a copied bundle is not authority and cannot write or replay state.

    Raises with the exact migration commands; nothing is read from ``bundle`` beyond its schema
    label and nothing is written to the spec path, the store, or any ledger. Cross-clone
    reconstruction is ``attach`` (read-only, from committed spec + GitHub); same-clone mutation
    requires a protected handoff — there is no escape hatch that copies a cache between hosts.
    """
    del repo_root, runner
    schema = bundle.get("schema") if isinstance(bundle, dict) else None
    raise OutcomeError(
        f"legacy bundle import is retired (#604 R10): a copied bundle (schema {schema!r}) "
        "carries no authority. Migrate: run `outcome discover <outcome-id>` in the source "
        "clone to emit the outcome.discovery.v1 envelope; run `outcome attach <outcome-id>` "
        "in this clone for read-only canonical reconstruction; same-clone mutation requires "
        "a protected handoff (`outcome handoff` then `outcome attach --advance`)."
    )


# ---------------------------------------------------------------------------
# graph — Mermaid topology (KTD12 one-glance frontier; full report is U8)
# ---------------------------------------------------------------------------


def graph_mermaid(repo_root: Path, outcome_id: str, *, store: Any | None = None) -> str:
    """A Mermaid flowchart of the DAG annotated with derived live state (KTD12 one-glance topology)."""
    spec = load_spec(repo_root, outcome_id)
    store = store if store is not None else _store(repo_root, outcome_id)
    states = derive_states(spec, store)
    lines = ["flowchart TD"]
    for node in spec.nodes:
        st = states[node.subplot_id]
        lines.append(f'    {node.subplot_id}["{node.subplot_id}: {st}"]')
    for node in spec.nodes:
        for dep in node.depends_on:
            lines.append(f"    {dep} --> {node.subplot_id}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Production harvester — the completion-barrier injector for the live advance loop (U5)
# ---------------------------------------------------------------------------


def production_harvester(
    repo_root: Path,
    *,
    github_runner: Callable[..., Any] | None = None,
    settlement_ledger: run_ledger.RunLedger | None = None,
    now: Callable[[], float] = time.time,
) -> Callable[[Any, Any], list[str]]:
    """Build the harvester ``advance`` runs each tick: it materializes GitHub-canonical completions
    (a merged PR / closed issue) into the store so the frontier unlocks the next Kahn layer (U5).

    Child-outcome nodes (``child_spec_ref``, KTD10) resolve their terminal state by **recursing**
    into the child outcome — load its branch spec, harvest it, and report ``done`` iff every child
    node is success-complete. A ``seen`` set guards against a ``child_spec_ref`` ancestor cycle (the
    deep static cycle check lands with the decompose flow, U7); a missing/unstarted child reads
    ``unknown`` (so the parent waits, never falsely unlocks).
    """
    import outcome_orchestrator

    def child_state_reader(child_id: str, seen: frozenset[str] = frozenset()) -> str:
        if child_id in seen:
            return "unknown"  # ancestor cycle — do not recurse forever
        try:
            child_spec = load_spec(repo_root, child_id)
        except OutcomeError:
            return "unknown"  # child not started yet -> parent keeps waiting
        # NOTE: the store's runner resolves the git-common-dir (NOT GitHub) — it must stay the
        # default git resolver, never the ``github_runner`` (that is only for ``gh`` reads in harvest).
        child_store = _store(repo_root, child_id)
        nxt = seen | {child_id}
        outcome_orchestrator.harvest(
            child_spec,
            store=child_store,
            github_runner=github_runner,
            child_state_reader=lambda cid: child_state_reader(cid, nxt),
            repo_root=repo_root,
        )
        done_set = outcome_store.completed_subplots(child_store)
        all_done = all(n.subplot_id in done_set for n in child_spec.nodes)
        return "done" if all_done else "running"

    def harvester(spec: Any, store: Any) -> list[str]:
        harvested = outcome_orchestrator.harvest(
            spec,
            store=store,
            github_runner=github_runner,
            child_state_reader=child_state_reader,
            repo_root=repo_root,
        )
        if settlement_ledger is not None:
            commits = _dispatch_commit_records(store)
            bindings = dispatch_settlement.outcome_dispatch_bindings(
                settlement_ledger, spec.outcome_id, (node.subplot_id for node in spec.nodes)
            )
            # Reconcile every durable terminal completion on every tick. This closes the
            # completion-written/settlement-write crash gap even when harvest returns no new IDs,
            # including failed/rejected/stalled terminals absent from the success frontier.
            for sid in sorted(bindings):
                binding = bindings.get(sid)
                if binding is None:
                    continue
                events = outcome_store.read_completion_events(store, sid)
                if not events:
                    continue
                completion = events[-1]
                dispatch_id, _unit = binding
                commit_binding = commits.get(sid, {}).get("settlement")
                attempt: int | None = None
                if isinstance(commit_binding, dict) and (
                    commit_binding.get("dispatch_id") == dispatch_id
                    and commit_binding.get("unit_id") == sid
                    and isinstance(commit_binding.get("attempt"), int)
                    and not isinstance(commit_binding.get("attempt"), bool)
                ):
                    attempt = int(commit_binding["attempt"])
                if attempt is None:
                    attempt = dispatch_settlement.latest_attempt(
                        settlement_ledger, dispatch_id=dispatch_id, unit_id=sid
                    )
                if attempt is None:
                    continue
                evidence = completion.to_dict()
                is_success = completion.is_success
                dispatch_settlement.settle_attempt(
                    settlement_ledger,
                    subplot_id=sid,
                    at=dispatch_settlement.iso_at(now()),
                    dispatch_id=dispatch_id,
                    unit_id=sid,
                    attempt=attempt,
                    classification=(
                        dispatch_settlement.DELIVERED
                        if is_success
                        else dispatch_settlement.SILENT_NOOP
                    ),
                    reason=(
                        "outcome parent harvested durable successful completion evidence"
                        if is_success
                        else f"outcome terminal completion fail-closed: {completion.state}"
                    ),
                    # A silent-no-op is intentionally evidence-free in the closed settlement schema:
                    # the durable negative event establishes fail-closed classification, while only a
                    # successful delivery may carry digest-bound delivery evidence.
                    evidence_ref=(f"outcome-completion:{completion.state}" if is_success else ""),
                    evidence_sha256=(
                        dispatch_settlement.evidence_digest(evidence) if is_success else ""
                    ),
                )
        return harvested

    return harvester


def production_merge_processor(
    *,
    github_runner: Callable[..., Any] | None = None,
    repo_root: Path | None = None,
) -> Callable[[Any, Any], Any]:
    """Build the merge processor ``advance`` runs each tick under the held coordinator lease (U6): it
    auto-merges every clean, non-gated, **envelope-authorized** (#449) code leaf (serialized) and
    records GitHub negative terminals. Without a ``ceremony_gates.merge: "auto"`` posture AND one
    active merge token, every leaf ``waits-operator`` — the never-autonomous default is enforced.

    ``repo_root`` (production wiring) makes the merge ceremony read the ON-DISK spec's committed
    intent per authorization, so a mid-tick repost's posture is honored within the same tick; a
    caller that omits it falls back to the tick's in-memory posture (residual documented in
    ``outcome_merge``). An unreadable on-disk spec fails the authorization closed, never the tick.
    """
    import outcome_merge

    ops = outcome_merge.github_merge_ops(github_runner)

    def processor(spec: Any, store: Any) -> Any:
        intent_reader: Callable[[], tuple[dict[str, Any] | None, int]] | None = None
        if repo_root is not None:
            root_now = repo_root
            outcome_id = spec.outcome_id

            def _on_disk_intent() -> tuple[dict[str, Any] | None, int]:
                data = json.loads(spec_path(root_now, outcome_id).read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    raise OutcomeError("on-disk outcome spec is not a JSON object")
                intent = data.get("intent")
                if intent is not None and not isinstance(intent, dict):
                    raise OutcomeError(f"on-disk intent is not an object: {intent!r}")
                revision = data.get("intent_revision", 0)
                if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
                    raise OutcomeError(f"on-disk intent_revision invalid: {revision!r}")
                return (intent, revision)

            intent_reader = _on_disk_intent

        return outcome_merge.process_merge_queue(spec, store, ops, intent_reader=intent_reader)

    return processor


def production_worktree_processor(
    repo_root: Path,
    *,
    runner: Callable[..., Any] | None = None,
    owner: str = "",
    cap: int | None = None,
    lease_authority: Any | None = None,
) -> Callable[[Any, Any], Any]:
    """Build the worktree processor ``advance`` runs each tick under the held coordinator lease (U7):
    it reaps terminal sub-outcomes' worktrees, records the worktree-removed terminal (R32) + cascade,
    and provisions a durable worktree for each dispatched sub-outcome (cap-bounded, R15)."""
    import lease_broker as fleet_leases
    import outcome_worktrees

    ops = outcome_worktrees.git_worktree_ops(repo_root, runner=runner)
    owner = owner or _default_holder()
    wt_cap = cap if cap is not None else outcome_worktrees.WORKTREE_CAP
    selected = fleet_leases.broker() if lease_authority is None else lease_authority

    def processor(spec: Any, store: Any) -> Any:
        leases = outcome_worktrees.reconcile_worktree_leases(
            repo_root,
            spec,
            store,
            ops,
            selected,
            owner=owner,
        )
        harvested = outcome_worktrees.harvest_worktrees(spec, store, ops, lease_authority=selected)
        provisioned = outcome_worktrees.provision_pending(
            repo_root,
            spec,
            store,
            ops,
            owner=owner,
            cap=wt_cap,
            lease_authority=selected,
        )
        return {**leases, **harvested, **provisioned}

    return processor


def production_liveness_processor(
    *, now: Callable[[], float] = time.time
) -> Callable[[Any, Any], Any]:
    """Build the liveness processor ``advance`` runs each tick under the held coordinator lease (U9): it
    reclaims every hung dispatched leaf (breaching its heartbeat/timeout budget) as ``stalled`` (R31)."""
    import outcome_liveness

    def processor(spec: Any, store: Any) -> Any:
        return outcome_liveness.harvest_liveness(spec, store, now=now())

    return processor


def production_cost_processor(repo_root: Path) -> Callable[[Any, Any], Any]:
    """Build the cost processor ``advance`` runs each tick (U10): it materializes the realized-cost
    rollup (R24) into ``spec.cost_rollup`` and persists the spec WHEN the rollup changed, so the U8
    report renders it (the producer -> spec -> consumer edge, no U8->U10 code dependency).

    **Never clobbers a mid-tick repost (#433 M2).** The save runs through ``save_spec``'s
    stale-write guard: when a concurrent ``repost``/``set-intent`` committed a newer revision
    after this tick loaded the spec, the stale save is refused, the NEWER spec is reloaded,
    and the rollup is re-derived from the same ledger and re-applied on top of it — the
    repost's revision bump, envelope change, and decision-trail entry all survive, and the
    tick's record says so loudly (``reapplied_over_stale_revision``). This closes the
    demonstrated lost-update sequence — a stale in-memory spec persisted at tick end erasing
    a committed repost. It does NOT close ``save_spec``'s own check->write race (a writer
    landing between the guard's revision read and its write syscall is still overwritten) —
    that residual is documented on ``save_spec`` and in references/outcome-spec.md, not
    claimed away.
    """
    import outcome_costs

    def processor(spec: Any, store: Any) -> Any:
        changed = outcome_costs.materialize(spec, store)
        if not changed:
            return {"rollup": spec.cost_rollup, "changed": False}
        try:
            save_spec(repo_root, spec)
        except StaleSpecError as exc:
            fresh = load_spec(repo_root, spec.outcome_id)
            rechanged = outcome_costs.materialize(fresh, store)
            if rechanged:
                save_spec(repo_root, fresh)  # a second concurrent bump here fails loudly
            return {
                "rollup": fresh.cost_rollup,
                "changed": rechanged,
                "reapplied_over_stale_revision": spec.spec_revision,
                "spec_revision": fresh.spec_revision,
                "stale_reason": str(exc),
            }
        return {"rollup": spec.cost_rollup, "changed": True}

    return processor


# ---------------------------------------------------------------------------
# CLI — the thin /outcome verbs (KTD11). No I/O at import.
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="OutcomeOrchestrator — thin coordinator verbs.")
    parser.add_argument("--repo-root", default=".")
    sub = parser.add_subparsers(dest="command", required=True)

    p_start = sub.add_parser("start", help="create the branch-local spec + store")
    p_start.add_argument("outcome_id")
    p_start.add_argument("objective", nargs="?", default=None)
    p_start.add_argument(
        "--from-objective",
        metavar="<owner>/<repo>#<N>",
        default=None,
        help="seed the DAG from a GitHub Objective's sub-issues (#375)",
    )
    p_start.add_argument(
        "--intent-file",
        metavar="<envelope.json>",
        default=None,
        help=(
            "a run-start intent envelope to commit on the spec (#380) — e.g. the output of "
            "`intent_envelope.py capture`; wins over an issue-carried envelope"
        ),
    )

    p_set_intent = sub.add_parser(
        "set-intent",
        help="attach a run-start intent envelope to an already-started outcome (#380)",
    )
    p_set_intent.add_argument("outcome_id")
    p_set_intent.add_argument(
        "--intent-file",
        metavar="<envelope.json>",
        required=True,
        help="the captured envelope (e.g. `intent_envelope.py capture` output) to commit",
    )

    p_repost = sub.add_parser(
        "repost",
        help=(
            "renegotiate a LIVE campaign's posture mid-run (#433) — the set_intent renegotiation "
            "form: atomic snapshot→validate→bump_revision→decision_trail; merge/deploy gates move "
            "only toward MORE gating; a loosening repost re-closes the frontier approval"
        ),
    )
    p_repost.add_argument("outcome_id")
    p_repost.add_argument(
        "--scope",
        default="",
        help=(
            "subplot_id — scope the change to ONE leaf (degrade_policy / sandbox); omit for "
            "campaign posture (run_mode / reviews_required / merge / deploy_nonprod)"
        ),
    )
    p_repost.add_argument(
        "--set",
        dest="sets",
        action="append",
        required=True,
        metavar="FIELD=VALUE",
        help="a posture change (repeatable); the field vocabulary is closed per scope",
    )
    p_repost.add_argument(
        "--reason", required=True, help="why posture changed — recorded on the decision trail (R1)"
    )

    p_advance = sub.add_parser("advance", help="run a reconcile tick (dispatch the ready frontier)")
    p_advance.add_argument("outcome_id")
    p_advance.add_argument("--loop", action="store_true")
    p_advance.add_argument(
        "--autonomous",
        action="store_true",
        help="operator is away — an unavailable backend degrades one rung instead of HALTing (R23)",
    )
    p_advance.add_argument(
        "--host-capable",
        action="store_true",
        help="this host can run the forked-context backends (fork/subagent/goal)",
    )
    p_advance.add_argument(
        "--workflow-available",
        action="store_true",
        help="this host can run cc-workflows-ultracode (the Workflow tool is present)",
    )
    p_advance.add_argument(
        "--persist",
        action="store_true",
        help="commit + push the spec to the outcome branch after advancing (R26/R27 durability)",
    )

    for verb in ("resume", "status", "graph"):
        p = sub.add_parser(verb, help=f"{verb} an outcome")
        p.add_argument("outcome_id")

    p_attend = sub.add_parser(
        "attend",
        help="the consolidated attention prompt (R18); with a subplot, the /resume handoff",
    )
    p_attend.add_argument("outcome_id")
    p_attend.add_argument("subplot_id", nargs="?", default=None)

    p_discover = sub.add_parser(
        "discover",
        help="emit the outcome.discovery.v1 envelope from the COMMITTED spec (#604, read-only)",
    )
    p_discover.add_argument("outcome_id")

    p_handoff = sub.add_parser(
        "handoff",
        help="offer a protected one-subplot cross-runtime handoff (#604; closes issuer authority)",
    )
    p_handoff.add_argument("outcome_id")
    p_handoff.add_argument("subplot_id")
    p_handoff.add_argument("--operation", choices=("advance-one", "attend"), required=True)
    p_handoff.add_argument("--attempt", type=int, default=1)
    p_handoff.add_argument("--dispatch-id", default="")
    p_handoff.add_argument("--ttl-seconds", type=int, default=300)
    for flag_parser in (p_handoff,):
        flag_parser.add_argument("--session-id", required=True)
        flag_parser.add_argument("--policy-sha256", required=True)
        flag_parser.add_argument("--session-limit", type=int, required=True)
        flag_parser.add_argument("--aggregate-limit", type=int, required=True)
        flag_parser.add_argument("--broker-root", default=None)

    p_attach = sub.add_parser(
        "attach",
        help="attach to a discovered outcome: read-only canonical status by default; "
        "--advance/--attend require a validated protected handoff (#604)",
    )
    p_attach.add_argument("outcome_id")
    attach_mode = p_attach.add_mutually_exclusive_group()
    attach_mode.add_argument("--advance", action="store_true")
    attach_mode.add_argument("--attend", dest="attach_attend", action="store_true")
    p_attach.add_argument("--handoff-id", default=None)
    p_attach.add_argument("--subplot", default=None)
    p_attach.add_argument("--receiver", default=None)
    p_attach.add_argument("--session-id", default=None)
    p_attach.add_argument("--policy-sha256", default=None)
    p_attach.add_argument("--session-limit", type=int, default=None)
    p_attach.add_argument("--aggregate-limit", type=int, default=None)
    p_attach.add_argument("--broker-root", default=None)

    p_report = sub.add_parser(
        "report", help="regenerate docs/outcomes/<id>/report.md from state (R19)"
    )
    p_report.add_argument("outcome_id")

    p_project = sub.add_parser(
        "project", help="the generated mission-control secondary projection (R25)"
    )
    p_project.add_argument("outcome_id")
    p_project.add_argument("--markdown", action="store_true")

    p_commit = sub.add_parser(
        "commit", help="commit (+ --push) the spec to the outcome's branch (R26/R27 durability)"
    )
    p_commit.add_argument("outcome_id")
    p_commit.add_argument("--push", action="store_true")

    p_export = sub.add_parser(
        "export",
        help="deprecated read-only alias of `discover` (#604 R10); prints the discovery envelope",
    )
    p_export.add_argument("outcome_id")

    p_import = sub.add_parser(
        "import",
        help="retired (#604 R10): always refuses with discover/attach migration guidance",
    )
    p_import.add_argument("path")

    p_approve = sub.add_parser(
        "approve", help="approve the current frontier so it may dispatch (R20)"
    )
    p_approve.add_argument("outcome_id")
    p_approve.add_argument(
        "--answerer",
        default=None,
        help="who answered the gate — provenance for a remote/channel approval (#379)",
    )
    p_approve.add_argument(
        "--transport",
        default=None,
        help="transport the approval arrived over, e.g. redis-channel/discord — provenance (#379)",
    )

    p_prune = sub.add_parser("prune", help="prune a node + reconcile its orphans (R33)")
    p_prune.add_argument("outcome_id")
    p_prune.add_argument("subplot_id")

    p_promote = sub.add_parser("promote", help="promote a subplot to its own child saga (R21)")
    p_promote.add_argument("outcome_id")
    p_promote.add_argument("subplot_id")
    p_promote.add_argument("child_spec_ref")

    p_link_pr = sub.add_parser(
        "link-pr", help="attach a code leaf's merged PR to its node so harvest fires (#495)"
    )
    p_link_pr.add_argument("outcome_id")
    p_link_pr.add_argument("subplot_id")
    p_link_pr.add_argument(
        "pr_url", help="the leaf's PR URL (https://github.com/<owner>/<repo>/pull/<N>)"
    )
    p_link_pr.add_argument(
        "--push",
        action="store_true",
        help="commit the spec to the outcome branch (run on that branch)",
    )

    p_reconcile = sub.add_parser(
        "reconcile",
        help="detect board<->saga drift for this outcome (#295); --resolve to apply a decision",
    )
    p_reconcile.add_argument("outcome_id")
    p_reconcile.add_argument("--project", default="operations")
    p_reconcile.add_argument(
        "--resolve", metavar="DRIFT_ID", help="apply --action to the drift with this id"
    )
    p_reconcile.add_argument(
        "--action", choices=("accept-board", "re-assert", "hold"), help="resolution for --resolve"
    )

    args = parser.parse_args(argv)
    # Resolve the repo root to an absolute, symlink-collapsed path. The default is ``.`` (relative),
    # and a relative/symlinked root would make the worktree registry paths diverge from git's absolute
    # realpath porcelain — reading every live worktree as ABSENT (R15 cap unenforced + R34 false
    # worktree-removed terminals). Canonicalizing here keeps the registry paths == git's view.
    root = Path(args.repo_root).resolve()
    try:
        if args.command == "start":
            intent_file = Path(args.intent_file) if args.intent_file else None
            if args.from_objective:
                owner, repo, number = _parse_objective_ref(args.from_objective)
                nodes, dropped, objective_title, parent_body = nodes_from_objective(
                    owner, repo, number
                )
                objective = args.objective or objective_title or args.from_objective
                # #380: read the issue-authored envelope (skip the run-start interview when a
                # valid one is present; fall back to asking when absent or invalid).
                resolution = resolve_start_intent(parent_body, intent_file)
                spec = start(
                    root, args.outcome_id, objective, nodes=nodes, intent=resolution["intent"]
                )
                if dropped:
                    print(json.dumps({"dropped_edges": dropped}), file=sys.stderr)
            else:
                if not args.objective:
                    raise OutcomeError("start requires an objective (or --from-objective)")
                resolution = resolve_start_intent(None, intent_file)
                spec = start(root, args.outcome_id, args.objective, intent=resolution["intent"])
            print(
                json.dumps(
                    {
                        "started": spec.outcome_id,
                        "nodes": len(spec.nodes),
                        "intent_source": resolution["intent_source"],
                        "interview_required": resolution["interview_required"],
                        "interview_reason": resolution["interview_reason"],
                    }
                )
            )
        elif args.command == "set-intent":
            spec = set_intent(root, args.outcome_id, Path(args.intent_file))
            print(
                json.dumps(
                    {
                        "outcome_id": spec.outcome_id,
                        "intent_source": "file",
                        "spec_revision": spec.spec_revision,
                    }
                )
            )
        elif args.command == "repost":
            spec = load_spec(root, args.outcome_id)
            store = _store(root, args.outcome_id)
            repost_result = outcome_intent.repost(
                spec,
                store,
                changes=outcome_intent.parse_set_args(args.sets),
                scope=args.scope,
                reason=args.reason,
                envelope_path=adjustment_envelope.default_envelope_path(root),
            )
            # Persist ONLY after the atomic mutation succeeded — a rejected/stranded repost
            # raises above and the on-disk spec stays byte-identical (R2).
            save_spec(root, spec)
            print(json.dumps(repost_result.to_dict()))
        elif args.command == "advance":
            # The production /outcome advance routes through the REAL backend seam (R5/R6), the REAL
            # completion barrier (U5, harvester), the REAL auto-merge queue (U6, merge_processor), the
            # REAL worktree lifecycle (U7, worktree_processor), the REAL approval gate (U7, gate_factory),
            # the REAL liveness reclaim (U9, liveness_processor: hung leaf -> stalled), and the REAL
            # presence-conditional degrade decision (U9, available + attending): an unavailable backend
            # HALTs when attended/guaranteed/side-effected, else degrades one rung when --autonomous.
            import outcome_decompose

            avail = outcome_dispatcher.resolve_available(
                host_capable=args.host_capable, workflow_available=args.workflow_available
            )
            settlement_ledger = run_ledger.RunLedger.resolve(root)
            # The dispatcher mints any backend the degrade decision resolves to (it never halts here —
            # _reconcile_once owns the HALT/degrade decision via degrade_decision with `avail`).
            result = advance(
                root,
                args.outcome_id,
                loop=args.loop,
                dispatcher=outcome_dispatcher.make_dispatcher(
                    available=outcome_spec.NODE_BACKENDS,
                    lease_authority=outcome_dispatcher.default_lease_authority(),
                ),
                harvester=production_harvester(root, settlement_ledger=settlement_ledger),
                merge_processor=production_merge_processor(repo_root=root),
                worktree_processor=production_worktree_processor(root),
                liveness_processor=production_liveness_processor(),
                cost_processor=production_cost_processor(root),
                gate_factory=lambda spec, store: outcome_decompose.make_dispatch_gate(store, spec),
                available=avail,
                attending=not args.autonomous,
                autonomous=args.autonomous,
                settlement_ledger=settlement_ledger,
            )
            out = result.to_dict()
            if args.persist:
                # R26/R27: commit + push the (possibly cost-rollup-mutated) spec to the outcome branch so
                # a different machine can pull-and-reconstruct (refuses on main; no-op if unchanged).
                out["persisted"] = commit_spec(root, args.outcome_id, push=True)
            print(json.dumps(out))
        elif args.command == "commit":
            print(json.dumps(commit_spec(root, args.outcome_id, push=args.push)))
        elif args.command == "approve":
            import outcome_decompose

            spec = load_spec(root, args.outcome_id)
            store = _store(root, args.outcome_id)
            rev = outcome_decompose.approve_frontier(
                store, spec, answerer=args.answerer, transport=args.transport
            )
            print(
                json.dumps(
                    {
                        "approved_revision": rev,
                        "outcome_id": spec.outcome_id,
                        "answerer": args.answerer,
                        "transport": args.transport,
                    }
                )
            )
        elif args.command == "prune":
            import outcome_decompose
            import outcome_worktrees

            spec = load_spec(root, args.outcome_id)
            store = _store(root, args.outcome_id)
            # The worktree reap is wired to the real git adapter. U8's projection is artifact-only (it
            # generates the secondary view, it does NOT create GitHub sub-issues), so there is no
            # generated sub-issue to close yet; the sub-issue close adapter is deferred to a later
            # operator-initiated mission-control consumer, so issue_close stays None until then.
            summary = outcome_decompose.prune(
                spec,
                store,
                args.subplot_id,
                worktree_ops=outcome_worktrees.git_worktree_ops(root),
                lease_authority=outcome_dispatcher.default_lease_authority(),
            )
            save_spec(root, spec)
            print(json.dumps(summary))
        elif args.command == "promote":
            import outcome_decompose

            spec = load_spec(root, args.outcome_id)
            rev = outcome_decompose.promote(spec, args.subplot_id, args.child_spec_ref)
            save_spec(root, spec)
            print(json.dumps({"promoted": args.subplot_id, "spec_revision": rev}))
        elif args.command == "link-pr":
            print(
                json.dumps(
                    link_pr(root, args.outcome_id, args.subplot_id, args.pr_url, push=args.push)
                )
            )
        elif args.command == "resume":
            print(json.dumps(resume(root, args.outcome_id)))
        elif args.command == "status":
            print(json.dumps(status(root, args.outcome_id)))
        elif args.command == "graph":
            print(graph_mermaid(root, args.outcome_id))
        elif args.command in ("discover", "handoff", "attach"):
            import outcome_compat

            try:
                if args.command == "discover":
                    envelope = outcome_compat.build_discovery_envelope(
                        root, args.outcome_id, saga_version=_saga_version()
                    )
                    print(outcome_compat.canonical_json(envelope))
                elif args.command == "handoff":
                    broker = _cli_broker(args.broker_root)
                    admission = _cli_admission(args)
                    identity = outcome_compat.repository_identity(root)
                    lease = broker.acquire_agent(
                        owner_id=f"outcome-handoff-{os.getpid()}-{time.monotonic_ns()}",
                        session_id=admission["session_id"],
                        policy_sha256=admission["policy_sha256"],
                        session_limit=admission["session_limit"],
                        aggregate_limit=admission["aggregate_limit"],
                        mutation="read-write",
                        resource_ref=outcome_compat.outcome_dispatch_resource(
                            identity, args.outcome_id, args.subplot_id, args.attempt
                        ),
                    )
                    _offer, reference = outcome_compat.offer_handoff(
                        root,
                        args.outcome_id,
                        args.subplot_id,
                        operation=args.operation,
                        attempt=args.attempt,
                        broker=broker,
                        lease=lease,
                        dispatch_id=args.dispatch_id,
                        ttl_seconds=args.ttl_seconds,
                    )
                    print(outcome_compat.canonical_json(reference))
                else:  # attach
                    if args.advance or args.attach_attend:
                        if not args.handoff_id or not args.subplot:
                            raise OutcomeError(
                                "attach --advance/--attend requires --handoff-id and --subplot"
                            )
                        broker = _cli_broker(args.broker_root)
                        admission = _cli_admission(args)
                        receiver = args.receiver or (
                            f"outcome-attach-{os.getpid()}-{time.monotonic_ns()}"
                        )
                        if args.advance:
                            outcome_result = attached_advance(
                                root,
                                args.outcome_id,
                                args.subplot,
                                handoff_id=args.handoff_id,
                                receiver_owner_id=receiver,
                                admission=admission,
                                broker=broker,
                                settled_lookup=_settled_lookup(root),
                            )
                            print(json.dumps(outcome_result))
                        else:
                            print(
                                attended_handoff(
                                    root,
                                    args.outcome_id,
                                    args.subplot,
                                    handoff_id=args.handoff_id,
                                    receiver_owner_id=receiver,
                                    admission=admission,
                                    broker=broker,
                                )
                            )
                    else:
                        canonical = outcome_compat.build_canonical_status(root, args.outcome_id)
                        print(outcome_compat.canonical_json(canonical))
            except outcome_compat.CompatibilityHaltError as halt:
                print(json.dumps(halt.receipt()))
                return 3
            except _cli_broker_error() as exc:
                # A broker rejection (capacity, policy, registry) is an operational failure of
                # this clone's coordination authority, not a cross-runtime compatibility halt —
                # exit 1 with the standard structured error, never a bare traceback.
                print(
                    json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}),
                    file=sys.stderr,
                )
                return 1
        elif args.command == "attend":
            if args.subplot_id:
                print(attend(root, args.outcome_id, args.subplot_id))
            else:
                # No subplot -> the single consolidated attention prompt (R18), one ranked page.
                import outcome_report

                spec = load_spec(root, args.outcome_id)
                store = _store(root, args.outcome_id)
                print(outcome_report.consolidated_prompt(outcome_report.consolidate(spec, store)))
        elif args.command == "report":
            import outcome_report

            path = outcome_report.write_report(root, args.outcome_id)
            print(json.dumps({"report": str(path)}))
        elif args.command == "project":
            import outcome_projection

            spec = load_spec(root, args.outcome_id)
            store = _store(root, args.outcome_id)
            if args.markdown:
                print(outcome_projection.projection_markdown(spec, store), end="")
            else:
                print(json.dumps(outcome_projection.project(spec, store)))
        elif args.command == "export":
            import outcome_compat

            print(
                "WARNING: `outcome export` is a deprecated alias of `outcome discover` "
                "(#604 R10); the outcome-bundle/1 authority path is retired.",
                file=sys.stderr,
            )
            try:
                print(outcome_compat.canonical_json(export_bundle(root, args.outcome_id)))
            except outcome_compat.CompatibilityHaltError as halt:
                print(json.dumps(halt.receipt()))
                return 3
        elif args.command == "import":
            bundle = json.loads(Path(args.path).read_text(encoding="utf-8"))
            # Unconditionally refuses (#604 R10); the top-level handler prints the refusal
            # receipt. No success path exists.
            import_bundle(root, bundle)
        elif args.command == "reconcile":
            # #295 U5: explicit board<->saga drift detection (read-only on the world; no lease).
            import outcome_github
            import outcome_reconcile

            spec = load_spec(root, args.outcome_id)
            store = _store(root, args.outcome_id)

            def _br(ref: str) -> str:
                return outcome_github.board_status(ref, project=args.project)

            drift = outcome_reconcile.detect(
                spec,
                store,
                board_reader=_br,
                issue_reader=outcome_github.issue_close_info,
                project=args.project,
            )
            if args.resolve:
                if not args.action:
                    raise OutcomeError("--resolve requires --action")
                match = next((d for d in drift if d.get("drift_id") == args.resolve), None)
                if match is None:
                    print(
                        json.dumps({"ok": False, "error": f"no live drift id {args.resolve!r}"}),
                        file=sys.stderr,
                    )
                    return 1
                writer = _default_board_writer(root, project=args.project)
                resolved = outcome_reconcile.apply_resolution(
                    match, args.action, store=store, board_writer=writer
                )
                print(json.dumps({"resolved": resolved}))
            else:
                print(json.dumps({"drift": drift}))
    except (OutcomeError, outcome_spec.OutcomeSpecError, outcome_store.OutcomeStoreError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1
    except ValueError as exc:
        # DecomposeError / WorktreeError (both ValueError subclasses) — a rejected edit / worktree op.
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
