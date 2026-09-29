from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, field_validator

from app.models.notification import NotificationChannelType

_ALLOWED_CHANNELS = {c.value for c in NotificationChannelType}

class NotificationResponse(BaseModel):
    id: int
    user_id: int
    anomaly_id: Optional[int] = None
    title: str
    body: str
    severity: str
    is_read: bool
    read_at: Optional[datetime] = None
    sent_at: datetime
    channels_sent: list[str] = []

    class Config:
        from_attributes = True

class NotificationChannelCreate(BaseModel):
    channel_type: str
    config: dict[str, Any] = {}
    enabled: bool = True

    @field_validator("channel_type")
    @classmethod
    def validate_channel_type(cls, value: str) -> str:
        if value not in _ALLOWED_CHANNELS:
            raise ValueError(f"channel_type must be one of {sorted(_ALLOWED_CHANNELS)}")
        return value

class NotificationChannelUpdate(BaseModel):
    config: Optional[dict[str, Any]] = None
    enabled: Optional[bool] = None

class NotificationChannelResponse(BaseModel):
    id: int
    user_id: int
    channel_type: str
    config: dict[str, Any] = {}
    enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
