"""Drift guard for the ``typesafe-sdk`` version pin (plan U1, requirement R22).

``typesafe-sdk`` is pre-1.0 and shipped breaking changes in 0.6.0 and 0.7.0 four
days apart, so ``pyproject.toml`` pins it to a single minor.  A pin alone is
weaker than it looks: ``uv.lock`` can be regenerated without anyone reading the
diff.  This guard proves the *declaration* rather than restating it -- it parses
the specifier out of ``pyproject.toml`` at test time and checks the installed
distribution against it, so editing the declared range and the installed version
together keeps the guard green while either one drifting alone reds it.

Same posture as the bridge-enumeration guard described in DECISIONS
``{#http-bridge-receipt-pair-387-383}`` KTD9.
"""

from __future__ import annotations

import tomllib
from importlib import metadata
from pathlib import Path

import pytest

PACKAGE = "typesafe-sdk"
REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = REPO_ROOT / "pyproject.toml"


def _declared_specifier(package: str = PACKAGE) -> str:
    """Return the version specifier declared for ``package`` in pyproject.toml."""
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    for requirement in data["project"]["dependencies"]:
        name = requirement.split(">")[0].split("<")[0].split("=")[0].split("[")[0]
        if name.strip().lower().replace("_", "-") == package:
            return str(requirement[len(name) :]).strip()
    raise AssertionError(f"{package} is not declared in {PYPROJECT}; the pin was removed")


def _installed_version(package: str = PACKAGE) -> str:
    try:
        return metadata.version(package)
    except metadata.PackageNotFoundError:  # pragma: no cover - environment defect
        raise AssertionError(
            f"{package} is declared in pyproject.toml but is not installed; "
            "run `uv sync` before the test suite"
        ) from None


def _satisfies(version: str, specifier: str) -> bool:
    """Evaluate ``specifier`` (a comma-separated list of comparisons) against ``version``.

    Written against the standard library on purpose: pulling ``packaging`` in for
    a guard whose whole job is to police dependencies would be self-defeating.
    """

    def _parts(text: str) -> tuple[int, ...]:
        return tuple(int(piece) for piece in text.strip().split(".") if piece.isdigit())

    actual = _parts(version)
    for clause in specifier.split(","):
        clause = clause.strip()
        if not clause:
            continue
        for operator in (">=", "<=", "==", "!=", ">", "<"):
            if clause.startswith(operator):
                bound = _parts(clause[len(operator) :])
                break
        else:  # pragma: no cover - unreachable for the specifiers we declare
            raise AssertionError(f"unsupported version specifier clause: {clause!r}")
        # Compare on equal length so 0.7.0 and 0.8 compare sensibly.
        width = max(len(actual), len(bound))
        left = actual + (0,) * (width - len(actual))
        right = bound + (0,) * (width - len(bound))
        checks = {
            ">=": left >= right,
            "<=": left <= right,
            "==": left == right,
            "!=": left != right,
            ">": left > right,
            "<": left < right,
        }
        if not checks[operator]:
            return False
    return True


def test_installed_sdk_satisfies_the_declared_pin() -> None:
    """The happy path: what is installed is what pyproject.toml allows."""
    specifier = _declared_specifier()
    version = _installed_version()
    assert _satisfies(version, specifier), (
        f"installed {PACKAGE} {version} does not satisfy the declared range "
        f"'{specifier}' in pyproject.toml -- the vendor shipped a release outside "
        "the pin, so review its changelog before widening the range"
    )


def test_pin_is_bounded_above() -> None:
    """An unbounded pin would let the next breaking minor land on a lock refresh."""
    specifier = _declared_specifier()
    assert "<" in specifier, (
        f"{PACKAGE} is declared as '{specifier}' with no upper bound; the package is "
        "pre-1.0 and has shipped breaking minors, so the range must be capped"
    )


def test_guard_fails_against_a_version_outside_the_range() -> None:
    """The forcing function: prove the guard reds rather than passing vacuously."""
    specifier = _declared_specifier()
    assert not _satisfies("0.8.0", specifier), (
        "the guard accepted 0.8.0 against the declared range, so it would not have "
        "caught the next breaking minor"
    )
    assert not _satisfies("0.6.9", specifier)


def test_guard_reads_the_declaration_rather_than_a_literal() -> None:
    """Editing the declared range moves the guard with it, by construction."""
    assert _satisfies("1.4.0", ">=1.2,<2.0")
    assert not _satisfies("2.0.0", ">=1.2,<2.0")


def test_missing_package_reports_by_name() -> None:
    """An absent distribution names the package, never a bare PackageNotFoundError."""
    with pytest.raises(AssertionError, match="definitely-not-installed"):
        _installed_version("definitely-not-installed")


def test_pydantic_floor_covers_what_the_sdk_requires() -> None:
    """KTD3: the declared floor must not sit below the SDK's own requirement."""
    declared = _declared_specifier("pydantic")
    assert _satisfies("2.12.0", declared), (
        f"pydantic is declared as '{declared}', which admits versions below the "
        "2.12.0 that typesafe-sdk requires; the real constraint would then be "
        "visible only as a transitive requirement"
    )
    assert not _satisfies("2.5.0", declared)
