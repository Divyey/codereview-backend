from pydantic import BaseModel
from typing import Optional, Any, List

class AIAnalysis(BaseModel):
    summary: Optional[str]
    ai_score: Optional[float]
    risk_level: Optional[str]
    issues: Optional[Any]  # or List[dict] if you want to be more specific
    warnings: Optional[Any]
    recommendations: Optional[Any]

# from pydantic import BaseModel
# from typing import List, Optional

# class Issue(BaseModel):
#     type: str
#     severity: str
#     message: str
#     file: Optional[str] = None
#     line: Optional[int] = None

# class Warning(BaseModel):
#     type: str
#     severity: str
#     message: str
#     suggestion: Optional[str] = None

# class AIAnalysis(BaseModel):
#     ai_score: float
#     risk_level: str
#     issue_count: int
#     warning_count: int
#     issues: List[Issue]
#     warnings: List[Warning]
#     recommendations: List[str]
#     summary: str
