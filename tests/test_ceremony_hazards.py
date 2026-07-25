"""ceremony_hazards.py tests (issue #346, U1).

Test design: a module-local ``FakeRunner`` (distinct from ``test_ship_ceremony.py``'s
``FakeGh`` — the full ``FakeGh``/bare-origin rig stays there for U4's integration
tests, per the plan). Every test here drives ``detect()`` directly against canned
``gh`` JSON responses; nothing touches a real git repo or a real ``gh`` process.

Oracles:

* stacked-pr — an open PR based on the branch about to be deleted (or merged) is
  reported as an acknowledgeable ``stacked_pr`` hazard.
* merge-not-landed — a ``branch_delete`` requested before the ceremony PR's state is
  confirmably ``MERGED`` is reported as a non-acknowledgeable ``merge_not_landed``
  hazard (the ``gh pr merge --auto``/``--delete-branch`` reorder hazard, R2).
* clean — a clean topology (no stacked PRs, merge landed) returns ``[]``.
* zero-probe — reversible transitions never issue a ``gh`` call.
* fail-loud — a probe that fails (non-zero exit) raises, never silently returns [].
* ordering — hazards are reported in registry order, not probe-completion order.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).parent.parent
CEREMONY_HAZARDS_PATH = ROOT / "plugins" / "saga" / "scripts" / "ceremony_hazards.py"


def _load_ceremony_hazards() -> ModuleType:
    spec = importlib.util.spec_from_file_location("ceremony_hazards", CEREMONY_HAZARDS_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses needs the module registered (py3.12)
    spec.loader.exec_module(module)
    return module


CH = _load_ceremony_hazards()


def _ok(stdout: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


def _fail(stderr: str = "boom") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr=stderr)


class FakeRunner:
    """A tiny, module-local fake ``gh`` runner. Configured per-test with canned
    responses keyed by the ``gh`` subcommand prefix (``("pr", "list")`` etc.);
    records every call so "zero probes on reversible transitions" is provable."""

    def __init__(
        self,
        *,
        pr_list: list[dict[str, Any]] | None = None,
        pr_view: dict[str, Any] | None = None,
        pr_list_fails: bool = False,
        pr_view_fails: bool = False,
    ) -> None:
        self._pr_list = pr_list if pr_list is not None else []
        self._pr_view = pr_view if pr_view is not None else {"state": "MERGED", "mergedAt": "x"}
        self._pr_list_fails = pr_list_fails
        self._pr_view_fails = pr_view_fails
        self.calls: list[list[str]] = []

    def __call__(self, cmd, *, cwd, capture_output, text, timeout):  # noqa: ANN001
        self.calls.append(list(cmd))
        args = list(cmd)[1:]  # drop leading "gh"
        if args[:2] == ["pr", "list"]:
            if self._pr_list_fails:
                return _fail("pr list failed")
            return _ok(json.dumps(self._pr_list))
        if args[:2] == ["pr", "view"]:
            if self._pr_view_fails:
                return _fail("pr view failed")
            return _ok(json.dumps(self._pr_view))
        raise AssertionError(f"unhandled fake gh call: {args!r}")


def _saga(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "kind": "issue",
        "id": "346",
        "branch": "work/346-ceremony-hazards",
        "pr_refs": ["#101"],
    }
    base.update(overrides)
    return base


# --------------------------------------------------------------------------- #
# Hazard / registry shape
# --------------------------------------------------------------------------- #


def test_hazard_registry_contains_canonical_ids() -> None:
    # Issue #635/U4 appends BRANCH_DELETE_TARGETS_BASE to the registry (R2/KTD3); the
    # first two ids and their order are unchanged.
    assert CH.HAZARD_REGISTRY == (
        CH.STACKED_PR,
        CH.MERGE_NOT_LANDED,
        CH.BRANCH_DELETE_TARGETS_BASE,
    )


def test_merge_not_landed_is_not_acknowledgeable_by_construction() -> None:
    runner = FakeRunner(pr_list=[], pr_view={"state": "OPEN", "mergedAt": None})
    hazards = CH.detect(_saga(), "branch_delete", ROOT, runner)
    assert len(hazards) == 1
    assert hazards[0].acknowledgeable is False


# --------------------------------------------------------------------------- #
# R1: stacked_pr hazard
# --------------------------------------------------------------------------- #


def test_stacked_pr_hazard_reported_for_branch_delete() -> None:
    runner = FakeRunner(
        pr_list=[{"number": 202, "title": "child PR"}],
        pr_view={"state": "MERGED", "mergedAt": "2026-07-11T00:00:00Z"},
    )
    hazards = CH.detect(_saga(), "branch_delete", ROOT, runner)
    ids = [h.hazard_id for h in hazards]
    assert CH.STACKED_PR in ids
    stacked = next(h for h in hazards if h.hazard_id == CH.STACKED_PR)
    assert stacked.transition == "branch_delete"
    assert stacked.acknowledgeable is True
    assert "202" in stacked.message


def test_stacked_pr_hazard_reported_for_merge() -> None:
    runner = FakeRunner(pr_list=[{"number": 303, "title": "child PR"}])
    hazards = CH.detect(_saga(), "merge", ROOT, runner)
    assert [h.hazard_id for h in hazards] == [CH.STACKED_PR]
    assert hazards[0].transition == "merge"
    assert hazards[0].acknowledgeable is True
    # Only the stacked-pr probe runs for `merge` — no pr-view probe.
    assert all(call[1:3] != ["pr", "view"] for call in runner.calls)


# --------------------------------------------------------------------------- #
# R2: merge_not_landed hazard — the --auto/--delete-branch reorder hazard
# --------------------------------------------------------------------------- #


def test_auto_merge_delete_branch_hazard_reorders() -> None:
    """delete requested before the ceremony PR is confirmably MERGED -> hazard,
    non-acknowledgeable (KTD3)."""
    runner = FakeRunner(pr_list=[], pr_view={"state": "OPEN", "mergedAt": None})
    hazards = CH.detect(_saga(), "branch_delete", ROOT, runner)
    assert len(hazards) == 1
    hazard = hazards[0]
    assert hazard.hazard_id == CH.MERGE_NOT_LANDED
    assert hazard.transition == "branch_delete"
    assert hazard.acknowledgeable is False
    assert "101" in hazard.message


def test_merge_not_landed_treats_merged_state_without_timestamp_as_not_landed() -> None:
    runner = FakeRunner(pr_list=[], pr_view={"state": "MERGED", "mergedAt": None})
    hazards = CH.detect(_saga(), "branch_delete", ROOT, runner)
    assert [h.hazard_id for h in hazards] == [CH.MERGE_NOT_LANDED]


# --------------------------------------------------------------------------- #
# Issue #635 / R2: branch_delete_targets_base — the deletion target IS the PR base
# --------------------------------------------------------------------------- #


def _landed(**overrides: Any) -> dict[str, Any]:
    """A confirmably-merged ``pr view`` payload carrying both ref names, so the
    merge_not_landed probe stays silent and only the R2 probe can speak."""
    payload: dict[str, Any] = {
        "state": "MERGED",
        "mergedAt": "2026-07-25T00:00:00Z",
        "headRefName": "work/635-ceremony-ref-resolution",
        "baseRefName": "outcome/norns-next-horizon",
    }
    payload.update(overrides)
    return payload


def test_branch_delete_targets_base_fires_when_head_equals_base() -> None:
    """R2: the resolved head equalling the resolved base means branch_delete would
    delete the branch the PR merged INTO — the live incident's shape."""
    runner = FakeRunner(
        pr_list=[],
        pr_view=_landed(headRefName="outcome/norns-next-horizon"),
    )
    hazards = CH.detect(_saga(), "branch_delete", ROOT, runner)
    assert [h.hazard_id for h in hazards] == [CH.BRANCH_DELETE_TARGETS_BASE]
    assert hazards[0].transition == "branch_delete"
    assert "outcome/norns-next-horizon" in hazards[0].message


