from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Text, Float, JSON, BigInteger
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..core.database import Base
from pydantic import BaseModel
from typing import Optional

class PullRequest(Base):
    __tablename__ = "pull_requests"

    id = Column(Integer, primary_key=True, index=True)
    number = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    branch = Column(String, nullable=False)
    base_branch = Column(String, nullable=True)
    status = Column(String, default="open")
    github_id = Column(BigInteger, nullable=True)
    github_url = Column(String, nullable=True)
    github_created_at = Column(DateTime(timezone=True), nullable=True)
    github_updated_at = Column(DateTime(timezone=True), nullable=True)
    github_closed_at = Column(DateTime(timezone=True), nullable=True)
    github_merged_at = Column(DateTime(timezone=True), nullable=True)
    github_author = Column(String, nullable=True)
    merge_commit_sha = Column(String, nullable=True)
    additions = Column(Integer, default=0)
    deletions = Column(Integer, default=0)
    changed_files = Column(Integer, default=0)
    review_comments = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    labels = Column(JSON, nullable=True)
    milestone = Column(String, nullable=True)
    commits = Column(Integer, default=0)
    pr_type = Column(String, nullable=True)

    ai_score = Column(Float, nullable=True)
    risk_level = Column(String, nullable=True)
    issue_count = Column(Integer, default=0)
    warning_count = Column(Integer, default=0)
    files_changed = Column(Integer, default=0)
    lines_added = Column(Integer, default=0)
    lines_deleted = Column(Integer, default=0)
    ai_review_started_at = Column(DateTime(timezone=True), nullable=True)
    ai_review_completed_at = Column(DateTime(timezone=True), nullable=True)
    ai_review_time_seconds = Column(Float, nullable=True)
    user_review_time_minutes = Column(Float, nullable=True)
    ai_analysis = Column(JSON, nullable=True)
    review_status = Column(String, default="AI only")
    reviewers = Column(JSON, server_default="[]")

    repository_id = Column(Integer, ForeignKey("repositories.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships (no duplicates)
    repository = relationship("Repository", back_populates="pull_requests")
    author = relationship("User", back_populates="pull_requests")
    files = relationship("PRFile", back_populates="pull_request", cascade="all, delete-orphan")
    analysis_history = relationship("PullRequestAnalysisHistory", back_populates="pull_request", cascade="all, delete-orphan")
    reviews = relationship("PullRequestReview", back_populates="pull_request", cascade="all, delete-orphan")
    comments = relationship("PRComment", back_populates="pull_request", cascade="all, delete-orphan")
    code_quality_issues = relationship("CodeQualityIssue", back_populates="pull_request", cascade="all, delete-orphan")
    sca_findings = relationship("SCAFinding", back_populates="pull_request", cascade="all, delete-orphan")
    secret_findings = relationship("SecretFinding", back_populates="pull_request", cascade="all, delete-orphan")
    infra_findings = relationship("InfraFinding", back_populates="pull_request", cascade="all, delete-orphan")
    security_findings = relationship("SecurityFinding", back_populates="pull_request", cascade="all, delete-orphan")

    @property
    def lifetime_seconds(self):
        end = self.github_merged_at or self.github_closed_at
        if self.github_created_at and end:
            return (end - self.github_created_at).total_seconds()
        return None
