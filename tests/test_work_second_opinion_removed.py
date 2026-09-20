"""Work's in-process external-engine second-opinion offer is gone, and stays gone (issue #938).

Four properties, in the order the card states them:

1. **No offer by any route.** Work's skill and its continuation reference no longer tell an agent to
   print the offer line, no longer carry the offer's section, and no longer name any function the
   deleted module exported. The offer was prose an agent was instructed to print, not a function it
   called, so the negative is asserted over the shipped prose. Asserting only that an import fails
   would pass against a skill that still tells an agent to do the same thing by hand.
2. **No feature-private machinery survives.** No dispatch, sidecar, streak, or state module for the
   removed feature is importable or on disk.
3. **Every retained shared component still has its named live consumer.** One explicit assertion per
   row, never a loop over a directory: the component exists, the consumer still carries the reference
   that makes it a consumer, and the proving test still defines the test that proves it. This file
   does not run pytest inside pytest -- the proving tests pass by being in this same suite; this
   file's job is to make a vanished consumer or a renamed proving test fail loudly, by name.
4. **The mutation proof.** Re-adding the offer line to a copy of Work's skill makes the same
   predicate the real assertion uses report a violation. A proof that pins its own separate copy of
   the rule proves nothing, so both call ``offer_violations``.

The anti-regression pin is here too, because this card edits Work's skill and the card forbids it
from touching three of that skill's behaviours.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
PLUGINS = ROOT / "plugins"
SAGA = PLUGINS / "saga"
WORK_SKILL = SAGA / "skills" / "work" / "SKILL.md"
WORK_CONTINUATION = SAGA / "skills" / "work" / "references" / "pr-continuation-loop.md"
SECOND_OPINION_SCRIPT = SAGA / "scripts" / "second_opinion.py"

#: The exact line Work used to print when a target failed three fix attempts.
OFFER_LINE = (
    "Second opinion available: {target} failed after 3 fix attempts; "
    "dispatch an advisory second opinion?"
)

#: The heading of the section that carried the offer.
OFFER_HEADING = "## Second-opinion triggers"

#: The heading of the continuation reference's half of the same feature.
SIDECAR_HEADING = "## Repeated-failure second-opinion sidecar"

#: The versioned sidecar schema the removed state machinery wrote.
SIDECAR_SCHEMA = "saga.work-second-opinion.v1"

#: Every name the deleted module exported that Work's prose used to instruct an agent to call.
REMOVED_MODULE_NAMES = (
    "WorkAttempt",
    "load_work_second_opinion_state",
    "save_work_second_opinion_state",
    "record_work_attempt",
    "accept_work_offer",
    "prepare_second_opinion",
    "dispatch_second_opinion",
    "record_work_dispatch_outcome",
    "complete_second_opinion",
    "collect_second_opinion",
    "abandon_pending_second_opinion",
    "reconcile_second_opinion",
    "SecondOpinionClaimStore",
    "work_second_opinion_sidecar",
    "set_work_offer_disposition",
    "render_work_offer_line",
)

#: Retained component -> (live consumer file, the reference that makes it a consumer,
#: two rows named references inside the team-execution plugin, archived by issue #1030;
#: they retired with it and the components they pointed at are still covered by the rows below.
#: proving test file, the proving test's function name).
RETAINED_COMPONENTS: tuple[tuple[str, str, str, str, str], ...] = (
    (
        "plugins/saga/scripts/engine_dispatch.py",
        "plugins/saga/scripts/engine_resolver.py",
        "engine_dispatch",
        "tests/test_saga_engine_dispatch.py",
        "test_satisfy_gate_requires_ready_reconciliation_before_existing_checks",
    ),
    (
        "plugins/saga/scripts/engine_dispatch.py",
        "plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py",
        "retired saga external-engine runner",
        "tests/test_saga_second_opinion.py",
        "test_review_skills_halt_instead_of_naming_a_launch_cli",
    ),
    (
        "plugins/saga/scripts/reconcile.py",
        "plugins/saga/scripts/outcome_reconcile.py",
        "import reconcile",
        "tests/test_reconcile.py",
        "def test_",
    ),
    (
        "plugins/saga/scripts/run_ledger.py",
        "plugins/saga/scripts/pulse.py",
        "run_ledger",
        "tests/test_run_ledger.py",
        "def test_",
    ),
    (
        "plugins/saga/scripts/engine_resolver.py",
        "plugins/saga/scripts/execution_spec.py",
        "engine_resolver",
        "tests/test_saga_engine_resolver.py",
        "def test_",
    ),
    (
        "plugins/saga/skills/doc-review/SKILL.md",
        "plugins/saga/skills/doc-review/SKILL.md",
        "external_opinion.state=recommended",
        "tests/test_saga_plugin.py",
        "test_document_review_second_opinion_contract_is_intact",
    ),
)

#: The three Work behaviours this card is forbidden from changing, as substrings of Work's skill.
WORK_ANTI_REGRESSION_PINS = (
    "PR-open, review-request, and merge are each explicitly confirmed",
    "review_result.v1",
    "Outcome-driven review gate",
    "writes nothing durable",
    "the caller owns persistence",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def offer_violations(text: str, *, where: str) -> list[str]:
    """Report every way ``text`` still offers Work's in-process second opinion.

    Shared by the real assertion and by the mutation proof, so the proof exercises the same rule
    the suite enforces rather than a restatement of it.
    """
    violations: list[str] = []
    if OFFER_LINE in text:
        violations.append(f"{where}: the second-opinion offer line is still printed")
    if OFFER_HEADING in text:
        violations.append(f"{where}: the '{OFFER_HEADING}' section is still present")
    if SIDECAR_HEADING in text:
        violations.append(f"{where}: the '{SIDECAR_HEADING}' section is still present")
    if SIDECAR_SCHEMA in text:
        violations.append(f"{where}: the '{SIDECAR_SCHEMA}' sidecar schema is still named")
    for name in REMOVED_MODULE_NAMES:
        if re.search(rf"\b{re.escape(name)}\b", text):
            violations.append(f"{where}: still names the removed module's '{name}'")
    return violations


def test_work_offers_no_in_process_second_opinion_by_any_route() -> None:
    """Issue #938: neither Work surface offers, describes, or routes to the removed feature."""
    assert WORK_SKILL.is_file(), "Work's skill must exist for this negative to mean anything"
    assert WORK_CONTINUATION.is_file(), "Work's continuation reference must exist"

    violations = offer_violations(_read(WORK_SKILL), where=str(WORK_SKILL.relative_to(ROOT)))
    violations += offer_violations(
        _read(WORK_CONTINUATION), where=str(WORK_CONTINUATION.relative_to(ROOT))
    )

    assert violations == [], "Work still offers an in-process second opinion:\n" + "\n".join(
        violations
    )


