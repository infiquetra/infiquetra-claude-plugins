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
import functools
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
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
LOCAL_RUN_STATE_EXCLUDE = ".orchestrate/"

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

# The note matches the task column's existing human-facing bound. It used to be the only unbounded
# status field: one delivery warning stretched a two-unit table to 268 characters per row.
STATUS_TEXT_WIDTH = 44

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

REVIEW_CONTROLLER_ROLE = "review-controller"
WORK_FIX_ROLES = frozenset({"review-fixer", "downstream-resolver"})
OPERATOR_FIX_ROLES = frozenset({"human", "release"})
REVIEW_RESULT_SCHEMA = "review_result.v1"
REVIEW_OUTCOMES = frozenset(
    {"accepted", "repairs_requested", "cycle_cap_best_available", "review_incomplete"}
)


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
    """Extra arguments appended after the vendor token, passed through verbatim and never inspected.

    Arguments after the vendor token reach the vendor, except for the few the wrapper intercepts
    from that position (``--company-account`` is one: it swaps the configuration directory before
    the tool starts). A launcher flag that must precede the vendor token cannot be expressed here
    -- ``--workspace`` is the case that forced the ``workspace`` field: after the vendor token the
    wrapper treats it as the vendor's argument and the session lands in the caller's workspace.

    ``model`` and ``effort`` cover what every vendor has in common; this covers everything else the
    wrapper knows and this plugin does not. Deliberately not validated here. The wrapper is a
    separate program on its own release schedule, so any list of acceptable flags kept in this file
    would go stale silently -- which is the same closed vocabulary one level up. It already rejects
    what it does not accept, by name. Carry it, do not police it."""
    workspace: str | None = None
    """Herdr workspace NAME this unit launches into.

    Emitted as ``--workspace <name>`` in the launcher position, before the vendor token, alongside
    ``--task`` and ``--cwd``. Absent, the run's default is used if it has one; absent both, the
    session lands in the caller's workspace -- today's behaviour. The wrapper's ``--workspace``
    takes a name, not an ID: handed an ID it creates a new workspace called that rather than
    joining the one you meant.

    A field rather than a ``launch_args`` entry because the two argv positions are mutually
    exclusive, and this plugin should not have to know which of the wrapper's flags belong where."""
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
    role: str | None = None
    """The unit's review-loop role, when it participates in that loop.

    ``review-controller`` identifies the one top-level Code Review invocation. Work workers use
    ``review-fixer`` or ``downstream-resolver`` so an opaque result can be routed without treating a
    unit name as policy. Older run records carry no role and continue to load unchanged."""
    paths: list[str] = field(default_factory=list)
    """Repository paths this Work worker owns for review-fix routing.

    A directory path owns its descendants. Routing requires both path overlap and the matching
    ``role``; neither a familiar unit name nor a vendor choice substitutes for ownership."""
    fix_requests: list[dict[str, Any]] = field(default_factory=list)
    """Outstanding routing-only fix requests assigned to this Work worker.

    The complete typed result remains an opaque string on ``Run``. These are only the request fields
    Orchestrate is allowed to act on, retained until the worker's repair lands."""
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
    branched_from: str | None = None
    """The commit the unit branch started from, recorded when its worktree is created.

    Kept as creation provenance and for compatibility with existing run records. It cannot prove
    that the unit authored later commits: an empty unit can move its pointer by merging an advanced
    run branch. Landing therefore still requires the second-parent merge shape described by
    ``landed_by_merge``."""
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
class ReviewRouting:
    """Routing actions extracted from an otherwise opaque typed review result."""

    outcome: str
    run_branch: str = ""
    dispatches: list[tuple[Unit, dict[str, Any]]] = field(default_factory=list)
    replacements: list[Unit] = field(default_factory=list)
    operator_requests: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class RunBranchState:
    """The recorded run branch and the commit it resolved to when the run was loaded."""

    name: str
    commit: str | None


class RunBranchResolutionError(RuntimeError):
    """A branch-dependent predicate was asked about an unresolvable run branch."""


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
    branch_state: RunBranchState | None = field(default=None, init=False, repr=False)
    """One load-time resolution of ``branch``; absent only for a legacy branchless run."""
    conflict_worktree: str | None = None
    """A detached land worktree retained so the operator can resolve a merge conflict."""
    workspace: str | None = None
    """Default herdr workspace NAME every unit inherits unless it sets its own.

    Absent means today's behaviour: sessions land in the caller's workspace. A unit with its own
    ``workspace`` wins; there is no other precedence."""
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
    review_result: str | None = None
    """The latest typed Code Review result, stored verbatim and never normalized."""
    review_outcome: str | None = None
    """The result's routing outcome, copied without deriving a review-policy decision."""
    review_resubmit_pending: bool = False
    """Whether landed Work repairs must be resubmitted to the one review controller."""
    operator_fix_requests: list[dict[str, Any]] = field(default_factory=list)
    """Outstanding ``human`` or ``release`` requests, surfaced rather than dispatched as Work."""

    @classmethod
    def load(cls, path: Path = RUN_FILE) -> Run:
        raw = json.loads(path.read_text())
        loaded = cls(
            run_id=raw["run_id"],
            source=raw["source"],
            base=raw["base"],
            units=[read_unit(u) for u in raw["units"]],
            backend=raw.get("backend", "inline"),
            branch=raw.get("branch", ""),
            conflict_worktree=raw.get("conflict_worktree") or None,
            engine_prefs=raw.get("engine_prefs", {}),
            issues=raw.get("issues", {}),
            status_map=raw.get("status_map", {}),
            workspace=raw.get("workspace") or None,
            review_result=raw.get("review_result"),
            review_outcome=raw.get("review_outcome"),
            review_resubmit_pending=bool(raw.get("review_resubmit_pending", False)),
            operator_fix_requests=raw.get("operator_fix_requests", []),
        )
        loaded.resolve_branch_once()
        return loaded

    def resolve_branch_once(self) -> None:
        """Resolve the named run branch once and retain both success and failure as state."""
        if not self.branch:
            self.branch_state = None
            return
        if self.branch_state is None or self.branch_state.name != self.branch:
            self.branch_state = RunBranchState(self.branch, resolve_ref(self.branch))

    @property
    def resolved_branch(self) -> str | None:
        """The cached run-branch commit, or None for a legacy or unresolvable branch."""
        self.resolve_branch_once()
        return self.branch_state.commit if self.branch_state is not None else None

    @property
    def unresolvable_branch(self) -> str | None:
        """The recorded branch name when its one load-time resolution failed."""
        self.resolve_branch_once()
        if self.branch_state is not None and self.branch_state.commit is None:
            return self.branch_state.name
        return None

    def resolved_run_ref(self) -> str:
        """The cached run commit, or the historical HEAD fallback for a branchless run."""
        if not self.branch:
            return "HEAD"
        commit = self.resolved_branch
        if commit is None:
            raise RunBranchResolutionError(f"run branch {self.branch!r} does not resolve")
        return commit

    def record_branch_advance(self, commit: str) -> None:
        """Keep the cached resolution current after this process advances the run branch."""
        if self.branch:
            self.branch_state = RunBranchState(self.branch, commit)

    def save(self, path: Path = RUN_FILE) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "run_id": self.run_id,
            "source": self.source,
            "base": self.base,
            "backend": self.backend,
            "branch": self.branch,
            "conflict_worktree": self.conflict_worktree,
            "engine_prefs": self.engine_prefs,
            "issues": self.issues,
            "status_map": self.status_map,
            "workspace": self.workspace,
            "review_result": self.review_result,
            "review_outcome": self.review_outcome,
            "review_resubmit_pending": self.review_resubmit_pending,
            "operator_fix_requests": self.operator_fix_requests,
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
        there: a review phase is one top-level Code Review controller. An explicit role is
        authoritative. Role-less legacy units retain task-text inference in any vendor's spelling,
        since ``normalize_task`` has not run yet at this point.
        """
        return any(is_review_controller(unit) for unit in self.units)

    def review_controller(self) -> Unit | None:
        """Return the single Code Review controller, refusing an ambiguous legacy panel."""
        controllers = [unit for unit in self.units if is_review_controller(unit)]
        if len(controllers) > 1:
            raise SystemExit(
                "this run has more than one Code Review controller; one review phase is one "
                "top-level controller invocation"
            )
        return controllers[0] if controllers else None

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


def resolve_task_file(pointer: str) -> Path:
    """The spill file a ``task_file`` pointer names, refusing anything outside ``TASK_DIR``.

    Symlinks are resolved before the comparison, so a link planted inside the directory does not
    pass. The check runs on the resolved target rather than trusting the join: in Python an
    absolute right-hand operand discards the left, so ``TASK_DIR / "/etc/passwd"`` is simply
    ``/etc/passwd``. Every pointer passes through here, on save AND on load -- a run record
    edited by hand never passed through name validation, and that is the case this check exists
    for."""
    base = TASK_DIR.resolve()
    resolved = (TASK_DIR / pointer).resolve()
    if base not in resolved.parents:
        raise SystemExit(f"task file {pointer!r} resolves outside {TASK_DIR}: {resolved}")
    return resolved


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
    pointer = f"{unit.name}.task.md"
    resolve_task_file(pointer).write_text(unit.task)
    data["task"] = ""
    data["task_file"] = pointer
    return data


def read_unit(raw: dict[str, Any]) -> Unit:
    """One unit from its record row, reading a spilled task back transparently.

    A row without a pointer is an old-format record or a short task, and its inline task is
    taken as-is -- nothing is migrated at read time, so a run.json written by an older version
    loads exactly as it lies. A pointer whose file is genuinely missing loads as an empty task
    with a note naming it: a run record must stay loadable even when its spill does not. Every
    other read failure -- a directory standing where the file should be, a permission error, an
    I/O error -- raises rather than being absorbed: absorbing it also drops the pointer, so the
    next save would make the loss permanent and the unit could be launched with no instructions."""
    unit = Unit(**raw)
    if not unit.task_file:
        return unit
    spill = resolve_task_file(unit.task_file)
    try:
        unit.task = spill.read_text()
    except FileNotFoundError:
        unit.task = ""
        unit.task_file = None
        note = f"spilled task file is gone: {spill}"
        unit.note = f"{unit.note}; {note}" if unit.note else note
    return unit


def is_code_review_task(task: str) -> bool:
    """Whether task text invokes Saga's Code Review controller in any supported spelling."""
    return bool(re.search(r"[/$](saga:)?code-review\b", task))


def is_review_controller(unit: Unit) -> bool:
    """Identify a controller without letting generated Work prose override an explicit role."""
    return unit.role == REVIEW_CONTROLLER_ROLE or (
        unit.role is None and is_code_review_task(unit.task)
    )


def plan_units(plan: Mapping[str, Any]) -> list[Unit]:
    """Load unit rows and enforce one top-level Code Review controller per plan.

    Older plans identified Code Review only through their task text. Preserve that authoring shape,
    but assign the explicit controller role while loading it and refuse the former N-reviewer panel.
    Work routing roles require path ownership because a role alone cannot identify the responsible
    worker for a finding.
    """
    raw_units = plan.get("units")
    if not isinstance(raw_units, list):
        raise SystemExit("plan `units` must be a list")
    units: list[Unit] = []
    for raw in raw_units:
        if not isinstance(raw, dict):
            raise SystemExit("every plan unit must be an object")
        try:
            unit = Unit(**raw)
        except TypeError as exc:
            raise SystemExit(f"invalid plan unit: {exc}") from None
        if unit.role == REVIEW_CONTROLLER_ROLE:
            if not is_code_review_task(unit.task):
                raise SystemExit(
                    f"unit {unit.name!r} declares {REVIEW_CONTROLLER_ROLE!r} but does not invoke "
                    "Code Review"
                )
        elif unit.role is None and is_code_review_task(unit.task):
            unit.role = REVIEW_CONTROLLER_ROLE
        if unit.role in WORK_FIX_ROLES and not unit.paths:
            raise SystemExit(
                f"Work worker {unit.name!r} declares role {unit.role!r} without owned paths"
            )
        if unit.paths:
            unit.paths = [
                _route_path(path, label=f"unit {unit.name!r} owned path") for path in unit.paths
            ]
        units.append(unit)
    assert_single_review_controller(units)
    return units


