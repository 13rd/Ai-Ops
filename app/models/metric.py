from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON
from sqlalchemy.orm import relationship

from app.db.base import Base


class MetricSnapshot(Base):
    """
    Stores system metrics snapshots.
    TODO: Consider time-series optimization for Sprint 2+
    """

    __tablename__ = "metric_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    server_id = Column(
        Integer, ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # CPU metrics
    cpu_usage_percent = Column(Float, nullable=True)
    load_average_1m = Column(Float, nullable=True)
    load_average_5m = Column(Float, nullable=True)
    load_average_15m = Column(Float, nullable=True)

    # Memory metrics
    memory_total_mb = Column(Float, nullable=True)
    memory_used_mb = Column(Float, nullable=True)
    memory_free_mb = Column(Float, nullable=True)
    memory_usage_percent = Column(Float, nullable=True)

    # Disk metrics
    disk_total_gb = Column(Float, nullable=True)
    disk_used_gb = Column(Float, nullable=True)
    disk_free_gb = Column(Float, nullable=True)
    disk_usage_percent = Column(Float, nullable=True)

    # Network metrics (bytes)
    network_in_bytes = Column(Float, nullable=True)
    network_out_bytes = Column(Float, nullable=True)

    # System uptime
    uptime_seconds = Column(Integer, nullable=True)

    # Extended metrics
    disk_read_bytes = Column(Float, nullable=True)  # Disk read bytes
    disk_write_bytes = Column(Float, nullable=True)  # Disk write bytes
    process_count = Column(Integer, nullable=True)  # Total process count
    active_connections = Column(Integer, nullable=True)  # Active network connections

    # Additional data for flexibility
    extra_data = Column(JSON, default=dict, nullable=False)

    collected_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    server = relationship("Server", back_populates="metrics")
