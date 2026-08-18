#!/usr/bin/env python3
"""Run a plan of units across herdr agent sessions, one git worktree each.

The plan is authored by the operator and Claude together; this script is the mechanical half.
It creates a worktree and branch per unit, launches the requested agent there, sends the unit's
saga command, waits, merges the branches back, and cleans up.

State is one JSON file, plus one file each for tasks too long to live in it. If it is wrong,
delete it -- `herdr agent list` is the real truth.
"""

from __future__ import annotations

import argparse
import contextlib
import glob
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import textwrap
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# Ships beside this file. Kept optional so a partial install degrades to per-unit waits rather
# than refusing to run at all.
try:
    import herdr_events
except ImportError:  # pragma: no cover - only when the sibling module is missing
    herdr_events = None  # type: ignore[assignment]

RUN_FILE = Path(".orchestrate/run.json")

# Where task text lives when it does not belong inside run.json. Two mechanisms write here,
# named apart: the spill (see ``TASK_SPILL_THRESHOLD``) moves a long unit task out of the run
# record at save time, and ``pane_text`` hands a too-long-to-type task to a session as a file.
TASK_DIR = RUN_FILE.parent / "tasks"

# A task longer than this is spilled to ``TASK_DIR / f"{unit.name}.task.md"`` at save time, and
# the record keeps a pointer instead. Measured on a real 75-unit run: run.json was 267,897 bytes
# and 223,040 of them -- 83% -- were unit task text, rewritten whole on every save and parsed by
# every subcommand. This threshold is about the record, not the session: what a pane will carry
# as typed input is a different limit with its own mechanism (``PANE_TYPING_LIMIT``).
TASK_SPILL_THRESHOLD = 400

# How each agent takes a model and a reasoning effort on its own command line, read from each
# tool's own `--help`. Anything not listed launches with no tier flags -- see SETUP_HINT for how a
# unit still sets its tier in that case.
#
# Verify with `roster --probe` after an agent updates. This table went stale once: claude and agy
# both grew an --effort flag, muse arrived with one, and opencode's -m turned out to belong to its
# `run` subcommand rather than the interactive session orchestrate launches. Every one of those was
# silent -- the tier was simply not applied.
VENDOR_FLAGS: dict[str, dict[str, str]] = {
    "claude": {"model": "--model {value}", "effort": "--effort {value}"},
    "codex": {"model": "--model {value}", "effort": "-c model_reasoning_effort={value}"},
    "grok": {"model": "-m {value}", "effort": "--reasoning-effort {value}"},
    "muse": {"model": "--model {value}", "effort": "--reasoning-effort {value}"},
    "agy": {"model": "--model {value}", "effort": "--effort {value}"},
    "qwen": {"model": "-m {value}"},
    # opencode wants the model as `provider/model`, e.g. `deepseek/deepseek-v4-pro`; a bare name is
    # rejected at startup with "Invalid model format".
    "opencode": {"model": "-m {value}"},
}

# Where a tool has no launch flag for something, the session is told after it starts. Every agent
# here takes slash commands, so tier is always settable -- through the command line where one
# exists, and through the session where one does not.
# What is worth knowing about a vendor that no other table has room for.
#
# Every one of these was learned by a run going wrong, and each was re-learned at least once because
# it lived nowhere. `roster` prints them, so the interview reads how a vendor behaves rather than
# recalling it -- which is the failure this is for: an orchestrator that guesses, plausibly, and is
# only found out a phase later.
VENDOR_NOTES: dict[str, str] = {
    "qwen": (
        "never reports interactive readiness, so its task is typed into the pane rather than "
        "prompted, and a task over the typing limit is handed over as a file. `--yolo` is real and "
        "absent from `--help`. NEVER pass `--safe-mode`: it reads like the opposite of `--yolo` and "
        "disables every customization, including the extensions saga loads."
    ),
    "muse": (
        "approval and the sandbox are ON by default. `--yolo` disables BOTH and is bypass, not "
        "auto; the ladder is `--approval-mode untrusted|on-request|never`."
    ),
    "opencode": (
        "effort is a variant -- Default, high, max -- chosen through `/variants`, which opens a "
        "picker rather than taking an argument. A picker cannot be answered from a `setup` line in "
        "an unwatched tab, so a dispatched unit runs at whatever variant was last selected. Offer "
        "it on its model and leave the variant to the operator. Its model wants `provider/model`; a "
        "bare name is rejected at startup."
    ),
    "agy": (
        "its saga plugin is a symlink into the operator's own checkout under the Gemini config "
        "directory, not a fetched cache -- so a search for directories named `saga` finds only the "
        "saga state and concludes it has none."
    ),
    "codex": "saga ships as skills under the `saga` namespace with no command directory, and "
    "prefixes with `$` rather than `/`.",
}

SETUP_HINT = "no {what} flag on the command line; set it with a slash command in `setup`"

# Vendors that can be asked which models they have. The rest cannot answer, so their model name
# comes from the operator rather than from anyone's recollection.
MODEL_LIST: dict[str, list[str]] = {
    "grok": ["models"],
    "agy": ["models"],
    "opencode": ["models"],
}

# What each vendor needs in order to actually do work in the worktree it was handed.
#
# Without this, every unit runs at its vendor's default -- read-only, or ask-first in a tab nobody
# is watching. Two competing plans were once produced at xhigh over twelve minutes and both were
# lost, because neither session could save a file: codex answered "I can't write", claude sat in
# plan mode. A worktree a unit cannot write to is not isolation, it is theatre.
#
# Two levels. ``auto`` is the default and means "get on with the task without asking" -- claude and
# grok share that exact vocabulary. ``bypass`` is the operator's everyday mode, granted per unit
# when the work needs it. Either way the worktree is the blast radius: a unit reaches its own tree
# and nothing else. A vendor with an empty list already behaves that way unflagged.
VENDOR_PERMISSION: dict[str, dict[str, list[str]]] = {
    "claude": {
        "auto": ["--permission-mode", "auto"],
        "bypass": ["--permission-mode", "bypassPermissions"],
    },
    "grok": {
        "auto": ["--always-approve", "auto"],
        "bypass": ["--always-approve", "bypassPermissions"],
    },
    "codex": {
        "auto": ["--sandbox", "workspace-write"],
        "bypass": ["--dangerously-bypass-approvals-and-sandbox"],
    },
    "agy": {"auto": [], "bypass": ["--dangerously-skip-permissions"]},
    # opencode has one switch and no ladder, so both modes are the same flag. Recorded as it is
    # rather than papered over: asking for `auto` here genuinely gets you `bypass`.
    "opencode": {"auto": ["--auto"], "bypass": ["--auto"]},
    # muse's own help: approval and the sandbox are ON by default, `--approval-mode` takes
    # untrusted|on-request|never, and `--yolo` means "disable approval and sandboxing and trust
    # this workspace". Both modes were once `--yolo`, so asking for the constrained mode handed the
    # unit full bypass -- a safety claim backwards. `never` is the honest `auto`: it stops asking
    # without dropping the sandbox.
    "muse": {"auto": ["--approval-mode", "never"], "bypass": ["--yolo"]},
    # `--yolo` is absent from `qwen --help` and works anyway -- verified by running it, against a
    # control showing qwen rejects an unknown flag with "Unknown arguments". Its own warning names
    # the equivalent: "running headless with --yolo / approval-mode=yolo and no sandbox".
    #
    # Do NOT reach for `--safe-mode` here. It reads like the opposite of `--yolo` and is not a
    # permission flag at all: it disables all customizations -- context files, hooks, extensions --
    # which is exactly what saga needs loaded.
    "qwen": {"auto": [], "bypass": ["--yolo"]},
}

# Where each vendor keeps its saga install, so "does this vendor have saga" is resolved rather than
# believed. Checked by `saga --check`. A vendor absent here, or whose globs match nothing, cannot
# run a saga capability at all -- agy and muse are in that position today, and a saga task sent to
# them does nothing no matter what prefix it carries.
SAGA_INSTALL: dict[str, list[str]] = {
    "claude": ["~/.claude/plugins/cache/*/saga/*/commands"],
    "codex": ["~/.codex/plugins/cache/*/saga/*/skills"],
    "grok": ["~/.grok/marketplace-cache/*/plugins/saga/commands"],
    "qwen": ["~/.qwen/extensions/saga/commands"],
    "opencode": ["~/.config/opencode/commands"],
    # agy is Antigravity, and its home is the Gemini config directory. The plugin there is a
    # *symlink* into the operator's own antigravity-plugins checkout rather than a fetched cache,
    # which is why a search for directories named `saga` finds only `~/.gemini/saga` -- the saga
    # state, not the commands. `glob` resolves the link, so one concrete path is enough.
    "agy": ["~/.gemini/config/plugins/saga/commands"],
}

# How each vendor names a saga capability. Saga is installed for most of them, but the invocation
# differs -- and a bare "/plan" is a command nowhere, so it arrives as prose the agent may or may
# not act on. That is how a "/plan" unit once produced claude's own built-in plan mode instead.
# `normalize_task` applies this at send time, so the interview writes one form for everybody.
#
# claude and grok/qwen/opencode were read off their installed command files; codex's saga ships
# skills under the `saga` namespace with no command directory at all (its PORTABILITY.md says so),
# and codex prefixes with `$`.
# Saga stages that stop and ask the operator which execution backend to use. `/work` offers it
# unconditionally -- there is no skip-if-already-decided path in its contract -- and an
# `AskUserQuestion` in a background tab waits forever. Unlike saga's engine offer there is no stored
# preference to pre-seed, so the decision is carried in the task text, which is the only lever saga
# exposes. Orchestrate is always inline by design: a dispatched unit is already one of several
# parallel sessions, and nesting a workflow inside one is the orchestration-of-orchestration this
# plugin exists to avoid.
# Saga stages that stop and ask the operator which execution backend to use, and what each one
# needs to be told instead. Both `/plan` and `/work` offer it, so under orchestration the planner
# hangs before the builder is ever reached -- an `AskUserQuestion` in a background tab waits
# forever.
#
# The two messages differ because the stages have different jobs. `/plan` is where the decision is
# recorded, and it records it into the plan document's `backend:` frontmatter, which is the only
# carrier that survives a worktree boundary: the saga tick is untracked local state. `/work` then
# reads that field rather than asking, so the note there is a belt to the document's braces.
BACKEND_NOTES: dict[str, str] = {
    "plan": (
        " The execution backend for this run is already decided: {backend}. "
        "Do not offer or ask about it -- set `backend: {backend}` in the plan's frontmatter "
        "and continue."
    ),
    "work": (
        " The execution backend for this run is already decided: {backend}, and the plan's "
        "`backend:` frontmatter says so. Do not offer or ask about it -- record {backend} "
        "and continue."
    ),
}

