from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.sca_finding import SCAFinding

router = APIRouter()

@router.get("/")
def list_sca_findings(db: Session = Depends(get_db)):
    return db.query(SCAFinding).all()

@router.get("/{finding_id}")
def get_sca_finding(finding_id: int, db: Session = Depends(get_db)):
    finding = db.query(SCAFinding).filter_by(id=finding_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="SCA finding not found")
    return finding

# TODO: Add filtering by package, repo, PR, etc.

