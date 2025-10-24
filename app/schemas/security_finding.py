# from pydantic import BaseModel
# from typing import Optional

# class SecurityFindingBase(BaseModel):
#     pull_request_id: int
#     repo_id: Optional[int] = None
#     file_id: Optional[int] = None
#     type: str  # secret, infra, sca
#     issue_type: Optional[str] = None
#     severity: Optional[str] = None
#     likelihood: Optional[str] = None
#     confidence: Optional[float] = None
#     cwe: Optional[str] = None
#     owasp: Optional[str] = None
#     description: Optional[str] = None
#     line: Optional[int] = None
#     code_example_bad: Optional[str] = None
#     code_example_good: Optional[str] = None

# class SecurityFindingCreate(SecurityFindingBase):
#     pass

# class SecurityFindingUpdate(BaseModel):
#     issue_type: Optional[str] = None
#     severity: Optional[str] = None
#     likelihood: Optional[str] = None
#     confidence: Optional[float] = None
#     cwe: Optional[str] = None
#     owasp: Optional[str] = None
#     description: Optional[str] = None
#     line: Optional[int] = None
#     code_example_bad: Optional[str] = None
#     code_example_good: Optional[str] = None

# class SecurityFindingRead(SecurityFindingBase):
#     id: int

#     class Config:
#         from_attributes = True
