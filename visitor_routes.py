from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from database import get_db   # FIX: import shared get_db instead of redefining it
import models, schemas

router = APIRouter(prefix="/visitor", tags=["Visitors"])


@router.post(
    "/create",
    response_model=schemas.VisitorResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_visitor(visitor: schemas.VisitorCreate, db: Session = Depends(get_db)):
    # FIX: validate that logged_by user exists (and is a security guard)
    if visitor.logged_by is not None:
        guard = db.query(models.User).filter(models.User.id == visitor.logged_by).first()
        if not guard:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Security guard with id {visitor.logged_by} not found",
            )
        if guard.role not in ("security", "admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only security personnel can log visitors",
            )

    new_visitor = models.Visitor(
        visitor_name = visitor.visitor_name,
        phone        = visitor.phone,
        flat_no      = visitor.flat_no,
        visitor_type = visitor.visitor_type,
        logged_by    = visitor.logged_by,
        status       = "pending",
    )
    db.add(new_visitor)
    db.commit()
    db.refresh(new_visitor)
    return new_visitor


@router.post("/approve", response_model=schemas.VisitorResponse)
def approve_visitor(data: schemas.VisitorApprove, db: Session = Depends(get_db)):
    visitor = db.query(models.Visitor).filter(models.Visitor.id == data.visitor_id).first()

    # FIX: raise 404 instead of returning {"error": "..."} with HTTP 200
    if not visitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Visitor with id {data.visitor_id} not found",
        )

    # FIX: guard against approving an already-decided visitor
    if visitor.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Visitor request is already '{visitor.status}'",
        )

    visitor.status = data.action   # Literal["approved", "rejected"] — safe
    db.commit()
    db.refresh(visitor)
    return visitor


@router.get("/list", response_model=List[schemas.VisitorResponse])
def list_visitors(
    flat_no : Optional[str] = Query(None, description="Filter by flat number"),
    status  : Optional[str] = Query(None, description="Filter by status: pending/approved/rejected"),
    skip    : int           = Query(0,    ge=0),
    limit   : int           = Query(20,   ge=1, le=100),
    db      : Session       = Depends(get_db),
):
    """List visitors, optionally filtered by flat or status."""
    q = db.query(models.Visitor)
    if flat_no:
        q = q.filter(models.Visitor.flat_no == flat_no)
    if status:
        q = q.filter(models.Visitor.status == status)
    return q.order_by(models.Visitor.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/{visitor_id}", response_model=schemas.VisitorResponse)
def get_visitor(visitor_id: int, db: Session = Depends(get_db)):
    """Fetch a single visitor by ID."""
    visitor = db.query(models.Visitor).filter(models.Visitor.id == visitor_id).first()
    if not visitor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visitor not found")
    return visitor
