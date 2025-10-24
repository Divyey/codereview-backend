from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.core.database import Base

class Branch(Base):
    __tablename__ = "branches"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"))
    last_commit_sha = Column(String)
    last_pushed_at = Column(DateTime)

    repository = relationship("Repository", back_populates="branches")
    commits = relationship("Commit", back_populates="branch")
