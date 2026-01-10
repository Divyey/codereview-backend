from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Body, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from ..core.config import settings
from ..core.database import get_db
from ..models.user import User
from ..models.pull_request import PullRequest
from ..models.pr_file import PRFile
from ..models.repository import Repository
from ..models.pull_request_analysis_history import PullRequestAnalysisHistory
from ..schemas.pull_request import (
    PullRequestRead as PullRequestSchema,
    PullRequestCreate,
    PullRequestUpdate,
    PullRequestAnalysis,
    GithubImportRequest
)
from ..services.github_service import GitHubService
from ..services.ai_service import AIService
from .auth import get_current_user
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class PullRequestListResponse(BaseModel):
    id: int
    number: int
    title: str
    description: Optional[str] = None
    branch: str
    base_branch: Optional[str] = None
    status: Optional[str] = "open"
    github_id: Optional[int] = None
    github_url: Optional[str] = None
    github_created_at: Optional[datetime] = None
    github_updated_at: Optional[datetime] = None
    github_closed_at: Optional[datetime] = None
    github_merged_at: Optional[datetime] = None
    github_author: Optional[str] = None
    ai_score: Optional[float] = None
    risk_level: Optional[str] = None
    repository_id: int
    author_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

from app.models.code_quality_issue import CodeQualityIssue as CodeQualityIssueModel
from app.schemas.code_quality_issue import CodeQualityIssue
from app.schemas.pr_file import PRFileRead as PRFileSchema

router = APIRouter()

def format_reviewed_by(reviewers):
    names = []
    for r in reviewers or []:
        if r.get("type") == "AI":
            model = r.get("model", "AI")
            names.append(f"AI ({model})")
        elif r.get("type") == "Human":
            names.append(r.get("name"))
    return "Reviewed by: " + ", ".join(names) if names else "No review"

async def analyze_pr_background(pr_id: int, commit_sha: str, db: Session):
    """Background task to analyze PR with AI and store in history"""
    pr = db.query(PullRequest).filter(PullRequest.id == pr_id).first()
    if not pr:
        return

    ai_service = AIService()
    ai_model = getattr(ai_service, "model_name", "gpt-4o")
    files_data = []
    for file in pr.files:
        files_data.append({
            "filename": file.filename,
            "additions": file.additions,
            "deletions": file.deletions,
            "content": file.content
        })

    ai_review_started_at = datetime.utcnow()
    analysis = await ai_service.analyze_code(files_data)
    ai_review_completed_at = datetime.utcnow()
    ai_review_time_seconds = (ai_review_completed_at - ai_review_started_at).total_seconds()

    pr.ai_review_started_at = ai_review_started_at
    pr.ai_review_completed_at = ai_review_completed_at
    pr.ai_review_time_seconds = ai_review_time_seconds

    pr.ai_score = analysis["ai_score"]
    pr.risk_level = analysis["risk_level"]
    pr.issue_count = analysis["issue_count"]
    pr.warning_count = analysis["warning_count"]
    pr.ai_analysis = analysis

    reviewers = pr.reviewers or []
    if not any(r.get("type") == "AI" for r in reviewers):
        reviewers.append({"type": "AI", "model": ai_model})
    pr.reviewers = reviewers
    if not any(r.get("type") == "Human" for r in reviewers):
        pr.review_status = "AI only"
    else:
        pr.review_status = "AI + Human"
    db.commit()

    analysis_history = PullRequestAnalysisHistory(
        pull_request_id=pr.id,
        commit_sha=commit_sha,
        analyzed_at=datetime.utcnow(),
        ai_score=analysis["ai_score"],
        risk_level=analysis["risk_level"],
        issues=analysis.get("issues", []),
        warnings=analysis.get("warnings", []),
        recommendations=analysis.get("recommendations", []),
        summary=analysis.get("summary", ""),
        reviewer=f"AI ({ai_model})"
    )
    db.add(analysis_history)
    db.commit()

