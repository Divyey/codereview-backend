from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import List, Optional
from ..core.config import settings
from ..core.database import get_db
from ..models.user import User
from ..models.repository import Repository
from ..schemas.repository import (
    RepositoryRead as RepositorySchema,
    RepositoryCreate,
    RepositoryUpdate,
    GithubRepositoryImportRequest,
)
from ..services.github_service import GitHubService
from .auth import get_current_user
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

router = APIRouter()


async def import_repository_from_github_payload(db: AsyncSession, repo_payload: dict):
    print("========== 📦 Importing Repository from GitHub Payload ==========")
    owner_data = repo_payload.get('owner')
    if not owner_data:
        print("❌ [ERROR] No owner information in GitHub payload!")
        raise ValueError("Missing owner data in repository payload.")

    print(f"👤 Owner login: {owner_data.get('login')} (GitHub ID: {owner_data.get('id')})")

    result = await db.execute(
        select(User).filter_by(github_id=owner_data['id'])
    )
    owner = result.scalars().first()
    if not owner:
        print("🆕 Owner not found in DB. Creating new User record...")
        owner = User(
            github_id=owner_data['id'],
            login=owner_data['login'],
            type=owner_data.get('type', 'User'),
        )
        db.add(owner)
        await db.commit()
        await db.refresh(owner)
        print(f"✅ Created User: {owner.login} (id={owner.id})")
    else:
        print(f"✅ Owner already exists in DB: {owner.login} (id={owner.id})")

    result = await db.execute(
        select(Repository).filter_by(github_id=repo_payload['id'])
    )
    repo = result.scalars().first()
    if repo:
        print(f"📚 Repository already exists in DB: {repo.full_name} (id={repo.id})")
        return repo

    print("🆕 Repository not found in DB. Creating new Repository record...")
    repo = Repository(
        name=repo_payload['name'],
        full_name=repo_payload['full_name'],
        description=repo_payload.get('description'),
        github_id=repo_payload['id'],
        url=repo_payload['html_url'],
        default_branch=repo_payload['default_branch'],
        is_private=repo_payload['private'],
        owner_id=owner.id,
    )
    db.add(repo)
    await db.commit()
    await db.refresh(repo)
    print(f"✅ Created Repository: {repo.full_name} (id={repo.id}, owner_id={repo.owner_id})")
    return repo

