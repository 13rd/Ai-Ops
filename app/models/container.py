from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import relationship

from app.db.base import Base


class ContainerSnapshot(Base):
    """
    Stores container information snapshots.
    """

    __tablename__ = "container_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    server_id = Column(
        Integer, ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, index=True
    )

    container_id = Column(String, nullable=False)
    container_name = Column(String, nullable=False)
    image = Column(String, nullable=True)
    status = Column(String, nullable=True)  # running, stopped, etc.

    # Additional container data
    extra_data = Column(JSON, default=dict, nullable=False)

    collected_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    server = relationship("Server", back_populates="containers")
