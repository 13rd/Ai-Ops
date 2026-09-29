from datetime import datetime
from typing import Optional

from pydantic import BaseModel

class ContainerSnapshotBase(BaseModel):
    container_id: str
    container_name: str
    image: Optional[str] = None
    status: Optional[str] = None
    cpu_percentage: Optional[float] = None
    memory_usage_mb: Optional[float] = None
    memory_percentage: Optional[float] = None
    restart_count: Optional[int] = None
    health_status: Optional[str] = None
    ports: Optional[str] = None
    command: Optional[str] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    running: Optional[bool] = None

class ContainerSnapshotResponse(ContainerSnapshotBase):
    id: int
    server_id: int
    collected_at: datetime
    extra_data: dict = {}

    class Config:
        from_attributes = True