# What a builder is told when this run reviews the build in its own phase.
#
# `/work` Phase 5 calls `/code-review` programmatically as its own pre-PR gate. In one session that
# is right. Under orchestration it is a self-review -- the reviewer is the builder's own vendor,
# which is the one thing the operator's roster rule forbids -- and it has a worse failure than the
# wasted pass: §5.3 blocks on any P0 or P1 and the only documented exit is an operator override with
# a recorded rationale. That is a question, in a background tab, waiting forever. The observed run
# came back clean and so survived; a run that does not would hang after an hour of work.
#
# Sent only when the run actually has a code-review phase of its own. Without one the in-loop gate
# is the only review there is, and suppressing it would remove the review rather than move it.
REVIEW_ELSEWHERE_NOTE = (
    " This run reviews the build in its own separate phase, with a different vendor than yours, "
    "after your work is landed. Skip the Phase 5 code-review gate entirely -- do not call "
    "/code-review, do not write a code-review evidence record, and do not ask for an override. "
    "Commit your work, say what you did, and stop."
)

# Sent with every dispatched saga task, whatever the capability.
#
# `BACKEND_NOTES` pre-answers one question. Saga's `/plan` names the whole family in its own
# SKILL.md: "Use AskUserQuestion for choices from a known set (destination, execution backend,
# scope class, resume-vs-mint)". Shipping a note for the backend fixed one member of four, and the
# next live run stopped on the destination within minutes of starting -- a planner sitting blocked
# in a tab nobody was watching, with the rest of the run queued behind it.
#
# One rule rather than four more pre-decided answers. Pre-deciding each would make this plugin model
# saga's entire question vocabulary, which goes stale the moment saga adds a fifth -- the same closed
# vocabulary that sent a whole review phase around the plugin (see `launch_args`).
#
# The second half is the load-bearing half. A unit must not silently invent an answer to a real
# question about the work: "should this refactor also cover X" is the operator's, and guessing it
# produces confident work on the wrong thing. Stopping is safe, because an idle unit is exactly what
# `settle` and the orchestrator are watching for.
UNATTENDED_NOTE = (
    " You are running unattended in a tab nobody is watching, so a question waits forever and takes "
    "the run down with it. For a choice from a known set -- destination, execution backend, scope "
    "class, resume-vs-mint -- do not ask: take the most defensible option, say in one line which "
    "you took and why, and continue. For a real question about the work itself, do not guess and "
    "do not prompt either: write the question into your output and stop, and the orchestrator will "
    "bring it to the operator."
)

SAGA_SYNTAX: dict[str, str] = {
    "claude": "/saga:{cap}",
    "codex": "$saga:{cap}",
    "grok": "/{cap}",
    "agy": "/saga:{cap}",
    "qwen": "/{cap}",
    "opencode": "/{cap}",
}

PENDING, RUNNING, DONE, FAILED = "pending", "running", "done", "failed"


@dataclass
class Unit:
    name: str
    vendor: str
    task: str
    """What the session is told to do -- a saga command like "/plan #456", or free prose.

    Always the full text in memory, even when the record on disk keeps only a pointer: ``save``
    spills a task longer than ``TASK_SPILL_THRESHOLD`` into its own file, and ``load`` reads it
    back, so no caller of ``task`` knows the difference."""
    task_file: str | None = None
    """The file this unit's task is spilled in, relative to ``TASK_DIR`` -- None when inline.

    Written only by ``save``. A record from before the spill existed carries its task inline and
    has no such key, which ``load`` still accepts; nothing is migrated at read time."""
    model: str | None = None
    effort: str | None = None
    permission: str = "auto"
    """How freely this unit may act: ``auto`` (get on with it) or ``bypass`` (ask nothing).

    ``auto`` is the default because it is enough for a unit to do its own work in its own worktree.
    ``bypass`` is there because it is what the operator runs all day, and a unit that keeps stopping
    to ask in a tab nobody is watching has failed. The containment is the worktree either way."""
    setup: list[str] = field(default_factory=list)
    """Lines sent into the session before its task, for tier control the command line lacks.

    ``["/effort high"]`` for an agent whose CLI has no effort flag. Sent in order, each as its own
    prompt, so the session has settled into the requested tier before it is given work. Anything a
    slash command can do to a fresh session belongs here."""
    launch_args: list[str] = field(default_factory=list)
    """Extra arguments for the launcher, passed through verbatim and never inspected.

    ``model`` and ``effort`` cover what every vendor has in common; this covers everything else the
    wrapper knows and this plugin does not. ``["--company-account"]`` is the case that forced it:
    the wrapper intercepts that flag and swaps the configuration directory before the tool starts,
    so it is a launcher concern, invisible to the tool's own ``--help``, and there was no way to
    ask for it through a unit. The operator asked, the plugin could not carry it, and a whole review
    phase was launched by hand and lost to the run record.

    Deliberately not validated here. The wrapper is a separate program on its own release schedule,
    so any list of acceptable flags kept in this file would go stale silently -- which is the same
    closed vocabulary one level up. It already rejects what it does not accept, by name. Carry it,
    do not police it."""
    merge: bool = True
    """Should this unit's branch be merged onto the run branch by ``land``?

    True for almost everything: a phase becomes real to the next one by landing. False is for a unit
    whose branch is meant to be *read* rather than merged -- several planners each writing their own
    version of the same document, where merging them by git produces a conflict at best and a
    silently interleaved plan at worst.

    Whether a unit is that kind is a judgement about what the phase was for, so it is authored here
    rather than guessed. This plugin does not compare branches for overlapping paths to work it out:
    that is real work, wrong in both directions, and it decides something the person who wrote the
    phase already knows."""
    after: list[str] = field(default_factory=list)
    serialize: list[str] = field(default_factory=list)
    """Wait for these units to finish, without claiming anything about needing their output.

    ``after`` means "I build on what you produce", and it was also being used to mean "do not run
    at the same time as you -- we would both touch the same files" or "wait until that has landed
    so I can rebase on it". A run using it the second way looked blocked for a reason that does
    not exist, and a reader could not tell the two apart. This edge gates launch exactly like
    ``after`` -- a unit is not eligible until every name in both lists is done -- and the
    difference is carried downstream, not in the gate: ``go`` does not ask whether a serialize
    dependency committed anything, and ``status`` names which kind of edge holds a unit."""
    worktree: str | None = None
    branch: str | None = None
    tab_id: str | None = None
    pane_id: str | None = None
    """The pane this session occupies. Recorded because herdr's event subscriptions are keyed by
    pane, not by agent name -- ``events.subscribe`` rejects a request without one."""
    agent_name: str | None = None
    """What herdr calls this session. The wrapper uniquifies names, so it can differ from
    ``name`` -- which is the plan's identity and the dependency key, and never changes."""
    status: str = PENDING
    note: str = ""


@dataclass
class Run:
    run_id: str
    source: str
    base: str
    units: list[Unit]
    backend: str = "inline"
    """The execution backend every saga unit in this run uses.

    Decided once, up front, because it is a property of the run rather than of a unit -- and because
    `/work` otherwise stops to ask in a background tab nobody is watching. Always ``inline`` today:
    a dispatched unit is already one of several parallel sessions, so nesting a workflow inside one
    is the orchestration-of-orchestration this plugin exists to avoid."""
    branch: str = ""
    """The run's shared branch -- what a team would call the feature branch.

    Every unit branches from here and lands back here when it finishes, so the next phase opens on
    everything the earlier phases actually produced rather than on one predecessor's branch. At the
    end this is the single branch that merges into the operator's tree."""
    engine_prefs: dict[str, dict[str, str]] = field(default_factory=dict)
    """Saga's per-stage external-engine answers, decided once in the interview.

    Keyed by saga stage (``code-review``, ``doc-review``, ``work``, …), each value carrying
    ``intent`` and optionally ``model`` and ``effort``. Written into every worktree so a dispatched
    saga command finds the answer already stored and never stops to ask a question in a tab nobody
    is watching. See ``write_engine_prefs``.
    """
    issues: dict[str, str] = field(default_factory=dict)
    """Unit name -> issue reference (``owner/repo#N``) whose board card this run reports to.

    Absent means this run writes nothing back: every board writeback in this file is a no-op, and a
    run file written before this field existed loads and behaves exactly as it did. The field is the
    whole connection between a phase boundary and the card it happened for -- the observed 75-unit
    run for issue 52 crossed nine phases while its card never left `Idea`, not because the write was
    missing but because nothing ever called it. See ``announce_units``."""
    status_map: dict[str, str] = field(default_factory=dict)
    """Unit-name prefix -> board Status overrides, replacing the default one key at a time.

    A key present here wins over ``DEFAULT_STATUS_MAP`` for that prefix; every other prefix keeps
    the default. Values are still checked against the board's Status ladder -- an override is a way
    to re-route a phase, not a way to invent a status. See ``mapped_status``."""

    @classmethod
    def load(cls, path: Path = RUN_FILE) -> Run:
        raw = json.loads(path.read_text())
        return cls(
            run_id=raw["run_id"],
            source=raw["source"],
            base=raw["base"],
            units=[read_unit(u) for u in raw["units"]],
            backend=raw.get("backend", "inline"),
            branch=raw.get("branch", ""),
            engine_prefs=raw.get("engine_prefs", {}),
            issues=raw.get("issues", {}),
            status_map=raw.get("status_map", {}),
        )

    def save(self, path: Path = RUN_FILE) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "run_id": self.run_id,
            "source": self.source,
            "base": self.base,
            "backend": self.backend,
            "branch": self.branch,
            "engine_prefs": self.engine_prefs,
            "issues": self.issues,
            "status_map": self.status_map,
            "units": [spill_unit(u) for u in self.units],
        }
        path.write_text(json.dumps(payload, indent=2) + "\n")

    def unit(self, name: str) -> Unit:
        for u in self.units:
            if u.name == name:
                return u
        raise SystemExit(f"no unit named {name!r}")

    def reviews_separately(self) -> bool:
        """Does this run have a code-review phase of its own?

        Read off the unit table rather than asked, because the interview already wrote the answer
        there: a review phase is units, one per reviewer. Matching is on the saga capability in the
        task text, in any vendor's spelling, since ``normalize_task`` has not run yet at this point.
        """
        return any(re.search(r"[/$](saga:)?code-review\b", u.task) for u in self.units)

    def eligible(self) -> list[Unit]:
        """Pending units whose every ordering edge is satisfied.

        ``after`` and ``serialize`` gate identically -- a unit is not eligible until every name in
        both lists is done. What the edge *means* is carried elsewhere: see ``wait_reason``."""
        done = {u.name for u in self.units if u.status == DONE}
        return [
            u
            for u in self.units
            if u.status == PENDING and all(dep in done for dep in u.after + u.serialize)
        ]

    def wait_reason(self, unit: Unit) -> str:
        """Why a pending unit is still pending, naming the kind of each edge that holds it.

        ``after`` and ``serialize`` gate launch identically but mean different things -- one
        needs the dependency's output, the other only asks not to run beside it -- and while both
        lived in ``after``, a reader could not tell them apart. Empty means nothing holds the
        unit: it is eligible and simply has not been launched yet."""
        done = {u.name for u in self.units if u.status == DONE}
        parts: list[str] = []
        needs = [dep for dep in unit.after if dep not in done]
        if needs:
            parts.append(f"needs output from {', '.join(needs)}")
        behind = [dep for dep in unit.serialize if dep not in done]
        if behind:
            parts.append(f"serialized behind {', '.join(behind)}")
        return "; ".join(parts)