def assert_single_review_controller(units: Sequence[Unit]) -> None:
    """Refuse the superseded one-full-review-per-reviewer plan shape."""
    controllers = [unit for unit in units if is_review_controller(unit)]
    if len(controllers) > 1:
        names = ", ".join(unit.name for unit in controllers)
        raise SystemExit(
            f"review phase has {len(controllers)} controller units ({names}); create exactly one "
            "top-level Code Review controller"
        )


def _route_path(value: object, *, label: str) -> str:
    """Normalize one repository-relative path used only for ownership overlap."""
    if not isinstance(value, str) or not value.strip():
        raise SystemExit(f"{label} must be non-empty text")
    if "\n" in value or "\r" in value:
        raise SystemExit(f"{label} must not contain a newline")
    path = value.strip().replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    path = path.rstrip("/")
    if not path or path.startswith("/") or ".." in path.split("/"):
        raise SystemExit(f"{label} must be a repository-relative path: {value!r}")
    return path


def route_paths_overlap(left: Sequence[str], right: Sequence[str]) -> bool:
    """Whether two exact-or-directory-prefix repository path sets overlap."""
    left_paths = [_route_path(path, label="worker path") for path in left]
    right_paths = [_route_path(path, label="fix request touched path") for path in right]
    return any(
        a == b or a.startswith(f"{b}/") or b.startswith(f"{a}/")
        for a in left_paths
        for b in right_paths
    )


def _review_routing_fields(raw_result: str) -> tuple[str, list[dict[str, Any]]]:
    """Read only the result fields Orchestrate is authorized to route.

    Scores, dimensions, cycles, priorities, confidence, and all other Code Review policy stay
    untouched. The original string is persisted separately on ``Run`` before this function is
    called by the command surface.
    """
    try:
        payload = json.loads(raw_result)
    except (TypeError, ValueError) as exc:
        raise SystemExit(f"review result is not JSON: {exc}") from None
    if not isinstance(payload, dict):
        raise SystemExit("review result must be a JSON object")
    schema = payload.get("schema")
    if schema != REVIEW_RESULT_SCHEMA:
        raise SystemExit(
            f"review result has unsupported schema {schema!r}; expected {REVIEW_RESULT_SCHEMA!r}"
        )
    outcome = payload.get("outcome")
    if not isinstance(outcome, str) or outcome not in REVIEW_OUTCOMES:
        raise SystemExit(f"review result has unsupported routing outcome {outcome!r}")
    if outcome != "repairs_requested":
        return str(outcome), []

    raw_requests = payload.get("fix_requests")
    if not isinstance(raw_requests, list):
        raise SystemExit("repairs_requested result requires a fix_requests list")
    requests: list[dict[str, Any]] = []
    for index, item in enumerate(raw_requests):
        if not isinstance(item, dict):
            raise SystemExit(f"fix request {index} must be an object")
        owner = item.get("owner")
        if not isinstance(owner, str) or owner not in WORK_FIX_ROLES | OPERATOR_FIX_ROLES:
            raise SystemExit(f"fix request {index} has unsupported owner role {owner!r}")
        fix_id = item.get("fix_id")
        if not isinstance(fix_id, str) or not fix_id.strip():
            raise SystemExit(f"fix request {index} requires a non-empty fix_id")
        if "\n" in fix_id or "\r" in fix_id:
            raise SystemExit(f"fix request {index} fix_id must not contain a newline")
        touched = item.get("touched_paths")
        if not isinstance(touched, list) or not touched:
            raise SystemExit(f"fix request {fix_id!r} requires touched_paths")
        normalized = [
            _route_path(path, label=f"fix request {fix_id!r} touched path") for path in touched
        ]
        request = json.loads(json.dumps(item, ensure_ascii=False))
        request["owner"] = owner
        request["fix_id"] = fix_id.strip()
        request["touched_paths"] = normalized
        requests.append(request)
    return str(outcome), requests


def _unit_is_live(unit: Unit, agents: Sequence[Mapping[str, Any]]) -> bool:
    """Whether Herdr still reports the worker's recorded pane or agent identity."""
    return any(
        (unit.pane_id and row.get("pane_id") == unit.pane_id)
        or ((unit.agent_name or unit.name) == row.get("name"))
        for row in agents
    )


def _fix_request_id(request: Mapping[str, Any]) -> str:
    """Return the already-validated request identity."""
    return str(request["fix_id"])


def _request_prompt(request: Mapping[str, Any], *, run_branch: str = "") -> str:
    """A Work instruction carrying the structured request without the surrounding result."""
    refresh = (
        f"Before editing, merge the current run branch `{run_branch}` into this unit branch so the "
        "repair is based on the reviewed revision. "
        if run_branch
        else ""
    )
    return (
        refresh
        + "Apply only this Code Review fix request as Work. Keep the request's owner role and path "
        "scope, commit the repair on this unit's branch, run the relevant checks, and stop. The "
        "complete review result remains opaque to Orchestrate; this is its routing request:\n\n"
        + json.dumps(request, ensure_ascii=False, sort_keys=True)
    )


def _replacement_name(template: Unit, request: Mapping[str, Any], existing: set[str]) -> str:
    """Create a stable safe unit name without treating the request identity as a path."""
    slug = re.sub(r"[^a-z0-9]+", "-", _fix_request_id(request).lower()).strip("-") or "repair"
    stem = f"{template.name}-fix-{slug}"[:80].rstrip("-")
    candidate = stem
    suffix = 2
    while candidate in existing:
        candidate = f"{stem}-{suffix}"
        suffix += 1
    return candidate


def _replacement_worker(
    template: Unit, request: dict[str, Any], controller: Unit | None, existing: set[str]
) -> Unit:
    """Create a fresh Work unit from an approved worker's execution configuration."""
    name = _replacement_name(template, request, existing)
    task = f"/saga:work {_request_prompt(request)}"
    replacement = Unit(
        name=name,
        vendor=template.vendor,
        task=task,
        model=template.model,
        effort=template.effort,
        permission=template.permission,
        setup=list(template.setup),
        launch_args=list(template.launch_args),
        workspace=template.workspace,
        merge=True,
        role=str(request["owner"]),
        paths=list(request["touched_paths"]),
        fix_requests=[request],
        serialize=[controller.name] if controller is not None else [],
    )
    existing.add(name)
    return replacement


def route_review_result(
    r: Run,
    raw_result: str,
    *,
    agents: Sequence[Mapping[str, Any]] | None = None,
) -> ReviewRouting:
    """Route one persisted result without making or recomputing a review decision."""
    outcome, requests = _review_routing_fields(raw_result)
    r.review_outcome = outcome
    r.operator_fix_requests = []
    routing = ReviewRouting(outcome=outcome, run_branch=r.branch)
    if outcome != "repairs_requested":
        r.review_resubmit_pending = False
        return routing

    live = list(live_agents() if agents is None else agents)
    controller = r.review_controller()
    names = {unit.name for unit in r.units}
    work_requests = 0
    for request in requests:
        owner = str(request["owner"])
        if owner in OPERATOR_FIX_ROLES:
            r.operator_fix_requests.append(request)
            routing.operator_requests.append(request)
            continue

        work_requests += 1
        touched_paths = list(request["touched_paths"])
        role_workers = [unit for unit in r.units if unit.role == owner]
        matching = [unit for unit in role_workers if route_paths_overlap(unit.paths, touched_paths)]
        reusable = [unit for unit in matching if _unit_is_live(unit, live)]
        if reusable:
            worker = reusable[0]
            if not any(
                _fix_request_id(existing) == _fix_request_id(request)
                for existing in worker.fix_requests
            ):
                worker.fix_requests.append(request)
            routing.dispatches.append((worker, request))
            continue

        templates = matching or role_workers
        if not templates:
            raise SystemExit(
                f"no Work worker declares owner role {owner!r}; cannot choose a replacement "
                "vendor or execution tier"
            )
        replacement = _replacement_worker(templates[0], request, controller, names)
        r.units.append(replacement)
        if templates[0].name in r.issues:
            r.issues[replacement.name] = r.issues[templates[0].name]
        routing.replacements.append(replacement)

    r.review_resubmit_pending = work_requests > 0
    return routing


def dispatch_review_routing(
    routing: ReviewRouting,
    *,
    sender: Callable[[Unit, str], None] | None = None,
) -> list[str]:
    """Send routed requests to live workers; replacement units launch through ordinary ``go``."""
    send_one = sender or (lambda unit, text: say(unit, unit.pane_id, text))
    dispatched: list[str] = []
    for unit, request in routing.dispatches:
        send_one(unit, _request_prompt(request, run_branch=routing.run_branch))
        unit.status = RUNNING
        append_unit_note(unit, f"outstanding review fix {_fix_request_id(request)}")
        dispatched.append(unit.name)
    return dispatched


def complete_landed_fix_requests(r: Run, landed_names: Sequence[str]) -> list[str]:
    """Clear only requests whose assigned worker was merged by this land invocation."""
    completed: list[str] = []
    for name in landed_names:
        unit = r.unit(name)
        if not unit.fix_requests:
            continue
        completed.extend(_fix_request_id(request) for request in unit.fix_requests)
        unit.fix_requests.clear()
        append_unit_note(unit, "review fix landed")
    return completed


def resubmit_review_if_ready(
    r: Run,
    revision: str,
    *,
    sender: Callable[[Unit, str], None] | None = None,
) -> bool:
    """Resubmit the landed revision through the same controller when every Work repair landed."""
    if not r.review_resubmit_pending:
        return False
    if r.operator_fix_requests or any(unit.fix_requests for unit in r.units):
        return False
    controller = r.review_controller()
    if controller is None:
        raise SystemExit("review repairs landed, but this run has no Code Review controller")
    task = normalize_task(controller.vendor, controller.task, r.backend)
    task += (
        f" The routed Work repairs are now landed on the run branch at revision {revision}. "
        "Resubmit that exact revision through this same Code Review controller and emit the next "
        "complete typed result for `review-result` collection."
    )
    send_one = sender or (lambda unit, text: say(unit, unit.pane_id, text))
    send_one(controller, task)
    controller.status = RUNNING
    append_unit_note(controller, f"resubmitted landed revision {revision}")
    r.review_resubmit_pending = False
    return True


