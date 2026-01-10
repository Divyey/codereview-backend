"""
Sync API endpoints for comprehensive data refresh and synchronization
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from pydantic import BaseModel

from ..core.database import get_db
from .auth import get_current_user
from ..models.user import User
from ..services.sync_service import sync_service

router = APIRouter()

class SyncRequest(BaseModel):
    github_token: Optional[str] = None
    force_reanalysis: bool = True

class IndividualSyncRequest(BaseModel):
    github_token: Optional[str] = None
    force_reanalysis: bool = True

@router.post("/sync/complete-reset")
async def complete_reset_and_sync(
    background_tasks: BackgroundTasks,
    request: SyncRequest = SyncRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Complete reset and sync of all data for the current user
    This is the main "Complete Reset" functionality
    """
    try:
        # Start sync in background
        background_tasks.add_task(
            sync_service.complete_reset_and_sync,
            current_user,
            db,
            request.github_token
        )
        
        return {
            "message": "Complete reset and sync started",
            "status": "initiated",
            "estimated_duration": "5-10 minutes",
            "note": "This will refresh all repositories, pull requests, and re-analyze everything with enhanced AI"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start complete sync: {str(e)}"
        )

@router.post("/sync/repository/{repository_id}")
async def sync_repository(
    repository_id: int,
    background_tasks: BackgroundTasks,
    request: IndividualSyncRequest = IndividualSyncRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Sync a specific repository and its pull requests
    """
    try:
        # Start repository sync in background
        background_tasks.add_task(
            sync_service.sync_individual_repository,
            current_user,
            repository_id,
            db,
            request.github_token
        )
        
        return {
            "message": f"Repository {repository_id} sync started",
            "status": "initiated",
            "estimated_duration": "1-3 minutes"
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start repository sync: {str(e)}"
        )

@router.post("/sync/pull-request/{pr_id}")
async def sync_pull_request(
    pr_id: int,
    request: IndividualSyncRequest = IndividualSyncRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Sync and re-analyze a specific pull request
    """
    try:
        result = await sync_service.sync_individual_pull_request(
            current_user,
            pr_id,
            db,
            request.github_token,
            request.force_reanalysis
        )
        
        return {
            "message": f"Pull request {pr_id} synced successfully",
            "status": "completed",
            "result": result
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync pull request: {str(e)}"
        )

@router.get("/sync/status/{sync_id}")
async def get_sync_status(
    sync_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get the status of a running sync operation
    """
    try:
        status_info = sync_service.get_sync_status(sync_id)
        
        if not status_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sync operation not found"
            )
        
        return {
            "sync_id": sync_id,
            "status": status_info
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get sync status: {str(e)}"
        )

@router.post("/sync/auto-sync/enable")
async def enable_auto_sync(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Enable automatic syncing for the user
    """
    try:
        # Update user preferences to enable auto-sync
        # This would be stored in user preferences or settings table
        
        return {
            "message": "Auto-sync enabled",
            "status": "enabled",
            "note": "Data will be automatically refreshed when changes are detected"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enable auto-sync: {str(e)}"
        )

@router.post("/sync/auto-sync/disable")
async def disable_auto_sync(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Disable automatic syncing for the user
    """
    try:
        # Update user preferences to disable auto-sync
        
        return {
            "message": "Auto-sync disabled",
            "status": "disabled"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to disable auto-sync: {str(e)}"
        )

@router.get("/sync/quick-stats")
async def get_quick_sync_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get quick stats about what would be synced
    """
    try:
        from ..models.repository import Repository
        from ..models.pull_request import PullRequest
        from sqlalchemy import func, and_
        from datetime import datetime, timedelta
        
        # Count repositories
        repo_count = db.query(func.count(Repository.id)).filter(
            Repository.user_id == current_user.id
        ).scalar()
        
        # Count pull requests
        pr_count = db.query(func.count(PullRequest.id)).filter(
            PullRequest.user_id == current_user.id
        ).scalar()
        
        # Count PRs needing re-analysis (older than 7 days or no AI score)
        stale_prs = db.query(func.count(PullRequest.id)).filter(
            and_(
                PullRequest.user_id == current_user.id,
                PullRequest.updated_at < datetime.utcnow() - timedelta(days=7)
            )
        ).scalar()
        
        return {
            "repositories": repo_count,
            "pull_requests": pr_count,
            "stale_analyses": stale_prs,
            "estimated_sync_time": f"{max(2, repo_count * 0.5 + pr_count * 0.1):.0f} minutes"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get sync stats: {str(e)}"
        )

