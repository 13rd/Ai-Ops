from datetime import datetime
from enum import Enum

from sqlalchemy import Column, DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base


class ServerStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"


class ConnectionType(str, Enum):
    SSH = "ssh"
    # TODO: Add other connection types when needed (agent, api, etc.)


class Server(Base):
    __tablename__ = "servers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    host = Column(String, nullable=False)
    port = Column(Integer, default=22, nullable=False)
    connection_type = Column(String, default=ConnectionType.SSH, nullable=False)
    environment = Column(String, nullable=True)  # dev, staging, prod
    tags = Column(JSON, default=list, nullable=False)  # ["web", "database", etc.]
    status = Column(String, default=ServerStatus.OFFLINE, nullable=False)
    last_seen = Column(DateTime, nullable=True)

    # Connection credentials - TODO: Move to vault in production
    ssh_username = Column(String, nullable=True)
    ssh_password = Column(Text, nullable=True)  # Encrypted
    ssh_private_key = Column(Text, nullable=True)  # Encrypted

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    metrics = relationship("MetricSnapshot", back_populates="server", cascade="all, delete-orphan")
    containers = relationship(
        "ContainerSnapshot", back_populates="server", cascade="all, delete-orphan"
    )
