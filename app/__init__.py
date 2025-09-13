"""Application package initializer.

Keeps the package importable and is a good place to expose top-level metadata
if you want (e.g., __version__). For now, we keep it minimal.
"""
from importlib.metadata import PackageNotFoundError, version

try:  # If you later package this, __version__ will resolve; else default.
    __version__ = version("kb_indexer_stateless")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"