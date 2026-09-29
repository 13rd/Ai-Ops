from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import JSON, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base

class ServerStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"

class ConnectionType(str, Enum):
    SSH = "ssh"

class Server(Base):
    __tablename__ = "servers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    host = Column(String, nullable=False)
    port = Column(Integer, default=22, nullable=False)
    connection_type = Column(String, default=ConnectionType.SSH, nullable=False)
    environment = Column(String, nullable=True)
    tags = Column(JSON, default=list, nullable=False)
    status = Column(String, default=ServerStatus.OFFLINE, nullable=False)
    last_seen = Column(DateTime, nullable=True)

    ssh_username = Column(String, nullable=True)
    ssh_password = Column(Text, nullable=True)
    ssh_private_key = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    metrics = relationship("MetricSnapshot", back_populates="server", cascade="all, delete-orphan")
    containers = relationship(
        "ContainerSnapshot", back_populates="server", cascade="all, delete-orphan"
    )

    def get_decrypted_password(self) -> Optional[str]:
        return _decrypt_optional(self.ssh_password)

    def get_decrypted_private_key(self) -> Optional[str]:
        return _decrypt_optional(self.ssh_private_key)

def _decrypt_optional(value: Optional[str]) -> Optional[str]:
    if not value:
        return value
    from app.core.secrets import get_secrets_manager

    return get_secrets_manager().decrypt_if_encrypted(value)
