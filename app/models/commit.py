from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from app.core.database import Base

class Commit(Base):
    __tablename__ = "commits"

    id = Column(Integer, primary_key=True, index=True)
    sha = Column(String, unique=True, index=True)
    message = Column(Text)
    author_name = Column(String)
    author_email = Column(String)
    timestamp = Column(DateTime)
    branch_id = Column(Integer, ForeignKey("branches.id"))
    repository_id = Column(Integer, ForeignKey("repositories.id"))

    branch = relationship("Branch", back_populates="commits")
    repository = relationship("Repository", back_populates="commits")
