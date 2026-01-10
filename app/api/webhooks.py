from fastapi import APIRouter, Request, BackgroundTasks, Depends, HTTPException, Header
from sqlalchemy.orm import Session
import hmac
import hashlib
import logging
from datetime import datetime
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.models.pr_file import PRFile
from app.models.pull_request_analysis_history import PullRequestAnalysisHistory
from app.models.branch import Branch
from app.models.commit import Commit
from app.services.github_service import GitHubService
from app.services.ai_service import AIService
import json
from app.models.webhook import WebhookEvent
from app.models.contributor import Contributor 
from app.models.code_quality_issue import CodeQualityIssue
from app.models.secret_finding import SecretFinding
from app.models.infra_finding import InfraFinding
from app.models.sca_finding import SCAFinding
from app.models.security_finding import SecurityFinding
import logging

router = APIRouter()

logger = logging.getLogger(__name__)

def log_webhook_event(db, event_type, delivery_id, signature, payload):
    event = WebhookEvent(
        event_type=event_type,
        delivery_id=delivery_id,
        signature=signature,
        payload=payload,  # already dict, SQLAlchemy will handle JSONB
        processed=False,
        status="received"
    )
    db.add(event)
    db.commit()
    return event

def checkpoint(msg):
    logger.info(f"CHECKPOINT: {msg}")

def verify_github_signature(secret: str, body: bytes, signature: str) -> bool:
    """
    Verifies the GitHub webhook HMAC SHA-256 signature.

    Args:
        secret (str): The webhook secret.
        body (bytes): The raw request body.
        signature (str): The value of the 'X-Hub-Signature-256' header.

    Returns:
        bool: True if the signature is valid, False otherwise.
    """
    if not signature:
        return False
    try:
        sha_name, signature_hash = signature.split('=')
        if sha_name != 'sha256':
            # Only support sha256 as per GitHub's current recommendation
            return False
        # Compute HMAC SHA-256 using the secret and request body
        mac = hmac.new(secret.encode(), msg=body, digestmod=hashlib.sha256)
        # Use compare_digest for constant-time comparison to prevent timing attacks
        return hmac.compare_digest(mac.hexdigest(), signature_hash)
    except Exception as e:
        print(f"Signature verification error: {e}")
        return False

def get_or_create_contributor(db, github_id, login, email=None, avatar_url=None):
    contributor = db.query(Contributor).filter_by(github_id=github_id).first()
    if not contributor:
        contributor = Contributor(
            github_id=github_id,
            login=login,
            email=email,
            avatar_url=avatar_url
        )
        db.add(contributor)
        db.commit()
        db.refresh(contributor)
    return contributor

# --- Background Analysis Tasks ---

