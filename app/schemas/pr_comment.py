from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class PRCommentBase(BaseModel):
    pull_request_id: int
    user_id: int
    body: str
    ai_generated: bool = False
    type: str = "comment"  # question, answer, comment

class PRCommentCreate(PRCommentBase):
    pass

class PRCommentUpdate(BaseModel):
    body: Optional[str] = None
    ai_generated: Optional[bool] = None
    type: Optional[str] = None

class PRCommentRead(PRCommentBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
