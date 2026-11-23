"""Common response envelopes and shared pagination types."""
from typing import Any, Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field

DataT = TypeVar("DataT")


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[dict[str, Any]] = None


class ResponseEnvelope(BaseModel, Generic[DataT]):
    success: bool = True
    data: DataT
    request_id: str = Field(..., description="Unique request tracing ID")


class ErrorEnvelope(BaseModel):
    success: bool = False
    error: ErrorDetail
    request_id: str = Field(..., description="Unique request tracing ID")


class PaginationMeta(BaseModel):
    total_count: int
    limit: int
    offset: int

