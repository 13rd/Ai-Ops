from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from app.models.alert import AlertRuleType, AlertSeverity, AlertStatus


class AlertResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    status: str  # AlertStatus as string
    severity: str  # AlertSeverity as string
    rule_type: str  # AlertRuleType as string
    server_id: Optional[int] = None
    container_id: Optional[str] = None
    metric_type: Optional[str] = None
    threshold_value: Optional[str] = None
    current_value: Optional[str] = None
    metadata: dict = {}
    acknowledged_at: Optional[datetime] = None
    acknowledged_by_user_id: Optional[int] = None
    resolved_at: Optional[datetime] = None
    first_triggered_at: datetime
    last_triggered_at: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CreateAlertRequest(BaseModel):
    title: str
    description: str
    severity: AlertSeverity
    rule_type: AlertRuleType
    server_id: Optional[int] = None
    container_id: Optional[str] = None
    metric_type: Optional[str] = None
    threshold_value: Optional[str] = None
    current_value: Optional[str] = None
    metadata: Optional[dict] = None


class AcknowledgeAlertRequest(BaseModel):
    user_id: int


class AlertFilterRequest(BaseModel):
    status: Optional[AlertStatus] = None
    severity: Optional[AlertSeverity] = None
    server_id: Optional[int] = None
    limit: int = 100
    offset: int = 0


class AlertCountResponse(BaseModel):
    count: int
    status: Optional[str] = None
    severity: Optional[str] = None
    server_id: Optional[int] = None