@router.post("/", response_model=RepositorySchema)
async def create_repository(
    repo_data: RepositoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new repository record manually."""
    repo = db.query(Repository).filter(Repository.full_name == repo_data.full_name).first()
    if repo:
        raise HTTPException(status_code=400, detail="Repository already exists")
    repo = Repository(
        name=repo_data.name,
        full_name=repo_data.full_name,
        description=repo_data.description,
        github_id=repo_data.github_id,
        url=repo_data.url,
        default_branch=repo_data.default_branch,
        is_private=repo_data.is_private,
        owner_id=current_user.id
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)
    return repo

@router.post("/from-github", response_model=RepositorySchema)
async def import_repository_from_github(
    payload: GithubRepositoryImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Import a repository from GitHub by URL."""
    github_url = payload.github_url
    github_token = payload.github_token
    token = github_token or current_user.github_token or settings.GITHUB_TOKEN
    github_service = GitHubService(token)
    url_parts = github_service.parse_github_repo_url(github_url)
    if not url_parts:
        raise HTTPException(status_code=400, detail="Invalid GitHub repository URL")
    owner = url_parts["owner"]
    repo_name = url_parts["repo"]
    repo_info = await github_service.get_repository(owner, repo_name)
    if not repo_info:
        raise HTTPException(status_code=404, detail="Repository not found or access denied")
    repo_full_name = f"{owner}/{repo_name}"
    repo = db.query(Repository).filter(Repository.full_name == repo_full_name).first()
    if not repo:
        repo = Repository(
            name=repo_name,
            full_name=repo_full_name,
            description=repo_info.get("description"),
            github_id=repo_info["id"],
            url=repo_info["html_url"],
            default_branch=repo_info["default_branch"],
            is_private=repo_info["private"],
            owner_id=current_user.id
        )
        db.add(repo)
        db.commit()
        db.refresh(repo)
    return repo

@router.post("/{repo_id}/sync-prs")
async def sync_repository_prs(
    repo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Sync all pull requests from GitHub for a repository"""
    import logging
    from ..models.pull_request import PullRequest
    
    logger = logging.getLogger(__name__)
    logger.info(f"Starting PR sync for repository ID: {repo_id}")
    
    # Get repository
    repository = db.query(Repository).filter(
        Repository.id == repo_id,
        Repository.owner_id == current_user.id
    ).first()
    if not repository:
        logger.error(f"Repository not found: {repo_id}")
        raise HTTPException(status_code=404, detail="Repository not found")
    
    logger.info(f"Syncing PRs for repository: {repository.full_name}")
    
    # Parse repository name
    try:
        owner, repo_name = repository.full_name.split('/')
    except ValueError:
        logger.error(f"Invalid repository full_name format: {repository.full_name}")
        raise HTTPException(status_code=400, detail="Invalid repository name format")
    
    # Get GitHub token
    token = current_user.github_token or settings.GITHUB_TOKEN
    if not token:
        logger.error("No GitHub token available")
        raise HTTPException(status_code=400, detail="GitHub token required. Please provide a GitHub token in your profile or ensure system token is configured.")
    
    github_service = GitHubService(token)
    
    try:
        logger.info(f"Fetching PRs from GitHub for {owner}/{repo_name}")
        # Get all PRs from GitHub (open and closed)
        all_prs = await github_service.get_pull_requests(owner, repo_name, state="all")
        all_prs = all_prs or []
        
        logger.info(f"Found {len(all_prs)} PRs on GitHub")
        
        synced_count = 0
        skipped_count = 0
        
        for pr_data in all_prs:
            try:
                pr_number = pr_data["number"]
                
                # Check if PR already exists
                existing_pr = db.query(PullRequest).filter(
                    PullRequest.repository_id == repository.id,
                    PullRequest.number == pr_number
                ).first()
                
                if existing_pr:
                    # Update status and other fields if they changed
                    changed = False
                    new_status = "merged" if pr_data.get("merged") else ("closed" if pr_data.get("closed_at") else "open")
                    if existing_pr.status != new_status:
                        existing_pr.status = new_status
                        changed = True
                    
                    if pr_data.get("title") != existing_pr.title:
                        existing_pr.title = pr_data["title"]
                        changed = True
                        
                    # Backfill github_author if missing
                    gh_author = pr_data.get("user", {}).get("login")
                    if gh_author and not existing_pr.github_author:
                        existing_pr.github_author = gh_author
                        changed = True

                    if changed:
                        db.add(existing_pr)
                        db.commit()
                        logger.info(f"Updated PR #{pr_number}: {pr_data['title']} (status: {new_status})")
                    
                    skipped_count += 1
                    continue  # Skip creating new, but we might have updated
                
                # Create new PR
                gh_author = pr_data.get("user", {}).get("login")
                pr = PullRequest(
                    number=pr_number,
                    title=pr_data["title"],
                    description=pr_data.get("body"),
                    branch=pr_data["head"]["ref"],
                    status="merged" if pr_data.get("merged") else ("closed" if pr_data.get("closed_at") else "open"),
                    github_id=pr_data["id"],
                    github_url=pr_data["html_url"],
                    github_author=gh_author,
                    repository_id=repository.id,
                    author_id=current_user.id, # The user who synced it
                    files_changed=pr_data.get("changed_files", 0),
                    lines_added=pr_data.get("additions", 0),
                    lines_deleted=pr_data.get("deletions", 0),
                    review_status="Pending",
                    reviewers=[]
                )
                db.add(pr)
                db.commit()
                db.refresh(pr)
                synced_count += 1
                logger.info(f"Synced PR #{pr_number}: {pr_data['title']}")
                
            except Exception as pr_error:
                logger.error(f"Error syncing PR #{pr_data.get('number', 'unknown')}: {str(pr_error)}")
                db.rollback()
                continue
        
        logger.info(f"Sync completed: {synced_count} new PRs, {skipped_count} skipped")
        
        return {
            "message": f"Successfully synced {synced_count} new pull requests",
            "synced_count": synced_count,
            "skipped_count": skipped_count,
            "total_found": len(all_prs)
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions (from GitHub service)
        raise
    except Exception as e:
        logger.error(f"Unexpected error during PR sync: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to sync PRs: {str(e)}")

@router.get("/", response_model=List[RepositorySchema])
def get_repositories(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List repositories owned by the current user."""
    return db.query(Repository).filter(Repository.owner_id == current_user.id).offset(skip).limit(limit).all()

@router.get("/{repo_id}", response_model=RepositorySchema)
def get_repository(
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
    return repo

@router.put("/{repo_id}", response_model=RepositorySchema)
def update_repository(
    repo_id: int,
    repo_update: RepositoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    repo = db.query(Repository).filter(
        Repository.id == repo_id,
        Repository.owner_id == current_user.id
    ).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    for field, value in repo_update.dict(exclude_unset=True).items():
        setattr(repo, field, value)
    db.commit()
    db.refresh(repo)
    return repo

@router.delete("/{repo_id}")
def delete_repository(
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
    db.delete(repo)
    db.commit()
    return {"message": "Repository deleted successfully"}
