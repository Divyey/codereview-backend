from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from pydantic import BaseModel, validator
import re
import logging

from ..core.database import get_db
from ..models.user import User
from ..models.repository import Repository
from ..services.github_service import GitHubService
from ..core.config import settings
from .auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

class RepositoryAnalysisRequest(BaseModel):
    github_url: str
    github_token: Optional[str] = None
    
    @validator('github_url')
    def validate_github_url(cls, v):
        # Support multiple GitHub URL formats
        patterns = [
            r'https://github\.com/([^/]+)/([^/]+)/?$',  # Basic repo URL
            r'https://github\.com/([^/]+)/([^/]+)/pull/(\d+)',  # PR URL
            r'https://github\.com/([^/]+)/([^/]+)/tree/([^/]+)',  # Branch URL
        ]
        
        for pattern in patterns:
            if re.match(pattern, v.strip()):
                return v.strip()
        
        raise ValueError('Invalid GitHub URL format. Expected: https://github.com/owner/repo')

class RepositoryAnalysisResponse(BaseModel):
    success: bool
    repository_info: Optional[Dict[str, Any]] = None
    token_requirement: Dict[str, Any]
    capabilities: Dict[str, bool]
    next_steps: list
    error_details: Optional[Dict[str, Any]] = None

class TokenRequirement(BaseModel):
    required: bool
    reason: str  # 'private_repo', 'rate_limit', 'organization', 'optional'
    message: str
    severity: str  # 'error', 'warning', 'info'

def parse_github_url(url: str) -> Dict[str, str]:
    """Enhanced URL parsing for different GitHub URL formats."""
    patterns = {
        'repo': r'https://github\.com/([^/]+)/([^/]+)/?$',
        'pull_request': r'https://github\.com/([^/]+)/([^/]+)/pull/(\d+)',
        'branch': r'https://github\.com/([^/]+)/([^/]+)/tree/([^/]+)',
    }
    
    for url_type, pattern in patterns.items():
        match = re.match(pattern, url.strip())
        if match:
            result = {
                'owner': match.group(1),
                'repo': match.group(2),
                'type': url_type
            }
            if url_type == 'pull_request':
                result['pr_number'] = int(match.group(3))
            elif url_type == 'branch':
                result['branch'] = match.group(3)
            return result
    
    raise ValueError("Invalid GitHub URL format")

def determine_token_requirement(
    repo_info: Optional[Dict], 
    error: Optional[Exception],
    has_token: bool
) -> TokenRequirement:
    """Smart token requirement detection."""
    
    if error:
        if hasattr(error, 'status_code'):
            if error.status_code == 404:
                return TokenRequirement(
                    required=True,
                    reason='private_repo',
                    message='Repository not found. It may be private or you may not have access. Please provide a GitHub token.',
                    severity='error'
                )
            elif error.status_code == 403:
                return TokenRequirement(
                    required=True,
                    reason='rate_limit',
                    message='GitHub API rate limit exceeded. Please provide a GitHub token for higher limits.',
                    severity='error'
                )
    
    if repo_info:
        if repo_info.get('private', False) and not has_token:
            return TokenRequirement(
                required=True,
                reason='private_repo',
                message='This is a private repository. A GitHub token is required for access.',
                severity='error'
            )
        
        if repo_info.get('owner', {}).get('type') == 'Organization':
            return TokenRequirement(
                required=False,
                reason='organization',
                message='Organization repository detected. A token is recommended for full access and webhooks.',
                severity='warning'
            )
        
        if not has_token:
            return TokenRequirement(
                required=False,
                reason='optional',
                message='Public repository detected. A token is optional but recommended for webhooks and higher rate limits.',
                severity='info'
            )
    
    return TokenRequirement(
        required=False,
        reason='optional',
        message='Token provided. Full access available.',
        severity='info'
    )

def calculate_capabilities(repo_info: Optional[Dict], has_token: bool) -> Dict[str, bool]:
    """Calculate available capabilities based on repository and token."""
    if not repo_info:
        return {
            'manual_pr_analysis': False,
            'dashboard_analytics': False,
            'webhook_setup': False,
            'automatic_pr_detection': False,
            'private_repo_access': False,
            'team_analytics': False,
            'advanced_permissions': False
        }
    
    is_private = repo_info.get('private', False)
    is_organization = repo_info.get('owner', {}).get('type') == 'Organization'
    
    return {
        'manual_pr_analysis': True,
        'dashboard_analytics': True,
        'webhook_setup': has_token,
        'automatic_pr_detection': has_token,
        'private_repo_access': not is_private or has_token,
        'team_analytics': is_organization,
        'advanced_permissions': is_organization and has_token
    }

def generate_next_steps(capabilities: Dict[str, bool], repo_info: Optional[Dict]) -> list:
    """Generate contextual next steps based on capabilities."""
    steps = []
    
    if capabilities['manual_pr_analysis']:
        steps.append({
            'id': 'analyze_prs',
            'title': 'Analyze Pull Requests',
            'description': 'Import and analyze existing PRs from this repository',
            'action': 'import_prs',
            'priority': 'high',
            'enabled': True
        })
    
    if capabilities['webhook_setup']:
        steps.append({
            'id': 'setup_webhooks',
            'title': 'Enable Auto-Analysis',
            'description': 'Set up webhooks for automatic PR analysis on new PRs',
            'action': 'setup_webhooks',
            'priority': 'medium',
            'enabled': True
        })
    
    if capabilities['dashboard_analytics']:
        steps.append({
            'id': 'configure_dashboard',
            'title': 'Customize Dashboard',
            'description': 'Set up analytics preferences and monitoring',
            'action': 'configure_dashboard',
            'priority': 'low',
            'enabled': True
        })
    
    if capabilities['team_analytics']:
        steps.append({
            'id': 'team_setup',
            'title': 'Team Analytics',
            'description': 'Configure team-wide code quality monitoring',
            'action': 'setup_team',
            'priority': 'medium',
            'enabled': True
        })
    
    return steps