def spill_unit(unit: Unit) -> dict[str, Any]:
    """One unit's row in the run record, with a long task spilled to its own file.

    The record keeps the pointer and ``TASK_DIR`` keeps the text, so run.json stops being 83%
    task prose on a big run. A short task stays inline, and any pointer on one is dropped: a row
    carrying both would have its inline text overwritten by the file at load. The in-memory unit
    is untouched -- the spill is something that happens to the record, not to the run."""
    data = asdict(unit)
    if len(unit.task) <= TASK_SPILL_THRESHOLD:
        data["task_file"] = None
        return data
    TASK_DIR.mkdir(parents=True, exist_ok=True)
    (TASK_DIR / f"{unit.name}.task.md").write_text(unit.task)
    data["task"] = ""
    data["task_file"] = f"{unit.name}.task.md"
    return data


def read_unit(raw: dict[str, Any]) -> Unit:
    """One unit from its record row, reading a spilled task back transparently.

    A row without a pointer is an old-format record or a short task, and its inline task is
    taken as-is -- nothing is migrated at read time, so a run.json written by an older version
    loads exactly as it lies. A pointer whose file is gone loads as an empty task with a note
    naming the missing file: a run record must stay loadable even when its spill does not."""
    unit = Unit(**raw)
    if not unit.task_file:
        return unit
    spill = TASK_DIR / unit.task_file
    try:
        unit.task = spill.read_text()
    except OSError:
        unit.task = ""
        unit.task_file = None
        note = f"spilled task file is gone: {spill}"
        unit.note = f"{unit.note}; {note}" if unit.note else note
    return unit


def run(
    cmd: list[str],
    *,
    check: bool = True,
    capture: bool = True,
    timeout: float | None = None,
) -> subprocess.CompletedProcess:
    """Run a command. Pass ``timeout`` for anything that asks a vendor a question.

    A vendor's own subcommand can reach the network and hang; without a bound that becomes an
    interview frozen on a question the operator cannot see, which is the failure this plugin keeps
    having to fix. A timeout is reported as a non-zero result, so callers handle it as "no answer"
    rather than as a crash.

    ``check=False`` means every failure comes back as a result, and a command that is not installed
    is a failure like any other. It was not, once: ``subprocess.run`` raises rather than returning
    when the program does not exist, so a machine without herdr got a traceback out of a read-only
    command that had already decided herdr was optional.
    """
    try:
        proc = subprocess.run(cmd, capture_output=capture, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        if check:
            raise SystemExit(f"timed out after {timeout}s: {' '.join(cmd)}") from None
        return subprocess.CompletedProcess(cmd, returncode=124, stdout="", stderr="timed out")
    except OSError as exc:
        if check:
            raise SystemExit(f"cannot run {cmd[0]!r}: {exc}") from None
        # 127 is the shell's own "command not found", so a caller reading returncode sees the
        # ordinary shape of a failure rather than a special case.
        return subprocess.CompletedProcess(cmd, returncode=127, stdout="", stderr=str(exc))
    if check and proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        raise SystemExit(f"command failed ({proc.returncode}): {' '.join(cmd)}\n{err}")
    return proc


def repo_root() -> Path:
    return Path(run(["git", "rev-parse", "--show-toplevel"]).stdout.strip())


# ----------------------------------------------------------------- launching


def write_engine_prefs(worktree: Path, prefs: dict[str, dict[str, str]]) -> None:
    """Answer saga's external-engine offer before the session is even launched.

    A dispatched ``/code-review`` or ``/doc-review`` opens by resolving an engine offer, and with
    nothing stored it stops and asks the operator -- in a background tab, which means it waits
    forever. Saga reads a stored answer from ``<repo>/.saga/engine-prefs.json`` and skips the
    question entirely (``engine_offer.resolve_offer`` returns early, ``prompt_required=False``).

    Written directly rather than by shelling out to saga's ``engine_offer.py remember``, which would
    mean resolving another plugin's script path across install layouts. The format is small and
    carries its own version. If saga ever moves past version 1 the stored answer stops being
    honoured, and the visible symptom is a review unit sitting at ``blocked`` in ``status`` -- which
    is the first place to look if that ever happens.
    """
    if not prefs:
        return
    path = worktree / ".saga" / "engine-prefs.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"stages": prefs, "version": 1}, indent=2) + "\n")


def produced_anything(dep: Unit, r: Run) -> bool:
    """Did this unit actually commit something to its branch?

    A dependent unit opens on its dependency's branch, so if that branch is still sitting at the
    base commit there is nothing there to work on. Launching anyway does not fail loudly -- the
    session finds no plan, no diff, no artifact, and writes something plausible about nothing. That
    happened: a doc-review unit reviewed a plan document that was never written.
    """
    if not dep.branch:
        return False
    got = run(["git", "rev-list", "--count", f"{r.base}..{dep.branch}"], check=False)
    return got.returncode == 0 and got.stdout.strip() not in ("", "0")


def make_worktree(unit: Unit, r: Run, root: Path) -> None:
    """One worktree and one branch per unit. This is the whole isolation story.

    A unit with dependencies branches from the last one it named, so a ``/work`` unit opens on top
    of the ``/plan`` unit's output rather than on bare ``base``. Made at launch time, not at
    ``start``, because the dependency's branch does not have its commits until it has run.
    """
    path = root.parent / f"orch-{unit.name}"
    # dash, not a second slash: git cannot hold `orch/<run>` as a branch and `orch/<run>/<unit>`
    # as another, because one ref would have to be both a file and a directory
    branch = f"orch/{r.run_id}-{unit.name}"
    base = r.branch or r.base
    if path.exists():
        print(f"  worktree already there: {path}")
    else:
        run(["git", "worktree", "add", str(path), "-b", branch, base or r.base])
    unit.worktree = str(path)
    unit.branch = branch
    write_engine_prefs(path, r.engine_prefs)
    print(f"  {unit.name}: {path.name} on {branch} from {base}")


def launcher() -> str:
    """The local wrapper that creates an agent session.

    Called ``agents`` rather than ``agent`` because ``agent`` was taken over by another tool on this
    machine. That is why this is resolved instead of hardcoded: a stale name does not fail cleanly,
    it launches somebody else's binary with flags it has never heard of. Checking first turns a
    confusing wrong-program run into one clear sentence.
    """
    name = os.environ.get("ORCHESTRATE_AGENT_LAUNCHER", "agents")
    if not shutil.which(name):
        raise SystemExit(
            f"no {name!r} on PATH -- that is the wrapper that creates agent sessions. "
            f"If it is called something else here, set ORCHESTRATE_AGENT_LAUNCHER."
        )
    return name


def launchable() -> list[str]:
    """Everything the wrapper says it can launch on this machine, asked every time.

    The ``Tools:`` section of the wrapper's own help. Two things this is deliberately not:

    - **Not ``--crews``.** A crew is the operator's saved workspace layout and has nothing to do with
      orchestration. Offering it drops available agents silently, which is the quiet kind of wrong
      answer worth spending code on rather than instructions.
    - **Not a ``PATH`` check.** Several entries are modes of one wrapper rather than binaries of
      their own, so looking for a file by that name reports them missing when they work fine. The
      wrapper is the authority on what the wrapper can launch.
    """
    out = run([launcher(), "--help"], check=False, timeout=20).stdout
    names: list[str] = []
    in_tools = False
    for line in out.splitlines():
        if line.startswith("Tools:"):
            in_tools = True
            continue
        if in_tools:
            if not line.strip():
                break
            # a tool line is "  name   description"; continuation lines are indented further
            if re.match(r"^ {2}\S", line):
                names.append(line.split()[0])
    return names


def roster() -> list[tuple[str, str]]:
    """The vendors this run may use: ones orchestrate knows how to drive, that are available here.

    Both halves matter. ``VENDOR_FLAGS`` is what this plugin understands well enough to hand a model
    and an effort to; the wrapper's tool list is what this particular machine can actually start.
    Offering anything outside the intersection is a promise orchestrate cannot keep -- a Hermes
    profile or a provider variant is launchable but is not a vendor this plugin knows how to tier,
    and a vendor it knows is useless on a machine that does not have it.

    Returns ``(name, flags)``, where ``flags`` says what tier control the command line gives.
    """
    here = set(launchable())
    return [(n, ",".join(f) or "none") for n, f in VENDOR_FLAGS.items() if n in here]


FAVOURITES_PATH = Path("~/.config/orchestrate/models.json").expanduser()


def favourites(vendor: str) -> list[str]:
    """The models the operator actually uses for this vendor, in their order of preference.

    Asking a vendor what it has is a fact; deciding which of them matters is a preference, and a
    preference belongs in a file the operator owns rather than in anyone's guess. opencode fronts
    164 models across eight providers, so offering four of them is noise -- three rounds running,
    the suggestions were wrong.

    Absent or unreadable, this returns nothing and the interview falls back to asking. It is a
    convenience, never a constraint: a model not listed here is still perfectly usable.
    """
    try:
        raw = json.loads(FAVOURITES_PATH.read_text())
    except (OSError, ValueError):
        return []
    got = raw.get(vendor, [])
    return [str(m) for m in got] if isinstance(got, list) else []


def models(name: str) -> list[str]:
    """Ask one vendor which models it actually has.

    Model names are the last thing in this plugin still taken from memory, and memory is exactly
    what got the crew list and the flag table wrong. A recalled name that has since been renamed
    does not fail politely -- the session starts on some default tier and nobody is told.

    Only three vendors can answer today. The rest return nothing, and the operator supplies the
    name -- which is honest, and better than inventing one.
    """
    sub = MODEL_LIST.get(name)
    if not sub:
        return []
    # generous: a cold vendor can take most of a minute to answer, and an inconsistent
    # answer run-to-run is worse than a slow one for a command the operator invoked
    got = run([name, *sub], check=False, timeout=60)
    if got.returncode != 0:
        return []
    return [ln.strip() for ln in got.stdout.splitlines() if ln.strip()]


def agent_argv(unit: Unit) -> list[str]:
    argv = [
        launcher(),
        "--no-focus",
        "--current",
        "--herdr",
        "--herdr-control-only",
        "--task",
        unit.name,
        "--cwd",
        unit.worktree or ".",
        unit.vendor,
    ]
    modes = VENDOR_PERMISSION.get(unit.vendor, {})
    argv.extend(modes.get(unit.permission, modes.get("auto", [])))
    flags = VENDOR_FLAGS.get(unit.vendor, {})
    for key, value in (("model", unit.model), ("effort", unit.effort)):
        template = flags.get(key)
        if value and template:
            argv.extend(template.format(value=value).split(" "))
    # Last, and verbatim. The wrapper reads its own flags out of the arguments that follow the
    # vendor token, so this is the position they have to occupy -- and anything it does not
    # recognise it hands to the vendor, which is the right failure either way.
    argv.extend(unit.launch_args)
    return argv


# How long to give a new session to become able to read a prompt, and how long to give it after
# being sent to show that it took one.
#
# The wrapper returns when the tab exists, which is earlier than the agent being able to read
# anything, and sending into that gap does not fail: `herdr agent prompt` reports success, the agent
# finishes booting, and the prompt is gone. Observed three times across two vendors on one live run,
# always the same tell -- a unit idle immediately after launch, having consumed nothing. `settle`
# reads that idle as done and only `land` notices, a phase later, that it committed nothing.
LAUNCH_SETTLE_SECONDS = 30.0
DELIVERY_CHECK_SECONDS = 15.0


def agent_row(unit: Unit, agents: list[dict] | None = None) -> dict | None:
    """This unit's row in herdr's agent list, matched on the pane it was given."""
    for a in live_agents() if agents is None else agents:
        if unit.pane_id and a.get("pane_id") == unit.pane_id:
            return a
    return None


def await_ready(unit: Unit, seconds: float = LAUNCH_SETTLE_SECONDS) -> bool:
    """Wait until this session will actually take a prompt. True if it said so.

    Some agents never report readiness at all -- qwen is one, and it is why `say` has a pane
    fallback. There is nothing to wait for there, so the window is spent and the send goes ahead,
    which is still later than sending the instant the tab appears.
    """
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        row = agent_row(unit)
        if row is not None and row.get("interactive_ready"):
            return True
        time.sleep(1.0)
    return False


def took_the_task(unit: Unit, seconds: float = DELIVERY_CHECK_SECONDS) -> bool:
    """Did the session actually take the task? One that did stops being idle.

    Not a guarantee -- an agent that answers instantly is idle again quickly. It is a check on the
    failure that has actually happened, which is a session that never started at all. Reported
    rather than repaired: a resend risks giving a unit its task twice, and a unit that quietly did
    nothing is worth a line in `status` more than it is worth a guess.
    """
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        row = agent_row(unit)
        if row is not None and row.get("agent_status") not in (None, "idle", "done", "unknown"):
            return True
        time.sleep(1.0)
    return False


def launch(unit: Unit, backend: str = "inline", *, review_elsewhere: bool = False) -> None:
    proc = run(agent_argv(unit))
    pane_id = None
    try:
        info = json.loads(proc.stdout.strip().splitlines()[-1])
        unit.tab_id = info.get("tab_id")
        unit.agent_name = info.get("agent_name", unit.name)
        pane_id = info.get("pane_id")
        unit.pane_id = pane_id
    except (ValueError, IndexError):
        unit.note = "launched, but the wrapper's JSON could not be read"
    await_ready(unit)
    send(unit, pane_id, backend, review_elsewhere=review_elsewhere)
    unit.status = RUNNING
    if not took_the_task(unit):
        unit.note = (
            "SENT BUT NEVER STARTED: idle after being given its task. Check the tab before "
            "trusting this unit -- it may have been prompted while still booting."
        )


# How long a line may be before typing it into a pane stops delivering it as an instruction.
#
# Measured against qwen 0.21.13 through `herdr pane run`: 859 characters arrive as typed text, 1660
# arrive as `[Pasted Content N chars]`. The paste is submitted and the agent knows its size -- it
# simply does not treat it as the instruction. Its own words, verbatim, to a 6402-character task:
# "I can see you've pasted some content (6402 characters), but I'm not sure what you'd like me to do
# with it."
#
# That is the whole failure: the unit launches, the keystrokes are delivered, orchestrate records
# success, and the session sits waiting for an instruction it thinks it has not been given. It goes
# idle, `settle` marks it done, and only `land` -- a phase later -- reports that it committed
# nothing. A real task is routinely well past this, so the door this plugin uses for any vendor that
# will not take `herdr agent prompt` was quietly unusable for real work.
PANE_TYPING_LIMIT = 800


def pane_text(unit: Unit, text: str) -> str:
    """The line to type, which is the task itself only when the task is short enough to survive.

    Past the limit the task goes to a file and the typed line points at it. The leading saga command
    stays typed: it is what makes the vendor load the skill, and inside a file it is just prose.
    """
    if len(text) <= PANE_TYPING_LIMIT:
        return text
    path = (TASK_DIR / f"{unit.name}.md").resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + "\n")
    lead = text.split(" ", 1)[0] if re.match(r"^\s*[/$]", text) else ""
    unit.note = f"task handed over as a file, too long to type: {path}"
    return (
        f"{lead} Your full task is in {path} -- read that file in full and carry it out exactly. "
        "It is the complete instruction; nothing else is coming."
    ).strip()


