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
