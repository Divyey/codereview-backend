from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Body
from sqlalchemy.orm import Session
from typing import List, Optional
from ..core.config import settings
from ..core.database import get_db
from ..models.user import User
from ..models.pull_request import PullRequest, PRFile
from ..models.repository import Repository
from ..models.pull_request_analysis_history import PullRequestAnalysisHistory
from ..schemas.pull_request import (
    GithubImportRequest,
    PullRequest as PullRequestSchema,
    PullRequestCreate,
    PullRequestUpdate,
    PullRequestAnalysis
)
from ..services.github_service import GitHubService
from ..services.ai_service import AIService
from .auth import get_current_user
from datetime import datetime
from ..models.project import Project
from sqlalchemy import or_

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

    # --- Start timing the OpenAI review ---
    ai_review_started_at = datetime.utcnow()
    analysis = await ai_service.analyze_code(files_data)
    ai_review_completed_at = datetime.utcnow()
    ai_review_time_seconds = (ai_review_completed_at - ai_review_started_at).total_seconds()

    # --- Store timing in the PR record ---
    pr.ai_review_started_at = ai_review_started_at
    pr.ai_review_completed_at = ai_review_completed_at
    pr.ai_review_time_seconds = ai_review_time_seconds

    # Update PR with latest analysis summary fields
    pr.ai_score = analysis["ai_score"]
    pr.risk_level = analysis["risk_level"]
    pr.issue_count = analysis["issue_count"]
    pr.warning_count = analysis["warning_count"]
    pr.ai_analysis = analysis

    # Ensure AI reviewer is present
    reviewers = pr.reviewers or []
    if not any(r.get("type") == "AI" for r in reviewers):
        reviewers.append({"type": "AI", "model": ai_model})
    pr.reviewers = reviewers
    # Set review_status if not set or no human reviewer
    if not any(r.get("type") == "Human" for r in reviewers):
        pr.review_status = "AI only"
    else:
        pr.review_status = "AI + Human"
    db.commit()

    # Store analysis in history
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

async def create_or_update_pr_from_github(
    owner, repo_name, pr_number, db, background_tasks, user_id, github_token
):
    github_service = GitHubService(github_token)
    pr_data = await github_service.get_pull_request(owner, repo_name, pr_number)
    if not pr_data:
        raise Exception("Pull request not found or access denied")
    repo_full_name = f"{owner}/{repo_name}"
    repository = db.query(Repository).filter(Repository.full_name == repo_full_name).first()
    if not repository:
        repo_info = await github_service.get_repository(owner, repo_name)
        if not repo_info:
            raise Exception("Repository not found")
        repository = Repository(
            name=repo_name,
            full_name=repo_full_name,
            description=repo_info.get("description"),
            github_id=repo_info["id"],
            url=repo_info["html_url"],
            default_branch=repo_info["default_branch"],
            is_private=repo_info["private"],
            owner_id=user_id
        )
        db.add(repository)
        db.commit()
        db.refresh(repository)
    # Get or create PR
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
            repository_id=repository.id,
            author_id=user_id,
            files_changed=pr_data.get("changed_files", 0),
            lines_added=pr_data.get("additions", 0),
            lines_deleted=pr_data.get("deletions", 0),
            review_status="AI only",
            reviewers=[{"type": "AI", "model": "gpt-4o"}]
        )
        db.add(pr)
        db.commit()
        db.refresh(pr)
    commit_sha = pr_data["head"]["sha"] #latest sha
    # Fetch and add files (overwrite or append as needed)
    files_data = await github_service.get_pull_request_files(owner, repo_name, pr_number)
    ai_service = AIService()
    db.query(PRFile).filter(PRFile.pull_request_id == pr.id).delete()

    for file_data in files_data:
        content = await github_service.get_file_content(
            owner, repo_name, file_data["filename"], pr_data["head"]["sha"]
        )
        if content is not None and '\x00' in content:
            content = None  # or "BINARY FILE"
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
    # Start background analysis for this commit SHA
    background_tasks.add_task(analyze_pr_background, pr.id, commit_sha, db)
    return pr

