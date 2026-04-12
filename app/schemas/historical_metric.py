from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from app.models.historical_metric import AggregationType, MetricType


class HistoricalMetricResponse(BaseModel):
    id: int
    server_id: int
    metric_type: str  # Using str instead of MetricType for easier serialization
    aggregation_level: str  # Using str instead of AggregationType for easier serialization
    timestamp: datetime
    period_start: datetime
    value_min: Optional[float] = None
    value_max: Optional[float] = None
    value_avg: Optional[float] = None
    value_last: Optional[float] = None
    sample_count: int
    collected_at: datetime

    class Config:
        from_attributes = True


class HistoricalMetricsRequest(BaseModel):
    time_range: str  # Using str for validation of specific values
    aggregation_level: Optional[str] = "minute"  # minute, hour, day


class HistoricalMetricsResponse(BaseModel):
    server_id: int
    metric_type: str
    time_range: str
    aggregation_level: str
    metrics: List[HistoricalMetricResponse]


class MetricsAggregationLevelResponse(BaseModel):
    available_levels: List[str]
