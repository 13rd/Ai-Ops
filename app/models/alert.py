from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base


class AlertStatus(str, Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"  # Added resolved status to indicate when alert is fixed


class AlertSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertRuleType(str, Enum):
    CPU_THRESHOLD = "cpu_threshold"
    MEMORY_THRESHOLD = "memory_threshold"
    DISK_THRESHOLD = "disk_threshold"
    SERVER_OFFLINE = "server_offline"
    CONTAINER_DOWN = "container_down"
    CONTAINER_UNHEALTHY = "container_unhealthy"


class Alert(Base):
    """
    Alert records for system monitoring.
    """

    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, default=AlertStatus.OPEN, nullable=False, index=True)
    severity = Column(String, default=AlertSeverity.MEDIUM, nullable=False, index=True)
    rule_type = Column(String, nullable=False, index=True)  # Type of rule that triggered

    # Source entity references
    server_id = Column(
        Integer, ForeignKey("servers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    container_id = Column(
        String, nullable=True, index=True
    )  # Container ID for container-related alerts
    metric_type = Column(String, nullable=True)  # Metric type for metric-based alerts

    # Rule condition values
    threshold_value = Column(String, nullable=True)  # Threshold that was exceeded
    current_value = Column(String, nullable=True)  # Current value that triggered the alert

    # State tracking
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_by_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at = Column(DateTime, nullable=True)
    first_triggered_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_triggered_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Additional context
    additional_metadata = Column(JSON, default=dict, nullable=False)  # Additional context data

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    server = relationship("Server")
    acknowledged_by = relationship("User")


class AlertRule(Base):
    """
    Alert rules configuration for automatic alert generation.
    """

    __tablename__ = "alert_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)  # Human-readable rule name
    description = Column(Text, nullable=True)
    rule_type = Column(String, nullable=False, index=True)  # Type of alert rule
    is_enabled = Column(Boolean, default=True, nullable=False)  # Whether the rule is active
    severity = Column(String, default=AlertSeverity.MEDIUM, nullable=False)  # Default severity

    # Configuration values as JSON for flexibility
    config = Column(JSON, default=dict, nullable=False)  # Rule-specific configuration

    # Scope limitations
    server_ids = Column(
        JSON, default=list, nullable=False
    )  # Servers this rule applies to (empty = all)
    tags = Column(JSON, default=list, nullable=False)  # Tags this rule applies to (empty = all)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return (
            f"<AlertRule(name='{self.name}', type='{self.rule_type}', enabled={self.is_enabled})>"
        )
