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
import shlex
import subprocess
import sys
from pathlib import Path

_MANIFEST_REL = Path("tools") / "gate-manifest.json"

# Fallback per-step budget when a manifest step declares no ``timeout_seconds``.
# Steps that legitimately need longer say so in the manifest (issue #658).
_DEFAULT_STEP_TIMEOUT = 300


# git's own global options, i.e. the ones that may appear BEFORE the subcommand. Split by
# whether they consume a following token, so the subcommand scan can skip an option's value
# without mistaking it for the subcommand (`git -C /repo push` must not read `/repo` as the
# subcommand). Long `--opt=value` forms are self-contained and need no entry here.
_GIT_GLOBAL_OPTS_WITH_VALUE = frozenset(
    {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--config-env"}
)
_GIT_GLOBAL_FLAGS = frozenset(
    {
        "-p",
        "-P",
        "--paginate",
        "--no-pager",
        "--no-replace-objects",
        "--bare",
        "--literal-pathspecs",
        "--glob-pathspecs",
        "--noglob-pathspecs",
        "--icase-pathspecs",
        "--no-optional-locks",
    }
)

# Shell operators that end one command and begin another.
_SEGMENT_SEPARATORS = frozenset({"|", "||", "&&", ";", "&", "\n"})


def _segments(command: str) -> list[list[str]]:
    """Split a shell command into token lists, one per pipeline/list segment.

    Uses ``shlex`` so quoting is honored: the tokens of ``git commit -m 'git push now'``
    carry the message as ONE token, which is what makes subcommand identification possible
    at all. An unparseable command (unbalanced quotes) yields no segments, so the caller
    degrades to not gating rather than guessing.
    """
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        return []
    segments: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        if token in _SEGMENT_SEPARATORS:
            segments.append(current)
            current = []
        else:
            current.append(token)
    segments.append(current)
    return [s for s in segments if s]


def _git_invocations(command: str) -> list[list[str]]:
    """Every ``git`` invocation in the command, as its own token list.

    A segment's git call is its FIRST token (``git push``) or the token right after an
    ``env``-style prefix or a ``cd <path> &&`` that shlex already split into its own segment.
    ``echo 'git push'`` yields nothing because ``git`` is inside a quoted token, not a
    command head.
    """
    found: list[list[str]] = []
    for segment in _segments(command):
        head = 0
        # Skip a leading `env VAR=value ...` or bare `VAR=value` assignments.
        while head < len(segment) and (segment[head] == "env" or "=" in segment[head].split()[0]):
            if segment[head] == "env":
                head += 1
                continue
            if "=" in segment[head] and not segment[head].startswith("-"):
                head += 1
                continue
            break
        if head < len(segment) and Path(segment[head]).name == "git":
            found.append(segment[head:])
    return found


def _git_subcommand(invocation: list[str]) -> tuple[str | None, str | None]:
    """Return ``(subcommand, target_path)`` for one ``git`` token list.

    Walks git's global options -- skipping an option's value where it takes one -- and returns
    the first non-option token as the SUBCOMMAND. This is the fix for #663 fault (b): the old
    regex matched the word ``push`` anywhere in the argument span, so ``git add
    docs/push-notes.md``, ``git log --grep=push``, and ``git commit -m "... push ..."`` all ran
    the full gate suite. A token list knows the difference between a subcommand and an argument.

    ``target_path`` is ``-C <path>`` / ``--git-dir=<path>`` / ``--work-tree=<path>`` when given
    -- #663 fault (a): resolving the repo from the invocation rather than the session cwd is what
    lets a push aimed elsewhere reach that repo's manifest, or fall through the cross-repo exit.
    """
    target: str | None = None
    i = 1  # token 0 is `git`
    while i < len(invocation):
        token = invocation[i]
        if not token.startswith("-"):
            return token, target
        name, sep, value = token.partition("=")
        if sep and name in _GIT_GLOBAL_OPTS_WITH_VALUE:
            if name in ("--git-dir", "--work-tree"):
                target = value
            i += 1
            continue
        if token in _GIT_GLOBAL_OPTS_WITH_VALUE:
            if i + 1 < len(invocation):
                if token in ("-C", "--git-dir", "--work-tree"):
                    target = invocation[i + 1]
                i += 2
                continue
            return None, target
        if token in _GIT_GLOBAL_FLAGS:
            i += 1
            continue
        # An unrecognized option before the subcommand: skip it rather than guess it is the
        # subcommand. Unknown never reads as `push`, so the gate stays off by default.
        i += 1
    return None, target


def _push_target(command: str) -> tuple[bool, str | None]:
    """``(is_push, target_path)`` for the whole command.

    True when ANY segment's git invocation has ``push`` as its actual subcommand. A compound
    like ``git add -A && git push`` is still a push.
    """
    for invocation in _git_invocations(command):
        subcommand, target = _git_subcommand(invocation)
        if subcommand == "push":
            return True, target
    return False, None


def _cd_target(command: str) -> str | None:
    """Path from a leading ``cd <path> &&`` prefix, if any.

    #663 fault (a) observed live: ``cd <other-repo> && git push`` resolved to the SESSION repo,
    so this repo's ~5500-test suite ran against a push aimed elsewhere and blocked it on 17
    unrelated failures. The missing-manifest cross-repo exit could not save it, because the
    session repo does have a manifest.
    """
    for segment in _segments(command):
        if len(segment) >= 2 and segment[0] == "cd":
            return segment[1]
    return None


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

    is_push, target = _push_target(command)
    if not is_push:
        sys.exit(0)

    # Resolve the repo from the INVOCATION (`git -C` / `--git-dir` / `--work-tree`), then from a
    # leading `cd <path> &&`, and only then from the session cwd (#663 fault (a)). Resolving from
    # cwd first is what ran this repo's suite against a push aimed at another repo.
    cwd_str = target or _cd_target(command)
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
