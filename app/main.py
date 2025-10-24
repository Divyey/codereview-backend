from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import engine, Base
from app.api.auth import router as auth_router
from app.api.user import router as user_router
from app.api.pull_requests import router as pull_requests_router
from app.api.repositories import router as repositories_router
from app.api.webhooks import router as webhooks_router 
from app.api.code_quality_issues import router as code_quality_router
from app.api.security_findings import router as security_router
from app.api.dashboard import router as dashboard_router
import logging

logging.basicConfig(
    level=logging.INFO,  # Change to ERROR in production
    format="%(asctime)s [%(levelname)s] %(message)s"
)

logger = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="CodeReviewPro API",
    description="AI-powered code review and pull request analytics platform",
    version="1.0.0"
)

origins = [
    "http://localhost:5173",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user_router)
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
# app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(pull_requests_router, prefix="/api/pull_requests", tags=["pull_requests"])
app.include_router(repositories_router, prefix="/api/repositories", tags=["repositories"])
app.include_router(webhooks_router, prefix="/api/webhooks", tags=["webhooks"])
app.include_router(code_quality_router, prefix="/api/code-quality-issues", tags=["Code Quality"])
app.include_router(security_router, prefix="/api/security-findings", tags=["Security"])
app.include_router(dashboard_router, prefix="/api", tags=["dashboard"])

@app.get("/")
def read_root():
    logger.info("Root endpoint accessed")
    return {"message": "CodeReviewPro API", "version": "1.0.0"}

@app.get("/health")
def health_check():
    logger.info("Health check endpoint accessed")
    return {"status": "healthy"}
