from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class Repository(Base):
    __tablename__ = "repositories"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    full_name = Column(String, unique=True, nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    default_branch = Column(String)
    is_private = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    branches = relationship("Branch", back_populates="repository")
    commits = relationship("Commit", back_populates="repository")
    description = Column(String, nullable=True)
    github_id = Column(Integer, unique=True, nullable=False)
    url = Column(String, nullable=False)  
    owner = relationship("User", back_populates="repositories")
    pull_requests = relationship("PullRequest", back_populates="repository")