def say(unit: Unit, pane_id: str | None, text: str) -> None:
    """Put one line into the session.

    ``herdr agent prompt`` is the right door, but it refuses any agent that never reports
    ``interactive_ready`` -- qwen is one today. For those, type into the pane instead, which is what
    the operator would do by hand -- but only up to the length a pane will still carry as an
    instruction rather than as an attachment. See ``pane_text``.
    """
    handle = unit.agent_name or unit.name
    attempt = run(["herdr", "agent", "prompt", handle, text], check=False)
    if attempt.returncode == 0:
        return
    if not pane_id:
        raise SystemExit(f"{unit.name}: agent prompt refused and no pane to fall back to")
    typed = pane_text(unit, text)
    run(["herdr", "pane", "run", pane_id, typed])
    if not unit.note:
        unit.note = "prompted through its pane; this agent does not report interactive readiness"


def send(
    unit: Unit, pane_id: str | None, backend: str = "inline", *, review_elsewhere: bool = False
) -> None:
    """Set the session up, then give it its task.

    Setup goes first and separately: a tier has to be in force before the work starts, and a slash
    command bundled into the same message as the task is just text the agent reads.
    """
    for line in unit.setup:
        say(unit, pane_id, line)
    say(
        unit,
        pane_id,
        normalize_task(unit.vendor, unit.task, backend, review_elsewhere=review_elsewhere),
    )


def poll(unit: Unit, agents: list[dict] | None = None) -> str:
    """Ask herdr what this session is doing. Absence means the session is gone.

    A caller looking at several units at once passes one already-fetched list rather than paying a
    herdr round trip per unit: an unresponsive herdr costs the timeout once instead of once a row.
    """
    handle = unit.agent_name or unit.name
    for a in live_agents() if agents is None else agents:
        if a.get("name") == handle:
            return str(a.get("agent_status", "unknown"))
    return "gone"


def live_agents() -> list[dict]:
    """The sessions herdr is tracking right now.

    herdr is the truth a run file only mirrors, so it is asked, never remembered. A missing or
    failing herdr is not an error here: it means there is nothing to match a worktree or a session
    against, and the caller degrades -- to "no live agent" when adopting, to "gone" when polling.
    """
    proc = run(["herdr", "agent", "list"], check=False, timeout=20)
    try:
        agents = json.loads(proc.stdout)["result"]["agents"]
    except (ValueError, KeyError):
        return []
    return [a for a in agents if isinstance(a, dict)]


def run_branches(run_id: str) -> list[str]:
    """Every local unit branch of this run, exactly as git records them.

    The list is the discovery source for ``check`` and ``adopt``: a unit branch that exists without
    a row in the table is work the record lost track of. The run branch itself is excluded by the
    pattern -- it carries no unit-name suffix, so it can never be mistaken for one.
    """
    proc = run(["git", "branch", "--list", f"orch/{run_id}-*", "--format=%(refname:short)"])
    return [b.strip() for b in proc.stdout.splitlines() if b.strip()]


def worktree_on_branch(branch: str) -> str | None:
    """The path of the worktree checked out on this branch, if any."""
    proc = run(["git", "worktree", "list", "--porcelain"])
    path: str | None = None
    for line in proc.stdout.splitlines():
        if line.startswith("worktree "):
            path = line[len("worktree ") :]
        elif line.startswith("branch ") and line[len("branch ") :] == branch:
            return path
    return None


def agent_for_worktree(path: str | None, agents: list[dict]) -> dict | None:
    """The live session sitting in this worktree, matched by its cwd.

    A session's cwd is the one thing about it that cannot drift: it was handed to the launcher and
    never changes, while names can be uniquified and statuses come and go. No worktree, no match --
    a branch without its tree cannot be tied to a session.
    """
    if not path:
        return None
    for a in agents:
        if a.get("cwd") == path:
            return a
    return None


