# from fastapi import APIRouter, Depends, HTTPException
# from sqlalchemy.orm import Session
# from app.core.database import get_db
# from app.models.infra_finding import InfraFinding

# router = APIRouter()

# @router.get("/")
# def list_infra_findings(db: Session = Depends(get_db)):
#     return db.query(InfraFinding).all()

# @router.get("/{finding_id}")
# def get_infra_finding(finding_id: int, db: Session = Depends(get_db)):
#     finding = db.query(InfraFinding).filter_by(id=finding_id).first()
#     if not finding:
#         raise HTTPException(status_code=404, detail="Infra finding not found")
#     return finding

# # TODO: Add filtering by resource, repo, PR, etc.
