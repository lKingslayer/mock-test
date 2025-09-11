from __future__ import annotations

import re

__all__ = [
    "normalize_resource_path",
    "extension",
]

# Allow printable ASCII only (conservative); adjust if you need Unicode paths later.
_VALID_PATH_RE = re.compile(r"^[ -~]+$")


def normalize_resource_path(path: str) -> str:
    """Deterministically normalize a resource path.

    Rules:
    - Strip leading/trailing whitespace.
    - Convert backslashes to forward slashes (Windows→POSIX style).
    - Collapse repeated slashes.
    - Remove leading "./".
    - Remove trailing "/".
    - Lowercase only the file extension; keep the base name's original case.

    Raises:
        ValueError: if the path is empty or contains invalid characters.
    """
    if not isinstance(path, str) or not path:
        raise ValueError("resource_path must be a non-empty string")

    p = path.strip().replace("\\", "/")
    p = re.sub(r"/+", "/", p)
    if p.startswith("./"):
        p = p[2:]
    p = p.rstrip("/")
    if p == "":
        raise ValueError("resource_path resolves to empty after normalization")

    if not _VALID_PATH_RE.match(p):
        raise ValueError("resource_path contains invalid characters")

    # Lowercase only the extension (if present)
    head, dot, ext = p.rpartition(".")
    if dot:
        p = f"{head}.{ext.lower()}"
    return p


def extension(path: str) -> str:
    """Return the normalized file extension (without the dot) or empty string."""
    p = normalize_resource_path(path)
    _, dot, ext = p.rpartition(".")
    return ext if dot else ""