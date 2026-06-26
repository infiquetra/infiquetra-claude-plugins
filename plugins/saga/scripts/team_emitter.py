#!/usr/bin/env python3
"""Team-execution markdown emitter — the R9 second emitter (U11).

`/plan` authors ONE structured execution-spec (``execution_spec.py``, U10) and emits
from it **either** a runnable Claude Code workflow script (U10) **or** this team-
execution markdown protocol.  The governance difference is *which emitter runs*, not
the authoring — the spec is the single source of truth (R9, KTD6).

This emitter produces the ``## Team Structure`` section (mirroring
``team-execution/skills/team-execution/SKILL.md:234``) from the spec's units:

* **Workers** — one row per spec unit (each unit is a discrete phase of work).
* **Reviewers** — always the base reviewer set required by team-execution protocol.
* **Validators** — the base scanner set; extended per-unit via ``validators`` metadata.
* **Execution Gates** — the standard consensus + remediation protocol.
* **Reference Files** — the team-execution protocol reference set.

Saga records the path to the emitted plan file as ``orchestration_ref`` (a pointer,
never a copy of team-execution machinery — R9, KTD6).  The emitter returns the markdown
string; the caller writes it beside the plan and passes the path to
``saga.py save --orchestration-ref <path>``.

House testability pattern (mirrors ``execution_spec.py`` / ``saga.py``): pure functions,
no I/O at import.  The ``emit_team_structure`` function is the single testable surface.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# The base reviewer set the team-execution protocol always requires.
# These are the three mandatory base reviewers from the SKILL.md template.
_BASE_REVIEWERS: list[tuple[str, str]] = [
    ("devils-advocate-reviewer", "Devil's Advocate Reviewer"),
    ("security-reviewer", "Security Reviewer"),
    ("architecture-reviewer", "Architecture Reviewer"),
]

# The base validator set (security-scanner is the baseline).
_BASE_VALIDATORS: list[tuple[str, str]] = [
    ("security-scanner", "Scanner"),
]

# The reference files the team-execution protocol requires (verbatim from SKILL.md).
_REFERENCE_FILES: list[str] = [
    "team-execution/skills/team-execution/references/reviewer-registry.md",
    "team-execution/skills/team-execution/references/review-criteria.md",
    "team-execution/skills/team-execution/references/consensus-protocol.md",
    "team-execution/skills/team-execution/references/validator-registry.md",
    "team-execution/skills/team-execution/references/validator-criteria.md",
    "team-execution/skills/team-execution/references/validator-execution-order.md",
    "team-execution/skills/team-execution/references/validator-evidence-state.md",
    "team-execution/skills/team-execution/references/validator-spawn-quirks.md",
]

# The standard execution-gate protocol (verbatim from SKILL.md).
_EXECUTION_GATES: list[str] = [
    "Reviewer consensus threshold: >= 9.0/10 from every reviewer.",
    "Reviewer non-consensus blocks validators unless the user explicitly overrides.",
    "Scanners run before PR/CI/merge/nonprod coordination.",
    "Tester hard-fail blocks completion.",
    "Maximum 3 remediation loops before escalation.",
]


def emit_team_structure(spec: Any) -> str:
    """Emit the ``## Team Structure`` markdown section from an ``ExecutionSpec``.

    The spec is the same object ``execution_spec.py`` builds — validated by the caller
    before passing here.  This emitter never vendors team-execution machinery (R9): it
    produces a conforming markdown section the team-execution skill reads, nothing more.

    Returns the markdown string.  The caller writes it to the plan file and passes the
    path to ``saga.py save --orchestration-ref <path>`` so saga records only a pointer.

    Parameters
    ----------
    spec:
        A validated ``ExecutionSpec`` (from ``execution_spec.ExecutionSpec.from_dict``).
        The units become worker rows; the base reviewer / validator sets are fixed.
    """
    spec.validate()

    lines: list[str] = []

    # ---- Header ----
    lines.append("## Team Structure")
    lines.append("")
    lines.append(
        f"<!-- emitted from execution-spec '{spec.name}' by team_emitter.py (R9, KTD6) -->"
    )
    lines.append(
        "<!-- governance: team-execution (gated consensus); "
        "for advisory consensus use emit_workflow_script instead -->"
    )
    lines.append("")

    # ---- Workers ---- one row per spec unit
    lines.append("### Workers")
    lines.append("| Agent | Role | Mode | Responsibilities |")
    lines.append("|-------|------|------|------------------|")
    for i, unit in enumerate(spec.units, start=1):
        agent = f"worker-{i}"
        role = unit.label
        responsibilities = unit.prompt.split("\n")[0][:120] if unit.prompt else unit.label
        lines.append(f"| `{agent}` | {role} | bypassPermissions | {responsibilities} |")
    lines.append("")

    # ---- Reviewers ---- always the base set
    lines.append("### Reviewers")
    lines.append("| Agent | Role | Required | Selection Reason |")
    lines.append("|-------|------|----------|------------------|")
    for agent, role in _BASE_REVIEWERS:
        lines.append(f"| `{agent}` | {role} | yes | Base reviewer |")
    lines.append("")

    # ---- Validators ---- base set; the team-execution skill selects further per plan
    lines.append("### Validators")
    lines.append("| Agent | Group | Required | Selection Reason | Blocking |")
    lines.append("|-------|-------|----------|------------------|----------|")
    for agent, group in _BASE_VALIDATORS:
        lines.append(
            f"| `{agent}` | {group} | yes | Base validator | hard-fail blocks automation |"
        )
    lines.append("")

    # ---- Execution Gates ----
    lines.append("### Execution Gates")
    for gate in _EXECUTION_GATES:
        lines.append(f"- {gate}")
    lines.append("")

    # ---- Reference Files ----
    lines.append("### Reference Files")
    for ref in _REFERENCE_FILES:
        lines.append(f"- `{ref}`")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI -- emit the team-structure markdown from a JSON spec file
# ---------------------------------------------------------------------------


def _load_spec(path: Path) -> Any:
    """Load and return an ``ExecutionSpec`` from a JSON file.

    Imports ``execution_spec`` lazily so this module is importable without it on the
    path (tests import it directly from the file path).
    """
    # Resolve execution_spec relative to this file so the CLI works from any cwd.
    spec_module_path = Path(__file__).parent / "execution_spec.py"
    import importlib.util

    _spec = importlib.util.spec_from_file_location("execution_spec", spec_module_path)
    assert _spec is not None and _spec.loader is not None
    mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod.ExecutionSpec.from_dict(json.loads(path.read_text()))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Emit a team-execution ## Team Structure section from a spec JSON (R9, U11)."
    )
    parser.add_argument("spec", type=Path, help="Path to the execution-spec JSON file.")
    parser.add_argument(
        "-o",
        "--out",
        type=Path,
        help="Write the markdown here (default: stdout).",
    )
    args = parser.parse_args(argv)

    try:
        spec = _load_spec(args.spec)
        markdown = emit_team_structure(spec)
    except Exception as exc:  # SpecError or IO
        print(f"EMIT ERROR: {exc}", file=sys.stderr)
        return 2

    if args.out:
        args.out.write_text(markdown)
        print(f"wrote {args.out}")
    else:
        print(markdown, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
