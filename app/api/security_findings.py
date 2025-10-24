from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.security_finding import SecurityFinding

router = APIRouter()

@router.get("/")
def list_security_findings(db: Session = Depends(get_db)):
    return db.query(SecurityFinding).all()

@router.get("/{finding_id}")
def get_security_finding(finding_id: int, db: Session = Depends(get_db)):
    finding = db.query(SecurityFinding).filter_by(id=finding_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Security finding not found")
    return finding

# TODO: Add filtering by type, repo, PR, etc.
