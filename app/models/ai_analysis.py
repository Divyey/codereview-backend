from pydantic import BaseModel
from typing import Optional, Any
from ..core.database import Base

class AIAnalysis(BaseModel):
    summary: Optional[str]
    ai_score: Optional[float]
    risk_level: Optional[str]
    issues: Optional[Any]
    warnings: Optional[Any]
    recommendations: Optional[Any]
