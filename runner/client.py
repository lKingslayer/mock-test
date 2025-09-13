from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import httpx

from app.domain.paths import normalize_resource_path
from app.logging_conf import get_logger
from runner.types import CreateKBError, PollError, SmokeError, Uploaded, UploadError

logger = get_logger("runner.client")


async def wait_for_health(base_url: str, timeout_s: float = 20.0) -> None:
    """Ping /health until it returns ok or raise after a timeout.

    - Tries repeatedly for `timeout_s` seconds
    - Logs a concise status when health is confirmed
    """
    import time

    deadline = time.monotonic() + timeout_s
    async with httpx.AsyncClient(base_url=base_url, timeout=5.0) as client:
        while time.monotonic() < deadline:
            try:
                r = await client.get("/health")
                if r.status_code == 200 and r.json().get("ok") is True:
                    logger.info("health.ok", extra={"event": "health_ok"})
                    return
            except Exception:
                pass
            import asyncio

            await asyncio.sleep(0.25)
    raise SmokeError("Health check did not pass within timeout")


async def create_kb(base_url: str, name: str | None = None, *, retries: int = 3) -> str:
    """Create a knowledge base and return its id, with basic retry.

    - Retries simple transient failures up to `retries` times
    - Logs each attempt and the final kb_id on success
    """
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
                payload = {"name": name} if name else None
                r = await client.post("/knowledge_bases", json=payload)
                r.raise_for_status()
                kb_id = r.json()["knowledge_base_id"]
                logger.info(
                    "kb.created",
                    extra={
                        "event": "kb_created",
                        "kb_id": kb_id,
                        "attempt": attempt + 1,
                    },
                )
                return kb_id
        except Exception as e:  # pragma: no cover - network flakiness
            last_err = e
            logger.warning(
                "kb.create_retry",
                extra={
                    "event": "kb_create_retry",
                    "attempt": attempt + 1,
                    "error": str(e),
                },
            )
    raise CreateKBError(str(last_err) if last_err else "create_kb failed")


async def upload_one(
    client: httpx.AsyncClient, kb_id: str, path: Path, *, retries: int = 2
) -> Uploaded:
    """Upload one file and return its token + metadata, with retry.

    - Uses the stateless upload endpoint; the file bytes are not inspected server-side
    - Retries a couple of times on transient errors
    - Logs success and retry attempts with the normalized path
    """
    rp = normalize_resource_path(str(path))
    files = {
        "resource_type": (None, "file"),
        "resource_path": (None, rp),
        "file": (path.name, path.read_bytes()),
    }
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            r = await client.post(f"/knowledge_bases/{kb_id}/resources", files=files)
            r.raise_for_status()
            data = r.json()
            return Uploaded(
                token=data["resource_id"],
                path=data["resource_path"],
                created_at_ms=data["created_at"],
            )
        except Exception as e:  # pragma: no cover
            last_err = e
            logger.warning(
                "upload.retry",
                extra={
                    "event": "upload_retry",
                    "kb_id": kb_id,
                    "path": rp,
                    "attempt": attempt + 1,
                    "error": str(e),
                },
            )
    raise UploadError(f"upload failed for {path}: {last_err}")


async def upload_all(base_url: str, kb_id: str, files: Iterable[Path]) -> list[Uploaded]:
    """Upload files concurrently and return metadata for successful uploads.

    - Continues even if some uploads fail
    - Logs a short summary of counts
    """
    import asyncio

    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        tasks = [upload_one(client, kb_id, p) for p in files]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        uploaded: list[Uploaded] = []
        for res in results:
            if isinstance(res, Exception):
                # Skip failed uploads but keep going
                continue
            uploaded.append(res)
        logger.info(
            "upload.summary",
            extra={
                "event": "upload_summary",
                "requested": len(list(files)),
                "succeeded": len(uploaded),
                "failed": len(results) - len(uploaded),
            },
        )
        return uploaded


async def poll_children(
    base_url: str, kb_id: str, tokens: list[str], *, retries: int = 3
) -> list[dict]:
    """Fetch current statuses for the given tokens, with retry.

    - Calls the list-children endpoint and returns the raw items
    - Retries transient failures a few times
    """
    last_err: Exception | None = None
    for _ in range(retries):
        try:
            async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
                params = [("ids", t) for t in tokens]
                r = await client.get(f"/knowledge_bases/{kb_id}/resources/children", params=params)
                r.raise_for_status()
                return r.json()["items"]
        except Exception as e:  # pragma: no cover
            last_err = e
            logger.warning(
                "poll.retry",
                extra={
                    "event": "poll_retry",
                    "kb_id": kb_id,
                    "count": len(tokens),
                    "error": str(e),
                },
            )
    raise PollError(str(last_err) if last_err else "poll failed")


