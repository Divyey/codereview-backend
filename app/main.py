from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.database import engine, Base
from app.core.config import settings
from app.api.auth import router as auth_router
from app.api.user import router as user_router
from app.api.pull_requests import router as pull_requests_router
from app.api.repositories import router as repositories_router
from app.api.webhooks import router as webhooks_router 
from app.api.code_quality_issues import router as code_quality_router
from app.api.security_findings import router as security_router
from app.api.dashboard import router as dashboard_router
from app.api.optimized_dashboard import router as optimized_dashboard_router
from app.api.smart_repository import router as smart_repository_router
# from app.api.user_api_keys import router as user_api_keys_router
from app.api.sync import router as sync_router
import logging

logging.basicConfig(
    level=logging.ERROR if settings.ENV == "production" else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s %(message)s"
)

logger = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="CodeReviewPro API",
    description="AI-powered code review and pull request analytics platform",
    version="1.0.0",
    docs_url="/docs" if settings.ENV != "production" else None,  # Hide docs in production
    redoc_url="/redoc" if settings.ENV != "production" else None
)

# Dynamic CORS based on environment
origins = settings.BACKEND_CORS_ORIGINS if settings.ENV == "production" else [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:8000",
    "http://localhost:5175",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],  # Specific methods instead of *
    allow_headers=["*"],
)

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if settings.ENV == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# Request size limit middleware
@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    content_length = request.headers.get('content-length')
    if content_length and int(content_length) > 10_000_000:  # 10MB limit
        return JSONResponse(
            status_code=413,
            content={"detail": "Request too large"}
        )
    return await call_next(request)

# user_router removed - duplicate of repositories_router endpoints (user.py contains repository CRUD, which is already handled by repositories_router)
# app.include_router(user_router)
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(pull_requests_router, prefix="/api/pull_requests", tags=["pull_requests"])
app.include_router(repositories_router, prefix="/api/repositories", tags=["repositories"])
app.include_router(smart_repository_router, prefix="/api/smart-repositories", tags=["smart-repositories"])
app.include_router(webhooks_router, prefix="/api/webhooks", tags=["webhooks"])
app.include_router(code_quality_router, prefix="/api/code-quality-issues", tags=["Code Quality"])
app.include_router(security_router, prefix="/api/security-findings", tags=["Security"])
app.include_router(dashboard_router, prefix="/api", tags=["dashboard"])
app.include_router(optimized_dashboard_router, prefix="/api", tags=["optimized-dashboard"])
# app.include_router(user_api_keys_router)
app.include_router(sync_router, prefix="/api", tags=["sync"])

# Startup validation
@app.on_event("startup")
async def validate_environment():
    required_vars = ["DATABASE_URL", "SECRET_KEY", "FERNET_KEY", "OPENAI_API_KEY"]
    missing = [var for var in required_vars if not getattr(settings, var, None)]
    if missing:
        logger.critical(f"Missing required environment variables: {missing}")
        raise RuntimeError(f"Missing required environment variables: {missing}")
    logger.info(f"Application starting in {settings.ENV} mode")

@app.get("/")
def read_root():
    logger.info("Root endpoint accessed")
    return {"message": "CodeReviewPro API", "version": "1.0.0", "status": "healthy"}

@app.get("/health")
def health_check():
    return {"status": "healthy", "environment": settings.ENV}
