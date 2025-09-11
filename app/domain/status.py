from __future__ import annotations

from enum import Enum

__all__ = [
    "Status",
    "PENDING_MS",
    "PARSED_MS",
    "salt_to_unit",
    "compute_status",
]

# Timeline thresholds (milliseconds)
PENDING_MS = 300
PARSED_MS = 1000
_UINT64_MAX = (1 << 64) - 1


class Status(str, Enum):
    pending = "pending"
    parsed = "parsed"
    indexed = "indexed"
    error = "error"


def salt_to_unit(salt: int) -> float:
    """Map a 64-bit salt to a unit interval [0,1)."""
    return (salt & _UINT64_MAX) / (_UINT64_MAX + 1)


def compute_status(*, created_at_ms: int, now_ms: int, salt: int, failure_rate: float) -> Status:
    """Deterministically derive status given time elapsed and failure_rate.

    Timeline:
      0–300 ms   -> pending
      300–1000 ms -> parsed
      >=1000 ms   -> indexed (success) or error (failure)

    The success/failure split is deterministic via `salt` and `failure_rate`.
    """
    if not (0.0 <= failure_rate <= 1.0):
        raise ValueError("failure_rate must be in [0,1]")

    elapsed = max(0, now_ms - created_at_ms)
    if elapsed < PENDING_MS:
        return Status.pending
    if elapsed < PARSED_MS:
        return Status.parsed

    # Terminal state based on the salt-drawn uniform
    u = salt_to_unit(salt)
    return Status.error if u < failure_rate else Status.indexed