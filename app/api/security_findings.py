from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.database import get_db
from app.models.security_finding import SecurityFinding
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.user import User
from app.api.auth import get_current_user

router = APIRouter()

@router.get("/")
def list_security_findings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    repo_id: Optional[int] = Query(None),
    severity: Optional[str] = Query(None),
    finding_type: Optional[str] = Query(None)
):
    """List security findings for the current user's repositories"""
    # Get user's repository IDs
    user_repo_ids = [repo.id for repo in current_user.repositories]
    
    # Query security findings through pull requests -> repositories
    query = db.query(SecurityFinding).join(
        PullRequest, SecurityFinding.pull_request_id == PullRequest.id
    ).join(
        Repository, PullRequest.repository_id == Repository.id
    ).filter(
        Repository.owner_id == current_user.id
    )
    
    # Apply filters
    if repo_id:
        if repo_id not in user_repo_ids:
            raise HTTPException(status_code=404, detail="Repository not found")
        query = query.filter(PullRequest.repository_id == repo_id)
    
    if severity:
        query = query.filter(SecurityFinding.severity == severity)
    
    if finding_type:
        query = query.filter(SecurityFinding.type == finding_type)
    
    return query.all()

@router.get("/{finding_id}")
def get_security_finding(
    finding_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific security finding"""
    finding = db.query(SecurityFinding).join(
        PullRequest, SecurityFinding.pull_request_id == PullRequest.id
    ).join(
        Repository, PullRequest.repository_id == Repository.id
    ).filter(
        SecurityFinding.id == finding_id,
        Repository.owner_id == current_user.id
    ).first()
    
    if not finding:
        raise HTTPException(status_code=404, detail="Security finding not found")
    
    return finding

@router.get("/stats/summary")
def get_security_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    repo_id: Optional[int] = Query(None)
):
    """Get security statistics for user's repositories"""
    user_repo_ids = [repo.id for repo in current_user.repositories]
    
    query = db.query(SecurityFinding).join(
        PullRequest, SecurityFinding.pull_request_id == PullRequest.id
    ).join(
        Repository, PullRequest.repository_id == Repository.id
    ).filter(
        Repository.owner_id == current_user.id
    )
    
    if repo_id:
        if repo_id not in user_repo_ids:
            raise HTTPException(status_code=404, detail="Repository not found")
        query = query.filter(PullRequest.repository_id == repo_id)
    
    all_findings = query.all()
    
    stats = {
        "total": len(all_findings),
        "critical": len([f for f in all_findings if f.severity == 'critical']),
        "high": len([f for f in all_findings if f.severity == 'high']),
        "medium": len([f for f in all_findings if f.severity == 'medium']),
        "low": len([f for f in all_findings if f.severity == 'low']),
        "by_type": {}
    }
    
    for finding in all_findings:
        finding_type = finding.type or 'unknown'
        stats["by_type"][finding_type] = stats["by_type"].get(finding_type, 0) + 1
    
    return stats
