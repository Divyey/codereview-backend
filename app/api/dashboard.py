from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from collections import Counter
import json
from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.repository import Repository
from app.models.branch import Branch
from app.models.pull_request import PullRequest
from app.models.secret_finding import SecretFinding
from app.models.infra_finding import InfraFinding
from app.models.security_finding import SecurityFinding
from app.models.sca_finding import SCAFinding

router = APIRouter()

# 1. List all repositories
@router.get("/repositories/", tags=["dashboard"])
def list_repositories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    repos = db.query(Repository).filter(Repository.owner_id == current_user.id).all()
    return [{"id": r.id, "name": r.name, "full_name": r.full_name} for r in repos]


# 2. List branches for a repository
@router.get("/branches/", tags=["dashboard"])
def list_branches(
    repo_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    repo = db.query(Repository).filter(
        Repository.id == repo_id,
        Repository.owner_id == current_user.id
    ).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    branches = db.query(Branch).filter(Branch.repository_id == repo_id).all()
    return [{"name": b.name} for b in branches]


# 3. List PRs for a repo/branch
@router.get("/pull-requests/", tags=["dashboard"])
def list_pull_requests(
    repo_id: int = Query(...),
    branch: str = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    repo = db.query(Repository).filter(
        Repository.id == repo_id,
        Repository.owner_id == current_user.id
    ).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    pr_query = db.query(PullRequest).filter(PullRequest.repository_id == repo_id)
    if branch:
        pr_query = pr_query.filter(PullRequest.branch == branch)
    prs = pr_query.order_by(PullRequest.github_created_at.desc()).all()
    return [{"id": pr.id, "number": pr.number, "title": pr.title} for pr in prs]


# 4. Get PR details (for QuickView sidebar)
@router.get("/pull-requests/{pr_id}", tags=["dashboard"])
def get_pull_request(
    pr_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    pr = db.query(PullRequest).filter(PullRequest.id == pr_id).first()
    # Check: PR exists and belongs to a repo owned by the current user
    if not pr or pr.repository.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Pull request not found")
    pr_dict = pr.__dict__.copy()
    pr_dict["repository"] = {
        "id": pr.repository.id,
        "name": pr.repository.name,
        "full_name": pr.repository.full_name
    } if pr.repository else None
    pr_dict["files"] = [
        {
            "filename": f.filename,
            "status": f.status,
            "additions": f.additions,
            "deletions": f.deletions,
            "content": f.content,
            "language": f.language
        }
        for f in getattr(pr, "files", [])
    ]
    return pr_dict

# 5. Main dashboard stats endpoint
from fastapi import Depends, Query, HTTPException
from app.api.auth import get_current_user
from app.models.user import User

@router.get("/dashboard/ai-review-stats/", tags=["dashboard"])
def ai_review_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    repo_id: int = Query(None),
    branch: str = Query(None),
    pr_number: int = Query(None),
    risk_level: str = Query(None),
    period: str = Query("all")  # "all", "7", "30", "90"
):
    # Only include repos owned by the current user
    user_repo_ids = [repo.id for repo in current_user.repositories]

    # If repo_id is provided, ensure it's one of the user's repos
    if repo_id is not None and repo_id not in user_repo_ids:
        raise HTTPException(status_code=404, detail="Repository not found")

    pr_query = db.query(PullRequest).filter(PullRequest.repository_id.in_(user_repo_ids))
    if repo_id:
        pr_query = pr_query.filter(PullRequest.repository_id == repo_id)
    if branch:
        pr_query = pr_query.filter(PullRequest.branch == branch)
    if pr_number:
        pr_query = pr_query.filter(PullRequest.number == pr_number)
    if risk_level:
        pr_query = pr_query.filter(PullRequest.risk_level.ilike(risk_level))
    if period != "all":
        try:
            days = int(period)
            since = datetime.utcnow() - timedelta(days=days)
            pr_query = pr_query.filter(PullRequest.github_created_at >= since)
        except Exception:
            pass

    # Only count repos owned by the user
    repo_count = len(user_repo_ids)
    repo_added = 0  # You can implement logic to count repos added in the period if you store created_at
    repo_added_change = 0

    pr_reviewed = pr_query.filter(PullRequest.ai_review_completed_at != None).count()
    pr_reviewed_change = 0

    pr_ids = [pr.id for pr in pr_query.all()]

    secrets_detected = db.query(SecretFinding).filter(SecretFinding.pull_request_id.in_(pr_ids)).count() if pr_ids else 0
    infra_issues = db.query(InfraFinding).filter(InfraFinding.pull_request_id.in_(pr_ids)).count() if pr_ids else 0
    security_findings = db.query(SecurityFinding).filter(SecurityFinding.pull_request_id.in_(pr_ids)).count() if pr_ids else 0
    sca_findings = db.query(SCAFinding).filter(SCAFinding.pull_request_id.in_(pr_ids)).count() if pr_ids else 0

    avg_ai_score = pr_query.with_entities(func.avg(PullRequest.ai_score)).scalar() or 0

    critical_issues = db.query(SecurityFinding).filter(
        SecurityFinding.pull_request_id.in_(pr_ids),
        SecurityFinding.severity == 'critical'
    ).count() if pr_ids else 0

    pr_issues = pr_query.with_entities(func.sum(PullRequest.issue_count)).scalar() or 0
    active_issues = pr_query.filter(PullRequest.status == 'open').with_entities(func.sum(PullRequest.issue_count)).scalar() or 0
    active_issues_pct = int((active_issues / pr_issues) * 100) if pr_issues else 0

    avg_review_time = pr_query.with_entities(func.avg(PullRequest.ai_review_time_seconds)).scalar()
    avg_review_time = round((avg_review_time or 0) / 60, 1)

    risk_levels = ['low', 'medium', 'high', 'critical']
    risk_level_counts = {
        lvl: pr_query.filter(PullRequest.risk_level.ilike(lvl)).count() for lvl in risk_levels
    }
    risk_distribution = [
        {"risk": lvl.capitalize(), "value": risk_level_counts[lvl]} for lvl in risk_levels
    ]

    if sum(risk_level_counts.values()) == 0:
        avg_risk_level = "N/A"
    else:
        avg_risk_level = max(risk_level_counts, key=risk_level_counts.get).capitalize()

    # --- Issue Type Distribution (from ai_analysis) ---
    issue_type_counter = Counter()
    all_issues = []
    for pr in pr_query:
        ai_analysis = pr.ai_analysis
        if isinstance(ai_analysis, str):
            try:
                ai_analysis = json.loads(ai_analysis)
            except Exception:
                ai_analysis = None
        if ai_analysis and isinstance(ai_analysis, dict):
            for issue in ai_analysis.get("issues", []):
                issue_type = issue.get("type")
                if issue_type:
                    issue_type_counter[issue_type.lower()] += 1
                    all_issues.append(issue)
            for warning in ai_analysis.get("warnings", []):
                warning_type = warning.get("type")
                if warning_type:
                    issue_type_counter[warning_type.lower()] += 1
                    all_issues.append(warning)
    issue_distribution = [
        {"issue": t.replace("_", " ").capitalize(), "value": c}
        for t, c in issue_type_counter.items()
    ]

    recent_prs = pr_query.order_by(PullRequest.github_created_at.desc()).limit(5).all()
    recent_prs = [
        {
            "id": pr.id,
            "number": pr.number,
            "title": pr.title,
            "status": pr.status,
            "ai_score": pr.ai_score,
            "risk_level": pr.risk_level,
            "ai_review_completed_at": pr.ai_review_completed_at,
            "review_status": pr.review_status,
        }
        for pr in recent_prs
    ]

    ai_score_distribution = []
    for i in range(11):
        count = pr_query.filter(func.floor(PullRequest.ai_score) == i).count()
        ai_score_distribution.append({"score": i, "count": count})

    # --- PR Lifecycle Trend (Opened, Merged, Closed) ---
    # We use a date-range based approach to fill in gaps if necessary, but here we'll just group existing data
    trend_data = {}

    def add_to_trend(date_obj, key):
        if not date_obj: return
        date_str = str(date_obj.date()) if hasattr(date_obj, 'date') else str(date_obj).split(' ')[0]
        if date_str not in trend_data:
            trend_data[date_str] = {"date": date_str, "opened": 0, "merged": 0, "closed": 0}
        trend_data[date_str][key] += 1

    for pr in pr_query:
        if pr.github_created_at:
            add_to_trend(pr.github_created_at, "opened")
        if pr.github_merged_at:
            add_to_trend(pr.github_merged_at, "merged")
        elif pr.github_closed_at:
            add_to_trend(pr.github_closed_at, "closed")

    pr_trend = sorted(trend_data.values(), key=lambda x: x["date"])

    return {
        "repo_count": repo_count,
        "repo_added": repo_added,
        "repo_added_change": repo_added_change,
        "pr_reviewed": pr_reviewed,
        "pr_reviewed_change": pr_reviewed_change,
        "avg_ai_score": round(avg_ai_score, 2),
        "critical_issues": critical_issues,
        "pr_issues": pr_issues,
        "active_issues": active_issues,
        "active_issues_pct": active_issues_pct,
        "avg_review_time": avg_review_time,
        "avg_risk_level": avg_risk_level,
        "ai_score_distribution": ai_score_distribution,
        "pr_trend": pr_trend,
        "risk_distribution": risk_distribution or [],
        "issue_distribution": issue_distribution,
        "all_issues": all_issues,
        "secrets_detected": secrets_detected,
        "infra_issues": infra_issues,
        "security_findings": security_findings,
        "sca_findings": sca_findings,
        "recent_prs": recent_prs,
    }
