#!/usr/bin/env python3
"""Fleet-wide serialized admission limits shared by every runtime.

Saga owns resolution precedence. This module owns only the normalized defaults and the closed
value that the lease broker records and enforces after resolution.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

DEFAULT_MAX_CONCURRENT = 3
DEFAULT_READONLY_MAX_CONCURRENT = 4
DEFAULT_AGGREGATE_MAX_CONCURRENT = 7

_POLICY_KEYS = frozenset({"max_concurrent", "readonly_max_concurrent", "aggregate_max_concurrent"})


class AdmissionPolicyError(ValueError):
    """A malformed or internally inconsistent admission policy."""


@dataclass(frozen=True)
class AdmissionLimits:
    """Closed, serializable limits for one resolved admission policy."""

    max_concurrent: int = DEFAULT_MAX_CONCURRENT
    readonly_max_concurrent: int = DEFAULT_READONLY_MAX_CONCURRENT
    aggregate_max_concurrent: int = DEFAULT_AGGREGATE_MAX_CONCURRENT

    def validate(self, where: str = "concurrency") -> None:
        for name, value in self.to_dict().items():
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise AdmissionPolicyError(f"{where}.{name} must be a positive integer")
        if self.max_concurrent > self.readonly_max_concurrent:
            raise AdmissionPolicyError(
                f"{where}: max_concurrent {self.max_concurrent} exceeds "
                f"readonly_max_concurrent {self.readonly_max_concurrent}"
            )
        if self.readonly_max_concurrent > self.aggregate_max_concurrent:
            raise AdmissionPolicyError(
                f"{where}: readonly_max_concurrent {self.readonly_max_concurrent} exceeds "
                f"aggregate_max_concurrent {self.aggregate_max_concurrent}"
            )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], where: str = "concurrency") -> AdmissionLimits:
        unknown = sorted(set(data) - _POLICY_KEYS)
        if unknown:
            raise AdmissionPolicyError(f"{where}: unknown field(s): {', '.join(unknown)}")
        values: dict[str, int] = {}
        for key in _POLICY_KEYS:
            if key not in data:
                continue
            value = data[key]
            if isinstance(value, bool) or not isinstance(value, int):
                raise AdmissionPolicyError(f"{where}.{key} must be a positive integer")
            values[key] = value
        limits = cls(**values)
        limits.validate(where)
        return limits

    def to_dict(self) -> dict[str, int]:
        return {
            "max_concurrent": self.max_concurrent,
            "readonly_max_concurrent": self.readonly_max_concurrent,
            "aggregate_max_concurrent": self.aggregate_max_concurrent,
        }

    def policy_sha256(self) -> str:
        """Return the stable digest used to prevent live session policy mixing."""

        encoded = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()
