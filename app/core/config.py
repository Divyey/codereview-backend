from pydantic_settings import BaseSettings
from pydantic import validator
from typing import Optional, List
import os
from cryptography.fernet import Fernet

# ENV = os.getenv("ENV", "development")
FERNET_KEY = os.getenv("FERNET_KEY")

class Settings(BaseSettings):
    DATABASE_URL: str
    
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    GITHUB_CLIENT_ID: Optional[str] = None
    GITHUB_CLIENT_SECRET: Optional[str] = None
    GITHUB_TOKEN: Optional[str] = None
    GITHUB_WEBHOOK_SECRET: str = "" 
    
    OPENAI_API_KEY: str        
    
    ENV: str = "development"  # development, staging, production
    FERNET_KEY: str
    
    # REDIS_URL: str = "redis://localhost:6379"
    
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:5173"]
    
    @validator('SECRET_KEY')
    def secret_key_strength(cls, v):
        if len(v) < 32:
            raise ValueError('SECRET_KEY must be at least 32 characters for production security')
        return v
    
    @validator('FERNET_KEY')
    def validate_fernet_key(cls, v):
        try:
            Fernet(v.encode())
        except Exception:
            raise ValueError('Invalid FERNET_KEY format. Generate with: from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')
        return v
    
    @validator('ENV')
    def validate_environment(cls, v):
        if v not in ['development', 'staging', 'production']:
            raise ValueError('ENV must be one of: development, staging, production')
        return v
    
    class Config:
        env_file = ".env"
        validate_assignment = True

settings = Settings()