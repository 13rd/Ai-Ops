from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base

class AuditAction(str, Enum):

    LOGIN = "login"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    TOKEN_REFRESHED = "token_refreshed"
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DEACTIVATED = "user_deactivated"
    SERVER_ACCESS_ASSIGNED = "server_access_assigned"
    SERVER_CREATED = "server_created"
    SERVER_UPDATED = "server_updated"
    SERVER_DELETED = "server_deleted"
    CONSOLE_OPENED = "console_opened"
    CONSOLE_COMMAND = "console_command"
    CONSOLE_CLOSED = "console_closed"
    CONTAINER_ACTION = "container_action"
    RECOMMENDATION_APPROVED = "recommendation_approved"
    RECOMMENDATION_REJECTED = "recommendation_rejected"
    ANOMALY_STATUS_CHANGED = "anomaly_status_changed"
    LLM_SETTINGS_UPDATED = "llm_settings_updated"

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action = Column(String, nullable=False, index=True)
    resource_type = Column(String, nullable=True, index=True)
    resource_id = Column(String, nullable=True)
    details = Column(JSON, nullable=False, default=dict)
    ip_address = Column(String, nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    user = relationship("User")
