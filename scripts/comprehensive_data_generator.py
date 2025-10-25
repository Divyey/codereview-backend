#!/usr/bin/env python3
"""
Comprehensive Data Generator for CodeReviewPro
Creates realistic data for testing the optimized dashboard
"""

import sys
import os
import random
from datetime import timedelta
from faker import Faker
import json

# Add the parent directory to the path so we can import our app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal, engine
from app.models import (
    User, Repository, PullRequest, PRFile, SecurityFinding, 
    CodeQualityIssue
)
from app.models import Base
from sqlalchemy import text

fake = Faker()

# Sample data constants
PROGRAMMING_LANGUAGES = ['Python', 'JavaScript', 'TypeScript', 'Java', 'Go', 'Rust']
FILE_EXTENSIONS = {
    'Python': ['.py', '.pyx', '.pyi'],
    'JavaScript': ['.js', '.jsx', '.mjs'],
    'TypeScript': ['.ts', '.tsx', '.d.ts'],
    'Java': ['.java'],
    'Go': ['.go'],
    'Rust': ['.rs']
}

SECURITY_FINDING_TYPES = [
    'SQL Injection', 'XSS', 'CSRF', 'Authentication Bypass', 'Authorization Flaw',
    'Insecure Deserialization', 'Path Traversal', 'Command Injection', 'SSRF'
]

CODE_QUALITY_ISSUES = [
    'Cyclomatic Complexity', 'Code Duplication', 'Long Method', 'Large Class',
    'Dead Code', 'Unused Variables', 'Magic Numbers', 'Long Parameter List'
]

SEVERITY_LEVELS = ['Critical', 'High', 'Medium', 'Low']
PR_STATUSES = ['open', 'closed', 'merged']
RISK_LEVELS = ['Critical', 'High', 'Medium', 'Low']

