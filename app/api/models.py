from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from ..domain.status import Status


class KBCreateRequest(BaseModel):
    """Optional inputs for creating a knowledge base."""
    name: Optional[str] = None
    description: Optional[str] = None


class KBCreateResponse(BaseModel):
    """Representation of a created knowledge base."""
    knowledge_base_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    created_at: int


class ResourceUploadResponse(BaseModel):
    """Response describing an accepted resource upload request."""
    resource_id: str
    resource_path: str
    status: Status
    created_at: int


class ChildStatus(BaseModel):
    """Current state of a single resource within a knowledge base."""
    resource_id: str
    resource_path: str
    status: Status
    updated_at: int
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class MonitorChildrenResponse(BaseModel):
    """Statuses for a batch of resources."""
    items: list[ChildStatus]