def rebuild_unit(name: str, branch: str, r: Run, agents: list[dict]) -> Unit:
    """Reconstruct a unit from what is still true about it: its branch, tree, and session.

    ``task``, ``after``, ``serialize``, ``model``, ``effort`` and ``permission`` are left at their
    defaults: they cannot be recovered, and an invented value is worse than an empty one -- the
    session has already been given its task, so nothing here is ever sent to it again.
    """
    worktree = worktree_on_branch(branch)
    agent = agent_for_worktree(worktree, agents)
    vendor = str(agent.get("agent", "unknown")) if agent else "unknown"
    if agent is not None and agent.get("agent_status") == "working":
        status = RUNNING
    elif agent is not None or produced_anything(
        Unit(name=name, vendor=vendor, task="", branch=branch), r
    ):
        status = DONE
    else:
        status = FAILED
    return Unit(
        name=name,
        vendor=vendor,
        task="",
        worktree=worktree,
        branch=branch,
        tab_id=agent.get("tab_id") if agent else None,
        pane_id=agent.get("pane_id") if agent else None,
        agent_name=(agent.get("name") or name) if agent else name,
        status=status,
        note="adopted: created outside the run record",
    )


def discover_unrecorded(r: Run) -> list[tuple[str, str]]:
    """``(unit name, branch)`` for every unit branch the table has no row for, in git's order."""
    prefix = f"orch/{r.run_id}-"
    known = {u.name for u in r.units}
    return [
        (branch[len(prefix) :], branch)
        for branch in run_branches(r.run_id)
        if branch.startswith(prefix) and branch[len(prefix) :] not in known
    ]


# ------------------------------------------------- board writeback (via saga's reconcile_controller)

# The board's closed Status vocabulary. These are the values the card can hold and nothing else --
# a mapped status outside this ladder is a typo or an invention, and both are refused here rather
# than sent to GitHub to fail in front of the board writer.
STATUS_LADDER = ("Idea", "Shaping", "Ready", "Active", "Verify", "Done")

# Where a unit's phase boundary lands its issue's card, read off the unit name's prefix. This is
# the default only: ``Run.status_map`` replaces it one key at a time. The prefixes are the saga
# capabilities a unit runs, so ``fix-52-claude`` is a fix phase exactly like ``work-52-build`` is a
# work phase -- matching is at the first dash, never a bare string prefix, so ``planner-notes``
# does not count as a plan.
DEFAULT_STATUS_MAP: dict[str, str] = {
    "plan": "Shaping",
    "docreview": "Shaping",
    "work": "Active",
    "fix": "Active",
    "codereview": "Verify",
    "landed": "Done",
}

# Name of the environment variable that points straight at saga's reconcile_controller, for a
# layout the globs below do not know.
RECONCILE_CONTROLLER_ENV = "ORCHESTRATE_RECONCILE_CONTROLLER"


def _controller_candidates() -> list[Path]:
    """Where saga's reconcile_controller can live, in order of trust.

    First the repo layout -- this file shipped beside the saga plugin in the same checkout. Then
    the installed-plugin layouts, mirroring ``SAGA_INSTALL``: each vendor keeps its own cache, so
    each gets its own glob. ``glob`` resolves symlinks, which is what agy's install is."""
    here = Path(__file__).resolve()
    paths = [here.parents[4] / "saga" / "scripts" / "reconcile_controller.py"]
    for pattern in (
        "~/.claude/plugins/cache/*/saga/*/scripts/reconcile_controller.py",
        "~/.codex/plugins/cache/*/saga/*/scripts/reconcile_controller.py",
        "~/.grok/marketplace-cache/*/plugins/saga/scripts/reconcile_controller.py",
        "~/.qwen/extensions/saga/scripts/reconcile_controller.py",
        "~/.gemini/config/plugins/saga/scripts/reconcile_controller.py",
    ):
        paths.extend(Path(hit) for hit in sorted(glob.glob(str(Path(pattern).expanduser()))))
    return paths


def reconcile_controller_path() -> Path | None:
    """Resolve saga's reconcile_controller script, or None when it is not importable here.

    Never an error: a missing saga is an ordinary state of this machine, and writeback is a guest
    of the run, not a gate on it. ``land`` and ``announce`` say so on stderr and carry on."""
    override = os.environ.get(RECONCILE_CONTROLLER_ENV, "")
    if override:
        path = Path(override).expanduser()
        return path if path.is_file() else None
    for candidate in _controller_candidates():
        if candidate.is_file():
            return candidate
    return None


def parse_issue_ref(ref: str) -> tuple[str, int] | None:
    """Split ``owner/repo#N`` into ``("owner/repo", N)``; None when the ref is malformed.

    A bad mapping must never take down a land -- it is reported and skipped instead."""
    match = re.fullmatch(r"\s*(\S+)#(\d+)\s*", ref)
    if not match:
        return None
    return match.group(1), int(match.group(2))


def mapped_status(unit_name: str, overrides: dict[str, str] | None = None) -> str | None:
    """The board Status a unit's phase boundary lands its card on, or None when nothing applies.

    The run's ``status_map`` overrides ``DEFAULT_STATUS_MAP`` key by key. Longest key wins so a
    specific override cannot be shadowed by a shorter default. Matching is at a dash boundary: the
    unit name is the key itself or starts with the key and a dash."""
    merged = {**DEFAULT_STATUS_MAP, **(overrides or {})}
    for key in sorted(merged, key=len, reverse=True):
        if unit_name == key or unit_name.startswith(key + "-"):
            return merged[key]
    return None


def announce_comment_body(r: Run, unit: Unit, status: str) -> str:
    """The one progress comment a boundary posts, naming what actually happened."""
    return (
        "\n".join(
            [
                "### Orchestrate: phase boundary passed",
                "",
                f"- run: {r.run_id}",
                f"- unit: {unit.name} ({unit.vendor})",
                f"- landed on: {r.branch}",
                f"- board status: {status}",
            ]
        )
        + "\n"
    )


def _reconcile_call(
    controller: Path,
    op: str,
    repo: str,
    number: int,
    target_state: str,
    *,
    payload: dict[str, str] | None,
    root: Path,
) -> dict[str, Any]:
    """Drive ONE write through saga's reconcile_controller and hand back its record.

    This is the only door to GitHub in this file: the controller owns the certificate gate, the
    idempotency key, and the retry. ``--repo-root`` pins the shared ledger into the repository the
    run is working in, so a re-run -- here or from ``/work`` -- dedups against the same keys.

    A failure comes back as a record, never as an exception: a board write is a guest of the run,
    and its absence must not cost the run anything."""
    argv = [
        sys.executable,
        str(controller),
        "reconcile",
        "--op",
        op,
        "--repo",
        repo,
        "--number",
        str(number),
        "--target-state",
        target_state,
        "--repo-root",
        str(root),
    ]
    if payload is not None:
        argv += ["--payload", json.dumps(payload)]
    proc = run(argv, check=False, timeout=180)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip()
        return {"status": "failed", "op_kind": op, "error": tail}
    try:
        parsed = json.loads(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"status": "failed", "op_kind": op, "error": "controller printed no JSON record"}
    if not isinstance(parsed, dict):
        return {"status": "failed", "op_kind": op, "error": "controller record is not an object"}
    return {str(key): value for key, value in parsed.items()}


def announce_units(r: Run, names: Sequence[str]) -> list[dict[str, Any]]:
    """Write each named unit's just-passed boundary back to its issue's board card.

    Two writes per unit, both through ``reconcile_controller``: set the card's Status field to the
    unit's mapped status, then post one progress comment naming what happened. The comment's
    idempotency discriminator is stable across calls -- ``orchestrate:{run}:{unit}:{status}`` -- so
    a second ``land`` re-driving the same boundary meets the key the first one wrote and skips,
    rather than posting a duplicate comment.

    Returns one record per name. ``skipped`` records carry a reason and cost no writes: the run
    maps no issue for that unit, the ref is malformed, or no status applies. A run with no
    ``issues`` mapping at all returns nothing and writes nothing -- for it, this whole feature is a
    no-op. A missing reconcile_controller is reported on stderr and skipped: writeback must never
    fail a land."""
    if not r.issues:
        return []

    todo: list[tuple[Unit, str, int, str]] = []
    records: list[dict[str, Any]] = []
    for name in names:
        unit = r.unit(name)
        ref = r.issues.get(name)
        if not ref:
            records.append({"unit": name, "skipped": "no issue mapped for this unit"})
            continue
        parsed = parse_issue_ref(ref)
        if parsed is None:
            records.append({"unit": name, "skipped": f"malformed issue reference {ref!r}"})
            continue
        repo, number = parsed
        status = mapped_status(name, r.status_map)
        if status is None:
            records.append({"unit": name, "skipped": "no status mapped for this unit's prefix"})
            continue
        if status not in STATUS_LADDER:
            records.append(
                {
                    "unit": name,
                    "skipped": f"status {status!r} is not on the ladder: "
                    f"{', '.join(STATUS_LADDER)}",
                }
            )
            continue
        todo.append((unit, repo, number, status))

    if not todo:
        return records

    controller = reconcile_controller_path()
    if controller is None:
        print(
            "orchestrate: reconcile_controller is not importable -- saga is not installed "
            f"here; skipping board writeback for {', '.join(unit.name for unit, *_ in todo)}",
            file=sys.stderr,
        )
        records.extend(
            {"unit": unit.name, "skipped": "reconcile_controller not importable"}
            for unit, *_ in todo
        )
        return records

    root = repo_root()
    for unit, repo, number, status in todo:
        writes = [
            _reconcile_call(
                controller, "set-field-status", repo, number, status, payload=None, root=root
            )
        ]
        discriminator = f"orchestrate:{r.run_id}:{unit.name}:{status}"
        writes.append(
            _reconcile_call(
                controller,
                "issue-progress-comment",
                repo,
                number,
                discriminator,
                payload={"body": announce_comment_body(r, unit, status)},
                root=root,
            )
        )
        records.append(
            {"unit": unit.name, "issue": f"{repo}#{number}", "status": status, "writes": writes}
        )
    return records


def report_announcements(records: list[dict[str, Any]], *, verbose: bool = False) -> None:
    """Print what a round of writeback did, one line per unit that is not a silent no-op."""
    for record in records:
        name = record.get("unit", "?")
        if "skipped" in record:
            if verbose:
                print(f"  {name}: not announced -- {record['skipped']}")
            continue
        parts = []
        for write in record.get("writes", []):
            status = str(write.get("status", "unknown"))
            kind = "status" if write.get("op_kind") == "set-field-status" else "comment"
            parts.append(f"{kind} {status}")
        print(f"  board writeback {name} -> {record.get('status', '?')}: {', '.join(parts)}")


