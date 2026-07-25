#!/usr/bin/env python3
"""
PreToolUse hook: run the pre-push gate and report by exception.

Fires when the Bash tool runs a `git push` command.  Reads the single-source
gate manifest at ``tools/gate-manifest.json`` (relative to the repo root) and
executes every step in order.  Passes silently on success (report by
exception).  On any failure, prints the step label, its output, and the
failure hint to stderr, then exits 2 (blocking) to prevent the push.

Properties:
  - SILENT ON PASS: no output when every step is green.
  - BLOCKING ON FAILURE: exits 2, which prevents the push.
  - SINGLE SOURCE: adding or removing steps in gate-manifest.json — or
    retuning one via its optional ``timeout_seconds`` — is the only change
    needed to update the gate; this script never diverges.
  - CROSS-REPO-SAFE: degrades silently when the manifest is absent (so the
    hook can be registered globally without breaking repos that lack one).

Exit codes:
  0 — all steps passed (or not a push command / manifest absent).
  2 — one or more steps failed (blocking).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

_MANIFEST_REL = Path("tools") / "gate-manifest.json"

# Fallback per-step budget when a manifest step declares no ``timeout_seconds``.
# Steps that legitimately need longer say so in the manifest (issue #658).
_DEFAULT_STEP_TIMEOUT = 300


def _is_git_push_command(command: str) -> bool:
    """
    Return True if the shell command invokes `git push`.

    Matches:
      git push ...
      git -C /path push ...
      git push --force-with-lease

    Does NOT match:
      echo 'git push'      (git not at command boundary)
      git commit -m 'msg'  (different subcommand)
      git pull ...         (different subcommand)
    """
    # git is the first token of a pipeline segment (start of string or after
    # a pipe/semicolon/&&/||), followed by optional flags+values, then `push`.
    # `-C <path>` uses a separate token for the value, so we allow arbitrary
    # intervening non-push tokens before the `push` subcommand.
    return bool(re.search(r"(?:^|[|;&])\s*git\b[^|;&]*\bpush\b", command))


def _find_repo_root(cwd: str | None) -> Path | None:
    """Return the git repository root, or None if not inside a repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=5,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
    except Exception:
        pass
    return None


def _parse_git_dash_c(command: str) -> str | None:
    """Return the path from `git -C <path>` if present, else None."""
    m = re.search(r"\bgit\s+-C\s+(['\"]?)([^'\" ]+)\1", command)
    if m:
        return m.group(2)
    return None


def _run_step(step: dict, cwd: Path) -> tuple[bool, str]:
    """
    Run a single gate step.

    Returns (passed, output) where output is combined stdout+stderr
    (empty string on pass — caller decides whether to surface it).
    """
    cmd: list[str] = step.get("command", [])
    if not cmd:
        return True, ""

    # Per-step budget, from the manifest, defaulting to the historical 300 s (issue
    # #658). The timeout used to be hardcoded here, which broke the SINGLE SOURCE
    # property above: tuning the gate meant editing the hook, not the manifest. It also
    # failed the wrong way — the suite grew past 300 s while still passing, so the gate
    # blocked every push in the repo reporting a timeout rather than a test failure,
    # which reads identically to a real red at the call site.
    timeout_seconds = step.get("timeout_seconds", _DEFAULT_STEP_TIMEOUT)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(cwd),
            timeout=timeout_seconds,
        )
    except FileNotFoundError:
        return False, f"command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return False, f"timed out after {timeout_seconds} s"
    except Exception as exc:
        return False, str(exc)

    if result.returncode == 0:
        return True, ""

    combined = "\n".join(part for part in (result.stdout.rstrip(), result.stderr.rstrip()) if part)
    return False, combined


def main() -> None:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw)
    except Exception:
        # Malformed envelope — pass through silently.
        sys.exit(0)

    tool_name: str = payload.get("tool_name", "")
    tool_input: dict = payload.get("tool_input", {})

    if tool_name != "Bash":
        sys.exit(0)

    command: str = tool_input.get("command", "")

    if not _is_git_push_command(command):
        sys.exit(0)

    # Determine the repo root from `git -C <path>` or cwd.
    cwd_str = _parse_git_dash_c(command)
    repo_root = _find_repo_root(cwd_str)

    if repo_root is None:
        # Not inside a git repo — degrade silently.
        sys.exit(0)

    manifest_path = repo_root / _MANIFEST_REL
    if not manifest_path.exists():
        # No manifest — degrade silently (cross-repo safety).
        sys.exit(0)

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(
            f"[saga/pre-push-gate] Cannot read gate manifest: {exc}",
            file=sys.stderr,
        )
        sys.exit(0)  # Manifest unreadable — degrade silently rather than blocking.

    steps: list[dict] = manifest.get("steps", [])
    if not steps:
        sys.exit(0)

    failures: list[tuple[str, str, str]] = []  # (label, output, hint)

    for step in steps:
        label: str = step.get("label", step.get("id", "unknown"))
        passed, output = _run_step(step, repo_root)
        if not passed:
            hint: str = step.get("failure_hint", "")
            failures.append((label, output, hint))

    if not failures:
        # All green — silent pass (report by exception).
        sys.exit(0)

    # Report failures and block the push.
    print(
        f"[saga/pre-push-gate] {len(failures)} gate step(s) failed — push blocked.\n",
        file=sys.stderr,
    )
    for label, output, hint in failures:
        print(f"  FAIL: {label}", file=sys.stderr)
        if output:
            for line in output.splitlines():
                print(f"    {line}", file=sys.stderr)
        if hint:
            print(f"    Hint: {hint}", file=sys.stderr)
        print(file=sys.stderr)

    sys.exit(2)


if __name__ == "__main__":
    main()
