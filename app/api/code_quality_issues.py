from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.database import get_db
from app.models.code_quality_issue import CodeQualityIssue
from app.schemas.code_quality_issue import (
    CodeQualityIssue as CodeQualityIssueSchema,
    CodeQualityIssueCreate,
    CodeQualityIssueUpdate,
)
from app.api.auth import get_current_user
from app.models.user import User

router = APIRouter()

@router.get("/", response_model=List[CodeQualityIssueSchema])
def list_code_quality_issues(
    repo_id: Optional[int] = Query(None),
    type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(CodeQualityIssue)
    # Only allow issues from repos owned by the current user
    user_repo_ids = [repo.id for repo in current_user.repositories]
    query = query.filter(CodeQualityIssue.repo_id.in_(user_repo_ids))
    if repo_id:
        if repo_id not in user_repo_ids:
            raise HTTPException(status_code=404, detail="Repository not found")
        query = query.filter(CodeQualityIssue.repo_id == repo_id)
    if type:
        query = query.filter(CodeQualityIssue.type == type)
    return query.all()


@router.get("/repo/{repo_id}/stats")
def repo_code_quality_stats(
    repo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    repo = db.query(Repository).filter(
        Repository.id == repo_id,
        Repository.owner_id == current_user.id
    ).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    stats = {
        "docstring_absent": db.query(CodeQualityIssue).filter_by(repo_id=repo_id, type="docstring_absent").count(),
        "complex_function": db.query(CodeQualityIssue).filter_by(repo_id=repo_id, type="complex_function").count(),
        "antipattern": db.query(CodeQualityIssue).filter_by(repo_id=repo_id, type="antipattern").count(),
        "dead_code": db.query(CodeQualityIssue).filter_by(repo_id=repo_id, type="dead_code").count(),
        "duplicate_code": db.query(CodeQualityIssue).filter_by(repo_id=repo_id, type="duplicate_code").count(),
    }
    return stats


@router.get("/{issue_id}", response_model=CodeQualityIssueSchema)
def get_code_quality_issue(
    issue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    issue = db.query(CodeQualityIssue).filter_by(id=issue_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    # Ensure the issue's repo belongs to the user
    repo = db.query(Repository).filter(Repository.id == issue.repo_id).first()
    if not repo or repo.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed")
    return issue

@router.post("/", response_model=CodeQualityIssueSchema)
def create_code_quality_issue(
    issue: CodeQualityIssueCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Only allow creation for user's own repos
    repo = db.query(Repository).filter(
        Repository.id == issue.repo_id,
        Repository.owner_id == current_user.id
    ).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    db_issue = CodeQualityIssue(**issue.dict())
    db.add(db_issue)
    db.commit()
    db.refresh(db_issue)
    return db_issue


@router.patch("/{issue_id}", response_model=CodeQualityIssueSchema)
def update_code_quality_issue(
    issue_id: int,
    update: CodeQualityIssueUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_issue = db.query(CodeQualityIssue).filter_by(id=issue_id).first()
    if not db_issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    # Ensure the issue's repo belongs to the user
    repo = db.query(Repository).filter(Repository.id == db_issue.repo_id).first()
    if not repo or repo.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed")
    for key, value in update.dict(exclude_unset=True).items():
        setattr(db_issue, key, value)
    db.commit()
    db.refresh(db_issue)
    return db_issue

