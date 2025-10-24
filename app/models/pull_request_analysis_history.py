from sqlalchemy import Column, Integer, String, DateTime, Float, JSON, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base
from sqlalchemy.dialects.postgresql import JSONB

class PullRequestAnalysisHistory(Base):
    __tablename__ = "pull_request_analysis_history"
    id = Column(Integer, primary_key=True)
    pull_request_id = Column(Integer, ForeignKey("pull_requests.id"), nullable=False)
    commit_sha = Column(String)
    analyzed_at = Column(DateTime, default=datetime.utcnow)
    ai_score = Column(Float)
    risk_level = Column(String)
    issues = Column(JSON)
    warnings = Column(JSON)
    recommendations = Column(JSON)
    summary = Column(Text)
    reviewer = Column(String)
    recommendations = Column(JSONB, nullable=False, default=list)
    
    pull_request = relationship("PullRequest", back_populates="analysis_history")
