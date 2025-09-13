from __future__ import annotations

 

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status

from ..logging_conf import get_logger
from ..service import kb_service
from .models import (
    ChildStatus,
    KBCreateRequest,
    KBCreateResponse,
    MonitorChildrenResponse,
    ResourceUploadResponse,
)

router = APIRouter()
logger = get_logger("api")


@router.post(
    "/knowledge_bases",
    response_model=KBCreateResponse,
    summary="Create a knowledge base (stateless)",
)
async def create_kb(req: KBCreateRequest | None = None) -> KBCreateResponse:
    """Create and return a new knowledge base descriptor."""
    req = req or KBCreateRequest()
    out = kb_service.create_kb(name=req.name, description=req.description)
    return KBCreateResponse(**out)


@router.post(
    "/knowledge_bases/{kb_id}/resources",
    response_model=ResourceUploadResponse,
    summary="Upload a resource (stateless)",
)
async def upload_resource(
    kb_id: str,
    resource_type: str = Form(..., description='Must be "file"'),
    resource_path: str = Form(...),
    file: UploadFile = File(...),  # content ignored by design (stateless)
) -> ResourceUploadResponse:
    """Accept a file upload request and return a pending resource."""
    if resource_type.lower() != "file":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error_code": "malformed_request",
                "error_message": 'resource_type must be "file"',
            },
        )
    try:
        out = kb_service.upload_resource(kb_id=kb_id, resource_path=resource_path)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "malformed_request", "error_message": str(e)},
        )
    return ResourceUploadResponse(**out)


@router.get(
    "/knowledge_bases/{kb_id}/resources/children",
    response_model=MonitorChildrenResponse,
    summary="Monitor resource children statuses",
)
async def monitor_children(
    kb_id: str,
    ids: list[str] = Query(
        ..., description="Repeat ?ids=token. Also supports a single comma-separated string."
    ),
) -> MonitorChildrenResponse:
    """Return the current statuses for the provided resource ids."""
    # Accept either repeated ?ids=..&ids=.. or a single comma-separated string
    if len(ids) == 1 and ("," in ids[0]):
        ids = [tok.strip() for tok in ids[0].split(",") if tok.strip()]
    try:
        items = kb_service.list_children(kb_id=kb_id, ids=ids)
    except ValueError as e:
        if str(e) == "missing_ids":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "missing_ids",
                    "error_message": "At least one id must be provided",
                },
            )
        raise
    return MonitorChildrenResponse(items=[ChildStatus(**it) for it in items])


@router.delete(
    "/knowledge_bases/{kb_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a knowledge base (no-op)",
)
async def delete_kb(kb_id: str):
    """Delete a knowledge base (no-op in this stateless service)."""
    kb_service.delete_kb(kb_id=kb_id)