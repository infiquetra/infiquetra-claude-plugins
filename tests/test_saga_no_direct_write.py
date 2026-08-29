"""W7 (SDLC issue #88, AE2): the Saga plugin holds no direct lifecycle-field write initiation.

What this guard proves, and the two ways a naive version of it fails (both reproduced against the
real tree during W7 planning):

1. **Zero ``set-field-status`` initiation survives in shipped Saga sources.** The write may only
   *execute* through Mission Control (``board_progression.default_board_writer`` -> mission-control's
   ``flow set-field --correction``); no Saga command may *decide and initiate* one. R30 (SDLC
   requirements) removes the authority, not the shared mechanism (plan KTD1) — so the vocabulary in
   the submission/gating core files is legal, and initiation elsewhere is not.

2. **The scan resolves the op-kind CONSTANT, not its literal value** (plan KTD6, false-green guard).
   ``/outcome`` used to compose its op through ``cert.OpKind.SET_FIELD_STATUS`` rather than the
   ``"set-field-status"`` string, so a literal grep returned zero matches in ``outcome_board_sync.py``
   while the write was fully intact. This scan therefore flags the constant symbol too.

3. **Nested run artifacts are excluded from scope** (plan KTD6, false-red guard). A nested checkout
   under ``.claude/agy/runs/**`` (a proof worktree with its own vendored copy of these files) must
   never be reported — vendored copies would keep the gate permanently red on failures that do not
   exist in shipped code.

Offline: pure filesystem + source scanning plus the REAL certificate/controller/board_progression
modules loaded by path (the single-writer-guard's house pattern). No git, no GitHub, no gh.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parent.parent
SAGA_ROOT = ROOT / "plugins" / "saga"
SCRIPTS = SAGA_ROOT / "scripts"
SUBMISSION_PATH = (SCRIPTS / "board_progression.py").resolve()

# The op-kind vocabulary is ALLOWED only in the submission/gating core: the certificate (definition
# + field gating), the one legal writer (board_progression), and the reconcile controller (its
# expected/drift vocabulary maps op kinds to readable live values — it composes none since W7).
OP_KIND_CORE_FILES = frozenset(
    {
        (SCRIPTS / "board_progression.py").resolve(),
        (SCRIPTS / "reversibility_certificate.py").resolve(),
        (SCRIPTS / "reconcile_controller.py").resolve(),
    }
)

# /outcome's resume-time detector reads HISTORICAL status keys out of the board-sync ledger; its
# family constant is a read-side vocabulary for ledger records, not an initiation. Pre-W7 campaigns
# keep their drift detection (skills/outcome/SKILL.md). Listed explicitly so the scan is a decision,
# not an accident.
OP_KIND_READ_SIDE_FILES = frozenset(
    {
        (SCRIPTS / "outcome_reconcile.py").resolve(),
    }
)

# Fenced-block initiation: a bash block that invokes the WRITING reconcile subcommand for the
# lifecycle-field op is an initiation; ``detect --op set-field-status`` is read-only and allowed.
# Python composition signature (KTD6 false-green guard): the op kind composed through the certificate
# CONSTANT — the exact shape ``outcome_board_sync.py`` had at the planning base — or the bare string
# literal outside the whitelisted core/read-side modules. A docstring that only NAMES the constant
# (documentation of absence) does not match either signature.
_PY_CONSTANT_COMPOSE_RE = re.compile(
    r"str\s*\(\s*cert\.OpKind\.SET_FIELD_STATUS|OpKind\.SET_FIELD_STATUS\s*[,)\]]"
)

_MARKER = "set-field-status"


def _load(name: str) -> ModuleType:
    # Reuse an existing module instance when one is loaded: these share the singleton module
    # identity other saga tests assert on (e.g. outcome_reconcile's re-export identity probe).
    if name in sys.modules:
        return sys.modules[name]
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


RC = _load("reconcile_controller")
CERT = _load("reversibility_certificate")

# Shipped sources only: any path under a nested checkout or run artifact is out of scope (KTD6).
_EXCLUDED_SEGMENTS = frozenset({".claude", "agy", "runs", "worktree", "__pycache__"})

# The shipped Saga source root names (markdown included — commands and skills are executable prose).
_SOURCE_DIR_NAMES = ("scripts", "skills", "commands", "agents", "hooks", "references")


def _iter_saga_sources(root: Path = SAGA_ROOT) -> list[Path]:
    """Every shipped Saga source file under ``root``, vendored/nested artifacts excluded (KTD6)."""
    files: list[Path] = []
    for name in _SOURCE_DIR_NAMES:
        directory = root / name
        if not directory.is_dir():
            continue
        for path in directory.rglob("*"):
            if not path.is_file() or path.suffix not in (".py", ".md"):
                continue
            if _EXCLUDED_SEGMENTS & set(path.relative_to(root).parts):
                continue
            files.append(path)
    return sorted(files)


def _fenced_blocks(text: str) -> list[str]:
    return re.findall(r"```(?:bash|sh|shell)?\n(.*?)```", text, re.DOTALL)


def scan_initiations(root: Path = SAGA_ROOT) -> list[tuple[str, str]]:
    """Return (relative-path, reason) for every surviving lifecycle-field write initiation.

    Two detection layers (plan KTD6):
    * Markdown skills/commands, inside FENCED blocks only: invoking the WRITE reconcile subcommand
      for ``set-field-status`` is an initiation — ``detect`` is the read-only tick /loop drives.
    * Python sources outside the op-kind core: the constant-composed op signature OR the literal
      value is an initiation — resolving the constant is the false-green guard.
    """
    rel = lambda p: str(p.relative_to(root))  # noqa: E731
    offenses: list[tuple[str, str]] = []
    for path in _iter_saga_sources(root):
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".md":
            for block in _fenced_blocks(text):
                if re.search(
                    r"reconcile_controller\.py\s+reconcile\b(?:(?!```).)*--op\s+set-field-status",
                    block,
                    re.DOTALL,
                ):
                    offenses.append(
                        (rel(path), "fenced reconcile --op set-field-status initiation")
                    )
        if path.suffix == ".py":
            resolved = path.resolve() if root == SAGA_ROOT else path
            in_core = resolved in OP_KIND_CORE_FILES
            in_read_side = resolved in OP_KIND_READ_SIDE_FILES
            if in_core or in_read_side:
                continue
            if _PY_CONSTANT_COMPOSE_RE.search(text):
                offenses.append(
                    (rel(path), "composes a set-field-status op (constant-resolved, KTD6)")
                )
            elif _MARKER in text:
                offenses.append((rel(path), "set-field-status literal outside the submission core"))
    return offenses


# ---------------------------------------------------------------------------
# AE2: zero direct set-field-status writes; the surviving paths resolve to Mission Control
# ---------------------------------------------------------------------------


def test_saga_no_direct_write_plan_initiates_no_lifecycle_write() -> None:
    """AE2/U2: no ``set-field-status`` initiation survives in skills/plan/SKILL.md — /plan decides
    no lifecycle-field move (SDLC R30)."""
    plan_skill = (SAGA_ROOT / "skills" / "plan" / "SKILL.md").read_text(encoding="utf-8")
    assert "set-field-status" not in plan_skill, (
        "skills/plan/SKILL.md still names the lifecycle-field write op"
    )
    assert "--target-state" not in plan_skill, (
        "skills/plan/SKILL.md still instructs a lifecycle-field target-state write"
    )


def test_saga_no_direct_write_work_initiates_no_lifecycle_write() -> None:
    """AE2/U2: no ``set-field-status`` initiation survives in skills/work/SKILL.md. The two nearby
    non-field ops (``issue-progress-comment`` at 4.3, ``sub-issue-close`` at 4.4) MUST survive —
    R30 governs Stage/Status only (plan U2's custody note)."""
    work_skill = (SAGA_ROOT / "skills" / "work" / "SKILL.md").read_text(encoding="utf-8")
    assert "set-field-status" not in work_skill
    assert "--target-state" not in work_skill
    assert "--op issue-progress-comment" in work_skill, (
        "the non-field progress-comment op must survive (R30 governs fields only)"
    )
    assert "--op sub-issue-close" in work_skill, (
        "the non-field sub-issue-close op must survive (an issue-state write, not a field write)"
    )


def test_saga_no_direct_write_shipped_initiations_are_zero() -> None:
    """AE2: the repository-wide scan over shipped Saga sources reports ZERO write initiations."""
    assert scan_initiations() == [], "direct lifecycle-field initiations survive:\n" + "\n".join(
        f"  {path}: {reason}" for path, reason in scan_initiations()
    )


def test_saga_no_direct_write_excludes_nested_run_artifacts(tmp_path: Path) -> None:
    """KTD6 false-red guard: a vendored copy of the tree under ``.claude/agy/runs/**`` — carrying
    its own ``reconcile_controller.py`` initiation-like text — is NOT reported. Seeded, not assumed:
    the fixture reproduces the nested-checkout shape and the scanner stays silent about it while
    still reporting the real (shipped copy) file.
    """
    nested = (
        tmp_path
        / "plugins"
        / "saga"
        / "scripts"
        / ".claude"
        / "agy"
        / "runs"
        / "agy-0-6-1-proof"
        / "worktree"
        / "plugins"
        / "saga"
        / "scripts"
    )
    nested.mkdir(parents=True)
    (nested / "reconcile_controller.py").write_text(
        'AUTO_CORRECT_OP_KINDS = frozenset({"set-field-status"})\n'
        '# init: str(cert.OpKind.SET_FIELD_STATUS), "Done"\n',
        encoding="utf-8",
    )
    shipped_violation = tmp_path / "plugins" / "saga" / "skills" / "evil" / "SKILL.md"
    shipped_violation.parent.mkdir(parents=True)
    shipped_violation.write_text(
        "```bash\npython3 reconcile_controller.py reconcile --op set-field-status\n```\n",
        encoding="utf-8",
    )
    hits = dict(scan_initiations(tmp_path / "plugins" / "saga"))
    assert hits == {"skills/evil/SKILL.md": "fenced reconcile --op set-field-status initiation"}, (
        f"nested run artifacts leaked into the scan (or the genuine hit vanished): {hits}"
    )


def test_saga_no_direct_write_resolves_op_kind_constant(tmp_path: Path) -> None:
    """KTD6 false-green guard: the scan resolves the ``OpKind.SET_FIELD_STATUS`` CONSTANT, not just
    its string value. A module that composes the constant-composed op (and never writes the literal)
    IS reported — the exact shape ``outcome_board_sync.py`` had at the planning base.
    """
    composed = tmp_path / "plugins" / "saga" / "scripts" / "evil_constant_composer.py"
    composed.parent.mkdir(parents=True, exist_ok=True)
    composed.write_text(
        "import reversibility_certificate as cert\n"
        'ops = [(str(cert.OpKind.SET_FIELD_STATUS), "In Progress")]\n',
        encoding="utf-8",
    )
    literal = tmp_path / "plugins" / "saga" / "skills" / "evil-literal" / "SKILL.md"
    literal.parent.mkdir(parents=True, exist_ok=True)
    literal.write_text(
        "```bash\npython3 reconcile_controller.py reconcile --op set-field-status\n```\n",
        encoding="utf-8",
    )
    # Control, first: the SAME file WITHOUT the constant and WITHOUT the literal is clean — proving
    # the fixture's failure comes from the constant symbol, not from its filename.
    clean = tmp_path / "plugins" / "saga" / "scripts" / "clean_module.py"
    clean.write_text("ops: list[tuple[str, str]] = []\n", encoding="utf-8")
    assert scan_initiations(tmp_path / "plugins" / "saga") == [
        (
            str(composed.relative_to(tmp_path / "plugins" / "saga")),
            "composes a set-field-status op (constant-resolved, KTD6)",
        ),
        (
            str(literal.relative_to(tmp_path / "plugins" / "saga")),
            "fenced reconcile --op set-field-status initiation",
        ),
    ]


def test_saga_no_direct_write_loop_reconcile_path_is_read_only_detect() -> None:
    """AE2: /loop's reconcile path resolves to the READ-ONLY ``detect`` tick — the drift vocabulary
    and idempotency writer sit underneath, but the skill's driven command can never write (R33)."""
    loop_skill = (SAGA_ROOT / "skills" / "loop" / "SKILL.md").read_text(encoding="utf-8")
    assert "reconcile_controller.py detect" in loop_skill, "/loop drives the read-only detect tick"
    fenced = "\n".join(
        block for block in re.findall(r"```(?:bash|sh|shell)?\n(.*?)```", loop_skill, re.DOTALL)
    )
    assert "set-field-status" in fenced, "the detect block names its op explicitly"
    assert not re.search(r"reconcile_controller\.py\s+reconcile", fenced), (
        "no fenced WRITING reconcile invocation survives in /loop's skill (R30/R33)"
    )


def test_saga_no_direct_write_outcome_issue_writes_resolve_to_mission_control() -> None:
    """AE2/U4: /outcome's surviving issue writes resolve to Mission Control — the tick delegates
    every candidate op to ``board_progression.authorize_and_write`` with the writer built by
    ``default_board_writer`` (whose ``set-field-status`` arm is the ``flow set-field --correction``
    submission), and since W7 composes NO lifecycle-field op at all."""
    sync_text = (SCRIPTS / "outcome_board_sync.py").read_text(encoding="utf-8")
    assert "_bp.authorize_and_write(" in sync_text, (
        "every /outcome board op routes through the shared authorize/write mechanism"
    )
    assert not _PY_CONSTANT_COMPOSE_RE.search(sync_text), (
        "no lifecycle-field op is composed anywhere in /outcome's board sync (W7/R34)"
    )
    assert '"set-field-status"' not in sync_text, (
        "no literal lifecycle-field op kind appears in /outcome's board sync (W7/R34)"
    )
    outcome = _load("outcome_board_sync")
    cert = _load("reversibility_certificate")
    for state in ("ready", "dispatched", "done", "blocked", "failed"):
        composed = outcome._candidate_ops(state, {})  # noqa: SLF001 — the guard reads the seam
        assert all(op != str(cert.OpKind.SET_FIELD_STATUS) for op, _t in composed), (
            f"{state}: a lifecycle-field op leaked back into /outcome's candidate set"
        )


def test_saga_no_direct_write_outcome_retains_no_autonomous_board_authority() -> None:
    """AE2/U4: no code path lets /outcome write Status except by operator-resolved submission
    through the Mission Control mutation — the reconcile-controller controller auto-correct
    allowlist is EMPTY (W7/R32), and /outcome's writer composition carries no field op."""
    controller = _load("reconcile_controller")
    assert frozenset() == controller.AUTO_CORRECT_OP_KINDS, (
        "the controller auto-correct allowlist must be empty — no autonomous field writes (R32)"
    )
    # The one remaining /outcome Status touch is the operator-resolved re-assert, which is gated
    # by the certificate BEFORE any write and drives the INJECTED writer (never a direct call).
    reconcile_text = (SCRIPTS / "outcome_reconcile.py").read_text(encoding="utf-8")
    assert "cert.authorize_write(op_kind)" in reconcile_text, (
        "the re-assert path keeps its certificate gate"
    )
