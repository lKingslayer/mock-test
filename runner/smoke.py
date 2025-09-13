#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from app.logging_conf import get_logger, setup_logging
from runner.cli import parse_args
from runner.client import create_kb, poll_children, upload_all, wait_for_health
from runner.types import Uploaded
from runner.utils import summarize, validate_and_collect_fixtures


setup_logging()
logger = get_logger("runner")


async def _poll_until_terminal(
    *, base_url: str, kb_id: str, tokens: list[str], poll_interval_s: float, timeout_s: float
) -> tuple[list[dict], dict[str, int]]:
    import asyncio as _asyncio
    import time as _time
    from runner.types import now_ms as _now_ms

    started = _time.monotonic()
    terminal_at: dict[str, int] = {}
    last_items: list[dict] = []
    while True:
        if _time.monotonic() - started > timeout_s:
            break
        items = await poll_children(base_url, kb_id, tokens)
        last_items = items
        now = _now_ms()
        for it in items:
            status = it.get("status")
            rid = it["resource_id"]
            if status in ("indexed", "error") and rid not in terminal_at:
                terminal_at[rid] = int(it.get("updated_at", now))
        if len(terminal_at) == len(tokens):
            break
        await _asyncio.sleep(poll_interval_s)
    return last_items, terminal_at


async def run_smoke(
    *, base_url: str, fixtures_dir: Path, poll_interval_s: float = 0.25, timeout_s: float = 30.0
) -> int:
    await wait_for_health(base_url)
    all_files = validate_and_collect_fixtures(fixtures_dir)
    kb_id = await create_kb(base_url)
    uploaded = await upload_all(base_url, kb_id, all_files)
    token_to_info: dict[str, Uploaded] = {u.token: u for u in uploaded}
    last_items, terminal_at = await _poll_until_terminal(
        base_url=base_url,
        kb_id=kb_id,
        tokens=list(token_to_info.keys()),
        poll_interval_s=poll_interval_s,
        timeout_s=timeout_s,
    )
    summary, exit_code = summarize(
        uploaded=uploaded, last_items=last_items, terminal_at=terminal_at
    )
    logger.info("runner.summary", extra=summary)
    return exit_code


def main(argv: list[str] | None = None) -> None:
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
