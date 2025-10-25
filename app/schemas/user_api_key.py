from pydantic import BaseModel, validator
from typing import Optional
from datetime import datetime
from enum import Enum

class APIKeyType(str, Enum):
    GITHUB = "github"
    SLACK = "slack"
    JIRA = "jira"
    DISCORD = "discord"
    TEAMS = "teams"

class UserAPIKeyBase(BaseModel):
    key_type: APIKeyType
    key_name: str
    description: Optional[str] = None
    is_active: bool = True

class UserAPIKeyCreate(UserAPIKeyBase):
    api_key: str
    
    @validator('api_key')
    def validate_api_key(cls, v):
        if not v or len(v.strip()) < 10:
            raise ValueError('API key must be at least 10 characters long')
        return v.strip()
    
    @validator('key_name')
    def validate_key_name(cls, v):
        if not v or len(v.strip()) < 3:
            raise ValueError('Key name must be at least 3 characters long')
        return v.strip()

class UserAPIKeyUpdate(BaseModel):
    key_name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    api_key: Optional[str] = None
    
    @validator('api_key')
    def validate_api_key(cls, v):
        if v is not None and len(v.strip()) < 10:
            raise ValueError('API key must be at least 10 characters long')
        return v.strip() if v else v
    
    @validator('key_name')
    def validate_key_name(cls, v):
        if v is not None and len(v.strip()) < 3:
            raise ValueError('Key name must be at least 3 characters long')
        return v.strip() if v else v

class UserAPIKeyRead(UserAPIKeyBase):
    id: int
    masked_key: str
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    last_used_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class UserAPIKeyReadWithKey(UserAPIKeyRead):
    """Schema that includes the actual API key - only for internal use"""
    api_key: str

class APIKeyValidationResponse(BaseModel):
    is_valid: bool
    message: str
    key_type: Optional[str] = None

class APIKeyTestResponse(BaseModel):
    success: bool
    message: str
    details: Optional[dict] = None
