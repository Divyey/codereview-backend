from pydantic import BaseModel
from typing import Optional

class PRFileBase(BaseModel):
    pull_request_id: int
    filename: str
    status: Optional[str] = None
    additions: Optional[int] = 0
    deletions: Optional[int] = 0
    patch: Optional[str] = None
    content: Optional[str] = None
    old_content: Optional[str] = None
    language: Optional[str] = None

class PRFileCreate(PRFileBase):
    pass

class PRFileUpdate(BaseModel):
    status: Optional[str] = None
    additions: Optional[int] = None
    deletions: Optional[int] = None
    patch: Optional[str] = None
    content: Optional[str] = None
    old_content: Optional[str] = None
    language: Optional[str] = None

class PRFileRead(PRFileBase):
    id: int

    class Config:
        from_attributes = True
