from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base

class NotificationChannelType(str, Enum):
    INAPP = "inapp"
    TELEGRAM = "telegram"

class NotificationChannel(Base):
    __tablename__ = "notification_channels"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel_type = Column(String, nullable=False, index=True)
    config = Column(JSON, nullable=False, default=dict)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", backref="notification_channels")

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    anomaly_id = Column(
        Integer, ForeignKey("anomalies.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    severity = Column(String, nullable=False, default="medium")
    is_read = Column(Boolean, default=False, nullable=False, index=True)
    read_at = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    channels_sent = Column(JSON, nullable=False, default=list)

    user = relationship("User", backref="notifications")
    anomaly = relationship("Anomaly")
