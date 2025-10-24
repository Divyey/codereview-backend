from sqlalchemy import Column, Integer, String, Text, Float, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class CodeQualityIssue(Base):
    __tablename__ = "code_quality_issues"
    id = Column(Integer, primary_key=True)
    repo_id = Column(Integer, ForeignKey("repositories.id"))
    pull_request_id = Column(Integer, ForeignKey("pull_requests.id"), nullable=True)
    file_id = Column(Integer, ForeignKey("pr_files.id"), nullable=True)
    type = Column(String)  # docstring_absent, complex_function, antipattern, dead_code, duplicate_code
    function_name = Column(String, nullable=True)
    line = Column(Integer, nullable=True)
    line_start = Column(Integer, nullable=True)     
    line_end = Column(Integer, nullable=True)  
    severity = Column(String, nullable=True)
    message = Column(Text, nullable=True)
    suggestion = Column(Text, nullable=True)
    maintainability_index = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)
    path = Column(String, nullable=True)  
    status = Column(String, default="open") 

    pull_request = relationship("PullRequest", back_populates="code_quality_issues")
    file = relationship("PRFile", back_populates="code_quality_issues")
