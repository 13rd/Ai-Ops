from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.base import Base

class AnomalyType(str, Enum):
    MEMORY_LEAK = "memory_leak"
    CPU_SPIKE = "cpu_spike"
    CONTAINER_CRASH = "container_crash"
    SERVICE_DOWN = "service_down"
    DISK_PRESSURE = "disk_pressure"
    NETWORK_ANOMALY = "network_anomaly"
    DISK_FILL = "disk_fill"
    NETWORK_STORM = "network_storm"

class AnomalySeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class AnomalyStatus(str, Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"

class Anomaly(Base):
    __tablename__ = "anomalies"

    id = Column(Integer, primary_key=True, index=True)
    server_id = Column(
        Integer, ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    detected_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    anomaly_type = Column(String, nullable=False, index=True)
    severity = Column(String, default=AnomalySeverity.MEDIUM.value, nullable=False, index=True)

    reconstruction_error = Column(Float, nullable=False, default=0.0)
    threshold = Column(Float, nullable=False, default=0.0)

    shap_explanation = Column(JSON, nullable=False, default=dict)
    metrics_snapshot = Column(JSON, nullable=False, default=dict)

    status = Column(String, default=AnomalyStatus.OPEN.value, nullable=False, index=True)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    server = relationship("Server")
    resolver = relationship("User", foreign_keys=[resolved_by])
    recommendations = relationship(
        "Recommendation", back_populates="anomaly", cascade="all, delete-orphan"
    )
