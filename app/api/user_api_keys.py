from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import httpx
from datetime import datetime

from ..core.database import get_db
from ..models.user import User
from ..models.user_api_key import UserAPIKey, APIKeyType
from ..schemas.user_api_key import (
    UserAPIKeyCreate, 
    UserAPIKeyUpdate, 
    UserAPIKeyRead, 
    APIKeyValidationResponse,
    APIKeyTestResponse
)
from .auth import get_current_user

router = APIRouter(prefix="/api/user/api-keys", tags=["User API Keys"])

@router.get("/", response_model=List[UserAPIKeyRead])
def get_user_api_keys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all API keys for the current user"""
    api_keys = db.query(UserAPIKey).filter(
        UserAPIKey.user_id == current_user.id
    ).order_by(UserAPIKey.created_at.desc()).all()
    
    return [key.to_dict() for key in api_keys]

@router.post("/", response_model=UserAPIKeyRead)
def create_api_key(
    api_key_data: UserAPIKeyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new API key for the current user"""
    
    # Check if user already has a key with the same name
    existing_key = db.query(UserAPIKey).filter(
        UserAPIKey.user_id == current_user.id,
        UserAPIKey.key_name == api_key_data.key_name
    ).first()
    
    if existing_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"API key with name '{api_key_data.key_name}' already exists"
        )
    
    # Create new API key
    new_key = UserAPIKey(
        user_id=current_user.id,
        key_type=api_key_data.key_type.value,
        key_name=api_key_data.key_name,
        description=api_key_data.description,
        is_active=api_key_data.is_active
    )
    
    # Set the encrypted API key (this will also set the prefix)
    new_key.api_key = api_key_data.api_key
    
    # Validate the key format
    is_valid, message = new_key.validate_key_format()
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    
    db.add(new_key)
    db.commit()
    db.refresh(new_key)
    
    return new_key.to_dict()

@router.get("/{key_id}", response_model=UserAPIKeyRead)
def get_api_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific API key by ID"""
    api_key = db.query(UserAPIKey).filter(
        UserAPIKey.id == key_id,
        UserAPIKey.user_id == current_user.id
    ).first()
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    return api_key.to_dict()

@router.put("/{key_id}", response_model=UserAPIKeyRead)
def update_api_key(
    key_id: int,
    api_key_data: UserAPIKeyUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update an existing API key"""
    api_key = db.query(UserAPIKey).filter(
        UserAPIKey.id == key_id,
        UserAPIKey.user_id == current_user.id
    ).first()
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    # Check for name conflicts if name is being updated
    if api_key_data.key_name and api_key_data.key_name != api_key.key_name:
        existing_key = db.query(UserAPIKey).filter(
            UserAPIKey.user_id == current_user.id,
            UserAPIKey.key_name == api_key_data.key_name,
            UserAPIKey.id != key_id
        ).first()
        
        if existing_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"API key with name '{api_key_data.key_name}' already exists"
            )
    
    # Update fields
    update_data = api_key_data.dict(exclude_unset=True)
    
    for field, value in update_data.items():
        if field == "api_key":
            api_key.api_key = value  # This will encrypt and set prefix
            # Validate the new key format
            is_valid, message = api_key.validate_key_format()
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=message
                )
        else:
            setattr(api_key, field, value)
    
    api_key.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(api_key)
    
    return api_key.to_dict()

@router.delete("/{key_id}")
def delete_api_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete an API key"""
    api_key = db.query(UserAPIKey).filter(
        UserAPIKey.id == key_id,
        UserAPIKey.user_id == current_user.id
    ).first()
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    db.delete(api_key)
    db.commit()
    
    return {"message": "API key deleted successfully"}

@router.post("/{key_id}/test", response_model=APIKeyTestResponse)
async def test_api_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Test an API key to verify it's working"""
    api_key = db.query(UserAPIKey).filter(
        UserAPIKey.id == key_id,
        UserAPIKey.user_id == current_user.id
    ).first()
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    if not api_key.is_active:
        return APIKeyTestResponse(
            success=False,
            message="API key is inactive"
        )
    
    try:
        if api_key.key_type == APIKeyType.GITHUB.value:
            # Test GitHub API key
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.github.com/user",
                    headers={"Authorization": f"token {api_key.api_key}"},
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    user_data = response.json()
                    api_key.update_last_used()
                    db.commit()
                    return APIKeyTestResponse(
                        success=True,
                        message="GitHub API key is valid",
                        details={
                            "username": user_data.get("login"),
                            "name": user_data.get("name"),
                            "public_repos": user_data.get("public_repos")
                        }
                    )
                else:
                    return APIKeyTestResponse(
                        success=False,
                        message=f"GitHub API returned status {response.status_code}"
                    )
        
        elif api_key.key_type == APIKeyType.SLACK.value:
            # Test Slack API key
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://slack.com/api/auth.test",
                    headers={"Authorization": f"Bearer {api_key.api_key}"},
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("ok"):
                        api_key.update_last_used()
                        db.commit()
                        return APIKeyTestResponse(
                            success=True,
                            message="Slack API key is valid",
                            details={
                                "user": data.get("user"),
                                "team": data.get("team"),
                                "url": data.get("url")
                            }
                        )
                    else:
                        return APIKeyTestResponse(
                            success=False,
                            message=f"Slack API error: {data.get('error', 'Unknown error')}"
                        )
                else:
                    return APIKeyTestResponse(
                        success=False,
                        message=f"Slack API returned status {response.status_code}"
                    )
        
        else:
            return APIKeyTestResponse(
                success=False,
                message=f"Testing not implemented for {api_key.key_type} keys"
            )
            
    except httpx.TimeoutException:
        return APIKeyTestResponse(
            success=False,
            message="Request timed out while testing API key"
        )
    except Exception as e:
        return APIKeyTestResponse(
            success=False,
            message=f"Error testing API key: {str(e)}"
        )

@router.post("/validate", response_model=APIKeyValidationResponse)
def validate_api_key_format(
    key_type: APIKeyType,
    api_key: str
):
    """Validate API key format without storing it"""
    
    # Create a temporary UserAPIKey instance for validation
    temp_key = UserAPIKey(
        key_type=key_type.value,
        key_name="temp",
        user_id=0  # Temporary
    )
    temp_key.api_key = api_key
    
    is_valid, message = temp_key.validate_key_format()
    
    return APIKeyValidationResponse(
        is_valid=is_valid,
        message=message,
        key_type=key_type.value
    )
