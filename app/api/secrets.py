from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.secret_finding import SecretFinding

router = APIRouter()

@router.get("/")
def list_secret_findings(db: Session = Depends(get_db)):
    return db.query(SecretFinding).all()

@router.get("/{finding_id}")
def get_secret_finding(finding_id: int, db: Session = Depends(get_db)):
    finding = db.query(SecretFinding).filter_by(id=finding_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Secret finding not found")
    return finding

# TODO: Add filtering by secret_type, repo, PR, etc.
