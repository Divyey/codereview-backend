from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Body
from sqlalchemy.orm import Session
from typing import List, Optional
from ..core.config import settings
from ..core.database import get_db
from ..models.user import User
from ..models.repository import Repository
from ..models.pull_request import PullRequest, PRFile
from ..services.github_service import GitHubService
from ..services.ai_service import AIService
from ..schemas.repository import Repository as RepositorySchema, RepositoryCreate, RepositoryUpdate
from .auth import get_current_user
from .pull_requests import analyze_pr_background
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/repositories",
    tags=["repositories"]
)

@router.post("/", response_model=RepositorySchema)
def create_repository(
    repo_data: RepositoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new repository"""
    existing_repo = db.query(Repository).filter(Repository.full_name == repo_data.full_name).first()
    if existing_repo:
        raise HTTPException(status_code=400, detail="Repository already exists")
    repository = Repository(
        **repo_data.dict(),
        owner_id=current_user.id
    )
    db.add(repository)
    db.commit()
    db.refresh(repository)
    return repository

@router.get("/", response_model=List[RepositorySchema])
def get_repositories(
    skip: int = 0,
    limit: int = 25,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(Repository).filter(Repository.owner_id == current_user.id).offset(skip).limit(limit).all()

@router.get("/{repo_id}", response_model=RepositorySchema)
def get_repository(
    repo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get specific repository"""
    repository = db.query(Repository).filter(
        Repository.id == repo_id,
        Repository.owner_id == current_user.id
    ).first()
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")
    return repository

@router.put("/{repo_id}", response_model=RepositorySchema)
def update_repository(
    repo_id: int,
    repo_update: RepositoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update repository"""
    repository = db.query(Repository).filter(
        Repository.id == repo_id,
        Repository.owner_id == current_user.id
    ).first()
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")
    for field, value in repo_update.dict(exclude_unset=True).items():
        setattr(repository, field, value)
    db.commit()
    db.refresh(repository)
    return repository

@router.delete("/{repo_id}")
def delete_repository(
    repo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete repository"""
    repository = db.query(Repository).filter(
        Repository.id == repo_id,
        Repository.owner_id == current_user.id
    ).first()
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")
    db.delete(repository)
    db.commit()
    return {"message": "Repository deleted successfully"}

# Helper function to import a single PR (reuse your logic from pull_request endpoint)
async def import_single_pr(
    owner: str,
    repo_name: str,
    pr_number: int,
    repository: Repository,
    current_user: User,
    background_tasks: BackgroundTasks,
    db: Session,
    github_service: GitHubService
):
    pr_data = await github_service.get_pull_request(owner, repo_name, pr_number)
    if not pr_data:
        return None
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
        # Null-byte check for binary files
        if content is not None and '\x00' in content:
            content = None
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
    return pr

@router.post("/from-github")
async def import_repository_from_github(
    github_url: str = Body(..., embed=True),
    github_token: Optional[str] = Body(None, embed=True),
    pr_number: Optional[int] = Body(None, embed=True),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    import re
    logger.info(f"Received import request for repo: {github_url}")
    m = re.match(r"https://github.com/([^/]+)/([^/]+)", github_url)
    if not m:
        logger.error(f"Invalid GitHub repository URL: {github_url}")
        raise HTTPException(status_code=400, detail="Invalid GitHub repository URL")
    owner, repo_name = m.group(1), m.group(2)
    token = github_token or getattr(current_user, "github_token", None) or getattr(settings, "GITHUB_TOKEN", None)
    logger.info(f"Using token: {'provided' if github_token else 'user/default'}")
    github_service = GitHubService(token)
    logger.info(f"Fetching repository info for {owner}/{repo_name} from GitHub...")
    repo_info = await github_service.get_repository(owner, repo_name)
    if not repo_info:
        logger.error(f"Repository not found: {owner}/{repo_name}")
        raise HTTPException(status_code=404, detail="Repository not found")
    repo_full_name = f"{owner}/{repo_name}"
    repository = db.query(Repository).filter(Repository.full_name == repo_full_name).first()
    if not repository:
        logger.info(f"Repository not in DB, creating: {repo_full_name}")
        repository = Repository(
            name=repo_name,
            full_name=repo_full_name,
            description=repo_info.get("description"),
            github_id=repo_info.get("id"),
            url=repo_info.get("html_url"),
            default_branch=repo_info.get("default_branch"),
            is_private=repo_info.get("private"),
            owner_id=current_user.id,
            language=repo_info.get("language"),
            stars=repo_info.get("stargazers_count"),
            forks=repo_info.get("forks_count"),
            open_issues=repo_info.get("open_issues_count"),
            archived=repo_info.get("archived"),
            github_created_at=repo_info.get("created_at"),
            github_updated_at=repo_info.get("updated_at"),
            last_imported_at=datetime.utcnow(),
        )
        db.add(repository)
        db.commit()
        db.refresh(repository)
        logger.info(f"Repository created in DB: {repo_full_name}")
    else:
        if repository.owner_id != current_user.id:
            logger.warning(f"User {current_user.id} tried to import repo they do not own: {repo_full_name}")
            raise HTTPException(status_code=403, detail="You do not own this repository")
        # Update repo metadata on re-import
        repository.language = repo_info.get("language")
        repository.stars = repo_info.get("stargazers_count")
        repository.forks = repo_info.get("forks_count")
        repository.open_issues = repo_info.get("open_issues_count")
        repository.archived = repo_info.get("archived")
        repository.github_created_at = repo_info.get("created_at")
        repository.github_updated_at = repo_info.get("updated_at")
        repository.last_imported_at = datetime.utcnow()
        db.commit()
        logger.info(f"Repository already exists in DB: {repo_full_name}, metadata updated.")

    imported_prs = []
    if pr_number:
        logger.info(f"Importing specific PR: #{pr_number}")
        pr_numbers = [pr_number]
    else:
        logger.info(f"Fetching all PRs for {owner}/{repo_name} from GitHub...")
        prs = await github_service.get_pull_requests(owner, repo_name, state="all")
        pr_numbers = [pr["number"] for pr in prs]
        logger.info(f"Found {len(pr_numbers)} PR(s) to import.")

    for number in pr_numbers:
        pr = db.query(PullRequest).filter(
            PullRequest.repository_id == repository.id,
            PullRequest.number == number
        ).first()
        if pr:
            logger.info(f"PR #{number} already imported, skipping.")
            continue  # Skip already imported PRs
        logger.info(f"Importing PR #{number}...")
        try:
            await import_single_pr(owner, repo_name, number, repository, current_user, background_tasks, db, github_service)
            logger.info(f"PR #{number} imported successfully.")
            imported_prs.append(number)
        except Exception as e:
            logger.error(f"Failed to import PR #{number}: {str(e)}")

    logger.info(f"Import complete: {len(imported_prs)} PR(s) imported for {repo_full_name}")
    return {"message": f"Imported repository and {len(imported_prs)} PR(s)", "prs": imported_prs}
