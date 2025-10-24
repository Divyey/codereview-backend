from sqlalchemy import Column, Integer, String, Text, Float, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class SecurityFinding(Base):
    __tablename__ = "security_findings"
    id = Column(Integer, primary_key=True)
    pull_request_id = Column(Integer, ForeignKey("pull_requests.id"))
    repo_id = Column(Integer, ForeignKey("repositories.id"))
    file_id = Column(Integer, ForeignKey("pr_files.id", ondelete="CASCADE"))
    type = Column(String)  # secret, infra, sca
    issue_type = Column(String)
    severity = Column(String)
    likelihood = Column(String)
    confidence = Column(Float)
    cwe = Column(String)
    owasp = Column(String)
    description = Column(Text)
    line = Column(Integer)
    code_example_bad = Column(Text)
    code_example_good = Column(Text)

    pull_request = relationship("PullRequest", back_populates="security_findings")
    file = relationship("PRFile", back_populates="security_findings")