@router.post("/analyze", response_model=RepositoryAnalysisResponse)
async def analyze_repository(
    request: RepositoryAnalysisRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Smart repository analysis with progressive token requirements.
    This endpoint analyzes a GitHub repository and determines what's needed for full access.
    """
    try:
        # Parse the GitHub URL
        url_info = parse_github_url(request.github_url)
        owner = url_info['owner']
        repo = url_info['repo']
        
        logger.info(f"Analyzing repository: {owner}/{repo} for user {current_user.email}")
        
        # Check if repository already exists
        existing_repo = db.query(Repository).filter(
            Repository.full_name == f"{owner}/{repo}",
            Repository.owner_id == current_user.id
        ).first()
        
        if existing_repo:
            return RepositoryAnalysisResponse(
                success=True,
                repository_info={
                    'id': existing_repo.id,
                    'name': existing_repo.name,
                    'full_name': existing_repo.full_name,
                    'description': existing_repo.description,
                    'private': existing_repo.is_private,
                    'default_branch': existing_repo.default_branch,
                    'url': existing_repo.url,
                    'already_added': True
                },
                token_requirement={
                    'required': False,
                    'reason': 'already_added',
                    'message': 'Repository already added to your account.',
                    'severity': 'info'
                },
                capabilities=calculate_capabilities({'private': existing_repo.is_private}, bool(request.github_token)),
                next_steps=generate_next_steps(
                    calculate_capabilities({'private': existing_repo.is_private}, bool(request.github_token)),
                    {'private': existing_repo.is_private}
                )
            )
        
        # Try to fetch repository info
        repo_info = None
        error = None
        
        # Determine which token to use
        token = request.github_token or current_user.github_token or settings.GITHUB_TOKEN
        github_service = GitHubService(token)
        
        try:
            repo_info = await github_service.get_repository(owner, repo)
            logger.info(f"Successfully fetched repository info for {owner}/{repo}")
        except Exception as e:
            error = e
            logger.warning(f"Failed to fetch repository info: {str(e)}")
        
        # Determine token requirements
        token_req = determine_token_requirement(repo_info, error, bool(request.github_token))
        
        # Calculate capabilities
        capabilities = calculate_capabilities(repo_info, bool(request.github_token))
        
        # Generate next steps
        next_steps = generate_next_steps(capabilities, repo_info)
        
        response = RepositoryAnalysisResponse(
            success=repo_info is not None,
            repository_info=repo_info,
            token_requirement=token_req.dict(),
            capabilities=capabilities,
            next_steps=next_steps
        )
        
        if error:
            response.error_details = {
                'type': type(error).__name__,
                'message': str(error),
                'status_code': getattr(error, 'status_code', None)
            }
        
        return response
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid input: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error in repository analysis: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during repository analysis"
        )

@router.post("/add")
async def add_repository(
    request: RepositoryAnalysisRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Add repository after successful analysis.
    This should be called after /analyze confirms the repository is accessible.
    """
    try:
        # Parse URL and get repository info
        url_info = parse_github_url(request.github_url)
        owner = url_info['owner']
        repo = url_info['repo']
        
        # Use provided token or user's stored token
        token = request.github_token or current_user.github_token or settings.GITHUB_TOKEN
        github_service = GitHubService(token)
        
        # Fetch repository info
        repo_info = await github_service.get_repository(owner, repo)
        
        # Check if already exists
        existing_repo = db.query(Repository).filter(
            Repository.full_name == f"{owner}/{repo}",
            Repository.owner_id == current_user.id
        ).first()
        
        if existing_repo:
            return {
                'success': True,
                'message': 'Repository already exists',
                'repository': {
                    'id': existing_repo.id,
                    'name': existing_repo.name,
                    'full_name': existing_repo.full_name
                }
            }
        
        # Create new repository
        new_repo = Repository(
            name=repo,
            full_name=f"{owner}/{repo}",
            owner_id=current_user.id,
            github_id=repo_info['id'],
            url=repo_info['html_url'],
            description=repo_info.get('description'),
            default_branch=repo_info.get('default_branch', 'development'),
            is_private=repo_info.get('private', False)
        )
        
        db.add(new_repo)
        
        # Update user's GitHub token if provided
        if request.github_token and request.github_token != current_user.github_token:
            current_user.github_token = request.github_token
            
            # Also update GitHub user info if we can fetch it
            try:
                user_info = await github_service.get_user()
                if user_info:
                    current_user.github_id = user_info.get('id')
                    current_user.login = user_info.get('login')
                    current_user.type = user_info.get('type', 'User')
            except Exception as e:
                logger.warning(f"Could not fetch user info: {str(e)}")
        
        db.commit()
        db.refresh(new_repo)
        
        logger.info(f"Successfully added repository {new_repo.full_name} for user {current_user.email}")
        
        return {
            'success': True,
            'message': 'Repository added successfully',
            'repository': {
                'id': new_repo.id,
                'name': new_repo.name,
                'full_name': new_repo.full_name,
                'description': new_repo.description,
                'private': new_repo.is_private,
                'default_branch': new_repo.default_branch,
                'url': new_repo.url
            }
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error adding repository: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add repository: {str(e)}"
        )
