#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import httpx

# Reuse the same JSON logging as the server for consistent artifacts
try:
    from app.logging_conf import setup_logging, get_logger
except Exception:  # pragma: no cover
    # Minimal fallback if project imports aren't available
    import logging

    def setup_logging(level: str | int = "INFO") -> None:
        logging.basicConfig(level=getattr(logging, str(level).upper(), logging.INFO))

    def get_logger(name: str | None = None) -> logging.Logger:
        return logging.getLogger(name or __name__)

from app.domain.paths import extension, normalize_resource_path


setup_logging()
logger = get_logger("runner")


@dataclass
class Uploaded:
    token: str
    path: str
    created_at_ms: int


class SmokeError(RuntimeError):
    pass


def _now_ms() -> int:
    return int(time.time() * 1000)


async def wait_for_health(base_url: str, timeout_s: float = 20.0) -> None:
    """Wait until /health reports ok or raise after timeout."""
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
            await asyncio.sleep(0.25)
    raise SmokeError("Health check did not pass within timeout")


async def create_kb(base_url: str, name: str | None = None) -> str:
    """Create a knowledge base and return its id."""
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        payload = {"name": name} if name else None
        r = await client.post("/knowledge_bases", json=payload)
        r.raise_for_status()
        kb_id = r.json()["knowledge_base_id"]
        logger.info("kb.created", extra={"event": "kb_created", "kb_id": kb_id})
        return kb_id


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
    return Uploaded(token=data["resource_id"], path=data["resource_path"], created_at_ms=data["created_at"])


async def upload_all(base_url: str, kb_id: str, files: list[Path]) -> list[Uploaded]:
    """Upload all files concurrently and return their metadata."""
    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        tasks = [upload_one(client, kb_id, p) for p in files]
        return await asyncio.gather(*tasks)


async def poll_children(base_url: str, kb_id: str, tokens: list[str]) -> list[dict]:
    """Fetch current statuses for the given tokens."""
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        # Use repeated query params ?ids=tok&ids=tok
        params = [("ids", t) for t in tokens]
        r = await client.get(f"/knowledge_bases/{kb_id}/resources/children", params=params)
        r.raise_for_status()
        return r.json()["items"]


def _percentile(values: list[float], p: float) -> float:
    """Compute the p-th percentile using linear interpolation."""
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * p
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    d0 = s[f] * (c - k)
    d1 = s[c] * (k - f)
    return d0 + d1


def _validate_and_collect_fixtures(fixtures_dir: Path) -> list[Path]:
    """Return the list of fixture files, asserting exactly 10 exist."""
    if not fixtures_dir.exists():
        raise SmokeError(f"fixtures directory not found: {fixtures_dir}")
    all_files = sorted([p for p in fixtures_dir.rglob("*") if p.is_file()])
    if len(all_files) != 10:
        raise SmokeError(f"expected exactly 10 fixture files, found {len(all_files)}")
    return all_files


async def _poll_until_terminal(
    *, base_url: str, kb_id: str, tokens: list[str], poll_interval_s: float, timeout_s: float
) -> tuple[list[dict], dict[str, int]]:
    """Poll children until all terminal or timeout; return final items and terminal times."""
    started = time.monotonic()
    terminal_at: dict[str, int] = {}
    last_items: list[dict] = []
    while True:
        if time.monotonic() - started > timeout_s:
            break
        items = await poll_children(base_url, kb_id, tokens)
        last_items = items
        now_ms = _now_ms()
        for it in items:
            status = it.get("status")
            rid = it["resource_id"]
            if status in ("indexed", "error") and rid not in terminal_at:
                terminal_at[rid] = int(it.get("updated_at", now_ms))
        if len(terminal_at) == len(tokens):
            break
        await asyncio.sleep(poll_interval_s)
    return last_items, terminal_at


def _summarize(
    *, uploaded: list[Uploaded], last_items: list[dict], terminal_at: dict[str, int]
) -> tuple[dict, int]:
    """Compute summary dict and exit code from final states."""
    durations_ms: list[float] = []
    success = 0
    failure = 0
    per_ext: dict[str, dict[str, int]] = {}
    failures_detail: list[dict] = []

    items_by_id = {it["resource_id"]: it for it in (last_items or [])}
    for u in uploaded:
        ext = extension(u.path)
        per_ext.setdefault(ext, {"indexed": 0, "error": 0})
        term_ms = terminal_at.get(u.token)
        it = items_by_id.get(u.token, {})
        status = it.get("status")
        if term_ms is not None:
            durations_ms.append(term_ms - u.created_at_ms)
        if status == "indexed":
            success += 1
            per_ext[ext]["indexed"] += 1
        elif status == "error":
            failure += 1
            per_ext[ext]["error"] += 1
            failures_detail.append(
                {"path": u.path, "error_code": it.get("error_code"), "error_message": it.get("error_message")}
            )
        else:
            failures_detail.append({"path": u.path, "error_code": "timeout", "error_message": "not terminal"})

    avg_ms = (sum(durations_ms) / len(durations_ms)) if durations_ms else 0.0
    p95_ms = _percentile(durations_ms, 0.95)
    max_ms = max(durations_ms) if durations_ms else 0.0
    summary = {
        "component": "runner",
        "event": "summary",
        "uploaded": len(uploaded),
        "indexed_count": success,
        "error_count": failure,
        "timings": {"avg_ms": round(avg_ms, 2), "p95_ms": round(p95_ms, 2), "max_ms": round(max_ms, 2)},
        "per_extension": per_ext,
        "failures": failures_detail,
    }
    all_terminal = (success + failure) == len(uploaded)
    exit_code = 0 if (all_terminal and success > 0) else 1
    return summary, exit_code


async def run_smoke(
    *,
    base_url: str,
    fixtures_dir: Path,
    poll_interval_s: float = 0.25,
    timeout_s: float = 30.0,
) -> int:
    """Run end-to-end smoke: health, create KB, upload, poll, summarize."""
    # 1) wait for health
    await wait_for_health(base_url)

    # 2) ensure fixtures
    all_files = _validate_and_collect_fixtures(fixtures_dir)

    # 3) create kb
    kb_id = await create_kb(base_url)

    # 4) concurrent uploads
    uploaded = await upload_all(base_url, kb_id, all_files)
    token_to_info: dict[str, Uploaded] = {u.token: u for u in uploaded}

    # 5) poll until terminal or timeout
    last_items, terminal_at = await _poll_until_terminal(
        base_url=base_url,
        kb_id=kb_id,
        tokens=list(token_to_info.keys()),
        poll_interval_s=poll_interval_s,
        timeout_s=timeout_s,
    )

    # 6) compute summary and decide exit code
    summary, exit_code = _summarize(uploaded=uploaded, last_items=last_items, terminal_at=terminal_at)
    logger.info("runner.summary", extra=summary)
    return exit_code


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse CLI arguments for the smoke runner."""
    parser = argparse.ArgumentParser(description="Stateless KB smoke runner")
    parser.add_argument("--base-url", default=os.getenv("BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--fixtures", default=str(Path(__file__).resolve().parents[1] / "fixtures"))
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--poll", type=float, default=0.25, dest="poll_interval")
    return parser.parse_args(argv)

def main(argv: list[str] | None = None) -> None:
    """Entrypoint for command-line execution."""
    args = parse_args(argv or sys.argv[1:])
    code = asyncio.run(
        run_smoke(
            base_url=args.base_url,
            fixtures_dir=Path(args.fixtures),
            poll_interval_s=args.poll_interval,
            timeout_s=args.timeout,
        )
    )
    raise SystemExit(code)


if __name__ == "__main__":
    main()