@router.post("/", response_model=PullRequestSchema)
async def create_pull_request(
    pr_data: PullRequestCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new pull request for a repo (team lead only) and validate it"""
    repository = db.query(Repository).filter(Repository.id == pr_data.repository_id).first()
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    # NEW: Ensure the current user owns this repository
    if repository.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="You do not own this repository")

    company = None
    project = None
    if pr_data.company_id:
        company = db.query(Company).filter(Company.id == pr_data.company_id).first()
        if not company:
            raise HTTPException(status_code=400, detail="Invalid company")

    if company and pr_data.project_name:
        project = db.query(Project).filter(
            Project.name == pr_data.project_name,
            Project.company_id == company.id
        ).first()
        if not project:
            project = Project(name=pr_data.project_name, company_id=company.id)
            db.add(project)
            db.commit()
            db.refresh(project)

    pr = PullRequest(
        number=pr_data.number,
        title=pr_data.title,
        description=pr_data.description,
        branch=pr_data.branch,
        status=pr_data.status,
        github_url=pr_data.github_url,
        repository_id=pr_data.repository_id,
        author_id=current_user.id,
        project_id=pr_data.project_id,
        company_id=company.id if company else None,
        files_changed=len(pr_data.files) if pr_data.files else 0,
        lines_added=sum(f.additions for f in pr_data.files) if pr_data.files else 0,
        lines_deleted=sum(f.deletions for f in pr_data.files) if pr_data.files else 0,
        review_status="AI only",
        reviewers=[{"type": "AI", "model": "gpt-4o"}],
    )
    db.add(pr)
    db.commit()
    db.refresh(pr)
    
    if pr_data.files:
        ai_service = AIService()
        for file_data in files_data:
            content = await github_service.get_file_content(
                owner, repo_name, file_data["filename"], pr_data["head"]["sha"]
            )
            if content is not None and '\x00' in content:
                content = None  # or "BINARY FILE"
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
    background_tasks.add_task(analyze_pr_background, pr.id, "", db)
    return pr

@router.get("/count")
def get_pull_requests_count(
    status: Optional[str] = None,
    risk_level: Optional[str] = None,
    project_id: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Get all repo IDs owned by the current user (team lead)
    repo_ids = [repo.id for repo in db.query(Repository).filter(Repository.owner_id == current_user.id)]
    query = db.query(PullRequest).filter(PullRequest.repository_id.in_(repo_ids))

    if status:
        query = query.filter(PullRequest.status == status)
    if risk_level:
        query = query.filter(PullRequest.risk_level == risk_level)
    if project_id is not None:
        if project_id == "null":
            query = query.filter(PullRequest.project_id == None)
        elif project_id != "":
            query = query.filter(PullRequest.project_id == int(project_id))
    if search:
        search_str = f"%{search}%"
        query = query.filter(
            or_(
                PullRequest.title.ilike(search_str),
                PullRequest.description.ilike(search_str),
                PullRequest.branch.ilike(search_str),
                PullRequest.github_author.ilike(search_str)
            )
        )
    return query.count()

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
        # Create the repo and assign to current user
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
    else:
        # NEW: Ensure the current user owns this repository
        if repository.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="You do not own this repository")

    # Get or create PR
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
            repository_id=repository.id,
            author_id=current_user.id,
            company_id=payload.company_id,
            project_id=payload.project_id,
            files_changed=pr_data.get("changed_files", 0),
            lines_added=pr_data.get("additions", 0),
            lines_deleted=pr_data.get("deletions", 0),
            review_status="AI only",
            reviewers=[{"type": "AI", "model": "gpt-4o"}],
            github_created_at=pr_data.get("created_at"),
            github_author=pr_data["user"]["login"],
        )
        db.add(pr)
        db.commit()
        db.refresh(pr)
    # Always fetch latest commit SHA for analysis history
    commit_sha = pr_data["head"]["sha"]
    # Fetch and add files (overwrite or append as needed)
    files_data = await github_service.get_pull_request_files(owner, repo_name, pr_number)
    ai_service = AIService()
    db.query(PRFile).filter(PRFile.pull_request_id == pr.id).delete()
    for file_data in files_data:
        content = await github_service.get_file_content(
            owner, repo_name, file_data["filename"], pr_data["head"]["sha"]
        )
        # For modified/removed files, also get the old content (at BASE)
        old_content = None
        if file_data["status"] in ("modified", "removed"):
            old_content = await github_service.get_file_content(
                owner, repo_name, file_data["filename"], pr_data["base"]["sha"]
            )
        language = ai_service.get_language_from_filename(file_data["filename"])
        pr_file = PRFile(
            filename=file_data["filename"],
            status=file_data["status"],
            additions=file_data.get("additions", 0),
            deletions=file_data.get("deletions", 0),
            patch=file_data.get("patch"),
            content=content,
            old_content=old_content,
            language=language,
            pull_request_id=pr.id
        )
        db.add(pr_file)
    db.commit()

    # Start background analysis for this commit SHA
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

    # Ensure AI reviewer is present
    if not any(r.get("type") == "AI" for r in reviewers):
        reviewers.append({"type": "AI", "model": "gpt-4o"})

    # Ensure the current (only) user is the human reviewer
    if not any(r.get("type") == "Human" and r.get("name") == current_user.username for r in reviewers):
        reviewers.append({"type": "Human", "name": current_user.username})

    pr.reviewers = reviewers

    # Update review_status
    if any(r.get("type") == "AI" for r in reviewers) and any(r.get("type") == "Human" for r in reviewers):
        pr.review_status = "AI + Human"
    elif any(r.get("type") == "Human" for r in reviewers):
        pr.review_status = "Human only"
    else:
        pr.review_status = "AI only"

    # Store user review time in minutes
    pr.user_review_time_minutes = user_review_time_hours * 60

    db.commit()

    return {
        "message": "Review marked as complete",
        "review_status": pr.review_status,
        "reviewed_by": format_reviewed_by(pr.reviewers),
        "user_review_time_hours": user_review_time_hours
    }

@router.get("/", response_model=List[PullRequestSchema])
def get_pull_requests(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    risk_level: Optional[str] = None,
    project_id: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: Optional[str] = "created",
    sort_order: Optional[str] = "desc",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get pull requests for dashboard:
      - Team lead sees all PRs for their repos
      - Supports filtering, searching, and sorting
    """
    # Only include PRs for repos owned by the current user (team lead)
    repo_ids = [repo.id for repo in db.query(Repository).filter(Repository.owner_id == current_user.id)]
    query = db.query(PullRequest).filter(PullRequest.repository_id.in_(repo_ids))

    if status:
        query = query.filter(PullRequest.status == status)
    if risk_level:
        query = query.filter(PullRequest.risk_level == risk_level)
    if project_id is not None:
        if project_id == "null":
            query = query.filter(PullRequest.project_id == None)
        elif project_id != "":
            query = query.filter(PullRequest.project_id == int(project_id))
    if search:
        search_str = f"%{search}%"
        query = query.filter(
            or_(
                PullRequest.title.ilike(search_str),
                PullRequest.description.ilike(search_str),
                PullRequest.branch.ilike(search_str),
                PullRequest.github_author.ilike(search_str)
            )
        )
    # Sorting
    if sort_by == "created":
        order_col = PullRequest.github_created_at
    elif sort_by == "ai_score":
        order_col = PullRequest.ai_score
    elif sort_by == "files_changed":
        order_col = PullRequest.files_changed
    else:
        order_col = PullRequest.github_created_at
    if sort_order == "asc":
        query = query.order_by(order_col.asc())
    else:
        query = query.order_by(order_col.desc())

    # Pagination and project name enrichment
    pr_list = []
    for pr in query.offset(skip).limit(limit).all():
        pr_dict = pr.__dict__.copy()
        if pr.project_id:
            project = db.query(Project).filter(Project.id == pr.project_id).first()
            pr_dict["project_name"] = project.name if project else None
        else:
            pr_dict["project_name"] = None
        pr_list.append(pr_dict)
    return pr_list

@router.get("/", response_model=List[PullRequestSchema])
def get_pull_requests(
    project_id: Optional[int] = None,
    repository_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(PullRequest).join(Repository).filter(Repository.owner_id == current_user.id)
    if project_id:
        query = query.filter(Repository.project_id == project_id)
    if repository_id:
        query = query.filter(PullRequest.repository_id == repository_id)
    return query.all()

@router.delete("/{pr_id}")
def delete_pull_request(
    pr_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete pull request (team lead can only delete PRs in their own repos)"""
    # Get all repo IDs owned by the current user (team lead)
    repo_ids = [repo.id for repo in db.query(Repository).filter(Repository.owner_id == current_user.id)]
    pr = db.query(PullRequest).filter(
        PullRequest.id == pr_id,
        PullRequest.repository_id.in_(repo_ids)
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
    # Only allow access to PRs in repos owned by the current user (team lead)
    repo_ids = [repo.id for repo in db.query(Repository).filter(Repository.owner_id == current_user.id)]
    pr = db.query(PullRequest).filter(
        PullRequest.id == pr_id,
        PullRequest.repository_id.in_(repo_ids)
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
        reviewed_by=format_reviewed_by(pr.reviewers) if hasattr(pr, "reviewers") else None
    )

@router.get("/{pr_id}/analysis/history")
def get_pr_analysis_history(
    pr_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all analysis history for a pull request (team lead: only for owned repos)"""
    # Get all repo IDs owned by the current user (team lead)
    repo_ids = [repo.id for repo in db.query(Repository).filter(Repository.owner_id == current_user.id)]
    pr = db.query(PullRequest).filter(
        PullRequest.id == pr_id,
        PullRequest.repository_id.in_(repo_ids)
    ).first()
    if not pr:
        raise HTTPException(status_code=404, detail="Pull request not found")

    reviewed_by = format_reviewed_by(pr.reviewers) if hasattr(pr, "reviewers") else None

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
