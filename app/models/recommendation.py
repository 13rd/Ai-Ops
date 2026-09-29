from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base

class RecommendationStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"

class Recommendation(Base):
    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, index=True)
    anomaly_id = Column(
        Integer, ForeignKey("anomalies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    llm_raw_output = Column(Text, nullable=True)
    filtered_command = Column(Text, nullable=False)
    explanation = Column(Text, nullable=False)
    status = Column(
        String, default=RecommendationStatus.PENDING.value, nullable=False, index=True
    )
    approved_by = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    executed_at = Column(DateTime, nullable=True)
    execution_result = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    anomaly = relationship("Anomaly", back_populates="recommendations")
    approver = relationship("User", foreign_keys=[approved_by])
