from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ContainerSnapshotBase(BaseModel):
    container_id: str
    container_name: str
    image: Optional[str] = None
    status: Optional[str] = None


class ContainerSnapshotResponse(ContainerSnapshotBase):
    id: int
    server_id: int
    collected_at: datetime

    class Config:
        from_attributes = True
