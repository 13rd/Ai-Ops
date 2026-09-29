from typing import Any

from app.core.responses import ok
from app.schemas.common import APIResponse, ErrorDetail, PaginatedData, PaginationMeta

__all__ = [
    "APIResponse",
    "ErrorDetail",
    "PaginatedData",
    "PaginationMeta",
    "success_response",
    "error_response",
]

def success_response(data: Any = None, message: str = "Success") -> dict:
    return ok(data=data, message=message)

def error_response(error: str, message: str = "Error occurred") -> dict:
    return APIResponse(
        success=False,
        data=None,
        message=message,
        error=ErrorDetail(code=error),
    ).model_dump(mode="json")