async def analyze_pr_background(pr_id: int, commit_sha: str, db):
    checkpoint("🚀 AI Analysis Background Task Started")
    logger.info(f"🔍 Fetching PR {pr_id} for analysis")
    pr = db.query(PullRequest).filter(PullRequest.id == pr_id).first()
    if not pr:
        logger.error("❌ PR not found for AI analysis")
        return

    ai_service = AIService()
    ai_model = getattr(ai_service, "model_name", "gpt-4o")

    # Prepare file data for the AI
    files_data = [
        {
            "filename": file.filename,
            "additions": file.additions,
            "deletions": file.deletions,
            "content": file.content
        }
        for file in pr.files
    ]

    logger.info(f"🤖 Starting AI analysis for PR {pr_id} with model {ai_model}")
    ai_review_started_at = datetime.utcnow()
    analysis = await ai_service.analyze_code(files_data)
    if not analysis:
        logger.error("❌ AI analysis failed or returned empty result")
        return
    ai_review_completed_at = datetime.utcnow()
    ai_review_time_seconds = (ai_review_completed_at - ai_review_started_at).total_seconds()

    # --- Update PR with AI analysis results ---
    pr.ai_review_started_at = ai_review_started_at
    pr.ai_review_completed_at = ai_review_completed_at
    pr.ai_review_time_seconds = ai_review_time_seconds

    pr.ai_score = analysis.get("ai_score")
    pr.risk_level = analysis.get("risk_level")
    pr.issue_count = analysis.get("issue_count")
    pr.warning_count = analysis.get("warning_count")
    pr.ai_analysis = analysis

    print("\n========== Saving code quality issues for PR ==========")
    # Build file_id_map ONCE before the loop
    file_id_map = {file.filename: file.id for file in pr.files}

    from app.models.code_quality_issue import CodeQualityIssue
    db.query(CodeQualityIssue).filter(CodeQualityIssue.pull_request_id == pr.id).delete()
    count = 0
    for issue in analysis.get("issues", []):
        file_path = issue.get("file") or issue.get("path")
        # Support both int and dict for line
        line_info = issue.get("line")
        if isinstance(line_info, dict):
            line_start = line_info.get("start")
            line_end = line_info.get("end")
            line = line_start
        else:
            line_start = line_end = line = line_info

        new_issue = CodeQualityIssue(
            repo_id=pr.repository_id,
            pull_request_id=pr.id,
            file_id=file_id_map.get(file_path),
            # file_id_map = {file.filename: file.id for file in pr.files},
            # file_id=file_id_map.get(file_path),
            type=issue.get("type"),
            function_name=issue.get("function_name"),
            line=line,
            line_start=line_start,
            line_end=line_end,
            severity=issue.get("severity"),
            message=issue.get("message"),
            suggestion=issue.get("suggestion"),
            path=file_path
        )
        db.add(new_issue)
        count += 1

    db.commit()

    print(f"✅ {count} code quality issues saved for PR #{pr.id}\n")

    # --- Update reviewers and review status ---
    reviewers = pr.reviewers or []
    if not any(r.get("type") == "AI" for r in reviewers):
        reviewers.append({"type": "AI", "model": ai_model})
    pr.reviewers = reviewers
    pr.review_status = "AI only" if not any(r.get("type") == "Human" for r in reviewers) else "AI + Human"
    db.commit()

    logger.info(f"✅ AI analysis for PR {pr_id} complete in {ai_review_time_seconds:.2f}s, storing analysis history")

    # --- Store analysis in history ---
    analysis_history = PullRequestAnalysisHistory(
        pull_request_id=pr.id,
        commit_sha=commit_sha,
        analyzed_at=datetime.utcnow(),
        ai_score=analysis.get("ai_score"),
        risk_level=analysis.get("risk_level"),
        issues=analysis.get("issues", []),
        warnings=analysis.get("warnings", []),
        recommendations=analysis.get("recommendations", []),
        summary=analysis.get("summary", ""),
        reviewer=f"AI ({ai_model})"
    )
    db.add(analysis_history)
    db.commit()
    logger.info(f"📦 Analysis history for PR {pr_id} stored.\n")

     # --- Extract and save findings from AI analysis ---
    for issue in analysis.get("issues", []):
        file_id = None
        if issue.get("file"):
            pr_file = db.query(PRFile).filter_by(
                pull_request_id=pr.id,
                filename=issue["file"]
            ).first()
            if pr_file:
                file_id = pr_file.id

        # SecurityFinding (always)
        sec = SecurityFinding(
            pull_request_id=pr.id,
            repo_id=pr.repository_id,
            file_id=file_id,
            type=issue.get("type"),
            issue_type=issue.get("type"),
            severity=issue.get("severity"),
            description=issue.get("message"),
            line=issue.get("line"),
        )
        db.add(sec)

        # SecretFinding (if type == "secret")
        if issue.get("type") == "secret":
            secret = SecretFinding(
                pull_request_id=pr.id,
                repo_id=pr.repository_id,
                file_id=file_id,
                secret_type=issue.get("type"),
                severity=issue.get("severity"),
                message=issue.get("message"),
                line=issue.get("line"),
            )
            db.add(secret)

        # InfraFinding (if type == "infra")
        if issue.get("type") == "infra":
            infra = InfraFinding(
                pull_request_id=pr.id,
                repo_id=pr.repository_id,
                file_id=file_id,
                issue_type=issue.get("type"),
                severity=issue.get("severity"),
                message=issue.get("message"),
                line=issue.get("line"),
            )
            db.add(infra)

        # SCAFinding (if type == "sca")
        if issue.get("type") == "sca":
            sca = SCAFinding(
                pull_request_id=pr.id,
                repo_id=pr.repository_id,
                package=issue.get("package"),
                version=issue.get("version"),
                vulnerability_id=issue.get("vulnerability_id"),
                severity=issue.get("severity"),
                message=issue.get("message"),
                recommendation=issue.get("suggestion"),
            )
            db.add(sca)

    db.commit()