@router.post("/", response_model=PullRequestSchema)
async def create_pull_request(
    pr_data: PullRequestCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new pull request and analyze it"""
    repository = db.query(Repository).filter(Repository.id == pr_data.repository_id).first()
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    pr = PullRequest(
        number=pr_data.number,
        title=pr_data.title,
        description=pr_data.description,
        branch=pr_data.branch,
        status=pr_data.status,
        github_url=pr_data.github_url,
        github_author=pr_data.github_author,
        repository_id=pr_data.repository_id,
        author_id=current_user.id,
        files_changed=len(pr_data.files) if pr_data.files else 0,
        lines_added=sum(f.additions for f in pr_data.files) if pr_data.files else 0,
        lines_deleted=sum(f.deletions for f in pr_data.files) if pr_data.files else 0,
        review_status="AI only",
        reviewers=[{"type": "AI", "model": "gpt-4o"}]
    )
    db.add(pr)
    db.commit()
    db.refresh(pr)
    
    if pr_data.files:
        ai_service = AIService()
        for file_data in pr_data.files:
            language = ai_service.get_language_from_filename(file_data.filename)
            pr_file = PRFile(
                filename=file_data.filename,
                status=file_data.status,
                additions=file_data.additions,
                deletions=file_data.deletions,
                patch=file_data.patch,
                content=file_data.content,
                language=language,
                pull_request_id=pr.id
            )
            db.add(pr_file)
        db.commit()
    
    background_tasks.add_task(analyze_pr_background, pr.id, "", db)
    return pr

@router.post("/from-github")
async def create_pr_from_github(
    payload: GithubImportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create PR by fetching from GitHub URL, allow multiple analyses per PR (history)"""
    github_url = payload.github_url
    github_token = payload.github_token
    token = github_token or current_user.github_token or settings.GITHUB_TOKEN
    github_service = GitHubService(token)
    url_parts = github_service.parse_github_url(github_url)
    if not url_parts:
        raise HTTPException(status_code=400, detail="Invalid GitHub URL")
    owner = url_parts["owner"]
    repo_name = url_parts["repo"]
    pr_number = url_parts["pr_number"]
    pr_data = await github_service.get_pull_request(owner, repo_name, pr_number)
    if not pr_data:
        raise HTTPException(status_code=404, detail="Pull request not found or access denied")
    repo_full_name = f"{owner}/{repo_name}"
    repository = db.query(Repository).filter(Repository.full_name == repo_full_name).first()
    if not repository:
        repo_info = await github_service.get_repository(owner, repo_name)
        if not repo_info:
            raise HTTPException(status_code=404, detail="Repository not found")
        repository = Repository(
            name=repo_name,
            full_name=repo_full_name,
            description=repo_info.get("description"),
            github_id=repo_info["id"],
            url=repo_info["html_url"],
            default_branch=repo_info["default_branch"],
            is_private=repo_info["private"],
            owner_id=current_user.id
        )
        db.add(repository)
        db.commit()
        db.refresh(repository)
    pr = db.query(PullRequest).filter(
        PullRequest.repository_id == repository.id,
        PullRequest.number == pr_number
    ).first()
    if not pr:
        pr = PullRequest(
            number=pr_number,
            title=pr_data["title"],
            description=pr_data.get("body"),
            branch=pr_data["head"]["ref"],
            status="merged" if pr_data["merged"] else ("closed" if pr_data["closed_at"] else "open"),
            github_id=pr_data["id"],
            github_url=pr_data["html_url"],
            github_author=pr_data.get("user", {}).get("login"),
            repository_id=repository.id,
            author_id=current_user.id,
            files_changed=pr_data.get("changed_files", 0),
            lines_added=pr_data.get("additions", 0),
            lines_deleted=pr_data.get("deletions", 0),
            review_status="AI only",
            reviewers=[{"type": "AI", "model": "gpt-4o"}]
        )
        db.add(pr)
        db.commit()
        db.refresh(pr)
    commit_sha = pr_data["head"]["sha"]
    files_data = await github_service.get_pull_request_files(owner, repo_name, pr_number)
    ai_service = AIService()
    db.query(PRFile).filter(PRFile.pull_request_id == pr.id).delete()
    for file_data in files_data:
        content = await github_service.get_file_content(
            owner, repo_name, file_data["filename"], pr_data["head"]["sha"]
        )
        language = ai_service.get_language_from_filename(file_data["filename"])
        pr_file = PRFile(
            filename=file_data["filename"],
            status=file_data["status"],
            additions=file_data.get("additions", 0),
            deletions=file_data.get("deletions", 0),
            patch=file_data.get("patch"),
            content=content,
            language=language,
            pull_request_id=pr.id
        )
        db.add(pr_file)
    db.commit()
    background_tasks.add_task(analyze_pr_background, pr.id, commit_sha, db)
    return {"message": "Pull request imported and analysis started", "pr_id": pr.id, "commit_sha": commit_sha}

@router.post("/{pr_id}/review/complete")
def mark_review_complete(
    pr_id: int,
    user_review_time_hours: float = Body(..., embed=True, description="Manual review time in hours"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    pr = db.query(PullRequest).filter(PullRequest.id == pr_id).first()
    if not pr:
        raise HTTPException(status_code=404, detail="Pull request not found")
    reviewers = pr.reviewers or []
    if not any(r.get("type") == "AI" for r in reviewers):
        reviewers.append({"type": "AI", "model": "gpt-4o"})
    if not any(r.get("type") == "Human" and r.get("name") == current_user.username for r in reviewers):
        reviewers.append({"type": "Human", "name": current_user.username})
    pr.reviewers = reviewers
    if any(r.get("type") == "AI" for r in reviewers) and any(r.get("type") == "Human" for r in reviewers):
        pr.review_status = "AI + Human"
    elif any(r.get("type") == "Human" for r in reviewers):
        pr.review_status = "Human only"
    else:
        pr.review_status = "AI only"
    pr.user_review_time_minutes = user_review_time_hours * 60
    db.commit()
    return {
        "message": "Review marked as complete",
        "review_status": pr.review_status,
        "reviewed_by": format_reviewed_by(pr.reviewers),
        "user_review_time_hours": user_review_time_hours
    }

@router.get("/test")
def test_pull_requests(
    current_user: User = Depends(get_current_user)
):
    """Simple test endpoint"""
    return {"message": "Test successful", "user_id": current_user.id}

@router.get("/", response_model=List[PullRequestListResponse])
def get_pull_requests(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    risk_level: Optional[str] = None,
    repository_id: Optional[int] = Query(None),
    branch: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get user's pull requests with optional filtering"""
    try:
        # Get user's repository IDs to ensure they can only access their own PRs
        user_repo_ids = [repo.id for repo in current_user.repositories]
        
        # Base query: filter by repositories owned by the user
        query = db.query(PullRequest).filter(PullRequest.repository_id.in_(user_repo_ids))
        
        # Apply filters
        if repository_id is not None:
            if repository_id not in user_repo_ids:
                raise HTTPException(status_code=404, detail="Repository not found")
            query = query.filter(PullRequest.repository_id == repository_id)
        
        if status:
            query = query.filter(PullRequest.status == status)
        
        if risk_level:
            query = query.filter(PullRequest.risk_level == risk_level)
        
        if branch:
            query = query.filter(PullRequest.branch == branch)
        
        return query.order_by(PullRequest.github_created_at.desc()).offset(skip).limit(limit).all()
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"Error in get_pull_requests: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/{pr_id}", response_model=PullRequestSchema)
def get_pull_request(
    pr_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    pr = db.query(PullRequest).filter(
        PullRequest.id == pr_id
    ).first()
    if not pr:
        raise HTTPException(status_code=404, detail="Pull request not found")
    pr_dict = pr.__dict__.copy()
    pr_dict["reviewed_by"] = format_reviewed_by(pr.reviewers)
    return pr_dict

@router.put("/{pr_id}", response_model=PullRequestSchema)
def update_pull_request(
    pr_id: int,
    pr_update: PullRequestUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update pull request"""
    pr = db.query(PullRequest).filter(
        PullRequest.id == pr_id,
        PullRequest.author_id == current_user.id
    ).first()
    if not pr:
        raise HTTPException(status_code=404, detail="Pull request not found")
    for field, value in pr_update.dict(exclude_unset=True).items():
        setattr(pr, field, value)
    db.commit()
    db.refresh(pr)
    return pr

@router.delete("/{pr_id}")
def delete_pull_request(
    pr_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete pull request"""
    pr = db.query(PullRequest).filter(
        PullRequest.id == pr_id,
        PullRequest.author_id == current_user.id
    ).first()
    if not pr:
        raise HTTPException(status_code=404, detail="Pull request not found")
    db.delete(pr)
    db.commit()
    return {"message": "Pull request deleted successfully"}

@router.get("/{pr_id}/analysis", response_model=PullRequestAnalysis)
def get_pr_analysis(
    pr_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    pr = db.query(PullRequest).filter(
        PullRequest.id == pr_id,
        PullRequest.author_id == current_user.id
    ).first()
    if not pr:
        raise HTTPException(status_code=404, detail="Pull request not found")
    if not pr.ai_analysis:
        raise HTTPException(status_code=404, detail="Analysis not yet available")
    return PullRequestAnalysis(
        pr_id=pr.id,
        ai_score=pr.ai_score,
        risk_level=pr.risk_level,
        issues=pr.ai_analysis.get("issues", []),
        warnings=pr.ai_analysis.get("warnings", []),
        recommendations=pr.ai_analysis.get("recommendations", []),
        summary=pr.ai_analysis.get("summary", ""),
        reviewed_by=format_reviewed_by(pr.reviewers)
    )

@router.get("/{pr_id}/analysis/history")
def get_pr_analysis_history(
    pr_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    pr = db.query(PullRequest).filter(
        PullRequest.id == pr_id,
        PullRequest.author_id == current_user.id
    ).first()
    if not pr:
        raise HTTPException(status_code=404, detail="Pull request not found")
    reviewed_by = format_reviewed_by(pr.reviewers)
    return [
        {
            "analysis_id": h.id,
            "commit_sha": h.commit_sha,
            "analyzed_at": h.analyzed_at,
            "ai_score": h.ai_score,
            "risk_level": h.risk_level,
            "issues": h.issues,
            "warnings": h.warnings,
            "recommendations": h.recommendations,
            "summary": h.summary,
            "reviewer": h.reviewer,
            "reviewed_by": reviewed_by
        }
        for h in pr.analysis_history
    ]

@router.get("/pull_requests/{pr_id}/issues", response_model=List[CodeQualityIssue])
def get_pr_issues(
    pr_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    pr = db.query(PullRequest).filter(PullRequest.id == pr_id).first()
    if not pr or pr.repository.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="PR not found")
    issues = db.query(CodeQualityIssueModel).filter(CodeQualityIssueModel.pull_request_id == pr_id).all()
    return issues

@router.get("/issues", response_model=List[CodeQualityIssue])
def list_issues(
    repo_id: Optional[int] = Query(None),
    type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(CodeQualityIssueModel)
    # Only allow filtering by user's repos
    user_repo_ids = [repo.id for repo in current_user.repositories]
    query = query.filter(CodeQualityIssueModel.repo_id.in_(user_repo_ids))
    if repo_id is not None:
        if repo_id not in user_repo_ids:
            raise HTTPException(status_code=404, detail="Repository not found")
        query = query.filter(CodeQualityIssueModel.repo_id == repo_id)
    if type:
        query = query.filter(CodeQualityIssueModel.type == type)
    if severity:
        query = query.filter(CodeQualityIssueModel.severity == severity)
    if status:
        query = query.filter(CodeQualityIssueModel.status == status)
    return query.all()

# Update issue status
@router.patch("/issues/{issue_id}/status", response_model=CodeQualityIssue)
def update_issue_status(
    issue_id: int,
    status: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    issue = db.query(CodeQualityIssueModel).filter(CodeQualityIssueModel.id == issue_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    # Ensure the issue's repo belongs to the user
    repo = db.query(Repository).filter(Repository.id == issue.repo_id).first()
    if not repo or repo.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed")
    issue.status = status
    db.commit()
    db.refresh(issue)
    return issue

@router.get("/pull_requests", response_model=List[PullRequestSchema])
def list_pull_requests(
    repository_id: Optional[int] = Query(None),
    branch: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user_repo_ids = [repo.id for repo in current_user.repositories]
    query = db.query(PullRequest).filter(PullRequest.repository_id.in_(user_repo_ids))
    if repository_id is not None:
        if repository_id not in user_repo_ids:
            raise HTTPException(status_code=404, detail="Repository not found")
        query = query.filter(PullRequest.repository_id == repository_id)
    if branch:
        query = query.filter(PullRequest.branch == branch)
    return query.all()

# Get all issues for a PR
@router.get("/pull_requests/{pr_id}/issues", response_model=List[CodeQualityIssue])
def get_pr_issues(
    pr_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    pr = db.query(PullRequest).filter(PullRequest.id == pr_id).first()
    if not pr or pr.repository.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="PR not found")
    issues = db.query(CodeQualityIssueModel).filter(CodeQualityIssueModel.pull_request_id == pr_id).all()
    return issues

# List all files for a PR
@router.get("/{pr_id}/files", response_model=List[PRFileSchema])
def list_pr_files(
    pr_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    pr = db.query(PullRequest).filter(PullRequest.id == pr_id).first()
    if not pr or pr.repository.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="PR not found")
    files = db.query(PRFile).filter(PRFile.pull_request_id == pr_id).all()
    return files


# Get a single file for a PR
@router.get("/pull_requests/{pr_id}/files/{file_id}", response_model=PRFileSchema)
def get_pr_file(
    pr_id: int,
    file_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    pr = db.query(PullRequest).filter(PullRequest.id == pr_id).first()
    if not pr or pr.repository.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="PR not found")
    pr_file = db.query(PRFile).filter(
        PRFile.pull_request_id == pr_id,
        PRFile.id == file_id
    ).first()
    if not pr_file:
        raise HTTPException(status_code=404, detail="File not found")
    return pr_file


# Get code diff for a file in a PR
@router.get("/pull_requests/{pr_id}/files/{file_id}/diff")
def get_file_diff(
    pr_id: int,
    file_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    pr = db.query(PullRequest).filter(PullRequest.id == pr_id).first()
    if not pr or pr.repository.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="PR not found")
    pr_file = db.query(PRFile).filter(
        PRFile.pull_request_id == pr_id,
        PRFile.id == file_id
    ).first()
    if not pr_file:
        raise HTTPException(status_code=404, detail="File not found")
    return {"filename": pr_file.filename, "patch": pr_file.patch}


# Get file content for a file in a PR
@router.get("/pull_requests/{pr_id}/files/{file_id}/content")
def get_file_content(
    pr_id: int,
    file_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    pr = db.query(PullRequest).filter(PullRequest.id == pr_id).first()
    if not pr or pr.repository.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="PR not found")
    pr_file = db.query(PRFile).filter(
        PRFile.pull_request_id == pr_id,
        PRFile.id == file_id
    ).first()
    if not pr_file:
        raise HTTPException(status_code=404, detail="File not found")
    return {"filename": pr_file.filename, "content": pr_file.content}
