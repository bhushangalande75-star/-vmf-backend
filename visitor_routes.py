from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from database import get_db
import models, schemas

router = APIRouter(prefix="/visitor", tags=["Visitors"])

def _date_filter(q, model, period: str):
    now = datetime.now(timezone.utc)
    if period == "day":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        start = now - timedelta(days=now.weekday())
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == "year":
        start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        return q
    return q.filter(model.created_at >= start)


# ── Guard logs visitor ────────────────────────────────────────────────────────

@router.post("/create", response_model=schemas.VisitorResponse, status_code=201)
def create_visitor(visitor: schemas.VisitorCreate, db: Session = Depends(get_db)):
    if visitor.logged_by is not None:
        guard = db.query(models.User).filter(models.User.id == visitor.logged_by).first()
        if not guard:
            raise HTTPException(status_code=404,
                detail=f"Guard with id {visitor.logged_by} not found")
        if guard.role not in ("security", "admin"):
            raise HTTPException(status_code=403,
                detail="Only security personnel can log visitors")

    new_visitor = models.Visitor(
        visitor_name    = visitor.visitor_name,
        phone           = visitor.phone,
        flat_no         = visitor.flat_no,
        visitor_type    = visitor.visitor_type,
        logged_by       = visitor.logged_by,
        checkin_time    = visitor.checkin_time,
        checkin_date    = visitor.checkin_date,
        is_prescheduled = visitor.is_prescheduled,
        status          = "approved" if visitor.is_prescheduled else "pending",
    )
    db.add(new_visitor)
    db.commit()
    db.refresh(new_visitor)
    return new_visitor


# ── Resident pre-schedules visitor ───────────────────────────────────────────

@router.post("/preschedule", response_model=schemas.VisitorResponse, status_code=201)
def preschedule_visitor(visitor: schemas.VisitorCreate, db: Session = Depends(get_db)):
    new_visitor = models.Visitor(
        visitor_name    = visitor.visitor_name,
        phone           = visitor.phone,
        flat_no         = visitor.flat_no,
        visitor_type    = visitor.visitor_type,
        logged_by       = visitor.logged_by,
        checkin_time    = visitor.checkin_time,
        checkin_date    = visitor.checkin_date,
        is_prescheduled = True,
        status          = "approved",
    )
    db.add(new_visitor)
    db.commit()
    db.refresh(new_visitor)
    return new_visitor


# ── Guard checks out visitor ──────────────────────────────────────────────────

@router.post("/checkout", response_model=schemas.VisitorResponse)
def checkout_visitor(data: schemas.VisitorCheckout, db: Session = Depends(get_db)):
    visitor = db.query(models.Visitor).filter(models.Visitor.id == data.visitor_id).first()
    if not visitor:
        raise HTTPException(status_code=404, detail="Visitor not found")
    if visitor.checkout_time:
        raise HTTPException(status_code=409, detail="Visitor already checked out")

    visitor.checkout_time = data.checkout_time
    visitor.checkout_date = data.checkout_date
    db.commit()
    db.refresh(visitor)
    return visitor


# ── Resident approves/rejects guard request ───────────────────────────────────

@router.post("/approve", response_model=schemas.VisitorResponse)
def approve_visitor(data: schemas.VisitorApprove, db: Session = Depends(get_db)):
    visitor = db.query(models.Visitor).filter(models.Visitor.id == data.visitor_id).first()
    if not visitor:
        raise HTTPException(status_code=404, detail="Visitor not found")
    if visitor.status != "pending":
        raise HTTPException(status_code=409,
            detail=f"Visitor request is already '{visitor.status}'")

    visitor.status = data.action
    db.commit()
    db.refresh(visitor)
    return visitor


# ── List visitors ─────────────────────────────────────────────────────────────

@router.get("/list", response_model=List[schemas.VisitorResponse])
def list_visitors(
    flat_no : Optional[str] = Query(None),
    status  : Optional[str] = Query(None),
    period  : Optional[str] = Query(None),
    skip    : int           = Query(0, ge=0),
    limit   : int           = Query(20, ge=1, le=100),
    db      : Session       = Depends(get_db),
):
    q = db.query(models.Visitor)
    if flat_no:
        q = q.filter(models.Visitor.flat_no == flat_no)
    if status:
        q = q.filter(models.Visitor.status == status)
    if period:
        q = _date_filter(q, models.Visitor, period)
    return q.order_by(models.Visitor.created_at.desc()).offset(skip).limit(limit).all()


# ── Dashboard metrics ─────────────────────────────────────────────────────────

@router.get("/dashboard/metrics")
def dashboard_metrics(
    period      : str           = Query("day"),
    flat_no     : Optional[str] = Query(None),
    db          : Session       = Depends(get_db),
):
    q = db.query(models.Visitor)
    if flat_no:
        q = q.filter(models.Visitor.flat_no == flat_no)
    q = _date_filter(q, models.Visitor, period)

    all_visitors = q.all()
    return {
        "period"         : period,
        "total"          : len(all_visitors),
        "pending"        : sum(1 for v in all_visitors if v.status == "pending"),
        "approved"       : sum(1 for v in all_visitors if v.status == "approved"),
        "rejected"       : sum(1 for v in all_visitors if v.status == "rejected"),
        "prescheduled"   : sum(1 for v in all_visitors if v.is_prescheduled),
        "checked_out"    : sum(1 for v in all_visitors if v.checkout_time),
    }


# ── Get single visitor ────────────────────────────────────────────────────────

@router.get("/{visitor_id}", response_model=schemas.VisitorResponse)
def get_visitor(visitor_id: int, db: Session = Depends(get_db)):
    visitor = db.query(models.Visitor).filter(models.Visitor.id == visitor_id).first()
    if not visitor:
        raise HTTPException(status_code=404, detail="Visitor not found")
    return visitor