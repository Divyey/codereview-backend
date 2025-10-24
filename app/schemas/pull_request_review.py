from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class PullRequestReviewBase(BaseModel):
    pull_request_id: int
    reviewer_id: Optional[int] = None
    reviewer_login: Optional[str] = None
    state: str  # APPROVED, CHANGES_REQUESTED, COMMENTED, etc.
    body: Optional[str] = None

class PullRequestReviewCreate(PullRequestReviewBase):
    pass

class PullRequestReviewUpdate(BaseModel):
    state: Optional[str] = None
    body: Optional[str] = None

class PullRequestReviewRead(PullRequestReviewBase):
    id: int
    submitted_at: datetime

    class Config:
        from_attributes = True