def test_branch_delete_targets_base_is_not_acknowledgeable_by_construction() -> None:
    """KTD3: there is no legitimate case for deleting the PR base, so there is
    nothing to acknowledge — the hazard is not acknowledgeable, matching
    merge_not_landed."""
    runner = FakeRunner(pr_list=[], pr_view=_landed(headRefName="outcome/norns-next-horizon"))
    hazard = CH.detect(_saga(), "branch_delete", ROOT, runner)[0]
    assert hazard.acknowledgeable is False


def test_stacked_pr_probe_asks_about_the_resolved_head_not_the_rolling_field() -> None:
    """The probe's contract is "an open PR based on the branch about to be deleted", and
    on a leaf-into-outcome ceremony the saga's rolling ``branch`` field is not that
    branch — it is re-stamped on every tick save, so after ``checkout_main`` it names
    the PR base.

    Probing the base asks the wrong question in both directions: a child PR stacked on
    the real head goes undetected and the branch is deleted out from under it, while
    every sibling leaf still open against the base fires a spurious hazard — and this
    hazard IS acknowledgeable, so spurious firings train the operator to wave it
    through. ``merge`` passes no resolved head and keeps its old operand."""
    runner = FakeRunner(pr_list=[], pr_view=_landed())
    CH._probe_stacked_pr(  # noqa: SLF001
        _saga(),
        transition="branch_delete",
        repo_root=ROOT,
        runner=runner,
        resolved_head="feat/the-real-head",
    )
    listed = [c for c in runner.calls if c[:2] == ["gh", "pr"] and "list" in c]
    assert listed, "the probe must have issued its pr list query"
    argv = listed[-1]
    assert argv[argv.index("--base") + 1] == "feat/the-real-head"

    runner_bare = FakeRunner(pr_list=[], pr_view=_landed())
    CH._probe_stacked_pr(  # noqa: SLF001
        _saga(), transition="merge", repo_root=ROOT, runner=runner_bare, resolved_head=None
    )
    argv_bare = [c for c in runner_bare.calls if c[:2] == ["gh", "pr"] and "list" in c][-1]
    assert argv_bare[argv_bare.index("--base") + 1] == _saga()["branch"]


