from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base


class ConsoleSessionStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    TERMINATED = "terminated"


class ConsoleSession(Base):
    """
    Model to represent a console session between a user and a server.
    """

    __tablename__ = "console_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_token = Column(
        String, unique=True, nullable=False, index=True
    )  # Unique identifier for the session
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    server_id = Column(
        Integer, ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status = Column(String, default=ConsoleSessionStatus.ACTIVE, nullable=False, index=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)  # Session duration in seconds

    # Connection info
    client_ip = Column(String, nullable=True)  # IP of the connecting client
    terminated_by_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )  # Who terminated the session
    termination_reason = Column(String, nullable=True)  # Reason for termination

    # Additional metadata
    session_metadata = Column(String, default="{}", nullable=False)  # JSON metadata as string

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    server = relationship("Server")
    terminated_by_user = relationship("User", foreign_keys=[terminated_by_user_id])

    def __repr__(self):
        return f"<ConsoleSession(id={self.id}, token={self.session_token}, status={self.status})>"
