from datetime import datetime
from typing import Any, Optional, Union

from pydantic import BaseModel, field_validator

from app.models.anomaly import AnomalySeverity, AnomalyStatus, AnomalyType


class AnomalyResponse(BaseModel):
    id: int
    server_id: int
    detected_at: datetime
    anomaly_type: str
    severity: str
    reconstruction_error: float
    threshold: float
    # Legacy rule-based pipeline wrote {feature: weight}; the AE+classifier
    # pipeline writes a ranked list of {metric, impact_percent, ...} dicts.
    shap_explanation: Union[dict[str, Any], list[dict[str, Any]]] = {}
    metrics_snapshot: dict[str, Any] = {}
    status: str
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[int] = None

    class Config:
        from_attributes = True


class AnomalyStatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        allowed = {s.value for s in AnomalyStatus}
        if value not in allowed:
            raise ValueError(f"status must be one of {sorted(allowed)}")
        return value


# Re-export enum values for endpoint param validation.
ANOMALY_TYPES = {t.value for t in AnomalyType}
ANOMALY_SEVERITIES = {s.value for s in AnomalySeverity}
ANOMALY_STATUSES = {s.value for s in AnomalyStatus}
