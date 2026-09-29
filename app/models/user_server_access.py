from datetime import datetime
from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.base import Base

class ServerPermission(str, Enum):
    READ = "read"
    WRITE = "write"

class UserServerAccess(Base):
    __tablename__ = "user_server_access"

    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    server_id = Column(
        Integer, ForeignKey("servers.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    permission = Column(String, default=ServerPermission.READ.value, nullable=False)
    granted_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", backref="server_access")
    server = relationship("Server")
