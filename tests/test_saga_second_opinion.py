"""Managed-session transport and external-only offer mode for review second opinions."""

from __future__ import annotations

import ast
import importlib.util
import io
import json
import re
import sys
import threading
from collections.abc import Mapping
from contextlib import redirect_stdout
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "plugins" / "saga" / "scripts"
CODE_REVIEW_SKILL = ROOT / "plugins" / "saga" / "skills" / "code-review" / "SKILL.md"
DOC_REVIEW_SKILL = ROOT / "plugins" / "saga" / "skills" / "doc-review" / "SKILL.md"
REGISTRY = ROOT / "plugins" / "saga" / "references" / "engine-registry.yaml"
GATE_RECORD = re.compile(
    r"<!-- gate-record: id=(?P<id>[^\s]+) absence=(?P<absence>[^\s]+) "
    r"transport=(?P<transport>[^\s]+) -->"
)

# Frozen offer surface as it stood before the new mode, minus the mode itself.
# A later field change here is a contract change, not a formatting preference.
_STABLE_OFFER_FIELDS = (
    "stage",
    "intent",
    "model",
    "effort",
    "unit_shape",
    "source",
    "prompt_required",
    "reason",
    "cost_delta_preview",
    "advisory_only",
)


def _load(name: str, path: Path) -> ModuleType:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


E = _load("engine_offer", SCRIPTS / "engine_offer.py")
XO = _load("external_only", SCRIPTS / "external_only.py")
SR = _load("engine_session_runner", SCRIPTS / "engine_session_runner.py")
SO = _load("second_opinion", SCRIPTS / "second_opinion.py")
D = SO.engine_dispatch
RC = SO.reconcile
REG = SO.Registry.load(REGISTRY)


@pytest.fixture(autouse=True)
def _isolated_fleet_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INFIQUETRA_FLEET_STATE_DIR", str(tmp_path / "fleet-state"))


def _excerpt(content: str = "assert verdict is computed from Claude-owned state") -> Any:
    return SO.SourceExcerpt(
        path="plugins/saga/scripts/engine_dispatch.py",
        start_line=100,
        end_line=101,
        content=content,
    )


def _finding() -> Any:
    return SO.FindingSnapshot(
        finding_id="F1",
        title="Advisory output must not change the gate verdict",
        severity="P1",
        why_it_matters="An external engine must never become the verifier of record.",
        evidence=("The verdict reads final Claude finding state.",),
        suggested_fix="Keep second-opinion output outside verdict inputs.",
        reviewed_revision="abc123",
        excerpts=(_excerpt(),),
    )


def _resolution(*, engine_id: str = "codex", variant: str = "gpt-5.5-high") -> Any:
    return SO.engine_resolver.Resolution(
        engine_id=engine_id,
        variant=variant,
        effort="high",
        recipe="review independently",
        protocol=["Review the selected finding."],
        payload="Review the selected finding.",
        write_capable=False,
        fallback=None,
        halt=None,
    )


def _prepared(monkeypatch: pytest.MonkeyPatch, **kwargs: Any) -> Any:
    resolution = kwargs.pop("resolution", None) or _resolution()
    monkeypatch.setattr(SO.engine_resolver, "resolve", lambda *_args, **_kwargs: resolution)
    return SO.prepare_second_opinion(
        _finding(),
        registry=REG,
        requested_by="human",
        reason="Check whether the stated impact follows from the selected source.",
        session_id="review-session",
        **kwargs,
    )


class ScriptedLauncher:
    """A scripted session launcher. Absence of a result is explicit, not inferred."""

    def __init__(
        self,
        *,
        start_error: Exception | None = None,
        collect_error: Exception | None = None,
        pending: bool = False,
        findings: tuple[dict[str, Any], ...] = (),
        output: str = "",
        result_path: Path | None = None,
    ) -> None:
        self.start_error = start_error
        self.collect_error = collect_error
        self.pending = pending
        self.findings = findings
        self.output = output
        self.result_path = result_path
        self.starts = 0
        self.collects = 0
        self.last_invocation: dict[str, Any] | None = None

    def start(self, invocation: Mapping[str, Any]) -> Any:
        self.starts += 1
        self.last_invocation = dict(invocation)
        if self.start_error is not None:
            raise self.start_error
        digest = str(invocation.get("request_digest") or "scripted")
        path = self.result_path or Path("/tmp/scripted-so-missing.json")
        return SR.SessionHandle(
            label="scripted",
            request_digest=digest,
            result_path=path,
            tool="codex",
        )

    def collect(self, handle: Any) -> Any:
        self.collects += 1
        if self.pending:
            raise SR.SessionPending("no result yet")
        if self.collect_error is not None:
            raise self.collect_error
        return SR.CollectedSession(findings=self.findings, output=self.output)


def _offer_core(offer: Any) -> dict[str, Any]:
    data = offer.to_json()
    return {key: data[key] for key in _STABLE_OFFER_FIELDS}


def _choices_without_new_mode(offer: Any) -> list[str]:
    return [choice for choice in offer.choices if choice != "external-only"]


