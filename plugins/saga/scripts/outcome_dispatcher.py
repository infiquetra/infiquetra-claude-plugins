#!/usr/bin/env python3
"""OutcomeOrchestrator dispatcher seam — route a leaf to its backend (U4).

This is the **single dispatcher seam** every subplot routes through (R5). It is the outcome-layer
counterpart to ``execution_spec.recompile_for_tier`` (the by-mode emitter fork, now extended with the
``team_emitter`` third leg): given a leaf and its chosen backend, it either **dispatches** — minting a
leaf saga id and a ``/resume`` return channel (the R9 bidirectional envelope's re-entry token out) —
or, when the backend cannot actually run, emits a **visible HALT-not-degrade receipt** (R5/R23) rather
than silently substituting a lesser backend.

U4 made **team-execution the first real backend** (R6); **U9 completes the menu** (R6): ``resolve_available``
exposes the full host-conditional set (the always-available floor inline / team-execution / manual + the
host-dependent fork / subagent / cc-workflows-ultracode / goal), and ``degrade_decision`` is the
**presence-conditional degrade policy** (R23/AE1) — an unavailable backend HALTs when the operator is
attending / the leaf is guarantee-bearing / it already side-effected, else degrades **one rung** down the
``DEGRADE_LADDER`` (recording a visible :class:`DegradeReceipt`) when the leaf is autonomous and the
operator is away. ``recommend_outcome_backend`` adds the R7 frontier-budget + fork-cost levers, and
``outcome_liveness`` (a sibling module) enforces the R31 heartbeat/timeout ``stalled`` terminal.

``make_dispatcher`` returns a ``Dispatcher`` (the callable ``outcome.advance`` consumes): it mints the
leaf saga id (the production loop gives it the full menu so it never HALTs — ``outcome._reconcile_once``
owns the HALT/degrade decision via ``degrade_decision``); it still raises ``BackendHaltError`` for a
restricted/unit caller, which the reconcile loop records as a HALT.

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

import execution_spec  # noqa: E402  (after the sys.path shim, by design)
import intent_envelope  # noqa: E402  (the #373 run-start posture schema, by design)
import outcome_spec  # noqa: E402  (after the sys.path shim, by design)

# The always-available floor (R6): the agent can always run inline, emit a team-execution artifact, or
# hand a leaf to the operator (manual). The host-dependent backends (fork / subagent /
# cc-workflows-ultracode / goal) are only available when the host advertises them (KTD9) — the
# coordinator is a Python script that cannot itself probe the Claude Code host, so they stay OFF by
# default and an unavailable choice HALTs or DEGRADES (R23), never a silent substitution (R5).
ALWAYS_AVAILABLE: tuple[str, ...] = ("inline", "team-execution", "manual")
HOST_DEPENDENT: frozenset[str] = frozenset({"fork", "subagent", "cc-workflows-ultracode", "goal"})
DEFAULT_AVAILABLE: tuple[str, ...] = ALWAYS_AVAILABLE

# The capability ladder degrade walks DOWN (R23): most-capable dynamic workflows -> review-gated
# team-execution -> the always-runnable inline floor. A backend NOT on this ladder
# (fork/subagent/goal/manual) has no defined lower rung, so an unavailable one HALTs rather than
# silently substituting (R5). Mirrors lifecycle_state.ORCHESTRATION_TIERS.
DEGRADE_LADDER: tuple[str, ...] = ("cc-workflows-ultracode", "team-execution", "inline")


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
    # #433 R8: a POSTURE-caused gate HALT (the leaf halts because the current posture requires
    # the operator — attending / guarantee-bearing / already-side-effected under
    # HALT-not-degrade) carries the scoped-repose resolution option: renegotiate THIS leaf's
    # posture via ``outcome repost --scope <subplot>``, not the whole campaign's. ``None``
    # (an availability-caused halt, or a pre-#433 producer) emits no key — receipt shapes
    # for every existing producer stay byte-identical.
    scoped_repose: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "kind": "halt",
            "outcome_id": self.outcome_id,
            "subplot_id": self.subplot_id,
            "backend": self.backend,
            "reason": self.reason,
            "available": list(self.available),
        }
        if self.scoped_repose is not None:
            out["scoped_repose"] = dict(self.scoped_repose)
        return out


class BackendHaltError(Exception):
    """A backend HALT (R5/R23): the chosen backend cannot run. Carries the :class:`HaltReceipt`.

    Owned by this backend module (never run as ``__main__``), so the engine's reconcile loop and this
    dispatcher reference the SAME class regardless of how the engine is launched — the per-leaf
    ``except`` in ``outcome._reconcile_once`` reliably catches it.
    """

    def __init__(self, receipt: HaltReceipt) -> None:
        super().__init__(receipt.reason)
        self.receipt = receipt


@dataclass(frozen=True)
class RateLimitReceipt:
    """A visible record that a chosen backend was RATE-LIMITED (HTTP 429) during dispatch.

    Unlike a :class:`HaltReceipt` (backend down -> operator attention), a rate-limit is TRANSIENT:
    the coordinator re-picks the leaf on the next advance tick with no operator action (#348 KTD4).
    ``retry_after`` carries the backend's Retry-After hint (seconds) when known, mirroring the
    fleet-commons ``retry_backoff`` primitive's ``retry_after`` seam.
    """

    outcome_id: str
    subplot_id: str
    backend: str
    reason: str
    retry_after: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "rate_limited",
            "outcome_id": self.outcome_id,
            "subplot_id": self.subplot_id,
            "backend": self.backend,
            "reason": self.reason,
            "retry_after": self.retry_after,
        }


class BackendRateLimitError(Exception):
    """A backend 429 during dispatch (#348 KTD4): TRANSIENT, not a HALT. Carries the receipt.

    Owned by this backend module (never run as ``__main__``) so ``outcome._reconcile_once``'s
    per-leaf ``except`` catches the SAME class regardless of how the engine is launched -- the same
    identity discipline as :class:`BackendHaltError`. A 429'd dispatch leaves NO commit record, so
    the leaf's derived state stays ``ready`` and the ready frontier re-picks it; ``retriable-pending``
    is a derived-on-read RESULT label, never a committed ``NODE_STATE``.
    """

    def __init__(self, receipt: RateLimitReceipt) -> None:
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
    # Sandbox enforceability probe (#287 U3, R4): the resolved backend must be able to enforce the
    # leaf's declared containment. If it cannot, HALT with the axis named rather than silently
    # running the leaf without the requested sandbox. Duck-typed ``sandbox`` (a Node carries it as
    # of #287 U1; older reqs simply lack it) keeps this backward compatible.
    offending = execution_spec.unenforceable_sandbox_axis(backend, getattr(req, "sandbox", None))
    if offending is not None:
        axis_name, axis_value = offending
        receipt = HaltReceipt(
            outcome_id=str(req.outcome_id),
            subplot_id=str(req.subplot_id),
            backend=backend,
            reason=(
                f"backend {backend!r} cannot enforce sandbox {axis_name}={axis_value!r} "
                f"(#287 R4 halt-not-downgrade) -- it would run the leaf without the requested "
                f"containment. HALT and page rather than silently drop the sandbox."
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
        # #348 KTD4: a ``rate_limited`` dispatch result surfaces as a TRANSIENT 429, distinct from a
        # HALT. No in-scope backend emits this status yet (agy/codex bridge adoption is deferred per
        # KTD2 -- the fleet-commons primitive is import-ready); this translation makes the production
        # dispatcher CAPABLE the instant a backend returns it, mirroring the halt branch.
        if result["status"] == "rate_limited":
            raise BackendRateLimitError(RateLimitReceipt(**_rate_limit_kwargs(result["receipt"])))
        return str(result["leaf_saga_id"])

    return _dispatch


def _receipt_kwargs(receipt: dict[str, Any]) -> dict[str, Any]:
    return {
        "outcome_id": receipt["outcome_id"],
        "subplot_id": receipt["subplot_id"],
        "backend": receipt["backend"],
        "reason": receipt["reason"],
        "available": tuple(receipt["available"]),
        "scoped_repose": receipt.get("scoped_repose"),
    }


def _rate_limit_kwargs(receipt: dict[str, Any]) -> dict[str, Any]:
    return {
        "outcome_id": receipt["outcome_id"],
        "subplot_id": receipt["subplot_id"],
        "backend": receipt["backend"],
        "reason": receipt["reason"],
        "retry_after": receipt.get("retry_after"),
    }


# ---------------------------------------------------------------------------
# team-execution artifact (R5 — wiring the existing team_emitter)
# ---------------------------------------------------------------------------


def team_execution_artifact(execution_spec_obj: Any) -> str:
    """Emit the team-execution ``## Team Structure`` markdown for a leaf's execution spec (R5).

    Delegates to ``execution_spec.recompile_for_tier(spec, "team-execution")`` — the by-mode
    dispatcher seam whose third leg is ``team_emitter`` — so the team-execution backend's runnable
    artifact is produced through the single seam, not reinvented here. Uses the module-level
    ``execution_spec`` import (loaded under the sys.path shim) so this and ``team_emitter`` reach the
    SAME class objects — a fresh per-call ``exec_module`` would mint a second ``SpecError`` that an
    upstream ``except`` misses (the #287 U3 dynamic-reload identity trap).
    """
    return str(execution_spec.recompile_for_tier(execution_spec_obj, "team-execution"))


# ---------------------------------------------------------------------------
# Full backend menu + the presence-conditional degrade decision (U9 — R6/R23/AE1)
# ---------------------------------------------------------------------------


def resolve_available(
    *, host_capable: bool = False, workflow_available: bool = False
) -> tuple[str, ...]:
    """The runnable backend set for this host (R6), ordered by the spec's ``NODE_BACKENDS`` vocabulary.

    ``ALWAYS_AVAILABLE`` (inline / team-execution / manual) is unconditional. ``host_capable`` enables
    the forked-context backends (``fork`` / ``subagent`` / ``goal``); ``workflow_available`` additionally
    enables ``cc-workflows-ultracode``. The conservative default (both False) is the always-available
    floor — the coordinator never claims a host-dependent backend it cannot verify.
    """
    avail = set(ALWAYS_AVAILABLE)
    if host_capable:
        avail |= {"fork", "subagent", "goal"}
    if host_capable and workflow_available:
        avail.add("cc-workflows-ultracode")
    return tuple(b for b in outcome_spec.NODE_BACKENDS if b in avail)


def scoped_repose_option(outcome_id: str, subplot_id: str) -> dict[str, Any]:
    """The scoped-repose resolution option a POSTURE-caused gate HALT carries (#433 R8/R9).

    Attached by the reconcile loop when a leaf HALTs because the current posture requires the
    operator (attending / guarantee-bearing / already-side-effected under HALT-not-degrade) —
    never for an availability-caused halt (no lower rung / backend down), which posture cannot
    resolve. The option is an *offer*, not a mechanism that acts: the leaf stays halted until
    the operator explicitly runs the scoped ``repost`` (and re-approves, when it loosens) or
    explicitly leaves it halted. There is no default and no timeout — silence is never consent
    (R9); the halt is simply re-derived on every later tick until the operator selects.
    """
    return {
        "scope": subplot_id,
        "verb": "repost",
        "hint": (
            f"python3 plugins/saga/scripts/outcome.py repost {outcome_id} "
            f"--scope {subplot_id} --set degrade_policy=<policy>|sandbox=<profile> "
            f"--reason <why> — resolves THIS leaf's posture only, never the whole campaign's"
        ),
        "resolution": "explicit-operator-selection",
    }


def is_guarantee_bearing(node: Any) -> bool:
    """A leaf that must HALT rather than degrade (R23): it carries guarantee tags OR opts into the
    ``halt`` degrade policy. Such a leaf never silently runs on a lesser backend, even autonomous + away.
    """
    return (
        bool(getattr(node, "guarantee_tags", None)) or getattr(node, "degrade_policy", "") == "halt"
    )


@dataclass(frozen=True)
class DegradeReceipt:
    """A visible record that an autonomous, away leaf was DEGRADED one rung (R23) — surfaced in the report."""

    outcome_id: str
    subplot_id: str
    from_backend: str
    to_backend: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "degrade",
            "outcome_id": self.outcome_id,
            "subplot_id": self.subplot_id,
            "from_backend": self.from_backend,
            "to_backend": self.to_backend,
            "reason": self.reason,
        }


def degrade_decision(
    backend: str,
    *,
    available: Sequence[str],
    attending: bool,
    guarantee_bearing: bool,
    had_side_effect: bool,
) -> tuple[str, str, str]:
    """The presence-conditional degrade decision (R23/AE1). Returns ``(action, backend, reason)`` where
    ``action`` is ``dispatch`` (run on ``backend``) / ``degrade`` (run on the returned lower rung) /
    ``halt`` (page the operator, never substitute).

    * backend **available** -> ``dispatch`` on it.
    * **operator attending** the leaf -> ``halt`` (the operator decides; never auto-degrade under their nose).
    * **guarantee-bearing** -> ``halt`` even when away (never run a guaranteed leaf on a lesser backend).
    * **already side-effected** (a destructive leaf: deploy/migration/write/repo-mutation) -> ``halt``,
      never re-run on a lesser backend (R23 no-duplicate-side-effect).
    * else (autonomous + away + no guarantee + no side effect) -> ``degrade`` to the first AVAILABLE
      lower rung of the ``DEGRADE_LADDER``; if ``backend`` is not on the ladder, or no lower rung is
      available -> ``halt`` (no silent substitution, R5).
    """
    avail = set(available)
    if backend in avail:
        return ("dispatch", backend, "")
    if attending:
        return (
            "halt",
            backend,
            f"{backend} unavailable and the operator is attending -> HALT + page (R23)",
        )
    if guarantee_bearing:
        return (
            "halt",
            backend,
            f"{backend} unavailable but the leaf is guarantee-bearing -> HALT even when away (R23)",
        )
    import reversibility_certificate  # lazy, mirrors lifecycle_state idiom; certificate is the authority (R10, R11)

    side_effected = reversibility_certificate.side_effected(had_side_effect)
    if side_effected:
        return (
            "halt",
            backend,
            f"{backend} unavailable after a side effect -> HALT, never re-run on a lesser backend (R23)",
        )
    if backend in DEGRADE_LADDER:
        below = DEGRADE_LADDER[DEGRADE_LADDER.index(backend) + 1 :]
        for lower in below:
            if lower in avail:
                return (
                    "degrade",
                    lower,
                    f"{backend} unavailable; autonomous + away -> degraded to {lower} (R23)",
                )
    return (
        "halt",
        backend,
        f"{backend} unavailable and no lower rung is available -> HALT (no silent substitution, R5)",
    )


# ---------------------------------------------------------------------------
# Captured run-start posture — the #373 intent-envelope consumers at the seam
# (T8-F6-8 backends/degrade + T8-F5-7 spend). The posture is captured ONCE on
# the spec's committed intent envelope and CONSUMED here; the HALT/degrade
# decision itself stays derived at dispatch time by the unchanged
# ``degrade_decision`` machinery above, exactly per the U1-U11 register row
# (derived-on-read, HALT-not-degrade, backend menu off-by-default).
# ---------------------------------------------------------------------------


def captured_posture(intent: Any) -> Any | None:
    """Parse a spec's committed intent envelope (#373) — ``None`` when no intent is committed.

    Returns the validated :class:`intent_envelope.IntentEnvelope` (fail closed on a malformed
    dict — ``OutcomeSpec.validate`` already rejects one on every normal path, so a raise here
    means the caller bypassed the spec house). The caller reads ``backends_permitted`` /
    ``degrade_policy`` / ``spend_envelope`` off it; a pre-#373 envelope carries none of them
    and every consumer below treats that as "posture not captured" (behavior unchanged).
    """
    if intent is None:
        return None
    return intent_envelope.IntentEnvelope.from_dict(intent)


def effective_available(
    backends_permitted: Sequence[str] | None, available: Sequence[str] | None
) -> tuple[str, ...] | None:
    """The run's effective backend menu: captured-permitted ∩ runtime-available (#373 AC1).

    The captured half is the run-start authorization (what the operator permitted, once); the
    runtime half stays the per-call host truth (KTD9 — the coordinator cannot self-probe host
    availability, so ``--host-capable``/``--workflow-available`` remain runtime inputs). The
    intersection can only NARROW: a captured backend the host cannot run is not effective, and
    a host-available backend the envelope did not permit is not effective. ``None``/``None``
    means no availability decision exists at all (the legacy direct-dispatch path). Ordered by
    the spec's ``NODE_BACKENDS`` vocabulary for deterministic receipts.
    """
    if backends_permitted is None and available is None:
        return None
    if backends_permitted is None:
        return tuple(b for b in outcome_spec.NODE_BACKENDS if b in set(available or ()))
    if available is None:
        return tuple(b for b in outcome_spec.NODE_BACKENDS if b in set(backends_permitted))
    both = set(backends_permitted) & set(available)
    return tuple(b for b in outcome_spec.NODE_BACKENDS if b in both)


def captured_degrade_decision(
    backend: str,
    *,
    effective: Sequence[str] | None,
    degrade_policy: str,
    attending: bool,
    guarantee_bearing: bool,
    had_side_effect: bool,
) -> tuple[str, str, str]:
    """Feed the captured run-start posture into the EXISTING degrade machinery (#373 AC1-AC3).

    Returns the same ``(action, backend, reason)`` contract as :func:`degrade_decision`.
    This function REUSES ``degrade_decision`` — it never re-implements the presence
    conditions; it only restricts the inputs to what the captured posture permits:

    * ``backend`` in the effective menu -> ``dispatch`` (unchanged).
    * Unmet backend + no permissive captured posture (``degrade_policy`` absent or
      ``halt``) -> ``halt`` by default (AC2) — the run never substitutes without an
      explicit, captured permission.
    * Unmet backend + ``operator_away_one_rung`` -> the available set handed to
      ``degrade_decision`` is restricted to the IMMEDIATE lower ``DEGRADE_LADDER`` rung
      only, so the unchanged mechanism can degrade AT MOST one rung and then HALTs —
      a two-rung-unavailable scenario halts instead of silently cascading (AC3), and
      every presence condition (attending / guarantee-bearing / side-effected -> HALT)
      still decides exactly as before.

    ``effective=None`` means no availability decision exists (no captured set and no runtime
    set): there is nothing to enforce, so the leaf dispatches on its declared backend.
    """
    if effective is None:
        return ("dispatch", backend, "")
    avail = set(effective)
    if backend in avail:
        return ("dispatch", backend, "")
    if degrade_policy != intent_envelope.INTENT_DEGRADE_ONE_RUNG:
        return (
            "halt",
            backend,
            f"{backend} is not in the run's effective backend menu {tuple(effective)} and the "
            f"captured run-start posture permits no degrade (degrade_policy="
            f"{degrade_policy or 'not captured'}) -> HALT by default (#373, R5/R23)",
        )
    if backend in DEGRADE_LADDER:
        idx = DEGRADE_LADDER.index(backend)
        one_rung = set(DEGRADE_LADDER[idx + 1 : idx + 2])
    else:
        one_rung = set()  # off-ladder backends have no defined lower rung -> HALT below
    restricted = tuple(b for b in effective if b in one_rung)
    return degrade_decision(
        backend,
        available=restricted,
        attending=attending,
        guarantee_bearing=guarantee_bearing,
        had_side_effect=had_side_effect,
    )


@dataclass(frozen=True)
class SpendHaltReceipt:
    """A visible record that a leaf's dispatch was DENIED by the captured spend envelope (#373).

    Distinct from :class:`HaltReceipt` (backend unavailability) and from the degrade path:
    spend gating is HALT-only — an over-ceiling or tier-escalating leaf pauses for explicit
    step-up authorization and is NEVER silently run at a lower tier (T8-F5-7). The receipt
    echoes the compared values so the operator sees exactly what tripped — surfaced per-tick
    in the advance output (``AdvanceResult.halted``) and durably on the ``spend:<sid>`` ledger
    lane. The consolidated report's ambiguity tier does not yet render halt receipts (it
    filters on ``kind == "dispatch"``; backend halts on main are equally invisible there).
    """

    outcome_id: str
    subplot_id: str
    backend: str
    reason: str
    tier_ceiling: str = ""
    cost_ceiling_tokens: float | None = None
    requested_tier: str | None = None
    actual_tokens: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "spend-halt",
            "outcome_id": self.outcome_id,
            "subplot_id": self.subplot_id,
            "backend": self.backend,
            "reason": self.reason,
            "tier_ceiling": self.tier_ceiling,
            "cost_ceiling_tokens": self.cost_ceiling_tokens,
            "requested_tier": self.requested_tier,
            "actual_tokens": self.actual_tokens,
        }


class SpendHaltError(Exception):
    """A spend-gate HALT (#373): the dispatch needs explicit step-up authorization.

    Owned by this backend module (never run as ``__main__``) for the same class-identity
    discipline as :class:`BackendHaltError`. Deliberately NOT a ``BackendHaltError`` subclass:
    the spend gate is a distinct code path from the backend-menu HALT/degrade — a caller
    handling backend unavailability must not accidentally swallow a spend denial.
    """

    def __init__(self, receipt: SpendHaltReceipt) -> None:
        super().__init__(receipt.reason)
        self.receipt = receipt


def authorize_dispatch_spend(
    spend: Any,
    *,
    outcome_id: str,
    subplot_id: str,
    backend: str,
    requested_tier: str | None = None,
    actual_tokens: float | None = None,
) -> None:
    """The #373 pre-dispatch spend-authorization check at the seam — raises on denial.

    Resolves the pure decision through the canonical ``intent_envelope.authorize_spend``
    (tier ceiling vs the leaf's declared tier; cost ceiling vs ``outcome_costs``'s
    leaf-produced cumulative actuals) and raises a typed :class:`SpendHaltError` carrying a
    :class:`SpendHaltReceipt` when the dispatch is not authorized. Authorization is silent
    (returns ``None``) — an under-ceiling dispatch clears with no receipt and no interrupt
    (AC5). ``spend=None`` (no captured spend envelope) is a no-op: pre-#373 behavior.
    """
    if spend is None:
        return
    decision = intent_envelope.authorize_spend(
        spend, actual_tokens=actual_tokens, requested_tier=requested_tier
    )
    if decision.authorized:
        return
    raise SpendHaltError(
        SpendHaltReceipt(
            outcome_id=outcome_id,
            subplot_id=subplot_id,
            backend=backend,
            reason=decision.reason,
            tier_ceiling=decision.tier_ceiling,
            cost_ceiling_tokens=decision.cost_ceiling_tokens,
            requested_tier=decision.requested_tier,
            actual_tokens=decision.actual_tokens,
        )
    )


def fork_is_cheap(
    *, model_matches: bool, system_matches: bool, tools_match: bool, within_ttl: bool
) -> bool:
    """Whether the ``fork`` cost lever is actually cheap (R7 / the operator-choice fork note).

    A fork only shares the parent's warm prompt cache — and is therefore the cheap option — when the
    child's **model + system prompt + tools** all match the parent AND the request is **within the cache
    TTL**. If any differs, the fork pays a full cache miss and must NOT be claimed as cheap.
    """
    return model_matches and system_matches and tools_match and within_ttl


# How wide the ready frontier must be before per-leaf dynamic workflows become a budget concern (R7).
_FRONTIER_BUDGET_THRESHOLD = 5


def recommend_outcome_backend(
    *,
    frontier_width: int = 1,
    fork_candidate: bool = False,
    fork_signals: dict[str, bool] | None = None,
    **leaf_signals: Any,
) -> dict[str, Any]:
    """Outcome-level backend recommender (R7): wraps the leaf recommender with two outcome concerns.

    1. **Fork cost lever** — when the caller offers ``fork`` as a candidate, recommend it ONLY if
       :func:`fork_is_cheap` holds for ``fork_signals``; otherwise fall through so a cache-missing fork is
       never claimed as the cheap option.
    2. **Frontier-budget awareness** — a wide ready frontier (``frontier_width`` above the threshold)
       makes a dynamic workflow *per leaf* expensive, so a ``cc-workflows-ultracode`` recommendation is
       downgraded to ``team-execution`` with a ``budget_note`` (escalation stays one keystroke via
       ``alternatives``). A narrow frontier is unaffected.
    """
    import lifecycle_state

    if fork_candidate and fork_signals is not None and fork_is_cheap(**fork_signals):
        # Intentionally reduced shape: `fork` is an /outcome-internal verdict outside the
        # three-backend offer vocabulary, so this dict carries no `backends` /
        # `workflow_availability` enumeration (KTD4 applies to the recommender passthrough
        # below, not to the fork fast-path). Consumers must not read `backends`
        # unconditionally off this function's result.
        return {
            "recommended": "fork",
            "rationale": "fork shares the parent's warm cache (model+system+tools match within TTL) -> cheap (R7)",
            "alternatives": ["inline", "team-execution"],
            "frontier_width": frontier_width,
        }

    rec = dict(lifecycle_state.recommend_execution_backend(**leaf_signals))
    rec["frontier_width"] = frontier_width
    if (
        frontier_width > _FRONTIER_BUDGET_THRESHOLD
        and rec["recommended"] == "cc-workflows-ultracode"
    ):
        rec["budget_note"] = (
            f"frontier width {frontier_width} > {_FRONTIER_BUDGET_THRESHOLD}: a dynamic workflow per "
            f"leaf is expensive -> downgraded to team-execution (R7 frontier budget)"
        )
        alts = [a for a in rec.get("alternatives", []) if a != "team-execution"]
        if "cc-workflows-ultracode" not in alts:
            alts.append("cc-workflows-ultracode")
        rec["recommended"] = "team-execution"
        rec["alternatives"] = [a for a in alts if a != "team-execution"]
        # KTD4 compat contract: the leaf recommender's full-enumeration ``backends`` payload is
        # authoritative, so the frontier-budget downgrade must re-stamp it or the enumeration would
        # contradict the downgraded ``recommended``. Team-execution becomes recommended and the
        # ultracode entry becomes an alternative carrying the budget_note reason.
        for entry in rec.get("backends", []):
            if entry.get("backend") == "team-execution":
                entry["status"] = "recommended"
            elif entry.get("backend") == "cc-workflows-ultracode":
                entry["status"] = "alternative"
                entry["note"] = rec["budget_note"]
    return rec


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
