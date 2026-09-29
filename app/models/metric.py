from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer
from sqlalchemy.orm import relationship

from app.db.base import Base

class MetricSnapshot(Base):

    __tablename__ = "metric_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    server_id = Column(
        Integer, ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, index=True
    )

    cpu_usage_percent = Column(Float, nullable=True)
    load_average_1m = Column(Float, nullable=True)
    load_average_5m = Column(Float, nullable=True)
    load_average_15m = Column(Float, nullable=True)

    memory_total_mb = Column(Float, nullable=True)
    memory_used_mb = Column(Float, nullable=True)
    memory_free_mb = Column(Float, nullable=True)
    memory_usage_percent = Column(Float, nullable=True)

    disk_total_gb = Column(Float, nullable=True)
    disk_used_gb = Column(Float, nullable=True)
    disk_free_gb = Column(Float, nullable=True)
    disk_usage_percent = Column(Float, nullable=True)

    network_in_bytes = Column(Float, nullable=True)
    network_out_bytes = Column(Float, nullable=True)

    uptime_seconds = Column(Integer, nullable=True)

    disk_read_bytes = Column(Float, nullable=True)
    disk_write_bytes = Column(Float, nullable=True)
    process_count = Column(Integer, nullable=True)
    active_connections = Column(Integer, nullable=True)

    extra_data = Column(JSON, default=dict, nullable=False)

    collected_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    server = relationship("Server", back_populates="metrics")
