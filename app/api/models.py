from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel

from ..domain.status import Status


class KBCreateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class KBCreateResponse(BaseModel):
    knowledge_base_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    created_at: int


class ResourceUploadResponse(BaseModel):
    resource_id: str
    resource_path: str
    status: Status
    created_at: int


class ChildStatus(BaseModel):
    resource_id: str
    resource_path: str
    status: Status
    updated_at: int
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class MonitorChildrenResponse(BaseModel):
    items: List[ChildStatus]