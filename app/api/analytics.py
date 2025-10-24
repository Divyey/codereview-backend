# CODE QUALITY DASHBOARD

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.core.database import get_db
from app.models.user import User
from app.models.repository import Repository
from app.models.pull_request_analysis_history import PullRequestAnalysisHistory
from app.api.auth import get_current_user

router = APIRouter()

@router.get("/analytics/code-quality")
def code_quality_analytics(
    repo_id: int,
    branch: str = None,
    days: int = 7,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # --- Multi-user security: Only allow analytics for user's own repos ---
    repo = db.query(Repository).filter(
        Repository.id == repo_id,
        Repository.owner_id == current_user.id
    ).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    now = datetime.utcnow()
    since = now - timedelta(days=days)
    prev_since = since - timedelta(days=days)
    prev_until = since

    # Helper to count issues by type in a period
    def count_issues(since, until):
        q = db.query(PullRequestAnalysisHistory).filter(
            PullRequestAnalysisHistory.analyzed_at >= since,
            PullRequestAnalysisHistory.analyzed_at < until,
            PullRequestAnalysisHistory.repository_id == repo_id
        )
        if branch:
            q = q.filter(PullRequestAnalysisHistory.branch_name == branch)
        issues = []
        for h in q.all():
            issues.extend(h.issues or [])
        def count_type(t):
            return sum(1 for i in issues if i.get("type") == t)
        return {
            "docstring_absent": count_type("docstring_absent"),
            "complex_function": count_type("complex_function"),
            "antipattern": sum(1 for i in issues if i.get("type") == "antipattern" or i.get("category") == "bug"),
            "dead_code": count_type("dead_code"),
            "duplicate_code": count_type("duplicate_code"),
            "code_suggestions": sum(len(h.recommendations or []) for h in q.all())
        }
    current = count_issues(since, now)
    previous = count_issues(prev_since, prev_until)

    def percent_change(curr, prev):
        if prev == 0:
            return 100 if curr > 0 else 0
        return round((curr - prev) / prev * 100)

    metrics = [
        {
            "title": "Functions missing docstrings",
            "value": current["docstring_absent"],
            "percentChange": percent_change(current["docstring_absent"], previous["docstring_absent"])
        },
        {
            "title": "Complex functions",
            "value": current["complex_function"],
            "percentChange": percent_change(current["complex_function"], previous["complex_function"])
        },
        {
            "title": "Antipatterns/Bugs detected",
            "value": current["antipattern"],
            "percentChange": percent_change(current["antipattern"], previous["antipattern"])
        },
        {
            "title": "Dead code instances",
            "value": current["dead_code"],
            "percentChange": percent_change(current["dead_code"], previous["dead_code"])
        },
        {
            "title": "Duplicate code regions",
            "value": current["duplicate_code"],
            "percentChange": percent_change(current["duplicate_code"], previous["duplicate_code"])
        },
        {
            "title": "AI code suggestions given",
            "value": current["code_suggestions"],
            "percentChange": percent_change(current["code_suggestions"], previous["code_suggestions"])
        }
    ]
    return {"metrics": metrics}
# ===========================================
# from fastapi import APIRouter, Depends, Query
# from sqlalchemy.orm import Session
# from sqlalchemy import func
# from datetime import datetime, timedelta
# from typing import Optional
# from ..core.database import get_db
# from ..models.user import User
# from ..models.pull_request import PullRequest
# from ..models.pull_request_analysis_history import PullRequestAnalysisHistory

# router = APIRouter(prefix="/api/analytics", tags=["analytics"])

# @router.get("/summary")
# def get_dashboard_summary(
#     project_id: Optional[int] = Query(None),
#     db: Session = Depends(get_db)
# ):
#     base_query = db.query(PullRequest).join(Repository, PullRequest.repository_id == Repository.id)
#     if project_id:
#         base_query = base_query.filter(PullRequest.project_id == project_id)
#     else:
#         base_query = base_query.filter(Repository.owner_id == current_user.id)
#     # base_query = db.query(PullRequest)
#     if project_id:
#         base_query = base_query.filter(PullRequest.project_id == project_id)
#     total_prs = base_query.count()
#     ai_reviewed_prs = base_query.filter(PullRequest.review_status.ilike("%AI%")).count()
#     ai_review_time = base_query.with_entities(func.sum(PullRequest.ai_review_time_seconds)).scalar() or 0
#     user_review_time = base_query.with_entities(func.sum(PullRequest.user_review_time_minutes)).scalar() or 0
#     total_issues = base_query.with_entities(func.sum(PullRequest.issue_count)).scalar() or 0
#     total_warnings = base_query.with_entities(func.sum(PullRequest.warning_count)).scalar() or 0
#     return {
#         "total_prs": total_prs,
#         "ai_reviewed_prs": ai_reviewed_prs,
#         "ai_review_time_seconds": int(ai_review_time),
#         "user_review_time_minutes": int(user_review_time),
#         "total_issues": int(total_issues),
#         "total_warnings": int(total_warnings)
#     }

# @router.get("/pr-timeline")
# def pr_timeline(
#     project_id: Optional[int] = Query(None),
#     db: Session = Depends(get_db)
# ):
#     prs = db.query(PullRequest)
#     if project_id:
#         prs = prs.filter(PullRequest.project_id == project_id)
#     prs = prs.all()
#     timeline = {}
#     for pr in prs:
#         date = pr.created_at.strftime("%Y-%m-%d")
#         pr_type = getattr(pr, "pr_type", "New")
#         if date not in timeline:
#             timeline[date] = {"date": date, "New": 0, "Added": 0, "Improved": 0, "Fixed": 0}
#         timeline[date][pr_type] = timeline[date].get(pr_type, 0) + 1
#     return sorted(timeline.values(), key=lambda d: d["date"])

# @router.get("/pr-type-distribution")
# def pr_type_distribution(
#     project_id: Optional[int] = Query(None),
#     db: Session = Depends(get_db)
# ):
#     prs = db.query(PullRequest)
#     if project_id:
#         prs = prs.filter(PullRequest.project_id == project_id)
#     prs = prs.all()
#     type_counts = {"New": 0, "Added": 0, "Improved": 0, "Fixed": 0}
#     for pr in prs:
#         pr_type = getattr(pr, "pr_type", "New")
#         type_counts[pr_type] = type_counts.get(pr_type, 0) + 1
#     total = sum(type_counts.values()) or 1
#     return [
#         {"type": t, "count": c, "percent": round(100 * c / total, 2)}
#         for t, c in type_counts.items()
#     ]

# @router.get("/risk-distribution")
# def risk_distribution(
#     project_id: Optional[int] = Query(None),
#     db: Session = Depends(get_db)
# ):
#     base_query = db.query(PullRequest)
#     if project_id:
#         base_query = base_query.filter(PullRequest.project_id == project_id)
#     total = base_query.count() or 1
#     risk_counts = base_query.with_entities(PullRequest.risk_level, func.count(PullRequest.id)).group_by(PullRequest.risk_level)
#     return [
#         {"risk": risk or "unknown", "count": count, "percent": round(100 * count / total, 2)}
#         for risk, count in risk_counts
#     ]

# @router.get("/ai-score-distribution")
# def ai_score_distribution(
#     project_id: Optional[int] = Query(None),
#     db: Session = Depends(get_db)
# ):
#     bins = [
#         (0, 6, "0-6"),
#         (6, 8, "6-8"),
#         (8, 11, "8-10"),
#     ]
#     result = []
#     for low, high, label in bins:
#         query = db.query(func.count(PullRequest.id)).filter(
#             PullRequest.ai_score >= low,
#             PullRequest.ai_score < high
#         )
#         if project_id:
#             query = query.filter(PullRequest.project_id == project_id)
#         result.append({"range": label, "count": query.scalar()})
#     return result

# @router.get("/review-time-distribution")
# def review_time_distribution(
#     project_id: Optional[int] = Query(None),
#     db: Session = Depends(get_db)
# ):
#     q = db.query(
#         func.avg(PullRequest.ai_review_time_seconds).label("ai_avg"),
#         func.avg(PullRequest.user_review_time_minutes).label("manual_avg")
#     )
#     if project_id:
#         q = q.filter(PullRequest.project_id == project_id)
#     row = q.first()
#     return [
#         {"type": "AI", "avg_time": round(row.ai_avg or 0, 2)},
#         {"type": "Manual", "avg_time": round(row.manual_avg or 0, 2)},
#     ]

# @router.get("/issue-breakdown")
# def issue_breakdown(
#     project_id: Optional[int] = Query(None),
#     db: Session = Depends(get_db)
# ):
#     query = db.query(PullRequestAnalysisHistory.issues)
#     if project_id:
#         query = query.join(PullRequest, PullRequestAnalysisHistory.pull_request_id == PullRequest.id)
#         query = query.filter(PullRequest.project_id == project_id)
#     type_counts = {}
#     total = 0
#     for row in query:
#         issues = row.issues or []
#         for issue in issues:
#             issue_type = issue.get("type", "Other")
#             type_counts[issue_type] = type_counts.get(issue_type, 0) + 1
#             total += 1
#     return [
#         {"type": t, "count": c, "percent": round(100 * c / total, 2) if total else 0}
#         for t, c in type_counts.items()
#     ]

# @router.get("/contributors")
# def active_contributors(
#     project_id: Optional[int] = Query(None),
#     db: Session = Depends(get_db)
# ):
#     query = db.query(
#         User.username,
#         func.count(PullRequest.id).label("prs")
#     ).join(PullRequest, PullRequest.author_id == User.id)
#     if project_id:
#         query = query.filter(PullRequest.project_id == project_id)
#     query = query.group_by(User.username).order_by(func.count(PullRequest.id).desc()).limit(10)
#     return [{"name": row.username, "prs": row.prs} for row in query]

# @router.get("/lines-stacked")
# def lines_stacked(
#     period: str = Query("weekly", enum=["weekly", "monthly"]),
#     project_id: Optional[int] = Query(None),
#     db: Session = Depends(get_db)
# ):
#     now = datetime.utcnow()
#     if period == "weekly":
#         start = now - timedelta(weeks=12)
#         label_func = func.strftime("%Y-%W", PullRequest.created_at)
#     else:
#         start = now - timedelta(weeks=52)
#         label_func = func.strftime("%Y-%m", PullRequest.created_at)
#     query = db.query(
#         label_func.label("period"),
#         func.sum(PullRequest.lines_added).label("added"),
#         func.sum(PullRequest.lines_deleted).label("deleted"),
#     ).filter(PullRequest.created_at >= start)
#     if project_id:
#         query = query.filter(PullRequest.project_id == project_id)
#     query = query.group_by("period").order_by("period")
#     return [
#         {
#             "period": row.period,
#             "added": row.added or 0,
#             "deleted": row.deleted or 0,
#         }
#         for row in query
#     ]
