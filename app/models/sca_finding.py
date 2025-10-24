from sqlalchemy import Column, Integer, String, Text, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.core.database import Base
from datetime import datetime

class SCAFinding(Base):
    __tablename__ = "sca_findings"
    id = Column(Integer, primary_key=True)
    pull_request_id = Column(Integer, ForeignKey("pull_requests.id"), nullable=True)
    repo_id = Column(Integer, ForeignKey("repositories.id"))
    package = Column(String)
    version = Column(String)
    vulnerability_id = Column(String)
    severity = Column(String)
    message = Column(Text)
    recommendation = Column(Text)
    detected_at = Column(DateTime, default=datetime.utcnow)

    pull_request = relationship("PullRequest", back_populates="sca_findings")
