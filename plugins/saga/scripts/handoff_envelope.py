#!/usr/bin/env python3
"""Build a thin Infiquetra loop handoff envelope for mission-control."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

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

#: The subset whose `suggested_command` is runnable. `pending-confirmation` is a member of
#: HANDOFF_MATURITIES but carries no durable route, so offering it as a remediation target
#: sends the author straight back to the same diagnostic (API-25).
ROUTABLE_MATURITIES = tuple(m for m in HANDOFF_MATURITIES if m != "pending-confirmation")

# Derived from SOURCE_DIRS to avoid a second literal that must be kept in sync.
# Used for re-anchoring an absolute source outside the declared root to its
# marker-directory subpath.
MARKER_DIRS = tuple(p.name for p in SOURCE_DIRS)

# Bounded read size for frontmatter scan to avoid amplifying memory on large files.
_FRONTMATTER_READ_LIMIT = 8192


def _extract_declared_maturity_value(line: str, allow_bullet: bool = False) -> str | None:
    """Extract a ``maturity:`` value from a single frontmatter line.

    When ``allow_bullet`` is False (delimited frontmatter), only an unindented
    top-level ``maturity:`` at column 0 is accepted. When True (carrier and
    unterminated arms), a bullet- or indent-prefixed ``maturity:`` is also
    accepted, so both arms share one notion of a declaration line. Inline-comment
    and quote stripping is centralized here.
    """
    if allow_bullet:
        stripped = line.strip()
        cleaned = stripped.lstrip("-*").strip()
        if not cleaned.startswith("maturity:"):
            return None
        # Do not treat an indented line that is not a bullet as a top-level key
        # when allow_bullet is True — the carrier/unterminated arms intentionally
        # accept both, so any line whose stripped form starts with maturity: is a hit.
        value = cleaned[len("maturity:") :].strip()
    else:
        if not line.startswith("maturity:"):
            if line.strip().startswith("maturity:") and line[0] in (" ", "\t"):
                return None
            return None
        stripped = line.strip()
        value = stripped[len("maturity:") :].strip()
    if "#" in value:
        value = value.split("#", 1)[0].strip()
    value = value.strip("\"'").strip()
    # Caller distinguishes empty vs non-empty; return empty string for blank.
    return value


def _read_frontmatter_maturity(path: Path) -> str | None:
    try:
        with path.open("rb") as f:
            raw_bytes = f.read(_FRONTMATTER_READ_LIMIT)
            # If we hit the limit and the file is larger, the slice may end mid-codepoint.
            # Trim trailing partial UTF-8 sequence so a valid file is not mis-marked unreadable
            # (SEC-09). Only trim when the file has more bytes beyond the limit.
            if len(raw_bytes) == _FRONTMATTER_READ_LIMIT:
                try:
                    peek = f.read(1)
                except OSError:
                    peek = b""
                if peek:
                    # File is larger than the limit; ensure the slice ends on a character boundary.
                    while raw_bytes:
                        try:
                            raw_bytes.decode("utf-8-sig")
                            break
                        except UnicodeDecodeError as e:
                            if "unexpected end of data" in str(e):
                                raw_bytes = raw_bytes[:-1]
                                continue
                            break
    except OSError:
        return "unknown:unreadable"
    # Decode with UTF-8-SIG, handling BOM. NUL bytes are valid UTF-8 but indicate
    # UTF-16 without BOM or binary corruption — reject a successful decode that
    # contains NUL and route it into the recovery ladder (API-18/CORR-22).
    text: str | None = None
    try:
        text = raw_bytes.decode("utf-8-sig")
        if "\x00" in text:
            raise UnicodeDecodeError("utf-8-sig", raw_bytes, 0, 1, "NUL byte in decoded text")
    except UnicodeDecodeError:
        if raw_bytes.startswith((b"\xff\xfe", b"\xfe\xff")) or b"\x00" in raw_bytes:
            for enc in ("utf-16", "utf-16-le", "utf-16-be"):
                try:
                    candidate = raw_bytes.decode(enc)
                except UnicodeDecodeError:
                    continue
                # Only accept a UTF-16 decode that actually contains a maturity declaration;
                # otherwise it is mojibake and should be treated as unreadable (API-18).
                if "maturity:" not in candidate:
                    continue
                text = candidate
                break
        if text is None:
            try:
                text = raw_bytes.decode("utf-8-sig", errors="replace")
            except OSError:
                return "unknown:unreadable"
            if "maturity:" not in text:
                return "unknown:unreadable"
    if text is None:
        return "unknown:unreadable"
    # Also reject a successful UTF-8 decode that produced NUL-interleaved text but did not
    # raise — this is the BOM-less UTF-16 case that decodes as valid UTF-8 with NULs.
    if "\x00" in text:
        return "unknown:unreadable"
    if not text.startswith("---"):
        # Non-delimited carrier (AU-09): scan the leading block rather than a fixed
        # 10-line window, iterating until the first blank-line-separated prose
        # paragraph or a hard cap, so a maturity on line 11 is not missed.
        lines = text.splitlines()
        scan_limit = 30
        for idx, line in enumerate(lines):
            if idx >= scan_limit:
                break
            extracted = _extract_declared_maturity_value(line, allow_bullet=True)
            if extracted is not None:
                if extracted:
                    return f"unknown:carrier:{extracted}"
                return "unknown:carrier:"
        return None
    end = text.find("\n---", 3)
    if end == -1:
        # Unterminated frontmatter block (API-13/CORR-15): opening delimiter present
        # but no closing delimiter — scan the opened block for a visible maturity
        # declaration and fail closed with a distinct sentinel rather than falling
        # through to the path rule. Both arms share one notion of a declaration line
        # (accept bullet and indented forms), so no shape can fail closed under one
        # arm and route live under another.
        frontmatter = text[3:]
        for line in frontmatter.splitlines():
            extracted = _extract_declared_maturity_value(line, allow_bullet=True)
            if extracted is not None:
                if not extracted:
                    return "unknown:unterminated:"
                return f"unknown:unterminated:{extracted}"
            if line.strip().startswith("maturity:") and line[0] in (" ", "\t"):
                continue
        return None
    frontmatter = text[3:end]
    # Only a top-level YAML mapping key declares a maturity (AM-35/CORR-28/CORR-29).
    # Every other in-block appearance fails closed as unknown:carrier: rather than
    # falling through to the path rule. A line scan cannot make this distinction: a
    # sequence item at column 0 is nested under the preceding key, not top-level.

    def _scanned_maturity_line() -> str | None:
        for line in frontmatter.splitlines():
            probe = line.strip().lstrip("-*").strip()
            if probe.startswith("maturity:"):
                return probe[len("maturity:") :].strip().strip("\"'").strip()
        return None

    def _carrier(value: str | None) -> str:
        return f"unknown:carrier:{value}" if value else "unknown:carrier:"

    def _has_nested_maturity(node: object) -> bool:
        if isinstance(node, dict):
            return any(key == "maturity" or _has_nested_maturity(val) for key, val in node.items())
        if isinstance(node, list):
            return any(_has_nested_maturity(item) for item in node)
        return False

    try:
        parsed = yaml.safe_load(frontmatter)
    except yaml.YAMLError:
        scanned = _scanned_maturity_line()
        return None if scanned is None else _carrier(scanned)
    if isinstance(parsed, dict) and "maturity" in parsed:
        raw = parsed["maturity"]
        value = "" if raw is None else str(raw).strip()
        if not value:
            return ""  # Empty maturity — signal, do not fall through
        if value in HANDOFF_MATURITIES:
            return value
        # Unrecognized non-empty — signal as unknown:unrecognized: (reserved namespace)
        return f"unknown:unrecognized:{value}"
    scanned = _scanned_maturity_line()
    if scanned is not None or _has_nested_maturity(parsed):
        return _carrier(scanned)
    return None


def _is_within(candidate: Path, base: Path) -> bool:
    """True when CANDIDATE resolves inside BASE.

    Both sides are resolved, so a parent segment cannot spell its way past a lexical
    comparison (SEC-16). A path that cannot be resolved is treated as outside.
    """
    try:
        return candidate.resolve().is_relative_to(base.resolve())
    except (OSError, ValueError):
        return False


def _reanchor_to_marker(normalized: str) -> str | None:
    """Return NORMALIZED's marker-directory subpath, or None when it carries no marker.

    Single owner for re-anchoring (AM-28). Both `infer_maturity` and `build_handoff_envelope`
    consume this, so which path was chosen cannot diverge between the maturity decision and
    the path the envelope publishes.
    """
    parts = Path(normalized).parts
    for marker in MARKER_DIRS:
        if marker in parts:
            idx = parts.index(marker)
            # Guard against a zero index so the slice can never re-include the path anchor.
            return "/".join(parts[idx - 1 :] if idx > 0 else parts[idx:])
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
    # otherwise read the original absolute path directly. Three outcomes are possible:
    # the re-anchored file is read, the original absolute file is read, or the source is
    # refused. A
    # path carrying no marker directory never enters this branch at all and always
    # resolves by the path rule.
    base = root or Path.cwd()
    absolute = Path(normalized).is_absolute()
    if absolute and root is not None and not _is_within(Path(normalized), base):
        # Untrusted absolute input (root != cwd): try re-anchored subpath first.
        reanchored_normalized = _reanchor_to_marker(normalized)
        if reanchored_normalized is not None:
            # Check containment before reading: re-anchored candidate must be inside base.
            reanchored_candidate = base / reanchored_normalized
            try:
                resolved_reanchored = reanchored_candidate.resolve()
                resolved_base = base.resolve()
                is_contained = resolved_reanchored.is_relative_to(resolved_base)
            except (OSError, ValueError):
                is_contained = False
            if is_contained and reanchored_candidate.is_file():
                declared = _read_frontmatter_maturity(reanchored_candidate)
                if declared is not None:
                    return declared
                return f"unknown:out-of-root:{normalized}"
            else:
                # Re-anchored subpath does not exist or not contained — read the
                # original absolute file directly (the file the caller named). When
                # that file also declares nothing, control DOES reach the path rule
                # below and can route live; the release note states this.
                original_candidate = Path(normalized)
                if original_candidate.is_file():
                    declared = _read_frontmatter_maturity(original_candidate)
                    if declared is not None:
                        return declared
                return f"unknown:out-of-root:{normalized}"
        else:
            # No marker directory in absolute path — keep original absolute handling:
            # `base / normalized` with absolute RHS returns the absolute path itself.
            absolute = False
    # Resolve candidate with containment check (SEC-04).
    candidate = Path(normalized) if absolute else base / normalized
    if absolute:
        # Absolute path explicitly named by caller — read directly if file exists.
        if candidate.is_file():
            declared = _read_frontmatter_maturity(candidate)
            if declared is not None:
                return declared
    else:
        # Relative path — require containment before reading to prevent directory traversal.
        if _is_within(candidate, base):
            if candidate.is_file():
                declared = _read_frontmatter_maturity(candidate)
                if declared is not None:
                    return declared
        else:
            # Outside the declared root: refuse rather than fall through (SEC-15). The path
            # rule below would route this live, so falling through would give one file
            # opposite gate decisions depending only on how its path is spelled.
            return f"unknown:out-of-root:{normalized}"
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
        # Use lstat to avoid following directory symlinks that could escape root (SEC-04).
        try:
            if not directory.exists() or directory.is_symlink():
                continue
        except OSError:
            continue
        # Collect candidates but skip file symlinks that escape containment.
        for path in directory.rglob("*.md"):
            if not path.is_file() or path.is_symlink():
                continue
            try:
                if not path.resolve().is_relative_to(directory.resolve()):
                    continue
            except (OSError, ValueError):
                continue
            candidates.append(path)
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

    # Track whether source was re-anchored to attribute correctly (CORR-18).
    original_selected_source = selected_source
    # If selected_source is absolute outside root and re-anchored, update source to actual file read.
    if Path(selected_source).is_absolute() and root is not None:
        try:
            if not _is_within(Path(selected_source), root):
                reanchored = _reanchor_to_marker(selected_source)
                if reanchored is not None:
                    reanchored_candidate = root / reanchored
                    if _is_within(reanchored_candidate, root) and reanchored_candidate.is_file():
                        selected_source = reanchored
        except (OSError, ValueError):
            pass

    maturity = infer_maturity(selected_source, root)
    # Keep original source for diagnostic if re-anchoring occurred
    reanchored_diagnostic = ""
    if original_selected_source != selected_source:
        reanchored_diagnostic = (
            f" (re-anchored from {original_selected_source!r} to {selected_source!r})"
        )
    if maturity.startswith("unknown:"):
        # Bound the raw author-controlled value so unbounded artifact text cannot
        # enter the published JSON field (API-12); the diagnostic tail is redundant
        # with suggested_command, so the bound only ever shortens machine input.
        body = maturity[len("unknown:") :]
        # Mark the loss: without the ellipsis the diagnostic quotes a value that does not
        # appear anywhere in the artifact, and the author cannot tell it was truncated (AU-28).
        maturity = "unknown:" + (body[:120] + "…" if len(body) > 120 else body)
    # Fail-closed for unrecognized/empty maturity (API-03) and pending-confirmation
    if maturity == "pending-confirmation":
        suggested_command = (
            f"Boundary recorded but unconfirmed for {selected_source}{reanchored_diagnostic} — "
            "no durable route exists until the operator confirms in Brainstorm Phase 2.5"
        )
    elif maturity == "" or maturity.startswith("unknown:"):
        if maturity.startswith("unknown:carrier:"):
            raw = maturity.removeprefix("unknown:carrier:")
            suggested_command = (
                f"Frontmatter carrier missing delimiters for {selected_source}{reanchored_diagnostic} — "
                f"maturity {raw!r} declared outside a delimited YAML block; "
                f"no durable route; fix frontmatter to be delimited by literal --- lines "
                f"with a top-level maturity: key"
            )
        elif maturity.startswith("unknown:unterminated:"):
            raw = maturity.removeprefix("unknown:unterminated:")
            suggested_command = (
                f"Unterminated frontmatter block for {selected_source}{reanchored_diagnostic} — "
                f"maturity {raw!r} declared but closing --- missing; "
                f"no durable route; fix frontmatter to close the block"
            )
        elif maturity.startswith("unknown:out-of-root:"):
            raw = maturity.removeprefix("unknown:out-of-root:")
            suggested_command = (
                f"Source outside the declared root for {selected_source}{reanchored_diagnostic} — "
                f"{raw!r} resolves outside the root this handoff was given; no durable route; "
                f"name a source inside the declared root"
            )
        elif maturity == "unknown:unreadable":
            suggested_command = (
                f"Unreadable frontmatter for {selected_source}{reanchored_diagnostic} — "
                f"file could not be opened, or decoded into text carrying a maturity "
                f"declaration; no durable route; re-save the file as UTF-8 with a closed "
                f"--- block and a top-level maturity: key, then re-run"
            )
        elif maturity.startswith("unknown:unrecognized:"):
            raw = maturity.removeprefix("unknown:unrecognized:")
            suggested_command = (
                f"Unrecognized maturity {raw!r} for {selected_source}{reanchored_diagnostic} — "
                "no durable route; fix frontmatter to one of "
                f"{', '.join(ROUTABLE_MATURITIES)}"
            )
        else:
            # Fallback for legacy unknown: prefix (should not occur after namespace reservation)
            raw = (
                maturity.removeprefix("unknown:") if maturity.startswith("unknown:") else "(empty)"
            )
            suggested_command = (
                f"Unrecognized maturity {raw!r} for {selected_source}{reanchored_diagnostic} — "
                "no durable route; fix frontmatter to one of "
                f"{', '.join(ROUTABLE_MATURITIES)}"
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
