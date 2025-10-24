from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class PRFile(Base):
    __tablename__ = "pr_files"
    id = Column(Integer, primary_key=True)
    pull_request_id = Column(Integer, ForeignKey("pull_requests.id"), nullable=False)
    filename = Column(String, nullable=False)
    status = Column(String)
    additions = Column(Integer, default=0)
    deletions = Column(Integer, default=0)
    patch = Column(Text)
    content = Column(Text)
    old_content = Column(Text)
    language = Column(String)

    pull_request = relationship("PullRequest", back_populates="files")
    code_quality_issues = relationship("CodeQualityIssue", back_populates="file", cascade="all, delete-orphan")
    security_findings = relationship("SecurityFinding", back_populates="file", cascade="all, delete-orphan")
    secret_findings = relationship("SecretFinding", back_populates="file", cascade="all, delete-orphan")
    infra_findings = relationship("InfraFinding", back_populates="file", cascade="all, delete-orphan")