# ----------------------------------------------------------------- commands


def cmd_start(args: argparse.Namespace) -> int:
    plan = json.loads(Path(args.plan).read_text())
    base = args.base or run(["git", "rev-parse", "HEAD"]).stdout.strip()
    r = Run(
        run_id=plan["run_id"],
        source=plan.get("source", ""),
        base=base,
        units=[Unit(**u) for u in plan["units"]],
        backend=plan.get("backend", "inline"),
        engine_prefs=plan.get("engine_prefs", {}),
        issues=plan.get("issues", {}),
        status_map=plan.get("status_map", {}),
    )
    assert_vendors_available(r.units)
    assert_saga_reachable(r.units)
    r.branch = f"orch/{r.run_id}"
    exists = run(["git", "rev-parse", "--verify", "--quiet", r.branch], check=False)
    if exists.returncode != 0:
        run(["git", "branch", r.branch, base])
    r.save()
    print(f"run branch {r.branch} from {base[:8]} — units land here, it merges out once")
    order = " -> ".join(u.name for u in r.units)
    print(f"run {r.run_id}: {len(r.units)} units on base {base[:8]}  ({order})")
    print("`orchestrate.py go` to launch what is eligible.")
    return 0


def probe(name: str) -> tuple[str, dict[str, bool]]:
    """Ask one tool's own help what tier control it offers, and whether ours still works.

    Only run against agents ``VENDOR_FLAGS`` claims to know -- those are the entries that can rot,
    and running ``--help`` on an arbitrary tool could start something.

    Returns the help text plus, per key, whether the tool advertises *any* flag for it. The check
    for whether *our* flag still exists is done against the token orchestrate actually passes, not
    against a guessed name: codex sets effort through ``-c key=value``, which no search for
    ``--effort`` would ever find.
    """
    got = run([name, "--help"], check=False, timeout=20)
    out = (got.stdout or "") + (got.stderr or "")
    return out, {
        "model": bool(re.search(r"--model\b", out)),
        "effort": bool(re.search(r"--effort\b|--reasoning-effort\b", out)),
    }


def normalize_task(
    vendor: str, task: str, backend: str = "inline", *, review_elsewhere: bool = False
) -> str:
    """Rewrite a leading namespaced saga command into the form this vendor understands.

    The interview writes the task, and it writes ``/saga:plan`` -- claude's form -- for every
    vendor. Codex needs ``$saga:plan`` and grok, qwen and opencode need a bare ``/plan``. A wrong
    prefix does not error: the agent reads it as prose and does something of its own, which is the
    quiet failure this plugin keeps having to fix. So the translation happens here, at the moment of
    sending, rather than depending on the interview to remember.

    Only an explicitly namespaced command is rewritten (``/saga:x`` or ``$saga:x``). A task that
    opens with anything else -- a path, a bare slash command, plain prose -- is left exactly alone,
    because guessing at what is and is not a command is how this goes wrong in the other direction.
    """
    match = re.match(r"^\s*[/$]saga:([a-z][a-z0-9-]*)", task)
    if not match:
        return task
    cap = match.group(1)
    rewritten = saga_command(vendor, cap) + task[match.end() :]
    note = BACKEND_NOTES.get(cap)
    if note and backend not in ("", None):
        rewritten += note.format(backend=backend)
    if cap == "work" and review_elsewhere:
        rewritten += REVIEW_ELSEWHERE_NOTE
    # Last, and for every capability: the specific notes above answer the questions this plugin
    # knows about, and this one covers the rest -- including whatever saga asks next.
    rewritten += UNATTENDED_NOTE
    return rewritten


def saga_command(vendor: str, cap: str) -> str:
    """Render a saga capability the way this vendor actually invokes it.

    ``cap`` is the bare name -- ``plan``, ``doc-review``, ``code-review``. A vendor with no entry
    gets the plain name back, which reads as prose rather than pretending to be a command.
    """
    return SAGA_SYNTAX.get(vendor, "{cap}").format(cap=cap.lstrip("/$").replace("saga:", ""))


def saga_capabilities(vendor: str) -> list[str]:
    """Which saga capabilities are actually installed for this vendor, read off disk."""
    found: set[str] = set()
    for pattern in SAGA_INSTALL.get(vendor, []):
        for directory in glob.glob(str(Path(pattern).expanduser())):
            base = Path(directory)
            found.update(f.stem for f in base.glob("*.md") if f.stem != "README")
            found.update(d.name for d in base.iterdir() if d.is_dir() and (d / "SKILL.md").exists())
    return sorted(found)


def cmd_saga(args: argparse.Namespace) -> int:
    """Show how each vendor invokes a saga capability, and whether it has saga at all."""
    for name, _ in roster():
        caps = saga_capabilities(name)
        if not caps:
            print(f"{name:12s} NO SAGA INSTALLED — a saga task here does nothing, whatever prefix")
            continue
        has = args.cap in caps
        mark = "" if has else f"  (no `{args.cap}` among its {len(caps)} capabilities)"
        print(f"{name:12s} {saga_command(name, args.cap)}{mark}")
    missing = [n for n, _ in roster() if not saga_capabilities(n)]
    if missing:
        print(f"\nwithout saga: {', '.join(missing)} — give those units plain prose, not a command")
    return 0


def cmd_roster(args: argparse.Namespace) -> int:
    """Print the agents this machine can run, asked now rather than remembered."""
    rows = roster()
    if not rows:
        print("could not read the wrapper's tool list; check that it runs and prints `Tools:`")
        return 1
    print(f"{'vendor':12s} tier control")
    for name, flags in rows:
        print(f"{name:12s} {flags}")
    print(f"\n{len(rows)} usable here. A vendor showing 'none' still takes a tier — set it with a")
    print("slash command in the unit's `setup`, which is sent before the task.")

    print("\nhow each of these behaves -- read this rather than recalling it:")
    for name, _ in rows:
        caps = saga_capabilities(name)
        modes = VENDOR_PERMISSION.get(name, {})
        print(f"\n  {name}")
        print(f"    permission   auto={' '.join(modes.get('auto', [])) or '(vendor default)'}")
        print(f"                 bypass={' '.join(modes.get('bypass', [])) or '(no escalation)'}")
        if caps:
            print(
                f"    saga         {len(caps)} capabilities, invoked as {saga_command(name, 'plan')}"
            )
        else:
            print("    saga         not installed -- a saga task here arrives as prose")
        note = VENDOR_NOTES.get(name)
        if note:
            for i, line in enumerate(textwrap.wrap(note, 92)):
                label = "note" if i == 0 else ""
                print(f"    {label:12s} {line}")

    missing = [n for n in VENDOR_FLAGS if n not in {x for x, _ in rows}]
    if missing:
        print(f"known but not available on this machine: {', '.join(missing)}")
    unknown = [n for n in launchable() if n not in VENDOR_FLAGS]
    if unknown:
        print(f"launchable but not vendors orchestrate drives: {', '.join(unknown)}")

    if args.models:
        print("\nmodels, asked of each vendor that can answer:")
        for name, _ in rows:
            liked = favourites(name)
            found = models(name)
            if liked:
                print(f"  {name}: {', '.join(liked)}   <- your favourites, offer these first")
            elif not found:
                print(f"  {name}: no favourites and it cannot list its own — ask for the name")
            if found:
                head = "     also available:" if liked else f"  {name}:"
                print(head)
                for m in found[: args.limit]:
                    print(f"    {m}")
                if len(found) > args.limit:
                    print(f"    ... and {len(found) - args.limit} more (`{name} models`)")

    if not args.probe:
        if not args.models:
            print("\n`roster --models` asks each vendor what it has; `--probe` checks flag drift.")
        return 0

    print("\nprobing each tool's help for drift:")
    drift = 0
    for name, _ in rows:
        try:
            out, says = probe(name)
        except SystemExit:
            print(f"  {name:12s} could not run --help; skipped")
            continue
        for what in ("model", "effort"):
            template = VENDOR_FLAGS[name].get(what)
            if template:
                # check the token we actually pass, so a `-c key=value` override is not called a lie
                token = template.split()[0].split("=")[0]
                if token not in out:
                    print(
                        f"  {name:12s} DRIFT: passes {token} for {what}; its help no longer shows it"
                    )
                    drift += 1
            elif says[what]:
                print(f"  {name:12s} DRIFT: advertises a {what} flag orchestrate does not pass")
                drift += 1
    print("  no drift" if not drift else f"\n{drift} mismatch(es) — update VENDOR_FLAGS")
    return 0


def assert_saga_reachable(units: list[Unit]) -> None:
    """Refuse a saga task aimed at a vendor with no saga installed.

    The prefix is not the only way this goes wrong. agy and muse have no saga install at all, so a
    ``/saga:plan`` sent to either is prose whatever it is prefixed with -- the session reads it,
    does something of its own, and reports itself done. Catch it before a tab opens.
    """
    bad = []
    for unit in units:
        if not re.match(r"^\s*[/$]saga:", unit.task):
            continue
        if not saga_capabilities(unit.vendor):
            bad.append(f"{unit.name} ({unit.vendor})")
    if bad:
        raise SystemExit(
            f"saga is not installed for: {', '.join(bad)}. "
            "Write those tasks as plain prose, or move them to a vendor that has it "
            "(`orchestrate.py saga <cap>`)."
        )


def assert_vendors_available(units: list[Unit]) -> None:
    """Refuse a plan naming an agent the wrapper cannot launch.

    A typo otherwise surfaces as a launch failure per unit, after worktrees exist and tabs have
    opened. Cheaper to fail before anything is created.
    """
    available = {n for n, _ in roster()}
    if not available:
        return  # the wrapper could not be read; do not block on a check that itself failed
    unknown = sorted({u.vendor for u in units if u.vendor not in available})
    if unknown:
        raise SystemExit(
            f"the wrapper cannot launch: {', '.join(unknown)}. "
            f"available: {', '.join(sorted(available))} (`orchestrate.py roster`)"
        )


