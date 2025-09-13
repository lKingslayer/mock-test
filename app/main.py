"""FastAPI app factory and minimal health endpoint + API routes (Phase 3)."""
from __future__ import annotations

import os
import time
from collections.abc import Callable
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from app.api import router as api_router
from app.logging_conf import get_logger, setup_logging

# Configure logging before anything else.
setup_logging()
logger = get_logger("app")


def create_app() -> FastAPI:
    app = FastAPI(
        title="KB Indexer (Stateless)",
        version=os.getenv("APP_VERSION", "0.1.0"),
    )

    @app.on_event("startup")
    async def _on_startup() -> None:
        logger.info("startup", extra={"event": "startup"})

    @app.on_event("shutdown")
    async def _on_shutdown() -> None:
        logger.info("shutdown", extra={"event": "shutdown"})

    @app.middleware("http")
    async def request_logger(request: Request, call_next: Callable[[Request], Response]):
        """Minimal JSON request logging with correlation id.

        - If the client sends X-Request-ID we propagate it; otherwise we mint one
        - Logs a start and end event with method/path/status/elapsed_ms
        - Attaches X-Request-ID header on the response for easy tracing
        """
        # Reuse incoming X-Request-ID if present; else mint a new one.
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        request.state.request_id = request_id

        start = time.perf_counter()
        logger.info(
            "request.start",
            extra={
                "event": "request_start",
                "method": request.method,
                "path": request.url.path,
                "request_id": request_id,
            },
        )
        try:
            response = await call_next(request)
        except Exception as exc:  # Log and re-raise to let FastAPI handle 500
            logger.exception(
                "request.error",
                extra={
                    "event": "request_error",
                    "path": request.url.path,
                    "method": request.method,
                    "request_id": request_id,
                },
            )
            raise exc
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000.0

        # Attach request id for client correlation
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request.end",
            extra={
                "event": "request_end",
                "status_code": response.status_code,
                "elapsed_ms": round(elapsed_ms, 2),
                "request_id": request_id,
            },
        )
        return response

    # Health route
    @app.get("/health", summary="Liveness/readiness check")
    async def health() -> JSONResponse:
        return JSONResponse(content={"ok": True})

    # Phase 3: attach API router
    app.include_router(api_router)

    return app


# ASGI entrypoint for uvicorn: `uvicorn app.main:app --port 8000`
app = create_app()