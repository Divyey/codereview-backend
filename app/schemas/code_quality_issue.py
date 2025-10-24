from pydantic import BaseModel
from typing import Optional

class CodeQualityIssueBase(BaseModel):
    repo_id: int
    pull_request_id: Optional[int] = None
    file_id: Optional[int] = None
    type: str  # docstring_absent, complex_function, antipattern, dead_code, duplicate_code, security, etc.
    function_name: Optional[str] = None
    line: Optional[int] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    severity: Optional[str] = None
    message: Optional[str] = None
    suggestion: Optional[str] = None
    maintainability_index: Optional[float] = None
    confidence: Optional[float] = None
    path: Optional[str] = None
    status: Optional[str] = "open"

class CodeQualityIssueCreate(CodeQualityIssueBase):
    pass

class CodeQualityIssueUpdate(BaseModel):
    function_name: Optional[str] = None
    line: Optional[int] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    severity: Optional[str] = None
    message: Optional[str] = None
    suggestion: Optional[str] = None
    maintainability_index: Optional[float] = None
    confidence: Optional[float] = None
    path: Optional[str] = None

class CodeQualityIssue(CodeQualityIssueBase):
    id: int

    class Config:
        from_attributes = True
