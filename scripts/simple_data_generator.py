#!/usr/bin/env python3
"""
Simple Data Generator for CodeReviewPro - Debug Version
"""

import sys
import os
import random
from datetime import datetime, timedelta
from faker import Faker
import json

# Add the parent directory to the path so we can import our app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal, engine
from app.models import User, Repository, PullRequest
from app.models import Base
from sqlalchemy import text

fake = Faker()

def main():
    """Generate minimal sample data"""
    print("🚀 Starting simple data generation...")
    
    # Create database tables
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        # Clear existing data in correct order (respecting foreign keys)
        print("🧹 Clearing existing data...")
        # First delete dependent records
        db.execute(text("DELETE FROM pull_requests"))
        db.execute(text("DELETE FROM branches"))
        db.execute(text("DELETE FROM repositories"))
        db.execute(text("DELETE FROM users"))
        db.commit()
        
        # Create a simple user
        print("👥 Creating sample user...")
        user = User(
            username="testuser",
            email="test@example.com",
            hashed_password=User.get_password_hash("password123"),
            github_id=12345,
            login="testuser",
            type="user"
        )
        db.add(user)
        db.commit()
        
        # Create a simple repository
        print("📁 Creating sample repository...")
        repo = Repository(
            name="test-repo",
            full_name="testuser/test-repo",
            owner_id=user.id,
            default_branch="main",
            is_private=False,
            description="Test repository",
            github_id=67890,
            url="https://github.com/testuser/test-repo",
            created_at=datetime.utcnow()
        )
        db.add(repo)
        db.commit()
        
        # Create a simple pull request
        print("🔄 Creating sample pull request...")
        pr = PullRequest(
            number=1,
            title="Test PR",
            description="Test pull request",
            branch="feature/test",
            base_branch="main",
            status="open",
            repository_id=repo.id,
            author_id=user.id
        )
        db.add(pr)
        db.commit()
        
        print("✅ Simple data generation completed!")
        print(f"Created 1 user, 1 repository, 1 pull request")
        
    except Exception as e:
        print(f"❌ Error generating sample data: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()
