"""
Token Service - Centralized GitHub token resolution and management
"""
from typing import Optional
from ..models.user import User
from ..core.config import settings


class TokenService:
    @staticmethod
    def get_github_token(user: User, provided_token: Optional[str] = None) -> Optional[str]:
        """
        Get GitHub token with fallback logic (API Key feature disabled)
        """
        # 1. Use provided token if given
        if provided_token:
            return provided_token
        
        # 2. Use legacy User.github_token
        if user.github_token:
            return user.github_token
        
        # 3. Fallback to system token
        return settings.GITHUB_TOKEN
    
    @staticmethod
    def update_token_usage(user: User, token_used: str, db_session=None) -> None:
        """
        No-op since API Key feature is disabled
        """
        pass
    
    @staticmethod
    def get_user_github_tokens(user: User) -> list:
        """
        API Key feature disabled
        """
        return []
    
    @staticmethod
    def has_github_token(user: User) -> bool:
        """
        Check if user has legacy token or system token
        """
        return bool(user.github_token or settings.GITHUB_TOKEN)
