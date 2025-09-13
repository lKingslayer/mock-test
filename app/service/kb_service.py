from __future__ import annotations

import os
import time
from uuid import uuid4

from ..logging_conf import get_logger
from ..domain.paths import normalize_resource_path
from ..domain.tokens import (
    TokenError,
    decode_resource_token,
    encode_resource_token,
    get_seed_from_env,
)
from ..domain.status import Status, compute_status

logger = get_logger("service.kb")


def now_ms() -> int:
    """Return current time in epoch milliseconds."""
    return int(time.time() * 1000)


def get_failure_rate_from_env() -> float:
    """Return FAILURE_RATE from environment, defaulting to 0.3."""
    raw = os.getenv("FAILURE_RATE", "0.3")
    try:
        val = float(raw)
    except ValueError as e:  # pragma: no cover
        raise ValueError("FAILURE_RATE must be a float") from e
    if not (0.0 <= val <= 1.0):
        raise ValueError("FAILURE_RATE must be in [0,1]")
    return val


# ------------------------
# Use-cases
# ------------------------

def create_kb(*, name: str | None = None, description: str | None = None) -> dict:
    """Create a new knowledge base descriptor."""
    kb_id = str(uuid4())
    created_at = now_ms()
    logger.info("kb.create", extra={"event": "kb_create", "kb_id": kb_id})
    return {
        "knowledge_base_id": kb_id,
        "name": name,
        "description": description,
        "created_at": created_at,
    }


def upload_resource(*, kb_id: str, resource_path: str) -> dict:
    """Accept a resource path and return an initial pending resource."""
    created_at = now_ms()
    seed = get_seed_from_env()
    rp = normalize_resource_path(resource_path)
    token = encode_resource_token(
        kb_id=kb_id,
        resource_path=rp,
        created_at_ms=created_at,
        seed=seed,
    )
    logger.info(
        "resource.upload",
        extra={"event": "resource_upload", "kb_id": kb_id, "resource_path": rp},
    )
    return {
        "resource_id": token,
        "resource_path": rp,
        "status": Status.pending,
        "created_at": created_at,
    }


def list_children(*, kb_id: str, ids: list[str]) -> list[dict]:
    """Return statuses for the provided resource ids within a KB."""
    if not ids:
        raise ValueError("missing_ids")

    failure_rate = get_failure_rate_from_env()
    now = now_ms()
    out: list[dict] = []

    for tok in ids:
        try:
            payload = decode_resource_token(tok)
        except TokenError as e:
            out.append(
                {
                    "resource_id": tok,
                    "resource_path": "",
                    "status": Status.error,
                    "updated_at": now,
                    "error_code": e.code,
                    "error_message": str(e),
                }
            )
            continue

        if payload.kb_id != kb_id:
            out.append(
                {
                    "resource_id": tok,
                    "resource_path": payload.rp,
                    "status": Status.error,
                    "updated_at": now,
                    "error_code": "kb_mismatch",
                    "error_message": "Token belongs to a different knowledge base",
                }
            )
            continue

        status = compute_status(
            created_at_ms=payload.ca_ms,
            now_ms=now,
            salt=payload.salt,
            failure_rate=failure_rate,
        )
        out.append(
            {
                "resource_id": tok,
                "resource_path": payload.rp,
                "status": status,
                "updated_at": now,
            }
        )

    logger.info(
        "children.list",
        extra={"event": "children_list", "kb_id": kb_id, "count": len(ids)},
    )
    return out


def delete_kb(*, kb_id: str) -> None:
    """Record a delete request for a knowledge base (no-op)."""
    logger.info("kb.delete", extra={"event": "kb_delete", "kb_id": kb_id})
    return None