def cmd_expand(args: argparse.Namespace) -> int:
    """Add units to a run already in flight.

    The up-front table can only name the later phases, never their units: what ``/work`` splits into
    is decided by the plan, which does not exist yet when the operator approves. So a phase that
    produces the next phase's units is read when it finishes, the operator approves the new rows,
    and they are appended to the same run -- not started as a second one. That keeps ``after``
    reaching back to the units they depend on, and keeps one ``collect`` for the whole thing.
    """
    r = Run.load()
    added = json.loads(Path(args.plan).read_text())
    incoming = [Unit(**u) for u in added["units"]]

    existing = {u.name for u in r.units}
    seen: set[str] = set()
    for unit in incoming:
        if unit.name in existing or unit.name in seen:
            raise SystemExit(f"unit {unit.name!r} is already in this run; give the new one a name")
        seen.add(unit.name)
    reachable = existing | seen
    for unit in incoming:
        for dep in unit.after:
            if dep not in reachable:
                raise SystemExit(f"unit {unit.name!r} waits on {dep!r}, which is in no run")
        for dep in unit.serialize:
            if dep not in reachable:
                raise SystemExit(
                    f"unit {unit.name!r} serializes behind {dep!r}, which is in no run"
                )

    assert_vendors_available(incoming)
    assert_saga_reachable(incoming)
    r.units.extend(incoming)
    r.engine_prefs.update(added.get("engine_prefs", {}))
    r.issues.update(added.get("issues", {}))
    r.status_map.update(added.get("status_map", {}))
    r.save()
    print(f"added {len(incoming)}: {', '.join(u.name for u in incoming)}")
    print("`orchestrate.py go` to launch whatever is now eligible.")
    return 0


def cmd_go(args: argparse.Namespace) -> int:
    r = Run.load()
    ready = r.eligible()
    if not ready:
        print("nothing eligible -- either everything is running or dependencies are unmet.")
        return 0
    root = repo_root()
    for unit in ready[: args.limit] if args.limit else ready:
        if unit.tab_id:
            print(f"  {unit.name}: already has tab {unit.tab_id}; not launching twice")
            continue
        empty = [d for d in unit.after if not produced_anything(r.unit(d), r)]
        if empty:
            print(f"  {unit.name}: skipped — {', '.join(empty)} committed nothing to build on")
            continue
        make_worktree(unit, r, root)
        r.save()  # persist the worktree before the launch, so a failure is not relaunched blind
        print(f"launching {unit.name} ({unit.vendor}) -> {unit.task}")
        try:
            launch(unit, r.backend, review_elsewhere=r.reviews_separately())
        except SystemExit as exc:
            unit.status = FAILED
            unit.note = str(exc)
            print(f"  {unit.name} FAILED: {exc}")
        r.save()
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    r = Run.load()
    live = {u.name: poll(u) for u in r.units if u.status == RUNNING}
    print(f"run {r.run_id}   base {r.base[:8]}   {r.source}\n")
    head = f"{'unit':10s} {'vendor':9s} {'model':14s} {'effort':7s} {'state':9s} {'herdr':9s} task"
    print(head)
    print("-" * len(head))
    for u in r.units:
        tail = u.task[:44]
        if u.status == PENDING:
            why = r.wait_reason(u)
            if why:
                # The wait is the interesting thing about a blocked unit -- its task is in the
                # plan. Naming the kind of edge is the fix for a run that looked blocked for a
                # reason that does not exist.
                tail = f"[{why}]"
        print(
            f"{u.name:10s} {u.vendor:9s} {(u.model or '-'):14s} {(u.effort or '-'):7s} "
            f"{u.status:9s} {live.get(u.name, '-'):9s} {tail}"
        )
    return 0


def settle_reading(units: list[Unit]) -> dict[str, str]:
    """One poll of every unit, against one herdr round trip in total.

    ``live_agents`` is fetched once and passed to ``poll`` -- polling each unit separately costs one
    round trip a row, and an unresponsive herdr costs its timeout once a row instead of once.
    """
    agents = live_agents()
    return {unit.name: poll(unit, agents) for unit in units}


def cmd_settle(args: argparse.Namespace) -> int:
    """Mark running units done when their session goes idle. No inference beyond that.

    Idle is read twice, ``interval`` seconds apart, and only counts when both readings agree: an
    agent is also idle *between* turns -- it finishes a tool call, returns to the prompt, thinks,
    and continues. One instantaneous sample once marked a unit done in that gap; it had two commits
    at the time and finished with ten. ``--once`` restores the single sample for a caller that
    wants it.
    """
    r = Run.load()
    running = [u for u in r.units if u.status == RUNNING]
    first = settle_reading(running) if running else {}
    second = first
    if running and not args.once:
        time.sleep(args.interval)
        second = settle_reading(running)
    for unit in running:
        a, b = first[unit.name], second[unit.name]
        if a in {"idle", "done"} and b in {"idle", "done"}:
            unit.status = DONE
            shown = a if args.once else f"{a} then {b}"
            print(f"  {unit.name}: {shown} -> done")
        elif a == "gone" and b == "gone":
            unit.status = FAILED
            unit.note = "session disappeared"
            print(f"  {unit.name}: session gone -> failed")
        elif a in {"idle", "done"}:
            print(f"  {unit.name}: {a} then {b} -> still moving")
    r.save()
    return 0


