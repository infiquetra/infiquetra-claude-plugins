#!/usr/bin/env python3
"""External-only review admission: exclude the home vendor, halt on quorum loss.

A review under this mode is answered only by vendors other than the one whose
work is under review. Quorum that cannot be met is not a quorum of whoever
answered, and it is never filled by putting the excluded vendor back.

The bound of that guarantee is ``EXTERNAL_ONLY_GUARANTEE``. This module
governs the external-reviewer seat. It does not govern the in-session lens
fan-out.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

EXTERNAL_ONLY_MODE = "external-only"
ADDITIVE_MODE = "second-opinion"
EXTERNAL_ONLY_GUARANTEE = (
    "Under external-only the home vendor cannot be reached through the "
    "external-reviewer seat. The in-session lens fan-out is governed by the "
    "consensus-panel roster, which is separate work."
)


class ExternalOnlyError(ValueError):
    """An external-only roster or admission request is invalid."""


@dataclass(frozen=True)
class ExternalOnlyHalt:
    """Quorum cannot be met without the excluded vendor. This is not a roster."""

    reason: str
    excluded_vendor: str
    remaining: tuple[str, ...]
    quorum: int

    def __post_init__(self) -> None:
        excluded = vendor_of(self.excluded_vendor)
        if any(vendor_of(member) == excluded for member in self.remaining):
            raise ExternalOnlyError("a halt record must not list the excluded vendor as remaining")


@dataclass(frozen=True)
class ExternalOnlyRoster:
    """A constructed reviewer set that cannot contain the excluded vendor."""

    home_vendor: str
    members: tuple[str, ...]
    quorum: int

    def __post_init__(self) -> None:
        if not self.home_vendor.strip():
            raise ExternalOnlyError("home_vendor must be non-empty")
        if self.quorum < 1:
            raise ExternalOnlyError("quorum must be at least 1")
        if any(vendor_of(member) == vendor_of(self.home_vendor) for member in self.members):
            raise ExternalOnlyError("excluded vendor cannot sit on an external-only roster")
        if len(self.members) < self.quorum:
            raise ExternalOnlyError(
                "an external-only roster cannot be smaller than its quorum; "
                "admit_external_only returns a halt instead"
            )


def vendor_of(member: str) -> str:
    """Return the vendor identity of an engine key or engine id.

    Comparison is strip + casefold. ``codex/gpt-5.5-high`` and ``codex`` both
    name vendor ``codex``. Leading or inner space is not a different vendor.
    """
    if not isinstance(member, str) or not member.strip():
        raise ExternalOnlyError("member key must be a non-empty string")
    normalized = member.strip().casefold()
    vendor, sep, rest = normalized.partition("/")
    vendor = vendor.strip()
    rest = rest.strip()
    if sep and (not vendor or not rest):
        raise ExternalOnlyError("member key must be an engine id or engine/variant")
    if not vendor:
        raise ExternalOnlyError("member key must be a non-empty string")
    return vendor


def admit_external_only(
    *,
    home_vendor: str,
    candidates: Sequence[str],
    quorum: int = 1,
) -> ExternalOnlyRoster | ExternalOnlyHalt:
    """Admit a roster or halt. Never fills a hole with the excluded vendor.

    Governs the external-reviewer seat only. See ``EXTERNAL_ONLY_GUARANTEE``.
    """
    if not isinstance(home_vendor, str) or not home_vendor.strip():
        raise ExternalOnlyError("home_vendor must be non-empty")
    if quorum < 1:
        raise ExternalOnlyError("quorum must be at least 1")
    excluded = vendor_of(home_vendor)
    remaining = tuple(candidate for candidate in candidates if vendor_of(candidate) != excluded)
    if len(remaining) < quorum:
        return ExternalOnlyHalt(
            reason=(
                "external-only quorum cannot be met without the excluded vendor; no review happened"
            ),
            excluded_vendor=excluded,
            remaining=remaining,
            quorum=quorum,
        )
    return ExternalOnlyRoster(home_vendor=excluded, members=remaining, quorum=quorum)
