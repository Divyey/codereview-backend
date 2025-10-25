"""
Optimized Dashboard API with better performance and real-world usage patterns
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import func, desc, and_, or_, case
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import json

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.models.security_finding import SecurityFinding
from app.models.code_quality_issue import CodeQualityIssue
from app.models.pr_file import PRFile

router = APIRouter()

@router.get("/dashboard/overview")
def get_dashboard_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    days: int = Query(30, description="Number of days to look back")
):
    """
    Get comprehensive dashboard overview with optimized queries
    """
    # Calculate date range
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # Get user's repository IDs for filtering
    user_repo_ids = [repo.id for repo in current_user.repositories]
    
    if not user_repo_ids:
        return {
            "summary": {
                "total_repositories": 0,
                "total_pull_requests": 0,
                "active_pull_requests": 0,
                "merged_pull_requests": 0,
                "security_findings": 0,
                "code_quality_issues": 0
            },
            "trends": {},
            "top_repositories": [],
            "recent_activity": []
        }
    
    # Optimized query for PR statistics
    pr_stats = db.query(
        func.count(PullRequest.id).label('total_prs'),
        func.count(case((PullRequest.status == 'open', 1))).label('active_prs'),
        func.count(case((PullRequest.status == 'merged', 1))).label('merged_prs'),
        func.avg(PullRequest.ai_score).label('avg_ai_score'),
        func.sum(PullRequest.lines_added).label('total_lines_added'),
        func.sum(PullRequest.lines_deleted).label('total_lines_deleted')
    ).filter(
        PullRequest.repository_id.in_(user_repo_ids),
        PullRequest.created_at >= start_date
    ).first()
    
    # Security findings count
    security_count = db.query(func.count(SecurityFinding.id)).join(
        PullRequest, SecurityFinding.pull_request_id == PullRequest.id
    ).filter(
        PullRequest.repository_id.in_(user_repo_ids),
        PullRequest.created_at >= start_date
    ).scalar()
    
    # Code quality issues count
    quality_count = db.query(func.count(CodeQualityIssue.id)).join(
        PullRequest, CodeQualityIssue.pull_request_id == PullRequest.id
    ).filter(
        PullRequest.repository_id.in_(user_repo_ids),
        PullRequest.created_at >= start_date
    ).scalar()
    
    # Top repositories by activity
    top_repos = db.query(
        Repository.name,
        Repository.full_name,
        func.count(PullRequest.id).label('pr_count'),
        func.avg(PullRequest.ai_score).label('avg_score')
    ).join(
        PullRequest, Repository.id == PullRequest.repository_id
    ).filter(
        Repository.owner_id == current_user.id,
        PullRequest.created_at >= start_date
    ).group_by(
        Repository.id, Repository.name, Repository.full_name
    ).order_by(
        desc('pr_count')
    ).limit(5).all()
    
    # Recent activity (last 10 PRs)
    recent_prs = db.query(PullRequest).options(
        joinedload(PullRequest.repository),
        joinedload(PullRequest.author)
    ).filter(
        PullRequest.repository_id.in_(user_repo_ids)
    ).order_by(
        desc(PullRequest.created_at)
    ).limit(10).all()
    
    # Daily trends for the past week
    daily_trends = db.query(
        func.date(PullRequest.created_at).label('date'),
        func.count(PullRequest.id).label('pr_count'),
        func.avg(PullRequest.ai_score).label('avg_score')
    ).filter(
        PullRequest.repository_id.in_(user_repo_ids),
        PullRequest.created_at >= start_date
    ).group_by(
        func.date(PullRequest.created_at)
    ).order_by('date').all()
    
    return {
        "summary": {
            "total_repositories": len(user_repo_ids),
            "total_pull_requests": pr_stats.total_prs or 0,
            "active_pull_requests": pr_stats.active_prs or 0,
            "merged_pull_requests": pr_stats.merged_prs or 0,
            "security_findings": security_count or 0,
            "code_quality_issues": quality_count or 0,
            "avg_ai_score": round(float(pr_stats.avg_ai_score or 0), 2),
            "total_lines_changed": (pr_stats.total_lines_added or 0) + (pr_stats.total_lines_deleted or 0)
        },
        "trends": {
            "daily": [
                {
                    "date": trend.date.isoformat(),
                    "pr_count": trend.pr_count,
                    "avg_score": round(float(trend.avg_score or 0), 2)
                }
                for trend in daily_trends
            ]
        },
        "top_repositories": [
            {
                "name": repo.name,
                "full_name": repo.full_name,
                "pr_count": repo.pr_count,
                "avg_score": round(float(repo.avg_score or 0), 2)
            }
            for repo in top_repos
        ],
        "recent_activity": [
            {
                "id": pr.id,
                "title": pr.title,
                "repository": pr.repository.name,
                "author": pr.author.username,
                "status": pr.status,
                "ai_score": pr.ai_score,
                "risk_level": pr.risk_level,
                "created_at": pr.created_at.isoformat() if pr.created_at else None
            }
            for pr in recent_prs
        ]
    }

@router.get("/dashboard/security-insights")
def get_security_insights(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    days: int = Query(30, description="Number of days to look back")
):
    """
    Get detailed security insights and trends
    """
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    user_repo_ids = [repo.id for repo in current_user.repositories]
    
    if not user_repo_ids:
        return {"findings_by_severity": {}, "findings_by_type": {}, "trends": []}
    
    # Security findings by severity
    severity_stats = db.query(
        SecurityFinding.severity,
        func.count(SecurityFinding.id).label('count')
    ).join(
        PullRequest, SecurityFinding.pull_request_id == PullRequest.id
    ).filter(
        PullRequest.repository_id.in_(user_repo_ids),
        PullRequest.created_at >= start_date
    ).group_by(SecurityFinding.severity).all()
    
    # Security findings by type
    type_stats = db.query(
        SecurityFinding.issue_type,
        func.count(SecurityFinding.id).label('count'),
        SecurityFinding.severity
    ).join(
        PullRequest, SecurityFinding.pull_request_id == PullRequest.id
    ).filter(
        PullRequest.repository_id.in_(user_repo_ids),
        PullRequest.created_at >= start_date
    ).group_by(
        SecurityFinding.issue_type, SecurityFinding.severity
    ).order_by(desc('count')).limit(10).all()
    
    # Daily security findings trend
    daily_security = db.query(
        func.date(PullRequest.created_at).label('date'),
        func.count(SecurityFinding.id).label('findings_count')
    ).join(
        SecurityFinding, PullRequest.id == SecurityFinding.pull_request_id
    ).filter(
        PullRequest.repository_id.in_(user_repo_ids),
        PullRequest.created_at >= start_date
    ).group_by(
        func.date(PullRequest.created_at)
    ).order_by('date').all()
    
    return {
        "findings_by_severity": {
            finding.severity: finding.count 
            for finding in severity_stats
        },
        "findings_by_type": [
            {
                "type": finding.issue_type,
                "count": finding.count,
                "severity": finding.severity
            }
            for finding in type_stats
        ],
        "trends": [
            {
                "date": trend.date.isoformat(),
                "findings_count": trend.findings_count
            }
            for trend in daily_security
        ]
    }

@router.get("/dashboard/code-quality-metrics")
def get_code_quality_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    days: int = Query(30, description="Number of days to look back")
):
    """
    Get comprehensive code quality metrics
    """
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    user_repo_ids = [repo.id for repo in current_user.repositories]
    
    if not user_repo_ids:
        return {"issues_by_type": {}, "issues_by_severity": {}, "file_analysis": []}
    
    # Code quality issues by type
    type_stats = db.query(
        CodeQualityIssue.type,
        func.count(CodeQualityIssue.id).label('count')
    ).join(
        PullRequest, CodeQualityIssue.pull_request_id == PullRequest.id
    ).filter(
        PullRequest.repository_id.in_(user_repo_ids),
        PullRequest.created_at >= start_date
    ).group_by(CodeQualityIssue.type).order_by(desc('count')).all()
    
    # Issues by severity
    severity_stats = db.query(
        CodeQualityIssue.severity,
        func.count(CodeQualityIssue.id).label('count')
    ).join(
        PullRequest, CodeQualityIssue.pull_request_id == PullRequest.id
    ).filter(
        PullRequest.repository_id.in_(user_repo_ids),
        PullRequest.created_at >= start_date
    ).group_by(CodeQualityIssue.severity).all()
    
    # Most problematic files
    file_analysis = db.query(
        PRFile.filename,
        PRFile.language,
        func.count(CodeQualityIssue.id).label('issue_count'),
        func.avg(func.coalesce(PRFile.additions, 0) + func.coalesce(PRFile.deletions, 0)).label('avg_changes')
    ).join(
        CodeQualityIssue, PRFile.id == CodeQualityIssue.file_id
    ).join(
        PullRequest, PRFile.pull_request_id == PullRequest.id
    ).filter(
        PullRequest.repository_id.in_(user_repo_ids),
        PullRequest.created_at >= start_date
    ).group_by(
        PRFile.filename, PRFile.language
    ).order_by(desc('issue_count')).limit(10).all()
    
    return {
        "issues_by_type": {
            issue.type: issue.count 
            for issue in type_stats
        },
        "issues_by_severity": {
            issue.severity: issue.count 
            for issue in severity_stats
        },
        "problematic_files": [
            {
                "filename": file.filename,
                "language": file.language,
                "issue_count": file.issue_count,
                "avg_changes": round(float(file.avg_changes or 0), 1)
            }
            for file in file_analysis
        ]
    }

@router.get("/dashboard/performance-metrics")
def get_performance_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    days: int = Query(30, description="Number of days to look back")
):
    """
    Get performance and efficiency metrics
    """
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    user_repo_ids = [repo.id for repo in current_user.repositories]
    
    if not user_repo_ids:
        return {"review_times": {}, "pr_metrics": {}, "efficiency": {}}
    
    # Review time metrics
    review_times = db.query(
        func.avg(PullRequest.ai_review_time_seconds).label('avg_ai_time'),
        func.avg(PullRequest.user_review_time_minutes).label('avg_user_time'),
        func.count(case((PullRequest.ai_review_completed_at.isnot(None), 1))).label('ai_reviewed'),
        func.count(case((PullRequest.user_review_time_minutes.isnot(None), 1))).label('user_reviewed')
    ).filter(
        PullRequest.repository_id.in_(user_repo_ids),
        PullRequest.created_at >= start_date
    ).first()
    
    # PR size and complexity metrics
    pr_metrics = db.query(
        func.avg(PullRequest.lines_added + PullRequest.lines_deleted).label('avg_size'),
        func.avg(PullRequest.changed_files).label('avg_files'),
        func.avg(PullRequest.commits).label('avg_commits'),
        func.count(case((PullRequest.risk_level == 'High', 1))).label('high_risk'),
        func.count(case((PullRequest.risk_level == 'Medium', 1))).label('medium_risk'),
        func.count(case((PullRequest.risk_level == 'Low', 1))).label('low_risk')
    ).filter(
        PullRequest.repository_id.in_(user_repo_ids),
        PullRequest.created_at >= start_date
    ).first()
    
    return {
        "review_times": {
            "avg_ai_review_seconds": round(float(review_times.avg_ai_time or 0), 1),
            "avg_user_review_minutes": round(float(review_times.avg_user_time or 0), 1),
            "ai_review_coverage": round((review_times.ai_reviewed or 0) / max(1, (review_times.ai_reviewed or 0) + (review_times.user_reviewed or 0)) * 100, 1)
        },
        "pr_metrics": {
            "avg_size_lines": round(float(pr_metrics.avg_size or 0), 1),
            "avg_files_changed": round(float(pr_metrics.avg_files or 0), 1),
            "avg_commits": round(float(pr_metrics.avg_commits or 0), 1)
        },
        "risk_distribution": {
            "high": pr_metrics.high_risk or 0,
            "medium": pr_metrics.medium_risk or 0,
            "low": pr_metrics.low_risk or 0
        }
    }

@router.get("/dashboard/repositories/{repo_id}/details")
def get_repository_details(
    repo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    days: int = Query(30, description="Number of days to look back")
):
    """
    Get detailed metrics for a specific repository
    """
    # Verify repository ownership
    repo = db.query(Repository).filter(
        Repository.id == repo_id,
        Repository.owner_id == current_user.id
    ).first()
    
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # Repository statistics
    repo_stats = db.query(
        func.count(PullRequest.id).label('total_prs'),
        func.count(case((PullRequest.status == 'open', 1))).label('open_prs'),
        func.count(case((PullRequest.status == 'merged', 1))).label('merged_prs'),
        func.avg(PullRequest.ai_score).label('avg_ai_score'),
        func.sum(PullRequest.lines_added).label('total_additions'),
        func.sum(PullRequest.lines_deleted).label('total_deletions')
    ).filter(
        PullRequest.repository_id == repo_id,
        PullRequest.created_at >= start_date
    ).first()
    
    # Top contributors
    contributors = db.query(
        PullRequest.github_author,
        func.count(PullRequest.id).label('pr_count'),
        func.avg(PullRequest.ai_score).label('avg_score')
    ).filter(
        PullRequest.repository_id == repo_id,
        PullRequest.created_at >= start_date,
        PullRequest.github_author.isnot(None)
    ).group_by(
        PullRequest.github_author
    ).order_by(desc('pr_count')).limit(5).all()
    
    # Language distribution (based on files)
    languages = db.query(
        PRFile.language,
        func.count(PRFile.id).label('file_count')
    ).join(
        PullRequest, PRFile.pull_request_id == PullRequest.id
    ).filter(
        PullRequest.repository_id == repo_id,
        PullRequest.created_at >= start_date,
        PRFile.language.isnot(None)
    ).group_by(PRFile.language).order_by(desc('file_count')).all()
    
    return {
        "repository": {
            "id": repo.id,
            "name": repo.name,
            "full_name": repo.full_name,
            "description": repo.description,
            "is_private": repo.is_private
        },
        "statistics": {
            "total_prs": repo_stats.total_prs or 0,
            "open_prs": repo_stats.open_prs or 0,
            "merged_prs": repo_stats.merged_prs or 0,
            "avg_ai_score": round(float(repo_stats.avg_ai_score or 0), 2),
            "total_lines_changed": (repo_stats.total_additions or 0) + (repo_stats.total_deletions or 0)
        },
        "top_contributors": [
            {
                "author": contrib.github_author,
                "pr_count": contrib.pr_count,
                "avg_score": round(float(contrib.avg_score or 0), 2)
            }
            for contrib in contributors
        ],
        "languages": [
            {
                "language": lang.language,
                "file_count": lang.file_count
            }
            for lang in languages
        ]
    }
