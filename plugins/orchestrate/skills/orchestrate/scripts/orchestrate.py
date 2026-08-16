#!/usr/bin/env python3
"""Run a plan of units across herdr agent sessions, one git worktree each.

The plan is authored by the operator and Claude together; this script is the mechanical half.
It creates a worktree and branch per unit, launches the requested agent there, sends the unit's
saga command, waits, merges the branches back, and cleans up.

State is one JSON file. If it is wrong, delete it -- `herdr agent list` is the real truth.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

RUN_FILE = Path(".orchestrate/run.json")

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
SETUP_HINT = "no {what} flag on the command line; set it with a slash command in `setup`"

# Vendors that can be asked which models they have. The rest cannot answer, so their model name
# comes from the operator rather than from anyone's recollection.
MODEL_LIST: dict[str, list[str]] = {
    "grok": ["models"],
    "agy": ["models"],
    "opencode": ["models"],
}

PENDING, RUNNING, DONE, FAILED = "pending", "running", "done", "failed"


@dataclass
class Unit:
    name: str
    vendor: str
    task: str
    """What the session is told to do -- a saga command like "/plan #456", or free prose."""
    model: str | None = None
    effort: str | None = None
    setup: list[str] = field(default_factory=list)
    """Lines sent into the session before its task, for tier control the command line lacks.

    ``["/effort high"]`` for an agent whose CLI has no effort flag. Sent in order, each as its own
    prompt, so the session has settled into the requested tier before it is given work. Anything a
    slash command can do to a fresh session belongs here."""
    after: list[str] = field(default_factory=list)
    worktree: str | None = None
    branch: str | None = None
    tab_id: str | None = None
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
    engine_prefs: dict[str, dict[str, str]] = field(default_factory=dict)
    """Saga's per-stage external-engine answers, decided once in the interview.

    Keyed by saga stage (``code-review``, ``doc-review``, ``work``, …), each value carrying
    ``intent`` and optionally ``model`` and ``effort``. Written into every worktree so a dispatched
    saga command finds the answer already stored and never stops to ask a question in a tab nobody
    is watching. See ``write_engine_prefs``.
    """

    @classmethod
    def load(cls, path: Path = RUN_FILE) -> Run:
        raw = json.loads(path.read_text())
        return cls(
            run_id=raw["run_id"],
            source=raw["source"],
            base=raw["base"],
            units=[Unit(**u) for u in raw["units"]],
            engine_prefs=raw.get("engine_prefs", {}),
        )

    def save(self, path: Path = RUN_FILE) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "run_id": self.run_id,
            "source": self.source,
            "base": self.base,
            "engine_prefs": self.engine_prefs,
            "units": [asdict(u) for u in self.units],
        }
        path.write_text(json.dumps(payload, indent=2) + "\n")

    def unit(self, name: str) -> Unit:
        for u in self.units:
            if u.name == name:
                return u
        raise SystemExit(f"no unit named {name!r}")

    def eligible(self) -> list[Unit]:
        done = {u.name for u in self.units if u.status == DONE}
        return [
            u for u in self.units if u.status == PENDING and all(dep in done for dep in u.after)
        ]


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
    """
    try:
        proc = subprocess.run(cmd, capture_output=capture, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        if check:
            raise SystemExit(f"timed out after {timeout}s: {' '.join(cmd)}") from None
        return subprocess.CompletedProcess(cmd, returncode=124, stdout="", stderr="timed out")
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


def make_worktree(unit: Unit, r: Run, root: Path) -> None:
    """One worktree and one branch per unit. This is the whole isolation story.

    A unit with dependencies branches from the last one it named, so a ``/work`` unit opens on top
    of the ``/plan`` unit's output rather than on bare ``base``. Made at launch time, not at
    ``start``, because the dependency's branch does not have its commits until it has run.
    """
    path = root.parent / f"orch-{unit.name}"
    branch = f"orch/{unit.name}"
    base = r.unit(unit.after[-1]).branch if unit.after else r.base
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
    got = run([name, *sub], check=False, timeout=20)
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
    flags = VENDOR_FLAGS.get(unit.vendor, {})
    for key, value in (("model", unit.model), ("effort", unit.effort)):
        template = flags.get(key)
        if value and template:
            argv.extend(template.format(value=value).split(" "))
    return argv


def launch(unit: Unit) -> None:
    proc = run(agent_argv(unit))
    pane_id = None
    try:
        info = json.loads(proc.stdout.strip().splitlines()[-1])
        unit.tab_id = info.get("tab_id")
        unit.agent_name = info.get("agent_name", unit.name)
        pane_id = info.get("pane_id")
    except (ValueError, IndexError):
        unit.note = "launched, but the wrapper's JSON could not be read"
    send(unit, pane_id)
    unit.status = RUNNING


def say(unit: Unit, pane_id: str | None, text: str) -> None:
    """Put one line into the session.

    ``herdr agent prompt`` is the right door, but it refuses any agent that never reports
    ``interactive_ready`` -- qwen is one today. For those, type into the pane instead, which is what
    the operator would do by hand.
    """
    handle = unit.agent_name or unit.name
    attempt = run(["herdr", "agent", "prompt", handle, text], check=False)
    if attempt.returncode == 0:
        return
    if not pane_id:
        raise SystemExit(f"{unit.name}: agent prompt refused and no pane to fall back to")
    run(["herdr", "pane", "run", pane_id, text])
    unit.note = "prompted through its pane; this agent does not report interactive readiness"


def send(unit: Unit, pane_id: str | None) -> None:
    """Set the session up, then give it its task.

    Setup goes first and separately: a tier has to be in force before the work starts, and a slash
    command bundled into the same message as the task is just text the agent reads.
    """
    for line in unit.setup:
        say(unit, pane_id, line)
    say(unit, pane_id, unit.task)


def poll(unit: Unit) -> str:
    """Ask herdr what this session is doing. Absence means the session is gone."""
    proc = run(["herdr", "agent", "list"], check=False)
    try:
        agents = json.loads(proc.stdout)["result"]["agents"]
    except (ValueError, KeyError):
        return "unknown"
    handle = unit.agent_name or unit.name
    for a in agents:
        if a.get("name") == handle:
            return str(a.get("agent_status", "unknown"))
    return "gone"


# ----------------------------------------------------------------- commands


def cmd_start(args: argparse.Namespace) -> int:
    plan = json.loads(Path(args.plan).read_text())
    base = args.base or run(["git", "rev-parse", "HEAD"]).stdout.strip()
    r = Run(
        run_id=plan["run_id"],
        source=plan.get("source", ""),
        base=base,
        units=[Unit(**u) for u in plan["units"]],
        engine_prefs=plan.get("engine_prefs", {}),
    )
    assert_vendors_available(r.units)
    r.save()
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

    missing = [n for n in VENDOR_FLAGS if n not in {x for x, _ in rows}]
    if missing:
        print(f"known but not available on this machine: {', '.join(missing)}")
    unknown = [n for n in launchable() if n not in VENDOR_FLAGS]
    if unknown:
        print(f"launchable but not vendors orchestrate drives: {', '.join(unknown)}")

    if args.models:
        print("\nmodels, asked of each vendor that can answer:")
        for name, _ in rows:
            found = models(name)
            if found:
                print(f"  {name}:")
                for m in found[: args.limit]:
                    print(f"    {m}")
                if len(found) > args.limit:
                    print(f"    ... and {len(found) - args.limit} more (`{name} models`)")
            else:
                print(f"  {name}: cannot list its models — ask the operator for the name")

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

    assert_vendors_available(incoming)
    r.units.extend(incoming)
    r.engine_prefs.update(added.get("engine_prefs", {}))
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
        make_worktree(unit, r, root)
        r.save()  # persist the worktree before the launch, so a failure is not relaunched blind
        print(f"launching {unit.name} ({unit.vendor}) -> {unit.task}")
        try:
            launch(unit)
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
        print(
            f"{u.name:10s} {u.vendor:9s} {(u.model or '-'):14s} {(u.effort or '-'):7s} "
            f"{u.status:9s} {live.get(u.name, '-'):9s} {u.task[:44]}"
        )
    return 0


def cmd_settle(args: argparse.Namespace) -> int:
    """Mark running units done when their session goes idle. No inference beyond that."""
    r = Run.load()
    for unit in r.units:
        if unit.status != RUNNING:
            continue
        state = poll(unit)
        if state in {"idle", "done"}:
            unit.status = DONE
            print(f"  {unit.name}: {state} -> done")
        elif state == "gone":
            unit.status = FAILED
            unit.note = "session disappeared"
            print(f"  {unit.name}: session gone -> failed")
    r.save()
    return 0


def cmd_collect(args: argparse.Namespace) -> int:
    r = Run.load()
    dirty = run(["git", "status", "--porcelain"]).stdout.strip()
    if dirty:
        print("your working tree has uncommitted changes; git will refuse to merge into it.")
        print("commit or stash them, then rerun collect. what is uncommitted:\n")
        print("\n".join(f"  {line}" for line in dirty.splitlines()[:15]))
        return 1
    merged, skipped = [], []
    for unit in r.units:
        if unit.status != DONE or not unit.branch:
            skipped.append(unit.name)
            continue
        ahead = run(["git", "rev-list", "--count", f"HEAD..{unit.branch}"]).stdout.strip()
        if ahead == "0":
            skipped.append(f"{unit.name} (no commits)")
            continue
        proc = run(["git", "merge", "--no-ff", "--no-edit", unit.branch], check=False)
        if proc.returncode == 0:
            merged.append(f"{unit.name} (+{ahead})")
        else:
            print(f"  CONFLICT merging {unit.branch} -- resolve it yourself, then rerun collect")
            return 1
    print(f"merged: {', '.join(merged) or 'nothing'}")
    if skipped:
        print(f"skipped: {', '.join(skipped)}")
    return 0


def cmd_clean(args: argparse.Namespace) -> int:
    r = Run.load()
    for unit in r.units:
        if unit.tab_id:
            run(["herdr", "tab", "close", unit.tab_id], check=False)
        if unit.worktree and Path(unit.worktree).exists():
            run(["git", "worktree", "remove", "--force", unit.worktree], check=False)
        if args.branches and unit.branch:
            run(["git", "branch", "-D", unit.branch], check=False)
    if args.all:
        shutil.rmtree(RUN_FILE.parent, ignore_errors=True)
    print("cleaned.")
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

    s = sub.add_parser("expand", help="append units to a run in flight, once a phase names them")
    s.add_argument("--plan", required=True)
    s.set_defaults(func=cmd_expand)

    s = sub.add_parser("go", help="launch every unit whose dependencies are met")
    s.add_argument("--limit", type=int, default=0, help="launch at most this many now")
    s.set_defaults(func=cmd_go)

    s = sub.add_parser("status", help="show the table")
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("settle", help="mark running units done when their session goes idle")
    s.set_defaults(func=cmd_settle)

    s = sub.add_parser("collect", help="merge each finished unit's branch")
    s.set_defaults(func=cmd_collect)

    s = sub.add_parser("clean", help="close tabs and remove worktrees")
    s.add_argument("--branches", action="store_true", help="delete the unit branches too")
    s.add_argument("--all", action="store_true", help="delete the run file too")
    s.set_defaults(func=cmd_clean)

    args = p.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
