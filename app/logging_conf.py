"""Logging configuration for the service.

This module sets up a JSON-line logger suitable for CI/CD and local dev.
It is idempotent: calling setup_logging() multiple times won't duplicate handlers.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import UTC, datetime
from logging import Handler, LogRecord
from typing import Any

_DEFAULT_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


class JsonFormatter(logging.Formatter):
    """A minimal JSON formatter.

    - Produces one JSON object per line.
    - Includes common fields (ts, level, logger, message) and any structured
      extras provided via `logger.info("msg", extra={...})`.
    """

    def format(self, record: LogRecord) -> str:  # type: ignore[override]
        # Base event structure
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
        }

        # If the original message was a dict, include it verbatim; otherwise use getMessage().
        msg = record.msg
        if isinstance(msg, dict):
            payload.update(msg)
        else:
            payload["message"] = record.getMessage()

        # Merge any custom structured fields from record.__dict__
        for key, value in record.__dict__.items():
            if key in {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
            }:
                continue
            # Do not overwrite core keys if present
            if key not in payload:
                payload[key] = value

        # Attach exception info if present
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


def _make_stream_handler(level: int) -> Handler:
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(JsonFormatter())
    return handler


def setup_logging(level: str | int = _DEFAULT_LEVEL) -> None:
    """Configure root and uvicorn loggers for JSON output.

    Idempotent: only attaches handlers if none are present.
    """
    root = logging.getLogger()

    # Normalize level
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    if root.handlers:  # Prevent double configuration under reload / tests
        return

    root.setLevel(level)
    root.addHandler(_make_stream_handler(level))

    # Align common server loggers to the same handler/level
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.setLevel(level)
        # Inherit root handler; ensure no duplicate handlers are attached.
        lg.propagate = True
        for h in list(lg.handlers):
            lg.removeHandler(h)


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a module-scoped logger.

    Usage: logger = get_logger(__name__)
    """
    return logging.getLogger(name if name else __name__)