from typing import Any, Optional

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.schemas.common import APIResponse, ErrorDetail, PaginatedData, PaginationMeta

def ok(data: Any = None, message: Optional[str] = None) -> dict[str, Any]:

    return APIResponse(success=True, data=data, message=message).model_dump(mode="json")

def fail(
    code: str,
    message: str,
    *,
    details: Optional[dict[str, Any]] = None,
    status_code: int = 400,
) -> JSONResponse:

    body = APIResponse(
        success=False,
        data=None,
        message=message,
        error=ErrorDetail(code=code, details=details),
    ).model_dump(mode="json")
    return JSONResponse(status_code=status_code, content=jsonable_encoder(body))

def paginated(
    items: list[Any],
    *,
    limit: int,
    offset: int,
    total: Optional[int] = None,
    message: Optional[str] = None,
) -> dict[str, Any]:
    payload = PaginatedData(
        items=items,
        pagination=PaginationMeta(total=total, limit=limit, offset=offset),
    )
    return APIResponse(success=True, data=payload, message=message).model_dump(mode="json")