def create_comprehensive_data(db, user_id):
    """Create comprehensive test data for a user"""
    
    # Create 5 repositories
    repositories = []
    for _ in range(5):
        lang = random.choice(PROGRAMMING_LANGUAGES)
        repo_name = f"{fake.word()}-{lang.lower()}-{fake.word()}"
        
        repo = Repository(
            name=repo_name,
            full_name=f"testuser/{repo_name}",
            owner_id=user_id,
            default_branch="development",
            is_private=random.choice([True, False]),
            description=fake.text(max_nb_chars=200),
            github_id=fake.random_int(min=100000, max=9999999),
            url=f"https://github.com/testuser/{repo_name}",
            created_at=fake.date_time_between(start_date='-1y', end_date='now')
        )
        db.add(repo)
        repositories.append(repo)
    
    db.commit()
    
    # Create 50 pull requests across repositories
    pull_requests = []
    for i in range(50):
        repo = random.choice(repositories)
        
        # Generate realistic PR data with dates spread over last 3 months
        created_at = fake.date_time_between(start_date='-3m', end_date='now')
        status = random.choice(PR_STATUSES)
        
        # Calculate realistic metrics
        additions = random.randint(5, 500)
        deletions = random.randint(1, additions // 2)
        changed_files = random.randint(1, 15)
        commits = random.randint(1, 10)
        
        # AI analysis data
        ai_score = round(random.uniform(0.1, 1.0), 2)
        risk_level = random.choice(RISK_LEVELS)
        issue_count = random.randint(0, 20)
        warning_count = random.randint(0, 15)
        
        # Review timing
        ai_review_time = random.randint(30, 300)  # seconds
        user_review_time = random.randint(10, 180) if random.random() > 0.3 else None  # minutes
        
        pr = PullRequest(
            number=fake.random_int(min=1, max=9999),
            title=fake.sentence(nb_words=6),
            description=fake.text(max_nb_chars=500),
            branch=f"feature/{fake.word()}-{fake.word()}",
            base_branch="development",
            status=status,
            github_id=fake.random_int(min=100000, max=9999999),
            github_url=f"https://github.com/{repo.full_name}/pull/{fake.random_int(min=1, max=999)}",
            github_created_at=created_at,
            github_updated_at=fake.date_time_between(start_date=created_at, end_date='now'),
            github_closed_at=fake.date_time_between(start_date=created_at, end_date='now') if status in ['closed', 'merged'] else None,
            github_merged_at=fake.date_time_between(start_date=created_at, end_date='now') if status == 'merged' else None,
            github_author=fake.user_name(),
            merge_commit_sha=fake.sha1() if status == 'merged' else None,
            additions=additions,
            deletions=deletions,
            changed_files=changed_files,
            review_comments=random.randint(0, 25),
            comments=random.randint(0, 10),
            labels=json.dumps(random.sample(['bug', 'feature', 'enhancement', 'documentation'], k=random.randint(0, 3))),
            commits=commits,
            pr_type=random.choice(['feature', 'bugfix', 'hotfix', 'refactor', 'docs']),
            ai_score=ai_score,
            risk_level=risk_level,
            issue_count=issue_count,
            warning_count=warning_count,
            files_changed=changed_files,
            lines_added=additions,
            lines_deleted=deletions,
            ai_review_started_at=created_at + timedelta(minutes=random.randint(1, 60)),
            ai_review_completed_at=created_at + timedelta(minutes=random.randint(1, 60), seconds=ai_review_time),
            ai_review_time_seconds=ai_review_time,
            user_review_time_minutes=user_review_time,
            ai_analysis=json.dumps({
                "summary": fake.text(max_nb_chars=200),
                "complexity_score": round(random.uniform(0.1, 1.0), 2),
                "maintainability_score": round(random.uniform(0.1, 1.0), 2),
                "security_score": round(random.uniform(0.1, 1.0), 2),
                "test_coverage": round(random.uniform(0.0, 1.0), 2),
                "recommendations": [fake.sentence() for _ in range(random.randint(1, 5))]
            }),
            review_status=random.choice(['AI only', 'Human reviewed', 'Approved', 'Changes requested']),
            repository_id=repo.id,
            author_id=user_id,
            # created_at will use server default
        )
        
        db.add(pr)
        pull_requests.append(pr)
    
    db.commit()
    
    # Create PR files for each PR
    pr_files = []
    for pr in pull_requests:
        # Determine language based on repository
        lang = random.choice(PROGRAMMING_LANGUAGES)
        extensions = FILE_EXTENSIONS[lang]
        
        # Create 1-8 files per PR
        for i in range(random.randint(1, min(8, pr.changed_files))):
            filename = f"{fake.word()}/{fake.word()}{random.choice(extensions)}"
            
            pr_file = PRFile(
                filename=filename,
                additions=random.randint(1, 100),
                deletions=random.randint(0, 50),
                status=random.choice(['added', 'modified', 'deleted', 'renamed']),
                patch=fake.text(max_nb_chars=1000),
                content=fake.text(max_nb_chars=2000),
                old_content=fake.text(max_nb_chars=1800),
                language=lang,
                pull_request_id=pr.id
            )
            
            db.add(pr_file)
            pr_files.append(pr_file)
    
    db.commit()
    
    # Create security findings (40% of PRs have security issues)
    security_findings = []
    for pr in pull_requests:
        if random.random() < 0.4:
            pr_file_subset = [f for f in pr_files if f.pull_request_id == pr.id]
            if not pr_file_subset:
                continue
                
            # Create 1-5 security findings per PR
            for i in range(random.randint(1, 5)):
                pr_file = random.choice(pr_file_subset)
                finding_type = random.choice(SECURITY_FINDING_TYPES)
                severity = random.choice(SEVERITY_LEVELS)
                
                finding = SecurityFinding(
                    pull_request_id=pr.id,
                    repo_id=pr.repository_id,
                    file_id=pr_file.id,
                    type="security",
                    issue_type=finding_type,
                    severity=severity,
                    likelihood=random.choice(['High', 'Medium', 'Low']),
                    confidence=round(random.uniform(0.5, 1.0), 2),
                    cwe=f"CWE-{random.randint(1, 999)}",
                    owasp=f"A{random.randint(1, 10)}",
                    description=f"Potential {finding_type.lower()} vulnerability detected in {pr_file.filename}",
                    line=random.randint(1, 200),
                    code_example_bad=fake.text(max_nb_chars=200),
                    code_example_good=fake.text(max_nb_chars=200)
                )
                
                db.add(finding)
                security_findings.append(finding)
    
    db.commit()
    
    # Create code quality issues (70% of PRs have quality issues)
    quality_issues = []
    for pr in pull_requests:
        if random.random() < 0.7:
            pr_file_subset = [f for f in pr_files if f.pull_request_id == pr.id]
            if not pr_file_subset:
                continue
                
            # Create 1-10 quality issues per PR
            for i in range(random.randint(1, 10)):
                pr_file = random.choice(pr_file_subset)
                issue_type = random.choice(CODE_QUALITY_ISSUES)
                severity = random.choice(['High', 'Medium', 'Low'])
                
                issue = CodeQualityIssue(
                    pull_request_id=pr.id,
                    file_id=pr_file.id,
                    type=issue_type,
                    severity=severity,
                    message=f"{issue_type} detected in {pr_file.filename}",
                    line_start=random.randint(1, 200),
                    line_end=random.randint(1, 200),
                    rule_id=f"RULE_{random.randint(1000, 9999)}",
                    status='open'
                )
                
                db.add(issue)
                quality_issues.append(issue)
    
    db.commit()
    
    return {
        "repositories": len(repositories),
        "pull_requests": len(pull_requests),
        "pr_files": len(pr_files),
        "security_findings": len(security_findings),
        "quality_issues": len(quality_issues)
    }

def main():
    """Generate comprehensive sample data"""
    print("🚀 Starting comprehensive data generation...")
    
    # Create database tables
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        # Clear existing data in correct order (respecting foreign keys)
        print("🧹 Clearing existing data...")
        db.execute(text("DELETE FROM security_findings"))
        db.execute(text("DELETE FROM code_quality_issues"))
        db.execute(text("DELETE FROM pr_comments"))
        db.execute(text("DELETE FROM pull_request_reviews"))
        db.execute(text("DELETE FROM pr_files"))
        db.execute(text("DELETE FROM pull_requests"))
        db.execute(text("DELETE FROM branches"))
        db.execute(text("DELETE FROM repositories"))
        db.execute(text("DELETE FROM users"))
        db.commit()
        
        # Create test user
        print("👥 Creating test user...")
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
        
        # Create comprehensive data
        print("📊 Creating comprehensive sample data...")
        stats = create_comprehensive_data(db, user.id)
        
        print("✅ Comprehensive data generation completed!")
        print("Generated:")
        print("  - 1 user")
        print(f"  - {stats['repositories']} repositories")
        print(f"  - {stats['pull_requests']} pull requests")
        print(f"  - {stats['pr_files']} PR files")
        print(f"  - {stats['security_findings']} security findings")
        print(f"  - {stats['quality_issues']} code quality issues")
        
    except Exception as e:
        print(f"❌ Error generating sample data: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()
