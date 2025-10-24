from sqlalchemy import Column, Integer, String, BigInteger
from app.core.database import Base

class Contributor(Base):
    __tablename__ = "contributors"
    id = Column(Integer, primary_key=True)
    github_id = Column(BigInteger, unique=True, nullable=False)
    login = Column(String, nullable=False)
    email = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