def cmd_wait(args: argparse.Namespace) -> int:
    """Block until a running unit settles, told by herdr rather than asking it.

    Subscribes to ``pane.agent_status_changed`` on each running unit's pane over herdr's event
    socket and blocks in the kernel until a line arrives. Subscriptions are keyed by pane, which is
    why a unit records its ``pane_id`` at launch -- a request without one is rejected outright.

    Falls back to ``herdr agent wait`` when the socket is unreachable: an older herdr, a stopped
    server, or a unit launched before pane ids were recorded. That path is level-triggered and
    correct too, just one process per unit instead of one socket.
    """
    r = Run.load()
    running = [u for u in r.units if u.status == RUNNING]
    if not running:
        print("nothing running -- `go` to launch what is eligible")
        return 0

    by_pane = {u.pane_id: u for u in running if u.pane_id}
    print(f"waiting on {', '.join(u.name for u in running)} (up to {args.timeout}s)")

    if by_pane and herdr_events is not None:
        try:
            for event in herdr_events.agent_status_events(
                list(by_pane), timeout=float(args.timeout)
            ):
                unit = by_pane.get(event.pane_id)
                if unit is None:
                    continue
                if event.agent_status in {"idle", "done"}:
                    print(f"{unit.name} is {event.agent_status} -- `settle`, `land`, then `go`")
                    return 0
                if event.agent_status == "blocked":
                    print(f"{unit.name} is blocked -- it is asking a question in its own tab")
                    return 0
            print("no unit changed state before the timeout")
            return 0
        except herdr_events.HerdrEventError as exc:
            print(f"event socket unavailable ({exc}); falling back to per-unit waits")

    procs: dict[int, Unit] = {}
    for unit in running:
        handle = unit.agent_name or unit.name
        proc = subprocess.Popen(
            [
                "herdr",
                "agent",
                "wait",
                handle,
                "--until",
                "idle",
                "--until",
                "done",
                "--timeout",
                str(args.timeout * 1000),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        procs[proc.pid] = unit
    try:
        pid, _ = os.wait()
    except ChildProcessError:
        return 0
    settled = procs.pop(pid, None)
    for other in procs:
        with contextlib.suppress(ProcessLookupError):
            os.kill(other, signal.SIGTERM)
    print(
        f"{settled.name} settled -- `settle`, `land`, then `go`"
        if settled
        else "a wait returned but its unit could not be identified; run `status`"
    )
    return 0


def cmd_land(args: argparse.Namespace) -> int:
    """Merge finished units back onto the run branch.

    This is the step that makes a phase real to the next one. A reviewer does not read the planner's
    branch; it opens on the run branch, and it can only find a plan there because the planner's work
    was landed first. Run it after ``settle`` and before the next ``go``.

    A unit that finished without committing anything is named here rather than passed over. That is
    the failure worth catching -- not a missing merge, but a session that produced nothing and
    reported itself done.
    """
    r = Run.load()
    if not r.branch:
        raise SystemExit("this run has no run branch; it predates `land` -- start a new run")
    dirty = run(["git", "status", "--porcelain", "--untracked-files=no"]).stdout.strip()
    if dirty:
        print("your working tree has uncommitted changes; commit or stash them, then rerun land")
        return 1

    on = run(["git", "rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
    run(["git", "checkout", r.branch])
    landed, empty, already, held = [], [], [], []
    landed_names: list[str] = []
    try:
        for unit in r.units:
            if unit.status != DONE or not unit.branch:
                continue
            if not unit.merge:
                held.append(unit.name)
                continue
            ahead = run(
                ["git", "rev-list", "--count", f"{r.branch}..{unit.branch}"], check=False
            ).stdout.strip()
            if ahead in ("", "0"):
                (already if produced_anything(unit, r) else empty).append(unit.name)
                continue
            merge = run(["git", "merge", "--no-ff", "--no-edit", unit.branch], check=False)
            if merge.returncode != 0:
                run(["git", "merge", "--abort"], check=False)
                print(f"  CONFLICT landing {unit.name}; resolve it on {r.branch} yourself")
                return 1
            landed.append(f"{unit.name} (+{ahead})")
            landed_names.append(unit.name)
    finally:
        run(["git", "checkout", on], check=False)

    print(f"landed on {r.branch}: {', '.join(landed) or 'nothing new'}")
    if already:
        print(f"already there: {', '.join(already)}")
    if held:
        # Named, not passed over. A unit that finishes and never lands is the same shape of quiet
        # loss as one that finishes without committing, and it stays quiet for longer -- the branch
        # is right there, so nothing looks wrong until the phase that needed it opens on nothing.
        print(
            f"NOT MERGED BY REQUEST: {', '.join(held)} -- "
            f"their branches hold work that is not on {r.branch}; read them yourself"
        )
    if empty:
        print(f"COMMITTED NOTHING: {', '.join(empty)} -- those sessions finished without saving")
    # The boundary just passed: write it back to the board here, where it happened, rather than as a
    # separate operator step. A no-op for a run with no `issues` mapping; a missing saga says so on
    # stderr and never fails the land. Re-runs dedup on the controller's idempotency keys.
    if landed_names:
        report_announcements(announce_units(r, landed_names))
    return 0


def cmd_announce(args: argparse.Namespace) -> int:
    """Write a unit's passed phase boundary back to its issue's board card.

    ``land`` already does this for the units it merges; this is the operator's door for the
    boundaries land does not cover -- a unit announced at the wrong moment, or one whose writeback
    failed at the time because saga was missing. Safe to re-run: the controller's idempotency keys
    coalesce a repeat into a skip, so announcing twice posts one comment, not two.
    """
    r = Run.load()
    if not r.issues:
        print("this run has no `issues` mapping, so there is nothing to announce")
        return 0
    records = announce_units(r, args.units)
    report_announcements(records, verbose=True)
    return 0


def landed(branch: str, r: Run) -> bool:
    """Is every commit on this branch already on the branch this run lands onto?

    Measured against the run branch, not the operator's tree. Units land on the run branch as each
    phase finishes, and the operator's tree sees none of it until `collect`, once, at the very end.
    Measured against HEAD this was therefore false for every unit for the whole run -- so
    `clean --merged`, the only mode that is safe to run unattended, closed nothing at exactly the
    time sessions pile up. The only way to reap mid-run was bare `clean`, which closes everything
    regardless of whether its work survived, including the worktree that is the evidence a unit
    failed.

    A run with no run branch predates `land`. There is nothing else to measure against, so the
    operator's tree it is.
    """
    base = r.branch or "HEAD"
    ahead = run(["git", "rev-list", "--count", f"{base}..{branch}"], check=False)
    return ahead.returncode == 0 and ahead.stdout.strip() == "0"


def cmd_collect(args: argparse.Namespace) -> int:
    """Merge the run branch into the operator's tree -- one merge, at the end.

    Units land on the run branch as they finish (``land``); this brings that single branch home, the
    way a feature branch merges once rather than each contributor merging separately.
    """
    r = Run.load()
    if not r.branch:
        raise SystemExit("this run has no run branch; it predates `collect` — start a new run")
    dirty = run(["git", "status", "--porcelain", "--untracked-files=no"]).stdout.strip()
    if dirty:
        print("your working tree has uncommitted changes; git will refuse to merge into it.")
        print("commit or stash them, then rerun collect. what is uncommitted:\n")
        print("\n".join(f"  {line}" for line in dirty.splitlines()[:15]))
        return 1
    ahead = run(["git", "rev-list", "--count", f"HEAD..{r.branch}"]).stdout.strip()
    if ahead in ("", "0"):
        print(f"{r.branch} has nothing your tree does not already have — did you `land` first?")
        return 0
    proc = run(["git", "merge", "--no-ff", "--no-edit", r.branch], check=False)
    if proc.returncode != 0:
        print(f"  CONFLICT merging {r.branch} — resolve it, then rerun collect")
        return 1
    print(f"merged {r.branch} (+{ahead})")
    return 0


def cmd_clean(args: argparse.Namespace) -> int:
    """Close tabs and remove worktrees.

    ``--merged`` restricts it to units whose work is already on the run branch, which is the only
    case where closing is unambiguously free: the work survived the unit, so the tab and the worktree
    are pure overhead. Everything else is left alone, because an unlanded unit's worktree is the
    evidence you look at when it went wrong -- and that is the whole reason this plugin keeps no
    other record.

    Run it after every ``land``, not once at the end. A phase's sessions are finished the moment
    their work is on the run branch, and leaving them open for the rest of the run is how a
    workspace ends up with a dozen idle tabs nobody can tell apart.
    """
    r = Run.load()
    kept, closed = [], []
    for unit in r.units:
        if args.merged and not (unit.branch and landed(unit.branch, r)):
            kept.append(unit.name)
            continue
        if unit.tab_id:
            run(["herdr", "tab", "close", unit.tab_id], check=False)
        if unit.worktree and Path(unit.worktree).exists():
            run(["git", "worktree", "remove", "--force", unit.worktree], check=False)
        if args.branches and unit.branch:
            run(["git", "branch", "-D", unit.branch], check=False)
        closed.append(unit.name)
    if args.all:
        shutil.rmtree(RUN_FILE.parent, ignore_errors=True)
    print(f"closed: {', '.join(closed) or 'nothing'}")
    if kept:
        print(f"kept (not merged, so still your evidence): {', '.join(kept)}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    """Report where the run record and the repository disagree.

    Read-only: no writes, no merges, no launches. The record is one JSON file and the truth is git
    plus herdr, and the two can drift -- a session started by hand leaves a branch with no row; a
    unit marked done saved nothing; a unit marked running finished while nobody was looking. Six
    shapes of drift are reported, and finding any of them is the non-zero exit; ``adopt`` is the
    repair for the first one, and ``settle`` is the repair for the last -- it reads idle twice,
    ``interval`` seconds apart, and only marks the unit done when both readings agree.
    """
    r = Run.load()
    findings: list[str] = []

    for name, branch in discover_unrecorded(r):
        findings.append(f"UNRECORDED {name} -- branch {branch} is not a unit in this run")

    # One herdr round for the whole run, not one per row. A pending or failed unit has no session,
    # so it is never matched against the list at all.
    agents = live_agents()
    for unit in r.units:
        if unit.status not in (RUNNING, DONE):
            continue
        state = poll(unit, agents)
        if unit.status == DONE:
            if not produced_anything(unit, r):
                findings.append(
                    f"NO COMMITS {unit.name} -- marked done, but its branch committed nothing"
                )
            if unit.merge and r.branch and unit.branch:
                ahead = run(
                    ["git", "rev-list", "--count", f"{r.branch}..{unit.branch}"], check=False
                )
                count = ahead.stdout.strip() if ahead.returncode == 0 else ""
                if count not in ("", "0"):
                    plural = "commit" if count == "1" else "commits"
                    findings.append(f"NOT LANDED {unit.name} -- {count} {plural} not on {r.branch}")
            if state == "working":
                findings.append(
                    f"STILL WORKING {unit.name} -- marked done, but its session is still working"
                )
        elif state == "gone":
            findings.append(f"SESSION GONE {unit.name} -- marked running, but its session is gone")
        elif state in {"idle", "done"} and produced_anything(unit, r):
            # Idle with nothing committed is not drift -- a session is also idle between turns,
            # thinking. Idle with commits is a unit that finished while the record still calls it
            # running, and nothing else will notice until an operator asks why the run stopped.
            findings.append(
                f"LOOKS DONE {unit.name} -- marked running, but its session is {state} "
                f"and its branch has commits"
            )

    if not findings:
        print("the record agrees with the repository")
        return 0
    for line in findings:
        print(f"  {line}")
    return 1


def cmd_adopt(args: argparse.Namespace) -> int:
    """Put stranded unit branches back into the run record.

    A unit created outside the run -- a session launched by hand, a run file deleted around live
    work -- leaves a branch the table knows nothing about. This finds those branches and rebuilds a
    row from what is still true: the branch, its worktree, and the session herdr reports there.
    Without ``--yes`` nothing is written; the discovery is printed so the operator can see what
    would be added.
    """
    r = Run.load()
    found = discover_unrecorded(r)
    if not found:
        print("nothing to adopt -- every run branch is already a unit")
        return 0

    agents = live_agents()
    rebuilt = [rebuild_unit(name, branch, r, agents) for name, branch in found]
    verb = "adopted" if args.yes else "would adopt"
    for unit in rebuilt:
        line = (
            f"  {verb}: {unit.name}  vendor={unit.vendor}  "
            f"status={unit.status}  branch={unit.branch}"
        )
        print(line)

    if not args.yes:
        print("nothing written -- rerun with --yes")
        return 0
    r.units.extend(rebuilt)
    r.save()
    print(f"{len(rebuilt)} unit(s) written to the run file")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="orchestrate", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("start", help="create worktrees and the run file from a plan")
    s.add_argument("--plan", required=True)
    s.add_argument("--base", help="commit to branch every unit from (default HEAD)")
    s.set_defaults(func=cmd_start)

    s = sub.add_parser("roster", help="list the agents this machine can actually run")
    s.add_argument("--probe", action="store_true", help="check tier flags against each tool's help")
    s.add_argument("--models", action="store_true", help="ask each vendor which models it has")
    s.add_argument("--limit", type=int, default=12, help="models to show per vendor")
    s.set_defaults(func=cmd_roster)

    s = sub.add_parser("saga", help="how each vendor invokes a saga capability")
    s.add_argument("cap", help="the bare capability name, e.g. plan")
    s.set_defaults(func=cmd_saga)

    s = sub.add_parser("expand", help="append units to a run in flight, once a phase names them")
    s.add_argument("--plan", required=True)
    s.set_defaults(func=cmd_expand)

    s = sub.add_parser("go", help="launch every unit whose dependencies are met")
    s.add_argument("--limit", type=int, default=0, help="launch at most this many now")
    s.set_defaults(func=cmd_go)

    s = sub.add_parser("status", help="show the table")
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("settle", help="mark running units done when their session goes idle")
    s.add_argument(
        "--interval",
        type=int,
        default=20,
        help="seconds between the two idle readings (default 20)",
    )
    s.add_argument(
        "--once",
        action="store_true",
        help="a single reading, no confirmation -- the old behaviour, for a caller that wants it",
    )
    s.set_defaults(func=cmd_settle)

    s = sub.add_parser(
        "wait", help="block until a running unit settles (herdr events, not polling)"
    )
    s.add_argument("--timeout", type=int, default=1800, help="seconds to wait at most")
    s.set_defaults(func=cmd_wait)

    s = sub.add_parser("land", help="merge finished units onto the run branch")
    s.set_defaults(func=cmd_land)

    s = sub.add_parser("announce", help="write a unit's phase boundary back to its board card")
    s.add_argument("units", nargs="+", help="unit names whose boundary has passed")
    s.set_defaults(func=cmd_announce)

    s = sub.add_parser("collect", help="merge the run branch into your tree")
    s.set_defaults(func=cmd_collect)

    s = sub.add_parser("clean", help="close tabs and remove worktrees")
    s.add_argument("--merged", action="store_true", help="only units whose branch is in HEAD")
    s.add_argument("--branches", action="store_true", help="delete the unit branches too")
    s.add_argument("--all", action="store_true", help="delete the run file too")
    s.set_defaults(func=cmd_clean)

    s = sub.add_parser("check", help="report where the run record and the repository disagree")
    s.set_defaults(func=cmd_check)

    s = sub.add_parser("adopt", help="write units for run branches the table does not know")
    s.add_argument(
        "--yes", action="store_true", help="write the discovered units into the run file"
    )
    s.set_defaults(func=cmd_adopt)

    args = p.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
