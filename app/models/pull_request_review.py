from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class PullRequestReview(Base):
    __tablename__ = "pull_request_reviews"
    id = Column(Integer, primary_key=True)
    pull_request_id = Column(Integer, ForeignKey("pull_requests.id"), nullable=False)
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewer_login = Column(String)
    state = Column(String)  # APPROVED, CHANGES_REQUESTED, COMMENTED, etc.
    submitted_at = Column(DateTime, default=datetime.utcnow)
    body = Column(Text)

    pull_request = relationship("PullRequest", back_populates="reviews")
    reviewer = relationship("User", back_populates="reviews")