def run(
    cmd: list[str],
    *,
    check: bool = True,
    capture: bool = True,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
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


def ensure_local_run_state_excluded() -> None:
    """Keep Orchestrate's local run state out of the driven repository's status.

    ``git rev-parse --git-path`` resolves the shared ``info/exclude`` file correctly for both a
    primary checkout and a linked worktree. Existing rules stay byte-for-byte intact; the only
    addition is one newline when the previous final line needs terminating, followed by the one
    Orchestrate rule. Repeated ``start`` calls therefore do not grow the file.
    """
    root = repo_root()
    result = run(["git", "-C", str(root), "rev-parse", "--git-path", "info/exclude"])
    exclude_path = Path(result.stdout.strip())
    if not exclude_path.is_absolute():
        exclude_path = root / exclude_path
    exclude_path.parent.mkdir(parents=True, exist_ok=True)
    existing = exclude_path.read_text() if exclude_path.exists() else ""
    if LOCAL_RUN_STATE_EXCLUDE in (line.strip() for line in existing.splitlines()):
        return
    separator = "" if not existing or existing.endswith("\n") else "\n"
    with exclude_path.open("a", encoding="utf-8") as exclude_file:
        exclude_file.write(f"{separator}{LOCAL_RUN_STATE_EXCLUDE}\n")


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

    "Commit something" means what THIS unit did, and it is read two ways. First, its own commits
    still on its branch: counted from the merge base of the run branch and the unit's branch --
    the point the unit was cut from -- so inherited work does not count. Counting from the run's
    original base did exactly that: a unit created after the first land is cut from a run branch
    that already carries the landed commits, so it counted as productive the moment it existed.
    Measured live on one run: four units with zero commits of their own each reported six. The
    consequences were all live: `check` could never say NO COMMITS after the first land, its
    LOOKS DONE fired on any post-land unit merely idle between turns, and `go`'s dependency gate
    -- which exists because a doc-review once reviewed a plan that was never written -- could
    never catch an empty dependency again. Second, a unit whose commits already landed still
    produced: see ``landed_by_merge``.
    """
    if not dep.branch:
        return False
    return branch_produced_anything(dep.branch, r)


def branch_produced_anything(branch: str, r: Run) -> bool:
    """The branch-level reading behind ``produced_anything`` -- see its docstring for the why."""
    base = r.resolved_run_ref()
    mb = run(["git", "merge-base", base, branch], check=False)
    if mb.returncode != 0:
        return False
    got = run(["git", "rev-list", "--count", f"{mb.stdout.strip()}..{branch}"], check=False)
    if got.returncode == 0 and got.stdout.strip() not in ("", "0"):
        return True
    return landed_by_merge(branch, r)


def landed_by_merge(branch: str, r: Run) -> bool:
    """Is this branch's tip the second parent of a merge on the branch this run lands onto?

    That shape, and only that shape, records work that ``land`` brought home. Git cannot distinguish
    a genuinely fast-forwarded unit from an empty unit whose branch pointer moved by merging the
    advanced run branch: both tips are on the run branch's first-parent history. Inferring either
    from ancestry would let the empty unit launch dependents and be reaped as if it saved work.

    The ref measured is the run branch commit cached at load. A run with no stored run branch
    predates the run-branch design and falls back to ``HEAD`` -- those units landed straight onto
    the operator's tree, where this shape is just as readable. Refusing that case left a legacy
    unit whose work WAS merged reading as produced nothing: ``check`` shouted NO COMMITS at landed
    work, and ``clean --merged`` would not reap it. When ``r.base`` is absent too there is no
    earlier bound to name, so the range is the ref's whole history.
    """
    ref = r.resolved_run_ref()
    tip = run(["git", "rev-parse", "--verify", "--quiet", branch], check=False)
    if tip.returncode != 0 or not tip.stdout.strip():
        return False
    revs = f"{r.base}..{ref}" if r.base else ref
    merges = run(["git", "log", "--first-parent", "--merges", "--format=%P", revs], check=False)
    if merges.returncode != 0:
        return False
    sha = tip.stdout.strip()
    for parents in merges.stdout.splitlines():
        pair = parents.split()
        if len(pair) >= 2 and pair[1] == sha:
            return True
    return False


def make_worktree(unit: Unit, r: Run, root: Path) -> None:
    """One worktree and one branch per unit. This is the whole isolation story.

    Every unit branches from the run branch, whatever it names in ``after``. A dependency's
    output is visible to it because ``land`` merged that work onto the run branch, not because
    of where this unit branches from -- that is why a phase is landed before the next one is
    launched; the land is what puts the earlier phase's work where a dependent unit can see it.
    Made at launch time, not at ``start``, so the branch opens on the run branch as it stands,
    with everything landed so far already on it.
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
        unit.branched_from = resolve_ref(branch)
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


def workspace_for(unit: Unit, default: str | None = None) -> str | None:
    """The workspace name this unit launches into.

    The unit's own field wins; otherwise the run default. Absent both, the wrapper inherits
    the caller's workspace -- today's behaviour. No other precedence.
    """
    return unit.workspace or default


def agent_argv(unit: Unit, default_workspace: str | None = None) -> list[str]:
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
    ]
    workspace = workspace_for(unit, default_workspace)
    if workspace:
        argv.extend(["--workspace", workspace])
    argv.append(unit.vendor)
    modes = VENDOR_PERMISSION.get(unit.vendor, {})
    argv.extend(modes.get(unit.permission, modes.get("auto", [])))
    flags = VENDOR_FLAGS.get(unit.vendor, {})
    for key, value in (("model", unit.model), ("effort", unit.effort)):
        template = flags.get(key)
        if value and template:
            argv.extend(template.format(value=value).split(" "))
    # Last, and verbatim. Arguments after the vendor token reach the vendor, except for the
    # few the wrapper intercepts from that position. A launcher flag that must precede the
    # vendor token cannot be expressed here -- see ``workspace``.
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
DELIVERY_WARNING = (
    "SENT BUT NEVER STARTED: idle after being given its task. Check the tab before "
    "trusting this unit -- it may have been prompted while still booting."
)


def append_unit_note(unit: Unit, note: str) -> None:
    """Add one fact without erasing a note recorded by an earlier delivery step."""
    unit.note = f"{unit.note}; {note}" if unit.note else note


def has_delivery_warning(unit: Unit) -> bool:
    """Whether the unit still carries the exact warning written by ``launch``."""
    return DELIVERY_WARNING in unit.note.split("; ")


def clear_delivery_warning(unit: Unit) -> None:
    """Remove only the delivery warning, preserving every other semicolon-delimited note."""
    unit.note = "; ".join(note for note in unit.note.split("; ") if note != DELIVERY_WARNING)


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
        append_unit_note(unit, DELIVERY_WARNING)


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
    append_unit_note(unit, f"task handed over as a file, too long to type: {path}")
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
    fallback_note = "prompted through its pane; this agent does not report interactive readiness"
    if fallback_note not in unit.note.split("; "):
        append_unit_note(unit, fallback_note)


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


def poll(
    unit: Unit,
    agents: list[dict[str, Any]] | None = None,
    *,
    timeout: float = 20,
) -> str:
    """Ask herdr what this session is doing. Absence means the session is gone.

    A caller looking at several units at once passes one already-fetched list rather than paying a
    herdr round trip per unit: an unresponsive herdr costs the timeout once instead of once a row.
    """
    handle = unit.agent_name or unit.name
    for a in live_agents(timeout=timeout) if agents is None else agents:
        if a.get("name") == handle:
            return str(a.get("agent_status", "unknown"))
    return "gone"


