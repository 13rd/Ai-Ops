from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel

from app.models.recommendation import RecommendationStatus

class RecommendationResponse(BaseModel):
    id: int
    anomaly_id: int
    llm_raw_output: Optional[str] = None
    filtered_command: str
    explanation: str
    status: str
    approved_by: Optional[int] = None
    executed_at: Optional[datetime] = None
    execution_result: Optional[dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True

RECOMMENDATION_STATUSES = {s.value for s in RecommendationStatus}
