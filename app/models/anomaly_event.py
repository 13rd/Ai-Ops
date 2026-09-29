from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.base import Base

class ScenarioType:
    NORMAL = "normal"
    MEMORY_LEAK = "memory_leak"
    CPU_SPIKE = "cpu_spike"
    CONTAINER_CRASH = "container_crash"
    SERVICE_DOWN = "service_down"

class AnomalyEvent(Base):
    __tablename__ = "anomaly_events"

    id = Column(Integer, primary_key=True, index=True)
    server_id = Column(
        Integer, ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scenario_type = Column(String, nullable=False, index=True)
    start_ts = Column(DateTime, nullable=False, index=True)
    end_ts = Column(DateTime, nullable=True)
    parameters = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    server = relationship("Server")
