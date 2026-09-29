from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base

class LLMSettings(Base):

    __tablename__ = "llm_settings"

    id = Column(Integer, primary_key=True, default=1)
    enabled = Column(Boolean, default=True, nullable=False)
    model = Column(String, nullable=True)
    timeout_sec = Column(Integer, nullable=True)
    keep_alive = Column(String, nullable=True)
    prompt_template = Column(Text, nullable=True)
    extra = Column(JSON, default=dict, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    updated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    updater = relationship("User", foreign_keys=[updated_by])
