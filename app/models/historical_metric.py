from datetime import datetime
from enum import Enum

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.base import Base

class MetricType(str, Enum):
    CPU_PERCENT = "cpu_percent"
    MEMORY_PERCENT = "memory_percent"
    DISK_PERCENT = "disk_percent"
    LOAD_AVERAGE_1M = "load_average_1m"
    LOAD_AVERAGE_5M = "load_average_5m"
    LOAD_AVERAGE_15M = "load_average_15m"
    NETWORK_IN = "network_in"
    NETWORK_OUT = "network_out"
    DISK_READ = "disk_read"
    DISK_WRITE = "disk_write"

class AggregationType(str, Enum):
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"

class HistoricalMetric(Base):

    __tablename__ = "historical_metrics"

    id = Column(Integer, primary_key=True, index=True)
    server_id = Column(
        Integer, ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    metric_type = Column(String, nullable=False, index=True)
    aggregation_level = Column(String, default=AggregationType.MINUTE, nullable=False, index=True)

    timestamp = Column(DateTime, nullable=False, index=True)
    period_start = Column(DateTime, nullable=False, index=True)

    value_min = Column(Float, nullable=True)
    value_max = Column(Float, nullable=True)
    value_avg = Column(Float, nullable=True)
    value_last = Column(Float, nullable=True)
    sample_count = Column(Integer, default=1, nullable=False)

    collected_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    server = relationship("Server")

    def __repr__(self):
        return f"<HistoricalMetric(server_id={self.server_id}, metric_type='{self.metric_type}', timestamp='{self.timestamp}', value_avg={self.value_avg})>"
