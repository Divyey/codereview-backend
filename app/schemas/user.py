from pydantic import BaseModel, EmailStr
from typing import Optional

# Response schema (for reading user data)
class UserRead(BaseModel):
    id: int
    username: str
    email: EmailStr

    class Config:
        from_attributes = True

# Request schema for creating a user (registration)
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

# Request schema for updating a user
class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None

# For authentication/token responses
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class UserLogin(BaseModel):
    username: str
    password: str
