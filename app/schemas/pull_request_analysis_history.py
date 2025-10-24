from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime

class PullRequestAnalysisHistoryBase(BaseModel):
    pull_request_id: int
    commit_sha: Optional[str] = None
    analyzed_at: Optional[datetime] = None
    ai_score: Optional[float] = None
    risk_level: Optional[str] = None
    issues: Optional[Any] = None  # Use List[dict] or more specific type if you know the structure
    warnings: Optional[Any] = None
    recommendations: Optional[Any] = None
    summary: Optional[str] = None
    reviewer: Optional[str] = None

class PullRequestAnalysisHistoryCreate(PullRequestAnalysisHistoryBase):
    pass

class PullRequestAnalysisHistoryUpdate(BaseModel):
    ai_score: Optional[float] = None
    risk_level: Optional[str] = None
    issues: Optional[Any] = None
    warnings: Optional[Any] = None
    recommendations: Optional[Any] = None
    summary: Optional[str] = None
    reviewer: Optional[str] = None

class PullRequestAnalysisHistoryRead(PullRequestAnalysisHistoryBase):
    id: int

    class Config:
        from_attributes = True
