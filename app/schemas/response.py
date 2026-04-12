from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    success: bool
    data: Optional[T] = None
    message: Optional[str] = None
    error: Optional[str] = None


def success_response(data: Any = None, message: str = "Success") -> dict:
    return {"success": True, "data": data, "message": message}


def error_response(error: str, message: str = "Error occurred") -> dict:
    return {"success": False, "error": error, "message": message}
