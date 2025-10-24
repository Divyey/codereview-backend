from pydantic_settings import BaseSettings
from typing import Optional
import os

# ENV = os.getenv("ENV", "development")
FERNET_KEY = os.getenv("FERNET_KEY")

class Settings(BaseSettings):
    DATABASE_URL: str
    
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    GITHUB_CLIENT_ID: Optional[str] = None
    GITHUB_CLIENT_SECRET: Optional[str] = None
    GITHUB_TOKEN: Optional[str] = None
    GITHUB_WEBHOOK_SECRET: str = "" 
    
    OPENAI_API_KEY: str        
    
    ENV: str # = "development"  # or "production" in prod
    FERNET_KEY: str
    
    # REDIS_URL: str = "redis://localhost:6379"
    
    BACKEND_CORS_ORIGINS: list = ["http://localhost:5173"]
    
    class Config:
        env_file = ".env"

settings = Settings()