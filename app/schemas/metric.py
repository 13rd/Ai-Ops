from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class MetricSnapshotBase(BaseModel):
    cpu_usage_percent: Optional[float] = None
    load_average_1m: Optional[float] = None
    load_average_5m: Optional[float] = None
    load_average_15m: Optional[float] = None
    memory_total_mb: Optional[float] = None
    memory_used_mb: Optional[float] = None
    memory_free_mb: Optional[float] = None
    memory_usage_percent: Optional[float] = None
    disk_total_gb: Optional[float] = None
    disk_used_gb: Optional[float] = None
    disk_free_gb: Optional[float] = None
    disk_usage_percent: Optional[float] = None
    network_in_bytes: Optional[float] = None
    network_out_bytes: Optional[float] = None
    uptime_seconds: Optional[int] = None


class MetricSnapshotResponse(MetricSnapshotBase):
    id: int
    server_id: int
    collected_at: datetime

    class Config:
        from_attributes = True
