from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime
from .pr_file import PRFileRead
from .pull_request_analysis_history import PullRequestAnalysisHistoryRead
from .pull_request_review import PullRequestReviewRead

class PullRequestBase(BaseModel):
    number: int
    title: str
    description: Optional[str] = None
    branch: str
    base_branch: Optional[str] = None
    status: Optional[str] = "open"
    github_id: Optional[int] = None
    github_url: Optional[str] = None
    github_created_at: Optional[datetime] = None
    github_updated_at: Optional[datetime] = None
    github_closed_at: Optional[datetime] = None
    github_merged_at: Optional[datetime] = None
    github_author: Optional[str] = None
    merge_commit_sha: Optional[str] = None
    additions: Optional[int] = 0
    deletions: Optional[int] = 0
    changed_files: Optional[int] = 0
    review_comments: Optional[int] = 0
    comments: Optional[int] = 0
    labels: Optional[Any] = None  # JSON field
    milestone: Optional[str] = None
    commits: Optional[int] = 0
    pr_type: Optional[str] = None

    ai_score: Optional[float] = None
    risk_level: Optional[str] = None
    issue_count: Optional[int] = 0
    warning_count: Optional[int] = 0
    files_changed: Optional[int] = 0
    lines_added: Optional[int] = 0
    lines_deleted: Optional[int] = 0
    ai_review_started_at: Optional[datetime] = None
    ai_review_completed_at: Optional[datetime] = None
    ai_review_time_seconds: Optional[float] = None
    user_review_time_minutes: Optional[float] = None
    ai_analysis: Optional[Any] = None  # JSON field
    review_status: Optional[str] = "AI only"
    reviewers: Optional[List[Any]] = Field(default_factory=list)

    repository_id: int
    author_id: int

class PullRequestCreate(PullRequestBase):
    pass

class PullRequestUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    ai_score: Optional[float] = None
    risk_level: Optional[str] = None
    issue_count: Optional[int] = None
    warning_count: Optional[int] = None
    files_changed: Optional[int] = None
    lines_added: Optional[int] = None
    lines_deleted: Optional[int] = None
    review_status: Optional[str] = None
    reviewers: Optional[List[Any]] = None
    ai_analysis: Optional[Any] = None

class PullRequestRead(PullRequestBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    files: List[PRFileRead] = []
    analysis_history: List[PullRequestAnalysisHistoryRead] = []
    reviews: List[PullRequestReviewRead] = []

    class Config:
        from_attributes = True

    @property
    def lifetime_seconds(self) -> Optional[float]:
        end = self.github_merged_at or self.github_closed_at
        if self.github_created_at and end:
            return (end - self.github_created_at).total_seconds()
        return None

class GithubImportRequest(BaseModel):
    github_url: str
    github_token: Optional[str] = None

class PullRequestAnalysis(BaseModel):
    pr_id: int
    ai_score: Optional[float] = None
    risk_level: Optional[str] = None
    issues: Optional[List[dict]] = []
    warnings: Optional[List[dict]] = []
    recommendations: Optional[List[dict]] = []
    summary: Optional[str] = None
    reviewed_by: Optional[str] = None