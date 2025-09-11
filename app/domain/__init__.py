"""Pure domain utilities: paths, tokens, status.

These modules are intentionally free of FastAPI/HTTP concerns so they can be
unit-tested and reused by both the server and the smoke runner.
"""
__all__ = ["paths", "tokens", "status"]