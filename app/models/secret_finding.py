from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class SecretFinding(Base):
    __tablename__ = "secret_findings"
    id = Column(Integer, primary_key=True)
    pull_request_id = Column(Integer, ForeignKey("pull_requests.id"), nullable=True)
    repo_id = Column(Integer, ForeignKey("repositories.id"))
    file_id = Column(Integer, ForeignKey("pr_files.id"), nullable=True)
    line = Column(Integer)
    secret_type = Column(String)  # e.g., "AWS Key", "Token"
    severity = Column(String)
    message = Column(Text)
    detected_at = Column(DateTime, default=datetime.utcnow)

    pull_request = relationship("PullRequest", back_populates="secret_findings")
    file = relationship("PRFile", back_populates="secret_findings")
