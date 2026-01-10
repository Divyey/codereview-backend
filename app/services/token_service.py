"""
Token Service - Centralized GitHub token resolution and management
"""
from typing import Optional
from ..models.user import User
from ..core.config import settings


class TokenService:
    """Centralized service for handling GitHub token resolution"""
    
    @staticmethod
    def get_github_token(user: User, provided_token: Optional[str] = None) -> Optional[str]:
        """
        Get GitHub token with intelligent fallback logic
        
        Priority order:
        1. Provided token (from request)
        2. Primary GitHub token from UserAPIKey (new system)
        3. Legacy User.github_token (backward compatibility)
        4. System default token
        
        Args:
            user: User object
            provided_token: Token provided in the request (highest priority)
            
        Returns:
            GitHub token string or None
        """
        # 1. Use provided token if given
        if provided_token:
            return provided_token
        
        # 2. Try primary GitHub token from UserAPIKey (new system)
        primary_token = user.primary_github_token
        if primary_token:
            return primary_token
        
        # 3. Fallback to system token
        return settings.GITHUB_TOKEN
    
    @staticmethod
    def update_token_usage(user: User, token_used: str, db_session=None) -> None:
        """
        Update last_used_at for the token that was used
        
        Args:
            user: User object
            token_used: The actual token that was used
            db_session: Database session (optional, for committing changes)
        """
        # Find matching UserAPIKey and update last_used_at
        for api_key in user.api_keys:
            if (api_key.key_type == "github" and 
                api_key.is_active and 
                api_key.api_key == token_used):
                api_key.update_last_used()
                if db_session:
                    db_session.commit()
                break
    
    @staticmethod
    def get_user_github_tokens(user: User) -> list:
        """
        Get all active GitHub tokens for a user
        
        Returns:
            List of UserAPIKey objects with GitHub tokens
        """
        return [key for key in user.api_keys 
                if key.key_type == "github" and key.is_active]
    
    @staticmethod
    def has_github_token(user: User) -> bool:
        """
        Check if user has any GitHub token available
        
        Returns:
            True if user has at least one GitHub token
        """
        return bool(user.primary_github_token or settings.GITHUB_TOKEN)
