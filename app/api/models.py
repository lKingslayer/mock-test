from __future__ import annotations

from pydantic import BaseModel

from app.domain.status import Status


class KBCreateRequest(BaseModel):
    """Optional inputs for creating a knowledge base."""
    name: str | None = None
    description: str | None = None


class KBCreateResponse(BaseModel):
    """Representation of a created knowledge base."""
    knowledge_base_id: str
    name: str | None = None
    description: str | None = None
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
    error_code: str | None = None
    error_message: str | None = None


class MonitorChildrenResponse(BaseModel):
    """Statuses for a batch of resources."""
    items: list[ChildStatus]