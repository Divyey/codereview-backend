from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
from ..core.database import Base

class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String, index=True)
    delivery_id = Column(String, unique=True, index=True)
    signature = Column(String, nullable=True)
    payload = Column(JSONB)
    analysis = Column(JSONB, nullable=True)
    processed = Column(Boolean, default=False)
    status = Column(String, default="received")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    received_at = Column(DateTime, default=datetime.utcnow) 
    # repository_id = Column(Integer, ForeignKey("repositories.id"), nullable=True)  # future