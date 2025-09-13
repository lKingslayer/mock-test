from __future__ import annotations

import time
from dataclasses import dataclass


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


class CreateKBError(SmokeError):
    """Raised when creating a knowledge base fails after retries."""


class UploadError(SmokeError):
    """Raised when uploading a single file fails after retries."""


class PollError(SmokeError):
    """Raised when polling children fails repeatedly."""


