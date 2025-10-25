from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from ..core.database import Base
from cryptography.fernet import Fernet
from ..core.config import settings
import enum

fernet = Fernet(settings.FERNET_KEY)

class APIKeyType(enum.Enum):
    GITHUB = "github"
    SLACK = "slack"
    JIRA = "jira"
    DISCORD = "discord"
    TEAMS = "teams"

class UserAPIKey(Base):
    __tablename__ = "user_api_keys"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    key_type = Column(String, nullable=False)  # github, slack, etc.
    key_name = Column(String, nullable=False)  # User-friendly name like "Personal GitHub Token"
    _encrypted_key = Column("encrypted_key", Text, nullable=False)
    key_prefix = Column(String(10), nullable=True)  # First few characters for display (ghp_, xoxb-, etc.)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="api_keys")
    
    @property
    def api_key(self):
        """Decrypt and return the API key"""
        if self._encrypted_key:
            try:
                return fernet.decrypt(self._encrypted_key.encode()).decode()
            except Exception:
                return None
        return None
    
    @api_key.setter
    def api_key(self, value):
        """Encrypt and store the API key"""
        if value:
            self._encrypted_key = fernet.encrypt(value.encode()).decode()
            # Extract prefix for display (first 4-8 characters depending on key type)
            self.key_prefix = self._extract_key_prefix(value)
        else:
            self._encrypted_key = None
            self.key_prefix = None
    
    def _extract_key_prefix(self, key):
        """Extract the prefix from the API key for display purposes"""
        if not key:
            return None
            
        # GitHub tokens: ghp_, gho_, ghu_, ghs_, ghr_
        if key.startswith(('ghp_', 'gho_', 'ghu_', 'ghs_', 'ghr_')):
            return key[:8]  # Show first 8 characters
        # Slack tokens: xoxb-, xoxp-, xoxa-, xoxr-
        elif key.startswith(('xoxb-', 'xoxp-', 'xoxa-', 'xoxr-')):
            return key[:8]  # Show first 8 characters
        # Generic fallback
        else:
            return key[:6]  # Show first 6 characters
    
    @property
    def masked_key(self):
        """Return a masked version of the key for display"""
        if not self.key_prefix:
            return "***********"
        
        # Show prefix + asterisks
        return f"{self.key_prefix}{'*' * 20}"
    
    def validate_key_format(self):
        """Validate the API key format based on type"""
        key = self.api_key
        if not key:
            return False, "API key is required"
        
        if self.key_type == APIKeyType.GITHUB.value:
            # GitHub personal access tokens
            if not (key.startswith(('ghp_', 'gho_', 'ghu_', 'ghs_', 'ghr_')) and len(key) >= 40):
                return False, "Invalid GitHub token format. Should start with ghp_, gho_, ghu_, ghs_, or ghr_ and be at least 40 characters"
        
        elif self.key_type == APIKeyType.SLACK.value:
            # Slack tokens
            if not (key.startswith(('xoxb-', 'xoxp-', 'xoxa-', 'xoxr-')) and len(key) >= 50):
                return False, "Invalid Slack token format. Should start with xoxb-, xoxp-, xoxa-, or xoxr- and be at least 50 characters"
        
        return True, "Valid"
    
    def update_last_used(self):
        """Update the last used timestamp"""
        self.last_used_at = datetime.utcnow()
    
    def to_dict(self, include_key=False):
        """Convert to dictionary for API responses"""
        data = {
            "id": self.id,
            "key_type": self.key_type,
            "key_name": self.key_name,
            "masked_key": self.masked_key,
            "description": self.description,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
        }
        
        # Only include actual key if explicitly requested (for internal use)
        if include_key:
            data["api_key"] = self.api_key
            
        return data