def test_managed_session_runner_satisfies_runner_protocol_and_module_contract(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    rows = [{"content": "The existing final-state-only verdict remains correct."}]
    launcher = ScriptedLauncher(
        findings=tuple(rows),
        output=RC.render_source_findings(RC.parse_source_findings(rows)),
    )
    selected = SR.select_review_runner(
        stage="code-review",
        mode="second-opinion",
        home_vendor="claude",
        engine_id="codex",
        launcher=launcher,
    )
    assert callable(selected)
    prepared = _prepared(monkeypatch)
    store = SO.SecondOpinionClaimStore(tmp_path / "session-claims.json")
    evidence = SO.dispatch_second_opinion(prepared, runner=selected, claim_store=store)

    assert launcher.starts == 1
    assert launcher.collects == 1
    assert evidence.halt is None
    assert evidence.source_findings
    assert evidence.role_kind == "advisory-reviewer"
    assert evidence.intent == "second-opinion"
    assert "engine_session_runner" not in (SCRIPTS / "second_opinion.py").read_text(
        encoding="utf-8"
    )


def test_dispatch_second_opinion_still_takes_an_injected_runner() -> None:
    tree = ast.parse((SCRIPTS / "second_opinion.py").read_text(encoding="utf-8"))
    found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "dispatch_second_opinion":
            found = True
            names = [arg.arg for arg in node.args.args]
            names.extend(arg.arg for arg in node.args.kwonlyargs)
            assert "runner" in names
            assert "fallback_runner" not in names
    assert found


def test_offer_surface_is_byte_identical_apart_from_the_new_mode() -> None:
    work_mechanical = E.resolve_offer("work", unit_shape="mechanical")
    work_unknown = E.resolve_offer("work", unit_shape="unknown")
    work_judgment = E.resolve_offer("work", unit_shape="judgment")
    ideate = E.resolve_offer("ideate")
    code_review = E.resolve_offer("code-review", unit_shape="judgment")
    doc_review = E.resolve_offer("doc-review", unit_shape="judgment")

    assert work_mechanical.to_json() == {
        "stage": "work",
        "intent": "offload",
        "model": "sonnet",
        "effort": "medium",
        "unit_shape": "mechanical",
        "source": "default",
        "prompt_required": False,
        "choices": ["offload", "none", "second-opinion"],
        "reason": "work unit classified mechanical; mechanical work can be chaperoned cheaply",
        "cost_delta_preview": None,
        "advisory_only": True,
    }
    assert work_unknown.to_json() == {
        "stage": "work",
        "intent": "none",
        "model": None,
        "effort": None,
        "unit_shape": "unknown",
        "source": "default",
        "prompt_required": False,
        "choices": ["none", "offload", "second-opinion"],
        "reason": "work unit classified unknown; no engine offer selected by default",
        "cost_delta_preview": None,
        "advisory_only": True,
    }
    assert work_judgment.to_json() == {
        "stage": "work",
        "intent": "second-opinion",
        "model": "opus",
        "effort": "high",
        "unit_shape": "judgment",
        "source": "default",
        "prompt_required": False,
        "choices": ["second-opinion", "none", "offload"],
        "reason": "work unit classified judgment; judgment work benefits from advisory review",
        "cost_delta_preview": None,
        "advisory_only": True,
    }
    assert ideate.to_json() == {
        "stage": "ideate",
        "intent": "second-opinion",
        "model": "opus",
        "effort": "high",
        "unit_shape": "judgment",
        "source": "default",
        "prompt_required": False,
        "choices": ["second-opinion", "none", "offload"],
        "reason": "ideate unit classified judgment; judgment work benefits from advisory review",
        "cost_delta_preview": None,
        "advisory_only": True,
    }

    assert _offer_core(code_review) == {
        "stage": "code-review",
        "intent": "second-opinion",
        "model": "opus",
        "effort": "high",
        "unit_shape": "judgment",
        "source": "default",
        "prompt_required": False,
        "reason": (
            "code-review unit classified judgment; judgment work benefits from advisory review"
        ),
        "cost_delta_preview": None,
        "advisory_only": True,
    }
    assert _offer_core(doc_review) == {
        "stage": "doc-review",
        "intent": "second-opinion",
        "model": "opus",
        "effort": "high",
        "unit_shape": "judgment",
        "source": "default",
        "prompt_required": False,
        "reason": (
            "doc-review unit classified judgment; judgment work benefits from advisory review"
        ),
        "cost_delta_preview": None,
        "advisory_only": True,
    }
    assert _choices_without_new_mode(code_review) == ["second-opinion", "none", "offload"]
    assert _choices_without_new_mode(doc_review) == ["second-opinion", "none", "offload"]
    assert code_review.choices == ("second-opinion", "none", "offload", "external-only")
    assert doc_review.choices == ("second-opinion", "none", "offload", "external-only")
    assert "external-only" not in work_mechanical.choices
    assert "external-only" not in ideate.choices


def test_external_only_excludes_the_home_panel() -> None:
    admitted = XO.admit_external_only(
        home_vendor="claude",
        candidates=("claude/opus-high", "codex/gpt-5.6-sol-high", "agy/gemini-3.1-pro-high"),
        quorum=1,
    )
    assert isinstance(admitted, XO.ExternalOnlyRoster)
    assert admitted.home_vendor == "claude"
    assert admitted.members == ("codex/gpt-5.6-sol-high", "agy/gemini-3.1-pro-high")
    assert all(XO.vendor_of(member) != "claude" for member in admitted.members)

    with pytest.raises(XO.ExternalOnlyError, match="excluded vendor cannot sit"):
        XO.ExternalOnlyRoster(
            home_vendor="claude",
            members=("claude/opus-high",),
            quorum=1,
        )

    selected = SR.select_review_runner(
        stage="code-review",
        mode="external-only",
        home_vendor="claude",
        engine_id="codex",
        launcher=ScriptedLauncher(findings=({"content": "x"},)),
    )
    assert callable(selected)


def test_quorum_loss_under_external_only_halts_and_does_not_fall_back() -> None:
    halt = XO.admit_external_only(
        home_vendor="claude",
        candidates=("claude/opus-high",),
        quorum=1,
    )
    assert isinstance(halt, XO.ExternalOnlyHalt)
    assert halt.excluded_vendor == "claude"
    assert halt.remaining == ()
    assert "no review happened" in halt.reason
    assert not hasattr(halt, "fallback")
    assert not hasattr(halt, "home_panel")

    with pytest.raises(XO.ExternalOnlyError, match="must not list the excluded vendor"):
        XO.ExternalOnlyHalt(
            reason="x",
            excluded_vendor="claude",
            remaining=("claude/opus-high",),
            quorum=1,
        )

    launcher = ScriptedLauncher(findings=({"content": "x"},))
    selected = SR.select_review_runner(
        stage="doc-review",
        mode="external-only",
        home_vendor="claude",
        engine_id="claude",
        launcher=launcher,
    )
    assert isinstance(selected, XO.ExternalOnlyHalt)
    assert selected.excluded_vendor == "claude"
    assert launcher.starts == 0

    retry = XO.admit_external_only(
        home_vendor="claude",
        candidates=("claude/opus-high",),
        quorum=1,
    )
    assert isinstance(retry, XO.ExternalOnlyHalt)
    assert retry.remaining == ()


def test_external_only_modules_have_no_fallback_identifier() -> None:
    for path in (SCRIPTS / "external_only.py", SCRIPTS / "engine_session_runner.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = {node.id.lower() for node in ast.walk(tree) if isinstance(node, ast.Name)}
        assert "fallback" not in names
        assert "fall_back" not in names
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "select_review_runner":
                args = [arg.arg for arg in node.args.args]
                args.extend(arg.arg for arg in node.args.kwonlyargs)
                assert "fallback_runner" not in args


def test_gate_record_contract_still_opens_satisfies_and_resolves_absent() -> None:
    code_review = CODE_REVIEW_SKILL.read_text(encoding="utf-8")
    records = {match.group("id"): match.groupdict() for match in GATE_RECORD.finditer(code_review)}
    assert records["code-review-interaction"] == {
        "id": "code-review-interaction",
        "absence": "HALT",
        "transport": "ask-user-question",
    }
    assert records["code-review-engine-offer"] == {
        "id": "code-review-engine-offer",
        "absence": "HALT",
        "transport": "ask-user-question",
    }
    assert "open before prompting, satisfy on answer, `resolve-absent`" in code_review
    assert "on silence (`HALT`)" in code_review
    assert frozenset({"advisory-reviewer", "panel"}) == D.NON_GATING_ROLE_KINDS


def test_session_not_started_is_not_a_review_that_found_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    not_started = SR.runner(
        launcher=ScriptedLauncher(start_error=SR.SessionLaunchError("launcher refused"))
    )
    empty_review = SR.runner(launcher=ScriptedLauncher(findings=(), output=""))
    died = SR.runner(
        launcher=ScriptedLauncher(collect_error=SR.SessionCollectError("no result file"))
    )

    started = not_started({"task": "review"})
    found_nothing = empty_review({"task": "review"})
    vanished = died({"task": "review"})

    assert SR.classify_session_result(started) == "not-started"
    assert SR.classify_session_result(found_nothing) == "ran-empty"
    assert SR.classify_session_result(vanished) == "died"
    assert started["status"] == "error"
    assert found_nothing["status"] == "ok"
    assert found_nothing["findings"] == []
    assert vanished["status"] == "no-output"
    assert started != found_nothing

    prepared = _prepared(monkeypatch)
    missing_store = SO.SecondOpinionClaimStore(tmp_path / "not-started.json")
    missing = SO.dispatch_second_opinion(prepared, runner=not_started, claim_store=missing_store)
    assert missing.halt == "second-opinion dispatch error"

    empty_prepared = _prepared(monkeypatch)
    empty_store = SO.SecondOpinionClaimStore(tmp_path / "ran-empty.json")
    empty = SO.dispatch_second_opinion(empty_prepared, runner=empty_review, claim_store=empty_store)
    assert empty.halt == SO.EMPTY_OPINION_NOTE
    assert empty.halt != missing.halt


def test_provider_egress_tier_and_claim_persistence_unchanged_with_session_runner(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    prepared = _prepared(monkeypatch)
    assert prepared.selected_identity == "codex/gpt-5.5-high"
    assert prepared.egress_policy == "networked"
    assert prepared.chaperone_model == "opus"
    assert prepared.chaperone_effort == "high"
    assert prepared.chaperone_model == SO.DEFAULT_SECOND_OPINION_TIER["model"]
    assert prepared.chaperone_effort == SO.DEFAULT_SECOND_OPINION_TIER["effort"]

    rows = [{"content": "The existing final-state-only verdict remains correct."}]
    launcher = ScriptedLauncher(
        findings=tuple(rows),
        output=RC.render_source_findings(RC.parse_source_findings(rows)),
    )
    session_runner = SR.runner(launcher=launcher)
    store = SO.SecondOpinionClaimStore(tmp_path / "persist-claims.json")
    first = SO.dispatch_second_opinion(prepared, runner=session_runner, claim_store=store)
    assert first.halt is None
    assert launcher.starts == 1

    second = SO.dispatch_second_opinion(prepared, runner=session_runner, claim_store=store)
    assert launcher.starts == 1
    assert second.halt == SO.COLLECTED_NOTE
    assert store.read(prepared.request_id).state == "collected"


def test_external_only_is_rejected_for_non_review_stages(tmp_path: Path) -> None:
    with pytest.raises(E.EngineOfferError, match="only valid for code-review and doc-review"):
        E.save_preference(
            tmp_path,
            "work",
            E.Preference(intent="external-only", model="opus", effort="high"),
        )


def test_remember_external_only_roundtrip_for_code_review(tmp_path: Path) -> None:
    saved = E.save_preference(
        tmp_path,
        "code-review",
        E.Preference(intent="external-only", model="opus", effort="high"),
    )
    raw = json.loads(saved.read_text(encoding="utf-8"))
    assert raw["stages"]["code-review"] == {
        "intent": "external-only",
        "model": "opus",
        "effort": "high",
    }
    offer = E.resolve_offer("code-review", repo_root=tmp_path, unit_shape="judgment")
    assert offer.intent == "external-only"
    assert offer.model == "opus"
    assert offer.effort == "high"
    assert offer.source == "stored"
    assert offer.prompt_required is False


def test_command_launcher_nonzero_exit_is_not_started(tmp_path: Path) -> None:
    def run(_argv: list[str]) -> Any:
        return SR.CommandResult(returncode=1, stderr="agent missing")

    launcher = SR.CommandSessionLauncher(run=run, cwd=tmp_path)
    result = SR.runner(launcher=launcher)(
        {
            "via": "codex:delegate",
            "task": "REVIEW THIS EXACT FINDING",
            "model": "gpt-5.5",
            "effort": "high",
        }
    )
    assert SR.classify_session_result(result) == "not-started"
    assert result["status"] == "error"


def test_command_launcher_missing_result_file_is_pending_not_died(tmp_path: Path) -> None:
    def run(_argv: list[str]) -> Any:
        return SR.CommandResult(returncode=0, stdout='{"tab_id":"tab-1"}', pid=9)

    launcher = SR.CommandSessionLauncher(run=run, cwd=tmp_path)
    result = SR.runner(launcher=launcher)(
        {
            "via": "codex:delegate",
            "task": "REVIEW THIS EXACT FINDING",
            "model": "gpt-5.5",
            "effort": "high",
            "request_digest": "abc123digest",
        }
    )
    assert SR.classify_session_result(result) == "pending"
    assert result["status"] == "pending"


def test_review_stage_sets_match() -> None:
    assert E.REVIEW_STAGES == SR.REVIEW_STAGES == frozenset({"code-review", "doc-review"})


def test_skills_name_the_session_runner_and_external_only_halt() -> None:
    code_review = CODE_REVIEW_SKILL.read_text(encoding="utf-8")
    doc_review = DOC_REVIEW_SKILL.read_text(encoding="utf-8")
    for text in (code_review, doc_review):
        assert "engine_session_runner.py" in text
        assert "admit_external_only" in text
        assert "do not\nfall back to the excluded vendor" in text or (
            "do not fall back to the excluded vendor" in text
        )


def _folded(text: str) -> str:
    return " ".join(text.split())


def test_external_only_names_the_seat_it_governs_and_the_roster_it_does_not() -> None:
    """The guarantee's bound is stated, not implied. Removing the sentence fails this."""
    assert XO.EXTERNAL_ONLY_GUARANTEE == (
        "Under external-only the home vendor cannot be reached through the "
        "external-reviewer seat. The in-session lens fan-out is governed by the "
        "consensus-panel roster, which is separate work."
    )
    folded = _folded(XO.EXTERNAL_ONLY_GUARANTEE)
    assert "EXTERNAL_ONLY_GUARANTEE" in (SCRIPTS / "external_only.py").read_text(encoding="utf-8")
    for path in (CODE_REVIEW_SKILL, DOC_REVIEW_SKILL):
        assert folded in _folded(path.read_text(encoding="utf-8"))


def _codex_invocation(**overrides: object) -> dict[str, Any]:
    invocation: dict[str, Any] = {
        "via": "codex:delegate",
        "task": "REVIEW THIS EXACT FINDING",
        "model": "gpt-5.5",
        "effort": "high",
        "role": "reviewer",
        "sandbox": "read-only",
    }
    invocation.update(overrides)
    return invocation


def test_pending_launch_is_not_died_and_collect_recovers_findings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    result_path = tmp_path / "slow.json"
    launcher = ScriptedLauncher(pending=True, result_path=result_path)
    run = SR.runner(launcher=launcher)
    store = SO.SecondOpinionClaimStore(tmp_path / "claims.json")
    prepared = _prepared(monkeypatch)

    first = SO.dispatch_second_opinion(prepared, runner=run, claim_store=store)
    assert first.halt == SO.PENDING_NOTE
    assert store.read(prepared.request_id).state == "pending"
    assert launcher.starts == 1

    payload = {
        "request_digest": prepared.request_digest,
        "findings": [{"content": "P0: the gate can be bypassed"}],
        "output": "P0: the gate can be bypassed",
    }
    result_path.write_text(json.dumps(payload), encoding="utf-8")
    launcher.pending = False
    launcher.findings = ({"content": "P0: the gate can be bypassed"},)
    launcher.output = RC.render_source_findings(
        RC.parse_source_findings([{"content": "P0: the gate can be bypassed"}])
    )

    retry = SO.dispatch_second_opinion(prepared, runner=run, claim_store=store)
    assert retry.halt == SO.PENDING_NOTE
    assert launcher.starts == 1

    recovered = SO.dispatch_second_opinion(
        prepared, runner=run, claim_store=store, recover_pending=True
    )
    assert recovered.halt is None
    assert recovered.source_findings
    assert store.read(prepared.request_id).state == "collected"
    assert launcher.starts == 1


def test_recover_pending_on_requested_is_interrupt_not_collect(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    store = SO.SecondOpinionClaimStore(tmp_path / "claims.json")
    prepared = _prepared(monkeypatch)
    claimed = store.claim(prepared)
    assert claimed.acquired
    assert claimed.claim.state == "requested"
    evidence = SO.dispatch_second_opinion(
        prepared,
        runner=SR.runner(launcher=ScriptedLauncher(findings=({"content": "x"},))),
        claim_store=store,
        recover_pending=True,
    )
    assert evidence.halt == SO.INTERRUPTED_DISPATCH_NOTE
    assert store.read(prepared.request_id).state == "unavailable"


def test_abandon_pending_is_never_collected_not_empty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    launcher = ScriptedLauncher(pending=True)
    store = SO.SecondOpinionClaimStore(tmp_path / "claims.json")
    prepared = _prepared(monkeypatch)
    SO.dispatch_second_opinion(prepared, runner=SR.runner(launcher=launcher), claim_store=store)
    evidence = SO.abandon_pending_second_opinion(prepared, claim_store=store)
    assert evidence.halt == SO.NEVER_COLLECTED_NOTE
    assert store.read(prepared.request_id).state == "unavailable"
    assert evidence.halt != SO.EMPTY_OPINION_NOTE


def test_pending_claim_bound_refuses_a_ninth_launch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(SO, "MAX_PENDING_CLAIMS", 2)
    store = SO.SecondOpinionClaimStore(tmp_path / "claims.json")
    launcher = ScriptedLauncher(pending=True)
    run = SR.runner(launcher=launcher)
    first = _prepared(monkeypatch)
    SO.dispatch_second_opinion(first, runner=run, claim_store=store)
    second = SO.prepare_second_opinion(
        _finding(),
        registry=REG,
        requested_by="human",
        reason="A second independent request to fill the pending bound.",
        session_id="review-session",
    )
    SO.dispatch_second_opinion(second, runner=run, claim_store=store)
    third = SO.prepare_second_opinion(
        _finding(),
        registry=REG,
        requested_by="human",
        reason="A third request that must be refused by the pending bound.",
        session_id="review-session",
    )
    blocked = SO.dispatch_second_opinion(third, runner=run, claim_store=store)
    assert blocked.halt == SO.PENDING_BOUND_NOTE
    assert store.read(third.request_id).state == "unavailable"
    assert launcher.starts == 2


def test_real_codex_invocation_keeps_tool_task_model_and_effort(tmp_path: Path) -> None:
    captured: list[list[str]] = []

    def run(argv: list[str]) -> Any:
        captured.append(argv)
        return SR.CommandResult(returncode=0, stdout='{"tab_id":"tab-1"}', pid=11)

    invocation = _codex_invocation(request_digest="digest-for-launch")
    result = SR.runner(launcher=SR.CommandSessionLauncher(run=run, cwd=tmp_path))(invocation)
    assert captured, "launcher must run"
    argv = captured[0]
    assert "codex" in argv
    assert argv[-1].endswith(".prompt.md")
    assert "--model" in argv and "gpt-5.5" in argv
    assert "-c" in argv and "model_reasoning_effort=high" in argv
    assert argv[argv.index("codex") + 1 :].count("--model") == 1
    assert "REVIEW THIS EXACT FINDING" in Path(argv[-1]).read_text(encoding="utf-8")
    assert SR.classify_session_result(result) == "pending"
    handle = SR.SessionHandle.from_dict(result["handle"])
    assert handle.tool == "codex"
    assert handle.request_digest == "digest-for-launch"
    assert handle.model == "gpt-5.5"
    assert handle.effort == "high"
    assert not handle.result_path.exists()


def test_missing_findings_key_is_not_an_empty_review(tmp_path: Path) -> None:
    path = tmp_path / "nofindings.json"
    path.write_text(json.dumps({"output": "reviewer crashed mid-write"}), encoding="utf-8")
    handle = SR.SessionHandle(
        label="x",
        request_digest="d1",
        result_path=path,
        tool="codex",
    )
    with pytest.raises(SR.SessionCollectError, match="does not claim findings"):
        SR.read_result_file(handle)
    result = SR.runner(
        launcher=ScriptedLauncher(collect_error=SR.SessionCollectError("does not claim findings"))
    )(_codex_invocation())
    assert SR.classify_session_result(result) == "died"


def test_preexisting_result_file_is_not_this_session(tmp_path: Path) -> None:
    digest = "stale-digest"
    path = SR.result_path_for(tmp_path, digest)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "request_digest": digest,
                "findings": [{"content": "stale finding"}],
                "output": "stale finding",
            }
        ),
        encoding="utf-8",
    )

    def run(_argv: list[str]) -> Any:
        return SR.CommandResult(returncode=0, stdout='{"tab_id":"tab-1"}')

    result = SR.runner(launcher=SR.CommandSessionLauncher(run=run, cwd=tmp_path))(
        _codex_invocation(request_digest=digest)
    )
    assert SR.classify_session_result(result) == "not-started"


def test_result_file_for_another_request_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "other.json"
    path.write_text(
        json.dumps(
            {
                "request_digest": "other-digest",
                "findings": [{"content": "stale finding"}],
                "output": "stale finding",
            }
        ),
        encoding="utf-8",
    )
    handle = SR.SessionHandle(
        label="x", request_digest="this-digest", result_path=path, tool="codex"
    )
    with pytest.raises(SR.SessionCollectError, match="not bound to this request"):
        SR.read_result_file(handle)


def test_external_only_runner_rejects_excluded_vendor_invocation() -> None:
    launcher = ScriptedLauncher(findings=({"content": "x"},), output="x")
    selected = SR.select_review_runner(
        stage="code-review",
        mode="external-only",
        home_vendor="codex",
        engine_id="agy",
        launcher=launcher,
    )
    assert callable(selected)
    result = selected(_codex_invocation())
    assert result["session_outcome"] == "not-started"
    assert "excluded vendor" in result["reason"]
    assert launcher.starts == 0


def test_vendor_compare_is_casefold_and_stripped() -> None:
    admitted = XO.admit_external_only(
        home_vendor="claude",
        candidates=("Claude/opus-high", " CLAUDE/opus", "codex/gpt-5.6-sol-high"),
        quorum=1,
    )
    assert isinstance(admitted, XO.ExternalOnlyRoster)
    assert admitted.members == ("codex/gpt-5.6-sol-high",)


def test_external_only_offer_reason_names_the_seat_not_the_home_panel(tmp_path: Path) -> None:
    E.save_preference(
        tmp_path,
        "code-review",
        E.Preference(intent="external-only", model="opus", effort="high"),
    )
    offer = E.resolve_offer("code-review", repo_root=tmp_path)
    assert XO.EXTERNAL_ONLY_GUARANTEE in offer.reason
    assert "home vendor's panel" not in offer.reason


def test_real_dispatch_invocation_keeps_tool_task_model_and_effort(tmp_path: Path) -> None:
    captured: list[list[str]] = []

    def run(argv: list[str]) -> Any:
        captured.append(argv)
        return SR.CommandResult(returncode=0, stdout='{"tab_id":"tab-1"}', pid=11)

    resolution = SO.engine_resolver.Resolution(
        engine_id="codex",
        variant="gpt-5.5-high",
        effort="high",
        recipe="review independently",
        protocol=["Review the selected finding."],
        payload="REVIEW THIS EXACT FINDING",
        write_capable=False,
        fallback=None,
        halt=None,
        invocation={"model": "gpt-5.5", "effort": "high"},
    )
    invocation = dict(
        D._build_invocation(
            resolution, model=None, sandbox=None, write_set=None, role_kind="advisory-reviewer"
        )
    )
    invocation["request_digest"] = "digest-from-dispatch"
    result = SR.runner(launcher=SR.CommandSessionLauncher(run=run, cwd=tmp_path))(invocation)
    assert captured, "launcher must run"
    argv = captured[0]
    assert "codex" in argv
    assert "--model" in argv and "gpt-5.5" in argv
    assert "model_reasoning_effort=high" in argv
    assert "REVIEW THIS EXACT FINDING" in Path(argv[-1]).read_text(encoding="utf-8")
    handle = SR.SessionHandle.from_dict(result["handle"])
    assert handle.tool == "codex"
    assert handle.request_digest == "digest-from-dispatch"
    assert handle.result_path == SR.result_path_for(tmp_path, "digest-from-dispatch")
    assert not handle.result_path.exists()
    assert SR.classify_session_result(result) == "pending"


def test_missing_findings_key_through_runner_is_died_not_empty(tmp_path: Path) -> None:
    path = tmp_path / "nofindings.json"
    path.write_text(json.dumps({"output": "reviewer crashed mid-write"}), encoding="utf-8")
    handle = SR.SessionHandle(label="x", request_digest="d1", result_path=path, tool="codex")

    class FileLauncher:
        def start(self, invocation: Mapping[str, Any]) -> Any:
            return handle

        def collect(self, collected: Any) -> Any:
            return SR.read_result_file(collected)

    result = SR.runner(launcher=FileLauncher())({"task": "t"})
    assert SR.classify_session_result(result) == "died"
    assert result["status"] == "no-output"
    assert result.get("findings") != []


def test_empty_object_result_is_not_an_empty_review(tmp_path: Path) -> None:
    path = tmp_path / "empty-object.json"
    path.write_text("{}", encoding="utf-8")
    handle = SR.SessionHandle(label="x", request_digest="d1", result_path=path, tool="codex")
    with pytest.raises(SR.SessionCollectError, match="does not claim findings"):
        SR.read_result_file(handle)


def test_pending_then_later_file_is_collected_not_spent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    result_path = tmp_path / "slow.json"
    starts = {"n": 0}

    class LaterFileLauncher:
        def start(self, invocation: Mapping[str, Any]) -> Any:
            starts["n"] += 1
            digest = str(invocation.get("request_digest") or "later")
            return SR.SessionHandle(
                label="review",
                request_digest=digest,
                result_path=result_path,
                tool="codex",
            )

        def collect(self, handle: Any) -> Any:
            return SR.read_result_file(handle)

    run = SR.runner(launcher=LaterFileLauncher())
    store = SO.SecondOpinionClaimStore(tmp_path / "claims.json")
    prepared = _prepared(monkeypatch)

    first = SO.dispatch_second_opinion(prepared, runner=run, claim_store=store)
    assert first.halt == SO.PENDING_NOTE
    assert store.read(prepared.request_id).state == "pending"
    assert starts["n"] == 1

    rows = [{"content": "P0: the gate can be bypassed"}]
    result_path.write_text(
        json.dumps(
            {
                "request_digest": prepared.request_digest,
                "findings": rows,
                "output": RC.render_source_findings(RC.parse_source_findings(rows)),
            }
        ),
        encoding="utf-8",
    )

    retry = SO.dispatch_second_opinion(prepared, runner=run, claim_store=store)
    assert retry.halt == SO.PENDING_NOTE
    assert starts["n"] == 1

    recovered = SO.collect_second_opinion(prepared, runner=run, claim_store=store)
    assert recovered.halt is None
    assert recovered.source_findings
    assert store.read(prepared.request_id).state == "collected"
    assert starts["n"] == 1


def test_vendor_spellings_of_the_home_vendor_are_excluded() -> None:
    for candidate in ("Claude/opus-high", " claude/opus-high", "claude", "CLAUDE/opus"):
        got = XO.admit_external_only(
            home_vendor="claude",
            candidates=(candidate, "codex/gpt-5.6-sol-high"),
            quorum=2,
        )
        assert isinstance(got, XO.ExternalOnlyHalt), candidate
        assert got.remaining == ("codex/gpt-5.6-sol-high",)

    mixed_home = XO.admit_external_only(
        home_vendor="Claude",
        candidates=("claude/opus-high", "codex/gpt-5.6-sol-high"),
        quorum=1,
    )
    assert isinstance(mixed_home, XO.ExternalOnlyRoster)
    assert mixed_home.members == ("codex/gpt-5.6-sol-high",)
    assert mixed_home.home_vendor == "claude"

    spaced = XO.admit_external_only(
        home_vendor="codex",
        candidates=("codex /gpt-5.5", "CODEX /gpt-5.5", "agy/gemini-3.1-pro-high"),
        quorum=1,
    )
    assert isinstance(spaced, XO.ExternalOnlyRoster)
    assert spaced.members == ("agy/gemini-3.1-pro-high",)

    engine_id_only = XO.admit_external_only(
        home_vendor="codex",
        candidates=("codex", "agy/gemini-3.1-pro-high"),
        quorum=1,
    )
    assert isinstance(engine_id_only, XO.ExternalOnlyRoster)
    assert engine_id_only.members == ("agy/gemini-3.1-pro-high",)

    with pytest.raises(XO.ExternalOnlyError, match="excluded vendor cannot sit"):
        XO.ExternalOnlyRoster(
            home_vendor="Claude",
            members=("claude/opus-high",),
            quorum=1,
        )
    with pytest.raises(XO.ExternalOnlyError, match="excluded vendor cannot sit"):
        XO.ExternalOnlyRoster(
            home_vendor="codex",
            members=("codex /gpt-5.5",),
            quorum=1,
        )


def test_default_external_only_reason_names_the_seat() -> None:
    reason = E._reason_for(
        "code-review",
        "judgment",
        E.Preference(intent="external-only", model="opus", effort="high"),
    )
    assert XO.EXTERNAL_ONLY_GUARANTEE in reason
    assert "home vendor's panel" not in reason


def test_cli_parser_exposes_launch_and_collect() -> None:
    parser = SR._build_parser()
    launch = parser.parse_args(
        [
            "launch",
            "--invocation-file",
            "inv.json",
            "--stage",
            "code-review",
            "--mode",
            "external-only",
            "--home-vendor",
            "claude",
            "--engine-id",
            "codex",
        ]
    )
    assert launch.command == "launch"
    assert launch.claim_store.endswith("second-opinion-claims.json")
    collect = parser.parse_args(["collect", "--handle-file", "handle.json"])
    assert collect.command == "collect"
    assert collect.claim_store.endswith("second-opinion-claims.json")


def test_cli_launch_and_collect_exist() -> None:
    assert 'add_parser("launch"' in (SCRIPTS / "engine_session_runner.py").read_text(
        encoding="utf-8"
    ) or "add_parser('launch'" in (SCRIPTS / "engine_session_runner.py").read_text(encoding="utf-8")
    text = (SCRIPTS / "engine_session_runner.py").read_text(encoding="utf-8")
    assert 'add_parser("launch"' in text
    assert 'add_parser("collect"' in text
    code_review = CODE_REVIEW_SKILL.read_text(encoding="utf-8")
    assert "engine_session_runner.py launch" in code_review
    assert "engine_session_runner.py collect" in code_review
    assert "--claim-store" in code_review
    assert "request_digest" in code_review
    assert SO.CLAIM_SCHEMA == "saga.second-opinion-claims.v2"


def test_collected_result_survives_resume(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    result_path = tmp_path / "slow.json"
    launcher = ScriptedLauncher(pending=True, result_path=result_path)
    run = SR.runner(launcher=launcher)
    store = SO.SecondOpinionClaimStore(tmp_path / "claims.json")
    prepared = _prepared(monkeypatch)
    SO.dispatch_second_opinion(prepared, runner=run, claim_store=store)
    rows = [{"content": "P0: collected review found a blocker"}]
    result_path.write_text(
        json.dumps(
            {
                "request_digest": prepared.request_digest,
                "findings": rows,
                "output": RC.render_source_findings(RC.parse_source_findings(rows)),
            }
        ),
        encoding="utf-8",
    )
    launcher.pending = False
    launcher.findings = tuple(rows)
    launcher.output = RC.render_source_findings(RC.parse_source_findings(rows))
    collected = SO.collect_second_opinion(prepared, runner=run, claim_store=store)
    assert collected.source_findings
    assert store.read(prepared.request_id).state == "collected"
    resumed = SO.dispatch_second_opinion(
        prepared, runner=run, claim_store=store, recover_pending=True
    )
    assert resumed.halt is None
    assert resumed.source_findings
    assert store.read(prepared.request_id).state == "collected"
    assert launcher.starts == 1


def test_recover_during_launch_does_not_terminalize_or_raise(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    started = threading.Event()
    release = threading.Event()
    starts = {"n": 0}

    class BlockingLauncher:
        def start(self, invocation: Mapping[str, Any]) -> Any:
            starts["n"] += 1
            started.set()
            assert release.wait(2)
            digest = str(invocation.get("request_digest") or "blocked")
            return SR.SessionHandle(
                label="review",
                request_digest=digest,
                result_path=tmp_path / "blocked.json",
                tool="codex",
            )

        def collect(self, handle: Any) -> Any:
            raise SR.SessionPending("still launching")

    prepared = _prepared(monkeypatch)
    store = SO.SecondOpinionClaimStore(tmp_path / "claims.json")
    run = SR.runner(launcher=BlockingLauncher())
    errors: list[BaseException] = []
    launch_result: dict[str, Any] = {}

    def launch() -> None:
        try:
            launch_result["evidence"] = SO.dispatch_second_opinion(
                prepared, runner=run, claim_store=store
            )
        except BaseException as exc:  # noqa: BLE001 - test records the raise
            errors.append(exc)

    worker = threading.Thread(target=launch)
    worker.start()
    assert started.wait(2)
    resume = SO.dispatch_second_opinion(
        prepared, runner=run, claim_store=store, recover_pending=True
    )
    assert resume.halt == SO.PENDING_NOTE
    assert store.read(prepared.request_id).state == "pending"
    release.set()
    worker.join(2)
    assert not errors
    assert launch_result["evidence"].halt == SO.PENDING_NOTE
    assert store.read(prepared.request_id).state == "pending"
    assert starts["n"] == 1


def test_prose_output_is_not_unusable(tmp_path: Path) -> None:
    path = tmp_path / "prose.json"
    rows = [{"content": "P0: the gate can be bypassed"}]
    path.write_text(
        json.dumps(
            {
                "request_digest": "d1",
                "findings": rows,
                "output": "Here is a prose summary of the finding.",
            }
        ),
        encoding="utf-8",
    )
    handle = SR.SessionHandle(label="x", request_digest="d1", result_path=path, tool="codex")
    collected = SR.read_result_file(handle)
    assert collected.output == RC.render_source_findings(RC.parse_source_findings(rows))
    assert collected.findings


def test_control_character_session_id_does_not_launch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    prepared = _prepared(monkeypatch)
    object.__setattr__(prepared, "session_id", "review\nsession")
    launcher = ScriptedLauncher(findings=({"content": "x"},), output="x")
    store = SO.SecondOpinionClaimStore(tmp_path / "claims.json")
    evidence = SO.dispatch_second_opinion(
        prepared, runner=SR.runner(launcher=launcher), claim_store=store
    )
    assert launcher.starts == 0
    assert evidence.halt == SO.UNUSABLE_DISPATCH_NOTE
    assert store.read(prepared.request_id).state == "unavailable"


def test_launch_writes_engine_fact_before_collect(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    events: list[str] = []

    class FakeState:
        @staticmethod
        def arm(engine_id: str, session_id: str, producer: str, root: Any = None) -> Any:
            events.append(f"ARM({engine_id})")
            return type("Entry", (), {"armed_at": 1.0})()

        @staticmethod
        def disarm(session_id: str, root: Any = None) -> None:
            events.append("DISARM")

    def load(name: str) -> Any:
        if name == "delegation_state":
            return FakeState, ""
        return None, "unused"

    monkeypatch.setattr(SO.engine_dispatch, "_load_fleet_module", load)
    launcher = ScriptedLauncher(pending=True)
    prepared = _prepared(monkeypatch)
    store = SO.SecondOpinionClaimStore(tmp_path / "claims.json")
    ledger = SO.run_ledger.RunLedger(tmp_path / "facts.jsonl")
    first = SO.dispatch_second_opinion(
        prepared,
        runner=SR.runner(launcher=launcher),
        claim_store=store,
        ledger=ledger,
        subplot_id="review-1",
        at="2026-08-16T00:00:00Z",
    )
    assert first.halt == SO.PENDING_NOTE
    assert events[:2] == ["ARM(codex)", "DISARM"] or events[0] == "ARM(codex)"
    assert "ARM(codex)" in events
    assert launcher.starts == 1
    facts = list(SO.run_ledger.read_facts(ledger))
    engine_facts = [item for item in facts if item.get("kind") == "engine"]
    assert engine_facts
    assert engine_facts[0]["status"] == "pending"


def test_pending_evidence_does_not_close_work_offer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    prepared = _prepared(monkeypatch)
    store = SO.SecondOpinionClaimStore(tmp_path / "claims.json")
    evidence = SO.dispatch_second_opinion(
        prepared,
        runner=SR.runner(launcher=ScriptedLauncher(pending=True)),
        claim_store=store,
    )
    assert SO.is_pending_evidence(evidence)
    attempt = SO.WorkAttempt(
        attempt_id="a1",
        change_ref="ref",
        result="fail",
        failing_test_files=("tests/test_x.py",),
    )
    offer = SO.WorkOffer(
        offer_id="o1",
        target="tests/test_x.py",
        streak_epoch_attempt_id="a1",
        disposition="accepted",
        tier={"model": "opus", "effort": "high"},
        request_id=prepared.request_id,
        request_digest=prepared.request_digest,
        execution_id=prepared.execution_id,
    )
    state = SO.WorkSecondOpinionState(round=1, attempts=(attempt,), offers=(offer,))
    updated = SO.record_work_dispatch_outcome(state, offer_id="o1", evidence=evidence)
    assert updated.offers[0].disposition == "accepted"


def test_documented_cli_launch_marks_pending_and_collect_accepts_stdout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    prepared = _prepared(monkeypatch)
    store_path = tmp_path / "claims.json"
    store = SO.SecondOpinionClaimStore(store_path)
    assert store.claim(prepared).acquired

    def start(self: Any, invocation: Mapping[str, Any]) -> Any:
        digest = str(invocation.get("request_digest") or "")
        return SR.SessionHandle(
            label="cli",
            request_digest=digest,
            result_path=tmp_path / "cli-result.json",
            tool="codex",
        )

    monkeypatch.setattr(SR.CommandSessionLauncher, "start", start)
    invocation_path = tmp_path / "inv.json"
    invocation_path.write_text(
        json.dumps(
            {
                "via": "codex:delegate",
                "task": "REVIEW THIS EXACT FINDING",
                "model": "gpt-5.5",
                "effort": "high",
                "request_digest": prepared.request_digest,
                "engine_id": "codex",
            }
        ),
        encoding="utf-8",
    )
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = SR.main(
            [
                "launch",
                "--invocation-file",
                str(invocation_path),
                "--repo-root",
                str(tmp_path),
                "--claim-store",
                str(store_path),
            ]
        )
    assert code == 0
    payload = json.loads(buffer.getvalue())
    assert payload["session_outcome"] == "pending"
    assert payload["result_path"]
    assert store.read(prepared.request_id).state == "pending"
    handle_path = tmp_path / "launch-stdout.json"
    handle_path.write_text(json.dumps(payload), encoding="utf-8")
    handle = SR.handle_from_payload(payload)
    assert handle.request_digest == prepared.request_digest
    collected = SO.collect_second_opinion(
        prepared,
        runner=SR.runner(launcher=ScriptedLauncher(pending=True)),
        claim_store=store,
    )
    assert collected.halt == SO.PENDING_NOTE
