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
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        # Decode failure (API-15/CORR-15): try alternative encodings so a declared
        # value is classified rather than lost. A file whose body contains a
        # Latin-1 byte but whose frontmatter is valid should still return the
        # frontmatter value; a UTF-16 file should be sniffed.
        raw = path.read_bytes()
        for enc in ("utf-8-sig", "utf-16", "utf-16-le", "utf-16-be"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            try:
                text = raw.decode("utf-8-sig", errors="replace")
            except OSError:
                return "unknown:unreadable"
        # If the decoded text still contains no visible maturity declaration,
        # treat the file as unreadable rather than falling through to the path
        # rule — the file exists and was unreadable as UTF-8, so routing live
        # would be fail-open.
        if "maturity:" not in text:
            return "unknown:unreadable"
    except OSError:
        return "unknown:unreadable"
    if not text.startswith("---"):
        # Non-delimited carrier (AU-09): a `maturity:` mention in the first lines
        # means the document declares a maturity the delimited-block reader cannot
        # honour — fail closed with a carrier-distinguished sentinel, rather than
        # silently routing on the path default. No mention at all keeps the
        # legacy path-default behaviour.
        for line in text.splitlines()[:10]:
            stripped = line.strip()
            if stripped.lstrip("-*").strip().startswith("maturity:"):
                raw = stripped.split(":", 1)[1].strip() if ":" in stripped else ""
                raw = raw.strip("\"'").strip()
                if raw:
                    return f"unknown:carrier:{raw}"
                return "unknown:carrier:"
        return None
    end = text.find("\n---", 3)
    if end == -1:
        # Unterminated frontmatter block (API-13/CORR-15): opening delimiter present
        # but no closing delimiter — scan the opened block for a visible maturity
        # declaration and fail closed with a distinct sentinel rather than falling
        # through to the path rule.
        frontmatter = text[3:]
        for line in frontmatter.splitlines():
            if line.startswith("maturity:"):
                stripped = line.strip()
                value = stripped[len("maturity:") :].strip()
                if "#" in value:
                    value = value.split("#", 1)[0].strip()
                value = value.strip("\"'").strip()
                if not value:
                    return ""
                if value in HANDOFF_MATURITIES:
                    return f"unknown:unterminated:{value}"
                return f"unknown:unterminated:{value}"
            if line.strip().startswith("maturity:") and line[0] in (" ", "\t"):
                continue
        return None
    frontmatter = text[3:end]
    for line in frontmatter.splitlines():
        # Require unindented top-level key (API-03); ignore indented nested keys
        if line.startswith("maturity:"):
            stripped = line.strip()
            value = stripped[len("maturity:") :].strip()
            # Strip inline YAML comment
            if "#" in value:
                value = value.split("#", 1)[0].strip()
            value = value.strip("\"'").strip()
            if not value:
                return ""  # Empty maturity — signal, do not fall through
            if value in HANDOFF_MATURITIES:
                return value
            # Unrecognized non-empty — signal as unknown: (fail-closed)
            return f"unknown:{value}"
        if line.strip().startswith("maturity:") and line[0] in (" ", "\t"):
            # Indented nested key — ignore, not a top-level declaration
            continue
    return None


def infer_maturity(source: str, root: Path | None = None) -> str:
    normalized = source.replace("\\", "/")
    # Frontmatter-declared maturity wins when the source resolves to an existing file
    # that declares one (KTD7) — so a pending-confirmation checkpoint under
    # docs/brainstorms/ no longer hands off as requirements-ready.
    # Candidate resolution (SEC-01, fix-c23, CORR-13): the caller-declared root wins
    # over the process cwd in BOTH forms. For an absolute source outside the declared
    # root, re-anchor to the subpath below the marker directory and resolve under
    # `base`; accept the re-anchored candidate ONLY when it is an existing file —
    # otherwise read the original absolute path directly or fail closed with a
    # sentinel, never fall through to the path rule (which would route live).
    base = root or Path.cwd()
    absolute = Path(normalized).is_absolute()
    if absolute and root is not None and not Path(normalized).is_relative_to(base.resolve()):
        # Untrusted absolute input (root != cwd): try re-anchored subpath first.
        parts = Path(normalized).parts
        reanchored_normalized: str | None = None
        for marker in ("ideation", "brainstorms", "specs", "plans", "reviews", "work-sessions"):
            if marker in parts:
                idx = parts.index(marker)
                reanchored_normalized = "/".join(parts[idx - 1 :])
                break
        if reanchored_normalized is not None:
            reanchored_candidate = base / reanchored_normalized
            if reanchored_candidate.is_file():
                declared = _read_frontmatter_maturity(reanchored_candidate)
                if declared is not None:
                    return declared
                # Re-anchored file exists but declares no maturity — use its path
                # for the path-rule fallback below, not the original absolute.
                normalized = reanchored_normalized
                absolute = False
            else:
                # Re-anchored subpath does not exist under declared root — read
                # the original absolute file directly (the file the caller named)
                # or fail closed, never fall through to the path rule.
                original_candidate = Path(normalized)
                if original_candidate.is_file():
                    declared = _read_frontmatter_maturity(original_candidate)
                    if declared is not None:
                        return declared
                # Original also has no visible maturity — fall through using the
                # re-anchored subpath for the path-rule check (consistent marker-based path)
                normalized = reanchored_normalized
                absolute = False
        else:
            # No marker directory in absolute path — keep original absolute handling:
            # `base / normalized` with absolute RHS returns the absolute path itself.
            absolute = False
    candidate = Path(normalized) if absolute else base / normalized
    if candidate.is_file():
        declared = _read_frontmatter_maturity(candidate)
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
    if maturity.startswith("unknown:"):
        # Bound the raw author-controlled value so unbounded artifact text cannot
        # enter the published JSON field (API-12); the diagnostic tail is redundant
        # with suggested_command, so the bound only ever shortens machine input.
        maturity = "unknown:" + maturity[len("unknown:") :][:120]
    # Fail-closed for unrecognized/empty maturity (API-03) and pending-confirmation
    if maturity == "pending-confirmation":
        suggested_command = (
            f"Boundary recorded but unconfirmed for {selected_source} — "
            "no durable route exists until the operator confirms in Brainstorm Phase 2.5"
        )
    elif maturity == "" or maturity.startswith("unknown:"):
        if maturity.startswith("unknown:carrier:"):
            raw = maturity.removeprefix("unknown:carrier:")
            suggested_command = (
                f"Frontmatter carrier missing delimiters for {selected_source} — "
                f"maturity {raw!r} declared outside a delimited YAML block; "
                f"no durable route; fix frontmatter to be delimited by literal --- lines "
                f"with an unindented maturity: key"
            )
        elif maturity.startswith("unknown:unterminated:"):
            raw = maturity.removeprefix("unknown:unterminated:")
            suggested_command = (
                f"Unterminated frontmatter block for {selected_source} — "
                f"maturity {raw!r} declared but closing --- missing; "
                f"no durable route; fix frontmatter to close the block"
            )
        elif maturity == "unknown:unreadable":
            suggested_command = (
                f"Unreadable frontmatter for {selected_source} — "
                f"file could not be read or decoded; no durable route"
            )
        else:
            raw = (
                maturity.removeprefix("unknown:") if maturity.startswith("unknown:") else "(empty)"
            )
            suggested_command = (
                f"Unrecognized maturity {raw!r} for {selected_source} — "
                "no durable route; fix frontmatter to one of "
                f"{', '.join(HANDOFF_MATURITIES)}"
            )
        # Keep handoff_maturity as the raw signal for diagnostics, but do not emit a route
    else:
        suggested_command = f"/issue --prepare --from {selected_source} --maturity {maturity}"
        if target_team:
            suggested_command += f" for {target_team}"
        if target_repo:
            suggested_command += f" in {target_repo}"

    return {
        "schema_version": "1.1",
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