def test_branch_delete_targets_base_silent_when_head_differs_from_base() -> None:
    runner = FakeRunner(pr_list=[], pr_view=_landed())
    assert CH.detect(_saga(), "branch_delete", ROOT, runner) == []


def test_branch_delete_targets_base_uses_the_injected_resolved_head() -> None:
    """``run()`` resolves the deletion target through ``resolve_ceremony_refs`` and
    injects it, so the check compares the branch that will ACTUALLY be deleted against
    the PR's authoritative base.

    The injected head here is supplied directly, which is the rung-2 shape: manifest
    head vs PR base, two independent records. It is NOT evidence that the comparison
    spans two records in general — when the resolver answers on rung 1 both operands
    come from one ``gh pr view`` payload and the probe is inert by construction. See
    ``_probe_branch_delete_targets_base``'s docstring for the rung split."""
    runner = FakeRunner(pr_list=[], pr_view=_landed())
    fired = CH.detect(
        _saga(), "branch_delete", ROOT, runner, resolved_head="outcome/norns-next-horizon"
    )
    assert [h.hazard_id for h in fired] == [CH.BRANCH_DELETE_TARGETS_BASE]
    assert "outcome/norns-next-horizon" in fired[0].message
    silent = CH.detect(
        _saga(), "branch_delete", ROOT, runner, resolved_head="work/635-ceremony-ref-resolution"
    )
    assert silent == []


def test_branch_delete_targets_base_ignores_a_payload_missing_ref_names() -> None:
    """A ``pr view`` payload without headRefName/baseRefName must not read as
    ``"" == ""`` and fire — an absent answer is not a match."""
    runner = FakeRunner(pr_list=[], pr_view={"state": "MERGED", "mergedAt": "2026-07-25T00:00:00Z"})
    assert CH.detect(_saga(), "branch_delete", ROOT, runner) == []


