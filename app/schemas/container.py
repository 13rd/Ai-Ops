from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ContainerSnapshotBase(BaseModel):
    container_id: str
    container_name: str
    image: Optional[str] = None
    status: Optional[str] = None
    # Extended container metrics
    cpu_percentage: Optional[float] = None
    memory_usage_mb: Optional[float] = None
    memory_percentage: Optional[float] = None
    restart_count: Optional[int] = None
    health_status: Optional[str] = None  # healthy, unhealthy, starting
    ports: Optional[str] = None  # Port mappings
    command: Optional[str] = None  # Command running in container
    created_at: Optional[str] = None  # Creation timestamp
    started_at: Optional[str] = None  # Start timestamp
    running: Optional[bool] = None  # Is the container currently running


class ContainerSnapshotResponse(ContainerSnapshotBase):
    id: int
    server_id: int
    collected_at: datetime

    class Config:
        from_attributes = True
