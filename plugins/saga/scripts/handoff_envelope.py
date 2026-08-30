#!/usr/bin/env python3
"""Build a thin Infiquetra loop handoff envelope for mission-control."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

STATE_DIR = Path(".claude/saga")
SOURCE_DIRS = (
    Path("docs/plans"),
    Path("docs/brainstorms"),
    Path("docs/specs"),
    Path("docs/ideation"),
    Path("docs/reviews"),
    Path("docs/work-sessions"),
)

HANDOFF_MATURITIES = (
    "idea-ready",
    "requirements-ready",
    "plan-ready",
    "resume-ready",
    "deferred-context",
    "pending-confirmation",
)


def _read_frontmatter_maturity(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    frontmatter = text[3:end]
    for line in frontmatter.splitlines():
        stripped = line.strip()
        if stripped.startswith("maturity:"):
            value = stripped[len("maturity:") :].strip()
            # Strip inline YAML comment
            if "#" in value:
                value = value.split("#", 1)[0].strip()
            value = value.strip("\"'").strip()
            if value and value in HANDOFF_MATURITIES:
                return value
    return None


def infer_maturity(source: str, root: Path | None = None) -> str:
    normalized = source.replace("\\", "/")
    # Frontmatter-declared maturity wins when the source resolves to an existing file
    # that declares one (KTD7) — so a pending-confirmation checkpoint under
    # docs/brainstorms/ no longer hands off as requirements-ready.
    base = root or Path.cwd()
    candidate = base / normalized if not Path(normalized).is_absolute() else Path(normalized)
    # Also try the literal path for absolute tmp_path sources
    for cand in (Path(normalized), candidate):
        if cand.is_file():
            declared = _read_frontmatter_maturity(cand)
            if declared is not None:
                return declared
    if "docs/ideation/" in normalized:
        return "idea-ready"
    if "docs/brainstorms/" in normalized:
        return "requirements-ready"
    if "docs/specs/" in normalized:
        # A spec is a sharp WHAT, NOT plan-ready. This equals the final default below and
        # is set for consistency with the other SOURCE_DIRS entries, not a behavior change.
        return "requirements-ready"
    if "docs/plans/" in normalized or "docs/reviews/" in normalized:
        return "plan-ready"
    if "docs/work-sessions/" in normalized or normalized.startswith("branch:"):
        return "resume-ready"
    return "requirements-ready"


def infer_lifecycle_phase(source: str) -> str:
    normalized = source.replace("\\", "/")
    if "docs/ideation/" in normalized:
        return "ideation"
    if "docs/brainstorms/" in normalized:
        return "brainstorm"
    if "docs/plans/" in normalized:
        return "plan"
    if "docs/reviews/" in normalized:
        return "review"
    if "docs/work-sessions/" in normalized or normalized.startswith("branch:"):
        return "work"
    # docs/specs/ is off-chain (/spec) — no lifecycle phase; maturity is set in infer_maturity.
    return "unknown"


def read_state(root: Path) -> dict[str, object]:
    state_path = root / STATE_DIR / "state.json"
    if not state_path.exists():
        return {}
    try:
        loaded = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def discover_active_source(root: Path) -> str | None:
    state = read_state(root)
    current = state.get("current_work")
    if isinstance(current, dict):
        for key in ("plan_path", "work_session_path"):
            value = current.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    candidates: list[Path] = []
    for rel_dir in SOURCE_DIRS:
        directory = root / rel_dir
        if directory.exists():
            candidates.extend(path for path in directory.rglob("*.md") if path.is_file())
    if not candidates:
        return None
    latest = max(candidates, key=lambda path: path.stat().st_mtime)
    return latest.relative_to(root).as_posix()


def current_git_state(root: Path) -> dict[str, str]:
    def run(args: list[str]) -> str:
        result = subprocess.run(args, cwd=root, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return ""
        return result.stdout.strip()

    branch = run(["git", "branch", "--show-current"])
    head = run(["git", "rev-parse", "--short", "HEAD"])
    return {"branch": branch, "head": head}


def build_handoff_envelope(
    source: str | None = None,
    *,
    target_team: str = "",
    target_repo: str = "",
    issue_type: str = "",
    reason: str = "",
    blockers: str = "",
    open_questions: str = "",
    root: Path | None = None,
) -> dict[str, object]:
    root = root or Path.cwd()
    selected_source = source or discover_active_source(root)
    if not selected_source:
        raise RuntimeError("No handoff source found; provide --source or create a durable artifact")

    maturity = infer_maturity(selected_source, root)
    if maturity == "pending-confirmation":
        suggested_command = (
            f"Boundary recorded but unconfirmed for {selected_source} — "
            "no durable route exists until the operator confirms in Brainstorm Phase 2.5"
        )
    else:
        suggested_command = f"/issue --prepare --from {selected_source} --maturity {maturity}"
        if target_team:
            suggested_command += f" for {target_team}"
        if target_repo:
            suggested_command += f" in {target_repo}"

    return {
        "schema_version": "1.0",
        "created_at": datetime.now(UTC).isoformat(),
        "source": selected_source,
        "lifecycle_phase": infer_lifecycle_phase(selected_source),
        "handoff_maturity": maturity,
        "handoff_reason": reason,
        "target_team": target_team,
        "target_repo": target_repo,
        "issue_type": issue_type,
        "blockers": blockers,
        "open_questions": open_questions,
        "suggested_command": suggested_command,
        "lifecycle_owner": "saga",
        "issue_artifact_owner": "mission-control",
        "body_template_owner": "mission-control",
        "git": current_git_state(root),
    }


def build_deploy_handoff_envelope(
    saga_id: str,
    *,
    payload: str = "gate",
    offered_by: str = "",
    pr_refs: list[str] | None = None,
    token: str | None = None,
    now: str | None = None,
) -> dict[str, object]:
    """Thin delegator to ``deploy_handoff.build_envelope`` (issue #395, KTD1).

    The saga -> deploy edge gets its own single-writer sidecar module
    (``deploy_handoff.py``); this builder is the only seam ``handoff_envelope.py`` exposes onto it,
    keeping the mission-control envelope (``build_handoff_envelope`` above) byte-untouched. The
    import is lazy so loading this module for the mission-control path never pulls the deploy edge
    in — and ``deploy_handoff`` is a sibling script resolved via a ``sys.path`` insert, not a
    cross-plugin import (R1).
    """
    scripts_dir = str(Path(__file__).resolve().parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import deploy_handoff  # noqa: PLC0415

    return deploy_handoff.build_envelope(
        saga_id,
        payload=payload,
        offered_by=offered_by,
        pr_refs=pr_refs,
        token=token,
        now=now,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=None)
    parser.add_argument("--target-team", default="")
    parser.add_argument("--target-repo", default="")
    parser.add_argument("--issue-type", default="")
    parser.add_argument("--reason", default="")
    parser.add_argument("--blockers", default="")
    parser.add_argument("--open-questions", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    envelope = build_handoff_envelope(
        args.source,
        target_team=args.target_team,
        target_repo=args.target_repo,
        issue_type=args.issue_type,
        reason=args.reason,
        blockers=args.blockers,
        open_questions=args.open_questions,
    )
    print(json.dumps(envelope, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