def test_branch_delete_targets_base_is_not_probed_for_merge() -> None:
    """Probed only for branch_delete: ``merge`` does not delete anything, so the
    head==base topology raises no hazard there."""
    runner = FakeRunner(pr_list=[], pr_view=_landed(headRefName="outcome/norns-next-horizon"))
    assert CH.detect(_saga(), "merge", ROOT, runner) == []


def test_branch_delete_targets_base_probe_failure_raises() -> None:
    """Fail-loud: the R2 probe never degrades a failed ``gh`` call into "no hazard"."""
    runner = FakeRunner(pr_list=[], pr_view_fails=True)
    with pytest.raises(CH.HazardProbeError):
        CH.detect(_saga(), "branch_delete", ROOT, runner)


# --------------------------------------------------------------------------- #
# Clean topology
# --------------------------------------------------------------------------- #


def test_no_hazards_on_clean_topology_returns_empty() -> None:
    runner = FakeRunner(pr_list=[], pr_view={"state": "MERGED", "mergedAt": "2026-07-11T00:00:00Z"})
    assert CH.detect(_saga(), "branch_delete", ROOT, runner) == []
    assert CH.detect(_saga(), "merge", ROOT, runner) == []


# --------------------------------------------------------------------------- #
# Zero probes on reversible / non-gated transitions
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "transition", ["commit", "open_pr", "request_review", "checkout_main", "pull"]
)
def test_reversible_transitions_probe_nothing(transition: str) -> None:
    runner = FakeRunner()
    hazards = CH.detect(_saga(), transition, ROOT, runner)
    assert hazards == []
    assert runner.calls == []


def test_reversible_transitions_return_empty_even_without_runner() -> None:
    # No gh call should ever be attempted, so a runner isn't even needed here.
    assert CH.detect(_saga(), "checkout_main", ROOT, None) == []


# --------------------------------------------------------------------------- #
# Fail-loud probes
# --------------------------------------------------------------------------- #


def test_probe_failure_raises_not_empty() -> None:
    runner = FakeRunner(pr_list_fails=True)
    with pytest.raises(CH.HazardProbeError):
        CH.detect(_saga(), "branch_delete", ROOT, runner)


def test_pr_view_probe_failure_raises() -> None:
    runner = FakeRunner(pr_list=[], pr_view_fails=True)
    with pytest.raises(CH.HazardProbeError):
        CH.detect(_saga(), "branch_delete", ROOT, runner)


# --------------------------------------------------------------------------- #
# Ordering
# --------------------------------------------------------------------------- #


def test_hazard_ordering_is_registry_order() -> None:
    # Issue #635/U4: the payload now also carries head == base, so ALL THREE hazards
    # fire at once and the ordering assertion covers the whole registry rather than
    # its first two entries.
    runner = FakeRunner(
        pr_list=[{"number": 202, "title": "child PR"}],
        pr_view={
            "state": "OPEN",
            "mergedAt": None,
            "headRefName": "outcome/demo",
            "baseRefName": "outcome/demo",
        },
    )
    hazards = CH.detect(_saga(), "branch_delete", ROOT, runner)
    assert [h.hazard_id for h in hazards] == [
        CH.STACKED_PR,
        CH.MERGE_NOT_LANDED,
        CH.BRANCH_DELETE_TARGETS_BASE,
    ]
    assert [h.hazard_id for h in hazards] == list(CH.HAZARD_REGISTRY)


def test_garbled_pr_ref_fails_loud_never_reaches_gh() -> None:
    """A pr_refs entry that doesn't yield a plain PR number must raise (fail-loud,
    never 'no hazard') and must never reach gh argv (code-review F3)."""

    def exploding_runner(cmd, *, cwd, capture_output, text, timeout):  # noqa: ANN001, ANN202
        raise AssertionError(f"probe should not have shelled out, but called: {cmd!r}")

    saga = {"branch": "", "pr_refs": ["#12x"]}
    with pytest.raises(CH.HazardProbeError, match="not a plain PR number"):
        CH.detect(saga, "branch_delete", ROOT, exploding_runner)
