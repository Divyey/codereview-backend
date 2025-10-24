from sqlalchemy import Column, Integer, Text, DateTime, Boolean, String, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base
from pydantic import BaseModel

class PRComment(Base):
    __tablename__ = "pr_comments"
    id = Column(Integer, primary_key=True)
    pull_request_id = Column(Integer, ForeignKey("pull_requests.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    body = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    ai_generated = Column(Boolean, default=False)
    type = Column(String)  # question, answer, comment

    pull_request = relationship("PullRequest", back_populates="comments")
    user = relationship("User", back_populates="comments")

class PRCommentRead(BaseModel):
    id: int
    pull_request_id: int
    user_id: int
    body: str
    created_at: datetime
    ai_generated: bool
    type: str

    class Config:
        from_attributes = True

class PRCommentCreate(BaseModel):
    pull_request_id: int
    user_id: int
    body: str
    ai_generated: bool = False
    type: str = "comment"
