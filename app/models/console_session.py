from datetime import datetime
from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.base import Base

class ConsoleSessionStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    TERMINATED = "terminated"

class ConsoleSession(Base):

    __tablename__ = "console_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_token = Column(
        String, unique=True, nullable=False, index=True
    )
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    server_id = Column(
        Integer, ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status = Column(String, default=ConsoleSessionStatus.ACTIVE, nullable=False, index=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    client_ip = Column(String, nullable=True)
    terminated_by_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    termination_reason = Column(String, nullable=True)

    session_metadata = Column(String, default="{}", nullable=False)

    user = relationship("User", foreign_keys=[user_id])
    server = relationship("Server")
    terminated_by_user = relationship("User", foreign_keys=[terminated_by_user_id])

    def __repr__(self):
        return f"<ConsoleSession(id={self.id}, token={self.session_token}, status={self.status})>"
