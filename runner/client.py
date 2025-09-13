from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import httpx

from app.domain.paths import normalize_resource_path
from runner.types import SmokeError, Uploaded


async def wait_for_health(base_url: str, timeout_s: float = 20.0) -> None:
    """Wait until /health reports ok or raise after timeout."""
    import time

    deadline = time.monotonic() + timeout_s
    async with httpx.AsyncClient(base_url=base_url, timeout=5.0) as client:
        while time.monotonic() < deadline:
            try:
                r = await client.get("/health")
                if r.status_code == 200 and r.json().get("ok") is True:
                    return
            except Exception:
                pass
            import asyncio

            await asyncio.sleep(0.25)
    raise SmokeError("Health check did not pass within timeout")


async def create_kb(base_url: str, name: str | None = None) -> str:
    """Create a knowledge base and return its id."""
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        payload = {"name": name} if name else None
        r = await client.post("/knowledge_bases", json=payload)
        r.raise_for_status()
        return r.json()["knowledge_base_id"]


async def upload_one(client: httpx.AsyncClient, kb_id: str, path: Path) -> Uploaded:
    """Upload a single file and return its token + metadata."""
    rp = normalize_resource_path(str(path))
    files = {
        "resource_type": (None, "file"),
        "resource_path": (None, rp),
        "file": (path.name, path.read_bytes()),
    }
    r = await client.post(f"/knowledge_bases/{kb_id}/resources", files=files)
    r.raise_for_status()
    data = r.json()
    return Uploaded(
        token=data["resource_id"],
        path=data["resource_path"],
        created_at_ms=data["created_at"],
    )


async def upload_all(base_url: str, kb_id: str, files: Iterable[Path]) -> list[Uploaded]:
    """Upload all files concurrently and return their metadata."""
    import asyncio

    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        tasks = [upload_one(client, kb_id, p) for p in files]
        return list(await asyncio.gather(*tasks))


async def poll_children(base_url: str, kb_id: str, tokens: list[str]) -> list[dict]:
    """Fetch current statuses for the given tokens."""
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        params = [("ids", t) for t in tokens]
        r = await client.get(f"/knowledge_bases/{kb_id}/resources/children", params=params)
        r.raise_for_status()
        return r.json()["items"]


