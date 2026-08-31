"""Brainstorm continuity contract — issue 913 (B1).

Twelve assertions over the live skill and section contract files, each through a
module-level ``check_*`` predicate (KTD3) so U3 can mutate it. Every test calls the
predicate twice: on the real file (expect empty) and on a mutated copy with the
rule string removed (expect non-empty).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
BRAINSTORM_SKILL = ROOT / "plugins/saga/skills/brainstorm/SKILL.md"
REQUIREMENTS_SECTIONS = ROOT / "plugins/saga/skills/brainstorm/references/requirements-sections.md"
RESUME_SKILL = ROOT / "plugins/saga/skills/resume/SKILL.md"
LINT = ROOT / "plugins/saga/scripts/lint_gate_absence_contract.py"


# ---------------------------------------------------------------------------
# Module-level predicates (KTD3) — each returns violation messages, [] = pass.
# ---------------------------------------------------------------------------


def _norm(text: str) -> str:
    return " ".join(text.split())


def check_provenance(text: str) -> list[str]:
    violations: list[str] = []
    if "`capability`" not in text:
        violations.append("missing `capability` field")
    if "`activity`" not in text:
        violations.append("missing `activity` field")
    if "`maturity`" not in text:
        violations.append("missing `maturity` field")
    if "producing capability" not in text.lower():
        violations.append("missing producing capability declaration")
    if "producing activity" not in text.lower():
        violations.append("missing producing activity identity declaration")
    if "brainstorm" not in text.lower():
        violations.append("missing brainstorm capability value")
    if "brainstorm-<topic-slug>-<UTC timestamp" not in text:
        violations.append("missing activity identity format")
    return violations


def check_checkpoint(text: str) -> list[str]:
    violations: list[str] = []
    norm = _norm(text)
    if "pending-confirmation" not in text:
        violations.append("missing pending-confirmation")
    if "exact proposed boundary" not in norm:
        violations.append("missing exact proposed boundary")
    if "before the confirmation question is posed" not in norm:
        violations.append("missing before-confirmation ordering")
    if "no readiness-claiming artifact exists at that point" not in norm:
        violations.append("missing no readiness-claiming artifact guard")
    if (
        "written AFTER the confirmation question" in text
        or "written after the confirmation question" in text.lower()
    ):
        violations.append("found inverted ordering: written AFTER confirmation")
    return violations


def check_declared_gate(text: str) -> list[str]:
    violations: list[str] = []
    pattern = r"<!--\s*gate-record:\s*id=brainstorm-scope-confirmation\s+absence=HALT\s+transport=ask-user-question\s*-->"
    matches = re.findall(pattern, text)
    if len(matches) != 1:
        violations.append(
            f"expected exactly one brainstorm-scope-confirmation marker, found {len(matches)}"
        )
    # Ensure it sits near Phase 2.5 context (section proximity check).
    if "Phase 2.5" not in text:
        violations.append("missing Phase 2.5 context for gate")
    return violations


def check_resume_restore(text: str) -> list[str]:
    violations: list[str] = []
    norm = _norm(text)
    if "summarize the restored boundary" not in norm:
        violations.append("missing summarize the restored boundary")
    if "without re-presenting settled decisions" not in norm:
        violations.append("missing without re-presenting settled decisions")
    return violations


def check_ambiguity_stop(text: str) -> list[str]:
    violations: list[str] = []
    norm = _norm(text).lower()
    if "two or more near-matches stop and ask" not in norm:
        violations.append("missing ambiguity stop rule")
    if "never by recency" not in norm:
        violations.append("missing never by recency refusal")
    if "filename" not in norm:
        violations.append("missing filename refusal")
    if "broad content match" not in norm:
        violations.append("missing broad content match refusal")
    return violations


def check_revision(text: str) -> list[str]:
    violations: list[str] = []
    norm = _norm(text)
    if "rewrites the file back to `pending-confirmation`" not in norm:
        violations.append("missing rewrites back to pending-confirmation")
    if "requires a fresh Phase 2.5 confirmation" not in norm:
        violations.append("missing requires fresh confirmation")
    if "without fresh confirmation is refused" not in norm:
        violations.append("missing refused without fresh confirmation")
    return violations


def check_artifact_free(text: str) -> list[str]:
    violations: list[str] = []
    norm = _norm(text)
    if "writes no file at all" not in norm:
        violations.append("missing writes no file at all")
    if "Shown only when the artifact on disk declares `maturity: requirements-ready`" not in text:
        violations.append("missing per-option route gating")
    if "nothing is labelled `requirements-ready`" not in norm:
        violations.append("missing nothing labelled requirements-ready")
    if "tied to declared maturity, not to file existence" not in norm:
        violations.append("missing tied to declared maturity guard")
    return violations


def check_minimum_artifact(text: str) -> list[str]:
    violations: list[str] = []
    norm = _norm(text)
    if "exactly four parts" not in norm:
        violations.append("missing exactly four parts")
    if "confirmed scope and material decisions" not in norm:
        violations.append("missing confirmed scope and material decisions")
    if "rationale" not in norm:
        violations.append("missing rationale")
    if "intended acceptance outcome" not in norm:
        violations.append("missing intended acceptance outcome")
    if "unresolved planning questions" not in norm:
        violations.append("missing unresolved planning questions")
    if "no architecture or implementation plan" not in norm:
        violations.append("missing no architecture or implementation plan exclusion")
    return violations


def check_legacy_inference(text: str) -> list[str]:
    violations: list[str] = []
    norm = _norm(text)
    if "labelled inferred" not in norm:
        violations.append("missing labelled inferred")
    if "operator confirms it before it is used" not in norm:
        violations.append("missing operator confirms before use")
    if "file on disk is left exactly as found" not in norm:
        violations.append("missing file on disk is left exactly as found")
    if "does not backfill the producer facts" not in norm:
        violations.append("missing does not backfill producer facts")
    if "discovery never writes to the file" not in norm:
        violations.append("missing discovery never writes")
    return violations


def check_telemetry(text: str) -> list[str]:
    violations: list[str] = []
    if "saga.py save" in text:
        violations.append("found forbidden saga.py save reference")
    if "gate-divergence" in text:
        violations.append("found forbidden gate-divergence reference")
    return violations


def check_marker_census(text: str) -> list[str]:
    violations: list[str] = []
    ids = re.findall(r"<!--\s*gate-record:\s*id=([^\s]+)", text)
    expected = {
        "brainstorm-interrogation-gate",
        "brainstorm-handoff-routing",
        "brainstorm-scope-confirmation",
    }
    if set(ids) != expected:
        violations.append(f"marker ids {set(ids)!r} != expected {expected!r}")
    if len(ids) != 3:
        violations.append(f"expected exactly 3 markers, found {len(ids)}")
    if "brainstorm-interrogation-choice" in text:
        violations.append("old id brainstorm-interrogation-choice must not appear")
    return violations


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _mutate(text: str, needle: str) -> str:
    assert needle in text, f"mutation needle not found: {needle!r}"
    return text.replace(needle, "", 1)


# ---------------------------------------------------------------------------
# Provenance — section contract metadata.
# ---------------------------------------------------------------------------


def test_provenance_positive_and_mutation_fails() -> None:
    text = _read(REQUIREMENTS_SECTIONS)
    assert check_provenance(text) == [], f"provenance violations: {check_provenance(text)}"
    mutated = _mutate(text, "the producing capability, fixed as `brainstorm`")
    assert check_provenance(mutated) != []


# ---------------------------------------------------------------------------
# Checkpoint — Phase 2.5 ordering.
# ---------------------------------------------------------------------------


def test_checkpoint_positive_and_mutation_fails() -> None:
    text = _read(BRAINSTORM_SKILL)
    assert check_checkpoint(text) == [], f"checkpoint violations: {check_checkpoint(text)}"
    mutated = _mutate(text, "before the confirmation question is posed")
    assert check_checkpoint(mutated) != []


# ---------------------------------------------------------------------------
# Declared gate — Phase 2.5 marker.
# ---------------------------------------------------------------------------


def test_declared_gate_positive_and_mutation_fails() -> None:
    text = _read(BRAINSTORM_SKILL)
    assert check_declared_gate(text) == [], f"gate violations: {check_declared_gate(text)}"
    mutated = _mutate(text, "brainstorm-scope-confirmation")
    assert check_declared_gate(mutated) != []


# ---------------------------------------------------------------------------
# Resume restore — both skills.
# ---------------------------------------------------------------------------


def test_resume_restore_in_brainstorm_skill_and_mutation_fails() -> None:
    text = _read(BRAINSTORM_SKILL)
    assert check_resume_restore(text) == [], f"restore violations: {check_resume_restore(text)}"
    mutated = _mutate(text, "without re-presenting settled decisions")
    assert check_resume_restore(mutated) != []


def test_resume_restore_in_resume_skill_and_mutation_fails() -> None:
    text = _read(RESUME_SKILL)
    assert check_resume_restore(text) == [], (
        f"resume restore violations: {check_resume_restore(text)}"
    )
    mutated = text.replace("without re-presenting settled decisions", "")
    assert check_resume_restore(mutated) != []


# ---------------------------------------------------------------------------
# Ambiguity stop — recency/filename/content refusals.
# ---------------------------------------------------------------------------


def test_ambiguity_stop_positive_and_mutation_fails() -> None:
    text = _read(BRAINSTORM_SKILL)
    assert check_ambiguity_stop(text) == [], f"ambiguity violations: {check_ambiguity_stop(text)}"
    mutated = _mutate(text, "never by recency")
    assert check_ambiguity_stop(mutated) != []


def test_ambiguity_stop_in_resume_skill() -> None:
    text = _read(RESUME_SKILL)
    assert check_ambiguity_stop(text) == [], (
        f"resume ambiguity violations: {check_ambiguity_stop(text)}"
    )


# ---------------------------------------------------------------------------
# Revision — fresh confirmation required.
# ---------------------------------------------------------------------------


def test_revision_positive_and_mutation_fails() -> None:
    text = _read(BRAINSTORM_SKILL)
    assert check_revision(text) == [], f"revision violations: {check_revision(text)}"
    mutated = _mutate(text, "without fresh confirmation is refused")
    assert check_revision(mutated) != []


# ---------------------------------------------------------------------------
# Artifact-free outcome — no file, no route, gating on maturity.
# ---------------------------------------------------------------------------


def test_artifact_free_positive_and_mutation_fails() -> None:
    text = _read(BRAINSTORM_SKILL)
    assert check_artifact_free(text) == [], f"artifact-free violations: {check_artifact_free(text)}"
    mutated = _mutate(text, "writes no file at all")
    assert check_artifact_free(mutated) != []


# ---------------------------------------------------------------------------
# Minimum artifact — four parts, no architecture.
# ---------------------------------------------------------------------------


def test_minimum_artifact_positive_and_mutation_fails() -> None:
    text = _read(REQUIREMENTS_SECTIONS)
    assert check_minimum_artifact(text) == [], (
        f"minimum artifact violations: {check_minimum_artifact(text)}"
    )
    mutated = _mutate(text, "exactly four parts")
    assert check_minimum_artifact(mutated) != []

    # Skill now points to the section contract for the four-part definition
    skill_text = _read(BRAINSTORM_SKILL)
    assert "requirements-sections.md" in skill_text


# ---------------------------------------------------------------------------
# Legacy inference — labelled, confirmed, unchanged.
# ---------------------------------------------------------------------------


def test_legacy_inference_positive_and_mutation_fails() -> None:
    text = _read(BRAINSTORM_SKILL)
    assert check_legacy_inference(text) == [], f"legacy violations: {check_legacy_inference(text)}"
    mutated = _mutate(text, "labelled inferred")
    assert check_legacy_inference(mutated) != []


# ---------------------------------------------------------------------------
# Telemetry — no deferred save, no gate-divergence.
# ---------------------------------------------------------------------------


def test_telemetry_negative_and_mutation_proves_detection() -> None:
    text = _read(BRAINSTORM_SKILL)
    assert check_telemetry(text) == [], f"telemetry violations: {check_telemetry(text)}"
    # Mutation: injecting a forbidden string must be caught.
    mutated = text + "\ncall saga.py save\n"
    assert check_telemetry(mutated) != []
    mutated2 = text + "\ngate-divergence\n"
    assert check_telemetry(mutated2) != []


# ---------------------------------------------------------------------------
# Marker census — three markers, exact ids, old id absent.
# ---------------------------------------------------------------------------


def test_marker_census_positive_and_mutation_fails() -> None:
    text = _read(BRAINSTORM_SKILL)
    assert check_marker_census(text) == [], f"census violations: {check_marker_census(text)}"
    mutated = _mutate(text, "brainstorm-interrogation-gate")
    assert check_marker_census(mutated) != []
    # Old id must not appear anywhere.
    assert "brainstorm-interrogation-choice" not in text


# ---------------------------------------------------------------------------
# Gate-absence agreement — production lint exits 0, VIOLATIONS: 0.
# ---------------------------------------------------------------------------


def test_gate_absence_lint_reports_zero_violations() -> None:
    result = subprocess.run(
        [sys.executable, str(LINT)],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "VIOLATIONS: 0" in result.stdout


# ---------------------------------------------------------------------------
# Resume matched-brainstorm classification and dispatch routing (FIX-3)
# ---------------------------------------------------------------------------

DISPATCH_TABLE = ROOT / "plugins/saga/skills/loop/references/dispatch-table.md"


def check_matched_brainstorm(text: str) -> list[str]:
    violations: list[str] = []
    norm = _norm(text)
    if "matched-brainstorm" not in text:
        violations.append("missing matched-brainstorm classification")
    if "routes to `/brainstorm`" not in norm and "Route directly to `/brainstorm`" not in text:
        violations.append("missing routes to /brainstorm")
    return violations


def check_no_tick(text: str) -> list[str]:
    violations: list[str] = []
    norm = _norm(text).lower()
    if "writes no" not in norm or "re-entry tick" not in norm.lower():
        violations.append("missing writes no re-entry tick")
    return violations


def check_dispatch_pending(text: str) -> list[str]:
    violations: list[str] = []
    pending_rows = 0
    for line in text.splitlines():
        if "pending-confirmation" in line and line.strip().startswith("|"):
            pending_rows += 1
            parts = [p.strip() for p in line.split("|")]
            # 4-column main-chain table: | Saga `lifecycle_phase` | `phase_status` | Handoff maturity | Next command |
            # parts[0] empty, parts[1] phase, parts[2] status, parts[3] maturity, parts[4] command, parts[5] empty
            if len(parts) >= 5:
                consumer = parts[4]
                if "`/brainstorm`" not in consumer:
                    violations.append(
                        f"pending-confirmation row does not route to /brainstorm: {line.strip()[:80]}"
                    )
    if pending_rows == 0:
        violations.append("missing pending-confirmation -> /brainstorm row")
    elif pending_rows < 2:
        violations.append(
            f"expected at least 2 pending-confirmation rows (no-saga and brainstorm), found {pending_rows}"
        )
    # Check that requirements-ready still routes to /plan (at least one row)
    has_requirements_row = False
    for line in text.splitlines():
        if "requirements-ready" in line and line.strip().startswith("|") and "`/plan`" in line:
            has_requirements_row = True
            break
    if not has_requirements_row:
        violations.append("missing requirements-ready -> /plan row")
    # Check for brainstorm -- row (no declared maturity)
    has_brainstorm_empty = False
    for line in text.splitlines():
        if (
            line.strip().startswith("|")
            and "`brainstorm`" in line
            and "| — |" in line
            # Must be the brainstorm any -- row, not the pending row
            and "`/brainstorm`" in line
        ):
            has_brainstorm_empty = True
    if not has_brainstorm_empty:
        violations.append("missing brainstorm -- (no maturity) -> /brainstorm row")
    return violations


def check_no_pending_to_plan(text: str) -> list[str]:
    violations: list[str] = []
    for line in text.splitlines():
        if line.strip().startswith("|") and "pending-confirmation" in line and "/plan" in line:
            violations.append(f"pending-confirmation must not route to /plan: {line.strip()[:80]}")
    return violations


def test_resume_matched_brainstorm_positive() -> None:
    text = _read(RESUME_SKILL)
    assert check_matched_brainstorm(text) == [], (
        f"matched-brainstorm: {check_matched_brainstorm(text)}"
    )
    assert check_no_tick(text) == [], f"no tick: {check_no_tick(text)}"


def test_dispatch_pending_routing_positive() -> None:
    text = DISPATCH_TABLE.read_text(encoding="utf-8")
    assert check_dispatch_pending(text) == [], f"dispatch pending: {check_dispatch_pending(text)}"
    assert check_no_pending_to_plan(text) == [], (
        f"no pending to plan: {check_no_pending_to_plan(text)}"
    )
