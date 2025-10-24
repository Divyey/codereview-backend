from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class RepositoryBase(BaseModel):
    name: str
    full_name: str
    default_branch: Optional[str] = None
    is_private: bool = False

class RepositoryCreate(RepositoryBase):
    owner_id: int

class RepositoryUpdate(BaseModel):
    name: Optional[str] = None
    full_name: Optional[str] = None
    default_branch: Optional[str] = None
    is_private: Optional[bool] = None

class RepositoryRead(RepositoryBase):
    id: int
    owner_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class GithubRepositoryImportRequest(BaseModel):
    github_url: str
    github_token: Optional[str] = None
