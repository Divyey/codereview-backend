from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.models.repository import Repository
from app.schemas.repository import RepositoryRead, RepositoryCreate, RepositoryUpdate
from app.api.auth import get_current_user
from app.models.user import User

router = APIRouter()

@router.get("/", response_model=List[RepositoryRead])
def list_repositories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(Repository).filter(Repository.owner_id == current_user.id).all()

@router.post("/", response_model=RepositoryRead)
def create_repository(
    repo: RepositoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    new_repo = Repository(
        name=repo.name,
        full_name=repo.full_name,
        owner_id=current_user.id,
        default_branch=repo.default_branch,
        is_private=repo.is_private
    )
    db.add(new_repo)
    db.commit()
    db.refresh(new_repo)
    return new_repo

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
    return {"message": "Repository deleted"}
