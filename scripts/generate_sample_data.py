#!/usr/bin/env python3
"""
Sample Data Generator for CodeReviewPro
Generates realistic pull request data, security findings, and code quality issues
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
    CodeQualityIssue, PRComment, PullRequestReview, Branch
)
from app.models import Base

fake = Faker()

# Sample data constants
PROGRAMMING_LANGUAGES = ['Python', 'JavaScript', 'TypeScript', 'Java', 'Go', 'Rust', 'C++', 'C#']
FILE_EXTENSIONS = {
    'Python': ['.py', '.pyx', '.pyi'],
    'JavaScript': ['.js', '.jsx', '.mjs'],
    'TypeScript': ['.ts', '.tsx', '.d.ts'],
    'Java': ['.java', '.kt'],
    'Go': ['.go'],
    'Rust': ['.rs'],
    'C++': ['.cpp', '.cc', '.cxx', '.h', '.hpp'],
    'C#': ['.cs']
}

SECURITY_FINDING_TYPES = [
    'SQL Injection', 'XSS', 'CSRF', 'Authentication Bypass', 'Authorization Flaw',
    'Insecure Deserialization', 'Path Traversal', 'Command Injection', 'LDAP Injection',
    'XML External Entity', 'Server-Side Request Forgery', 'Insecure Cryptography'
]

CODE_QUALITY_ISSUES = [
    'Cyclomatic Complexity', 'Code Duplication', 'Long Method', 'Large Class',
    'Dead Code', 'Unused Variables', 'Magic Numbers', 'Long Parameter List',
    'Feature Envy', 'Data Clumps', 'Primitive Obsession', 'Switch Statements'
]

SEVERITY_LEVELS = ['Critical', 'High', 'Medium', 'Low', 'Info']
PR_STATUSES = ['open', 'closed', 'merged', 'draft']
RISK_LEVELS = ['Critical', 'High', 'Medium', 'Low']

def create_sample_users(db, count=10):
    """Create sample users"""
    users = []
    for i in range(count):
        user = User(
            username=fake.user_name() + str(i),
            email=fake.email(),
            hashed_password=User.get_password_hash("password123"),
            github_id=fake.random_int(min=1000, max=999999),
            login=fake.user_name() + str(i),
            type="user"
        )
        db.add(user)
        users.append(user)
    
    db.commit()
    return users

def create_sample_repositories(db, users, count=20):
    """Create sample repositories"""
    repositories = []
    for _ in range(count):
        owner = random.choice(users)
        lang = random.choice(PROGRAMMING_LANGUAGES)
        repo_name = f"{fake.word()}-{lang.lower()}-{fake.word()}"
        
        repo = Repository(
            name=repo_name,
            full_name=f"{owner.username}/{repo_name}",
            owner_id=owner.id,
            default_branch="development",
            is_private=fake.boolean(chance_of_getting_true=30),
            description=fake.text(max_nb_chars=200),
            github_id=fake.random_int(min=100000, max=9999999),
            url=f"https://github.com/{owner.username}/{repo_name}",
            created_at=fake.date_time_between(start_date='-2y', end_date='now')
        )
        db.add(repo)
        repositories.append(repo)
    
    db.commit()
    return repositories

def create_sample_branches(db, repositories, count_per_repo=5):
    """Create sample branches for repositories"""
    branches = []
    for repo in repositories:
        # Always create development branch
        development_branch = Branch(
            name="development",
            repository_id=repo.id,
            last_commit_sha=fake.sha1(),
            last_pushed_at=fake.date_time_between(start_date=repo.created_at, end_date='now')
        )
        db.add(development_branch)
        branches.append(development_branch)
        
        # Create feature branches
        for _ in range(random.randint(2, count_per_repo)):
            branch_name = f"feature/{fake.word()}-{fake.word()}"
            branch = Branch(
                name=branch_name,
                repository_id=repo.id,
                last_commit_sha=fake.sha1(),
                last_pushed_at=fake.date_time_between(start_date=repo.created_at, end_date='now')
            )
            db.add(branch)
            branches.append(branch)
    
    db.commit()
    return branches

def create_sample_pull_requests(db, repositories, users, count=100):
    """Create sample pull requests with realistic data"""
    pull_requests = []
    
    for _ in range(count):
        repo = random.choice(repositories)
        author = random.choice(users)
        
        # Generate realistic PR data
        created_at = fake.date_time_between(start_date='-6m', end_date='now')
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
            github_author=author.username,
            merge_commit_sha=fake.sha1() if status == 'merged' else None,
            additions=additions,
            deletions=deletions,
            changed_files=changed_files,
            review_comments=random.randint(0, 25),
            comments=random.randint(0, 10),
            labels=json.dumps(random.sample(['bug', 'feature', 'enhancement', 'documentation', 'refactor'], k=random.randint(0, 3))),
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
            # reviewers field will use server default
            repository_id=repo.id,
            author_id=author.id,
            created_at=created_at
        )
        
        db.add(pr)
        pull_requests.append(pr)
    
    db.commit()
    return pull_requests

def create_sample_pr_files(db, pull_requests):
    """Create sample PR files"""
    pr_files = []
    
    for pr in pull_requests:
        # Determine language based on repository
        lang = random.choice(PROGRAMMING_LANGUAGES)
        extensions = FILE_EXTENSIONS[lang]
        
        # Create 1-10 files per PR
        for _ in range(random.randint(1, min(10, pr.changed_files))):
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
    return pr_files

def create_sample_security_findings(db, pull_requests, pr_files):
    """Create sample security findings"""
    security_findings = []
    
    for pr in pull_requests:
        # 30% chance of having security findings
        if random.random() < 0.3:
            pr_file_subset = [f for f in pr_files if f.pull_request_id == pr.id]
            if not pr_file_subset:
                continue
                
            # Create 1-5 security findings per PR
            for _ in range(random.randint(1, 5)):
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
    return security_findings

def create_sample_code_quality_issues(db, pull_requests, pr_files):
    """Create sample code quality issues"""
    quality_issues = []
    
    for pr in pull_requests:
        # 60% chance of having code quality issues
        if random.random() < 0.6:
            pr_file_subset = [f for f in pr_files if f.pull_request_id == pr.id]
            if not pr_file_subset:
                continue
                
            # Create 1-8 quality issues per PR
            for _ in range(random.randint(1, 8)):
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
    return quality_issues

def create_sample_comments_and_reviews(db, pull_requests, users):
    """Create sample PR comments and reviews"""
    comments = []
    reviews = []
    
    for pr in pull_requests:
        # 70% chance of having comments
        if random.random() < 0.7:
            # Create 1-5 comments per PR
            for _ in range(random.randint(1, 5)):
                commenter = random.choice(users)
                comment = PRComment(
                    content=fake.text(max_nb_chars=300),
                    line_number=random.randint(1, 100) if random.random() < 0.5 else None,
                    pull_request_id=pr.id,
                    user_id=commenter.id,
                    created_at=fake.date_time_between(start_date=pr.created_at, end_date='now')
                )
                db.add(comment)
                comments.append(comment)
        
        # 50% chance of having reviews
        if random.random() < 0.5:
            reviewer = random.choice(users)
            review = PullRequestReview(
                state=random.choice(['approved', 'changes_requested', 'commented']),
                body=fake.text(max_nb_chars=500),
                pull_request_id=pr.id,
                reviewer_id=reviewer.id,
                submitted_at=fake.date_time_between(start_date=pr.created_at, end_date='now')
            )
            db.add(review)
            reviews.append(review)
    
    db.commit()
    return comments, reviews

def main():
    """Generate all sample data"""
    print("🚀 Starting sample data generation...")
    
    # Create database tables
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        # Clear existing data (optional)
        print("🧹 Clearing existing data...")
        db.query(SecurityFinding).delete()
        db.query(CodeQualityIssue).delete()
        db.query(PRComment).delete()
        db.query(PullRequestReview).delete()
        db.query(PRFile).delete()
        db.query(PullRequest).delete()
        db.query(Branch).delete()
        db.query(Repository).delete()
        db.query(User).delete()
        db.commit()
        
        # Generate sample data
        print("👥 Creating sample users...")
        users = create_sample_users(db, count=15)
        
        print("📁 Creating sample repositories...")
        repositories = create_sample_repositories(db, users, count=25)
        
        print("🌿 Creating sample branches...")
        branches = create_sample_branches(db, repositories)
        
        print("🔄 Creating sample pull requests...")
        pull_requests = create_sample_pull_requests(db, repositories, users, count=150)
        
        print("📄 Creating sample PR files...")
        pr_files = create_sample_pr_files(db, pull_requests)
        
        print("🔒 Creating sample security findings...")
        security_findings = create_sample_security_findings(db, pull_requests, pr_files)
        
        print("⚡ Creating sample code quality issues...")
        quality_issues = create_sample_code_quality_issues(db, pull_requests, pr_files)
        
        print("💬 Creating sample comments and reviews...")
        comments, reviews = create_sample_comments_and_reviews(db, pull_requests, users)
        
        print("✅ Sample data generation completed!")
        print("Generated:")
        print(f"  - {len(users)} users")
        print(f"  - {len(repositories)} repositories")
        print(f"  - {len(branches)} branches")
        print(f"  - {len(pull_requests)} pull requests")
        print(f"  - {len(pr_files)} PR files")
        print(f"  - {len(security_findings)} security findings")
        print(f"  - {len(quality_issues)} code quality issues")
        print(f"  - {len(comments)} comments")
        print(f"  - {len(reviews)} reviews")
        
    except Exception as e:
        print(f"❌ Error generating sample data: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()