async def analyze_branch_background(repository_id: int, branch_name: str, db):
    checkpoint(f"🚀 Background analysis for repo {repository_id}, branch '{branch_name}' started")
    logger.info(f"Analyzing branch '{branch_name}' in repo {repository_id}")

    # Fetch the repository and branch
    repo = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repo:
        logger.error(f"❌ Repository {repository_id} not found")
        return

    branch = db.query(Branch).filter(
        Branch.repository_id == repository_id,
        Branch.name == branch_name
    ).first()
    if not branch:
        logger.error(f"❌ Branch '{branch_name}' not found in repository {repository_id}")
        return

    # Get the latest commits (limit for cost control, e.g. last 5)
    commits = db.query(Commit).filter(
        Commit.repository_id == repository_id,
        Commit.branch_id == branch.id 
    ).order_by(Commit.timestamp.desc()).limit(5).all()  
    if not commits:
        logger.warning(f"⚠️ No commits found on branch '{branch_name}' in repository {repository_id}")
        return

    # Find the latest PR for this branch and repo
    pr = db.query(PullRequest).filter(
        PullRequest.branch == branch_name,
        PullRequest.repository_id == repository_id
    ).order_by(PullRequest.github_created_at.desc()).first()

    files_data = []
    if pr and pr.files:
        for file in pr.files:
            files_data.append({
                "filename": file.filename,
                "additions": file.additions,
                "deletions": file.deletions,
                "content": file.content
            })
    else:
        logger.warning(f"No PR or files found for branch '{branch_name}' in repository {repository_id}")
        return


    # Run AI analysis
    ai_service = AIService()
    ai_model = getattr(ai_service, "model_name", "gpt-4o")
    ai_review_started_at = datetime.utcnow()
    analysis = await ai_service.analyze_code(files_data)
    ai_review_completed_at = datetime.utcnow()
    ai_review_time_seconds = (ai_review_completed_at - ai_review_started_at).total_seconds()

    logger.info(f"✅ AI analysis for branch '{branch_name}' complete in {ai_review_time_seconds:.2f}s, storing analysis history")

    print("\n========== Saving code quality issues for Branch Analysis ==========")
    from app.models.code_quality_issue import CodeQualityIssue
    db.query(CodeQualityIssue).filter(
        CodeQualityIssue.repo_id == repository_id,
        CodeQualityIssue.path.in_([f["filename"] for f in files_data])
    ).delete(synchronize_session=False)
    count = 0
    for issue in analysis.get("issues", []):
        db_issue = CodeQualityIssue(
            repo_id=repository_id,
            pull_request_id=None,
            file_id=None,
            type=issue.get("type"),
            function_name=issue.get("function_name"),
            line=issue.get("line"),
            severity=issue.get("severity"),
            message=issue.get("message"),
            suggestion=issue.get("suggestion"),
            maintainability_index=issue.get("maintainability_index"),
            confidence=issue.get("confidence"),
            path=issue.get("file")
        )
        db.add(db_issue)
        count += 1
    db.commit()
    print(f"✅ {count} code quality issues saved for branch '{branch_name}'\n")


    # Store analysis in PullRequestAnalysisHistory for branch (use a special pull_request_id or add a branch_id field)
    branch_analysis_history = PullRequestAnalysisHistory(
        pull_request_id=None,  # or use a dedicated field if you want to relate to branches
        commit_sha=latest_commit.sha,
        analyzed_at=datetime.utcnow(),
        ai_score=analysis.get("ai_score"),
        risk_level=analysis.get("risk_level"),
        issues=analysis.get("issues", []),
        warnings=analysis.get("warnings", []),
        recommendations=analysis.get("recommendations", []),
        summary=analysis.get("summary", ""),
        reviewer=f"AI ({ai_model})",
        branch_name=branch_name  # Add this field if your model supports it
    )
    db.add(branch_analysis_history)
    db.commit()
    logger.info(f"📦 Branch analysis history for '{branch_name}' stored.\n")

