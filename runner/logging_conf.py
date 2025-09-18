"""Minimal JSON logging config for the runner (decoupled from server).

Idempotent: calling setup_logging() multiple times won't duplicate handlers.
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
    def format(self, record: LogRecord) -> str:  # type: ignore[override]
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
        }
        msg = record.msg
        if isinstance(msg, dict):
            payload.update(msg)
        else:
            payload["message"] = record.getMessage()
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
            if key not in payload:
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def _make_stream_handler(level: int) -> Handler:
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(JsonFormatter())
    return handler


def setup_logging(level: str | int = _DEFAULT_LEVEL) -> None:
    root = logging.getLogger()
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)
    if root.handlers:
        return
    root.setLevel(level)
    root.addHandler(_make_stream_handler(level))


def get_logger(name: str | None = None) -> logging.Logger:
    return logging.getLogger(name if name else __name__)