def live_agents(*, timeout: float = 20) -> list[dict[str, Any]]:
    """The sessions herdr is tracking right now.

    herdr is the truth a run file only mirrors, so it is asked, never remembered. A missing or
    failing herdr is not an error here: it means there is nothing to match a worktree or a session
    against, and the caller degrades -- to "no live agent" when adopting, to "gone" when polling.
    """
    proc = run(["herdr", "agent", "list"], check=False, timeout=timeout)
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
    wanted = branch if branch.startswith("refs/") else f"refs/heads/{branch}"
    path: str | None = None
    for line in proc.stdout.splitlines():
        if line.startswith("worktree "):
            path = line[len("worktree ") :]
        elif line.startswith("branch ") and line[len("branch ") :] == wanted:
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
    elif agent is not None:
        status = DONE
    elif r.unresolvable_branch:
        status = FAILED
    elif produced_anything(Unit(name=name, vendor=vendor, task="", branch=branch), r):
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
    unit's mapped status, then post one progress comment naming what happened. The comment is
    attempted only when the status write converged: it says ``board status: {status}``, and a
    comment describing a write that did not happen is worse than one not attempted -- the retry
    door is ``announce``, whose idempotency keys make a repeat safe. The comment's idempotency
    discriminator is stable across calls -- ``orchestrate:{run}:{unit}:{status}`` -- so a second
    ``land`` re-driving the same boundary meets the key the first one wrote and skips, rather than
    posting a duplicate comment.

    Returns one record per name. ``skipped`` records carry a reason and cost no writes: the run
    maps no issue for that unit, the ref is malformed, or no status applies. A run with no
    ``issues`` mapping at all returns nothing and writes nothing -- for it, this whole feature is a
    no-op. A missing reconcile_controller is reported on stderr and skipped: a missing saga is an
    ordinary state of this machine, not a failure of the land."""
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
        status_write = _reconcile_call(
            controller, "set-field-status", repo, number, status, payload=None, root=root
        )
        writes = [status_write]
        # One failure is a failure; two writes half-done is worse than one not attempted. A
        # failed write leaves no ledger key, so the retry door -- `announce` -- re-drives both
        # writes cleanly.
        if _write_converged(status_write):
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


# Controller record statuses that mean the board converged: the write happened (``written``), had
# already happened (``skipped`` on the idempotency key or the live re-read), or was re-driven
# after outside drift (``corrected``). Anything else -- ``failed``, ``gated``, ``halt`` -- is a
# write that did not happen, and the card still does not say what the run did.
CONVERGED_STATUSES = ("written", "skipped", "corrected")


def _write_converged(write: dict[str, Any]) -> bool:
    """True when one controller record means its board write actually converged."""
    return str(write.get("status")) in CONVERGED_STATUSES


def _failed_writebacks(records: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """The writeback records whose writes did not converge.

    A ``skipped`` record is not a failure -- no issue mapped, a malformed ref, no saga on this
    machine: those are designed no-ops. A record with even one unconverged write is."""
    return [
        record
        for record in records
        if "skipped" not in record
        and any(not _write_converged(write) for write in record.get("writes", []))
    ]


def _report_failed_writebacks(failures: Sequence[dict[str, Any]]) -> None:
    """Name every unit whose merge landed but whose board writeback did not converge.

    A failed writeback never undoes or blocks a merge -- the code on the run branch is right;
    only the claim that the board was updated is wrong. The retry door is named with the unit:
    ``announce`` is idempotency-keyed, so a repeat is safe."""
    for record in failures:
        name = str(record.get("unit", "?"))
        issue = str(record.get("issue", "?"))
        print(
            f"BOARD WRITEBACK FAILED: {name} ({issue}) -- the merge landed, but its card was "
            f"not updated; retry with `orchestrate.py announce {name}`"
        )


def _report_landing_cleanup_failures(failures: Sequence[tuple[Path, str]]) -> None:
    """Name every landing path that remains after cleanup."""
    for path, detail in failures:
        print(f"  LANDING CLEANUP FAILED at {path}: {detail}")


# ----------------------------------------------------------------- commands


def cmd_start(args: argparse.Namespace) -> int:
    plan = json.loads(Path(args.plan).read_text())
    assert_safe_path_component(plan["run_id"], "run id")
    units = plan_units(plan)
    assert_safe_unit_names(units)
    base = args.base or run(["git", "rev-parse", "HEAD"]).stdout.strip()
    r = Run(
        run_id=plan["run_id"],
        source=plan.get("source", ""),
        base=base,
        units=units,
        backend=plan.get("backend", "inline"),
        engine_prefs=plan.get("engine_prefs", {}),
        issues=plan.get("issues", {}),
        status_map=plan.get("status_map", {}),
        workspace=plan.get("workspace") or None,
    )
    # Before anything is written or any worktree is created: a typo in an ordering edge is a
    # unit that is never eligible, forever, and `start` is the only moment it fails cheaply.
    assert_dependencies_reachable(r.units)
    assert_vendors_available(r.units)
    assert_saga_reachable(r.units)
    r.branch = f"orch/{r.run_id}"
    exists = run(["git", "rev-parse", "--verify", "--quiet", r.branch], check=False)
    if exists.returncode != 0:
        run(["git", "branch", r.branch, base])
    ensure_local_run_state_excluded()
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


def assert_safe_path_component(value: str, label: str) -> None:
    """Refuse a value that is not one safe path component."""
    if not value:
        raise SystemExit(f"{label} must not be empty")
    if Path(value).is_absolute():
        raise SystemExit(f"{label} {value!r} must not be an absolute path")
    if "/" in value or "\\" in value:
        raise SystemExit(f"{label} {value!r} must not contain a path separator")
    if value in (".", ".."):
        raise SystemExit(f"{label} {value!r} is a path traversal")


def assert_safe_unit_names(units: list[Unit]) -> None:
    """Refuse any unit name that is not one safe path component.

    A spilled task is written to ``TASK_DIR / f"{name}.task.md"``, and in Python an absolute
    right-hand operand discards the left when joined, while ``..`` traverses -- unchecked, a name
    is a write anywhere on disk, and the pointer stored from it a read back from anywhere. Names
    are therefore refused here, where they enter a run, so a bad plan fails before anything is
    written and before any worktree exists. ``resolve_task_file`` re-checks every pointer
    independently: a run record edited by hand never passed through this function.
    """
    for unit in units:
        assert_safe_path_component(unit.name, "unit name")


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


def assert_dependencies_reachable(incoming: list[Unit], existing: set[str] | None = None) -> None:
    """Reject an ``after`` or ``serialize`` name that is in no run.

    A typo in an ordering edge otherwise produces a unit that is never eligible, forever --
    ``eligible`` waits on a name that does not exist, and ``status`` reports the wait -- and the
    failure is silent at the only moment it could have been caught cheaply. A name may point at a
    sibling in ``incoming`` itself: units routinely depend on the units they were planned with.
    """
    reachable = {u.name for u in incoming} | (existing or set())
    for unit in incoming:
        for dep in unit.after:
            if dep not in reachable:
                raise SystemExit(f"unit {unit.name!r} waits on {dep!r}, which is in no run")
        for dep in unit.serialize:
            if dep not in reachable:
                raise SystemExit(
                    f"unit {unit.name!r} serializes behind {dep!r}, which is in no run"
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
    incoming = plan_units(added)
    assert_safe_unit_names(incoming)

    existing = {u.name for u in r.units}
    seen: set[str] = set()
    for unit in incoming:
        if unit.name in existing or unit.name in seen:
            raise SystemExit(f"unit {unit.name!r} is already in this run; give the new one a name")
        seen.add(unit.name)
    assert_dependencies_reachable(incoming, existing)
    assert_single_review_controller([*r.units, *incoming])

    assert_vendors_available(incoming)
    assert_saga_reachable(incoming)
    r.units.extend(incoming)
    r.engine_prefs.update(added.get("engine_prefs", {}))
    r.issues.update(added.get("issues", {}))
    r.status_map.update(added.get("status_map", {}))
    if "workspace" in added:
        r.workspace = added["workspace"] or None
    r.save()
    print(f"added {len(incoming)}: {', '.join(u.name for u in incoming)}")
    print("`orchestrate.py go` to launch whatever is now eligible.")
    return 0


def cmd_review_result(args: argparse.Namespace) -> int:
    """Persist one typed result verbatim, then act only on its routing fields."""
    try:
        raw_result = Path(args.file).read_bytes().decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise SystemExit(f"cannot read review result {args.file!r}: {exc}") from None

    r = Run.load()
    if r.review_result == raw_result and r.review_outcome is not None:
        print("review result is already recorded byte-for-byte; nothing dispatched twice")
        return 0

    # Persist before interpreting even the routing envelope. A bad or unsupported route must not
    # discard the controller's evidence; the operator can inspect the exact string that failed.
    r.review_result = raw_result
    r.review_outcome = None
    r.save()
    routing = route_review_result(r, raw_result)
    # ``review_outcome`` is the completion marker used by the byte-identical replay guard. Keep it
    # unset until every live-worker prompt succeeds, while saving the routed fix requests first so
    # cleanup cannot reap their workers across this process boundary.
    r.review_outcome = None
    r.save()  # outstanding requests protect workers before any prompt crosses a process boundary

    try:
        dispatched = dispatch_review_routing(routing)
    except SystemExit as exc:
        r.save()
        print(f"REVIEW FIX DISPATCH FAILED: {exc}")
        return 1
    r.review_outcome = routing.outcome
    r.save()

    print(f"recorded Code Review routing outcome: {routing.outcome}")
    for name in dispatched:
        print(f"  dispatched Work repair to live worker {name}")
    for unit in routing.replacements:
        print(f"  created replacement Work worker {unit.name}; `orchestrate.py go` launches it")
    for request in routing.operator_requests:
        print(
            f"  OPERATOR ACTION: {request['owner']} owns fix {_fix_request_id(request)} "
            f"for {', '.join(request['touched_paths'])}; it was not dispatched as Work"
        )
    return 0


def cmd_go(args: argparse.Namespace) -> int:
    r = Run.load()
    if r.unresolvable_branch:
        raise SystemExit(f"run branch {r.unresolvable_branch!r} does not resolve; cannot go")
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
        if not unit.workspace and r.workspace:
            unit.workspace = r.workspace
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


def unit_commit_statuses(units: Sequence[Unit], r: Run) -> list[tuple[str, str]]:
    """Return every unit's commit count and landed state from one landing-history walk.

    Once a unit is merged, its branch tip is also in the run branch and their ordinary merge base
    is the unit tip. Counting from that point would report zero for work that plainly exists, so
    the landing merge's first parent recovers the branch point used for the honest count. Resolving
    the branch tips first lets one first-parent walk classify every unit instead of repeating the
    same run-branch history query once per row.
    """
    if r.unresolvable_branch:
        return [("?", "unknown") if unit.branch else ("-", "-") for unit in units]

    comparison = r.resolved_run_ref()
    branch_tips: dict[str, str | None] = {}
    for unit in units:
        if unit.branch and unit.branch not in branch_tips:
            branch_tips[unit.branch] = resolve_ref(unit.branch)
    resolved_tips = {branch: tip for branch, tip in branch_tips.items() if tip is not None}
    merged_by_branch = landing_merges(resolved_tips, comparison)

    statuses: list[tuple[str, str]] = []
    for unit in units:
        if not unit.branch:
            statuses.append(("-", "-"))
            continue
        tip = branch_tips[unit.branch]
        if tip is None:
            statuses.append(("?", "missing"))
            continue
        merged = merged_by_branch.get(unit.branch)
        base = merge_base(f"{merged}^1", tip) if merged else merge_base(comparison, tip)
        if base is None:
            statuses.append(("?", "yes" if merged else "unknown"))
            continue
        count = run(["git", "rev-list", "--count", f"{base}..{tip}"], check=False)
        if count.returncode != 0 or not count.stdout.strip():
            statuses.append(("?", "yes" if merged else "unknown"))
            continue
        statuses.append((count.stdout.strip(), "yes" if merged else "no"))
    return statuses


def one_line(text: str) -> str:
    """Collapse arbitrary task and note whitespace so one unit always occupies one table row."""
    return " ".join(text.split())


def status_cell(text: str) -> str:
    """Collapse and visibly bound a prose status cell."""
    collapsed = one_line(text)
    if len(collapsed) <= STATUS_TEXT_WIDTH:
        return collapsed
    return f"{collapsed[: STATUS_TEXT_WIDTH - 1]}…"


def cmd_status(args: argparse.Namespace) -> int:
    r = Run.load()
    live = {u.name: poll(u) for u in r.units if u.status == RUNNING}
    print(f"run {r.run_id}   base {r.base[:8]}   {r.source}\n")
    if r.unresolvable_branch:
        print(f"WARNING: run branch {r.unresolvable_branch!r} does not resolve\n")
    headers = (
        "unit",
        "vendor",
        "model",
        "effort",
        "state",
        "herdr",
        "commits",
        "landed",
        "task",
        "note",
    )
    rows: list[tuple[str, ...]] = []
    commit_statuses = unit_commit_statuses(r.units, r)
    for unit, (commits, is_landed) in zip(r.units, commit_statuses, strict=True):
        tail = one_line(unit.task)[:STATUS_TEXT_WIDTH]
        if unit.status == PENDING:
            why = r.wait_reason(unit)
            if why:
                # The wait is the interesting thing about a blocked unit -- its task is in the
                # plan. Naming the kind of edge is the fix for a run that looked blocked for a
                # reason that does not exist.
                tail = f"[{why}]"
        rows.append(
            (
                unit.name,
                unit.vendor,
                unit.model or "-",
                unit.effort or "-",
                unit.status,
                live.get(unit.name, "-"),
                commits,
                is_landed,
                tail,
                status_cell(unit.note),
            )
        )
    widths = [
        max([len(headers[index]), *(len(row[index]) for row in rows)])
        for index in range(len(headers))
    ]

    def format_row(values: Sequence[str]) -> str:
        return " ".join(value.ljust(widths[index]) for index, value in enumerate(values)).rstrip()

    head = format_row(headers)
    print(head)
    print("-" * (sum(widths) + len(widths) - 1))
    for row in rows:
        print(format_row(row))
    if r.review_outcome:
        outstanding_work = any(unit.fix_requests for unit in r.units)
        if r.review_resubmit_pending and outstanding_work and r.operator_fix_requests:
            state = "awaiting landed Work repairs and operator-owned fix requests"
        elif r.review_resubmit_pending and outstanding_work:
            state = "awaiting landed Work repairs"
        elif r.review_resubmit_pending and r.operator_fix_requests:
            state = "resubmission held by operator-owned fix requests"
        elif r.review_resubmit_pending:
            state = "awaiting Code Review resubmission"
        elif r.operator_fix_requests:
            state = "operator-owned fix requests outstanding"
        else:
            state = "recorded"
        print(f"\nCode Review result: {status_cell(str(r.review_outcome))} ({state})")
    for request in r.operator_fix_requests:
        owner = status_cell(str(request.get("owner", "?")))
        fix_id = status_cell(str(request.get("fix_id", "?")))
        touched_paths = status_cell(
            ", ".join(str(path) for path in request.get("touched_paths", []))
        )
        print(f"OPERATOR ACTION: {owner} owns fix {fix_id} for {touched_paths}")
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
        if (
            has_delivery_warning(unit)
            and r.unresolvable_branch is None
            and produced_anything(unit, r)
        ):
            clear_delivery_warning(unit)
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


SETTLED_STATES = frozenset({"idle", "done"})


def confirmation_count(value: str) -> int:
    """Parse a wait confirmation count, rejecting the single-observation defect."""
    try:
        count = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("confirmations must be an integer") from exc
    if count < 2:
        raise argparse.ArgumentTypeError("confirmations must be at least 2")
    return count


def confirmed_stop(
    first: str,
    further: Callable[[], str],
    *,
    interval: int,
    needed: int,
    sleep: Callable[[float], None] = time.sleep,
    deadline: float | None = None,
    monotonic: Callable[[], float] = time.monotonic,
) -> str | None:
    """Return the status if consecutive observations agree the unit has stopped, else None.

    ``blocked`` is a real stop and returns on the first sighting. ``idle`` and ``done`` need
    ``needed`` agreeing samples ``interval`` seconds apart -- an agent is also idle between
    turns, and one sample once returned ``wait`` in that gap. Any other status is not a stop.
    """
    if needed < 2:
        raise ValueError("wait requires at least two confirming observations")
    if first == "blocked":
        return "blocked"
    if first not in SETTLED_STATES:
        return None
    last = first
    for _ in range(needed - 1):
        if deadline is not None:
            remaining = deadline - monotonic()
            if remaining <= interval:
                if remaining > 0:
                    sleep(remaining)
                return None
        sleep(interval)
        last = further()
        if last == "blocked":
            return "blocked"
        if last not in SETTLED_STATES:
            return None
    return last


def report_wait(unit: Unit, status: str) -> None:
    if status == "blocked":
        print(f"{unit.name} is blocked -- it is asking a question in its own tab")
        return
    print(f"{unit.name} is {status} -- `settle`, `land`, then `go`")


def wait_on_events(
    by_pane: dict[str, Unit],
    events: Iterator[Any],
    *,
    interval: int,
    needed: int,
    poll_unit: Callable[[Unit], str],
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[Unit, str] | None:
    """Drive the event-socket path: a wake is one observation, not a settlement.

    The stream is edge-triggered, so a single ``idle`` is the think-pause this function exists
    to ignore. Confirmation is level-triggered, through ``poll_unit``, matching ``settle``.
    """
    for event in events:
        unit = by_pane.get(event.pane_id)
        if unit is None:
            continue

        status = confirmed_stop(
            event.agent_status,
            functools.partial(poll_unit, unit),
            interval=interval,
            needed=needed,
            sleep=sleep,
        )
        if status is not None:
            return unit, status
    return None


def wait_on_agent_waits(
    running: list[Unit],
    *,
    timeout: int,
    interval: int,
    needed: int,
) -> tuple[Unit, str] | None:
    """Drive the ``herdr agent wait`` fallback with the same confirmation rule as the socket.

    A successful wait-process exit is a wake, not a settlement: the first observation is a poll,
    then further polls ``interval`` apart until they agree -- or the unit is still moving and its
    wait is restarted. A failed child is not a wake and is not restarted. Every child and poll gets
    only the time left before one shared monotonic deadline.
    """
    deadline = time.monotonic() + max(timeout, 0)
    procs: dict[int, tuple[Unit, subprocess.Popen[bytes]]] = {}

    def remaining() -> float:
        return max(deadline - time.monotonic(), 0.0)

    def start_unit(unit: Unit) -> bool:
        budget = remaining()
        if budget <= 0:
            return False
        proc = _popen_herdr_wait(unit, budget)
        procs[proc.pid] = (unit, proc)
        return True

    def stop_children() -> None:
        children = [proc for _, proc in procs.values()]
        for proc in children:
            if proc.poll() is None:
                with contextlib.suppress(ProcessLookupError):
                    proc.kill()
        for proc in children:
            with contextlib.suppress(ChildProcessError):
                proc.wait()

    try:
        for unit in running:
            start_unit(unit)
        while procs:
            budget = remaining()
            if budget <= 0:
                return None
            finished = next(
                (
                    (pid, unit, proc, returncode)
                    for pid, (unit, proc) in procs.items()
                    if (returncode := proc.poll()) is not None
                ),
                None,
            )
            if finished is None:
                time.sleep(min(0.01, budget))
                continue
            pid, unit, _proc, returncode = finished
            procs.pop(pid)
            if returncode != 0:
                continue

            budget = remaining()
            if budget <= 0:
                return None

            def poll_before_deadline(current_unit: Unit = unit) -> str:
                budget = remaining()
                if budget <= 0:
                    return "timeout"
                return poll(current_unit, timeout=budget)

            status = confirmed_stop(
                poll_before_deadline(),
                poll_before_deadline,
                interval=interval,
                needed=needed,
                deadline=deadline,
            )
            if status is not None:
                return unit, status
            start_unit(unit)
    finally:
        stop_children()
    return None


def _popen_herdr_wait(unit: Unit, timeout: float) -> subprocess.Popen[bytes]:
    handle = unit.agent_name or unit.name
    return subprocess.Popen(
        [
            "herdr",
            "agent",
            "wait",
            handle,
            "--until",
            "idle",
            "--until",
            "done",
            "--until",
            "blocked",
            "--timeout",
            str(max(1, int(timeout * 1000))),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def cmd_wait(args: argparse.Namespace) -> int:
    """Block until a running unit settles, told by herdr rather than asking it.

    Subscribes to ``pane.agent_status_changed`` on each running unit's pane over herdr's event
    socket and blocks in the kernel until a line arrives. Subscriptions are keyed by pane, which is
    why a unit records its ``pane_id`` at launch -- a request without one is rejected outright.

    An agent goes idle between turns -- it finishes a tool call, returns to the prompt, thinks,
    and continues -- so a single ``idle`` is not a settlement. Idle is read ``confirmations``
    times, ``interval`` seconds apart, and only counts when consecutive readings agree, the same
    shape as ``settle``. At least two observations are mandatory. ``blocked`` is a real stop and
    returns on the first sighting, naming that state.

    Falls back to ``herdr agent wait`` when the socket is unreachable: an older herdr, a stopped
    server, or a unit launched before pane ids were recorded. That path obeys the same
    confirmation rule; a degraded path that still fired on one sample would leave the defect in
    place on exactly the machines that hit the fallback.
    """
    r = Run.load()
    running = [u for u in r.units if u.status == RUNNING]
    if not running:
        print("nothing running -- `go` to launch what is eligible")
        return 0

    needed = args.confirmations
    by_pane = {u.pane_id: u for u in running if u.pane_id}
    print(f"waiting on {', '.join(u.name for u in running)} (up to {args.timeout}s)")

    if by_pane and herdr_events is not None:
        try:
            settled = wait_on_events(
                by_pane,
                herdr_events.agent_status_events(list(by_pane), timeout=float(args.timeout)),
                interval=args.interval,
                needed=needed,
                poll_unit=poll,
            )
            if settled is None:
                print("no unit changed state before the timeout")
                return 0
            report_wait(*settled)
            return 0
        except herdr_events.HerdrEventError as exc:
            print(f"event socket unavailable ({exc}); falling back to per-unit waits")

    settled = wait_on_agent_waits(
        running,
        timeout=args.timeout,
        interval=args.interval,
        needed=needed,
    )
    if settled is None:
        print("no unit settled before the timeout")
        return 0
    report_wait(*settled)
    return 0


def resolved_retained_land(r: Run, retained: Path) -> tuple[Unit, str, str] | str:
    """Return one exact retained merge candidate, or its specific refusal reason.

    A hand-written commit message, ancestry, or a branch merely contained in ``HEAD`` is not enough:
    the retained ``HEAD`` must be a clean two-parent merge whose second parent is exactly one
    current unit tip. The caller separately requires its first parent to be the current run tip
    before publication. An exact candidate already in run-branch history needs only cleanup.
    """
    status = run(["git", "-C", str(retained), "status", "--porcelain"], check=False)
    if status.returncode != 0:
        detail = (status.stderr or status.stdout or "unknown git error").strip()
        return f"Git could not inspect the worktree status: {detail}; it is left untouched."
    if status.stdout.strip():
        return (
            "the worktree has uncommitted or unresolved changes. Resolve the conflicts there, "
            "stage and commit the merge, then rerun `orchestrate.py land`; it is left untouched."
        )
    commit = run(
        ["git", "-C", str(retained), "rev-list", "--parents", "-n", "1", "HEAD"],
        check=False,
    )
    parts = commit.stdout.split() if commit.returncode == 0 else []
    if len(parts) != 3:
        return (
            "HEAD is clean but is not a committed two-parent merge. Commit a merge of the "
            "current run tip and one current unit tip there, then rerun `orchestrate.py land`; "
            "it is left untouched."
        )
    unit_tip = parts[2]
    matches = [
        unit
        for unit in r.units
        if unit.status == DONE
        and unit.merge
        and unit.branch
        and resolve_ref(unit.branch) == unit_tip
    ]
    if len(matches) != 1:
        return (
            "HEAD is a clean two-parent merge, but its second parent does not match exactly one "
            "current DONE, merge-enabled unit tip. Restore that exact unit branch match before "
            "rerunning `orchestrate.py land`; the worktree is left untouched."
        )
    return matches[0], parts[0], parts[1]


def registered_worktree_paths() -> list[Path]:
    """Return every path Git records, including missing prunable worktrees."""
    listed = run(["git", "worktree", "list", "--porcelain", "-z"], check=False)
    if listed.returncode != 0:
        detail = (listed.stderr or listed.stdout or "unknown git error").strip()
        raise SystemExit(f"cannot inspect registered worktrees before land: {detail}")
    return [
        Path(field.removeprefix("worktree ")).resolve()
        for field in listed.stdout.split("\0")
        if field.startswith("worktree ")
    ]


def worktree_registration_exists(path: Path) -> bool:
    """Whether Git still records ``path``, including a missing prunable worktree."""
    wanted = path.resolve()
    return wanted in registered_worktree_paths()


def live_linked_worktree_at(path: Path, *, operator_worktree: Path) -> bool:
    """Whether ``path`` is an exact, separate linked worktree safe for housekeeping.

    This proof deliberately does not invoke ``git -C path``. An untrusted path may be a plain
    directory inside the operator's checkout, a symlink, or a worktree whose gitfile was rewritten
    to the primary gitdir. Read the registration and linked-worktree metadata from the repository
    side instead; only callers holding a true result may issue path-scoped Git commands.
    """
    lexical = Path(os.path.abspath(path))
    try:
        wanted = path.resolve(strict=True)
    except OSError:
        return False
    if lexical != wanted:
        return False

    registered = registered_worktree_paths()
    # Git lists its primary worktree first. The operator can also invoke Orchestrate from another
    # linked worktree, so both checkouts are distinct exclusions from a housekeeping candidate.
    if (
        not registered
        or wanted == registered[0]
        or wanted == operator_worktree.resolve()
        or wanted not in registered
    ):
        return False

    gitfile = wanted / ".git"
    if gitfile.is_symlink() or not gitfile.is_file():
        return False
    try:
        marker, separator, raw_gitdir = gitfile.read_text().strip().partition(":")
    except OSError:
        return False
    if marker != "gitdir" or not separator or not raw_gitdir.strip():
        return False
    admin = Path(raw_gitdir.strip())
    if not admin.is_absolute():
        admin = gitfile.parent / admin
    try:
        admin = admin.resolve(strict=True)
    except OSError:
        return False

    common_result = run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], check=False
    )
    reported_common = common_result.stdout.strip()
    if common_result.returncode != 0 or not reported_common:
        return False
    common = Path(reported_common).resolve()
    try:
        relative_admin = admin.relative_to(common / "worktrees")
    except ValueError:
        return False
    if len(relative_admin.parts) != 1:
        return False

    try:
        back_pointer = Path((admin / "gitdir").read_text().strip())
    except OSError:
        return False
    if not back_pointer.is_absolute():
        back_pointer = admin / back_pointer
    return back_pointer.resolve() == gitfile.resolve()


def fresh_landing_worktree_path(canonical: Path) -> Path:
    """Return the lowest unused numbered sibling of the canonical landing path."""
    registered = set(registered_worktree_paths())
    number = 1
    while True:
        candidate = canonical.with_name(f"{canonical.name}-{number}")
        if not os.path.lexists(candidate) and candidate.resolve() not in registered:
            return candidate
        number += 1


def landing_worktree_paths(r: Run, *, root: Path | None = None) -> list[Path]:
    """Discover canonical and numbered landing paths from files and Git registrations."""
    repository = (root or repo_root()).resolve()
    parent = repository / RUN_FILE.parent
    canonical_name = f"land-{r.run_id}"
    numbered = re.compile(rf"{re.escape(canonical_name)}-(\d+)")

    found: dict[Path, Path] = {}
    if parent.is_dir():
        for child in parent.iterdir():
            if child.name == canonical_name or numbered.fullmatch(child.name):
                found[Path(os.path.abspath(child))] = child
    for registered in registered_worktree_paths():
        if registered.parent == parent and (
            registered.name == canonical_name or numbered.fullmatch(registered.name)
        ):
            found.setdefault(Path(os.path.abspath(registered)), registered)

    def order(path: Path) -> tuple[int, int]:
        if path.name == canonical_name:
            return (0, 0)
        match = numbered.fullmatch(path.name)
        assert match is not None
        return (1, int(match.group(1)))

    return sorted(found.values(), key=order)


def cmd_land(args: argparse.Namespace) -> int:
    """Merge finished units back onto the run branch.

    This is the step that makes a phase real to the next one. A reviewer does not read the planner's
    branch; it opens on the run branch, and it can only find a plan there because the planner's work
    was landed first. Run it after ``settle`` and before the next ``go``.

    A unit that finished without committing anything is named here rather than passed over. That is
    the failure worth catching -- not a missing merge, but a session that produced nothing and
    reported itself done.

    With ``--clean``, a successful land then reaps on the spot -- but only the units this
    invocation merged, and they must still pass the ``clean --merged`` rule: DONE, with every
    commit on the run branch. A land that merged nothing reaps nothing: work an earlier
    invocation deliberately kept stays kept until the operator's own ``clean`` sweep. Nothing
    else is touched, and no branch is ever deleted here: that stays an explicit
    ``clean --branches``.

    Each unit is announced the moment its own merge lands, before the next merge is attempted: a
    conflict on a later unit returns out of the loop, and anything still waiting for the whole
    batch would never be announced at all -- the next land sees those units already merged and
    announces nothing either.

    The exit status is deliberate, and five-way. 0: every merge and every board write converged.
    1: the land itself could not finish -- a missing run branch, retained conflict, merge conflict,
    or ref-advance failure, named above. 2: every merge landed, but at least one board writeback did
    not converge; the units are named above with their retry. 3: every merge landed, but a landing
    path remains because it was unsafe to touch or could not be removed. A failed writeback or
    cleanup never undoes a merge: the code on the run branch is right, and only the bookkeeping is
    incomplete. 4: repairs landed but could not be resubmitted to the recorded Code Review
    controller. A caller scripting this has to be able to tell those failures apart.
    """
    r = Run.load()
    if not r.branch:
        raise SystemExit("this run has no run branch; it predates `land` -- start a new run")
    branch_tip = r.resolved_branch
    if branch_tip is None:
        raise SystemExit(f"run branch {r.branch!r} does not resolve; cannot land")

    root = repo_root()
    land_path = root / RUN_FILE.parent / f"land-{r.run_id}"
    branch_ref = r.branch if r.branch.startswith("refs/") else f"refs/heads/{r.branch}"
    landed: list[str] = []
    empty: list[str] = []
    already: list[str] = []
    held: list[str] = []
    # The bare names, kept apart from ``landed``'s display strings: ``--clean`` reaps exactly the
    # units this invocation merged, and a name recovered by stripping " (+3)" off a display string
    # would break on the first unit name containing a bracket.
    landed_names: list[str] = []
    completed_fix_ids: list[str] = []
    writeback_failures: list[dict[str, Any]] = []
    cleanup_failures: list[tuple[Path, str]] = []
    preserved_landing_paths: list[tuple[Path, str]] = []
    canonical_unavailable = False
    handled_canonical = False
    canonical_key = Path(os.path.abspath(land_path))

    held_at = worktree_on_branch(r.branch)
    if held_at:
        print(
            f"WARNING: {r.branch} is checked out at {held_at}; advancing the ref leaves files "
            "brought in by land staged for deletion in that checkout. Do not commit that index; "
            f"run `git -C {held_at} reset` first, then reconcile it with the new branch tip."
        )

    if r.conflict_worktree:
        retained = Path(os.path.abspath(Path(r.conflict_worktree)))
        retained_exists = os.path.lexists(retained)
        handled_canonical = retained_exists and retained == canonical_key
        if retained_exists:
            if live_linked_worktree_at(retained, operator_worktree=root):
                recovered = resolved_retained_land(r, retained)
                if isinstance(recovered, str):
                    print(f"  CONFLICT worktree is still retained at {retained}: {recovered}")
                    return 1
                unit, recovered_tip, recovered_base = recovered
                published = run(
                    ["git", "merge-base", "--is-ancestor", recovered_tip, branch_tip],
                    check=False,
                )
                if published.returncode not in (0, 1):
                    detail = (published.stderr or published.stdout or "unknown git error").strip()
                    print(
                        f"  CONFLICT worktree is still retained at {retained}: could not verify "
                        f"whether its exact merge is already on {r.branch}: {detail}; it is left "
                        "untouched."
                    )
                    return 1
                if published.returncode == 1:
                    if recovered_base != branch_tip:
                        print(
                            f"  CONFLICT worktree is still retained at {retained}: run branch "
                            f"{r.branch} has advanced since {unit.name}'s retained merge was built. "
                            f"Re-merge {unit.name} onto the current tip in that worktree, commit the "
                            "new merge, then rerun `orchestrate.py land`; it is left untouched."
                        )
                        return 1
                    expected_tip = branch_tip
                    recovered_ahead = run(
                        ["git", "rev-list", "--count", f"{expected_tip}..{unit.branch}"],
                        check=False,
                    ).stdout.strip()
                    advanced = run(
                        ["git", "update-ref", branch_ref, recovered_tip, expected_tip], check=False
                    )
                    if advanced.returncode != 0:
                        detail = (advanced.stderr or advanced.stdout or "unknown git error").strip()
                        print(
                            f"  LANDING REF UPDATE FAILED for {r.branch}: {detail}; resolved merge "
                            f"retained at {retained} for another `orchestrate.py land` attempt"
                        )
                        return 1
                    branch_tip = recovered_tip
                    r.record_branch_advance(recovered_tip)
                    # Publication ends this pointer's job. Persist that fact before cleanup so a
                    # filesystem failure cannot turn a published merge back into unresolved work.
                    r.conflict_worktree = None
                    r.save()
                    landed.append(f"{unit.name} (+{recovered_ahead or '?'})")
                    landed_names.append(unit.name)
                    completed_fix_ids.extend(complete_landed_fix_requests(r, [unit.name]))
                    r.save()
                    records = announce_units(r, [unit.name])
                    report_announcements(records)
                    writeback_failures.extend(_failed_writebacks(records))
                else:
                    # A clean exact retained merge already in run-branch history is published. This
                    # closes records written by the older cleanup ordering without republishing it.
                    r.conflict_worktree = None
                    r.save()

                # Protected by live_linked_worktree_at at retained-path admission: this is the
                # exact separate linked worktree whose resolved merge was just proved published.
                removed = run(["git", "worktree", "remove", "--force", str(retained)], check=False)
                if removed.returncode != 0:
                    detail = (removed.stderr or removed.stdout or "unknown git error").strip()
                    cleanup_failures.append((retained, detail))
                    preserved_landing_paths.append((retained, detail))
                    if retained == canonical_key:
                        canonical_unavailable = True
            else:
                detail = "the existing path is not a proven live separate linked worktree"
                cleanup_failures.append((retained, f"{detail}; it was left untouched"))
                preserved_landing_paths.append((retained, detail))
                if retained == canonical_key:
                    canonical_unavailable = True
                r.conflict_worktree = None
                r.save()
        else:
            r.conflict_worktree = None
            r.save()

    if os.path.lexists(land_path) and not handled_canonical:
        canonical_unavailable = True
        if live_linked_worktree_at(land_path, operator_worktree=root):
            # A previous recovery may have published and cleared its pointer before cleanup failed.
            # Remove it only with the same exact merge and ancestry proof used above. It is never
            # rebound or used for another merge.
            leftover = resolved_retained_land(r, land_path)
            if isinstance(leftover, str):
                detail = leftover
                cleanup_failures.append((land_path, f"{detail}; it was left untouched"))
                preserved_landing_paths.append((land_path, detail))
            else:
                _, leftover_tip, _ = leftover
                published = run(
                    ["git", "merge-base", "--is-ancestor", leftover_tip, branch_tip], check=False
                )
                if published.returncode == 0:
                    # Protected by live_linked_worktree_at at canonical-path admission: this
                    # separate linked worktree's exact merge was also proved published.
                    removed = run(
                        ["git", "worktree", "remove", "--force", str(land_path)], check=False
                    )
                    if removed.returncode == 0:
                        canonical_unavailable = False
                    else:
                        detail = (removed.stderr or removed.stdout or "unknown git error").strip()
                        cleanup_failures.append((land_path, detail))
                        preserved_landing_paths.append((land_path, detail))
                else:
                    if published.returncode == 1:
                        detail = f"its exact merge is not published on {r.branch}"
                    else:
                        error = (
                            published.stderr or published.stdout or "unknown git error"
                        ).strip()
                        detail = (
                            f"Git could not verify whether its exact merge is published: {error}"
                        )
                    cleanup_failures.append((land_path, f"{detail}; it was left untouched"))
                    preserved_landing_paths.append((land_path, detail))
        else:
            detail = "the existing path is not a proven live separate linked worktree"
            cleanup_failures.append((land_path, f"{detail}; it was left untouched"))
            preserved_landing_paths.append((land_path, detail))

    # The canonical land path can outlive the record pointer: `clean --merged` deliberately clears
    # a pointer to a missing directory. Inspect Git itself, and prune before constructing it again.
    if (
        not canonical_unavailable
        and not land_path.exists()
        and worktree_registration_exists(land_path)
    ):
        pruned = run(["git", "worktree", "prune", "--expire", "now"], check=False)
        if pruned.returncode != 0:
            detail = (pruned.stderr or pruned.stdout or "unknown git error").strip()
            raise SystemExit(f"cannot prune stale landing worktree registrations: {detail}")

    landing_worktree = (
        fresh_landing_worktree_path(land_path) if canonical_unavailable else land_path
    )
    for preserved, reason in preserved_landing_paths:
        print(
            f"  landing path left untouched at {preserved}: {reason}; "
            f"using fresh detached landing worktree at {landing_worktree}"
        )

    # A missing recovery directory is no longer unresolved work once its surviving Git
    # registration has been reconciled (or was already absent).
    if r.conflict_worktree:
        r.conflict_worktree = None
        r.save()
    added = run(
        ["git", "worktree", "add", "--detach", str(landing_worktree), branch_tip], check=False
    )
    if added.returncode != 0:
        detail = (added.stderr or added.stdout or "unknown git error").strip()
        raise SystemExit(f"cannot create detached landing worktree at {landing_worktree}: {detail}")

    keep_land_worktree = False
    try:
        for unit in r.units:
            if unit.status != DONE or not unit.branch:
                continue
            if not unit.merge:
                held.append(unit.name)
                continue
            ahead = run(
                ["git", "rev-list", "--count", f"{branch_tip}..{unit.branch}"], check=False
            ).stdout.strip()
            if ahead in ("", "0"):
                if unit.name not in landed_names:
                    (already if produced_anything(unit, r) else empty).append(unit.name)
                continue
            expected_tip = branch_tip
            merge = run(
                [
                    "git",
                    "-C",
                    str(landing_worktree),
                    "merge",
                    "--no-ff",
                    "--no-edit",
                    unit.branch,
                ],
                check=False,
            )
            if merge.returncode != 0:
                keep_land_worktree = True
                r.conflict_worktree = str(landing_worktree)
                r.save()
                print(
                    f"  CONFLICT landing {unit.name}; retained worktree at {landing_worktree}. "
                    "Resolve the conflicts there, stage and commit the merge, then rerun "
                    "`orchestrate.py land`; it will publish that exact merge with a guarded ref "
                    f"advance. The failed command was `git merge --no-ff {unit.branch}`"
                )
                # Name any writeback that already failed before the conflict buries the return.
                _report_failed_writebacks(writeback_failures)
                _report_landing_cleanup_failures(cleanup_failures)
                return 1
            merged_tip = run(
                ["git", "-C", str(landing_worktree), "rev-parse", "HEAD"]
            ).stdout.strip()
            advanced = run(["git", "update-ref", branch_ref, merged_tip, expected_tip], check=False)
            if advanced.returncode != 0:
                keep_land_worktree = True
                r.conflict_worktree = str(landing_worktree)
                r.save()
                detail = (advanced.stderr or advanced.stdout or "unknown git error").strip()
                print(
                    f"  LANDING REF UPDATE FAILED for {r.branch}: {detail}; "
                    f"recovery worktree retained at {landing_worktree}"
                )
                _report_failed_writebacks(writeback_failures)
                _report_landing_cleanup_failures(cleanup_failures)
                return 1
            branch_tip = merged_tip
            r.record_branch_advance(merged_tip)
            landed.append(f"{unit.name} (+{ahead})")
            landed_names.append(unit.name)
            completed_fix_ids.extend(complete_landed_fix_requests(r, [unit.name]))
            r.save()
            # The boundary just passed: write it back to the board here, where it happened, rather
            # than as a separate operator step -- and now, before the next merge is attempted, so
            # a later conflict cannot discard this unit's announcement. A no-op for a run with no
            # `issues` mapping; a missing saga says so on stderr. Re-runs dedup on the
            # controller's idempotency keys.
            records = announce_units(r, [unit.name])
            report_announcements(records)
            writeback_failures.extend(_failed_writebacks(records))
    finally:
        if not keep_land_worktree:
            # Safe by construction: this invocation created `landing_worktree` with
            # `git worktree add --detach` and has not exposed it to an external actor. A conflict
            # sets `keep_land_worktree` and skips this removal.
            removed = run(
                ["git", "worktree", "remove", "--force", str(landing_worktree)], check=False
            )
            if removed.returncode != 0:
                detail = (removed.stderr or removed.stdout or "unknown git error").strip()
                cleanup_failures.append((landing_worktree, detail))

    resubmit_failed = False
    if landed_names and r.review_resubmit_pending:
        try:
            if resubmit_review_if_ready(r, branch_tip):
                print(f"resubmitted landed revision {branch_tip} to the Code Review controller")
        except SystemExit as exc:
            resubmit_failed = True
            print(f"REVIEW RESUBMIT FAILED: {exc}")
        r.save()

    outstanding_work = any(unit.fix_requests for unit in r.units)
    if r.review_resubmit_pending and r.operator_fix_requests and not outstanding_work:
        fix_ids = ", ".join(
            status_cell(str(request.get("fix_id", "?"))) for request in r.operator_fix_requests
        )
        request_label = "request" if len(r.operator_fix_requests) == 1 else "requests"
        print(f"Code Review resubmission held by operator-owned fix {request_label}: {fix_ids}")

    print(f"landed on {r.branch}: {', '.join(landed) or 'nothing new'}")
    if completed_fix_ids:
        print(f"review fixes landed: {', '.join(completed_fix_ids)}")
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
    _report_failed_writebacks(writeback_failures)
    if cleanup_failures:
        _report_landing_cleanup_failures(cleanup_failures)
        return 3
    # ``getattr``: a caller that built its own Namespace before this flag existed has no
    # ``clean`` attribute, and a land that worked yesterday must keep working today. Reaping comes
    # after the announcement, not before: it removes the worktrees the announcement reads from. A
    # failed writeback does not hold the reap back: reaping turns on the merge, and the merge
    # landed. The sweep names only the units THIS land merged: reaping the whole run here also
    # closed the worktrees an earlier invocation deliberately kept.
    if getattr(args, "clean", False):
        closed, _ = reap(r, merged_only=True, only=landed_names)
        if closed:
            print(f"reaped: {', '.join(closed)}")
        else:
            print("nothing to reap: this land merged nothing")
    if resubmit_failed:
        return 4
    return 2 if writeback_failures else 0


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


def landed(branch: str, r: Run) -> bool | None:
    """Where this branch's work stands relative to the branch this run lands onto.

    Three answers, and the third is the one that used to be missing:

    ``True`` -- the branch has commits, and every one of them is on the run branch: landed.
    ``False`` -- the branch has commits the run branch does not have, or git cannot answer.
    ``None`` -- the branch has no commits of its own at all: nothing to land.

    ``None`` is NOT ``True``. A session that has not committed yet sits at exactly the commit it
    was cut from, and "zero commits ahead of the run branch" describes it perfectly -- which is
    also exactly what a merged branch looks like. Answering both with one yes is how
    `clean --merged` once closed the tabs and removed the worktrees of units that were still
    working, and destroyed their work. "Commits of its own" is the same question
    ``produced_anything`` answers, and gets the same reading: the unit's own commits from the
    merge base, or the merge that landed them.

    Measured against the run branch, not the operator's tree. Units land on the run branch as each
    phase finishes, and the operator's tree sees none of it until `collect`, once, at the very end.

    A run with no run branch predates `land`. There is nothing else to measure against, so the
    operator's tree it is.
    """
    base = r.resolved_run_ref()
    ahead = run(["git", "rev-list", "--count", f"{base}..{branch}"], check=False)
    if ahead.returncode != 0 or ahead.stdout.strip() not in ("", "0"):
        return False
    if branch_produced_anything(branch, r):
        return True
    return None


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


def reapable(unit: Unit, r: Run) -> bool:
    """May ``--merged`` reap this unit: its DONE work is landed and no review needs its controller.

    ``reap`` keeps a worker carrying a routed fix before this predicate is reached. Here, pending
    resubmission or operator-owned work keeps the controller available. The status gate keeps
    reaping away from anything still working:
    zero commits ahead of the run branch is also exactly what a unit that has not committed yet
    looks like, and that reading once cost four live units their worktrees. The commit gate keeps
    reaping away from a DONE unit that saved nothing: its worktree is the evidence the session
    failed, and this plugin keeps no other record.
    """
    if is_review_controller(unit) and (r.review_resubmit_pending or bool(r.operator_fix_requests)):
        return False
    if unit.status != DONE or not unit.branch:
        return False
    if r.unresolvable_branch:
        return False
    return landed(unit.branch, r) is True


def reap(
    r: Run,
    *,
    merged_only: bool,
    branches: bool = False,
    only: Sequence[str] | None = None,
) -> tuple[list[str], list[str]]:
    """Close tabs and remove worktrees; return ``(closed, kept)`` by unit name.

    A worker carrying an outstanding review fix is always kept. Otherwise, ``merged_only`` applies
    the ``--merged`` rule -- see ``reapable`` -- and keeps everything else. Without it, every other
    unit is closed regardless of its state: a last resort, run with the table in front of you,
    because it also discards the worktree that is the evidence a unit failed.

    ``only`` narrows the sweep to those unit names; every other unit is kept, whatever its
    state. ``land --clean`` passes the units that land just merged, so reaping there is a
    consequence of what that invocation did -- not a licence to close work an earlier one
    deliberately kept. ``clean`` never passes it: the operator's own sweep still sees the whole
    run, and its behaviour is unchanged.

    ``branches`` deletes the branches of the units it closes. Reaping itself never does: a branch
    is cheap, and it is the last copy of a failed unit's work. Deleting one stays an explicit
    ``clean --branches``; ``land --clean`` never passes this.
    """
    kept, closed = [], []
    root = repo_root()
    discovered_landing_paths = landing_worktree_paths(r, root=root)
    recorded_conflict = (
        Path(os.path.abspath(Path(r.conflict_worktree))) if r.conflict_worktree else None
    )
    scope = set(only) if only is not None else None
    for unit in r.units:
        if scope is not None and unit.name not in scope:
            kept.append(unit.name)
            continue
        if unit.fix_requests:
            kept.append(unit.name)
            continue
        if merged_only and not reapable(unit, r):
            kept.append(unit.name)
            continue
        if unit.tab_id:
            run(["herdr", "tab", "close", unit.tab_id], check=False)
        if unit.worktree and Path(unit.worktree).exists():
            run(["git", "worktree", "remove", "--force", unit.worktree], check=False)
        if branches and unit.branch:
            run(["git", "branch", "-D", unit.branch], check=False)
        closed.append(unit.name)

    if r.conflict_worktree:
        conflict_path = Path(r.conflict_worktree)
        label = f"conflict worktree at {conflict_path}"
        if conflict_path.exists() and merged_only:
            # A conflicted merge is, by definition, not merged. Name the recovery surface in the
            # ordinary kept report so `clean --merged` cannot look like it silently swept it up.
            kept.append(label)
        elif conflict_path.exists():
            if not live_linked_worktree_at(conflict_path, operator_worktree=root):
                kept.append(label)
            else:
                # Protected by live_linked_worktree_at immediately above: the record names an
                # exact separate linked worktree, not a symlink or another untrusted path.
                removed = run(
                    ["git", "worktree", "remove", "--force", str(conflict_path)], check=False
                )
                if removed.returncode == 0 or not conflict_path.exists():
                    closed.append(label)
                    r.conflict_worktree = None
                    r.save()
                else:
                    kept.append(label)
        else:
            # The directory was removed by hand. Clear the pointer so clean reports the filesystem
            # truth. `land` independently inspects and prunes the canonical path's Git registration
            # before reuse, because this record pointer is not the registration's owner.
            r.conflict_worktree = None
            r.save()

    for landing_path in discovered_landing_paths:
        candidate = Path(os.path.abspath(landing_path))
        # The recorded conflict path is governed by the recovery rules immediately above. Skipping
        # it here preserves the existing `clean --merged` contract and avoids a duplicate report.
        if recorded_conflict is not None and candidate == recorded_conflict:
            continue
        label = f"landing worktree at {candidate}"
        if not os.path.lexists(candidate):
            pruned = run(["git", "worktree", "prune", "--expire", "now"], check=False)
            if pruned.returncode == 0 and not worktree_registration_exists(candidate):
                closed.append(label)
            else:
                kept.append(label)
            continue
        if not live_linked_worktree_at(candidate, operator_worktree=root):
            kept.append(f"landing path at {candidate}")
            continue
        if merged_only:
            recovered = resolved_retained_land(r, candidate)
            if isinstance(recovered, str) or r.resolved_branch is None:
                kept.append(label)
                continue
            _, recovered_tip, _ = recovered
            published = run(
                ["git", "merge-base", "--is-ancestor", recovered_tip, r.resolved_branch],
                check=False,
            )
            if published.returncode != 0:
                kept.append(label)
                continue
        # Protected by live_linked_worktree_at above: the discovered candidate is an exact
        # separate linked worktree; `--merged` additionally proves its merge was published.
        removed = run(["git", "worktree", "remove", "--force", str(candidate)], check=False)
        if removed.returncode == 0 or not os.path.lexists(candidate):
            closed.append(label)
        else:
            kept.append(label)
    return closed, kept


def cmd_clean(args: argparse.Namespace) -> int:
    """Close tabs and remove worktrees.

    ``--merged`` reaps a unit only when its status is DONE and every commit it made is on the run
    branch. A RUNNING or PENDING unit is never touched, whatever its commit count -- zero commits
    ahead is also exactly what a unit looks like that has not committed yet, and reaping it
    destroys work still in flight. A DONE unit that committed nothing keeps its worktree too:
    that worktree is the evidence the session saved nothing, and this plugin keeps no other
    record.

    Without ``--merged``, every unit is closed regardless of its state. That is a last resort,
    not a routine: run it with the table in front of you.

    Branches are deleted only with ``--branches``: a branch is cheap, and it is the last copy of
    a failed unit's work.

    With ``--all``, run state is deleted only when the sweep keeps nothing. Any retained unit or
    landing worktree keeps the run record that names and explains that work. Canonical and numbered
    landing paths that no conflict record owns are discovered here as cleanup debt; only a proven
    separate linked worktree is removed, so an untrusted directory or symlink stays untouched.

    Run it after every ``land``, not once at the end. A phase's sessions are finished the moment
    their work is on the run branch, and leaving them open for the rest of the run is how a
    workspace ends up with a dozen idle tabs nobody can tell apart.
    """
    r = Run.load()
    if r.unresolvable_branch:
        print(
            f"WARNING: run branch {r.unresolvable_branch!r} does not resolve; "
            "branch-dependent cleanup checks are unavailable"
        )
    closed, kept = reap(r, merged_only=args.merged, branches=args.branches)
    if args.all and not kept:
        shutil.rmtree(RUN_FILE.parent, ignore_errors=True)
    elif args.all:
        print("run state retained because cleanup kept work")
    print(f"closed: {', '.join(closed) or 'nothing'}")
    if kept:
        print(f"kept (not done, or its work not on the run branch): {', '.join(kept)}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    """Report where the run record and the repository disagree.

    Read-only: no writes, no merges, no launches. The record is one JSON file and the truth is git
    plus herdr, and the two can drift -- a session started by hand leaves a branch with no row; a
    unit marked done saved nothing; a unit marked running finished while nobody was looking. Each
    shape of drift is reported, and finding any of them is the non-zero exit; ``adopt`` is the
    repair for the first one, and ``settle`` is the repair for the last -- it reads idle twice,
    ``interval`` seconds apart, and only marks the unit done when both readings agree.
    """
    r = Run.load()
    findings: list[str] = []
    branch_error = r.unresolvable_branch
    branch_tip = r.resolved_branch

    if branch_error:
        findings.append(f"RUN BRANCH -- run branch {branch_error!r} does not resolve")

    root = repo_root()
    recorded_conflict = (
        Path(os.path.abspath(Path(r.conflict_worktree))) if r.conflict_worktree else None
    )
    for landing_path in landing_worktree_paths(r, root=root):
        candidate = Path(os.path.abspath(landing_path))
        # A live conflict pointer remains the accepted recovery surface and keeps its existing
        # reporting behavior. This check is for otherwise unrecorded landing cleanup debt.
        if recorded_conflict is not None and candidate == recorded_conflict:
            continue
        if live_linked_worktree_at(candidate, operator_worktree=root):
            findings.append(
                f"LANDING WORKTREE {candidate} -- no run record owns this cleanup path; "
                "run `orchestrate.py clean --merged` to retry cleanup"
            )
        else:
            findings.append(
                f"LANDING PATH {candidate} -- not a proven separate linked worktree; "
                "it is left untouched for inspection"
            )

    for name, branch in discover_unrecorded(r):
        findings.append(f"UNRECORDED {name} -- branch {branch} is not a unit in this run")

    # One herdr round for the whole run, not one per row. A pending or failed unit has no session,
    # so it is never matched against the list at all.
    agents = live_agents()
    for unit in r.units:
        if branch_error is None and has_delivery_warning(unit) and not produced_anything(unit, r):
            findings.append(
                f"DELIVERY WARNING {unit.name} -- sent its task but was never observed starting, "
                "and its branch has no commits"
            )
        if unit.status not in (RUNNING, DONE):
            continue
        state = poll(unit, agents)
        if unit.status == DONE:
            if branch_error is None and not produced_anything(unit, r):
                findings.append(
                    f"NO COMMITS {unit.name} -- marked done, but its branch committed nothing"
                )
            if branch_error is None and unit.merge and r.branch and unit.branch:
                assert branch_tip is not None
                ahead = run(
                    ["git", "rev-list", "--count", f"{branch_tip}..{unit.branch}"], check=False
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
        elif branch_error is None and state in {"idle", "done"} and produced_anything(unit, r):
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


def resolve_ref(ref: str) -> str | None:
    """The commit a ref names, or None when nothing resolves -- gone, or never existed."""
    if not ref:
        return None
    got = run(["git", "rev-parse", "--verify", "--quiet", ref], check=False)
    if got.returncode != 0:
        return None
    return got.stdout.strip() or None


def merge_base(ref_a: str, ref_b: str) -> str | None:
    """The newest commit common to both refs, or None when git finds none."""
    got = run(["git", "merge-base", ref_a, ref_b], check=False)
    if got.returncode != 0:
        return None
    return got.stdout.strip() or None


def landing_merges(branch_tips: Mapping[str, str], cmp_ref: str) -> dict[str, str]:
    """Map branches to the first-parent merge that landed each current tip on ``cmp_ref``."""
    branches_by_tip: dict[str, list[str]] = {}
    for branch, tip in branch_tips.items():
        branches_by_tip.setdefault(tip, []).append(branch)
    if not branches_by_tip:
        return {}
    log = run(["git", "log", "--first-parent", "--merges", "--format=%H %P", cmp_ref], check=False)
    if log.returncode != 0:
        return {}
    found: dict[str, str] = {}
    for line in log.stdout.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        for branch in branches_by_tip.get(parts[2], []):
            found.setdefault(branch, parts[0])
    return found


def landing_merge(branch: str, cmp_ref: str) -> str | None:
    """The merge commit that landed ``branch`` onto ``cmp_ref``, or None when it never landed.

    ``land`` creates a ``--no-ff`` merge in a detached worktree and advances the run branch ref, so
    a landed unit branch is the second parent of the merge that brought it in. Finding that merge
    is what lets a landed unit still show its change -- the merge base of the merge's parents is
    where the unit branched -- instead of an empty diff that reads as "this unit changed nothing".
    """
    tip = resolve_ref(branch)
    if tip is None:
        return None
    return landing_merges({branch: tip}, cmp_ref).get(branch)


def diff_against(r: Run) -> str | None:
    """The ref a unit's change is measured against.

    The run branch when there is one; the run base for a run predating it -- those units all
    branched from the base, so it is still the honest comparison. None when neither resolves,
    which leaves nothing to diff against."""
    if r.branch and r.resolved_branch is not None:
        return r.branch
    if resolve_ref(r.base) is not None:
        return r.base
    return None


def print_git_diff(base: str, branch: str, *, stat: bool) -> None:
    """The git diff itself: a full patch, or the stat summary with ``stat``."""
    argv = ["git", "diff"]
    if stat:
        argv.append("--stat")
    argv.append(f"{base}..{branch}")
    body = run(argv).stdout.strip("\n")
    if body:
        print(body)


def show_unit_diff(unit: Unit, cmp_ref: str, *, stat: bool) -> None:
    """One unit's change -- merge base to branch -- or words for why there is nothing to show.

    An empty diff is never printed: it reads as "this unit changed nothing", and a branch
    measures empty in two ways that are both not nothing -- its work already landed on the run
    branch, or the session never committed at all. Each gets words of its own."""
    if not unit.branch:
        print(f"{unit.name}: has no branch -- it was never launched")
        return
    branch = unit.branch
    if resolve_ref(branch) is None:
        print(f"{unit.name}: branch {branch} no longer resolves -- nothing to diff")
        return
    base = merge_base(cmp_ref, branch)
    if base is None:
        print(f"{unit.name}: no commit common to {cmp_ref} and {branch} -- cannot compare")
        return
    own = run(["git", "rev-list", "--count", f"{base}..{branch}"], check=False)
    if own.returncode == 0 and own.stdout.strip() not in ("", "0"):
        print(f"{unit.name}: diff {base[:8]}..{branch}")
        print(
            f"merge base {base[:8]} of {cmp_ref} and {branch} -- work landed on {cmp_ref} "
            "by siblings does not appear in this diff"
        )
        print_git_diff(base, branch, stat=stat)
        return
    # Nothing of its own against the comparison ref. That is either "already landed" or "never
    # committed", and the run branch says which: a landed branch is the second parent of the
    # merge that brought it in.
    merged = landing_merge(branch, cmp_ref)
    if merged is None:
        print(f"{unit.name}: branch {branch} has no commits of its own")
        return
    branched = merge_base(f"{merged}^1", branch)
    if branched is None:
        print(f"{unit.name}: landed in {merged[:8]}, but its branch point no longer resolves")
        return
    print(
        f"{unit.name}: landed on {cmp_ref} in merge {merged[:8]} -- diff {branched[:8]}..{branch}"
    )
    print(f"merge base {branched[:8]} -- where {branch} branched before it was merged")
    print_git_diff(branched, branch, stat=stat)


def diff_summary(r: Run, cmp_ref: str) -> int:
    """The shape of the whole run: one stat summary per unit that has a branch."""
    branched = [u for u in r.units if u.branch]
    if not branched:
        print("no unit has a branch yet -- nothing to diff")
        return 0
    print(f"run {r.run_id} against {cmp_ref} -- each unit's change, merge base to branch")
    for unit in branched:
        print()
        show_unit_diff(unit, cmp_ref, stat=True)
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    """Show what a unit actually changed: the diff from the merge base to its branch.

    ``run-branch..unit-branch`` is the obvious comparison and the wrong one for this question:
    every unit in a phase branches from the same base, so the moment a sibling lands, that diff
    reports the sibling's additions as this unit's deletions -- in one run it showed a 391-line
    test file as deleted by a unit that had never touched it. The merge base of the run branch
    and the unit branch is where the unit branched; from there to the branch is its change, and
    nobody else's, whoever else has landed since.

    With no unit name, prints the stat summary of every unit that has a branch -- the shape of
    the whole run in one read.
    """
    r = Run.load()
    cmp_ref = diff_against(r)
    if cmp_ref is None:
        print("neither the run branch nor the run base resolves -- nothing to compare against")
        return 1
    if not args.unit:
        return diff_summary(r, cmp_ref)
    show_unit_diff(r.unit(args.unit), cmp_ref, stat=args.stat)
    return 0


def cmd_adopt(args: argparse.Namespace) -> int:
    """Put stranded unit branches back into the run record.

    A unit created outside the run -- a session launched by hand, a run file deleted around live
    work -- leaves a branch the table knows nothing about. This finds those branches and rebuilds a
    row from what is still true: the branch, its worktree, and the session herdr reports there.
    Without ``--yes`` nothing is written; the discovery is printed so the operator can see what
    would be added.
    """
    r = Run.load()
    if r.unresolvable_branch:
        print(
            f"WARNING: run branch {r.unresolvable_branch!r} does not resolve; commit-based "
            "adoption checks are unavailable, so units without a live session are marked failed"
        )
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

    s = sub.add_parser(
        "review-result",
        help="persist a typed Code Review result verbatim and route its fix requests",
    )
    s.add_argument("--file", required=True, help="UTF-8 file containing the complete typed result")
    s.set_defaults(func=cmd_review_result)

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
    s.add_argument(
        "--interval",
        type=int,
        default=20,
        help="seconds between confirming idle readings (default 20)",
    )
    s.add_argument(
        "--confirmations",
        type=confirmation_count,
        default=2,
        help="agreeing idle/done observations required before returning (default 2)",
    )
    s.set_defaults(func=cmd_wait)

    s = sub.add_parser("land", help="merge finished units onto the run branch")
    s.add_argument(
        "--clean",
        action="store_true",
        help="after a successful land, reap the units the merged rule allows; never their branches",
    )
    s.set_defaults(func=cmd_land)

    s = sub.add_parser("announce", help="write a unit's phase boundary back to its board card")
    s.add_argument("units", nargs="+", help="unit names whose boundary has passed")
    s.set_defaults(func=cmd_announce)

    s = sub.add_parser("collect", help="merge the run branch into your tree")
    s.set_defaults(func=cmd_collect)

    s = sub.add_parser("clean", help="close tabs and remove worktrees")
    s.add_argument(
        "--merged",
        action="store_true",
        help="only DONE units whose commits are all on the run branch",
    )
    s.add_argument("--branches", action="store_true", help="delete the unit branches too")
    s.add_argument(
        "--all",
        action="store_true",
        help="delete run state only when cleanup keeps no work",
    )
    s.set_defaults(func=cmd_clean)

    s = sub.add_parser("check", help="report where the run record and the repository disagree")
    s.set_defaults(func=cmd_check)

    s = sub.add_parser(
        "diff", help="what a unit actually changed: merge base to its branch, nothing else"
    )
    s.add_argument(
        "unit",
        nargs="?",
        help="unit to show; omit for a --stat summary of every unit with a branch",
    )
    s.add_argument(
        "--stat", action="store_true", help="print the stat summary instead of the full patch"
    )
    s.set_defaults(func=cmd_diff)

    s = sub.add_parser("adopt", help="write units for run branches the table does not know")
    s.add_argument(
        "--yes", action="store_true", help="write the discovered units into the run file"
    )
    s.set_defaults(func=cmd_adopt)

    args = p.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