# --- Modular Event Handlers ---

async def handle_pull_request_event(payload, background_tasks, db):
    action = payload.get("action")
    pr_data = payload.get("pull_request")
    repo_data = payload.get("repository")
    if not pr_data or not repo_data:
        logger.warning("⚠️ Not a pull_request event")
        return {"msg": "Not a pull_request event"}
    logger.info(f"📝 Webhook action: {action}")
    if action not in ["opened", "synchronize", "reopened", "closed"]:
        logger.info(f"⏩ Ignored action: {action}")
        return {"msg": f"Ignored action: {action}"}
    owner = repo_data["owner"]["login"]
    repo_name = repo_data["name"]
    pr_number = pr_data["number"]
    logger.info(f"📦 Processing PR #{pr_number} in {owner}/{repo_name}")
    checkpoint(f"📥 Importing PR #{pr_number}")

    # --- Contributor tracking: Add here, just after extracting pr_data ---
    pr_user = pr_data.get("user", {})
    contributor = None
    if pr_user:
        contributor = get_or_create_contributor(
            db,
            github_id=pr_user.get("id"),
            login=pr_user.get("login"),
            email=None,  # GitHub API does not always provide email for PR user
            avatar_url=pr_user.get("avatar_url")
        )
    # --- End contributor tracking ---
    
    user = db.query(User).first()
    if not user:
        logger.error("❌ No user found in DB")
        raise HTTPException(status_code=404, detail="No user found")
    github_service = GitHubService(user.github_token or settings.GITHUB_TOKEN)
    pr_info = await github_service.get_pull_request(owner, repo_name, pr_number)
    repo_full_name = f"{owner}/{repo_name}"
    repository = db.query(Repository).filter(Repository.full_name == repo_full_name).first()
    if not repository:
        logger.info("📚 Repository not found in DB, fetching from GitHub")
        repo_info = await github_service.get_repository(owner, repo_name)
        if not repo_info:
            logger.error("❌ Repository not found on GitHub")
            raise HTTPException(status_code=404, detail="Repository not found")
        repository = Repository(
            name=repo_name,
            full_name=repo_full_name,
            description=repo_info.get("description"),
            github_id=repo_info["id"],
            url=repo_info["html_url"],
            default_branch=repo_info["default_branch"],
            is_private=repo_info["private"],
            owner_id=user.id
        )
        db.add(repository)
        db.commit()
        db.refresh(repository)
    pr = db.query(PullRequest).filter(
        PullRequest.repository_id == repository.id,
        PullRequest.number == pr_number
    ).first()
    if not pr:
        logger.info("🆕 PR not found in DB, creating new PR record")
        pr = PullRequest(
            number=pr_number,
            title=pr_info["title"],
            description=pr_info.get("body"),
            branch=pr_info["head"]["ref"],
            status="merged" if pr_info.get("merged") else ("closed" if pr_info.get("closed_at") else "open"),
            github_id=pr_info["id"],
            github_url=pr_info["html_url"],
            github_author=pr_info.get("user", {}).get("login"),
            repository_id=repository.id,
            author_id=user.id,
            files_changed=pr_info.get("changed_files", 0),
            lines_added=pr_info.get("additions", 0),
            lines_deleted=pr_info.get("deletions", 0),
            github_created_at=datetime.fromisoformat(pr_info["created_at"].replace("Z", "+00:00")) if pr_info.get("created_at") else None,
            github_updated_at=datetime.fromisoformat(pr_info["updated_at"].replace("Z", "+00:00")) if pr_info.get("updated_at") else None,
            github_closed_at=datetime.fromisoformat(pr_info["closed_at"].replace("Z", "+00:00")) if pr_info.get("closed_at") else None,
            github_merged_at=datetime.fromisoformat(pr_info["merged_at"].replace("Z", "+00:00")) if pr_info.get("merged_at") else None,
            review_status="AI only",
            reviewers=[{"type": "AI", "model": "gpt-4o"}]
        )
        db.add(pr)
        db.commit()
        db.refresh(pr)
    else:
        # Update existing PR status and timestamps
        changed = False
        new_status = "merged" if pr_info.get("merged") else ("closed" if pr_info.get("closed_at") else "open")
        if pr.status != new_status:
            pr.status = new_status
            changed = True
        
        if pr_info.get("closed_at") and not pr.github_closed_at:
            pr.github_closed_at = datetime.fromisoformat(pr_info["closed_at"].replace("Z", "+00:00"))
            changed = True
        
        if pr_info.get("merged_at") and not pr.github_merged_at:
            pr.github_merged_at = datetime.fromisoformat(pr_info["merged_at"].replace("Z", "+00:00"))
            changed = True

        if pr_info.get("title") != pr.title:
            pr.title = pr_info["title"]
            changed = True

        if changed:
            db.add(pr)
            db.commit()
            logger.info(f"✅ Updated PR #{pr_number} status to {new_status}")

    # If action is 'closed', we don't necessarily need to re-analyze files
    if action == "closed":
        return {"msg": f"PR {pr_number} marked as {pr.status}"}

    commit_sha = pr_info["head"]["sha"]
    logger.info(f"📂 Fetching PR files for PR #{pr_number}")
    files_data = await github_service.get_pull_request_files(owner, repo_name, pr_number)
    ai_service = AIService()

    # Delete code quality issues referencing these PR files
    pr_file_ids = [f.id for f in pr.files]
    if pr_file_ids:
        db.query(CodeQualityIssue).filter(CodeQualityIssue.file_id.in_(pr_file_ids)).delete(synchronize_session=False)
    db.query(PRFile).filter(PRFile.pull_request_id == pr.id).delete(synchronize_session=False)

    # db.query(PRFile).filter(PRFile.pull_request_id == pr.id).delete()
    for file_data in files_data:
        content = await github_service.get_file_content(
            owner, repo_name, file_data["filename"], pr_info["head"]["sha"]
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
    logger.info(f"✅ Files for PR #{pr_number} stored")
    checkpoint(f"🤖 Starting AI analysis for PR #{pr_number}")
    background_tasks.add_task(analyze_pr_background, pr.id, commit_sha, db)
    logger.info(f"🏁 Webhook processing for PR #{pr_number} complete!\n")
    return {"msg": "Pull request imported and analysis started", "pr_id": pr.id, "commit_sha": commit_sha}

async def handle_push_event(payload, background_tasks, db):
    logger.info("Received push event")
    repo_data = payload.get("repository", {})
    repo_full_name = repo_data.get("full_name")
    ref = payload.get("ref")  # e.g., "refs/heads/main"
    branch_name = ref.split("/")[-1] if ref else None
    commits = payload.get("commits", [])
    pusher = payload.get("pusher", {}).get("name")
    commit_count = len(commits)
    logger.info(f"Push to {branch_name} in {repo_full_name} by {pusher} with {commit_count} commits.")

    # --- STEP 1: Look up repository in your DB ---
    repository = db.query(Repository).filter(Repository.full_name == repo_full_name).first()
    if not repository:
        logger.error(f"Repository {repo_full_name} not found in DB. Cannot process webhook.")
        raise HTTPException(status_code=404, detail="Repository not found in this app. Please add it first.")

    # --- STEP 2: Get the owner of the repo (the user who added it in your app) ---
    owner = db.query(User).filter(User.id == repository.owner_id).first()
    if not owner:
        logger.error("Repo owner not found in DB!")
        raise HTTPException(status_code=404, detail="Repo owner not found")

    # --- STEP 3: Use owner's GitHub token (or fallback to global token) ---
    github_service = GitHubService(owner.github_token or settings.GITHUB_TOKEN)
    logger.info(f"Using GitHub token for user {owner.email} (id={owner.id})")

    # --- STEP 4: Find or create branch record ---
    branch = db.query(Branch).filter(
        Branch.name == branch_name,
        Branch.repository_id == repository.id
    ).first()
    if not branch:
        branch = Branch(
            name=branch_name,
            repository_id=repository.id,
            last_commit_sha=commits[-1]["id"] if commits else None,
            last_pushed_at=datetime.utcnow()
        )
        db.add(branch)
        db.commit()
        db.refresh(branch)
    else:
        branch.last_commit_sha = commits[-1]["id"] if commits else branch.last_commit_sha
        branch.last_pushed_at = datetime.utcnow()
        db.commit()

    # --- STEP 5: Store commits ---
    for commit_data in commits:
        commit = db.query(Commit).filter(Commit.sha == commit_data["id"]).first()
        if not commit:
            commit = Commit(
                sha=commit_data["id"],
                message=commit_data["message"],
                author_name=commit_data["author"]["name"],
                author_email=commit_data["author"]["email"],
                timestamp=datetime.strptime(commit_data["timestamp"], "%Y-%m-%dT%H:%M:%S%z"),
                branch_id=branch.id,
                repository_id=repository.id
            )
            db.add(commit)
    db.commit()

    # --- STEP 6: Optionally trigger background AI analysis for this branch ---
    background_tasks.add_task(analyze_branch_background, repository.id, branch_name, db)

    return {
        "msg": f"Push event processed for {repo_full_name} on branch {branch_name} with {commit_count} commits."
    }

# --- Main Webhook Route ---

@router.post("/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    x_hub_signature_256: str = Header(None),
    x_github_event: str = Header(None)
):
    checkpoint("🔔 GitHub Webhook Received")
    body = await request.body()
    secret = settings.GITHUB_WEBHOOK_SECRET
    if not verify_github_signature(secret, body, x_hub_signature_256):
        logger.error("❌ Invalid GitHub webhook signature")
        raise HTTPException(status_code=403, detail="Invalid GitHub webhook signature")
    print("\n========== 🛡️ Webhook Signature Verified ==========")
    logger.info("🔑 Signature verified")
    payload = await request.json()
    # Storing the webhook event in the database
    event = WebhookEvent(
        event_type=x_github_event or payload.get("action") or "unknown",
        payload=payload,
        received_at=datetime.utcnow()
        # repository_id can be set if you extract it from payload, else leave None
    )
    db.add(event)
    db.commit()
    
    if x_github_event == "pull_request":
        return await handle_pull_request_event(payload, background_tasks, db)
    elif x_github_event == "push":
        return await handle_push_event(payload, background_tasks, db)
    else:
        logger.info(f"Unhandled event: {x_github_event}")
        return {"msg": f"Unhandled event: {x_github_event}"}
