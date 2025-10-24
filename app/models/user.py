from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship 
from ..core.database import Base
from passlib.context import CryptContext
from cryptography.fernet import Fernet
from ..core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
fernet = Fernet(settings.FERNET_KEY)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    github_id = Column(Integer, unique=True, index=True)  
    login = Column(String, unique=True, index=True)
    type = Column(String) # userr/organisation

    _github_token = Column("github_token", String, nullable=True)
    repositories = relationship("Repository", back_populates="owner")
    pull_requests = relationship("PullRequest", back_populates="author")
    comments = relationship("PRComment", back_populates="user")
    reviews = relationship("PullRequestReview", back_populates="reviewer")

    def verify_password(self, password: str) -> bool:
        return pwd_context.verify(password, self.hashed_password)

    @staticmethod
    def get_password_hash(password: str) -> str:
        return pwd_context.hash(password)

    @property
    def github_token(self):
        if self._github_token:
            return fernet.decrypt(self._github_token.encode()).decode()
        return None

    @github_token.setter
    def github_token(self, value):
        if value:
            self._github_token = fernet.encrypt(value.encode()).decode()
        else:
            self._github_token = None
