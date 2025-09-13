from __future__ import annotations

from dataclasses import dataclass
import time


@dataclass
class Uploaded:
    """Metadata for a resource uploaded during the smoke run."""

    token: str
    path: str
    created_at_ms: int


class SmokeError(RuntimeError):
    """Raised when the smoke flow cannot proceed (e.g., health never ready)."""


def now_ms() -> int:
    """Return current time in epoch milliseconds."""
    return int(time.time() * 1000)


