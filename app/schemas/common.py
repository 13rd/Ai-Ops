from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")

class ErrorDetail(BaseModel):
    code: str = Field(..., description="Machine-readable error code")
    details: Optional[dict[str, Any]] = Field(
        default=None, description="Optional structured error context"
    )

class APIResponse(BaseModel, Generic[T]):

    success: bool
    data: Optional[T] = None
    message: Optional[str] = None
    error: Optional[ErrorDetail] = None

class PaginationMeta(BaseModel):
    total: Optional[int] = None
    limit: int
    offset: int

class PaginatedData(BaseModel, Generic[T]):
    items: list[T]
    pagination: PaginationMeta

PaginatedResponse = APIResponse[PaginatedData[T]]
