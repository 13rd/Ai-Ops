from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel

class LLMSettingsResponse(BaseModel):
    id: int
    enabled: bool
    model: Optional[str] = None
    timeout_sec: Optional[int] = None
    keep_alive: Optional[str] = None
    prompt_template: Optional[str] = None
    extra: dict[str, Any] = {}
    updated_at: datetime
    updated_by: Optional[int] = None

    class Config:
        from_attributes = True

class LLMSettingsUpdate(BaseModel):
    enabled: Optional[bool] = None
    model: Optional[str] = None
    timeout_sec: Optional[int] = None
    keep_alive: Optional[str] = None
    prompt_template: Optional[str] = None
    extra: Optional[dict[str, Any]] = None