def test_no_feature_private_second_opinion_module_survives() -> None:
    """Issue #938: the dispatch, sidecar, streak, and state machinery is gone from disk."""
    assert not SECOND_OPINION_SCRIPT.exists(), (
        f"{SECOND_OPINION_SCRIPT.relative_to(ROOT)} came back; issue #938 removed it"
    )

    strays = sorted(p.relative_to(ROOT) for p in PLUGINS.rglob("second_opinion.py"))
    assert strays == [], f"a second_opinion module survives at: {strays}"

    importers = sorted(
        str(path.relative_to(ROOT))
        for path in PLUGINS.rglob("*.py")
        if re.search(r"^\s*import\s+second_opinion\b", _read(path), re.MULTILINE)
    )
    assert importers == [], f"these modules still import second_opinion: {importers}"

    carriers = sorted(
        str(path.relative_to(ROOT))
        for path in PLUGINS.rglob("*.md")
        if path.name != "CHANGELOG.md" and SIDECAR_SCHEMA in _read(path)
    )
    assert carriers == [], f"the removed sidecar schema is still named in: {carriers}"


def test_every_retained_component_keeps_its_named_live_consumer() -> None:
    """Issue #938: nothing shared was removed, and each retained piece still has a real caller."""
    failures: list[str] = []
    for component, consumer, reference, proving_test_file, proving_test in RETAINED_COMPONENTS:
        component_path = ROOT / component
        consumer_path = ROOT / consumer
        proving_path = ROOT / proving_test_file

        if not component_path.is_file():
            failures.append(f"retained component missing: {component}")
            continue
        if not consumer_path.is_file():
            failures.append(f"named live consumer missing: {consumer} (consumes {component})")
            continue
        if reference not in _read(consumer_path):
            failures.append(f"{consumer} no longer references {reference!r} from {component}")
        if not proving_path.is_file():
            failures.append(f"proving test file missing: {proving_test_file} (for {component})")
            continue
        if proving_test not in _read(proving_path):
            failures.append(f"{proving_test_file} no longer defines {proving_test!r}")

    assert failures == [], "retained-component inventory broke:\n" + "\n".join(failures)


def test_the_external_content_trust_boundary_survives_the_removal() -> None:
    """Issue #938's named risk: the boundary three consumers cite is not removed with the feature."""
    doc = SAGA / "references" / "engine-output-trust-boundary.md"
    assert doc.is_file(), "the external-content trust boundary document was removed"

    text = _read(doc)
    for anchor in (
        "AdvisoryEvidence.evidence",
        "external_opinion.findings[].content",
        "validator and reviewer finding text",
        "opaque evidence data",
    ):
        assert anchor in text, f"the trust boundary lost its {anchor!r} row or rule"

    assert "second_opinion.py" not in text, (
        "the trust boundary still names the module issue #938 deleted; correct the Source cell"
    )


def test_work_keeps_merge_confirmation_typed_outcomes_and_the_programmatic_rule() -> None:
    """Issue #938 edits Work's skill, so its three untouchable behaviours are pinned here."""
    text = _read(WORK_SKILL)
    missing = [pin for pin in WORK_ANTI_REGRESSION_PINS if pin not in text]
    assert missing == [], (
        "issue #938's edit disturbed a Work behaviour the card forbids changing: " + repr(missing)
    )


def test_readding_the_offer_fails_the_no_offer_check(tmp_path: Path) -> None:
    """Mutation proof: the no-offer predicate is capable of failing, on the real prose."""
    mutant = tmp_path / "SKILL.md"
    mutant.write_text(
        _read(WORK_SKILL) + f"\n\n{OFFER_HEADING}\n\n```text\n{OFFER_LINE}\n```\n",
        encoding="utf-8",
    )

    violations = offer_violations(_read(mutant), where="mutant")

    assert violations != [], "re-adding the offer did not fail the no-offer check"
    assert any("offer line is still printed" in v for v in violations)
    assert any(OFFER_HEADING in v for v in violations)
